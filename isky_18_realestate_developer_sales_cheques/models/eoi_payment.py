from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class EoiPayment(models.Model):
    """Cheque side of eoi.payment. Phase 3 step 3: moved out of sales_crm so L2 does not
    hard-depend on the optional L1 cheque module (supplement S1)."""
    _inherit = 'eoi.payment'

    cheque_ids = fields.One2many('cheque.manage', 'eoi_payment_id', string='Cheques')

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
