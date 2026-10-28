"""Offline placement for the two catalog compositions; no device timing claims."""

from copy import deepcopy

from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.ensemble.families import parse_definition, population
from tests.unit.test_assembly_cluster import ensemble_definition
from tests.unit.test_integrated_ensemble import experiment
from tests.unit.test_morris_lecar_catalog_planning import verify
from tests.unit.test_surface_catalog import evidence
from validation.tissue import morris_lecar_repair_fixtures as repair
from validation.tissue import morris_lecar_water_fixtures as water


def test_water_and_repair_worlds_keep_identity_in_one_four_sixteen_gpu_plans():
    raw = experiment("ionic", backend="gpu", worlds=8, width=1)
    template = deepcopy(raw["arms"][0])
    raw["arms"] = []
    models = dict(water="resolved_water@3", repair="resolved_repair@4")
    for name, fixtures in (("water", water), ("repair", repair)):
        arm = deepcopy(template)
        arm.update(id=name, seconds_per_world=None)
        arm["definition"]["simulation"] = fixtures.definition(backend="gpu")
        arm["definition"]["window_steps"] = 256
        raw["arms"].append(arm)
    raw["execution"]["max_output_bytes"] = 4 * 1024**3
    plans = verify(raw)
    ids, counts = [], dict(water=0, repair=0)
    for task in plans["local"]["tasks"]:
        spec = parse_definition(task["definition"])
        group = population(spec)
        assert spec.simulation.to_dict()["model"]["id"] == models[task["arm"]]
        assert len(spec.simulation.model.channels) == 60
        assert group.seed == raw["seed"]
        counts[task["arm"]] += group.worlds
        ids.extend(range(group.world_id_start, group.world_id_start + group.worlds))
    assert sorted(ids) == list(range(16)) and set(counts.values()) == {8}
    evidence(
        "morris-lecar-water-repair-planning",
        dict(
            status="passed",
            inputs=raw,
            plans=plans,
            world_ids=sorted(ids),
            arm_worlds=counts,
            scope=(
                "Offline 1/4/16-GPU placement; runtime balance, utilization "
                "and remote execution unqualified"
            ),
        ),
    )


def test_repair_assembly_worlds_keep_owner_streams_in_gpu_plans():
    raw = ensemble_definition()
    arm = deepcopy(raw["arms"][0])
    arm.update(
        id="repair",
        worlds=16,
        batch_worlds=1,
        seconds_per_world=None,
        definition=repair.assembly_definition(),
    )
    for binding in arm["definition"]["pools"]:
        for key in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(key)
    raw["arms"] = [arm]
    plans = verify(raw)
    ids = []
    for task in plans["local"]["tasks"]:
        spec = parse_assembly(task["definition"])
        assert spec.ionic.to_dict()["model"]["id"] == "resolved_repair@4"
        assert [binding.pool.seed for binding in spec.pools] == [2**32 - 1, 0]
        ids.extend(range(spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds))
    assert sorted(ids) == list(range(16))
    evidence(
        "morris-lecar-repair-assembly-planning",
        dict(
            status="passed",
            inputs=raw,
            plans=plans,
            world_ids=sorted(ids),
            scope="Offline 1/4/16-GPU placement; no stochastic assembly history",
        ),
    )
