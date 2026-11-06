from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Eoi(models.Model):
    """Cheque half of eoi.eoi. Moved out of sales_crm in Phase 3 step 3 (supplement S1) so
    that sales_crm installs without the cheque module."""
    _inherit = 'eoi.eoi'

    cheque_manage_ids = fields.One2many('cheque.manage', 'eoi_id', string='Cheque')
    cheque_count = fields.Integer(compute='_compute_cheque_count', string='Cheque Count')

    @api.depends('cheque_manage_ids')
    def _compute_cheque_count(self):
        for record in self:
            record.cheque_count = len(record.cheque_manage_ids)

    # --- hooks declared in sales_crm ------------------------------------------------------

    def _link_cheques_to_reservation(self, reservation):
        """Point this EOI's non-draft cheques at the reservation it just produced."""
        res = super()._link_cheques_to_reservation(reservation)
        for cheque in self.cheque_manage_ids:
            if cheque.state not in ['draft', 'return_to_client']:
                cheque.sale_reservation_id = reservation.id
        return res

    def _return_cheques_on_refund(self):
        """Return this EOI's outstanding cheques to the client."""
        res = super()._return_cheques_on_refund()
        cheques = self.env['cheque.manage'].search([
            ('eoi_id', '=', self.id), ('state', 'in', ['collect', 'register']),
        ])
        for cheque in cheques:
            cheque.action_return()
            if cheque.state == 'return_to_client':
                cheque.action_return_to_client()
        return res

    # --- cheque-only actions --------------------------------------------------------------

    def create_cheque_payment(self):
        self.ensure_one()
        cheque_payment_id = self.env['cheque.manage'].create({
            'payer': self.customer_id.id,
            'amount': self.reservation_amount,
            'eoi_id': self.id,
            'journal_id': self.env['account.journal'].search([], limit=1).id,
            'cheq_type': 'incoming',
            'from_eoi': True,
        })
        return {
            'name': _('Cheque Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'cheque.manage',
            'res_id': cheque_payment_id.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def check_cheque_payment(self):
        for rec in self:
            if not self.cheque_manage_ids:
                raise ValidationError("EOI Cheque Payment is Not Complete")
            else:
                if rec.cheque_manage_ids[0].amount != self.reservation_amount:
                    raise ValidationError("The Cheque Payment Of This EOI Not Equal The Reservation Amount")

                if rec.payment_methods != 'cheque':
                    raise ValidationError("Please use 'Check Payment' button for cash or bank payments")

                # Check if the cheque payment is not in draft or returned state
                # Assuming the cheque state is stored in a field called 'state' in account.payment
                if rec.cheque_manage_ids[0].state not in ['draft', 'return_to_client']:
                    rec.status = "paid"
                else:
                    raise ValidationError("EOI Cheque Payment is not in a valid state")

    def action_show_cheques(self):
        cheques = self.env['cheque.manage'].search([('eoi_id', '=', self.id)])
        context = {
            'default_cheq_type': 'incoming',
            'default_eoi_id': self.id,
            'default_amount': self.reservation_amount,
            'default_payer': self.customer_id.id,
        }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cheque.manage',
            'name': _("Cheques"),
            'target': 'current',
            'views': [(False, 'list'), (False, 'form')] if cheques else [(False, 'form'), (False, 'list')],
            'domain': [('eoi_id', '=', self.id)] if cheques else [],
            'context': context,
        }
