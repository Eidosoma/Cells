"""Immutable native-blocked tissue controls on declared CPU; default remains CPU6."""

import argparse
import json
import os
import resource
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from validation.betse import betse_native_multi_cell_post_world_operators_software as inherited

runner = inherited.runner
metadata = inherited.parent.inherited._metadata
ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/betse_native_tissue_configuration_software.py"
TEST = "tests/unit/test_betse_native_tissue_configuration.py"
GROUPS = {
    "focused": "software",
    "smoke": "software_complete_fresh or software_ast",
    "factory": "software_factory_ or software_complete_fresh or software_ast",
    "abc": "software_abc_hook_ or software_factory_",
}
BEARTYPE_OVERLAY = Path("/mnt/workspaces/Cells/beartype-overlay-0.22.9-20261031-01")
BEARTYPE_INIT_SHA256 = "8b89846b9967a46362f9bf4a6d4e0f03681974d1a63243126d5d6768f0274f33"


def _beartype_inputs(group):
    if group == "smoke":
        return {}
    root = BEARTYPE_OVERLAY / "beartype"
    if runner.source_snapshot.digest(root / "__init__.py") != BEARTYPE_INIT_SHA256:
        raise ValueError("Exact existing decorator-library producer required")
    return {
        str(path): runner.source_snapshot.digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def _beartype_runtime(output):
    inputs = json.loads((output / "inputs.json").read_text())
    declared = inputs.get("external_beartype_files", {})
    loaded = {}
    for name, module in tuple(sys.modules.items()):
        if name != "beartype" and not name.startswith("beartype."):
            continue
        path = getattr(module, "__file__", None)
        if path is None:
            continue
        actual = runner.source_snapshot.digest(Path(path))
        if declared.get(path) != actual:
            raise ValueError("Loaded decorator library differs from declared inputs: " + name)
        loaded[name] = dict(path=path, sha256=actual)
    runner.write(
        output / "beartype-runtime.json", dict(loaded=loaded, declared_files=len(declared))
    )


def child(output, group):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    from cells.processes import betse_native_tissue_configuration as tissue

    original = (
        tuple(tissue._NATIVE.values()) + tuple(tissue._STORES.values()) + (tissue._native_setup,)
    )
    codes = {fn.__code__: fn.__qualname__ for fn in original}
    attempted = []
    previous, trace = sys.getprofile(), sys.gettrace()

    def setprofile(delegate):
        if delegate is None:
            sys.setprofile(previous)
            return

        def profile(frame, event, arg):
            if event == "call" and (
                frame.f_code in codes
                or frame.f_code is tissue._lazy_factory.__code__
                and frame.f_locals.get("name") not in frame.f_locals["context"].factories
                or frame.f_code.co_filename.startswith(str(tissue.aliases.NATIVE) + "/")
            ):
                attempted.append(
                    dict(method=frame.f_code.co_qualname, file=frame.f_code.co_filename)
                )
                raise AssertionError(
                    "Actual native tissue/descriptor/factory/source entry forbidden"
                )
            delegate(frame, event, arg)
            if previous is not None:
                previous(frame, event, arg)

        sys.setprofile(profile)

    facade = SimpleNamespace(**dict(vars(sys), setprofile=setprofile))
    try:
        code = metadata(inherited.child, ROOT=ROOT, TEST=TEST, GROUPS=GROUPS, sys=facade)(
            output, group
        )
    finally:
        restored = sys.getprofile() is previous and sys.gettrace() is trace
        sys.setprofile(previous)
        sys.settrace(trace)
        runner.write(
            output / "tissue-native-entry-guard.json",
            dict(
                attempted=attempted,
                blocked_codes=list(codes.values()),
                all_native_source_paths_blocked=True,
                prior_trace_and_profile_restored=restored,
                scientific_credit=0,
            ),
        )
    if attempted:
        raise RuntimeError("A control attempted original tissue work")
    _beartype_runtime(output)
    tissue._verify_sources()
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", choices=GROUPS, required=True)
    parser.add_argument("--cpu", type=int, choices=(4, 6), default=6)
    parser.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.absolute()
    if not output.is_relative_to(runner.BASE) or os.sched_getaffinity(0) != {args.cpu}:
        parser.error("Require declared CPU affinity and fresh output below /mnt/workspaces/Cells")
    if args._child:
        return child(output, args.group)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    output.mkdir(parents=True, exist_ok=False)
    (output / "process").mkdir()
    external = _beartype_inputs(args.group)
    closure = runpy.run_path(str(ROOT / runner.CLOSURE_TOOL))["closure"]
    files = closure(ROOT, [OWN, TEST])
    files[runner.CLOSURE_TOOL] = runner.source_snapshot.digest(ROOT / runner.CLOSURE_TOOL)
    frozen = output / "tested-source"
    snapshot = runner.source_snapshot.freeze(ROOT, frozen, {name: name for name in files})
    manifest = runner.source_snapshot.digest(frozen / "SNAPSHOT.json")
    runner.write(
        output / "inputs.json",
        dict(
            git_revision=snapshot["git_revision"],
            snapshot_manifest_sha256=manifest,
            source_sha256={name: row["sha256"] for name, row in snapshot["files"].items()},
            software_group=args.group,
            cpu=args.cpu,
            external_beartype_files=external,
            pytest_selection=GROUPS[args.group],
            synthetic_only=True,
            actual_native_release=False,
        ),
    )
    environment = dict(os.environ)
    paths = [str(frozen), str(frozen / "src")] + [
        p
        for p in environment.get("PYTHONPATH", "").split(os.pathsep)
        if p and not Path(p).resolve().is_relative_to(ROOT)
    ]
    if external:
        paths.append(str(BEARTYPE_OVERLAY))
    environment.update(
        PYTHONPATH=os.pathsep.join(paths),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        CELLS_TISSUE_CONFIGURATION_EVIDENCE=str(output / "evidence"),
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
    )
    environment.pop("PYTEST_ADDOPTS", None)
    try:
        process = runner.guard.run_bounded(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_native_tissue_configuration_software",
                "--output",
                str(output),
                "--group",
                args.group,
                "--cpu",
                str(args.cpu),
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
    except subprocess.CalledProcessError:
        process = json.loads((output / "process/failure.json").read_text())
    required = [
        "runtime-producers.json",
        "tests.xml",
        "native-entry-guard.json",
        "tail-native-entry-guard.json",
        "post-world-native-entry-guard.json",
        "tissue-native-entry-guard.json",
        "beartype-runtime.json",
    ]
    missing = [name for name in required if not (output / name).is_file()]
    if missing:
        runner.write(
            output / "result.json",
            dict(
                process,
                status="failed_incomplete_software",
                missing_terminal_artifacts=missing,
                snapshot_manifest_sha256=manifest,
                complete_execution_verification=False,
                synthetic_only=True,
                scientific_credit=0,
                process_failure_sha256=runner.source_snapshot.digest(
                    output / "process/failure.json"
                ),
            ),
        )
        return 1
    tools = inherited.parent.inherited.inherited
    authority = metadata(tools.verify_frozen_execution, TEST=TEST)(
        frozen, manifest, output / "runtime-producers.json"
    )
    runner.write(output / "execution-verification.json", authority)
    integration = tools.checkout_integration_status(frozen, output)
    runner.write(output / "checkout-integration.json", integration)
    guards = {
        name: json.loads((output / name).read_text())
        for name in (
            "native-entry-guard.json",
            "tail-native-entry-guard.json",
            "post-world-native-entry-guard.json",
            "tissue-native-entry-guard.json",
        )
    }
    if any(row["attempted"] for row in guards.values()):
        raise RuntimeError("A native/source body was attempted")
    if not guards["tissue-native-entry-guard.json"]["prior_trace_and_profile_restored"]:
        raise RuntimeError("Outer guard not restored")
    result = dict(
        process,
        synthetic_only=True,
        actual_native_release=False,
        snapshot_manifest_sha256=manifest,
        runtime_producers_sha256=runner.source_snapshot.digest(output / "runtime-producers.json"),
        beartype_runtime_sha256=runner.source_snapshot.digest(output / "beartype-runtime.json"),
        junit_sha256=runner.source_snapshot.digest(output / "tests.xml"),
        guard_pins={name: runner.source_snapshot.digest(output / name) for name in guards},
        frozen_execution_authority=authority,
        checkout_integration=integration,
        all11_owners_invalid=True,
        all12_postcut_science_held=True,
        full_phase_parameters_YAML_checkpoint_physical_admitted=False,
    )
    runner.write(output / "result.json", result)
    print(json.dumps(dict(status=result["status"], output=str(output))))
    return int(result["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
