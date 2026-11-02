from odoo import fields, models


class Zone(models.Model):
    _inherit = 'zone'

    bua = fields.Float(compute='_compute_building_totals', string='BUA (Total of Buildings)')
    units_gross_area = fields.Float(compute='_compute_building_totals', string='Total Units Gross Area')

    def _get_buildings(self):
        self.ensure_one()
        # In onchange the zone can be a virtual record, so use the id of the saved origin.
        return self.env['real.estate.building'].search([('parent_source_id', '=', 'zone,%d' % self._origin.id)])

    def _compute_building_totals(self):
        for zone in self:
            buildings = zone._get_buildings()
            zone.bua = sum(buildings.mapped('bua'))
            zone.units_gross_area = sum(buildings.mapped('units_gross_area'))
