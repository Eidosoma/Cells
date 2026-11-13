"""Compiled guards of restricted_cleft_lumen@1 (docs/CELL_DIVISION_S3_PLAN.md §1).

Through the runner and its host checks, on the S2 cleft cell (tests/membrane_insertion_fixtures):
* growth: the lumen's volume follows w dA / 2, half a step behind the area at each step's end
  (the fill waits for the next step's first half), filled at the bath's composition; every
  ledger closes on every row; the fill heat is nonnegative and nondecreasing; the observer
  reads each saved lumen filled to the area at its time, bitwise a NumPy fill of the row;
* RK4 keeps the exact half-steps around its inner step, and its energy ledger, whose bound has
  no solver tolerance, closes with the fill's terms;
* the composition without growth equals S2's, bitwise (membrane state and insertion, and with
  injection's pulses across the onset);
* restart across the onset and the growth is bitwise, through a written snapshot too, and the
  run manifest carries the lumen's field owners;
* the vmapped batch (vector windows, device checks) is bitwise against the same worlds in
  reversed order and reproduces each world's own run to 1e-12 of each field's scale.
About 4 minutes on one core (each run compiles); the tier-1 smoke test is
test_restricted_lumen.py.
"""

import json

import jax
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models.operators import restricted_lumen as lumen
from cells.models.registry import get_model
from tests import membrane_insertion_fixtures as fx
from validation.tissue import composite_guard as guard

ONSET = 0.002
END = 0.006
TIMES = [0.0, 0.001, ONSET, 0.003, 0.004, END]
WIDTH = 2e-6  # m: the cleft cell's 0.01 pL is w A_on / 2 over its 1e-11 m^2 furrow.
RATE = 1e-10  # m^2/s: 1e-13 m^2 (1%) per step, so the lumen gains 1% of its volume per step.
CLEFT, FURROW = 1, 1


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def block():
    return dict(
        law=lumen.LAW_ID, lumens=[dict(node_id="cleft", source_id="bath_0", gap_width_m=WIDTH)]
    )


def s2(rate=RATE, *, base=None):
    """The S2 composition: membrane state and the furrow's insertion."""
    base = fx.cleft_cell(end=END, observation_times=TIMES) if base is None else base
    return fx.with_operators(base, fx.furrow_insertion(rate=rate, onset=ONSET))


def s3(rate=RATE, *, base=None):
    """S2's composition with the lumen after the insertion."""
    raw = s2(rate, base=base)
    raw["model"]["operators"].append(block())
    return raw


def with_pulses(raw, *, after):
    """Injection's alternating pulses into the cell across the onset, after operator `after`."""
    cell = raw["model"]["cells"][0]["id"]
    raw["model"]["operators"].insert(
        after + 1,
        dict(
            law="electrode_current_injection@1",
            electrodes=[dict(cell_id=cell, carriers={"K": 0.4912, "M": 0.5088})],
        ),
    )
    raw["experiment"]["injection_controls"] = [
        dict(
            cell_id=cell,
            schedule=[
                dict(time=0.0, current_A=2e-12),
                dict(time=0.001, current_A=0.0),
                dict(time=0.003, current_A=-2e-12),
                dict(time=0.005, current_A=0.0),
            ],
        )
    ]
    return raw


@pytest.fixture(scope="module")
def growth_run():
    spec = parse_spec(s3())
    return spec, run(spec)


