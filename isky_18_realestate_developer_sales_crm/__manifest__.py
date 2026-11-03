# -*- coding: utf-8 -*-
{
    'name': 'iSky 18 Real Estate Developer - Sales & CRM',
    'version': '1.0',
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
        'isky_18_realestate_developer_accounting',
        'arkzayed_18_gt_cheque_management',
    ],
    'data': [],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
