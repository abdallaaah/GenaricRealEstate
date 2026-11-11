# Decisions Log — GenaricRealEstate

Source of truth for this project. If `implementation_plan.md` conflicts with an entry here, this log wins.
Every new or changed decision must be recorded here *before* it is implemented.

Format per entry: `## YYYY-MM-DD — Title` then a short rationale and the scope it affects.

---

## Section 12 (2026-11-04) — Open questions

Numbered so it can be cited as "decisions_log.md section 12". Items here are **decided
provisionally and awaiting confirmation**, not settled.

**12.1 — EOI Paid button reuses the installment Paid group.** NEEDS FUNCTIONAL CONFIRMATION.
`eoi.action_mark_paid()` / `action_unmark_paid()` are gated on
`isky_18_realestate_developer_sales_crm.group_manual_paid_installment` — the same group that
gates ticking an installment Paid by hand. Supplement S2 specifies the EOI Paid button and that
it stores date and user, but says nothing about a permission gate. I added one, reusing that
group, because both actions acknowledge money with no payment or cheque record behind it, and
leaving the EOI button ungated would be the weaker default. The group's label reads "Can Tick
Installments as Paid", which does not mention EOIs, so either the label or the group choice
likely needs adjusting. **Functional team to confirm**: same group, a new EOI-specific group, or
no gate at all. Verified working: a non-member is rejected on both actions with no field change,
and the same user succeeds once added to the group (see
`claude/logs/phase3_gate_nonmember.log`).

**12.2 — RESOLVED 2026-11-06** (see the entry of that date). ~~`sales_crm` ships no access rules for its own models.~~ Found while building the
non-member gate test: `isky_18_realestate_developer_sales_crm` has no `ir.model.access.csv`, and
in the Mode B database both `installment.lines` and `eoi.eoi` have **zero** ACL rows. Any
non-superuser is therefore blocked from those models outright, before any group gate is even
consulted — so no ordinary user can work with installments or EOIs. The gate test had to create
temporary in-transaction ACLs just to reach the models and isolate the group check. Not fixed
here: adding ACLs is a security-model decision (which groups get read/write/create/unlink on
which sales models) that belongs with the S7 approval-settings work, not with Phase 3 step 2b.
Recorded as backlog item too.

**12.3 — where should the cheque settings live, and who closes the L1 gap?** S8's placement rule
("`sales_cheques` if sales-facing, otherwise the L1 cheque module") cannot be followed literally:
`cheque_incoming_credit_account_id` is core cheque accounting, so it belongs at L1, but L1 is the
legacy `arkzayed_18_gt_cheque_management`, which CLAUDE.md puts off limits. Both settings were
therefore put in `isky_18_realestate_developer_sales_cheques` with the fix at the
`cheque.manage.create()` choke point, which covers all 11 create call sites — the four legacy
wizards included — with no legacy edit. The residual gap: a database with the legacy cheque module
but without `sales_cheques` has no choke point, so those four wizards can still reach the NOT NULL
constraint. **Decision needed**: accept the gap, create a new L1-level `isky` cheque-config module
(which would also give backlog #29's rename a home), or allow a one-line edit to the legacy
module's `default_get`. See the S8 implementation entry below for the full reasoning.

## Section 11 (2026-11-04) — Approval gates: configurable approver groups, gates stay in code

Numbered rather than dated so `implementation_plan_supplement.md` S7 can cite it as
"decisions_log.md section 11". (Note: this file is otherwise chronological, with no numbered
sections — see the housekeeping note at the end of this entry.)

Context: Phase 3 step 2a's new lint check found 10 approval/permission features that were
**silently dead** — `sales_crm` referenced 7 groups defined in the monolith it does not depend
on, so `has_group()` returned False for every user. Those gates are now live again, which means
decisions are needed about how they are configured.

Decisions:
1. **Approver groups are configurable.** A setting per approval *stage* picks which `res.groups`
   approve that stage. Default: the current groups.
2. **The gates themselves stay in code.** Do NOT add any setting that disables unit blocking,
   reservation exception, or any other control that bypasses a check. Configurability covers
   *who* approves, never *whether* the check runs.
3. **One company-level setting in Sales Setup turns the approval step on or off.** Default = on.
4. **At most 2–3 approval settings in Sales Setup.** No per-gate flag.
5. **Before enabling the 10 previously-dead approval features in any environment holding real
   data**: confirm with the functional team which of those groups actually have real users, and
   record the answer in `plan_status.md`. Re-activating a gate that no user is a member of would
   lock the corresponding action for everyone.
6. **Implementation is scheduled after Phase 3 step 2b.** Not implemented now.

Housekeeping, flagged not fixed: the supplement cites "decisions_log.md, section 7" (installments
toggle) and "section 8" (the five settings sections) as well. Neither exists here — this log has
only dated entries, and those two topics live in `implementation_plan.md` (Phase 3 and Phase 6
respectively). Those two citations should be repointed, or the corresponding decisions written
here as numbered sections, when convenient.

## 2026-11-04 — Phase 2b ACCEPTED as PARTIALLY COMPLETE; sales_cheques deferred to Phase 3

User accepted Phase 2b as partially complete and ruled: `sales_cheques` is deferred to Phase 3
together with the guard pattern, and is **not** to be created as an empty shell (matching the
reasoning already recorded below).

Phase 2b acceptance test result — **PASS**. `claude/logs/phase2b_cheques_only.log`:
`arkzayed_18_gt_cheque_management` installs completely standalone (exit 0, zero errors, zero
registry failures), with `sales_crm`, L0 `unit_inventory` and the L1 accounting bridge all
`uninstalled`. This satisfies S1's acceptance item "Install cheques without `sales_crm`: works".

Step-1 fix verified in the database, confirming the two locked-together faults are both cleared:
- `arkzayed_18_gt_cheque_management.account_cash_in_out_report` now exists
  (`ir.actions.report` id=381). It did not exist at all before the fix.
- `arkzayed_18_gt_cheque_management.model_account_move` now exists — the gating xmlid. Adding
  the `account.move` model file to that module is what allows it to be generated, which is what
  allows the report files to be registered.
- The report action resolves correctly: `model=account.move`, `report_type=qweb-pdf`, pointing at
  `...account_cash_in_out_template`.
- The relocated button view loaded as
  `arkzayed_18_gt_cheque_management.view_account_move_cash_in_out`.

Phase 3 acceptance criteria recorded in `plan_status.md`, in the user's ordering: (1) `sales_crm`
no longer hard-depends on the L1 cheque module; (2) one guard pattern established and applied to
S2 Mode B first, then to cheques; (3) then `sales_cheques` created and the `cheque.manage` plus
`account.payment` returned-cheque fields moved into it.

Also logged as backlog #29, explicitly **not** Phase 3 work: rename
`arkzayed_18_gt_cheque_management` to a generic name once the product is stable. It already meets
S1's "no sales references" requirement in substance; only the name is client-specific, and
renaming now would churn every `depends`, every qualified `ref=`, and the
`report.<module>.<name>` parser lookups while the product is still moving.

## 2026-11-04 — CORRECTION: "legacy repo" is custom/arkzayed, NOT the arkzayed_* modules in this repo

User clarified the zero-diff rule's scope, and verification confirms I had it wrong:

| Repo | git toplevel | Status |
|---|---|---|
| Legacy (zero-diff applies) | `/opt/odoo/odoo18/odoo/custom/arkzayed` | 0 changes — **never touched in this session** |
| Legacy (zero-diff applies) | `/opt/odoo/odoo18/odoo/custom/marketstandards` | 0 changes — never touched |
| New work (changes allowed) | `/opt/odoo/odoo18/odoo/custom/GenaricRealEstate` | where every edit happened |

These are **separate git repositories** (verified via `git rev-parse --show-toplevel` on each),
and both contain `arkzayed_18_*` module directories. Every edit I have made this session was to
the GenaricRealEstate copy — i.e. to new work, never to a legacy repo. The legacy repos have been
at zero diff the entire time, without any action on my part.

**Consequence: the Option A revert was unnecessary.** It was based on my misreading that the
`arkzayed_*`-named modules inside GenaricRealEstate were the protected legacy code. Having
confirmed otherwise, and with the user's explicit note that the patch "is for the new branch"
and that moving files in GenaricRealEstate is allowed, I re-applied
`claude/legacy_fixes_to_reapply.patch` to GenaricRealEstate. It applied cleanly (32 files). Both
legacy repos re-verified at 0 changes afterward.

This also resolves backlog **#28** (cost_distribution broken by the Option A revert) and restores
**#23–#27** (dangling imports, ~45 unqualified xmlid refs, construction security groups,
cost-allocation field placement).

## 2026-11-04 — Phase 2b step 1: cash-in-out statement moved out of the L1 bridge

The `env.ref` bug found during S3 verification turned out to be worse than an undeclared
dependency. The bridge's `account_move.py` called
`self.env.ref('arkzayed_18_gt_cheque_management.account_cash_in_out_report')`, and the target
xmlid **did not exist at all**: the two files defining it
(`report/journal_entries_report.xml`, `report/journal_entries_template.xml`) were absent from
that module's manifest `data`, so they were never loaded. The button was broken unconditionally,
not merely when the cheque module was uninstalled.

Root cause of *why* they were unregistered: the report action's
`binding_model_id` refs `arkzayed_18_gt_cheque_management.model_account_move`, and that module
had no `account.move` model file — so the xmlid could never be generated and registering the
file would have failed. The two problems were locked together.

Fix (all inside GenaricRealEstate, per the clarified scope rule) — moved the whole self-contained
cash-in-out feature from the L1 bridge into `arkzayed_18_gt_cheque_management`, where its report
action and QWeb template already live:
- `journal_type` field, `action_cash_in_out_statement()`, and the four helpers its template calls
  (`is_receipt`, `_get_arabic_amount`, `calculate_total_amount`, `get_currency_name`) →
  new `arkzayed_18_gt_cheque_management/models/account_move.py` (registered in that module's
  `models/__init__.py`). Verified those four helpers have no other caller anywhere in the repo.
- the `view_account_move_modi` button view → new
  `arkzayed_18_gt_cheque_management/views/account_move_views.xml` (renamed
  `view_account_move_cash_in_out`).
- registered `report/journal_entries_report.xml`, `report/journal_entries_template.xml` and the
  new view in that module's manifest. Adding the model file is what makes the
  `model_account_move` xmlid exist, which is what makes those report files registerable.
- dropped the now-unused `num2words` import from the bridge's `account_move.py`.

The L1 bridge now has no functional cheque reference at all. The single remaining match is the
string `('cheque', 'Cheque')` — a selection *value* of the generic `payment_method_type` field,
with no model reference; a payment can be made by cheque regardless of whether the cheque module
is installed, so it correctly stays.

## 2026-11-04 — **DECISION NEEDED**: Phase 2b step 2 (sales_cheques extraction) is blocked

Step 2 asked to move two "self-contained parts" into a new `sales_cheques` bridge. Verification
shows **neither is self-contained**, and unblocking either requires exactly the 72-`@api.depends`
rework that step 3 excludes from this phase.

**(a) The `cheque.manage` extension (1036 lines) cannot move.** All seven of its sales inverse
Many2one fields live in that one file: `eoi_id`, `installment_line_id`,
`maintenance_installment_line_id`, `sale_proposal_id`, `sale_reservation_id`,
`reservation_payment_id`, `eoi_payment_id` (the L1 cheque module defines none of them). Seven
One2many fields in `sales_crm` point at precisely those inverses — `eoi.cheque_manage_ids`,
`sale_proposal.cheque_ids`, `sale_reservation.cheque_manage_ids`,
`installment_lines.cheque_ids`, `maintenance_installment_lines.cheque_ids`,
`eoi_payment.cheque_ids`, `reservation_payment.cheque_ids`. Move the file and those seven lose
their inverse → `KeyError` at field setup → `sales_crm` will not load. This is the identical
failure mode hit six times during Phase 2. Moving the One2manys along with it does not help:
they are named by the 72 excluded `@api.depends`.

