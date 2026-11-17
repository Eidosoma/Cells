"""D035 short engineering checks; no test runs a 1000-unit refinement."""

import copy
import inspect

import pytest

from scripts import audit_graph_refinement as audit
from scripts import refine_graph_reference as trial
from tests import reference_graph_comparison as comparison

ref, paths, campaign = trial.ref, trial.paths, trial.campaign


@pytest.fixture(scope="module")
def real_spec():
    return trial.specification(trial.OUTPUT_PARENT / "bdf-tight-01")


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


def test_new_work_is_reference_only():
    for module in (trial, comparison, audit):
        source = inspect.getsource(module)
        assert "from cells" not in source and "import cells" not in source
        assert "import bitsey" not in source
    assert "model.derivative" not in inspect.getsource(audit)
