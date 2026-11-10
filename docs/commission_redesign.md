# Commission Engine Re-design

## Why

The broker commission engine exists in three generations of the same code. Each gained
and lost capabilities, and `isky_20_broker_commission` — the newest — lost the most.

| Gen | Module | Date | Retro | Rollup | Approve guard |
|---|---|---|---|---|---|
| 1 | `marketstandards/isky_realestate_broker_commission` | 2025-09 | ❌ | recursive SQL, 6 rules | ✅ |
| 2 | `arabella/arabella_18_realestate_broker_commission` | 2026-09 | ✅ | same as gen 1 | ✅ |
| 3 | `general_broker/isky_20_broker_commission` | 2026-11 | ❌ | collapsed, broken | ❌ |

Gen 2 is byte-identical to gen 1 apart from an added retro layer. Gen 3 is a cleaner
rewrite (dated project rules, multi-company, no `print()` debris) that dropped the
retroactive effect, the hierarchy rollup, and the plan-conflict guard.

Gen 2 is the only generation installed anywhere, on two staging databases — where all
8 plans are `type='achieve'` and `retro_active` is 0 across all 47 achievement rows.
**The bracket and retro paths have never executed on real data.** Gen 2's retro code is
a record of intent, not verified behaviour.

## What was wrong

1. **The rollup never aggregated a team.** `_get_user_achieved_amount` filtered
   `commission_plan_id = plan.id`, but plans are matched per `hr.job`, so every
   subordinate sits on a different plan than their manager. The filter excluded all of
   them; the rollup silently returned only the person's own deals. Gen 1/2 looked each
   member's plan up individually — and still got it wrong, passing a `job.level` where
   the method expected an `hr.job`.

2. **The reporting chain was written twice and the copies disagreed.** A four-branch
   `if/elif` in the engine, six hand-written `UNION` branches plus a recursive CTE in
   the report. Neither covered the same cases.

3. **`bracket.amount` is a field Odoo owns.** Native
   `sale.commission.plan.target.commission.amount` is a *stored compute*
   (`amount_rate × plan.commission_amount`) with an inverse, so Odoo rewrites it
   whenever the plan's on-target commission changes. The shipped demo data is
   self-inconsistent, so the 50% bracket drifts 3000 → 2500 on first recompute
   (−6,000 EGP on a 12M deal).

4. **`additional_commission_percentage`** has been on `project.commission`, in the UI,
   read by nothing, in all three generations.

## What this re-design does

### The rollup has one definition

`job.level` now carries `hierarchy_sequence` (rank) and `team_role_field` (which
`crm.team` slot holds that role). `broker.sales.hierarchy` generates its relationships
from that chain: a manager is linked to a subordinate when the subordinate sits in a
lower-ranked slot on the same team **and every slot between them is vacant**. That one
rule reproduces all six of gen 1's hand-written branches — including the skip-level
cases (a director manages the team leader directly on a team with no sales manager)
without any of them being spelled out. Rows are the transitive closure.

`res.users._get_subordinate_users()` is the single accessor. The engine calls it; the
achievement report embeds the same generated SQL as a CTE. They cannot drift apart.

The report does **not** JOIN the view: `drop_view_if_exists` cascades, so rebuilding the
chain after a `job.level` change would drop the report view with no error.

A client with a different org shape edits `job.level` rows. Removing the Sales Manager
tier regenerates 3 branches instead of 6, with no code change — the same approach as
`broker.approval.rule`.

### Segmentation lives in a model we own

`commission.segment` — `amount_from` / `amount_to` / `percentage`, as an o2m on the
plan. `percentage` is a **true percent**: 2.5 means 2.5%. Bounds are half-open
(`from <= value < to`), so a value on a boundary belongs to the upper band;
`amount_to = 0` means open-ended, and only the last band may be open. A constraint
validates the whole ladder: starts at 0, no gaps, no overlaps, one open band, last.

`segment_basis` on the plan picks what the bounds measure: `volume` (cumulative sales
volume in currency) or `target_rate` (percent of the period target achieved).

`use_custom_segments` is off by default, so existing plans keep computing through the
native bracket path exactly as before.

