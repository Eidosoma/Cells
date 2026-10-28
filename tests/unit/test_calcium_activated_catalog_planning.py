"""Offline mixed-feature placement preserves world counts and owner seeds."""

from copy import deepcopy

from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.ensemble.families import parse_definition, population
from cells.ensemble.plan import jupiter_plan, plan
from tests.unit.test_assembly_cluster import ensemble_definition
from tests.unit.test_integrated_ensemble import experiment
from tests.unit.test_surface_catalog import evidence
from validation.tissue import calcium_activated_catalog_fixtures as fixtures


def verify(raw):
    original = deepcopy(raw)
    local = plan(raw, 1)
    plans = dict(local=local, node=jupiter_plan(raw, 1), four_nodes=jupiter_plan(raw, 4))
    for remote in (plans["node"], plans["four_nodes"]):
        assert remote["tasks"] == local["tasks"]
        deployment = remote["deployment"]
        assert deployment["maximum_target_gpus"] == 16
        assert not deployment["remote_execution_qualified"]
        assert not deployment["interacting_tissue_partitioning"]
        assigned = [t for rank in deployment["ranks"] for t in rank["tasks"]]
        assert len(assigned) == len(set(assigned)) == len(local["tasks"])
    assert raw == original
    assert not local["runtime_estimates_supplied"]
    return plans


def test_mixed_ionic_calcium_fuel_worlds_keep_identity_through_sixteen_gpu_plans():
    raw = experiment("ionic", backend="gpu", worlds=8, width=1)
    template = deepcopy(raw["arms"][0])
    raw["arms"] = []
    for family in fixtures.FAMILIES:
        arm = deepcopy(template)
        arm.update(id=family, seconds_per_world=None)
        arm["definition"]["simulation"] = fixtures.definition(family, backend="gpu")
        # Keep every physical step; validate in normal bounded windows instead
        # of the two-step windows inherited from a tiny adapter fixture.
        arm["definition"]["window_steps"] = 256
        raw["arms"].append(arm)
    raw["execution"]["max_output_bytes"] = 4 * 1024**3
    plans = verify(raw)
    ids, counts = [], {f: 0 for f in fixtures.FAMILIES}
    for task in plans["local"]["tasks"]:
        spec = parse_definition(task["definition"])
        group = population(spec)
        assert spec.simulation.to_dict()["model"]["id"] == fixtures.MODEL_IDS[task["arm"]]
        assert len(spec.simulation.model.channels) == 47
        assert group.seed == raw["seed"]
        counts[task["arm"]] += group.worlds
        ids.extend(range(group.world_id_start, group.world_id_start + group.worlds))
    assert sorted(ids) == list(range(24)) and set(counts.values()) == {8}
    evidence(
        "calcium-activated-mixed-planning",
        dict(
            status="passed",
            inputs=raw,
            plans=plans,
            world_ids=sorted(ids),
            arm_worlds=counts,
            scope=(
                "Offline 1/4/16-GPU routing; runtimes, utilization and remote execution unqualified"
            ),
        ),
    )


def test_both_assembly_compositions_keep_world_and_owner_stream_ids():
    raw = ensemble_definition()
    template = deepcopy(raw["arms"][0])
    raw["arms"] = []
    for family in ("calcium", "energy"):
        arm = deepcopy(template)
        arm.update(
            id=family,
            worlds=8,
            batch_worlds=1,
            seconds_per_world=None,
            definition=fixtures.assembly_definition(family),
        )
        for binding in arm["definition"]["pools"]:
            for key in ("worlds", "world_id_start", "seed"):
                binding["pool"].pop(key)
        raw["arms"].append(arm)
    plans = verify(raw)
    ids = []
    for task in plans["local"]["tasks"]:
        spec = parse_assembly(task["definition"])
        assert spec.ionic.to_dict()["model"]["id"] == fixtures.MODEL_IDS[task["arm"]]
        assert [binding.pool.seed for binding in spec.pools] == [2**32 - 1, 0]
        ids.extend(range(spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds))
    assert sorted(ids) == list(range(16))
    evidence(
        "calcium-activated-assembly-planning",
        dict(
            status="passed",
            inputs=raw,
            plans=plans,
            world_ids=sorted(ids),
            scope="Offline placement only; assembly history unqualified",
        ),
    )
