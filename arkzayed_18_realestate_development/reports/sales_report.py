from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

# Everything is a sale except drafts, cancelled and terminated contracts.
EXCLUDED_STATES = ['draft', 'draft_contract', 'cancelled', 'terminated']
LOST_STATES = ['cancelled', 'terminated']
TYPES = ('domestic', 'overseas', 'unspecified')
TYPE_LABELS = {'domestic': 'Domestic', 'overseas': 'Overseas', 'unspecified': 'Not specified'}
AVAILABLE_STATUSES = ('available', 'available_for_sale')
MONTHS_BACK = 12
TOP_N = 10


def _blank():
    return {'contracts': 0, 'value': 0.0, 'area': 0.0, 'collected': 0.0,
            'domestic': [0, 0.0], 'overseas': [0, 0.0], 'unspecified': [0, 0.0]}


def _add(bucket, ctype, value, area, collected=0.0):
    bucket['contracts'] += 1
    bucket['value'] += value
    bucket['area'] += area
    bucket['collected'] += collected
    bucket[ctype][0] += 1
    bucket[ctype][1] += value


def _pct(part, whole):
    return part / whole * 100 if whole else 0.0


def _cap(label):
    return label[:1].upper() + label[1:] if label else label


class ReportSales(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.report_sales'
    _description = 'Sales Executive Report'

    @api.model
    def _get_contracts(self, data, lost=False):
        domain = [('state', 'in' if lost else 'not in', LOST_STATES if lost else EXCLUDED_STATES)]
        if data.get('project_id'):
            domain.append(('unit_id.project_id', '=', data['project_id']))
        if data.get('building_ids'):
            domain.append(('unit_id.building_id', 'in', data['building_ids']))
        if data.get('contract_type'):
            domain.append(('contract_type', '=', data['contract_type']))
        return self.env['sale.proposal'].search(domain)

    @api.model
    def _collected_by_contract(self, contracts):
        """Same rules as the collections report: an installment marked Paid counts as collected."""
        result = {}
        for line in self.env['installment.lines'].search([('sale_proposal_id', 'in', contracts.ids)]):
            recorded_paid = line.paid_amount or 0.0
            recorded_remaining = line.remaining_amount or 0.0
            line_total = recorded_paid + recorded_remaining
            settled = bool(line.paid) or recorded_remaining <= 0
            result[line.sale_proposal_id.id] = result.get(line.sale_proposal_id.id, 0.0) + (
                line_total if settled else recorded_paid)
        return result

    @api.model
    def _get_inventory(self, data, sold_unit_ids):
        Unit = self.env['real.estate.unit']
        domain = []
        if data.get('project_id'):
            domain.append(('project_id', '=', data['project_id']))
        if data.get('building_ids'):
            domain.append(('building_id', 'in', data['building_ids']))
        type_labels = dict(Unit._fields['unit_type']._description_selection(self.env))
        residential_labels = dict(Unit._fields['residential_type']._description_selection(self.env))
        rows = {}
        for unit in Unit.search(domain):
            if unit.unit_type == 'residential' and unit.residential_type:
                category = _cap(residential_labels.get(unit.residential_type, unit.residential_type))
            else:
                category = type_labels.get(unit.unit_type) or 'Not specified'
            row = rows.setdefault(category, {'label': category, 'total': 0, 'sold': 0, 'reserved': 0,
                                             'available': 0, 'other': 0, 'open_value': 0.0, 'no_price': 0})
            row['total'] += 1
            if unit.id in sold_unit_ids:
                row['sold'] += 1
            elif unit.unit_status == 'reserved' or unit.unit_status in AVAILABLE_STATUSES:
                if unit.unit_status == 'reserved':
                    row['reserved'] += 1
                else:
                    row['available'] += 1
                row['open_value'] += unit.total_price_unit or 0.0
                if not unit.total_price_unit:
                    row['no_price'] += 1
            else:
                row['other'] += 1
        result = sorted(rows.values(), key=lambda r: -r['total'])
        total = {'label': 'Total', 'total': 0, 'sold': 0, 'reserved': 0, 'available': 0, 'other': 0,
                 'open_value': 0.0, 'no_price': 0}
        for row in result:
            for key in ('total', 'sold', 'reserved', 'available', 'other', 'open_value', 'no_price'):
                total[key] += row[key]
            row['sell_through'] = _pct(row['sold'], row['total'])
        total['sell_through'] = _pct(total['sold'], total['total'])
        return result, total

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        today = fields.Date.context_today(self)
        contracts = self._get_contracts(data)
        company = self.env.company

        def selection(model, field):
            return dict(self.env[model]._fields[field]._description_selection(self.env))

        state_labels = selection('sale.proposal', 'state')
        type_labels = selection('sale.proposal', 'unit_type')
        residential_labels = selection('sale.proposal', 'residential_type')
        channel_labels = selection('sale.proposal', 'referred_by')
        collected_by = self._collected_by_contract(contracts)

        total = _blank()
        years, months, earlier = {}, {}, _blank()
        first_month = today.replace(day=1) - relativedelta(months=MONTHS_BACK - 1)
        unit_types, states, buildings, clients, channels = {}, {}, {}, {}, {}
        no_date_count = unspecified_count = no_schedule_count = 0
        disc = {'list_total': 0.0, 'discount_n': 0, 'discount_value': 0.0, 'premium_n': 0, 'premium_value': 0.0}

        for c in contracts:
            value = c.price_after_discount or 0.0
            area = c.unit_id.unit_area or 0.0
            collected = collected_by.get(c.id, 0.0)
            ctype = c.contract_type if c.contract_type in ('domestic', 'overseas') else 'unspecified'
            issue = c.contract_issue_date
            year = issue.year if issue else 0
            _add(total, ctype, value, area, collected)
            _add(years.setdefault(year, _blank()), ctype, value, area, collected)
            no_date_count += 0 if issue else 1
            unspecified_count += 1 if ctype == 'unspecified' else 0
            no_schedule_count += 0 if c.id in collected_by else 1
            if issue:
                key = issue.replace(day=1)
                _add(months.setdefault(key, _blank()) if key >= first_month else earlier, ctype, value, area, collected)

            if c.unit_type == 'residential' and c.residential_type:
                category = _cap(residential_labels.get(c.residential_type, c.residential_type))
            else:
                category = type_labels.get(c.unit_type) or 'Not specified'
            _add(unit_types.setdefault(category, dict(_blank(), label=category)), ctype, value, area, collected)
            _add(states.setdefault(c.state, _blank()), ctype, value, area, collected)
            building = c.unit_id.building_id
            if building:
                bkey, bname = building.id, building.system_code
            elif c.residential_type == 'villa':
                bkey, bname = 'villas', 'Villas (no building)'
            else:
                bkey, bname = 'other', 'Other (no building)'
            _add(buildings.setdefault(bkey, dict(_blank(), name=bname)), ctype, value, area, collected)
            partner = c.customer_id
            _add(clients.setdefault(partner.id, dict(_blank(), name=partner.name or 'Unknown')), ctype, value, area,
                 collected)
            channel = c.referred_by or 'unspecified'
            crow = channels.setdefault(channel, dict(_blank(), label=channel_labels.get(channel, _cap(channel)),
                                                      years=defaultdict(int)))
            _add(crow, ctype, value, area, collected)
            crow['years'][year] += 1

            list_price = c.unit_price or 0.0
            gap = list_price - value
            disc['list_total'] += list_price
            if gap > 1:
                disc['discount_n'] += 1
                disc['discount_value'] += gap
            elif gap < -1:
                disc['premium_n'] += 1
                disc['premium_value'] += -gap

        def finish(bucket):
            bucket['avg'] = bucket['value'] / bucket['contracts'] if bucket['contracts'] else 0.0
            bucket['per_sqm'] = bucket['value'] / bucket['area'] if bucket['area'] else 0.0
            bucket['share'] = _pct(bucket['value'], total['value'])
            bucket['collected_pct'] = _pct(bucket['collected'], bucket['value'])
            bucket['remaining'] = bucket['value'] - bucket['collected']
            for t in TYPES:
                bucket[t + '_share'] = _pct(bucket[t][1], bucket['value'])
            return bucket

        def with_bars(rows):
            top = max([r['value'] for r in rows] or [0]) or 1
            for row in rows:
                row['bar'] = row['value'] / top * 100
                for t in TYPES:
                    row[t + '_bar'] = row[t][1] / top * 100
            return rows

        finish(total)

        year_rows = []
        for year in sorted(years, key=lambda y: (y == 0, y)):
            row = finish(years[year])
            row['year'] = year
            row['label'] = 'No issue date' if year == 0 else ('%d (to date)' % year if year == today.year else str(year))
            year_rows.append(row)
        with_bars(year_rows)

        month_rows = []
        cursor = first_month
        while cursor <= today.replace(day=1):
            row = finish(months.get(cursor, _blank()))
            row['label'] = cursor.strftime('%b %Y')
            month_rows.append(row)
            cursor += relativedelta(months=1)
        with_bars(month_rows)
        finish(earlier)

        type_rows = [finish(b) for b in sorted(unit_types.values(), key=lambda b: -b['value'])]
        state_rows = []
        for key, bucket in sorted(states.items(), key=lambda kv: -kv[1]['value']):
            row = finish(bucket)
            row['label'] = state_labels.get(key, key)
            state_rows.append(row)
        building_rows = [finish(b) for b in sorted(buildings.values(), key=lambda b: -b['value'])]
        client_rows = [finish(b) for b in sorted(clients.values(), key=lambda b: -b['value'])[:TOP_N]]
        channel_rows = [finish(b) for b in sorted(channels.values(), key=lambda b: -b['value'])]
        channel_years = [y['label'] for y in year_rows]
        for row in channel_rows:
            row['year_counts'] = [row['years'].get(y['year'], 0) for y in year_rows]

        # Inventory and sell-through: units are not filtered by contract type.
        all_sold = self._get_contracts(dict(data, contract_type=False))
        inventory_rows, inventory_total = self._get_inventory(data, set(all_sold.mapped('unit_id').ids))

        # Cancelled / terminated contracts (sales lost).
        lost_years = {}
        for c in self._get_contracts(data, lost=True):
            when = c.cancelled_date if c.state == 'cancelled' else c.termination_date
            when = when or c.contract_issue_date
            row = lost_years.setdefault(when.year if when else 0, {'cancelled': [0, 0.0], 'terminated': [0, 0.0]})
            row[c.state][0] += 1
            row[c.state][1] += c.price_after_discount or 0.0
        lost_rows = []
        lost_total = {'cancelled': [0, 0.0], 'terminated': [0, 0.0]}
        for year in sorted(lost_years, key=lambda y: (y == 0, y)):
            row = lost_years[year]
            row['label'] = str(year) if year else 'No date'
            row['count'] = row['cancelled'][0] + row['terminated'][0]
            row['value'] = row['cancelled'][1] + row['terminated'][1]
            for state in ('cancelled', 'terminated'):
                lost_total[state][0] += row[state][0]
                lost_total[state][1] += row[state][1]
            lost_rows.append(row)
        lost_count = lost_total['cancelled'][0] + lost_total['terminated'][0]
        lost_value = lost_total['cancelled'][1] + lost_total['terminated'][1]

        disc['net_value'] = disc['discount_value'] - disc['premium_value']
        disc['discount_pct'] = _pct(disc['discount_value'], disc['list_total'])

        filters = []
        if data.get('project_id'):
            filters.append(self.env['realestate.project'].browse(data['project_id']).display_name)
        if data.get('building_ids'):
            filters.append(', '.join(self.env['real.estate.building'].browse(data['building_ids']).mapped('system_code')))
        if data.get('contract_type'):
            filters.append(TYPE_LABELS[data['contract_type']])

        return {
            'doc_ids': docids,
            'doc_model': 'arkzayed.sales.report.wizard',
            'docs': self.env['arkzayed.sales.report.wizard'].browse(docids),
            'company': company,
            'currency': company.currency_id,
            'today': today,
            'user_name': self.env.user.name,
            'filters': ' | '.join(filters),
            'total': total,
            'year_rows': year_rows,
            'month_rows': month_rows,
            'earlier': earlier,
            'type_rows': type_rows,
            'state_rows': state_rows,
            'top_buildings': building_rows[:TOP_N],
            'building_count': len(building_rows),
            'client_rows': client_rows,
            'channel_rows': channel_rows,
            'channel_years': channel_years,
            'inventory_rows': inventory_rows,
            'inventory_total': inventory_total,
            'lost_rows': lost_rows,
            'lost_total': lost_total,
            'lost_count': lost_count,
            'lost_value': lost_value,
            'discount': disc,
            'no_date_count': no_date_count,
            'unspecified_count': unspecified_count,
            'no_schedule_count': no_schedule_count,
        }
