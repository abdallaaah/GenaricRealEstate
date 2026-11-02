from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

HORIZON = 12
MONTHS_BACK = 6
UNDER_COLLECTION_STATES = ('register', 'under_collection', 'deposit', 'sent')
RETURNED_STATES = ('return', 'return_to_client', 'bounce')
ACTIVE_STATES = [
    'approved', 'signed_client', 'operation_review', 'finance_review', 'top_management',
    'signed_ceo', 'ready_to_deliver_contract', 'sent_to_client', 'delivered_contract',
    'ready_to_deliver', 'delivered',
]
SUSPICIOUS_YEAR = 2060


class ReportCash(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.report_cash'
    _description = 'Cash Executive Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        env = self.env
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        today = now.date()
        this_month = today.replace(day=1)
        company = env.company
        currency = company.currency_id
        Move, Line = env['account.move'], env['account.move.line']

        # --- cash and bank today ---
        liquidity = env['account.account'].search([('account_type', '=', 'asset_cash')])
        bal = Line._read_group(
            [('account_id', 'in', liquidity.ids), ('parent_state', '=', 'posted'), ('date', '<=', today)],
            ['account_id'], ['balance:sum'])
        cash_rows = sorted(
            [{'code': acc.code or '', 'name': acc.name or '', 'balance': b}
             for acc, b in bal if abs(b) > 0.005], key=lambda r: -r['balance'])
        cash_total = sum(r['balance'] for r in cash_rows)

        # --- monthly cash in / out (real inflow/outflow: transfers between liquidity accounts excluded) ---
        first_month = this_month - relativedelta(months=MONTHS_BACK - 1)
        flow = defaultdict(lambda: [0.0, 0.0])
        lines = Line.search([
            ('account_id', 'in', liquidity.ids), ('parent_state', '=', 'posted'),
            ('date', '>=', first_month), ('date', '<=', today)])
        for move, mlines in lines.grouped('move_id').items():
            if not (move.line_ids - move.line_ids.filtered(lambda l: l.account_id in liquidity)):
                continue  # pure transfer between cash/bank accounts
            key = move.date.strftime('%Y-%m')
            flow[key][0] += sum(mlines.mapped('debit'))
            flow[key][1] += sum(mlines.mapped('credit'))
        def balance_as_of(as_of_date):
            res = Line._read_group(
                [('account_id', 'in', liquidity.ids), ('parent_state', '=', 'posted'), ('date', '<=', as_of_date)],
                [], ['balance:sum'])
            return res[0][0] if res else 0.0

        flow_rows, cursor = [], first_month
        while cursor <= this_month:
            k = cursor.strftime('%Y-%m')
            month_end = cursor + relativedelta(months=1) - relativedelta(days=1)
            flow_rows.append({
                'label': cursor.strftime('%b %Y'), 'in': flow[k][0], 'out': flow[k][1],
                'net': flow[k][0] - flow[k][1],
                'opening': balance_as_of(cursor - relativedelta(days=1)),
                'closing': balance_as_of(min(month_end, today)),
            })
            cursor += relativedelta(months=1)
        max_flow = max([max(r['in'], r['out']) for r in flow_rows] or [0]) or 1
        for r in flow_rows:
            r['in_bar'] = r['in'] / max_flow * 100
            r['out_bar'] = r['out'] / max_flow * 100

        # --- cheques (incoming) ---
        cheques = env['cheque.manage'].search([('cheq_type', '=', 'incoming')])
        by_state = defaultdict(lambda: [0, 0.0])
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
        status_rows = [
            {'label': 'Draft (not received yet)', 'key': 'draft', 'color': '#9ca3af'},
            {'label': 'Received (in hand)', 'key': 'collect', 'color': '#0f2a4a'},
            {'label': 'Under collection / Deposited', 'key': 'under', 'color': '#0d9488'},
            {'label': 'To Hermes', 'key': 'hermes', 'color': '#8b5cf6'},
            {'label': 'To Adib', 'key': 'to_adib', 'color': '#0ea5e9'},
            {'label': 'Collected', 'key': 'done', 'color': '#059669'},
            {'label': 'Returned / Bounced', 'key': 'returned', 'color': '#dc2626'},
        ]
        for r in status_rows:
            r['count'], r['amount'] = by_state[r['key']]

        in_hand = cheques.filtered(lambda c: c.state == 'collect' and c.cycle_type != 'hermes')
        draft = cheques.filtered(lambda c: c.state == 'draft')
        expected = in_hand | draft if data.get('include_draft') else in_hand
        horizon_end = this_month + relativedelta(months=HORIZON)
        cheque_month = defaultdict(float)
        matured = later = far = 0.0
        matured_count = 0
        for c in expected:
            d, amount = c.cheque_date, c.amount or 0.0
            if not d:
                continue
            if d.year > SUSPICIOUS_YEAR:
                far += amount
            elif d <= today:
                matured += amount
                matured_count += 1
            elif d >= horizon_end:
                later += amount
            else:
                cheque_month[d.strftime('%Y-%m')] += amount

        # --- installments still to collect, by due month ---
        inst = env['installment.lines'].search([('contract_state', 'in', ACTIVE_STATES), ('paid', '=', False),
                                                ('remaining_amount', '>', 0)])
        inst_overdue = 0.0
        inst_month = defaultdict(float)
        for line in inst:
            if not line.date or line.date.year > SUSPICIOUS_YEAR:
                continue
            if line.date <= today:
                inst_overdue += line.remaining_amount
            elif line.date < horizon_end:
                inst_month[line.date.strftime('%Y-%m')] += line.remaining_amount

        # --- supplier bills ---
        bills = Move.search([('move_type', '=', 'in_invoice'), ('state', '=', 'posted'),
                             ('payment_state', 'in', ('not_paid', 'partial'))])
        pay_overdue = pay_total = 0.0
        pay_month = defaultdict(float)
        vendors = defaultdict(lambda: [0.0, 0.0, 0])
        for b in bills:
            amount = b.amount_residual
            pay_total += amount
            due = b.invoice_date_due or b.invoice_date or today
            v = vendors[b.partner_id.name or 'Unknown']
            v[0] += amount
            v[2] += 1
            if due <= today:
                pay_overdue += amount
                v[1] += amount
            elif due < horizon_end:
                pay_month[due.strftime('%Y-%m')] += amount
        vendor_rows = sorted(
            [{'name': n, 'total': v[0], 'overdue': v[1], 'count': v[2]} for n, v in vendors.items()],
            key=lambda r: -r['total'])[:8]

        # --- 12 month outlook ---
        outlook, cursor = [], this_month
        cumulative = cash_total + matured - pay_overdue
        for _i in range(HORIZON):
            k = cursor.strftime('%Y-%m')
            net = cheque_month[k] - pay_month[k]
            cumulative += net
            outlook.append({
                'label': cursor.strftime('%b %Y') + (' (rest of month)' if cursor == this_month else ''), 'cheques': cheque_month[k], 'inst': inst_month[k],
                'coverage': cheque_month[k] / inst_month[k] * 100 if inst_month[k] else None,
                'bills': pay_month[k], 'net': net, 'cumulative': cumulative,
            })
            cursor += relativedelta(months=1)

        return {
            'doc_ids': docids,
            'doc_model': 'arkzayed.cash.report.wizard',
            'docs': env['arkzayed.cash.report.wizard'].browse(docids),
            'company': company, 'currency': currency,
            'as_of': now.strftime('%d %b %Y, %H:%M'), 'user_name': env.user.name,
            'include_draft': bool(data.get('include_draft')),
            'cash_rows': cash_rows, 'cash_total': cash_total,
            'flow_rows': flow_rows,
            'status_rows': status_rows,
            'cheque_total_count': len(cheques),
            'in_hand_total': sum(in_hand.mapped('amount')), 'in_hand_count': len(in_hand),
            'matured': matured, 'matured_count': matured_count, 'later': later, 'far': far,
            'inst_overdue': inst_overdue,
            'pay_total': pay_total, 'pay_overdue': pay_overdue, 'pay_count': len(bills),
            'vendor_rows': vendor_rows,
            'outlook': outlook,
            'outlook_cheques': sum(r['cheques'] for r in outlook),
            'outlook_bills': sum(r['bills'] for r in outlook),
            'horizon': HORIZON,
            'opening': cash_total + matured - pay_overdue,
        }