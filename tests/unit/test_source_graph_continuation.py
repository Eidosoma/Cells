"""Continuation engineering fixtures; no test runs a 1000-unit path."""

import copy
import inspect
import json
import os
import subprocess
from datetime import datetime, timezone
from time import perf_counter

import numpy as np
import pytest

from scripts import audit_source_graph_continuation as audit
from scripts import audit_source_graph_paths as prior_audit
from scripts import continue_source_graph_paths as continuation
from scripts import qualify_source_graph_paths as campaign
from tests import reference_graph_paths as paths
from tests import reference_source_graph_numerics as ref


def test_real_saved_handoff_exact_remaining_order_and_unchanged_settings():
    output = continuation.PRIOR.parent / "continuation-01"
    existed = output.exists()
    spec = continuation.specification(output)
    assert output.exists() == existed
    assert len(spec["imported_cases"]) == 8
    assert spec["new_cases"] == [
        f"M_to_E/{case}"
        for case in (
            "blocked",
            "ionic_only",
            "mirna_only",
            "same_state",
            "one_neighbor",
            "isolated",
        )
    ]
    assert spec["planned_attempts"] == [
        f"{case}/{method}" for case in spec["new_cases"] for method in ("radau", "bdf", "refined")
    ]
    old = ref.read_json(continuation.PRIOR / "registration.json")
    for key in (
        "cases",
        "prepared_packets",
        "numerics",
        "resources",
        "methods",
        "runtime",
        "observation_times",
    ):
        assert spec[key] == old[key]
    assert spec["prior_incomplete_attempts"][0]["key"] == "M_to_E/blocked/radau"
    assert spec["prior_incomplete_attempts"][0]["status"] == "incomplete_timeout"
    assert spec["storage_budget"]["prior_artifact_bytes_including_stopped_attempt"] == 387154280
    assert spec["storage_budget"]["new_session_artifact_limit_bytes"] == 686587544
    effective = continuation.execution_registration(spec)
    assert effective["resources"] == old["resources"] | {"artifact_budget_bytes": 686587544}
    assert spec["resources"]["artifact_budget_bytes"] == 1073741824


def test_pinned_old_receipt_tamper_refused_without_reading_or_mutating_real_evidence(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(continuation, "PRIOR", tmp_path)
    ref.write_json(tmp_path / "registration.json", {})
    with pytest.raises(ValueError, match="Prior evidence changed"):
        continuation.prior_evidence()


@pytest.mark.parametrize("kind", ["case", "trajectory", "promote", "integrity"])
def test_import_requires_exact_audited_complete_subset(monkeypatch, kind):
    original = campaign.frozen.pinned_json

    def changed(path, digest):
        result = original(path, digest)
        if path == continuation.PRIOR_AUDIT:
            if kind == "case":
                result["case_audits"].pop("E_to_M/active")
            elif kind == "trajectory":
                result["complete_trajectory_audits"]["M_to_E/blocked/radau"] = {}
            elif kind == "promote":
                result["incomplete_attempts_not_numerically_promoted"] = False
            else:
                result["integrity"]["artifact_bytes"] += 1
        return result

    monkeypatch.setattr(campaign.frozen, "pinned_json", changed)
    with pytest.raises(ValueError, match="does not permit reuse"):
        continuation.prior_evidence()


@pytest.fixture
def fixture_campaign(monkeypatch, tmp_path):
    """Mock only old-evidence discovery; exercise real registration/run/integrity logic."""
    old = campaign.specification()
    prior = tmp_path / "sessions/old"
    prior.mkdir(parents=True)
    (prior / "retained.log").write_text("retained incomplete attempt\n")
    imports = {
        case: {"directory": f"sessions/old/{case}", "receipt_hashes": {}}
        for case in list(dict.fromkeys(k.rsplit("/", 1)[0] for k in old["planned_attempts"]))[:8]
    }
    stopped = {"attempts": [{"key": "M_to_E/blocked/radau", "status": "incomplete_timeout"}]}
    integrity = {"artifact_bytes": continuation.tree_bytes(prior)}
    monkeypatch.setattr(continuation, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(continuation, "PRIOR", prior)
    monkeypatch.setattr(continuation, "PRIOR_AUDIT", tmp_path / "old-audit.json")
    monkeypatch.setattr(
        continuation,
        "prior_evidence",
        lambda: (
            copy.deepcopy(old),
            copy.deepcopy(stopped),
            integrity.copy(),
            copy.deepcopy(imports),
        ),
    )
    monkeypatch.setattr(continuation, "SOURCES", ["fixture-source.txt"])
    (tmp_path / "fixture-source.txt").write_text("registered fixture source\n")
    for key, value in campaign.THREADS.items():
        monkeypatch.setenv(key, value)
    return prior.parent / "new"


def test_exclusive_registration_roundtrip_and_no_mutation(fixture_campaign):
    output = fixture_campaign
    before = continuation.tree_bytes(continuation.PRIOR)
    registration = continuation.register(output)
    assert continuation.check_registration(output) == registration
    assert continuation.tree_bytes(continuation.PRIOR) == before
    with pytest.raises(FileExistsError):
        continuation.register(output)


@pytest.mark.parametrize(
    "field", ["planned_attempts", "new_cases", "imported_cases", "storage_budget", "runtime"]
)
def test_registration_tampering_refused(fixture_campaign, field):
    output = fixture_campaign
    registration = continuation.register(output)
    registration[field] = []
    (output / "registration.json").write_text(json.dumps(registration))
    with pytest.raises(ValueError, match="registration inputs"):
        continuation.check_registration(output)


def test_changed_new_source_refused(fixture_campaign):
    continuation.register(fixture_campaign)
    (continuation.ROOT / "fixture-source.txt").write_text("changed source\n")
    with pytest.raises(ValueError, match="source identity"):
        continuation.check_registration(fixture_campaign)


def test_unknown_sibling_refused_and_old_root_not_an_output(fixture_campaign):
    prior = continuation.PRIOR
    used = continuation.tree_bytes(prior)
    with pytest.raises(ValueError, match="new direct sibling"):
        continuation.budget(prior, used, 10_000_000)
    (prior.parent / "unknown.log").write_text("unregistered artifact")
    with pytest.raises(ValueError, match="Unexpected session"):
        continuation.budget(fixture_campaign, used, 10_000_000)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "linked_root"])
