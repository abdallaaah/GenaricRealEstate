"""#49: adopt the legacy stage xmlids before this module's new stage data loads.

Runs on every database where this module is already installed - which is every existing one, since
the stage rows used to live in `arkzayed_18_realestate_developer_crm` and this module shipped none.
Without it, loading `data/lead_stage_data.xml` and `data/crm_stage_data.xml` would insert a second
set of stages beside the ones the client's leads point at.

A no-op where the legacy module was never installed. See `hooks.py` for the mechanism and the
decisions log, 2026-11-07, for why the rows moved.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        # a fresh install does not need adoption: the legacy CRM module depends on this one, so
        # it can only be installed afterwards and its rows cannot exist yet
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    # imported here, not at module level: at pre-migrate time Odoo has not yet imported this
    # addon, and the import must not be a side effect of merely collecting migration scripts
    from odoo.addons.isky_18_realestate_developer_sales_crm.hooks import (
        adopt_legacy_stage_xmlids,
    )
    adopt_legacy_stage_xmlids(env)
