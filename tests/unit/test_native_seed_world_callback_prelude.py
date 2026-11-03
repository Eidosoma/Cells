"""Native-blocked dispatcher/policy controls; no synthetic owner is admission."""

import ast
import json
import os
from contextlib import contextmanager
from types import FunctionType, ModuleType
from types import SimpleNamespace as NS

import pytest
from PIL import Image

from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import native_seed_world_callback_prelude as stage
from validation.betse import native_seed_world_callback_prelude_software as software

_RAW_GUARDS = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit native-blocked callback-prelude software release required")
    request.config.option.maxfail = 1
    adapter = NS(**dict(vars(software), reuse=software.base.reuse.reuse))
    namespace = dict(vars(guards), software=adapter, _BLOCKADE_FAILURES=())
    fn = FunctionType(guards._blockade.__wrapped__.__code__, namespace)
    try:
        with contextmanager(fn)(request, tmp_path):
            yield
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARDS.append(namespace["_BLOCKADE_FAILURES"])


def test_source_scope_auxiliary_ancestry_and_native_filesystem_conflict_are_explicit():
    plan = stage.source_plan()
    assert len(plan["native_order"]) == 6 and plan["before_first_betse_import"]
    assert plan["actual_application_observation_required"]
    assert not plan["auxiliary_objects_are_world_parameter_or_phase_sim_authority"]
    assert plan["runtime_source"] is plan["runtime_review"] is None
    assert plan["preserve_existing_native_testing_branch"]
    assert plan["filesystem_conflicts"]["native_HOME_unchanged"]
    assert plan["filesystem_conflicts"][
        "strict_mnt_output_policy_conflicts_with_default_native_dot_directory"
    ]
    assert not plan["native_or_scientific_release"] and Image.__name__ == "PIL.Image"


@pytest.mark.parametrize(
    "enabled,release", [(False, None), (True, None), (False, "1"), (True, "1")]
)
def test_unreleased_or_unbound_public_entry_never_accesses_foreign_inputs(
    enabled, release, monkeypatch
):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("No foreign parent/path/state may be consulted")

    if release is None:
        monkeypatch.delenv(stage.RELEASE, raising=False)
    else:
        monkeypatch.setenv(stage.RELEASE, release)
    with pytest.raises(stage.PreludeRejected) as caught:
        stage.acquire_callback(
            Foreign(), Foreign(), bootstrap=Foreign(), bootstrap_sha256="x", enabled=enabled
        )
    if enabled and release == "1":
        assert caught.value.__cause__.stage == "unbound"
        assert caught.value.partial.callback is None
    else:
        assert caught.value.stage == "release"
    assert stage._ACTIVE == []


@pytest.mark.parametrize(
    "existing", [{}, {"numpy": object()}, {"betse": object()}, {"betse.science.cells": object()}]
)
def test_preinitialized_native_state_refuses_without_removing_or_resetting_it(existing):
    original = dict(existing)
    check = FunctionType(stage._fresh_native.__code__, dict(vars(stage), sys=NS(modules=existing)))
    if any(name.startswith("betse") for name in existing):
        with pytest.raises(stage.PreludeRejected) as caught:
            check()
        assert caught.value.stage == "native_before" and caught.value.partial == tuple(existing)
    else:
        assert check() is None
    assert existing == original and all(existing[name] is value for name, value in original.items())


class Evidence:
    def __init__(self, failure=None):
        self.rows, self.failure = [], failure

    def save(self, label, value):
        self.rows.append((label, value))
        return label != self.failure


