"""Native target/regulator/dispatch evidence, independent arithmetic and CPU JAX."""

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_network_modulation as modulation
from validation.regulation import betse_network_modulation_reference as reference
from validation.regulation.betse_network_modulation_fixtures import (
    base,
    cases,
    channel,
    limitations,
)

CASES = cases()
ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "validation/regulation/betse_network_modulation_protocol.json").read_text()
)


def evidence(name, data):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("betse-network-modulation-" + name + ".json")).write_text(
            json.dumps(data, indent=2, allow_nan=False) + "\n"
        )


def captured(name):
    if not (directory := os.environ.get("CELLS_BETSE_MODULATION_NATIVE_CAPTURE")):
        pytest.skip("Bounded wrapper supplies authenticated native control captures")
    return json.loads((Path(directory) / (name + ".json")).read_text())


def prepare(raw=None, padding=0):
    raw = deepcopy(base() if raw is None else raw)
    count = len(raw["modulators"]) + len(raw["channels"])
    t, p = modulation.bind(
        raw["modulators"],
        raw["channels"],
        raw["species_ids"],
        raw["species_valence"],
        raw["membrane_to_environment"],
        raw["environment_count"],
        raw["ion_ids"],
        tj_targets=raw["tj_targets"],
        channel_targets=raw["channel_targets"],
        rule_capacity=count + padding,
        faraday_C_mol=raw["faraday_C_mol"],
        gas_constant_J_mol_K=raw["gas_constant_J_mol_K"],
        temperature_K=raw["temperature_K"],
    )
    m = len(raw["membrane_to_environment"])
    channels = np.zeros((count + padding, m))
    channels[len(raw["modulators"]) : count] = raw["initial_channel_modulator"]
    controls = modulation.Controls(
        np.asarray(raw["initial_gj"], float),
        np.asarray(raw["initial_nak"], float),
        np.asarray(raw["initial_tj"], float),
        channels,
    )
    return (
        raw,
        np.asarray(raw["sample_mM"], float),
        np.asarray(raw["voltage_V"], float),
        controls,
        t,
        p,
    )


def close(actual, expected, *, diffusivity=False):
    np.testing.assert_allclose(actual, expected, rtol=5e-12, atol=1e-30 if diffusivity else 3e-14)


def drive(raw, controls, t, p, *, xp=np):
    k, m = t.rule_kind.size, t.membrane_to_environment.size
    opening, relative = np.zeros((k, m)), np.zeros((t.ion_active.size, k))
    for i, row in enumerate(raw["channels"], start=len(raw["modulators"])):
        opening[i] = np.asarray(raw["core_P"]) * np.asarray(
            raw["channel_targets"].get(row["name"], [True] * m)
        )
        relative[:, i] = raw["relative_permeability"]
    value = modulation.channel_diffusivity(
        xp.asarray(opening), xp.asarray(relative), controls, t, p, xp=xp
    )
    running = modulation.channel_run_mask(t, initialization=raw["initialization"], xp=xp)
    return xp.where(running[..., None, :, None], value, 0.0)


@pytest.mark.parametrize("raw", CASES, ids=lambda r: r["name"])
def test_native_and_independent_factors_targets_dispatch(raw):
    raw, c, v, controls, t, p = prepare(raw)
    with np.errstate(all="ignore"):
        assert modulation.domain_valid(
            c, v, controls, t, p, initialization=raw["initialization"], xp=np
        )
        factors = modulation.evaluate(c, v, t, p, xp=np)
    after = modulation.apply(
        factors.value, controls, t, initialization=raw["initialization"], xp=np
    )
    expected, native = reference.evaluate(raw), captured(raw["name"])
    assert native["status"] == "passed"
    shape = factors.value.shape
    close(factors.value, np.asarray(expected["factors"]).reshape(shape))
    close(factors.regulation, np.asarray(expected["regulation"]).reshape(shape))
    for key, actual in after._asdict().items():
        expected_field = np.asarray(expected["controls"][key]).reshape(actual.shape)
        close(actual, expected_field)
        for variant in native["variants"].values():
            close(actual, np.asarray(variant["controls"][key]).reshape(actual.shape))
    close(
        drive(raw, after, t, p),
        np.asarray(expected["diffusivity_m2_s"]).reshape(
            (len(raw["ion_ids"]), t.rule_kind.size, v.size)
        ),
        diffusivity=True,
    )
    np.testing.assert_array_equal(
        modulation.channel_run_mask(t, initialization=raw["initialization"], xp=np),
        expected["channel_run"],
    )
    for key in ("gj", "nak", "tj"):
        np.testing.assert_array_equal(
            native["live_after_modulator_init"][key], getattr(controls, key)
        )
    for value in native["initialized_original_arrays"].values():
        np.testing.assert_array_equal(value, np.ones(v.size))
    evidence(
        raw["name"],
        dict(
            status="passed",
            input=raw,
            factors=factors.value.tolist(),
            controls={key: value.tolist() for key, value in after._asdict().items()},
            diffusivity_m2_s=np.asarray(drive(raw, after, t, p)).tolist(),
        ),
    )


