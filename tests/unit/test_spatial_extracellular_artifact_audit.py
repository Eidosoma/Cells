"""Adversarial replay preflights on a separate 2 ms fixture, not the panel."""

import copy
import json
import subprocess
import sys
import tomllib

import pytest

from scripts import audit_spatial_extracellular_reference as audit
from scripts import qualify_spatial_extracellular_reference as runner
from scripts import spatial_extracellular_artifacts as evidence
from tests import reference_spatial_extracellular_dynamics as ref
from tests import spatial_extracellular_numerical_checks as checks
from tests import spatial_extracellular_numerical_data as data
from tests.unit.test_spatial_extracellular_dynamics import PLAN, short_case


@pytest.fixture(scope="module")
def short_records():
    case, plan = short_case(), copy.deepcopy(PLAN)
    plan["candidate"]["steps_s"] = [0.0004, 0.0002]
    records, stats = {}, {}
    for setting in evidence.attempts(plan):
        name = setting["id"]
        if setting["method"] == "RK4":
            arrays, info = ref.integrate_candidate(case, setting["dt_s"])
        else:
            arrays, info = ref.integrate_reference(case, setting)
        info["id"] = name
        records[name], stats[name] = arrays, info
    analysis = checks.analyze_case(case, records, stats, plan)
    assert analysis["references_pass"]
    assert all(result["pass"] for result in analysis["comparisons"].values())
    return case, plan, records, stats, analysis


def save_short(root, short_records, *, mutate=None):
    case, plan, records, stats, analysis = short_records
    records, stats, analysis = copy.deepcopy((records, stats, analysis))
    if mutate:
        mutate(case, records, stats, analysis)
    output = evidence.Artifacts(root, 16 * 1048576)
    output.json(f"cases/{case.id}/definition.json", case.definition())
    for setting in evidence.attempts(plan):
        runner.save_record(output, case, setting, records[setting["id"]], stats[setting["id"]])
    output.json(f"cases/{case.id}/analysis.json", analysis)
    return output


def seal_storage(output):
    capsule, hashes = evidence.sources()
    output.write("sources.zip", capsule)
    receipt = {
        "files_sha256": dict(output.hashes),
        "source_sha256": hashes,
        "resources": {"artifact_bytes": output.limit},
        "artifact_bytes_before_receipt": output.used,
    }
    output.json("verification.json", receipt, closing=True)
    return receipt


def test_short_case_replays_read_only_without_integration(tmp_path, short_records, monkeypatch):
    root = tmp_path / "short"
    output = save_short(root, short_records)
    receipt = seal_storage(output)
    before = {
        p: (p.stat().st_mtime_ns, evidence.file_sha(p)) for p in root.rglob("*") if p.is_file()
    }

    def forbidden(*args, **kwargs):
        raise AssertionError("The auditor must not integrate")

    monkeypatch.setattr(ref, "integrate_reference", forbidden)
    monkeypatch.setattr(ref, "integrate_candidate", forbidden)
    evidence.authenticate(root, receipt)
    actual, _, _ = audit.audit_case(root, short_records[0], short_records[1])
    assert actual == short_records[4]
    after = {
        p: (p.stat().st_mtime_ns, evidence.file_sha(p)) for p in root.rglob("*") if p.is_file()
    }
    assert before == after


