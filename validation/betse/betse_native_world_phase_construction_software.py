"""Prepared immutable blocked-software runner; no current execution release."""

import argparse
import hashlib
import json
import os
import resource
import runpy
import sys
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_seed_world_prefix_software as reuse

inherited, snapshot = reuse.inherited, reuse.snapshot
ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_world_phase_construction.py"
TEST = "tests/unit/test_betse_native_world_phase_construction.py"
FILE = "validation/betse/betse_native_world_phase_construction_software.py"
MODULE = "validation.betse.betse_native_world_phase_construction_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_WORLD_PHASE_CONSTRUCTION_SOFTWARE_RELEASED"
OWNED = (SOURCE, TEST, FILE)
_RAW_FAILURES = ()
NATIVE_ROOT = "/mnt/workspaces/Cells/betse-v1.5.0"
FORBIDDEN_MODULES = frozenset(
    (
        "cells.processes.betse_native_phase_assembly",
        "cells.processes.betse_native_phase_caches",
        "cells.processes.betse_native_phase_dyna",
        "cells.processes.betse_native_phase_tail",
        "cells.processes.betse_native_phase_assembly_source",
        "cells.processes.betse_native_phase_dyna_source",
        "cells.processes.betse_native_phase_tail_source",
        "cells.processes.betse_native_parameter_world_construction",
        "cells.processes.betse_native_parameter_load_remainder",
        "betse.science.phase.phasecls",
        "betse.science.cells",
        "betse.science.sim",
        "betse.science.tissue.tishandler",
        "betse.science.math.cache.cacheabc",
        "betse.science.math.cache.cachevec",
        "betse.science.math.cache.cachevecfld",
    )
)


def is_forbidden_frame(frame):
    if frame.f_globals.get("__name__") in FORBIDDEN_MODULES:
        return True
    filename = frame.f_code.co_filename
    if not os.path.isabs(filename):
        return False
    path = os.path.normpath(filename)
    return path == NATIVE_ROOT or path.startswith(NATIVE_ROOT + os.sep)


class Reports:
    """Actual runner callbacks, also reachable by isolated metadata controls."""

    def __init__(self, output, state, select, skipped):
        self.output, self.state, self.select, self.skipped = output, state, select, skipped

    def pytest_runtest_makereport(self, item, call):
        if call.excinfo is not None and self.state.primary is None:
            self.state.primary, self.state.primary_stage = call.excinfo.value, "pytest_" + call.when

    def pytest_collection_modifyitems(self, config, items):
        selected, removed = reuse.select_items(items, self.select)
        snapshot.write_json(
            self.output / "selection.json",
            dict(
                matching="literal item.name only",
                selector=self.select,
                selected=[item.name for item in selected],
                deselected=[item.name for item in removed],
            ),
        )
        items[:] = selected
        if removed:
            config.hook.pytest_deselected(items=removed)

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.skipped.append(report.nodeid)
        try:
            directory = self.output / "reports"
            directory.mkdir(exist_ok=True)
            name = hashlib.sha256(report.nodeid.encode()).hexdigest() + "." + report.when
            snapshot.write_json(
                directory / (name + ".json"),
                dict(
                    nodeid=report.nodeid,
                    when=report.when,
                    outcome=report.outcome,
                    duration=report.duration,
                    longrepr=str(report.longrepr),
                ),
            )
        except BaseException as error:
            self.state.evidence_errors = (
                *self.state.evidence_errors,
                ("case_report", error, report),
            )


def prepare(output, select):
    from cells.processes import betse_native_world_phase_construction as stage

    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Fresh canonical-checkout preparation required")
    # Dynamic stage/Key imports are enumerated; source preparation grants no
    # authority to those unreviewed/unbound implementations.
    explicit = [
        "src/" + name.replace(".", "/") + ".py"
        for name in (*stage.STAGE_MODULES, stage.KEY_MODULE, stage.PARAMETER_MODULE)
    ]
    files = runpy.run_path(str(ROOT / inherited.CLOSURE))["closure"](ROOT, [*OWNED, *explicit])
    for name in (inherited.CLOSURE, "tests/__init__.py", "pyproject.toml"):
        files[name] = snapshot.digest(ROOT / name)
    manifest = snapshot.freeze(ROOT, output / "source", {name: name for name in files})
    snapshot.assert_checkout_unchanged(output / "source")
    snapshot.write_json(
        output / "inputs.json",
        dict(
            source_plan=stage.source_plan(),
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
            git_revision=manifest["git_revision"],
            snapshot_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            selection=select,
            cpu=6,
            threads=1,
            metadata_bytes=512 * 2**20,
            software_bytes=2**30,
            wall_seconds=480,
            reserve_bytes=8 * 2**30,
            software_release_requested=os.environ.get(SOFTWARE_RELEASE) == "1",
            actual_source_native_reference_or_scientific_release=False,
            dynamic_source_inclusion_is_not_producer_adoption=True,
            native_guard_policy=dict(root=NATIVE_ROOT, modules=sorted(FORBIDDEN_MODULES)),
        ),
    )
    snapshot.assert_checkout_unchanged(output / "source")


