"""Native-blocked orchestration controls for the fresh ordinary diagnostic."""

import copy
import hashlib
import io
import json
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from validation.betse import native_multi_cell_environment_qualification as q


def authority_rows(tmp_path):
    return [q.shared.read(p) for p in sorted((tmp_path / "authority-timings").glob("*.json"))]


def authority_fixture(tmp_path, namespace):
    work = NS(failure=None, count=0, phase="make_maskM")
    targets = tuple(("synthetic." + name, namespace, name) for name in namespace)
    observer = q.AuthorityTimings(tmp_path, work, targets)
    return observer, work


def test_authority_timing_real_nested_counts_are_inclusive_not_success(tmp_path):
    calls = []

    class Opaque:
        def __repr__(self):
            raise AssertionError("Scientific values must not be inspected")

    value = Opaque()

    def inner(argument):
        calls.append("inner")
        return argument

    def outer(argument):
        assert inner(argument) is argument
        return inner(argument)

    observer, work = authority_fixture(tmp_path, dict(outer=outer, inner=inner))
    previous, trace = sys.getprofile(), sys.gettrace()
    with observer.active():
        assert outer(value) is value
        observer.checkpoint("completed-outer")
    assert sys.getprofile() is previous and sys.gettrace() is trace and work.failure is None
    rows = authority_rows(tmp_path)
    final = rows[-1]
    a, b = final["targets"]
    assert (a["entries"], a["observed_returns"], b["entries"], b["observed_returns"]) == (
        1,
        1,
        2,
        2,
    )
    assert a["inclusive_wall_ns"] >= b["inclusive_wall_ns"] >= 0
    assert a["inclusive_process_cpu_ns"] >= b["inclusive_process_cpu_ns"] >= 0
    assert calls == ["inner", "inner"] and final["active_frames"] == []
    assert final["return_event_is_success"] is False
    assert final["inclusive_times_are_additive"] is False
    assert final["scientific_values_observed"] is False
    assert final["independent_case_credit"] == 0
    assert any(len(row["active_frames"]) == 2 for row in rows)


def test_authority_timing_durable_inflight_survives_without_completion(tmp_path):
    saved = []

    def target():
        observer.checkpoint("in-flight")
        saved.extend(authority_rows(tmp_path))

    observer, _ = authority_fixture(tmp_path, dict(target=target))
    with observer.active():
        target()
    inflight = next(x for x in saved if x["reason"] == "in-flight")
    assert inflight["targets"][0]["entries"] == 1
    assert inflight["targets"][0]["observed_returns"] == 0
    assert inflight["active_frames"][0]["target"] == "synthetic.target"
    assert inflight["active_frames"][0]["elapsed_wall_ns"] >= 0
    assert inflight["periodic_checkpoint_requires_profile_events"] is True


@pytest.mark.parametrize("event", ["c_return", "c_exception"])
def test_authority_timing_exact_C_identity_and_return_categories(tmp_path, monkeypatch, event):
    observer, _ = authority_fixture(tmp_path, dict(target=len))
    frame = NS(f_code=None, f_globals={})
    clocks = iter(((100, 10), (160, 25)))
    monkeypatch.setattr(observer, "_clock", lambda: next(clocks))
    observer.last_checkpoint = 100
    observer.rows[0]["entries"] = 1  # Avoid the separately tested first-entry writer.
    observer._event(frame, "c_call", len)
    observer._event(frame, event, len)
    observer._event(frame, "c_call", abs)  # Equal names/types are never sufficient.
    row = observer.rows[0]
    assert row["entries"] == 2
    assert row["observed_returns"] == (event == "c_return")
    assert row["observed_c_exceptions"] == (event == "c_exception")
    assert (row["inclusive_wall_ns"], row["inclusive_process_cpu_ns"]) == (60, 15)
    assert observer.stack == []


@pytest.mark.parametrize("change", ["callable", "code", "globals_clone"])
def test_authority_timing_retained_binding_drift_refuses_before_action(tmp_path, change):
    from types import FunctionType

    calls = []

    def target():
        calls.append("forbidden")

    def replacement():
        return "replacement"

    namespace = dict(target=target)
    observer, work = authority_fixture(tmp_path, namespace)
    old_code = target.__code__
    try:
        if change == "callable":
            namespace["target"] = replacement
        elif change == "code":
            # Matching free-variable arity, deliberately different code.
            def changed():
                calls.append("different")

            target.__code__ = changed.__code__
        else:
            namespace["target"] = FunctionType(
                target.__code__, dict(target.__globals__), closure=target.__closure__
            )
        with pytest.raises(q.TimingObservationFailed, match="binding changed"):
            with observer.active():
                namespace["target"]()
    finally:
        target.__code__ = old_code
    assert calls == [] and work.failure is not None


def test_authority_timing_previous_profile_rejects_immediately_and_is_restored(tmp_path):
    calls = []
    original, trace = sys.getprofile(), sys.gettrace()
    primary = ValueError("inherited native entry refusal")

    def target():
        calls.append("forbidden")

    def guard(frame, event, arg):
        if original is not None:
            original(frame, event, arg)
        if event == "call" and frame.f_code is target.__code__:
            raise primary

    observer, work = authority_fixture(tmp_path, dict(target=target))
    sys.setprofile(guard)
    try:
        with pytest.raises(ValueError) as caught:
            with observer.active():
                target()
        assert caught.value is primary and sys.getprofile() is guard and sys.gettrace() is trace
    finally:
        sys.setprofile(original)
    assert calls == [] and observer.rows[0]["entries"] == 0
    assert work.failure["origin"] == "previous_profile"


@pytest.mark.parametrize("hook", ["profile", "trace"])
def test_authority_timing_hook_drift_refuses_and_restores_both(tmp_path, hook):
    original, trace = sys.getprofile(), sys.gettrace()

    def target():
        return None

    observer, _ = authority_fixture(tmp_path, dict(target=target))
    with pytest.raises(q.TimingObservationFailed, match="hooks changed"):
        with observer.active():
            (sys.setprofile if hook == "profile" else sys.settrace)(lambda *a: None)
            observer.checkpoint("outer-boundary")
    assert sys.getprofile() is original and sys.gettrace() is trace


def test_authority_timing_prior_trace_local_callback_is_unchanged(tmp_path):
    original_trace = sys.gettrace()
    seen = []

    def target():
        value = "unchanged"
        return value

    def local(frame, event, arg):
        seen.append(event)
        return local

    def trace(frame, event, arg):
        if original_trace is not None:
            original_trace(frame, event, arg)
        return local if frame.f_code is target.__code__ else trace

    observer, _ = authority_fixture(tmp_path, dict(target=target))
    sys.settrace(trace)
    try:
        with observer.active():
            assert target() == "unchanged"
        assert sys.gettrace() is trace
    finally:
        sys.settrace(original_trace)
    assert "line" in seen and "return" in seen


@pytest.mark.parametrize("source_fails", [False, True])
def test_authority_timing_capture_failure_preserves_primary_or_completed_return(
    tmp_path, monkeypatch, source_fails
):
    value, calls = {"retained": "raw returned object"}, []
    primary, cause = ValueError("source failed"), RuntimeError("source cause")

    def target():
        calls.append("target")
        if source_fails:
            raise primary from cause
        return value

    observer, work = authority_fixture(tmp_path, dict(target=target))
    timings = q.StageTimings(tmp_path, work)
    timings.authority = observer
    writer = q.shared.write

    def write(path, row):
        if Path(path).parent == observer.folder and row["reason"] == "first-target-entry":
            raise OSError("authority snapshot failed")
        return writer(path, row)

    monkeypatch.setattr(q.shared, "write", write)
    with pytest.raises(ValueError if source_fails else q.TimingObservationFailed) as caught:
        with observer.active():
            timings.run(q.STAGES[-1], "action", target)
    assert calls == ["target"] and work.failure is not None
    if source_fails:
        assert caught.value is primary and primary.__cause__ is cause
    else:
        assert caught.value.partial["returned"] is value
    assert authority_rows(tmp_path)[-1]["observation_failed"] is True


@pytest.mark.parametrize(
    "limit", ["max_active", "max_events", "max_snapshots", "max_snapshot_bytes"]
)
def test_authority_timing_recorder_bounds_refuse_without_acceptance(tmp_path, limit):
    def target(depth=0):
        if depth:
            return target(depth - 1)

    observer, work = authority_fixture(tmp_path, dict(target=target))
    observer.policy[limit] = 1
    with pytest.raises(q.TimingObservationFailed, match="allowance"):
        with observer.active():
            target(2)
            observer.checkpoint("outer-boundary")
    assert work.failure is not None
    assert len(list(observer.folder.glob("*.json"))) <= observer.policy["max_snapshots"]


def test_authority_timing_periodic_summary_has_bounded_inflight_clock(tmp_path, monkeypatch):
    def target():
        return None

    observer, _ = authority_fixture(tmp_path, dict(target=target))
    frame = NS(f_code=target.__code__, f_globals=target.__globals__)
    clocks = iter(((100, 10), (110, 15), (150, 30)))
    monkeypatch.setattr(observer, "_clock", lambda: next(clocks))
    observer.policy.update(periodic_ns=20, clock_stride=1)
    observer._event(frame, "call", None)
    observer._event(NS(f_code=None), "c_call", abs)
    observer._event(NS(f_code=None), "c_call", abs)
    rows = authority_rows(tmp_path)
    assert [x["reason"] for x in rows] == ["first-target-entry", "periodic"]
    active = rows[-1]["active_frames"][0]
    assert (active["elapsed_wall_ns"], active["elapsed_process_cpu_ns"]) == (50, 20)
    assert rows[-1]["targets"][0]["observed_returns"] == 0


def test_authority_timing_duplicate_or_unavailable_targets_refuse(tmp_path):
    def target():
        return None

    namespace = dict(target=target)
    for targets in (
        (),
        (("a", namespace, "missing"),),
        (("a", namespace, "target"), ("b", namespace, "target")),
    ):
        with pytest.raises(ValueError, match="targets|Unavailable|Ambiguous|Duplicate"):
            q.AuthorityTimings(tmp_path, NS(failure=None), targets)


