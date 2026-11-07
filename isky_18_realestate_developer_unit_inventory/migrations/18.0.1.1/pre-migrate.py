"""Phase 7: carry the client-prefixed config parameters onto the generic `realestate.` prefix.

Runs before this module's data loads, on every database where it is already installed. A no-op on a
fresh one. See `hooks.py` for the map and for the one key deliberately left behind.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.isky_18_realestate_developer_unit_inventory.hooks import (
        rename_config_parameters,
    )
    rename_config_parameters(env)
