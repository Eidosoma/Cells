"""resolved_pump_water@1: osmotic water and compliant volumes on resolved_pump_tissue@3.

Definitions: round trip, dispatch and declaration errors. Law: edge_exchange is
evaluate()'s pressures, flows and heat, bitwise; the layout binds conductance
1e15 A Lp and the held bath's water potential P_b - RT sum(c_b). Physics: a cell
with every ion route closed is an ideal osmometer and follows the exact
solution, with second-order water steps; water-on heredity cells close every
ledger, and the energy ledger needs the dilution, elastic and bath-work terms
(without them it fails); every @3 stage sees amount / current volume. Refusals:
a volume bound (no clipping), an over-fast water law, an invalid water control.
Restart is bitwise; the split ARS(2,2,2) step is second order and agrees with the
coupled RK4 path.
"""

import copy

import jax
import numpy as np
import pytest
from scipy import optimize

from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_pump_water_spec import Control, control_values
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_pump_v3, surface_pump_water
from cells.models.registry import get_model
from cells.numerics import osmotic_water as water
from cells.numerics import surface_imex as imex
from cells.processes.electrochemistry import R
from validation.tissue import pump_water_fixtures as fixtures
from validation.tissue import surface_pump_v3_fixtures as v3_fixtures

AQUAPORIN_PF = 5e-4  # 0.05 cm/s (astrocytes, Solenov et al. 2004): tau about 0.85 s.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def cell(state="H", *, end=0.2, dt=1e-3, solver=imex.ARS222_ID, times=None, **water_kw):
    raw = fixtures.heredity_cell(state, dt=dt, end_time=end, solver=solver)
    raw["experiment"]["observation_times"] = (
        [0.0, round(end / 2, 6), end] if times is None else list(times)
    )
    return fixtures.with_water(raw, **water_kw)


def initial(raw):
    spec = parse_spec(raw)
    state, layout = get_model(spec.model).initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, Control(*(v[0] for v in controls))


def closed_ions(raw):
    """Every ion route closed: membrane leak, pump and channel availabilities 0."""
    raw = copy.deepcopy(raw)
    e = raw["experiment"]
    for key in ("membrane_controls", "pump_controls", "channel_controls"):
        for group in e[key]:
            group["schedule"] = [dict(time=0.0, availability=0.0)]
    return raw


# ------------------------------------------------------------ definitions


def test_definition_round_trip_and_dispatch():
    spec = parse_spec(cell())
    assert get_model(spec.model) is surface_pump_water
    assert parse_spec(spec.to_dict()) == spec
    assert spec.to_dict()["model"]["id"] == "resolved_pump_water@1"
    raw = cell()
    assert [c["compartment_id"] for c in raw["model"]["water"]["compartments"]] == ["cell_0"]
    assert [c["compartment_id"] for c in raw["model"]["water"]["baths"]] == ["bath_0"]


def test_junction_heat_option_passes_through_to_resolved_pump_tissue_3():
    raw = fixtures.with_water(fixtures.gated_sheet(end_time=0.01))
    assert "junction_heat_booking" not in parse_spec(raw).to_dict()["model"]
    raw["model"]["junction_heat_booking"] = "trapezoid_nonnegative@1"
    spec = parse_spec(raw)
    assert spec.model.junction_heat_booking == "trapezoid_nonnegative@1"
    assert parse_spec(spec.to_dict()) == spec
    _, p = surface_pump_water.initial_values(spec)
    assert p.junction_heat_trapezoid.shape == (1,)


def _edit(path, value):
    def apply(raw):
        target = raw
        for key in path[:-1]:
            target = target[key]
        if value is KeyError:
            del target[path[-1]]
        else:
            target[path[-1]] = value
        return raw

    return apply


