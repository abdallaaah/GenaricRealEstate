from odoo import api, fields, models


class RealEstateUnit(models.Model):
    _inherit = 'real.estate.unit'

    allocation_ids = fields.One2many('arkzayed.cost.allocation', 'unit_id', string='Cost Allocations')
    currency_id = fields.Many2one('res.currency', compute='_compute_costs', string='Currency')
    direct_cost = fields.Monetary(compute='_compute_costs', string='Direct Cost', currency_field='currency_id')
    indirect_cost = fields.Monetary(compute='_compute_costs', string='Indirect Cost', currency_field='currency_id')
    total_cost = fields.Monetary(compute='_compute_costs', string='Total Cost', currency_field='currency_id')
    cost_per_sqm = fields.Monetary(compute='_compute_costs', string='Cost / m²', currency_field='currency_id')
    sale_price_per_sqm_after_discount = fields.Monetary(
        compute='_compute_costs', string='Sale Price / m² (After Discount)', currency_field='currency_id')
    profit_per_sqm = fields.Monetary(compute='_compute_costs', string='Profit / m²', currency_field='currency_id')
    total_profit = fields.Monetary(compute='_compute_costs', string='Total Profit', currency_field='currency_id')

    @api.depends('allocation_ids.amount', 'allocation_ids.cost_type', 'unit_area', 'price_after_discount')
    def _compute_costs(self):
        for unit in self:
            unit.currency_id = unit.env.company.currency_id
            direct = sum(unit.allocation_ids.filtered(lambda a: a.cost_type == 'direct').mapped('amount'))
            indirect = sum(unit.allocation_ids.filtered(lambda a: a.cost_type == 'indirect').mapped('amount'))
            unit.direct_cost = direct
            unit.indirect_cost = indirect
            unit.total_cost = direct + indirect

            if unit.unit_area > 0:
                unit.cost_per_sqm = unit.total_cost / unit.unit_area
                unit.sale_price_per_sqm_after_discount = unit.price_after_discount / unit.unit_area
            else:
                unit.cost_per_sqm = 0
                unit.sale_price_per_sqm_after_discount = 0

            unit.profit_per_sqm = unit.sale_price_per_sqm_after_discount - unit.cost_per_sqm
            unit.total_profit = unit.price_after_discount - unit.total_cost
