from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


SCRM = 'isky_18_realestate_developer_sales_crm'


@tagged('post_install', '-at_install')
class TestPhase4Commission(TransactionCase):
    """Phase 4 acceptance: one hierarchy engine, role-driven levels, and the commission basis
    with its lock."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        JL = self.env['job.level']
        self.lvl_sales = JL.create({
            'name': 'Sales Person', 'sequence': 10, 'is_sales_person': True,
            'company_id': self.company.id})
        self.lvl_manager = JL.create({
            'name': 'Sales Manager', 'sequence': 20, 'is_sales_manager': True,
            'company_id': self.company.id})
        self.lvl_sector = JL.create({
            'name': 'Sales Sector Manager', 'sequence': 30, 'is_sales_sector_manager': True,
            'company_id': self.company.id})
        self.lvl_director = JL.create({
            'name': 'Director', 'sequence': 40, 'is_directory': True,
            'company_id': self.company.id})

        def _user(login, level):
            # an email is required: mail.thread posts a tracking message when a reservation is
            # created, and it refuses to send without a sender address
            return self.env['res.users'].create({
                'name': login, 'login': login, 'email': '%s@example.com' % login,
                'company_id': self.company.id,
                'company_ids': [(6, 0, [self.company.id])], 'job_level_id': level.id})

        self.u_sales = _user('p4_sales', self.lvl_sales)
        self.u_manager = _user('p4_manager', self.lvl_manager)
        self.u_sector = _user('p4_sector', self.lvl_sector)
        self.u_director = _user('p4_director', self.lvl_director)

        self.team = self.env['crm.team'].create({
            'name': 'P4 Team', 'company_id': self.company.id,
            'sales_manager_id': self.u_manager.id,
            'operation_id': self.u_sector.id,
            'director_id': self.u_director.id,
        })
        self.env['crm.team.member'].create({
            'crm_team_id': self.team.id, 'user_id': self.u_sales.id})

        self.partner = self.env['res.partner'].create({
            'name': 'P4 Customer', 'national_id': 'P4-NID-0001'})
        # crm.lead has four NOT NULL columns with no default in this build: medium_id,
        # source_id, type and user_id (checked against information_schema, not guessed).
        self.source = self.env['utm.source'].search([], limit=1) or \
            self.env['utm.source'].create({'name': 'P4 Source'})
        self.medium = self.env['utm.medium'].search([], limit=1) or \
            self.env['utm.medium'].create({'name': 'P4 Medium'})
        self.project = self.env['realestate.project'].create({
            'name': 'P4 Project', 'abbreviation': 'P4P'})

        # #44: the acting user is a STANDARD Odoo CRM salesperson - base.group_user plus
        # sales_team.group_sale_salesman, nothing else. No approver groups, no
        # group_sale_manager. It IS u_sales, so the documents belong to the acting user and
        # core CRM's own-documents record rule is satisfied without widening any group.
        self.u_sales.groups_id = [
            (6, 0, [self.env.ref('base.group_user').id,
                    self.env.ref('sales_team.group_sale_salesman').id])]
        self.operator = self.u_sales

    def _reservation(self):
        return self.env['real.estate.sale.reservation'].create({
            'customer_id': self.partner.id, 'company_id': self.company.id,
            'project_id': self.project.id, 'user_id': self.u_sales.id})

    def _contract(self, reservation=None):
        """A contract resolves its project through its unit or the reservation it came from
        (sale.proposal has no project_id of its own - step 5 finding). The fixture links it to
        a reservation, which is how a real contract is created; without a resolvable project it
        would legitimately fall back to the company default."""
        return self.env['sale.proposal'].create({
            'customer_id': self.partner.id, 'company_id': self.company.id,
            'user_id': self.u_sales.id,
            'sale_contract_reservation_id': (reservation or self._reservation()).id})

    # -- acceptance 1: commission only on the selected basis document -------------------
    def test_basis_reservation_only(self):
        self.project.commission_basis_mode = 'reservation'
        res = self._reservation()
        con = self._contract(res)
        res._build_commission_hierarchy()
        con._build_commission_hierarchy()
        self.assertTrue(res.commission_ids, "basis=reservation must calculate on the reservation")
        self.assertFalse(con.commission_ids, "basis=reservation must NOT calculate on the contract")

    def test_basis_contract_only(self):
        self.project.commission_basis_mode = 'contract'
        res = self._reservation()
        con = self._contract(res)
        res._build_commission_hierarchy()
        con._build_commission_hierarchy()
        self.assertFalse(res.commission_ids, "basis=contract must NOT calculate on the reservation")
        self.assertTrue(con.commission_ids, "basis=contract must calculate on the contract")

    def test_no_double_calculation(self):
        """Whatever the basis, exactly one of the two documents calculates.

        A fresh project per basis, because the lock rightly refuses to change the basis once
        commission exists - the first iteration would otherwise block the second."""
        for basis in ('reservation', 'contract'):
            project = self.env['realestate.project'].create({
                'name': 'P4 %s' % basis, 'abbreviation': 'P4%s' % basis[:1].upper(),
                'commission_basis_mode': basis})
            res = self.env['real.estate.sale.reservation'].create({
                'customer_id': self.partner.id, 'company_id': self.company.id,
                'project_id': project.id, 'user_id': self.u_sales.id})
            con = self._contract(res)
            res._build_commission_hierarchy()
            con._build_commission_hierarchy()
            self.assertEqual(
                bool(res.commission_ids), basis == 'reservation',
                "reservation calculated wrongly for basis=%s" % basis)
            self.assertEqual(
                bool(con.commission_ids), basis == 'contract',
                "contract calculated wrongly for basis=%s" % basis)
            self.assertTrue(
                bool(res.commission_ids) != bool(con.commission_ids),
                "exactly one document must calculate, never both and never neither")

    # -- acceptance 2: basis locks once commission exists ------------------------------
    def test_basis_change_rejected_after_commission(self):
        self.project.commission_basis_mode = 'reservation'
        res = self._reservation()
        res._build_commission_hierarchy()
        self.assertTrue(res.commission_ids)
        self.assertTrue(self.project._has_commission())

        # re-writing the same value stays allowed, or the project form would be unsaveable
        self.project.commission_basis_mode = 'reservation'
        with self.assertRaises(ValidationError) as caught:
            self.project.commission_basis_mode = 'contract'
        self.assertIn(self.project.name, str(caught.exception))

    def test_basis_change_rejected_even_if_deal_cancelled(self):
        """The plan requires the lock to hold 'even if the deal is cancelled'."""
        self.project.commission_basis_mode = 'reservation'
        res = self._reservation()
        res._build_commission_hierarchy()
        self.assertTrue(self.project._has_commission())

        # The state value is 'cancelled', not 'cancel'. The previous version of this test wrote
        # 'cancel' inside a bare try/except, so the write raised on an invalid selection value
        # and was swallowed - the deal was never actually cancelled and this criterion was
        # never really tested. Written directly and asserted, because action_cancel() opens a
        # wizard.
        self.assertIn('cancelled', dict(res._fields['state'].selection),
                      "the reservation must have a cancelled state to test this criterion")
        res.state = 'cancelled'
        self.assertEqual(res.state, 'cancelled', "the deal really is cancelled")
        self.assertTrue(self.project._has_commission(),
                        "cancelling the deal must not unlock the basis")
        with self.assertRaises(ValidationError):
            self.project.commission_basis_mode = 'contract'

    def test_company_basis_locked_while_inheriting_project_has_commission(self):
        self.project.commission_basis_mode = 'inherit'
        self.company.commission_basis = 'reservation'
        res = self._reservation()
        res._build_commission_hierarchy()
        self.assertTrue(self.project._has_commission())
        self.company.commission_basis = 'reservation'      # no-op write allowed
        with self.assertRaises(ValidationError) as caught:
            self.company.commission_basis = 'contract'
        self.assertIn(self.company.name, str(caught.exception))

    def test_basis_change_allowed_before_commission(self):
        clean = self.env['realestate.project'].create({
            'name': 'P4 Clean', 'abbreviation': 'P4C'})
        self.assertFalse(clean._has_commission())
        clean.commission_basis_mode = 'reservation'
        clean.commission_basis_mode = 'contract'
        clean.commission_basis_mode = 'inherit'
        self.assertEqual(clean.commission_basis_mode, 'inherit')

    # -- acceptance 3: same manager mapping across all four documents -------------------
    def _project(self, name, basis):
        return self.env['realestate.project'].create({
            'name': 'P4 %s' % name, 'abbreviation': 'P4%s' % name[:2].upper(),
            'commission_basis_mode': basis})

    def _as_operator(self, model, vals):
        """Create as a real user, so the record passes through every gate a user hits."""
        return self.env[model].with_user(self.operator).create(vals)

    def _lead(self):
        return self._as_operator('crm.lead', {
            'name': 'P4 Opp', 'type': 'opportunity', 'user_id': self.u_sales.id,
            'company_id': self.company.id, 'team_id': self.team.id,
            'source_id': self.source.id, 'medium_id': self.medium.id,
            'phone': '+20 100 000 0000',
            # not a workaround: is_personal_lead means "do not round-robin this lead", and
            # without it crm.lead.create() reassigns user_id to whoever the rotation picks,
            # which would compare four documents with different salespeople.
            'is_personal_lead': True})

    @staticmethod
    def _mapping(doc):
        """Who is on the hierarchy, and in which role."""
        return {(line.employee_id.id, line.job_level_id.id) for line in doc.commission_ids}

    @staticmethod
    def _participants(doc):
        """The engine's participant resolution, which the commission basis does not gate - so
        it is comparable across all four documents at once."""
        return {user.id for user, _label in doc._commission_participants()}

    def test_standard_salesperson_creates_opportunity_but_cannot_approve(self):
        """#44: a standard Odoo CRM user - base.group_user + sales_team.group_sale_salesman and
        nothing else - creates an opportunity with the approval statuses at their 'pending'
        default. Setting a status to an actual decision still requires the approver group."""
        # asserted as the requirement rather than as an exact set: Odoo's implied-groups
        # machinery adds technical groups behind base.group_user, so an equality check would
        # fail for reasons that have nothing to do with #44.
        self.assertTrue(self.operator.has_group('base.group_user'))
        self.assertTrue(self.operator.has_group('sales_team.group_sale_salesman'))
        self.assertFalse(self.operator.has_group('sales_team.group_sale_manager'),
                         "no manager group: a plain salesperson must suffice")
        for approver in ('approval_manager_group', 'financial_manager_group',
                         'operation_manager_group', 'operation_executive_group',
                         'sales_manager_group'):
            self.assertFalse(
                self.operator.has_group('%s.%s' % (SCRM, approver)),
                "the acting user must hold no approver group (%s)" % approver)

        lead = self._lead()
        self.assertTrue(lead.id, "a standard salesperson must be able to create an opportunity")
        for doc in ('eoi', 'contract', 'reservation'):
            for role in ('manager', 'financial', 'operations'):
                self.assertEqual(
                    lead['%s_status_for_%s' % (doc, role)], 'pending',
                    "the statuses kept their default, so no approval was implied")

        # a real approval decision is still gated
        with self.assertRaises(UserError):
            lead.with_user(self.operator).write({'contract_status_for_financial': 'approved'})
        with self.assertRaises(UserError):
            lead.with_user(self.operator).write({'eoi_status_for_manager': 'rejected'})

    def test_same_manager_mapping_across_documents(self):
        """Criterion C: the same manager mapping across lead, EOI, reservation and contract.

        All four, as a real non-superuser. Two projects are used because criterion A means a
        reservation and a contract cannot both calculate under one basis, and the basis lock
        forbids switching once commission exists - so the reservation is driven under
        basis=reservation and the contract under basis=contract, then the four mappings are
        compared. Lead and EOI are not basis-gated (Phase 3 fixes them as informational).
        """
        proj_res = self._project('Res', 'reservation')
        proj_con = self._project('Con', 'contract')

        reservation = self._as_operator('real.estate.sale.reservation', {
            'customer_id': self.partner.id, 'company_id': self.company.id,
            'project_id': proj_res.id, 'user_id': self.u_sales.id})
        contract = self._as_operator('sale.proposal', {
            'customer_id': self.partner.id, 'company_id': self.company.id,
            'user_id': self.u_sales.id,
            'sale_contract_reservation_id': self._as_operator(
                'real.estate.sale.reservation', {
                    'customer_id': self.partner.id, 'company_id': self.company.id,
                    'project_id': proj_con.id, 'user_id': self.u_sales.id}).id})
        eoi = self._as_operator('eoi.eoi', {
            'customer_id': self.partner.id, 'company_id': self.company.id,
            'user_id': self.u_sales.id})
        lead = self._lead()

        docs = {'reservation': reservation, 'contract': contract, 'eoi': eoi, 'lead': lead}
        for name, doc in docs.items():
            doc.with_user(self.operator)._build_commission_hierarchy()

        # every document must be eligible in its own right, so an empty mapping cannot pass
        # by accident
        for name, doc in docs.items():
            self.assertTrue(
                doc.commission_ids,
                "%s produced no commission hierarchy at all - criterion C cannot be judged "
                "from an empty set" % name)

        baseline_name, baseline = 'reservation', self._mapping(reservation)
        for name, doc in docs.items():
            self.assertEqual(
                self._mapping(doc), baseline,
                "%s mapping differs from the %s mapping; one engine must give one answer"
                % (name, baseline_name))

        # and the basis-independent participant set agrees across all four
        participant_sets = {name: self._participants(doc) for name, doc in docs.items()}
        self.assertEqual(len(set(map(frozenset, participant_sets.values()))), 1,
                         "participants differ across documents: %s" % participant_sets)

        # all four roles present, including Sales Sector Manager, which the old lead copy
        # omitted entirely
        levels = {line.job_level_id for line in reservation.commission_ids}
        for lvl in (self.lvl_sales, self.lvl_manager, self.lvl_sector, self.lvl_director):
            self.assertIn(lvl, levels, "%s must be in the hierarchy" % lvl.name)
        self.assertEqual(len(baseline), 4, "four people, four roles")

    def test_unteamed_user_still_gets_a_line(self):
        """D3: the EOI copy used to clear every line when the salesperson had no team, which
        silently dropped their commission."""
        loner = self.env['res.users'].create({
            'name': 'p4_loner', 'login': 'p4_loner', 'email': 'p4_loner@example.com',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])], 'job_level_id': self.lvl_sales.id})
        eoi = self.env['eoi.eoi'].create({
            'customer_id': self.partner.id, 'company_id': self.company.id,
            'user_id': loner.id})
        eoi._build_commission_hierarchy()
        self.assertEqual(len(eoi.commission_ids), 1)
        self.assertEqual(eoi.commission_ids.employee_id, loner)

    # -- role flags, not names ---------------------------------------------------------
    def test_role_comes_from_job_level_not_a_name_string(self):
        """D2: the role is job_level_id. Renaming a job level must not change the role."""
        self.project.commission_basis_mode = 'reservation'
        res = self._reservation()
        res._build_commission_hierarchy()
        line = res.commission_ids.filtered(lambda l: l.employee_id == self.u_manager)
        self.assertTrue(line, "the sales manager must be in the hierarchy")
        self.assertEqual(line.job_level_id, self.lvl_manager)

        self.lvl_manager.name = 'Renamed Entirely'
        res._build_commission_hierarchy()
        line = res.commission_ids.filtered(lambda l: l.employee_id == self.u_manager)
        self.assertEqual(line.job_level_id, self.lvl_manager,
                         "the role must survive renaming the job level")
        self.assertEqual(line.jop_position, 'Renamed Entirely',
                         "the legacy Char follows the level's name")

    def test_job_level_role_unique_per_company_not_globally(self):
        """The plan requires job levels per company; the old constraint was global."""
        other = self.env['res.company'].create({'name': 'P4 Other Co'})
        # same role, different company: allowed
        twin = self.env['job.level'].create({
            'name': 'Sales Person (other co)', 'is_sales_person': True,
            'company_id': other.id})
        self.assertTrue(twin.id)
        # same role, same company: rejected
        with self.assertRaises(ValidationError):
            self.env['job.level'].create({
                'name': 'Duplicate', 'is_sales_person': True,
                'company_id': self.company.id})

    def test_job_level_requires_at_least_one_role(self):
        with self.assertRaises(ValidationError):
            self.env['job.level'].create({'name': 'No role', 'company_id': self.company.id})

    # -- one engine, one model ---------------------------------------------------------
    def test_single_engine_and_single_model(self):
        """D1/D2: all four documents share the engine and the L3 line model."""
        for model in ('crm.lead', 'eoi.eoi', 'real.estate.sale.reservation', 'sale.proposal'):
            self.assertEqual(
                self.env[model]._fields['commission_ids'].comodel_name, 'realestate.commission',
                "%s must use the shared L3 line model" % model)
            self.assertTrue(hasattr(self.env[model], '_commission_lines'),
                            "%s must get the shared engine" % model)
        # the deprecated L2 duplicate is no longer referenced by any commission_ids
        self.assertIn('commission.commission', self.env,
                      "kept defined for the legacy ACL; see backlog #43")
