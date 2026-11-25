"""D188 step 0's legacy inventory, built with D187's test audit: each registered model family's
consumers, and what the modular path imports from older modules.

A family is one definition module (src/cells/definitions/*_spec.py, specs.py among them) with the
model IDs it declares and the model modules src/cells/registry/models.py dispatches its classes
to. For each family the inventory gives:
  - its place in the import graph from the active entry points (ENTRIES: the modular tissue
    model @3, the composite, the operators, the kinds, the runner and execution). The registry is
    cut as a transit node, since it imports every family; its importers are listed separately;
  - the protocols that name its model IDs (validation.protocol_models.scan: registered or not)
    and the validation modules that import it;
  - the G1 baseline worlds and crossrev sets that run it (model IDs in the saved G1 definitions);
  - the test files that import it (directly or through tests/ helper modules), with their tiers
    and costs (tests/test_tiers.json; tier 3 from tests/tier3_record.json, at its cap).
A family is active when the static model table (registry/model_table.py) has its row
(rule_family, shared with source_moves_plan.py classes; 17 November 2026, before it the rule was
an entry point or a G1 world, which missed GARD's family); "decide" when only registered
protocols name it; every other family is legacy (frozen). Entry points, G1 worlds and protocols
are reported per family. Every import from the active closure into a legacy family's modules is a
coupling, listed with the names used: move 1 needs each one resolved, so that nothing outside
legacy/ imports legacy code.

Static (ast): module-level and function-level imports, `from pkg import module`, names used as
`alias.name`, and string literals naming a module (importlib). Read-only except --out.

Usage:
  PYTHONPATH=src:. python scripts/legacy_inventory.py inventory --g1 G1_MERGED_DIR --out DIR \
      [--runtime RUNTIME_JSON ...]
  PYTHONPATH=src:. python scripts/legacy_inventory.py runtime --world WORLD_JSON --out JSON \
      [--steps 3]
The runtime action runs one saved G1 world's first window and records the cells modules loaded
beyond those the registry's own module-level imports load: the inventory checks they lie in the
static active closure (a cross-check of the static graph).
"""  # noqa: E501

import argparse
import ast
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
REGISTRY = "cells.registry.models"
# D188 R1: the older families' halves of the dispatch points live in the legacy registration;
# the core's dispatch points reach it on a miss, through core/legacy_entry's one constant.
REGISTRATION = "cells.legacy.registration"
TRANSIT = (REGISTRY, REGISTRATION)  # The transit nodes that import every family they dispatch.
# Dispatch chains: modules that import every family to dispatch on it (the model registry,
# the definition parser, the control schedules). They are reached but not expanded, and each
# one's per-family imports are listed apart: move 1 refactors them (D188).
DISPATCH = (REGISTRY, "cells.definitions.specs", "cells.execution.schedule", REGISTRATION)
CLASSES = ("active", "decide", "legacy")
ENTRIES = {
    "@3": ["cells.models.surface_pump_v3", "cells.definitions.surface_pump_v3_spec"],
    "composite": [
        "cells.models.pump_composite",
        "cells.models.pump_composite_adapter",
        "cells.definitions.pump_composite_spec",
    ],
    "operators": ["cells.operators"],
    "kinds": [
        "cells.registry.kind_registry",
        "cells.kinds",
        "cells.models.inner_laws",
        "cells.registry.species_registry",
        "cells.registry.inventory_species",
    ],
    "runner and execution": [
        "cells.execution.runner",
        "cells.execution.windows",
        "cells.execution.vector_windows",
        "cells.execution.batch",
        "cells.execution.batch_windows",
        "cells.execution.projective",
        "cells.execution.devices",
        "cells.execution.phases",
        "cells.execution.continuity",
    ],
}
# A model's ID, bare or in the models' family (D345). The inventory keys both spellings by the ID's
# name@major, so a saved definition and a protocol that is never rewritten still match.
ID = re.compile(r"^(?:cells\.model\.)?([a-z][a-z0-9_]*@\d+)$")


