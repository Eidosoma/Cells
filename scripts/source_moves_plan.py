"""D188's move plans: the classes, the name-level reach, draft move maps and code pins.

The evidence that scripts/source_moves.py's maps are built from
(docs/SOURCE_LAYOUT_MOVES_DESIGN.md):
  classes  the registry's families with D189's ruling (the nine active families' modules are the
           starts), from scripts/legacy_inventory.py's import graph cut at the dispatch points:
           the older families' modules, the modules reached only from them, the modules outside
           both that import them, and the module-level couplings into them
  reach    name-level reachability from the active entry points: the top-level definitions of
           each module that are reached, following imported names
  move1    move 1's draft map: what moves to src/cells/legacy/ (mirroring the sub-packages), the
           modules pulled in by their importers, the reached modules that still import a moved
           one (the refactors to make first) and the dispatch points' imports of moved modules
  move2    move 2's draft map, by a rule table, with the modules it does not place
  pins     the code pins in src/cells (a hex literal equal to a tracked file's SHA-256), their
           kind, the modules computing paths from their own __file__, and which of them the
           given scan reports (source_moves.py scan --out) touch
Static analysis (ast): imports made from computed names are not seen; source_moves.py scan lists
them as hazards. Each action reads the earlier ones' outputs from DIR. Usage, from a checkout,
PYTHONPATH=src:. :
  python scripts/source_moves_plan.py classes --out DIR --g1 G1_MERGED_DIR
  python scripts/source_moves_plan.py reach|move1|move2 --out DIR
  python scripts/source_moves_plan.py pins --out DIR [--report SCAN_JSON ...]
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

ACTIVE_RULED = ("active", "decide")  # D189: the four undecided families stay active.
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


def classes(args):
    """legacy_inventory's families and closures, with D189's four families active."""
    index = li.module_index()
    edges = li.graph(index)
    fams = li.families(index)
    worlds = li.g1_worlds(args.g1)
    rows = li.protocols()
    ruled = {}
    for key, fam in fams.items():
        g1 = {w for i in fam["ids"] for w in worlds.get(i, [])}
        mods = {fam["definition"], *fam["models"]}
        entry = any(mods & li._expand(es, index) for es in li.ENTRIES.values())
        registered = any(set(r["ids"]) & set(fam["ids"]) and r["registered"] for r in rows)
        ruled[key] = "active" if entry or g1 else ("decide" if registered else "legacy")
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
    starts = sorted((entry | act_mods) - legacy)
    active, cut = li.closure(starts, edges, stop=legacy | {li.REGISTRY}, leaves=li.DISPATCH)
    couplings = [
        dict(src=u, dst=v, names=n, kind=k, via=via)
        for u, v, n, k, via in cut
        if v != li.REGISTRY and u not in li.DISPATCH
    ]
    reach_legacy, _ = li.closure(
        sorted(legacy), edges, stop=active | {li.REGISTRY}, leaves=li.DISPATCH
    )
    cells = {m for m in index if m.startswith("cells")}
    private = sorted((reach_legacy - active) - legacy)
    rest = cells - active - reach_legacy - set(li.DISPATCH)
    side = sorted(m for m in rest if set(edges.get(m, {})) & (legacy | set(private)))
    out = dict(
        kind="cells.source_moves.classes@1",
        families={k: ruled[k] for k in sorted(ruled)},
        counts=Counter("active" if c in ACTIVE_RULED else "legacy" for c in ruled.values()),
        legacy=sorted(legacy),
        active=sorted(active),
        couplings=couplings,
        private=private,
        side=side,
        independent=sorted(rest - set(side)),
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


def move1(args):
    """Move 1's draft: older families' modules the active path does not reach, then their
    importers, except the dispatch points."""
    c = _load(args.out, "classes.json")
    r = _load(args.out, "reach.json")
    reached = {m for m, x in r.items() if x["status"] != "unreached"}
    index = li.module_index()
    edges = li.graph(index)
    legacy = (set(c["legacy"]) | set(c["private"]) | set(c["side"])) - reached - CHAINS
    pulled, changed = [], True
    while changed:
        changed = False
        for m in sorted(index):
            if not m.startswith("cells") or m in legacy or m in CHAINS or m in reached:
                continue
            if {t for t in edges.get(m, {}) if t.startswith("cells")} & legacy:
                legacy.add(m)
                pulled.append(m)
                changed = True
    couplings = [
        [m, sorted(t for t in edges.get(m, {}) if t in legacy)]
        for m in sorted(reached)
        if m not in CHAINS and set(edges.get(m, {})) & legacy
    ]
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
            pulled_in_by_importers=pulled,
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
}
REGISTRY = {"kind_registry", "species_registry", "inventory_species"}
RECORDS = {"io", "window_io", "batch_io", "batch_window_io", "run_view", "observers"}
STAY = ("numerics", "models", "analysis", "assays", "assembly", "assembly_pool", "ensemble", "laws")


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


def move2(args):
    """Move 2's draft: the modules move 1 leaves outside legacy/, by the rule table."""
    m1 = _load(args.out, "move1-draft.json")
    moved1 = {o for o, _ in m1["modules"]}
    mods = sorted(m for m in li.module_index() if m.startswith("cells.") and m not in moved1)
    pairs, unplaced = [], []
    for m in mods:
        new = _target2(m)
        if new and new != m:
            pairs.append([m, new])
        elif new is None and m.split(".")[1] not in STAY and m != "cells.__main__":
            unplaced.append(m)
    doc = dict(
        kind=MAP_KIND,
        move="d188-move-2-draft",
        description="DRAFT (D188 step 0), after move 1's draft; rule table in "
        "scripts/source_moves_plan.py",
        modules=pairs,
        packages=_packages(pairs),
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
                        kind="path" if isinstance(key, str) and key.endswith(".py") else "module",
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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("action", choices=["classes", "reach", "move1", "move2", "pins"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--g1", help="classes: a G1 run's merged folder (SET/WORLD.json)")
    parser.add_argument("--report", nargs="*", help="pins: source_moves.py scan reports")
    args = parser.parse_args(argv)
    if args.action == "classes" and not args.g1:
        parser.error("classes needs --g1")
    dict(classes=classes, reach=reach, move1=move1, move2=move2, pins=pins)[args.action](args)


if __name__ == "__main__":
    main()
