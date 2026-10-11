"""Bounded native SVG single-centre geometry feasibility, without a solver loop."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import alignment as a
import contact as c
import preparation

FILES = (
    "geometry_probe.py",
    "single_cell.svg",
    "alignment.py",
    "alignment_protocol.json",
    "contact.py",
)
PRIOR_HANDOFF = c.ROOT / "reports/ref-003b1-closeout.json"


def hashes():
    return {name: c.sha(c.HERE / name) for name in FILES}


def authenticate():
    previous = c.read(PRIOR_HANDOFF)
    c.require(previous["status"] == "recorded_not_qualified", "Prior status differs")
    c.require(
        preparation.audit(c.ROOT / "runs/ref-003b1-2026-09-12/alignment-05")
        == c.read(c.ROOT / "reports/ref-003b1-preparation-audit.json"),
        "Prior diagnostic differs",
    )
    for name, attempt in previous["retained_attempts"].items():
        directory = c.ROOT / "runs/ref-003b1-2026-09-12" / name
        for filename, digest in attempt["files_sha256"].items():
            c.require(c.sha(directory / filename) == digest, "Earlier preparation changed")
    return previous


def worker(output):
    import betse
    import numpy as np
    from betse.science.parameters import Parameters
    from betse.science.simrunner import SimRunner
    from ruamel.yaml import YAML

    registration = c.read(output / "registration.json")
    c.require(registration["sources"] == hashes(), "Worker source changed")
    package = Path(betse.__file__).resolve().parent
    installed = {
        f"betse/{path.relative_to(package)}": c.sha(path) for path in package.rglob("*.py")
    }
    expected = {
        k: v
        for k, v in registration["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(installed == expected, "Native installed source differs")
    c.require(c.environment()["packages"] == c.locked_reference_packages(), "Dependencies differ")
    parser = YAML(typ="safe")
    parser.default_flow_style = False
    with (c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        config = a.configuration(parser.load(handle), registration["base_protocol"], output)
    world = config["world options"]
    world["simulate single cell"] = False
    world["import from svg"]["svg override"] = True
    world["import from svg"]["cells from svg"] = "single_cell.svg"
    world["import from svg"]["svg size"] = 500
    shutil.copyfile(c.HERE / "single_cell.svg", output / "single_cell.svg")
    with (output / "native.yaml").open("x") as handle:
        parser.dump(config, handle)
    p = Parameters()
    p.load(str(output / "native.yaml"))
    c.require(p.svg_override and not p.single_cell and not p.molecules_enabled, "Wrong input mode")
    np.random.seed(registration["base_protocol"]["seed"])
    result = {
        "configuration_loaded": True,
        "native_seed_completed": False,
        "requested_explicit_centres": 1,
        "environment": c.environment(),
        "installed_python_sha256": installed,
        "native_config_sha256": c.sha(output / "native.yaml"),
        "registration_sha256": c.sha(output / "registration.json"),
        "trajectory_run": False,
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            phase = SimRunner(p).seed()
            result |= {
                "native_seed_completed": True,
                "cell_count": len(phase.cells.cell_i),
                "membrane_count": len(phase.cells.mem_i),
            }
        except Exception as error:
            result |= {
                "exception_type": type(error).__name__,
                "exception": str(error),
                "traceback": traceback.format_exc(),
            }
    result["warnings"] = [
        {"category": w.category.__name__, "message": str(w.message)} for w in caught
    ]
    c.write(output / "native_result.json", result)


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    try:
        authenticate()
        names = (
            subprocess.check_output(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
                cwd=c.ROOT,
            )
            .decode()
            .split("\0")
        )
        registration = {
            "schema": "cells.betse_svg_geometry_probe@1",
            "registered_utc": datetime.now(UTC).isoformat(),
            "base_protocol": c.read(a.PROTOCOL),
            "upstream": c.inspect_source(),
            "sources": hashes(),
            "prior_handoff_sha256": c.sha(PRIOR_HANDOFF),
            "worker_timeout_seconds": 20,
            "configuration_intervention": (
                "Disable single_cell preset; import exactly one explicit SVG centre"
            ),
            "baseline_sha256": {name: c.sha(c.ROOT / name) for name in sorted(set(names) - {""})},
        }
        c.write(output / "registration.json", registration)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in FILES:
                archive.write(c.HERE / name, arcname=name)
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(output / "matplotlib-cache"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
        env.pop("PYTHONPATH", None)
        with (output / "stdout.log").open("x") as out, (output / "stderr.log").open("x") as err:
            subprocess.run(
                [
                    "taskset",
                    "-c",
                    "0-3",
                    str(c.REFERENCE_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "worker",
                    str(output),
                ],
                env=env,
                cwd=c.ROOT,
                stdout=out,
                stderr=err,
                stdin=subprocess.DEVNULL,
                timeout=20,
                check=True,
            )
        result = c.read(output / "native_result.json")
        c.require(
            hashes() == registration["sources"] and c.inspect_source() == registration["upstream"],
            "Source changed",
        )
        c.require(time.monotonic() - started < 30, "Geometry probe exceeded wall limit")
        c.write(
            output / "completion.json",
            {
                "status": "geometry_probe_completed",
                "one_cell_seed_succeeded": result["native_seed_completed"]
                and result.get("cell_count") == 1,
                "seconds": time.monotonic() - started,
                "files_sha256": {
                    str(p.relative_to(output)): c.sha(p) for p in output.rglob("*") if p.is_file()
                },
            },
        )
        print(
            json.dumps(
                {
                    "status": "geometry_probe_completed",
                    "seed_completed": result["native_seed_completed"],
                    "exception_type": result.get("exception_type"),
                    "seconds": time.monotonic() - started,
                }
            )
        )
    except BaseException:
        c.write(
            output / "failure.json",
            {"status": "probe_execution_failed", "traceback": traceback.format_exc()},
        )
        raise


def audit(output):
    completed = c.read(output / "completion.json")
    c.require(
        completed["status"] == "geometry_probe_completed"
        and not (output / "failure.json").exists(),
        "Incomplete geometry probe",
    )
    names = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()} - {
        "completion.json"
    }
    c.require(names == set(completed["files_sha256"]), "Geometry payload coverage differs")
    for name, digest in completed["files_sha256"].items():
        c.require(c.sha(output / name) == digest, "Geometry payload differs")
    registered = c.read(output / "registration.json")
    c.require(registered["sources"] == hashes(), "Use captured geometry source context")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(FILES) and set(archive.namelist()) == set(FILES),
            "Capsule coverage differs",
        )
        for name, digest in registered["sources"].items():
            c.require(
                hashlib.sha256(archive.read(name)).hexdigest() == digest, "Capsule bytes differ"
            )
    native = c.read(output / "native_result.json")
    c.require(
        native["registration_sha256"] == c.sha(output / "registration.json")
        and native["native_config_sha256"] == c.sha(output / "native.yaml"),
        "Native inputs differ",
    )
    c.require(
        native["configuration_loaded"] is True and native["trajectory_run"] is False, "Wrong scope"
    )
    authenticate()
    c.require(c.inspect_source() == registered["upstream"], "Pinned source differs")
    return {
        "status": "geometry_probe_audited",
        "one_cell_seed_succeeded": completed["one_cell_seed_succeeded"],
        "native_exception_type": native.get("exception_type"),
        "completion_sha256": c.sha(output / "completion.json"),
        "upstream_calls": 0,
        "trajectory_calls": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "worker", "audit"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.action == "capture":
        capture(output)
    elif args.action == "worker":
        worker(output)
    else:
        result = audit(output)
        c.write(args.receipt, result)
        print(json.dumps(result))
