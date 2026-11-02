# -*- coding: utf-8 -*-
{
    'name': 'iSky 18 Real Estate Developer Accounting',
    'version': '1.0',
    'summary': 'Combined accounting-model inheritance for the real estate developer modules',
    'description': """
Consolidates the account.* model inheritance that used to be scattered across
arkzayed_18_realestate_development, arkzayed_18_vendor_bill and arkzayed_cost_distribution
into a single module, one file per Odoo accounting model.

arkzayed_loan_payments was deliberately excluded - its account.loan / account.loan.line /
account.move additions stay in that module.

Cheque-dependent fields and logic were intentionally left in place in
arkzayed_18_realestate_development (account.payment) and in
arkzayed_18_gt_cheque_management, and are not part of this module.

NOTE: this module depends on arkzayed_18_realestate_development / arkzayed_18_vendor_bill /
arkzayed_cost_distribution for the business models its fields point to (sale.proposal,
real.estate.unit, eoi.eoi, account.move.history.line, arkzayed.cost.allocation, ...).
Those modules' own remaining code/views still reference fields that now live here, so
they need this module as a dependency too - that back-and-forth is a circular dependency
that has not been resolved yet. Flagged here on purpose; see conversation notes.
    """,
    'author': 'iSkyDev',
    'depends': [
        'account',
        'purchase_requisition',
        'arkzayed_18_realestate_development',
        'arkzayed_18_vendor_bill',
        'arkzayed_cost_distribution',
    ],
    'data': [
        'views/account_account_views.xml',
        'views/account_journal_views.xml',
        'views/account_analytic_account_views.xml',
        'views/account_analytic_plan_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/account_tax_group_views.xml',
        'views/account_reconcile_wizard_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
