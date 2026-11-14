"""Compiled guard of Q7's idle sheet (S5 design §8.3 Q7, the lead's ruling of 14 November).

The 19-cell heredity sheet (validation/tissue/cell_replacement_fixtures.heredity_sheet(2), every
cell on its own held bath) is padded to the 64-node cap of field-input providers: 32 cell slots
and 32 outside slots, 38 of them declared. It runs with idle division operators,
isopotential_partition@1 with no divisions and cytoplasmic_bridge_closure@1 with no bridges, and
without them, at the same padding. The two must be bitwise equal: every inner state field on
every accepted row, and every observation column they share.

The partition closes `active`, so the composite counts it as a field-input provider whether or
not it is live: the cap (pump_composite_adapter.check_field_inputs) is checked for the idle
composition, and 64 field nodes is admitted. One compiled run of each; about a minute.
"""

import math

import jax
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import pump_composite_adapter as adapter
from tests import membrane_insertion_fixtures as ifx
from tests import partition_fixtures as fx
from validation.tissue import cell_replacement_fixtures as rfx

DT = 1e-3
END = 0.05
SLOTS = 32  # Cell slots and outside slots alike: 64 field nodes, the cap.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def sheet(*, idle):
    raw = cs.frozen_definition(rfx.heredity_sheet(2, dt=DT, end_time=END))
    raw["experiment"]["observation_times"] = [0.0, END]
    raw["execution"].update(
        capacity=SLOTS,
        extracellular_capacity=SLOTS,
        max_steps=int(math.ceil(END / DT)) + 8,
    )
    operators = [ifx.membrane_state(raw)]
    if idle:
        operators += [dict(law=fx.PARTITION, divisions=[]), dict(law=fx.BRIDGE, bridges=[])]
        raw["experiment"]["partition_events"] = []
        raw["experiment"]["bridge_controls"] = []
    raw["model"]["operators"] = operators
    return raw


def test_the_sheet_sits_at_the_cap():
    raw = sheet(idle=True)
    m, x = raw["model"], raw["execution"]
    assert (len(m["cells"]), len(m["extracellular"])) == (19, 19)
    assert x["capacity"] + x["extracellular_capacity"] == adapter.FIELD_INPUT_NODE_CAP
    raw["execution"]["capacity"] = SLOTS + 1  # One node past the cap is refused.
    with pytest.raises(Exception, match="field nodes"):
        run(parse_spec(raw))


def test_idle_division_operators_leave_the_sheet_bitwise_unchanged():
    idle = run(parse_spec(sheet(idle=True)))
    plain = run(parse_spec(sheet(idle=False)))
    assert np.array_equal(np.asarray(idle.times), np.asarray(plain.times))
    compared = 0
    for name in type(plain.history)._fields:
        a, b = np.asarray(getattr(idle.history, name)), np.asarray(getattr(plain.history, name))
        assert a.dtype == b.dtype and np.array_equal(a, b), name
        compared += 1
    assert compared >= 20
    for name in type(plain.observations).__dataclass_fields__:
        a = np.asarray(getattr(idle.observations, name))
        b = np.asarray(getattr(plain.observations, name))
        assert np.array_equal(a, b), name
