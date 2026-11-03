from odoo import models, fields, api
from odoo.exceptions import ValidationError

FLAGS = [
    'for_initial_reservation',
    'for_draft_reservation',
    'blocked_from_cancellation',
    'blocked_from_termination',
    'for_upgrade',
    'for_reallocation',
    'for_sale_request',
]

class BlockReason(models.Model):
    _name = "block.reason"
    _description = "Block Reason for unit"

    name = fields.Char(string="Block Reason", required=True)
    for_initial_reservation = fields.Boolean(string="Initial Reservation")
    for_draft_reservation = fields.Boolean(string="On Hold")
    blocked_from_cancellation = fields.Boolean(string="Blocked from Cancellation")
    blocked_from_termination = fields.Boolean(string="Blocked from Termination")
    for_upgrade = fields.Boolean(string="For Upgrade")
    for_reallocation = fields.Boolean(string="Blocked for Reallocation")
    for_sale_request = fields.Boolean(string="For Sale Request")

    @api.constrains(*FLAGS)
    def _check_flags(self):
        for record in self:
            checked = [f for f in FLAGS if record[f]]
            if not checked:
                continue
            if len(checked) > 1:
                raise ValidationError("A reason can only have one flag checked.")

            for flag in checked:
                existing = self.search([(flag, '=', True), ('id', '!=', record.id)], limit=1)
                if existing:
                    label = self._fields[flag].string
                    raise ValidationError(
                        f"'{existing.name}' already has the '{label}' flag. Only one reason can have this flag."
                    )
