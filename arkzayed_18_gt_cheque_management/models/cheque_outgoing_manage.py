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

from odoo import fields, models ,api, _
from odoo.exceptions import UserError, ValidationError

class account_payment_method(models.Model):
    _inherit = "account.payment.method"
    
    payment_type = fields.Selection([('inbound', 'Inbound'), ('outbound', 'Outbound'), ('cheque', 'Cheque')], required=True)
    
       
class account_payment(models.Model):
    _inherit = "account.payment"
    
    @api.depends('cheque_out_attach_line')
    def _get_attach(self):
        self.attachment_count += len(self.cheque_out_attach_line.ids)
    
    attachment_count = fields.Integer(string='Attachment Count', compute='_get_attach', readonly=True)
    cheque_date = fields.Date(string='Cheque Date')
    cheque_receive_date = fields.Date(string='Cheque Receive Date')
    cheque_no = fields.Char(string='Cheque Number')
    state_new = fields.Selection([
    ('draft', 'Draft'),
    ('register', 'Registered'),
    ('bounce', 'Bounced'),
    ('return', 'Returned'),
    ('done', 'Done'),
    ('cancel', 'Cancel'),
    ], string='Status', default='draft')
    description = fields.Text('Description')
    cheque_out_attach_line = fields.One2many('cheque.outgoing.attach', 'cheque_out_id', string='Bank account')
    credit_account_id = fields.Many2one('account.account', string='Credit Account')
    debit_account_id = fields.Many2one('account.account', string='Debit Account')
    

    def action_cashed(self):
        return {
            'res_model': 'cheque.outgoing.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': self.env.ref('arkzayed_18_gt_cheque_management.cheque_outgoing_wizard_view').id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
    
    

    def action_submit(self):
        """ Create the journal items for the payment and update the payment's state to 'posted'.
            A journal entry is created containing an item in the source liquidity account (selected journal's default_debit or default_credit)
            and another in the destination reconcilable account (see _compute_destination_account_id).
            If invoice_ids is not empty, there will be one reconcilable move line per invoice to reconcile with.
            If the payment is a transfer, a second journal entry is created in the destination journal to receive money from the transfer account.
        """
        for rec in self:

            if rec.state != 'draft':
                raise UserError(_("Only a draft payment can be posted."))

            if any(inv.state != 'open' for inv in rec.invoice_ids):
                raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))

            # keep the name in case of a payment reset to draft
            if not rec.name:
                # Use the right sequence to set the name
                if rec.payment_type == 'transfer':
                    sequence_code = 'account.payment.transfer'
                else:
                    if rec.partner_type == 'customer':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.customer.invoice'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.customer.refund'
                    if rec.partner_type == 'supplier':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.supplier.refund'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.supplier.invoice'
                rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.payment_date).next_by_code(sequence_code)
                if not rec.name and rec.payment_type != 'transfer':
                    raise UserError(_("You have to define a sequence for %s in your company.") % (sequence_code,))

            # Create the journal entry
            amount = rec.amount * (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
            move = rec._create_payment_entry(amount)

            # In case of a transfer, the first journal entry created debited the source liquidity account and credited
            # the transfer account. Now we debit the transfer account and credit the destination liquidity account.
            if rec.payment_type == 'transfer':
                transfer_credit_aml = move.line_ids.filtered(lambda r: r.account_id == rec.company_id.transfer_account_id)
                transfer_debit_aml = rec._create_transfer_entry(amount)
                (transfer_credit_aml + transfer_debit_aml).reconcile()

            rec.write({'state': 'in_process', 'move_name': move.name})
        return True
    

    def button_journal_entries(self):
        return {
            'name': _('Journal Items'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move.line',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('payment_id', 'in', self.ids)],
        }

    

    def action_bounce(self):    
        return self.write({'state': 'bounce'})
    

    def action_draft(self):
        return self.write({'state': 'draft'})
    

    def action_return(self):
        return self.write({'state': 'return'})
    

    def action_deposit(self):
        return self.write({'state': 'deposit'})
    

    def action_transfer(self):
        return self.write({'state': 'transfer'})

    
class Chequeattach(models.Model):
    _name = "cheque.outgoing.attach"
    _description = 'Cheque Outgoing Attach'


    cheque_out_id = fields.Many2one('account.payment', string='Cheque Attach')
    name = fields.Char(string='Name')
    filename = fields.Binary(string='File Name')
    resource_model = fields.Char(string='Resouce Model')
    resource_field = fields.Char(string='Resource Field')
    resource_id = fields.Char(string='Resource ID')
    created_by = fields.Many2one('res.users', 'Created by')
    created_on = fields.Datetime('Created on')