def test_order_is_replacement_and_TJ_selection_is_exact():
    raw = next(r for r in CASES if r["name"] == "ordered-overwrites")
    raw, c, v, controls, t, p = prepare(raw)
    factors = modulation.evaluate(c, v, t, p, xp=np)
    after = modulation.apply(factors.value, controls, t, xp=np)
    np.testing.assert_array_equal(after.gj, -0.3)
    np.testing.assert_array_equal(after.nak, 1.8)
    np.testing.assert_array_equal(after.tj[:, ~t.tj_targets], controls.tj[:, ~t.tj_targets])
    np.testing.assert_array_equal(after.tj[0, t.tj_targets], 0.9)
    np.testing.assert_array_equal(after.tj[1, t.tj_targets], -0.7)
    np.testing.assert_array_equal(after.tj[2, t.tj_targets], 0.2)
    for actual, original in zip(
        controls,
        (
            raw["initial_gj"],
            raw["initial_nak"],
            raw["initial_tj"],
            np.zeros_like(controls.channel_modulator),
        ),
        strict=True,
    ):
        np.testing.assert_array_equal(actual, original)


def test_channel_floors_preserve_generated_operator_precedence():
    raw = next(r for r in CASES if r["name"] == "channel-two-floors")
    _, c, v, _, t, p = prepare(raw)
    actual = modulation.evaluate(c, v, t, p, xp=np).value[0, :3]
    a, z = c[3, :3], c[5, 3 + np.asarray(raw["membrane_to_environment"])]
    km_z = 1.2 * np.exp(
        0.5 * v * raw["faraday_C_mol"] / (raw["gas_constant_J_mol_K"] * raw["temperature_K"])
    )
    h1, h2 = 0.8 / (1 + (a / 0.8) ** 2), 0.7 / (1 + z / km_z)
    close(actual, h1 + 0.2 * h2 + 0.3)
    assert np.max(np.abs(actual - (h1 + 0.2) * (h2 + 0.3))) > 0.05


def test_voltage_only_affects_channel_star_and_uses_p_temperature():
    raw = next(r for r in CASES if r["name"] == "channel-voltage-zones")
    _, c, v, _, t, p = prepare(raw)
    normal = modulation.evaluate(c, v, t, p, xp=np).value
    changed = modulation.evaluate(c, -v, t, p, xp=np).value
    assert np.max(np.abs(normal - changed)) > 0.01
    changed_t = modulation.evaluate(
        c, v, t, p._replace(temperature_K=np.asarray([raw["sim_temperature_K"]])), xp=np
    ).value
    assert np.max(np.abs(normal - changed_t)) > 1e-5
    raw = next(r for r in CASES if r["name"] == "zoned-GJ")
    _, c, v, _, t, p = prepare(raw)
    np.testing.assert_array_equal(
        modulation.evaluate(c, v, t, p, xp=np).value, modulation.evaluate(c, -v, t, p, xp=np).value
    )


def test_channel_target_and_express_maxDm_contract():
    raw = next(r for r in CASES if r["name"] == "channel-named-profile")
    _, c, v, controls, t, p = prepare(raw)
    factors = modulation.evaluate(c, v, t, p, xp=np)
    np.testing.assert_array_equal(factors.value[0, :3], 1.0)
    assert not t.channel_targets[0, 1]
    after = modulation.apply(factors.value, controls, t, xp=np)
    assert np.all(drive(raw, after, t, p)[:, 0, 1] == 0)
    native = captured("channel-express-maxDm-unscaled")
    np.testing.assert_array_equal(native["channel_init"]["channel"]["targets"], [0, 1, 2])
    assert native["channel_init"]["channel"]["maxDm"] == 2e-18
    close(native["channel_init"]["channel"]["channelMax"], [4e-19, 0.0, 0.0], diffusivity=True)


