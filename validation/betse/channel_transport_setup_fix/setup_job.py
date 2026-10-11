"""One explicitly approved setup-corrected capture; no change to numerical criteria."""

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

import setup_context as setup

c, t = setup.c, setup.t
base_job = setup.base_job
NEW_NAMES = (
    "amendment.json",
    "setup_context.py",
    "native_setup_fix.py",
    "native_config_contract.py",
    "setup_job.py",
    "test_transport_setup_fix.py",
)


def source_hashes():
    names = (
        set(base_job.source_hashes())
        | {f"validation/betse/channel_transport_setup_fix/{name}" for name in NEW_NAMES}
        | {"docs/BETSE_CHANNEL_SETUP_FIX.md"}
    )
    return {name: c.sha(c.ROOT / name) for name in sorted(names)}


def software_receipt(path):
    receipt = base_job.software_receipt(path)
    names = receipt["identities"]
    old = [n for n in names if "channel_transport_preflight.test_transport::" in n]
    new = [n for n in names if "channel_transport_setup_fix.test_transport_setup_fix::" in n]
    c.require(
        len(old) == 76 and len(new) >= 20 and len(old) + len(new) == len(names),
        "Require original 76 tests and the setup-correction regression suite",
    )
    return receipt | {"original_tests": len(old), "new_tests": len(new)}


def configuration_contract(path):
    c.require(
        path.is_dir() and path.is_relative_to(c.ROOT / "reports"), "Missing native contract packet"
    )
    c.require(not (path / "data/failure.json").exists(), "Native configuration contract failed")
    result = c.read(path / "data/result.json")
    c.require(
        result["schema"] == "cells.betse_channel_configuration_contract@1"
        and result["status"] == "pass"
        and result["warnings"] == [],
        "Wrong contract result",
    )
    c.require(
        result["native_parameter_loader_used"] is True
        and all(
            result[k] is False
            for k in ("native_world_seeded", "native_network_initialized", "transport_executed")
        ),
        "Contract check scope expanded",
    )
    c.require(
        result["amendment_sha256"] == c.sha(setup.AMENDMENT)
        and result["script_sha256"] == c.sha(setup.HERE / "native_config_contract.py")
        and result["configuration_provider_sha256"] == c.sha(setup.HERE / "setup_context.py"),
        "Native contract sources changed",
    )
    original = setup.authenticate_preservation()
    expected = {
        k: v
        for k, v in original["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(result["installed_python_sha256"] == expected, "Native contract source mismatch")
    c.require(
        result["environment"]["packages"] == c.locked_reference_packages()
        and Path(result["environment"]["executable"]) == c.REFERENCE_PYTHON
        and result["environment"]["python"] == "3.13.5",
        "Native contract environment differs",
    )
    c.require(
        result["cpu_affinity"] == original["protocol"]["resources"]["cpu_affinity"],
        "Wrong contract CPU affinity",
    )
    variants = original["protocol"]["variants"]
    c.require(
        [row["id"] for row in result["rows"]] == [v["id"] for v in variants],
        "Incomplete native configuration coverage",
    )
    for row, variant in zip(result["rows"], variants, strict=True):
        for version, value, allowed in (("original", None, False), ("corrected", [], True)):
            c.require(
                row["loaded"][version]
                == {
                    "biomolecules": value,
                    "accepted_by_tissue_init_annotation": allowed,
                    "network_enabled": variant["network"],
                    "temperature_K": 298.15,
                    "init_dt_s": 25e-6,
                    "sim_dt_s": 25e-6,
                },
                "Native YAML/type regression differs",
            )
            config = path / "data" / variant["id"] / f"{version}.yaml"
            c.require(row["yaml_sha256"][version] == c.sha(config), "Regression YAML changed")
    return {
        "path": str(path.relative_to(c.ROOT)),
        "files_sha256": setup.packet_hashes(path),
        "result_sha256": c.sha(path / "data/result.json"),
        "variants": len(variants),
        "native_world_preparation_claimed": False,
    }


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(
        r["schema"] == "cells.betse_channel_transport_preflight_registration@2", "Wrong stage"
    )
    setup.validate_amendment(r["configuration_amendment"])
    original = setup.authenticate_preservation()
    c.require(
        c.sha(setup.PRESERVED) == r["failure_preservation_sha256"], "Failure preservation changed"
    )
    c.require(r["sources_sha256"] == source_hashes(), "Corrected capture sources changed")
    for key in (
        "protocol",
        "base_protocol",
        "preserved_sources_sha256",
        "upstream",
        "cells_runtime",
        "preservation_sha256",
        "prior_closeout",
        "geometry_source_sha256",
        "expected_geometry",
    ):
        c.require(r[key] == original[key], f"Unapproved scientific/provenance change: {key}")
    c.require(
        software_receipt(c.ROOT / r["software_preflight"]["path"]) == r["software_preflight"],
        "Correction test receipt changed",
    )
    c.require(
        configuration_contract(c.ROOT / r["configuration_contract"]["path"])
        == r["configuration_contract"],
        "Native configuration regression changed",
    )
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Incorrect corrected source capsule",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == digest
                for n, digest in r["sources_sha256"].items()
            ),
            "Corrected capsule bytes changed",
        )
    return r


def validate_workers(r, native, cells, output):
    base_job.validate_workers(r, native, cells, output)
    for result in (native, cells):
        c.require(
            result["configuration_amendment_sha256"] == c.sha(setup.AMENDMENT),
            "Wrong worker amendment",
        )


def worker(kind, output):
    r = authenticate(output)
    cap = r["protocol"]["resources"]["max_worker_file_bytes"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))
    from native_setup_fix import native_worker
    from transport_workers import cells_worker

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
    result["configuration_amendment_sha256"] = c.sha(setup.AMENDMENT)
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
                "schema": "cells.betse_channel_transport_preflight_capture@2",
                "configuration_amendment": r["configuration_amendment"],
                "failure_preservation_sha256": r["failure_preservation_sha256"],
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


def register(output, preflight, contract):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Use a fresh run directory",
    )
    original = setup.authenticate_preservation()
    amendment = c.read(setup.AMENDMENT)
    setup.validate_amendment(amendment)
    c.require(c.inspect_source() == original["upstream"], "Native checkout changed")
    r = original | {
        "schema": "cells.betse_channel_transport_preflight_registration@2",
        "registered_utc": datetime.now(UTC).isoformat(),
        "configuration_amendment": amendment,
        "failure_preservation_sha256": c.sha(setup.PRESERVED),
        "sources_sha256": source_hashes(),
        "software_preflight": software_receipt(preflight),
        "configuration_contract": configuration_contract(contract),
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


def launch(output, preflight, contract):
    r = register(output, preflight, contract)
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
    sub.add_parser("preserve")
    launcher = sub.add_parser("launch")
    launcher.add_argument("output", type=Path)
    launcher.add_argument("--preflight", type=Path, required=True)
    launcher.add_argument("--contract", type=Path, required=True)
    sub.add_parser("execute").add_argument("output", type=Path)
    child = sub.add_parser("worker")
    child.add_argument("kind", choices=("betse", "cells"))
    child.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "preserve":
        print(json.dumps(setup.preserve(), sort_keys=True))
    elif args.action == "launch":
        print(
            json.dumps(
                launch(args.output.resolve(), args.preflight.resolve(), args.contract.resolve()),
                sort_keys=True,
            )
        )
    elif args.action == "execute":
        execute(args.output.resolve())
    else:
        worker(args.kind, args.output.resolve())