def metadata_modules(failure=None):
    calls, owners = [], []
    primary = ValueError("unchanged source primary")
    primary.__cause__ = KeyError("unchanged cause")
    for_label = {}
    for label, method in (
        ("tissue", "from_configuration"),
        ("simulator", "from_tissue"),
        ("callbacks", "from_simulator"),
    ):

        def request(parent, *, law_id, label=label):
            calls.append((label + "_request", parent))
            if failure == label + "_request":
                raise primary
            assert law_id == label
            return NS(parent=parent)

        def prepare(request, label=label, **kwargs):
            calls.append((label, request))
            assert kwargs == ({} if label == "tissue" else dict(enabled=True))
            if failure == label:
                raise primary
            owner = NS(trial=NS(cache=None, factory_completed=label == "callbacks"))
            owners.append(owner)
            return owner

        module = NS(
            LAW_ID=label, prepare=prepare, trial_record=lambda trial: dict(cache=trial.cache)
        )
        setattr(module, method, request)
        for_label[label] = module
    app, cache = object(), (True, False)
    for_label["callbacks"]._validate = lambda owner: NS(
        owner=owner, trial=owner.trial, source=NS(app=app), after=NS(cache=cache)
    )
    return for_label, calls, owners, primary, app, cache


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "tissue_request",
        "tissue",
        "simulator_request",
        "simulator",
        "callbacks_request",
        "callbacks",
    ],
)
def test_private_dispatch_retains_real_return_order_or_original_failure_without_any_native_body(
    failure,
):
    modules, calls, owners, primary, app, cache = metadata_modules(failure)
    state, evidence = stage.Execution(), Evidence()
    configuration = dict(declared="auxiliary control only")
    if failure is None:
        returned = stage._execute(state, modules, configuration, evidence)
        assert returned is state.callback is owners[-1] and state.completed
        assert state.observed_application is app and state.observed_testing_cache is cache
        assert [name for name, _ in state.parents] == ["tissue", "simulator", "callbacks"]
    else:
        with pytest.raises(ValueError) as caught:
            stage._execute(state, modules, configuration, evidence)
        assert caught.value is state.source_error is primary
        assert primary.__cause__.args == ("unchanged cause",)
        assert state.callback is None and not state.completed
        assert calls[-1][0] == failure
    assert calls[0][1] is configuration
    if owners:
        assert state.last_return is owners[-1] or failure.endswith("_request") is False


@pytest.mark.parametrize("label", ["tissue.trial", "simulator.cache", "callbacks.trial"])
def test_raw_return_and_original_parents_survive_observation_refusal_before_next_source(label):
    modules, calls, owners, _, _, _ = metadata_modules()
    state = stage.Execution()
    with pytest.raises(RuntimeError, match="typed observation refused") as caught:
        stage._execute(state, modules, {}, Evidence(label))
    assert state.last_return is owners[-1] is state.parents[-1][1]
    assert state.capture_errors[-1][1] is caught.value and state.source_error is None
    assert not state.completed and state.callback is None
    expected_last = label.split(".")[0]
    assert calls[-1][0] == expected_last


@pytest.mark.parametrize("swallow", [False, True])
def test_caught_or_uncaught_reentry_poison_prevents_any_usable_return(swallow, monkeypatch):
    monkeypatch.setenv(stage.RELEASE, "1")
    calls, states, returned = [], [], NS()
    active = []
    namespace = dict(vars(stage), _ACTIVE=active, _RETAINED={})
    public = FunctionType(stage.acquire_callback.__code__, namespace)

    def actual(state, *args, **kwargs):
        calls.append("delegate")
        states.append(state)
        try:
            public({}, "unused", bootstrap="unused", bootstrap_sha256="x", enabled=True)
        except stage.PreludeRejected:
            if not swallow:
                raise
        state.callback, state.completed = returned, True
        return returned

    namespace["_acquire_callback"] = actual
    with pytest.raises(stage.PreludeRejected) as caught:
        public({}, "unused", bootstrap="unused", bootstrap_sha256="x", enabled=True)
    assert calls == ["delegate"] and active == []
    assert caught.value.__cause__ is states[0].entry_error
    assert namespace["_RETAINED"] == {} and caught.value.partial is states[0]


@pytest.mark.parametrize("mutation", [None, "signed_zero", "body"])
def test_callable_authentication_uses_original_typed_code_and_never_executes_it(tmp_path, mutation):
    path = tmp_path / "metadata_only.py"
    path.write_text("def declared():\n    return 0.0\n")
    code = next(
        value
        for value in compile(path.read_bytes(), str(path), "exec").co_consts
        if isinstance(value, type((lambda: None).__code__))
    )
    module = ModuleType("metadata_only")
    module.__file__ = str(path)
    module.declared = FunctionType(code, vars(module))
    if mutation is not None:
        value = -0.0 if mutation == "signed_zero" else 1.0
        module.declared.__code__ = code.replace(
            co_consts=tuple(value if type(item) is float else item for item in code.co_consts)
        )
        with pytest.raises(stage.PreludeRejected) as caught:
            stage._function(module, "declared")
        assert caught.value.stage == "function"
    else:
        assert stage._function(module, "declared") is module.declared


