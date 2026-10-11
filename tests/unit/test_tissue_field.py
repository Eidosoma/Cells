"""Cross-region current closure: independent roots, local charge and CPU/L4 parity."""

import copy
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.numerics import extracellular_field as outside
from cells.numerics import tissue_field as model
from validation.tissue import fixtures, reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
RTOL = 3e-10
ATOL = {
    "potential_V": 3e-13,
    "cell_potential_V": 3e-13,
    "face_flux_fmol_per_s": 3e-13,
    "face_delta_mu_J_per_mol": 3e-8,
    "face_current_A": 1e-23,
    "face_dissipation_rate_pJ_per_s": 3e-12,
    "junction_voltage_V": 3e-13,
    "junction_flux_fmol_per_s": 3e-13,
    "junction_delta_mu_J_per_mol": 3e-8,
    "junction_current_A": 1e-23,
    "junction_dissipation_rate_pJ_per_s": 3e-12,
}


def evidence(name, result):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


def compare(a, b):
    for name, atol in ATOL.items():
        np.testing.assert_allclose(a[name], b[name], rtol=RTOL, atol=atol, err_msg=name)


@pytest.fixture(scope="module")
def computed():
    jax.config.update("jax_enable_x64", True)
    device = jax.devices(BACKEND)[0]
    compiled = jax.jit(model.solve)
    result = {}
    for name in fixtures.CASES:
        values = compiled(*jax.device_put(fixtures.arrays(fixtures.definition(name)), device))
        jax.block_until_ready(values)
        assert all(v.device.platform == BACKEND for v in jax.tree.leaves(values))
        result[name] = jax.tree.map(np.asarray, values)
    # Every array signature used by this suite's single-world solver is now warm.
    # Other test functions compile additional kernels, so no whole-suite warm
    # interval is inferred from this timestamp.
    evidence(
        "field-kernels-ready", {"time": time.time(), "scope": "single-world field signatures only"}
    )
    return result


@pytest.mark.parametrize("name", fixtures.CASES)
def test_independent_roots_and_physical_accounting(name, computed):
    raw = fixtures.definition(name)
    expected = reference.solve(raw)
    actual = computed[name]
    assert actual.converged and actual.current_normalized <= 1
    compare(actual._asdict(), expected)
    rates = reference.power_and_charge_rates(raw, actual._asdict())
    np.testing.assert_allclose(rates["material_rate_fmol_per_s"], 0, rtol=0, atol=1e-15)
    np.testing.assert_allclose(rates["component_charge_rate_A"], 0, rtol=0, atol=2e-23)
    assert abs(rates["energy_rate_residual_pJ_per_s"]) <= 1e-10
    for key in ("face_dissipation_rate_pJ_per_s", "junction_dissipation_rate_pJ_per_s"):
        assert np.min(getattr(actual, key), initial=0) >= -1e-15
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        np.savez_compressed(root / (name + ".npz"), **actual._asdict())
    evidence(
        name,
        {
            "status": "passed",
            "inputs": raw,
            "iterations": int(actual.iterations),
            "current_normalized": float(actual.current_normalized),
            "energy_rate_residual_pJ_per_s": rates["energy_rate_residual_pJ_per_s"],
            "max_component_charge_rate_A": float(np.max(np.abs(rates["component_charge_rate_A"]))),
            "physical_fields_compared": list(ATOL),
        },
    )


