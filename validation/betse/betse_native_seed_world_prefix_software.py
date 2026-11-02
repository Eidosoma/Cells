"""Prepared immutable native-blocked prefix runner; software release is held."""

import argparse
import hashlib
import json
import os
import resource
import runpy
import sys
from pathlib import Path
from types import FunctionType, SimpleNamespace

from validation.betse import betse_native_phase_assembly_software as phase

inherited, snapshot = phase.inherited, phase.snapshot
ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/betse_native_seed_world_prefix_software.py"
TEST = "tests/unit/test_betse_native_seed_world_prefix.py"
SOURCE = "src/cells/processes/betse_native_seed_world_prefix.py"
LITERAL = "src/cells/processes/betse_native_seed_world_prefix_source.py"
MODULE = "validation.betse.betse_native_seed_world_prefix_software"
# The reused runner strips CELLS_* native/scientific switches from children.
# This distinct software-only declaration survives that deliberate clearing.
SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_WORLD_PREFIX_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)
_RAW_FAILURES = ()


def select_items(items, selector):
    if not selector:
        return list(items), []
    parts = tuple(part.strip() for part in selector.split(","))
    if any(not part for part in parts):
        raise ValueError("Nonempty literal test-item-name fragments required")
    selected = [item for item in items if any(part in item.name for part in parts)]
    if not selected:
        raise ValueError("Explicit selector matches no test item names")
    return selected, [item for item in items if item not in selected]


def prepare(output, select):
    from cells.processes import betse_native_seed_world_prefix as stage

    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Fresh canonical-checkout prefix snapshot required")
    plan = stage.source_plan()
    files = runpy.run_path(str(ROOT / inherited.CLOSURE))["closure"](ROOT, list(OWNED))
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
            git_revision=manifest["git_revision"],
            snapshot_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            selection=select,
            cpu=6,
            threads=1,
            metadata_rss_bytes=512 * 2**20,
            software_bytes=2**30,
            wall_seconds=480,
            reserve_bytes=8 * 2**30,
            software_release_requested=os.environ.get(SOFTWARE_RELEASE) == "1",
            actual_source_native_reference_or_scientific_release=False,
            missing_world_ready_parameter_and_dispatch_authority=True,
        ),
    )
    snapshot.assert_checkout_unchanged(output / "source")


def _run_state():
    return SimpleNamespace(
        primary=None, primary_stage=None, secondary=(), evidence_errors=(),
        evidence_attempts=(), hook_attempts=(), hook_observations=(),
        hook_before=None, hook_after=None, hook_samples=(), cleanup_errors=(),
        cleanup_phase=None,
        guard_active_on_cleanup=False, hooks_restored=False, status=2,
        restore_setters=None, restore_getters=None,
    )


def _error_record(error, memo=None):
    if error is None:
        return None
    memo = {} if memo is None else memo
    if id(error) in memo:
        return dict(error_reference=memo[id(error)])
    if len(memo) >= 16:
        return dict(error_chain_truncated=True)
    token = len(memo)
    memo[id(error)] = token
    frames, tb = [], error.__traceback__
    while tb is not None and len(frames) < 64:
        frames.append(dict(file=tb.tb_frame.f_code.co_filename,
                           function=tb.tb_frame.f_code.co_name, line=tb.tb_lineno))
        tb = tb.tb_next
    return dict(
        error_identity=token, type=type(error).__module__ + "." + type(error).__qualname__,
        frames=frames, exception_not_formatted=True,
        cause=_error_record(error.__cause__, memo),
        context=_error_record(error.__context__, memo),
        suppress_context=error.__suppress_context__,
    )


