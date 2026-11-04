"""Native-blocked cache-constructor controls; no real phase/cache execution."""

import builtins
import json
import sys
import weakref
from types import CodeType, FunctionType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_phase_caches as stage
from tests.unit import test_betse_native_phase_assembly as phase_controls
from validation.betse.betse_native_single_cell_core_synthetic import save


@pytest.mark.parametrize(
    "relative,name",
    [
        ("betse/science/math/cache/cacheabc.py", "SimPhaseCaches"),
        ("betse/science/math/cache/cacheabc.py", "SimPhaseCacheABC"),
        ("betse/science/math/cache/cachevec.py", "SimPhaseCacheVectorCells"),
    ],
)
def test_contextual_metadata_cache_constructor_is_original_module_code(relative, name):
    path = stage.aliases.NATIVE / relative
    module = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    cls = next(c for c in module.co_consts if type(c) is CodeType and c.co_name == name)
    expected = next(c for c in cls.co_consts if type(c) is CodeType and c.co_name == "__init__")
    actual = stage._method_code(relative, name)
    assert actual == expected
    assert actual.co_qualname == name + ".__init__"
    assert actual.co_filename == str(path)
    assert actual.co_freevars == (("__class__",) if name == "SimPhaseCacheVectorCells" else ())


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    previous, trace, imported = sys.getprofile(), sys.gettrace(), builtins.__import__
    attempted = []
    codes = {
        stage._acquire.__code__,
        stage._import_native.__code__,
        *(method.__code__ for method in stage._METHODS.values()),
        stage.previous._acquire.__code__,
        stage.previous._PREFIX.__code__,
        stage.previous._import_native.__code__,
        stage.previous.previous._load.__code__,
        stage.previous.previous.paths._upgrade.__code__,
        stage.previous.previous.paths._reload.__code__,
        stage.previous.callbacks._acquire.__code__,
        stage.previous.previous.paths.prefix.parameters._acquire.__code__,
        stage.previous.previous.paths.prefix.parameters._invoke.__code__,
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code.co_filename.startswith(str(stage.aliases.NATIVE) + "/")
        ):
            attempted.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native/source cache constructor forbidden")
        if previous is not None:
            previous(frame, event, arg)

    def imports(name, *args, **kwargs):
        if name == "betse" or name.startswith(("betse.", "ruamel")):
            attempted.append(name)
            raise AssertionError("Actual native import forbidden")
        return imported(name, *args, **kwargs)

    def rng(*args, **kwargs):
        attempted.append("RNG")
        raise AssertionError("Actual RNG forbidden")

    monkeypatch.setattr(builtins, "__import__", imports)
    for name in ("RandomState", "default_rng", "seed", "random", "normal", "uniform", "choice"):
        monkeypatch.setattr(stage.literal.callers.np.random, name, rng)
    sys.setprofile(profile)
    try:
        yield
        assert attempted == [] and sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)
        (tmp_path / "native-blocked.json").write_text(
            json.dumps(
                dict(
                    nodeid=request.node.nodeid,
                    attempted=attempted,
                    actual_source_or_scientific_credit=0,
                )
            )
        )


@pytest.fixture(scope="module")
def plans():
    return stage.previous.previous.source_plan(), stage.previous.callbacks.source_plan()


@pytest.fixture
def parent(monkeypatch, tmp_path, plans):
    h = phase_controls.controlled.__wrapped__(monkeypatch, tmp_path, plans)
    owner = stage.previous.prepare(h.request, enabled=True)
    return NS(h=h, owner=owner, context=stage.previous._ISSUED[owner])


