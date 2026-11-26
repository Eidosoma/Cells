"""The operator section of the build's registry (docs/CORE_SEAMS_DESIGN.md §8.4; seam F).

Operators register the way kinds do, each claim with a planted error it must catch (D187):
- the one registration call runs the contract's check_declarations (planted: an operator whose
  owned heat field is undeclared, which today's plain dictionary took without a check);
- a duplicate ID is refused whatever its spelling, and a built-in's ID is never rebound in
  another section, whose compositions the composite caches by law ID (planted: a second class
  under a built-in's namespaced ID, in BUILTIN's copy and in a fresh section);
- OPERATORS is the active section: today's keys, order and exact-key lookup, scoped to the build
  (planted: an operator registered only in a scoped section);
- a package registers every operator its modules define, so a new operator module joins with no
  edit to the package's __init__ (CORE_SEAMS §18's further hand-offs): the composite's package
  defines exactly its FIRST, in today's order, and a planted package's later module joins it
  (planted: classes imported from this package and from another, an intermediate base, an
  inherited LAW_ID and a non-operator, none of which is an operator; and, each refused, an
  operator that breaks the contract, a module that fails to import, a subpackage, and a FIRST
  naming a class the package does not define);
- an operator's standard free energies (seam E) are checked as a kind's are, and name no law,
  since an operator hosts none; either dG° form reads, dG°/RT or dG° in kJ/mol with its basis;
  today's operators declare none (planted, each refused: an entry naming a registered cycle law, a
  list, a bare 3-tuple, a zero c0, and an entry giving both forms).
"""

import importlib
import re
import sys

import pytest

import cells.operators as package
from cells.operators import OPERATORS, contract
from cells.operators.osmotic_water import OsmoticWater
from cells.registry import kind_registry, operators
from cells.registry import laws as law_registry

TODAY = (  # The built-in package's registration order: today's dictionary's order.
    "cells.operator.ideal_osmosis_linear_compliance_water@1",
    "cells.operator.k_anion_symport_mass_action@1",
    "cells.operator.scheduled_cell_replacement@1",
)
HEADER = "from cells.operators.contract import Operator\n\n\n"
EXISTING = HEADER + (
    "class Existing(Operator):\n    LAW_ID = 'tests.operator.existing_operator@1'\n    EVENT = "
    "True\n"
)
NEW = HEADER + (
    "from cells.operators.osmotic_water import OsmoticWater  # Imported from another package.\n"
    "from {package}.a_existing import Existing  # Imported: its own module's, not this one's.\n\n\n"
    "class Base(Operator):  # An intermediate base: no LAW_ID of its own.\n    EVENT = True\n\n\n"
    "class New(Base):\n    LAW_ID = 'tests.operator.new_operator@1'\n\n\n"
    "class Inherits(New):  # It only inherits New's LAW_ID: not a second operator.\n    pass\n\n\n"
    "class Helper:  # Not an Operator.\n    LAW_ID = 'tests.operator.not_an_operator@1'\n"
)
NEWER = HEADER + (
    "class Newer(Operator):\n    LAW_ID = 'tests.operator.newer_operator@1'\n    EVENT = True\n"
)
UNBOOKED = HEADER + (  # The contract's planted error below, in a module of its own.
    "class Unbooked(Operator):\n    LAW_ID = 'tests.operator.unbooked_operator@1'\n    EVENT = "
    "True\n"
    "    STATE_AXES = {'unbooked_dissipated_energy_pJ': ('cell_slot',)}\n"
)


class Planted(contract.Operator):
    """A valid declaration: an event part and nothing else."""

    LAW_ID = "tests.operator.planted_operator@1"
    EVENT = True


class Unbooked(contract.Operator):
    """The planted error: an owned field named as heat but not declared as heat."""

    LAW_ID = "tests.operator.unbooked_operator@1"
    EVENT = True
    STATE_AXES = {"unbooked_dissipated_energy_pJ": ("cell_slot",)}


