"""Synthetic checks of the route-agnostic Cells-vs-BETSE comparator (no BETSE, no Cells)."""

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from validation.betse import betse_reference_extract as ex
from validation.betse import cells_betse_compare as cmp

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "validation/betse/protocols/default_world_dense_example.json"
M, N, IONS, K, DT = 6, 2, 2, 5, 1e-4


def make_betse(directory, samples=4, aliased=False, venv_scale=1e-4):
    """Tiny extraction: every observable changes in time, concentrations stay positive."""
    directory.mkdir()
    s = np.arange(1, samples + 1, dtype=float)[:, None]
    history = {
        "vm_time": (-0.02 + 1e-3 * s * np.linspace(0, 1, M), ("membranes",), "V"),
        "vm_ave_time": (-0.02 + 1e-3 * s * np.ones(N), ("cells",), "V"),
        "cc_time": (10 + s[:, :, None] * np.ones((IONS, N)), ("ions", "cells"), "mol/m^3"),
        "cc_env_time": (100 + s[:, :, None] * np.ones((IONS, K)), ("ions", "env"), "mol/m^3"),
        "venv_time": (venv_scale * s * np.ones(K), ("ECM grid points",), "V"),
    }
    meta = {
        name: {"units": units, "axes": ["samples", *axes]}
        for name, (_, axes, units) in history.items()
    }
    if aliased:
        meta["vm_time"]["aliased_samples"] = True
    files = {
        "geometry.npz": ex.write_npz(
            directory / "geometry.npz", {"mem_to_cells": (np.repeat([0, 1], 3), {"units": "index"})}
        )
    }
    time = {}
    for phase in cmp.PHASES:
        files[f"{phase}_history.npz"] = ex.write_npz(
            directory / f"{phase}_history.npz",
            {name: (array, meta[name]) for name, (array, _, _) in history.items()},
        )
        finals = {
            cmp.SUPPORTED[name]: (array[-1], {"units": "x"})
            for name, (array, _, _) in history.items()
        }
        files[f"{phase}_final.npz"] = ex.write_npz(directory / f"{phase}_final.npz", finals)
        time[phase] = {
            "elapsed_after_update_s": [(k + 1) * DT for k in range(samples)],
            "final_state_elapsed_s": samples * DT,
        }
    manifest = {
        "kind": ex.KIND,
        "status": "complete",
        "files": files,
        "time": time,
        "ions": {"order": ["Na", "K"]},
        "source_run": {"case": "synthetic"},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return manifest


@pytest.fixture
def case(tmp_path):
    protocol = json.loads(EXAMPLE.read_text())
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol))
    betse = make_betse(tmp_path / "betse")
    return {
        "tmp": tmp_path,
        "betse_dir": tmp_path / "betse",
        "betse": betse,
        "protocol": protocol,
        "protocol_path": protocol_path,
        "sha": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "geometry": betse["files"]["geometry.npz"]["sha256"],
    }


def layout(case, name="cells", phases=None, perturbation=None, **overrides):
    if phases is None:
        phases = cmp.layout_from_betse(
            case["betse_dir"], case["betse"], case["protocol"], perturbation
        )
    keywords = {
        "protocol_sha256": case["sha"],
        "betse_geometry_sha256": case["geometry"],
        "provenance": {"producer": "test"},
        **overrides,
    }
    cmp.write_layout(case["tmp"] / name, phases, **keywords)
    return cmp.run_comparison(case["betse_dir"], case["tmp"] / name, case["protocol_path"])


def test_example_protocol_declares_the_two_tolerance_classes():
    protocol, _ = cmp.load_protocol(EXAMPLE)
    assert protocol["tolerance_classes"] == {
        "codata_constants": {
            "voltage": 1e-5,
            "cell_concentration": 1e-6,
            "ecm_concentration": 1e-7,
        },
        "matched_constants_or_cpu_gpu": {
            "voltage": 1e-9,
            "cell_concentration": 1e-11,
            "ecm_concentration": 1e-11,
        },
    }
    assert set(protocol["observables"]) == set(cmp.SUPPORTED)


def test_identity_passes_with_zero_error_and_records_protocol(case):
    result = layout(case)
    assert (
        result["verdict"] == "pass" and result["classes"]["matched_constants_or_cpu_gpu"] == "pass"
    )
    assert result["protocol"]["sha256"] == case["sha"]
    for phase in result["phases"].values():
        assert phase["common_samples"] == 4
        for obs in phase["observables"].values():
            assert obs["history"]["max_abs"]["value"] == 0 and obs["final"]["max_rel"]["value"] == 0
            assert obs["dynamic_range"]["max_temporal_change"] > 0


