from odoo import models, fields

class Neighborhood(models.Model):

    _name = 'neighborhood.neighborhood'

    name = fields.Char(string='Neighborhood')
    city_id = fields.Many2one('res.country.city', string='City')
