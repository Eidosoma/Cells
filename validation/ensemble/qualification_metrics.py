"""Reuse busy-time and DCGM samplers for bounded scientific qualification jobs."""

import json
import shutil
import time
from pathlib import Path

from cells.assembly.io import digest, write_json
from cells.ensemble.telemetry import Monitor, utilization
from validation.ensemble.gpu_counters import CounterMonitor, summarize, tool_identity


def registration(tool_root, uuid, timeout_seconds):
    return {
        "tool_root": str(tool_root),
        "tool_sha256": tool_identity(tool_root),
        "driver_sha256": digest(Path(__file__).with_name("gpu_counters.py")),
        "uuid": uuid,
        "timeout_seconds": timeout_seconds,
    }


def busy_summary(samples, uuid, began, ended):
    """Report the observed mean and coverage; missing measurements are not zeroes."""
    raw = utilization(samples, [uuid], began, ended, 70)
    coverage = raw["per_gpu_coverage_fraction"][uuid]
    return {
        "metric": "nvidia-smi GPU busy time; not SM activity",
        "seconds": ended - began,
        "mean_pct_over_covered_time": raw["per_gpu_mean_pct"][uuid] / coverage
        if coverage
        else None,
        "coverage_fraction": coverage,
        "coverage_pass": coverage >= 0.98,
        "missing_values_are_zero": False,
        "target_is_advisory": True,
    }


class GpuQualificationMetrics:
    def __init__(self, directory, settings):
        self.directory, self.settings = Path(directory), settings
        self.busy = self.counters = None
        self.started = None
        self.closed = False

    def start(self):
        self.directory.mkdir()
        (self.directory / "source").mkdir()
        shutil.copyfile(
            Path(__file__).with_name("gpu_counters.py"), self.directory / "source/gpu_counters.py"
        )
        self.counters = CounterMonitor(self.directory, self.settings)
        try:
            self.counters.start()
            self.busy = Monitor(self.directory / "gpu-utilization.jsonl", [self.settings["uuid"]])
            self.busy.start()
            self.started = time.time()
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        # Cleanup is independent: a broken busy sampler must not leave a
        # privileged hardware sampler running, or discard its failure evidence.
        for monitor in (self.busy, self.counters):
            if monitor is not None:
                try:
                    monitor.finish()
                except Exception as exc:
                    errors.append(str(exc))
        if errors:
            write_json(self.directory / "cleanup-failure.json", {"errors": errors})
            raise RuntimeError("; ".join(errors))

    def finish(self, *, warm_time=None, warm_unavailable_reason=None):
        ended = time.time()
        self.close()
        if self.started is None:
            raise ValueError("GPU observation never started")
        samples = [
            json.loads(line)
            for line in (self.directory / "gpu-utilization.jsonl").read_text().splitlines()
        ]
        whole = {
            "gpu_busy": busy_summary(samples, self.settings["uuid"], self.started, ended),
            "hardware": summarize(self.counters.rows, self.started, ended),
        }
        warm = None
        if warm_time is not None:
            if not self.started <= warm_time < ended:
                raise ValueError("Warm interval lies outside the GPU phase")
            warm = {
                "gpu_busy": busy_summary(samples, self.settings["uuid"], warm_time, ended),
                "hardware": summarize(self.counters.rows, warm_time, ended),
            }
        elif not warm_unavailable_reason:
            raise ValueError("An unavailable warm interval requires an explicit reason")
        result = {
            "gpu_uuid": self.settings["uuid"],
            "started_time": self.started,
            "finished_time": ended,
            "whole_job": whole,
            "after_warmup": warm,
            "warm_interval_unavailable_reason": warm_unavailable_reason if warm is None else None,
            "scope": (
                "Scientific GPU qualification includes compilation, host checks and sampler "
                "overhead; utilization is descriptive, not a correctness gate"
            ),
            "evidence_sha256": {
                name: digest(self.directory / name)
                for name in (
                    "gpu-utilization.jsonl",
                    "gpu-counters.jsonl",
                    "gpu-counters.stderr.log",
                    "dcgm.log",
                )
            },
        }
        write_json(self.directory / "result.json", result)
        return result