ERRORS = {
    "no_water": _edit(("model", "water"), KeyError),
    "no_controls": _edit(("experiment", "water_controls"), KeyError),
    "law": _edit(("model", "water", "law"), "ideal_osmosis@0"),
    "missing_compartment": _edit(("model", "water", "compartments"), []),
    "bath_as_compartment": lambda raw: (
        raw["model"]["water"]["compartments"].append(
            dict(raw["model"]["water"]["compartments"][0], compartment_id="bath_0")
        )
        or raw
    ),
    "missing_bath": _edit(("model", "water", "baths"), []),
    "initial_outside_bounds": _edit(
        ("model", "water", "compartments", 0, "minimum_volume_pL"), 0.8
    ),
    "reference_outside_bounds": _edit(
        ("model", "water", "compartments", 0, "reference_volume_pL"), 2.0
    ),
    "negative_permeability": _edit(
        ("model", "water", "membranes", 0, "hydraulic_permeability_m_per_Pa_s"), -1e-13
    ),
    "negative_impermeant": _edit(
        ("model", "water", "compartments", 0, "impermeant_amount_fmol"), -1.0
    ),
    "negative_modulus": _edit(("model", "water", "compartments", 0, "bulk_modulus_Pa"), -1.0),
    "availability": _edit(
        ("experiment", "water_controls", 0, "schedule"), [dict(time=0.0, availability=1.5)]
    ),
    "control_id": _edit(("experiment", "water_controls", 0, "membrane_id"), "membrane_9"),
    "late_start": _edit(
        ("experiment", "water_controls", 0, "schedule"), [dict(time=0.1, availability=1.0)]
    ),
}


@pytest.mark.parametrize("fault", ERRORS)
def test_definition_errors(fault):
    with pytest.raises(ConfigError):
        parse_spec(ERRORS[fault](cell()))


# ---------------------------------------------------------------- the law


def test_edge_exchange_is_evaluate_bitwise():
    rng = np.random.default_rng(3)
    n, e = 6, 9
    sender = rng.integers(0, n, e)
    receiver = (sender + rng.integers(1, n, e)) % n
    p = water.validate_parameters(
        water.Parameters(
            temperature_K=310.0,
            active=np.ones(n, dtype=bool),
            reference_volume_pL=rng.uniform(0.5, 2.0, n),
            minimum_volume_pL=np.full(n, 0.1),
            maximum_volume_pL=np.full(n, 5.0),
            impermeant_amount_fmol=rng.uniform(0, 50, n),
            bulk_modulus_Pa=rng.uniform(0, 1e4, n),
            pressure_offset_Pa=rng.uniform(-100, 100, n),
            edge_active=np.ones(e, dtype=bool),
            sender=sender,
            receiver=receiver,
            conductance_pL_per_Pa_s=rng.uniform(0, 1e-5, e),
        )
    )
    volume = rng.uniform(0.6, 1.8, n)
    amount = rng.uniform(10, 200, (4, n))
    availability = rng.uniform(0, 1, e)
    a = water.evaluate(volume, amount, availability, p)
    b = water.edge_exchange(volume, amount, availability, p)
    for name in water.EdgeValues._fields:
        np.testing.assert_array_equal(getattr(b, name), getattr(a, name))


def test_layout_binds_conductance_and_held_bath_potential():
    raw = cell(bath_pressure_Pa=12.5)
    spec, state, p, control = initial(raw)
    lp = raw["model"]["water"]["membranes"][0]["hydraulic_permeability_m_per_Pa_s"]
    area = raw["model"]["membranes"][0]["area_m2"]
    assert p.water_conductance_pL_per_Pa_s[0] == pytest.approx(1e15 * area * lp, rel=1e-15)
    assert lp == pytest.approx(fixtures.NO_AQUAPORIN_PF_M_S * 18.07e-6 / (R * 310.0), rel=1e-6)
    bath = raw["model"]["extracellular"][0]
    osmolarity = sum(bath["initial_amount_fmol"].values()) / bath["volume_pL"]
    assert p.water_bath.tolist() == [True]
    assert p.water_bath_potential_Pa[0] == pytest.approx(12.5 - R * 310.0 * osmolarity, rel=1e-14)
    assert osmolarity == 300.0
    # No water state yet; every water field exists and is zero.
    for name in surface_pump_water.WATER_STATE_AXES:
        assert not np.any(getattr(state, name))


# ---------------------------------------------------------------- physics


def osmometer(dt, end=2.0):
    raw = closed_ions(
        cell(
            end=end,
            dt=dt,
            times=[0.0, 0.5, end],
            pf_m_s=AQUAPORIN_PF,
            bulk_modulus_Pa=0.0,
            pressure_offset_Pa=0.0,
        )
    )
    return parse_spec(raw), run(parse_spec(raw))