def test_authority_timing_equal_but_distinct_code_is_not_the_retained_target(tmp_path):
    from types import FunctionType

    def target():
        return "synthetic"

    other_code = target.__code__.replace()
    assert other_code == target.__code__ and other_code is not target.__code__
    clone = FunctionType(other_code, target.__globals__)
    observer, _ = authority_fixture(tmp_path, dict(target=target))
    with observer.active():
        assert clone() == "synthetic"
        assert target() == "synthetic"
    assert observer.rows[0]["entries"] == observer.rows[0]["observed_returns"] == 1


def authority_loaded_modules(monkeypatch):
    prefix = "cells.processes.betse_native_multi_cell_"
    multi = NS(__name__=prefix + "caller", _check=len, _verify_sources=abs)
    env = NS(__name__=prefix + "environment", multi=multi, _TreeRuntime=type("Tree", (), {}))
    atoms = NS(__name__="cells.processes.betse_native_single_cell_grid_alias")
    accounting = NS(__name__="cells.processes.betse_native_single_cell_caller_completion")
    caches = NS(__name__="cells.processes.betse_initial_mesh_preparation_cache")
    core = NS(__name__="cells.processes.betse_native_single_cell_core_preparation", caches=caches)
    multi.atoms, multi.accounting, multi.core = atoms, accounting, core
    modules = dict(environment=env, multi=multi, atoms=atoms, accounting=accounting, core=core)
    modules["caches"] = caches
    for module in modules.values():
        monkeypatch.setitem(sys.modules, module.__name__, module)
    return modules


def test_authority_timing_loaded_target_roster_reads_only_named_bindings(monkeypatch):
    modules = authority_loaded_modules(monkeypatch)
    targets = q._authority_targets()
    assert len(targets) == 24 <= q.AUTHORITY_TIMING_POLICY["max_targets"]
    assert {x[2] for x in targets[:16]} >= {"_check", "_verify_sources", "_TREE_QUERY", "query"}
    assert [x[2] for x in targets[16:]] == [
        "_bindings",
        "_lineage",
        "_namespace_bindings",
        "_helper_bindings",
        "validate",
        "_check_binding_identity",
        "validate",
        "snapshot",
    ]
    assert all(len(x) == 3 for x in targets)
    assert targets[-1][1] is vars(modules["caches"])
    monkeypatch.delitem(sys.modules, modules["multi"].__name__)
    with pytest.raises(ValueError, match="loaded"):
        q._authority_targets()


@pytest.mark.parametrize("alias", ["atoms", "accounting", "core", "caches"])
@pytest.mark.parametrize("change", ["missing_loaded", "foreign_alias"])
def test_authority_timing_caller_dependency_requires_actual_loaded_alias(
    monkeypatch, alias, change
):
    modules = authority_loaded_modules(monkeypatch)
    if change == "missing_loaded":
        monkeypatch.delitem(sys.modules, modules[alias].__name__)
    else:
        owner = modules["core" if alias == "caches" else "multi"]
        monkeypatch.setattr(owner, alias, NS(**vars(modules[alias])))
    with pytest.raises(ValueError, match="Actual loaded caller"):
        q._authority_targets()


def test_authority_timing_caller_breakdown_records_nested_metadata_only(tmp_path, monkeypatch):
    modules = authority_loaded_modules(monkeypatch)
    multi, caches = modules["multi"], modules["caches"]
    calls = []

    class Opaque:
        def __repr__(self):
            raise AssertionError("Timing must not inspect validated data")

    value = Opaque()

    def helper_bindings():
        calls.append("helpers")

    def bindings():
        multi._helper_bindings()

    def namespace_bindings():
        multi._helper_bindings()

    def cache_validate(argument):
        assert argument is value
        calls.append("validate-cache")

    def cache_snapshot(argument):
        assert argument is value
        calls.append("snapshot")

    def lineage():
        caches.validate(value)
        caches.snapshot(value)

    def descriptor_validate(argument):
        assert argument is value
        calls.append("descriptor")

    def binding_identity(argument):
        assert argument is value
        calls.append("identity")

    def check():
        multi._bindings()
        multi._lineage()
        multi._namespace_bindings()
        multi.atoms.validate(value)
        multi.accounting._check_binding_identity(value)

    multi._check, multi._bindings, multi._lineage = check, bindings, lineage
    multi._namespace_bindings, multi._helper_bindings = namespace_bindings, helper_bindings
    multi.atoms.validate = descriptor_validate
    multi.accounting._check_binding_identity = binding_identity
    caches.validate, caches.snapshot = cache_validate, cache_snapshot
    targets = q._authority_targets()
    selected = (targets[11], *targets[16:])
    assert selected[0][1] is vars(multi) and selected[0][2] == "_check"
    work = NS(failure=None, count=0, phase="make_maskM")
    observer = q.AuthorityTimings(tmp_path, work, selected)
    previous, trace = sys.getprofile(), sys.gettrace()
    with observer.active():
        multi._check()
    assert sys.getprofile() is previous and sys.gettrace() is trace and work.failure is None
    final = authority_rows(tmp_path)[-1]
    for row in final["targets"]:
        expected = 2 if row["target"].endswith("._helper_bindings") else 1
        assert row["entries"] == row["observed_returns"] == expected
    assert calls == ["helpers", "validate-cache", "snapshot", "helpers", "descriptor", "identity"]
    assert final["scientific_values_observed"] is False
    assert final["inclusive_times_are_additive"] is False
    assert final["independent_case_credit"] == 0


def test_authority_timing_worker_uses_loaded_observer_before_mock_stage(tmp_path, monkeypatch):
    prepared, output, baseline = repair_c5_worker(tmp_path, monkeypatch, "none")
    assert q.worker(prepared, "a" * 64, "release", q.CASES[0], output) == 0
    diagnostic = q.shared.read(output / "diagnostic.json")
    assert diagnostic["completed_stages"] == baseline["completed_stages"]
    assert diagnostic["authority_timing"]["initialized"] is True
    final = authority_rows(output)[-1]
    assert final["targets"][0]["entries"] == final["targets"][0]["observed_returns"] == 1
    assert final["observation_failed"] is False
    assert diagnostic["accepted_cases"] == 0


def test_authority_timing_selection_is_function_scoped():
    selected = NS(originalname="test_authority_timing_nested", name="x")
    excluded = NS(originalname="test_unrelated", name="authority_timing")
    assert q._software_selection("authority-timing", [selected, excluded]) == (
        [selected],
        [excluded],
    )


class FalseyTimingStop(BaseException):
    def __bool__(self):
        return False


def test_authority_timing_cleanup_formatting_waits_for_real_cleared_hook_recovery(tmp_path):
    original, trace, setter = sys.getprofile(), sys.gettrace(), sys.setprofile
    armed, formatting, refused = [False], [], []
    primary, cause = ValueError("source primary"), RuntimeError("source cause")

    class RecordedFailure(FalseyTimingStop):
        def __str__(self):
            formatting.append((sys.getprofile() is guard, sys.gettrace() is trace))
            return "recorded cleanup refusal"

    fault = RecordedFailure()

    def target():
        return None

    observer, work = authority_fixture(tmp_path, dict(target=target))

    def guard(frame, event, arg):
        if original is not None:
            original(frame, event, arg)
        if (
            armed[0]
            and event == "c_call"
            and arg is setter
            and frame.f_code is q.AuthorityTimings._restore_hook.__code__
        ):
            armed[0] = False
            refused.append(True)
            raise fault

    setter(guard)
    try:
        with pytest.raises(ValueError) as caught:
            with observer.active():
                target()
                armed[0] = True
                raise primary from cause
        assert caught.value is primary and primary.__cause__ is cause
        assert sys.getprofile() is guard and sys.gettrace() is trace
    finally:
        armed[0] = False
        setter(original)
    assert refused == [True] and formatting and all(a and b for a, b in formatting)
    assert any(error is fault for _, error in observer.pending_cleanup_errors)
    assert work.failure is not None and observer.lifecycle["final_capture_attempted"] is True


@pytest.mark.parametrize("helper", ["_restore_hook", "_render_errors"])
def test_authority_timing_cleanup_helper_entry_refusal_keeps_primary_and_other_hook(
    tmp_path, helper
):
    original, trace, setter, trace_setter = (
        sys.getprofile(),
        sys.gettrace(),
        sys.setprofile,
        sys.settrace,
    )
    armed, formatting, entries = [False], [], []
    primary, cause = ValueError("source primary"), RuntimeError("source cause")

    class EntryFailure(FalseyTimingStop):
        def __str__(self):
            formatting.append(sys.getprofile())
            return "cleanup helper entry refusal"

    fault = EntryFailure()

    def target():
        return None

    observer, _ = authority_fixture(tmp_path, dict(target=target))
    code = getattr(q.AuthorityTimings, helper).__code__

    def guard(frame, event, arg):
        if original is not None:
            original(frame, event, arg)
        if armed[0] and event == "call" and frame.f_code is code:
            armed[0] = False
            entries.append(helper)
            raise fault

    setter(guard)
    try:
        with pytest.raises(ValueError) as caught:
            with observer.active():
                target()
                trace_setter(lambda *args: None)
                armed[0] = True
                raise primary from cause
        assert caught.value is primary and primary.__cause__ is cause
        assert sys.getprofile() is guard and sys.gettrace() is trace
    finally:
        armed[0] = False
        setter(original)
        trace_setter(trace)
    assert entries == [helper] and formatting == []
    assert any(error is fault for _, error in observer.pending_cleanup_errors)
    assert observer.lifecycle["hooks_after_cleanup"] == dict(profile="entry", trace="entry")
    assert observer.lifecycle["raw_cleanup_errors"]


def test_authority_timing_unrestorable_hook_never_formats_failure_wrapper(tmp_path, monkeypatch):
    original, setter = sys.getprofile(), sys.setprofile
    formatting = []

    class Unrenderable(FalseyTimingStop):
        def __str__(self):
            formatting.append("must not format while unrestored")
            return "unsafe formatting"

    fault = Unrenderable()

    def target():
        return None

    observer, work = authority_fixture(tmp_path, dict(target=target))

    def replace(value):
        if value is original:
            raise fault
        return setter(value)

    with monkeypatch.context() as patch:
        patch.setattr(sys, "setprofile", replace)
        try:
            with pytest.raises(q.TimingObservationFailed) as caught:
                with observer.active():
                    target()
            assert caught.value.capture_error is fault and caught.value.__cause__ is fault
            assert any(error is fault for _, error in caught.value.raw_cleanup_errors)
            assert str(caught.value) == "Authority timing cleanup failed; raw exception retained"
        finally:
            setter(original)
    assert formatting == [] and work.failure is not None
    assert observer.lifecycle["final_capture_blocked"] == "Inherited hooks not restored"
    assert (
        observer.lifecycle["raw_cleanup_error_count"] <= q.AUTHORITY_TIMING_POLICY["max_raw_errors"]
    )