@pytest.mark.parametrize("raw", limitations(), ids=lambda r: r["name"])
def test_native_failures_and_partial_state_are_retained(raw):
    native = captured(raw["name"])
    assert native["status"] == (
        "captured_failure" if raw["expected_failure"] else "captured_limitation"
    )
    if raw["name"] == "duplicate-name-overwrite":
        assert list(native["expressions"]["modulators"]) == ["same", "other"]
        np.testing.assert_array_equal(native["variants"]["normal"]["controls"]["gj"], -0.9)
    elif raw["name"] in ("unknown-channel-type", "missing-sim-dyna"):
        # Core registration and legacy sim.dyna lookup are caller-owned; the
        # pure factor binder can use its explicit declarations/profile mask.
        prepare(raw)
    elif raw["name"] == "TJ-uninitialized-live-array":
        assert native["partial_controls"]["tj"] is None
        _, c, v, controls, t, p = prepare(raw)
        assert not modulation.domain_valid(c, v, controls._replace(tj=None), t, p, xp=np)
    else:
        with pytest.raises((ValueError, TypeError)):
            prepare(raw)


def test_padding_and_empty_rules_are_neutral():
    for name in ("mixed-channels-controls", "empty-network"):
        raw = next(r for r in CASES if r["name"] == name)
        _, c, v, controls, t, p = prepare(raw)
        _, _, _, padded, tp, pp = prepare(raw, padding=2)
        original = modulation.evaluate(c, v, t, p, xp=np)
        result = modulation.evaluate(c, v, tp, pp, xp=np)
        close(result.value[:-2], original.value)
        np.testing.assert_array_equal(result.value[-2:], 0.0)
        assert modulation.domain_valid(
            c, v, padded, tp, pp, initialization=raw["initialization"], xp=np
        )
        left = modulation.apply(
            original.value, controls, t, initialization=raw["initialization"], xp=np
        )
        right = modulation.apply(
            result.value, padded, tp, initialization=raw["initialization"], xp=np
        )
        for x, y in zip(left[:3], right[:3], strict=True):
            np.testing.assert_array_equal(x, y)
        np.testing.assert_array_equal(right.channel_modulator[:-2], left.channel_modulator)
        np.testing.assert_array_equal(right.channel_modulator[-2:], 0.0)


def test_batch_parameters_and_phase_are_independent():
    raw = next(r for r in CASES if r["name"] == "mixed-channels-controls")
    _, c, v, controls, t, p = prepare(raw)
    states, voltages = np.stack((c, c * 1.2)), np.stack((v, -v))
    params = p._replace(temperature_K=np.array([[310.0], [285.0]]))
    values = modulation.evaluate(states, voltages, t, params, xp=np)
    after = modulation.apply(
        values.value, controls, t, initialization=np.array([False, True]), xp=np
    )
    for i in range(2):
        separate = modulation.evaluate(
            states[i],
            voltages[i],
            t,
            p._replace(temperature_K=np.asarray([310.0, 285.0])[i]),
            xp=np,
        )
        expected = modulation.apply(separate.value, controls, t, initialization=bool(i), xp=np)
        close(values.value[i], separate.value)
        for left, right in zip(after, expected, strict=True):
            close(left[i], right)


