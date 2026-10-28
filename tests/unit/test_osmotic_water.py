"""Production water kernel versus independent thermodynamics and graph oracles."""

import json
import os
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.assembly.engine import device_for
from cells.numerics import osmotic_water as model
from validation.tissue import water_volume_reference as reference
from validation.tissue.test_water_volume_reference import case

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")


def evidence(name, data):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        (path / ("water-kernel-" + name + ".json")).write_text(
            json.dumps(data, indent=2, allow_nan=False) + "\n"
        )


def variant(name):
    raw = case()
    if name in ("mixed", "mechanical"):
        raw.update(
            initial_volume_pL=[1.1, 2.9],
            bulk_modulus_Pa=[12345.0, 23456.0],
            pressure_offset_Pa=[150.0, -70.0],
        )
    if name in ("empty", "mechanical"):
        raw.update(amount_fmol=[], impermeant_amount_fmol=[0.0, 0.0])
    if name == "branched":
        raw.update(
            initial_volume_pL=[1.0, 3.0, 2.0],
            reference_volume_pL=[1.0, 3.0, 2.0],
            amount_fmol=[[100.0, 300.0, 200.0], [80.0, 200.0, 150.0]],
            impermeant_amount_fmol=[120.0, 100.0, 100.0],
            bulk_modulus_Pa=[0.0] * 3,
            pressure_offset_Pa=[0.0] * 3,
        )
        raw["edges"] = [
            dict(sender=a, receiver=b, area_m2=2e-10, hydraulic_permeability_m_per_Pa_s=1e-12)
            for a, b in ((0, 1), (0, 2), (2, 1), (0, 1))
        ]
    return raw


def prepared(raw, *, padded=False):
    c = reference.bind(raw)
    n, e = len(c["initial_volume_pL"]), len(c["edges"])
    pad = 2 * int(padded)
    volume = np.r_[c["initial_volume_pL"], np.ones(pad)]
    amount = np.pad(c["amount_fmol"], ((0, 0), (0, pad)))
    p = model.validate_parameters(
        model.Parameters(
            np.asarray(c["temperature_K"]),
            np.arange(n + pad) < n,
            np.r_[c["reference_volume_pL"], np.ones(pad)],
            np.full(n + pad, 0.1),
            np.full(n + pad, 10.0),
            np.r_[c["impermeant_amount_fmol"], np.zeros(pad)],
            np.r_[c["bulk_modulus_Pa"], np.zeros(pad)],
            np.r_[c["pressure_offset_Pa"], np.zeros(pad)],
            np.arange(e + pad) < e,
            np.asarray([v["sender"] for v in c["edges"]] + [0] * pad, dtype=np.int64),
            np.asarray([v["receiver"] for v in c["edges"]] + [0] * pad, dtype=np.int64),
            np.asarray(
                [1e15 * v["area_m2"] * v["hydraulic_permeability_m_per_Pa_s"] for v in c["edges"]]
                + [0.0] * pad
            ),
        )
    )
    return volume, amount, p.edge_active.astype(float), p