def child(output, select):
    global _RAW_FAILURES
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs.get("software_release_requested") is not True:
        raise ValueError("Source-only preparation has no software release")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    if any(snapshot.digest(ROOT / name) != manifest["files"][name]["sha256"] for name in OWNED):
        raise ValueError("Actual immutable selected producer changed")
    import pytest

    os.environ[SOFTWARE_RELEASE] = "1"
    state = reuse._run_state()
    attempts, skipped = [], []
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)
    prior = (getters[0](), getters[1]())
    state.hook_before = prior
    state.restore_setters, state.restore_getters = setters, getters

    def profile(frame, event, arg):
        if event == "call" and is_forbidden_frame(frame):
            attempts.append((frame.f_code.co_filename, frame.f_code.co_qualname))
            raise AssertionError("Actual phase/parameter/native source work is forbidden")
        if prior[0] is not None:
            prior[0](frame, event, arg)

    pytest.hookimpl(tryfirst=True)(Reports.pytest_runtest_makereport)

    try:
        setters[0](profile)
        state.status = pytest.main(
            [
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
            ],
            plugins=[Reports(output, state, select, skipped)],
        )
    except BaseException as error:
        if state.primary is None:
            state.primary, state.primary_stage = error, "software_or_guard_setup"
        elif state.primary is not error:
            state.secondary = (*state.secondary, ("software_or_guard_setup", error, None))
    finally:
        # Reuse accepted independently protected cleanup and metadata capture.
        # Helper-entry rejection still gets BOTH actual setter attempts below.
        try:
            reuse._restore_hooks(state, prior, (profile, prior[1]), setters, getters)
        except BaseException as error:
            state.cleanup_errors = (*state.cleanup_errors, ("restore_entry", error, None))
            for index in (1, 0):
                try:
                    setters[index](prior[index])
                except BaseException as cleanup:
                    state.cleanup_errors = (
                        *state.cleanup_errors,
                        ("emergency_restore", cleanup, index),
                    )
        try:
            reuse._write_evidence(output, state, attempts, skipped)
        except BaseException as error:
            state.evidence_errors = (*state.evidence_errors, ("evidence_entry", error, output))
            try:
                snapshot.write_json(output / "child-failure.json", reuse._summary(state))
            except BaseException as capture:
                state.evidence_errors = (*state.evidence_errors, ("failure_write", capture, output))
        # No recorder follows this last restoration/identity boundary.
        try:
            reuse._restore_hooks(state, prior, prior, setters, getters, record_active=False)
        except BaseException as error:
            state.cleanup_errors = (*state.cleanup_errors, ("final_restore_entry", error, None))
            for index in (1, 0):
                try:
                    setters[index](prior[index])
                except BaseException as cleanup:
                    state.cleanup_errors = (
                        *state.cleanup_errors,
                        ("final_emergency_restore", cleanup, index),
                    )
        first, second = [None, None], [None, None]
        for actual, order in ((first, (0, 1)), (second, (1, 0))):
            for index in order:
                try:
                    actual[index] = getters[index]()
                except BaseException as error:
                    actual[index] = error
                    state.cleanup_errors = (
                        *state.cleanup_errors,
                        ("final_hook_read", error, index),
                    )
        state.hook_samples = ((first[0], first[1]), (second[0], second[1]))
        state.hook_after = state.hook_samples[-1]
        state.hooks_restored = (
            first[0] is prior[0]
            and first[1] is prior[1]
            and second[0] is prior[0]
            and second[1] is prior[1]
        )
        if state.hooks_restored is not True:
            state.cleanup_errors = (
                *state.cleanup_errors,
                ("final_hook_identity_mismatch", None, state.hook_samples),
            )
        _RAW_FAILURES = (
            (*_RAW_FAILURES, state)
            if (state.primary is not None or state.cleanup_errors or state.evidence_errors)
            else _RAW_FAILURES
        )
    try:
        return reuse._finish(state, attempts, skipped)
    except BaseException as error:
        if state.primary is not None and error is not state.primary:
            state.secondary = (*state.secondary, ("finish_entry", error, None))
            raise state.primary  # noqa: B904 - retain original identity and cause
        raise


def software(output, select):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("Prepared blocked controls require explicit later Root release")
    scope = dict(vars(inherited), ROOT=ROOT, FILE=FILE, TEST=TEST, SOURCE=SOURCE, MODULE=MODULE)
    return FunctionType(inherited.software.__code__, scope)(output, select)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument(
        "--select",
        default=(
            "preparation,ordering,failure,step,helper,atom_delegate,validation,reserved,"
            "exact_guard,fixture,residual"
        ),
    )
    args = parser.parse_args()
    output = (
        args.child
        if args.child is not None
        else (args.prepare if args.prepare is not None else args.software)
    )
    try:
        if args.child:
            resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
            return child(args.child, args.select)
        if args.prepare:
            resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
            prepare(args.prepare, args.select)
            return 0
        if args.software:
            resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
            return software(args.software, args.select)
    except BaseException as error:
        if output is not None:
            try:
                reuse._main_failure(output, error)
            except BaseException as capture:
                global _RAW_FAILURES
                _RAW_FAILURES = (*_RAW_FAILURES, ("main_failure_entry", error, capture, output))
        raise
    parser.error("Choose prepare, software or child")


if __name__ == "__main__":
    raise SystemExit(main())