def test_authority_timing_one_shot_bounds_cleanup_records_across_invocations(tmp_path):
    def target():
        return None

    observer, _ = authority_fixture(tmp_path, dict(target=target))
    with observer.active():
        target()
    with pytest.raises(ValueError, match="reused"):
        with observer.active():
            raise AssertionError("No second observer invocation")


@pytest.mark.parametrize("hook", ["profile", "trace"])
@pytest.mark.parametrize("position", ["before", "after"])
def test_authority_timing_cleanup_setter_fault_keeps_primary_and_independent_restore(
    tmp_path, monkeypatch, hook, position
):
    original_profile, original_trace = sys.getprofile(), sys.gettrace()
    set_profile, set_trace = sys.setprofile, sys.settrace
    primary, cause = ValueError("source primary"), RuntimeError("source cause")
    fault = FalseyTimingStop("cleanup setter refusal")
    calls, armed = [], [True]

    def target():
        return None

    def changed_trace(*args):
        return None

    observer, work = authority_fixture(tmp_path, dict(target=target))

    def setter(value):
        expected = original_profile if hook == "profile" else original_trace
        delegate = set_profile if hook == "profile" else set_trace
        if armed[0] and value is expected:
            armed[0] = False
            calls.append(hook)
            if position == "after":
                delegate(value)
            raise fault
        return delegate(value)

    with monkeypatch.context() as patch:
        patch.setattr(sys, "set" + hook, setter)
        try:
            with pytest.raises(ValueError) as caught:
                with observer.active():
                    set_trace(changed_trace)
                    target()
                    raise primary from cause
            assert caught.value is primary and primary.__cause__ is cause
            assert sys.getprofile() is original_profile and sys.gettrace() is original_trace
        finally:
            armed[0] = False
            set_profile(original_profile)
            set_trace(original_trace)
    assert calls == [hook] and work.failure is not None
    assert observer.lifecycle["cleanup_errors"]
    assert observer.lifecycle["final_capture_attempted"] is True
    assert observer.lifecycle["hooks_after_cleanup"] == dict(profile="entry", trace="entry")
    assert authority_rows(tmp_path)[-1]["observation_failed"] is True


@pytest.mark.parametrize("position", ["before", "after"])
def test_authority_timing_setup_setter_fault_never_enters_source(tmp_path, monkeypatch, position):
    original_profile, original_trace = sys.getprofile(), sys.gettrace()
    setter, calls = sys.setprofile, []
    fault = FalseyTimingStop("setup setter refusal")

    def target():
        calls.append("forbidden")

    observer, work = authority_fixture(tmp_path, dict(target=target))

    def replace(value):
        if value is observer.active_profile:
            if position == "after":
                setter(value)
            raise fault
        return setter(value)

    with monkeypatch.context() as patch:
        patch.setattr(sys, "setprofile", replace)
        try:
            with pytest.raises(FalseyTimingStop) as caught:
                with observer.active():
                    target()
            assert caught.value is fault
            assert sys.getprofile() is original_profile and sys.gettrace() is original_trace
        finally:
            setter(original_profile)
    assert calls == [] and work.failure is not None
    assert observer.lifecycle["setup_error"] is not None
    assert observer.lifecycle["hooks_after_cleanup"] == dict(profile="entry", trace="entry")


def test_authority_timing_persistent_setter_fault_is_bounded_and_blocks_unguarded_capture(
    tmp_path, monkeypatch
):
    original_profile, original_trace = sys.getprofile(), sys.gettrace()
    set_profile, set_trace = sys.setprofile, sys.settrace
    primary = ValueError("source primary")
    calls = []

    def target():
        return None

    observer, _ = authority_fixture(tmp_path, dict(target=target))

    def replace(value):
        if value is original_profile:
            calls.append("restore")
            raise FalseyTimingStop("persistent restore refusal")
        return set_profile(value)

    with monkeypatch.context() as patch:
        patch.setattr(sys, "setprofile", replace)
        try:
            with pytest.raises(ValueError) as caught:
                with observer.active():
                    set_trace(lambda *args: None)
                    raise primary
            assert caught.value is primary and sys.gettrace() is original_trace
            assert observer.lifecycle["hooks_after_cleanup"]["profile"] == "observer"
        finally:
            set_profile(original_profile)
            set_trace(original_trace)
    assert calls == ["restore"] * 4
    assert observer.lifecycle["final_capture_attempted"] is False
    assert observer.lifecycle["final_capture_blocked"] == "Inherited hooks not restored"
    assert not any(row["reason"] == "observer-exit" for row in authority_rows(tmp_path))


def test_authority_timing_real_profile_cleanup_rejection_recovers_chain_before_capture(tmp_path):
    original, trace = sys.getprofile(), sys.gettrace()
    set_profile = sys.setprofile
    armed, refused, capture_entries = [False], [], []
    primary, cause = ValueError("source primary"), RuntimeError("source cause")
    fault = FalseyTimingStop("inherited cleanup rejection")

    def target():
        return None

    observer, _ = authority_fixture(tmp_path, dict(target=target))

    def guard(frame, event, arg):
        if original is not None:
            original(frame, event, arg)
        if (
            armed[0]
            and event == "c_call"
            and arg is set_profile
            and frame.f_code is q.AuthorityTimings._restore_hook.__code__
        ):
            armed[0] = False
            refused.append("actual c_call")
            raise fault
        if event == "call" and frame.f_code is q.AuthorityTimings._snapshot_record.__code__:
            if frame.f_locals["reason"] == "observer-exit":
                capture_entries.append(sys.getprofile() is guard)

    set_profile(guard)
    try:
        with pytest.raises(ValueError) as caught:
            with observer.active():
                target()
                armed[0] = True
                raise primary from cause
        assert caught.value is primary and primary.__cause__ is cause
        assert sys.getprofile() is guard and sys.gettrace() is trace
    finally:
        armed[0] = False
        set_profile(original)
    assert refused == ["actual c_call"] and capture_entries == [True]
    assert observer.lifecycle["hooks_after_cleanup"] == dict(profile="entry", trace="entry")


@pytest.mark.parametrize("source_fails", [False, True])
def test_authority_timing_falsey_BaseException_at_profile_return_retains_original(
    tmp_path, monkeypatch, source_fails
):
    primary, cause = ValueError("source unwind"), RuntimeError("original cause")
    fault, value = FalseyTimingStop("return observation failed"), {"raw": "same object"}

    def target():
        if source_fails:
            raise primary from cause
        return value

    observer, work = authority_fixture(tmp_path, dict(target=target))
    timings = q.StageTimings(tmp_path, work)
    timings.authority = observer
    event = observer._event

    def observe(frame, kind, arg):
        if kind == "return" and frame.f_code is target.__code__:
            raise fault
        return event(frame, kind, arg)

    monkeypatch.setattr(observer, "_event", observe)
    with pytest.raises(ValueError if source_fails else q.TimingObservationFailed) as caught:
        with observer.active():
            timings.run("make_maskM", "action", target)
    assert observer.failure is fault and work.failure is not None
    if source_fails:
        assert caught.value is primary and primary.__cause__ is cause
    else:
        assert caught.value.partial["returned"] is value


@pytest.mark.parametrize("source_fails", [False, True])
def test_authority_timing_falsey_BaseException_final_capture_keeps_primary_and_hooks(
    tmp_path, monkeypatch, source_fails
):
    original, trace = sys.getprofile(), sys.gettrace()
    primary, cause = ValueError("source primary"), RuntimeError("source cause")
    fault = FalseyTimingStop("final writer failure")

    def target():
        if source_fails:
            raise primary from cause

    observer, work = authority_fixture(tmp_path, dict(target=target))
    writer = q.shared.write

    def write(path, row):
        if Path(path).parent == observer.folder and row["reason"] == "observer-exit":
            raise fault
        return writer(path, row)

    with monkeypatch.context() as patch:
        patch.setattr(q.shared, "write", write)
        with pytest.raises(ValueError if source_fails else q.TimingObservationFailed) as caught:
            with observer.active():
                target()
    assert observer.failure is fault and work.failure is not None
    if source_fails:
        assert caught.value is primary and primary.__cause__ is cause
    else:
        assert caught.value.capture_error is fault
    assert sys.getprofile() is original and sys.gettrace() is trace
    assert observer.lifecycle["final_capture_error"] is not None


