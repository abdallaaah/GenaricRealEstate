from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

# Same rule as the other Ark Zayed reports: everything counts as a real sale except
# drafts, cancelled and terminated contracts.
EXCLUDED_STATES = ['draft', 'draft_contract', 'cancelled', 'terminated']
MONTHS_BACK = 12
STATUS_BUCKETS = [
    ('available', 'Available', '#22c55e'),
    ('available_for_sale', 'Available For Sale', '#10b981'),
    ('reserved', 'Reserved', '#f59e0b'),
    ('other', 'Other', '#9ca3af'),
]

# Same rule as arkzayed_collections_report: contracts whose installments are real receivables.
ACTIVE_STATES = [
    'approved', 'signed_client', 'operation_review', 'finance_review', 'top_management',
    'signed_ceo', 'ready_to_deliver_contract', 'sent_to_client', 'delivered_contract',
    'ready_to_deliver', 'delivered',
]
SUSPICIOUS_YEAR = 2060  # due dates beyond this are almost certainly typing mistakes

# Same rule as arkzayed_cash_report.
UNDER_COLLECTION_STATES = ('register', 'under_collection', 'deposit', 'sent')
RETURNED_STATES = ('return', 'return_to_client', 'bounce')
CASH_MONTHS_BACK = 6
FORECAST_WEEKS = 8
AGEING_BUCKETS = [  # label, from days overdue, to days overdue (inclusive), colour
    ('0-30 days', 0, 30, '#fbbf24'), ('31-60 days', 31, 60, '#f59e0b'), ('61-90 days', 61, 90, '#f97316'),
    ('91-180 days', 91, 180, '#ea580c'), ('Over 180 days', 181, 10 ** 6, '#dc2626'),
]


def _pct(part, whole):
    return part / whole * 100 if whole else 0.0


def _drill(name, model, domain, res_id=None):
    """What the dashboard opens when a number is clicked: a plain Odoo list (or form) on the same records."""
    return {'name': name, 'model': model, 'domain': domain, 'res_id': res_id}


