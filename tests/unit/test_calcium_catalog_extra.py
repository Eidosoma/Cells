"""Independent remaining-calcium targets, analytic limits and full-duration clocks."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.processes import calcium_catalog_extra as calcium
from cells.processes import cav_channels
from validation.channels import calcium_catalog_extra_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "validation/channels/calcium_catalog_extra_protocol.json").read_text()
)
TOL = PROTOCOL["tolerances"]
CLASSES = tuple(calcium.CALCIUM_EXTRA_LAWS.values())
CODES = tuple(calcium.LAW_CODES.values())
CODE_BY_NAME = dict(zip(CLASSES, CODES, strict=True))
NAME_BY_CODE = dict(zip(CODES, CLASSES, strict=True))
TRANSITIONS = tuple((name, v) for name, points in reference.TRANSITIONS_V.items() for v in points)


def evidence(name, report, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(directory) / "cpu"
        path.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(path / ("calcium-extras-" + name + ".npz"), **arrays)
        (path / ("calcium-extras-" + name + ".json")).write_text(
            json.dumps(report, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )


def close(actual, expected, key):
    np.testing.assert_allclose(actual, expected, rtol=TOL["relative"], atol=TOL[key])


def case(name, voltage, gates=(0.2, 0.7)):
    return (
        np.asarray(gates, float)[:, None],
        np.array([voltage]),
        np.array([CODE_BY_NAME[name]], np.int64),
    )


def test_standalone_codebook_metadata_and_explicit_negative_padding():
    assert CLASSES == reference.CLASSES == tuple(PROTOCOL["classes"])
    assert calcium.LAW_CODES == PROTOCOL["law_codes"]
    assert CODES == (35, 36, 37, 38) and calcium.PAD_CODE == PROTOCOL["padding_code"] == -1
    assert calcium.valid_codes(np.array([-1, *CODES]), xp=np)
    assert not calcium.valid_codes(np.array([0, 11, 12, 17, 34, 39]), xp=np)
    for law, name in calcium.CALCIUM_EXTRA_LAWS.items():
        assert calcium.LAW_PERMEABILITIES[law] == (("Ca", 1.0),)
        assert calcium.GATE_POWERS[law] == reference.POWERS[name]


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("voltage", [-0.120, -0.080, -0.065, -0.020, 0.0, 0.060])
def test_decimal_kinetics_initialization_opening_and_rhs(name, voltage):
    g, v, codes = case(name, voltage)
    assert calcium.domain_valid(g, v, codes, xp=np)
    target, tau = calcium.kinetics(v, codes, xp=np)
    derivative, opened = calcium.rhs(g, v, codes, xp=np), calcium.opening(g, codes, xp=np)
    stem = f"ordinary-{name}-{voltage:.9g}"
    evidence(
        stem,
        dict(status="captured", name=name, voltage_V=voltage),
        dict(target=target, tau_s=tau, derivative=derivative, opening=opened),
    )
    expected = reference.kinetics(voltage, name)
    close(target[:, 0], expected["target"], "gate_atol")
    close(tau[:, 0], expected["tau_s"], "tau_atol_s")
    close(derivative[:, 0], reference.rhs(g[:, 0].tolist(), voltage, name), "rate_atol_per_s")
    close(opened, reference.opening(g[:, 0].tolist(), name), "opening_atol")
    np.testing.assert_array_equal(calcium.initial_gates(v, codes, xp=np), target)
    evidence(stem, dict(status="passed", name=name, voltage_V=voltage, reference=expected))


@pytest.mark.parametrize("name,point", TRANSITIONS)
def test_transition_and_cav_g_limit_at_adjacent_binary_inputs(name, point):
    voltage = np.array(
        [
            point,
            np.nextafter(point, -np.inf),
            np.nextafter(point, np.inf),
            point - 1e-10,
            point + 1e-10,
        ]
    )
    codes = np.full(voltage.size, CODE_BY_NAME[name], np.int64)
    with np.errstate(all="raise"):
        target, tau = calcium.kinetics(voltage, codes, xp=np)
    expected = [reference.kinetics(float(v), name) for v in voltage]
    stem = f"transition-{name}-{point:.9g}"
    evidence(
        stem, dict(status="captured", name=name, voltage_V=voltage), dict(target=target, tau_s=tau)
    )
    close(target, np.asarray([v["target"] for v in expected]).T, "gate_atol")
    close(tau, np.asarray([v["tau_s"] for v in expected]).T, "tau_atol_s")
    evidence(
        stem,
        dict(
            status="passed",
            name=name,
            voltage_V=voltage,
            analytic_singularity_limit=(name == "Cav_G" and point == -0.027),
            native_source_match_claim=False,
        ),
    )


def test_l2_target_only_overlap_and_l3_exact_source_shift_are_not_full_kinetic_aliases():
    voltage = np.array([-0.100, -0.080, -0.030, -0.015, 0.0, 0.060])
    l2 = calcium.kinetics(voltage, np.full(6, 35), xp=np)
    accepted = cav_channels.cav_kinetics(voltage, np.full(6, 12), xp=np)
    np.testing.assert_array_equal(l2[0], accepted[0])
    assert np.max(np.abs(l2[1] - accepted[1])) > 0.005
    shifted = calcium.kinetics(voltage, np.full(6, 36), xp=np)
    unshifted = calcium.kinetics(voltage - 0.015, np.full(6, 35), xp=np)
    for a, b in zip(shifted, unshifted, strict=True):
        np.testing.assert_array_equal(a, b)
    native_cav12 = cav_channels.cav_kinetics(voltage, np.full(6, 11), xp=np)
    assert np.max(np.abs(shifted[0] - native_cav12[0])) > 0.01
    for v, code in ((-0.030, 35), (-0.015, 36)):
        close(calcium.kinetics(np.array([v]), np.array([code]), xp=np)[0][0, 0], 0.5, "gate_atol")
    evidence(
        "aliases",
        dict(
            status="passed",
            full_kinetic_aliases=[],
            l2_target_overlap="Cav1p3 only",
            l3_shift_mV=15,
            fixed_tau_s=[0.010, 0.059],
        ),
    )


def test_cav_g_alpha_limit_is_0209_per_ms_without_voltage_perturbation():
    _, v, code = case("Cav_G", -0.027)
    target, tau = calcium.kinetics(v, code, xp=np)
    reconstructed_alpha = target[0, 0] / (1000 * tau[0, 0])
    close(reconstructed_alpha, 0.209, "gate_atol")
    assert np.all(np.isfinite(target)) and np.all(np.isfinite(tau))
    # The input is unchanged; a physical trial is not shifted away from the source defect.
    np.testing.assert_array_equal(v, np.array([-0.027]))


def test_caleak_second_clock_powers_and_strict_auxiliary_state():
    g, v, codes = case("CaLeak", -0.080, (0.2, 0.7))
    target, tau = calcium.kinetics(v, codes, xp=np)
    np.testing.assert_array_equal(target, 1)
    np.testing.assert_array_equal(tau, 1)
    np.testing.assert_array_equal(calcium.opening(g, codes, xp=np), 1)
    close(calcium.rhs(g, v, codes, xp=np)[:, 0], [0.8, 0.3], "rate_atol_per_s")
    assert calcium.domain_valid(g, v, codes, xp=np)
    g[1, 0] = np.nan
    assert not calcium.domain_valid(g, v, codes, xp=np)


@pytest.mark.parametrize("name", CLASSES)
def test_full_analytic_clamp_and_recovery_cover_twelve_slow_time_constants(name):
    start = reference.kinetics(-0.080, name)["target"]
    if name == "CaLeak":
        start = PROTOCOL["clamp_protocol"]["CaLeak_initial_auxiliary_gates"]
    duration, rows = 0.0, []
    for phase, voltage in (("depolarize", 0.0), ("recover", -0.080)):
        values = reference.kinetics(voltage, name)
        slow, fast = max(values["tau_s"]), min(values["tau_s"])
        for time in sorted(
            set([0.0, fast / 10, fast, 4 * fast, slow, 4 * slow, 8 * slow, 12 * slow])
        ):
            state = reference.relaxation(start, voltage, name, time)
            g, v, code = case(name, voltage, state)
            assert calcium.domain_valid(g, v, code, xp=np)
            close(
                calcium.rhs(g, v, code, xp=np)[:, 0],
                reference.rhs(state, voltage, name),
                "rate_atol_per_s",
            )
            close(calcium.opening(g, code, xp=np), reference.opening(state, name), "opening_atol")
            rows.append(dict(phase=phase, time_s=duration + time, gates=state))
        start = reference.relaxation(start, voltage, name, 12 * slow)
        assert (
            max(abs(a - b) for a, b in zip(start, values["target"], strict=True))
            <= np.exp(-12) + 1e-13
        )
        duration += 12 * slow
    evidence(
        "analytic-clamp-" + name,
        dict(
            status="passed",
            name=name,
            duration_s=duration,
            duration_rule="12 slow time constants per phase",
            leak_auxiliary_only=name == "CaLeak",
            rows=rows,
        ),
    )


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("gate", [0, 1], ids=["m", "h"])
@pytest.mark.parametrize("voltage", [0.0, -0.080], ids=["depolarize", "recover"])
def test_isolated_rk4_refinement_over_twelve_gate_time_constants(name, gate, voltage):
    _, v, code = case(name, voltage)
    target, tau = calcium.kinetics(v, code, xp=np)
    initial = target.copy()
    initial[gate, 0] = 0.2 if target[gate, 0] > 0.5 else 0.8
    duration = 12 * tau[gate, 0]
    errors, samples = [], {}
    for steps in PROTOCOL["clamp_protocol"]["continuous_gate_refinement_steps"]:
        state, dt = initial.copy(), duration / steps
        saved, error = [state.copy()], 0.0
        for i in range(steps):
            a = calcium.rhs(state, v, code, xp=np)
            b = calcium.rhs(state + dt * a / 2, v, code, xp=np)
            c = calcium.rhs(state + dt * b / 2, v, code, xp=np)
            d = calcium.rhs(state + dt * c, v, code, xp=np)
            state = state + dt * (a + 2 * b + 2 * c + d) / 6
            exact = reference.relaxation(initial[:, 0].tolist(), voltage, name, (i + 1) * dt)
            error = max(error, abs(state[gate, 0] - exact[gate]))
            assert calcium.domain_valid(state, v, code, xp=np)
            saved.append(state.copy())
        errors.append(error)
        samples[str(steps)] = np.stack(saved)
    stem = f"rk4-{name}-{gate}-{voltage:.9g}"
    evidence(
        stem,
        dict(
            status="captured",
            name=name,
            gate=gate,
            voltage_V=voltage,
            duration_s=float(duration),
            errors=errors,
        ),
        samples,
    )
    assert errors[2] < errors[1] < errors[0]
    order = float(np.log2(errors[1] / errors[2]))
    assert TOL["continuous_order_bounds"][0] <= order <= TOL["continuous_order_bounds"][1]
    evidence(
        stem,
        dict(
            status="passed",
            name=name,
            gate=gate,
            voltage_V=voltage,
            duration_s=float(duration),
            errors=errors,
            observed_order=order,
            companion_at_exact_fixed_point=True,
        ),
    )


def test_actual_two_by_three_worlds_and_population_reordering():
    codes = np.array([*CODES, -1], np.int64)
    worlds = np.stack([codes, np.r_[np.roll(codes[:4], 1), -1], np.r_[codes[:4][::-1], -1]])[
        None, :, :
    ]
    voltage = np.array([[-0.080, -0.015, -0.027, 0.0, 0.0], [-0.100, -0.065, 0.020, 0.060, 0.0]])[
        :, None, :
    ]
    g = np.stack(
        [np.stack([np.full(5, 0.2 + 0.1 * j), np.full(5, 0.7 - 0.1 * j)]) for j in range(3)]
    )[None, ...]
    g[..., -1] = 0
    assert calcium.domain_valid(g, voltage, worlds, xp=np)
    target, tau = calcium.kinetics(voltage, worlds, xp=np)
    derivative = calcium.rhs(g, voltage, worlds, xp=np)
    opened = calcium.opening(g, worlds, xp=np)
    assert target.shape == tau.shape == derivative.shape == (2, 3, 2, 5)
    assert opened.shape == (1, 3, 5)
    for i in range(2):
        for j in range(3):
            for k in range(4):
                name = NAME_BY_CODE[int(worlds[0, j, k])]
                expected = reference.kinetics(float(voltage[i, 0, k]), name)
                close(target[i, j, :, k], expected["target"], "gate_atol")
                close(tau[i, j, :, k], expected["tau_s"], "tau_atol_s")
                close(
                    derivative[i, j, :, k],
                    reference.rhs(g[0, j, :, k].tolist(), float(voltage[i, 0, k]), name),
                    "rate_atol_per_s",
                )
    order = np.array([2, 0, 3, 1, 4])
    np.testing.assert_array_equal(
        calcium.rhs(g[..., order], voltage[..., order], worlds[..., order], xp=np),
        derivative[..., order],
    )
    assert (
        np.all(target[..., -1] == 0)
        and np.all(tau[..., -1] == 1)
        and np.all(derivative[..., -1] == 0)
    )
    evidence(
        "worlds",
        dict(status="passed", independent_worlds=6, reordering="exact"),
        dict(target=target, tau_s=tau, derivative=derivative, opening=opened),
    )


@pytest.mark.parametrize(
    "failure",
    [
        "voltage-low",
        "voltage-high",
        "voltage-nan",
        "bool-voltage",
        "gate-low",
        "gate-high",
        "gate-nan",
        "shared-zero",
        "unknown-code",
        "float-code",
        "bool-code",
        "pad-voltage",
        "pad-gate",
        "gate-axis",
        "bool-gates",
        "scalar-voltage",
        "scalar-code",
    ],
)
def test_strict_domain_and_padding_rejections(failure):
    g = np.array([[0.2, 0.0], [0.7, 0.0]])
    v, codes = np.array([-0.080, 0.0]), np.array([35, -1])
    if failure == "voltage-low":
        v[0] = -0.121
    elif failure == "voltage-high":
        v[0] = 0.061
    elif failure == "voltage-nan":
        v[0] = np.nan
    elif failure == "bool-voltage":
        v = v.astype(bool)
    elif failure == "gate-low":
        g[0, 0] = -0.1
    elif failure == "gate-high":
        g[1, 0] = 1.1
    elif failure == "gate-nan":
        g[1, 0] = np.nan
    elif failure == "shared-zero":
        codes[0] = 0
    elif failure == "unknown-code":
        codes[0] = 39
    elif failure == "float-code":
        codes = codes.astype(float)
    elif failure == "bool-code":
        codes = codes.astype(bool)
    elif failure == "pad-voltage":
        v[-1] = 0.01
    elif failure == "pad-gate":
        g[0, -1] = 0.1
    elif failure == "gate-axis":
        g = np.zeros((3, 2))
    elif failure == "bool-gates":
        g = g.astype(bool)
    elif failure == "scalar-voltage":
        v = -0.080
    else:
        codes = 35
    assert not calcium.domain_valid(g, v, codes, xp=np)


def test_empty_and_all_inactive_populations_are_neutral():
    for n in (0, 3):
        v, codes, g = np.zeros((2, n)), np.full(n, -1, np.int64), np.zeros((2, 2, n))
        assert calcium.domain_valid(g, v, codes, xp=np)
        target, tau = calcium.kinetics(v, codes, xp=np)
        assert target.shape == tau.shape == (2, 2, n)
        assert np.all(target == 0) and np.all(tau == 1)
        assert np.all(calcium.rhs(g, v, codes, xp=np) == 0) and np.all(
            calcium.opening(g, codes, xp=np) == 0
        )


@pytest.mark.parametrize(
    "failure", ["voltage-nan", "voltage-bound", "gate-nan", "gate-bound", "unknown-code"]
)
def test_empty_broadcast_does_not_discard_invalid_declared_input(failure):
    g, v, codes = np.zeros((2, 0)), np.zeros(0), np.empty(0, dtype=np.int64)
    if failure == "voltage-nan":
        v = np.array([np.nan])
    elif failure == "voltage-bound":
        v = np.array([0.061])
    elif failure == "gate-nan":
        g = np.array([[np.nan], [0.7]])
    elif failure == "gate-bound":
        g = np.array([[1.1], [0.7]])
    else:
        codes = np.array([39])
    assert not calcium.domain_valid(g, v, codes, xp=np)


def test_jax_eager_jit_vmap_arrays_rhs_opening_and_strict_domains():
    import jax
    import jax.numpy as jnp

    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    codes = np.array([*CODES, -1], np.int64)
    v = np.array([[-0.080, -0.015, -0.027, 0.0, 0.0], [-0.100, -0.065, 0.020, 0.060, 0.0]])
    g = np.broadcast_to(np.array([0.2, 0.7])[:, None], (2, 5)).copy()
    g[:, -1] = 0
    expected = calcium.kinetics(v, codes, xp=np)
    for actual in (
        jax.jit(calcium.kinetics)(v, codes),
        jax.jit(jax.vmap(lambda x: calcium.kinetics(x, codes)))(v),
        calcium.kinetics(jnp.asarray(v), jnp.asarray(codes)),
    ):
        close(actual[0], expected[0], "gate_atol")
        close(actual[1], expected[1], "tau_atol_s")
    close(jax.jit(calcium.rhs)(g, v, codes), calcium.rhs(g, v, codes, xp=np), "rate_atol_per_s")
    close(jax.jit(calcium.opening)(g, codes), calcium.opening(g, codes, xp=np), "opening_atol")
    valid = jax.jit(calcium.domain_valid)
    assert bool(valid(g, v, codes))
    bad = g.copy()
    bad[1, 3] = np.nan
    assert not bool(valid(bad, v, codes))
    badcodes = codes.copy()
    badcodes[0] = 0
    assert not bool(valid(g, v, badcodes))
    badv = v.copy()
    badv[0, -1] = 0.001
    assert not bool(valid(g, badv, codes))
    assert not bool(valid(np.zeros((2, 0)), np.array([np.nan]), np.empty(0, dtype=np.int64)))
    assert not bool(valid(np.array([[np.nan], [0.7]]), np.empty(0), np.empty(0, dtype=np.int64)))
    assert not bool(valid(np.zeros((2, 0)), np.empty(0), np.array([39])))
    evidence(
        "jax-arrays", dict(status="passed", jit=True, eager=True, vmap=True, strict_rejection=True)
    )


def test_jax_derivatives_at_native_singularity_shifts_and_leak_zero_sensitivity():
    import jax
    import jax.numpy as jnp

    points = (*TRANSITIONS, ("CaLeak", 0.0), ("Cav_G", -0.119))
    v = np.array([x for _, x in points])
    codes = np.array([CODE_BY_NAME[n] for n, _ in points])
    derivative = jax.jit(
        jax.jacfwd(lambda x: jnp.concatenate(calcium.kinetics(x, codes), axis=-2))
    )(v)
    assert np.isfinite(derivative).all()
    actual = np.stack([np.asarray(derivative)[:, i, i] for i in range(len(points))], axis=-1)
    expected = np.asarray([reference.voltage_derivative(float(x), n) for n, x in points]).T
    np.testing.assert_allclose(
        actual, expected, rtol=TOL["derivative_relative"], atol=TOL["derivative_atol_per_V"]
    )
    leak = [i for i, (n, _) in enumerate(points) if n == "CaLeak"][0]
    np.testing.assert_array_equal(actual[:, leak], 0)
    evidence(
        "jax-derivatives",
        dict(
            status="passed",
            cases=len(points),
            decimal_increment_V=1e-20,
            singular_Cav_G_finite=True,
            leak_voltage_derivative=actual[:, leak].tolist(),
        ),
    )
