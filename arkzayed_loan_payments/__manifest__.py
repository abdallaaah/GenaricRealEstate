{
    'name': 'Ark Zayed Loan Payments & Commission',
    'version': '1.0',
    'summary': 'Adds a Commission accrual and a one-click Register Payment button to Odoo Loans (account_loans)',
    'author': 'iSkyDev',
    'depends': ['account_loans'],
    'license': 'LGPL-3',
    'data': [
        'security/ir.model.access.csv',
        'wizard/loan_line_payment_wizard_views.xml',
        'views/account_loan_views.xml',
    ],
    'application': False,
}