def test_growth_fills_the_lumen_and_closes_every_check(growth_run):
    spec, result = growth_run  # The runner's host checks raise on any ledger or domain failure.
    h, times = result.history, np.asarray(result.times)
    area = np.asarray(h.membrane_area_increment_m2)[:, FURROW]
    volume = np.asarray(h.lumen_volume_increment_pL)[:, CLEFT]
    lag = RATE * fx.DT / 2  # The area the second half-step inserted after the fill.
    expected = np.where(area > 0, 0.5e15 * WIDTH * (area - lag), 0.0)
    np.testing.assert_allclose(volume, expected, rtol=1e-12, atol=1e-25)
    assert not np.any(volume[times <= ONSET + 1e-12]) and volume[-1] > 0
    bath = np.asarray(spec.model.extracellular[0].initial_amount_fmol)  # 1 pL: mM.
    supplied = np.asarray(h.lumen_supplied_fmol)[:, :, CLEFT]
    np.testing.assert_allclose(supplied, volume[:, None] * bath[None, :], rtol=1e-12, atol=1e-25)
    # One fill per step, in its first half: replaying c_b dV from the saved volumes, one rounded
    # addition per row, gives the supplied amounts bitwise (a spurious second-half fill would
    # not), so the second half-step of every growing step was idle.
    replay = np.zeros_like(supplied)
    for j in range(1, len(volume)):
        grown = volume[j] > volume[j - 1]
        replay[j] = replay[j - 1] + bath * (volume[j] - volume[j - 1]) if grown else replay[j - 1]
    assert replay.tobytes() == supplied.tobytes()
    heat = np.asarray(h.lumen_fill_dissipated_energy_pJ)[:, CLEFT]
    assert np.all(heat >= 0) and np.all(np.diff(heat) >= 0)
    # Q5's observer reads each saved lumen filled to the area at its time: bitwise what a NumPy
    # fill of the saved row gives, and V_on + w dA / 2 with no lag.
    model = get_model(spec.model)
    p = model.initial_values(spec)[1]
    observed = result.observations
    v_on = spec.model.extracellular[1].volume_pL
    column = np.asarray(observed.lumen_volume_pL)[:, CLEFT]
    assert not np.any(column[: TIMES.index(ONSET) + 1])
    checked = 0
    for j, t in enumerate(np.asarray(observed.times)):
        if t <= ONSET + 1e-12:
            continue
        i = int(np.flatnonzero(times == t)[0])
        new, ok = lumen.filled(type(h)(*(np.asarray(v)[i] for v in h)), p, xp=np)
        assert ok
        view = model.view(p, new, xp=np)
        filled_volume = view.extracellular_volume[CLEFT]
        amounts = (
            view.extracellular_amount_reference[:, CLEFT]
            + new.extracellular_amount_increment[:, CLEFT]
        )
        assert column[j].tobytes() == filled_volume.tobytes(), t
        concentration = np.asarray(observed.lumen_concentration_mM)[j, :, CLEFT]
        assert concentration.tobytes() == (amounts / filled_volume).tobytes(), t
        assert filled_volume == pytest.approx(v_on + 0.5e15 * WIDTH * area[i], rel=1e-12)
        checked += 1
    assert checked == len([t for t in TIMES if t > ONSET])
    for key in ("max_energy_balance_error_pJ", "max_lumen_fill_balance_error_fmol"):
        assert np.isfinite(result.diagnostics[key]), key


def test_rk4_keeps_the_exact_half_steps_and_closes_its_energy():
    base = fx.cleft_cell(end=5e-5, observation_times=[0.0, 2.5e-5, 5e-5])
    base["execution"].update(solver="rk4", dt=2.5e-6, max_steps=40)
    raw = fx.with_operators(base, fx.furrow_insertion(rate=1e-8, onset=2.5e-5))
    raw["model"]["operators"].append(block())
    result = run(parse_spec(raw))  # Host checks with the RK4 energy bound (no solver rtol).
    volume = np.asarray(result.history.lumen_volume_increment_pL)[-1, CLEFT]
    area = np.asarray(result.history.membrane_area_increment_m2)[-1, FURROW]
    assert area == pytest.approx(2.5e-13) and volume > 0
    assert volume == pytest.approx(0.5e15 * WIDTH * (area - 1e-8 * 1.25e-6), rel=1e-12)
    assert result.diagnostics["max_energy_balance_error_pJ"] < 1e-12


