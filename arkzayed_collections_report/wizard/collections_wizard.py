from odoo import fields, models


class CollectionsReportWizard(models.TransientModel):
    _name = 'arkzayed.collections.report.wizard'
    _description = 'Collections Report Options'

    project_id = fields.Many2one('realestate.project', string='Project')
    building_ids = fields.Many2many(
        'real.estate.building', 'arkzayed_coll_wiz_building_rel', 'wizard_id', 'building_id',
        string='Buildings')
    customer_ids = fields.Many2many(
        'res.partner', 'arkzayed_coll_wiz_customer_rel', 'wizard_id', 'partner_id',
        string='Clients', domain=[('is_customer', '=', True)])

    def action_print(self):
        self.ensure_one()
        data = {
            'project_id': self.project_id.id,
            'building_ids': self.building_ids.ids,
            'customer_ids': self.customer_ids.ids,
        }
        return self.env.ref('arkzayed_collections_report.action_report_collections').report_action(self, data=data)
