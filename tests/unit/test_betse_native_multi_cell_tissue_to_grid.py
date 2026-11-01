"""Native-blocked probes on an actually issued synthetic multi API chain."""

import ast
import hashlib
import json
import os
import runpy
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_multi_cell_tissue_to_grid as stage
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

HELPER = Path(__file__).with_name("test_betse_native_multi_cell_world_finalization.py")
helpers = SimpleNamespace(**runpy.run_path(str(HELPER)))
_FIXTURE_LOG_ERRORS = []


def _fixture_error_record(error):
    seen = {}

    def record(value, depth=0):
        if value is None:
            return None
        if id(value) in seen:
            return dict(ref=seen[id(value)])
        if depth > 12:
            return dict(truncated_exception_chain=True, type=type(value).__name__)
        token = len(seen)
        seen[id(value)] = token
        frames, tb = [], value.__traceback__
        while tb is not None and len(frames) < 64:
            frames.append(
                dict(
                    file=tb.tb_frame.f_code.co_filename,
                    function=tb.tb_frame.f_code.co_qualname,
                    line=tb.tb_lineno,
                )
            )
            tb = tb.tb_next
        attrs = vars(value)
        partial = attrs.get("partial")
        trial = attrs.get("trial")
        return dict(
            token=token,
            type=type(value).__module__ + "." + type(value).__qualname__,
            arguments=[
                arg if type(arg) in (str, int, bool, type(None)) else type(arg).__name__
                for arg in value.args
            ],
            frames=frames,
            more_frames=tb is not None,
            source=record(attrs.get("source_error"), depth + 1),
            capture=record(attrs.get("capture_error"), depth + 1),
            cause=record(value.__cause__, depth + 1),
            context=record(value.__context__, depth + 1),
            partial_keys=sorted(partial) if type(partial) is dict else None,
            trial_identity=vars(trial).get("identity") if hasattr(trial, "__dict__") else None,
            complete_failed_live_owner_serialization=False,
        )

    return record(error)


def _environment_facade(environment, continuation):
    # The reused fixture replaces _METHODS after this facade is created. Keep
    # its method/template reads attached to that live module, not an old dict.
    class Facade:
        def __getattr__(self, name):
            if name == "prepare_continuation":
                return continuation
            return getattr(environment, name)

    return Facade()


def _fixture_verified_sources():
    # Keep the full original file proof before upstream software fixtures install
    # their descriptive, non-file labels. Production pin validation stays live.
    pins = stage._verify_sources()

    def verify():
        return stage._verify_pin_bytes(pins)

    return verify


def _fixture_progress(stage_name, error=None):
    if not (folder := os.environ.get("CELLS_MAPPING_EVIDENCE")):
        return
    try:
        path = Path(folder).parent / "parent-setup.jsonl"
        with path.open("a") as stream:
            stream.write(
                json.dumps(
                    dict(
                        stage=stage_name,
                        monotonic_seconds=time.monotonic(),
                        process_cpu_seconds=time.process_time(),
                        error=None
                        if error is None
                        else dict(type=type(error).__name__, message=str(error)),
                        native_or_scientific_credit=0,
                    ),
                    sort_keys=True,
                )
                + "\n"
            )
            stream.flush()
        if error is not None:
            with (path.parent / "parent-failure.json").open("x") as stream:
                json.dump(_fixture_error_record(error), stream, indent=2, sort_keys=True)
                stream.write("\n")
    except Exception as capture:
        _FIXTURE_LOG_ERRORS.append(capture)


