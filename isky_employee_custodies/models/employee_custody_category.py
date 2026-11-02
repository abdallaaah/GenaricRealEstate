from odoo import models, fields, api


class EmployeeCustodyCategory(models.Model):
    _name = 'employee.custody.category'
    _description = 'Employee Custody Category'

    name = fields.Char(string='Custody Category Name', required=True)
    custody_description = fields.Text(string='Description', required=True)
    fixed = fields.Boolean(string='Fixed')
