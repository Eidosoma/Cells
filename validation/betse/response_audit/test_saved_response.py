"""D082 saved-data, immutable-report and detached-job checks; never run either model."""

import copy
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest
import response_audit as audit
import response_audit_context as ctx
import response_audit_job as job

c = ctx.c


@pytest.fixture(scope="module")
def registered():
    return c.read(ctx.SESSION / "registration.json")


@pytest.fixture(scope="module")
def comparison():
    return c.read(ctx.SESSION / "comparison.json")


@pytest.fixture(scope="module")
def surfaces(registered):
    return {
        condition: (
            audit.native_surface(
                registered,
                c.read(ctx.SESSION / f"native/{condition}/observed/result.json")["numerical"],
            ),
            audit.cells_surface(
                registered,
                c.read(ctx.SESSION / f"cells/{condition}/jax_jit/subdivision-4/result.json"),
            ),
        )
        for condition in ("baseline", "suppression_recovery", "static_blocked")
    }


def test_preservation_and_explicit_metadata_amendment():
    result = ctx.preservation_check()
    assert result["baseline_files"] == 969
    assert result["capture_files_unchanged"] == 150
    assert result["accepted_implementation_files_unchanged"] == 352
    assert result["production_modules_unchanged"] == 51
    assert len(ctx.prior.old.sources()) == 88
    assert ctx.EXTERNAL_METADATA["changed_by_audit"] is False


def test_historical_guard_still_rejects_external_ignore_change():
    with pytest.raises(ValueError, match="Unexpected pre-existing edit"):
        ctx.prior.preservation_check()


def test_ignored_old_receipts_remain_in_preservation_inventory():
    current = c.read(ctx.PRESERVATION)["baseline_sha256"]
    previous = c.read(ctx.prior.PRESERVATION)["baseline_sha256"]
    receipts = {n for n in previous if n.startswith("reports/ref-") and n.endswith(".xml")}
    assert receipts
    assert all(current[n] == previous[n] == c.sha(c.ROOT / n) for n in receipts)


def test_saved_packet_manifest_and_execution_metadata(registered):
    assert len(ctx.verify_manifest(ctx.SESSION, registered)["files_sha256"]) == 146
    result = audit.inspect_metadata(registered, ctx.SESSION)
    assert result["native_runs"] == 8 and result["cells_runs"] == 24
    assert result["payloads"] == 146 and result["total_files"] == 150
    assert result["capture_bytes"] == 56020787
    assert result["capture_seconds"] == pytest.approx(715.7691208649194)
    assert result["warnings"] == []


