# -*- encoding: utf-8 -*-
{
    'name': 'iSky HR Egypt Social Insurance',
    'summary': 'iSky HR Egypt Social Insurance',
    'author': 'iSky Development Team',
    'website': 'http://www.iskydev.com',
    'description': '''
        This module add social insurance in contract and add deduction rules in payslip.
     ''',

    'depends': ['hr_payroll', 'isky_hr_egypt_policy'],

    'data': [
        'security/ir.model.access.csv',
        'data/salary_rules.xml',
        'views/policy_group.xml',
        'views/insurance_line.xml',
        'views/si_position.xml',
        'views/hr_contract.xml',
        'views/hr_insurance.xml',
        'views/hr_insurance_annual.xml',
        'views/insurance_policy.xml',
        'views/insurance_history.xml',
        'views/menu_items.xml',
        'reports/insurance_form_2.xml',
        'views/res_company_inherit.xml',
        'views/hr_payroll.xml'
    ],
'license': 'LGPL-3',
}
