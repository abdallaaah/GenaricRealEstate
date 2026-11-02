from odoo import models, fields


class ResCountry(models.Model):
    _inherit = 'res.country'

    nationality = fields.Char()
    nationality_en = fields.Char()