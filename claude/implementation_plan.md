# Implementation Plan — GenaricRealEstate (generic product)

Source of truth for decisions: `claude/decisions_log.md`. If this plan conflicts with the log, the log wins.

## 0. Prerequisites

* Repo `GenaricRealEstate` locally. All repo modifications go to branch `developer_18` (decisions_log, 2026-11-05). The `new` branch is not created for now.
* Working Odoo 18 Community environment for install tests.
* Execution happens in Claude Code on the repo.

## 1. Rules

* One commit per phase. Do not start a phase until the previous one passes its acceptance tests.
* Do not modify legacy repos (arkzayed, marketstandards).
* Any new or changed decision is recorded in `decisions_log.md` before it is implemented.

## 2. Phases

### Phase 1: Core hierarchy in L0 (`unit_inventory`)

* Hierarchy template at company level; per-project override.
* Allowed levels: project, building, cluster, zone, floor, unit. Zone is a tree level, not a separate dimension.
* Each node has its own code, unique under its parent.
* Unit system code = concatenation of path node codes. Format (separator, pattern) is set per project.
* Hierarchy level definition locks after the first unit exists in the project. Adding nodes after lock is allowed; existing node codes never change.
* L0 has no dependency on sales or accounting.

Acceptance:

* Project with 2 levels (project → unit) generates correct system codes.
* Project with cluster and zone generates correct codes with no code change.
* Changing levels after the first unit is rejected at server level.
* Duplicate code under the same parent is rejected.

### Phase 2: Accounting bridge, break the cycle (L1)

* `isky_18_realestate_developer_accounting` depends only on `account` and L0.
* Remove every field pointing to sales (`sale_proposal_id`, `penalty_id`, `sale_reservation_id`, etc.).
* Remove every field pointing to `arkzayed.cost.allocation` (`allocation_ids`, distribution fields).
* Move sales-related `account.move` fields to L2 as `_inherit`.
* Module becomes an optional bridge.
* Remove the dependency of `arkzayed_18_realestate_development` on accounting if it is part of the cycle.

Acceptance:

* Dependency graph script reports no cycles.
* Install without the accounting bridge succeeds.
* Install with the accounting bridge succeeds.

### Phase 3: Sales (L2)

* `sales_crm` depends on L0, and on L1 only through the optional bridge.
* Split model shared by reservation and contract. Sum of percentages must equal 100%.
* Installments toggle in Sales Setup, with per-project override. When off, no installment lines are generated.
* Installments toggle cannot change for a project once installment lines exist.
* Lead and EOI are informational only: no real commission is calculated.

Acceptance:

* Split sum not equal to 100% is rejected.
* Toggle off: deal is created with no installment lines.
* Changing toggle after installments exist is rejected.

### Phase 3c: UI migration (views and menus, S4)

Added 2026-11-06 (decisions log). Phase 3's step 6 established that S4's remaining acceptance
criteria cannot be met inside Phase 3: 215 view records across 8 modules still define the UI for
models the isky modules own, L0 has no views or actions of its own, and the monolith already owns
the `Real Estate` root menu. Menus and view migration are one job.

Run layer by layer, **L0 first**, so the business-area roots have something to show before they
are introduced:

1. **L0 `unit_inventory`** - 76 views. Then introduce the shared root menu and the `Units`
   business-area section.
2. **L2 `sales_crm`** - 90 views, plus the `Sales` section. Includes the two UI pieces deferred
   from Phase 3 step 5: the `installments_mode` field on the project form, and hiding the
   installment tabs and buttons when the flag is off.
3. **L3 `commission`** - 26 views, plus the `Commission` section.
4. **L4 `construction`** - 12 views, plus the `Construction` section.
5. **Optional bridges** - `accounting`, `sales_accounting`, `sales_cheques`: their menus appear
   only when installed.
6. Retire or re-parent the monolith's `menu_real_estate_root` and the CRM module's
   `menu_broker_root`, so only one root remains.

Legacy edits: authorised for **view and menu records only**, strictly as part of moving a
model's UI (decisions log, 2026-11-06). Business logic, Python and data files stay untouched.

Acceptance:

* `claude/scripts/lint_s4_views.py` passes, with the migration backlog it reports down to zero
  for the layer being migrated.
* Menu tree shows the business-area roots with every optional module uninstalled.
* No menu points to an action that does not exist in the installed module set.
* No duplicate root menu once step 6 of this phase is done.

### Phase 4: Commission (L3)

* One hierarchy engine used by lead, EOI, reservation, and contract. Remove the 4 existing implementations.
* Job levels defined per company. Role flags are assigned by role, not by name.
* Commission basis: company default (`reservation` or `contract`), per-project override (default `inherit`).
* Commission is calculated only on the selected basis document. No double calculation.
* Timing: at signing (default).
* Basis locks for a project once any commission is calculated or posted, even if the deal is cancelled.
* Broker commission stays inside L3 of the developer product for now.

Acceptance:

* Same deal with basis=reservation and basis=contract produces commission only on the selected document.
* Changing basis after first commission is rejected.
* Same manager mapping across lead, EOI, reservation, and contract.

### Phase 5: Construction (L4)

* Depends on L0 and L1 only.
* Confirm it does not need anything from the cost distribution module.

Acceptance: installs standalone.

### Phase 6: Settings

Five sections only. Each setting lives in exactly one section.

* Company Setup: company type (developer or broker); default commission basis; default job levels template.
* Sales Setup: installments toggle; default years for residential and non-residential units; reservation expiry settings.
* Commission: job levels definition; split rule (fixed 100%); commission timing (fixed default: signing).
* Financials: accounts and journals for entries; VAT and withholding rates; installment rounding rules (only relevant when installments are on).
* Units: default hierarchy template at company level; system code format per project.

Acceptance: every setting is in its section, with no duplicates.

### Phase 7: Remove hardcoded client values

* Fields with client names (`collection_gis_percentage`, `collection_credit_oaya_account_id`, and similar) become generic revenue split configuration rows (company, business line, account, percentage, sequence).
* VAT divisor (1.14) and withholding rate (0.05) in `broker_claim` move to Financials.
* Config parameters prefixed `arkzayed_18_realestate_development.` are renamed to a generic prefix.
* Job level boolean flags are replaced by role-based configuration.

Acceptance: grep for client names (GIS, OAYA, arkzayed) in models, views, and config returns zero results.

### Phase 8: Broker branch

* Broker stores the system code as a char field. No computed logic.
* Broker reads the code from the developer product.

Acceptance: broker reads the code without recalculating it.

### Phase 9: Extract core (on hold; target branch to be confirmed, see decisions_log 2026-11-05)

* Core = L0, L1 bridge, L2 base, hierarchy engine.
* Developer and broker become extensions on the core.

Acceptance: core installs alone. Developer and broker profiles install and work on top of it.

## 3. Risks

* A cycle can reappear in a new place. Run the dependency graph script after every phase.
* Views and security XML left in the monolith may reference removed fields. Audit them before deleting anything.
* Odoo registers model xmlids under the new module name. Old refs fail silently. Run a repo-wide sweep after each move.

## 4. First steps

1. Prepare Odoo 18 environment and run install on the current baseline.
2. Write the dependency graph script (reads all `__manifest__.py`, reports cycles).
3. Start Phase 1.
