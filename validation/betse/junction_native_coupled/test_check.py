"""Saved native witnesses, corruption rejection and ordinary CPU/L4 integration."""

import copy
import importlib.util
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("dynamic_free_voltage_checks", HERE / "check.py")
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def witness(case):
    name = os.environ.get("CELLS_NATIVE_COUPLED_WITNESS")
    if not name:
        pytest.skip("Saved native development witness required")
    root = Path(name)
    p = check.u.read(root / "witness-protocol.json")
    path = root / "native" / case / "step-0/observed"
    row = check.u.read(path / "result.json")
    bare = check.u.read(path.parent / "bare/result.json")
    assert row["final"] == bare["final"] and row["fixture"] == bare["fixture"]
    assert check.u.sha(path / "trace.npz") == row["trace_sha256"]
    assert check.u.sha(path / "gates.npz") == row["gates_sha256"]
    assert check.u.sha(path / "preparation.json") == row["preparation_sha256"]
    with np.load(path / "trace.npz", allow_pickle=False) as f:
        trace = dict(f)
    with np.load(path / "gates.npz", allow_pickle=False) as f:
        gates = dict(f)
    c = check.bind(check.u.read(path / "preparation.json"), row, trace, p)
    return c, row, trace, gates, p


@pytest.mark.parametrize("case", ["single_na", "network_nakcl", "half_block"])
def test_saved_native_source_transport_and_complete_replay(case, tmp_path):
    c, row, trace, gates, p = witness(case)
    times, native, balances = check.native_values(c, row, trace, gates, p)
    predicted, lagged, device = check.adapter.replay(c, p, row["dt_s"], "cpu")
    errors = check.ref.physical.difference(c, predicted, native)
    native_delta = check.ref.physical.unpack(c, native)[0]
    expected_lag = np.concatenate((np.zeros_like(native_delta[:1]), native_delta[:-1]))
    np.testing.assert_allclose(
        lagged, expected_lag, rtol=0, atol=p["tolerances"]["replay_amount_fmol"]
    )
    check.u.write(tmp_path / "comparison.json", {"errors": errors, "balances": balances, **device})
    check.bounded(errors, p, "replay_")
    assert balances["gate_calls"] == len(c["species"]) * row["steps"]
    assert times[-1] == p["duration_s"]


@pytest.mark.parametrize(
    "corruption",
    [
        "call_count",
        "species_order",
        "step_index",
        "gate_input",
        "gate_output",
        "block",
        "voltage_input",
        "gate_continuity",
        "lag",
        "flux",
        "charge",
        "material",
        "labels",
    ],
)
def test_corrupt_evidence_rejected(corruption):
    c, row, trace, gates, p = witness("network_nakcl")
    if corruption == "call_count":
        gates["after"] = gates["after"][:-1]
    elif corruption == "species_order":
        gates["species"][1] = gates["species"][0]
    elif corruption == "step_index":
        gates["step"][-1] -= 1
    elif corruption == "gate_input":
        gates["before"][0, 0] += 0.01
    elif corruption == "gate_output":
        gates["after"][0, 0] += 0.01
    elif corruption == "block":
        gates["block"][0, 0] = 0.3
    elif corruption == "voltage_input":
        gates["voltage"][0, 0] += 0.001
    elif corruption == "gate_continuity":
        trace["transport_gjopen"][-1, 0] += 0.01
    elif corruption == "lag":
        trace["before_cc_at_mem"][-1] = trace["before_cc_cells"][-1][:, c["owners"]]
    elif corruption == "flux":
        trace["transport_fluxes_gj"][-1, c["indices"][0], c["faces"][0, 0]] *= -1
    elif corruption == "charge":
        trace["after_vm_ave"][-1, 0] += 0.001
    elif corruption == "material":
        trace["after_cc_cells"][-1, c["indices"][0], 0] += 0.001
    elif corruption == "labels":
        trace["native_labels_s"] = (np.arange(row["steps"]) + 1) * row["dt_s"]
    with pytest.raises((ValueError, AssertionError)):
        check.native_values(c, row, trace, gates, p)


def test_last_gate_cannot_stand_in_for_species_specific_transport():
    c, row, trace, gates, p = witness("half_block")
    collapsed = copy.deepcopy(gates)
    for k in ("before", "after"):
        x = collapsed[k].reshape(row["steps"], len(c["species"]), -1)
        x[:] = x[:, -1:]
    with pytest.raises((ValueError, AssertionError)):
        check.native_values(c, row, trace, collapsed, p)


def test_half_block_has_no_multicall_physical_time_limit():
    c, _, _, _, p = witness("half_block")
    with pytest.raises(ValueError, match="no such continuous limit"):
        check.ref.integrate(c, p, np.array([0, p["duration_s"]]), "DOP853", calls_per_step=3)


def test_registered_half_block_clocks_keep_exact_restart_boundary():
    from cells.core.runner import timeline
    from cells.core.specs import parse_spec

    c, _, _, _, _ = witness("half_block")
    p = check.u.read(HERE / "protocol.json")
    case = next(case for case in p["cases"] if case["id"] == "half_block")
    p |= {key: case[key] for key in ("duration_s", "observation_step_s", "restart_time_s")}
    assert [p["duration_s"] / dt for dt in p["native_steps_s"]] == [32, 64, 128]
    for dt in p["cells_steps_s"]:
        raw = check.definition(c, p, dt, "cpu")
        grid = timeline(parse_spec(raw))
        assert grid[-1] == p["duration_s"] and p["restart_time_s"] in grid


