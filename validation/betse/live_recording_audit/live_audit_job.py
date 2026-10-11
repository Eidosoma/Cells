"""Short source-bound software checks, then one detached read-only D129 review.

The module name is distinct from earlier audit controllers on the helper path.
"""

import argparse
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

import audit_context as c
import cells_review
import native_review

BOUNDS = dict(
    cpu_affinity=[0, 1, 2, 3],
    timeout_seconds=900,
    address_space_bytes=4 * 1024**3,
    per_file_bytes=8 * 1024**2,
    artifact_bytes=64 * 1024**2,
    free_disk_reserve_bytes=1024**3,
)
REQUIRED_TESTS = {
    "test_saved_cells_paths",
    "test_checkpoint_resealed_corruption",
    "test_resealed_recording_corruption",
    "test_window_receipt_corruption",
    "test_native_saved_row",
    "test_native_pair",
    "test_import_fence",
    "test_registration_tamper",
    "test_failed_review_durable",
    "test_launch_detaches_without_wait",
}


def write(path, value):
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def fresh(output):
    c.need(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Fresh audit output required",
    )
    c.child(c.ROOT, str(output.relative_to(c.ROOT)))


def receipt(path):
    c.need(path.is_relative_to(c.ROOT / "reports"), "Software receipt location")
    result = c.e.software(path, 60)
    suites = ET.parse(path).getroot().findall("testsuite")
    cases = [case for suite in suites for case in suite.findall("testcase")]
    names = {(v.get("classname"), v.get("name")) for v in cases}
    c.need(
        len(names) == len(cases) == result["tests"]
        and all("test_live_audit" in v.get("classname", "") for v in cases)
        and REQUIRED_TESTS <= {v.get("name", "").split("[")[0] for v in cases},
        "Incomplete live-review tests",
    )
    return result


def environment():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "JAX", "XLA"))}
    env.update(
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
    )
    return env


def archive(output, sources):
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as z:
        for name in sources:
            z.write(c.child(c.ROOT, name), arcname=name)


def check(output, tests):
    fresh(output)
    c.need(tests.is_relative_to(c.ROOT / "reports") and not tests.exists(), "Fresh XML required")
    before = c.sources()
    output.mkdir(parents=True)
    started = time.monotonic()
    write(output / "registration.json", dict(sources_sha256=before, test_timeout_seconds=60))
    archive(output, before)
    try:
        with (
            (output / "tests.stdout.log").open("x") as out,
            (output / "tests.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    str(c.ROOT / ".venv/bin/python"),
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-W",
                    "error",
                    str(c.HERE / "test_live_audit.py"),
                    "--junitxml=" + str(tests),
                    "--basetemp=" + str(output / "tests"),
                ],
                cwd=c.ROOT,
                env=environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                timeout=60,
                check=True,
            )
        software = receipt(tests)
        c.need(
            c.sources() == before and (output / "tests.stderr.log").read_bytes() == b"",
            "Software source/stderr guard",
        )
        files, links = c.inventory(output, pytest_links=True)
        done = dict(
            status="independent_live_review_software_pass",
            software=software,
            sources_sha256=before,
            files_sha256=files,
            pytest_internal_links=links,
            elapsed_seconds=time.monotonic() - started,
            automatic_followup=False,
        )
        write(output / "completion.json", done)
        return {k: done[k] for k in ("status", "software", "elapsed_seconds")}
    except BaseException:
        write(
            output / "failure.json",
            dict(status="software_failed", traceback=traceback.format_exc()),
        )
        raise


def software(path):
    c.need(
        path.is_relative_to(c.ROOT / "runs") and path.name == "completion.json", "Software packet"
    )
    done, _ = c.packet(path.parent, path.name, c.sha(path), pytest_links=True)
    c.need(
        done["status"] == "independent_live_review_software_pass"
        and done["sources_sha256"] == c.sources()
        and done["automatic_followup"] is False,
        "Changed software context",
    )
    c.need(
        receipt(c.child(c.ROOT, done["software"]["path"])) == done["software"],
        "Changed software XML",
    )
    c.capsule(path.parent, done["sources_sha256"])
    return dict(path=str(path.relative_to(c.ROOT)), sha256=c.sha(path), xml=done["software"])


