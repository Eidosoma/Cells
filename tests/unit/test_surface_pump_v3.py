"""resolved_pump_tissue@3: resolved_pump_tissue@2 plus voltage-gated channel populations.

Equivalence: with no channels the identity reproduces @2 (observed bitwise for
RK4 and both IMEX schemes), and its RK4 law path reproduces resolved_tissue@8's
Kv1.5/Kir2.1/NaV1.2/leak catalog. Gates: the exponential update is bounded,
exact at constant voltage and second order. IMEX: exact explicit/implicit
split, single-patch channel currents against the RK4 catalog at small steps,
observed orders, family ledgers, the explicit-stage refusal, bitwise restart,
definition errors, temperatures and CPU/L4 agreement. Heredity: the pre-screen's
H and D states are stationary and stable at 1 ms, a Na-leak cue writes D and a
NaV1.2 block erases it.
"""

import json
import os
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_pump_v3_spec import NALEAK_LAW_ID, control_values
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_catalog, surface_pump_v2, surface_pump_v3
from cells.models.registry import get_model
from cells.numerics import exponential_gates as gates
from cells.numerics import surface_imex as imex
from cells.processes import sodium_channels, voltage_gates
from validation.tissue import surface_pump_v2_fixtures as second
from validation.tissue import surface_pump_v3_fixtures as fixtures

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
SOLVERS = (imex.EULER_ID, imex.ARS222_ID)
CHANNEL_FIELDS = ("channel_gate", "channel_transferred", "channel_dissipated_energy_pJ")
CHANNEL_OBSERVATIONS = (
    *CHANNEL_FIELDS,
    "channel_flux_fmol_s",
    "channel_targets",
    "channel_tau_s",
    "channel_availability",
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def scaled_difference(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    scale = max(np.max(np.abs(a), initial=0), np.max(np.abs(b), initial=0))
    return 0.0 if scale == 0 else float(np.max(np.abs(a - b)) / scale)


def initial(raw):
    spec = parse_spec(raw)
    state, layout = get_model(spec.model).initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


def test_exponential_gate_update_is_bounded_exact_and_second_order():
    rng = np.random.default_rng(11)
    g, a, b = rng.uniform(0, 1, (3, 4096))
    tau_a, tau_b = 10 ** rng.uniform(-5, 0, (2, 4096))
    dt = 10 ** rng.uniform(-6, -1, 4096)
    value = gates.advance(g, a, tau_a, b, tau_b, dt, xp=np)
    low, high = np.minimum(g, np.minimum(a, b)), np.maximum(g, np.maximum(a, b))
    assert np.all((value >= low - 1e-15) & (value <= high + 1e-15))
    # Constant voltage: the exact relaxation; stiff limit: target with its lag.
    np.testing.assert_allclose(
        gates.advance(g, a, tau_a, a, tau_a, dt, xp=np),
        a + (g - a) * np.exp(-dt / tau_a),
        rtol=1e-13,
        atol=1e-16,
    )
    z = 1e6
    np.testing.assert_allclose(
        gates.advance(g, a, 1.0, b, 1.0, z, xp=np), b - (b - a) / z, rtol=1e-12, atol=1e-15
    )
    # Both branches of the lag weight agree where they meet (the closed form's
    # own rounding is about 4e-16/z there).
    z = np.array([gates.SERIES_LIMIT * (1 - 1e-12), gates.SERIES_LIMIT * (1 + 1e-12), 1.0, 30.0])
    closed = (np.expm1(-z) + z) / z
    np.testing.assert_allclose(gates.lag_weight(z, xp=np), closed, rtol=2e-12)

    # Second order with a prescribed voltage swing, including the stiff NaV1.2
    # m gate at millisecond steps, against fine RK4 of the gate equations.
    codes = np.array([0, 1, 2])

    def voltage(t):
        return -0.07 + 0.024 * (1 + np.tanh((t - 0.01) / 0.003)) + 0.004 * np.sin(400 * t)

    def kinetics(t):
        return sodium_channels.kinetics(np.full(3, voltage(t)), codes, xp=np)

    end, h = 0.02, 2.5e-6
    reference = kinetics(0.0)[0]
    for i in range(int(round(end / h))):
        t = i * h

        def slope(time, y):
            target, tau = kinetics(time)
            return (target - y) / tau

        k1 = slope(t, reference)
        k2 = slope(t + h / 2, reference + h / 2 * k1)
        k3 = slope(t + h / 2, reference + h / 2 * k2)
        k4 = slope(t + h, reference + h * k3)
        reference = reference + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    errors = []
    for dt in (1e-3, 5e-4, 2.5e-4, 1.25e-4):
        gate = kinetics(0.0)[0]
        for i in range(int(round(end / dt))):
            start, stop = kinetics(i * dt), kinetics((i + 1) * dt)
            gate = gates.advance(gate, *start, *stop, dt, xp=np)
        errors.append(float(np.max(np.abs(gate - reference))))
    rates = np.log2(np.asarray(errors[:-1]) / np.asarray(errors[1:]))
    assert np.all(rates > 1.8), errors


@pytest.mark.parametrize("solver", ["rk4", *SOLVERS])
def test_without_channels_reproduces_resolved_pump_tissue_2(solver):
    """Same states and observations as @2; the channel terms are exact zeros.

    Observed bitwise on CPU; the bound is the requested 1e-13 of each array's
    magnitude, which admits a compiled reordering.
    """
    spec = parse_spec(fixtures.definition("release", solver=solver, channels=False))
    assert get_model(spec.model) is surface_pump_v3
    assert parse_spec(spec.to_dict()) == spec
    reference = parse_spec(second.definition("release", solver=solver))
    assert get_model(reference.model) is surface_pump_v2
    a, b = run(spec), run(reference)
    for key in surface_pump_v2.STATE_TYPE._fields:
        if key not in CHANNEL_FIELDS:
            assert scaled_difference(getattr(a.history, key), getattr(b.history, key)) <= 1e-13
    for key, value in vars(b.observations).items():
        if key in CHANNEL_OBSERVATIONS:
            assert not np.asarray(getattr(a.observations, key)).size or key.endswith("tau_s")
            continue
        if key in ("charge_residual_C", "component_current_residual_A", "energy_balance_pJ_s"):
            continue  # Roundoff-level constraint residuals.
        assert scaled_difference(getattr(a.observations, key), value) <= 1e-13, key
    assert a.diagnostics.keys() == b.diagnostics.keys()


def test_rk4_law_reproduces_the_resolved_tissue_8_catalog():
    """Kv1.5, Kir2.1, NaV1.2 and both leaks: same currents, gates and ledgers.

    resolved_tissue@8 keeps two unused gates for its leak laws; those rows are
    not compared. Its dense field agrees with the factored one to 1e-12.
    """
    raw = fixtures.definition("clamped", calcium=False)
    reference = fixtures.catalog_reference(raw)
    dt = 1.25e-6
    for definition in (raw, reference):
        definition["execution"].update(dt=dt, max_steps=1024)
        definition["experiment"].update(end_time=5e-4, observation_times=[0.0, 200 * dt, 5e-4])
    a, b = run(parse_spec(raw)), run(parse_spec(reference))
    assert get_model(b.spec.model) is surface_catalog
    gated = [i for i, row in enumerate(fixtures.CHANNELS) if row[-1]]
    for key in surface_pump_v3.STATE_TYPE._fields:
        if key.startswith("calcium"):
            continue
        x, y = np.asarray(getattr(a.history, key)), np.asarray(getattr(b.history, key))
        if key == "channel_gate":
            x, y = x[..., gated], y[..., gated]
        assert scaled_difference(x, y) <= 1e-12, key
    for key in ("channel_flux_fmol_s", "membrane_voltage_V", "membrane_flux_fmol_s"):
        x, y = getattr(a.observations, key), getattr(b.observations, key)
        assert scaled_difference(x, y) <= 1e-12, key


def test_single_patch_channel_currents_match_the_rk4_catalog_at_small_steps():
    """All five laws on one patch, gates off steady state: IMEX converges to RK4.

    The reference is resolved_tissue@8 (RK4 at its 1.25 us bound). Each
    population's flux, scaled by its own largest magnitude, converges at second
    order under ARS(2,2,2).
    """
    reference = run(
        parse_spec(fixtures.catalog_reference(fixtures.single_patch(dt=1.25e-6)))
    ).observations.channel_flux_fmol_s
    errors = []
    for dt in (1e-5, 5e-6, 2.5e-6):
        raw = fixtures.single_patch(dt=dt, solver=imex.ARS222_ID)
        flux = run(parse_spec(raw)).observations.channel_flux_fmol_s
        scale = np.max(np.abs(reference), axis=(0, 1))
        errors.append(float(np.max(np.abs(flux - reference) / scale)))
    rates = np.log2(np.asarray(errors[:-1]) / np.asarray(errors[1:]))
    assert errors[-1] <= 2e-6 and np.all(rates > 1.75), errors


@pytest.mark.parametrize("arm", ["open", "closed", "release"])
def test_explicit_and_implicit_parts_sum_to_the_law(arm):
    """At the law's potentials the split rates equal the readouts; gates are separate."""
    spec, state, p, control = initial(fixtures.definition(arm, solver=imex.ARS222_ID))
    law = surface_pump_v3.readouts(state, control, p, xp=np)
    explicit, valid = surface_pump_v3.explicit_rates(
        state, law.field.potential_V, control, p, xp=np
    )
    assert law.valid and valid
    co = np.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1)
    weight, _ = imex.face_weights(co, surface_pump_v3.tissue.field_layout(p).surface, xp=np)
    drift = surface_pump_v3.implicit_rates(weight, law.field.potential_V, state, p, xp=np)
    for key in surface_pump_v3.STATE_TYPE._fields:
        if key.endswith(("face_dissipated_energy_pJ", "_work_pJ")) or key in (
            "electrode_charge_transferred_C",
            "channel_gate",
        ):
            continue  # Step-level ledgers, and gates set by the exponential update.
        total = getattr(explicit, key) + getattr(drift, key)
        assert scaled_difference(total, getattr(law.derivative, key)) <= 1e-13, key
    assert not np.any(explicit.channel_gate) and not np.any(drift.channel_gate)
    target, tau = law.channel_targets, law.channel_tau_s
    expected = np.where(p.channel_gate_active, (target - state.channel_gate) / tau, 0.0)
    np.testing.assert_array_equal(law.derivative.channel_gate, expected)
    if arm != "release":
        assert np.all(np.abs(law.channel_flux_fmol_s).sum(axis=0)[p.channel_active] > 0)


@pytest.fixture(scope="module")
def imex_runs():
    runs = {
        (arm, solver): run(parse_spec(fixtures.definition(arm, solver=solver, backend=BACKEND)))
        for arm in ("closed", "release")
        for solver in SOLVERS
    }
    reference = fixtures.definition("clamped", backend=BACKEND)
    reference["execution"].update(dt=2.5e-6, max_steps=1024)
    runs["clamped", "rk4"] = run(parse_spec(reference))
    for solver in SOLVERS:
        runs["clamped", solver] = run(
            parse_spec(fixtures.definition("clamped", solver=solver, backend=BACKEND))
        )
    return runs


@pytest.mark.parametrize("arm", ["closed", "clamped", "release"])
@pytest.mark.parametrize("solver", SOLVERS)
def test_imex_ledgers_constraints_and_channel_transfer(arm, solver, imex_runs):
    value = imex_runs[arm, solver]
    d = value.diagnostics
    tol = value.spec.execution.material_balance_atol_fmol
    for key in ("balance", "extracellular_balance", "global_balance"):
        assert d[f"max_{key}_error_fmol"] <= min(tol)
    assert d["max_capacitor_charge_error_C"] <= 3e-25
    assert d["max_global_charge_bound_ratio"] <= 1.0
    assert d["max_reservoir_work_error_pJ"] <= 3e-12 and d["max_metabolic_work_error_pJ"] <= 3e-12
    assert d["max_energy_balance_relative"] <= surface_pump_v3.ENERGY_RTOL[solver]
    # Each cell's K changes by its leak, pump, channel and junction exchange, so
    # the channels move the inventory they are said to move.
    history, k = value.history, value.spec.model.species_ids.index("K")
    _, p = surface_pump_v3.initial_values(value.spec)
    expected = np.zeros_like(history.amount_increment[:, k])
    for transferred, owner, sign in (
        (history.membrane_transferred[:, k], p.membrane_cell, -1),
        (-p.stoichiometry[k] * history.pump_cycles, p.membrane_cell, -1),
        (history.channel_transferred[:, k], p.membrane_cell[p.channel_membranes], -1),
        (history.junction_transferred[:, k], p.junction_sender, -1),
        (history.junction_transferred[:, k], p.junction_receiver, 1),
    ):
        np.add.at(expected, (slice(None), owner), sign * np.asarray(transferred))
    np.testing.assert_allclose(history.amount_increment[:, k], expected, rtol=0, atol=1e-15)
    moved = np.abs(history.channel_transferred[-1]).sum(axis=0)
    assert np.all(moved[p.channel_active] > 0)
    heat = np.asarray(history.channel_dissipated_energy_pJ)
    assert np.all(np.diff(heat.sum(axis=1), axis=0) >= -1e-12)  # The family's tolerance.
    if arm == "release":
        before = value.times <= 0.00073
        assert not np.any(history.channel_transferred[before])
        assert np.all(value.observations.channel_availability[0] == 0)


@pytest.mark.parametrize("solver, tolerance", [(imex.EULER_ID, 2e-2), (imex.ARS222_ID, 1e-3)])
def test_imex_dissipation_and_work_ledgers_track_rk4(solver, tolerance, imex_runs):
    value, reference = imex_runs["clamped", solver], imex_runs["clamped", "rk4"]
    for key in surface_pump_v3.STATE_TYPE._fields:
        if key.endswith(("_dissipated_energy_pJ", "_work_pJ")):
            expected = np.sum(np.asarray(getattr(reference.final.state, key)))
            actual = np.sum(np.asarray(getattr(value.final.state, key)))
            assert abs(actual - expected) <= tolerance * abs(expected) + 3e-12, key


def test_imex_observed_order_against_rk4_with_channels(imex_runs):
    """Euler first and ARS(2,2,2) second order in Vm, channel flux and energy residual."""
    reference = imex_runs["clamped", "rk4"].observations
    for solver, order in ((imex.EULER_ID, 1), (imex.ARS222_ID, 2)):
        errors, energy = [[], []], []
        for dt in (1e-4, 5e-5, 2.5e-5):
            raw = fixtures.definition("clamped", solver=solver, backend=BACKEND)
            raw["execution"]["dt"] = dt
            value = imex_runs["clamped", solver] if dt == 1e-4 else run(parse_spec(raw))
            assert value.spec.execution.dt == dt
            for row, key in zip(errors, ("membrane_voltage_V", "channel_flux_fmol_s"), strict=True):
                observed, expected = getattr(value.observations, key), getattr(reference, key)
                row.append(float(np.max(np.abs(observed[-1] - expected[-1]))))
            energy.append(value.diagnostics["max_energy_balance_relative"])
        for values in (*errors, energy):
            rates = np.log2(np.asarray(values[:-1]) / np.asarray(values[1:]))
            assert np.all(rates > order - 0.25), (solver, values)


def test_explicit_stage_guard_refuses_open_sodium_channels():
    """A fully open NaV1.2 population is stiff: refused at 1 ms, admitted at 0.2 ms."""
    raw = fixtures.heredity_cells([fixtures.HEREDITY_STATES["D"][:4]], end_time=0.01)
    raw["model"]["channels"][1]["initial_gate"] = [1.0, 1.0]
    spec, state, p, control = initial(raw)
    rate = float(surface_pump_v3.membrane_rate(state, control, p, xp=np))
    assert 2500 < rate < 3000  # F^2/RT P c / (C/A) for 2.5e-7 m/s, 0.05 F/m^2.
    step = jax.jit(surface_pump_v3.checked_step)
    kept, valid = step(state, 1e-3, control, p, p.active)
    assert not valid
    for a, b in zip(kept, state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), b)
    _, valid = step(state, 2e-4, control, p, p.active)
    assert valid
    with pytest.raises(NumericalError):
        run(spec)
    # The pre-screen states are far from it (open Kir2.1 dominates at H, about
    # 28 /s): window currents admit millisecond steps.
    for name in ("H", "D"):
        _, state, p, control = initial(
            fixtures.heredity_cells([fixtures.HEREDITY_STATES[name][:4]], end_time=0.01)
        )
        assert 1e-3 * float(surface_pump_v3.membrane_rate(state, control, p, xp=np)) < 0.05


