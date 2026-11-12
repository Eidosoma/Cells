"""Guards (b)-(d) of design §3.7 for the scheduled replacement operator (D143).

(c) Re-expressed through the composite, resolved_pump_replacement@1 equals the
frozen model bitwise on its own test worlds: every state field, observation
column and max_ diagnostic (np.array_equal), compiled. Worlds: the heredity sheet
with one, simultaneous, both-ends, second-generation and D-template events (IMEX
ARS(2,2,2) and Euler), donor copies with a route-only template, law_steady
arrival gates with an inner schedule change between events, a newcomer's own
route values, @3's padded reference world and RK4. Refusals (a schedule
disagreement, a floating-component slot, invalid events) give the frozen
verdicts; device checks give the frozen bits on injected faults.
(b) Without events the operator equals the empty composition.
(d) Restart before, at and after an event is bitwise; a vmap batch with two
schedules reproduces the frozen model's batch bitwise.

These tests passed against the frozen implementation (commit 82fe086, run from
snapshot-8416a72 before the rebase; evidence in
/mnt/workspaces/Cells/composite-s1-20261111-01/tests/). Since the replacement
module became a thin composition, "frozen" is the frozen definition format run
through its own model module, and the tests guard that it and its composite rewrite
run identically; the comparison with the earlier implementation is the
cross-revision guard (validation/tissue/composite_crossrev.py and composite_dump.py).
"""

import copy

import jax
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.cell_replacement_spec import exact_event_times
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy
from cells.models import cell_replacement
from cells.models.registry import get_model
from cells.numerics import surface_imex as imex
from validation.tissue import cell_replacement_fixtures as fx
from validation.tissue import composite_guard as guard
from validation.tissue import surface_pump_v3_fixtures as v3fx