@pytest.mark.parametrize("stride", [1, 4096])
def test_authority_timing_active_real_clocks_do_not_reenter_bookkeeping(tmp_path, stride):
    previous, trace = sys.getprofile(), sys.gettrace()
    clock_events = []

    def target():
        observer.checkpoint("inside-target")

    observer, work = authority_fixture(tmp_path, dict(target=target))
    observer.policy["clock_stride"] = stride

    def guard(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event in ("c_call", "c_return") and arg in (q.time.monotonic_ns, q.time.process_time_ns):
            clock_events.append((event, observer.bookkeeping_depth > 0))

    sys.setprofile(guard)
    try:
        with observer.active():
            # For4096, align the formerly dangerous wall-clock c_return.
            observer.events = max(stride - 3, 0)
            first = observer._clock()
            target()
            observer.checkpoint("outer-boundary")
            last = observer._clock()
            assert first[0] <= last[0] and first[1] <= last[1]
        assert sys.getprofile() is guard and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
    assert work.failure is None and observer.failure is None
    assert observer.rows[0]["entries"] == observer.rows[0]["observed_returns"] == 1
    assert any(protected for _, protected in clock_events)
    assert observer.suppressed_own_events > 0
    rows = authority_rows(tmp_path)
    assert all(a["monotonic_ns"] <= b["monotonic_ns"] for a, b in zip(rows, rows[1:], strict=False))


def timing_fixture(tmp_path):
    work = NS(failure=None, count=0, phase=None)
    timings = q.StageTimings(tmp_path, work)
    base = q.shared.Evidence(tmp_path, sidecars=True, capture_writer=q._write_capture)
    return timings, q.TimedEvidence(base, timings), work


def timing_rows(tmp_path):
    return [q.shared.read(p) for p in sorted((tmp_path / "stage-timings").glob("*.json"))]


def test_stage_timing_action_and_capture_separate_wall_and_CPU(tmp_path, monkeypatch):
    walls, cpus = iter((100, 160, 200, 280)), iter((10, 20, 30, 50))
    monkeypatch.setattr(q.time, "monotonic_ns", lambda: next(walls))
    monkeypatch.setattr(q.time, "process_time_ns", lambda: next(cpus))
    timings, evidence, work = timing_fixture(tmp_path)
    value = {"actual_return": "unchanged"}
    result = q.shared.run_stages(timings.steps(((q.STAGES[0], lambda: value),)), evidence, work)
    rows = timing_rows(tmp_path)
    assert [r["position"] for r in rows] == ["start", "returned", "start", "capture_saved"]
    assert [(r["elapsed_wall_ns"], r["elapsed_process_cpu_ns"]) for r in rows] == [
        (None, None),
        (60, 10),
        (None, None),
        (80, 20),
    ]
    assert [r["operation"] for r in rows] == ["action", "action", "capture", "capture"]
    assert all(
        r["entry_is_source_success"] is False and r["independent_case_credit"] == 0 for r in rows
    )
    assert q.payload.read(tmp_path / evidence.rows[0]["path"]) == value
    assert result["completed_stages"] == [q.STAGES[0]] and result["accepted_cases"] == 0


@pytest.mark.parametrize("timing_fails", [False, True])
def test_stage_timing_preserves_primary_cause_even_if_unwind_record_fails(
    tmp_path, monkeypatch, timing_fails
):
    timings, _, work = timing_fixture(tmp_path)
    writer = q.shared.write
    primary, cause = ValueError("original source"), RuntimeError("original cause")

    def write(path, row):
        if timing_fails and Path(path).parent == timings.folder and row["position"] == "raised":
            raise OSError("timing disk failure")
        return writer(path, row)

    def source():
        raise primary from cause

    monkeypatch.setattr(q.shared, "write", write)
    with pytest.raises(ValueError) as caught:
        timings.run(q.STAGES[0], "action", source)
    assert caught.value is primary and caught.value.__cause__ is cause
    assert bool(timings.failures) is timing_fails
    assert (work.failure is not None) is timing_fails
    assert timing_rows(tmp_path)[0]["position"] == "start"


@pytest.mark.parametrize("position", ["start", "returned"])
def test_stage_timing_observer_failure_stops_continuation_and_retains_return(
    tmp_path, monkeypatch, position
):
    timings, evidence, work = timing_fixture(tmp_path)
    writer, calls, value = q.shared.write, [], {"retained": "source return"}

    def write(path, row):
        if Path(path).parent == timings.folder and row["position"] == position:
            raise OSError("timing checkpoint refused")
        return writer(path, row)

    def action():
        calls.append("first")
        return value

    monkeypatch.setattr(q.shared, "write", write)
    result = q.shared.run_stages(
        timings.steps(((q.STAGES[0], action), (q.STAGES[1], lambda: calls.append("later")))),
        evidence,
        work,
    )
    assert calls == ([] if position == "start" else ["first"])
    assert result["source_error"] is None and result["observer_error"] is not None
    assert result["completed_stages"] == [] and result["accepted_cases"] == 0
    if position == "returned":
        row = next(
            r for r in evidence.rows if r["label"] == "TimingObservationFailed.partial.returned"
        )
        assert q.payload.read(tmp_path / row["path"]) == value


def test_stage_timing_capture_failure_stays_distinct_from_source_error(tmp_path):
    timings, _, work = timing_fixture(tmp_path)
    calls = []
    original = NS(rows=[], save=lambda label, value: False, failure=lambda error: None)
    evidence = q.TimedEvidence(original, timings)
    result = q.shared.run_stages(
        timings.steps(
            (
                (q.STAGES[0], lambda: {"source_completed": True}),
                (q.STAGES[1], lambda: calls.append("later")),
            )
        ),
        evidence,
        work,
    )
    assert calls == [] and result["failed_stage"] == q.STAGES[0] + ":capture"
    assert result["source_error"] is None and work.failure is None
    assert timing_rows(tmp_path)[-1]["position"] == "capture_failed"


def test_stage_timing_capture_end_observation_failure_preserves_saved_bytes(tmp_path, monkeypatch):
    timings, evidence, work = timing_fixture(tmp_path)
    writer, calls = q.shared.write, []

    def write(path, row):
        if Path(path).parent == timings.folder and row["position"] == "capture_saved":
            raise OSError("end checkpoint failure")
        return writer(path, row)

    monkeypatch.setattr(q.shared, "write", write)
    value = {"complete": True}
    result = q.shared.run_stages(
        timings.steps(((q.STAGES[0], lambda: value), (q.STAGES[1], lambda: calls.append("later")))),
        evidence,
        work,
    )
    assert evidence.rows[0]["status"] == "saved" and calls == []
    assert q.payload.read(tmp_path / evidence.rows[0]["path"]) == value
    assert result["accepted_cases"] == 0 and result["observer_error"] is not None


def test_stage_timing_unfinished_start_does_not_invent_elapsed_work(tmp_path):
    timings, _, _ = timing_fixture(tmp_path)
    timings._checkpoint(q.STAGES[0], "action", "start")
    rows = timing_rows(tmp_path)
    assert len(rows) == 1 and rows[0]["position"] == "start"
    assert rows[0]["elapsed_wall_ns"] is None and rows[0]["elapsed_process_cpu_ns"] is None


@pytest.mark.parametrize("label, operation", [("unknown", "action"), (q.STAGES[0], "unknown")])
def test_stage_timing_unknown_boundaries_refuse_before_delegate(tmp_path, label, operation):
    timings, _, work = timing_fixture(tmp_path)
    calls = []
    with pytest.raises(q.TimingObservationFailed):
        timings.run(label, operation, lambda: calls.append("forbidden"))
    assert calls == [] and work.failure is not None


def test_stage_timing_forensic_capture_keeps_existing_separate_path(tmp_path):
    timings, _, _ = timing_fixture(tmp_path)
    calls = []
    primary = ValueError("source")
    base = NS(
        rows=[],
        save=lambda label, value: calls.append((label, value)),
        failure=lambda error: calls.append(error),
    )
    evidence = q.TimedEvidence(base, timings)
    evidence.failure(primary)
    evidence.save(q.STAGES[0] + ":interrupted-return", "retained")
    assert calls == [primary, (q.STAGES[0] + ":interrupted-return", "retained")]
    assert timing_rows(tmp_path) == []


@pytest.mark.parametrize("failure_kind", ["write", "profile_entry"])
def test_stage_timing_capture_start_failure_retains_exact_request_once(
    tmp_path, monkeypatch, failure_kind
):
    work = q.shared.WorkLog(tmp_path, q.ROOT, phases=q.STAGES)
    timings = q.StageTimings(tmp_path, work)
    base = q.shared.Evidence(tmp_path, sidecars=True, capture_writer=q._write_capture)
    for label in q.STAGES[:6]:
        assert base.save(label, {"retained": label})
    evidence = q.TimedEvidence(base, timings)
    value = capture_metadata_request("x" * (17 * 2**20))
    writer, calls, saves = q.shared.write, [], []
    error = OSError("capture start observation")
    previous = sys.getprofile()

    def write(path, row):
        if (
            failure_kind == "write"
            and Path(path).parent == timings.folder
            and row["operation"] == "capture"
            and row["position"] == "start"
        ):
            raise error
        return writer(path, row)

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code is q.StageTimings._checkpoint.__code__:
            if (
                failure_kind == "profile_entry"
                and frame.f_locals["operation"] == "capture"
                and frame.f_locals["position"] == "start"
            ):
                raise error
        if event == "call" and frame.f_code is q.shared.Evidence.save.__code__:
            saves.append(
                (frame.f_locals["label"], frame.f_locals["value"], work._retaining_failure)
            )

    monkeypatch.setattr(q.shared, "write", write)
    sys.setprofile(profile)
    try:
        with work.active():
            result = q.shared.run_stages(
                timings.steps(
                    (("ordinary_request", lambda: value), ("cell_index", lambda: calls.append(1)))
                ),
                evidence,
                work,
            )
        assert sys.getprofile() is profile
    finally:
        sys.setprofile(previous)
    assert calls == [] and len(saves) == 1
    assert saves[0][0] == "ordinary_request" and saves[0][1] is value and saves[0][2] > 0
    assert len(evidence.rows) == 7 and evidence.rows[-1]["status"] == "saved"
    path = tmp_path / "capture-0006.json"
    assert q.payload.MAX_METADATA < path.stat().st_size < q.payload.REQUEST_METADATA
    assert q.read_capture(path, evidence.rows[-1]) == value
    assert result["observer_error"] is not None and result["source_error"] is None
    assert result["completed_stages"] == [] and result["accepted_cases"] == 0
    assert len(timings.failures) == 1 and work.failure_retention_entries > 0


@pytest.mark.parametrize("position", ["start", "returned", "raised"])
def test_stage_timing_checkpoint_entry_guard_preserves_return_or_primary(tmp_path, position):
    work = q.shared.WorkLog(tmp_path, q.ROOT, phases=q.STAGES)
    timings = q.StageTimings(tmp_path, work)
    base = q.shared.Evidence(tmp_path, sidecars=True, capture_writer=q._write_capture)
    evidence = q.TimedEvidence(base, timings)
    value, calls, guarded_captures = {"returned_bits": "8000000000000000"}, [], []
    observation = RuntimeError("prior guard rejected checkpoint entry")
    primary, cause = ValueError("primary source"), RuntimeError("primary cause")
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if (
            event == "call"
            and frame.f_code is q.StageTimings._checkpoint.__code__
            and frame.f_locals["position"] == position
        ):
            raise observation
        if event == "call" and frame.f_code is q.shared.Evidence.save.__code__:
            guarded_captures.append(work._retaining_failure)

    def source():
        calls.append("source")
        if position == "raised":
            raise primary from cause
        return value

    sys.setprofile(profile)
    try:
        with work.active():
            result = q.shared.run_stages(
                timings.steps(
                    ((q.STAGES[0], source), (q.STAGES[1], lambda: calls.append("later")))
                ),
                evidence,
                work,
            )
        assert sys.getprofile() is profile
    finally:
        sys.setprofile(previous)
    assert calls == ([] if position == "start" else ["source"])
    assert result["observer_error"] is not None and result["accepted_cases"] == 0
    assert len(timings.failures) == 1
    if position == "returned":
        assert guarded_captures and all(n > 0 for n in guarded_captures)
        row = next(
            r for r in evidence.rows if r["label"] == "TimingObservationFailed.partial.returned"
        )
        assert q.payload.read(tmp_path / row["path"]) == value
        assert observation is not None and work.failure_retention_entries > 0
        graph = result["interrupted_exception_graph"]
        assert "prior guard rejected checkpoint entry" in json.dumps(graph)
    elif position == "raised":
        assert primary.__cause__ is cause
        assert "primary source" in json.dumps(result["interrupted_exception_graph"])
        assert "primary cause" in json.dumps(result["interrupted_exception_graph"])


def test_stage_timing_forensic_fallback_still_enforces_prior_guard(tmp_path):
    work = q.shared.WorkLog(tmp_path, q.ROOT, phases=q.STAGES)
    timings = q.StageTimings(tmp_path, work)
    base = q.shared.Evidence(tmp_path, sidecars=True, capture_writer=q._write_capture)
    evidence = q.TimedEvidence(base, timings)
    previous, calls = sys.getprofile(), []
    refusal = RuntimeError("prior guard forbids evidence writer")

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if (
            event == "call"
            and frame.f_code is q.StageTimings._checkpoint.__code__
            and frame.f_locals["operation"] == "capture"
            and frame.f_locals["position"] == "start"
        ):
            raise RuntimeError("capture timing refused")
        if event == "call" and frame.f_code is q.shared.Evidence.save.__code__:
            calls.append(work._retaining_failure)
            raise refusal

    sys.setprofile(profile)
    try:
        with work.active(), pytest.raises(RuntimeError) as caught:
            evidence.save(q.STAGES[0], {"already_returned": True})
        assert caught.value is refusal and sys.getprofile() is profile
    finally:
        sys.setprofile(previous)
    assert len(calls) == 1 and calls[0] > 0 and base.rows == []
    assert work.failure is not None


@pytest.mark.parametrize("failure_kind", ["write", "profile_entry"])
def test_stage_timing_large_action_return_keeps_declared_capture_budget(
    tmp_path, monkeypatch, failure_kind
):
    work = q.shared.WorkLog(tmp_path, q.ROOT, phases=q.STAGES)
    timings = q.StageTimings(tmp_path, work)
    base = q.shared.Evidence(tmp_path, sidecars=True, capture_writer=q._write_capture)
    for label in q.STAGES[:6]:
        assert base.save(label, {"retained": label})
    evidence = q.TimedEvidence(base, timings)
    value = capture_metadata_request("x" * (17 * 2**20))
    writer, calls, saves = q.shared.write, [], []
    observation = RuntimeError("timing after large request returned")
    previous = sys.getprofile()

    def write(path, row):
        if failure_kind == "write" and Path(path).parent == timings.folder:
            if row["operation"] == "action" and row["position"] == "returned":
                raise observation
        return writer(path, row)

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code is q.StageTimings._checkpoint.__code__:
            if failure_kind == "profile_entry" and frame.f_locals["position"] == "returned":
                raise observation
        if event == "call" and frame.f_code is q.shared.Evidence.save.__code__:
            saves.append(
                (frame.f_locals["label"], frame.f_locals["value"], work._retaining_failure)
            )

    monkeypatch.setattr(q.shared, "write", write)
    sys.setprofile(profile)
    try:
        with work.active():
            result = q.shared.run_stages(
                timings.steps(
                    (("ordinary_request", lambda: value), ("cell_index", lambda: calls.append(1)))
                ),
                evidence,
                work,
            )
        assert sys.getprofile() is profile
    finally:
        sys.setprofile(previous)
    assert calls == [] and len(saves) == 2
    assert saves[0][0] == "ordinary_request" and saves[0][1] is value and saves[0][2] > 0
    assert saves[1][0] == "TimingObservationFailed.partial.returned" and saves[1][2] > 0
    assert len(evidence.rows) == 8 and evidence.rows[6]["status"] == "saved"
    path = tmp_path / "capture-0006.json"
    assert q.payload.MAX_METADATA < path.stat().st_size < q.payload.REQUEST_METADATA
    assert q.read_capture(path, evidence.rows[6]) == value
    assert evidence.rows[7]["status"] == "capture_failed"
    assert "metadata bound" in json.dumps(evidence.rows[7])
    assert result["observer_error"] is not None and result["source_error"] is None
    assert result["completed_stages"] == [] and result["accepted_cases"] == 0
    assert "timing after large request returned" in json.dumps(
        result["interrupted_exception_graph"]
    )
    assert len(timings.failures) == 1 and work.failure_retention_entries > 0


def capture_metadata_request(text="{}"):
    return dict(
        identity="a" * 64,
        caller_request=dict(
            identity="b" * 64,
            lifecycle_request={},
            lifecycle_state={"descriptor_json": text},
            configuration_json="{}",
            grid_descriptor="native_grid_size_yaml_alias@1",
        ),
    )


def capture_metadata_row(path):
    return dict(
        label="ordinary_request",
        path=path.name,
        status="saved",
        sha256=q.source_snapshot.digest(path),
    )


def test_capture_metadata_nested_request_roundtrip_and_default_bound(tmp_path):
    value = capture_metadata_request("x" * (17 * 2**20))
    value["caller_request"]["lifecycle_state"]["raw_bytes_hex"] = "00" * q.payload.THRESHOLD
    path = tmp_path / "capture-0006.json"
    pins = q._write_capture("ordinary_request", path, value)
    assert q.payload.MAX_METADATA < path.stat().st_size < q.payload.REQUEST_METADATA
    row = capture_metadata_row(path)
    assert q.read_capture(path, row) == value
    assert q.capture_files(path, row) == pins and len(pins) == 2
    with pytest.raises(ValueError, match="metadata bound"):
        q.payload.read(path)
    with pytest.raises(ValueError, match="metadata bound"):
        q.payload.write(tmp_path / "default.json", value)
    with pytest.raises(ValueError, match="metadata bound"):
        q._write_capture("cell_index", tmp_path / "capture-0007.json", value)
    assert q.payload.MAX_NODES == 262144 and q.payload.MAX_DEPTH == 64
    assert q.payload.MAX_BLOB == 16 * 2**20 and q.shared.LIMITS["max_rss_bytes"] == 2**30


@pytest.mark.parametrize("change", ["outer", "inner", "descriptor", "identity", "shape"])
def test_capture_metadata_closed_request_shape_on_producer_and_reader(tmp_path, change):
    value = capture_metadata_request()
    if change == "outer":
        value["extra"] = None
    elif change == "inner":
        value["caller_request"]["extra"] = None
    elif change == "descriptor":
        value["caller_request"]["grid_descriptor"] = "supplied"
    elif change == "identity":
        value["identity"] = "not a digest"
    else:
        value["caller_request"]["lifecycle_state"] = []
    path = tmp_path / "capture-0006.json"
    with pytest.raises(ValueError, match="schema"):
        q._write_capture("ordinary_request", path, value)
    q.payload.write(path, value)
    with pytest.raises(ValueError, match="schema"):
        q.read_capture(path, capture_metadata_row(path))


@pytest.mark.parametrize("change", ["label", "path", "status", "hash", "fields"])
def test_capture_metadata_exact_role_path_and_hash(tmp_path, change):
    path = tmp_path / "capture-0006.json"
    q._write_capture("ordinary_request", path, capture_metadata_request())
    row = capture_metadata_row(path)
    if change == "label":
        row["label"] = "cell_index"
    elif change == "path":
        row["path"] = "capture-0007.json"
    elif change == "status":
        row["status"] = "capture_failed"
    elif change == "hash":
        row["sha256"] = "0" * 64
    else:
        row["extra"] = None
    for reader in (q.read_capture, q.capture_files):
        with pytest.raises(ValueError, match="Changed"):
            reader(path, row)
    with pytest.raises(ValueError, match="occurrence"):
        q._write_capture(
            "ordinary_request", tmp_path / "capture-0007.json", capture_metadata_request()
        )


def test_capture_metadata_over_cap_preserves_capture_failure_and_stops(tmp_path):
    evidence = q.shared.Evidence(tmp_path, sidecars=True, capture_writer=q._write_capture)
    evidence.rows.extend(dict(label="retained") for _ in range(6))
    calls = []
    value = capture_metadata_request("x" * q.payload.REQUEST_METADATA)
    result = q.shared.run_stages(
        (("ordinary_request", lambda: value), ("cell_index", lambda: calls.append("caller"))),
        evidence,
        NS(phase=None, count=0, failure=None),
    )
    assert result["failed_stage"] == "ordinary_request:capture"
    assert result["source_error"] is None and result["accepted_cases"] == 0
    assert evidence.rows[-1]["status"] == "capture_failed" and calls == []
    assert "Evidence metadata bound" in json.dumps(evidence.rows[-1])
    assert not (tmp_path / "capture-0006.json").exists()


@pytest.mark.parametrize("change", ["replacement", "growth"])
def test_capture_metadata_hashes_the_actual_bounded_read(tmp_path, monkeypatch, change):
    path = tmp_path / "capture-0006.json"
    q._write_capture("ordinary_request", path, capture_metadata_request())
    row = capture_metadata_row(path)
    raw = path.read_bytes()
    replacement = raw.replace(b"aaaaaaaa", b"cccccccc", 1)
    assert hashlib.sha256(replacement).hexdigest() != row["sha256"]
    original, sizes = Path.open, []

    class Stream(io.BytesIO):
        def read(self, size=-1):
            sizes.append(size)
            return super().read(size)

    def changed(self, *args, **kwargs):
        if self == path:
            return Stream(
                replacement if change == "replacement" else b" " * (q.payload.REQUEST_METADATA + 1)
            )
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", changed)
    with pytest.raises(ValueError, match="Changed|metadata bound"):
        q.read_capture(path, row)
    assert sizes == [q.payload.REQUEST_METADATA + 1]


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}'])
def test_capture_metadata_rejects_ambiguous_json(tmp_path, text):
    path = tmp_path / "capture-0006.json"
    path.write_text(text)
    with pytest.raises(ValueError, match="Duplicate|Nonstandard"):
        q.read_capture(path, capture_metadata_row(path))


