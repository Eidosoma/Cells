"""The J2 bright line (docs/CELL_DIVISION_S5_DESIGN.md §10.1; decision 10, confirmed 13 November).

Until the user releases J2, nothing in the repository combines the J1 inputs with a partition. That
covers anything built from the J1 declared inputs (validation/division/j1_declared_inputs.json) or
the J1 record (j1_prediction_of_record.json), directly or through a function that reads them,
together with a partition. This test fails for a module under validation/, tests/ or scripts/ that
holds both kinds of source, unless the module is listed in EXEMPT with its reason. EXEMPT starts
empty; a J2 driver enters it only after the user releases J2, citing that decision.

A J1 source in a module is any of:
* a string constant, docstrings excepted, that names either J1 file;
* an import of a J1 module (J1_MODULES): one that reads them itself;
* the use of a J1-reading function of cleft_egg_reference (J1_FUNCTIONS). These count at function
  level, as D147's BUILDER_FUNCTIONS do, because R-tissue imports that module's transport laws
  without reading J1.

A partition source is any of:
* a string constant naming the partition law;
* an import of the engine's partition operator or its definition helper, of R-ops, of S5's compact
  worlds (tests/partition_fixtures), of the Q10 driver, of the egg-scale division world, of the
  Q2, Q3 and Q5 comparison drivers, of Q2's domain probe or of S5's own crossrev set;
* the use of R-tissue's division entry point. R-tissue's static entry point is kept apart, so its
  cross-check against R-full may read J1.

insertion@2 and lumen@2 stay off the partition list, because Q7 puts them beside a J1 module, on
the lead's condition: neither reaches a partition module through its explicit imports,
transitively (the scan at the end, with a positive control).

The check is static, at module granularity, and sees only the listed sources, as D147's driver
test does. Use through an unlisted builder is outside its reach; the rule binds anyway (§10.1).
Literals below are split so this module holds no source itself. Only files whose text carries a
marker of both kinds are parsed, which keeps the scan fast.
"""

import ast
import functools
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ("validation", "tests", "scripts")
J1_FILES = ("j1_" + "declared_inputs", "j1_" + "prediction_of_record")
PARTITION_LAW = "isopotential_" + "partition@1"
J1_MODULES = {
    "validation.division.cleft_egg_engine",
    "validation.division.static_cleft_egg_steps",
    "validation.division.j1_diagnostic_runner",
    "validation.division.j1_combination_runner",
    "validation.tissue.injection_rm1",
    "validation.division.cleft_tissue_crosscheck",  # R-tissue against R-full (the lead).
}
REFERENCE = "validation.division.cleft_egg_reference"
J1_FUNCTIONS = {
    f"{REFERENCE}.{name}"
    for name in ("DECLARED", "load_declared", "build", "scalar_values", "band_members")
}
PARTITION_MODULES = {
    "cells.models.operators.partition",  # isopotential_partition@1.
    "cells.core.partition_spec",  # Its definition helper.
    "validation.division.partition_reference",  # R-ops.
    "tests.partition_fixtures",  # S5's compact worlds (the lead, 13 November).
    "validation.division.q10_sensitivity",  # The Q10 driver.
    "validation.division.egg_division_world",  # S5's egg-scale accounting world.
    "validation.division.q2_rops_comparison",  # Q2: the engine against R-ops.
    "validation.division.q3_tissue_comparison",  # Q3: the engine against R-tissue.
    "validation.division.q5_order",  # Q5: the observed order.
    "validation.division.q2_domain_probe",  # Q2's sampling rule against the engine's checks.
    "validation.division.division_crossrev",  # S5's own crossrev world set (§8.4).
}
PARTITION_FUNCTIONS = {"validation.division.cleft_tissue_reference.simulate_divisions"}
# Text that every source of each kind must contain (the pre-filter).
J1_MARKERS = (*J1_FILES, *(m.rsplit(".", 1)[1] for m in J1_MODULES), "cleft_egg_reference")
PARTITION_MARKERS = (
    "isopotential_" + "partition",
    "partition_spec",
    "partition_reference",
    "operators.partition",
    "operators import partition",
    "simulate_divisions",
    "partition_fixtures",
    "q10_sensitivity",
    "egg_division_world",
    "q2_rops_comparison",
    "q3_tissue_comparison",
    "q5_order",
    "q2_domain_probe",
    "division_crossrev",
)
EXEMPT = {}  # {path: reason}; a J2 driver enters only after the user releases J2.


