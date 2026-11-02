from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProgressUpdateWizard(models.TransientModel):
    _name = 'arkzayed.progress.update.wizard'
    _description = 'Update Construction Progress'

    unit_ids = fields.Many2many(
        'real.estate.unit', 'arkzayed_progress_wiz_unit_rel', 'wizard_id', 'unit_id', string='Units')
    building_ids = fields.Many2many(
        'real.estate.building', 'arkzayed_progress_wiz_building_rel', 'wizard_id', 'building_id',
        string='Buildings')
    percent = fields.Float(string='Progress %', required=True, digits=(16, 1))
    date = fields.Date(required=True, default=fields.Date.context_today)
    note = fields.Char()
    summary = fields.Char(compute='_compute_summary')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        model, ids = self.env.context.get('active_model'), self.env.context.get('active_ids') or []
        if model == 'real.estate.unit':
            res['unit_ids'] = [(6, 0, ids)]
        elif model == 'real.estate.building':
            res['building_ids'] = [(6, 0, ids)]
        return res

    @api.depends('unit_ids', 'building_ids')
    def _compute_summary(self):
        for wizard in self:
            parts = []
            if wizard.unit_ids:
                parts.append(_("%s unit(s)", len(wizard.unit_ids)))
            if wizard.building_ids:
                parts.append(_("%s building(s)", len(wizard.building_ids)))
            wizard.summary = ' + '.join(parts) or _("Nothing selected")

    def action_confirm(self):
        self.ensure_one()
        if not (self.unit_ids or self.building_ids):
            raise UserError(_("Select at least one unit or building."))
        vals = [{'unit_id': u.id} for u in self.unit_ids] + [{'building_id': b.id} for b in self.building_ids]
        for item in vals:
            item.update(percent=self.percent, date=self.date, note=self.note)
        self.env['arkzayed.construction.progress'].create(vals)
        return {'type': 'ir.actions.act_window_close'}
