"""Blocked real-reader prefix boundaries using explicit synthetic providers."""

import ast
import builtins
import hashlib
import json
import struct
import sys
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_yaml_prefix as stage
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    attempted = []
    old, trace, imp = sys.getprofile(), sys.gettrace(), builtins.__import__
    codes = {
        stage._invoke.__code__,
        stage.parameters._acquire.__code__,
        stage.parameters._invoke.__code__,
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code.co_filename.startswith(
                str(stage.parameters.inherited.tissue.aliases.NATIVE) + "/"
            )
        ):
            attempted.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native/parser/model work forbidden")
        if old is not None:
            old(frame, event, arg)

    def imports(name, *args, **kwargs):
        if name == "betse" or name.startswith("betse.") or name.startswith("ruamel"):
            attempted.append(("import", name))
            raise AssertionError("Actual native/parser import forbidden")
        return imp(name, *args, **kwargs)

    def rng(*args, **kwargs):
        attempted.append("RNG")
        raise AssertionError("Actual RNG forbidden")

    monkeypatch.setattr(builtins, "__import__", imports)
    for name in ("RandomState", "default_rng", "seed", "random", "normal", "choice", "uniform"):
        monkeypatch.setattr(stage.parameters.inherited.tissue.callers.np.random, name, rng)
    sys.setprofile(profile)
    try:
        yield
        assert attempted == [] and sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(old)
        sys.settrace(trace)
        (tmp_path / "native-blocked.json").write_text(
            json.dumps(
                dict(
                    nodeid=request.node.nodeid, attempted=attempted, actual_native_parser_entries=0
                )
            )
        )


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, plan):
    monkeypatch.setattr(stage, "BASE", tmp_path)
    path = tmp_path / "declared.yaml"
    data = b"key: declared synthetic reader input\n"
    path.write_bytes(data)
    path.chmod(0o444)
    file = stage.input_file(
        path,
        sha256=hashlib.sha256(data).hexdigest(),
        origin="explicit synthetic input, no native derivation",
    )

    class Yaml:
        def __init__(self):
            self._conf = None

    class Params(Yaml):
        def __init__(self):
            super().__init__()
            self._conf_filename = self._conf_dirname = self._conf_basename = None
            self.init_export_dirname = None

    class Comment:
        __slots__ = ("text", "anchor")

        def __init__(self, text):
            self.text = text
            self.anchor = "retained synthetic anchor"

    class RTMap(OrderedDict):
        pass

    class RTSeq(list):
        pass

    p = Params()
    birth_cache = stage.parameters.inherited.tissue.core.caches.snapshot(dict(unloaded=True))
    owner = object.__new__(stage.parameters.ParameterOwner)
    parent = SimpleNamespace(
        p=p,
        active=False,
        invalid=False,
        trial=SimpleNamespace(identity="synthetic-native-birth", cache=birth_cache),
        graph=((), {}),
        source=SimpleNamespace(yaml=Yaml, cls=Params),
        plan=dict(path_fields=("init_export_dirname",)),
        runtime=((), (Params,)),
    )
    calls, hooks, errors = [], {}, {}

    def validate(value):
        if value is not owner or parent.invalid:
            raise stage.parameters.ParameterRejected(
                "Unissued/retired synthetic parent", stage="owner"
            )
        return parent

    def reader(self, filename):
        calls.append("reader")
        assert parent.invalid and self is p and filename == file.filename
        if "reader" in hooks:
            hooks["reader"]()
        if "reader" in errors:
            raise errors["reader"] from errors.get("cause")
        shared = RTSeq(["same scalar", -0.0])
        root = RTMap([("a", shared), ("b", shared)])
        root.comment = Comment("original synthetic comment")
        root.alias = root
        self._conf = root
        self._conf_filename = filename
        self._conf_dirname = str(Path(filename).parent)
        self._conf_basename = Path(filename).name

    def prefix(context):
        return reader

    def registry(context):
        return frozenset((Yaml, Params, Comment, RTMap, RTSeq)), {}, ((), (Params,))

    def invoke(context):
        context.work.append(
            dict(
                sequence=len(context.work),
                layer="synthetic_yaml_reader",
                phase=context.stage,
                status="entered_not_source_credit",
            )
        )
        return context.function(context.p, context.request.file.filename)

    monkeypatch.setattr(stage.parameters, "_validate", validate)
    monkeypatch.setattr(stage.parameters, "_runtime", lambda source: parent.runtime)
    monkeypatch.setattr(stage, "_prefix", prefix)
    monkeypatch.setattr(stage, "_runtime_types", registry)
    monkeypatch.setattr(stage, "_invoke", invoke)
    monkeypatch.setattr(stage, "source_plan", lambda: dict(plan, synthetic_only=True))
    monkeypatch.setenv(stage.parameters.inherited.RELEASE, "1")
    return SimpleNamespace(
        parent=owner,
        context=parent,
        p=p,
        file=file,
        path=path,
        data=data,
        calls=calls,
        hooks=hooks,
        errors=errors,
        types=frozenset((Yaml, Params, Comment, RTMap, RTSeq)),
        Yaml=Yaml,
        RTMap=RTMap,
        RTSeq=RTSeq,
        Comment=Comment,
        request=lambda: stage.from_unloaded(owner, file, law_id=stage.LAW_ID),
    )