def exact_osmometer_volume(spec, t):
    """V(t) of dV/dt = a (N/V - c), a = G R T, from its exact inverse

    t(V) = -[(V - V0) + (N/c) ln((N - cV)/(N - cV0))] / (a c).
    """
    _, p = surface_pump_water.initial_values(spec)
    v0 = float(p.volume[0])
    n = float(np.sum(p.amount_reference[:, 0]))
    c = float(np.sum(p.extracellular_amount_reference[:, 0]) / p.extracellular_volume[0])
    a = float(p.water_conductance_pL_per_Pa_s[0]) * R * 310.0

    def elapsed(v):
        return -((v - v0) + (n / c) * np.log((n - c * v) / (n - c * v0))) / (a * c) - t

    final = n / c
    return optimize.brentq(elapsed, final + 1e-12 * (v0 - final), v0, xtol=1e-16, rtol=1e-15)


def test_osmometer_follows_the_exact_solution_with_second_order_water_steps():
    errors = []
    for dt in (4e-3, 2e-3, 1e-3):
        spec, result = osmometer(dt)
        # Every ion route is closed: no ion moves, so the volume is the only dynamics.
        assert not np.any(result.history.amount_increment)
        assert not np.any(result.history.extracellular_amount_increment)
        volume = result.observations.cell_volume_pL[:, 0]
        exact = [exact_osmometer_volume(spec, t) for t in result.observations.times]
        assert volume[-1] < volume[0]  # 284.2 mM against a 300 mM bath: it shrinks.
        errors.append(float(np.max(np.abs(volume - exact))))
        assert result.diagnostics["max_energy_balance_relative"] < 1e-6
    assert errors[-1] < 1e-7 * volume[0]
    orders = np.log2(np.asarray(errors[:-1]) / np.asarray(errors[1:]))
    assert np.all(orders > 1.8), errors


@pytest.fixture(scope="module")
def water_on():
    raw = cell("H", end=0.5, times=[0.0, 0.25, 0.5], pf_m_s=AQUAPORIN_PF)
    spec = parse_spec(raw)
    return spec, run(spec)


def test_water_on_cell_closes_every_ledger(water_on):
    spec, result = water_on
    d = result.diagnostics
    for key in (
        "max_cell_water_balance_error_pL",
        "max_outside_water_balance_error_pL",
        "max_global_water_balance_error_pL",
    ):
        assert d[key] < 1e-15
    assert d["max_bath_water_work_error_pJ"] < 1e-12
    assert d["max_energy_balance_relative"] < 1e-6
    volume = result.observations.cell_volume_pL[:, 0]
    assert volume[-1] < volume[0] * (1 - 1e-3)  # Visible shrinkage in 0.5 s.
    # Water supply from the bath is the cell's volume change, exactly booked.
    np.testing.assert_allclose(
        -result.history.bath_water_supplied_pL[-1, 0],
        -result.history.volume_increment_pL[-1, 0],
        rtol=1e-12,
    )


def test_energy_ledger_needs_the_water_terms(water_on):
    """Negative control: @3's energy ledger alone does not close with water on."""
    spec, result = water_on
    _, p = surface_pump_water.initial_values(spec)
    row = surface_pump_water.STATE_TYPE(*(np.asarray(v[-1]) for v in result.history))
    alone = surface_pump_v3.balances(
        surface_pump_water.ionic_state(row), surface_pump_water.ionic_layout(p)
    )["energy"]
    complete = surface_pump_water.balances(row, p)["energy"]
    assert abs(alone) > 1e3 * abs(complete)
    assert abs(alone) > 1e-6


def test_every_ionic_stage_sees_the_current_volume(water_on):
    spec, result = water_on
    _, p = surface_pump_water.initial_values(spec)
    row = surface_pump_water.STATE_TYPE(*(np.asarray(v[-1]) for v in result.history))
    control = Control(*(v[0] for v in control_values(spec, [0.5])))
    v = surface_pump_water.readouts(row, control, p, xp=np)
    current = surface_pump_v3.LAYOUT_TYPE(
        *(getattr(p, k) for k in surface_pump_v3.LAYOUT_TYPE._fields)
    )
    volume = p.volume + row.volume_increment_pL
    assert volume[0] != p.volume[0]
    reference = surface_pump_v3.readouts(
        surface_pump_water.ionic_state(row),
        surface_pump_water.ionic_control(control),
        current._replace(volume=volume),
        xp=np,
    )
    for a, b in zip(v.ionic.derivative, reference.derivative, strict=True):
        np.testing.assert_array_equal(a, b)
    # The flow is the law's: G a (psi_cell - psi_bath), psi = P - RT N / V.
    total = np.sum(p.amount_reference[:, 0] + row.amount_increment[:, 0])
    psi_cell = (
        p.water_bulk_modulus_Pa[0] * (volume[0] / p.water_reference_volume_pL[0] - 1)
        + p.water_pressure_offset_Pa[0]
        - R * 310.0 * total / volume[0]
    )
    flow = p.water_conductance_pL_per_Pa_s[0] * (psi_cell - p.water_bath_potential_Pa[0])
    assert v.water.flow[0] == pytest.approx(flow, rel=1e-12)
    obs = result.observations
    np.testing.assert_allclose(
        obs.cell_concentration_mM[-1, :, 0],
        (p.amount_reference[:, 0] + row.amount_increment[:, 0]) / volume[0],
        rtol=1e-15,
    )


