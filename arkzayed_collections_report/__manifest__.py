{
    'name': 'Ark Zayed Collections Report',
    'version': '1.1',
    'summary': 'Executive collections report: collected, outstanding, overdue, ageing and client details',
    'author': 'iSkyDev',
    'depends': ['arkzayed_18_realestate_development'],
    'license': 'LGPL-3',
    'data': [
        'security/ir.model.access.csv',
        'report/report_collections.xml',
        'report/report_collections_period.xml',
        'wizard/collections_wizard_views.xml',
        'wizard/collections_period_wizard_views.xml',
        'views/installment_views.xml',
    ],
    'application': False,
}