**(b) The `account.payment` returned-cheque fields cannot move either.** `account_payment.py:195`
declares `@api.depends('returned_cheque_ids.sale_proposal_id.contract_type')` on
`_compute_contract_type`, which computes a *sales* field that stays in `sales_crm`. The same
fields are also read inside three method bodies that stay: `_create_collection_journal_entry`
(lines 240–265), `action_post` (570–571), and `_prepare_move_line_default_vals` (663).

So Phase 2b delivers step 1 only. The substantive cheque extraction is gated on the same guard
pattern Phase 3/S2 must build, which matches the user's own instruction not to create two
separate refactors. `sales_cheques` was deliberately **not** created as an empty shell — an empty
module with no code would add a dependency edge and a manifest to maintain while delivering
nothing.

## 2026-11-04 — S3 (payment allocations) VERIFIED CLOSED; folded into Phase 2b per user decision

User instruction: verify first, then fold into Phase 2b; do not create a separate phase for S3.

**Step 1 — verification result: PASS.** Swept the whole L1 bridge
(`isky_18_realestate_developer_accounting`, all `.py` and `.xml`) for the string `allocation`.
Zero hits in code. The only two occurrences are prose in `__manifest__.py`'s own description,
documenting the Phase 2 move (`payment.allocation moved to ...sales_crm (L2)` and
`arkzayed.cost.allocation fields on account.move.line moved to arkzayed_cost_distribution`).
No `payment.allocation` reference, no `allocation_ids`, no allocation compute/validate method,
no allocation view fragment. S3's requirement "confirm no allocation logic remains in the bridge
that is sales-specific" is therefore satisfied by the Phase 2 work already done.

**Step 2 — nothing to move.** Since no sales-specific allocation logic remains, there is no S3
code to carry into Phase 2b. S3's remaining open item is its *test* requirement ("confirm L2
allocation works in Mode B, and add acceptance tests for each mode"), which cannot be done yet:
Mode B is defined by S2 and S2 is Phase 3 work. Recording that the allocation **placement** is
closed, while the Mode-A/Mode-B allocation **acceptance tests** remain Phase 3, where Mode B
first exists.

**Step 3 — no separate phase created.** S3 is closed as a placement question here.

Side finding from the same sweep (not allocation, so not an S3 item — carried into Phase 2b as
cheque work): the bridge's `models/account_move.py:51` does
`self.env.ref('arkzayed_18_gt_cheque_management.account_cash_in_out_report')`, and its
`views/account_move_views.xml` renders a "cash in/out statement" button on every cash journal
entry that calls it — but the bridge does **not** declare `arkzayed_18_gt_cheque_management` in
`depends`. Install the bridge without that legacy module and the button raises
`External ID not found` when clicked. This did not fail Phase 2's acceptance tests because
`env.ref` resolves at call time, not install time, so the latent bug is invisible to an install
check. It is cheque-coupled, so it belongs to Phase 2b (S1) rather than the backlog.

## 2026-11-04 — Phase 2 CLOSED; S1 moved to a new Phase 2b

Phase 2 scope was fixed by the user as exactly four criteria. All verified:

1. Bridge installs standalone — PASS. `phase2_bridge_test` DB: `isky_18_realestate_developer_accounting`,
   `isky_18_realestate_developer_unit_inventory`, `account`, `account_reports` all `installed`.
2. Zero dependency cycles — PASS. `dep_graph.py`, 26 local modules, no cycles.
3. Install **with** the bridge — PASS (criterion 1's DB is this configuration).
4. Install **without** the bridge — PASS. `phase2_no_bridge_test` DB: L0 `installed`, bridge
   `uninstalled`, and `account` itself `uninstalled` too (a stronger result than required — L0
   needs no accounting stack at all). Exit code 0, zero errors, registry loaded cleanly.
   Log: `claude/logs/phase2_no_bridge.log`.

Final bridge manifest: `['account', 'account_reports', 'isky_18_realestate_developer_unit_inventory']`
— i.e. `account` + L0 only, plus the Enterprise `account_reports` dependency that was always
required but never declared (backlog #7).

**S1 (cheque split) moved out of Phase 2 into a new Phase 2b**, per user instruction, to start
after Phase 2 closure. S5 in `implementation_plan_supplement.md` updated accordingly. S1 was NOT
implemented as part of Phase 2 closure. Its text is still missing from the supplement (that file
remains truncated at the top), so Phase 2b is blocked on receiving it — but that no longer blocks
Phase 2, which closed on its own scope.

Also flagged, not actioned: S5 still assigns part of S3 (payment allocation split) to
"Phase 2 (bridge)", which is now closed. Phase 2 did already move the whole allocation block off
the bridge into L2, so that portion may be satisfied, but S3's full text is unavailable in the
truncated file. Recorded as an OPEN QUESTION in the supplement rather than decided unilaterally.

## 2026-11-04 — Option A: all legacy edits reverted; legacy repos restored to zero diff

User set a hard scope rule (`plan_status.md`, rule 1): legacy repos (`arkzayed_*`,
`marketstandards`) stay untouched, and any fix that touched them must be re-applied in the new
branch instead. Presented the one genuine conflict (the four `arkzayed.cost.allocation` fields
Phase 2 required stripping from the L1 bridge, which I had re-homed into
`arkzayed_cost_distribution`) as A = revert and accept the breakage, B = keep the re-homing.
**User chose A.**

Reverted all 32 legacy changes from this session: 31 modified files restored, the deleted
`arkzayed_18_realestate_development/security/construction_progress_security.xml` restored, and
the added `arkzayed_cost_distribution/models/account_move_line.py` removed. Verified
`git status` shows **zero** legacy diff. Before reverting, the complete diff was saved to
`claude/legacy_fixes_to_reapply.patch` (793 lines, 32 files) so every fix is recoverable
verbatim for re-application in the new branch — the backlog prose alone was not sufficient for
that.

Attribution note, verified line by line: all 32 were mine from this session. The dirty-looking
`git status` captured at session start was a `staging`-vs-`developer_18` artifact (the branch was
switched early on), **not** third-party uncommitted legacy work. So the revert was precise with
no risk of discarding someone else's changes.

Post-revert verification:
- `dep_graph.py`: still zero cycles. The Phase 2 cycle break does not depend on any legacy edit -
  it came from the bridge dropping its own upward edges, which is an isky-module change.
- Bridge manifest is now exactly `['account', 'account_reports', 'isky_18_realestate_developer_unit_inventory']`.
- No `isky_*` module is affected by the revert.

Accepted, precisely-scoped breakage (tracked as backlog #28): `arkzayed_cost_distribution` no
longer installs. Its `views/cost_distribution_views.xml` menuitem points at
`isky_18_realestate_developer_accounting.action_pending_cost_distribution`, which Phase 2
removed from the bridge, and `wizard/distribution_wizard.py` references the now-undefined
`move_line_id.remaining_amount` / `distribution_state`. Tolerated under scope rule 3 (the legacy
stack is a separate verification gate, not a Phase 2 acceptance criterion) and because
`arkzayed_cost_distribution` is slated for replacement by an `isky_*` module anyway.

## 2026-11-04 — Autonomous execution mode for Phases 2-9

User authorized autonomous, unattended execution of all remaining phases (2 through 9) in one
continuous session while away from the laptop. Operating rule for this stretch: a critical design
issue or bug that would normally warrant stopping to ask does NOT block progress - instead, make the
best-supported call, flag it clearly in this log under a `**NEEDS REVIEW**` marker with the
reasoning and alternatives considered, and keep going. Nothing is to be silently decided; everything
flagged this way must be revisited with the user before being considered final. Commits remain held
until the user explicitly asks (per the earlier commit-strategy override), regardless of how many
phases complete in the meantime. The final, full-stack post-all-phases test DB is named
`real_estate_developer_full_testing` (phase-by-phase testing along the way still uses fresh
throwaway DBs, per the existing testing-environment decision).

## 2026-11-04 — **NEEDS REVIEW**: Phase 2 accounting-bridge split (much larger than the plan text implied)

Phase 2's literal bullets ("remove fields pointing to sale_proposal_id/penalty_id/...",
"remove fields pointing to arkzayed.cost.allocation") undersold the real scope. Auditing every
relational field and every `self.env[...]` call in the bridge's `account_move.py` and
`account_payment.py` (1040 lines) turned up a THREE-layer entanglement, not a handful of fields:
L1 code was directly calling into L2 (`sale.proposal`, `eoi.eoi`, `real.estate.sale.reservation`,
`installment.lines`, `maintenance.installment.lines`, `loan.line`, `revenue.share2`,
`installment.penalty`, `reservation.payment`, `eoi.payment`, `payment.allocation`, and
`sales_crm`'s own `cheque.manage`-extension fields `is_returned_cheque`/`returned_cheque_ids`)
AND into L3 (`broker.claim`, via `action_post`'s `update_broker_claim()` and a whole
`action_draft()` override). None of this was declared in the bridge's manifest; it only
surfaced by tracing every field/method, the same way Phase 1's five bugs did, just at far
greater scale (a method-by-method audit, not isolated fields).

**What was done** (verbatim code relocation, no logic rewritten - behavior preserved):
- `account.move`: `sale_proposal_id`, `penalty_id`, `sale_reservation_id`, `line_id`,
  `installment_line_id`, `installment_lines_line_id`, `revenue_share_id`, `revenue_share_type`
  moved to a new `isky_18_realestate_developer_sales_crm/models/core/account_move_crm_ext.py`.
- `account.move.line`'s cost-allocation cluster (`allocation_ids`, `distribution_state`,
  `distributed_amount`, `remaining_amount`, `_compute_distributed_amount`,
  `action_open_cost_distribution_wizard`) moved to a new
  `arkzayed_cost_distribution/models/account_move_line.py` - this is where the bridge's own
  manifest docstring said they lived before an earlier consolidation, so this reverts that one
  piece rather than inventing new arkzayed functionality. The matching view
  (`view_pending_cost_distribution_list` / `action_pending_cost_distribution`) moved into
  `arkzayed_cost_distribution/views/cost_distribution_views.xml`, next to the menu item that
  already referenced it by a fully-qualified xmlid.
- `account.payment`: the large majority of the 1040-line file (eoi/proposal/reservation/unit
  resolution in `create()`, all `_onchange_*`, `_validate_allocations_on_confirm`,
  `_compute_available_allocations`/`_compute_unallocated`/`_get_amount_company_currency`,
  `_compute_contract_type`, `_compute_unit_id`, `button_draft`, the collection-journal-entry
  cluster including `_create_collection_journal_entry` (still has its pre-existing hardcoded
  GIS/OAYA account-param logic untouched - that is Phase 7's job, not this one's), and the
  bulk of `action_post`) moved into the EXISTING
  `isky_18_realestate_developer_sales_crm/models/core/account_payment.py` (which already held
  the cheque-return fields this code was using). `action_post`'s `broker.claim`-only tail and
  all of `action_draft` moved to a NEW
  `isky_18_realestate_developer_commission/models/core/account_payment_commission_ext.py`,
  chained via `super()` on top of sales_crm's override (so execution order is unchanged:
  bridge's own down-payment check → core post → sales_crm's commission/broker-claim-create
  logic → commission module's broker.claim-paid update). `_prepare_move_line_default_vals`
  was split the same way: the bridge kept the overseas/down-payment account-selection logic,
  sales_crm added a new override that calls `super()` then layers the returned-cheque
  notes-receivable swap on top - same reasoning, since that method mixed an L1-only concern
  with an L2-only field access in one method body that can't be cut in half any other way.
  Matching view xpaths split the same way into
  `isky_18_realestate_developer_sales_crm/views/account_{move,payment}_views.xml` (first views
  that module has ever had - its manifest `data` was empty before this).
- Manifests: the bridge now depends on `['account', 'isky_18_realestate_developer_unit_inventory']`
  only. `arkzayed_cost_distribution` dropped `arkzayed_18_realestate_development` (confirmed
  vestigial - none of its own files reference anything from that module, only
  `real.estate.unit`/`building`/`zone` which now live in L0) and gained
  `isky_18_realestate_developer_unit_inventory` explicitly instead of getting it transitively.
  `dep_graph.py` now reports zero cycles. `arkzayed_18_realestate_development`'s own manifest
  was deliberately left untouched - once the bridge no longer points back at it, its
  (one-directional) dependency on the bridge is no longer part of any cycle, so the plan's own
  conditional wording ("remove it... if it is part of the cycle") no longer applies.

**Why this is flagged NEEDS REVIEW rather than just logged as done**: this is production
payment-posting and commission-trigger code running across many real client databases (per
`psql -l` listing many `*_live*`/`*_main*` databases). The relocation was done verbatim
(same method bodies, same call order via super() chaining) specifically to minimize behavioral
risk, and `dep_graph.py` plus install tests (see below) confirm it loads - but this is NOT the
same confidence level as Phase 1's small, isolated fixes. Please review the `action_post`/
`action_draft`/`_prepare_move_line_default_vals` three-way split in particular before trusting
this in production - re-read the method bodies in
`isky_18_realestate_developer_accounting/models/account_payment.py`,
`isky_18_realestate_developer_sales_crm/models/core/account_payment.py`, and
`isky_18_realestate_developer_commission/models/core/account_payment_commission_ext.py`
side by side against what git history shows the original single file did.

**Also found, fixed differently**: the bridge's own `res_config_settings_views.xml` inherited
`arkzayed_18_realestate_development.res_config_settings_view_form_rs` (that module's own
`app_settings_block`/`data-key="real_estate_bits"` settings-tab container) to nest its account
fields inside it - another hard dependency on the module Phase 2 is removing. Changed it to
inherit `base.res_config_settings_view_form` directly with its own
`data-key="real_estate_accounting"` container. When both modules are installed together this
now renders as two separate "Real Estate"-ish settings tabs instead of one merged tab - a minor
cosmetic duplication, acceptable for now since Phase 6 (Settings) is explicitly where all of
this gets consolidated into the plan's five final sections; no attempt made to merge them here.

**Known non-fatal limitation, left as-is**: `account_payment_views.xml`'s "CFO Approve"/"Deputy
CEO Approve" buttons are gated by `groups="arkzayed_18_realestate_development.payment_cfo_group"`
/`payment_deputy_cfo_group`. With the bridge installed but that module absent, Odoo logs a
warning and treats the group as resolving to nobody - the buttons become permanently hidden
rather than the install failing. Judged acceptable degraded behavior for an explicitly optional
module (every real deployment installs the full stack together, where the groups do exist);
flagging in case that assumption turns out wrong.

**Also found and fixed**: `models/account_cash_flow.py` in the bridge overrides
`account.cash.flow.report.handler`, confirmed via standalone install test to be undeclared -
that model is defined in the Enterprise `account_reports` module (depends on `accountant`,
license OEEL-1), not in community `account`. This bug predates Phase 2 entirely; it only
surfaced now because this was the first time the bridge was ever installed in isolation rather
than always alongside `arkzayed_18_realestate_development`'s huge dependency list (which pulls
in `accountant` too, masking it). Added `account_reports` to the bridge's `depends`. Using an
Enterprise-licensed dependency is consistent with the rest of this product -
`arkzayed_18_realestate_development` already depends on `accountant` directly.



Initial implementation plan committed as `claude/implementation_plan.md`. No decisions have deviated from it yet.

Note on branch naming: the plan's Prerequisites (section 0) refer to a `developer` branch; the actual repo remote is `developer_18` (checked out locally as `developer_18`). Treat `developer_18` as the `developer` branch referenced throughout the plan unless corrected here.

## 2026-11-04 — Testing environment

Odoo 18 instance already exists. For each phase's acceptance testing, a new/fresh Odoo DB is created rather than reusing a shared one.

## 2026-11-04 — installment.mixin relocated from L2 to L0

Found during Phase 1 install testing: `real.estate.unit` (L0, `isky_18_realestate_developer_unit_inventory`)
inherited `installment.mixin`, but that mixin was actually *defined* in `isky_18_realestate_developer_sales_crm`
(L2) — L0 module could not install standalone, contradicting the Phase 1 rule "L0 has no dependency on sales
or accounting" and the module's own manifest claim of zero dependency on other levels.

The mixin itself (`installment_mixin.py`) is dependency-free pure logic (installment rounding math,
one `ir.config_parameter` read) with no coupling to any sales model, so it was moved down to L0
(`isky_18_realestate_developer_unit_inventory/models/config/installment_mixin.py`) rather than reworked.
L2's own consumers (`sale_reservation.py`, `sale_proposal.py`) are unaffected: `sales_crm` already depends
on `isky_18_realestate_developer_unit_inventory`, so they still resolve `'installment.mixin'` by name.

## 2026-11-04 — models/__init__.py import order: config before core

Found while testing the `installment.mixin` relocation above: Odoo builds a module's models in
*import order*, and resolving a class's `_inherit` list requires the named parent model to already
be *built* (not just imported) — `real.estate.unit` (in `core/`) inherits `installment.mixin` (in
`config/`), but `unit_inventory/models/__init__.py` imported `core` before `config`, so the parent
wasn't built yet and the whole module failed to load with "non-existing model 'installment.mixin'".
Fixed by swapping the import order to `config` then `core`. Confirmed safe: every `_inherit` inside
`config/` targets a base Odoo model (res.country, res.company, product.product/template), never a
`core/` model, so nothing in `config/` depends on `core/` loading first.

## 2026-11-04 — Removed orphaned sequence.mixin override from L0

Found during the same install-testing pass: `models/core/sequence.py` defined a class (nonsensical
name `ssdsdsdd`) that `_inherit`ed `sequence.mixin` — which is defined in the `account` module, not
declared as a dependency. Same class of bug as the `installment.mixin` one above, but this one was
dead code: nothing else in the module referenced `_sequence_field`/`_sequence_date_field`/
`sequence.mixin`, and the method body called `_(...)` without importing `_`, so it would have raised
NameError if ever triggered. Deleted rather than relocated (not legitimate reusable logic, unlike
installment.mixin) and removed its import from `models/core/__init__.py`. Swept the rest of the
module's `_inherit` targets afterward - all resolve to `mail`/`product`/`base` (declared
dependencies) or to this module's own new mixins.

## 2026-11-04 — archive.place's sale.proposal link moved to L2

Third instance of the same bug class found during install testing: `archive.place` (L0, config)
declared `sale_proposal_ids = One2many('sale.proposal', 'archive_place_id', ...)` plus a dependent
`contract_count` and `action_view_contracts()` - but `sale.proposal` is an L2 (sales_crm) model, and
its `archive_place_id` Many2one (the actual inverse) is defined in
`isky_18_realestate_developer_sales_crm/models/core/sale_proposal.py`. L0 couldn't install standalone
("KeyError: archive_place_id" during field setup).

Fix followed the plan's own Phase 2 pattern for this exact situation ("move sales-related fields to
L2 as _inherit"): removed the One2many/contract_count/action from `archive_place.py` (L0) and added
them back via a new `_inherit` extension,
`isky_18_realestate_developer_sales_crm/models/core/archive_place_ext.py` (L2), next to where
`sale_proposal.archive_place_id` already lives. No XML view in any L0-owned or L0-loaded module
referenced the moved fields (checked: only legacy `arkzayed_18_realestate_development` views did,
which already depend on L2 functionality anyway).

## 2026-11-04 — down.payment.increase / installment.template / maintenance.template moved to L0

Fourth and largest instance of the same bug class: `real.estate.unit` (L0) has long-standing Many2one
fields to `down.payment.increase`, `installment.template`, and `maintenance.template` - all three were
defined in `sales_crm` (L2), undeclared. Unlike the payment-plan *business logic* that reads these
fields (hundreds of lines in `real_estate_unit.py` - `_get_installments_grouped_by_date`,
`_get_unit_offer_plan_schedule_for_template`, etc., which is genuinely Phase 3 (Sales/Installments)
territory and was deliberately left untouched), these three are plain config/master-data models with
no actual coupling to CRM/sale/hr/project - `down_payment_increase.py` already imported L0's own
`unit_type_selection`, and both `installment.template`/`maintenance.template` only reference
`realestate.project` (L0) and `res.company` (base). `price.plan.line` (already in L0) also has a
Many2one to `down.payment.increase`, confirming it was misplaced, not that L0 was reaching too far.

Moved the three model files to `isky_18_realestate_developer_unit_inventory/models/config/`,
fixed `down_payment_increase.py`'s absolute cross-addon import to a relative one, added
`ir.model.access.csv` rows for them (sales_crm's own manifest has an empty `data: []`, so there
were no existing access rows or views anywhere to break). The payment-plan logic in
`real_estate_unit.py` that reads these fields is untouched and keeps working identically either way.

**Finding for future phases**: a manifest-level dependency-graph check (`dep_graph.py`) only catches
declared `depends` cycles - it did not catch any of these four field/model-level reaches into an
undeclared module, which only surface at actual install time. Worth a repo-wide sweep of Many2one/
Many2many/One2many comodel targets per module (grep for `fields.(Many2one|Many2many|One2many)` and
cross-check each comodel against that module's own `_name`s + its declared `depends`) before
trusting any module's manifest to reflect its real coupling - especially before Phase 2 touches the
accounting bridge, which is denser and older than this one.

## 2026-11-04 — res.users.realestate_project_ids moved to L0

Fifth instance: `isky_18_realestate_developer_unit_inventory/security/security.xml` (L0's own
record rules, e.g. `user_real_state_project_assigned_rule`) filters on
`user.realestate_project_ids.ids`, but that field was only defined in `sales_crm`
(`models/core/res_users.py`) - L0's own security rules failed to load standalone. Split the file:
`realestate_project_ids` (Many2many to `realestate.project`, an L0 model, with no CRM coupling)
moved to a new `isky_18_realestate_developer_unit_inventory/models/config/res_users.py`; the
genuinely L2 field in that same file, `job_level_id` (job/commission-hierarchy concept), stayed in
`sales_crm`. `sales_crm`'s own consumer of the moved field (`loan_line.py`, plain attribute access,
no `_inherit`) is unaffected since it still resolves via the dependency chain.

## 2026-11-04 — Construction module's security groups moved from legacy module (found during
Phase 2 full-stack install test, fixed now rather than deferred to Phase 5)

Installing everything together for the first time (to validate the Phase 2 payment/move split
end to end) surfaced an unrelated pre-existing bug: `isky_18_realestate_developer_construction`
(L4)'s own `ir.model.access.csv` references three security groups
(`group_vendor_commitment_user`, `group_progress_engineer`, `group_progress_manager`) that were
defined in `arkzayed_18_realestate_development`, which construction's manifest does not (and per
Phase 5's own rule - "Construction depends on L0 and L1 only" - should not) depend on. All three
groups gate construction's own models (`vendor_commitment.py`,
`arkzayed.construction.progress`), confirming they were simply misplaced, not a case of L4
genuinely needing the legacy module.

