"""Synthetic ordinary environment/mask controls with the existing snapshot/resource guard."""

import argparse
import hashlib
import json
import os
import resource
import runpy
import sys
from pathlib import Path

from validation.betse import betse_native_single_cell_dec_parent_software as runner

ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/betse_native_single_cell_environment_software.py"
TEST = "tests/unit/test_betse_native_single_cell_environment.py"
UPSTREAM_TESTS = (
    "tests/unit/test_betse_native_single_cell_make_ecm.py",
    "tests/unit/test_betse_native_single_cell_initial_geometry.py",
    "tests/unit/test_betse_native_single_cell_caller_completion.py",
)


GROUPS = {
    "smoke": "literal_order or fresh_projection",
    "source": "literal_order or fresh_projection or legacy_ecm or source_failures or native_style",
    "ownership_a": (
        "source_child_rejects and (caller_array or equal_alias or tree_data or tree_edge "
        "or tree_class or parent_invalid or parameter)"
    ),
    "ownership_b": "source_child_rejects and (dispatch or RNG or observer or method or helper)",
    "retention": "local_capture or sealing_failure or reentrancy",
}


def child(output, group):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    (output / "case-reports").mkdir(exist_ok=False)
    import pytest

    from cells.processes import betse_native_single_cell_environment as environment
    from cells.processes import betse_native_single_cell_initial_geometry as caller
    from cells.processes import betse_native_single_cell_make_ecm as ecm

    original_methods = [
        caller.images.images.prepare,
        caller.images.images.validate_prelude,
        caller.images.images.lattice.generate,
        caller.images.images.lattice.validate_state,
        caller.images.prepare,
        caller.callers._validate_request,
        caller.core.prepare,
        caller.core.validate_request,
        caller.core.initial.prepare,
        caller.core.initial.validate_state,
        caller.parameters._construct,
        caller.parameters._PARAMETER_STORES,
        caller.parameters._GEOMETRY_STORES,
        caller.callers._Parameters.__init__,
        caller.completion._TAIL_ALIASES,
        caller.completion._CELL_INDEX,
        *caller._NATIVE.values(),
        caller.source.flatten,
        caller.meshes._CONSTRUCTOR,
        caller.meshes._PRE_MESH,
        caller.meshes._CORE,
        caller.meshes._INIT_MESH,
        *caller.meshes._INHERITED_NATIVE.values(),
    ]
    original_methods += [ecm._MAKE, ecm._INIT, ecm._GRID, ecm.aliases._descriptor_from_source]
    original_methods += [
        *environment._METHODS.values(),
        caller.parameters._ENVIRONMENT_STORES,
        environment._allocate_native_tree,
        environment._GRIDDATA,
        environment._GAUSSIAN,
    ]
    codes = {m.__code__: m.__module__ + "." + m.__qualname__ for m in original_methods}
    source_files = {
        str(Path(module.__file__).resolve())
        for module in (
            caller.core.initial.source,
            caller.core.lifecycle.source,
            caller.callers.source,
            caller.images.source,
            caller.parameters.source,
            caller.parameters.geometry_source,
            caller.source,
            ecm.source,
            environment.source,
        )
    }
    native_names = {
        "__init__",
        "get_image_mask",
        "load_image",
        "interp2d_linear",
        "get_clipped_points_index",
        "pick_cells",
        "pick_cells_and_mems",
        "cell_index",
        "make_voronoi_mesh_aliases",
        "_make_cell_lattice",
        "init_mesh",
        "pre_mesh",
        "create_core_operators",
        "create_tri_map",
        "create_mappings",
    }
    native_names.update(caller.meshes.GUARDED_NATIVE_METHODS)
    native_names.update(caller.METHODS)
    native_names.add("flatten")
    native_names.add("initialize_source_stores")
    native_names.update(("makeECM", "cell_grid", "environment", "assign_grid_len", "make_maskM"))
    attempted = []

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_globals.get("__name__", "") == "betse"
            or frame.f_globals.get("__name__", "").startswith("betse.")
            or (frame.f_code.co_filename in source_files and frame.f_code.co_name in native_names)
        ):
            attempted.append(codes.get(frame.f_code, frame.f_code.co_qualname))
            raise AssertionError("Original source execution forbidden in caller software control")

    def forbidden(*a, **k):
        attempted.append("real_numpy_RNG_or_pinv")
        raise AssertionError("Real RNG/operator entry forbidden")

    caller.core.np.random.RandomState = forbidden
    caller.core.np.linalg.pinv = forbidden
    caller.images.Image.open = forbidden
    caller.images.RectBivariateSpline = forbidden
    caller.images.ConvexHull = forbidden
    ecm.source.cKDTree = forbidden
    arguments = [
        "-q",
        "--noconftest",
        "-c",
        "/dev/null",
        "-p",
        "no:cacheprovider",
        str(ROOT / TEST),
        "-k",
        GROUPS[group],
        "--junitxml=" + str(output / "tests.xml"),
        "--basetemp=" + str(output / "tmp"),
    ]
    sys.setprofile(profile)
    try:

        class Reports:
            def pytest_runtest_logreport(self, report):
                if report.when == "call" or report.failed:
                    key = hashlib.sha256((report.nodeid + report.when).encode()).hexdigest()
                    runner.write(
                        output / "case-reports" / (key + ".json"),
                        dict(
                            nodeid=report.nodeid,
                            when=report.when,
                            outcome=report.outcome,
                            traceback=str(report.longrepr) if report.failed else None,
                            native_entry_attempts=list(attempted),
                        ),
                    )

        code = pytest.main(arguments, plugins=[Reports()])
    finally:
        sys.setprofile(None)
        runner.write(
            output / "native-entry-guard.json",
            dict(
                attempted=attempted,
                blocked_methods=list(codes.values()) + sorted(native_names),
                numerical_credit=False,
            ),
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
    environment._verify_sources()
    if attempted:
        raise RuntimeError("A synthetic control attempted actual source work")
    return int(code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", choices=tuple(GROUPS), required=True)
    parser.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.absolute()
    if not output.is_relative_to(runner.BASE) or os.sched_getaffinity(0) != {6}:
        parser.error("Require CPU6 and a fresh /mnt/workspaces/Cells output")
    if args._child:
        return child(output, args.group)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    output.mkdir(parents=True, exist_ok=False)
    (output / "process").mkdir()
    closure = runpy.run_path(str(ROOT / runner.CLOSURE_TOOL))["closure"]
    files = closure(ROOT, [OWN, TEST, *UPSTREAM_TESTS])
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
            software_group=args.group,
            pytest_selection=GROUPS[args.group],
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
        CELLS_ENVIRONMENT_EVIDENCE=str(output / "evidence"),
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
            "validation.betse.betse_native_single_cell_environment_software",
            "--output",
            str(output),
            "--group",
            args.group,
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
        software_group=args.group,
        actual_source_replay_released=False,
        native_entry_attempts=attempted,
        all11_owners_remain_invalid=True,
        full_caller_continuation_admitted=False,
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