class ArkzayedExecutiveDashboard(models.AbstractModel):
    _name = 'arkzayed.executive.dashboard'
    _description = 'Executive Dashboard (RPC data provider, no stored data)'

    @api.model
    def get_projects(self):
        return self.env['realestate.project'].search_read([], ['id', 'name'], order='name')

    @api.model
    def _type_label(self, unit):
        """Residential units are split Villa / Apartment / ... (residential_type),
        every other unit uses its own unit_type label."""
        if not unit:
            return 'Unspecified'
        if unit.unit_type == 'residential' and unit.residential_type:
            label = dict(unit._fields['residential_type'].selection).get(unit.residential_type, unit.residential_type)
            return label[:1].upper() + label[1:]
        return dict(unit._fields['unit_type'].selection).get(unit.unit_type, unit.unit_type or 'Unspecified')

    @api.model
    def _sold_records(self, contracts, area_of, date_from=None, date_to=None):
        """One row per sold contract, same sold definition as the KPI cards."""
        df = fields.Date.from_string(date_from) if date_from else None
        dt = fields.Date.from_string(date_to) if date_to else None
        records = []
        for c in contracts:
            d = c.contract_issue_date
            if (df or dt) and not d:
                continue
            if df and d < df:
                continue
            if dt and d > dt:
                continue
            records.append({
                'unit': c.unit_id, 'customer': c.customer_id, 'date': d,
                'value': c.price_after_discount or 0.0, 'area': area_of(c.unit_id),
                'channel': c.referred_by, 'broker': c.referred_by_partner_id,
            })
        return records

    @api.model
    def _sub_label(self, unit):
        """The unit's own model inside its type (Villa D, 2 B.R, ...); empty when none is set."""
        if not unit:
            return ''
        field = {'villa': 'villa_type_id', 'apartment': 'apartment_type_id', 'loft': 'loft_type_id'}.get(
            unit.residential_type) if unit.unit_type == 'residential' else {
            'office': 'office_type_id', 'medical': 'medical_type_id'}.get(unit.unit_type)
        return unit[field].name if field and field in unit._fields and unit[field] else ''

    @api.model
    def _sub_field(self, unit):
        if unit.unit_type == 'residential':
            return {'villa': 'villa_type_id', 'apartment': 'apartment_type_id', 'loft': 'loft_type_id'}.get(
                unit.residential_type)
        return {'office': 'office_type_id', 'medical': 'medical_type_id'}.get(unit.unit_type)

    @api.model
    def _type_domain(self, unit):
        if unit.unit_type == 'residential' and unit.residential_type:
            return [('unit_id.unit_type', '=', 'residential'), ('unit_id.residential_type', '=', unit.residential_type)]
        return [('unit_id.unit_type', '=', unit.unit_type or False)]

    @api.model
    def _sub_domain(self, unit):
        field = self._sub_field(unit)
        if not field or field not in unit._fields:
            return []
        return [('unit_id.%s' % field, '=', unit[field].id or False)]

    @api.model
    def _agg_rows(self, groups, total_value):
        rows = [{
            'type': t, 'count': v['count'], 'value': v['value'], 'area': v['area'],
            'avg_per_sqm': (v['value'] / v['area']) if v['area'] else 0.0,
            'pct': _pct(v['value'], total_value),
            'unit': v.get('unit'),
        } for t, v in sorted(groups.items(), key=lambda kv: -kv[1]['value'])]
        return rows

    @api.model
    def _by_type_rows(self, records, base_domain=None):
        total_value = sum(r['value'] for r in records)
        by_type, by_sub = {}, {}
        for r in records:
            t = self._type_label(r['unit'])
            sub = self._sub_label(r['unit']) or 'Unspecified'
            for groups, key in ((by_type, t), (by_sub.setdefault(t, {}), sub)):
                row = groups.setdefault(key, {'count': 0, 'value': 0.0, 'area': 0.0, 'unit': r['unit']})
                row['count'] += 1
                row['value'] += r['value']
                row['area'] += r['area']
        base_domain = base_domain or []
        rows = self._agg_rows(by_type, total_value)
        for row in rows:
            unit = row.pop('unit')
            row['drill'] = _drill(row['type'], 'sale.proposal', base_domain + self._type_domain(unit))
            children = self._agg_rows(by_sub[row['type']], row['value'])
            for ch in children:
                cunit = ch.pop('unit')
                ch['drill'] = _drill('%s / %s' % (row['type'], ch['type']), 'sale.proposal',
                                     base_domain + self._type_domain(cunit) + self._sub_domain(cunit))
            # a single child that only repeats the type (or has no model at all) adds nothing
            if len(children) == 1 and children[0]['type'] in ('Unspecified', row['type']):
                children = []
            row['children'] = children
        total_area = sum(r['area'] for r in records)
        totals = {'count': len(records), 'value': total_value, 'area': total_area,
                  'avg_per_sqm': (total_value / total_area) if total_area else 0.0,
                  'drill': _drill('Sold contracts', 'sale.proposal', base_domain)}
        return rows, totals

    @api.model
    def _insights(self, type_rows, records):
        today = fields.Date.context_today(self)
        years = sorted({r['date'].year for r in records if r['date']})
        insights = {
            'best_type_by_value': None, 'best_type_by_count': None, 'best_type_by_avg_per_sqm': None,
            'yoy_growth_pct': None, 'yoy_prev_year': None, 'yoy_curr_year': None, 'yoy_ytd': False,
        }
        if type_rows:
            insights['best_type_by_value'] = type_rows[0]
            insights['best_type_by_count'] = max(type_rows, key=lambda r: r['count'])
            insights['best_type_by_avg_per_sqm'] = max(type_rows, key=lambda r: r['avg_per_sqm'])
        if len(years) >= 2:
            curr_year, prev_year = years[-1], years[-2]
            # The running year is compared with the same period of the year before,
            # otherwise a half-finished year always looks like a collapse.
            ytd = curr_year == today.year
            cutoff = (today.month, today.day)
            curr = {'year': curr_year, 'count': 0, 'value': 0.0}
            prev = {'year': prev_year, 'count': 0, 'value': 0.0}
            for r in records:
                d = r['date']
                if not d:
                    continue
                bucket = curr if d.year == curr_year else prev if d.year == prev_year else None
                if bucket is None or (ytd and (d.month, d.day) > cutoff):
                    continue
                bucket['count'] += 1
                bucket['value'] += r['value']
            insights.update(yoy_prev_year=prev, yoy_curr_year=curr, yoy_ytd=ytd)
            if prev['value']:
                insights['yoy_growth_pct'] = (curr['value'] - prev['value']) / prev['value'] * 100.0
        return insights

    @api.model
    def get_sales_by_type(self, project_id=None, date_from=None, date_to=None, area_mode='built'):
        """Duration-filterable version of the "By Unit Type" table."""
        def area_of(unit):
            if area_mode == 'villas_landed' and unit.residential_type == 'villa':
                return unit.landed_area or 0.0
            return unit.unit_area or 0.0

        domain = [('state', 'not in', EXCLUDED_STATES)]
        if project_id:
            domain.append(('unit_id.project_id', '=', project_id))
        records = self._sold_records(self.env['sale.proposal'].search(domain), area_of, date_from, date_to)
        drill_domain = list(domain)
        if date_from:
            drill_domain.append(('contract_issue_date', '>=', date_from))
        if date_to:
            drill_domain.append(('contract_issue_date', '<=', date_to))
        rows, totals = self._by_type_rows(records, drill_domain)
        return {'by_type': rows, 'totals': totals}

    @api.model
    def get_sales_inventory(self, project_id=None, area_mode='built'):
        Unit = self.env['real.estate.unit']
        Contract = self.env['sale.proposal']

        def area_of(unit):
            if area_mode == 'villas_landed' and unit.residential_type == 'villa':
                return unit.landed_area or 0.0
            return unit.unit_area or 0.0

        unit_domain = [('project_id', '=', project_id)] if project_id else []
        units = Unit.search(unit_domain)
        total_project_area = sum(units.mapped('project_id').mapped('total_area'))

        contract_domain = [('state', 'not in', EXCLUDED_STATES)]
        if project_id:
            contract_domain.append(('unit_id.project_id', '=', project_id))
        contracts = Contract.search(contract_domain)

        sold_unit_ids = set(contracts.mapped('unit_id').ids)
        total_sold_value = sum(contracts.mapped('price_after_discount'))
        total_sold_area = sum(area_of(c.unit_id) for c in contracts)

        total_units = len(units)
        buckets = {key: {'count': 0, 'area': 0.0, 'value': 0.0} for key, _label, _color in STATUS_BUCKETS}
        for unit in units:
            if unit.id in sold_unit_ids:
                continue
            key = unit.unit_status if unit.unit_status in ('available', 'available_for_sale', 'reserved') else 'other'
            b = buckets[key]
            b['count'] += 1
            b['area'] += area_of(unit)
            b['value'] += unit.total_price_unit or 0.0

        sold_count = len(sold_unit_ids)
        available_count = buckets['available']['count']
        reserved_count = buckets['reserved']['count']
        other_count = buckets['available_for_sale']['count'] + buckets['other']['count']
        open_value = sum(b['value'] for key, b in buckets.items() if key != 'other')

        # --- data quality checks ---
        ghost_sold = units.filtered(lambda u: u.id not in sold_unit_ids and u.unit_status == 'sold')
        open_units = units.filtered(
            lambda u: u.id not in sold_unit_ids and u.unit_status in ('available', 'available_for_sale', 'reserved'))
        no_price_units = open_units.filtered(lambda u: not u.total_price_unit)
        data_quality = {
            'ghost_sold_count': len(ghost_sold),
            'ghost_sold_codes': ghost_sold.mapped('system_code'),
            'no_price_count': len(no_price_units),
            'open_count': len(open_units),
        }

        status_breakdown = [{
            'label': 'Sold', 'count': sold_count, 'area': total_sold_area, 'value': total_sold_value,
            'color': '#0f2a4a',
        }]
        for key, label, color in STATUS_BUCKETS:
            b = buckets[key]
            status_breakdown.append({
                'label': label, 'count': b['count'], 'area': b['area'], 'value': b['value'], 'color': color,
            })
        status_breakdown.append({
            'label': 'Total',
            'count': sum(r['count'] for r in status_breakdown),
            'area': sum(r['area'] for r in status_breakdown),
            'value': sum(r['value'] for r in status_breakdown),
            'color': None,
        })

        # --- what a click opens (plain Odoo lists, same filters as the numbers) ---
        project_c = [('unit_id.project_id', '=', project_id)] if project_id else []
        unit_scope = list(unit_domain) + [('id', 'not in', list(sold_unit_ids))]
        three = ['available', 'available_for_sale', 'reserved']
        drills = {
            'Sold': _drill('Sold contracts', 'sale.proposal', contract_domain),
            'Available': _drill('Available units', 'real.estate.unit', unit_scope + [('unit_status', '=', 'available')]),
            'Available For Sale': _drill('Available for sale units', 'real.estate.unit',
                                         unit_scope + [('unit_status', '=', 'available_for_sale')]),
            'Reserved': _drill('Reserved units', 'real.estate.unit', unit_scope + [('unit_status', '=', 'reserved')]),
            'Other': _drill('Other units (blocked, hold, in lease...)', 'real.estate.unit',
                            unit_scope + [('unit_status', 'not in', three)]),
            'Available (all)': _drill('Available units (incl. available for sale)', 'real.estate.unit',
                                      unit_scope + [('unit_status', 'in', ['available', 'available_for_sale'])]),
            'All units': _drill('All units', 'real.estate.unit', list(unit_domain)),
        }
        for row in status_breakdown:
            row['drill'] = drills.get(row['label'], drills['All units'])

        # --- monthly sales trend, last 12 months ---
        today = fields.Date.context_today(self)
        this_month = today.replace(day=1)
        first_month = this_month - relativedelta(months=MONTHS_BACK - 1)
        month_value = defaultdict(float)
        month_count = defaultdict(int)
        for c in contracts:
            d = c.contract_issue_date
            if d and first_month <= d.replace(day=1) <= this_month:
                key = d.strftime('%Y-%m')
                month_value[key] += c.price_after_discount or 0.0
                month_count[key] += 1

        trend = []
        cursor = first_month
        while cursor <= this_month:
            key = cursor.strftime('%Y-%m')
            month_end = cursor + relativedelta(months=1, days=-1)
            trend.append({
                'label': cursor.strftime('%b %Y'),
                'value': month_value[key],
                'count': month_count[key],
                'drill': _drill('Sales %s' % cursor.strftime('%b %Y'), 'sale.proposal', contract_domain + [
                    ('contract_issue_date', '>=', fields.Date.to_string(cursor)),
                    ('contract_issue_date', '<=', fields.Date.to_string(month_end))]),
            })
            cursor += relativedelta(months=1)

        # --- Arabella-style extras: area tree, insights, top clients, sales by source ---
        records = self._sold_records(contracts, area_of)
        type_rows, _totals = self._by_type_rows(records, contract_domain)
        by_client, by_channel = {}, {}
        channel_labels = dict(Contract._fields['referred_by'].selection) if 'referred_by' in Contract._fields else {}
        for r in records:
            row = by_client.setdefault(r['customer'].id, {'name': r['customer'].name or 'Unknown', 'count': 0, 'value': 0.0})
            row['count'] += 1
            row['value'] += r['value']
            label = channel_labels.get(r['channel'], r['channel']) if r['channel'] else 'Unspecified'
            row = by_channel.setdefault(label, {'count': 0, 'value': 0.0, 'key': r['channel'] or False})
            row['count'] += 1
            row['value'] += r['value']
        top_clients = [{'client': v['name'], 'count': v['count'], 'value': v['value'],
                        'drill': _drill('Contracts of %s' % v['name'], 'sale.proposal',
                                        contract_domain + [('customer_id', '=', cid)])}
                       for cid, v in sorted(by_client.items(), key=lambda kv: -kv[1]['value'])[:5]]
        channel_rows = [{'channel': n, 'count': v['count'], 'value': v['value'], 'pct': _pct(v['value'], total_sold_value),
                         'drill': _drill('Sales by source: %s' % n, 'sale.proposal',
                                         contract_domain + [('referred_by', '=', v['key'])])}
                        for n, v in sorted(by_channel.items(), key=lambda kv: -kv[1]['value'])]

        # --- top brokers (contracts that name a broker partner) ---
        by_broker = {}
        for r in records:
            if r['broker']:
                row = by_broker.setdefault(r['broker'].id, {'name': r['broker'].name, 'count': 0, 'value': 0.0})
                row['count'] += 1
                row['value'] += r['value']
        top_brokers = [{
            'broker': v['name'], 'count': v['count'], 'value': v['value'],
            'drill': _drill('Contracts via %s' % v['name'], 'sale.proposal',
                            contract_domain + [('referred_by_partner_id', '=', bid)]),
        } for bid, v in sorted(by_broker.items(), key=lambda kv: -kv[1]['value'])[:5]]

        # --- this month vs last month ---
        last_month_start = this_month - relativedelta(months=1)
        month_cmp = {'value': 0.0, 'count': 0, 'prev_value': 0.0, 'prev_count': 0}
        for r in records:
            if r['date'] and r['date'] >= this_month:
                month_cmp['value'] += r['value']
                month_cmp['count'] += 1
            elif r['date'] and last_month_start <= r['date'] < this_month:
                month_cmp['prev_value'] += r['value']
                month_cmp['prev_count'] += 1
        month_cmp['delta_pct'] = ((month_cmp['value'] - month_cmp['prev_value']) / month_cmp['prev_value'] * 100.0
                                  if month_cmp['prev_value'] else None)
        month_cmp['drill'] = _drill('Sales this month', 'sale.proposal', contract_domain + [
            ('contract_issue_date', '>=', fields.Date.to_string(this_month))])

        total_inventory_area = sum(r['area'] for r in status_breakdown if r['label'] != 'Total')
        by_label = {r['label']: r for r in status_breakdown}

        def node(label, row, color=None, **extra):
            return dict({
                'label': label, 'area': row['area'], 'value': row['value'], 'count': row['count'],
                'color': color or row['color'], 'pct': _pct(row['area'], total_inventory_area),
                'drill': row.get('drill'),
            }, **extra)

        avail, afs = by_label['Available'], by_label['Available For Sale']
        combined = {'area': avail['area'] + afs['area'], 'value': avail['value'] + afs['value'],
                    'count': avail['count'] + afs['count'], 'drill': drills['Available (all)']}
        area_tree = [
            node('Sold', by_label['Sold']),
            node('Available', combined, avail['color'], children=[
                node('Available For Sale', afs),
                node('Non Available For Sale', avail),
            ]),
            node('Reserved', by_label['Reserved']),
            node('Other', by_label['Other']),
        ]

        return {
            'as_of': fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d %b %Y, %H:%M'),
            'area_mode': area_mode,
            'kpi': {
                'total_units': total_units,
                'total_project_area': total_project_area,
                'sold_count': sold_count,
                'available_count': available_count,
                'reserved_count': reserved_count,
                'other_count': other_count,
                'sell_through_pct': _pct(sold_count, total_units),
                'total_sold_value': total_sold_value,
                'total_sold_area': total_sold_area,
                'avg_price_per_sqm': (total_sold_value / total_sold_area) if total_sold_area else 0.0,
                'open_value': open_value,
                'contracts_count': len(contracts),
                'total_inventory_area': total_inventory_area,
                'available_value': combined['value'],
                'month': month_cmp,
            },
            'inventory_split': [
                {'label': r['label'], 'value': r['count'], 'color': r['color'], 'drill': r['drill']}
                for r in status_breakdown if r['label'] != 'Total' and r['count'] > 0
            ],
            'kpi_drill': {
                'sold': drills['Sold'], 'units': drills['All units'],
                'project': _drill('Projects', 'realestate.project',
                                  [('id', '=', project_id)] if project_id else []),
                'open': _drill('Open units (available + reserved)', 'real.estate.unit',
                               unit_scope + [('unit_status', 'in', three)]),
            },
            'status_breakdown': status_breakdown,
            'trend': trend,
            'area_tree': area_tree,
            'insights': self._insights(type_rows, records),
            'by_type': type_rows[:8],
            'top_clients': top_clients,
            'top_brokers': top_brokers,
            'by_channel': channel_rows,
            'data_quality': data_quality,
        }

    @api.model
    def get_collections_vs_due(self, project_id=None, date_from=None, date_to=None):
        today = fields.Date.context_today(self)
        date_from = fields.Date.from_string(date_from) if date_from else today.replace(day=1)
        date_to = fields.Date.from_string(date_to) if date_to else today
        far_future = today.replace(year=SUSPICIOUS_YEAR)

        domain = [('contract_state', 'in', ACTIVE_STATES)]
        if project_id:
            domain.append(('unit_id.project_id', '=', project_id))
        lines = self.env['installment.lines'].search(domain)

        # --- collected in period: same collected_on derivation as arkzayed_collections_report ---
        collections_in_period = 0.0
        collections_by_day = defaultdict(float)
        collected_line_ids = set()
        allocations = self.env['payment.allocation'].search([('installment_id', 'in', lines.ids)])
        for alloc in allocations:
            amount = alloc.allocated_amount
            collected_on = False
            if alloc.payment_id and alloc.payment_id.state == 'paid':
                payment = alloc.payment_id
                entry = payment.move_id
                collected_on = entry.date if entry.is_collection and entry.state == 'posted' else payment.date
            elif alloc.cheque_id and alloc.cheque_id.state == 'done':
                cheque = alloc.cheque_id
                entries = cheque.move_line_ids.mapped('move_id').filtered(
                    lambda m: m.is_collection and m.state == 'posted')
                if entries:
                    collected_on = entries.sorted('id')[-1].date
                else:
                    candidates = [d for d in (cheque.cheque_date, cheque.cheque_receive_date) if d]
                    collected_on = cheque.cashed_date or (max(candidates) if candidates else False)
            else:
                continue
            if not collected_on or not (date_from <= collected_on <= date_to):
                continue
            collections_in_period += amount
            collections_by_day[collected_on] += amount
            collected_line_ids.add(alloc.installment_id.id)

        # An installment ticked Paid is collected money too: the part no payment or cheque covers
        # is dated on its own due date (same rule as the printed Collections reports).
        for line in lines:
            if line.paid and line.date and date_from <= line.date <= date_to:
                amount = line.remaining_amount or 0.0
                if amount > 0.01:
                    collections_in_period += amount
                    collections_by_day[line.date] += amount
                    collected_line_ids.add(line.id)

        # daily buckets for a short range, monthly buckets for a longer one (same rule as the printed report)
        span_days = (date_to - date_from).days + 1
        by_month = span_days > 62
        timeline = []
        if by_month:
            month_totals = defaultdict(float)
            for d, amount in collections_by_day.items():
                month_totals[d.strftime('%Y-%m')] += amount
            cursor = date_from.replace(day=1)
            last_month = date_to.replace(day=1)
            while cursor <= last_month:
                key = cursor.strftime('%Y-%m')
                timeline.append({'label': cursor.strftime('%b %Y'), 'amount': month_totals.get(key, 0.0)})
                cursor += relativedelta(months=1)
        else:
            cursor = date_from
            while cursor <= date_to:
                timeline.append({'label': cursor.strftime('%d %b'), 'amount': collections_by_day.get(cursor, 0.0)})
                cursor += relativedelta(days=1)

        # --- installments due within the period: fully / partially / not collected ---
        due_total = due_collected = due_remaining = 0.0
        fully_n = partial_n = none_n = 0
        fully_amt = partial_amt = none_amt = 0.0
        partial_paid = partial_left = none_left = 0.0
        unpaid_rows = []
        due_ids = {'fully': [], 'partial': [], 'none': [], 'remaining': []}
        for line in lines:
            if not line.date or line.date > far_future or not (date_from <= line.date <= date_to):
                continue
            recorded_paid = line.paid_amount or 0.0
            recorded_remaining = line.remaining_amount or 0.0
            line_total = recorded_paid + recorded_remaining
            settled = bool(line.paid) or recorded_remaining <= 0
            paid = line_total if settled else recorded_paid
            remaining = 0.0 if settled else recorded_remaining

            due_total += line_total
            due_collected += paid
            due_remaining += remaining
            if remaining > 0:
                due_ids['remaining'].append(line.id)

            due_ids['fully' if settled else 'partial' if paid > 0 else 'none'].append(line.id)
            if settled:
                fully_n += 1
                fully_amt += line_total
            elif paid > 0:
                partial_n += 1
                partial_amt += line_total
                partial_paid += paid
                partial_left += remaining
            else:
                none_n += 1
                none_amt += line_total
                none_left += remaining
                unpaid_rows.append({
                    'client': line.customer_id.name or '', 'unit': line.unit_id.system_code or '',
                    'due_date': line.date, 'amount': line_total,
                    'drill': _drill('Contract %s' % (line.sale_proposal_id.name or ''), 'sale.proposal', [],
                                    res_id=line.sale_proposal_id.id) if line.sale_proposal_id else None,
                })

        unpaid_rows.sort(key=lambda r: -r['amount'])

        def lines_drill(name, ids):
            return _drill(name, 'installment.lines', [('id', 'in', ids)])

        status_breakdown = [
            {'label': 'Fully Collected', 'count': fully_n, 'amount': fully_amt,
             'collected': fully_amt, 'remaining': 0.0, 'color': '#059669',
             'drill': lines_drill('Installments fully collected', due_ids['fully'])},
            {'label': 'Partially Collected', 'count': partial_n, 'amount': partial_amt,
             'collected': partial_paid, 'remaining': partial_left, 'color': '#f59e0b',
             'drill': lines_drill('Installments partially collected', due_ids['partial'])},
            {'label': 'Not Collected', 'count': none_n, 'amount': none_amt,
             'collected': 0.0, 'remaining': none_left, 'color': '#dc2626',
             'drill': lines_drill('Installments not collected', due_ids['none'])},
        ]
        status_breakdown.append({
            'label': 'Total',
            'count': sum(r['count'] for r in status_breakdown),
            'amount': sum(r['amount'] for r in status_breakdown),
            'collected': sum(r['collected'] for r in status_breakdown),
            'remaining': sum(r['remaining'] for r in status_breakdown),
            'color': None,
            'drill': lines_drill('Installments due in the period', due_ids['fully'] + due_ids['partial'] + due_ids['none']),
        })

        if date_from.replace(day=1) == date_to.replace(day=1) and date_to.month == date_from.month:
            period_label = date_from.strftime('%b %Y')
        else:
            period_label = '%s – %s' % (date_from.strftime('%d %b %Y'), date_to.strftime('%d %b %Y'))

        return {
            'as_of': fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d %b %Y, %H:%M'),
            'period_label': period_label,
            'date_from': fields.Date.to_string(date_from),
            'date_to': fields.Date.to_string(date_to),
            'kpi': {
                'collected_in_period': collections_in_period,
                'due_total': due_total,
                'due_collected': due_collected,
                'due_remaining': due_remaining,
                'collected_pct': _pct(due_collected, due_total),
                # money received in the period on installments that are not due in it
                # (late payments on older installments, or payments made in advance)
                'collected_other': max(0.0, collections_in_period - due_collected),
            },
            'kpi_drill': {
                'collected': lines_drill('Installments collected in the period', sorted(collected_line_ids)),
                'due': lines_drill('Installments due in the period',
                                   due_ids['fully'] + due_ids['partial'] + due_ids['none']),
                'remaining': lines_drill('Due and still unpaid', due_ids['remaining']),
            },
            'status_split': [
                {'label': r['label'], 'value': r['count'], 'color': r['color'], 'drill': r['drill']}
                for r in status_breakdown if r['label'] != 'Total' and r['count'] > 0
            ],
            'status_breakdown': status_breakdown,
            'timeline': timeline,
            'top_unpaid': unpaid_rows[:10],
        }

    @api.model
    def get_cash_position(self):
        # Company-wide by nature (bank accounts and vendor bills aren't split by project),
        # so this section ignores the project filter — same scope as arkzayed_cash_report.
        today = fields.Date.context_today(self)
        far_future = today.replace(year=SUSPICIOUS_YEAR)
        Line = self.env['account.move.line']

        # --- cash and bank today ---
        company_currency = self.env.company.currency_id
        liquidity = self.env['account.account'].search([('account_type', '=', 'asset_cash')])
        bal = Line._read_group(
            [('account_id', 'in', liquidity.ids), ('parent_state', '=', 'posted'), ('date', '<=', today)],
            ['account_id'], ['balance:sum', 'amount_currency:sum'])
        cash_rows = []
        for acc, balance, amount_currency in bal:
            if abs(balance) <= 0.005:
                continue
            is_foreign = bool(acc.currency_id and acc.currency_id != company_currency)
            cash_rows.append({
                'drill': _drill('%s %s' % (acc.code or '', acc.name or ''), 'account.move.line', [
                    ('account_id', '=', acc.id), ('parent_state', '=', 'posted'), ('date', '<=', today)]),
                'code': acc.code or '', 'name': acc.name or '',
                'balance': balance,
                'display_amount': amount_currency if is_foreign else balance,
                'currency': acc.currency_id.name if is_foreign else company_currency.name,
                'is_foreign': is_foreign,
            })
        cash_rows.sort(key=lambda r: -r['balance'])
        cash_total = sum(r['balance'] for r in cash_rows)

        # --- monthly cash in / out, last 6 months (pure transfers between liquidity accounts excluded) ---
        this_month = today.replace(day=1)
        first_month = this_month - relativedelta(months=CASH_MONTHS_BACK - 1)
        flow = defaultdict(lambda: [0.0, 0.0])
        lines = Line.search([
            ('account_id', 'in', liquidity.ids), ('parent_state', '=', 'posted'),
            ('date', '>=', first_month), ('date', '<=', today)])
        for move, mlines in lines.grouped('move_id').items():
            if not (move.line_ids - move.line_ids.filtered(lambda l: l.account_id in liquidity)):
                continue
            key = move.date.strftime('%Y-%m')
            flow[key][0] += sum(mlines.mapped('debit'))
            flow[key][1] += sum(mlines.mapped('credit'))
        flow_rows, cursor = [], first_month
        while cursor <= this_month:
            k = cursor.strftime('%Y-%m')
            flow_rows.append({
                'label': cursor.strftime('%b %Y'),
                'in': flow[k][0], 'out': flow[k][1], 'net': flow[k][0] - flow[k][1],
            })
            cursor += relativedelta(months=1)

        # --- incoming cheques by status ---
        cheques = self.env['cheque.manage'].search([('cheq_type', '=', 'incoming')])
        by_state = defaultdict(lambda: [0, 0.0])
        ids_by_state = defaultdict(list)
        for c in cheques:
            if c.state == 'to_adib':
                key = 'to_adib'
            elif c.cycle_type == 'hermes' or c.state == 'to_hermes':
                key = 'hermes'
            elif c.state in UNDER_COLLECTION_STATES:
                key = 'under'
            elif c.state in RETURNED_STATES:
                key = 'returned'
            else:
                key = c.state
            by_state[key][0] += 1
            by_state[key][1] += c.amount or 0.0
            ids_by_state[key].append(c.id)
        status_defs = [
            ('draft', 'Draft (not received yet)', '#9ca3af'),
            ('collect', 'Received (in hand)', '#0f2a4a'),
            ('under', 'Under Collection / Deposited', '#0d9488'),
            ('hermes', 'To Hermes', '#8b5cf6'),
            ('to_adib', 'To Adib', '#0ea5e9'),
            ('done', 'Collected', '#059669'),
            ('returned', 'Returned / Bounced', '#dc2626'),
        ]
        cheque_status = [
            {'label': label, 'count': by_state[key][0], 'amount': by_state[key][1], 'color': color,
             'drill': _drill('Cheques: %s' % label, 'cheque.manage', [('id', 'in', ids_by_state[key])])}
            for key, label, color in status_defs
        ]
        cheque_status.append({
            'label': 'Total',
            'count': sum(r['count'] for r in cheque_status),
            'amount': sum(r['amount'] for r in cheque_status),
            'color': None,
            'drill': _drill('Incoming cheques', 'cheque.manage',
                           [('id', 'in', [i for key, _l, _c in status_defs for i in ids_by_state[key]])]),
        })

        in_hand = cheques.filtered(lambda c: c.state == 'collect' and c.cycle_type != 'hermes')
        in_hand_total = sum(in_hand.mapped('amount'))

        # --- cheque deposit forecast: incoming cheques not yet collected, by week of their cheque date ---
        waiting = cheques.filtered(lambda c: c.state == 'collect' or c.cycle_type == 'hermes' or c.state == 'to_hermes')
        week0 = today - relativedelta(days=today.weekday())
        buckets = [{'label': 'Due now', 'hand': [], 'hermes': [], 'drill_ids': []}]
        for i in range(FORECAST_WEEKS):
            start = week0 + relativedelta(weeks=i)
            buckets.append({'label': start.strftime('%d %b'), 'start': start, 'hand': [], 'hermes': []})
        buckets.append({'label': 'Later', 'hand': [], 'hermes': []})
        horizon = week0 + relativedelta(weeks=FORECAST_WEEKS)
        for c in waiting:
            d = c.cheque_date
            if not d or d <= today and d < week0:
                idx = 0
            elif d >= horizon:
                idx = len(buckets) - 1
            else:
                idx = 1 + (d - week0).days // 7
            if d and d <= today:
                idx = 0
            bucket = buckets[idx]
            bucket['hermes' if (c.cycle_type == 'hermes' or c.state == 'to_hermes') else 'hand'].append(c)
        forecast = []
        for b in buckets:
            hand_total = sum(x.amount or 0.0 for x in b['hand'])
            hermes_total = sum(x.amount or 0.0 for x in b['hermes'])
            all_ids = [x.id for x in b['hand'] + b['hermes']]
            forecast.append({
                'label': b['label'], 'hand': hand_total, 'hermes': hermes_total, 'count': len(all_ids),
                'drill': _drill('Cheques: %s' % b['label'], 'cheque.manage', [('id', 'in', all_ids)]),
            })

        # --- returned / bounced incoming cheques ---
        returned = cheques.filtered(lambda c: c.state in RETURNED_STATES).sorted(
            key=lambda c: c.return_date or c.cheque_date or today, reverse=True)
        returned_rows = [{
            'cheque_no': c.cheque_no or c.seq_no or '', 'client': c.sale_proposal_id.customer_id.name or c.partner_id.name or '',
            'unit': c.unit_id.system_code or '', 'date': c.return_date or c.cheque_date, 'amount': c.amount or 0.0,
            'drill': _drill('Cheque %s' % (c.cheque_no or ''), 'cheque.manage', [], res_id=c.id),
        } for c in returned[:6]]

        # --- overdue installments (due, unpaid) ---
        inst = self.env['installment.lines'].search([
            ('contract_state', 'in', ACTIVE_STATES), ('paid', '=', False), ('remaining_amount', '>', 0)])
        overdue_lines = inst.filtered(lambda l: l.date and l.date <= today and l.date.year <= SUSPICIOUS_YEAR)
        inst_overdue = sum(overdue_lines.mapped('remaining_amount'))

        # --- vendor bills ---
        bills = self.env['account.move'].search([
            ('move_type', '=', 'in_invoice'), ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial'))])
        pay_overdue = pay_total = 0.0
        overdue_bill_ids = []
        for b in bills:
            amount = b.amount_residual
            pay_total += amount
            due = b.invoice_date_due or b.invoice_date or today
            if due <= today:
                pay_overdue += amount
                overdue_bill_ids.append(b.id)

        return {
            'as_of': fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d %b %Y, %H:%M'),
            'kpi': {
                'cash_total': cash_total,
                'in_hand_total': in_hand_total,
                'inst_overdue': inst_overdue,
                'pay_overdue': pay_overdue,
                'pay_total': pay_total,
            },
            'kpi_drill': {
                'cash': _drill('Cash and bank accounts', 'account.move.line', [
                    ('account_id', 'in', liquidity.ids), ('parent_state', '=', 'posted'), ('date', '<=', today)]),
                'in_hand': _drill('Cheques in hand', 'cheque.manage', [('id', 'in', in_hand.ids)]),
                'inst_overdue': _drill('Overdue installments', 'installment.lines', [('id', 'in', overdue_lines.ids)]),
                'pay_overdue': _drill('Overdue vendor bills', 'account.move', [('id', 'in', overdue_bill_ids)]),
                'pay_total': _drill('Open vendor bills', 'account.move', [('id', 'in', bills.ids)]),
            },
            'forecast': forecast,
            'returned': {
                'count': len(returned), 'amount': sum(returned.mapped('amount')), 'rows': returned_rows,
                'drill': _drill('Returned / bounced cheques', 'cheque.manage', [('id', 'in', returned.ids)]),
            },
            'cash_rows': cash_rows,
            'flow_rows': flow_rows,
            'cheque_status': cheque_status,
            'cheque_status_split': [
                {'label': r['label'], 'value': r['count'], 'color': r['color'], 'drill': r['drill']}
                for r in cheque_status if r['label'] != 'Total' and r['count'] > 0
            ],
        }

    @api.model
    def get_receivables(self, project_id=None):
        """Overdue installments of live contracts, aged by days past due, and the clients behind them."""
        today = fields.Date.context_today(self)
        far_future = today.replace(year=SUSPICIOUS_YEAR)
        domain = [('contract_state', 'in', ACTIVE_STATES), ('paid', '=', False), ('remaining_amount', '>', 0),
                  ('date', '!=', False), ('date', '<=', today), ('date', '<=', far_future)]
        if project_id:
            domain.append(('unit_id.project_id', '=', project_id))
        lines = self.env['installment.lines'].search(domain)

        buckets = [{'label': label, 'amount': 0.0, 'count': 0, 'color': color, 'ids': []}
                   for label, _a, _b, color in AGEING_BUCKETS]
        by_client = {}
        for line in lines:
            days = (today - line.date).days
            for b, (_l, lo, hi, _c) in zip(buckets, AGEING_BUCKETS):
                if lo <= days <= hi:
                    b['amount'] += line.remaining_amount
                    b['count'] += 1
                    b['ids'].append(line.id)
                    break
            row = by_client.setdefault(line.customer_id.id, {
                'client': line.customer_id.name or 'Unknown', 'amount': 0.0, 'oldest': days, 'ids': [], 'units': {}})
            row['amount'] += line.remaining_amount
            row['oldest'] = max(row['oldest'], days)
            row['ids'].append(line.id)
            unit = row['units'].setdefault(line.unit_id.system_code or '-', {'amount': 0.0, 'ids': []})
            unit['amount'] += line.remaining_amount
            unit['ids'].append(line.id)

        total = sum(b['amount'] for b in buckets)
        ageing = [{
            'label': b['label'], 'amount': b['amount'], 'count': b['count'], 'color': b['color'],
            'pct': _pct(b['amount'], total),
            'drill': _drill('Overdue %s' % b['label'], 'installment.lines', [('id', 'in', b['ids'])]),
        } for b in buckets]
        top = []
        for row in sorted(by_client.values(), key=lambda r: -r['amount'])[:5]:
            top.append({
                'client': row['client'], 'amount': row['amount'], 'oldest': row['oldest'],
                'drill': _drill('Overdue installments of %s' % row['client'], 'installment.lines',
                                [('id', 'in', row['ids'])]),
                'units': [{'unit': u, 'amount': v['amount'],
                           'drill': _drill('Overdue %s' % u, 'installment.lines', [('id', 'in', v['ids'])])}
                          for u, v in sorted(row['units'].items(), key=lambda kv: -kv[1]['amount'])],
            })
        return {
            'total': total, 'count': len(lines), 'clients': len(by_client),
            'drill': _drill('Overdue installments', 'installment.lines', [('id', 'in', lines.ids)]),
            'ageing': ageing, 'top_clients': top,
        }

    @api.model
    def get_pipeline(self, project_id=None):
        """Deals before they are signed (reservations, drafts, approval steps) and cancellations."""
        Contract = self.env['sale.proposal']
        Reservation = self.env['real.estate.sale.reservation']
        project_c = [('unit_id.project_id', '=', project_id)] if project_id else []

        stages = []
        res_labels = dict(Reservation._fields['state'].selection)
        for state in ('draft', 'reserved'):
            recs = Reservation.search(project_c + [('state', '=', state)])
            if recs:
                stages.append({
                    'label': 'Reservation - %s' % res_labels.get(state, state), 'count': len(recs),
                    'value': sum(recs.mapped('price_after_discount')), 'counted_as_sold': False,
                    'drill': _drill('Reservations: %s' % res_labels.get(state, state), 'real.estate.sale.reservation',
                                    [('id', 'in', recs.ids)]),
                })
        c_labels = dict(Contract._fields['state'].selection)
        order = [k for k, _l in Contract._fields['state'].selection]
        groups = Contract._read_group(project_c + [('state', 'not in', ['cancelled', 'terminated', 'signed_client'])],
                                      ['state'], ['id:count', 'price_after_discount:sum'])
        for state, count, value in sorted(groups, key=lambda g: order.index(g[0]) if g[0] in order else 99):
            stages.append({
                'label': 'Contract - %s' % c_labels.get(state, state), 'count': count, 'value': value or 0.0,
                'counted_as_sold': state not in EXCLUDED_STATES,
                'drill': _drill('Contracts: %s' % c_labels.get(state, state), 'sale.proposal',
                                project_c + [('state', '=', state)]),
            })

        cancelled = Contract.search(project_c + [('state', 'in', ['cancelled', 'terminated'])])
        cancelled = cancelled.sorted(key=lambda c: c.cancelled_date or c.termination_date or fields.Date.today(), reverse=True)
        return {
            'stages': stages,
            'cancelled': {
                'count': len(cancelled), 'value': sum(cancelled.mapped('price_after_discount')),
                'drill': _drill('Cancelled and terminated contracts', 'sale.proposal', [('id', 'in', cancelled.ids)]),
                'rows': [{
                    'client': c.customer_id.name or '', 'unit': c.unit_id.system_code or '',
                    'date': c.cancelled_date or c.termination_date, 'reason': c.cancellation_reason or '',
                    'value': c.price_after_discount or 0.0,
                    'drill': _drill('Contract %s' % c.name, 'sale.proposal', [], res_id=c.id),
                } for c in cancelled[:6]],
            },
        }