Moved all three groups (plus their category records and the admin noupdate-assignment) into a
new `isky_18_realestate_developer_construction/security/security.xml`, loaded before that
module's access CSV. Updated the CSV's group references to the now-local xmlids, deleted the
now-empty `arkzayed_18_realestate_development/security/construction_progress_security.xml` and
removed it from that module's manifest, and requalified the one remaining cross-reference
(`views/menus.xml`'s `groups=` attribute) to point at the new location. Swept the rest of the
`isky_18_realestate_developer_*` tree for any other `arkzayed_18_realestate_development.group_*`
reference - none found. This happens to satisfy a piece of Phase 5 early; Phase 5 itself still
needs its own full standalone-install verification pass when that phase is reached.

## 2026-11-04 — Correction: arkzayed_cost_distribution needs arkzayed_18_realestate_development after all (for views)

The full-stack install test caught a gap in my own Phase 2 cycle-fix: I'd dropped
`arkzayed_18_realestate_development` from `arkzayed_cost_distribution`'s manifest after
checking only its *Python model* files for real coupling (confirmed clean). I didn't check its
*view* files. `views/real_estate_unit_views.xml` and `views/hierarchy_views.xml` each
`inherit_id` a form view (`view_real_estate_unit_form`, `view_real_estate_building_form`,
`zone_form`) that only exists in `arkzayed_18_realestate_development` - L0
(`isky_18_realestate_developer_unit_inventory`) has no form views of its own yet (a separate,
already-known gap, not something Phase 1 or 2 was asked to fill). Re-added the dependency, with
a comment explaining it's view-only and doesn't reintroduce the cycle (confirmed via
`dep_graph.py`: still zero cycles) since the cycle was broken by removing the accounting
bridge's *upward* edges, not this one, one-directional, downward edge. Lesson for future phases:
when auditing a module's real coupling, check its view/`data` files for `inherit_id` and
`ref=` targets, not just its Python files for field/model references - same blind spot as the
settings-view and account_payment-view issues found earlier in this same phase.

## 2026-11-04 — Fixed table-name-too-long bug in sales_crm's report parser (unrelated to Phase 2)

Full-stack install hit `ValidationError: Table name 'report_arkzayed_18_realestate_developer_crm_report_sales_achievement'
is too long`. Cause: `isky_18_realestate_developer_sales_crm/wizard/sales_achievement_report.py`
declares `class ReportSalesAchievement(models.AbstractModel): _name =
'report.arkzayed_18_realestate_developer_crm.report_sales_achievement'` - the old-style QWeb
report-parser naming convention, kept as-is (still referencing the legacy module's name) from
whenever this class was moved into sales_crm as part of that "absorption" its own manifest
docstring mentions. The dotted `_name` must stay exactly this value (it's what Odoo uses to find
the parser for the `ir.actions.report` whose `report_name` field, and the `<template>` xmlid it
points to, both still live - correctly - in `arkzayed_18_realestate_developer_crm`), but Odoo
auto-derives the SQL table name from it by replacing dots with underscores, and that's 68
characters - over PostgreSQL's 63-char identifier limit. Pure pre-existing bug, unrelated to
anything architectural in this refactor; it only surfaced now because this was the first time
this report's model was ever actually registered in a real database.

Fixed with an explicit `_table = 'report_sales_achievement_parser'` override - zero behavior
change, no legacy file touched, the `report.<report_name>` lookup convention stays intact since
`_name` itself is unchanged.

## 2026-11-04 — EOI commission hierarchy moved from L2 to L3 (and a duplicate dead copy removed)

Full-stack install hit `KeyError: 'eoi_id'` building `eoi.eoi.commission_ids` (One2many to
`realestate.commission`, defined in `isky_18_realestate_developer_commission`, L3) - sales_crm
(L2) must not depend on L3, and didn't declare it, so the inverse field wasn't resolvable.
While fixing this, found the field had **two** separate `compute_person_hierarchy`
implementations in sales_crm itself - `models/core/eoi.py`'s own version, and
`eoi_commission_hierarchy_ext.py`'s (slightly different: 4 job levels incl. "Sales Sector
Manager" vs 3, and `team_id.sales_manager_id`/`operation_id` vs `team_id.user_id`). Since
`eoi_commission_hierarchy_ext` is imported after `eoi` in `core/__init__.py`, its version always
won outright (no `super()` chaining between them) - the one in `eoi.py` was provably dead code.
Confirms this module's own manifest docstring: "the old CRM module had its own _inherit shims
on sale.proposal/sale.reservation/eoi.eoi/crm.lead duplicating the same 'commission hierarchy
builder' algorithm. Not deduplicated yet - that's Level 3 (Commissions & Broker) work."

Removed the dead copy entirely (field + method) from `eoi.py`. Moved the live copy
(`eoi_commission_hierarchy_ext.py`, field + method) to a same-named file in
`isky_18_realestate_developer_commission/models/core/`, dropping its stray debug `print()`
along the way. No behavior change otherwise - same job-level logic, same field.

**Deferred to Phase 4, not fixed now**: the same sweep found `sale_proposal.py` (L2) also holds
plain Many2one fields to L3 models (`broker_contract_id`, `broker_claim_id`,
`ambassador_claim_id` → `broker.contract`/`broker.claim`; `res_users.py`/`res_user.py`'s
`job_level_id` → `job.level`). Unlike the EOI case these are Many2one, not One2many - a missing
comodel there only warns (field just reads as empty) rather than crashing field setup, so they
don't block this install. But they're the same L2→L3 layering issue, deeply woven through
`sale_proposal.py`'s own commission-trigger logic (`_check_and_create_broker_claim`,
`_auto_create_commission_achievements`, `_is_commission_eligible`, all called from the payment
flow moved earlier in this phase). Phase 4 ("Broker commission stays inside L3... for now",
"one hierarchy engine... remove the 4 existing implementations") is explicitly where this
belongs - untangling it now, mid-Phase-2, on a 3000+ line file would be exactly the kind of
hasty large-surface change this flagging process exists to avoid.

## 2026-11-04 — Same L2→L3 commission-hierarchy bug found and fixed on reservation AND contract too

The EOI fix above was one of (at least) three. The exact same pattern recurred on
`real.estate.sale.reservation` (`KeyError: 'sale_reservation_id'` - `commission_ids` One2many
to `realestate.commission`) and, found proactively before it could crash a install too,
`sale.proposal`'s own `commission_ids` (same target, inverse `sale_proposal_id`). Both had the
identical shape as the EOI case: a dead, always-shadowed copy of the hierarchy-building logic
left in sales_crm's main file, and the live copy (in `sale_reservation_crm_ext.py` /
`sale_proposal_crm_ext.py`, imported later and winning by MRO) also in sales_crm instead of
commission. Fixed the same way: dead copies deleted outright; live copies' field +
`_build_commission_hierarchy` method moved into new
`isky_18_realestate_developer_commission/models/core/{sale_reservation,sale_proposal}_crm_ext.py`
files. `sale_proposal_crm_ext.py`'s `create()`/`write()` overrides and both sale_proposal.py
onchange methods stayed in L2 - they only call `_build_commission_hierarchy()` by name, never
reference the L3 model directly, so they're safe to leave (same reasoning as EOI's
`_onchange_sales_ids`).

Confirmed `crm_lead.py`'s own `commission_ids` (→ `commission.commission`, not
`realestate.commission`) is NOT this bug - that model is defined within sales_crm itself
(`persons_commission.py`), so it's same-module and carries no crash risk. Whether
`commission.commission` and `realestate.commission` are actually the same concept under two
names is exactly the kind of question Phase 4 ("remove the 4 existing implementations") should
answer - not touched here.

**Also confirmed, to bound the remaining risk**: the broader `sale_proposal.py` broker/commission
coupling flagged earlier (plain Many2one fields to `broker.contract`/`broker.claim`, and runtime
`self.env['broker.claim']`/`self.env['realestate.commission.achievement']` calls inside
`_auto_create_commission_achievements` etc.) does NOT carry this same install-crashing risk -
only a *declared relational field* with a cross-layer inverse (One2many, or `_inherit` itself)
is checked at field-setup time; a plain Many2one to an not-yet-loaded model only warns, and a
runtime `self.env[model].create(...)` call is resolved against the fully-built registry when it
executes, not at field-setup time. That distinction is what let Phase 2 leave the rest of that
coupling for Phase 4 with confidence it won't block any install.

## 2026-11-04 — Three more plain L2→L3 One2many fields on sale.proposal, same fix

After the hierarchy-builder duplicates, a full sweep of every One2many in `sale_proposal.py`
turned up three more straightforward (no duplicate-method complexity this time) cross-layer
fields: `commission_achievement_ids` (→ `realestate.commission.achievement`),
`non_sales_claim_ids` and `all_commission_claim_ids` (→ `broker.claim`), all L3. Moved the three
field declarations into `isky_18_realestate_developer_commission/models/core/sale_proposal_crm_ext.py`
(alongside `commission_ids` from the previous fix); left `commission_achievement_count` and
`non_sales_claim_count` (plain Integers, compute just does `len()` on the moved fields) in L2 -
reading a field via `self.x` works regardless of which module defines it, so no need to move
those too. Swept every other One2many across `sale_proposal.py`, `sale_reservation.py`, and
`eoi.py` against sales_crm's own model set to confirm nothing else is affected - all clean.

## 2026-11-04 — **NEEDS REVIEW**: fixed a pre-existing fresh-install crash unrelated to layering