@pytest.mark.parametrize("case", ["single_na", "network_nakcl", "half_block"])
def test_prospective_native_step_ladder_against_independent_limit(case, tmp_path):
    c, _, _, _, _ = witness(case)
    p = check.u.read(HERE / "protocol.json")
    registered = next(r for r in p["cases"] if r["id"] == case)
    p |= {
        key: registered[key]
        for key in ("duration_s", "observation_step_s", "restart_time_s")
        if key in registered
    }
    reports = []
    for dt in p["native_steps_s"]:
        predicted, _, _ = check.adapter.replay(c, p, dt, "cpu")
        times = np.arange(len(predicted)) * dt
        delta, transfer, energy, _ = check.ref.physical.unpack(c, predicted)
        balances = check.base.ref.accounting(c, delta, transfer, energy)
        row = {"dt_s": dt, "balances": balances}
        if c["block"] == 1:
            expected, _ = check.ref.integrate(
                c, p, times, "DOP853", calls_per_step=len(c["species"])
            )
            row["errors"] = check.ref.native_difference(c, predicted, expected)
        reports.append(row)
    check.u.write(tmp_path / "prospective-ladder.json", {"case": case, "rows": reports})
    if c["block"] == 1:
        check.bounded(reports[-1]["errors"], p, "native_")
        for coarse, fine in zip(reports[:-1], reports[1:], strict=True):
            for field, floor in (("voltage_V", "V"), ("gate", "gate")):
                assert (
                    fine["errors"][field]
                    <= p["tolerances"]["native_refinement_ratio_max"] * coarse["errors"][field]
                    + p["tolerances"]["native_refinement_floor_" + floor]
                )
    check.base.check_accounting(reports[-1]["balances"], p["tolerances"], "native_energy_pJ")


def short_production(case, backend, tmp_path):
    c, _, _, _, _ = witness(case)
    p = check.u.read(HERE / "protocol.json")
    p.update(duration_s=0.002, observation_step_s=0.0005, restart_time_s=0.001)
    raw = check.definition(c, p, p["cells_steps_s"][0], backend)
    result = check.production.retained_run(raw, tmp_path / "production")
    actual = check.ref.physical.physical(result.observations)
    times = np.asarray(raw["experiment"]["observation_times"])
    errors = {}
    for method in ("DOP853", "Radau"):
        reference, _ = check.ref.integrate(c, p, times, method)
        errors[method] = check.ref.physical.difference(c, actual, reference)
        check.bounded(errors[method], p)
    checkpoint = check.production.replay(result, tmp_path / "production", p["restart_time_s"])
    check.u.write(tmp_path / "comparison.json", {"errors": errors, **checkpoint})


@pytest.mark.parametrize("case", ["single_na", "network_nakcl"])
def test_short_ordinary_cpu_trajectory_and_disk_restart(case, tmp_path):
    short_production(case, "cpu", tmp_path)


@pytest.mark.skipif(os.environ.get("CELLS_TEST_GPU") != "1", reason="Dedicated L4 check")
def test_gpu_native_replay_and_physical_trajectory(tmp_path):
    c, row, trace, gates, p = witness("network_nakcl")
    _, native, _ = check.native_values(c, row, trace, gates, p)
    cpu, _, _ = check.adapter.replay(c, p, row["dt_s"], "cpu")
    gpu, _, device = check.adapter.replay(c, p, row["dt_s"], "gpu")
    assert device["platform"] == "gpu" and device["dtype"] == "float64"
    check.bounded(check.ref.physical.difference(c, gpu, native), p, "replay_")
    np.testing.assert_allclose(cpu, gpu, rtol=0, atol=p["tolerances"]["cpu_gpu_atol"])
    check.u.write(
        tmp_path / "replay.json", {"cpu_gpu_error": float(np.max(np.abs(cpu - gpu))), **device}
    )
    short_production("network_nakcl", "gpu", tmp_path)


@pytest.mark.skipif(os.environ.get("CELLS_TEST_GPU") != "1", reason="Dedicated L4 check")
def test_gpu_complete_comparison_pipeline_uses_saved_native_pair(tmp_path):
    root = Path(os.environ["CELLS_NATIVE_COUPLED_WITNESS"])
    p = check.u.read(HERE / "protocol.json")
    witness_p = check.u.read(root / "witness-protocol.json")
    case = next(c for c in witness_p["cases"] if c["id"] == "half_block")
    p.update(
        duration_s=witness_p["duration_s"],
        observation_step_s=0.000625,
        restart_time_s=0.0015,
        native_steps_s=witness_p["native_steps_s"],
    )
    shutil.copytree(root / "native/half_block", tmp_path / "native/half_block")
    panel = check.u.read(root / "native/panel.json")
    records = [r for r in panel["rows"] if r["path"].startswith("half_block/")]
    rows = {r["path"]: check.load_row(tmp_path / "native", r, p) for r in records}
    result = check.check_case(tmp_path, p, case, rows)
    assert len(result["cells"]) == 4
    assert all(r["disk_restart_exact"] for r in result["cells"])
    assert result["native_vs_physical_model"]["gate"] > 0.05
