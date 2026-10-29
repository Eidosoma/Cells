"""Freeze and run guarded full-history barrier comparisons, with no auto-launch.

Preparation and one explicitly selected attached pilot are separate commands.
The six-case suite is intended for a detached invocation by the coordinator.
Every case uses the existing component_process live RSS and host-reserve guard.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

CPU = 5
PYTHON = Path("/mnt/workspaces/Cells/venv-cpu/bin/python")
TEST = "tests/unit/test_environment_barrier_composition_transients.py"
HELPER = "tests.owned_barrier_composition_transient_helpers"
PILOT = "water-asymmetric_modulators"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    with Path(path).open() as stream:
        return json.load(stream)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def environment(source, bundle, output):
    return dict(
        os.environ,
        PYTHONPATH=f"{source / 'src'}:{source}",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="true",
        CUDA_VISIBLE_DEVICES="",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        MALLOC_ARENA_MAX="2",
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        TMPDIR=str(output / "tmp"),
        CELLS_BARRIER_TRANSIENT_BUNDLE=str(bundle),
        CELLS_BARRIER_TRANSIENT_OUTPUT=str(output),
    )


def available():
    fields = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    return int(fields["MemAvailable"].split()[0]) * 1024


def guard_command(command, *, source, bundle, output, name, timeout):
    sys.path[:0] = [str(source / "src"), str(source)]
    from validation.assembly.component_process import run_bounded

    (output / "tmp").mkdir(parents=True, exist_ok=True)
    directory = output / name
    env = environment(source, bundle, output)
    write(
        directory / "inputs.json",
        dict(
            command=command,
            cpu_affinity=sorted(os.sched_getaffinity(0)),
            environment={
                k: v
                for k, v in env.items()
                if k.startswith(("CELLS_", "JAX_", "XLA_"))
                or k
                in ("PYTHONPATH", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "CUDA_VISIBLE_DEVICES")
            },
        ),
    )
    return run_bounded(
        command,
        directory=directory,
        cwd=source,
        env=env,
        timeout=timeout,
        max_rss_bytes=1 << 30,
        min_available_bytes=8 << 30,
    )


def verify_bundle(bundle):
    manifest = read(bundle / "source-manifest.json")
    mismatches = [k for k, v in manifest.items() if sha(bundle / "source" / k) != v]
    if mismatches:
        raise ValueError(("Frozen scientific source changed", mismatches))
    for values in read(bundle / "input-manifest.json").values():
        for value in values.values():
            if sha(bundle / value["path"]) != value["sha256"]:
                raise ValueError(("Frozen physical input changed", value["path"]))
    return dict(
        source_manifest_sha256=sha(bundle / "source-manifest.json"),
        input_manifest_sha256=sha(bundle / "input-manifest.json"),
    )


def prepare(bundle, repo):
    bundle.mkdir(parents=True, exist_ok=False)
    source = bundle / "source"
    hashes = {}
    paths = [repo / "pyproject.toml"]
    for folder in ("src", "validation", "tests", "configs", "examples"):
        paths += [
            p
            for p in (repo / folder).rglob("*")
            if p.is_file() and p.suffix in (".py", ".json", ".toml", ".txt")
        ]
    for path in sorted(paths):
        if available() < 8 << 30:
            raise RuntimeError("Preparation host reserve below 8 GiB")
        rel = path.relative_to(repo)
        target = source / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        before = sha(path)
        shutil.copy2(path, target)
        assert sha(target) == before == sha(path), rel
        hashes[str(rel)] = before
    assert all(sha(repo / k) == v for k, v in hashes.items()), "Live sources changed during capture"
    write(bundle / "source-manifest.json", hashes)
    command = [str(PYTHON), "-B", "-m", HELPER, "--prepare", "--bundle", str(bundle)]
    result = guard_command(
        command, source=source, bundle=bundle, output=bundle, name="prepare-inputs", timeout=180
    )
    assert result["returncode"] == 0
    command = [
        str(PYTHON),
        "-B",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "--basetemp=" + str(bundle / "contract-tmp"),
        "--junitxml=" + str(bundle / "contracts.xml"),
        TEST,
        "-k",
        "full_physical_inputs",
        "--maxfail=1",
    ]
    result = guard_command(
        command, source=source, bundle=bundle, output=bundle, name="contracts", timeout=180
    )
    assert result["returncode"] == 0
    cases = list(ET.parse(bundle / "contracts.xml").iter("testcase"))
    assert len(cases) == 6 and all(not list(c) for c in cases)
    ids = verify_bundle(bundle)
    write(
        bundle / "preparation.json",
        dict(
            status="prepared_not_launched",
            utc=datetime.now(UTC).isoformat(),
            **ids,
            source_files=len(hashes),
            datasets=list(read(bundle / "input-manifest.json")),
            full_horizon_s=50e-6,
            production_dt_s=[0.625e-6, 0.3125e-6],
            reference_refinements=[1, 2],
            contract_checks=6,
            scientific_transient_checks=0,
            independent_biological_cases=0,
            resources=dict(cpu=CPU, max_rss_bytes=1 << 30, min_available_host_bytes=8 << 30),
            future_suite_requires_coordinator_invocation=True,
            launch_command=(
                f"taskset -c {CPU} {PYTHON} -B "
                f"{source}/validation/transport/"
                "environment_barrier_composition_transient_runner.py "
                f"run --bundle {bundle} --output OUTPUT_DIRECTORY --retain PILOT_DIRECTORY"
            ),
        ),
    )


def run_cases(bundle, output, *, pilot, retain):
    output.mkdir(parents=True, exist_ok=False)
    source = bundle / "source"
    ids = verify_bundle(bundle)
    cases = [PILOT] if pilot else list(read(bundle / "input-manifest.json"))
    expected = set(cases)
    results = []
    began = time.monotonic()
    if retain:
        old = read(retain / "result.json")
        assert old["status"] == "passed" and old["pilot"] and not pilot
        assert all(old[k] == v for k, v in ids.items())
        for key, value in old["artifact_sha256"].items():
            assert sha(retain / key) == value
        assert old["completed_datasets"] == [PILOT]
        cases.remove(PILOT)
        results.append(
            dict(
                dataset=PILOT,
                retained_receipt=str(retain / "result.json"),
                sha256=sha(retain / "result.json"),
            )
        )
    write(
        output / "inputs.json",
        dict(
            **ids,
            bundle=str(bundle),
            pilot=pilot,
            datasets=cases,
            retained=str(retain) if retain else None,
            cpu_affinity=sorted(os.sched_getaffinity(0)),
            automatic_retry=False,
        ),
    )
    try:
        for dataset in cases:
            write(
                output / "status.json", dict(status="running", dataset=dataset, completed=results)
            )
            command = [
                str(PYTHON),
                "-B",
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp=" + str(output / (dataset + "-tmp")),
                "--junitxml=" + str(output / (dataset + ".xml")),
                TEST + "::test_complete_evolved_barrier_history_and_refinement[" + dataset + "]",
                "--maxfail=1",
            ]
            value = guard_command(
                command,
                source=source,
                bundle=bundle,
                output=output,
                name=dataset,
                timeout=480 if pilot else 1800,
            )
            assert value["returncode"] == 0, (dataset, value)
            tests = list(ET.parse(output / (dataset + ".xml")).iter("testcase"))
            assert len(tests) == 1 and not list(tests[0]), dataset
            record = read(output / "evidence" / dataset / "comparison.json")
            assert record["status"] == "passed"
            results.append(
                dict(
                    dataset=dataset,
                    guard_result=str(output / dataset / "result.json"),
                    comparison=str(output / "evidence" / dataset / "comparison.json"),
                )
            )
        assert {r["dataset"] for r in results} == expected
        assert verify_bundle(bundle) == ids
        write(output / "status.json", dict(status="passed", completed=results))
        artifacts = {
            str(p.relative_to(output)): sha(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
            and not any(v.endswith("-tmp") or v == "tmp" for v in p.relative_to(output).parts)
        }
        result = dict(
            status="passed",
            pilot=pilot,
            **ids,
            completed_datasets=[r["dataset"] for r in results],
            unique_full_transient_checks=len(results),
            independent_biological_cases=0,
            elapsed_seconds=time.monotonic() - began,
            results=results,
            artifact_sha256=artifacts,
            original_full_horizon_s=50e-6,
            scientific_tolerances_relaxed=False,
            automatic_followup=False,
        )
        write(output / "result.json", result)
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in ("artifact_sha256", "results")},
                indent=2,
            )
        )
    except Exception as error:
        write(output / "status.json", dict(status="failed", completed=results, error=str(error)))
        write(
            output / "failure.json",
            dict(
                status="failed",
                error=str(error),
                traceback=traceback.format_exc(),
                completed=results,
                **ids,
                elapsed_seconds=time.monotonic() - began,
                automatic_retry=False,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "pilot", "run"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--retain", type=Path)
    args = parser.parse_args()
    assert os.sched_getaffinity(0) == {CPU}, "Use the assigned CPU5 lane"
    assert available() >= 8 << 30, "Require 8 GiB available host memory"
    if args.mode == "prepare":
        prepare(args.bundle, args.repo)
    else:
        if args.output is None:
            parser.error("Execution needs a new durable output directory")
        run_cases(args.bundle, args.output, pilot=args.mode == "pilot", retain=args.retain)


if __name__ == "__main__":
    main()
