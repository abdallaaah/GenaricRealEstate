from odoo import fields, models
from ..selections import residential_type_selection

class ResidentialSubType(models.Model):
    _name = "residential.sub.type"
    _description = "Residential Sub Type"

    name = fields.Char()
    type = fields.Selection(selection=residential_type_selection, string='Residential Type')
    number_of_slots = fields.Integer(string='Number of Slots')