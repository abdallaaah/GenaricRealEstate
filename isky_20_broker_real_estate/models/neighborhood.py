from odoo import fields, models


class Neighborhood(models.Model):
    _name = 'neighborhood.neighborhood'
    _description = "Neighborhood"

    name = fields.Char(string="Neighborhood", required=True)
    city_id = fields.Many2one('res.country.city', string="City")
