#!/usr/bin/env python3
"""S4 compliance lint: views and menus (supplement S4).

Three checks, matching S4's acceptance list:

  1. A standalone view (no inherit_id) for model X must live in the module that declares
     X's `_name`. An `inherit_id` extension may live anywhere - extending another module's
     model is the whole point of a bridge.
  2. Every `action=` on a menuitem must resolve to an action record defined in the same
     module or in one of its declared dependencies (transitively).
  3. Every `parent=` on a menuitem must resolve the same way.

Scope: the isky_18_realestate_developer_* modules. Legacy modules are reported as
INFORMATIONAL only - they are the migration backlog, not a failure, until their UI moves.

Run after any view or menu change:
    python3 claude/scripts/lint_s4_views.py
Exit 0 = pass, 1 = fail.
"""
import ast
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PREFIX = 'isky_18_realestate_developer_'

# Narrow exceptions to check 1, each one a standalone view of ANOTHER layer's model, allowed
# because every field it renders belongs to the declaring module - so the view cannot live in the
# model's own layer (which has not got the fields) and it is not a legacy module holding our UI,
# which is what check 1 exists to catch. Phase 3c step 6 (S6-D3). This list may only shrink.
CHECK1_EXCEPTIONS = {
    # the construction-progress lists: progress columns only, on L0's unit and building
    ('isky_18_realestate_developer_construction/views/unit_building_progress_views.xml',
     'real.estate.unit'),
    ('isky_18_realestate_developer_construction/views/unit_building_progress_views.xml',
     'real.estate.building'),
}


def module_dirs():
    for name in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, name)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, '__manifest__.py')):
            yield name, p


def read_manifest(path):
    try:
        return ast.literal_eval(open(os.path.join(path, '__manifest__.py'), encoding='utf-8').read())
    except Exception:
        return {}


def _class_name_and_inherit(node):
    """(_name, [_inherit...]) for one class body."""
    name, inherit = None, []
    for st in node.body:
        if not isinstance(st, ast.Assign):
            continue
        for t in st.targets:
            if not isinstance(t, ast.Name):
                continue
            if t.id == '_name' and isinstance(st.value, ast.Constant):
                name = st.value.value
            elif t.id == '_inherit':
                if isinstance(st.value, ast.Constant):
                    inherit = [st.value.value]
                elif isinstance(st.value, (ast.List, ast.Tuple)):
                    inherit = [e.value for e in st.value.elts
                               if isinstance(e, ast.Constant)]
    return name, inherit


