import base64
import io
from collections import defaultdict

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.arkzayed_18_realestate_development.models.sale_proposal import COMMISSION_EXCLUDED_STATES

TYPE_ORDER = ['broker', 'ambassador', 'agent', 'employee']
STATUS_LABELS = {
    'paid': 'Paid',
    'paid_out': 'Paid (outside system)',
    'confirmed': 'Claimed - not paid (confirmed)',
    'draft': 'Claimed - not paid (draft)',
    'pending': 'Not yet claimed',
}


class BrokerClaimStatementWizard(models.TransientModel):
    _name = 'broker.claim.statement.wizard'
    _description = 'Broker / Ambassador Commission Statement'

    partner_id = fields.Many2one(
        'res.partner', string='Broker / Ambassador',
        help='Leave empty to get every broker and ambassador, grouped by type.')
    claim_type = fields.Selection([
        ('all', 'All types'),
        ('broker', 'Broker'),
        ('ambassador', 'Ambassador'),
        ('agent', 'Agent'),
        ('employee', 'Non-Sales Employee'),
    ], string='Claim Type', default='all', required=True)
    date_from = fields.Date(string='Contract Date From')
    date_to = fields.Date(string='Contract Date To')
    show_details = fields.Boolean(
        string='Include unit details', default=True,
        help='When no broker is selected: list every unit under each broker/ambassador, not only the totals.')
    include_pending = fields.Boolean(
        string='Include contracts not claimed yet', default=True,
        help='Contracts of the broker/ambassador whose claim has not been raised yet '
             '(expected commission = price x current commission rate).')
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
    def _claim_status(self, claim):
        if claim.state == 'paid':
            return 'paid_out' if claim.paid_outside_system else 'paid'
        return 'confirmed' if claim.state == 'confirmed' else 'draft'

    def _recipient_of(self, claim):
        if claim.claim_type == 'employee' and claim.employee_id:
            return ('employee', claim.employee_id.id), claim.employee_id.name
        return ('partner', claim.broker_company.id), claim.broker_company.name or _('Unknown')

    def _collect(self):
        self.ensure_one()
        Claim = self.env['broker.claim']
        Contract = self.env['sale.proposal']
        types = TYPE_ORDER if self.claim_type == 'all' else [self.claim_type]

        domain = [('state', '!=', 'cancelled'), ('claim_type', 'in', types),
                  ('company_id', 'in', [self.company_id.id, False])]
        if self.partner_id:
            domain.append(('broker_company', '=', self.partner_id.id))
        if self.date_from:
            domain.append(('sale_proposal_id.contract_issue_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('sale_proposal_id.contract_issue_date', '<=', self.date_to))
        claims = Claim.search(domain)

        # recipients[type][key] = {'name', 'rows': []}
        recipients = {t: {} for t in TYPE_ORDER}

        def bucket(ctype, key, name):
            return recipients[ctype].setdefault(key, {'name': name, 'rows': []})

        per_contract = defaultdict(int)
        for claim in claims:
            per_contract[(claim.sale_proposal_id.id, claim.claim_type, claim.broker_company.id)] += 1

        for claim in claims:
            key, name = self._recipient_of(claim)
            contract = claim.sale_proposal_id
            status = self._claim_status(claim)
            bucket(claim.claim_type, key, name)['rows'].append({
                'status': status, 'status_label': STATUS_LABELS[status],
                'contract': contract.name or '', 'unit': claim.unit_id.system_code or claim.unit_id.name or '',
                'customer': contract.customer_id.name or '',
                'date': contract.contract_issue_date or claim.claim_date,
                'price': claim.unit_sold_price, 'pct': claim.commission, 'amount': claim.commission_amount,
                'ref': claim.name, 'payment_date': claim.payment_date,
                'note': _('Duplicate: more than one claim exists for this contract') if (
                    claim.sale_proposal_id and per_contract[
                        (claim.sale_proposal_id.id, claim.claim_type, claim.broker_company.id)] > 1) else '',
            })

        if self.include_pending:
            for kind, flag in (('broker', 'broker_claim_created'), ('ambassador', 'ambassador_claim_created')):
                if kind not in types:
                    continue
                cdom = [('referred_by', '=', kind), (flag, '=', False),
                        ('state', 'not in', list(COMMISSION_EXCLUDED_STATES))]
                if self.partner_id:
                    cdom.append(('referred_by_partner_id', '=', self.partner_id.id))
                else:
                    cdom.append(('referred_by_partner_id', '!=', False))
                if self.date_from:
                    cdom.append(('contract_issue_date', '>=', self.date_from))
                if self.date_to:
                    cdom.append(('contract_issue_date', '<=', self.date_to))
                for contract in Contract.search(cdom):
                    if Claim.search_count([('sale_proposal_id', '=', contract.id), ('claim_type', '=', kind),
                                           ('state', '!=', 'cancelled')]):
                        continue
                    partner = contract.referred_by_partner_id
                    broker_contract = contract.broker_contract_id if kind == 'broker' else False
                    if not broker_contract:
                        for ref_date in filter(None, (contract.contract_issue_date, fields.Date.today())):
                            broker_contract = self.env['broker.contract'].search([
                                ('broker_company', '=', partner.id),
                                ('contract_start_date', '<=', ref_date),
                                ('contract_end_date', '>=', ref_date)], limit=1)
                            if broker_contract:
                                break
                    pct = contract._get_applicable_commission(broker_contract) if broker_contract else 0.0
                    required = broker_contract.collection if broker_contract else 0
                    collected = contract._get_installment_collection_percentage()
                    if pct:
                        note = _('Collected %(c).1f%% of %(r)s%% required before the claim is raised') % {
                            'c': collected, 'r': required}
                    else:
                        note = _('No active commission rate for this broker/ambassador')
                    price = contract.price_after_discount or 0.0
                    bucket(kind, ('partner', partner.id), partner.name or _('Unknown'))['rows'].append({
                        'status': 'pending', 'status_label': STATUS_LABELS['pending'],
                        'contract': contract.name or '', 'unit': contract.unit_id.system_code or '',
                        'customer': contract.customer_id.name or '', 'date': contract.contract_issue_date,
                        'price': price, 'pct': pct, 'amount': price * pct / 100.0,
                        'ref': '', 'payment_date': False, 'note': note,
                    })

        def totals(rows):
            t = {'units': len({r['unit'] for r in rows}), 'paid': 0.0, 'paid_out': 0.0, 'unpaid': 0.0, 'pending': 0.0}
            for r in rows:
                if r['status'] == 'paid':
                    t['paid'] += r['amount']
                elif r['status'] == 'paid_out':
                    t['paid_out'] += r['amount']
                elif r['status'] in ('confirmed', 'draft'):
                    t['unpaid'] += r['amount']
                else:
                    t['pending'] += r['amount']
            t['paid_total'] = t['paid'] + t['paid_out']
            t['due'] = t['unpaid'] + t['pending']
            t['total'] = t['paid_total'] + t['unpaid'] + t['pending']
            return t

        type_labels = dict(Claim._fields['claim_type'].selection)
        groups = []
        all_rows = []
        for ctype in TYPE_ORDER:
            recs = []
            for key, rec in sorted(recipients[ctype].items(), key=lambda kv: kv[1]['name'].lower()):
                rec['rows'].sort(key=lambda r: (r['date'] or fields.Date.today(), r['contract']))
                rec['totals'] = totals(rec['rows'])
                rec['unit_codes'] = ', '.join(sorted({r['unit'] for r in rec['rows'] if r['unit']}))
                recs.append(rec)
                all_rows += rec['rows']
            if recs:
                groups.append({
                    'type': ctype, 'label': type_labels.get(ctype, ctype), 'recipients': recs,
                    'totals': totals([r for rec in recs for r in rec['rows']]),
                })
        if self.partner_id:
            scope = self.partner_id.name
        else:
            scope = _('All brokers and ambassadors, grouped by type')
        period = ''
        if self.date_from or self.date_to:
            period = '%s - %s' % (self.date_from.strftime('%d/%m/%Y') if self.date_from else '...',
                                  self.date_to.strftime('%d/%m/%Y') if self.date_to else '...')
        return {
            'scope': scope, 'single': bool(self.partner_id), 'period': period,
            'show_details': self.show_details or bool(self.partner_id),
            'include_pending': self.include_pending,
            'groups': groups, 'grand': totals(all_rows), 'status_labels': STATUS_LABELS,
            'printed_on': fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d/%m/%Y %H:%M'),
            'company': self.company_id.name,
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_print_pdf(self):
        self.ensure_one()
        if not self._collect()['groups']:
            raise UserError(_('Nothing found for these filters.'))
        return self.env.ref('arkzayed_18_realestate_development.action_report_broker_statement').report_action(self)

    def action_export_excel(self):
        self.ensure_one()
        data = self._collect()
        if not data['groups']:
            raise UserError(_('Nothing found for these filters.'))
        out = io.BytesIO()
        wb = xlsxwriter.Workbook(out, {'in_memory': True})
        title = wb.add_format({'bold': True, 'font_size': 14})
        head = wb.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#0F2A4A', 'border': 1, 'text_wrap': True})
        txt = wb.add_format({'border': 1})
        money = wb.add_format({'border': 1, 'num_format': '#,##0.00'})
        bold_money = wb.add_format({'border': 1, 'num_format': '#,##0.00', 'bold': True, 'bg_color': '#EEF2F7'})
        bold = wb.add_format({'border': 1, 'bold': True, 'bg_color': '#EEF2F7'})
        date = wb.add_format({'border': 1, 'num_format': 'dd/mm/yyyy'})
        green = wb.add_format({'border': 1, 'num_format': '#,##0.00', 'bg_color': '#E3F6EA', 'font_color': '#15803D'})
        red = wb.add_format({'border': 1, 'num_format': '#,##0.00', 'bg_color': '#FDE8E8', 'font_color': '#B91C1C', 'bold': True})
        green_txt = wb.add_format({'border': 1, 'font_color': '#15803D', 'bold': True})
        red_txt = wb.add_format({'border': 1, 'font_color': '#B91C1C', 'bold': True})

        summary = wb.add_worksheet('Summary')
        summary.write(0, 0, _('Broker / Ambassador Commission Statement'), title)
        summary.write(1, 0, data['scope'])
        if data['period']:
            summary.write(2, 0, _('Contract date: %s') % data['period'])
        cols = [_('Type'), _('Recipient'), _('Units'), _('Unit codes'), _('Paid'), _('of which paid outside system'),
                _('Not paid yet'), _('Total')]
        for c, h in enumerate(cols):
            summary.write(4, c, h, head)
        r = 5
        for g in data['groups']:
            for rec in g['recipients']:
                t = rec['totals']
                summary.write(r, 0, g['label'], txt); summary.write(r, 1, rec['name'], txt)
                summary.write(r, 2, t['units'], txt)
                summary.write(r, 3, rec['unit_codes'], txt)
                for c, k in enumerate(('paid_total', 'paid_out', 'due', 'total'), start=4):
                    summary.write(r, c, t[k], green if (k == 'paid_total' and t[k]) else red if (k == 'due' and t[k]) else money)
                r += 1
            t = g['totals']
            summary.write(r, 0, _('Total %s') % g['label'], bold); summary.write(r, 1, '', bold)
            summary.write(r, 2, t['units'], bold); summary.write(r, 3, '', bold)
            for c, k in enumerate(('paid_total', 'paid_out', 'due', 'total'), start=4):
                summary.write(r, c, t[k], bold_money)
            r += 1
        t = data['grand']
        summary.write(r + 1, 0, _('GRAND TOTAL'), bold); summary.write(r + 1, 1, '', bold)
        summary.write(r + 1, 2, t['units'], bold); summary.write(r + 1, 3, '', bold)
        for c, k in enumerate(('paid_total', 'paid_out', 'due', 'total'), start=4):
            summary.write(r + 1, c, t[k], bold_money)
        summary.set_column(0, 1, 30); summary.set_column(2, 2, 8); summary.set_column(3, 3, 60); summary.set_column(4, 7, 22)

        det = wb.add_worksheet('Details')
        dcols = [_('Type'), _('Recipient'), _('Contract'), _('Unit'), _('Customer'), _('Contract date'),
                 _('Unit price'), _('Commission %'), _('Commission'), _('Status'), _('Claim'), _('Payment date'), _('Note')]
        for c, h in enumerate(dcols):
            det.write(0, c, h, head)
        r = 1
        for g in data['groups']:
            for rec in g['recipients']:
                for row in rec['rows']:
                    det.write(r, 0, g['label'], txt); det.write(r, 1, rec['name'], txt)
                    det.write(r, 2, row['contract'], txt); det.write(r, 3, row['unit'], txt)
                    det.write(r, 4, row['customer'], txt)
                    if row['date']:
                        det.write_datetime(r, 5, fields.Datetime.to_datetime(row['date']), date)
                    else:
                        det.write(r, 5, '', txt)
                    det.write(r, 6, row['price'], money); det.write(r, 7, row['pct'], money)
                    is_paid = row['status'] in ('paid', 'paid_out')
                    det.write(r, 8, row['amount'], green if is_paid else red)
                    det.write(r, 9, row['status_label'], green_txt if is_paid else red_txt)
                    det.write(r, 10, row['ref'], txt)
                    if row['payment_date']:
                        det.write_datetime(r, 11, fields.Datetime.to_datetime(row['payment_date']), date)
                    else:
                        det.write(r, 11, '', txt)
                    det.write(r, 12, row['note'], txt)
                    r += 1
        det.set_column(0, 1, 28); det.set_column(2, 3, 14); det.set_column(4, 4, 34)
        det.set_column(5, 8, 16); det.set_column(9, 9, 30); det.set_column(10, 11, 14); det.set_column(12, 12, 60)
        det.freeze_panes(1, 0); det.autofilter(0, 0, max(r - 1, 1), len(dcols) - 1)
        wb.close()
        self.write({
            'excel_file': base64.b64encode(out.getvalue()),
            'excel_filename': 'Commission_Statement_%s.xlsx' % fields.Date.today().strftime('%Y%m%d'),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=excel_file&filename_field=excel_filename&download=true' % (
                self._name, self.id),
            'target': 'self',
        }
