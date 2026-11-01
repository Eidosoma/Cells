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
SAVED_TEST = "tests/unit/test_rectangular_environment_saved.py"
REFERENCE_TEST = "tests/unit/test_rectangular_environment_reference.py"
STENCIL_TEST = "tests/unit/test_rectangular_environment_stencil.py"
SAVED_EXTRA = (
    "validation/betse/rectangular_environment_saved.py",
    "validation/betse/rectangular_environment_reference.py",
    "validation/betse/native_single_cell_poisson_spectrum.py",
    "validation/betse/native_single_cell_poisson_algebra.py",
    "validation/betse/native_single_cell_prefix_compare.py",
    "validation/betse/native_single_cell_prefix_payload.py",
    "validation/betse/native_single_cell_prefix_qualification.py",
    "validation/betse/betse_native_membrane_initialization_archive.py",
)


def suite_files(suite):
    if suite == "small":
        return FILES, TEST
    if suite == "saved":
        return (*[name for name in FILES if name != TEST], *SAVED_EXTRA, SAVED_TEST), SAVED_TEST
    if suite == "stencil":
        return (
            *FILES,  # The existing small-test module supplies only save/spec helpers.
            "tests/__init__.py",
            "src/cells/processes/rectangular_environment_stencil.py",
            STENCIL_TEST,
        ), STENCIL_TEST
    if suite == "reference":
        return (
            OWN,
            "validation/betse/rectangular_environment_reference.py",
            REFERENCE_TEST,
            "validation/source_snapshot.py",
            "validation/betse/betse_mesh_lifecycle_preparation_guard.py",
            "validation/betse/betse_normal_channel_join_runtime.py",
        ), REFERENCE_TEST
    raise ValueError("Unknown declared validation suite")


def write(path, data):
    snapshot.write_json(path, data)


def bound_json(path):
    """Hash and decode the same bounded bytes, then reject concurrent replacement."""
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file():
        raise ValueError("Require a regular metadata input")
    with path.open("rb") as stream:
        data = stream.read(16 * 2**20 + 1)
    if len(data) > 16 * 2**20:
        raise ValueError("Oversized metadata input")
    pin = dict(path=str(path), sha256=hashlib.sha256(data).hexdigest())
    value = json.loads(data)
    if path.is_symlink() or snapshot.digest(path) != pin["sha256"]:
        raise ValueError("Metadata input changed while decoding")
    return pin, value


def retained_output(output, baseline, baseline_sha256, numpy_pins=()):
    """Protect all retained input/runtime directories before any output write."""
    from validation.betse import native_single_cell_prefix_qualification as prior

    output = prior.output_path(output)
    pin, record = bound_json(baseline)
    if pin["sha256"] != baseline_sha256:
        raise ValueError("Changed retained baseline")
    protected = [pin, *record["inputs"], *numpy_pins]
    prior.verify_pins(protected)
    for item in protected:
        path = Path(item["path"]).absolute()
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise ValueError("Linked retained input or runtime")
        folder = path.parent
        if output.is_relative_to(folder) or folder.is_relative_to(output):
            raise ValueError("Output overlaps retained evidence or runtime")
    return output


def analysis_preflight(output, analysis_inputs):
    pin, raw = bound_json(analysis_inputs)
    if (
        set(raw) != {"baseline", "numpy_pins", "scope"}
        or raw["scope"] != "retained_physical_rectangle_diagnostic"
    ):
        raise ValueError("Require explicit bounded retained-grid inputs")
    retained_output(output, raw["baseline"]["path"], raw["baseline"]["sha256"], raw["numpy_pins"])
    if Path(pin["path"]).is_relative_to(output) or output.is_relative_to(Path(pin["path"])):
        raise ValueError("Output overlaps its input declaration")
    return pin, raw


def verify_runtime(frozen, source, producers, expected_cpu, required_files=FILES):
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
            or name.split(".")[0] in ("cells", "validation")
            or name.startswith("test_rectangular_environment")
            or name == "__main__"
        ):
            raise ValueError("Worker imported a project producer outside the frozen image: " + name)
    if set(required_files) - selected:
        raise ValueError(
            "Required frozen producers were not loaded: "
            + repr(sorted(set(required_files) - selected))
        )
    return loaded


