"""Scientific counts, runtime balance, node accounting and portable outputs."""

import copy

import pytest

from cells.core.output_paths import output_root, within_output_root
from cells.ensemble.cli import wilson
from cells.ensemble.plan import balance, plan
from cells.ensemble.telemetry import utilization


def experiment():
    return {
        "kind": "assembly_ensemble@1",
        "seed": 72,
        "arms": [
            {
                "id": name,
                "definition": {"end_time_s": 1.0},
                "worlds": 32,
                "batch_worlds": 8,
                "seconds_per_world": cost,
            }
            for name, cost in (("slow", 4), ("fast", 1))
        ],
        "execution": {
            "max_wall_seconds": 300,
            "max_output_bytes": 2**30,
            "target_gpu_utilization_pct": 70,
            "worker_threads": 1,
        },
    }


def test_two_workers_still_account_for_four_physical_gpus():
    data = experiment()
    data["execution"]["workers_per_gpu"] = 2
    result = plan(data, 4)
    assert result["allocated_gpus"] == 4
    assert result["worker_processes"] == 8
    assert len(result["tasks"]) == 8


def test_measured_balancing_preserves_the_experiment():
    original = experiment()
    tuned = balance(original, {"slow": 4, "fast": 1}, 8)
    assert tuned["arms"][0]["batch_worlds"] == 2
    assert tuned["arms"][1]["batch_worlds"] == 8
    assert tuned["seed"] == original["seed"]
    for before, after in zip(original["arms"], tuned["arms"], strict=True):
        assert before["definition"] == after["definition"]
        assert before["worlds"] == after["worlds"]
    for data in (original, tuned):
        tasks = plan(data, 4)["tasks"]
        ids = [
            i
            for task in tasks
            for i in range(
                task["definition"]["world_id_start"],
                task["definition"]["world_id_start"] + task["definition"]["worlds"],
            )
        ]
        assert sorted(ids) == list(range(64))


def test_cannot_omit_allocated_slurm_gpus_or_nodes(monkeypatch):
    from cells.ensemble.telemetry import devices

    monkeypatch.setenv("SLURM_GPUS_ON_NODE", "4")
    with pytest.raises(ValueError, match="every GPU"):
        devices("0", 1)
    monkeypatch.setenv("SLURM_JOB_NUM_NODES", "2")
    with pytest.raises(ValueError, match="one node"):
        devices("all", 4)


def test_balanced_plan_preserves_counts_ids_and_input():
    source = experiment()
    before = copy.deepcopy(source)
    result = plan(source, 4)
    assert source == before
    assert result["projected_tail_fraction"] <= 0.25
    assert result["tasks"][0]["arm"] == "slow"
    ids = []
    for task in result["tasks"]:
        spec = task["definition"]
        ids.extend(range(spec["world_id_start"], spec["world_id_start"] + spec["worlds"]))
    assert sorted(ids) == list(range(64))
    assert len(set(ids)) == 64
    assert sum(t["definition"]["worlds"] for t in result["tasks"] if t["arm"] == "slow") == 32


@pytest.mark.parametrize(
    "mutation", ["low_target", "duplicate", "ids", "too_few", "output_budget", "invalid_cost"]
)
def test_planner_refusals(mutation):
    data = experiment()
    if mutation == "low_target":
        data["execution"]["target_gpu_utilization_pct"] = 0
    elif mutation == "duplicate":
        data["arms"][1]["id"] = "slow"
    elif mutation == "ids":
        data["arms"][0]["definition"]["world_id_start"] = 1
    elif mutation == "too_few":
        for arm in data["arms"]:
            arm["batch_worlds"] = 32
    elif mutation == "invalid_cost":
        data["arms"][0]["seconds_per_world"] = float("nan")
    else:
        data["execution"]["max_output_bytes"] = 1
    with pytest.raises(ValueError):
        plan(data, 4)


def samples(values):
    return [
        {"time": float(t), "gpus": {str(i): {"utilization_pct": v} for i, v in enumerate(values)}}
        for t in range(100)
    ]


def test_node_metric_includes_idle_slots_and_tail():
    ids = [str(i) for i in range(4)]
    result = utilization(samples([90, 0, 0, 0]), ids, 0, 100, 70)
    assert result["allocated_gpu_mean_pct"] == 22.5
    assert result["gate"] == "below_target"
    assert utilization(samples([80] * 4), ids, 0, 100, 70)["gate"] == "pass"
    tail = samples([90] * 4)
    for row in tail[50:]:
        row["gpus"] = {u: {"utilization_pct": 0} for u in ids}
    assert utilization(tail, ids, 0, 100, 70)["allocated_gpu_mean_pct"] == 45


def test_missing_telemetry_cannot_pass():
    result = utilization(samples([100])[::20], ["0"], 0, 100, 70)
    assert result["gate"] == "insufficient_telemetry"
    assert result["allocated_gpu_mean_pct"] <= 15


def test_advisory_target_can_be_lowered_without_changing_scientific_work():
    data = experiment()
    original = plan(data, 1)
    data["execution"]["target_gpu_utilization_pct"] = 60
    revised = plan(data, 1)
    assert revised == original


def test_short_sample_cannot_qualify_full_job():
    assert utilization(samples([100]), ["0"], 0, 5, 70)["gate"] == "insufficient_telemetry"


def test_portable_explicit_output_root(monkeypatch, tmp_path):
    monkeypatch.setenv("CELLS_OUTPUT_ROOT", str(tmp_path))
    assert output_root() == tmp_path
    assert within_output_root(tmp_path / "runs/a")
    assert not within_output_root(tmp_path.parent / "escape")
    monkeypatch.setenv("CELLS_OUTPUT_ROOT", "/")
    with pytest.raises(ValueError):
        output_root()


def test_binomial_uncertainty_retains_zero_and_complete_arms():
    assert wilson(0, 100)[0] == 0
    assert 0 < wilson(0, 100)[1] < 0.05
    assert wilson(100, 100)[1] == 1
    assert 0.95 < wilson(100, 100)[0] < 1
