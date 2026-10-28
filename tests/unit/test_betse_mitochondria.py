"""Native Mito timing/charge, independent Decimal, physical units and CPU JAX."""

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_mitochondria as mito
from validation.organelles import betse_mitochondria_reference as reference
from validation.organelles.betse_mitochondria_fixtures import base, cases, neutral_relaxation

CASES = cases()
ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/organelles/betse_mitochondria_protocol.json").read_text())
TOL = PROTOCOL["tolerances"]


def evidence(name, record):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / ("betse-mito-" + name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False) + "\n"
        )


def native_file(name):
    directory = os.environ.get("CELLS_BETSE_MITO_NATIVE_CAPTURE")
    if not directory:
        pytest.skip("Bounded wrapper supplies authenticated native Mito captures")
    return json.loads((Path(directory) / (name + ".json")).read_text())


def prepared(raw=None, padding=0):
    raw = deepcopy(base() if raw is None else raw)
    count, ns = len(raw["cell_volume_m3"]), len(raw["species_valence"])
    t, p = mito.bind(
        raw["species_valence"],
        raw["moving_species"],
        raw["cell_volume_m3"] + [0.0] * padding,
        raw["cell_area_m2"] + [0.0] * padding,
        active=[True] * count + [False] * padding,
        **{
            k: raw[k]
            for k in (
                "specific_capacitance_F_m2",
                "temperature_K",
                "membrane_thickness_m",
                "faraday_C_mol",
                "gas_constant_J_mol_K",
            )
        },
    )

    def pad(value):
        a = np.asarray(value, dtype=float)
        return np.pad(a, [(0, 0)] * (a.ndim - 1) + [(0, padding)])

    s = mito.initial_state(pad(raw["cytosol_mM"]), t, xp=np)
    s = s._replace(
        mitochondria_mM=pad(raw["mitochondria_mM"]),
        charge_C=pad(raw["charge_C"]),
        voltage_V=pad(raw["voltage_V"]),
    )
    if "live_cytosol_volume_m3" in raw:
        p = p._replace(cytosol_volume_m3=pad(raw["live_cytosol_volume_m3"]))
    for key in ("diffusivity_m2_s", "base_diffusivity_m2_s", "channel_diffusivity_m2_s"):
        if key in raw:
            p = p._replace(**{key: pad(raw[key])})
    extra = pad(raw["extra_charge_density_C_m3"])
    if raw.get("refresh_before"):
        s = mito.refresh_voltage(s, t, p, extra, xp=np)
    assert s.cytosol_mM.shape == (ns, count + padding)
    return raw, s, t, p, extra


def result_dict(result):
    return {
        **{k: np.asarray(v).tolist() for k, v in result.state._asdict().items()},
        **{k: np.asarray(v).tolist() for k, v in result._asdict().items() if k != "state"},
    }


def close_field(key, actual, expected):
    atol = (
        TOL["charge_atol_C"]
        if key.endswith("_C")
        else TOL["voltage_atol_V"]
        if key.endswith("_V")
        else TOL["density_atol_mol_m2_s"]
        if key == "flux_density_mol_m2_s"
        else TOL["material_atol_fmol"]
        if key == "transferred_fmol"
        else TOL["concentration_atol_mM"]
    )
    expected = np.asarray(expected).reshape(np.shape(actual))
    np.testing.assert_allclose(actual, expected, atol=atol, rtol=TOL["relative"])


def balances(before, result, t, p):
    b = mito.material_balances(before, result, t, p, xp=np)
    for key, value in b._asdict().items():
        np.testing.assert_allclose(
            value,
            0,
            atol=TOL["charge_atol_C"] if key.endswith("_C") else TOL["material_atol_fmol"],
            rtol=0,
        )


@pytest.mark.parametrize("raw", CASES, ids=[r["name"] for r in CASES])
def test_independent_decimal_ordered_flux_and_charge(raw):
    raw, s, t, p, extra = prepared(raw)
    assert mito.LAW_ID == PROTOCOL["law_id"]
    assert mito.domain_valid(s, t, p, extra, raw["dt_s"], xp=np)
    result = mito.step(s, t, p, extra, raw["dt_s"], xp=np)
    expected = reference.evaluate(raw)
    evidence(raw["name"], dict(input=raw, actual=result_dict(result), expected=expected))
    for key, value in result_dict(result).items():
        close_field(key, value, expected[key])
    balances(s, result, t, p)


