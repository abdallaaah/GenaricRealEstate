from collections import defaultdict

from odoo import api, fields, models

from .collections_report import ACTIVE_STATES, SUSPICIOUS_YEAR, DETAIL_LIMIT, manual_paid_events


class ReportCollectionsPeriod(models.AbstractModel):
    _name = 'report.arkzayed_collections_report.report_collections_period'
    _description = 'Monthly Report Collections'

    @api.model
    def _get_lines(self, data):
        domain = [('contract_state', 'in', ACTIVE_STATES)]
        if data.get('project_id'):
            domain.append(('unit_id.project_id', '=', data['project_id']))
        if data.get('building_ids'):
            domain.append(('unit_id.building_id', 'in', data['building_ids']))
        if data.get('customer_ids'):
            domain.append(('customer_id', 'in', data['customer_ids']))
        return self.env['installment.lines'].search(domain)

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        today = fields.Date.context_today(self)
        date_from = fields.Date.from_string(data['date_from'])
        date_to = fields.Date.from_string(data['date_to'])
        far_future = today.replace(year=SUSPICIOUS_YEAR)
        lines = self._get_lines(data)
        company = self.env.company
        currency = company.currency_id

        # --- collection events, dated exactly like the executive Collections Report ---
        collected_on_by_line = {}
        collections_in_period = 0.0
        collections_by_day = defaultdict(float)
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
            if not collected_on:
                continue
            if collected_on >= date_from and collected_on <= date_to:
                collections_in_period += amount
                collections_by_day[collected_on] += amount
                collected_on_by_line[alloc.installment_id.id] = collected_on_by_line.get(
                    alloc.installment_id.id, 0.0) + amount

        # an installment ticked Paid counts as collected on its own due date for the part no
        # payment or cheque covers; the period below keeps only the due dates inside the report
        for line, amount, when in manual_paid_events(lines):
            if date_from <= when <= date_to:
                collections_in_period += amount
                collections_by_day[when] += amount
                collected_on_by_line[line.id] = collected_on_by_line.get(line.id, 0.0) + amount

        # group the "collected in period" timeline: daily if the period is short, monthly otherwise
        span_days = (date_to - date_from).days + 1
        by_month = span_days > 62
        buckets = defaultdict(float)
        for d, amount in collections_by_day.items():
            key = d.strftime('%Y-%m') if by_month else d.isoformat()
            buckets[key] += amount
        timeline = []
        for key in sorted(buckets.keys()):
            if by_month:
                label = fields.Date.from_string(key + '-01').strftime('%b %Y')
            else:
                label = fields.Date.from_string(key).strftime('%d %b')
            timeline.append({'label': label, 'amount': buckets[key]})
        max_bucket = max([t['amount'] for t in timeline] or [0]) or 1
        for t in timeline:
            t['bar'] = t['amount'] / max_bucket * 100

        # --- installments due within the period: fully / partially / not collected ---
        due_rows = []
        due_total = due_collected = due_remaining = 0.0
        fully_n = partial_n = none_n = 0
        fully_amt = partial_collected_amt = partial_remaining_amt = none_amt = 0.0
        for line in lines:
            if not line.date or line.date > far_future:
                continue
            if not (date_from <= line.date <= date_to):
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

            if settled:
                status = 'fully'
                fully_n += 1
                fully_amt += line_total
            elif paid > 0:
                status = 'partial'
                partial_n += 1
                partial_collected_amt += paid
                partial_remaining_amt += remaining
            else:
                status = 'none'
                none_n += 1
                none_amt += line_total

            due_rows.append({
                'client': line.customer_id.name or '', 'unit': line.unit_id.system_code or '',
                'name': line.name or ('#%s' % line.serial), 'due_date': line.date,
                'total': line_total, 'collected': paid, 'remaining': remaining, 'status': status,
            })

        status_order = {'partial': 0, 'none': 1, 'fully': 2}
        due_rows.sort(key=lambda r: (status_order[r['status']], -r['remaining']))

        def pct(part, whole):
            return part / whole * 100 if whole else 0.0

        filters = []
        if data.get('project_id'):
            filters.append(self.env['realestate.project'].browse(data['project_id']).display_name)
        if data.get('building_ids'):
            filters.append(', '.join(self.env['real.estate.building'].browse(data['building_ids']).mapped('system_code')))
        if data.get('customer_ids'):
            filters.append(', '.join(self.env['res.partner'].browse(data['customer_ids']).mapped('name')))

        return {
            'doc_ids': docids,
            'doc_model': 'arkzayed.collections.period.wizard',
            'docs': self.env['arkzayed.collections.period.wizard'].browse(docids),
            'company': company,
            'currency': currency,
            'today': today,
            'date_from': date_from,
            'date_to': date_to,
            'user_name': self.env.user.name,
            'filters': ' | '.join(filters),
            'collections_in_period': collections_in_period,
            'timeline': timeline,
            'by_month': by_month,
            'due_total': due_total,
            'due_collected': due_collected,
            'due_remaining': due_remaining,
            'due_collected_pct': pct(due_collected, due_total),
            'fully_n': fully_n, 'fully_amt': fully_amt,
            'partial_n': partial_n, 'partial_collected_amt': partial_collected_amt,
            'partial_remaining_amt': partial_remaining_amt,
            'none_n': none_n, 'none_amt': none_amt,
            'due_rows': due_rows[:DETAIL_LIMIT],
            'due_hidden': max(0, len(due_rows) - DETAIL_LIMIT),
        }
