from odoo import models, fields, api, _

from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class EoiPayment(models.Model):
    _name = 'eoi.payment'
    _description = 'EOI Partial Payment Line'

    def _compute_default_line_amount(self):
        eoi_id = self.env.context.get('default_eoi_id')
        if eoi_id:
            eoi = self.env['eoi.eoi'].browse(eoi_id)
            if eoi.exists() and eoi.reservation_amount:
                return eoi.reservation_amount
        return 0

    amount = fields.Float(default=lambda self: self._compute_default_line_amount())
    remaining_amount = fields.Float()
    payment_attachment = fields.Binary()
    is_payed = fields.Boolean(string='Paid', compute='_compute_is_paid', store=True)
    eoi_id = fields.Many2one('eoi.eoi', string="EOI")
    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('bank_cheque', 'Bank check'),
        ('cash', 'Cash')
    ], string='Payment Method')
    payment_ids = fields.One2many('account.payment', 'eoi_payment_id', string='Payments')
    cheque_ids = fields.One2many('cheque.manage', 'eoi_payment_id', string='Cheques')
    is_payment_created = fields.Boolean()

    @api.depends('payment_ids.state', 'payment_ids.amount', 'cheque_ids.state', 'cheque_ids.amount')
    def _compute_is_paid(self):
        for rec in self:
            cheque_amount = sum(rec.cheque_ids.filtered(
                lambda c: c.cheq_type == 'incoming' and c.state not in ('draft', 'return_to_client', 'return',
                                                                         'cancel')
            ).mapped('amount'))
            payment_amount = sum(rec.payment_ids.filtered(
                lambda p: p.payment_type == 'inbound' and p.state not in ('draft', 'canceled')
            ).mapped('amount'))
            total_paid = cheque_amount + payment_amount
            rec.is_payed = float_compare(total_paid, rec.amount, precision_digits=2) >= 0

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record.remaining_amount = record.eoi_id.reservation_amount
        return records

    def create_payment(self):
        """Create payment for bank transfer or cash"""
        self.ensure_one()
        if not self.payment_attachment and self.payment_method == 'bank_transfer':
            raise ValidationError(_("Please upload the Payment Attachment before creating a payment."))
        if self.payment_method in ['bank_transfer', 'cash']:
            journal_type = 'bank' if self.payment_method == 'bank_transfer' else 'cash'
            journal = self.env['account.journal'].search([('type', '=', journal_type)], limit=1)

            if not journal:
                raise ValidationError(_("No %s journal found. Please create one first.") % journal_type)

            amount = self.amount
            memo = f'EOI Payment - {self.eoi_id.name}'

            if float_compare(amount, 0.0, precision_digits=2) <= 0:
                raise ValidationError(_("Payment amount must be greater than zero."))

            total_payments = sum(self.eoi_id.account_payment_ids.filtered(
                lambda p: p.payment_type == 'inbound' and p.state != 'canceled'
            ).mapped('amount'))
            total_cheques = sum(self.eoi_id.cheque_manage_ids.filtered(
                lambda c: c.state not in ['return_to_client', 'return', 'cancel']
            ).mapped('amount'))
            total_paid = total_payments + total_cheques + self.amount
            if float_compare(total_paid, self.eoi_id.reservation_amount, precision_digits=2) > 0:
                raise ValidationError(_("The amount will be greater than the EOI Amount."))

            payment = self.env['account.payment'].create({
                'partner_id': self.eoi_id.customer_id.id,
                'payment_type': 'inbound',
                'amount': amount,
                'eoi_id': self.eoi_id.id,
                'eoi_payment_id': self.id,
                'currency_id': self.eoi_id.currency_id.id,
                'memo': memo,
                'payment_method_type': journal_type,
                'journal_id': journal.id,
                'is_down_payment': True,
                'from_eoi': True,
            })
            self.is_payment_created = True

            return {
                'name': _('Payment'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'account.payment',
                'res_id': payment.id,
                'type': 'ir.actions.act_window',
                'target': 'current',
            }
        return True

    def create_cheque(self):
        """Create cheque payment"""
        self.ensure_one()
        if not self.payment_attachment:
            raise ValidationError(_("Please upload the Payment Attachment before creating a cheque payment."))
        journal = self.env['account.journal'].search([], limit=1)

        if not journal:
            raise ValidationError(_("No journal found. Please create one first."))

        amount = self.amount

        if float_compare(amount, 0.0, precision_digits=2) <= 0:
            raise ValidationError(_("Payment amount must be greater than zero."))

        total_payments = sum(self.eoi_id.account_payment_ids.filtered(
            lambda p: p.payment_type == 'inbound' and p.state != 'canceled'
        ).mapped('amount'))
        total_cheques = sum(self.eoi_id.cheque_manage_ids.filtered(
            lambda c: c.state not in ['return_to_client', 'return', 'cancel']
        ).mapped('amount'))
        total_paid = total_payments + total_cheques + self.amount
        if float_compare(total_paid, self.eoi_id.reservation_amount, precision_digits=2) > 0:
            raise ValidationError(_("The amount will be greater than the EOI Amount."))

        cheque_payment_id = self.env['cheque.manage'].create({
            'payer': self.eoi_id.customer_id.id,
            'amount': amount,
            'eoi_id': self.eoi_id.id,
            'eoi_payment_id': self.id,
            'journal_id': journal.id,
            'cheq_type': 'incoming',
            'from_eoi': True,
        })
        self.is_payment_created = True

        return {
            'name': _('Cheque Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'cheque.manage',
            'res_id': cheque_payment_id.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }
