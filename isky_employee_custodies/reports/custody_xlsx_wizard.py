# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


CUSTODY_STATE_SELECTION = [
    ('draft', 'New'),
    ('open', 'Open'),
    ('receiving_custody', 'Receiving Custody'),
    ('pay', 'Payment'),
    ('done', 'Closed'),
    ('cancel', 'Cancelled'),
]

CUSTODY_TYPE_SELECTION = [
    ('temporary', 'Temporary'),
    ('permanent', 'Permanent'),
]

STATE_AR_LABEL = {
    'draft': 'جديدة',
    'open': 'مفتوحة',
    'receiving_custody': 'استلام عهدة',
    'pay': 'دفع',
    'done': 'مغلقة',
    'cancel': 'ملغاة',
}

TYPE_AR_LABEL = {
    'temporary': 'مؤقته',
    'permanent': 'مستديمه',
}


class CustodyXlsxReportWizard(models.TransientModel):
    _name = 'custody.xlsx.report.wizard'
    _description = 'Custody XLSX Report Wizard'

    date_from = fields.Date(
        string='From Date', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string='To Date', required=True,
        default=fields.Date.context_today,
    )
    employee_id = fields.Many2one('hr.employee', string='Employee')
    state = fields.Selection(CUSTODY_STATE_SELECTION, string='Status')
    custody_type = fields.Selection(CUSTODY_TYPE_SELECTION, string='Custody Type')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_('"From Date" must be earlier than or equal to "To Date".'))

    def _build_domain(self):
        self.ensure_one()
        domain = [
            ('custody_date', '>=', self.date_from),
            ('custody_date', '<=', self.date_to),
        ]
        if self.employee_id:
            domain.append(('employee_id', '=', self.employee_id.id))
        if self.state:
            domain.append(('state', '=', self.state))
        if self.custody_type:
            domain.append(('custody_type', '=', self.custody_type))
        return domain

    def action_print_xlsx(self):
        self.ensure_one()
        return self.env.ref(
            'isky_employee_custodies.action_custody_xlsx_report'
        ).report_action(self)