@pytest.mark.parametrize(
    "mutation",
    [
        "native",
        "sample",
        "dense",
        "degree",
        "amount_only",
        "history",
        "dissipation",
        "shift",
        "settings",
        "stage_count",
        "jacobian_count",
        "verdict",
        "initial_state",
    ],
)
def test_rehashed_corruption_is_not_a_new_verdict(tmp_path, short_records, mutation):
    def change(case, records, stats, analysis):
        name = "rk4_0.0004"
        record, info = records[name], stats[name]
        if mutation == "native":
            record["native_state"][-1, 0] += 1e-5
        elif mutation == "sample":
            record["sample_state"][1, 0] += 1e-5
        elif mutation == "dense":
            record["coefficients"][0, 0, 2] += 1e-5
        elif mutation == "degree":
            record["degree"][0] = 2
        elif mutation == "amount_only":
            record["native_state"] = record["native_state"][:, : case.layout.amount_count]
        elif mutation in {"history", "dissipation"}:
            field = "face_transfer" if mutation == "history" else "face_dissipation"
            record["native_state"][-1, case.layout.slices[field].start] += 1e-3
        elif mutation == "shift":
            records["bdf"]["shift"][0, 0] += 1e-3
        elif mutation == "settings":
            info["dt_s"] *= 2
        elif mutation == "stage_count":
            info["rhs_calls"] += 1
        elif mutation == "jacobian_count":
            stats["radau"]["jacobian_rhs_calls"] -= 1
        elif mutation == "verdict":
            analysis["comparisons"][name]["pass"] = False
        else:
            record["native_state"][0, 0] = 1e-5

    root = tmp_path / mutation
    output = save_short(root, short_records, mutate=change)
    receipt = seal_storage(output)
    # Even self-consistent new payload hashes are insufficient.
    evidence.authenticate(root, receipt)
    with pytest.raises(ValueError):
        audit.audit_case(root, short_records[0], short_records[1])


@pytest.mark.parametrize("mutation", ["payload", "extra", "symlink", "source", "byte_count"])
def test_storage_authentication_rejects_changed_evidence(tmp_path, mutation):
    root = tmp_path / "evidence"
    output = evidence.Artifacts(root, 16 * 1048576)
    output.json("probe.json", {"registered": True})
    receipt = seal_storage(output)
    if mutation == "payload":
        (root / "probe.json").write_text("{}")
    elif mutation == "extra":
        (root / "extra").write_text("undeclared")
    elif mutation == "symlink":
        (root / "alias").symlink_to(root / "probe.json")
    elif mutation == "source":
        receipt["source_sha256"][evidence.SOURCE_FILES[0]] = "0" * 64
    else:
        receipt["artifact_bytes_before_receipt"] += 1
    with pytest.raises(ValueError):
        evidence.authenticate(root, receipt)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../escape", "a//b", "a\\b", ""])
def test_append_only_paths_and_overwrites_are_refused(tmp_path, name):
    output = evidence.Artifacts(tmp_path / "bounded", 2 * 1048576)
    with pytest.raises(ValueError, match="path"):
        output.write(name, b"payload")
    output.write("one", b"original")
    with pytest.raises(FileExistsError):
        output.write("one", b"replacement")
    with pytest.raises(FileExistsError):
        evidence.Artifacts(output.path, 2 * 1048576)
    assert (output.path / "one").read_bytes() == b"original"


def test_artifact_cap_preserves_closing_reserve(tmp_path):
    output = evidence.Artifacts(tmp_path / "bounded", 2 * 1048576)
    with pytest.raises(RuntimeError, match="budget"):
        output.write("too_large", b"x" * (1048576 + 1))
    assert not (output.path / "too_large").exists() and output.used == 0
    output.write("payload", b"x" * 1048576)
    output.json("failure.json", {"status": "stopped"}, closing=True)
    assert output.used <= output.limit


@pytest.mark.parametrize("mutation", ["none", "reason", "control", "state", "stage_count"])
def test_actual_rejected_trial_replays_or_refuses_mutation(mutation):
    raw = short_case(controls=False).definition()
    raw["horizon_s"] = 0.02
    raw["world"]["faces"][0]["area_m2"] *= 1000
    case = data.resolve(raw)
    arrays, stats = ref.integrate_candidate(case, 0.01)
    assert stats["status"] == "rejected"
    if mutation == "none":
        audit.audit_rejection(case, arrays, stats)
        return
    if mutation == "reason":
        stats["rejected_trial"]["reason"] = "invented"
    elif mutation == "control":
        stats["rejected_trial"]["availability"] = [0]
    elif mutation == "state":
        stats["rejected_trial"]["state"] = list(data.initial_state(case))
    else:
        stats["rejected_rhs_calls"] = 0
    with pytest.raises(ValueError):
        audit.audit_rejection(case, arrays, stats)


