"""Detached checkpoint-capacity and 10-ms prefix qualification, before a longer run.

Reuses the independent native laws, decoder and tolerances. A synthetic 512k
history tests storage capacity only; it never stands in for a trajectory.
"""

import argparse
import gc
import json
import os
import resource
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from itertools import zip_longest
from pathlib import Path

import pilot
from pickle_buffers import MODE

u = pilot.u
DURATION = 0.01
DT = 1.953125e-7
STEPS = 51200
CAPACITY_STEPS = 512000
PROCESS_BYTES = 16 * 1024**3
RESERVE_BYTES = 4 * 1024**3
ARTIFACT_BYTES = 6 * 1024**3
FILE_BYTES = 2 * 1024**3
PHASES = {
    "regression": 600,
    "sample": 120,
    "capacity": 3600,
    "capacity_load": 1800,
    "overlap": 1800,
    "observed": 3600,
    "unobserved": 3600,
    "checkpoints": 1800,
    "compare": 14400,
}


def runtime_for(phase):
    return "cpu" if phase in ("regression", "compare") else "betse"


def controls(registration):
    u.need(
        registration["duration_s"] == DURATION
        and registration["dt_s"] == DT
        and registration["steps"] == STEPS
        and round(DURATION / DT) == STEPS
        and registration["capacity_steps"] == CAPACITY_STEPS
        and registration["checkpoint_mode"] == MODE,
        "Memory qualification clock/storage contract changed",
    )
    u.need(registration["protocol"] == u.plan(), "Memory qualification science changed")


def budget(root):
    sizes = [p.stat().st_size for p in root.rglob("*") if p.is_file()]
    u.need(max(sizes, default=0) <= FILE_BYTES, "Memory qualification per-file allowance")
    u.need(sum(sizes) <= ARTIFACT_BYTES, "Memory qualification artifact allowance")
    u.need(shutil.disk_usage(root).free >= RESERVE_BYTES, "Memory qualification disk reserve")
    return sum(sizes)


def resource_check(root, phase):
    # Capacity write/read are deliberately serial. Other projects retain the
    # reserve even if this worker reaches its full address-space allowance.
    memory = PROCESS_BYTES
    available, free = pilot.available_memory(), shutil.disk_usage(root).free
    used = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    remaining = max(0, ARTIFACT_BYTES - used)
    passed = (
        used <= ARTIFACT_BYTES
        and available >= memory + RESERVE_BYTES
        and free >= RESERVE_BYTES + remaining
    )
    value = dict(
        phase=phase,
        available_memory_bytes=available,
        requested_memory_bytes=memory,
        free_disk_bytes=free,
        remaining_artifact_allowance_bytes=remaining,
        memory_reserve_bytes=RESERVE_BYTES,
        disk_reserve_bytes=RESERVE_BYTES,
        passed=passed,
        utc=u.utc(),
    )
    u.write(root / f"resource-{phase}.json", value)
    u.need(passed, "Memory qualification phase memory/disk reserve; see saved resource check")
    return value


def exact_streams(left, right, decoder, *, progress=None):
    """Compare all recorded fields, including observer traces and float bits."""
    streams = [decoder.ctx.reader()(path) for path in (left, right)]
    exact, missing, count = decoder.exact.Exact(), object(), 0
    for a, b in zip_longest(*streams, fillvalue=missing):
        u.need(a is not missing and b is not missing, "Writer comparison record extent")
        exact.match(a, b, "Checkpoint writer numerical recording")
        count += 1
        if progress is not None and count % 2048 == 0:
            progress("writer_records", completed=count, total=streams[0].manifest["records"])
    u.need(count > 0 and all(s.complete for s in streams), "Incomplete writer comparison")
    return dict(
        records=count,
        exact_scalars=exact.scalars,
        float64_bits=exact.floats,
        all_recorded_fields=True,
        failed_comparisons=0,
    )


