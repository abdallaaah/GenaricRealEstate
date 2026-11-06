from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..selections import unit_type_selection

class DownPaymentIncrease(models.Model):
    _name = 'down.payment.increase'
    _description = 'Down Payment Increase'

    name = fields.Char(required=True)
    unit_type = fields.Selection(selection=unit_type_selection, string='Unit Type', required=True)

    price_plan_ids = fields.One2many('price.plan.line', 'down_payment_id', string="Price Plans")


    @api.constrains( 'unit_type')
    def check_years(self):
        for rec in self:
            duplicated_plan = self.env['down.payment.increase'].search([('unit_type', '=', rec.unit_type),
                                                                        ('id', '!=', rec.id)])
            if duplicated_plan:
                raise ValidationError(
                    f"There is another plan called {duplicated_plan.name} has the same unit type."
                )
