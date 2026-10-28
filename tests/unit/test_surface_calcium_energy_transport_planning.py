"""Offline 1/4/16-GPU placement of independent transporter worlds."""

from copy import deepcopy

from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.ensemble.families import parse_definition, population
from tests.unit.test_assembly_cluster import ensemble_definition
from tests.unit.test_hcn_extra_catalog_planning import verify
from tests.unit.test_integrated_ensemble import experiment
from tests.unit.test_surface_calcium_energy_transport import assembly_definition
from tests.unit.test_surface_catalog import evidence
from validation.tissue import calcium_energy_network_transport_fixtures as fixtures


def test_ordinary_transport_worlds_keep_identity_through_sixteen_gpu_plan():
    raw = experiment("ionic", backend="gpu", worlds=8, width=1)
    template = deepcopy(raw["arms"][0])
    raw["arms"] = []
    for name in ("active", "blocked"):
        arm = deepcopy(template)
        arm.update(id=name, seconds_per_world=None)
        arm["definition"]["simulation"] = fixtures.compact_probe(name, backend="gpu")
        arm["definition"]["window_steps"] = 256
        raw["arms"].append(arm)
    raw["execution"]["max_output_bytes"] = 4 * 1024**3
    plans = verify(raw)
    ids = []
    for task in plans["local"]["tasks"]:
        spec = parse_definition(task["definition"])
        group = population(spec)
        assert spec.simulation.to_dict()["model"]["id"] == fixtures.MODEL_ID
        assert len(spec.simulation.model.network_transporters) == 4
        assert group.seed == raw["seed"]
        ids.extend(range(group.world_id_start, group.world_id_start + group.worlds))
    assert sorted(ids) == list(range(16))
    evidence(
        "network-ordinary-planning",
        dict(
            status="passed",
            inputs=raw,
            plans=plans,
            world_ids=sorted(ids),
            scope="Offline placement only; runtime and GPU utilization unqualified",
        ),
    )


def test_assembly_transport_worlds_keep_owner_streams_through_sixteen_gpu_plan():
    raw = ensemble_definition()
    raw["arms"] = [deepcopy(raw["arms"][0])]
    raw["arms"][0].update(
        id="transport",
        worlds=16,
        batch_worlds=1,
        seconds_per_world=None,
        definition=assembly_definition(),
    )
    for binding in raw["arms"][0]["definition"]["pools"]:
        for key in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(key)
    plans = verify(raw)
    ids = []
    for task in plans["local"]["tasks"]:
        spec = parse_assembly(task["definition"])
        assert spec.ionic.to_dict()["model"]["id"] == fixtures.MODEL_ID
        assert [binding.pool.seed for binding in spec.pools] == [2**32 - 1, 0]
        ids.extend(range(spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds))
    assert sorted(ids) == list(range(16))
    evidence(
        "network-assembly-planning",
        dict(
            status="passed",
            inputs=raw,
            plans=plans,
            world_ids=sorted(ids),
            scope="Offline placement only; stochastic assembly history unqualified",
        ),
    )