@pytest.fixture
def manifest_fixture(tmp_path, registered):
    """Structural-only fixture: tiny dummy payloads, never executable native pickles."""
    names = ctx.expected_paths(registered)
    for name in names | ctx.OPERATIONAL:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"{}")
    c.write(tmp_path / "failure.json", {"files_sha256": {n: c.sha(tmp_path / n) for n in names}})
    return tmp_path


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "digest", "omit_hash", "add_hash", "link", "empty", "pass"]
)
def test_manifest_rejects_corruption_even_when_rehashed(manifest_fixture, registered, mutation):
    output, target = manifest_fixture, manifest_fixture / "native.json"
    saved = c.read(output / "failure.json")
    if mutation == "missing":
        target.unlink()
        saved["files_sha256"].pop("native.json")
    elif mutation == "extra":
        (output / "extra.json").write_bytes(b"{}")
        saved["files_sha256"]["extra.json"] = c.sha(output / "extra.json")
    elif mutation == "digest":
        target.write_bytes(b"changed")
    elif mutation == "omit_hash":
        saved["files_sha256"].pop("native.json")
    elif mutation == "add_hash":
        saved["files_sha256"]["missing.json"] = "0" * 64
    elif mutation == "link":
        target.unlink()
        target.symlink_to(output / "cells.json")
    elif mutation == "empty":
        target.write_bytes(b"")
        saved["files_sha256"]["native.json"] = c.sha(target)
    else:
        (output / "capture.json").write_bytes(b"{}")
    (output / "failure.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError):
        ctx.verify_manifest(output, registered)


@pytest.mark.parametrize(
    "name,key,value",
    [
        ("failure.json", "stage", "cells"),
        ("failure.json", "automatic_retry", True),
        ("failure.json", "elapsed_seconds", 9999),
        ("launch.json", "pid", 0),
        ("launch.json", "automatic_polling", True),
        ("launch.json", "launched_utc", "2099-01-01T00:00:00+00:00"),
        ("native.json", "warnings", ["warning"]),
        ("native.json", "installed_python_sha256", {}),
        ("native.json", "pairs", []),
        ("native.json", "results", []),
        ("cells.json", "device", "gpu"),
        ("cells.json", "x64_enabled", False),
        ("cells.json", "results", {}),
        ("cells-started/00.json", "started_utc", "2099-01-01T00:00:00+00:00"),
        ("comparison.json", "trajectory_qualified", True),
        ("comparison.json", "failed_comparisons", 0),
    ],
)
def test_metadata_rejects_semantic_corruption(registered, monkeypatch, name, key, value):
    # Replace decoded input only; every byte of the real packet stays untouched.
    read, target = c.read, ctx.SESSION / name
    modified = read(target) | {key: value}
    monkeypatch.setattr(
        c, "read", lambda path: copy.deepcopy(modified) if Path(path) == target else read(path)
    )
    with pytest.raises(ValueError):
        audit.inspect_metadata(registered, ctx.SESSION)


def test_frozen_reporting_bug_is_reproduced_without_edit():
    original = c.sha(c.HERE / "held_response_check.py")
    result = audit.reporting_defect()
    assert result["synthetic_reproduction"] is True
    assert result["physical_comparisons_changed"] is False
    assert c.sha(c.HERE / "held_response_check.py") == original


def test_snapshot_never_aliases_later_or_nested_mutations():
    checks = audit.AuditChecks()
    empty = audit.immutable_summary(checks)
    limits = {"amount_fmol": 1.0, "relative": 0.0}
    checks.compare("first", 2.0, 0.0, "amount_fmol", limits)
    snapshot = audit.immutable_summary(checks)
    checks.compare("second", 3.0, 0.0, "amount_fmol", limits)
    checks.failures[0]["id"] = "mutated"
    assert empty["first_failures"] == [] and empty["worst"] is None
    assert snapshot["first_failures"][0]["id"] == snapshot["worst"]["id"] == "first"
    assert snapshot["failed_comparisons"] == len(snapshot["first_failures"]) == 1


def replay_body(value):
    return {k: v for k, v in value.items() if k not in audit.WORKER_FIELDS}


def test_corrected_review_changes_only_the_alias_field(comparison):
    original = copy.deepcopy(comparison)
    reviewed = audit.corrected_report(comparison, replay_body(comparison))
    expected = copy.deepcopy(comparison)
    expected["internal_laws"]["first_failures"] = []
    assert reviewed["comparison"] == expected
    assert reviewed["comparison"]["failed_comparisons"] == 150
    assert reviewed["comparison"]["status"] == "failed_not_qualified"
    assert reviewed["changed_fields"] == ["internal_laws.first_failures"]
    assert reviewed["physical_criteria_changed"] is False
    assert comparison == original


@pytest.mark.parametrize("mutation", ["replay", "count", "failure", "maximum", "list"])
def test_correction_cannot_hide_other_differences(comparison, mutation):
    bad = copy.deepcopy(comparison)
    internal = bad["internal_laws"]
    if mutation == "count":
        internal["comparisons"] -= 1
    elif mutation == "failure":
        internal["failed_comparisons"] = 1
    elif mutation == "maximum":
        internal["maximum_normalized_error"] = 2
    elif mutation == "list":
        internal["first_failures"] = []
    replay = copy.deepcopy(replay_body(bad))
    if mutation == "replay":
        replay["failed_comparisons"] = 0
    with pytest.raises(ValueError):
        audit.corrected_report(bad, replay)


def test_normalization_uses_declared_expected_value_scale():
    checks = audit.AuditChecks()
    checks.compare("a", 2.0, 1.0, "amount_fmol", {"amount_fmol": 0.1, "relative": 0.2})
    assert checks.maximum == pytest.approx(1 / 0.3)
    assert checks.failed_count == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "2"])
def test_nonfinite_or_nonnumeric_comparison_rejected(value):
    with pytest.raises(ValueError, match="Invalid independent comparison"):
        audit.AuditChecks().compare("a", value, 1.0, "x", {"x": 0.1, "relative": 0.2})


