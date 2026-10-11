"""Bounded 100-ms pump/leak resource and timestep pilot using existing evidence paths.

One native timestep is diagnostic, not a refinement qualification. Keep all
source-law, conservation and numerical thresholds from the completed 10-ms
comparison. Reuse the three independent 100-ms references without solving again.
"""

import argparse
import copy
import gc
import json
import math
import os
import resource
import shutil
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "validation/betse/fresh_rerun"))
import common as u  # noqa: E402

DURATION = 0.1
DT = 1.5625e-6
STREAM_BYTES = 512 * 1024**2
CELLS_TRACE_BYTES = 512 * 1024**2
ARTIFACT_BYTES = 2 * 1024**3
PHASE_SECONDS = {"cells": 900, "observed": 9000, "unobserved": 6000, "compare": 9000}
SIMULATIONS = ("cells", "observed", "unobserved")


class Progress:
    """Append-only, fsynced phase/step evidence survives a killed reviewer."""

    def __init__(self, directory):
        self.directory, self.phase = directory, "starting"
        self.started = time.monotonic()
        self.path = directory / "review-progress.jsonl"
        with self.path.open("x"):
            pass
        self("review_started")

    def __call__(self, event, **values):
        row = dict(
            utc=u.utc(),
            phase=self.phase,
            event=event,
            elapsed_seconds=time.monotonic() - self.started,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            **values,
        )
        with self.path.open("a") as handle:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        print(json.dumps(row, sort_keys=True), flush=True)

    def run(self, name, action, *, artifact=None):
        self.phase = name
        began = time.monotonic()
        self("phase_started")
        try:
            result = action()
            evidence = {}
            if artifact is not None:
                u.write(self.directory / artifact, result)
                evidence = {"artifact": artifact, "sha256": u.sha(self.directory / artifact)}
            self("phase_completed", phase_seconds=time.monotonic() - began, **evidence)
            return result
        except BaseException as exc:
            self("phase_failed", error=str(exc), phase_seconds=time.monotonic() - began)
            raise


def evidence_root(root, registration):
    return Path(registration.get("reused_simulations", {}).get("path", root))


def cells_root(root, registration):
    if "refinement" in registration:
        return Path(registration["refinement"]["simulation_parent"])
    return evidence_root(root, registration)


def native_controls(registration):
    index = registration.get("native_index", 0)
    u.need(type(index) is int and index in (0, 1, 2, 3), "Supported 100-ms native timestep index")
    if index == 3:
        from pickle_buffers import MODE

        u.need(
            registration.get("checkpoint_mode") == MODE
            and registration.get("native_parallel") is False
            and isinstance(registration.get("memory_qualification"), dict)
            and {"path", "completion_sha256", "registration_sha256", "result_sha256"}
            <= registration["memory_qualification"].keys(),
            "Finer native clock requires the qualified writer, receipt and serial captures",
        )
        dt = u.RANGES["pump_leak"][2] / 2
    else:
        dt = u.RANGES["pump_leak"][index]
    count = round(DURATION / dt)
    u.need(
        registration["native_dt_s"] == dt and registration["max_native_labels"] == count,
        "Registered native clock changed",
    )
    return index, dt, count


def prefix_input(registration):
    value = registration.get("native_prefix")
    if value is not None:
        return Path(value["path"]), value["completion_sha256"]
    return (
        Path(registration["parent"]) / "native/pump_leak/0",
        registration["parent_coarse_completion_sha256"],
    )


def authenticate_files(root, expected):
    for name, digest in expected.items():
        path = root / name
        u.need(
            not Path(name).is_absolute()
            and ".." not in Path(name).parts
            and path.resolve().is_relative_to(root.resolve())
            and not path.is_symlink(),
            "Unsafe pilot artifact: " + name,
        )
        u.need(u.sha(path) == digest, "Completed pilot artifact changed: " + name)


def authenticate_simulations(root, phases=SIMULATIONS):
    receipts, count = {}, 0
    for phase in phases:
        directory = root / phase
        stage = u.read(directory / "completion.json")
        u.need(stage["status"] == "completed", "Incomplete pilot phase: " + phase)
        authenticate_files(directory, stage["files_sha256"])
        # Require all saved artifacts, including the phase result, to be bound.
        names = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
        u.need(
            "result.json" in stage["files_sha256"]
            and names == set(stage["files_sha256"]) | {"completion.json"},
            "Pilot phase inventory changed: " + phase,
        )
        receipts[phase] = u.sha(directory / "completion.json")
        count += len(stage["files_sha256"])
    return {"phase_completions_sha256": receipts, "artifacts_verified": count}


def reuse_inputs(parent):
    """Authenticate completed simulations from a terminal pilot, without rewriting it."""
    u.need(parent.is_dir() and not parent.is_symlink(), "Saved pilot directory")
    old = u.read(parent / "registration.json")
    u.need(
        old["protocol"] == make_plan(u.plan()) and old["native_dt_s"] == DT,
        "Saved pilot scientific contract changed",
    )
    u.need("reused_simulations" not in old, "Reuse the original simulation pilot")
    terminal = [name for name in ("failure.json", "completion.json") if (parent / name).is_file()]
    u.need(len(terminal) == 1, "Require one terminal pilot receipt before reuse")
    u.need(u.sources(parent / "source") == old["sources_sha256"], "Saved pilot source changed")
    authenticate_files(parent, old["inputs_sha256"])
    for path, expected in (
        (Path(old["parent"]) / "completion.json", old["parent_completion_sha256"]),
        (
            Path(old["parent"]) / "native/pump_leak/0/completion.json",
            old["parent_coarse_completion_sha256"],
        ),
        (Path(old["reference_parent"]) / "completion.json", old["reference_completion_sha256"]),
    ):
        u.need(u.sha(path) == expected, "Saved pilot upstream receipt changed")
    _, references = inputs(Path(old["parent"]), Path(old["reference_parent"]))
    u.need(
        {name: u.sha(path) for name, path in references.items()}
        == {name: value["sha256"] for name, value in old["references"].items()},
        "Saved pilot reference selection changed",
    )
    receipt = dict(
        path=str(parent),
        registration_sha256=u.sha(parent / "registration.json"),
        terminal_receipt=terminal[0],
        terminal_sha256=u.sha(parent / terminal[0]),
        **authenticate_simulations(parent),
    )
    return old, receipt


def unchanged_production(old, hashes):
    def selected(values):
        return {k: v for k, v in values.items() if k.startswith(("src/", "configs/"))}

    u.need(selected(old["sources_sha256"]) == selected(hashes), "Reused production source changed")