### Retroactive effect is cliff + reachback, with an audit trail

Cliff segmentation makes the rate a property of the period, not of the individual deal:
crossing into a higher band lifts what every deal already booked in that period should
have earned.

Gen 2 wrote that correction into a `retro_active` float, overwriting whatever was there,
leaving an amount nobody could explain. Here each correction is a
`commission.retro.adjustment` row — which deal triggered it, which band it moved from
and to, the before and after — and `retro_active` is their sum.

Deltas are **incremental**, measured against the row's current effective total, so
successive corrections sum to exactly "amount at the current band minus amount as first
booked":

| | deal 1 (2M) booked | retro | effective | band |
|---|---|---|---|---|
| after deal 1 (40% of target) | 40,000 | +0 | 40,000 | 2.0% |
| after deal 2 (60%) | 40,000 | +10,000 | 50,000 | 2.5% |
| after deal 3 (80%) | 40,000 | +20,000 | 60,000 | 3.0% |
| after cancelling deal 3 (60%) | 40,000 | +10,000 | 50,000 | 2.5% |

`applied_segment_id` records which band a row was rated at — without it the retro pass
has no way to know what a past deal earned. `is_cancelled` replaces deleting rows:
`create_from_lead` supersedes instead of `unlink()`, and `action_cancel` re-rates the
period without that deal's volume, booking negative corrections.

### Everything is a feature flag

`broker.feature.flag` was portal-specific in name only. It now has
`is_feature_enabled` / `_check_feature` / `_set_flag` as the generic core, with the
portal methods delegating, plus a `category` to group the list.

| Flag | Seeded | Why |
|---|---|---|
| `commission_team_rollup` | on | the engine attempts this today |
| `commission_hierarchy_stacking` | on | `basic_hierarchy_commission` is active today |
| `commission_segmentation` | off | new behaviour |
| `commission_retroactive` | off | new behaviour |
| `commission_project_additional_percentage` | off | the field is dead today |

Seeded explicitly (with `company_id` unset, so every company inherits and a
company-specific row can override) rather than relying on fail-open, so an upgrade can
never switch a money path on by itself. Commission lookups pass `default=False`.

**With every flag at its seeded value and `use_custom_segments` off, the engine computes
exactly what it computed before this change.**

### Other fixes

- `broker.feature.flag` lookup ordered by `company_id desc` with `limit=1`, but Postgres
  sorts NULLs **first** on DESC — so a global row outranked a company-specific override,
  the opposite of the intent. Now two explicit searches: company, then global.
- The report built its rows from achievements, so a director who closes nothing
  personally got **no row at all** — precisely the person the rollup exists for. Rows
  now start from plan assignments, as gen 1 did.
- `_find_plan` with no job key left the filter out of the domain entirely, so a user
  with no `hr.job` picked up whichever approved plan had the lowest id. No key now
  means no plan.
- `_apply_project_adjustments` compared a configured percentage to the threshold with
  `==`; now `float_compare`, since that branch decides whether commission is capped.
- `_get_basic_hierarchy_commission` branched on role flags and handled only Director
  and Sales Manager, so a Team Leader who closed personally always stacked exactly
  nothing. Now derived from `hierarchy_sequence`.
- `double_commission_mode` setting: gen 1/2 *added* the entry band's rate, gen 3
  silently changed it to `× 2`. Both readings are available; default is gen 3's.
- The pre-v20 search filter `('retro_active', '=', True)` on a float column makes
  Postgres reject the query (`operator does not exist: double precision = boolean`).
  The equivalent filter here uses `!= 0`.

### Harvested from the live gen-2 engine

Gen 2's `crm_lead.py` turns out to carry a note that its Confirmed-Contract trigger was
**switched off**: commission there is created from the contract once collection reaches
the plan's threshold (`sale.proposal._auto_create_commission_achievements` in
`arabella_18_realestate_development`). That path is the one actually running in
production, and it contains features neither gen 1 nor gen 3 has.

