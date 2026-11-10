# Access-Rights Run — 2026-11-10

Branch: `broker` (worktree). Scope: the five broker modules; commission models untouched (D6);
portal switched off pending D8. Tested end-to-end on Odoo 20 (`/opt/odoo/odoo20`, Community),
database `broker_access_test` — the four non-commission modules install and run there.

## Step 0 — the Odoo 20 access model, measured from source

All answers read from `odoo/addons/base/models/ir_access.py` and `odoo/orm/models.py` of
`/opt/odoo/odoo20`, then exercised by the test suite.

1. **Combination.** One mechanism, `ir.access`. A row **with** a group is a *permission*; every
   permission whose group the user has (directly or transitively — `_get_group_ids` returns
   `all_group_ids`) is **OR-ed**, whether the rows share a group or not. A row **without** a
   group is a *restriction*; restrictions are **AND-ed** on top. The exact formula
   (`models.py:3647`): `Domain.OR(permissions) & Domain.AND(restrictions)`. Empty OR is FALSE
   (`DomainOr.ZERO = _FALSE_DOMAIN`): restrictions alone grant nothing.
2. **Global restriction.** A groupless row (+ domain + the operations it covers). `kind`
   computes to `'restriction'` precisely when `group_id` is empty — it is NOT an
   "everyone-CRUD" row, and it binds every user except the superuser. The stock
   `crm_lead_company_rule` multi-company row is exactly this shape.
3. **Domains and caching.** A domain may be a Python expression over `user`, `company_id`,
   `company_ids` (evaluated via safe_eval; `user` carries an empty context). The evaluated
   result is cached **registry-wide**: `_access_domain` is
   `@api.ormcache('operation', 'self.env._access_context')` with key
   `(operation, uid, allowed_company_ids)`, in the `'default'` cache container; raw rows are in
   `'stable'` (`_get_all_access`). Invalidation: any ir.access create/write/unlink
   (`_clear_caches` → `invalidate_ormcache('stable')`, and `_CACHES_BY_KEY['stable']`
   cascades into `'default'`), and user-group changes. **An arbitrary user/company field
   change does NOT invalidate it** — the v17 ir.rule caveat survives in v20 form.
   Consequence used in Step 2a: the pool setting is referenced **as a field path on the
   record** (`company_id.broker_unassigned_leads_visible_to_all`), so Postgres evaluates it
   at query time and the cached domain never goes stale; the company `write()` additionally
   calls `ir.access._clear_caches()` as belt and braces. Verified by
   `test_pool_setting_turns_on_without_restart` — toggle, same registry, no restart.
4. **Effective matrix** — below.

## Effective rights on crm.lead — Before

| Row (module) | Group | Ops | Domain |
|---|---|---|---|
| crm_rule_personal_lead (crm, stock) | Salesman | cru | own **+ unassigned** |
| crm_rule_all_lead_1 (crm, stock) | Salesman All Docs | cru | all |
| crm_rule_all_lead (crm, stock) | Sale Manager | **crud** | all |
| assigned_lead_portal_rule_1 (partner_assign, stock) | **Portal** | r | assigned-partner leads |
| crm_lead_company_rule (crm, stock) | — restriction | crud | allowed companies |
| crm_lead_rule_split_deal (broker) | **base.group_user** | cru | own + split |
| crm_lead_rule_director_lead_admin_all (broker) | Director | **crud** | all |
| crm_lead_rule_lead_admin_all (broker) | Lead Admin | crud | all |
| crm_lead_rule_portal_hierarchy (broker) | **Portal** | ru | hierarchy |

Plus: Operations Manager ⟹ Director ⟹ Sale Manager (full sales track, team/tag admin, lead
delete). `developer.project`, `project.sale.phase`, `neighborhood`, `res.country.city`,
`broker.unit`, `broker.unit.counter`, `permission.request`, `user.notification`,
`partner.notification.rel`: **base.group_user crud, no domain** (P1 violations).
`user.notification` had no ownership scoping at all.

## Effective rights on crm.lead — After

| Row | Group | Ops | Domain |
|---|---|---|---|
| crm_rule_personal_lead (stock, untouched) | Salesman | cru | own + unassigned |
| crm_lead_rule_split_deal | Salesman | cru | own + split (`sales_ids`) |
| crm_lead_rule_team_leader | Salesman | cru | `team_id.user_id = user` |
| crm_rule_all_lead / _1 (stock, untouched) | Sale Manager / All-Docs | crud / cru | all |
| crm_lead_rule_director_lead_admin_all | Director | cru | all |
| crm_lead_rule_lead_admin_all | Lead Admin | crud | all |
| crm_lead_rule_operation_executive | Ops Executive | r | all |
| crm_lead_rule_operation_manager | Ops Manager | cru | all |
| crm_lead_rule_finance | Finance | ru | all (see "given back") |
| crm_lead_rule_commission_upline | base.group_user | r | `commission_ids.employee_id ∋ user` |
| crm_lead_company_rule (stock) | — restriction | crud | allowed companies |
| **crm_lead_restriction_unassigned_pool** | — restriction | rud | pool rule (Step 2a) |
| **crm_lead_restriction_no_portal** | — restriction | crud | FALSE for portal users |

