{
    'name': 'Ark Zayed Cost Distribution',
    'version': '1.1',
    'summary': 'Distribute shared costs (PO/Bill lines) across units by area, and track direct vs indirect cost per unit',
    'author': 'iSkyDev',
    'depends': ['account', 'arkzayed_18_realestate_development', 'isky_18_realestate_developer_accounting'],
    'license': 'LGPL-3',
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'report/report_cost_distribution.xml',
        'wizard/distribution_wizard_views.xml',
        'views/real_estate_unit_views.xml',
        'views/hierarchy_views.xml',
        'views/cost_allocation_views.xml',
        'views/cost_distribution_views.xml',
    ],
    'application': False,
}