| Harvested | Setting | Default |
|---|---|---|
| Trigger stage — a signed contract is not money received | `commission_trigger_stage` | `confirmed_contract` |
| Achieve amount read as a rate per million | `achieve_commission_basis` | `flat` |
| Operations staff paid alongside the hierarchy | `commission_operations_share` | off |
| Only pay from a plan the person is assigned to | `commission_require_plan_assignment` | off |
| Plans partitioned by how the deal was referred | `commission_referral_plan_matching` | off |
| Commission booked into a separate broker company | `res.company.commission_broker_company_id` | empty |

- **Trigger stage.** The broker side has no installment ledger to measure a collection
  percentage against, but `crm.stage` already carries `is_collected` alongside
  `is_confirmed_contract`, so the trigger is a choice of stage rather than a hard-coded one.
- **Operations share.** Operations users cannot arrive through `lead.commission_ids`:
  that list is built from the reporting chain, and an Operations job level sits outside
  it (`hierarchy_sequence` 0) by design. They are collected separately from approved
  achieve plans whose job level is an Operations level, skipping anyone the hierarchy
  already paid on that deal.
- **Plan assignment.** Gen 1/2 had a `confirm_salesperson_plan` for this that searched,
  discarded the result, and returned the plan regardless — the check never ran. The live
  gen-2 path does perform it. It is implemented here for real, and off by default
  because switching it on stops paying anyone whose assignment rows were never filled in.

- **Referral plan matching.** `with_broker` / `with_ambassador` on the plan. Matching is
  exact on both flags, as in production: a broker-referred deal matches only plans
  flagged With Broker, and a deal with no broker only plans without it. Enabling it
  therefore needs a plan per referral combination, which is why it is off by default.
  The deal's referral state comes from `crm.lead.broker_ids` / `ambassador_ids`.

  One deliberate deviation: production also constrains the two flags to be mutually
  exclusive, because its source was a single "referred by" selection. Here the lead
  carries two independent many2many fields, so a deal can genuinely have both a broker
  and an ambassador — and such a deal needs a plan with both flags set. Carrying the
  constraint across would leave those deals matching no plan and silently earning
  nothing.

- **Commission broker company.** `res.company.commission_broker_company_id` routes
  commission earned on one company's deals into another — for a group where a developer
  company sells the units and a separate broker company receives the commission and pays
  the sales team. Self-gating: empty (every existing install) means commission stays
  with the company that owns the deal, so this needs no flag.

  This one has a trap worth knowing. The rollup and the report both scoped achievements
  by the *plan's* company. Once rows are booked into the broker company while plans stay
  with the developer company, that comparison matches nothing — every achieved figure
  silently becomes zero. Both now resolve the commission company the same way
  (`_commission_company` in Python, `COALESCE(company.commission_broker_company_id,
  company.id)` in the report SQL), and the currency follows the resolved company too.

Not portable to this repo: the collection *percentage* itself, which is computed from
installments, allocations and cheque states in the developer-side module.

## Semantics to know

**The `(/M)` convention is deliberate.** On the native bracket path, the Commission
column is a rate per million of contract price: 5000 earns 0.5%. It renders as a
Monetary with a currency symbol, so the plan form states it. `commission.segment` does
not use this convention.

**The achieve path has two readings, and both are available.** Gen 1/2 — and the live
gen-2 production path — compute a hierarchy beneficiary's commission as
`contract_price × commission_amount / 1_000_000` (per million). Gen 3's
`_calc_non_sales_amount` treats `commission_amount` as flat money. On a 12M deal with an
achieve plan of 1000 that is 12,000 versus 1,000 — a 12× difference on every
beneficiary, every deal. `achieve_commission_basis` selects between them; it defaults to
`flat` so that upgrading changes nobody's commission, but **production uses per-million**,
so most clients will want to switch. The same setting governs the stacked hierarchy
commission.

## Not yet done

Tests. `isky_20_broker_commission` has none, and the module cannot be installed on this
machine: Odoo 20 here is Community (no `sale_commission`), while Odoo 18/19 ship it but
reject a `20.0.*` manifest. Verification so far has been done by stubbing Odoo, running
the real model source, and executing the generated SQL against Postgres with fixture
tables — which covers the SQL generation, the hierarchy closure, the flag precedence,
the segment boundaries and the retro arithmetic, but not the ORM write path.