Confirmed via an isolated test (installing just `isky_18_realestate_developer_sales_crm` alone,
with no other arkzayed siblings) that this crash is NOT a Phase 2 layering issue, and predates
this session entirely - it's the first time this module has ever been installed into a
genuinely fresh database in this environment. Root cause: several fields use Odoo's own
standard idiom `default=lambda self: _('New')` (the same pattern Odoo core uses for e.g.
`sale.order.name`). On a *fresh* install, `_()`'s language resolution reads `res.users`/
`res.partner`, and if that read happens to run (via `_init_column`'s backfill of a *different*
model's new column) before `res.partner`'s own new columns from this same module have been
schema-synced, it crashes with "column res_partner.<field> does not exist" - here, `is_agent`.
This is an ordering race between unrelated models' schema-sync steps within one module's
install, not anything to do with sales/accounting/commission layering.

Fixed by dropping the translation wrapper on 10 occurrences across
`isky_18_realestate_developer_sales_crm` (`crm_lead.py` x2, `eoi.py`, `permission_request.py`,
`sale_reservation.py`, `sale_request.py`, `sale_proposal.py`) and
`isky_18_realestate_developer_commission` (`broker_contract.py`, `broker_claim.py`,
`broker_visit.py`): `default=lambda self: _('New')` → `default='New'`. Every one of these is a
placeholder value immediately overwritten by a real sequence number once the record is saved,
so the one-time loss of translation on that placeholder is inconsequential. Re-verified in
isolation that this specific crash is gone (see test log referenced below).

**Flagged for review**: one more instance of the exact same pattern exists in
`arkzayed_18_realestate_development/models/real_estate_lease_contratct.py` - left untouched
since it's legacy code, but if the full-stack install still crashes the same way afterward,
that file is now the known remaining source and the same trivial fix applies. This is purely a
fragile-timing bug, not a design question, so "flag and proceed" here means: fixed everywhere I
can, documented the one spot I can't touch without explicit permission to edit legacy code.

## 2026-11-04 — sales_crm cannot install 100% standalone, by design, until Phase 4

After the `is_agent` fix, testing `isky_18_realestate_developer_sales_crm` alone (no other
module) hit a different crash: `ValueError: Wrong @depends on 'None' (compute method of field
eoi.eoi.sales_ids). Dependency field 'is_sales_person' not found in model _unknown.` Traced to
`eoi.py`'s `sales_ids` Many2many, whose static `domain=[...('job_level_id.is_sales_person', '=',
True)...]` makes Odoo register an implicit cache-invalidation dependency through
`res.users.job_level_id` (comodel `job.level`) to `job.level.is_sales_person` - and since
`job.level` lives in `isky_18_realestate_developer_commission` (L3), which isn't installed when
testing sales_crm alone, the comodel resolves to Odoo's `_unknown` placeholder and the path walk
fails hard (a plain Many2one to an unbuilt model only warns; a domain path trying to walk
*through* it does not).

This is not a new bug - it's the already-logged, Phase-4-deferred L2→L3 `job_level_id` coupling
surfacing through a different mechanism (implicit domain dependency instead of a One2many
inverse). It does not affect the actual target test (the full product stack, where commission
*is* installed and `job.level`/`is_sales_person` resolve fine) - confirmed by re-running that
full-stack test directly rather than chasing a standalone-sales_crm scenario that Phase 2 never
claimed to support. Noting here only so a future "why doesn't sales_crm install alone" question
has an answer: it's expected until Phase 4 resolves the broker/commission layering, not a Phase
2 regression.

## 2026-11-04 — Correction: the job_level_id domain crash DOES block the real full-stack install too

The previous entry's conclusion was wrong - re-running the actual full-stack install hit the
exact same `ValueError: Wrong @depends on 'None' (compute method of field eoi.eoi.sales_ids)...
'is_sales_person' not found in model _unknown` even with commission installed. Reason: Odoo
loads modules in dependency order, and `isky_18_realestate_developer_commission` *depends on*
`isky_18_realestate_developer_sales_crm` - so sales_crm's own models always finish loading
(including the implicit-dependency registration for `sales_ids`' domain) before commission's
`job.level` is built, regardless of what's in the overall install list. The crash isn't a
test-isolation artifact; it was always going to happen on any first-ever fresh install that
includes sales_crm, in this dependency order, full stop.

Fixed for real this time: removed the `domain=[...job_level_id.is_sales_person/is_directory/
is_sales_manager/is_sales_sector_manager...]` clauses from `user_id` and `sales_ids` on `eoi.py`,
`sale_proposal.py`, and `sale_reservation.py` (6 fields total, 3 files). These domains were pure
UI narrowing (restricting which users show up in a salesperson-picker dropdown) - removing them
loses that narrowing (the dropdown now offers more users than ideal) but changes no stored data
and no business logic; a correct fix needs the job_level_id relationship properly resolved,
which is Phase 4's job once L2/L3 broker-commission layering gets its real treatment.

`crm_team_hierarchy.py` has three *Many2one* fields with the same style of domain
(`director_id`, `operation_id`, `sales_manager_id` → `job_level_id.is_*`) - left untouched since
the observed crash was specific to a *Many2many* field's domain (confirmed `user_id`, a
Many2one with the identical domain, never crashed on its own); if these turn out to have the
same problem, the identical fix applies.

## 2026-11-04 — Follow-up: the count fields reading a moved L3 field needed to move with it

Immediate next crash after the domain fix: `commission_achievement_count`'s own
`@api.depends('commission_achievement_ids')` failed the same way (`Dependency field
'commission_achievement_ids' not found in model sale.proposal`) - I'd moved the One2many field
itself to L3 in an earlier fix but left its two dependent count fields
(`commission_achievement_count`, `non_sales_claim_count`) and their compute methods behind in
L2, reasoning (wrongly - noted and corrected here) that "they just do len() so they're
unaffected." They're not: `@api.depends()` resolution happens while *this* module
(sales_crm) is loading, before commission's `_inherit` adds the field, so any depends naming it
fails regardless of which method body merely reads it at runtime versus declares a compile-time
dependency on it. Moved both count fields + their computes into
`isky_18_realestate_developer_commission/models/core/sale_proposal_crm_ext.py` alongside the
field they depend on. Checked eoi.py/sale_reservation.py for the same pattern on their own
moved `commission_ids` - clean, no other compute depends on it.

## 2026-11-04 — **NEEDS REVIEW** (touches legacy files): fixed a dangling import predating this session entirely

Full-stack install got past sales_crm, commission, and construction cleanly, then hit
`CRITICAL ... Couldn't load module arkzayed_18_realestate_development` with no traceback in the
log (Odoo logs that line without `exc_info`). Reproduced directly via
`odoo.modules.module.load_openerp_module()` to get the real error:
`arkzayed_18_realestate_development/wizard/broker_statement_wizard.py` and
`arkzayed_trace_commission/wizard/trace_commission.py` both do
`from odoo.addons.arkzayed_18_realestate_development.models.sale_proposal import
COMMISSION_EXCLUDED_STATES` - but `arkzayed_18_realestate_development/models/sale_proposal.py`
does not exist (confirmed via `find`). This predates Phase 2 and this session entirely: the
plan's own earlier notes already described `sale.proposal`'s model code as having been
"absorbed" into `isky_18_realestate_developer_sales_crm` well before this refactor started:
these two wizard files' imports were simply never updated when that absorption happened, so
neither file - and therefore neither module - has ever successfully imported since. Not a
layering question, not a design choice: a flat-out broken reference to a file that doesn't
exist, zero functional ambiguity about where the fix points.

Fixed both imports to point at `COMMISSION_EXCLUDED_STATES`'s actual current location
(`odoo.addons.isky_18_realestate_developer_sales_crm.models.core.sale_proposal`), confirmed
module-level there and confirmed both files' own modules already depend (directly or
transitively) on sales_crm, so the import now resolves. Verified via a direct
`load_openerp_module()` reproduction before re-running the full install.

**Flagged NEEDS REVIEW** per the standing rule for anything touching `arkzayed_*` files: this is
a one-line corrected import path with zero logic change in two legacy files, done because
nothing else makes those two modules importable at all (not a case of modifying legacy
business logic) - but it's still an edit to legacy-owned files, so flagging rather than treating
as self-evidently fine.

## 2026-11-04 — **NEEDS REVIEW** (touches legacy files): qualified ~45 unqualified cross-module `ref=` xmlids