def model_key(value):
    """A model ID's name@major; any other string as it is."""
    match = ID.match(value)
    return match[1] if match else value


# ------------------------------------------------------------------ the module graph


def module_index():
    """{module name: path} of src/cells and validation, and {path name: path} of tests/scripts."""
    out = {}
    for base, top in ((SRC, "cells"), (ROOT, "validation")):
        for path in sorted((base / top).rglob("*.py")):
            parts = list(path.relative_to(base).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            out[".".join(parts)] = path
    for top in ("tests", "scripts"):
        for path in sorted((ROOT / top).rglob("*.py")):
            out[str(path.relative_to(ROOT))] = path
    return out


def _package(name, path):
    return name if path.name == "__init__.py" else name.rpartition(".")[0]


def file_imports(name, path, index):
    """[(target module, names used, kind)] of one file: imports anywhere in it (kind "import"),
    the names used through each module alias, and string literals naming a module ("string")."""
    tree = ast.parse(path.read_text(), str(path))
    edges, aliases = defaultdict(set), {}
    kinds = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in index:
                    edges[a.name]
                    kinds[a.name] = "import"
                    aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                pkg = _package(name, path).split(".")
                pkg = pkg[: len(pkg) - node.level + 1]
                base = ".".join([*pkg, base] if base else pkg)
            for a in node.names:
                sub = f"{base}.{a.name}"
                if sub in index:
                    edges[sub]
                    kinds[sub] = "import"
                    aliases[a.asname or a.name] = sub
                elif base in index:
                    edges[base].add(a.name)
                    kinds[base] = "import"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in index and node.value.startswith(("cells.", "validation.")):
                edges[node.value]
                kinds.setdefault(node.value, "string")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            target = aliases.get(node.value.id)
            if target:
                edges[target].add(node.attr)
    for target in list(edges):  # Importing a.b.c runs a's and a.b's __init__ first.
        parts = target.split(".")
        for k in range(1, len(parts)):
            parent = ".".join(parts[:k])
            if parent in index and parent not in edges and parent.startswith("cells"):
                edges[parent]
                kinds[parent] = "package"
    return [(t, sorted(n), kinds[t]) for t, n in sorted(edges.items()) if t != name]


def helper_aliases(index):
    """{tests.x dotted name: tests/x.py}: tests/ helper modules as test files import them."""
    out = {}
    for n in index:
        if n.startswith("tests/") and not Path(n).name.startswith("test_"):
            out[".".join(Path(n).with_suffix("").parts)] = n
    return out


def graph(index):
    """{module: {target: (names, kind)}} over every indexed file (tests/ helpers by path)."""
    aliases = helper_aliases(index)
    known = {**index, **{a: index[p] for a, p in aliases.items()}}
    out = {}
    for name, path in index.items():
        found = {}
        for t, n, k in file_imports(name, path, known):
            found[aliases.get(t, t)] = (n, k)
        out[name] = found
    return out


def closure(starts, edges, stop, leaves=()):
    """Modules reachable from starts, not entering modules in stop and not expanding leaves
    (dispatch chains: reached, but their per-family imports are reported apart); with the
    cut edges."""
    seen, cut, todo = set(starts), [], deque(starts)
    parent = dict.fromkeys(starts)
    while todo:
        u = todo.popleft()
        if u in leaves:
            continue
        for v, (names, kind) in edges.get(u, {}).items():
            if not v.startswith("cells"):
                continue
            if v in stop:
                via, w = [], u
                while w is not None:  # The import path from a start to u (breadth first).
                    via.append(w)
                    w = parent[w]
                cut.append((u, v, names, kind, via[::-1]))
            elif v not in seen:
                seen.add(v)
                parent[v] = u
                todo.append(v)
    return seen, cut


# ------------------------------------------------------------------ the registry's families


def _const_ids(tree):
    """{constant name: model ID} of a module's module-level string constants."""
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            value = node.value.value
            if isinstance(value, str) and ID.match(value):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        out[t.id] = model_key(value)
    return out


def _isinstance_class(test):
    """The class name of an `isinstance(x, Class)` test, else None."""
    if isinstance(test, ast.Call) and getattr(test.func, "id", None) == "isinstance":
        if len(test.args) == 2:
            cls = test.args[1]
            return getattr(cls, "id", getattr(cls, "attr", None))
    return None


def _class_ids(tree, consts):
    """{class name: model ID} from a module's model_id(model) isinstance chain (if statements,
    and a final `return A if isinstance(model, X) else B`), with its default under None; {}
    without such a function."""

    def returned(value, out):
        while isinstance(value, ast.IfExp):
            cls = _isinstance_class(value.test)
            if cls and isinstance(value.body, ast.Name):
                out.setdefault(cls, consts.get(value.body.id))
            value = value.orelse
        if isinstance(value, ast.Name):
            out.setdefault(None, consts.get(value.id))

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "model_id":
            out = {}
            for stmt in node.body:
                cls = _isinstance_class(stmt.test) if isinstance(stmt, ast.If) else None
                if cls and isinstance(stmt.body[-1], ast.Return):
                    value = stmt.body[-1].value
                    if isinstance(value, ast.Name):
                        out.setdefault(cls, consts.get(value.id))
                elif isinstance(stmt, ast.Return):
                    returned(stmt.value, out)
            return out
    return {}


def _dispatch_chain(path, function, index):
    """[(spec module, class, model module)] of one dispatch function's isinstance chain, in its
    order. Names resolve through the module's top-level imports and the function's own; other
    functions are not read (the registration's control_values returns `module.call(...)`, which
    is not a model dispatch)."""
    tree = ast.parse(path.read_text())
    body = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function), None
    )
    if body is None:
        return []
    names = {}  # local name -> module (a model or spec module) or (spec module, class)

    def bind(node):
        for a in node.names:
            sub = f"{node.module}.{a.name}"
            if sub in index:
                names[a.asname or a.name] = sub
            elif node.module in index:
                names[a.asname or a.name] = (node.module, a.name)

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            bind(node)
    for node in ast.walk(body):
        if isinstance(node, ast.ImportFrom) and node.module:
            bind(node)
    out = []
    for node in ast.walk(body):
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.Call)):
            continue
        call = node.test
        if getattr(call.func, "id", None) != "isinstance" or len(call.args) != 2:
            continue
        cls = call.args[1]
        if isinstance(cls, ast.Name):
            spec = names.get(cls.id)
        elif isinstance(cls, ast.Attribute) and isinstance(cls.value, ast.Name):
            spec = (names.get(cls.value.id), cls.attr)
        else:
            continue
        model = None
        for stmt in node.body:
            if isinstance(stmt, ast.ImportFrom) and stmt.module:
                for a in stmt.names:
                    names[a.asname or a.name] = f"{stmt.module}.{a.name}"
            if isinstance(stmt, ast.Return):
                value = stmt.value
                if isinstance(value, ast.Call):
                    value = value.func.value if isinstance(value.func, ast.Attribute) else None
                if isinstance(value, ast.Name):
                    model = names.get(value.id)
        if isinstance(spec, tuple) and isinstance(model, str):
            out.append((spec[0], spec[1], model))
    return out


