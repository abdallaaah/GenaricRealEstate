# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountTaxGroup(models.Model):
    _inherit = 'account.tax.group'

    include_in_insurance = fields.Boolean(
        string='Include in Insurance Calculation',
        default=False,
        help="If checked, this tax will be included when calculating insurance on products that include tax"
    )
