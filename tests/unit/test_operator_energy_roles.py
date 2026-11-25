"""Seam D's declared energy roles and seam E's hook on the operator contract
(docs/CORE_SEAMS_DESIGN.md §6.1 and §7.1; operators/contract.py).

* Every registered operator keeps today's energy tuples: its heat fields are heat and monotone, its
  work fields work and not monotone, so the composite's dissipation and energy-flow fields are
  today's, in today's order (no program changes).
* A declared non-monotone heat (GARD's event heat, closing against a state function) leaves the
  composite's dissipation check and stays among its energy flows; a stored field is a level, in
  neither.
* ENERGY_ROLES is checked at registration: EnergyRole values on owned state fields, consistent with
  HEAT_FIELDS and WORK_FIELDS, which the run view and the declarations manifest read.
* The free-energy hook defaults to none for every registered operator.
"""

import pytest

from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.operators import OPERATORS
from cells.operators.contract import (
    check_declarations,
    energy_roles,
    monotone_heat,
)
from cells.operators.membrane_insertion_v2 import ScheduledMembraneInsertionV2
from cells.operators.membrane_state import MembraneEntityState
from cells.registry.kind_registry import EnergyRole

HEAT = "insertion_dissipated_energy_pJ"


def test_every_registered_operator_keeps_todays_energy_roles():
    """Undeclared roles follow today's lists: heat monotone, work not, in STATE_AXES order, and the
    dissipation check's fields are HEAT_FIELDS, in their order."""
    assert OPERATORS
    for law, op in OPERATORS.items():
        roles = energy_roles(op)
        expected = {
            k: EnergyRole("heat", True) if k in op.HEAT_FIELDS else EnergyRole("work", False)
            for k in op.STATE_AXES
            if k in op.HEAT_FIELDS or k in op.WORK_FIELDS
        }
        assert roles == expected, law
        assert list(roles) == list(expected), law
        assert monotone_heat(op) == tuple(op.HEAT_FIELDS), law
        assert not op.ENERGY_ROLES, law  # No registered operator declares one yet.


def composition(*operators):
    return pump_composite.Composition(adapter, (MembraneEntityState(), *operators))


def todays_fields(composite):
    """The composite's two tuples by today's rule: every heat field is checked as dissipation, and
    every heat and work field is an energy flow, in state order."""
    ops = composite.operators
    flows = {*composite.inner.HEAT_FIELDS, *composite.inner.WORK_FIELDS}
    for op in ops:
        flows |= {*op.HEAT_FIELDS, *op.WORK_FIELDS}
    return (
        (*composite.inner.DISSIPATION_FIELDS, *(k for op in ops for k in op.HEAT_FIELDS)),
        tuple(k for k in composite.STATE_TYPE._fields if k in flows),
    )


def test_the_composites_dissipation_and_flow_fields_are_todays():
    composite = composition(ScheduledMembraneInsertionV2())
    dissipation, flows = todays_fields(composite)
    assert composite.DISSIPATION_FIELDS == dissipation
    assert composite.ENERGY_FLOW_FIELDS == flows
    assert HEAT in composite.DISSIPATION_FIELDS and HEAT in composite.ENERGY_FLOW_FIELDS


class EventHeat(ScheduledMembraneInsertionV2):
    """Insertion@2 with its heat declared non-monotone (a planted declaration)."""

    LAW_ID = "tests.event_heat_insertion@1"
    ENERGY_ROLES = {HEAT: EnergyRole("heat", False)}