class CustodyXlsxReport(models.AbstractModel):
    _name = 'report.isky_employee_custodies.custody_xlsx_template'
    _description = 'Custody XLSX Report Template'
    _inherit = 'report.report_xlsx.abstract'

    # ----- styling palette -----
    NAVY = '#1F3864'
    NAVY_LIGHT = '#2E5597'
    GOLD = '#C9A227'
    HEADER_BG = '#D9E1F2'
    BAND_BG = '#F2F2F2'
    TOTAL_BG = '#FFF2CC'
    GRAND_TOTAL_BG = '#FCE4D6'
    BORDER = '#7F7F7F'

    STATE_COLORS = {
        'draft': '#BDD7EE',
        'open': '#9DC3E6',
        'receiving_custody': '#A9D08E',
        'pay': '#FFD966',
        'done': '#C6E0B4',
        'cancel': '#F4B084',
    }

    def _formats(self, workbook):
        f = {}
        f['title'] = workbook.add_format({
            'bold': True, 'font_size': 20, 'font_color': 'white',
            'bg_color': self.NAVY, 'align': 'center', 'valign': 'vcenter',
            'font_name': 'Arial',
        })
        f['subtitle'] = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_color': self.NAVY,
            'align': 'center', 'valign': 'vcenter', 'italic': True,
            'font_name': 'Arial',
        })
        f['filter_label'] = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_color': 'white',
            'bg_color': self.NAVY_LIGHT, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER, 'font_name': 'Arial',
        })
        f['filter_value'] = workbook.add_format({
            'font_size': 10, 'bg_color': 'white',
            'align': 'center', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER, 'font_name': 'Arial',
        })
        f['emp_section'] = workbook.add_format({
            'bold': True, 'font_size': 12, 'font_color': 'white',
            'bg_color': self.NAVY, 'align': 'right', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER,
            'indent': 1, 'font_name': 'Arial',
        })
        f['col_header'] = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_color': self.NAVY,
            'bg_color': self.HEADER_BG, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER, 'text_wrap': True,
            'font_name': 'Arial',
        })
        f['cell'] = workbook.add_format({
            'font_size': 10, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER, 'text_wrap': True,
            'font_name': 'Arial',
        })
        f['cell_band'] = workbook.add_format({
            'font_size': 10, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER, 'text_wrap': True,
            'bg_color': self.BAND_BG, 'font_name': 'Arial',
        })
        f['cell_reason'] = workbook.add_format({
            'font_size': 10, 'align': 'right', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER, 'text_wrap': True,
            'indent': 1, 'font_name': 'Arial',
        })
        f['cell_reason_band'] = workbook.add_format({
            'font_size': 10, 'align': 'right', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER, 'text_wrap': True,
            'indent': 1, 'bg_color': self.BAND_BG, 'font_name': 'Arial',
        })
        f['amount'] = workbook.add_format({
            'font_size': 10, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER,
            'num_format': '#,##0.00', 'font_name': 'Arial',
        })
        f['amount_band'] = workbook.add_format({
            'font_size': 10, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER, 'bg_color': self.BAND_BG,
            'num_format': '#,##0.00', 'font_name': 'Arial',
        })
        f['date'] = workbook.add_format({
            'font_size': 10, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER,
            'num_format': 'yyyy-mm-dd', 'font_name': 'Arial',
        })
        f['date_band'] = workbook.add_format({
            'font_size': 10, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER, 'bg_color': self.BAND_BG,
            'num_format': 'yyyy-mm-dd', 'font_name': 'Arial',
        })
        f['total_label'] = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_color': self.NAVY,
            'bg_color': self.TOTAL_BG, 'align': 'right', 'valign': 'vcenter',
            'border': 2, 'border_color': self.NAVY, 'indent': 1,
            'font_name': 'Arial',
        })
        f['total_amount'] = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_color': self.NAVY,
            'bg_color': self.TOTAL_BG, 'align': 'center', 'valign': 'vcenter',
            'border': 2, 'border_color': self.NAVY,
            'num_format': '#,##0.00', 'font_name': 'Arial',
        })
        f['total_blank'] = workbook.add_format({
            'bg_color': self.TOTAL_BG, 'border': 2, 'border_color': self.NAVY,
        })
        f['grand_label'] = workbook.add_format({
            'bold': True, 'font_size': 12, 'font_color': 'white',
            'bg_color': self.NAVY, 'align': 'right', 'valign': 'vcenter',
            'border': 2, 'border_color': self.NAVY, 'indent': 1,
            'font_name': 'Arial',
        })
        f['grand_amount'] = workbook.add_format({
            'bold': True, 'font_size': 12, 'font_color': self.NAVY,
            'bg_color': self.GRAND_TOTAL_BG, 'align': 'center', 'valign': 'vcenter',
            'border': 2, 'border_color': self.NAVY,
            'num_format': '#,##0.00', 'font_name': 'Arial',
        })
        f['grand_blank'] = workbook.add_format({
            'bg_color': self.GRAND_TOTAL_BG, 'border': 2, 'border_color': self.NAVY,
        })
        return f

    # state cell with colored badge
    def _state_format(self, workbook, state, banded):
        bg = self.STATE_COLORS.get(state, self.BAND_BG if banded else 'white')
        return workbook.add_format({
            'bold': True, 'font_size': 10, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'border_color': self.BORDER, 'bg_color': bg,
            'font_name': 'Arial',
        })

    def generate_xlsx_report(self, workbook, data, wizard):
        ws = workbook.add_worksheet('العهد')
        ws.right_to_left()
        ws.hide_gridlines(2)

        # column widths (A..I)
        widths = [18, 12, 50, 14, 14, 24, 14, 14, 14]
        for idx, w in enumerate(widths):
            ws.set_column(idx, idx, w)

        f = self._formats(workbook)
        company = wizard.env.company

        # ---------- title bar ----------
        ws.set_row(0, 32)
        ws.merge_range(0, 0, 0, 8, 'تقرير العهد', f['title'])
        ws.set_row(1, 18)
        ws.merge_range(1, 0, 1, 8, company.name or '', f['subtitle'])

        # ---------- filters strip ----------
        ws.set_row(3, 22)
        # date range: label / value / label / value spanning the row
        ws.merge_range(3, 0, 3, 1, 'من تاريخ', f['filter_label'])
        ws.merge_range(3, 2, 3, 3, wizard.date_from.strftime('%Y-%m-%d'), f['filter_value'])
        ws.merge_range(3, 4, 3, 5, 'إلى تاريخ', f['filter_label'])
        ws.merge_range(3, 6, 3, 8, wizard.date_to.strftime('%Y-%m-%d'), f['filter_value'])

        ws.set_row(4, 22)
        ws.merge_range(4, 0, 4, 1, 'الموظف', f['filter_label'])
        ws.merge_range(4, 2, 4, 3, wizard.employee_id.name or 'الكل', f['filter_value'])
        ws.merge_range(4, 4, 4, 4, 'النوع', f['filter_label'])
        ws.merge_range(4, 5, 4, 5, TYPE_AR_LABEL.get(wizard.custody_type, 'الكل'), f['filter_value'])
        ws.merge_range(4, 6, 4, 7, 'الحالة', f['filter_label'])
        ws.write(4, 8, STATE_AR_LABEL.get(wizard.state, 'الكل'), f['filter_value'])

        # column header row
        headers = [
            'الكود', 'النوع', 'السبب', 'المبلغ', 'المبلغ المتبقي',
            'دفتر اليومية', 'تاريخ الطلب', 'تاريخ الاسترجاع', 'الحالة',
        ]

        # ---------- data ----------
        custodies = wizard.env['employee.custody'].search(
            wizard._build_domain(), order='employee_id, custody_date'
        )

        # group by employee, preserving order
        groups = {}
        for c in custodies:
            emp = c.employee_id
            if emp not in groups:
                groups[emp] = wizard.env['employee.custody']
            groups[emp] |= c

        row = 6
        grand_amount = 0.0
        grand_remaining = 0.0

        if not custodies:
            ws.set_row(row, 28)
            empty_fmt = workbook.add_format({
                'italic': True, 'font_size': 11, 'font_color': self.NAVY,
                'align': 'center', 'valign': 'vcenter',
                'border': 1, 'border_color': self.BORDER,
                'bg_color': self.BAND_BG, 'font_name': 'Arial',
            })
            ws.merge_range(row, 0, row, 8, 'لا توجد بيانات تطابق معايير البحث.', empty_fmt)
            row += 1
        else:
            for employee, emp_custodies in groups.items():
                # employee section header
                ws.set_row(row, 24)
                ws.merge_range(row, 0, row, 8,
                               'الموظف: %s' % (employee.name or '-'),
                               f['emp_section'])
                row += 1

                # column headers
                ws.set_row(row, 26)
                for col, h in enumerate(headers):
                    ws.write(row, col, h, f['col_header'])
                row += 1

                emp_amount = 0.0
                emp_remaining = 0.0
                for i, c in enumerate(emp_custodies):
                    banded = (i % 2 == 1)
                    cell = f['cell_band'] if banded else f['cell']
                    reason = f['cell_reason_band'] if banded else f['cell_reason']
                    amt = f['amount_band'] if banded else f['amount']
                    dt = f['date_band'] if banded else f['date']
                    state_fmt = self._state_format(workbook, c.state, banded)

                    ws.set_row(row, 22)
                    ws.write(row, 0, c.name or '', cell)
                    ws.write(row, 1, TYPE_AR_LABEL.get(c.custody_type, ''), cell)
                    ws.write(row, 2, c.description or '', reason)
                    ws.write(row, 3, c.actual_open_balance or 0.0, amt)
                    ws.write(row, 4, c.close_balance or 0.0, amt)
                    ws.write(row, 5, c.payment_method_id.name or '', cell)
                    ws.write_datetime(row, 6, c.custody_date, dt) if c.custody_date else ws.write(row, 6, '', cell)
                    ws.write_datetime(row, 7, c.custody_close_date, dt) if c.custody_close_date else ws.write(row, 7, '', cell)
                    ws.write(row, 8, STATE_AR_LABEL.get(c.state, c.state or ''), state_fmt)

                    emp_amount += c.actual_open_balance or 0.0
                    emp_remaining += c.close_balance or 0.0
                    row += 1

                # employee total
                ws.set_row(row, 24)
                ws.write(row, 0, '', f['total_blank'])
                ws.write(row, 1, '', f['total_blank'])
                ws.write(row, 2, 'المجموع', f['total_label'])
                ws.write(row, 3, emp_amount, f['total_amount'])
                ws.write(row, 4, emp_remaining, f['total_amount'])
                for c in range(5, 9):
                    ws.write(row, c, '', f['total_blank'])
                row += 1
                # spacer
                row += 1

                grand_amount += emp_amount
                grand_remaining += emp_remaining

            # grand total
            ws.set_row(row, 26)
            ws.write(row, 0, '', f['grand_blank'])
            ws.write(row, 1, '', f['grand_blank'])
            ws.write(row, 2, 'الإجمالي العام', f['grand_label'])
            ws.write(row, 3, grand_amount, f['grand_amount'])
            ws.write(row, 4, grand_remaining, f['grand_amount'])
            for c in range(5, 9):
                ws.write(row, c, '', f['grand_blank'])

        # freeze top + print setup
        ws.freeze_panes(6, 0)
        ws.set_landscape()
        ws.fit_to_pages(1, 0)
        ws.set_margins(0.4, 0.4, 0.5, 0.5)
        ws.repeat_rows(0, 4)