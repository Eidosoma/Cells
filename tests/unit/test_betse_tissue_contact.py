"""Native spatial semantics and shared transport laws, separately from tissue parity."""

import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.coupling.selective import selective_flux
from cells.processes.electrochemistry import ghk_leak
from validation.betse.tissue_contact import reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "validation/betse/tissue_contact/protocol.json"
PROTOCOL = json.loads(PROTOCOL_PATH.read_text())
BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
CASES = [
    (case["id"], i) for case in PROTOCOL["cases"] for i in range(len(PROTOCOL["native_steps_s"]))
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence(name, record):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")


def load_capture(path, protocol):
    receipt = json.loads((path / "completion.json").read_text())
    assert receipt["status"] == "native_spatial_contact_recorded"
    assert receipt["panel_sha256"] == digest(path / "panel.json")
    panel = json.loads((path / "panel.json").read_text())
    assert panel["protocol"] == protocol
    expected = {
        f"{case['id']}/step-{i}/{mode}"
        for case in protocol["cases"]
        for i in range(len(protocol["native_steps_s"]))
        for mode in ("observed", "bare")
    }
    assert {r["path"] for r in panel["rows"]} == expected
    assert len(panel["rows"]) == len(expected)
    loaded = {}
    for item in panel["rows"]:
        directory = path / item["path"]
        assert digest(directory / "result.json") == item["sha256"]
        row = json.loads((directory / "result.json").read_text())
        assert digest(directory / "preparation.json") == row["preparation_sha256"]
        assert row["hook_restored"] and row["native_pickle_present"]
        trace = None
        if row["mode"] == "observed":
            assert digest(directory / "trace.npz") == row["trace_sha256"]
            with np.load(directory / "trace.npz", allow_pickle=False) as saved:
                trace = {k: saved[k] for k in saved}
        loaded[item["path"]] = row, trace
    return loaded


@pytest.fixture(scope="module")
def captured(tmp_path_factory):
    if BACKEND == "gpu":
        assert EVIDENCE, "GPU phase requires saved CPU native capture"
        path = Path(EVIDENCE) / "cpu/native"
    else:
        root = Path(EVIDENCE) / "cpu" if EVIDENCE else tmp_path_factory.mktemp("betse-tissue")
        root.mkdir(parents=True, exist_ok=True)
        path = root / "native"
        with (
            (root / "native.stdout.log").open("x") as out,
            (root / "native.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    "/mnt/workspaces/Cells/venv-betse/bin/python",
                    "-B",
                    str(ROOT / "validation/betse/tissue_contact/native.py"),
                    "--output",
                    str(path),
                    "--protocol",
                    str(PROTOCOL_PATH),
                ],
                check=True,
                timeout=PROTOCOL["resources"]["native_timeout_seconds"],
                stdout=out,
                stderr=err,
                env=dict(os.environ, MPLBACKEND="Agg", MPLCONFIGDIR=str(root / "matplotlib")),
            )
    return load_capture(path, PROTOCOL)


def test_protocol_keeps_claims_and_recording_explicit():
    assert PROTOCOL["automatic_followup"] is False
    assert len(CASES) == 8
    assert PROTOCOL["duration_s"] == 8e-6
    assert PROTOCOL["native_steps_s"] == [1e-6, 5e-7]
    assert PROTOCOL["expected_cpu_skips"] == 1


def test_native_boundary_derivatives_are_not_a_closed_volume_flux():
    y, x = np.mgrid[:5, :5].astype(float)
    # A linear vector field has divergence 2; the pinned boundary stencil reverses its edges.
    value = reference.native_divergence(x, y, 1.0)
    np.testing.assert_array_equal(value[1:-1, 1:-1], 2.0)
    np.testing.assert_array_equal(value[[0, -1]][:, [0, -1]], -2.0)
    np.testing.assert_array_equal(value[[0, -1], 1:-1], 0.0)
    np.testing.assert_array_equal(value[1:-1, [0, -1]], 0.0)


@pytest.mark.parametrize("case,index", CASES)
def test_native_geometry_lifecycle_and_update_accounting(case, index, captured):
    key = f"{case}/step-{index}"
    row, trace = captured[key + "/observed"]
    report = reference.check(row, trace, PROTOCOL)
    other, _ = captured[key + "/bare"]
    for field in (
        "case",
        "dt_s",
        "steps",
        "fixture",
        "geometry",
        "parameters",
        "arrays",
        "species",
        "final",
    ):
        assert row[field] == other[field], field
    assert max(report["extracellular_owners_per_cell"]) > 1
    if case == "diffusion":
        assert np.max(np.abs(report["reservoir_reset_fmol"])) > 0.01
    if case == "combined":
        assert (
            report["max_within_cell_membrane_voltage_spread_V"]
            > 10 * PROTOCOL["tolerances"]["field_atol_V"]
        )
    evidence(
        "native-spatial-" + case + "-" + str(index), report | {"observer_neutrality": "bitwise"}
    )


@pytest.mark.parametrize("fault", ["owner", "environment", "voltage", "species_clock"])
def test_damaged_native_capture_rejected(fault, captured):
    row, trace = captured["combined/step-0/observed"]
    reference.check(row, trace, PROTOCOL)
    row, trace = copy.deepcopy(row), copy.deepcopy(trace)
    if fault == "owner":
        row["geometry"]["map_mem2ecm"][0] += 1
    elif fault == "environment":
        index = np.flatnonzero((trace["method"] == 1) & trace["after"])[0]
        trace["cc_env"][index, 0, 11] += 0.001
    elif fault == "voltage":
        index = np.flatnonzero((trace["method"] == 3) & trace["after"])[0]
        trace["v_env"][index, 0] += 0.001
    else:
        trace["ion"][0] = row["species"]["Cl"]
    with pytest.raises(AssertionError):
        reference.check(row, trace, PROTOCOL)


def junction(ci, co, voltage, valence, temperature, area, permeability, multiplier):
    return selective_flux(
        ci, co, voltage, valence, temperature, area, permeability, 0.0, 1.0, multiplier
    )


@pytest.fixture(scope="module")
def computed(captured):
    device = jax.devices(BACKEND)[0]
    jax.config.update("jax_enable_x64", True)
    joined = {name: [] for name in ("membrane", "junction")}
    for name, (row, trace) in captured.items():
        if name.endswith("/observed"):
            for kind, values in reference.shared_inputs(row, trace, PROTOCOL).items():
                joined[kind].append(values)
    results = {}
    for name, function in (("membrane", ghk_leak), ("junction", junction)):
        arrays = tuple(np.concatenate(v) for v in zip(*joined[name], strict=True))
        actual = jax.jit(function)(*jax.device_put(arrays[:8], device))
        actual.block_until_ready()
        assert actual.device.platform == BACKEND and actual.dtype == jnp.float64
        results[name] = (np.asarray(actual), *arrays[8:])
    return results


def test_shared_native_transport_laws_on_selected_device(computed):
    errors = {}
    tol = PROTOCOL["tolerances"]
    for name, (actual, native, scalar) in computed.items():
        for expected in (native, scalar):
            np.testing.assert_allclose(
                actual, expected, rtol=tol["flux_rtol"], atol=tol["flux_atol_fmol_s"]
            )
        errors[name] = float(np.max(np.abs(actual - native)))
    if EVIDENCE:
        np.savez_compressed(
            Path(EVIDENCE) / BACKEND / "native-spatial-shared-laws.npz",
            **{k: v[0] for k, v in computed.items()},
        )
    evidence(
        "native-spatial-shared-laws",
        {
            "status": "passed",
            "backend": BACKEND,
            "native_flux_scalars": sum(v[0].size for v in computed.values()),
            "max_native_error_fmol_s": errors,
        },
    )


def test_contact_summary_preserves_scope(captured):
    summary = {}
    for name, (row, trace) in captured.items():
        if trace is not None:
            summary[name] = reference.check(row, trace, PROTOCOL)
    evidence(
        "native-spatial-contact",
        {
            "status": "passed",
            "cases": summary,
            "native_runs": len(captured),
            "observer_pairs": len(summary),
            "scope": PROTOCOL["scope"],
            "scope_exclusions": PROTOCOL["scope_exclusions"],
        },
    )


def test_cpu_gpu_saved_fluxes(computed):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU transport laws")
    assert EVIDENCE
    count = 0
    tol = PROTOCOL["tolerances"]
    with np.load(
        Path(EVIDENCE) / "cpu/native-spatial-shared-laws.npz", allow_pickle=False
    ) as saved:
        for name, (actual, _, _) in computed.items():
            np.testing.assert_allclose(
                actual, saved[name], rtol=tol["cpu_gpu_rtol"], atol=tol["cpu_gpu_atol_fmol_s"]
            )
            count += actual.size
    evidence(
        "native-spatial-cpu-gpu",
        {
            "status": "passed",
            "physical_scalars": count,
            "atol_fmol_s": tol["cpu_gpu_atol_fmol_s"],
            "rtol": tol["cpu_gpu_rtol"],
        },
    )