def compare(root, r, directory):
    import fresh_review

    saved, native_read, clocks = fresh_review.modules()
    progress = pilot.Progress(directory)
    decoder = pilot.reader(saved, native_read, progress=progress)
    preparation, plan = u.read(root / "preparation.json"), r["protocol"]
    baseline = preparation["rows"]["pump_leak/observed"]
    variant = next(
        v
        for v in preparation["native_preparation"]["protocol"]["variants"]
        if v["id"] == "pump_leak"
    )
    with saved.e.model_fence():
        progress.run(
            "authenticate_new_phases",
            lambda: pilot.authenticate_simulations(
                root, tuple(p for p in PHASES if p != "compare")
            ),
            artifact="phase-authentication.json",
        )
        prefix = Path(r["fresh_parent"]) / "native/pump_leak/2"
        u.need(
            u.authenticate_stage(prefix) == r["upstream"]["prefix_completion_sha256"],
            "Prior 10-ms prefix changed",
        )
        small = progress.run(
            "sample_writer_equivalence",
            lambda: exact_streams(
                root / "sample/native/stream",
                root / "sample/inline/stream",
                decoder,
                progress=progress,
            ),
            artifact="sample-writer-equivalence.json",
        )
        overlap = progress.run(
            "qualified_prefix_writer_equivalence",
            lambda: exact_streams(
                root / "overlap/capture/stream",
                prefix / "capture/stream",
                decoder,
                progress=progress,
            ),
            artifact="prefix-writer-equivalence.json",
        )
        row, format_check = progress.run(
            "native_format", lambda: decoder.read(root / "observed/capture/stream")
        )
        u.write(directory / "format-check.json", format_check)
        progress.run(
            "native_identity",
            lambda: saved.native_records.identity(row, baseline, DT, DURATION, "observed"),
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
                max_count=STEPS,
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
        checks = {}
        for name in r["references"]:
            target = saved.d.sample(
                u.read(root / "references" / f"{name}.json"), plan["common_times_s"]
            )
            checks.update(
                {name + "/" + k: v for k, v in saved.state_checks(points, target, plan).items()}
            )
        checks["energy_closure"] = saved.d.discrepancy(
            points["energy"]["max_defect_pJ"], 0.0, plan["accounting"]["native_finest_energy_pJ"]
        )
        pair = progress.run(
            "observer_neutrality",
            lambda: decoder.pair(
                root / "observed/capture/stream",
                root / "unobserved/capture/stream",
                progress=progress,
            ),
            artifact="observer-pair.json",
        )
    failed = [name for name, value in checks.items() if value["failures"]]
    result = dict(
        status="memory_prefix_comparison_completed",
        duration_s=DURATION,
        dt_s=DT,
        steps=STEPS,
        format_check=format_check,
        physical=physical,
        constraints=checks,
        failed_numeric_limits=failed,
        sample_writer_equivalence=small,
        qualified_prefix_writer_equivalence=overlap,
        observer_pair=pair,
        independent_comparisons=ledger.count,
        independent_maxima=ledger.maxima,
        prefix_qualified=not failed,
        scientific_tolerances_changed=False,
        full_betse_parity=False,
        actual_512000_step_capture_qualified=False,
    )
    u.write(directory / "comparison.json", result)
    u.need(not failed, "Finer 10-ms prefix exceeds unchanged numerical limits")
    return result


def action(root, r, directory, phase):
    if phase == "regression":
        scratch = Path(r["workspace"]) / "cache" / root.name / "regression"
        argv = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "validation/betse/long_relaxation/test_memory.py",
            "validation/betse/long_relaxation/test_pilot.py",
            "-o",
            f"cache_dir={scratch / 'pytest'}",
            "--basetemp",
            str(scratch / "tmp"),
            "--junitxml",
            str(directory / "pytest.xml"),
        ]
        u.write(directory / "command.json", dict(argv=argv, cwd=str(u.ROOT)))
        import pytest

        os.chdir(u.ROOT)
        u.need(pytest.main(argv[4:]) == 0, "Regression command failed")
        suites = ET.parse(directory / "pytest.xml").getroot().findall("testsuite")
        u.need(
            suites
            and all(
                int(s.get(k, 0)) == 0 for s in suites for k in ("errors", "failures", "skipped")
            ),
            "Regression checks failed",
        )
        return dict(tests=sum(int(s.get("tests")) for s in suites), status="regressions_passed")
    if phase == "compare":
        return compare(root, r, directory)
    if phase in ("sample", "overlap", "observed", "unobserved"):
        import prepare

        preparation, workspace = u.read(root / "preparation.json"), Path(r["workspace"])
        if phase == "sample":
            from betse.lib.pickle import pickles
            from memory_native import compare_graph, verify_checkpoint

            results = {}
            for name, mode in (("native", "native"), ("inline", MODE)):
                results[name] = prepare.capture(
                    directory / name,
                    workspace,
                    preparation,
                    "pump_leak",
                    2,
                    "observed",
                    8 * u.RANGES["pump_leak"][2],
                    checkpoint_mode=mode,
                )
            paths = [directory / name / "INITS/init_1.betse.gz" for name in ("native", "inline")]
            results["checkpoint_graph"] = compare_graph(
                *(pickles.load(str(p)) for p in paths),
                relocated_roots=(directory / "native", directory / "inline"),
            )
            results["stock_roundtrip"] = verify_checkpoint(
                paths[1], directory / "stock-roundtrip.betse.gz"
            )
            return results
        overlap = phase == "overlap"
        result = prepare.capture(
            directory / "capture",
            workspace,
            preparation,
            "pump_leak",
            2 if overlap else None,
            "unobserved" if phase == "unobserved" else "observed",
            DURATION,
            dt_s=None if overlap else DT,
            checkpoint_mode=MODE,
            stream_bytes=pilot.STREAM_BYTES,
        )
        u.need(result["steps"] == (25600 if overlap else STEPS), "Qualification native extent")
        return result
    import memory_native
    from betse.lib.pickle import pickles

    pickles.init()
    sample = root / "sample/inline/INITS/init_1.betse.gz"
    if phase == "capacity":
        return memory_native.capacity(sample, directory / "synthetic.betse.gz", CAPACITY_STEPS - 1)
    if phase == "capacity_load":
        return memory_native.capacity_load(
            root / "capacity/synthetic.betse.gz", sample, u.read(root / "capacity/result.json")
        )
    u.need(phase == "checkpoints", "Unknown memory qualification phase")
    results = {}
    for name in ("overlap", "observed", "unobserved"):
        results[name] = memory_native.verify_checkpoint(
            root / name / "capture/INITS/init_1.betse.gz", directory / f"{name}-stock.betse.gz"
        )
        gc.collect()
    return results