@pytest.fixture
def controlled(monkeypatch, parent):
    # A missing real upstream retirement capability is a held prerequisite,
    # never replaced by a synthetic registry/claim or a fabricated phase owner.
    if not callable(getattr(stage.previous, "_claim_for_caches", None)):
        pytest.skip("Phase-prefix retirement hook remains under upstream review")

    class ABC:
        def __init__(self, phase):
            raise AssertionError("Unselected original synthetic constructor")

    class Top:
        def __init__(self, phase):
            raise AssertionError("Unselected original synthetic constructor")

    class Upscaled(ABC):
        @property
        def extent(self):
            raise AssertionError("Lazy cache property forbidden")

    class Vector(ABC):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            from betse.science.math.cache.cachelyrvec import SimPhaseCacheLayerCellsVector

            self.layer = SimPhaseCacheLayerCellsVector(self._phase)

    class Layer(ABC):
        @property
        def voltage_membrane(self):
            raise AssertionError("Lazy cache property forbidden")

    class Field(ABC):
        @property
        def currents_extra(self):
            raise AssertionError("Lazy cache property forbidden")

    space = {}
    exec(
        compile(
            """
def attach(self):
    self.cache=SimPhaseCaches(phase=self)
def top(self,phase):
    from betse.science.math.cache.cacheupscaled import SimPhaseCacheUpscaled
    from betse.science.math.cache.cachevec import SimPhaseCacheVectorCells
    from betse.science.math.cache.cachevecfld import SimPhaseCacheVectorFieldCells
    self.upscaled=SimPhaseCacheUpscaled(phase)
    self.vector=SimPhaseCacheVectorCells(phase)
    self.vector_field=SimPhaseCacheVectorFieldCells(phase)
def abc(self,phase):
    self._phase=pyref.proxy_weak(phase)
def proxy(obj):
    return obj if isinstance(obj,WeakRefProxyTypes) else weakref.proxy(obj)
""",
            "<synthetic-cache-constructor>",
            "exec",
        ),
        space,
    )
    methods = {key: space[key] for key in ("attach", "top", "abc", "proxy")}
    methods["vector"] = Vector.__init__
    factories = dict(zip(stage.MODULES, (Top, ABC, Upscaled, Vector, Layer, Field), strict=True))
    modules = {name: NS() for name in dict.fromkeys(stage.MODULES.values())}

    def acquire(context):
        context.factories = factories
        context.import_modules = modules
        context.pyref = NS(
            proxy_weak=methods["proxy"], WeakRefProxyTypes=weakref.ProxyTypes, weakref=weakref
        )
        context.modules = {}

    monkeypatch.setattr(stage, "_acquire", acquire)
    monkeypatch.setattr(stage, "_import_native", lambda name, *a: modules[name])
    monkeypatch.setattr(stage, "_METHODS", methods)
    monkeypatch.setenv(stage.RELEASE, "1")
    request = stage.from_phase(parent.owner, law_id=stage.LAW_ID, mode=stage.MODE)
    return NS(parent=parent, request=request, factories=factories)


@pytest.fixture
def refused(tmp_path):
    from contextlib import contextmanager

    @contextmanager
    def check():
        with pytest.raises(stage.CacheConstructionRejected) as caught:
            yield caught
        error = caught.value
        partial = error.partial if type(error.partial) is dict else {}
        save(
            tmp_path,
            "refusal",
            dict(
                stage=error.stage,
                primary=error.source_error,
                capture=error.capture_error,
                cause=error.__cause__,
                trial=error.trial,
                parent=partial.get("parent_trial"),
                objects=partial.get("objects"),
                proxies=partial.get("proxies"),
                attempts=partial.get("attempts"),
                returns=partial.get("returns"),
                last_completed=partial.get("last_completed"),
            ),
        )

    return check


def test_preparation_literal_bodies_weak_helper_and_boundary():
    plan = stage.source_plan()
    assert plan["phase_store_lines"] == [185, 185]
    assert plan["constructor_lines"] == {
        "SimPhaseCaches": [47, 56],
        "SimPhaseCacheABC": [93, 93],
        "SimPhaseCacheVectorCells": [34, 41],
    }
    assert plan["factory_order"] == stage.ROLES
    assert plan["parameter_reads_or_stores"] == ()
    assert not plan["full_phase_or_world_or_physical_or_checkpoint_admitted"]


@pytest.mark.parametrize(
    "name,relative,freevars",
    [
        ("SimPhaseCaches", "betse/science/math/cache/cacheabc.py", ()),
        ("SimPhaseCacheABC", "betse/science/math/cache/cacheabc.py", ()),
        ("SimPhaseCacheVectorCells", "betse/science/math/cache/cachevec.py", ("__class__",)),
    ],
)
def test_preparation_constructor_metadata_preserves_original_class_cell(name, relative, freevars):
    # Compilation only: neither class suite nor any constructor is executed.
    code = stage._method_code(relative, name)
    assert code.co_name == "__init__" and code.co_freevars == freevars
    assert code.co_filename == str(stage.aliases.NATIVE / relative)


@pytest.mark.parametrize("enabled,flag", [(False, "1"), (True, "0"), (1, "1")])
def test_preparation_release_precedes_all_constructor_work(monkeypatch, refused, enabled, flag):
    monkeypatch.setenv(stage.RELEASE, flag)
    with refused() as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release" and caught.value.trial is None


def test_preparation_requires_actual_issued_request(monkeypatch, refused):
    monkeypatch.setenv(stage.RELEASE, "1")
    with refused() as caught:
        stage.prepare(NS(), enabled=True)
    assert caught.value.stage == "request" and caught.value.trial is None


def test_preparation_wrong_mode_cannot_gain_cache_authority(refused):
    with refused() as caught:
        stage.from_phase(None, law_id=stage.LAW_ID, mode="complete_phase")
    assert caught.value.stage == "law"


def test_preparation_missing_hook_keeps_real_prefix_unconsumed(parent, monkeypatch, refused):
    monkeypatch.setenv(stage.RELEASE, "1")
    request = stage.from_phase(parent.owner, law_id=stage.LAW_ID, mode=stage.MODE)
    before = parent.owner.partial_phase
    with monkeypatch.context() as changed:
        changed.delattr(stage.previous, "_claim_for_caches")
        with refused() as caught:
            stage.prepare(request, enabled=True)
    assert caught.value.stage == "phase_hook" and caught.value.trial is None
    assert request not in stage._CONSUMED and parent.owner.partial_phase is before
    assert "cache" not in vars(before)


def test_same_live_phase_subcache_order_and_real_weak_links(controlled, tmp_path):
    h = controlled
    phase = h.parent.owner.partial_phase
    before = tuple(vars(phase).items())
    owner = stage.prepare(h.request, enabled=True)
    assert owner.partial_phase is phase and tuple(vars(phase)) == (*stage.previous.FIELDS, "cache")
    assert all(vars(phase)[key] is value for key, value in before)
    cache = owner.cache_namespace
    for value in (cache.upscaled, cache.vector, cache.vector.layer, cache.vector_field):
        assert type(value._phase) in weakref.ProxyTypes
        assert any(value._phase is ref for ref in weakref.getweakrefs(phase))
    assert cache.vector.layer._phase is cache.vector._phase
    assert owner.trial.completed and owner.trial.proxy_returns == 4
    save(tmp_path, "trial", owner.trial)


@pytest.mark.parametrize(
    "registry",
    [
        "phase_issuance",
        "phase_retirement",
        "phase_retirement_marker",
        "parameter_claim",
        "cache_object",
        "parameter_issuance",
        "callback_issuance",
        "prefix_request_claim",
        "prefix_parameter_claim",
        "prefix_raw_object",
    ],
)
def test_retained_issuance_links_cannot_disappear(controlled, refused, registry):
    h = controlled
    owner = stage.prepare(h.request, enabled=True)
    context = stage._ISSUED[owner]
    before = stage._snapshot(context).identity
    if registry == "phase_issuance":
        stage.previous._ISSUED.pop(h.parent.owner)
    elif registry == "phase_retirement":
        stage.previous._FORWARDED.pop(h.parent.owner)
    elif registry == "phase_retirement_marker":
        del h.parent.context.cache_transition
    elif registry == "parameter_claim":
        stage.previous.claims._CONSTRUCTED.pop(h.parent.h.parameter_owner)
    elif registry == "cache_object":
        stage._OBJECTS.pop(context.phase.cache.vector)
    elif registry == "parameter_issuance":
        stage.previous.previous._ISSUED.pop(h.parent.h.parameter_owner)
    elif registry == "callback_issuance":
        stage.previous.callbacks._ISSUED.pop(h.parent.h.callback_owner)
    elif registry == "prefix_request_claim":
        stage.previous._CONSUMED.pop(h.parent.context.request)
    elif registry == "prefix_parameter_claim":
        stage.previous._CLAIMED.pop(h.parent.h.parameter_owner)
    else:
        stage.previous._OBJECTS.pop(context.phase.cells)
    assert stage._snapshot(context).identity == before
    with refused() as caught:
        _ = owner.cache_namespace
    assert caught.value.stage == "owner_drift"


