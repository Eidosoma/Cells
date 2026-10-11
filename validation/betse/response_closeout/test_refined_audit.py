"""D086 short saved-data and synthetic corruption tests; no simulation or full actual audit."""

import copy
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest
import refined_audit as audit
import refined_audit_context as ctx
import refined_audit_job as job
import refined_audit_surfaces as surfaces

c = ctx.c


@pytest.fixture(scope="module")
def registered():
    return c.read(ctx.SESSION / "registration.json")


@pytest.fixture(scope="module")
def comparison():
    return c.read(ctx.SESSION / "comparison.json")


def test_sources_production_and_both_capture_roots_preserved():
    result = ctx.preservation_check()
    assert result["baseline_files"] == 1027
    assert result["capture_files_unchanged"] == 56
    assert result["resource_failure_files_unchanged"] == 241
    assert result["accepted_implementation_files_unchanged"] == 352
    assert result["production_modules_unchanged"] == 51
    assert len(ctx.sources()) == 118 and len(ctx.prior.sources()) == 112
    assert len(ctx.prior.prior.legacy.old.sources()) == 88
    assert set(ctx.OLD_TESTS) <= set(c.read(ctx.PRESERVATION)["baseline_sha256"])


@pytest.mark.parametrize(
    "key,value",
    [
        ("cpu_affinity", "0-31"),
        ("total_timeout_seconds", 9000),
        ("max_artifact_bytes", 1),
        ("max_worker_file_bytes", True),
        ("required_comparisons", 2298935),
        ("diagnostic_failed_comparisons", 0),
        ("independent_surface_comparisons", 147312),
        ("surface_scopes", 131),
        ("previous_regression_tests", 230),
        ("test_modules", []),
        ("capture_rerun", True),
        ("automatic_retry", True),
        ("automatic_polling", True),
        ("native_convergence_qualified", True),
        ("forcing_convergence_qualified", True),
        ("biology_validated", True),
        ("gpu_tested", True),
    ],
)
def test_unregistered_scope_resource_or_claim_rejected(key, value):
    with pytest.raises(ValueError):
        ctx.validate_plan(c.read(ctx.PLAN) | {key: value})


def test_completed_capture_metadata_and_resource_accounting(registered):
    result = audit.inspect_metadata(registered, ctx.SESSION)
    assert result["capture_seconds"] == pytest.approx(2239.32150707196)
    assert result["combined_capture_bytes_before_receipt"] == 325843874
    assert result["new_cells_runs"] == 22 and result["reused_cells_runs"] == 26
    assert result["reused_native_runs"] == 16 and result["new_native_runs"] == 0
    assert result["original_cells_worker_receipt_invented"] is False
    assert result["retained_native_installed_python_files"] == 332


@pytest.mark.parametrize(
    "name,key,value",
    [
        ("capture.json", "trajectory_qualified", True),
        ("capture.json", "required_failed_comparisons", 1),
        ("capture.json", "failed_comparisons", 0),
        ("capture.json", "reused_cells_runs", 48),
        ("capture.json", "elapsed_seconds", 9000),
        ("capture.json", "combined_artifact_bytes_before_receipt", 1),
        ("launch.json", "pid", 0),
        ("launch.json", "automatic_retry", True),
        ("launch.json", "launched_utc", "2099-01-01T00:00:00+00:00"),
        ("cells.json", "device", "gpu"),
        ("cells.json", "warnings", ["warning"]),
        ("cells.json", "results", {}),
        ("cells.json", "source_sha256", "0" * 64),
        ("cells.json", "runtime_resource_probe_sha256", "0" * 64),
        ("cells-started/21.json", "started_utc", "2099-01-01T00:00:00+00:00"),
        ("comparison.json", "independent_audit_run", True),
        ("comparison.json", "criteria_unchanged", False),
        ("comparison.json", "coarse_rejection_replayed_exactly", False),
        ("comparison.json", "terminal_native_rate_invented", True),
        ("comparison.json", "required_gates", {"comparisons": 2298936, "failed_comparisons": 1}),
    ],
)
def test_decoded_metadata_corruption_rejected(registered, monkeypatch, name, key, value):
    # The actual manifest is tested separately; replace only decoded test input.
    read, target = c.read, ctx.SESSION / name
    modified = read(target) | {key: value}
    monkeypatch.setattr(
        c, "read", lambda path: copy.deepcopy(modified) if Path(path) == target else read(path)
    )
    monkeypatch.setattr(ctx, "verify_manifest", lambda output, r: c.read(output / "capture.json"))
    with pytest.raises(ValueError):
        audit.inspect_metadata(registered, ctx.SESSION)


