"""Prepared immutable SEED-tail software runner; actual source work stays blocked."""

import argparse
import hashlib
import resource
import runpy
import sys
import time
import traceback
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace

from validation.betse import betse_native_phase_assembly_software as phase
from validation.betse import betse_native_phase_caches_software as batch

inherited, snapshot = phase.inherited, phase.snapshot
ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/betse_native_phase_tail_software.py"
TEST = "tests/unit/test_betse_native_phase_tail.py"
SOURCE = "src/cells/processes/betse_native_phase_tail.py"
LITERAL = "src/cells/processes/betse_native_phase_tail_source.py"
MODULE = "validation.betse.betse_native_phase_tail_software"
HOOKS = (
    "src/cells/processes/betse_native_phase_assembly.py",
    "src/cells/processes/betse_native_phase_caches.py",
    "src/cells/processes/betse_native_phase_dyna.py",
)
OWNED = (SOURCE, LITERAL, TEST, FILE, *HOOKS)
_RAW_FAILURES = ()


def native_profile(codes, owner, attempted, previous, reason):
    """Same blockade/delegation, with one root conversion per guard lifetime."""
    aliases = owner.aliases
    native_root = aliases.NATIVE
    prefix = str(native_root) + "/"

    def profile(frame, event, arg):
        if owner.aliases is not aliases or aliases.NATIVE is not native_root:
            attempted.append("native_root_identity_changed")
            raise AssertionError("Native guard root changed during its lifetime")
        if event == "call":
            code = frame.f_code
            if code in codes or code.co_filename.startswith(prefix):
                attempted.append(code.co_qualname)
                raise AssertionError(reason)
        if previous is not None:
            previous(frame, event, arg)

    return profile


def adapt_upstream_guard(original, source):
    """Adapt only the exact installed dyna fixture guard, not an arbitrary hook."""
    if type(original) is not FunctionType or type(source) is not FunctionType:
        raise TypeError("Actual original fixture/profile functions required")
    expected = tuple(
        value
        for value in source.__code__.co_consts
        if type(value) is CodeType and value.co_name == "profile"
    )
    if (
        len(expected) != 1
        or original.__code__ is not expected[0]
        or original.__globals__ is not source.__globals__
    ):
        raise ValueError("Original upstream guard code/globals changed")
    original_code, source_code = original.__code__, source.__code__
    namespace, closure = original.__globals__, original.__closure__
    cells = dict(zip(original_code.co_freevars, closure or (), strict=True))
    if set(cells) != {"attempts", "codes", "previous"}:
        raise ValueError("Exact original guard closure roster required")
    codes_cell, attempts_cell, previous_cell = (
        cells[name] for name in ("codes", "attempts", "previous")
    )
    codes, attempted, previous = (
        cell.cell_contents for cell in (codes_cell, attempts_cell, previous_cell)
    )
    roster, owner = frozenset(codes), namespace["stage"]
    delegate = native_profile(
        codes,
        owner,
        attempted,
        previous,
        "Actual source/native dyna/phase work forbidden",
    )

    def profile(frame, event, arg):
        if (
            original.__code__ is not original_code
            or source.__code__ is not source_code
            or original.__globals__ is not namespace
            or source.__globals__ is not namespace
            or original.__closure__ is not closure
            or namespace.get("stage") is not owner
            or codes_cell.cell_contents is not codes
            or attempts_cell.cell_contents is not attempted
            or previous_cell.cell_contents is not previous
            or codes != roster
        ):
            attempted.append("upstream_guard_authority_changed")
            raise AssertionError("Original upstream guard authority changed during use")
        return delegate(frame, event, arg)

    return profile


def boundary(output, name, started):
    try:
        snapshot.write_json(
            output / ("boundary-" + name + ".json"),
            dict(
                stage=name,
                elapsed_seconds=time.monotonic() - started,
                wall_limit_seconds=480,
                source_or_scientific_credit=0,
            ),
        )
    except BaseException as error:
        return error
    return None


def stamp(output, name, started, errors):
    # boundary's own try cannot protect rejection BEFORE its body starts.
    try:
        error = boundary(output, name, started)
    except BaseException as rejected:
        error = rejected
    if error is not None:
        errors.append((name, error))


