"""Freeze the checkout and run guarded phase-prefix software on CPU6."""

import argparse
import hashlib
import resource
import runpy
import sys
import traceback
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_tissue_handler_attachment_software as inherited

ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/betse_native_phase_assembly_software.py"
TEST = "tests/unit/test_betse_native_phase_assembly.py"
SOURCE = "src/cells/processes/betse_native_phase_assembly.py"
LITERAL = "src/cells/processes/betse_native_phase_assembly_source.py"
MODULE = "validation.betse.betse_native_phase_assembly_software"
OWNED = (SOURCE, LITERAL, TEST, FILE)
snapshot = inherited.snapshot


def prepare(output, select):
    from cells.processes import betse_native_phase_assembly as stage

    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Prepare a new phase prefix snapshot from the checkout only")
    plan = stage.source_plan()
    files = runpy.run_path(str(ROOT / inherited.CLOSURE))["closure"](ROOT, list(OWNED))
    for name in (inherited.CLOSURE, "tests/__init__.py", "pyproject.toml"):
        files[name] = snapshot.digest(ROOT / name)
    manifest = snapshot.freeze(ROOT, output / "source", {n: n for n in files})
    snapshot.write_json(
        output / "inputs.json",
        dict(
            source_plan=plan,
            source_sha256={
                name: manifest["files"][name]["sha256"] for name in (FILE, TEST, SOURCE)
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
            actual_source_release=False,
        ),
    )
    snapshot.assert_checkout_unchanged(output / "source")


def child(output, select):
    import pytest

    from cells.processes import betse_native_phase_assembly as stage

    previous, trace = sys.getprofile(), sys.gettrace()
    attempted = []
    codes = {stage._acquire.__code__, stage._PREFIX.__code__, stage._import_native.__code__}

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code.co_filename.startswith(str(stage.aliases.NATIVE) + "/")
        ):
            attempted.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native phase/source entry forbidden")
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
                actual_source_or_scientific_credit=0,
            ),
        )
        snapshot.write_json(output / "runtime.json", inherited.runtime.inventory())
    return int(status) if not attempted and restored else 1


def software(output, select):
    scope = dict(vars(inherited), ROOT=ROOT, FILE=FILE, TEST=TEST, SOURCE=SOURCE, MODULE=MODULE)
    return FunctionType(inherited.software.__code__, scope)(output, select)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("software", "child", "prepare"):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--select", default="")
    a = p.parse_args()
    if a.child:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        return child(a.child, a.select)
    if a.prepare:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        prepare(a.prepare, a.select)
        return 0
    if a.software:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        try:
            return software(a.software, a.select)
        except Exception as error:
            if a.software.is_dir():
                snapshot.write_json(
                    a.software / "FAILURE.json",
                    dict(
                        status="preparation_or_verification_failed",
                        type=type(error).__name__,
                        message=str(error),
                        traceback=traceback.format_exc(),
                        scientific_credit=0,
                    ),
                )
            raise
    p.error("Choose software, prepare or child")


if __name__ == "__main__":
    raise SystemExit(main())
