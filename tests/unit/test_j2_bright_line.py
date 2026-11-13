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
* an import of the engine's partition operator or its definition helper, or of R-ops;
* the use of R-tissue's division entry point. R-tissue's static entry point is kept apart, so its
  cross-check against R-full may read J1.

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
