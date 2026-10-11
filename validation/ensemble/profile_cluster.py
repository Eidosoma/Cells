"""Detached diagnostic replay using the ordinary ensemble worker and checks.

This validation driver adds observers and an optional qualified execution
candidate. Production source, physical inputs, world identities and checkpoint
codecs retain their qualified definitions. Timing includes observer overhead.
"""

import argparse
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from contextlib import ExitStack, nullcontext
from functools import partial
from pathlib import Path
from unittest.mock import patch

from cells.core.output_paths import within_output_root
from cells.ensemble import cli
from cells.ensemble.worker import worker as ordinary_worker

if __package__:
    from . import gpu_counters
else:
    import gpu_counters

TRACE_ALLOWANCE = 2 * 1024**3
RESOURCE_OBSERVER_ALLOWANCE = 64 * 1024**2
RESERVE = 4 * 1024**3


def need(value, message):
    if not value:
        raise ValueError(message)


def candidate_helpers():
    # Import only when explicitly selecting the experimental path. Worker
    # imports occur after ordinary_worker sets device visibility and affinity.
    if __package__:
        from . import parallel_cluster as parallel
    else:
        import parallel_cluster as parallel
    modules = (parallel, parallel.candidate_kernel, parallel.steps, parallel.rounding)
    paths = [Path(module.__file__) for module in modules]
    paths.append(Path(sys.modules[parallel.differences.__module__].__file__))
    return parallel, {path.name: path for path in paths}


def authenticate_candidate(path, parent_registration):
    """Bind the passed full-trajectory screen and its verbatim implementation."""
    parallel, helpers = candidate_helpers()
    result, done = (cli.read(path / name) for name in ("result.json", "completion.json"))
    need(result["status"] == done["status"] == "completed", "Candidate screen incomplete")
    need(done["result_sha256"] == cli.sha(path / "result.json"), "Candidate result changed")
    need(
        result["registration_sha256"] == cli.sha(path / "registration.json"),
        "Candidate registration changed",
    )
    record = parallel.authenticate(path)
    variant = parallel.ENERGY_SCREEN_VARIANT
    need(
        record["mode"] == result["mode"] == "energy_gpu_screen"
        and record["variants"] == [variant]
        and record["tile_width_by_backend"]["gpu"] in (32, 64)
        and record["execution_policy_by_backend"]["gpu"] == variant,
        "Require a complete 32- or 64-wide membrane-sum GPU qualification",
    )
    outcome = result["variants"][variant]
    need(
        outcome["bounded_numerical_checks_pass"] is True
        and outcome["eligible_for_performance_measurement"] is True
        and outcome["candidate_backends"] == ["gpu"],
        "Candidate is not eligible for performance measurement",
    )
    for name, helper in helpers.items():
        # The qualification orchestrator gained the width-64 gate after the
        # width-32 run. Numerical implementations and their dependencies must
        # still match; freeze and report the actual current orchestrator below.
        if name != "parallel_cluster.py":
            need(
                cli.sha(helper) == record["drivers_sha256"][name],
                "Candidate helper changed: " + name,
            )
    for name, digest in record["production_sources_sha256"].items():
        need(cli.sha(path / "source/cells" / name) == digest, "Candidate production changed")
    for name, digest in result["evidence_sha256"].items():
        need(cli.sha(path / name) == digest, "Candidate evidence changed: " + name)
    spec = parallel.parse_spec(record["definition"])
    for task in parent_registration["plan"]["tasks"]:
        parallel.same_world_physics(spec, parallel.parse_spec(task["definition"]))
    return {
        "path": str(path),
        "result_sha256": cli.sha(path / "result.json"),
        "registration_sha256": cli.sha(path / "registration.json"),
        "completion_sha256": cli.sha(path / "completion.json"),
        "variant": variant,
        "tile_width": record["tile_width_by_backend"]["gpu"],
        "helpers_sha256": {name: cli.sha(helper) for name, helper in helpers.items()},
        "qualified_orchestrator_sha256": record["drivers_sha256"]["parallel_cluster.py"],
        "qualified_trajectory_worlds": spec.pool.worlds,
        "scope": "65-world trajectory qualification; benchmark checks all saved endpoints",
    }


