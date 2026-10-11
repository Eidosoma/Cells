"""Source-bound offline codec qualification. Detached, no polling or follow-up."""

import argparse
import os
import resource
import shutil
import signal
import subprocess
import sys
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import qualify
import record_codec as codec

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pump_relaxation_plan"))
import check_plan as context  # noqa: E402

e, ROOT = context.e, context.ROOT
CAPTURE = context.evidence.CAPTURE
LARGEST = "pump_leak/dt_1.5625e-06/observed"
BOUNDS = dict(
    cpu_affinity=[0, 1, 2, 3],
    timeout_seconds=900,
    address_space_bytes=4 * 1024**3,
    per_file_bytes=16 * 1024**2,
    per_stream_bytes=32 * 1024**2,
    artifact_bytes=512 * 1024**2,
    minimum_free_disk_bytes=1024**3,
    chunk_records=32,
    chunk_bytes=8 * 1024**2,
)


def runtime_sources():
    return {
        str((HERE / name).relative_to(ROOT)): codec.file_sha(HERE / name)
        for name in ("record_codec.py", "native_row.py", "qualify.py")
    }


def source_manifest():
    paths = [
        *HERE.glob("*.py"),
        HERE / "README.md",
        ROOT / "reports/REF005D_CODEC_HANDOFF.md",
        HERE.parent / "pump_relaxation_plan/check_plan.py",
        HERE.parent / "pump_pilot_audit/audit_evidence.py",
        HERE.parent / "pump_pilot_diagnosis/diagnose.py",
        HERE.parent / "pump_pilot_diagnosis/native_energy.py",
        HERE.parent / "pump_loop_audit/evidence.py",
        HERE.parent / "pump_loop_audit/review.py",
        HERE.parent / "kinetic_family_audit/artifacts.py",
    ]
    return {str(p.relative_to(ROOT)): codec.file_sha(p) for p in sorted(paths)}


def fresh(output):
    e.require(
        output.is_relative_to(ROOT / "runs") and output != ROOT / "runs" and not output.exists(),
        "Fresh codec output required",
    )


def bind_records():
    e.require(
        codec.file_sha(CAPTURE / "completion.json") == context.evidence.COMPLETION_SHA,
        "Closed capture identity",
    )
    done = codec.read_json(CAPTURE / "completion.json")
    e.require(
        codec.file_sha(CAPTURE / "betse.json") == done["files_sha256"]["betse.json"],
        "Native index changed",
    )
    records = codec.read_json(CAPTURE / "betse.json")["records"]
    variants = (
        "pump_leak",
        "pump_only",
        "leak_only",
        "all_blocked",
        "half_density",
        "closed_boundary",
    )
    expected = {
        f"{v}/dt_{h:.8g}/{m}"
        for v in variants
        for h in (6.25e-6, 3.125e-6, 1.5625e-6)
        for m in ("observed", "unobserved")
    }
    e.require(set(records) == expected, "Offline matrix membership")
    result = {}
    for label, name in sorted(records.items()):
        path = context.evidence.child(CAPTURE, name)
        result[label] = dict(
            path=name, sha256=done["files_sha256"][name], bytes=path.stat().st_size
        )
    return result


def set_bounds(seconds):
    def expired(_signal, _frame):
        raise TimeoutError(f"Offline codec job exceeded {seconds} seconds")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    resource.setrlimit(resource.RLIMIT_AS, (BOUNDS["address_space_bytes"],) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (BOUNDS["per_file_bytes"],) * 2)


def inventory(output):
    return {
        str(p.relative_to(output)): codec.file_sha(p)
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.name not in ("launch.json", "runner.stdout.log", "runner.stderr.log")
    }


def budget(output, reserve=0):
    used = 0
    for path in output.rglob("*"):
        e.require(not path.is_symlink(), "Linked codec artifact")
        if path.is_file():
            size = path.stat().st_size
            e.require(size <= BOUNDS["per_file_bytes"], "Codec per-file cap")
            used += size
    e.require(used + reserve < BOUNDS["artifact_bytes"] - 1024**2, "Codec aggregate cap")
    e.require(
        shutil.disk_usage(output).free >= BOUNDS["minimum_free_disk_bytes"],
        "Codec free-space reserve",
    )
    return used


def software(path):
    e.require(path.is_relative_to(ROOT / "reports"), "Codec receipt location")
    result = e.software(path, 120)
    cases = ET.parse(path).getroot().findall("testsuite/testcase")
    e.require(all("test_recording" in c.attrib["classname"] for c in cases), "Wrong codec suite")
    return result


