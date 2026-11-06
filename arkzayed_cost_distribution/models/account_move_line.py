from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    distribution_state = fields.Selection([
        ('pending', 'Not Distributed'),
        ('partial', 'Partially Distributed'),
        ('done', 'Fully Distributed'),
    ], string='Unit Distribution', default='pending')

    allocation_ids = fields.One2many('arkzayed.cost.allocation', 'move_line_id', string='Cost Allocations')

    distributed_amount = fields.Monetary(compute='_compute_distributed_amount', string='Distributed Amount')

    remaining_amount = fields.Monetary(compute='_compute_distributed_amount', string='Remaining to Distribute')

    @api.depends('allocation_ids.amount', 'price_total')
    def _compute_distributed_amount(self):
        for line in self:
            distributed = sum(line.allocation_ids.mapped('amount'))
            line.distributed_amount = distributed
            # The distributable amount is the line total including taxes.
            line.remaining_amount = line.price_total - distributed

    def action_open_cost_distribution_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Distribute Cost to Units',
            'res_model': 'arkzayed.cost.distribution.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_line_id': self.id},
        }
