# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools
from odoo.tools.sql import drop_view_if_exists


class CustodyJournalEntries(models.Model):
    _name = 'custody.journal.entries'
    _description = 'Custody Journal Entries'
    _auto = False

    # Calculate balance for each employee
    def _get_balance(self):
        self._cr.execute("SELECT DISTINCT(employee_id) FROM custody_journal_entries")
        for each_emp in self._cr.fetchall():
            balance = 0
            emp_entries = self.env['custody.journal.entries'].search([('employee_id', '=', each_emp[0])])
            for entry in emp_entries:
                if entry.debit:
                    balance += entry.debit
                if entry.credit:
                    balance -= entry.credit
                entry.balance = balance

    # Display balance in group
    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        res = super(CustodyJournalEntries, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                            orderby=orderby, lazy=lazy)
        for line in res:
            line['balance'] = line['debit'] - line['credit']
        return res

    date = fields.Date(string="Date")
    debit = fields.Float('Debit')
    credit = fields.Float('Credit')
    custody_id = fields.Many2one('employee.custody')
    employee_id = fields.Many2one('hr.employee', string="Employee")
    type = fields.Selection([('payment', 'Payment'),
                             ('direct_expense', 'Direct Expense'), ('payback', 'Payback')],
                            'Type')
    balance = fields.Float(compute="_get_balance")

    def init(self):
        drop_view_if_exists(self._cr, 'custody_journal_entries')
        self._cr.execute("""
                create or replace view custody_journal_entries as  (
                SELECT account_move_line.id as id,
                    account_move_line.date as date,
                    account_move_line.debit as debit,
                    account_move_line.credit as credit,
                    employee_custody.employee_id as employee_id,
                    account_move_line.custody_id as custody_id,
                    account_move_line.account_move_type as type
                    FROM
                        account_move_line
                    LEFT JOIN employee_custody
                    ON
                        employee_custody.id = account_move_line.custody_id
                    WHERE
                        account_move_line.custody_id IS NOT NULL AND ((account_move_line.ref IS NOT NULL AND account_move_line.credit = 0) or(account_move_line.ref IS NULL AND account_move_line.debit = 0))
                    ORDER BY account_move_line.id

     )""")
