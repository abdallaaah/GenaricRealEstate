from odoo import fields, models


class ProgressReportWizard(models.TransientModel):
    _name = 'arkzayed.progress.report.wizard'
    _description = 'Construction Progress Report Options'

    project_id = fields.Many2one('realestate.project', string='Project')
    building_ids = fields.Many2many(
        'real.estate.building', 'arkzayed_progress_rep_building_rel', 'wizard_id', 'building_id',
        string='Buildings')

    def action_print(self):
        self.ensure_one()
        data = {'project_id': self.project_id.id, 'building_ids': self.building_ids.ids}
        return self.env.ref('arkzayed_construction_progress.action_report_progress').report_action(self, data=data)