@pytest.mark.parametrize("target", ["top", "abc", "vector", "proxy"])
def test_constructor_failure_keeps_actual_parent_and_partial_objects(
    controlled, monkeypatch, refused, target
):
    primary, cause = ValueError("constructor primary"), LookupError("original cause")
    original = stage._namespace

    def namespace(context):
        original(context)

        def failed(*args, **kwargs):
            raise primary from cause

        old = context.methods[target]
        context.methods[target] = FunctionType(
            failed.__code__, old.__globals__, old.__name__, failed.__defaults__, failed.__closure__
        )
        context.scope_bindings = stage._scope_bindings(context)

    monkeypatch.setattr(stage, "_namespace", namespace)
    with refused() as caught:
        stage.prepare(controlled.request, enabled=True)
    error = caught.value
    assert (
        error.source_error is primary and error.__cause__ is primary and primary.__cause__ is cause
    )
    assert error.partial["phase"] is controlled.parent.context.phase
    assert not error.partial["usable_child_available"]
    assert stage.previous._FORWARDED[controlled.parent.owner] is error.partial["context"]
    with pytest.raises(stage.CacheConstructionRejected) as again:
        stage.prepare(controlled.request, enabled=True)
    assert again.value.stage == "consumed"


def test_later_owner_cannot_reopen_retired_phase_prefix(controlled):
    owner = stage.prepare(controlled.request, enabled=True)
    phase = owner.partial_phase
    with pytest.raises(stage.previous.AssemblyRejected) as caught:
        _ = controlled.parent.owner.partial_phase
    assert caught.value.stage == "forwarded" and not controlled.parent.context.invalid
    assert owner.partial_phase is phase


@pytest.mark.parametrize("target", ["caller_method", "cache_method", "weak_helper"])
def test_inherited_callable_or_private_helper_drift_with_unchanged_values(
    controlled, refused, target
):
    owner = stage.prepare(controlled.request, enabled=True)
    context = stage._ISSUED[owner]
    before = stage._snapshot(context).identity
    marker = object()

    def changed(*args, **kwargs):
        assert marker is not None
        raise AssertionError("Changed callable must never run")

    if target == "caller_method":
        controlled.parent.h.classes["cells"].make_world = changed
    elif target == "cache_method":
        controlled.factories["SimPhaseCacheVectorCells"].__init__.__code__ = changed.__code__
    else:
        context.methods["abc"].__globals__["pyref"].proxy_weak = changed
    assert stage._snapshot(context).identity == before
    with refused() as caught:
        _ = owner.cache_namespace
    assert caught.value.stage == "owner_drift"


def test_retirement_link_drift_stops_before_the_next_factory(controlled, monkeypatch, refused):
    original = stage._namespace

    def namespace(context):
        original(context)

        class Events(list):
            def append(self, row):
                super().append(row)
                if row[0] == "SimPhaseCacheABC.__init___return":
                    stage.previous._FORWARDED.pop(controlled.parent.owner)

        context.events = Events()
        context.tape.events = context.events

    monkeypatch.setattr(stage, "_namespace", namespace)
    with refused() as caught:
        stage.prepare(controlled.request, enabled=True)
    assert caught.value.partial["attempts"] == ["SimPhaseCaches", "SimPhaseCacheUpscaled"]
    assert "cache" not in vars(caught.value.partial["phase"])
    with pytest.raises(stage.previous.AssemblyRejected) as old:
        _ = controlled.parent.owner.partial_phase
    assert old.value.stage == "forwarded"