def run(h):
    return stage.prepare(h.request(), enabled=True)


def test_pinned_prefix_precedes_compatibility_and_path_continuation(plan):
    assert plan["prefix_statements"] == 3 and plan["yaml_version"] == "1.2"
    assert plan["next_source_line"] > plan["prefix_lines"][1]
    assert not plan["full_parameters_load_or_phase_admitted"]


@pytest.mark.parametrize("enabled,env", [(False, "0"), (True, "0"), (False, "1"), (1, "1")])
def test_entry_release_gates_precede_reader(monkeypatch, enabled, env):
    monkeypatch.setenv(stage.parameters.inherited.RELEASE, env)
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"


def test_same_live_p_is_consumed_once_file_associated_and_roundtrip_graph_retained(
    controlled, tmp_path
):
    h = controlled
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    assert owner.parameters is h.p and h.context.invalid and h.calls == ["reader"]
    assert h.p._conf["a"] is h.p._conf["b"] and h.p._conf.alias is h.p._conf
    assert h.p._conf.comment.text == "original synthetic comment"
    assert owner.trial.prefix_completed and h.p.init_export_dirname is None
    with pytest.raises(stage.parameters.ParameterRejected):
        stage.parameters._validate(h.parent)
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        stage.prepare(request, enabled=True)
    assert caught.value.stage == "consumed"
    save(
        tmp_path,
        "prefix",
        dict(trial=owner.trial, graph=stage._ISSUED[owner].graph[1], synthetic_only=True),
    )


@pytest.mark.parametrize(
    "value", [None, {}, SimpleNamespace(), object.__new__(stage.parameters.ParameterOwner)]
)
def test_real_unloaded_authority_refuses_receipt_hydration(value):
    with pytest.raises(
        stage.parameters.ParameterRejected, match="Issued fresh native parameter owner"
    ):
        stage.from_unloaded(value, None, law_id=stage.LAW_ID)


@pytest.mark.parametrize(
    "mutation", ["copy-request", "copy-file", "wrong-hash", "file-replaced", "symlink", "writable"]
)
def test_file_identity_and_request_authority_refuse_before_reader(controlled, mutation):
    h = controlled
    if mutation == "wrong-hash":
        with pytest.raises(stage.YamlPrefixRejected):
            stage.input_file(h.path, sha256="0" * 64, origin="declared")
        assert h.calls == []
        return
    if mutation == "copy-file":
        with pytest.raises(stage.YamlPrefixRejected):
            stage.from_unloaded(h.parent, replace(h.file), law_id=stage.LAW_ID)
        return
    request = h.request()
    if mutation == "copy-request":
        request = replace(request)
    elif mutation == "file-replaced":
        h.path.unlink()
        h.path.write_bytes(h.data)
        h.path.chmod(0o444)
    elif mutation == "symlink":
        target = h.path.with_name("linked.yaml")
        target.write_bytes(h.data)
        target.chmod(0o444)
        h.path.unlink()
        h.path.symlink_to(target)
    else:
        h.path.chmod(0o644)
    with pytest.raises((stage.YamlPrefixRejected, ValueError)):
        stage.prepare(request, enabled=True)
    assert h.calls == [] and not h.context.invalid


