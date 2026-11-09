"""Synthetic checks of the route-agnostic Cells-vs-BETSE comparator (no BETSE, no Cells)."""

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from validation.betse import betse_reference_extract as ex
from validation.betse import cells_betse_compare as cmp

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "validation/betse/protocols/default_world_dense_example.json"
M, N, IONS, K, DT = 6, 2, 2, 5, 1e-4


def make_betse(directory, samples=4, aliased=False, venv_scale=1e-4, grid=None):
    """Tiny extraction: every observable changes in time, concentrations stay positive.

    ``grid`` (rows, cols) adds a row-major ECM grid (X, Y, xypts) with rows * cols sites.
    """
    directory.mkdir()
    sites = K if grid is None else grid[0] * grid[1]
    s = np.arange(1, samples + 1, dtype=float)[:, None]
    history = {
        "vm_time": (-0.02 + 1e-3 * s * np.linspace(0, 1, M), ("membranes",), "V"),
        "vm_ave_time": (-0.02 + 1e-3 * s * np.ones(N), ("cells",), "V"),
        "cc_time": (10 + s[:, :, None] * np.ones((IONS, N)), ("ions", "cells"), "mol/m^3"),
        "cc_env_time": (100 + s[:, :, None] * np.ones((IONS, sites)), ("ions", "env"), "mol/m^3"),
        "venv_time": (venv_scale * s * np.ones(sites), ("ECM grid points",), "V"),
    }
    geometry = {"mem_to_cells": (np.repeat([0, 1], 3), {"units": "index"})}
    if grid is not None:
        X, Y = np.meshgrid(np.arange(grid[1], dtype=float), np.arange(grid[0], dtype=float))
        geometry |= {
            "X": (X, {"units": "m"}),
            "Y": (Y, {"units": "m"}),
            "xypts": (np.column_stack([X.ravel(), Y.ravel()]), {"units": "m"}),
        }
    meta = {
        name: {"units": units, "axes": ["samples", *axes]}
        for name, (_, axes, units) in history.items()
    }
    if aliased:
        meta["vm_time"]["aliased_samples"] = True
    files = {"geometry.npz": ex.write_npz(directory / "geometry.npz", geometry)}
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


# ............................................................ protocol extensions


def with_protocol(case, edit, name="variant.json"):
    protocol = copy.deepcopy(case["protocol"])
    edit(protocol)
    path = case["tmp"] / name
    path.write_text(json.dumps(protocol))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return {**case, "protocol": protocol, "protocol_path": path, "sha": sha}


def grid_case(case, grid=(4, 5)):
    make_betse(case["tmp"] / "grid", grid=grid)
    manifest = json.loads((case["tmp"] / "grid/manifest.json").read_text())
    geometry = manifest["files"]["geometry.npz"]["sha256"]
    return {**case, "betse_dir": case["tmp"] / "grid", "betse": manifest, "geometry": geometry}


def bump(case, phase, observable, index, delta=None, factor=None):
    old = float(cmp._npz(case["betse_dir"] / f"{phase}_history.npz")[observable][tuple(index)])
    new = old * factor if factor is not None else old + delta
    return {"phase": phase, "observable": observable, "index": index, "new_value": new}


