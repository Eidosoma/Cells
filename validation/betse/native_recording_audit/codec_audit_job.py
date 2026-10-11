"""One detached independent review of saved codec evidence; never run a simulator."""

import argparse
import gc
import json
import os
import resource
import shutil
import signal
import subprocess
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import codec_audit_context as context
import codec_review as review
import wire_decode as wire

ROOT, e = context.ROOT, context.e
BOUNDS = dict(
    cpu_affinity=[0, 1, 2, 3],
    timeout_seconds=600,
    address_space_bytes=4 * 1024**3,
    per_file_bytes=4 * 1024**2,
    artifact_bytes=32 * 1024**2,
    free_disk_reserve_bytes=1024**3,
)


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def rss():
    values = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    return dict(
        current_bytes=int(values["VmRSS"].split()[0]) * 1024,
        process_peak_bytes=int(values["VmHWM"].split()[0]) * 1024,
        rusage_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    )


def receipt(path):
    wire.need(path.is_relative_to(ROOT / "reports"), "Review receipt location")
    result = e.software(path, 80)
    rows = ET.parse(path).getroot().findall("testsuite/testcase")
    wire.need(all("test_codec_review" in r.attrib["classname"] for r in rows), "Wrong review tests")
    return result


def budget(output):
    total = 0
    for path in output.rglob("*"):
        wire.need(not path.is_symlink(), "Linked review artifact")
        if path.is_file():
            size = path.stat().st_size
            wire.need(size <= BOUNDS["per_file_bytes"], "Review per-file budget")
            total += size
    wire.need(total < BOUNDS["artifact_bytes"] - 1024**2, "Review total budget")
    wire.need(
        shutil.disk_usage(output).free >= BOUNDS["free_disk_reserve_bytes"], "Review disk reserve"
    )
    return total


def fresh(output):
    wire.need(
        output.is_relative_to(ROOT / "runs") and output != ROOT / "runs" and not output.exists(),
        "Fresh review output required",
    )


