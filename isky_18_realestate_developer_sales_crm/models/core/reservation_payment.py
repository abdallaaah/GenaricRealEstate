from odoo import models, fields, api, _

from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class ReservationPayment(models.Model):
    _name = 'reservation.payment'

    def _compute_default_line_amount(self):
        reservation_id = self.env.context.get('default_sale_reservation_id')
        if reservation_id:
            reservation = self.env['real.estate.sale.reservation'].browse(reservation_id)
            if reservation.exists() and reservation.complete_reservation_amount:
                return reservation.complete_reservation_amount
        return 0

    amount = fields.Float(default=lambda self: self._compute_default_line_amount())
    remaining_amount = fields.Float()
    payment_attachment = fields.Binary()
    is_payed = fields.Boolean(string='Paid', compute='_compute_is_paid', store=True)
    sale_reservation_id = fields.Many2one('real.estate.sale.reservation', string="Reservation Payments")
    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('bank_cheque', 'Bank check'),
        ('cash', 'Cash')
    ], string='Payment Method')
    payment_ids = fields.One2many('account.payment', 'reservation_payment_id', string='Payments')
    cheque_ids = fields.One2many('cheque.manage', 'reservation_payment_id', string='Cheques')
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
        record = super().create(vals_list)
        if record and len(record) > 1:
            raise ValidationError(_("Please only add one Payment record at a time."))

        record.remaining_amount = record.sale_reservation_id.complete_reservation_amount

        return record

    def create_payment(self):
        """Create payment for bank transfer or cash AND allocate to Down Payment line"""
        self.ensure_one()
        if not self.payment_attachment and self.payment_method == 'bank_transfer':
            raise ValidationError(_("Please upload the Payment Attachment before creating a payment."))
        if self.payment_method in ['bank_transfer', 'cash']:
            journal_type = 'bank' if self.payment_method == 'bank_transfer' else 'cash'
            journal = self.env['account.journal'].search([('type', '=', journal_type)], limit=1)

            if not journal:
                raise ValidationError(_("No %s journal found. Please create one first.") % journal_type)

            amount = self.amount
            memo = f'Reservation Payment - {self.sale_reservation_id.name}'

            if float_compare(amount, 0.0, precision_digits=2) <= 0:
                raise ValidationError(_("Payment amount must be greater than zero."))
            total_payments = 0
            total_cheques = 0
            if self.sale_reservation_id.account_payment_ids:
                total_payments = sum(self.sale_reservation_id.account_payment_ids.filtered(
                    lambda p: p.payment_type == 'inbound' and p.state != 'canceled' and p.from_down_payment == True
                ).mapped('amount'))
            if self.sale_reservation_id.cheque_manage_ids:
                total_cheques = sum(self.sale_reservation_id.cheque_manage_ids.filtered(
                    lambda c: c.state not in ['return_to_client', 'return', 'cancel'] and c.from_down_payment == True
                ).mapped('amount'))
            total_paid = total_payments + total_cheques + self.amount
            total_required = self.sale_reservation_id.down_payment - self.sale_reservation_id.eoi_amount
            if float_compare(total_paid, total_required, precision_digits=2) > 0:
                raise ValidationError(_("The amount will be greater than Down Payment."))
            #eoi if exists
            eoi = None
            if self.sale_reservation_id and self.sale_reservation_id.eoi_id:
                eoi = self.sale_reservation_id.eoi_id

            payment = self.env['account.payment'].create({
                'partner_id': self.sale_reservation_id.customer_id.id,
                'payment_type': 'inbound',
                'amount': amount,
                'sale_reservation_id': self.sale_reservation_id.id,
                'eoi_id': eoi.id if eoi else False,
                'unit_id': self.sale_reservation_id.unit_id.id if self.sale_reservation_id.unit_id else False,
                'currency_id': self.sale_reservation_id.currency_id.id,
                'memo': memo,
                'payment_method_type': journal_type,
                'journal_id': journal.id,
                'is_down_payment': True,
                'from_down_payment': True,
                'reservation_payment_id': self.id,
                'from_reservation': self.env.context.get('from_reservation', False),
            })
            self.is_payment_created = True

            # --- ALLOCATE TO DOWN PAYMENT INSTALLMENT LINE ---
            reservation = self.sale_reservation_id
            if reservation and reservation.installment_ids:
                dp_lines = reservation.installment_ids.filtered(
                    lambda l: l.is_down_payment or l.is_down_payment_reservation or (l.name and 'Down Payment' in l.name)
                )
                if dp_lines:
                    dp_line = dp_lines[0]
                    self.env['payment.allocation'].create({
                        'payment_id': payment.id,
                        'installment_id': dp_line.id,
                        'allocated_amount': payment.amount,
                    })
                    dp_line.write({'payment_method_used': 'payment'})
            # -------------------------------------------------

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
        """Create cheque payment AND allocate to Down Payment line"""
        self.ensure_one()
        if not self.payment_attachment:
            raise ValidationError(_("Please upload the Payment Attachment before creating a cheque payment."))
        journal = self.env['account.journal'].search([], limit=1)

        if not journal:
            raise ValidationError(_("No journal found. Please create one first."))

        amount = self.amount

        if float_compare(amount, 0.0, precision_digits=2) <= 0:
            raise ValidationError(_("Payment amount must be greater than zero."))
        total_payments = 0
        total_cheques = 0
        if self.sale_reservation_id.account_payment_ids:
            total_payments = sum(self.sale_reservation_id.account_payment_ids.filtered(
                lambda p: p.payment_type == 'inbound' and p.state != 'canceled' and p.from_down_payment == True
            ).mapped('amount'))
        if self.sale_reservation_id.cheque_manage_ids:
            total_cheques = sum(self.sale_reservation_id.cheque_manage_ids.filtered(
                lambda c: c.state not in ['return_to_client', 'return', 'cancel'] and c.from_down_payment == True
            ).mapped('amount'))
        total_paid = total_payments + total_cheques + self.amount
        total_required = self.sale_reservation_id.down_payment - self.sale_reservation_id.eoi_amount
        if float_compare(total_paid, total_required, precision_digits=2) > 0:
            raise ValidationError(_("The amount will be greater than Down Payment."))

        eoi = None
        if self.sale_reservation_id and self.sale_reservation_id.eoi_id:
            eoi = self.sale_reservation_id.eoi_id
        cheque_payment_id = self.env['cheque.manage'].create({
            'payer': self.sale_reservation_id.customer_id.id,
            'amount': amount,
            'sale_reservation_id': self.sale_reservation_id.id,
            'journal_id': journal.id,
            'cheq_type': 'incoming',
            'from_down_payment': True,
            'reservation_payment_id': self.id,
            'eoi_id': eoi.id if eoi else False,
            'unit_id': self.sale_reservation_id.unit_id.id if self.sale_reservation_id.unit_id else False,
            'from_reservation': self.env.context.get('from_reservation', False),
        })
        self.is_payment_created = True

        # --- ALLOCATE TO DOWN PAYMENT INSTALLMENT LINE ---
        reservation = self.sale_reservation_id
        if reservation and reservation.installment_ids:
            dp_lines = reservation.installment_ids.filtered(
                lambda l: l.is_down_payment or l.is_down_payment_reservation or (l.name and 'Down Payment' in l.name)
            )
            if dp_lines:
                dp_line = dp_lines[0]
                self.env['payment.allocation'].create({
                    'cheque_id': cheque_payment_id.id,
                    'installment_id': dp_line.id,
                    'allocated_amount': cheque_payment_id.amount,
                })
                dp_line.write({'payment_method_used': 'cheque'})
        # -------------------------------------------------

        return {
            'name': _('Cheque Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'cheque.manage',
            'res_id': cheque_payment_id.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }








