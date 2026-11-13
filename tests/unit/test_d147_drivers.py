"""D147's guard over the run drivers under validation/ (docs/DECISIONS.md D147).

A new definition of the resolved pump family with free field offsets declares field solver
version 3; drivers apply that with validation/tissue/field_solver_choice.declare(). This
test fails when a run driver (a module with main() or a __main__ block) uses a builder of a
free-offset world without importing field_solver_choice, unless it is listed in EXEMPT with
its reason. The builders are the 825-node scale world's modules, and the fixture functions
that build that world (BUILDER_FUNCTIONS: a driver reaching it through a fixture module).

The check is static: it sees imports and the named builder functions, not the worlds a
driver builds at run time. A driver that builds a free-offset world through another route
(its own construction, or a builder not named here) is outside its reach; D147's text names
the rule for such drivers.
"""

import ast
import functools
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHOICE = "validation.tissue.field_solver_choice"
BUILDERS = {
    "validation.tissue.resolved_scale_world",  # The 825-node world: 172 free offsets.
    "validation.tissue.surface_pump_v3_study",  # tissue_definition: that world as @3.
    "validation.tissue.heredity_pilot",  # tissue_world and prepare_worlds: the full tissue.
    "validation.tissue.pump_water_fixtures.scale_world",  # That world with water.
}
# Functions of other modules that build those worlds: using one counts as a builder import.
BUILDER_FUNCTIONS = {"validation.tissue.pump_water_fixtures": {"scale_world"}}
# Drivers that build these worlds and keep their declared solver on purpose.
EXEMPT = {
    "validation/ensemble/batched_worlds_study.py": "study recorded before D147; reruns it",
    "validation/tissue/cell_replacement_cost.py": "cost study recorded before D147",
    "validation/tissue/cell_replacement_judge.py": "G2-Q1's judge: registered definitions",
    "validation/tissue/composite_crossrev.py": "cross-revision guard: the same definitions",
    "validation/tissue/composite_guard.py": "cross-revision guard: the same definitions",
    "validation/tissue/inplace_fix_guard.py": "D148 in-place-fix guard: recorded definitions",
    "validation/tissue/field_floor_guard.py": "declares version 2 and version 3 on purpose",
    "validation/tissue/field_floor_held.py": "declares version 3 on purpose (guard 6)",
    "validation/tissue/heredity_turnover_literature.py": "held-bath sheets only, no offsets",
    "validation/tissue/ledger_rounding_study.py": "study recorded before D147",
    "validation/tissue/pump_water_equivalence.py": "equivalence guard: water against @3",
    "validation/tissue/resolved_scale_study.py": "study recorded before D147",
    "validation/tissue/surface_pump_v3_study.py": "the builder (default version 2), its study",
}


def imported(tree):
    """Every absolute module imported anywhere in the module (functions included), and
    module.function for each BUILDER_FUNCTIONS function the module uses."""
    out, attributes = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module)
            out |= {f"{node.module}.{a.name}" for a in node.names}
        elif isinstance(node, ast.Attribute):
            attributes.add(node.attr)
    for module, functions in BUILDER_FUNCTIONS.items():
        if module in out:
            out |= {f"{module}.{f}" for f in functions & attributes}
    return out


def is_driver(tree):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return True
        if isinstance(node, ast.If) and "__main__" in ast.unparse(node.test):
            return True
    return False


@functools.cache
def modules():
    """{path: (imported modules, is a driver)} for every module under validation/ (parsed once)."""
    out = {}
    for path in sorted((ROOT / "validation").rglob("*.py")):
        tree = ast.parse(path.read_text())
        out[path.relative_to(ROOT).as_posix()] = (imported(tree), is_driver(tree))
    return out


def test_drivers_of_free_offset_worlds_choose_the_solver_by_d147():
    offenders = [
        name
        for name, (names, driver) in modules().items()
        if driver and names & BUILDERS and name not in EXEMPT and CHOICE not in names
    ]
    assert not offenders, (
        "Run drivers building free-offset worlds without field_solver_choice.declare() "
        f"(D147): {offenders}. Call it, or add the driver to EXEMPT with its reason."
    )


def test_every_exemption_is_still_a_driver_of_those_worlds():
    found = modules()
    stale = [
        name
        for name in EXEMPT
        if name not in found or not found[name][1] or not found[name][0] & BUILDERS
    ]
    assert not stale, f"Remove these EXEMPT entries: {stale}"


@pytest.mark.parametrize("builder", ["scale_world", "study_tissue"])
def test_the_builders_build_free_offset_worlds(builder):
    from validation.tissue import field_solver_choice as choice
    from validation.tissue import resolved_scale_world, surface_pump_v3_study

    raw = (
        resolved_scale_world.definition()
        if builder == "scale_world"
        else surface_pump_v3_study.tissue_definition(dt=1e-3, end_time=0.01)
    )
    assert choice.free_field_offsets(raw) > 0


SOURCES = {  # Synthetic modules: is each one a driver that breaks the rule?
    "from validation.tissue import resolved_scale_world\n\ndef main():\n    pass\n": True,
    "def main():\n    from validation.tissue import heredity_pilot as p\n": True,
    "from validation.tissue import pump_water_fixtures as fx\n\n"
    "def main():\n    fx.scale_world()\n": True,
    "from validation.tissue import pump_water_fixtures as fx\n\n"
    "def main():\n    fx.heredity_cell('D')\n": False,  # No free-offset world.
    "import validation.tissue.surface_pump_v3_study\nif __name__ == '__main__':\n    pass\n": True,
    "from validation.tissue import field_solver_choice, resolved_scale_world\n\n"
    "def main():\n    pass\n": False,
    "from validation.tissue import resolved_scale_world\n": False,  # Not a driver.
}


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_the_scan_sees_a_driver_without_the_choice(source):
    tree = ast.parse(source)
    names = imported(tree)
    assert (is_driver(tree) and bool(names & BUILDERS) and CHOICE not in names) is SOURCES[source]
