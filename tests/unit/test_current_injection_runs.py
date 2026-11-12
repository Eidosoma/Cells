"""Compiled runs of electrode_current_injection@1 (docs/PUMP_COMPOSITE_V2_DESIGN.md §4).

An @3 heredity cell with one electrode, through the runner and its host checks: both
polarities booked at f I h / (z F) with the ledgers closing, idle injection bitwise equal to
the composition without it, and the refusal when a cell cannot supply a removed carrier.
About 70 s (four compiles); the tier-1 smoke test is test_current_injection.py.
"""

import copy

import jax
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from validation.tissue import pump_water_fixtures as fx

jax.config.update("jax_enable_x64", True)

LAW = "electrode_current_injection@1"
DT = 1e-3


def definition(currents, carriers=None, *, end=0.004):
    base = fx.heredity_cell("H", dt=DT, end_time=end)
    base["experiment"]["observation_times"] = [0.0, end]
    raw = cs.frozen_definition(base)
    cell = raw["model"]["cells"][0]["id"]
    carriers = carriers or {"K": 0.4912, "M": 0.5088}  # M: this world's anion.
    raw["model"]["operators"] = [dict(law=LAW, electrodes=[dict(cell_id=cell, carriers=carriers)])]
    schedule = [dict(time=k * DT, current_A=i) for k, i in currents]
    raw["experiment"]["injection_controls"] = [dict(cell_id=cell, schedule=schedule)]
    return raw


def test_both_polarities_are_booked_and_the_ledgers_close():
    current, half = 1e-12, 2 * DT  # +1 pA for 2 ms, then -1 pA for 2 ms.
    spec = parse_spec(definition([(0, current), (2, -current)]))
    result = run(spec)  # The run's host checks raise on any ledger or domain failure.
    species = list(spec.model.species_ids)
    supplied = np.asarray(result.history.injection_supplied_fmol)[-1][:, 0]
    removed = np.asarray(result.history.injection_removed_fmol)[-1][:, 0]
    for name, fraction in (("K", 0.4912), ("M", 0.5088)):
        expected = fraction * current * half / CHARGE_PER_FMOL  # fmol, each direction.
        i = species.index(name)
        assert supplied[i] == pytest.approx(expected, rel=1e-12)
        assert removed[i] == pytest.approx(expected, rel=1e-12)
    assert np.asarray(result.history.injection_charge_C)[-1][0] == pytest.approx(0.0, abs=1e-30)
    middle = np.asarray(result.history.injection_charge_C)[2][0]
    assert middle == pytest.approx(current * half, rel=1e-12)  # K in and M out add up to I h.


def test_idle_injection_equals_the_composition_without_it():
    raw = definition([(0, 0.0)])
    plain = copy.deepcopy(raw)
    plain["model"]["operators"] = []
    del plain["experiment"]["injection_controls"]
    with_electrode, without = run(parse_spec(raw)), run(parse_spec(plain))
    for name in type(without.history)._fields:
        assert np.array_equal(
            np.asarray(getattr(with_electrode.history, name)),
            np.asarray(getattr(without.history, name)),
        ), name


def test_a_cell_that_cannot_supply_a_removed_carrier_refuses():
    spec = parse_spec(definition([(0, -1e-3)], carriers={"K": 1.0}, end=DT))  # 1 mA out of K.
    with pytest.raises(Exception, match="(?i)refus|domain|invalid"):
        run(spec)