def test_two_region_exact_resistor_limit_and_reversal(computed):
    raw = fixtures.definition("equal")
    p = raw["layout"]
    z = np.asarray(p["valence"])
    factor = reference.F**2 / (reference.R * p["temperature"])
    gj = factor * np.sum(
        z * z * np.asarray(p["junction_permeability"]) * np.asarray(raw["ci"])[:, :1]
    )
    gj *= p["junction_area"][0] * raw["gate"][0]
    gf = factor * np.sum(z * z * np.asarray(p["face_factor"]) * np.asarray(raw["co"])[:, :1])
    delta_vm = raw["membrane_voltage"][0] - raw["membrane_voltage"][1]
    expected_phi = gj / (gf + gj) * delta_vm
    value = computed["equal"]
    np.testing.assert_allclose(value.potential_V, [0, expected_phi], rtol=3e-12, atol=3e-15)
    np.testing.assert_allclose(
        value.junction_current_A, [gf * gj / (gf + gj) * delta_vm], rtol=3e-12, atol=1e-25
    )
    np.testing.assert_allclose(
        value.face_current_A, -value.junction_current_A, rtol=3e-12, atol=1e-25
    )
    np.testing.assert_allclose(
        computed["reverse"].junction_current_A, -value.junction_current_A, rtol=3e-12, atol=1e-25
    )
    assert not np.any(computed["zero_drive"].face_flux_fmol_per_s)
    assert not np.any(computed["zero_drive"].junction_flux_fmol_per_s)


def test_blocked_junction_keeps_diffusion_potential_and_gate(computed):
    raw = fixtures.definition("blocked")
    before = copy.deepcopy(raw)
    assert not np.any(computed["blocked"].junction_flux_fmol_per_s)
    assert np.any(np.abs(computed["blocked"].potential_V) > 1e-6)
    model.solve(*fixtures.arrays(raw), xp=np)
    assert raw == before


def test_same_region_reduces_to_existing_field_and_junction_law(computed):
    raw = fixtures.definition("same_region")
    ci, co, voltage, gate, availability, p = fixtures.arrays(raw)
    legacy = SimpleNamespace(**p._asdict(), senders=p.face_senders, receivers=p.face_receivers)
    old = outside.solve(co, legacy, xp=np)
    np.testing.assert_allclose(
        computed["same_region"].potential_V, old.potential_V, rtol=3e-12, atol=3e-15
    )
    np.testing.assert_allclose(
        computed["same_region"].face_flux_fmol_per_s, old.flux_fmol_per_s, rtol=3e-12, atol=3e-15
    )
    np.testing.assert_allclose(
        computed["same_region"].junction_voltage_V, [voltage[0] - voltage[1]], rtol=0, atol=3e-17
    )


def test_padding_does_not_ground_or_transport(computed):
    for key in ATOL:
        full, padded = getattr(computed["triangle"], key), getattr(computed["triangle_padded"], key)
        np.testing.assert_allclose(padded[..., : full.shape[-1]], full, rtol=3e-12, atol=ATOL[key])
        assert not np.any(padded[..., full.shape[-1] :])


def test_gauge_changes_only_absolute_potentials(computed):
    raw = fixtures.definition("triangle")
    raw["layout"]["gauge_mask"] = [False, False, True]
    changed = model.solve(*fixtures.arrays(raw), xp=np)
    original = computed["triangle"]
    assert changed.converged
    for key in ATOL:
        expected = getattr(original, key)
        if key in ("potential_V", "cell_potential_V"):
            expected = expected - original.potential_V[2]
        np.testing.assert_allclose(getattr(changed, key), expected, rtol=RTOL, atol=ATOL[key])


def test_outside_only_solution_fails_cross_region_current_balance(computed):
    raw = fixtures.definition("gradient")
    _, co, _, _, _, p = fixtures.arrays(raw)
    legacy = SimpleNamespace(**p._asdict(), senders=p.face_senders, receivers=p.face_receivers)
    old = outside.solve(co, legacy, xp=np)
    wrong = reference.evaluate(raw, old.potential_V)
    assert np.max(np.abs(wrong["current_residual_A"])) > 1e-14
    assert np.max(np.abs(computed["gradient"].current_residual_A)) < 2e-23


