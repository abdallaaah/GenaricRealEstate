"""Phase 7: convert the old two-business-line revenue split into rows.

**post**-migrate, not pre: the conversion creates `realestate.revenue.split.line` records, and a
pre-migrate for this module runs before Odoo imports it, so that model would not be in the registry
yet. (The stage adoption in 18.0.1.1 is a pre-migrate for the opposite reason - it must run before
the stage data loads, and it touches only `ir.model.data`.)

Runs on every database where this module is already installed; a no-op where there is nothing to
convert, and idempotent for a company that already has rows. See `hooks.py` for the mapping and for
why the old analytic flags are read in SQL.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.isky_18_realestate_developer_sales_crm.hooks import (
        migrate_revenue_split_rows,
    )
    migrate_revenue_split_rows(env)
