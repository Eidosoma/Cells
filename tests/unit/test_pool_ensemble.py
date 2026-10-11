"""The finite-bond family retains its completion definition and full material totals."""

import pytest

from cells.assembly_pool.engine import initial_state, summary
from cells.ensemble.cli import aggregate
from cells.ensemble.families import first_completion, parse_definition
from cells.ensemble.plan import plan


def experiment():
    return {
        "kind": "finite_bond_ensemble@1",
        "seed": 29,
        "arms": [
            {
                "id": name,
                "definition": {
                    "model": "finite_bond_assembly@1",
                    "initial_nodes": nodes,
                    "end_time_s": 0.1,
                    "event_chunk_size": 16,
                },
                "worlds": 16,
                "batch_worlds": 8,
                "seconds_per_world": None,
            }
            for name, nodes in (("ring", [10, 12, 14, 16, 18]), ("open", [10, 0, 1, 2, 3]))
        ],
        "execution": {
            "max_wall_seconds": 120,
            "max_output_bytes": 512 * 1024**2,
            "target_gpu_utilization_pct": 70,
            "worker_threads": 1,
            "workers_per_gpu": 2,
        },
    }


def test_finite_family_plan_and_kind_refusal():
    data = experiment()
    planned = plan(data, 1)
    assert planned["worlds"] == 32 and len(planned["tasks"]) == 4
    assert {t["definition"]["model"] for t in planned["tasks"]} == {"finite_bond_assembly@1"}
    data["kind"] = "assembly_ensemble@1"
    with pytest.raises(ValueError, match="kind"):
        plan(data, 1)


def test_full_cage_completion_requires_all_bonds():
    spec = parse_definition({"model": "finite_bond_assembly@1", "worlds": 2})
    state = initial_state(spec)
    state.first_passage_s[:, 20] = 0.1
    assert (first_completion(spec, state) == -1).all()
    state.full_first_s[1] = 0.2
    assert first_completion(spec, state).tolist() == [-1, 0.2]


def test_aggregation_keeps_finite_material_and_completion_semantics():
    spec = parse_definition({"model": "finite_bond_assembly@1", "worlds": 2})
    result = summary(spec, initial_state(spec)) | {
        "arm": "ring",
        "completed_shells": 0,
        "completion_event": "first_full_20_site_30_bond_cage",
        "restricted_wait_sum_s": 2.0,
        "wall_start": 0.0,
        "wall_end": 1.0,
        "survival_times_s": [0.0, 1.0],
        "not_completed_counts": [2, 2],
        "execute_seconds": 0.1,
    }
    arm = aggregate([result, result])["ring"]
    assert arm["initial_total_trimers"] == 4 * spec.total_trimers
    assert (
        arm["final_free_trimers"] + arm["final_attached_trimers"] + arm["final_fragment_trimers"]
        == arm["initial_total_trimers"]
    )
    assert arm["material_residual_trimers"] == 0
    assert arm["completion_event"] == "first_full_20_site_30_bond_cage"
