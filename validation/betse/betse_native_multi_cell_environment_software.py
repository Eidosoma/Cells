"""Blocked-native multi-cell environment controls using the existing resource guard."""

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
OWN = "validation/betse/betse_native_multi_cell_environment_software.py"
TEST = "tests/unit/test_betse_native_multi_cell_environment.py"
GROUPS = {
    "focused": "software",
    "execution_contract": "software_frozen_execution",
    "repair_contract": "software_frozen_execution or software_grid_original_numpy",
}


def verify_frozen_execution(frozen, manifest_sha256, runtime_path):
    """Authenticate executed immutable bytes, independent of later checkout edits."""
    frozen, runtime_path = Path(frozen).absolute(), Path(runtime_path).absolute()
    snapshot = runner.source_snapshot.verify(frozen, manifest_sha256=manifest_sha256)
    runner.source_snapshot.regular_file(runtime_path.parent, runtime_path.name)
    runtime_sha = runner.source_snapshot.digest(runtime_path)
    producers = json.loads(runtime_path.read_text())
    required = {"cells", runner.__name__, Path(TEST).stem}
    if not isinstance(producers, dict) or not required <= set(producers):
        raise ValueError("Missing actual loaded execution producers")
    for name, row in producers.items():
        path = Path(row["path"])
        if not path.is_absolute() or path != path.resolve():
            raise ValueError("Loaded producer path is not its recorded actual origin")
        runner.source_snapshot.regular_file(path.parent, path.name)
        if runner.source_snapshot.digest(path) != row["sha256"]:
            raise ValueError("Loaded producer bytes changed: " + name)
        if name in required or name.startswith(("cells.", "validation.")):
            if not path.is_relative_to(frozen):
                raise ValueError("Loaded producer escaped immutable execution image: " + name)
            relative = str(path.relative_to(frozen))
            if (
                relative not in snapshot["files"]
                or snapshot["files"][relative]["sha256"] != row["sha256"]
            ):
                raise ValueError("Loaded producer is not a selected frozen payload: " + name)
        elif name != "PIL" and not name.startswith("PIL."):
            raise ValueError("Unexpected execution producer namespace: " + name)
    if runner.source_snapshot.digest(runtime_path) != runtime_sha:
        raise ValueError("Runtime producer record changed during verification")
    return dict(
        authority="verified immutable snapshot and actual loaded producer hashes",
        snapshot_manifest_sha256=manifest_sha256,
        frozen_git_revision=snapshot["git_revision"],
        runtime_producers_sha256=runtime_sha,
        verified_loaded_producers=len(producers),
        current_checkout_used_as_execution_authority=False,
    )


def checkout_integration_status(frozen, output):
    """Retain live-source drift as integration metadata, never as a frozen test result."""
    frozen, output = Path(frozen).absolute(), Path(output).absolute()
    snapshot = runner.source_snapshot.verify(frozen)
    repository = Path(snapshot["repository"])
    source_rows = {row["checkout_path"]: row for row in snapshot["files"].values()}
    sources = sorted(source_rows)
    status = dict(
        frozen_git_revision=snapshot["git_revision"],
        integration_pending=False,
        explicit_later_integration_check_required=False,
        selected_source_drift=[],
        selected_stat_drift=[],
        checkout_source_policy_error=None,
        selected_current_snapshot=None,
        selected_current_snapshot_error=None,
        frozen_execution_result_changed=False,
    )
    try:
        runner.source_snapshot.assert_checkout_unchanged(frozen)
    except Exception as error:
        status.update(
            integration_pending=True,
            checkout_postcheck_error=dict(type=type(error).__name__, message=str(error)),
        )
    try:
        runner.source_snapshot._selected(repository, sources)
    except Exception as error:
        status["checkout_source_policy_error"] = dict(type=type(error).__name__, message=str(error))
    for name in sources:
        row = source_rows[name]
        try:
            current = runner.source_snapshot._observe(repository, name)
            if current["sha256"] != row["sha256"]:
                status["selected_source_drift"].append(
                    dict(
                        checkout_path=name,
                        frozen_sha256=row["sha256"],
                        current_sha256=current["sha256"],
                    )
                )
            elif current["observation"] != row["observation"]:
                status["selected_stat_drift"].append(name)
        except Exception as error:
            status["selected_source_drift"].append(
                dict(
                    checkout_path=name,
                    frozen_sha256=row["sha256"],
                    current_sha256=None,
                    error=dict(type=type(error).__name__, message=str(error)),
                )
            )
    try:
        state = runner.source_snapshot.git_state(repository, sources)
        status.update(
            current_git_revision=state["revision"],
            selected_status_sha256=hashlib.sha256(state["status"]).hexdigest(),
            selected_index_sha256=hashlib.sha256(state["index"]).hexdigest(),
            current_patch_sha256=hashlib.sha256(state["patch"]).hexdigest(),
            checkout_bookkeeping_drift=(
                state["revision"] != snapshot["git_revision"]
                or state["status"].decode("utf-8", "surrogateescape")
                != snapshot["selected_status_porcelain_v1_z"]
                or state["index"].decode("utf-8", "surrogateescape")
                != snapshot["selected_index_stage_z"]
                or hashlib.sha256(state["patch"]).hexdigest() != snapshot["patch_sha256"]
            ),
        )
    except Exception as error:
        status["checkout_state_error"] = dict(type=type(error).__name__, message=str(error))
    selected_changed = bool(
        status["selected_source_drift"] or status["checkout_source_policy_error"]
    )
    status["explicit_later_integration_check_required"] = selected_changed
    status["integration_pending"] = bool(
        status["integration_pending"]
        or selected_changed
        or status["selected_stat_drift"]
        or status.get("checkout_bookkeeping_drift")
        or status.get("checkout_state_error")
    )
    if selected_changed:
        # Preserve the second version through the same strict one-way freezer.
        # Missing/linked/ignored/concurrently changing sources still refuse;
        # their unresolved capture is explicit integration evidence.
        try:
            current_path = output / "selected-checkout-after-run"
            current = runner.source_snapshot.freeze(
                repository,
                current_path,
                {name: row["checkout_path"] for name, row in snapshot["files"].items()},
            )
            status["selected_current_snapshot"] = dict(
                path=str(current_path / "SNAPSHOT.json"),
                sha256=runner.source_snapshot.digest(current_path / "SNAPSHOT.json"),
                git_revision=current["git_revision"],
                executed=False,
            )
        except Exception as error:
            status["selected_current_snapshot_error"] = dict(
                type=type(error).__name__, message=str(error)
            )
    return status


