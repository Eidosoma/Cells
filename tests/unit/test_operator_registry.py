"""The operator section of the build's registry (docs/CORE_SEAMS_DESIGN.md §8.4; seam F).

Operators register the way kinds do, each claim with a planted error it must catch (D187):
- the one registration call runs the contract's check_declarations (planted: an operator whose
  owned heat field is undeclared, which today's plain dictionary took without a check);
- a duplicate ID is refused whatever its spelling (planted: a second class under a built-in's
  namespaced ID);
- OPERATORS is the active section: today's keys, order and exact-key lookup, scoped to the build
  (planted: an operator registered only in a scoped section).
"""

import pytest

from cells.models.operators import OPERATORS, contract
from cells.models.operators.osmotic_water import OsmoticWater
from cells.registry import operators

TODAY = (  # The built-in package's registration order: today's dictionary's order.
    "ideal_osmosis_linear_compliance_water@1",
    "k_anion_symport_mass_action@1",
    "scheduled_cell_replacement@1",
)


class Planted(contract.Operator):
    """A valid declaration: an event part and nothing else."""

    LAW_ID = "tests.planted_operator@1"
    EVENT = True


class Unbooked(contract.Operator):
    """The planted error: an owned field named as heat but not declared as heat."""

    LAW_ID = "tests.unbooked_operator@1"
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
    assert section.lookup("tests.planted_operator@1") is instance


def test_a_duplicate_operator_id_is_refused_whatever_its_spelling():
    class Twin(OsmoticWater):
        LAW_ID = "cells." + OsmoticWater.LAW_ID  # The namespaced spelling of a built-in's ID.

    section = operators.BUILTIN.extended()
    with pytest.raises(ValueError, match="already registered"):
        section.register(Twin)
    with pytest.raises(ValueError, match="already registered"):
        section.register(OsmoticWater())  # A second instance of the built-in's class.
    assert section.lookup(Twin.LAW_ID) is OPERATORS[OsmoticWater.LAW_ID]


def test_operators_is_the_active_section_with_todays_keys():
    assert tuple(OPERATORS)[: len(TODAY)] == TODAY and len(OPERATORS) == 19
    assert all(type(op).LAW_ID == law for law, op in OPERATORS.items())
    assert tuple(OPERATORS.values()) == operators.BUILTIN.operators()
    assert "cells." + TODAY[0] not in OPERATORS  # Exact keys, as definitions compare them.
    assert dict(OPERATORS) == OPERATORS and OPERATORS == dict(OPERATORS)
    with operators.scope(operators.BUILTIN.extended(Planted)):
        assert Planted.LAW_ID in OPERATORS and len(OPERATORS) == 20
        assert isinstance(OPERATORS[Planted.LAW_ID], Planted)
    assert Planted.LAW_ID not in OPERATORS  # A module-level dictionary would still hold it.
    OPERATORS[Planted.LAW_ID] = Planted()  # Assignment registers on the active section ...
    try:
        assert operators.BUILTIN.lookup(Planted.LAW_ID) is OPERATORS[Planted.LAW_ID]
        with pytest.raises(ValueError, match="already registered"):
            OPERATORS[Planted.LAW_ID] = Planted()
    finally:
        del OPERATORS[Planted.LAW_ID]  # ... and deletion unregisters it.
    assert Planted.LAW_ID not in operators.BUILTIN and len(OPERATORS) == 19
