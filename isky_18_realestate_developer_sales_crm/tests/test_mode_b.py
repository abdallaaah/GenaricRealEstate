from odoo.tests.common import TransactionCase, tagged

SALES_ACCOUNTING = 'isky_18_realestate_developer_sales_accounting'
# States contributed only by the L1 accounting bridge. They stay as literals in sales_crm's
# filter methods (harmless: they simply never match in Mode B), so this test pins that they
# really are absent from the selection when the bridge is not installed.
BRIDGE_ONLY_PAYMENT_STATES = {'to_check', 'cfo_approved', 'deputy_cfo_approved'}


@tagged('post_install', '-at_install')
class TestModeB(TransactionCase):
    """Supplement S2: with the accounting layer absent (Mode B), no Mode A code path runs and
    nothing is posted to account.move. Written to be correct in BOTH modes so it is meaningful
    whichever module set is installed."""

    def _mode_a(self):
        mod = self.env['ir.module.module'].search([('name', '=', SALES_ACCOUNTING)], limit=1)
        return bool(mod) and mod.state == 'installed'

    def test_no_mode_a_path_when_bridge_absent(self):
        payment_cls = type(self.env['account.payment'])
        state_values = set(dict(self.env['account.payment']._fields['state'].selection or []))

        if self._mode_a():
            # Mode A: the bridge's coupling must be present.
            self.assertTrue(
                hasattr(payment_cls, '_create_collection_journal_entry'),
                "Mode A: sales_accounting should supply the collection-entry path.")
            self.assertTrue(
                BRIDGE_ONLY_PAYMENT_STATES <= state_values,
                "Mode A: the bridge's approval states should be in the selection.")
            return

        # --- Mode B ---
        self.assertFalse(
            hasattr(payment_cls, '_create_collection_journal_entry'),
            "Mode B: the revenue-split collection entry is a Mode A path and must not exist.")
        self.assertFalse(
            BRIDGE_ONLY_PAYMENT_STATES & state_values,
            "Mode B: bridge-only approval states must not be in account.payment.state; the "
            "literals left in sales_crm's filter methods are inert, not live.")

    def test_manual_paid_creates_no_journal_entry(self):
        """The Mode B way of settling money: manual Paid, zero accounting side effects.
        Asserted as a delta so pre-existing demo data cannot mask a regression."""
        Move = self.env['account.move']
        before = Move.search_count([])

        eoi = self.env['eoi.eoi'].create({'name': 'MODEB-TEST-EOI'})
        eoi.action_mark_paid()
        self.assertTrue(eoi.is_paid)
        self.assertTrue(eoi.paid_date, "S2 requires the Paid date to be stored.")
        self.assertTrue(eoi.paid_by_id, "S2 requires the Paid user to be stored.")

        line = self.env['installment.lines'].create({'name': 'MODEB-TEST-INST', 'amount': 500.0})
        line.action_mark_fully_paid()
        self.assertTrue(line.paid)
        self.assertTrue(line.paid_date, "S2 requires the Paid date to be stored.")
        self.assertTrue(line.paid_by_id, "S2 requires the Paid user to be stored.")

        self.assertEqual(
            Move.search_count([]), before,
            "Marking an EOI or installment Paid must not create any account.move.")
