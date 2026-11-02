from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    commission_category_id = fields.Many2one(
        'commission.category',
        string='Commission Category',
        help="Determines the employee's share of the company-wide non-sales commission rate."
    )
    sales_reservation_signature = fields.Boolean(
        string='Sales Reservation Signature',
        help="Only one employee can have this flag. Their name is printed in the company section of the reservation report." ,
        copy=False
    )

    @api.constrains('sales_reservation_signature')
    def _check_single_sales_reservation_signature(self):
        flagged = self.filtered('sales_reservation_signature')
        if not flagged:
            return
        count = self.with_context(active_test=False).search_count(
            [('sales_reservation_signature', '=', True)]
        )
        if count > 1:
            raise ValidationError(_("Only one employee can be set as Sales Reservation Signature."))