@pytest.mark.parametrize(
    "condition,failures", [("baseline", 34), ("suppression_recovery", 7), ("static_blocked", 0)]
)
def test_saved_cross_engine_scopes_keep_original_verdicts(
    registered, comparison, surfaces, condition, failures
):
    checks = audit.AuditChecks()
    label = f"cross_engine/{condition}/jax_jit"
    result = audit.compare_surface(
        label, *surfaces[condition], registered["criteria"]["trajectory_tolerances"], checks
    )
    assert checks.count == 4092 and checks.failed_count == failures
    original = comparison["comparisons_by_scope"][label]
    assert result["failed_comparisons"] == original["failed_comparisons"]
    assert (
        result["maximum_absolute_errors"]["amount_fmol"]
        == original["maximum_absolute_errors"]["amount_fmol"]
    )
    assert all(f["id"].endswith(("/amount_fmol/21", "/amount_fmol/22")) for f in checks.failures)


@pytest.mark.parametrize("mutation", ["time", "endpoint", "owner", "transfer"])
def test_independent_surface_axes_fail_closed(registered, surfaces, mutation):
    left, right = copy.deepcopy(surfaces["baseline"])
    if mutation == "time":
        left.pop()
    elif mutation == "endpoint":
        left[-1]["current_A"] = [0.0] * 7
    elif mutation == "owner":
        left[0]["amount_fmol"].pop()
    else:
        left[0]["transfer_fmol"].pop()
    with pytest.raises(ValueError):
        audit.compare_surface(
            "bad", left, right, registered["criteria"]["trajectory_tolerances"], audit.AuditChecks()
        )


def test_endpoint_is_state_and_ledger_not_an_invented_native_rhs(surfaces):
    native, cells = surfaces["baseline"]
    for surface in (native, cells):
        assert surface[-1]["current_A"] == surface[-1]["flux_fmol_per_s"] == []
        assert any(v != 0 for v in surface[-1]["transfer_fmol"])
        assert len(surface[-1]["voltage_V"]) == 7


def test_saved_constant_input_ladder_does_not_claim_pulse_convergence(registered, surfaces):
    result = audit.retained_baseline_ladder(
        registered, {"baseline/jax_jit/subdivision-4": surfaces["baseline"][1]}
    )
    assert [r["native_dt_s"] for r in result["rows"]] == [25e-6, 12.5e-6, 6.25e-6]
    assert result["rows"][0]["failed_comparisons"] > 0
    assert result["rows"][-1]["failed_comparisons"] == 0
    assert all(0.49 < ratio < 0.51 for ratio in result["successive_amount_error_ratios"])
    assert result["pulse_native_convergence_qualified"] is False
    assert result["new_simulation"] is False


def synthetic_failures():
    return [
        {"id": f"cross_engine/{condition}/{backend}/{j}/amount_fmol/{species}"}
        for condition in ("baseline", "zero_amplitude", "suppression_recovery")
        for backend in ("jax_eager", "jax_jit")
        for j in range(41)
        for species in (21, 22)
    ][:150]


def test_complete_failure_classification_keeps_every_identity(registered):
    result = audit.classify(synthetic_failures(), registered["common_times_s"])
    assert len(result["all_failures"]) == 150
    assert result["all_in_shared_bath"] is True
    assert {f["species"] for f in result["all_failures"]} == {"Na", "K"}
    assert result["pulse_native_convergence_established"] is False


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "condition", "backend", "time", "quantity"]
)
def test_failure_classification_cannot_silently_drop_or_relabel(registered, mutation):
    failures = synthetic_failures()
    if mutation == "missing":
        failures.pop()
    elif mutation == "duplicate":
        failures[-1] = failures[0]
    else:
        parts = failures[0]["id"].split("/")
        parts[{"condition": 1, "backend": 2, "time": 3, "quantity": 4}[mutation]] = "wrong"
        failures[0] = {"id": "/".join(parts)}
    with pytest.raises(ValueError):
        audit.classify(failures, registered["common_times_s"])


def legacy_xml(tmp_path):
    tree = ET.parse(c.ROOT / "reports/ref-003e1-response-checks-03.xml")
    suite = next(tree.iter("testsuite"))
    cases = list(suite.findall("testcase"))
    case = next(
        case for case in cases if (case.get("classname"), case.get("name")) == job.LEGACY_GUARD
    )
    suite.set("failures", "1")
    ET.SubElement(case, "failure", {"message": "ValueError: Unexpected pre-existing edit"})
    path = tmp_path / "legacy.xml"
    tree.write(path)
    return tree, suite, cases, case, path


