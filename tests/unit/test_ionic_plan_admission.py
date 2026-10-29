"""Planning reuse preserves complete tasks, admission, bounds and identities."""

from copy import deepcopy

import pytest

from cells.core.specs import parse_spec as parse_simulation
from cells.ensemble import plan as planner
from cells.ensemble.families import output_bound, parse_definition
from cells.ensemble.ionic import validate_population
from tests.unit.test_integrated_ensemble import experiment
from tests.unit.test_surface_catalog import evidence


def inputs(*, width=3, worlds=8):
    raw = experiment("ionic", worlds=worlds, width=width)
    second = deepcopy(raw["arms"][0])
    second["id"] = "second"
    rows = second["definition"]["simulation"]["experiment"]["membrane_controls"]
    rows[0]["leak"][0]["multipliers"]["Na"] = 0.75
    raw["arms"].append(second)
    raw["execution"]["max_output_bytes"] = 4 * 1024**3
    return raw


@pytest.mark.parametrize("width", (1, 3, 8))
def test_each_task_matches_fresh_admission_with_exact_output_bound_and_independent_data(
    width, monkeypatch
):
    raw = inputs(width=width)
    original = deepcopy(raw)
    calls, parse = [], planner.parse_spec

    def recorded(value):
        calls.append(deepcopy(value))
        return parse(value)

    monkeypatch.setattr(planner, "parse_spec", recorded)
    result = planner.plan(raw, 1)
    sizes = {min(width, 8 - start) for start in range(0, 8, width)}
    assert len(calls) == 2 * len(sizes)
    assert raw == original
    expected = {
        arm["id"]: parse_simulation(arm["definition"]["simulation"]).to_dict()
        for arm in raw["arms"]
    }
    ids, bound = [], 32 * 1024**2
    for task in result["tasks"]:
        # Full admission remains the independent comparator and worker path.
        spec = parse_definition(task["definition"])
        assert spec.to_dict() == task["definition"]
        assert spec.simulation.to_dict() == expected[task["arm"]]
        assert spec.seed == raw["seed"]
        ids.extend(range(spec.world_id_start, spec.world_id_start + spec.worlds))
        bound += 2 * output_bound(spec)
    assert sorted(ids) == list(range(16))
    assert bound == result["output_bytes_bound"]
    assert result["worlds"] == 16
    assert result["counts_changed_by_scheduling"] is False
    evidence(
        "ionic-planning-admission-" + str(width),
        dict(
            inputs=raw,
            plan=result,
            full_admissions_during_plan=len(calls),
            distinct_arm_batch_sizes=2 * len(sizes),
            task_admissions_match=True,
            complete_output_bound_bytes=bound,
            world_ids=ids,
            scope="Offline planner/software equivalence; no runtime or biological case",
        ),
    )
    before_others = [deepcopy(task["definition"]) for task in result["tasks"][1:]]
    result["tasks"][0]["definition"]["simulation"]["execution"]["dt"] = -1
    assert [task["definition"] for task in result["tasks"][1:]] == before_others
    assert raw == original


def test_plan_revalidates_each_new_call_and_cannot_accept_changed_physics(monkeypatch):
    raw = inputs(width=8)
    first = planner.plan(raw, 1)
    raw["seed"] += 1
    second = planner.plan(raw, 1)
    assert [t["definition"]["seed"] for t in second["tasks"]] == [raw["seed"]] * 2
    assert [t["definition"]["seed"] for t in first["tasks"]] == [raw["seed"] - 1] * 2
    raw["arms"][1]["definition"]["simulation"]["execution"]["dt"] = -1
    with pytest.raises(ValueError):
        planner.plan(raw, 1)


def test_total_output_refusal_keeps_computed_and_declared_byte_limits():
    raw = inputs(width=8)
    bound = planner.plan(raw, 1)["output_bytes_bound"]
    raw["execution"]["max_output_bytes"] = bound - 1
    with pytest.raises(ValueError, match=rf"{bound} bytes.*{bound - 1} bytes"):
        planner.plan(raw, 1)


def test_whole_arm_id_overflow_refuses_before_any_physical_admission(monkeypatch):
    raw = inputs(width=1, worlds=2**31)

    def forbidden(_):
        raise AssertionError("Namespace admission must precede physical work")

    monkeypatch.setattr(planner, "parse_spec", forbidden)
    with pytest.raises(ValueError, match="namespace"):
        planner.plan(raw, 1)


@pytest.mark.parametrize(
    "worlds,start,seed",
    (
        (True, 0, 0),
        (0, 0, 0),
        (4097, 0, 0),
        (1, True, 0),
        (1, -1, 0),
        (1, 2**31 - 1, 0),
        (2, 2**31 - 2, 0),
        (1, 0, True),
        (1, 0, -1),
        (1, 0, 2**32),
    ),
)
def test_scheduler_owned_fields_retain_strict_integer_and_namespace_limits(worlds, start, seed):
    with pytest.raises(ValueError):
        validate_population(worlds, start, seed)


def test_highest_valid_positive_world_and_seed_are_preserved():
    validate_population(1, 2**31 - 2, 2**32 - 1)
