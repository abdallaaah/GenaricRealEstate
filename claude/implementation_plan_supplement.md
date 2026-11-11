# Implementation Plan — Supplement

Start condition: Phase 1 of `implementation_plan.md` is done. Phase 2 is COMPLETED (see `plan_status.md`). S1 is scheduled in Phase 2b, after Phase 2.

Decision changes in this supplement supersede the earlier "installments toggle off = no installment lines" rule in `decisions_log.md`, section 7.

## S1. Cheques (Phase 2b)
Decision: cheques are split across two layers.
- **L1 (optional): generic cheque module.** Cheque model, cheque states, cheque register. Depends only on `account` and the L1 accounting bridge. Contains no sales references.
- **L2 (sales): sales-linked cheque extensions.** Any field or logic that links a cheque to a sale, contract, reservation, or installment lives in L2 as `_inherit`.

Problem to resolve: L2 must not hard-depend on an optional L1 module. Therefore sales-linked cheque extensions go into a separate optional bridge module `sales_cheques` that depends on both `sales_crm` and the L1 cheque module. It is installed only when both are present.

Current code: cheque fields on `account.payment` live in the monolith (`arkzayed_18_realestate_development`). They must move out:
- generic cheque fields → L1 cheque module
- sales-linked cheque fields → `sales_cheques` bridge

Acceptance:
- Install `sales_crm` without cheques: works.
- Install cheques without `sales_crm`: works.
- Install all three: sales-linked cheque features work.

## S2. Sales with and without accounting (Phase 3)
Decision: two operating modes, determined by whether the L1 accounting bridge is installed.

Mode A: **With accounting** (bridge installed). Behavior stays as today: payments create journal entries.

Mode B: **Without accounting** (bridge not installed). No journal entries at all. Nothing is posted to `account.move`.

Installments are a separate flag, independent of accounting:
- **Installments enabled** (Sales Setup, company default, project override, lock rule from the main plan): when on, installment lines are generated. When off, no lines.
- Mode B with installments on: lines are generated and tracked by manual status only.

Manual payment tracking (L2, no accounting dependency, used in Mode B):
- Each installment line has a "Paid" button and a boolean.
- Each EOI has a "Paid" button and a boolean.
- Setting "Paid" stores date and user. No journal entries are created.

Acceptance:
- Mode B, installments on: lines generated, "Paid" button works, zero `account.move` records created.
- Mode B, installments off: no lines generated, deal flow unaffected.
- Mode A: payment flow creates journal entries as before (regression test against current behavior).
- EOI "Paid" button works in both modes.

## S3. Payment allocations (status: verify, then close)
The payment allocation block was moved off the L1 bridge into L2 during Phase 2.

Target placement:
- **L1 bridge**: allocation of a payment to `account.move` (invoices). Exists only in Mode A.
- **L2 sales**: allocation of a payment to installment lines and EOI. Exists in both modes, using manual status in Mode B.

Work item (Phase 3, verification only if the Phase 2 move is complete): confirm no allocation logic remains in the bridge that is sales-specific, confirm L2 allocation works in Mode B, and add acceptance tests for each mode.

## S4. Views and menus (applies from Phase 2 onwards)
Views (form, list, search, kanban):
- A view lives in the module that owns the model. A unit form lives in L0. An installment form lives in L2. Never place a view for a model in a module that does not own it.
- Remove views from the monolith as each model moves. Do not leave views in the monolith that reference fields from other layers.

Menus:
- One shared root menu, defined in L0 (`unit_inventory`), named by business area, not by module: Units, Sales, Commission, Financials, Construction, Configuration.
- Each module adds its own sub-menus under the shared root, using `sequence` for order.
- Configuration menu contains the five settings sections from `decisions_log.md`, section 8.
- Optional modules (accounting bridge, cheques, sales_cheques) add their menus only when installed.

Acceptance:
- Every model's views are in its owning module.
- Menu tree shows the business-area roots even when some optional modules are not installed.
- No menu points to an action that does not exist in the installed module set.

## S6. Guard pattern: super()-chained compute extension (approved 2026-11-04, Phase 3)

The one pattern for every money compute that depends on payment / `account.move` / cheque paths.
Chosen because `@api.depends` resolves at module load and therefore cannot be guarded at
runtime — the dependency must be handled structurally. Already proven in this codebase: Phase 2
used it for `_prepare_move_line_default_vals` (L1 bridge base, sales_crm layering the
returned-cheque swap on top via `super()`).

