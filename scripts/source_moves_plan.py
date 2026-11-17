"""D188's move plans: the classes, the name-level reach, draft move maps and code pins.

The evidence that scripts/source_moves.py's maps are built from
(docs/SOURCE_LAYOUT_MOVES_DESIGN.md):
  classes  the registry's families, each active when the model table has its row
           (registry/model_table.py: every active model, D189's ruling kept as a table), or
           "decide" (D189's undecided, counted active) when registered protocols name it, and
           legacy otherwise; the active families' modules and their rows' homes are the starts.
           From scripts/legacy_inventory.py's import graph cut at the dispatch points: the
           older families' modules, the modules reached only from them, the modules outside
           both that import them, and the module-level couplings into them
  reach    name-level reachability from the active entry points: the top-level definitions of
           each module that are reached, following imported names
  move1    move 1's draft map: what moves to src/cells/legacy/ (mirroring the sub-packages), by
           move_set's rules: the modules kept because the core imports them, pulled in by their
           importers, moved with their only importers, and the package __init__s moved with
           their last module; the modules that stay but still import a moved one (the refactors
           to make first) and the dispatch points' imports of moved modules
  move2    move 2's draft map, by a rule table, with the modules it does not place
  pins     the code pins in src/cells (a hex literal equal to a tracked file's SHA-256), their
           kind, the modules computing paths from their own __file__, and which of them the
           given scan reports (source_moves.py scan --out) touch
Static analysis (ast): imports made from computed names are not seen; source_moves.py scan lists
them as hazards. Each action reads the earlier ones' outputs from DIR. Usage, from a checkout,
PYTHONPATH=src:. :
  python scripts/source_moves_plan.py classes --out DIR [--g1 G1_MERGED_DIR]
  python scripts/source_moves_plan.py reach|move1|move2 --out DIR
  python scripts/source_moves_plan.py pins --out DIR [--report SCAN_JSON ...]
  python scripts/source_moves_plan.py selftest   (move_set's rules on planted cases)
"""

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_inventory as li  # noqa: E402

ACTIVE_RULED = ("active", "decide")  # D189: the undecided families stay active.
# The static model table: every active model, its definitions' module and its homes. A family is
# active by its row, so a new family is active once it joins the table, as it must to run, and no
# list of names here needs to learn it (GARD's @1, OL1's @2; D196's legacy list follows).
MODEL_TABLE = "cells.registry.model_table"
# The modules that import every family to dispatch on it: move 1 refactors them (R1), so they
# neither move nor pull their importers along.
CHAINS = {
    "cells.models.registry",
    "cells.core.specs",
    "cells.core.schedule",
    "cells.__main__",
    "cells.ensemble.families",
    "cells.ensemble.cli",
}
MAP_KIND = "cells.source_moves.map@1"


def _load(out, name):
    return json.loads((Path(out) / name).read_text())


def _dump(out, name, value):
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / name).write_text(json.dumps(value, indent=1) + "\n")


