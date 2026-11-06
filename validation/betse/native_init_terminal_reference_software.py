"""Immutable CPU5 controls for independent reference preparation; no BETSE calls."""

import argparse
import json
import os
import resource
import runpy
import sys
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_mesh_lifecycle_preparation_guard as guard
from validation.betse import betse_normal_channel_join_runtime as runtime

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
SOURCE = "validation/betse/native_init_terminal_reference.py"
TEST = "tests/unit/test_native_init_terminal_reference.py"
FILE = "validation/betse/native_init_terminal_reference_software.py"
MODULE = "validation.betse.native_init_terminal_reference_software"
OWNED = (SOURCE, TEST, FILE)
CLOSURE = "agent-work/cells-worker-01/workfiles/betse_normal_ecm_reviewed_successors_resources.py"
RELEASE = "CELLS_INIT_TERMINAL_REFERENCE_BLOCKED_SOFTWARE"
NATIVE_ROOT = "/mnt/workspaces/Cells/betse-v1.5.0"
POLICY = dict(
    cpu=5,
    threads=1,
    wall_seconds=480,
    max_rss_bytes=2**30,
    metadata_bytes=512 * 2**20,
    reserve_bytes=8 * 2**30,
)
_RAW_FAILURES = []


class NativeBlocked(RuntimeError):
    pass


def forbidden(frame):
    module = frame.f_globals.get("__name__", "")
    filename = frame.f_code.co_filename
    return (
        module == "betse"
        or module.startswith(("betse.", "numpy.linalg", "numpy.random"))
        or filename == NATIVE_ROOT
        or filename.startswith(NATIVE_ROOT + os.sep)
        or module == "validation.betse.native_init_terminal_reference"
        and frame.f_code.co_name == "_workflow"
        or module.startswith("cells.processes.")
    )


@contextmanager
def blocked(folder):
    """One ordinary empty guard receipt per control, including failed controls."""
    attempts, local = [], {}
    old_profile, old_trace = sys.getprofile(), sys.gettrace()
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)
    errors, primary = [], None

    def reject(frame, event):
        if event == "call" and forbidden(frame):
            attempts.append(
                dict(
                    module=frame.f_globals.get("__name__"),
                    name=frame.f_code.co_name,
                    file=frame.f_code.co_filename,
                )
            )
            raise NativeBlocked("Actual native/owner/RNG/operator entry is forbidden")

    def profile(frame, event, arg):
        reject(frame, event)
        if old_profile is not None:
            old_profile(frame, event, arg)

    def trace(frame, event, arg):
        reject(frame, event)
        prior = old_trace if event == "call" else local.get(id(frame))
        if prior is not None:
            child = prior(frame, event, arg)
            if child is None:
                local.pop(id(frame), None)
            else:
                local[id(frame)] = child
        if event == "return":
            local.pop(id(frame), None)
        return trace

    try:
        setters[0](profile)
        setters[1](trace)
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        for setter, previous in zip(setters, (old_profile, old_trace), strict=True):
            try:
                setter(previous)
            except BaseException as error:
                errors.append(error)
        restored = getters[0]() is old_profile and getters[1]() is old_trace
        try:
            snapshot.write_json(
                Path(folder) / "native-blocked.json",
                dict(
                    attempted=attempts,
                    prior_profile_trace_restored=restored,
                    cleanup_errors=[type(error).__qualname__ for error in errors],
                    actual_source_RNG_operator_reference_or_owner_credit=0,
                ),
            )
        except BaseException as error:
            errors.append(error)
        if errors or not restored:
            _RAW_FAILURES.append((primary, errors, attempts))
            if primary is None:
                raise NativeBlocked("Blocked-control cleanup/evidence failed")


class Reports:
    def __init__(self, folder):
        self.folder, self.rows = folder, []
        self.folder.mkdir()

    def pytest_runtest_logreport(self, report):
        row = dict(
            nodeid=report.nodeid,
            when=report.when,
            outcome=report.outcome,
            duration=report.duration,
            error=None if report.passed else str(report.longrepr),
        )
        self.rows.append(row)
        snapshot.write_json(self.folder / f"report-{len(self.rows):04d}.json", row)


