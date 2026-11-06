import psycopg2

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestS8ChequeSettings(TransactionCase):
    """S8 acceptance tests: the incoming-cheque credit account setting (backlog #34) and the
    sales-linked cheque toggle."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.journal = self.env['account.journal'].search(
            [('type', 'in', ('bank', 'cash')), ('company_id', '=', self.company.id)], limit=1)
        self.account = self.env['account.account'].search(
            [('deprecated', '=', False), ('company_ids', 'in', self.company.ids)], limit=1)
        if not self.account:
            self.account = self.env['account.account'].search([('deprecated', '=', False)], limit=1)
        self.partner = self.env['res.partner'].create({
            'name': 'S8 Cheque Customer', 'national_id': 'S8-NID-0001',
        })
        self.assertTrue(self.journal, "a bank/cash journal is required")
        self.assertTrue(self.account, "an account is required")
        # the creating actions read this legacy parameter for the journal (backlog #33)
        self.env['ir.config_parameter'].sudo().set_param(
            'arkzayed_18_gt_cheque_management.journal_id', str(self.journal.id))

    def _cheque_vals(self, **extra):
        """Exactly what a real caller passes - deliberately WITHOUT credit_account, which is
        the whole point of backlog #34: no call site supplies it."""
        vals = {
            'payer': self.partner.id,
            'amount': 1000.0,
            'journal_id': self.journal.id,
            'cheq_type': 'incoming',
        }
        vals.update(extra)
        return vals

    # -- 1 ---------------------------------------------------------------------------------
    def test_cheque_create_with_setting(self):
        """Setting populated: creating a cheque succeeds and takes the configured account."""
        self.company.cheque_incoming_credit_account_id = self.account
        cheque = self.env['cheque.manage'].create(self._cheque_vals())
        self.assertTrue(cheque.id)
        self.assertEqual(
            cheque.credit_account, self.account,
            "credit_account must come from res.company.cheque_incoming_credit_account_id")

    # -- 2 ---------------------------------------------------------------------------------
    def test_cheque_create_without_setting(self):
        """Setting empty: a UserError naming the setting, and the NOT NULL never fires."""
        self.company.cheque_incoming_credit_account_id = False
        with self.assertRaises(UserError) as caught:
            self.env['cheque.manage'].create(self._cheque_vals())
        message = str(caught.exception)
        self.assertIn('cheque_incoming_credit_account_id', message,
                      "the error must name the setting field")
        self.assertIn('Incoming Cheque Credit Account', message,
                      "the error must name the setting as the user sees it")
        # the point of the fix: a clean UserError, not a database-level failure
        self.assertNotIsInstance(caught.exception, psycopg2.Error)
        self.assertNotIn('not-null', message.lower())
        self.assertNotIn('violates', message.lower())

    def test_cheque_create_without_setting_raises_before_insert(self):
        """The refusal happens before any INSERT, so the cursor stays usable - proof the
        NOT NULL constraint was never reached."""
        self.company.cheque_incoming_credit_account_id = False
        before = self.env['cheque.manage'].search_count([])
        with self.assertRaises(UserError):
            self.env['cheque.manage'].create(self._cheque_vals())
        # a NOT NULL violation would have aborted the transaction and made this raise
        self.assertEqual(self.env['cheque.manage'].search_count([]), before)

    # -- 3 ---------------------------------------------------------------------------------
    def test_cheque_generation_toggle_off(self):
        """cheques_enabled False: a sale proposal generates no cheque."""
        self.company.cheque_incoming_credit_account_id = self.account
        self.company.cheques_enabled = False
        proposal = self.env['sale.proposal'].create({
            'customer_id': self.partner.id, 'company_id': self.company.id,
        })
        before = self.env['cheque.manage'].search_count([])
        for action in ('action_create_cheques', 'action_open_combined_cheque_wizard'):
            with self.assertRaises(UserError, msg="%s must be gated" % action):
                getattr(proposal, action)()
        with self.assertRaises(UserError):
            proposal._generate_cheques(False)
        self.assertEqual(self.env['cheque.manage'].search_count([]), before,
                         "no cheque may be created from a deal while the toggle is off")

    def test_manual_cheque_unaffected_by_toggle(self):
        """The toggle gates deals only - a cheque registered by hand still works."""
        self.company.cheque_incoming_credit_account_id = self.account
        self.company.cheques_enabled = False
        cheque = self.env['cheque.manage'].create(self._cheque_vals())
        self.assertTrue(cheque.id, "manual cheque creation must not be gated")
        self.assertEqual(cheque.credit_account, self.account)

    def test_cheques_enabled_defaults_on(self):
        """Default = on, for an existing company and for a newly created one. Odoo backfills a
        new stored column with the field default, so this covers both."""
        self.assertTrue(
            self.env.company.cheques_enabled,
            "cheques_enabled must default to True on the company that already existed")
        fresh = self.env['res.company'].create({'name': 'S8 Fresh Co'})
        self.assertTrue(fresh.cheques_enabled,
                        "cheques_enabled must default to True on a new company")
        self.assertFalse(
            fresh.cheque_incoming_credit_account_id,
            "the credit account has no default - it must be configured explicitly")

    # -- 4 ---------------------------------------------------------------------------------
    def test_default_get_keeps_caller_value(self):
        """A caller's own credit account is never overwritten - not by the legacy default_get,
        and not by the company setting."""
        other = self.env['account.account'].search(
            [('deprecated', '=', False), ('id', '!=', self.account.id)], limit=1)
        self.assertTrue(other, "need a second account to prove the caller's value survives")
        self.company.cheque_incoming_credit_account_id = self.account

        # a) explicit in vals
        cheque = self.env['cheque.manage'].create(self._cheque_vals(credit_account=other.id))
        self.assertEqual(cheque.credit_account, other,
                         "an explicit credit_account must win over the setting")

        # b) via a default_credit_account context key, which the legacy default_get used to
        #    discard (this is the regression backlog #34 describes)
        defaults = self.env['cheque.manage'].with_context(
            default_cheq_type='incoming', default_credit_account=other.id,
        ).default_get(['credit_account', 'cheq_type'])
        self.assertEqual(defaults.get('credit_account'), other.id,
                         "default_get must not discard the caller's default_credit_account")

        ctx_cheque = self.env['cheque.manage'].with_context(
            default_credit_account=other.id).create(self._cheque_vals())
        self.assertEqual(ctx_cheque.credit_account, other,
                         "a context default must survive through create()")

    def test_default_get_falls_back_to_setting(self):
        """With no caller value, default_get offers the company setting."""
        self.company.cheque_incoming_credit_account_id = self.account
        defaults = self.env['cheque.manage'].with_context(
            default_cheq_type='incoming').default_get(['credit_account'])
        self.assertEqual(defaults.get('credit_account'), self.account.id)

    # -- every create path -----------------------------------------------------------------
    def test_all_sales_cheque_paths_covered_by_choke_point(self):
        """The fix lives on cheque.manage.create(), so every call site is covered. Assert the
        choke point is in place rather than re-testing each of the 11 callers."""
        self.assertTrue(hasattr(self.env['cheque.manage'], '_resolve_incoming_credit_account'))
        self.company.cheque_incoming_credit_account_id = self.account
        # a maintenance line's action is one of the 11 - drive it end to end
        proposal = self.env['sale.proposal'].create({
            'customer_id': self.partner.id, 'company_id': self.company.id,
        })
        line = self.env['maintenance.installment.lines'].create({
            'name': 'S8 maintenance', 'amount': 2500.0, 'serial': 1,
            'date': fields.Date.today(), 'sale_proposal_id': proposal.id,
        })
        line.action_create_cheque()
        cheque = line.allocation_ids.mapped('cheque_id')
        self.assertEqual(len(cheque), 1, "action_create_cheque must now succeed")
        self.assertEqual(cheque.credit_account, self.account)
        self.assertEqual(cheque.amount, 2500.0)
        self.assertEqual(line.payment_method_used, 'cheque')
