"""Register once, run detached, preserve failure, and stop before a follow-up audit."""

import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import transport_protocol as t

c = t.c
PRIOR = c.ROOT / "runs/ref-004a-kv1p5-audit-2026-09-13/audit-01"
PRIOR_SHA = "5243eb2213591bf276af25dc417efe70e4beff4e29690cef2c01d6ea8aea0b6f"
NEW_NAMES = (
    "protocol.json",
    "transport_protocol.py",
    "transport_workers.py",
    "transport_check.py",
    "transport_job.py",
    "test_transport.py",
)
SOURCE_NAMES = tuple(f"validation/betse/channel_transport_preflight/{n}" for n in NEW_NAMES) + (
    "validation/betse/contact.py",
    "validation/betse/alignment.py",
    "validation/betse/alignment_protocol.json",
    "validation/betse/requirements-lock.txt",
    "docs/BETSE_CHANNEL_TRANSPORT_PREFLIGHT.md",
    "docs/BETSE_COUPLED_CHANNEL_PLAN.md",
)
MUTABLE = {
    "PROGRESS.md",
    "README.md",
    "docs/BETSE_CAPABILITY_ROADMAP.md",
    "docs/BETSE_PASSIVE_TRAJECTORY_PLAN.md",
    "docs/BETSE_REFERENCE_PLAN.md",
    "docs/DECISIONS.md",
    "validation/betse/README.md",
}


def source_hashes():
    names = set(SOURCE_NAMES) | {str(p.relative_to(c.ROOT)) for p in (c.ROOT / "src").rglob("*.py")}
    return {name: c.sha(c.ROOT / name) for name in sorted(names)}


def prior_closeout():
    c.require(c.sha(PRIOR / "completion.json") == PRIOR_SHA, "Isolated closeout changed")
    receipt = c.read(PRIOR / "completion.json")
    c.require(
        receipt["isolated_gate_qualified"] is True and receipt["failed_comparisons"] == 0,
        "Isolated prerequisite not qualified",
    )
    for name, digest in receipt["files_sha256"].items():
        c.require(c.sha(PRIOR / name) == digest, f"Prior audit payload changed: {name}")
    previous = c.read(PRIOR / "registration.json")
    for name, digest in previous["sources_sha256"].items():
        c.require(c.sha(c.ROOT / name) == digest, f"Prior audit source changed: {name}")
    capture = c.ROOT / previous["capture"]
    c.require(
        {str(p.relative_to(capture)) for p in capture.rglob("*") if p.is_file()}
        == set(previous["capture_sha256"]),
        "Original capture membership changed",
    )
    for name, digest in previous["capture_sha256"].items():
        c.require(c.sha(capture / name) == digest, f"Original capture changed: {name}")
    for name, digest in c.read(capture / "registration.json")["sources_sha256"].items():
        c.require(c.sha(c.ROOT / name) == digest, f"Isolated capture source changed: {name}")
    return {
        "path": str(PRIOR.relative_to(c.ROOT)),
        "completion_sha256": PRIOR_SHA,
        "capture_sha256": previous["capture_sha256"],
        "isolated_gate_qualified": True,
    }


def baseline_hashes():
    sources = source_hashes()
    paths = [
        p
        for directory in ("src", "tests", "configs", "docs", "validation")
        for p in (c.ROOT / directory).rglob("*")
        if p.is_file() and p.suffix in (".py", ".json", ".md")
    ]
    return {
        str(p.relative_to(c.ROOT)): c.sha(p)
        for p in sorted(paths)
        if str(p.relative_to(c.ROOT)) not in MUTABLE | set(sources)
    }


