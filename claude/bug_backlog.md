# Bug Backlog — pre-existing issues found during verification

Rule: a bug goes here if it does NOT block installing the new layers (L0, L1 bridge, L2, L3, L4, sales_cheques). A bug that blocks installation is fixed in the current phase, on the developer_18 branch, never in legacy repos.

Status values: OPEN, FIXED-IN-NEW, NEEDS-REVIEW, WONT-FIX, REVERTED.

## Blocked-installation fixes (developer_18 modules only, no legacy files touched)

These blocked installation, so per the rule above they were fixed in-phase rather than parked. All in `isky_18_realestate_developer_*` only. Full reasoning per item is in `decisions_log.md`.

| # | Module / file | Symptom | Type | Blocks new layers? | Status |
|---|---|---|---|---|---|
| 1 | L0 `unit_inventory` ← L2 `sales_crm/models/config/installment_mixin.py` | `real.estate.unit` (L0) `_inherit`s `installment.mixin`, defined in L2; L0 could not install alone | L0→L2 layering | YES | FIXED-IN-NEW |
| 2 | L0 `unit_inventory/models/__init__.py` | `core` imported before `config`; `_inherit` parent not yet built at registry-build time | import order | YES | FIXED-IN-NEW |
| 3 | L0 `unit_inventory/models/core/sequence.py` | dead class (`ssdsdsdd`) inheriting `account`'s `sequence.mixin` (undeclared dep); body called `_()` without importing it | dead code | YES | FIXED-IN-NEW (deleted) |
| 4 | L0 `unit_inventory/models/config/archive_place.py` | `One2many('sale.proposal', ...)` + dependent compute, from L0 into L2 | L0→L2 layering | YES | FIXED-IN-NEW |
| 5 | L0 ← L2 `down.payment.increase`, `installment.template`, `maintenance.template` | L0 `real.estate.unit` Many2ones to three config models defined in L2 | L0→L2 layering | YES | FIXED-IN-NEW (moved to L0) |
| 6 | L0 `security/security.xml` ← L2 `res.users.realestate_project_ids` | L0's own record rules filter on a field defined only in L2 | L0→L2 layering | YES | FIXED-IN-NEW |
| 7 | L1 `accounting/models/account_cash_flow.py` | `_inherit`s `account.cash.flow.report.handler` (Enterprise `account_reports`), undeclared in manifest | missing dependency | YES | FIXED-IN-NEW |
| 8 | L1 `accounting/views/res_config_settings_views.xml` | inherited `arkzayed_18_realestate_development`'s settings-tab container, so the "optional" bridge hard-depended on the monolith | legacy coupling | YES | FIXED-IN-NEW |
| 9 | L4 `construction/security/ir.model.access.csv` | referenced 3 groups (`group_vendor_commitment_user`, `group_progress_engineer`, `group_progress_manager`) defined in the monolith, which L4 must not depend on | legacy coupling | YES | FIXED-IN-NEW (own `security.xml`) |
| 10 | L2 `sales_crm/wizard/sales_achievement_report.py` | `_name` yields a 68-char table name, over Postgres' 63-char identifier limit | Postgres limit | YES | FIXED-IN-NEW (`_table` override) |
| 11 | L2 `sales_crm` + L3 `commission`, 10 fields | `default=lambda self: _('New')` → translation lookup reads `res.partner` before its new columns are schema-synced on a fresh install | fresh-install race | YES | FIXED-IN-NEW (`default='New'`) |
| 12 | L2 `eoi.py`, `sale_reservation.py`, `sale_proposal.py` | `commission_ids` One2many → `realestate.commission` (L3); each also had a **duplicate dead** `_build_commission_hierarchy` shadowed by a later-imported copy | L2→L3 layering + duplicate dead code | YES | FIXED-IN-NEW (live copy → L3, dead copy deleted) |
| 13 | L2 `sale_proposal.py` | `commission_achievement_ids`, `non_sales_claim_ids`, `all_commission_claim_ids` One2many → L3 | L2→L3 layering | YES | FIXED-IN-NEW |
| 14 | L2 `sale_proposal.py` | `commission_achievement_count` / `non_sales_claim_count` `@api.depends` named a field L3 adds later; depends resolution runs while L2 loads | L2→L3 layering | YES | FIXED-IN-NEW (moved with their field) |
| 15 | L2 `eoi.py`, `sale_proposal.py`, `sale_reservation.py` (6 fields) | `domain=[('job_level_id.is_*', ...)]` on Many2many registers an implicit dependency walking into L3 `job.level`; resolves to `_unknown` and hard-fails | L2→L3 layering | YES | FIXED-IN-NEW (domains removed — see note) |

Note on #15: removing those domains loses UI narrowing on salesperson pickers (dropdowns now offer more users than ideal). No stored data or business logic changed. A proper fix needs the `job_level_id` relationship resolved, which is Phase 4's scope.

## Parked — does not block new layers

