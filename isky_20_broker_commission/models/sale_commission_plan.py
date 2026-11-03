from odoo import api, fields, models


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
