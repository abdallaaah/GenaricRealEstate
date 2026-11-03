from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

# developer.project's core definition moved to isky_18_realestate_developer_unit_inventory
# (Level 0). These fields reference project.commission (a Level 3 / Commission & Broker
# concept), so they stay here as an extension until the Commission module phase, at which
# point this file moves there unchanged.


class DeveloperProject(models.Model):
    _inherit = 'developer.project'

    project_commission_ids = fields.One2many('project.commission', 'developer_project_id', string="Project Commissions")
    last_end_date = fields.Date(
        compute='_compute_last_end_date',
        store=True,
    )
    double_commission = fields.Boolean(string='Double Commission')
    half_commission = fields.Boolean(string='Half Commission')

    @api.depends('project_commission_ids.end_date')
    def _compute_last_end_date(self):
        for rec in self:
            valid = rec.project_commission_ids.filtered(lambda l: l.end_date)
            if valid:
                # sort records with real dates
                last_comm = valid.sorted('end_date', reverse=True)[0]
                rec.last_end_date = last_comm.end_date + relativedelta(days=1)
            else:
                rec.last_end_date = False