# ------------------------------------------------------------------ classes


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
            rows[ast.literal_eval(key)] = dict(
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
    definitions' module where that module defines no other family (core/specs.py defines many,
    each matched by its ID; a namespaced ID such as cells.assembly_lineages@1 is matched by its
    module, since the inventory's ID pattern is the bare one)."""
    ids = set(fam["ids"]) | {i for i in fam["class_ids"].values() if i}
    shared = fam["definition"] == li.SHARED
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


def classes(args):
    """legacy_inventory's families and closures, each family ruled by rule_family."""
    index = li.module_index()
    edges = li.graph(index)
    fams = li.families(index)
    worlds = li.g1_worlds(args.g1) if args.g1 else {}
    protocol_rows = li.protocols()
    rows = table_rows(index)
    ruled = {key: rule_family(fam, rows, protocol_rows) for key, fam in fams.items()}
    active_f = {k for k, c in ruled.items() if c in ACTIVE_RULED}
    legacy = {
        m
        for k, f in fams.items()
        if k not in active_f
        for m in (f["definition"], *f["models"])
        if m != li.SHARED
    }
    act_mods = {
        m for k, f in fams.items() if k in active_f for m in (f["definition"], *f["models"])
    }
    legacy -= act_mods
    entry = {
        m for g in li.ENTRIES.values() for e in g for m in index if m == e or m.startswith(e + ".")
    }
    homes = {  # The modules the active families' rows name: imported by name, not by import.
        m
        for k, f in fams.items()
        if k in active_f
        for row in family_rows(f, rows)
        for h in rows[row]["homes"]
        for m in index
        if m == h or m.startswith(h + ".")
    }
    starts = sorted((entry | act_mods | homes) - legacy)
    transit = set(li.TRANSIT)  # The registry and, after R1, the legacy registration.
    active, cut = li.closure(starts, edges, stop=legacy | transit, leaves=li.DISPATCH)
    couplings = [
        dict(src=u, dst=v, names=n, kind=k, via=via)
        for u, v, n, k, via in cut
        if v not in transit and u not in li.DISPATCH
    ]
    reach_legacy, _ = li.closure(sorted(legacy), edges, stop=active | transit, leaves=li.DISPATCH)
    cells = {m for m in index if m.startswith("cells")}
    private = sorted((reach_legacy - active) - legacy)
    rest = cells - active - reach_legacy - set(li.DISPATCH)
    side = sorted(m for m in rest if set(edges.get(m, {})) & (legacy | set(private)))
    out = dict(
        kind="cells.source_moves.classes@1",
        families={k: ruled[k] for k in sorted(ruled)},
        rows={k: family_rows(fams[k], rows) for k in sorted(fams)},
        g1_worlds={  # Evidence only: G1's coverage is not a ruling.
            k: len({w for i in fams[k]["ids"] for w in worlds.get(i, [])}) for k in sorted(fams)
        }
        if args.g1
        else None,
        counts=Counter("active" if c in ACTIVE_RULED else "legacy" for c in ruled.values()),
        legacy=sorted(legacy),
        active=sorted(active),
        couplings=couplings,
        private=private,
        side=side,
        independent=sorted(rest - set(side)),
        dispatched=sorted(li.registration_imports(index)),
    )
    _dump(args.out, "classes.json", out)
    print(
        json.dumps(
            dict(
                counts=out["counts"],
                legacy_modules=len(legacy),
                couplings=len(couplings),
                private=len(private),
                side=len(side),
            )
        )
    )


# ------------------------------------------------------------------ reach


class _Module:
    def __init__(self, name, path):
        self.name, self.tree = name, ast.parse(path.read_text())
        self.package = name if path.name == "__init__.py" else name.rpartition(".")[0]
        self.defs, self.stmts = defaultdict(list), []
        for node in self.tree.body:
            bound = self._bound(node)
            self.stmts.append((node, bound))
            for n in bound:
                self.defs[n].append(node)

    @staticmethod
    def _bound(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return [node.name]
        if isinstance(node, ast.Assign):
            return [n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)]
        if isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
            return [node.target.id]
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return [(a.asname or a.name).split(".")[0] for a in node.names]
        return []  # Other top-level statements always run.

    def resolve(self, node, modules):
        """{local name: (module, attribute or None)} of one import statement."""
        out = {}
        if isinstance(node, ast.Import):
            for a in node.names:
                out[a.asname or a.name.split(".")[0]] = (
                    a.name if a.asname else a.name.split(".")[0],
                    None,
                )
            return out
        base = node.module or ""
        if node.level:
            pkg = self.package.split(".")
            pkg = pkg[: len(pkg) - node.level + 1]
            base = ".".join([*pkg, base] if base else pkg)
        for a in node.names:
            sub = f"{base}.{a.name}"
            out[a.asname or a.name] = (sub, None) if sub in modules else (base, a.name)
        return out


def reach(args):
    """The top-level names of each module reached from the active entry points."""
    index = li.module_index()
    cells = {m: p for m, p in index.items() if m.startswith("cells")}
    mods = {m: _Module(m, p) for m, p in cells.items()}
    fams = li.families(index)
    ruled = _load(args.out, "classes.json")["families"]
    active_mods = {
        m
        for k, f in fams.items()
        if ruled.get(k) in ACTIVE_RULED
        for m in (f["definition"], *f["models"])
    }
    entry = {
        m for g in li.ENTRIES.values() for e in g for m in cells if m == e or m.startswith(e + ".")
    }
    ALL = "*"
    need, todo = defaultdict(set), []

    def require(mod, names):
        if mod not in mods or ALL in need[mod]:
            return
        new = {ALL} if names == ALL else set(names) - need[mod]
        if new:
            need[mod] |= new
            todo.append(mod)
        parts = mod.split(".")
        for k in range(1, len(parts)):  # Importing a.b.c runs a's and a.b's __init__.
            parent = ".".join(parts[:k])
            if parent in mods and not need[parent]:
                need[parent].add("<init>")
                todo.append(parent)

    for m in sorted(entry | active_mods):
        require(m, ALL)
    leaves = set(li.DISPATCH)
    while todo:
        mod = todo.pop()
        m = mods[mod]
        names = need[mod]
        if ALL in names or mod in leaves:
            nodes = [n for n, _ in m.stmts]
        else:
            seen, stack = set(), [n for n in names if n in m.defs]
            nodes = [n for n, b in m.stmts if not b]
            while stack:
                n = stack.pop()
                if n in seen:
                    continue
                seen.add(n)
                for st in m.defs[n]:
                    nodes.append(st)
                    stack += [
                        x.id for x in ast.walk(st) if isinstance(x, ast.Name) and x.id in m.defs
                    ]
            names.update(seen)
        if mod in leaves:
            continue  # Dispatch chains: reached, not expanded (move 1 refactors them).
        top = {}
        for st, _ in m.stmts:
            if isinstance(st, (ast.Import, ast.ImportFrom)):
                top.update(m.resolve(st, mods))
        for node in nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            local, attrs, used = dict(top), defaultdict(set), set()
            for x in ast.walk(node):
                if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name):
                    attrs[x.value.id].add(x.attr)
                elif isinstance(x, ast.Name):
                    used.add(x.id)
                elif isinstance(x, (ast.Import, ast.ImportFrom)):  # Run when the code runs.
                    bound = m.resolve(x, mods)
                    local.update(bound)
                    for target, attr in bound.values():
                        require(target, {"<init>"} if attr is None else {attr})
            for loc in used & set(local):
                target, attr = local[loc]
                if attr is not None:
                    require(target, {attr})
                elif target in mods:
                    require(target, attrs.get(loc) or {"<init>"})
                    for a in attrs.get(loc, ()):
                        if f"{target}.{a}" in mods:
                            require(f"{target}.{a}", ALL)
    out = {}
    for mod in sorted(cells):
        n = need.get(mod, set())
        status = "all" if ALL in n else "part" if n else "unreached"
        out[mod] = dict(
            status=status,
            reached=sorted(x for x in n if x in mods[mod].defs),
            defs=len(mods[mod].defs),
        )
    _dump(args.out, "reach.json", out)
    print(json.dumps(Counter(r["status"] for r in out.values())))


