import base64
import io
from collections import OrderedDict

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.isky_18_realestate_developer_sales_crm.models.core.sale_proposal import COMMISSION_EXCLUDED_STATES

STATUS_PAID = 'Paid'
STATUS_PAID_OUT = 'Paid (outside system)'
STATUS_CONFIRMED = 'Not paid (confirmed)'
STATUS_DRAFT = 'Not paid (draft)'
STATUS_PENDING = 'Not claimed yet'
STATUS_NONE = 'No commission record'
PAID_STATUSES = (STATUS_PAID, STATUS_PAID_OUT)


class TraceCommissionLine(models.TransientModel):
    _name = 'trace.commission.line'
    _description = 'Trace Commission line'
    _order = 'person, contract_date, id'

    wizard_id = fields.Many2one('trace.commission', ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='wizard_id.currency_id')
    person = fields.Char()
    role = fields.Char()
    unit_id = fields.Many2one('real.estate.unit', string='Unit')
    contract_id = fields.Many2one('sale.proposal', string='Contract')
    customer = fields.Char()
    contract_date = fields.Date(string='Contract Date')
    price = fields.Monetary(string='Unit Price', currency_field='currency_id')
    share_pct = fields.Float(string='Share %', digits=(16, 2),
                             help='Share of the sale credited to this person. 100% unless the deal was split.')
    sold_value = fields.Monetary(string='Sold Value', currency_field='currency_id',
                                 help='Unit price x share. What this person is credited with.')
    commission_pct = fields.Float(string='Commission %', digits=(16, 2))
    commission_amount = fields.Monetary(string='Commission', currency_field='currency_id')
    status = fields.Char()
    note = fields.Char()
    is_paid = fields.Boolean()
    payment_date = fields.Date()
    res_model = fields.Char()
    res_id = fields.Integer()

    def action_open_source(self):
        self.ensure_one()
        if not (self.res_model and self.res_id):
            raise UserError(_('Nothing to open for this line (no claim has been created for it yet).'))
        return {'type': 'ir.actions.act_window', 'res_model': self.res_model, 'res_id': self.res_id,
                'view_mode': 'form', 'target': 'current'}


