from odoo import api, fields, models


class CommissionCommission(models.Model):
    """One row per (opportunity, hierarchy member) produced by
    crm.lead.compute_person_hierarchy(). Stays in the CRM module, not the
    commission module, so the commission module can depend on CRM without a
    circular dependency back.
    """
    _name = 'commission.commission'
    _description = "Opportunity Commission Hierarchy Line"

    opportunity_id = fields.Many2one('crm.lead', required=True, ondelete='cascade')
    employee_id = fields.Many2one('res.users', required=True, string="Person")
    job_level_id = fields.Many2one(related='employee_id.job_level_id')
    commission = fields.Float(default=1, help="Share of the commission attributed to this person.")
    is_tcr_sales_person = fields.Boolean(
        string="Is Deal Closer", compute='_compute_is_tcr_sales_person', store=True,
        help="True if this person is the opportunity's own salesperson or a split-deal participant, "
             "as opposed to a hierarchy beneficiary (team leader/manager/director).")

    @api.depends('employee_id', 'opportunity_id.user_id', 'opportunity_id.sales_ids')
    def _compute_is_tcr_sales_person(self):
        for line in self:
            line.is_tcr_sales_person = bool(line.employee_id) and (
                line.employee_id == line.opportunity_id.user_id
                or line.employee_id in line.opportunity_id.sales_ids
            )