# ------------------------------------------------------------------ the draft maps


def _packages(pairs, existing=()):
    packages = {}
    for _, new in pairs:
        parts = new.split(".")
        for k in range(2, len(parts)):
            pkg = ".".join(parts[:k])
            if pkg not in packages and pkg not in {n for _, n in pairs} and pkg not in existing:
                packages[pkg] = ""
    return dict(sorted(packages.items()))


def _in_legacy(module):
    return module == "cells.legacy" or module.startswith("cells.legacy.")


def legacy_entries(edges):
    """The core's entry point into the older families (D188 R1, core/legacy_entry): the module
    outside the legacy package that names the legacy registration by its string constant, which
    importlib loads on a miss. It never moves to legacy/. Its string names a legacy module, so on
    a tree where move 1 is applied the classes count it among the modules importing legacy code
    ("side"), and without this rule the planner would move it (17 November, move 2's step 1)."""
    return {
        u
        for u, targets in edges.items()
        if u.startswith("cells")
        and not _in_legacy(u)
        and targets.get(li.REGISTRATION, (None, None))[1] == "string"
    }


def move_set(c, reached, index, edges):
    """Move 1's modules and how each rule placed them. The rules:
      - older families' modules the active path does not reach (by name), and the modules
        reached only from them or importing them (classes), move;
      - kept: a module that is not an older family's own (definition or model) module, nor one
        the legacy registration's dispatch functions import (an older family's parser or
        schedule), and that a module the active path reaches imports, anywhere in it, stays:
        what the core imports
        is the core's (surface_kinetic_spec's parse, which the older families still run from
        the core, needs its junction parser; cav_channels' CaV kinetics need calcium_gates).
        An older family's module imported so is a coupling, for a refactor before the move;
      - pulled: a module that imports a moved module moves, unless it is kept or reached;
      - moved with its importers: a module whose src importers are all moved (at least one)
        moves, unless it is kept or reached (assembly_cluster/controls);
      - a package's __init__ moves with its last module, unless it is kept or reached
        (assembly_cell, assembly_cluster).
    The dispatch points never move and their imports keep nothing; after D188 R1 what they
    still import that moves is a coupling like any other (move1 reports it). The legacy package
    itself (R1's registration) is already in place: it never moves, and as the transit node
    that imports every older family it keeps nothing either."""
    family = set(c["legacy"])
    stop = family | set(c.get("dispatched", ())) | set(li.TRANSIT)
    kept, _ = li.closure(sorted(reached - CHAINS), edges, stop=stop, leaves=CHAINS)
    kept = {m for m in kept if m.startswith("cells")} | (reached - CHAINS)
    placed = {m for m in index if _in_legacy(m)}
    fixed = kept | reached | CHAINS | placed | legacy_entries(edges)
    moved = (family | set(c["private"]) | set(c["side"])) - fixed
    importers = defaultdict(set)
    for u, targets in edges.items():
        if u.startswith("cells"):
            for v in targets:
                if v.startswith("cells") and v != u:
                    importers[v].add(u)
    cells = sorted(m for m in index if m.startswith("cells"))
    packages = {m for m in cells if index[m].name == "__init__.py"}
    notes = dict(pulled_in_by_importers=[], moved_with_their_only_importers=[], package_inits=[])
    changed = True
    while changed:
        changed = False
        for m in cells:
            if m in moved or m in fixed:
                continue
            why = None
            if {t for t in edges.get(m, {}) if t.startswith("cells")} & moved:
                why = "pulled_in_by_importers"
            elif importers[m] and importers[m] <= moved:
                why = "moved_with_their_only_importers"
            elif m in packages:
                inside = [x for x in cells if x.startswith(m + ".")]
                if inside and all(x in moved for x in inside):
                    why = "package_inits"
            if why:
                moved.add(m)
                notes[why].append(m)
                changed = True
    notes["kept_imported_by_the_core"] = sorted(
        m for m in kept - reached if m in family | set(c["private"]) | set(c["side"])
    )
    return moved, notes


