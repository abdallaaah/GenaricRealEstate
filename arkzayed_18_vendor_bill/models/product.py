# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    insurance_exclude_tax = fields.Boolean(
        string='Insurance Exclude Tax',
        default=False,
        help="If checked, insurance percentage will be calculated on the amount without tax"
    )

    deduction = fields.Boolean()
    ipc_type = fields.Selection(
        [
            ('work_done', 'Work Done'),
            ('material', 'Material'),
        ],
        string='IPC Type',
    )

    is_social_insurance = fields.Boolean(
        string='Social Insurance'
    )

    is_engineering_fee = fields.Boolean(
        string='Engineering Syndicate Fee'
    )

    @api.constrains('is_social_insurance', 'is_engineering_fee')
    def _check_deduction_flags(self):
        for rec in self:
            if rec.is_social_insurance and rec.is_engineering_fee:
                raise ValidationError(
                    "Product cannot be Social Insurance and Engineering Fee at the same time."
                )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    insurance_exclude_tax = fields.Boolean(
        related='product_tmpl_id.insurance_exclude_tax',
        string='Insurance Exclude Tax',
        readonly=False,
        store=True
    )
    ipc_type = fields.Selection(
        related='product_tmpl_id.ipc_type',
        store=True,
        readonly=False
    )
    is_social_insurance = fields.Boolean(
        related='product_tmpl_id.is_social_insurance',
        store=True,
        readonly=False
    )

    is_engineering_fee = fields.Boolean(
        related='product_tmpl_id.is_engineering_fee',
        store=True,
        readonly=False
    )