@pytest.mark.parametrize(
    "case",
    [
        "no_gauge",
        "two_gauges",
        "broken_return",
        "self_edge",
        "duplicate_edge",
        "wrong_owner",
        "negative_permeability",
        "floating_owner",
        "noninteger_index",
    ],
)
def test_invalid_layout_is_rejected(case):
    raw = fixtures.definition("triangle")
    p = raw["layout"]
    if case == "no_gauge":
        p["gauge_mask"] = [False] * 3
    elif case == "two_gauges":
        p["gauge_mask"] = [True, True, False]
    elif case == "broken_return":
        p["face_active"] = [False] * 3
        p["face_factor"] = [[0.0] * 3] * 3
    elif case == "self_edge":
        p["junction_receivers"][0] = 0
    elif case == "duplicate_edge":
        p["junction_senders"][2], p["junction_receivers"][2] = 1, 0
    elif case == "wrong_owner":
        p["cell_outside"][0] = 99
    elif case == "negative_permeability":
        p["junction_permeability"][0][0] = -1
    elif case == "floating_owner":
        p["extracellular_active"][2] = False
    else:
        p["cell_outside"] = [0.0, 1.0, 2.0]
    with pytest.raises(ValueError):
        fixtures.arrays(raw)


def test_iteration_exhaustion_is_a_failure_without_state_repair():
    args = fixtures.arrays(fixtures.definition("gradient"))
    original = jax.tree.map(lambda v: v.copy(), args)
    result = model.solve(*args, xp=np, max_iterations=0)
    assert not result.converged and result.current_normalized > 1
    for a, b in zip(jax.tree.leaves(args), jax.tree.leaves(original), strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize(
    "kind", ["negative_concentration", "negative_gate", "bad_availability", "excess_voltage"]
)
def test_invalid_physical_inputs_never_pass(kind):
    raw = fixtures.definition()
    if kind == "negative_concentration":
        raw["ci"][0][0] = -1
    elif kind == "negative_gate":
        raw["gate"][0] = -0.1
    elif kind == "bad_availability":
        raw["availability"][0] = 1.1
    else:
        raw["membrane_voltage"][0] = 2.0
    with np.errstate(all="ignore"):
        value = model.solve(*fixtures.arrays(raw), xp=np)
    assert not value.converged


def test_analytic_newton_jacobian_matches_autodifferentiation():
    jax.config.update("jax_enable_x64", True)
    from cells.processes.electrochemistry import bernoulli

    points = jnp.asarray([-40, -1, -1e-4, -1e-6, 0, 1e-6, 1e-4, 1, 40.0])
    device = jax.devices(BACKEND)[0]
    points = jax.device_put(points, device)
    automatic = jax.vmap(jax.grad(bernoulli))(points)
    analytic = model._bernoulli_derivative(points, xp=jnp)
    np.testing.assert_allclose(analytic, automatic, rtol=1e-8, atol=1e-11)


def test_batched_worlds_match_scalar_without_sharing_state(computed):
    device = jax.devices(BACKEND)[0]
    args = fixtures.arrays(fixtures.definition("gradient"))
    inputs = jax.device_put(jax.tree.map(lambda v: np.stack([v, v]), args), device)
    result = jax.jit(jax.vmap(model.solve))(*inputs)
    jax.block_until_ready(result)
    assert np.all(np.asarray(result.converged))
    for key in ATOL:
        for row in np.asarray(getattr(result, key)):
            np.testing.assert_allclose(
                row, getattr(computed["gradient"], key), rtol=RTOL, atol=ATOL[key]
            )


def test_cpu_gpu_saved_physical_fields(computed):
    if BACKEND == "cpu":
        pytest.skip("Requires the following L4 phase and saved CPU evidence")
    assert EVIDENCE, "GPU qualification requires frozen CPU evidence"
    count = 0
    for name, value in computed.items():
        with np.load(Path(EVIDENCE) / "cpu" / (name + ".npz"), allow_pickle=False) as saved:
            assert saved["converged"] and value.converged
            compare(value._asdict(), saved)
            count += sum(saved[key].size for key in ATOL)
    evidence(
        "cpu-gpu",
        {
            "status": "passed",
            "physical_scalars": count,
            "rtol": RTOL,
            "atol_by_field": ATOL,
            "scope": "Physical fields; each backend independently passes its residual bound",
        },
    )