@pytest.mark.parametrize("name", ["osmotic", "mixed", "mechanical", "empty", "branched"])
@pytest.mark.parametrize("padded", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_independent_stage_and_owned_conservative_graph(name, padded, reverse):
    raw = variant(name)
    if reverse:
        for edge in raw["edges"]:
            edge["sender"], edge["receiver"] = edge["receiver"], edge["sender"]
    v, a, control, p = prepared(raw, padded=padded)
    before = v.copy(), a.copy()
    assert model.domain_valid(v, a, p)
    actual = model.evaluate(v, a, control, p)
    expected = reference.evaluate(raw)
    n, e = len(raw["initial_volume_pL"]), len(raw["edges"])
    for key, wanted in expected.items():
        if key not in actual._fields:
            continue
        value = np.asarray(getattr(actual, key))
        if key in ("mixing_energy_pJ", "elastic_energy_pJ"):
            value = value.sum()
        elif value.ndim:
            value = value[: e if key.startswith("edge_") else n]
        np.testing.assert_allclose(value, wanted, rtol=3e-13, atol=3e-12, err_msg=key)
    np.testing.assert_array_equal(v, before[0])
    np.testing.assert_array_equal(a, before[1])
    np.testing.assert_allclose(actual.volume_rate_pL_s.sum(), 0, rtol=0, atol=2e-15)
    assert np.min(actual.edge_dissipation_pJ_s, initial=0) >= 0
    assert abs(actual.energy_balance_pJ_s) < 3e-10
    if padded:
        assert np.all(actual.volume_rate_pL_s[n:] == 0)
        assert np.all(actual.edge_flow_pL_s[e:] == 0)
    evidence(f"stage-{name}-{int(padded)}-{int(reverse)}", dict(status="passed", inputs=raw))


def test_pressure_gauge_sealed_edges_and_relaxation_bound():
    raw = variant("branched")
    v, a, control, p = prepared(raw)
    first = model.evaluate(v, a, control, p)
    shifted = model.evaluate(
        v, a, control, p._replace(pressure_offset_Pa=p.pressure_offset_Pa + 1e5)
    )
    np.testing.assert_allclose(first.volume_rate_pL_s, shifted.volume_rate_pL_s, rtol=0, atol=3e-16)
    np.testing.assert_allclose(
        first.edge_dissipation_pJ_s, shifted.edge_dissipation_pJ_s, rtol=0, atol=2e-13
    )
    sealed = model.evaluate(v, a, np.zeros_like(control), p)
    assert np.all(sealed.volume_rate_pL_s == 0) and sealed.dissipation_pJ_s == 0
    upper = np.sum(a) + p.impermeant_amount_fmol
    bound = model.relaxation_rate_bound(upper, p)
    columns = []
    for i in range(v.size):
        delta = np.eye(v.size)[i] * 1e-5
        columns.append(
            (
                model.evaluate(v + delta, a, control, p).volume_rate_pL_s
                - model.evaluate(v - delta, a, control, p).volume_rate_pL_s
            )
            / 2e-5
        )
    assert np.max(np.sum(np.abs(np.stack(columns, axis=1)), axis=1)) <= bound
    evidence("pressure-and-bound", dict(status="passed", relaxation_bound_per_s=float(bound)))


@pytest.mark.parametrize("fault", ["negative", "nan", "lower", "upper", "padding", "amount"])
def test_invalid_volume_and_material_domain_is_rejected(fault):
    v, a, _, p = prepared(case(), padded=True)
    if fault == "negative":
        v[0] = -1
    elif fault == "nan":
        v[0] = np.nan
    elif fault == "lower":
        v[0] = p.minimum_volume_pL[0]
    elif fault == "upper":
        v[0] = p.maximum_volume_pL[0]
    elif fault == "padding":
        v[-1] = 1.01
    else:
        a[0, 0] = -1e-30
    assert not model.domain_valid(v, a, p)


def test_compiled_stage_and_independent_world_axes():
    jax.config.update("jax_enable_x64", True)
    v, a, control, p = prepared(variant("branched"), padded=True)
    device = device_for(BACKEND, 0)
    evaluate = jax.jit(
        lambda volume, amount, ctl, q: model.evaluate(volume, amount, ctl, q, xp=jnp)
    )
    inputs = jax.device_put((v, a, control, p), device)
    actual = evaluate(*inputs)
    wanted = model.evaluate(v, a, control, p)
    for got, expected in zip(actual, wanted, strict=True):
        assert got.device.platform == BACKEND
        np.testing.assert_allclose(got, expected, rtol=3e-13, atol=3e-12)
    worlds = np.stack((v, v + np.array([0.1, -0.1, 0, 0, 0])))
    mapped = jax.jit(
        jax.vmap(lambda volume: model.evaluate(volume, inputs[1], inputs[2], inputs[3], xp=jnp))
    )(jax.device_put(worlds, device))
    for i in range(2):
        scalar = evaluate(jax.device_put(worlds[i], device), *inputs[1:])
        for combined, single in zip(mapped, scalar, strict=True):
            np.testing.assert_allclose(combined[i], single, rtol=3e-13, atol=3e-12)
    evidence("compiled", dict(status="passed", backend=BACKEND, worlds=2))
