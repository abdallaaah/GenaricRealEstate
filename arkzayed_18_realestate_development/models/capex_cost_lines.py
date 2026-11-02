from odoo import models, fields

class CapexCostLines(models.Model):

    _name = "capex.cost.lines"

    capex_cost = fields.Many2one('capex.scope')
    quantity = fields.Float()
    price = fields.Float()