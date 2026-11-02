# -*- encoding: utf-8 -*-

{
    'version': '18.0.1.0.0',
    'name': "iSky Employee  Custody",
    'summary': "iSky  Employee Custody",
    'description': "This module allows employees to take custodies from the company.",
    'author': "iSky Development Team",
    'website': "http://iskydev.com/",
    'license': 'LGPL-3',
    'depends': ['hr', 'account', 'report_xlsx'],

    'data': [
        # security
        'security/custody_security_view.xml',
        'security/ir.model.access.csv',
        # data
        'data/custody_sequence_view.xml',
        # views
        'views/res_partner.xml',
        'views/hr_employee.xml',
        'views/employee_custody_category_view.xml',
        'views/employee_custody_view.xml',
        'views/account_move.xml',
        'views/custody_transactions_view.xml',
        'views/employee_product_expense_view.xml',
        'views/custody_multi_generate_journals_view.xml',

        # report
        'reports/employee_custody_wizard.xml',
        'reports/employee_custody_display.xml',
        'reports/custody_journal_entries_report.xml',
        'reports/custody_xlsx_wizard.xml',
        'views/menu_items_view.xml',

    ]
}
