from odoo import models, fields, api

class PersonCommission(models.Model):

    # DEPRECATED (Phase 4, D1). Superseded by realestate.commission in
    # isky_18_realestate_developer_commission, which carries all four document FKs. Nothing
    # reads or writes this model any more: crm.lead.commission_ids was its only user and now
    # points at the L3 model.
    #
    # Kept defined rather than deleted for one reason: the legacy
    # arkzayed_18_realestate_developer_crm/security/ir.model.access.csv references
    # model_commission_commission, and the legacy-edit authorisation of 2026-11-06 covers
    # view and menu records only, not ACLs. Deleting the model would break that module's
    # install. Remove both together when the monolith security files can be touched.
    # Backlog #43.
    _name = "commission.commission"

    opportunity_id = fields.Many2one('crm.lead')
    employee_id = fields.Many2one('res.users')
    jop_position = fields.Char()
    job_level_id = fields.Many2one(related='employee_id.job_level_id')
    commission = fields.Float(default=1)
    is_tcr_sales_person = fields.Boolean(string="Is Sales person", compute='_compute_is_sales_person', store=True)

    @api.depends('employee_id', 'opportunity_id', 'opportunity_id.user_id', 'opportunity_id.sales_ids')
    def _compute_is_sales_person(self):
        """Check if the employee is a sales person for this opportunity."""
        for rec in self:
            is_sales = False
            if rec.opportunity_id and rec.employee_id:
                if rec.opportunity_id.user_id and rec.opportunity_id.user_id.id == rec.employee_id.id:
                    is_sales = True
                elif rec.opportunity_id.sales_ids and rec.employee_id in rec.opportunity_id.sales_ids:
                    is_sales = True
            rec.is_tcr_sales_person = is_sales
