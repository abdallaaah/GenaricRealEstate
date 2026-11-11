# Recovery manifest: GenaricRealEstate claude/ docs (2026-11-09)

## Sources, in order of trust

1. base_nov6/ : snapshot of the docs as uploaded to this session, last written 2026-11-06 23:37-23:38.
   Covers history up to the 12.2 ACL closure and the work order decided 2026-11-06.
   Files: bug_backlog.md (371 lines), decisions_log.md (1243), plan_status.md (1144),
   implementation_plan.md (165), implementation_plan_supplement.md (142), s8_cheque_settings_prompt.md (37).
2. reports_from_transcript.md : the 20 long Claude Code reports from 2026-11-07 to 2026-11-09, extracted verbatim
   from the session transcript (user messages carrying Claude Code's gate reports). Each block is tagged with its transcript line.
3. Prompts written in this session are already saved on disk in /home/claude/sync/claude/ and in the project.
   These are the authoritative text for the prompts (acl_audit_52, commission_flow_trace, returned_cheque_path,
   signed_by_client_state, sign_client_gate, sign_ceo_gate, phase6_settings, task60, sync_docs, recovery_check).

## Not recoverable as structured files

- The closure sections, decision entries and backlog edits written to the repo docs on 2026-11-07 to 2026-11-09
  exist only as prose inside reports_from_transcript.md. They must be re-entered by hand or by Claude Code from those reports.
- Files that never existed in the transcript as text: implementation_plan.md and implementation_plan_supplement.md were
  only ever read. base_nov6 is their only source.
- phase6_settings_inventory.md and INDEX.md: not found in any source.
- The four audit reports (acl_audit_52_report.md, commission_flow_trace.md, returned_cheque_path.md,
  signed_by_client_state.md): their full text is in reports_from_transcript.md (the Claude Code reports carry the same content).

## Gaps

- Phases 1 to 3 history before 2026-11-06 is intact in base_nov6.
- Anything written to the repo docs between 2026-11-06 23:38 and the loss, that was not reported in a Claude Code message, is lost.
