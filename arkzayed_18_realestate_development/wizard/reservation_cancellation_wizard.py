from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ReservationCancellationWizard(models.TransientModel):
    _name = 'reservation.cancellation.wizard'
    _description = 'Reservation Cancellation Wizard'

    sale_reservation_id = fields.Many2one('real.estate.sale.reservation', string='Reservation', required=True)
    cancellation_type = fields.Selection([
        ('without_penalty', 'Cancel Without Penalty'),
        ('with_penalty', 'Cancel With Penalty'),
    ], string='Cancellation Type', default='without_penalty', required=True)
    penalty_amount = fields.Float(string='Penalty Amount')
    paid_amount = fields.Float(string='Paid Amount', compute='_compute_paid_amount')
    refund_amount = fields.Float(string='Refund Amount', compute='_compute_refund_amount')

    @api.depends('sale_reservation_id', 'sale_reservation_id.state', 'sale_reservation_id.account_payment_ids', 'sale_reservation_id.cheque_manage_ids')
    def _compute_paid_amount(self):
        for rec in self:
            total_paid = 0.0
            for payment in rec.sale_reservation_id.account_payment_ids:
                if payment.payment_type == 'inbound' and payment.state in ('posted', 'paid'):
                    total_paid += payment.amount

            for cheque in rec.sale_reservation_id.cheque_manage_ids:
                if cheque.state not in ('draft', 'return_to_client'):
                    total_paid += cheque.amount

            rec.paid_amount = total_paid

    @api.depends('paid_amount', 'penalty_amount', 'cancellation_type')
    def _compute_refund_amount(self):
        for rec in self:
            if rec.cancellation_type == 'with_penalty':
                rec.refund_amount = rec.paid_amount - rec.penalty_amount
            else:
                rec.refund_amount = rec.paid_amount

    @api.onchange('cancellation_type')
    def _onchange_cancellation_type(self):
        if self.cancellation_type == 'without_penalty':
            self.penalty_amount = 0.0

    def action_confirm_cancellation(self):
        self.ensure_one()

        if self.cancellation_type == 'with_penalty' and self.penalty_amount <= 0:
            raise ValidationError("Please enter a valid penalty amount.")

        if self.penalty_amount > self.paid_amount:
            raise ValidationError("Penalty amount cannot exceed the paid amount.")

        cancel_reason = self.env['block.reason'].search([('blocked_from_cancellation', '=', True)], limit=1)
        if not cancel_reason:
            raise ValidationError("No block reason is configured for 'Blocked from Cancellation'. Please configure one in Block Reasons.")

        self.sale_reservation_id.write({
            'state': 'cancelled',
        })

        if self.sale_reservation_id.unit_id:
            self.sale_reservation_id.unit_id.write({
                'unit_status': 'blocked',
                'reason_id': cancel_reason.id,
            })

        if self.refund_amount > 0:
            self._create_refund_payment()

        if self.cancellation_type == 'with_penalty' and self.penalty_amount > 0:
            self._create_penalty_journal_entry()

        return {'type': 'ir.actions.act_window_close'}

    def _create_refund_payment(self):
        journal = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
        if not journal:
            journal = self.env['account.journal'].search([('type', '=', 'cash')], limit=1)
        if not journal:
            raise ValidationError("No bank or cash journal found. Please create one first.")

        params = self.env['ir.config_parameter'].sudo()
        cancellation_penalty_account_id = params.get_param('arkzayed_18_realestate_development.cancellation_penalty_account_id')

        payment_vals = {
            'partner_id': self.sale_reservation_id.customer_id.id,
            'payment_type': 'outbound',
            'partner_type': 'customer',
            'amount': self.refund_amount,
            'journal_id': journal.id,
            'sale_reservation_id': self.sale_reservation_id.id,
            'memo': f'Refund for cancelled reservation {self.sale_reservation_id.name}',
        }

        if cancellation_penalty_account_id:
            payment_vals['destination_account_id'] = int(cancellation_penalty_account_id)

        payment = self.env['account.payment'].create(payment_vals)

        if self.cancellation_type == 'with_penalty':
            message = (f"Reservation cancelled with penalty: {self.penalty_amount}")
        else:
            message = ("Reservation cancelled without penalty.")

        self.sale_reservation_id.message_post(body=message)

        return payment

    def _create_penalty_journal_entry(self):
        params = self.env['ir.config_parameter'].sudo()
        debit_account_id = params.get_param('arkzayed_18_realestate_development.cancellation_refund_debit_account_id')
        credit_account_id = params.get_param('arkzayed_18_realestate_development.cancellation_refund_credit_account_id')
        journal_id = params.get_param('arkzayed_18_realestate_development.cancellation_refund_journal_id')

        if not debit_account_id or not credit_account_id:
            raise ValidationError("Please configure the Cancellation Refund Debit and Credit accounts in Settings.")

        if not journal_id:
            raise ValidationError("Please configure the Cancellation Refund Journal in Settings.")

        move_vals = {
            'journal_id': int(journal_id),
            'ref': f'Penalty for cancelled reservation {self.sale_reservation_id.name}',
            'partner_id': self.sale_reservation_id.customer_id.id,
            'sale_reservation_id': self.sale_reservation_id.id,
            'line_ids': [
                (0, 0, {
                    'name': f'Penalty - {self.sale_reservation_id.name}',
                    'account_id': int(debit_account_id),
                    'partner_id': self.sale_reservation_id.customer_id.id,
                    'debit': self.penalty_amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': f'Penalty - {self.sale_reservation_id.name}',
                    'account_id': int(credit_account_id),
                    'partner_id': self.sale_reservation_id.customer_id.id,
                    'debit': 0.0,
                    'credit': self.penalty_amount,
                }),
            ],
        }

        move = self.env['account.move'].create(move_vals)

        self.sale_reservation_id.penalty_move_id = move.id
        self.sale_reservation_id.message_post(
            body=f"Penalty journal entry created: {move.name} for amount {self.penalty_amount}"
        )

        return move