def move1(args):
    """Move 1's draft: older families' modules the active path does not reach, then their
    importers, except the dispatch points (move_set has the rules)."""
    c = _load(args.out, "classes.json")
    r = _load(args.out, "reach.json")
    reached = {m for m, x in r.items() if x["status"] != "unreached"}
    index = li.module_index()
    edges = li.graph(index)
    legacy, notes = move_set(c, reached, index, edges)
    pulled = notes["pulled_in_by_importers"]
    couplings = couplings_of(legacy, edges, [x for x in index if x.startswith("cells")])
    chains = {ch: sorted(t for t in edges.get(ch, {}) if t in legacy) for ch in sorted(CHAINS)}
    pairs = [[m, "cells.legacy." + m.removeprefix("cells.")] for m in sorted(legacy)]
    packages = _packages(pairs)
    packages["cells.legacy"] = (
        '"""The older model families (D188, D189): frozen, run only through their registrations.'
        '\n\nNothing outside this package imports from it.\n"""\n'
    )
    doc = dict(
        kind=MAP_KIND,
        move="d188-move-1-draft",
        description="DRAFT (D188 step 0): regenerated on the head that holds the BLAS pin, the "
        "retire and refactors R1-R4 before it is applied.",
        modules=pairs,
        packages=dict(sorted(packages.items())),
        keep=[],
        reviewed=[],
        draft_notes=dict(
            **notes,
            reached_modules_importing_moved=couplings,
            dispatch_points=chains,
        ),
    )
    _dump(args.out, "move1-draft.json", doc)
    print(
        json.dumps(
            dict(
                modules=len(pairs),
                by_package=Counter(m.split(".")[1] for m, _ in pairs),
                pulled=len(pulled),
                couplings=len(couplings),
                chain_imports={k: len(v) for k, v in chains.items()},
            )
        )
    )


LAWS = {
    "channels": r"(potassium|sodium|leak|cav|hcn|hcn_extra|kv1|morris_lecar)_channels|voltage_gates"
    r"|calcium_activated_(potassium|catalog)|.*_catalog(_v2|_extra)?|exponential_gates",
    "junctions": r"junction_(gate|formation)",
    "pumps": r"kinetic_pump(_binding)?|calcium_atpase|proton_pump|atp_transporter",
    "routes": r"passive_permeation|k_anion_symport|cotransport|.*_transporter",
    "reactions": r"mass_action|reactions|hill_factors|rapid_proton_buffer|ph_condition|er_calcium"
    r"|plasma_calcium",
    "transport": r"proton_leak|patch_damage",
}
EXECUTION = {
    "runner",
    "windows",
    "vector_windows",
    "batch",
    "batch_windows",
    "projective",
    "devices",
    "phases",
    "grid",
    "state",
    "resources",
    "row_checks",
    "schedule",
    "errors",
    "output_paths",
    "blas_threads",
}
REGISTRY = {"kind_registry", "species_registry", "inventory_species"}
RECORDS = {"io", "window_io", "batch_io", "batch_window_io", "run_view", "observers"}
# Folders whose modules the rule table leaves where they are: D188's target folders (a module
# already in one is at home: R6's execution and registry package files, or a branch's new module
# there), cells.modules (D195's provisional surface, which no move touches) and the folders D188
# does not name.
STAY = (
    "numerics",
    "models",
    "analysis",
    "assays",
    "assembly",
    "assembly_pool",
    "ensemble",
    "laws",
    "kinds",
    "operators",
    "execution",
    "registry",
    "definitions",
    "records",
    "modules",
)


def _target2(m):
    parts, leaf = m.split("."), m.split(".")[-1]
    if m.startswith("cells.models.inner_kinds"):
        return "cells.kinds" + m.removeprefix("cells.models.inner_kinds")
    if m.startswith("cells.models.operators"):
        return "cells.operators" + m.removeprefix("cells.models.operators")
    if m == "cells.models.registry":
        return "cells.registry.models"  # Leaf renamed: cells.registry is the package.
    if len(parts) == 3 and parts[1] == "processes":
        for group, pattern in LAWS.items():
            if re.fullmatch(pattern, leaf):
                return f"cells.laws.{group}.{leaf}"
    if len(parts) == 3 and parts[1] == "coupling":
        return f"cells.laws.junctions.{leaf}"
    if len(parts) == 3 and parts[1] == "core":
        if leaf in EXECUTION:
            return f"cells.execution.{leaf}"
        if leaf in REGISTRY:
            return f"cells.registry.{leaf}"
        if leaf == "specs" or leaf.endswith("_spec"):
            return f"cells.definitions.{leaf}"
    if len(parts) == 2 and leaf == "continuity":
        return "cells.execution.continuity"
    if len(parts) == 2 and leaf in RECORDS:
        return f"cells.records.{leaf}"
    return None


def move2_plan(modules, moved1):
    """Move 2's pairs and unplaced modules: the modules outside legacy/ that move 1 (its draft, or
    nothing once it is applied) does not move, by the rule table. A module already under
    cells.legacy is move 1's, applied: it is neither moved nor listed as unplaced."""
    pairs, unplaced = [], []
    for m in sorted(modules):
        if not m.startswith("cells.") or m in moved1 or _in_legacy(m):
            continue
        new = _target2(m)
        if new and new != m:
            pairs.append([m, new])
        elif new is None and m.split(".")[1] not in STAY and m != "cells.__main__":
            unplaced.append(m)
    return pairs, unplaced


