"""Thirteen ML laws: real kinetic clocks and explicitly absent algebraic state."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.processes import morris_lecar_channels as ml
from validation.channels import morris_lecar_channels_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "validation/channels/morris_lecar_channels_protocol.json").read_text()
)
TOL = PROTOCOL["tolerances"]
CLASSES = tuple(ml.MORRIS_LECAR_LAWS.values())
CODES = tuple(ml.LAW_CODES.values())
CODE_BY_NAME = dict(zip(CLASSES, CODES, strict=True))
NAME_BY_CODE = dict(zip(CODES, CLASSES, strict=True))
KINETIC = tuple(name for name in CLASSES if name in reference.KINETIC)
ALGEBRAIC = tuple(name for name in CLASSES if name not in reference.KINETIC)


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(directory) / "cpu"
        path.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(path / ("morris-lecar-" + name + ".npz"), **arrays)
        (path / ("morris-lecar-" + name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )


def close(actual, expected, key="opening_atol"):
    np.testing.assert_allclose(actual, expected, rtol=TOL["relative"], atol=TOL[key])


def case(name, voltage, state=None):
    if state is None:
        state = 0.2 if name in reference.KINETIC else 0.0
    return np.array([state]), np.array([voltage]), np.array([CODE_BY_NAME[name]], np.int64)


def test_codebook_species_state_counts_and_no_redefinition_of_prior_codes():
    assert CLASSES == reference.CLASSES == tuple(PROTOCOL["classes"])
    assert ml.LAW_CODES == PROTOCOL["law_codes"] and CODES == tuple(range(40, 53))
    assert ml.PAD_CODE == -1 and ml.valid_codes(np.array([-1, *CODES]), xp=np)
    assert not ml.valid_codes(np.array([0, 39, 53]), xp=np)
    for law, name in ml.MORRIS_LECAR_LAWS.items():
        assert ml.STATE_COUNTS[law] == int(name in reference.KINETIC)
        assert ml.LAW_PERMEABILITIES[law] == reference.PERMEABILITIES[name]
    assert sum(ml.STATE_COUNTS.values()) == 5 and len(ALGEBRAIC) == 8


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("voltage", [-0.120, -0.080, -0.050, -0.020, 0.0, 0.060])
def test_decimal_target_real_tau_initial_state_opening_and_rhs(name, voltage):
    m, v, codes = case(name, voltage)
    assert ml.domain_valid(m, v, codes, xp=np)
    target, tau = ml.kinetics(v, codes, xp=np)
    expected = reference.kinetics(voltage, name)
    close(target, expected["target"])
    close(tau, expected["tau_s"], "tau_atol_s")
    close(ml.opening(m, v, codes, xp=np), reference.opening(float(m[0]), voltage, name))
    close(ml.rhs(m, v, codes, xp=np), reference.rhs(float(m[0]), voltage, name), "rhs_atol_per_s")
    initial = ml.initial_state(v, codes, xp=np)
    if name in reference.KINETIC:
        np.testing.assert_array_equal(initial, target)
    else:
        np.testing.assert_array_equal(initial, 0)
        np.testing.assert_array_equal(tau, 0)
    close(ml.opening(initial, v, codes, xp=np), expected["target"])
    evidence(
        f"ordinary-{name}-{voltage:.9g}",
        dict(
            status="passed",
            name=name,
            voltage_V=voltage,
            state_count=int(name in reference.KINETIC),
            reference=expected,
        ),
        dict(target=target, tau_s=tau, initial_state=initial),
    )


TRANSITIONS = tuple(
    (name, float(reference.PARAMETERS[name][0]) / 1000 if name != "Kir_ML" else -0.100)
    for name in CLASSES
)


@pytest.mark.parametrize("name,voltage", TRANSITIONS)
def test_smooth_midpoints_and_adjacent_binary_voltages(name, voltage):
    v = np.array(
        [
            voltage,
            np.nextafter(voltage, -np.inf),
            np.nextafter(voltage, np.inf),
            voltage - 1e-10,
            voltage + 1e-10,
        ]
    )
    codes = np.full(v.size, CODE_BY_NAME[name], np.int64)
    with np.errstate(all="raise"):
        target, tau = ml.kinetics(v, codes, xp=np)
    expected = [reference.kinetics(float(value), name) for value in v]
    close(target, [item["target"] for item in expected])
    close(tau, [item["tau_s"] for item in expected], "tau_atol_s")


def test_effective_phi_clock_slow_ratio_and_unused_algebraic_raw_taus():
    for name in KINETIC:
        midpoint = float(reference.PARAMETERS[name][0]) / 1000
        _, v, code = case(name, midpoint)
        tau = ml.kinetics(v, code, xp=np)[1][0]
        close(tau, 1 / (1.32 if name == "Kv1p5S_ML" else 66), "tau_atol_s")
    v = np.array([-0.080, 0.0, 0.060])
    fast = ml.kinetics(v, np.full(3, 43), xp=np)
    slow = ml.kinetics(v, np.full(3, 44), xp=np)
    np.testing.assert_array_equal(fast[0], slow[0])
    close(slow[1], 50 * fast[1], "tau_atol_s")
    for name in ALGEBRAIC:
        value = reference.kinetics(-0.080, name)
        assert value["raw_tau"] == 1 and value["tau_s"] == 0
    evidence(
        "clocks",
        dict(
            status="passed",
            five_dynamic=True,
            eight_algebraic=True,
            fast_peak_tau_s=1 / 66,
            slow_peak_tau_s=1 / 1.32,
            slow_ratio=50,
            algebraic_clock=None,
        ),
    )


@pytest.mark.parametrize("name", ALGEBRAIC)
def test_instantaneous_voltage_steps_have_no_state_rhs_or_relaxation_clock(name):
    v = np.array([-0.080, 0.0, -0.020, -0.080])
    code = np.full(4, CODE_BY_NAME[name])
    state = np.zeros(4)
    expected = [reference.kinetics(float(value), name)["target"] for value in v]
    close(ml.opening(state, v, code, xp=np), expected)
    np.testing.assert_array_equal(ml.rhs(state, v, code, xp=np), 0)
    np.testing.assert_array_equal(ml.kinetics(v, code, xp=np)[1], 0)
    assert ml.domain_valid(state, v, code, xp=np)
    assert not ml.domain_valid(np.full(4, 0.2), v, code, xp=np)
    with pytest.raises(ValueError, match="no dynamic state"):
        reference.relaxation(0.0, -0.080, name, 1.0)
    evidence(
        "instantaneous-" + name,
        dict(
            status="passed",
            name=name,
            voltage_steps_V=v,
            opening=expected,
            state_count=0,
            native_dt_zero_case_captured_separately=True,
        ),
    )


def test_source_hcn_sign_mixed_ions_and_kir_sech_are_not_silently_changed():
    v = np.array([-0.120, -0.099, -0.080, 0.0, 0.060])
    for code in (51, 52):
        target, tau = ml.kinetics(v, np.full(5, code), xp=np)
        assert np.all(np.diff(target) > 0) and target[1] == 0.5
        assert np.all(tau == 0)
    target = ml.kinetics(np.array([-0.100]), np.array([50]), xp=np)[0]
    close(target, 1 / np.cosh(35 / 37))
    assert all(
        ml.LAW_PERMEABILITIES[law] == (("K", 1.0), ("Na", 0.2))
        for law in ml.MORRIS_LECAR_LAWS
        if "hcn" in law
    )


@pytest.mark.parametrize("name", KINETIC)
def test_full_analytic_clamp_recovery_covers_twelve_effective_time_constants(name):
    start = reference.kinetics(-0.080, name)["target"]
    rows, duration = [], 0.0
    for phase, voltage in (("depolarize", 0.0), ("recover", -0.080)):
        values = reference.kinetics(voltage, name)
        tau = values["tau_s"]
        for multiple in (0.0, 0.1, 1.0, 4.0, 8.0, 12.0):
            value = reference.relaxation(start, voltage, name, multiple * tau)
            m, v, code = case(name, voltage, value)
            assert ml.domain_valid(m, v, code, xp=np)
            close(ml.opening(m, v, code, xp=np), value)
            close(ml.rhs(m, v, code, xp=np), reference.rhs(value, voltage, name), "rhs_atol_per_s")
            rows.append(dict(phase=phase, time_s=duration + multiple * tau, state=value))
        start = reference.relaxation(start, voltage, name, 12 * tau)
        assert abs(start - values["target"]) <= np.exp(-12) + 1e-13
        duration += 12 * tau
    evidence(
        "analytic-clamp-" + name,
        dict(
            status="passed",
            name=name,
            duration_s=duration,
            effective_tau_rule="12 per phase",
            rows=rows,
        ),
    )


@pytest.mark.parametrize("name", KINETIC)
@pytest.mark.parametrize("voltage", [0.0, -0.080], ids=["depolarize", "recover"])
def test_dynamic_rk4_refinement_over_twelve_true_tau(name, voltage):
    m, v, code = case(name, voltage)
    target, tau = ml.kinetics(v, code, xp=np)
    initial = 0.2 if target[0] > 0.5 else 0.8
    duration = 12 * tau[0]
    errors, samples = [], {}
    for steps in PROTOCOL["clamp_protocol"]["continuous_refinement_steps"]:
        state = np.array([initial])
        dt = duration / steps
        saved = [state.copy()]
        error = 0.0
        for i in range(steps):
            a = ml.rhs(state, v, code, xp=np)
            b = ml.rhs(state + dt * a / 2, v, code, xp=np)
            c = ml.rhs(state + dt * b / 2, v, code, xp=np)
            d = ml.rhs(state + dt * c, v, code, xp=np)
            state = state + dt * (a + 2 * b + 2 * c + d) / 6
            expected = reference.relaxation(initial, voltage, name, (i + 1) * dt)
            error = max(error, abs(state[0] - expected))
            assert ml.domain_valid(state, v, code, xp=np)
            saved.append(state.copy())
        errors.append(float(error))
        samples[str(steps)] = np.stack(saved)
    stem = f"rk4-{name}-{voltage:.9g}"
    evidence(
        stem,
        dict(
            status="captured",
            name=name,
            voltage_V=voltage,
            duration_s=float(duration),
            errors=errors,
        ),
        samples,
    )
    assert errors[2] < errors[1] < errors[0]
    order = float(np.log2(errors[1] / errors[2]))
    assert TOL["rk4_order_bounds"][0] <= order <= TOL["rk4_order_bounds"][1]
    evidence(
        stem,
        dict(
            status="passed",
            name=name,
            voltage_V=voltage,
            duration_s=float(duration),
            errors=errors,
            observed_order=order,
        ),
    )


def test_actual_two_by_three_worlds_mixed_state_counts_and_population_permutation():
    codes = np.array([*CODES, -1], np.int64)
    worlds = np.stack((codes, np.r_[np.roll(codes[:13], 2), -1], np.r_[codes[:13][::-1], -1]))[
        None, ...
    ]
    v = np.stack(
        (np.r_[np.linspace(-0.110, 0.050, 13), 0.0], np.r_[np.linspace(-0.100, 0.060, 13), 0.0])
    )[:, None, :]
    state = np.where((worlds >= 40) & (worlds <= 44), np.array([0.2, 0.4, 0.7])[None, :, None], 0.0)
    assert ml.domain_valid(state, v, worlds, xp=np)
    target, tau = ml.kinetics(v, worlds, xp=np)
    opened, derivative = ml.opening(state, v, worlds, xp=np), ml.rhs(state, v, worlds, xp=np)
    assert target.shape == tau.shape == opened.shape == derivative.shape == (2, 3, 14)
    for i in range(2):
        for j in range(3):
            for k in range(13):
                name = NAME_BY_CODE[int(worlds[0, j, k])]
                voltage = float(v[i, 0, k])
                m = float(state[0, j, k])
                expected = reference.kinetics(voltage, name)
                close(target[i, j, k], expected["target"])
                close(tau[i, j, k], expected["tau_s"], "tau_atol_s")
                close(opened[i, j, k], reference.opening(m, voltage, name))
                close(derivative[i, j, k], reference.rhs(m, voltage, name), "rhs_atol_per_s")
    order = np.r_[np.arange(13)[::-1], 13]
    np.testing.assert_array_equal(
        ml.rhs(state[..., order], v[..., order], worlds[..., order], xp=np), derivative[..., order]
    )
    np.testing.assert_array_equal(
        ml.opening(state[..., order], v[..., order], worlds[..., order], xp=np), opened[..., order]
    )
    assert (
        np.all(target[..., -1] == 0) and np.all(tau[..., -1] == 0) and np.all(opened[..., -1] == 0)
    )
    evidence(
        "worlds",
        dict(status="passed", independent_worlds=6, packed_absence_exact=True),
        dict(target=target, tau_s=tau, opening=opened, rhs=derivative),
    )


@pytest.mark.parametrize(
    "failure",
    [
        "state-low",
        "state-high",
        "state-nan",
        "state-bool",
        "voltage-low",
        "voltage-high",
        "voltage-nan",
        "voltage-bool",
        "unknown-code",
        "prior-code",
        "float-code",
        "bool-code",
        "pad-state",
        "pad-voltage",
        "algebraic-state",
        "scalar-state",
        "scalar-voltage",
        "scalar-code",
        "population-count",
    ],
)
def test_strict_hybrid_state_padding_types_and_population_domain(failure):
    state, v, codes = (
        np.array([0.2, 0.0, 0.0]),
        np.array([-0.080, -0.020, 0.0]),
        np.array([40, 45, -1]),
    )
    if failure == "state-low":
        state[0] = -0.1
    elif failure == "state-high":
        state[0] = 1.1
    elif failure == "state-nan":
        state[0] = np.nan
    elif failure == "state-bool":
        state = state.astype(bool)
    elif failure == "voltage-low":
        v[0] = -0.121
    elif failure == "voltage-high":
        v[0] = 0.061
    elif failure == "voltage-nan":
        v[0] = np.nan
    elif failure == "voltage-bool":
        v = v.astype(bool)
    elif failure == "unknown-code":
        codes[0] = 53
    elif failure == "prior-code":
        codes[0] = 39
    elif failure == "float-code":
        codes = codes.astype(float)
    elif failure == "bool-code":
        codes = codes.astype(bool)
    elif failure == "pad-state":
        state[-1] = 0.1
    elif failure == "pad-voltage":
        v[-1] = 0.001
    elif failure == "algebraic-state":
        state[1] = 0.5
    elif failure == "scalar-state":
        state = 0.2
    elif failure == "scalar-voltage":
        v = -0.080
    elif failure == "scalar-code":
        codes = 40
    else:
        state = np.ones(4)
    assert not ml.domain_valid(state, v, codes, xp=np)


def test_empty_and_wholly_inactive_layouts_and_invalid_raw_empty_inputs():
    for n in (0, 3):
        state, v, codes = np.zeros((2, n)), np.zeros((2, n)), np.full(n, -1, np.int64)
        assert ml.domain_valid(state, v, codes, xp=np)
        assert all(
            np.all(value == 0)
            for value in (
                *ml.kinetics(v, codes, xp=np),
                ml.opening(state, v, codes, xp=np),
                ml.rhs(state, v, codes, xp=np),
            )
        )
    assert not ml.domain_valid(np.array([np.nan]), np.empty(0), np.empty(0, dtype=np.int64), xp=np)
    assert not ml.domain_valid(np.empty(0), np.array([np.nan]), np.empty(0, dtype=np.int64), xp=np)


def test_jax_hybrid_state_domains_eager_jit_vmap_and_absent_slots():
    import jax
    import jax.numpy as jnp

    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    codes = np.array([*CODES, -1], np.int64)
    v = np.stack(
        (np.r_[np.linspace(-0.110, 0.050, 13), 0.0], np.r_[np.linspace(-0.100, 0.060, 13), 0.0])
    )
    state = np.where((codes >= 40) & (codes <= 44), 0.3, 0.0)
    expected = ml.kinetics(v, codes, xp=np)
    for actual in (
        jax.jit(ml.kinetics)(v, codes),
        jax.jit(jax.vmap(lambda x: ml.kinetics(x, codes)))(v),
        ml.kinetics(jnp.asarray(v), jnp.asarray(codes)),
    ):
        close(actual[0], expected[0])
        close(actual[1], expected[1], "tau_atol_s")
    close(jax.jit(ml.initial_state)(v, codes), ml.initial_state(v, codes, xp=np))
    close(jax.jit(ml.rhs)(state, v, codes), ml.rhs(state, v, codes, xp=np), "rhs_atol_per_s")
    close(jax.jit(ml.opening)(state, v, codes), ml.opening(state, v, codes, xp=np))
    valid = jax.jit(ml.domain_valid)
    assert bool(valid(state, v, codes))
    bad = state.copy()
    bad[5] = 0.1
    assert not bool(valid(bad, v, codes))
    badcodes = codes.copy()
    badcodes[0] = 53
    assert not bool(valid(state, v, badcodes))
    assert not bool(valid(np.array([np.nan]), np.empty(0), np.empty(0, dtype=np.int64)))
    evidence(
        "jax-hybrid",
        dict(
            status="passed",
            jit=True,
            eager=True,
            vmap=True,
            absent_slots_zero=True,
            strict_domain=True,
        ),
    )


def test_jax_analytic_derivatives_preserve_dynamic_and_instantaneous_semantics():
    import jax
    import jax.numpy as jnp

    v = np.array(
        [
            float(reference.PARAMETERS[name][0]) / 1000 + 0.007 if name != "Kir_ML" else -0.100
            for name in CLASSES
        ]
    )
    codes = np.array(CODES, np.int64)
    state = np.where(codes <= 44, 0.3, 0.0)

    def readout(voltage):
        target, tau = ml.kinetics(voltage, codes)
        return jnp.stack(
            (target, tau, ml.opening(state, voltage, codes), ml.rhs(state, voltage, codes))
        )

    jac = jax.jit(jax.jacfwd(readout))(v)
    actual = np.stack([np.asarray(jac)[:, i, i] for i in range(13)], axis=-1)
    expected = []
    for i, name in enumerate(CLASSES):
        values = reference.kinetics(float(v[i]), name)
        target_d, tau_d = reference.voltage_derivative(float(v[i]), name)
        kinetic = name in reference.KINETIC
        rhs_d = (
            (target_d - (values["target"] - state[i]) * tau_d / values["tau_s"]) / values["tau_s"]
            if kinetic
            else 0.0
        )
        expected.append([target_d, tau_d, 0.0 if kinetic else target_d, rhs_d])
    assert np.isfinite(jac).all()
    np.testing.assert_allclose(
        actual, np.asarray(expected).T, rtol=TOL["derivative_relative"], atol=TOL["derivative_atol"]
    )
    state_jac = jax.jit(jax.jacfwd(lambda m: ml.rhs(m, v, codes)))(state)
    tau = ml.kinetics(v, codes, xp=np)[1]
    diagonal = np.zeros(13)
    diagonal[:5] = -1 / tau[:5]
    np.testing.assert_allclose(state_jac, np.diag(diagonal), rtol=TOL["relative"], atol=1e-11)
    assert actual[2, 11] > 0 and actual[2, 12] > 0
    evidence(
        "jax-derivatives",
        dict(status="passed", analytic_cases=13, dynamic_states=5, instantaneous_laws=8),
        dict(actual=actual, expected=np.asarray(expected).T),
    )