def budget(output):
    files, _ = c.inventory(output)
    sizes = [c.child(output, k).stat().st_size for k in files]
    c.need(all(n <= BOUNDS["per_file_bytes"] for n in sizes), "Audit per-file budget")
    c.need(sum(sizes) < BOUNDS["artifact_bytes"] - 1024**2, "Audit total budget")
    c.need(
        shutil.disk_usage(output).free >= BOUNDS["free_disk_reserve_bytes"], "Audit disk reserve"
    )
    return sum(sizes)


def register(output, checked):
    fresh(output)
    tests = software(checked)
    with c.e.model_fence():
        _, files = c.authenticate()
    r = dict(
        schema="cells.live_recording_independent_review@1",
        decision="D129",
        created_utc=datetime.now(UTC).isoformat(),
        capture_registration_sha256=c.REG_SHA,
        capture_completion_sha256=c.DONE_SHA,
        prerequisite_files_sha256=files,
        sources_sha256=c.sources(),
        software=tests,
        bounds=BOUNDS,
        forbidden_imports=list(c.e.FORBIDDEN),
        phases=["native", "pairs", "probe", "matrix"],
        comparison="direct_saved_array_bits_and_independent_expected_receipt_replay",
        native_rows=36,
        observer_pairs=18,
        cells_counts=c.COUNTS,
        unsaved_trajectories_directly_inspected=False,
        physics_rerun=False,
        production_changed=False,
        automatic_retry=False,
        automatic_followup=False,
    )
    output.mkdir(parents=True)
    try:
        write(output / "registration.json", r)
        archive(output, r["sources_sha256"])
        budget(output)
    except BaseException:
        write(
            output / "registration-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise
    return r


def authenticate(output, expected_sha):
    c.need(c.sha(output / "registration.json") == expected_sha, "Audit registration digest")
    r = c.read(output / "registration.json", None)
    c.need(
        r["schema"] == "cells.live_recording_independent_review@1"
        and r["decision"] == "D129"
        and r["bounds"] == BOUNDS
        and r["capture_registration_sha256"] == c.REG_SHA
        and r["capture_completion_sha256"] == c.DONE_SHA
        and r["cells_counts"] == c.COUNTS
        and r["sources_sha256"] == c.sources(),
        "Audit context changed",
    )
    c.capsule(output, r["sources_sha256"])
    c.need(
        software(c.child(c.ROOT, r["software"]["path"])) == r["software"], "Audit software changed"
    )
    capture, files = c.authenticate()
    c.need(files == r["prerequisite_files_sha256"], "Prerequisites changed after registration")
    return capture


def cells_gate(phase, rows):
    keys = [c.PROBE_KEY] if phase == "probe" else c.cells_keys()
    c.need(sorted(rows) == keys, "Reviewed Cells case coverage")
    mapping = dict(
        full_trajectories="baseline_trajectories",
        window_runs="window_receipts",
        disk_recordings="disk_recordings",
        restart_suffixes="saved_restart_suffixes",
        restart_window_runs="restart_window_receipts",
        zero_length_runs="zero_length_receipts",
        sparse_schedule_controls="sparse_schedule_receipts",
    )
    counts = {name: sum(row[field] for row in rows.values()) for name, field in mapping.items()}
    c.need(counts == c.COUNTS[phase], "Reviewed Cells counts")
    return counts | dict(
        direct_arrays=sum(v["direct_arrays"] for v in rows.values()),
        direct_values=sum(v["direct_values"] for v in rows.values()),
    )


def review(output):
    native = c.read(c.NATIVE / "native.json", None)
    original = c.read(c.LEGACY / "betse.json", None)["records"]
    c.need(
        sorted(native["records"]) == sorted(original) == c.old.expected_labels(),
        "Native row mapping",
    )
    rows = {}
    (output / "native").mkdir()
    for i, label in enumerate(c.old.expected_labels()):
        print(f"Native {i + 1}/36: {label}", flush=True)
        record = native["records"][label]
        c.need(record["directory"] == f"native/{i:02d}", "Native directory order")
        rows[label] = native_review.inspect(label, record, c.child(c.LEGACY, original[label]))
        write(output / "native" / f"{i:02d}.json", rows[label])
        budget(output)
    pairs = {}
    saved_pairs = {p["label"]: p for p in native["observer_pairs"]}
    c.need(len(saved_pairs) == len(native["observer_pairs"]) == 18, "Pair report coverage")
    for label in sorted(saved_pairs):
        print("Observer pair: " + label, flush=True)
        dirs = [
            c.child(c.NATIVE, native["records"][label + "/" + mode]["directory"]) / "stream"
            for mode in ("observed", "unobserved")
        ]
        pairs[label] = native_review.pair(*dirs)
        c.exact.Exact().match(
            pairs[label] | dict(label=label), saved_pairs[label], "Saved observer-pair receipt"
        )
    write(output / "pairs.json", pairs)
    result = dict(native=native_review.matrix_gate(rows, pairs))
    accepted = c.read(c.LEGACY / "cells.json", None)["records"]
    for phase in ("probe", "matrix"):
        selected = c.read(c.CAPTURE / (phase + ".json"), None)["records"]
        reviewed = {}
        (output / phase).mkdir()
        for i, (key, record) in enumerate(sorted(selected.items())):
            print(f"Cells {phase} {i + 1}/{len(selected)}: {key}", flush=True)
            reviewed[key] = cells_review.inspect(
                c.child(c.CAPTURE / phase, record["directory"]),
                c.child(c.LEGACY, accepted[key]["directory"]),
            )
            write(output / phase / f"{i:02d}.json", dict(key=key, **reviewed[key]))
            budget(output)
        result[phase] = cells_gate(phase, reviewed)
    return result


def limits():
    def timeout(_signal, _frame):
        raise TimeoutError("Independent live review exceeded 900 seconds")

    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, BOUNDS["timeout_seconds"])
    resource.setrlimit(resource.RLIMIT_AS, (BOUNDS["address_space_bytes"],) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (BOUNDS["per_file_bytes"],) * 2)