def register(output, tests):
    fresh(output)
    software = receipt(tests)
    with e.model_fence():
        _, _, files = context.authenticate()
    sources = context.source_manifest()
    result = dict(
        schema="cells.offline_codec_independent_review@1",
        decision="D124",
        created_utc=datetime.now(UTC).isoformat(),
        capture_completion_sha256=context.COMPLETION_SHA,
        capture_registration_sha256=context.REGISTRATION_SHA,
        capture_files_sha256=files,
        sources_sha256=sources,
        software=software,
        bounds=BOUNDS,
        forbidden_imports=list(e.FORBIDDEN),
        planned_rows=36,
        planned_updates=6720,
        planned_history_samples=13404,
        planned_stream_records=20196,
        comparison="same_type_and_exact_float64_bits",
        physics_rerun=False,
        production_changed=False,
        automatic_retry=False,
        automatic_followup=False,
    )
    output.mkdir(parents=True)
    try:
        budget(output)
        write(output / "registration.json", result)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in sources:
                archive.write(ROOT / name, arcname=name)
    except BaseException:
        write(
            output / "registration-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise
    return result


def authenticate(output, expected_sha):
    wire.need(wire.sha(output / "registration.json") == expected_sha, "Review registration digest")
    r = wire.read_json(output / "registration.json", None)
    wire.need(
        r["schema"] == "cells.offline_codec_independent_review@1"
        and r["bounds"] == BOUNDS
        and r["capture_completion_sha256"] == context.COMPLETION_SHA
        and r["capture_registration_sha256"] == context.REGISTRATION_SHA,
        "Review identity",
    )
    wire.need(context.source_manifest() == r["sources_sha256"], "Review sources changed")
    context.prior.evidence.capsule(output, r["sources_sha256"])
    wire.need(receipt(ROOT / r["software"]["path"]) == r["software"], "Review software changed")
    capture, done, files = context.authenticate()
    wire.need(files == r["capture_files_sha256"], "Codec packet changed since review registration")
    return capture, done


def one(index, label, source):
    started = time.monotonic()
    path = context.prior.evidence.child(context.LEGACY, source["path"])
    wire.need(wire.sha(path) == source["sha256"], "Original row changed")
    original = wire.read_json(path, None)
    identifier, raw_dt, mode = label.split("/")
    dt = float(raw_dt.removeprefix("dt_"))
    steps = round(0.001 / dt)
    wire.need(
        original["id"] == identifier
        and original["dt_s"] == dt
        and original["mode"] == mode
        and original["steps"] == steps,
        "Original row identity",
    )
    directory = context.CAPTURE / "rows" / f"{index:02d}"
    result = review.inspect(original, directory)
    saved = wire.read_json(context.CAPTURE / "row_reports" / f"{index:02d}.json")
    wire.need(
        saved["label"] == label
        and saved["legacy_file_sha256"] == source["sha256"]
        and saved["manifest_sha256"] == wire.sha(directory / "manifest.json"),
        "Producer row link",
    )
    review.Exact().match(wire.read_json(directory / "manifest.json"), saved["manifest"], "manifest")
    wire.need(
        saved["status"] == "exact_offline_row_roundtrip_not_live_qualification"
        and saved["canonical_sha256"] == saved["reconstructed_canonical_sha256"],
        "Missing producer round-trip claim",
    )
    for key in ("stream_bytes", "stream_files", "largest_stream_file_bytes"):
        wire.need(result["stream"][key] == saved[key], "Producer measurement mismatch: " + key)
    wire.need(
        source["bytes"] == path.stat().st_size == saved["source_json_bytes"]
        and wire.sha(path) == source["sha256"],
        "Original row identity/size changed",
    )
    result |= dict(
        label=label,
        id=identifier,
        mode=mode,
        dt_s=dt,
        steps=steps,
        source_sha256=source["sha256"],
        original_json_bytes=path.stat().st_size,
        stream_manifest_sha256=wire.sha(directory / "manifest.json"),
        elapsed_seconds=time.monotonic() - started,
        reviewer_rss=rss(),
    )
    del original
    gc.collect()
    return result


def gate(rows, captured):
    wire.need(sorted(rows) == context.expected_labels(), "Review matrix incomplete")
    for label, row in rows.items():
        identifier, raw_dt, mode = label.split("/")
        n = round(0.001 / float(raw_dt.removeprefix("dt_")))
        wire.need(
            row["label"] == label
            and row["id"] == identifier
            and row["mode"] == mode
            and row["dt_s"] == float(raw_dt.removeprefix("dt_"))
            and row["steps"] == n
            and row["observed_updates"] == (n if mode == "observed" else 0)
            and row["history_samples"] == n - 1
            and row["stream_records"] == (2 * n + 1 if mode == "observed" else n + 1)
            and row["status"] == "exact_every_original_value"
            and row["exact_scalar_comparisons"] == row["original_scalar_values"] > 0
            and row["history_array_digests"] == 9
            and row["endpoint_array_digests"] == 14,
            "Unverified row/coverage",
        )
    summed = {
        name: sum(r[name] for r in rows.values())
        for name in (
            "observed_updates",
            "history_samples",
            "stream_records",
            "original_scalar_values",
            "exact_scalar_comparisons",
            "float64_bit_comparisons",
            "negative_zero_values",
            "history_array_digests",
            "endpoint_array_digests",
            "original_json_bytes",
        )
    }
    wire.need(
        summed["observed_updates"] == 6720
        and summed["history_samples"] == 13404
        and summed["stream_records"] == 20196,
        "Incomplete reviewed record extent",
    )
    result = dict(
        rows=36,
        **summed,
        stream_bytes=sum(r["stream"]["stream_bytes"] for r in rows.values()),
        max_encoded_chunk_bytes=max(r["stream"]["peak_chunk_bytes"] for r in rows.values()),
        max_encoded_record_bytes=max(r["stream"]["peak_record_bytes"] for r in rows.values()),
        largest_stream_file_bytes=max(
            r["stream"]["largest_stream_file_bytes"] for r in rows.values()
        ),
    )
    for key in (
        "rows",
        "observed_updates",
        "stream_records",
        "stream_bytes",
        "max_encoded_chunk_bytes",
        "max_encoded_record_bytes",
        "largest_stream_file_bytes",
    ):
        wire.need(result[key] == captured[key], "Captured summary disagrees: " + key)
    wire.need(
        result["original_json_bytes"] == captured["original_native_json_bytes"], "Legacy byte total"
    )
    result["storage_reduction_factor"] = result["original_json_bytes"] / result["stream_bytes"]
    return result


def set_limits():
    def timeout(_signal, _frame):
        raise TimeoutError("Independent codec review exceeded 600 seconds")

    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, BOUNDS["timeout_seconds"])
    resource.setrlimit(resource.RLIMIT_AS, (BOUNDS["address_space_bytes"],) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (BOUNDS["per_file_bytes"],) * 2)


