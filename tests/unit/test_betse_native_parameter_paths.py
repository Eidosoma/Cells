"""Conditional compatibility/path transport; original bodies and writes held."""

import builtins
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_paths as stage
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

ORIGINAL_NATIVE = stage._native


def test_wrapper_metadata_reload_uses_body_globals_but_retains_actual_wrapper(
    monkeypatch, tmp_path
):
    from types import ModuleType

    from tests.unit.test_betse_native_phase_parameters import _wrapped_parameter_metadata

    h = _wrapped_parameter_metadata("reload_paths", monkeypatch)
    dirs = ModuleType("betse.util.path.dirs")
    dirs.make_unless_dir = lambda *args: (_ for _ in ()).throw(AssertionError("No directory calls"))
    h.original.__globals__["dirs"] = dirs
    compat = ModuleType("betse.science.compat.compatconf")
    compat.__file__ = str(stage.prefix.parameters.inherited.tissue.aliases.NATIVE / stage.COMPAT)
    for name in (*stage.VERSIONS, stage.EXPORT_UPGRADE, "upgrade_sim_conf"):
        setattr(
            compat,
            name,
            lambda *args: (_ for _ in ()).throw(AssertionError("No compatibility calls")),
        )
    monkeypatch.setitem(sys.modules, dirs.__name__, dirs)
    monkeypatch.setitem(sys.modules, compat.__name__, compat)
    monkeypatch.setattr(
        stage.prefix.parameters.inherited.tissue.aliases, "_check_modules", lambda: None
    )
    p = object()
    filename = "metadata-only.yaml"
    native = stage.prefix.parameters.inherited.tissue.aliases.NATIVE
    yaml = SimpleNamespace(
        p=p,
        parent=SimpleNamespace(source=h.source),
        request=SimpleNamespace(file=SimpleNamespace(filename=filename)),
        locals={
            (str(native / stage.prefix.parameters.PARAMETERS), "Parameters.load"): dict(
                self=p,
                args=(filename,),
                kwargs={},
                YAML_VERSION="1.2",
                __class__=h.source.cls,
                compatconf=compat,
            )
        },
    )
    value = ORIGINAL_NATIVE(yaml)
    assert value.reload is h.wrapper and value.mkdir is dirs.make_unless_dir
    assert "dirs" not in h.wrapper.__globals__
    save(tmp_path, "wrapped-path-lookup", dict(source_body_calls=0, directory_calls=0))


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    attempts = []
    old, trace, imp = sys.getprofile(), sys.gettrace(), builtins.__import__
    real = {
        stage._upgrade.__code__,
        stage._reload.__code__,
        stage.prefix._invoke.__code__,
        stage.prefix.parameters._acquire.__code__,
        stage.prefix.parameters._invoke.__code__,
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in real
            or frame.f_code.co_filename.startswith(
                str(stage.prefix.parameters.inherited.tissue.aliases.NATIVE) + "/"
            )
        ):
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native/parser/path body forbidden")
        if old is not None:
            old(frame, event, arg)

    def imports(name, *args, **kwargs):
        if name == "betse" or name.startswith(("betse.", "ruamel")):
            attempts.append(name)
            raise AssertionError("Actual native/parser import forbidden")
        return imp(name, *args, **kwargs)

    def rng(*args, **kwargs):
        attempts.append("RNG")
        raise AssertionError("Actual RNG forbidden")

    monkeypatch.setattr(builtins, "__import__", imports)
    for name in ("RandomState", "default_rng", "seed", "random", "normal", "uniform", "choice"):
        monkeypatch.setattr(stage.prefix.parameters.inherited.tissue.callers.np.random, name, rng)
    sys.setprofile(profile)
    try:
        yield
        assert not attempts and sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(old)
        sys.settrace(trace)
        (tmp_path / "native-blocked.json").write_text(
            json.dumps(
                dict(
                    nodeid=request.node.nodeid,
                    attempted=attempts,
                    actual_native_parser_RNG_path_writes=0,
                )
            )
        )


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, plan):
    monkeypatch.setattr(stage, "BASE", tmp_path)
    monkeypatch.setattr(stage.prefix, "BASE", tmp_path)
    file_path = tmp_path / "source.yaml"
    data = b"explicit synthetic source; no native parsing\n"
    file_path.write_bytes(data)
    file_path.chmod(0o444)
    import hashlib

    file = stage.prefix.input_file(
        file_path, sha256=hashlib.sha256(data).hexdigest(), origin="conditional software input only"
    )
    birth_plan = stage.prefix.parameters.source_plan()

    class Yaml:
        def __init__(self):
            self._conf = None

    class Child(Yaml):
        pass

    class ChildList(Yaml):
        def __init__(self):
            super().__init__()
            self._item_type = Child

    class Params(Yaml):
        def __init__(self):
            super().__init__()
            self._conf = {"synthetic_source": True}
            self._conf_filename = file.filename
            self._conf_dirname = str(file_path.parent)
            self._conf_basename = file_path.name
            for name in birth_plan["path_fields"]:
                setattr(self, name, None)
            for name in stage.prefix.parameters._ROSTER:
                setattr(self, name, ChildList() if name.endswith("profiles") else Child())

    p = Params()
    original_config = p._conf
    types = frozenset((Yaml, Child, ChildList, Params))
    runtime = ((), (Params,))
    birth = SimpleNamespace(source=SimpleNamespace(cls=Params, yaml=Yaml), runtime=runtime)
    graph = ((), {})
    cache = stage.prefix.parameters.inherited.tissue.core.caches.snapshot({"synthetic_yaml": True})
    owner = object.__new__(stage.prefix.YamlPrefixOwner)
    yaml = SimpleNamespace(
        p=p,
        parent=birth,
        trial=SimpleNamespace(identity="synthetic_read_epoch", graph=cache),
        graph=graph,
        invalid=False,
        active=False,
        locals={},
        request=SimpleNamespace(file=file),
        runtime_types=types,
        file_record=stage.prefix.file_record(file),
        bindings=None,
    )
    result_root = tmp_path / "original-output"
    derived = {name: str(result_root / name) for name in stage.FIELDS}
    derived["grn_unpickle_filename"] = None
    policy = stage.declare_paths(paths=tuple(derived.items()), law_id=stage.LAW_ID)
    calls, hooks, errors = [], {}, {}

    def tick(name):
        calls.append(name)
        if name in hooks:
            hooks[name]()
        if name in errors:
            raise errors[name] from errors.get("cause")

    def step0(q):
        tick(stage.VERSIONS[1])
        q._conf["synthetic_upgrade"] = "0.5.0"

    def step1(q):
        tick(stage.VERSIONS[2])

    def step2(q):
        tick(stage.VERSIONS[3])

    def step3(q):
        tick(stage.VERSIONS[4])

    def exports(q):
        tick(stage.EXPORT_UPGRADE)

    def step4(q):
        tick(stage.VERSIONS[5])
        exports(q)

    def upgrade(q):
        tick(stage.VERSIONS[0])
        q.config = q._conf
        step0(q)
        step1(q)
        step2(q)
        step3(q)
        step4(q)

    def mkdir(*dirnames):
        tick("make_unless_dir")
        # Audit observations only: no actual directory syscall occurs.
        for name in dirnames:
            sys.audit("os.mkdir", name, 0o777, -1)

    def reload(q):
        tick("reload_paths")
        for name, value in derived.items():
            setattr(q, name, value)
        q.grn_config_filename_relative = "synthetic-relative"
        mkdir(*(derived[name] for name in stage.DIRECTORIES))
        if "second_directory" in hooks:
            mkdir(*(derived[name] for name in stage.DIRECTORIES))

    methods = dict(
        zip(
            (*stage.VERSIONS, stage.EXPORT_UPGRADE),
            (upgrade, step0, step1, step2, step3, step4, exports),
            strict=True,
        )
    )
    native = SimpleNamespace(
        compat=SimpleNamespace(), upgrade=upgrade, reload=reload, mkdir=mkdir, methods=methods
    )

    def validate(value):
        if value is not owner or yaml.invalid:
            raise stage.prefix.YamlPrefixRejected(
                "Unissued/retired synthetic read owner", stage="owner"
            )
        return yaml

    def native_resolve(value):
        if value is not yaml:
            raise AssertionError("Foreign synthetic read context")
        return native

    def native_bindings(context):
        return ((), (native, native.upgrade, native.reload, native.mkdir))

    def runtime_types(context):
        return types, {}, ((), (Params,))

    def invoke_upgrade(context):
        context.work.append(
            dict(layer="synthetic_source", method="upgrade", status="entered_not_native_credit")
        )
        return context.native.upgrade(context.p)

    def invoke_reload(context):
        context.work.append(
            dict(layer="synthetic_source", method="reload", status="entered_not_native_credit")
        )
        return context.native.reload(context.p)

    monkeypatch.setattr(stage.prefix, "_validate", validate)
    monkeypatch.setattr(stage, "_native", native_resolve)
    monkeypatch.setattr(stage, "_native_bindings", native_bindings)
    monkeypatch.setattr(stage.prefix.parameters, "_runtime", lambda source: runtime)
    monkeypatch.setattr(stage.prefix, "_runtime_types", runtime_types)
    monkeypatch.setattr(stage, "_directories_complete", lambda context: True)
    monkeypatch.setattr(stage, "_upgrade", invoke_upgrade)
    monkeypatch.setattr(stage, "_reload", invoke_reload)
    monkeypatch.setattr(stage, "source_plan", lambda: dict(plan, synthetic_only=True))
    monkeypatch.setenv(stage.RELEASE, "1")
    monkeypatch.setenv(stage.prefix.parameters.inherited.RELEASE, "1")
    yaml.bindings = stage.prefix._bindings()
    return SimpleNamespace(
        p=p,
        config=original_config,
        yaml=yaml,
        owner=owner,
        policy=policy,
        derived=derived,
        native=native,
        hooks=hooks,
        errors=errors,
        calls=calls,
        file=file,
        result_root=result_root,
        types=types,
        request=lambda: stage.from_yaml(owner, policy, law_id=stage.LAW_ID),
    )


