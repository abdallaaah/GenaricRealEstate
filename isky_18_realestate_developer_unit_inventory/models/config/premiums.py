from odoo import api, fields, models
from ..selections import unit_type_selection

class Premiums(models.Model):
    _name = 'premiums.premiums'
    _rec_name = 'name'

    name = fields.Char()
    percentage = fields.Float()
    unit_type = fields.Selection(selection=unit_type_selection, string='Unit Type',default='residential')