@pytest.mark.parametrize("encoding", ["utf-16", "utf-8-sig"])
@pytest.mark.parametrize("limit", [q.payload.MAX_METADATA, q.payload.REQUEST_METADATA])
def test_capture_metadata_retains_utf8_without_bom_contract(tmp_path, encoding, limit):
    path = tmp_path / "capture-0006.json"
    q._write_capture("ordinary_request", path, capture_metadata_request())
    path.write_bytes(path.read_text().encode(encoding))
    with pytest.raises(ValueError):
        q.payload.read(path, metadata_bytes=limit)


def test_capture_metadata_exception_cannot_read_plain_legacy_or_arbitrary_cap(tmp_path):
    path = tmp_path / "capture-0006.json"
    q.shared.write(path, capture_metadata_request())
    with pytest.raises(ValueError, match="envelope"):
        q.read_capture(path, capture_metadata_row(path))
    for limit in (True, 24.0 * 2**20, 32 * 2**20):
        with pytest.raises(ValueError, match="Unsupported"):
            q.payload.read(path, metadata_bytes=limit)


@pytest.mark.parametrize("policy", [None, {"request_metadata_bytes": 32 * 2**20}])
def test_capture_metadata_plan_cannot_drop_or_widen_policy(tmp_path, monkeypatch, policy):
    plan = dict(
        kind=q.KINDS[0],
        purpose=q.PURPOSE,
        cases=list(q.CASES),
        configuration=q.configuration(),
        fixture_controls=q.CONTROLS,
        limits=q.shared.LIMITS,
        stop_after=q.ENDPOINT,
        execution_stages=list(q.STAGES),
        ordinary_methods=list(q.native.METHODS),
        capture_transport=q.payload.KIND,
        capture_policy=q.CAPTURE_POLICY,
        authority_timing_policy=q.AUTHORITY_TIMING_POLICY,
        source_review_required_before_release=True,
        automatic_retry=False,
        cpu=3,
        snapshot_sha256="a" * 64,
        runner_sha256="a" * 64,
        external_inputs=[],
        **q.shared.NO_CREDIT,
    )
    snapshots = []
    monkeypatch.setattr(q.shared, "output_path", lambda p: p)
    monkeypatch.setattr(q.source_snapshot, "digest", lambda p: "a" * 64)
    monkeypatch.setattr(q.shared, "read", lambda p: plan)
    monkeypatch.setattr(q.source_snapshot, "verify", lambda *a, **k: snapshots.append("verified"))
    monkeypatch.setattr(q.shared, "verify_pins", lambda p: None)
    monkeypatch.setattr(q, "_native_inputs", lambda p: {})
    assert q.verify_plan(tmp_path, "a" * 64) == plan
    assert snapshots == ["verified"]
    plan["capture_policy"] = policy
    with pytest.raises(ValueError, match="widened"):
        q.verify_plan(tmp_path, "a" * 64)
    assert snapshots == ["verified"]