Pool restriction domain (per-user Python, group part cache-safe because group changes clear the
access caches; setting part is a field path, evaluated per query):

```
[(1,'=',1)] if user in {Sale Manager, Ops Executive, Lead Admin}   # Ops Mgr implies Ops Exec
else ['|' user_id set,
      '|' company_id.broker_unassigned_leads_visible_to_all,
          team_id.user_id = user]
```

Delete: stock still grants `d` to Sale Manager; `crm.lead.unlink()` refuses everyone but
Lead Administrator (su exempt) — stock rows untouched (D3).

Master data / units after (D7): everything readable by all internal users; writes:
projects + phases → Inventory Manager (`group_broker_unit_manager`, implied by Broker Admin);
neighborhood + city → Broker Admin (note: `res.country.city` is defined by
`isky_20_broker_real_estate` itself, so its rows are ours to change); units → assigned
salesperson (`seller_sales_person`) + stored `seller_team_leader` + Inventory Manager (cu),
delete Inventory Manager only; counters → `[('unit_id','access','write')]` delegation (cud) —
the v20 `access` operator makes "children follow the parent's write access" (P4) a one-line domain.
Unit price/status: `write()` guard + `can_edit_protected_fields` compute driving `readonly` in
the form (P7 — no `groups=`, fields stay readable). Initial price at `create()` stays with the
lister (the price-required constraint demands it); *changing* it is Inventory-Manager-only.
Deal cancellation flips `unit_status` back to available via `sudo()` (system act, not a user edit).

## Step 1 — rights Operations Manager lost and what was given back

Lost with `(3, director)` (everything reached via Director ⟹ Sale Manager):

| Lost | Given back? | Why |
|---|---|---|
| crm.lead crud all | **cru all** (own row) | D2 row; delete is nobody's (D3) |
| crm.lead delete | no | D3: Lead Admin only |
| crm.team crud | no (r stays via stock base row) | team structure is a sales-management concern |
| crm.tag cru | **r via Ops Executive row** | needed to render leads; editing tags is sales config |
| mail.activity.plan cud (lead plans) | no | sales-manager configuration |
| crm.merge.opportunity cru | no (Lead Admin got its own row) | merging deletes: D3 territory |
| Director/Sale-Manager stage-gate bypasses | kept | `is_restricted_user()` lists Ops Mgr explicitly |
| mail canned-response admin | no | not an operations need |

Given back additionally: implied `group_operation_executive` + `group_permission_approver`
(D1); reopen gate now states finance **or** Ops Manager explicitly (D5 — previously the text
said finance-only even though the decision reads both).

**Addition outside the D2 table:** `group_finance` got `ru` on all company leads. The finance
gates (Collected/Confirmed) are finance-only *writes*, which presuppose finance can see and
write the deal; the matrix omitted Finance entirely and no other group carries it after the
ladder split. Surfaced by `test_only_finance_reaches_collected` failing on read.

## Other decisions applied