Rules:
- The base compute in `sales_crm` keeps its own `@api.depends` on **always-present paths only**.
  This base behaviour *is* Mode B.
- Each bridge that extends a compute must **redeclare the method with `@api.depends` including
  its own paths**, and must call `super()`.
- **Lint check**: any compute method overridden in a bridge without `@api.depends` fails.
  Implemented at `claude/scripts/lint_guard_pattern.py`; run it after any bridge change.
  It skips methods whose signature is not `(self)`, since those are not field computes
  (e.g. `account_reports`' `_compute_<x>(self, report, options, ...)` handlers).

### New modules introduced by Phase 3
- **`isky_18_realestate_developer_sales_accounting`** (optional bridge, approved 2026-11-04).
  Holds only real accounting coupling: `payment_method_type`, `converted_amount`,
  `custom_exchange_rate`, `overseas_payment_type`, the bridge-only payment states, and the
  Mode A logic in `sale_reservation.py`. Installing it = Mode A; omitting it = Mode B.
- **`isky_18_realestate_developer_sales_cheques`** (optional bridge, from S1). Created in
  Phase 3 step 4, once the guard pattern exists.

Sales-owned flags are **not** accounting fields and stay in `sales_crm` as `_inherit` on
`account.move`: `is_contract`, `is_down_payment`, `is_collection`, `is_maintenance_collection`.

`is_gis_quia` is renamed to a generic name in Phase 3 (client name in a field identifier breaks
the Phase 7 rule).

## S7. Approval settings (scheduled after Phase 3 step 2b)

Full decision: **`decisions_log.md` section 11**. Summary:

- Approver groups are **configurable**: a setting per approval stage picks which `res.groups`
  approve it. Default = the current groups.
- The **gates stay in code**. No setting may disable unit blocking, reservation exception, or any
  other control that bypasses a check. Configurability covers *who* approves, never *whether* the
  check runs.
- **One company-level setting in Sales Setup** turns the approval step on or off. Default = on.
- **At most 2–3 approval settings** in Sales Setup. No per-gate flag.
- **Pre-condition for any environment with real data**: confirm with the functional team which of
  the 10 previously-dead approval groups actually have real users, and record the answer in
  `plan_status.md`. Re-activating a gate nobody belongs to would lock that action for everyone.
- **Not implemented now** — scheduled after Phase 3 step 2b.

Background: these 10 features were silently dead until Phase 3 step 2a. `sales_crm` referenced 7
groups defined in the monolith it does not depend on, so `has_group()` returned False for every
user. Step 2a moved the groups to the modules owning the models they gate, which makes the gates
live again — hence the need for these decisions.

## S5. Execution order (updated)
1. Phase 1 of the main plan: DONE.
2. Phase 2 of the main plan (accounting bridge, cycle break): COMPLETED.
3. Phase 2b: S1 cheque split (L1 cheque module, sales_cheques bridge). Starts after Phase 2 closure.
4. Phase 3 (Sales): S2 mode split and manual "Paid" tracking, S3 verification, S4 rules applied,
   S6 guard pattern. Step order approved 2026-11-04:
   1. S6 guard pattern + move `group_manual_paid_installment` into `sales_crm`.
      Acceptance: Mode B works, the Paid button is live without the monolith.
   2a. Move sales-owned flags to `sales_crm`.
   2b-a. Create `sales_accounting`; move the bridge-owned refs (~29 field refs, 12 payment-state
       refs) into it; remove `sales_crm`'s hard dependency on the L1 accounting bridge.
   2b-b. **Mode B gate — runs before any other 2b work.** Install `sales_crm` + L0 + Odoo
       `account`, WITHOUT the accounting bridge. Log: `claude/logs/phase3_step2b_modeb.log`.
       Pass criteria: Paid button works on installment line and EOI; zero `account.move` records
       created; no ParseError or KeyError at field setup; no Mode A code path executes.
   3. Apply S6 to cheques; remove `sales_crm`'s hard dependency on the L1 cheque module.
   4. Create `sales_cheques`; move `cheque.manage` and the returned-cheque fields into it.
   5. Installments toggle and shared split model.
   6. S4 rules on every new view and menu.
5. S4 rules apply from Phase 2b onwards for every new view or menu.
