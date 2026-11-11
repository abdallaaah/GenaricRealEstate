# Plan Status — GenaricRealEstate

Last updated: 2026-11-06. Source plans: `implementation_plan.md` and `implementation_plan_supplement.md`. Decisions: `decisions_log.md`.

## Phase status

* Phase 1 (Core hierarchy, L0): DONE. All 4 acceptance tests pass on a fresh DB.
* Phase 2 (Accounting bridge, break the cycle, L1): **COMPLETED** 2026-11-04.
   * Done: bridge split (account_move, account_payment), sales/commission-coupled fields moved out to L2/L3, manifest depends fixed.
   * Acceptance, all four criteria verified:
      1. Bridge installs standalone — PASS (`phase2_bridge_test`: bridge + L0 + `account` + `account_reports` all `installed`).
      2. Zero dependency cycles — PASS (`dep_graph.py`, 26 modules scanned).
      3. Install **with** the bridge — PASS (same DB as 1).
      4. Install **without** the bridge — PASS (`phase2_no_bridge_test`: L0 `installed`, bridge and `account` both `uninstalled`; exit 0, zero errors). Log: `claude/logs/phase2_no_bridge.log`.
   * Final bridge manifest: `['account', 'account_reports', 'isky_18_realestate_developer_unit_inventory']`.
   * Legacy repos at zero diff (verified `git status`).
   * S1 (cheques) was moved OUT of Phase 2 into Phase 2b — Phase 2 closed on its own scope only.
* Phase 2b (S1: cheque split): **COMPLETE**. Step 1 done 2026-11-04; step 2 was blocked at the
  time and was delivered in Phase 3 steps 3 and 4 (closed 2026-11-05), which is where the
  `@api.depends` rework it needed actually happened. The "BLOCKED (step 2)" note below is kept
  as the historical reasoning, not as current status.
   * DONE (step 1): cash-in-out statement feature moved out of the L1 accounting bridge into
     `arkzayed_18_gt_cheque_management`. The bridge's `env.ref` target xmlid did not exist at all
     (its two report files were never registered in that module's manifest, because the report's
     `binding_model_id` needed a `model_account_move` xmlid that module could not generate without
     an `account.move` file). Adding the model file unlocked registering the report. The L1 bridge
     now has zero functional cheque references.
   * BLOCKED (step 2): neither item named as "self-contained" actually is —
     the `cheque.manage` extension holds all 7 sales inverse Many2ones that 7 `sales_crm` One2many
     fields depend on, and the `account.payment` returned-cheque fields are named in a surviving
     `@api.depends` plus three surviving method bodies. Both unblock only via the 72-`@api.depends`
     rework that step 3 excludes. `sales_cheques` deliberately not created as an empty shell.
     Full reasoning in `decisions_log.md`.
* Phase 3 (Sales, L2): **CLOSED** 2026-11-06. All six steps closed; see the step sections
  below for gate tables and run IDs. Its three plan acceptance criteria are covered by
  `test_split_sum_not_100_rejected`, `test_toggle_off_creates_no_installment_lines` and
  `test_toggle_change_rejected_after_lines_exist` (Mode B, Mode A and all-three: 13 tests,
  0 failures in each).
* Phase 3c (UI migration, views and menus): **NOT STARTED**. Created 2026-11-06 out of Phase 3
  step 6. Backlog: 215 view records across 8 modules, 127 legacy menuitems. Run L0 first.
* Phase 4 (Commission, L3): **NOT STARTED**.
* Phase 5 (Construction, L4): **NOT STARTED**.
* Phase 6 (Settings, five sections): **NOT STARTED**.
* Phase 7 (Remove hardcoded client values): **NOT STARTED**. Backlog #33 and open question 12.3
  are already assigned to it.
* Phase 8 (Broker branch): **NOT STARTED**.
* Phase 9 (Extract core): **ON HOLD** — target branch to be confirmed.
   * Accepted for now: `sales_crm` still hard-depends on `arkzayed_18_gt_cheque_management`.
   * `sales_cheques` is DEFERRED to Phase 3, together with the guard pattern. Not created as an
     empty shell.
   * Test result: `claude/logs/phase2b_cheques_only.log` — L1 cheque module installs standalone,
     PASS (see Test results section).
* Phase 3 (Sales): **IN PROGRESS.** Applies S2 mode split, S4 view/menu rules, and the S6 guard
  pattern. Step order and progress:
   1. **DONE — acceptance PASS.** S6 guard pattern established + `group_manual_paid_installment`
      moved into `sales_crm`. Lint check added at `claude/scripts/lint_guard_pattern.py` (PASS).
      All four acceptance checks pass — see Test results. Log:
      `claude/logs/phase3_step1_modeb.log`.
      **Note for future runs: any install that pulls `sales_crm` needs 20+ minutes** (first
      attempt timed out at 15 min with zero errors, 60 of 177 modules in).
   2a. **DONE (code + lint); install verifying.** Sales-owned flags moved to `sales_crm`:
       `is_contract`, `is_collection`, `is_maintenance_collection` as `_inherit` on
       `account.move`; `is_down_payment` as `_inherit` on `account.payment` (it is declared on
       `account.payment`, not `account.move` — correction accepted 2026-11-04).
       `is_gis_quia` → **`is_revenue_split_entry`** (field stays in the L1 bridge; it marks a
       journal entry from the revenue-split posting). Old name: **zero** occurrences repo-wide.
       Greenfield, no migration — confirmed no data/demo/test file referenced the old name.
       Lint check 2 added (group reachability) and both checks PASS.
       Log: `claude/logs/phase3_step2a.log`.
       - The bridge keeps the down-payment ACCOUNT SELECTION and `_check_payable_receivable`
         (both accounting behaviour) and reads the two moved flags via `getattr`, so it remains
         installable standalone — Phase 2's acceptance is not regressed. The 4 view lines moved
         with their fields, since a view referencing a missing field is a hard ParseError
         whereas a Python read is only a runtime error.
       - **Lint check 2 immediately found 10 more instances of the step-1 bug class**: `sales_crm`
         referenced 7 groups living in the monolith it does not depend on, so `has_group()`
         returned False for every user and each gated feature was silently dead. All moved to
         the module owning the model they gate — `group_block_unit` → L0 `unit_inventory` (it
         gates blocking a *unit*, and L0 referenced it too, with the same bug);
         `group_show_discount_percentage`, `group_edit_discount_percentage`,
         `group_exception_reservation`, `group_confirm_reservation`, `group_finance_approval`,
         `group_finance_two_approval`, `group_manager_approval` → L2 `sales_crm`. 8 records
         removed from the monolith, every reference repointed, zero stale refs.
   2b. TODO — create `isky_18_realestate_developer_sales_accounting`; move the real accounting
       coupling into it (`payment_method_type`, `converted_amount`, `custom_exchange_rate`,
       `overseas_payment_type`, bridge-only payment states, Mode A logic in
       `sale_reservation.py`); drop `sales_crm`'s hard dep on the L1 accounting bridge.
   2b-a. **DONE** — created `isky_18_realestate_developer_sales_accounting`; moved the
       bridge-owned refs into it (~29 field refs: `is_overseas` 9, `payment_method_type` 6,
       `overseas_payment_type` 4, `is_revenue_split_entry` 3, `converted_amount` 2,
       `custom_exchange_rate` 2, `is_refund` 2, `installment_date` 1; plus 12 bridge-only
       payment-state refs) and remove `sales_crm`'s hard dependency on the L1 accounting bridge.
   2b-b. **Mode B gate — PASS** (all four criteria). Log:
       `claude/logs/phase3_step2b_modeb.log`. Evidence in Test results below.
       (The original "2b-pre" framing was circular — Mode B cannot be installed until 2b-a
       removes the dependency, so the removal came first and the gate ran immediately after,
       before any further 2b work.)
       - The gate earned its keep on the first run: it caught `action_register_penalty_payment`
         still living in the L1 bridge while a `sales_crm` view called it, which is a hard
         view-validation failure in Mode B. Phase 2 had left it in the bridge as "generic"; that
         was wrong — it is gated by a `sales_crm` field and rendered by a `sales_crm` view, and
         needs no bridge field, so it moved to `sales_crm`. A follow-up sweep of every button and
         field referenced by `sales_crm` views found no further bridge-only reference.
   3. **IN PROGRESS** — apply S6 to cheques; drop `sales_crm`'s hard dep on the L1 cheque module.
      Scope mapped: **13 fields** whose comodel is `cheque.manage` must move, plus ~9 compute
      splits, across 8 files. (Several `cheque`-named fields are NOT coupled — `cheque_number`,
      `cheque_due_date`, `cheque_starting_number*`, `cheque_is_serial`, `payment_methods` are
      plain Char/Selection and correctly stay in `sales_crm`.)
      - Acceptance items already satisfied with no work needed: the L1 cheque module depends on
        `['base', 'account', 'attachment_indexation', 'project']` only — no accounting bridge,
        no `sales_crm`.
      - Created `isky_18_realestate_developer_sales_cheques` (depends `sales_crm` + L1 cheque
        module, `auto_install`).
      - **Done (2 of 8 files)**: `eoi_payment.py`, `reservation_payment.py`. Both had the same
        shape; introduced a `_paid_total()` hook — base counts confirmed inbound payments, the
        bridge override adds incoming cheques — with `_compute_is_paid` redeclared per S6. Lint
        PASS across 4 bridge modules.
      - **Done (5 of 8 files)**: `eoi_payment`, `reservation_payment`, `payment_allocation`
        (`cheque_id` + `_allocation_parent` hook + constrains split), `installment_lines`
        (3 fields, 4 computes, 2 actions; `_allocation_is_collected` and
        `_has_cheque_allocation` hooks), `maintenance_installment_lines` (same shape).
        `cheque_manage.py` (1036 lines) relocated wholesale into the bridge.
      - **Remaining (3 files)**: `eoi`, `sale_reservation`, `sale_proposal`.
      - **STRUCTURAL FINDING — the requested checkpoint cannot be validated in isolation.**
        The checkpoint was specified as "after `payment_allocation.cheque_id` and
        `installment_lines`", but the cheque coupling is one **atomic** unit: moving
        `payment_allocation.cheque_id` breaks `cheque_manage.py`'s
        `One2many('payment.allocation', 'cheque_id')`, which forces that file into the bridge;
        and once it moves, all 7 remaining `One2many`s in `sales_crm` lose their inverse fields
        (`eoi_id`, `sale_proposal_id`, `sale_reservation_id`, ...) because `sales_crm` loads
        before `sales_cheques`. Confirmed empirically: the checkpoint install failed with
        `KeyError: 'cheque_id'` at field setup
        (`claude/logs/phase3_step3_ckpt_install.log`). This is the same interlock documented
        in Phase 2b step 2 — so steps 3 and 4 complete together, and the checkpoint install plus
        the paid-amount test run once the whole unit is in place.
      - Then: drop the cheque dep, re-run the Mode B gate
        (`claude/logs/phase3_step3_modeb.log`) and the three install combos.
   4. TODO — create `isky_18_realestate_developer_sales_cheques`; move `cheque.manage` and the
      returned-cheque fields into it.
   5. TODO — installments toggle + shared split model.
   6. TODO — S4 rules on every new view and menu.
* Phases 4 to 9: NOT STARTED.

### New modules introduced by Phase 3
- `isky_18_realestate_developer_sales_accounting` — optional bridge. Installed = Mode A,
  absent = Mode B. Holds only real accounting coupling.
- `isky_18_realestate_developer_sales_cheques` — optional bridge (from S1), created in step 4.

### OPEN ACTION — functional-team confirmation required before enabling approval gates

Blocks enabling the 10 previously-dead approval features in **any environment holding real data**.
Decision: `decisions_log.md` section 11; plan: supplement S7. Implementation is scheduled after
Phase 3 step 2b.

Step 2a made these gates live again (they had been silently dead — `has_group()` returned False
for every user because the groups sat in a module `sales_crm` does not depend on). Re-activating a
gate that no user belongs to would **lock that action for everyone**, so each group below needs a
confirmed answer before the gate is switched on.

| Group (now in) | Gates | Has real users? |
|---|---|---|
| `group_finance_approval` (sales_crm) | contract finance approval | **TBC** |
| `group_finance_two_approval` (sales_crm) | contract second finance approval | **TBC** |
| `group_manager_approval` (sales_crm) | contract manager approval | **TBC** |
| `group_confirm_reservation` (sales_crm) | confirming a reservation | **TBC** |
| `group_exception_reservation` (sales_crm) | reservation exceptions | **TBC** |
| `group_show_discount_percentage` (sales_crm) | seeing discount % | **TBC** |
| `group_edit_discount_percentage` (sales_crm) | editing discount % | **TBC** |
| `group_manual_paid_installment` (sales_crm) | ticking an installment Paid by hand | **TBC** |
| `group_block_unit` (unit_inventory, L0) | blocking a unit | **TBC** |
| `group_operation_manager_approval` (still in monolith) | operation manager approval | **TBC** |