@pytest.mark.parametrize("wall_seconds", [480, 1800])
def test_diagnostic_wall_allowance_changes_only_time(wall_seconds):
    original = dict(q.shared.LIMITS)
    limits = q._diagnostic_limits(wall_seconds)
    assert limits == dict(original, timeout=wall_seconds)
    assert limits is not q.shared.LIMITS and q.shared.LIMITS == original
    assert q.prepare.__kwdefaults__["wall_seconds"] == 480


@pytest.mark.parametrize("wall_seconds", [None, True, 480.0, 0, 60, 481, 1801, 3600])
def test_diagnostic_wall_allowance_refuses_unknown_budget(wall_seconds):
    with pytest.raises(ValueError, match="diagnostic wall allowance"):
        q._diagnostic_limits(wall_seconds)


@pytest.mark.parametrize(
    "field,value", [("timeout", 3600), ("max_rss_bytes", 2**31), ("min_available_bytes", 0)]
)
def test_diagnostic_wall_plan_preserves_all_other_resource_guards(
    tmp_path, monkeypatch, field, value
):
    plan = dict(
        kind=q.KINDS[0],
        purpose=q.PURPOSE,
        cases=list(q.CASES),
        configuration=q.configuration(),
        fixture_controls=q.CONTROLS,
        limits=q._diagnostic_limits(1800),
        stop_after=q.ENDPOINT,
        execution_stages=list(q.STAGES),
        ordinary_methods=list(q.native.METHODS),
        capture_transport=q.payload.KIND,
        capture_policy=q.CAPTURE_POLICY,
        authority_timing_policy=q.AUTHORITY_TIMING_POLICY,
        source_review_required_before_release=True,
        automatic_retry=False,
        cpu=3,
        snapshot_sha256="a" * 64,
        runner_sha256="a" * 64,
        external_inputs=[],
        **q.shared.NO_CREDIT,
    )
    verified = []
    monkeypatch.setattr(q.shared, "output_path", lambda p: p)
    monkeypatch.setattr(q.source_snapshot, "digest", lambda p: "a" * 64)
    monkeypatch.setattr(q.shared, "read", lambda p: plan)
    monkeypatch.setattr(q.source_snapshot, "verify", lambda *a, **k: verified.append("snapshot"))
    monkeypatch.setattr(q.shared, "verify_pins", lambda p: None)
    monkeypatch.setattr(q, "_native_inputs", lambda p: {})
    assert q.verify_plan(tmp_path, "a" * 64) is plan
    assert verified == ["snapshot"]
    plan["limits"][field] = value
    with pytest.raises(ValueError, match="allowance|widened"):
        q.verify_plan(tmp_path, "a" * 64)
    assert verified == ["snapshot"]


@pytest.mark.parametrize("after_output_creation", [False, True])
def test_diagnostic_supervisor_retains_early_and_late_controller_failure(
    tmp_path, monkeypatch, after_output_creation
):
    output = tmp_path / "diagnostic"
    primary = OSError("controller failure")
    cause = ValueError("original cause")

    def fail(*args):
        if after_output_creation:
            output.mkdir()
            (output / "earlier-evidence.txt").write_text("unchanged")
        raise primary from cause

    monkeypatch.setattr(q.shared, "execution_output", lambda path, *a: path)
    monkeypatch.setattr(q, "verify_plan", lambda *a: {"runtime_paths": []})
    monkeypatch.setattr(q, "launch", fail)
    with pytest.raises(OSError) as caught:
        q.supervised_launch(tmp_path / "prepared", "a" * 64, "release", q.CASES[0], output)
    assert caught.value is primary and primary.__cause__ is cause
    saved = q.shared.read(output / "controller-failure.json")
    assert saved["status"] == "failed" and saved["stage"] == "controller"
    graph = saved["failure"]
    node = graph["nodes"][graph["root"]]
    assert node["message"] == str(primary) and node["type"].endswith("OSError")
    assert graph["nodes"][node["cause"]]["message"] == str(cause)
    assert saved["automatic_retry"] is False
    if after_output_creation:
        assert (output / "earlier-evidence.txt").read_text() == "unchanged"


def test_diagnostic_supervisor_preserves_success_and_refuses_existing_output(tmp_path, monkeypatch):
    output = tmp_path / "diagnostic"
    result = {"status": "completed_unqualified"}
    entered = []

    def complete(*args):
        entered.append(True)
        output.mkdir()
        q.shared.write(output / "result.json", result)
        return result

    monkeypatch.setattr(q.shared, "execution_output", lambda path, *a: path)
    monkeypatch.setattr(q, "verify_plan", lambda *a: {"runtime_paths": []})
    monkeypatch.setattr(q, "launch", complete)
    args = (tmp_path / "prepared", "a" * 64, "release", q.CASES[0], output)
    assert q.supervised_launch(*args) is result
    before = (output / "result.json").read_bytes()
    with pytest.raises(ValueError, match="fresh supervised"):
        q.supervised_launch(*args)
    assert entered == [True] and (output / "result.json").read_bytes() == before
    assert not (output / "controller-failure.json").exists()


@pytest.mark.parametrize("target", ["safe", "overlay_child", "overlay_parent", "prepared"])
def test_diagnostic_supervisor_real_output_domain_precedes_failure_writer(
    tmp_path, monkeypatch, target
):
    prepared = tmp_path / "prepared"
    overlay = tmp_path / "runtime" / "overlay"
    prepared.mkdir()
    overlay.mkdir(parents=True)
    output = {
        "safe": tmp_path / "run",
        "overlay_child": overlay / "new-child",
        "overlay_parent": overlay.parent,
        "prepared": prepared / "new-child",
    }[target]
    calls = []
    primary = OSError("startup failure")

    def fail(*args):
        calls.append(args)
        raise primary

    monkeypatch.setattr(q.shared, "BASE", tmp_path)
    monkeypatch.setattr(q.shared, "NATIVE", tmp_path / "native")
    monkeypatch.setattr(q, "verify_plan", lambda *a: {"runtime_paths": [str(overlay)]})
    monkeypatch.setattr(q, "launch", fail)
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    if target == "safe":
        with pytest.raises(OSError) as caught:
            q.supervised_launch(prepared, "a" * 64, "release", q.CASES[0], output)
        assert caught.value is primary and len(calls) == 1
        assert q.shared.read(output / "controller-failure.json")["stage"] == "controller"
    else:
        with pytest.raises(ValueError, match="overlaps"):
            q.supervised_launch(prepared, "a" * 64, "release", q.CASES[0], output)
        assert not calls
        assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == before


