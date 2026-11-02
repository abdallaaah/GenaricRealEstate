# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountMoveHistoryLine(models.Model):
    _name = 'account.move.history.line'
    _description = 'Vendor Bill History Line'

    move_id = fields.Many2one('account.move', string='Vendor Bill', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    previous_work = fields.Monetary(string='Previous Work', currency_field='currency_id')
    current_work = fields.Monetary(string='Current Work', currency_field='currency_id')
    total_work = fields.Monetary(string='Total Work', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', related='move_id.currency_id', store=True)