# One issued-chain control per guarded worker; the pilot took 264 seconds.
# Reuse the reviewed cache controller, atomic progress and exclusive terminals.
GROUPS = {
    "g000": (
        "test_source_failure_retains_ordered_partial_stores_and_identical_primary_chain[after_sim-1]",
    ),
    "g001": (
        "test_source_failure_retains_ordered_partial_stores_and_identical_primary_chain[after_parameter-2]",
    ),
    "g002": (
        "test_source_failure_retains_ordered_partial_stores_and_identical_primary_chain[time-2]",
    ),
    "g003": (
        "test_source_failure_retains_ordered_partial_stores_and_identical_primary_chain[export-2]",
    ),
    "g004": ("test_early_refusal_preserves_parent_and_does_not_fabricate_baseline",),
    "g005": ("test_trial_capture_failure_keeps_actual_three_stores_but_never_issues_child",),
    "g006": (
        "test_helper_return_capture_preserves_completed_raw_fields_or_original_unwind[False]",
    ),
    "g007": ("test_helper_return_capture_preserves_completed_raw_fields_or_original_unwind[True]",),
    "g008": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[event-False-same]",
    ),
    "g009": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[event-False-next]",
    ),
    "g010": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[event-True-same]",
    ),
    "g011": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[event-True-next]",
    ),
    "g012": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[profile-False-same]",
    ),
    "g013": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[profile-False-next]",
    ),
    "g014": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[profile-True-same]",
    ),
    "g015": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[profile-True-next]",
    ),
    "g016": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[trace-False-same]",
    ),
    "g017": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[trace-False-next]",
    ),
    "g018": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[trace-True-same]",
    ),
    "g019": (
        "test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught[trace-True-next]",
    ),
    "g020": ("test_trace_observer_raw_callable_reentry_never_reaches_another_delegate[complete]",),
    "g021": ("test_trace_observer_raw_callable_reentry_never_reaches_another_delegate[helper]",),
    "g022": ("test_real_issued_cache_tuples_survive_tail_without_reconstruction",),
    "g023": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[preflight-remove]",
    ),
    "g024": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[preflight-equal_tuple]",
    ),
    "g025": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[preflight-direct_context]",
    ),
    "g026": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[preflight-wrong_context]",
    ),
    "g027": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[preflight-wrong_role]",
    ),
    "g028": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[before_helper-remove]",
    ),
    "g029": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[before_helper-equal_tuple]",
    ),
    "g030": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[before_helper-direct_context]",
    ),
    "g031": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[before_helper-wrong_context]",
    ),
    "g032": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[before_helper-wrong_role]",
    ),
    "g033": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[completed_child-remove]",
    ),
    "g034": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[completed_child-equal_tuple]",
    ),
    "g035": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[completed_child-direct_context]",
    ),
    "g036": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[completed_child-wrong_context]",
    ),
    "g037": (
        "test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate[completed_child-wrong_role]",
    ),
    "g038": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[remove-dyna_issuer]",
    ),
    "g039": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[remove-dyna_retirement]",
    ),
    "g040": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[remove-cache_issuer]",
    ),
    "g041": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[remove-cache_retirement]",
    ),
    "g042": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[remove-assembly_issuer]",
    ),
    "g043": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[remove-assembly_retirement]",
    ),
    "g044": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[remove-callback_issuer]",
    ),
    "g045": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[replace-dyna_issuer]",
    ),
    "g046": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[replace-dyna_retirement]",
    ),
    "g047": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[replace-cache_issuer]",
    ),
    "g048": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[replace-cache_retirement]",
    ),
    "g049": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[replace-assembly_issuer]",
    ),
    "g050": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[replace-assembly_retirement]",
    ),
    "g051": (
        "test_completed_child_requires_actual_inherited_issuance_and_retirement_links[replace-callback_issuer]",
    ),
    "g052": ("test_original_wrapper_and_delegate_links_stay_live_after_tail[code]",),
    "g053": ("test_original_wrapper_and_delegate_links_stay_live_after_tail[delegate]",),
    "g054": (
        "test_raw_phase_methods_after_success_never_enter_another_body_or_observer[_init_kludge]",
    ),
    "g055": (
        "test_raw_phase_methods_after_success_never_enter_another_body_or_observer[_init_kludge_time]",
    ),
    "g056": (
        "test_raw_phase_methods_after_success_never_enter_another_body_or_observer[die_unless_kind_seed]",
    ),
    "g057": (
        "test_raw_phase_methods_after_success_never_enter_another_body_or_observer[die_unless_kind_init_or_sim]",
    ),
    "g058": ("test_issued_seed_owner_cannot_be_relabelled_before_tail[INIT]",),
    "g059": ("test_issued_seed_owner_cannot_be_relabelled_before_tail[SIM]",),
    "g060": ("test_postmutation_use_calls_only_successor_validator_not_stale_parameter_epochs",),
    "g061": ("test_completed_tail_does_not_grant_full_phase_or_world_authority",),
    "g062": ("test_inherited_dyna_entry_guards_on_actual_cache_chain[event-__init__-same-False]",),
    "g063": ("test_inherited_dyna_entry_guards_on_actual_cache_chain[event-__init__-next-False]",),
    "g064": (
        "test_inherited_dyna_entry_guards_on_actual_cache_chain[event-_init_events-same-False]",
    ),
    "g065": (
        "test_inherited_dyna_entry_guards_on_actual_cache_chain[event-_init_events-next-False]",
    ),
    "g066": (
        "test_inherited_dyna_entry_guards_on_actual_cache_chain[profile-__init__-same-False]",
    ),
    "g067": (
        "test_inherited_dyna_entry_guards_on_actual_cache_chain[profile-__init__-next-False]",
    ),
    "g068": (
        "test_inherited_dyna_entry_guards_on_actual_cache_chain[profile-_init_events-same-False]",
    ),
    "g069": (
        "test_inherited_dyna_entry_guards_on_actual_cache_chain[profile-_init_events-next-False]",
    ),
    "g070": ("test_inherited_dyna_entry_guards_on_actual_cache_chain[event-__init__-next-True]",),
    "g071": ("test_inherited_dyna_entry_guards_on_actual_cache_chain[profile-__init__-next-True]",),
    "g072": ("test_inherited_dyna_simultaneous_entry_and_capture_keep_primary",),
}


