from odoo import fields, models


class RealEstateNearbyConnectivity(models.Model):
    _name = 'real.estate.nearby.connectivity'

    name = fields.Char()
    image = fields.Image()
    project_id = fields.Many2one('realestate.project')
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)


