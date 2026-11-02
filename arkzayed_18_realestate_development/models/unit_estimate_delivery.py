from odoo import fields, models
from .selections import unit_type_selection


class UnitEstimateDelivery(models.Model):
    _name = 'unit.estimate.delivery'
    _description = 'Unit Estimated Delivery Years Configuration'
    _rec_name = 'unit_type'

    unit_type = fields.Selection(selection=unit_type_selection, string='Unit Type', required=True)
    estimate_delivery_years = fields.Integer(string='Estimated Delivery Years', default=3, required=True)

    _sql_constraints = [
        ('unit_type_uniq', 'unique(unit_type)', 'Only one configuration is allowed per unit type.'),
    ]
