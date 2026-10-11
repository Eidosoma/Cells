"""D035 short engineering checks; no test runs a 1000-unit refinement."""

import copy
import inspect
import json
import subprocess
from datetime import datetime, timezone
from time import perf_counter

import numpy as np
import pytest

from scripts import audit_graph_refinement as audit
from scripts import refine_graph_reference as trial
from tests import reference_graph_comparison as comparison

ref, paths, campaign = trial.ref, trial.paths, trial.campaign


@pytest.fixture(scope="module")
def real_spec():
    return trial.specification(trial.OUTPUT_PARENT / "bdf-tight-01")


def test_one_exact_refinement_no_old_case_promotion(real_spec):
    assert real_spec["case_key"] == "M_to_E/mirna_only"
    assert real_spec["case"] == campaign.cases()["M_to_E/mirna_only"]
    assert real_spec["planned_attempts"] == ["bdf_tight"]
    assert real_spec["methods"]["bdf_tight"] == ["BDF", 0.1]
    assert len(real_spec["imports"]) == 3 and real_spec["duration"] == 1000
    assert real_spec["numerics"] == campaign.frozen.load_protocol()["numerics"]
    assert real_spec["storage_budget"]["prior_bytes"] == 511109773
    assert real_spec["storage_budget"]["new_root_limit_bytes"] == 562632051
    assert not real_spec["case_qualification_changed"] and not real_spec["candidate_selected"]
    assert trial.execution(real_spec)["resources"]["artifact_budget_bytes"] == 562632051
    assert real_spec["resources"]["artifact_budget_bytes"] == 1073741824
    assert trial.directories(real_spec)["bdf"] == trial.PRIOR / "M_to_E/mirna_only/bdf"
    assert real_spec["amendment"]["promotion_policy"].startswith("diagnostic_agreement_only")


def test_old_pin_tampering_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(trial, "ROOT", tmp_path)
    (tmp_path / "reports").mkdir()
    ref.write_json(tmp_path / trial.CLOSEOUT, {"status": "pass"})
    with pytest.raises(ValueError, match="Frozen input changed"):
        trial.evidence()


@pytest.fixture
def fixture_campaign(monkeypatch, tmp_path):
    parent = campaign.specification()
    plan = (trial.ROOT / trial.PLAN).read_bytes()
    prior = tmp_path / "old/continuation"
    prior.mkdir(parents=True)
    ref.write_json(prior / "registration.json", parent)
    ref.write_json(prior / "failure.json", {"status": "unqualified"})
    audited = {"new_trajectory_audits": {}}
    for variant in ("radau", "bdf", "refined"):
        key = f"M_to_E/mirna_only/{variant}"
        (prior / key).mkdir(parents=True)
        ref.write_json(prior / key / "trajectory.json", {"fixture": True})
        audited["new_trajectory_audits"][key] = {}
    audited["aggregate_artifact_bytes"] = trial.previous.tree_bytes(prior.parent)
    monkeypatch.setattr(trial, "ROOT", tmp_path)
    monkeypatch.setattr(trial, "PRIOR", prior)
    monkeypatch.setattr(trial, "OUTPUT_PARENT", tmp_path / "new")
    monkeypatch.setattr(trial, "evidence", lambda: (copy.deepcopy(parent), copy.deepcopy(audited)))
    monkeypatch.setattr(trial, "SOURCES", ["fixture.txt"])
    (tmp_path / "fixture.txt").write_text("fixture source\n")
    (tmp_path / trial.PLAN).parent.mkdir(parents=True)
    (tmp_path / trial.PLAN).write_bytes(plan)
    for key, value in campaign.THREADS.items():
        monkeypatch.setenv(key, value)
    return trial.OUTPUT_PARENT / "attempt"


def test_registration_exclusive_roundtrip(fixture_campaign):
    r = trial.register(fixture_campaign)
    assert trial.check_registration(fixture_campaign) == r
    with pytest.raises(FileExistsError):
        trial.register(fixture_campaign)


@pytest.mark.parametrize(
    "field",
    [
        "methods",
        "case",
        "duration",
        "required_pairs",
        "storage_budget",
        "imports",
        "planned_attempts",
    ],
)
def test_registration_tamper_refused(fixture_campaign, field):
    r = trial.register(fixture_campaign)
    r[field] = "tampered"
    (fixture_campaign / "registration.json").write_text(json.dumps(r))
    with pytest.raises(ValueError, match="Refinement registration changed"):
        trial.check_registration(fixture_campaign)


