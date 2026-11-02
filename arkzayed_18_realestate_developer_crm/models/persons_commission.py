from odoo import models, fields, api

class PersonCommission(models.Model):

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
