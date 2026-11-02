from odoo import models, fields

class CountryCity(models.Model):

    _name = 'res.country.city'

    name = fields.Char(string='City')
    governorate_id = fields.Many2one('res.country.state', string='Governorate')
    neighborhood_ids = fields.One2many('neighborhood.neighborhood', 'city_id', string='Neighborhoods')