def select_items(items, selector):
    """Match item names only; ancestor/output paths never grant selection."""
    if selector in GROUPS:
        expected = GROUPS[selector]
        selected = [item for item in items if item.name in expected]
        if len(selected) != len(expected) or {item.name for item in selected} != set(expected):
            raise ValueError("Explicit group roster differs from collected item names")
        return selected, [item for item in items if item not in selected]
    if not selector:
        return list(items), []
    fragments = tuple(part.strip() for part in selector.split(","))
    if any(not part for part in fragments):
        raise ValueError("Nonempty comma-separated test-name fragments required")
    selected, deselected = [], []
    for item in items:
        (selected if any(part in item.name for part in fragments) else deselected).append(item)
    if not selected:
        raise ValueError("No test item names match the explicit selection")
    return selected, deselected


def prepare(output, select):
    from cells.processes import betse_native_phase_tail as stage

    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("Fresh canonical-checkout tail snapshot required")
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
    global _RAW_FAILURES
    import pytest

    from cells.processes import betse_native_phase_tail as stage

    previous, trace = sys.getprofile(), sys.gettrace()
    attempted, skipped = [], []
    codes = {
        stage._acquire.__code__,
        stage._TAIL.__code__,
        *(fn.__code__ for fn in stage._METHODS.values()),
    }

    profile = native_profile(
        codes, stage, attempted, previous, "Actual native tail/phase source forbidden"
    )
    started = time.monotonic()
    state = SimpleNamespace(
        primary=None,
        timing_errors=[],
        cleanup_errors=[],
        restored=False,
        final_hooks_restored=False,
        hook_samples=(),
    )

    class Reports:
        def pytest_runtest_makereport(self, item, call):
            if call.excinfo is not None and state.primary is None:
                state.primary = call.excinfo.value

        def pytest_collection_modifyitems(self, config, items):
            try:
                declared = [name for names in GROUPS.values() for name in names]
                if len(declared) != len(set(declared)) or not set(declared).issubset(
                    {item.name for item in items}
                ):
                    raise ValueError("Exact disjoint owner roster differs from collection")
                selected, deselected = select_items(items, select)
            except ValueError as error:
                raise pytest.UsageError(str(error)) from error
            snapshot.write_json(
                output / "selection.json",
                dict(
                    selector=select,
                    matching="literal item.name fragments only",
                    selected=[item.name for item in selected],
                    deselected=[item.name for item in deselected],
                ),
            )
            items[:] = selected
            if deselected:
                config.hook.pytest_deselected(items=deselected)

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
    pytest.hookimpl(tryfirst=True)(Reports.pytest_runtest_makereport)
    try:
        try:
            stamp(output, "pytest-start", started, state.timing_errors)
        except BaseException as error:
            state.timing_errors.append(("pytest-start_entry", error))
        if state.timing_errors:
            raise state.timing_errors[0][1]
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
        status = pytest.main(args, plugins=[Reports()])
    except BaseException as error:
        if state.primary is None:
            state.primary = error
        elif state.primary is not error:
            state.cleanup_errors.append(("pytest_return", error))
    finally:
        try:
            state.restored = sys.getprofile() is profile and sys.gettrace() is trace
        except BaseException as error:
            state.cleanup_errors.append(("active_hooks", error))
        for setter, target, name in (
            (sys.setprofile, previous, "profile"),
            (sys.settrace, trace, "trace"),
        ):
            try:
                setter(target)
            except BaseException as error:
                state.cleanup_errors.append((name + "_restore", error))
        try:
            stamp(output, "pytest-finished", started, state.timing_errors)
        except BaseException as error:
            state.timing_errors.append(("pytest-finished_entry", error))
        try:
            snapshot.write_json(
                output / "native-entry-guard.json",
                dict(
                    attempted=attempted,
                    prior_profile_trace_restored=state.restored,
                    skipped_prerequisites=skipped,
                    actual_source_or_scientific_credit=0,
                ),
            )
        except BaseException as error:
            state.cleanup_errors.append(("guard_receipt", error))
        try:
            stamp(output, "runtime-start", started, state.timing_errors)
        except BaseException as error:
            state.timing_errors.append(("runtime-start_entry", error))
        try:
            inventory = inherited.runtime.inventory()
        except BaseException as error:
            state.cleanup_errors.append(("runtime_inventory", error))
        else:
            try:
                stamp(output, "runtime-returned", started, state.timing_errors)
            except BaseException as error:
                state.timing_errors.append(("runtime-returned_entry", error))
            try:
                snapshot.write_json(output / "runtime.json", inventory)
            except BaseException as error:
                state.cleanup_errors.append(("runtime_write", error))
            else:
                try:
                    stamp(output, "runtime-written", started, state.timing_errors)
                except BaseException as error:
                    state.timing_errors.append(("runtime-written_entry", error))
    # Missing real producer prerequisites cannot turn held controls into a
    # positive full-suite result. A preparation-only selector remains explicit.
    if state.primary is not None or state.timing_errors or state.cleanup_errors:
        try:
            snapshot.write_json(
                output / "timing-errors.json",
                dict(
                    status="software_or_metadata_failed",
                    primary_type=(
                        type(state.primary).__name__ if state.primary is not None else None
                    ),
                    errors=[
                        dict(stage=name, type=type(error).__name__)
                        for name, error in (*state.timing_errors, *state.cleanup_errors)
                    ],
                    final_hook_restoration_pending=True,
                    raw_errors_retained_in_memory=True,
                    complete_raw_serialization_claimed=False,
                    scientific_credit=0,
                ),
            )
        except BaseException as error:
            state.cleanup_errors.append(("timing_errors_receipt", error))
    # An inherited observer may disable itself while rejecting ANY recorder.
    # Independently restore both exact originals after ALL evidence writes.
    for setter, target, name in (
        (sys.setprofile, previous, "profile"),
        (sys.settrace, trace, "trace"),
    ):
        try:
            setter(target)
        except BaseException as error:
            state.cleanup_errors.append((name + "_final_restore", error))
    try:
        first = (sys.getprofile(), sys.gettrace())
        second_trace, second_profile = sys.gettrace(), sys.getprofile()
        state.hook_samples = (first, (second_profile, second_trace))
        state.final_hooks_restored = all(
            a is previous and b is trace for a, b in state.hook_samples
        )
    except BaseException as error:
        state.cleanup_errors.append(("final_hook_sample", error))
    if (
        state.primary is not None
        or state.timing_errors
        or state.cleanup_errors
        or not state.final_hooks_restored
    ):
        _RAW_FAILURES = (*_RAW_FAILURES, state)
    if state.primary is not None:
        try:
            state.primary.tail_software = state
        except BaseException as error:
            state.cleanup_errors.append(("primary_context", error))
        raise state.primary
    return (
        int(status)
        if not attempted
        and not skipped
        and state.restored
        and state.final_hooks_restored
        and not state.timing_errors
        and not state.cleanup_errors
        else 1
    )


