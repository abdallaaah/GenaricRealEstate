from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    npv_discount_rate = fields.Float(
        string='NPV Discount Rate %', default=20.0,
        help="Annual discount rate used to compute the present value (NPV) of contract installment "
             "schedules, and by the standalone NPV Calculator. Set by management/finance only; sales "
             "staff can see it but not change it.")
