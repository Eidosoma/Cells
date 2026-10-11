"""D036 short engineering checks; no fixture runs a 1000-unit scientific path."""

import copy
import inspect
import json
import subprocess
from datetime import datetime, timezone
from time import perf_counter

import numpy as np
import pytest

from scripts import audit_graph_reference_panel as audit
from scripts import complete_graph_reference_panel as panel
from tests import reference_graph_panel as readers

ref, paths, campaign = panel.ref, panel.paths, panel.campaign


@pytest.fixture(scope="module")
def real_spec():
    return panel.specification(panel.OUTPUT_PARENT / "panel-01")


def test_explicit_accuracy_policy_exact_inputs_and_mixed_settings(real_spec):
    r = real_spec
    assert r["cases"] == campaign.cases()
    assert len(r["references"]) == 14 and len(r["original_qualified_cases"]) == 10
    assert r["new_cases"] == ["M_to_E/same_state", "M_to_E/one_neighbor", "M_to_E/isolated"]
    assert r["reference_order"] == ["radau", "refined", "bdf_tight"]
    assert r["methods"]["bdf_tight"] == ["BDF", 0.1]
    assert len(r["planned_attempts"]) == 9
    assert all(key.rsplit("/", 1)[0] in r["new_cases"] for key in r["planned_attempts"])
    for case in r["original_qualified_cases"]:
        assert r["references"][case]["methods"]["bdf"] == ["BDF", 1]
    adopted = r["references"][r["adopted_case"]]
    assert adopted["policy"] == "A1_adopted" and len(adopted["imported_receipt_hashes"]) == 4
    assert panel.directories(r, r["adopted_case"])["bdf_tight"] == panel.A1 / "bdf_tight"
    assert "bdf" not in adopted["trajectories"]
    assert not r["original_campaign_reclassified"] and not r["biological_outcome_is_numerical_gate"]
    assert r["duration"] == 1000 and len(r["observation_times"]) == 1007
    protocol = campaign.frozen.load_protocol()
    assert r["resources"] == protocol["resources"] and r["numerics"] == protocol["numerics"]
    assert r["storage_budget"]["prior_bytes"] == 582424320
    assert panel.execution(r)["resources"]["artifact_budget_bytes"] == 491317504


def test_a1_closeout_pin_tampering_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(panel, "ROOT", tmp_path)
    (tmp_path / "reports").mkdir()
    ref.write_json(tmp_path / panel.CLOSEOUT, {"status": "pass"})
    with pytest.raises(ValueError, match="Frozen input changed"):
        panel.evidence()


@pytest.fixture
def fixture_campaign(monkeypatch, tmp_path):
    base = campaign.specification()
    plan_bytes = (panel.ROOT / panel.PLAN).read_bytes()
    source_panel = (panel.ROOT / "configs/reference/source_emt_pair_panel_v1.json").read_bytes()
    plan = json.loads(plan_bytes)
    original = {
        case: f"old/{case}"
        for case in base["cases"]
        if case not in [plan["adopted_case"], *plan["remaining_cases"]]
    }
    proof = {
        "original": original,
        "adopted_paths": {key: f"old/adopted/{key}" for key in plan["reference_order"]},
        "adopted_comparison": "old/adopted/comparison/comparison.json",
    }
    for folder in original.values():
        for variant in campaign.METHODS:
            (tmp_path / folder / variant).mkdir(parents=True)
            ref.write_json(tmp_path / folder / variant / "trajectory.json", {"fixture": True})
        (tmp_path / folder / "comparison").mkdir()
        ref.write_json(
            tmp_path / folder / "comparison/comparison.json", {"status": "pass", "maximum_score": 0}
        )
        (tmp_path / folder / "observations").mkdir()
        ref.write_json(tmp_path / folder / "observations/summary.json", {"fixture": True})
    for folder in proof["adopted_paths"].values():
        (tmp_path / folder).mkdir(parents=True)
        ref.write_json(tmp_path / folder / "trajectory.json", {"fixture": True})
    (tmp_path / proof["adopted_comparison"]).parent.mkdir()
    ref.write_json(
        tmp_path / proof["adopted_comparison"],
        {"status": "agreement_met", "maximum_required_score": 0},
    )
    proof["prior_bytes"] = panel.previous.tree_bytes(tmp_path / "old")
    monkeypatch.setattr(panel, "ROOT", tmp_path)
    monkeypatch.setattr(panel, "OUTPUT_PARENT", tmp_path / "new")
    monkeypatch.setattr(panel, "PRIOR_PARENTS", [tmp_path / "old"])
    monkeypatch.setattr(panel, "evidence", lambda: (copy.deepcopy(base), copy.deepcopy(proof)))
    monkeypatch.setattr(
        panel, "SOURCES", ["fixture.txt", "configs/reference/source_emt_pair_panel_v1.json"]
    )
    (tmp_path / "fixture.txt").write_text("fixture source\n")
    (tmp_path / panel.PLAN).parent.mkdir(parents=True)
    (tmp_path / panel.PLAN).write_bytes(plan_bytes)
    (tmp_path / "configs/reference/source_emt_pair_panel_v1.json").write_bytes(source_panel)
    for key, value in campaign.THREADS.items():
        monkeypatch.setenv(key, value)
    return {"output": panel.OUTPUT_PARENT / "attempt", "base": base, "proof": proof}


