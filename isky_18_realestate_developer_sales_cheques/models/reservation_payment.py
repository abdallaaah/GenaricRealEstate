from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class ReservationPayment(models.Model):
    """Cheque side of reservation.payment. Phase 3 step 3: moved out of sales_crm so L2 does not
    hard-depend on the optional L1 cheque module (supplement S1)."""
    _inherit = 'reservation.payment'

    cheque_ids = fields.One2many('cheque.manage', 'reservation_payment_id', string='Cheques')

    # S6 guard pattern: redeclare with this module's own paths added, then call super().
    @api.depends('payment_ids.state', 'payment_ids.amount',
                 'cheque_ids.state', 'cheque_ids.amount')
    def _compute_is_paid(self):
        return super()._compute_is_paid()

    def _paid_total(self):
        """Add incoming cheques that are not draft, returned or cancelled."""
        self.ensure_one()
        return super()._paid_total() + sum(self.cheque_ids.filtered(
            lambda c: c.cheq_type == 'incoming'
            and c.state not in ('draft', 'return_to_client', 'return', 'cancel')
        ).mapped('amount'))

    # --- create_cheque(), moved verbatim from sales_crm ---------------------------------

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