def test_restart_is_bitwise_and_invalid_channel_controls_refuse_the_step(tmp_path, imex_runs):
    value = imex_runs["release", imex.ARS222_ID]
    checkpoint = value.checkpoint_at(0.001)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, value.history, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    spec, state, p, control = initial(fixtures.definition("clamped", solver=imex.ARS222_ID))
    bad = control._replace(channel=np.full_like(control.channel, 1.01))
    kept, valid = jax.jit(surface_pump_v3.checked_step)(state, 1e-4, bad, p, p.active)
    assert not valid
    for a, b in zip(kept, state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), b)
    with pytest.raises(NumericalError):
        surface_pump_v3.check_values(
            state._replace(channel_transferred=state.channel_transferred + 0.01), spec
        )
    gate = state.channel_gate.copy()
    gate[:, -2] = 0.5  # A leak population has no gate state.
    with pytest.raises(NumericalError):
        surface_pump_v3.check_values(state._replace(channel_gate=gate), spec)


@pytest.mark.parametrize(
    "fault",
    [
        "retired_law_id",
        "unknown_law",
        "ion",
        "ion_ratio",
        "leak_gates",
        "gate_count",
        "patch",
        "missing_controls",
        "unknown_control",
        "duplicate_id",
        "capacity",
        "missing_channels",
        "hot",
    ],
)
def test_definition_errors_reject(fault):
    raw = fixtures.definition("clamped", solver=imex.ARS222_ID)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    channel = m["channels"][2]  # NaV1.2 on patch 2.
    if fault == "retired_law_id":  # Renamed to nav1p2_m3h_regularized@1 (stage B).
        channel["kinetic_law"] = "betse_nav1p2_m3h_regularized@1"
    elif fault == "unknown_law":
        channel["kinetic_law"] = "nav1p3_m3h_regularized@1"
    elif fault == "ion":
        channel["permeant_ions"] = [dict(species_id="K", relative_permeability=1.0)]
    elif fault == "ion_ratio":
        channel["permeant_ions"][0]["relative_permeability"] = 0.5
    elif fault == "leak_gates":
        m["channels"][6]["initial_gate"] = [0.5, 0.5]
    elif fault == "gate_count":
        channel["initial_gate"] = [0.5]
    elif fault == "patch":
        channel["membrane_id"] = "membrane_9"
    elif fault == "missing_controls":
        e["channel_controls"].pop()
    elif fault == "unknown_control":
        e["channel_controls"][0]["channel_id"] = "channel_99"
    elif fault == "duplicate_id":
        channel["id"] = "calcium_pump_0"
    elif fault == "capacity":
        x["channel_capacity"] = len(m["channels"]) - 1
    elif fault == "missing_channels":
        del m["channels"]
    else:
        m["temperature_K"] = 400.5
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_round_trip_configs_and_temperatures():
    root = Path(__file__).resolve().parents[2]
    for name in ("resolved_pump_tissue_channels.json", "resolved_pump_tissue_channels_cell.json"):
        spec = parse_spec(json.loads((root / "configs" / name).read_text()))
        assert get_model(spec.model) is surface_pump_v3 and spec.model.channels
        assert parse_spec(spec.to_dict()) == spec
    # Kv1.5 at 298 and 310 K: the gates have no temperature term (as the source
    # law); the constant-field flux and its affinity use the declared temperature.
    voltage = np.array([-0.05])
    values = []
    for temperature in (298.15, 310.0):
        spec, state, p, control = initial(
            fixtures.definition("clamped", solver=imex.ARS222_ID, temperature_K=temperature)
        )
        assert spec.model.temperature_K == temperature
        values.append(surface_pump_v3.readouts(state, control, p, xp=np))
        target, tau = surface_pump_v3.channel_kinetics(voltage, np.array([0]), xp=np)
        expected = voltage_gates.kinetics(voltage, xp=np)
        np.testing.assert_array_equal(target, expected[0])
        np.testing.assert_array_equal(tau, expected[1])
    flux = [v.channel_flux_fmol_s for v in values]
    assert scaled_difference(*flux) > 1e-3  # The fixed charge sets V; GHK moves with T.