@pytest.fixture
def manifest_fixture(tmp_path, registered):
    for name in ctx.expected_paths(registered) | ctx.prior.audit.OPERATIONAL:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"{}")
    c.write(
        tmp_path / "capture.json",
        {"files_sha256": {n: c.sha(tmp_path / n) for n in ctx.expected_paths(registered)}},
    )
    return tmp_path


@pytest.mark.parametrize(
    "mutation",
    ["missing", "extra", "digest", "omit_hash", "extra_hash", "link", "empty", "failure"],
)
def test_completed_manifest_rejects_rehashed_corruption(manifest_fixture, registered, mutation):
    output, target = manifest_fixture, manifest_fixture / "cells.json"
    saved = c.read(output / "capture.json")
    if mutation == "missing":
        target.unlink()
        saved["files_sha256"].pop("cells.json")
    elif mutation == "extra":
        (output / "extra.json").write_bytes(b"{}")
        saved["files_sha256"]["extra.json"] = c.sha(output / "extra.json")
    elif mutation == "digest":
        target.write_bytes(b"changed")
    elif mutation == "omit_hash":
        saved["files_sha256"].pop("cells.json")
    elif mutation == "extra_hash":
        saved["files_sha256"]["missing.json"] = "0" * 64
    elif mutation == "link":
        target.unlink()
        target.symlink_to(output / "comparison.json")
    elif mutation == "empty":
        target.write_bytes(b"")
        saved["files_sha256"]["cells.json"] = c.sha(target)
    else:
        (output / "failure.json").write_bytes(b"{}")
    (output / "capture.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError):
        ctx.verify_manifest(output, registered)


def test_all_48_cell_paths_use_exact_original_or_continuation_source(registered):
    counts = {ctx.prior.FAILED: 0, ctx.SESSION: 0}
    for row in registered["cells_rows"]:
        path = surfaces.cells_path(registered, row)
        owner = ctx.prior.FAILED if row["id"] in registered["reused_cells"] else ctx.SESSION
        assert path == owner / "cells" / row["id"] / "result.json"
        assert path.is_file()
        counts[owner] += 1
    assert counts == {ctx.prior.FAILED: 26, ctx.SESSION: 22}


@pytest.fixture(scope="module")
def real_surfaces(registered):
    result = {}
    for h in surfaces.HOLDS:
        coarse = h == surfaces.HOLDS[0]
        view = (
            c.read(ctx.prior.prior.COARSE / "registration.json")
            if coarse
            else registered | {"common_times_s": registered["common_times_s"][f"{h:.8f}"]}
        )
        for condition in ("baseline", "suppression_recovery"):
            prefix = (
                ctx.prior.prior.COARSE / "native" / condition
                if coarse
                else ctx.prior.FAILED / "native" / f"{h:.8f}" / condition
            )
            row = next(
                row
                for row in view["cells_rows"]
                if row["condition"] == condition
                and row["backend"] == "jax_jit"
                and row["subdivision"] == 4
                and (coarse or row["hold_step_s"] == h)
            )
            result[h, condition] = (
                surfaces.base.native_surface(
                    view, c.read(prefix / "observed/result.json")["numerical"]
                ),
                surfaces.base.cells_surface(
                    view, c.read(surfaces.cells_path(registered, row, coarse))
                ),
            )
    return result


@pytest.mark.parametrize("h", surfaces.HOLDS)
@pytest.mark.parametrize("condition", ["baseline", "suppression_recovery"])
def test_selected_actual_full_grid_cross_engine_surfaces_match(
    registered, comparison, real_surfaces, h, condition
):
    label = f"{h:.8f}/cross_engine/{condition}/jax_jit"
    native, cells = real_surfaces[h, condition]
    result, failures = surfaces.compare(
        label,
        native,
        cells,
        registered["criteria"]["trajectory_tolerances"],
        h == surfaces.HOLDS[-1],
    )
    result["hold_step_s"] = h
    surfaces.compare_one(label, result, comparison["comparisons_by_scope"][label])
    assert len(native) == len(cells) == round(0.001 / h) + 1
    assert native[-1]["flux_fmol_per_s"] == cells[-1]["current_A"] == []
    assert len(failures) == result["failed_comparisons"]


@pytest.mark.parametrize("a,b", [(0.000025, 0.0000125), (0.0000125, 0.00000625)])
@pytest.mark.parametrize("engine,index", [("native", 0), ("jax_jit", 1)])
def test_selected_actual_input_sensitivity_failures_remain(
    registered, comparison, real_surfaces, a, b, engine, index
):
    label = f"across_hold/{a:.8f}-{b:.8f}/suppression_recovery/{engine}"
    saved = comparison["comparisons_by_scope"][label]
    result, failures = surfaces.compare(
        label,
        surfaces.common(real_surfaces[a, "suppression_recovery"][index]),
        surfaces.common(real_surfaces[b, "suppression_recovery"][index]),
        registered["criteria"]["trajectory_tolerances"],
        False,
    )
    result |= {
        k: saved[k]
        for k in ("interpretation", "native_convergence_qualified", "forcing_convergence_qualified")
    }
    surfaces.compare_one(label, result, saved)
    assert len(failures) == saved["failed_comparisons"] > 100
    assert len(result["first_failures"]) == 100


def zero_surface(count):
    return [
        {
            u: [0.0] * (0 if j == count and u in ("current_A", "flux_fmol_per_s") else width)
            for u, width in surfaces.WIDTHS.items()
        }
        for j in range(count + 1)
    ]


def unit_limits():
    return dict.fromkeys(surfaces.WIDTHS, 1.0) | {"relative": 0.0}


@pytest.mark.parametrize("count", [40, 80, 160])
def test_variable_grid_scalar_count_and_exact_common_projection(count):
    data = zero_surface(count)
    result, failures = surfaces.compare("synthetic", data, data, unit_limits(), True)
    assert result["comparisons"] == 101 * count + 52 and failures == []
    selected = surfaces.common(data)
    assert len(selected) == 41 and selected[-1] is data[-1]


@pytest.mark.parametrize(
    "j,unit,index,failures",
    [
        (160, "amount_fmol", 23, 1),
        (159, "flux_fmol_per_s", 20, 1),
        (159, "current_A", 6, 1),
        (160, "transfer_fmol", 20, 2),
    ],
)
def test_late_full_grid_corruption_is_not_hidden_by_projection(j, unit, index, failures):
    left, right = zero_surface(160), zero_surface(160)
    left[j][unit][index] = 2.0
    result, ledger = surfaces.compare("synthetic", left, right, unit_limits(), True)
    assert result["failed_comparisons"] == len(ledger) == failures


@pytest.mark.parametrize("mutation", ["grid", "terminal_rhs", "owner", "field", "nan", "bool"])
def test_shape_endpoint_and_numeric_corruption_rejected(mutation):
    a, b = zero_surface(80), zero_surface(80)
    if mutation == "grid":
        a.pop()
    elif mutation == "terminal_rhs":
        a[-1]["current_A"] = [0.0] * 7
    elif mutation == "owner":
        a[20]["amount_fmol"].pop()
    elif mutation == "field":
        a[10]["unregistered"] = []
    else:
        a[3]["voltage_V"][0] = float("nan") if mutation == "nan" else True
    with pytest.raises(ValueError):
        surfaces.compare("synthetic", a, b, unit_limits(), True)


def test_diagnostic_roundoff_allowance_never_relaxes_physical_threshold():
    a, b = zero_surface(40), zero_surface(40)
    a[-1]["amount_fmol"][0] = 2e-20
    result, _ = surfaces.compare("synthetic", a, b, unit_limits() | {"amount_fmol": 1e-21}, True)
    assert result["failed_comparisons"] == 1


@pytest.mark.parametrize(
    "key,value",
    [
        ("comparisons", 1),
        ("failed_comparisons", 0),
        ("required", True),
        ("status", "pass"),
        ("hold_step_s", 0.1),
    ],
)
def test_report_cannot_hide_rejection_or_change_required_scope(comparison, key, value):
    label = "0.00002500/cross_engine/baseline/jax_jit"
    expected = comparison["comparisons_by_scope"][label]
    with pytest.raises(ValueError):
        surfaces.compare_one(label, expected | {key: value}, expected)


def test_synthetic_complete_surface_uses_no_original_comparison_helpers(registered, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("original surface/comparison helper called")

    for name in (
        "compare_panel",
        "compare_scope",
        "across_holds",
        "common_grid",
        "verdict",
        "difference",
        "native_record",
    ):
        monkeypatch.setattr(audit.replay.old, name, forbidden)
    monkeypatch.setattr(audit.replay.old.local, "cells_record", forbidden)
    panels = {}
    for h in surfaces.HOLDS:
        data = zero_surface(round(0.001 / h))
        panels[h] = (
            {condition: data for condition in registered["plan"]["conditions"]},
            {
                (condition, backend, factor): data
                for condition in registered["plan"]["conditions"]
                for backend in ("jax_eager", "jax_jit")
                for factor in (1, 2, 4)
            },
        )
    scopes, failures = surfaces.rebuild(registered, panels)
    assert len(scopes) == 132 and failures == []
    assert surfaces.combine(list(scopes.values()))["comparisons"] == 1121904
    assert surfaces.combine([v for v in scopes.values() if v["required"]])["comparisons"] == 925904
    assert sum(v["required"] for v in scopes.values()) == 92


def synthetic_failures(comparison):
    # Coordinates/counts are fabricated for reporting tests, never physics evidence.
    return [
        {
            "id": f"{name}/{i // 21}/amount_fmol/{i % 21}",
            "scope": name,
            "actual": 2.0,
            "expected": 0.0,
            "normalized_error": 2.0,
        }
        for name, record in comparison["comparisons_by_scope"].items()
        for i in range(record["failed_comparisons"])
    ]


def test_full_synthetic_failure_ledger_is_not_truncated(comparison):
    result = surfaces.classify(synthetic_failures(comparison), comparison["comparisons_by_scope"])
    assert len(result["all_failures"]) == 4173
    assert result["by_family"] == {
        "cross_engine/0.00002500": 150,
        "cross_engine/0.00001250": 40,
        "across_hold": 3983,
    }
    assert result["forcing_convergence_qualified"] is False


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "required", "scope", "coordinate", "quantity", "score"]
)
def test_full_ledger_corruption_rejected(comparison, mutation):
    rows, scopes = synthetic_failures(comparison), copy.deepcopy(comparison["comparisons_by_scope"])
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = rows[0]
    elif mutation == "required":
        scopes[rows[0]["scope"]]["required"] = True
    elif mutation == "scope":
        rows[0]["scope"] = "unknown"
    elif mutation == "coordinate":
        rows[0]["id"] = rows[0]["scope"] + "/999/amount_fmol/0"
    elif mutation == "quantity":
        rows[0]["id"] = rows[0]["scope"] + "/0/unknown/0"
    else:
        rows[0]["normalized_error"] = 0
    with pytest.raises(ValueError):
        surfaces.classify(rows, scopes)