def test_linked_artifacts_cannot_hide_or_alias_retained_evidence(tmp_path, kind):
    directory = tmp_path / "data"
    directory.mkdir()
    source = directory / "source"
    source.write_bytes(b"evidence")
    if kind == "symlink":
        (directory / "alias").symlink_to(source)
    elif kind == "hardlink":
        os.link(source, directory / "alias")
    else:
        alias = tmp_path / "alias"
        alias.symlink_to(directory, target_is_directory=True)
        directory = alias
    with pytest.raises(ValueError, match="[Ll]ink|real directory"):
        continuation.tree_bytes(directory)


def test_aggregate_budget_and_unchanged_writer_lower_local_cap(fixture_campaign):
    prior = continuation.PRIOR
    used = continuation.tree_bytes(prior)
    with pytest.raises(ref.BudgetExceeded, match="Aggregate"):
        continuation.budget(fixture_campaign, used, used + paths.TAIL_RESERVE - 1)
    fixture_campaign.mkdir()
    spec = {
        "resources": {"artifact_budget_bytes": 10_000_000},
        "storage_budget": {"new_session_artifact_limit_bytes": paths.TAIL_RESERVE + 8000},
    }
    effective = continuation.execution_registration(spec)
    with pytest.raises(ref.BudgetExceeded, match="before writing compressed"):
        paths.save_arrays(
            fixture_campaign / "not-written.npz",
            {"data": np.zeros(1000)},
            fixture_campaign,
            effective["resources"]["artifact_budget_bytes"],
        )
    assert not (fixture_campaign / "not-written.npz").exists()
    assert spec["resources"]["artifact_budget_bytes"] == 10_000_000


