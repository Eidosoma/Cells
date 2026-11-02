"""Prepared immutable dyna software runner; actual source work stays blocked."""

import argparse
import hashlib
import resource
import runpy
import sys
import traceback
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_phase_assembly_software as phase

inherited, snapshot = phase.inherited, phase.snapshot
ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/betse_native_phase_dyna_software.py"
TEST = "tests/unit/test_betse_native_phase_dyna.py"
SOURCE = "src/cells/processes/betse_native_phase_dyna.py"
LITERAL = "src/cells/processes/betse_native_phase_dyna_source.py"
MODULE = "validation.betse.betse_native_phase_dyna_software"
OWNED = (SOURCE, LITERAL, TEST, FILE)


def prepare(output, select):
    from cells.processes import betse_native_phase_dyna as stage

    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Fresh canonical-checkout dyna snapshot required")
    plan = stage.source_plan()
    starts = list(OWNED)
    if stage.KEY_SHA256 is not None:
        # Dynamic import is not a reason to omit the actual Key producer or
        # its ordinary static dependency closure from the execution image.
        starts.append(stage.KEY_FILE)
    files = runpy.run_path(str(ROOT / inherited.CLOSURE))["closure"](ROOT, starts)
    for name in (inherited.CLOSURE, "tests/__init__.py", "pyproject.toml"):
        files[name] = snapshot.digest(ROOT / name)
    manifest = snapshot.freeze(ROOT, output / "source", {name: name for name in files})
    snapshot.write_json(
        output / "inputs.json",
        dict(
            source_plan=plan,
            source_sha256={
                name: manifest["files"][name]["sha256"] for name in (SOURCE, TEST, FILE)
            },
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
            snapshot_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            git_revision=manifest["git_revision"],
            selection=select,
            cpu=6,
            threads=1,
            metadata_rss_bytes=512 * 2**20,
            metadata_address_space_bytes=2**30,
            software_bytes=2**30,
            wall_seconds=480,
            reserve_bytes=8 * 2**30,
            actual_native_source_release=False,
        ),
    )
    snapshot.assert_checkout_unchanged(output / "source")


def child(output, select):
    import pytest

    from cells.processes import betse_native_phase_dyna as stage

    previous, trace = sys.getprofile(), sys.gettrace()
    attempted, skipped = [], []
    codes = {
        stage._acquire.__code__,
        stage._ATTACH.__code__,
        *(fn.__code__ for fn in stage._NATIVE.values()),
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code.co_filename.startswith(str(stage.aliases.NATIVE) + "/")
        ):
            attempted.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native dyna/phase source forbidden")
        if previous is not None:
            previous(frame, event, arg)

    class Reports:
        def pytest_runtest_logreport(self, report):
            directory = output / "reports"
            directory.mkdir(exist_ok=True)
            name = hashlib.sha256(report.nodeid.encode()).hexdigest() + "." + report.when + ".json"
            snapshot.write_json(
                directory / name,
                dict(
                    nodeid=report.nodeid,
                    when=report.when,
                    outcome=report.outcome,
                    duration=report.duration,
                    longrepr=str(report.longrepr),
                ),
            )
            if report.skipped:
                skipped.append(report.nodeid)

    status = 2
    try:
        sys.setprofile(profile)
        args = [
            "-q",
            "-c",
            "/dev/null",
            "--noconftest",
            "-p",
            "no:cacheprovider",
            str(ROOT / TEST),
            "--basetemp",
            str(output / "pytest"),
            "--junitxml",
            str(output / "tests.xml"),
        ]
        if select:
            args += ["-k", select]
        status = pytest.main(args, plugins=[Reports()])
    finally:
        restored = sys.getprofile() is profile and sys.gettrace() is trace
        sys.setprofile(previous)
        sys.settrace(trace)
        snapshot.write_json(
            output / "native-entry-guard.json",
            dict(
                attempted=attempted,
                prior_profile_trace_restored=restored,
                skipped_prerequisites=skipped,
                actual_source_or_scientific_credit=0,
            ),
        )
        snapshot.write_json(output / "runtime.json", inherited.runtime.inventory())
    # Missing real producer prerequisites cannot turn held controls into a
    # positive full-suite result. A preparation-only selector remains explicit.
    return int(status) if not attempted and not skipped and restored else 1


def software(output, select):
    scope = dict(vars(inherited), ROOT=ROOT, FILE=FILE, TEST=TEST, SOURCE=SOURCE, MODULE=MODULE)
    return FunctionType(inherited.software.__code__, scope)(output, select)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("software", "prepare", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="")
    args = parser.parse_args()
    if args.child:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        return child(args.child, args.select)
    if args.prepare:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        prepare(args.prepare, args.select)
        return 0
    if args.software:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        try:
            return software(args.software, args.select)
        except Exception as error:
            if args.software.is_dir():
                snapshot.write_json(
                    args.software / "FAILURE.json",
                    dict(
                        status="preparation_or_verification_failed",
                        type=type(error).__name__,
                        traceback=traceback.format_exc(),
                        scientific_credit=0,
                    ),
                )
            raise
    parser.error("Choose software, prepare or child")


if __name__ == "__main__":
    raise SystemExit(main())
