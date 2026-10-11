"""Separate-process bounded CPU window profiles; no throughput pass threshold.

Twelve workers, two workloads, two horizons, full/32/256-step policies. Each
worker executes cold, warm-up, three warm calls, and an untimed full-parity digest
pass. RSS for the timed calls is captured before artifact/parity work. No other
verification workload should run during the profile.
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

from cells.core.runner import run  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.core.windows import WindowPolicy, run_windowed  # noqa: E402
from cells.io import _sha256 as sha  # noqa: E402
from cells.io import _write_json as write_json  # noqa: E402
from cells.io import load_snapshot, runtime_identity, source_hashes, write_run  # noqa: E402
from cells.window_io import write_windowed_run  # noqa: E402
from scripts.profile_worlds import workload  # noqa: E402


def definition(name, horizon):
    data = workload(name, 1).worlds[0].simulation.to_dict()
    # Explicit common profile reservation. The first 100-second graph attempt
    # correctly exceeded its inherited 64 MiB full-trace budget; retain that
    # refusal, without changing equations, dt, horizon or production guards.
    data["execution"]["max_trace_bytes"] = 134217728
    data["experiment"].update(
        end_time=horizon, observation_times=[0.0, 0.113, 0.613, float(horizon)]
    )
    return parse_spec(data)


def stream_digest():
    digests, count = {}, 0

    def consume(window):
        nonlocal count
        skip = 0 if count == 0 else 1
        arrays = {"accepted_times": window.times[skip:]}
        arrays.update(
            {name: v[skip:] for name, v in zip(window.history._fields, window.history, strict=True)}
        )
        arrays.update({"observed_" + k: v for k, v in vars(window.observations).items()})
        for k, v in arrays.items():
            digests.setdefault(k, hashlib.sha256()).update(np.ascontiguousarray(v).tobytes())
        count += 1

    return consume, digests


def worker(args):
    spec = definition(args.workload, args.horizon)
    args.output.mkdir(parents=True, exist_ok=False)
    sources, runtime = source_hashes(), runtime_identity()
    write_json(args.output / "definition.json", spec.to_dict())

    def execute():
        start = perf_counter()
        result = run(spec) if args.width == 0 else run_windowed(spec, WindowPolicy(args.width))
        elapsed = perf_counter() - start
        final = {
            k: np.asarray(v).tolist()
            for k, v in zip(result.final.state._fields, result.final.state, strict=True)
        }
        if args.width == 0:
            arrays = {
                "peak_host_history_bytes": result.times.nbytes
                + sum(v.nbytes for v in result.history),
                "peak_host_observation_bytes": sum(
                    v.nbytes for v in vars(result.observations).values()
                ),
            }
        else:
            arrays = result.resources
        return result.timings | {"whole_call_seconds": elapsed}, arrays, final

    cold, arrays, expected = execute()
    execute()
    warm = []
    for _ in range(3):
        timing, latest, actual = execute()
        assert actual == expected and latest == arrays
        warm.append(timing)
    timed_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    consume, digests = stream_digest()
    output_started = perf_counter()
    if args.width == 0:
        result = run(spec)
        consume(result)
        write_run(args.output / "run", result)
    else:
        run_windowed(spec, WindowPolicy(args.width), sink=consume)
        write_windowed_run(args.output / "run", spec, WindowPolicy(args.width, "observations"))
    artifacts = perf_counter() - output_started
    load_snapshot(args.output / "run/checkpoint_final")
    assert sources == source_hashes() and runtime == runtime_identity()
    receipt = {
        "status": "pass",
        "workload": args.workload,
        "horizon": args.horizon,
        "width": args.width,
        "runtime": runtime,
        "source_hashes": sources,
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "cold": cold,
        "warm": warm,
        "median_warm": {k: float(np.median([v[k] for v in warm])) for k in warm[0]},
        "arrays": arrays,
        "timed_worker_peak_rss_bytes": timed_rss,
        "whole_worker_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "parity_and_artifact_seconds": artifacts,
        "final_state": expected,
        "trajectory_digests": {k: v.hexdigest() for k, v in digests.items()},
        "files_sha256": {
            str(p.relative_to(args.output)): sha(p)
            for p in sorted(args.output.rglob("*"))
            if p.is_file()
        },
    }
    write_json(args.output / "profile.json", receipt)


def profile(output):
    output.mkdir(parents=True, exist_ok=False)
    records, comparison = {}, {}
    for name, horizons in (("graph32", (1, 100)), ("source_pair", (1, 10))):
        for horizon in horizons:
            outcomes = {}
            for width in (0, 32, 256):
                key = f"{name}-{horizon}-{width}"
                print(f"CPU profile: {key}", flush=True)
                path = output / key
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__)),
                        "--worker",
                        "--workload",
                        name,
                        "--horizon",
                        str(horizon),
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
                for payload, checksum in record["files_sha256"].items():
                    assert sha(path / payload) == checksum
                records[key] = {
                    "profile_sha256": sha(path / "profile.json"),
                    "payload_hashes": len(record["files_sha256"]),
                }
                outcomes[width] = record
            baseline = outcomes[0]
            comparison[f"{name}-{horizon}"] = {}
            for width, record in outcomes.items():
                assert record["final_state"] == baseline["final_state"]
                assert record["trajectory_digests"] == baseline["trajectory_digests"]
                comparison[f"{name}-{horizon}"][str(width)] = {
                    "median_warm_seconds": record["median_warm"]["whole_call_seconds"],
                    "full_to_policy_call_ratio": baseline["median_warm"]["whole_call_seconds"]
                    / record["median_warm"]["whole_call_seconds"],
                    "history_bytes": record["arrays"]["peak_host_history_bytes"],
                    "timed_worker_peak_rss_bytes": record["timed_worker_peak_rss_bytes"],
                }
    receipt = {
        "status": "pass",
        "scope": (
            "12 sequential CPU workers; 3 warm calls each; "
            "no GPU, hard RSS guarantee or general speedup claim"
        ),
        "runtime": runtime_identity(),
        "source_hashes": source_hashes(),
        "driver_sha256": sha(Path(__file__)),
        "workers": records,
        "comparison": comparison,
    }
    write_json(output / "verification.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--workload", choices=("graph32", "source_pair"))
    parser.add_argument("--horizon", type=int)
    parser.add_argument("--width", type=int)
    args = parser.parse_args()
    if args.worker:
        worker(args)
    else:
        profile(args.output.resolve())
