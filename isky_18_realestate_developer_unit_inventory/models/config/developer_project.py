from odoo import models, fields


class DeveloperProject(models.Model):
    _name = 'developer.project'

    name = fields.Char(required=True)
    developer_id = fields.Many2one('res.partner', required=True)
    country_id = fields.Many2one('res.country', string="Country")
    governorate_id = fields.Many2one('res.country.state', string="Governorate", domain="[('country_id', '=', country_id)]")
    city_id = fields.Many2one('res.country.city')
    neighborhood_id = fields.Many2one('neighborhood.neighborhood', string='Neighborhood')