def _restore_hooks(state, before, expected, setters, getters, *, record_active=True):
    """Restore independently; retain raw errors before any evidence writer."""
    state.hook_before = before
    state.restore_setters, state.restore_getters = setters, getters
    state.cleanup_phase = "restore"
    observed = []
    for name, getter in zip(("profile", "trace"), getters, strict=True):
        try:
            value = getter()
        except BaseException as error:
            value = error
            state.cleanup_errors = (*state.cleanup_errors, (name + "_before", error, None))
        observed.append(value)
    if record_active:
        state.guard_active_on_cleanup = (
            observed[0] is expected[0] and observed[1] is expected[1]
        )
    # No recorder, formatter, inventory or JSON call may precede the second
    # hook's independent restoration merely because the first one failed.
    for index in (1, 0):
        name = ("profile", "trace")[index]
        target, setter, getter = before[index], setters[index], getters[index]
        try:
            state.hook_attempts = (*state.hook_attempts, name + "_restore")
        except BaseException as error:
            state.cleanup_errors = (
                *state.cleanup_errors, (name + "_restore_attempt", error, target),
            )
        try:
            setter(target)
        except BaseException as error:
            state.cleanup_errors = (*state.cleanup_errors, (name + "_restore", error, target))
        needs_recovery = True
        try:
            value = getter()
            state.hook_observations = (*state.hook_observations, (name, value))
            needs_recovery = value is not target
        except BaseException as error:
            state.cleanup_errors = (*state.cleanup_errors, (name + "_read", error, target))
        if needs_recovery:
            try:
                state.hook_attempts = (*state.hook_attempts, name + "_recovery")
            except BaseException as error:
                state.cleanup_errors = (
                    *state.cleanup_errors, (name + "_recovery_attempt", error, target),
                )
            try:
                setter(target)
            except BaseException as error:
                state.cleanup_errors = (*state.cleanup_errors, (name + "_recovery", error, target))
    # Sample BOTH only after ALL setters, then repeat in reverse read order.
    state.cleanup_phase = "restore_final_sample"
    first, second = [None, None], [None, None]
    for actual, order in ((first, (0, 1)), (second, (1, 0))):
        for index in order:
            name = ("profile", "trace")[index]
            try:
                actual[index] = getters[index]()
            except BaseException as error:
                actual[index] = error
                state.cleanup_errors = (*state.cleanup_errors, (name + "_final", error, None))
    state.hook_samples = ((first[0], first[1]), (second[0], second[1]))
    state.hook_after = state.hook_samples[-1]
    state.hooks_restored = (
        first[0] is before[0] and first[1] is before[1]
        and second[0] is before[0] and second[1] is before[1]
    )
    if state.hooks_restored is not True:
        state.cleanup_errors = (
            *state.cleanup_errors, ("hook_identity_mismatch", None, (before, state.hook_after)),
        )


def _summary(state):
    return dict(
        primary=_error_record(state.primary), primary_stage=state.primary_stage,
        secondary=[dict(stage=name, error=_error_record(error))
                   for name, error, _ in state.secondary],
        cleanup_errors=[dict(stage=name, error=_error_record(error))
                        for name, error, _ in state.cleanup_errors],
        evidence_errors=[dict(stage=name, error=_error_record(error))
                         for name, error, _ in state.evidence_errors],
        evidence_attempts=state.evidence_attempts, hook_attempts=state.hook_attempts,
        final_hook_identities_restored=state.hooks_restored,
        status="failed" if state.primary is not None or state.cleanup_errors
               or state.evidence_errors or state.status != 0
               or not state.guard_active_on_cleanup or not state.hooks_restored else "completed",
        raw_errors_retained_in_memory=True, complete_raw_serialization_claimed=False,
        source_native_or_scientific_credit=0,
    )


def _write_evidence(output, state, attempts, skipped):
    def guarded_metadata():
        if state.hook_before is not None:
            _restore_hooks(
                state, state.hook_before, state.hook_before,
                state.restore_setters, state.restore_getters, record_active=False,
            )
            if state.hooks_restored is not True:
                raise RuntimeError("Metadata capture lacks the original outer hooks")

    def guard_record():
        snapshot.write_json(output / "native-entry-guard.json", dict(
            attempted=attempts, skipped_prerequisites=skipped,
            prior_profile_trace_restored=(state.guard_active_on_cleanup
                                          and state.hooks_restored),
            final_hook_identities_restored=state.hooks_restored,
            source_or_scientific_credit=0,
        ))

    def runtime_record():
        snapshot.write_json(output / "runtime.json", inherited.runtime.inventory())

    for name, writer in (("guard", guard_record), ("runtime", runtime_record)):
        state.evidence_attempts = (*state.evidence_attempts, name)
        try:
            guarded_metadata()
            writer()
        except BaseException as error:
            state.evidence_errors = (*state.evidence_errors, (name, error, output))
    # The fallback is independent, bounded and protected too. No failed
    # writer is retried or allowed to replace the original primary/cause.
    name = "child-failure.json" if (
        state.primary is not None or state.cleanup_errors or state.evidence_errors
        or state.status != 0 or not state.hooks_restored or not state.guard_active_on_cleanup
    ) else "child-cleanup.json"
    state.evidence_attempts = (*state.evidence_attempts, name)
    try:
        guarded_metadata()
        snapshot.write_json(output / name, _summary(state))
    except BaseException as error:
        state.evidence_errors = (*state.evidence_errors, (name, error, output))


