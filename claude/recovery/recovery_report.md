# Recovery check: can the lost `claude/` docs be restored from git?

Read-only run, 2026-11-09. Nothing was written, deleted, moved, stashed, checked out, reset,
cleaned, gc'd or committed. No `git add`. The index and the working tree are untouched apart from
the two files this task asked for: `claude/logs/recovery_state_before.txt` and this report.

HEAD at the time of the check: **`be2153c8bc062db870ecdc5f8072c02ae8b7cd2b`** on `developer_18`,
clean tree.

---

## 1. The answer, per file

**NOT-FOUND, all of them.** Not one of the lost documents exists in git in any form - no committed
version, no blob, no stash, no other ref.

| File | Verdict |
|---|---|
| `claude/plan_status.md` | **NOT-FOUND** |
| `claude/decisions_log.md` | **NOT-FOUND** |
| `claude/bug_backlog.md` | **NOT-FOUND** |
| `claude/HANDOVER.md` | **NOT-FOUND** |
| `claude/INDEX.md` | **NOT-FOUND** |
| `claude/implementation_plan.md` | **NOT-FOUND** |
| `claude/implementation_plan_supplement.md` | **NOT-FOUND** |
| `claude/phase6_settings_inventory.md` | **NOT-FOUND** |
| `claude/acl_audit_52_report.md` | **NOT-FOUND** |
| `claude/commission_flow_trace.md` | **NOT-FOUND** |
| `claude/returned_cheque_path.md` | **NOT-FOUND** |
| `claude/signed_by_client_state.md` | **NOT-FOUND** |
| the prompt files (`acl_draft_prompt.md`, `s7_approval_settings_spec.md`, and the rest) | **NOT-FOUND** |

**No blob was found for any lost file**, so the stop-and-report condition on a matching blob was
never reached. Why that is not a surprise, and why it is conclusive rather than a gap in the
search: a file ignored by `.gitignore` and never `git add`-ed is never hashed, so git has no object
for it to lose. The empirical check below confirms the reasoning rather than relying on it.

### What this is *not*

The premise in the task was that the folder may have been "overwritten or replaced", with the work
possibly surviving "as git objects that were never referenced". Neither holds:

- The files were **deleted, not overwritten** - the directory simply has no `.md` in it.
- There are **no unreferenced objects at all** (`git fsck --unreachable` returns zero), so there is
  nothing orphaned to rescue.
- The task also says "commits are on hold by owner decision, so the work may exist only as
  uncommitted files". In fact **a commit did happen**: `be2153c` is dated 2026-11-09 12:19:59 by
  `abdalla` and contains the code - `security.xml`, `approval_settings.py`,
  `test_sign_client_gate.py`. `origin/developer_18` matches it. So all the *code* is committed and
  pushed and safe; only the `.md` documents are gone, because a commit cannot pick up an ignored
  file.

---

## 2. The `.gitignore` finding

**Yes - line 6 is the cause.** `git check-ignore -v` names it for every single lost file:

```
     5	.*
     6	*.md          <-- this
     7	*.pyc
     8	*.sql
     9	!.gitignore
```

```
.gitignore:6:*.md	claude/plan_status.md
.gitignore:6:*.md	claude/decisions_log.md
.gitignore:6:*.md	claude/bug_backlog.md
.gitignore:6:*.md	claude/HANDOVER.md
... identical for all 14 paths checked
```

`*.md` is unanchored, so it matches at **every depth** in the repository - the whole project record
was invisible to git from the day it was written. Two consequences worth stating plainly:

- `git ls-files claude/` returns **107 tracked files, of which zero are `.md`**: 101 logs, 5
  scripts, 1 patch. The logs survived the incident precisely *because* nothing ignores `*.log`.
- No `.md` file has **ever** been committed anywhere in this repository. Checked across all 18
  commits on all 10 refs: `claude/*.md` appears in 0 commits, and `.md` appears in 0 trees.

Note also line 5, `.*`, which ignores every dotfile, and line 22, `status`, which would ignore a
file named exactly `status`. Neither is involved here, but the same unanchored-pattern habit runs
through the file.

---

## 3. Commands run, with exit codes

| Step | Command | Exit | Finding |
|---|---|---|---|
| 1 | `git rev-parse HEAD` | 0 | `be2153c8bc062db870ecdc5f8072c02ae8b7cd2b` |
| 1 | `git log --oneline -5` | 0 | be2153c, 7ff7d9e, a99b10e, 0148c7e, 7dd038e |
| 1 | `git status --porcelain` | 0 | clean but for this run's two new files |
| 2 | `git ls-files claude/` | 0 | 107 files, **0 `.md`** |
| 2 | `git ls-files \| grep -c .` | 0 | 1982 tracked files in the repo |
| 2 | `git ls-files --error-unmatch claude/<file>` ×12 | 1 each | every lost file **not tracked** |
| 3 | `cat -n .gitignore` | 0 | 57 lines; line 6 is `*.md` |
| 3 | `git check-ignore -v claude/<file>` ×14 | 0 each | all matched by `.gitignore:6` |
| 4 | `git log --oneline --all -- claude/` | 0 | 5 commits, all touching logs/scripts only |
| 4 | `git log --all --format=%H -- 'claude/*.md'` | 0 | **0 commits** |
| 4 | `git ls-tree -r --name-only <every ref> \| grep '\.md$'` | 0 | **0 hits on all 10 refs** |
| 5 | `git count-objects -v` | 0 | 720 loose, 2327 packed, garbage 0 |
| 5 | `git fsck --unreachable --no-reflogs` | 0 | **0 unreachable objects** |
| 5 | `git cat-file --batch-all-objects` + per-blob title scan | 0 | 2449 blobs scanned, **0 document matches** |
| 6 | `git stash list` | 0 | **no stashes** |
| 6 | `git reflog -n 30` | 0 | 10 entries; see below |
| 6 | `git branch -a` / `git tag` / `git for-each-ref` | 0 | 5 local + 5 remote branches, **0 tags** |
| 7 | `ls -la claude/` + `find` for `*~ *.swp *.bak .#*` | 0 | **no backup, swap or temp files** |
| 8 | `find / -name plan_status.md …` | 0 | **no other copy on disk** |

