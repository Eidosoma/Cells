"""Blocked metadata timing controls; no native constructors or actual parents."""

import ast
import builtins
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace as NS

import pytest

from validation.betse import native_multi_cell_environment_qualification as inherited
from validation.betse import native_pregeometry_validation_cost as stage


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    prior = sys.getprofile(), sys.gettrace()
    attempted = []

    def profile(frame, event, arg):
        if prior[0] is not None:
            prior[0](frame, event, arg)
        if event == "call" and frame.f_globals.get("__name__", "").startswith("betse."):
            attempted.append((frame.f_code.co_filename, frame.f_code.co_qualname))
            raise AssertionError("Actual native/source body held")

    try:
        sys.setprofile(profile)
        yield
    finally:
        sys.setprofile(prior[0])
        sys.settrace(prior[1])
        (tmp_path / "native-blocked.json").write_text(json.dumps(dict(attempted=attempted)))
        assert not attempted


def observer(tmp_path, namespace):
    targets = tuple(("metadata." + name, namespace, name) for name in namespace)
    return stage._observer(
        tmp_path, NS(phase="pregeometry-validation", failure=None, count=0), targets
    )


def rows(value):
    return [json.loads(line) for line in value.journal_path.read_text().splitlines()]


def test_cost_default_gate_precedes_foreign_path(monkeypatch):
    class Foreign:
        def __fspath__(self):
            raise AssertionError("No path access before release")

    monkeypatch.delenv(stage.RELEASE, raising=False)
    with pytest.raises(ValueError, match="held"):
        with stage.observe(Foreign()):
            pytest.fail("No model work")


def test_cost_reuses_exact_original_observer_and_bound_policy():
    assert stage._timing() is inherited
    assert sum(len(names) for _, names in stage.SITES) == 28
    assert stage.source_plan()["suggested_guard"]["wall_seconds"] == 120


def test_cost_nested_counters_and_durable_inflight_do_not_inspect_values(tmp_path):
    entries = []

    class Opaque:
        def __repr__(self):
            raise AssertionError("Scientific values must remain opaque")

    def inner(actual):
        entries.append("inner")
        return actual

    def outer(actual):
        return inner(inner(actual))

    value = observer(tmp_path, dict(outer=outer, inner=inner))
    prior = sys.getprofile(), sys.gettrace()
    try:
        with value.active():
            result = outer(Opaque())
        assert type(result) is Opaque
        assert sys.getprofile() is prior[0] and sys.gettrace() is prior[1]
        data = rows(value)
        final = data[-1]
        assert final["targets"][0]["entries"] == 1 and final["targets"][1]["entries"] == 2
        assert (
            final["targets"][0]["inclusive_wall_ns"]
            >= final["targets"][1]["inclusive_wall_ns"]
            >= 0
        )
        assert any(len(row["active_frames"]) == 2 for row in data)
        assert not final["active_frames"] and not final["return_event_is_success"]
        assert final["independent_case_credit"] == 0 and not final["inclusive_times_are_additive"]
    finally:
        os.close(value.journal_fd)


def test_cost_journal_needs_no_write_open_inside_readonly_parameter_scope(tmp_path):
    active = [False]
    refused = []

    def audit(event, args):
        if active[0] and (
            event == "os.mkdir"
            or event == "open"
            and type(args[2]) is int
            and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        ):
            refused.append(event)
            raise AssertionError("Read-only owner forbids filesystem opens/mkdir")

    def target():
        return None

    sys.addaudithook(audit)
    value = observer(tmp_path, dict(target=target))
    try:
        with value.active():
            active[0] = True
            target()
            active[0] = False
        assert not refused and rows(value)[-1]["targets"][0]["entries"] == 1
    finally:
        active[0] = False
        os.close(value.journal_fd)


def test_cost_source_error_cause_and_hooks_retained(tmp_path):
    primary, cause = ValueError("metadata target"), OSError("cause")

    def target():
        raise primary from cause

    value = observer(tmp_path, dict(target=target))
    prior = sys.getprofile(), sys.gettrace()
    try:
        with pytest.raises(ValueError) as caught:
            with value.active():
                target()
        assert caught.value is primary and primary.__cause__ is cause
        assert sys.getprofile() is prior[0] and sys.gettrace() is prior[1]
        assert rows(value)[-1]["return_event_is_success"] is False
    finally:
        os.close(value.journal_fd)


