# S8: Cheque settings and the #34 fix (Claude Code prompt)

Source of decision: `claude/decisions_log.md` (2026-11-05 entry). Backlog: #34 (create_cheque credit_account NOT NULL), #33 (Phase 7 rename).

## Scope
Branch: `new` (GenaricRealEstate). Do not edit legacy repos (arkzayed, marketstandards).
Timing: before Phase 3 step 5. Closes Phase 3 steps 3 and 4.

## Work

1. Incoming cheque credit account (setting, Financials, company-level)
   - Add a company-level field `cheque_incoming_credit_account_id` (Many2one `account.account`). Put it in the module that owns cheque config: `sales_cheques` if the setting is sales-facing, otherwise the L1 cheque module. Record the choice in plan_status.md.
   - Every path that creates `cheque.manage` reads this setting. Known paths: `action_create_cheque` and `sale.proposal._generate_cheques()`. Grep for every `cheque.manage` create call and cover each one.
   - No caller passes its own credit account. `default_get` must not overwrite a value the caller already set.
   - If the setting is empty when a creating path runs: raise `UserError` with a message that names the setting. The NOT NULL constraint must never fire.

2. Sales-linked cheque toggle (setting, Sales Setup)
   - Add `cheques_enabled` (Boolean, company-level).
   - Gate cheque generation from `sale.proposal` on it. When off, no cheque is generated from a deal. Manual cheque use is unaffected.
   - Show it in the Sales Setup form only when `sales_cheques` is installed.

3. Tests (add to the Phase 3 gate)
   - `test_cheque_create_with_setting`: set the account, create on an empty DB, expect success.
   - `test_cheque_create_without_setting`: setting empty, expect UserError naming the setting, no NOT NULL error.
   - `test_cheque_generation_toggle_off`: cheques_enabled False, sale.proposal generates no cheque.
   - `test_default_get_keeps_caller_value`: caller sets the credit account, default_get does not overwrite it.
   - Run each mode with the wrapper scripts (run_odoo.sh). Each report carries run ID, start time and exit code from its own log.

4. Close-out
   - plan_status.md: mark Phase 3 steps 3 and 4 closed, list test names and run IDs.
   - bug_backlog.md: #34 to FIXED-IN-NEW with commit hash and test names. Remove the uncovered-path note only after the create test passes.

## Constraints
- No DB password in the repo. Use `-h localhost -U odoo18` with PGPASSWORD.
- No behavior change in Mode A or Mode B outside the cheque paths named above.
- Lint must pass: `claude/scripts/lint_guard_pattern.py` (both checks).
- Report back: files changed, test table with run IDs, and any path still uncovered.