def test_launch_is_detached_and_never_polls(tmp_path, monkeypatch):
    c.write(tmp_path / "registration.json", {})
    monkeypatch.setattr(job, "register", lambda path: {})
    seen = {}

    def popen(command, **kwargs):
        seen.update(command=command, **kwargs)
        return SimpleNamespace(
            pid=12345,
            poll=lambda: pytest.fail("launch polled"),
            wait=lambda: pytest.fail("launch waited"),
        )

    monkeypatch.setattr(job.subprocess, "Popen", popen)
    job.launch(tmp_path)
    result = c.read(tmp_path / "launch.json")
    assert seen["start_new_session"] is True and seen["stdin"] == subprocess.DEVNULL
    assert result["automatic_polling"] is result["capture_rerun"] is False
    assert result["total_timeout_seconds"] == 900
    assert [name for name, _ in job.commands(tmp_path)] == ["audit", "regression"]


def test_launch_failure_has_durable_receipt_and_no_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "register", lambda path: {})

    def fail(*args, **kwargs):
        raise OSError("synthetic launch failure")

    monkeypatch.setattr(job.subprocess, "Popen", fail)
    with pytest.raises(OSError):
        job.launch(tmp_path)
    result = c.read(tmp_path / "failure.json")
    assert result["status"] == "launch_failed_not_started" and result["automatic_retry"] is False


