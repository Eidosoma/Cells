"""Compiled guards of scheduled_cell_replacement@2 over water (v2 design §2.9 B).

Through the runner and its host checks on every row, and vector windows with device checks:
* idle: [water, @2] without events equals [water] bitwise (the heredity cell with Euler and
  ARS(2,2,2), the gated sheet with ARS(2,2,2));
* reduction to @1: [closed water, @2] with templates at the declared volume and donor copies
  equals [@1] on the shared fields, bitwise; @2's volume accumulators hold the declared volume
  per event, and its water free energy and magnitude are exactly 0;
* ledgers across events: sheets under open water whose cells shrink (no neutral impermeant)
  or swell (20 fmol of it), with templates at their own arrival volumes and donor copies;
  every host check passes on every row, and the newcomer's volume carries into the next row;
* a refused event (a template volume outside water's bounds in the layout; a donor copy with
  another impermeant content) returns the full start state;
* restart before, at and after an event is bitwise, also through a written snapshot, and the
  manifest's field owners name @2 as the writer of the cell volume;
* the vmapped batch (vector windows, device checks) is bitwise against the same worlds in
  reversed order and within 1e-12 of each field's scale against each world's own run (the
  vmapped program compiles differently, as in S2).
The tier-1 smoke test is test_cell_replacement_v2.py.
"""

import json

import jax
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.cell_replacement_spec import exact_event_times
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models.operators import cell_replacement_v2 as v2
from cells.models.registry import get_model
from cells.numerics import surface_imex as imex
from tests import replacement_water_fixtures as fx
from validation.tissue import composite_guard as guard
from validation.tissue import pump_water_fixtures as wfx

DT = fx.DT
STEPS = 30
END = STEPS * DT
T1, T2, T3 = exact_event_times((10, 15, 20), DT)
OBSERVED = exact_event_times((0, 10, 11, 20, 21, STEPS), DT)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def schedule(raw):
    """Template events on a ring cell (twice) and on the centre, and a copy of the centre (D)
    into another ring cell. The ring cells are symmetric, so a copy between two of them would
    book an exact zero; the centre differs."""
    slot, _ = fx.ring_neighbours(raw)
    donor = "cell_3"
    target = next(c["id"] for c in raw["model"]["cells"] if c["id"] not in (slot, donor))
    events = (
        (T1, target, "h", "n1"),
        (T2, slot, None, "c1", donor),
        (T3, target, "d", "n2"),
        (T3, donor, "h", "n3"),
    )
    return events, target, slot, donor


def sheet():
    return fx.sheet(end=END, observed=OBSERVED)


def volume(raw):
    return raw["model"]["cells"][0]["volume_pL"]


@pytest.mark.parametrize(
    "world, solver",
    (("cell", imex.ARS222_ID), ("cell", imex.EULER_ID), ("sheet", imex.ARS222_ID)),
)
def test_idle_replacement_equals_water_alone(world, solver):
    if world == "cell":
        raw = wfx.heredity_cell("H", dt=DT, end_time=END, solver=solver)
        raw["experiment"]["observation_times"] = [0.0, T1, END]
    else:
        raw = fx.sheet(end=END, observed=OBSERVED, solver=solver)
    alone = run(parse_spec(cs.frozen_definition(wfx.with_water(raw, pf_m_s=fx.PF_M_S))))
    idle = run(parse_spec(fx.over_water(raw)))
    guard.assert_same(alone, idle)
    for name in v2.STATE_AXES:
        assert not np.any(np.asarray(getattr(idle.history, name))), name


def test_closed_water_reduces_to_replacement_v1():
    raw = sheet()
    events, *_ = schedule(raw)
    templates = fx.templates(raw)  # At the declared volume.
    v1 = run(parse_spec(fx.replacement_v1(raw, templates, events)))
    closed = run(parse_spec(fx.over_water(raw, templates, events, availability=0.0)))
    report = guard.assert_same(v1, closed)
    assert report["compared"]["history"] == len(type(v1.history)._fields)
    final = type(closed.history)(*(np.asarray(v)[-1] for v in closed.history))
    count = final.generation.astype(float)
    v0 = volume(raw)
    assert np.array_equal(final.replacement_volume_removed_pL, count * v0)
    assert np.array_equal(final.replacement_volume_supplied_pL, count * v0)
    assert np.all(np.asarray(closed.history.replacement_water_free_energy_pJ) == 0.0)
    assert np.all(np.asarray(closed.history.replacement_water_energy_magnitude_pJ) == 0.0)
    assert not np.any(np.asarray(closed.history.volume_increment_pL))


def moved(impermeant_fmol):
    raw = sheet()
    events, target, slot, donor = schedule(raw)
    v0 = volume(raw)
    templates = fx.templates(raw, volumes={"h": 0.97 * v0, "d": 1.03 * v0})
    spec = parse_spec(fx.over_water(raw, templates, events, impermeant_fmol=impermeant_fmol))
    order = {c.id: i for i, c in enumerate(spec.model.cells)}
    return spec, order[target], order[slot], order[donor], v0


