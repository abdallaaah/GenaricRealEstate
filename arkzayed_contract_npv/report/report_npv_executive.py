from collections import defaultdict

from odoo import _, api, fields, models

EXCLUDED_STATES = ['draft', 'draft_contract', 'cancelled', 'terminated']
TOP_N = 10


def _cap(label):
    return label[:1].upper() + label[1:] if label else label


class ReportNpvExecutive(models.AbstractModel):
    _name = 'report.arkzayed_contract_npv.report_npv_executive'
    _description = 'NPV Executive Report'

    @api.model
    def _get_contracts(self, data):
        domain = [('state', 'not in', EXCLUDED_STATES)]
        if data.get('project_id'):
            domain.append(('unit_id.project_id', '=', data['project_id']))
        if data.get('building_ids'):
            domain.append(('unit_id.building_id', 'in', data['building_ids']))
        return self.env['sale.proposal'].search(domain)

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        today = fields.Date.context_today(self)
        company = self.env.company
        currency = company.currency_id
        contracts = self._get_contracts(data)
        with_npv = contracts.filtered(lambda c: c.npv_nominal_total > 0)
        missing_npv = len(contracts) - len(with_npv)

        type_labels = dict(self.env['sale.proposal']._fields['unit_type']._description_selection(self.env))
        residential_labels = dict(
            self.env['sale.proposal']._fields['residential_type']._description_selection(self.env))

        # --- totals ---
        total_nominal = sum(with_npv.mapped('npv_nominal_total'))
        total_npv = sum(with_npv.mapped('npv_at_signing'))
        total_lost = total_nominal - total_npv
        total_remaining_nominal = sum(with_npv.mapped('npv_remaining_nominal'))
        total_remaining_npv = sum(with_npv.mapped('npv_remaining_today'))

        # --- by year (contract issue date) ---
        years = defaultdict(lambda: {'contracts': 0, 'nominal': 0.0, 'npv': 0.0})
        for c in with_npv:
            if not c.contract_issue_date:
                continue
            y = years[c.contract_issue_date.year]
            y['contracts'] += 1
            y['nominal'] += c.npv_nominal_total
            y['npv'] += c.npv_at_signing
        year_rows = []
        for y in sorted(years.keys()):
            b = years[y]
            year_rows.append({
                'label': str(y), 'contracts': b['contracts'], 'nominal': b['nominal'], 'npv': b['npv'],
                'lost': b['nominal'] - b['npv'],
                'pct_lost': (b['nominal'] - b['npv']) / b['nominal'] * 100 if b['nominal'] else 0.0,
            })

        # --- by unit type ---
        types = defaultdict(lambda: {'contracts': 0, 'nominal': 0.0, 'npv': 0.0})
        for c in with_npv:
            if c.unit_type == 'residential' and c.residential_type:
                category = _cap(residential_labels.get(c.residential_type, c.residential_type))
            else:
                category = type_labels.get(c.unit_type) or _('Not specified')
            b = types[category]
            b['contracts'] += 1
            b['nominal'] += c.npv_nominal_total
            b['npv'] += c.npv_at_signing
        type_rows = []
        for label, b in sorted(types.items(), key=lambda kv: -kv[1]['nominal']):
            type_rows.append({
                'label': label, 'contracts': b['contracts'], 'nominal': b['nominal'], 'npv': b['npv'],
                'lost': b['nominal'] - b['npv'],
                'pct_lost': (b['nominal'] - b['npv']) / b['nominal'] * 100 if b['nominal'] else 0.0,
            })

        # --- top N contracts by value lost to time ---
        ranked = sorted(with_npv, key=lambda c: -(c.npv_nominal_total - c.npv_at_signing))
        top_rows = []
        for c in ranked[:TOP_N]:
            lost = c.npv_nominal_total - c.npv_at_signing
            top_rows.append({
                'contract': c.name, 'client': c.customer_id.name or '', 'unit': c.unit_id.system_code or '',
                'issue_date': c.contract_issue_date, 'nominal': c.npv_nominal_total, 'npv': c.npv_at_signing,
                'lost': lost, 'pct_lost': lost / c.npv_nominal_total * 100 if c.npv_nominal_total else 0.0,
                'rate': c.npv_signing_rate,
            })

        filters = []
        if data.get('project_id'):
            filters.append(self.env['realestate.project'].browse(data['project_id']).display_name)
        if data.get('building_ids'):
            filters.append(', '.join(self.env['real.estate.building'].browse(data['building_ids']).mapped('system_code')))

        return {
            'doc_ids': docids,
            'doc_model': 'arkzayed.npv.report.wizard',
            'docs': self.env['arkzayed.npv.report.wizard'].browse(docids),
            'company': company,
            'currency': currency,
            'today': today,
            'user_name': self.env.user.name,
            'filters': ' | '.join(filters),
            'discount_rate': company.npv_discount_rate,
            'contract_count': len(with_npv),
            'missing_npv': missing_npv,
            'total_nominal': total_nominal,
            'total_npv': total_npv,
            'total_lost': total_lost,
            'total_pct_lost': total_lost / total_nominal * 100 if total_nominal else 0.0,
            'total_remaining_nominal': total_remaining_nominal,
            'total_remaining_npv': total_remaining_npv,
            'total_remaining_lost': total_remaining_nominal - total_remaining_npv,
            'year_rows': year_rows,
            'type_rows': type_rows,
            'top_rows': top_rows,
        }
