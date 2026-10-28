"""Independent instantaneous legacy Ca/V-activated K contracts; no invented clock."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.processes import calcium_activated_potassium as potassium
from validation.channels import calcium_activated_potassium_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "validation/channels/calcium_activated_potassium_protocol.json").read_text()
)
TOL = PROTOCOL["tolerances"]


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(directory) / "cpu"
        path.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(path / ("cagpotassium-" + name + ".npz"), **arrays)
        (path / ("cagpotassium-" + name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )


def close(actual, expected):
    np.testing.assert_allclose(actual, expected, rtol=TOL["relative"], atol=TOL["opening_atol"])


def one(calcium=2e-5, voltage=-0.040, temperature=298.15, availability=0.7):
    return dict(
        voltage=np.array([voltage]),
        calcium_free_mM=np.array([calcium]),
        temperature_K=np.array([temperature]),
        law_codes=np.array([39], np.int64),
        availability=np.array([availability]),
    )


def readout(data, *, xp=np):
    return potassium.opening(**{k: v for k, v in data.items() if k != "availability"}, xp=xp)


def test_named_legacy_law_and_zero_state_metadata_are_explicit():
    assert potassium.LAW_ID == PROTOCOL["law_id"]
    assert potassium.LAW_CODE == PROTOCOL["future_code"] == 39
    assert potassium.PAD_CODE == PROTOCOL["padding_code"] == -1
    assert potassium.LAW_PERMEABILITIES == {potassium.LAW_ID: (("K", 1.0),)}
    assert potassium.SENSED_SPECIES == "Ca" and potassium.TRANSPORTED_SPECIES == "K"
    assert potassium.GATE_STATE_COUNT == 0 and potassium.NATIVE_CALCIUM_SCALE == 1e6
    assert potassium.valid_codes(np.array([-1, 39]), xp=np)
    assert not potassium.valid_codes(np.array([0, 38, 40]), xp=np)


@pytest.mark.parametrize("calcium", [0.0, 1e-12, 5e-8, 0.89e-6, 10.22e-6, 0.001, 1e308])
@pytest.mark.parametrize("voltage", [-0.120, -0.040, 0.060])
@pytest.mark.parametrize("temperature", [200.0, 298.15, 400.0])
def test_decimal_literal_numeric_mM_opening_and_control(calcium, voltage, temperature):
    data = one(calcium, voltage, temperature)
    assert potassium.domain_valid(**data, xp=np)
    before = {k: v.copy() for k, v in data.items()}
    expected = reference.evaluate(voltage, calcium, temperature, 0.7)
    with np.errstate(all="raise"):
        actual = readout(data)
        effective = potassium.effective_opening(**data, xp=np)
    close(actual, expected["opening"])
    close(effective, expected["effective_opening"])
    assert 0 < actual[0] < 1 and 0 < effective[0] < actual[0]
    for k, v in before.items():
        np.testing.assert_array_equal(data[k], v)
    evidence(
        f"ordinary-{calcium:.9g}-{voltage:.9g}-{temperature:.9g}",
        dict(
            status="passed",
            calcium_free_mM=calcium,
            voltage_V=voltage,
            temperature_K=temperature,
            opening=float(actual[0]),
            reference=expected,
        ),
    )


@pytest.mark.parametrize("voltage", [-0.120, 0.0, 0.060])
def test_zero_calcium_basal_and_high_calcium_limit_are_source_equations(voltage):
    zero, high = one(0.0, voltage), one(1e200, voltage)
    actual_zero, actual_high = readout(zero)[0], readout(high)[0]
    close(actual_zero, reference.limiting_opening(voltage, 298.15, high_calcium=False))
    close(actual_high, reference.limiting_opening(voltage, 298.15, high_calcium=True))
    assert 0 < actual_zero < actual_high < 1
    calcium = np.r_[0.0, np.geomspace(1e-14, 1e3, 80)]
    values = potassium.opening(
        np.full(calcium.size, voltage), calcium, 298.15, np.full(calcium.size, 39), xp=np
    )
    assert np.all(np.diff(values) >= 0)
    # Source's literal 1e6 multiplier is preserved rather than silently using1e3.
    literal = reference.evaluate(voltage, 1e-6, 298.15)["opening"]
    rescaled = reference.evaluate(voltage, 1e-9, 298.15)["opening"]
    assert abs(literal - rescaled) > 1e-7
    evidence(
        "limits-" + str(voltage),
        dict(
            status="passed",
            voltage_V=voltage,
            basal_opening=float(actual_zero),
            high_calcium_limit=float(actual_high),
            literal_scale_preserved=True,
        ),
    )


def test_true_two_by_three_worlds_population_permutation_and_temperature_dependency():
    codes = np.array([39, 39, 39, -1], np.int64)[None, None, :]
    voltage = np.array([[-0.100, -0.040, 0.020, 0.0], [-0.080, 0.0, 0.060, 0.0]])[:, None, :]
    calcium = np.array(
        [[0.0, 0.89e-6, 1e-4, 0.0], [1e-8, 2e-5, 0.001, 0.0], [1e-6, 1e-4, 0.01, 0.0]]
    )[None, ...]
    temperature = np.array([[298.15, 298.15, 298.15, 298.15], [310.0, 310.0, 310.0, 298.15]])[
        :, None, :
    ]
    availability = np.array([[1.0, 0.4, 0.1, 0.0], [0.0, 0.7, 1.0, 0.0], [0.8, 0.3, 0.0, 0.0]])[
        None, ...
    ]
    data = dict(
        voltage=voltage,
        calcium_free_mM=calcium,
        temperature_K=temperature,
        law_codes=codes,
        availability=availability,
    )
    assert potassium.domain_valid(**data, xp=np)
    p, effective = readout(data), potassium.effective_opening(**data, xp=np)
    assert p.shape == effective.shape == (2, 3, 4)
    for i in range(2):
        for j in range(3):
            for k in range(3):
                expected = reference.evaluate(
                    float(voltage[i, 0, k]),
                    float(calcium[0, j, k]),
                    float(temperature[i, 0, k]),
                    float(availability[0, j, k]),
                )
                close(p[i, j, k], expected["opening"])
                close(effective[i, j, k], expected["effective_opening"])
    assert np.all(p[..., -1] == 0) and np.all(effective[..., -1] == 0)
    order = np.array([2, 0, 1, 3])
    permuted = {k: v[..., order] for k, v in data.items()}
    np.testing.assert_array_equal(
        potassium.effective_opening(**permuted, xp=np), effective[..., order]
    )
    evidence(
        "worlds",
        dict(status="passed", independent_worlds=6, population_order="exact"),
        dict(opening=p, effective_opening=effective),
    )


def test_current_free_cytosolic_owner_readouts_change_without_consuming_calcium():
    free = np.array([[0.0, 2e-5, 8.9e-7], [1e-8, 4e-5, 1e-6]])
    volume = np.array([2.0, 1.0, 0.5])
    owners = np.array([0, 1, 0, 2])
    # The composing model's explicit gather is the owner dependency, not a hidden
    # component state or a claim that bound/total calcium is a valid substitute.
    calcium = (free / volume)[..., owners]
    v = np.array([-0.100, -0.040, 0.020, 0.060])
    code = np.full(4, 39)
    before = free.copy()
    p = potassium.opening(v, calcium, 298.15, code, xp=np)
    for world in range(2):
        for patch, owner in enumerate(owners):
            close(
                p[world, patch],
                reference.evaluate(
                    float(v[patch]), float(free[world, owner] / volume[owner]), 298.15
                )["opening"],
            )
    np.testing.assert_array_equal(free, before)
    changed = calcium.copy()
    changed[..., owners == 0] = 2e-5
    response = potassium.opening(v, changed, 298.15, code, xp=np)
    assert np.all(response[..., owners == 0] != p[..., owners == 0])
    np.testing.assert_array_equal(response[..., owners != 0], p[..., owners != 0])
    evidence(
        "owner-input",
        dict(
            status="passed",
            membrane_cytosol_owner=owners,
            source_free_amount_fmol=free,
            volume_pL=volume,
            calcium_consumed=False,
            gate_state_count=0,
        ),
        dict(calcium_free_mM=calcium, opening=p),
    )


def test_algebraic_calcium_voltage_control_steps_and_twelve_tau_external_input():
    tau = PROTOCOL["external_input_protocol"]["decay_tau_s"]
    times = np.array(
        sorted(
            set(
                [
                    0.0,
                    0.5,
                    np.nextafter(1.0, 0.0),
                    1.0,
                    1.5,
                    2.0,
                    np.nextafter(2.0, np.inf),
                    3.37,
                    np.nextafter(3.37, 0.0),
                    5.13,
                    np.nextafter(5.13, 0.0),
                    *[2 + tau * k for k in (0.1, 0.5, 1, 2, 4, 8, 12)],
                ]
            )
        )
    )
    calcium = np.array([reference.manufactured_calcium_input(float(t)) for t in times])[:, None]
    voltage = np.where(times < 2, -0.080, -0.040)[:, None]
    availability = np.where((times >= 3.37) & (times < 5.13), 0.0, 1.0)[:, None]
    codes = np.array([39])
    temperature = 298.15
    p = potassium.opening(voltage, calcium, temperature, codes, xp=np)
    effective = potassium.effective_opening(
        voltage, calcium, temperature, codes, availability, xp=np
    )
    assert potassium.domain_valid(voltage, calcium, temperature, codes, availability, xp=np)
    for i in range(len(times)):
        expected = reference.evaluate(
            float(voltage[i, 0]), float(calcium[i, 0]), temperature, float(availability[i, 0])
        )
        close(p[i, 0], expected["opening"])
        close(effective[i, 0], expected["effective_opening"])
    np.testing.assert_array_equal(effective[availability[:, 0] == 0], 0)
    # Stateless evaluation retains exact results when the same inputs are
    # revisited after unrelated past inputs, including the zero-Ca baseline.
    order = np.arange(len(times))[::-1]
    revisited = potassium.opening(voltage[order], calcium[order], temperature, codes, xp=np)
    np.testing.assert_array_equal(revisited, p[order])
    assert times[-1] == 2 + 12 * tau
    close(calcium[-1, 0], 2e-5 * np.exp(-12))
    evidence(
        "external-input-history",
        dict(
            status="passed",
            scope=PROTOCOL["external_input_protocol"]["scope"],
            duration_s=float(times[-1]),
            external_decay_tau_s=tau,
            decay_tau_count=12,
            channel_tau=None,
            instantaneous_response=True,
            no_channel_settling_claim=True,
        ),
        dict(
            times_s=times,
            calcium_free_mM=calcium,
            voltage_V=voltage,
            availability=availability,
            opening=p,
            effective_opening=effective,
        ),
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("voltage", -0.121),
        ("voltage", 0.061),
        ("voltage", np.nan),
        ("voltage", True),
        ("calcium_free_mM", -1e-12),
        ("calcium_free_mM", np.nan),
        ("calcium_free_mM", np.inf),
        ("calcium_free_mM", True),
        ("temperature_K", 199.0),
        ("temperature_K", 401.0),
        ("temperature_K", 0.0),
        ("temperature_K", np.nan),
        ("temperature_K", True),
        ("availability", -0.1),
        ("availability", 1.1),
        ("availability", np.nan),
        ("availability", True),
        ("law_codes", np.array([0])),
        ("law_codes", np.array([40])),
        ("law_codes", np.array([39.0])),
        ("law_codes", np.array([True])),
        ("calcium_free_mM", np.array([1e-8, 2e-5])),
        ("availability", np.array([0.2, 0.7])),
    ],
)
def test_strict_domains_types_and_declared_population_count(field, value):
    data = one()
    data[field] = np.array([value]) if field == "voltage" else value
    assert not potassium.domain_valid(**data, xp=np)


@pytest.mark.parametrize("field", ["voltage", "calcium_free_mM", "temperature_K"])
def test_blocking_does_not_excuse_invalid_physical_inputs(field):
    data = one(availability=0.0)
    assert potassium.domain_valid(**data, xp=np)
    np.testing.assert_array_equal(potassium.effective_opening(**data, xp=np), 0)
    data[field] = np.array([np.nan])
    assert not potassium.domain_valid(**data, xp=np)


@pytest.mark.parametrize(
    "field,value",
    [
        ("voltage", 0.001),
        ("calcium_free_mM", 1e-8),
        ("temperature_K", 300.0),
        ("availability", 1.0),
    ],
)
def test_padding_requires_neutral_voltage_calcium_temperature_and_control(field, value):
    data = one(0.0, 0.0, 298.15, 0.0)
    data["law_codes"] = np.array([-1])
    assert potassium.domain_valid(**data, xp=np)
    np.testing.assert_array_equal(readout(data), 0)
    data[field] = np.array([value])
    assert not potassium.domain_valid(**data, xp=np)


def test_empty_and_wholly_padded_layouts_remain_neutral_with_strict_raw_checks():
    for n in (0, 3):
        v, codes = np.zeros((2, n)), np.full(n, -1, np.int64)
        assert potassium.domain_valid(v, 0.0, 298.15, codes, 0.0, xp=np)
        assert np.all(potassium.opening(v, 0.0, 298.15, codes, xp=np) == 0)
        assert np.all(potassium.effective_opening(v, 0.0, 298.15, codes, 0.0, xp=np) == 0)
    empty = np.zeros((2, 0))
    codes = np.empty(0, dtype=np.int64)
    assert not potassium.domain_valid(empty, np.nan, 298.15, codes, 0.0, xp=np)
    assert not potassium.domain_valid(empty, 0.0, 298.15, codes, np.nan, xp=np)
    assert not potassium.domain_valid(empty, 0.0, np.nan, codes, 0.0, xp=np)
    one_population = one()
    one_population["availability"] = np.array([[0.2], [0.7]])
    assert potassium.domain_valid(**one_population, xp=np)
    assert potassium.effective_opening(**one_population, xp=np).shape == (2, 1)


def test_jax_eager_jit_vmap_array_control_domains_and_native_zero_calcium():
    import jax
    import jax.numpy as jnp

    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    codes = np.array([39, 39, 39, -1], np.int64)
    v = np.array([[-0.120, -0.040, 0.060, 0.0], [-0.080, 0.0, 0.020, 0.0]])
    c = np.array([[0.0, 0.89e-6, 1e-4, 0.0], [1e-8, 2e-5, 0.001, 0.0]])
    t = np.array([[298.15, 298.15, 298.15, 298.15], [310.0, 310.0, 310.0, 298.15]])
    a = np.array([[1.0, 0.4, 0.1, 0.0], [0.0, 0.7, 1.0, 0.0]])
    expected = potassium.opening(v, c, t, codes, xp=np)
    actual = jax.jit(potassium.opening)(v, c, t, codes)
    eager = potassium.opening(jnp.asarray(v), jnp.asarray(c), jnp.asarray(t), jnp.asarray(codes))
    mapped = jax.jit(jax.vmap(lambda vv, cc, tt: potassium.opening(vv, cc, tt, codes)))(v, c, t)
    for result in (actual, eager, mapped):
        close(result, expected)
    close(
        jax.jit(potassium.effective_opening)(v, c, t, codes, a),
        potassium.effective_opening(v, c, t, codes, a, xp=np),
    )
    valid = jax.jit(potassium.domain_valid)
    assert bool(valid(v, c, t, codes, a))
    bad = c.copy()
    bad[0, 0] = -1e-12
    assert not bool(valid(v, bad, t, codes, np.zeros_like(a)))
    assert not bool(valid(np.empty(0), np.nan, 298.15, np.empty(0, dtype=np.int64), 0.0))
    assert not bool(valid(np.empty(0), 0.0, 298.15, np.empty(0, dtype=np.int64), np.nan))
    evidence(
        "jax-arrays",
        dict(
            status="passed",
            jit=True,
            eager=True,
            vmap=True,
            zero_calcium=True,
            strict_raw_empty_rejection=True,
        ),
    )


def test_jax_independent_calcium_voltage_temperature_and_availability_derivatives():
    import jax
    import jax.numpy as jnp

    cases = np.array(
        [
            [-0.080, 0.0, 298.15, 0.7],
            [0.0, 0.89e-6, 298.15, 0.4],
            [0.060, 1e-4, 310.0, 1.0],
            [-0.040, 0.001, 400.0, 0.0],
        ]
    )

    def scalar(values):
        v, c, t, a = values
        codes = jnp.array([39], jnp.int64)
        return potassium.effective_opening(
            jnp.array([v]), jnp.array([c]), jnp.array([t]), codes, jnp.array([a])
        )[0]

    gradient = jax.jit(jax.vmap(jax.grad(scalar)))(cases)
    expected = []
    for v, c, t, a in cases:
        oracle = reference.evaluate(float(v), float(c), float(t), float(a))
        expected.append(
            [
                a * oracle["dP_dV_per_V"],
                a * oracle["dP_dCa_per_mM"],
                a * oracle["dP_dT_per_K"],
                oracle["d_effective_d_availability"],
            ]
        )
    assert np.isfinite(gradient).all()
    np.testing.assert_allclose(
        gradient, expected, rtol=TOL["derivative_relative"], atol=TOL["derivative_atol"]
    )
    assert gradient[0, 1] > 0 and gradient[0, 0] > 0
    np.testing.assert_array_equal(np.asarray(gradient)[-1, :3], 0)
    assert gradient[-1, 3] > 0
    evidence(
        "jax-derivatives",
        dict(
            status="passed",
            cases=len(cases),
            independent_analytic=True,
            zero_calcium_derivative_finite=True,
            blocked_physical_sensitivity_zero=True,
        ),
        dict(actual=gradient, expected=expected),
    )
