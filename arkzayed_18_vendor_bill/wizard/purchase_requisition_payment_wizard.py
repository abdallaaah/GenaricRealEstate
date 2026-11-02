# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRequisitionPaymentWizard(models.TransientModel):
    _name = 'purchase.requisition.payment.wizard'
    _description = 'Purchase Requisition Down Payment Wizard'

    requisition_id = fields.Many2one(
        'purchase.requisition',
        string='Purchase Requisition',
        required=True,
        readonly=True
    )
    payment_type = fields.Selection([
        ('payment', 'Payment'),
        ('cheque', 'Cheque')
    ], string='Payment Type', required=True, default='payment')

    # Common fields
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.context_today
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        domain="[('type', 'in', ['bank', 'cash'])]"
    )
    memo = fields.Char(string='Memo')

    # Payment specific fields
    payment_method_line_id = fields.Many2one(
        'account.payment.method.line',
        string='Payment Method',
        domain="[('journal_id', '=', journal_id), ('payment_type', '=', 'outbound')]"
    )

    # Cheque specific fields
    cheque_no = fields.Char(string='Cheque Number')
    cheque_date = fields.Date(string='Cheque Date', default=fields.Date.context_today)
    bank_id = fields.Many2one('res.bank', string='Bank')
    debit_account = fields.Many2one(
        'account.account',
        string='Debit Account',
        domain="[('account_type', 'not in', ['asset_receivable', 'liability_payable'])]"
    )
    credit_account = fields.Many2one(
        'account.account',
        string='Credit Account',
        domain="[('account_type', 'not in', ['asset_receivable', 'liability_payable'])]"
    )

    @api.onchange('requisition_id')
    def _onchange_requisition_id(self):
        if self.requisition_id:
            self.partner_id = self.requisition_id.vendor_id
            self.amount = self.requisition_id.down_payment_agreement
            self.currency_id = self.requisition_id.currency_id

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        """Set default accounts based on payment type"""
        if self.payment_type == 'cheque':
            Parameters = self.env['ir.config_parameter'].sudo()
            credit_account = Parameters.get_param(
                'arkzayed_18_gt_cheque_management.credit_out_account'
            )
            if credit_account:
                self.credit_account = int(credit_account)

    @api.constrains('amount')
    def _check_amount(self):
        for wizard in self:
            if wizard.amount <= 0:
                raise ValidationError(_('Amount must be greater than zero.'))

    def action_create_payment(self):
        """Create payment for down payment"""
        self.ensure_one()

        if self.payment_type != 'payment':
            return

        payment_vals = {
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner_id.id,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'date': self.payment_date,
            'journal_id': self.journal_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
            'memo': _('Down payment for %s') % self.requisition_id.name,
            'requisition_id': self.requisition_id.id,
        }

        if self.memo:
            payment_vals['memo'] = self.memo

        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()

        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'res_id': payment.id,
            'target': 'current',
        }

    def action_create_cheque(self):
        """Create cheque for down payment"""
        self.ensure_one()

        if self.payment_type != 'cheque':
            return

        if not self.cheque_no:
            raise UserError(_('Please enter a cheque number.'))

        if not self.credit_account:
            raise UserError(_('Please select a credit account for the cheque.'))

        cheque_vals = {
            'name': self.memo or _('Down payment for %s') % self.requisition_id.name,
            'payer': self.partner_id.id,
            'cheque_no': self.cheque_no,
            'amount': self.amount,
            'cheque_date': self.cheque_date,
            'cheque_receive_date': self.payment_date,
            'journal_id': self.journal_id.id,
            'cheq_type': 'outgoing',
            'credit_account': self.credit_account.id,
            'requisition_id': self.requisition_id.id,
        }

        if self.bank_id:
            cheque_vals['bank_id'] = self.bank_id.id

        if self.debit_account:
            cheque_vals['debit_account'] = self.debit_account.id

        cheque = self.env['cheque.manage'].create(cheque_vals)

        return {
            'name': _('Cheque'),
            'type': 'ir.actions.act_window',
            'res_model': 'cheque.manage',
            'view_mode': 'form',
            'res_id': cheque.id,
            'target': 'current',
        }

    def action_confirm(self):
        """Main action to create payment or cheque based on selection"""
        self.ensure_one()

        if self.payment_type == 'payment':
            return self.action_create_payment()
        elif self.payment_type == 'cheque':
            return self.action_create_cheque()
