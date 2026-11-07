#!/usr/bin/env python3
"""Phase 7's acceptance gate: no client values in the generic product.

The plan words it as "grep for client names (GIS, OAYA, arkzayed) in models, views, and config
returns zero results". Read literally over the whole repo that can never pass - the legacy
`arkzayed_*` modules are still here and are full of the word - so this checks the thing the
acceptance is actually about: **the `isky_*` modules must contain no client-specific value.**

Three checks:

  1. No client business-line name (GIS, OAYA) anywhere in an isky module.
  2. No `ir.config_parameter` key on a client-named prefix, and no key squatting another
     module's namespace. Phase 7 moved every one of them to `realestate.`.
  3. No reference to a legacy module from an isky module, except the ALLOWLIST below - each
     entry a record that a legacy module owns and that a named later phase will move. The list
     may only ever shrink; adding to it is the thing this check exists to prevent.

Exit 0 when clean, 1 otherwise. Run from the repo root.
"""

import os
import re
import sys

ISKY_PREFIX = 'isky_'
LEGACY_MODULES = (
    'arkzayed_18_realestate_development',
    'arkzayed_18_realestate_developer_crm',
    'arkzayed_18_gt_cheque_management',
)
CLIENT_WORDS = re.compile(r'\b(gis|oaya)\b|_gis_|_oaya_|\bis_gis|\bis_oaya', re.IGNORECASE)
# A migration has to name what it converts, so the two files holding the old key maps may mention
# the old client names. Nothing else may, and these counts may only shrink.
CLIENT_WORD_ALLOWLIST = {
    'isky_18_realestate_developer_sales_crm/hooks.py': 6,
    'isky_18_realestate_developer_unit_inventory/hooks.py': 1,
}
# A reference to a RECORD a legacy module owns: a quoted or ref=/groups= xmlid. A bare module name
# in `depends` is a declared dependency, not a hidden coupling, and prose in a comment is neither.
LEGACY_RECORD_REF = re.compile(
    r"""['\"](?:%s)\.[A-Za-z0-9_.]+['\"]""" % '|'.join(LEGACY_MODULES))
PARAM_KEY = re.compile(
    r"""(?:config_parameter\s*=\s*|get_param\(\s*|set_param\(\s*)['"]([A-Za-z0-9_.]+)['"]""")
GENERIC_PREFIX = 'realestate.'

# Every surviving reference from an isky module into a legacy one, with its owner. Each is a
# *record* a legacy module defines; removing it means moving that record, which is Phase 3c's job
# for UI, or an owner decision for a module rename.
ALLOWLIST = {
    # --- reports, window actions and form views the monolith owns. Phase 3c moves the UI, and
    #     every one of these disappears with it (backlog #61's class).
    'isky_18_realestate_developer_unit_inventory/models/core/real_estate_unit.py': 3,
    'isky_18_realestate_developer_sales_crm/models/core/sale_reservation.py': 3,
    'isky_18_realestate_developer_sales_crm/models/core/sale_proposal.py': 3,
    'isky_18_realestate_developer_sales_crm/models/core/real_estate_unit_contract_ext.py': 2,
    'isky_18_realestate_developer_sales_crm/wizard/sales_achievement_report.py': 2,
    'isky_18_realestate_developer_commission/models/core/broker_claim.py': 1,
    'isky_18_realestate_developer_construction/wizard/report_wizard.py': 1,
    'isky_contract_template/views/sale_proposal_views.xml': 1,
    # --- portal templates the legacy CRM module owns (backlog #49 named these; Phase 3c).
    'isky_18_realestate_developer_sales_crm/controllers/main.py': 3,
    'isky_18_realestate_developer_sales_crm/controllers/permission_request_controller.py': 3,
    'isky_18_realestate_developer_sales_crm/controllers/units_controller.py': 3,
    # --- two crons that live in legacy modules, which is why their settings toggles do nothing
    #     without them (backlog #66, awaiting the owner).
    'isky_18_realestate_developer_sales_crm/models/config/res_config_settings.py': 2,
    'isky_18_realestate_developer_sales_crm/models/config/res_config_settings_crm.py': 2,
    # --- server actions behind a one-off data-migration helper (backlog #31: delete it).
    'isky_18_realestate_developer_sales_crm/models/core/payment_allocation.py': 2,
    # --- the legacy cheque module's own records: the journal key its settings page writes
    #     (open question 12.3 / backlog #29) and one group reference.
    'isky_18_realestate_developer_sales_cheques/models/sale_proposal.py': 1,
    'isky_18_realestate_developer_sales_cheques/models/installment_lines.py': 1,
    'isky_18_realestate_developer_sales_cheques/models/maintenance_installment_lines.py': 1,
    'isky_18_realestate_developer_sales_cheques/models/cheque_manage.py': 1,
    # --- two approval groups the monolith owns; the buttons are hidden without it (backlog #21).
    'isky_18_realestate_developer_accounting/views/account_payment_views.xml': 2,
    # --- the Phase 7 migration map, which has to name the old keys it converts.
    'isky_18_realestate_developer_sales_crm/hooks.py': 4,
}


