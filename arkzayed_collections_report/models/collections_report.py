from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

# Contracts whose installments are real receivables (drafts, cancelled and terminated are excluded).
ACTIVE_STATES = [
    'approved', 'signed_client', 'operation_review', 'finance_review', 'top_management',
    'signed_ceo', 'ready_to_deliver_contract', 'sent_to_client', 'delivered_contract',
    'ready_to_deliver', 'delivered',
]
DETAIL_LIMIT = 250
SUSPICIOUS_YEAR = 2060  # due dates beyond this are almost certainly typing mistakes
MONTHS_BACK = 12

def manual_paid_events(lines, until=None):
    """(line, amount, date) for the part of a ticked installment that no payment or cheque covers.

    An installment ticked "Paid" counts as fully collected, so the uncovered part is money that
    has no payment date of its own: it is dated on the installment's own due date. ``until``
    leaves out installments due later than that date (a tick on a future installment is only
    collected money once its due date is reached).
    """
    events = []
    for line in lines:
        if line.paid and line.date and (not until or line.date <= until):
            amount = line.remaining_amount or 0.0
            if amount > 0.01:
                events.append((line, amount, line.date))
    return events


class ReportCollections(models.AbstractModel):
    _name = 'report.arkzayed_collections_report.report_collections'
    _description = 'Collections Executive Report'

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
        far_future = today.replace(year=SUSPICIOUS_YEAR)
        lines = self._get_lines(data)
        company = self.env.company
        currency = company.currency_id

        # --- money in / cheques in hand, through allocations (same rules as installment.lines) ---
        cheque_in_hand = defaultdict(float)
        matured_in_hand = defaultdict(float)
        monthly = defaultdict(float)
        first_month = (today.replace(day=1) - relativedelta(months=MONTHS_BACK - 1))
        allocations = self.env['payment.allocation'].search([('installment_id', 'in', lines.ids)])
        for alloc in allocations:
            amount = alloc.allocated_amount
            if alloc.payment_id and alloc.payment_id.state == 'paid':
                payment = alloc.payment_id
                entry = payment.move_id
                # Posting an installment payment flags its journal entry as "Is Collection".
                collected_on = entry.date if entry.is_collection and entry.state == 'posted' else payment.date
            elif alloc.cheque_id and alloc.cheque_id.state == 'done':
                # Collecting a cheque flags its (last) journal entry as "Is Collection"; the date of
                # that entry is the collection date.
                cheque = alloc.cheque_id
                entries = cheque.move_line_ids.mapped('move_id').filtered(
                    lambda m: m.is_collection and m.state == 'posted')
                if entries:
                    collected_on = entries.sorted('id')[-1].date
                else:
                    # No flagged entry: a cheque cannot be collected before it is received nor before
                    # its cheque date, so the later of the two is the best estimate.
                    candidates = [d for d in (cheque.cheque_date, cheque.cheque_receive_date) if d]
                    collected_on = cheque.cashed_date or (max(candidates) if candidates else False)
            elif alloc.cheque_id and alloc.cheque_id.state == 'collect':
                cheque_in_hand[alloc.installment_id.id] += amount
                if alloc.cheque_id.cheque_date and alloc.cheque_id.cheque_date <= today:
                    matured_in_hand[alloc.installment_id.id] += amount
                continue
            else:
                continue
            if collected_on and collected_on >= first_month:
                monthly[collected_on.strftime('%Y-%m')] += amount

        for _line, amount, when in manual_paid_events(lines, until=today):
            if when >= first_month:
                monthly[when.strftime('%Y-%m')] += amount

        # --- totals ---
        total = collected = outstanding = due_total = due_collected = overdue = 0.0
        ageing = [
            {'label': '1 - 30 days', 'lo': 1, 'hi': 30, 'amount': 0.0, 'count': 0, 'clients': set()},
            {'label': '31 - 60 days', 'lo': 31, 'hi': 60, 'amount': 0.0, 'count': 0, 'clients': set()},
            {'label': '61 - 90 days', 'lo': 61, 'hi': 90, 'amount': 0.0, 'count': 0, 'clients': set()},
            {'label': 'Over 90 days', 'lo': 91, 'hi': 10 ** 6, 'amount': 0.0, 'count': 0, 'clients': set()},
        ]
        upcoming = [
            {'label': 'Next 30 days', 'lo': 0, 'hi': 30, 'amount': 0.0, 'count': 0},
            {'label': '31 - 60 days', 'lo': 31, 'hi': 60, 'amount': 0.0, 'count': 0},
            {'label': '61 - 90 days', 'lo': 61, 'hi': 90, 'amount': 0.0, 'count': 0},
            {'label': 'Later', 'lo': 91, 'hi': 10 ** 6, 'amount': 0.0, 'count': 0},
        ]
        check_date_count, check_date_amount = 0, 0.0
        clients = {}
        buildings = {}
        overdue_rows = []
        hand_total = matured_total = 0.0

        for line in lines:
            recorded_paid = line.paid_amount or 0.0
            recorded_remaining = line.remaining_amount or 0.0
            line_total = recorded_paid + recorded_remaining
            # An installment flagged Paid counts as fully collected, as the company does.
            settled = bool(line.paid) or recorded_remaining <= 0
            paid = line_total if settled else recorded_paid
            remaining = 0.0 if settled else recorded_remaining
            total += line_total
            collected += paid
            outstanding += remaining
            hand_total += cheque_in_hand.get(line.id, 0.0)
            matured_total += matured_in_hand.get(line.id, 0.0)

            building = line.unit_id.building_id
            brow = buildings.setdefault(building.id or 0, {
                'name': building.system_code or building.display_name or 'No building',
                'units': set(), 'total': 0.0, 'collected': 0.0, 'outstanding': 0.0, 'due': 0.0,
                'due_collected': 0.0, 'overdue': 0.0,
            })
            brow['units'].add(line.unit_id.id)
            brow['total'] += line_total
            brow['collected'] += paid
            brow['outstanding'] += remaining

            if not line.date:
                continue
            if line.date > far_future:
                if remaining > 0:
                    check_date_count += 1
                    check_date_amount += remaining
                continue
            if line.date <= today:
                due_total += line_total
                due_collected += paid
                brow['due'] += line_total
                brow['due_collected'] += paid

            if remaining <= 0:
                continue
            if line.date < today:
                days = (today - line.date).days
                overdue += remaining
                brow['overdue'] += remaining
                for bucket in ageing:
                    if bucket['lo'] <= days <= bucket['hi']:
                        bucket['amount'] += remaining
                        bucket['count'] += 1
                        bucket['clients'].add(line.customer_id.id)
                        break
                crow = clients.setdefault(line.customer_id.id, {
                    'name': line.customer_id.name or 'Unknown', 'units': set(), 'count': 0,
                    'amount': 0.0, 'oldest': 0, 'in_hand': 0.0,
                })
                crow['units'].add(line.unit_id.system_code)
                crow['count'] += 1
                crow['amount'] += remaining
                crow['oldest'] = max(crow['oldest'], days)
                crow['in_hand'] += cheque_in_hand.get(line.id, 0.0)
                overdue_rows.append({
                    'client': line.customer_id.name or '', 'unit': line.unit_id.system_code or '',
                    'name': line.name or ('#%s' % line.serial), 'date': line.date, 'days': days,
                    'total': line_total, 'paid': paid, 'remaining': remaining,
                    'in_hand': cheque_in_hand.get(line.id, 0.0),
                    'is_down_payment': line.is_down_payment,
                })
            else:
                ahead = (line.date - today).days
                for bucket in upcoming:
                    if bucket['lo'] <= ahead <= bucket['hi']:
                        bucket['amount'] += remaining
                        bucket['count'] += 1
                        break

        def pct(part, whole):
            return part / whole * 100 if whole else 0.0

        for bucket in ageing:
            bucket['clients'] = len(bucket['clients'])
            bucket['share'] = pct(bucket['amount'], overdue)
        max_upcoming = max([b['amount'] for b in upcoming] or [0]) or 1
        for bucket in upcoming:
            bucket['bar'] = bucket['amount'] / max_upcoming * 100

        months = []
        cursor = first_month
        while cursor <= today.replace(day=1):
            months.append({'label': cursor.strftime('%b %Y'), 'amount': monthly.get(cursor.strftime('%Y-%m'), 0.0)})
            cursor += relativedelta(months=1)
        max_month = max([m['amount'] for m in months] or [0]) or 1
        for month in months:
            month['bar'] = month['amount'] / max_month * 100

        top_clients = sorted(clients.values(), key=lambda c: -c['amount'])[:10]
        for c in top_clients:
            c['unit_count'] = len(c['units'])
            c['share'] = pct(c['amount'], overdue)

        building_rows = sorted(buildings.values(), key=lambda b: -b['overdue'])
        for b in building_rows:
            b['unit_count'] = len(b['units'])
            b['rate'] = pct(b['collected'], b['total'])
            b['due_rate'] = pct(b['due_collected'], b['due'])

        overdue_rows.sort(key=lambda r: -r['remaining'])
        filters = []
        if data.get('project_id'):
            filters.append(self.env['realestate.project'].browse(data['project_id']).display_name)
        if data.get('building_ids'):
            filters.append(', '.join(self.env['real.estate.building'].browse(data['building_ids']).mapped('system_code')))
        if data.get('customer_ids'):
            filters.append(', '.join(self.env['res.partner'].browse(data['customer_ids']).mapped('name')))

        return {
            'doc_ids': docids,
            'doc_model': 'arkzayed.collections.report.wizard',
            'docs': self.env['arkzayed.collections.report.wizard'].browse(docids),
            'company': company,
            'currency': currency,
            'today': today,
            'user_name': self.env.user.name,
            'filters': ' | '.join(filters),
            'total': total,
            'collected': collected,
            'collected_pct': pct(collected, total),
            'outstanding': outstanding,
            'due_total': due_total,
            'due_collected': due_collected,
            'overdue': overdue,
            'overdue_pct': pct(overdue, due_total),
            'efficiency': pct(due_collected, due_total),
            'hand_total': hand_total,
            'matured_total': matured_total,
            'installment_count': len(lines),
            'client_count': len(set(lines.mapped('customer_id').ids)),
            'overdue_count': len(overdue_rows),
            'overdue_client_count': len(clients),
            'ageing': ageing,
            'upcoming': upcoming,
            'months': months,
            'top_clients': top_clients,
            'building_rows': building_rows,
            'overdue_rows': overdue_rows[:DETAIL_LIMIT],
            'overdue_hidden': max(0, len(overdue_rows) - DETAIL_LIMIT),
            'check_date_count': check_date_count,
            'check_date_amount': check_date_amount,
        }
