from odoo import models, fields, api


class AccountMoveHistoryReport(models.Model):
    _name = "account.move.history.line.report"
    _description = "Vendor Bill History Line Report"

    move_id = fields.Many2one('account.move', string='Vendor Bill', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    previous_work = fields.Monetary(string='Previous Work', currency_field='currency_id')
    current_work = fields.Monetary(string='Current Work', currency_field='currency_id')
    total_work = fields.Monetary(string='Total Work', currency_field='currency_id', compute='_compute_total_work', store=True, readonly=False)
    currency_id = fields.Many2one('res.currency', string='Currency', related='move_id.currency_id', store=True)

    @api.depends('previous_work', 'current_work')
    def _compute_total_work(self):
        for line in self:
            line.total_work = line.previous_work + line.current_work
