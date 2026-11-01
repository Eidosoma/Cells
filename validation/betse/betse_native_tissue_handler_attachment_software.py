"""Immutable CPU6 selected-handler software, with all native entry held."""

import argparse
import hashlib
import json
import os
import resource
import runpy
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_mesh_lifecycle_preparation_guard as guard
from validation.betse import betse_normal_channel_join_runtime as runtime

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
FILE = "validation/betse/betse_native_tissue_handler_attachment_software.py"
TEST = "tests/unit/test_betse_native_tissue_handler_attachment.py"
SOURCE = "src/cells/processes/betse_native_tissue_handler_attachment.py"
CLOSURE = "agent-work/cells-worker-01/workfiles/betse_normal_ecm_reviewed_successors_resources.py"
MODULE = "validation.betse.betse_native_tissue_handler_attachment_software"


def child(output, select):
    import pytest

    from cells.processes import betse_native_tissue_handler_attachment as stage

    original_profile, original_trace = sys.getprofile(), sys.gettrace()
    attempted = []
    native_codes = {stage._acquire.__code__, *{fn.__code__ for fn in stage._NATIVE.values()}}

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in native_codes
            or frame.f_code.co_filename.startswith(str(stage.aliases.NATIVE) + "/")
        ):
            attempted.append(frame.f_code.co_qualname)
            raise AssertionError("Actual handler native body/factory/import work forbidden")
        if original_profile is not None:
            original_profile(frame, event, arg)

    status = 2

    class Reports:
        def pytest_runtest_logreport(self, report):
            records = output / "reports"
            records.mkdir(exist_ok=True)
            name = hashlib.sha256(report.nodeid.encode()).hexdigest() + "." + report.when + ".json"
            snapshot.write_json(
                records / name,
                dict(
                    nodeid=report.nodeid,
                    when=report.when,
                    outcome=report.outcome,
                    duration=report.duration,
                    longrepr=str(report.longrepr),
                ),
            )

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
            args.extend(["-k", select])
        status = pytest.main(args, plugins=[Reports()])
    finally:
        restored = sys.getprofile() is profile and sys.gettrace() is original_trace
        sys.setprofile(original_profile)
        sys.settrace(original_trace)
        snapshot.write_json(
            output / "native-entry-guard.json",
            dict(
                attempted=attempted,
                prior_profile_trace_restored=restored,
                actual_source_or_scientific_credit=0,
            ),
        )
        snapshot.write_json(output / "runtime.json", runtime.inventory())
    return int(status) if not attempted and restored else 1


def prepare(output, select):
    from cells.processes import betse_native_tissue_handler_attachment as stage

    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Prepare a new snapshot from checkout only")
    plan = stage.source_plan()
    files = runpy.run_path(str(ROOT / CLOSURE))["closure"](ROOT, [FILE, TEST, SOURCE])
    for name in (CLOSURE, "tests/__init__.py", "pyproject.toml"):
        files[name] = snapshot.digest(ROOT / name)
    frozen = output / "source"
    manifest = snapshot.freeze(ROOT, frozen, {n: n for n in files})
    digest = snapshot.digest(frozen / "SNAPSHOT.json")
    snapshot.write_json(
        output / "inputs.json",
        dict(
            source_plan=plan,
            source_sha256={n: manifest["files"][n]["sha256"] for n in (FILE, TEST, SOURCE)},
            git_revision=manifest["git_revision"],
            snapshot_sha256=digest,
            cpu=6,
            threads=1,
            metadata_rss_bytes=512 * 2**20,
            metadata_address_space_bytes=2**30,
            software_bytes=2**30,
            wall_seconds=480,
            reserve_bytes=8 * 2**30,
            selection=select,
            actual_source_release=False,
        ),
    )
    snapshot.assert_checkout_unchanged(frozen)


