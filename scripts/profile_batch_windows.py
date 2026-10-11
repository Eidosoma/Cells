"""Sixteen isolated CPU workers: full cohorts, scalar windows and cohort windows.

Two ten-unit workloads, 4/16 worlds, full batch or 32/256-step cohort windows
and sequential scalar 256-step windows. Common declared budgets, three warm
calls, fresh initial state, and an untimed exact full-trajectory digest pass.
Never run alongside the verification suite; no speedup acceptance threshold.
"""

import argparse
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

from cells.batch_io import load_batch_snapshot, write_batch_run  # noqa: E402
from cells.batch_window_io import write_windowed_batch  # noqa: E402
from cells.core.batch import plan_batch, run_batch  # noqa: E402
from cells.core.batch_windows import plan_batch_windows, run_batch_windowed  # noqa: E402
from cells.core.windows import WindowPolicy, plan_windows, run_windowed  # noqa: E402
from cells.io import _sha256 as sha  # noqa: E402
from cells.io import _write_json as write_json  # noqa: E402
from cells.io import load_snapshot, runtime_identity, source_hashes  # noqa: E402
from cells.window_io import write_windowed_run  # noqa: E402
from scripts.profile_windows import definition as scalar_definition  # noqa: E402
from scripts.profile_windows import stream_digest  # noqa: E402
from tests.batch_fixtures import definition  # noqa: E402

POLICIES = (("full", 0), ("scalar", 256), ("cohort", 32), ("cohort", 256))


def workload(name, count):
    return definition([scalar_definition(name, 10)] * count)


def timing(result, mode):
    t = result.timings
    if mode == "cohort":
        return {
            "preparation_seconds": t["preflight_seconds"]
            + t["static_preparation_seconds"]
            + t["window_preparation_seconds"],
            "compile_seconds": t["compile_seconds"],
            "execute_seconds": t["execute_seconds"],
            "transfer_seconds": t["host_transfer_and_assembly_seconds"],
            "analysis_seconds": t["analysis_seconds"],
        }
    prefix = "window_" if mode == "scalar" else ""
    return {
        "preparation_seconds": t[prefix + "preparation_seconds"] + t.get("preflight_seconds", 0),
        "compile_seconds": t[prefix + "compile_or_cache_seconds"],
        "execute_seconds": t["window_execute_seconds"]
        if mode == "scalar"
        else t["median_execute_seconds"],
        "transfer_seconds": t[prefix + "host_transfer_and_assembly_seconds"],
        "analysis_seconds": t[prefix + "analysis_seconds"],
    }


def worker(args):
    spec, policy = workload(args.workload, args.worlds), WindowPolicy(max(1, args.width))
    sources, runtime = source_hashes(), runtime_identity()
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "definition.json", spec.to_dict())

    def execute():
        tick = perf_counter()
        if args.mode == "full":
            result = run_batch(spec)
            times = timing(result, "full")
            finals = {i: w.final for i, w in result.worlds.items()}
            arrays = {
                "peak_host_history_bytes": sum(
                    w.times.nbytes + sum(v.nbytes for v in w.history)
                    for w in result.worlds.values()
                ),
                "peak_host_observation_bytes": sum(
                    sum(v.nbytes for v in vars(w.observations).values())
                    for w in result.worlds.values()
                ),
            }
        elif args.mode == "cohort":
            result = run_batch_windowed(spec, policy)
            times, finals = timing(result, "cohort"), result.checkpoints
            arrays = {
                "peak_host_history_bytes": result.resources["peak_host_history_array_bytes"],
                "peak_host_observation_bytes": result.resources[
                    "peak_host_observation_array_bytes"
                ],
                "prepared_parameter_sets": result.resources["prepared_parameter_sets"],
                "compiled_executables": result.resources["peak_compiled_executables"],
                "rounds": result.resources["rounds"],
            }
        else:
            times, finals = {}, {}
            arrays = {"peak_host_history_bytes": 0, "peak_host_observation_bytes": 0}
            for world in spec.worlds:
                result = run_windowed(world.simulation, policy)
                for key, value in timing(result, "scalar").items():
                    times[key] = times.get(key, 0) + value
                finals[world.world_id] = result.final
                for key in arrays:
                    arrays[key] = max(arrays[key], result.resources[key])
        elapsed = perf_counter() - tick
        state = {
            str(i): {
                k: np.asarray(v).tolist() for k, v in zip(cp.state._fields, cp.state, strict=True)
            }
            for i, cp in finals.items()
        }
        return times | {"whole_call_seconds": elapsed}, arrays, state

    cold, arrays, expected = execute()
    execute()  # Untimed warm-up, still a fresh initial-state run.
    warm = []
    for _ in range(3):
        sample, latest, actual = execute()
        assert actual == expected and arrays == latest
        warm.append(sample)
    timed_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    streams = {w.world_id: stream_digest() for w in spec.worlds}
    tick = perf_counter()
    if args.mode == "full":
        result = run_batch(spec)
        for identity, world in result.worlds.items():
            streams[identity][0](world)
        write_batch_run(args.output / "run", result)
        load_batch_snapshot(args.output / "run/checkpoint_final")
    elif args.mode == "cohort":

        def consume(round_):
            for identity, part in round_.worlds.items():
                streams[identity][0](part)

        run_batch_windowed(spec, policy, sink=consume)
        write_windowed_batch(args.output / "run", spec, policy)
        load_batch_snapshot(args.output / "run/checkpoint_final")
    else:
        for world in spec.worlds:
            run_windowed(world.simulation, policy, sink=streams[world.world_id][0])
            path = args.output / f"world-{world.world_id}"
            write_windowed_run(path, world.simulation, policy)
            load_snapshot(path / "checkpoint_final")
    artifact_seconds = perf_counter() - tick
    assert sources == source_hashes() and runtime == runtime_identity()
    record = {
        "status": "pass",
        "runtime": runtime,
        "source_hashes": sources,
        "workload": args.workload,
        "horizon": 10,
        "worlds": args.worlds,
        "mode": args.mode,
        "width": args.width,
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "cold": cold,
        "warm": warm,
        "median_warm": {k: float(np.median([v[k] for v in warm])) for k in warm[0]},
        "arrays": arrays,
        "timed_worker_peak_rss_bytes": timed_rss,
        "whole_worker_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "parity_and_artifact_seconds": artifact_seconds,
        "final_state": expected,
        "trajectory_digests": {
            str(i): {k: v.hexdigest() for k, v in d.items()} for i, (_, d) in streams.items()
        },
        "files_sha256": {
            str(p.relative_to(args.output)): sha(p)
            for p in sorted(args.output.rglob("*"))
            if p.is_file()
        },
    }
    write_json(args.output / "profile.json", record)


