"""Phase 7: the client-prefixed `ir.config_parameter` keys become generic.

Every key the isky modules read or write moved from `arkzayed_18_realestate_development.` (and two
strays, `arkzayed.` and Odoo's own `crm.`) to `realestate.`, which matches the product's model
prefix and squats nobody's namespace. The code now uses the new keys only; this module carries the
rename so an existing database keeps every configured account, journal, percentage and toggle.

It lives in L0 because L0 is the one module every layer and bridge depends on, and the keys belong
to no single layer - L1 declares 20, L2 declares 16, and L0, L2 and L3 read them. Called from
`migrations/18.0.1.1/pre-migrate.py`.

Deliberately NOT renamed: `arkzayed_18_gt_cheque_management.journal_id`. That key is **written by
the legacy cheque module's own settings page**, which this branch may not edit, so renaming our side
would simply stop us reading what the user sets. It stays until that module is dealt with - backlog
#29 and open question 12.3, both already parked for a later decision.
"""

import logging

_logger = logging.getLogger(__name__)

NEW_PREFIX = 'realestate.'

# old key -> new key. Explicit rather than a prefix rewrite, because the same module prefix also
# appears in `env.ref()` xmlids, which must not be touched.
OLD_PREFIX = 'arkzayed_18_realestate_development.'
_PREFIXED = [
    'apply_cents_in_last_line',
    'apply_to_nearer_ten',
    'cancellation_penalty_account_id',
    'cancellation_refund_credit_account_id',
    'cancellation_refund_debit_account_id',
    'cancellation_refund_journal_id',
    'collection_debit_account_id',
    'collection_journal_id',
    'commission_credit_account_id',
    'commission_debit_account_id',
    'commission_journal_id',
    'deferred_revenue_overseas_account',
    'enable_reservation_expiry_cron',
    'income_account',
    'installment_price_tolerance',
    'maintenance_account_id',
    'market_fees_account',
    'non_sales_commission_collection_percentage',
    'non_sales_commission_percentage',
    'onhold_reservation_expiration_hours',
    'overseas_installment_account',
    'overseas_maintenance_account',
    'penalty_credit_account_id',
    'penalty_debit_account_id',
    'penalty_journal_id',
    'sale_commission_credit_account_id',
    'sale_commission_debit_account_id',
    'sale_commission_journal_id',
    'service_account',
    'unpaid_reservation_expiration_hours',
]

KEY_MAP = {OLD_PREFIX + name: NEW_PREFIX + name for name in _PREFIXED}

# The four GIS/OAYA keys are not in the map: Phase 7 replaced them with
# realestate.revenue.split.line rows, and `migrate_revenue_split_rows` below converts them.

# Strays, each with its own history:
#   - `arkzayed.non_residential_default_years` was the key the settings field declared, while
#     `arkzayed.residential_default_years` was read by two call sites but written by nobody: the
#     residential setting wrote `…development.residential_default_years` instead, so the value a
#     user typed was never used (backlog #68). Both sides now meet on one key each, which makes
#     the residential setting take effect for the first time.
#   - the two unit-hold keys sat on Odoo's `crm.` prefix.
KEY_MAP.update({
    'arkzayed.non_residential_default_years': NEW_PREFIX + 'non_residential_default_years',
    'arkzayed.residential_default_years': NEW_PREFIX + 'residential_default_years',
    OLD_PREFIX + 'residential_default_years': NEW_PREFIX + 'residential_default_years',
    'crm.enable_crm_unit_hold': NEW_PREFIX + 'enable_unit_hold',
    'crm.crm_unit_hold_duration': NEW_PREFIX + 'unit_hold_duration',
})

# When two old keys map to the same new key, the one the settings form wrote wins.
PREFERRED_SOURCE = {
    NEW_PREFIX + 'residential_default_years': OLD_PREFIX + 'residential_default_years',
}


def rename_config_parameters(env):
    """Copy each old key's value onto its new key. Idempotent; never overwrites a new key that
    already holds a value, and leaves the old rows in place so a rollback can still read them."""
    ICP = env['ir.config_parameter'].sudo()
    moved, skipped = [], []
    for new_key in sorted(set(KEY_MAP.values())):
        # `get_param` answers False, not None, for a key that is not set - so an `is not None`
        # guard here would skip every key and migrate nothing. Caught by
        # test_the_rename_carries_a_value_and_is_idempotent.
        if ICP.get_param(new_key) not in (False, None, ''):
            skipped.append(new_key)
            continue
        sources = [old for old, new in KEY_MAP.items() if new == new_key]
        preferred = PREFERRED_SOURCE.get(new_key)
        if preferred in sources:
            sources = [preferred] + [s for s in sources if s != preferred]
        for old_key in sources:
            value = ICP.get_param(old_key)
            if value not in (False, None, ''):
                ICP.set_param(new_key, value)
                moved.append('%s -> %s' % (old_key, new_key))
                break
    if moved:
        _logger.info("Phase 7: carried %d config parameter(s) to the generic prefix: %s",
                     len(moved), '; '.join(moved))
    if skipped:
        _logger.info("Phase 7: %d generic key(s) already set, left alone", len(skipped))
    return moved
