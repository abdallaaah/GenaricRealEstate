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


def model_owners(mods):
    """model name -> module declaring its _name"""
    owners = {}
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
                    for st in node.body:
                        if isinstance(st, ast.Assign):
                            for t in st.targets:
                                if isinstance(t, ast.Name) and t.id == '_name' \
                                        and isinstance(st.value, ast.Constant):
                                    owners.setdefault(st.value.value, name)
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
                if own != mod:
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

    # informational: legacy UI still owning isky models
    legacy_hits = defaultdict(int)
    for mod in sorted(mods):
        if mod.startswith(PREFIX):
            continue
        for f in xml_files(mods[mod]):
            s = open(f, encoding='utf-8', errors='ignore').read()
            for m in re.finditer(r'<field name="model">([a-z0-9_.]+)</field>', s):
                own = owners.get(m.group(1))
                if own and own.startswith(PREFIX):
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

    if legacy_hits:
        print()
        print("  INFORMATIONAL - legacy UI still holding views for isky-owned models")
        print("  (the migration backlog; not a failure until that phase runs):")
        total = 0
        for (legacy, own), n in sorted(legacy_hits.items(), key=lambda kv: -kv[1]):
            print("        %-42s -> %-46s %3d" % (legacy, own.replace(PREFIX, ''), n))
            total += n
        print("        %-42s    %-46s %3d TOTAL" % ('', '', total))

    failed = fail_view or fail_action or fail_parent
    print()
    print("FAIL" if failed else "PASS - every new view is in its owning module, and every menu "
                               "reference resolves.")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