def authenticate_counter_baseline(parent, settings):
    """Use the scalar run with the same device counters as the timing comparator."""
    root = parent.parent
    result, done, record = (
        cli.read(root / name)
        for name in ("result.json", "completion.json", "profile-registration.json")
    )
    need(result["status"] == done["status"] == "completed", "Counter baseline incomplete")
    need(done["result_sha256"] == cli.sha(root / "result.json"), "Counter baseline changed")
    need(
        result["profile_registration_sha256"] == cli.sha(root / "profile-registration.json")
        and result["campaign_result_sha256"] == cli.sha(parent / "result.json"),
        "Counter baseline campaign changed",
    )
    need(
        record["mode"] == "throughput"
        and not record.get("experimental_candidate")
        and result["all_checkpoint_fields_bitwise_equal_to_parent"] is True,
        "Require a qualified scalar counter baseline",
    )
    # JSON normalizes integer field IDs to string keys.
    normalized = json.loads(json.dumps(settings))
    for key in (
        "tool_sha256",
        "driver_sha256",
        "uuid",
        "field_ids",
        "period_seconds",
        "minimum_coverage_fraction",
    ):
        need(record["gpu_counters"][key] == normalized[key], "Counter baseline differs: " + key)
    for name, digest in result["evidence_sha256"].items():
        need(cli.sha(root / name) == digest, "Counter baseline evidence changed: " + name)
    for interval in ("whole_job", "after_all_workers_warmed"):
        need(result["gpu_hardware_counters"][interval]["coverage_pass"], "Baseline coverage failed")
    return {"path": str(root), "result_sha256": cli.sha(root / "result.json")}


def candidate_execution(binding):
    return {
        key: binding[key] for key in ("variant", "tile_width", "result_sha256", "helpers_sha256")
    }


def candidate_context(binding):
    if binding is None:
        return nullcontext()
    parallel, helpers = candidate_helpers()
    need(
        {name: cli.sha(path) for name, path in helpers.items()} == binding["helpers_sha256"],
        "Worker candidate implementation changed",
    )
    return parallel.execution_candidate(binding["variant"], binding["tile_width"])


def process_sample(pid, proc=Path("/proc")):
    """Read identity, CPU seconds and resident memory without counting threads twice."""
    directory = proc / str(pid)
    fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
    status = dict(line.split(":", 1) for line in (directory / "status").read_text().splitlines())
    children = set()
    for task in (directory / "task").iterdir():
        try:
            children.update(int(p) for p in (task / "children").read_text().split())
        except FileNotFoundError:
            pass  # A thread can exit between discovery and reading its children.
    return {
        "pid": pid,
        "start_ticks": int(fields[19]),
        "cpu_seconds": (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK"),
        "rss_bytes": int(status.get("VmRSS", "0").split()[0]) * 1024,
        "hwm_bytes": int(status.get("VmHWM", "0").split()[0]) * 1024,
        "children": sorted(children),
    }


def memory_available():
    return next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )


def process_tree(pid):
    pending, seen, rows = [pid], set(), []
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            row = process_sample(current)
        except (FileNotFoundError, ProcessLookupError):
            continue  # Short-lived compiler and telemetry subprocesses can exit.
        rows.append(row)
        pending.extend(row["children"])
    return rows


class ResourceMonitor:
    def __init__(self, root, *, limits=None):
        self.root = root
        self.limits = limits
        self.violation = None
        self.pause_requested = False
        self.stop = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self.record, daemon=True)

    def request_pause(self):
        # The sampler starts before the ordinary controller installs its
        # cooperative handler. Never send SIGUSR1 to the default handler.
        if (
            self.violation
            and not self.pause_requested
            and callable(signal.getsignal(signal.SIGUSR1))
        ):
            os.kill(os.getpid(), signal.SIGUSR1)
            self.pause_requested = True
            cli.write(
                self.root / "memory-pause-requested.json",
                {
                    "time": time.time(),
                    "action": "ordinary_controller_checkpoint_pause",
                },
            )

    def inspect(self, sample):
        if self.limits and self.violation is None:
            reasons = []
            if sample["tree_rss_bytes"] > self.limits["tree_rss_bytes"]:
                reasons.append("process_tree_rss_allowance")
            if sample["available_memory_bytes"] < self.limits["available_memory_bytes"]:
                reasons.append("available_host_memory_reserve")
            if reasons:
                self.violation = {
                    "time": sample["time"],
                    "reasons": reasons,
                    "limits": self.limits,
                    "sample": sample,
                }
                cli.write(self.root / "memory-stop.json", self.violation)
        self.request_pause()

    def record(self):
        try:
            with (self.root / "host-resources.jsonl").open("x") as stream:
                while not self.stop.is_set():
                    rows = process_tree(os.getpid())
                    sample = {
                        "time": time.time(),
                        "processes": rows,
                        "tree_rss_bytes": sum(row["rss_bytes"] for row in rows),
                        "available_memory_bytes": memory_available(),
                    }
                    stream.write(json.dumps(sample) + "\n")
                    stream.flush()
                    self.inspect(sample)
                    self.stop.wait(1.0)
        except Exception:
            self.error = traceback.format_exc()
            if self.limits:
                self.violation = {
                    "time": time.time(),
                    "reasons": ["resource_sampler_failed"],
                    "traceback": self.error,
                }
                if not (self.root / "memory-stop.json").exists():
                    cli.write(self.root / "memory-stop.json", self.violation)
                # Keep trying until the cooperative handler is installed.
                while not self.stop.is_set() and not self.pause_requested:
                    self.request_pause()
                    self.stop.wait(0.1)

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=10)
        need(
            not self.thread.is_alive() and self.error is None,
            "Resource sampler failed: " + str(self.error),
        )