@pytest.mark.parametrize(
    "variant",
    (
        "negative-state",
        "nan-state",
        "nan-voltage",
        "infinite-effect",
        "negative-temperature",
        "zero-R",
        "invalid-owner",
        "bad-rule",
        "nonboolean-phase",
        "padding-control",
        "wrong-shape",
    ),
)
def test_invalid_trial_rejected_without_input_mutation(variant):
    _, c, v, controls, t, p = prepare(padding=1)
    if variant == "negative-state":
        c[0, 0] = -0.1
    elif variant == "nan-state":
        c[0, 0] = np.nan
    elif variant == "nan-voltage":
        v[0] = np.nan
    elif variant == "infinite-effect":
        p = p._replace(max_effect=np.full(p.max_effect.shape, np.inf))
    elif variant == "negative-temperature":
        p = p._replace(temperature_K=np.asarray([-1.0]))
    elif variant == "zero-R":
        p = p._replace(gas_constant_J_mol_K=np.asarray([0.0]))
    elif variant == "invalid-owner":
        t = t._replace(membrane_to_environment=np.array([999, 1, 3]))
    elif variant == "bad-rule":
        t = t._replace(rule_kind=np.array([99, 0]))
    elif variant == "padding-control":
        channels = controls.channel_modulator.copy()
        channels[-1] = 1.0
        controls = controls._replace(channel_modulator=channels)
    elif variant == "wrong-shape":
        c = c[:-1]
    initial = deepcopy((c, v, controls))
    with np.errstate(all="ignore"):
        assert not modulation.domain_valid(
            c,
            v,
            controls,
            t,
            p,
            initialization=0 if variant == "nonboolean-phase" else False,
            xp=np,
        )
    np.testing.assert_array_equal(c, initial[0])
    np.testing.assert_array_equal(v, initial[1])
    for value, before in zip(controls, initial[2], strict=True):
        np.testing.assert_array_equal(value, before)


def test_explicit_profiles_ions_names_and_signed_factors():
    raw = base()
    raw["modulators"][0]["max effect"] = -2.0
    _, c, v, controls, t, p = prepare(raw)
    result = modulation.evaluate(c, v, t, p, xp=np)
    np.testing.assert_array_equal(result.value[0, :3], -2.0)
    assert modulation.domain_valid(c, v, controls, t, p, xp=np)
    raw["modulators"].append(deepcopy(raw["modulators"][0]))
    with pytest.raises(ValueError, match="unique"):
        prepare(raw)
    raw = base()
    raw.update(modulators=[], channels=[channel(**{"apply to": ["named"]})])
    with pytest.raises(ValueError, match="explicit core targets"):
        prepare(raw)
    raw["channels"][0]["apply to"] = "express"
    raw["channel_targets"] = {"channel": [True, False, True]}
    with pytest.raises(ValueError, match="every membrane"):
        prepare(raw)


