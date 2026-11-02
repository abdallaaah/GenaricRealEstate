from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_unit = fields.Boolean(string='Is Unit', default=False)



class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_unit = fields.Boolean(string='Is Unit', default=False)