@pytest.mark.parametrize(
    "mutation", [None, "strict_mnt_only", "broad_root", "foreign_env", "reused_mpl"]
)
def test_bootstrap_declares_native_home_conflict_without_changing_HOME_or_any_runtime(
    tmp_path, mutation
):
    home = str(stage.Path.home() / ".betse")
    mpl = str(tmp_path / "mpl-cache")
    environment = dict(HOME=os.environ.get("HOME"), MPLCONFIGDIR=mpl, PYTHONDONTWRITEBYTECODE="1")
    declaration = dict(
        kind=stage.KIND,
        runtime={},
        environment=dict(environment),
        native_write_roots=[home, mpl],
        native_links={},
        Root_review="a" * 64,
    )
    if stage.Path(home).is_symlink():
        declaration["native_links"][home] = stage._link_record(stage.Path(home))
        declaration["native_write_roots"].append(declaration["native_links"][home]["resolved"])
    if mutation == "strict_mnt_only":
        declaration["native_write_roots"].remove(home)
    if mutation == "broad_root":
        declaration["native_write_roots"].append("/")
    if mutation == "foreign_env":
        declaration["environment"]["HOME"] = "/never-set-or-used"
    if mutation == "reused_mpl":
        stage.Path(mpl).mkdir()
    path = tmp_path / "bootstrap.json"
    path.write_text(json.dumps(declaration))
    namespace = dict(vars(stage), os=NS(environ=environment))
    validate = FunctionType(stage._bootstrap_input.__code__, namespace)
    if mutation is None:
        assert validate(path, stage.snapshot.digest(path), tmp_path / "fresh") == declaration
    else:
        with pytest.raises(stage.PreludeRejected):
            validate(path, stage.snapshot.digest(path), tmp_path / "fresh")
    assert environment["HOME"] == os.environ.get("HOME")
    assert not (tmp_path / "fresh").exists()
    assert (tmp_path / "mpl-cache").exists() is (mutation == "reused_mpl")


def test_no_live_prelude_state_checkpoint_or_native_import_at_module_scope():
    with pytest.raises(TypeError, match="hydration"):
        stage.Execution().__reduce_ex__(4)
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and (
            (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("betse"))
            or (
                isinstance(node, ast.Import)
                and any(name.name.startswith("betse") for name in node.names)
            )
        )
        for node in tree.body
    )


@pytest.mark.parametrize("replacement", [False, 0, "callable"])
def test_keyword_default_type_or_hidden_delegate_cannot_retarget_original_code(
    tmp_path, replacement
):
    path = tmp_path / "keyword_metadata.py"
    path.write_text("def declared(*, enabled=False):\n    return enabled\n")
    compiled = compile(path.read_bytes(), str(path), "exec")
    code = next(
        value for value in compiled.co_consts if isinstance(value, type((lambda: None).__code__))
    )
    module = ModuleType("keyword_metadata")
    module.__file__ = str(path)
    module.declared = FunctionType(code, vars(module))
    calls = []
    value = (lambda: calls.append("forbidden")) if replacement == "callable" else replacement
    module.declared.__kwdefaults__ = dict(enabled=value)
    if replacement is False:
        assert stage._function(module, "declared") is module.declared
    else:
        with pytest.raises(stage.PreludeRejected):
            stage._function(module, "declared")
    assert calls == []


@pytest.mark.parametrize("when", ["before", "return", "source_unwind"])
def test_original_cache_link_binding_refuses_retarget_and_retains_return_or_primary(tmp_path, when):
    first, second, link = tmp_path / "first", tmp_path / "second", tmp_path / "link"
    first.mkdir()
    second.mkdir()
    link.symlink_to(first, target_is_directory=True)
    record = json.dumps(stage._link_record(link), sort_keys=True, allow_nan=False)
    state = stage.Execution(path_links=((str(link), record),))
    calls, returned, primary = [], object(), ValueError("original source")
    primary.__cause__ = KeyError("same cause")

    def retarget():
        link.unlink()
        link.symlink_to(second, target_is_directory=True)

    def delegate():
        calls.append("one actual delegate")
        retarget()
        if when == "source_unwind":
            raise primary
        return returned

    if when == "before":
        retarget()
    with pytest.raises((stage.PreludeRejected, ValueError)) as caught:
        stage._operation(state, "metadata_control", delegate)
    if when == "before":
        assert calls == [] and state.last_return is state.source_error is None
    elif when == "return":
        assert state.last_return is returned and state.source_error is None
        assert state.operations[-1]["returned"] is returned
    else:
        assert caught.value is state.source_error is primary
        assert primary.__cause__.args == ("same cause",)
        assert state.capture_errors[-1][0] == "failed_source_path_check"
    assert state.path_links == ((str(link), record),)
    assert len(calls) == (0 if when == "before" else 1)


