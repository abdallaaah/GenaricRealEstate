{
    'name': 'Ark Zayed Cost Distribution',
    'version': '1.1',
    'summary': 'Distribute shared costs (PO/Bill lines) across units by area, and track direct vs indirect cost per unit',
    'author': 'iSkyDev',
    'depends': [
        'account', 'isky_18_realestate_developer_unit_inventory', 'isky_18_realestate_developer_accounting',
        # Needed for views only (real.estate.unit/building, zone form views to inherit) - L0 has
        # no form views of its own yet, that's a separate, already-flagged gap. Does NOT
        # reintroduce the Phase 2 cycle: that cycle was broken by removing the accounting
        # bridge's own upward edges to this module and to arkzayed_18_realestate_development,
        # not by this (one-directional, downward) edge.
        'arkzayed_18_realestate_development',
    ],
    'license': 'LGPL-3',
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'report/report_cost_distribution.xml',
        'wizard/distribution_wizard_views.xml',
        'views/real_estate_unit_views.xml',
        'views/hierarchy_views.xml',
        'views/cost_allocation_views.xml',
        'views/cost_distribution_views.xml',
    ],
    'application': False,
}
