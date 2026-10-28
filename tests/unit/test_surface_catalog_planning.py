"""Offline expanded-catalog routing; no device or distributed execution claim."""

from copy import deepcopy

from cells.ensemble.families import parse_definition, population
from cells.ensemble.plan import jupiter_plan, plan
from tests.unit.test_integrated_ensemble import experiment
from tests.unit.test_surface_catalog import evidence
from validation.tissue import surface_catalog_fixtures as fixtures


def test_expanded_catalog_keeps_worlds_on_one_four_and_sixteen_gpu_plans():
    raw = experiment("ionic", backend="gpu", worlds=8, width=1)
    raw["arms"][0]["id"] = "open"
    raw["arms"][0]["definition"]["simulation"] = fixtures.definition(backend="gpu")
    second = deepcopy(raw["arms"][0])
    second["id"] = "blocked"
    second["definition"]["simulation"] = fixtures.definition("blocked", backend="gpu")
    raw["arms"].append(second)
    raw["execution"]["max_output_bytes"] = 4 * 1024**3
    original = deepcopy(raw)
    baseline = plan(raw, 1)
    plans = {str(count): plan(raw, count) for count in (4, 16)}
    plans["jupiter-four-nodes"] = jupiter_plan(raw, 4)
    for actual in plans.values():
        assert actual["tasks"] == baseline["tasks"]
    remote = plans["jupiter-four-nodes"]["deployment"]
    assert remote["maximum_target_gpus"] == 16 and len(remote["ranks"]) == 16
    assert not remote["remote_execution_qualified"]
    assert not remote["interacting_tissue_partitioning"]
    assigned = [t for rank in remote["ranks"] for t in rank["tasks"]]
    assert len(assigned) == len(set(assigned)) == 16
    assert set(assigned) == {t["id"] for t in baseline["tasks"]}
    ids, counts = [], dict(open=0, blocked=0)
    for task in baseline["tasks"]:
        definition = parse_definition(task["definition"])
        group = population(definition)
        assert definition.simulation.to_dict()["model"]["id"] == "resolved_tissue@8"
        assert len(definition.simulation.model.channels) == 39
        assert group.seed == raw["seed"]
        counts[task["arm"]] += group.worlds
        ids.extend(range(group.world_id_start, group.world_id_start + group.worlds))
    assert sorted(ids) == list(range(16)) and counts == dict(open=8, blocked=8)
    assert raw == original
    evidence(
        "planning",
        dict(
            status="passed",
            scope="Offline routing only; no GPU utilization or remote execution claim",
            inputs=original,
            plans=plans,
            world_ids=sorted(ids),
            arm_worlds=counts,
        ),
    )