class WindowTrace:
    """Observe exactly two complete windows after two completed warm windows."""

    def __init__(self, directory, profiler):
        self.directory, self.profiler = directory, profiler
        self.active, self.failed, self.completed = False, False, False

    def failure(self):
        self.failed = True
        cli.write(
            self.directory / "failure.json",
            {
                "status": "failed",
                "time": time.time(),
                "traceback": traceback.format_exc(),
            },
        )

    def observe(self, window):
        if self.failed or self.completed:
            return
        if window == 2:
            self.directory.mkdir()
            try:
                options = self.profiler.ProfileOptions()
                options.python_tracer_level = 0
                options.host_tracer_level = 1
                options.enable_hlo_proto = False
                options.raise_error_on_start_failure = True
                self.profiler.start_trace(str(self.directory), profiler_options=options)
                self.active = True
                cli.write(self.directory / "started.json", {"time": time.time(), "after_window": 2})
            except Exception:
                self.failure()
        elif window == 4 and self.active:
            self.close(complete=True)

    def close(self, *, complete=False):
        if self.active:
            self.active = False
            try:
                ended = time.time()
                self.profiler.stop_trace()
                self.completed = complete
                cli.write(
                    self.directory / "finished.json",
                    {
                        "status": "captured" if complete else "interrupted",
                        "time": ended,
                        "export_finished_time": time.time(),
                        "last_window": 4 if complete else None,
                    },
                )
            except Exception:
                self.failure()


def profile_worker(
    root,
    slot,
    gpu,
    affinity,
    work,
    stopping,
    parents,
    *,
    trace_enabled=True,
    experimental_candidate=None,
):
    """Observe an optional candidate; the ordinary worker owns tasks and failures."""
    from cells.ensemble import families

    directory = Path(root) / f"worker-{slot}-profile"
    directory.mkdir()
    original = families.runtime_for
    seen = set()
    activation = ExitStack()
    activated = False

    def instrument(spec):
        nonlocal activated
        if experimental_candidate and not activated:
            # The ordinary worker has now set its device/CPU environment. Keep
            # one compiled candidate alive across all tasks on this worker.
            activation.enter_context(candidate_context(experimental_candidate))
            activated = True
        run, load, save = original(spec)

        def observed(spec, *, backend, state, callback):
            import jax.profiler

            width, first = spec.pool.worlds, spec.pool.world_id_start
            trace = None
            if trace_enabled and width not in seen:
                seen.add(width)
                trace = WindowTrace(directory / f"trace-batch-{width}", jax.profiler)
            with (directory / f"windows-batch-{width}-world-{first}.jsonl").open("x") as stream:

                def record(window, current, detail):
                    callback(window, current, detail)
                    usage = resource.getrusage(resource.RUSAGE_SELF)
                    stream.write(
                        json.dumps(
                            {
                                "window": window,
                                "time": time.time(),
                                "cpu_seconds": usage.ru_utime + usage.ru_stime,
                                "peak_rss_bytes": usage.ru_maxrss * 1024,
                                "traced_window": bool(trace and trace.active),
                            }
                        )
                        + "\n"
                    )
                    stream.flush()
                    if trace:
                        trace.observe(window)

                try:
                    final, report = run(spec, backend=backend, state=state, callback=record)
                    if experimental_candidate:
                        report = dict(
                            report,
                            experimental_candidate=candidate_execution(experimental_candidate),
                        )
                    return final, report
                finally:
                    if trace:
                        trace.close()

        def marked_save(path, spec, state, *, execution, provenance=None):
            return save(
                path,
                spec,
                state,
                execution=execution
                | {"experimental_candidate": candidate_execution(experimental_candidate)},
                provenance=provenance,
            )

        return observed, load, marked_save if experimental_candidate else save

    families.runtime_for = instrument
    try:
        ordinary_worker(root, slot, gpu, affinity, work, stopping, parents)
    finally:
        families.runtime_for = original
        activation.close()
        own = resource.getrusage(resource.RUSAGE_SELF)
        child = resource.getrusage(resource.RUSAGE_CHILDREN)
        cli.write(
            directory / "resources.json",
            {
                "pid": os.getpid(),
                "time": time.time(),
                "peak_rss_bytes": own.ru_maxrss * 1024,
                "cpu_seconds": own.ru_utime + own.ru_stime,
                "max_reaped_child_rss_bytes": child.ru_maxrss * 1024,
                "reaped_child_cpu_seconds": child.ru_utime + child.ru_stime,
                "gpu_tracing_enabled": trace_enabled,
                "experimental_candidate": candidate_execution(experimental_candidate)
                if experimental_candidate
                else None,
                "scope": (
                    "Worker lifetime including compilation and profiler overhead; "
                    "child RSS is a maximum, not a simultaneous sum"
                ),
            },
        )