def test_legacy_guard_is_reported_as_one_failure_not_a_green_suite(tmp_path):
    *_, path = legacy_xml(tmp_path)
    result = job.legacy_outcome(path, 1)
    assert result["passed"] == 121 and result["counts"]["failures"] == 1
    assert result["status"] == "expected_metadata_guard_rejection_not_all_tests_pass"
    assert result["assertions_changed"] is result["tests_skipped"] is False


@pytest.mark.parametrize(
    "mutation", ["extra_failure", "wrong_test", "wrong_reason", "skip", "duplicate", "returncode"]
)
def test_legacy_metadata_exception_is_exactly_bounded(tmp_path, mutation):
    tree, suite, cases, case, path = legacy_xml(tmp_path)
    if mutation == "extra_failure":
        ET.SubElement(next(c for c in cases if c is not case), "failure", {"message": "other"})
        suite.set("failures", "2")
    elif mutation == "wrong_test":
        case.set("name", "other_test")
    elif mutation == "wrong_reason":
        case.find("failure").set("message", "physical comparison failed")
    elif mutation == "skip":
        suite.set("skipped", "1")
    elif mutation == "duplicate":
        other = next(c for c in cases if c is not case)
        other.set("classname", case.get("classname"))
        other.set("name", case.get("name"))
    tree.write(path)
    with pytest.raises(ValueError):
        job.legacy_outcome(path, 0 if mutation == "returncode" else 1)


def test_capsule_bytes_not_just_names_are_authenticated(tmp_path):
    with zipfile.ZipFile(tmp_path / "sources.zip", "x") as archive:
        archive.writestr("example.py", "changed")
    with pytest.raises(ValueError, match="Audit capsule differs"):
        job.capsule(tmp_path, {"sources": {"example.py": hashlib.sha256(b"original").hexdigest()}})


def test_job_commands_have_no_native_worker_and_do_not_skip_legacy_tests(tmp_path):
    commands = dict(job.commands(tmp_path))
    assert set(commands) == {"audit", "legacy_regression", "regression"}
    assert all(str(c.REFERENCE_PYTHON) not in command for command in commands.values())
    assert str(c.HERE / "test_held_response.py") in commands["legacy_regression"]
    assert str(c.HERE / "test_held_response_check.py") in commands["legacy_regression"]
    assert not any(arg in ("-k", "--ignore") for arg in commands["legacy_regression"])


def test_detached_launch_returns_pid_without_wait_or_poll(tmp_path, monkeypatch):
    c.write(tmp_path / "registration.json", {"synthetic": True})
    monkeypatch.setattr(job, "register", lambda output: None)
    called = {}

    def launch(command, **kwargs):
        called.update(command=command, **kwargs)
        return SimpleNamespace(pid=123)  # No wait/poll method deliberately exists.

    monkeypatch.setattr(job.subprocess, "Popen", launch)
    job.launch(tmp_path)
    assert called["start_new_session"] is True
    assert called["stdin"] == subprocess.DEVNULL
    receipt = c.read(tmp_path / "launch.json")
    assert receipt["pid"] == 123
    assert receipt["automatic_polling"] is receipt["capture_rerun"] is False


@pytest.mark.parametrize("outcome", ["timeout", "nonzero"])
def test_job_failure_is_durable_and_never_retries(tmp_path, monkeypatch, outcome):
    c.write(tmp_path / "registration.json", {"synthetic": True})
    monkeypatch.setattr(job, "validate_registration", lambda registered: None)
    monkeypatch.setattr(job, "capsule", lambda output, registered: None)
    monkeypatch.setattr(job.resource, "setrlimit", lambda *args: None)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return SimpleNamespace(returncode=2)

    monkeypatch.setattr(job.subprocess, "run", run)
    with pytest.raises((ValueError, subprocess.TimeoutExpired)):
        job.execute(tmp_path)
    failure = c.read(tmp_path / "failure.json")
    assert failure["stage"] == "audit" and len(calls) == 1
    assert failure["automatic_retry"] is failure["capture_rerun"] is False
    assert failure["status"] == "audit_failed_not_closed"
    assert not (tmp_path / "completion.json").exists()


def test_clean_offline_process_import_fence():
    program = (
        "import sys; import response_audit as a; "
        "assert not any(n.split('.')[0] in a.frozen.fence.FORBIDDEN for n in sys.modules); "
        "sys.meta_path.insert(0, a.frozen.fence.ImportFence()); import numpy"
    )
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", program],
        cwd=ctx.HERE,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert "Offline audit forbids model/array import: numpy" in result.stderr
