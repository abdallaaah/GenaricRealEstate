# -*- coding: utf-8 -*-
{
    'name': "iSky HR Egypt Employee",
    'summary': "iSky HR Egypt Employee",
    'author': "iSky Development Team",
    'website': "http://www.iskydev.com",
    'description': """
        This module add pages to employee screen like 
            1- Skills\n
            2- Education Qualifications\n
            3- Employee Experience\n
            4- Employee Training\n
            5- Employee Referred Persons\n
            6- Employee Medical Data\n
        ,In this you must setup python library (validate_email) to validate email
         to install it run 'pip3 install validate_email' command and install
         num2words with command 'pip3 install num2words'
         
    """,
    'category': 'Human Resources',
    'version': '18.0.0.1',
    # depend on isky_18_realestate_broker because of (res.country.city) model only
    'depends': ['mail', 'hr_holidays', 'hr_contract', 'hr_recruitment','isky_base_modification'],

    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/hr_notifications.xml',
        'views/work_permit.xml',
        "views/exp_training.xml",
        "views/exp_skills.xml",
        "views/res_company.xml",
        'views/hr_employee_information.xml',
        "views/hr_employee.xml",
        "views/exp_informants.xml",
        "views/hr_qualification.xml",
        "views/practical_experience.xml",
        "views/hr_leave.xml",
        "views/hr_contract.xml",
        "views/education_qualification.xml",
        "views/menu_item.xml",
        "views/hr_departure_wizard_view.xml",
        "reports/employee_data_report_view.xml",
        "reports/employee_job_history_report_view.xml",
        "reports/employee_department_history_report_view.xml",
    ],
    'external_dependencies': {'python': ['validate_email']},
    'installable': True,
    'auto_install': False,
    'sequence': 1,
    'license': 'LGPL-3',
}
