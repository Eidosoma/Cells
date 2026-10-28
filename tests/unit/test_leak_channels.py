"""Always-open source leaks, explicit control ownership and auxiliary clocks."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.processes import leak_channels as leaks
from validation.channels import leak_channels_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/channels/leak_channels_protocol.json").read_text())
TOL = PROTOCOL["tolerances"]
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
CLASSES, CODES = tuple(leaks.LEAK_LAWS.values()), tuple(leaks.LAW_CODES.values())
CODE_BY_NAME, NAME_BY_CODE = (
    dict(zip(CLASSES, CODES, strict=True)),
    dict(zip(CODES, CLASSES, strict=True)),
)


def evidence(name, record, arrays=None):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(path / ("leak-catalog-" + name + ".npz"), **arrays)
        (path / ("leak-catalog-" + name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )


def close(actual, expected, key="gate_atol"):
    np.testing.assert_allclose(actual, expected, rtol=TOL["relative"], atol=TOL[key])


def case(name, voltage=-0.080, initial=(0.2, 0.7)):
    return (
        np.asarray(initial, float)[:, None],
        np.array([voltage]),
        np.array([CODE_BY_NAME[name]], np.int64),
    )


def test_source_identity_ordered_metadata_and_standalone_padding():
    assert CLASSES == reference.CLASSES == tuple(PROTOCOL["classes"])
    assert leaks.LAW_CODES == PROTOCOL["law_codes"]
    assert leaks.PAD_CODE == PROTOCOL["padding_code"] == -1
    assert leaks.SPECIES == reference.SPECIES == tuple(PROTOCOL["species"])
    for law, name in leaks.LEAK_LAWS.items():
        assert leaks.LAW_PERMEABILITIES[law] == reference.ORDERED_PERMEABILITIES[name]
        assert leaks.GATE_POWERS[law] == (0, 0)
    assert leaks.LAW_PERMEABILITIES["betse_catleak_na_k@1"][-1] == ("Ca", 0.0)
    assert leaks.valid_codes(np.array([-1, *CODES]), xp=np)
    assert not leaks.valid_codes(np.array([0, 1, 31, 35]), xp=np)


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("voltage", [-0.120, -0.080, -0.020, 0.0, 0.040, 0.060])
def test_exact_constant_kinetics_opening_and_one_second_rhs(name, voltage):
    gates = np.array([[0.0, 0.2, 1.0], [0.0, 0.7, 1.0]])
    v, code, control = np.full(3, voltage), np.full(3, CODE_BY_NAME[name]), np.array([0, 0.3, 1.0])
    assert leaks.domain_valid(gates, v, code, control, xp=np)
    target, tau = leaks.kinetics(v, code, xp=np)
    derivative, opening = leaks.rhs(gates, v, code, xp=np), leaks.opening(gates, code, xp=np)
    stem = f"constant-{name}-{voltage:.9g}"
    evidence(
        stem,
        dict(status="actual_captured", name=name, voltage_V=voltage, availability=control),
        dict(target=target, tau_s=tau, derivative=derivative, opening=opening),
    )
    np.testing.assert_array_equal(target, 1)
    np.testing.assert_array_equal(tau, 1)
    np.testing.assert_array_equal(opening, 1)
    np.testing.assert_array_equal(leaks.initial_gates(v, code, xp=np), target)
    for i in range(3):
        close(
            derivative[:, i], reference.rhs(gates[:, i].tolist(), voltage, name), "rate_atol_per_s"
        )
    evidence(stem, dict(status="passed", name=name, voltage_V=voltage, voltage_dependent=False))


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("availability", [0.0, 0.25, 1.0])
def test_one_population_availability_scales_all_routes_and_preserves_zero_ca(name, availability):
    gates, v, code = case(name)
    assert leaks.permeability_domain_valid(code, availability, xp=np)
    assert leaks.domain_valid(gates, v, code, availability, xp=np)
    actual = leaks.permeability_weights(code, availability, xp=np)[:, 0]
    expected = reference.permeability_weights(name, availability)
    np.testing.assert_array_equal(actual, expected)
    if name == "CatLeak":
        assert actual[1] == actual[2] and actual[3] == 0
    if name == "CatLeak2":
        assert actual[1] == actual[2] == actual[3]
    if availability == 0:
        assert not np.any(actual)
        close(
            leaks.rhs(gates, v, code, xp=np)[:, 0],
            reference.rhs(gates[:, 0].tolist(), -0.080, name),
            "rate_atol_per_s",
        )


def test_independent_population_control_does_not_close_another_population():
    code = np.array([32, 33, 34, -1])
    control = np.array([0.8, 0.6, 0.7, 0.0])
    first = leaks.permeability_weights(code, control, xp=np)
    control[1] = 0
    changed = leaks.permeability_weights(code, control, xp=np)
    np.testing.assert_array_equal(first[:, [0, 2, 3]], changed[:, [0, 2, 3]])
    assert np.all(changed[:, 1] == 0) and first[1, 1] == first[2, 1] == 0.6
    evidence(
        "ownership",
        dict(status="passed", species=leaks.SPECIES, zero_ca_preserved=True),
        dict(first=first, changed=changed),
    )


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("initial", [(0.2, 0.7), (0.8, 0.3)])
def test_exact_auxiliary_recovery_spans_twelve_seconds_without_voltage_gating(name, initial):
    rows = []
    for time in (0.0, 0.1, 1.0, 4.0, 8.0, 12.0):
        exact = reference.relaxation(initial, -0.080, name, time)
        gates, v, code = case(name, initial=exact)
        assert leaks.domain_valid(gates, v, code, 0.0, xp=np)
        close(
            leaks.rhs(gates, v, code, xp=np)[:, 0],
            reference.rhs(exact, -0.080, name),
            "rate_atol_per_s",
        )
        assert leaks.opening(gates, code, xp=np)[0] == 1.0
        assert np.all(leaks.permeability_weights(code, 0.0, xp=np) == 0)
        rows.append(dict(time_s=time, gates=exact))
    assert max(abs(g - 1) for g in rows[-1]["gates"]) <= np.exp(-12) + 1e-13
    evidence(
        f"auxiliary-exact-{name}-{initial[0]}",
        dict(
            status="passed",
            name=name,
            initial=initial,
            duration_s=12.0,
            conductance_blocked=True,
            opening_constant=True,
            rows=rows,
        ),
    )


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("gate", [0, 1], ids=["m", "h"])
def test_continuous_auxiliary_clock_has_fourth_order_refinement_over_twelve_tau(name, gate):
    initial, v, code = case(name, initial=(1.0, 1.0))
    initial[gate, 0] = 0.2
    errors, samples = [], {}
    for steps in PROTOCOL["auxiliary_recovery"]["continuous_refinement_steps"]:
        state, dt, error, saved = initial.copy(), 12.0 / steps, 0.0, [initial.copy()]
        for i in range(steps):
            a = leaks.rhs(state, v, code, xp=np)
            b = leaks.rhs(state + dt * a / 2, v, code, xp=np)
            c = leaks.rhs(state + dt * b / 2, v, code, xp=np)
            d = leaks.rhs(state + dt * c, v, code, xp=np)
            state = state + dt * (a + 2 * b + 2 * c + d) / 6
            exact = reference.relaxation(initial[:, 0].tolist(), -0.080, name, (i + 1) * dt)
            error = max(error, abs(state[gate, 0] - exact[gate]))
            assert leaks.domain_valid(state, v, code, 0.0, xp=np)
            assert leaks.opening(state, code, xp=np)[0] == 1
            saved.append(state.copy())
        errors.append(error)
        samples[str(steps)] = np.stack(saved)
    stem = f"auxiliary-refine-{name}-{gate}"
    evidence(
        stem, dict(status="captured", name=name, gate=gate, duration_s=12.0, errors=errors), samples
    )
    assert errors[2] < errors[1] < errors[0]
    order = float(np.log2(errors[1] / errors[2]))
    assert 3.7 <= order <= 4.6
    evidence(
        stem,
        dict(
            status="passed",
            name=name,
            gate=gate,
            duration_s=12.0,
            errors=errors,
            observed_order=order,
        ),
    )


def test_actual_voltage_gate_law_and_availability_world_broadcasts():
    codes = np.array([32, 33, 34, -1])
    worlds = np.stack((codes, np.r_[np.roll(codes[:3], 1), -1], np.r_[codes[:3][::-1], -1]))[
        None, :, :
    ]
    v = np.array([[-0.080, 0.0, 0.040, 0.0], [-0.100, -0.020, 0.060, 0.0]])[:, None, :]
    gates = np.stack(
        [np.stack((np.full(4, 0.2 + 0.1 * j), np.full(4, 0.7 - 0.1 * j))) for j in range(3)]
    )[None, :, :, :]
    gates[..., -1] = 0
    control = np.array([[1.0, 0.5, 0.0, 0.0], [0.3, 1.0, 0.8, 0.0]])[:, None, :]
    assert leaks.domain_valid(gates, v, worlds, control, xp=np)
    assert leaks.permeability_domain_valid(worlds, control, xp=np)
    target, tau = leaks.kinetics(v, worlds, xp=np)
    derivative, weights = (
        leaks.rhs(gates, v, worlds, xp=np),
        leaks.permeability_weights(worlds, control, xp=np),
    )
    assert target.shape == tau.shape == derivative.shape == (2, 3, 2, 4)
    assert weights.shape == (2, 3, 4, 4)
    evidence(
        "worlds",
        dict(status="actual_captured", independent_worlds=6),
        dict(target=target, tau_s=tau, derivative=derivative, weights=weights),
    )
    for i in range(2):
        for j in range(3):
            for k in range(3):
                name = NAME_BY_CODE[int(worlds[0, j, k])]
                close(
                    derivative[i, j, :, k],
                    reference.rhs(gates[0, j, :, k].tolist(), float(v[i, 0, k]), name),
                    "rate_atol_per_s",
                )
                np.testing.assert_array_equal(
                    weights[i, j, :, k],
                    reference.permeability_weights(name, float(control[i, 0, k])),
                )
    order = np.array([2, 0, 1, 3])
    np.testing.assert_array_equal(
        leaks.rhs(gates[..., order], v[..., order], worlds[..., order], xp=np),
        derivative[..., order],
    )
    np.testing.assert_array_equal(
        leaks.permeability_weights(worlds[..., order], control[..., order], xp=np),
        weights[..., order],
    )
    assert not np.any(target[..., -1]) and not np.any(weights[..., -1])
    evidence("worlds", dict(status="passed", independent_worlds=6, population_reorder="exact"))


@pytest.mark.parametrize("control", [-0.1, 1.1, np.nan, np.inf, True, np.ones(3)])
def test_invalid_controls_rejected_by_both_public_predicates(control):
    gates, v, codes = case("CatLeak")
    assert not leaks.permeability_domain_valid(codes, control, xp=np)
    assert not leaks.domain_valid(gates, v, codes, control, xp=np)


@pytest.mark.parametrize(
    "failure",
    [
        "voltage_low",
        "voltage_high",
        "voltage_nan",
        "gate_low",
        "gate_high",
        "gate_nan_blocked",
        "bad_code",
        "float_code",
        "bool_code",
        "pad_voltage",
        "pad_gate",
        "pad_control",
        "bad_gate_axis",
        "bool_gates",
    ],
)
def test_strict_auxiliary_domains_and_padding_even_when_blocked(failure):
    gates, voltage, codes, control = (
        np.array([[0.2, 0], [0.7, 0]]),
        np.array([-0.080, 0.0]),
        np.array([33, -1]),
        np.array([1.0, 0.0]),
    )
    if failure == "voltage_low":
        voltage[0] = -0.121
    elif failure == "voltage_high":
        voltage[0] = 0.061
    elif failure == "voltage_nan":
        voltage[0] = np.nan
    elif failure == "gate_low":
        gates[0, 0] = -0.1
    elif failure == "gate_high":
        gates[1, 0] = 1.1
    elif failure == "gate_nan_blocked":
        gates[1, 0] = np.nan
        control[0] = 0
    elif failure == "bad_code":
        codes[0] = 0
    elif failure == "float_code":
        codes = codes.astype(float)
    elif failure == "bool_code":
        codes = codes.astype(bool)
    elif failure == "pad_voltage":
        voltage[1] = 0.01
    elif failure == "pad_gate":
        gates[0, 1] = 0.1
    elif failure == "pad_control":
        control[1] = 1
    elif failure == "bad_gate_axis":
        gates = np.zeros((3, 2))
    else:
        gates = gates.astype(bool)
    assert not leaks.domain_valid(gates, voltage, codes, control, xp=np)


def test_empty_populations_still_reject_nonfinite_control_and_default_padding_is_neutral():
    for n in (0, 3):
        voltage, gates, codes = np.zeros((2, n)), np.zeros((2, 2, n)), np.full(n, -1, np.int64)
        control = np.zeros(n)
        assert leaks.domain_valid(gates, voltage, codes, xp=np)
        assert leaks.domain_valid(gates, voltage, codes, control, xp=np)
        assert leaks.permeability_domain_valid(codes, control, xp=np)
        assert not np.any(leaks.rhs(gates, voltage, codes, xp=np))
        assert not np.any(leaks.opening(gates, codes, xp=np))
        assert not np.any(leaks.permeability_weights(codes, control, xp=np))
    assert not leaks.permeability_domain_valid(np.zeros(0, np.int64), np.nan, xp=np)
    assert not leaks.domain_valid(
        np.zeros((2, 0)), np.zeros(0), np.zeros(0, np.int64), np.nan, xp=np
    )
    assert leaks.domain_valid(*case("ClLeak"), xp=np)
    evidence(
        "strict-empty-controls",
        dict(status="passed", empty_nan_rejected=True, default_padding_neutral=True),
    )


def test_jax_eager_jit_vmap_weights_rhs_and_strict_control_rejection():
    import jax
    import jax.numpy as jnp

    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    codes = np.array([32, 33, 34, -1])
    voltage = np.array([[-0.080, 0.0, 0.040, 0.0], [-0.100, -0.020, 0.060, 0.0]])
    gates = np.array([[0.2, 0.3, 0.4, 0.0], [0.7, 0.6, 0.5, 0.0]])
    control = np.array([[1.0, 0.4, 0.7, 0.0], [0.0, 0.8, 1.0, 0.0]])
    expected = leaks.kinetics(voltage, codes, xp=np)
    for actual in (
        jax.jit(leaks.kinetics)(voltage, codes),
        jax.jit(jax.vmap(lambda v: leaks.kinetics(v, codes)))(voltage),
        leaks.kinetics(jnp.asarray(voltage), jnp.asarray(codes)),
    ):
        np.testing.assert_array_equal(np.asarray(actual[0]), expected[0])
        np.testing.assert_array_equal(np.asarray(actual[1]), expected[1])
    close(
        np.asarray(jax.jit(leaks.rhs)(gates, voltage, codes)),
        leaks.rhs(gates, voltage, codes, xp=np),
        "rate_atol_per_s",
    )
    np.testing.assert_array_equal(
        np.asarray(jax.jit(leaks.opening)(gates, codes)), leaks.opening(gates, codes, xp=np)
    )
    np.testing.assert_array_equal(
        np.asarray(jax.jit(leaks.permeability_weights)(codes, control)),
        leaks.permeability_weights(codes, control, xp=np),
    )
    valid = jax.jit(leaks.domain_valid)
    assert bool(valid(gates, voltage, codes, control))
    bad = gates.copy()
    bad[1, 0] = np.nan
    assert not bool(valid(bad, voltage, codes, np.zeros_like(control)))
    bad_control = control.copy()
    bad_control[0, -1] = 1
    assert not bool(valid(gates, voltage, codes, bad_control))
    assert not bool(jax.jit(leaks.permeability_domain_valid)(np.full(0, -1, np.int64), np.nan))
    assert not bool(valid(np.zeros((2, 0)), np.zeros(0), np.full(0, -1, np.int64), np.nan))
    evidence(
        "jax-arrays",
        dict(status="passed", eager=True, jit=True, vmap=True, strict_empty_controls=True),
    )


def test_jax_zero_gating_sensitivity_and_one_control_per_route_derivatives():
    import jax
    import jax.numpy as jnp

    codes = np.array([32, 33, 34, -1])
    voltage = np.array([-0.080, -0.020, 0.040, 0.0])
    gates = np.array([[0.2, 0.3, 0.4, 0.0], [0.7, 0.6, 0.5, 0.0]])
    dv = jax.jit(jax.jacfwd(lambda v: jnp.concatenate(leaks.kinetics(v, codes), axis=-2)))(voltage)
    dg = jax.jit(jax.jacfwd(lambda g: leaks.opening(g, codes)))(gates)
    np.testing.assert_array_equal(np.asarray(dv), 0)
    np.testing.assert_array_equal(np.asarray(dg), 0)
    decay = np.asarray(jax.jit(jax.jacfwd(lambda g: leaks.rhs(g, voltage, codes)))(gates))
    expected_decay = np.zeros((2, 4, 2, 4))
    for gate in range(2):
        for population in range(3):
            expected_decay[gate, population, gate, population] = -1
    np.testing.assert_array_equal(decay, expected_decay)
    control = np.array([0.8, 0.6, 0.7, 0.0])
    derivative = np.asarray(
        jax.jit(jax.jacfwd(lambda a: leaks.permeability_weights(codes, a)))(control)
    )
    expected = np.zeros((4, 4, 4))
    for p, name in enumerate(CLASSES):
        expected[:, p, p] = reference.permeability_weights(name, 1.0)
    np.testing.assert_array_equal(derivative, expected)
    assert derivative[3, 1, 1] == 0 and derivative[3, 2, 2] == 1
    evidence(
        "jax-derivatives",
        dict(
            status="passed",
            voltage_gating_derivative_zero=True,
            auxiliary_decay_per_second=-1,
            independent_population_controls=True,
            zero_catleak_ca_derivative=True,
        ),
    )
