# Consolidation of `claude/` after the 2026-11-09 docs loss

Run 2026-11-09. No code, manifest, test or legacy file touched; no `isky_*` module and no
`RealEstateFacility` file touched; nothing committed. HEAD unchanged at
`be2153c8bc062db870ecdc5f8072c02ae8b7cd2b`.

## Moves

| # | From | To | exit |
|---|---|---|---|
| 1 | `claude/claude_files/bug_backlog.md` | `claude/bug_backlog.md` | 0 |
| 2 | `claude/claude_files/decisions_log.md` | `claude/decisions_log.md` | 0 |
| 3 | `claude/claude_files/implementation_plan.md` | `claude/implementation_plan.md` | 0 |
| 4 | `claude/claude_files/implementation_plan_supplement.md` | `claude/implementation_plan_supplement.md` | 0 |
| 5 | `claude/claude_files/plan_status.md` | `claude/plan_status.md` | 0 |
| 6 | `claude/claude_files/s8_cheque_settings_prompt.md` | `claude/s8_cheque_settings_prompt.md` | 0 |
| — | `claude/claude_files/` (empty) | removed by `rmdir` | 0 |
| 7 | `RECOVERY_MANIFEST.md` | `claude/recovery/RECOVERY_MANIFEST.md` | 0 |
| 8 | `reports_from_transcript.md` | `claude/recovery/reports_from_transcript.md` | 0 |
| 9 | `claude/recovery_report.md` | `claude/recovery/recovery_report.md` | 0 |

All nine used `mv -n`. **No collision occurred**; a pre-flight check compared every source basename
against `claude/` first and found none present.

Two operations beyond the moves, both necessary and both reported rather than silent:

- The six restored files arrived mode `-r--r--r--`. They were `chmod u+w`'d, because steps 4 to 6
  require appending to four of them. No other permission changed.
- `claude/decisions_log.CEO-D1-D3-only.PARTIAL.md` was merged into `decisions_log.md` under the
  required heading and then deleted. Its text was carried over verbatim; the merge note records
  that **the code those decisions describe was never written**.

## `[RECONSTRUCTED]` counts

| File | tags | `NOT RECOVERED` | lines before → after |
|---|---|---|---|
| `plan_status.md` | 17 | 7 | 1144 → 1462 |
| `decisions_log.md` | 12 | 0 | 1243 → 1432 |
| `bug_backlog.md` | 20 | 6 | 371 → 501 |
| `HANDOVER.md` | 4 | 6 | created, 85 |

Each tag names the transcript line of the report it came from, as
`<!-- transcript line N -->`. Run IDs, exit codes and counts are copied exactly.

## `NOT RECOVERED` list

- Phase 4 closure (2026-11-07)
- Backlog #49 closure (2026-11-07) — the finding survives, the fix run does not
- Phase 6 (2026-11-07), and `phase6_settings_inventory.md`
- Phase 3c steps 2b, 3, 4, 5, 6 (2026-11-08)
- The #52 ACL audit report (2026-11-08)
- The CEO signing gate **as implementation** — decisions survive, code never existed
- Backlog items **#55-#59, #65, #66, #76, #77, #78**
- `INDEX.md`
- The original `HANDOVER.md` in full — its work order, open-decision list and "first action" text

In every case `claude/logs/` still holds the relevant gate logs with their run IDs and exit codes,
which is the only surviving evidence for those phases.

## `.gitignore` — report only, not changed

Line 6 is `*.md`, unanchored, so it matches at every depth and hid the whole project record from
git. The documents were never tracked, which is why none could be recovered.

The negation must come **after** line 6 to take effect. Either of these works; the second is
narrower:

```
# after line 6 (*.md)
!claude/**
```

```
# after line 6 (*.md), narrower - only the docs, not the logs
!claude/*.md
!claude/**/*.md
```

Note that `claude/logs/*.log` and `claude/scripts/*` are already tracked, so a `!claude/**` rule
changes nothing for them. **Not applied** - this is the owner's decision, recorded as backlog #82.

Until it is applied, every document rebuilt in this run is still invisible to `git status` and
still one `clean` away from deletion with no history behind it. That includes this report.