DT = 1e-3
STEPS = 50
END = STEPS * DT
T1, T2, T3 = exact_event_times((10, 20, 30), DT)
OBSERVED = exact_event_times((0, 10, 11, 30, 31, STEPS), DT)
EVENTS = (
    (T1, "cell_0", "h", "n1"),
    (T2, "cell_2", "h", "n2"),
    (T2, "cell_5", "h", "n3"),
    (T3, "cell_0", "d", "n4"),
    (T3, "cell_3", "h", "n5"),
)
FAST_NAV = dict(fx.NO_ROUTES, channel_permeability_m_per_s={"nav1p2_m3h_regularized@1": 3e-7})
DONOR_EVENTS = (
    (T1, "cell_0", None, "c1", "cell_3"),
    (T2, "cell_4", "fast_nav", "c2", "cell_3"),
    (T2, "cell_3", "h", "c3"),
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def sheet(solver=imex.ARS222_ID, end=END):
    raw = fx.heredity_sheet(1, 0, dt=DT, end_time=end, solver=solver)
    raw["experiment"]["observation_times"] = [t for t in OBSERVED if t <= end]
    return raw


def templates(raw):
    return [fx.template_from_cell(raw, "cell_1", "h"), fx.template_from_cell(raw, "cell_3", "d")]


def replaced(solver=imex.ARS222_ID, events=EVENTS, **kw):
    raw = sheet(solver)
    return fx.with_replacement(raw, templates(raw), events, **kw)


def donors():
    raw = sheet()
    return fx.with_replacement(
        raw, [*templates(raw), fx.route_template("fast_nav", FAST_NAV)], DONOR_EVENTS
    )


def steady_between():
    raw = sheet()
    for control in raw["experiment"]["channel_controls"]:
        if control["channel_id"].startswith("nav_"):
            held = control["schedule"][0]["availability"]
            control["schedule"] = [
                dict(time=0.0, availability=held),
                dict(time=T2, availability=0.5),
            ]
    steady = dict(fx.FORMATION, initial_abundance=1.0, lag_s=0.0, gate_at_arrival="law_steady")
    events = ((T1, "cell_0", "h", "n1"), (T3, "cell_3", "h", "n2"))
    return fx.with_replacement(raw, templates(raw), events, formation=steady)


def drawn():
    raw = sheet()
    t = fx.template_from_cell(raw, "cell_1", "drawn")
    t["route_values"].update(
        channel_permeability_m_per_s={"nav1p2_m3h_regularized@1": 3.0e-7},
        membrane_permeability_m_per_s={"Na": 8e-11},
        pump_capacity_fmol_per_s_m2=1.2e8,
    )
    return fx.with_replacement(raw, [t], [(T1, "cell_0", "drawn", "n1")])


def padded():
    raw = v3fx.definition("release", solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0007, 0.0012]
    t1, t2 = exact_event_times((4, 9), raw["execution"]["dt"])
    own = [
        fx.template_from_cell(raw, "cell_0", "own_0"),
        fx.template_from_cell(raw, "cell_1", "own_1"),
    ]
    events = ((t1, "cell_0", "own_0", "n1"), (t2, "cell_0", "own_0", "n2"))
    return fx.with_replacement(raw, own, events)


def rk4():
    raw = fx.heredity_sheet(1, 0, dt=2.5e-6, end_time=40 * 2.5e-6, solver="rk4")
    raw["experiment"]["observation_times"] = [0.0, 20 * 2.5e-6, 40 * 2.5e-6]
    t1, t2 = exact_event_times((4, 9), 2.5e-6)
    events = ((t1, "cell_1", "h", "n1"), (t2, "cell_0", "d", "n2"), (t2, "cell_3", "h", "n3"))
    return fx.with_replacement(raw, templates(raw), events)


WORLDS = {
    "events_ars": lambda: replaced(),
    "events_euler": lambda: replaced(imex.EULER_ID),
    "trapezoid": lambda: _booking(replaced()),
    "donors": donors,
    "law_steady": steady_between,
    "route_values": drawn,
    "padded": padded,
    "rk4": rk4,
}


def _booking(raw):
    raw["model"]["junction_heat_booking"] = "trapezoid_nonnegative@1"
    return raw


@pytest.mark.parametrize("world", WORLDS)
def test_re_expressed_replacement_is_the_frozen_model(world):
    raw = WORLDS[world]()
    frozen, composite = parse_spec(raw), parse_spec(cs.frozen_definition(raw))
    assert get_model(frozen.model) is cell_replacement
    a, b = run(frozen), run(composite)
    report = guard.assert_same(a, b)
    assert report["compared"]["history"] == len(cell_replacement.STATE_TYPE._fields)
    summary = get_model(composite.model).summarize(b.history, b.diagnostics, composite)
    assert (
        summary["lineage"]
        == cell_replacement.summarize(a.history, a.diagnostics, frozen)["lineage"]
    )


@pytest.mark.parametrize("solver", (imex.EULER_ID, imex.ARS222_ID, "rk4"))
def test_without_events_the_operator_is_idle(solver):
    if solver == "rk4":
        raw = fx.heredity_sheet(1, 0, dt=2.5e-6, end_time=40 * 2.5e-6, solver="rk4")
        raw["experiment"]["observation_times"] = [0.0, 40 * 2.5e-6]
    else:
        raw = sheet(solver)
    empty = run(parse_spec(cs.frozen_definition(raw)))
    idle = run(parse_spec(cs.frozen_definition(fx.with_replacement(raw))))
    guard.assert_same(empty, idle, history_fields=type(empty.history)._fields)
    for name in cell_replacement.REPLACEMENT_STATE_AXES:
        assert not np.any(np.asarray(getattr(idle.history, name))), name


def test_refusals_are_the_frozen_verdicts():
    raw = replaced(events=((T1, "cell_0", "h", "n1"),))
    for spec in (parse_spec(raw), parse_spec(cs.frozen_definition(raw))):
        model = get_model(spec.model)
        state, p = model.initial_values(spec)
        controls = control_values(spec, [T1])
        control = type(controls)(*(np.asarray(v[0]) for v in controls))
        bad = control._replace(generation=np.where(np.arange(7) == 0, 2, 0))
        kept, valid = jax.jit(model.checked_step)(state, DT, bad, p, p.active)
        assert not valid
        for a, b in zip(kept, state, strict=True):
            assert np.array_equal(np.asarray(a), b)
    base = padded()
    floating = copy.deepcopy(base)
    floating["experiment"]["replacement_events"] = [
        fx.event(base["experiment"]["replacement_events"][0]["time"], "cell_1", "own_1", "n1")
    ]
    messages = []
    for candidate in (floating, cs.frozen_definition(floating)):
        with pytest.raises(ConfigError, match="held-bath") as error:
            parse_spec(candidate)
        messages.append(str(error.value))
    # Each definition format prefixes its own name; the refusal's reason is the same.
    assert messages[0].split(": ", 1)[1] == messages[1].split(": ", 1)[1]
    off_grid = replaced()
    off_grid["experiment"]["replacement_events"][0]["time"] = 0.0105
    for candidate in (off_grid, cs.frozen_definition(off_grid)):
        with pytest.raises(ConfigError, match="strictly inside"):
            parse_spec(candidate)


FAULTS = {
    "supply": ("replacement_supplied_fmol", lambda v: v * (1 + 1e-6)),
    "charge": ("replacement_charge_C", lambda v: v + 1e-18),
    "energy": ("replacement_free_energy_pJ", lambda v: v + 1.0),
    "generation": ("generation", lambda v: v + 5),
}


def test_faults_fail_the_frozen_checks():
    raw = replaced()
    frozen, composite = parse_spec(raw), parse_spec(cs.frozen_definition(raw))
    results = [run(frozen), run(composite)]
    k = int(np.flatnonzero(results[0].times == T3)[0]) + 1
    for name, (field, corrupt) in FAULTS.items():
        outcomes = []
        for spec, result in zip((frozen, composite), results, strict=True):
            model = get_model(spec.model)
            h, p = result.history, model.initial_values(spec)[1]
            rows = [type(h)(*(np.asarray(v[i]) for v in h)) for i in (k - 1, k)]
            value = np.array(getattr(rows[1], field), copy=True)
            value[..., 0] = corrupt(value[..., 0])
            bad = rows[1]._replace(**{field: value})
            try:
                model.check_values(bad, spec, [k])
                message = None
            except NumericalError as error:
                message = str(error)
            constants = model.device_check_constants(spec)
            failed, _ = model.device_checks(rows[0], bad, p, constants, k)
            outcomes.append((message, np.asarray(failed).tolist()))
        assert outcomes[0][0] is not None and outcomes[0] == outcomes[1], name


@pytest.mark.parametrize("time", (T1 - DT, T1, T1 + DT))
def test_restart_at_an_event_is_bitwise(time):
    spec = parse_spec(cs.frozen_definition(replaced()))
    result = run(spec)
    restarted = run(spec, result.checkpoint_at(time))
    k = int(np.flatnonzero(result.times == time)[0])
    for key in type(result.history)._fields:
        a = np.asarray(getattr(restarted.history, key))
        assert np.array_equal(a, np.asarray(getattr(result.history, key))[k:]), key


def test_vmap_batch_is_the_frozen_batch():
    t = exact_event_times((5, 9, 16), DT)

    def world(events):
        raw = fx.heredity_sheet(1, 0, dt=DT, end_time=24 * DT)
        raw["experiment"]["observation_times"] = [0.0, 12 * DT, 24 * DT]
        formation = dict(fx.FORMATION, lag_s=0.0, time_constant_s=40.0)
        return fx.with_replacement(raw, templates(raw), events, formation=formation)

    raws = [
        world(((t[0], "cell_0", "h", "a1"), (t[2], "cell_0", "d", "a2"))),
        world(((t[1], "cell_3", "h", "b1"), (t[1], "cell_4", "h", "b2"))),
    ]
    policy = WindowPolicy(8, "checkpoints")

    def cohort(specs):
        return BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 2, 10**6, 2**31)

    a = run_vector_windowed(cohort([parse_spec(r) for r in raws]), policy)
    b = run_vector_windowed(cohort([parse_spec(cs.frozen_definition(r)) for r in raws]), policy)
    for w in a.worlds:
        x, y = a.worlds[w].final.state, b.worlds[w].final.state
        for key in type(x)._fields:
            assert guard.compare_arrays(key, getattr(x, key), getattr(y, key)) is None, key
