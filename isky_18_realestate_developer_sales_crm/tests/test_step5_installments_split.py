from odoo import fields
from odoo.exceptions import ValidationError, UserError
from odoo.tests.common import TransactionCase, tagged

BRIDGE = 'isky_18_realestate_developer_sales_accounting'
L1_BRIDGE = 'isky_18_realestate_developer_accounting'


@tagged('post_install', '-at_install')
class TestStep5InstallmentsAndSplit(TransactionCase):
    """Phase 3 step 5: the installments toggle and the shared split model."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env['res.partner'].create({
            'name': 'Step5 Customer', 'national_id': 'S5-NID-0001',
        })
        self.other_partner = self.env['res.partner'].create({
            'name': 'Step5 Co-owner', 'national_id': 'S5-NID-0002',
        })
        self.project = self.env['realestate.project'].create({
            'name': 'Step5 Project', 'abbreviation': 'S5P',
        })

    def _bridge_installed(self, name):
        mod = self.env['ir.module.module'].search([('name', '=', name)], limit=1)
        return bool(mod) and mod.state == 'installed'

    def _reservation(self, project=None):
        return self.env['real.estate.sale.reservation'].create({
            'customer_id': self.partner.id,
            'company_id': self.company.id,
            'project_id': (project or self.project).id,
        })

    def _contract(self):
        return self.env['sale.proposal'].create({
            'customer_id': self.partner.id, 'company_id': self.company.id,
        })

    def _installment_line(self, reservation, amount=1000.0):
        return self.env['installment.lines'].create({
            'name': 'S5 line', 'amount': amount, 'serial': 1,
            'date': fields.Date.today(), 'reservation_id': reservation.id,
        })

    # -- 1 ---------------------------------------------------------------------------------
    def test_split_sum_not_100_rejected(self):
        """99 and 101 are rejected; 100 is accepted. Exactly, not approximately."""
        res_99 = self._reservation()
        with self.assertRaises(ValidationError) as caught:
            self.env['customer.ownership'].create({
                'customer_id': self.partner.id, 'percentage': 99.0,
                'reservation_id': res_99.id, 'company_id': self.company.id,
            })
        self.assertIn('100', str(caught.exception))

        res_101 = self._reservation()
        with self.assertRaises(ValidationError):
            self.env['customer.ownership'].create({
                'customer_id': self.partner.id, 'percentage': 101.0,
                'reservation_id': res_101.id, 'company_id': self.company.id,
            })

        res_100 = self._reservation()
        line = self.env['customer.ownership'].create({
            'customer_id': self.partner.id, 'percentage': 100.0,
            'reservation_id': res_100.id, 'company_id': self.company.id,
        })
        self.assertTrue(line.id, "a 100% split must be accepted")

        # two lines summing to 100, created in one batch as the real code does
        res_split = self._reservation()
        lines = self.env['customer.ownership'].create([
            {'customer_id': self.partner.id, 'percentage': 60.0,
             'reservation_id': res_split.id, 'company_id': self.company.id},
            {'customer_id': self.other_partner.id, 'percentage': 40.0,
             'reservation_id': res_split.id, 'company_id': self.company.id},
        ])
        self.assertEqual(len(lines), 2)
        self.assertEqual(sum(lines.mapped('percentage')), 100.0)

        # nudging one of them off 100 is rejected
        with self.assertRaises(ValidationError):
            lines[0].percentage = 59.0

    def test_split_no_lines_is_valid(self):
        """A single-owner deal has no split lines at all - that must stay valid."""
        res = self._reservation()
        self.assertFalse(res.customer_new_ownership_ids)
        res.flush_recordset()
        self.assertTrue(res.id, "a deal with no ownership lines must be valid")

    def test_split_deletion_leaving_partial_is_rejected(self):
        """Deleting one of two 50% lines leaves 50%. unlink() does not fire a line
        constraint, so the parent-level constraint has to catch it."""
        res = self._reservation()
        self.env['customer.ownership'].create([
            {'customer_id': self.partner.id, 'percentage': 50.0,
             'reservation_id': res.id, 'company_id': self.company.id},
            {'customer_id': self.other_partner.id, 'percentage': 50.0,
             'reservation_id': res.id, 'company_id': self.company.id},
        ])
        res.invalidate_recordset()
        victim = res.customer_new_ownership_ids[0]
        with self.assertRaises(ValidationError):
            res.write({'customer_new_ownership_ids': [(2, victim.id)]})

    # -- 2 ---------------------------------------------------------------------------------
    def test_split_shared_between_reservation_and_contract(self):
        """One model, one engine, both sides: the same customer.ownership rows are reachable
        from a reservation and from the contract it becomes."""
        CO = self.env['customer.ownership']
        self.assertIn('realestate.split.line.mixin', CO._inherit if isinstance(CO._inherit, list) else [CO._inherit])
        for model in ('real.estate.sale.reservation', 'sale.proposal'):
            self.assertTrue(
                hasattr(self.env[model], 'action_copy_customer_ownership_ids'),
                "%s must get the copy action from the shared parent mixin" % model)
            self.assertEqual(self.env[model]._fields['customer_new_ownership_ids'].comodel_name,
                             'customer.ownership')

        res = self._reservation()
        contract = self._contract()
        lines = CO.create([
            {'customer_id': self.partner.id, 'percentage': 70.0,
             'reservation_id': res.id, 'company_id': self.company.id},
            {'customer_id': self.other_partner.id, 'percentage': 30.0,
             'reservation_id': res.id, 'company_id': self.company.id},
        ])
        res.invalidate_recordset()
        self.assertEqual(set(res.customer_new_ownership_ids.ids), set(lines.ids))

        # the reservation->contract handover writes contract_id onto the same rows
        lines.write({'contract_id': contract.id})
        contract.invalidate_recordset()
        self.assertEqual(set(contract.customer_new_ownership_ids.ids), set(lines.ids),
                         "the same rows must be visible from the contract")
        self.assertEqual(sum(contract.customer_new_ownership_ids.mapped('percentage')), 100.0)

        # the shared sequence/ordering comes from the mixin
        self.assertIn('sequence', CO._fields)
        self.assertEqual(CO._order, 'sequence, id')

    # -- 3 ---------------------------------------------------------------------------------
    def test_toggle_off_creates_no_installment_lines(self):
        """Installments off: no lines are generated and the deal still completes."""
        self.project.installments_mode = 'off'
        self.assertFalse(self.project.installments_effective)

        res = self._reservation()
        self.assertFalse(res._installments_allowed())

        before = self.env['installment.lines'].search_count([])
        before_m = self.env['maintenance.installment.lines'].search_count([])

        # the actions must warn, never raise - the deal has to complete
        for action in ('action_calculate_installments', 'action_calculate_maintenance_installments'):
            result = getattr(res, action)()
            self.assertEqual(result.get('tag'), 'display_notification',
                             "%s must return a notification, not raise" % action)
            self.assertEqual(result['params']['type'], 'warning')

        # the builders produce nothing
        self.assertEqual(res._prepare_reservation_installment_lines(), [])
        self.assertEqual(res._prepare_reservation_maintenance_lines(), [])

        self.assertFalse(res.installment_ids)
        self.assertFalse(res.maintenance_installment_ids)
        self.assertEqual(self.env['installment.lines'].search_count([]), before)
        self.assertEqual(self.env['maintenance.installment.lines'].search_count([]), before_m)
        self.assertTrue(res.id, "the reservation itself must still be usable")

    def test_toggle_on_allows_generation(self):
        """The mirror of the test above: with the flag on, the gate does not block."""
        self.project.installments_mode = 'on'
        self.assertTrue(self.project.installments_effective)
        res = self._reservation()
        self.assertTrue(res._installments_allowed())
        # the gate passes, so the action proceeds to its own validation instead of warning.
        # Odoo's assertRaises does not accept a tuple of classes, hence the explicit catch.
        try:
            result = res.action_calculate_installments()
        except (ValidationError, UserError):
            pass   # reached the action's own checks - the gate did not block
        else:
            self.assertNotEqual(
                (result or {}).get('tag'), 'display_notification',
                "with installments on, the action must not return the off-warning")

    def test_project_inherits_company_default(self):
        """inherit mode follows the company, and an explicit mode overrides it."""
        self.project.installments_mode = 'inherit'
        self.company.installments_enabled = True
        self.assertTrue(self.project.installments_effective)
        self.company.installments_enabled = False
        self.project.invalidate_recordset()
        self.assertFalse(self.project.installments_effective)
        self.project.installments_mode = 'on'
        self.assertTrue(self.project.installments_effective,
                        "an explicit On must override a company default of off")
        self.company.installments_enabled = True

    # -- 4 ---------------------------------------------------------------------------------
    def test_toggle_change_rejected_after_lines_exist(self):
        """Both locks: the project override and the company default."""
        res = self._reservation()
        self._installment_line(res)
        self.assertTrue(self.project._has_installment_lines())

        # a) the project override. Re-writing the SAME value must stay allowed, or the
        #    project form would become unsaveable once any line existed.
        self.assertEqual(self.project.installments_mode, 'inherit')
        self.project.installments_mode = 'inherit'
        with self.assertRaises(ValidationError) as caught:
            self.project.installments_mode = 'off'
        self.assertIn(self.project.name, str(caught.exception))

        # b) the company default, while a project inheriting it has lines
        current = self.company.installments_enabled
        self.company.installments_enabled = current      # no-op write stays allowed
        with self.assertRaises(ValidationError) as caught_company:
            self.company.installments_enabled = not current
        self.assertIn(self.company.name, str(caught_company.exception))

    def test_toggle_change_allowed_before_lines_exist(self):
        """The lock must not block a project that has no lines yet."""
        clean = self.env['realestate.project'].create({
            'name': 'Step5 Clean', 'abbreviation': 'S5C',
        })
        self.assertFalse(clean._has_installment_lines())
        clean.installments_mode = 'off'
        clean.installments_mode = 'on'
        clean.installments_mode = 'inherit'
        self.assertEqual(clean.installments_mode, 'inherit')

    # -- 5 ---------------------------------------------------------------------------------
    def test_mode_b_installments_on_no_account_move(self):
        """Mode B, installments on: lines are tracked by the manual Paid button and no
        account.move is created (supplement S2)."""
        if self._bridge_installed(BRIDGE) or self._bridge_installed(L1_BRIDGE):
            self.skipTest("accounting bridge installed - this is the Mode B assertion")

        self.project.installments_mode = 'on'
        res = self._reservation()
        line = self._installment_line(res)

        group = self.env.ref('isky_18_realestate_developer_sales_crm.group_manual_paid_installment',
                             raise_if_not_found=False)
        self.assertTrue(group, "the manual-paid group must exist in Mode B")
        self.env.user.groups_id = [(4, group.id)]

        before = self.env['account.move'].search_count([])
        line.paid = True
        line.flush_recordset()
        self.assertTrue(line.paid)
        self.assertEqual(
            self.env['account.move'].search_count([]), before,
            "Mode B must create no journal entry when an installment is ticked Paid")

    # -- 6 ---------------------------------------------------------------------------------
    def test_mode_a_collections_unchanged(self):
        """Mode A regression: step 5 changes nothing outside the flag.

        Covers: with installments at their default the gate is open on all four generation
        paths, so Mode A behaves exactly as before; and the Mode A override chain is still
        bound (step 5 touched sale_proposal/sale_reservation, which the bridge extends).
        Does NOT re-test journal-entry content - that is the accounting bridge's own gate.
        """
        if not (self._bridge_installed(BRIDGE) or self._bridge_installed(L1_BRIDGE)):
            self.skipTest("no accounting bridge installed - this is the Mode A assertion")

        self.assertTrue(self.company.installments_enabled,
                        "the shipped default must leave installments on")
        self.project.installments_mode = 'inherit'
        res = self._reservation()
        contract = self._contract()
        self.assertTrue(res._installments_allowed())
        self.assertTrue(contract._installments_allowed())

        # a deal with no project at all must behave as it did before the toggle existed
        no_project = self.env['real.estate.sale.reservation'].create({
            'customer_id': self.partner.id, 'company_id': self.company.id,
        })
        self.assertFalse(no_project._installments_project())
        self.assertTrue(no_project._installments_allowed(),
                        "no project must fall back to the company default, not block")

        # the Mode A override chain is intact
        payment_model = self.env['account.payment']
        self.assertTrue(hasattr(payment_model, '_create_collection_journal_entry'),
                        "the Mode A collection entry builder must still be bound")

        # the gate itself creates no journal entries
        before = self.env['account.move'].search_count([])
        res._installments_allowed()
        contract._installments_allowed()
        self.assertEqual(self.env['account.move'].search_count([]), before)
