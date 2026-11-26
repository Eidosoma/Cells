"""cells.model.resolved_pump_tissue@3: gates, equivalence and the IMEX split.

A shard of the former test_surface_pump_v3.py: the exponential gate update is bounded,
exact and second order; with no channels the identity reproduces @2; the RK4 law
reproduces cells.model.resolved_tissue@8's catalog; single-patch currents against it; the explicit
and implicit parts sum to the law.
"""

import os

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import run
from cells.laws.channels import sodium_channels
from cells.models import surface_kinetic, surface_pump_v2, surface_pump_v3
from cells.numerics import exponential_gates as gates
from cells.numerics import surface_imex as imex
from cells.registry.models import get_model
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


@pytest.fixture(autouse=True)
def clear_compiled_programs():
    """Release the compiled programs after every test: these tests compile many programs
    and one process otherwise keeps them all (the unsplit file hit a 4 GB cap in tier 3)."""
    yield
    jax.clear_caches()


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
def test_without_channels_reproduces_resolved_pump_tissue_2(solver, monkeypatch):
    """Same states and observations as @2; the channel terms are exact zeros.

    Observed bitwise on CPU; the bound is the requested 1e-13 of each array's
    magnitude, which admits a compiled reordering. Fix (A) (D273) is @3's alone:
    this world's junction joins two capacitor components and one floats, so under
    ARS(2,2,2) @3's explicit stage rates read each stage's quasi-static potentials
    and @2's do not (1.2e-7 of amount_increment here, first order in dt). That arm
    asserts the switch is on for this world, then checks the identity with it off.
    """
    spec = parse_spec(fixtures.definition("release", solver=solver, channels=False))
    if solver == imex.ARS222_ID:
        assert surface_pump_v3.structure(spec.model).crossing_junctions == ("junction_0",)
        monkeypatch.setattr(surface_pump_v3, "crossing_junctions", lambda model: ())
    model = get_model(spec.model)
    assert isinstance(model, surface_pump_v3.InnerImplementation)
    assert model.structure == surface_pump_v3.structure(spec.model)
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

    cells.model.resolved_tissue@8 keeps two unused gates for its leak laws; those rows are
    not compared. Its dense field agrees with the factored one to 1e-12.
    """
    raw = fixtures.definition("clamped", calcium=False)
    reference = fixtures.catalog_reference(raw)
    dt = 1.25e-6
    for definition in (raw, reference):
        definition["execution"].update(dt=dt, max_steps=1024)
        definition["experiment"].update(end_time=5e-4, observation_times=[0.0, 200 * dt, 5e-4])
    a, b = run(parse_spec(raw)), run(parse_spec(reference))
    assert get_model(b.spec.model).MODEL_ID == "cells.model.resolved_tissue@8"
    assert type(b.final.layout) is surface_kinetic.CATALOG_LAYOUT_TYPE
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

    The reference is cells.model.resolved_tissue@8 (RK4 at its 1.25 us bound). Each
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