def test_amendment_tamper_refused(fixture_campaign):
    with (trial.ROOT / trial.PLAN).open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError, match="Frozen input changed"):
        trial.specification(fixture_campaign)


def test_new_source_tamper_refused(fixture_campaign):
    trial.register(fixture_campaign)
    (trial.ROOT / "fixture.txt").write_text("changed")
    with pytest.raises(ValueError, match="source identity changed"):
        trial.check_registration(fixture_campaign)


def test_aggregate_quota_and_unregistered_sibling_refusals(fixture_campaign):
    used = trial.previous.tree_bytes(trial.PRIOR.parent)
    with pytest.raises(ref.BudgetExceeded, match="Aggregate"):
        trial.storage(fixture_campaign, used, used + paths.TAIL_RESERVE - 1)
    trial.OUTPUT_PARENT.mkdir()
    (trial.OUTPUT_PARENT / "unknown.txt").write_text("not a quota reset")
    with pytest.raises(ValueError, match="Unexpected"):
        trial.storage(fixture_campaign, used, 1073741824)


def test_missing_import_audit_cannot_be_used(monkeypatch, fixture_campaign):
    parent, audited = trial.evidence()
    audited["new_trajectory_audits"].pop("M_to_E/mirna_only/bdf")
    monkeypatch.setattr(trial, "evidence", lambda: (parent, audited))
    with pytest.raises(ValueError, match="Unaudited or incomplete"):
        trial.specification(fixture_campaign)


@pytest.mark.parametrize("timeout", [False, True])
def test_single_stopped_worker_retained_without_retry(monkeypatch, fixture_campaign, timeout):
    calls = []

    def stopped(command, **kwargs):
        calls.append(command)
        kwargs["stdout"].write("buffered fixture log retained\n")
        assert 0 < kwargs["timeout"] <= 900
        if timeout:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(trial.subprocess, "run", stopped)
    with pytest.raises(subprocess.TimeoutExpired if timeout else ValueError):
        trial.run(fixture_campaign)
    r, receipt, name = audit.check_integrity(fixture_campaign)
    assert len(calls) == 1 and name == "failure.json"
    assert receipt["status"] == ("incomplete" if timeout else "unqualified")
    assert not receipt["automatic_retry"] and not receipt["case_qualification_changed"]
    with pytest.raises(ValueError, match="Closed refinement"):
        trial.worker(fixture_campaign)
    with pytest.raises(FileExistsError):
        trial.run(fixture_campaign)
    assert len(calls) == 1 and r["planned_attempts"] == ["bdf_tight"]
    (fixture_campaign / "extra.txt").write_text("unexpected payload")
    with pytest.raises(ValueError, match="payload inventory"):
        audit.check_integrity(fixture_campaign)


def test_worker_uses_exact_fresh_anchor_and_only_tighter_tolerances(monkeypatch, fixture_campaign):
    r = trial.register(fixture_campaign)
    session = {
        "registration_sha256": ref.sha(fixture_campaign / "registration.json"),
        "attempt_id": f"{r['output_directory']}/bdf_tight",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "wall_budget_seconds": 3600,
    }
    ref.write_json(fixture_campaign / "session.json", session)
    calls = []

    def record(model, output, **kwargs):
        calls.append((model, output, kwargs))

    monkeypatch.setattr(paths, "integrate", record)
    trial.worker(fixture_campaign)
    model, output, options = calls[0]
    np.testing.assert_array_equal(model.anchor, r["case"]["primary"])
    np.testing.assert_array_equal(model.initial()[6 * model.n :], 0)
    assert output == fixture_campaign / "bdf_tight"
    assert options["method"] == "BDF" and options["refinement"] == 0.1
    assert options["numerics"] == r["numerics"] and options["duration"] == 1000
    session["started_utc"] = "2000-01-01T00:00:00+00:00"
    (fixture_campaign / "session.json").write_text(json.dumps(session))
    with pytest.raises(ref.BudgetExceeded, match="no longer live"):
        trial.worker(fixture_campaign)
    assert len(calls) == 1


@pytest.fixture
def short_paths(monkeypatch, tmp_path, real_spec):
    r = copy.deepcopy(real_spec)
    monkeypatch.setattr(trial, "ROOT", tmp_path)
    r.update(duration=0.03, observation_times=[0, 0.00113, 0.02, 0.03], output_directory="new")
    r["resources"]["window_steps"] = 2
    r["resources"]["artifact_budget_bytes"] = 20_000_000
    r["imports"] = {key: {"directory": f"old/{key}"} for key in ("radau", "bdf", "refined")}
    for variant, directory in trial.directories(r).items():
        method, refinement = r["methods"][variant]
        paths.integrate(
            campaign.graph.Model(r["case"]),
            directory,
            method=method,
            refinement=refinement,
            duration=r["duration"],
            numerics=r["numerics"],
            resources=r["resources"],
            artifact_root=tmp_path,
        )
    return tmp_path / "new", r


