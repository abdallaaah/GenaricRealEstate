from odoo import fields, models


class NpvReportWizard(models.TransientModel):
    _name = 'arkzayed.npv.report.wizard'
    _description = 'NPV Executive Report - Options'

    project_id = fields.Many2one('realestate.project', string='Project')
    building_ids = fields.Many2many(
        'real.estate.building', 'arkzayed_npv_report_wiz_building_rel', 'wizard_id', 'building_id',
        string='Buildings')

    def action_print(self):
        self.ensure_one()
        data = {'project_id': self.project_id.id, 'building_ids': self.building_ids.ids}
        return self.env.ref('arkzayed_contract_npv.action_report_npv_executive').report_action(self, data=data)
