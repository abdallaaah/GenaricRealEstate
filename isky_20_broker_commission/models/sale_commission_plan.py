from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleCommissionPlan(models.Model):
    _inherit = 'sale.commission.plan'

    # Defaults False, not True as in the v17 version: this module coexists with Enterprise's
    # generic Sale Commission app, which a client might also use for non-broker plans (e.g.
    # furniture sale orders) -- those must not be swept into the real estate engine by default.
    realestate_commission = fields.Boolean(
        default=False,
        help="Only plans flagged here are considered by the real estate commission engine.")
    job_position_id = fields.Many2one(
        'hr.job', help="For tiered (target) plans: the job position this plan applies to.")
    job_level_id = fields.Many2one(
        'job.level', help="For linear (achieve) plans: the job level this plan applies to.")

    # ------------------------------------------------------------------ referral matching

    # Harvested from the live production engine, which partitions plans by how the deal
    # was referred: a plan flagged With Broker applies *only* to broker-referred deals,
    # and an unflagged plan applies only to deals with no broker. Matching is exact on
    # both flags, so a client using this needs a plan per referral combination.
    #
    # Deviation from that engine, deliberately: it also constrains the two flags to be
    # mutually exclusive, because its source field was a single "referred by" selection.
    # Here the lead carries independent broker_ids and ambassador_ids, so a deal can
    # genuinely have both -- and such a deal needs a plan with both flags set. Adding the
    # exclusivity constraint would leave those deals matching no plan and earning nothing.
    with_broker = fields.Boolean(
        string="With Broker",
        help="Restrict this plan to deals that were referred by an outside broker. Only "
             "consulted when Referral Plan Matching is enabled.")
    with_ambassador = fields.Boolean(
        string="With Ambassador",
        help="Restrict this plan to deals that were referred by an ambassador. Only "
             "consulted when Referral Plan Matching is enabled.")

    # ------------------------------------------------------------------ segmentation

    use_custom_segments = fields.Boolean(
        string="Use Segments",
        help="Compute from this plan's own from-to segments instead of Odoo's target "
             "brackets. Off by default, so existing plans keep computing exactly as before.")
    segment_basis = fields.Selection([
        ('volume', "Sales Volume"),
        ('target_rate', "Target Completion %"),
    ], default='volume', required=True,
        help="What the segment bounds are measured against: cumulative sales volume in "
             "currency, or percentage of the period target achieved.")
    segment_ids = fields.One2many('commission.segment', 'plan_id', copy=True)

    @api.constrains('use_custom_segments', 'segment_ids')
    def _check_segments_present(self):
        for plan in self:
            if plan.use_custom_segments and not plan.segment_ids:
                raise ValidationError(self.env._(
                    "%s is set to use segments but has none, so every deal on it would "
                    "earn nothing.", plan.display_name))

    # ------------------------------------------------------------------ assignment guard

    def action_approve(self):
        """Block approval when it would make plan lookup ambiguous.

        The engine resolves a person's plan with ``search(..., limit=1)``, so two
        approved plans of the same type covering one person at the same date would make
        the commission depend on row order. The pre-v20 generations guarded this on
        approve; the v20 port dropped the guard but kept the ``limit=1``.
        """
        self._check_user_date_overlap()
        return super().action_approve()

    def _check_user_date_overlap(self):
        for plan in self:
            if not plan.user_ids or not plan.date_from:
                continue
            overlapping = self.env['sale.commission.plan.user'].search([
                ('user_id', 'in', plan.user_ids.user_id.ids),
                ('plan_id', '!=', plan.id),
                ('plan_id.state', 'in', ['approved', 'done']),
                ('plan_id.type', '=', plan.type),
                ('plan_id.realestate_commission', '=', plan.realestate_commission),
                ('plan_id.company_id', '=', plan.company_id.id),
            ])
            for assignment in overlapping:
                other = assignment.plan_id
                if not other.date_from or not other.date_to or not plan.date_to:
                    continue
                if plan.date_from <= other.date_to and plan.date_to >= other.date_from:
                    raise ValidationError(self.env._(
                        "%(user)s is already on the approved %(type)s plan '%(other)s' "
                        "(%(other_from)s to %(other_to)s), which overlaps %(plan_from)s to %(plan_to)s. "
                        "Two approved plans covering the same person at the same date make the "
                        "commission depend on which row is read first. Adjust the dates or "
                        "remove the person from one plan.",
                        user=assignment.user_id.display_name,
                        type=dict(self._fields['type'].selection).get(other.type),
                        other=other.display_name,
                        other_from=other.date_from, other_to=other.date_to,
                        plan_from=plan.date_from, plan_to=plan.date_to,
                    ))

    # ------------------------------------------------------------------ onchanges

    @api.onchange('job_position_id')
    def _onchange_job_position_id(self):
        if self.type == 'target' and self.job_position_id:
            users = self.env['res.users'].search([('employee_ids.job_id', '=', self.job_position_id.id)])
            self.user_ids = [
                fields.Command.create({'user_id': user.id}) for user in users
            ]

    @api.onchange('job_level_id')
    def _onchange_job_level_id(self):
        if self.type == 'achieve' and self.job_level_id:
            users = self.env['res.users'].search([('job_level_id', '=', self.job_level_id.id)])
            self.user_ids = [
                fields.Command.create({'user_id': user.id}) for user in users
            ]
