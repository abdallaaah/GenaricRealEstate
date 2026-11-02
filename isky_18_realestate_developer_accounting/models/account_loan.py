from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare
from odoo.tools.misc import format_date


class AccountLoan(models.Model):
    _inherit = 'account.loan'

    commission_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Commission Account',
        tracking=True,
        domain="[('account_type', 'in', ('expense', 'expense_depreciation'))]",
    )
    commission = fields.Monetary(string='Commission', tracking=True)
    commission_difference = fields.Monetary(compute='_compute_commission_difference')

    payment_move_ids = fields.One2many('account.move', 'settlement_loan_id', string='Payments')
    payment_move_count = fields.Integer(compute='_compute_payment_move_count')

    # --- Payment Summary (paid vs remaining, per category) ---
    principal_paid = fields.Monetary(compute='_compute_payment_summary')
    principal_remaining = fields.Monetary(compute='_compute_payment_summary')
    interest_paid = fields.Monetary(compute='_compute_payment_summary')
    interest_remaining = fields.Monetary(compute='_compute_payment_summary')
    commission_paid = fields.Monetary(compute='_compute_payment_summary')
    commission_remaining = fields.Monetary(compute='_compute_payment_summary')
    total_paid = fields.Monetary(compute='_compute_payment_summary')
    total_remaining = fields.Monetary(compute='_compute_payment_summary')

    @api.depends('commission', 'line_ids.commission', 'currency_id')
    def _compute_commission_difference(self):
        for loan in self:
            loan.commission_difference = abs(
                loan.commission - loan.currency_id.round(sum(loan.line_ids.mapped('commission'))))

    def _compute_payment_move_count(self):
        for loan in self:
            loan.payment_move_count = len(loan.payment_move_ids)

    @api.depends(
        'amount_borrowed', 'interest', 'commission',
        'line_ids.principal', 'line_ids.interest', 'line_ids.commission',
        'line_ids.is_pi_paid', 'line_ids.is_commission_paid',
    )
    def _compute_payment_summary(self):
        for loan in self:
            pi_paid_lines = loan.line_ids.filtered('is_pi_paid')
            commission_paid_lines = loan.line_ids.filtered('is_commission_paid')
            loan.principal_paid = sum(pi_paid_lines.mapped('principal'))
            loan.interest_paid = sum(pi_paid_lines.mapped('interest'))
            loan.commission_paid = sum(commission_paid_lines.mapped('commission'))
            loan.principal_remaining = loan.amount_borrowed - loan.principal_paid
            loan.interest_remaining = loan.interest - loan.interest_paid
            loan.commission_remaining = loan.commission - loan.commission_paid
            loan.total_paid = loan.principal_paid + loan.interest_paid + loan.commission_paid
            loan.total_remaining = loan.principal_remaining + loan.interest_remaining + loan.commission_remaining

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payments'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('settlement_loan_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_confirm(self):
        # Runs the normal core flow first (validations, amortization moves, LT/ST reclassification)
        # untouched, then additively books a commission accrual per line — never modifies core behavior.
        res = super().action_confirm()
        for loan in self:
            commission_lines = loan.line_ids.filtered(lambda l: l.commission)
            if not commission_lines:
                continue
            if not loan.commission_account_id:
                raise UserError(_(
                    "Set a Commission Account on the loan before confirming lines that have a commission amount."))
            if float_compare(loan.commission_difference, 0.0, precision_rounding=loan.currency_id.rounding) != 0:
                raise UserError(_(
                    "The loan commission %(loan_commission)s should be equal to the sum of the lines' "
                    "commission: %(lines_commission)s (difference %(diff)s)",
                    loan_commission=loan.currency_id.format(loan.commission),
                    lines_commission=loan.currency_id.format(sum(loan.line_ids.mapped('commission'))),
                    diff=loan.currency_id.format(loan.commission_difference),
                ))

            moves_values = []
            for line in commission_lines:
                date_from = format_date(self.env, line.date, date_format='MM/y')
                moves_values.append({
                    'company_id': loan.company_id.id,
                    'auto_post': 'at_date',
                    'generating_loan_line_id': line.id,
                    'is_loan_payment_move': True,
                    'is_loan_commission_accrual': True,
                    'date': line.date + relativedelta(day=31),
                    'journal_id': loan.journal_id.id,
                    'ref': f"{loan.name} - {_('Commission')} {date_from}",
                    'line_ids': [
                        (0, 0, {
                            'account_id': loan.commission_account_id.id,
                            'debit': line.commission,
                            'name': f"{loan.name} - {_('Commission')} {date_from}",
                        }),
                        (0, 0, {
                            'account_id': loan.short_term_account_id.id,
                            'credit': line.commission,
                            'name': f"{loan.name} - {_('Commission Due')} {date_from}",
                        }),
                    ],
                })
            moves = self.env['account.move'].create(moves_values)
            moves.filtered(lambda m: m.date <= fields.Date.context_today(self)).action_post()
        return res
