# HANDOVER — GenaricRealEstate, branch `developer_18`

**This file was rebuilt on 2026-11-09 and is not the original.** The original `HANDOVER.md` was
lost with the rest of `claude/` and is **not in the recovery pack at all** - `RECOVERY_MANIFEST.md`
lists six restored files and this is not one of them. Everything below is either traceable to
`claude/recovery/reports_from_transcript.md` (tagged `[RECONSTRUCTED]` with its transcript line) or
is a present-tense fact about the repository that I verified today. **No work order, priority or
owner decision has been carried over unless a report records it** - the original's own status
summary, open-decision list and "first action" text are gone.

## Read these first, in this order

| File | What it is |
|---|---|
| `decisions_log.md` | **Wins over every other file.** Dated decisions. Original through 2026-11-06; reconstructed 2026-11-07 onward. |
| `plan_status.md` | What each phase did, with gate tables and run IDs. Original through 2026-11-06; reconstructed below the divider. |
| `bug_backlog.md` | Numbered findings. #1-#54 original; #61-#82 reconstructed; **#55-#59, #65, #66, #76-#78 NOT RECOVERED**. |
| `implementation_plan.md` + `_supplement.md` | The 9-phase plan and the S1-S8 briefs. Original, restored, untouched. |
| `recovery/` | `RECOVERY_MANIFEST.md`, `reports_from_transcript.md` (the 20 source reports), `recovery_report.md` (why git could not help), `consolidation_report.md`, and the state snapshots. |

## Where the work actually stands

Verified in the repository today, not from a report:

- **HEAD is `be2153c8bc062db870ecdc5f8072c02ae8b7cd2b`** ("phase 8 added", `abdalla`,
  2026-11-09 12:19:59), and `origin/developer_18` matches it. The working tree is clean.
- **The sign-client gate is committed and pushed** - `be2153c` contains
  `isky_18_realestate_developer_sales_crm/security/security.xml`,
  `models/config/approval_settings.py` and `tests/test_sign_client_gate.py`. The earlier
  "commits are held" rule no longer describes reality; whether it still applies going forward is
  the owner's call.
- **101 gate logs survive** in `claude/logs/`, each with its run ID, start time and exit code. They
  are the evidence base for every table in `plan_status.md`, and they are also the only surviving
  record for the phases marked `NOT RECOVERED`.
- All four lint scripts survive in `claude/scripts/`, with `run_gate.sh`.

## Phase status, as far as the record supports

| Phase | State | Source |
|---|---|---|
| 1, 2, 3 (steps 1-6) | CLOSED | original snapshot |
| 4 — Commission (L3) | closure **NOT RECOVERED**; the 2026-11-06 section records "Core: PASS. One gate RED" | — |
| 5 — Construction (L4) | **CLOSED** | `[RECONSTRUCTED]` <!-- transcript line 1048 --> |
| 6 — Settings | **NOT RECOVERED** (known only by its gap G4, which Phase 8 then closed) | — |
| 7 — Client values | **CLOSED** | `[RECONSTRUCTED]` <!-- transcript line 1080 --> |
| 8 — Broker branch | **CLOSED** | `[RECONSTRUCTED]` <!-- transcript line 1192 --> |
| 3c — UI migration | steps 1 and 2a **CLOSED**; steps 2b, 3, 4, 5, 6 **NOT RECOVERED** | <!-- transcript line 1204 --> / <!-- transcript line 1214 --> |
| 9 — Extract core | **ON HOLD**, pending its target branch | original snapshot |

## Next action

**Updated 2026-11-10 — two of the three waiting items are now done:**

1. **`.gitignore:6` — FIXED (backlog #82).** Lines 7-8 (`!claude/`, `!claude/**/*.md`) make every
   `claude/` markdown file visible to git; nothing outside `claude/` changed. **The docs still
   need a commit to gain history** - visibility alone does not protect them. That commit is the
   single most valuable next step.

2. **The signing questions — DECIDED AND BUILT (SG-D1..D4, 2026-11-10).** One signer group,
   `director_manager_group`, signs `signed_client`, `signed_by_client` and `signed_ceo`; the gates
   sit in `NON_CONFIGURABLE_GATES`, so `approval_enabled = False` no longer skips signing. **The
   Sales Team Lead no longer signs** - the owner must confirm this consequence before the diff is
   merged (SG-D1). This supersedes the unimplemented CEO-D1..D3 split. See `plan_status.md`,
   "Signing gate, always enforced".

3. **The two open audit findings**, both release-relevant: **#80**, commission releases with no
   collection check and the amount never follows the money (plus the "Generate Commissions" button
   raising `AttributeError` on every press); and **#81**, a salesperson can return a collected
   cheque and commission does not follow it back out.

Also outstanding from the original record and **not** reconstructable: whatever the original
HANDOVER listed as the agreed work order. Backlog #52 (the empty-group ACL rows) was the release
blocker in the 2026-11-06 snapshot's work order and nothing in the pack says it closed; its audit
report is itself `NOT RECOVERED`, though `claude/logs/acl52_*.log` survive.

## The rules that have not changed

From the original snapshot, still in force:

- No edits to the legacy repos (`arkzayed`, `marketstandards`) - both verified at zero changed
  files today.
- Legacy modules inside this repo (`arkzayed_*`) are edited only under an explicit, dated owner
  exception; Phase 3c's covered view, menu and report records only.
- Every decision goes in `decisions_log.md` **before** the code (rule 6).
- Every gate run logs its run ID, start time and exit code to its own file in `claude/logs/`.
