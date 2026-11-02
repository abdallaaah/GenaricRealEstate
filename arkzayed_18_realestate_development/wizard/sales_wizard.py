from odoo import fields, models


class SalesReportWizard(models.TransientModel):
    _name = 'arkzayed.sales.report.wizard'
    _description = 'Sales Report Options'

    project_id = fields.Many2one('realestate.project', string='Project')
    building_ids = fields.Many2many(
        'real.estate.building', 'arkzayed_sales_wiz_building_rel', 'wizard_id', 'building_id',
        string='Buildings')
    contract_type = fields.Selection([('domestic', 'Domestic'), ('overseas', 'Overseas')], string='Contract Type')

    def action_print(self):
        self.ensure_one()
        data = {
            'project_id': self.project_id.id,
            'building_ids': self.building_ids.ids,
            'contract_type': self.contract_type,
        }
        return self.env.ref('arkzayed_18_realestate_development.action_report_sales').report_action(self, data=data)
