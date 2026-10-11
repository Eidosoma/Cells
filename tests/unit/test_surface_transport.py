"""Resolved surfaces: independent physical checks, native contact and CPU/L4 parity."""

import json
import os
import shutil
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.numerics import surface_transport as model
from validation.betse.tissue_contact import reference as native_reference
from validation.tissue import surface_fixtures as fixtures
from validation.tissue import surface_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
PROTOCOL = json.loads(fixtures.PROTOCOL_PATH.read_text())
TOL = PROTOCOL["tolerances"]


def evidence(name, value, arrays=None):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        (path / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(path / (name + ".npz"), **arrays)


def atol(name):
    if name.endswith("_V"):
        return TOL["voltage_atol_V"]
    if name.endswith("_C"):
        return TOL["charge_atol_C"]
    if name.endswith("_J_mol"):
        return TOL["chemical_potential_atol_J_mol"]
    if name.endswith("_A"):
        return TOL["current_atol_A"]
    if name.endswith("_pJ_s"):
        return TOL["power_atol_pJ_s"]
    if name.endswith("_pJ"):
        return TOL["energy_atol_pJ"]
    return TOL["flux_atol_fmol_s"]


def compare(actual, expected):
    for key, value in expected.items():
        np.testing.assert_allclose(
            actual[key], value, rtol=TOL["physical_rtol"], atol=atol(key), err_msg=key
        )


def combined(ci, co, q, phi, opened, junction, p):
    voltage = model.from_cell_charge(q, phi, p)
    rates = model.transport(ci, co, voltage.cell_potential_V, phi, opened, junction, p)
    return voltage, rates


@pytest.fixture(scope="module")
def device():
    jax.config.update("jax_enable_x64", True)
    return jax.devices(BACKEND)[0]


def selected(function, args, device):
    result = jax.jit(function)(*jax.device_put(args, device))
    jax.block_until_ready(result)
    assert all(v.device.platform == BACKEND for v in jax.tree.leaves(result))
    assert all(v.dtype in (jnp.float64, jnp.bool_) for v in jax.tree.leaves(result))
    return jax.tree.map(np.asarray, result)


@pytest.fixture(scope="module")
def computed(device):
    return {
        name: selected(combined, fixtures.arrays(fixtures.definition(name)), device)
        for name in fixtures.CASES
    }


def physical_values(voltage, rates):
    return {
        **{k: v for k, v in voltage._asdict().items() if k != "valid"},
        **{k: v for k, v in rates._asdict().items() if k != "valid"},
    }


def assert_accounting(raw, voltage, rates):
    record = reference.accounting(
        raw, voltage.cell_potential_V, np.asarray(raw["outside_potential_V"]), rates._asdict()
    )
    np.testing.assert_allclose(
        record["material_residual_fmol_s"], 0, rtol=0, atol=TOL["material_rate_atol_fmol_s"]
    )
    assert abs(record["electrochemical_port_power_residual_pJ_s"]) <= TOL["port_power_atol_pJ_s"]
    return record


@pytest.mark.parametrize("name", fixtures.CASES)
def test_independent_surface_laws_and_accounting(name, computed):
    raw = fixtures.definition(name)
    voltage, rates = computed[name]
    assert voltage.valid and rates.valid
    expected = reference.voltage(raw)
    compare(voltage._asdict(), expected)
    compare(
        rates._asdict(),
        reference.transport(
            raw, expected["cell_potential_V"], np.asarray(raw["outside_potential_V"])
        ),
    )
    report = assert_accounting(raw, voltage, rates)
    for prefix in ("membrane", "junction", "face"):
        assert np.min(getattr(rates, prefix + "_dissipation_pJ_s"), initial=0) >= -1e-15
    evidence(name, {"status": "passed", "inputs": raw, **report}, physical_values(voltage, rates))


def test_analytic_capacitor_divider(computed):
    voltage, _ = computed["gradient"]
    # Cell 0: 4 pF facing +1 mV and 6 pF facing -1 mV, total charge -0.4 pC.
    np.testing.assert_allclose(voltage.cell_potential_V[0], -0.0402, rtol=0, atol=3e-17)
    np.testing.assert_allclose(
        voltage.membrane_voltage_V[:2], [-0.0412, -0.0392], rtol=0, atol=3e-17
    )
    assert np.ptp(voltage.membrane_voltage_V[:2]) > 0.001


def test_gauge_change_preserves_physics(device, computed):
    raw = fixtures.definition()
    raw["outside_potential_V"] = (np.asarray(raw["outside_potential_V"]) + 0.012).tolist()
    v, r = selected(combined, fixtures.arrays(raw), device)
    oldv, oldr = computed["gradient"]
    expected = oldv._asdict() | {"cell_potential_V": oldv.cell_potential_V + 0.012}
    compare(v._asdict(), {k: x for k, x in expected.items() if k != "valid"})
    compare(r._asdict(), {k: x for k, x in oldr._asdict().items() if k != "valid"})


def test_patch_subdivision_route_reversal_and_padding(computed):
    v, r = computed["gradient"]
    for name in ("split", "reversed", "padded"):
        other_v, other_r = computed[name]
        for field in ("cell_rate_fmol_s", "outside_rate_fmol_s", "reservoir_supply_fmol_s"):
            original = getattr(r, field)
            np.testing.assert_allclose(
                getattr(other_r, field)[..., : original.shape[-1]], original, rtol=3e-13, atol=3e-15
            )
        np.testing.assert_allclose(
            other_v.cell_potential_V[:2], v.cell_potential_V, rtol=0, atol=3e-17
        )
        np.testing.assert_allclose(
            other_v.capacitor_energy_pJ.sum(), v.capacitor_energy_pJ.sum(), rtol=3e-13, atol=3e-15
        )
        for prefix in ("membrane", "junction", "face"):
            np.testing.assert_allclose(
                getattr(other_r, prefix + "_dissipation_pJ_s").sum(),
                getattr(r, prefix + "_dissipation_pJ_s").sum(),
                rtol=3e-13,
                atol=3e-15,
            )
    for prefix in ("junction", "face"):
        np.testing.assert_allclose(
            getattr(computed["reversed"][1], prefix + "_flux_fmol_s"),
            -getattr(r, prefix + "_flux_fmol_s"),
            rtol=3e-13,
            atol=3e-15,
        )
    padv, padr = computed["padded"]
    assert padv.cell_potential_V[-1] == 0
    for key, value in padr._asdict().items():
        if key != "valid":
            np.testing.assert_array_equal(value[..., -1], 0)


def test_equilibrium_and_transport_blocking(computed):
    for prefix in ("membrane", "junction", "face"):
        np.testing.assert_array_equal(
            getattr(computed["equilibrium"][1], prefix + "_flux_fmol_s"), 0
        )
    for prefix in ("membrane", "junction"):
        np.testing.assert_array_equal(getattr(computed["blocked"][1], prefix + "_flux_fmol_s"), 0)
    assert np.any(computed["blocked"][1].face_flux_fmol_s)
    np.testing.assert_array_equal(computed["closed"][1].reservoir_supply_fmol_s, 0)


def test_one_surface_reduces_to_existing_capacitor_voltage(device):
    raw = fixtures.definition()
    raw["layout"]["membrane_outside"] = [0, 0, 1, 1]
    v, _ = selected(combined, fixtures.arrays(raw), device)
    np.testing.assert_allclose(
        v.membrane_voltage_V, [-0.04, -0.04, -0.06, -0.06], rtol=0, atol=3e-17
    )


def test_reservoir_reset_and_continuous_exchange(device, computed):
    raw = fixtures.definition()
    _, co, _, _, _, _, p = fixtures.arrays(raw)
    volume = np.array([0.1, 0.2, 0.3])
    before = co * volume
    prescribed = co + np.array([[0.5], [-0.5], [0.2]])
    after = selected(model.reset_reservoirs, (before, prescribed, volume, p), device)
    assert after.valid
    np.testing.assert_array_equal(after.amount_fmol[:, :2], before[:, :2])
    np.testing.assert_allclose(
        after.amount_fmol[:, 2], prescribed[:, 2] * volume[2], rtol=0, atol=1e-14
    )
    np.testing.assert_allclose(after.amount_fmol - before, after.supplied_fmol, rtol=0, atol=1e-14)
    assert np.any(after.supplied_fmol > 0) and np.any(after.supplied_fmol < 0)
    v, rates = computed["gradient"]
    np.testing.assert_array_equal(rates.outside_rate_fmol_s[:, p.reservoir], 0)
    assert np.any(abs(rates.reservoir_supply_fmol_s) > 1e-7)
    evidence(
        "reservoir",
        {
            "status": "passed",
            "reset_exchange_fmol": after.supplied_fmol.tolist(),
            **assert_accounting(raw, v, rates),
        },
        after._asdict(),
    )


@pytest.mark.parametrize("fault", ["negative_amount", "negative_target", "zero_volume"])
def test_reservoir_reset_does_not_repair_invalid_state(fault, device):
    *_, p = fixtures.arrays(fixtures.definition())
    amounts, target, volume = np.ones((3, 3)), np.ones((3, 3)), np.ones(3)
    if fault == "negative_amount":
        amounts[0, 2] = -1
    elif fault == "negative_target":
        target[0, 2] = -1
    else:
        volume[2] = 0
    result = selected(model.reset_reservoirs, (amounts, target, volume, p), device)
    assert not result.valid and np.isnan(result.amount_fmol).all()


@pytest.mark.parametrize(
    "fault",
    [
        "owner",
        "orphan",
        "capacity",
        "permeability",
        "reservoir",
        "self_route",
        "duplicate",
        "padding",
    ],
)
def test_invalid_layout_rejected(fault):
    raw = fixtures.definition("padded")
    p = raw["layout"]
    if fault == "owner":
        p["membrane_outside"][0] = 99
    elif fault == "orphan":
        p["membrane_cell"] = [0, 0, 0, 0, 0]
    elif fault == "capacity":
        p["membrane_capacitance"][0] = 0
    elif fault == "permeability":
        p["membrane_permeability"][0][0] = -1
    elif fault == "reservoir":
        p["reservoir"][-1] = True
    elif fault == "self_route":
        p["face_receiver"][0] = p["face_sender"][0]
    elif fault == "duplicate":
        p["face_sender"][1], p["face_receiver"][1] = 0, 1
    else:
        p["membrane_permeability"][0][-1] = 1e-9
    with pytest.raises(ValueError):
        fixtures.arrays(raw)


@pytest.mark.parametrize("fault", ["concentration", "gate", "voltage", "nan"])
def test_runtime_domain_rejection(fault, device):
    raw = fixtures.definition()
    if fault == "concentration":
        raw["co"][0][0] = 0
    elif fault == "gate":
        raw["membrane_open"][0] = 1.1
    elif fault == "voltage":
        raw["charge_C"][0] = 1e-7
    else:
        raw["ci"][0][0] = float("nan")
    _, result = selected(combined, fixtures.arrays(raw), device)
    assert not result.valid and np.isnan(result.cell_rate_fmol_s).all()


def test_batched_world_partition_replay(device):
    worlds = []
    for factor in [0.95, 0.98, 1.0, 1.02, 1.05, 1.08, 1.1]:
        raw = fixtures.definition()
        raw["ci"] = (np.asarray(raw["ci"]) * factor).tolist()
        worlds.append(fixtures.arrays(raw))
    stacked = jax.tree.map(lambda *v: np.stack(v), *worlds)
    fn = jax.jit(jax.vmap(combined))
    batch = jax.block_until_ready(fn(*jax.device_put(stacked, device)))
    assert all(v.device.platform == BACKEND for v in jax.tree.leaves(batch))
    parts = []
    for start, stop in ((0, 3), (3, 7)):
        part = jax.tree.map(lambda v, start=start, stop=stop: v[start:stop], stacked)
        parts.append(jax.block_until_ready(fn(*jax.device_put(part, device))))
    joined = jax.tree.map(lambda *v: np.concatenate([np.asarray(x) for x in v]), *parts)
    for a, b in zip(jax.tree.leaves(batch), jax.tree.leaves(joined), strict=True):
        np.testing.assert_array_equal(np.asarray(a), b)
    for i, world in enumerate(worlds):
        single_v, single_r = selected(combined, world, device)
        batch_v, batch_r = jax.tree.map(lambda v, i=i: np.asarray(v)[i], batch)
        assert single_v.valid and single_r.valid and batch_v.valid and batch_r.valid
        compare(physical_values(batch_v, batch_r), physical_values(single_v, single_r))
    evidence(
        "batch-partitions",
        {"status": "passed", "worlds": len(worlds), "partition": [3, 4], "replay": "bitwise"},
    )


def test_corrupted_accounting_rejected(computed):
    raw = fixtures.definition()
    v, r = computed["gradient"]
    assert_accounting(raw, v, r)
    bad_cell = r.cell_rate_fmol_s.copy()
    bad_cell[0, 0] += 0.001
    bad_supply = r.reservoir_supply_fmol_s.copy()
    bad_supply[0, 2] += 0.001
    for bad in (
        r._replace(cell_rate_fmol_s=bad_cell),
        r._replace(reservoir_supply_fmol_s=bad_supply),
    ):
        with pytest.raises(AssertionError):
            assert_accounting(raw, v, bad)
    q = v.membrane_charge_C.copy()
    q[0] += 1e-14
    with pytest.raises(AssertionError):
        compare({"membrane_charge_C": q}, {"membrane_charge_C": v.membrane_charge_C})
    evidence(
        "negative-controls",
        {"status": "passed", "rejected": ["cell transfer", "reservoir supply", "patch charge"]},
    )


def test_native_geometry_transport_and_voltage_correspondence(device):
    row, trace, native_protocol, directory = fixtures.native_capture()
    native_reference.check(row, trace, native_protocol)
    p, ids, left, right = fixtures.native_layout(row)
    g = row["geometry"]
    owner, outside = p.membrane_cell, p.membrane_outside
    first = np.asarray([np.flatnonzero(owner == i)[0] for i in range(len(p.cell_active))])
    opened = np.ones(len(owner))
    if not row["parameters"]["cluster_open"]:
        opened[np.asarray(g["bflags_mems"], int)] = 0
    errors, flux_values, voltage_values = [], [], []
    shifts = []
    for k in np.flatnonzero((trace["method"] == 0) & ~trace["after"]):
        ion = int(trace["ion"][k])
        species = ids.index(ion)
        ci = trace["cc_at_mem"][k][ids][:, first]
        co = trace["cc_env"][k][ids]
        phi = trace["Phi_b"][k]
        cell = (trace["vm"][k] + phi[outside])[first]
        np.testing.assert_allclose(ci[:, owner], trace["cc_at_mem"][k][ids], rtol=0, atol=0)
        np.testing.assert_allclose(
            cell[owner] - phi[outside], trace["vm"][k], rtol=0, atol=TOL["voltage_atol_V"]
        )
        np.testing.assert_array_equal(outside[left], outside[right])
        result = selected(
            model.transport, (ci, co, cell, phi, opened, trace["gjopen"][k + 1, left], p), device
        )
        assert result.valid
        native_mem = -trace["fluxes_mem"][k, ion] * p.membrane_area * 1e15
        native_gap = (
            (trace["fluxes_gj"][k + 1, ion, left] - trace["fluxes_gj"][k, ion, left])
            * p.junction_area
            * 1e15
        )
        for actual, expected in (
            (result.membrane_flux_fmol_s[species], native_mem),
            (result.junction_flux_fmol_s[species], native_gap),
        ):
            np.testing.assert_allclose(
                actual, expected, rtol=TOL["native_flux_rtol"], atol=TOL["native_flux_atol_fmol_s"]
            )
            errors.append(float(np.max(abs(actual - expected))))
            flux_values.extend(actual.tolist())
        # Native charge/C minus Phi_b lacks the weighted Phi_b term needed when
        # cell ionic charge is explicitly the sum of resolved patch charges.
        charge = trace["rho_cells"][k] * np.asarray(g["cell_vol"])
        physical = selected(model.from_cell_charge, (charge, phi, p), device)
        weights = np.asarray(g["M_sum_mems"]) @ (p.membrane_capacitance * phi[outside])
        weights /= row["parameters"]["cm"] * np.asarray(g["cell_sa"])
        np.testing.assert_allclose(
            physical.membrane_voltage_V - trace["vm"][k],
            weights[owner],
            rtol=2e-12,
            atol=TOL["voltage_atol_V"],
        )
        shifts.extend(weights.tolist())
        voltage_values.extend(result.membrane_voltage_V.tolist())
    assert max(abs(np.asarray(shifts))) > 5e-5
    assert len(p.membrane_active) == 30 and int(p.reservoir.sum()) == 36
    assert len(p.face_active) == 180
    if EVIDENCE:
        target = Path(EVIDENCE) / BACKEND / "native-inputs"
        target.mkdir(parents=True, exist_ok=True)
        for name in ("result.json", "preparation.json", "trace.npz"):
            shutil.copyfile(directory / name, target / name)
    evidence(
        "native-surfaces",
        {
            "status": "passed",
            "native_binding": PROTOCOL["native_binding"],
            "cells": 7,
            "membrane_surfaces": 30,
            "outside_nodes": 100,
            "reservoir_nodes": 36,
            "conservative_grid_faces": 180,
            "native_transport_scalars": len(flux_values),
            "max_native_flux_error_fmol_s": max(errors),
            "max_voltage_contract_difference_V": float(max(abs(np.asarray(shifts)))),
            "field_closure_equivalence": False,
            "outside_coefficients": "synthetic logmean; not native finite differences",
        },
        {"flux_fmol_s": np.asarray(flux_values), "membrane_voltage_V": np.asarray(voltage_values)},
    )


def test_cpu_gpu_saved_physical_values():
    if BACKEND != "gpu":
        pytest.skip("CPU baseline is compared in the registered GPU phase")
    assert EVIDENCE
    count = 0
    for name in (*fixtures.CASES, "reservoir", "native-surfaces"):
        with (
            np.load(Path(EVIDENCE) / "cpu" / (name + ".npz"), allow_pickle=False) as cpu,
            np.load(Path(EVIDENCE) / "gpu" / (name + ".npz"), allow_pickle=False) as gpu,
        ):
            assert set(cpu) == set(gpu)
            for key in cpu:
                np.testing.assert_allclose(
                    gpu[key],
                    cpu[key],
                    rtol=TOL["physical_rtol"],
                    atol=atol(key),
                    err_msg=name + "/" + key,
                )
                count += cpu[key].size
    evidence("surface-cpu-gpu", {"status": "passed", "physical_scalars": count, "tolerances": TOL})