def test_worker_restarts_exact_primary_at_zero_not_partial_solver_state(
    monkeypatch, fixture_campaign
):
    output = fixture_campaign
    registration = continuation.register(output)
    ref.write_json(
        output / "session.json",
        {
            "registration_sha256": ref.sha(output / "registration.json"),
            "wall_budget_seconds": 3600,
            "automatic_retry": False,
            "started_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    (output / "attempts.jsonl").write_text(
        json.dumps(
            {
                "key": "M_to_E/blocked/radau",
                "initial_time": 0.0,
                "status": "started",
                "attempt_id": f"{registration['output_directory']}/M_to_E/blocked/radau",
            }
        )
        + "\n"
    )
    calls = []

    def capture(model, target, **kwargs):
        calls.append((model, target, kwargs))
        return "no integration in this fixture"

    monkeypatch.setattr(paths, "integrate", capture)
    with pytest.raises(ValueError, match="Unregistered"):
        continuation.worker(output, "M_to_E/active/radau")
    assert not calls
    assert continuation.worker(output, "M_to_E/blocked/radau") == "no integration in this fixture"
    model, target, options = calls[0]
    np.testing.assert_array_equal(model.anchor, registration["cases"]["M_to_E/blocked"]["primary"])
    np.testing.assert_array_equal(model.initial()[6 * model.n :], 0)
    assert target == output / "M_to_E/blocked/radau" and options["duration"] == 1000
    assert options["artifact_root"] == output
    assert (
        options["resources"]["artifact_budget_bytes"]
        < registration["resources"]["artifact_budget_bytes"]
    )
    assert "restart" not in options and "initial_time" not in options
    ref.write_json(output / "failure.json", {"status": "incomplete"})
    with pytest.raises(ValueError, match="closed continuation"):
        continuation.worker(output, "M_to_E/blocked/bdf")
    assert len(calls) == 1


@pytest.mark.parametrize("timeout", [True, False])
def test_one_stopped_attempt_retained_no_retry_and_integrity_audit(
    monkeypatch, fixture_campaign, timeout
):
    calls = []

    def stopped(*args, **kwargs):
        calls.append((args, kwargs))
        kwargs["stdout"].write("fixture: retained stopped attempt\n")
        if timeout:
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
        return subprocess.CompletedProcess(args[0], 1)

    monkeypatch.setattr(continuation.subprocess, "run", stopped)
    output = fixture_campaign
    with pytest.raises(subprocess.TimeoutExpired if timeout else ValueError):
        continuation.run(output)
    assert len(calls) == 1 and 0 < calls[0][1]["timeout"] <= 900
    registration, receipt, name = audit.check_integrity(output)
    assert name == "failure.json" and receipt["no_automatic_retry"]
    assert len(receipt["not_started"]) == 17 and len(receipt["attempts"]) == 1
    assert receipt["attempts"][0]["key"] == "M_to_E/blocked/radau"
    assert len(registration["imported_cases"]) == 8
    with pytest.raises(FileExistsError):
        continuation.run(output)
    assert len(calls) == 1
    (output / "extra.log").write_text("not in final inventory")
    with pytest.raises(ValueError, match="payload inventory"):
        audit.check_integrity(output)


def test_short_remaining_path_uses_existing_numerics_and_independent_audit(tmp_path):
    registration = campaign.specification()
    case = "M_to_E/blocked"
    registration["duration"] = 0.03
    registration["storage_budget"] = {"new_session_artifact_limit_bytes": 20_000_000}
    execution = continuation.execution_registration(registration)
    for variant, (method, refinement) in campaign.METHODS.items():
        paths.integrate(
            campaign.graph.Model(registration["cases"][case]),
            tmp_path / case / variant,
            method=method,
            refinement=refinement,
            duration=0.03,
            numerics=execution["numerics"],
            resources=execution["resources"],
            artifact_root=tmp_path,
        )
        model = campaign.graph.Model(registration["cases"][case])
        checked = prior_audit.audit_trajectory(
            tmp_path / case / variant, model.case, registration, model.panel, perf_counter() + 30
        )
        assert checked["maximum_accounting_residual"] <= 2e-9


def test_mock_complete_session_has_exactly_18_new_attempts_and_14_composite_cases(
    monkeypatch, fixture_campaign
):
    calls = []
    comparison = {"status": "pass", "maximum_score": 0, "maximum_accounting_residual": 0}
    observations = {"scope": "engineering_fixture_not_a_scientific_result"}

    def success(command, **kwargs):
        calls.append(command[-1])
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(continuation.subprocess, "run", success)
    monkeypatch.setattr(campaign, "compare", lambda *a: comparison)
    monkeypatch.setattr(campaign, "observe", lambda *a: observations)
    monkeypatch.setattr(
        continuation,
        "case_result",
        lambda folder: {"comparison": comparison, "observations": observations},
    )
    result = continuation.run(fixture_campaign)
    registration, audited, name = audit.check_integrity(fixture_campaign)
    assert result == audited and name == "verification.json"
    assert calls == registration["planned_attempts"] and len(calls) == 18
    assert len(result["cases"]) == 14 and len(result["new_cross_qualified_cases"]) == 6
    assert not result["NUM005c_complete"]
    assert result["independent_continuation_audit"] == "pending"
    result["case_directories"]["M_to_E/blocked"] = registration["imported_cases"]["M_to_E/active"][
        "directory"
    ]
    (fixture_campaign / "verification.json").write_text(json.dumps(result))
    with pytest.raises(ValueError, match="Composite case sources"):
        audit.check_integrity(fixture_campaign)


def test_continuation_is_reference_only_and_auditor_has_no_rhs():
    for module in (continuation, audit):
        source = inspect.getsource(module)
        assert "import cells" not in source and "from cells" not in source
        assert "import bitsey" not in source
    assert "model.derivative" not in inspect.getsource(audit)
