#	-*-	coding:	utf-8	-*-
from odoo import models, fields, api


class EmployeeCustodyItem(models.Model):
    _name = 'employee.custody.item'
    _description = 'Employee Custody Item'

    employee_custody_id = fields.Many2one('employee.custody', string='Custody')
    name = fields.Char(related='employee_custody_id.name', readonly=True)
    employee_custody_category_id = fields.Many2one('employee.custody.category',
                                                   related='employee_custody_id.employee_custody_category_id',
                                                   readonly=True)
    open_balance = fields.Monetary(related='employee_custody_id.open_balance', readonly=True)
    close_balance = fields.Monetary(related='employee_custody_id.close_balance', readonly=True)
    total_transactions = fields.Monetary(related='employee_custody_id.total_transactions', readonly=True)
    state = fields.Selection(related='employee_custody_id.state', readonly=True)
    employee_id = fields.Many2one('hr.employee', related='employee_custody_id.employee_id', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='employee_custody_id.currency_id')