def prepare(output, select):
    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Fresh canonical checkout preparation required")
    writer_sources = [
        "validation/betse/native_seed_demo.py",
        "validation/betse/native_seed_world_callback_prelude.py",
        "validation/betse/native_seed_demo_launch.py",
    ]
    files = runpy.run_path(str(ROOT / CLOSURE))["closure"](ROOT, [*OWNED, *writer_sources])
    for name in (CLOSURE, "tests/__init__.py", "pyproject.toml"):
        files[name] = snapshot.digest(ROOT / name)
    manifest = snapshot.freeze(ROOT, output / "source", {name: name for name in files})
    snapshot.assert_checkout_unchanged(output / "source")
    snapshot.write_json(
        output / "inputs.json",
        dict(
            kind="cells.original_INIT_reference_blocked_software@1",
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
            git_revision=manifest["git_revision"],
            snapshot_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            selection=select,
            policy=POLICY,
            software_release_requested=os.environ.get(RELEASE) == "1",
            native_source_reference_owner_or_scientific_release=False,
        ),
    )
    snapshot.assert_checkout_unchanged(output / "source")


def child(output, select):
    import pytest

    from validation.betse import native_init_terminal_reference as reference

    value = json.loads((output / "inputs.json").read_text())
    if value["software_release_requested"] is not True or value["policy"] != POLICY:
        raise ValueError("Explicit blocked software release required")
    manifest = snapshot.verify(ROOT, manifest_sha256=value["snapshot_sha256"])
    for name in OWNED:
        if snapshot.digest(ROOT / name) != value["owned_files"][name]:
            raise ValueError("Frozen selected source changed")
    snapshot.write_json(output / "source-plan.json", reference.source_plan())
    # Shared numeric definitions only. Actual source, RNG and operators are
    # blocked per case. The original package is never imported by this worker.
    import numpy  # noqa: F401

    from validation.betse import betse_initial_mesh_preparation_wire  # noqa: F401

    os.environ[RELEASE] = "1"
    reports = Reports(output / "reports")
    code = 1
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
                str(ROOT / TEST),
                "-k",
                select,
            ],
            plugins=[reports],
        )
    finally:
        snapshot.write_json(output / "runtime.json", runtime.inventory())
        snapshot.write_json(
            output / "loaded-selected.json",
            {name: manifest["files"][name]["sha256"] for name in OWNED},
        )
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
        [
            sys.executable,
            "-B",
            "-m",
            MODULE,
            "--prepare",
            str(output),
            "--select",
            select,
            "--software-cpu",
            str(POLICY["cpu"]),
        ],
        directory=metadata,
        cwd=ROOT,
        env=env,
        timeout=120,
        max_rss_bytes=POLICY["metadata_bytes"],
        min_available_bytes=POLICY["reserve_bytes"],
    )
    frozen = output / "source"
    value = json.loads((output / "inputs.json").read_text())
    manifest = snapshot.verify(frozen, manifest_sha256=value["snapshot_sha256"])
    snapshot.assert_checkout_unchanged(frozen)
    env["PYTHONPATH"] = os.pathsep.join([str(frozen), str(frozen / "src")])
    process = output / "process"
    process.mkdir()
    result, failures = None, []
    try:
        result = guard.run_bounded(
            [
                sys.executable,
                "-B",
                "-m",
                MODULE,
                "--child",
                str(output),
                "--select",
                select,
                "--software-cpu",
                str(POLICY["cpu"]),
            ],
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
        snapshot.verify(frozen, manifest_sha256=value["snapshot_sha256"])
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
    guard_ok = len(cases) == len(receipts) > 0 and all(
        (row := json.loads(path.read_text()))["attempted"] == []
        and row["prior_profile_trace_restored"] is True
        and row["cleanup_errors"] == []
        for path in receipts
    )
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
            snapshot_sha256=value["snapshot_sha256"],
            owned_files=value["owned_files"],
            checkout_integration_pending=integration,
            scientific_credit=0,
        ),
    )
    return int(not passed)


def main():
    global POLICY
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "child", "software"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="reference")
    parser.add_argument("--software-cpu", type=int, choices=(5, 6), default=5)
    args = parser.parse_args()
    POLICY = dict(POLICY, cpu=args.software_cpu)
    if args.child is not None:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        return child(args.child, args.select)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    if args.prepare is not None:
        prepare(args.prepare, args.select)
        return 0
    if args.software is not None:
        return software(args.software, args.select)
    parser.error("Choose immutable preparation or native-blocked software")


if __name__ == "__main__":
    raise SystemExit(main())
