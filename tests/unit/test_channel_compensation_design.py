"""Input isolation for the proposed channel-compensation calibration pilot."""

import copy
import json
from collections import Counter

import numpy as np
import pytest

from cells.core.specs import parse_spec
from validation.assays import channel_compensation_design as design
from validation.assays import source_order_coupling_transfer as coupling
from validation.assays import two_task

PLAN = design.plan()
SOURCE = coupling.condition_rule(coupling.protocol(), "lower")
SOURCE_ROWS = coupling.cases(SOURCE)
BASE = json.loads((two_task.ROOT / SOURCE["template"]).read_text())


def source_row(row):
    identity = {k: v for k, v in row.items() if k != "world_id"}
    return next(
        r for r in SOURCE_ROWS if {k: v for k, v in r.items() if k != "world_id"} == identity
    )


def test_calibration_only_and_equal_arm_work():
    identities = set(r["world_id"] for r in SOURCE_ROWS)
    work = PLAN["work"]
    steps = sum(round(PLAN["calibration"]["duration_s"] / dt) for dt in SOURCE["dt_s"])
    for condition in PLAN["conditions"]:
        rows = design.cases(PLAN, condition["id"])
        assert len(rows) == 60
        assert Counter(r["arm"] for r in rows) == dict.fromkeys(PLAN["calibration"]["arms"], 12)
        assert {r["split"] for r in rows} == {"calibration"}
        assert {r["amplitude"] for r in rows} == {0.4, 0.6, 0.8}
        current = {r["world_id"] for r in rows}
        assert len(current) == 60 and current.isdisjoint(identities)
        identities.update(current)
        assert len(rows) * steps == work["world_steps_per_condition_per_backend"]
    assert 3 * 60 * 3 == work["worlds_per_backend"] == 540
    assert 3 * 60 * steps == work["world_steps_per_backend"] == 2580480
    assert work["world_steps_per_backend"] / 5 == work["world_steps_per_arm_per_backend"]


@pytest.mark.parametrize(
    "name,scale", [("sham", 1.0), ("channel_lower", 0.9), ("channel_higher", 1.1)]
)
@pytest.mark.parametrize("level", [0, 1, 2])
@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_only_remote_channels_change_at_fixed_impairment(name, scale, level, backend):
    original = copy.deepcopy(BASE)
    for row in design.cases(PLAN, name):
        old = source_row(row)
        before = coupling.definition(BASE, old, level, backend, SOURCE)
        actual = design.definition(BASE, row, level, backend, PLAN, name)
        # Independent ownership expectation: cue sources are cells 1 and 4.
        owner = np.array(before["model"]["tissue"]["cell_owner"])
        source = (owner == 0) | (owner == 3)
        expected = np.array(before["model"]["channel_permeability"])
        expected[~source] *= scale
        np.testing.assert_array_equal(actual["model"]["channel_permeability"], expected)
        np.testing.assert_array_equal(
            np.array(actual["model"]["channel_permeability"])[source],
            np.array(BASE["model"]["channel_permeability"])[source],
        )
        np.testing.assert_array_equal(
            actual["model"]["tissue"]["junction_permeability"],
            np.array(BASE["model"]["tissue"]["junction_permeability"]) * 0.9,
        )
        parse_spec(actual)
        restored = copy.deepcopy(actual)
        restored["model"]["channel_permeability"] = before["model"]["channel_permeability"]
        # Includes initial state, cue controls, all observations and the timestep.
        assert restored == before
        if name == "sham":
            assert actual == before
    assert BASE == original


def test_rejects_heldout_cases_and_unregistered_interventions():
    row = design.cases(PLAN, "sham")[0]
    with pytest.raises(ValueError, match="calibration"):
        design.definition(BASE, row | dict(split="heldout"), 0, "cpu", PLAN, "sham")
    with pytest.raises(ValueError, match="condition"):
        design.cases(PLAN, "channel_adaptive")
    changes = [
        ("impairment", "scale", 1.0),
        ("alternative_control", "cell_ids", [1, 2, 3, 4, 5, 6, 7]),
        ("alternative_control", "scales", [0.5, 1.0, 1.5]),
        ("calibration", "strengths", [0.4, 0.403125, 0.8]),
        ("calibration", "reader_margin_V", 1e-9),
        ("calibration", "primary_times_us", [128, 160, 512]),
    ]
    for section, key, value in changes:
        changed = copy.deepcopy(PLAN)
        changed[section][key] = value
        with pytest.raises(ValueError, match="frozen"):
            design.definition(BASE, row, 0, "cpu", changed, "sham")


def test_rejects_unbound_source_and_candidate_changes():
    for key, value in (
        ("source_protocol_sha256", "0" * 64),
        ("conditions", PLAN["conditions"][:-1]),
        ("automatic_followup", True),
    ):
        changed = copy.deepcopy(PLAN)
        changed[key] = value
        with pytest.raises(ValueError, match="Unregistered"):
            design.validate_plan(changed)
