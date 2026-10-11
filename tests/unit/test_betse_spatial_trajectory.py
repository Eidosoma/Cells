"""Freely evolving native spatial compatibility, device parity and full replay."""

import copy
import json
import os
from pathlib import Path

import jax
import numpy as np
import pytest
from scipy.ndimage import gaussian_filter

from cells.numerics import betse_spatial as model
from tests.unit.test_spatial_calcium import same as bits
from validation.betse.spatial_trajectory import fixtures, reference
from validation.betse.tissue_contact import reference as native_reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
PROTOCOL = json.loads(fixtures.PROTOCOL_PATH.read_text())
TOL = PROTOCOL["tolerances"]
CASES = [
    (name, index) for name in ("uniform", "diffusion", "junction", "combined") for index in (0, 1)
]
RUN = jax.jit(model.trajectory, static_argnums=(3,))
MAPPED = jax.jit(model.trajectories, static_argnums=(3,))
FIELDS = jax.jit(jax.vmap(model.field, in_axes=(0, None)))


def evidence(name, record, arrays=None):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


@pytest.fixture(scope="module")
def captured():
    rows, protocol = fixtures.capture()
    for case, index in CASES:
        key = f"{case}/step-{index}"
        row, trace = rows[key + "/observed"]
        other, _ = rows[key + "/bare"]
        for name in ("fixture", "geometry", "parameters", "arrays", "species", "final"):
            assert row[name] == other[name]
        native_reference.check(row, trace, protocol)
    return rows, protocol


@pytest.fixture(scope="module")
def device():
    jax.config.update("jax_enable_x64", True)
    return jax.devices(BACKEND)[0]


def selected(function, args, device, *static):
    result = jax.block_until_ready(function(*jax.device_put(args, device), *static))
    for value in jax.tree.leaves(result):
        assert value.device.platform == BACKEND
        assert value.dtype.kind != "f" or value.dtype == np.float64
    return jax.tree.map(np.asarray, result)


def observed_history(states, rates, fields, p):
    rows = []
    for i in range(len(states.step_count)):
        state, rate, field = (
            jax.tree.map(lambda v, i=i: v[i], item) for item in (states, rates, fields)
        )
        rows.append(fixtures.comparison(state, rate, field, p))
    return {name: np.stack([r[name] for r in rows]) for name in rows[0]}


def saved_arrays(states, observed):
    return {
        **{"state__" + k: v for k, v in states._asdict().items()},
        **{"observed__" + k: v for k, v in observed.items()},
    }


@pytest.fixture(scope="module")
def computed(captured, device):
    rows, protocol = captured
    results = {}
    for case, index in CASES:
        row, trace = rows[f"{case}/step-{index}/observed"]
        initial, p = fixtures.prepare(row, trace, protocol)
        final, (states, rates, accepted), valid = selected(
            RUN,
            (initial, p, np.asarray(row["dt_s"])),
            device,
            row["steps"],
        )
        assert valid and accepted.all()
        fields = selected(FIELDS, (states, p), device)
        observed = observed_history(states, rates, fields, p)
        results[(case, index)] = dict(
            row=row,
            trace=trace,
            initial=initial,
            layout=p,
            final=final,
            states=states,
            rates=rates,
            observed=observed,
        )
    return results


def test_protocol_keeps_native_identity_and_scope():
    assert model.MODEL_ID == "betse_spatial_passive@1"
    assert PROTOCOL["automatic_followup"] is False
    assert PROTOCOL["expected_cpu_skips"] == 1
    assert set(model.State._fields) == {
        "cell_concentration",
        "membrane_concentration",
        "outside_concentration",
        "membrane_inward_fmol",
        "junction_outward_fmol",
        "reservoir_reset_fmol",
        "stencil_exchange_fmol",
        "step_count",
        "elapsed_s",
    }


@pytest.mark.parametrize("kind", ["constant", "linear", "bilinear", "quadratic"])
def test_independent_dirichlet_solve(kind, device):
    y, x = np.mgrid[:5, :7].astype(float)
    targets = dict(
        constant=0.003 + 0 * x,
        linear=0.001 * x - 0.002 * y,
        bilinear=0.0001 * x * y,
        quadratic=0.0001 * (x * x - y * y),
    )
    target = targets[kind]
    result = selected(jax.jit(model.boundary_field), (target,), device)
    np.testing.assert_allclose(result, target, rtol=0, atol=TOL["boundary_atol_V"])
    values = target.copy()
    values[1:-1, 1:-1] = 100.0
    bits(selected(jax.jit(model.boundary_field), (values,), device), result)


