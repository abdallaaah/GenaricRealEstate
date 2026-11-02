{
    'name': 'Ark Zayed Construction Progress',
    'version': '1.0',
    'summary': 'Simple construction progress (%) per unit or building, updated by the responsible engineer',
    'author': 'iSkyDev',
    'depends': ['arkzayed_18_realestate_development'],
    'license': 'LGPL-3',
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/progress_wizard_views.xml',
        'report/report_progress.xml',
        'views/progress_views.xml',
        'views/unit_building_views.xml',
        'wizard/report_wizard_views.xml',
    ],
    'application': False,
}