def test_a_non_monotone_heat_is_booked_but_not_held_monotone():
    """Planted: a declared non-monotone heat leaves the dissipation check, which would refuse a
    falling element, and stays among the energy flows. If the composite ignored the declaration,
    the field would stay in DISSIPATION_FIELDS and this fails."""
    check_declarations(EventHeat)
    assert energy_roles(EventHeat)[HEAT] == EnergyRole("heat", False)
    assert monotone_heat(EventHeat) == ()
    composite = composition(EventHeat())
    dissipation, flows = todays_fields(composite)
    assert HEAT in dissipation  # Today's rule would hold it monotone ...
    assert HEAT not in composite.DISSIPATION_FIELDS  # ... the declaration does not.
    assert composite.DISSIPATION_FIELDS == tuple(k for k in dissipation if k != HEAT)
    assert composite.ENERGY_FLOW_FIELDS == flows  # Still booked as an energy flow.


class Stored(ScheduledMembraneInsertionV2):
    """Insertion@2 with one more owned field, declared stored (a planted level)."""

    LAW_ID = "tests.stored_insertion@1"
    STATE_AXES = {**ScheduledMembraneInsertionV2.STATE_AXES, "insertion_stored_pJ": ["cell_slot"]}
    ENERGY_ROLES = {"insertion_stored_pJ": EnergyRole("stored", False)}


def test_a_stored_field_is_a_level_in_neither_tuple():
    check_declarations(Stored)
    assert energy_roles(Stored)["insertion_stored_pJ"] == EnergyRole("stored", False)
    assert monotone_heat(Stored) == (HEAT,)
    composite = composition(Stored())
    assert "insertion_stored_pJ" not in composite.DISSIPATION_FIELDS
    assert "insertion_stored_pJ" not in composite.ENERGY_FLOW_FIELDS


def planted(name, **attributes):
    law_id = "tests.planted_operator@1".replace("planted_operator", name)
    return type(name, (ScheduledMembraneInsertionV2,), {"LAW_ID": law_id, **attributes})


REFUSED = {
    "work on a heat field": (
        dict(ENERGY_ROLES={HEAT: EnergyRole("work", False)}),
        "declared work, so it is listed in WORK_FIELDS alone",
    ),
    "a field it does not own": (
        dict(ENERGY_ROLES={"membrane_dissipated_energy_pJ": EnergyRole("heat", True)}),
        "names no owned state field",
    ),
    "a plain tuple": (
        dict(ENERGY_ROLES={HEAT: ("heat", True)}),
        "is an EnergyRole of heat, work, stored with a bool monotone",
    ),
    "an unknown role": (
        dict(ENERGY_ROLES={HEAT: EnergyRole("free", True)}),
        "is an EnergyRole of heat, work, stored",
    ),
    "a non-bool monotone": (
        dict(ENERGY_ROLES={HEAT: EnergyRole("heat", 1)}),
        "with a bool monotone",
    ),
    "stored on a heat field": (
        dict(ENERGY_ROLES={HEAT: EnergyRole("stored", False)}),
        "is stored energy, a level",
    ),
    "stored on a suffixed field it does not list": (
        dict(
            STATE_AXES={
                **ScheduledMembraneInsertionV2.STATE_AXES,
                "insertion_held_work_pJ": ["cell_slot"],
            },
            WORK_FIELDS=("insertion_held_work_pJ",),
            ENERGY_ROLES={"insertion_held_work_pJ": EnergyRole("stored", False)},
        ),
        "is stored energy, a level",
    ),
    "not a mapping": (dict(ENERGY_ROLES=((HEAT, EnergyRole("heat", True)),)), "maps owned state"),
}


@pytest.mark.parametrize("case", sorted(REFUSED))
def test_energy_role_declarations_are_checked_at_registration(case):
    attributes, message = REFUSED[case]
    with pytest.raises(ValueError, match=message):
        check_declarations(planted(case.replace(" ", "_").replace("-", "_"), **attributes))


def test_the_free_energy_hook_declares_none_by_default():
    """Seam E's operator hook (§7.1): ((stoichiometry, dG°/RT, c0), ...), none by default. The
    species registry's check reads it beside species_potentials."""
    for law, op in OPERATORS.items():
        assert op.standard_free_energies(None) == (), law