def software(output, select):
    scope = dict(vars(inherited), ROOT=ROOT, FILE=FILE, TEST=TEST, SOURCE=SOURCE, MODULE=MODULE)
    return FunctionType(inherited.software.__code__, scope)(output, select)


def _batch_scope():
    return dict(
        vars(batch),
        __file__=__file__,
        ROOT=ROOT,
        FILE=FILE,
        TEST=TEST,
        SOURCE=SOURCE,
        MODULE=MODULE,
        OWNED=OWNED,
        GROUPS=GROUPS,
    )


def launch_batch(output):
    return FunctionType(batch.launch_batch.__code__, _batch_scope())(output, None)


def batch_child(output, inputs_sha):
    return FunctionType(batch.batch_child.__code__, _batch_scope())(output, inputs_sha)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("software", "prepare", "child", "launch-batch", "batch-child"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="")
    parser.add_argument("--batch-inputs-sha256", default="")
    args = parser.parse_args()
    if args.batch_child:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        return batch_child(args.batch_child, args.batch_inputs_sha256)
    if args.launch_batch:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        try:
            return launch_batch(args.launch_batch)
        except BaseException as error:
            if args.launch_batch.is_dir():
                snapshot.write_json(
                    args.launch_batch / "LAUNCH-FAILURE.json",
                    dict(
                        status="launch_failed",
                        type=type(error).__name__,
                        traceback=traceback.format_exc(),
                        scientific_credit=0,
                    ),
                )
            raise
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
