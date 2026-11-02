from odoo import models, fields

class CapexType(models.Model):

    _name = 'capex.scope'

    name = fields.Char()
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
