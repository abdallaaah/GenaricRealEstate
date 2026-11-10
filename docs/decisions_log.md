# Decisions Log — general_broker

## 2026-11-10 — Access-rights run (D1–D12 minus D6/D8)
Applied the approved access decisions across the five broker modules on branch `broker`.
**Portal access disabled pending business decision** (who the portal users are, and what
permission.request is for): portal ir.access rows deactivated, portal feature flags seeded
off, portal routes return 404 while off, and a kill-switch restriction blocks portal users
from crm.lead (stock website_crm_partner_assign otherwise grants them read). Commission
models and access rows untouched — commission redesign runs separately.
Full report: docs/access_rights_run_2026-11-10.md. Test suite: 34/34 on Odoo 20.