def test_four_root_comparison_and_independent_score_audit(short_paths):
    output, r = short_paths
    result = comparison.compare(trial.directories(r), r, output, perf_counter() + 30)
    assert result["status"] == "agreement_met" and len(result["scores"]) == 6
    assert "radau_vs_bdf" in result["scores"] and not result["original_BDF_failure_reclassified"]
    checked = audit.audit_comparison(output, r, perf_counter() + 30)
    model = campaign.graph.Model(r["case"])
    curve = audit.old_audit.audit_trajectory(
        output / "bdf_tight", model.case, r, model.panel, perf_counter() + 30
    )
    assert curve["maximum_accounting_residual"] <= r["numerics"]["accounting_atol"]
    assert (
        checked["samples"] == result["samples"]
        and checked["sampled_state_identity"] == "all_four_inputs_exact"
    )
    result["scores"]["radau_vs_bdf_tight"]["regulatory_state"] += 0.01
    (output / "comparison/comparison.json").write_text(json.dumps(result))
    with pytest.raises(ValueError, match="Independent refinement score differs"):
        audit.audit_comparison(output, r, perf_counter() + 30)


def test_reader_lifetimes_close_on_early_refusal(short_paths):
    _, r = short_paths
    held = []
    with pytest.raises(ValueError, match="deliberate"):
        with comparison.open_readers(trial.directories(r), r) as readers:
            held.extend(readers.values())
            for reader in held:
                reader.sample([0])
            raise ValueError("deliberate early exit")
    assert len(held) == 4 and all(reader._iterator.gi_frame is None for reader in held)


def test_wrong_import_method_refused(short_paths):
    _, r = short_paths
    r["methods"]["bdf"] = ["Radau", 1]
    with pytest.raises(ValueError, match="trajectory identity differs"):
        with comparison.open_readers(trial.directories(r), r):
            pytest.fail("Incorrect method was imported")


def test_tighter_bdf_numerical_path_bit_exact_against_original_recorder(tmp_path, real_spec):
    r = real_spec
    model = campaign.graph.Model(r["case"])
    options = dict(
        method="BDF",
        refinement=0.1,
        duration=0.03,
        numerics=r["numerics"],
        resources=r["resources"] | {"window_steps": 2},
        artifact_root=tmp_path,
    )
    old = ref.integrate(model, tmp_path / "old", **options)
    new = paths.integrate(model, tmp_path / "new", **options)
    assert (
        old["accepted_steps"] == new["accepted_steps"]
        and old["rhs_calls_including_solver_jacobian"] == new["rhs_calls_including_solver_jacobian"]
    )
    for a, b in zip(
        ref.Trajectory(tmp_path / "old").chunks(),
        ref.Trajectory(tmp_path / "new").chunks(),
        strict=True,
    ):
        for name in a:
            np.testing.assert_array_equal(a[name], b[name])


def test_new_work_is_reference_only():
    for module in (trial, comparison, audit):
        source = inspect.getsource(module)
        assert "from cells" not in source and "import cells" not in source
        assert "import bitsey" not in source
    assert "model.derivative" not in inspect.getsource(audit)


def test_failed_refinement_comparison_does_not_launch_another_attempt(
    monkeypatch, fixture_campaign
):
    calls = []

    def completed(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    def disagree(directories, registration, output, deadline):
        assert list(directories) == ["radau", "bdf", "refined", "bdf_tight"]
        assert registration["numerics"]["reference_agreement_fraction"] == 0.1
        (output / "comparison").mkdir()
        result = {"status": "agreement_not_met", "scope": "engineering_fixture"}
        ref.write_json(output / "comparison/comparison.json", result)
        return result

    monkeypatch.setattr(trial.subprocess, "run", completed)
    monkeypatch.setattr(comparison, "compare", disagree)
    with pytest.raises(ValueError, match="no additional refinement"):
        trial.run(fixture_campaign)
    _, stopped, _ = audit.check_integrity(fixture_campaign)
    assert len(calls) == 1 and stopped["status"] == "unqualified"
    assert "comparison/comparison.json" in stopped["payload_hashes"]
    assert not stopped["case_qualification_changed"]