def test_cache_assignment_cannot_precede_constructor_completion(controlled, monkeypatch, refused):
    original = stage._namespace

    def namespace(context):
        original(context)

        class Events(list):
            def append(self, row):
                super().append(row)
                if row[0] == "SimPhaseCacheABC.__init___return":
                    context.phase.cache = context.constructed["SimPhaseCaches"]

        context.events = Events()
        context.tape.events = context.events

    monkeypatch.setattr(stage, "_namespace", namespace)
    with refused() as caught:
        stage.prepare(controlled.request, enabled=True)
    error = caught.value
    assert error.partial["attempts"] == ["SimPhaseCaches", "SimPhaseCacheUpscaled"]
    assert error.partial["phase"].cache is error.partial["objects"][0][1]
    assert error.source_error is not None and error.trial is not None
    assert not error.trial.completed and not error.partial["usable_child_available"]


@pytest.mark.parametrize("path", ["upscaled", "layer", "field", "constructor"])
def test_raw_lazy_and_constructor_entry_stays_blocked(controlled, refused, path):
    cache = stage.prepare(controlled.request, enabled=True).cache_namespace
    with refused():
        if path == "upscaled":
            _ = cache.upscaled.extent
        elif path == "layer":
            _ = cache.vector.layer.voltage_membrane
        elif path == "field":
            _ = cache.vector_field.currents_extra
        else:
            cache.vector.__init__(None)


@pytest.mark.parametrize("name", ["_phase", "layer"])
def test_equal_looking_reference_retarget_refuses(controlled, refused, name):
    owner = stage.prepare(controlled.request, enabled=True)
    cache = owner.cache_namespace
    if name == "_phase":
        # Weak targets must really be weak-referenceable; no SimpleNamespace
        # substitution for a source phase, even in the negative control.
        class Other:
            pass

        other = Other()
        cache.vector._phase = weakref.proxy(other)
    else:
        cache.vector.layer = cache.vector_field
    with refused() as caught:
        _ = owner.cache_namespace
    assert caught.value.stage == "owner_drift"


def test_entry_capture_failure_prevents_any_delegate(controlled, monkeypatch, refused):
    original = stage._namespace
    capture = OSError("constructor-enter observation")

    def namespace(context):
        original(context)

        class Events(list):
            def append(self, row):
                if row[0] == "SimPhaseCaches.__init___enter":
                    raise capture
                super().append(row)

        context.events = Events()
        context.tape.events = context.events

    monkeypatch.setattr(stage, "_namespace", namespace)
    with refused() as caught:
        stage.prepare(controlled.request, enabled=True)
    error = caught.value
    assert error.capture_error is capture and error.source_error is None
    assert len(error.partial["objects"]) == 1 and not error.partial["returns"]


def test_reentrant_enter_cannot_be_swallowed_into_a_constructor(controlled, monkeypatch, refused):
    original, nested = stage._namespace, []

    def namespace(context):
        original(context)

        class Events(list):
            def append(self, row):
                super().append(row)
                if row[0] == "SimPhaseCaches.__init___enter":
                    try:
                        stage.prepare(controlled.request, enabled=True)
                    except stage.CacheConstructionRejected as error:
                        nested.append(error)

        context.events = Events()
        context.tape.events = context.events

    monkeypatch.setattr(stage, "_namespace", namespace)
    with refused() as caught:
        stage.prepare(controlled.request, enabled=True)
    assert nested[0].stage == "reentrant"
    assert caught.value.partial["attempts"] == ["SimPhaseCaches"]
    assert caught.value.partial["imports"] == []
    assert caught.value.partial["returns"] == []
    assert not caught.value.partial["usable_child_available"]