def execute(output, expected_sha):
    c.need(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not (output / "started.json").exists(),
        "Fresh registered audit required",
    )
    started = time.monotonic()
    limits()
    try:
        write(
            output / "started.json",
            dict(pid=os.getpid(), started_utc=datetime.now(UTC).isoformat()),
        )
        c.need(sorted(os.sched_getaffinity(0)) == BOUNDS["cpu_affinity"], "Audit CPU affinity")
        with c.e.model_fence():
            authenticate(output, expected_sha)
            result = review(output)
            authenticate(output, expected_sha)
        write(output / "review.json", result)
        used = budget(output)
        files, _ = c.inventory(output)
        files = {
            k: v
            for k, v in files.items()
            if k not in ("launch.json", "runner.stdout.log", "runner.stderr.log")
        }
        write(
            output / "completion.json",
            dict(
                status="live_recording_saved_outputs_and_receipts_independently_closed",
                finished_utc=datetime.now(UTC).isoformat(),
                elapsed_seconds=time.monotonic() - started,
                files_sha256=files,
                artifact_bytes_before_completion=used,
                **result,
                reviewer_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                failed_comparisons=0,
                saved_native_streams_independently_reviewed=True,
                saved_cells_arrays_independently_reviewed=True,
                expected_window_receipts_replayed=True,
                unsaved_trajectories_directly_inspected=False,
                native_memory_bounded=False,
                earlier_attempts_stay_failed=True,
                physics_rerun=False,
                production_changed=False,
                scientific_tolerances_changed=False,
                longer_horizon_qualified=False,
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
                status="independent_live_review_failed_not_closed",
                elapsed_seconds=time.monotonic() - started,
                traceback=traceback.format_exc(),
                automatic_retry=False,
                automatic_followup=False,
            ),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, checked):
    register(output, checked)
    expected_sha = c.sha(output / "registration.json")
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            proc = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    "0-3",
                    str(c.ROOT / ".venv/bin/python"),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                    "--registration-sha",
                    expected_sha,
                ],
                cwd=c.ROOT,
                env=environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        ack = dict(
            status="launched_detached",
            pid=proc.pid,
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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("check", "launch", "execute"))
    p.add_argument("output", type=Path)
    p.add_argument("--tests", type=Path)
    p.add_argument("--software", type=Path)
    p.add_argument("--registration-sha")
    args = p.parse_args()
    output = args.output.absolute()
    if args.action == "check":
        if args.tests is None:
            p.error("--tests required")
        print(json.dumps(check(output, args.tests.absolute()), sort_keys=True))
    elif args.action == "launch":
        if args.software is None:
            p.error("--software required")
        print(json.dumps(launch(output, args.software.absolute()), sort_keys=True))
    else:
        if args.registration_sha is None:
            p.error("--registration-sha required")
        execute(output, args.registration_sha)
