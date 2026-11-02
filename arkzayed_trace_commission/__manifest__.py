{
    'name': 'Ark Zayed Trace Commission',
    'version': '1.0',
    'summary': 'Search one or more sales people, team leaders, managers, brokers or ambassadors and see every unit '
               'they sold with price, commission and whether it is paid, with PDF and Excel export',
    'author': 'Hekon Tech',
    'depends': ['arkzayed_18_realestate_development'],
    'license': 'LGPL-3',
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/trace_commission_views.xml',
        'report/report_trace_commission.xml',
    ],
    'application': False,
}
