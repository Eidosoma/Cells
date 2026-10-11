"""Native storage-rounding regression and authenticated comparison-only reuse."""

import importlib.util
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("coupled_replay_regression", HERE / "check.py")
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)
resume = check.u.private("coupled_comparison_reuse", HERE.parent / "junction_trajectory/resume.py")


@pytest.fixture
def parent():
    name = os.environ.get("CELLS_NATIVE_COUPLED_FAILED_PANEL")
    if not name:
        pytest.skip("Authenticated failed native-coupled panel required")
    return Path(name)


def witness(parent, case, index):
    protocol = check.u.read(parent / "protocol.json")
    path = parent / "native" / case / f"step-{index}/observed"
    row = check.u.read(path / "result.json")
    protocol |= {
        key: row["case"][key]
        for key in ("duration_s", "observation_step_s", "restart_time_s")
        if key in row["case"]
    }
    for name, key in (
        ("trace.npz", "trace_sha256"),
        ("gates.npz", "gates_sha256"),
        ("preparation.json", "preparation_sha256"),
    ):
        assert check.u.sha(path / name) == row[key]
    with np.load(path / "trace.npz", allow_pickle=False) as f:
        trace = dict(f)
    with np.load(path / "gates.npz", allow_pickle=False) as f:
        gates = dict(f)
    prepared = check.u.read(path / "preparation.json")
    c = check.bind(prepared, row, trace, protocol)
    times, actual, balances = check.native_values(c, row, trace, gates, protocol)
    return c, row, trace, protocol, times, actual, balances


@pytest.mark.parametrize(
    "case", ["single_na", "network_nakcl", "network_cl_k_na", "disconnected", "half_block"]
)
@pytest.mark.parametrize("index", [0, 1, 2])
def test_saved_native_replay_all_cases_cpu(parent, case, index, tmp_path):
    c, row, trace, protocol, _, actual, balances = witness(parent, case, index)
    corrected, lagged, device = check.adapter.replay(c, protocol, row["dt_s"], "cpu")
    errors = check.ref.physical.difference(c, corrected, actual)
    check.u.write(
        tmp_path / "comparison.json",
        {"case": case, "index": index, "errors": errors, "balances": balances, "device": device},
    )
    check.bounded(errors, protocol, "replay_")
    delta = check.ref.physical.unpack(c, actual)[0]
    expected_lag = np.concatenate((np.zeros_like(delta[:1]), delta[:-1]))
    np.testing.assert_allclose(
        lagged, expected_lag, rtol=0, atol=protocol["tolerances"]["replay_amount_fmol"]
    )
    np.testing.assert_array_equal(
        c["initial_concentration_mM"], trace["initial_cc_cells"][c["indices"]]
    )


def test_preserved_original_failure_is_rejected_without_relaxation(parent):
    c, _, _, p, _, actual, _ = witness(parent, "network_cl_k_na", 2)
    with np.load(parent / "comparison/network_cl_k_na/replay-2-cpu.npz") as f:
        old = f["values"]
    errors = check.ref.physical.difference(c, old, actual)
    assert p["tolerances"]["replay_gate"] == 5e-10
    assert errors["gate"] == pytest.approx(5.5906057561117e-10, rel=1e-10)
    with pytest.raises(ValueError, match="replay_gate"):
        check.bounded(errors, p, "replay_")


def test_source_concentration_additions_reproduce_recorded_rounding(parent, tmp_path):
    c, row, trace, _, _, _, _ = witness(parent, "network_cl_k_na", 2)
    prepared = check.u.read(parent / "native/network_cl_k_na/step-2/observed/preparation.json")
    g = prepared["geometry"]
    matrix, area, volume = (np.asarray(g[k]) for k in ("M_sum_mems", "mem_sa", "cell_vol"))
    initial = c["initial_concentration_mM"]
    direct, incremental = initial.copy(), np.zeros_like(initial)
    max_rounding = 0.0
    for density, expected in zip(
        trace["transport_fluxes_gj"][:, c["indices"]],
        trace["after_cc_cells"][:, c["indices"]],
        strict=True,
    ):
        change = row["dt_s"] * ((matrix @ (-density * area).T).T / volume)
        direct = direct + change
        incremental = incremental + change
        np.testing.assert_array_equal(direct, expected)
        max_rounding = max(max_rounding, float(np.max(np.abs(initial + incremental - expected))))
    assert max_rounding > 1e-12
    check.u.write(
        tmp_path / "rounding.json",
        {"source_update_exact": True, "accumulated_increment_difference_mM": max_rounding},
    )