def _fixture_templates(patch):
    """Compile only existing synthetic templates, never their throwaway owners.

    issued_multi_chain uses fixture() solely to fetch these function templates.
    Its actual caller -> environment -> Poisson -> tail APIs still issue the
    retained chain. No registry, cache, owner, parameter or guard is supplied.
    """
    poisson = stage.world.poisson
    path = HELPER.with_name("test_betse_native_multi_cell_poisson.py")
    body = next(
        n
        for n in ast.parse(path.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "harness"
    ).body
    selected = [
        n
        for n in body
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name)
        and n.value.func.id == "exec"
        and any(
            isinstance(c, ast.Constant) and c.value == "<synthetic-poisson>" for c in ast.walk(n)
        )
    ]
    assert len(selected) == 1
    values = dict(poisson.source.__dict__)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), {"values": values})
    patch.setattr(poisson, "_CALLER", {n: values[n] for n in poisson.METHODS})
    patch.setattr(poisson, "_LAPLACIAN", values["synthetic_operator"])

    body = next(
        n
        for n in ast.parse(HELPER.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "fixture"
    ).body
    selected = [
        n
        for n in body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id in {"statements", "text"} for t in n.targets)
        or isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name)
        and n.value.func.id == "exec"
        and any(
            isinstance(c, ast.Constant) and c.value == "<synthetic-world-tail>" for c in ast.walk(n)
        )
    ]
    assert len(selected) == 3
    namespace = dict(stage.world.source.__dict__)
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(HELPER), "exec"),
        {"tail": stage.world, "namespace": namespace},
    )
    patch.setattr(stage.world, "_NATIVE", {n: namespace[n] for n in stage.world.METHODS})


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_MAPPING_EVIDENCE", str(tmp_path)))
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(parents=True, exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


@pytest.fixture(scope="module")
def parent():
    patch = pytest.MonkeyPatch()
    verify_sources = _fixture_verified_sources()
    patch.setattr(stage, "_verify_sources", verify_sources)
    env = stage.world.environment
    original = env.prepare_continuation
    mask = np.asarray([[0.0, 0.0], [0.0, 0.0]])

    def before(request):
        _fixture_progress("environment_enter")
        namespace = {"fixture_mask": mask}
        exec(
            compile(
                """
def make_maskM(self,p):
    probe('make_maskM',self,p)
    self.maskM=interp.griddata(self.xypts,None,None)
    self.maskM=gaussian_filter(self.maskM,1)
    self.maskECM=fixture_mask
    self.voronoi_centres=self.xypts
""",
                "<synthetic-mapping-mask>",
                "exec",
            ),
            namespace,
        )
        patch.setitem(env._METHODS, "make_maskM", namespace["make_maskM"])
        original_namespace = env._namespace

        def supplied_namespace(context):
            methods = original_namespace(context)
            methods["make_maskM"].__globals__["fixture_mask"] = mask
            return methods

        patch.setattr(env, "_namespace", supplied_namespace)
        result = original(request)
        _fixture_progress("environment_return")
        return result

    facade = _environment_facade(env, before)
    constructor = helpers.issued_multi_chain
    _fixture_progress("issued_chain_enter")
    try:
        chain = FunctionType(
            constructor.__code__,
            dict(constructor.__globals__, env=facade, fixture=_fixture_templates),
            constructor.__name__,
            constructor.__defaults__,
            constructor.__closure__,
        )(patch)
        _fixture_progress("issued_chain_return")
        _fixture_progress("world_request_enter")
        request = stage.world.from_poisson(chain.owner, law_id=stage.world.LAW_ID)
        _fixture_progress("world_tail_enter")
        owner = stage.world.prepare_continuation(request)
        context = stage.world._authority(owner)
        prefix = stage.world._prefix(context)
        assert type(prefix.caller) is stage.multi._Caller and prefix.caller.maskECM is mask
        assert not _FIXTURE_LOG_ERRORS
        _fixture_progress("world_parent_sealed")
        yield SimpleNamespace(
            owner=owner, context=context, prefix=prefix, caller=prefix.caller, mask=mask
        )
    except BaseException as error:
        _fixture_progress("parent_setup_or_control_failed", error)
        raise
    finally:
        patch.undo()


def fixture(monkeypatch, parent, *, two_probes=False):
    calls, hooks, errors = [], {}, {}
    zero = np.asarray([[0.0, 0.0], [0.0, 0.0]])
    plain = np.asarray([[1.0, 2.0], [3.0, 4.0]])

    def point(name):
        calls.append(name)
        if name in hooks:
            hooks[name]()

    def griddata(*a, **k):
        point("griddata_delegate")
        assert k["fill_value"] == 0
        return plain

    def asarray(value):
        point("asarray_delegate")
        return value

    def finish(factor, result):
        point("multiply_standin")
        assert result is plain
        return zero if factor is parent.mask else plain

    namespace = dict(stage.source.__dict__, point=point, finish=finish)
    exec(
        compile(
            """
def map_cells_centre_to_grids_centre(self,*args,**kwargs):
    point('grid_entry')
    return self.map_cells_centre_to_points(*args,target_points=(self.X,self.Y),
        data_factor=self.maskECM,**kwargs)
def map_cells_centre_to_points(self,cells_centre_data,target_points,
        interp_method='linear',data_factor=1):
    point('points_entry')
    values=nparray.from_iterable(cells_centre_data)
    result=interp.griddata(points=(self.cell_centres[:,0],self.cell_centres[:,1]),
        values=values,xi=target_points,method=interp_method,fill_value=0)
    return finish(data_factor,result)
def from_iterable(value):
    if not sequences.is_sequence(value):raise TypeError('synthetic iterable failure')
    return np.asarray(value)
def is_sequence(*values):
    return True
""",
            "<synthetic-owned-mapping>",
            "exec",
        ),
        namespace,
    )
    monkeypatch.setattr(stage, "_NATIVE", {name: namespace[name] for name in stage.METHODS})
    monkeypatch.setattr(stage, "_FROM", namespace["from_iterable"])
    monkeypatch.setattr(stage, "_SEQUENCE", namespace["is_sequence"])
    monkeypatch.setattr(stage, "_ASARRAY", asarray)
    monkeypatch.setattr(stage, "_GRIDDATA", griddata)
    data = np.asarray([float(i) for i in range(len(parent.caller.cell_i))])
    probes = (
        stage.Probe("grid", "grids", data),
        stage.Probe("points", "points", data, (np.asarray([0.0, 1.0]), np.asarray([0.0, 1.0]))),
    )
    if not two_probes:
        probes = probes[:1]
    request = stage.from_world(parent.owner, probes, law_id=stage.LAW_ID)
    return SimpleNamespace(
        parent=parent,
        request=request,
        data=data,
        probes=probes,
        calls=calls,
        hooks=hooks,
        errors=errors,
        zero=zero,
        plain=plain,
    )


def retained(error):
    p = error.partial or {}
    return dict(
        error=error,
        source_error=error.source_error,
        capture_error=error.capture_error,
        trial=error.trial,
        results=p.get("results"),
        helpers=p.get("helpers"),
        events=p.get("events"),
        work=p.get("work"),
        lease_released=p.get("read_only_lease_released"),
    )


def test_software_source_ast_exact_methods_and_helper_roster(evidence):
    save(evidence, "source-pins", stage._verify_sources())
    assert stage.source.NATIVE_LINES[stage.METHODS[0]] == (2825, 2854)
    assert stage.source.NATIVE_LINES[stage.METHODS[1]] == (2883, 3017)
    assert len(stage.INVALIDATED_OWNERS) == 11
    with pytest.MonkeyPatch.context() as patch:
        _fixture_templates(patch)
        assert set(stage.world.poisson._CALLER) == set(stage.world.poisson.METHODS)
        assert stage.world.poisson._LAPLACIAN.__code__.co_filename == "<synthetic-poisson>"
        assert set(stage.world._NATIVE) == set(stage.world.METHODS)
        assert all(
            fn.__code__.co_filename == "<synthetic-world-tail>"
            for fn in stage.world._NATIVE.values()
        )


def test_software_readonly_same_caller_zero_mask_probe_results(monkeypatch, parent, evidence):
    h = fixture(monkeypatch, parent, two_probes=True)
    before = stage.world._snapshot(parent.context)
    child = stage.prepare(h.request)
    assert dict(child.results)["grid"] is h.zero and dict(child.results)["points"] is h.plain
    assert child.trial.before.identity == child.trial.after.identity == before.identity
    assert parent.owner.cells is parent.caller and parent.caller.maskECM is parent.mask
    assert not np.any(parent.mask) and not np.any(dict(child.results)["grid"])
    assert parent.caller not in stage.multi._READ_LEASES
    assert h.calls.count("griddata_delegate") == 2
    with pytest.raises(stage.multi.MultiCellRejected):
        parent.caller.map_cells_centre_to_points(h.data, (h.data, h.data))
    save(evidence, "trial", child.trial)


@pytest.mark.parametrize("which", ["grids", "points"])
def test_software_raw_entry_without_lease_never_enters_source(monkeypatch, parent, evidence, which):
    h = fixture(monkeypatch, parent)
    method = getattr(parent.caller, stage.METHODS[0 if which == "grids" else 1])
    with pytest.raises(stage.multi.MultiCellRejected) as caught:
        method(h.data)
    assert h.calls == []
    save(evidence, "raw-entry-refusal", caught.value)


def test_software_helper_failure_keeps_primary_and_releases_parent(monkeypatch, parent, evidence):
    h = fixture(monkeypatch, parent)
    cause = SyntheticSourceCause("original interpolation cause")
    error = SyntheticSourceFailure("synthetic interpolation failure")

    def fail():
        raise error from cause

    h.hooks["griddata_delegate"] = fail
    with pytest.raises(stage.MappingRejected) as caught:
        stage.prepare(h.request)
    actual = caught.value
    assert actual.source_error is error and actual.__cause__ is error and error.__cause__ is cause
    assert actual.partial["read_only_lease_released"] and parent.owner.cells is parent.caller
    assert not actual.trial.source_completed
    assert "multiply_standin" not in h.calls
    save(evidence, "failure", retained(actual))


def test_software_readonly_attr_write_and_reentry_are_blocked(monkeypatch, parent, evidence):
    h = fixture(monkeypatch, parent)
    original = parent.caller.X
    refusals = []

    def nested():
        with pytest.raises(stage.multi.MultiCellRejected) as caught:
            parent.caller.X = original.copy()
        refusals.append(caught.value)
        with pytest.raises(stage.MappingRejected) as reentry:
            stage.prepare(h.request)
        refusals.append(reentry.value)

    h.hooks["griddata_delegate"] = nested
    child = stage.prepare(h.request)
    assert len(refusals) == 2 and parent.caller.X is original and child.trial.source_completed
    save(evidence, "refusals", refusals)


@pytest.mark.parametrize("what", ["input", "helper", "equal_result_identity", "observer_code"])
def test_software_completed_stale_authority_refuse(monkeypatch, parent, evidence, what):
    h = fixture(monkeypatch, parent)
    child = stage.prepare(h.request)
    before = h.calls.count("griddata_delegate")
    if what == "input":
        h.data[0] = 9.0
    elif what == "helper":
        monkeypatch.setattr(
            stage,
            "_GRIDDATA",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("No stale helper entry")),
        )
    elif what == "equal_result_identity":
        context = stage._authority(child)
        original = context.results["grid"]
        replacement = original.copy()
        assert (
            stage.core.caches.snapshot(original).identity
            == stage.core.caches.snapshot(replacement).identity
        )
        context.results["grid"] = replacement
    else:

        def changed_observer(*args, **kwargs):
            raise AssertionError("Changed observer must never execute")

        monkeypatch.setattr(stage._event, "__code__", changed_observer.__code__)
    with pytest.raises(stage.MappingRejected) as caught:
        _ = child.results
    assert h.calls.count("griddata_delegate") == before
    assert parent.owner.cells is parent.caller
    save(evidence, "stale-refusal", retained(caught.value))


