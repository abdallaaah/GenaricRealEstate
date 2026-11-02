import io
import json
from datetime import date

import xlsxwriter

from odoo import http
from odoo.http import content_disposition, request

from ..models.engineer_inventory import COLUMNS, KIND_DOMAIN, SHEET_NAME

MONEY = {'unit_price', 'price_per_meter', 'sold_price', 'down_payment', 'maintenance', 'commission_paid', 'm2_price'}
AREAS = {'net_area', 'gross_area', 'indoor_net_area', 'indoor_gross_area', 'outdoor_gross_area', 'garden_area', 'land_area'}
PERCENT = {'discount_percentage', 'dp_percentage', 'maintenance_percentage'}


class EngineerMenuExport(http.Controller):

    @http.route('/ark_engineer_menu/export', type='http', auth='user', methods=['POST'], csrf=True)
    def export(self, kind='residential', domain='[]', **kw):
        if kind not in COLUMNS:
            kind = 'residential'
        Inventory = request.env['ark.engineer.inventory']
        domain = json.loads(domain or '[]') + KIND_DOMAIN[kind]
        columns = COLUMNS[kind]
        names = [f for f, _ in columns]
        rows = Inventory.search_read(domain, names)
        labels = {f: dict(Inventory._fields[f]._description_selection(request.env)) for f in names if Inventory._fields[f].type == 'selection'}

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True, 'default_date_format': 'dd/mm/yyyy'})
        ws = wb.add_worksheet(SHEET_NAME[kind])
        base = {'font_name': 'Arial', 'font_size': 10}
        head = wb.add_format(dict(base, bold=True, bg_color='#0F2A4A', font_color='white', border=1, text_wrap=True, align='center', valign='vcenter'))
        text = wb.add_format(dict(base, border=1))
        num = wb.add_format(dict(base, border=1, num_format='#,##0.00'))
        pct = wb.add_format(dict(base, border=1, num_format='0.00'))
        dat = wb.add_format(dict(base, border=1, num_format='dd/mm/yyyy', align='left'))
        ws.set_row(0, 30)
        for c, (f, header) in enumerate(columns):
            ws.write(0, c, header, head)
            ws.set_column(c, c, 14 if f in MONEY | AREAS | PERCENT else 24 if f in ('client_name', 'client_arabic_name', 'address', 'sales', 'sales_manager', 'sales_director', 'brokerage', 'agent_name', 'payment_plan') else 16)
        for r, row in enumerate(rows, 1):
            for c, (f, _h) in enumerate(columns):
                v = row[f]
                if v is False or v is None:
                    ws.write_blank(r, c, None, text)
                elif f in labels:
                    ws.write(r, c, labels[f].get(v, v), text)
                elif f in MONEY or f in AREAS:
                    ws.write_number(r, c, v, num)
                elif f in PERCENT:
                    ws.write_number(r, c, v, pct)
                elif isinstance(v, date):
                    ws.write_datetime(r, c, v, dat)
                else:
                    ws.write(r, c, v, text)
        ws.freeze_panes(1, 2)
        ws.autofilter(0, 0, max(len(rows), 1), len(columns) - 1)
        wb.close()
        filename = 'Engineer_Menu_%s_%s.xlsx' % (SHEET_NAME[kind].replace(' ', '_').replace('&', 'and'), date.today().strftime('%d-%m-%Y'))
        return request.make_response(buf.getvalue(), headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(filename)),
        ])
