{
    'name': 'iSky Broker - CRM',
    'version': '20.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Real estate brokerage lead/opportunity pipeline, approval workflow, and commission hierarchy',
    'description': """
iSky Broker - CRM
===================
- Dual-stage pipeline: a pre-qualification pipeline (lead.stage) separate
  from the deal pipeline (crm.stage flags: EOI/Reservation/Contract/
  Collected/Confirmed Contract/Cancel).
- Configurable approval chain (broker.approval.rule) instead of a fixed
  12-field, hardcoded-group approval matrix.
- Phone- and unit-based duplicate/conflict detection.
- Commission hierarchy computation (who gets a share of a deal, based on
  the job-level org chart), consumed by the commission module.
- An in-app notification bell, independent of the native mail inbox.
    """,
    'depends': ['crm', 'hr', 'phone_validation', 'isky_20_broker_base', 'isky_20_broker_real_estate'],
    'data': [
        'security/isky_20_broker_crm_security.xml',
        'security/ir.access.csv',
        'data/ir_sequence_data.xml',
        'data/lead_stage_data.xml',
        'data/crm_stage_data.xml',
        'data/utm_source_data.xml',
        'data/broker_approval_rule_data.xml',
        'views/crm_lead_views.xml',
        'views/res_company_views.xml',
        'views/crm_stage_views.xml',
        'views/lead_stage_views.xml',
        'views/broker_approval_rule_views.xml',
        'views/qualified_stage_wizard_views.xml',
        'views/crm_lead_unqualified_wizard_views.xml',
        'views/crm_lead_convert_contact_wizard_views.xml',
        'views/crm_lead_reassign_views.xml',
        'views/res_config_settings_views.xml',
        'views/broker_menus.xml',
    ],
    'demo': [
        'demo/crm_lead_demo.xml',
    ],
    'author': 'iSky Development',
    'license': 'LGPL-3',
}