# The registration's dispatch functions (D188 R1): the legacy halves of get_model, parse_spec,
# SimulationSpec._fine_dict and control_values.
DISPATCH_FUNCTIONS = ("model_for", "parse", "to_dict", "control_values")


def registration_imports(index):
    """The cells modules that the legacy registration's dispatch functions import inside their
    bodies: the older families' parse, serialization, schedule and model modules, which the
    core's dispatch points imported before R1. Its module-level imports are not counted (they
    include shared core modules such as core.schedule)."""
    if REGISTRATION not in index:
        return set()
    tree = ast.parse(index[REGISTRATION].read_text())
    out = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in DISPATCH_FUNCTIONS:
            for n in ast.walk(node):
                if isinstance(n, ast.ImportFrom) and n.module and not n.level:
                    for a in n.names:
                        sub = f"{n.module}.{a.name}"
                        out.add(sub if sub in index else n.module)
                elif isinstance(n, ast.Import):
                    out |= {a.name for a in n.names}
    return {m for m in out if m in index and m.startswith("cells")}


def registry_dispatch(index):
    """[(spec module, class, model module)] in get_model's order: the registry's get_model
    (the active families), then, after D188 R1, the legacy registration's model_for, which
    get_model calls on a miss (the older families)."""
    out = _dispatch_chain(index[REGISTRY], "get_model", index)
    if REGISTRATION in index:
        out += _dispatch_chain(index[REGISTRATION], "model_for", index)
    return out


