from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    custody_id = fields.Many2one('employee.custody', string='Employee Custody', copy=False)
    related_custody_line_id = fields.Many2one('employee.product.expense')
    total_debit = fields.Monetary(string='Total Debit', compute='_compute_total_debit_credit', currency_field='currency_id')
    total_credit = fields.Monetary(string='Total Credit', compute='_compute_total_debit_credit', currency_field='currency_id')

    def _is_custody_debit_move(self):
        """Return True if the first line's amount should be shown in the debit
        column of the list view — i.e. the move is a reimburse or payback."""
        self.ensure_one()
        if self.related_custody_line_id.type in ('reimburse', 'payback'):
            return True
        first_line = self.line_ids[:1]
        if not first_line:
            return False
        account_type = first_line.account_id.account_type or ''
        # direct_expense → first line is an expense account
        # payment       → first line is a payable account
        # payback       → first line is a cash/bank (asset) account
        # reimburse     → first line is the custody (asset) account
        if account_type.startswith('expense') or account_type == 'liability_payable':
            return False
        if account_type.startswith('asset'):
            return True
        return False

    @api.depends('line_ids.debit', 'line_ids.credit', 'line_ids.account_id',
                 'related_custody_line_id.type')
    def _compute_total_debit_credit(self):
        for move in self:
            total_debit = 0.0
            total_credit = 0.0
            first_line = move.line_ids[:1]
            if first_line:
                amount = first_line.debit + first_line.credit
                if move._is_custody_debit_move():
                    total_debit = amount
                else:
                    total_credit = amount
            move.total_debit = total_debit
            move.total_credit = total_credit


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    custody_id = fields.Many2one('employee.custody', string='Employee Custody', copy=False)
    account_move_type = fields.Selection([('payment', 'Payment'), ('direct_expense', 'Direct Expense'), ('payback', 'Payback'),
                             ('reimburse', 'Reimburse')], string='Type', default='direct_expense', copy=False)
    transaction_description = fields.Char(string='Transaction Description', copy=False)