@pytest.mark.parametrize("impermeant_fmol", (0.0, 20.0))  # Cells shrink, or swell.
def test_events_on_shrunk_or_swollen_cells_close_every_ledger(impermeant_fmol):
    spec, target, slot, donor, v0 = moved(impermeant_fmol)
    result = run(spec)  # The host checks raise on any ledger, domain or dissipation failure.
    times, h = np.asarray(result.times), result.history
    dv = np.asarray(h.volume_increment_pL)
    k1, k2 = (int(np.flatnonzero(times == t)[0]) for t in (T1, T2))
    sign = 1.0 if impermeant_fmol > 0 else -1.0
    assert sign * dv[k1, target] > 0  # The occupant had moved off its declared volume.
    # The newcomer starts at its arrival volume; one step of water moves it by far less.
    assert abs(dv[k1 + 1, target] - (0.97 * v0 - v0)) < 1e-4 * v0
    # The copy starts at the donor's volume. In the step after the event both move by the same
    # water flow (equal amounts, volume, compliance and bath), up to that step's small ionic
    # difference; the D copy's own flow is about 3e-4 pL in the step.
    assert abs(dv[k2 + 1, slot] - dv[k2 + 1, donor]) < 1e-6 * v0
    final = type(h)(*(np.asarray(v)[-1] for v in h))
    assert final.replacement_volume_supplied_pL[target] == pytest.approx(2.0 * v0, rel=1e-9)
    assert np.all(final.replacement_water_free_energy_pJ[[target, slot]] != 0.0)
    summary = get_model(spec.model).summarize(h, result.diagnostics, spec)
    assert summary["replacement_law"] == v2.LAW_ID and summary["impermeant_species"] == ["P"]
    assert summary["composition_status"] == cs.DEVELOPMENT_STATUS


def test_a_refused_event_returns_the_full_start_state():
    spec, target, slot, donor, v0 = moved(0.0)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    step = jax.jit(model.checked_step)
    for time in (T1, T2):
        control = model.CONTROL_TYPE(*(np.asarray(v[0]) for v in cs.control_values(spec, [time])))
        good, valid = step(state, DT, control, p, p.active)
        assert valid
        bad = p._replace(template_volume_pL=np.full_like(p.template_volume_pL, 0.1 * v0))
        inc = np.array(state.amount_increment, copy=True)
        inc[list(spec.model.species_ids).index("P"), donor] += 1.0
        for start, layout in ((state, bad), (state._replace(amount_increment=inc), p)):
            if time == T1 and layout is p:
                continue  # No donor copy at T1.
            if time == T2 and layout is bad:
                continue  # No template at T2.
            kept, valid = step(start, DT, control, layout, layout.active)
            assert not valid
            for name, a, b in zip(type(start)._fields, kept, start, strict=True):
                assert np.asarray(a).tobytes() == np.asarray(b).tobytes(), (time, name)
        assert not np.array_equal(np.asarray(good.volume_increment_pL), state.volume_increment_pL)


def test_restart_across_an_event_is_bitwise(tmp_path):
    spec, target, *_ = moved(20.0)
    result = run(spec)
    for time in (T1 - DT, T1, T1 + DT):
        checkpoint = result.checkpoint_at(time)
        resumed = run(spec, checkpoint)
        for a, b in zip(resumed.history, result.history, strict=True):
            assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :]), time
    checkpoint = result.checkpoint_at(T2)
    write_snapshot(tmp_path / "checkpoint", result.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    write_run(tmp_path / "run", result)
    owners = json.loads((tmp_path / "run" / "manifest.json").read_text())["field_owners"]
    assert owners["state"]["volume_increment_pL"] == {"owner": fx.WATER, "writers": [fx.LAW]}
    assert owners["views"]["volume"] == {"provider": fx.WATER, "readers": [fx.LAW]}


def vector_batch(specs):
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
    return run_vector_windowed(
        BatchSpec(worlds, len(worlds), 10**6, 2**31), WindowPolicy(4, "checkpoints")
    )


def test_the_vmapped_batch_reproduces_each_world():
    raw = sheet()
    events, target, slot, donor = schedule(raw)
    v0 = volume(raw)
    templates = fx.templates(raw, volumes={"h": 0.97 * v0, "d": 1.03 * v0})
    raws = (
        fx.over_water(raw, templates, events[:1] + events[2:]),  # Templates only.
        fx.over_water(raw, templates, events[1:2]),  # One donor copy.
        fx.over_water(raw, templates, ()),  # No event.
    )
    specs = [parse_spec(r) for r in raws]
    batch = vector_batch(specs)
    reversed_batch = vector_batch(specs[::-1])
    for k in range(len(specs)):
        x = batch.worlds[k + 1].final.state
        y = reversed_batch.worlds[len(specs) - k].final.state
        for name in type(x)._fields:
            assert guard.compare_arrays(name, getattr(x, name), getattr(y, name)) is None, name
    for world, spec in zip(batch.worlds, specs, strict=True):
        single = run(spec)
        final = batch.worlds[world].final.state
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(single.history, name))[-1]
            scale = np.max(np.abs(b), initial=0.0)
            assert np.max(np.abs(a - b), initial=0.0) <= 1e-12 * scale + 1e-30, (world, name)
        assert np.isfinite(batch.worlds[world].diagnostics["max_energy_balance_error_pJ"])
