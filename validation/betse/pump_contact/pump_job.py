"""Register and detach one bounded source-contact panel; never poll or auto-audit."""

import argparse
import ast
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

import pump_reference as ref

c = ref.c
HERE = Path(__file__).resolve().parent
SOURCES = tuple(
    f"validation/betse/pump_contact/{name}"
    for name in (
        "pump_reference.py",
        "pump_array.py",
        "pump_workers.py",
        "pump_job.py",
        "test_pump_contact.py",
    )
) + (
    "validation/betse/contact.py",
    "validation/betse/requirements-lock.txt",
    "docs/BETSE_PUMP_CONTACT.md",
    "validation/betse/biological_candidates/xenopus_costa_1989.json",
    "reports/REF004D_TIMED_RELEASE_CLOSEOUT.md",
    "reports/REF005A_PUMP_CONTACT_HANDOFF.md",
)
PRIOR = c.ROOT / "runs/ref-004d-timed-release-audit-2026-09-16/audit-01"
PRIOR_SHA = "f144dea687a1140409b549237faf63cf1b758e2aafe8b91091fd6055f7c5b8a7"


def sources():
    return {name: c.sha(c.ROOT / name) for name in SOURCES}


def prior():
    c.require(c.sha(PRIOR / "completion.json") == PRIOR_SHA, "Prior closeout changed")
    receipt = c.read(PRIOR / "completion.json")
    c.require(
        receipt["status"] == "timed_release_pilot_audit_closed"
        and receipt["release_response_qualified"] is True,
        "Prior scope not closed",
    )
    c.require(
        all(c.sha(PRIOR / n) == digest for n, digest in receipt["files_sha256"].items()),
        "Prior closeout payload changed",
    )
    return {"path": str(PRIOR.relative_to(c.ROOT)), "completion_sha256": PRIOR_SHA}


def source_defaults():
    """Check literal parameter values against the actual pinned source, not its comments."""
    expected = {
        "cATP": 1.5,
        "cADP": 0.1,
        "cPi": 0.1,
        "KmNK_Na": 12.0,
        "KmNK_K": 0.2,
        "KmNK_ATP": 0.5,
        "deltaGATP": -37000.0,
    }
    tree = ast.parse((c.SOURCE / "betse/science/parameters.py").read_text())
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and target.attr in expected
                ):
                    c.require(target.attr not in found, "Ambiguous source default")
                    found[target.attr] = float(ast.literal_eval(node.value))
    c.require(found == expected, "Source pump defaults changed")
    return found