def test_software_enter_capture_failure_stops_delegate(monkeypatch, parent, evidence):
    h = fixture(monkeypatch, parent)
    original = stage._event
    capture = SyntheticCaptureFailure("mapping enter capture")

    def event(context, name, value):
        if name == "griddata_enter":
            stage.geometry._remember_observation_error(context, capture, origin=name, raw=value)
        else:
            original(context, name, value)

    monkeypatch.setattr(stage, "_event", event)
    with pytest.raises(stage.MappingRejected) as caught:
        stage.prepare(h.request)
    assert caught.value.capture_error is capture and "griddata_delegate" not in h.calls
    assert caught.value.partial["read_only_lease_released"]
    save(evidence, "capture-refusal", retained(caught.value))


def test_software_lease_requires_issued_mapping_request(parent, evidence):
    called = []
    with pytest.raises(stage.MappingRejected) as caught:
        with stage.multi._mapping_read_lease(
            parent.caller,
            token=object(),
            check=lambda: called.append("unissued check"),
            invoke=lambda *a, **k: called.append("unissued invoke"),
        ):
            raise AssertionError("Unissued lease must not open")
    assert not called and parent.caller not in stage.multi._READ_LEASES
    assert parent.owner.cells is parent.caller
    save(evidence, "unissued-lease-refusal", retained(caught.value))


