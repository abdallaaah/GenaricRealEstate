from odoo import api, fields, models


class RealEstateUnit(models.Model):
    _inherit = 'real.estate.unit'

    responsible_engineer_id = fields.Many2one('res.users', string='Responsible Engineer')
    progress_ids = fields.One2many('arkzayed.construction.progress', 'unit_id', string='Progress Updates')
    construction_progress = fields.Float(
        compute='_compute_construction_progress', store=True, string='Progress', digits=(16, 1))
    progress_source = fields.Selection([
        ('unit', 'Unit update'),
        ('building', 'Building update'),
        ('none', 'Not started'),
    ], compute='_compute_construction_progress', store=True, string='Progress From')
    progress_date = fields.Date(compute='_compute_construction_progress', store=True, string='Last Update')
    progress_user_id = fields.Many2one(
        'res.users', compute='_compute_construction_progress', store=True, string='Updated By')

    @api.depends('progress_ids.percent', 'progress_ids.date',
                 'building_id.progress_ids.percent', 'building_id.progress_ids.date')
    def _compute_construction_progress(self):
        # The most recent update wins, whether it was made on the unit or on its building.
        for unit in self:
            own = unit.progress_ids.sorted(key=lambda p: (p.date or fields.Date.today(), p._origin.id or 10**12))[-1:]
            shared = unit.building_id.progress_ids.sorted(key=lambda p: (p.date or fields.Date.today(), p._origin.id or 10**12))[-1:]
            if own and (not shared or (own.date, own._origin.id or 10**12) >= (shared.date, shared._origin.id or 10**12)):
                chosen, source = own, 'unit'
            elif shared:
                chosen, source = shared, 'building'
            else:
                chosen, source = self.env['arkzayed.construction.progress'], 'none'
            unit.construction_progress = chosen.percent if chosen else 0.0
            unit.progress_source = source
            unit.progress_date = chosen.date if chosen else False
            unit.progress_user_id = chosen.user_id if chosen else False