@pytest.mark.parametrize("name", [r["name"] for r in CASES])
def test_actual_native_capture_matches_complete_update(name):
    captured = native_file(name)
    raw, s, t, p, extra = prepared(captured["input"])
    result = mito.step(s, t, p, extra, raw["dt_s"], xp=np)
    assert captured["status"] == "passed"
    for key, value in result.state._asdict().items():
        close_field(key, value, captured["after"][key])
    for key in (
        "flux_density_mol_m2_s",
        "transferred_fmol",
        "voltage_used_V",
        "physical_charge_before_C",
        "cache_charge_adjustment_C",
    ):
        close_field(key, getattr(result, key), captured[key])
    initial = captured["native_initial"]
    assert not initial["extra_charge_exists"]
    np.testing.assert_array_equal(initial["charge_C"], 0)
    np.testing.assert_array_equal(initial["voltage_V"], 0)
    np.testing.assert_array_equal(initial["mitochondria_mM"], raw["cytosol_mM"])
    for key in ("diffusivity_m2_s", "base_diffusivity_m2_s", "channel_diffusivity_m2_s"):
        np.testing.assert_array_equal(initial[key], 1e-19)
    for key, expected in reference.geometry(raw).items():
        if key != "cytosol_volume_m3":
            np.testing.assert_allclose(
                initial[
                    {
                        "mitochondria_volume_m3": "mit_volume_m3",
                        "mitochondria_area_m2": "mit_area_m2",
                    }.get(key, key)
                ],
                expected,
                rtol=3e-15,
                atol=0,
            )


def test_native_manifest_source_constants_and_broken_branches():
    r = native_file("source-manifest")
    assert (
        r["status"] == "passed" and r["no_production_or_jax_imports"] and not r["native_simulation"]
    )
    assert r["revision"] == PROTOCOL["native_source"]["revision"]
    assert r["native_parameter_constants"] == dict(F=96485, R=8.314, tm=7.5e-9)
    directory = Path(os.environ["CELLS_BETSE_MITO_NATIVE_CAPTURE"])
    for relative, expected in PROTOCOL["native_source"]["source_sha256"].items():
        assert (
            hashlib.sha256((directory / "upstream" / relative).read_bytes()).hexdigest() == expected
        )
    assert r["successful_cases"] == len(CASES) and r["observed_native_limits"] == 7
    for name in r["native_limits"]:
        assert native_file(name)["status"] == "observed_native_limit"


def test_cached_zero_init_nonce_order_and_no_implicit_refresh():
    raw, s, t, p, extra = prepared(
        next(r for r in CASES if r["name"] == "extra-charge-before-refresh")
    )
    result = mito.step(s, t, p, extra, raw["dt_s"], xp=np)
    baseline = mito.step(s, t, p, np.zeros_like(extra), raw["dt_s"], xp=np)
    np.testing.assert_array_equal(result.flux_density_mol_m2_s, baseline.flux_density_mol_m2_s)
    assert np.max(np.abs(result.state.voltage_V - baseline.state.voltage_V)) > 0.05
    voltage, used = np.zeros_like(s.voltage_V), []
    for _ in raw["moving_species"]:
        voltage = voltage + mito.NATIVE_NONCE
        used.append(voltage.copy())
    np.testing.assert_array_equal(result.voltage_used_V, np.array(used))
    refreshed = mito.refresh_voltage(s, t, p, extra, xp=np)
    altered = mito.step(refreshed, t, p, extra, raw["dt_s"], xp=np)
    assert np.max(np.abs(altered.flux_density_mol_m2_s - result.flux_density_mol_m2_s)) > 1e-10
    for actual, expected in zip(s, prepared(raw)[1], strict=True):
        np.testing.assert_array_equal(actual, expected)