def move2(args):
    """Move 2's draft: the modules move 1 leaves outside legacy/, by the rule table."""
    m1 = _load(args.out, "move1-draft.json")
    moved1 = {o for o, _ in m1["modules"]}
    index = li.module_index()
    pairs, unplaced = move2_plan(index, moved1)
    doc = dict(
        kind=MAP_KIND,
        move="d188-move-2-draft",
        description="DRAFT (D188 step 0), after move 1's draft; rule table in "
        "scripts/source_moves_plan.py",
        modules=pairs,
        packages=_packages(pairs, existing=set(index)),  # R6's execution and registry exist
        keep=[],
        reviewed=[],
        draft_notes=dict(unplaced=unplaced),
    )
    _dump(args.out, "move2-draft.json", doc)
    by = Counter(
        n.split(".")[1] + ("/" + n.split(".")[2] if n.split(".")[1] == "laws" else "")
        for _, n in pairs
    )
    print(json.dumps(dict(moves=len(pairs), by_target=by, unplaced=len(unplaced))))


# ------------------------------------------------------------------ pins

HEX = re.compile(r"[0-9a-f]{64}")
FILE_ARITHMETIC = re.compile(
    r"Path\(__file__\)(?:\.resolve\(\))?(?:\.parents\[(\d+)\]|((?:\.parent)+))"
)


def pins(args):
    """Code pins in src/cells, and which ones the given scan reports touch."""
    files = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout.split()
    by_sha = defaultdict(list)
    for f in files:
        if Path(f).is_file():
            by_sha[hashlib.sha256(Path(f).read_bytes()).hexdigest()].append(f)
    touched = defaultdict(set)
    for r in args.report or []:
        rep = json.loads(Path(r).read_text())["report"]
        back = {new: old for old, new in rep["moved"]}
        for old, _ in rep["moved"]:
            touched[old].add("moved")
        for p in rep["files"]:
            touched[back.get(p, p)].add("rewritten")
    rows, arithmetic = [], []
    for f in files:
        if not (f.startswith("src/cells/") and f.endswith(".py")):
            continue
        text = Path(f).read_text()
        for m in FILE_ARITHMETIC.finditer(text):
            arithmetic.append(
                dict(
                    module=f,
                    line=text.count("\n", 0, m.start()) + 1,
                    text=m.group(0),
                    touched=sorted(touched.get(f, ())),
                )
            )
        tree = ast.parse(text)
        consts = {
            n.targets[0].id: n
            for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
        }
        for node in ast.walk(tree):
            found = []
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values, strict=True):
                    if (
                        isinstance(v, ast.Constant)
                        and isinstance(v.value, str)
                        and HEX.fullmatch(v.value)
                    ):
                        found.append(
                            (k.value if isinstance(k, ast.Constant) else None, v.value, v.lineno)
                        )
            elif (
                isinstance(node, ast.Tuple)
                and len(node.elts) == 2
                and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts)
                and HEX.fullmatch(node.elts[1].value)
            ):
                found.append((node.elts[0].value, node.elts[1].value, node.lineno))
            elif (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
                and HEX.fullmatch(node.value.value)
            ):
                found.append((getattr(node.targets[0], "id", None), node.value.value, node.lineno))
            for key, value, line in found:
                pinned = [p for p in by_sha.get(value, []) if p.startswith("src/")]
                const = next(
                    (n for n, a in consts.items() if a.lineno <= line <= a.end_lineno), None
                )
                rows.append(
                    dict(
                        module=f,
                        line=line,
                        constant=const,
                        key=key,
                        pinned=pinned,
                        live=bool(pinned),
                        kind="path"
                        if isinstance(key, str) and "/" in key and key.endswith(".py")
                        else "module",
                        module_touched=sorted(touched.get(f, ())),
                        pinned_touched=sorted({t for p in pinned for t in touched.get(p, ())}),
                    )
                )
    live = [r for r in rows if r["live"]]
    summary = dict(
        pinning_modules=sorted({r["module"] for r in live}),
        live_pins=len(live),
        pinned_files=sorted({p for r in live for p in r["pinned"]}),
        path_keyed=sum(r["kind"] == "path" for r in live),
        pins_whose_file_is_touched=[
            dict(module=r["module"], key=r["key"], pinned=r["pinned"], touched=r["pinned_touched"])
            for r in live
            if r["pinned_touched"]
        ],
        pinning_modules_touched=sorted(
            {(r["module"], ",".join(r["module_touched"])) for r in live if r["module_touched"]}
        ),
        file_arithmetic_modules=len({a["module"] for a in arithmetic}),
        file_arithmetic_touched=[a for a in arithmetic if a["touched"]],
    )
    _dump(args.out, "code-pins.json", dict(summary=summary, pins=rows, file_arithmetic=arithmetic))
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in summary.items()}))


# ------------------------------------------------------------------ planted cases


