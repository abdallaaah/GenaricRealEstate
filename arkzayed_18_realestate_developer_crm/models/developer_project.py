from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta


class DeveloperProject(models.Model):
    _name = 'developer.project'


    name = fields.Char(required=True)
    developer_id = fields.Many2one('res.partner', required=True)
    country_id = fields.Many2one('res.country', string="Country")
    governorate_id = fields.Many2one('res.country.state', string="Governorate", domain="[('country_id', '=', country_id)]")
    city_id = fields.Many2one('res.country.city')
    neighborhood_id = fields.Many2one('neighborhood.neighborhood', string='Neighborhood')
    project_commission_ids = fields.One2many('project.commission', 'developer_project_id', string="Project Commissions")
    last_end_date = fields.Date(
        compute='_compute_last_end_date',
        store=True,
    )
    double_commission = fields.Boolean(string='Double Commission')
    half_commission = fields.Boolean(string='Half Commission')
    @api.depends('project_commission_ids.end_date')
    def _compute_last_end_date(self):
        for rec in self:
            valid = rec.project_commission_ids.filtered(lambda l: l.end_date)
            if valid:
                # sort records with real dates
                last_comm = valid.sorted('end_date', reverse=True)[0]
                rec.last_end_date = last_comm.end_date + relativedelta(days=1)
            else:
                rec.last_end_date = False