#!/usr/bin/env python3
"""Lint the super()-chained compute extension guard pattern (Phase 3).

The pattern, approved 2026-11-04:
  - The base compute lives in sales_crm and keeps its own @api.depends on always-present
    paths only.
  - Each BRIDGE module that extends a compute must redeclare the method WITH an @api.depends
    that includes its own paths, and must call super().

This check fails when a bridge module overrides a compute method without @api.depends,
because Odoo would then silently drop the bridge's own dependency paths: the field would
not recompute when the bridge's data changes.

Usage: python3 claude/scripts/lint_guard_pattern.py [repo_root]
Exit 0 = clean, 1 = violations found.
"""
import ast
import os
import re
import sys

# Modules that act as optional bridges layering onto a base module's computes.
BRIDGE_MODULES = {
    'isky_18_realestate_developer_accounting',
    'isky_18_realestate_developer_sales_accounting',
    'isky_18_realestate_developer_sales_cheques',
    'isky_18_realestate_developer_commission',
}


def has_decorator(node, name):
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        attr = getattr(target, 'attr', None) or getattr(target, 'id', None)
        if attr == name:
            return True
    return False


def calls_super(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            fn = sub.func
            # super().method(...)
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Call):
                inner = fn.value.func
                if getattr(inner, 'id', None) == 'super':
                    return True
            # super(Model, self).method(...)
            if getattr(fn, 'id', None) == 'super':
                return True
    return False


def takes_only_self(node):
    """An Odoo field compute always has the signature (self). A method carrying extra
    positional args is some other API (e.g. account_reports' report handlers, which use
    _compute_<x>(self, report, options, ...)), not a field compute - so a missing
    @api.depends there is correct, not a violation."""
    a = node.args
    if a.vararg or a.kwarg or a.kwonlyargs:
        return False
    return [arg.arg for arg in a.args] == ['self']


def is_compute(node):
    """A compute method: decorated with @api.depends, or named _compute_* / compute_* AND
    carrying a field-compute signature."""
    if has_decorator(node, 'depends'):
        return True
    named_like_compute = node.name.startswith('_compute_') or node.name.startswith('compute_')
    return named_like_compute and takes_only_self(node)


def check_file(path, module):
    violations = []
    try:
        tree = ast.parse(open(path, encoding='utf-8').read())
    except SyntaxError as exc:
        return [(path, 0, f'SYNTAX ERROR: {exc}')]

    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        # only _inherit classes are "overriding" something
        inherits = any(
            isinstance(stmt, ast.Assign)
            and any(getattr(t, 'id', None) == '_inherit' for t in stmt.targets)
            for stmt in cls.body
        )
        if not inherits:
            continue

        for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
            if not is_compute(fn):
                continue
            if not has_decorator(fn, 'depends'):
                violations.append((
                    path, fn.lineno,
                    f"{cls.name}.{fn.name}() overrides a compute in bridge '{module}' "
                    f"without @api.depends - the bridge's own dependency paths would be "
                    f"silently dropped. Redeclare @api.depends including them."
                ))
    return violations


#
# Check 2: every group_* referenced from sales_crm must be defined in sales_crm itself or in a
# module sales_crm declares as a dependency. Added Phase 3 step 2a, after a group it referenced
# turned out to live in the monolith - has_group() then returns False for every user and the
# feature is silently dead rather than erroring.
#
GROUP_REF_MODULE = 'isky_18_realestate_developer_sales_crm'
# Check 2 matches the CALL, not the name shape. Earlier revisions guessed from the xmlid -
# first `group_*`, then also `*group` - and each time a reference slipped through: Phase 4
# found 40 refs ending in `_group`, and S7 found
# `arkzayed_18_realestate_development.stop_checking_reservation_expiration`, which matches
# neither. Any module-qualified xmlid passed to has_group() is now checked, whatever it is
# called, because has_group() on an unreachable xmlid silently returns False for every user.
HAS_GROUP_RE = re.compile(r"""has_group\(\s*['"]([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)['"]""")
# XML `groups="module.xmlid"` attributes, which fail the same way.
GROUP_REF_RE = re.compile(r"""['"]([a-zA-Z0-9_]+)\.((?:group_[a-zA-Z0-9_]+|[a-zA-Z0-9_]*group))['"]""")