def test_software_missing_world_authority_retains_unsealed_request(evidence):
    request = stage.Request(object(), (), "unissued")
    with pytest.raises(stage.MappingRejected) as caught:
        stage.prepare(request)
    assert caught.value.request is request and caught.value.trial is None
    assert caught.value.source_error is caught.value.__cause__
    assert not caught.value.partial["usable_child_available"]
    save(evidence, "missing-world-refusal", retained(caught.value))


@pytest.mark.parametrize("callback", ["check", "invoke"])
def test_software_lease_callback_code_drift_stops_before_callback(
    monkeypatch, parent, evidence, callback
):
    h = fixture(monkeypatch, parent)
    refusals, entered = [], []

    def replacement_factory(context):
        def replacement(*a, **k):
            context["entered"].append(True)
            raise AssertionError("Changed callback must never execute")

        return replacement

    def nested():
        lease = stage.multi._READ_LEASES[parent.caller]
        actual = getattr(lease, callback)
        substitute = replacement_factory({"entered": entered})
        assert actual.__code__.co_freevars == substitute.__code__.co_freevars
        with monkeypatch.context() as patch:
            patch.setattr(actual, "__code__", substitute.__code__)
            with pytest.raises(ValueError) as caught:
                parent.caller.map_cells_centre_to_points(h.data, (h.data, h.data))
            refusals.append(caught.value)

    h.hooks["griddata_delegate"] = nested
    child = stage.prepare(h.request)
    assert child.trial.source_completed and not entered and len(refusals) == 1
    save(evidence, "callback-refusal", refusals)


