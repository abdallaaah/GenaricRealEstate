from odoo import models, fields


class DiscountConfig(models.Model):
    _name = 'discount.config'
    _description = 'Discount Configuration'

    name = fields.Char(
        string='Configuration Name',
        required=True
    )
    description = fields.Text(
        string='Description'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )