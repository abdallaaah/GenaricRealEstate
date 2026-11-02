from odoo import models, fields, api, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    employee_code = fields.Char(string='Employee Code')
    custody_ids = fields.One2many('employee.custody', 'employee_id', string='Custodies')
    address_home_id = fields.Many2one(
        'res.partner', 'Address',
        help='Enter here the private address of the employee, not the one linked to your company.',
        groups="", tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
