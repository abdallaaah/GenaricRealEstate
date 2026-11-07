import os

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from ..hooks import ADOPTED_STAGES, LEGACY_MODULE, THIS_MODULE, adopt_legacy_stage_xmlids

SC = 'isky_18_realestate_developer_sales_crm'

# every stage row this module seeds, with the flag that identifies it
LEAD_STAGES = {
    'stage_new': 'first',
    'stage_no_answer': 'no_answer',
    'stage_call_later': 'call_later',
    'stage_follow_up': 'follow_up',
    'stage_qualified': 'qualified',
    'stage_qualified_limited_budget': 'qualified_limited_budget',
    'stage_unqualified': 'unqualified',
    'stage_locked': 'locked',
}
CRM_STAGES = ('stage_lead5', 'stage_lead6', 'stage_lead7', 'stage_lead8')


@tagged('post_install', '-at_install')
class Test49LeadStages(TransactionCase):
    """#49: the lead stage rows live in this module, so the L2 lead workflow runs on a plain
    database. They used to be defined in `arkzayed_18_realestate_developer_crm`, which this
    module does not depend on, and all 34 call sites resolved those legacy xmlids."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        # a standard Odoo CRM salesperson and nothing more - the configuration #49 has to work
        # on. An email is required: mail.thread posts a tracking message on a lead.
        self.salesperson = self.env['res.users'].create({
            'name': 't49_sales', 'login': 't49_sales', 'email': 't49_sales@example.com',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('sales_team.group_sale_salesman').id])]})
        # locking a lead is gated on lead_admin_group, and editing an already locked one on
        # operation_manager_group, so a lock/unlock round trip needs both. Modelled as a second
        # user rather than widening the salesperson, because the plain salesperson is the
        # configuration #49 is about.
        self.lead_admin = self.env['res.users'].create({
            'name': 't49_admin', 'login': 't49_admin', 'email': 't49_admin@example.com',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('sales_team.group_sale_salesman').id,
                self.env.ref('%s.lead_admin_group' % SC).id,
                self.env.ref('%s.operation_manager_group' % SC).id])]})
        self.source = self.env['utm.source'].search([], limit=1) or \
            self.env['utm.source'].create({'name': 'T49 Source'})
        self.medium = self.env['utm.medium'].search([], limit=1) or \
            self.env['utm.medium'].create({'name': 'T49 Medium'})

    def _lead(self, user=None):
        user = user or self.salesperson
        return self.env['crm.lead'].with_user(user).create({
            'name': 'T49 Lead', 'type': 'lead', 'user_id': user.id,
            'company_id': self.company.id,
            'source_id': self.source.id, 'medium_id': self.medium.id,
            'phone': '+20 100 000 0000',
            # do not round-robin this lead away from the acting user
            'is_personal_lead': True})

    # -- 1 ---------------------------------------------------------------------------------
    def test_every_stage_row_is_owned_by_this_module(self):
        """The rows resolve from this module, on a database that need not have the legacy one."""
        for name, flag in LEAD_STAGES.items():
            stage = self.env.ref('%s.%s' % (SC, name))
            self.assertEqual(stage._name, 'lead.stage', name)
            self.assertTrue(stage[flag], "%s must carry its %s flag" % (name, flag))
        for name in CRM_STAGES:
            self.assertEqual(self.env.ref('%s.%s' % (SC, name))._name, 'crm.stage', name)

        # the two flags this module adds to crm.stage, as the legacy rows set them
        self.assertTrue(self.env.ref('%s.stage_lead7' % SC).is_collected)
        self.assertTrue(self.env.ref('%s.stage_lead8' % SC).is_confirmed_contract)

    # -- 2 ---------------------------------------------------------------------------------
    def test_lead_workflow_runs_for_a_plain_salesperson(self):
        """The acceptance of #49: new -> no answer -> follow up -> qualified, then converted to
        an opportunity, all as a user holding only base.group_user and
        sales_team.group_sale_salesman. Every one of these actions used to raise
        ValueError: External ID not found without the legacy CRM module.

        Locking is not in this walk, and qualifying comes last, because of two product rules a
        plain salesperson does not satisfy - both correct, neither a stage problem:
        `write()` refuses the Locked stage without `lead_admin_group`, and
        `_check_qualified_step_back_rights` refuses moving a *qualified* lead to any
        non-qualified stage. Both are covered by their own tests below."""
        lead = self._lead()
        acting = lead.with_user(self.salesperson)

        acting.write({'lead_stage_id': self.env.ref('%s.stage_new' % SC).id})
        self.assertTrue(acting.lead_stage_id.first)

        acting.action_no_answer()
        self.assertTrue(acting.lead_stage_id.no_answer, "action_no_answer must reach its stage")

        acting.action_follow_up_lead()
        self.assertTrue(acting.lead_stage_id.follow_up)

        # qualifying takes the direct route when the required information is present, and opens
        # a wizard otherwise; the direct route is the one that resolves the stage xmlid
        acting.write({
            'qualified_comment': 'ready', 'priority': '3', 'unit_type': 'residential',
            'finish_type': 'finished', 'min_area': 100, 'max_area': 200,
            'min_price': 1000, 'max_price': 2000})
        self.assertIs(acting.action_qualified_lead(), True)
        self.assertTrue(acting.lead_stage_id.qualified)

        customer = self.env['res.partner'].sudo().create({
            'name': 'T49 Customer', 'national_id': 'T49-NID-0001'})
        acting.convert_opportunity(customer)
        self.assertEqual(acting.type, 'opportunity',
                         "a plain salesperson must be able to convert the lead")

    # -- 3 ---------------------------------------------------------------------------------
    def test_limited_budget_qualification_resolves_at_last(self):
        """Backlog #56: `stage_qualified_limited_budget` was commented out in the legacy data
        file while two call sites resolved it, so this path always raised. The row now exists."""
        lead = self._lead()
        acting = lead.with_user(self.salesperson)
        acting.write({
            'qualified_comment': 'tight budget', 'priority': '2', 'unit_type': 'residential',
            'finish_type': 'semi_finished', 'min_area': 80, 'max_area': 120,
            'min_price': 500, 'max_price': 900})
        self.assertIs(acting.action_qualified_limited_budget_lead(), True)
        self.assertTrue(acting.lead_stage_id.qualified_limited_budget)

    # -- 4 ---------------------------------------------------------------------------------
    def test_unqualify_resolves_its_stage(self):
        """`state_to_unqualified_state()` takes the direct route once a lost reason is set."""
        lead = self._lead()
        acting = lead.with_user(self.salesperson)
        reason = self.env['crm.lost.reason'].sudo().search([], limit=1) or \
            self.env['crm.lost.reason'].sudo().create({'name': 'T49 Reason'})
        acting.sudo().write({'lost_reason_id': reason.id})
        self.assertIs(acting.state_to_unqualified_state(), True)
        self.assertTrue(acting.lead_stage_id.unqualified)

    # -- 5 ---------------------------------------------------------------------------------
    def test_adoption_points_this_module_at_an_existing_legacy_row(self):
        """An existing database must keep the stage records its leads already point at, instead
        of growing a duplicate set. `adopt_legacy_stage_xmlids()` gives the legacy row a second
        xmlid under this module, which is what makes the data file update it rather than insert.

        Simulated inside the transaction: this module's own xmlid for one stage is removed and a
        legacy xmlid is pointed at a different record, which is the shape of a database where
        only the legacy module ever defined the stages.
        """
        IMD = self.env['ir.model.data'].sudo()
        legacy_row = self.env['lead.stage'].sudo().create({
            'name': 'T49 Legacy Locked', 'locked': True, 'sequence': 80})
        ours = IMD.search([('module', '=', THIS_MODULE), ('name', '=', 'stage_locked')])
        self.assertTrue(ours, "the data file must have created this module's xmlid")
        ours.unlink()
        IMD.create({'module': LEGACY_MODULE, 'name': 'stage_locked',
                    'model': 'lead.stage', 'res_id': legacy_row.id, 'noupdate': False})

        adopted = adopt_legacy_stage_xmlids(self.env)

        self.assertIn('stage_locked', adopted)
        self.assertEqual(
            self.env.ref('%s.stage_locked' % SC), legacy_row,
            "this module's xmlid must now resolve to the record that already existed")

    # -- 6 ---------------------------------------------------------------------------------
    def test_adoption_is_idempotent_and_silent_without_the_legacy_module(self):
        """On a plain database there is nothing to adopt, and running it again changes nothing -
        which is why the migration can run unconditionally."""
        before = self.env['ir.model.data'].sudo().search_count(
            [('module', '=', THIS_MODULE), ('name', 'in', list(ADOPTED_STAGES))])
        self.assertEqual(adopt_legacy_stage_xmlids(self.env), [],
                         "nothing to adopt when every stage xmlid is already ours")
        self.assertEqual(
            self.env['ir.model.data'].sudo().search_count(
                [('module', '=', THIS_MODULE), ('name', 'in', list(ADOPTED_STAGES))]),
            before, "adoption must not create a second xmlid for a stage it already owns")

    # -- 7 ---------------------------------------------------------------------------------
    def test_lock_and_unlock_resolve_their_stages_for_a_lead_admin(self):
        """`stage_locked` and the return to `stage_new`, driven by the user the product gates
        those actions on."""
        lead = self._lead(self.lead_admin)
        acting = lead.with_user(self.lead_admin)
        acting.action_lock_lead()
        self.assertTrue(acting.lead_stage_id.locked)
        self.assertTrue(acting.locked)

        acting.action_unlock_lead()
        self.assertTrue(acting.lead_stage_id.first, "unlocking returns the lead to New")
        self.assertFalse(acting.locked)

    # -- 8 ---------------------------------------------------------------------------------
    def test_qualified_step_back_is_refused_for_a_plain_salesperson(self):
        """The rule the workflow test has to respect, pinned so a later change to it is
        deliberate: a qualified lead cannot be moved back by a plain salesperson. Two of the
        four groups that should grant this are referenced without a module prefix and therefore
        never match anyone - backlog #59, deliberately not changed here."""
        lead = self._lead()
        acting = lead.with_user(self.salesperson)
        acting.write({
            'qualified_comment': 'ready', 'priority': '3', 'unit_type': 'residential',
            'finish_type': 'finished', 'min_area': 100, 'max_area': 200,
            'min_price': 1000, 'max_price': 2000})
        self.assertIs(acting.action_qualified_lead(), True)
        with self.assertRaises(AccessError):
            acting.action_lock_lead()

    # -- 9 ---------------------------------------------------------------------------------
    def test_no_legacy_stage_xmlid_left_in_this_module(self):
        """Guard: a new reference to the legacy xmlids is the #49 bug again - it raises only at
        runtime, on a database where that module is absent."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        needle = '%s.stage_' % LEGACY_MODULE
        offenders = []
        for dirpath, _dirs, files in os.walk(root):
            if '__pycache__' in dirpath:
                continue
            for fn in files:
                if not fn.endswith(('.py', '.xml')):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding='utf-8') as fh:
                    for lineno, line in enumerate(fh, 1):
                        # hooks.py and this test name the legacy module on purpose, but never
                        # as a stage xmlid
                        if needle in line:
                            offenders.append('%s:%d' % (os.path.relpath(path, root), lineno))
        self.assertFalse(
            offenders,
            "a stage is still resolved from the legacy CRM module:\n%s" % '\n'.join(offenders))
