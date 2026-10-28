"""Pinned remaining-K equations, exact Kir overlap and adequate clamp horizons."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.processes import potassium_catalog as potassium
from cells.processes import potassium_channels as accepted
from validation.channels import potassium_catalog_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/channels/potassium_catalog_protocol.json").read_text())
TOL = PROTOCOL["tolerances"]
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
CLASSES = tuple(potassium.POTASSIUM_LAWS.values())
CODES = tuple(potassium.LAW_CODES.values())
CODE_BY_NAME = dict(zip(CLASSES, CODES, strict=True))
NAME_BY_CODE = dict(zip(CODES, CLASSES, strict=True))


def evidence(name, report, arrays=None):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(path / ("potassium-catalog-" + name + ".npz"), **arrays)
        (path / ("potassium-catalog-" + name + ".json")).write_text(
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


def test_owned_codebook_preserves_existing_kir_and_does_not_redefine_shared_zero():
    assert CLASSES == reference.CLASSES == tuple(PROTOCOL["classes"])
    assert potassium.LAW_CODES == PROTOCOL["law_codes"]
    assert potassium.LAW_CODES[accepted.KIR_LAW_ID] == 1
    assert potassium.PAD_CODE == PROTOCOL["padding_code"] == -1
    assert potassium.valid_codes(np.array([-1, *CODES]), xp=np)
    assert not potassium.valid_codes(np.array([0, 2, 18, 23]), xp=np)
    assert all(
        potassium.LAW_PERMEABILITIES[law] == (("K", 1.0),) for law in potassium.POTASSIUM_LAWS
    )


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("voltage", [-0.120, -0.080, -0.065, -0.020, 0.0, 0.060])
def test_decimal_kinetics_initialization_opening_and_rhs(name, voltage):
    gates, v, codes = case(name, voltage)
    assert potassium.domain_valid(gates, v, codes, xp=np)
    target, tau = potassium.kinetics(v, codes, xp=np)
    actual = dict(
        target=target,
        tau_s=tau,
        derivative=potassium.rhs(gates, v, codes, xp=np),
        opening=potassium.opening(gates, codes, xp=np),
    )
    stem = f"ordinary-{name}-{voltage:.9g}"
    evidence(
        stem,
        dict(status="actual_captured", name=name, voltage_V=voltage, gates=gates[:, 0]),
        actual,
    )
    expected = reference.kinetics(voltage, name)
    close(target[:, 0], expected["target"], "gate_atol")
    close(tau[:, 0], expected["tau_s"], "tau_atol_s")
    close(
        actual["derivative"][:, 0],
        reference.rhs(gates[:, 0].tolist(), voltage, name),
        "rate_atol_per_s",
    )
    close(actual["opening"], reference.opening(gates[:, 0].tolist(), name), "opening_atol")
    np.testing.assert_array_equal(potassium.initial_gates(v, codes, xp=np), target)
    assert np.all((target >= 0) & (target <= 1)) and np.all(tau > 0)
    evidence(stem, dict(status="passed", name=name, voltage_V=voltage, expected=expected))


TRANSITIONS = tuple(
    (name, point) for name, points in reference.TRANSITIONS_V.items() for point in points
)


@pytest.mark.parametrize(("name", "point"), TRANSITIONS)
def test_smooth_transition_centers_and_adjacent_binary_inputs(name, point):
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
        target, tau = potassium.kinetics(voltage, codes, xp=np)
    stem = f"transition-{name}-{point:.9g}"
    evidence(
        stem,
        dict(status="actual_captured", name=name, voltage_V=voltage),
        dict(target=target, tau_s=tau),
    )
    expected = [reference.kinetics(float(v), name) for v in voltage]
    close(target, np.asarray([v["target"] for v in expected]).T, "gate_atol")
    close(tau, np.asarray([v["tau_s"] for v in expected]).T, "tau_atol_s")
    evidence(stem, dict(status="passed", name=name, voltage_V=voltage, removable_singularity=False))


def test_accepted_kir_kinetics_and_opening_overlap_are_exact():
    voltage = np.array([-0.120, -0.09648, -0.080, -0.0329, 0.0, 0.060])
    codes = np.ones(voltage.size, np.int64)
    actual = potassium.kinetics(voltage, codes, xp=np)
    for a, b in zip(actual, accepted.kir2p1_kinetics(voltage, xp=np), strict=True):
        np.testing.assert_array_equal(a, b)
    gates = np.stack(
        (np.linspace(0.173, 0.817, voltage.size), np.linspace(0.919, 0.081, voltage.size))
    )
    np.testing.assert_array_equal(
        potassium.opening(gates, codes, xp=np), accepted.opening(gates, codes, xp=np)
    )
    evidence(
        "accepted-kir-overlap",
        dict(status="passed", law=accepted.KIR_LAW_ID, comparison="exact", voltage_V=voltage),
    )


@pytest.mark.parametrize("name", CLASSES)
def test_source_powers_and_unused_gates_are_preserved(name):
    gates, v, code = case(name, -0.080, (0.5, 0.25))
    exponents = reference.POWERS[name]
    expected = 0.5 ** exponents[0] * 0.25 ** exponents[1]
    assert potassium.opening(gates, code, xp=np)[0] == expected
    target, tau = potassium.kinetics(v, code, xp=np)
    if name in ("Kv3p1", "Kv3p2", "KLeak"):
        assert target[1, 0] == 1
        assert tau[1, 0] == (1 if name == "KLeak" else 0.001)
        assert potassium.rhs(gates, v, code, xp=np)[1, 0] > 0
        gates[1, 0] = np.nan
        assert not potassium.domain_valid(gates, v, code, xp=np)


def test_literal_source_time_units_baseline_and_long_kv3p3_recovery():
    gates, v, code = case("Kv3p3", -0.080, (0.2, 0.1))
    target, tau = potassium.kinetics(v, code, xp=np)
    expected = PROTOCOL["source_quirks"]
    close(tau[1, 0], expected["Kv3p3_tau_h_at_minus80mV_s"], "tau_atol_s")
    np.testing.assert_allclose(
        12 * tau[1, 0],
        86400 * expected["Kv3p3_12tau_at_minus80mV_days"],
        rtol=TOL["horizon_relative"],
        atol=TOL["horizon_atol_s"],
    )
    assert target[1, 0] > 0.25 and potassium.domain_valid(gates, v, code, xp=np)
    assert potassium.rhs(gates, v, code, xp=np)[1, 0] > 0  # Target baseline is not a state floor.
    _, vf, cf = case("K_Fast", -0.071)
    close(potassium.kinetics(vf, cf, xp=np)[1][0, 0], 0.00126, "tau_atol_s")
    vf[0] = -0.073
    close(potassium.kinetics(vf, cf, xp=np)[1][1, 0], 0.057, "tau_atol_s")
    _, vm, cm = case("Kv3p2", -0.000373267)
    assert potassium.kinetics(vm, cm, xp=np)[0][0, 0] == 0.5
    evidence(
        "source-quirks",
        dict(
            status="passed",
            kv3p3_tau_h_s=float(tau[1, 0]),
            recovery_12tau_days=float(12 * tau[1, 0] / 86400),
            nominal_vrev_not_used=True,
            source_preserved_without_unit_repair=True,
        ),
    )


@pytest.mark.parametrize("name", CLASSES)
def test_full_exact_clamp_recovery_covers_twelve_slow_time_constants(name):
    initial = reference.kinetics(-0.080, name)["target"]
    duration, rows = 0.0, []
    for phase, voltage in (("depolarize", 0.0), ("recover", -0.080)):
        values = reference.kinetics(voltage, name)
        slow, fast = max(values["tau_s"]), min(values["tau_s"])
        times = sorted(set([0.0, fast / 10, fast, 4 * fast, slow, 4 * slow, 8 * slow, 12 * slow]))
        for time in times:
            state = reference.relaxation(initial, voltage, name, time)
            gates, v, code = case(name, voltage, state)
            assert potassium.domain_valid(gates, v, code, xp=np)
            close(
                potassium.rhs(gates, v, code, xp=np)[:, 0],
                reference.rhs(state, voltage, name),
                "rate_atol_per_s",
            )
            close(
                potassium.opening(gates, code, xp=np),
                reference.opening(state, name),
                "opening_atol",
            )
            rows.append(dict(phase=phase, time_s=duration + time, gates=state))
        initial = reference.relaxation(initial, voltage, name, times[-1])
        assert (
            max(abs(a - b) for a, b in zip(initial, values["target"], strict=True))
            <= np.exp(-12) + 1e-13
        )
        duration += times[-1]
    evidence(
        "clamp-rhs-" + name,
        dict(
            status="passed",
            name=name,
            duration_s=duration,
            duration_rule="12 slow time constants per segment, no model-time truncation",
            rows=rows,
        ),
    )


@pytest.mark.parametrize("name", CLASSES)
@pytest.mark.parametrize("gate", [0, 1], ids=["m", "h"])
@pytest.mark.parametrize("voltage", [0.0, -0.080], ids=["depolarize", "recover"])
def test_isolated_continuous_gate_refinement_over_full_twelve_tau(name, gate, voltage):
    _, v, code = case(name, voltage)
    target, tau = potassium.kinetics(v, code, xp=np)
    initial = target.copy()
    initial[gate, 0] = 0.2 if target[gate, 0] > 0.5 else 0.8
    duration = 12 * tau[gate, 0]
    samples, errors = {}, []
    for steps in PROTOCOL["clamp_protocol"]["continuous_gate_refinement_steps"]:
        state, dt = initial.copy(), duration / steps
        saved, error = [state.copy()], 0.0
        for i in range(steps):
            a = potassium.rhs(state, v, code, xp=np)
            b = potassium.rhs(state + dt * a / 2, v, code, xp=np)
            c = potassium.rhs(state + dt * b / 2, v, code, xp=np)
            d = potassium.rhs(state + dt * c, v, code, xp=np)
            state = state + dt * (a + 2 * b + 2 * c + d) / 6
            expected = reference.relaxation(initial[:, 0].tolist(), voltage, name, (i + 1) * dt)
            error = max(error, abs(state[gate, 0] - expected[gate]))
            assert potassium.domain_valid(state, v, code, xp=np)
            saved.append(state.copy())
        samples[str(steps)] = np.stack(saved)
        errors.append(error)
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
            companion_at_exact_fixed_point=True,
        ),
    )


def test_true_world_code_voltage_gate_broadcasts_and_population_reorder():
    codes = np.array([*CODES, -1], np.int64)
    worlds = np.stack((codes, np.r_[np.roll(codes[:9], 1), -1], np.r_[codes[:9][::-1], -1]))[
        None, :, :
    ]
    voltage = np.array(
        [
            [-0.080, -0.060, -0.040, -0.020, 0.0, 0.020, 0.040, 0.060, -0.030, 0.0],
            [-0.100, -0.070, -0.050, -0.030, -0.010, 0.010, 0.030, 0.050, -0.020, 0.0],
        ]
    )[:, None, :]
    gates = np.stack(
        [np.stack((np.full(10, 0.2 + 0.1 * j), np.full(10, 0.7 - 0.1 * j))) for j in range(3)]
    )[None, :, :, :]
    gates[..., -1] = 0
    assert potassium.domain_valid(gates, voltage, worlds, xp=np)
    target, tau = potassium.kinetics(voltage, worlds, xp=np)
    derivative = potassium.rhs(gates, voltage, worlds, xp=np)
    assert target.shape == tau.shape == derivative.shape == (2, 3, 2, 10)
    evidence(
        "worlds",
        dict(status="actual_captured", independent_worlds=6),
        dict(target=target, tau_s=tau, derivative=derivative),
    )
    for i in range(2):
        for j in range(3):
            for k in range(9):
                name = NAME_BY_CODE[int(worlds[0, j, k])]
                expected = reference.kinetics(float(voltage[i, 0, k]), name)
                close(target[i, j, :, k], expected["target"], "gate_atol")
                close(tau[i, j, :, k], expected["tau_s"], "tau_atol_s")
                close(
                    derivative[i, j, :, k],
                    reference.rhs(gates[0, j, :, k].tolist(), float(voltage[i, 0, k]), name),
                    "rate_atol_per_s",
                )
    order = np.array([8, 2, 0, 5, 1, 7, 4, 6, 3, 9])
    np.testing.assert_array_equal(
        potassium.rhs(gates[..., order], voltage[..., order], worlds[..., order], xp=np),
        derivative[..., order],
    )
    assert (
        np.all(target[..., -1] == 0)
        and np.all(tau[..., -1] == 1)
        and np.all(derivative[..., -1] == 0)
    )
    evidence("worlds", dict(status="passed", independent_worlds=6, reordered_populations="exact"))


@pytest.mark.parametrize(
    "failure",
    [
        "voltage_low",
        "voltage_high",
        "voltage_nan",
        "gate_low",
        "gate_high",
        "gate_nan",
        "shared_zero",
        "unknown_code",
        "float_code",
        "bool_code",
        "pad_voltage",
        "pad_gate",
        "bad_gate_axis",
        "bool_gates",
    ],
)
def test_invalid_domain_and_explicit_negative_padding_rejected(failure):
    gates, voltage, codes = (
        np.array([[0.2, 0], [0.7, 0]]),
        np.array([-0.080, 0]),
        np.array([24, -1]),
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
    elif failure == "gate_nan":
        gates[1, 0] = np.nan
    elif failure == "shared_zero":
        codes[0] = 0
    elif failure == "unknown_code":
        codes[0] = -2
    elif failure == "float_code":
        codes = codes.astype(float)
    elif failure == "bool_code":
        codes = codes.astype(bool)
    elif failure == "pad_voltage":
        voltage[1] = 0.010
    elif failure == "pad_gate":
        gates[0, 1] = 0.1
    elif failure == "bad_gate_axis":
        gates = np.zeros((3, 2))
    else:
        gates = gates.astype(bool)
    assert not potassium.domain_valid(gates, voltage, codes, xp=np)


def test_empty_populations_and_wholly_inactive_layouts_are_neutral():
    for n in (0, 3):
        voltage, codes, gates = np.zeros((2, n)), np.full(n, -1, np.int64), np.zeros((2, 2, n))
        assert potassium.domain_valid(gates, voltage, codes, xp=np)
        target, tau = potassium.kinetics(voltage, codes, xp=np)
        assert target.shape == tau.shape == (2, 2, n)
        assert np.all(target == 0) and np.all(tau == 1)
        assert np.all(potassium.rhs(gates, voltage, codes, xp=np) == 0)
        assert np.all(potassium.opening(gates, codes, xp=np) == 0)


def test_jax_eager_jit_vmap_rhs_opening_and_strict_domain():
    import jax
    import jax.numpy as jnp

    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    codes = np.array([*CODES, -1], np.int64)
    voltage = np.array(
        [
            [-0.080, -0.060, -0.040, -0.020, 0.0, 0.020, 0.040, 0.060, -0.030, 0.0],
            [-0.100, -0.070, -0.050, -0.030, -0.010, -0.080, 0.030, 0.050, -0.020, 0.0],
        ]
    )
    gates = np.broadcast_to(np.array([0.2, 0.7])[:, None], (2, 10)).copy()
    gates[:, -1] = 0
    expected = potassium.kinetics(voltage, codes, xp=np)
    compiled = jax.jit(potassium.kinetics)(voltage, codes)
    mapped = jax.jit(jax.vmap(lambda v: potassium.kinetics(v, codes)))(voltage)
    for actual in (compiled, mapped, potassium.kinetics(jnp.asarray(voltage), jnp.asarray(codes))):
        close(np.asarray(actual[0]), expected[0], "gate_atol")
        close(np.asarray(actual[1]), expected[1], "tau_atol_s")
    close(
        np.asarray(jax.jit(potassium.rhs)(gates, voltage, codes)),
        potassium.rhs(gates, voltage, codes, xp=np),
        "rate_atol_per_s",
    )
    close(
        np.asarray(jax.jit(potassium.opening)(gates, codes)),
        potassium.opening(gates, codes, xp=np),
        "opening_atol",
    )
    valid = jax.jit(potassium.domain_valid)
    assert bool(valid(gates, voltage, codes))
    wrong = codes.copy()
    wrong[0] = 0
    assert not bool(valid(gates, voltage, wrong))
    bad = gates.copy()
    bad[1, 0] = np.nan
    assert not bool(valid(bad, voltage, codes))
    bad_v = voltage.copy()
    bad_v[0, -1] = 0.01
    assert not bool(valid(gates, bad_v, codes))
    evidence(
        "jax-arrays", dict(status="passed", jit=True, eager=True, vmap=True, strict_rejection=True)
    )


def test_jax_voltage_derivatives_at_transitions_and_slow_source_tail():
    import jax
    import jax.numpy as jnp

    points = (*TRANSITIONS, ("Kv3p3", -0.119))
    voltage = np.array([v for _, v in points])
    codes = np.array([CODE_BY_NAME[name] for name, _ in points])
    derivative = jax.jit(
        jax.jacfwd(lambda v: jnp.concatenate(potassium.kinetics(v, codes), axis=-2))
    )(voltage)
    assert np.isfinite(np.asarray(derivative)).all()
    h = 1e-7
    expected = []
    for name, value in points:
        a, b = reference.kinetics(value + h, name), reference.kinetics(value - h, name)
        expected.append((np.r_[a["target"], a["tau_s"]] - np.r_[b["target"], b["tau_s"]]) / (2 * h))
    actual = np.stack([np.asarray(derivative)[:, i, i] for i in range(len(points))], axis=-1)
    np.testing.assert_allclose(actual, np.asarray(expected).T, rtol=3e-7, atol=3e-8)
    evidence(
        "jax-derivatives",
        dict(status="passed", transition_and_tail_cases=len(points), difference_step_V=h),
    )
