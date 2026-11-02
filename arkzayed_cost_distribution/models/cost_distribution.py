from odoo import api, fields, models


class ArkZayedCostDistribution(models.Model):
    _name = 'arkzayed.cost.distribution'
    _description = 'Cost Distribution'
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    move_line_id = fields.Many2one('account.move.line', string='Bill Line', required=True, ondelete='cascade')
    move_id = fields.Many2one(related='move_line_id.move_id', string='Bill', store=True)
    partner_id = fields.Many2one(related='move_id.partner_id', string='Vendor', store=True)
    bill_date = fields.Date(related='move_id.date', string='Bill Date', store=True)
    description = fields.Char(related='move_line_id.name', string='Description')
    currency_id = fields.Many2one(related='move_line_id.currency_id')
    amount = fields.Monetary(string='Distributed Amount', currency_field='currency_id')
    cost_type = fields.Selection([
        ('direct', 'Direct'),
        ('indirect', 'Indirect'),
    ], string='Cost Type', required=True)
    total_area = fields.Float(string='Total Gross Area', digits=(16, 2))
    rate_per_sqm = fields.Float(string='Rate / m²', digits=(16, 2))
    unit_count = fields.Integer(string='Units')
    unit_ids = fields.Many2many(
        'real.estate.unit', 'arkzayed_cost_dist_unit_rel', 'distribution_id', 'unit_id', string='Units')
    building_ids = fields.Many2many(
        'real.estate.building', 'arkzayed_cost_dist_building_rel', 'distribution_id', 'building_id',
        string='Buildings')
    units_summary = fields.Char(compute='_compute_units_summary', string='Units')
    allocation_ids = fields.One2many('arkzayed.cost.allocation', 'distribution_id', string='Unit Details')

    @api.depends('unit_ids')
    def _compute_units_summary(self):
        for dist in self:
            codes = sorted(c for c in dist.unit_ids.mapped('system_code') if c)
            if len(codes) <= 4:
                dist.units_summary = ', '.join(codes)
            else:
                dist.units_summary = '%d units: %s ... %s' % (len(codes), codes[0], codes[-1])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('arkzayed.cost.distribution') or 'New'
        return super().create(vals_list)