def test_perturbation_fails_at_its_element_and_time(case):
    old = 100 + 3.0  # cc_env_time sample 2 (elapsed 3 dt), ion 1, point 4
    change = {"phase": "sim", "observable": "cc_env_time", "index": [2, 1, 4]}
    result = layout(case, perturbation={**change, "new_value": old * (1 + 1e-6)})
    assert result["verdict"] == "fail"
    obs = result["phases"]["sim"]["observables"]["cc_env_time"]
    worst = obs["history"]["max_rel"]
    assert worst["element"] == [1, 4] and worst["labels"]["ion"] == "K"
    assert worst["elapsed_s"] == pytest.approx(3 * DT) and worst["value"] == pytest.approx(1e-6)
    assert not obs["classes"]["codata_constants"]["pass"]
    assert result["phases"]["init"]["observables"]["cc_env_time"]["classes"]["codata_constants"][
        "pass"
    ]
    within = layout(case, "within", perturbation={**change, "new_value": old * (1 + 1e-8)})
    assert (
        within["verdict"] == "pass" and within["classes"]["matched_constants_or_cpu_gpu"] == "fail"
    )


def test_alignment_uses_common_elapsed_times_only(case):
    phases = cmp.layout_from_betse(case["betse_dir"], case["betse"], case["protocol"])
    sparse = copy.deepcopy(phases)
    for row in sparse.values():  # Cells sampled every other step, plus one extra time
        row["elapsed_after_update_s"] = [2 * DT, 4 * DT, 9 * DT]
        row["history"] = {k: np.concatenate([v[[1, 3]], v[[3]]]) for k, v in row["history"].items()}
    result = layout(case, "sparse", phases=sparse)
    assert result["verdict"] == "pass" and result["phases"]["sim"]["common_samples"] == 2

    for row in sparse.values():
        row["elapsed_after_update_s"] = [11 * DT, 12 * DT, 13 * DT]
    refused = layout(case, "disjoint", phases=sparse)
    assert refused["verdict"] == "refused" and "common elapsed" in refused["refusals"][0]


@pytest.mark.parametrize(
    "mutate, overrides, message",
    [
        (
            lambda p: p["sim"]["history"].update(vm_time=p["sim"]["history"]["vm_time"][:, 1:]),
            {},
            "shape",
        ),
        (lambda p: p["init"]["final"].pop("v_env"), {}, "missing"),
        (lambda p: p["sim"].update(final_elapsed_s=1.0), {}, "final elapsed"),
        (lambda p: None, {"protocol_sha256": "0" * 64}, "protocol"),
        (lambda p: None, {"betse_geometry_sha256": "0" * 64}, "geometry"),
    ],
)
def test_refusals(case, mutate, overrides, message):
    phases = cmp.layout_from_betse(case["betse_dir"], case["betse"], case["protocol"])
    mutate(phases)
    result = layout(case, phases=phases, **overrides)
    assert result["verdict"] == "refused" and message in result["refusals"][0], result["refusals"]


def test_aliased_reference_series_is_refused(case):
    make_betse(case["tmp"] / "aliased", aliased=True)
    case = {**case, "betse_dir": case["tmp"] / "aliased"}
    result = layout(case, "aliased-cells")
    assert result["verdict"] == "refused" and "aliased" in result["refusals"][0]


def test_flat_reference_is_flagged_per_class(case):
    make_betse(case["tmp"] / "flat", venv_scale=1e-7)  # venv changes by 3e-7 V in total
    case = {**case, "betse_dir": case["tmp"] / "flat"}
    venv = layout(case, "flat-cells")["phases"]["sim"]["observables"]["venv_time"]
    assert venv["dynamic_range"]["max_temporal_change"] == pytest.approx(3e-7)
    assert venv["classes"]["codata_constants"]["flat"]  # tolerance 1e-5 V
    assert not venv["classes"]["matched_constants_or_cpu_gpu"]["flat"]  # tolerance 1e-9 V


def test_non_finite_cells_value_fails_and_outputs_stay_strict_json(case):
    phases = cmp.layout_from_betse(case["betse_dir"], case["betse"], case["protocol"])
    phases["sim"]["history"]["venv_time"][1, 0] = np.nan
    result = layout(case, phases=phases)
    venv = result["phases"]["sim"]["observables"]["venv_time"]
    assert result["verdict"] == "fail" and venv["history"]["max_abs"]["value"] == np.inf
    assert (
        venv["history"]["max_abs"]["element"] == [0]
        and venv["history"]["max_abs"]["cells_sample"] == 1
    )
    assert cmp.write_outputs(result, case["tmp"] / "out") == 1
    assert json.loads((case["tmp"] / "out/summary.json").read_text())["verdict"] == "fail"
    assert json.loads((case["tmp"] / "out/result.json").read_text())["verdict"] == "fail"


def test_invalid_protocol_is_refused(case):
    broken = copy.deepcopy(case["protocol"])
    broken["verdict_class"] = "unknown"
    case["protocol_path"].write_text(json.dumps(broken))
    with pytest.raises(cmp.Refusal):
        cmp.load_protocol(case["protocol_path"])
