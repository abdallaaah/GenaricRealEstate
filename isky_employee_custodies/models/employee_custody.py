from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import ValidationError
from num2words import num2words
from datetime import date


class EmployeeCustody(models.Model):
    _name = 'employee.custody'
    _description = 'Employee Custody'
    _order = 'employee_code'

    # Read Group to display calculation of fields in group
    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        res = super(EmployeeCustody, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                      orderby=orderby, lazy=lazy)
        if 'employee_id' in fields and 'employee_id' in groupby:
            for line in res:
                total_amount_curr = 0
                get_custody_obj = self.env['employee.custody'].search([('employee_id', '=', line['employee_id'][0])])
                for each_em in get_custody_obj:
                    total_amount_curr += each_em.amount_currency
                line.update({
                    'amount_currency': total_amount_curr
                })
        return res

    def _get_amount_currency(self):
        for rec in self:
            if rec.currency_id.rate > 0:
                rec.amount_currency = rec.open_balance / rec.currency_id.rate

    @api.depends('employee_id')
    def _get_employee_custody_ids(self):
        for rec in self:
            employee_custody_objs = self.search([('employee_id', '=', rec.employee_id.id)])
            employee_custody_item_obj = self.env['employee.custody.item']

            for custody in employee_custody_objs:
                custody_item = employee_custody_item_obj.search([('employee_custody_id', '=', custody.id)])
                if not custody_item:
                    employee_custody_item_obj.create({'employee_custody_id': custody.id})

            employee_custody_item_objs = employee_custody_item_obj.search(
                [('employee_id', '=', self.employee_id.id), ('employee_custody_id', '!=', rec.id)])
            rec.employee_custody_item_ids = employee_custody_item_objs.ids if employee_custody_item_objs else False

    name = fields.Char(string='Reference', readonly=True, )
    employee_custody_category_id = fields.Many2one('employee.custody.category', string='Custody Category',
                                                   required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    employee_code = fields.Char(string='Employee Code', related='employee_id.employee_code', store=True)

    custody_date = fields.Date(string='Date', default=fields.Date.context_today)
    custody_close_date = fields.Date(string='Closing Date')
    custody_type = fields.Selection([
        ('temporary', 'Temporary'),
        ('permanent', 'Permanent')
    ], string='Custody Type', default='temporary')

    open_balance = fields.Monetary(string='Amount', copy=False)
    close_balance = fields.Monetary(string='Remaining Amount', store=True, readonly=True, compute='_calc_close_balance')

    total_transactions = fields.Monetary(string='Employee Transactions', store=True, readonly=True,
                                         compute='_calc_total_transactions')
    line_ids = fields.One2many('employee.product.expense', 'employee_custody_id', string='Transactions', copy=False)
    state = fields.Selection([('draft', 'New'),
                              ('open', 'Open'),
                              ('receiving_custody', 'Receiving Custody'),
                              ('pay', 'Payment'),
                              ('done', 'Closed'),
                              ('cancel', 'Cancelled')],
                             string='Status', required=True, readonly=True, default='draft')
    journal_id = fields.Many2one('account.journal', string='Journal', required=True)
    move_line_ids = fields.One2many('account.move.line', 'custody_id',
                                    'Entry lines', readonly=True)
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)

    company_id = fields.Many2one('res.company', string='Company', change_default=True,
                                 required=True,
                                 default=lambda self: self.env.company)

    description = fields.Text(string='Description')
    payment_method_id = fields.Many2one('account.journal', string='Payment Method', required=True)

    currency_id = fields.Many2one('res.currency', string='Currency',
                                  required=True,
                                  default=lambda self: self.env.user.company_id.currency_id, tracking=True)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    journal_entries_count = fields.Integer('Journal Entries Count', compute='_get_entries_count')
    invoices_count = fields.Integer('Invoices Count', compute='_get_invoices_count')

    employee_custody_item_ids = fields.One2many(compute='_get_employee_custody_ids',
                                                comodel_name='employee.custody.item',
                                                relation='employee_custody_id', string='Employee Custodies')
    arabic_amount = fields.Char(compute='_get_arabic_amount')
    amount_currency = fields.Float(string='Amounted Currency', compute="_get_amount_currency")

    reimburse_total_amount = fields.Monetary('Total Reimburse', copy=False)
    actual_open_balance = fields.Monetary('Actual Open Balance', copy=False)

    @api.onchange('actual_open_balance', 'line_ids')
    def get_open_balance(self):
        for rec in self:
            if rec.actual_open_balance and rec.line_ids:
                rec.open_balance = rec.actual_open_balance + sum([line.payment_amount for line in rec.line_ids if
                                                                  line.type == 'reimburse'])

    @api.onchange('open_balance', 'state')
    def change_reimburse_total_amount(self):
        for val in self:
            if val.state in ['draft', 'open']:
                val.actual_open_balance = val.open_balance

    @api.onchange('employee_id')
    def set_default_journal(self):
        for custody in self:
            if custody.employee_id and not custody.journal_id:
                custody.journal_id = custody.employee_id.company_id.custody_journal_id.id if custody.employee_id and custody.employee_id.company_id and custody.employee_id.company_id.custody_journal_id else False
            if custody.employee_id and not custody.payment_method_id:
                custody.payment_method_id = custody.employee_id.company_id.custody_payment_method_id.id if custody.employee_id and custody.employee_id.company_id and custody.employee_id.company_id.custody_payment_method_id else False

    @api.onchange('line_ids')
    def recompute_open_balance(self):
        for val in self:
            reimburse_total_amount = sum([line.price_subtotal for line in val.line_ids if
                                          line.type == 'reimburse'])
            val.reimburse_total_amount = reimburse_total_amount

    @api.depends('open_balance')
    def _get_arabic_amount(self):
        for rec in self:
            rec.arabic_amount = num2words(float(rec.open_balance), lang='en')

    @api.depends('move_id')
    def _get_entries_count(self):
        for rec in self:
            rec.journal_entries_count = self.env['account.move'].search_count([('custody_id', '=', rec.id)])

    @api.depends('line_ids')
    def _get_invoices_count(self):
        for rec in self:
            rec.invoices_count = self.env['account.move'].search_count([('custody_id', '=', rec.id)])

    @api.model
    def create(self, vals):
        if vals:
            vals.update({'name': self.env['ir.sequence'].next_by_code('custody.form.sequence')})
        return super(EmployeeCustody, self).create(vals)

    @api.depends('open_balance', 'total_transactions', 'state', 'line_ids')
    def _calc_close_balance(self):
        for rec in self:
            if rec.state == 'done':
                rec.close_balance = 0
            else:
                rec.close_balance = rec.open_balance - abs(rec.total_transactions)
            return True

    @api.depends('line_ids.price_subtotal', 'line_ids.type', 'currency_id', 'company_id')
    def _calc_total_transactions(self):
        for rec in self:
            rec.total_transactions = sum(
                line.price_subtotal if line.type != 'reimburse' else 0 for line in rec.line_ids)

    def button_validate(self):
        for rec in self:
            if rec.open_balance == 0.0:
                raise ValidationError('Please Add Amount First!')
            if rec.open_balance < 0.0:
                rec.with_context(button_type='receive').button_journal_entry()
                rec.write({'state': 'pay'})
            else:
                rec.state = 'open'

    def paid_custody(self):
        for rec in self:
            rec.write({'state': 'done', 'custody_close_date': fields.Date.today()})

    def cancel_custody(self):
        for rec in self:
            rec.write({'state': 'cancel'})
            if rec.employee_id.user_id:
                body = (_(
                    "Your Expense %s has been refused.<br/><ul class=o_timeline_tracking_value_list><li>Reason<span> : </span><span class=o_timeline_tracking_value>%s</span></li></ul>") % (
                            rec.name))
                rec.message_post(body=body, partner_ids=[rec.employee_id.user_id.partner_id.id])

    def unlink(self):
        for custody in self:
            if custody.state not in ['draft', 'cancel']:
                raise ValidationError(_('You can only delete draft or cancelled custody!'))
            posted_moves = self.env['account.move'].search([
                ('custody_id', '=', custody.id),
                ('state', '=', 'posted')
            ])
            if posted_moves:
                raise ValidationError(
                    _('You cannot delete custody "%s" because it has posted journal entries linked to it. Please cancel them first.') % custody.name
                )
        return super(EmployeeCustody, self).unlink()

    def _compute_expense_totals(self, company_currency, account_move_lines):
        for rec in self:
            total = 0.0
            total_currency = 0.0
            for line in account_move_lines:
                # In Odoo 18, currency_id is mandatory - always set to company currency by default
                line['currency_id'] = company_currency.id
                line['amount_currency'] = line['price']
                if rec.currency_id != company_currency:
                    line['currency_id'] = rec.currency_id.id
                    line['amount_currency'] = line['price']
                    line['price'] = rec.currency_id.with_context(
                        date=rec.custody_date or fields.Date.context_today(self)).compute(line['price'],
                                                                                          company_currency)
                total -= line['price']
                total_currency -= line['amount_currency'] or line['price']
            return total, total_currency, account_move_lines

    def _prepare_move_line(self, line):
        '''
        This function prepares move line of account.move related to an custody
        '''
        partner_id = self.employee_id.address_home_id.id
        # In Odoo 18, currency_id is mandatory - default to company currency
        currency_id = line.get('currency_id') or self.company_id.currency_id.id
        return {
            'date_maturity': line['date'],
            'partner_id': line['partner_id'],
            'name': line['name'],
            'date': line['date'],
            'debit': line['price'] > 0 and line['price'],
            'credit': line['price'] < 0 and -line['price'],
            'account_id': line['account_id'],
            'amount_currency': line.get('amount_currency') or (line['price'] > 0 and line['price'] or -line['price']),
            'currency_id': currency_id,
            'ref': line.get('ref'),
            'quantity': line.get('quantity', 1.00),
            'product_id': line.get('product_id'),
            'product_uom_id': line.get('uom_id'),
            'custody_id': self.id,
            'analytic_distribution': {str(line.get('account_analytic_id')): 100.0} if line.get('account_analytic_id') else False,
            'transaction_description': line.get('transaction_description') if line.get('price', 0) > 0 else False,
        }

    @api.constrains('custody_close_date')
    def constrain_custody_close_date(self):
        for rec in self:
            if rec.custody_close_date:
                if (fields.Datetime.from_string(rec.custody_close_date)).date() > date.today():
                    raise ValidationError('Closing Date can not be greater than today!')

    @api.onchange('custody_close_date')
    def _onchange_date(self):
        for rec in self:
            if rec.custody_close_date:
                if (fields.Datetime.from_string(rec.custody_close_date)).date() > date.today():
                    raise ValidationError('Closing Date can not be greater than today!')
                for line in rec.move_line_ids:
                    if line.date > rec.custody_close_date:
                        raise ValidationError('The closing date should be greater than or equal to opening')

    def _add_custody_journal(self, custody, amount, type=None, line=None, src_account=None, dest_account=None,
                             date=None):
        if line:
            type_value = str(' - ' + dict(line._fields['type'].selection).get(line.type)) or ' '
        else:
            type_value = ''

        company_currency = custody.company_id.currency_id
        diff_currency_p = custody.currency_id != company_currency
        move_lines = []
        journal_id = custody.journal_id.id

        move = self.env['account.move'].create({
            'journal_id': journal_id,
            'company_id': self.env.company.id,
            'date': line.date if line else fields.Date.today(),
            'ref': custody.description,
            'related_custody_line_id': line.id if line else False,
        })

        if type == 'direct_expense':
            # create journal items of line
            custody_name = "Custody" + type_value
            if custody.name:
                custody_name = custody.name.split('\n')[0][:64] + type_value
            move_line = {
                'name': custody_name,
                'price_unit': line.price_unit,
                'partner_id': False,
                'quantity': line.quantity,
                'price': amount,
                'account_id': line.account_id.id,
                'product_id': line.product_id.id if line.product_id else False,
                'uom_id': line.uom_id.id,
                'account_analytic_id': line.account_analytic_id.id,
                'date': line.date,
                'line_type': type,
                'transaction_description': line.name,
            }

            # if line['account_analytic_id']:
            #     move_line['analytic_line_ids'] = [(0, 0, line._get_analytic_line())]
            move_lines.append(move_line)
            # create one more move line, a counterline for the total on payable account
            total, total_currency, move_lines = custody._compute_expense_totals(company_currency,
                                                                                move_lines)
            custody_name = "Custody" + type_value
            if custody.name:
                custody_name = custody.name + type_value

            move_lines.append({
                'name': custody_name,
                'price': total,
                'partner_id': custody.employee_id.address_home_id.id,
                'account_id': self.env.company.custody_account_id.id,
                'date': line.date,
                'amount_currency': total_currency if diff_currency_p else total,
                'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                'ref': custody.employee_id.address_home_id.ref or False,
                'line_type': type
            })
        elif type == 'payment':
            # create journal items of line
            custody_name = "Custody" + type_value
            if custody.name:
                custody_name = custody.name.split('\n')[0][:64] + type_value
            move_line = {
                'name': custody_name,
                'price': amount,
                'account_id': line.partner_id.property_account_payable_id.id,
                'partner_id': line.partner_id.id,
                'date': line.date,
                'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                'ref': custody.name or False,
                'account_analytic_id': line.account_analytic_id.id,
                'line_type': type,
                'transaction_description': line.name,
            }
            move_lines.append(move_line)
            # create one more move line, a counterline for the total on payable account
            total, total_currency, move_lines = custody._compute_expense_totals(company_currency,
                                                                                move_lines)
            custody_name = "Custody" + type_value
            if custody.name:
                custody_name = custody.name + type_value
            move_lines.append({
                'name': custody_name,
                'price': total,
                'account_id': self.env.company.custody_account_id.id,
                'partner_id': custody.employee_id.address_home_id.id,
                'date': line.date,
                'amount_currency': total_currency if diff_currency_p else total,
                'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                'ref': custody.employee_id.address_home_id.ref or False,
                'line_type': type
            })
        elif type == 'payback':
            # create journal items of line
            custody_name = "Custody" + type_value
            if custody.name:
                custody_name = custody.name.split('\n')[0][:64] + type_value
            move_line = {
                'name': custody_name,
                'partner_id': False,
                'price': amount,
                'account_id': line.journal_id.default_account_id.id,
                'date': line.date,
                'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                'ref': custody.name or False,
                'account_analytic_id': line.account_analytic_id.id,
                'line_type': type,
                'transaction_description': line.name,
            }
            move_lines.append(move_line)
            # create one more move line, a counterline for the total on payable account
            total, total_currency, move_lines = custody._compute_expense_totals(company_currency,
                                                                                move_lines)
            custody_name = "Custody" + type_value
            if custody.name:
                custody_name = custody.name + type_value
            move_lines.append({
                'name': custody_name,
                'price': total,
                'account_id': self.env.company.custody_account_id.id,
                'partner_id': custody.employee_id.address_home_id.id,
                'date': line.date,
                'amount_currency': total_currency if diff_currency_p else total,
                'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                'ref': custody.employee_id.address_home_id.ref or False,
                'line_type': type
            })
        elif type == 'reimburse':
            custody_name = "Custody" + type_value
            if custody.name:
                custody_name = custody.name + type_value

            move_lines.append({
                'name': custody_name,
                'price': amount,
                'account_id': self.env.company.custody_account_id.id,
                'partner_id': custody.employee_id.address_home_id.id,
                'date': fields.Date.today(),
                'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                'ref': custody.name or False,
                'line_type': type,
                'transaction_description': line.name,
            })
            total, total_currency, move_lines = custody._compute_expense_totals(company_currency, move_lines)
            custody_name = "Custody" + type_value
            if custody.name:
                custody_name = custody.name + type_value

            move_lines.append({
                'name': custody_name,
                'price': total,
                'partner_id':False,
                'account_id': line.journal_id.default_account_id.id or custody.payment_method_id.default_account_id.id,
                'date': fields.Date.today(),
                'amount_currency': total_currency if diff_currency_p else total,
                'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                'ref': custody.payment_method_id.code or False,
                'line_type': type,
            })

        else:
            # create journal entry for the payment
            move = self.env['account.move'].create({
                'journal_id': custody.journal_id.id,
                'company_id': self.env.company.id,
                'date': fields.Date.today(),
                'description': custody.description,
                'related_custody_line_id': line.id if line else False,
            })
            custody_name = "Custody" + type_value
            if custody.name:
                custody_name = custody.name + type_value
            move_lines.append({
                'name': custody_name,
                'price': amount,
                'partner_id':False,
                'account_id': src_account,
                'date': date or fields.Date.today(),
                'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                'ref': custody.payment_method_id.code or False,
                'line_type': type
            })
            total, total_currency, move_lines = custody._compute_expense_totals(company_currency, move_lines)

            move_lines.append({
                'name': custody.name,
                'price': -amount,
                'partner_id': False,
                'account_id': dest_account,
                'date': date or fields.Date.today(),
                'amount_currency': total_currency if diff_currency_p else total,
                'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                'ref': custody.name or False,
                'line_type': type
            })

        # convert eml into an osv-valid format
        # lines = map(lambda x: (0, 0, custody._prepare_move_line(x)), move_lines)
        lines = [(0, 0, custody._prepare_move_line(move_line)) for move_line in move_lines]
        move.write({'line_ids': lines, 'custody_id': custody.id})
        print(move)
        print(f"move.custody_id: {move.custody_id}")
        # move.action_post()
        return True

    def button_journal_entry(self):
        for custody in self:
            if self.env.context.get('button_type') == 'entry' and not custody.line_ids:
                raise ValidationError('Please Add Transactions First!')
            if not custody.employee_id.address_home_id:
                raise ValidationError(_("No Home Address found for the employee %s, please configure one.") % (
                    custody.employee_id.name))
            if not custody.payment_method_id.default_account_id or not custody.payment_method_id.default_account_id:
                raise ValidationError(_("Please Configure Payment Method's Debit and Credit Accounts!"))
            if not custody.employee_id.company_id.custody_account_id.id or not custody.employee_id.company_id.custody_account_id.id:
                raise ValidationError(_("Please Configure Journal's Debit and Credit Accounts in Journal!"))

            custody_account = custody.employee_id.company_id.custody_account_id.id

            company_currency = custody.company_id.currency_id
            diff_currency_p = custody.currency_id != company_currency
            if self.env.context.get('button_type') == 'entry':
                account_payment_obj = self.env['account.payment']
                if custody.close_balance < 0:
                    raise ValidationError(
                        _('Total transaction lines amount must be less than or equal remaining amount.'))

                for line in custody.line_ids:
                    if not line.is_validated:
                        self._add_custody_journal(custody, line.price_subtotal, line.type, line)
                        line.is_validated = True

                # check if there is extra expense
                if custody.close_balance < 0:
                    raise ValidationError(_('Employee transactions must be equal to amount.'))

                if custody.close_balance == 0:
                    custody.write({'state': 'pay'})
            else:
                move_lines = []

                # create the move that will contain the accounting entries
                move = self.env['account.move'].create({
                    'journal_id': custody.journal_id.id,
                    'company_id': self.env.user.company_id.id,
                    'date': custody.custody_date or fields.Date.today(),
                    'ref': custody.description,
                })

                if self.env.context.get('button_type') == 'receive':
                    move_lines.append({
                        'name': custody.name,
                        'partner_id': custody.employee_id.address_home_id.id,
                        'price': custody.open_balance,
                        'account_id': custody.employee_id.company_id.custody_account_id.id,
                        'date': custody.custody_date or fields.Date.today(),
                        'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                        'ref': custody.name or False
                    })
                    total, total_currency, move_lines = custody._compute_expense_totals(company_currency, move_lines)

                    move_lines.append({
                        'name': custody.name,
                        'partner_id': False,
                        'price': total,
                        'account_id': custody.payment_method_id.default_account_id.id,
                        'date': custody.custody_date or fields.Date.today(),
                        'amount_currency': total_currency if diff_currency_p else total,
                        'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                        'ref': custody.payment_method_id.code or False
                    })
                    custody.write({'move_id': move.id, 'state': 'receiving_custody'})

                if self.env.context.get('button_type') == 'close':
                    for line in self.move_line_ids:
                        if self.custody_close_date:
                            if line.date > self.custody_close_date:
                                raise ValidationError('The closing date should be greater than or equale to opening')
                    if not self.custody_close_date:
                        raise ValidationError("Please set the closing date")
                    if custody.close_balance == 0.0:
                        custody.write({'state': 'done'})
                        return
                    else:
                        move_lines.append({
                            'type': 'src',
                            'name': custody.name,
                            'partner_id': False,
                            'price': custody.close_balance,
                            'account_id': custody.payment_method_id.default_account_id.id,
                            'date': custody.custody_close_date,
                            'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                            'ref': custody.payment_method_id.code or False
                        })
                        total, total_currency, move_lines = custody._compute_expense_totals(company_currency,
                                                                                            move_lines)
                        move_lines.append({
                            'name': custody.name,
                            'price': -custody.close_balance,
                            'partner_id': False,
                            'account_id': custody.employee_id.company_id.custody_account_id.id,
                            'date': custody.custody_close_date,
                            'amount_currency': total_currency if diff_currency_p else total,
                            'currency_id': custody.currency_id.id if diff_currency_p else company_currency.id,
                            'ref': custody.name or False
                        })
                        custody.write({'move_id': move.id, 'state': 'done'})

                # convert eml into an osv-valid format
                lines = [(0, 0, custody._prepare_move_line(move_line)) for move_line in move_lines]
                move.write({'line_ids': lines, 'custody_id': custody.id})
                # move.action_post()
        return True

    def button_cancel_entry(self):
        for rec in self:
            rec.write({'state': 'cancel'})
            moves = self.env['account.move'].search([('custody_id', '=', rec.id)])
            for move in moves:
                if move.state == 'posted':
                    move.button_draft()

    def button_reset_to_draft(self):
        for rec in self:
            rec.write({'state': 'draft'})
            moves = self.env['account.move'].search([('custody_id', '=', rec.id)])
            for move in moves:
                if move.state == 'posted':
                    move.button_draft()