def test_native_geometry_amount_copy_unused_channels_and_padding():
    raw, s, t, p, extra = prepared(padding=2)
    assert mito.domain_valid(s, t, p, extra, raw["dt_s"], xp=np)
    initial = mito.initial_state(s.cytosol_mM, t, xp=np)
    np.testing.assert_array_equal(initial.mitochondria_mM, initial.cytosol_mM)
    np.testing.assert_array_equal(p.mitochondria_volume_m3, 0.5 * p.cytosol_volume_m3)
    total = (
        initial.cytosol_mM * p.cytosol_volume_m3
        + initial.mitochondria_mM * p.mitochondria_volume_m3
    )
    np.testing.assert_allclose(
        total, 1.5 * initial.cytosol_mM * p.cytosol_volume_m3, rtol=3e-15, atol=0
    )
    result = mito.step(s, t, p, extra, raw["dt_s"], xp=np)
    for value in (
        *result.state,
        result.flux_density_mol_m2_s,
        result.transferred_fmol,
        result.voltage_used_V,
    ):
        np.testing.assert_array_equal(value[..., -2:], 0)
    modified = p._replace(
        base_diffusivity_m2_s=p.base_diffusivity_m2_s * 1e10,
        channel_diffusivity_m2_s=p.channel_diffusivity_m2_s * 1e8,
    )
    again = mito.step(s, t, modified, extra, raw["dt_s"], xp=np)
    for a, b in zip(result.state, again.state, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize(
    "fault",
    [
        "negative_cyto",
        "negative_mito",
        "nonfinite",
        "cache_nan",
        "rho_nan",
        "dt_negative",
        "dt_nan",
        "temperature",
        "faraday",
        "gas",
        "volume",
        "capacitance",
        "diffusion",
        "base_diffusion",
        "channel_diffusion",
        "padding_c",
        "padding_v",
        "padding_rho",
        "singularity",
        "negative_trial",
        "float32",
        "integer",
        "shape",
    ],
)
def test_invalid_complete_trial_rejects_without_mutation(fault):
    raw, s, t, p, extra = prepared(padding=1)
    dt = raw["dt_s"]
    if fault in ("negative_cyto", "negative_mito", "nonfinite", "padding_c"):
        key = "cytosol_mM" if fault != "negative_mito" else "mitochondria_mM"
        value = np.array(getattr(s, key), copy=True)
        value[0, -1 if fault == "padding_c" else 0] = (
            np.nan if fault == "nonfinite" else 1e-30 if fault == "padding_c" else -1.0
        )
        s = s._replace(**{key: value})
    elif fault in ("cache_nan", "padding_v", "singularity"):
        v = s.voltage_V.copy()
        v[-1 if fault == "padding_v" else 0] = (
            np.nan if fault == "cache_nan" else 1e-30 if fault == "padding_v" else -1e-25
        )
        s = s._replace(voltage_V=v)
    elif fault in ("rho_nan", "padding_rho"):
        extra[-1 if fault == "padding_rho" else 0] = np.nan if fault == "rho_nan" else 1e-30
    elif fault in ("dt_negative", "dt_nan", "negative_trial"):
        dt = -1.0 if fault == "dt_negative" else np.nan if fault == "dt_nan" else 1e6
    elif fault in ("temperature", "faraday", "gas"):
        p = p._replace(
            **{
                {
                    "temperature": "temperature_K",
                    "faraday": "faraday_C_mol",
                    "gas": "gas_constant_J_mol_K",
                }[fault]: -1.0
            }
        )
    elif fault in ("volume", "capacitance", "diffusion", "base_diffusion", "channel_diffusion"):
        key = {
            "volume": "mitochondria_volume_m3",
            "capacitance": "capacitance_F",
            "diffusion": "diffusivity_m2_s",
            "base_diffusion": "base_diffusivity_m2_s",
            "channel_diffusion": "channel_diffusivity_m2_s",
        }[fault]
        value = np.array(getattr(p, key), copy=True)
        value.flat[0] = -1
        p = p._replace(**{key: value})
    elif fault in ("float32", "integer"):
        s = s._replace(cytosol_mM=s.cytosol_mM.astype(np.float32 if fault == "float32" else int))
    else:
        s = s._replace(cytosol_mM=s.cytosol_mM[:-1])
    snapshot = [value.copy() for value in s]
    with np.errstate(all="ignore"):
        assert not mito.domain_valid(s, t, p, extra, dt, xp=np)
    for value, before in zip(s, snapshot, strict=True):
        np.testing.assert_array_equal(value, before)


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate_moving",
        "moving_range",
        "moving_bool",
        "valence_float",
        "negative_volume",
        "zero_cm",
        "boolean_geometry",
        "bad_temperature",
        "bad_faraday",
        "bad_gas",
    ],
)
def test_binding_rejects_invalid_native_parameters(fault):
    z, moving, volume, area = [1, -1], [0, 1], [1e-15], [1e-9]
    kwargs = dict(specific_capacitance_F_m2=0.05, temperature_K=310.0)
    if fault == "duplicate_moving":
        moving = [0, 0]
    elif fault == "moving_range":
        moving = [2]
    elif fault == "moving_bool":
        moving = [True]
    elif fault == "valence_float":
        z = [1.0, -1.0]
    elif fault == "negative_volume":
        volume = [-1e-15]
    elif fault == "boolean_geometry":
        volume = [True]
    else:
        kwargs[
            {
                "zero_cm": "specific_capacitance_F_m2",
                "bad_temperature": "temperature_K",
                "bad_faraday": "faraday_C_mol",
                "bad_gas": "gas_constant_J_mol_K",
            }[fault]
        ] = 0.0
    with pytest.raises(ValueError):
        mito.bind(z, moving, volume, area, **kwargs)