def test_candidate_resource_failure_keeps_only_actual_prefix():
    case, budget = short_case(), ref.Budget(max_calls=7)
    with pytest.raises(ref.ResourceLimit) as error:
        ref.integrate_candidate(case, 0.0004, budget=budget)
    arrays, stats = ref.stopped_candidate(case, 0.0004, budget, error.value)
    assert stats["rhs_calls"] == 7 and stats["accepted_steps"] == 1
    assert arrays["native_times_s"].tolist() == [0.0, 0.0004]
    assert arrays["coefficients"].shape[0] == 1
    assert arrays["sample_times_s"].size == 0
    assert stats["status"] == "stopped"


def test_registered_driver_stops_and_retains_reference_failure(tmp_path, monkeypatch):
    # Exercise the orchestrator on a separate fixture with a deliberately tiny
    # resource budget. It cannot become a complete scientific-panel receipt.
    case, plan = short_case(), copy.deepcopy(PLAN)
    plan["resources"]["max_rhs_calls_per_attempt"] = 2
    monkeypatch.setattr(data, "load_panel", lambda: (plan, (case,)))
    monkeypatch.setattr(evidence, "validate_runtime", lambda saved: None)
    root = tmp_path / "stopped_preflight"
    assert runner.qualify(root) is False
    failure = json.loads((root / "failure.json").read_text())
    assert failure["status"] == "stopped_not_qualified"
    assert failure["phase"] == f"main/{case.id}/radau"
    assert failure["prefix"]["saved"] is True
    assert failure["prefix"]["omission"] is None
    assert not (root / "verification.json").exists()
    arrays, info = evidence.load_record(root, case.id, "radau")
    assert arrays["native_times_s"].tolist() == [0.0]
    assert info["status"] == "stopped" and info["rhs_calls"] == 2
    assert arrays["sample_state"].shape == (0, case.size)
    for name, digest in failure["files_sha256"].items():
        assert evidence.file_sha(root / name) == digest
    with pytest.raises(FileExistsError):
        runner.qualify(root)


@pytest.mark.parametrize("mutation", ["none", "amount_only", "nonzero_history", "clock"])
def test_saved_complete_restart_contract(tmp_path, short_records, mutation):
    case, _, records, _, _ = short_records
    original = records["rk4_0.0004"]
    midpoint = len(original["native_times_s"]) // 2
    start = float(original["native_times_s"][midpoint])
    initial = original["native_state"][midpoint].copy()
    if mutation == "amount_only":
        initial = initial[: case.layout.amount_count]
        with pytest.raises(ValueError):
            ref.integrate_candidate(case, 0.0004, start=start, initial=initial)
        return
    if mutation == "nonzero_history":
        initial[case.layout.slices["face_transfer"]] = 0
    if mutation == "clock":
        start += 1e-7
    resumed, stats = ref.integrate_candidate(case, 0.0004, start=start, initial=initial)
    if mutation == "none":
        assert audit.restart_check(case, original, resumed, stats, midpoint)["pass"]
    else:
        with pytest.raises(ValueError):
            audit.restart_check(case, original, resumed, stats, midpoint)


def test_fresh_auditor_imports_neither_integrators_nor_production():
    command = (
        "import sys; import scripts.audit_spatial_extracellular_reference; "
        "print(any(k == 'scipy' or k.startswith('scipy.') or k == 'cells' or "
        "k.startswith('cells.') or k == 'jax' or k.startswith('jax.') for k in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", command],
        cwd=evidence.ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"


@pytest.mark.parametrize("key", ["python", "numpy", "scipy", "threads", "cpu_affinity"])
def test_runtime_refuses_unregistered_settings(key):
    current = evidence.runtime()
    current["cpu_affinity"] = [4]
    current["threads"] = dict.fromkeys(evidence.THREAD_VARIABLES, "1")
    current[key] = [] if key == "cpu_affinity" else {} if key == "threads" else "unregistered"
    with pytest.raises(ValueError, match="runtime"):
        evidence.validate_runtime(current)


def test_source_capsule_has_every_executable_dependency():
    _, hashes = evidence.sources()
    assert len(hashes) == len(evidence.SOURCE_FILES) == 21
    assert all(evidence.file_sha(evidence.ROOT / path) == digest for path, digest in hashes.items())
    assert not any(p.startswith("src/") for p in hashes)
    assert (
        tomllib.loads((evidence.ROOT / "pyproject.toml").read_text())["project"]["version"]
        == "0.14.0"
    )
