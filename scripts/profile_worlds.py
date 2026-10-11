"""Bounded CPU profiles in separate processes; no speedup acceptance threshold.

Compare one compiled independent-world map with serial scalar calls. Each
measurement starts from fresh identical definitions, never advanced state.
"""

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.batch_io import write_batch_run  # noqa: E402
from cells.core.batch import run_batch  # noqa: E402
from cells.core.runner import run  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.io import runtime_identity, source_hashes, write_run  # noqa: E402
from tests.batch_fixtures import definition, short_spec  # noqa: E402


def workload(name, count):
    if name == "source_pair":
        spec = short_spec("source_pair_controls", 1)
    elif name == "graph32":
        data = short_spec("reaction_transport_chain", 1).to_dict()
        n = 32
        model = data["model"]
        model["population"] = {"count": n, "cell_ids": list(range(1, n + 1))}
        model["initial_state"] = {
            "amount": [[8.0] + [0.0] * (n - 1), [0.0] * (n - 1) + [2.0]],
            "volume": [1.0] * n,
        }
        model["parameters"]["reaction"].update(forward_rate=[0.2] * n, reverse_rate=[0.05] * n)
        model["parameters"]["contacts"] = [
            {
                "contact_id": 1000 + i,
                "from_cell_id": i + 1,
                "to_cell_id": i + 2,
                "permeability": [0.4, 0.1],
            }
            for i in range(n - 1)
        ]
        data["experiment"]["contact"]["contact_ids"] = list(range(1000, 1000 + n - 1))
        data["experiment"]["contact"]["schedule"] = [
            {"time": 0, "open_fractions": [1.0] * (n - 1)},
            {"time": 0.137, "open_fractions": [float(i % 2) for i in range(n - 1)]},
            {"time": 0.274, "open_fractions": [1.0] * (n - 1)},
        ]
        data["execution"].update(dt=0.01, capacity=n, edge_capacity=n - 1)
        spec = parse_spec(data)
    else:
        raise ValueError("Unknown bounded workload")
    return definition([spec] * count)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def worker(args):
    spec = workload(args.workload, args.worlds)
    initial, runtime = source_hashes(), runtime_identity()
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "definition.json", spec.to_dict())

    def execute():
        start = perf_counter()
        result = (
            run_batch(spec)
            if args.mode == "batch"
            else tuple(run(w.simulation) for w in spec.worlds)
        )
        elapsed = perf_counter() - start
        if args.mode == "batch":
            timing = result.timings
            values = {
                key: timing[key]
                for key in (
                    "preparation_seconds",
                    "compile_or_cache_seconds",
                    "host_transfer_and_assembly_seconds",
                    "analysis_seconds",
                )
            }
            values["execute_seconds"] = timing["median_execute_seconds"]
        else:
            values = {
                key: sum(r.timings[key] for r in result)
                for key in (
                    "preparation_seconds",
                    "compile_or_cache_seconds",
                    "execute_seconds",
                    "host_transfer_and_assembly_seconds",
                    "analysis_seconds",
                )
            }
        return result, values | {"full_call_seconds": elapsed}

    cold, cold_timing = execute()
    execute()  # Explicitly untimed warm-up, from the same original state.
    samples = []
    for _ in range(3):
        result, timing = execute()
        samples.append(timing)
        original_worlds = tuple(cold.worlds.values()) if args.mode == "batch" else cold
        repeated_worlds = tuple(result.worlds.values()) if args.mode == "batch" else result
        for a, b in zip(original_worlds, repeated_worlds, strict=True):
            for x, y in zip(a.history, b.history, strict=True):
                np.testing.assert_array_equal(x, y)
    stored = perf_counter()
    if args.mode == "batch":
        write_batch_run(output / "run", cold)
        arrays = cold.resources
    else:
        for world, result in zip(spec.worlds, cold, strict=True):
            write_run(output / f"run/worlds/world-{world.world_id}", result)
        arrays = {
            "host_history_array_bytes": sum(a.nbytes for r in cold for a in r.history),
            "host_observation_array_bytes": sum(
                a.nbytes for r in cold for a in vars(r.observations).values()
            ),
        }
    write_seconds = perf_counter() - stored
    payloads = {
        str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
    }
    bytes_written = sum((output / name).stat().st_size for name in payloads)
    assert source_hashes() == initial and runtime_identity() == runtime
    receipt = {
        "status": "pass",
        "workload": args.workload,
        "worlds": args.worlds,
        "mode": args.mode,
        "definition_sha256": spec.fingerprint,
        "cold_call": cold_timing,
        "warm_full_call_samples": samples,
        "median_warm_full_call_seconds": float(
            np.median([r["full_call_seconds"] for r in samples])
        ),
        "median_warm_execute_seconds": float(np.median([r["execute_seconds"] for r in samples])),
        "artifact_write_seconds": write_seconds,
        "artifact_bytes": bytes_written,
        "arrays": arrays,
        "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        * (1 if sys.platform == "darwin" else 1024),
        "rss_scope": (
            "whole worker peak including imports, compiler, repeated runs and output; "
            "not live array storage"
        ),
        "source_hashes": initial,
        "runtime": runtime,
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "files_sha256": payloads,
        "driver_sha256": sha(Path(__file__)),
    }
    write_json(output / "profile.json", receipt)
    print(
        json.dumps(
            {"status": "pass", "workload": args.workload, "worlds": args.worlds, "mode": args.mode}
        ),
        flush=True,
    )