### A deviation from the task, and why

Step 5 asked for `git fsck --lost-found`, noting it writes only to `.git/lost-found`. I ran
`git fsck --unreachable --no-reflogs` instead: it returns the same hashes and writes **nothing at
all**. Given the instruction to avoid writes, the read-only form was the better match for the
intent, and since it found zero unreachable objects there was nothing `--lost-found` could have
materialised.

### The blob scan, in detail

Two passes over all 2,449 blobs in the store, loose and packed:

1. **Title scan** for `Plan Status`, `Decisions Log`, `Bug Backlog`, `HANDOVER`,
   `Implementation Plan`, `What is in this folder`, `access-rule audit`,
   `Commission flow as the code runs`, `Returned cheques: what the UI`, `Signed by client`,
   `Work order`, `settings inventory`. **13 hits, all false positives**: the handover *report*
   views and controller (`handover_report_tree`, `paperformat_handover_report`,
   `handover_report_xlsx.py`), the Phase 6 settings *views*, and `run_gate.sh`. No document.
2. **Markdown-shape scan** for any blob whose first line begins `# ` or `## `. **231 hits, all
   false positives**: Python headers (`# -*- coding: utf-8 -*-`), `.po` files
   (`# Translation of Odoo Server.`), `__init__.py` load-order comments, and `.gitignore` itself.
   **Zero markdown documents in the entire object store.**

### Reflog, for the record

```
be2153c HEAD@{0}: checkout: moving from broker to developer_18
27d94f6 HEAD@{1}: checkout: moving from developer_18 to broker
be2153c HEAD@{2}: commit: phase 8 added
7ff7d9e HEAD@{3}: commit: till phase 7
...
4fbc36c HEAD@{9}: commit (initial): initial commit
```

The branch switch at `HEAD@{1}`/`HEAD@{0}` is when every surviving file acquired its
`Nov 9 12:34` mtime. A checkout on its own does not remove ignored files, so a separate step that
targets ignored files (a `clean` variant that includes them) is the only thing that fits: `*.md`
went, `*.log` stayed, and `*.log` is the one of those two that **is not** ignored. Nothing in the
reflog records a `clean`, because git does not log it - so this is inference from the evidence, not
a recorded fact.

---

## 4. What was written to the scratch folder

**Nothing, because there was nothing to extract.** Step 4 instructed me to save the latest
committed version of each tracked file; no lost file is tracked, so no file was produced. For the
same reason `/home/claude/recovery/` was never created - I did not test it for writability, since
there was nothing to put in it.

The only two files this run created, both explicitly requested:

| Path | Contents |
|---|---|
| `claude/logs/recovery_state_before.txt` | step 1's state capture, 21 lines |
| `claude/recovery_report.md` | this report |

---

## 5. Where the documents *can* come from

Git is a dead end. These are not:

| Source | What it holds | Confidence |
|---|---|---|
| This session's transcript, `c04d7dfd-…jsonl` (11 MB) | the **full authored text** of `acl_audit_52_report.md` (3 occurrences), `commission_flow_trace.md` (2), `returned_cheque_path.md` (2), `signed_by_client_state.md` (1), and every `plan_status`/`decisions_log`/`bug_backlog`/`HANDOVER` block written on 8-9 Nov, including the whole "Sign-client gate" section and the Phase 3c closure | **high** - these were written through heredocs, so the exact bytes are in the transcript |
| Session `3a43631c-…jsonl` (15 MB, 7 Nov) | the Phase 4-7 era: the 12.2 closure entry, the Phase 4 closure, and the doc edits of that period | **partial** - fragments read and written, not whole files |
| `/tmp/claude-1000/_sbc_head.md` (49 lines), `_sbc_body.md` (160 lines) | sections 0-3 of `signed_by_client_state.md`, near-complete | high |
| `/tmp/claude-1000/_acl52_table.md` (56 lines) | the #52 per-row decision table | high |
| `claude/logs/` - 101 logs | every gate's run ID, start time, exit code and test tally, which is the evidence base the plan_status tables were built from | **complete** |
| `claude/scripts/` - 5 files | all four lints and `run_gate.sh`, untouched | **complete** |

So a reconstruction is realistic for the recent and audit-heavy material, and partial for the
Phases 1-8 history in `plan_status.md` and `decisions_log.md` - the bulk of which predates both
transcripts and was only ever read in fragments. `implementation_plan.md` and its supplement are
the weakest: they were inputs I read, never wrote, so only the parts quoted in conversation survive.

One correction to the current directory state, made before this run and noted here so the next
reader is not misled: my step-0 append during the aborted 2026-11-09 CEO-stage run **recreated**
`claude/decisions_log.md` containing only that run's 45 new lines. It is now
`claude/decisions_log.CEO-D1-D3-only.PARTIAL.md`, so no file at `decisions_log.md` pretends to be
the project log. Reverse with a single `mv` if preferred.

---

## 6. The one-line fix for the cause

`*.md` on line 6 of `.gitignore` is why a routine git operation erased the project record. The
documents cannot be protected by git until that changes - either narrow the rule, or add a negation
for the docs folder, for example `!claude/` or `!claude/**/*.md` after line 6. Until then, every
`.md` in this repository remains one `clean` away from deletion, with no history to fall back on.