Record the functional team's answers in this table when received.

### Known conditions carried forward

**Bridge-only payment states remain as literals in filter methods.** `to_check`,
`cfo_approved` and `deputy_cfo_approved` are contributed only by the L1 accounting bridge, but
four filter sites in `sales_crm` still name them (`sale_reservation.py:164,1150,1513`,
`sale_proposal.py:2914`). They are **inert** in Mode B: Odoo 18 core `account.payment.state`
already supplies `in_process` and `paid`, so those filters still select correctly and the
bridge-only literals simply never match. Deliberately not moved — splitting those filter methods
would add risk for no behavioural change. Pinned by a test:
`isky_18_realestate_developer_sales_crm/tests/test_mode_b.py::TestModeB::test_no_mode_a_path_when_bridge_absent`
asserts the bridge-only states are absent from the selection and that
`_create_collection_journal_entry` does not exist on `account.payment` when the bridge is absent.
The test is mode-aware, so it also asserts the opposite in Mode A.

**`sales_crm` has no access rules for its own models** — `decisions_log.md` 12.2. No
`ir.model.access.csv`; `installment.lines` and `eoi.eoi` have zero ACL rows, so non-superusers
cannot reach them at all. Deferred to the S7 security work, not fixed in Phase 3 step 2b.

**Optional before release (not blocking):** re-run the Mode B gate with `--without-demo=all` for
a literal zero `account.move` count. Current evidence is causal (delta = 0 across both Paid
actions) rather than an absolute count, because Odoo's `account` demo data was loaded.

### Guard pattern (S6) and its lint check
super()-chained compute extension: base compute in `sales_crm` with `@api.depends` on
always-present paths only (that base behaviour *is* Mode B); each bridge redeclares the method
with `@api.depends` including its own paths and calls `super()`. Enforced by
`claude/scripts/lint_guard_pattern.py` — any compute overridden in a bridge without
`@api.depends` fails the check. Run it after any bridge change.

### Phase 3 acceptance criteria
1. `sales_crm` no longer hard-depends on the L1 cheque module.
2. One guard pattern is established and applied to S2 Mode B first, then to cheques.
3. Then `sales_cheques` is created and the `cheque.manage` and `account.payment`
   returned-cheque fields move into it.

Supporting detail for criterion 2: the guard pattern covers the 72 `@api.depends` in `sales_crm`
that reference payment / `account.move` / cheque paths. Several sit on money fields — `eoi_amount`
(`sale_proposal.py:759-761`), reservation amounts (`sale_reservation.py:349-350,566`), and the
installment paid flag (`installment_lines.py:262,291`). One pattern only; do not build two
separate refactors.

Supporting detail for criterion 3 (why it is gated on 1 and 2): the `cheque.manage` extension holds
all 7 sales inverse Many2ones that 7 `sales_crm` One2many fields require, and the
`account.payment` returned-cheque fields are named in a surviving `@api.depends` plus three
surviving method bodies. Both only become movable once the guard pattern exists.

   * S2 and S4 text: present in the supplement, usable. No blocker.