@pytest.mark.parametrize("failed_capture", ["mkdir", "encode", "write"])
def test_diagnostic_supervisor_secondary_capture_never_replaces_primary(
    tmp_path, monkeypatch, failed_capture
):
    output = tmp_path / "run"
    primary, cause, secondary = OSError("primary"), ValueError("cause"), RuntimeError("capture")

    def fail(*args):
        raise primary from cause

    def capture(*args, **kwargs):
        raise secondary

    monkeypatch.setattr(q.shared, "BASE", tmp_path)
    monkeypatch.setattr(q.shared, "NATIVE", tmp_path / "native")
    monkeypatch.setattr(q, "verify_plan", lambda *a: {"runtime_paths": []})
    monkeypatch.setattr(q, "launch", fail)
    if failed_capture == "mkdir":
        original = type(output).mkdir

        def mkdir(path, *args, **kwargs):
            return capture() if path == output else original(path, *args, **kwargs)

        monkeypatch.setattr(type(output), "mkdir", mkdir)
    elif failed_capture == "encode":
        monkeypatch.setattr(q.shared, "exception_record", capture)
    else:
        original_write = q.shared.write

        def write(path, value):
            return (
                capture()
                if path == output / "controller-failure.json"
                else original_write(path, value)
            )

        monkeypatch.setattr(q.shared, "write", write)
    with pytest.raises(OSError) as caught:
        q.supervised_launch(tmp_path / "prepared", "a" * 64, "release", q.CASES[0], output)
    assert caught.value is primary and primary.__cause__ is cause
    assert primary.controller_capture_error is secondary
    assert primary.__notes__ == ["Controller failure evidence could not be saved."]


def chain(fail=None):
    calls, seen = [], {}
    initial_request, clip_request, life_request = object(), object(), object()
    initial_state = NS(status="source_completed_unqualified")
    clip_state = NS(status="source_clipped_rebuilt_unqualified")
    life_state = NS(status="source_lifecycle_completed_unqualified")
    ordinary = NS(caller_request=object())
    caller = NS(trial=NS(source_completed=True))
    env_request = object()
    environment = NS(trial=NS(source_completed=True))

    def call(name, result):
        def action(*args, **kwargs):
            calls.append(name)
            seen[name] = (args, kwargs)
            if fail == name:
                raise ValueError("original " + name)
            return result

        return action

    def forbidden(*a, **k):
        raise AssertionError("Legacy scalar-only caller request forbidden")

    raw = dict(lifecycle_case=q.CASES[0], native_option_recipe=None, controls=q.CONTROLS)
    modules = dict(
        fixtures=NS(declaration=call("fixture", (initial_request, raw))),
        initial=NS(prepare=call("initial", initial_state)),
        clipped=NS(
            from_initial_mesh=call("clip_request", clip_request), prepare=call("clip", clip_state)
        ),
        lifecycle=NS(
            from_clipped=call("lifecycle_request", life_request),
            prepare=call("lifecycle", life_state),
        ),
        multi=NS(from_lifecycle=forbidden, prepare=call("caller", caller)),
        environment=NS(
            LAW_ID="synthetic ordinary",
            from_lifecycle=call("ordinary_request", ordinary),
            from_caller=call("continuation_request", env_request),
            prepare_continuation=call("ordinary", environment),
        ),
    )
    return (
        modules,
        calls,
        seen,
        NS(life=life_state, request=ordinary, caller=caller, env=environment),
    )


def test_fresh_descriptor_request_precedes_actual_caller_and_same_owner_continuation(tmp_path):
    modules, calls, seen, objects = chain()
    steps = q._pipeline(q.CASES[0], tmp_path, **modules)
    results = [action() for _, action in steps]
    assert [name for name, _ in steps] == list(q.STAGES)
    assert calls == [
        "fixture",
        "initial",
        "clip_request",
        "clip",
        "lifecycle_request",
        "lifecycle",
        "ordinary_request",
        "caller",
        "continuation_request",
        "ordinary",
    ]
    assert results[0]["configuration"] == q.configuration()
    assert seen["ordinary_request"][0][1] is objects.life
    assert seen["ordinary_request"][0][2] == q.configuration()
    assert seen["caller"][0] == (objects.request.caller_request,)
    assert seen["continuation_request"][0] == (objects.caller,)
    assert results[-1] is objects.env.trial


@pytest.mark.parametrize(
    "stage", ["initial", "clip", "lifecycle", "ordinary_request", "caller", "ordinary"]
)
def test_original_stage_refusal_stops_without_later_delegate(tmp_path, stage):
    modules, calls, _, _ = chain(stage)
    for _, action in q._pipeline(q.CASES[0], tmp_path, **modules):
        try:
            action()
        except ValueError as error:
            assert str(error) == "original " + stage
            break
    else:
        raise AssertionError("Expected source refusal")
    assert calls[-1] == stage and calls.count(stage) == 1


@pytest.mark.parametrize("which", ["caller", "env"])
def test_partial_trial_never_becomes_completed(tmp_path, which):
    modules, calls, _, objects = chain()
    getattr(objects, which).trial.source_completed = False
    with pytest.raises(q.prior.PrerequisiteRejected) as caught:
        for _, action in q._pipeline(q.CASES[0], tmp_path, **modules):
            action()
    assert caught.value.trial is getattr(objects, which).trial
    assert calls[-1] == ("caller" if which == "caller" else "ordinary")


def test_failed_capture_stops_before_next_source_and_keeps_completed_work():
    calls = []
    evidence = NS(rows=[], save=lambda label, value: False, failure=lambda error: None)
    work = NS(phase=None, count=1, failure=None)
    result = q.shared.run_stages(
        (("first", lambda: calls.append("first")), ("second", lambda: calls.append("second"))),
        evidence,
        work,
    )
    assert calls == ["first"] and result["failed_stage"] == "first:capture"
    assert result["source_error"] is None and result["accepted_cases"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("stop_after", "lapENV_P_inv"),
        ("allow_actual_source_diagnostic", False),
        ("scientific_qualification", True),
        ("kind", q.prior.KINDS[1]),
    ],
)
def test_release_cannot_widen_endpoint_or_reuse_legacy_grant(monkeypatch, field, value):
    plan = dict(cpu=6, snapshot_sha256="a" * 64)
    grant = dict(
        kind=q.KINDS[1],
        plan_sha256="b" * 64,
        snapshot_sha256="a" * 64,
        case=q.CASES[0],
        stop_after=q.ENDPOINT,
        allow_actual_source_diagnostic=True,
        scientific_qualification=False,
        source_review=dict(path="/no/source", sha256="c" * 64),
    )
    grant[field] = value
    monkeypatch.setattr(q, "verify_plan", lambda *a: plan)
    monkeypatch.setattr(q.shared, "read", lambda p: grant)
    monkeypatch.setattr(
        q.shared, "verify_pins", lambda p: (_ for _ in ()).throw(AssertionError("No file reads"))
    )
    with pytest.raises(ValueError, match="release"):
        q.verify_release("unused", "b" * 64, "unused", q.CASES[0])


def test_default_grid_and_method_sequence_are_not_postcut_or_poisson():
    assert q.configuration()["general options"] == {"comp grid size": 25}
    assert q.native.METHODS == (
        "cellVerts",
        "cellMatrices",
        "cell_vols",
        "mem_processing",
        "near_neigh",
        "makeECM",
        "environment",
        "assign_grid_len",
        "make_maskM",
    )
    assert "intra_updater" not in q.native.METHODS
    assert q.shared.LIMITS == dict(timeout=480, max_rss_bytes=2**30, min_available_bytes=8 * 2**30)


def repair_c5_worker(tmp_path, monkeypatch, where, source_kind="complete"):
    from validation.betse import native_multi_cell_environment_compare as comparator

    source = tmp_path / "prepared/source"
    source.mkdir(parents=True)
    output = tmp_path / "output"
    output.mkdir()
    rows = [
        dict(label=stage, path=f"capture-{i:04d}.json", status="saved", sha256="a" * 64)
        for i, stage in enumerate(q.STAGES)
    ]
    baseline = dict(
        status="source_completed_unqualified",
        completed_stages=list(q.STAGES),
        failed_stage=None,
        source_error=None,
        observer_error=None,
        interrupted_exception_graph=None,
        captures=copy.deepcopy(rows),
        observed_source_entry_attempts=9,
        accepted_cases=0,
        **q.shared.NO_CREDIT,
    )
    if source_kind != "complete":
        baseline.update(
            status="diagnostic_failed",
            failed_stage="cell_index",
            completed_stages=list(q.STAGES[:7]),
        )
        error = ValueError("original source failure")
        error.__cause__ = RuntimeError("original source cause")
        graph = q.shared.exception_record(error)
        if source_kind == "source":
            baseline["source_error"] = graph
        else:
            baseline["observer_error"] = graph
            baseline["interrupted_exception_graph"] = graph

    class Evidence:
        def __init__(self, *a, **k):
            self.rows = copy.deepcopy(rows)

        def failure(self, error):
            self.rows.append(dict(label="metadata_failure_capture", status="saved"))
            if where == "runtime_capture":
                raise OSError("secondary failure recording")

    class Work:
        def __init__(self, *a, **k):
            self.phase = q.STAGES[-1]
            self.count = 9
            self.failure = None

        def active(self):
            return nullcontext()

    plan = dict(
        interpreter=str(Path(q.sys.executable).absolute()),
        runtime_paths=[],
        authority_timing_policy=q._authority_policy(True),
    )
    monkeypatch.setattr(q, "ROOT", source)
    monkeypatch.setattr(q, "verify_release", lambda *a: plan)
    monkeypatch.setattr(q.resource, "setrlimit", lambda *a: None)
    monkeypatch.setattr(q.shared, "execution_output", lambda *a: output)
    monkeypatch.setattr(q.shared, "Evidence", Evidence)
    monkeypatch.setattr(q.shared, "WorkLog", Work)
    monkeypatch.setattr(q, "_steps", lambda *a: ())

    def stages(*args):
        if where == "source_execution":
            raise ValueError("source execution exception") from RuntimeError(
                "source execution cause"
            )
        return copy.deepcopy(baseline)

    monkeypatch.setattr(q.shared, "run_stages", stages)
    namespace = {"stages": stages}
    monkeypatch.setattr(
        q, "_authority_targets", lambda: (("synthetic.stages", namespace, "stages"),)
    )
    monkeypatch.setattr(q.payload, "read", lambda *a: dict(cache={"synthetic": "cache"}))

    def domain(*args):
        if where == "diagnostics":
            raise OSError("post-source diagnostics failure")
        return dict(domain_gate_passed=False)

    monkeypatch.setattr(comparator, "diagnostics_from_cache", domain)

    def runtime(*args):
        if where.startswith("runtime"):
            raise OSError("post-source runtime failure")
        return {}

    monkeypatch.setattr(q.shared, "runtime_inventory", runtime)

    def verify(*args):
        if where == "pins":
            raise OSError("post-source pin failure")
        return plan

    monkeypatch.setattr(q, "verify_plan", verify)
    return source.parent, output, baseline


