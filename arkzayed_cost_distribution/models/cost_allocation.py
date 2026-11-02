from odoo import fields, models


class ArkZayedCostAllocation(models.Model):
    _name = 'arkzayed.cost.allocation'
    _description = 'Cost Allocation per Unit'
    _order = 'create_date desc'

    distribution_id = fields.Many2one('arkzayed.cost.distribution', string='Distribution', ondelete='cascade')
    unit_id = fields.Many2one('real.estate.unit', string='Unit', required=True, ondelete='cascade')
    move_line_id = fields.Many2one('account.move.line', string='Bill Line', required=True, ondelete='cascade')
    move_id = fields.Many2one(related='move_line_id.move_id', string='Bill', store=True)
    partner_id = fields.Many2one(related='move_id.partner_id', string='Vendor', store=True)
    bill_date = fields.Date(related='move_id.date', string='Bill Date', store=True)
    description = fields.Char(related='move_line_id.name', string='Line Description')
    building_id = fields.Many2one(related='unit_id.building_id', string='Building', store=True)
    percentage = fields.Float(string='Share % of Line', digits=(16, 6))
    currency_id = fields.Many2one(related='move_line_id.currency_id')
    unit_area = fields.Float(string='Unit Gross Area', digits=(16, 2))
    rate_per_sqm = fields.Float(string='Rate / m²', digits=(16, 6))
    amount = fields.Monetary(string='Allocated Amount', currency_field='currency_id')
    cost_type = fields.Selection([
        ('direct', 'Direct'),
        ('indirect', 'Indirect'),
    ], string='Cost Type', required=True)
