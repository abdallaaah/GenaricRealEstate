from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero

from .commission_feature_codes import (
    COMMISSION_FEATURE_HIERARCHY_STACKING,
    COMMISSION_FEATURE_OPERATIONS_SHARE,
    COMMISSION_FEATURE_PROJECT_ADDITIONAL,
    COMMISSION_FEATURE_REFERRAL_PLAN_MATCHING,
    COMMISSION_FEATURE_REQUIRE_PLAN_ASSIGNMENT,
    COMMISSION_FEATURE_RETROACTIVE,
    COMMISSION_FEATURE_SEGMENTATION,
    COMMISSION_FEATURE_TEAM_ROLLUP,
)

# Project commission percentages and segment bounds are configured to a few decimals;
# comparing them with == was fragile enough to flip a threshold branch on a rounding bit.
PERCENTAGE_PRECISION = 4


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
    applied_segment_id = fields.Many2one(
        'commission.segment', ondelete='set null',
        help="The segment this commission was computed at. Recorded because the retroactive "
             "pass has no way to know what a past deal was rated at otherwise.")
    retro_adjustment_ids = fields.One2many('commission.retro.adjustment', 'achievement_id')
    retro_active = fields.Monetary(
        compute='_compute_retro_active', store=True, currency_field='currency_id',
        help="Sum of the retroactive corrections on this row. Each one is an auditable "
             "line rather than a figure typed over the previous value.")
    total_commission_amount = fields.Monetary(
        compute='_compute_total_commission_amount', store=True, currency_field='currency_id')
    paid_amount = fields.Monetary(currency_field='currency_id')
    is_cancelled = fields.Boolean(
        help="Superseded or cancelled: kept for history but excluded from achieved-volume "
             "aggregation. Replaces deleting the row, which lost the audit trail.")
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('retro_adjustment_ids.difference')
    def _compute_retro_active(self):
        for achievement in self:
            achievement.retro_active = sum(achievement.retro_adjustment_ids.mapped('difference'))

    @api.depends('commission_amount', 'basic_hierarchy_commission', 'retro_active')
    def _compute_total_commission_amount(self):
        for achievement in self:
            achievement.total_commission_amount = (
                achievement.commission_amount + achievement.basic_hierarchy_commission + achievement.retro_active
            )

    @api.model
    def create_from_lead(self, lead):
        # Supersede rather than unlink: the retroactive pass needs to know what was
        # already booked, and a cancelled row is evidence, not clutter.
        self.search([('opportunity_id', '=', lead.id), ('is_cancelled', '=', False)]).write(
            {'is_cancelled': True})
        for line in lead.commission_ids:
            if not line.employee_id:
                continue
            if line.is_tcr_sales_person:
                self._create_for_tcr_sales_person(lead, line)
            else:
                self._create_for_hierarchy_beneficiary(lead, line)
        self._create_for_operations(lead)

    def _create_for_operations(self, lead):
        """Operations staff on an approved achieve plan, at a full share.

        Harvested from the live gen-2 engine, where operations users are paid alongside
        the sales hierarchy. They cannot come through lead.commission_ids: that list is
        built from the reporting chain, and an Operations job level sits outside it
        (hierarchy_sequence 0) precisely so it never absorbs sales targets.

        Anyone already paid on this deal through the hierarchy is skipped, so a person
        holding both roles is not paid twice.
        """
        if not self.env['broker.feature.flag'].is_feature_enabled(
                COMMISSION_FEATURE_OPERATIONS_SHARE, default=False):
            return
        already_paid = self.search([
            ('opportunity_id', '=', lead.id), ('is_cancelled', '=', False),
        ]).user_id
        operations_plans = self.env['sale.commission.plan'].search([
            ('type', '=', 'achieve'),
            ('state', '=', 'approved'),
            ('realestate_commission', '=', True),
            ('job_level_id.is_operations', '=', True),
            ('date_from', '<=', lead.achievement_date),
            ('date_to', '>=', lead.achievement_date),
        ] + self._referral_domain(lead))
        for plan in operations_plans:
            for user in plan.user_ids.user_id - already_paid:
                if not self._plan_covers_user(plan, user, lead.achievement_date):
                    continue
                amount = self._apply_project_adjustments(
                    lead, self._achieve_amount(plan, lead.contract_price))
                self.create({
                    'opportunity_id': lead.id,
                    'user_id': user.id,
                    'commission_plan_id': plan.id,
                    'sales_volume': lead.contract_price,
                    'commission_percentage': plan.commission_amount,
                    'commission_amount': amount,
                    **self._commission_company_vals(lead),
                })

    def _create_for_tcr_sales_person(self, lead, line):
        user = line.employee_id
        job = user.employee_id.job_id
        plan = self._find_plan(
            'target', job_position_id=job.id, date=lead.achievement_date, user=user, lead=lead)
        vals = {
            'opportunity_id': lead.id,
            'commission_line_id': line.id,
            'user_id': user.id,
            'commission_plan_id': plan.id,
            **self._commission_company_vals(lead),
        }
        if plan:
            vals.update(self._calc_achieved_target(user, line.commission, plan, lead))
        else:
            vals.update(self._calc_non_sales_amount(lead, line))
        if user.job_level_id and not user.job_level_id.is_sales_person:
            vals['basic_hierarchy_commission'] = self._get_basic_hierarchy_commission(user, lead)
        achievement = self.create(vals)
        if achievement.applied_segment_id:
            self._apply_retroactive(achievement, plan)
        return achievement

    def _create_for_hierarchy_beneficiary(self, lead, line):
        user = line.employee_id
        plan = self._find_plan(
            'achieve', job_level_id=user.job_level_id.id, date=lead.achievement_date,
            user=user, lead=lead)
        vals = {
            'opportunity_id': lead.id,
            'commission_line_id': line.id,
            'user_id': user.id,
            'commission_plan_id': plan.id,
            **self._commission_company_vals(lead),
        }
        vals.update(self._calc_non_sales_amount(lead, line, plan))
        self.create(vals)

    @api.model
    def _commission_company(self, company):
        """The company commission is booked into, which need not own the deal.

        Harvested from the live production engine, where a developer company sells the
        units and a separate broker company receives the commission and pays the sales
        team. Self-gating: with res.company.commission_broker_company_id unset -- the
        case for every existing install -- this returns the company unchanged, so no
        flag is needed to keep current behaviour.
        """
        return company.sudo().commission_broker_company_id or company

    def _commission_company_vals(self, lead):
        """company_id / currency_id for a new achievement, following the broker company."""
        company = self._commission_company(lead.company_id or self.env.company)
        return {'company_id': company.id, 'currency_id': company.currency_id.id}

    @api.model
    def _referral_domain(self, lead):
        """Plan domain restricting by how the deal was referred, or [] when not enabled.

        Matching is exact on both flags, as in the production engine: a broker-referred
        deal matches only plans flagged With Broker, and a deal with no broker matches
        only plans without it.
        """
        if lead is None or not self.env['broker.feature.flag'].is_feature_enabled(
                COMMISSION_FEATURE_REFERRAL_PLAN_MATCHING, default=False):
            return []
        return [
            ('with_broker', '=', bool(lead.broker_ids)),
            ('with_ambassador', '=', bool(lead.ambassador_ids)),
        ]

    @api.model
    def _plan_covers_user(self, plan, user, date):
        """Is `user` assigned to `plan` on `date`, per the plan's own From/To lines?

        The pre-v20 generations had a ``confirm_salesperson_plan`` for this, but it
        searched and threw the result away, then returned the plan regardless -- the
        check was never actually performed. The live gen-2 engine does perform it. Here
        it is real, and gated by ``commission_require_plan_assignment`` so enabling it
        cannot silently stop paying people on an existing install.
        """
        for assignment in plan.user_ids:
            if assignment.user_id != user:
                continue
            if assignment.date_from and date and assignment.date_from > date:
                continue
            if assignment.date_to and date and assignment.date_to < date:
                continue
            return True
        return False

    def _achieve_amount(self, plan, contract_price):
        """The achieve-plan (flat, non-bracketed) commission for one deal.

        Both pre-v20 generations, and the live gen-2 engine, read
        ``plan.commission_amount`` as a rate per million of contract price: 1000 earns
        0.1%. The v20 rewrite dropped the division and treats it as a flat currency
        amount -- on a 12M deal with a plan of 1000 that is 1,000 instead of 12,000, a
        12x difference on every hierarchy beneficiary's commission.

        Rather than pick a winner, both readings are available. The default is the v20
        reading so that upgrading this module changes nobody's commission; a client
        whose plans were written against the pre-v20 engine switches to per-million.
        """
        basis = self.env['ir.config_parameter'].sudo().get_param(
            'isky_20_broker_commission.achieve_commission_basis', 'flat')
        if basis == 'per_million':
            return contract_price * plan.commission_amount / 1_000_000.0
        return plan.commission_amount

    def _find_plan(self, plan_type, job_position_id=False, job_level_id=False, date=False,
                   user=None, lead=None):
        # Without a job key there is nothing to match on, and the filter would simply be
        # left out of the domain -- so a user with no hr.job silently picked up whichever
        # approved plan had the lowest id. No key means no plan.
        if not job_position_id and not job_level_id:
            return self.env['sale.commission.plan'].browse()
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
        domain += self._referral_domain(lead)
        plans = self.env['sale.commission.plan'].search(domain)
        if user is not None and self.env['broker.feature.flag'].is_feature_enabled(
                COMMISSION_FEATURE_REQUIRE_PLAN_ASSIGNMENT, default=False):
            plans = plans.filtered(lambda p: self._plan_covers_user(p, user, date))
        return plans[:1]

    def _calc_non_sales_amount(self, lead, line, plan=None):
        """Flat, non-bracketed commission: the plan's on-target commission amount,
        adjusted for the project's base-commission threshold/multiplier.
        """
        amount = self._achieve_amount(plan, lead.contract_price) if plan else 0.0
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
        achieved_total = self._get_user_achieved_amount(user, plan, period) + deal_amount
        achieved_rate = achieved_total / period.amount

        if self._segmentation_active(plan):
            return self._calc_from_segments(plan, lead, deal_amount, achieved_total, achieved_rate)

        # Native bracket path, unchanged: one bracket's rate applies to the whole deal,
        # and that rate is per million (5000 means 0.5%).
        bracket = plan.target_commission_ids.filtered(
            lambda c: c.target_rate <= achieved_rate).sorted('target_rate', reverse=True)[:1]
        rate = bracket.amount if bracket else 0.0
        amount = self._apply_project_adjustments(lead, deal_amount * rate / 1_000_000.0)
        return {
            'sales_volume': deal_amount,
            'commission_percentage': achieved_rate * 100,
            'commission_amount': amount,
        }

    def _segmentation_active(self, plan):
        return plan.use_custom_segments and self.env['broker.feature.flag'].is_feature_enabled(
            COMMISSION_FEATURE_SEGMENTATION, company=plan.company_id, default=False)

    def _segment_basis_value(self, plan, achieved_total, achieved_rate):
        """What the plan's segment bounds are measured against."""
        if plan.segment_basis == 'target_rate':
            # Bounds are configured in percent (0-100), so the rate is scaled to match.
            return achieved_rate * 100
        return achieved_total

    def _calc_from_segments(self, plan, lead, deal_amount, achieved_total, achieved_rate):
        """Cliff segmentation: the matched band's percentage applies to the whole deal.

        Marginal (slab) splitting is deliberately not implemented -- the agreed
        behaviour is cliff plus retroactive reachback, which is what the pre-v20
        generation did and what the client's plans describe.
        """
        basis_value = self._segment_basis_value(plan, achieved_total, achieved_rate)
        segment = self.env['commission.segment']._match(plan.segment_ids, basis_value)
        percentage = segment.percentage if segment else 0.0
        amount = self._apply_project_adjustments(lead, deal_amount * percentage / 100.0)
        return {
            'sales_volume': deal_amount,
            'commission_percentage': percentage,
            'commission_amount': amount,
            'applied_segment_id': segment.id,
        }

    # ------------------------------------------------------------------ retroactive

    def _retro_enabled(self, plan):
        return self.env['broker.feature.flag'].is_feature_enabled(
            COMMISSION_FEATURE_RETROACTIVE, company=plan.company_id, default=False)

    def _period_for(self, plan, date):
        return plan.target_ids.filtered(lambda t: t.date_from <= date <= t.date_to)[:1]

    def _apply_retroactive(self, achievement, plan):
        """Re-rate this period's earlier deals at the segment that now applies.

        Cliff segmentation makes the rate a property of the period rather than of the
        individual deal: crossing into a higher band lifts what every deal already
        booked in that period should have earned. This is the "retroactive effect" the
        pre-v20 generation implemented and the v20 port dropped.

        Scoped to the trigger's own plan, because a segment only means anything on the
        plan that defines it. (That is the opposite of the rollup, where filtering by
        plan was the defect -- there the point is to count other people's deals, and
        those people are on other plans.)
        """
        segment = achievement.applied_segment_id
        if not segment or not self._retro_enabled(plan):
            return
        period = self._period_for(plan, achievement.opportunity_id.achievement_date)
        if not period:
            return
        earlier = self.search([
            ('id', '!=', achievement.id),
            ('user_id', '=', achievement.user_id.id),
            ('commission_plan_id', '=', plan.id),
            ('is_cancelled', '=', False),
            ('applied_segment_id', '!=', False),
            ('applied_segment_id', '!=', segment.id),
            ('opportunity_id.achievement_date', '>=', period.date_from),
            ('opportunity_id.achievement_date', '<=', period.date_to),
        ])
        earlier._book_retro_to_segment(segment, achievement.opportunity_id)

    def _book_retro_to_segment(self, segment, trigger_lead):
        """Write one incremental correction per record, moving each to `segment`'s rate.

        The delta is measured against the row's *current effective* total
        (``commission_amount + retro_active``), not against what it was first booked at,
        so a row corrected more than once ends up with lines that sum to exactly
        "amount at the current segment minus amount as first booked".

        Each row is re-costed through its own opportunity, since the project threshold
        and multiplier that apply depend on that deal's project and date -- not on the
        deal that triggered the correction.
        """
        Adjustment = self.env['commission.retro.adjustment']
        for achievement in self:
            effective_before = achievement.commission_amount + achievement.retro_active
            recomputed = self._apply_project_adjustments(
                achievement.opportunity_id,
                achievement.sales_volume * segment.percentage / 100.0)
            if not float_is_zero(recomputed - effective_before, precision_digits=2):
                Adjustment.create({
                    'achievement_id': achievement.id,
                    'trigger_opportunity_id': trigger_lead.id,
                    'old_segment_id': achievement.applied_segment_id.id,
                    'new_segment_id': segment.id,
                    'old_amount': effective_before,
                    'new_amount': recomputed,
                })
            achievement.applied_segment_id = segment

    def action_cancel(self):
        """Cancel these rows, then re-rate the period without their volume.

        Removing a deal can move the person back down a band, so the corrections booked
        here are negative. The previous generation deleted achievement rows, which made
        a claw-back impossible to compute and destroyed the history along with it.
        """
        for achievement in self:
            plan = achievement.commission_plan_id
            lead = achievement.opportunity_id
            segmented = plan and self._segmentation_active(plan) and self._retro_enabled(plan)
            achievement.is_cancelled = True
            if not segmented:
                continue
            period = self._period_for(plan, lead.achievement_date)
            if not period or not period.amount:
                continue
            remaining = self.search([
                ('user_id', '=', achievement.user_id.id),
                ('commission_plan_id', '=', plan.id),
                ('is_cancelled', '=', False),
                ('applied_segment_id', '!=', False),
                ('opportunity_id.achievement_date', '>=', period.date_from),
                ('opportunity_id.achievement_date', '<=', period.date_to),
            ])
            if not remaining:
                continue
            achieved_total = self._get_user_achieved_amount(achievement.user_id, plan, period)
            basis_value = self._segment_basis_value(
                plan, achieved_total, achieved_total / period.amount)
            segment = self.env['commission.segment']._match(plan.segment_ids, basis_value)
            if segment:
                remaining._book_retro_to_segment(segment, lead)

    def _get_user_achieved_amount(self, user, plan, period):
        """Volume achieved against `period`'s target, by `user` plus whoever rolls up to them.

        Two things changed from the version this replaces.

        The hierarchy now comes from broker.sales.hierarchy via
        :meth:`res.users._get_subordinate_users`, rather than a per-role if/elif over
        job-level flags. That covers the cases the old branches missed -- a team with no
        team leader, a director's indirect reports -- and it is the same definition the
        achievement report uses, so calculation and reporting cannot drift apart again.

        And the search no longer filters ``commission_plan_id = plan.id``. Plans are
        matched per hr.job, so every subordinate sits on a different plan than their
        manager; that filter excluded all of them and the rollup silently returned
        nothing but the user's own deals. Any approved real-estate target plan counts
        now, which is what "volume this person achieved" actually means. Scoping is by
        the plan's company and the period's dates instead.
        """
        users = user
        if self.env['broker.feature.flag'].is_feature_enabled(
                COMMISSION_FEATURE_TEAM_ROLLUP, default=False):
            users |= user._get_subordinate_users()
        achievements = self.search([
            ('user_id', 'in', users.ids),
            ('is_cancelled', '=', False),
            # The resolved commission company, not the plan's: where a broker company is
            # configured the rows were booked there, and filtering on the plan's own
            # company would match none of them.
            ('company_id', '=', self._commission_company(plan.company_id).id),
            ('commission_plan_id.type', '=', 'target'),
            ('commission_plan_id.realestate_commission', '=', True),
            ('opportunity_id.achievement_date', '>=', period.date_from),
            ('opportunity_id.achievement_date', '<=', period.date_to),
        ])
        return sum(achievements.mapped('sales_volume'))

    def _get_basic_hierarchy_commission(self, user, lead):
        """Achieve-type commission for every level below this person's own, stacked.

        Paid to a team leader / manager / director who closed the deal personally, on
        top of their own target commission.

        Derived from job.level's hierarchy chain rather than the role flags the previous
        version branched on. That version handled only Director and Sales Manager, so a
        Team Leader who closed personally always stacked exactly nothing -- the branch
        for their case did not exist. Reading the chain also means a client who adds or
        removes a tier gets the right stack with no code change.
        """
        if not self.env['broker.feature.flag'].is_feature_enabled(
                COMMISSION_FEATURE_HIERARCHY_STACKING, default=False):
            return 0.0
        own_rank = user.job_level_id.hierarchy_sequence
        if not own_rank:
            return 0.0
        levels_below = self.env['job.level'].search([
            ('hierarchy_sequence', '>', 0),
            ('hierarchy_sequence', '<', own_rank),
        ])
        total = 0.0
        for level in levels_below:
            plan = self._find_plan(
                'achieve', job_level_id=level.id, date=lead.achievement_date, lead=lead)
            if plan:
                total += self._apply_project_adjustments(
                    lead, self._achieve_amount(plan, lead.contract_price))
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
        double_mode = IrConfigParameter.get_param(
            'isky_20_broker_commission.double_commission_mode', 'multiply')
        project_commission = lead.project_id.project_commission_ids.filtered(
            lambda c: c.start_date <= lead.achievement_date <= c.end_date)[:1]
        if not project_commission:
            return amount

        # float_compare, not ==: this branch decides whether the commission is capped,
        # and a stored 5.0 that is really 4.999999 would have taken the wrong one.
        against_threshold = float_compare(
            project_commission.commission_percentage, threshold, precision_digits=PERCENTAGE_PRECISION)
        if against_threshold < 0:
            amount /= 2
        elif against_threshold == 0 and max_amount:
            amount = min(amount, max_amount)

        if project_commission.commission_multiplier == 'half':
            amount /= 2
        elif project_commission.commission_multiplier == 'double':
            # Two readings of "double" exist in the field. The pre-v20 generations added
            # the base band's rate; the v20 rewrite silently changed it to x2. Both are
            # kept so a client gets the one their plans were written against.
            if double_mode == 'add_base_segment':
                amount += self._get_base_segment_amount(lead)
            else:
                amount *= 2

        if project_commission.additional_commission_percentage and self.env[
                'broker.feature.flag'].is_feature_enabled(
                COMMISSION_FEATURE_PROJECT_ADDITIONAL, default=False):
            # Captured on project.commission since the first generation of this engine
            # and read by none of them. Applied as an uplift on the computed commission.
            amount *= 1 + project_commission.additional_commission_percentage / 100.0
        return amount

    def _get_base_segment_amount(self, lead):
        """The plan's entry-band rate, for the 'add_base_segment' reading of "double".

        Mirrors the pre-v20 ``get_min_target_commission_rate``: the amount configured at
        the bottom of the ladder, which that generation added rather than doubling.
        """
        job = lead.user_id.employee_id.job_id
        plan = self._find_plan(
            'target', job_position_id=job.id, date=lead.achievement_date,
            user=lead.user_id, lead=lead)
        if not plan:
            return 0.0
        if self._segmentation_active(plan):
            base = self.env['commission.segment']._match(plan.segment_ids, 0.0)
            return lead.contract_price * base.percentage / 100.0 if base else 0.0
        base = plan.target_commission_ids.filtered(
            lambda c: not c.target_rate).sorted('target_rate')[:1]
        return lead.contract_price * base.amount / 1_000_000.0 if base else 0.0
