"""Profiled synthetic join/read/parser models; actual BETSE/ruamel are blocked."""

import json
import sys
from functools import wraps
from pathlib import Path
from types import SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_network_load as stage
from tests.unit import test_betse_native_parameter_network_boundary as earlier
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)


def parser_authority(parser_type):
    # Conditional metadata only, never a native parser birth or a public input.
    kinds = frozenset((parser_type,))
    classes = stage.prefix._class_bindings(kinds)
    method, chain, bindings = stage._born_parser(parser_type, kinds, classes)
    return dict(
        parser_runtime_types=kinds,
        parser_runtime_classes=classes,
        parser_method=method,
        parser_chain=chain,
        parser_bindings=bindings,
    )


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    inherited = earlier.blocked.__wrapped__(monkeypatch, request, tmp_path)
    next(inherited)
    old, trace = sys.getprofile(), sys.gettrace()
    attempts = []
    code = stage._invoke.__code__

    def profile(frame, event, arg):
        if event == "call" and (frame.f_code is code or "/ruamel/" in frame.f_code.co_filename):
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native network/parser/source execution forbidden")
        if old is not None:
            old(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
        assert attempts == [] and sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(old)
        try:
            next(inherited)
        except StopIteration:
            pass
        p = tmp_path / "native-blocked.json"
        row = json.loads(p.read_text())
        row["attempted"].extend(attempts)
        p.write_text(json.dumps(row))


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, request):
    scenario = getattr(request, "param", "network")
    h = earlier.controlled.__wrapped__(
        monkeypatch,
        tmp_path,
        SimpleNamespace(param="network" if scenario in {"wrapped", "null-decoded"} else scenario),
    )
    calls = []
    hooks = {}
    errors = {}
    state = {}
    shared = ["declared", "alias"]
    decoded = (
        None if scenario == "null-decoded" else {"a": shared, "b": shared, "nested": {"x": -0.0}}
    )
    filename = None if h.file is None else h.file.filename

    class Parser:
        def load(self, stream):
            raise AssertionError("Actual parser methods must not run in conditional models")

    def fail(point):
        if errors.get("point") == point:
            raise errors["primary"] from errors.get("cause")

    def join(*partnames):
        calls.append("join")
        fail("join")
        if state.get("join-none"):
            return None
        return str(tmp_path / "foreign.yaml") if state.get("wrong-join") else filename

    def reader(filename, encoding="utf-8"):
        calls.append("reader")
        fail("reader")
        return open(filename, "rt", encoding=encoding)

    def factory():
        calls.append("factory")
        fail("factory")
        return Parser()

    def load(filename, yaml_version):
        calls.append("load")
        fail("load")
        if state.get("skip-read"):
            return decoded
        with reader(filename) as stream:
            state["stream"] = stream
            state["parser"] = factory()
            return decoded

    if scenario == "wrapped":

        def wrap(raw):
            @wraps(raw)
            def wrapped(*args, **kwargs):
                return raw(*args, **kwargs)

            return wrapped

        join, reader, factory, load = (wrap(fn) for fn in (join, reader, factory, load))

    def branch(p, **kwargs):
        calls.append("branch")
        if "before" in hooks:
            hooks["before"]()
        if p.network_config is not None:
            p.molecules_enabled = p.network_config["implement network"]
            p.mol_mit_enabled = False
            p.expression_data_path_rel = p.network_config.get("expression data file", None)
            if p.expression_data_path_rel is not None and p.expression_data_path_rel != "None":
                p.expression_data_path = join(str(tmp_path), p.expression_data_path_rel)
                value = load(p.expression_data_path, kwargs[stage.previous.LOCAL_KEY])
                p.expression_data = dict(value) if state.get("copy-result") else value
        else:
            p.mol_mit_enabled = False
        if "after" in hooks:
            hooks["after"]()

    monkeypatch.setattr(stage.previous, "_compile", lambda parent: (branch, branch))
    boundary = h.prepare()
    parser_namespace = SimpleNamespace(YAML=Parser)
    modules = dict(
        pathnames=SimpleNamespace(join=join),
        yamls=SimpleNamespace(load=load, _make_ruamel_parser=factory, ruamel_yaml=parser_namespace),
        iofiles=SimpleNamespace(reading_chars=reader),
    )
    modules["yamls"].iofiles = modules["iofiles"]
    roles = {
        name: SimpleNamespace(
            function=fn,
            raw=stage.prefix.parameters.inherited._chain(fn)[-1],
            chain=stage.prefix.parameters.inherited._chain(fn),
            module=modules[module],
            module_name=module,
            name=key,
        )
        for name, fn, module, key in (
            ("join", join, "pathnames", "join"),
            ("load", load, "yamls", "load"),
            ("reader", reader, "iofiles", "reading_chars"),
            ("factory", factory, "yamls", "_make_ruamel_parser"),
        )
    }
    api = SimpleNamespace(
        roles=roles,
        modules=modules,
        parser_type=Parser,
        parser_namespace=parser_namespace,
        **parser_authority(Parser),
    )
    monkeypatch.setattr(stage, "_native", lambda bound: api)

    def invoke(context):
        context.work.append(
            dict(
                sequence=len(context.work),
                layer="synthetic_branch",
                status="entered_not_native_or_case_credit",
            )
        )
        return context.bound.function(
            context.p, **{stage.previous.LOCAL_KEY: context.bound.version}
        )

    monkeypatch.setattr(stage, "_invoke", invoke)
    monkeypatch.setenv(stage.RELEASE, "1")
    return SimpleNamespace(
        base=h,
        boundary=boundary,
        p=h.parent.p,
        calls=calls,
        hooks=hooks,
        errors=errors,
        state=state,
        decoded=decoded,
        roles=roles,
        api=api,
        request=lambda: stage.from_boundary(boundary, law_id=stage.LAW_ID),
    )


