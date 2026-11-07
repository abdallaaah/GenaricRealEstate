"""Stage-xmlid adoption (#49) and the revenue-split conversion (Phase 7).

#49: the lead stage rows this module needs used to be defined in
`arkzayed_18_realestate_developer_crm`, which this module does not depend on. They are now seeded
from `data/lead_stage_data.xml` and `data/crm_stage_data.xml`. On a database that already holds the
legacy rows, seeding would create a second set of stages next to the ones the leads actually point
at, so the legacy rows are **adopted** first: each gets a second `ir.model.data` row under this
module, pointing at the same record. Odoo allows several xmlids per record, so the data load then
resolves to the existing row instead of inserting a twin, and the client keeps its stage data.

Phase 7: the two hardcoded business lines of the revenue split (four client-named config
parameters, plus two client-named booleans on `account.analytic.account`) become
`realestate.revenue.split.line` rows. `migrate_revenue_split_rows` builds them from whatever the
database already holds, so an existing client keeps posting the same collection entries.

`adopt_legacy_stage_xmlids` is called from `migrations/18.0.1.1/pre-migrate.py` - it has to run
*before* the stage data loads. It therefore touches no model but `ir.model.data`: a pre-migrate for
this module runs before `load_openerp_module()` imports it, so `lead.stage` and this module's
`crm.stage` extension are not in the registry yet, and row existence is checked in SQL against the
table - which is why each entry carries its table name explicitly.

`migrate_revenue_split_rows` is called from `migrations/18.0.1.2/post-migrate.py` instead, for the
mirror-image reason: it *creates* records of a model this module declares, so it has to run after
the module is loaded.
"""

import logging

_logger = logging.getLogger(__name__)

THIS_MODULE = 'isky_18_realestate_developer_sales_crm'
LEGACY_MODULE = 'arkzayed_18_realestate_developer_crm'

# local xmlid -> (model, table), for every stage row this module seeds that the legacy module also
# defines. The local names match the legacy ones so an adopted row keeps its identity; see the
# decisions log, 2026-11-07.
#
# `stage_qualified_limited_budget` is absent on purpose: it is commented out in the legacy data
# file, so there is never a legacy row to adopt (backlog #56). The data file creates it.
ADOPTED_STAGES = {
    'stage_new': ('lead.stage', 'lead_stage'),
    'stage_no_answer': ('lead.stage', 'lead_stage'),
    'stage_call_later': ('lead.stage', 'lead_stage'),
    'stage_follow_up': ('lead.stage', 'lead_stage'),
    'stage_qualified': ('lead.stage', 'lead_stage'),
    'stage_unqualified': ('lead.stage', 'lead_stage'),
    'stage_locked': ('lead.stage', 'lead_stage'),
    'stage_lead5': ('crm.stage', 'crm_stage'),
    'stage_lead6': ('crm.stage', 'crm_stage'),
    'stage_lead7': ('crm.stage', 'crm_stage'),
    'stage_lead8': ('crm.stage', 'crm_stage'),
}

# Phase 7: the old parameter pairs, in the order they were posted. The names are not written here -
# each row is named after its own credit account, so no client business-line name enters the code.
OLD_SPLIT_PARAMS = [
    ('arkzayed_18_realestate_development.collection_credit_gis_account_id',
     'arkzayed_18_realestate_development.collection_gis_percentage',
     'is_gis_account'),
    ('arkzayed_18_realestate_development.collection_credit_oaya_account_id',
     'arkzayed_18_realestate_development.collection_oaya_percentage',
     'is_oaya_account'),
]


def _row_exists(cr, table, res_id):
    """True when the record an ir.model.data row points at is really still there."""
    cr.execute(
        'SELECT 1 FROM information_schema.tables WHERE table_name = %s AND table_schema = %s',
        (table, 'public'))
    if not cr.fetchone():
        return False
    cr.execute('SELECT 1 FROM "%s" WHERE id = %%s' % table, (res_id,))
    return bool(cr.fetchone())