def short_history(xp=np):
    captured = native_file("short-ordered-trajectory")
    raw, s, t, p, extra = prepared(captured["input"])
    records = [s]
    for extra, multiplier in zip(
        captured["extra_charge_density_C_m3"], captured["diffusivity_multiplier"], strict=True
    ):
        pstep = p._replace(diffusivity_m2_s=p.diffusivity_m2_s * multiplier)
        result = mito.step(s, t, pstep, np.array(extra), raw["dt_s"], xp=xp)
        if xp is np:
            assert mito.domain_valid(s, t, pstep, np.array(extra), raw["dt_s"], xp=np)
            balances(s, result, t, pstep)
        s = result.state
        records.append(s)
    return captured, records, t, p


def test_twelve_native_steps_stored_state_restart_and_external_charge_lag(tmp_path):
    captured, records, t, p = short_history()
    for expected, actual in zip(captured["history"], records, strict=True):
        for key, value in actual._asdict().items():
            close_field(key, value, expected[key])
    checkpoint = tmp_path / "mito-state.npz"
    np.savez(checkpoint, **records[5]._asdict())
    with np.load(checkpoint) as values:
        restored = mito.State(*(values[key].copy() for key in mito.State._fields))
    for index in range(5, 12):
        extra = np.array(captured["extra_charge_density_C_m3"][index])
        pstep = p._replace(
            diffusivity_m2_s=p.diffusivity_m2_s * captured["diffusivity_multiplier"][index]
        )
        restored = mito.step(restored, t, pstep, extra, captured["input"]["dt_s"], xp=np).state
        for a, b in zip(restored, records[index + 1], strict=True):
            np.testing.assert_array_equal(a, b)
    for record in records[9:]:
        np.testing.assert_array_equal(record.cytosol_mM, records[8].cytosol_mM)
    evidence(
        "short-trajectory",
        dict(
            physical_horizon_s=captured["physical_horizon_s"],
            exact_stored_state_restart=True,
            history=[{k: v.tolist() for k, v in s._asdict().items()} for s in records],
        ),
    )


