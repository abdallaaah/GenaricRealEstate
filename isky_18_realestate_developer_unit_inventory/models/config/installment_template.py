from odoo import api, fields, models


class InstallmentTemplate(models.Model):
    _name = "installment.template"
    _description = "Installment Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("Name", size=64, required=True)
    arabic_name = fields.Char()
    project_ids = fields.Many2many('realestate.project')
    phase_id = fields.Many2one('real.estate.project.phase', string='Phase',
                               domain="[('project_id', 'in', project_ids)]")
    monthly_installment_amount = fields.Float()
    monthly_installment_duration = fields.Integer()
    quarterly_installment_amount = fields.Float()
    quarterly_installment_duration = fields.Integer()
    semi_annual_installment_amount = fields.Float()
    semi_annual_installment_duration = fields.Integer()
    annual_installment_amount = fields.Float()
    annual_installment_duration = fields.Integer()
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    reservation_percentage = fields.Float("Down Payment Percentage")
    contracting_percentage = fields.Float("Down Payment 2 Percentage")
    number_of_years = fields.Integer("Number of Years")
