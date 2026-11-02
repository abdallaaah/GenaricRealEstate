# -*- coding: utf-8 -*-
{
    'name': "ARK Zayed 18 Vendor Bill",
    'summary': "Vendor Bill",
    'description': """Vendor Bill History""",
    'author': "iSkyDev",
    'website': "https://www.iskydev.com",
    'category': 'Uncategorized',
    'summary': 'Add History tab to Vendor Bills tracking Purchase Agreement products',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','account', 'purchase', 'purchase_requisition', 'arkzayed_18_realestate_development', 'isky_18_realestate_developer_accounting'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        # views
        'views/product.xml',
        'views/account_move.xml',
        'views/purchase_requisition.xml',
        'views/purchase_order.xml',
        'views/account_tax_group.xml',
        'views/res_partner.xml',
        'views/wip_report_views.xml',
        # reports
        'reports/ipc_report_action.xml',
        'reports/ipc_report_templates.xml',
        'reports/ipc_server_action.xml',
        # wizard
        'wizard/purchase_requisition_payment_wizard.xml',
        "wizard/account_reconcile_wizard.xml",
    ],
    # only loaded in demonstration mode
    'demo': [],

    'application': True,
    'installable': True,
}
