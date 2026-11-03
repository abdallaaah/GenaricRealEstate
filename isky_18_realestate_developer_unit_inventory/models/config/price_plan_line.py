from odoo import models, fields, api
from odoo.exceptions import ValidationError

class PricePlanLine(models.Model):
    _name ='price.plan.line'
    _order = 'year_no'

    year_no = fields.Integer(string="Year number")
    down_payment = fields.Float('Down Payment (%)')
    percentage_increase = fields.Float(
        string='Percentage Increase (%)',
        required=True,
        help="Percentage to increase the unit price"
    )
    down_payment_id = fields.Many2one(
        'down.payment.increase',
        string="Down Payment Plan"
    )
    @api.constrains('down_payment_id', 'year_no')
    def check_duplicated_plan(self):
        for rec in self:
            duplicated_plan = self.env['price.plan.line'].search([('year_no', '=', rec.year_no), ('down_payment_id', '=', rec.down_payment_id.id),
                                                                  ('id', '!=', rec.id)])
            if duplicated_plan:
                raise ValidationError(
                    f"There is another plan with the same Year number")