class TraceCommission(models.TransientModel):
    """Type one or more sales people, team leaders, managers, brokers or ambassadors and see every unit
    they sold with price, commission and whether the commission is paid."""
    _name = 'trace.commission'
    _description = 'Trace Commission'

    person_ids = fields.Many2many(
        'trace.commission.person', 'trace_commission_person_rel', 'wizard_id', 'person_id', string='Search',
        help='Sales person, team leader, manager, broker or ambassador. You can pick more than one.')
    role_ids = fields.Many2many(
        'trace.commission.role', 'trace_commission_role_rel', 'wizard_id', 'role_id', string='Everyone in a role',
        help='Pick a role (Broker, Sales Person, Sales Manager...) to include everybody who has it, on top of the '
             'people picked in the search.')
    people_count = fields.Integer(string='People included', compute='_compute_people_count')
    date_from = fields.Date(string='Contract date from')
    date_to = fields.Date(string='Contract date to')
    paid_filter = fields.Selection([('all', 'Paid and not paid'), ('paid', 'Paid only'), ('unpaid', 'Not paid only')],
                                   string='Show', default='all', required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    line_ids = fields.One2many('trace.commission.line', 'wizard_id', string='Units')

    unit_count = fields.Integer(string='Units', compute='_compute_totals')
    unit_equiv = fields.Float(string='Units (by share)', compute='_compute_totals', digits=(16, 2),
                              help='Every unit counted by the share credited: a unit split 50/50 counts 0.5.')
    total_price = fields.Monetary(string='Total Sold Value', compute='_compute_totals', currency_field='currency_id')
    total_commission = fields.Monetary(string='Total Commission', compute='_compute_totals', currency_field='currency_id')
    total_paid = fields.Monetary(string='Paid', compute='_compute_totals', currency_field='currency_id')
    total_unpaid = fields.Monetary(string='Not Paid', compute='_compute_totals', currency_field='currency_id')

    excel_file = fields.Binary(readonly=True)
    excel_filename = fields.Char()

    @api.depends('line_ids.sold_value', 'line_ids.share_pct', 'line_ids.commission_amount', 'line_ids.is_paid',
                 'line_ids.unit_id', 'line_ids.person', 'line_ids.contract_id')
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids
            # a sale counts once per person even when the person has two claims on the same contract
            sales = {}
            for l in lines:
                key = (l.person, l.contract_id.id)
                sales[key] = (max(sales.get(key, (0.0, 0.0))[0], l.share_pct), max(sales.get(key, (0.0, 0.0))[1], l.sold_value))
            rec.unit_count = len(lines.mapped('unit_id'))
            rec.unit_equiv = sum(share / 100.0 for share, _sold in sales.values())
            rec.total_price = sum(sold for _share, sold in sales.values())
            rec.total_commission = sum(lines.mapped('commission_amount'))
            rec.total_paid = sum(lines.filtered('is_paid').mapped('commission_amount'))
            rec.total_unpaid = rec.total_commission - rec.total_paid

    @api.depends('person_ids', 'role_ids')
    def _compute_display_name(self):
        for rec in self:
            names = rec.person_ids.mapped('name')[:3] or rec.role_ids.mapped('name')[:3]
            rec.display_name = ', '.join(names) or _('Trace Commission')

    def _people(self):
        """The people picked in the search plus everybody who has one of the picked roles."""
        self.ensure_one()
        people = self.person_ids
        if self.role_ids:
            domain = ['|'] * (len(self.role_ids) - 1) + [('kind', 'ilike', r.name) for r in self.role_ids]
            people |= self.env['trace.commission.person'].search(domain)
        return people

    @api.depends('person_ids', 'role_ids')
    def _compute_people_count(self):
        for rec in self:
            rec.people_count = len(rec._people())

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _date_domain(self, field):
        domain = []
        if self.date_from:
            domain.append((field, '>=', self.date_from))
        if self.date_to:
            domain.append((field, '<=', self.date_to))
        return domain

    @staticmethod
    def _row(person, role, contract, unit, price, amount, status, rec=None, payment_date=False, share=100.0):
        sold = (price or 0.0) * share / 100.0
        return {
            'person': person, 'role': role, 'unit_id': unit.id, 'unit': unit.system_code or unit.name or '',
            'contract_id': contract.id, 'contract': contract.name or '', 'customer': contract.customer_id.name or '',
            'contract_date': contract.contract_issue_date, 'price': price or 0.0, 'share_pct': share,
            'share_txt': '%g%%' % share, 'sold_value': sold,
            'commission_pct': (amount / sold * 100.0) if sold else 0.0, 'commission_amount': amount or 0.0,
            'status': status, 'note': '', 'is_paid': status in PAID_STATUSES, 'payment_date': payment_date,
            'res_model': rec._name if rec else False, 'res_id': rec.id if rec else 0,
        }

    def _claim_status(self, rec):
        if rec.state == 'paid':
            return STATUS_PAID_OUT if rec.paid_outside_system else STATUS_PAID
        return STATUS_CONFIRMED if rec.state == 'confirmed' else STATUS_DRAFT

    def _rows_for_user(self, person):
        """Staff: every contract where the person is on the commission lines (sales person, manager, director) or is the
        salesperson. The share comes from the contract's commission line, so a deal split 50/50 counts half for each."""
        Achievement = self.env['realestate.commission.achievement']
        Contract = self.env['sale.proposal']
        uid = person.source_id
        not_sales = ['draft', 'draft_contract', 'cancelled', 'terminated']
        contracts = Contract.search([
            ('state', 'not in', not_sales), '|', ('user_id', '=', uid), ('commission_ids.employee_id', '=', uid),
        ] + self._date_domain('contract_issue_date'))
        achievements = Achievement.search([('user_id', '=', uid), ('state', '!=', 'cancelled'),
                                           ('sale_proposal_id', '!=', False)] +
                                          self._date_domain('sale_proposal_id.contract_issue_date'))
        by_contract = {a.sale_proposal_id.id: a for a in achievements}
        contracts |= achievements.mapped('sale_proposal_id')
        rows = []
        for contract in contracts:
            lines = contract.commission_ids.filtered(lambda l: l.employee_id.id == uid)
            share = max(lines.mapped('commission')) if lines else 100.0
            a = by_contract.get(contract.id)
            role = (a.job_level_id.name if a and a.job_level_id else False) or (lines[:1].jop_position if lines else False) \
                or _('Sales Person')
            if contract.split_deal and share < 100.0:
                role = '%s (split %s%%)' % (role, ('%g' % share))
            if a:
                rows.append(self._row(person.name, role, contract, contract.unit_id, contract.price_after_discount,
                                      a.total_commission_amount, self._claim_status(a), a, a.payment_date, share))
            else:
                rows.append(self._row(person.name, role, contract, contract.unit_id, contract.price_after_discount,
                                      0.0, STATUS_NONE, share=share))
        return rows

    def _rows_for_employee(self, person):
        Claim = self.env['broker.claim']
        domain = [('claim_type', '=', 'employee'), ('employee_id', '=', person.source_id), ('state', '!=', 'cancelled')] + \
            self._date_domain('sale_proposal_id.contract_issue_date')
        rows = []
        for c in Claim.search(domain):
            contract = c.sale_proposal_id
            if contract:
                rows.append(self._row(person.name, _('Employee'), contract, c.unit_id, c.unit_sold_price,
                                      c.commission_amount, self._claim_status(c), c, c.payment_date))
        return rows

    def _rows_for_partner(self, person):
        Claim = self.env['broker.claim']
        Contract = self.env['sale.proposal']
        type_labels = dict(Claim._fields['claim_type'].selection)
        rows, claimed = [], set()
        domain = [('broker_company', '=', person.source_id), ('claim_type', 'in', ['broker', 'ambassador', 'agent']),
                  ('state', '!=', 'cancelled')] + self._date_domain('sale_proposal_id.contract_issue_date')
        for c in Claim.search(domain):
            contract = c.sale_proposal_id
            if not contract:
                continue
            claimed.add((contract.id, c.claim_type))
            rows.append(self._row(person.name, type_labels.get(c.claim_type, c.claim_type), contract, c.unit_id,
                                  c.unit_sold_price, c.commission_amount, self._claim_status(c), c, c.payment_date))
        # contracts this broker / ambassador brought whose claim has not been raised yet: expected commission
        for kind, flag in (('broker', 'broker_claim_created'), ('ambassador', 'ambassador_claim_created')):
            cdom = [('referred_by', '=', kind), ('referred_by_partner_id', '=', person.source_id), (flag, '=', False),
                    ('state', 'not in', list(COMMISSION_EXCLUDED_STATES))] + self._date_domain('contract_issue_date')
            for contract in Contract.search(cdom):
                if (contract.id, kind) in claimed or Claim.search_count([
                        ('sale_proposal_id', '=', contract.id), ('claim_type', '=', kind), ('state', '!=', 'cancelled')]):
                    continue
                broker_contract = contract.broker_contract_id if kind == 'broker' else False
                if not broker_contract:
                    for ref_date in filter(None, (contract.contract_issue_date, fields.Date.today())):
                        broker_contract = self.env['broker.contract'].search([
                            ('broker_company', '=', person.source_id), ('contract_start_date', '<=', ref_date),
                            ('contract_end_date', '>=', ref_date)], limit=1)
                        if broker_contract:
                            break
                pct = contract._get_applicable_commission(broker_contract) if broker_contract else 0.0
                price = contract.price_after_discount or 0.0
                rows.append(self._row(person.name, type_labels.get(kind, kind), contract, contract.unit_id, price,
                                      price * pct / 100.0, STATUS_PENDING))
        return rows

    def _collect_rows(self):
        """One list of rows per selected person, honouring the date range and the paid filter."""
        self.ensure_one()
        groups = OrderedDict()
        for person in self._people():
            if person.source == 'user':
                rows = self._rows_for_user(person)
            elif person.source == 'employee':
                rows = self._rows_for_employee(person)
            else:
                rows = self._rows_for_partner(person)
            seen = {}
            for r in rows:
                seen[(r['contract_id'], r['role'])] = seen.get((r['contract_id'], r['role']), 0) + 1
            for r in rows:
                if seen[(r['contract_id'], r['role'])] > 1:
                    r['note'] = _('Duplicate: more than one claim on this contract')
            if self.paid_filter == 'paid':
                rows = [r for r in rows if r['is_paid']]
            elif self.paid_filter == 'unpaid':
                rows = [r for r in rows if not r['is_paid'] and r['status'] != STATUS_NONE]
            rows.sort(key=lambda r: (r['contract_date'] or fields.Date.today(), r['unit']))
            groups[person.id] = {'name': person.name, 'role': person.kind, 'rows': rows}
        return groups

    def _refresh_lines(self):
        for rec in self:
            commands = [(5, 0, 0)]
            for group in rec._collect_rows().values():
                for r in group['rows']:
                    commands.append((0, 0, {k: v for k, v in r.items() if k not in ('unit', 'contract', 'share_txt')}))
            rec.line_ids = commands

    @api.onchange('person_ids', 'role_ids', 'date_from', 'date_to', 'paid_filter')
    def _onchange_refresh(self):
        self._refresh_lines()

    # The list is read-only, so the browser does not send it back when the form is saved: rebuild it on the server,
    # otherwise Save would leave an empty form.
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_lines()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'person_ids', 'role_ids', 'date_from', 'date_to', 'paid_filter'} & set(vals):
            self._refresh_lines()
        return result

    def action_search(self):
        self.ensure_one()
        self._refresh_lines()
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'current'}

    # ------------------------------------------------------------------
    # Exports
    # ------------------------------------------------------------------
    @staticmethod
    def _totals(rows):
        total = sum(r['commission_amount'] for r in rows)
        paid = sum(r['commission_amount'] for r in rows if r['is_paid'])
        sales = {}   # a sale counts once per person, even with two claims on the same contract
        for r in rows:
            key = (r['person'], r['contract_id'])
            old = sales.get(key, (0.0, 0.0))
            sales[key] = (max(old[0], r['share_pct']), max(old[1], r['sold_value']))
        return {'units': len({r['unit_id'] for r in rows}), 'equiv': sum(s[0] / 100.0 for s in sales.values()),
                'price': sum(s[1] for s in sales.values()), 'commission': total, 'paid': paid, 'unpaid': total - paid}

    def _report_data(self):
        self.ensure_one()
        groups = self._collect_rows()
        all_rows = [r for g in groups.values() for r in g['rows']]
        for g in groups.values():
            g['totals'] = self._totals(g['rows'])
        fmt = '{:,.0f}'.format
        return {
            'groups': list(groups.values()), 'grand': self._totals(all_rows), 'fmt': fmt,
            'period': ('%s - %s' % (self.date_from.strftime('%d/%m/%Y') if self.date_from else '...',
                                    self.date_to.strftime('%d/%m/%Y') if self.date_to else '...'))
            if (self.date_from or self.date_to) else _('All dates'),
            'show': dict(self._fields['paid_filter'].selection).get(self.paid_filter),
            'printed_on': fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d/%m/%Y %H:%M'),
            'company': self.company_id.name,
        }

    def action_print_pdf(self):
        self.ensure_one()
        if not self._people():
            raise UserError(_('Pick at least one person or role first.'))
        return self.env.ref('arkzayed_trace_commission.action_report_trace_commission').report_action(self)

    def action_export_excel(self):
        self.ensure_one()
        if not self._people():
            raise UserError(_('Pick at least one person or role first.'))
        data = self._report_data()
        out = io.BytesIO()
        wb = xlsxwriter.Workbook(out, {'in_memory': True})
        title = wb.add_format({'bold': True, 'font_size': 13})
        head = wb.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#0F2A4A', 'border': 1, 'text_wrap': True})
        txt = wb.add_format({'border': 1})
        money = wb.add_format({'border': 1, 'num_format': '#,##0'})
        pct = wb.add_format({'border': 1, 'num_format': '0.00'})
        date = wb.add_format({'border': 1, 'num_format': 'dd/mm/yyyy'})
        green = wb.add_format({'border': 1, 'num_format': '#,##0', 'bg_color': '#E3F6EA', 'font_color': '#15803D'})
        red = wb.add_format({'border': 1, 'num_format': '#,##0', 'bg_color': '#FDE8E8', 'font_color': '#B91C1C', 'bold': True})
        green_t = wb.add_format({'border': 1, 'font_color': '#15803D', 'bold': True})
        red_t = wb.add_format({'border': 1, 'font_color': '#B91C1C', 'bold': True})
        bold = wb.add_format({'border': 1, 'bold': True, 'bg_color': '#EEF2F7'})
        bold_m = wb.add_format({'border': 1, 'bold': True, 'bg_color': '#EEF2F7', 'num_format': '#,##0'})

        s = wb.add_worksheet('Summary')
        s.write(0, 0, _('Trace Commission'), title)
        s.write(1, 0, _('Contract date: %s') % data['period'])
        for c, h in enumerate([_('Person'), _('Role'), _('Units'), _('Units (by share)'), _('Total sold value'),
                               _('Total commission'), _('Paid'), _('Not paid')]):
            s.write(3, c, h, head)
        r = 4
        for g in data['groups']:
            t = g['totals']
            s.write(r, 0, g['name'], txt); s.write(r, 1, g['role'], txt); s.write(r, 2, t['units'], txt)
            s.write(r, 3, round(t['equiv'], 2), pct); s.write(r, 4, t['price'], money); s.write(r, 5, t['commission'], money)
            s.write(r, 6, t['paid'], green if t['paid'] else money); s.write(r, 7, t['unpaid'], red if t['unpaid'] else money)
            r += 1
        t = data['grand']
        s.write(r, 0, _('Total'), bold); s.write(r, 1, '', bold); s.write(r, 2, t['units'], bold)
        s.write(r, 3, round(t['equiv'], 2), bold_m)
        for c, k in enumerate(('price', 'commission', 'paid', 'unpaid'), start=4):
            s.write(r, c, t[k], bold_m)
        s.set_column(0, 1, 30); s.set_column(2, 3, 12); s.set_column(4, 7, 20)

        w = wb.add_worksheet('Units')
        cols = [_('Person'), _('Role'), _('Unit'), _('Contract'), _('Customer'), _('Contract date'), _('Unit price'),
                _('Share %'), _('Sold value'), _('Commission %'), _('Commission'), _('Status'), _('Payment date'), _('Note')]
        for c, h in enumerate(cols):
            w.write(0, c, h, head)
        r = 1
        for g in data['groups']:
            for x in g['rows']:
                w.write(r, 0, x['person'], txt); w.write(r, 1, x['role'], txt); w.write(r, 2, x['unit'], txt)
                w.write(r, 3, x['contract'], txt); w.write(r, 4, x['customer'], txt)
                if x['contract_date']:
                    w.write_datetime(r, 5, fields.Datetime.to_datetime(x['contract_date']), date)
                else:
                    w.write(r, 5, '', txt)
                w.write(r, 6, x['price'], money); w.write(r, 7, x['share_pct'], pct); w.write(r, 8, x['sold_value'], money)
                w.write(r, 9, x['commission_pct'], pct)
                w.write(r, 10, x['commission_amount'], green if x['is_paid'] else red)
                w.write(r, 11, x['status'], green_t if x['is_paid'] else red_t)
                if x['payment_date']:
                    w.write_datetime(r, 12, fields.Datetime.to_datetime(x['payment_date']), date)
                else:
                    w.write(r, 12, '', txt)
                w.write(r, 13, x['note'], txt)
                r += 1
        t = data['grand']
        w.write(r, 0, _('Total'), bold)
        for c in range(1, 14):
            w.write(r, c, '', bold)
        w.write(r, 8, t['price'], bold_m); w.write(r, 10, t['commission'], bold_m)
        w.set_column(0, 1, 28); w.set_column(2, 3, 14); w.set_column(4, 4, 36); w.set_column(5, 5, 14)
        w.set_column(6, 12, 18); w.set_column(13, 13, 44)
        w.freeze_panes(1, 0); w.autofilter(0, 0, max(r - 1, 1), len(cols) - 1)
        wb.close()
        self.write({'excel_file': base64.b64encode(out.getvalue()),
                    'excel_filename': 'Trace_Commission_%s.xlsx' % fields.Date.today().strftime('%Y%m%d')})
        return {'type': 'ir.actions.act_url',
                'url': '/web/content/?model=%s&id=%s&field=excel_file&filename_field=excel_filename&download=true' % (
                    self._name, self.id),
                'target': 'self'}
