"""Launch explicitly accepted, frozen full INIT/SIM refinements; never poll jobs."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def verify_bundle(bundle):
    manifest = read(bundle / "manifest.json")
    for name, expected in manifest["file_sha256"].items():
        assert sha(bundle / name) == expected, name
    return manifest


def has_binding(value, path, digest):
    if isinstance(value, dict):
        if value.get("path") == str(path) and value.get("sha256") == digest:
            return True
        strings = [v for v in value.values() if isinstance(v, str)]
        if str(path) in strings and digest in strings:
            return True
        return any(has_binding(v, path, digest) for v in value.values())
    if isinstance(value, list):
        return any(has_binding(v, path, digest) for v in value)
    return False


def admission(bundle, review_path, review_sha):
    """Called only by an explicit launch after Chief has accepted the contracts."""
    manifest = verify_bundle(bundle)
    assert review_path is not None and review_sha is not None
    assert sha(review_path) == review_sha, "Accepted review differs from Chief's supplied SHA256"
    receipt = Path(manifest["required_contract_receipt"])
    report = read(receipt)
    assert has_binding(read(review_path), receipt, sha(receipt)), (
        "Review must bind this exact completed contract receipt"
    )
    assert report["tests"] == dict(tests=71, errors=0, failures=0, skipped=0)
    assert report["complete_expected_contract_coverage"]
    assert not report["sources_changed_during_checks"]
    assert not report["workspace_sources_changed_during_checks"]
    assert not report["frozen_validation_sources_changed_during_checks"]
    assert report["executed_runtime_source_sha256"] == manifest["runtime_source_sha256"]
    for name, expected in report["executed_validation_source_sha256"].items():
        assert sha(bundle / "workspace" / name) == expected, name
    assert sum(r["finalized_tests"] for r in report["retained_finalized_runs"]) == 6
    assert len(set(report["unique_check_ids"])) == 71
    for name, expected in report["output_sha256"].items():
        assert sha(receipt.parent / name) == expected, name
    return manifest, receipt, report


def launch(args):
    manifest, receipt, _ = admission(args.bundle, args.contract_review, args.contract_review_sha256)
    assert args.completed_pilot is not None, "Full launch requires the completed numerical pilot"
    pilot = read(args.completed_pilot / "result.json")
    assert pilot["status"] == "passed" and pilot["pilot_only"]
    assert pilot["bundle_manifest_sha256"] == sha(args.bundle / "manifest.json")
    assert not pilot["immutable_sources_changed"]
    for name, expected in pilot["output_sha256"].items():
        assert sha(args.completed_pilot / name) == expected, name
    output = args.output.resolve()
    assert output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("joint-water-epoch-refinements-")
    directory = Path(str(output) + "-launch")
    assert not output.exists() and not directory.exists()
    directory.mkdir()
    review_copy = directory / "accepted-contract-review.json"
    shutil.copyfile(args.contract_review, review_copy)
    env = os.environ.copy()
    env.update(
        {
            n: "1"
            for n in (
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        }
    )
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
        JAX_DISABLE_JIT="true",
        JAX_ENABLE_COMPILATION_CACHE="false",
    )
    command = [
        "/usr/bin/taskset",
        "-c",
        "4",
        sys.executable,
        "-B",
        str(args.bundle / "runner.py"),
        "--worker",
        "--bundle",
        str(args.bundle),
        "--output",
        str(output),
        "--contract-review",
        str(review_copy),
        "--contract-review-sha256",
        args.contract_review_sha256,
        "--completed-pilot",
        str(args.completed_pilot.resolve()),
    ]
    started = datetime.now(UTC)
    with (
        (directory / "stdout.log").open("ab", buffering=0) as stdout,
        (directory / "stderr.log").open("ab", buffering=0) as stderr,
    ):
        process = subprocess.Popen(
            command,
            cwd=args.bundle,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
            close_fds=True,
        )
    record = dict(
        status="launched",
        utc=started.isoformat(),
        pid=process.pid,
        command=command,
        output=str(output),
        bundle_manifest_sha256=sha(args.bundle / "manifest.json"),
        accepted_contract_receipt=dict(path=str(receipt), sha256=sha(receipt)),
        accepted_review=dict(path=str(review_copy), sha256=sha(review_copy)),
        retained_contracts=71,
        new_refinements=6,
        retained_pilot_integrations=4,
        pilot_receipt=dict(
            path=str(args.completed_pilot / "result.json"),
            sha256=sha(args.completed_pilot / "result.json"),
        ),
        expected_total_checks=77,
        expected_duration_minutes=[35, 60],
        expected_completion_window_utc=[
            (started + timedelta(minutes=n)).isoformat() for n in (35, 60)
        ],
        detached=True,
        automatic_polling=False,
        automatic_followup=False,
        resources=manifest["resources"],
        completion_artifact=str(output / "result.json"),
        failure_artifact=str(output / "failure.json"),
    )
    write(directory / "launch.json", record)
    print(json.dumps(record))


def worker(args):
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    manifest, receipt, contracts = admission(
        args.bundle, args.contract_review, args.contract_review_sha256
    )
    workspace = args.bundle / "workspace"
    env = os.environ.copy()
    env.update(
        {
            n: "1"
            for n in (
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        }
    )
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="true",
        CUDA_VISIBLE_DEVICES="",
        JAX_ENABLE_COMPILATION_CACHE="false",
        PYTHONPATH=str(workspace / "src") + os.pathsep + str(workspace),
        CELLS_COMPONENT_SOURCE_ROOT=str(workspace),
        CELLS_REFINEMENT_BUNDLE=str(args.bundle),
        CELLS_REFINEMENT_OUTPUT=str(output),
        MALLOC_ARENA_MAX="2",
    )
    for name in ("tmp", "cache"):
        (output / name).mkdir()
    env.update(
        TMPDIR=str(output / "tmp"),
        XDG_CACHE_HOME=str(output / "cache"),
        JAX_COMPILATION_CACHE_DIR=str(output / "cache/jax"),
    )
    commands = []
    helper = workspace / "tests/owned_joint_water_epoch_transient_helpers.py"
    test = workspace / "tests/unit/test_joint_water_epoch_transients.py"
    datasets = ["INIT-water", "SIM-water-changed-controls"] if args.pilot else manifest["datasets"]
    for dataset in datasets:
        prefix = [
            sys.executable,
            "-B",
            str(helper),
            "--bundle",
            str(args.bundle),
            "--output",
            str(output),
            "--dataset",
            dataset,
        ]
        commands.append((dataset + "-reference", [*prefix, "--role", "reference"]))
        for factor in (1,) if args.pilot else (1, 2):
            commands.append(
                (
                    dataset + "-production-" + str(factor),
                    [*prefix, "--role", "production", "--factor", str(factor)],
                )
            )
        if args.pilot:
            commands.append((dataset + "-pilot-accuracy", [*prefix, "--role", "pilot-accuracy"]))
            continue
        commands.append(
            (
                dataset + "-comparison",
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-x",
                    "-p",
                    "no:cacheprovider",
                    "--basetemp=" + str(output / "tmp" / dataset),
                    "--junitxml=" + str(output / (dataset + "-tests.xml")),
                    str(test),
                    "-k",
                    dataset,
                ],
            )
        )
    retained_pilot = None
    if args.completed_pilot is not None:
        assert not args.pilot
        pilot = read(args.completed_pilot / "result.json")
        assert pilot["status"] == "passed" and pilot["pilot_only"]
        assert pilot["bundle_manifest_sha256"] == sha(args.bundle / "manifest.json")
        for name, expected in pilot["output_sha256"].items():
            assert sha(args.completed_pilot / name) == expected, name
        shutil.copytree(args.completed_pilot / "evidence", output / "evidence")
        reused = {
            d + suffix
            for d in ("INIT-water", "SIM-water-changed-controls")
            for suffix in ("-reference", "-production-1")
        }
        commands = [row for row in commands if row[0] not in reused]
        retained_pilot = dict(
            path=str(args.completed_pilot / "result.json"),
            sha256=sha(args.completed_pilot / "result.json"),
            completed_integrations=sorted(reused),
            rerun=False,
        )
        write(output / "retained-pilot.json", retained_pilot)
    retained = []
    for path in sorted(receipt.parent.glob("*-tests.xml")):
        target = output / ("retained-contract-" + path.name)
        shutil.copyfile(path, target)
        retained.append(dict(path=str(target), sha256=sha(target)))
    write(
        output / "retained-contracts.json",
        dict(
            receipt=dict(path=str(receipt), sha256=sha(receipt)),
            review=dict(path=str(args.contract_review), sha256=sha(args.contract_review)),
            tests=contracts["tests"],
            junit=retained,
            rerun=False,
            evidence_location=str(receipt.parent / "evidence"),
        ),
    )
    write(
        output / "inputs.json",
        dict(
            started_utc=datetime.now(UTC).isoformat(),
            bundle=str(args.bundle),
            bundle_manifest_sha256=sha(args.bundle / "manifest.json"),
            affinity=sorted(os.sched_getaffinity(0)),
            environment=env_imports(env),
            commands=[dict(name=n, argv=a) for n, a in commands],
            executing_import_paths=dict(
                cells=str(workspace / "src/cells"),
                tests=str(workspace / "tests"),
                validation=str(workspace / "validation"),
            ),
            retained_contract_receipt=str(receipt),
            retained_contract_receipt_sha256=sha(receipt),
            accepted_review_sha256=sha(args.contract_review),
            pilot_only=args.pilot,
            retained_pilot=retained_pilot,
            automatic_followup=False,
        ),
    )
    assert sorted(os.sched_getaffinity(0)) == [4]
    sys.path[:0] = [str(workspace / "src"), str(workspace)]
    from validation.assembly.component_process import run_bounded

    checks = []
    error = None
    try:
        for name, argv in commands:
            write(
                output / "job-status.json",
                dict(status="running", stage=name, utc=datetime.now(UTC).isoformat()),
            )
            directory = output / (name + "-guard")
            directory.mkdir()
            run_bounded(
                argv,
                directory=directory,
                cwd=workspace,
                env=env,
                timeout=480,
                max_rss_bytes=2**30,
                min_available_bytes=8 * 2**30,
            )
            checks.append(
                dict(name=name, status="completed", resource_receipt=str(directory / "result.json"))
            )
    except Exception as exception:
        error = dict(
            type=type(exception).__name__, message=str(exception), traceback=traceback.format_exc()
        )
    changed = [
        name
        for name, expected in manifest["file_sha256"].items()
        if sha(args.bundle / name) != expected
    ]
    counts = dict(tests=0, errors=0, failures=0, skipped=0)
    ids = []
    for path in output.glob("*-tests.xml"):
        tree = ET.parse(path).getroot()
        for suite in tree.iter("testsuite"):
            for key in counts:
                counts[key] += int(suite.get(key, "0"))
        ids.extend(c.attrib["classname"] + "::" + c.attrib["name"] for c in tree.iter("testcase"))
    expected_checks = 71 if args.pilot else 77
    passed = (
        error is None
        and len(checks) == len(commands)
        and not changed
        and counts == dict(tests=expected_checks, errors=0, failures=0, skipped=0)
        and len(ids) == len(set(ids)) == expected_checks
    )
    result = dict(
        status="passed" if passed else "failed",
        tests=counts,
        unique_check_ids=ids,
        checks=checks,
        error=error,
        immutable_sources_changed=changed,
        retained_contracts=71,
        new_refinements=0 if args.pilot else 6,
        pilot_only=args.pilot,
        pilot_accuracy_cases=2 if args.pilot and passed else 0,
        retained_pilot=retained_pilot,
        bundle_manifest_sha256=sha(args.bundle / "manifest.json"),
        accepted_review=dict(path=str(args.contract_review), sha256=sha(args.contract_review)),
        actual_import_paths=dict(
            cells=str(workspace / "src/cells"),
            tests=str(workspace / "tests"),
            validation=str(workspace / "validation"),
        ),
        runtime_source_sha256=manifest["runtime_source_sha256"],
        all_executed_source_sha256=manifest["file_sha256"],
        endpoint_only_claim=False,
        convergence_order_claim=False,
        compiled_or_gpu_qualified=False,
        automatic_followup=False,
    )
    write(
        output / "job-status.json", dict(status=result["status"], utc=datetime.now(UTC).isoformat())
    )
    result["output_sha256"] = {
        str(p.relative_to(output)): sha(p) for p in output.rglob("*") if p.is_file()
    }
    write(output / "result.json", result)
    if not passed:
        write(output / "failure.json", result)
    print(json.dumps(dict(output=str(output), status=result["status"], tests=counts)))
    return 0 if passed else 1


def env_imports(env):
    keys = (
        "PYTHONPATH",
        "CELLS_COMPONENT_SOURCE_ROOT",
        "CELLS_REFINEMENT_BUNDLE",
        "CELLS_REFINEMENT_OUTPUT",
        "OPENBLAS_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "JAX_DISABLE_JIT",
        "CUDA_VISIBLE_DEVICES",
        "JAX_ENABLE_COMPILATION_CACHE",
    )
    return {k: env[k] for k in keys}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--launch", action="store_true")
    mode.add_argument("--worker", action="store_true")
    mode.add_argument("--pilot", action="store_true")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--contract-review", type=Path)
    parser.add_argument("--contract-review-sha256")
    parser.add_argument("--completed-pilot", type=Path)
    args = parser.parse_args()
    args.bundle = args.bundle.resolve()
    if args.check:
        manifest = verify_bundle(args.bundle)
        print(
            json.dumps(
                dict(
                    status="prepared_not_launched",
                    datasets=manifest["datasets"],
                    frozen_files=len(manifest["file_sha256"]),
                    contracts_inspected=False,
                )
            )
        )
        return 0
    if args.output is None or args.contract_review is None or args.contract_review_sha256 is None:
        parser.error(
            "Launch needs an output and the Chief-accepted contract review with its supplied SHA256"
        )
    if args.launch:
        launch(args)
        return 0
    try:
        return worker(args)
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        write(
            args.output / "failure.json",
            dict(
                status="failed",
                type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
            ),
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
