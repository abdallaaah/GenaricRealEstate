from odoo import api, fields, models


class RealestateCommissionAchievement(models.Model):
    """Per-opportunity, per-hierarchy-member commission calculation.

    Created by create_from_lead() the moment a crm.lead reaches the
    "Confirmed Contract" stage (see crm_lead.py's write() hook). Reads the
    CRM module's commission.commission hierarchy lines (who gets a share)
    and this module's sale.commission.plan/target/target.commission
    configuration (how much), adapted to the Odoo 20 Enterprise
    sale_commission data model, which is structured differently from the
    Odoo 17 version this replaces (plan assignments are their own model,
    sale.commission.plan.user, not a plain user_ids many2many).
    """
    _name = 'realestate.commission.achievement'
    _description = "Real Estate Commission Achievement"

    opportunity_id = fields.Many2one('crm.lead', required=True, ondelete='cascade')
    commission_line_id = fields.Many2one('commission.commission', ondelete='cascade')
    user_id = fields.Many2one('res.users', required=True)
    job_level_id = fields.Many2one(related='user_id.job_level_id')
    is_tcr_sales_person = fields.Boolean(related='commission_line_id.is_tcr_sales_person')
    commission_plan_id = fields.Many2one('sale.commission.plan')
    sales_volume = fields.Monetary(currency_field='currency_id')
    commission_percentage = fields.Float(help="Matched target-bracket rate, or the flat plan commission amount basis.")
    commission_amount = fields.Monetary(currency_field='currency_id')
    basic_hierarchy_commission = fields.Monetary(
        currency_field='currency_id',
        help="For a team leader/manager/director who personally closed the deal: the stacked "
             "achieve-type commission for every level below them.")
    retro_active = fields.Monetary(currency_field='currency_id', help="Manual retroactive adjustment.")
    total_commission_amount = fields.Monetary(
        compute='_compute_total_commission_amount', store=True, currency_field='currency_id')
    paid_amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('commission_amount', 'basic_hierarchy_commission', 'retro_active')
    def _compute_total_commission_amount(self):
        for achievement in self:
            achievement.total_commission_amount = (
                achievement.commission_amount + achievement.basic_hierarchy_commission + achievement.retro_active
            )

    @api.model
    def create_from_lead(self, lead):
        self.search([('opportunity_id', '=', lead.id)]).unlink()
        for line in lead.commission_ids:
            if not line.employee_id:
                continue
            if line.is_tcr_sales_person:
                self._create_for_tcr_sales_person(lead, line)
            else:
                self._create_for_hierarchy_beneficiary(lead, line)

    def _create_for_tcr_sales_person(self, lead, line):
        user = line.employee_id
        job = user.employee_id.job_id
        plan = self._find_plan('target', job_position_id=job.id, date=lead.achievement_date)
        vals = {
            'opportunity_id': lead.id,
            'commission_line_id': line.id,
            'user_id': user.id,
            'commission_plan_id': plan.id,
        }
        if plan:
            vals.update(self._calc_achieved_target(user, line.commission, plan, lead))
        else:
            vals.update(self._calc_non_sales_amount(lead, line))
        if user.job_level_id and not user.job_level_id.is_sales_person:
            vals['basic_hierarchy_commission'] = self._get_basic_hierarchy_commission(user, lead)
        self.create(vals)

    def _create_for_hierarchy_beneficiary(self, lead, line):
        user = line.employee_id
        plan = self._find_plan('achieve', job_level_id=user.job_level_id.id, date=lead.achievement_date)
        vals = {
            'opportunity_id': lead.id,
            'commission_line_id': line.id,
            'user_id': user.id,
            'commission_plan_id': plan.id,
        }
        vals.update(self._calc_non_sales_amount(lead, line, plan))
        self.create(vals)

    def _find_plan(self, plan_type, job_position_id=False, job_level_id=False, date=False):
        domain = [
            ('type', '=', plan_type),
            ('state', '=', 'approved'),
            ('realestate_commission', '=', True),
        ]
        if job_position_id:
            domain.append(('job_position_id', '=', job_position_id))
        if job_level_id:
            domain.append(('job_level_id', '=', job_level_id))
        if date:
            domain += [('date_from', '<=', date), ('date_to', '>=', date)]
        return self.env['sale.commission.plan'].search(domain, limit=1)

    def _calc_non_sales_amount(self, lead, line, plan=None):
        """Flat, non-bracketed commission: the plan's on-target commission amount,
        adjusted for the project's base-commission threshold/multiplier.
        """
        amount = plan.commission_amount if plan else 0.0
        amount = self._apply_project_adjustments(lead, amount)
        return {
            'sales_volume': lead.contract_price * line.commission,
            'commission_percentage': plan.commission_amount if plan else 0.0,
            'commission_amount': amount,
        }

    def _calc_achieved_target(self, user, share, plan, lead):
        deal_amount = lead.contract_price * share
        period = plan.target_ids.filtered(
            lambda t: t.date_from <= lead.achievement_date <= t.date_to)[:1]
        if not period or not period.amount:
            return {'sales_volume': deal_amount, 'commission_percentage': 0.0, 'commission_amount': 0.0}
        already_achieved = self._get_user_achieved_amount(user, plan, period)
        achieved_total = already_achieved + deal_amount
        achieved_rate = achieved_total / period.amount
        bracket = plan.target_commission_ids.filtered(
            lambda c: c.target_rate <= achieved_rate).sorted('target_rate', reverse=True)[:1]
        rate = bracket.amount if bracket else 0.0
        amount = lead.contract_price * share * rate / 1_000_000.0
        amount = self._apply_project_adjustments(lead, amount)
        return {
            'sales_volume': deal_amount,
            'commission_percentage': achieved_rate * 100,
            'commission_amount': amount,
        }

    def _get_user_achieved_amount(self, user, plan, period):
        """Sum this user's achievements for the period; if they are a team
        leader/sales manager/director, also roll up their whole team's
        achievements for the same period (matching the v17 rollup logic).
        """
        team_users = self.env['res.users']
        if user.job_level_id.is_team_leader:
            team = self.env['crm.team'].search([('user_id', '=', user.id)], limit=1)
            team_users = team.member_ids
        elif user.job_level_id.is_sales_manager:
            teams = self.env['crm.team'].search([('sales_manager_id', '=', user.id)])
            team_users = teams.member_ids | teams.user_id
        elif user.job_level_id.is_directory:
            teams = self.env['crm.team'].search([('director_id', '=', user.id)])
            team_users = teams.member_ids | teams.user_id
        users = user | team_users
        achievements = self.search([
            ('user_id', 'in', users.ids),
            ('commission_plan_id', '=', plan.id),
            ('opportunity_id.achievement_date', '>=', period.date_from),
            ('opportunity_id.achievement_date', '<=', period.date_to),
        ])
        return sum(achievements.mapped('sales_volume'))

    def _get_basic_hierarchy_commission(self, user, lead):
        """A team leader/manager/director who personally closed the deal also
        gets the achieve-type commission for every level below their own,
        stacked.
        """
        levels_below = self.env['job.level']
        if user.job_level_id.is_directory:
            levels_below = self.env['job.level'].search([('is_sales_manager', '=', True)])
            levels_below |= self.env['job.level'].search([('is_team_leader', '=', True)])
        elif user.job_level_id.is_sales_manager:
            levels_below = self.env['job.level'].search([('is_team_leader', '=', True)])
        total = 0.0
        for level in levels_below:
            plan = self._find_plan('achieve', job_level_id=level.id, date=lead.achievement_date)
            if plan:
                total += self._apply_project_adjustments(lead, plan.commission_amount)
        return total

    def _apply_project_adjustments(self, lead, amount):
        """Project-level threshold/multiplier adjustments, reading
        isky_20_broker_real_estate's project.commission (time-windowed base
        percentage + commission_multiplier), and the two system parameters
        configured in Settings.
        """
        IrConfigParameter = self.env['ir.config_parameter'].sudo()
        threshold = IrConfigParameter.get_float('isky_20_broker_commission.base_percentage_threshold', 0.0)
        max_amount = IrConfigParameter.get_float('isky_20_broker_commission.base_max_commission_percentage_amount', 0.0)
        project_commission = lead.project_id.project_commission_ids.filtered(
            lambda c: c.start_date <= lead.achievement_date <= c.end_date)[:1]
        if project_commission:
            if project_commission.commission_percentage < threshold:
                amount /= 2
            elif project_commission.commission_percentage == threshold and max_amount:
                amount = min(amount, max_amount)
            if project_commission.commission_multiplier == 'half':
                amount /= 2
            elif project_commission.commission_multiplier == 'double':
                amount *= 2
        return amount
