import math
from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import http
from odoo.http import request
import io
import xlsxwriter
from ast import literal_eval


_header_format = {'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter'}
_normal_format = {'border': 1, 'align': 'center', 'valign': 'vcenter'}
_money_format = {'num_format': '#,##0.00', 'border': 1, 'align': 'center', 'valign': 'vcenter'}
_date_format = {'num_format': 'dd-mmm-yy', 'border': 1, 'align': 'center', 'valign': 'vcenter'}
_percentage_format = {'num_format': '0.00%', 'border': 1, 'align': 'center', 'valign': 'vcenter'}
class XlsxInstallmentReport(http.Controller):

    @http.route('/unit/excel/report/<string:unit_id>', type='http',  auth='user')
    def download_installment_report(self, unit_id):
        unit_id = literal_eval(unit_id)
        unit = request.env['real.estate.unit'].browse(unit_id)
        total_price_unit = unit.effective_price
        down_payment_pct = unit.effective_down_payment
        installment_years = unit.effective_installment_years
        maintenance_fees = unit.maintenance_fees
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(f'{installment_years} Years - {down_payment_pct * 100}% DP')
        header_format = workbook.add_format(_header_format)
        normal_format = workbook.add_format(_normal_format)
        money_format = workbook.add_format(_money_format)
        date_format = workbook.add_format(_date_format)
        percentage_format = workbook.add_format(_percentage_format)

        # set the column widths
        worksheet.set_column(0, 4, 25)
        # set the first three rows
        unit_basic_info = [
            ["Unit ID:", unit.system_code or '', ''],
            ["Sold Price", total_price_unit, ''],
            ["Maintenance Fees", maintenance_fees, '']
        ]
        # merge_range(first_row, first_col, last_row, last_col, data, format)
        for row, data in enumerate(unit_basic_info):
                worksheet.merge_range(row, 0, row, 2, data[0], header_format)
                if row == 0:
                    worksheet.write(row, 3, data[1], normal_format)
                else:
                    worksheet.write(row, 3, data[1], money_format)
                worksheet.write(row, 4, data[2], normal_format)
        # main Header
        headers=['#', 'Date Of Installment', 'Installment %', 'Unit Installment', 'Maintenance Installment']
        for col_num, header in enumerate(headers):
            worksheet.write(3, col_num, header, header_format)
        # set Date to start form down_payment_date
        down_payment_date = unit.down_payment_date
        dawn_payment_amount = math.ceil(total_price_unit * down_payment_pct)
        total_installment = total_price_unit - dawn_payment_amount

        # first row value
        worksheet.write(4, 0, 'Down Payment', normal_format)
        worksheet.write(4, 1, down_payment_date, date_format)
        worksheet.write(4, 2, down_payment_pct, percentage_format)
        worksheet.write(4, 3, dawn_payment_amount, money_format)
        worksheet.write(4, 4, '', normal_format)

        # the rest of the installments
        total_installment_count = int(installment_years * 12 / 3)
        next_installment_date = down_payment_date + relativedelta(months=3)
        if total_installment_count:
            installment_percentage_per_quarter = (1 - down_payment_pct) / total_installment_count
            installment_amount_per_quarter = math.ceil(total_installment / total_installment_count)
        maintainance_installment_per_year = maintenance_fees / 3
        row_num = 5
        maintenance_installment_count = 0
        for i in range(1, total_installment_count + 1):
            worksheet.write(row_num, 0, f'Installment {i}', normal_format)
            worksheet.write(row_num, 1, next_installment_date, date_format)
            worksheet.write(row_num, 2, installment_percentage_per_quarter, percentage_format)
            worksheet.write(row_num, 3, installment_amount_per_quarter, money_format)
            if (i+1) % 4 == 0  and maintenance_installment_count < 3:
                worksheet.write(row_num, 4, maintainance_installment_per_year, money_format)
                maintenance_installment_count += 1

            else:
                worksheet.write(row_num, 4, '', normal_format)
            next_installment_date += relativedelta(months=3)
            row_num += 1

        # footer
        bold_money_format = workbook.add_format({'num_format': '#,##', 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        worksheet.merge_range(row_num, 0, row_num, 1, 'Total', header_format)
        worksheet.write(row_num, 2, '100.00%', header_format)
        worksheet.write(row_num, 3, total_price_unit, bold_money_format)
        worksheet.write(row_num, 4, maintenance_fees, bold_money_format)

        workbook.close()
        output.seek(0)
        month_abbr = down_payment_date.strftime("%b")
        year_str = down_payment_date.strftime("%Y")
        file_name = f'Clinins -{installment_years} Yrs - {down_payment_pct * 100}%DP - Payment Plan - {month_abbr} {year_str}.xlsx'

        return request.make_response(
            output.getvalue(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="{file_name}"')
            ]
        )


    @http.route('/payment-plan/excel/report/<string:sale_id>', type='http', auth='user')
    def download_payment_plan(self, sale_id):
        # get the model name from the request params
        model_name = request.params.get('model')
        sale_id = literal_eval(sale_id)
        sale_model_id = request.env[model_name].browse(sale_id)
        # installment data
        unit_id = sale_model_id.unit_id.system_code or ''
        maintenance_installment_ids = sale_model_id.maintenance_installment_ids
        unit_installment_ids = sale_model_id.installment_ids
        down_payment = unit_installment_ids.filtered(lambda x: x.name == 'Down Payment')
        total_price_unit = sum(unit_installment_ids.mapped('total_amount'))
        down_payment_pct = (sum(down_payment.mapped('total_amount')) / total_price_unit) if total_price_unit else 0
        maintenance_fees = sum(maintenance_installment_ids.mapped('total_amount'))
        start_unit_installment_date = min((unit_installment_ids.mapped('date'))) if unit_installment_ids else min((maintenance_installment_ids.mapped('date')))
        end_unit_installment_date = max((unit_installment_ids.mapped('date'))) if unit_installment_ids else max((maintenance_installment_ids.mapped('date')))
        installment_years = end_unit_installment_date.year - start_unit_installment_date.year + 1
        # set the output file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(f'{installment_years} Years - {down_payment_pct * 100:.2f}% DP')
        # set the format
        header_format = workbook.add_format(_header_format)
        normal_format = workbook.add_format(_normal_format)
        money_format = workbook.add_format(_money_format)
        date_format = workbook.add_format(_date_format)
        percentage_format = workbook.add_format(_percentage_format)

        # set the column widths
        worksheet.set_column(0, 4, 25)
        # set the first three rows
        unit_basic_info = [
            ["Unit ID:", unit_id, ''],
            ["Sold Price", total_price_unit, ''],
            ["Maintenance Fees", maintenance_fees, '']
        ]
        # merge_range(first_row, first_col, last_row, last_col, data, format)
        for row, data in enumerate(unit_basic_info):
            worksheet.merge_range(row, 0, row, 2, data[0], header_format)
            if row == 0:
                worksheet.write(row, 3, data[1], normal_format)
            else:
                worksheet.write(row, 3, data[1], money_format)
            worksheet.write(row, 4, data[2], normal_format)
        # main Header
        headers = ['#', 'Date Of Installment', 'Installment %', 'Unit Installment', 'Maintenance Installment']
        for col_num, header in enumerate(headers):
            worksheet.write(3, col_num, header, header_format)

        #  installments
        # here we will merge all the installments lines and the maintanace installment lines
        # and will group it by the date
        # to be like this:
        # ( date , installment line instance, maintenance installment line instance)
        # ( 07/01/2026 , installment.lines(1,) , maintenance.installment.lines())
        # ( 07/01/2028 , installment.lines() , maintenance.installment.lines(1,))
        # ( 07/01/2029 , installment.lines(3,) , maintenance.installment.lines(4,))

        installments_by_date = defaultdict(lambda: {
            'unit': request.env['installment.lines'],
            'maintenance': request.env['maintenance.installment.lines'],
        })

        # unit installments
        for inst in unit_installment_ids:
            installments_by_date[inst.date]['unit'] |= inst

        # maintenance installments
        for inst in maintenance_installment_ids:
            installments_by_date[inst.date]['maintenance'] |= inst

        # final structured list
        all_installments = [
            (date, vals['unit'], vals['maintenance'])
            for date, vals in sorted(installments_by_date.items())
        ]


        if len(all_installments):
            row_num = 4
            down_payment_count = 1
            installment_count = 1
            for line in all_installments:
                installment_date = line[0]
                installment_percentage = 0
                installment_amount = 0
                if line[1] and len(line[1]) > 1:
                    installment_amount = sum(line[1].mapped('total_amount'))
                    installment_percentage = installment_amount / total_price_unit
                elif line[1] and len(line[1]) == 1:
                    installment_amount = line[1][0].total_amount
                    installment_percentage = installment_amount / total_price_unit
                if line[1] and len(line[1]) >= 1 and line[1][0].name == 'Down Payment':
                        installment_text = f'Down Payment {down_payment_count}'
                        down_payment_count += 1
                else:
                    installment_text = f'Installment {installment_count}'
                    installment_count += 1
                worksheet.write(row_num, 0, installment_text, normal_format)
                worksheet.write(row_num, 1, installment_date, date_format)
                worksheet.write(row_num, 2, installment_percentage, percentage_format)
                worksheet.write(row_num, 3, installment_amount, money_format)
                if line[2] and len(line[2]) == 1:
                    maintenance_installment_amount = line[2][0].total_amount
                    worksheet.write(row_num, 4, maintenance_installment_amount, money_format)

                else:
                    worksheet.write(row_num, 4, '', normal_format)
                row_num += 1

        # footer
        bold_money_format = workbook.add_format(
            {'num_format': '#,##', 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        worksheet.merge_range(row_num, 0, row_num, 1, 'Total', header_format)
        worksheet.write(row_num, 2, '100.00%', header_format)
        worksheet.write(row_num, 3, total_price_unit, bold_money_format)
        worksheet.write(row_num, 4, maintenance_fees, bold_money_format)

        workbook.close()
        output.seek(0)
        month_abbr = start_unit_installment_date.strftime("%b")
        year_str = start_unit_installment_date.strftime("%Y")
        file_name = f'Clinins -{installment_years} Yrs - {down_payment_pct * 100:.2f}%DP - Payment Plan - {month_abbr} {year_str}.xlsx'

        return request.make_response(
            output.getvalue(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="{file_name}"')
            ]
        )