def manifest_depends(root, module):
    path = os.path.join(root, module, '__manifest__.py')
    if not os.path.isfile(path):
        return []
    try:
        return list(ast.literal_eval(open(path, encoding='utf-8').read()).get('depends', []))
    except (SyntaxError, ValueError):
        return []


def transitive_depends(root, module, seen=None):
    """All modules reachable through this repo's manifests. Modules outside the repo (Odoo core
    and Enterprise) are returned as-is: their presence is guaranteed by the dependency itself."""
    if seen is None:
        seen = set()
    for dep in manifest_depends(root, module):
        if dep in seen:
            continue
        seen.add(dep)
        transitive_depends(root, dep, seen)
    return seen


def defines_group(root, module, group):
    """True if `module` defines an xmlid `group` in any of its data files."""
    mod_dir = os.path.join(root, module)
    if not os.path.isdir(mod_dir):
        # Not in this repo (Odoo core / Enterprise) - assume it defines its own groups.
        return True
    needle = f'id="{group}"'
    for dirpath, dirnames, filenames in os.walk(mod_dir):
        dirnames[:] = [d for d in dirnames if d != '__pycache__']
        for fname in filenames:
            if not fname.endswith(('.xml', '.csv')):
                continue
            try:
                if needle in open(os.path.join(dirpath, fname), encoding='utf-8').read():
                    return True
            except (OSError, UnicodeDecodeError):
                continue
    return False


def check_group_refs(root):
    """Scan sales_crm for qualified group references and verify each is reachable."""
    violations = []
    mod_dir = os.path.join(root, GROUP_REF_MODULE)
    if not os.path.isdir(mod_dir):
        return violations

    reachable = {GROUP_REF_MODULE} | transitive_depends(root, GROUP_REF_MODULE)

    for dirpath, dirnames, filenames in os.walk(mod_dir):
        dirnames[:] = [d for d in dirnames if d != '__pycache__']
        for fname in filenames:
            if not fname.endswith(('.py', '.xml', '.csv')):
                continue
            path = os.path.join(dirpath, fname)
            try:
                content = open(path, encoding='utf-8').read()
            except (OSError, UnicodeDecodeError):
                continue
            for lineno, line in enumerate(content.splitlines(), 1):
                # both patterns: any has_group() call, plus name-shaped xmlids in XML
                found = set(HAS_GROUP_RE.findall(line)) | set(GROUP_REF_RE.findall(line))
                for owner, group in sorted(found):
                    if owner not in reachable:
                        violations.append((
                            path, lineno,
                            f"references group '{owner}.{group}', but '{GROUP_REF_MODULE}' does "
                            f"not declare '{owner}' as a dependency (directly or transitively). "
                            f"has_group() would silently return False for every user."
                        ))
                    elif not defines_group(root, owner, group):
                        violations.append((
                            path, lineno,
                            f"references group '{owner}.{group}', but '{owner}' does not define "
                            f"an xmlid '{group}'."
                        ))
    return violations


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    all_violations = []
    checked = 0

    for module in sorted(BRIDGE_MODULES):
        mod_dir = os.path.join(root, module)
        if not os.path.isdir(mod_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(mod_dir):
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            for fname in filenames:
                if fname.endswith('.py'):
                    checked += 1
                    all_violations += check_file(os.path.join(dirpath, fname), module)

    group_violations = check_group_refs(root)

    print(f"Check 1 (compute @api.depends): {checked} file(s) across "
          f"{len([m for m in BRIDGE_MODULES if os.path.isdir(os.path.join(root, m))])} "
          f"bridge module(s) present -> "
          f"{'FAIL' if all_violations else 'PASS'}")
    print(f"Check 2 (sales_crm group refs reachable): -> "
          f"{'FAIL' if group_violations else 'PASS'}\n")

    all_violations = all_violations + group_violations

    if not all_violations:
        print("PASS - every compute overridden in a bridge redeclares @api.depends, and every "
              "group referenced from sales_crm is reachable.")
        return 0

    print(f"FAIL - {len(all_violations)} violation(s):\n")
    for path, line, msg in all_violations:
        print(f"  {os.path.relpath(path, root)}:{line}")
        print(f"    {msg}\n")
    return 1


if __name__ == '__main__':
    sys.exit(main())
