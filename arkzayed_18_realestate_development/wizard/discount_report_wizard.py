import base64
import io
from collections import OrderedDict, defaultdict

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# A contract counts as a sale unless it is a draft, cancelled or terminated (same rule as the Executive Dashboard).
EXCLUDED_STATES = ['draft', 'draft_contract', 'cancelled', 'terminated']


def _first_of_year(self_):
    return fields.Date.context_today(self_).replace(month=1, day=1)


class DiscountReportWizard(models.TransientModel):
    _name = 'discount.report.wizard'
    _description = 'Discount Review Report'

    date_from = fields.Date(string='Contract date from', required=True, default=_first_of_year)
    date_to = fields.Date(string='Contract date to', required=True, default=fields.Date.context_today)
    include_drafts = fields.Boolean(
        string='Include draft contracts',
        help='Draft contracts are not sales yet. Tick to show them as well.')
    show_units = fields.Boolean(
        string='Include the list of all units with a discount',
        help='Adds the full list of units that were sold with a discount (one line per unit) after the executive page.')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    excel_file = fields.Binary(readonly=True)
    excel_filename = fields.Char()

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise UserError(_("'From' date must be before 'To' date."))

    # ------------------------------------------------------------------
    @api.model
    def _type_label(self, unit):
        if not unit:
            return _('Unspecified')
        if unit.unit_type == 'residential' and unit.residential_type:
            label = dict(unit._fields['residential_type'].selection).get(unit.residential_type, unit.residential_type)
            return label[:1].upper() + label[1:]
        return dict(unit._fields['unit_type'].selection).get(unit.unit_type, unit.unit_type or _('Unspecified'))

    def _collect(self):
        self.ensure_one()
        Contract = self.env['sale.proposal']
        excluded = [s for s in EXCLUDED_STATES if not (self.include_drafts and s in ('draft', 'draft_contract'))]
        base = [('contract_issue_date', '>=', self.date_from), ('contract_issue_date', '<=', self.date_to),
                ('state', 'not in', excluded)]
        sold = Contract.search(base)
        states = dict(Contract._fields['state'].selection)
        sources = dict(Contract._fields['referred_by'].selection)

        sold_by_type = defaultdict(lambda: {'count': 0, 'value': 0.0})
        for c in sold:
            row = sold_by_type[self._type_label(c.unit_id)]
            row['count'] += 1
            row['value'] += c.price_after_discount or 0.0

        rows, premium = [], []
        for c in sold.filtered(lambda c: (c.discount_percentage or 0.0) != 0.0 and c.discount_percentage < 100):
            final = c.price_after_discount or 0.0
            before = final / (1 - c.discount_percentage / 100.0)
            row = {
                'unit': c.unit_id.system_code or c.unit_id.name or '', 'contract': c.name or '',
                'customer': c.customer_id.name or '', 'state': states.get(c.state, c.state), 'state_key': c.state,
                'date': c.contract_issue_date, 'pct': c.discount_percentage, 'before': before, 'final': final,
                'amount': before - final, 'type': self._type_label(c.unit_id),
                'source': sources.get(c.referred_by, '') if c.referred_by else _('No source recorded'),
                'broker': c.referred_by_partner_id.name or '',
                'approved_by': c.discount_approved_by.name if c.discount_approved_by else '',
            }
            (rows if c.discount_percentage > 0 else premium).append(row)
        rows.sort(key=lambda r: (r['date'], r['unit']))

        total_before = sum(r['before'] for r in rows)
        total_amount = sum(r['amount'] for r in rows)
        total_final = sum(r['final'] for r in rows)
        sold_value = sum(sold.mapped('price_after_discount'))
        avg_pct = total_amount / total_before * 100.0 if total_before else 0.0

        def group(key):
            out = defaultdict(lambda: {'n': 0, 'before': 0.0, 'amount': 0.0})
            for r in rows:
                g = out[r[key]]
                g['n'] += 1
                g['before'] += r['before']
                g['amount'] += r['amount']
            res = []
            for name, g in sorted(out.items(), key=lambda kv: -kv[1]['amount']):
                g['name'] = name
                g['pct'] = g['amount'] / g['before'] * 100.0 if g['before'] else 0.0
                res.append(g)
            return res

        by_type = group('type')
        for g in by_type:
            g['sold'] = sold_by_type.get(g['name'], {}).get('count', 0)
        by_source = group('source')
        months = OrderedDict()
        for r in rows:
            m = months.setdefault(r['date'].strftime('%Y-%m'), {'label': r['date'].strftime('%b %Y'), 'n': 0, 'amount': 0.0})
            m['n'] += 1
            m['amount'] += r['amount']
        peak = max(months.values(), key=lambda m: m['amount']) if months else None
        max_month = max([m['amount'] for m in months.values()] or [0]) or 1
        for m in months.values():
            m['bar'] = round(m['amount'] / max_month * 100)
        top5 = sorted(rows, key=lambda r: -r['amount'])[:5]
        top5_amount = sum(r['amount'] for r in top5)

        points, attention = [], []
        if rows:
            points.append(_('%(n)d of the %(t)d contracts in this period carry a discount (%(s).0f%%), worth %(a)s EGP or %(p).2f%% on average.') % {
                'n': len(rows), 't': len(sold), 's': len(rows) / len(sold) * 100.0, 'a': '{:,.1f}M'.format(total_amount / 1e6), 'p': avg_pct})
            points.append(_('The five largest discounts add up to %(a)s EGP, %(s).0f%% of the total (largest: %(u)s, %(l)s EGP).') % {
                'a': '{:,.1f}M'.format(top5_amount / 1e6), 's': top5_amount / total_amount * 100.0 if total_amount else 0.0,
                'u': top5[0]['unit'], 'l': '{:,.1f}M'.format(top5[0]['amount'] / 1e6)})
            if peak:
                top_source = max(by_source, key=lambda g: g['amount'])
                points.append(_('%(m)s was the heaviest month (%(a)s EGP on %(n)d contracts). %(s)s sales carry the largest part of the discounts (%(sa)s EGP).') % {
                    'm': peak['label'], 'a': '{:,.1f}M'.format(peak['amount'] / 1e6), 'n': peak['n'],
                    's': top_source['name'], 'sa': '{:,.1f}M'.format(top_source['amount'] / 1e6)})
            if not any(r['approved_by'] for r in rows + premium):
                attention.append(_('No approver is recorded on any of these contracts, so the discount approval trail cannot be shown.'))
            unsigned = [r for r in rows if r['state_key'] != 'signed_client']
            if unsigned:
                attention.append(_('%(n)d discounted contract(s) not signed yet: %(u)s (%(a)s EGP of discount).') % {
                    'n': len(unsigned), 'u': ', '.join(r['unit'] for r in unsigned),
                    'a': '{:,.1f}M'.format(sum(r['amount'] for r in unsigned) / 1e6)})
        if premium:
            attention.append(_('%(n)d contract(s) priced above the list price: %(u)s (+%(a)s EGP). Excluded from the discount totals.') % {
                'n': len(premium), 'u': ', '.join(r['unit'] for r in premium),
                'a': '{:,.1f}M'.format(-sum(r['amount'] for r in premium) / 1e6)})

        fmt = '{:,.0f}'.format
        type_rows = [[g['name'], '%d of %d' % (g['n'], g['sold']), fmt(g['before']), fmt(g['amount']), '%.2f%%' % g['pct']]
                     for g in by_type]
        type_foot = ['Total', '%d of %d' % (len(rows), len(sold)), fmt(total_before), fmt(total_amount), '%.2f%%' % avg_pct]
        source_rows = [[g['name'], g['n'], fmt(g['before']), fmt(g['amount']), '%.2f%%' % g['pct']] for g in by_source]
        top5_rows = [[r['unit'], r['customer'][:36], r['date'].strftime('%d %b'), fmt(r['before']), fmt(r['amount']),
                      '%.2f%%' % r['pct']] for r in top5]

        sym = {'signed_client': 'Signed'}
        def unit_line(r):
            return [r['unit'], r['customer'][:30], r['date'].strftime('%d/%m/%y'), fmt(r['before']), '%.2f%%' % r['pct'],
                    fmt(r['amount']), fmt(r['final']), sym.get(r['state_key'], r['state'])]

        unit_rows = [unit_line(r) for r in rows]
        unit_foot = ['Total', '%d units' % len(rows), '', fmt(total_before), '%.2f%%' % avg_pct, fmt(total_amount),
                     fmt(total_final), '']
        premium_rows = [unit_line(r) for r in premium]

        return {
            'show_units': self.show_units, 'unit_rows': unit_rows, 'unit_foot': unit_foot, 'premium_rows': premium_rows,
            'type_rows': type_rows, 'type_foot': type_foot, 'source_rows': source_rows, 'top5_rows': top5_rows,
            'period': '%s - %s' % (self.date_from.strftime('%d %b %Y'), self.date_to.strftime('%d %b %Y')),
            'printed_on': fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d/%m/%Y %H:%M'),
            'company': self.company_id.name,
            'include_drafts': self.include_drafts,
            'rows': rows, 'premium': premium, 'sold_count': len(sold), 'sold_value': sold_value,
            'total_before': total_before, 'total_amount': total_amount, 'total_final': total_final, 'avg_pct': avg_pct,
            'share_units': len(rows) / len(sold) * 100.0 if sold else 0.0,
            'share_value': total_final / sold_value * 100.0 if sold_value else 0.0,
            'by_type': by_type, 'by_source': by_source, 'months': list(months.values()), 'top5': top5,
            'top5_amount': top5_amount, 'points': points, 'attention': attention,
        }

    # ------------------------------------------------------------------
    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('arkzayed_18_realestate_development.action_report_discount').report_action(self)

    def action_export_excel(self):
        self.ensure_one()
        d = self._collect()
        if not d['rows'] and not d['premium']:
            raise UserError(_('No contract with a discount in this period.'))
        out = io.BytesIO()
        wb = xlsxwriter.Workbook(out, {'in_memory': True})
        title = wb.add_format({'bold': True, 'font_size': 13})
        head = wb.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#0F2A4A', 'border': 1, 'text_wrap': True})
        txt = wb.add_format({'border': 1})
        money = wb.add_format({'border': 1, 'num_format': '#,##0'})
        pct = wb.add_format({'border': 1, 'num_format': '0.00'})
        date = wb.add_format({'border': 1, 'num_format': 'dd/mm/yyyy'})
        bold = wb.add_format({'border': 1, 'bold': True, 'bg_color': '#EEF2F7'})
        bold_money = wb.add_format({'border': 1, 'bold': True, 'bg_color': '#EEF2F7', 'num_format': '#,##0'})

        s = wb.add_worksheet('Summary')
        s.write(0, 0, _('Discount Review - %s') % d['period'], title)
        for c, h in enumerate([_('Group'), _('Contracts'), _('Price before discount'), _('Discount amount'), _('Discount %')]):
            s.write(2, c, h, head)
        r = 3
        groups = [(_('All with a discount'), d['rows'])]
        groups.append((_('Signed by client'), [x for x in d['rows'] if x['state_key'] == 'signed_client']))
        groups.append((_('Not signed yet'), [x for x in d['rows'] if x['state_key'] != 'signed_client']))
        for label, lst in groups:
            b = sum(x['before'] for x in lst)
            a = sum(x['amount'] for x in lst)
            s.write(r, 0, label, txt); s.write(r, 1, len(lst), txt); s.write(r, 2, b, money); s.write(r, 3, a, money)
            s.write(r, 4, a / b * 100.0 if b else 0.0, pct)
            r += 1
        r += 1
        for m in d['months']:
            s.write(r, 0, m['label'], txt); s.write(r, 1, m['n'], txt); s.write(r, 2, '', txt); s.write(r, 3, m['amount'], money); s.write(r, 4, '', txt)
            r += 1
        if d['premium']:
            r += 1
            s.write(r, 0, _('Priced above list price (negative discount)'), txt)
            s.write(r, 1, len(d['premium']), txt); s.write(r, 2, '', txt)
            s.write(r, 3, sum(x['amount'] for x in d['premium']), money); s.write(r, 4, '', txt)
        s.set_column(0, 0, 48); s.set_column(1, 4, 22)

        w = wb.add_worksheet('Contracts with discount')
        cols = [_('Unit'), _('Contract'), _('Customer'), _('Status'), _('Contract date'), _('Type'), _('Price before discount'),
                _('Discount %'), _('Discount amount'), _('Price after discount'), _('Source'), _('Broker'), _('Approved by')]
        for c, h in enumerate(cols):
            w.write(0, c, h, head)
        r = 1
        for x in d['rows'] + d['premium']:
            w.write(r, 0, x['unit'], txt); w.write(r, 1, x['contract'], txt); w.write(r, 2, x['customer'], txt)
            w.write(r, 3, x['state'], txt)
            w.write_datetime(r, 4, fields.Datetime.to_datetime(x['date']), date)
            w.write(r, 5, x['type'], txt); w.write(r, 6, x['before'], money); w.write(r, 7, x['pct'], pct)
            w.write(r, 8, x['amount'], money); w.write(r, 9, x['final'], money)
            w.write(r, 10, x['source'], txt); w.write(r, 11, x['broker'], txt); w.write(r, 12, x['approved_by'], txt)
            r += 1
        w.write(r, 0, _('Total (discounts only)'), bold)
        for c in range(1, 13):
            w.write(r, c, '', bold)
        w.write(r, 6, d['total_before'], bold_money); w.write(r, 8, d['total_amount'], bold_money); w.write(r, 9, d['total_final'], bold_money)
        w.set_column(0, 1, 14); w.set_column(2, 2, 40); w.set_column(3, 3, 18); w.set_column(4, 5, 14)
        w.set_column(6, 9, 20); w.set_column(10, 12, 24)
        w.freeze_panes(1, 0); w.autofilter(0, 0, max(r - 1, 1), len(cols) - 1)
        wb.close()
        self.write({'excel_file': base64.b64encode(out.getvalue()),
                    'excel_filename': 'Discount_Review_%s.xlsx' % fields.Date.today().strftime('%Y%m%d')})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=excel_file&filename_field=excel_filename&download=true' % (self._name, self.id),
            'target': 'self',
        }
