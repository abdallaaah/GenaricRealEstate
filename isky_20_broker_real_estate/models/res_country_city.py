from odoo import fields, models


class ResCountryCity(models.Model):
    _name = 'res.country.city'
    _description = "City"

    name = fields.Char(string="City", required=True)
    governorate_id = fields.Many2one('res.country.state', string="Governorate")
    neighborhood_ids = fields.One2many('neighborhood.neighborhood', 'city_id', string="Neighborhoods")
