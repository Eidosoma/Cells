"""Compiled guards of the S2 operators (docs/PUMP_COMPOSITE_V2_DESIGN.md §3).

Through the runner and its host checks:
* idle membrane state equals the composition without it, bitwise (one heredity cell, the
  seven-cell gated sheet);
* insertion at rate 0 equals the idle membrane state, bitwise;
* onset and insertion on the cleft cell: the furrow, its cleft and access stay closed until
  the onset, the area grows at the declared rate after it, the insertion heat is booked
  nonnegative and nondecreasing, and every ledger closes; RK4 keeps its exact half-steps;
* restart across the onset and the insertion is bitwise, through a written snapshot too, and
  the run manifest carries the field owners;
* the vmapped batch (vector windows, device checks) reproduces each world's own run to
  1e-12 of each field's scale (it compiles differently, so not bitwise);
* a catalogue reference changes neither the step's jaxpr nor the trajectory.
About 3 minutes on one core (each run compiles); the tier-1 smoke tests are
test_membrane_state.py and test_membrane_insertion.py.
"""

import json

import jax
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models.registry import get_model
from tests import membrane_insertion_fixtures as fx
from validation.tissue import composite_guard as guard
from validation.tissue import pump_water_fixtures as wfx

ONSET = 0.002
END = 0.006
TIMES = [0.0, 0.001, ONSET, 0.003, END]


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def cleft(rate=1e-11, **kw):
    base = fx.cleft_cell(end=END, observation_times=TIMES, **kw)
    return fx.with_operators(base, fx.furrow_insertion(rate=rate, onset=ONSET))


@pytest.fixture(scope="module")
def cleft_run():
    spec = parse_spec(cleft())
    return spec, run(spec)


def plain(base):
    return cs.frozen_definition(base)


@pytest.mark.parametrize(
    "world",
    [
        lambda: fx.one_patch(end=0.01, observation_times=[0.0, 0.005, 0.01]),
        lambda: wfx.gated_sheet(dt=fx.DT, end_time=0.004),
    ],
)
def test_idle_membrane_state_equals_the_composition_without_it(world):
    base = world()
    without = run(parse_spec(plain(base)))
    with_state = run(parse_spec(fx.with_operators(base)))
    guard.assert_same(without, with_state, history_fields=type(without.history)._fields)
    for name in ("membrane_area_increment_m2", "membrane_capacitance_increment_F"):
        assert not np.any(np.asarray(getattr(with_state.history, name))), name


def test_zero_rate_insertion_equals_the_idle_membrane_state():
    base = fx.two_clamps(end=0.004)
    idle = run(parse_spec(fx.with_operators(base)))
    zero = run(parse_spec(fx.with_operators(base, {"membrane_0": ({}, None, [(0.0, 0.0)])})))
    guard.assert_same(idle, zero, history_fields=type(idle.history)._fields)
    for name in ("inserted_area_m2", "insertion_dissipated_energy_pJ", "insertion_image_charge_C"):
        assert not np.any(np.asarray(getattr(zero.history, name))), name


def test_onset_and_insertion_close_their_checks(cleft_run):
    spec, result = cleft_run  # The runner's host checks raise on any ledger or domain failure.
    h, times = result.history, np.asarray(result.times)
    before = times <= ONSET + 1e-12  # Rows up to the step that leaves the onset.
    opened = np.asarray(h.insertion_opened)[:, 1]
    assert not np.any(opened[before]) and np.all(opened[~before] == 1)
    cleft_amounts = np.asarray(h.extracellular_amount_increment)[:, :, 1]
    assert not np.any(cleft_amounts[before]) and np.any(cleft_amounts[-1])
    area = np.asarray(h.membrane_area_increment_m2)[:, 1]
    np.testing.assert_allclose(area, 1e-11 * np.maximum(times - ONSET, 0.0), rtol=1e-12, atol=0)
    heat = np.asarray(h.insertion_dissipated_energy_pJ)[:, 1]
    assert np.all(heat >= 0) and np.all(np.diff(heat) >= 0) and heat[-1] > 0
    observed = np.asarray(result.observations.membrane_voltage_V)[:, 1]
    assert not np.any(observed[: TIMES.index(ONSET) + 1]) and observed[-1] != 0
    for key in ("max_energy_balance_error_pJ", "max_electrode_charge_error_C"):
        assert np.isfinite(result.diagnostics[key]), key