def authenticate_parent(parent):
    result, done, registration = (
        cli.read(parent / name) for name in ("result.json", "completion.json", "registration.json")
    )
    need(result["status"] == done["status"] == "completed", "Require a completed parent profile")
    need(done["result_sha256"] == cli.sha(parent / "result.json"), "Parent result changed")
    need(
        result["registration_sha256"] == cli.sha(parent / "registration.json"),
        "Parent registration changed",
    )
    need(
        not any(result[k] for k in ("failed_tasks", "missing_tasks", "worker_abnormal_exits")),
        "Parent has incomplete tasks",
    )
    need(registration["sources_sha256"] == cli.sources(), "Production differs from parent")
    for name, expected in registration["sources_sha256"].items():
        need(cli.sha(parent / "source/cells" / name) == expected, "Frozen parent source changed")
    for task, record in result["result_records"].items():
        path = parent / "tasks" / task / "result.json"
        need(
            Path(record["path"]) == path and cli.sha(path) == record["sha256"],
            "Parent task changed",
        )
        row = cli.read(path)
        checkpoint = path.parent / "checkpoint"
        need(
            cli.sha(checkpoint / "manifest.json") == row["checkpoint_manifest_sha256"],
            "Parent checkpoint manifest changed",
        )
        need(
            cli.sha(checkpoint / "state.npz")
            == cli.read(checkpoint / "manifest.json")["state_sha256"],
            "Parent checkpoint state changed",
        )
    return result, registration


def compare_states(left, right):
    """Complete saved fields, dtype/shape and raw floating-point bits must match."""
    import numpy as np

    count = 0
    with np.load(left, allow_pickle=False) as a, np.load(right, allow_pickle=False) as b:
        need(set(a.files) == set(b.files), "Checkpoint fields differ")
        for name in a.files:
            x, y = a[name], b[name]
            need(
                x.shape == y.shape and x.dtype == y.dtype and x.tobytes() == y.tobytes(),
                "Checkpoint state differs: " + name,
            )
            count += x.size
    return count


def same_workload(definition, original):
    import copy

    normalized = copy.deepcopy(definition)
    for key in ("workers_per_gpu", "worker_threads", "max_wall_seconds"):
        normalized["execution"][key] = original["execution"][key]
    need(normalized == original, "Replay changed the scientific workload or non-worker controls")


