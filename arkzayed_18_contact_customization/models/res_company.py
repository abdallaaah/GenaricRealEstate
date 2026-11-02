from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    company_profile = fields.Binary()