def test_timeout_preserves_partial_audit_and_never_starts_regression(tmp_path, monkeypatch):
    c.write(tmp_path / "registration.json", {"plan": ctx.EXPECTED})
    monkeypatch.setattr(job, "validate_registration", lambda r: None)
    monkeypatch.setattr(ctx.prior.old_job, "capsule", lambda *args: None)
    monkeypatch.setattr(job.resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(job.os, "sched_getaffinity", lambda pid: {0, 1, 2, 3})
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        c.write(tmp_path / "partial.json", {"synthetic": True})
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(job.subprocess, "run", fail)
    with pytest.raises(subprocess.TimeoutExpired):
        job.execute(tmp_path)
    saved = c.read(tmp_path / "failure.json")
    assert len(calls) == 1 and saved["stage"] == "audit"
    assert "partial.json" in saved["files_sha256"] and saved["automatic_retry"] is False
    assert not (tmp_path / "completion.json").exists()


def junit(path, mutation=None):
    suite = ET.Element(
        "testsuite",
        tests="2",
        failures="1" if mutation == "failure" else "0",
        errors="0",
        skipped="1" if mutation == "skip" else "0",
        time="0.01",
    )
    for index in range(2):
        case = ET.SubElement(
            suite,
            "testcase",
            classname="synthetic",
            name=str(0 if mutation == "duplicate" else index),
        )
        if index == 0 and mutation in ("failure", "skip"):
            ET.SubElement(case, "failure" if mutation == "failure" else "skipped")
    if mutation == "count":
        suite.set("tests", "3")
    ET.ElementTree(suite).write(path)


@pytest.mark.parametrize("mutation", ["failure", "skip", "duplicate", "count"])
def test_regression_receipt_rejects_failure_skip_duplicate_or_missing_test(tmp_path, mutation):
    path = tmp_path / "tests.xml"
    junit(path, mutation)
    with pytest.raises(ValueError):
        ctx.test_evidence(path)


def test_closeout_requires_exact_regression_identities(tmp_path, monkeypatch):
    c.write(tmp_path / "audit.json", {})
    junit(tmp_path / "regression.xml")
    monkeypatch.setattr(job, "validate_registration", lambda r: None)
    monkeypatch.setattr(ctx.prior.old_job, "capsule", lambda *args: None)
    monkeypatch.setattr(ctx, "preservation_check", lambda: {})
    monkeypatch.setattr(audit, "validate_result", lambda *args: None)
    with pytest.raises(ValueError, match="Regression identities differ"):
        job.finish(tmp_path, {"expected_regression_identities": [["different", "test"]]}, 0, {})
    assert not (tmp_path / "completion.json").exists()


def test_offline_entrypoint_import_fence():
    code = (
        "import sys, importlib; sys.path.insert(0, " + repr(str(ctx.HERE)) + "); "
        "import refined_audit as a; "
        "assert not any(n.split('.')[0] in a.fence.FORBIDDEN for n in sys.modules); "
        "sys.meta_path.insert(0, a.fence.ImportFence());\n"
        "for name in ('cells', 'betse', 'numpy', 'jax', 'scipy'):\n"
        " try: importlib.import_module(name)\n"
        " except RuntimeError as error: assert 'Offline audit forbids' in str(error)\n"
        " else: raise AssertionError('forbidden import succeeded: ' + name)\n"
        "print('read_only_fence_pass')\n"
    )
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", code],
        cwd=c.ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert result.stdout.strip() == "read_only_fence_pass"


def test_full_panel_loader_routes_84_saved_records_without_relabelling(registered, monkeypatch):
    coarse = c.read(ctx.prior.prior.COARSE / "registration.json")
    seen = []

    def read(path):
        path = Path(path)
        if path == ctx.prior.prior.COARSE / "registration.json":
            return coarse
        assert path.name == "result.json" and path.is_file()
        seen.append(path)
        return {"numerical": {"synthetic_path": str(path)}, "synthetic_path": str(path)}

    monkeypatch.setattr(c, "read", read)
    monkeypatch.setattr(surfaces.base, "native_surface", lambda r, v: v["synthetic_path"])
    monkeypatch.setattr(surfaces.base, "cells_surface", lambda r, v: v["synthetic_path"])
    panels = surfaces.load_panels(registered)
    assert len(seen) == len(set(seen)) == 84  # 12 observed native + 72 Cells records
    assert all(len(n) == 4 and len(cs) == 24 for n, cs in panels.values())
    assert sum(p.is_relative_to(ctx.SESSION) for p in seen) == 22
    assert sum(p.is_relative_to(ctx.prior.FAILED) for p in seen) == 34  # 8 native + 26 Cells
    assert sum(p.is_relative_to(ctx.prior.prior.COARSE) for p in seen) == 28


@pytest.fixture
def audit_fixture(tmp_path, comparison):
    """Synthetic output-schema fixture, not an independent numerical result."""
    scopes = copy.deepcopy(comparison["comparisons_by_scope"])
    rows = synthetic_failures(comparison)
    for name, scope in scopes.items():
        failed = [
            {k: v for k, v in row.items() if k != "scope"} for row in rows if row["scope"] == name
        ]
        scope["first_failures"] = failed[:100]
        if failed:
            scope["maximum_normalized_error"], scope["worst"] = 2.0, failed[0]
    total = surfaces.combine(list(scopes.values()))
    required = surfaces.combine([v for v in scopes.values() if v["required"]])
    ledger = surfaces.classify(rows, scopes)
    surface = {
        "scope": audit.SCOPE,
        "all_surfaces": total,
        "required_surfaces": required,
        "comparisons_by_scope": scopes,
    }
    c.write(tmp_path / "independent-surfaces.json", surface)
    c.write(tmp_path / "failure-ledger.json", ledger)
    r = {"sources": ctx.sources()}
    result = {
        "schema": "cells.betse_refined_response_saved_audit@1",
        "status": "saved_data_audit_pass_pending_regression",
        "scope": audit.SCOPE,
        "anchors": ctx.ANCHORS,
        "driver_sha256": c.sha(ctx.HERE / "refined_audit.py"),
        "frozen_comparisons_replayed": 2494936,
        "internal_laws_replayed": comparison["internal_laws"],
        "required_gates_replayed": comparison["required_gates"],
        "independent_surfaces": total,
        "independent_required_surfaces": required,
        "independent_surface_scopes": 132,
        "failure_classification": ledger["by_family"],
        "independent_surfaces_sha256": c.sha(tmp_path / "independent-surfaces.json"),
        "failure_ledger_sha256": c.sha(tmp_path / "failure-ledger.json"),
        "model_calls": 0,
        "model_imports": [],
        "finest_held_response_qualified": False,
        "native_convergence_qualified": False,
        "forcing_convergence_qualified": False,
        "capture_rerun": False,
        "original_packets_rewritten": False,
        "biology_validated": False,
        "gpu_tested": False,
        "capture_metadata": {"original_cells_worker_receipt_invented": False},
    }
    return result, r


def test_audit_output_linkage_positive_synthetic_fixture(tmp_path, audit_fixture):
    result, r = audit_fixture
    audit.validate_result(result, tmp_path, r)
    assert result["finest_held_response_qualified"] is False


@pytest.mark.parametrize(
    "mutation",
    ["qualified", "model", "scope", "count", "digest", "truncated", "scope_total", "examples"],
)
def test_audit_output_corruptions_rejected_even_if_rehashed(tmp_path, audit_fixture, mutation):
    result, r = audit_fixture
    result = copy.deepcopy(result)
    if mutation == "qualified":
        result["finest_held_response_qualified"] = True
    elif mutation == "model":
        result["model_calls"] = 1
    elif mutation == "scope":
        result["scope"]["duration_s"] = 1.0
    elif mutation == "count":
        result["independent_surface_scopes"] = 131
    elif mutation == "digest":
        result["failure_ledger_sha256"] = "0" * 64
    elif mutation == "truncated":
        path = tmp_path / "failure-ledger.json"
        data = c.read(path)
        data["all_failures"].pop()
        path.write_text(json.dumps(data))
        result["failure_ledger_sha256"] = c.sha(path)
    else:
        path = tmp_path / "independent-surfaces.json"
        data = c.read(path)
        scope = next(v for v in data["comparisons_by_scope"].values() if v["failed_comparisons"])
        if mutation == "scope_total":
            scope["comparisons"] -= 1
        else:
            scope["first_failures"] = []
        path.write_text(json.dumps(data))
        result["independent_surfaces_sha256"] = c.sha(path)
    with pytest.raises(ValueError):
        audit.validate_result(result, tmp_path, r)
