{
    'name': 'Ark Zayed Executive Dashboard',
    'version': '1.3',
    'summary': 'Live, on-screen executive dashboard: sales & inventory, collections vs due, cash position',
    'author': 'iSkyDev',
    'depends': ['arkzayed_18_realestate_development', 'arkzayed_18_gt_cheque_management', 'account'],
    'license': 'LGPL-3',
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            ('include', 'web.chartjs_lib'),
            'arkzayed_executive_dashboard/static/src/js/dashboard_action.js',
            'arkzayed_executive_dashboard/static/src/xml/dashboard_action.xml',
            'arkzayed_executive_dashboard/static/src/scss/dashboard.scss',
        ],
    },
    'application': False,
}
