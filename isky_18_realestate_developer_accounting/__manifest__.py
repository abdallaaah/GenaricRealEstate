# -*- coding: utf-8 -*-
{
    'name': 'iSky 18 Real Estate Developer Accounting',
    'version': '1.0',
    'summary': 'Combined accounting-model inheritance for the real estate developer modules',
    'description': """
Level 1 of the real estate developer product restructuring: an optional accounting bridge.
Depends only on `account` and L0 (unit_inventory). Consolidates the account.* model
inheritance that is genuinely accounting-only (account.account/journal/analytic config,
res.config.settings account/journal settings, currency-conversion and down-payment/overseas
account selection on account.payment, the approval workflow, the reconcile wizard override).

arkzayed_loan_payments was deliberately excluded - its account.loan / account.loan.line /
account.move additions stay in that module.

arkzayed_18_vendor_bill was removed from the project (functional team flagged its approach
as wrong); everything derived from it (building_id/purchase_type/engineering_approved/
history/IPC fields on account.move, is_insurance_product/insurance_percentage on
account.move.line, requisition_id on account.payment, include_in_insurance on
account.tax.group, and the construction-percentage half of the reconcile wizard) was
stripped back out of this module along with it.

Cheque-dependent fields and logic were intentionally left in place in
arkzayed_18_realestate_development (account.payment) and in
arkzayed_18_gt_cheque_management, and are not part of this module.

Phase 2 (see claude/decisions_log.md): every field/method here that pointed to sale.proposal,
real.estate.sale.reservation, eoi.eoi, installment.lines/maintenance.installment.lines,
loan.line, revenue.share2, installment.penalty, reservation.payment, eoi.payment, or
payment.allocation moved to isky_18_realestate_developer_sales_crm (L2); everything that
pointed to broker.claim moved to isky_18_realestate_developer_commission (L3); the
arkzayed.cost.allocation fields on account.move.line moved to arkzayed_cost_distribution,
where they lived before an earlier consolidation. This module is now a true optional bridge -
the product installs and works without it.
    """,
    'author': 'iSkyDev',
    'depends': [
        'account',
        'account_reports',
        'isky_18_realestate_developer_unit_inventory',
    ],
    'data': [
        'views/account_account_views.xml',
        'views/account_journal_views.xml',
        'views/account_analytic_account_views.xml',
        'views/account_analytic_plan_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
