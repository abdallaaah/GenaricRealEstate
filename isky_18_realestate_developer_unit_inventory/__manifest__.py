# -*- coding: utf-8 -*-
{
    'name': 'iSky 18 Real Estate Developer - Unit Inventory',
    # 1.1: Phase 7 renamed the client-prefixed config parameters; the values are carried over by
    # migrations/18.0.1.1/pre-migrate.py, which Odoo only runs when the version changes.
    'version': '1.1',
    'summary': 'Property/unit master data foundation for the real estate developer product (Level 0)',
    'description': """
Level 0 of the real estate developer product restructuring: property/unit master data with
zero dependency on any other level (Accounting, Cheques, Sales & CRM, Commissions & Broker,
Developer Construction). Everything else depends on this module; this module depends on
nothing from the product line itself.

models/core/ holds the transactional/operational records (project, building, unit, zone,
cluster, floor, utility meters). models/config/ holds setup/master-data/lookup models
(sub-types, templates, pricing config, reason codes, geography reference data).

A few fields/methods that originally lived on these models were extracted out and left behind
in arkzayed_18_realestate_development as _inherit extensions, because they reference models
that belong to higher levels not yet built (sale.proposal, account.analytic.plan's is_unit/
is_building/is_project flags owned by the Accounting module). See
real_estate_unit_contract_ext.py and analytic_account_autocreate_ext.py there.
    """,
    'author': 'iSkyDev',
    'depends': [
        'base',
        'mail',
        'analytic',
        'product',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        # Phase 3c step 1: the UI for L0's own models, moved out of the legacy modules.
        # Views before menus, because a menuitem needs its action to exist already.
        'views/archive_place.xml',
        'views/block_reason_wizard.xml',
        'views/cluster_views.xml',
        'views/developer_project_view.xml',
        'views/down_payment_increase.xml',
        'views/floor_area_views.xml',
        'views/floor_views.xml',
        'views/medical_type_views.xml',
        'views/neighborhood.xml',
        'views/office_type_views.xml',
        'views/outdoor_percentage_views.xml',
        'views/parking_area_configuration_views.xml',
        'views/parking_template.xml',
        'views/premiums.xml',
        'views/price_plan_view.xml',
        'views/project_phases.xml',
        'views/real_estate_building_views.xml',
        'views/real_estate_facility_views.xml',
        'views/real_estate_feature_views.xml',
        'views/real_estate_nearby_connectivity_views.xml',
        'views/real_estate_project_type_views.xml',
        'views/real_estate_project_views.xml',
        'views/real_estate_unit_views.xml',
        'views/res_country_city_views.xml',
        'views/res_state.xml',
        'views/residential_sub_type_views.xml',
        'views/unit_block_reasons_views.xml',
        'views/unit_design_views.xml',
        'views/unit_estimate_delivery_views.xml',
        'views/view_installment_template.xml',
        'views/view_maintenance_template.xml',
        'views/zone_views.xml',
        'reports/unit_documents.xml',
        'reports/unit_layout.xml',
        'views/menus.xml',
        # Phase 6: the shared "Real Estate" settings tab and the Units section
        'views/res_config_settings_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