def software_receipt(path):
    c.require(path.is_file() and path.is_relative_to(c.ROOT / "reports"), "Missing preflight XML")
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    identities = []
    for suite in suites:
        c.require(
            all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Software tests did not pass",
        )
        rows = list(suite.findall("testcase"))
        c.require(len(rows) == int(suite.attrib["tests"]), "Wrong XML count")
        c.require(
            all(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped"))
                for row in rows
            ),
            "Rejected software test",
        )
        identities += [row.attrib["classname"] + "::" + row.attrib["name"] for row in rows]
    c.require(
        len(identities) >= 40
        and len(identities) == len(set(identities))
        and all("test_transport" in name for name in identities),
        "Wrong focused suite",
    )
    return {
        "path": str(path.relative_to(c.ROOT)),
        "sha256": c.sha(path),
        "tests": len(identities),
        "identities": identities,
    }


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(
        r["schema"] == "cells.betse_channel_transport_preflight_registration@1", "Wrong stage"
    )
    t.validate_protocol(r["protocol"])
    c.require(r["sources_sha256"] == source_hashes(), "Registered sources changed")
    c.require(r["preserved_sources_sha256"] == baseline_hashes(), "Earlier sources changed")
    c.require(c.sha(c.PRESERVATION) == r["preservation_sha256"], "Preservation anchor changed")
    c.require(c.authenticate_cells()["runtime"] == r["cells_runtime"], "Accepted runtime changed")
    c.require(r["prior_closeout"] == prior_closeout(), "Prerequisite changed")
    c.require(r["base_protocol"] == c.read(t.a.PROTOCOL), "Base setup changed")
    g = c.ROOT / r["protocol"]["geometry_source"]
    c.require(c.sha(g) == r["geometry_source_sha256"], "Prior geometry changed")
    c.require(
        r["expected_geometry"] == {k: c.read(g)[k] for k in t.GEOMETRY_FIELDS},
        "Expected geometry differs",
    )
    c.require(
        software_receipt(c.ROOT / r["software_preflight"]["path"]) == r["software_preflight"],
        "Preflight XML changed",
    )
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Wrong source capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == digest
                for n, digest in r["sources_sha256"].items()
            ),
            "Capsule bytes changed",
        )
    return r