def _graph(spec):
    """A synthetic tree for move_set: {module: [imports]}, packages named with a trailing '/'.
    As in legacy_inventory's graph, importing a.b.c also imports the packages a and a.b."""
    index, edges = {}, {}
    for name, targets in spec.items():
        module = name.rstrip("/")
        tail = "/__init__.py" if name.endswith("/") else ".py"
        index[module] = Path("src/" + module.replace(".", "/") + tail)
        edges[module] = {t: ([], "import") for t in targets}
    for module, found in edges.items():
        for target in list(found):
            parts = target.split(".")
            for k in range(1, len(parts)):
                parent = ".".join(parts[:k])
                if parent in index and parent != module:
                    found.setdefault(parent, ([], "package"))
    return index, edges


def couplings_of(moved, edges, cells):
    """[[module, [moved modules it imports]]] of the modules that stay outside the legacy
    package, the dispatch points included (after D188 R1 they hold only the core's halves)."""
    return [
        [m, sorted(t for t in edges.get(m, {}) if t in moved)]
        for m in sorted(cells)
        if m not in moved
        and not (m == "cells.legacy" or m.startswith("cells.legacy."))
        and set(edges.get(m, {})) & moved
    ]


def selftest(args):
    """move_set's rules on a synthetic tree, each with a planted case it must catch."""
    index, edges = _graph(
        {
            "cells/": [],
            "cells.core/": [],
            "cells.core.specs": ["cells.core.old_spec"],  # A dispatch point: keeps nothing.
            "cells.core.old_spec": ["cells.models.old_model"],  # An older family's definition.
            "cells.models/": [],
            "cells.models.old_model": ["cells.processes.law", "cells.processes.only_old"],
            "cells.models.active": ["cells.core.shared_spec"],  # Reached: models/ stays.
            "cells.core.shared_spec": ["cells.processes.law", "cells.core.old_spec"],
            "cells.processes/": [],
            "cells.processes.law": [],  # Reached only from older families, imported by the core.
            "cells.processes.only_old": [],  # Reached only from older families.
            "cells.core.helper": ["cells.models.old_model"],  # Imports a moved module.
            # A package whose modules move: engine is pulled, controls has only engine as its
            # importer, and the package's __init__ follows them (a dispatch point imports it).
            "cells.assembly/": [],
            "cells.assembly.engine": [
                "cells.models.old_model",
                "cells.assembly.controls",
                "cells.assembly",
            ],
            "cells.assembly.controls": [],
            "cells.core.schedule": ["cells.assembly.engine", "cells.assembly"],
            "cells.tool": [],  # An entry point: no importer at all, so it stays.
            "cells.core.independent": ["cells.processes.both"],  # Unreached, stays.
            "cells.processes.both": [],  # Imported by a moved and by a staying module: stays.
            "cells.processes.reached_law": [],  # Reached, imported only by a moved module.
            "cells.pkg/": [],
            "cells.pkg.a": ["cells.models.old_model"],  # Moves.
            "cells.pkg.b": [],  # Stays, so the package's __init__ stays.
            # D188 R1: the registration imports every older family; the entry names it.
            "cells.legacy/": [],
            "cells.legacy.registration": [
                "cells.models.old_model",
                "cells.processes.via_registration",
            ],
            "cells.core.legacy_entry": ["cells.legacy.registration"],
            "cells.processes.via_registration": [],  # Imported by the registration only.
            "cells.ensemble/": [],
            "cells.ensemble.families": ["cells.models.old_model"],  # A dispatch point.
            "cells.core.old_parse": [],  # An older family's parser, whose class lives in specs.
            "cells.core.active_spec": ["cells.core.old_parse"],  # Reached: imports that parser.
        }
    )
    for target in ("cells.processes.both", "cells.processes.reached_law"):
        edges["cells.models.old_model"][target] = ([], "import")
    c = dict(
        legacy=["cells.core.old_spec", "cells.models.old_model", "cells.core.shared_spec"],
        private=[
            "cells.processes.law",
            "cells.processes.only_old",
            "cells.processes.via_registration",
            "cells.core.old_parse",
        ],
        side=[],
        dispatched=["cells.core.old_parse", "cells.models.old_model"],
    )
    reached = {
        "cells.core.shared_spec",
        "cells.core.specs",
        "cells",
        "cells.core",
        "cells.processes.reached_law",
        "cells.models.active",
        "cells.models",
        "cells.processes",
        "cells.core.legacy_entry",
        "cells.core.active_spec",
    }
    moved, notes = move_set(c, reached, index, edges)
    cells = [m for m in index if m.startswith("cells")]
    checks = {
        "an unreached family module moves": "cells.core.old_spec" in moved,
        "a reached family module stays": "cells.core.shared_spec" not in moved,
        "kept: a non-family module the core imports stays": "cells.processes.law" not in moved
        and notes["kept_imported_by_the_core"] == ["cells.processes.law"],
        "a module only older families reach moves": "cells.processes.only_old" in moved,
        "pulled: an importer of a moved module moves": "cells.core.helper" in moved
        and "cells.core.helper" in notes["pulled_in_by_importers"],
        "a family module the core imports is a coupling, not kept": [
            "cells.core.shared_spec",
            ["cells.core.old_spec"],
        ]
        in couplings_of(moved, edges, cells),
        "R1: a dispatch point's import of a moved module is a coupling": [
            "cells.ensemble.families",
            ["cells.models.old_model"],
        ]
        in couplings_of(moved, edges, cells),
        "R1: the legacy package neither moves nor counts as a coupling": not (
            {"cells.legacy", "cells.legacy.registration"} & moved
        )
        and not [m for m, _ in couplings_of(moved, edges, cells) if m.startswith("cells.legacy")],
        "R1: the registration is a transit node: what only it imports still moves": (
            "cells.processes.via_registration" in moved
        ),
        "R1: a parser the registration dispatches to is a coupling, not kept": (
            "cells.core.old_parse" in moved
            and ["cells.core.active_spec", ["cells.core.old_parse"]]
            in couplings_of(moved, edges, cells)
        ),
        "a dispatch point neither moves nor keeps": "cells.core.specs" not in moved,
        "moved with its importers: a module only moved modules import moves": (
            "cells.assembly.controls" in moved
            and "cells.assembly.controls" in notes["moved_with_their_only_importers"]
        ),
        "an entry point with no importer stays": "cells.tool" not in moved,
        "a module a staying module also imports stays": "cells.processes.both" not in moved,
        "a reached module stays though only moved modules import it": (
            "cells.processes.reached_law" not in moved
        ),
        "a package's __init__ moves with its last module": notes["package_inits"]
        == ["cells.assembly"],
        "a package's __init__ stays while one of its modules stays": "cells.pkg" not in moved
        and "cells.pkg.a" in moved,
    }
    checks.update(_after_move1_checks())
    checks.update(_classes_checks())
    # The planted control: without the rule, the law moves and the core imports a moved module.
    unkept = dict(c, private=c["private"])
    moved_plain = (set(unkept["legacy"]) | set(unkept["private"])) - reached - CHAINS
    checks["planted: without the keep rule the core would import a moved law"] = any(
        "cells.processes.law" in t for _, t in couplings_of(moved_plain, edges, cells)
    )
    checks.update(_reader_checks())
    failed = [k for k, v in checks.items() if not v]
    print(json.dumps(dict(checks=len(checks), failed=failed), indent=1))
    return 1 if failed else 0


