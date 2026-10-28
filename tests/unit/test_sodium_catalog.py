"""Pinned NaV equations, regularized limits, adequate clamps and world axes."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.processes import sodium_catalog as sodium
from cells.processes import sodium_channels as accepted
from validation.channels import sodium_catalog_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/channels/sodium_catalog_protocol.json").read_text())
TOL = PROTOCOL["tolerances"]
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
CLASSES = tuple(sodium.SODIUM_LAWS.values())
CODES = tuple(sodium.LAW_CODES.values())
CODE_BY_NAME = dict(zip(CLASSES, CODES, strict=True))
NAME_BY_CODE = dict(zip(CODES, CLASSES, strict=True))


def evidence(name, value, arrays=None):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(path / ("sodium-catalog-" + name + ".npz"), **arrays)
        (path / ("sodium-catalog-" + name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )


def close(actual, expected, key):
    np.testing.assert_allclose(actual, expected, rtol=TOL["relative"], atol=TOL[key])


def case(name, voltage, gates=(0.2, 0.7)):
    return (
        np.asarray(gates, float)[:, None],
        np.array([voltage]),
        np.array([CODE_BY_NAME[name]], np.int64),
    )


def test_complete_pinned_class_identity_and_sodium_only_codebook():
    assert CLASSES == reference.CLASSES == tuple(PROTOCOL["classes"])
    assert sodium.LAW_CODES == PROTOCOL["law_codes"]
    assert sodium.LAW_CODES[accepted.LAW_ID] == 2
    assert all(sodium.LAW_PERMEABILITIES[law] == (("Na", 1.0),) for law in sodium.SODIUM_LAWS)
    assert sodium.valid_codes(np.array([0, *CODES]), xp=np)
    assert not sodium.valid_codes(np.array([1]), xp=np)  # Not the older shared catalog.


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("voltage", [-0.120, -0.080, -0.065, -0.020, 0.0, 0.060])
def test_independent_decimal_kinetics_initialization_opening_and_rates(name, voltage):
    g, v, codes = case(name, voltage)
    assert sodium.domain_valid(g, v, codes, xp=np)
    target, tau = sodium.kinetics(v, codes, xp=np)
    actual = dict(
        target=target,
        tau_s=tau,
        derivative=sodium.rhs(g, v, codes, xp=np),
        opening=sodium.opening(g, codes, xp=np),
    )
    stem = f"ordinary-{name}-{voltage:.9g}"
    evidence(
        stem, dict(status="actual_captured", name=name, voltage_V=voltage, gates=g[:, 0]), actual
    )
    expected = reference.kinetics(voltage, name)
    close(target[:, 0], expected["target"], "gate_atol")
    close(tau[:, 0], expected["tau_s"], "tau_atol_s")
    close(
        actual["derivative"][:, 0],
        reference.rhs(g[:, 0].tolist(), voltage, name),
        "rate_atol_per_s",
    )
    close(actual["opening"], reference.opening(g[:, 0].tolist(), name), "opening_atol")
    np.testing.assert_array_equal(sodium.initial_gates(v, codes, xp=np), target)
    assert np.all((target >= 0) & (target <= 1)) and np.all(tau > 0)
    evidence(stem, dict(status="passed", name=name, voltage_V=voltage, expected=expected))


SINGULAR_CASES = tuple(
    (name, point) for name, points in reference.SINGULAR_V.items() for point in points
)


@pytest.mark.parametrize(("name", "point"), SINGULAR_CASES)
def test_analytic_singular_limits_and_adjacent_binary_inputs(name, point):
    codes = np.full(5, CODE_BY_NAME[name], np.int64)
    voltage = np.array(
        [
            point,
            np.nextafter(point, -np.inf),
            np.nextafter(point, np.inf),
            point - 1e-12,
            point + 1e-12,
        ]
    )
    with np.errstate(all="raise"):
        target, tau = sodium.kinetics(voltage, codes, xp=np)
    evidence(
        f"regularized-{name}-{point:.9g}",
        dict(status="actual_captured", name=name, voltage_V=voltage),
        dict(target=target, tau_s=tau),
    )
    expected = [reference.kinetics(float(v), name) for v in voltage]
    close(target, np.asarray([v["target"] for v in expected]).T, "gate_atol")
    close(tau, np.asarray([v["tau_s"] for v in expected]).T, "tau_atol_s")
    assert np.isfinite(target).all() and np.isfinite(tau).all()
    evidence(
        f"regularized-{name}-{point:.9g}",
        dict(
            status="passed",
            name=name,
            voltage_V=voltage,
            claim="Analytic regularization, not finite native singular parity",
        ),
    )


def test_accepted_nav1p2_overlap_is_exact_including_regularized_points():
    voltage = np.array([-0.120, -0.080, -0.065000123, -0.040, -0.025, -0.020, 0, 0.060])
    codes = np.full(voltage.shape, 2, np.int64)
    expected = accepted.nav1p2_kinetics(voltage, xp=np)
    actual = sodium.kinetics(voltage, codes, xp=np)
    for a, b in zip(actual, expected, strict=True):
        np.testing.assert_array_equal(a, b)
    gates = np.stack((np.linspace(0, 1, voltage.size), np.linspace(1, 0, voltage.size)))
    np.testing.assert_array_equal(
        sodium.opening(gates, codes, xp=np), accepted.opening(gates, codes, xp=np)
    )
    evidence(
        "accepted-overlap",
        dict(
            status="passed",
            accepted_component=accepted.LAW_ID,
            comparison="exact",
            voltage_V=voltage,
        ),
    )


def test_rat1_rat3_remain_distinct_names_with_identical_source_kinetics():
    voltage = np.array([-0.12, -0.075000123, -0.050, -0.035, 0.0, 0.060])
    a = sodium.kinetics(voltage, np.full(voltage.size, CODE_BY_NAME["NavRat1"]), xp=np)
    b = sodium.kinetics(voltage, np.full(voltage.size, CODE_BY_NAME["NavRat3"]), xp=np)
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)
    assert CODE_BY_NAME["NavRat1"] != CODE_BY_NAME["NavRat3"]


@pytest.mark.parametrize("name", CLASSES)
def test_source_gate_powers_and_auxiliary_gate_semantics(name):
    g, v, code = case(name, -0.080, (0.5, 0.25))
    expected = 1.0 if name == "NaLeak" else 0.5 if name == "Nav1p6" else 0.03125
    assert sodium.opening(g, code, xp=np)[0] == expected
    target, tau = sodium.kinetics(v, code, xp=np)
    if name in ("NaLeak", "Nav1p6"):
        assert target[1, 0] == 1
        assert tau[1, 0] == (1 if name == "NaLeak" else 0.001)
        assert sodium.rhs(g, v, code, xp=np)[1, 0] > 0
        g[1, 0] = np.nan
        assert not sodium.domain_valid(g, v, code, xp=np)


@pytest.mark.parametrize("name", CLASSES)
def test_full_clamp_and_recovery_rhs_along_independent_exact_solutions(name):
    start = reference.kinetics(-0.080, name)["target"]
    duration, rows = 0.0, []
    for phase, voltage in (("depolarize", 0.0), ("recover", -0.080)):
        values = reference.kinetics(voltage, name)
        slow, fast = max(values["tau_s"]), min(values["tau_s"])
        times = sorted(set([0, fast / 10, fast, 4 * fast, slow, 4 * slow, 8 * slow, 12 * slow]))
        for time in times:
            exact = reference.relaxation(start, voltage, name, time)
            g, v, code = case(name, voltage, exact)
            assert sodium.domain_valid(g, v, code, xp=np)
            close(
                sodium.rhs(g, v, code, xp=np)[:, 0],
                reference.rhs(exact, voltage, name),
                "rate_atol_per_s",
            )
            close(sodium.opening(g, code, xp=np), reference.opening(exact, name), "opening_atol")
            rows.append(dict(phase=phase, time_s=duration + time, gates=exact))
        start = reference.relaxation(start, voltage, name, times[-1])
        if name == "NaLeak":
            close(start, values["target"], "gate_atol")
        assert (
            max(abs(a - b) for a, b in zip(start, values["target"], strict=True))
            <= np.exp(-12) + 1e-13
        )
        duration += times[-1]
    evidence(
        "clamp-rhs-" + name,
        dict(
            status="passed",
            name=name,
            duration_s=duration,
            duration_rule="12 slow time constants per segment",
            rows=rows,
        ),
    )


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("gate", [0, 1], ids=["m", "h"])
@pytest.mark.parametrize("voltage", [0.0, -0.080], ids=["depolarize", "recover"])
def test_isolated_continuous_gate_refinement_over_twelve_time_constants(name, gate, voltage):
    _, v, codes = case(name, voltage)
    target, tau = sodium.kinetics(v, codes, xp=np)
    initial = target.copy()
    initial[gate, 0] = 0.2 if target[gate, 0] > 0.5 else 0.8
    duration = 12 * tau[gate, 0]
    errors, samples = [], {}
    for steps in PROTOCOL["clamp_protocol"]["continuous_gate_refinement_steps"]:
        state, dt = initial.copy(), duration / steps
        saved = [state.copy()]
        error = 0.0
        for i in range(steps):
            a = sodium.rhs(state, v, codes, xp=np)
            b = sodium.rhs(state + 0.5 * dt * a, v, codes, xp=np)
            c = sodium.rhs(state + 0.5 * dt * b, v, codes, xp=np)
            d = sodium.rhs(state + dt * c, v, codes, xp=np)
            state = state + dt * (a + 2 * b + 2 * c + d) / 6
            expected = reference.relaxation(initial[:, 0].tolist(), voltage, name, (i + 1) * dt)
            error = max(error, abs(state[gate, 0] - expected[gate]))
            assert sodium.domain_valid(state, v, codes, xp=np)
            saved.append(state.copy())
        errors.append(error)
        samples[str(steps)] = np.stack(saved)
    stem = f"refine-{name}-{gate}-{voltage:.9g}"
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
    assert 3.7 <= order <= 4.6
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
            independent_other_gate_held_at_fixed_point=True,
        ),
    )


def test_true_world_law_voltage_gate_broadcasting_and_population_permutation():
    codes = np.array([*CODES, 0], np.int64)
    code_worlds = np.stack((codes, np.r_[np.roll(codes[:7], 1), 0], np.r_[codes[:7][::-1], 0]))[
        None, :, :
    ]
    voltage = np.array(
        [
            [-0.080, -0.060, -0.040, -0.020, 0.0, 0.020, 0.060, 0.0],
            [-0.100, -0.070, -0.050, -0.030, -0.010, 0.010, 0.040, 0.0],
        ]
    )[:, None, :]
    gates = np.stack(
        [np.stack((np.full(8, 0.2 + 0.1 * j), np.full(8, 0.7 - 0.1 * j))) for j in range(3)]
    )[None, :, :, :]
    gates[..., -1] = 0
    assert sodium.domain_valid(gates, voltage, code_worlds, xp=np)
    target, tau = sodium.kinetics(voltage, code_worlds, xp=np)
    derivative = sodium.rhs(gates, voltage, code_worlds, xp=np)
    opening = sodium.opening(gates, code_worlds, xp=np)
    assert target.shape == tau.shape == derivative.shape == (2, 3, 2, 8)
    assert opening.shape == (1, 3, 8)  # Opening has no voltage world axis of its own.
    evidence(
        "worlds",
        dict(status="actual_captured", independent_worlds=6),
        dict(target=target, tau_s=tau, derivative=derivative, opening=opening),
    )
    for i in range(2):
        for j in range(3):
            for k in range(7):
                name = NAME_BY_CODE[int(code_worlds[0, j, k])]
                expected = reference.kinetics(float(voltage[i, 0, k]), name)
                close(target[i, j, :, k], expected["target"], "gate_atol")
                close(tau[i, j, :, k], expected["tau_s"], "tau_atol_s")
                close(
                    derivative[i, j, :, k],
                    reference.rhs(gates[0, j, :, k].tolist(), float(voltage[i, 0, k]), name),
                    "rate_atol_per_s",
                )
    order = np.array([6, 2, 0, 5, 1, 4, 3, 7])
    reordered = sodium.rhs(gates[..., order], voltage[..., order], code_worlds[..., order], xp=np)
    np.testing.assert_array_equal(reordered, derivative[..., order])
    assert (
        np.all(target[..., -1] == 0)
        and np.all(tau[..., -1] == 1)
        and np.all(derivative[..., -1] == 0)
    )
    evidence("worlds", dict(status="passed", independent_worlds=6, population_reorder="exact"))


@pytest.mark.parametrize(
    "failure",
    [
        "voltage_low",
        "voltage_high",
        "voltage_nan",
        "gate_low",
        "gate_high",
        "gate_nan",
        "bad_code",
        "float_code",
        "bool_code",
        "pad_voltage",
        "pad_gate",
        "bad_gate_axis",
        "bool_gates",
    ],
)
def test_invalid_domain_and_neutral_padding_rejected(failure):
    g = np.array([[0.2, 0.0], [0.7, 0.0]])
    v, code = np.array([-0.080, 0.0]), np.array([18, 0])
    if failure == "voltage_low":
        v[0] = -0.121
    elif failure == "voltage_high":
        v[0] = 0.061
    elif failure == "voltage_nan":
        v[0] = np.nan
    elif failure == "gate_low":
        g[0, 0] = -0.1
    elif failure == "gate_high":
        g[1, 0] = 1.1
    elif failure == "gate_nan":
        g[1, 0] = np.nan
    elif failure == "bad_code":
        code[0] = 1
    elif failure == "float_code":
        code = code.astype(float)
    elif failure == "bool_code":
        code = code.astype(bool)
    elif failure == "pad_voltage":
        v[1] = -0.010
    elif failure == "pad_gate":
        g[0, 1] = 0.1
    elif failure == "bad_gate_axis":
        g = np.zeros((3, 2))
    else:
        g = g.astype(bool)
    assert not sodium.domain_valid(g, v, code, xp=np)


def test_empty_population_axis_and_wholly_inactive_layouts_are_neutral():
    for n in (0, 3):
        v, code, gate = np.zeros((2, n)), np.zeros(n, np.int64), np.zeros((2, 2, n))
        assert sodium.domain_valid(gate, v, code, xp=np)
        target, tau = sodium.kinetics(v, code, xp=np)
        assert target.shape == tau.shape == (2, 2, n)
        assert np.all(target == 0) and np.all(tau == 1)
        assert np.all(sodium.rhs(gate, v, code, xp=np) == 0)
        assert np.all(sodium.opening(gate, code, xp=np) == 0)


def test_jax_eager_jit_vmap_opening_rhs_and_compiled_domains():
    import jax
    import jax.numpy as jnp

    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    codes = np.array([*CODES, 0], np.int64)
    v = np.array(
        [
            [-0.080, -0.026, -0.038, -0.035, -0.050, -0.010, 0.020, 0.0],
            [-0.025, -0.040, -0.075000123, 0.0, 0.020, -0.080, -0.030, 0.0],
        ]
    )
    g = np.broadcast_to(np.array([0.2, 0.7])[:, None], (2, 8)).copy()
    g[:, -1] = 0
    expected = sodium.kinetics(v, codes, xp=np)
    actual = jax.jit(sodium.kinetics)(v, codes)
    mapped = jax.jit(jax.vmap(lambda x: sodium.kinetics(x, codes)))(v)
    for values in (actual, mapped, sodium.kinetics(jnp.asarray(v), jnp.asarray(codes))):
        close(np.asarray(values[0]), expected[0], "gate_atol")
        close(np.asarray(values[1]), expected[1], "tau_atol_s")
    close(
        np.asarray(jax.jit(sodium.rhs)(g, v, codes)),
        sodium.rhs(g, v, codes, xp=np),
        "rate_atol_per_s",
    )
    close(
        np.asarray(jax.jit(sodium.opening)(g, codes)),
        sodium.opening(g, codes, xp=np),
        "opening_atol",
    )
    valid = jax.jit(sodium.domain_valid)
    assert bool(valid(g, v, codes))
    bad = g.copy()
    bad[1, 0] = np.nan
    assert not bool(valid(bad, v, codes))
    bad = v.copy()
    bad[0, -1] = 0.01
    assert not bool(valid(g, bad, codes))
    evidence(
        "jax-arrays",
        dict(status="passed", eager=True, jit=True, vmap=True, compiled_rejection=True),
    )


def test_jax_finite_voltage_derivatives_at_every_removable_singularity():
    import jax
    import jax.numpy as jnp

    names = [v[0] for v in SINGULAR_CASES]
    voltage = np.array([v[1] for v in SINGULAR_CASES])
    codes = np.array([CODE_BY_NAME[name] for name in names])
    derivative = jax.jit(jax.jacfwd(lambda x: jnp.concatenate(sodium.kinetics(x, codes), axis=-2)))(
        voltage
    )
    assert np.isfinite(np.asarray(derivative)).all()
    h = 1e-7
    plus = [reference.kinetics(float(v + h), name) for v, name in zip(voltage, names, strict=True)]
    minus = [reference.kinetics(float(v - h), name) for v, name in zip(voltage, names, strict=True)]
    expected = np.array(
        [
            (np.r_[a["target"], a["tau_s"]] - np.r_[b["target"], b["tau_s"]]) / (2 * h)
            for a, b in zip(plus, minus, strict=True)
        ]
    ).T
    actual = np.stack([np.asarray(derivative)[:, i, i] for i in range(len(voltage))], axis=-1)
    np.testing.assert_allclose(actual, expected, rtol=3e-7, atol=3e-8)
    evidence(
        "jax-singular-derivatives",
        dict(status="passed", singular_cases=len(voltage), difference_step_V=h),
    )