# The shared definitions module: one family per dispatched class.
SHARED = "cells.definitions.specs"


def _snake(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name).upper()


def _model_consts(consts):
    """The model-ID constants among a module's ID constants (the rest name laws, kinds and
    policies: LAW_ID, METABOLISM_ID, ...)."""
    return {k: v for k, v in consts.items() if k.endswith("MODEL_ID")}


def _class_id(cls, model, consts, chain):
    """A dispatched class's model ID: its module's model_id() chain; else the constant named
    after the class (KineticFiniteExtracellularSpec: KINETIC_FINITE_EXTRACELLULAR_ID); else the
    model-ID constant whose ID is named after the model module; else the module's only one."""
    if chain:
        return chain.get(cls, chain.get(None))
    stem = _snake(cls.removesuffix("Spec"))
    for name in (f"{stem}_ID", f"{stem}_MODEL_ID"):
        if name in consts:
            return consts[name]
    models = _model_consts(consts)
    base = model.rpartition(".")[2]
    named = sorted({v for v in models.values() if v.split("@")[0] == base})
    if len(named) == 1:
        return named[0]
    values = sorted(set(models.values()))
    return values[0] if len(values) == 1 else None


def families(index):
    """{family: {"definition", "classes", "models", "dispatch", "ids", "class_ids"}}: one per
    definition module the registry dispatches from (one per class for definitions/specs.py)."""
    out = {}
    for spec, cls, model in registry_dispatch(index):
        key = f"{spec}:{cls}" if spec == SHARED else spec
        fam = out.setdefault(key, {"definition": spec, "classes": [], "models": [], "dispatch": []})
        fam["classes"].append(cls)
        fam["dispatch"].append([cls, model])
        if model not in fam["models"]:
            fam["models"].append(model)
    for fam in out.values():
        tree = ast.parse(index[fam["definition"]].read_text())
        consts = _const_ids(tree)
        chain = _class_ids(tree, consts)
        fam["class_ids"] = {c: _class_id(c, m, consts, chain) for c, m in fam["dispatch"]}
        ids = set(fam["class_ids"].values()) - {None}
        if fam["definition"] != SHARED:
            ids |= set(_model_consts(consts).values())  # Every version the module declares.
        fam["ids"] = sorted(ids)
    return out


# ------------------------------------------------------------------ the ruling

# The static model table: every active model, its definitions' module and its homes. A family is
# active by its row, so a new family is active once it joins the table, as it must to run, and no
# list of names needs to learn it (GARD's @1, OL1's @2; D196's legacy-removal list follows). One
# rule for this inventory and the move planner (source_moves_plan.py classes).
MODEL_TABLE = "cells.registry.model_table"


def table_rows_of(text):
    """{model ID: {"module", "homes"}} of a model table's source, read statically: each row's
    definitions' module, and the modules it names besides (law and operator homes, and its
    runner's module)."""
    rows = {}
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, ast.Assign) or not any(
            isinstance(t, ast.Name) and t.id == "MODELS" for t in node.targets
        ):
            continue
        table = node.value.args[0] if isinstance(node.value, ast.Call) else node.value
        for key, row in zip(table.keys, table.values, strict=True):
            fields = {k.arg: ast.literal_eval(k.value) for k in row.keywords}
            runner = fields.get("runner")
            rows[model_key(ast.literal_eval(key))] = dict(
                module=fields["module"],
                homes=[
                    *fields.get("law_homes", ()),
                    *fields.get("operator_homes", ()),
                    *([runner.partition(":")[0]] if runner else []),
                ],
            )
    return rows


