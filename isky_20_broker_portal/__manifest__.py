{
    'name': 'iSky Broker - Portal',
    'version': '20.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Broker-facing portal: leads/opportunities, resale units, and permission requests',
    'description': """
iSky Broker - Portal
======================
- Broadens website_crm_partner_assign's reseller-only portal domain to
  iSky's actual portal usage: external salespeople/team leads/split-deal
  participants.
- Restricts a portal user to their own authored chatter messages (plus
  authorless system messages) on crm.lead, implemented as a mail.message
  _search override rather than hiding the whole chatter widget.
- My Units (resale listings) and My Permission Requests portal pages, each
  gated through isky_20_broker_base's centralized broker.feature.flag check
  -- used identically by the portal card, the route, and (for units) the
  record-level access rule.

Portal feature codes used here: 'real_estate_units', 'permission_requests'.
    """,
    'depends': ['portal', 'website_crm_partner_assign', 'isky_20_broker_crm', 'isky_20_broker_real_estate'],
    'data': [
        'security/ir.access.csv',
        'data/ir_sequence_data.xml',
        'data/portal_entry_data.xml',
        'views/permission_request_templates.xml',
        'views/broker_unit_templates.xml',
        'views/res_config_settings_views.xml',
    ],
    'demo': [
        'demo/permission_request_demo.xml',
    ],
    'author': 'iSky Development',
    'license': 'LGPL-3',
}