def software(output, select):
    output = Path(output).absolute()
    if (
        not output.is_relative_to(BASE)
        or output.exists()
        or any(p.is_symlink() for p in (output, *output.parents))
        or os.sched_getaffinity(0) != {6}
    ):
        raise ValueError("Fresh real CPU6 output required")
    output.mkdir(parents=True)
    metadata = output / "metadata"
    metadata.mkdir()
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("CELLS_", "PYTEST_"))}
    command = [sys.executable, "-B", "-m", MODULE, "--prepare", str(output)]
    if select:
        command.extend(["--select", select])
    guard.run_bounded(
        command,
        directory=metadata,
        cwd=ROOT,
        env=environment,
        timeout=120,
        max_rss_bytes=512 * 2**20,
        min_available_bytes=8 * 2**30,
        process_tree_memory_metric="rss",
    )
    frozen = output / "source"
    digest = json.loads((output / "inputs.json").read_text())["snapshot_sha256"]
    manifest = snapshot.verify(frozen, manifest_sha256=digest)
    snapshot.assert_checkout_unchanged(frozen)
    (output / "process").mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CELLS_", "PYTEST_"))}
    env.update(
        PYTHONPATH=os.pathsep.join(
            [
                str(frozen),
                str(frozen / "src"),
                *[
                    p
                    for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                    if p and not Path(p).resolve().is_relative_to(ROOT)
                ],
            ]
        ),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
    )
    result = None
    try:
        command = [sys.executable, "-B", "-m", MODULE, "--child", str(output)]
        if select:
            command.extend(["--select", select])
        result = guard.run_bounded(
            command,
            directory=output / "process",
            cwd=frozen,
            env=env,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
    except Exception as error:
        result = (
            json.loads((output / "process/failure.json").read_text())
            if (output / "process/failure.json").exists()
            else dict(status="failed", error=str(error))
        )
    verification_errors = []
    try:
        snapshot.verify(frozen, manifest_sha256=digest)
        loaded = json.loads((output / "runtime.json").read_text())["loaded_files"]
        producers = {}
        for row in loaded.values():
            path = Path(row["path"])
            if path.is_relative_to(ROOT):
                raise ValueError(
                    "Frozen execution loaded a mutable checkout producer: " + str(path)
                )
            if path.is_relative_to(frozen):
                name = str(path.relative_to(frozen))
                if (
                    name not in manifest["files"]
                    or row.get("sha256") != manifest["files"][name]["sha256"]
                ):
                    raise ValueError("Loaded producer differs from immutable snapshot: " + name)
                producers[name] = row["sha256"]
        if not all(name in producers for name in (SOURCE, TEST, FILE)):
            raise ValueError("Missing selected loaded producer")
        snapshot.write_json(output / "producer-bindings.json", producers)
    except Exception as error:
        verification_errors.append(dict(type=type(error).__name__, message=str(error)))
    integration = None
    try:
        snapshot.assert_checkout_unchanged(frozen)
    except Exception as error:
        integration = dict(type=type(error).__name__, message=str(error))
    receipts = sorted((output / "pytest").rglob("native-blocked.json"))
    cases = (
        list(ET.parse(output / "tests.xml").iter("testcase"))
        if (output / "tests.xml").exists()
        else []
    )
    native_guard = (
        json.loads((output / "native-entry-guard.json").read_text())
        if (output / "native-entry-guard.json").exists()
        else {}
    )
    complete_guards = (
        bool(cases)
        and len(cases) == len(receipts)
        and all(json.loads(path.read_text())["attempted"] == [] for path in receipts)
    )
    guard_ok = (
        complete_guards
        and native_guard.get("attempted") == []
        and native_guard.get("prior_profile_trace_restored") is True
    )
    status = int(result.get("returncode", 1))
    if verification_errors or not guard_ok:
        status = 1
    snapshot.write_json(
        output / "result.json",
        dict(
            status="passed" if status == 0 else "failed",
            process=result,
            verification_errors=verification_errors,
            snapshot_sha256=digest,
            selected_cases=len(cases),
            guard_receipts=len(receipts),
            complete_guards=guard_ok,
            actual_native_entries=0 if guard_ok else None,
            integration_pending=integration is not None,
            checkout_drift=integration,
            scientific_credit=0,
        ),
    )
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--software", type=Path)
    parser.add_argument("--child", type=Path)
    parser.add_argument("--prepare", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--select", default="")
    args = parser.parse_args()
    if args.child:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        return child(args.child, args.select)
    if args.prepare:
        # Address-space mapping is larger than resident metadata memory after
        # importing the read-only array stack. The parent enforces 512MiB RSS.
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
                        message=str(error),
                        traceback=traceback.format_exc(),
                        scientific_credit=0,
                    ),
                )
            raise
    parser.error("Choose software or child")


if __name__ == "__main__":
    raise SystemExit(main())