@pytest.mark.parametrize("pulses", [False, True])
def test_the_composition_without_growth_equals_s2s(pulses):
    """With no growth the lumen is idle: the S2 composition's state, observations and
    diagnostics are unchanged bitwise, with and without injection's pulses across the onset."""
    without, with_lumen = s2(0.0), s3(0.0)
    if pulses:  # Injection after the insertion, and after the lumen.
        without, with_lumen = with_pulses(without, after=1), with_pulses(with_lumen, after=2)
    reference = run(parse_spec(without))
    result = run(parse_spec(with_lumen))
    guard.assert_same(reference, result, history_fields=type(reference.history)._fields)
    for name in lumen.STATE_AXES:
        assert not np.any(np.asarray(getattr(result.history, name))), name


def test_restart_across_the_onset_and_the_growth_is_bitwise(growth_run, tmp_path):
    spec, value = growth_run
    for time in (0.001, ONSET, 0.004):  # Before, at and after the onset.
        checkpoint = value.checkpoint_at(time)
        resumed = run(spec, checkpoint)
        for a, b in zip(resumed.history, value.history, strict=True):
            assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :]), time
    checkpoint = value.checkpoint_at(0.004)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, value.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    summary = write_run(tmp_path / "run", value)
    owners = json.loads((tmp_path / "run" / "manifest.json").read_text())["field_owners"]
    assert owners["views"]["extracellular_volume"] == {"provider": lumen.LAW_ID, "readers": []}
    assert lumen.LAW_ID in owners["views"]["membrane_area"]["readers"]
    assert owners["state"]["lumen_supplied_fmol"] == {"owner": lumen.LAW_ID, "writers": []}
    assert lumen.LAW_ID in owners["state"]["reservoir_supplied"]["writers"]
    assert summary["lumens"]["cleft"] == dict(source_id="bath_0", gap_width_m=WIDTH)


def vector_batch(specs):
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
    return run_vector_windowed(
        BatchSpec(worlds, len(worlds), 10**6, 2**31), WindowPolicy(4, "checkpoints")
    )


def test_the_vmapped_batch_reproduces_each_world(growth_run):
    rates = (0.5 * RATE, RATE, 2 * RATE)
    specs = [parse_spec(s3(rate)) for rate in rates]
    batch = vector_batch(specs)
    reversed_batch = vector_batch(specs[::-1])  # One compiled program: bitwise, per world.
    for k in range(len(specs)):
        x = batch.worlds[k + 1].final.state
        y = reversed_batch.worlds[len(specs) - k].final.state
        for name in type(x)._fields:
            assert guard.compare_arrays(name, getattr(x, name), getattr(y, name)) is None, name
    for world, spec in zip(batch.worlds, specs, strict=True):
        single = growth_run[1] if spec == growth_run[0] else run(spec)
        final = batch.worlds[world].final.state
        # The vmapped program (with device checks) compiles differently from a single run: it
        # agrees to rounding, not bitwise (as S2's vmap guard). The floor covers rounding noise
        # (one clamp: the fill's image charge is of order 1e-30 C).
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(single.history, name))[-1]
            scale = np.max(np.abs(b), initial=0.0)
            assert np.max(np.abs(a - b), initial=0.0) <= 1e-12 * scale + 1e-30, (world, name)
        assert np.isfinite(batch.worlds[world].diagnostics["max_lumen_fill_balance_error_fmol"])


def test_the_studys_windowed_observations_reproduce_the_run(growth_run):
    """The S3 study's observation path (cleft_egg_engine.windowed_observations: vector windows
    with device checks, one world) on the cleft world: the observer's columns at every requested
    time agree with the runner's to rounding (the vmapped program compiles differently)."""
    from validation.division import cleft_egg_engine as engine

    spec, result = growth_run
    stacked, diagnostics, _ = engine.windowed_observations(spec, window_steps=2)
    assert stacked["times"].tolist() == np.asarray(result.observations.times).tolist()
    for name in ("membrane_voltage_V", "lumen_concentration_mM"):
        a, b = stacked[name], np.asarray(getattr(result.observations, name))
        assert a.shape == b.shape, name
        assert np.max(np.abs(a - b)) <= 1e-12 * np.max(np.abs(b)) + 1e-30, name
    assert np.isfinite(diagnostics["max_lumen_fill_balance_error_fmol"])
