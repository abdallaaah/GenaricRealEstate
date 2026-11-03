from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CommissionCategory(models.Model):
    _name = "commission.category"
    _description = "Non-Sales Commission Category"

    name = fields.Char(required=True)
    percentage = fields.Float(
        string='% of Base Commission',
        default=0.0,
        help="Share of the company's non-sales commission rate (Settings > Non-Sales "
             "Commission) that employees in this category receive."
    )
    employee_ids = fields.One2many('hr.employee', 'commission_category_id', string='Employees')
    employee_count = fields.Integer(compute='_compute_employee_count')

    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for rec in self:
            rec.employee_count = len(rec.employee_ids)

    @api.constrains('percentage')
    def _check_total_percentage(self):
        total = sum(self.search([]).mapped('percentage'))
        if total > 100:
            raise ValidationError(_(
                "The total commission percentage across all categories (%.2f%%) cannot "
                "exceed 100%%. Please lower one or more categories' percentages."
            ) % total)

    def action_view_employees(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Employees'),
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('commission_category_id', '=', self.id)],
        }
