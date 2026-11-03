{
    'name': 'iSky Broker - Real Estate',
    'version': '20.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Real estate inventory: developer projects, sale units, and project commission rules',
    'description': """
iSky Broker - Real Estate
===========================
- Developer projects and their sale phases.
- Sale units (broker.unit) with classification, pricing, geography, and the
  resale-seller side of a unit.
- Per-project commission base/additional percentage, time-windowed, used by
  the commission module.
- Unit utility counters (electricity/gas/water/landline/internet),
  consolidated into one model instead of five near-identical ones.
    """,
    'depends': ['isky_20_broker_base', 'base_geolocalize', 'sales_team'],
    'data': [
        'security/ir.access.csv',
        'data/ir_sequence_data.xml',
        'views/developer_project_views.xml',
        'views/project_commission_views.xml',
        'views/broker_unit_views.xml',
        'views/broker_menus.xml',
    ],
    'demo': [
        'demo/developer_project_demo.xml',
        'demo/broker_unit_demo.xml',
    ],
    'author': 'iSky Development',
    'license': 'LGPL-3',
}
