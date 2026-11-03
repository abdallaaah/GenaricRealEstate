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
        'isky_18_realestate_developer_unit_inventory',
        'isky_18_realestate_developer_accounting',
        'isky_18_realestate_developer_sales_crm',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