def run(h):
    return stage.prepare(h.request(), enabled=True)


def empty():
    assert not stage._ACTIVE and not stage.previous._ACTIVE and not stage.declarations._ACTIVE
    assert not stage.declarations.previous._ACTIVE and not stage.claims._ACTIVE
    assert (
        not stage.declarations.previous.previous._ACTIVE
        and not stage.declarations.previous.previous.paths._ACTIVE
    )


def test_exact_boundary_and_no_GRN_full_parameter_admission(plan):
    assert plan["original"]["source_lines"] == (779, 796) and plan["end_before_GRN"] == 802
    assert not plan["full_Parameters_ions_phase_INIT_admitted"]


@pytest.mark.parametrize("change", ["helper", "reader-module", "parser-module", "parser-type"])
def test_reached_helper_dispatch_is_bound_without_calling_source(change):
    entered = []

    def helper():
        entered.append("forbidden")
        raise AssertionError("No helper evaluation in metadata controls")

    class Parser:
        def load(self, stream):
            entered.append("forbidden_parser")
            raise AssertionError("No parser calls in metadata controls")

    parser = SimpleNamespace(YAML=Parser)
    reader = SimpleNamespace(reading_chars=helper)
    yamls = SimpleNamespace(
        load=helper, _make_ruamel_parser=helper, iofiles=reader, ruamel_yaml=parser
    )
    pathnames = SimpleNamespace(join=helper)
    modules = dict(pathnames=pathnames, yamls=yamls, iofiles=reader)
    roles = {
        role: SimpleNamespace(
            function=helper,
            raw=helper,
            chain=(helper,),
            module=modules[module],
            module_name=module,
            name=key,
        )
        for role, module, key in (
            ("join", "pathnames", "join"),
            ("load", "yamls", "load"),
            ("reader", "iofiles", "reading_chars"),
            ("factory", "yamls", "_make_ruamel_parser"),
        )
    }
    api = SimpleNamespace(
        roles=roles,
        modules=modules,
        parser_type=Parser,
        parser_namespace=parser,
        **parser_authority(Parser),
    )
    first = stage._native_bindings(api)
    stage.prefix.parameters.inherited._same(first, stage._native_bindings(api))
    if change == "helper":
        pathnames.join = lambda: None
    elif change == "reader-module":
        yamls.iofiles = SimpleNamespace(reading_chars=helper)
    elif change == "parser-module":
        yamls.ruamel_yaml = SimpleNamespace(YAML=Parser)
    else:
        parser.YAML = type("Parser", (), {})
    with pytest.raises(ValueError, match="dispatch"):
        stage._native_bindings(api)
    assert entered == []