def test_receipt(path):
    path = path.resolve()
    c.require(path.is_file() and path.is_relative_to(c.ROOT / "reports"), "Missing test receipt")
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    ids = []
    c.require(bool(suites), "No test suites")
    for suite in suites:
        c.require(
            all(int(suite.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped")),
            "Rejected software receipt",
        )
        cases = list(suite.findall("testcase"))
        c.require(len(cases) == int(suite.attrib["tests"]), "Wrong test count")
        c.require(
            all(
                not any(row.find(k) is not None for k in ("failure", "error", "skipped"))
                for row in cases
            ),
            "Rejected test case",
        )
        ids += [row.attrib["classname"] + "::" + row.attrib["name"] for row in cases]
    c.require(
        len(ids) >= 40
        and len(ids) == len(set(ids))
        and all("test_pump_contact" in name for name in ids),
        "Wrong focused test coverage",
    )
    return {
        "path": str(path.relative_to(c.ROOT)),
        "sha256": c.sha(path),
        "tests": len(ids),
        "identities": ids,
    }


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(r["schema"] == "cells.betse_nak_contact_registration@1", "Wrong registration")
    ref.validate_protocol(r["protocol"])
    c.require(r["sources_sha256"] == sources(), "Contact source changed")
    c.require(r["upstream"] == c.inspect_source(), "Upstream changed")
    c.require(r["source_defaults"] == source_defaults(), "Source defaults changed")
    c.require(r["prior_closeout"] == prior(), "Prior changed")
    c.require(r["preservation_sha256"] == c.sha(c.PRESERVATION), "Preservation changed")
    c.require(r["cells_runtime"] == c.authenticate_cells()["runtime"], "Production changed")
    c.require(r["software"] == test_receipt(c.ROOT / r["software"]["path"]), "Tests changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(SOURCES) and set(archive.namelist()) == set(SOURCES),
            "Wrong source capsule",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == digest
                for n, digest in r["sources_sha256"].items()
            ),
            "Capsule changed",
        )
    return r


def register(output, tests):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Use a fresh run directory",
    )
    plan = ref.protocol()
    ref.validate_protocol(plan)
    accepted = c.authenticate_cells()
    r = {
        "schema": "cells.betse_nak_contact_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "protocol": plan,
        "sources_sha256": sources(),
        "upstream": c.inspect_source(),
        "source_defaults": source_defaults(),
        "prior_closeout": prior(),
        "preservation_sha256": c.sha(c.PRESERVATION),
        "cells_runtime": accepted["runtime"],
        "prototype_environment": c.environment(),
        "software": test_receipt(tests),
    }
    output.mkdir(parents=True, exist_ok=False)
    try:
        c.write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in SOURCES:
                archive.write(c.ROOT / name, arcname=name)
        authenticate(output)
    except BaseException:
        c.write(
            output / "registration-failure.json",
            {
                "status": "not_launched",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    return r


def environment(output):
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(output / "mplconfig"),
            "JAX_PLATFORMS": "cpu",
            "JAX_ENABLE_X64": "true",
            "JAX_DISABLE_JIT": "false",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def worker(output, engine):
    import pump_workers

    c.require(not (output / f"{engine}.json").exists(), "Worker already attempted")
    r = authenticate(output)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        result = getattr(pump_workers, engine)(r)
    result["warnings"] = [str(row.message) for row in captured]
    result["registration_sha256"] = c.sha(output / "registration.json")
    c.write(output / f"{engine}.json", result)
    c.require(not captured, "Worker warnings retained; contact not qualified")


def deadline(_signum, _frame):
    raise TimeoutError("Pump contact deadline exceeded")


def validate_workers(native, prototype, registration_sha):
    c.require(native["engine"] == "unmodified_betse_pumpNaKATP", "Wrong native engine")
    c.require(prototype["engine"] == "validation_only_nak_array_law", "Wrong prototype engine")
    c.require(
        set(native["results"]) == {"native"}
        and set(prototype["results"]) == {"numpy", "jax_eager", "jax_jit"},
        "Worker engine overlap or missing backend",
    )
    c.require(
        prototype["dtype"] == "float64" and prototype["backend"] == "cpu",
        "Wrong prototype execution mode",
    )
    c.require(
        all(
            row["registration_sha256"] == registration_sha
            and not row["warnings"]
            and row["input_unchanged"] is True
            for row in (native, prototype)
        ),
        "Worker provenance or input check failed",
    )
    c.require(
        native["met_ignored"] is True and native["third_is_outward_na"] is True,
        "Native call contract failed",
    )


def execute(output):
    c.require(not (output / "started.json").exists(), "Execution already attempted")
    began = time.monotonic()
    plan = ref.protocol()
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, plan["total_timeout_seconds"])
    try:
        c.write(
            output / "started.json",
            {"started_utc": datetime.now(UTC).isoformat(), "pid": os.getpid()},
        )
        r = authenticate(output)
        c.require(sorted(os.sched_getaffinity(0)) == plan["cpu_affinity"], "Wrong CPU affinity")
        resource.setrlimit(resource.RLIMIT_FSIZE, (plan["per_file_limit_bytes"],) * 2)
        for engine, python in (("native", c.REFERENCE_PYTHON), ("prototype", c.CELLS_PYTHON)):
            with (
                (output / f"{engine}.stdout.log").open("x") as out,
                (output / f"{engine}.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    [
                        str(python),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        str(output),
                        "--engine",
                        engine,
                    ],
                    cwd=c.ROOT,
                    env=environment(output),
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    check=True,
                    timeout=plan["worker_timeout_seconds"],
                )
        native, prototype = (c.read(output / f"{name}.json") for name in ("native", "prototype"))
        registration_sha = c.sha(output / "registration.json")
        validate_workers(native, prototype, registration_sha)
        result = ref.evaluate(plan, {**native["results"], **prototype["results"]})
        c.write(output / "comparison.json", result)
        c.require(result["failures"] == 0, "Pump contact comparison failed; rows retained")
        authenticate(output)
        paths = [p for p in output.rglob("*") if p.is_file()]
        used = sum(p.stat().st_size for p in paths)
        c.require(used <= plan["artifact_limit_bytes"] - 1024**2, "Artifact budget exceeded")
        c.require(
            all(p.stat().st_size <= plan["per_file_limit_bytes"] for p in paths),
            "Artifact per-file budget exceeded",
        )
        # Operational logs can still be open. Bind immutable evidence, not a live log.
        payload = {
            name: c.sha(output / name)
            for name in (
                "registration.json",
                "sources.zip",
                "started.json",
                "native.json",
                "prototype.json",
                "comparison.json",
            )
        }
        c.write(
            output / "completion.json",
            {
                "schema": "cells.betse_nak_contact_capture@1",
                "status": "contact_pass_pending_audit",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - began,
                "files_sha256": payload,
                "registration_sha256": registration_sha,
                "comparisons": result["comparisons"],
                "failures": 0,
                "fixtures_per_profile": len(plan["profiles"]["source_constants"]["cases"]),
                "profiles": len(plan["profiles"]),
                "engines": list(ref.ENGINES),
                "software_tests": r["software"]["tests"],
                "artifact_bytes_before_receipt": used,
                "production_changed": False,
                "production_pump_implemented": False,
                "coupled_trajectory_qualified": False,
                "biology_validated": False,
                "gpu_tested": False,
                "independent_saved_data_audit_complete": False,
                "automatic_retry": False,
                "automatic_followup": False,
            },
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if not (output / "failure.json").exists():
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


def launch(output, tests):
    r = register(output, tests)
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    ",".join(map(str, r["protocol"]["cpu_affinity"])),
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
                env=environment(output),
            )
        result = {
            "status": "launched_detached",
            "pid": process.pid,
            "launched_utc": datetime.now(UTC).isoformat(),
            "registration_sha256": c.sha(output / "registration.json"),
            "automatic_polling": False,
            "automatic_retry": False,
            "automatic_followup": False,
        }
        c.write(output / "launch.json", result)
        return result
    except BaseException:
        c.write(
            output / "launch-failure.json",
            {
                "status": "launch_failed",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "execute", "worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--engine", choices=("native", "prototype"))
    args = parser.parse_args()
    output = args.output.resolve()
    if args.action == "launch":
        c.require(args.tests is not None, "Need focused software receipt")
        print(json.dumps(launch(output, args.tests), sort_keys=True))
    elif args.action == "execute":
        execute(output)
    else:
        c.require(args.engine is not None, "Need worker engine")
        worker(output, args.engine)


if __name__ == "__main__":
    main()