def refinement_inputs(parent, *, expected_index=None):
    """Authenticate a completed refinement and its decreasing, bounded parent chain."""
    r, done, result = (
        u.read(parent / name) for name in ("registration.json", "completion.json", "result.json")
    )
    u.need(
        done["status"] == result["status"] == "long_pump_pilot_completed"
        and done["registration_sha256"] == u.sha(parent / "registration.json")
        and done["result_sha256"] == u.sha(parent / "result.json"),
        "Completed refinement receipt changed",
    )
    index, dt, count = native_controls(r)
    u.need(expected_index is None or index == expected_index, "Refinement parent clock index")
    u.need(
        result["native_dt_s"] == dt
        and result["native_steps_per_run"] == count
        and result["duration_s"] == DURATION
        and result["failed_numeric_limits"] in ([], ["native/energy_closure"]),
        "Require a completed native refinement without other numerical failures",
    )
    u.need(u.sources(parent / "source") == r["sources_sha256"], "Refinement source changed")
    authenticate_files(parent, r["inputs_sha256"])
    if index == 0:
        u.need("refinement" not in r, "Coarse review cannot have a refinement parent")
        original, receipt = reuse_inputs(evidence_root(parent, r))
        u.need(receipt == r["reused_simulations"], "Coarse simulation provenance changed")
        review = authenticate_simulations(parent, ("compare",))
        expected_phases = receipt["phase_completions_sha256"] | review["phase_completions_sha256"]
    else:
        u.need("reused_simulations" not in r, "Refinement must bind its own native captures")
        original, _, prior = refinement_inputs(
            Path(r["refinement"]["path"]), expected_index=index - 1
        )
        u.need(prior == r["refinement"], "Refinement ancestor receipt changed")
        receipt = prior["simulation_receipt"]
        review = authenticate_simulations(parent, ("observed", "unobserved", "compare"))
        expected_phases = {
            "cells": receipt["phase_completions_sha256"]["cells"],
            **review["phase_completions_sha256"],
        }
        prefix, prefix_sha = prefix_input(r)
        expected_prefix = Path(original["parent"]) / f"native/pump_leak/{index}"
        if index == 3:
            import memory_refinement

            memory_reg, _, memory_receipt = memory_refinement.authenticate(
                Path(r["memory_qualification"]["path"]), Path(r["refinement"]["path"])
            )
            u.need(memory_receipt == r["memory_qualification"], "Memory qualification changed")
            memory_refinement.compatible_sources(memory_reg, r["sources_sha256"])
            expected_prefix = Path(memory_receipt["path"]) / "observed"
        u.need(
            prefix == expected_prefix and u.authenticate_stage(prefix) == prefix_sha,
            "Refinement prefix provenance changed",
        )
    u.need(
        result["phase_completions_sha256"] == expected_phases,
        "Refinement phase receipts changed",
    )
    comparison = u.read(parent / "compare/comparison.json")
    if "regression_tests" in r:
        software = authenticate_simulations(parent, ("regression",))
        u.need(
            result["regression"]
            == {
                "completion_sha256": software["phase_completions_sha256"]["regression"],
                **u.read(parent / "regression/result.json"),
            },
            "Refinement regression receipt changed",
        )
    u.need(
        comparison == u.read(parent / "compare/result.json")
        and all(result[k] == v for k, v in comparison.items()),
        "Refinement verdict changed",
    )
    u.need(
        r["protocol"] == original["protocol"] == make_plan(u.plan())
        and r["inputs_sha256"] == original["inputs_sha256"]
        and r["runtimes"] == original["runtimes"],
        "Refinement scientific contract changed",
    )
    unchanged_production(original, r["sources_sha256"])
    return (
        original,
        result,
        {
            "path": str(parent),
            "completion_sha256": u.sha(parent / "completion.json"),
            "registration_sha256": u.sha(parent / "registration.json"),
            "result_sha256": u.sha(parent / "result.json"),
            "simulation_parent": receipt["path"],
            "simulation_receipt": receipt,
        },
    )


def refinement_preflight(original, result, receipt, *, available_memory, free_disk):
    """Project the next level from measured costs; serialize captures when necessary."""
    u.need(original["native_dt_s"] == DT, "Preflight baseline timestep changed")
    parent = Path(receipt["path"])
    registration = u.read(parent / "registration.json")
    index, old_dt, _ = native_controls(registration)
    index += 1
    u.need(index <= 2, "Refinement needs a new resource/prefix qualification beyond 256000 steps")
    dt = u.RANGES["pump_leak"][index]
    u.need(result["native_dt_s"] == old_dt and old_dt == 2 * dt, "Refinement projection clock")
    factor = old_dt / dt
    stream_limit = STREAM_BYTES * 2 ** (index - 1)
    artifact_limit = ARTIFACT_BYTES * 2 ** (index - 1)
    source = evidence_root(parent, registration)
    rows = {}
    for phase in ("observed", "unobserved"):
        directory = source / phase
        files = [p for p in directory.rglob("*") if p.is_file()]
        sizes = [p.stat().st_size for p in files]
        stream_bytes = sum(p.stat().st_size for p in (directory / "capture/stream").iterdir())
        rows[phase] = {
            "projected_artifact_bytes": math.ceil(sum(sizes) * factor * 1.5),
            "projected_largest_file_bytes": math.ceil(max(sizes) * factor * 1.5),
            "projected_stream_bytes": math.ceil(stream_bytes * factor * 1.5),
            "projected_peak_rss_bytes": math.ceil(
                result["phase_resources"][phase]["peak_rss_bytes"] * factor * 1.3
            ),
        }
        u.need(
            rows[phase]["projected_largest_file_bytes"] <= stream_limit
            and rows[phase]["projected_stream_bytes"] <= stream_limit,
            "Refinement exceeds registered file/stream allowance",
        )
    review_peak = math.ceil(result["phase_resources"]["compare"]["peak_rss_bytes"] * factor * 1.3)
    parallel_peak = sum(v["projected_peak_rss_bytes"] for v in rows.values())
    parallel = available_memory >= parallel_peak + 4 * 1024**3
    memory = max(
        review_peak,
        parallel_peak if parallel else max(v["projected_peak_rss_bytes"] for v in rows.values()),
    )
    output = sum(v["projected_artifact_bytes"] for v in rows.values()) + 128 * 1024**2
    u.need(
        max(review_peak, *(v["projected_peak_rss_bytes"] for v in rows.values())) <= 16 * 1024**3,
        "Refinement process memory allowance",
    )
    u.need(available_memory >= memory + 4 * 1024**3, "Refinement available-memory reserve")
    u.need(output <= artifact_limit, "Refinement total artifact allowance")
    u.need(free_disk >= artifact_limit + 4 * 1024**3, "Refinement disk reserve")
    capture_seconds = [result["phase_resources"][p]["elapsed_seconds"] for p in rows]
    return {
        "status": "refinement_resources_fit",
        "native_index": index,
        "dt_s": dt,
        "steps": round(DURATION / dt),
        "native_parallel": parallel,
        "native_stream_bytes": stream_limit,
        "artifact_bytes": artifact_limit,
        "process_address_space_bytes": 16 * 1024**3,
        "native_cost_source": str(source),
        "step_count_factor": factor,
        "artifact_headroom_multiplier": 1.5,
        "memory_headroom_multiplier": 1.3,
        "phases": rows,
        "projected_review_peak_rss_bytes": review_peak,
        "projected_parallel_native_peak_rss_bytes": parallel_peak,
        "projected_concurrent_peak_rss_bytes": memory,
        "projected_artifact_bytes": output,
        "available_memory_bytes": available_memory,
        "free_disk_bytes": free_disk,
        "memory_reserve_bytes": 4 * 1024**3,
        "disk_reserve_bytes": 4 * 1024**3,
        "projected_seconds": factor
        * (
            (max(capture_seconds) if parallel else sum(capture_seconds))
            + result["phase_resources"]["compare"]["elapsed_seconds"]
        ),
        "scientific_tolerances_changed": False,
        "native_histories_retained": True,
        "native_memory_bounded": False,
    }


