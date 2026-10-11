"""Fixed scientific counts for the first GPU concentration/rate experiment."""

import argparse
import json
from pathlib import Path

from cells.assembly.graph import OPEN_CHAIN, RING
from cells.core.output_paths import within_output_root
from cells.ensemble.plan import plan


def definition(worlds=32768, batch_worlds=32768):
    arms = []
    for concentration in (5.6, 9.0, 17.0):
        for off in (5.0, 10.0, 20.0):
            for name, nodes in (("ring", RING), ("open", OPEN_CHAIN), ("single", (10,))):
                arms.append(
                    {
                        "id": f"{name}-c{concentration:g}-off{off:g}".replace(".", "p"),
                        "definition": {
                            "initial_nodes": list(nodes),
                            "free_trimer_M": concentration * 1e-9,
                            "k_on_M_inv_s": 1e7,
                            "k_off_s_inv": off,
                            "end_time_s": 300.0,
                            "event_chunk_size": 512,
                            "max_events_per_world": 100000,
                            "max_wall_seconds": 600.0,
                        },
                        "worlds": worlds,
                        "batch_worlds": batch_worlds,
                        "seconds_per_world": None,
                    }
                )
    return {
        "kind": "assembly_ensemble@1",
        "seed": 20260920,
        "arms": arms,
        "execution": {
            "max_wall_seconds": 1800,
            "max_output_bytes": 8 * 1024**3,
            "target_gpu_utilization_pct": 70,
            "worker_threads": 2,
            "workers_per_gpu": 2,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worlds", type=int, default=32768)
    parser.add_argument("--batch-worlds", type=int, default=32768)
    args = parser.parse_args()
    if not within_output_root(args.output) or args.output.exists():
        raise ValueError("Write a new definition within the configured output root")
    data = definition(args.worlds, args.batch_worlds)
    planned = plan(data, 4)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "definition": str(args.output),
                "worlds": planned["worlds"],
                "arms": len(data["arms"]),
                "tasks": len(planned["tasks"]),
            }
        )
    )
