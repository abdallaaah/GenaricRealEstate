# -*- coding: utf-8 -*-
{
    'name': 'iSky 18 Real Estate Developer - Commissions & Broker',
    'version': '1.0',
    'summary': 'Commission categories, broker contracts/teams/visits/claims, commission achievements (Level 3)',
    'description': """
Level 3 of the real estate developer product restructuring.

NOT done in this pass (flagged, not fixed): the "commission hierarchy builder" algorithm still
has 4 separate near-duplicate implementations spread across isky_18_realestate_developer_sales_crm
(crm_lead.py's compute_person_hierarchy, eoi_commission_hierarchy_ext.py,
sale_proposal_crm_ext.py's _build_commission_hierarchy, sale_reservation_crm_ext.py's
_build_commission_hierarchy) - they were found to have real behavioral differences (one splits
commission % across duplicate roles, the others give 100% to each), not just copy-paste, so
picking one canonical version is a product decision, not a mechanical refactor. Left in place.

Also NOT merged: res_partner.py's broker/ambassador flags (is_broker, is_ambassador, is_agent,
commission_claim_count) still live in isky_18_realestate_developer_sales_crm mixed in with
generic partner fields (nationality, academic_qualifications) rather than split out here.

realestate.project.commission (broker % per project, simple list) and project.commission
(time-boxed commission-rate periods per developer.project) were in the original plan as "the
same model, consolidate" - they are not; different _name, different fields, different purpose.
Both kept, separately, as project_commission.py / project_commission_crm.py.
    """,
    'author': 'iSkyDev',
    'depends': [
        'hr',
        # Phase 4: undeclared dependency, found when this module was installed for the first
        # time. models/config/sale_commission_plan.py does `_inherit = "sale.commission.plan"`,
        # an Enterprise model from `sale_commission`, which was never listed - so this module
        # has never been installable. Same class as the `account_reports` omission Phase 2
        # found in the L1 bridge (backlog #7).
        'sale_commission',
        'isky_18_realestate_developer_unit_inventory',
        # Phase 4 (D4): the hard dependency on the optional L1 accounting bridge was
        # removed - this module references only core account.payment / account.move /
        # account.account, nothing the bridge adds. Keeping it forced Mode A on anyone
        # installing commission. Same change Phase 2b/3 made for sales_crm.
        'account',
        'isky_18_realestate_developer_sales_crm',
    ],
    'data': [
        'security/ir.model.access.csv',
        # Phase 3c: the UI for this layer's own models, moved out of the legacy modules.
        # Views and reports before menus, because a menuitem needs its action to exist.
        'views/broker_claim.xml',
        'views/broker_contract.xml',
        'views/broker_team_view.xml',
        'views/broker_visit_views.xml',
        'views/commission_category_views.xml',
        'views/job_level.xml',
        'views/project_commission_view.xml',
        'views/project_commission_views.xml',
        'views/realestate_commission_achievement.xml',
        'views/menus.xml',
        # Phase 6: the Company Setup and Commission sections of the shared settings tab
        # Phase 3c step 1: this layer's fields added back onto L0's own views, which
        # had to be stripped of them so L0 installs alone.
        'views/l0_view_extensions.xml',
        'views/res_config_settings_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
