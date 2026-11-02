from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    is_new = fields.Boolean(string="Is New Stage")
    is_eoi = fields.Boolean(string="Is EOI Stage")
    is_reserved = fields.Boolean(string="Is Reserved Stage")
    is_contract = fields.Boolean(string="Is Contract Stage")
    is_cancel = fields.Boolean(string="Is Cancel Stage")
    is_request_to_cancel = fields.Boolean(string="Is Request to Cancel Stage")
    is_collected = fields.Boolean(string="Is Collected Stage")
    is_confirmed_contract = fields.Boolean(string="Is Confirmed Contract Stage")

    @api.constrains('is_reserved', 'is_contract', 'is_cancel')
    def _check_unique_flags(self):
        if self.is_new and self.search_count([('is_new', '=', True)]) > 1:
            raise ValidationError('Only one stage can be marked as "Is New Stage".')
        if self.is_eoi and self.search_count([('is_eoi', '=', True)]) > 1:
            raise ValidationError('Only one stage can be marked as "Is Eoi Stage".')
        if self.is_reserved and self.search_count([('is_reserved', '=', True)]) > 1:
            raise ValidationError('Only one stage can be marked as "Is Reserved Stage".')
        if self.is_contract and self.search_count([('is_contract', '=', True)]) > 1:
            raise ValidationError('Only one stage can be marked as "Is Contract Stage".')
        if self.is_collected and self.search_count([('is_collected', '=', True)]) > 1:
            raise ValidationError('Only one stage can be marked as "Is Collected Stage".')
        if self.is_confirmed_contract and self.search_count([('is_confirmed_contract', '=', True)]) > 1:
            raise ValidationError('Only one stage can be marked as "Is Confirmed Contract Stage".')
        if self.is_cancel and self.search_count([('is_cancel', '=', True)]) > 1:
            raise ValidationError('Only one stage can be marked as "Is Cancel Stage".')
        if self.is_request_to_cancel and self.search_count([('is_request_to_cancel', '=', True)]) > 1:
            raise ValidationError('Only one stage can be marked as "Is Request to Cancel Stage".')