def test_heredity_cell_holds_and_switches_the_prescreen_states():
    """Six independent cells at 1 ms: the two states, their stability, a write, an erase.

    The pre-screen's slow steady states (H -79.556 mV, D -21.518 mV) are
    stationary: rates vanish and Vm holds to 1 uV for 2 s. A 5 mV charge kick
    relaxes back with the pre-screen's fastest time constant (0.258 s H, 0.089 s
    D; dynamic Kir2.1 h gates lengthen H's by about 6%). A 9x Na-leak cue for
    0.3 s writes D's depolarized branch from H, and a 0.5 s NaV1.2 block erases
    D to the hyperpolarized branch; both persist after the cue.
    """
    states = fixtures.HEREDITY_STATES
    h, d = states["H"], states["D"]
    cells = [h[:4], d[:4], fixtures.kicked(h, 5), fixtures.kicked(d, -5), h[:4], d[:4]]
    times = [0.0, 0.1, 0.25, 0.35, 0.55, 1.0, 2.0]
    raw = fixtures.heredity_cells(
        cells,
        end_time=2.0,
        observation_times=times,
        gate_voltages=[h[0], d[0], h[0], d[0], h[0], d[0]],
    )
    m, e = raw["model"], raw["experiment"]
    cue = 9 * fixtures.HEREDITY_PERMEABILITY["Na"]
    m["channels"].append(fixtures.channel("cue_4", 4, NALEAK_LAW_ID, "Na", cue, 1.0, []))
    e["channel_controls"].append(
        dict(
            channel_id="cue_4",
            schedule=[
                dict(time=0.0, availability=0.0),
                dict(time=0.05, availability=1.0),
                dict(time=0.35, availability=0.0),
            ],
        )
    )
    blocked = next(g for g in e["channel_controls"] if g["channel_id"] == "nav_5")
    blocked["schedule"] = [
        dict(time=0.0, availability=1.0),
        dict(time=0.05, availability=0.0),
        dict(time=0.55, availability=1.0),
    ]
    raw["execution"]["channel_capacity"] += 1
    spec, state, p, control = initial(raw)
    law = surface_pump_v3.readouts(state, control, p, xp=np)
    assert law.valid
    assert np.all(np.abs(law.field.membrane_voltage_rate_V_s[:2]) < 1e-9)
    assert np.all(np.abs(law.derivative.amount_increment[:3, :2] / p.volume[:2]) < 1e-12)
    value = run(spec)
    d_ = value.diagnostics
    assert d_["max_energy_balance_relative"] <= surface_pump_v3.ENERGY_RTOL[imex.ARS222_ID]
    assert d_["max_global_charge_bound_ratio"] <= 1.0
    vm = np.asarray(value.observations.membrane_voltage_V)
    np.testing.assert_allclose(vm[:, 0], h[0], rtol=0, atol=1e-6)
    np.testing.assert_allclose(vm[:, 1], d[0], rtol=0, atol=1e-6)
    for cell, state_, sign in ((2, h, 1), (3, d, -1)):
        deviation = sign * (vm[:, cell] - state_[0])
        tau = 0.15 / np.log(deviation[1] / deviation[2])
        assert abs(tau / state_[4] - 1) < 0.15, (cell, tau)
        assert abs(vm[-1, cell] - state_[0]) < 5e-5
    assert -0.020 < vm[-1, 4] < -0.010 and vm[3, 4] > -0.010  # Written, held after release.
    assert vm[4, 5] < -0.070 and vm[-1, 5] < -0.085  # Erased, held after unblocking.


def test_cpu_and_gpu_trajectories_agree():
    """Channel fixture (IMEX) and a heredity cell at 1 ms agree on CPU and L4."""
    if not any(d.platform == "gpu" for d in jax.devices()):
        pytest.skip("Requires the L4 GPU environment")
    states = fixtures.HEREDITY_STATES
    definitions = (
        lambda backend: fixtures.definition("release", solver=imex.ARS222_ID, backend=backend),
        lambda backend: fixtures.heredity_cells(
            [states["H"][:4], fixtures.kicked(states["D"], -5)],
            end_time=0.25,
            backend=backend,
            gate_voltages=[states["H"][0], states["D"][0]],
        ),
    )
    for definition in definitions:
        values = {}
        for backend in ("cpu", "gpu"):
            value = run(parse_spec(definition(backend)))
            assert all(v.device.platform == backend for v in value.final.state)
            values[backend] = value
        for key in surface_pump_v3.STATE_TYPE._fields:
            a, b = (np.asarray(getattr(values[k].history, key)) for k in ("cpu", "gpu"))
            assert scaled_difference(a, b) <= 3e-12, key