def worker(root, phase):
    r = u.read(root / "registration.json")
    directory = root / phase
    directory.mkdir()
    began = time.monotonic()
    u.write(directory / "started.json", dict(pid=os.getpid(), utc=u.utc()))
    u.write(
        directory / "registration.json",
        dict(
            phase=phase,
            root_registration_sha256=u.sha(root / "registration.json"),
            duration_s=r["duration_s"],
            dt_s=r["dt_s"],
            checkpoint_mode=r["checkpoint_mode"],
        ),
    )
    try:
        controls(r)
        u.need(u.sources() == r["sources_sha256"], "Frozen memory-qualification source changed")
        u.need(u.runtime() == r["runtimes"][runtime_for(phase)], "Qualification runtime changed")
        pilot.authenticate_files(root, r["inputs_sha256"])
        resource.setrlimit(resource.RLIMIT_AS, (PROCESS_BYTES,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_BYTES,) * 2)
        result = action(root, r, directory, phase)
        u.write(directory / "result.json", result)
        u.write(
            directory / "completion.json",
            dict(
                status="completed",
                phase=phase,
                utc=u.utc(),
                registration_sha256=u.sha(directory / "registration.json"),
                elapsed_seconds=time.monotonic() - began,
                peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                files_sha256=u.inventory(directory),
            ),
        )
    except BaseException as exc:
        u.write(
            directory / "failure.json",
            dict(
                status="failed",
                error=str(exc),
                traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic() - began,
                utc=u.utc(),
                automatic_retry=False,
            ),
        )
        raise