def test_cost_stop_site_is_source_callsite_not_mutable_function_identity(tmp_path):
    path = tmp_path / "metadata_dispatch.py"
    path.write_text(
        "def _execute_chain(value):\n return value\n"
        "def evaluate_live(value):\n return _execute_chain(value)\n"
    )
    namespace = {}
    exec(compile(path.read_bytes(), str(path), "exec"), namespace)
    actual = namespace["evaluate_live"]
    offsets = stage._stop_site(actual, namespace["_execute_chain"])
    called = []

    def foreign(value):
        called.append(value)
        return value

    namespace["_execute_chain"] = foreign
    prior = sys.getprofile()
    reached = []

    def stop(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        caller = frame.f_back
        if (
            event == "call"
            and caller is not None
            and caller.f_code is actual.__code__
            and caller.f_lasti in offsets
        ):
            reached.append(frame)
            raise stage.PrephaseBoundaryReached("metadata stop")

    try:
        sys.setprofile(stop)
        with pytest.raises(stage.PrephaseBoundaryReached):
            actual(object())
    finally:
        sys.setprofile(prior)
    assert reached and not called


def public_interval(tmp_path, monkeypatch, caught=False):
    path = tmp_path / "metadata_evaluate.py"
    raw = "def _execute_chain(value):\n allocated.append(value)\n return value\n"
    if caught:
        raw += (
            "def _seal_execution():\n evidence_failure()\n final_writer()\n"
            "def evaluate_live(value):\n"
            " try:\n  return _execute_chain(value)\n"
            " except BaseException as error:\n  errors.append(error)\n"
            " finally:\n  _seal_execution()\n"
            " raise ValueError('retained geometry failure') from errors[-1]\n"
        )
    else:
        raw += "def evaluate_live(value):\n return _execute_chain(value)\n"
    path.write_text(raw)
    geometry = ModuleType("metadata_geometry")
    geometry.allocated = []
    exec(compile(path.read_bytes(), str(path), "exec"), vars(geometry))
    namespace = vars(geometry)
    targets = tuple(
        ("metadata." + name, namespace, name) for name in ("evaluate_live", "_execute_chain")
    )
    monkeypatch.setattr(stage, "_sites", lambda: targets)
    proxy = NS(**dict(vars(sys), modules=dict(sys.modules, **{stage.SITES[0][0]: geometry})))
    monkeypatch.setattr(stage, "sys", proxy)
    monkeypatch.setenv(stage.RELEASE, "1")
    return geometry


def test_cost_public_interval_stops_before_phase_and_restores_both_hooks(tmp_path, monkeypatch):
    geometry = public_interval(tmp_path, monkeypatch)
    prior = sys.getprofile(), sys.gettrace()
    with pytest.raises(stage.PrephaseBoundaryReached):
        with stage.observe(tmp_path / "cost", enabled=True):
            geometry.evaluate_live(object())
    assert not geometry.allocated
    assert sys.getprofile() is prior[0] and sys.gettrace() is prior[1]
    data = [
        json.loads(line)
        for line in (tmp_path / "cost/authority-timings/events.jsonl").read_text().splitlines()
    ]
    assert any(row["reason"] == "prephase-stop" for row in data)
    assert data[-1]["targets"][1]["entries"] == 0


@pytest.mark.parametrize("with_trace", (False, True))
@pytest.mark.parametrize("inherited_refusal", (False, True))
def test_cost_caught_stop_recovers_inherited_coverage_before_final_evidence(
    tmp_path, monkeypatch, with_trace, inherited_refusal
):
    geometry = public_interval(tmp_path, monkeypatch, caught=True)
    geometry.errors = []
    before = sys.getprofile(), sys.gettrace()
    calls, profile_events, trace_events, refused = [], [], [], []
    primary, cause = LookupError("inherited entry refusal"), OSError("original cause")
    primary.__cause__ = cause

    def profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if frame.f_globals is vars(geometry):
            profile_events.append((frame.f_code.co_name, event))
            if (
                inherited_refusal
                and event == "call"
                and frame.f_code is geometry._execute_chain.__code__
            ):
                refused.append(primary)
                raise primary

    def local(frame, event, arg):
        if frame.f_globals is vars(geometry):
            trace_events.append((frame.f_code.co_name, event))
        return local

    def global_trace(frame, event, arg):
        assert event == "call"
        if frame.f_globals is vars(geometry):
            trace_events.append((frame.f_code.co_name, event))
        return local

    def failure():
        assert sys.getprofile() is profile
        assert sys.gettrace() is expected_trace
        error = geometry.errors[-1]
        if inherited_refusal:
            assert error is primary and error.__cause__ is cause
        else:
            assert type(error) is stage.PrephaseBoundaryReached
        calls.append("failure")

    def final():
        assert sys.getprofile() is profile and sys.gettrace() is expected_trace
        calls.append("final")

    geometry.evidence_failure, geometry.final_writer = failure, final
    expected_trace = global_trace if with_trace else None
    try:
        sys.setprofile(profile)
        sys.settrace(expected_trace)
        with pytest.raises(ValueError, match="retained geometry failure") as caught:
            with stage.observe(tmp_path / "cost", enabled=True) as observed:
                geometry.evaluate_live(object())
        assert sys.getprofile() is profile and sys.gettrace() is expected_trace
    finally:
        sys.settrace(before[1])
        sys.setprofile(before[0])
    assert calls == ["failure", "final"] and not geometry.allocated
    assert caught.value.__cause__ is geometry.errors[-1]
    assert observed.prephase_hook_recovery == dict(attempted=True, complete=True)
    assert ("_seal_execution", "call") in profile_events
    assert bool(refused) is inherited_refusal
    if with_trace:
        assert trace_events.count(("evaluate_live", "call")) == 1
        assert trace_events.count(("evaluate_live", "exception")) == 2
        assert ("_seal_execution", "call") in trace_events
    else:
        assert not trace_events
    software = dict(
        inherited_trace_present=with_trace,
        inherited_refusal=inherited_refusal,
        source_primary_retained=True,
        final_evidence_under_both_inherited_hooks=calls,
        phase_allocations=len(geometry.allocated),
        recovery=observed.prephase_hook_recovery,
    )
    (tmp_path / "caught-stop.json").write_text(json.dumps(software))


def test_cost_original_evaluate_and_seal_ast_retain_failed_stop_under_inherited_hooks(
    tmp_path, monkeypatch
):
    original = Path(stage.__file__).with_name("native_seed_world_geometry_qualification.py")
    names = {"QualificationRejected", "Execution", "_seal_execution", "evaluate_live"}
    nodes = [
        node
        for node in ast.parse(original.read_bytes()).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names
    ]
    assert len(nodes) == len(names)
    geometry = ModuleType("metadata_original_evaluate_and_seal")
    monkeypatch.setitem(sys.modules, geometry.__name__, geometry)
    entered, writes, errors = [], [], []
    prior = sys.getprofile(), sys.gettrace()

    def profile(frame, event, arg):
        if prior[0] is not None:
            prior[0](frame, event, arg)

    def covered():
        assert sys.getprofile() is profile and sys.gettrace() is prior[1]

    class Evidence:
        def __init__(self, directory, **kwargs):
            self.rows = []

        def failure(self, primary):
            covered()
            assert type(primary) is stage.PrephaseBoundaryReached
            errors.append(primary)

    def writer(path, value):
        covered()
        writes.append(path)
        path.write_text(json.dumps(value))

    def imports(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "validation.betse.native_single_cell_prefix_qualification":
            return NS(Evidence=Evidence)
        return builtins.__import__(name, globals, locals, fromlist, level)

    def chain(*args):
        entered.append(args)
        raise AssertionError("Actual phase preparation remains held")

    geometry.__dict__.update(
        __builtins__=dict(vars(builtins), __import__=imports),
        dataclass=dataclass,
        field=field,
        Path=Path,
        _released=lambda enabled: None,
        _evidence_writer=lambda profile: None,
        _dependencies=lambda: (None, {"callbacks": NS(_validate=lambda value: None)}),
        _resources=lambda: None,
        _execute_chain=chain,
        snapshot=NS(write_json=writer),
    )
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(original), "exec"), vars(geometry))
    targets = tuple(
        ("metadata.original." + name, vars(geometry), name)
        for name in ("evaluate_live", "_execute_chain")
    )
    monkeypatch.setattr(stage, "_sites", lambda: targets)
    monkeypatch.setattr(stage, "sys", NS(**dict(vars(sys), modules={stage.SITES[0][0]: geometry})))
    monkeypatch.setenv(stage.RELEASE, "1")
    directory = tmp_path / "geometry"
    try:
        sys.setprofile(profile)
        with pytest.raises(geometry.QualificationRejected) as caught:
            with stage.observe(tmp_path / "cost", enabled=True) as observation:
                geometry.evaluate_live(NS(parameters=object()), object(), directory, enabled=True)
        covered()
    finally:
        sys.settrace(prior[1])
        sys.setprofile(prior[0])
    assert not entered and len(errors) == len(writes) == 1
    assert caught.value.__cause__ is caught.value.partial.primary is errors[0]
    assert caught.value.partial.metadata_error is errors[0]
    assert not caught.value.partial.capture_errors
    outcome = json.loads((directory / "outcome.json").read_text())
    assert outcome["status"] == "failed" and not outcome["source_completed"]
    assert outcome["api_operations"] == outcome["actual_inputs"] == 0
    assert observation.prephase_hook_recovery == dict(attempted=True, complete=True)
    (tmp_path / "literal-caught-stop.json").write_text(
        json.dumps(
            dict(
                copied_original_definitions=sorted(names),
                source=str(original),
                failed_outcome_retained=True,
                phase_entries=0,
                actual_world_or_native_authority=False,
            )
        )
    )


@pytest.mark.parametrize("source_fails", [False, True])
def test_cost_outer_close_failure_retains_source_or_refuses_completion(
    tmp_path, monkeypatch, source_fails
):
    public_interval(tmp_path, monkeypatch)
    close, descriptors = os.close, []
    secondary, primary, cause = OSError("close"), ValueError("source"), TypeError("cause")

    def refuse(fd):
        descriptors.append(fd)
        raise secondary

    monkeypatch.setattr(stage, "os", NS(**dict(vars(os), close=refuse)))
    prior = sys.getprofile(), sys.gettrace()
    with pytest.raises(ValueError if source_fails else RuntimeError) as caught:
        with stage.observe(tmp_path / "cost", enabled=True) as observation:
            if source_fails:
                raise primary from cause
    try:
        if source_fails:
            assert caught.value is primary and primary.__cause__ is cause
        else:
            assert caught.value.__cause__ is secondary
        assert observation.pending_cleanup_errors[-1] == ("outer_journal_close", secondary)
        assert sys.getprofile() is prior[0] and sys.gettrace() is prior[1]
    finally:
        for fd in descriptors:
            close(fd)