def test_screened_smoothing_and_native_edge_convention(device):
    source = np.zeros((10, 10))
    source[0, 1] = 1
    source[5, 5] = -2
    result = selected(jax.jit(model.smooth), (source,), device)
    np.testing.assert_allclose(
        result, gaussian_filter(source, 1, mode="constant"), rtol=3e-15, atol=3e-17
    )
    y, x = np.mgrid[:5, :7].astype(float)
    dx, _ = selected(jax.jit(lambda v: model.gradient(v, 1.0, native_edges=True)), (x,), device)
    _, dy = selected(jax.jit(lambda v: model.gradient(v, 1.0, native_edges=True)), (y,), device)
    np.testing.assert_array_equal(dx + dy, native_reference.native_divergence(x, y, 1.0))
    assert (dx + dy)[0, 0] == -2 and (dx + dy)[2, 2] == 2


def test_rebuilt_boundary_operator_and_initial_field(captured, device):
    rows, protocol = captured
    errors = {}
    for case, index in CASES:
        row, trace = rows[f"{case}/step-{index}/observed"]
        initial, p = fixtures.prepare(row, trace, protocol)
        matrix = model.dirichlet_operator(p.boundary_values.shape)
        native_inverse = np.asarray(row["geometry"]["lapENVinv"]) / float(p.spacing) ** 2
        np.testing.assert_allclose(
            matrix @ native_inverse, np.eye(matrix.shape[0]), rtol=0, atol=3e-12
        )
        actual = selected(jax.jit(model.field), (initial, p), device)
        target = native_reference.native_field(
            {"cc_cells": initial.cell_concentration, "cc_env": initial.outside_concentration}, row
        )
        for actual_value, name in (
            (actual.membrane_voltage_V, "vm"),
            (actual.boundary_potential_V.ravel(), "Phi_b"),
            (actual.outside_potential_V.ravel(), "v_env"),
        ):
            np.testing.assert_allclose(
                actual_value, target[name], rtol=TOL["voltage_rtol"], atol=TOL["voltage_atol_V"]
            )
            errors[case + str(index) + name] = float(np.max(abs(actual_value - target[name])))
    evidence(
        "native-spatial-boundary-field",
        dict(status="passed", max_errors_V=errors, imported_native_inverse=False),
    )


@pytest.mark.parametrize("case,index", CASES)
def test_complete_freely_evolving_native_trajectory(case, index, computed):
    value = computed[(case, index)]
    report = reference.compare(
        value["row"], value["trace"], TOL, value["states"]._asdict(), value["observed"]
    )
    report.update(backend=BACKEND, state_fields=list(model.State._fields))
    evidence(
        f"native-spatial-trajectory-{case}-{index}",
        report,
        saved_arrays(value["states"], value["observed"]),
    )


@pytest.mark.parametrize("case,index", CASES)
def test_numpy_evolution_independently_matches_native(case, index, captured):
    rows, protocol = captured
    row, trace = rows[f"{case}/step-{index}/observed"]
    initial, p = fixtures.prepare(row, trace, protocol)
    state = initial
    histories = []
    rates = []
    fields = []
    for _ in range(row["steps"]):
        state, rate, valid = model.step(state, p, row["dt_s"], xp=np)
        assert valid
        histories.append(state)
        rates.append(rate)
        fields.append(model.field(state, p, xp=np))
    states, rates, fields = (
        jax.tree.map(lambda *v: np.stack(v), *items) for items in (histories, rates, fields)
    )
    reference.compare(row, trace, TOL, states._asdict(), observed_history(states, rates, fields, p))