def adjacent_refinement(current, previous, plan):
    """One adjacent pair reports contraction; the three-level qualification stays open."""
    u.need(
        current["duration_s"] == previous["duration_s"] == DURATION
        and current["native_dt_s"] * 2 == previous["native_dt_s"],
        "Refinement clock pair",
    )
    checks = {}
    for field, floor_name in (
        ("amount", "floor_amount_fmol"),
        ("energy", "floor_energy_pJ"),
        ("voltage", "floor_voltage_V"),
    ):
        old = previous["constraints"]["native/" + field]["max_error"]
        new = current["constraints"]["native/" + field]["max_error"]
        floor, ratio = plan["refinement"][floor_name], plan["refinement"]["contraction_max"]
        checks[field] = {
            "coarse_error": old,
            "fine_error": new,
            "floor": floor,
            "contraction_max": ratio,
            "passed": old <= floor or new <= ratio * old,
            "observed_ratio": new / old if old else None,
        }
    old = previous["constraints"]["native/energy_closure"]["max_error"]
    new = current["constraints"]["native/energy_closure"]["max_error"]
    return {
        "levels": 2,
        "dt_s": [previous["native_dt_s"], current["native_dt_s"]],
        "trajectory_contraction": checks,
        "adjacent_trajectory_contraction_pass": all(v["passed"] for v in checks.values()),
        "energy_closure": {
            "coarse_pJ": old,
            "fine_pJ": new,
            "observed_ratio": new / old if old else None,
            "observed_order": math.log2(old / new) if min(old, new) > 0 else None,
            "unchanged_limit_pJ": plan["accounting"]["native_finest_energy_pJ"],
            "fine_within_limit": not current["constraints"]["native/energy_closure"]["failures"],
        },
        "timestep_ladder_qualified": False,
        "required_successive_contractions": 2,
        "available_successive_contractions": 1,
        "scientific_tolerances_changed": False,
    }


def refinement_ladder(current, previous, plan):
    """Keep measured pairs; qualification needs two contractions and all finest limits."""
    prior = previous.get("refinement_ladder")
    if prior is not None:
        pairs = copy.deepcopy(prior["pairs"])
    elif "adjacent_refinement" in previous:
        pairs = [copy.deepcopy(previous["adjacent_refinement"])]
    else:
        pairs = []
    pairs.append(adjacent_refinement(current, previous, plan))
    for left, right in zip(pairs, pairs[1:], strict=False):
        u.need(left["dt_s"][-1] == right["dt_s"][0], "Nonconsecutive refinement ladder")
    consecutive = 0
    for pair in reversed(pairs):
        if not pair["adjacent_trajectory_contraction_pass"]:
            break
        consecutive += 1
    passed = not current["failed_numeric_limits"]
    return {
        "duration_s": DURATION,
        "levels": len(pairs) + 1,
        "dt_s": [pairs[0]["dt_s"][0]] + [pair["dt_s"][-1] for pair in pairs],
        "pairs": pairs,
        "required_successive_contractions": 2,
        "available_successive_contractions": len(pairs),
        "passing_successive_contractions": consecutive,
        "finest_meets_numeric_limits": passed,
        "timestep_ladder_qualified": consecutive >= 2 and passed,
        "scientific_tolerances_changed": False,
    }


def make_plan(original):
    plan = copy.deepcopy(original)
    plan.update(
        schema="cells.long_pump_timestep_pilot@1",
        scope=("One 100-ms pump/leak timestep; no ladder, recovery or stationarity claim"),
        duration_s=DURATION,
        common_times_s=[i / 1000 for i in range(101)],
        restart_time_s=0.05,
        variants=["pump_leak"],
        cells_trajectories=3,
        restart_suffixes=1,
        reference_solves=0,
    )
    plan["resources"].update(max_cells_steps=8192, max_cells_trace_bytes=CELLS_TRACE_BYTES)
    return plan


def cell_spec(plan, preparation, dt):
    from cells.core.specs import parse_spec

    u.module_path("pump_matched_pilot")
    import pilot_context

    case = dict(preparation["cases"]["pump_leak"], end_time_s=plan["duration_s"])
    raw = pilot_context.definition(case, dt, times=plan["common_times_s"])
    raw["execution"].update(
        max_steps=plan["resources"]["max_cells_steps"],
        max_trace_bytes=plan["resources"]["max_cells_trace_bytes"],
    )
    return parse_spec(raw)


def cell_preflight(plan, preparation):
    """Check every actual production grid before any trajectory or native run."""
    from cells.core.resources import trace_bytes
    from cells.core.runner import timeline
    from cells.core.specs import digest

    rows = []
    for dt in plan["cells_steps_s"]:
        spec = cell_spec(plan, preparation, dt)
        grid = timeline(spec)
        restart = dt == plan["restart_step_s"]
        if restart:
            u.need(plan["restart_time_s"] in grid, "Restart must lie on the production grid")
        rows.append(
            {
                "dt_s": dt,
                "steps": len(grid) - 1,
                "estimated_trace_bytes": trace_bytes(spec, len(grid) - 1),
                "max_trace_bytes": spec.execution.max_trace_bytes,
                "spec_sha256": digest(spec.to_dict()),
                "restart_grid_checked": restart,
            }
        )
    return {"status": "all_cells_grids_preflight_pass", "rows": rows}