def table_rows(index):
    """The tree's model table (MODEL_TABLE), or none when the tree has no table."""
    return table_rows_of(index[MODEL_TABLE].read_text()) if MODEL_TABLE in index else {}


def family_rows(fam, rows):
    """A family's rows in the model table: those keyed by one of its IDs, or naming its
    definitions' module where that module defines no other family (definitions/specs.py defines many,
    each matched by its ID; a namespaced ID such as cells.assembly_lineages@1 is matched by its
    module, since the inventory's ID pattern is the bare one)."""  # noqa: E501
    ids = set(fam["ids"]) | {i for i in fam["class_ids"].values() if i}
    shared = fam["definition"] == SHARED
    return sorted(
        k for k, r in rows.items() if k in ids or (not shared and r["module"] == fam["definition"])
    )


def rule_family(fam, rows, protocol_rows):
    """D189's ruling as a general rule: active by a model-table row; "decide" when registered
    protocols name it (counted active); legacy otherwise."""
    if family_rows(fam, rows):
        return "active"
    if any(set(r["ids"]) & set(fam["ids"]) and r["registered"] for r in protocol_rows):
        return "decide"
    return "legacy"


# ------------------------------------------------------------------ consumers


def g1_worlds(merged):
    """{model ID: [SET/WORLD]} of every saved G1 definition (any string equal to a model ID)."""
    out = defaultdict(set)
    for path in sorted(Path(merged).glob("*/*.json")):
        doc = json.loads(path.read_text())
        name = f"{path.parent.name}/{path.stem}"

        def walk(value, name=name):
            if isinstance(value, dict):
                for v in value.values():
                    walk(v)
            elif isinstance(value, list):
                for v in value:
                    walk(v)
            elif isinstance(value, str) and ID.match(value):
                out[model_key(value)].add(name)

        walk(doc.get("definition"))
    return {k: sorted(v) for k, v in out.items()}


def protocols():
    """validation.protocol_models.scan()'s rows, each with every model-ID-like string its file
    names (scan() keeps only IDs declared as *MODEL_ID constants; older families declare theirs
    under other names, e.g. definitions/specs.py's BIOELECTRIC_ID)."""
    from validation import protocol_models

    rows = protocol_models.scan()["rows"]
    for row in rows:
        row["ids"] = sorted(set(protocol_models.ID.findall((ROOT / row["file"]).read_text())))
    return rows


def test_costs():
    tiers = json.loads((ROOT / "tests" / "test_tiers.json").read_text())
    record = json.loads((ROOT / "tests" / "tier3_record.json").read_text())
    out = {}
    for tier, rows in tiers["tiers"].items():
        for row in rows:
            out[row["file"]] = {"tier": int(tier), "seconds": row["seconds"]}
            if tier != "3":
                out[row["file"]]["exit_code"] = row["exit_code"]
    for f, row in record["files"].items():
        out.setdefault(f, {"tier": 3})
        out[f] |= {"seconds": row["seconds"], "status": row["status"]}
    return out


def test_reach(index, edges):
    """{test file: cells modules it imports, directly or through tests/ helper modules}."""
    out = {}
    for n in index:
        if not (n.startswith("tests/") and Path(n).name.startswith("test_")):
            continue
        seen, todo, reach = {n}, [n], set()
        while todo:
            u = todo.pop()
            for v in edges.get(u, {}):
                if v.startswith("cells"):
                    reach.add(v)
                elif v.startswith("tests/") and v not in seen:
                    seen.add(v)
                    todo.append(v)
        out[n] = reach
    return out


# ------------------------------------------------------------------ the inventory