def test_volume_bound_refuses_without_clipping():
    raw = cell("H", end=0.2, pf_m_s=AQUAPORIN_PF, minimum_fraction=0.9999)
    spec, state, p, control = initial(raw)
    with pytest.raises(NumericalError):
        run(spec)
    step = jax.jit(surface_pump_water.checked_step)
    gap = float(p.volume[0] - p.water_minimum_volume_pL[0])
    near = state._replace(volume_increment_pL=np.array([-gap * (1 - 1e-9)]))
    kept, valid = step(near, 1e-3, control, p, p.active)
    assert not valid
    for a, b in zip(kept, near, strict=True):
        np.testing.assert_array_equal(np.asarray(a), b)


def test_fast_water_law_is_refused_at_the_definition():
    spec = parse_spec(cell(pf_m_s=1.0))  # 100 cm/s: dt x rate far above 0.05 at 1 ms.
    with pytest.raises(ConfigError, match="Water relaxation"):
        run(spec)


def test_invalid_water_control_refuses_the_step():
    spec, state, p, control = initial(cell())
    bad = control._replace(water=np.full_like(control.water, 1.01))
    kept, valid = jax.jit(surface_pump_water.checked_step)(state, 1e-3, bad, p, p.active)
    assert not valid
    for a, b in zip(kept, state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), b)


def test_restart_is_bitwise(tmp_path):
    raw = cell("D", end=0.1, times=[0.0, 0.05, 0.1], pf_m_s=AQUAPORIN_PF)
    spec = parse_spec(raw)
    value = run(spec)
    checkpoint = value.checkpoint_at(0.05)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, value.history, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])


def kicked_cell(dt, end, solver=imex.ARS222_ID):
    state = v3_fixtures.kicked(v3_fixtures.HEREDITY_STATES["D"], 4.0)
    raw = v3_fixtures.heredity_cells(
        [state], dt=dt, end_time=end, solver=solver, observation_times=[0.0, end]
    )
    return parse_spec(fixtures.with_water(raw, pf_m_s=AQUAPORIN_PF))


def test_split_ars_step_is_second_order():
    end, results = 0.064, {}
    for dt in (4e-3, 2e-3, 1e-3, 5e-4, 2.5e-4):
        results[dt] = run(kicked_cell(dt, end)).history
    reference = results.pop(2.5e-4)
    errors = {"volume": [], "voltage": [], "amount": []}
    for history in results.values():
        errors["volume"].append(
            float(np.abs(history.volume_increment_pL[-1] - reference.volume_increment_pL[-1]).max())
        )
        errors["amount"].append(
            float(np.abs(history.amount_increment[-1] - reference.amount_increment[-1]).max())
        )
    for name in ("volume", "amount"):
        values = np.asarray(errors[name])
        orders = np.log2(values[:-1] / values[1:])
        assert np.all(orders > 1.75), (name, values)


def test_coupled_rk4_path_agrees_with_the_split_step():
    end = 0.001
    rk4 = run(kicked_cell(2.5e-6, end, solver="rk4")).history
    split = run(kicked_cell(2.5e-6, end)).history
    for name in ("volume_increment_pL", "amount_increment", "water_transferred_pL"):
        a, b = np.asarray(getattr(rk4, name))[-1], np.asarray(getattr(split, name))[-1]
        scale = max(np.abs(a).max(), 1e-30)
        assert np.abs(a - b).max() <= 1e-6 * scale, name