def recording_limits(registration):
    stream = registration.get("native_stream_bytes", STREAM_BYTES)
    total = registration.get("artifact_bytes", ARTIFACT_BYTES)
    multiplier = 2
    if registration.get("native_index") == 3:
        native_controls(registration)
        multiplier = 4
    u.need(
        type(stream) is int and STREAM_BYTES <= stream <= multiplier * STREAM_BYTES,
        "Registered pilot file/stream allowance",
    )
    u.need(
        type(total) is int and ARTIFACT_BYTES <= total <= multiplier * ARTIFACT_BYTES,
        "Registered pilot artifact allowance",
    )
    return stream, total


def budget(root):
    registration = root / "registration.json"
    stream, total = recording_limits(u.read(registration) if registration.exists() else {})
    sizes = [p.stat().st_size for p in root.rglob("*") if p.is_file()]
    u.need(sum(sizes) <= total, "Pilot exceeded its registered artifact allowance")
    u.need(max(sizes, default=0) <= stream, "Pilot exceeded its registered per-file allowance")
    u.need(shutil.disk_usage(root).free >= 4 * 1024**3, "Pilot 4 GiB disk reserve")
    return sum(sizes)


def inputs(parent, references):
    done, reg = (u.read(parent / name) for name in ("completion.json", "registration.json"))
    u.need(done["status"] == "fresh_10ms_numerical_review_pass", "Require completed 10-ms parent")
    u.need(
        done["registration_sha256"] == u.sha(parent / "registration.json"), "Parent registration"
    )
    u.need(
        done["comparison_sha256"] == u.sha(parent / "conclusion/comparison.json"), "Parent result"
    )
    u.authenticate_stage(parent / "prepare")
    u.authenticate_stage(parent / "native/pump_leak/0")
    completed = u.read(references / "completion.json")
    report = u.read(references / "result.json")
    reference_reg = u.read(references / "registration.json")
    u.need(
        completed["status"] == report["status"] == "reference_residual_study_pass"
        and completed["result_sha256"] == u.sha(references / "result.json")
        and report["registration_sha256"] == u.sha(references / "registration.json"),
        "Require authenticated longer references",
    )
    u.need(
        reference_reg["parent_completion_sha256"] == u.sha(parent / "completion.json")
        and reference_reg["parent_preparation_sha256"]
        == u.sha(parent / "prepare/preparation.json"),
        "Longer references use a different preparation",
    )
    paths = {}
    for i, row in enumerate(reference_reg["rows"]):
        if row["case"] != "pump_leak" or row["duration_s"] != DURATION:
            continue
        record = report["rows"][i]
        directory = references / "rows" / str(i)
        u.need(
            record["status"] == "passed"
            and record["result_sha256"] == u.sha(directory / "result.json"),
            "Reference row receipt",
        )
        result = u.read(directory / "result.json")
        u.need(
            result["trajectory_sha256"] == u.sha(directory / "trajectory.json"),
            "Reference trajectory",
        )
        paths[row["setting"]["id"]] = directory / "trajectory.json"
    u.need(set(paths) == {"dop853_base", "dop853_tight", "radau_check"}, "Reference coverage")
    return reg, paths


def cells(root, registration, directory):
    import numpy as np

    from cells.core.runner import run
    from cells.io import load_snapshot, write_run

    u.module_path("pump_matched_pilot")
    import pilot_context
    from pilot_math import canonical

    plan = registration["protocol"]
    preparation = u.read(root / "preparation.json")
    u.need(
        cell_preflight(plan, preparation) == registration["cells_preflight"],
        "Frozen production preflight changed",
    )
    rows = []
    for index, dt in enumerate(plan["cells_steps_s"]):
        result = run(cell_spec(plan, preparation, dt))
        output = directory / str(index)
        times = (plan["restart_time_s"],) if dt == plan["restart_step_s"] else ()
        write_run(output, result, checkpoint_times=times)
        values = vars(result.observations)
        row = {
            "dt_s": dt,
            "times_s": values["times"].tolist(),
            "states": [
                canonical(
                    {k: np.asarray(values[k])[i].tolist() for k in pilot_context.STATE_FIELDS}
                )
                for i in range(len(values["times"]))
            ],
            "voltage_V": values["voltage_V"][:, :7].tolist(),
            "diagnostics": result.diagnostics,
            "timings": result.timings,
            "disk_restart_exact": None,
        }
        if times:
            checkpoint = result.checkpoint_at(times[0])
            saved = load_snapshot(output / f"snapshots/step-{checkpoint.step_index:06d}")
            resumed = run(saved.spec, saved.checkpoint)
            write_run(output / "resumed", resumed)
            for full, suffix in zip(result.history, resumed.history, strict=True):
                np.testing.assert_array_equal(full[checkpoint.step_index :], suffix)
            row["disk_restart_exact"] = True
        rows.append(row)
        print(f"Cells 100-ms trajectory captured at {dt:g} s", flush=True)
    return {"rows": rows, "trajectories": 3, "exact_disk_restarts": 1}


def reader(saved, native_read, *, streamed=True, progress=None, stream_bytes=STREAM_BYTES):
    # The qualified independent decoder still checks every field/hash/sequence.
    # Only the registered aggregate byte allowance changes in a private instance.
    wire = u.private("_long_pump_wire", Path(saved.c.wire.__file__))
    u.need(wire.STREAM_BYTES == 32 * 1024**2 and wire.CHUNK_BYTES == 8 * 1024**2, "Reader defaults")
    u.need(
        type(stream_bytes) is int and STREAM_BYTES <= stream_bytes <= 4 * STREAM_BYTES,
        "Registered reader stream allowance",
    )
    wire.STREAM_BYTES = stream_bytes
    result = u.private("_long_pump_reader", Path(native_read.__file__))
    result.ctx = SimpleNamespace(**(vars(result.ctx) | {"reader": lambda: wire.Stream}))
    if streamed:
        module = u.private("_long_pump_streamed", Path(__file__).with_name("streamed_review.py"))
        result.read = lambda directory: module.read(
            directory, result, wire.Stream, progress=progress
        )
    return result