def payloads(output):
    return {
        k: v
        for k, v in context.inventory(output).items()
        if k not in ("launch.json", "runner.stdout.log", "runner.stderr.log")
    }


def execute(output, expected_sha):
    wire.need(
        output.is_relative_to(ROOT / "runs") and output != ROOT / "runs", "Review output location"
    )
    wire.need(not (output / "started.json").exists(), "Review already attempted")
    started = time.monotonic()
    set_limits()
    try:
        write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        wire.need(sorted(os.sched_getaffinity(0)) == BOUNDS["cpu_affinity"], "Review CPU affinity")
        with e.model_fence():
            capture, captured_done = authenticate(output, expected_sha)
            (output / "rows").mkdir()
            rows = {}
            for index, label in enumerate(context.expected_labels()):
                print(f"{index + 1}/36 review {label}", flush=True)
                result = one(index, label, capture["records"][label])
                write(output / "rows" / f"{index:02d}.json", result)
                rows[label] = result
                budget(output)
                print(
                    f"{index + 1}/36 exact {result['exact_scalar_comparisons']} values", flush=True
                )
            summary = gate(rows, captured_done)
            authenticate(output, expected_sha)
        write(output / "review.json", summary)
        used = budget(output)
        write(
            output / "completion.json",
            dict(
                status="offline_lossless_recording_independently_closed",
                elapsed_seconds=time.monotonic() - started,
                finished_utc=datetime.now(UTC).isoformat(),
                files_sha256=payloads(output),
                artifact_bytes_before_completion=used,
                **summary,
                reviewer_rss=rss(),
                failed_comparisons=0,
                offline_codec_qualified=True,
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
        write(
            output / "failure.json",
            dict(
                status="independent_codec_review_failed_not_closed",
                elapsed_seconds=time.monotonic() - started,
                traceback=traceback.format_exc(),
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, tests):
    register(output, tests)
    expected_sha = wire.sha(output / "registration.json")
    environment = {
        k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "JAX", "XLA"))
    }
    environment.update(
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
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
                    expected_sha,
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
            registration_sha256=expected_sha,
            launched_utc=datetime.now(UTC).isoformat(),
            automatic_polling=False,
        )
        write(output / "launch.json", ack)
        return ack
    except BaseException:
        write(
            output / "launch-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "execute"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--registration-sha")
    args = parser.parse_args()
    if args.action == "launch":
        if args.tests is None:
            parser.error("--tests required")
        print(json.dumps(launch(args.output.resolve(), args.tests.resolve()), sort_keys=True))
    else:
        if args.registration_sha is None:
            parser.error("--registration-sha required")
        execute(args.output.resolve(), args.registration_sha)
