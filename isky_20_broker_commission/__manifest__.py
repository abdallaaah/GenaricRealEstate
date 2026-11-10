{
    'name': 'iSky Broker - Commission',
    'version': '20.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Real estate broker commission hierarchy and target-achievement calculation',
    'description': """
iSky Broker - Commission
==========================
- Extends Odoo Enterprise's Sale Commission app (sale.commission.plan) with
  a real-estate-specific filter flag and job-position/job-level targeting.
- Calculates, per confirmed-contract opportunity and per hierarchy member,
  the commission amount: a bracketed rate against a target for the actual
  deal-closing salesperson, a flat achieve-type rate for hierarchy
  beneficiaries (team leader/sales manager/director), adjusted for the
  project's base-commission threshold and multiplier.
- Achievement report by salesperson/team/period.

Adapted from the Odoo 17 version of this engine against the actual Odoo 20
Enterprise sale_commission data model, which was substantially restructured
between versions (plan assignments are their own sale.commission.plan.user
model now, not a plain many2many) -- this is not a line-for-line port.
    """,
    'depends': ['sale_commission', 'isky_20_broker_crm', 'isky_20_broker_real_estate'],
    'data': [
        'security/ir.access.csv',
        'data/commission_feature_flag_data.xml',
        'views/sale_commission_plan_views.xml',
        'views/realestate_commission_achievement_views.xml',
        'views/realestate_achievement_report_views.xml',
        'views/res_config_settings_views.xml',
        'views/broker_menus.xml',
    ],
    'demo': [
        'demo/account_chart_demo.xml',
        'demo/sale_commission_plan_demo.xml',
    ],
    'author': 'iSky Development',
    'license': 'OEEL-1',
}
