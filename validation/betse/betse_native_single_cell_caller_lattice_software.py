"""Focused synthetic caller controls, reusing the source snapshot/resource runner."""

import argparse
import json
import os
import resource
import runpy
import sys
from pathlib import Path

from validation.betse import betse_native_single_cell_dec_parent_software as runner

ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/betse_native_single_cell_caller_lattice_software.py"
TEST = "tests/unit/test_betse_native_single_cell_caller_lattice.py"


def child(output):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    import pytest

    from cells.processes import betse_native_single_cell_caller_lattice as caller

    original_methods = [
        caller.source.CellsKernel.__init__,
        caller.source.CellsKernel._make_cell_lattice,
        caller.source.ParameterStores.initialize_source_stores,
        caller._Parameters.__init__,
        caller.core.initial.image_stage.lattice.generate,
        caller.core.initial.image_stage.lattice.validate_state,
        caller.core.initial.image_stage.prepare,
        caller.core.prepare,
        caller.core.initial.prepare,
    ]
    codes = {m.__code__: m.__module__ + "." + m.__qualname__ for m in original_methods}
    attempted = []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code in codes:
            attempted.append(codes[frame.f_code])
            raise AssertionError("Original source execution forbidden in caller software control")

    def forbidden(*a, **k):
        attempted.append("real_numpy_RNG_or_pinv")
        raise AssertionError("Real RNG/operator entry forbidden")

    caller.np.random.RandomState = forbidden
    caller.np.linalg.pinv = forbidden
    arguments = [
        "-q",
        "--noconftest",
        "-c",
        "/dev/null",
        "-p",
        "no:cacheprovider",
        str(ROOT / TEST),
        "--junitxml=" + str(output / "tests.xml"),
        "--basetemp=" + str(output / "tmp"),
    ]
    sys.setprofile(profile)
    try:
        code = pytest.main(arguments)
    finally:
        sys.setprofile(None)
        runner.write(
            output / "native-entry-guard.json",
            dict(attempted=attempted, blocked_methods=list(codes.values()), numerical_credit=False),
        )
    runner.write(output / "pytest-exit.json", dict(returncode=int(code), argv=arguments))
    producers = {}
    for name, module in list(sys.modules.items()):
        file = getattr(module, "__file__", None)
        if file and (
            name == "cells"
            or name.startswith(("cells.", "validation.", "PIL."))
            or name == "PIL"
            or name == Path(TEST).stem
        ):
            path = Path(file).resolve()
            producers[name] = dict(path=str(path), sha256=runner.source_snapshot.digest(path))
            if (
                name == "cells"
                or name.startswith(("cells.", "validation."))
                or name == Path(TEST).stem
            ) and not path.is_relative_to(ROOT):
                raise RuntimeError("Runtime source escaped immutable snapshot: " + name)
    runner.write(output / "runtime-producers.json", producers)
    caller._verify_sources()
    if attempted:
        raise RuntimeError("A synthetic control attempted actual source work")
    return int(code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.absolute()
    if not output.is_relative_to(runner.BASE) or os.sched_getaffinity(0) != {6}:
        parser.error("Require CPU6 and a fresh /mnt/workspaces/Cells output")
    if args._child:
        return child(output)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    output.mkdir(parents=True, exist_ok=False)
    (output / "process").mkdir()
    closure = runpy.run_path(str(ROOT / runner.CLOSURE_TOOL))["closure"]
    files = closure(ROOT, [OWN, TEST])
    files[runner.CLOSURE_TOOL] = runner.source_snapshot.digest(ROOT / runner.CLOSURE_TOOL)
    frozen = output / "tested-source"
    snapshot = runner.source_snapshot.freeze(ROOT, frozen, {name: name for name in files})
    runner.write(
        output / "inputs.json",
        dict(
            git_revision=snapshot["git_revision"],
            snapshot_manifest_sha256=runner.source_snapshot.digest(frozen / "SNAPSHOT.json"),
            source_sha256={name: row["sha256"] for name, row in snapshot["files"].items()},
            selected_tests=[TEST],
            synthetic_only=True,
            actual_source_replay_released=False,
        ),
    )
    environment = dict(os.environ)
    paths = [str(frozen), str(frozen / "src")]
    paths += [
        p
        for p in environment.get("PYTHONPATH", "").split(os.pathsep)
        if p and not Path(p).resolve().is_relative_to(ROOT)
    ]
    environment.update(
        PYTHONPATH=os.pathsep.join(paths),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        CELLS_CALLER_LATTICE_EVIDENCE=str(output / "evidence"),
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
    )
    result = runner.guard.run_bounded(
        [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_native_single_cell_caller_lattice_software",
            "--output",
            str(output),
            "--_child",
        ],
        directory=output / "process",
        cwd=frozen,
        env=environment,
        timeout=480,
        max_rss_bytes=2**30,
        min_available_bytes=8 * 2**30,
        process_tree_memory_metric="rss",
    )
    runner.source_snapshot.assert_checkout_unchanged(frozen)
    attempted = json.loads((output / "native-entry-guard.json").read_text())["attempted"]
    if attempted:
        raise RuntimeError("Actual source entry was attempted")
    result.update(
        synthetic_only=True,
        actual_source_replay_released=False,
        native_entry_attempts=attempted,
        all11_owners_remain_invalid=True,
        full_make_voronoi_or_cell_index_admitted=False,
        git_revision=snapshot["git_revision"],
        snapshot_manifest_sha256=runner.source_snapshot.digest(frozen / "SNAPSHOT.json"),
        junit_sha256=runner.source_snapshot.digest(output / "tests.xml"),
        runtime_producers_sha256=runner.source_snapshot.digest(output / "runtime-producers.json"),
    )
    runner.write(output / "result.json", result)
    print(json.dumps(dict(status=result["status"], output=str(output))))
    return int(result["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
