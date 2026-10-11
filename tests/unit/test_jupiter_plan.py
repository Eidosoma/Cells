"""Four-node planning preserves experiment identity and full allocation cost."""

import copy

import pytest

from cells.ensemble.plan import jupiter_plan, plan
from tests.unit.test_ensemble import experiment


def many_tasks():
    result = experiment()
    result["execution"]["max_output_bytes"] = 4 * 1024**3
    for arm in result["arms"]:
        arm["worlds"] = 128
        arm["batch_worlds"] = 4
    return result


@pytest.mark.parametrize("nodes", [1, 2, 3, 4])
@pytest.mark.parametrize("workers", [1, 2])
def test_node_layout_preserves_every_task_and_world(nodes, workers):
    data = many_tasks()
    data["execution"]["workers_per_gpu"] = workers
    before = copy.deepcopy(data)
    result = jupiter_plan(data, nodes)
    assert data == before
    assert result["tasks"] == plan(data, 1)["tasks"]
    placement = result["deployment"]
    ranks = placement["ranks"]
    assert len(ranks) == nodes * 4
    assert {(r["node"], r["local_gpu"]) for r in ranks} == {
        (n, g) for n in range(nodes) for g in range(4)
    }
    tasks = [t for rank in ranks for t in rank["tasks"]]
    assert len(tasks) == len(set(tasks)) == len(result["tasks"])
    assert set(tasks) == {t["id"] for t in result["tasks"]}
    assert all(r["tasks"] for r in ranks)
    assert placement["projected_allocated_gpu_hours"] == pytest.approx(
        nodes * 4 * placement["projected_wall_seconds"] / 3600
    )
    assert placement["projected_allocated_node_hours"] * 4 == pytest.approx(
        placement["projected_allocated_gpu_hours"]
    )
    assert placement["remote_execution_qualified"] is False
    assert placement["interacting_tissue_partitioning"] is False


@pytest.mark.parametrize("nodes", [0, 5, True, 1.5])
def test_future_target_has_an_explicit_upper_bound(nodes):
    with pytest.raises(ValueError, match="16 GH200"):
        jupiter_plan(many_tasks(), nodes)


def test_unknown_costs_do_not_invent_a_runtime_or_gpu_hour_estimate():
    data = many_tasks()
    data["arms"][0]["seconds_per_world"] = None
    result = jupiter_plan(data, 4)["deployment"]
    assert result["projected_wall_seconds"] is None
    assert result["projected_allocated_gpu_hours"] is None
    assert result["projected_tail_fraction"] is None


def test_sixteen_gpus_cannot_be_filled_by_eight_tasks():
    with pytest.raises(ValueError, match="Every allocated GPU"):
        jupiter_plan(experiment(), 4)


@pytest.mark.parametrize("family", ["ionic", "assembly_cell"])
def test_integrated_models_keep_world_identity_across_four_nodes(family):
    from cells.ensemble.families import parse_definition, population
    from tests.unit.test_integrated_ensemble import experiment as integrated

    data = integrated(family, backend="gpu", worlds=64, width=2)
    data["execution"]["max_output_bytes"] = 4 * 1024**3
    result = jupiter_plan(data, 4)
    ids = []
    for task in result["tasks"]:
        group = population(parse_definition(task["definition"]))
        ids.extend(range(group.world_id_start, group.world_id_start + group.worlds))
        assert group.seed == data["seed"]
    assert sorted(ids) == list(range(64))
    assert len(result["deployment"]["ranks"]) == 16


def test_cli_offline_plan_needs_no_gpu_and_refuses_omitted_devices(tmp_path, capsys):
    import json

    from cells.ensemble.cli import main

    definition = tmp_path / "definition.json"
    definition.write_text(json.dumps(many_tasks()))
    assert main(["plan", str(definition), "--jupiter-nodes", "4"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["allocated_gpus"] == 16 and result["deployment"]["nodes"] == 4
    assert main(["plan", str(definition), "--jupiter-nodes", "4", "--allocated-gpus", "4"]) == 2
    assert "all four GPUs per node" in capsys.readouterr().err
    assert main(["plan", str(definition), "--allocated-gpus", "0"]) == 2