def test_early_parent_refusal_has_no_fabricated_baseline_or_trial(controlled, refused):
    h = controlled
    phase = h.parent.context.phase
    wrong = NS()
    phase.p = wrong
    with refused() as caught:
        stage.prepare(h.request, enabled=True)
    error = caught.value
    assert error.stage == "parent_preflight" and error.trial is None
    assert isinstance(error.source_error, stage.previous.AssemblyRejected)
    assert error.__cause__ is error.source_error
    assert error.partial["phase"] is phase and phase.p is wrong
    assert error.partial["parent_trial"] is h.parent.context.trial
    assert error.partial["attempts"] == [] and error.partial["objects"] == []
    assert h.parent.owner not in stage.previous._FORWARDED
    assert not hasattr(error.partial["context"], "before")


def test_return_capture_stops_before_the_next_factory(controlled, monkeypatch, refused):
    original = stage._namespace
    capture = OSError("ABC return observation")

    def namespace(context):
        original(context)

        class Events(list):
            def append(self, row):
                if row[0] == "SimPhaseCacheABC.__init___return":
                    raise capture
                super().append(row)

        context.events = Events()
        context.tape.events = context.events

    monkeypatch.setattr(stage, "_namespace", namespace)
    profile, trace = sys.getprofile(), sys.gettrace()
    with refused() as caught:
        stage.prepare(controlled.request, enabled=True)
    error = caught.value
    assert error.capture_error is capture and error.source_error is None
    assert error.partial["attempts"] == ["SimPhaseCaches", "SimPhaseCacheUpscaled"]
    assert len(error.partial["proxies"]) == 1
    assert error.partial["objects"][1][1]._phase is error.partial["proxies"][0][1]
    assert sys.getprofile() is profile and sys.gettrace() is trace


def test_unwind_capture_preserves_primary_and_failed_raw_entry_guard(
    controlled, monkeypatch, refused
):
    original = stage._namespace
    primary, cause, capture = ValueError("weak primary"), KeyError("cause"), OSError("unwind")

    def namespace(context):
        original(context)

        def fail(*args):
            raise primary from cause

        old = context.methods["proxy"]
        context.methods["proxy"] = FunctionType(
            fail.__code__, old.__globals__, old.__name__, fail.__defaults__, fail.__closure__
        )
        context.scope_bindings = stage._scope_bindings(context)

        class Events(list):
            def append(self, row):
                if row[0] == "proxy_weak_unwind":
                    raise capture
                super().append(row)

        context.events = Events()
        context.tape.events = context.events

    monkeypatch.setattr(stage, "_namespace", namespace)
    with refused() as caught:
        stage.prepare(controlled.request, enabled=True)
    error = caught.value
    assert error.source_error is primary and error.capture_error is capture
    assert error.__cause__ is primary and primary.__cause__ is cause
    assert error.partial["attempts"] == ["SimPhaseCaches", "SimPhaseCacheUpscaled"]
    raw = error.partial["objects"][1][1]
    with pytest.raises(stage.literal._CaptureStop):
        raw.__init__(controlled.parent.context.phase)
    assert not error.partial["usable_child_available"]


def test_failed_sealing_preserves_native_primary_and_cause(controlled, monkeypatch, refused):
    original = stage._namespace
    primary, cause, capture = ValueError("proxy primary"), KeyError("cause"), OSError("sealing")

    def namespace(context):
        original(context)

        def fail(*args):
            raise primary from cause

        old = context.methods["proxy"]
        context.methods["proxy"] = FunctionType(
            fail.__code__, old.__globals__, old.__name__, fail.__defaults__, fail.__closure__
        )
        context.scope_bindings = stage._scope_bindings(context)

    def snapshot(context):
        raise capture

    monkeypatch.setattr(stage, "_namespace", namespace)
    monkeypatch.setattr(stage, "_snapshot", snapshot)
    with refused() as caught:
        stage.prepare(controlled.request, enabled=True)
    error = caught.value
    assert error.source_error is primary and error.capture_error is capture
    assert error.__cause__ is primary and primary.__cause__ is cause
    assert error.partial["parent_trial"] is controlled.parent.context.trial


def test_complete_phase_remains_unavailable(controlled, refused):
    owner = stage.prepare(controlled.request, enabled=True)
    with refused() as caught:
        stage.require_phase(owner)
    assert caught.value.stage == "phase_incomplete"