def test_source_identity_frozen_dependency_and_native_dispatch_order():
    if not (directory := os.environ.get("CELLS_BETSE_MODULATION_NATIVE_CAPTURE")):
        pytest.skip("Bounded wrapper supplies authenticated native control captures")
    folder = Path(directory)
    manifest = json.loads((folder / "source-manifest.json").read_text())
    assert manifest["component_cases"] == len(CASES) == 38
    assert manifest["limitations"] == len(limitations()) == 14
    assert not manifest["production_cells_imported"] and not manifest["jax_imported"]
    for relative, sha in PROTOCOL["native_source"]["source_sha256"].items():
        assert hashlib.sha256((folder / "upstream" / relative).read_bytes()).hexdigest() == sha
    for relative, sha in PROTOCOL["frozen_dependencies"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == sha
    dispatch = json.loads((folder / "dispatch-order.json").read_text())
    for variant, channel_call in (
        ("normal", "run_loop_channels"),
        ("fast", "run_fast_loop_channels"),
    ):
        assert dispatch[variant] == [
            group + "." + method
            for group in ("molecules", "grn")
            for method in (
                "clear_run_loop",
                "run_loop_transporters",
                channel_call,
                "run_loop_modulators",
                "run_loop",
            )
        ]
    source = (ROOT / "validation/regulation/betse_network_modulation_reference.py").read_text()
    assert (
        "import numpy" not in source and "import jax" not in source and "from cells" not in source
    )
    evidence(
        "dispatch-order",
        dict(
            status="passed",
            native_order=dispatch,
            scope=(
                "Authenticated simulator network if-block traces; "
                "core/transport are explicit test doubles"
            ),
        ),
    )


def test_cpu_jax_compiled_batch_and_target_writes():
    import jax
    import jax.numpy as jnp

    raw = next(r for r in CASES if r["name"] == "mixed-channels-controls")
    _, c, v, controls, t, p = prepare(raw, padding=2)
    assert jax.config.x64_enabled and all(d.platform == "cpu" for d in jax.devices())
    t, p, controls = (jax.tree.map(jnp.asarray, x) for x in (t, p, controls))
    states, voltages = np.stack((c, c * 1.2)), np.stack((v, -v))

    def run(c, v):
        factors = modulation.evaluate(c, v, t, p)
        return factors, modulation.apply(
            factors.value, controls, t, initialization=jnp.array([False, True])
        )

    factors, updated = jax.jit(run)(states, voltages)
    expected = modulation.evaluate(states, voltages, t, p, xp=np)
    after = modulation.apply(
        expected.value, controls, t, initialization=np.array([False, True]), xp=np
    )
    close(factors.value, expected.value)
    for left, right in zip(updated, after, strict=True):
        close(left, right)
    evidence(
        "jax-batch",
        dict(status="passed", shape=list(factors.value.shape), backend=jax.default_backend()),
    )


def test_cpu_jax_invalid_world_isolation():
    import jax
    import jax.numpy as jnp

    _, c, v, controls, t, p = prepare(padding=1)
    t, p, controls = (jax.tree.map(jnp.asarray, x) for x in (t, p, controls))
    invalid = c.copy()
    invalid[0, 0] = -0.1
    worlds = jnp.asarray(np.stack((c, invalid, c)))
    actual = jax.jit(
        jax.vmap(lambda state: modulation.domain_valid(state, jnp.asarray(v), controls, t, p))
    )(worlds)
    np.testing.assert_array_equal(actual, [True, False, True])
    factors = jax.jit(
        jax.vmap(lambda state: modulation.evaluate(state, jnp.asarray(v), t, p).value)
    )(worlds)
    np.testing.assert_array_equal(factors[0], factors[2])
    np.testing.assert_array_equal(factors[:, -1], 0.0)


def test_cpu_jax_checkpoint_carry_for_control_sequence():
    import jax
    import jax.numpy as jnp

    raw = next(r for r in CASES if r["name"] == "mixed-channels-controls")
    _, c, v, controls, t, p = prepare(raw)
    t, p, controls = (jax.tree.map(jnp.asarray, x) for x in (t, p, controls))
    samples = jnp.asarray(np.stack([c * value for value in (1.0, 1.2, 0.9, 1.1)]))

    def body(state, sample):
        values = modulation.evaluate(sample, jnp.asarray(v), t, p)
        state = modulation.apply(values.value, state, t)
        return state, values.value

    run = jax.jit(lambda state, rows: jax.lax.scan(body, state, rows))
    full, trace = run(controls, samples)
    half, _ = run(controls, samples[:2])
    restarted, _ = run(half, samples[2:])
    for left, right in zip(full, restarted, strict=True):
        np.testing.assert_array_equal(left, right)
    state = controls
    for sample in samples:
        values = modulation.evaluate(np.asarray(sample), v, t, p, xp=np)
        state = modulation.apply(values.value, state, t, xp=np)
    for left, right in zip(full, state, strict=True):
        close(left, right)
    evidence(
        "jax-control-carry",
        dict(
            status="passed",
            updates=4,
            sample_interval_s=0.05,
            sample_span_s=0.2,
            exact_restart=True,
            shape=list(trace.shape),
            scope=(
                "Prescribed control samples/array carry only; "
                "no kinetic settling or shared checkpoint claim"
            ),
        ),
    )


def test_cpu_jax_voltage_gradient_and_DChan_units():
    import jax
    import jax.numpy as jnp

    raw = next(r for r in CASES if r["name"] == "channel-voltage-zones")
    _, c, v, controls, t, p = prepare(raw)
    t, p, controls = (jax.tree.map(jnp.asarray, x) for x in (t, p, controls))

    def scalar(voltage):
        vm = jnp.asarray(v).at[0].set(voltage)
        return modulation.evaluate(jnp.asarray(c), vm, t, p).value[0, 0]

    derivative = float(jax.jit(jax.grad(scalar))(v[0]))
    h = 1e-6
    finite = float((scalar(v[0] + h) - scalar(v[0] - h)) / (2 * h))
    np.testing.assert_allclose(derivative, finite, rtol=5e-8, atol=1e-10)
    assert derivative != 0 and np.isfinite(derivative)
    factors = modulation.evaluate(jnp.asarray(c), jnp.asarray(v), t, p)
    after = modulation.apply(factors.value, controls, t)
    got = jax.jit(lambda controls: drive(raw, controls, t, p, xp=jnp))(after)
    expected = reference.evaluate(raw)["diffusivity_m2_s"]
    close(got, expected, diffusivity=True)
    evidence(
        "jax-gradient",
        dict(
            status="passed",
            voltage_V=float(v[0]),
            derivative_per_V=derivative,
            finite_difference_per_V=finite,
            step_V=h,
        ),
    )