def test_software_cached_proof_requires_exact_current_bytes(tmp_path, evidence):
    path = tmp_path / "selected-source.py"
    path.write_bytes(b"selected producer\x00\xff")
    pins = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()}
    assert stage._verify_pin_bytes(pins) == pins
    path.write_bytes(b"changed! producer\x00\xff")
    with pytest.raises(ValueError) as caught:
        stage._verify_pin_bytes(pins)
    save(evidence, "changed-source-refusal", caught.value)


class FalseySourceFailure(SyntheticSourceFailure):
    def __bool__(self):
        return False


def _profile_context():
    context = SimpleNamespace(
        work=[],
        locals={},
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
    )
    context.work_context = SimpleNamespace(stage="isolated_profile_control", work=context.work)
    return context


@contextmanager
def _prior_observer(site, reject, capture, *, delegate=None):
    previous, old_trace = sys.getprofile(), sys.gettrace()
    seen, traced = [], []

    def profile(frame, event, arg):
        if (
            (delegate is None and frame.f_code is site.__code__)
            or delegate is not None
            and arg is delegate
        ):
            seen.append((event, frame.f_code.co_name))
            if event == reject:
                raise capture
        if previous is not None:
            previous(frame, event, arg)

    def trace(frame, event, arg):
        if frame.f_code is site.__code__:
            traced.append(event)
        if old_trace is not None:
            old_trace(frame, event, arg)
        return trace

    sys.setprofile(profile)
    sys.settrace(trace)
    try:
        yield SimpleNamespace(profile=profile, trace=trace, seen=seen, traced=traced)
    finally:
        sys.setprofile(previous)
        sys.settrace(old_trace)