def test_registration_roundtrip_and_exclusive_output(fixture_campaign):
    output = fixture_campaign["output"]
    r = panel.register(output)
    assert panel.check_registration(output) == r
    with pytest.raises(FileExistsError):
        panel.register(output)


@pytest.mark.parametrize(
    "field",
    [
        "methods",
        "references",
        "duration",
        "numerics",
        "resources",
        "planned_attempts",
        "adopted_case",
        "storage_budget",
    ],
)
def test_registration_tampering_refused(fixture_campaign, field):
    output = fixture_campaign["output"]
    r = panel.register(output)
    r[field] = "tampered"
    (output / "registration.json").write_text(json.dumps(r))
    with pytest.raises(ValueError, match="Panel registration"):
        panel.check_registration(output)


def test_source_and_amendment_tampering_refused(fixture_campaign):
    output = fixture_campaign["output"]
    panel.register(output)
    (panel.ROOT / "fixture.txt").write_text("changed")
    with pytest.raises(ValueError, match="source identity"):
        panel.check_registration(output)
    with (panel.ROOT / panel.PLAN).open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError, match="Frozen input changed"):
        panel.specification(output)


def test_aggregate_quota_unknown_siblings_and_links_refused(fixture_campaign):
    output, proof = fixture_campaign["output"], fixture_campaign["proof"]
    used = proof["prior_bytes"]
    with pytest.raises(ref.BudgetExceeded, match="Aggregate"):
        panel.storage(output, used, used + paths.TAIL_RESERVE - 1)
    panel.OUTPUT_PARENT.mkdir()
    unexpected = panel.OUTPUT_PARENT / "unknown.txt"
    unexpected.write_text("not a fresh quota")
    with pytest.raises(ValueError, match="Unexpected"):
        panel.storage(output, used, 1073741824)
    unexpected.rename(panel.ROOT / "preserved-unexpected.txt")
    output.symlink_to(panel.ROOT / "old", target_is_directory=True)
    with pytest.raises(ValueError, match="unlinked"):
        panel.storage(output, used, 1073741824)


def fake_observe(directories, output, case, registration, deadline):
    folder = output / case / "observations"
    folder.mkdir(parents=True)
    ref.write_json(folder / "summary.json", {"fixture": True})


@pytest.mark.parametrize("timeout", [False, True])
def test_worker_stop_retains_adoption_log_and_no_retry(monkeypatch, fixture_campaign, timeout):
    output = fixture_campaign["output"]
    calls = []
    monkeypatch.setattr(readers, "observe", fake_observe)

    def stop(command, **kwargs):
        calls.append(command)
        kwargs["stdout"].write("retained failure fixture\n")
        if timeout:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(panel.subprocess, "run", stop)
    with pytest.raises(subprocess.TimeoutExpired if timeout else ValueError):
        panel.run(output)
    r, receipt, name = audit.check_integrity(output)
    assert name == "failure.json" and len(calls) == 1
    assert receipt["status"] == ("incomplete" if timeout else "unqualified")
    assert receipt["new_observer_qualified_cases"] == [r["adopted_case"]]
    assert len(receipt["not_started"]) == 8 and receipt["no_automatic_retry"]
    with pytest.raises(ValueError, match="closed panel"):
        panel.worker(output, r["planned_attempts"][0])
    with pytest.raises(FileExistsError):
        panel.run(output)
    (output / "unexpected.txt").write_text("extra payload")
    with pytest.raises(ValueError, match="payload inventory"):
        audit.check_integrity(output)


