"""Check local-channel inputs against the completed sham's physical recipe."""

import copy
import json
from collections import Counter

import numpy as np
import pytest

from cells.core.specs import parse_spec
from validation.assays import local_channel_design as design

PLAN = design.plan()
BASE = json.loads((design.source.two_task.ROOT / design.SOURCE["template"]).read_text())


def test_grid_budgets_and_flank_topology():
    work = PLAN["work"]
    ids = {r["world_id"] for r in design.SOURCE_ROWS}
    for condition in design.CONDITIONS:
        rows = design.cases(PLAN, condition["id"])
        assert len(rows) == 60
        assert {r["split"] for r in rows} == {"calibration"}
        assert {r["amplitude"] for r in rows} == {0.4, 0.6, 0.8}
        assert Counter(r["arm"] for r in rows) == dict.fromkeys(PLAN["fixed_assay"]["arms"], 12)
        current = {r["world_id"] for r in rows}
        assert len(current) == 60 and current.isdisjoint(ids)
        ids.update(current)
    steps = sum(round(512e-6 / dt) for dt in design.SOURCE["dt_s"])
    assert 5 * 60 * 3 == work["worlds_per_backend"] == 900
    assert 5 * 60 * steps == work["world_steps_per_backend"] == 4300800
    assert work["world_steps_per_backend"] / 5 == work["world_steps_per_arm_per_backend"]
    tissue = BASE["model"]["tissue"]
    owner = np.asarray(tissue["cell_owner"]) + 1
    edges = {
        tuple(sorted((owner[i], owner[j])))
        for i, j in enumerate(tissue["partner"])
        if i != j and tissue["junction_open"][i]
    }
    assert {b if a == 1 else a for a, b in edges if 1 in (a, b)} == {2, 6, 7}
    assert {b if a == 4 else a for a, b in edges if 4 in (a, b)} == {3, 5, 7}


@pytest.mark.parametrize(
    "name,owners,scale",
    [
        ("sham", [], 1.0),
        ("source1_flank_lower", [1, 5], 0.9),
        ("source1_flank_higher", [1, 5], 1.1),
        ("source4_flank_lower", [2, 4], 0.9),
        ("source4_flank_higher", [2, 4], 1.1),
    ],
)
@pytest.mark.parametrize("level", [0, 1, 2])
@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_only_selected_flank_changes(name, owners, scale, level, backend):
    before_base = copy.deepcopy(BASE)
    for row in design.cases(PLAN, name):
        before = design.source.definition(
            BASE, design.predecessor(row), level, backend, design.SHAM
        )
        actual = design.definition(BASE, row, level, backend, PLAN, name)
        owner = np.asarray(before["model"]["tissue"]["cell_owner"])
        expected = np.asarray(before["model"]["channel_permeability"]).copy()
        mask = np.isin(owner, owners)
        expected[mask] *= scale
        np.testing.assert_array_equal(actual["model"]["channel_permeability"], expected)
        np.testing.assert_array_equal(
            np.asarray(actual["model"]["channel_permeability"])[~mask],
            np.asarray(before["model"]["channel_permeability"])[~mask],
        )
        np.testing.assert_array_equal(
            actual["model"]["tissue"]["junction_permeability"],
            np.asarray(BASE["model"]["tissue"]["junction_permeability"]) * 0.9,
        )
        parse_spec(actual)
        actual["model"]["channel_permeability"] = before["model"]["channel_permeability"]
        assert actual == before
    assert BASE == before_base


def test_rejects_unregistered_cases_and_changed_support():
    row = design.cases(PLAN, "sham")[0]
    with pytest.raises(ValueError, match="calibration"):
        design.definition(BASE, row | dict(split="heldout"), 0, "cpu", PLAN, "sham")
    with pytest.raises(ValueError, match="condition"):
        design.cases(PLAN, "central")
    for key, value in (
        ("reader_margin_V", 1e-9),
        ("junction_permeability_scale", 1.0),
        ("primary_times_us", [128, 160, 512]),
        ("central_cell_id", 3),
        ("calibration_strengths", [0.4, 0.403125, 0.8]),
    ):
        changed = copy.deepcopy(PLAN)
        changed["fixed_assay"][key] = value
        with pytest.raises(ValueError, match="frozen"):
            design.validate_plan(changed)
    changed = copy.deepcopy(PLAN)
    changed["conditions"][1]["cell_ids"] = [1, 2, 6]
    with pytest.raises(ValueError, match="Unregistered"):
        design.validate_plan(changed)


def test_completed_source_and_diagnosis_bindings():
    assert design.authenticate_bindings(PLAN)["completed_records_bound"]
    changed = copy.deepcopy(PLAN)
    changed["diagnostic_binding"]["completion_sha256"] = "0" * 64
    with pytest.raises(AssertionError):
        design.authenticate_bindings(changed)