@pytest.mark.parametrize(
    "enabled,local,parent", [(False, "1", "1"), (True, "0", "1"), (True, "1", "0"), (1, "1", "1")]
)
def test_release_gates_precede_boundary_lookup_or_native_work(monkeypatch, enabled, local, parent):
    monkeypatch.setenv(stage.RELEASE, local)
    monkeypatch.setenv(stage.declarations.RELEASE, parent)
    with pytest.raises(stage.NetworkLoadRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"
    empty()


@pytest.mark.parametrize(
    "value", [None, {}, SimpleNamespace(), object.__new__(stage.previous.NetworkBoundary)]
)
def test_unissued_boundary_or_supplied_parsed_dictionary_refuses(value):
    with pytest.raises(stage.previous.BoundaryRejected) as caught:
        stage.from_boundary(value, law_id=stage.LAW_ID)
    assert caught.value.stage == "boundary"
    empty()


@pytest.mark.parametrize(
    "controlled", ["zero", "network", "wrapped", "null-decoded"], indirect=True
)
def test_once_only_same_p_native_order_and_exact_decoded_alias_graph(controlled, tmp_path):
    h = controlled
    before = dict(vars(h.p))
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    ctx = stage._ISSUED[owner]
    assert owner.parameters is h.p and h.base.parent.invalid
    assert all(vars(h.p)[k] is v for k, v in before.items())
    if h.base.file:
        assert h.calls == ["branch", "join", "load", "reader", "factory"]
        assert ctx.counts == dict(join=1, load=1, reader=1, factory=1)
        assert h.p.expression_data is ctx.decoded is h.decoded
        assert ctx.decoded_observed
        if h.decoded is not None:
            assert h.p.expression_data["a"] is h.p.expression_data["b"]
        assert (
            ctx.join_verified
            and ctx.parser is h.state["parser"]
            and ctx.stream is h.state["stream"]
            and ctx.stream.closed
        )
        assert ctx.stream_stat == h.base.file.stat and owner.trial.parsed
        if len(h.roles["join"].chain) > 1:
            wrapper_work = [w for w in ctx.work if w.get("layer") == "network_helper_wrapper_entry"]
            assert len(wrapper_work) == 4
    else:
        assert h.calls == ["branch"] and not owner.trial.parsed
    with pytest.raises(stage.NetworkLoadRejected) as caught:
        stage.prepare(request, enabled=True)
    assert caught.value.stage == "consumed"
    with pytest.raises(ValueError):
        _ = h.boundary.binding
    with pytest.raises(stage.NetworkLoadRejected) as caught:
        stage.require_grn(owner)
    assert caught.value.stage == "GRN_authority" and caught.value.partial["next_source_line"] == 802
    empty()
    save(
        tmp_path,
        "network-result",
        dict(
            trial=owner.trial,
            graph=ctx.graph[1],
            events=ctx.events,
            metadata_work=ctx.metadata_work,
            source_work=ctx.work,
            conditional_models_only=True,
            native_entries=0,
        ),
    )


@pytest.mark.parametrize("point", ["join", "load", "reader", "factory"])
def test_original_helper_exception_and_cause_survive_unwind(controlled, tmp_path, point):
    h = controlled
    primary = SyntheticSourceFailure("source helper failed")
    cause = SyntheticSourceCause("original cause")
    h.errors.update(point=point, primary=primary, cause=cause)
    with pytest.raises(stage.NetworkLoadRejected) as caught:
        run(h)
    e = caught.value
    assert e.source_error is primary and e.__cause__ is primary and primary.__cause__ is cause
    assert not e.partial.source_completed and e.partial.retired and h.base.parent.invalid
    assert point in h.calls and e.partial.decoded is None
    empty()
    save(
        tmp_path,
        "helper-failure",
        dict(
            primary=primary,
            secondary=e.capture_errors,
            raw=vars(h.p),
            events=e.partial.events,
            work=e.partial.work,
            counts=e.partial.counts,
        ),
    )


@pytest.mark.parametrize("change", ["wrong-join", "join-none", "skip-read", "copy-result"])
def test_missing_join_read_parser_or_copied_equal_decoded_result_cannot_issue_owner(
    controlled, change
):
    h = controlled
    h.state[change] = True
    with pytest.raises(stage.NetworkLoadRejected) as caught:
        run(h)
    e = caught.value
    if change in {"wrong-join", "join-none"}:
        assert "load" not in h.calls
        assert e.partial.counts["load"] == (0 if change == "wrong-join" else 1)
    if change == "wrong-join":
        assert e.source_error is None and e.capture_errors
    assert e.partial.retired and h.base.parent.invalid
    empty()


@pytest.mark.parametrize("swallow", [False, True])
def test_reentrant_branch_does_not_repeat_source_or_rearm_parent(controlled, swallow):
    h = controlled
    request = h.request()
    seen = []

    def nested():
        try:
            stage.prepare(request, enabled=True)
        except stage.NetworkLoadRejected as error:
            seen.append(error)
            if not swallow:
                raise

    h.hooks["before"] = nested
    with pytest.raises(stage.NetworkLoadRejected) as caught:
        stage.prepare(request, enabled=True)
    assert seen[0].stage == "reentrant" and h.calls.count("branch") == 1 and h.base.parent.invalid
    assert caught.value.partial.invalid
    empty()


@pytest.mark.parametrize("source_failure", [False, True])
def test_profile_return_capture_keeps_primary_cause_and_refuses_without_parser_replay(
    controlled, tmp_path, source_failure
):
    h = controlled
    primary = SyntheticSourceFailure("join failed")
    cause = SyntheticSourceCause("cause")
    capture = SyntheticCaptureFailure("inherited return capture")
    if source_failure:
        h.errors.update(point="join", primary=primary, cause=cause)
    old = sys.getprofile()
    code = h.roles["join"].raw.__code__
    seen = []

    def profile(frame, event, arg):
        if old is not None:
            old(frame, event, arg)
        if frame.f_code is code and event == "return":
            seen.append(event)
            raise capture

    sys.setprofile(profile)
    try:
        with pytest.raises(stage.NetworkLoadRejected) as caught:
            run(h)
        assert sys.getprofile() is profile
    finally:
        sys.setprofile(old)
    e = caught.value
    assert seen == ["return"] and e.source_error is (primary if source_failure else None)
    assert e.__cause__ is (primary if source_failure else capture)
    assert any(error is capture for _, error in e.capture_errors)
    if source_failure:
        assert primary.__cause__ is cause
    assert "load" not in h.calls
    empty()
    save(
        tmp_path,
        "profile-failure",
        dict(
            primary=e.source_error,
            secondary=e.capture_errors,
            events=e.partial.events,
            raw=vars(h.p),
            source_work=e.partial.work,
        ),
    )


def test_completed_parse_capture_failure_retains_decoded_object_and_no_child(
    controlled, monkeypatch, tmp_path
):
    h = controlled
    capture = SyntheticCaptureFailure("graph seal failed")
    original = stage.prefix.parameters.inherited.tissue.core.caches.snapshot

    def snapshot(value):
        if sys._getframe(1).f_code is stage.prepare.__code__:
            raise capture
        return original(value)

    monkeypatch.setattr(stage.prefix.parameters.inherited.tissue.core.caches, "snapshot", snapshot)
    with pytest.raises(stage.NetworkLoadRejected) as caught:
        run(h)
    e = caught.value
    assert e.source_error is None and e.__cause__ is capture and e.partial.source_completed
    assert h.p.expression_data is e.partial.decoded is h.decoded
    empty()
    save(
        tmp_path,
        "capture-failure",
        dict(
            primary=e.source_error,
            secondary=e.capture_errors,
            decoded=e.partial.decoded,
            raw=vars(h.p),
            events=e.partial.events,
        ),
    )


@pytest.mark.parametrize("change", ["decoded-alias", "earlier-field", "file", "cache"])
def test_saved_network_owner_detects_graph_file_and_cache_drift(controlled, change):
    h = controlled
    owner = run(h)
    ctx = stage._ISSUED[owner]
    if change == "decoded-alias":
        h.p.expression_data["b"] = list(h.p.expression_data["a"])
    elif change == "earlier-field":
        h.p.init_tsteps = 100
    elif change == "file":
        Path(h.base.file.filename).chmod(0o644)
    else:
        object.__setattr__(ctx.trial.cache, "descriptor_json", "{}")
    with pytest.raises(stage.NetworkLoadRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "owner_drift" and ctx.invalid


def test_live_request_and_network_owner_pickle_refuse(controlled):
    import pickle

    h = controlled
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    for value in (request, owner):
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(value)
    empty()


@pytest.mark.parametrize("role", ["join", "reader", "factory", "load"])
@pytest.mark.parametrize("unwind", [False, True])
@pytest.mark.parametrize("capture_at", ["locals", "event"])
def test_repair_raw_return_precedes_fallible_capture(
    monkeypatch, tmp_path, role, unwind, capture_at
):
    """Actually profile return/unwind; no original parser/helper is invoked."""
    primary = SyntheticSourceFailure("profiled synthetic helper failure")
    cause = SyntheticSourceCause("source cause")
    secondary = SyntheticCaptureFailure("return observation failed")
    returned = {"role": role, "data": [1, 2]}
    seen = []

    def observed():
        seen.append("entered")
        if unwind:
            raise primary from cause
        return returned

    class BadEvents(list):
        def append(self, value):
            raise secondary

    context = SimpleNamespace(
        stage="synthetic_return_control",
        work=[],
        events=BadEvents() if capture_at == "event" else [],
        raw_returns=[],
        raw_return=None,
        locals={},
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
        stream=None,
        parser=None,
        decoded=None,
        decoded_observed=False,
        api=SimpleNamespace(roles={role: SimpleNamespace(raw=observed, chain=(observed,))}),
    )
    monkeypatch.setattr(stage, "_entry", lambda *args: None)
    if capture_at == "locals":
        real_dict = dict

        def copy_locals(*args, **kwargs):
            if args:
                raise secondary
            return real_dict(*args, **kwargs)

        monkeypatch.setattr(stage, "dict", copy_locals, raising=False)
    profile, trace = sys.getprofile(), sys.gettrace()
    with stage._observe(context):
        if unwind:
            with pytest.raises(SyntheticSourceFailure) as caught:
                observed()
            assert caught.value is primary and primary.__cause__ is cause
        else:
            assert observed() is returned
    assert sys.getprofile() is profile and sys.gettrace() is trace
    assert seen == ["entered"] and context.observation_error is secondary
    witness = context.raw_returns[0]
    assert len(context.raw_returns) == 1 and context.raw_return is witness
    assert witness[0] == role and witness[1].f_code is observed.__code__
    assert witness[2] is (None if unwind else returned)
    assert context.observation_raw[0] == role
    assert context.observation_raw[1] is witness[1] and context.observation_raw[2] is witness[2]
    assert context.stream is context.parser is context.decoded is None
    assert context.decoded_observed is False and context.events == []
    save(
        tmp_path,
        "raw-return",
        dict(
            role=role,
            unwind=unwind,
            capture_at=capture_at,
            returned=witness[2],
            raw_frame_file=witness[1].f_code.co_filename,
            raw_frame_function=witness[1].f_code.co_qualname,
            primary=primary if unwind else None,
            secondary=context.observation_errors,
            exact_witness_identity_checked=True,
            verified_owner_published=False,
            native_calls=0,
        ),
    )


@pytest.mark.parametrize("unwind", [False, True])
def test_repair_capture_failure_retains_raw_load_and_refuses_owner(
    controlled, monkeypatch, tmp_path, unwind
):
    h = controlled
    primary = SyntheticSourceFailure("load source failure")
    cause = SyntheticSourceCause("primary cause")
    secondary = SyntheticCaptureFailure("event append failure")
    if unwind:
        h.errors.update(point="load", primary=primary, cause=cause)
    original = stage._returned

    class BadEvents(list):
        def append(self, value):
            raise secondary

    def returned(context, role, frame, arg):
        if role == "load":
            context.events = BadEvents(context.events)
        return original(context, role, frame, arg)

    monkeypatch.setattr(stage, "_returned", returned)
    request = h.request()
    with pytest.raises(stage.NetworkLoadRejected) as caught:
        stage.prepare(request, enabled=True)
    error = caught.value
    assert error.request is request and error.source_error is (primary if unwind else None)
    assert error.__cause__ is (primary if unwind else secondary)
    if unwind:
        assert primary.__cause__ is cause
    context = error.partial
    witness = context.raw_return
    assert witness[0] == "load" and witness[1].f_code is h.roles["load"].raw.__code__
    assert witness[2] is (None if unwind else h.decoded)
    assert context.decoded is None and context.decoded_observed is False
    assert context.observation_error is secondary and context.retired and h.base.parent.invalid
    assert context.source_completed is (not unwind)
    assert all(value is not context for value in stage._ISSUED.values())
    empty()
    save(
        tmp_path,
        "raw-load-failure",
        dict(
            primary=error.source_error,
            secondary=error.capture_errors,
            raw_return=witness[2],
            raw_fields=vars(h.p),
            events=context.events,
            work=context.work,
            verified_decoded=False,
            request=stage.request_record(request),
        ),
    )


@pytest.mark.parametrize("change", ["method", "code"])
def test_repair_born_parser_method_and_code_are_bound_without_calls(change):
    calls = []

    class Parser:
        def load(self, stream):
            calls.append("original")
            raise AssertionError("No parser evaluation")

    def foreign(self, stream):
        calls.append("foreign")
        raise AssertionError("No foreign parser evaluation")

    kinds = frozenset((Parser,))
    born = stage.prefix._class_bindings(kinds)
    method, chain, bindings = stage._born_parser(Parser, kinds, born)
    assert method is Parser.load and chain == (method,) and len(bindings) == 1
    if change == "method":
        Parser.load = foreign
    else:
        method.__code__ = foreign.__code__
        assert Parser.load is method
    with pytest.raises(ValueError):
        stage._born_parser(Parser, kinds, born)
    assert calls == []


def test_repair_factory_receiver_dispatch_is_checked_without_parser_calls():
    calls = []

    class Parser:
        def load(self, stream):
            calls.append(stream)
            raise AssertionError("No parser calls")

    api = SimpleNamespace(parser_type=Parser, parser_method=Parser.load)
    parser = Parser()
    stage._parser_receiver(api, parser)
    parser.load = parser.load
    with pytest.raises(ValueError, match="Instance YAML.load"):
        stage._parser_receiver(api, parser)
    assert calls == []


@pytest.mark.parametrize("when", ["before_prepare", "during", "after_owner"])
def test_repair_same_class_method_replacement_refuses_without_parser_calls(
    controlled, when, monkeypatch, tmp_path
):
    h = controlled
    request = h.request()
    parser_type = h.api.parser_type
    entered = []

    def foreign(self, stream):
        entered.append("foreign")
        raise AssertionError("Foreign parser may not be called")

    def mutate():
        monkeypatch.setattr(parser_type, "load", foreign)

    if when == "after_owner":
        owner = stage.prepare(request, enabled=True)
        mutate()
        with pytest.raises(stage.NetworkLoadRejected) as caught:
            _ = owner.parameters
        assert caught.value.stage == "owner_drift" and caught.value.request is request
    else:
        if when == "before_prepare":
            mutate()
        else:
            h.hooks["before"] = mutate
        with pytest.raises(stage.NetworkLoadRejected) as caught:
            stage.prepare(request, enabled=True)
        assert caught.value.stage == (
            "native_helper_binding" if when == "before_prepare" else "native_network_branch"
        )
        assert h.calls == ([] if when == "before_prepare" else ["branch"])
    error = caught.value
    assert h.api.parser_type is parser_type and h.api.parser_namespace.YAML is parser_type
    assert error.source_error is not None and entered == []
    empty()
    save(
        tmp_path,
        "parser-dispatch-failure",
        dict(
            when=when,
            stage=error.stage,
            error=error.source_error,
            request=stage.request_record(request),
            class_identity_unchanged=True,
            native_parser_calls=0,
            work=error.partial.work,
        ),
    )


@pytest.mark.parametrize("when", ["before_prepare", "before_retire", "after_owner"])
def test_repair_source_plan_budget_drift_refuses_exact_original_request(
    controlled, monkeypatch, tmp_path, when
):
    h = controlled
    request = h.request()
    original_record = stage.request_record(request)
    budget = stage.MAX_PARSER_CALLS

    def mutate():
        monkeypatch.setattr(stage, "MAX_PARSER_CALLS", budget + 1)

    if when == "after_owner":
        owner = stage.prepare(request, enabled=True)
        mutate()
        with pytest.raises(stage.NetworkLoadRejected) as caught:
            _ = owner.parameters
        assert caught.value.stage == "owner_drift"
    else:
        if when == "before_prepare":
            mutate()
        else:
            native = stage._native

            def binding(boundary):
                result = native(boundary)
                mutate()
                return result

            monkeypatch.setattr(stage, "_native", binding)
        with pytest.raises(stage.NetworkLoadRejected) as caught:
            stage.prepare(request, enabled=True)
        assert caught.value.stage == (
            "source_plan" if when == "before_prepare" else "native_helper_binding"
        )
        assert caught.value.partial.retired is False and h.calls == []
    error = caught.value
    assert error.request is request and stage.request_record(request) == original_record
    assert isinstance(error.source_error, ValueError) and "source plan" in str(error.source_error)
    assert error.partial.observed_source_identity != request.source_identity
    assert error.partial.observed_source_plan["max_parser_calls"] == budget + 1
    assert stage._CONSUMED[request] is error.partial and h.base.parent.invalid
    empty()
    save(
        tmp_path,
        "source-plan-failure",
        dict(
            when=when,
            stage=error.stage,
            request=original_record,
            current_plan=error.partial.observed_source_plan,
            error=error.source_error,
            original_request_identity=request.identity,
            work=error.partial.work,
            retired=error.partial.retired,
        ),
    )


def test_repair_runner_child_selects_group_and_restores_environment(monkeypatch, tmp_path):
    import shlex

    from validation.betse import betse_native_parameter_network_load_software as runner

    seen = []
    error = SyntheticCaptureFailure("conditional software child error")

    def delegate(function, **bindings):
        assert function is runner.inherited.child and bindings == dict(TEST=runner.TEST)

        def child(output):
            group = runner.os.environ[runner.GROUP_VARIABLE]
            assert output is tmp_path
            assert shlex.split(runner.os.environ["PYTEST_ADDOPTS"]) == ["-k", runner.GROUPS[group]]
            seen.append(group)
            if group == "affected":
                raise error
            return 0

        return child

    monkeypatch.setattr(runner.callbacks, "delegate", delegate)
    monkeypatch.setenv("PYTEST_ADDOPTS", "original-options")
    for group in runner.GROUPS:
        monkeypatch.setenv(runner.GROUP_VARIABLE, group)
        if group == "affected":
            with pytest.raises(SyntheticCaptureFailure) as caught:
                runner.child(tmp_path)
            assert caught.value is error
        else:
            assert runner.child(tmp_path) == 0
        assert runner.os.environ["PYTEST_ADDOPTS"] == "original-options"
    assert seen == ["repair", "affected"]


def test_repair_runner_unselected_child_refuses_before_pytest(monkeypatch, tmp_path):
    from validation.betse import betse_native_parameter_network_load_software as runner

    calls = []
    monkeypatch.setattr(runner.callbacks, "delegate", lambda *a, **k: calls.append(a))
    for value in (None, "all"):
        if value is None:
            monkeypatch.delenv(runner.GROUP_VARIABLE, raising=False)
        else:
            monkeypatch.setenv(runner.GROUP_VARIABLE, value)
        with pytest.raises(ValueError, match="explicit repair or affected"):
            runner.child(tmp_path)
    assert calls == []


def test_repair_runner_guard_keeps_declared_policy_and_environment(monkeypatch, tmp_path):
    from validation.betse import betse_native_parameter_network_load_software as runner

    seen = []
    environment = {"KEEP": "original"}

    def backend(command, **kwargs):
        assert command == ["conditional-software-only"]
        seen.append(kwargs)
        return dict(status="completed", returncode=0)

    def delegate(function, **bindings):
        assert function is runner.inherited.software and bindings["FILE"] == runner.FILE

        def software(packet, output):
            assert packet == "conditional-packet" and output is tmp_path
            return bindings["guard"].run_bounded(
                ["conditional-software-only"],
                env=environment,
                directory=tmp_path,
                cwd=tmp_path,
                timeout=480,
                max_rss_bytes=2**30,
                min_available_bytes=8 * 2**30,
            )

        return software

    monkeypatch.setattr(runner.callbacks, "delegate", delegate)
    monkeypatch.setattr(runner.inherited.guard, "run_bounded", backend)
    for group in runner.GROUPS:
        assert runner.software("conditional-packet", tmp_path, group=group)["returncode"] == 0
    assert len(seen) == 2 and environment == {"KEEP": "original"}
    for row, group in zip(seen, runner.GROUPS, strict=True):
        assert row["env"] == dict(environment, **{runner.GROUP_VARIABLE: group})
        assert row["timeout"] == 480 and row["max_rss_bytes"] == 2**30
        assert row["min_available_bytes"] == 8 * 2**30 and row["cwd"] is tmp_path


def test_repair_runner_invalid_group_refuses_before_lookup(monkeypatch, tmp_path):
    from validation.betse import betse_native_parameter_network_load_software as runner

    calls = []
    monkeypatch.setattr(runner.callbacks, "delegate", lambda *a, **k: calls.append(a))
    for value in (None, "all"):
        with pytest.raises(ValueError, match="explicit repair or affected"):
            runner.software("nonexistent-packet", tmp_path, group=value)
    assert calls == []