@pytest.mark.parametrize(
    "where,stage",
    [
        ("diagnostics", "postprocessing.saved_geometry_diagnostics"),
        ("runtime", "postprocessing.runtime_inventory"),
        ("pins", "postprocessing.end_pin_verification"),
    ],
)
def test_repair_c5_postprocessing_failure_preserves_completed_source_and_zero_credit(
    tmp_path, monkeypatch, where, stage
):
    prepared, output, baseline = repair_c5_worker(tmp_path, monkeypatch, where)
    assert q.worker(prepared, "synthetic_plan", "synthetic_release", q.CASES[0], output) == 1
    result = q.shared.read(output / "diagnostic.json")
    assert result["status"] == "diagnostic_failed" and result["accepted_cases"] == 0
    assert result["source_error"] is None and result["observer_error"] is None
    assert result["completed_stages"] == list(q.STAGES) and result["failed_stage"] == stage
    assert result["postprocessing_stage"] == stage and result["postprocessing_error"]["nodes"]
    assert result["prior_result"]["status"] == "source_completed_unqualified"
    assert result["prior_result"]["captures"] == baseline["captures"]
    assert len(result["captures"]) == len(baseline["captures"]) + 1


@pytest.mark.parametrize("source_kind", ["source", "observer"])
def test_repair_c5_metadata_failure_never_erases_an_existing_primary(
    tmp_path, monkeypatch, source_kind
):
    prepared, output, baseline = repair_c5_worker(tmp_path, monkeypatch, "runtime", source_kind)
    assert q.worker(prepared, "synthetic_plan", "synthetic_release", q.CASES[0], output) == 1
    result = q.shared.read(output / "diagnostic.json")
    for field in (
        "source_error",
        "observer_error",
        "interrupted_exception_graph",
        "completed_stages",
        "failed_stage",
    ):
        assert result[field] == baseline[field]
    assert result["postprocessing_stage"] == "postprocessing.runtime_inventory"
    assert (
        result["postprocessing_error"] is not None
        and result["prior_result"]["status"] == "diagnostic_failed"
    )


def test_repair_c5_secondary_failure_recording_has_separate_error(tmp_path, monkeypatch):
    prepared, output, baseline = repair_c5_worker(
        tmp_path, monkeypatch, "runtime_capture", "source"
    )
    assert q.worker(prepared, "synthetic_plan", "synthetic_release", q.CASES[0], output) == 1
    result = q.shared.read(output / "diagnostic.json")
    assert result["source_error"] == baseline["source_error"]
    assert (
        result["postprocessing_error"] is not None and result["failure_capture_error"] is not None
    )


def test_repair_c5_actual_source_exception_stays_a_source_error(tmp_path, monkeypatch):
    prepared, output, _ = repair_c5_worker(tmp_path, monkeypatch, "source_execution")
    assert q.worker(prepared, "synthetic_plan", "synthetic_release", q.CASES[0], output) == 1
    result = q.shared.read(output / "diagnostic.json")
    assert result["source_error"]["nodes"][0]["message"] == "source execution exception"
    assert result["source_error"]["nodes"][1]["message"] == "source execution cause"
    assert "postprocessing_error" not in result


@pytest.mark.parametrize("enabled", [True, False])
def test_execution_overhead_policy_is_explicit_and_preserves_default(enabled):
    policy = q._authority_policy(enabled)
    assert q._authority_enabled(policy) is enabled
    assert q.prepare.__kwdefaults__["authority_timing"] is True
    assert q._authority_policy(enabled) is not policy
    if not enabled:
        assert policy == dict(
            kind="cells.authority_timing_disabled@1",
            source_work_log=True,
            stage_timings=True,
            scientific_guards="unchanged",
        )
    assert q.shared.LIMITS == dict(timeout=480, max_rss_bytes=2**30, min_available_bytes=8 * 2**30)


@pytest.mark.parametrize("value", [None, 0, 1, "false", {}, []])
def test_execution_overhead_requires_exact_boolean_declaration(value):
    with pytest.raises(ValueError, match="profiling is enabled"):
        q._authority_policy(value)


@pytest.mark.parametrize(
    "policy",
    [
        None,
        {},
        dict(q.AUTHORITY_TIMING_DISABLED_POLICY, source_work_log=False),
        dict(q.AUTHORITY_TIMING_DISABLED_POLICY, stage_timings=False),
        dict(q.AUTHORITY_TIMING_DISABLED_POLICY, scientific_guards="disabled"),
        dict(q.AUTHORITY_TIMING_DISABLED_POLICY, undeclared=True),
        dict(q.AUTHORITY_TIMING_POLICY, max_raw_errors=64),
    ],
)
def test_execution_overhead_plan_rejects_missing_or_widened_policy(tmp_path, monkeypatch, policy):
    plan = dict(
        kind=q.KINDS[0],
        purpose=q.PURPOSE,
        cases=list(q.CASES),
        configuration=q.configuration(),
        fixture_controls=q.CONTROLS,
        limits=q.shared.LIMITS,
        stop_after=q.ENDPOINT,
        execution_stages=list(q.STAGES),
        ordinary_methods=list(q.native.METHODS),
        capture_transport=q.payload.KIND,
        capture_policy=q.CAPTURE_POLICY,
        authority_timing_policy=q._authority_policy(False),
        source_review_required_before_release=True,
        automatic_retry=False,
        cpu=3,
        snapshot_sha256="a" * 64,
        runner_sha256="a" * 64,
        external_inputs=[],
        **q.shared.NO_CREDIT,
    )
    verified = []
    monkeypatch.setattr(q.shared, "output_path", lambda p: p)
    monkeypatch.setattr(q.source_snapshot, "digest", lambda p: "a" * 64)
    monkeypatch.setattr(q.shared, "read", lambda p: plan)
    monkeypatch.setattr(q.source_snapshot, "verify", lambda *a, **k: verified.append("snapshot"))
    monkeypatch.setattr(q.shared, "verify_pins", lambda p: None)
    monkeypatch.setattr(q, "_native_inputs", lambda p: {})
    assert q.verify_plan(tmp_path, "a" * 64) is plan
    plan["authority_timing_policy"] = policy
    with pytest.raises(ValueError, match="authority timing policy"):
        q.verify_plan(tmp_path, "a" * 64)
    assert verified == ["snapshot"]


@pytest.mark.parametrize("fault", ["none", "source", "capture", "inherited_guard"])
def test_execution_overhead_disabled_retains_real_work_and_stage_accounting(
    tmp_path, monkeypatch, fault
):
    """Real recorder and stage controller; only declared metadata actions run."""
    from types import FunctionType

    work_type, run_stages = q.shared.WorkLog, q.shared.run_stages
    prepared, output, _ = repair_c5_worker(tmp_path, monkeypatch, "none")
    plan = q.verify_release(None, None, None, None)
    plan["authority_timing_policy"] = q._authority_policy(False)
    delegates, failures, hook_samples = [], [], []
    primary = ValueError("metadata action source failure")
    primary.__cause__ = RuntimeError("metadata action cause")

    def action():
        delegates.append("first")
        if fault == "source":
            raise primary
        return ("declared synthetic metadata", 7)

    action = FunctionType(
        action.__code__.replace(
            co_filename=str(prepared / "source/validation/betse/declared_metadata.py")
        ),
        action.__globals__,
        closure=action.__closure__,
    )

    def later():
        delegates.append("later")
        return ("second metadata action", 8)

    class Evidence:
        def __init__(self, *args, **kwargs):
            self.rows = []

        def save(self, label, value):
            hook_samples.append((sys.getprofile() is not None, sys.gettrace() is trace))
            self.rows.append(dict(label=label, path="synthetic-capture.json", status="saved"))
            return fault != "capture"

        def failure(self, error):
            failures.append(error)

    def forbidden(*args, **kwargs):
        raise AssertionError("Disabled optional profiler must not be initialized")

    previous, trace = sys.getprofile(), sys.gettrace()
    entries = []

    def inherited(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code is action.__code__:
            entries.append("action")
            if fault == "inherited_guard":
                raise primary

    monkeypatch.setattr(q.shared, "WorkLog", work_type)
    monkeypatch.setattr(q.shared, "run_stages", run_stages)
    monkeypatch.setattr(q.shared, "Evidence", Evidence)
    monkeypatch.setattr(q, "AuthorityTimings", forbidden)
    monkeypatch.setattr(q, "_authority_targets", forbidden)
    monkeypatch.setattr(q, "_steps", lambda *a: ((q.STAGES[0], action), (q.STAGES[1], later)))
    try:
        sys.setprofile(inherited)
        rc = q.worker(prepared, "synthetic-plan", "synthetic-release", q.CASES[0], output)
        assert sys.getprofile() is inherited and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
    result = q.shared.read(output / "diagnostic.json")
    assert rc == (fault != "none")
    assert result["authority_timing"]["enabled"] is False
    assert result["authority_timing"]["initialized"] is False
    assert result["authority_timing"]["snapshots_attempted"] == 0
    assert not (output / "authority-timings").exists()
    counts = q.shared.read(output / "work-counts.json")
    assert counts["independent_case_credit"] == result["accepted_cases"] == 0
    assert entries == ["action"]
    assert (output / "work.jsonl").is_file()
    assert list((output / "stage-timings").glob("*.json"))
    if fault == "none":
        assert delegates == ["first", "later"]
        assert result["completed_stages"] == list(q.STAGES[:2])
        assert counts["observed_entry_attempts"] > 0
    else:
        assert delegates == ([] if fault == "inherited_guard" else ["first"])
        assert result["completed_stages"] == []
    if fault in ("source", "inherited_guard"):
        assert failures == [primary] and failures[0].__cause__ is primary.__cause__
        assert result["source_error"]["nodes"][0]["message"] == str(primary)
    assert all(profile and trace_ok for profile, trace_ok in hook_samples)


def test_execution_overhead_selection_uses_only_function_names():
    selected = NS(originalname="test_execution_overhead_policy", name="x")
    excluded = NS(originalname="test_unrelated", name="execution_overhead")
    assert q._software_selection("execution-overhead", [selected, excluded]) == (
        [selected],
        [excluded],
    )
