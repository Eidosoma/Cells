"""One detached isolated-gate capture, with immutable inputs and durable failure.

No retry, polling, automatic audit, coupled-cell campaign or production edits.
"""

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

import gate_reference as ref

c = ref.c
HERE = Path(__file__).resolve().parent
NEW_NAMES = (
    "protocol.json",
    "gate_reference.py",
    "gate_workers.py",
    "gate_job.py",
    "test_gate_contact.py",
)
SOURCE_NAMES = tuple(f"validation/betse/voltage_gate_contact/{n}" for n in NEW_NAMES) + (
    "validation/betse/contact.py",
    "validation/betse/requirements-lock.txt",
    "src/cells/processes/voltage_gates.py",
    "src/cells/numerics/fixed_step.py",
    "configs/reference/voltage_gated_channel_v1.json",
    "docs/BETSE_VOLTAGE_GATE_CONTACT.md",
)
PRIOR = c.ROOT / "runs/ref-003e1-refined-response-audit-2026-09-13/audit-01"
PRIOR_SHA = "c4352798787638b1b8749672cf18376d01b404debbde0938304733792f0c75f6"


def source_hashes():
    return {name: c.sha(c.ROOT / name) for name in SOURCE_NAMES}


def prior_closeout():
    """Authenticate the completed receipt; do not rerun its numerical audit."""
    c.require(c.sha(PRIOR / "completion.json") == PRIOR_SHA, "Prior closeout changed")
    receipt = c.read(PRIOR / "completion.json")
    c.require(
        receipt["finest_held_response_qualified"] is True
        and receipt["required_failed_comparisons"] == 0
        and receipt["diagnostic_failed_comparisons"] == 4173,
        "Wrong prior scope",
    )
    c.require(
        all(c.sha(PRIOR / name) == digest for name, digest in receipt["files_sha256"].items()),
        "Prior closeout payload changed",
    )
    return {
        "path": str(PRIOR.relative_to(c.ROOT)),
        "completion_sha256": PRIOR_SHA,
        "finest_held_response_qualified": True,
        "diagnostic_failures_retained": 4173,
    }


def software_receipt(path):
    c.require(
        path.is_file() and path.is_relative_to(c.ROOT / "reports"), "Missing software receipt"
    )
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    c.require(bool(suites), "No test suites")
    identities = []
    for suite in suites:
        c.require(
            all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Software preflight did not pass",
        )
        rows = list(suite.findall("testcase"))
        c.require(int(suite.attrib["tests"]) == len(rows), "Wrong software test count")
        c.require(
            all(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped"))
                for row in rows
            ),
            "Rejected test case",
        )
        identities += [row.attrib["classname"] + "::" + row.attrib["name"] for row in rows]
    c.require(
        len(identities) >= 20
        and len(set(identities)) == len(identities)
        and all("test_gate_contact" in name for name in identities),
        "Wrong focused tests",
    )
    return {
        "path": str(path.relative_to(c.ROOT)),
        "sha256": c.sha(path),
        "tests": len(identities),
        "identities": identities,
    }


def authenticate_registration(output):
    r = c.read(output / "registration.json")
    c.require(r["schema"] == "cells.betse_kv1p5_contact_registration@1", "Wrong registration")
    ref.validate_protocol(r["protocol"])
    c.require(r["sources_sha256"] == source_hashes(), "Source changed after registration")
    c.require(c.sha(c.PRESERVATION) == r["preservation_sha256"], "Accepted preservation changed")
    c.require(c.authenticate_cells()["runtime"] == r["cells_runtime"], "Accepted runtime changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            set(archive.namelist()) == set(r["sources_sha256"])
            and len(archive.namelist()) == len(r["sources_sha256"]),
            "Wrong capsule coverage",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == digest
                for n, digest in r["sources_sha256"].items()
            ),
            "Capsule bytes differ",
        )
    c.require(
        software_receipt(c.ROOT / r["software_preflight"]["path"]) == r["software_preflight"],
        "Preflight receipt changed",
    )
    c.require(prior_closeout() == r["prior_closeout"], "Prior receipt differs")
    return r


