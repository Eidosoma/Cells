"""Small fixed workloads for integrated-model scheduling measurements.

Batch-size arms have disjoint world IDs. Assembly timings are exploratory cost
profiles with different random realizations, not a matched speedup estimate.
"""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def definitions():
    coupled = json.loads((ROOT / "configs/assembly_regulated_cell.json").read_text())
    for key in ("seed", "worlds", "world_id_start"):
        coupled["pool"].pop(key, None)
    coupled["ionic"]["execution"]["backend"] = "gpu"
    coupled["pool"].update(k_off_s_inv=300.0, k_close_s_inv=1000.0)
    assembly_arms = []
    # Ring/open controls have the same initial material and physical rates.
    for name, nodes in (("ring", [10, 12, 14, 16, 18]), ("open", [10, 0, 1, 2, 3])):
        for width in (64, 256):
            raw = copy.deepcopy(coupled)
            raw["pool"]["initial_nodes"] = nodes
            assembly_arms.append(
                {
                    "id": f"{name}-batch-{width}",
                    "definition": raw,
                    "worlds": 1024,
                    "batch_worlds": width,
                    "seconds_per_world": None,
                }
            )
    ionic = json.loads((ROOT / "configs/junction_finite_cluster.json").read_text())
    ionic["execution"]["backend"] = "gpu"
    ionic_arms = []
    for width in (8, 32):
        ionic_arms.append(
            {
                "id": f"cluster-batch-{width}",
                "definition": {
                    "model": "ionic_worlds@1",
                    "simulation": copy.deepcopy(ionic),
                    "window_steps": 256,
                },
                "worlds": 128,
                "batch_worlds": width,
                "seconds_per_world": None,
            }
        )
    execution = {
        "max_wall_seconds": 900,
        "max_output_bytes": 2 * 1024**3,
        "target_gpu_utilization_pct": 70,
        "worker_threads": 1,
        "workers_per_gpu": 2,
    }
    return {
        "ionic": {
            "kind": "ionic_ensemble@1",
            "seed": 20260921,
            "arms": ionic_arms,
            "execution": copy.deepcopy(execution),
        },
        "assembly_cell": {
            "kind": "assembly_cell_ensemble@1",
            "seed": 20260921,
            "arms": assembly_arms,
            "execution": copy.deepcopy(execution),
        },
    }


def throughput_definitions(baseline):
    """Increase useful ensemble work with one batch shape per model family.

    Physical rates, timestep, 20-ms horizon and controls come from the completed
    baseline. More worlds change the stochastic sample; this is a capacity and
    cost profile, not a matched biological comparison or four-GPU extrapolation.
    """
    tuned = copy.deepcopy(baseline)
    assembly = tuned["assembly_cell"]
    arms = []
    for name in ("ring", "open"):
        candidates = [a for a in assembly["arms"] if a["id"].startswith(name + "-batch-")]
        if len(candidates) != 2 or candidates[0]["definition"] != candidates[1]["definition"]:
            raise ValueError("Require matching baseline physical definitions for each organization")
        raw = copy.deepcopy(candidates[0]["definition"])
        # One complete 200-tick chunk avoids a second compiled tail shape and
        # repeated host transfers. Event times and guarded RK4 steps are unchanged.
        raw["window_ticks"] = 200
        arms.append(
            {
                "id": name,
                "definition": raw,
                "worlds": 16384,
                "batch_worlds": 2048,
                "seconds_per_world": None,
            }
        )
    assembly["arms"] = arms
    assembly["execution"]["max_output_bytes"] = 4 * 1024**3
    ionic = tuned["ionic"]
    if len(ionic["arms"]) != 2 or ionic["arms"][0]["definition"] != ionic["arms"][1]["definition"]:
        raise ValueError("Require matching baseline ionic definitions")
    ionic["arms"] = [
        {
            "id": "cluster",
            "definition": copy.deepcopy(ionic["arms"][0]["definition"]),
            "worlds": 1024,
            "batch_worlds": 64,
            "seconds_per_world": None,
        }
    ]
    return tuned