def child(output, suite="small", analysis_inputs=None, analysis_sha256=None):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    if analysis_inputs is None:
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
    operations = {}
    watched = {
        ("cells.processes.rectangular_environment", "bind"),
        ("cells.processes.rectangular_environment", "solve"),
        ("numpy.linalg._linalg", "inv"),
        ("validation.betse.rectangular_environment_reference", "diagnose"),
        ("cells.processes.rectangular_environment_stencil", "gradient"),
        ("cells.processes.rectangular_environment_stencil", "divergence"),
    }
    original_profile = profile

    def counting_profile(frame, event, arg):
        original_profile(frame, event, arg)
        if event == "call":
            site = (frame.f_globals.get("__name__"), frame.f_code.co_name)
            if site in watched:
                label = ".".join(site)
                operations[label] = operations.get(label, 0) + 1

    sys.setprofile(counting_profile)
    try:
        if analysis_inputs is not None:
            from validation.betse import rectangular_environment_saved as adapter

            input_pin, data = bound_json(analysis_inputs)
            if input_pin["sha256"] != analysis_sha256:
                raise ValueError("Changed declared numerical inputs before execution")
            adapter.run(
                data["baseline"]["path"],
                data["baseline"]["sha256"],
                output / "calculation",
                numpy_pins=data["numpy_pins"],
            )
            code = 0
            if snapshot.digest(analysis_inputs) != analysis_sha256:
                raise ValueError("Changed declared numerical inputs during execution")
        else:
            code = pytest.main(
                [
                    "-q",
                    "--noconftest",
                    "-c",
                    "/dev/null",
                    "-p",
                    "no:cacheprovider",
                    suite_files(suite)[1],
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
                pytest_completed=code is not None and analysis_inputs is None,
                calculation_completed=code == 0 and analysis_inputs is not None,
                native_execution=False,
                biological_cases=0,
                actual_entries=operations,
                numerical_work_is_not_case_credit=True,
            ),
        )
        write(output / "runtime-producers.json", runtime.inventory())
    write(
        output / ("execution-exit.json" if analysis_inputs is not None else "pytest-exit.json"),
        dict(returncode=int(code)),
    )
    return int(code) if not attempts else 1


def prepare(output, run, *, suite="small", analysis_inputs=None):
    output = output.absolute()
    base = Path("/mnt/workspaces/Cells")
    if not output.is_relative_to(base) or output == base or output.resolve() != output:
        raise ValueError("Require a new regular output directory below /mnt/workspaces/Cells")
    if analysis_inputs is not None and suite != "saved":
        raise ValueError("Retained-grid evaluation uses the explicit saved-grid suite")
    numerical_inputs, numerical_copy, raw = None, None, None
    if analysis_inputs is not None:
        numerical_inputs, raw = analysis_preflight(output, analysis_inputs)
    files, selected_test = suite_files(suite)
    expected_cpu = sorted(os.sched_getaffinity(0))
    if len(expected_cpu) != 1:
        raise ValueError("Require an explicitly selected single CPU for these bounded checks")
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "source"
    source = snapshot.freeze(ROOT, frozen, {name: name for name in files})
    manifest_sha = snapshot.digest(frozen / "SNAPSHOT.json")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.rectangular_environment_validation",
        "--output",
        str(output),
        "--child",
        "--suite",
        suite,
    ]
    if analysis_inputs is not None:
        from validation.betse import native_single_cell_prefix_qualification as prior

        prior.verify_pins([numerical_inputs, raw["baseline"], *raw["numpy_pins"]])
        write(output / "analysis-inputs.json", raw)
        numerical_copy = prior.pin(output / "analysis-inputs.json")
        command.extend(
            [
                "--analysis-inputs",
                numerical_copy["path"],
                "--analysis-sha256",
                numerical_copy["sha256"],
            ]
        )
    write(
        output / "inputs.json",
        dict(
            limits=LIMITS,
            cpu=expected_cpu,
            threads=1,
            source_manifest_sha256=manifest_sha,
            suite=suite,
            analysis_inputs=numerical_inputs,
            analysis_inputs_copy=numerical_copy,
            command=command,
            source_sha256={name: item["sha256"] for name, item in source["files"].items()},
            scope=(
                "Retained physical-grid numerical diagnostic; no native or biological execution"
                if analysis_inputs is not None
                else "Small software/algebra fixtures; no native or retained-grid execution"
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
        required = tuple(name for name in files if analysis_inputs is None or name != selected_test)
        loaded = verify_runtime(frozen, source, producers, expected_cpu, required)
        entry = json.loads((output / "native-entry-guard.json").read_text())
        exit_name = "execution-exit.json" if analysis_inputs is not None else "pytest-exit.json"
        completion_key = (
            "calculation_completed" if analysis_inputs is not None else "pytest_completed"
        )
        exit_record = json.loads((output / exit_name).read_text())
        if entry["attempted"] or not entry[completion_key] or exit_record["returncode"]:
            raise ValueError("Incomplete or failed bounded numerical checks")
        if numerical_copy is not None:
            prior.verify_pins([numerical_inputs, numerical_copy])
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
                status="completed_retained_grid_diagnostic"
                if analysis_inputs is not None
                else "completed_small_grid_checks",
                mode="retained_grid_numerical_diagnostic" if analysis_inputs is not None else suite,
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
    parser.add_argument(
        "--suite", choices=("small", "saved", "reference", "stencil"), default="small"
    )
    parser.add_argument("--analysis-inputs", type=Path)
    parser.add_argument("--analysis-sha256", help=argparse.SUPPRESS)
    args = parser.parse_args()
    return (
        child(args.output, args.suite, args.analysis_inputs, args.analysis_sha256)
        if args.child
        else prepare(args.output, args.run, suite=args.suite, analysis_inputs=args.analysis_inputs)
    )


if __name__ == "__main__":
    raise SystemExit(main())
