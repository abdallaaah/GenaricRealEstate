# -*- coding: utf-8 -*-
{
    'name': 'iSky 18 Real Estate Developer - Sales Accounting Bridge',
    'version': '1.0',
    'summary': 'Optional bridge: wires the sales pipeline to the accounting layer (Mode A)',
    'description': """
Phase 3 step 2b-a. Optional bridge between isky_18_realestate_developer_sales_crm (L2) and
isky_18_realestate_developer_accounting (L1).

Installed  => Mode A: payments post journal entries, the user-edited exchange rate is honoured,
              and the revenue-split collection entry is produced.
Not installed => Mode B: sales_crm runs with no accounting coupling at all. No journal entries
              are created and nothing is posted to account.move. Installments and EOIs are
              tracked by manual Paid status only. See supplement S2.

This module exists so that sales_crm does not hard-depend on the optional L1 accounting bridge.
It holds ONLY real accounting coupling - the fields the bridge owns
(payment_method_type, converted_amount, custom_exchange_rate, overseas_payment_type, the
bridge-only payment states) and the Mode A code paths that use them.

Sales-owned flags are deliberately NOT here: is_contract, is_collection,
is_maintenance_collection and is_down_payment live in sales_crm (Phase 3 step 2a), because they
are set by sales flows rather than by accounting.

Every compute extended here follows the S6 guard pattern: the method is redeclared with an
@api.depends that includes this module's own paths, and it calls super(). Enforced by
claude/scripts/lint_guard_pattern.py.
    """,
    'author': 'iSkyDev',
    'depends': [
        'isky_18_realestate_developer_sales_crm',
        'isky_18_realestate_developer_accounting',
    ],
    'data': [],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': True,
}