def compare(root, registration, directory, *, progress=None):
    import fresh_review

    saved, native_read, clocks = fresh_review.modules()
    progress = progress or Progress(directory)
    stream_bytes, _ = recording_limits(registration)
    decoder = reader(saved, native_read, progress=progress, stream_bytes=stream_bytes)
    data = evidence_root(root, registration)
    _, dt, count = native_controls(registration)
    plan = registration["protocol"]
    preparation = u.read(root / "preparation.json")
    baseline = preparation["rows"]["pump_leak/observed"]
    variant = next(
        v
        for v in preparation["native_preparation"]["protocol"]["variants"]
        if v["id"] == "pump_leak"
    )
    with saved.e.model_fence():
        row, format_check = progress.run(
            "native_format", lambda: decoder.read(data / "observed/capture/stream")
        )
        u.write(directory / "format-check.json", format_check)
        progress.run(
            "native_identity",
            lambda: saved.native_records.identity(row, baseline, dt, DURATION, "observed"),
        )
        ledger = saved.e.Ledger()
        physical = progress.run(
            "native_physics",
            lambda: clocks.inspect(
                saved.native_records,
                saved.c.exact.Exact,
                row,
                baseline,
                plan,
                variant,
                ledger,
                max_count=count,
                progress=progress,
            ),
            artifact="physical-check.json",
        )
        points = progress.run(
            "native_energy",
            lambda: saved.native_energy.reconstruct(
                row, variant, plan["common_times_s"], ledger, progress=progress
            ),
            artifact="native-points.json",
        )
        targets = {
            name: saved.d.sample(
                u.read(root / "references" / f"{name}.json"), plan["common_times_s"]
            )
            for name in registration["references"]
        }
        primary = targets[plan["reference"]["primary"]]
        constraints = {
            "native/" + k: v for k, v in saved.state_checks(points, primary, plan).items()
        }
        constraints["native/energy_closure"] = saved.d.discrepancy(
            points["energy"]["max_defect_pJ"], 0.0, plan["accounting"]["native_finest_energy_pJ"]
        )
        pair = progress.run(
            "observer_neutrality",
            lambda: decoder.pair(
                data / "observed/capture/stream",
                data / "unobserved/capture/stream",
                progress=progress,
            ),
            artifact="observer-pair.json",
        )
        prefix_directory, prefix_sha = prefix_input(registration)
        u.need(
            u.sha(prefix_directory / "completion.json") == prefix_sha,
            "Parent prefix receipt changed",
        )
        u.authenticate_stage(prefix_directory)
        # Do not hold both the entire 100-ms histories and the 10-ms histories.
        # All full-run identity, physics and energy checks have finished above.
        from streamed_review import prefix_window

        window = prefix_window(row, round(0.01 / dt))
        row = None
        gc.collect()
        progress("full_histories_released_before_prefix", prefix_steps=round(0.01 / dt))
        native_read_original = reader(saved, native_read, progress=progress)
        short, _ = progress.run(
            "prefix_format",
            lambda: native_read_original.read(prefix_directory / "capture/stream"),
        )
        prefix = progress.run(
            "physical_prefix",
            lambda: fresh_review.prefix(
                window, short, saved.c.exact, duration_s=0.01, progress=progress
            ),
            artifact="prefix-check.json",
        )
        progress.phase = "numeric_comparisons"
        progress("phase_started")
        cell_rows = u.read(cells_root(root, registration) / "cells/result.json")["rows"]
        for i, local in enumerate(cell_rows):
            for method, target in targets.items():
                constraints.update(
                    {
                        f"cells/{i}/{method}/{k}": v
                        for k, v in saved.state_checks(local, target, plan, cells=True).items()
                    }
                )
            for key, names in {
                "cells_material_fmol": (
                    "max_balance_error_fmol",
                    "max_extracellular_balance_error_fmol",
                    "max_global_balance_error_fmol",
                ),
                "cells_charge_C": ("max_countercharge_error_C",),
                "cells_energy_pJ": ("max_energy_balance_error_pJ",),
            }.items():
                constraints[f"cells/{i}/{key}"] = saved.d.discrepancy(
                    [local["diagnostics"][n] for n in names],
                    [0.0] * len(names),
                    plan["accounting"][key],
                )
        constraints.update(
            {
                "cross/" + k: v
                for k, v in saved.state_checks(points, cell_rows[-1], plan, cross=True).items()
            }
        )
    failed = [k for k, v in constraints.items() if v["failures"]]
    result = {
        "status": "long_pump_pilot_completed",
        "duration_s": DURATION,
        "native_dt_s": dt,
        "native_steps_per_run": count,
        "native_runs": 2,
        "cells_trajectories": 3,
        "exact_disk_restarts": 1,
        "constraints": constraints,
        "failed_numeric_limits": failed,
        "candidate_meets_numeric_limits": not failed,
        "physical": physical,
        "format_check": format_check,
        "observer_pair": pair,
        "physical_prefix": prefix,
        "independent_comparisons": ledger.count,
        "independent_maxima": ledger.maxima,
        "timestep_ladder_qualified": False,
        "steady_state_qualified": False,
        "recovery_qualified": False,
        "full_betse_parity": False,
        "scientific_tolerances_changed": False,
    }
    if "refinement" in registration:
        previous = u.read(Path(registration["refinement"]["path"]) / "result.json")
        result["adjacent_refinement"] = adjacent_refinement(result, previous, plan)
        result["refinement_ladder"] = refinement_ladder(result, previous, plan)
        result["timestep_ladder_qualified"] = result["refinement_ladder"][
            "timestep_ladder_qualified"
        ]
    # Native candidate accuracy misses are the pilot's output. A Cells accuracy
    # regression remains a failure and cannot be relabelled as a native diagnostic.
    u.write(directory / "comparison.json", result)
    u.need(not any(k.startswith("cells/") for k in failed), "Cells 100-ms comparison failed")
    progress(
        "phase_completed", artifact="comparison.json", sha256=u.sha(directory / "comparison.json")
    )
    return result


