from odoo import api, fields, models
from odoo.exceptions import ValidationError

STAGE_FLAGS = [
    ('is_eoi', "EOI"),
    ('is_reserved', "Reserved"),
    ('is_contract', "Contract"),
    ('is_cancel', "Cancel"),
    ('is_request_to_cancel', "Request to Cancel"),
    ('is_collected', "Collected"),
    ('is_confirmed_contract', "Confirmed Contract"),
]


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    is_eoi = fields.Boolean(string="Is EOI Stage")
    is_reserved = fields.Boolean(string="Is Reserved Stage")
    is_contract = fields.Boolean(string="Is Contract Stage")
    is_cancel = fields.Boolean(string="Is Cancel Stage")
    is_request_to_cancel = fields.Boolean(string="Is Request to Cancel Stage")
    is_collected = fields.Boolean(string="Is Collected Stage")
    is_confirmed_contract = fields.Boolean(string="Is Confirmed Contract Stage")

    @api.constrains(*(flag for flag, _label in STAGE_FLAGS))
    def _check_unique_flags(self):
        for stage in self:
            for flag, label in STAGE_FLAGS:
                if stage[flag] and self.search_count([(flag, '=', True)]) > 1:
                    raise ValidationError(self.env._('Only one stage can be marked as "%s".', label))
