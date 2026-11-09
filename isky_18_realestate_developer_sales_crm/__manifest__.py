# -*- coding: utf-8 -*-
{
    'name': 'iSky 18 Real Estate Developer - Sales & CRM',
    # 1.1: #49 moved the lead stage data in, which needs migrations/18.0.1.1/pre-migrate.py
    # to run on existing databases - Odoo only runs it when the version changes.
    # 1.2: Phase 7 turned the two hardcoded revenue-split business lines into rows, converted by
    # migrations/18.0.1.2/pre-migrate.py.
    'version': '1.2',
    'summary': 'Lead -> EOI -> Reservation -> Contract -> Installments -> Maintenance -> Discounts -> Leasing -> CRM (Level 2)',
    'description': """
Level 2 of the real estate developer product restructuring. Bundles the full sales pipeline
(CRM lead, EOI, reservation, contract/sale.proposal, installments, maintenance, discounts,
leasing) and CRM lead management into one module, per the decision to not split these into
separate modules (none of them are ever installed independently of each other).

Absorbs the former arkzayed_18_realestate_developer_crm module's models/wizards/controllers;
that module now only carries views/data/security referencing models defined here (not yet
moved over - flagged as follow-up work, same as this module's own views still living in
arkzayed_18_realestate_development for now).

Several files here are *_crm_ext.py / *_commission_hierarchy_ext.py - these existed because the
old CRM module had its own _inherit shims on sale.proposal/sale.reservation/eoi.eoi/crm.lead
duplicating the same "commission hierarchy builder" algorithm. Not deduplicated yet - that's
Level 3 (Commissions & Broker) work, since that module is meant to own the one canonical copy.

Two models (job.level, arkzayed.construction.progress - the latter not present here) were found
defined twice across the old modules with near-identical content; job.level was merged into one
definition in models/config/job_level.py.
    """,
    'author': 'iSkyDev',
    'depends': [
        'base',
        'web',
        'portal',
        'mail',
        'hr',
        'crm',
        'sales_team',
        'sale_management',
        'project',
        'utm',
        'documents',
        'website_crm_partner_assign',
        'website_studio',
        'base_geolocalize',
        'arkzayed_18_contact_customization',
        'isky_18_realestate_developer_unit_inventory',
        # Phase 3 step 2b-a: the hard dependency on the optional L1 accounting bridge
        # (isky_18_realestate_developer_accounting) was removed. Odoo core `account` is
        # still required: this module _inherits account.move and account.payment, and a
        # model cannot _inherit a model that does not exist. `account` is not L1 - the L1
        # bridge is the optional isky module, and Mode B means THAT is absent (supplement
        # S2). Mode A coupling lives in isky_18_realestate_developer_sales_accounting.
        'account',
        # Phase 3 step 3: the hard dependency on the optional L1 cheque module
        # (arkzayed_18_gt_cheque_management) was removed. Every sales<->cheque link now
        # lives in isky_18_realestate_developer_sales_cheques (supplement S1), so this
        # module installs with no cheque module present at all.
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        # #49: stage rows for the two stage models this module owns. Data before views, so
        # anything referencing a stage resolves.
        'data/lead_stage_data.xml',
        'data/crm_stage_data.xml',
        # Phase 3c step 2a: the UI for L2's own models, moved out of the legacy modules.
        # Views and reports before menus, because a menuitem needs its action to exist.
        'views/attachment_type.xml',
        'views/broker_unit_views.xml',
        'views/collections_installment_views.xml',
        'views/crm_lead_reassign_views.xml',
        'views/customer_ownership.xml',
        'views/discount_approval_views.xml',
        'views/discount_config_views.xml',
        'views/discount_request_views.xml',
        'views/handover_report_views.xml',
        'views/installment_penalty_views.xml',
        'views/installment_report_views.xml',
        'views/lead_stage_views.xml',
        'views/lease_installment_tree_view.xml',
        'views/maintenance_config_views.xml',
        'views/maintenance_report_views.xml',
        'views/meeting_report_views.xml',
        'views/offer.xml',
        'views/project_sale_phase_views.xml',
        'views/qualified_stage.xml',
        'views/revenue_share2.xml',
        'views/sale_installment_tree_view.xml',
        'views/sale_request.xml',
        'views/sales_achievement_report_views.xml',
        'views/sales_contract_analysis_views.xml',
        'views/unqualified_stage.xml',
        'reports/eoi_cancellation_report.xml',
        'reports/report_sale_contract_document.xml',
        'reports/reservation_cancellation_report.xml',
        'reports/unit_plan_report.xml',
        'views/menus.xml',
        # Phase 3c step 1: this layer's fields added back onto L0's own views, which
        # had to be stripped of them so L0 installs alone.
        'views/l0_view_extensions.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