def worker(root, phase):
    r = u.read(root / "registration.json")
    directory = root / phase
    directory.mkdir()
    began = time.monotonic()
    u.write(directory / "started.json", {"pid": os.getpid(), "utc": u.utc()})
    progress = Progress(directory) if phase == "compare" else None
    try:
        u.need(u.sources() == r["sources_sha256"], "Frozen pilot source changed")
        interpreter = "betse" if phase in ("observed", "unobserved") else "cpu"
        u.need(u.runtime() == r["runtimes"][interpreter], "Frozen pilot runtime changed")
        for name, digest in r["inputs_sha256"].items():
            u.need(u.sha(root / name) == digest, "Frozen pilot input changed: " + name)
        stream_bytes, _ = recording_limits(r)
        resource.setrlimit(resource.RLIMIT_AS, (16 * 1024**3,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (stream_bytes,) * 2)
        if "memory_qualification" in r:
            import memory_refinement

            memory_reg, _, memory_receipt = memory_refinement.authenticate(
                Path(r["memory_qualification"]["path"]), Path(r["refinement"]["path"])
            )
            u.need(memory_receipt == r["memory_qualification"], "Memory qualification changed")
            memory_refinement.compatible_sources(memory_reg, r["sources_sha256"])
        if phase in ("observed", "unobserved"):
            import prepare

            index, dt, count = native_controls(r)
            result = prepare.capture(
                directory / "capture",
                Path(r["workspace"]),
                u.read(root / "preparation.json"),
                "pump_leak",
                index if index < 3 else None,
                phase,
                DURATION,
                stream_bytes=stream_bytes,
                **({"dt_s": dt, "checkpoint_mode": r["checkpoint_mode"]} if index == 3 else {}),
            )
            u.need(result["steps"] == count, "Pilot native step count")
        elif phase == "cells":
            result = cells(root, r, directory)
        elif phase == "regression":
            import memory_refinement

            result = memory_refinement.regression(root, r, directory)
        else:

            def authenticate():
                if "refinement" in r:
                    old, _, receipt = refinement_inputs(Path(r["refinement"]["path"]))
                    u.need(receipt == r["refinement"], "Refinement parent receipt changed")
                    u.need(
                        old["protocol"] == r["protocol"]
                        and old["inputs_sha256"] == r["inputs_sha256"],
                        "Refinement science/inputs changed",
                    )
                    unchanged_production(old, r["sources_sha256"])
                    u.need(old["runtimes"] == r["runtimes"], "Refinement runtime changed")
                    native = authenticate_simulations(root, ("observed", "unobserved"))
                    return {"coarse_parent": receipt, "new_native": native}
                if "reused_simulations" in r:
                    old, receipt = reuse_inputs(evidence_root(root, r))
                    u.need(receipt == r["reused_simulations"], "Reused simulation receipt changed")
                    u.need(
                        old["protocol"] == r["protocol"]
                        and old["inputs_sha256"] == r["inputs_sha256"],
                        "Reused science/inputs changed",
                    )
                    unchanged_production(old, r["sources_sha256"])
                    u.need(
                        old["runtimes"]["cpu"] == r["runtimes"]["cpu"], "Reused CPU runtime changed"
                    )
                    return receipt
                return authenticate_simulations(root)

            progress.run("authenticate_simulations", authenticate, artifact="input-check.json")
            result = compare(root, r, directory, progress=progress)
        u.write(directory / "result.json", result)
        u.write(
            directory / "completion.json",
            {
                "status": "completed",
                "elapsed_seconds": time.monotonic() - began,
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                "files_sha256": u.inventory(directory),
            },
        )
    except BaseException as exc:
        u.write(
            directory / "failure.json",
            {
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "utc": u.utc(),
                "review_phase": progress.phase if progress is not None else None,
            },
        )
        raise


def available_memory():
    return next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )


def phase_resource_check(root, registration, phases):
    """Recheck the measured memory/disk reserve before each scheduled large allocation."""
    preflight = registration.get("resource_preflight")
    if preflight is None:
        return
    memory = sum(
        preflight["projected_review_peak_rss_bytes"]
        if phase == "compare"
        else preflight["phases"][phase]["projected_peak_rss_bytes"]
        for phase in phases
    )
    output = sum(
        preflight.get("projected_review_artifact_bytes", 128 * 1024**2)
        if phase == "compare"
        else preflight["phases"][phase]["projected_artifact_bytes"]
        for phase in phases
    )
    available, free = available_memory(), shutil.disk_usage(root).free
    passed = (
        available >= memory + preflight["memory_reserve_bytes"]
        and free >= output + preflight["disk_reserve_bytes"]
    )
    u.write(
        root / ("-".join(phases) + "-resource-check.json"),
        dict(
            passed=passed,
            phases=list(phases),
            available_memory_bytes=available,
            free_disk_bytes=free,
            projected_peak_rss_bytes=memory,
            projected_artifact_bytes=output,
            memory_reserve_bytes=preflight["memory_reserve_bytes"],
            disk_reserve_bytes=preflight["disk_reserve_bytes"],
            utc=u.utc(),
        ),
    )
    u.need(passed, "Refinement phase memory/disk reserve; see saved resource check")


def controller(root):
    r = u.read(root / "registration.json")
    began = time.monotonic()
    u.write(root / "started.json", {"pid": os.getpid(), "utc": u.utc()})

    def execute(phase, core):
        workspace = Path(r["workspace"])
        environment = u.env(workspace, workspace / "cache" / root.name / phase)
        interpreter = "betse" if phase in ("observed", "unobserved") else "cpu"
        with (
            (root / f"{phase}.stdout.log").open("x") as out,
            (root / f"{phase}.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    "taskset",
                    "-c",
                    str(core),
                    str(workspace / f"venv-{interpreter}/bin/python"),
                    "-B",
                    str(Path(__file__).resolve()),
                    "_worker",
                    str(root),
                    phase,
                ],
                env=environment,
                stdout=out,
                stderr=err,
                stdin=subprocess.DEVNULL,
                timeout=r["phase_limits_seconds"][phase],
                check=True,
            )
        lines = (root / f"{phase}.stderr.log").read_text().splitlines()
        u.need(
            all(
                line == "[pilot.py] Ignoring cutting event, as cut profiles are disabled."
                for line in lines
            )
            if interpreter == "betse"
            else not lines,
            "Unexpected pilot stderr; see saved log",
        )
        budget(root)

    try:
        if "regression_tests" in r:
            execute("regression", 4)
        if "reused_simulations" not in r:
            if "refinement" not in r:
                execute("cells", 4)
            if r.get("native_parallel", True):
                phase_resource_check(root, r, ("observed", "unobserved"))
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [
                        pool.submit(execute, phase, core)
                        for phase, core in (("observed", 4), ("unobserved", 5))
                    ]
                    for future in futures:
                        future.result()
            else:
                for phase, core in (("observed", 4), ("unobserved", 5)):
                    phase_resource_check(root, r, (phase,))
                    execute(phase, core)
        phase_resource_check(root, r, ("compare",))
        execute("compare", 4)
        result = u.read(root / "compare/result.json")
        data = evidence_root(root, r)

        def phase_path(phase):
            if phase == "cells":
                return cells_root(root, r) / phase
            return (root if phase == "compare" else data) / phase

        result.update(
            elapsed_seconds=time.monotonic() - began,
            finished_utc=u.utc(),
            artifact_bytes=budget(root),
            phase_resources={
                phase: {
                    k: u.read(phase_path(phase) / "completion.json")[k]
                    for k in ("elapsed_seconds", "peak_rss_bytes")
                }
                for phase in PHASE_SECONDS
            },
            phase_completions_sha256={
                phase: u.sha(phase_path(phase) / "completion.json") for phase in PHASE_SECONDS
            },
            automatic_followup=False,
        )
        if "reused_simulations" in r:
            result.update(
                reused_simulations=r["reused_simulations"],
                new_native_runs=0,
                new_cells_trajectories=0,
                new_reference_solves=0,
            )
        if "refinement" in r:
            result.update(
                refinement=r["refinement"],
                new_native_runs=2,
                new_cells_trajectories=0,
                new_reference_solves=0,
            )
        if "regression_tests" in r:
            result["regression"] = {
                "completion_sha256": u.sha(root / "regression/completion.json"),
                **u.read(root / "regression/result.json"),
            }
        u.write(root / "result.json", result)
        u.write(
            root / "completion.json",
            {
                "status": result["status"],
                "result_sha256": u.sha(root / "result.json"),
                "registration_sha256": u.sha(root / "registration.json"),
                "utc": u.utc(),
            },
        )
    except BaseException as exc:
        last_progress = None
        journal = root / "compare/review-progress.jsonl"
        if journal.exists():
            for line in reversed(journal.read_text().splitlines()):
                try:
                    last_progress = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        if (
            isinstance(exc, subprocess.TimeoutExpired)
            and exc.cmd[-1] == "compare"
            and not (root / "compare/failure.json").exists()
        ):
            u.write(
                root / "compare/failure.json",
                {
                    "status": "timed_out",
                    "error": str(exc),
                    "last_progress": last_progress,
                    "utc": u.utc(),
                    "automatic_retry": False,
                },
            )
        u.write(
            root / "failure.json",
            {
                "status": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "elapsed_seconds": time.monotonic() - began,
                "utc": u.utc(),
                "automatic_retry": False,
                "last_review_progress": last_progress,
            },
        )
        raise