def projections(root):
    costs = {phase: u.read(root / phase / "completion.json") for phase in PHASES}
    measured = {phase: costs[phase]["peak_rss_bytes"] for phase in costs}
    projected = {
        "native_checkpoint_write": round(measured["capacity"] * 1.3),
        "ordinary_checkpoint_load": round(measured["capacity_load"] * 1.3),
        "independent_review": round(measured["compare"] * (CAPACITY_STEPS / STEPS) * 1.3),
    }
    return dict(
        measured_phase_peak_rss_bytes=measured,
        projected_512000_step_peak_rss_bytes=projected,
        memory_headroom_multiplier=1.3,
        process_address_space_bytes=PROCESS_BYTES,
        projected_memory_fits=all(value <= PROCESS_BYTES for value in projected.values()),
        synthetic_storage_is_not_a_trajectory=True,
        actual_long_capture_and_resource_preflight_still_required=True,
    )


def controller(root):
    r, began, phase = u.read(root / "registration.json"), time.monotonic(), None
    u.write(root / "started.json", dict(pid=os.getpid(), utc=u.utc()))
    try:
        for phase in PHASES:
            resource_check(root, phase)
            interpreter = runtime_for(phase)
            with (
                (root / f"{phase}.stdout.log").open("x") as out,
                (root / f"{phase}.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    [
                        "taskset",
                        "-c",
                        "5" if phase == "unobserved" else "4",
                        str(Path(r["workspace"]) / f"venv-{interpreter}/bin/python"),
                        "-B",
                        str(Path(__file__).resolve()),
                        "_worker",
                        str(root),
                        phase,
                    ],
                    stdout=out,
                    stderr=err,
                    stdin=subprocess.DEVNULL,
                    check=True,
                    timeout=PHASES[phase],
                    env=u.env(
                        Path(r["workspace"]), Path(r["workspace"]) / "cache" / root.name / phase
                    ),
                )
            lines = (root / f"{phase}.stderr.log").read_text().splitlines()
            u.need(
                all(
                    line == "[memory_job.py] Ignoring cutting event, as cut profiles are disabled."
                    for line in lines
                )
                if interpreter == "betse"
                else not lines,
                "Unexpected qualification stderr; see saved log",
            )
            budget(root)
        result = u.read(root / "compare/result.json") | dict(
            status="betse_memory_prefix_qualification_completed",
            memory=projections(root),
            phase_completions_sha256={p: u.sha(root / p / "completion.json") for p in PHASES},
            elapsed_seconds=time.monotonic() - began,
            finished_utc=u.utc(),
            artifact_bytes=budget(root),
            automatic_followup=False,
        )
        u.write(root / "result.json", result)
        u.write(
            root / "completion.json",
            dict(
                status=result["status"],
                registration_sha256=u.sha(root / "registration.json"),
                result_sha256=u.sha(root / "result.json"),
                utc=u.utc(),
            ),
        )
    except BaseException as exc:
        failure = dict(
            status="failed",
            phase=phase,
            error=str(exc),
            traceback=traceback.format_exc(),
            elapsed_seconds=time.monotonic() - began,
            utc=u.utc(),
            automatic_retry=False,
        )
        if (
            phase is not None
            and (root / phase).is_dir()
            and not any((root / phase / p).exists() for p in ("failure.json", "completion.json"))
        ):
            u.write(root / phase / "failure.json", failure)
        u.write(root / "failure.json", failure)
        raise