def _profile_evidence(context):
    raw = context.observation_raw
    frame, event, arg = raw if type(raw) is tuple else (raw, None, None)
    return dict(
        error=context.observation_error,
        errors=context.observation_errors,
        origin=context.observation_origin,
        raw_frame=None
        if frame is None
        else dict(
            file=frame.f_code.co_filename,
            function=frame.f_code.co_qualname,
            local_names=sorted(frame.f_locals),
        ),
        raw_event=event,
        raw_return=arg if type(arg) in (type(None), str, int, tuple) else type(arg).__name__,
        locals=context.locals,
        work=context.work,
        native_owner_or_parent_fabricated=False,
    )


@pytest.mark.parametrize("scenario", ["success", "unwind", "falsey"])
def test_software_profile_unit_return_failure_is_deferred(monkeypatch, evidence, scenario):
    context = _profile_context()
    cause = SyntheticSourceCause("original source cause")
    primary = (FalseySourceFailure if scenario == "falsey" else SyntheticSourceFailure)(
        "original source primary"
    )
    capture = SyntheticCaptureFailure("inherited return observer")
    marker = ("raw result", 17)
    entered = []

    def site(value):
        raw_marker = value
        entered.append(raw_marker)
        if scenario != "success":
            raise primary from cause
        return raw_marker

    monkeypatch.setattr(stage, "_NATIVE", {name: site for name in stage.METHODS})
    with _prior_observer(site, "return", capture) as prior:
        if scenario == "success":
            with pytest.raises(stage.world.poisson.environment._CaptureStop):
                with stage._account(context):
                    assert site(marker) is marker
                    assert context.observation_error is capture
                    assert sys.getprofile() is not None
        else:
            with pytest.raises(type(primary)) as caught:
                with stage._account(context):
                    site(marker)
            assert caught.value is primary and primary.__cause__ is cause
        save(evidence, "deferred-profile", _profile_evidence(context))
        save(evidence, "primary", primary if scenario != "success" else None)
        save(evidence, "prior-events", prior.seen)
        assert sys.getprofile() is prior.profile and sys.gettrace() is prior.trace
        assert [event for event, _ in prior.seen] == ["call", "c_call", "c_return", "return"]
    assert entered == [marker] and context.observation_error is capture
    assert context.observation_origin == "inherited_profile_return"
    assert context.observation_raw[0].f_code is site.__code__
    assert context.observation_raw[2] is (marker if scenario == "success" else None)
    assert any(value["raw_marker"] is marker for value in context.locals.values())


@pytest.mark.parametrize("kind", ["python", "c"])
def test_software_profile_unit_entry_guard_is_immediate(monkeypatch, evidence, kind):
    context = _profile_context()
    guard = SyntheticSourceFailure("inherited entry guard")
    entered, payload = [], ["unconsumed"]
    delegate = payload.pop

    def site():
        if kind == "python":
            entered.append("body")
        else:
            delegate()

    monkeypatch.setattr(stage, "_NATIVE", {name: site for name in stage.METHODS})
    with _prior_observer(
        site,
        "call" if kind == "python" else "c_call",
        guard,
        delegate=None if kind == "python" else delegate,
    ) as prior:
        with pytest.raises(SyntheticSourceFailure) as caught:
            with stage._account(context):
                site()
        assert caught.value is guard
        assert sys.getprofile() is prior.profile and sys.gettrace() is prior.trace
    assert context.observation_error is None and not entered and payload == ["unconsumed"]
    assert len(context.work) == 1
    assert context.work[0]["status"] == "entered_not_success_credit"
    save(evidence, "immediate-entry-rejection", caught.value)