def preflight(output):
    """One bounded largest-row resource probe, not the full qualification campaign."""
    fresh(output)
    output.mkdir(parents=True)
    set_bounds(60)
    try:
        with e.model_fence():
            record = bind_records()[LARGEST]
            source = runtime_sources()
            budget(output, BOUNDS["per_stream_bytes"])
            result = qualify.one(
                CAPTURE / record["path"],
                output / "stream",
                record["sha256"],
                BOUNDS["per_stream_bytes"],
            )
            e.require(source == runtime_sources(), "Codec changed during probe")
            codec.write_json(
                output / "measurement.json",
                dict(
                    schema="cells.native_codec_resource_probe@1",
                    label=LARGEST,
                    sources_sha256=source,
                    result=result,
                    scientific_acceptance_rerun=False,
                    live_memory_qualified=False,
                ),
            )
            codec.write_json(
                output / "completion.json",
                dict(
                    status="largest_saved_row_exact_resource_probe_only",
                    files_sha256=inventory(output),
                    automatic_followup=False,
                ),
            )
        return dict(output=str(output.relative_to(ROOT)), **result)
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        codec.write_json(
            output / "failure.json",
            dict(status="probe_failed", traceback=traceback.format_exc(), automatic_retry=False),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def probe_receipt(directory):
    e.require(directory.is_relative_to(ROOT / "runs"), "Probe location")
    done = codec.read_json(directory / "completion.json")
    e.require(
        done["status"] == "largest_saved_row_exact_resource_probe_only"
        and not (directory / "failure.json").exists(),
        "Probe not complete",
    )
    context.evidence.hashes(directory, done["files_sha256"])
    record = codec.read_json(directory / "measurement.json")
    e.require(
        record["sources_sha256"] == runtime_sources() and record["label"] == LARGEST,
        "Probe code/scope changed",
    )
    value = record["result"]
    e.require(
        value["legacy_file_sha256"] == bind_records()[LARGEST]["sha256"]
        and value["steps"] == 640
        and value["manifest"]["records"] == 1281
        and value["canonical_sha256"] == value["reconstructed_canonical_sha256"]
        and value["manifest"]["chunk_records"] == BOUNDS["chunk_records"]
        and value["manifest"]["chunk_bytes"] == BOUNDS["chunk_bytes"]
        and value["manifest"]["max_output_bytes"] == BOUNDS["per_stream_bytes"],
        "Probe result mismatch",
    )
    return dict(
        path=str(directory.relative_to(ROOT)),
        completion_sha256=codec.file_sha(directory / "completion.json"),
        measurement_sha256=codec.file_sha(directory / "measurement.json"),
    )


def register(output, tests, probe):
    fresh(output)
    receipt, measured = software(tests), probe_receipt(probe)
    with e.model_fence():
        context.authenticate()
    sources = source_manifest()
    r = dict(
        schema="cells.native_codec_qualification@1",
        decision="D123",
        registered_utc=datetime.now(UTC).isoformat(),
        bounds=BOUNDS,
        capture_completion_sha256=context.evidence.COMPLETION_SHA,
        prior_audit_completion_sha256=context.AUDIT_SHA,
        records=bind_records(),
        sources_sha256=sources,
        software=receipt,
        probe=measured,
        native_observed_updates=6720,
        planned_rows=36,
        planned_stream_records=20196,
        signed_zero_sensitive_whole_row_comparison=True,
        scientific_tolerances_changed=False,
        simulators_imported=False,
        automatic_followup=False,
        automatic_retry=False,
    )
    output.mkdir(parents=True)
    try:
        budget(output, BOUNDS["per_stream_bytes"])
        codec.write_json(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in sources:
                archive.write(ROOT / name, arcname=name)
    except BaseException:
        codec.write_json(
            output / "registration-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise
    return r


def authenticate(output, expected_sha):
    e.require(
        codec.file_sha(output / "registration.json") == expected_sha,
        "Codec registration digest changed",
    )
    r = codec.read_json(output / "registration.json")
    e.require(
        r["schema"] == "cells.native_codec_qualification@1"
        and r["bounds"] == BOUNDS
        and r["capture_completion_sha256"] == context.evidence.COMPLETION_SHA
        and r["prior_audit_completion_sha256"] == context.AUDIT_SHA,
        "Codec registration identity",
    )
    e.require(source_manifest() == r["sources_sha256"], "Codec source membership/content changed")
    context.evidence.capsule(output, r["sources_sha256"])
    e.require(software(ROOT / r["software"]["path"]) == r["software"], "Codec receipt changed")
    e.require(probe_receipt(ROOT / r["probe"]["path"]) == r["probe"], "Probe receipt changed")
    e.require(bind_records() == r["records"], "Offline matrix changed")
    context.authenticate()
    return r


def gate(reports):
    e.require(set(reports) == set(bind_records()), "Incomplete offline matrix")
    for label, row in reports.items():
        identifier, step, mode = label.split("/")
        dt = float(step.removeprefix("dt_"))
        steps = round(0.001 / dt)
        e.require(
            row["id"] == identifier
            and row["mode"] == mode
            and row["dt_s"] == dt
            and row["steps"] == steps
            and row["manifest"]["records"] == (2 * steps + 1 if mode == "observed" else steps + 1),
            "Offline row identity/extent",
        )
    e.require(
        sum(r["steps"] for r in reports.values() if r["mode"] == "observed") == 6720
        and sum(r["mode"] == "observed" for r in reports.values()) == 18
        and sum(r["mode"] == "unobserved" for r in reports.values()) == 18
        and sum(r["manifest"]["records"] for r in reports.values()) == 20196,
        "Incomplete native record coverage",
    )
    e.require(
        all(
            r["status"] == "exact_offline_row_roundtrip_not_live_qualification"
            and r["canonical_sha256"] == r["reconstructed_canonical_sha256"]
            for r in reports.values()
        ),
        "Nonexact offline row",
    )
    return dict(
        rows=36,
        observed_updates=6720,
        stream_records=20196,
        original_native_json_bytes=sum(r["source_json_bytes"] for r in reports.values()),
        stream_bytes=sum(r["stream_bytes"] for r in reports.values()),
        max_encoded_chunk_bytes=max(
            r["manifest"]["peak_encoded_chunk_bytes"] for r in reports.values()
        ),
        max_encoded_record_bytes=max(
            r["manifest"]["peak_encoded_record_bytes"] for r in reports.values()
        ),
        largest_stream_file_bytes=max(r["largest_stream_file_bytes"] for r in reports.values()),
        process_peak_rss_bytes=qualify.rss()["process_high_water_bytes"],
    )


def execute(output, expected_sha):
    e.require(
        output.is_relative_to(ROOT / "runs") and output != ROOT / "runs",
        "Codec execution output location",
    )
    e.require(not (output / "started.json").exists(), "Codec job already attempted")
    started = time.monotonic()
    set_bounds(BOUNDS["timeout_seconds"])
    try:
        codec.write_json(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        e.require(sorted(os.sched_getaffinity(0)) == BOUNDS["cpu_affinity"], "Codec CPU affinity")
        with e.model_fence():
            r = authenticate(output, expected_sha)
            (output / "rows").mkdir()
            (output / "row_reports").mkdir()
            reports = {}
            for index, (label, source) in enumerate(r["records"].items()):
                budget(output, BOUNDS["per_stream_bytes"])
                print(f"{index + 1}/36 start {label}", flush=True)
                report = qualify.one(
                    CAPTURE / source["path"],
                    output / "rows" / f"{index:02d}",
                    source["sha256"],
                    BOUNDS["per_stream_bytes"],
                )
                codec.write_json(
                    output / "row_reports" / f"{index:02d}.json", dict(label=label, **report)
                )
                reports[label] = report
                print(f"{index + 1}/36 exact {label}: {report['stream_bytes']} bytes", flush=True)
            summary = gate(reports)
            authenticate(output, expected_sha)
        codec.write_json(output / "summary.json", summary)
        used = budget(output)
        codec.write_json(
            output / "completion.json",
            dict(
                status="offline_codec_exact_pending_independent_review",
                elapsed_seconds=time.monotonic() - started,
                finished_utc=datetime.now(UTC).isoformat(),
                files_sha256=inventory(output),
                artifact_bytes_before_completion=used,
                **summary,
                live_observer_qualified=False,
                native_memory_bounded=False,
                longer_horizon_qualified=False,
                production_changed=False,
                biology_validated=False,
                gpu_tested=False,
                automatic_followup=False,
            ),
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        codec.write_json(
            output / "failure.json",
            dict(
                status="offline_codec_failed_not_qualified",
                elapsed_seconds=time.monotonic() - started,
                traceback=traceback.format_exc(),
                automatic_retry=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, tests, probe):
    register(output, tests, probe)
    registered_sha = codec.file_sha(output / "registration.json")
    environment = {
        k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "JAX", "XLA"))
    }
    environment.update(
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
    )
    try:
        with (
            (output / "runner.stdout.log").open("x") as stdout,
            (output / "runner.stderr.log").open("x") as stderr,
        ):
            child = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    "0-3",
                    str(ROOT / ".venv/bin/python"),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                    "--registration-sha",
                    registered_sha,
                ],
                cwd=ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
        ack = dict(
            status="launched_detached",
            pid=child.pid,
            launched_utc=datetime.now(UTC).isoformat(),
            registration_sha256=registered_sha,
            automatic_polling=False,
        )
        codec.write_json(output / "launch.json", ack)
        return ack
    except BaseException:
        codec.write_json(
            output / "launch-failure.json",
            dict(status="launch_failed", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "launch", "execute"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--registration-sha")
    args = parser.parse_args()
    output = args.output.resolve()
    if args.action == "preflight":
        result = preflight(output)
    elif args.action == "execute":
        if args.registration_sha is None:
            parser.error("--registration-sha required")
        execute(output, args.registration_sha)
        result = {"status": "finished"}
    else:
        if args.tests is None or args.probe is None:
            parser.error("--tests and --probe required")
        result = launch(output, args.tests.resolve(), args.probe.resolve())
    print(codec.canonical(result).decode())
