from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountLoanLinePaymentWizard(models.TransientModel):
    _name = 'account.loan.line.payment.wizard'
    _description = 'Register Payment for a Loan Line'

    loan_line_id = fields.Many2one('account.loan.line', required=True)
    loan_id = fields.Many2one(related='loan_line_id.loan_id')
    currency_id = fields.Many2one(related='loan_line_id.currency_id')
    payment_type = fields.Selection([
        ('principal_interest', 'Principal & Interest'),
        ('commission', 'Commission'),
    ], required=True, default='principal_interest')
    journal_id = fields.Many2one(
        'account.journal', string='Pay From', required=True,
        domain="[('type', 'in', ('bank', 'cash'))]",
    )
    date = fields.Date(default=fields.Date.context_today, required=True)
    amount = fields.Monetary(required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'journal_id' in fields_list and not res.get('journal_id'):
            journal = self.env['account.journal'].search(
                [('type', 'in', ('bank', 'cash')), ('company_id', '=', self.env.company.id)], limit=1)
            res['journal_id'] = journal.id
        return res

    def action_confirm(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(self.env._("The payment amount must be positive."))
        line = self.loan_line_id
        loan = line.loan_id
        if not self.journal_id.default_account_id:
            raise UserError(self.env._("The selected journal has no default account configured."))

        is_commission = self.payment_type == 'commission'
        label = self.env._("Commission") if is_commission else self.env._("Principal & Interest")

        # The relevant accrual (Interest+Principal, or Commission) for this line must already be
        # posted — otherwise there is nothing yet to settle, and we'd create a payment move with
        # nothing to reconcile it against (a real bug hit in testing: it silently created an orphan
        # entry). We validate here, on click, rather than hiding the button proactively.
        outstanding = line.generated_move_ids.filtered(
            lambda m: m.is_loan_payment_move and m.state == 'posted' and m.is_loan_commission_accrual == is_commission
        ).line_ids.filtered(lambda l: l.account_id == loan.short_term_account_id and not l.reconciled)
        if not outstanding:
            raise UserError(self.env._(
                "This line's %(label)s accrual hasn't been posted yet — there is nothing to settle. "
                "It will auto-post on %(date)s, or ask your accountant to post it manually first if "
                "you need to pay early.", label=label, date=line.date))

        move = self.env['account.move'].create({
            'date': self.date,
            'journal_id': self.journal_id.id,
            'is_loan_payment_move': True,
            'settlement_loan_id': loan.id,
            'ref': self.env._("%(loan)s - %(label)s Payment %(date)s", loan=loan.name, label=label, date=line.date),
            'line_ids': [
                (0, 0, {
                    'account_id': loan.short_term_account_id.id,
                    'debit': self.amount,
                    'name': self.env._("%(loan)s - %(label)s Payment %(date)s",
                                        loan=loan.name, label=label, date=line.date),
                }),
                (0, 0, {
                    'account_id': self.journal_id.default_account_id.id,
                    'credit': self.amount,
                    'name': self.env._("%(loan)s - %(label)s Payment %(date)s",
                                        loan=loan.name, label=label, date=line.date),
                }),
            ],
        })
        move.action_post()

        new_line = move.line_ids.filtered(lambda l: l.account_id == loan.short_term_account_id)
        (outstanding | new_line).reconcile()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._("Payment Registered"),
                'message': self.env._("%(amount)s (%(label)s) reconciled against %(loan)s.",
                                       amount=self.amount, label=label, loan=loan.name),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
