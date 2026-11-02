#
#    Globalteckz Pvt Ltd
#    Copyright (C) 2013-Today(www.globalteckz.com).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from num2words import num2words

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
import ast


class ChequeManage(models.Model):
    _name = "cheque.manage"
    _description = 'Cheque Manage'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'cheque_no'

    @api.model
    def default_get(self, deafult_fields):
        res = super(ChequeManage, self).default_get(deafult_fields)
        debit_account = False
        credit_account = False
        Parameters = self.env['ir.config_parameter'].sudo()
        if res.get('cheq_type') == 'incoming':
            debit_account = Parameters.get_param('arkzayed_18_gt_cheque_management.debit_inc_account')
        else:
            credit_account = Parameters.get_param('arkzayed_18_gt_cheque_management.credit_out_account')
        res.update({'debit_account': int(debit_account) if debit_account else None,
                    'credit_account': int(credit_account) if credit_account else None,
                    'bank_account': int(Parameters.get_param('arkzayed_18_gt_cheque_management.deposite_account')) if Parameters.get_param(
                        'arkzayed_18_gt_cheque_management.deposite_account') else None,
                    'journal_id': int(Parameters.get_param('arkzayed_18_gt_cheque_management.journal_id'))}) if Parameters.get_param(
            'arkzayed_18_gt_cheque_management.journal_id') else None
        return res

    @api.depends('cheq_attachment_ids')
    def _get_attach(self):
        Attachment = self.env['ir.attachment']
        for attachment in self:
            attachment.attachment_count = Attachment.search_count([('cheque_id', '=', attachment.id)])

    @api.depends('move_line_ids')
    def _journal_item_count(self):
        for item in self:
            item.journal_item_count = len(item.move_line_ids)

    def _get_debit_account(self):
        account = self.env['account.account'].search([('is_under_collection', '=', True)])
        return account.id if account else None

    seq_no = fields.Char(string='Sequence', copy=False)
    name = fields.Char(string='Name')
    attachment_count = fields.Integer(string='Attachment Count', compute='_get_attach', readonly=True, copy=False)
    journal_item_count = fields.Integer(string='Journal Items', compute='_journal_item_count', readonly=True,
                                        copy=False)
    payer = fields.Many2one('res.partner', 'Partner')
    bank_account = fields.Many2one('account.account', string='Bank account')
    bank_id = fields.Many2one('res.bank')
    debit_account = fields.Many2one('account.account', string='Debit account', default=_get_debit_account)
    hermes_account = fields.Many2one('account.account', string='Hermes account')
    credit_account = fields.Many2one('account.account', string='Credit account', required=True)
    debit = fields.Monetary(default=0.0, currency_field='company_currency_id')
    credit = fields.Monetary(default=0.0, currency_field='company_currency_id')
    journal_id = fields.Many2one('account.journal', string='Journal', required=True,
                                 states={'confirm': [('readonly', True)]})
    cheque_date = fields.Date(string='Cheque Date', default=fields.Date.context_today)
    cashed_date = fields.Date(string='Cashed Date', copy=False)
    return_date = fields.Date(string='Returned Date', copy=False)
    cheque_receive_date = fields.Date(string='Cheque Given/Receive Date')
    cheque_no = fields.Char(string='Cheque Number', copy=False)
    amount = fields.Float(string='Amount')
    bounced = fields.Boolean(string='Bounced')
    partner_id = fields.Many2one('res.partner', 'Company')
    cheq_type = fields.Selection([('incoming', 'Incoming'), ('outgoing', 'Outgoing')])
    cheq_attachment_ids = fields.One2many('ir.attachment', 'cheque_id', 'Attachment Line', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('collect', 'Received'),
        ('return_to_client','Returned From Bank'),
        ('to_hermes','To Hermes'),
        ('to_adib','To Adib'),
        ('register', 'Under Collection'),
        ('sent', 'Sent'),
        ('under_collection', 'Under Collection'),
        ('deposit', 'Deposited'),
        ('done', 'Collected'),
        ('transfer', 'Transferred'),
        ('bounce', 'Bounced'),
        ('return', 'Returned'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft')
    outgoing_state = fields.Selection([
        ('draft', 'Draft'),
        ('hand_in', 'Handed In'),
        ('return_to_client', 'Returned From Bank'),
        ('register', 'Received'),
        ('sent', 'Sent'),
        ('under_collection', 'Clear'),
        ('to_adib', 'To Adib'),
        ('deposit', 'Deposited'),
        ('done', 'Done'),
        ('transfer', 'Transfered'),
        ('bounce', 'Bounced'),
        ('return', 'Returned'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft')
    project_id = fields.Many2one('project.project', string='Project')
    is_merged = fields.Boolean(string='Is Merged', default=False, help="This Cheque is Merged into another Cheque")
    merged_into_id = fields.Many2one('cheque.manage', string='Merged Into', copy=False)
    is_consolidated = fields.Boolean(string='Is Consolidated', default=False,help="This Cheque is Consolidated from other Cheques")
    cheque_scan = fields.Binary()
    cheque_portfolio_ids = fields.Many2many('cheque.portfolio', 'cheque_portfolio_cheque_manage_rel','cheque_manage_id', 'cheque_portfolio_id')
    envelope_number = fields.Integer("Envelope Number", help="This is the number of the Envelope containing the Cheque")
    archive_place = fields.Char("Archive Location", help="This is the archive place location")
    cycle_type = fields.Selection([('main', 'Main'), ('hermes', 'Hermes'), ('adib', 'Adib')], default='main')

    @api.constrains('state')
    def set_outgoing_state(self):
        for rec in self:
            if rec.cheq_type == 'outgoing':
                if rec.state == 'collect':
                    rec.outgoing_state = 'hand_in'
                else:
                    rec.outgoing_state = rec.state

    description = fields.Text('Description')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency",
                                          readonly=True,
                                          store=True)
    move_id = fields.Many2one('account.move', string='Invoice', copy=False)
    move_line_ids = fields.One2many('account.move.line', 'cheque_id', readonly=True, copy=False, ondelete='restrict')
    is_owner = fields.Boolean()
    under_collection_account_id = fields.Many2one('account.account')
    equity_account_id = fields.Many2one('account.account',domain=[('is_owner', '=', True)])
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user)

    return_reason_id = fields.Many2one('return.reason', string='Return Reason', copy=False)
    amount_in_words = fields.Char(compute="_compute_amount_in_words")
    memo = fields.Char()
    _sql_constraints = [
        ('cheque_no_company_uniq', 'unique (cheque_no,bank_id)', 'Cheque number must be unique per bank.'
)
    ]

    @api.depends('amount')
    def _compute_amount_in_words(self):
        for payment in self:
            if payment.amount:
                amount_in_words = num2words(payment.amount, lang='ar', to='currency',
                                                 currency='EGP')
                payment.amount_in_words = amount_in_words + ' فقط '
            else:
                payment.amount_in_words = False

    def submit_under_collection_action(self):
        self.ensure_one()
        if not self.cheque_scan and not self.sale_proposal_id.is_old_contract:
            raise ValidationError(_("Cannot proceed to 'Under Collection'.\n"
                                    "A Cheque Scan must be uploaded before continuing.\n"
                                    "Please attach the scanned copy of the cheque and try again."))
        return {
            'name': _('Under Collection'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'under.collection.wizard',
            'view_mode': 'form',
            'context': {
                'action_submit_under_collection': True,
                'default_date': self.cheque_receive_date or fields.Date.today(),
            }
        }

    @api.onchange('cheq_type')
    def onchange_cheq_type(self):
        domain = {}
        if self.cheq_type:
            if self.cheq_type == 'incoming':
                domain['payer'] = [('customer_rank', '>=', 1)]
            else:
                domain['payer'] = [('supplier_rank', '>=', 1)]
        return {'domain': domain}

    @api.model
    def create(self, vals):
        if vals.get('cheq_type') == 'incoming':
            vals['seq_no'] = self.env['ir.sequence'].next_by_code('cheque.manage.incoming') or '/'
        else:
            vals['seq_no'] = self.env['ir.sequence'].next_by_code('cheque.manage.outgoing') or '/'
        res = super(ChequeManage, self).create(vals)
        if res.cheque_scan:
            res.message_post(body=_('Cheque Scan has been uploaded.'))

        return res

    def write(self, vals):
        res = super().write(vals)
        if 'cheque_scan' in vals:
            for rec in self:
                rec.message_post(body=_('Cheque Scan has been uploaded.'))
        return res

    def action_cashed(self):
        return {
            'res_model': 'cheque.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('arkzayed_18_gt_cheque_management.cheque_wizard_view').id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def action_transfer(self):
        return {
            'res_model': 'cheque.transfer.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('arkzayed_18_gt_cheque_management.cheque_transfer_wizard_view').id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def abc(self):
        acc_pay = self.env['account.payment'].search([('move_line_ids', '=', self.ids)])
        for rec in acc_pay:
            if any(inv.state != 'open' for inv in rec.invoice_ids):
                raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))

            # Use the right sequence to set the name
            if rec.payment_type == 'transfer':
                sequence_code = 'account.payment.transfer'
            else:
                if rec.partner_type == 'customer_rank':
                    if rec.payment_type == 'inbound':
                        sequence_code = 'account.payment.customer.invoice'
                    if rec.payment_type == 'outbound':
                        sequence_code = 'account.payment.customer.refund'
                if rec.partner_type == 'supplier_rank':
                    if rec.payment_type == 'inbound':
                        sequence_code = 'account.payment.supplier.refund'
                    if rec.payment_type == 'outbound':
                        sequence_code = 'account.payment.supplier.invoice'
            rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.payment_date).next_by_code(
                sequence_code)
            if not rec.name and rec.payment_type != 'transfer':
                raise UserError(_("You have to define a sequence for %s in your company.") % (sequence_code,))

            # Create the journal entry
            amount = rec.amount * (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
            move = rec._create_payment_entry(amount)

            # In case of a transfer, the first journal entry created debited the source liquidity account and credited
            # the transfer account. Now we debit the transfer account and credit the destination liquidity account.
            if rec.payment_type == 'transfer':
                transfer_credit_aml = move.line_ids.filtered(
                    lambda r: r.account_id == rec.company_id.transfer_account_id)
                transfer_debit_aml = rec._create_transfer_entry(amount)
                (transfer_credit_aml + transfer_debit_aml).reconcile()

            rec.write({'state': 'posted', 'move_name': move.name})

    def _get_equity_account(self):
        if self.is_owner:
            return self.equity_account_id
        else:
            if self.cheq_type == 'incoming':
                return self.payer.property_account_receivable_id
            else:
                return self.payer.property_account_payable_id

    def cheque_collect(self):
        Move = self.env['account.move']
        if not self.company_id.received_checks:
            raise UserError(_("journal and company received checks cannot be empty for cheque with sequence %s ") % (self.seq_no))
        if self.cheq_type == 'incoming':
            if not self.payer.property_account_down_payment_receivable_id:
                raise ValidationError("Please Set Partner Account Down Payment Receivable for cheque with sequence %s " % (self.seq_no))
            credit_line = {
                'account_id': self.payer.property_account_down_payment_receivable_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.company_id.received_checks.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            self.write({'state': 'collect'})
        else:
            if not self.payer.property_account_down_payment_payable_id:
                raise ValidationError("Please Set Partner Account Down Payment Payable")
            credit_line= {
                'account_id': self.credit_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.payer.property_account_down_payment_payable_id.id if not self.is_owner else self.equity_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            self.write({'state': 'collect'})
        move_vals = {
            'date':self.cheque_receive_date or fields.Date.today(),
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_id = Move.create(move_vals)
        self.move_id = move_id.id
        move_id.action_post()

    def action_submit(self, date=None):
        Move = self.env['account.move']
        if not self.company_id.received_checks:
            raise UserError(_("journal and company received checks cannot be empty"))
        # if not self.journal_id.under_collection:
        #     raise UserError(_("journal under collection cannot be empty"))
        if self.cheq_type == 'incoming':
            if self.state=='return_to_client':
                credit_line = {
                    'account_id': self.debit_account.id,
                    'partner_id': self.payer.id,
                    'name': self.name,
                    'debit': self.amount,
                    'credit': 0,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }
                debit_line = {
                    'account_id': self.company_id.received_checks.id,
                    'partner_id': self.payer.id,
                    'name': self.name,
                    'debit': 0,
                    'credit': self.amount,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }
            else:
                credit_line = {
                    'account_id': self.company_id.received_checks.id,
                    'partner_id': self.payer.id,
                    'name': self.name,
                    'debit': 0,
                    'credit': self.amount,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }
                debit_line = {
                    'account_id': self.debit_account.id,
                    'partner_id': self.payer.id,
                    'name': self.name,
                    'debit': self.amount,
                    'credit': 0,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }

            self.write({'state': 'register'})
        else:
            if self.state=='return_to_client':
                credit_line = {
                    'account_id': self.company_id.outgoing_checks.id,
                    'partner_id': self.payer.id,
                    'name': self.name,
                    'debit': self.amount,
                    'credit': 0,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }
                debit_line = {
                    'account_id': self.credit_account.id,
                    'partner_id': self.payer.id,
                    'name': self.name,
                    'debit': 0,
                    'credit': self.amount,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }
            else:
                credit_line = {
                    'account_id': self.credit_account.id,
                    'partner_id': self.payer.id,
                    'name': self.name,
                    'debit': 0,
                    'credit': self.amount,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }
                debit_line = {
                    'account_id': self.company_id.outgoing_checks.id,
                    'partner_id': self.payer.id,
                    'name': self.name,
                    'debit': self.amount,
                    'credit': 0,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }


            self.write({'state': 'register'})
        move_date = date or self.cheque_receive_date or fields.Date.today()
        move_vals = {
            'date':move_date,
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_id = Move.create(move_vals)
        move_id.action_post()

    def under_collection_action(self):
        if self.cheq_type == 'incoming':
            return {
                'name': _('Under Collection'),
                'type': 'ir.actions.act_window',
                'target': 'new',
                'res_model': 'under.collection.wizard',
                'view_mode': 'form',
                'context': {
                    'action_under_collection': True,
                    'default_journal_id': self.bank_id.journal_id.id if self.bank_id.journal_id and self.cheq_type == 'outgoing' else False,
                }
            }
        else:
            return {
                'name': _('Cheque Payment'),
                'type': 'ir.actions.act_window',
                'target': 'new',
                'res_model': 'under.collection.wizard',
                'view_mode': 'form',
                'context': {
                    'action_under_collection': True,
                    'default_journal_id': self.bank_id.journal_id.id if self.bank_id.journal_id and self.cheq_type == 'outgoing' else False,
                }
            }

    def under_collection(self, journal_id=None, date=None):
        Move = self.env['account.move']
        if self.cheq_type == 'incoming':
            if self.state == 'to_adib':
                if not self.company_id.adib_account:
                    raise ValidationError(_("Please set Adib account into company setting"))
                source_account = self.company_id.adib_account
            else:
                source_account = self.debit_account
            credit_line = {
                'account_id': source_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': journal_id.default_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        else:
            credit_line = {
                'account_id': journal_id.default_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.credit_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        move_vals = {
            'date': date,
            'journal_id': self.journal_id.id,
            'partner_id': self.payer.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_id = Move.create(move_vals)
        move_id.action_post()
        return self.write({'state': 'done', 'under_collection_account_id': journal_id.default_account_id})

    def action_cancel(self):
        if not self.move_line_ids:
            raise UserError(_("You cannot cancel a record that is not posted yet!"))
        for rec in self:
            for move in rec.move_line_ids.mapped('move_id'):
                move.button_cancel()
                # move.unlink()
            return rec.write({'state': 'cancel'})

    # It will make reverse entry for the registerd entries
    def action_collect(self):
        return {
            'name': _('Collect Action'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'under.collection.wizard',
            'view_mode': 'form',
            'context': {
                'action_collect': True,
                'name': self.name
            }
        }

    def action_bounce(self, journal_id=None, date=None):
        Move = self.env['account.move']
        Mov_two = self.env['account.move']
        if self.cheq_type == 'incoming':
            credit_line = {
                'account_id': self.under_collection_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': journal_id.default_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            credit_line_1 = {
                'account_id': self.payer.property_account_receivable_id.id if not self.is_owner else self.equity_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line_1 = {
                'account_id': self.company_id.received_checks.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        else:
            credit_line = {
                'account_id': journal_id.default_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.credit_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            credit_line_1 = {
                'account_id': self.company_id.outgoing_checks.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line_1 = {
                'account_id': self.payer.property_account_payable_id.id if not self.is_owner else self.equity_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }

        move_vals = {
            'date': date,
            'journal_id': self.journal_id.id,
            'partner_id': self.payer.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_vals_two = {
            'date': date,
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line_1), (0, 0, debit_line_1)]
        }
        move_id = Move.create(move_vals)
        move_id_two = Mov_two.create(move_vals_two)
        move_id.action_post()
        move_id_two.action_post()
        return self.write({'state': 'bounce', 'bounced': True})

    def action_draft(self):
        return self.write({'state': 'draft'})


    def action_return_wizard(self):
        return {
            'name': _('Return'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'under.collection.wizard',
            'view_mode': 'form',
            'context': {
                'action_return': True,
                'default_date': fields.Date.today(),
            }
        }

    def action_return(self, date=None):
        state = 'return' if self.state == 'collect' else 'return_to_client'

        if self.bounced:
            for rec in self:
                for move in rec.move_line_ids.mapped('move_id'):
                    move.button_cancel()
                    # move.unlink()
                return rec.write({'state': state, 'return_date': fields.Date.today()})
        else:
            Move = self.env['account.move']
            if self.state == 'collect':
                if self.cheq_type == 'incoming':
                    credit_line = {
                        # self.debit_account.id
                        'account_id': self.company_id.received_checks.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line = {
                        'account_id': self.payer.property_account_down_payment_receivable_id.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                else:
                    credit_line = {
                        'account_id': self.payer.property_account_down_payment_payable_id.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line = {
                        'account_id': self.credit_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                move_vals = {
                    'date': date or fields.Date.today(),
                    'journal_id': self.journal_id.id,
                    'ref': self.seq_no,
                    'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
                }
                move_id = Move.create(move_vals)
                move_id.action_post()
            elif self.state=='register':
                if not self.company_id.return_account:
                    raise ValidationError(_("Please set the Return Account in company settings"))
                if self.cheq_type == 'incoming':
                    credit_line1 = {
                        'account_id': self.debit_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line1 = {
                        'account_id': self.company_id.return_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                else:
                    credit_line1 = {
                        'account_id': self.company_id.return_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line1 = {
                        'account_id': self.credit_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                move_vals1 = {
                    'date': date or fields.Date.today(),
                    'journal_id': self.journal_id.id,
                    'ref': self.seq_no,
                    'line_ids': [(0, 0, credit_line1), (0, 0, debit_line1)]
                }
                move_id1 = Move.create(move_vals1)
                move_id1.action_post()

            return self.write({'state': state, 'return_date': fields.Date.today()})

    def action_return_to_hermes(self):
        if not self.company_id.hermes_account:
            raise ValidationError(_("Please set hermes account into company setting"))
        Move = self.env['account.move']
        received_checks = self.company_id.received_checks
        hermes_account = self.company_id.hermes_account
        credit_line = {
            'account_id': hermes_account.id,
            'partner_id': self.payer.id,
            'name': self.name,
            'debit': 0,
            'credit': self.amount,
            'date_maturity': self.cheque_date,
            'cheque_id': self.id,
        }
        debit_line = {
            'account_id': received_checks.id,
            'partner_id': self.payer.id,
            'name': self.name,
            'debit': self.amount,
            'credit': 0,
            'date_maturity': self.cheque_date,
            'cheque_id': self.id,
        }
        move_vals = {
            'date': fields.Date.today(),
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_id = Move.create(move_vals)
        move_id.action_post()
        return self.write({'state': 'collect', 'return_date': fields.Date.today()})

    def action_return_to_adib(self, date=None):
        if not self.company_id.adib_account:
            raise ValidationError(_("Please set Adib account into company setting"))
        Move = self.env['account.move']
        received_checks = self.company_id.received_checks
        adib_account = self.company_id.adib_account
        credit_line = {
            'account_id': adib_account.id,
            'partner_id': self.payer.id,
            'name': self.name,
            'debit': 0,
            'credit': self.amount,
            'date_maturity': self.cheque_date,
            'cheque_id': self.id,
        }
        debit_line = {
            'account_id': received_checks.id,
            'partner_id': self.payer.id,
            'name': self.name,
            'debit': self.amount,
            'credit': 0,
            'date_maturity': self.cheque_date,
            'cheque_id': self.id,
        }
        move_vals = {
            'date': date or fields.Date.today(),
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_id = Move.create(move_vals)
        move_id.action_post()
        return self.write({'state': 'collect', 'return_date': date or fields.Date.today()})

    def action_return_to_client(self):
        if self.bounced:
            for rec in self:
                for move in rec.move_line_ids.mapped('move_id'):
                    move.button_cancel()
                    # move.unlink()
                return rec.write({'state': 'return', 'return_date': fields.Date.today()})
        else:
            Move = self.env['account.move']
            if self.state=='return_to_client':
                if self.cheq_type == 'incoming':
                    credit_line = {
                        # self.debit_account.id
                        'account_id': self.company_id.received_checks.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line = {
                        'account_id': self.payer.property_account_down_payment_receivable_id.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                else:
                    credit_line = {
                        'account_id': self.payer.property_account_payable_id.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line = {
                        'account_id': self.company_id.outgoing_checks.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                move_vals = {
                    'date': fields.Date.today(),
                    'journal_id': self.journal_id.id,
                    'ref': self.seq_no,
                    'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
                }
                move_id = Move.create(move_vals)
                move_id.action_post()
            return self.write({'state': 'return', 'return_date': fields.Date.today()})


    def action_deposit(self):
        Move = self.env['account.move']
        if self.cheq_type == 'incoming':
            credit_line = {
                'account_id': self.debit_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.bank_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        else:
            credit_line = {
                'account_id': self.bank_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.credit_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        move_vals = {
            'date': fields.Date.today(),
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_id = Move.create(move_vals)
        move_id.action_post()
        return self.write({'state': 'deposit'})

    def unlink(self):
        if any(bool(rec.move_line_ids) for rec in self):
            raise UserError(_("You cannot delete a record that is already posted!"))
        return super(ChequeManage, self).unlink()

    def open_payment_matching_screen(self):
        self.ensure_one()
        # Open reconciliation view for this account
        action_values = self.env['ir.actions.act_window']._for_xml_id(
            'account_accountant.action_move_line_posted_unreconciled')
        domain = ast.literal_eval(action_values['domain'])
        domain.append(('partner_id', '=', self.payer.id))
        if self.cheq_type == 'incoming':
            domain.append(('account_id', '=', self.payer.property_account_receivable_id.id))
        else:
            domain.append(('account_id', '=', self.payer.property_account_payable_id.id))

        action_values['domain'] = domain
        return action_values

    def button_journal_entries(self):
        return {
            'name': _('Journal Items'),
            'view_mode': 'list,form',
            'res_model': 'account.move.line',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('cheque_id', 'in', self.ids)],
        }

    def to_hermes_action(self):
        self.ensure_one()
        return {
            'name': _('To Hermes'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'under.collection.wizard',
            'view_mode': 'form',
            'context': {
                'action_to_hermes': True,
                'default_date': fields.Date.today(),
            }
        }

    def to_adib_action(self):
        self.ensure_one()
        return {
            'name': _('To Adib'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'under.collection.wizard',
            'view_mode': 'form',
            'context': {
                'action_to_adib': True,
                'default_date': fields.Date.today(),
            }
        }

    def return_adib_action(self):
        self.ensure_one()
        return {
            'name': _('Return From Adib'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'under.collection.wizard',
            'view_mode': 'form',
            'context': {
                'action_return_adib': True,
                'default_date': fields.Date.today(),
            }
        }

    def to_hermes(self, date=None):
        if self.cycle_type == 'hermes' and self.amount > 0:
            if not self.company_id.hermes_account:
                raise ValidationError("Please set hermes account into company setting")
            received_checks = self.company_id.received_checks
            hermes_account = self.company_id.hermes_account
            Move = self.env['account.move']

            amount = self.amount
            credit_line = {
                'account_id': received_checks.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': hermes_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            move_vals = {
                'date': date or fields.Date.today(),
                'journal_id': self.journal_id.id,
                'ref': self.seq_no,
                'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
            }
            move_id = Move.create(move_vals)
            move_id.action_post()
            return self.write({'state': 'to_hermes'})

    def to_adib(self, date=None):
        if self.cycle_type == 'adib' and self.amount > 0:
            if not self.company_id.adib_account:
                raise ValidationError("Please set Adib account into company setting")
            received_checks = self.company_id.received_checks
            adib_account = self.company_id.adib_account
            Move = self.env['account.move']

            amount = self.amount
            credit_line = {
                'account_id': received_checks.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': adib_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            move_vals = {
                'date': date or fields.Date.today(),
                'journal_id': self.journal_id.id,
                'ref': self.seq_no,
                'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
            }
            move_id = Move.create(move_vals)
            move_id.action_post()
            return self.write({'state': 'to_adib'})


    def _get_arabic_amount(self, amount, lang):
        return num2words(float(amount), lang=lang)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    cheque_id = fields.Many2one('cheque.manage', 'Cheque Id')


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    cheque_id = fields.Many2one('cheque.manage', 'Cheque Id')