@pytest.mark.parametrize(
    "fault",
    [
        "cell_owner",
        "outside_owner",
        "partner",
        "volume",
        "permeability",
        "asymmetric",
        "nan",
        "scalar_shape",
        "grid",
        "moving",
    ],
)
def test_invalid_layouts_are_rejected(fault, captured):
    rows, protocol = captured
    row, trace = rows["combined/step-0/observed"]
    _, p = fixtures.prepare(row, trace, protocol)
    if fault in ("cell_owner", "outside_owner", "partner"):
        v = getattr(p, fault).copy()
        v[0] = 999
        p = p._replace(**{fault: v})
    elif fault == "volume":
        p = p._replace(cell_volume=-p.cell_volume)
    elif fault == "permeability":
        p = p._replace(membrane_permeability=-np.ones_like(p.membrane_permeability))
    elif fault == "asymmetric":
        v = p.junction_open.copy()
        v[0] *= 0.5
        p = p._replace(junction_open=v)
    elif fault == "nan":
        p = p._replace(temperature=np.asarray(np.nan))
    elif fault == "scalar_shape":
        p = p._replace(temperature=np.full((1,), float(p.temperature)))
    elif fault == "grid":
        p = p._replace(boundary_values=np.zeros((2, 10)))
    else:
        p = p._replace(moving=np.zeros_like(p.moving))
    with pytest.raises(ValueError):
        model.validate_layout(p)


@pytest.mark.parametrize(
    "fault", ["zero_dt", "negative_dt", "large_dt", "negative_state", "nan_state"]
)
def test_invalid_trial_retains_all_state(fault, captured, device):
    rows, protocol = captured
    row, trace = rows["combined/step-0/observed"]
    state, p = fixtures.prepare(row, trace, protocol)
    dt = {"zero_dt": 0.0, "negative_dt": -1e-6, "large_dt": 1e6}.get(fault, row["dt_s"])
    if fault in ("negative_state", "nan_state"):
        value = state.cell_concentration.copy()
        value[0, 0] = -1 if fault == "negative_state" else np.nan
        state = state._replace(cell_concentration=value)
    result, _, valid = selected(jax.jit(model.step), (state, p, np.asarray(dt)), device)
    assert not valid
    bits(result, state)


@pytest.mark.parametrize(
    "fault", ["cell", "membrane_lag", "voltage", "flux", "reset_ledger", "stencil_ledger"]
)
def test_corrupted_trajectory_is_rejected(fault, computed):
    v = computed[("combined", 0)]
    states, observed = copy.deepcopy(v["states"]._asdict()), copy.deepcopy(v["observed"])
    if fault.endswith("ledger"):
        name = "reservoir_reset_fmol" if fault == "reset_ledger" else "stencil_exchange_fmol"
        states[name][-1, 0, 0] += 1e-6
    else:
        name = {
            "cell": "cc_cells",
            "membrane_lag": "cc_at_mem",
            "voltage": "vm",
            "flux": "fluxes_mem",
        }[fault]
        observed[name].reshape(len(observed[name]), -1)[-1, 0] += 0.001
    with pytest.raises(AssertionError):
        reference.compare(v["row"], v["trace"], TOL, states, observed)


def test_omitted_lag_is_detected_and_accounting_is_complete(captured, computed):
    v = computed[("combined", 0)]
    p = v["layout"]
    state = v["initial"]
    for _ in range(v["row"]["steps"]):
        state, _, valid = model.step(state, p, v["row"]["dt_s"], xp=np)
        assert valid
        state = state._replace(membrane_concentration=state.cell_concentration[:, p.cell_owner])
    target = v["trace"]["cc_at_mem"][
        np.flatnonzero((v["trace"]["method"] == 3) & v["trace"]["after"])[-1]
    ]
    with pytest.raises(AssertionError):
        np.testing.assert_allclose(
            state.membrane_concentration,
            target,
            rtol=TOL["concentration_rtol"],
            atol=TOL["concentration_atol_mM"],
        )
    for value in computed.values():
        for residual in model.accounting(
            value["initial"], value["final"], value["layout"]
        ).values():
            np.testing.assert_allclose(residual, 0, rtol=0, atol=TOL["material_atol_fmol"])
    evidence(
        "native-spatial-negative-controls",
        dict(
            status="passed",
            omitted_lag_detected=True,
            explicit_reservoir_and_stencil_accounting=True,
        ),
    )