def child(output, group):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    (output / "case-reports").mkdir(exist_ok=False)
    import pytest

    from cells.processes import betse_native_multi_cell_caller as multi
    from cells.processes import betse_native_multi_cell_environment as continuation
    from cells.processes import betse_native_single_cell_environment as environment
    from cells.processes import betse_native_single_cell_initial_geometry as caller
    from cells.processes import betse_native_single_cell_make_ecm as ecm
    from cells.processes import betse_native_single_cell_poisson as poisson

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
    original_methods += [
        ecm._MAKE,
        ecm._INIT,
        ecm._GRID,
        ecm.aliases._descriptor_from_source,
        *continuation._METHODS.values(),
        continuation._INIT,
        continuation._GRID,
        continuation._allocate_native_tree,
    ]
    original_methods += [
        *environment._METHODS.values(),
        caller.parameters._ENVIRONMENT_STORES,
        environment._allocate_native_tree,
        environment._GRIDDATA,
        environment._GAUSSIAN,
        *poisson._CALLER.values(),
        poisson._LAPLACIAN,
        multi._STORES,
        multi._CELL_INIT,
        multi._LATTICE,
        multi._VORONOI,
        multi._INDEX,
        multi._PIPELINE,
        *multi._NATIVE.values(),
        *multi._TOOL_METHODS.values(),
        multi.lifecycle.validate_state,
        multi.initial.validate_state,
        multi.clipped.validate_state,
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
            poisson.source,
            multi.source,
            multi.clipped.source,
            multi.lifecycle.source,
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
    native_names.update(("makeLaplacian", *poisson.METHODS))
    native_names.update(
        ("make_voronoi_non_svg", "clip_and_refine", *multi._NATIVE, *multi._TOOL_METHODS)
    )
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
    continuation._verify_sources()
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
    files = closure(ROOT, [OWN, TEST, "tests/unit/test_betse_native_multi_cell_caller.py"])
    files[runner.CLOSURE_TOOL] = runner.source_snapshot.digest(ROOT / runner.CLOSURE_TOOL)
    frozen = output / "tested-source"
    snapshot = runner.source_snapshot.freeze(ROOT, frozen, {name: name for name in files})
    manifest_sha256 = runner.source_snapshot.digest(frozen / "SNAPSHOT.json")
    runner.write(
        output / "inputs.json",
        dict(
            git_revision=snapshot["git_revision"],
            snapshot_manifest_sha256=manifest_sha256,
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
        CELLS_MULTI_ENV_EVIDENCE=str(output / "evidence"),
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
            "validation.betse.betse_native_multi_cell_environment_software",
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
    try:
        execution = verify_frozen_execution(
            frozen, manifest_sha256, output / "runtime-producers.json"
        )
    except Exception as error:
        runner.write(
            output / "execution-verification-failure.json",
            dict(
                status="frozen_execution_evidence_invalid",
                stage="immutable_source_verification",
                error_type=type(error).__name__,
                message=str(error),
                snapshot_manifest_sha256=manifest_sha256,
                numerical_credit=False,
            ),
        )
        raise
    runner.write(output / "execution-verification.json", execution)
    integration = checkout_integration_status(frozen, output)
    runner.write(output / "checkout-integration.json", integration)
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
        multi_cell_geometry_ECM_environment_source_only=True,
        git_revision=snapshot["git_revision"],
        snapshot_manifest_sha256=manifest_sha256,
        junit_sha256=runner.source_snapshot.digest(output / "tests.xml"),
        runtime_producers_sha256=runner.source_snapshot.digest(output / "runtime-producers.json"),
        execution_verification_sha256=runner.source_snapshot.digest(
            output / "execution-verification.json"
        ),
        checkout_integration_sha256=runner.source_snapshot.digest(
            output / "checkout-integration.json"
        ),
        integration_pending=integration["integration_pending"],
        explicit_later_integration_check_required=integration[
            "explicit_later_integration_check_required"
        ],
    )
    runner.write(output / "result.json", result)
    print(json.dumps(dict(status=result["status"], output=str(output))))
    return int(result["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
