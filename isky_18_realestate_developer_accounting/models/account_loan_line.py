from odoo import api, fields, models


class AccountLoanLine(models.Model):
    _inherit = 'account.loan.line'

    commission = fields.Monetary(string='Commission')
    # NOTE: 'payment' is intentionally left as principal+interest only (core definition) — the
    # core action_confirm() debits only principal+interest in its own move, so 'payment' must keep
    # matching that or the core's own journal entry becomes unbalanced by the commission amount.
    amount_due = fields.Monetary(string='Total Due', compute='_compute_amount_due')

    is_pi_accrual_posted = fields.Boolean(string='P&I Accrual Posted', compute='_compute_payment_state')
    is_pi_paid = fields.Boolean(string='P&I Paid', compute='_compute_payment_state')
    is_commission_accrual_posted = fields.Boolean(string='Commission Accrual Posted', compute='_compute_payment_state')
    is_commission_paid = fields.Boolean(string='Commission Paid', compute='_compute_payment_state')
    is_paid = fields.Boolean(string='Paid', compute='_compute_payment_state')

    @api.depends('principal', 'interest', 'commission')
    def _compute_amount_due(self):
        for line in self:
            line.amount_due = line.principal + line.interest + line.commission

    @api.depends('generated_move_ids.line_ids.reconciled', 'generated_move_ids.state', 'commission')
    def _compute_payment_state(self):
        for line in self:
            st_account = line.loan_id.short_term_account_id
            posted_payment_moves = line.generated_move_ids.filtered(
                lambda m: m.is_loan_payment_move and m.state == 'posted')

            pi_lines = posted_payment_moves.filtered(
                lambda m: not m.is_loan_commission_accrual
            ).line_ids.filtered(lambda l: l.account_id == st_account)
            line.is_pi_accrual_posted = bool(pi_lines)
            line.is_pi_paid = bool(pi_lines) and all(pi_lines.mapped('reconciled'))

            commission_lines = posted_payment_moves.filtered(
                lambda m: m.is_loan_commission_accrual
            ).line_ids.filtered(lambda l: l.account_id == st_account)
            line.is_commission_accrual_posted = bool(commission_lines)
            line.is_commission_paid = bool(commission_lines) and all(commission_lines.mapped('reconciled'))

            line.is_paid = line.is_pi_paid and (not line.commission or line.is_commission_paid)

    def action_register_payment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Register Payment — Principal & Interest',
            'res_model': 'account.loan.line.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_loan_line_id': self.id,
                'default_payment_type': 'principal_interest',
                'default_amount': self.principal + self.interest,
            },
        }

    def action_register_payment_commission(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Register Payment — Commission',
            'res_model': 'account.loan.line.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_loan_line_id': self.id,
                'default_payment_type': 'commission',
                'default_amount': self.commission,
            },
        }