def _finish(state, attempts, skipped):
    global _RAW_FAILURES
    failed = (state.primary is not None or state.cleanup_errors or state.evidence_errors
              or not state.hooks_restored or not state.guard_active_on_cleanup
              or attempts or skipped or state.status != 0)
    if failed:
        _RAW_FAILURES = (*_RAW_FAILURES, state)
    if state.primary is not None:
        try:
            state.primary.seed_world_software = state
        except BaseException as error:
            state.secondary = (*state.secondary, ("attach_failure_context", error, state.primary))
        raise state.primary
    return 1 if failed else int(state.status)


def child(output, select):
    # A source-only preparation cannot be reused as execution approval.
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs.get("software_release_requested") is not True:
        raise ValueError("Source-only preparation has no software execution release")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    if any(snapshot.digest(ROOT / name) != manifest["files"][name]["sha256"] for name in OWNED):
        raise ValueError("Actual selected immutable producer differs")
    import pytest

    from cells.processes import betse_native_seed_world_prefix as stage

    os.environ[SOFTWARE_RELEASE] = "1"
    prior, trace = sys.getprofile(), sys.gettrace()
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)
    state = _run_state()
    state.hook_before = (prior, trace)
    state.restore_setters, state.restore_getters = setters, getters
    attempts, skipped = [], []
    codes = {
        stage._acquire.__code__,
        *(fn.__code__ for fn in stage._BODIES.values()),
        stage.previous.prepare.__code__,
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code.co_filename.startswith(str(stage.aliases.NATIVE) + "/")
        ):
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Actual world/native/RNG/phase source execution is forbidden")
        if prior is not None:
            prior(frame, event, arg)

    class Reports:
        @pytest.hookimpl(tryfirst=True)
        def pytest_runtest_makereport(self, item, call):
            if call.excinfo is not None and state.primary is None:
                state.primary = call.excinfo.value
                state.primary_stage = "pytest_" + call.when

        def pytest_collection_modifyitems(self, config, items):
            try:
                selected, removed = select_items(items, select)
            except ValueError as error:
                raise pytest.UsageError(str(error)) from error
            state.evidence_attempts = (*state.evidence_attempts, "selection")
            try:
                snapshot.write_json(output / "selection.json", dict(
                    matching="literal item.name only", selector=select,
                    selected=[item.name for item in selected],
                    deselected=[item.name for item in removed],
                ))
            except BaseException as error:
                state.evidence_errors = (*state.evidence_errors, ("selection", error, items))
                if state.primary is None:
                    state.primary, state.primary_stage = error, "selection"
                raise
            items[:] = selected
            if removed:
                config.hook.pytest_deselected(items=removed)

        def pytest_runtest_logreport(self, report):
            if report.skipped:
                skipped.append(report.nodeid)
            state.evidence_attempts = (*state.evidence_attempts, ("report", report.nodeid, report.when))
            try:
                directory = output / "reports"
                directory.mkdir(exist_ok=True)
                name = hashlib.sha256(report.nodeid.encode()).hexdigest() + "." + report.when + ".json"
                snapshot.write_json(directory / name, dict(
                    nodeid=report.nodeid, when=report.when, outcome=report.outcome,
                    duration=report.duration, longrepr=str(report.longrepr),
                ))
            except BaseException as error:
                state.evidence_errors = (*state.evidence_errors, ("report", error, report))

        def pytest_exception_interact(self, node, call, report):
            from validation.betse.betse_native_single_cell_core_synthetic import save

            error = call.excinfo.value
            if state.primary is None:
                state.primary, state.primary_stage = error, "pytest_exception_interact"
            if not isinstance(error, stage.WorldPrefixRejected):
                return
            raw = error.partial if type(error.partial) is dict else {}
            state.evidence_attempts = (*state.evidence_attempts, "raw_failure")
            try:
                directory = output / "unexpected-failures"
                directory.mkdir(exist_ok=True)
                name = hashlib.sha256(node.nodeid.encode()).hexdigest()
                save(
                    directory,
                    name,
                    dict(
                        stage=error.stage,
                        source_error=error.source_error,
                        capture_error=error.capture_error,
                        cause=error.__cause__,
                        trial=error.trial,
                        parent_trial=raw.get("parent_trial"),
                        stages=raw.get("stages"),
                        work=raw.get("work"),
                        draws=raw.get("draws"),
                        last_completed=raw.get("last_completed"),
                        last_caller_fields=raw.get("last_caller_fields"),
                        complete_raw_owner_serialization_claimed=False,
                    ),
                )
            except BaseException as capture:
                state.evidence_errors = (*state.evidence_errors, ("raw_failure", capture, error))
                state.evidence_attempts = (*state.evidence_attempts, "raw_failure_fallback")
                try:
                    snapshot.write_json(output / "raw-failure-capture-error.json", dict(
                        capture=_error_record(capture), primary=_error_record(error),
                        original_failure_retained=True,
                    ))
                except BaseException as fallback:
                    state.evidence_errors = (
                        *state.evidence_errors, ("raw_failure_fallback", fallback, error),
                    )

    try:
        sys.setprofile(profile)
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
            plugins=[Reports()],
        )
    except BaseException as error:
        if state.primary is None:
            state.primary, state.primary_stage = error, "pytest_or_guard_setup"
        elif state.primary is not error:
            state.secondary = (*state.secondary, ("pytest_or_guard_setup", error, None))
    finally:
        try:
            _restore_hooks(state, (prior, trace), (profile, trace), setters, getters)
        except BaseException as error:
            # Even rejection at the cleanup helper's entry cannot skip both
            # actual restore attempts or erase a retained source primary.
            state.cleanup_errors = (*state.cleanup_errors, ("restore_entry", error, None))
            state.cleanup_phase = "emergency_restore"
            for index in (1, 0):
                name = ("profile", "trace")[index]
                try:
                    state.hook_attempts = (*state.hook_attempts, name + "_emergency_restore")
                except BaseException as cleanup:
                    state.cleanup_errors = (
                        *state.cleanup_errors, (name + "_emergency_attempt", cleanup, None),
                    )
                try:
                    setters[index]((prior, trace)[index])
                except BaseException as cleanup:
                    state.cleanup_errors = (
                        *state.cleanup_errors, (name + "_emergency_restore", cleanup, None),
                    )
            state.cleanup_phase = "emergency_final_sample"
            first, second = [None, None], [None, None]
            for actual, order in ((first, (0, 1)), (second, (1, 0))):
                for index in order:
                    name = ("profile", "trace")[index]
                    try:
                        actual[index] = getters[index]()
                    except BaseException as cleanup:
                        actual[index] = cleanup
                        state.cleanup_errors = (
                            *state.cleanup_errors, (name + "_emergency_read", cleanup, None),
                        )
            state.hook_samples = ((first[0], first[1]), (second[0], second[1]))
            state.hook_after = state.hook_samples[-1]
            state.hooks_restored = (
                first[0] is prior and first[1] is trace
                and second[0] is prior and second[1] is trace
            )
        try:
            _write_evidence(output, state, attempts, skipped)
        except BaseException as error:
            state.evidence_errors = (*state.evidence_errors, ("evidence_entry", error, output))
            try:
                snapshot.write_json(output / "child-failure.json", _summary(state))
            except BaseException as fallback:
                state.evidence_errors = (*state.evidence_errors, ("evidence_fallback", fallback, output))
        # Evidence entry rejection may disable an inherited hook after the
        # first restoration. Final identities are checked after all writers;
        # these final raw errors are not sent through another writer.
        state.cleanup_phase = "post_evidence_restore"
        for index in (0, 1):
            name, old = ("profile", "trace")[index], (prior, trace)[index]
            changed = True
            try:
                changed = getters[index]() is not old
            except BaseException as error:
                state.cleanup_errors = (
                    *state.cleanup_errors, (name + "_post_evidence_read", error, old),
                )
            if changed:
                try:
                    state.hook_attempts = (*state.hook_attempts, name + "_post_evidence_restore")
                except BaseException as error:
                    state.cleanup_errors = (
                        *state.cleanup_errors, (name + "_post_evidence_attempt", error, old),
                    )
                try:
                    setters[index](old)
                except BaseException as error:
                    state.cleanup_errors = (
                        *state.cleanup_errors, (name + "_post_evidence_restore", error, old),
                    )
        # No setter or evidence writer follows these final identity samples.
        state.cleanup_phase = "post_evidence_final_sample"
        first, second = [None, None], [None, None]
        for actual, order in ((first, (0, 1)), (second, (1, 0))):
            for index in order:
                name = ("profile", "trace")[index]
                try:
                    actual[index] = getters[index]()
                except BaseException as error:
                    actual[index] = error
                    state.cleanup_errors = (
                        *state.cleanup_errors, (name + "_post_evidence_final", error, None),
                    )
        state.hook_samples = ((first[0], first[1]), (second[0], second[1]))
        state.hook_after = state.hook_samples[-1]
        state.hooks_restored = (
            first[0] is prior and first[1] is trace
            and second[0] is prior and second[1] is trace
        )
        if state.hooks_restored is not True:
            state.cleanup_errors = (
                *state.cleanup_errors, ("final_hook_identity_mismatch", None, state.hook_after),
            )
    try:
        return _finish(state, attempts, skipped)
    except BaseException as error:
        if state.primary is not None and error is not state.primary:
            state.secondary = (*state.secondary, ("finish_entry", error, None))
            raise state.primary  # noqa: B904 - preserve the original primary/cause
        raise