def test_actual_default_neutral_pair_physical_time_and_euler_order():
    row = neutral_relaxation()
    plan = reference.neutral_profile(row, [0.0])
    evidence("neutral-plan", dict(input=row, **plan, refinements=[32, 64, 128]))
    errors, profiles = [], []
    for count in (32, 64, 128):
        row["dt_s"] = plan["tau_s"] / count
        raw, s, t, p, extra = prepared(row)
        values, times, material = (
            [[float(s.cytosol_mM[0, 0]), float(s.mitochondria_mM[0, 0])]],
            [0.0],
            [],
        )
        for index in range(1, 12 * count + 1):
            assert mito.domain_valid(s, t, p, extra, raw["dt_s"], xp=np)
            step = mito.step(s, t, p, extra, raw["dt_s"], xp=np)
            balances(s, step, t, p)
            s = step.state
            values.append([float(s.cytosol_mM[0, 0]), float(s.mitochondria_mM[0, 0])])
            times.append(index * raw["dt_s"])
            material.append(
                float(
                    (
                        s.cytosol_mM * p.cytosol_volume_m3
                        + s.mitochondria_mM * p.mitochondria_volume_m3
                    ).sum()
                    / 1e-15
                    - 25.0
                )
            )
            assert np.all(s.charge_C == 0) and np.all(s.voltage_V == 0)
        expected = reference.neutral_profile(raw, times)
        error = float(np.max(np.abs(np.asarray(values) - expected["concentration_mM"])))
        native = native_file("neutral-physical-" + str(count))
        np.testing.assert_allclose(values, native["concentration_mM"], rtol=5e-12, atol=3e-12)
        record = dict(
            input=raw,
            times_s=times,
            concentration_mM=values,
            analytic=expected,
            maximum_error_mM=error,
            maximum_material_residual_fmol=float(np.max(np.abs(material))),
        )
        evidence("neutral-physical-" + str(count), record)
        assert min(np.ravel(values)) >= 0 and max(np.abs(material)) < TOL["material_atol_fmol"]
        assert abs(values[-1][0] - values[-1][1]) < 1.3e-4
        errors.append(error)
        profiles.append(record)
    assert errors[1] < errors[0] / 1.9 and errors[2] < errors[1] / 1.9
    evidence(
        "neutral-physical-summary",
        dict(
            tau_s=plan["tau_s"],
            physical_horizon_s=plan["horizon_s"],
            actual_default_D_m2_s=1e-19,
            maximum_errors_mM=errors,
            orders=np.log2(np.array(errors[:-1]) / errors[1:]).tolist(),
            scope="Single neutral finite pair only; no full mitochondrial/cell settling",
        ),
    )


def test_empty_cells_and_empty_moving_list_refresh_remain_explicit():
    t, p = mito.bind([0], [0], [], [], specific_capacitance_F_m2=0.05, temperature_K=310.0)
    s = mito.initial_state(np.empty((1, 0)), t, xp=np)
    assert mito.domain_valid(s, t, p, np.empty(0), 0.0, xp=np)
    assert mito.step(s, t, p, np.empty(0), 0.0, xp=np).state.voltage_V.shape == (0,)
    assert not mito.domain_valid(s, t, p._replace(faraday_C_mol=np.nan), np.empty(0), 0.0, xp=np)
    assert not mito.domain_valid(s, t, p, np.empty(0), -1.0, xp=np)
    raw, s, t, p, extra = prepared(next(r for r in CASES if r["name"] == "no-moving-ions"))
    extra[:] = -7500
    result = mito.step(s, t, p, extra, raw["dt_s"], xp=np)
    np.testing.assert_array_equal(result.state.cytosol_mM, s.cytosol_mM)
    assert np.max(np.abs(result.state.voltage_V)) > 0.05


