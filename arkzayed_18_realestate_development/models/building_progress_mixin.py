from odoo import api, fields, models


class RealEstateBuilding(models.Model):
    _inherit = 'real.estate.building'

    responsible_engineer_id = fields.Many2one('res.users', string='Responsible Engineer', tracking=False)
    progress_ids = fields.One2many('arkzayed.construction.progress', 'building_id', string='Progress Updates')
    progress_percent = fields.Float(
        compute='_compute_progress', store=True, string='Progress', digits=(16, 1))
    progress_date = fields.Date(compute='_compute_progress', store=True, string='Last Update')
    progress_user_id = fields.Many2one('res.users', compute='_compute_progress', store=True, string='Updated By')
    progress_unit_ids = fields.One2many('real.estate.unit', 'building_id', string='Units')
    units_progress = fields.Float(
        compute='_compute_units_progress', store=True, string='Units Average', digits=(16, 1),
        help="Average progress of the units in this building, weighted by unit area.")
    units_count = fields.Integer(compute='_compute_units_progress', store=True, string='Units')

    @api.depends('progress_ids.percent', 'progress_ids.date')
    def _compute_progress(self):
        for building in self:
            last = building.progress_ids.sorted(key=lambda p: (p.date or fields.Date.today(), p._origin.id or 10**12))[-1:]
            building.progress_percent = last.percent if last else 0.0
            building.progress_date = last.date if last else False
            building.progress_user_id = last.user_id if last else False

    @api.depends('progress_unit_ids.construction_progress', 'progress_unit_ids.unit_area')
    def _compute_units_progress(self):
        for building in self:
            units = building.progress_unit_ids
            area = sum(units.mapped('unit_area'))
            if area:
                building.units_progress = sum(u.construction_progress * u.unit_area for u in units) / area
            elif units:
                building.units_progress = sum(units.mapped('construction_progress')) / len(units)
            else:
                building.units_progress = 0.0
            building.units_count = len(units)