| # | Module / file | Symptom | Type | Blocks new layers? | Status |
|---|---|---|---|---|---|
| 16 | `arkzayed_18_realestate_development/models/real_estate_lease_contratct.py` | same `default=lambda self: _('New')` pattern as #11; not yet observed firing | fresh-install race | not observed | OPEN (legacy) |
| 17 | L2 `sales_crm/models/core/crm_team_hierarchy.py` | `director_id`, `operation_id`, `sales_manager_id` carry the same `job_level_id.is_*` domain as #15, but as Many2one (which only warns, does not hard-fail) | L2→L3 layering | not observed | OPEN |
| 18 | L2 `sales_crm` standalone | cannot install entirely alone (#15/#17 class of coupling); never a supported configuration in Phase 2 | layering | n/a | WONT-FIX until Phase 4 |
| 19 | L1 `accounting/models/account_account.py` | `unique_change_ownership_type` partial-index constraint not applied by Odoo's schema sync (logged as ERROR, install continues) | schema | no | OPEN |
| 20 | core `crm_lead` | `unable to set NOT NULL on column 'source_id'` / `'medium_id'` during install | schema | no | OPEN |
| 21 | L1 `accounting/views/account_payment_views.xml` | CFO / Deputy-CEO approval buttons gated on `arkzayed_18_realestate_development.payment_{cfo,deputy_cfo}_group`; with the bridge installed and the monolith absent, the groups resolve to nobody and the buttons are permanently hidden | degraded behavior | no | OPEN |
| 22 | L2 `sales_crm/models/core/crm_lead.py` | `commission_ids` → `commission.commission` (`persons_commission.py`), while L3 has a near-identical `realestate.commission`. Whether these are one concept under two names is a Phase 4 question | duplicate model? | no | OPEN |
| 28 | `arkzayed_cost_distribution`: `views/cost_distribution_views.xml`, `wizard/distribution_wizard.py` (lines 26, 171, 173) | Was introduced by the Option A revert, then **resolved** when that revert was undone — the revert had been based on a misreading of which repo is the protected legacy one (see `decisions_log.md`, 2026-11-04 CORRECTION). The cost-allocation fields are restored in `arkzayed_cost_distribution/models/account_move_line.py` | consequence of Phase 2 | no | **RESOLVED** — patch re-applied to GenaricRealEstate |
| 29 | `arkzayed_18_gt_cheque_management` (module name) | Serves as the L1 generic cheque module per S1 and already satisfies S1's "no sales references" requirement in substance (no sales field definitions; one defensive `getattr(self, 'sale_proposal_id', False)` guarded by a comment). Only its **name** is client-specific. Renaming now would churn every `depends`, every qualified `ref=`, and the `report.<module>.<name>` report parser lookups while the product is still moving | naming / cosmetic | no | OPEN — **deferred: rename to a generic name once the product is stable. Not Phase 3.** |

## Legacy-owned fixes — REVERTED, awaiting re-application on developer_18

Applied during Phase 2 verification **before** the no-legacy-edits rule was set, then **all reverted** on 2026-11-04 per that rule (user chose Option A). Legacy repos are now at **zero diff** — verified with `git status`.

The complete reverted diff is preserved at **`claude/legacy_fixes_to_reapply.patch`** (793 lines, 32 files). Each fix below is mechanical — same target, corrected reference, zero logic change — and each is required for its module to import or load data at all, so all of them need re-applying to the new-branch copies when those are created.

Status `REVERTED` = the fix is known, captured in the patch, and currently **not** applied.

| # | Module / file | Symptom | Type | Blocks new layers? | Status |
|---|---|---|---|---|---|
| 23 | `arkzayed_18_realestate_development/wizard/broker_statement_wizard.py` and `arkzayed_trace_commission/wizard/trace_commission.py` | `from ...arkzayed_18_realestate_development.models.sale_proposal import COMMISSION_EXCLUDED_STATES` — that file no longer exists (absorbed into L2 before this session); neither module has imported successfully since | dangling import | blocks legacy stack only | REVERTED |
| 24 | `arkzayed_18_realestate_development` + `arkzayed_18_realestate_developer_crm`, ~45 occurrences across `security/`, `views/`, `data/`, `reports/` | unqualified `ref="model_<x>"` for models owned by other modules; only resolves when the current module owns the target | unqualified XML ref | blocks legacy stack only | REVERTED |
| 25 | `arkzayed_cost_distribution`: new `models/account_move_line.py`, `models/__init__.py`, `views/cost_distribution_views.xml` | Phase 2 required stripping the `arkzayed.cost.allocation` fields (`allocation_ids`, `distribution_state`, `distributed_amount`, `remaining_amount`) from the L1 bridge; they were put back in cost_distribution, where the bridge's own manifest docstring says they originated. If reverted they exist in **no** module | forced relocation | — | REVERTED — Option A chosen; see #28 |
| 26 | `arkzayed_18_realestate_development`: `security/security.xml`, `views/menus.xml`, `__manifest__.py`, deleted `security/construction_progress_security.xml` | counterpart of #9 — the three construction groups were removed from the monolith and the one surviving `groups=` reference requalified | legacy coupling | — | REVERTED |
| 27 | `arkzayed_cost_distribution/__manifest__.py` | added explicit `isky_18_realestate_developer_unit_inventory` (already transitive); `arkzayed_18_realestate_development` retained because its views inherit form views that exist only there (L0 has no form views yet) | manifest | — | REVERTED |

## Categories already seen in Phase 2

- Dangling imports
- Unqualified XML refs
- Table name longer than the Postgres limit
- Translated-default race condition
- Duplicate dead code
- L2 to L3 layering issues

## Fix policy

Legacy-owned files (`arkzayed_*`, `marketstandards`): never edited. Mechanical fix goes to developer_18 only.

NEEDS-REVIEW: any fix that touches legacy-owned files or changes behavior, not only syntax.

## Phase 3 step 3 / step 4 findings (2026-11-05)

30. **`installment.lines` / `maintenance.installment.lines` collected-state test was a
    substring test, not a membership test.** The originals read
    `if alloc.payment_id.state in ('paid')` and `alloc.cheque_id.state in ('done')` -
    single-quoted strings, not tuples, so `in` compared substrings. No current payment state
    (`draft, in_process, paid, canceled, rejected`) or cheque state is a proper substring of
    `'paid'`/`'done'`, so the behaviour was accidentally correct. Phase 3 step 3 replaced both
    with explicit `== 'paid'` / `== 'done'` inside
    `payment.allocation._is_collected()`. Nothing to fix; recorded because it is money math
    and the original intent was clearly a tuple.

31. **`payment.allocation.execute_data_migration()` is dead weight in a greenfield product.**
    It reads `doc.cheque_ids` / `doc.cheque_manage_ids` and writes `cheque_id` allocation keys
    directly, so with the cheque bridge absent it raises `AttributeError` when called. It is
    never called by any view, action or cron - it is a one-off data-migration helper for the
    client's existing database. The decision of 2026-11-05 ("greenfield, no migrations") means
    it should be deleted outright rather than split across the cheque bridge. Not install-
    blocking: left in place pending that call.

32. **`sale.proposal` cheque generation references two wizard models that live in the
    monolith.** `action_create_cheques()` and `action_open_combined_cheque_wizard()` call
    `env['sale.proposal.cheque.wizard']` and `env['combined.cheque.wizard']`, both defined in
    `arkzayed_18_realestate_development/wizard/`, which neither `sales_crm` nor
    `isky_18_realestate_developer_sales_cheques` depends on. Runtime `env[...]` lookups, so not
    install-blocking, but those two buttons raise `KeyError` unless the monolith is installed.
    The two wizards need carving into the cheque bridge before the cheque-generation feature
    can be called complete.

33. **Client-prefixed config parameter inside an `isky_*` module.** The cheque code moved into
    `isky_18_realestate_developer_sales_cheques` reads
    `ir.config_parameter` key `arkzayed_18_gt_cheque_management.journal_id`
    (`sale_proposal._generate_cheques()`, `maintenance_installment_lines.action_create_cheque()`).
    This breaks the CLAUDE.md rule against client-prefixed config parameters in the generic
    modules. Phase 7 owns renaming it to a generic key; the value is written by the legacy
    cheque module's settings page, so the rename has to move both sides at once.

34. **FIXED-IN-NEW (S8, 2026-11-05)** — ~~RELEASE BLOCKER~~ no cheque could be created programmatically on a fresh database.
    `cheque.manage.credit_account` is `required=True`, and on a fresh install the column is
    `NOT NULL` (verified: `information_schema` reports `is_nullable = NO`). No cheque-creating
    call site anywhere supplies it - not `maintenance.action_create_cheque()`, not
    `installment_lines.make_cheque_payment()`, not `eoi`/`sale_reservation.create_cheque_payment()`,
    and not `sale_proposal._generate_cheques()`, which is the main production path. Confirmed
    against git HEAD: the original `cheque_vals` dicts never set it either, so this is
    pre-existing and not a Phase 3 regression.

    The two possible configurations are mutually exclusive, which is why no workaround exists
    (measured in `claude/logs/phase3_probe_credit.log`):

    | `…gt_cheque_management.journal_id` | result |
    |---|---|
    | set (what every creating action requires) | `cheque.manage.default_get()` runs its `res.update({… 'credit_account': None …})` and **overwrites** any value a caller or a `default_credit_account` context key supplied → `NotNullViolation` |
    | unset | a context default survives and the create succeeds, but every action refuses first with "Please configure the cheque journal" |

    Root cause: `default_get` resolves `debit_inc_account` for incoming cheques and
    `credit_out_account` for outgoing ones, then writes **both** keys unconditionally. For an
    incoming cheque `credit_account` is therefore always forced to `None`. There is no
    `credit_inc_account` parameter at all.

    Why it has not been noticed: in a long-lived database the `NOT NULL` was almost certainly
    never applied (Odoo logs a warning and leaves the column nullable when existing rows hold
    nulls), so the client's production database tolerates the null. Every **new** deployment
    starts from a fresh database, so for a generic product this is a release blocker, not a
    cosmetic issue.

    Three candidate fixes, in increasing order of correctness - **needs a decision**:
    1. Make `default_get` set only the keys it actually resolved (one line, but it is in the
       legacy `arkzayed_18_gt_cheque_management`, which CLAUDE.md puts off limits).
    2. Have the cheque-creating actions pass the customer's receivable account explicitly.
    3. Phase 7: add a generic incoming-credit-account setting next to the existing ones and
       have every creating path read it. This is the real fix and Phase 7 already owns the
       renaming of these parameters (backlog #33).

    **Fix (S8, option 3 of the three below):** a company-level setting
    `res.company.cheque_incoming_credit_account_id`, read by
    `cheque.manage._resolve_incoming_credit_account()`, which is called from the
    `cheque.manage.create()` override in `isky_18_realestate_developer_sales_cheques`. That
    override is the single choke point all 11 create call sites pass through, so no call site
    needed patching and no legacy file was touched. `default_get()` is also overridden there so
    the legacy implementation can no longer discard a caller's credit account. When the setting
    is empty the create raises `UserError` naming the setting; the NOT NULL constraint is never
    reached.

    Commit: **pending** - commits are held until the user asks (decisions log, 2026-11-04), so
    there is no hash to record yet. Update this line when the Phase 3 work is committed.

    Tests (`isky_18_realestate_developer_sales_cheques/tests/test_s8_cheque_settings.py`):
    `test_cheque_create_with_setting`, `test_cheque_create_without_setting`,
    `test_cheque_create_without_setting_raises_before_insert`,
    `test_cheque_generation_toggle_off`, `test_manual_cheque_unaffected_by_toggle`,
    `test_default_get_keeps_caller_value`, `test_default_get_falls_back_to_setting`,
    `test_cheques_enabled_defaults_on`,
    `test_all_sales_cheque_paths_covered_by_choke_point`. The last one drives
    `maintenance.action_create_cheque()` end to end, which is the path that was previously
    impossible to cover; the uncovered-path note has been removed from
    `claude/logs/phase3_maintenance_cheque_actions.log`'s test, which now asserts the full
    happy path plus the cleared-setting guard.

    **Residual gap:** the choke point lives in `sales_cheques`, so it is absent in a database
    where the legacy cheque module is installed *without* `sales_cheques` (which needs
    `sales_crm` too). In that configuration the monolith's four cheque wizards
    (`combined_cheque_wizard`, `cheque_merge_wizard`, `cheque_split_wizard`,
    `contract_change_ownership_wizard`) can still hit the NOT NULL. Closing that needs the
    setting to live at L1, which today means either editing the legacy cheque module (off
    limits per CLAUDE.md) or a new L1-level `isky` cheque-config module - a scope decision,
    see the 2026-11-05 S8 placement note in the decisions log.

    **Decision (2026-11-05): option 3** - resolved by the generic setting
    `cheque_incoming_credit_account_id` (Financials), read by every creating path, plus the
    `default_get` fix; an empty setting raises `UserError`. Implementation prompt:
    `claude/s8_cheque_settings_prompt.md`. Implemented and verified - see the S8 gate table in
    `claude/plan_status.md` for the run IDs.

35. **Residual L1 cheque gap (accepted until Phase 7).** The incoming-credit-account protection
    from #34 ships in `isky_18_realestate_developer_sales_cheques`. A database with the legacy cheque
    module but without `sales_cheques` has no protection. The monolith's four cheque wizards can still
    reach the NOT NULL constraint in that configuration. Status: OPEN-ACCEPTED. Fix in Phase 7, together
    with the setting's move to a generic L1 home and backlog #29's rename. Decision recorded in
    `decisions_log.md` (2026-11-05, 12.3 accepted).

## Phase 3 step 5 findings (2026-11-05)

35. **FIXED-IN-NEW — L2 called two L3-only methods, breaking record creation in Mode B.**
    Phase 2 moved `_build_commission_hierarchy` (reservation, contract) and
    `compute_person_hierarchy` (EOI) into L3 `isky_18_realestate_developer_commission` but left
    **12 call sites in L2** (10 and 2 respectively). Runtime attribute reads, so no install gate
    caught it; creating a reservation, contract or EOI with the commission module absent raised
    `AttributeError`. Regression from Phase 2, not a legacy defect. Fixed with
    `realestate.sales.commission.hooks` (no-op L2 bases, overridden by L3). Found by the step 5
    tests; see the decisions log entry of 2026-11-05 for the lesson about install gates not
    seeing cross-layer calls.

36. **`customer.ownership` had no sum-to-100 constraint of any kind** (no `_sql_constraints`, no
    `@api.constrains`) despite being the ownership-percentage split used by both reservations
    and contracts. Any combination of percentages was accepted. Fixed in step 5 by
    `realestate.split.line.mixin`. Recorded because it means **existing data may already
    violate the rule**: a database with historical splits that do not total 100 will raise on
    the next write to those lines. A data audit before deployment is advisable - this is not a
    migration the greenfield decision covers, since it concerns the client's live database.

37. **`action_copy_customer_ownership_ids` was duplicated verbatim** in `sale_reservation.py`
    and `sale_proposal.py` - 34 lines each, differing only in the FK key and one word of the
    error message. Consolidated into `realestate.split.parent.mixin` in step 5.

38. **`commission.commission` is declared in L2, not L3.** `sales_crm/models/core/persons_commission.py`
    defines `_name = "commission.commission"` with per-user commission percentages on a
    `crm.lead`. By the layer model this is an L3 concept sitting in L2. Not install-blocking and
    not touched by step 5; flagged for the Phase 3/L3 boundary review.

39. **`sale.proposal` has no `project_id`.** A contract reaches its project only through
    `unit_id.project_id`, or through the reservation it came from. Step 5's lock rule works
    around this with a two-route search, but any future per-project rule on contracts will hit
    the same gap. Worth considering a stored related field in a later phase.

## Phase 3 step 6 findings (2026-11-06)

40. **The UI for isky-owned models is spread across 8 modules, not just the monolith.**
    `lint_s4_views.py` counts 215 view records: `arkzayed_18_realestate_development` 177,
    `arkzayed_18_realestate_developer_crm` 27, `arkzayed_collections_report` 3,
    `arkzayed_cost_distribution` 3, `isky_base_modification` 2, `isky_contract_template` 2,
    `arkzayed_contract_npv` 1. The last two are `isky_*` modules, so the no-legacy-edit rule
    never covered them. Phase 3c owns the migration; the lint prints the live count.

41. **L0 `unit_inventory` ships no views, no window actions and no menus** for its own 41
    models. Any shared root menu placed there is hidden by Odoo until L0 owns at least one
    action, which is why Phase 3c must start with L0. Not install-blocking - the monolith
    currently supplies the UI.

42. **Two root menus will coexist during Phase 3c.** The monolith defines
    `menu_real_estate_root` "Real Estate" (101 menuitems) and
    `arkzayed_18_realestate_developer_crm` defines `menu_broker_root` "Units Inventory". The new
    L0 root cannot be introduced until enough of the migration is done to retire or re-parent
    those, or users see duplicate menus.

## Phase 4 findings (2026-11-06)

43. **`isky_18_realestate_developer_commission` (L3) had never been installable.** Its
    `models/config/sale_commission_plan.py` does `_inherit = "sale.commission.plan"`, an
    **Enterprise** model from `sale_commission`, which the manifest never declared - not even
    at git HEAD. Confirmed by checking every test database from Phases 2, 3 and S8: L3 is
    `uninstalled` in all of them, so no gate ever exercised it. Same class as the
    `account_reports` omission Phase 2 found in the L1 bridge (#7). Fixed in Phase 4 by
    declaring `sale_commission`. The module now installs and its 13 tests pass.

44. **RELEASE BLOCKER - no opportunity can be created in an L2-only database.**
    `crm.lead` has nine approval-status fields (`eoi_`/`contract_`/`reservation_` x
    `manager`/`financial`/`operations`), each defaulting to `'pending'` and each carrying an
    `@api.constrains` that demands a group from the legacy
    `arkzayed_18_realestate_developer_crm`. That module is not a dependency of `sales_crm`, so
    `has_group()` returns False for **every** user and creation is rejected nine times over.
    Found while building the Phase 4 mapping test, which had to set all nine falsy to create a
    single opportunity. Pre-existing; not caused by Phase 4.

45. **The guard-pattern lint was blind to most group references.** `lint_guard_pattern.py`
    check 2 matched only xmlids spelled `group_*`, so it reported PASS while `sales_crm` held
    **40 references to 8 legacy groups** whose names end in `_group` instead:
    `operation_manager_group` (10), `operation_executive_group` (7), `lead_admin_group` (7),
    `financial_manager_group` (6), `approval_manager_group` (6), `sales_manager_group` (2),
    `finance_group` (1), `director_manager_group` (1). Pattern widened in Phase 4; the check
    now **fails**, correctly. Fixing the 40 references means moving those 8 groups into
    `sales_crm` as Phase 3 step 1 did for `group_manual_paid_installment` - that is the same
    work as open question 12.2 and S7, and is **not yet done**.

46. **`res_users.py` in `sales_crm` is a pure duplicate.** It declares only
    `job_level_id = fields.Many2one('job.level')`, identical to the declaration in
    `res_user.py`, which loads second and wins. The whole file is redundant. Also note both
    declare an L2 field whose comodel `job.level` is L3 - tolerated because a Many2one to a
    missing comodel only warns.

47. **`crm.team`'s three role fields carry domains into L3.** `crm_team_hierarchy.py` (L2)
    sets `domain=[('job_level_id.is_directory', '=', True)]` and similar on `director_id`,
    `operation_id` and `sales_manager_id`. These walk into `job.level` (L3). They survive
    because a Many2one `domain` resolves at search time, unlike the Many2many domains Phase 2
    had to strip (#15) - but with L3 absent the domain silently matches nothing.

48. **FIXED-IN-NEW (2026-11-06) — the eight CRM role/approval groups moved into `sales_crm`.**
    `operation_manager_group`, `operation_executive_group`, `lead_admin_group`,
    `financial_manager_group`, `approval_manager_group`, `sales_manager_group`, `finance_group`
    and `director_manager_group` were defined in `arkzayed_18_realestate_developer_crm` and
    referenced from **40 places** in `sales_crm`, which does not depend on it - so `has_group()`
    returned False for every user and all 40 gates denied everyone. Now defined in
    `sales_crm/security/security.xml` with the legacy implied chain preserved
    (director -> sector manager -> sales manager -> `sales_team.group_sale_salesman`), and all
    40 references repointed. **No legacy file was touched**: the legacy module references only
    its own copies. Closes #44 and #45; `lint_guard_pattern.py` check 2 passes again.

    Two things to know. `operation_executive_group` was **commented out** in the legacy
    groups.xml, so it had never existed as a record - its 7 gates were dead twice over, and
    defining it makes them live for the first time. And in a database with both modules
    installed there are now two similarly named groups; a user holding the legacy one does
    **not** hold the new one, so existing users must be re-assigned. Both recorded as
    NEEDS REVIEW in the decisions log.

49. **`sales_crm` still depends on 22 other legacy-CRM xmlids at runtime - 35 of them via
    `env.ref()`, which raises rather than failing quietly.** Found while sweeping for the group
    references. They are not groups, so moving the groups did not address them:

    | Kind | xmlids | refs |
    |---|---|---|
    | CRM lead stages | `stage_new`, `stage_qualified`, `stage_qualified_limited_budget`, `stage_unqualified`, `stage_locked`, `stage_no_answer`, `stage_call_later`, `stage_follow_up`, `stage_lead5`-`stage_lead8` | 31 |
    | Portal templates | `portal_create_lead`, `portal_my_units`, `portal_create_unit`, `unit_list_view`, `portal_my_permission_request(s)`, `portal_create_permission_request` | 9 |
    | Cron | `ir_cron_release_held_units` | 2 |
    | Report | `action_report_sales_achievement`, `report_sales_achievement` | 3 |

    Consequence: the **entire lead workflow** in L2 - qualify, unqualify, lock, follow-up, stage
    transitions - raises `ValueError: External ID not found` without the legacy CRM module. The
    portal controllers 404 or raise. This is the same class as the groups but larger, and it is
    data, not code: the stage records have to be created in `sales_crm` (or a successor) and the
    portal templates and report moved, which is Phase 3c territory for the templates and a new
    data-migration task for the stages. **Not fixed.**

50. **FIXED-IN-NEW (2026-11-06) — `customer.ownership` audit fixes.** B1 (copy action aborted on
    any non-empty template, `return` instead of `continue`), B2 (contract lines double-counted
    into the reservation total), R1 (template rows never validated), R2 (0% split accepted),
    R3 (installment lines invisible to the project lock), R4 (hardcoded precision), R5
    (multi-company totals), C1 (four cleanups). All covered by
    `tests/test_ownership_fixes.py` (15 tests). Audit report and decisions in the decisions log,
    2026-11-06.

51. **`@api.constrains` does not fire on create for a field absent from the vals.** Found while
    implementing R3: a line created with neither `reservation_id` nor `sale_proposal_id` - the
    exact invisible-to-the-lock case - slipped past `@api.constrains('reservation_id',
    'sale_proposal_id')` entirely, because Odoo validates only the fields actually being
    written. The first test run failed for this reason; fixed with a `create()` override on both
    line models that calls the check explicitly. **Worth checking elsewhere**: any constrains in
    this codebase that guards "at least one of these must be set" has the same hole. Not swept
    in this run.

52. **`unit_inventory` and `commission` grant full CRUD to every user, including portal.**
    28 ACL rows in `isky_18_realestate_developer_unit_inventory/security/ir.model.access.csv`
    and 9 in `isky_18_realestate_developer_commission` have an **empty `group_id`**, which in
    Odoo applies the permission to every user with no group restriction at all - portal and
    public users included - with `1,1,1,1` on models including `realestate.project`,
    `real.estate.unit` and `cluster`. Found while writing 12.2's ACLs, which deliberately do
    not follow that convention. Tightening those rows is an L0/L3 change that needs its own
    review of who actually reads those models (the portal controllers in `sales_crm` render
    unit pages), so it is **not** done here. Severity: security.

53. **FIXED-IN-NEW (2026-11-06) — 12.2: `sales_crm` shipped no access rules.** 52 ACL rows added
    covering all 38 models it declares; `crm.lead` excluded as core-owned. Tests in
    `tests/test_acl_12_2.py` (8, all running `with_user`). `maintenance.config.get_config()`
    now bootstraps its singleton with `sudo()`. The S7 test's in-transaction ACL workaround was
    removed. See the decisions log, 2026-11-06.

54. **An Odoo CSV cannot carry comments.** A `#` line in `ir.model.access.csv` parses as a
    single column and raises `IndexError: list index out of range` while loading the file, which
    surfaces only as "Failed to load registry". Recorded because the rationale for a security
    matrix naturally wants to live beside it, and it cannot - it has to go in the module's XML
    or a separate document.

52. **RELEASE BLOCKER (priority set 2026-11-06, last in the work order).** `unit_inventory` (28 rows)
    and `commission` (9 rows) have an empty `group_id` in their access rules. In Odoo that grants full
    CRUD to every user, including portal and public, on models such as `realestate.project` and
    `real.estate.unit`. Not touched in 12.2 by design. Status: OPEN, release blocker. Fix goes in its
    own run with a read-only audit first: which portal or public routes render these models, and which
    rows must stay open. No client database may be deployed before this is closed.

---

# Reconstructed items, #55 onward (rebuilt 2026-11-09)

Items #1 to #54 above are original, restored from the 2026-11-06 snapshot. The items below were
rebuilt from `claude/recovery/reports_from_transcript.md` after the docs loss; each carries
`[RECONSTRUCTED]` and its transcript line. **Numbers quoted exactly from the reports.** Where a
report names an item number but not its text, that is said rather than invented.

**Gap, stated plainly:** items **#55 to #59** were created between 2026-11-06 and 2026-11-07 and
**no report in the pack names them**. `NOT RECOVERED: #55-#59.` They are referenced by nothing that
survives, so even their subjects are unknown.

61. `[RECONSTRUCTED]` <!-- transcript line 1048 --> **OPEN** — the progress report action and its
    parser still belong to the monolith. L4 installs standalone, but its PDF report needs the
    monolith until Phase 3c step 4 moves the action and template. A second copy was deliberately
    not added, "since that's how #49's duplicate stage rows happen".

62. `[RECONSTRUCTED]` <!-- transcript line 1048 --> **OPEN** — three models named
    `arkzayed.construction.progress` / `arkzayed.progress.*.wizard`. Renaming touches tables,
    auto-generated `model_*` xmlids and the monolith's references → Phase 7, with #29.

63. `[RECONSTRUCTED]` <!-- transcript line 1048 --> **OPEN** — the vendor supplier filter.
    `vendor_commitment.vendor_id` lost `domain=[('supplier_rank', '>', 0)]` because `supplier_rank`
    is declared by Odoo's `account`, which L4 does not depend on.

64. `[RECONSTRUCTED]` <!-- transcript line 1048 --> **OPEN, folded into #52** — #52's empty-group
    ACL rows extend to L4: `capex.scope` and `capex.cost.lines` are open to every user. The
    progress rows are correctly gated.

65. **NOT RECOVERED: #65.** Named by the Phase 8 report `[RECONSTRUCTED]` <!-- transcript line 1192 -->
    as part of "backlog #61 and #65" in Phase 3c's checklist, and the sign-client era referred to
    it as the monolith's settings tab. Its own text does not survive.

66. **NOT RECOVERED: #66.** No surviving report names it.

67. `[RECONSTRUCTED]` <!-- transcript line 1080 --> **OPEN-ACCEPTED** — the six `job.level` role
    booleans were assessed in Phase 7 and deliberately left as they are. They are the product's role
    vocabulary, not a client's; converting them to rows would force the engine's role→`crm.team`
    field mapping to become data. Recorded with the reasoning rather than skipped silently.

68. `[RECONSTRUCTED]` <!-- transcript line 1080 --> **FIXED IN PHASE 7, with a behaviour change** —
    "Residential Units Default Years" wrote one config key while both readers read another, so the
    setting never had any effect. Both sides now meet on one key and the migration prefers the value
    the user actually typed. **On a database where someone set that field, the number changes.**

69. `[RECONSTRUCTED]` <!-- transcript line 1080 --> **OPEN** — the cheque bridge reads a monolith
    group that resolves for nobody. Unlike Phase 5's two cases the group exists in no isky module,
    so placing it is a functional question.

70. `[RECONSTRUCTED]` <!-- transcript line 1192 --> **OPEN** —
    `broker.unit.parent_source_id` still references the developer's L0 hierarchy directly. Phase 8
    fixed the code's handling; the structural split needs Phase 9 (on hold), and removing it now
    would break the portal creation flow.

71. `[RECONSTRUCTED]` <!-- transcript line 1192 --> **OPEN** —
    `broker.unit.built_up_area` is declared `requied=True`, a typo, so the field is not required at
    all. Making it required is a data-entry change that wants a functional answer.

72. `[RECONSTRUCTED]` <!-- transcript line 1204 --> **OPEN** — a duplicated group from Phase 3c
    step 1: the step declared one group in L2 while the monolith kept its own copy, so members must
    be re-assigned in a database with both installed. Named again at
    <!-- transcript line 1214 --> as the reason step 2b refused to repeat the pattern ten times.

73. `[RECONSTRUCTED]` <!-- transcript line 1204 --> **FIXED IN PHASE 3c STEP 1** —
    `real.estate.unit.customer_id` carried `domain="[('is_customer','=',True)]"`, a field from a
    legacy contact module. Harmless for five phases because a Many2one domain resolves at search
    time; fatal the moment L0 shipped the form. Only the L0-only install could find it - the same
    shape as #63.

74. `[RECONSTRUCTED]` <!-- transcript line 1214 --> **FIXED** — a bug in `lint_s4_views.py` itself:
    it credited `sale.proposal`, `eoi.eoi` and `real.estate.sale.reservation` to `commission`,
    because it took the first module alphabetically declaring a `_name`. This repo deliberately
    re-declares `_name` in extending classes. The rule is now that a class whose own `_name` is in
    its `_inherit` is an extension, never the owner. The corrected figures: `sales_crm` 133 (not
    86), `commission` 38 (not 85).

75. `[RECONSTRUCTED]` <!-- transcript line 1214 --> **OPEN** — `arkzayed_collections_report` had
    been invisibly shipping a byte-identical duplicate of the monolith's collections views.

76. **NOT RECOVERED: #76.** Named in step 2a's docs line as part of "#74-#76"
    `[RECONSTRUCTED]` <!-- transcript line 1214 --> but its text does not survive.

77. **NOT RECOVERED: #77.** No surviving report names it.

78. **NOT RECOVERED: #78.** No surviving report names it.

79. `[RECONSTRUCTED]` <!-- transcript line 1491 --> **FIXED by the sign-client gate**, run
    `20261108-233645-302823` and the three gates beside it — any internal user could move a sale
    into a signed state, and `signed_client` is the first state the commission engine treats as
    eligible. The transition carried no permission: the "Sign by Client" button was the one header
    button of 23 with no `groups=`, and `write({'state': 'signed_client'})` bypassed even that.
    Measured: a salesperson with no manager or approval group set the state, the unit went to
    `sold`, and the commission record appeared.

    Two things the fix deliberately did not close at the time: the approvals-off skip, and the
    button `groups=`. **The first is FIXED 2026-11-10** - SG-D1..D4: signing moved into
    `NON_CONFIGURABLE_GATES` with one signer group (`director_manager_group`), enforced whether or
    not approvals are on; verified by `test_approvals_off_still_enforced` running as four real
    users. Note the same decision moved signing OFF the Sales Team Lead - the Director signs
    everything now. The button `groups=` still waits for Phase 9 (monolith form).

80. `[RECONSTRUCTED]` <!-- transcript line 1353 --> **OPEN** — commission is released with no check
    on collection, and the amount never follows the money. `action_confirm()` creates the journal
    entry and `action_create_payment()` the vendor payment with no read of collection or of
    `sale.commission.plan`; `commission_amount` is a plain stored Float written once at creation and
    nothing reverses it. Measured: collection taken from 30% back to 10% after confirmation, then
    paid, amount unchanged.

    Two further breaks in the same flow: the "Generate Commissions" button always raises
    `AttributeError` because `commission_achievement_ids` is declared nowhere, and the plan lookup
    is an `AccessError` for any non-manager on every explicit trigger. **Not touched by #79's fix** -
    #79 gates who may open the gate, not what happens after.

81. `[RECONSTRUCTED]` <!-- transcript line 1414 --> **OPEN** — a salesperson can return a collected
    cheque, and commission does not follow. `action_return`, `action_return_to_client` and the
    `under.collection.wizard` route all succeed on a cheque in `done` (Collected), with
    `cheque.manage` granting `base.group_user` full CRUD and no state guard in any of the three
    methods. Measured: collection fell 600,000 to 0.00 while the commission record stood at its full
    amount.

    Also carries the "Sign by Client" button's missing `groups=`, which cannot be added until the
    contract form leaves the monolith in Phase 9 (SC-D5 in the decisions log).

82. `[RECONSTRUCTED]` <!-- transcript line 1584 --> **OPEN, and the cause of the 2026-11-09 docs
    loss** — `.gitignore:6` is `*.md`, unanchored, so every markdown file in the repository is
    invisible to git at every depth. The `claude/` documents were never tracked and could not be
    recovered: `git ls-files claude/` returns 107 tracked files, none `.md`, and `.md` appears in 0
    of 18 commits across all 10 refs. 2,449 blobs scanned, zero document matches. Until the rule is
    narrowed, every rebuilt document here remains one `clean` away from deletion with no history.
    **FIXED 2026-11-10**: lines 7-8 added after line 6 - `!claude/` and `!claude/**/*.md`. Both
    checked: `claude/plan_status.md` and `claude/recovery/RECOVERY_MANIFEST.md` no longer ignored,
    a control `.md` at the repo root still ignored by line 6, and all 11 newly visible markdown
    files are under `claude/` with zero outside. Logs: `claude/logs/gitignore_before.txt` and
    `gitignore_after.txt`. The docs still need a commit to gain history - the rule change only
    makes them visible.