def inventory(args):
    index = module_index()
    edges = graph(index)
    fams = families(index)
    worlds = g1_worlds(args.g1)
    rows = protocols()
    table = table_rows(index)
    costs = test_costs()
    reach = test_reach(index, edges)
    entry_modules = {
        m
        for group in ENTRIES.values()
        for e in group
        for m in index
        if m == e or m.startswith(e + ".")
    }
    for fam in fams.values():
        mods = {fam["definition"], *fam["models"]}
        fam["entry"] = sorted(g for g, es in ENTRIES.items() if mods & set(_expand(es, index)))
        fam["g1"] = sorted({w for i in fam["ids"] for w in worlds.get(i, [])})
        fam["crossrev"] = sorted({w.split("/")[0] for w in fam["g1"] if w.startswith("crossrev-")})
        fam["protocols"] = [
            {"file": r["file"], "registered": r["registered"], "status": r["status"][:120]}
            for r in rows
            if set(r["ids"]) & set(fam["ids"])
        ]
        fam["rows"] = family_rows(fam, table)
        # rule_family: active by its model-table row; "decide" when only registered protocols
        # name it, listed for the user to rule on (kept legacy in the closures below, so its
        # imports from the path show as couplings); legacy otherwise. Entry points and G1 are
        # reported, not ruled on.
        fam["class"] = rule_family(fam, table, rows)
        fam["active"] = fam["class"] == "active"
    # The shared definitions module stays outside legacy/ whatever its classes' families are.
    legacy = {
        m
        for f in fams.values()
        if not f["active"]
        for m in (f["definition"], *f["models"])
        if m != SHARED
    }
    active_family_modules = {
        m for f in fams.values() if f["active"] for m in (f["definition"], *f["models"])
    }
    legacy -= active_family_modules  # A module shared by an active family stays active.
    starts = sorted((entry_modules | active_family_modules) - legacy)
    active, cut = closure(starts, edges, stop=legacy | set(TRANSIT), leaves=DISPATCH)
    legacy_reach, _ = closure(sorted(legacy), edges, stop=active | set(TRANSIT), leaves=DISPATCH)
    couplings = [
        {"from": u, "to": v, "names": n, "kind": k, "via": via}
        for u, v, n, k, via in cut
        if v not in TRANSIT and u not in DISPATCH
    ]
    chains = {}
    for chain in DISPATCH:
        targets = [v for v in edges.get(chain, {}) if v.startswith("cells")]
        chains[chain] = {
            "in_active_closure": chain in active,
            "legacy_targets": sorted(v for v in targets if v in legacy),
            "other_targets_only_through_chains": sorted(
                v for v in targets if v not in legacy and v not in active and v not in DISPATCH
            ),
        }
    registry_importers = sorted(n for n, e in edges.items() if REGISTRY in e and n != REGISTRY)
    validation_importers = defaultdict(list)
    for n, e in edges.items():
        if n.startswith("validation"):
            for v in e:
                if v in legacy:
                    validation_importers[v].append(n)
    for fam in fams.values():
        mods = {fam["definition"], *fam["models"]} - {SHARED}
        fam["validation_importers"] = sorted({n for m in mods for n in validation_importers[m]})
        tests = sorted(t for t, r in reach.items() if r & mods)
        fam["tests"] = [{"file": t, **costs.get(t, {"tier": None})} for t in tests]
        fam["test_seconds"] = round(sum(t.get("seconds") or 0 for t in fam["tests"]), 1)
        fam["couplings_in"] = [c for c in couplings if c["to"] in mods]
    cells_modules = {m for m in index if m.startswith("cells")}
    private = sorted((legacy_reach - active) - legacy)
    rest = cells_modules - active - legacy_reach - set(DISPATCH)
    legacy_side = sorted(m for m in rest if set(edges.get(m, {})) & (legacy | set(private)))
    independent = sorted(rest - set(legacy_side))
    # The whole static reach of the active starts, dispatch chains and the registry expanded:
    # whatever a run loads must lie in it, or the static graph misses a dynamic import.
    full, _ = closure(sorted(set(starts) | set(TRANSIT) & set(index)), edges, stop=set())
    legacy_all = legacy | set(private) | set(legacy_side)
    runtime = []
    for path in args.runtime or []:
        doc = json.loads(Path(path).read_text())
        loaded = set(doc["loaded_beyond_registry"]) | set(doc["registry_module_level"])
        runtime.append(
            {
                "world": doc["world"],
                "model": doc["model"],
                "loaded": len(loaded),
                "unexplained_by_the_static_graph": sorted(loaded - full),
                "legacy_loaded": len(loaded & legacy_all),
                "legacy_loaded_beyond_registry": sorted(
                    set(doc["loaded_beyond_registry"]) & legacy_all
                ),
            }
        )
    result = {
        "kind": "cells.legacy_inventory@1",
        "entries": ENTRIES,
        "g1": str(args.g1),
        "families": fams,
        "dispatch_chains": chains,
        "active_closure": sorted(active),
        "legacy_family_modules": sorted(legacy),
        "legacy_private_modules": private,
        "legacy_side_modules": legacy_side,
        "independent_modules": independent,
        "couplings": couplings,
        "registry_importers": registry_importers,
        "runtime": runtime,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "legacy_inventory.json").write_text(json.dumps(result, indent=1) + "\n")
    (out / "legacy_inventory.md").write_text(markdown(result))
    print(
        json.dumps(
            {
                "families": len(fams),
                **{k: sum(f["class"] == k for f in fams.values()) for k in CLASSES},
                "couplings": len(couplings),
                "runtime_unexplained": [r["unexplained_by_the_static_graph"] for r in runtime],
            }
        )
    )