def run(h):
    return stage.prepare(h.request(), enabled=True)


def test_original_continuation_order_and_stop_boundary(plan):
    assert len(plan["native_pins"]) == 272 and plan["compatibility_order"] == stage.VERSIONS
    assert plan["next_source_line"] > plan["continuation_lines"][1]
    assert not plan["subconfigurations_ions_phase_INIT_admitted"]


@pytest.mark.parametrize(
    "enabled,local,base", [(False, "1", "1"), (True, "0", "1"), (True, "1", "0"), (1, "1", "1")]
)
def test_release_gates_precede_any_parent_native_or_filesystem_work(
    monkeypatch, enabled, local, base
):
    monkeypatch.setenv(stage.RELEASE, local)
    monkeypatch.setenv(stage.prefix.parameters.inherited.RELEASE, base)
    with pytest.raises(stage.PathsRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"


@pytest.mark.parametrize(
    "value", [None, {}, SimpleNamespace(), object.__new__(stage.prefix.YamlPrefixOwner)]
)
def test_unissued_read_owner_or_receipt_cannot_supply_configuration(plan, value):
    with pytest.raises(stage.prefix.YamlPrefixRejected, match="Issued YAML prefix owner"):
        stage.from_yaml(value, None, law_id=stage.LAW_ID)


def test_same_p_config_ancestry_native_order_and_unloaded_subconfigs_retained(controlled, tmp_path):
    h = controlled
    request = h.request()
    before = tuple((name, getattr(h.p, name)) for name in stage.prefix.parameters._ROSTER)
    owner = stage.prepare(request, enabled=True)
    assert (
        owner.parameters is h.p
        and h.p._conf is h.config
        and h.p.config is h.config
        and h.yaml.invalid
    )
    assert tuple(h.calls) == (
        *stage.VERSIONS,
        stage.EXPORT_UPGRADE,
        "reload_paths",
        "make_unless_dir",
    )
    assert all(getattr(h.p, name) is child and child._conf is None for name, child in before)
    assert len(owner.trial.work) == 2 and len(owner.trial.filesystem) == 5
    assert not h.result_root.exists()
    with pytest.raises(stage.PathsRejected) as caught:
        stage.prepare(request, enabled=True)
    assert caught.value.stage == "consumed"
    save(
        tmp_path,
        "continued",
        dict(
            trial=owner.trial,
            graph=stage._ISSUED[owner].graph[1],
            no_actual_directories=True,
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize("mutation", ["missing", "order", "relative", "outside", "copy"])
def test_path_permissions_are_complete_explicit_and_not_hydration(controlled, mutation):
    h = controlled
    items = h.policy.paths
    if mutation == "copy":
        with pytest.raises(stage.PathsRejected):
            stage.from_yaml(h.owner, replace(h.policy), law_id=stage.LAW_ID)
        return
    if mutation == "missing":
        items = items[:-1]
    elif mutation == "order":
        items = tuple(reversed(items))
    else:
        items = (
            (items[0][0], "relative" if mutation == "relative" else "/outside/namespace"),
            *items[1:],
        )
    with pytest.raises((stage.PathsRejected, ValueError)):
        stage.declare_paths(paths=items, law_id=stage.LAW_ID)
    assert (
        h.calls == []
        and not h.yaml.invalid
        and all(vars(h.p)[n] is None for n in stage.DIRECTORIES)
    )


@pytest.mark.parametrize("point", [*stage.VERSIONS, "reload_paths", "make_unless_dir"])
def test_raw_native_shaped_failure_cause_partials_and_retired_epoch_retained(
    controlled, tmp_path, point
):
    h = controlled
    primary = SyntheticSourceFailure("source failure at " + point)
    cause = SyntheticSourceCause("original cause")
    h.errors.update({point: primary, "cause": cause})
    with pytest.raises(stage.PathsRejected) as caught:
        run(h)
    error = caught.value
    assert (
        error.source_error is primary and error.__cause__ is primary and primary.__cause__ is cause
    )
    assert h.yaml.invalid and error.partial.p is h.p and error.partial.invalid and not stage._ACTIVE
    assert all(ctx is not error.partial for ctx in stage._ISSUED.values())
    save(
        tmp_path,
        "source-failure",
        dict(
            primary=error.source_error,
            capture=error.capture_errors,
            work=error.partial.work,
            calls=error.partial.calls,
            raw=vars(h.p),
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize(
    "change",
    ["different-path", "config-root", "config-alias", "subconfig", "class", "unrelated-store"],
)
def test_changed_actual_configuration_owner_or_stores_refuse_before_directory_body(
    controlled, change
):
    h = controlled

    def alter():
        if change == "different-path":
            h.derived["init_pickle_filename"] = str(h.result_root / "foreign")
        elif change == "config-root":
            h.p._conf = dict(h.p._conf)
        elif change == "config-alias":
            h.p.config = {}
        elif change == "subconfig":
            h.p.tissue_default._conf = {}
        elif change == "class":
            h.p.__class__ = type("Foreign", type(h.p).__bases__, {})
        else:
            h.p.unrelated_state = "foreign"

    h.hooks[
        "reload_paths" if change in {"different-path", "config-alias"} else stage.VERSIONS[-1]
    ] = alter
    with pytest.raises(stage.PathsRejected) as caught:
        run(h)
    assert caught.value.source_error is not None and h.yaml.invalid and not h.result_root.exists()
    assert h.calls.count("make_unless_dir") == 0


@pytest.mark.parametrize("operation", ["mkdir", "open", "rename"])
def test_unexpected_real_filesystem_attempts_are_refused_before_writes(
    controlled, tmp_path, operation
):
    h = controlled
    target = tmp_path / "forbidden-write"

    def attempt():
        if operation == "mkdir":
            os.mkdir(target)
        elif operation == "open":
            target.write_text("forbidden")
        else:
            os.rename(h.file.filename, target)

    h.hooks[stage.VERSIONS[1]] = attempt
    with pytest.raises(stage.PathsRejected) as caught:
        run(h)
    assert (
        type(caught.value.source_error) is ValueError
        and not target.exists()
        and Path(h.file.filename).is_file()
    )
    assert h.yaml.invalid and h.calls.count("reload_paths") == 0
    save(
        tmp_path,
        "blocked-filesystem",
        dict(operation=operation, error=caught.value, actual_path_writes=0, synthetic_only=True),
    )


@pytest.mark.parametrize("swallow", [False, True])
def test_reentrant_continuation_cannot_issue_child_or_repeat_upgrade(controlled, swallow):
    h = controlled
    request = h.request()
    inner = []

    def nested():
        try:
            stage.prepare(request, enabled=True)
        except stage.PathsRejected as error:
            inner.append(error)
            if not swallow:
                raise

    h.hooks[stage.VERSIONS[1]] = nested
    with pytest.raises(stage.PathsRejected) as caught:
        stage.prepare(request, enabled=True)
    assert len(inner) == 1 and inner[0].stage == "reentrant" and caught.value.partial.invalid
    assert h.calls.count(stage.VERSIONS[0]) == 1 and not stage._ACTIVE


def test_duplicate_directory_call_is_not_independent_work_or_success(controlled):
    h = controlled
    h.hooks["second_directory"] = lambda: None
    with pytest.raises(stage.PathsRejected) as caught:
        run(h)
    assert (
        h.calls.count("make_unless_dir") == 1
        and caught.value.partial.directory_calls == 1
        and h.yaml.invalid
    )


@pytest.mark.parametrize("source_failure", [False, True])
def test_profile_return_capture_and_primary_cause_remain_separate(
    controlled, tmp_path, source_failure
):
    h = controlled
    request = h.request()
    primary = stage.prefix.parameters.inherited.tissue._CaptureStop("source stop")
    cause = SyntheticSourceCause("source cause")
    capture = SyntheticCaptureFailure("return capture")
    if source_failure:
        h.errors.update({stage.VERSIONS[2]: primary, "cause": cause})
    selected = h.native.methods[stage.VERSIONS[2]].__code__
    old, trace = sys.getprofile(), sys.gettrace()
    seen = []

    def prior(frame, event, arg):
        if old is not None:
            old(frame, event, arg)
        if frame.f_code is selected and event == "return":
            seen.append(event)
            raise capture

    sys.setprofile(prior)
    try:
        with pytest.raises(stage.PathsRejected) as caught:
            stage.prepare(request, enabled=True)
        assert sys.getprofile() is prior and sys.gettrace() is trace
    finally:
        sys.setprofile(old)
        sys.settrace(trace)
    error = caught.value
    assert seen == ["return"] and error.source_error is (primary if source_failure else None)
    assert error.__cause__ is (primary if source_failure else capture)
    if source_failure:
        assert primary.__cause__ is cause
    assert any(e is capture for _, e in error.capture_errors) and h.calls.count("reload_paths") == 0
    save(
        tmp_path,
        "source-and-capture",
        dict(
            primary=error.source_error,
            capture=error.capture_errors,
            locals=error.partial.locals,
            synthetic_only=True,
        ),
    )


def test_actual_retained_import_is_required_before_retiring_read_owner(controlled, monkeypatch):
    h = controlled
    monkeypatch.setattr(stage, "_native", ORIGINAL_NATIVE)
    with pytest.raises(stage.PathsRejected) as caught:
        h.request()
    assert caught.value.stage == "retained_import" and not h.yaml.invalid and h.calls == []


@pytest.mark.parametrize("mutation", ["path", "config-alias", "subconfig", "file", "cache"])
def test_completed_path_owner_rejects_later_binding_graph_or_cache_drift(controlled, mutation):
    h = controlled
    owner = run(h)
    context = stage._ISSUED[owner]
    if mutation == "path":
        h.p.init_pickle_filename = str(h.result_root / "changed")
    elif mutation == "config-alias":
        h.p.config = dict(h.p._conf)
    elif mutation == "subconfig":
        h.p.csv._conf = {}
    elif mutation == "file":
        Path(h.file.filename).chmod(0o644)
    else:
        object.__setattr__(context.trial.cache, "descriptor_json", "{}")
    with pytest.raises(stage.PathsRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "owner_drift" and context.invalid


def test_no_subconfiguration_ion_phase_or_pickle_admission(controlled):
    import pickle

    h = controlled
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    with pytest.raises(stage.PathsRejected) as caught:
        stage.require_complete_load(owner)
    assert (
        caught.value.stage == "full_load_prerequisites"
        and not caught.value.partial["full_parameters_or_phase_or_INIT_admitted"]
    )
    for value in (request, owner):
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(value)


def test_preopened_file_writer_is_refused_before_content_write(controlled, tmp_path):
    h = controlled
    path = tmp_path / "preopened-log"
    with path.open("w") as stream:
        h.hooks[stage.VERSIONS[1]] = lambda: stream.write("forbidden")
        with pytest.raises(stage.PathsRejected) as caught:
            run(h)
    assert type(caught.value.source_error) is ValueError
    assert str(caught.value.source_error) == "Unowned pre-opened file writer refused"
    assert path.read_bytes() == b"" and h.yaml.invalid
    save(tmp_path, "preopened-write-refusal", dict(error=caught.value, content_writes=0))


def test_undeclared_directory_inside_original_helper_is_refused(controlled, tmp_path):
    h = controlled
    target = tmp_path / "undeclared-directory"
    h.hooks["make_unless_dir"] = lambda: os.mkdir(target)
    with pytest.raises(stage.PathsRejected) as caught:
        run(h)
    assert type(caught.value.source_error) is ValueError
    assert str(caught.value.source_error) == "Undeclared directory write refused"
    assert not target.exists() and not h.result_root.exists() and h.yaml.invalid
    save(tmp_path, "undeclared-directory-refusal", dict(error=caught.value, actual_path_writes=0))


def test_capture_failure_keeps_completed_source_flags_and_raw_partial(
    controlled, monkeypatch, tmp_path
):
    h = controlled
    error = SyntheticCaptureFailure("final graph capture failed")

    def fail(context):
        raise error

    monkeypatch.setattr(stage.prefix.parameters.inherited.tissue.core.caches, "snapshot", fail)
    with pytest.raises(stage.PathsRejected) as caught:
        run(h)
    failure = caught.value
    assert failure.source_error is None and failure.__cause__ is error
    assert any(item is error for _, item in failure.capture_errors)
    assert failure.partial.upgrade_completed and failure.partial.paths_completed
    assert failure.partial.p is h.p and h.yaml.invalid and not stage._ACTIVE
    assert not h.result_root.exists()
    save(
        tmp_path,
        "completed-source-capture-refusal",
        dict(
            error=failure,
            partial=vars(h.p),
            calls=failure.partial.calls,
            filesystem=failure.partial.filesystem,
            synthetic_only=True,
        ),
    )


def test_two_issued_requests_cannot_consume_the_same_read_epoch(controlled):
    h = controlled
    first, second = h.request(), h.request()
    owner = stage.prepare(first, enabled=True)
    with pytest.raises(stage.PathsRejected) as caught:
        stage.prepare(second, enabled=True)
    assert caught.value.stage == "consumed"
    assert owner.parameters is h.p and h.calls.count(stage.VERSIONS[0]) == 1
