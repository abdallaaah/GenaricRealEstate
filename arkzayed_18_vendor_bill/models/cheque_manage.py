# -*- coding: utf-8 -*-

from odoo import models, fields


class ChequeManage(models.Model):
    _inherit = 'cheque.manage'

    requisition_id = fields.Many2one(
        'purchase.requisition',
        string='Purchase Requisition',
        readonly=True,
        help="Related purchase requisition for down payment"
    )
