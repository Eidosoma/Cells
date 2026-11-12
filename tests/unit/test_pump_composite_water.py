"""Guards (b)-(d) of design §3.7 for the water and symport operators (D143).

(c) Re-expressed through the composite, resolved_pump_water@1 and
resolved_pump_water@2 equal the frozen models bitwise on their own test worlds:
every state field, observation column and max_ diagnostic (np.array_equal, as the
frozen equivalence tests compare), compiled with default XLA flags. Worlds: the
water-on heredity cell, the ion-closed osmometer, the gated sheet with the
trapezoid junction-heat booking, the coupled RK4 path, the KCC route cell and the
route-and-booking sheet. Refusals (a volume bound, a bad water control, an
over-fast water law, an over-fast route) give the frozen verdicts. Device checks
give the frozen failure bits and diagnostics, faults included.
(b) An idle operator equals the composition without it: closed water (every
availability 0) equals the empty composition, and a symport without routes or
with every route blocked equals water alone (IMEX).
(d) Restart is bitwise; a vmap batch reproduces the frozen model's batch bitwise.

These tests passed against the frozen implementation (commit 8416a72; evidence in
/mnt/workspaces/Cells/composite-s1-20261111-01/tests/). Since commit 0161127 the
water@1 and water@2 modules are thin compositions, so here "frozen" is the frozen
definition format run through its own model module, and the tests guard that it and
its composite rewrite (core/pump_composite_spec.frozen_definition) run identically.
The comparison with the earlier implementation is the cross-revision guard
(validation/tissue/composite_dump.py, run from the frozen snapshot).
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy
from cells.models import surface_pump_water, surface_pump_water_v2
from cells.models.registry import get_model
from cells.numerics import surface_imex as imex
from validation.tissue import composite_guard as guard
from validation.tissue import pump_water_fixtures as fixtures
from validation.tissue import surface_pump_v3_fixtures as v3_fixtures

AQUAPORIN_PF = 5e-4


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def cell(state="H", *, end=0.2, dt=1e-3, solver=imex.ARS222_ID, times=None, **water_kw):
    raw = fixtures.heredity_cell(state, dt=dt, end_time=end, solver=solver)
    raw["experiment"]["observation_times"] = (
        [0.0, round(end / 2, 6), end] if times is None else list(times)
    )
    return fixtures.with_water(raw, **water_kw)


def closed_ions(raw):
    for key in ("membrane_controls", "pump_controls", "channel_controls"):
        for group in raw["experiment"][key]:
            group["schedule"] = [dict(time=0.0, availability=0.0)]
    return raw


def kicked(dt, end, solver=imex.ARS222_ID):
    state = v3_fixtures.kicked(v3_fixtures.HEREDITY_STATES["D"], 4.0)
    raw = v3_fixtures.heredity_cells(
        [state], dt=dt, end_time=end, solver=solver, observation_times=[0.0, end / 2, end]
    )
    return fixtures.with_water(raw, pf_m_s=AQUAPORIN_PF)


def regulated(raw, **kw):
    return fixtures.with_symport(raw, **({"flux_mmol_L_h": 15.0, "steepness": 0.12} | kw))


def sheet(end=0.03):
    raw = fixtures.gated_sheet(end_time=end)
    raw["experiment"]["observation_times"] = [0.0, end / 2, end]
    raw["model"]["junction_heat_booking"] = "trapezoid_nonnegative@1"
    return fixtures.with_water(raw, pf_m_s=AQUAPORIN_PF)


WORLDS = {
    "water_on": lambda: cell("H", end=0.3, pf_m_s=AQUAPORIN_PF),
    "osmometer": lambda: closed_ions(
        cell(end=0.5, dt=2e-3, pf_m_s=AQUAPORIN_PF, bulk_modulus_Pa=0.0, pressure_offset_Pa=0.0)
    ),
    "euler_kicked": lambda: kicked(1e-3, 0.064, imex.EULER_ID),
    "rk4_coupled": lambda: kicked(2.5e-6, 2.5e-4, "rk4"),
    "sheet_trapezoid": sheet,
    "route_on": lambda: regulated(cell("D", end=0.2, pf_m_s=AQUAPORIN_PF)),
    "route_sheet": lambda: regulated(sheet(0.02)),
    "route_rk4": lambda: regulated(kicked(2.5e-6, 2.5e-4, "rk4")),
}


@pytest.mark.parametrize("world", WORLDS)
def test_re_expressed_water_models_are_the_frozen_models(world):
    raw = WORLDS[world]()
    frozen, composite = parse_spec(raw), parse_spec(cs.frozen_definition(raw))
    expected = surface_pump_water_v2 if "route" in world else surface_pump_water
    assert get_model(frozen.model) is expected
    report = guard.assert_same(run(frozen), run(composite))
    assert report["compared"]["history"] == len(expected.STATE_TYPE._fields)


def outcome(spec):
    try:
        run(spec)
    except (NumericalError, ConfigError) as error:
        return type(error).__name__, str(error)
    return None


REFUSALS = {
    "volume_bound": lambda: cell("H", end=0.2, pf_m_s=AQUAPORIN_PF, minimum_fraction=0.9999),
    "fast_water": lambda: cell(pf_m_s=1.0),
    "fast_route": lambda: regulated(cell("D", pf_m_s=AQUAPORIN_PF), flux_mmol_L_h=1e9),
}


@pytest.mark.parametrize("case", REFUSALS)
def test_refusals_are_the_frozen_verdicts(case):
    raw = REFUSALS[case]()
    frozen, composite = outcome(parse_spec(raw)), outcome(parse_spec(cs.frozen_definition(raw)))
    assert frozen is not None
    assert composite[0] == frozen[0]
    if frozen[0] == "ConfigError":
        assert composite[1] == frozen[1]


def test_a_bad_water_control_refuses_the_step_as_frozen():
    raw = cell()
    frozen, composite = parse_spec(raw), parse_spec(cs.frozen_definition(raw))
    for spec in (frozen, composite):
        model = get_model(spec.model)
        state, p = model.initial_values(spec)
        controls = control_values(spec, [0.0])
        control = type(controls)(*(np.asarray(v[0]) for v in controls))
        bad = control._replace(water=np.full_like(control.water, 1.01))
        kept, valid = jax.jit(model.checked_step)(state, 1e-3, bad, p, p.active)
        assert not valid
        for a, b in zip(kept, state, strict=True):
            assert np.array_equal(np.asarray(a), b)


def device(model, spec, history, row):
    _, p = model.initial_values(spec)
    p = jax.tree.map(jnp.asarray, p)
    constants = model.device_check_constants(spec)
    rows = [type(history)(*(jnp.asarray(v[i]) for v in history)) for i in (row - 1, row)]
    bits, values = model.device_checks(rows[0], rows[1], p, constants, row)
    return np.asarray(bits), np.asarray(values)


FAULTS = {
    "water_transfer": lambda s, i: s._replace(
        water_transferred_pL=s.water_transferred_pL.at[i, 0].add(1e-9)
    ),
    "bath_work": lambda s, i: s._replace(
        bath_water_work_pJ=s.bath_water_work_pJ.at[i, 0].add(1e-6)
    ),
    "symport_heat": lambda s, i: s._replace(
        symport_dissipated_energy_pJ=s.symport_dissipated_energy_pJ.at[i, 0].set(
            s.symport_dissipated_energy_pJ[i - 1, 0] - 2e-12
        )
    ),
}


def test_device_and_host_checks_give_the_frozen_bits_and_messages():
    raw = WORLDS["route_on"]()
    frozen, composite = parse_spec(raw), parse_spec(cs.frozen_definition(raw))
    a, b = run(frozen), run(composite)
    fm, cm = get_model(frozen.model), get_model(composite.model)
    assert cm.DEVICE_CHECKS == fm.DEVICE_CHECKS
    assert cm.DEVICE_DIAGNOSTICS == fm.DEVICE_DIAGNOSTICS
    for row in (1, 100, len(a.times) - 1):
        x, y = device(fm, frozen, a.history, row), device(cm, composite, b.history, row)
        assert np.array_equal(x[0], y[0]) and np.array_equal(x[1], y[1]), row
    steps = np.arange(len(a.times))
    for name, change in FAULTS.items():
        row = 100
        bad = [
            type(h)(*(np.asarray(v) for v in change(type(h)(*(jnp.asarray(v) for v in h)), row)))
            for h in (a.history, b.history)
        ]
        messages = []
        for model, spec, history in ((fm, frozen, bad[0]), (cm, composite, bad[1])):
            try:
                model.check_values(history, spec, steps=steps)
                messages.append(None)
            except NumericalError as error:
                messages.append(str(error))
        assert messages[0] is not None and messages[0] == messages[1], name
        x, y = device(fm, frozen, bad[0], row), device(cm, composite, bad[1], row)
        assert np.array_equal(x[0], y[0]), name


def test_idle_operators_equal_the_composition_without_them():
    raw = fixtures.heredity_cell("H", end_time=0.2)
    raw["experiment"]["observation_times"] = [0.0, 0.1, 0.2]
    empty = run(parse_spec(cs.frozen_definition(raw)))
    closed = run(parse_spec(cs.frozen_definition(fixtures.with_water(raw, availability=0.0))))
    guard.assert_same(empty, closed, history_fields=type(empty.history)._fields)
    for name in surface_pump_water.WATER_STATE_AXES:
        assert not np.any(np.asarray(getattr(closed.history, name))), name
    water = cell("D", end=0.2, pf_m_s=AQUAPORIN_PF)
    alone = run(parse_spec(cs.frozen_definition(water)))
    for idle in (
        fixtures.with_symport(water, membranes=[]),
        fixtures.with_symport(water, availability=0.0),
    ):
        result = run(parse_spec(cs.frozen_definition(idle)))
        guard.assert_same(alone, result, history_fields=type(alone.history)._fields)
        for name in surface_pump_water_v2.SYMPORT_STATE_AXES:
            assert not np.any(np.asarray(getattr(result.history, name))), name


def test_restart_and_vmap_identity(tmp_path):
    raw = WORLDS["route_on"]()
    spec = parse_spec(cs.frozen_definition(raw))
    value = run(spec)
    checkpoint = value.checkpoint_at(0.1)
    resumed = run(spec, checkpoint)
    for a, b in zip(resumed.history, value.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    frozen, composite = [], []
    for i, state in enumerate(("D", "H", "D")):
        raw = cell(state, end=0.1, pf_m_s=AQUAPORIN_PF * (1 + 0.1 * i))
        for c in raw["model"]["channels"]:
            c["max_permeability_m_per_s"] *= 1 + 0.1 * i
        frozen.append(parse_spec(raw))
        composite.append(parse_spec(cs.frozen_definition(raw)))
    policy = WindowPolicy(40, "checkpoints")

    def cohort(specs):
        return BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 3, 10**6, 2**31)

    a = run_vector_windowed(cohort(frozen), policy)
    b = run_vector_windowed(cohort(composite), policy)
    for world in a.worlds:
        x, y = a.worlds[world].final.state, b.worlds[world].final.state
        for key in type(x)._fields:
            assert guard.compare_arrays(key, getattr(x, key), getattr(y, key)) is None, key
        for key, value in a.worlds[world].diagnostics.items():
            if key.startswith("max_"):
                assert b.worlds[world].diagnostics[key] == value, (world, key)