def model_owners(mods):
    """model name -> the module that DEFINES it.

    A class may carry both `_name` and `_inherit` - this repo uses that pattern to extend a model
    while keeping its name (crm_lead.py explains why: without `_name`, a list `_inherit` makes Odoo
    treat the class as a new anonymous model). Such a class is an **extension**, not the owner, and
    it is told apart by its own name appearing in its `_inherit`.

    Before Phase 3c step 2 this function took the first module alphabetically, which credited
    `sale.proposal`, `eoi.eoi` and `real.estate.sale.reservation` to `commission` - whose classes
    extend them - instead of `sales_crm`, which defines them. That mis-stated the per-layer
    migration backlog and could have let check 1 pass on a misplaced view.
    """
    definers = defaultdict(set)
    extenders = defaultdict(set)
    for name, path in mods.items():
        for dp, _, fs in os.walk(path):
            if '__pycache__' in dp:
                continue
            for fn in fs:
                if not fn.endswith('.py'):
                    continue
                try:
                    tree = ast.parse(open(os.path.join(dp, fn), encoding='utf-8').read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue
                    model, inherit = _class_name_and_inherit(node)
                    if not model:
                        continue
                    if model in inherit:
                        extenders[model].add(name)
                    else:
                        definers[model].add(name)

    owners = {}
    for model, mods_defining in definers.items():
        real = sorted(mods_defining)
        # a module that only extends never owns; when more than one module defines the same
        # model, prefer an isky module - the legacy copies are what this refactor is removing
        isky = [m for m in real if m.startswith(PREFIX)]
        owners[model] = (isky or real)[0]
    for model, mods_extending in extenders.items():
        owners.setdefault(model, sorted(mods_extending)[0])
    return owners


def xml_files(path):
    for dp, _, fs in os.walk(path):
        if '__pycache__' in dp:
            continue
        for fn in fs:
            if fn.endswith('.xml'):
                yield os.path.join(dp, fn)


def record_ids(path, module):
    """xmlids defined by this module, both bare and module-qualified"""
    ids = set()
    for f in xml_files(path):
        s = open(f, encoding='utf-8', errors='ignore').read()
        for m in re.finditer(r'<record[^>]*\bid="([^"]+)"', s):
            ids.add(m.group(1))
            ids.add('%s.%s' % (module, m.group(1)))
        for m in re.finditer(r'<menuitem[^>]*\bid="([^"]+)"', s):
            ids.add(m.group(1))
            ids.add('%s.%s' % (module, m.group(1)))
        for m in re.finditer(r'<template[^>]*\bid="([^"]+)"', s):
            ids.add(m.group(1))
            ids.add('%s.%s' % (module, m.group(1)))
    return ids


def closure(module, manifests, seen=None):
    if seen is None:
        seen = set()
    for dep in manifests.get(module, {}).get('depends', []) or []:
        if dep not in seen:
            seen.add(dep)
            closure(dep, manifests, seen)
    return seen


def main():
    mods = dict(module_dirs())
    manifests = {n: read_manifest(p) for n, p in mods.items()}
    owners = model_owners(mods)
    ours = [n for n in mods if n.startswith(PREFIX)]

    ids_by_module = {n: record_ids(mods[n], n) for n in mods}

    fail_view, fail_action, fail_parent, info = [], [], [], []

    for mod in sorted(ours):
        reachable = set(ids_by_module[mod])
        for dep in closure(mod, manifests):
            reachable |= ids_by_module.get(dep, set())

        for f in xml_files(mods[mod]):
            rel = os.path.relpath(f, ROOT)
            s = open(f, encoding='utf-8', errors='ignore').read()

            # check 1: standalone views belong to the owning module
            for m in re.finditer(r'<record\b[^>]*model="ir\.ui\.view"[^>]*>(.*?)</record>',
                                 s, re.S):
                body = m.group(1)
                if 'inherit_id' in body:
                    continue
                mm = re.search(r'<field name="model">([a-z0-9_.]+)</field>', body)
                if not mm:
                    continue
                model = mm.group(1)
                own = owners.get(model)
                if own != mod and (rel, model) not in CHECK1_EXCEPTIONS:
                    fail_view.append(
                        "%s: standalone view for '%s' (owned by %s)"
                        % (rel, model, own or 'a non-isky module'))

            # checks 2 and 3: menu references resolve
            for m in re.finditer(r'<menuitem\b[^>]*>', s):
                tag = m.group(0)
                mid = re.search(r'\bid="([^"]+)"', tag)
                for attr, bucket in (('action', fail_action), ('parent', fail_parent)):
                    am = re.search(r'\b%s="([^"]+)"' % attr, tag)
                    if not am:
                        continue
                    ref = am.group(1)
                    if ref not in reachable:
                        bucket.append("%s: menuitem '%s' %s=\"%s\" does not resolve"
                                      % (rel, mid.group(1) if mid else '?', attr, ref))

    # informational: legacy UI still holding records for isky-owned models.
    #
    # Phase 3c step 1 (decisions log 2026-11-08, S1-D2) splits this into the two numbers that
    # mean different things. MUST MOVE: a standalone record - a view with no inherit_id, a window
    # action, a report - which S4 says belongs to the module owning the model. MAY STAY: an
    # inherited view, which S4 explicitly allows to live anywhere, because adding your own fields
    # to someone else's form is what a bridge is for. A phase's acceptance is the first number
    # reaching zero for the layer being migrated; the second is printed so nothing is hidden.
    legacy_hits = defaultdict(int)
    may_stay = defaultdict(int)
    for mod in sorted(mods):
        if mod.startswith(PREFIX):
            continue
        for f in xml_files(mods[mod]):
            s = open(f, encoding='utf-8', errors='ignore').read()
            for m in re.finditer(r'<record\b(?:(?!</record>).)*?</record>', s, re.S):
                body = m.group(0)
                mm = re.search(r'<field name="(?:model|res_model)">([a-z0-9_.]+)</field>', body)
                if not mm:
                    continue
                own = owners.get(mm.group(1))
                if not own or not own.startswith(PREFIX):
                    continue
                if 'inherit_id' in body:
                    may_stay[(mod, own)] += 1
                else:
                    legacy_hits[(mod, own)] += 1

    print("S4 lint: views and menus")
    print("  modules checked: %d isky module(s)" % len(ours))
    print()
    for label, bucket in (("Check 1 (standalone view in owning module)", fail_view),
                          ("Check 2 (menuitem action resolves)", fail_action),
                          ("Check 3 (menuitem parent resolves)", fail_parent)):
        status = "PASS" if not bucket else "FAIL (%d)" % len(bucket)
        print("  %-48s -> %s" % (label, status))
        for line in bucket:
            print("        " + line)

    if legacy_hits or may_stay:
        print()
        print("  MIGRATION BACKLOG - standalone records a legacy module still holds for an")
        print("  isky-owned model. These MUST MOVE; zero for a layer closes its Phase 3c step:")
        total = 0
        for (legacy, own), n in sorted(legacy_hits.items(), key=lambda kv: -kv[1]):
            print("        %-42s -> %-46s %3d" % (legacy, own.replace(PREFIX, ''), n))
            total += n
        print("        %-42s    %-46s %3d TOTAL" % ('', '', total))
        per_layer = defaultdict(int)
        for (_legacy, own), n in legacy_hits.items():
            per_layer[own] += n
        print("        per layer: %s" % (', '.join(
            '%s=%d' % (k.replace(PREFIX, ''), v) for k, v in sorted(per_layer.items())) or 'none'))
        if may_stay:
            print()
            print("  MAY STAY - inherited views, which S4 allows in any module (a bridge adding")
            print("  its own fields to another layer's form). Not part of the backlog:")
            stay_total = 0
            for (legacy, own), n in sorted(may_stay.items(), key=lambda kv: -kv[1]):
                print("        %-42s -> %-46s %3d" % (legacy, own.replace(PREFIX, ''), n))
                stay_total += n
            print("        %-42s    %-46s %3d TOTAL" % ('', '', stay_total))

    failed = fail_view or fail_action or fail_parent
    print()
    print("FAIL" if failed else "PASS - every new view is in its owning module, and every menu "
                               "reference resolves.")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
