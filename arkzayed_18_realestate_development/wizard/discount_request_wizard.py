from odoo import models, fields, api


class DiscountRequestWizard(models.TransientModel):
    _name = 'discount.request.wizard'
    _description = 'Discount Request Wizard'

    unit_id = fields.Many2one(
        'real.estate.unit',
        string='Unit',
        required=True,
        readonly=True
    )

    down_payment = fields.Float(
        string='Down Payment',
        required=True,
    )
    installment_years = fields.Integer(string='Installment Years', required=True)
    total_price_unit = fields.Float(string='Total Price', required=True)

    def action_confirm(self):
        self.ensure_one()
        discount_request = self.env['discount.request'].create({
            'unit_id': self.unit_id.id,
            'down_payment': self.down_payment,
            'installment_years': self.installment_years,
            'total_price_unit': self.total_price_unit,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Discount Request',
            'res_model': 'discount.request',
            'res_id': discount_request.id,
            'view_mode': 'form',
            'target': 'current',
        }