def launch(parent, output, workspace):
    output, parent, workspace = output.resolve(), parent.resolve(), workspace.resolve()
    u.need(
        output.is_relative_to(workspace) and workspace.is_relative_to(Path("/mnt/workspaces")),
        "Qualification outputs must use /mnt/workspaces",
    )
    old, done = u.read(parent / "registration.json"), u.read(parent / "completion.json")
    prior_result = u.read(parent / "result.json")
    u.need(
        done["status"] == prior_result["status"] == "long_pump_pilot_completed"
        and done["registration_sha256"] == u.sha(parent / "registration.json")
        and done["result_sha256"] == u.sha(parent / "result.json"),
        "Completed parent receipt changed",
    )
    u.need(
        old["native_dt_s"] == 2 * DT and old["max_native_labels"] == CAPACITY_STEPS // 2,
        "Require the completed quarter-step parent",
    )
    u.need(u.sources(parent / "source") == old["sources_sha256"], "Parent frozen source changed")
    fresh = Path(old["parent"])
    upstream = {
        name + "_completion_sha256": u.authenticate_stage(fresh / path)
        for name, path in (
            ("preparation", "prepare"),
            ("reference", "reference"),
            ("prefix", "native/pump_leak/2"),
        )
    }
    output.mkdir(parents=True)
    resource_check(output, "launch")
    hashes = u.sources()
    source = output / "source"
    # The pilot's production-reuse guard stays intact. Its regression context
    # uses the qualified production snapshot; only validation code is updated.
    for name in set(hashes) | set(old["sources_sha256"]):
        production = name.startswith(("src/", "configs/"))
        selected = old["sources_sha256"] if production else hashes
        if name not in selected:
            continue
        origin = (parent / "source" if production else u.ROOT) / name
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, destination)
        u.need(u.sha(destination) == selected[name], "Qualification source copy changed")
    preparation_path = fresh / "prepare/preparation.json"
    references = {
        name: fresh / "reference/reference/pump_leak" / name / "result.json"
        for name in old["references"]
    }
    for name, path in {
        "preparation.json": preparation_path,
        **{f"references/{n}.json": p for n, p in references.items()},
    }.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        phase = "prepare" if name == "preparation.json" else "reference"
        expected = u.read(fresh / phase / "completion.json")["files_sha256"][
            str(path.relative_to(fresh / phase))
        ]
        u.need(u.sha(target) == expected, "Authenticated qualification input copy changed")
    r = dict(
        schema="cells.betse_memory_prefix_qualification@1",
        created_utc=u.utc(),
        workspace=str(workspace),
        parent=str(parent),
        fresh_parent=str(fresh),
        parent_completion_sha256=u.sha(parent / "completion.json"),
        upstream=upstream,
        duration_s=DURATION,
        dt_s=DT,
        steps=STEPS,
        capacity_steps=CAPACITY_STEPS,
        checkpoint_mode=MODE,
        protocol=u.plan(),
        references=list(references),
        sources_sha256=u.sources(source),
        live_sources_sha256=hashes,
        production_snapshot=str(parent / "source"),
        production_context=(
            "Frozen qualified production for legacy regression; "
            "new simulations are native BETSE only"
        ),
        inputs_sha256={
            name: u.sha(output / name)
            for name in ("preparation.json", *(f"references/{n}.json" for n in references))
        },
        runtimes=old["runtimes"],
        phase_limits_seconds=PHASES,
        expected_seconds=12600,
        process_address_space_bytes=PROCESS_BYTES,
        artifact_bytes=ARTIFACT_BYTES,
        per_file_bytes=FILE_BYTES,
        cpu_affinity=[4, 5],
        serial_workers=True,
        scientific_tolerances_changed=False,
        automatic_followup=False,
        actual_512000_step_capture_qualified=False,
    )
    controls(r)
    pilot.unchanged_production(old, r["sources_sha256"])
    u.write(output / "registration.json", r)
    with (output / "stdout.log").open("x") as out, (output / "stderr.log").open("x") as err:
        child = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(source / "validation/betse/long_relaxation/memory_job.py"),
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
    result = dict(
        status="launched",
        pid=child.pid,
        output=str(output),
        expected_seconds=r["expected_seconds"],
        utc=u.utc(),
    )
    u.write(output / "launch.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("launch")
    for name in ("parent", "output", "workspace"):
        start.add_argument("--" + name, required=True, type=Path)
    for name in ("_controller", "_worker"):
        command = commands.add_parser(name)
        command.add_argument("output", type=Path)
        if name == "_worker":
            command.add_argument("phase", choices=PHASES)
    args = parser.parse_args()
    if args.command == "launch":
        print(json.dumps(launch(args.parent, args.output, args.workspace), indent=2))
    elif args.command == "_controller":
        controller(args.output)
    else:
        worker(args.output, args.phase)


if __name__ == "__main__":
    main()