def execute(root):
    monitor = ResourceMonitor(root)
    counters = None
    try:
        settings = cli.read(root / "profile-registration.json")
        mode = settings.get("mode", "trace")
        need(mode in ("trace", "throughput"), "Unsupported observation mode")
        monitor.limits = settings.get("memory_limits")
        if mode == "throughput":
            need(
                isinstance(monitor.limits, dict)
                and set(monitor.limits) == {"tree_rss_bytes", "available_memory_bytes"}
                and all(type(v) is int and v > 0 for v in monitor.limits.values())
                and monitor.limits["available_memory_bytes"] >= RESERVE,
                "Throughput run requires the memory guard and host reserve",
            )
        need(cli.sha(Path(__file__)) == settings["driver_sha256"], "Profile driver changed")
        parent = Path(settings["parent"])
        need(cli.sha(parent / "result.json") == settings["parent_result_sha256"], "Parent changed")
        parent_result, parent_registration = authenticate_parent(parent)
        need(
            cli.sha(root / "definition.json") == settings["definition_sha256"], "Definition changed"
        )
        need(cli.sources() == settings["sources_sha256"], "Frozen production changed")
        if "preparation" in settings:
            need(
                cli.sha(Path(settings["preparation"]) / "preparation.json")
                == settings["preparation_sha256"],
                "Prepared resource evidence changed",
            )
        same_workload(cli.read(root / "definition.json"), parent_registration["definition"])
        candidate = settings.get("experimental_candidate")
        if candidate:
            need(
                mode == "throughput" and settings.get("gpu_counters"),
                "Candidate benchmark requires hardware counters",
            )
            need(
                authenticate_candidate(Path(candidate["path"]), parent_registration) == candidate,
                "Candidate qualification binding changed",
            )
            need(
                authenticate_counter_baseline(parent, settings["gpu_counters"])
                == settings["counter_baseline"],
                "Counter baseline binding changed",
            )
        if settings.get("gpu_counters"):
            need(mode == "throughput", "Hardware counters cannot share a GPU trace session")
            counters = gpu_counters.CounterMonitor(root, settings["gpu_counters"])
            counters.start()
        cli.write(root / "started.json", {"pid": os.getpid(), "time": time.time()})
        monitor.thread.start()
        observer = (
            profile_worker if mode == "trace" else partial(profile_worker, trace_enabled=False)
        )
        if candidate:
            observer = partial(
                profile_worker, trace_enabled=False, experimental_candidate=candidate
            )
        with patch("cells.ensemble.worker.worker", observer):
            result = cli.register(
                argparse.Namespace(
                    command="run",
                    input=root / "definition.json",
                    output=root / "campaign",
                    devices="0",
                    allocated_gpus=1,
                    detach=False,
                )
            )
        if counters:
            counters.finish()
        monitor.finish()
        need(
            monitor.violation is None,
            "Memory guard requested a checkpoint pause; see memory-stop.json",
        )
        need(result["status"] == "completed", "Ordinary campaign did not complete")
        current = cli.read(root / "campaign/registration.json")
        comparable_plan = dict(current["plan"])
        comparable_plan["worker_processes"] = parent_registration["plan"]["worker_processes"]
        need(comparable_plan == parent_registration["plan"], "Replay task plan changed")
        compared = {}
        for task in current["plan"]["tasks"]:
            name = task["id"]
            path = Path("tasks") / name / "checkpoint/state.npz"
            compared[name] = compare_states(parent / path, root / "campaign" / path)
            if candidate:
                checkpoint = root / "campaign" / path.parent
                provenance = cli.read(checkpoint / "manifest.json")["provenance"]
                task_result = cli.read(checkpoint.parent / "result.json")
                need(
                    provenance["execution"]["experimental_candidate"]
                    == candidate_execution(candidate)
                    and provenance["parent"] is None
                    and task_result["experimental_candidate"] == candidate_execution(candidate),
                    "Candidate checkpoint or task provenance changed",
                )
        worker_resources = {
            p.parent.name: cli.read(p)
            for p in (root / "campaign").glob("worker-*-profile/resources.json")
        }
        need(
            len(worker_resources) == current["plan"]["worker_processes"],
            "Missing worker resource receipt",
        )
        traces = list((root / "campaign").glob("worker-*-profile/trace-batch-*"))
        need(len(traces) == (2 if mode == "trace" else 0), "Unexpected batch trace count")
        for trace in traces:
            need(
                not (trace / "failure.json").exists()
                and cli.read(trace / "finished.json")["status"] == "captured"
                and any(trace.rglob("*.xplane.pb")),
                "Missing or failed profiler trace",
            )
        samples = [
            json.loads(line) for line in (root / "host-resources.jsonl").read_text().splitlines()
        ]
        need(samples, "Missing resource samples")
        profile_bytes = sum(
            p.stat().st_size
            for p in (root / "campaign").glob("worker-*-profile/**/*")
            if p.is_file()
        )
        observer_allowance = TRACE_ALLOWANCE if mode == "trace" else RESOURCE_OBSERVER_ALLOWANCE
        need(profile_bytes <= observer_allowance, "Profiler output exceeded its allowance")
        worker_finishes = {
            p.stem: cli.read(p)["time"] for p in (root / "campaign").glob("worker-*-finished.json")
        }
        need(len(worker_finishes) == current["plan"]["worker_processes"], "Missing worker finish")
        arms = {}
        for record in result["result_records"].values():
            row = cli.read(record["path"])
            arms[row["arm"]] = max(arms.get(row["arm"], 0), row["wall_end"])
        output = {
            "status": "completed",
            "mode": mode,
            "finished_time": time.time(),
            "campaign_result_sha256": cli.sha(root / "campaign/result.json"),
            "profile_registration_sha256": cli.sha(root / "profile-registration.json"),
            "worker_resources": worker_resources,
            "worker_finish_gap_seconds": max(worker_finishes.values())
            - min(worker_finishes.values()),
            "arm_finish_gap_seconds": max(arms.values()) - min(arms.values()),
            "memory_limits": monitor.limits,
            "memory_guard_triggered": False,
            "resource_samples": len(samples),
            "sampled_peak_process_tree_rss_bytes": max(s["tree_rss_bytes"] for s in samples),
            "minimum_available_memory_bytes": min(s["available_memory_bytes"] for s in samples),
            "maximum_resource_sample_gap_seconds": max(
                (b["time"] - a["time"] for a, b in zip(samples, samples[1:], strict=False)),
                default=0,
            ),
            "all_checkpoint_fields_bitwise_equal_to_parent": True,
            "checkpoint_scalars_compared": compared,
            "trace_directories": [str(p.relative_to(root)) for p in traces],
            "profile_bytes": profile_bytes,
            "evidence_sha256": {
                str(p.relative_to(root)): cli.sha(p)
                for p in [
                    root / "host-resources.jsonl",
                    root / "campaign/gpu-utilization.jsonl",
                    *(p for p in (root / "campaign").glob("worker-*-profile/**/*") if p.is_file()),
                    *(root / "campaign").glob("worker-*-started.json"),
                    *(root / "campaign").glob("worker-*-finished.json"),
                ]
            },
            "automatic_followup": False,
            "scope": (
                "Instrumented diagnostic; trace contents still require interpretation. "
                "Timing and memory include observer overhead. "
                "No throughput or concurrency improvement claim."
            )
            if mode == "trace"
            else (
                "Single local paired-workload comparison with lightweight resource observations. "
                "Includes compilation, checks, I/O and all idle time; no GPU tracing. "
                "One trial does not establish multi-GPU scaling or general speedup."
            ),
        }
        if mode == "throughput":
            output["performance_comparison"] = {
                "baseline_result_sha256": settings["parent_result_sha256"],
                "baseline_elapsed_seconds": parent_result["elapsed_seconds"],
                "elapsed_seconds": result["elapsed_seconds"],
                "baseline_worlds_per_gpu_hour": parent_result["throughput"][
                    "worlds_per_allocated_gpu_hour"
                ],
                "worlds_per_gpu_hour": result["throughput"]["worlds_per_allocated_gpu_hour"],
                "baseline_gpu_busy_pct": parent_result["full_job_utilization"][
                    "allocated_gpu_mean_pct"
                ],
                "gpu_busy_pct": result["full_job_utilization"]["allocated_gpu_mean_pct"],
            }
        if candidate:
            output["experimental_candidate"] = candidate
            output["production_default_changed"] = False
            output["scope"] += (
                " Candidate trajectory equivalence covers 65 worlds; this benchmark additionally "
                "requires exact saved endpoints for all 128 worlds."
            )
        if counters:
            warms = [cli.read(p)["time"] for p in (root / "campaign").glob("worker-*-warm.json")]
            need(len(warms) == current["plan"]["worker_processes"], "Missing worker warm times")
            output["gpu_hardware_counters"] = {
                "whole_job": gpu_counters.summarize(
                    counters.rows, result["started_time"], result["finished_time"]
                ),
                "after_all_workers_warmed": gpu_counters.summarize(
                    counters.rows, max(warms), result["finished_time"]
                ),
                "interpretation": (
                    "SM activity counts time with at least one active warp per SM, averaged "
                    "over SMs. Occupancy counts resident warps relative to capacity. "
                    "Both include stalled warps; neither measures arithmetic throughput."
                ),
            }
            cli.write(root / "gpu-counter-summary.json", output["gpu_hardware_counters"])
            for interval in ("whole_job", "after_all_workers_warmed"):
                need(
                    output["gpu_hardware_counters"][interval]["coverage_pass"],
                    "Insufficient valid GPU counter coverage: " + interval,
                )
            output["evidence_sha256"].update(
                {
                    name: cli.sha(root / name)
                    for name in (
                        "gpu-counters.jsonl",
                        "gpu-counters.stderr.log",
                        "gpu-counter-summary.json",
                        "dcgm.log",
                    )
                    if (root / name).is_file()
                }
            )
            output["scope"] += " DCGM device counters were enabled; timing includes their overhead."
            if candidate:
                baseline = settings["counter_baseline"]
                need(
                    cli.sha(Path(baseline["path"]) / "result.json") == baseline["result_sha256"],
                    "Counter baseline result changed during run",
                )
                output["counter_baseline"] = baseline
                output["baseline_gpu_hardware_counters"] = cli.read(
                    Path(baseline["path"]) / "result.json"
                )["gpu_hardware_counters"]
        cli.write(root / "result.json", output)
        cli.write(
            root / "completion.json",
            {"status": "completed", "result_sha256": cli.sha(root / "result.json")},
        )
    except BaseException:
        failure_traceback = traceback.format_exc()
        if counters:
            try:
                counters.finish()
            except Exception:
                failure_traceback += "\nCounter cleanup:\n" + traceback.format_exc()
        if monitor.thread.is_alive():
            monitor.stop.set()
            monitor.thread.join(timeout=10)
        cli.write(
            root / "failure.json",
            {
                "status": "failed",
                "time": time.time(),
                "traceback": failure_traceback,
            },
        )
        raise