def module_name(path):
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def docstrings(tree):
    """ids of the docstring constants of the module, its classes and functions."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    out.add(id(body[0].value))
    return out


def imported(tree, name):
    """Absolute imported modules, module.attribute for each name imported from a module, and
    alias.attribute uses resolved to module.attribute (relative imports resolved from name)."""
    out, aliases = set(), {}
    package = name.rsplit(".", 1)[0] if "." in name else ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
                if a.asname:
                    aliases[a.asname] = a.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                module = ".".join([*base, *([node.module] if node.module else [])])
            else:
                module = node.module or ""
            out.add(module)
            for a in node.names:
                out.add(f"{module}.{a.name}")
                aliases[a.asname or a.name] = f"{module}.{a.name}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            chain, value = [node.attr], node.value
            while isinstance(value, ast.Attribute):
                chain.append(value.attr)
                value = value.value
            if isinstance(value, ast.Name):
                head = aliases.get(value.id, value.id)
                for k in range(1, len(chain) + 1):
                    out.add(".".join([head, *reversed(chain[-k:])]))
    return out


def sources(source, name):
    """(J1 sources, partition sources) of one module's text, as sets of descriptions."""
    tree = ast.parse(source)
    skip = docstrings(tree)
    j1, partition = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            j1 |= {f"literal {k}" for k in J1_FILES if k in node.value}
            if PARTITION_LAW in node.value:
                partition.add("literal " + PARTITION_LAW)
    names = imported(tree, name)
    j1 |= names & (J1_MODULES | J1_FUNCTIONS)
    partition |= names & (PARTITION_MODULES | PARTITION_FUNCTIONS)
    return j1, partition


@functools.cache
def scanned():
    """{path: (J1 sources, partition sources)} for every module that carries markers of both."""
    out = {}
    for top in SCOPE:
        for path in sorted((ROOT / top).rglob("*.py")):
            text = path.read_text()
            if not any(m in text for m in J1_MARKERS) or not any(
                m in text for m in PARTITION_MARKERS
            ):
                continue
            out[path.relative_to(ROOT).as_posix()] = sources(text, module_name(path))
    return out


def test_no_module_builds_from_j1_with_a_partition():
    offenders = {
        path: (sorted(j1), sorted(partition))
        for path, (j1, partition) in scanned().items()
        if j1 and partition and path not in EXEMPT
    }
    assert not offenders, (
        "Modules combining a J1 input with a partition (the J2 bright line, S5 design §10.1): "
        f"{offenders}. J2 is held; only the user's release admits a J2 driver to EXEMPT."
    )


def test_exemptions_are_still_needed():
    found = scanned()
    stale = [p for p in EXEMPT if p not in found or not all(found[p])]
    assert not stale, f"Remove these EXEMPT entries: {stale}"


@pytest.mark.parametrize("module", sorted(J1_MODULES))
def test_each_listed_j1_module_reads_a_j1_input(module):
    path = ROOT / (module.replace(".", "/") + ".py")
    j1, _ = sources(path.read_text(), module)
    assert j1, f"{module} no longer reads a J1 input: update J1_MODULES"


def test_the_listed_j1_functions_exist_and_their_module_names_a_j1_file():
    path = ROOT / (REFERENCE.replace(".", "/") + ".py")
    tree = ast.parse(path.read_text())
    defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    defined |= {
        t.id
        for n in tree.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
    }
    assert {f.rsplit(".", 1)[1] for f in J1_FUNCTIONS} <= defined
    assert sources(path.read_text(), REFERENCE)[0], "cleft_egg_reference names no J1 file"


def test_the_engine_partition_module_declares_the_law():
    path = ROOT / "src/cells/models/operators/partition.py"
    if path.exists():
        assert PARTITION_LAW in path.read_text()