def test_software_profile_unit_c_exception_keeps_original_error(monkeypatch, evidence):
    context = _profile_context()
    capture = SyntheticCaptureFailure("inherited C-exception observer")
    cause = SyntheticSourceCause("original C-helper cause")
    errors = []
    delegate = [].pop

    def site():
        try:
            delegate()
        except IndexError as error:
            errors.append(error)
            raise error from cause

    monkeypatch.setattr(stage, "_NATIVE", {name: site for name in stage.METHODS})
    with _prior_observer(site, "c_exception", capture, delegate=delegate) as prior:
        with pytest.raises(IndexError) as caught:
            with stage._account(context):
                site()
        assert sys.getprofile() is prior.profile and sys.gettrace() is prior.trace
    assert caught.value is errors[0] and caught.value.__cause__ is cause
    assert context.observation_error is capture
    assert context.observation_origin == "inherited_profile_c_exception"
    save(evidence, "C-primary", caught.value)
    save(evidence, "deferred-C-observation", _profile_evidence(context))


def test_software_profile_unit_retains_both_local_and_prior_failures(monkeypatch, evidence):
    context = _profile_context()
    local = SyntheticCaptureFailure("raw-local observer")
    inherited = SyntheticCaptureFailure("inherited observer")
    primary = SyntheticSourceFailure("source unwind")
    cause = SyntheticSourceCause("source cause")

    class BrokenLocals(dict):
        def __setitem__(self, key, value):
            raise local

    context.locals = BrokenLocals(previous="retained")

    def site():
        raw_marker = "last raw local"
        assert raw_marker
        raise primary from cause

    monkeypatch.setattr(stage, "_NATIVE", {name: site for name in stage.METHODS})
    with _prior_observer(site, "return", inherited):
        with pytest.raises(SyntheticSourceFailure) as caught:
            with stage._account(context):
                site()
    assert caught.value is primary and primary.__cause__ is cause
    assert context.observation_error is local
    assert [error for _, error in context.observation_errors] == [local, inherited]
    assert context.locals == {"previous": "retained"}
    save(evidence, "both-observers", _profile_evidence(context))
    save(evidence, "primary", primary)


def test_software_profile_unit_unchanged_observer_restores_chain(monkeypatch, evidence):
    context = _profile_context()
    value = ("unchanged", 23)

    def site():
        return value

    monkeypatch.setattr(stage, "_NATIVE", {name: site for name in stage.METHODS})
    with _prior_observer(site, "never", None) as prior:
        with stage._account(context):
            assert site() is value
        assert sys.getprofile() is prior.profile and sys.gettrace() is prior.trace
        assert prior.seen and prior.traced
    assert context.observation_error is None
    save(evidence, "clean-profile", _profile_evidence(context))


@pytest.mark.parametrize("scenario", ["success", "unwind", "falsey"])
def test_software_profile_owner_keeps_primary_and_partial_return(
    monkeypatch, parent, evidence, scenario
):
    h = fixture(monkeypatch, parent)
    capture = SyntheticCaptureFailure("inherited helper return observer")
    cause = SyntheticSourceCause("original helper cause")
    primary = (FalseySourceFailure if scenario == "falsey" else SyntheticSourceFailure)(
        "original helper primary"
    )
    if scenario != "success":

        def fail():
            raise primary from cause

        h.hooks["griddata_delegate"] = fail
    target = stage._GRIDDATA
    with _prior_observer(target, "return", capture) as prior:
        with pytest.raises(stage.MappingRejected) as caught:
            stage.prepare(h.request)
        assert sys.getprofile() is prior.profile and sys.gettrace() is prior.trace
    error = caught.value
    assert error.capture_error is capture and error.stage == "capture"
    assert error.source_error is (None if scenario == "success" else primary)
    assert error.__cause__ is (capture if scenario == "success" else primary)
    if scenario != "success":
        assert primary.__cause__ is cause
    assert error.partial["observation_raw"][0].f_code is target.__code__
    assert error.partial["read_only_lease_released"]
    assert not error.partial["usable_child_available"]
    assert error.partial["parent_trial"] is parent.context.trial
    assert not any(context.request is h.request for context in stage._ISSUED.values())
    assert "multiply_standin" not in h.calls
    save(evidence, "profile-owner-refusal", retained(error))