def test_jax_compiled_batch_paired_amount_charge_and_padding():
    import jax
    import jax.numpy as jnp

    raw, s, t, p, extra = prepared(padding=1)
    state = mito.State(*(np.stack([value, value, value]) for value in s))
    rho = np.stack([extra, extra, extra])
    rho[1, :3] = [-7500, -3500, 2000]
    pb = p._replace(temperature_K=np.array([[280.0], [310.0], [320.0]]))
    fn = jax.jit(
        lambda state, rho: (
            mito.step(state, t, pb, rho, raw["dt_s"], xp=jnp),
            mito.domain_valid(state, t, pb, rho, raw["dt_s"], xp=jnp),
        )
    )
    result, valid = fn(state, rho)
    assert bool(valid) and all(device.platform == "cpu" for device in jax.devices())
    expected = mito.step(state, t, pb, rho, raw["dt_s"], xp=np)
    for key, value in result.state._asdict().items():
        close_field(key, value, getattr(expected.state, key))
    for key in mito.Step._fields[1:]:
        close_field(key, getattr(result, key), getattr(expected, key))
    balances(state, result, t, pb)
    evidence(
        "jax-batch",
        dict(
            valid=bool(valid),
            state={k: np.asarray(v).tolist() for k, v in result.state._asdict().items()},
            backend_devices=[d.platform for d in jax.devices()],
        ),
    )


def test_jax_vmap_singular_world_isolation():
    import jax
    import jax.numpy as jnp

    raw, s, t, p, extra = prepared()
    states = mito.State(*(np.stack([v, v, v]) for v in s))
    states.voltage_V[0, 0] = -1e-25
    fn = jax.jit(
        jax.vmap(
            lambda state: (
                mito.step(state, t, p, extra, raw["dt_s"], xp=jnp),
                mito.domain_valid(state, t, p, extra, raw["dt_s"], xp=jnp),
            )
        )
    )
    actual, valid = fn(states)
    np.testing.assert_array_equal(valid, [False, True, True])
    for value in actual.state:
        np.testing.assert_array_equal(value[1], value[2])
    evidence("jax-isolation", dict(valid=np.asarray(valid).tolist(), rejected_singular_world=True))


def test_jax_scan_native_timing_and_pure_continuation():
    import jax
    import jax.numpy as jnp

    captured = native_file("short-ordered-trajectory")
    raw, s, t, p, _ = prepared(captured["input"])
    controls = (
        np.array(captured["extra_charge_density_C_m3"]),
        np.array(captured["diffusivity_multiplier"]),
    )

    def run(state, controls):
        def advance(state, control):
            rho, multiplier = control
            result = mito.step(
                state,
                t,
                p._replace(diffusivity_m2_s=p.diffusivity_m2_s * multiplier),
                rho,
                raw["dt_s"],
                xp=jnp,
            )
            return result.state, result.state

        return jax.lax.scan(advance, state, controls)

    last, history = jax.jit(run)(s, controls)
    for key, values in history._asdict().items():
        close_field(key, values, [v[key] for v in captured["history"][1:]])
    first, _ = jax.jit(run)(s, tuple(v[:5] for v in controls))
    resumed, _ = jax.jit(run)(first, tuple(v[5:] for v in controls))
    for a, b in zip(last, resumed, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        "jax-scan",
        dict(
            physical_horizon_s=captured["physical_horizon_s"],
            exact_continuation=True,
            final={k: np.asarray(v).tolist() for k, v in last._asdict().items()},
        ),
    )


def test_jax_empty_kernel_and_external_charge_voltage_gradient():
    import jax
    import jax.numpy as jnp

    raw, s, t, p, extra = prepared()
    derivative = jax.jit(
        jax.jacrev(lambda rho: mito.refresh_voltage(s, t, p, rho, xp=jnp).voltage_V)
    )(extra)
    np.testing.assert_allclose(
        derivative, np.diag(p.mitochondria_volume_m3 / p.capacitance_F), rtol=5e-12, atol=1e-15
    )
    t0, p0 = mito.bind([0], [], [], [], specific_capacitance_F_m2=0.05, temperature_K=310.0)
    s0 = mito.initial_state(np.empty((1, 0)), t0, xp=np)
    valid = jax.jit(
        lambda constant: mito.domain_valid(
            s0, t0, p0._replace(gas_constant_J_mol_K=constant), jnp.empty(0), 0.0, xp=jnp
        )
    )
    assert bool(valid(8.314)) and not bool(valid(jnp.nan))
    evidence(
        "jax-empty-gradient",
        dict(
            derivative=np.asarray(derivative).tolist(),
            empty_valid=True,
            invalid_constant_rejected=True,
        ),
    )