- **D4 sales checkpoint**: enforced in `write()` (not the constraint — the constraint
  re-validates *all* non-pending approval fields on any approval write and cannot know which
  field this write sets; a retroactive identity check there would make the manager's later
  approval fail on the salesperson's earlier one). Group check unchanged; identity check new.
- **D4 approval rules**: `broker.approval.rule` now `mail.thread` with tracking on all three
  fields; Broker-Admin-only row unchanged.
- **D9**: `group_permission_approver` (in base — portal and crm both reference it);
  approve/reject actions check group + not-own-request; `approval_status` writable only
  through the two actions (context token), su exempt. Internal rows: group_user `cru`,
  approver `crud` (P4).
- **D11**: notifications scoped by recipient through new inverse `partner_rel_ids`
  (`user.notification` r own; `partner.notification.rel` ru own; created by the existing
  `sudo()` infrastructure in `mail_message.py` — the "own user" linkage is
  `partner.notification.rel.partner_id`).
- **D12**: Broker Admin implies neither `base.group_system` nor `base.group_erp_manager`
  (structural test).
- **Step 7**: portal access rows deactivated **in place** (CSV `active` column — deleting CSV
  lines would leave live orphans on upgraded databases); three portal flags seeded off,
  global, `noupdate`; routes raise **404** (not AccessError — an error page confirms the page
  exists) via `check_portal_feature_http`; stock `website_crm_partner_assign` still grants
  portal read on crm.lead, hence the `crm_lead_restriction_no_portal` kill-switch restriction
  — stock row untouched. Logged in the decisions log.
- **Lead Admin** joined `is_restricted_user()`'s exempt set: the merge wizard (their D3 tool)
  tripped the marketing-attribution guard, and `_check_lead_stage_transition`'s error text
  already claimed lead admins were exempt while the code disagreed.

## Multi-company (Step 8)

With `company_id` and now under a global company restriction: `crm.lead` (stock row, already
present), `broker.feature.flag` (new restriction row; global rows with no company stay visible
everywhere by design — they are the inheritable defaults).

Without `company_id` — **proposal only, no fields added this run**: `developer.project`,
`project.sale.phase`, `neighborhood.neighborhood`, `res.country.city`, `broker.unit`,
`broker.unit.counter`, `permission.request`, `user.notification` (+rel), `lead.stage`,
`broker.approval.rule`, `job.level`. Proposal: add `company_id` to `broker.unit` and
`permission.request` first (truly operational data); treat projects/master data as shared
catalog (company field optional, restriction `in company_ids + [False]`); keep `job.level`,
`lead.stage`, `broker.approval.rule` global configuration.

## BLOCKED

none — every step implemented.

## TEAM-REVIEW

1. **Four-eyes (D4).** The approving user is not stored per phase×role (only the status
   selections exist; `cancellation_approver` is the sole stored approver anywhere), so "the
   same user may not approve two roles in one phase" cannot be enforced. Options:
   (a) 12 `*_approved_by` Many2one fields mirroring the status fields; (b) one
   `broker.approval.entry` o2m (phase, role, user, date) written by the approval flow —
   preferred: auditable and extensible; (c) reconstruct from mail tracking values — fragile.
   No new fields added this run, per instructions.
2. **`_check_approval_rights` retro-validation.** Adjacent finding: the constraint re-checks
   every non-pending approval field on each approval write, so with rules configured for several
   roles, user B's approval re-validates user A's earlier one against *B's* groups. Latent today
   (first approver's group often ⊂ later approvers'), but it belongs with the four-eyes rework.
3. **`broker.unit.counter` semantics (D7).** The decision table assumed a system-incremented
   counter; the model is actually utility-meter records (electricity/gas/water…) edited inline
   on the unit. Applied intent instead of letter: read all, cud follows unit-write access
   (P4 child rule). If "system only" really is wanted, say so and it becomes a one-line change.

## Tests (P6 — all behavioural tests run `with_user`)

Suite `--test-tags=broker_access`, Odoo 20, DB `broker_access_test`:

| Run | Log | Started | Exit | Result |
|---|---|---|---|---|
| install | scratchpad/access_install.log | 2026-11-10 12:29 | 0 | 4 modules installed clean |
| tests #1 | scratchpad/access_tests.log | 2026-11-10 12:31 | 1 | 31/34 — portal leak via stock partner-assign row; merge blocked by attribution guard; finance invisible |
| tests #2 | scratchpad/access_tests2.log | 2026-11-10 12:34 | **0** | **34/34 passed** |

Coverage: the three structural tests; salesperson own/split/not-colleague/not-pool;
pool-setting toggle without restart; team leader (team + team's pool); ops exec read-only;
ops manager write; manager/ops/lead-admin see-all; commission upline read-only; company A/B
isolation; manager-cannot-delete / lead-admin-can / merge-works; sales checkpoint (owner yes,
manager-in-group no, split participant yes); approval rules admin-only; finance gate on
Collected; reopen by Ops Manager; notification isolation; unit owner/TL/other edit rights;
price+status manager-only; unit delete manager-only; counter delegation; project/phase/city
CRUD split; archive path; requester-not-own-approval; status-only-via-actions; portal
AccessError on eight broker models.

Not covered: HTTP-level 404 on portal routes (needs an HttpCase with website fixtures; the
flag checks the routes call are unit-covered by the flag seeds + `is_portal_feature_enabled`).

## Files changed

Groups/CSV: `isky_20_broker_base/security/*` (+approver group, +flag company restriction),
`isky_20_broker_crm/security/*` (ladder, lead rows, notifications, finance, two restrictions),
`isky_20_broker_real_estate/security/*` (new XML + CSV rewrite),
`isky_20_broker_portal/security/ir.access.csv` (portal rows off, approver rows).
Models: `crm_lead` (unlink guard, sales checkpoint, reopen gate, lead-admin exemption, unit
sudo on cancel), `res_company`+`res_config_settings` (pool setting + cache clear),
`user_notification` (inverse), `broker_approval_rule` (tracking), `broker_unit` (price/status
guard + compute), `developer_project`/`project_sale_phase` (+active),
`permission_request` (decision guards). Views: crm settings (+pool), unit form (readonly),
feature-flag + achievement search views (v20 `<group>` syntax). Portal: data flag seeds,
controllers 404, manifest. Tests: 4 new suites, 34 tests.
Odoo-20 compat found by this run's install: `broker_sales_hierarchy` `table_exists` import.
