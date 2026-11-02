# -*- coding: utf-8 -*-
from odoo import models


class EmployeeCustodyXls(models.AbstractModel):
    _name = 'report.isky_employee_custodies.employee_custody_xls'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, wizard_data):
        worksheet = workbook.add_worksheet("Employee Custody Report")
        f1 = workbook.add_format({'bold': True, 'font_color': '#000000', 'border': True, 'align': 'vcenter'})
        worksheet.write(6, 2, 'Employee', f1)
        worksheet.write(6, 3, ' Debit', f1)
        worksheet.write(6, 4, 'Credit', f1)
        worksheet.write(6, 5, 'Balance', f1)
        worksheet.write(6, 6, 'Currency', f1)

        line_num = 7
        if data['data']:
            for obj in data['data']['data']:
                worksheet.write(line_num, 2, obj['employee'], f1)
                worksheet.write(line_num, 3, obj['debit'], f1)
                worksheet.write(line_num, 4, obj['credit'], f1)
                worksheet.write(line_num, 5, obj['balance'], f1)
                worksheet.write(line_num, 6, obj['currency'], f1)
                line_num += 1