def _classes_checks():
    """rule_family on planted families: a lineage family with a namespaced ID and its successor,
    active by their rows; a shared module's two families, one with a row; a family that only
    registered protocols name; and a planted unreferenced family, which must be legacy."""
    table = table_rows_of(
        "from types import MappingProxyType\n"
        "MODELS = MappingProxyType({\n"
        "    'cells.lineages@1': Model(type='family', module='cells.models.lineages.spec',\n"
        "        law_homes=('cells.models.lineages.gard',),\n"
        "        runner='cells.models.lineages.runner:run'),\n"
        "    'cells.lineages@2': Model(type='family', module='cells.models.lineages_v2.spec'),\n"
        "    'a@1': Model(type='family', module='cells.core.specs'),\n"
        "})\n"
    )

    def fam(definition, ids=(), class_ids=None):
        return dict(definition=definition, ids=list(ids), class_ids=class_ids or {"M": None})

    lineage = fam("cells.models.lineages.spec")  # Its namespaced ID escapes the ID pattern.
    successor = fam("cells.models.lineages_v2.spec")
    shared_a = fam(li.SHARED, ["a@1"], {"ASpec": "a@1"})
    shared_b = fam(li.SHARED, ["b@1"], {"BSpec": "b@1"})
    registered = fam("cells.core.r_spec", ["r@1"], {"R": "r@1"})
    planted = fam("cells.core.unreferenced_spec", ["old@1"], {"Old": "old@1"})
    protocols = [dict(ids=["r@1"], registered=True), dict(ids=["old@1"], registered=False)]

    def rule(f, rows=table):
        return rule_family(f, rows, protocols)

    return {
        "classes: the table is read statically, with its homes and its runner's module": (
            table["cells.lineages@1"]["homes"]
            == ["cells.models.lineages.gard", "cells.models.lineages.runner"]
        ),
        "classes: a namespaced ID escapes the inventory's ID pattern": not li.ID.match(
            "cells.lineages@1"
        ),
        "classes: a family with a row is active (by its module, its ID being namespaced)": (
            rule(lineage) == "active"
        ),
        "classes: a family's successor is active by its own row": rule(successor) == "active",
        "classes: a shared module's family is active by its ID's row, not by the module": (
            rule(shared_a) == "active" and rule(shared_b) == "legacy"
        ),
        "classes: registered protocols alone rule a family decide": rule(registered) == "decide",
        "planted: an unreferenced family is legacy (only an unregistered protocol names it)": (
            rule(planted) == "legacy"
        ),
        "planted: without the table the lineage families would be legacy": [
            rule(f, {}) for f in (lineage, successor, shared_a, registered)
        ]
        == ["legacy", "legacy", "legacy", "decide"],
    }