Full-stack install next hit `ValueError: External ID not found in the system:
arkzayed_18_realestate_development.model_crm_team` loading that module's `security.xml` - an
unqualified `ref="model_crm_team"` that only resolves when the target model happens to be owned
by the current module (Odoo looks in the current module's own xmlids for an unqualified ref);
`crm.team` belongs to core `crm`/`sales_team`, so it doesn't. Confirmed the correct qualified
form (`crm.model_crm_team`) empirically: `arkzayed_18_realestate_developer_crm`'s own
`security/ir_rules.xml` already uses it successfully elsewhere in this codebase.

Given one instance existed, swept the whole of `arkzayed_18_realestate_development` and
`arkzayed_18_realestate_developer_crm` (the other legacy module in this install list) for the
same `ref="model_<x>"` pattern and qualified every one whose target model lives outside the
referencing module: `project.model_project_{project,task}`, `crm.model_crm_lead`, and roughly a
dozen distinct models now correctly prefixed with
`isky_18_realestate_developer_sales_crm.model_*` (eoi_eoi, sale_proposal,
real_estate_sale_reservation, maintenance_template, customer_ownership, installment_template,
maintenance_config, maintenance_installment_lines, installment_lines, revenue_share2,
broker_unit, permission_request, crm_meeting_report) and
`isky_18_realestate_developer_unit_inventory.model_real_estate_unit` - about 45 occurrences
total across `security/`, `views/`, `data/`, and `reports/` in both modules. Left the one
genuinely same-module unqualified ref alone (`arkzayed_cost_distribution`'s own
`model_arkzayed_cost_distribution`, in its own `report_cost_distribution.xml` - that's the
normal case that already works). Validated every edited file is still well-formed XML.

**Flagged NEEDS REVIEW**: same reasoning as the dangling-import fix above - these are
mechanical reference corrections (same target model, just properly qualified) in legacy-owned
files, done because the alternative is those modules never loading at all; not a design choice,
but still an edit to files outside this refactor's own modules, so flagging rather than treating
as self-evidently fine. Given the volume, worth a second pair of eyes on the full diff for these
two files in particular.

## 2026-11-04 — Commit strategy override

Plan section 1 said "one commit per phase." Overridden: no commits until the user says to, regardless of how many phases are completed in the meantime. Work still proceeds phase-by-phase with acceptance tests gating the next phase — only the git commit boundary is deferred.

## 2026-11-05 — Cheque credit account and sales cheque toggle as settings (backlog #34, option 3)

Decision: resolve backlog #34 with option 3 (a generic setting read by every creating path), not
with a patch to the legacy cheque module. Recorded in the project copy as section 13.

- **Incoming cheque credit account**: a company-level setting (`cheque_incoming_credit_account_id`,
  Many2one `account.account`) in Financials. Every path that creates `cheque.manage` reads it. No
  caller passes its own value. If the setting is empty, the create raises `UserError` naming the
  setting; the NOT NULL constraint must never be the first thing to fail.
- **`default_get` must not overwrite a value the caller already set** (part of #34).
- **Sales-linked cheque toggle** (`cheques_enabled`, Sales Setup, company-level): gates cheque
  generation from `sale.proposal`. Visible only when `sales_cheques` is installed.
- **Timing**: implemented before Phase 3 step 5. Steps 3 and 4 close only after the acceptance tests
  in `claude/s8_cheque_settings_prompt.md` pass. The rename of backlog #33 stays in Phase 7.
- Correction to the project copy: section 13 of the project's decisions log said the work lands in
  Phase 7. That was wrong. The timing above is the correct one.

## 2026-11-05 — All repo modifications go to branch developer_18

Decision (user): the repo's working branch is `developer_18`, and every repo modification is made on
it. The `new` branch is not created for now. Earlier entries that say "new branch" describe the
same work on `developer_18`. Where the plan still names `new` (Phase 9, extracting the core), that
step is on hold until the target branch is confirmed.

Effects:
- `implementation_plan.md` Prerequisites: branch list updated. Phase 9 marked on hold.
- `bug_backlog.md` and `plan_status.md`: fix-policy wording now says `developer_18`.
- `s8_cheque_settings_prompt.md`: Claude Code works on `developer_18`.
- Legacy repos (arkzayed, marketstandards) are still never edited.

## 2026-11-05 — S8 implementation: where the cheque settings live (section 13a)

The S8 prompt's rule was "`sales_cheques` if the setting is sales-facing, otherwise the L1
cheque module". Applied literally, `cheque_incoming_credit_account_id` is **not** sales-facing -
it is core cheque accounting, needed by every cheque creation including flows that never touch
sales - so it belongs at L1. But L1 is `arkzayed_18_gt_cheque_management`, which CLAUDE.md puts
off limits. The rule as written is therefore unsatisfiable without either editing legacy code or
creating a new module.

**Decision: both settings live in `isky_18_realestate_developer_sales_cheques`**, and the fix is
implemented as a single choke point rather than per call site.

- `res.company.cheque_incoming_credit_account_id` and `res.company.cheques_enabled` are
  company-level fields (not `ir.config_parameter`) - a multi-company database needs a different
  credit account per company, which a global parameter cannot express.
- `cheque.manage.create()` in this module already existed as an override, and every one of the
  11 `cheque.manage` create call sites passes through it. Putting
  `_resolve_incoming_credit_account()` there covers all 11 - including the four wizards in
  `arkzayed_18_realestate_development` - without editing a single legacy file. Patching seven
  isky call sites individually would have been more code, would still have missed the four
  legacy ones, and would have left the next new call site unprotected.
- `default_get()` is overridden in the same module so the legacy implementation can no longer
  discard a caller's credit account. It only ever fills a blank; it never replaces a real value.
- Outgoing cheques are deliberately untouched: their credit account still comes from the legacy
  `credit_out_account` parameter. S8 constrains behaviour changes to the incoming path.

**Known consequence, recorded rather than hidden:** the choke point ships in `sales_cheques`, so
it is absent when the legacy cheque module is installed without it (which also requires
`sales_crm`). In that configuration the monolith's four cheque wizards can still reach the NOT
NULL constraint. Closing that gap properly means hosting the setting at L1 - either a new
L1-level `isky` cheque-config module (which would also give backlog #29's rename a home) or an
edit to the legacy module. **Open question 12.3** - needs a scope decision, not implemented.

Also unresolved by design: S8's close-out asks for a commit hash against backlog #34, but commits
are held until the user asks (decision of 2026-11-04). The hash line in `bug_backlog.md` is
marked pending.

## 2026-11-05 — Open question 12.3 ACCEPTED until Phase 7 (user decision)

The residual L1 gap in section 13a is accepted for now. The incoming-credit-account protection
ships only in `sales_cheques`. Without that module, the legacy cheque module and the monolith's four
cheque wizards can still reach the NOT NULL constraint. This closes the scope question. It does not
close the gap itself.

Conditions of acceptance:
- The setting stays in the Financials section (decisions log 2026-11-04, section 8). Its location in
  the UI does not change.
- Today the setting's view is only shown when `sales_cheques` is installed. That is the accepted
  behaviour until Phase 7.
- The full fix (a generic L1 cheque-config home for the setting, which also takes backlog #29's
  rename) is scheduled in Phase 7. A one-line edit to the legacy `default_get` is not used.
- Phase 3 steps 3 and 4 are closed with this acceptance.

## 2026-11-05 — Phase 3 step 5: the installments lock rule — **NEEDS REVIEW**

Marked NEEDS REVIEW because this is a design choice made while implementing step 5, not one
the user has confirmed. Step 5's brief specified *that* the toggle locks once installment lines
exist; the three decisions below are how.

**1. The lock lives in `write()`, not in `@api.constrains`.** `@api.constrains` fires on every
write that merely *includes* the field, even when the value is unchanged. With a constrains the
project form would become **unsaveable** as soon as any installment line existed, because saving
a form writes all its fields. Comparing old against new in `write()` means only a real change is
rejected; re-writing the same value is allowed. The step-5 test asserts both halves.

**2. Reaching the project from a line is a two-route search.** `installment.lines` has no
`project_id`, and `sale.proposal` has none either (step 0 findings), so
`realestate.project._has_installment_lines()` matches on
`reservation_id.project_id` **or** the line's stored `unit_id.project_id`. The second route is
the only one that works for a contract-only line. A line counts if either matches. If a line is
linked to neither a reservation nor a unit, it is invisible to the lock - acceptable, since such
a line has no project to govern it, but worth knowing.

**3. The company lock only considers projects in `inherit` mode.** Changing the company default
is rejected while any project that *follows* it has lines; projects with an explicit On/Off
override are unaffected, because the default does not govern them. The error names up to five
blocking projects so the user can act on it.

**Open for review:**
- Should the lock be absolute, or should a manager group be allowed to override it? Currently
  absolute for everyone, including superuser.
- Should it consider only *unpaid* lines? Today any line blocks, paid or not. Allowing a switch
  while unpaid lines exist would mean deciding what happens to them.
- The sum-to-100 constraint deliberately skips one case: a **single line with 0%**, so that
  adding a blank row in a form does not error before the user types. Any other total, including
  0% across two or more lines, is rejected. This escape hatch is a usability call, not a rule
  from the brief.

## 2026-11-05 — Phase 3 step 5: naming

- `res.company.installments_enabled` / `realestate.project.installments_mode` /
  `installments_effective` - the names the brief specified, used verbatim.
- `realestate.sales.installments.gate` - the L2 abstract mixin resolving whether a deal may
  generate lines. Not added to L0's existing `installment.mixin`: the flags it reads are
  declared in L2, and `real.estate.unit` also inherits `installment.mixin`, so that would push
  a sales dependency into L0.
- `realestate.split.line.mixin` / `realestate.split.parent.mixin` - the split engine and the
  deal side of it. `customer.ownership` keeps its existing `customer_id` field name rather than
  being renamed to `partner_id`: legacy reports and views read it by name. The mixin therefore
  names the party field through `_split_party_field` instead of declaring it, which is also how
  it supports a user-based split without forcing a redundant column.
- `realestate.sales.commission.hooks` - no-op bases for the two L3 commission methods L2 calls
  (see the regression entry below).

## 2026-11-05 — Regression found and fixed: L2 called L3-only methods (Phase 2 fallout)

Found by the step 5 tests, not by any install gate. Phase 2 moved the live
`_build_commission_hierarchy` (reservation and contract) and `compute_person_hierarchy` (EOI)
implementations into L3 `isky_18_realestate_developer_commission` but **left their callers in
L2** - 10 call sites for the first, 2 for the second. These are plain runtime attribute reads,
not `@api.depends` paths, so every install gate passed while
**creating a reservation, a contract or an EOI in an L2-only database raised `AttributeError`**.
That is the core sales flow, broken in exactly the Mode B configuration the refactor is meant to
support.

This was a regression I introduced in Phase 2, not a pre-existing legacy defect: git HEAD shows
the callers and the definitions were in the same module before the move.

Fixed with the established pattern: `realestate.sales.commission.hooks`, an L2 abstract mixin
with no-op bases, inherited by `eoi.eoi`, `real.estate.sale.reservation` and `sale.proposal`.
L3 declares the same methods on the same models and loads after L2, so its real implementations
override the no-ops when the commission module is installed.

**Lesson for the remaining phases:** the install gates cannot see this class of break. A
cross-layer call is only caught by exercising the flow. Every future layer move must be followed
by a grep for callers left behind, and the phase's tests must create one of each core record.

## 2026-11-06 — Phase 3 step 6: the UI migration becomes its own phase (Phase 3c)

Step 6 was "S4 rules on every new view and menu". The audit showed the rules are **already met
for every view Phases 2 and 3 produced**, and that S4's remaining acceptance criteria cannot be
reached inside Phase 3. Three interlocking findings:

1. **L0 `unit_inventory` has no views and no window actions.** Odoo hides a menu with no
   accessible children, so the shared root menu S4 mandates would be invisible - which fails
   S4's own acceptance ("menu tree shows the business-area roots even when some optional
   modules are not installed").
2. **The monolith already owns a `Real Estate` root with 101 menuitems.** Adding L0's root while
   the monolith's remains would show users a second, empty `Real Estate` menu.
3. **215 view records across 8 modules** still define the UI for models the isky modules own.
   A correct menu tree requires owning the actions, which requires moving those views. Menus and
   view migration are one job.

**Decision: a dedicated phase, Phase 3c (UI migration), run layer by layer, L0 first** so the
business-area roots have something to show before they are introduced. Phase 3 closes without
it. Nothing user-visible changes in the meantime: the monolith keeps serving the UI exactly as
it does today.

**Scoped exception to the no-legacy-edit rule, authorised 2026-11-06:** deleting or trimming
**view and menu records only** in the legacy modules is permitted, strictly as part of moving a
model's UI into its owning module. Business logic, Python and data files stay untouched. This is
narrower than S4's wording ("remove views from the monolith") in one respect and wider in
another: the audit found the UI for isky-owned models spread across **8** modules, not just the
monolith -
`arkzayed_18_realestate_development` (177), `arkzayed_18_realestate_developer_crm` (27),
`arkzayed_collections_report` (3), `arkzayed_cost_distribution` (3), `isky_base_modification` (2),
`isky_contract_template` (2), `arkzayed_contract_npv` (1). Two of those are `isky_*` modules, not
legacy at all. The exception covers the arkzayed ones; the isky ones were never restricted.

**Policing it:** `claude/scripts/lint_s4_views.py`, added in step 6, enforces S4 mechanically -
a standalone view must live in the module owning the model, and every menuitem `action=` and
`parent=` must resolve within the module's dependency closure. It also prints the remaining
migration backlog per module, so Phase 3c has a running count. All three checks pass today.

## 2026-11-06 — Phase 4 step 0: audit, and four decisions taken before implementing

### Audit findings

**1. Four hierarchy implementations confirmed, and they genuinely disagree.** The plan says
"remove the 4 existing implementations"; they are not four copies of one algorithm, they are four
behaviours:

| Document | Where | Roles used | No-team behaviour | Form |
|---|---|---|---|---|
| Lead | **L2** `crm_lead.py:1500` | 3 - **omits Sales Sector Manager**, adds `team.user_id` | includes user | stored compute on `@api.depends` |
| EOI | L3 `eoi_commission_hierarchy_ext.py:19` | 4 | **clears all lines** | imperative |
| Reservation | L3 `sale_reservation_crm_ext.py:15` | 4 | user as Sales Person | imperative |
| Contract | L3 `sale_proposal_crm_ext.py:58` | 4 | user as Sales Person | imperative |

So the plan's acceptance criterion "same manager mapping across lead, EOI, reservation and
contract" **fails today** - that is the defect Phase 4 fixes, not a property to preserve. The EOI
copy also reads `person.sales_manager_id` / `person.operation_id` off a `res.users` record where
the sibling copies read them off the user's `crm.team`; that looks like a bug and is treated as
one.

**2. There are two commission models, one in the wrong layer.**
`realestate.commission` (L3, `commission.py:6`) already carries all four document FKs including
`opportunity_id`. `commission.commission` (L2, `persons_commission.py:5`) is a near-duplicate
used only by `crm.lead.commission_ids`, with a **different default** (`commission=1` vs `100`)
plus `job_level_id` and `is_tcr_sales_person`. Backlog #38 already flagged the layer violation.

**3. Commission basis does not exist at all.** No `commission_basis`, no timing field, no lock.
Built from scratch.

**4. `job.level` has no `company_id`**, and its flag-uniqueness constraint is global. The plan
requires job levels per company.

**5. The role flags exist but the engine ignores them.** All four implementations hardcode
`['Sales Person', 'Sales Manager', 'Sales Sector Manager', 'Director']` and assign a role by the
*position of a `crm.team` field in that list*, writing the result into a Char. `job.level`'s six
`is_*` role flags are never consulted. This is precisely what "role flags are assigned by role,
not by name" forbids.

**6. L3 hard-depends on the optional L1 accounting bridge but uses nothing from it.** Its
manifest lists `isky_18_realestate_developer_accounting`, yet it references only core
`account.payment` (10), `account.move` (6) and `account.account` (1). Installing commission
therefore forces Mode A for no reason.

### Decisions

- **D1. One model, not two.** `realestate.commission` (L3) is the single commission line model;
  `commission.commission` (L2) is removed and `crm.lead.commission_ids` repoints to the L3 model,
  carrying `job_level_id` and `is_tcr_sales_person` across. Consequence, stated plainly: lead
  commission lines become unavailable unless L3 is installed. That is correct layering - lead
  commission *is* commission - but it is a behaviour change for an L2-only database, so the field
  and its compute move behind the same no-op hook pattern used in step 5
  (`realestate.sales.commission.hooks`). The differing default (1 vs 100) is resolved to **100**,
  matching the three documents that actually drive payment.
- **D2. One engine, in L3, driven by role flags.** A single abstract mixin builds the hierarchy
  for all four documents. A participant's role comes from `user.job_level_id`'s `is_*` flags, not
  from the position of a `crm.team` field in a hardcoded name list. The team traversal still
  decides *who* participates; `job.level` decides *what* they are. Ordering comes from a new
  `sequence` on `job.level` rather than from list index.
- **D3. The four behaviours converge on the reservation/contract one** (a user with no team is
  still a Sales Person; all four roles considered). Rationale: it is the behaviour of the two
  documents that actually produce commission, it loses nobody from the hierarchy, and the EOI
  "clear everything" branch would silently drop commission for an unteamed salesperson. The
  lead's omission of Sales Sector Manager is treated as the bug it is.
- **D4. L3 drops the L1 bridge dependency**, replacing it with core `account` - the same change
  Phase 2b/3 made for `sales_crm`. It uses nothing from the bridge, so this is a manifest fix,
  not a redesign.

Each is a design choice made here, not one the user confirmed in advance; D1 and D3 change
behaviour and are the two most worth challenging.

## 2026-11-06 — The eight CRM groups moved into `sales_crm` — **NEEDS REVIEW**

Done at the user's instruction, after Phase 4's widened lint exposed the problem (backlog #45).

- The eight groups are now defined in `sales_crm/security/security.xml` keeping their original
  local ids (`financial_manager_group`, not `group_financial_manager`), so the mapping to the
  legacy group each one replaces stays 1:1 and obvious. This differs from the `group_*` naming
  of the groups Phase 3 moved; chosen deliberately for traceability of the move.
- The legacy implied chain is preserved exactly: director -> sector manager -> sales manager ->
  `sales_team.group_sale_salesman`.
- **No legacy file was edited.** The legacy module references only its own copies, so both sets
  can coexist. This was checked, not assumed.

**Flagged NEEDS REVIEW for two reasons:**

1. **`operation_executive_group` was commented out in the legacy file** - it had never existed
   as a record, so its 7 gates in `sales_crm` were dead twice over. Defining it makes those 7
   gates live for the first time. Decisions log section 11 requires functional-team confirmation
   before enabling previously-dead approval features in an environment with real data; this is
   exactly that case, and the same caution applies to the other seven.
2. **Duplicate groups in a transitional database.** Where both modules are installed there are
   now two groups named "Financial Manager", "Sales Manager" and so on, and a user holding the
   legacy one does **not** hold the new one - so the gates will still deny them until they are
   re-assigned. Options: re-assign by hand, ship a one-off mapping script, or retire the legacy
   CRM module's groups as part of Phase 3c. **Not decided.**

Not addressed by this change: `sales_crm` still resolves **22 other legacy-CRM xmlids** at
runtime, 35 of them through `env.ref()`, which raises. That includes every CRM lead stage, so
the whole lead workflow still requires the legacy module. Backlog #49.

## 2026-11-06 — S7 approval settings: implemented, with four deviations from the spec

Spec: `S7` as given, which itself records section 11's limits. The four decisions in the spec
(retroactive groups, fresh databases only, full audit, two gates never configurable) are
implemented as written. Four things differed from the spec text and were decided here.

**1. `operation_manager` has no default group.** The spec names
`sales_crm.group_operation_manager_approval`. That group does not exist: it is defined in
`arkzayed_18_realestate_development` and referenced **only from legacy views**, never from a
Python gate in `sales_crm`. Rather than point a default at a group this module cannot see, the
stage ships empty and is excluded from the "must be configured" constraint. It is kept in the
registry and the form so the configuration is complete rather than silently missing a stage.
Its one useful side effect: it is the one stage legitimately empty while approvals are on, so
the "empty group refuses loudly" test needs no contrivance to reach that branch.

**2. Two of the eight stages have no Python gate in `sales_crm`** - `operation_manager` and
`show_discount` are referenced only from view `groups=` attributes. They are marked
`has_python_gate=False`: configurable and surfaced, but excluded from the
no-empty-group constraint, because an empty group there blocks nothing. Recorded so nobody
later reads the eight settings as eight enforced gates.

**3. Defaults had to be seeded explicitly, and this is not a migration.** A field `default=`
applies only to records created afterwards, and a Many2many has no column to backfill, so Odoo
populates nothing for a `res.company` that already exists - which is every company, because
`base` creates one long before this module installs. Without a seed, **every database, fresh
ones included, installs with all eight stages empty**, which both changes behaviour and leaves
an unsatisfiable gate while approvals are on. `res.company._s7_apply_default_approver_groups()`
is called from the data file; it fills only empty stages, so a module update never overwrites
configuration. The spec's decision 2 ("fresh databases only, no migration") does not cover this,
because it is not a migration - it is the install-time default.

**4. The memberless-group warning is client-side only.** The spec asks for a save that succeeds
with a warning. Odoo has no non-blocking warning on `write()`, so the warning is an
`@api.onchange` on `res.config.settings` - the form shows it and the user can still save - and
`res.company.write()` additionally logs it server-side. A caller writing to `res.company`
directly gets the log, not a UI warning. Stated rather than silently approximated.

**Also done in this pass, and strictly speaking beyond S7:** `lint_guard_pattern.py` check 2 now
matches the `has_group()` **call** rather than guessing from the xmlid's name. The name-shape
heuristic had already missed two classes of reference (Phase 4's 40 `*_group` refs, and now
`arkzayed_18_realestate_development.stop_checking_reservation_expiration`, which matches neither
pattern). That last group was moved into `sales_crm` as well, so check 2 is green.

**Unchanged and still blocking real use** (spec section 7): 12.2's missing ACLs. The S7 test for
the approval audit trail had to grant `ir.model.access` rows in-transaction, because a
non-superuser cannot write `sale.proposal` at all - so on real data the approval step is still
never reached. The spec predicted this; it remains true.

## 2026-11-06 — customer.ownership audit fixes (B1, B2, R1-R5, C1)

Implemented from the approved audit. Four things are worth recording beyond the change list.

**B2: the contract -> reservation link is kept, and precedence decides the group.**
`_split_parent_fields` is now an ordered tuple `('contract_id', 'reservation_id')` and a line
belongs to exactly one group - the first of those that is set. So a contract line still carries
`reservation_id` (the legacy reports read it, and `action_create_contract` relies on it), but it
counts only in the contract total. Before this a reservation holding its own 60/40 plus a
contract holding its own 60/40 made the reservation group 200%, and every subsequent write on
those lines raised.

**The legacy reports still see the link.** `sale_reservation.xml`, `initial_reservation_form.xml`
and `reservation_unit_report.xml` iterate `o.customer_new_ownership_ids`, which for a reservation
now returns both its own lines and its contract's lines, exactly as before. Nothing in the
reports changes. **Revisit in Phase 3c**, when those reports move into the owning module and the
question of what a reservation report should show after contracting can be answered properly.

**R2: the escape is gone entirely, not narrowed.** The old rule tolerated "one line totalling 0%",
which also tolerated a real single-owner 0% split. A new row in a form never reaches an
`@api.constrains` - constrains run after the write - so removing the escape costs nothing in
usability and the form is still editable. Verified both ways by test.

**R4 created the setting it reads.** There was no Financials rounding *precision* setting; the
existing `_apply_rounding_config` rounds amounts (cents, nearest ten), not decimal places. So
`res.company.split_percentage_precision` (Integer, default 2) was added and surfaced in the
settings form. Default 2 keeps the rule behaving exactly as before. Unlike S7's Many2many
defaults, a scalar default IS backfilled onto existing rows by Odoo, so no seeding was needed.
Phase 6 owns relocating it into the Financials section.

**C1 choices:** `_order` is declared on the **mixin** only, because the ordering is part of the
shared contract and every future split model should inherit it; the duplicate on
`customer.ownership` was removed. The `customer_new_ownership_ids` constrains moved to the two
**concrete models**, which own the field, and delegates to `_validate_split_children()` in the
mixin - the trigger is local, the logic stays shared.

## 2026-11-06 — 12.2 closed: access rules for `sales_crm`'s own models

`isky_18_realestate_developer_sales_crm` shipped **no** `ir.model.access` rows for the 38 models
it declares. Every one had zero ACLs, so no ordinary user could read or write installments, EOIs
or contracts - the models worked, but only for the superuser. Found during Phase 3 step 2b and
carried as open question 12.2 through steps 3, 4, 5, S7 and Phase 4.

The matrix is in `security/ir.model.access.csv`; the reasoning is in `security/security.xml`,
because an Odoo CSV cannot carry comments (a `#` row raises `IndexError` at install - measured,
not assumed).

**Three choices worth challenging:**

1. **`base.group_user`, never an empty `group_id`.** The established convention in this codebase
   is an *empty* group - 28 rows in `unit_inventory`, 9 in `commission` - which in Odoo grants
   full CRUD to **every** user, portal and public included. That convention was not copied.
   Backlog #52 raises the existing rows as a separate security question, since tightening them
   is an L0/L3 change with its own blast radius.
2. **Unlink split by what deletion means.** Children a recompute deletes and recreates
   (installment lines, maintenance lines, payment allocations, ownership lines, payment lines)
   are unlinkable by an ordinary user, because `self.installment_ids = None` and the reallocation
   engine run as that user and would otherwise fail outright. Top-level documents - EOI,
   reservation, contract, offer, the three request models, broker unit - are manager-only to
   delete. The alternative (manager-only everywhere) would have broken recalculation; the
   alternative (user-deletes-everything) gives every salesperson the ability to delete a signed
   contract.
3. **`sales_manager_group` is the configuration maintainer**, and the sector-manager and
   director groups imply it, so seniority inherits the right rather than needing its own row.

`crm.lead` deliberately has no row: core `crm` owns it, and this module only sets `_name` on it
to inject a mixin (Phase 4).

**A design fix this forced.** `maintenance.config.get_config()` lazily **creates** the singleton
config row, and it is called from `sale_reservation._default_maintenance()` while an ordinary
user creates a reservation. With configuration models read-only for users, reservation creation
failed. The row is now created with `sudo()`: bootstrapping a missing default is a system action,
and requiring every salesperson to hold configuration-write rights just to open a reservation
would have made the configuration ACL meaningless. Nothing user-supplied is written there.

**The S7 workaround is gone.** `test_s7_approval_settings` had to create `ir.model.access` rows
in-transaction to reach the approval gate at all, because a non-superuser could not write
`sale.proposal`. Those 14 lines are deleted and the suite still passes - which is the concrete
evidence that 12.2 is closed rather than merely described.

**Why this survived so long, and the guard against a repeat.** Odoo tests run as superuser,
which bypasses ACLs entirely, so every test written before this one would have passed whatever
the rules said. Every test in `test_acl_12_2.py` uses `with_user(...)`, and two of them are
structural guards: `test_every_model_has_an_acl_row` fails if a new model ships without one, and
`test_no_acl_row_grants_access_to_every_user` fails if anyone adds an empty-group row here.


## 2026-11-07 to 2026-11-09 — reconstructed decisions (docs loss of 2026-11-09)

Everything above this heading is original, restored from the 2026-11-06 snapshot. The entries in
this section were **rebuilt on 2026-11-09** from `claude/recovery/reports_from_transcript.md`; the
originals were lost with the rest of `claude/`. Each carries `[RECONSTRUCTED]` and its transcript
line. Where a decision was taken but its record does not survive in any report, that is stated
rather than guessed.

**Placed here, before the 2026-11-09 CEO entry, to keep the log in date order.** No pre-existing
entry was moved or altered.

### Phase 5, decision on the vendor domain

`[RECONSTRUCTED]` <!-- transcript line 1048 --> `vendor_commitment.vendor_id` carried
`domain=[('supplier_rank', '>', 0)]`, and `supplier_rank` is declared by Odoo's `account`. **The
domain was removed rather than adding `account` to L4's depends.** Reasoning recorded at the time:
this repo already settled that core `account` is not L1 (which is why `sales_crm` depends on it),
`sales_crm` needs it to `_inherit account.move`, whereas L4's only use was narrowing one dropdown.
The lost filter is backlog #63.

### Phase 7, decision on the job level flags (plan bullet 4 deliberately not followed)

`[RECONSTRUCTED]` <!-- transcript line 1080 --> Phase 4 had already removed what was actually
hardcoded - the engine used to match job levels by name string against
`['Sales Person', 'Sales Manager', …]` and now resolves roles via `_role_key()` with a configurable
sequence, per company. What remains is six booleans that are **the product's role vocabulary, not
any client's**. Converting them to rows would force the engine's role→`crm.team`-field mapping to
become data - configuration naming a field, breakable by typo on a posting path. "Cost real,
client-value benefit nil", so it is backlog #67 with the reasoning rather than a silent skip.

### Phase 7, the one config key deliberately left on the client prefix

`[RECONSTRUCTED]` <!-- transcript line 1080 --> `arkzayed_18_gt_cheque_management.journal_id` is
written by the legacy module's own settings page, so renaming our side alone would stop us reading
what the user sets. Left as it is; tracked as open question 12.3 and backlog #29.

### Backlog #60, the owner's exception and then option B

`[RECONSTRUCTED]` <!-- transcript line 1019 --> The 2026-11-07 owner exception authorised exactly
three one-token legacy edits. The run found **four** lines needing the change, not three, and
stopped at the prompt's stop condition rather than widening the diff, putting three options to the
owner.

`[RECONSTRUCTED]` <!-- transcript line 1039 --> **Option B was chosen and applied.** Two
corrections to the figures the choice was made on, recorded at the time: the CSV rows are **41, not
38**, split **35 empty-group / 6 grouped**; and **one of the six was held back** - monolith row 2
grants `base.group_user` `1,1,1,1` on `real.estate.sale.reservation` where 12.2 deliberately chose
`1,1,1,0`, so repairing the reference alone would have silently undone a closed decision. That row
went to #52.

### Phase 3c, step 1 decisions and the three lessons

`[RECONSTRUCTED]` <!-- transcript line 1204 --> Recorded as S1-D1…D6 at the time; the individual
decision texts do not survive. What the report preserves: the shared **Real Estate root menu lives
in L0**, because L0 is the only module every layer depends on; four views were **split rather than
moved**, with the L2/L3 halves restored through inherited views (`l0_view_extensions.xml`); and the
two construction-progress views were **not** moved, being step 4's.

Three lessons carried forward: a dotless xmlid resolves against the current module, so bare
references must be swept with a resolver rather than grep; expect to split, not only move; and
**write the offline view validator before the first install**, after four installs were spent
discovering view errors one at a time.

### Phase 3c, step 2 split (S2-D1/D2) and the step 2b decision put to the owner

`[RECONSTRUCTED]` <!-- transcript line 1214 --> Step 2 was **split into 2a and 2b**. 2a moved the
101 of L2's 133 records that need nothing outside "view and menu records". 2b was stopped and put
to the owner, with three options and a recommendation, because its 32 records need ten monolith
security groups, a paperformat or an action button - and "doing it ten times on the forms carrying
the approval and payment gates is a security change wearing a UI costume, which is why I stopped
rather than decided". Step 1 had done the declare-in-L2-and-leave-the-monolith's option once, for a
single group, and it already cost backlog #72.

### Phase 8, the four decisions (D1-D4) and the G4 field name

`[RECONSTRUCTED]` <!-- transcript line 1192 --> **D3, stored not related** - three reasons recorded:
a related/computed field is re-resolved on every read, which is recalculation; a broker database
may hold no developer records, so the code must be typeable by hand; and when a developer re-codes,
the broker's stored code must not shift under the offers quoting it. Re-reading is an explicit act.

**On G4**, the field is `realestate_company_type`, not `company_type`: `res.partner` already
declares `company_type` (person/company), and although `res.company` has no delegation to partner
in Odoo 18 - checked - two fields of that name on models this close is a trap. Values and default
are as the owner decided: developer/broker, default developer.

A product rule corrected the test: the first no-recalculation test re-coded a developer unit to
force a divergence, and Phase 1 refused it because the project's unit hierarchy is locked once it
holds a unit. The test now repoints the link to a second developer unit - legitimate, and a sharper
check, since a related field would have changed the instant the link changed.

### The sign-client gate, SC-D1 to SC-D5

`[RECONSTRUCTED]` <!-- transcript line 1520 --> The decisions themselves were recorded before the
code per rule 6, and their full text does not survive. What the closure report preserves:

- The new group is `sales_team_lead_group` ("Sales Team Lead", **a placeholder name**), owned by
  L2, implying `sales_team.group_sale_salesman`, with `sales_manager_group` implying it.
- The new S7 stage is `sign_client`, `has_python_gate: True`, default approver
  `sales_team_lead_group`.
- The gate sits in `sale.proposal.write()` beside the three approval Booleans, and **fires only
  when a record actually moves** into a signing state - without that carve-out an ordinary
  salesperson could not edit a signed contract whose write happened to include `state`, and every
  such write would add a spurious audit row.
- **SC-D4 gated `signed_ceo` through the same `sign_client` stage**, with the consequence recorded:
  a Sales Team Lead could perform the step labelled "Signed by CEO". Superseded by the 2026-11-09
  CEO entry below, which is the decision to split it - though that split was never implemented.
- **SC-D5: step 5 of that task could not be done.** It asked for `groups=` on the "Sign by Client"
  button. That button exists only in the monolith's contract form, legacy edits were forbidden
  twice by the same task, and an inheriting view in `sales_crm` is impossible because the monolith
  *depends on* `sales_crm` - an `inherit_id` pointing at it is an upward reference that does not
  resolve in Mode B. Deferred to Phase 9, when the form moves.

**Still open, unchanged by any of this:** `approval_enabled = False` skips every stage, so with
approvals off an ordinary salesperson can sign again. Asserted explicitly by
`test_stage_off_skips_gate`. The owner must accept it or ask for the signing stages to join
`NON_CONFIGURABLE_GATES`.

### 2026-11-09 — the docs loss, and the decision not to continue into it

`[RECONSTRUCTED]` <!-- transcript line 1584 --> Every `claude/*.md` document was lost. The cause is
`.gitignore:6`, `*.md`, unanchored: the documents were **never tracked by git**, so a branch switch
plus a clean of ignored files removed them with no history to fall back on. The logs survived
because nothing ignores `*.log`.

Two decisions taken at the time, both recorded here because they shaped what exists now:

1. **The CEO-stage run was stopped rather than carried on.** Writing four more documents on top of
   empty files would have buried the loss, and rule 6 cannot be satisfied by appending 45 lines to
   a log that has lost 2,438.
2. **The 45-line stub that the aborted run's own `cat >>` had recreated as `decisions_log.md` was
   renamed**, so no file pretended to be the project log. It is now merged into this file and the
   stub is deleted.

`.gitignore` was **not** changed: the fix is the owner's call, and the exact lines are in the
consolidation report.

## 2026-11-09 — CEO signing (D1-D3), recovered from partial stub

[RECONSTRUCTED] Source: `claude/decisions_log.CEO-D1-D3-only.PARTIAL.md`, the stub written on
2026-11-09 during the aborted CEO-stage run. Not from the transcript reports - this is the
stub's own text, carried over verbatim below so nothing of it is lost. The decisions were
recorded; **the code they describe was never written**, because that run stopped when the
docs loss was found. Treat CEO-D1 to CEO-D3 as agreed-but-unimplemented.


Owner decisions of this date. They follow the sign-client gate of 2026-11-08 and fix the weakness
that run recorded in SC-D4: both signing states shared one stage, so a Sales Team Lead could
perform the step labelled "Signed by CEO".

**CEO-D1 — new S7 stage `sign_ceo`, default approver `director_manager_group`.** In
`isky_18_realestate_developer_sales_crm`, `has_python_gate: True`, configurable in Sales Setup like
the rest. **No new group**: step 1 confirmed `director_manager_group` is the director, checked in
the database rather than read from source - name `'Director'`, direct `implied_ids`
`operation_manager_group`, and its only code use is a seniority test in
`crm_lead.has_reassign_auth` (`crm_lead.py:1505`) alongside the manager and sector-manager groups.
Nothing contradicts the name.

**The chain matches the one the previous run recorded**, so the step-1 and step-3 stop conditions
both pass. Read back from `scg_modeb`:

| group | name | implies (direct) |
|---|---|---|
| `sales_team_lead_group` | Sales Team Lead | `sales_team.group_sale_salesman` |
| `sales_manager_group` | Sales Manager | `sales_team_lead_group`, `group_sale_salesman` |
| `operation_manager_group` | Sales Sector Manager | `sales_manager_group` |
| `director_manager_group` | Director | `operation_manager_group` |

A director holds `sales_team_lead_group` transitively; a team lead does **not** hold director. That
asymmetry is what makes the split work: the director can do both steps, the team lead only the
client one.

**CEO-D2 — `signed_ceo` moves from `sign_client` to `sign_ceo`.** `signed_client` and
`signed_by_client` stay on `sign_client`. Before this change
`sale_proposal.py:34` read `SIGNING_STATES = ('signed_client', 'signed_ceo')` and
`sale_proposal.py:2025` called `_require_approval('sign_client')` for both - quoted here because
the next run should be able to see what moved.

**CEO-D3 — same placement as before.** The gate stays in `sale.proposal.write()` beside the other
approval Booleans, and still fires only when a record actually *moves* into the state, which is the
carve-out the previous run added and `test_signing_an_already_signed_contract_is_not_a_second_approval`
pins.

**Still open, and this run does not decide it.** `approval_enabled = False` skips every stage, so
with approvals off a salesperson can set `signed_ceo` as well as `signed_client`. The new
`test_stage_off_behaviour_for_ceo` measures and asserts whatever the behaviour is rather than
assuming it; the decision - accept it, or move the signing stages into `NON_CONFIGURABLE_GATES` -
remains the owner's, and is unchanged by this split.

## 2026-11-10 — Signing always enforced, one signer group (owner decisions 1-4)

Owner decisions from the task prompt of this date, recorded before any code change (rule 6).

**SG-D1 — one signer group for all signing states: `director_manager_group` (Director).** It signs
`signed_client`, `signed_by_client` and `signed_ceo`. **Consequence, recorded as the prompt
requires: the Sales Team Lead no longer signs.** This supersedes SC-D1/SC-D2 of 2026-11-08, where
`sales_team_lead_group` was the default approver of the client step, and it also supersedes the
unimplemented CEO-D1 of 2026-11-09 (which would have given the CEO step to the director while the
team lead kept the client step). The owner must confirm this consequence **before the diff is
merged**; the diff is produced and shown, and nothing is committed.

**SG-D2 — signing is NON-CONFIGURABLE and always enforced.** `sign_client` and `sign_ceo` move out
of the S7 stage registry into `NON_CONFIGURABLE_GATES`, so `approval_enabled = False` no longer
skips them. **This is an explicit exception to S7 decision 2** (the one on/off switch skips every
configurable stage): signing is the first gate that started life as a configurable stage and was
then made exempt. The two existing non-configurable gates (`block_unit`,
`exception_reservation`) were never stages, so the precedent is the section-11-decision-4 list,
not the switch.

**SG-D3 — the group is configurable only through the group itself** (its members, in Settings >
Users & Companies > Groups), not through Sales Setup. The company field `sign_client_group_ids`
and its settings row are removed; no new setting is added, so the S7 settings limit is kept.
`sign_ceo_group_ids` was named by the prompt but **never existed** - the CEO stage of 2026-11-09
was decided and not built - so there is nothing to remove on that side.

**SG-D4 — `sales_team_lead_group` stays in the database and keeps its other rights.** Only signing
moves. The group's place in the implied chain
(`salesman <- sales_team_lead_group <- sales_manager_group <- ...`) is unchanged, so no user loses
any right they hold through it.

The SC-D3 carve-out of 2026-11-08 is kept unchanged: the gate fires only when a record actually
*moves* into a signing state, so a no-op state write on an already-signed contract is neither
gated nor logged.

## 2026-11-10 — Signing gate rebuilt per SG-D1..D4; one premise corrected

Implemented the same day the decisions were recorded. The diff is shown, nothing committed; per
SG-D1 the merge waits on the owner confirming the consequence (the Sales Team Lead no longer
signs).

**One prompt premise corrected rather than followed:** the task said to remove
`sign_ceo_group_ids` from Sales Setup. That field never existed - the 2026-11-09 CEO stage was
decided (CEO-D1..D3 above) and never built. Only `sign_client_group_ids` existed, and it is
removed: the company field, the settings related field, the onchange/sweep entries and the view
row. The `company_sign_client_rel` table remains in existing databases as an orphan; harmless,
and dropping data tables is not this run's business.

**How SG-D2 is implemented.** `sign_client` and `sign_ceo` are entries in
`NON_CONFIGURABLE_GATES` pointing at `director_manager_group`, with their labels in a new
`NON_CONFIGURABLE_GATE_LABELS` beside them. `SIGNING_STATES` became a mapping
`{'signed_client': 'sign_client', 'signed_ceo': 'sign_ceo'}`, so each state names its gate and a
new signing state cannot compile without one. The gate in `sale.proposal.write()` checks
`has_group()` directly - deliberately NOT `_require_approval()`, which returns True for everyone
when `approval_enabled` is False - and writes the same audit row shape the S7 gates write
(entry_type `approval`, the gate key as `stage`, approver, matched group, document), so signing
stays in the one audit trail.

**The buttons stay untouched (SC-D5 still in force).** "Sign by Client" and "Sign by CEO" live
only in the monolith's contract form (`arkzayed_18_realestate_development/views/
sale_proposal_views.xml:84` and `:101`); legacy edits are forbidden and an inheriting view cannot
point upward at a module that depends on this one. The `groups=` attribute goes on when the form
moves in Phase 9. The backend gate does not depend on it.

**Tests replaced, not weakened.** `test_team_lead_can_sign`, `test_manager_can_sign`,
`test_stage_off_skips_gate`, `test_stage_defaults_to_the_team_lead_group` and
`test_empty_group_refused_when_approval_on` asserted the 2026-11-08 rule and are gone; their
replacements assert the owner's new rule (`test_team_lead_cannot_sign`,
`test_manager_cannot_sign`, `test_approvals_off_still_enforced`, `test_signing_not_configurable`).
No test outside the gate's own file signs a contract - swept, zero hits - so no other test was
touched. The SC-D3 carve-out test and both structural guards survive, updated for the mapping.