def test_operators_register_with_check_declarations():
    section = operators.OperatorRegistry()
    with pytest.raises(ValueError, match="declared as heat or work"):
        section.register(Unbooked)
    with pytest.raises(ValueError, match="declared as heat or work"):
        OPERATORS[Unbooked.LAW_ID] = Unbooked()
    assert Unbooked.LAW_ID not in OPERATORS and Unbooked.LAW_ID not in section
    with pytest.raises(ValueError):  # Today's dictionary took this one without a check.
        contract.check_declarations(Unbooked)
    instance = section.register(Planted)
    assert isinstance(instance, Planted) and section.register(Planted) is instance  # Idempotent.
    assert section.lookup("tests.operator.planted_operator@1") is instance


def test_a_duplicate_operator_id_is_refused_whatever_its_spelling():
    class Twin(OsmoticWater):
        LAW_ID = kind_registry.qualified(OsmoticWater.LAW_ID)  # A built-in's, namespaced.

    section = operators.BUILTIN.extended()
    with pytest.raises(ValueError, match="already registered"):
        section.register(Twin)
    with pytest.raises(ValueError, match="already registered"):
        section.register(OsmoticWater())  # A second instance of the built-in's class.
    assert section.lookup(Twin.LAW_ID) is OPERATORS[OsmoticWater.LAW_ID]
    with pytest.raises(ValueError, match="only as BUILTIN's own"):
        operators.OperatorRegistry().register(Twin)
    fresh = operators.OperatorRegistry()
    assert fresh.register(OsmoticWater) is OPERATORS[OsmoticWater.LAW_ID]  # One object per ID.


def test_operators_is_the_active_section_with_todays_keys():
    count = len(operators.BUILTIN.operators())
    assert tuple(OPERATORS)[: len(TODAY)] == TODAY and len(OPERATORS) == count
    assert all(type(op).LAW_ID == law for law, op in OPERATORS.items())
    assert tuple(OPERATORS.values()) == operators.BUILTIN.operators()
    name = TODAY[0].rsplit(".", 1)[-1]
    spellings = (name, f"cells.{name}", f"cells.operator.{name}")
    assert [s for s in spellings if s in OPERATORS] == [TODAY[0]]  # Exact keys: one spelling.
    assert dict(OPERATORS) == OPERATORS and OPERATORS == dict(OPERATORS)
    with operators.scope(operators.BUILTIN.extended(Planted)):
        assert Planted.LAW_ID in OPERATORS and len(OPERATORS) == count + 1
        assert isinstance(OPERATORS[Planted.LAW_ID], Planted)
    assert Planted.LAW_ID not in OPERATORS  # A module-level dictionary would still hold it.
    OPERATORS[Planted.LAW_ID] = Planted()  # Assignment registers on the active section ...
    try:
        assert operators.BUILTIN.lookup(Planted.LAW_ID) is OPERATORS[Planted.LAW_ID]
        with pytest.raises(ValueError, match="already registered"):
            OPERATORS[Planted.LAW_ID] = Planted()
    finally:
        del OPERATORS[Planted.LAW_ID]  # ... and deletion unregisters it.
    assert Planted.LAW_ID not in operators.BUILTIN and len(OPERATORS) == count


def test_the_composite_s_package_registers_each_operator_its_modules_define():
    """The section is FIRST, in today's order, then every other operator the package defines, in
    package_operators' order: a later operator module joins this list with no edit to this test
    or to FIRST (at c09ae4c7 the package defined FIRST's 19 alone, checked against main)."""
    defined = operators.package_operators("cells.operators")
    assert set(package.FIRST) <= set(defined) and len(set(package.FIRST)) == len(package.FIRST)
    assert tuple(c.LAW_ID for c in package.FIRST)[: len(TODAY)] == TODAY  # Today's order.
    expected = (*package.FIRST, *(c for c in defined if c not in package.FIRST))
    registered = tuple(type(op) for op in operators.BUILTIN.operators())
    assert registered[: len(expected)] == expected  # Planted operators of other tests follow.
    assert tuple(OPERATORS)[: len(expected)] == tuple(c.LAW_ID for c in expected)


@pytest.fixture
def planted_packages(tmp_path, monkeypatch):
    """A writer of planted operator packages under tmp_path, importable by name; their modules
    leave sys.modules afterwards."""
    monkeypatch.syspath_prepend(str(tmp_path))
    names = []

    def write(name, modules):
        root = tmp_path / name
        root.mkdir()
        (root / "__init__.py").write_text("")
        for leaf, text in modules.items():
            (root / f"{leaf}.py").write_text(text.replace("{package}", name))
        importlib.invalidate_caches()
        names.append(name)
        return root

    yield write
    for key in [k for k in sys.modules if k.split(".", 1)[0] in names]:
        del sys.modules[key]


