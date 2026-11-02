from odoo import models, fields, api, _
from datetime import date, datetime
import odoo.addons.decimal_precision as dp
from odoo.exceptions import ValidationError


class EmployeeProductExpense(models.Model):
    _name = 'employee.product.expense'
    _description = 'Employee Product Expense'

    @api.depends('payment_amount', 'price_unit', 'quantity', 'product_id', 'employee_custody_id.currency_id')
    def _compute_price(self):
        for rec in self:
            if rec.payment_amount:
                rec.price_subtotal = price_subtotal_signed = rec.payment_amount
            else:
                rec.price_subtotal = price_subtotal_signed = rec.quantity * rec.price_unit

            if rec.employee_custody_id.currency_id and rec.employee_custody_id.currency_id != rec.employee_custody_id.company_id.currency_id:
                price_subtotal_signed = rec.employee_custody_id.currency_id.compute(price_subtotal_signed,
                                                                                    rec.employee_custody_id.company_id.currency_id)
            rec.price_subtotal_signed = price_subtotal_signed

    @api.constrains('type')
    def _check_type(self):
        for val in self:
            if val.type == 'reimburse' and not val.employee_custody_id.employee_custody_category_id.fixed:
                raise ValidationError(_("Custody category must be checked 'Fixed' to add Reimburse type!!"))

    name = fields.Text(string='Description')
    product_id = fields.Many2one('product.product', string='Product', ondelete='restrict', index=True)
    account_id = fields.Many2one('account.account', string='Account',
                                 help="The expense account related to the selected product.")
    price_unit = fields.Monetary(string='Unit Price')
    price_subtotal = fields.Monetary(string='Amount', store=True, compute='_compute_price')
    price_subtotal_signed = fields.Monetary(string='Amount Signed', store=True, readonly=True, compute='_compute_price',
                                            help="Total amount in the currency of the company, negative for credit notes.")
    quantity = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), default=1)
    company_id = fields.Many2one('res.company', string='Company', related='employee_custody_id.company_id', store=True,
                                 readonly=True)
    currency_id = fields.Many2one('res.currency')
    company_currency_id = fields.Many2one('res.currency', related='employee_custody_id.company_currency_id',
                                          readonly=True)
    partner_id = fields.Many2one('res.partner', string='Supplier')
    check_invoice = fields.Boolean(string='Invoice?')
    type = fields.Selection([('payment', 'Payment'), ('direct_expense', 'Direct Expense'), ('payback', 'Payback'),
                             ('reimburse', 'Reimburse')], string='Type', required=True, default='direct_expense')

    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    employee_custody_id = fields.Many2one('employee.custody', string='Employee Custody', required=True,
                                          ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', related='employee_custody_id.employee_id', string='Employee',
                                  store=True)
    state = fields.Selection([('draft', 'New'),
                              ('open', 'Open'),  # used by cash statements
                              ('receiving_custody', 'Receiving Custody'),  # used by cash statements
                              ('pay', 'Payment'),  # used by cash statements
                              ('done', 'Closed'),
                              ('cancel', 'Cancelled')],
                             string='Status', related='employee_custody_id.state', store=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True,
                             default=lambda self: self.env['uom.uom'].search([], limit=1, order='id'))
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)

    attachment_ids = fields.Many2many(comodel_name='ir.attachment',
                                      relation='employee_expense_attachment_rel',
                                      column1='employee_expense_line_id',
                                      column2='attachment_id', string='Attachments')
    journal_id = fields.Many2one('account.journal', string='Payment Method', domain=[('type', 'in', ('bank', 'cash'))])
    payment_amount = fields.Monetary(string='Payment Amount')
    is_validated = fields.Boolean(string='Is validated?')
    amount_before_transaction = fields.Monetary(string='Amount Before Transaction', readonly=True)
    amount_after_transaction = fields.Monetary(string='Amount After Transaction',
                                               compute='_calc_amount_after_transaction')



    @api.onchange('product_id')
    def _get_account(self):
        for val in self:
            acc = val.product_id.product_tmpl_id.get_product_accounts()
            if acc.get('expense', False):
                val.account_id = acc['expense'].id

    @api.model
    def create(self, vals):
        if 'payment_amount' in vals or 'price_unit' in vals:
            res = super(EmployeeProductExpense, self).create(vals)
            remaining_amount = res.employee_custody_id.close_balance
            res.amount_before_transaction = remaining_amount
            return res
        else:
            return super(EmployeeProductExpense, self).create(vals)

    @api.depends('amount_before_transaction', 'price_subtotal', 'payment_amount', 'price_unit', 'quantity')
    def _calc_amount_after_transaction(self):
        for rec in self:
            rec.amount_after_transaction = rec.amount_before_transaction - rec.price_subtotal

    @api.constrains('date')
    def check_date(self):
        if (fields.Datetime.from_string(self.date)).date() > date.today():
            raise ValidationError('Date can not be greater than today!')

    # @api.onchange('date')
    # def _onchange_date(self):
    #     for rec in self:
    #         for line in rec.employee_custody_id.move_line_ids:
    #             if line.date > rec.date:
    #                 raise ValidationError("Transaction date should't be less than opening balance date")
    #             break
    #         return

    @api.onchange('type')
    def _onchange_type(self):
        return {'value': {'product_id': False,
                          'name': False,
                          'partner_id': False,
                          'account_analytic_id': False}}

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            domain = {}
            if not rec.employee_custody_id:
                return

            company = rec.employee_custody_id.company_id
            currency = rec.employee_custody_id.currency_id

            if not rec.product_id:
                rec.price_unit = 0.0
                domain['uom_id'] = []
            else:
                product = rec.product_id
                rec.name = product.description_purchase

                if product.name:
                    rec.name = product.name

                if product.list_price:
                    rec.price_unit = product.list_price

                if not rec.uom_id or product.uom_id.category_id.id != rec.uom_id.category_id.id:
                    rec.uom_id = product.uom_id.id
                domain['uom_id'] = [('category_id', '=', product.uom_id.category_id.id)]

                if company and currency:
                    if company.currency_id != currency:
                        rec.price_unit = rec.price_unit * currency.with_context(
                            dict(self._context or {}, date=fields.Date.today())).rate

                    if rec.uom_id and rec.uom_id.id != product.uom_id.id:
                        rec.price_unit = self.env['uom.uom'].browse(rec.uom_id.id)._compute_price(rec.price_unit,
                                                                                                  product.uom_id)
            return {'domain': domain}

    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        warning = {}
        result = {}
        for rec in self:
            rec._onchange_product_id()
            if not rec.uom_id:
                rec.price_unit = 0.0
            if rec.product_id and rec.uom_id:
                if rec.product_id.uom_id.category_id.id != rec.uom_id.category_id.id:
                    warning = {
                        'title': _('Warning!'),
                        'message': _(
                            'The selected unit of measure is not compatible with the unit of measure of the product.'),
                    }
                    rec.uom_id = rec.product_id.uom_id.id
            if warning:
                result['warning'] = warning
            return result

    def _get_analytic_line(self):
        for rec in self:
            ref = rec.employee_custody_id.name
            return {
                'name': rec.employee_custody_id.name,
                'date': fields.Date.today(),
                'account_id': rec.account_analytic_id.id,
                'unit_amount': rec.quantity,
                'amount': rec.price_subtotal_signed,
                'product_id': rec.product_id.id,
                'product_uom_id': rec.uom_id.id,
                'general_account_id': rec.account_id.id,
                'ref': ref,
            }

    def unlink(self):
        for line in self:
            if line.is_validated:
                linked_move = self.env['account.move'].search([
                    ('custody_id', '=', line.employee_custody_id.id),
                    ('related_custody_line_id', '=', line.id),
                ])
                if not linked_move:
                    # Fallback for old transactions created before related_custody_line_id
                    # was introduced: match by custody + date + amount on the move lines.
                    matching_move_lines = self.env['account.move.line'].search([
                        ('custody_id', '=', line.employee_custody_id.id),
                        ('date', '=', line.date),
                        '|',
                        ('debit', '=', line.price_subtotal),
                        ('credit', '=', line.price_subtotal),
                    ])
                    linked_move = matching_move_lines.mapped('move_id')
                if linked_move and any(m.state != 'cancel' for m in linked_move):
                    raise ValidationError(_('You cannot delete a validated transaction with journal entries. Please cancel or delete the related journal entry first.'))
                line.is_validated = False
        return super(EmployeeProductExpense, self).unlink()

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        res = super(EmployeeProductExpense, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                             orderby=orderby, lazy=lazy)
        if 'amount_before_transaction' in fields:
            for line in res:
                if '__domain' in line:
                    lines = self.search(line['__domain'])
                    inv_value = 0.0
                    for line2 in lines:
                        inv_value += line2.amount_before_transaction
                        break
                    line['amount_before_transaction'] = inv_value
        return res