def _expand(entries, index):
    return {m for e in entries for m in index if m == e or m.startswith(e + ".")}


def _short(module):
    return module.removeprefix("cells.")


def markdown(result):
    fams = result["families"]
    lines = ["# Legacy inventory (D188 step 0, with D187's audit)", ""]
    counts = ", ".join(f"{sum(f['class'] == k for f in fams.values())} {k}" for k in CLASSES)
    lines.append(
        f"{len(fams)} families: {counts}. {len(result['couplings'])} import couplings from the "
        "active closure into legacy modules. Classes: active (an entry point, or run by a G1 "
        "world); decide (off the modular path, but a registered protocol names it: the user "
        "rules); legacy (frozen)."
    )
    lines += ["", "## Families", ""]
    lines.append(
        "| Family (definition module) | Model IDs | Model modules | Class | Entry | G1 worlds "
        "(crossrev sets) | Protocols (registered) | Tests (tier 1/2/3) | Test s | Couplings in |"
    )
    lines.append("| --- " * 10 + "|")
    order = {k: n for n, k in enumerate(CLASSES)}
    for spec, f in sorted(fams.items(), key=lambda kv: (order[kv[1]["class"]], kv[0])):
        tiers = defaultdict(int)
        for t in f["tests"]:
            tiers[t.get("tier")] += 1
        reg = sum(p["registered"] for p in f["protocols"])
        lines.append(
            f"| {_short(spec)} | {', '.join(f['ids'])} | "
            f"{', '.join(_short(m).removeprefix('models.') for m in f['models'])} | "
            f"{f['class']} | {', '.join(f['entry']) or '-'} | "
            f"{len(f['g1'])} ({', '.join(f['crossrev']) or '-'}) | "
            f"{len(f['protocols'])} ({reg}) | "
            f"{tiers[1]}/{tiers[2]}/{tiers[3]} | {f['test_seconds']} | {len(f['couplings_in'])} |"
        )
    lines += [
        "",
        "## For the user to rule on: off the modular path, named by registered protocols",
        "",
    ]
    for spec, f in sorted(fams.items()):
        if f["class"] == "decide":
            regs = [p for p in f["protocols"] if p["registered"]]
            lines.append(f"- {_short(spec)} ({', '.join(f['ids'])}):")
            lines += [f"  - `{p['file']}`: {p['status'][:100]}" for p in regs]
    lines += ["", "## Couplings: the active closure imports from legacy modules", ""]
    for c in result["couplings"]:
        names = ", ".join(c["names"]) or "(the module)"
        via = " -> ".join(_short(m) for m in c["via"][:-1])
        lines.append(
            f"- `{_short(c['from'])}` -> `{_short(c['to'])}` ({c['kind']}): {names}"
            + (f" (reached via {via})" if via else "")
        )
    lines += ["", "## Dispatch chains (reached, not expanded; refactored by move 1)", ""]
    for chain, c in result["dispatch_chains"].items():
        others = ", ".join(f"`{_short(m)}`" for m in c["other_targets_only_through_chains"])
        lines.append(
            f"- `{_short(chain)}`: in the active closure: {c['in_active_closure']}; imports "
            f"{len(c['legacy_targets'])} legacy family modules; other modules reached only "
            f"through the chains: {others or 'none'}"
        )
    cells_importers = [m for m in result["registry_importers"] if m.startswith("cells")]
    lines += ["", "## Importers of the registry (a dispatch chain, cut)", ""]
    lines.append(
        f"{len(result['registry_importers'])} files import it: {len(cells_importers)} in "
        "src/cells, the rest in tests/, validation/ and scripts/. The src/cells ones:"
    )
    lines += [f"- `{_short(m)}`" for m in cells_importers]
    lines += ["", "## Runtime cross-check", ""]
    for r in result["runtime"]:
        beyond = ", ".join(f"`{_short(m)}`" for m in r["legacy_loaded_beyond_registry"])
        lines.append(
            f"- {r['world']} ({r['model']}): {r['loaded']} cells modules loaded; unexplained by "
            f"the static graph: {r['unexplained_by_the_static_graph'] or 'none'}; legacy modules "
            f"loaded: {r['legacy_loaded']}, of which beyond the registry's module-level imports "
            f"(the dispatch chains at run time): {beyond or 'none'}"
        )
    lines += ["", "## Legacy-private modules (reached only from legacy families)", ""]
    lines += [f"- `{_short(m)}`" for m in result["legacy_private_modules"]]
    lines += ["", "## Legacy-side modules (outside both closures, importing legacy modules)", ""]
    lines += [f"- `{_short(m)}`" for m in result["legacy_side_modules"]]
    lines += ["", "## Independent modules (outside both closures, importing no legacy module)", ""]
    lines += [f"- `{_short(m)}`" for m in result["independent_modules"]]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ the runtime cross-check


