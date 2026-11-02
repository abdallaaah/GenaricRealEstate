
from odoo import fields, models


class InstallmentTemplate(models.Model):
    _name = "maintenance.template"
    _description = "Maintenance Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("Name", size=64, required=True)
    percentage = fields.Float("Percentage", help="Maintenance percentage applied on the unit total price.")
    project_ids = fields.Many2many('realestate.project')
    monthly_installment_amount = fields.Float()
    monthly_installment_duration = fields.Integer()
    quarterly_installment_amount = fields.Float()
    quarterly_installment_duration = fields.Integer()
    semi_annual_installment_amount = fields.Float()
    semi_annual_installment_duration = fields.Integer()
    annual_installment_amount = fields.Float()
    annual_installment_duration = fields.Integer()
    type = fields.Selection([('maintenance', 'Maintenance'), ('parking', 'Parking')], default='maintenance')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    default_for_reservation = fields.Boolean("Default For Reservation")