def test_complete_disk_restart_windows_and_mapped_partitions(computed, device, tmp_path):
    v = computed[("combined", 1)]
    p = v["layout"]
    dt = np.asarray(v["row"]["dt_s"])
    first, _, ok = selected(RUN, (v["initial"], p, dt), device, 7)
    assert ok
    np.savez_compressed(tmp_path / "state.npz", **first._asdict())
    with np.load(tmp_path / "state.npz", allow_pickle=False) as saved:
        resumed = model.State(*(saved[name] for name in model.State._fields))
    resumed, _, ok = selected(RUN, (resumed, p, dt), device, 4)
    assert ok
    resumed, _, ok = selected(RUN, (resumed, p, dt), device, 5)
    assert ok
    bits(resumed, v["final"])
    values = [computed[(case, 0)] for case in ("combined", "diffusion", "junction")]
    states = jax.tree.map(lambda *x: np.stack(x), *(v["initial"] for v in values))
    layouts = jax.tree.map(lambda *x: np.stack(x), *(v["layout"] for v in values))
    mapped_dt = np.asarray(1e-6)
    together, _, valid = selected(MAPPED, (states, layouts, mapped_dt), device, 8)
    assert valid.all()
    for i, value in enumerate(values):
        bits(jax.tree.map(lambda x, i=i: x[i], together), value["final"])
    order = np.array([2, 0, 1])
    reordered, _, valid = selected(
        MAPPED, (*jax.tree.map(lambda x: x[order], (states, layouts)), mapped_dt), device, 8
    )
    assert valid.all()
    bits(reordered, jax.tree.map(lambda x: x[order], together))
    for i in range(3):
        alone, _, valid = selected(
            MAPPED,
            (*jax.tree.map(lambda x, i=i: x[i : i + 1], (states, layouts)), mapped_dt),
            device,
            8,
        )
        assert valid.all()
        bits(alone, jax.tree.map(lambda x, i=i: x[i : i + 1], together))
    evidence(
        "native-spatial-replay",
        dict(
            status="passed",
            comparison="bitwise",
            state_fields=list(model.State._fields),
            disk=True,
            windows=[7, 4, 5],
            mapped_worlds=3,
            reordered=True,
            partitions=True,
        ),
    )


def compare_cpu_gpu_arrays(actual, saved, area, tol=TOL):
    """Physical-unit comparison reused by short and extended trajectory panels."""
    count = 0
    assert set(actual) == set(saved)
    for key, x in actual.items():
        expected = saved[key]
        assert np.asarray(x).shape == np.asarray(expected).shape, key
        assert np.isfinite(x).all() and np.isfinite(expected).all(), key
        if x.dtype.kind in "biu":
            np.testing.assert_array_equal(x, expected)
        else:
            if key.endswith("elapsed_s"):
                atol = tol.get("clock_atol_s", 3e-20)
            elif "fmol" in key:
                atol = tol["cpu_gpu_ledger_atol_fmol"]
            elif "concentration" in key or "__cc_" in key:
                atol = tol["cpu_gpu_concentration_atol_mM"]
            elif "__E_env" in key:
                atol = tol["field_atol_V_m"]
            elif "__rho_cells" in key:
                atol = tol["charge_density_atol_C_m3"]
            elif key.endswith(("fluxes_mem", "fluxes_gj")):
                scale = area * 1e15
                x, expected = x * scale, expected * scale
                atol = tol["flux_atol_fmol_s"]
            elif "fluxes_env" in key:
                atol = tol["environment_flux_atol_mol_m2_s"]
            else:
                atol = tol["voltage_atol_V"]
            np.testing.assert_allclose(
                x, expected, rtol=tol["cpu_gpu_rtol"], atol=atol, err_msg=key
            )
        count += x.size
    return count


def test_cpu_gpu_complete_trajectories(computed):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert EVIDENCE
    count = 0
    for (case, index), value in computed.items():
        actual = saved_arrays(value["states"], value["observed"])
        path = Path(EVIDENCE) / "cpu" / f"native-spatial-trajectory-{case}-{index}.npz"
        with np.load(path, allow_pickle=False) as saved:
            count += compare_cpu_gpu_arrays(actual, saved, value["layout"].membrane_area)
    evidence("native-spatial-trajectory-cpu-gpu", dict(status="passed", compared_scalars=count))