def launch(preparation, parent, root, *, mode="trace", dcgm_root=None, qualification=None):
    need(within_output_root(root) and not root.exists(), "Require a fresh workspace output")
    _, registration = authenticate_parent(parent)
    prepared = cli.read(preparation / "preparation.json")
    definition = cli.read(preparation / "definition.json")
    need(
        cli.sha(preparation / "definition.json") == prepared["definition_sha256"]
        and cli.sha(preparation / "plan.json") == prepared["plan_sha256"],
        "Preparation changed",
    )
    need(mode in ("trace", "throughput"), "Unsupported observation mode")
    counters_settings = None
    if dcgm_root is not None:
        from cells.ensemble.telemetry import devices

        need(mode == "throughput", "Hardware counters require an untraced throughput replay")
        subprocess.run(["sudo", "-n", "true"], check=True, timeout=5)
        counters_settings = {
            "tool_root": str(dcgm_root),
            "tool_sha256": gpu_counters.tool_identity(dcgm_root),
            "driver_sha256": cli.sha(Path(gpu_counters.__file__)),
            "uuid": devices("0", 1)[0]["uuid"],
            "timeout_seconds": definition["execution"]["max_wall_seconds"] + 180,
            "field_ids": gpu_counters.FIELDS,
            "period_seconds": gpu_counters.PERIOD,
            "minimum_coverage_fraction": gpu_counters.MIN_COVERAGE,
            "scope": "Device-wide counters; only the sampler runs with profiling privileges",
        }
    same_workload(definition, registration["definition"])
    candidate = baseline = None
    if qualification is not None:
        need(
            mode == "throughput" and counters_settings is not None,
            "Candidate benchmark requires hardware counters",
        )
        candidate = authenticate_candidate(qualification, registration)
        baseline = authenticate_counter_baseline(parent, counters_settings)
    planned = cli.read(preparation / "plan.json")
    comparable_plan = dict(planned)
    comparable_plan["worker_processes"] = registration["plan"]["worker_processes"]
    need(comparable_plan == registration["plan"], "Diagnostic must replay the same tasks")
    need(
        prepared["family"] == "ip3"
        and prepared["worker_processes"] == (1 if mode == "trace" else 2),
        "Require the registered one-worker trace or two-worker throughput profile",
    )
    need(
        prepared["qualified_parent"]["production_sources_sha256"] == cli.sources(),
        "Production differs from qualification",
    )
    if mode == "throughput":
        basis = prepared.get("measured_memory_basis")
        need(basis is not None, "Two workers require completed memory evidence")
        observed = Path(basis["path"])
        need(
            cli.sha(observed / "result.json") == basis["result_sha256"]
            and cli.sha(observed / "completion.json") == basis["completion_sha256"]
            and cli.sha(observed / "profile-registration.json")
            == basis["profile_registration_sha256"],
            "Prepared memory evidence changed",
        )
    extra_memory = TRACE_ALLOWANCE if mode == "trace" else 0
    observer_allowance = TRACE_ALLOWANCE if mode == "trace" else RESOURCE_OBSERVER_ALLOWANCE
    need(
        memory_available() >= prepared["required_available_memory_bytes"] + extra_memory,
        "Require the prepared worker allowance, trace allowance and memory reserve",
    )
    need(
        shutil.disk_usage(root.parent).free
        >= prepared["output_bytes_bound"]
        + prepared["cache_allowance_bytes"]
        + observer_allowance
        + RESERVE,
        "Diagnostic would consume the disk reserve",
    )
    need(
        set(prepared["cpu_affinity"]).issubset(os.sched_getaffinity(0)), "CPU affinity unavailable"
    )
    root.mkdir()
    (root / "source").mkdir()
    shutil.copytree(
        Path(cli.__file__).parents[1],
        root / "source/cells",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    driver = root / "source/profile_cluster.py"
    shutil.copyfile(__file__, driver)
    shutil.copyfile(gpu_counters.__file__, root / "source/gpu_counters.py")
    if candidate:
        for name, path in candidate_helpers()[1].items():
            shutil.copyfile(path, root / "source" / name)
    shutil.copyfile(preparation / "definition.json", root / "definition.json")
    environment = os.environ.copy()
    environment.pop("JAX_PLATFORMS", None)
    environment.update(
        PYTHONPATH=str(root / "source"),
        PYTHONDONTWRITEBYTECODE="1",
        JAX_ENABLE_X64="1",
        XLA_PYTHON_CLIENT_PREALLOCATE="false",
        XLA_PYTHON_CLIENT_MEM_FRACTION="0.2",
    )
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        environment[name] = "1"
    for name, folder in [
        ("TMPDIR", "tmp"),
        ("XDG_CACHE_HOME", "cache"),
        ("CUDA_CACHE_PATH", "cache/cuda"),
        ("JAX_COMPILATION_CACHE_DIR", "cache/jax"),
    ]:
        path = root / folder
        path.mkdir(parents=True, exist_ok=True)
        environment[name] = str(path)
    command = [
        "taskset",
        "-c",
        ",".join(map(str, prepared["cpu_affinity"])),
        sys.executable,
        "-B",
        str(driver),
        "_run",
        str(root),
    ]
    cli.write(
        root / "profile-registration.json",
        {
            "parent": str(parent),
            "mode": mode,
            "gpu_counters": counters_settings,
            "experimental_candidate": candidate,
            "counter_baseline": baseline,
            "parent_result_sha256": cli.sha(parent / "result.json"),
            "preparation": str(preparation),
            "preparation_sha256": cli.sha(preparation / "preparation.json"),
            "definition_sha256": cli.sha(root / "definition.json"),
            "sources_sha256": cli.sources(),
            "driver_sha256": cli.sha(driver),
            "command": command,
            "environment_overrides": {
                k: v for k, v in environment.items() if os.environ.get(k) != v
            },
            "removed_environment_variables": ["JAX_PLATFORMS"],
            "sample_period_seconds": 1.0,
            "traced_windows": [3, 4] if mode == "trace" else [],
            "trace_batches": [16, 32] if mode == "trace" else [],
            "observer_output_allowance_bytes": observer_allowance,
            "required_available_memory_bytes": prepared["required_available_memory_bytes"]
            + extra_memory,
            "memory_limits": {
                "tree_rss_bytes": prepared["host_memory_allowance_per_worker_bytes"]
                * prepared["worker_processes"],
                "available_memory_bytes": RESERVE,
            }
            if mode == "throughput"
            else None,
            "memory_guard_scope": (
                "One-second sampled soft guard; request the ordinary controller's checkpoint "
                "pause on pressure or monitoring failure. Not an instantaneous RSS cap."
            ),
            "available_memory_bytes_at_launch": memory_available(),
            "checkpoint_comparison": (
                "Every saved field, dtype, shape and raw bit versus the completed parent"
            ),
            "automatic_followup": False,
        },
    )
    with (root / "stdout.log").open("x") as stdout, (root / "stderr.log").open("x") as stderr:
        child = subprocess.Popen(
            command,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
            close_fds=True,
        )
    receipt = {
        "status": "launched",
        "pid": child.pid,
        "output": str(root),
        "time": time.time(),
        "max_wall_seconds": definition["execution"]["max_wall_seconds"],
    }
    cli.write(root / "launch.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("launch")
    start.add_argument("--preparation", type=Path, required=True)
    start.add_argument("--parent", type=Path, required=True)
    start.add_argument("--output", type=Path, required=True)
    start.add_argument("--mode", choices=("trace", "throughput"), default="trace")
    start.add_argument("--dcgm-root", type=Path)
    start.add_argument("--qualification", type=Path)
    internal = sub.add_parser("_run")
    internal.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "launch":
        print(
            json.dumps(
                launch(
                    args.preparation.resolve(),
                    args.parent.resolve(),
                    args.output.resolve(),
                    mode=args.mode,
                    dcgm_root=args.dcgm_root.resolve() if args.dcgm_root else None,
                    qualification=args.qualification.resolve() if args.qualification else None,
                ),
                indent=2,
            )
        )
    else:
        execute(args.output.resolve())
