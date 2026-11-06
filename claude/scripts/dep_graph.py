#!/usr/bin/env python3
"""Read every __manifest__.py under the repo root and report dependency cycles.

Usage: python3 claude/scripts/dep_graph.py [repo_root]
"""
import ast
import os
import sys


def load_manifest(path):
    with open(path, encoding="utf-8") as f:
        source = f.read()
    return ast.literal_eval(source)


def build_graph(repo_root):
    graph = {}
    for entry in sorted(os.listdir(repo_root)):
        manifest_path = os.path.join(repo_root, entry, "__manifest__.py")
        if not os.path.isfile(manifest_path):
            continue
        try:
            manifest = load_manifest(manifest_path)
        except (SyntaxError, ValueError) as exc:
            print(f"WARNING: could not parse {manifest_path}: {exc}", file=sys.stderr)
            continue
        graph[entry] = list(manifest.get("depends", []))
    return graph


def find_cycles(graph):
    """DFS-based cycle detection. Returns a list of cycles (each a list of module names)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}
    cycles = []
    path = []

    def visit(node):
        color[node] = GRAY
        path.append(node)
        for dep in graph.get(node, []):
            if dep not in graph:
                continue  # external/core Odoo module, not part of this repo
            if color[dep] == GRAY:
                cycle_start = path.index(dep)
                cycles.append(path[cycle_start:] + [dep])
            elif color[dep] == WHITE:
                visit(dep)
        path.pop()
        color[node] = BLACK

    for node in graph:
        if color[node] == WHITE:
            visit(node)
    return cycles


def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    graph = build_graph(repo_root)
    print(f"Scanned {len(graph)} local modules under {repo_root}\n")

    cycles = find_cycles(graph)
    if not cycles:
        print("No dependency cycles found.")
        return 0

    print(f"Found {len(cycles)} cycle(s):\n")
    seen = set()
    for cycle in cycles:
        key = tuple(sorted(cycle))
        if key in seen:
            continue
        seen.add(key)
        print("  " + " -> ".join(cycle))
    return 1


if __name__ == "__main__":
    sys.exit(main())
