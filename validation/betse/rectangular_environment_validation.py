"""Bounded small-grid numerical checks, using existing snapshot/resource tools.

This runs declared synthetic algebra fixtures, not native BETSE, a retained
625-point solve or a biological simulation. Default invocation only prepares.
"""

import argparse
import hashlib
import importlib.abc
import json
import os
import resource
import sys
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_mesh_lifecycle_preparation_guard as guard
from validation.betse import betse_normal_channel_join_runtime as runtime

ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/rectangular_environment_validation.py"
TEST = "tests/unit/test_rectangular_environment.py"
FILES = (
    OWN,
    TEST,
    "src/cells/processes/rectangular_environment.py",
    "src/cells/processes/betse_native_grid_metric_audit.py",
    "src/cells/__init__.py",
    "src/cells/processes/__init__.py",
    "validation/source_snapshot.py",
    "validation/betse/betse_mesh_lifecycle_preparation_guard.py",
    "validation/betse/betse_normal_channel_join_runtime.py",
)
LIMITS = dict(timeout=480, max_rss_bytes=2**30, min_available_bytes=8 * 2**30)


def write(path, data):
    snapshot.write_json(path, data)


def verify_runtime(frozen, source, producers, expected_cpu):
    """Bind every executed project producer to this image, including the test."""
    if producers["measured_cpu_affinity"] != expected_cpu:
        raise ValueError("Child CPU affinity differs from the recorded execution plan")
    executable = producers["executable"]
    if (
        Path(executable["path"]) != Path(sys.executable).resolve()
        or snapshot.digest(Path(executable["path"])) != executable["sha256"]
    ):
        raise ValueError("Changed worker executable")
    loaded, selected = {}, set()
    for name, row in producers["loaded_files"].items():
        path = Path(row["path"])
        if not path.is_file() or snapshot.digest(path) != row.get("sha256"):
            raise ValueError("Changed or unavailable runtime file: " + name)
        if path.is_relative_to(frozen):
            rel = str(path.relative_to(frozen))
            if rel not in source["files"] or row["sha256"] != source["files"][rel]["sha256"]:
                raise ValueError("Unbound loaded source: " + name)
            loaded[name], selected = row, selected | {rel}
        elif (
            path.is_relative_to(ROOT)
            or name.split(".")[0] in ("cells", "validation", "test_rectangular_environment")
            or name == "__main__"
        ):
            raise ValueError("Worker imported a project producer outside the frozen image: " + name)
    if set(FILES) - selected:
        raise ValueError(
            "Required frozen producers were not loaded: " + repr(sorted(set(FILES) - selected))
        )
    return loaded


def child(output):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    import pytest

    attempts = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] == "betse":
                attempts.append(fullname)
                raise AssertionError("Original BETSE execution is outside these small checks")

    class Reports:
        def pytest_runtest_logreport(self, report):
            if report.when == "call" or report.failed:
                key = hashlib.sha256((report.nodeid + report.when).encode()).hexdigest()
                write(
                    output / "case-reports" / (key + ".json"),
                    dict(
                        nodeid=report.nodeid,
                        when=report.when,
                        outcome=report.outcome,
                        traceback=str(report.longrepr) if report.failed else None,
                    ),
                )

    previous = sys.getprofile()

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and "/betse/science/" in frame.f_code.co_filename:
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Original BETSE source is outside these small checks")

    block = Block()
    sys.meta_path.insert(0, block)
    sys.setprofile(profile)
    code = None
    try:
        code = pytest.main(
            [
                "-q",
                "--noconftest",
                "-c",
                "/dev/null",
                "-p",
                "no:cacheprovider",
                TEST,
                "--junitxml=" + str(output / "junit.xml"),
                "--basetemp=" + str(output / "tmp"),
            ],
            plugins=[Reports()],
        )
    finally:
        sys.setprofile(previous)
        sys.meta_path.remove(block)
        write(
            output / "native-entry-guard.json",
            dict(
                attempted=attempts,
                pytest_completed=code is not None,
                native_execution=False,
                biological_cases=0,
            ),
        )
        write(output / "runtime-producers.json", runtime.inventory())
    write(output / "pytest-exit.json", dict(returncode=int(code)))
    return int(code) if not attempts else 1


def prepare(output, run):
    output = output.absolute()
    base = Path("/mnt/workspaces/Cells")
    if not output.is_relative_to(base) or output == base or output.resolve() != output:
        raise ValueError("Require a new regular output directory below /mnt/workspaces/Cells")
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "source"
    source = snapshot.freeze(ROOT, frozen, {name: name for name in FILES})
    manifest_sha = snapshot.digest(frozen / "SNAPSHOT.json")
    expected_cpu = sorted(os.sched_getaffinity(0))
    if len(expected_cpu) != 1:
        raise ValueError("Require an explicitly selected single CPU for these bounded checks")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.rectangular_environment_validation",
        "--output",
        str(output),
        "--child",
    ]
    write(
        output / "inputs.json",
        dict(
            limits=LIMITS,
            cpu=expected_cpu,
            threads=1,
            source_manifest_sha256=manifest_sha,
            command=command,
            source_sha256={name: item["sha256"] for name, item in source["files"].items()},
            scope=(
                "Small declared rectangular-grid algebra fixtures; "
                "no native, retained grid or biological execution"
            ),
        ),
    )
    if not run:
        return 0
    (output / "process").mkdir()
    (output / "case-reports").mkdir()
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join((str(frozen / "src"), str(frozen))),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="1",
        CELLS_RECTANGULAR_EVIDENCE=str(output / "evidence"),
        TMPDIR=str(output / "tmp"),
    )
    (output / "tmp").mkdir()
    try:
        process = guard.run_bounded(
            command,
            directory=output / "process",
            cwd=frozen,
            env=env,
            process_tree_memory_metric="rss",
            **LIMITS,
        )
        snapshot.verify(frozen, manifest_sha256=manifest_sha)
        producers = json.loads((output / "runtime-producers.json").read_text())
        loaded = verify_runtime(frozen, source, producers, expected_cpu)
        entry = json.loads((output / "native-entry-guard.json").read_text())
        exit_record = json.loads((output / "pytest-exit.json").read_text())
        if entry["attempted"] or not entry["pytest_completed"] or exit_record["returncode"]:
            raise ValueError("Incomplete or failed bounded numerical checks")
        # Immutable executed source controls acceptance; concurrent unrelated Git
        # bookkeeping is reported separately, never reclassified as worker failure.
        changed = [
            name
            for name, row in source["files"].items()
            if not (ROOT / name).is_file() or snapshot.digest(ROOT / name) != row["sha256"]
        ]
        write(
            output / "result.json",
            dict(
                status="completed_small_grid_checks",
                process=process,
                snapshot_manifest_sha256=manifest_sha,
                loaded_source=loaded,
                live_source_drift=changed,
                native_execution=False,
                biological_cases=0,
                physical_tissue_admission=False,
            ),
        )
        return 0
    except BaseException as error:
        write(
            output / "failure.json",
            dict(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                snapshot_manifest_sha256=manifest_sha,
                native_or_physical_acceptance=False,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    return child(args.output) if args.child else prepare(args.output, args.run)


if __name__ == "__main__":
    raise SystemExit(main())