def adopt_legacy_stage_xmlids(env):
    """Give every surviving legacy stage row a second xmlid under this module.

    Idempotent, and a no-op on a database with no legacy rows (the plain L2 case), which is why
    it can run unconditionally. Returns the list of adopted xmlid names.
    """
    IMD = env['ir.model.data'].sudo()
    adopted, already_ours, orphaned = [], [], []
    for name, (model, table) in ADOPTED_STAGES.items():
        legacy = IMD.search(
            [('module', '=', LEGACY_MODULE), ('name', '=', name), ('model', '=', model)], limit=1)
        if not legacy:
            continue
        if IMD.search_count(
                [('module', '=', THIS_MODULE), ('name', '=', name), ('model', '=', model)]):
            already_ours.append(name)
            continue
        if not _row_exists(env.cr, table, legacy.res_id):
            # the record was deleted while its ir.model.data row survived; let the data file
            # create a fresh one rather than pointing an xmlid at nothing
            orphaned.append(name)
            continue
        IMD.create({
            'module': THIS_MODULE, 'name': name, 'model': model,
            'res_id': legacy.res_id,
            # False so a later reseed may still correct the row; the data files are themselves
            # noupdate="1", so in practice nothing of the client's is overwritten.
            'noupdate': False,
        })
        adopted.append(name)

    if adopted:
        _logger.info("#49: adopted %d legacy stage xmlid(s) from %s: %s",
                     len(adopted), LEGACY_MODULE, ', '.join(sorted(adopted)))
    if already_ours:
        _logger.info("#49: %d stage xmlid(s) already owned here: %s",
                     len(already_ours), ', '.join(sorted(already_ours)))
    if orphaned:
        _logger.warning("#49: %d legacy stage xmlid(s) point at a deleted record, not adopted: %s",
                        len(orphaned), ', '.join(sorted(orphaned)))
    return adopted


def _analytic_account_id(cr, flag_column):
    """The analytic account an old client-named flag marked, read in SQL.

    The flag fields were removed from the L1 bridge in Phase 7, but Odoo does not drop columns
    when a field disappears, so the data is still there to convert - and reading it in SQL means
    this works whether or not the bridge is installed.
    """
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'account_analytic_account' AND column_name = %s", (flag_column,))
    if not cr.fetchone():
        return False
    cr.execute('SELECT id FROM account_analytic_account WHERE "%s" IS TRUE ORDER BY id LIMIT 1'
               % flag_column)
    row = cr.fetchone()
    return row[0] if row else False


def migrate_revenue_split_rows(env):
    """Turn the old two-business-line configuration into revenue split rows.

    Idempotent: a company that already has rows is left alone. Each row is named after its credit
    account, so the client's business-line names come from their own data rather than from this
    file. Returns the rows created.
    """
    ICP = env['ir.config_parameter'].sudo()
    Line = env['realestate.revenue.split.line'].sudo()
    created = Line.browse()
    for company in env['res.company'].sudo().search([]):
        if Line.search_count([('company_id', '=', company.id)]):
            continue
        sequence = 10
        for account_key, percentage_key, flag_column in OLD_SPLIT_PARAMS:
            account_id = ICP.get_param(account_key)
            percentage = ICP.get_param(percentage_key)
            try:
                percentage = float(percentage or 0.0)
            except (TypeError, ValueError):
                percentage = 0.0
            if not account_id or percentage <= 0.0:
                continue
            account = env['account.account'].sudo().browse(int(account_id)).exists()
            if not account:
                continue
            analytic_id = _analytic_account_id(env.cr, flag_column)
            created |= Line.create({
                'name': account.display_name,
                'sequence': sequence,
                'company_id': company.id,
                'account_id': account.id,
                'analytic_account_id': analytic_id or False,
                'percentage': percentage,
            })
            sequence += 10
    if created:
        _logger.info("Phase 7: created %d revenue split line(s) from the old configuration: %s",
                     len(created), ', '.join(created.mapped('name')))
    return created