J1_FILE = J1_FILES[0] + ".json"
PARTITION_IMPORT = "from cells.models.operators import partition as op"
SOURCES = {  # Synthetic modules: (does it hold a J1 source, a partition source)?
    f"import json\nD = '{J1_FILE}'\nLAW = '{PARTITION_LAW}'\n": (True, True),
    f'"""Mentions {J1_FILE} and {PARTITION_LAW} in its docstring."""\n': (False, False),
    "from validation.division import cleft_egg_engine\n" + PARTITION_IMPORT + "\n": (True, True),
    "from validation.division import cleft_egg_reference as ref\n"
    "x = ref.build(ref.load_declared(), {})\n": (True, False),
    "from validation.division import cleft_egg_reference as ref\n"
    "flux = ref.ghk_flux(1.0, 1, 0.0, 1.0, 1.0)\n": (False, False),
    "from validation.division.cleft_egg_reference import scalar_values\n": (True, False),
    "import validation.tissue.injection_rm1 as rm1\n": (True, False),
    "from validation.division import cleft_tissue_reference as rt\nrt.simulate_divisions()\n": (
        False,
        True,
    ),
    "from validation.division import cleft_tissue_reference as rt\nrt.simulate_static()\n": (
        False,
        False,
    ),
    "import cells.core.partition_spec\n": (False, True),
    "from validation.division import partition_reference\n": (False, True),
}


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_the_scan_sees_each_form(source):
    j1, partition = sources(source, "validation.division.synthetic")
    assert (bool(j1), bool(partition)) == SOURCES[source]


def test_relative_imports_resolve():
    j1, _ = sources("from . import cleft_egg_engine\n", "validation.division.synthetic")
    assert "validation.division.cleft_egg_engine" in j1


# ---------------------------------------------------------------- insertion@2 and lumen@2 (Q7)
# S3's cleft egg on insertion@2 and lumen@2 (Q7) puts a J1 module beside them, so they stay off
# the partition list on one condition (the lead, 13 November): neither imports anything on it,
# transitively. The scan follows explicit imports through the repository's modules. It does not
# follow the operator and model registries: every engine user reaches them, and they register
# every law. Reaching the partition through them would need its law named in a definition, which
# the literal check above sees.
REGISTRIES = {"cells.models.operators", "cells.models.registry"}
CLEAN = (
    "cells.models.operators.membrane_insertion_v2",
    "cells.models.operators.restricted_lumen_v2",
)


@functools.cache
def module_file(name):
    for base in (ROOT / "src", ROOT):
        stem = base / name.replace(".", "/")
        for path in (stem.with_suffix(".py"), stem / "__init__.py"):
            if path.is_file():
                return path
    return None


def reached(name):
    """Every repository module reached from name through explicit imports (registries
    recorded but not followed)."""
    seen, stack = set(), [name]
    while stack:
        module = stack.pop()
        if module in seen:
            continue
        seen.add(module)
        if module_file(module) is None or (module in REGISTRIES and module != name):
            continue
        stack.extend(imports_of(module))
    return seen


@functools.cache
def imports_of(module):
    """The repository modules a module imports explicitly (each import's longest module
    prefix)."""
    out = set()
    for dotted in imported(ast.parse(module_file(module).read_text()), module):
        parts = dotted.split(".")
        for k in range(len(parts), 0, -1):
            candidate = ".".join(parts[:k])
            if module_file(candidate) is not None:
                out.add(candidate)
                break
    return tuple(sorted(out))


@pytest.mark.parametrize("module", CLEAN)
def test_insertion_v2_and_lumen_v2_reach_no_partition_code(module):
    found = reached(module) & PARTITION_MODULES
    assert not found, f"{module} reaches {sorted(found)}: Q7 could reach partition code through it"


def test_the_import_scan_sees_a_partition_through_a_chain():
    # The bridge imports the partition directly, and lumen@2 reaches insertion@2.
    assert "cells.models.operators.partition" in reached("cells.models.operators.bridge_closure")
    assert "cells.models.operators.membrane_insertion_v2" in reached(CLEAN[1])
