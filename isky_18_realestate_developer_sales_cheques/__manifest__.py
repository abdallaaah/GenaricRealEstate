# -*- coding: utf-8 -*-
{
    'name': 'iSky 18 Real Estate Developer - Sales Cheques Bridge',
    'version': '1.0',
    'summary': 'Optional bridge: links cheques to the sales pipeline (supplement S1)',
    'description': """
Supplement S1, implemented in Phase 3 steps 3 and 4.

S1 requires that L2 sales must NOT hard-depend on the optional L1 cheque module. This bridge
holds every sales<->cheque link, so each side installs on its own:

  sales_crm alone                  -> no cheque fields, no cheque code paths
  cheque module alone              -> generic cheque register, no sales references
  sales_crm + cheques + this       -> sales-linked cheque features work

What lives here:
  - the sales inverse fields on cheque.manage (eoi_id, sale_proposal_id, sale_reservation_id,
    installment_line_id, maintenance_installment_line_id, reservation_payment_id,
    eoi_payment_id) and the One2many counterparts on the sales models
  - payment.allocation.cheque_id
  - the cheque half of every compute that mixes payments and cheques, layered with the S6
    guard pattern: the base compute in sales_crm depends only on payment paths, and the
    override here redeclares @api.depends with the cheque paths added and calls super()

Enforced by claude/scripts/lint_guard_pattern.py.
    """,
    'author': 'iSkyDev',
    'depends': [
        'isky_18_realestate_developer_sales_crm',
        'arkzayed_18_gt_cheque_management',
    ],
    'data': [
        # Phase 3c step 2a: this bridge's column on L2's installment list
        'views/l2_view_extensions.xml',
        'views/res_config_settings_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': True,
}