def test_adopted_observer_failure_stops_before_any_integration(monkeypatch, fixture_campaign):
    def refuse(*args):
        raise ref.BudgetExceeded("observer fixture stop")

    monkeypatch.setattr(readers, "observe", refuse)
    monkeypatch.setattr(panel.subprocess, "run", lambda *a, **k: pytest.fail("must not launch"))
    with pytest.raises(ref.BudgetExceeded):
        panel.run(fixture_campaign["output"])
    _, receipt, _ = audit.check_integrity(fixture_campaign["output"])
    assert receipt["attempts"] == [] and receipt["new_observer_qualified_cases"] == []
    assert len(receipt["not_started"]) == 9


def test_worker_exact_anchor_tighter_bdf_order_and_expiry(monkeypatch, fixture_campaign):
    output = fixture_campaign["output"]
    r = panel.register(output)
    session = {
        "registration_sha256": ref.sha(output / "registration.json"),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "wall_budget_seconds": 3600,
        "automatic_retry": False,
    }
    ref.write_json(output / "session.json", session)
    with pytest.raises(ValueError, match="imports cannot be rerun"):
        panel.worker(output, f"{r['adopted_case']}/bdf_tight")
    entries = [
        {
            "key": key,
            "attempt_id": f"{r['output_directory']}/{key}",
            "initial_time": 0.0,
            "status": "started",
        }
        for key in r["planned_attempts"][:3]
    ]
    (output / "attempts.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
    calls = []
    monkeypatch.setattr(
        paths, "integrate", lambda model, path, **kw: calls.append((model, path, kw))
    )
    panel.worker(output, entries[-1]["key"])
    model, target, settings = calls[0]
    np.testing.assert_array_equal(model.anchor, r["cases"][r["new_cases"][0]]["primary"])
    np.testing.assert_array_equal(model.initial()[6 * model.n :], 0)
    assert target == output / entries[-1]["key"]
    assert settings["method"] == "BDF" and settings["refinement"] == 0.1
    assert settings["numerics"] == r["numerics"] and settings["duration"] == 1000
    with pytest.raises(ValueError, match="ordered registered start"):
        panel.worker(output, entries[0]["key"])
    session["started_utc"] = "2000-01-01T00:00:00+00:00"
    (output / "session.json").write_text(json.dumps(session))
    with pytest.raises(ref.BudgetExceeded, match="no longer live"):
        panel.worker(output, entries[-1]["key"])
    assert len(calls) == 1


@pytest.fixture
def short_paths(tmp_path):
    r = campaign.specification()
    r.update(duration=0.03, observation_times=[0, 0.00113, 0.02, 0.03])
    r["observer"]["terminal_window"] = [0.02, 0.03]
    r["resources"]["window_steps"] = 2
    case = "M_to_E/mirna_only"
    r["methods"]["bdf_tight"] = ["BDF", 0.1]
    for key, (method, refinement) in r["methods"].items():
        paths.integrate(
            campaign.graph.Model(r["cases"][case]),
            tmp_path / "old" / case / key,
            method=method,
            refinement=refinement,
            duration=0.03,
            numerics=r["numerics"],
            resources=r["resources"],
            artifact_root=tmp_path,
        )
    return tmp_path, case, r


def test_original_and_multiroot_observers_bit_exact(short_paths):
    root, case, r = short_paths
    original = root / "old"
    new = root / "new"
    (new / case).mkdir(parents=True)
    original_r = r | {
        "methods": {key: r["methods"][key] for key in campaign.METHODS},
        "reference_order": list(campaign.METHODS),
    }
    old = campaign.observe(original, case, original_r, perf_counter() + 30)
    selected = {key: original / case / key for key in campaign.METHODS}
    result = readers.observe(selected, new, case, original_r, perf_counter() + 30)
    assert result == old
    for index in range(result["chunks"]):
        name = f"{case}/observations/chunk-{index:06d}.npz"
        with (
            np.load(original / name, allow_pickle=False) as a,
            np.load(new / name, allow_pickle=False) as b,
        ):
            assert set(a.files) == set(b.files)
            for key in a.files:
                np.testing.assert_array_equal(a[key], b[key])


def test_selected_trio_samples_scores_and_observers_independent_audit(short_paths):
    root, case, r = short_paths
    order = ["radau", "refined", "bdf_tight"]
    r = r | {"methods": {key: r["methods"][key] for key in order}, "reference_order": order}
    selected = {key: root / "old" / case / key for key in order}
    output = root / "new"
    (output / case).mkdir(parents=True)
    comparison = readers.compare(selected, output, case, r, perf_counter() + 30)
    obs = readers.observe(selected, output, case, r, perf_counter() + 30)
    assert comparison["status"] == "pass" and len(comparison["scores"]) == 3
    assert not obs["recipient_terminal_target"] and obs["terminal_observations"] == 2
    checked = audit.sampled_identity(
        output / case / "comparison",
        selected,
        r | {"case": r["cases"][case]},
        perf_counter() + 30,
        comparison=True,
    )
    assert checked["samples"] == comparison["samples"] and checked["agreement"] == "pass"
    audit.sampled_identity(
        output / case / "observations",
        selected,
        r | {"case": r["cases"][case]},
        perf_counter() + 30,
        comparison=False,
    )
    audit.old.audit_observations(output / case, r["cases"][case], r)
    assert (
        audit.observer_events(output / case / "observations", case, r, perf_counter() + 30)["cells"]
        == 3
    )
    comparison["scores"]["radau_vs_bdf_tight"]["regulatory_state"] += 0.01
    (output / case / "comparison/comparison.json").write_text(json.dumps(comparison))
    with pytest.raises(ValueError, match="Independent panel score"):
        audit.sampled_identity(
            output / case / "comparison",
            selected,
            r | {"case": r["cases"][case]},
            perf_counter() + 30,
            comparison=True,
        )
    obs["cells"][0]["first_sampled_target_time"] = 0.02
    (output / case / "observations/summary.json").write_text(json.dumps(obs))
    with pytest.raises(ValueError, match="observer event summary"):
        audit.observer_events(output / case / "observations", case, r, perf_counter() + 30)


def test_multiroot_observer_closes_readers_on_refusal(monkeypatch, short_paths):
    root, case, r = short_paths
    r["reference_order"] = list(campaign.METHODS)
    selected = {key: root / "old" / case / key for key in campaign.METHODS}
    held = []

    def refuse(ts, *args):
        held.extend(ts.values())
        for reader in held:
            reader.sample([0])
        raise ValueError("fixture refusal")

    monkeypatch.setattr(readers, "_observe", refuse)
    with pytest.raises(ValueError, match="fixture refusal"):
        readers.observe(selected, root, case, r, perf_counter() + 30)
    assert all(reader._iterator.gi_frame is None for reader in held)
    with pytest.raises(ValueError, match="reference inventory"):
        readers.observe(dict(reversed(list(selected.items()))), root, case, r, perf_counter() + 30)


@pytest.mark.parametrize("corruption", ["time", "state"])
def test_rehashed_comparison_corruption_still_fails_identity(short_paths, corruption):
    root, case, r = short_paths
    r["reference_order"] = ["radau", "refined", "bdf_tight"]
    selected = {key: root / "old" / case / key for key in r["reference_order"]}
    output = root / "new"
    (output / case).mkdir(parents=True)
    summary = readers.compare(selected, output, case, r, perf_counter() + 30)
    folder = output / case / "comparison"
    chunk = folder / "chunk-000000.npz"
    with np.load(chunk, allow_pickle=False) as data:
        changed = {key: data[key].copy() for key in data.files}
    if corruption == "time":
        changed["times"][0] += 1e-10
    else:
        changed["bdf_tight"][0, 0] += 1e-10
    np.savez_compressed(chunk, **changed)
    entries = [json.loads(line) for line in (folder / "chunks.jsonl").read_text().splitlines()]
    entries[0]["sha256"] = ref.sha(chunk)
    entries[0]["start"] = float(changed["times"][0])
    (folder / "chunks.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
    summary["index_sha256"] = ref.sha(folder / "chunks.jsonl")
    (folder / "comparison.json").write_text(json.dumps(summary))
    with pytest.raises(AssertionError):
        audit.sampled_identity(
            folder,
            selected,
            r | {"case": r["cases"][case]},
            perf_counter() + 30,
            comparison=True,
        )


def test_complete_short_panel_orchestration_and_independent_audit(monkeypatch, fixture_campaign):
    output, base, proof = (fixture_campaign[k] for k in ("output", "base", "proof"))
    base.update(duration=0.03, observation_times=[0, 0.0113, 0.02, 0.03])
    base["observer"]["terminal_window"] = [0.02, 0.03]
    base["resources"]["window_steps"] = 2
    # Real short imported paths live separately; the earlier fixture stubs stay preserved.
    for key, (method, refinement) in json.loads((panel.ROOT / panel.PLAN).read_text())[
        "methods"
    ].items():
        folder = panel.ROOT / f"old/short-adopted/{key}"
        paths.integrate(
            campaign.graph.Model(base["cases"]["M_to_E/mirna_only"]),
            folder,
            method=method,
            refinement=refinement,
            duration=0.03,
            numerics=base["numerics"],
            resources=base["resources"],
            artifact_root=panel.ROOT,
        )
        proof["adopted_paths"][key] = str(folder.relative_to(panel.ROOT))
    proof["prior_bytes"] = panel.previous.tree_bytes(panel.ROOT / "old")
    calls = []

    def local_worker(command, **kwargs):
        calls.append(command[-1])
        panel.worker(output, command[-1])
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(panel.subprocess, "run", local_worker)
    receipt = panel.run(output)
    checked = audit.verify(output)
    assert len(calls) == 9 and receipt["qualified_conditions"] == 14
    assert checked["NUM005c1_complete_under_A2"] and checked["amended_qualified_conditions"] == 14
    assert len(checked["new_trajectory_audits"]) == 9 and len(checked["new_observer_audits"]) == 4
    assert not receipt["original_campaign_reclassified"] and not receipt["production_changed"]
    assert not receipt["cases"]["M_to_E/isolated"]["observations"]["recipient_terminal_target"]


def test_failed_comparison_stops_after_one_trio_without_next_control(monkeypatch, fixture_campaign):
    output = fixture_campaign["output"]
    calls = []
    monkeypatch.setattr(readers, "observe", fake_observe)

    def complete(command, **kwargs):
        key = command[-1]
        calls.append(key)
        (output / key).mkdir(parents=True)
        ref.write_json(
            output / key / "trajectory.json", {"status": "complete_not_yet_cross_qualified"}
        )
        return subprocess.CompletedProcess(command, 0)

    def disagree(directories, output, case, registration, deadline):
        (output / case / "comparison").mkdir()
        result = {"status": "unqualified", "maximum_score": 0.2}
        ref.write_json(output / case / "comparison/comparison.json", result)
        return result

    monkeypatch.setattr(panel.subprocess, "run", complete)
    monkeypatch.setattr(readers, "compare", disagree)
    with pytest.raises(ValueError, match="no automatic amendment"):
        panel.run(output)
    _, receipt, _ = audit.check_integrity(output)
    assert len(calls) == 3 and len(receipt["not_started"]) == 6
    assert receipt["new_observer_qualified_cases"] == ["M_to_E/mirna_only"]
    assert any("comparison/comparison.json" in path for path in receipt["payload_hashes"])


def test_reference_only_no_global_method_override_or_auditor_rhs():
    for module in (panel, readers, audit):
        source = inspect.getsource(module)
        assert "from cells" not in source and "import cells" not in source
        assert "import bitsey" not in source and "campaign.METHODS =" not in source
    assert "model.derivative" not in inspect.getsource(audit)
