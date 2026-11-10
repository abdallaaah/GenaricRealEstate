{
    'name': 'iSky Broker - Base',
    'version': '20.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Shared foundation for the iSky real estate brokerage platform',
    'description': """
iSky Broker - Base
===================
Foundation layer shared by every iSky_20_Broker module:

- Partner role flags used by CRM/real-estate domain filters (broker, ambassador,
  resale seller/buyer, developer, customer, vendor, portal access by area).
- KYC/legal document fields on partners (national ID, passport, commercial
  registration, tax registration) with expiry tracking.
- The sales job-level hierarchy (salesperson / team leader / sales manager /
  director / operations) used by CRM and commission.
- Centralized feature-flag model so portal menus, templates, and controllers
  check feature availability through one place instead of duplicating the
  check per surface.
    """,
    'depends': ['base', 'contacts', 'mail', 'hr', 'sales_team'],
    'data': [
        'security/isky_20_broker_base_security.xml',
        'security/ir.access.csv',
        'data/job_level_data.xml',
        'data/res_company_data.xml',
        'views/job_level_views.xml',
        'views/broker_feature_flag_views.xml',
        'views/res_partner_views.xml',
        'views/crm_team_views.xml',
        'views/res_users_views.xml',
        'views/broker_menus.xml',
    ],
    'demo': [
        'demo/res_partner_demo.xml',
        'demo/res_users_demo.xml',
        'demo/crm_team_demo.xml',
    ],
    'author': 'iSky Development',
    'license': 'LGPL-3',
}