@pytest.mark.parametrize("failure", ["source", "capture"])
def test_failed_read_or_capture_keeps_exact_parent_retired_and_partials(
    controlled, monkeypatch, tmp_path, failure
):
    h = controlled
    request = h.request()
    error = SyntheticSourceFailure("native-shaped parser refusal")
    cause = SyntheticSourceCause("parse cause")
    if failure == "source":
        h.errors.update(reader=error, cause=cause)
    else:

        def capture(ctx):
            raise SyntheticCaptureFailure("roundtrip capture refused")

        monkeypatch.setattr(stage, "_capture", capture)
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        stage.prepare(request, enabled=True)
    e = caught.value
    assert h.context.invalid and e.partial.p is h.p and h.calls == ["reader"] and not stage._ACTIVE
    if failure == "source":
        assert e.source_error is error and e.__cause__ is error and error.__cause__ is cause
    else:
        assert e.source_error is None and e.capture_errors and e.partial.prefix_completed
    save(
        tmp_path,
        "failed-prefix",
        dict(
            primary=e.source_error,
            capture=e.capture_errors,
            parent_retired=h.context.invalid,
            raw_p=vars(h.p),
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize("mutation", ["comment", "alias", "anchor", "scalar-sign", "file", "path"])
def test_loaded_prefix_rejects_comment_alias_bit_file_and_path_drift(controlled, mutation):
    h = controlled
    owner = run(h)
    if mutation == "comment":
        h.p._conf.comment.text = "changed"
    elif mutation == "anchor":
        h.p._conf.comment.anchor = "foreign"
    elif mutation == "alias":
        h.p._conf["b"] = h.RTSeq(h.p._conf["a"])
    elif mutation == "scalar-sign":
        h.p._conf["a"][1] = 0.0
    elif mutation == "path":
        h.p.init_export_dirname = "/supplied"
    else:
        h.path.chmod(0o644)
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "owner_drift" and h.calls == ["reader"]


def test_no_full_load_or_phase_authority_and_no_pickle(controlled):
    import pickle

    request = controlled.request()
    owner = stage.prepare(request, enabled=True)
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        stage.require_complete_load(owner)
    assert (
        caught.value.stage == "full_load_prerequisites"
        and not caught.value.partial["full_load_or_phase_or_INIT_admitted"]
    )
    for value in (owner, request, stage._ISSUED[owner].lease):
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(value)


def test_graph_refuses_unknown_objects_without_projection(controlled):
    with pytest.raises(stage.graphs.UnsupportedYamlGraph):
        stage.graphs.capture(
            dict(raw=object()), yaml_base=controlled.Yaml, runtime_types=controlled.types
        )


def test_source_prefix_captures_class_cell_without_running_method():
    tree = ast.parse(
        "class P(object):\n def load(self,*args,**kwargs):\n  super().load(*args,**kwargs)"
    )
    code = stage.parameters._method_code(tree.body[0], "load", "<metadata-only>")
    assert code.co_freevars == ("__class__",)


@pytest.mark.parametrize("point", ["source", "capture"])
def test_reentry_poison_refuses_even_when_inner_error_is_caught(
    controlled, monkeypatch, tmp_path, point
):
    h = controlled
    request = h.request()
    inner = []

    def nested():
        with pytest.raises(stage.YamlPrefixRejected) as caught:
            stage.prepare(request, enabled=True)
        inner.append(caught.value)

    if point == "source":
        h.hooks["reader"] = nested
    else:
        original = stage._capture

        def capture(context):
            nested()
            return original(context)

        monkeypatch.setattr(stage, "_capture", capture)
    before = set(stage._ISSUED)
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        stage.prepare(request, enabled=True)
    assert caught.value.partial.invalid and not stage._ACTIVE and set(stage._ISSUED) == before
    assert (
        inner
        and all(e.stage == "reentrant" for e in inner)
        and h.calls == ["reader"]
        and h.context.invalid
    )
    save(tmp_path, "reentry", dict(error=caught.value, inner=inner, synthetic_only=True))


@pytest.mark.parametrize("field", ["p", "trial", "graph", "source", "runtime", "plan"])
def test_commit_requires_original_unloaded_parent_graph_source_and_epoch(controlled, field):
    h = controlled
    request = h.request()

    def mutate():
        if field == "p":
            h.context.p = object()
        elif field == "trial":
            h.context.trial = replace(h.file)
        elif field == "graph":
            h.context.graph = ((), {})
        elif field == "source":
            h.context.source = SimpleNamespace(**vars(h.context.source))
        elif field == "runtime":
            h.context.runtime = ((), (h.Yaml,))
        else:
            h.context.plan = {"path_fields": ()}

    h.hooks["reader"] = mutate
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        stage.prepare(request, enabled=True)
    assert (
        h.calls == ["reader"]
        and caught.value.source_error is not None
        and caught.value.partial.invalid
    )
    assert not stage._ACTIVE and h.context.invalid


@pytest.mark.parametrize("outcome", ["success-return", "source-unwind", "entry"])
def test_inherited_hook_failures_keep_source_cause_and_restore_profile(
    controlled, tmp_path, outcome
):
    h = controlled
    request = h.request()
    source = SyntheticSourceFailure("synthetic parser primary")
    cause = SyntheticSourceCause("original parser cause")
    observation = SyntheticCaptureFailure("synthetic inherited hook refusal")
    reader = stage._prefix(SimpleNamespace()).__code__
    previous, trace = sys.getprofile(), sys.gettrace()
    if outcome == "source-unwind":
        h.errors.update(reader=source, cause=cause)

    def observer(frame, event, arg):
        if frame.f_code is reader and event == ("call" if outcome == "entry" else "return"):
            raise observation
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(observer)
    try:
        with pytest.raises(stage.YamlPrefixRejected) as caught:
            stage.prepare(request, enabled=True)
        assert sys.getprofile() is observer and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)
    error = caught.value
    if outcome == "source-unwind":
        assert (
            error.source_error is source and error.__cause__ is source and source.__cause__ is cause
        )
        assert any(item is observation for _, item in error.capture_errors)
    elif outcome == "entry":
        assert error.source_error is observation and h.calls == [] and error.capture_errors == ()
    else:
        assert error.source_error is None and error.partial.prefix_completed
        assert any(item is observation for _, item in error.capture_errors)
    assert h.context.invalid and not stage._ACTIVE
    save(
        tmp_path,
        "hook-boundary",
        dict(
            error=error,
            source=error.source_error,
            capture_errors=error.capture_errors,
            raw_fields=vars(h.p),
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize("law,release", [(None, "1"), ("foreign", "1"), (stage.LAW_ID, "0")])
def test_parameter_consumption_requires_declared_consumer_and_release(
    controlled, monkeypatch, law, release
):
    h = controlled
    monkeypatch.setenv(stage.parameters.inherited.RELEASE, release)
    with pytest.raises(stage.parameters.ParameterRejected) as caught:
        stage.parameters.begin_yaml_prefix(h.parent, law_id=law)
    assert caught.value.stage == "consumer" and not h.context.invalid and h.calls == []


def test_parameter_lease_keeps_original_owner_and_is_one_shot(controlled):
    h = controlled
    lease = stage.parameters.begin_yaml_prefix(h.parent, law_id=stage.LAW_ID)
    owner, context = stage.parameters._yaml_prefix_parent(lease)
    assert owner is h.parent and context is h.context and context.p is h.p and context.invalid
    with pytest.raises(stage.parameters.ParameterRejected):
        stage.parameters.begin_yaml_prefix(h.parent, law_id=stage.LAW_ID)
    with pytest.raises(stage.parameters.ParameterRejected):
        stage.parameters._yaml_prefix_parent(object())
    assert h.calls == []


def test_declaring_two_requests_cannot_reload_same_live_parent(controlled):
    h = controlled
    first, second = h.request(), h.request()
    owner = stage.prepare(first, enabled=True)
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        stage.prepare(second, enabled=True)
    assert caught.value.stage == "consumed" and h.calls == ["reader"] and owner.parameters is h.p


@pytest.mark.parametrize("bound", ["depth", "nodes", "bytes"])
def test_yaml_capture_bounds_are_enforced_without_parser(controlled, monkeypatch, bound):
    h = controlled
    if bound == "depth":
        monkeypatch.setattr(stage.graphs, "MAX_DEPTH", 1)
        data = [[[1]]]
    elif bound == "nodes":
        monkeypatch.setattr(stage.graphs, "MAX_NODES", 2)
        data = [1, 2, 3]
    else:
        monkeypatch.setattr(stage.graphs, "MAX_BYTES", 2)
        data = "three"
    with pytest.raises(stage.graphs.UnsupportedYamlGraph):
        stage.graphs.capture({"bounded": data}, yaml_base=h.Yaml, runtime_types=h.types)


def test_graph_captures_nan_payloads_sign_zero_type_and_scalar_aliases(controlled):
    h = controlled
    one = struct.unpack(">d", bytes.fromhex("7ff8000000000001"))[0]
    two = struct.unpack(">d", bytes.fromhex("fff8000000000002"))[0]
    zero = -0.0
    shared = "".join(("synthetic", " scalar"))
    values = [one, two, zero, 0.0, 1, True, shared, shared]
    objects, data = stage.graphs.capture(
        {"values": values}, yaml_base=h.Yaml, runtime_types=h.types
    )
    assert any(value is one for value in objects) and any(value is two for value in objects)
    bits = [node["float64"] for node in data["nodes"] if "float64" in node]
    assert bits == ["7ff8000000000001", "fff8000000000002", "8000000000000000", "0000000000000000"]
    edges = data["nodes"][0]["list_storage"]
    assert edges[-1] == edges[-2] and edges[4] != edges[5]


def test_unknown_timestamp_or_callback_state_is_not_serialized(controlled):
    import datetime

    h = controlled
    for value in (datetime.date(2026, 11, 1), lambda: None):
        with pytest.raises(stage.graphs.UnsupportedYamlGraph):
            stage.graphs.capture({"unknown": value}, yaml_base=h.Yaml, runtime_types=h.types)


@pytest.mark.parametrize(
    "mutation", ["relative", "escape", "hardlink", "over-size", "origin", "hash-type"]
)
def test_file_authority_bounds_do_not_issue_a_supplied_configuration(
    controlled, monkeypatch, mutation
):
    h = controlled
    path = h.path
    digest = h.file.sha256
    origin = "declared synthetic input"
    if mutation == "relative":
        path = Path("declared.yaml")
    elif mutation == "escape":
        path = h.path.parent / ".." / h.path.parent.name / h.path.name
    elif mutation == "hardlink":
        h.path.with_name("alias.yaml").hardlink_to(h.path)
    elif mutation == "over-size":
        monkeypatch.setattr(stage, "MAX_FILE_BYTES", 2)
    elif mutation == "origin":
        origin = ""
    else:
        digest = 1
    with pytest.raises((stage.YamlPrefixRejected, ValueError)):
        stage.input_file(path, sha256=digest, origin=origin)
    assert h.calls == [] and not h.context.invalid


def test_supplied_dictionary_is_not_a_prefix_request(controlled):
    h = controlled
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        stage.prepare({"_conf": {"supplied": True}}, enabled=True)
    assert caught.value.stage == "request" and h.calls == [] and not h.context.invalid


def test_source_epoch_changed_after_declaration_refuses_before_load(controlled, monkeypatch):
    h = controlled
    request = h.request()
    plan = stage.source_plan()
    monkeypatch.setattr(stage, "source_plan", lambda: dict(plan, foreign_source_epoch=True))
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        stage.prepare(request, enabled=True)
    assert caught.value.stage == "load_admission" and not h.context.invalid and h.calls == []


@pytest.mark.parametrize("failure", ["missing-file", "path-continuation", "unknown-runtime"])
def test_incomplete_or_unowned_parser_output_never_issues_child(controlled, monkeypatch, failure):
    h = controlled
    original = stage._invoke
    request = h.request()

    def invoke(context):
        value = original(context)
        if failure == "missing-file":
            h.p._conf_filename = None
        elif failure == "path-continuation":
            h.p.init_export_dirname = "/not-a-prefix"
        else:
            h.p._conf.unknown = object()
        return value

    monkeypatch.setattr(stage, "_invoke", invoke)
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        stage.prepare(request, enabled=True)
    assert h.context.invalid and h.calls == ["reader"] and caught.value.partial.prefix_completed
    if failure == "unknown-runtime":
        assert caught.value.source_error is None and caught.value.capture_errors
    else:
        assert caught.value.source_error is not None


@pytest.mark.parametrize("mutation", ["equal-function", "defaults", "cached-builtins"])
def test_actual_prefix_function_and_cached_lookup_authority_cannot_change(controlled, mutation):
    h = controlled

    def mutate():
        context = stage._ACTIVE[-1]
        fn = context.function
        if mutation == "defaults":
            fn.__defaults__ = (None,)
        else:
            namespace = fn.__globals__
            if mutation == "cached-builtins":
                namespace = dict(namespace, __builtins__=dict(fn.__builtins__))
            changed = FunctionType(
                fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__
            )
            if mutation == "cached-builtins":
                namespace["__builtins__"] = fn.__builtins__
            context.function = changed

    h.hooks["reader"] = mutate
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        run(h)
    assert h.calls == ["reader"] and caught.value.source_error is not None and h.context.invalid


def test_trial_cache_contents_and_live_graph_must_match(controlled):
    h = controlled
    owner = run(h)
    context = stage._ISSUED[owner]
    object.__setattr__(context.trial.graph, "descriptor_json", "{}")
    with pytest.raises(stage.YamlPrefixRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "owner_drift" and h.calls == ["reader"]


def test_profiled_source_capture_stop_and_return_error_keep_separate_primary(controlled, tmp_path):
    h = controlled
    primary = stage.parameters.inherited.tissue._CaptureStop("synthetic source stop")
    cause = SyntheticSourceCause("retained source cause")
    capture = SyntheticCaptureFailure("retained return observer error")
    h.errors.update(reader=primary, cause=cause)
    selected = stage._prefix(SimpleNamespace()).__code__
    previous, trace = sys.getprofile(), sys.gettrace()
    observed = []

    def observer(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if frame.f_code is selected and event == "return":
            observed.append(event)
            raise capture

    sys.setprofile(observer)
    try:
        with pytest.raises(stage.YamlPrefixRejected) as caught:
            run(h)
        assert sys.getprofile() is observer and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)
    error = caught.value
    assert observed == ["return"] and error.source_error is primary and error.__cause__ is primary
    assert primary.__cause__ is cause and any(item is capture for _, item in error.capture_errors)
    assert (
        h.context.invalid
        and error.partial.p is h.p
        and not error.partial.prefix_completed
        and not stage._ACTIVE
    )
    save(
        tmp_path,
        "source-stop-and-capture",
        dict(
            primary=error.source_error,
            capture=error.capture_errors,
            raw=vars(h.p),
            synthetic_only=True,
        ),
    )


def test_captured_actual_type_identity_rejects_same_label_layout_and_storage(controlled, tmp_path):
    h = controlled
    original = h.RTSeq
    foreign = type(
        original.__name__,
        original.__bases__,
        dict(__module__=original.__module__, __qualname__=original.__qualname__),
    )
    types = h.types | {foreign}
    value = original(["retained"])
    fields = vars(value)
    before = stage.graphs.capture(
        {"left": value, "right": value}, yaml_base=h.Yaml, runtime_types=types
    )
    value.__class__ = foreign
    after = stage.graphs.capture(
        {"left": value, "right": value}, yaml_base=h.Yaml, runtime_types=types
    )
    assert vars(value) is fields and before[1] == after[1] and foreign is not original
    with pytest.raises(ValueError, match="alias graph changed"):
        stage.parameters.inherited._same_graph(after, before)
    save(
        tmp_path,
        "actual-type-binding",
        dict(graph=after[1], same_labels=True, changed_actual_class=True, synthetic_only=True),
    )


def test_explicit_repaired_parameter_producer_is_not_silently_rebound(monkeypatch):
    monkeypatch.setattr(stage, "PARAMETERS_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="Explicit repaired native parameter producer"):
        stage.source_plan()


@pytest.mark.parametrize(
    "mutation", ["unchanged", "wrapper", "defaults", "class-cell", "cached-builtins", "namespace"]
)
def test_native_loader_executable_prefix_metadata_without_execution(mutation, tmp_path):
    # Compile real original AST without executing its class/module or method.
    # This metadata-only class is never issued as Parameters/INIT authority.
    path = stage.parameters.inherited.tissue.aliases.NATIVE / stage.parameters.PARAMETERS
    node = stage.parameters.inherited._class(ast.parse(path.read_bytes()), "Parameters")
    code = stage.parameters._method_code(node, "load", str(path))
    cls = type("MetadataParameters", (), {})
    module = ModuleType("metadata_only_parameters")
    namespace = vars(module)
    namespace["__builtins__"] = builtins.__dict__

    def cell(value):
        return (lambda: value).__closure__[0]

    assert code.co_freevars == ("__class__",)
    closure = (cell(object() if mutation == "class-cell" else cls),)
    if mutation == "cached-builtins":
        namespace["__builtins__"] = dict(builtins.__dict__)
    original = FunctionType(code, namespace, "load", None, closure)
    if mutation == "cached-builtins":
        namespace["__builtins__"] = builtins.__dict__
        assert original.__builtins__ is not namespace["__builtins__"]
    if mutation == "namespace":
        namespace["__builtins__"] = dict(original.__builtins__)
    cls.load = original
    if mutation == "wrapper":

        def wrapper(*args, **kwargs):
            raise AssertionError("Metadata control may not call a wrapper")

        wrapper.__wrapped__ = original
        cls.load = wrapper
    elif mutation == "defaults":
        original.__defaults__ = (None,)
    context = SimpleNamespace(
        parent=SimpleNamespace(
            source=SimpleNamespace(cls=cls, modules={"betse.science.parameters": module})
        )
    )
    if mutation == "unchanged":
        result = stage._prefix(context)
        selected = stage.parameters.inherited._class(ast.parse(path.read_bytes()), "Parameters")
        method = stage.parameters.inherited._method(selected, "load")
        method.body = method.body[:3]
        expected = stage.parameters._method_code(selected, "load", str(path))
        assert stage.parameters.inherited._code(result.__code__) == (
            stage.parameters.inherited._code(expected)
        )
        assert result.__globals__ is namespace and result.__closure__ is original.__closure__
        assert result.__builtins__ is original.__builtins__
    else:
        with pytest.raises(ValueError):
            stage._prefix(context)
    save(
        tmp_path,
        "loader-metadata",
        dict(mutation=mutation, source_method_invocations=0, synthetic_only=True),
    )


@pytest.mark.parametrize("same_name", [False, True])
def test_live_parameters_class_may_not_change_during_reader(
    controlled, monkeypatch, tmp_path, same_name
):
    h = controlled
    original = type(h.p)
    foreign = type(
        original.__name__ if same_name else "ForeignParameters",
        original.__bases__,
        dict(
            __module__=original.__module__,
            __qualname__=original.__qualname__ if same_name else "ForeignParameters",
        ),
    )
    registry = stage._runtime_types

    def known_types(context):
        kinds, files, bindings = registry(context)
        return kinds | {foreign}, files, bindings

    # Keep the replacement known to the closed synthetic type registry, so
    # an unknown-type refusal cannot stand in for the intended Parameters check.
    monkeypatch.setattr(stage, "_runtime_types", known_types)
    fields = vars(h.p)

    def replace_class():
        h.p.__class__ = foreign

    h.hooks["reader"] = replace_class
    request = h.request()
    result = failure = None
    try:
        result = stage.prepare(request, enabled=True)
    except BaseException as error:
        failure = error
    save(
        tmp_path,
        "typed-parameter-attempt",
        dict(
            issued_child=result is not None,
            failure=failure,
            original_type_label=original.__module__ + "." + original.__qualname__,
            actual_type_label=type(h.p).__module__ + "." + type(h.p).__qualname__,
            actual_type_changed=type(h.p) is not original,
            exact_p_and_dictionary_retained=vars(h.p) is fields,
            parent_retired=h.context.invalid,
            calls=h.calls,
            raw_fields=vars(h.p),
            synthetic_only=True,
            independent_biological_cases=0,
        ),
    )
    assert h.calls == ["reader"] and type(h.p) is foreign and vars(h.p) is fields
    assert h.context.source.cls is original and h.context.invalid
    assert result is None and isinstance(failure, stage.YamlPrefixRejected)
    assert failure.stage == "native_yaml_read_prefix" and failure.partial.prefix_completed
    assert type(failure.source_error) is ValueError
    assert str(failure.source_error) == "Original native Parameters class changed"
    assert failure.partial.p is h.p and failure.partial.invalid and not stage._ACTIVE
    assert all(context is not failure.partial for context in stage._ISSUED.values())
