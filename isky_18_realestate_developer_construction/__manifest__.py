# -*- coding: utf-8 -*-
{
    'name': 'iSky 18 Real Estate Developer - Construction',
    'version': '1.0',
    'summary': 'Construction progress tracking, capex scope/cost lines, vendor commitments (Level 4)',
    'description': """
Level 4 of the real estate developer product restructuring.

Fixed in this pass: arkzayed_construction_progress was a standalone module that duplicated
arkzayed.construction.progress (model, both real.estate.unit/building mixin extensions, views,
wizards, security, report) byte-for-byte against code that already lived inside
arkzayed_18_realestate_development, which depended on it. It also hardcoded report_name/report_file
as "arkzayed_construction_progress.report_progress" inside the OTHER module's own copy of
report_progress.xml - that copy only rendered correctly because the duplicate module happened to
also ship a template with the same id. The standalone module has been deleted; its abstract report
model's _name and the report action's report_name/report_file (which stays in
arkzayed_18_realestate_development, deferred along with the rest of that module's views) have been
corrected to self-consistently point at arkzayed_18_realestate_development.report_progress.
    """,
    'author': 'iSkyDev',
    'depends': [
        'base',
        'mail',
        'project',
        'isky_18_realestate_developer_unit_inventory',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
