"""Allocation-wide NVIDIA utilization, including startup, idle slots and tail."""

import csv
import io
import json
import os
import subprocess
import threading
import time


def inventory():
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,uuid,name", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    return [
        {"index": row[0].strip(), "uuid": row[1].strip(), "name": row[2].strip()}
        for row in csv.reader(io.StringIO(result.stdout))
        if row
    ]


def devices(requested, expected):
    if os.environ.get("SLURM_JOB_NUM_NODES", "1") != "1":
        raise ValueError(
            "This launcher owns exactly one node; multi-node accounting is not supported"
        )
    allocated = os.environ.get("SLURM_GPUS_ON_NODE")
    if allocated and allocated.isdigit() and int(allocated) != expected:
        raise ValueError("--allocated-gpus must include every GPU reserved by Slurm")
    rows = inventory()
    visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    if visible is not None:
        tokens = visible.split(",")
        resolved = []
        for token in tokens:
            matches = [r for r in rows if token.strip() in (r["uuid"], r["index"])]
            if len(matches) != 1:
                raise ValueError(
                    "Cannot resolve CUDA_VISIBLE_DEVICES to distinct allocated NVIDIA GPUs"
                )
            resolved.append(matches[0])
        rows = resolved
    indices = (
        list(range(len(rows))) if requested == "all" else [int(x) for x in requested.split(",")]
    )
    if (
        len(indices) != expected
        or len(set(indices)) != expected
        or any(i < 0 or i >= len(rows) for i in indices)
    ):
        raise ValueError("Selected GPUs must exactly fill --allocated-gpus; no silent idle slots")
    selected = [rows[i] for i in indices]
    if len({r["uuid"] for r in selected}) != expected:
        raise ValueError("GPU slots resolve to duplicate devices")
    return selected


class Monitor:
    def __init__(self, path, uuids, *, period=1.0):
        self.path, self.uuids, self.period = path, uuids, period
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._record, daemon=True)

    def start(self):
        self.thread.start()

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=20)
        if self.thread.is_alive():
            raise RuntimeError("Telemetry reader did not stop")

    def _record(self):
        with self.path.open("x") as stream:
            while not self.stop.is_set():
                sample = {"time": time.time(), "gpus": {}}
                try:
                    result = subprocess.run(
                        [
                            "nvidia-smi",
                            "-i",
                            ",".join(self.uuids),
                            "--query-gpu=uuid,utilization.gpu,utilization.memory,memory.used,power.draw",
                            "--format=csv,noheader,nounits",
                        ],
                        text=True,
                        capture_output=True,
                        check=True,
                        timeout=10,
                    )
                    for row in csv.reader(io.StringIO(result.stdout)):
                        if row:
                            values = []
                            for value in row[1:]:
                                try:
                                    values.append(float(value.strip()))
                                except ValueError:
                                    values.append(None)
                            sample["gpus"][row[0].strip()] = dict(
                                zip(
                                    (
                                        "utilization_pct",
                                        "memory_utilization_pct",
                                        "memory_MiB",
                                        "power_W",
                                    ),
                                    values,
                                    strict=True,
                                )
                            )
                except (OSError, subprocess.SubprocessError, ValueError) as exc:
                    sample["error"] = str(exc)
                stream.write(json.dumps(sample, allow_nan=False) + "\n")
                stream.flush()
                self.stop.wait(self.period)


def utilization(samples, uuids, start, end, target):
    duration = max(0, end - start)
    totals = {u: 0.0 for u in uuids}
    covered = {u: 0.0 for u in uuids}
    for i, sample in enumerate(samples):
        stop = samples[i + 1]["time"] if i + 1 < len(samples) else end
        # A stalled/missing monitor cannot invent a long interval of high use.
        stop = min(stop, sample["time"] + 3.0)
        width = max(0.0, min(end, stop) - max(start, sample["time"]))
        for uuid in uuids:
            value = sample["gpus"].get(uuid, {}).get("utilization_pct")
            if isinstance(value, (float, int)) and 0 <= value <= 100:
                totals[uuid] += width * value
                covered[uuid] += width
    means = {u: totals[u] / duration if duration else None for u in uuids}
    coverage = {u: covered[u] / duration if duration else 0 for u in uuids}
    enough = duration >= 30 and min(coverage.values(), default=0) >= 0.9
    met = enough and all(v >= target for v in means.values())
    return {
        "seconds": duration,
        "per_gpu_mean_pct": means,
        "allocated_gpu_mean_pct": sum(v or 0 for v in means.values()) / len(uuids),
        "per_gpu_coverage_fraction": coverage,
        "target_pct": target,
        "gate": "pass" if met else "below_target" if enough else "insufficient_telemetry",
        "metric": "time-weighted nvidia-smi GPU busy percent, not SM occupancy",
        "missing_intervals_count_as_zero": True,
    }
