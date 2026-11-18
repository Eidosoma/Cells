"""A7's static guard (the summation SPEC.md §4; docs/INNER_MODEL_V4_DESIGN.md §10.6): every sum in
@3's module, the operators and the inner model's kinds goes through cells/numerics/species_sums.

An AST scan of models/surface_pump_v3.py, operators/*.py and kinds/*.py (under src/cells):
- refused: any `.sum(...)` call (xp.sum, np.sum, jnp.sum or an array's method), any einsum, and
  builtin sum over anything but a generator expression or a list display;
- allowed: species_sum, entity_sum, and builtin sum over a generator or a list (tableau stage
  combinations, parse-time arithmetic);
- every entity_sum call is listed with its module, its enclosing function and its expression text
  (ast.unparse, not its line) in the frozen allow-list tests/species_sum_entity_sums.json, so a new
  one is reviewed once, and a listed one that is gone is refused too (the list stays exact).

The host-equals-device guard of the helper itself is tests/unit/test_species_sums.py.
"""

import ast
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CELLS = ROOT / "src" / "cells"
ALLOW = ROOT / "tests" / "species_sum_entity_sums.json"


def scope():
    return [
        CELLS / "models" / "surface_pump_v3.py",
        *sorted((CELLS / "operators").glob("*.py")),
        *sorted((CELLS / "kinds").glob("*.py")),
    ]


def calls(path, base=CELLS):
    """(refusals, entity sums, species sums) of one module: each entity sum as (module, function,
    expression); refusals as text with their lines, in line order."""
    tree = ast.parse(path.read_text())
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def enclosing(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        return "<module>"

    module = str(path.relative_to(base))
    refused, entity, species = [], [], 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        text = ast.unparse(node)
        if (isinstance(f, ast.Attribute) and name == "sum") or name == "einsum":
            refused.append((node.lineno, f"{module}:{node.lineno}: {text}"))
        elif isinstance(f, ast.Name) and name == "sum":
            if not (
                len(node.args) == 1
                and isinstance(node.args[0], (ast.GeneratorExp, ast.ListComp, ast.List))
            ):
                refused.append((node.lineno, f"{module}:{node.lineno}: {text}"))
        elif isinstance(f, ast.Name) and name == "entity_sum":
            entity.append((module, enclosing(node), text))
        elif isinstance(f, ast.Name) and name == "species_sum":
            species += 1
    return [text for _, text in sorted(refused)], entity, species


def scan():
    refused, entity, species = [], [], 0
    for path in scope():
        r, e, s = calls(path)
        refused += r
        entity += e
        species += s
    return refused, entity, species


def test_no_sum_bypasses_the_species_sum_helpers():
    refused, _, species = scan()
    assert not refused, "sums outside species_sum/entity_sum:\n" + "\n".join(refused)
    assert species > 0  # The scan reaches the sweep's sites.


def test_every_entity_sum_is_in_the_frozen_allow_list():
    """A new entity_sum is reviewed once (is its axis really not the species axis?) and added; a
    removed one leaves the list too."""
    _, entity, _ = scan()
    listed = Counter(tuple(row) for row in json.loads(ALLOW.read_text())["entity_sums"])
    found = Counter(entity)
    new = sorted((found - listed).elements())
    gone = sorted((listed - found).elements())
    assert not new, "entity_sum calls not in the allow-list:\n" + "\n".join(map(str, new))
    assert not gone, "allow-list entries with no call:\n" + "\n".join(map(str, gone))


def test_the_scan_refuses_a_planted_bypass(tmp_path):
    """Non-vacuous: a planted xp.sum, an array's .sum, an einsum and a builtin sum over a name are
    each refused; species_sum, entity_sum and sum over a generator pass."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(xp, a, rows):\n"
        "    b = xp.sum(a, axis=0)\n"
        "    c = a.sum()\n"
        "    d = xp.einsum('ij->j', a)\n"
        "    e = sum(rows)\n"
        "    g = sum(r for r in rows)\n"
        "    h = species_sum(a, xp=xp)\n"
        "    k = entity_sum(a, axis=None, xp=xp)\n"
        "    return b, c, d, e, g, h, k\n"
    )
    refused, entity, species = calls(planted, base=tmp_path)
    assert [r.split(": ", 1)[1] for r in refused] == [
        "xp.sum(a, axis=0)",
        "a.sum()",
        "xp.einsum('ij->j', a)",
        "sum(rows)",
    ]
    assert entity == [("planted.py", "f", "entity_sum(a, axis=None, xp=xp)")] and species == 1
