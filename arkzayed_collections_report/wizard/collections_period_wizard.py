from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class CollectionsPeriodWizard(models.TransientModel):
    _name = 'arkzayed.collections.period.wizard'
    _description = 'Monthly Report Collections - Options'

    date_from = fields.Date(string='From', required=True,
                             default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(string='To', required=True, default=lambda self: fields.Date.context_today(self))
    project_id = fields.Many2one('realestate.project', string='Project')
    building_ids = fields.Many2many(
        'real.estate.building', 'arkzayed_coll_period_wiz_building_rel', 'wizard_id', 'building_id',
        string='Buildings')
    customer_ids = fields.Many2many(
        'res.partner', 'arkzayed_coll_period_wiz_customer_rel', 'wizard_id', 'partner_id',
        string='Clients', domain=[('is_customer', '=', True)])

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to:
                raise ValueError("'From' date must be before or equal to 'To' date.")

    def action_print(self):
        self.ensure_one()
        data = {
            'date_from': fields.Date.to_string(self.date_from),
            'date_to': fields.Date.to_string(self.date_to),
            'project_id': self.project_id.id,
            'building_ids': self.building_ids.ids,
            'customer_ids': self.customer_ids.ids,
        }
        return self.env.ref('arkzayed_collections_report.action_report_collections_period').report_action(
            self, data=data)