def validate_workers(r, native, cells, output):
    c.require(
        native["engine"] == "unmodified_betse_native_channel_single_transfer"
        and native["upstream_patched"] is False,
        "Wrong native worker",
    )
    c.require(
        cells["engine"] == "unchanged_cells_matched_state_rhs_prescribed_transfer"
        and cells["production_integrator_run"] is False,
        "Wrong Cells worker",
    )
    expected = {
        k: v
        for k, v in r["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(native["installed_python_sha256"] == expected, "Native source differs")
    c.require(
        native["environment"]["packages"] == c.locked_reference_packages(), "Native lock differs"
    )
    c.require(cells["accepted_runtime"] == r["cells_runtime"], "Cells runtime differs")
    c.require(
        cells["device"] == "cpu"
        and cells["x64_enabled"] is True
        and cells["jit_disabled"] is False,
        "Wrong Cells execution regime",
    )
    module = "src/cells/models/finite_extracellular.py"
    c.require(
        cells["production_module_sha256"] == {module: r["sources_sha256"][module]},
        "Wrong Cells implementation",
    )
    for result, interpreter in ((native, c.REFERENCE_PYTHON), (cells, c.CELLS_PYTHON)):
        c.require(
            result["environment"]["python"] == "3.13.5"
            and Path(result["environment"]["executable"]) == interpreter,
            "Wrong interpreter",
        )
        c.require(
            result["full_trajectory_run"] is False and result["warnings"] == [],
            "Unexpected trajectory or Python warning",
        )
        c.require(
            result["registration_sha256"] == c.sha(output / "registration.json"),
            "Worker registration changed",
        )
        c.require(
            result["cpu_affinity"] == r["protocol"]["resources"]["cpu_affinity"], "Wrong CPUs"
        )
    for variant in r["protocol"]["variants"]:
        name = variant["id"]
        c.require(
            native["preparations"][name]["native_config_sha256"]
            == c.sha(output / "native" / name / "native.yaml"),
            "Native YAML receipt differs",
        )


def worker(kind, output):
    r = authenticate(output)
    cap = r["protocol"]["resources"]["max_worker_file_bytes"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))
    from transport_workers import cells_worker, native_worker

    began = time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = native_worker(r, output) if kind == "betse" else cells_worker(r, output)
    result.update(
        {
            "warnings": [
                {"category": w.category.__name__, "message": str(w.message)} for w in caught
            ],
            "registration_sha256": c.sha(output / "registration.json"),
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "elapsed_seconds": time.monotonic() - began,
        }
    )
    c.write(output / f"{kind}.json", result)


def alarm(_signum, _frame):
    raise TimeoutError("Registered overall wall-clock budget exceeded")


def execute(output):
    began = time.monotonic()
    try:
        budget = c.read(t.PROTOCOL)["resources"]
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, budget["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_worker_file_bytes"],) * 2)
        r = authenticate(output)
        c.require(c.inspect_source() == r["upstream"], "Native source changed")
        c.write(
            output / "started.json",
            {"started_utc": datetime.now(UTC).isoformat(), "pid": os.getpid()},
        )
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(output / "matplotlib-cache"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "JAX_PLATFORMS": "cpu",
            "JAX_ENABLE_X64": "true",
            "JAX_DISABLE_JIT": "false",
        }
        env.pop("PYTHONPATH", None)
        for kind, interpreter in (("betse", c.REFERENCE_PYTHON), ("cells", c.CELLS_PYTHON)):
            remaining = budget["total_timeout_seconds"] - (time.monotonic() - began)
            c.require(remaining > 0, "No remaining worker budget")
            with (output / f"{kind}.log").open("x") as log:
                subprocess.run(
                    [
                        str(interpreter),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        kind,
                        str(output),
                    ],
                    cwd=c.ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=min(remaining, budget["worker_timeout_seconds"][kind]),
                )
        native, cells = c.read(output / "betse.json"), c.read(output / "cells.json")
        validate_workers(r, native, cells, output)
        from transport_check import evaluate

        comparison = evaluate(r, native, cells)
        c.write(output / "comparison.json", comparison)
        c.require(comparison["status"] == "pass", "Transport comparison rejected; retain failures")
        authenticate(output)
        c.require(c.inspect_source() == r["upstream"], "Native source changed during execution")
        excluded = {"launch.json", "runner.stdout.log", "runner.stderr.log"}
        payload = {
            str(p.relative_to(output)): c.sha(p)
            for p in output.rglob("*")
            if p.is_file() and str(p.relative_to(output)) not in excluded
        }
        used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(used + 65536 < budget["max_artifact_bytes"], "Artifact budget exceeded")
        c.write(
            output / "completion.json",
            {
                "schema": "cells.betse_channel_transport_preflight_capture@1",
                "status": "capture_pass_pending_audit",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - began,
                "files_sha256": payload,
                "comparison_count": comparison["comparison_count"],
                "failed_comparisons": 0,
                "native_preparations": 4,
                "native_single_updates": 12,
                "cells_matched_transfers_per_backend": 12,
                "artifact_bytes_before_receipt": used,
                "independent_audit_complete": False,
                "coupled_trajectory_qualified": False,
                "biology_validated": False,
                "gpu_tested": False,
                "production_changed": False,
                "automatic_retry": False,
                "automatic_followup": False,
            },
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        c.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "elapsed_seconds": time.monotonic() - began,
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def register(output, preflight):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Use a fresh run directory",
    )
    p = c.read(t.PROTOCOL)
    t.validate_protocol(p)
    accepted, upstream = c.authenticate_cells(), c.inspect_source()
    g = c.ROOT / p["geometry_source"]
    r = {
        "schema": "cells.betse_channel_transport_preflight_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "protocol": p,
        "base_protocol": c.read(t.a.PROTOCOL),
        "sources_sha256": source_hashes(),
        "preserved_sources_sha256": baseline_hashes(),
        "upstream": upstream,
        "cells_runtime": accepted["runtime"],
        "preservation_sha256": c.sha(c.PRESERVATION),
        "prior_closeout": prior_closeout(),
        "software_preflight": software_receipt(preflight),
        "geometry_source_sha256": c.sha(g),
        "expected_geometry": {k: c.read(g)[k] for k in t.GEOMETRY_FIELDS},
    }
    output.mkdir(parents=True, exist_ok=False)
    try:
        c.write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in r["sources_sha256"]:
                archive.write(c.ROOT / name, arcname=name)
        authenticate(output)
    except BaseException:
        c.write(
            output / "registration-failure.json",
            {
                "status": "registration_failed_not_launched",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    return r


def launch(output, preflight):
    r = register(output, preflight)
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    ",".join(map(str, r["protocol"]["resources"]["cpu_affinity"])),
                    str(c.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                ],
                cwd=c.ROOT,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        receipt = {
            "status": "launched_detached",
            "pid": process.pid,
            "launched_utc": datetime.now(UTC).isoformat(),
            "registration_sha256": c.sha(output / "registration.json"),
            "resources": r["protocol"]["resources"],
            "automatic_polling": False,
            "automatic_retry": False,
            "automatic_followup": False,
        }
        c.write(output / "launch.json", receipt)
        return receipt
    except BaseException:
        c.write(
            output / "launch-failure.json",
            {"status": "launch_failed", "traceback": traceback.format_exc()},
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    launcher = sub.add_parser("launch")
    launcher.add_argument("output", type=Path)
    launcher.add_argument("--preflight", type=Path, required=True)
    sub.add_parser("execute").add_argument("output", type=Path)
    child = sub.add_parser("worker")
    child.add_argument("kind", choices=("betse", "cells"))
    child.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        print(json.dumps(launch(args.output.resolve(), args.preflight.resolve()), sort_keys=True))
    elif args.action == "execute":
        execute(args.output.resolve())
    else:
        worker(args.kind, args.output.resolve())
