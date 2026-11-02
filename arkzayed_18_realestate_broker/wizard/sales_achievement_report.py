import base64
import io
from collections import defaultdict

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError

EXCLUDED_STATES = ('draft', 'draft_contract', 'pending_approvals', 'cancelled', 'terminated')
TOP_MANAGEMENT = 'Top Management'
BOARD_REPRESENTATIVE = 'Board Representative'
NO_MANAGER = 'No Manager'
NO_SALESPERSON = 'No Salesperson'

# Referred By values that credit the deal to a fixed "manager" instead of the sales team manager
REFERRED_BY_MANAGER = {
    'management': TOP_MANAGEMENT,
    'board_representative': BOARD_REPRESENTATIVE,
}

DEFAULT_PRIMARY_COLOR = '#2B2B29'
DEFAULT_SECONDARY_COLOR = '#AFAFAD'


class SalesAchievementReportWizard(models.TransientModel):
    _name = 'sales.achievement.report.wizard'
    _description = 'Sales Achievement Report'

    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    excel_file = fields.Binary(readonly=True)
    excel_filename = fields.Char()

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to:
                raise UserError(_("'From' date must be before 'To' date."))

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _get_contracts(self):
        return self.env['sale.proposal'].search([
            ('contract_issue_date', '>=', self.date_from),
            ('contract_issue_date', '<=', self.date_to),
            ('state', 'not in', EXCLUDED_STATES),
            ('company_id', 'in', [self.company_id.id, False]),
        ], order='contract_issue_date, name')

    @staticmethod
    def _category(contract):
        return 'residential' if contract.unit_type == 'residential' else 'commercial'

    @staticmethod
    def _role_shares(contract, role):
        """{user: share} from the commission tab for a role (duplicate lines counted once)."""
        shares = {}
        for line in contract.commission_ids.filtered(lambda l: l.jop_position == role):
            if line.employee_id not in shares:
                shares[line.employee_id] = (line.commission or 0.0) / 100.0
        return shares

    def _team_manager(self, user):
        if not user:
            return self.env['res.users']
        member = self.env['crm.team.member'].search([('user_id', '=', user.id)], limit=1)
        return member.crm_team_id.sales_manager_id

    def _manager_shares(self, contract, sales_shares):
        if contract.referred_by in REFERRED_BY_MANAGER:
            return {REFERRED_BY_MANAGER[contract.referred_by]: 1.0}
        shares = {user.name: share for user, share in self._role_shares(contract, 'Sales Manager').items()}
        if not shares:
            for user, share in sales_shares.items():
                name = self._team_manager(user).name or NO_MANAGER
                shares[name] = shares.get(name, 0.0) + share
        return shares

    def _get_report_data(self):
        self.ensure_one()
        contracts = self._get_contracts()
        state_labels = dict(self.env['sale.proposal']._fields['state']._description_selection(self.env))
        unit_type_labels = dict(self.env['sale.proposal']._fields['unit_type']._description_selection(self.env))
        referred_labels = dict(self.env['sale.proposal']._fields['referred_by']._description_selection(self.env))

        sales = defaultdict(lambda: {'commercial_units': 0.0, 'commercial_value': 0.0,
                                     'residential_units': 0.0, 'residential_value': 0.0})
        managers = {'commercial': defaultdict(lambda: [0.0, 0.0]),
                    'residential': defaultdict(lambda: [0.0, 0.0])}
        sales_manager_names = {}
        contract_lines = []

        for contract in contracts:
            category = self._category(contract)
            price = contract.price_after_discount or 0.0

            sales_shares = self._role_shares(contract, 'Sales Person')
            if not sales_shares:
                sales_shares = {contract.user_id: 1.0}

            for user, share in sales_shares.items():
                name = user.name or NO_SALESPERSON
                row = sales[name]
                row['%s_units' % category] += share
                row['%s_value' % category] += price * share
                if name not in sales_manager_names:
                    sales_manager_names[name] = self._team_manager(user).name or ''

            manager_shares = self._manager_shares(contract, sales_shares)
            for name, share in manager_shares.items():
                managers[category][name][0] += share
                managers[category][name][1] += price * share

            contract_lines.append({
                'name': contract.name,
                'date': contract.contract_issue_date,
                'state': state_labels.get(contract.state, contract.state or ''),
                'unit': contract.unit_id.display_name or '',
                'unit_type': unit_type_labels.get(contract.unit_type, contract.unit_type or ''),
                'category': _('Residential') if category == 'residential' else _('Commercial'),
                'customer': contract.customer_id.display_name or '',
                'referred_by': referred_labels.get(contract.referred_by, contract.referred_by or ''),
                'price': price,
                'discount_percentage': contract.discount_percentage or 0.0,
                'price_before_discount': contract.contracted_selling_price or 0.0,
                'discount_approved_by': contract.discount_approved_by.name if contract.discount_approved_by else '',
                'sales': ', '.join('%s (%g%%)' % (user.name or NO_SALESPERSON, round(share * 100, 2))
                                   for user, share in sales_shares.items()),
                'managers': ', '.join('%s (%g%%)' % (name, round(share * 100, 2))
                                      for name, share in manager_shares.items()),
            })

        def _sum(rows, key):
            return sum(r[key] for r in rows)

        grand_total = sum(line['price'] for line in contract_lines)

        sales_rows = []
        for name in sorted(sales, key=str.lower):
            row = sales[name]
            total = row['commercial_value'] + row['residential_value']
            sales_rows.append(dict(row, name=name, manager=sales_manager_names.get(name, ''), total=total,
                                   share=(total / grand_total * 100) if grand_total else 0.0))

        def _manager_rows(data):
            section_total = sum(value for _units, value in data.values())
            return [{'name': name, 'units': units, 'value': value,
                     'share': (value / section_total * 100) if section_total else 0.0}
                    for name, (units, value) in sorted(data.items(), key=lambda item: -item[1][1])]

        sales_totals = {key: _sum(sales_rows, key) for key in (
            'commercial_units', 'commercial_value', 'residential_units', 'residential_value', 'total')}
        commercial_rows = _manager_rows(managers['commercial'])
        residential_rows = _manager_rows(managers['residential'])
        return {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'contract_count': len(contracts),
            'kpis': {
                'contracts': len(contracts),
                'units': sales_totals['commercial_units'] + sales_totals['residential_units'],
                'value': sales_totals['total'],
                'commercial_value': sales_totals['commercial_value'],
                'residential_value': sales_totals['residential_value'],
            },
            'sales_rows': sales_rows,
            'sales_totals': sales_totals,
            'commercial_rows': commercial_rows,
            'commercial_totals': {'units': _sum(commercial_rows, 'units'), 'value': _sum(commercial_rows, 'value')},
            'residential_rows': residential_rows,
            'residential_totals': {'units': _sum(residential_rows, 'units'), 'value': _sum(residential_rows, 'value')},
            'contract_lines': contract_lines,
        }

    def _get_colors(self):
        company = self.company_id
        return {
            'primary': company.secondary_color or DEFAULT_PRIMARY_COLOR,
            'secondary': company.primary_color or DEFAULT_SECONDARY_COLOR,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_print_pdf(self):
        return self.env.ref('arkzayed_18_realestate_broker.action_report_sales_achievement').report_action(self)

    def action_export_excel(self):
        self.ensure_one()
        data = self._get_report_data()
        content = self._build_excel(data)
        filename = 'Sales_Achievement_%s_%s.xlsx' % (self.date_from, self.date_to)
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
        colors = self._get_colors()
        company = self.company_id
        period = '%s  →  %s' % (data['date_from'].strftime('%d/%m/%Y'), data['date_to'].strftime('%d/%m/%Y'))
        printed = fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d/%m/%Y %H:%M')

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        base = {'font_name': 'Calibri', 'font_size': 10, 'valign': 'vcenter'}

        def fmt(**kwargs):
            return workbook.add_format(dict(base, **kwargs))

        f = {
            'company': fmt(bold=True, font_size=18, font_color=colors['primary']),
            'title': fmt(bold=True, font_size=14, font_color='#FFFFFF', bg_color=colors['primary'], indent=1),
            'meta_label': fmt(bold=True, font_color='#595959'),
            'meta': fmt(font_color='#262626'),
            'kpi_label': fmt(font_size=9, font_color='#595959', bg_color='#F3F3F2', align='center',
                             top=2, top_color=colors['primary']),
            'kpi_value': fmt(bold=True, font_size=14, font_color=colors['primary'], bg_color='#F3F3F2',
                             align='center', num_format='#,##0.##', bottom=1, bottom_color='#D9D9D9'),
            'section': fmt(bold=True, font_size=12, font_color=colors['primary'], bottom=2,
                           bottom_color=colors['primary']),
            'header': fmt(bold=True, font_color='#FFFFFF', bg_color=colors['primary'], align='center',
                          text_wrap=True, border=1, border_color='#FFFFFF'),
            'group': fmt(bold=True, font_color=colors['primary'], bg_color='#E7E6E6', align='center',
                         border=1, border_color='#FFFFFF'),
            'text': fmt(border=1, border_color='#D9D9D9'),
            'text_alt': fmt(border=1, border_color='#D9D9D9', bg_color='#F7F7F7'),
            'units': fmt(border=1, border_color='#D9D9D9', align='center', num_format='#,##0.##'),
            'units_alt': fmt(border=1, border_color='#D9D9D9', align='center', num_format='#,##0.##',
                             bg_color='#F7F7F7'),
            'money': fmt(border=1, border_color='#D9D9D9', num_format='#,##0'),
            'money_alt': fmt(border=1, border_color='#D9D9D9', num_format='#,##0', bg_color='#F7F7F7'),
            'pct': fmt(border=1, border_color='#D9D9D9', align='center', num_format='0.0"%"'),
            'pct_alt': fmt(border=1, border_color='#D9D9D9', align='center', num_format='0.0"%"',
                           bg_color='#F7F7F7'),
            'date': fmt(border=1, border_color='#D9D9D9', align='center', num_format='dd/mm/yyyy'),
            'date_alt': fmt(border=1, border_color='#D9D9D9', align='center', num_format='dd/mm/yyyy',
                            bg_color='#F7F7F7'),
            'total_text': fmt(bold=True, font_color=colors['primary'], bg_color='#E7E6E6', top=2, top_color=colors['primary'], bottom=2, bottom_color=colors['primary']),
            'total_units': fmt(bold=True, font_color=colors['primary'], bg_color='#E7E6E6', top=2, top_color=colors['primary'], bottom=2, bottom_color=colors['primary'], align='center',
                               num_format='#,##0.##'),
            'total_money': fmt(bold=True, font_color=colors['primary'], bg_color='#E7E6E6', top=2, top_color=colors['primary'], bottom=2, bottom_color=colors['primary'],
                               num_format='#,##0'),
            'total_pct': fmt(bold=True, font_color=colors['primary'], bg_color='#E7E6E6', top=2, top_color=colors['primary'], bottom=2, bottom_color=colors['primary'], align='center',
                             num_format='0.0"%"'),
        }

        def setup_sheet(sheet, title, last_col):
            sheet.hide_gridlines(2)
            sheet.set_landscape()
            sheet.set_paper(9)  # A4
            sheet.fit_to_pages(1, 0)
            sheet.set_margins(left=0.4, right=0.4, top=0.7, bottom=0.7)
            sheet.set_header('&L&"Calibri,Bold"%s&R&"Calibri"%s' % (
                company.name.replace('&', '&&'), _('Sales Achievement Report')))
            sheet.set_footer('&L&"Calibri"%s&C&"Calibri"Page &P of &N&R&"Calibri"%s' % (
                period, _('Printed %s') % printed))
            sheet.set_row(0, 30)
            sheet.merge_range(0, 0, 0, last_col, company.name, f['company'])
            sheet.set_row(1, 24)
            sheet.merge_range(1, 0, 1, last_col, title, f['title'])
            sheet.write(2, 0, _('Period'), f['meta_label'])
            sheet.write(2, 1, period, f['meta'])
            sheet.write(3, 0, _('Printed by'), f['meta_label'])
            sheet.write(3, 1, '%s — %s' % (self.env.user.name, printed), f['meta'])
            return 5

        def zebra(key, index):
            return f['%s_alt' % key] if index % 2 else f[key]

        # ---------------- Sheet 1: Summary (sales + managers) ----------------
        sheet = workbook.add_worksheet(_('Summary'))
        sheet.set_column(0, 0, 26)
        sheet.set_column(1, 1, 22)
        sheet.set_column(2, 7, 16)
        row = setup_sheet(sheet, _('Sales Achievement Report'), 7)

        kpis = data['kpis']
        for col, (label, value) in enumerate([
                (_('Contracts'), kpis['contracts']),
                (_('Units'), kpis['units']),
                (_('Total Value'), kpis['value']),
                (_('Commercial Value'), kpis['commercial_value']),
                (_('Residential Value'), kpis['residential_value'])]):
            first, last = (col, col) if col < 2 else (col * 2 - 2, col * 2 - 1)
            if first == last:
                sheet.write(row, first, label, f['kpi_label'])
                sheet.write(row + 1, first, value, f['kpi_value'])
            else:
                sheet.merge_range(row, first, row, last, label, f['kpi_label'])
                sheet.merge_range(row + 1, first, row + 1, last, value, f['kpi_value'])
        sheet.set_row(row + 1, 26)
        row += 3

        sheet.merge_range(row, 0, row, 7, _('Sales'), f['section'])
        row += 1
        sheet.merge_range(row, 0, row + 1, 0, _('Sales'), f['header'])
        sheet.merge_range(row, 1, row + 1, 1, _('Sales Manager'), f['header'])
        sheet.merge_range(row, 2, row, 3, _('Commercial'), f['group'])
        sheet.merge_range(row, 4, row, 5, _('Residential'), f['group'])
        sheet.merge_range(row, 6, row + 1, 6, _('Total Value'), f['header'])
        sheet.merge_range(row, 7, row + 1, 7, _('Share %'), f['header'])
        row += 1
        for col, header in ((2, _('Units')), (3, _('Value')), (4, _('Units')), (5, _('Value'))):
            sheet.write(row, col, header, f['header'])
        sheet.freeze_panes(row + 1, 1)
        for index, line in enumerate(data['sales_rows']):
            row += 1
            sheet.write(row, 0, line['name'], zebra('text', index))
            sheet.write(row, 1, line['manager'], zebra('text', index))
            sheet.write(row, 2, line['commercial_units'], zebra('units', index))
            sheet.write(row, 3, line['commercial_value'], zebra('money', index))
            sheet.write(row, 4, line['residential_units'], zebra('units', index))
            sheet.write(row, 5, line['residential_value'], zebra('money', index))
            sheet.write(row, 6, line['total'], zebra('money', index))
            sheet.write(row, 7, line['share'], zebra('pct', index))
        row += 1
        totals = data['sales_totals']
        sheet.merge_range(row, 0, row, 1, _('Grand Total'), f['total_text'])
        sheet.write(row, 2, totals['commercial_units'], f['total_units'])
        sheet.write(row, 3, totals['commercial_value'], f['total_money'])
        sheet.write(row, 4, totals['residential_units'], f['total_units'])
        sheet.write(row, 5, totals['residential_value'], f['total_money'])
        sheet.write(row, 6, totals['total'], f['total_money'])
        sheet.write(row, 7, 100.0 if totals['total'] else 0.0, f['total_pct'])

        row += 3
        sheet.merge_range(row, 0, row, 7, _('Managers'), f['section'])
        row += 1
        start_row = row
        for first_col, title, rows_key, totals_key in (
                (0, _('Commercial'), 'commercial_rows', 'commercial_totals'),
                (4, _('Residential'), 'residential_rows', 'residential_totals')):
            row = start_row
            sheet.merge_range(row, first_col, row, first_col + 3, title, f['group'])
            row += 1
            for offset, header in enumerate([_('Sales Manager'), _('Units'), _('Value'), _('Share %')]):
                sheet.write(row, first_col + offset, header, f['header'])
            for index, line in enumerate(data[rows_key]):
                row += 1
                sheet.write(row, first_col, line['name'], zebra('text', index))
                sheet.write(row, first_col + 1, line['units'], zebra('units', index))
                sheet.write(row, first_col + 2, line['value'], zebra('money', index))
                sheet.write(row, first_col + 3, line['share'], zebra('pct', index))
            row += 1
            sheet.write(row, first_col, _('Grand Total'), f['total_text'])
            sheet.write(row, first_col + 1, data[totals_key]['units'], f['total_units'])
            sheet.write(row, first_col + 2, data[totals_key]['value'], f['total_money'])
            sheet.write(row, first_col + 3, 100.0 if data[totals_key]['value'] else 0.0, f['total_pct'])

        # ---------------- Sheet 2: Contract details ----------------
        detail = workbook.add_worksheet(_('Contracts'))
        headers = [
            (_('Contract'), 13), (_('Issue Date'), 12), (_('Status'), 20), (_('Unit'), 22),
            (_('Unit Type'), 12), (_('Category'), 13), (_('Customer'), 28), (_('Referred By'), 18),
            (_('Discount %'), 12), (_('Price Before Discount'), 18), (_('Value'), 18),
            (_('Discount Approved By'), 20), (_('Sales (Share)'), 34), (_('Managers (Share)'), 34),
        ]
        for col, (_label, width) in enumerate(headers):
            detail.set_column(col, col, width)
        row = setup_sheet(detail, _('Contract Details'), len(headers) - 1)
        for col, (label, _width) in enumerate(headers):
            detail.write(row, col, label, f['header'])
        detail.set_row(row, 22)
        detail.freeze_panes(row + 1, 1)
        header_row = row
        for index, line in enumerate(data['contract_lines']):
            row += 1
            detail.write(row, 0, line['name'], zebra('text', index))
            if line['date']:
                detail.write_datetime(row, 1, fields.Datetime.to_datetime(line['date']), zebra('date', index))
            else:
                detail.write(row, 1, '', zebra('text', index))
            detail.write(row, 2, line['state'], zebra('text', index))
            detail.write(row, 3, line['unit'], zebra('text', index))
            detail.write(row, 4, line['unit_type'], zebra('text', index))
            detail.write(row, 5, line['category'], zebra('text', index))
            detail.write(row, 6, line['customer'], zebra('text', index))
            detail.write(row, 7, line['referred_by'], zebra('text', index))
            detail.write(row, 8, line['discount_percentage'], zebra('pct', index))
            detail.write(row, 9, line['price_before_discount'], zebra('money', index))
            detail.write(row, 10, line['price'], zebra('money', index))
            detail.write(row, 11, line['discount_approved_by'], zebra('text', index))
            detail.write(row, 12, line['sales'], zebra('text', index))
            detail.write(row, 13, line['managers'], zebra('text', index))
        if data['contract_lines']:
            detail.autofilter(header_row, 0, row, len(headers) - 1)
        row += 1
        detail.merge_range(row, 0, row, 7, _('Grand Total (%s contracts)') % data['contract_count'],
                           f['total_text'])
        detail.write(row, 8, '', f['total_text'])
        detail.write(row, 9, '', f['total_text'])
        detail.write(row, 10, data['kpis']['value'], f['total_money'])
        detail.merge_range(row, 11, row, 13, '', f['total_text'])

        workbook.close()
        return output.getvalue()


class ReportSalesAchievement(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_broker.report_sales_achievement'
    _description = 'Sales Achievement PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env['sales.achievement.report.wizard'].browse(docids)
        wizard = wizards[:1]
        return {
            'doc_ids': docids,
            'doc_model': 'sales.achievement.report.wizard',
            'docs': wizards,
            'report_data': wizard._get_report_data(),
            'colors': wizard._get_colors(),
            'company': wizard.company_id,
            'printed_on': fields.Datetime.context_timestamp(wizard, fields.Datetime.now()),
            'fmt_units': lambda value: '%g' % round(value or 0.0, 2),
            'fmt_money': lambda value: '{:,.0f}'.format(value or 0.0),
            'fmt_pct': lambda value: '%.1f%%' % (value or 0.0),
        }
