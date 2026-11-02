from odoo import api, fields, models


class RealEstateBuilding(models.Model):
    _inherit = 'real.estate.building'

    unit_ids = fields.One2many('real.estate.unit', 'building_id', string='Units')
    units_gross_area = fields.Float(
        compute='_compute_units_gross_area', store=True, string='Total Units Gross Area')

    @api.depends('unit_ids.unit_area')
    def _compute_units_gross_area(self):
        for building in self:
            building.units_gross_area = sum(building.unit_ids.mapped('unit_area'))