def runtime(args):
    import importlib

    doc = json.loads(Path(args.world).read_text())
    importlib.import_module(REGISTRY)
    before = {m for m in sys.modules if m.startswith("cells")}
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, iter_windows

    spec = parse_spec(doc["definition"])
    next(iter(iter_windows(spec, WindowPolicy(args.steps, "checkpoints"))))
    after = {m for m in sys.modules if m.startswith("cells")}
    out = {
        "world": str(args.world),
        "model": doc["definition"]["model"]["id"],
        "steps": args.steps,
        "registry_module_level": sorted(before),
        "loaded_beyond_registry": sorted(after - before),
    }
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({"model": out["model"], "beyond_registry": len(after - before)}))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    i = sub.add_parser("inventory")
    i.add_argument("--g1", required=True, help="a G1 run's merged folder (SET/WORLD.json)")
    i.add_argument("--out", required=True)
    i.add_argument("--runtime", nargs="*", help="runtime action outputs to cross-check")
    r = sub.add_parser("runtime")
    r.add_argument("--world", required=True, help="a saved G1 world JSON")
    r.add_argument("--out", required=True)
    r.add_argument("--steps", type=int, default=3)
    args = parser.parse_args(argv)
    return {"inventory": inventory, "runtime": runtime}[args.command](args) or 0


if __name__ == "__main__":
    sys.exit(main())