* Separate verification gate (not a Phase 2 criterion, per scope rule 3): full legacy-stack install. Run 12 hit the 10-minute timeout rather than erroring — the surviving `phase2_full_stack_test` DB shows L0 `installed` and the rest `to install`, and earlier runs failed *with errors* at ~9 min, so the fixes had cleared the previous blocker and the run simply needed a longer budget. Note this gate is now expected to fail regardless: the legacy fixes it depended on were reverted under Option A (backlog #23–#27), and `arkzayed_cost_distribution` no longer installs (backlog #28).

## Test results

| Test | Config | Result | Log |
|---|---|---|---|
| Phase 2 — bridge installs standalone | bridge + L0 + `account` + `account_reports` | PASS | `phase2_bridge_test` DB |
| Phase 2 — install **without** bridge | L0 only; bridge and `account` uninstalled | PASS (exit 0) | `claude/logs/phase2_no_bridge.log` |
| Phase 2 — zero dependency cycles | 26 local modules | PASS | `dep_graph.py` |
| Phase 2b — L1 cheque module installs **without** `sales_crm` | `arkzayed_18_gt_cheque_management` only; `sales_crm`, L0, bridge all uninstalled | PASS (exit 0, 0 errors, 0 registry failures) | `claude/logs/phase2b_cheques_only.log` |
| Phase 3 step 1 — guard-pattern lint | 35 files, bridge modules present | PASS | `claude/scripts/lint_guard_pattern.py` |
| Phase 3 step 1 — `sales_crm` installs **without the monolith**, Paid button live | `sales_crm` installed; `arkzayed_18_realestate_development` uninstalled | PASS (exit 0, 0 registry failures) | `claude/logs/phase3_step1_modeb.log` |
| Phase 3 step 2a — flags moved, `is_gis_quia` renamed | `sales_crm` + bridge + L0 | PASS (exit 0) | `claude/logs/phase3_step2a.log` |
| Phase 3 step 2b-b — **Mode B gate** | `sales_crm` + L0 + core `account`; bridge AND `sales_accounting` both uninstalled | **PASS** (all 4 criteria) | `claude/logs/phase3_step2b_modeb.log` |

Mode B gate (2b-b) evidence, per criterion:
1. **Install clean** — exit 0, 0 registry failures, no ParseError/KeyError at field setup.
2. **Correct module set** — `isky_18_realestate_developer_sales_crm` = `installed`, core `account` = `installed`; `isky_18_realestate_developer_accounting` = `uninstalled` AND `isky_18_realestate_developer_sales_accounting` = `uninstalled` (so no Mode A code is even loaded).
3. **Zero journal entries from the sales flow.** Measured by causation rather than a row count: a shell run created an EOI and an installment line, invoked both Paid actions, and the `account.move` **delta was 0**. The DB does hold 26 `account.move` rows, but all are Odoo `account` demo fixtures (24 carry an `ir_model_data` xmlid owned by `account`; the other 2 are plain `entry` records in the Bank journal from demo loading). None is linked to a `sale_proposal`, reservation or penalty, none carries `is_contract`/`is_collection`/`is_maintenance_collection`, and the DB contains **no sales records at all** (`sale_proposal` 0, reservations 0, EOI 0, installment lines 0), so no sales flow could have produced one. A `--without-demo=all` run would make the literal count zero if an unambiguous number is preferred.
4. **Paid works on installment line AND EOI**, exercised functionally, not just structurally:
   - `eoi.action_mark_paid()` → `is_paid=True`, `paid_by_id` set, `paid_date` set
   - `installment.lines.action_mark_fully_paid()` → `paid=True`, `paid_by_id` set, `paid_date` set
   - all 6 Paid fields owned by `isky_18_realestate_developer_sales_crm`
   - Caveat: the smoke test ran in `odoo-bin shell` as superuser, so `_check_manual_paid_group`'s
     gate was bypassed (`env.su`). The mechanics and the zero-journal-entry result are verified;
     that the gate *blocks a non-member* is not yet covered by a test.

Phase 3 step 1 acceptance detail, verified in the DB:
- `isky_18_realestate_developer_sales_crm` = `installed`; `arkzayed_18_realestate_development` = `uninstalled`.
- `isky_18_realestate_developer_sales_crm.group_manual_paid_installment` exists (`res.groups` id=68), owned by sales_crm.
- `admin` holds that group → **the Paid button is live**, which it was not before (the group lived in the monolith, which `sales_crm` does not depend on, so `has_group()` returned False for every user and S2 Mode B's manual tracking could not work at all).
- Zero stale `arkzayed_18_realestate_development.group_manual_paid_installment` rows remain.

Phase 2b step-1 fix verified in the DB, end to end:
- `arkzayed_18_gt_cheque_management.account_cash_in_out_report` → now exists (`ir.actions.report` id=381). It did not exist before this fix.
- `arkzayed_18_gt_cheque_management.model_account_move` → now generated. This was the gating xmlid: without an `account.move` file in that module it could not exist, which is why the report files could never be registered.
- Report action live: `report_name=...account_cash_in_out_template`, `model=account.move`, `report_type=qweb-pdf`.
- Moved button view loaded: `arkzayed_18_gt_cheque_management.view_account_move_cash_in_out`.

## Findings during Phase 2 verification

* Full-stack install surfaced a long tail of pre-existing bugs, not caused by the refactor: dangling imports, unqualified XML refs, a table name longer than the Postgres limit, a translated-default race, duplicate dead code, and a few L2 to L3 layering issues.
* About a dozen fixed. All logged in `decisions_log.md`. Several are marked NEEDS REVIEW because they touch legacy-owned files.
* Now itemised in `bug_backlog.md`: 27 entries — 15 blocked installation and were fixed in new-branch modules only, 7 are parked as non-blocking, and 5 (#23–#27) touch legacy-owned files and need reverting plus re-application in the new branch per scope rule 1.
* Legacy diff audit: 31 modified files + 1 deletion + 1 addition, **all** from this session and cleanly attributable (verified line by line). The dirty-looking git status at session start was a `staging` vs `developer_18` artifact — the branch was switched early on, so there is no third-party uncommitted legacy work mixed in. Reverting was therefore precise.
* RESOLVED (Option A, 2026-11-04): all 32 legacy changes reverted. **Legacy repos are at zero diff**, verified with `git status`. The complete diff is preserved at `claude/legacy_fixes_to_reapply.patch` (793 lines, 32 files) for re-application in the new branch. `dep_graph.py` still reports zero cycles after the revert — the Phase 2 cycle break came from the bridge dropping its own upward edges, not from any legacy edit.
* Accepted consequence (backlog #28): `arkzayed_cost_distribution` no longer installs — its menuitem targets an action Phase 2 removed from the bridge, and its wizard uses the removed `account.move.line` cost-allocation fields. Scope is exactly that one legacy module, two files. **No `isky_*` module is affected.**

## Scope rules going forward

1. The legacy repos (arkzayed, marketstandards) must stay untouched. Verify this before closing Phase 2. Any NEEDS REVIEW fix that touches legacy files must be re-applied on developer_18 instead.
2. Pre-existing bugs that do not block installing the new layers go to a backlog (`claude/bug_backlog.md`), not into Phase 2.
3. Phase 2 acceptance is: bridge installs standalone, no cycles, install with and without the bridge. Full legacy-stack install is a separate verification gate, run in the background with a log file, not as a foreground command.
4. Cheques (S1) and payment allocations (S3) start after Phase 2 acceptance passes.

## Next actions

1. DONE — legacy repos confirmed at zero diff.
2. DONE — Phase 2 closed; all four acceptance criteria pass.
3. DONE — S1 moved out of Phase 2 into Phase 2b; S5 updated in the supplement.
4. BLOCKED — supply the full S1–S5 text in `implementation_plan_supplement.md`. S1 is needed for Phase 2b, S2 for Phase 3. The file on disk is still truncated (31 lines, starts mid-sentence at S4).
5. THEN — start Phase 3 (Sales), applying the S2 mode split and the S4 view/menu rules.

## Test invocation (recorded 2026-11-05)

Phase installs and shell tests need a config that earlier logs in `claude/logs/` were produced
with but which is **not** in the repo (and must not be: it carries the database password).
Recreate it before running any gate:

- copy `db_host` / `db_port` / `db_user` / `db_password` from any working server config, e.g.
  `/opt/odoo/odoo18/conf/Ark.conf`
- set `addons_path` to all four paths, in this order:
  `/opt/odoo/odoo18/odoo/enterprise,/opt/odoo/odoo18/odoo/addons,/opt/odoo/odoo18/odoo/odoo/addons,/opt/odoo/odoo18/odoo/custom/GenaricRealEstate`
- do **not** set `logfile`, so the run's output lands in the gate log

Two traps cost time on 2026-11-05 and are worth remembering:

1. `/opt/odoo/odoo18/conf/Ark.conf` omits `/opt/odoo/odoo18/odoo/addons` (the community addons
   directory, 626 modules). Copying its `addons_path` verbatim fails with
   `ModuleNotFoundError: No module named 'odoo.addons.web'`, which then surfaces as a
   misleading `ParseError` on core `base` data. All four paths are required.
2. PostgreSQL asks the shell user `isky` for a password, so bare `dropdb` / `psql` **hang on a
   prompt** rather than failing. Always pass `-h localhost -U odoo18` with `PGPASSWORD`.

A multi-line `cd … && nohup …` passed to the Bash tool can be collapsed into a single line,
which turns the whole thing into arguments to `cd` and silently runs nothing - the stale log
from a previous run then looks like a fresh failure. Gates are launched through
`/tmp/claude-1000/run_odoo.sh` and `/tmp/claude-1000/run_shell.sh` (single-argument wrappers)
to avoid this.

## Phase 3 step 3 checkpoint — PASS (2026-11-05)

The structural finding recorded above is confirmed and now resolved: the cheque coupling is one
atomic unit, so steps 3 and 4 were completed together before the checkpoint could install.

| Gate | Result | Log |
|---|---|---|
| `lint_guard_pattern.py` check 1 (compute `@api.depends`) | PASS — 52 files, 4 bridge modules | — |
| `lint_guard_pattern.py` check 2 (`group_*` reachable from sales_crm) | PASS | — |
| `dep_graph.py` | PASS — 28 modules, no cycles | — |
| Install: cheque module + sales_crm + sales_cheques | PASS (EXIT=0) | `claude/logs/phase3_step3_ckpt_install.log` |
| Paid-amount test (cheque pays one installment line) | PASS — 11/11 | `claude/logs/phase3_step3_paid_amount.log` |

Install verified in the DB, not just by exit code: `arkzayed_18_gt_cheque_management`,
`isky_18_realestate_developer_sales_crm` and `isky_18_realestate_developer_sales_cheques` all
`installed`, both accounting bridges `uninstalled` (so this is Mode B **with** cheques), and
`payment_allocation.cheque_id` present as a column contributed by the bridge.

The paid-amount test asserts a negative control before the positive case — while the cheque is
still `draft`, `paid_amount` is 0.0 and `paid` is False; only after `state = 'done'` do the
expected values appear. That makes it a causation test, not a coincidence. Asserted:
`total_amount` 10000, `paid_amount` 10000, `remaining_amount` 0.0, `paid` True,
`payment_method_used` 'cheque', `cheque_state` 'done', plus the three shared hooks
(`_is_collected()` True, `_fund_kind()` 'cheque', `_allocation_parent()` is the cheque).
Rolled back; nothing committed.

### What moved in steps 3 and 4

`sales_crm` no longer declares `arkzayed_18_gt_cheque_management` in `depends`. Eight files
split, each field removed and re-declared in the bridge in the same pass:

- `eoi_payment.py`, `reservation_payment.py` — `cheque_ids`, `create_cheque()`, `_paid_total()`
- `payment_allocation.py` — `cheque_id`; new shared predicates `_is_collected()`,
  `_fund_kind()`, `_allocation_parent()`
- `installment_lines.py`, `maintenance_installment_lines.py` — `cheque_ids`, `cheque_state`,
  `allocated_cheque_ids`, 4 computes, the cheque actions
- `cheque_manage.py` (1036 lines) — relocated wholesale
- `eoi.py` — `cheque_manage_ids`, `cheque_count`, 4 methods, 2 new hooks
- `sale_reservation.py` — `cheque_manage_ids` + the 3 bank-cheque input fields, 3 S6 computes,
  8 hooks, `create_cheque_payment()`, `action_show_cheques()`
- `sale_proposal.py` — the whole cheque-generation subsystem (`action_create_cheques`,
  `_generate_cheques`, `action_view_cheques`, the combined-cheque wizard button) plus the
  `cheque_is_serial` / `bank_id*` / `cheque_starting_number*` configuration block
- `account_payment.py` (step 4) — `cheque_id`, `returned_cheque_ids`, `returned_source_type`,
  the onchange and the constrains; `is_returned_cheque` stays in `sales_crm` (a plain flag with
  no cheque coupling)

One consolidation beyond a straight move: five copies of
`alloc.cheque_id.state == 'done' or alloc.payment_id.state == 'paid'` in `sale_proposal.py`,
plus the two per-model hooks on installment and maintenance lines, now all route through
`payment.allocation._is_collected()`. CLAUDE.md requires one engine, and the alternative was
writing the same predicate a third and fourth time.

A gap found while splitting: `maintenance_installment_lines`' cheque actions had been removed
from `sales_crm` in an earlier pass with **no bridge counterpart created**, so
`action_create_cheque()` / `action_view_cheque()` existed nowhere. Now created.

New backlog items 30–33 (substring state test, dead migration helper, two wizards still in the
monolith, client-prefixed config parameter).

## Phase 3 steps 3 + 4 — closure gates (2026-11-05)

Every log below carries `### RUN_ID` / `### START` / `### EXIT` stamped by the wrapper, so each
log proves its own provenance. The two earliest gates were re-run because they predated the
stamping wrapper and their provenance could not be attested.

| # | Gate | Run ID | Start | Exit | Result |
|---|---|---|---|---|---|
| 1 | Mode B re-gate — `phase3_step3_modeb.log` | 20261105-143841-3196480 | 14:38:41 EET | 0 | PASS — 2 post-tests ran |
| 2a | Combo: sales_crm, no cheque module — `phase3_step3_combo_crm_only.log` | 20261105-142612-2579254 | 14:26:12 EET | 0 | PASS |
| 2b | Combo: cheque module, no sales_crm — `phase3_step3_combo_cheque_only.log` | 20261105-143120-2825055 | 14:31:20 EET | 0 | PASS |
| 2c | Combo: all three — `phase3_step3_combo_all_three.log` | 20261105-143348-2946508 | 14:33:48 EET | 0 | PASS |
| 3 | Collected-predicate equivalence — `phase3_collected_equiv.log` | 20261105-144348-3448844 | 14:43:48 EET | 0 | PASS — 25 fixtures, 0 mismatches |
| 4 | Maintenance cheque actions — `phase3_maintenance_cheque_actions.log` | 20261105-144826-3701331 | 14:48:26 EET | 0 | PASS — 33 checks, 0 failures, one path blocked (see below) |
| — | Checkpoint install — `phase3_step3_ckpt_install.log` | 20261105-144920-3754117 | 14:49:20 EET | 0 | PASS |
| — | Paid-amount test — `phase3_step3_paid_amount.log` | 20261105-145425-3999237 | 14:54:25 EET | 0 | PASS — 11/11 |

### Gate 1 — Mode B re-gate

`--test-enable` alone was useless here: it runs every installed core module's suite, and `crm`,
`crm_sms`, `phone_validation` and `base` have pre-existing failures that swamp the signal
(observed: crm 5/111, crm_sms 1/1, phone_validation 12/16, base 1 error of 1047 — cause not
established, recorded as an observation only). Scoped with
`--test-tags /isky_18_realestate_developer_sales_crm`.

A passing test run at `--log-level=warn` prints **nothing**, so an empty log is not evidence
that tests ran. Re-run at `--log-level=test` for positive confirmation:

```
Starting TestModeB.test_manual_paid_creates_no_journal_entry ...
Starting TestModeB.test_no_mode_a_path_when_bridge_absent ...
2 post-tests in 0.25s, 35 queries
```

### Gate 2 — the three combinations, verified in the database

Exit code 0 is not proof the intended combination was installed, so module states were read
back from each database:

| DB | sales_crm | cheque module | sales_cheques | `payment_allocation.cheque_id` column |
|---|---|---|---|---|
| `phase3_combo_crm_only` | installed | uninstalled | uninstalled | **absent** |
| `phase3_combo_cheque_only` | uninstalled | installed | uninstalled | absent |
| `phase3_combo_all_three` | installed | installed | installed | present |

The absent column in the first row is the real proof of supplement S1: `sales_crm` carries no
cheque schema at all when the cheque module is not installed.

### Gate 3 — collected-predicate equivalence

Three predicates compared on identical fixtures: `OLD_A` (the git-HEAD original, verbatim,
including `VALID_PAYMENT_STATES = ('paid')` — a string, so a substring test), `OLD_B` (the
`sale_proposal` variant, which already used `==` and checked the cheque first), and `NEW`
(`payment.allocation._is_collected()`).

- Layer 1, exhaustive: all 19 values of the two real selection domains, asserting
  `value in 'paid'` ≡ `value == 'paid'` and the same for `'done'`, plus that no state is a
  proper substring of either target. 0 mismatches — the substring rewrite is behaviour-
  preserving over the whole domain, not just the values a fixture happened to hit.
- Layer 2, real records: one allocation per cheque state, all 14 states.
- Layer 3, real records: all 5 `account.payment` states (forced at SQL level, rolled back),
  each both alone and combined with a collected cheque, plus the neither-set case.

25 fixtures, all three predicates agree everywhere.

### Gate 4 — maintenance cheque actions

33 checks, 0 failures. `action_view_cheque` is fully covered (no-cheque → ValidationError;
one cheque → `form` + `res_id`; two cheques → `list,form` + `res_id` False; domain, target),
as are the bridge computes the actions feed (`allocated_cheque_ids`,
`_has_cheque_allocation()`, `payment_method_used`, and `paid_amount`/`remaining_amount`/`paid`
before and after the cheque is collected).

All six `action_create_cheque` guard rails pass: journal unconfigured, journal pointing at a
missing record, no date, no linked proposal, and an already fully-paid line.

**Its create step is NOT covered, and cannot be on a fresh database** — backlog #34, a
pre-existing release blocker, not a Phase 3 regression. `cheque.manage.credit_account` is
`required=True`/`NOT NULL` and no cheque-creating call site anywhere supplies it, including
the main production path `sale_proposal._generate_cheques()`. The two configurations are
mutually exclusive (measured in `claude/logs/phase3_probe_credit.log`), so no test-side
workaround exists. The test **pins** the defect: if the create step ever succeeds it reports
that the happy-path assertions should be re-enabled. Needs a decision — see backlog #34 for
the three candidate fixes.

## S8 — Cheque settings and the #34 fix (2026-11-05). Phase 3 steps 3 and 4: CLOSED

Branch: `developer_18`. No branch named `new` exists; "new" was read as the new codebase (the
`isky_*` modules) as against the legacy repos, consistent with `FIXED-IN-NEW` and earlier usage.
Confirmed with the user before starting. `custom/arkzayed` and `custom/marketstandards` remain at
zero diff; no file in any `arkzayed_*` module was touched by S8.

### Where the settings live, and why (S8 asked for this to be recorded)

**Both settings are in `isky_18_realestate_developer_sales_cheques`.**

S8's rule was "`sales_cheques` if the setting is sales-facing, otherwise the L1 cheque module".
`cheque_incoming_credit_account_id` is **not** sales-facing - it is core cheque accounting needed
by every cheque creation - so by that rule it belongs at L1. But L1 is
`arkzayed_18_gt_cheque_management`, which CLAUDE.md puts off limits, so the rule cannot be
followed literally. `sales_cheques` was chosen as the only home that required no legacy edit, and
the fix was implemented as a **single choke point** instead of per call site:

- `cheque.manage.create()` in this module already existed as an override, and **all 11**
  `cheque.manage` create call sites pass through it - the 7 in `sales_cheques` plus the 4 wizards
  in `arkzayed_18_realestate_development`. One `_resolve_incoming_credit_account()` call there
  covers every one of them.
- Patching the 7 isky call sites individually would have been more code, would still have missed
  the 4 legacy ones, and would have left the next new call site unprotected.
- Company-level fields rather than `ir.config_parameter`: a multi-company database needs a
  different credit account per company, which a global parameter cannot express.
- Outgoing cheques are untouched - their credit account still comes from the legacy
  `credit_out_account` parameter. S8 limits behaviour changes to the incoming path.

Verified that the settings ship only with the bridge: the `res_company` columns exist in
`phase3_combo_all_three` and in **neither** `phase3_combo_crm_only` nor
`phase3_combo_cheque_only`.

### Files changed

New, all in `isky_18_realestate_developer_sales_cheques`:

| File | Purpose |
|---|---|
| `models/res_company.py` | `cheque_incoming_credit_account_id`, `cheques_enabled` (default True) |
| `models/res_config_settings.py` | related fields so both are editable from Settings |
| `views/res_config_settings_views.xml` | "Financials" and "Sales Setup" blocks |
| `tests/__init__.py`, `tests/test_s8_cheque_settings.py` | the 9 acceptance tests |

Modified:

| File | Change |
|---|---|
| `models/cheque_manage.py` | `_resolve_incoming_credit_account()`, `default_get()` override, one line at the top of `create()` |
| `models/sale_proposal.py` | `_check_cheque_generation_enabled()`, called from `action_create_cheques`, `_generate_cheques`, `action_open_combined_cheque_wizard` |
| `models/__init__.py` | registers `res_company` before `res_config_settings` (the related fields walk `company_id.<field>`) |
| `__manifest__.py` | `data` now lists the settings view |

`models/__init__.py` ordering matters: `res_config_settings`' related fields resolve
`company_id.cheque_incoming_credit_account_id` at field setup, so the company fields must be
registered first.

### Gate results

| Gate | Log | Run ID | Start | Exit | Result |
|---|---|---|---|---|---|
| S8 acceptance suite | `phase3_s8_cheque_settings.log` | 20261105-155857-2975190 | 15:58:57 EET | 0 | PASS — 9 post-tests, 0 failures |
| Mode B re-gate | `phase3_step3_modeb.log` | 20261105-160545-3283107 | 16:05:45 EET | 0 | PASS — 2 post-tests, 0 failures |
| Combo: sales_crm only | `phase3_step3_combo_crm_only.log` | 20261105-153918-2085168 | 15:39:18 EET | 0 | PASS |
| Combo: cheque module only | `phase3_step3_combo_cheque_only.log` | 20261105-154441-2329406 | 15:44:41 EET | 0 | PASS |
| Combo: all three | `phase3_step3_combo_all_three.log` | 20261105-154721-2449995 | 15:47:21 EET | 0 | PASS |
| Checkpoint install | `phase3_step3_ckpt_install.log` | 20261105-155251-2698685 | 15:52:51 EET | 0 | PASS |
| Paid-amount | `phase3_step3_paid_amount.log` | 20261105-155820-2946938 | 15:58:20 EET | 0 | PASS — 11/11 |
| Collected equivalence | `phase3_collected_equiv.log` | 20261105-155826-2951378 | 15:58:26 EET | 0 | PASS — 25 fixtures, 0 mismatches |
| Maintenance cheque actions | `phase3_maintenance_cheque_actions.log` | 20261105-155833-2956724 | 15:58:33 EET | 0 | PASS — **54 checks** (was 33), 0 failures |

The whole Phase 3 gate set was re-run after S8, not just the new suite, because the bridge changed.

The Mode B row is a separate, later run: the gate set runs at `--log-level=warn`, where a passing
Odoo test suite prints **nothing**, so that log could not show its tests had executed. Re-run at
`--log-level=test` purely to get the two test names and the `2 post-tests` line on the record.

### Test names (S8 item 3, plus what the brief did not ask for)

The four S8 named it: `test_cheque_create_with_setting`, `test_cheque_create_without_setting`,
`test_cheque_generation_toggle_off`, `test_default_get_keeps_caller_value`.

Five added:

- `test_cheque_create_without_setting_raises_before_insert` — proves the refusal happens before
  any INSERT, so the NOT NULL was never reached rather than merely not surfaced
- `test_manual_cheque_unaffected_by_toggle` — S8 says manual use must be unaffected; nothing
  else asserted it
- `test_default_get_falls_back_to_setting` — the other half of the `default_get` contract
- `test_cheques_enabled_defaults_on` — "default = on" was a stated requirement with no test;
  also checks a **pre-existing** company row, since Odoo backfills a new stored column
- `test_all_sales_cheque_paths_covered_by_choke_point` — drives
  `maintenance.action_create_cheque()` end to end, the path that was impossible to cover before

### The uncovered-path note is removed

`phase3_maintenance_cheque_actions` grew from 33 to 54 checks. Its pinned-defect block is gone,
replaced by the full happy path (cheque created, amount, state, source_type, proposal, payer,
journal, date, **credit_account from the setting**, the allocation, `payment_method_used`, and
paid/remaining before and after collection) plus a guard asserting that a cleared setting
produces a `UserError` naming the setting and not a database error.

### Still open

- **Open question 12.3** — the residual L1 gap: the choke point ships in `sales_cheques`, so a
  database with the legacy cheque module but without it has no protection, and the monolith's
  four cheque wizards can still reach the NOT NULL. Needs a scope decision: accept it, create a
  new L1-level `isky` cheque-config module (which would also house backlog #29's rename), or
  allow a one-line edit to the legacy `default_get`.
- **Commit hash for backlog #34** — S8's close-out asks for one, but commits are held until the
  user asks (decision of 2026-11-04). The hash line in `bug_backlog.md` is marked pending.
- **Outgoing cheques**: checked, not a gap. All 11 create call sites pass
  `cheq_type: 'incoming'` - no code path creates an outgoing cheque. Outgoing creation happens
  only through the cheque form, where `credit_account` is `required=True` and the form itself
  forces a value, so the NOT NULL cannot be reached there either. The setting is named
  "incoming" accordingly and `_resolve_incoming_credit_account()` returns early for outgoing,
  leaving that path's legacy behaviour untouched as S8 requires.
- Backlog #33 (renaming the `arkzayed_*`-prefixed config parameters) stays in Phase 7. The new
  settings use generic company fields, so they need no rename.

## Decision (2026-11-05): open question 12.3 accepted until Phase 7

- The L1 cheque gap from S8 is accepted until Phase 7. Backlog #35 tracks it (OPEN-ACCEPTED).
- The cheque settings stay in the Financials section. Today they show only when `sales_cheques` is
  installed.
- Phase 3 steps 3 and 4 are closed. Step 5 (installments toggle and shared split model) is the next
  step, and it starts only on the user's go-ahead.
- Commit for backlog #34 is still held (decision of 2026-11-04). The hash line stays pending until the
  user asks for a commit.

## Phase 3 step 5 — installments toggle and shared split model (2026-11-05)

Branch `developer_18` (no `new` branch created; confirmed with the user). No legacy file touched;
`custom/arkzayed` and `custom/marketstandards` still at zero diff.

### Step 0 pre-check findings

| # | Finding | Consequence for step 5 |
|---|---|---|
| 1 | **No installments toggle exists.** Zero hits for `installments_enabled`/`installments_mode`/`installments_effective` or any equivalent. The only near-match is a local variable `has_installment` in `account_payment.py:458`. | Built from scratch. |
| 2 | **A shared split model already exists**: `customer.ownership` (`customer_ownership.py:5`), already used by both sides - `sale_reservation.py:47-48` and `sale_proposal.py:78-79`. | "Reservation and contract both use it" was already true. **No second implementation created.** |
| 3 | **It had no sum-to-100 check of any kind** - no `_sql_constraints`, no `@api.constrains`. | This was the real missing piece. Backlog #36. |
| 4 | `revenue.share2` is **not** a duplicate - it is rental revenue-share invoicing. | Left alone. |
| 5 | **A real duplicate**: `action_copy_customer_ownership_ids`, 34 identical lines in `sale_reservation.py:2102` and `sale_proposal.py:3693`, differing only in the FK key and one word. | Consolidated into `realestate.split.parent.mixin`. Backlog #37. |
| 6 | **`installment.lines` has no `project_id`**, and **`sale.proposal` has no `project_id`** either - only the reservation and the unit do. | The lock rule needs a two-route search. Backlog #39. |
| 7 | **Four creation points, no direct `create()`** outside tests: `_prepare_reservation_installment_lines`, `_prepare_reservation_maintenance_lines`, `_prepare_installment_lines`, `_prepare_lines`. | All four gated, plus their four action entry points: 8 gates. |
| 8 | **`commission.commission` is declared in L2**, not L3. | Out of step 5 scope. Backlog #38. |

### The view half was deferred, by decision

The only `realestate.project` form view, and the only reservation/contract forms carrying the
installment tabs, live in `arkzayed_18_realestate_development`. L0 ships no project form and
`sales_crm` had no settings view. Inheriting a legacy view from L2 would reintroduce the
dependency cycle Phase 2 removed. **Decision (user-confirmed): model layer in step 5, the
project-form field and the tab hiding in step 6 (S4 views/menus)**, which already owns building
non-legacy forms. The Sales Setup settings block *was* delivered now, as a fresh view file in
`sales_crm` inheriting `base.res_config_settings_view_form`.

Still open from the brief, for step 6: the `installments_mode` field on the project form, and
hiding the installment tabs/buttons when the flag is off. Model enforcement is complete and
independent of both.

### Files changed

New, all in `isky_18_realestate_developer_sales_crm`:

| File | Lines | Purpose |
|---|---|---|
| `models/config/res_company.py` | 47 | `installments_enabled` + the company lock |
| `models/config/realestate_project_sales_ext.py` | 78 | `installments_mode`, `installments_effective`, `_has_installment_lines()`, the project lock |
| `models/core/installments_gate_mixin.py` | 50 | `_installments_allowed()`, the per-model project resolver, the off-notification |
| `models/core/split_line_mixin.py` | 152 | the split engine (sum-to-100) and the deal-side copy action |
| `models/core/commission_hooks_mixin.py` | 27 | no-op bases for the two L3 methods L2 calls (regression fix) |
| `views/res_config_settings_views.xml` | 42 | the Sales Setup block |
| `tests/test_step5_installments_split.py` | 298 | the step 5 suite |

Modified: `__manifest__.py`, `models/config/__init__.py`, `models/config/res_config_settings.py`,
`models/core/__init__.py`, `models/core/customer_ownership.py`, `models/core/sale_reservation.py`,
`models/core/sale_proposal.py`, `models/core/eoi.py`, `tests/__init__.py`.

### Gate results

| Gate | Log | Run ID | Start | Exit | Result |
|---|---|---|---|---|---|
| Mode B + step 5 suite | `phase3_step5_modeb.log` | 20261105-213426-3642322 | 21:34:26 EET | 0 | **PASS** — 13 post-tests, 0 failed, 0 errors |
| Mode A (both accounting bridges) + suite | `phase3_step5_modea.log` | 20261105-214033-3905929 | 21:40:33 EET | 0 | **PASS** — 13 post-tests, 0 failed, 0 errors |
| Combo: sales_crm only | `phase3_step5_combo_crm_only.log` | 20261105-214711-4174740 | 21:47:11 EET | 0 | **PASS** |
| Combo: cheque module only | `phase3_step5_combo_cheque_only.log` | 20261105-215321-223963 | 21:53:21 EET | 0 | **PASS** |
| Combo: all three + suite | `phase3_step5_combo_all_three.log` | 20261105-215616-342695 | 21:56:16 EET | 0 | **PASS** — 13 post-tests, 0 failed, 0 errors |
| `lint_guard_pattern.py` | — | — | — | — | **PASS** both checks (56 files, 4 bridge modules) |
| `dep_graph.py` | — | — | — | — | **PASS** no cycles |

Module states read back from each combo database, not inferred from exit codes. Mode A has both
accounting bridges `installed`; Mode B has neither. `commission` is uninstalled in **both**, so
the Mode B run genuinely exercised the L2-only path that the regression below had broken.

### Test names

The six the brief named: `test_split_sum_not_100_rejected`,
`test_split_shared_between_reservation_and_contract`,
`test_toggle_off_creates_no_installment_lines`, `test_toggle_change_rejected_after_lines_exist`,
`test_mode_b_installments_on_no_account_move`, `test_mode_a_collections_unchanged`.

Five added:

- `test_split_no_lines_is_valid` — a single-owner deal has no split lines; that must stay valid,
  and a naive sum-to-100 rule would have broken it
- `test_split_deletion_leaving_partial_is_rejected` — `unlink()` does not fire a line
  constraint, so deleting one of two 50% lines needed the parent-level constraint to catch it
- `test_toggle_on_allows_generation` — the mirror of the toggle-off test, so that test cannot
  pass just because generation is broken
- `test_project_inherits_company_default` — inherit follows the company; explicit overrides it
- `test_toggle_change_allowed_before_lines_exist` — the lock must not block a clean project

The two mode tests are mode-aware and skip with a logged reason in the wrong mode, verified in
both directions: in the Mode B log the Mode A test skips and the Mode B test runs; in the Mode A
log the reverse. Neither gate can pass vacuously.

### The regression this step uncovered

The step 5 tests caught a **Phase 2 regression of mine**: `_build_commission_hierarchy`
(reservation, contract) and `compute_person_hierarchy` (EOI) were moved to L3 while **12 call
sites stayed in L2**. They are runtime attribute reads, so every install gate passed, yet
**creating a reservation, contract or EOI in an L2-only database raised `AttributeError`** - the
core sales flow, broken in exactly the Mode B configuration this refactor targets. Fixed with
`realestate.sales.commission.hooks`. Backlog #35, decisions log 2026-11-05.

The lesson is recorded in the decisions log: install gates cannot see cross-layer calls, so
every future layer move needs a grep for callers left behind, and each phase's tests must create
one of each core record.

### Open items

- **Lock rule is NEEDS REVIEW** in the decisions log - it is a design choice, not a confirmed
  requirement. Three questions there: whether a manager group may override the lock, whether
  only *unpaid* lines should block, and the deliberate single-blank-line escape in the
  sum-to-100 rule.
- **Backlog #36 is a data concern, not just code**: `customer.ownership` never had a sum-to-100
  constraint, so a live database may already hold splits that do not total 100. Those rows will
  raise on their next write. An audit before deployment is advisable; the greenfield decision
  does not cover the client's existing data.
- Step 6 owns the two deferred UI pieces listed above.

## Phase 3 step 6 — S4 rules on views and menus (2026-11-06). Phase 3: CLOSED

Branch `developer_18`. **No module code changed in this step** - the only new file is
`claude/scripts/lint_s4_views.py`, plus documentation. Install gates therefore cannot have
regressed and were not re-run; the step 5 gate table above remains the current evidence for the
module set.

### Audit: S4 is already met for everything Phases 2 and 3 built

| Module | Views in the module | Legacy views for its models | Menus |
|---|---|---|---|
| `sales_crm` | 3 | 90 | 0 |
| `unit_inventory` (L0) | **0** | **76** | **0** |
| `commission` | 0 | 26 | 0 |
| `construction` | 0 | 12 | 0 |
| `accounting` | 7 | — | 0 |
| `sales_cheques` | 1 | — | 0 |
| monolith + 6 others | — | **215 total** | 127 menuitems |

All 11 view files in the isky modules are `inherit_id` extensions of core Odoo models
(`account.*`, `res.config.settings`). **None is a standalone view for a model another layer
owns**, so S4's first rule holds for every view Phases 2 and 3 produced. The three
`security.xml` files are not views.

### Why the rest became its own phase

1. **L0 has no views and no window actions**, so the shared root menu S4 mandates would be
   hidden by Odoo - failing S4's own acceptance criterion about the roots being visible.
2. **The monolith already owns `menu_real_estate_root` "Real Estate"** with 101 menuitems, so
   adding L0's root now shows users a second, empty one.
3. **215 view records across 8 modules** own the UI for isky models. A correct menu tree
   requires owning the actions, which requires moving the views - menus and migration are one
   job, not two.

**Decision: Phase 3c (UI migration)**, layer by layer, L0 first. Added to
`claude/implementation_plan.md`. Phase 3 closes without it, and nothing user-visible changes -
the monolith keeps serving the UI exactly as today.

**Legacy-edit exception authorised 2026-11-06**: view and menu records only, strictly as part of
moving a model's UI. Business logic, Python and data files untouched. Recorded in the decisions
log.

### New gate: `claude/scripts/lint_s4_views.py`

Enforces S4 mechanically, three checks matching its acceptance list:

1. a standalone view (no `inherit_id`) must live in the module declaring the model's `_name`
2. every menuitem `action=` must resolve within the module's dependency closure
3. every menuitem `parent=` must resolve the same way

It also prints the remaining migration backlog per module, so Phase 3c has a running count.

```
Check 1 (standalone view in owning module)       -> PASS
Check 2 (menuitem action resolves)               -> PASS
Check 3 (menuitem parent resolves)               -> PASS
PASS - every new view is in its owning module, and every menu reference resolves.
```

The lint corrected my own earlier count: the backlog is **215 views across 8 modules**, not 204
across 3. The five it caught that a manual grep had missed - `arkzayed_collections_report` (3),
`arkzayed_cost_distribution` (3), `isky_base_modification` (2), `isky_contract_template` (2),
`arkzayed_contract_npv` (1) - matter because two are `isky_*` modules that the no-legacy-edit
rule never covered. Backlog #40.

### Deferred to Phase 3c (from step 5)

- the `installments_mode` field on the project form
- hiding the installment tabs and buttons when the flag is off

Both need a non-legacy project/reservation/contract form, which only exists after the L0 and L2
migrations. Model-level enforcement is complete and independent of both.

### Phase 3 is closed

| Step | State |
|---|---|
| 1 — S6 guard pattern + manual-paid group | closed |
| 2a — sales-owned flags | closed |
| 2b — `sales_accounting`, Mode B gate | closed |
| 3 + 4 — cheque split, `sales_cheques` | closed 2026-11-05 (S8 closed the #34 blocker) |
| 5 — installments toggle, shared split model | closed 2026-11-05 |
| 6 — S4 rules on views and menus | closed 2026-11-06; remainder → Phase 3c |

Open items carried forward: the NEEDS REVIEW lock rule (decisions log), the
`customer.ownership` data audit (backlog #36), open question 12.3 (the L1 cheque-settings gap),
12.1 and 12.2, and the S7 approval settings. Commits still held.

## Phase 4 — Commission (L3), 2026-11-06. Core: PASS. One gate RED.

Branch `developer_18`. Legacy repos untouched.

### Step 0 audit (before any code)

| Finding | Consequence |
|---|---|
| Four hierarchy implementations exist, and they **disagree** - the lead (in **L2**) omitted Sales Sector Manager and added `team.user_id`; the EOI **cleared every line** when the salesperson had no team; reservation and contract kept the user as Sales Person | The plan's "same manager mapping across lead, EOI, reservation and contract" **failed today**. It was the defect to fix, not a property to preserve. |
| Two commission line models: `realestate.commission` (L3, all four FKs) and `commission.commission` (L2, lead only, **default 1 instead of 100**) | D1: one model. |
| Commission basis, timing and lock: **nothing existed** | Built from scratch. |
| `job.level` had **no `company_id`**, and its role-flag uniqueness was global | Added, uniqueness now per company. |
| The six `is_*` role flags existed but **the engine ignored them**, hardcoding `['Sales Person', 'Sales Manager', 'Sales Sector Manager', 'Director']` and assigning a role by a field's position in that list | D2: role from `job.level`, order from a new `sequence`. |
| L3 hard-depended on the optional L1 accounting bridge but referenced **only core** `account.*` | D4: dependency replaced with core `account`. |

Decisions D1-D4 are in the decisions log, recorded before implementing.

### What Phase 4 built

| File | Purpose |
|---|---|
| `models/core/commission_hierarchy_engine.py` (new, 148 lines) | the single engine: team traversal decides *who*, `job.level` decides *what* |
| `models/config/commission_basis.py` (new, 110 lines) | `res.company.commission_basis`, `realestate.project.commission_basis_mode` / `_effective`, `_has_commission()`, both locks |
| `models/core/crm_lead_commission_ext.py` (new) | the lead's commission moved from L2 to L3 |
| `models/config/job_level.py` (rewritten) | `company_id`, `sequence`, per-company uniqueness, `_role_key()` |
| `models/core/commission.py` | `job_level_id` as the role; `is_tcr_sales_person` carried over from the removed duplicate |
| the three `*_crm_ext.py` files | hand-written builders deleted, replaced by the engine |
| L2 `crm_lead.py` | field + 4 helper methods (48 lines) removed; two use sites routed through hooks |
| L2 `commission_hooks_mixin.py` | two more no-ops so L2 still works without L3 |
| L2 `installments_gate_mixin.py` | `_installments_project()` generalised to `_deal_project()`, shared with the basis lookup |
| `tests/test_phase4_commission.py` (new, 13 tests) | the suite |

### Gates

| Gate | Log | Run ID | Exit | Result |
|---|---|---|---|---|
| Phase 4 suite (L3 installed) | `phase4_commission.log` | 20261106-165017-2520985 | 0 | **PASS** - 13 tests, 0 failed, 0 errors |
| Mode B: `sales_crm` alone, L3 absent | `phase4_modeb.log` | 20261106-165744-2808372 | 0 | **PASS** - 13 tests, 0 failures; L3 verified `uninstalled` |
| Mode A: both accounting bridges | `phase4_modea.log` | 20261106-170347-3043968 | 0 | **PASS** - 13 tests, 0 failures |
| Combo: cheque module only | `phase4_combo_cheque_only.log` | 20261106-171132-3304328 | 0 | **PASS** |
| Combo: sales_crm + cheque + bridge | `phase4_combo_all_three.log` | 20261106-171433-3421726 | 0 | **PASS** |
| `dep_graph.py` | — | — | — | **PASS** no cycles |
| `lint_guard_pattern.py` check 1 | — | — | — | **PASS** (61 files, 4 bridge modules) |
| `lint_guard_pattern.py` check 2 | — | — | — | **FAIL - 40 violations, pre-existing** (see below) |

Module states read back from each database, not inferred from exit codes:

| DB | installed |
|---|---|
| `phase4_commission` | commission, sales_crm, unit_inventory |
| `phase4_modeb` | sales_crm, unit_inventory (**commission absent**) |
| `phase4_modea` | accounting, sales_accounting, sales_crm, unit_inventory |
| `phase4_combo_cheque_only` | cheque module only |
| `phase4_combo_all_three` | cheque module, sales_cheques, sales_crm, unit_inventory |

`phase4_commission` is the first database in this whole refactor in which L3 is `installed`
(backlog #43).

### The lint is now red, on purpose

Widening check 2's pattern (backlog #45) exposed **40 references from `sales_crm` to 8 groups in
the legacy CRM module**, none of it a declared dependency - so `has_group()` returns False for
every user and each of those gates denies everyone. The old pattern matched only xmlids spelled
`group_*` and these end in `_group`, so the check had been reporting PASS over a real defect
since Phase 3 step 2a.

This is **not** a Phase 4 regression, and I have not softened the lint to hide it. Fixing it
means moving those 8 groups into `sales_crm`, exactly as Phase 3 step 1 did for
`group_manual_paid_installment` - the same work as open question 12.2 and S7. **Not done; needs
a decision on sequencing.**

Its most visible symptom is backlog #44: `crm.lead`'s nine approval-status fields all default to
`'pending'` and each constrains on one of those legacy groups, so **no opportunity can be created
at all in an L2-only database**. The Phase 4 mapping test had to set all nine falsy to create one.

### Five bugs this phase surfaced

- **#43** L3 had **never been installable** - undeclared Enterprise dependency `sale_commission`.
  Verified across every prior test database: L3 was `uninstalled` in all of them, so no gate had
  ever exercised it. Fixed.
- **#44** the nine-gate opportunity blocker above. Pre-existing.
- **#45** the lint blind spot. Fixed (the check now fails honestly).
- **#46** `res_users.py` is a pure duplicate of a declaration in `res_user.py`.
- **#47** `crm.team`'s role-field domains walk into L3's `job.level`.

Two bugs of my own, caught by the tests and fixed:

- `_inherit` as a **list without `_name`** makes Odoo treat the class as a new anonymous model;
  the symptom was `Many2many fields CrmLead.tag_ids and crm.lead.tag_ids use the same table`.
  Five extension classes needed an explicit `_name`.
- **MRO collision**: L2's no-op `_build_commission_hierarchy` hook won over L3's engine
  implementation of the same name, so the engine never ran and every document silently produced
  zero lines. Measured, not assumed. The engine's implementation is now `_commission_build()`
  and each concrete model overrides the public entry point explicitly - resolution by override,
  not by mixin ordering.

## S7 — Approval settings (2026-11-06). PASS

Branch `developer_18`. No legacy file touched; `custom/arkzayed` and `custom/marketstandards`
at zero diff.

### Pre-check

| Spec default | Reality |
|---|---|
| `sales_crm.group_finance_approval` | exists |
| `sales_crm.group_finance_two_approval` | exists |
| `sales_crm.group_manager_approval` | exists |
| `sales_crm.group_operation_manager_approval` | **does not exist** - the group is in `arkzayed_18_realestate_development` and referenced only from legacy views, never from a Python gate here |
| `sales_crm.group_confirm_reservation` | exists |
| `sales_crm.group_show_discount_percentage` | exists, but **view-only**: no Python gate |
| `sales_crm.group_edit_discount_percentage` | exists |
| `sales_crm.group_manual_paid_installment` | exists |
| `group_block_unit` | in **L0** `unit_inventory`, not `sales_crm` - fine, the spec does not claim otherwise |
| `group_exception_reservation` | exists |

So 6 of the 8 configurable stages have a real Python gate; `operation_manager` and
`show_discount` are configuration only. Recorded in the registry as `has_python_gate=False`.

### Files changed

New, in `isky_18_realestate_developer_sales_crm`:

| File | Lines | Purpose |
|---|---|---|
| `models/config/approval_settings.py` | 250 | the stage registry, the 9 company fields, both locks, the audit write |
| `models/core/approval_gate_mixin.py` | 77 | `_user_can_approve`, `_require_approval`, `_matched_approver_group`, `_log_approval` |
| `models/core/approval_audit.py` | 41 | `realestate.approval.audit` - config changes and approvals in one trail |
| `security/ir.model.access.csv` | 3 | ACLs for the audit model, append-only for ordinary users. **The first ACL file this module has ever had** (open question 12.2 is otherwise untouched) |
| `tests/test_s7_approval_settings.py` | 251 | 11 tests |

Modified: `res_config_settings.py` (9 related fields + the memberless-group onchange),
`security/security.xml`, `views/res_config_settings_views.xml` (the Sales Setup approvals block),
`__manifest__.py`, `models/config/__init__.py`, `models/core/__init__.py`, `tests/__init__.py`,
and the four gate files - `sale_proposal.py`, `sale_reservation.py`, `installment_lines.py`,
`eoi.py`. Plus `claude/scripts/lint_guard_pattern.py`.

Eleven gate sites now route through the helper; the two non-configurable gates
(`group_block_unit`, `group_exception_reservation`) remain hardcoded by design, and
`test_no_hardcoded_group_check_left` enforces exactly that split.

### Default group xmlids confirmed in the database (`s7_modeb`)

```
approval_enabled = true
company_finance_approver_rel       sales_crm.group_finance_approval
company_finance_two_approver_rel   sales_crm.group_finance_two_approval
company_manager_approver_rel       sales_crm.group_manager_approval
company_op_manager_approver_rel    (empty - by design, see decisions log)
company_confirm_reservation_rel    sales_crm.group_confirm_reservation
company_show_discount_rel          sales_crm.group_show_discount_percentage
company_edit_discount_rel          sales_crm.group_edit_discount_percentage
company_manual_paid_rel            sales_crm.group_manual_paid_installment
```

### Gates

| Gate | Log | Run ID | Exit | Result |
|---|---|---|---|---|
| Mode B + S7 suite | `s7_modeb.log` | 20261106-184327-2148121 | 0 | **PASS** - 24 tests, 0 failed, 0 errors |
| Mode A + suite | `s7_modea.log` | 20261106-185035-2441280 | 0 | **PASS** - 24 tests, 0 failures |
| Combo: cheque module only | `s7_combo_cheque_only.log` | 20261106-185727-2709165 | 0 | **PASS** |
| Combo: all three + suite | `s7_combo_all_three.log` | 20261106-190026-2825682 | 0 | **PASS** - 24 tests, 0 failures |
| `lint_guard_pattern.py` | — | — | — | **PASS** both checks |
| `lint_s4_views.py` | — | — | — | **PASS** all three |
| `dep_graph.py` | — | — | — | **PASS** no cycles |

24 tests = Phase 3 step 5's 13 + S7's 11.

### Four deviations from the spec, all in the decisions log

1. `operation_manager` ships with **no default** - the group the spec names does not exist in a
   module `sales_crm` can see.
2. Two of the eight stages have **no Python gate** and are excluded from the
   no-empty-group constraint, because an empty group there blocks nothing.
3. **Defaults had to be seeded explicitly.** A Many2many `default=` is never backfilled onto an
   existing record, and `base` creates `res.company` long before this module - so without
   `_s7_apply_default_approver_groups()` **every** database, fresh ones included, installs with
   all eight stages empty. Found by the first test run, not reasoned about in advance.
4. The memberless-group warning is an onchange (client-side) plus a server-side log; Odoo has no
   non-blocking warning on `write()`.

### Still blocking real use

Spec section 7 named 12.2, and it is still true: `sales_crm` ships no ACLs for its own models, so
a non-superuser cannot even write `sale.proposal`. The approval-audit test had to create
`ir.model.access` rows in-transaction to reach the gate at all. The approval layer is correct and
tested, but on real data the approval step is still unreachable for ordinary users.

## customer.ownership audit fixes (2026-11-06). Runs before 12.2.

Branch `developer_18`. No legacy file touched (verified by mtime sweep); `custom/arkzayed` and
`custom/marketstandards` at zero diff.

### Files changed — all in `isky_18_realestate_developer_sales_crm`

| File | Change |
|---|---|
| `models/core/split_line_mixin.py` | rewritten: `_split_group_field()` + `_split_group_domain()` (B2 precedence), `_validate_template_total()` (R1), 0% escape removed (R2), `_split_precision()` (R4), company filter in `_split_groups()` (R5), `_split_child_o2m`/`_split_template_m2m` + `_validate_split_children()` (C1) |
| `models/core/customer_ownership.py` | `return` → `continue` (B1), `_split_parent_fields` now precedence-ordered (B2), `self.env.company` default and `_order` removed (C1) |
| `models/core/installment_lines.py` | `_check_line_has_resolvable_project()` + `create()` override (R3) |
| `models/core/maintenance_installment_lines.py` | same (R3) |
| `models/config/realestate_project_sales_ext.py` | third lock route `sale_proposal_id.unit_id.project_id` (R3) |
| `models/config/res_company.py` | `split_percentage_precision` (R4) |
| `models/config/res_config_settings.py` | surfaced `split_percentage_precision` (R4) |
| `models/core/sale_reservation.py`, `models/core/sale_proposal.py` | `@api.constrains('customer_new_ownership_ids')` declared on the concrete models (C1) |
| `tests/test_ownership_fixes.py` | **new**, 15 tests |
| `tests/test_mode_b.py` | its unparented installment line now has a reservation (R3) |
| `tests/__init__.py` | registers the new suite |

### Item-to-test map

| Item | Tests |
|---|---|
| B1 copy action | `test_copy_action_multi_line_template_succeeds_on_reservation`, `..._on_contract`, `test_single_copy_implementation` |
| B2 group separation | `test_contract_and_reservation_groups_are_separate` |
| R1 template validation | `test_template_not_100_refused_and_creates_nothing`, `test_template_rows_may_be_edited_freely` |
| R2 0% escape | `test_saved_zero_percent_line_refused`, `test_unsaved_zero_percent_row_accepted` |
| R3 no unparented lines | `test_unparented_installment_line_refused`, `test_line_with_reservation_accepted`, `test_lock_sees_contract_only_line_through_the_unit`, `test_contract_without_unit_line_refused` |
| R4 precision | `test_precision_read_from_financials_setting` |
| R5 multi-company | `test_other_company_lines_do_not_count` |
| C1 cleanups | `test_cleanups` |

### Gates

| Gate | Log | Run ID | Exit | Result |
|---|---|---|---|---|
| Mode B + full suite | `own_modeb.log` | 20261106-200425-762050 | 0 | **PASS — 39 tests, 0 failed, 0 errors** |
| `lint_guard_pattern.py` | — | — | — | **PASS** both checks |
| `lint_s4_views.py` | — | — | — | **PASS** all three |
| `dep_graph.py` | — | — | — | **PASS** no cycles |
| Mode A + full suite | `own_modea.log` | 20261106-224239-8074 | 0 | **PASS — 39 tests, 0 failures** |
| Combo: sales_crm only | `own_combo_crm_only.log` | 20261106-224530-8564 | 0 | **PASS** |
| Combo: cheque module only | `own_combo_cheque_only.log` | 20261106-224746-8863 | 0 | **PASS** |
| Combo: all three + full suite | `own_combo_all_three.log` | 20261106-224854-8991 | 0 | **PASS — 39 tests, 0 failures** |
| L3 commission + Phase 4 suite | `own_commission.log` | 20261106-225119-9303 | 0 | **PASS — 13 tests, 0 failures** |

The first attempt at these five died when the session was torn down; `own_modeb` had already
completed. The scratchpad config and runner scripts went with it and were rebuilt from the
"Test invocation" recipe recorded earlier in this file - which is exactly what that section was
for. The five were then re-run under `setsid` so a teardown cannot kill them again.

39 tests = step 5's 13 + S7's 11 + these 15.

### Two findings not in the audit

1. **`continue` alone was enough** — the audit flagged a risk that it would still leave
   `from_action` records unassigned for a *stored* compute, which Odoo normally rejects. Measured
   instead of assumed: `test_copy_action_multi_line_template_succeeds_on_contract` exercises the
   path where the compute actually runs on a `from_action` record with no value in vals, and it
   passes. No extra assignment was needed.
2. **`@api.constrains` does not fire on create for a field absent from the vals** (backlog #51).
   R3's constrains on `('reservation_id', 'sale_proposal_id')` missed the exact case it was
   written for - a line created with *neither* field - because Odoo validates only the fields
   being written. The first run of `test_unparented_installment_line_refused` failed for this
   reason; fixed with a `create()` override on both line models. **Any other "at least one of
   these must be set" constrains in this codebase has the same hole; not swept in this run.**

## 12.2 — access rules for `sales_crm` (2026-11-06). CLOSED

Open question 12.2 was raised during Phase 3 step 2b and carried through steps 3, 4, 5, S7 and
Phase 4: `isky_18_realestate_developer_sales_crm` shipped **no** `ir.model.access` rows for the
38 models it declares, so no ordinary user could read or write installments, EOIs or contracts.
The models worked, but only for the superuser.

### Files changed

| File | Change |
|---|---|
| `security/ir.model.access.csv` | 52 new rows (54 total) covering all 38 declared models |
| `security/security.xml` | the matrix's rationale, which an Odoo CSV cannot carry |
| `models/config/maintenance_config.py` | `get_config()` bootstraps its singleton with `sudo()` |
| `tests/test_acl_12_2.py` | **new**, 8 tests, every one running `with_user(...)` |
| `tests/test_s7_approval_settings.py` | the in-transaction ACL workaround deleted (14 lines) |
| `tests/__init__.py` | registers the new suite |

### The matrix

| Class | Models | `base.group_user` | `sales_manager_group` |
|---|---|---|---|
| Recompute children — installment lines, maintenance lines, payment allocations, ownership lines, EOI/reservation payments, loan lines, counters, notifications, penalties, meeting reports, revenue shares | 18 | read, write, create, **unlink** | — |
| Documents — EOI, reservation, contract, offer, discount request, sale request, permission request, broker unit | 8 | read, write, create | + **unlink** |
| Configuration — attachment type, lead stage, project sale phase, maintenance config, discount config, discount approval | 6 | **read only** | full |
| Deprecated — `commission.commission` | 1 | read only | `base.group_system` full |
| Wizards (transient) | 4 | full | — |
| Audit trail (S7) | 1 | read + create (append-only) | `base.group_system` full |

Unlink is split by what deletion *means*: children that a recompute deletes and recreates must be
unlinkable by an ordinary user, because `self.installment_ids = None` and the reallocation engine
run as that user and would otherwise fail; documents are manager-only to delete.

`crm.lead` has no row — core `crm` owns it, and this module only sets `_name` on it to inject a
mixin (Phase 4).

### Verified in the database (`acl_modeb`)

```
54 ACL rows from sales_crm, covering 38 models
rows with NO group (would apply to every user): 0
```

### Gates

| Gate | Log | Run ID | Exit | Result |
|---|---|---|---|---|
| Mode B + full suite | `acl_modeb.log` | 20261106-231532-12771 | 0 | **PASS — 47 tests, 0 failed, 0 errors** |
| Mode A + full suite | `acl_modea.log` | 20261106-231802-13486 | 0 | **PASS — 47 tests, 0 failures** |
| Combo: sales_crm only | `acl_combo_crm_only.log` | 20261106-232048-13931 | 0 | **PASS** |
| Combo: cheque module only | `acl_combo_cheque_only.log` | 20261106-232308-14248 | 0 | **PASS** |
| Combo: all three + full suite | `acl_combo_all_three.log` | 20261106-232421-14438 | 0 | **PASS — 47 tests, 0 failures** |
| L3 commission + Phase 4 suite | `acl_commission.log` | 20261106-232653-15454 | 0 | **PASS — 13 tests, 0 failures** |
| `lint_guard_pattern.py` | — | — | — | **PASS** both checks |
| `lint_s4_views.py` | — | — | — | **PASS** all three |
| `dep_graph.py` | — | — | — | **PASS** no cycles |

47 tests = step 5's 13 + S7's 11 + ownership's 15 + these 8.

### Why this survived five phases, and the guard against a repeat

**Odoo tests run as superuser, which bypasses ACLs entirely** - so every test written before this
one passed regardless of what the rules said. Every test in `test_acl_12_2.py` uses
`with_user(...)`, and two are structural guards: `test_every_model_has_an_acl_row` fails when a
new model ships without one, and `test_no_acl_row_grants_access_to_every_user` fails if an
empty-group row is ever added here.

### Three findings from this run

1. **A design fix was forced.** `maintenance.config.get_config()` lazily **creates** the
   singleton config row, and it is called from `sale_reservation._default_maintenance()` while an
   ordinary user creates a reservation. With configuration read-only for users, reservation
   creation failed outright. Now created with `sudo()` - bootstrapping a default is a system
   action, and requiring every salesperson to hold configuration-write rights just to open a
   reservation would have made the configuration ACL meaningless.
2. **An Odoo CSV cannot carry comments** (backlog #54). A `#` row parses as one column and raises
   `IndexError`, surfacing only as "Failed to load registry". The rationale had to move to
   `security.xml`.
3. **`unit_inventory` and `commission` grant full CRUD to every user, portal included**
   (backlog #52) - 28 and 9 rows with an **empty** `group_id`, on models including
   `realestate.project` and `real.estate.unit`. 12.2 deliberately does not follow that
   convention. Tightening those rows is an L0/L3 change needing its own review, since
   `sales_crm`'s portal controllers render unit pages. **Not done here. Security severity.**

## Work order (decided 2026-11-06, owner)

The repo is under construction and no one uses it yet, so release-time security work moves to the end.
Remaining order:

1. Phase 4 formal closure: update this file (it still says NOT STARTED for Phase 4) and confirm the gate table.
2. #49 lead stages in `sales_crm`, so the L2-only lead workflow runs on a plain database.
3. Phase 5 (Construction, L4).
4. Phase 6 (Settings, five sections).
5. Phase 7 (remove hardcoded client values). Takes backlog #33, #29 and open question 12.3.
6. Phase 8 (Broker branch).
7. Phase 3c (UI migration, L0 first).
8. ACL hardening for L0 and L3 (backlog #52). This is a release blocker, not an optional item. It must be done before any client database is deployed.

Phase 9 stays on hold until the target branch is confirmed.

---

# Reconstructed record, 2026-11-07 to 2026-11-09

Everything above this line is the 2026-11-06 snapshot restored from the recovery pack and is
original. Everything below was **rebuilt on 2026-11-09** from
`claude/recovery/reports_from_transcript.md` after the `claude/` docs were lost; see
`claude/recovery/recovery_report.md` for why git could not restore them.

Every fact below carries `[RECONSTRUCTED]` and the transcript line of the report it came from.
Run IDs, exit codes and counts are copied exactly, never paraphrased. Where no report survives for
a phase, the entry says `NOT RECOVERED` and stops there - nothing is inferred to fill a gap.

## Phase 4 — Commission (L3): closure

**NOT RECOVERED: Phase 4 closure (2026-11-07).** The 2026-11-06 section above records Phase 4 as
"Core: PASS. One gate RED". The formal closure run of 2026-11-07 has no report in the recovery
pack, so its gate table and run IDs are gone. What is independently known: `claude/logs/` holds
`p4c_modeb.log`, `p4c_modea.log` and `p4c_all_three.log`, which are that closure's own logs and
still carry their run IDs, start times and exit codes on disk.

## Backlog #49 — lead stage records in `sales_crm`

`[RECONSTRUCTED]` <!-- transcript line 462 --> The finding, in full: repointing the eight CRM
groups exposed that `sales_crm` still resolved **22 other legacy-CRM xmlids - 35 of them via
`env.ref()`**, which raises rather than failing quietly. Of those, **31 refs to CRM lead stages**
(`stage_new`, `stage_qualified`, `stage_locked`, `stage_lead5-8`), 9 portal templates, 2 cron refs,
3 report refs. Consequence recorded at the time: "the entire lead workflow raises
`ValueError: External ID not found` without the legacy module". Same bug class as the groups, but
data rather than code - the stage records must be created in `sales_crm`.

**NOT RECOVERED: #49 closure (2026-11-07).** The fix run has no report in the pack. `claude/logs/`
holds `t49_modeb.log` and `t49_legacy_combo.log` on disk.

## Phase 5 — Construction (L4): CLOSED

`[RECONSTRUCTED]` <!-- transcript line 1048 -->

| Gate | Run ID | Start | Exit | Result |
|---|---|---|---|---|
| Standalone — L4 + L0 (the acceptance) | `20261107-203805-104109` | 20:38:05 EET | 0 | 9 tests, 0 failed, 0 errors |
| With L1 bridge | `20261107-204012-104549` | 20:40:12 EET | 0 | 9 tests |
| Coexistence — L4 + L2 + L3 | `20261107-204339-105203` | 20:43:39 EET | 0 | 9 tests |

Lints all PASS, no cycles. Verified in `p5_standalone` rather than inferred: L4 and L0 installed;
`account`, L1, `sales_crm`, `commission`, `arkzayed_cost_distribution` and the monolith all
uninstalled. Legacy repos at zero diff.

**The standalone gate earned its keep immediately.** Its first run failed where the with-L1 run
passed - the signal only a minimum-footprint gate can give. `vendor_commitment.vendor_id` carried
`domain=[('supplier_rank', '>', 0)]`, and `supplier_rank` is declared by Odoo's `account`. The
domain was removed rather than adding `account` to L4's depends; the lost filter is backlog #63.

Acceptance mapped to named tests: `test_depends_on_l0_and_l1_only` (reads the manifest, not
memory), `test_nothing_from_the_cost_distribution_module` (source sweep as a test), plus the
manager/engineer/cron behaviour and `test_no_new_monolith_reference`, which allowlists exactly two
report-layer spots so a third reference fails the suite.

## Phase 6 — Settings in five sections

**NOT RECOVERED: Phase 6 (2026-11-07).** No report in the pack. Known from the next phase's report
`[RECONSTRUCTED]` <!-- transcript line 1192 -->: Phase 6 left a gap **G4** (company type: developer
or broker), which Phase 8 then implemented. `claude/logs/` holds `p6_modeb.log`, `p6_modea.log`,
`p6_all_three.log`, `p6_l0.log` and `p6_l4.log` on disk. `phase6_settings_inventory.md`, which
Phase 6 produced, is listed in `RECOVERY_MANIFEST.md` as "not found in any source".

## Phase 7 — Remove hardcoded client values: CLOSED

`[RECONSTRUCTED]` <!-- transcript line 1080 -->

| Gate | Run ID | Start | Exit | Result |
|---|---|---|---|---|
| Mode B | `20261107-233843-137933` | 23:38:43 EET | 0 | 106 tests, 0 failed |
| Mode A | `20261107-234440-139277` | 23:44:40 EET | 0 | 106 tests |
| All three | `20261107-235044-140490` | 23:50:44 EET | 0 | 106 tests |
| L0 standalone | `20261107-235632-141627` | 23:56:32 EET | 0 | 7 tests |

All four lints PASS. Legacy repos zero diff; the only legacy files in the tree are #60's five,
untouched.

Delivered: client-named fields became `realestate.revenue.split.line` (company, business line,
credit account, analytic account, percentage, sequence), edited inline in Financials - the four
GIS/OAYA settings and the two `account.analytic.account` flags are gone. `res.company.vat_rate`
(14.0) and `withholding_tax_rate` (5.0) plus `_vat_divisor()`, which at the defaults reproduces
exactly what 1.14 and 0.05 did. **39 config keys moved to the `realestate.` prefix, 71 call sites
across 13 files**, values carried over by migration.

The first bullet exposed a triplication: the same ~60 lines of collection-entry money math existed
three times (contract signing, payment registration, cheque collection). All three now call
`realestate.revenue.split.mixin`.

New gate `lint_client_values.py`: no client business-line name in any isky module, every config key
generic, and every surviving legacy reference inside **a shrinking allowlist of 41**.

Bullet 4 (job level flags) was assessed and deliberately **not** changed - six booleans that are
the product's role vocabulary, not a client's. Recorded as backlog #67 with the reasoning.

Three defects: **#68 fixed with a behaviour change** - "Residential Units Default Years" wrote one
key while both readers read another, so it never had any effect; on a database where someone set
that field, the number changes. The migration guard was wrong in the first draft (`get_param`
answers `False`, not `None`, so it skipped every key), caught by the test that asserts the copy
rather than the map. **#69 open** - the cheque bridge reads a monolith group that resolves for
nobody.

## Backlog #60 — three stale model xmlids in the monolith: PARTIALLY FIXED

`[RECONSTRUCTED]` <!-- transcript line 1019 --> First run, under the owner's 2026-11-07 exception
for exactly three one-token legacy edits. **Four lines, not three**: `model_cheque_manage` carried
the wrong prefix on two report-binding lines as well.

| File:line | Before → After |
|---|---|
| `security.xml:107` | `isky_…sales_crm.model_maintenance_template` → `isky_18_realestate_developer_unit_inventory.model_maintenance_template` |
| `security.xml:127` | `isky_…sales_crm.model_installment_template` → `isky_18_realestate_developer_unit_inventory.model_installment_template` |
| `cheque_receipt_report.xml:11` | `isky_…sales_crm.model_cheque_manage` → `arkzayed_18_gt_cheque_management.model_cheque_manage` |
| `cheque_receipt_voucher_report.xml:10` | same change |

Gate hit the prompt's stop condition: `t60_client_stack.log`, run `20261107-191918-89100`, start
2026-11-07 19:19:18 EET, **exit 255** - past all three fixed xmlids (it had died at
`security.xml:107`, now reaches line 132). Lints all PASS, 28 modules, no cycles.

`[RECONSTRUCTED]` <!-- transcript line 1039 --> Option B applied, with two corrections to the
figures: **the CSV rows are 41, not 38** (the first count deduplicated by xmlid; `model_loan_line`
and `model_lead_stage` each appear on two rows), split **35 empty-group / 6 grouped**. One of the
six was held back - monolith row 2 grants `base.group_user` `1,1,1,1` on
`real.estate.sale.reservation` where 12.2 deliberately chose `1,1,1,0`, so fixing the reference
alone would have re-granted delete to every internal user and undone a closed decision. It went to
#52 with the other 35.

| Gate | Log | Run ID | Start | Exit | Result |
|---|---|---|---|---|---|
| Client stack, fresh DB | `t60b_client_stack.log` | `20261107-193654-92604` | 19:36:54 EET | 255 | FAIL, as expected |
| Mode B regression, `sales_crm` alone | `t60b_modeb.log` | `20261107-194338-93947` | 19:43:38 EET | 0 | PASS — 63 tests, 0 failed, 0 errors |

What the failing gate proves: `security/security.xml` now loads completely; the install dies later
in the monolith's CSV, and Odoo reports every CSV error in one pass, so the remaining set is known
exactly - **20 distinct unresolved model xmlids**, every one either the held-back reservation row or
an empty-group row.

## Phase 3c — UI migration, step 1 (L0's UI): CLOSED

`[RECONSTRUCTED]` <!-- transcript line 1204 -->

| Gate | Run ID | Start | Exit | Result |
|---|---|---|---|---|
| L0 standalone — the UI must render with L0 alone | `20261108-033210-184918` | 03:32:10 EET | 0 | 10 tests, 0 failed |
| Mode B | `20261108-033402-185319` | 03:34:02 EET | 0 | 121 tests |
| Mode A | `20261108-034046-186886` | 03:40:46 EET | 0 | 121 tests |
| All three | `20261108-090933-189093` | 09:09:33 EET | 0 | 121 tests |
| L4 + L0 | `20261108-091707-191029` | 09:17:07 EET | 0 | 9 tests |

All four lints PASS. The real inventory was **121 records across 39 files in 4 legacy modules, plus
39 menuitems** - the lint had undercounted. Moved: **110 records into 32 view files and 2 report
files**, plus a new `views/menus.xml` with 39 menuitems. Local xmlids unchanged; only the module
half moved. L0's must-move count went **76 → 8**, and the 8 are not residue: 6 are
construction-progress records (step 4) and 2 are sales reports (step 2).

Three things that nearly went wrong quietly: the monolith's menus referenced the moved actions
**bare**, and a dotless xmlid resolves against the current module, so 39 references would have
broken silently; four views had to be **split, not moved**; and **#73** -
`real.estate.unit.customer_id` carried `domain="[('is_customer','=',True)]"`, a field from a legacy
contact module, harmless for five phases because a Many2one domain resolves at search time and
fatal the moment L0 shipped the form.

Legacy edits: 39 files, all view or report files - zero Python, security, data or manifest. Both
protected repos at zero diff.

## Phase 3c — step 2a (L2's self-contained UI): CLOSED

`[RECONSTRUCTED]` <!-- transcript line 1214 -->

| Gate | Run ID | Exit | Result |
|---|---|---|---|
| L0 standalone | `20261108-112407-220087` | 0 | 10 tests |
| Mode B | `20261108-112451-220242` | 0 | 121 tests, 0 failed |
| Mode A | `20261108-112803-221081` | 0 | 121 tests |
| All three | `20261108-113203-223008` | 0 | 121 tests |
| L4 + L0 | `20261108-113524-224517` | 0 | 9 tests |

All four lints PASS. **The figures changed before any code did**: `lint_s4_views.py` had credited
`sale.proposal`, `eoi.eoi` and `real.estate.sale.reservation` to `commission`, because it took the
first module alphabetically declaring a `_name`. Corrected and recorded as **#74**.

| Layer | Reported after step 1 | Actually | After 2a |
|---|---|---|---|
| `sales_crm` | 86 | **133** | 40 |
| `commission` | 85 | **38** | 38 |

Delivered **101 of L2's 133 records**: 28 view files, 4 report files, and a Sales section with 26
entries under the root L0 declares. All 59 candidate views were validated offline first - create in
a savepoint in a Mode B database, read Odoo's own error, roll back. **Zero installs spent on view
errors, against four in step 1.** Measured in the databases: Mode B shows `['Units', 'Sales']` (35 +
26 entries), L0 alone shows `['Units']`. 69 legacy files touched, every one a view or report file.

**Step 2b was split out and stopped for a decision**: 32 records cannot move under "view and menu
records only" - fifteen name one of ten monolith security groups, sixteen need a monolith
paperformat, one needs a monolith action button.

## Phase 3c — steps 2b, 3, 4, 5 and 6

**NOT RECOVERED: Phase 3c steps 2b, 3, 4, 5, 6 (2026-11-08).** No report in the pack. What is
independently known: `claude/logs/` holds `p3c_l0.log`, `p3c_modeb.log`, `p3c_modea.log`,
`p3c_all_three.log` and `p3c_l4.log` on disk, and the sign-client gate report of 2026-11-08
`[RECONSTRUCTED]` <!-- transcript line 1520 --> states that the contract form is "one of Phase 3c's
40 deferred records", which is consistent with step 2a's figure above but is not a closure record
for the later steps.

## Phase 8 — Broker branch: CLOSED

`[RECONSTRUCTED]` <!-- transcript line 1192 -->

| Gate | Run ID | Start | Exit | Result |
|---|---|---|---|---|
| Mode B | `20261108-011050-157118` | 01:10:50 EET | 0 | 121 tests, 0 failed |
| Mode A | `20261108-011426-157843` | 01:14:26 EET | 0 | 121 tests |
| All three | `20261108-011817-158634` | 01:18:17 EET | 0 | 121 tests |
| L0 standalone | `20261108-012156-159471` | 01:21:56 EET | 0 | 10 tests |

All four lints PASS. **The audit changed what the phase needed to do**: the plan assumed the broker
recalculates the code and must be stopped. It does not - `broker.unit` had no system code at all,
just a free-form `unit_code` the portal sets. So Phase 8 added the code as **received data**, not
as a stripped computation.

Acceptance read off the live field in `p8_modeb`:

```
broker.unit.system_code:               type=char  compute=False  related=False  store=True
res.company.realestate_company_type:  selection=['developer','broker']  default=developer  required=True
```

On G4 the field is named `realestate_company_type`, not `company_type`, because `res.partner`
already declares `company_type` (person/company). Two findings: **#70** -
`broker.unit.parent_source_id` still references the developer's L0 hierarchy directly, and the
structural split needs Phase 9; **#71** - `broker.unit.built_up_area` is declared `requied=True`,
a typo, so the field is not required at all.

## Backlog #52 — the ACL audit

**NOT RECOVERED: the #52 ACL audit report (2026-11-08).** `RECOVERY_MANIFEST.md` lists
`acl_audit_52_report.md` among the four audit reports whose "full text is in
reports_from_transcript.md", but no block in that file carries it - the only occurrence of the
filename is in the recovery check's own list of lost files
`[RECONSTRUCTED]` <!-- transcript line 1584 -->. What survives on disk: `claude/logs/acl52_lints.log`,
`acl52_modeb.log` and `acl52_portal_probe.log`, which carry that audit's run IDs and exit codes.

## The commission flow audit (backlog #80)

`[RECONSTRUCTED]` <!-- transcript line 1353 --> Read-only audit, report was
`claude/commission_flow_trace.md` (467 lines).

| Purpose | Log | Run ID | Start | Exit |
|---|---|---|---|---|
| Fresh Mode B install + tests | `cf_modeb.log` | `20261108-151530-266014` | 15:15:30 EET | 0 (0 failed of 19) |
| Flow trace, steps A–H | `cf_trace.log` | `20261108-152259-268162` | 15:22:59 EET | 0 |
| Probe: hard AccessError? | `cf_probe_access.log` | `20261108-152347-268327` | 15:23:47 EET | 0 |
| Probe: sudo cache leak? | `cf_probe_sudo_leak.log` | `20261108-152430-268504` | 15:24:30 EET | 0 |
| Probe: direct vs recompute | `cf_probe_recompute.log` | `20261108-152548-268770` | 15:25:48 EET | 0 |

`sale.commission.plan` exists - Enterprise `sale_commission`. Findings are in backlog #80.

## The returned-cheque audit (backlog #81)

`[RECONSTRUCTED]` <!-- transcript line 1414 -->

| Purpose | Log | Run ID | Start | Exit |
|---|---|---|---|---|
| Mode B + `sales_cheques` + commission | `rc_modeb.log` | `20261108-155701-275416` | 15:57:01 EET | **1** |
| Returned-cheque probe (rolled back) | `rc_probe.log` | `20261108-160133-276734` | 16:01:33 EET | 0 |
| `sales_cheques` alone, to isolate the above | `rc_bridge_only.log` | `20261108-160220-276922` | 16:02:20 EET | **1** |

Both exit-1 runs are the same pre-existing error in the bridge's own suite, isolated by the third
run; the installs themselves succeeded.

## The signed-by-client audit (backlog #79)

`[RECONSTRUCTED]` <!-- transcript line 1491 -->

| Purpose | Log | Run ID | Start | Exit |
|---|---|---|---|---|
| Fresh Mode B install + tests | `sbc_modeb.log` | `20261108-230432-295023` | 23:04:32 EET | 0 (0 failed of 19) |
| Signing-state probe (rolled back) | `sbc_probe.log` | `20261108-231136-295902` | 23:11:36 EET | 0 |

## The sign-client gate: CLOSED

`[RECONSTRUCTED]` <!-- transcript line 1520 -->

| Gate | Run ID | Start | Exit | Result |
|---|---|---|---|---|
| Lints ×4 | `20261108-233625-302698` | 23:36:25 EET | 0 | all pass; check 2 still reachable with the new group; no cycles |
| Mode B | `20261108-233645-302823` | 23:36:45 EET | 0 | 0 failed, 0 errors of 133 |
| Mode A (both bridges) | `20261108-234325-305010` | 23:43:25 EET | 0 | 0 failed, 0 errors of 133 |
| All three (+ cheques) | `20261108-235005-306757` | 23:50:05 EET | 0 | 0 failed, 0 errors of 133 |
| L4 + L0 standalone | `20261108-235745-308704` | 23:57:45 EET | 0 | 0 failed, 0 errors of 9; zero sign-gate tests ran — correct, L4 doesn't depend on L2 |

The test file's last edit was 23:39:24 and the class first ran at 23:42:43, so Mode B exercised the
final version - checked, not assumed. All 12 new tests ran.

This work **is committed**: `be2153c` ("phase 8 added", `abdalla`, 2026-11-09 12:19:59) contains
`security.xml`, `approval_settings.py` and `test_sign_client_gate.py`, and `origin/developer_18`
matches it.

## The CEO signing gate

**NOT RECOVERED as implementation.** The decisions CEO-D1 to CEO-D3 survive and are merged into
`decisions_log.md` under "2026-11-09 — CEO signing (D1-D3), recovered from partial stub". **The
code was never written**: that run stopped at step 0 when the docs loss was found. No gate ran, no
`sign_ceo` stage exists in the registry. Steps 1 and 2 of that run did complete as read-only
checks, and their findings are in the decisions entry.

## The recovery check (2026-11-09)

`[RECONSTRUCTED]` <!-- transcript line 1584 --> Read-only check of whether the lost docs could be
restored from git. Answer: **NOT-FOUND for every file**. `.gitignore:6` is `*.md`, unanchored, so
the documents were never tracked - `git ls-files claude/` returns 107 tracked files, none of them
`.md`, and `.md` appears in 0 of 18 commits across all 10 refs. 2,449 blobs scanned, zero document
matches; zero unreachable objects; no stashes, no tags, no editor leftovers. Full detail in
`claude/recovery/recovery_report.md`.

## Signing gate, always enforced (2026-11-10)

Owner decisions SG-D1..D4 (`decisions_log.md`, 2026-11-10): **one signer group -
`director_manager_group` (Director) - signs `signed_client`, `signed_by_client` and `signed_ceo`,
whether or not approvals are enabled.** This supersedes the 2026-11-08 rule (Sales Team Lead signs
the client step, gate skipped when `approval_enabled = False`) and the unimplemented 2026-11-09
CEO split. **The merge waits on the owner confirming SG-D1's consequence: the Sales Team Lead no
longer signs.** Nothing committed.

### What changed

| File | Change |
|---|---|
| `sales_crm/models/config/approval_settings.py` | `sign_client` stage **removed** from `APPROVAL_STAGES`; `sign_client` + `sign_ceo` added to `NON_CONFIGURABLE_GATES` → `director_manager_group`; new `NON_CONFIGURABLE_GATE_LABELS`; company field `sign_client_group_ids` removed |
| `sales_crm/models/config/res_config_settings.py` | the related field and its onchange/sweep entries removed |
| `sales_crm/views/res_config_settings_views.xml` | the Sales Setup row removed |
| `sales_crm/models/core/sale_proposal.py` | `SIGNING_STATES` is now `{'signed_client': 'sign_client', 'signed_ceo': 'sign_ceo'}`; the `write()` gate checks `has_group()` against `NON_CONFIGURABLE_GATES` directly (not `_require_approval()`, which honours the approvals switch) and writes the same audit-row shape the S7 gates write |
| `sales_crm/tests/test_sign_client_gate.py` | rewritten to the new rule: 11 tests, all as real users |
| `.gitignore` | (the same working session, backlog #82) lines 7-8: `!claude/`, `!claude/**/*.md` |

Corrections to the prompt's premises, reported not silently absorbed: `sign_ceo_group_ids` never
existed (the CEO stage was never built), so only `sign_client_group_ids` was removed; and the two
sign buttons live in the monolith's contract form, so their `groups=` waits for Phase 9 (SC-D5).

### Tests (11, every one through `with_user(...)`)

| Test | What it pins |
|---|---|
| `test_group_chain_unchanged` | SG-D4 - the team-lead group keeps its chain place; the chain does not run backwards |
| `test_signing_not_configurable` | SG-D2/D3 - gates in `NON_CONFIGURABLE_GATES` → Director; stage out of the registry; no company/settings field |
| `test_director_can_sign_client_and_ceo` | both states; one audit row each naming the gate and matched group |
| `test_director_can_set_signed_by_client_flag` | the Boolean route, allowed for the Director |
| `test_team_lead_cannot_sign` | SG-D1's consequence - refused, named step, state unmoved |
| `test_manager_cannot_sign` | refused on `signed_ceo` |
| `test_salesperson_cannot_sign` | refused on both states and the flag |
| `test_approvals_off_still_enforced` | `approval_enabled=False`: salesperson, team lead and manager all still refused on all three writes; the Director still signs. Replaces 2026-11-08's `test_stage_off_skips_gate`, which asserted the opposite |
| `test_signing_an_already_signed_contract_is_not_a_second_approval` | the SC-D3 carve-out survives |
| `test_source_sweep_for_signing_states` | no `_write`/SQL bypass; no `write()` override without `super()` |
| `test_the_gate_covers_every_signing_state` | every signing-looking state is mapped, and every mapped gate is enforced |

### Gates

| Gate | Log | Run ID | Start | Exit | Result |
|---|---|---|---|---|---|
| Lints ×4 (`lint_guard_pattern` both checks, `lint_s4_views`, `dep_graph`, `lint_client_values`) | `claude/logs/sg_lints.log` | `20261110-141926-489239` | 2026-11-10 14:19:26 EET | **0** | all four pass |
| Mode B | `claude/logs/sg_modeb.log` | `20261110-141943-489420` | 2026-11-10 14:19:43 EET | **0** | 0 failed, 0 error(s) of **132** tests; all 11 gate tests ran |
| Mode A (both accounting bridges) | `claude/logs/sg_modea.log` | `20261110-142323-490863` | 2026-11-10 14:23:23 EET | **0** | 0 failed, 0 error(s) of **132** tests; all 11 gate tests ran |
| All three (+ cheque module + `sales_cheques`) | `claude/logs/sg_all_three.log` | `20261110-142735-492118` | 2026-11-10 14:27:35 EET | **0** | 0 failed, 0 error(s) of **132** tests; all 11 gate tests ran |
| L4 + L0 standalone | `claude/logs/sg_l4.log` | `20261110-143125-493318` | 2026-11-10 14:31:25 EET | **0** | 0 failed, 0 error(s) of **9** tests; zero gate tests ran — correct, L4 does not depend on L2 |

### Legacy edits

**Zero.** Both protected legacy repos at zero diff; no `arkzayed_*` file touched.

### The group and the gates, read back from `sg_modeb` (not from source)

```
xmlid     : isky_18_realestate_developer_sales_crm.director_manager_group  (db id 81)
name      : Director
implies   : operation_manager_group -> sales_manager_group -> sales_team_lead_group -> salesman
director holds team-lead transitively : True
team lead holds director              : False
NON_CONFIGURABLE_GATES['sign_client'] = director_manager_group
NON_CONFIGURABLE_GATES['sign_ceo']    = director_manager_group
'sign_client' in APPROVAL_STAGES      = False
company field / settings field        = both gone
```

**All four database gates green, zero failures anywhere.** The suite is 132 tests (the
2026-11-08 file's 12 were replaced by 11). CLOSED as implementation; the **merge** waits on the
owner confirming SG-D1's consequence (the Sales Team Lead no longer signs). Nothing committed.
