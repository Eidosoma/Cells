"""CPU5 frozen metadata controls for SIM launch and saved-report consumers only."""

import argparse
import importlib
import json
import os
import resource
import sys
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType

from validation.betse import native_init_terminal_reference_software as base

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "validation/betse/native_sim_demo_report.py"
TEST = "tests/unit/test_native_sim_demo_report.py"
LAUNCH = "validation/betse/native_seed_demo_launch.py"
LAUNCH_TEST = "tests/unit/test_native_seed_demo_launch.py"
FILE = "validation/betse/native_sim_demo_report_software.py"
MODULE = "validation.betse.native_sim_demo_report_software"
OWNED = (SOURCE, TEST, FILE, LAUNCH, LAUNCH_TEST)
RELEASE = "CELLS_SIM_DEMO_REPORT_BLOCKED_SOFTWARE"
POLICY = dict(base.POLICY, cpu=5)
BASE, CLOSURE = base.BASE, base.CLOSURE
snapshot, guard, runtime = base.snapshot, base.guard, base.runtime
_RAW_FAILURES = []


def forbidden(frame):
    module, name = frame.f_globals.get("__name__", ""), frame.f_code.co_name
    return base.forbidden(frame) or (
        module == "validation.betse.native_seed_demo"
        and name in ("run_demo", "_execute", "_dependencies", "prepare")
        or module == "validation.betse.native_sim_demo"
        or module == "validation.betse.betse_native_parameter_world_ready_qualification"
        and name in ("_execute", "acquire_world_ready", "acquire_current_world_ready")
    )


blocked = contextmanager(
    FunctionType(base.blocked.__wrapped__.__code__, dict(vars(base), forbidden=forbidden))
)


def _namespace():
    return dict(
        vars(base),
        **{
            name: globals()[name]
            for name in ("ROOT", "SOURCE", "TEST", "FILE", "MODULE", "OWNED", "RELEASE", "POLICY")
        },
        __file__=__file__,
    )


def prepare(output, select):
    return FunctionType(base.prepare.__code__, _namespace())(output, select)