@pytest.mark.parametrize("shape", ["escape", "still_inside", "relative"])
def test_output_canonical_containment_refuses_before_any_mkdir_or_runtime_delegate(
    tmp_path, monkeypatch, shape
):
    bootstrap = tmp_path / "bootstrap.json"
    bootstrap.write_text(
        json.dumps(
            dict(
                kind=stage.KIND,
                runtime={},
                environment={},
                native_write_roots=[],
                native_links={},
                Root_review="a" * 64,
            )
        )
    )
    directory = {
        "escape": stage.Path("/mnt/workspaces/Cells") / ".." / "escape-witness-never-created",
        "still_inside": tmp_path / "unused" / ".." / "fresh-never-created",
        "relative": stage.Path("relative-never-created"),
    }[shape]
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("No directory creation or bootstrap delegate may run")

    namespace = dict(
        vars(stage),
        _dependencies=lambda: object(),
        _fresh_native=lambda: None,
        _resources=lambda: None,
        _function=forbidden,
    )
    private = FunctionType(stage._acquire_callback.__code__, namespace)
    with monkeypatch.context() as patch:
        patch.setattr(stage.Path, "mkdir", forbidden)
        with pytest.raises(stage.PreludeRejected) as caught:
            private(
                stage.Execution(),
                {},
                directory,
                bootstrap=bootstrap,
                bootstrap_sha256=stage.snapshot.digest(bootstrap),
            )
    assert caught.value.stage == "output" and calls == []
    assert not (tmp_path / "fresh-never-created").exists()


def test_repeated_caught_reentry_retains_first_identity_and_separates_later_attempts(monkeypatch):
    monkeypatch.setenv(stage.RELEASE, "1")
    namespace = dict(vars(stage), _ACTIVE=[], _RETAINED={})
    public = FunctionType(stage.acquire_callback.__code__, namespace)
    rejected, states, calls = [], [], []

    def actual(state, *args, **kwargs):
        states.append(state)
        for _ in range(3):
            try:
                public({}, "unused", bootstrap="unused", bootstrap_sha256="x", enabled=True)
            except stage.PreludeRejected as error:
                rejected.append(error)
        with pytest.raises(stage.PreludeRejected) as stopped:
            stage._operation(state, "never-next", lambda: calls.append("forbidden"))
        assert stopped.value is rejected[0]
        state.completed = True
        return object()

    namespace["_acquire_callback"] = actual
    with pytest.raises(stage.PreludeRejected) as caught:
        public({}, "unused", bootstrap="unused", bootstrap_sha256="x", enabled=True)
    state = states[0]
    assert caught.value.__cause__ is state.primary is state.entry_error is rejected[0]
    assert [error for _, error in state.later_errors] == rejected[1:]
    assert len({id(error) for error in rejected}) == 3
    assert calls == [] and namespace["_ACTIVE"] == [] and namespace["_RETAINED"] == {}


@pytest.mark.parametrize("secondary_capture", [False, True])
def test_falsey_source_primary_survives_reentrant_forensics_and_later_capture_failure(
    monkeypatch, secondary_capture
):
    monkeypatch.setenv(stage.RELEASE, "1")
    bool_calls, states, reentries, later_calls = [], [], [], []

    class FalseySource(ValueError):
        def __bool__(self):
            bool_calls.append("never-coerce-primary")
            return False

    primary = FalseySource("original source")
    cause, capture = KeyError("original cause"), OSError("secondary capture")
    primary.__cause__ = cause
    namespace = dict(vars(stage), _ACTIVE=[], _RETAINED={})
    public = FunctionType(stage.acquire_callback.__code__, namespace)

    def actual(state, *args, **kwargs):
        states.append(state)
        try:
            stage._operation(state, "original_source", lambda: (_ for _ in ()).throw(primary))
        except FalseySource:
            # Models failed-result forensic callbacks, after source retention.
            for _ in range(2):
                try:
                    public({}, "unused", bootstrap="unused", bootstrap_sha256="x", enabled=True)
                except stage.PreludeRejected as error:
                    reentries.append(error)
            if secondary_capture:
                state.capture_errors.append(("forensics", capture, primary))
            with pytest.raises(FalseySource) as stopped:
                stage._operation(state, "never-next", lambda: later_calls.append("forbidden"))
            assert stopped.value is primary
            raise

    namespace["_acquire_callback"] = actual
    with pytest.raises(stage.PreludeRejected) as caught:
        public({}, "unused", bootstrap="unused", bootstrap_sha256="x", enabled=True)
    state = states[0]
    assert caught.value.__cause__ is state.source_error is state.primary is primary
    assert primary.__cause__ is cause and state.entry_error is reentries[0]
    assert [error for _, error in state.later_errors] == reentries
    assert bool_calls == later_calls == []
    if secondary_capture:
        assert state.capture_errors[-1][1] is capture
    assert namespace["_ACTIVE"] == [] and namespace["_RETAINED"] == {}