def preflight():
    result = {}
    for name in ("graph32", "source_pair"):
        for count in (4, 16):
            spec = workload(name, count)
            result[f"{name}-{count}"] = {
                "full": plan_batch(spec).estimated_working_bytes,
                "scalar256": max(
                    plan_windows(w.simulation, WindowPolicy(256)).estimated_working_bytes
                    for w in spec.worlds
                ),
                "cohort32": plan_batch_windows(spec, WindowPolicy(32)).estimated_working_bytes,
                "cohort256": plan_batch_windows(spec, WindowPolicy(256)).estimated_working_bytes,
                "max_working_bytes": spec.max_working_bytes,
                "per_world_max_trace_bytes": spec.worlds[0].simulation.execution.max_trace_bytes,
            }
    return result


def profile(output):
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "preflight.json", preflight())
    sources, runtime = source_hashes(), runtime_identity()
    records, comparisons = {}, {}
    for name in ("graph32", "source_pair"):
        for count in (4, 16):
            outcomes = {}
            for mode, width in POLICIES:
                key = f"{name}-{count}-{mode}-{width}"
                print(f"Isolated CPU profile: {key}", flush=True)
                path = output / key
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__)),
                        "--worker",
                        "--workload",
                        name,
                        "--worlds",
                        str(count),
                        "--mode",
                        mode,
                        "--width",
                        str(width),
                        "--output",
                        str(path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                (output / f"{key}.log").write_text(completed.stdout + completed.stderr)
                assert completed.returncode == 0, completed.stderr
                record = json.loads((path / "profile.json").read_text())
                assert record["source_hashes"] == sources and record["runtime"] == runtime
                for relative, checksum in record["files_sha256"].items():
                    assert sha(path / relative) == checksum
                records[key] = {
                    "profile_sha256": sha(path / "profile.json"),
                    "payload_hashes": len(record["files_sha256"]),
                }
                outcomes[f"{mode}{width}"] = record
            base = outcomes["full0"]
            for record in outcomes.values():
                assert record["trajectory_digests"] == base["trajectory_digests"]
                assert record["final_state"] == base["final_state"]
            comparisons[f"{name}-{count}"] = {
                k: {
                    "median_warm_seconds": v["median_warm"]["whole_call_seconds"],
                    "history_bytes": v["arrays"]["peak_host_history_bytes"],
                    "timed_worker_peak_rss_bytes": v["timed_worker_peak_rss_bytes"],
                }
                for k, v in outcomes.items()
            }
    assert source_hashes() == sources and runtime_identity() == runtime
    receipt = {
        "status": "pass",
        "scope": "16 sequential fresh CPU workers; no GPU, hard RSS or general speedup guarantee",
        "runtime": runtime,
        "source_hashes": sources,
        "driver_sha256": sha(Path(__file__)),
        "preflight_sha256": sha(output / "preflight.json"),
        "workers": records,
        "comparison": comparisons,
    }
    write_json(output / "verification.json", receipt)
    return {"status": "pass", "workers": len(records), "sha256": sha(output / "verification.json")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--workload", choices=("graph32", "source_pair"))
    parser.add_argument("--worlds", type=int)
    parser.add_argument("--mode", choices=("full", "scalar", "cohort"))
    parser.add_argument("--width", type=int)
    args = parser.parse_args()
    if args.preflight_only:
        print(json.dumps(preflight(), indent=2))
    elif args.worker:
        worker(args)
    else:
        print(json.dumps(profile(args.output.resolve()), indent=2))