def validate_workers(r, native, cells, registration_sha):
    c.require(native["engine"] == "unmodified_betse_Kv1p5_init_run", "Wrong native engine")
    c.require(
        native["initial_open_fraction_origin"] == "derived_m_times_h_before_first_native_update",
        "Wrong initial open-fraction origin",
    )
    c.require(
        cells["engine"] == "unchanged_cells_kinetics_shared_rk4_isolated_harness",
        "Wrong Cells engine",
    )
    expected = {
        name: digest
        for name, digest in r["upstream"]["files_sha256"].items()
        if name.startswith("betse/") and name.endswith(".py")
    }
    c.require(native["installed_python_sha256"] == expected, "Native source mismatch")
    c.require(
        native["environment"]["packages"] == c.locked_reference_packages(), "Native lock differs"
    )
    c.require(
        native["environment"]["python"] == "3.13.5"
        and Path(native["environment"]["executable"]) == c.REFERENCE_PYTHON,
        "Wrong native interpreter",
    )
    native_modules = ["science/channels/vg_k.py", "science/channels/channelsabc.py"]
    package = c.REFERENCE_PYTHON.parent.parent / "lib/python3.13/site-packages/betse"
    c.require(
        native["module_paths"] == [str(package / name) for name in native_modules],
        "Native module origins differ",
    )
    c.require(
        native["native_metadata"]
        == {
            "time_unit": 1000.0,
            "voltage_correction_mV": 0.0,
            "powers": [1, 1],
            "ions": ["K"],
            "relative_permeability": [1.0],
            "targets": None,
            "declared_unused_reversal_mV": -65,
        },
        "Native channel metadata differs",
    )
    c.require(cells["accepted_runtime"] == r["cells_runtime"], "Cells runtime mismatch")
    c.require(Path(cells["environment"]["executable"]) == c.CELLS_PYTHON, "Wrong Cells interpreter")
    c.require(
        cells["module_sha256"]
        == {
            n: r["sources_sha256"][n]
            for n in ("src/cells/processes/voltage_gates.py", "src/cells/numerics/fixed_step.py")
        },
        "Production kernel identity changed",
    )
    c.require(
        cells["device"] == "cpu"
        and cells["x64_enabled"] is True
        and cells["jit_disabled"] is False
        and cells["trajectory_backend"] == "jax_jit"
        and cells["kinetic_backends"] == list(ref.BACKENDS)
        and cells["production_world_runner_executed"] is False,
        "Wrong Cells execution scope",
    )
    for worker in (native, cells):
        c.require(worker["registration_sha256"] == registration_sha, "Worker registration differs")
        c.require(worker["warnings"] == [], "Worker emitted Python warnings")
        c.require(
            worker["dtype"] == "float64" and worker["kinetic_input_unchanged"] is True,
            "Wrong arithmetic/input contract",
        )
        c.require(
            worker["cpu_affinity"] == r["protocol"]["resources"]["cpu_affinity"],
            "Wrong worker CPU affinity",
        )


def worker(kind, output):
    r = authenticate_registration(output)
    cap = r["protocol"]["resources"]["max_worker_file_bytes"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))
    from gate_workers import cells_worker, native_worker

    began = time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = native_worker(r) if kind == "betse" else cells_worker(r)
    result |= {
        "warnings": [{"category": w.category.__name__, "message": str(w.message)} for w in caught],
        "registration_sha256": c.sha(output / "registration.json"),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "elapsed_seconds": time.monotonic() - began,
    }
    c.write(output / f"{kind}.json", result)


def alarm(_signum, _frame):
    raise TimeoutError("Registered total wall budget exceeded")


def execute(output):
    began = time.monotonic()
    try:
        # Arm before expensive provenance checks; the fixed source-bound protocol
        # is verified again below. subprocess.run kills its worker on exception.
        budget = c.read(ref.PROTOCOL)["resources"]
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, budget["total_timeout_seconds"])
        r = authenticate_registration(output)
        c.require(c.inspect_source() == r["upstream"], "Upstream checkout changed")
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
        }
        env.pop("PYTHONPATH", None)
        for kind, interpreter in (("betse", c.REFERENCE_PYTHON), ("cells", c.CELLS_PYTHON)):
            remaining = budget["total_timeout_seconds"] - (time.monotonic() - began)
            c.require(remaining > 0, "No remaining worker time")
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
                    timeout=min(budget["worker_timeout_seconds"][kind], remaining),
                )
        native, cells = c.read(output / "betse.json"), c.read(output / "cells.json")
        validate_workers(r, native, cells, c.sha(output / "registration.json"))
        result = ref.evaluate(r["protocol"], native, cells)
        c.write(output / "comparison.json", result)
        c.require(result["status"] == "pass", "Gate comparisons rejected; retain full comparison")
        authenticate_registration(output)
        c.require(c.inspect_source() == r["upstream"], "Upstream changed during capture")
        excluded = {"launch.json", "runner.stdout.log", "runner.stderr.log"}
        payloads = {
            str(p.relative_to(output)): c.sha(p)
            for p in output.rglob("*")
            if p.is_file() and str(p.relative_to(output)) not in excluded
        }
        used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(used + 65536 < budget["max_artifact_bytes"], "Artifact budget exceeded")
        c.write(
            output / "completion.json",
            {
                "schema": "cells.betse_kv1p5_contact_capture@1",
                "status": "capture_pass_pending_audit",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - began,
                "files_sha256": payloads,
                "registration_sha256": c.sha(output / "registration.json"),
                "comparison_count": result["comparison_count"],
                "failed_comparisons": 0,
                "isolated_gate_protocols": 6,
                "trajectories_per_engine": 18,
                "scope": r["protocol"]["scope"],
                "artifact_bytes_before_receipt": used,
                "independent_audit_complete": False,
                "coupled_cell_qualified": False,
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
    protocol = c.read(ref.PROTOCOL)
    ref.validate_protocol(protocol)
    accepted = c.authenticate_cells()
    r = {
        "schema": "cells.betse_kv1p5_contact_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "protocol": protocol,
        "sources_sha256": source_hashes(),
        "upstream": c.inspect_source(),
        "cells_runtime": accepted["runtime"],
        "preservation_sha256": c.sha(c.PRESERVATION),
        "prior_closeout": prior_closeout(),
        "software_preflight": software_receipt(preflight),
    }
    # Bind the earlier independently reviewed equations and source license too.
    reviewed = c.read(c.ROOT / "configs/reference/voltage_gated_channel_v1.json")["source"]
    c.require(reviewed["commit"] == r["upstream"]["revision"], "Reviewed source revision differs")
    c.require(
        all(
            r["upstream"]["files_sha256"][name] == value["sha256"]
            for name, value in reviewed["files"].items()
        ),
        "Reviewed channel source changed",
    )
    output.mkdir(parents=True, exist_ok=False)
    try:
        c.write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in r["sources_sha256"]:
                archive.write(c.ROOT / name, arcname=name)
        authenticate_registration(output)
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
