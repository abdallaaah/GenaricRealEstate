# -*- coding: utf-8 -*-
{
    'name': "iSky HR Egypt Policy",
    'summary': """iSky HR Egypt Policy""",
    'author': "iSky Development Team",
    'website': "http://www.iskydev.com",
    'category': 'Human Resources',

    'description': """
    1- Add policy group to contract.\n
    2- Add type to salary rules.\n
    3- Add method to get rates in payslip.\n

        """,
    'version': '0.1',
    'depends': ['hr_payroll', 'hr_attendance', 'isky_hr_egypt_employee', 'hr_work_entry'],

    'data': [
        'security/ir.model.access.csv',
        "data/default_structure.xml",
        "views/policy_group.xml",
        "views/resource_calendar.xml",
        "views/hr_payslip.xml",
        "views/hr_contract.xml",
        'views/hr_salary_rule.xml',
        'views/menu_item.xml',
        # 'views/templates.xml',
    ],
    'external_dependencies': {'python': ['datetimerange']},
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
