"""Offline placement of an ensemble's worlds, through the sixteen-GPU plans, on live worlds.

One file holds the planning rules that a copy per older family repeated: an experiment of several
arms is planned for one GPU, for a four-GPU node and for four nodes, and every plan keeps the tasks,
each arm's physics and world count, the experiment's seed and the world IDs. Two kinds of arms:
ionic worlds of the three pump tissues, and finite-pool assemblies. No device, runtime or remote
execution claim.
"""

from collections import Counter
from copy import deepcopy

import pytest

from cells.ensemble.families import parse_definition, population
from cells.ensemble.plan import jupiter_plan, plan
from cells.numerics import surface_imex as imex
from validation.tissue import (
    surface_pump_fixtures,
    surface_pump_v2_fixtures,
    surface_pump_v3_fixtures,
)

WORLDS = 8


def ionic():
    """One arm per pump tissue: the pump, with the calcium pump, with channel populations."""
    families = dict(
        pump=surface_pump_fixtures,
        calcium=surface_pump_v2_fixtures,
        channels=surface_pump_v3_fixtures,
    )
    return {
        name: dict(
            model="cells.model.ionic_worlds@1",
            simulation=family.definition(backend="gpu", solver=imex.ARS222_ID),
            window_steps=256,
        )
        for name, family in families.items()
    }


def finite_bond():
    """Two arms of finite pools, from a ring of nodes and from an open chain."""
    return {
        name: dict(model="cells.model.finite_bond_assembly@1", initial_nodes=nodes, end_time_s=0.1)
        for name, nodes in (("ring", [10, 12, 14, 16, 18]), ("open", [10, 0, 1, 2, 3]))
    }


ARMS = {"ionic_ensemble@1": ionic, "finite_bond_ensemble@1": finite_bond}


def experiment(kind):
    """Each world its own task, with no runtime estimate, on the highest seed."""
    return dict(
        kind=kind,
        seed=2**32 - 1,
        arms=[
            dict(
                id=name,
                definition=definition,
                worlds=WORLDS,
                batch_worlds=1,
                seconds_per_world=None,
            )
            for name, definition in ARMS[kind]().items()
        ],
        execution=dict(
            max_wall_seconds=600,
            max_output_bytes=4 * 1024**3,
            target_gpu_utilization_pct=70,
            worker_threads=1,
        ),
    )


def physics(spec):
    """A parsed task's definition without the population fields, which the ensemble owns."""
    owned = ("worlds", "world_id_start", "seed")
    return {k: v for k, v in spec.to_dict().items() if k not in owned}


@pytest.mark.parametrize("kind", ARMS)
def test_mixed_arms_keep_their_identity_through_sixteen_gpu_plans(kind):
    raw = experiment(kind)
    original = deepcopy(raw)
    local = plan(raw, 1)
    placements = {t["id"] for t in local["tasks"]}
    for nodes in (1, 4):
        remote = jupiter_plan(raw, nodes)
        assert remote["tasks"] == local["tasks"]
        deployment = remote["deployment"]
        assert deployment["maximum_target_gpus"] == 16
        assert len(deployment["ranks"]) == 4 * nodes
        assert not deployment["remote_execution_qualified"]
        assert not deployment["interacting_tissue_partitioning"]
        assigned = [t for rank in deployment["ranks"] for t in rank["tasks"]]
        assert len(assigned) == len(local["tasks"]) and set(assigned) == placements
    assert raw == original
    assert not local["runtime_estimates_supplied"]
    arms = {arm["id"]: physics(parse_definition(arm["definition"])) for arm in raw["arms"]}
    ids, counts = [], Counter()
    for task in local["tasks"]:
        spec = parse_definition(task["definition"])
        assert physics(spec) == arms[task["arm"]]
        group = population(spec)
        assert group.seed == raw["seed"]
        counts[task["arm"]] += group.worlds
        ids.extend(range(group.world_id_start, group.world_id_start + group.worlds))
    assert sorted(ids) == list(range(WORLDS * len(arms)))
    assert counts == dict.fromkeys(arms, WORLDS)
