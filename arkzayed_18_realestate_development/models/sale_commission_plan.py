from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class SaleCommissionPlan(models.Model):
    _inherit = "sale.commission.plan"

    realestate_commission = fields.Boolean(string="Real Estate Commission", default=True)
    job_position_id = fields.Many2one(comodel_name='hr.job')
    job_level_id = fields.Many2one(comodel_name='job.level')
    collection = fields.Float()
    with_broker = fields.Boolean(
        string="With Broker",
        default=False,
        help="If checked, this commission plan applies only when the deal is referred by a broker"
    )
    with_ambassador = fields.Boolean(
        string="With Ambassador",
        default=False,
        help="If checked, this commission plan applies only when the deal is referred by a ambassador"
    )

    commission_amount_display = fields.Char(
        string="Commission Amount",
        compute="_compute_commission_amount_display"
    )

    @api.constrains('with_broker', 'with_ambassador')
    def _check_broker_ambassador_exclusivity(self):
        for record in self:
            if record.with_broker and record.with_ambassador:
                raise ValidationError(
                    _("You cannot select both 'With Broker' and 'With Ambassador' at the same time.")
                )

    @api.depends('commission_amount')
    def _compute_commission_amount_display(self):
        for record in self:
            if record.commission_amount:
                record.commission_amount_display = f"{record.commission_amount} (/M)"
            else:
                record.commission_amount_display = ""

    @api.onchange('job_position_id')
    def _onchange_job_position_id(self):
        """Auto-populate user_ids based on selected job_position_id"""
        if self.job_position_id:
            # Find all users with employees that have this job position
            users_with_job = self.env['res.users'].search([
                ('employee_id.job_id', '=', self.job_position_id.id),
                ('active', '=', True)
            ])

            # Clear existing user_ids and add new ones
            self.user_ids = [(5, 0, 0)]  # Clear all existing records

            # Add users to the One2many field
            user_vals = []
            for user in users_with_job:
                user_vals.append((0, 0, {
                    'user_id': user.id,
                }))

            self.user_ids = user_vals
        else:
            # Clear user_ids if no job position is selected
            self.user_ids = [(5, 0, 0)]

    @api.onchange('job_level_id')
    def _onchange_job_level_id(self):
        """Auto-populate user_ids based on selected job_level_id"""
        if self.job_level_id:
            # Find all users with this job level
            users_with_level = self.env['res.users'].search([
                ('job_level_id', '=', self.job_level_id.id),
                ('active', '=', True)
            ])

            # Clear existing user_ids and add new ones
            self.user_ids = [(5, 0, 0)]  # Clear all existing records

            # Add users to the One2many field
            user_vals = []
            for user in users_with_level:
                user_vals.append((0, 0, {
                    'user_id': user.id,
                }))

            self.user_ids = user_vals
        else:
            # Clear user_ids if no job level is selected
            self.user_ids = [(5, 0, 0)]

    def action_approve(self):
        """Override approve method to add validation for overlapping user periods"""
        self._check_user_date_overlap()
        return super().action_approve()

    def _check_user_date_overlap(self):
        """
        Check if any user already has an active commission plan
        during the same time period when approving.
        Allow overlap only if broker/ambassador flags differ
        """
        for record in self:
            if not record.user_ids:
                continue

            # Get the plan's date range
            plan_date_from = record.date_from
            plan_date_to = record.date_to
            if not plan_date_from:
                continue

            # Check each user in the commission plan
            for user_line in record.user_ids:
                if not user_line.user_id:
                    continue

                # Search for overlapping approved plans for this user
                overlapping_plan_users = self.env['sale.commission.plan.user'].search([
                    ('user_id', '=', user_line.user_id.id),
                    ('plan_id', '!=', record.id),
                    ('plan_id.state', 'in', ['approved', 'done']),
                    ('plan_id.type', '=', record.type),
                ])

                # Check each overlapping plan user line
                for existing_user_line in overlapping_plan_users:
                    existing_plan = existing_user_line.plan_id
                    existing_date_from = existing_plan.date_from
                    existing_date_to = existing_plan.date_to

                    if not existing_date_from:
                        continue

                    # Check if dates overlap
                    if (plan_date_from <= existing_date_to and plan_date_to >= existing_date_from):
                        # Allow overlap if broker/ambassador flags differ
                        if (record.with_broker != existing_plan.with_broker or
                                record.with_ambassador != existing_plan.with_ambassador):
                            continue

                        # Otherwise, raise validation error
                        raise ValidationError(_(
                            "❌ APPROVAL BLOCKED - Commission Plan Conflict\n\n"
                            "👤 User: %s\n"
                            "📅 Requested Period: %s → %s\n"
                            "⚠️  Conflicts with approved '%s' plan: '%s'\n"
                            "📅 Existing Period: %s → %s\n"
                            "🏢 Broker Flag: Current=%s, Existing=%s\n"
                            "🎖️  Ambassador Flag: Current=%s, Existing=%s\n\n"
                            "✅ Solution: Adjust dates, remove user, or ensure flags differ"
                        ) % (
                                                  user_line.user_id.name,
                                                  plan_date_from,
                                                  plan_date_to,
                                                  dict(existing_plan._fields['type'].selection).get(existing_plan.type),
                                                  existing_plan.name,
                                                  existing_date_from,
                                                  existing_date_to,
                                                  record.with_broker,
                                                  existing_plan.with_broker,
                                                  record.with_ambassador,
                                                  existing_plan.with_ambassador
                                              ))