def software(output, select):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("Prepared prefix software checks require explicit later release")
    scope = dict(vars(inherited), ROOT=ROOT, FILE=FILE, TEST=TEST, SOURCE=SOURCE, MODULE=MODULE)
    return FunctionType(inherited.software.__code__, scope)(output, select)


def _main_failure(output, error):
    global _RAW_FAILURES
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)
    before = (getters[0](), getters[1]())
    try:
        if output.is_dir():
            snapshot.write_json(output / "FAILURE.json", dict(
                status="preparation_or_verification_failed", primary=_error_record(error),
                source_or_scientific_credit=0,
            ))
    except BaseException as recording_error:
        _RAW_FAILURES = (*_RAW_FAILURES, ("main_failure", error, recording_error, output))
    finally:
        # A rejected fallback recorder is metadata failure, not authority to
        # leave either inherited hook disabled or to replace the primary.
        for index in (1, 0):
            try:
                setters[index](before[index])
            except BaseException as cleanup:
                _RAW_FAILURES = (
                    *_RAW_FAILURES, ("main_hook_restore", error, cleanup, index),
                )
        first, second = [None, None], [None, None]
        for actual, order in ((first, (0, 1)), (second, (1, 0))):
            for index in order:
                try:
                    actual[index] = getters[index]()
                except BaseException as cleanup:
                    actual[index] = cleanup
                    _RAW_FAILURES = (
                        *_RAW_FAILURES, ("main_hook_read", error, cleanup, index),
                    )
        if (first[0] is not before[0] or first[1] is not before[1]
                or second[0] is not before[0] or second[1] is not before[1]):
            _RAW_FAILURES = (
                *_RAW_FAILURES,
                ("main_hook_identity_mismatch", error, before,
                 ((first[0], first[1]), (second[0], second[1]))),
            )


def main():
    global _RAW_FAILURES
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="preparation,isolated")
    args = parser.parse_args()
    output = args.child if args.child is not None else (
        args.prepare if args.prepare is not None else args.software
    )
    try:
        if args.child:
            resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
            return child(args.child, args.select)
        if args.prepare:
            resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
            prepare(args.prepare, args.select)
            return 0
        if args.software:
            resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
            return software(args.software, args.select)
    except BaseException as error:
        if output is not None:
            try:
                _main_failure(output, error)
            except BaseException as recording_error:
                _RAW_FAILURES = (*_RAW_FAILURES, ("main_failure_entry", error, recording_error, output))
        raise
    parser.error("Choose prepare, software or child")


if __name__ == "__main__":
    raise SystemExit(main())
