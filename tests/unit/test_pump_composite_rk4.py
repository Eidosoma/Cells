"""The composite's RK4 composition rule (pump_composite.Composition.check_definition).

Under RK4 a composition with a coupled operator, a split part declared "coupled" (water@1) or an
in-step membrane process (the K-anion symport), integrates the coupled right-hand side unsplit, as
the frozen water models did. Such a composition holds no event maps, no split-only parts and no
integer state (docs/PUMP_COMPOSITE.md, "The step"). Without a coupled operator, events and exact
half-steps stay around @3's own RK4 step, as replacement@1's do.

The rule had no test of its own; the composition matrix (validation/tissue/composition_matrix.py)
cites this file. Each of the three conditions is refused beside each kind of coupled operator,
from the declarations (no definition needed: the rule raises before reading one). On the
replacement fixtures' heredity sheet, [water, replacement@2] with an event is refused under RK4
and admitted under the sheet's IMEX solver, while [water], [water, symport] and replacement@1
with its event are admitted under RK4.
"""

import copy
import re
from types import SimpleNamespace

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.cell_replacement_spec import exact_event_times
from cells.definitions.specs import ConfigError, parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as pump3
from cells.operators.contract import Operator
from tests import replacement_water_fixtures as fx
from validation.tissue import pump_water_fixtures as wfx

RULE = re.escape(
    "An RK4 composition with a coupled operator cannot hold event maps, split-only parts or "
    "integer state"
)
RK4_SPEC = SimpleNamespace(execution=SimpleNamespace(solver="rk4"))
T1 = exact_event_times((10,), fx.DT)[0]


class Coupled(Operator):
    LAW_ID = "cells.operator.dummy_coupled@1"
    SPLIT = True
    RK4 = "coupled"


class Process(Operator):
    LAW_ID = "cells.operator.dummy_process@1"
    PROCESS = True


class Event(Operator):
    LAW_ID = "cells.operator.dummy_event@1"
    EVENT = True


class Split(Operator):
    LAW_ID = "cells.operator.dummy_split@1"
    SPLIT = True
    RK4 = "split"


class Counter(Operator):
    LAW_ID = "cells.operator.dummy_counter@1"
    STATE_AXES = {"dummy_count": ("cell_slot",)}
    STATE_DTYPES = {"dummy_count": np.int64}


@pytest.mark.parametrize("coupled", (Coupled, Process), ids=("coupled_split", "in_step_process"))
@pytest.mark.parametrize("held", (Event, Split, Counter), ids=("event", "split_part", "integer"))
def test_each_condition_is_refused_beside_each_kind_of_coupled_operator(coupled, held):
    for operators in ((coupled(), held()), (held(), coupled())):
        composition = pump_composite.Composition(pump3, operators)
        assert composition.coupled
        with pytest.raises(ConfigError, match=RULE):
            composition.check_definition(RK4_SPEC)


def rk4(raw):
    out = copy.deepcopy(raw)
    out["execution"]["solver"] = "rk4"
    return out


@pytest.fixture(scope="module")
def sheet():
    raw = fx.sheet(end=0.02)
    slot, donor = fx.ring_neighbours(raw)
    templates = fx.templates(raw)
    events = ((T1, slot, None, "c1", donor),)
    return SimpleNamespace(raw=raw, templates=templates, events=events)


def test_replacement_over_water_is_refused_under_rk4_only(sheet):
    over_water = fx.over_water(sheet.raw, sheet.templates, sheet.events)
    assert [d.law for d in parse_spec(over_water).model.operators] == [fx.WATER, fx.LAW]
    with pytest.raises(ConfigError, match=RULE):
        parse_spec(rk4(over_water))


def test_coupled_compositions_without_the_three_and_split_events_are_admitted_under_rk4(sheet):
    water = cs.frozen_definition(wfx.with_water(sheet.raw))
    symport = cs.frozen_definition(wfx.with_symport(wfx.with_water(sheet.raw)))
    replacement = cs.frozen_definition(fx.replacement_v1(sheet.raw, sheet.templates, sheet.events))
    for raw, laws in (
        (water, [fx.WATER]),
        (symport, [fx.WATER, "cells.operator.k_anion_symport_mass_action@1"]),
        (replacement, [fx.V1]),
    ):
        spec = parse_spec(rk4(raw))
        assert spec.execution.solver == "rk4"
        assert [d.law for d in spec.model.operators] == laws
