from odoo import models, fields, api,_
from odoo.exceptions import UserError, ValidationError


class ReservationChangeUnitWizard(models.TransientModel):
    _name = 'reservation.change.unit.wizard'

    reservation_id = fields.Many2one('real.estate.sale.reservation',required=True,readonly=True)
    old_unit_id = fields.Many2one('real.estate.unit',string='Current Unit',readonly=True)
    new_unit_id = fields.Many2one('real.estate.unit',string='New Unit',required=True)

    def action_confirm_change(self):
        self.ensure_one()
        if not self.new_unit_id:
            raise UserError("Please select a new unit.")
        if self.new_unit_id == self.old_unit_id:
            raise UserError("You must select a different unit.")
        if self.new_unit_id.unit_status != 'available':
            raise UserError("Selected unit is no longer available.")
        if self.new_unit_id.unit_purpose != 'to_sale':
            raise UserError("Selected unit is no longer for sale.")
        reservation = self.reservation_id
        block_reason = self.env['block.reason'].search([
            ('for_upgrade', '=', True)
        ], limit=1)
        if not block_reason:
            block_reason = self.sudo().env['block.reason'].create({
                'name': 'BLOCKED FROM UPGRADE',
                'for_upgrade': True,
            })

        initial_reason = self.env['block.reason'].search([('for_initial_reservation', '=', True)], limit=1)

        if not initial_reason:
            raise ValidationError(
                _("No block reason is configured for 'Initial Reservation'. Please configure one in Block Reasons."))

        try:
            self.env.cr.execute(
                """
                SELECT id
                FROM real_estate_unit
                WHERE id IN %s
                    FOR UPDATE NOWAIT
                """,
                (tuple([self.new_unit_id.id, self.old_unit_id.id]),)
            )

            if self.new_unit_id.unit_status != 'available':
                raise UserError("Selected unit is no longer available.")

            old_unit_old_status = self.old_unit_id.unit_status

            self.new_unit_id.write({
                'unit_status': 'blocked',
                'reason_id': initial_reason.id
            })

            self.old_unit_id.write({
                'unit_status': 'blocked',
                'reason_id': block_reason.id if block_reason else False,
            })

            reservation.write({
                'unit_id': self.new_unit_id.id
            })

            self.new_unit_id.message_post(
                body=f"Unit upgraded/downgraded from {self.old_unit_id.name} ({self.old_unit_id.system_code}). Now assigned to reservation {reservation.name}.",
                subject="Unit Change - New Assignment"
            )

            self.old_unit_id.message_post(
                body=f"Unit changed to {self.new_unit_id.name} ({self.new_unit_id.system_code}). Reservation {reservation.name} moved to new unit. Unit now blocked.",
                subject="Unit Change - Blocked"
            )

            reservation.message_post(
                body=f"Unit changed from {self.old_unit_id.name} ({self.old_unit_id.system_code}) to {self.new_unit_id.name} ({self.new_unit_id.system_code})",
                subject="Unit Upgrade/Downgrade"
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Unit Changed Successfully'),
                    'message': _('Unit has been changed from %s to %s. Both units are now blocked.') % (
                        self.old_unit_id.name,
                        self.new_unit_id.name
                    ),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'}
                }
            }

        except Exception as e:
            print(f"Failed to change unit: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to change unit: %s'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
