from odoo import fields, models


class AccountAnalyticPlan(models.Model):
    _inherit = "account.analytic.plan"

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        index=True,
        default=lambda self: self.env.company
    )
    is_project = fields.Boolean()
    is_building = fields.Boolean()
    is_unit = fields.Boolean()
    is_sale = fields.Boolean()
    is_wip = fields.Boolean()
