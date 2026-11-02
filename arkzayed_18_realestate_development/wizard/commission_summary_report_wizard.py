import base64
import io
from collections import defaultdict
from datetime import timedelta

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CommissionSummaryReportWizard(models.TransientModel):
    _name = 'commission.summary.report.wizard'
    _description = 'Commission Summary Report'

    sale_proposal_id = fields.Many2one(
        'sale.proposal',
        string='Contract',
        help="Limit the report to a single contract's commissions. Leave empty for "
             "the company-wide report over the date range below."
    )
    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    excel_file = fields.Binary(readonly=True)
    excel_filename = fields.Char()

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise UserError(_("'From' date must be before 'To' date."))

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _get_report_data(self):
        self.ensure_one()
        company_domain = [('company_id', 'in', [self.company_id.id, False])]

        if self.sale_proposal_id:
            scope_domain = [('sale_proposal_id', '=', self.sale_proposal_id.id)]
            period = self.sale_proposal_id.name
        else:
            if not self.date_from or not self.date_to:
                raise UserError(_("Please set both 'From' and 'To' dates, or pick a specific contract instead."))
            date_to_exclusive = self.date_to + timedelta(days=1)
            scope_domain = [('create_date', '>=', self.date_from), ('create_date', '<', date_to_exclusive)]
            period = '%s  -  %s' % (self.date_from.strftime('%d/%m/%Y'), self.date_to.strftime('%d/%m/%Y'))

        achievements = self.env['realestate.commission.achievement'].search(
            scope_domain + [('state', '!=', 'cancelled')] + company_domain)

        claims = self.env['broker.claim'].search(
            scope_domain + [('state', '!=', 'cancelled')] + company_domain)

        claim_type_labels = dict(self.env['broker.claim']._fields['claim_type'].selection)

        recipients = defaultdict(lambda: {'total': 0.0, 'paid': 0.0, 'outstanding': 0.0,
                                          'by_type': defaultdict(float)})
        detail_lines = []

        for achievement in achievements:
            name = achievement.user_id.name or _('Unknown')
            amount = achievement.total_commission_amount or 0.0
            paid = amount if achievement.state == 'paid' else 0.0
            row = recipients[name]
            row['total'] += amount
            row['paid'] += paid
            row['outstanding'] += amount - paid
            row['by_type'][_('Sales Achievement')] += amount
            detail_lines.append({
                'recipient': name,
                'type': _('Sales Achievement'),
                'reference': achievement.sale_proposal_id.name or '',
                'amount': amount,
                'state': achievement.state,
                'paid_outside_system': achievement.paid_outside_system,
                'date': achievement.create_date and achievement.create_date.date(),
                'payment_date': achievement.payment_date,
            })

        for claim in claims:
            if claim.claim_type == 'employee' and claim.employee_id:
                name = claim.employee_id.name
            else:
                name = claim.broker_company.name or _('Unknown')
            amount = claim.paid_commission or 0.0
            paid = amount if claim.state == 'paid' else 0.0
            type_label = claim_type_labels.get(claim.claim_type, claim.claim_type)
            row = recipients[name]
            row['total'] += amount
            row['paid'] += paid
            row['outstanding'] += amount - paid
            row['by_type'][type_label] += amount
            detail_lines.append({
                'recipient': name,
                'type': type_label,
                'reference': claim.sale_proposal_id.name or claim.name,
                'amount': amount,
                'state': claim.state,
                'paid_outside_system': claim.paid_outside_system,
                'date': claim.create_date and claim.create_date.date(),
                'payment_date': claim.payment_date,
            })

        recipient_rows = []
        for name in sorted(recipients, key=str.lower):
            row = recipients[name]
            recipient_rows.append({
                'name': name,
                'total': row['total'],
                'paid': row['paid'],
                'outstanding': row['outstanding'],
                'by_type': dict(row['by_type']),
            })

        detail_lines.sort(key=lambda line: (line['recipient'].lower(), line['type']))

        return {
            'period': period,
            'recipient_rows': recipient_rows,
            'detail_lines': detail_lines,
            'kpis': {
                'total': sum(r['total'] for r in recipient_rows),
                'paid': sum(r['paid'] for r in recipient_rows),
                'outstanding': sum(r['outstanding'] for r in recipient_rows),
                'recipient_count': len(recipient_rows),
            },
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_print_pdf(self):
        return self.env.ref('arkzayed_18_realestate_development.action_report_commission_summary').report_action(self)

    def action_export_excel(self):
        self.ensure_one()
        data = self._get_report_data()
        content = self._build_excel(data)
        if self.sale_proposal_id:
            filename = 'Commission_Summary_%s.xlsx' % self.sale_proposal_id.name
        else:
            filename = 'Commission_Summary_%s_%s.xlsx' % (self.date_from, self.date_to)
        self.write({'excel_file': base64.b64encode(content), 'excel_filename': filename})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/excel_file/%s?download=true' % (self._name, self.id, filename),
            'target': 'self',
        }

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------
    def _build_excel(self, data):
        company = self.company_id
        period = data['period']
        printed = fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d/%m/%Y %H:%M')

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        base = {'font_name': 'Calibri', 'font_size': 10, 'valign': 'vcenter'}

        def fmt(**kwargs):
            return workbook.add_format(dict(base, **kwargs))

        f = {
            'company': fmt(bold=True, font_size=16),
            'title': fmt(bold=True, font_size=13, font_color='#FFFFFF', bg_color='#2B2B29', indent=1),
            'meta_label': fmt(bold=True, font_color='#595959'),
            'meta': fmt(font_color='#262626'),
            'kpi_label': fmt(font_size=9, font_color='#595959', bg_color='#F3F3F2', align='center', top=2),
            'kpi_value': fmt(bold=True, font_size=13, bg_color='#F3F3F2', align='center',
                             num_format='#,##0.00', bottom=1, bottom_color='#D9D9D9'),
            'header': fmt(bold=True, font_color='#FFFFFF', bg_color='#2B2B29', align='center',
                          text_wrap=True, border=1, border_color='#FFFFFF'),
            'text': fmt(border=1, border_color='#D9D9D9'),
            'text_alt': fmt(border=1, border_color='#D9D9D9', bg_color='#F7F7F7'),
            'money': fmt(border=1, border_color='#D9D9D9', num_format='#,##0.00'),
            'money_alt': fmt(border=1, border_color='#D9D9D9', num_format='#,##0.00', bg_color='#F7F7F7'),
            'date': fmt(border=1, border_color='#D9D9D9', align='center', num_format='dd/mm/yyyy'),
            'date_alt': fmt(border=1, border_color='#D9D9D9', align='center', num_format='dd/mm/yyyy',
                            bg_color='#F7F7F7'),
            'total_text': fmt(bold=True, bg_color='#E7E6E6', top=2, bottom=2),
            'total_money': fmt(bold=True, bg_color='#E7E6E6', top=2, bottom=2, num_format='#,##0.00'),
        }

        def setup_sheet(sheet, title, last_col):
            sheet.hide_gridlines(2)
            sheet.set_landscape()
            sheet.fit_to_pages(1, 0)
            sheet.set_row(0, 26)
            sheet.merge_range(0, 0, 0, last_col, company.name, f['company'])
            sheet.set_row(1, 22)
            sheet.merge_range(1, 0, 1, last_col, title, f['title'])
            sheet.write(2, 0, _('Contract') if self.sale_proposal_id else _('Period'), f['meta_label'])
            sheet.write(2, 1, period, f['meta'])
            sheet.write(3, 0, _('Printed by'), f['meta_label'])
            sheet.write(3, 1, '%s - %s' % (self.env.user.name, printed), f['meta'])
            return 5

        def zebra(key, index):
            return f['%s_alt' % key] if index % 2 else f[key]

        # ---------------- Sheet 1: Summary by recipient ----------------
        sheet = workbook.add_worksheet(_('Summary'))
        sheet.set_column(0, 0, 30)
        sheet.set_column(1, 3, 18)
        row = setup_sheet(sheet, _('Commission Summary Report'), 3)

        kpis = data['kpis']
        for col, (label, value) in enumerate([
                (_('Recipients'), kpis['recipient_count']),
                (_('Total Commission'), kpis['total']),
                (_('Paid'), kpis['paid']),
                (_('Outstanding'), kpis['outstanding'])]):
            sheet.write(row, col, label, f['kpi_label'])
            sheet.write(row + 1, col, value, f['kpi_value'])
        sheet.set_row(row + 1, 24)
        row += 3

        for col, header in enumerate([_('Recipient'), _('Total'), _('Paid'), _('Outstanding')]):
            sheet.write(row, col, header, f['header'])
        sheet.freeze_panes(row + 1, 1)
        for index, line in enumerate(data['recipient_rows']):
            row += 1
            sheet.write(row, 0, line['name'], zebra('text', index))
            sheet.write(row, 1, line['total'], zebra('money', index))
            sheet.write(row, 2, line['paid'], zebra('money', index))
            sheet.write(row, 3, line['outstanding'], zebra('money', index))
        row += 1
        sheet.write(row, 0, _('Grand Total'), f['total_text'])
        sheet.write(row, 1, kpis['total'], f['total_money'])
        sheet.write(row, 2, kpis['paid'], f['total_money'])
        sheet.write(row, 3, kpis['outstanding'], f['total_money'])

        # ---------------- Sheet 2: Detail lines ----------------
        detail = workbook.add_worksheet(_('Details'))
        headers = [(_('Recipient'), 28), (_('Type'), 20), (_('Reference'), 16),
                  (_('Amount'), 16), (_('State'), 14), (_('Created'), 14), (_('Payment Date'), 14)]
        for col, (_label, width) in enumerate(headers):
            detail.set_column(col, col, width)
        row = setup_sheet(detail, _('Commission Detail'), len(headers) - 1)
        for col, (label, _width) in enumerate(headers):
            detail.write(row, col, label, f['header'])
        detail.freeze_panes(row + 1, 1)
        header_row = row
        for index, line in enumerate(data['detail_lines']):
            row += 1
            detail.write(row, 0, line['recipient'], zebra('text', index))
            detail.write(row, 1, line['type'], zebra('text', index))
            detail.write(row, 2, line['reference'], zebra('text', index))
            detail.write(row, 3, line['amount'], zebra('money', index))
            state_label = _('Paid (Outside System)') if line['paid_outside_system'] else line['state']
            detail.write(row, 4, state_label, zebra('text', index))
            if line['date']:
                detail.write_datetime(row, 5, line['date'], zebra('date', index))
            else:
                detail.write(row, 5, '', zebra('text', index))
            if line['payment_date']:
                detail.write_datetime(row, 6, line['payment_date'], zebra('date', index))
            else:
                detail.write(row, 6, '', zebra('text', index))
        if data['detail_lines']:
            detail.autofilter(header_row, 0, row, len(headers) - 1)

        workbook.close()
        return output.getvalue()


class ReportCommissionSummary(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.commission_summary'
    _description = 'Commission Summary PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env['commission.summary.report.wizard'].browse(docids)
        wizard = wizards[:1]
        return {
            'doc_ids': docids,
            'doc_model': 'commission.summary.report.wizard',
            'docs': wizards,
            'report_data': wizard._get_report_data(),
            'printed_on': fields.Datetime.context_timestamp(wizard, fields.Datetime.now()),
            'fmt_money': lambda value: '{:,.2f}'.format(value or 0.0),
        }
