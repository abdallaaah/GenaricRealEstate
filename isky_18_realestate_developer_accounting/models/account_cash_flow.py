from odoo import models
from odoo.tools import SQL


class AccountCashFlowReport(models.AbstractModel):
    _inherit = 'account.cash.flow.report.handler'

    def _compute_liquidity_balance(self, report, options, payment_account_ids, date_scope):
        ''' Compute the balance of all liquidity accounts to populate the following sections:
            'Cash and cash equivalents, beginning of period' and 'Cash and cash equivalents, closing balance'.

        :param options:                 The report options.
        :param payment_account_ids:     A tuple containing all account.account's ids being used in a liquidity journal.
        :return:                        A list of tuple (account_id, account_code, account_name, balance).
        '''
        queries = []

        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            query = report._get_report_query(column_group_options, date_scope,
                                             domain=[('account_id', 'in', payment_account_ids)])

            # Use LEFT JOIN instead of trying to reuse an existing join
            # This avoids the assertion error from duplicate joins
            queries.append(SQL(
                '''
                SELECT
                    %(column_group_key)s AS column_group_key,
                    account_move_line.account_id,
                    account_account.code_store->>%(company_root_id)s AS account_code,
                    account_account.name AS account_name,
                    SUM(%(balance_select)s) AS balance
                FROM %(table_references)s
                LEFT JOIN account_account ON account_account.id = account_move_line.account_id
                %(currency_table_join)s
                WHERE %(search_condition)s
                GROUP BY account_move_line.account_id, account_account.code_store->>%(company_root_id)s, account_account.name
                ''',
                column_group_key=column_group_key,
                company_root_id=str(self.env.company.root_id.id),
                table_references=query.from_clause,
                balance_select=report._currency_table_apply_rate(SQL("account_move_line.balance")),
                currency_table_join=report._currency_table_aml_join(column_group_options),
                search_condition=query.where_clause,
            ))

        self._cr.execute(SQL(' UNION ALL ').join(queries))

        return self._cr.dictfetchall()