def test_a_new_operator_module_joins_its_package_with_no_edit_there(planted_packages):
    root = planted_packages("planted_operators", {"a_existing": EXISTING, "b_new": NEW})
    existing = importlib.import_module("planted_operators.a_existing").Existing
    new = importlib.import_module("planted_operators.b_new").New
    # The imported class, the base, the inherited LAW_ID and the non-operator are not operators.
    assert operators.package_operators("planted_operators") == (existing, new)
    section = operators.OperatorRegistry()
    registered = operators.register_package(section, "planted_operators", first=(new,))
    assert (
        [type(op) for op in registered]
        == [new, existing]
        == [type(op) for op in section.operators()]
    )
    # A module written later joins, with no edit to the package's __init__ (still empty).
    (root / "c_newer.py").write_text(NEWER)
    importlib.invalidate_caches()
    later = operators.OperatorRegistry()
    operators.register_package(later, "planted_operators", first=(existing,))
    newer = importlib.import_module("planted_operators.c_newer").Newer
    assert [type(op) for op in later.operators()] == [existing, new, newer]
    assert (root / "__init__.py").read_text() == ""
    # Planted: each refused, and nothing registered by the refused call.
    with pytest.raises(ValueError, match="names each of its own operators once"):
        operators.register_package(
            operators.OperatorRegistry(), "planted_operators", first=(OsmoticWater,)
        )
    planted_packages("planted_unbooked", {"a_existing": EXISTING, "b_unbooked": UNBOOKED})
    unbooked = operators.OperatorRegistry()
    with pytest.raises(ValueError, match="declared as heat or work"):
        operators.register_package(unbooked, "planted_unbooked")
    assert "tests.operator.unbooked_operator@1" not in unbooked
    planted_packages("planted_broken", {"a_broken": "raise RuntimeError('a planted failure')\n"})
    with pytest.raises(RuntimeError, match="a planted failure"):
        operators.package_operators("planted_broken")
    nested = planted_packages("planted_nested", {"a_existing": EXISTING})
    (nested / "inner").mkdir()
    (nested / "inner" / "__init__.py").write_text(NEWER)
    importlib.invalidate_caches()
    with pytest.raises(ValueError, match="holds modules, not subpackages"):
        operators.package_operators("planted_nested")


class PlantedReaction:
    """A planted composite operator's standard free energies hook, by its LAW_ID."""

    LAW_ID = "tests.operator.planted_reaction@1"

    def __init__(self, entries):
        self.entries = entries

    def standard_free_energies(self, declaration):
        return self.entries


def test_an_operator_s_standard_free_energies_are_checked_and_name_no_law():
    reaction = kind_registry.FreeEnergyEntry((("A", -1), ("B", 1)), -2.0, 1000.0)
    cited = reaction._replace(
        dG_RT=None, dG_kJ_mol=-5.2, dG_basis=kind_registry.TEMPERATURE_INDEPENDENT
    )
    assert operators.operator_standard_free_energies(OsmoticWater(), None) == ()  # Today's.
    assert operators.operator_standard_free_energies(PlantedReaction((reaction, cited)), None) == (
        reaction,
        cited,
    )
    law = law_registry.active().laws(law_registry.CYCLE_LAW, "cells.kind.transporter@1")[0]
    for entries, words in (
        ((reaction._replace(law_id=law.law_id, mode="coupled"),), "is not a cycle law it hosts"),
        ([reaction], "returns a tuple of FreeEnergyEntry"),
        (((reaction.stoichiometry, -2.0, 1000.0),), "returns a tuple of FreeEnergyEntry"),
        ((reaction._replace(c0=0.0),), "its c0 is finite and positive"),
        ((cited._replace(dG_RT=-2.0),), "it gives its dG° in exactly one form"),
    ):
        with pytest.raises(ValueError, match=re.escape(words)):
            operators.operator_standard_free_energies(PlantedReaction(entries), None)
