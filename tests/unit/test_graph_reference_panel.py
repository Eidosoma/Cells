"""D036 short engineering checks; no fixture runs a 1000-unit scientific path."""

import copy
import inspect
import json

import pytest

from scripts import audit_graph_reference_panel as audit
from scripts import complete_graph_reference_panel as panel
from tests import reference_graph_panel as readers

ref, paths, campaign = panel.ref, panel.paths, panel.campaign


@pytest.fixture(scope="module")
def real_spec():
    return panel.specification(panel.OUTPUT_PARENT / "panel-01")


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


def fake_observe(directories, output, case, registration, deadline):
    folder = output / case / "observations"
    folder.mkdir(parents=True)
    ref.write_json(folder / "summary.json", {"fixture": True})


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


def test_reference_only_no_global_method_override_or_auditor_rhs():
    for module in (panel, readers, audit):
        source = inspect.getsource(module)
        assert "from cells" not in source and "import cells" not in source
        assert "import bitsey" not in source and "campaign.METHODS =" not in source
    assert "model.derivative" not in inspect.getsource(audit)
