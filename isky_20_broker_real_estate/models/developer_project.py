from odoo import api, fields, models


class DeveloperProject(models.Model):
    _name = 'developer.project'
    _description = "Developer Project"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    developer_id = fields.Many2one('res.partner', required=True , domain="[('is_developer', '=', True)]")
    country_id = fields.Many2one('res.country')
    governorate_id = fields.Many2one('res.country.state', domain="[('country_id', '=', country_id)]")
    city_id = fields.Many2one('res.country.city',string="District")
    neighborhood_id = fields.Many2one('neighborhood.neighborhood')
    project_commission_ids = fields.One2many('project.commission', 'developer_project_id', string="Project Commissions")
    last_end_date = fields.Date(compute='_compute_last_end_date', store=True)

    @api.depends('project_commission_ids.end_date')
    def _compute_last_end_date(self):
        for project in self:
            dated = project.project_commission_ids.filtered('end_date')
            if dated:
                last = dated.sorted('end_date', reverse=True)[0]
                project.last_end_date = fields.Date.add(last.end_date, days=1)
            else:
                project.last_end_date = False
