from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class ArkZayedCostDistributionWizardBuilding(models.TransientModel):
    _name = 'arkzayed.cost.distribution.wizard.building'
    _description = 'Wizard Building Summary'

    wizard_id = fields.Many2one('arkzayed.cost.distribution.wizard', ondelete='cascade')
    currency_id = fields.Many2one(related='wizard_id.currency_id')
    building_id = fields.Many2one('real.estate.building', string='Building')
    unit_count = fields.Integer(string='Units')
    area = fields.Float(string='Gross Area', digits=(16, 2))
    share = fields.Float(string='Share %', digits=(16, 2))
    amount = fields.Monetary(string='Amount', currency_field='currency_id')


class ArkZayedCostDistributionWizard(models.TransientModel):
    _name = 'arkzayed.cost.distribution.wizard'
    _description = 'Distribute a Bill/PO Line Cost Across Units'

    move_line_id = fields.Many2one('account.move.line', string='Bill Line', required=True)
    description = fields.Char(related='move_line_id.name', string='Description')
    currency_id = fields.Many2one(related='move_line_id.currency_id')
    line_total = fields.Monetary(related='move_line_id.price_total', string='Full Line Amount (incl. taxes)')
    remaining_amount = fields.Monetary(related='move_line_id.remaining_amount', string='Remaining Undistributed')
    amount_to_distribute = fields.Monetary(string='Amount to Distribute')
    zone_ids = fields.Many2many(
        'zone', 'arkzayed_dist_wizard_zone_rel', 'wizard_id', 'zone_id', string='Zones')
    building_ids = fields.Many2many(
        'real.estate.building', 'arkzayed_dist_wizard_building_rel', 'wizard_id', 'building_id',
        string='Buildings')
    unit_ids = fields.Many2many('real.estate.unit', string='Units')
    building_line_ids = fields.One2many(
        'arkzayed.cost.distribution.wizard.building', 'wizard_id',
        compute='_compute_building_lines', string='Buildings')
    total_area = fields.Float(compute='_compute_total_area', string='Total Selected Area')
    cost_per_sqm = fields.Monetary(compute='_compute_total_area', string='Cost / m²')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get('move_line_id') and 'amount_to_distribute' in fields_list:
            line = self.env['account.move.line'].browse(res['move_line_id'])
            res['amount_to_distribute'] = line.remaining_amount
        return res

    @api.onchange('zone_ids')
    def _onchange_zone_ids(self):
        # Picking zones selects all their buildings (and their units); the user can then drop
        # whole buildings by removing their tags, or single units from the list.
        buildings = self.env['real.estate.building']
        for zone in self.zone_ids:
            buildings |= zone._get_buildings()
        self.building_ids = buildings
        self.unit_ids = self.env['real.estate.unit'].search([('building_id', 'in', buildings.ids)])

    @api.onchange('building_ids')
    def _onchange_building_ids(self):
        self.unit_ids = self.env['real.estate.unit'].search([('building_id', 'in', self.building_ids.ids)])

    @api.depends('unit_ids', 'unit_ids.unit_area', 'amount_to_distribute')
    def _compute_building_lines(self):
        for wizard in self:
            total_area = sum(wizard.unit_ids.mapped('unit_area'))
            commands = [Command.clear()]
            buildings = wizard.unit_ids.mapped('building_id')
            groups = [(b, wizard.unit_ids.filtered(lambda u, b=b: u.building_id == b)) for b in buildings]
            no_building = wizard.unit_ids.filtered(lambda u: not u.building_id)
            if no_building:
                groups.append((self.env['real.estate.building'], no_building))
            for building, units in groups:
                area = sum(units.mapped('unit_area'))
                commands.append(Command.create({
                    'building_id': building.id,
                    'unit_count': len(units),
                    'area': area,
                    'share': area / total_area * 100 if total_area else 0.0,
                    'amount': wizard.amount_to_distribute * area / total_area if total_area else 0.0,
                }))
            wizard.building_line_ids = commands

    @api.depends('unit_ids', 'unit_ids.unit_area', 'amount_to_distribute')
    def _compute_total_area(self):
        for wizard in self:
            total_area = sum(wizard.unit_ids.mapped('unit_area'))
            wizard.total_area = total_area
            wizard.cost_per_sqm = wizard.amount_to_distribute / total_area if total_area else 0.0

    def action_confirm(self):
        self.ensure_one()
        if not self.unit_ids:
            raise UserError("Please select at least one unit.")

        if self.amount_to_distribute <= 0:
            raise UserError("Amount to distribute must be greater than zero.")

        if self.amount_to_distribute - self.move_line_id.remaining_amount > 0.01:
            raise UserError(
                "You are trying to distribute %.2f, but only %.2f is left undistributed on this line."
                % (self.amount_to_distribute, self.move_line_id.remaining_amount)
            )

        total_area = sum(self.unit_ids.mapped('unit_area'))
        if total_area <= 0:
            raise UserError("Selected units must have an area greater than zero.")

        unit_plan = self.env['account.analytic.plan'].search([('is_unit', '=', True)], limit=1)
        if not unit_plan:
            raise UserError("No analytic plan flagged as 'is_unit' was found.")

        cost_type = 'direct' if len(self.unit_ids) == 1 else 'indirect'
        line_total = self.move_line_id.price_total
        rate_per_sqm = self.amount_to_distribute / total_area
        analytic_dist = dict(self.move_line_id.analytic_distribution or {})

        # Each unit's cost = rate per m² x its gross area, rounded to the currency precision;
        # any rounding remainder goes to the largest unit so the parts sum exactly to the total.
        currency = self.move_line_id.currency_id
        unit_amounts = {u.id: currency.round(rate_per_sqm * u.unit_area) for u in self.unit_ids}
        remainder = currency.round(self.amount_to_distribute - sum(unit_amounts.values()))
        if remainder:
            largest = max(self.unit_ids, key=lambda u: u.unit_area)
            unit_amounts[largest.id] += remainder

        distribution = self.env['arkzayed.cost.distribution'].create({
            'move_line_id': self.move_line_id.id,
            'amount': self.amount_to_distribute,
            'cost_type': cost_type,
            'total_area': total_area,
            'rate_per_sqm': rate_per_sqm,
            'unit_count': len(self.unit_ids),
            'unit_ids': [(6, 0, self.unit_ids.ids)],
            'building_ids': [(6, 0, self.unit_ids.mapped('building_id').ids)],
        })

        for unit in self.unit_ids:
            if not unit.analytic_account_id:
                existing = self.env['account.analytic.account'].search([
                    ('plan_id', '=', unit_plan.id),
                    ('name', '=', unit.system_code),
                ], limit=1)
                if existing:
                    unit.analytic_account_id = existing.id
                else:
                    # Reuses Ark Zayed's own auto-creation logic on write()
                    unit.write({'system_code': unit.system_code})

            unit_amount = unit_amounts[unit.id]
            # Percentages in analytic_distribution are relative to the FULL line amount,
            # so a partial distribution naturally leaves the remainder unassigned.
            unit_percentage_of_line = (unit_amount / line_total) * 100
            key = str(unit.analytic_account_id.id)
            analytic_dist[key] = analytic_dist.get(key, 0) + unit_percentage_of_line

            self.env['arkzayed.cost.allocation'].create({
                'distribution_id': distribution.id,
                'unit_id': unit.id,
                'move_line_id': self.move_line_id.id,
                'percentage': unit_percentage_of_line,
                'unit_area': unit.unit_area,
                'rate_per_sqm': rate_per_sqm,
                'amount': unit_amount,
                'cost_type': cost_type,
            })

        self.move_line_id.analytic_distribution = analytic_dist

        remaining_after = self.move_line_id.remaining_amount
        if remaining_after <= 0.01:
            self.move_line_id.distribution_state = 'done'
        else:
            self.move_line_id.distribution_state = 'partial'

        return {'type': 'ir.actions.act_window_close'}