def test_physical_definitions_and_independent_rhs_unchanged(parent):
    old = check.u.private(
        "frozen_prior_coupled_checks",
        parent / "source/validation/betse/junction_native_coupled/check.py",
    )
    for case in check.u.read(parent / "protocol.json")["cases"]:
        c, row, trace, p, _, _, _ = witness(parent, case["id"], 0)
        prepared = check.u.read(parent / "native" / case["id"] / "step-0/observed/preparation.json")
        prior_c = old.bind(prepared, row, trace, p)
        assert set(c) - set(prior_c) == {"initial_concentration_mM"}
        for key in prior_c:
            np.testing.assert_array_equal(prior_c[key], c[key])
        for backend in ("cpu", "gpu"):
            assert check.definition(c, p, p["cells_steps_s"][0], backend) == old.definition(
                prior_c, p, p["cells_steps_s"][0], backend
            )
        size = c["initial_amount_fmol"].size + c["permeability_m_s"].size + len(c["initial_gate"])
        y = np.r_[np.zeros(size), c["initial_gate"]]
        np.testing.assert_array_equal(
            check.ref.physical.rhs(c, c["opening"] * c["block"], y),
            old.ref.physical.rhs(prior_c, prior_c["opening"] * prior_c["block"], y),
        )


@pytest.mark.skipif(os.environ.get("CELLS_TEST_GPU") != "1", reason="Dedicated L4 regression")
@pytest.mark.parametrize(
    "case", ["single_na", "network_nakcl", "network_cl_k_na", "disconnected", "half_block"]
)
def test_gpu_corrected_finest_replays(parent, case, tmp_path):
    c, row, _, p, _, actual, _ = witness(parent, case, 2)
    histories = {}
    for backend in ("cpu", "gpu"):
        histories[backend], _, device = check.adapter.replay(c, p, row["dt_s"], backend)
        assert device["platform"] == backend and device["dtype"] == "float64"
        check.bounded(check.ref.physical.difference(c, histories[backend], actual), p, "replay_")
    error = float(np.max(np.abs(histories["cpu"] - histories["gpu"])))
    check.u.write(
        tmp_path / "comparison.json",
        {
            "case": case,
            "cpu_gpu_error": error,
            "gpu_native_errors": check.ref.physical.difference(c, histories["gpu"], actual),
        },
    )
    assert error <= p["tolerances"]["cpu_gpu_atol"]


def registration(parent):
    value = {
        "panel_kind": "native_coupled",
        "protocol": check.u.read(parent / "protocol.json"),
        "sources_sha256": check.u.sources(),
        "runtime": check.u.runtime(),
    }
    value["resume"] = resume.describe(
        parent,
        value["protocol"],
        value["sources_sha256"],
        value["runtime"],
        comparison_only=True,
        panel_kind="native_coupled",
    )
    return value


def test_complete_native_panel_copies_with_all_gate_traces(parent, tmp_path):
    value = registration(parent)
    receipt = value["resume"]
    assert len(receipt["rows"]) == 30 and receipt["missing_rows"] == []
    assert receipt["native_timeout_seconds"] == receipt["estimated_native_seconds"] == 0
    assert not receipt["reuse_is_numerical_acceptance"]
    resume.stage_complete(tmp_path / "native", value)
    assert check.u.inventory(tmp_path / "native") == check.u.inventory(parent / "native")
    check.u.write(tmp_path / "reuse.json", receipt)


@pytest.mark.parametrize(
    "name",
    [
        "src/cells/core/runner.py",
        "validation/betse/junction_native_coupled/native.py",
        "validation/betse/junction_native_coupled/protocol.json",
        "validation/betse/junction_native_coupled/reference.py",
        "validation/betse/junction_trajectory/reference.py",
    ],
)
def test_reuse_rejects_changed_science(name):
    with pytest.raises(ValueError, match="scientific source changed"):
        resume.compatible_sources(
            {name: "original"}, {name: "changed"}, comparison_only=True, panel_kind="native_coupled"
        )


@pytest.mark.parametrize("corruption", ["gate", "trace", "clock", "missing_pickle"])
def test_reuse_rejects_corrupted_capture(parent, tmp_path, corruption):
    p = check.u.read(parent / "protocol.json")
    name = "half_block/step-0/observed"
    path = tmp_path / "row"
    shutil.copytree(parent / "native" / name, path)
    if corruption in ("gate", "trace"):
        q = path / ("gates.npz" if corruption == "gate" else "trace.npz")
        with q.open("ab") as stream:
            stream.write(b"changed")
    elif corruption == "clock":
        row = check.u.read(path / "result.json")
        row["steps"] = round(p["duration_s"] / row["dt_s"])
        (path / "result.json").unlink()
        check.u.write(path / "result.json", row)
    else:
        (path / "INITS/init_1.betse.gz").unlink()
    with pytest.raises(ValueError):
        resume.complete_row(path, resume.identities(p)[name], p, panel_kind="native_coupled")


def test_reuse_rejects_active_parent(parent, monkeypatch):
    monkeypatch.setattr(resume.os, "kill", lambda pid, signal: None)
    with pytest.raises(ValueError, match="still present"):
        registration(parent)


def test_staging_rejects_changed_receipt_before_copy(parent, tmp_path):
    value = registration(parent)
    value["resume"]["parent_files_sha256"]["native/panel.json"] = "changed"
    with pytest.raises(ValueError, match="Registered comparison evidence changed"):
        resume.stage_complete(tmp_path / "native", value)
    assert not (tmp_path / "native").exists()
