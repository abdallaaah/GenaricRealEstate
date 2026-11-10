from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    company_profile = fields.Binary()
    commission_broker_company_id = fields.Many2one(
        'res.company', string="Commission Broker Company",
        help="Book commission earned on this company's deals into this company instead. "
             "Used where a developer company sells the units while a separate broker company "
             "receives the commission and pays the sales team. Leave empty to book commission "
             "in the company that owns the deal.")