def _after_move1_checks():
    """A tree where move 1 is applied (17 November, move 2's step 1): the older families live under
    cells.legacy, and R1's entry point, which names the legacy registration by a string and which
    the dispatch points import only inside functions, is unreached and counts among the modules
    importing legacy code. It must stay; move 1's plan is then empty, and move 2's lists no legacy
    module, moved or unplaced."""
    global legacy_entries
    index, edges = _graph(
        {
            "cells/": [],
            "cells.core/": [],
            "cells.core.specs": [],  # A dispatch point.
            "cells.core.legacy_entry": [],
            "cells.core.runner": ["cells.core.specs"],
            "cells.legacy/": [],
            "cells.legacy.registration": ["cells.legacy.models.old_model"],
            "cells.legacy.models/": [],
            "cells.legacy.models.old_model": [],
            "cells.processes/": [],
            "cells.processes.mystery": [],
        }
    )
    edges["cells.core.legacy_entry"][li.REGISTRATION] = ([], "string")
    c = dict(
        legacy=["cells.legacy.models.old_model"],
        private=[],
        side=["cells.core.legacy_entry"],  # As the classes read it after move 1.
        dispatched=[],
    )
    reached = {"cells", "cells.core", "cells.core.specs", "cells.core.runner"}
    moved, _ = move_set(c, reached, index, edges)
    real = legacy_entries
    try:
        legacy_entries = lambda edges: set()  # noqa: E731  The planted control: the rule removed.
        planted, _ = move_set(c, reached, index, edges)
    finally:
        legacy_entries = real
    pairs, unplaced = move2_plan(index, moved1=set())
    return {
        "after move 1: R1's entry point stays, and move 1's plan is empty": moved == set(),
        "after move 1, planted: without the entry rule the entry would move": planted
        == {"cells.core.legacy_entry"},
        "after move 1: move 2 lists no legacy module, moved or unplaced": not [
            m for pair in pairs for m in pair if _in_legacy(m)
        ]
        and not [m for m in unplaced if _in_legacy(m)]
        and ["cells.core.runner", "cells.execution.runner"] in pairs
        and "cells.processes.mystery" in unplaced,
    }


def _reader_checks():
    """legacy_inventory.registry_dispatch on planted dispatch modules: get_model's chain, then
    the registration's model_for (D188 R1), each read by its function body only."""
    import tempfile

    files = {
        li.REGISTRY: (
            "from cells.core.active_spec import ActiveModel\n\n\n"
            "def get_model(spec):\n"
            "    if isinstance(spec, ActiveModel):\n"
            "        from cells.models import active\n\n"
            "        return active\n"
            "    from cells.core.legacy_entry import legacy\n\n"
            "    return legacy().model_for(spec)\n"
        ),
        li.REGISTRATION: (
            "from cells.core.old_spec import OldModel\n"
            "from cells.models import old_model\n\n\n"
            "def model_for(spec):\n"
            "    if isinstance(spec, OldModel):\n"
            "        return old_model\n"
            "    return None\n\n\n"
            "def control_values(spec, times):\n"
            "    from cells.core import schedule_part as part\n\n"
            "    if isinstance(spec, OldModel):\n"
            "        return part.control_values(spec, times)\n\n\n"
            "def parse(data):\n"
            "    from cells.core.old_spec import parse\n\n"
            "    return parse(data)\n"
        ),
    }
    others = [
        "cells.core.active_spec",
        "cells.models.active",
        "cells.core.old_spec",
        "cells.models.old_model",
        "cells.core.schedule_part",
        "cells.core.legacy_entry",
    ]
    with tempfile.TemporaryDirectory() as folder:
        index = {}
        for name in [*files, *others]:
            path = Path(folder) / (name.replace(".", "_") + ".py")
            path.write_text(files.get(name, ""))
            index[name] = path
        found = li.registry_dispatch(index)
        dispatched = li.registration_imports(index)
        del index[li.REGISTRATION]
        before_r1 = li.registry_dispatch(index)
    return {
        "reader: get_model's chain, then the registration's model_for": found
        == [
            ("cells.core.active_spec", "ActiveModel", "cells.models.active"),
            ("cells.core.old_spec", "OldModel", "cells.models.old_model"),
        ],
        "reader: a tree without the registration reads get_model alone": before_r1
        == [("cells.core.active_spec", "ActiveModel", "cells.models.active")],
        "reader: the registration's dispatch functions' imports, not its module-level ones": (
            dispatched == {"cells.core.old_spec", "cells.core.schedule_part"}
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "action", choices=["classes", "reach", "move1", "move2", "pins", "selftest"]
    )
    parser.add_argument("--out")
    parser.add_argument(
        "--g1", help="classes: a G1 run's merged folder (SET/WORLD.json), reported per family"
    )
    parser.add_argument("--report", nargs="*", help="pins: source_moves.py scan reports")
    args = parser.parse_args(argv)
    if args.action == "selftest":
        return selftest(args)
    if not args.out:
        parser.error(f"{args.action} needs --out")
    dict(classes=classes, reach=reach, move1=move1, move2=move2, pins=pins)[args.action](args)


if __name__ == "__main__":
    sys.exit(main())