def launch(parent, references, output, workspace):
    parent, references, output, workspace = (
        p.resolve() for p in (parent, references, output, workspace)
    )
    u.need(
        output.is_relative_to(Path("/mnt/workspaces")) and not output.exists(),
        "Require new workspace output",
    )
    original, paths = inputs(parent, references)
    # Keep production imports out of the controller/independent reviewer. This
    # short subprocess exercises all real grid/resource guards before detaching.
    preflight = json.loads(
        subprocess.check_output(
            [
                str(workspace / "venv-cpu/bin/python"),
                "-B",
                str(Path(__file__).resolve()),
                "_preflight",
                str(parent),
            ],
            text=True,
            env=u.env(workspace, workspace / "cache" / output.name / "preflight"),
            timeout=60,
        )
    )
    runtimes = {}
    for name in ("cpu", "betse"):
        runtimes[name] = json.loads(
            subprocess.check_output(
                [
                    str(workspace / f"venv-{name}/bin/python"),
                    "-B",
                    "-c",
                    "import sys,json;sys.path.insert(0,sys.argv[1]);"
                    "import common;print(json.dumps(common.runtime()))",
                    str(u.HERE),
                ],
                text=True,
            )
        )
    u.need(
        shutil.disk_usage(workspace).free >= ARTIFACT_BYTES + 4 * 1024**3,
        "Pilot output/reserve allowance",
    )
    output.mkdir(parents=True)
    hashes = u.sources()
    for name in hashes:
        destination = output / "source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    (output / "references").mkdir()
    shutil.copyfile(parent / "prepare/preparation.json", output / "preparation.json")
    for name, path in paths.items():
        shutil.copyfile(path, output / "references" / f"{name}.json")
    r = {
        "protocol": make_plan(original["protocol"]),
        "cells_preflight": preflight,
        "parent": str(parent),
        "parent_completion_sha256": u.sha(parent / "completion.json"),
        "parent_coarse_completion_sha256": u.sha(parent / "native/pump_leak/0/completion.json"),
        "reference_parent": str(references),
        "reference_completion_sha256": u.sha(references / "completion.json"),
        "references": {
            name: {"path": str(path), "sha256": u.sha(path)} for name, path in paths.items()
        },
        "inputs_sha256": {
            str(path.relative_to(output)): u.sha(path)
            for path in [output / "preparation.json", *(output / "references").glob("*.json")]
        },
        "sources_sha256": hashes,
        "runtimes": runtimes,
        "workspace": str(workspace),
        "native_dt_s": DT,
        "native_stream_bytes": STREAM_BYTES,
        "max_native_labels": 64000,
        "artifact_bytes": ARTIFACT_BYTES,
        "phase_limits_seconds": PHASE_SECONDS,
        "cpu_affinity": [4, 5],
        "timing_basis": (
            "10x saved coarse capture/review plus repeat stream reads; bare capture in parallel"
        ),
        "expected_seconds": 10800,
        "review_storage": "Reiterable authenticated step/raw-call views; histories retained",
        "scope": (
            "Diagnostic at the prior coarse timestep; refinement and recovery follow separately"
        ),
        "scientific_tolerances_changed": False,
        "automatic_followup": False,
        "created_utc": u.utc(),
    }
    u.write(output / "registration.json", r)
    return detach(output, r)


def launch_review(parent, output, workspace):
    parent, output, workspace = (p.resolve() for p in (parent, output, workspace))
    u.need(
        output.is_relative_to(Path("/mnt/workspaces")) and not output.exists(),
        "Require new workspace output",
    )
    old, receipt = reuse_inputs(parent)
    hashes = u.sources()
    unchanged_production(old, hashes)
    u.need(u.runtime() == old["runtimes"]["cpu"], "Saved CPU runtime changed")
    u.need(
        shutil.disk_usage(workspace).free >= ARTIFACT_BYTES + 4 * 1024**3,
        "Review output/reserve allowance",
    )
    output.mkdir(parents=True)
    for name in hashes:
        destination = output / "source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    for name in old["inputs_sha256"]:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(parent / name, destination)
    r = dict(old)
    r.update(
        sources_sha256=hashes,
        workspace=str(workspace),
        reused_simulations=receipt,
        phase_limits_seconds={"compare": 21600},
        cpu_affinity=[4],
        expected_seconds=7200,
        timing_basis=(
            "Short saved-trace profile identifies repeated decoder work; six history "
            "passes fused into physics. Two-hour estimate is provisional; six-hour hard cap."
        ),
        new_native_runs=0,
        new_cells_trajectories=0,
        new_reference_solves=0,
        scope="Comparison-only recovery of the saved 100-ms diagnostic; no new simulations",
        created_utc=u.utc(),
    )
    u.write(output / "registration.json", r)
    return detach(output, r)


