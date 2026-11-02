# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
import datetime
import io

from odoo.tools import date_utils

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


class EmployeeCustodyReport(models.AbstractModel):
    _name = 'report.isky_employee_custodies.all_custody_view_id'

    def _open_balance(self, employee_id, currency_id):
        open_balance_total = 0
        close_balance_total = 0
        total_transactions_sum = 0
        total_list = []
        custody_obj = self.env['employee.custody'].search(
            [('employee_id', '=', employee_id), ('currency_id', '=', currency_id)])
        for each_custody in custody_obj:
            open_balance_total += each_custody.open_balance
            close_balance_total += each_custody.close_balance
            total_transactions_sum += each_custody.total_transactions
        total_list.append(open_balance_total)
        total_list.append(close_balance_total)
        total_list.append(total_transactions_sum)
        return total_list

    def _get_currency(self, employee_id):
        currency_ids = []
        return_values = []
        currency = self.env['employee.custody'].search([('employee_id', '=', employee_id)])
        for each_currency in currency:
            if each_currency.currency_id not in currency_ids:
                currency_ids.append(each_currency.currency_id)
        for each_cur in currency_ids:
            open_balance_total = 0
            close_balance_total = 0
            total_transactions_sum = 0
            each_line = []
            emp_name = ''
            for each_rec in self.env['employee.custody'].search(
                    [('employee_id', '=', employee_id), ('currency_id', '=', each_cur.id)]):
                open_balance_total += each_rec.open_balance
                close_balance_total += each_rec.close_balance
                total_transactions_sum += each_rec.total_transactions
                emp_name = each_rec.employee_id.display_name
            each_line.append(emp_name)
            each_line.append(open_balance_total)
            each_line.append(close_balance_total)
            each_line.append(total_transactions_sum)
            each_line.append(each_cur.display_name)
            return_values.append(each_line)
        return return_values

    def render_html(self, docids, data=None):
        docs = self.env['employee.custody'].browse(data['ids'])
        employee_ids = []
        for doc in docs:
            if doc.employee_id.id not in employee_ids:
                employee_ids.append(doc.employee_id.id)
        docs = self.env['hr.employee'].browse(employee_ids)
        records = {
            'open_balance': self._open_balance,
            'doc_ids': data['ids'],
            'doc_model': 'employee.custody',
            'docs': docs,
            'currency': self._get_currency
        }
        return self.env['report'].render('isky_employee_custodies.all_custody_view_id', records)


class EmployeeCustodyReport(models.TransientModel):
    _name = "employee.custody.report"
    _description = 'Employee Custody Report'

    employee_id = fields.Many2one('hr.employee', string='Sales Person')
    from_date = fields.Date(string='From Date')
    to_date = fields.Date(string='To Date')
    employee_custody_category_id = fields.Many2one('employee.custody.category', string='Custody Category')

    def display_data(self):
        domain = []
        view_id = self.env.ref('isky_employee_custodies.view_employee_custody_tree_report').id
        ctx = dict(self._context, )
        for val in self:
            if val.from_date and val.to_date:
                if val.to_date <= val.from_date:
                    raise ValidationError("Date to must be greater than Date from !! ")
            domain = []
            if val.employee_id:
                domain += [('employee_id', '=', self.employee_id.id)]
            if val.from_date:
                domain += [('custody_date', '>=', self.from_date)]
            if val.to_date:
                domain += [('custody_date', '<=', self.to_date)]
            if val.employee_custody_category_id:
                domain += [('employee_custody_category_id', '=', self.employee_custody_category_id.id)]

        return {
            'domain': domain,
            'name': _('Employees Custody Report'),
            # 'view_type': 'form',
            'view_mode': 'list',
            'res_model': 'employee.custody',
            'type': 'ir.actions.act_window',
            'view_id': view_id,
            'context': ctx,
        }

    def get_data(self, date_from, date_to):
        for val in self:
            if val.from_date and val.to_date:
                if val.to_date <= val.from_date:
                    raise ValidationError("Date to must be greater than Date from !! ")
            domain = []
            if val.employee_id:
                domain += [('employee_id', '=', val.employee_id.id)]
            if val.from_date:
                domain += [('custody_date', '>=', val.from_date)]
            if val.to_date:
                domain += [('custody_date', '<=', val.to_date)]
            if val.employee_custody_category_id:
                domain += [('employee_custody_category_id', '=', val.employee_custody_category_id.id)]
            data = {}
            res = []
            emp_custodies = self.env['employee.custody'].search(domain)
            currencies = []
            for custody in emp_custodies:
                if custody.currency_id.id not in currencies:
                    currencies.append(custody.currency_id.id)
            for currency in currencies:
                if val.employee_id:
                    emp_objects = self.env['employee.custody'].search(
                        [('employee_id', '=', val.employee_id.id), ('currency_id', '=', currency)])
                    for object in emp_objects:
                        res.append({'employee': object.employee_id.name,
                                    'debit': object.open_balance,
                                    'credit': object.close_balance,
                                    'balance': object.total_transactions,
                                    'currency': object.currency_id.name})
                data['data'] = res
            return data

    def print_pdf_data(self):
        for val in self:
            res = val.get_data(val.from_date, val.to_date)
            return self.env.ref('isky_employee_custodies.all_employee_custody_report_id').report_action(self, data=res)

    # def print_data_xlsx(self):
    #     self.ensure_one
    #     res = self.get_data(self.from_date, self.to_date)
    #     data = self.read()[0]
    #     datas = {
    #         'ids': [],
    #         'model': 'employee.custody',
    #         'form': data,
    #         'data': res
    #     }
    #     return self.env['ir.actions.report'].search(
    #         [('report_name', '=', 'isky_employee_custodies.employee_custody_xls'),
    #          ('report_type', '=', 'xlsx')],
    #         limit=1).report_action(self, data=datas)

    def export_xls(self):
        data = {
            'ids': self.ids,
            'model': self._name,
            'data': self.get_data(self.from_date, self.to_date),

        }
        return {
            'type': 'ir.actions.report',
            'data': {'model': 'employee.custody.report',
                     'options': json.dumps(data, default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'custody Report',
                     },
            'report_type': 'report_xlsx'
        }

    def get_xlsx_report(self, data, response):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Employee Custody Report")
        f1 = workbook.add_format({'bold': True, 'font_color': '#000000', 'border': True, 'align': 'vcenter'})
        worksheet.write(6, 2, 'Employee', f1)
        worksheet.write(6, 3, ' Debit', f1)
        worksheet.write(6, 4, 'Credit', f1)
        worksheet.write(6, 5, 'Balance', f1)
        worksheet.write(6, 6, 'Currency', f1)

        line_num = 7
        print(data['data'])
        if data['data']:
            for obj in data['data']['data']:
                worksheet.write(line_num, 2, obj['employee'], f1)
                worksheet.write(line_num, 3, obj['debit'], f1)
                worksheet.write(line_num, 4, obj['credit'], f1)
                worksheet.write(line_num, 5, obj['balance'], f1)
                worksheet.write(line_num, 6, obj['currency'], f1)
                line_num += 1

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
