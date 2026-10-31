"""Bounded synthetic transport controls from a one-way immutable Git snapshot."""

import argparse
import json
import os
import resource
import runpy
import sys
from pathlib import Path

from validation import source_snapshot
from validation.betse import betse_mesh_lifecycle_preparation_guard as guard

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
OWN = "validation/betse/betse_native_single_cell_dec_parent_software.py"
TEST = "tests/unit/test_betse_native_single_cell_dec_parent.py"
CLOSURE_TOOL = (
    "agent-work/cells-worker-01/workfiles/betse_normal_ecm_reviewed_successors_resources.py"
)


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def child(output):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    import pytest

    from cells.processes import betse_native_single_cell_dec_parent as transport

    core = transport.core
    codes, attempted = {}, []
    # Block actual native bodies even if an older bound method bypasses a
    # monkeypatch. Synthetic methods have different code objects. The driver
    # itself may run with synthetic collaborators; its real numerical callees
    # and upstream authentication replays cannot run in this software packet.
    for cls in (
        core.initial.source.Kernel,
        core.lifecycle.source.LifecycleKernel,
        transport.source.MeshKernel,
        transport.source.CellKernel,
    ):
        for name, method in vars(cls).items():
            if hasattr(method, "__code__"):
                codes[method.__code__] = cls.__name__ + "." + name
    for method in (
        core.initial.prepare,
        core.initial.validate_state,
        core.initial.image_stage.prepare,
        core.initial.image_stage.lattice.generate,
        transport.source.cut_through_contacts,
    ):
        codes[method.__code__] = method.__module__ + "." + method.__name__

    def blocked(frame, event, arg):
        if event == "call" and frame.f_code in codes:
            attempted.append(codes[frame.f_code])
            raise AssertionError("Native numerical entry forbidden: " + codes[frame.f_code])

    def forbidden(*args, **kwargs):
        attempted.append("real_numpy_RNG_or_pinv")
        raise AssertionError("Real RNG or pinv work forbidden in synthetic transport controls")

    core.np.random.RandomState = forbidden
    core.np.linalg.pinv = forbidden
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
    sys.setprofile(blocked)
    try:
        code = pytest.main(arguments)
    finally:
        sys.setprofile(None)
        write(
            output / "native-entry-guard.json",
            dict(
                attempted=attempted,
                blocked_methods=sorted(set(codes.values())),
                scientific_credit=False,
            ),
        )
    write(output / "pytest-exit.json", dict(returncode=int(code), argv=arguments))
    producers = {}
    for name, module in list(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if path and (
            name == "cells"
            or name.startswith(("cells.", "validation.", "PIL."))
            or name == "PIL"
            or name == Path(TEST).stem
        ):
            path = Path(path).resolve()
            producers[name] = dict(path=str(path), sha256=source_snapshot.digest(path))
            if (
                name == "cells"
                or name.startswith(("cells.", "validation."))
                or name == Path(TEST).stem
            ) and not path.is_relative_to(ROOT):
                raise RuntimeError(
                    "Software imported checkout source outside its snapshot: " + name
                )
    write(output / "runtime-producers.json", producers)
    transport._verify_sources()  # Hash checks only.
    if attempted:
        raise RuntimeError("A control attempted actual native numerical work")
    return int(code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.absolute()
    if not output.is_relative_to(BASE) or os.sched_getaffinity(0) != {6}:
        parser.error("Require CPU6 and a fresh /mnt/workspaces/Cells output")
    if args._child:
        return child(output)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    output.mkdir(parents=True, exist_ok=False)
    (output / "process").mkdir()
    closure = runpy.run_path(str(ROOT / CLOSURE_TOOL))["closure"]
    files = closure(ROOT, [OWN, TEST])
    files[CLOSURE_TOOL] = source_snapshot.digest(ROOT / CLOSURE_TOOL)
    frozen = output / "tested-source"
    snapshot = source_snapshot.freeze(ROOT, frozen, {name: name for name in files})
    write(
        output / "inputs.json",
        dict(
            source_sha256={name: row["sha256"] for name, row in snapshot["files"].items()},
            git_revision=snapshot["git_revision"],
            snapshot_manifest_sha256=source_snapshot.digest(frozen / "SNAPSHOT.json"),
            execution_source_root=str(frozen),
            selected_tests=[TEST],
            synthetic_only=True,
            positive_native_execution_released=False,
            scientific_qualification=False,
        ),
    )
    environment = dict(os.environ)
    paths = [str(frozen), str(frozen / "src")]
    for inherited in environment.get("PYTHONPATH", "").split(os.pathsep):
        if inherited and not Path(inherited).resolve().is_relative_to(ROOT):
            paths.append(inherited)
    environment.update(
        PYTHONPATH=os.pathsep.join(paths),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        CELLS_DEC_TRANSPORT_EVIDENCE=str(output / "evidence"),
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
    )
    result = guard.run_bounded(
        [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_native_single_cell_dec_parent_software",
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
    source_snapshot.assert_checkout_unchanged(frozen)
    saved = json.loads((output / "pytest-exit.json").read_text())
    native = json.loads((output / "native-entry-guard.json").read_text())
    if saved["returncode"] or native["attempted"]:
        raise RuntimeError("Focused software controls did not pass with native work blocked")
    result.update(
        synthetic_only=True,
        scientific_qualification=False,
        native_entry_attempts=native["attempted"],
        executable_DEC_parent_admitted=False,
        all11_native_owners_remain_invalid=True,
        git_revision=snapshot["git_revision"],
        snapshot_manifest_sha256=source_snapshot.digest(frozen / "SNAPSHOT.json"),
        junit_sha256=source_snapshot.digest(output / "tests.xml"),
        runtime_producers_sha256=source_snapshot.digest(output / "runtime-producers.json"),
    )
    write(output / "result.json", result)
    print(json.dumps(dict(status=result["status"], output=str(output))))
    return int(result["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