def child(output, select):
    import pytest

    inputs = json.loads((output / "inputs.json").read_text())
    if inputs["software_release_requested"] is not True or inputs["policy"] != POLICY:
        raise ValueError("Explicit immutable CPU5 blocked software required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if snapshot.digest(ROOT / name) != inputs["owned_files"][name]:
            raise ValueError("Frozen selected producer changed")
    report = importlib.import_module("validation.betse.native_sim_demo_report")
    if Path(report.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Actual frozen report required")
    snapshot.write_json(output / "source-plan.json", report.source_plan())
    os.environ[RELEASE] = "1"
    os.environ["BETSE_NATIVE_SEED_DEMO_LAUNCH_SOFTWARE_RELEASED"] = "1"
    final_guards = output / "final-guards"
    final_guards.mkdir()

    class Reports(base.Reports):
        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_protocol(self, item, nextitem):
            before = (sys.getprofile(), sys.gettrace())
            yield
            after = (sys.getprofile(), sys.gettrace())
            snapshot.write_json(
                final_guards / f"guard-{len(tuple(final_guards.iterdir())):04d}.json",
                dict(
                    nodeid=item.nodeid,
                    prior_profile_trace_restored=all(
                        a is b for a, b in zip(before, after, strict=True)
                    ),
                    inherited_failure_banks_empty=all(
                        not getattr(module, "_RAW_GUARDS", ())
                        for name, module in tuple(sys.modules.items())
                        if name
                        in (
                            "tests.unit.test_native_seed_demo_launch",
                            "tests.unit.test_native_sim_demo_report",
                        )
                    ),
                    native_source_owner_RNG_or_operator_credit=0,
                ),
            )

    code, primary, errors = 1, None, []
    try:
        code = pytest.main(
            [
                "--noconftest",
                "-q",
                "-x",
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",
                "--basetemp=" + str(output / "pytest"),
                "--junitxml=" + str(output / "tests.xml"),
                str(ROOT / LAUNCH_TEST),
                str(ROOT / TEST),
                "-k",
                select,
            ],
            plugins=[Reports(output / "reports")],
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        for artifact_name, action in (
            ("runtime.json", runtime.inventory),
            (
                "loaded-selected.json",
                lambda: {name: manifest["files"][name]["sha256"] for name in OWNED},
            ),
        ):
            try:
                snapshot.write_json(output / artifact_name, action())
            except BaseException as error:
                errors.append((artifact_name, error))
        if errors:
            _RAW_FAILURES.append((primary, errors))
            if primary is None:
                raise errors[0][1]
    return int(code)


def software(output, select):
    if os.environ.get(RELEASE) != "1" or os.sched_getaffinity(0) != {POLICY["cpu"]}:
        raise ValueError("Explicit CPU5 blocked-software release required")
    output = Path(output).absolute()
    if (
        output.exists()
        or not output.is_relative_to(BASE)
        or any(path.is_symlink() for path in (output, *output.parents))
    ):
        raise ValueError("Fresh contained output required")
    output.mkdir(parents=True)
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
    )
    metadata = output / "metadata"
    metadata.mkdir()
    guard.run_bounded(
        [sys.executable, "-B", "-m", MODULE, "--prepare", str(output), "--select", select],
        directory=metadata,
        cwd=ROOT,
        env=env,
        timeout=120,
        max_rss_bytes=POLICY["metadata_bytes"],
        min_available_bytes=POLICY["reserve_bytes"],
    )
    frozen = output / "source"
    inputs = json.loads((output / "inputs.json").read_text())
    manifest = snapshot.verify(frozen, manifest_sha256=inputs["snapshot_sha256"])
    snapshot.assert_checkout_unchanged(frozen)
    env["PYTHONPATH"] = os.pathsep.join([str(frozen), str(frozen / "src")])
    process = output / "process"
    process.mkdir()
    result, failures = None, []
    try:
        result = guard.run_bounded(
            [sys.executable, "-B", "-m", MODULE, "--child", str(output), "--select", select],
            directory=process,
            cwd=frozen,
            env=env,
            timeout=POLICY["wall_seconds"],
            max_rss_bytes=POLICY["max_rss_bytes"],
            min_available_bytes=POLICY["reserve_bytes"],
        )
    except Exception as error:
        failures.append(dict(stage="worker", type=type(error).__name__, message=str(error)))
    try:
        snapshot.verify(frozen, manifest_sha256=inputs["snapshot_sha256"])
        loaded = json.loads((output / "runtime.json").read_text())["loaded_files"]
        producers = {}
        for row in loaded.values():
            path = Path(row["path"])
            if path.is_relative_to(ROOT):
                raise ValueError("Worker loaded mutable checkout source")
            if path.is_relative_to(frozen):
                name = str(path.relative_to(frozen))
                if row.get("sha256") != manifest["files"].get(name, {}).get("sha256"):
                    raise ValueError("Loaded source does not match snapshot")
                producers[name] = row["sha256"]
        if not all(name in producers for name in OWNED):
            raise ValueError("Selected loaded producer missing")
        snapshot.write_json(output / "producer-bindings.json", producers)
    except Exception as error:
        failures.append(
            dict(stage="final_source_binding", type=type(error).__name__, message=str(error))
        )
    cases = (
        list(ET.parse(output / "tests.xml").iter("testcase"))
        if (output / "tests.xml").exists()
        else []
    )
    receipts = sorted((output / "pytest").rglob("native-blocked.json"))
    final = [
        json.loads(path.read_text()) for path in sorted((output / "final-guards").glob("*.json"))
    ]
    guard_ok = (
        len(cases) == len(receipts) == len(final) > 0
        and all(json.loads(path.read_text())["attempted"] == [] for path in receipts)
        and all(
            row["prior_profile_trace_restored"] is True
            and row["inherited_failure_banks_empty"] is True
            for row in final
        )
    )
    for path in receipts:
        row = json.loads(path.read_text())
        if "cleanup_errors" in row:
            guard_ok &= row["cleanup_errors"] == [] and row["prior_profile_trace_restored"] is True
        else:
            guard_ok &= row.get("secondary_cleanup") == []
    integration = None
    try:
        snapshot.assert_checkout_unchanged(frozen)
    except Exception as error:
        integration = dict(type=type(error).__name__, message=str(error))
    passed = result is not None and result.get("returncode") == 0 and guard_ok and not failures
    snapshot.write_json(
        output / "result.json",
        dict(
            status="passed" if passed else "failed",
            process=result,
            errors=failures,
            selected_cases=len(cases),
            guard_receipts=len(receipts),
            complete_guards=guard_ok,
            source_native_RNG_operator_or_reference_entries=0 if guard_ok else None,
            snapshot_sha256=inputs["snapshot_sha256"],
            owned_files=inputs["owned_files"],
            checkout_integration_pending=integration,
            scientific_credit=0,
        ),
    )
    return int(not passed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument(
        "--select", default="launch_sim or sim_report or launch_initial_rng or launch_init_terminal"
    )
    args = parser.parse_args()
    if args.child is not None:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        return child(args.child, args.select)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    if args.prepare is not None:
        prepare(args.prepare, args.select)
        return 0
    if args.software is not None:
        return software(args.software, args.select)
    parser.error("Choose immutable preparation or blocked software")


if __name__ == "__main__":
    raise SystemExit(main())
