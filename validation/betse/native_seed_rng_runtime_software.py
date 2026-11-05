"""One immutable CPU5 batch for versioned RNG-origin metadata and readers."""

import argparse
import importlib
import json
import os
import resource
import runpy
import sys
from pathlib import Path
from types import FunctionType

from validation.betse import native_sim_demo_report_software as saved
from validation.betse import native_sim_demo_software as orchestration

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "validation/betse/native_rng_runtime.py"
TEST = "tests/unit/test_native_rng_runtime.py"
FILE = "validation/betse/native_seed_rng_runtime_software.py"
MODULE = "validation.betse.native_seed_rng_runtime_software"
RELEASE = "CELLS_RNG_BUILTIN_METADATA_SOFTWARE"
TESTS = (
    TEST,
    "tests/unit/test_native_seed_rng_report.py",
    "tests/unit/test_native_seed_demo.py",
    "tests/unit/test_native_seed_demo_launch.py",
    "tests/unit/test_native_sim_demo_report.py",
)
OWNED = (
    SOURCE,
    "validation/betse/native_seed_initial_rng.py",
    "validation/betse/native_seed_demo.py",
    "validation/betse/native_seed_demo_launch.py",
    "validation/betse/native_sim_demo_report.py",
    "validation/betse/native_seed_rng_report.py",
    FILE,
    *TESTS,
)
POLICY = dict(saved.POLICY)
snapshot, guard, runtime = saved.snapshot, saved.guard, saved.runtime
BASE, CLOSURE = saved.BASE, saved.CLOSURE
blocked = orchestration.blocked
_RAW_FAILURES = []


def _namespace():
    return dict(
        vars(saved),
        **{
            key: globals()[key]
            for key in ("ROOT", "SOURCE", "TEST", "FILE", "MODULE", "OWNED", "RELEASE", "POLICY")
        },
        __file__=__file__,
    )


def prepare(output, select):
    snapshot.write_json(output / "external-runtime.json", orchestration._overlay())
    files = runpy.run_path(str(ROOT / CLOSURE))["closure"](ROOT, list(OWNED))
    for name in (CLOSURE, "tests/__init__.py", "pyproject.toml"):
        files[name] = snapshot.digest(ROOT / name)
    manifest = snapshot.freeze(ROOT, output / "source", {name: name for name in files})
    snapshot.assert_checkout_unchanged(output / "source")
    snapshot.write_json(
        output / "inputs.json",
        dict(
            kind="cells.initial_rng_builtin_metadata_software@1",
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
            snapshot_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            selection=select,
            policy=POLICY,
            software_release_requested=os.environ.get(RELEASE) == "1",
            native_source_reference_owner_or_scientific_release=False,
        ),
    )


def child(output, select):
    import pytest

    inputs = json.loads((output / "inputs.json").read_text())
    if inputs["software_release_requested"] is not True or inputs["policy"] != POLICY:
        raise ValueError("Explicit frozen CPU5 RNG metadata release required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if snapshot.digest(ROOT / name) != inputs["owned_files"][name]:
            raise ValueError("Frozen selected RNG producer changed")
    declared = json.loads((output / "external-runtime.json").read_text())
    if orchestration._overlay() != declared:
        raise ValueError("Predeclared Pillow definition overlay changed")
    sys.path.append(str(orchestration.OVERLAY))
    importlib.import_module("cells.processes.betse_native_parameter_yaml_prefix")
    report = importlib.import_module("validation.betse.native_seed_rng_report")
    snapshot.write_json(output / "source-plan.json", report.source_plan())
    for key in (
        RELEASE,
        "BETSE_NATIVE_SEED_DEMO_SOFTWARE_RELEASED",
        "BETSE_NATIVE_SEED_DEMO_LAUNCH_SOFTWARE_RELEASED",
        "CELLS_SIM_DEMO_REPORT_BLOCKED_SOFTWARE",
    ):
        os.environ[key] = "1"
    final_guards = output / "final-guards"
    final_guards.mkdir()

    class Reports(saved.base.Reports):
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
                            "tests.unit.test_native_seed_demo",
                            "tests.unit.test_native_seed_demo_launch",
                            "tests.unit.test_native_sim_demo_report",
                        )
                    ),
                    native_source_owner_RNG_or_operator_credit=0,
                ),
            )

    primary, errors, code = None, [], 1
    try:
        code = int(
            pytest.main(
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
                    *(str(ROOT / name) for name in TESTS),
                    "-k",
                    select,
                ],
                plugins=[Reports(output / "reports")],
            )
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
    return code


def software(output, select):
    return FunctionType(saved.software.__code__, _namespace())(output, select)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "child", "software"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument(
        "--select", default="rng_runtime or rng_report or rng_origin or demo_initial_rng"
    )
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (2**30 if args.child else 512 * 2**20, 2**30))
    if args.child:
        return child(args.child, args.select)
    if args.prepare:
        prepare(args.prepare, args.select)
        return 0
    if args.software:
        return software(args.software, args.select)
    parser.error("Choose immutable preparation or blocked software")


if __name__ == "__main__":
    raise SystemExit(main())
