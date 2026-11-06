from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOwnershipFixes(TransactionCase):
    """The customer.ownership audit fixes: B1, B2, R1-R5, C1."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.p1 = self.env['res.partner'].create({'name': 'OF A', 'national_id': 'OF-1'})
        self.p2 = self.env['res.partner'].create({'name': 'OF B', 'national_id': 'OF-2'})
        self.project = self.env['realestate.project'].create({
            'name': 'OF Project', 'abbreviation': 'OFP'})
        self.CO = self.env['customer.ownership']

    def _reservation(self):
        return self.env['real.estate.sale.reservation'].create({
            'customer_id': self.p1.id, 'company_id': self.company.id,
            'project_id': self.project.id})

    def _contract(self, reservation=None):
        return self.env['sale.proposal'].create({
            'customer_id': self.p1.id, 'company_id': self.company.id,
            'sale_contract_reservation_id': (reservation or self._reservation()).id})

    def _template(self, *percentages):
        """Template rows: ownership lines with no parent."""
        return self.CO.create([
            {'customer_id': (self.p1 if i == 0 else self.p2).id, 'percentage': pct,
             'company_id': self.company.id}
            for i, pct in enumerate(percentages)
        ])

    # ================================================================== B1
    def test_copy_action_multi_line_template_succeeds_on_reservation(self):
        """B1: the copy action used to abort on any template with a line, because
        _compute_reservation_id did `return` instead of `continue`."""
        res = self._reservation()
        res.customer_ownership_ids = [(6, 0, self._template(60.0, 40.0).ids)]
        result = res.action_copy_customer_ownership_ids()
        self.assertEqual(result.get('tag'), 'display_notification')
        res.invalidate_recordset()
        self.assertEqual(len(res.customer_new_ownership_ids), 2)
        self.assertEqual(sum(res.customer_new_ownership_ids.mapped('percentage')), 100.0)
        self.assertTrue(all(res.customer_new_ownership_ids.mapped('from_action')))

    def test_copy_action_multi_line_template_succeeds_on_contract(self):
        """The contract path is the harder one: the copied lines carry no reservation_id in
        their vals, so the stored compute actually runs on a from_action record."""
        con = self._contract()
        con.customer_ownership_ids = [(6, 0, self._template(60.0, 40.0).ids)]
        con.action_copy_customer_ownership_ids()
        con.invalidate_recordset()
        self.assertEqual(len(con.customer_new_ownership_ids), 2)
        self.assertEqual(sum(con.customer_new_ownership_ids.mapped('percentage')), 100.0)

    def test_single_copy_implementation(self):
        """B1: one implementation, reached from both models."""
        import inspect
        fn_res = type(self.env['real.estate.sale.reservation']).action_copy_customer_ownership_ids
        fn_con = type(self.env['sale.proposal']).action_copy_customer_ownership_ids
        self.assertEqual(inspect.unwrap(fn_res), inspect.unwrap(fn_con),
                         "both models must resolve to the same function object")
        self.assertIn('split_line_mixin', inspect.getsourcefile(inspect.unwrap(fn_res)))

    # ================================================================== B2
    def test_contract_and_reservation_groups_are_separate(self):
        """B2: a contract line also carries reservation_id, so without precedence the
        reservation group totalled 200% and every later write raised."""
        res = self._reservation()
        con = self._contract(res)

        res_lines = self.CO.create([
            {'customer_id': self.p1.id, 'percentage': 60.0, 'reservation_id': res.id,
             'company_id': self.company.id},
            {'customer_id': self.p2.id, 'percentage': 40.0, 'reservation_id': res.id,
             'company_id': self.company.id},
        ])
        con_lines = self.CO.create([
            {'customer_id': self.p1.id, 'percentage': 60.0, 'contract_id': con.id,
             'company_id': self.company.id},
            {'customer_id': self.p2.id, 'percentage': 40.0, 'contract_id': con.id,
             'company_id': self.company.id},
        ])
        # the contract lines picked up reservation_id automatically - the link is kept
        con_lines.invalidate_recordset()
        self.assertTrue(all(l.reservation_id == res for l in con_lines),
                        "the automatic contract->reservation link must still be there")

        # each group totals exactly 100, and a further write does not raise
        self.assertEqual(sum(res_lines.mapped('percentage')), 100.0)
        self.assertEqual(sum(con_lines.mapped('percentage')), 100.0)
        res_lines[0].sequence = 5          # triggers the constrains on both groups
        con_lines[0].sequence = 5
        self.assertEqual(con_lines[0]._split_group_field(), 'contract_id',
                         "a line with a contract belongs to the contract group")
        self.assertEqual(res_lines[0]._split_group_field(), 'reservation_id')

    # ================================================================== R1
    def test_template_not_100_refused_and_creates_nothing(self):
        """R1: a template is validated at copy time, and a bad one creates nothing."""
        res = self._reservation()
        res.customer_ownership_ids = [(6, 0, self._template(150.0, 100.0).ids)]
        before = self.CO.search_count([])
        with self.assertRaises(ValidationError) as caught:
            res.action_copy_customer_ownership_ids()
        self.assertIn('250', str(caught.exception))
        self.assertEqual(self.CO.search_count([]), before,
                         "a refused copy must create nothing at all")
        self.assertFalse(res.customer_new_ownership_ids)

    def test_template_rows_may_be_edited_freely(self):
        """R1: template rows carry no parent, so they are not validated while being edited."""
        template = self._template(10.0)
        self.assertTrue(template.id)
        template.percentage = 250.0          # still fine: no parent
        self.assertEqual(template.percentage, 250.0)

    # ================================================================== R2
    def test_saved_zero_percent_line_refused(self):
        """R2: the escape that tolerated a blank row also tolerated a real 0% split."""
        res = self._reservation()
        with self.assertRaises(ValidationError):
            self.CO.create({'customer_id': self.p1.id, 'percentage': 0.0,
                            'reservation_id': res.id, 'company_id': self.company.id})

    def test_unsaved_zero_percent_row_accepted(self):
        """R2: a new, unsaved row in a form is never validated, so the form stays usable."""
        res = self._reservation()
        draft = self.CO.new({'customer_id': self.p1.id, 'percentage': 0.0,
                             'reservation_id': res.id, 'company_id': self.company.id})
        self.assertEqual(draft.percentage, 0.0, "an unsaved 0% row must be allowed to exist")
        self.assertFalse(draft.id.origin if hasattr(draft.id, 'origin') else False)

    # ================================================================== R3
    def _line_vals(self, **extra):
        vals = {'name': 'OF line', 'amount': 1000.0, 'serial': 1, 'date': fields.Date.today()}
        vals.update(extra)
        return vals

    def test_unparented_installment_line_refused(self):
        """R3: a line the project lock cannot see must not exist."""
        for model in ('installment.lines', 'maintenance.installment.lines'):
            with self.assertRaises(ValidationError, msg=model):
                self.env[model].create(self._line_vals())

    def test_line_with_reservation_accepted(self):
        res = self._reservation()
        line = self.env['installment.lines'].create(
            self._line_vals(reservation_id=res.id))
        self.assertTrue(line.id)
        self.assertTrue(self.project._has_installment_lines(),
                        "route 1 (reservation) must make the line visible to the lock")

    def test_lock_sees_contract_only_line_through_the_unit(self):
        """R3: the third route. A contract-only line is reachable only through
        sale_proposal_id.unit_id.project_id."""
        unit = self.env['real.estate.unit'].create({
            'name': 'OF Unit',
            'parent_source_id': 'realestate.project,%d' % self.project.id,
        })
        unit.invalidate_recordset()
        self.assertEqual(unit.project_id, self.project,
                         "the unit must resolve its project through the hierarchy")
        contract = self.env['sale.proposal'].create({
            'customer_id': self.p1.id, 'company_id': self.company.id, 'unit_id': unit.id})
        line = self.env['installment.lines'].create(
            self._line_vals(sale_proposal_id=contract.id))
        self.assertTrue(line.id)
        self.assertFalse(line.reservation_id, "no reservation: route 1 cannot apply")
        self.assertTrue(self.project._has_installment_lines(),
                        "the lock must find a contract-only line through the unit")

    def test_contract_without_unit_line_refused(self):
        """R3: a contract with no unit identifies no project, so the line is refused rather
        than created invisible to the lock."""
        contract = self.env['sale.proposal'].create({
            'customer_id': self.p1.id, 'company_id': self.company.id})
        with self.assertRaises(ValidationError):
            self.env['installment.lines'].create(
                self._line_vals(sale_proposal_id=contract.id))

    # ================================================================== R4
    def test_precision_read_from_financials_setting(self):
        """R4: the sum-to-100 precision comes from the setting, not a literal 2."""
        self.assertEqual(self.company.split_percentage_precision, 2,
                         "the shipped default must preserve the old behaviour")
        res = self._reservation()
        # 99.995 rounds to 100.00 at 2 decimals, so it passes
        lines = self.CO.create([
            {'customer_id': self.p1.id, 'percentage': 60.0, 'reservation_id': res.id,
             'company_id': self.company.id},
            {'customer_id': self.p2.id, 'percentage': 39.995, 'reservation_id': res.id,
             'company_id': self.company.id},
        ])
        self.assertEqual(len(lines), 2, "99.995% is exactly 100% at 2 decimals")

        # at 3 decimals the same split is wrong
        self.company.split_percentage_precision = 3
        res2 = self._reservation()
        with self.assertRaises(ValidationError):
            self.CO.create([
                {'customer_id': self.p1.id, 'percentage': 60.0, 'reservation_id': res2.id,
                 'company_id': self.company.id},
                {'customer_id': self.p2.id, 'percentage': 39.995, 'reservation_id': res2.id,
                 'company_id': self.company.id},
            ])
        self.company.split_percentage_precision = 2

    # ================================================================== R5
    def test_other_company_lines_do_not_count(self):
        """R5: the total is confined to the parent's company."""
        other = self.env['res.company'].create({'name': 'OF Other Co'})
        res = self._reservation()
        self.CO.create([
            {'customer_id': self.p1.id, 'percentage': 60.0, 'reservation_id': res.id,
             'company_id': self.company.id},
            {'customer_id': self.p2.id, 'percentage': 40.0, 'reservation_id': res.id,
             'company_id': self.company.id},
        ])
        # a line on the same reservation but owned by another company must be ignored; without
        # the company filter this would make the group total 150% and raise
        stray = self.CO.create({
            'customer_id': self.p2.id, 'percentage': 50.0, 'reservation_id': res.id,
            'company_id': other.id})
        self.assertTrue(stray.id, "the stray line itself is not validated against this group")
        groups = res.customer_new_ownership_ids._split_groups()
        for (_f, _pid), lines in groups.items():
            self.assertNotIn(stray, lines, "another company's line must not be in the group")
            self.assertEqual(sum(lines.mapped('percentage')), 100.0)

    # ================================================================== C1
    def test_cleanups(self):
        CO = self.env['customer.ownership']
        self.assertEqual(CO._order, 'sequence, id')
        self.assertEqual(self.env['realestate.split.line.mixin']._order, 'sequence, id',
                         "_order is declared on the mixin only - the concrete model inherits it")
        # the children constrains is declared on the concrete models now
        for model in ('real.estate.sale.reservation', 'sale.proposal'):
            self.assertTrue(hasattr(self.env[model], '_check_ownership_split_total'))
            self.assertTrue(hasattr(self.env[model], '_validate_split_children'))
        self.assertFalse(
            hasattr(self.env['realestate.split.parent.mixin'], 'customer_new_ownership_ids'),
            "the abstract mixin must not need a field it does not declare")