def test_grid_boundary_ring_follows_the_case_grid():
    X, Y = np.meshgrid(np.arange(25.0), np.arange(24.0))  # 24 rows x 25 columns
    geometry = {"X": X, "Y": Y, "xypts": np.column_stack([X.ravel(), Y.ravel()])}
    ring, grid = cmp.grid_boundary_ring(geometry)
    assert grid == (24, 25) and ring.size == 94
    assert set(ring) == {k for k in range(600) if k // 25 in (0, 23) or k % 25 in (0, 24)}
    with pytest.raises(cmp.Refusal):  # points not in row-major X/Y order
        cmp.grid_boundary_ring({**geometry, "xypts": geometry["xypts"][::-1]})


def test_excluded_ring_errors_are_reported_but_not_judged(case):
    case = grid_case(case)  # 4 x 5 grid, ring of 14 sites

    def exclude(protocol):
        for name in ("cc_env_time", "venv_time"):
            protocol["observables"][name]["exclude"] = cmp.RING

    ring = with_protocol(case, exclude)
    corner = bump(case, "sim", "cc_env_time", [2, 1, 0], factor=1 + 1e-3)  # site 0: a corner
    result = layout(ring, "ring", perturbation=corner)
    obs = result["phases"]["sim"]["observables"]["cc_env_time"]
    assert result["verdict"] == "pass" and obs["history"]["max_rel"]["value"] == 0
    assert obs["excluded"]["sites"] == 14 and obs["excluded"]["elements"] == IONS * 14
    worst = obs["excluded"]["history"]["max_rel"]
    assert worst["element"] == [1, 0] and worst["value"] == pytest.approx(1e-3)
    assert worst["elapsed_s"] == pytest.approx(3 * DT)
    assert (
        "excluded 14 ring sites"
        in cmp.summarize(result)["phases"]["sim"]["observables"]["cc_env_time"]
    )
    assert layout(case, "plain", perturbation=corner)["verdict"] == "fail"
    inner = bump(case, "sim", "cc_env_time", [2, 1, 6], factor=1 + 1e-3)  # grid (1, 1)
    failed = layout(ring, "inner", perturbation=inner)
    assert failed["verdict"] == "fail"
    assert failed["phases"]["sim"]["observables"]["cc_env_time"]["history"]["max_rel"][
        "element"
    ] == [1, 6]


def test_ring_exclusion_needs_an_ecm_grid_axis(case):
    ring = with_protocol(case, lambda p: p["observables"]["cc_env_time"].update(exclude=cmp.RING))
    result = layout(ring, "no-grid")  # synthetic case without X/Y
    assert result["verdict"] == "refused" and cmp.RING in result["refusals"][0]


def test_reported_only_observables_stay_out_of_the_verdict(case):
    only = with_protocol(case, lambda p: p["observables"]["venv_time"].update(judged=False))
    wrong = {"phase": "sim", "observable": "venv_time", "index": [1, 0], "new_value": 1.0}
    result = layout(only, "venv-wrong", perturbation=wrong)
    venv = result["phases"]["sim"]["observables"]["venv_time"]
    assert result["verdict"] == "pass" and venv["judged"] is False
    assert not venv["classes"]["codata_constants"]["pass"] and venv["dynamic_range"]
    assert "flat" in venv["classes"]["codata_constants"]
    phases = cmp.layout_from_betse(only["betse_dir"], only["betse"], only["protocol"])
    for row in phases.values():
        row["history"].pop("venv_time")
        row["final"].pop("v_env")
    absent = layout(only, "no-venv", phases=phases)
    assert absent["verdict"] == "pass"
    assert absent["phases"]["init"]["observables"]["venv_time"]["absent_in_cells"]
    assert layout(case, "no-venv-judged", phases=phases)["verdict"] == "refused"
    nothing = with_protocol(
        case, lambda p: [row.update(judged=False) for row in p["observables"].values()]
    )
    with pytest.raises(cmp.Refusal):
        cmp.load_protocol(nothing["protocol_path"])


def test_cells_only_diagnostics_are_reported_and_never_judged(case):
    diag = with_protocol(case, lambda p: p["observables"].update({"diag_*": {"judged": False}}))
    phases = cmp.layout_from_betse(diag["betse_dir"], diag["betse"], diag["protocol"])
    for row in phases.values():
        row["history"]["diag_pump_time"] = np.linspace(0.0, 1.0, 12).reshape(4, 3)
        row["final"]["diag_pump"] = np.full(3, 2.0)
    result = layout(diag, "diag", phases=phases)
    report = result["phases"]["sim"]["cells_only"]["diag_pump_time"]
    assert result["verdict"] == "pass" and report["cells_only"] and not report["judged"]
    assert report["shape"] == [4, 3] and report["final_array"] == "diag_pump"
    assert report["dynamic_range"]["value_max"] == 2.0 and report["samples_match_elapsed"]
    lines = cmp.summarize(result)["phases"]["sim"]["observables"]
    assert lines["diag_pump_time"].startswith("cells-only")
    for bad in ({"judged": True}, {"judged": False, "final": "diag_pump"}):
        broken = with_protocol(case, lambda p, b=bad: p["observables"].update(diag_x_time=b))
        with pytest.raises(cmp.Refusal):
            cmp.load_protocol(broken["protocol_path"])


def test_tolerances_may_differ_per_phase(case):
    def split(protocol):
        for values in protocol["tolerance_classes"].values():
            values["voltage"] = {"init": 1e-3, "sim": 1e-6}

    phased = with_protocol(case, split)
    for phase, verdict in (("init", "pass"), ("sim", "fail")):
        result = layout(
            phased, f"tol-{phase}", perturbation=bump(case, phase, "vm_time", [1, 2], 1e-4)
        )
        vm = result["phases"][phase]["observables"]["vm_time"]["classes"]["codata_constants"]
        assert result["verdict"] == verdict
        assert vm["tolerance"] == {"init": 1e-3, "sim": 1e-6}[phase]
    for value in ({"init": 1e-3}, {"init": 0.0, "sim": 1e-6}, {"init": 1, "sim": 1, "x": 1}):
        broken = with_protocol(
            case, lambda p, v=value: p["tolerance_classes"]["codata_constants"].update(voltage=v)
        )
        with pytest.raises(cmp.Refusal):
            cmp.load_protocol(broken["protocol_path"])


def test_tolerances_may_differ_per_ion(case):
    """Each ion meets its own tolerance; the worst error of each ion is reported."""

    def per_ion(protocol):
        for values in protocol["tolerance_classes"].values():
            values["cell_concentration"] = {
                "init": {"by_ion": {"Na": 1e-3, "K": 1e-9}},
                "sim": 1e-9,
            }

    ionic = with_protocol(case, per_ion)
    na = bump(case, "init", "cc_time", [1, 0, 1], factor=1 + 1e-4)
    result = layout(ionic, "ion-na", perturbation=na)
    cls = result["phases"]["init"]["observables"]["cc_time"]["classes"]["codata_constants"]
    assert result["verdict"] == "pass" and cls["pass"]
    assert cls["by_ion"]["Na"]["worst"] == pytest.approx(1e-4) and cls["by_ion"]["K"]["worst"] == 0
    assert cls["by_ion"]["Na"]["tolerance"] == 1e-3 and not cls["by_ion"]["Na"]["flat"]
    line = cmp.summarize(result)["phases"]["init"]["observables"]["cc_time"]
    assert "Na 0.0001 of 0.001" in line
    k = bump(case, "init", "cc_time", [1, 1, 0], factor=1 + 1e-8)
    failed = layout(ionic, "ion-k", perturbation=k)
    cls = failed["phases"]["init"]["observables"]["cc_time"]["classes"]["codata_constants"]
    assert (
        failed["verdict"] == "fail"
        and not cls["by_ion"]["K"]["pass"]
        and cls["by_ion"]["Na"]["pass"]
    )
    for i, broken in enumerate(
        (
            {"init": {"by_ion": {"Na": 1e-3}}, "sim": 1e-9},  # an ion missing
            {"init": {"by_ion": {"Na": 1e-3, "K": 1e-9, "Ca": 1.0}}, "sim": 1e-9},
        )
    ):
        bad = with_protocol(
            case,
            lambda p, v=broken: p["tolerance_classes"]["codata_constants"].update(
                cell_concentration=v
            ),
            name=f"bad-{i}.json",
        )
        refused = layout(bad, f"ion-bad-{i}")
        assert refused["verdict"] == "refused" and "per-ion" in refused["refusals"][0]
    for value in ({"init": {"by_ion": {}}, "sim": 1e-9}, {"init": {"ions": {"Na": 1}}, "sim": 1}):
        invalid = with_protocol(
            case,
            lambda p, v=value: p["tolerance_classes"]["codata_constants"].update(
                cell_concentration=v
            ),
            name="invalid.json",
        )
        with pytest.raises(cmp.Refusal):
            cmp.load_protocol(invalid["protocol_path"])
    voltage = with_protocol(
        case,
        lambda p: p["tolerance_classes"]["codata_constants"].update(
            voltage={"init": {"by_ion": {"Na": 1.0, "K": 1.0}}, "sim": 1.0}
        ),
        name="voltage.json",
    )
    assert layout(voltage, "ion-voltage")["verdict"] == "refused"  # no ions axis


# ............................................................ regression

BASELINE = "432e62b"  # comparator before exclusions, reported-only and per-phase tolerances


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    shown = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{BASELINE}:validation/betse/cells_betse_compare.py"],
        capture_output=True,
        text=True,
    )
    if shown.returncode:
        pytest.skip("baseline comparator is not in this checkout's history")
    directory = tmp_path_factory.mktemp("baseline")
    (directory / "cells_betse_compare.py").write_text(shown.stdout)
    for sibling in ("betse_reference_extract.py", "betse_reference_run.py"):
        shutil.copy(ROOT / "validation/betse" / sibling, directory / sibling)
    spec = importlib.util.spec_from_file_location(
        "_baseline_compare", directory / "cells_betse_compare.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalized(record):
    record = json.loads(json.dumps(cmp.json_safe(record)))
    record.pop("created_utc")
    record.pop("comparator")
    return record


@pytest.mark.parametrize(
    "name",
    [
        "default_world_dense_example.json",
        "emulator_default_world.json",
        "emulator_default_world_dense.json",
    ],
)
def test_existing_protocols_give_unchanged_results(case, baseline, name):
    path = ROOT / "validation/betse/protocols" / name
    fixed = {
        **case,
        "protocol": json.loads(path.read_text()),
        "protocol_path": path,
        "sha": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    changes = {
        "identity": None,
        "vm": bump(case, "sim", "vm_time", [1, 2], 3e-6),
        "env": bump(case, "init", "cc_env_time", [2, 1, 4], factor=1 + 5e-8),
        "nan": {"phase": "sim", "observable": "venv_time", "index": [3, 1], "new_value": np.nan},
    }
    for label, change in changes.items():
        new = layout(fixed, f"{name}-{label}", perturbation=change)
        old = baseline.run_comparison(fixed["betse_dir"], fixed["tmp"] / f"{name}-{label}", path)
        assert normalized(new) == normalized(old), label
        assert cmp.json_safe(cmp.summarize(new)) == baseline.json_safe(baseline.summarize(old))
