{
    'name': 'Ark Zayed Contract NPV',
    'version': '1.1',
    'summary': 'NPV of each contract\'s installment schedule, a standalone what-if Calculator, and a '
               'portfolio-wide Executive Report',
    'author': 'iSkyDev',
    'depends': ['arkzayed_18_realestate_development', 'isky_18_realestate_developer_sales_crm'],
    'license': 'LGPL-3',
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/sale_proposal_views.xml',
        'wizard/npv_calculator_wizard_views.xml',
        'report/report_npv_executive.xml',
        'wizard/npv_report_wizard_views.xml',
    ],
    'application': False,
}