def test_rk4_keeps_the_exact_half_steps():
    base = fx.two_clamps(end=5e-5)
    base["execution"].update(solver="rk4", dt=2.5e-6, max_steps=40)
    base["experiment"]["observation_times"] = [0.0, 2.5e-5, 5e-5]
    raw = fx.with_operators(base, {"membrane_0": ({}, None, [(0.0, 1e-8)])})
    result = run(parse_spec(raw))  # Host checks with the RK4 energy bound (no solver rtol).
    image = np.asarray(result.history.insertion_image_charge_C)[-1]
    assert np.all(image > 0)
    assert np.asarray(result.history.membrane_area_increment_m2)[-1][0] == pytest.approx(5e-13)


def test_restart_across_onset_and_insertion_is_bitwise(cleft_run, tmp_path):
    spec, value = cleft_run
    for time in (0.001, ONSET, 0.003):  # Before, at and after the onset.
        checkpoint = value.checkpoint_at(time)
        resumed = run(spec, checkpoint)
        for a, b in zip(resumed.history, value.history, strict=True):
            assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :]), time
    checkpoint = value.checkpoint_at(0.003)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, value.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    summary = write_run(tmp_path / "run", value)
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    owners = manifest["field_owners"]
    assert owners["state"]["membrane_capacitance_increment_F"] == {
        "owner": fx.STATE,
        "writers": [fx.INSERTION],
    }
    assert owners["views"]["membrane_active"] == {"provider": fx.INSERTION, "readers": []}
    assert owners["views"]["membrane_capacitance"]["readers"] == [fx.INSERTION]
    assert summary["insertion_patches"]["furrow"]["onset_time"] == ONSET


def test_the_vmapped_batch_reproduces_each_world(cleft_run):
    rates = (0.5e-11, 1e-11, 2e-11)
    specs = [parse_spec(cleft(rate)) for rate in rates]
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
    batch = run_vector_windowed(
        BatchSpec(worlds, len(worlds), 10**6, 2**31), WindowPolicy(4, "checkpoints")
    )
    for world, spec in zip(batch.worlds, specs, strict=True):
        single = cleft_run[1] if spec == cleft_run[0] else run(spec)
        final = batch.worlds[world].final.state
        # The vmapped program (with device checks) compiles differently from a single run, so
        # it agrees to rounding, not bitwise (S1's vmap guards compare batch with batch). The
        # floor covers fields that are rounding noise here (one clamp: no image charge).
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(single.history, name))[-1]
            scale = np.max(np.abs(b), initial=0.0)
            assert np.max(np.abs(a - b), initial=0.0) <= 1e-12 * scale + 1e-30, (world, name)
        # The batch's device checks passed (a failure raises); their diagnostics are reported.
        assert np.isfinite(batch.worlds[world].diagnostics["max_energy_balance_error_pJ"])


def test_a_catalogue_reference_changes_neither_jaxprs_nor_trajectories():
    catalogue = {
        "kir_0": {"catalogue": "test_catalogue", "entry": "kir2.1"},
        "nav_0": {"catalogue": "test_catalogue", "entry": "nav1.2"},
    }
    base = fx.cleft_cell(end=0.003, observation_times=[0.0, 0.003])
    insertion = fx.furrow_insertion(onset=0.001)
    specs = [
        parse_spec(fx.with_operators(base, insertion)),
        parse_spec(fx.with_operators(base, insertion, catalogue=catalogue)),
    ]
    model = get_model(specs[0].model)
    assert get_model(specs[1].model) is model
    jaxprs = []
    for spec in specs:
        state, p = model.initial_values(spec)
        control = model.CONTROL_TYPE(*(np.asarray(v[0]) for v in cs.control_values(spec, [0.0])))
        jaxprs.append(
            str(
                jax.make_jaxpr(lambda s, d, c, q: model.checked_step(s, d, c, q, q.active))(
                    state, fx.DT, control, p
                )
            )  # fmt: skip
        )
    assert jaxprs[0] == jaxprs[1]
    results = [run(spec) for spec in specs]
    guard.assert_same(results[0], results[1])
    summaries = [
        model.summarize(r.history, r.diagnostics, s) for r, s in zip(results, specs, strict=True)
    ]
    assert summaries[0]["membrane_populations"]["kir_0"]["catalogue"] is None
    assert summaries[1]["membrane_populations"]["kir_0"]["catalogue"] == catalogue["kir_0"]
