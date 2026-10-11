"""Small saved-packet/corruption checks; no numerical trajectory generation."""

import copy
import importlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
a = importlib.import_module("coupled_audit")


def synthetic():
    plan = a.read(a.CAPTURE / "registration.json")["protocol"]
    refs, candidates, groups, refinement = {}, {}, [], []
    for case in plan["cases"]:
        width, name = 8 * len(case["volume_pL"]) + 3, case["id"]
        sample = {
            "times_s": [k * 0.001 for k in range(11)],
            "state": [[0.0] * width for _ in range(11)],
        }
        segments = []
        for i, control in enumerate(case["controls"]):
            end = case["controls"][i + 1]["time_s"] if i + 1 < len(case["controls"]) else 0.01
            segments.append(
                {
                    "start_s": control["time_s"],
                    "end_s": end,
                    "last_solver_time_s": end,
                    "nfev": 1,
                    "end_state": [0.0] * width,
                }
            )
        refs[name] = {
            method: {**copy.deepcopy(sample), "segments": copy.deepcopy(segments)}
            for method in ("DOP853", "Radau")
        }
        paths, checkpoints = {}, {}
        for engine in ("numpy", "jax_jit"):
            for dt in plan["rk4_steps_s"]:
                full = [[0.0] * width for _ in range(round(0.01 / dt) + 1)]
                paths[f"{engine}/{dt}"] = {
                    **copy.deepcopy(sample),
                    "step_s": dt,
                    "full_state": full,
                }
                if dt == 0.00005:
                    checkpoints[engine] = {
                        "time_s": 0.006,
                        "exact": True,
                        "complete_state": full[120],
                        "suffix_state": full[120:],
                    }
            refinement.append(
                {
                    "case": name,
                    "engine": engine,
                    "coarse": 0.0,
                    "fine": 0.0,
                    "bound": 0.001,
                    "pass": True,
                    "roundoff_limited": True,
                }
            )
        candidates[name] = {
            "trajectories": paths,
            "restart_exact": True,
            "checkpoints": checkpoints,
        }
        for method in ("DOP853", *paths):
            groups.append(
                {
                    "case": name,
                    "method": method,
                    "max_scaled_state_error": 0.0,
                    "max_voltage_error_V": 0.0,
                    "material_residual_fmol": 0.0,
                    "charge_residual_C": 0.0,
                    "energy_residual_pJ": 0.0,
                    "pass": True,
                }
            )
    return (
        plan,
        refs,
        candidates,
        {"status": "pass", "state_comparisons": 4070, "groups": groups, "refinement": refinement},
    )


def test_complete_synthetic_packet():
    result = a.audit(*synthetic())
    assert result["state_comparisons"] == 4070
    assert result["physical_records"] == 3756
    assert result["restarts"] == 12
    assert result["all_refinement_roundoff_limited"]
    assert not result["production_model_accepted"]


@pytest.mark.parametrize(
    "change",
    [
        "case",
        "method",
        "step",
        "sample",
        "endpoint",
        "energy",
        "negative",
        "nonfinite",
        "restart",
        "segment",
        "summary",
        "refinement",
        "time",
    ],
)
def test_saved_corruption_fails(change):
    plan, refs, candidates, summary = synthetic()
    trial = candidates["pump_leak"]["trajectories"]["numpy/0.0001"]
    if change == "case":
        candidates.pop("leak_only")
    elif change == "method":
        refs["pump_leak"].pop("DOP853")
    elif change == "step":
        trial["step_s"] = 0.00005
    elif change == "sample":
        trial["state"][1][0] = 1e-4
    elif change == "endpoint":
        trial["full_state"].pop()
    elif change == "energy":
        trial["full_state"][1][-1] = 1e-5
    elif change == "negative":
        trial["full_state"][1][0] = -13
    elif change == "nonfinite":
        trial["full_state"][1][-1] = math.nan
    elif change == "restart":
        candidates["pump_leak"]["checkpoints"]["numpy"]["suffix_state"] = []
    elif change == "segment":
        refs["pump_leak"]["Radau"]["segments"][0]["last_solver_time_s"] = 0.009
    elif change == "summary":
        summary["groups"][0]["max_scaled_state_error"] = 0.001
    elif change == "refinement":
        summary["refinement"][0]["bound"] = 1.0
    elif change == "time":
        trial["times_s"][2] = 0.0019
    with pytest.raises(ValueError):
        a.audit(plan, refs, candidates, summary)


def test_decimal_accounting_retains_small_transfers():
    plan, *_ = synthetic()
    case = plan["cases"][0]
    state = [0.0] * 11
    state[0], state[3], state[6] = 1e-18, -1e-18, 1e-18
    result = a.physical(case, state, plan["constants"])
    # Decimal lifts the complete binary value; 60-digit arithmetic still rounds
    # this unusually tiny input's much longer exact decimal expansion.
    assert result["material_residual_fmol"] < 1e-70
    assert result["charge_residual_C"] < 1e-80
    assert 0 < result["energy_residual_pJ"] < 1e-14


def test_original_source_capture_authenticates():
    registered, preserved = a.authenticate()
    assert len(registered["sources_sha256"]) == 14
    assert len(preserved["implementation_files_sha256"]) == 352


def test_model_import_fence_in_fresh_interpreter():
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import coupled_audit as a\n"
            "with a.model_fence():\n"
            " for name in a.FORBIDDEN:\n"
            "  try: __import__(name)\n"
            "  except ImportError: pass\n"
            "  else: raise AssertionError(name)\n",
        ],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_strict_json(tmp_path):
    for data in ('{"x":1,"x":2}', '{"x":NaN}'):
        target = tmp_path / str(len(data))
        target.write_text(data)
        with pytest.raises(ValueError):
            a.read(target)


def test_existing_audit_directory_is_never_changed(tmp_path):
    with pytest.raises(ValueError, match="fresh"):
        a.run(tmp_path, a.ROOT / "reports/num-011-kinetic-pump-checks-03.xml")
    assert not list(tmp_path.iterdir())


def test_worker_json_is_independent_of_model_imports():
    # Inspect just one saved state, never reintegrate a reference or candidate.
    registration = a.read(a.CAPTURE / "registration.json")
    case = registration["protocol"]["cases"][-1]
    worker = a.read(a.CAPTURE / "candidate.json")
    state = worker["results"][case["id"]]["trajectories"]["numpy/5e-05"]["full_state"][-1]
    result = a.physical(case, state, registration["protocol"]["constants"])
    assert result["energy_residual_pJ"] < 2e-8
    assert result["min_concentration_mM"] > 0
    assert json.loads(json.dumps(state)) == state