def profile(output):
    output.mkdir(parents=True, exist_ok=False)
    initial = source_hashes()
    records, comparison = {}, {}
    for name in ("graph32", "source_pair"):
        for count in (1, 4, 16):
            pair = {}
            for mode in ("scalar", "batch"):
                label = f"{name}-{count:02d}-{mode}"
                with (output / f"{label}.log").open("x") as log:
                    subprocess.run(
                        [
                            sys.executable,
                            "-W",
                            "error",
                            str(Path(__file__)),
                            "--worker",
                            "--workload",
                            name,
                            "--worlds",
                            str(count),
                            "--mode",
                            mode,
                            "--output",
                            str((output / label).resolve()),
                        ],
                        cwd=ROOT,
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=120,
                        check=True,
                    )
                receipt = json.loads((output / label / "profile.json").read_text())
                assert receipt["source_hashes"] == initial
                records[label] = sha(output / label / "profile.json")
                pair[mode] = receipt
                print(label, flush=True)
            assert pair["batch"]["definition_sha256"] == pair["scalar"]["definition_sha256"]
            maximum = 0.0
            for identity in range(10, 10 + count):
                files = [
                    output / f"{name}-{count:02d}-{mode}/run/worlds/world-{identity}/trajectory.npz"
                    for mode in ("scalar", "batch")
                ]
                with np.load(files[0]) as scalar, np.load(files[1]) as batched:
                    assert set(scalar.files) == set(batched.files)
                    for key in scalar.files:
                        a, b = scalar[key], batched[key]
                        assert a.shape == b.shape and a.dtype == b.dtype
                        if a.dtype.kind in "biuUS":
                            np.testing.assert_array_equal(a, b)
                        else:
                            np.testing.assert_allclose(a, b, rtol=2e-11, atol=2e-11)
                            maximum = max(maximum, float(np.max(abs(a - b), initial=0)))
            comparison[f"{name}-{count:02d}"] = {
                "max_absolute_array_difference": maximum,
                "scalar_to_batch_warm_kernel_ratio": pair["scalar"]["median_warm_execute_seconds"]
                / pair["batch"]["median_warm_execute_seconds"],
                "scalar_to_batch_warm_full_call_ratio": pair["scalar"][
                    "median_warm_full_call_seconds"
                ]
                / pair["batch"]["median_warm_full_call_seconds"],
            }
    assert source_hashes() == initial
    write_json(
        output / "verification.json",
        {
            "status": "pass",
            "source_hashes": initial,
            "runtime": runtime_identity(),
            "workers": records,
            "comparison": comparison,
            "driver_sha256": sha(Path(__file__)),
            "scope": (
                "12 sequential bounded CPU workers, 3 warm measurements each; "
                "shared-host diagnostics, no GPU or general speedup claim"
            ),
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--workload", choices=("graph32", "source_pair"))
    parser.add_argument("--worlds", type=int, choices=(1, 4, 16))
    parser.add_argument("--mode", choices=("scalar", "batch"))
    arguments = parser.parse_args()
    if arguments.worker:
        if any(getattr(arguments, name) is None for name in ("workload", "worlds", "mode")):
            parser.error("Worker requires workload, worlds and mode")
        worker(arguments)
    else:
        profile(arguments.output)