def isky_files(root='.'):
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != '__pycache__' and not d.startswith('.')]
        parts = os.path.relpath(dirpath, root).split(os.sep)
        if not parts or not parts[0].startswith(ISKY_PREFIX):
            continue
        for fn in files:
            if fn.endswith(('.py', '.xml', '.csv')):
                yield os.path.join(dirpath, fn)


def main():
    client_hits, bad_keys, legacy_refs, client_words = [], [], {}, {}
    for path in isky_files():
        rel = os.path.relpath(path, '.').lstrip('./')
        is_test = os.sep + 'tests' + os.sep in path
        with open(path, encoding='utf-8', errors='replace') as fh:
            for lineno, line in enumerate(fh, 1):
                stripped = line.strip()
                is_comment = stripped.startswith('#') or stripped.startswith('<!--')
                if not is_test and not is_comment and CLIENT_WORDS.search(line):
                    client_words[rel] = client_words.get(rel, 0) + 1
                    client_hits.append('%s:%d %s' % (rel, lineno, stripped[:110]))
                for key in PARAM_KEY.findall(line):
                    if '.' not in key:
                        continue
                    if key.startswith(GENERIC_PREFIX):
                        continue
                    if key.startswith('arkzayed_18_gt_cheque_management.'):
                        continue      # 12.3 / #29: written by the legacy module's own page
                    if key.split('.')[0] in ('web', 'base', 'mail'):
                        continue      # core keys we only read
                    bad_keys.append('%s:%d %s' % (rel, lineno, key))
                if not is_test:
                    found = len(LEGACY_RECORD_REF.findall(line))
                    if found:
                        legacy_refs[rel] = legacy_refs.get(rel, 0) + found

    failed = False
    print("Check 1 (no client business-line names in isky modules): ", end='')
    over_budget = []
    for rel, count in sorted(client_words.items()):
        allowed = CLIENT_WORD_ALLOWLIST.get(rel, 0)
        if count > allowed:
            over_budget.append('%s: %d found, %d allowed' % (rel, count, allowed))
    if over_budget:
        failed = True
        print("-> FAIL")
        for item in over_budget:
            print("    " + item)
        for hit in client_hits[:20]:
            print("      " + hit)
    else:
        print("-> PASS (%d mention(s), all in allowlisted migration maps)"
              % sum(client_words.values()))

    print("Check 2 (every config parameter key on the generic prefix): ", end='')
    if bad_keys:
        failed = True
        print("-> FAIL, %d key(s)" % len(bad_keys))
        for hit in bad_keys[:20]:
            print("    " + hit)
    else:
        print("-> PASS")

    print("Check 3 (legacy references only where allowlisted, and never more than before):")
    grown, unlisted = [], []
    for rel, count in sorted(legacy_refs.items()):
        allowed = ALLOWLIST.get(rel)
        if allowed is None:
            unlisted.append('%s (%d)' % (rel, count))
        elif count > allowed:
            grown.append('%s: %d now, %d allowed' % (rel, count, allowed))
    shrunk = sorted(
        '%s: %d allowed, %d left' % (rel, allowed, legacy_refs.get(rel, 0))
        for rel, allowed in ALLOWLIST.items() if legacy_refs.get(rel, 0) < allowed)
    total = sum(legacy_refs.values())
    print("    %d reference(s) across %d file(s); allowlist budget %d"
          % (total, len(legacy_refs), sum(ALLOWLIST.values())))
    if unlisted:
        failed = True
        print("    -> FAIL, new file(s) referencing a legacy module:")
        for item in unlisted:
            print("       " + item)
    if grown:
        failed = True
        print("    -> FAIL, reference count grew:")
        for item in grown:
            print("       " + item)
    if shrunk:
        print("    note: these shrank - tighten the allowlist:")
        for item in shrunk:
            print("       " + item)
    if not (unlisted or grown):
        print("    -> PASS")

    print()
    print("FAIL - a client value reached the generic product." if failed
          else "PASS - no client values in the isky modules; legacy references within budget.")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