def launch_refinement(parent, output, workspace, *, memory_qualification=None):
    parent, output, workspace = (p.resolve() for p in (parent, output, workspace))
    u.need(
        output.is_relative_to(Path("/mnt/workspaces")) and not output.exists(),
        "Require new workspace output",
    )
    original, previous, receipt = refinement_inputs(parent)
    hashes = u.sources()
    memory = None
    if memory_qualification is not None:
        import memory_refinement

        memory_reg, memory_result, memory = memory_refinement.authenticate(
            memory_qualification.resolve(), parent
        )
        # Retain the qualified production snapshot for reused Cells results;
        # only the current validation code is extended for the larger run.
        hashes = {k: v for k, v in hashes.items() if not k.startswith(("src/", "configs/"))}
        hashes.update(
            {
                k: v
                for k, v in memory_reg["sources_sha256"].items()
                if k.startswith(("src/", "configs/"))
            }
        )
        memory_refinement.compatible_sources(memory_reg, hashes)
    unchanged_production(original, hashes)
    u.need(u.runtime() == original["runtimes"]["cpu"], "Saved CPU runtime changed")
    native_runtime = json.loads(
        subprocess.check_output(
            [
                str(workspace / "venv-betse/bin/python"),
                "-B",
                "-c",
                "import sys,json;sys.path.insert(0,sys.argv[1]);"
                "import common;print(json.dumps(common.runtime()))",
                str(u.HERE),
            ],
            text=True,
            env=u.env(workspace, workspace / "cache" / output.name / "preflight"),
            timeout=30,
        )
    )
    u.need(native_runtime == original["runtimes"]["betse"], "Saved BETSE runtime changed")
    if memory is None:
        preflight = refinement_preflight(
            original,
            previous,
            receipt,
            available_memory=available_memory(),
            free_disk=shutil.disk_usage(workspace).free,
        )
    else:
        preflight = memory_refinement.preflight(
            parent,
            Path(memory["path"]),
            memory_result,
            available_memory=available_memory(),
            free_disk=shutil.disk_usage(workspace).free,
        )
    index = preflight["native_index"]
    prefix = (
        Path(original["parent"]) / f"native/pump_leak/{index}"
        if memory is None
        else Path(memory["path"]) / "observed"
    )
    prefix_sha = u.authenticate_stage(prefix)
    output.mkdir(parents=True)
    for name in hashes:
        destination = output / "source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        origin = (
            Path(memory["path"]) / "source"
            if memory is not None and name.startswith(("src/", "configs/"))
            else ROOT
        ) / name
        shutil.copyfile(origin, destination)
        u.need(u.sha(destination) == hashes[name], "Refinement source copy changed")
    for name in original["inputs_sha256"]:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(receipt["simulation_parent"]) / name, destination)
    r = dict(original)
    r.update(
        sources_sha256=hashes,
        workspace=str(workspace),
        refinement=receipt,
        native_index=index,
        native_dt_s=preflight["dt_s"],
        max_native_labels=preflight["steps"],
        native_stream_bytes=preflight["native_stream_bytes"],
        artifact_bytes=preflight["artifact_bytes"],
        native_parallel=preflight["native_parallel"],
        native_prefix={"path": str(prefix), "completion_sha256": prefix_sha},
        resource_preflight=preflight,
        phase_limits_seconds={
            "observed": 10800 * 2 ** (index - 1),
            "unobserved": 9000 * 2 ** (index - 1),
            "compare": 21600 * 2 ** (index - 1),
        },
        cpu_affinity=[4, 5],
        expected_seconds=math.ceil(preflight["projected_seconds"] * 1.2),
        timing_basis=(
            "Twice measured previous-level phase costs using the registered capture schedule, "
            "plus 20% timing headroom"
        ),
        new_native_runs=2,
        new_cells_trajectories=0,
        new_reference_solves=0,
        scope=(
            "One halved 100-ms native timestep, observed/bare pair and independent review; "
            "reuse Cells/references and retain successive measured contractions. "
            "Qualification requires two contractions and every finest numerical limit."
        ),
        created_utc=u.utc(),
    )
    if memory is not None:
        from pickle_buffers import MODE

        r.update(
            memory_qualification=memory,
            checkpoint_mode=MODE,
            production_snapshot=str(Path(memory["path"]) / "source"),
            regression_tests=memory_refinement.TEST_FILES,
            phase_limits_seconds={
                "regression": 600,
                "observed": 21600,
                "unobserved": 10800,
                "compare": 64800,
            },
            timing_basis="Ten times measured qualified 10-ms phase costs, plus 20% headroom",
        )
    native_controls(r)
    u.write(output / "registration.json", r)
    return detach(output, r)


def detach(output, r):
    workspace = Path(r["workspace"])
    with (output / "stdout.log").open("x") as out, (output / "stderr.log").open("x") as err:
        child = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(output / "source/validation/betse/long_relaxation/pilot.py"),
                "_controller",
                str(output),
            ],
            env=u.env(workspace, workspace / "cache" / output.name / "controller"),
            stdout=out,
            stderr=err,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    result = {
        "status": "launched",
        "pid": child.pid,
        "output": str(output),
        "expected_seconds": r["expected_seconds"],
        "utc": u.utc(),
    }
    u.write(output / "launch.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("launch")
    for name in ("parent", "references", "output", "workspace"):
        start.add_argument("--" + name, required=True, type=Path)
    review = commands.add_parser("review")
    for name in ("parent", "output", "workspace"):
        review.add_argument("--" + name, required=True, type=Path)
    refine = commands.add_parser("refine")
    for name in ("parent", "output", "workspace"):
        refine.add_argument("--" + name, required=True, type=Path)
    refine.add_argument("--memory-qualification", type=Path)
    check = commands.add_parser("_preflight")
    check.add_argument("parent", type=Path)
    for name in ("_controller", "_worker"):
        command = commands.add_parser(name)
        command.add_argument("output", type=Path)
        if name == "_worker":
            command.add_argument("phase", choices=(*PHASE_SECONDS, "regression"))
    args = parser.parse_args()
    if args.command == "launch":
        print(
            json.dumps(launch(args.parent, args.references, args.output, args.workspace), indent=2)
        )
    elif args.command == "review":
        print(json.dumps(launch_review(args.parent, args.output, args.workspace), indent=2))
    elif args.command == "refine":
        print(
            json.dumps(
                launch_refinement(
                    args.parent,
                    args.output,
                    args.workspace,
                    memory_qualification=args.memory_qualification,
                ),
                indent=2,
            )
        )
    elif args.command == "_preflight":
        print(
            json.dumps(
                cell_preflight(
                    make_plan(u.read(args.parent / "registration.json")["protocol"]),
                    u.read(args.parent / "prepare/preparation.json"),
                )
            )
        )
    elif args.command == "_controller":
        controller(args.output)
    else:
        worker(args.output, args.phase)


if __name__ == "__main__":
    main()
