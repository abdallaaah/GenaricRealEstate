# -*- coding: utf-8 -*-
from odoo import models, fields


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    input_line_ids = fields.One2many(
        'hr.payslip.run.input', 'payslip_run_id',
        string='Other Inputs',
        help="Inputs defined at the batch level. When the batch payslips are "
             "generated, every payslip receives a copy of these inputs in its "
             "'Other Inputs' tab.")


class HrPayslipRunInput(models.Model):
    _name = 'hr.payslip.run.input'
    _description = 'Payslip Batch Input'
    _order = 'payslip_run_id, sequence, id'

    payslip_run_id = fields.Many2one(
        'hr.payslip.run', string='Batch', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(required=True, index=True, default=10)
    input_type_id = fields.Many2one(
        'hr.payslip.input.type', string='Type', required=True)
    code = fields.Char(related='input_type_id.code', readonly=True)
    name = fields.Char(string='Description')
    amount = fields.Float(
        string='Count', digits='Payroll Rate',
        help="Count/amount used in the salary rule computation. It is copied "
             "to every payslip generated in this batch.")
