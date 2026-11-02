# -*- coding: utf-8 -*-
{
    'name': "iSky HR Egypt Allowances Application Contract",
    'summary': """iSky HR Egypt Allowances Application Contract""",
    'author': "iSky Development Team",
    'website': "http://www.iskydev.com",
    'category': 'Human Resources',

    'description': """
    1) Adding allowances to application / contract.\n
    2) Adding reports to contract.\n
        """,
    'version': '0.1',
    'depends': ['hr_payroll',
                'hr_recruitment',
                'isky_hr_egypt_policy',
                ],

    'data': [
        'security/ir.model.access.csv',
        "views/hr_contract.xml",
        "views/hr_job.xml",
        'views/hr_recruitment_stage.xml',
        'views/hr_applicant.xml',
        'views/hr_employee.xml',
        'views/res_country_views_inherit.xml',
        'views/hr_payslip_run.xml',
        # reports
        'reports/start_work_report.xml',
        'reports/salary_report.xml',
        'reports/cancel_contract_report.xml',
        'reports/it_specification_report_view.xml',
        'reports/safety_report_view.xml',
        'reports/financial_report_view.xml',
        'reports/partial_report_view.xml',
        'reports/single_contract_report.xml',
        'reports/job_offer_report.xml',
        # data
        'data/hr_salary_rule_data.xml',
        # menu
        'views/menu_item.xml',
    ],
    'external_dependencies': {'python': ['validate_email','num2words']},
    'installable': True,
    'auto_install': False,
}
