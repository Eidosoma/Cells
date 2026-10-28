"""Offline assembly/catalog world routing through the sixteen-GPU target."""

from copy import deepcopy

from cells.assembly_cluster.spec import parse_spec
from cells.ensemble.plan import jupiter_plan, plan
from tests.unit.test_assembly_cluster import ensemble_definition
from tests.unit.test_surface_calcium_catalog import evidence
from validation.tissue import surface_calcium_catalog_fixtures as fixtures


def test_owned_catalog_assembly_keeps_world_and_stream_ids_through_jupiter_plans():
    raw = ensemble_definition()
    raw["arms"][0].update(worlds=8, batch_worlds=1, id="open")
    raw["arms"][0]["definition"] = fixtures.assembly_definition()
    for binding in raw["arms"][0]["definition"]["pools"]:
        for key in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(key)
    second = deepcopy(raw["arms"][0])
    second["id"] = "blocked"
    second["definition"]["ionic"] = fixtures.definition("blocked")
    raw["arms"].append(second)
    original = deepcopy(raw)
    local = plan(raw, 1)
    node, future = jupiter_plan(raw, 1), jupiter_plan(raw, 4)
    for actual in (node, future):
        assert actual["tasks"] == local["tasks"]
        deployment = actual["deployment"]
        assert deployment["maximum_target_gpus"] == 16
        assert not deployment["remote_execution_qualified"]
        assert not deployment["interacting_tissue_partitioning"]
        assigned = [t for rank in deployment["ranks"] for t in rank["tasks"]]
        assert len(assigned) == len(set(assigned)) == 16
    ids, counts = [], dict(open=0, blocked=0)
    for task in local["tasks"]:
        spec = parse_spec(task["definition"])
        assert spec.ionic.to_dict()["model"]["id"] == "resolved_calcium@7"
        assert spec.ionic.to_dict()["model"]["ionic"]["id"] == "resolved_tissue@8"
        assert [b.pool.seed for b in spec.pools] == [2**32 - 1, 0]
        ids.extend(range(spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds))
        counts[task["arm"]] += spec.pool.worlds
    assert sorted(ids) == list(range(16)) and counts == dict(open=8, blocked=8)
    assert raw == original
    evidence(
        "assembly-planning",
        dict(
            status="passed",
            scope="Offline 1/4/16-GPU world/stream routing; no remote execution claim",
            inputs=original,
            plans=dict(local=local, jupiter_one_node=node, jupiter_four_nodes=future),
            world_ids=sorted(ids),
            arm_worlds=counts,
        ),
    )
