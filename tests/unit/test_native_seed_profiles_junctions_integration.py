"""Isolated blocked integration controls; no supplied state becomes a native owner."""

import hashlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_phase_dyna as dyna
from cells.processes import betse_native_seed_init_core as core
from cells.processes import betse_native_seed_init_profiles as profiles
from cells.processes import betse_native_seed_junctions as junctions
from cells.processes import betse_native_world_phase_construction as world
from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import native_seed_profiles_junctions_integration_software as software

_RAW_GUARDS = []


def clone(fn, **values):
    current = FunctionType(
        fn.__code__, dict(fn.__globals__, **values), fn.__name__, fn.__defaults__, fn.__closure__
    )
    current.__kwdefaults__ = fn.__kwdefaults__
    return current


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit isolated native-blocked release required")
    request.config.option.maxfail = 1
    adapter = NS(**dict(vars(software), reuse=software.base.reuse.reuse))
    scope = dict(vars(guards), software=adapter, _BLOCKADE_FAILURES=())
    control = FunctionType(guards._blockade.__wrapped__.__code__, scope)
    attempted = []

    def forbidden(*args, **kwargs):
        attempted.append("operator_or_RNG")
        raise AssertionError("Actual operators/RNG remain blocked")

    try:
        with contextmanager(control)(request, tmp_path), monkeypatch.context() as patch:
            for name in ("pinv", "inv", "svd", "solve", "lstsq"):
                patch.setattr(np.linalg, name, forbidden)
            for name in (
                "RandomState",
                "default_rng",
                "seed",
                "set_state",
                "rand",
                "randn",
                "normal",
                "uniform",
                "shuffle",
            ):
                patch.setattr(np.random, name, forbidden)
            try:
                yield
            finally:
                software.snapshot.write_json(
                    tmp_path / "operator-RNG-blocked.json", dict(attempted=attempted)
                )
            assert attempted == []
    finally:
        if scope["_BLOCKADE_FAILURES"]:
            _RAW_GUARDS.append(scope["_BLOCKADE_FAILURES"])


def test_coherent_nine_path_scope_keeps_every_source_gate_closed():
    assert len(software.OWNED) == len(set(software.OWNED)) == 9
    for module in (profiles, junctions):
        assert module.PARENT_SOURCE_SHA256 is module.PARENT_REVIEW_SHA256 is None
        assert module.COORDINATOR_SOURCE_SHA256 is module.COORDINATOR_REVIEW_SHA256 is None
    assert world.SEED_PROFILES_INTERFACE_SHA256 is world.SEED_JUNCTIONS_INTERFACE_SHA256 is None
    assert profiles.PROPOSED_CLAIM == "_claim_for_seed_profiles"
    assert junctions.PROPOSED_CLAIM == "_claim_for_seed_junctions"


@pytest.mark.parametrize(
    "entry", ["profiles_request", "profiles_prepare", "junction_request", "junction_prepare"]
)
def test_closed_producer_gate_precedes_every_foreign_owner_read(entry):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("Foreign authority read before source adoption")

    with pytest.raises(ValueError):
        if entry == "profiles_request":
            profiles.from_core(Foreign(), law_id=profiles.LAW_ID)
        elif entry == "profiles_prepare":
            profiles.prepare(Foreign(), enabled=True)
        elif entry == "junction_request":
            junctions.from_profiles(Foreign(), law_id=junctions.LAW_ID)
        else:
            junctions.prepare(Foreign(), enabled=True)


@pytest.mark.parametrize(
    "module,kind",
    [(profiles, world.SEED_PROFILES_BINDING_KIND), (junctions, world.SEED_JUNCTIONS_BINDING_KIND)],
)
@pytest.mark.parametrize("slot", [None, *world.SEED_CHILD_BACK_REFERENCE_SLOTS, "body"])
def test_four_explicit_backrefs_break_only_the_declared_parent_coordinator_cycles(
    module, kind, slot
):
    raw = Path(module.__file__).read_bytes()
    original, refs = world._seed_child_binding(raw, kind=kind)
    assert refs == tuple((name, None) for name in world.SEED_CHILD_BACK_REFERENCE_SLOTS)
    changed = raw
    if slot == "body":
        changed += b"\n# distinct non-back-reference bytes\n"
    elif slot is not None:
        old = (slot + " = None").encode()
        new = (slot + " = '" + "a" * 64 + "'").encode()
        assert raw.count(old) == 1
        changed = raw.replace(old, new, 1)
    actual, _ = world._seed_child_binding(changed, kind=kind)
    assert (actual == original) is (slot != "body")


@pytest.mark.parametrize("mutation", [None, "code", "keyword_type", "foreign_globals", "filename"])
def test_exact_loaded_interface_checks_same_object_code_and_typed_defaults_before_any_body(
    tmp_path, mutation
):
    payload = (
        b"def selected(owner, *, enabled=False):\n    raise AssertionError('BODY MUST NOT RUN')\n"
    )
    path = tmp_path / "metadata_interface.py"
    module = ModuleType("metadata_interface")
    compiled = compile(payload, str(path), "exec", dont_inherit=True)
    code = next(value for value in compiled.co_consts if type(value) is type(compiled))
    fn = FunctionType(code, vars(module), "selected")
    fn.__kwdefaults__ = {"enabled": False}
    module.selected = fn
    if mutation == "code":
        fn.__code__ = fn.__code__.replace(co_consts=(*fn.__code__.co_consts, "new constant"))
    elif mutation == "keyword_type":
        fn.__kwdefaults__["enabled"] = 0
    elif mutation == "foreign_globals":
        module.selected = clone(fn)
    elif mutation == "filename":
        fn.__code__ = fn.__code__.replace(co_filename="foreign_interface.py")
    if mutation is None:
        assert world._source_interface(module, payload, path, ("selected",)) is None
    else:
        with pytest.raises(ValueError):
            world._source_interface(module, payload, path, ("selected",))


@pytest.mark.parametrize(
    "mutation", [None, "parent", "coordinator", "review", "loaded_slot", "code"]
)
def test_deferred_loader_authenticates_every_full_backref_then_actual_loaded_code(
    tmp_path, mutation
):
    # Definition-only modules in a private namespace. No owner or native module
    # body is evaluated; this tests the real loader's exact-byte boundaries.
    parent, module = ModuleType("metadata_parent"), ModuleType("metadata_child")
    parent_path, child_path, coordinator_path = (
        tmp_path / "parent.py",
        tmp_path / "child.py",
        tmp_path / "coordinator.py",
    )
    parent_path.write_bytes(b"metadata parent bytes only\n")
    coordinator_path.write_bytes(b"metadata coordinator bytes only\n")
    parent.__file__, module.__file__, module.previous = str(parent_path), str(child_path), parent
    values = {
        "PARENT_SOURCE_SHA256": hashlib.sha256(parent_path.read_bytes()).hexdigest(),
        "PARENT_REVIEW_SHA256": "b" * 64,
        "COORDINATOR_SOURCE_SHA256": hashlib.sha256(coordinator_path.read_bytes()).hexdigest(),
        "COORDINATOR_REVIEW_SHA256": "c" * 64,
    }
    payload = "\n".join(name + " = " + repr(value) for name, value in values.items()) + "\n"
    for name in ("prepare", "_authority", "_dispatch", "_wrapper_guard", "_check_fields"):
        payload += "def " + name + "(context):\n    raise AssertionError('NO BODY EXECUTION')\n"
    raw = payload.encode()
    child_path.write_bytes(raw)
    compiled = compile(raw, str(child_path), "exec", dont_inherit=True)
    for code in compiled.co_consts:
        if type(code) is type(compiled):
            setattr(module, code.co_name, FunctionType(code, vars(module), code.co_name))
    for name, value in values.items():
        setattr(module, name, value)
    identity, _ = world._seed_child_binding(raw, kind=world.SEED_JUNCTIONS_BINDING_KIND)
    imports = []

    def imported(name):
        imports.append(name)
        return module

    if mutation == "parent":
        parent_path.write_bytes(b"different parent bytes\n")
    elif mutation == "coordinator":
        coordinator_path.write_bytes(b"different coordinator bytes\n")
    elif mutation == "loaded_slot":
        module.PARENT_SOURCE_SHA256 = "d" * 64
    elif mutation == "code":
        module.prepare.__code__ = module.prepare.__code__.replace(
            co_consts=(*module.prepare.__code__.co_consts, "untrusted code")
        )
    loader = clone(
        world._import_seed_child,
        __file__=str(coordinator_path),
        _module_file=lambda name: child_path if name == module.__name__ else parent_path,
        sys=NS(modules={module.__name__: module, parent.__name__: parent}),
        importlib=NS(import_module=imported),
    )
    kwargs = dict(
        kind=world.SEED_JUNCTIONS_BINDING_KIND,
        interface=identity,
        review="e" * 64,
        coordinator_review="c" * 64,
        parent=parent,
        parent_review="f" * 64 if mutation == "review" else "b" * 64,
    )
    if mutation is None:
        assert loader(module.__name__, **kwargs) is module
    else:
        with pytest.raises(ValueError):
            loader(module.__name__, **kwargs)
    assert imports == ([module.__name__] if mutation in (None, "loaded_slot", "code") else [])


@pytest.mark.parametrize("world_mode", [False, True])
def test_future_handler_delegate_is_declared_before_birth_and_legacy_surface_stays_closed(
    world_mode,
):
    calls = []

    class HandlerShape:
        def init_profiles(self, phase):
            calls.append(phase)
            raise AssertionError("No actual handler instance/body")

    ctx = NS(
        symbols={},
        entry_wrappers={},
        native_handler=HandlerShape,
        runtime_types={},
        runtime_bindings={},
        world_mode=dyna.WORLD_MODE if world_mode else None,
    )
    make = clone(
        dyna._namespace, _factory_scope=lambda context: {}, _namespace_bindings=lambda context: ()
    )
    make(ctx)
    member = vars(ctx.runtime_types["TissueHandler"])["init_profiles"]
    cells = dict(
        zip(
            member.__code__.co_freevars,
            (c.cell_contents for c in member.__closure__ or ()),
            strict=True,
        )
    )
    assert cells["context"] is ctx
    if world_mode:
        assert cells["delegate"] is HandlerShape.init_profiles
        assert member.__code__.co_varnames[:2] == ("self", "phase")
    else:
        assert "delegate" not in cells
    assert calls == []  # No runtime instance is allocated; no owner is fabricated.


@pytest.mark.parametrize("mutation", [None, "remove", "equal_tuple", "registry", "field"])
def test_inherited_registry_tuple_and_holder_edges_are_exact_readonly_relations(mutation):
    module = ModuleType("metadata_registry")
    actual, key = NS(request=object()), object()
    issued = (actual, "cache_role")
    module.registry = {key: issued}
    lease = NS(
        edges=(
            (
                module,
                actual,
                (("request", actual.request),),
                (("registry", module.registry, ((key, issued, tuple(issued)),)),),
            ),
        )
    )
    if mutation == "remove":
        module.registry.pop(key)
    elif mutation == "equal_tuple":
        module.registry[key] = tuple([*issued])
        assert module.registry[key] == issued and module.registry[key] is not issued
    elif mutation == "registry":
        module.registry = dict(module.registry)
    elif mutation == "field":
        actual.request = object()
    if mutation is None:
        assert core._check_profile_ancestor_edges(lease) is None
    else:
        with pytest.raises(ValueError):
            core._check_profile_ancestor_edges(lease)


def _epoch_metadata():
    ctx = NS(
        dm=np.array([[1.0, -0.0, 3.0]]),
        cell_i=np.array([0, 1, 2]),
        dyna=NS(),
        parent=NS(parent=object()),
        metadata_rng=NS(identity="unchanged_MT"),
        request=object(),
        refs=(),
        api=object(),
        phase=object(),
        p=object(),
        cells=object(),
        sim=object(),
        expected_rng=object(),
        percent_active=False,
        active=True,
        invalid=False,
        thread=core.get_ident(),
        entries={},
        parent_claim=object(),
        parent_check=object(),
        call_tracing=object(),
    )
    sampler = clone(
        profiles._observer_epoch,
        _cache=lambda context, value: core._CORE.caches.snapshot(value),
        previous=NS(previous=NS(_rng=lambda parent: ctx.metadata_rng)),
    )
    return ctx, sampler


@pytest.mark.parametrize(
    "mutation", [None, "material", "indices", "MT", "equal_array", "map_alias"]
)
def test_per_observer_epoch_covers_mutable_bits_rng_and_equal_object_retarget(mutation):
    ctx, sampler = _epoch_metadata()
    setattr(ctx.dyna, profiles.MAPS[0], {})
    before = sampler(ctx)
    if mutation == "material":
        ctx.dm[0, 0] = 9.0
    elif mutation == "indices":
        ctx.cell_i[:] = [2, 1, 0]
    elif mutation == "MT":
        ctx.metadata_rng.identity = "different_MT"
    elif mutation == "equal_array":
        ctx.dm = ctx.dm.copy()
    elif mutation == "map_alias":
        setattr(ctx.dyna, profiles.MAPS[0], {})
    assert (sampler(ctx) == before) is (mutation is None)


@pytest.mark.parametrize("primary", [False, True])
def test_inherited_observer_capture_failure_retains_original_source_error_and_cause(primary):
    source, cause, capture = ValueError("original source"), KeyError("cause"), OSError("capture")
    source.__cause__ = cause
    ctx = NS(
        inherited_hook_active=False,
        entry_error=None,
        primary=source if primary else None,
        observation_error=None,
        capture_errors=(),
        call_tracing=lambda fn, args: fn(*args),
    )
    calls = []

    def epoch(context):
        calls.append("epoch")
        if len(calls) > 1:
            raise capture
        return "before"

    fn = clone(profiles._inherited_observer, _observer_epoch=epoch)
    if primary:
        assert fn(ctx, lambda *args: "return", object(), "return", None) == "return"
        assert ctx.primary is source and source.__cause__ is cause
    else:
        with pytest.raises(OSError) as caught:
            fn(ctx, lambda *args: "return", object(), "return", None)
        assert caught.value is capture
    assert ctx.observation_error is capture and ctx.inherited_hook_active is False


def test_profile_forwarder_passes_the_actual_immediate_wrapper_and_dispatch_frames():
    origin, actual, phase, delegate = object(), object(), object(), object()
    calls = []
    ctx = NS(dyna=actual, phase=phase)

    def wrapper_guard(current, original, frame):
        calls.append(("guard", current, original, frame.f_code, frame.f_back.f_code))

    def dispatch(current, original, label, body, receiver, args, kwargs, frame):
        calls.append(("dispatch", current, original, label, body, receiver, args, kwargs))
        assert frame.f_code is forward.__code__ and frame.f_back.f_code is invoke.__code__
        return "metadata_return"

    ctx.entries = dict(wrapper_guard=wrapper_guard, dispatch=dispatch)
    forward = clone(world._seed_profiles_call, _world_profile_origin=lambda owner: (ctx, NS()))

    def invoke():
        return forward(origin, delegate, actual, phase)

    assert invoke() == "metadata_return"
    assert calls[0][1:4] == (ctx, origin, invoke.__code__)
    assert calls[1][1:] == (ctx, origin, "init_profiles", delegate, actual, (phase,), {})


def test_picker_forwarder_keeps_the_actual_original_native_call_as_its_immediate_parent():
    origin, delegate, actual, cells, parameter = (
        NS(active=False, world_mode=dyna.WORLD_MODE),
        object(),
        object(),
        object(),
        object(),
    )
    calls = []
    ctx = NS(entries={})

    def dispatch(current, original, label, body, args, kwargs, frame):
        assert frame.f_back.f_code is dyna._native_call.__code__
        calls.append((current, original, label, body, args, kwargs))
        return "metadata_return"

    ctx.entries["picker_dispatch"] = dispatch
    origin.world_transition = NS(api=NS(stages=(None, None, dyna)))
    forward = clone(
        world._seed_profiles_picker_call,
        _world_profile_origin=lambda owner: (ctx, NS()),
        _world_profiles_wrapper_guard=lambda owner, frame: None,
    )
    api = NS(_world_has_seed_profiles_route=lambda owner: True, _seed_profiles_picker_call=forward)
    native = clone(dyna._native_call, _guard=lambda owner: None, _world_api=lambda: api)
    assert (
        native(origin, "TissuePickerAll.pick_cells", delegate, actual, cells, parameter)
        == "metadata_return"
    )
    assert calls == [
        (ctx, origin, "TissuePickerAll.pick_cells", delegate, (actual, cells, parameter), {})
    ]


@pytest.mark.parametrize("percent", [False, True])
@pytest.mark.parametrize("mutation", ["material", "indices", "unowned", "equal_retarget"])
def test_parent_observation_projection_exempts_only_identical_owned_buffers(percent, mutation):
    dm, cell_i, other = np.array([[1.0, -0.0]]), np.array([0, 1]), np.array([9.0])
    fields = dict(Dm_cells=dm, cell_i=cell_i, unowned=other)
    view = NS(fields=[fields])
    parent = NS(parent=object(), profile_lease=NS(percent=percent))
    ctx = NS(dm=dm, cell_i=cell_i)
    policy = clone(
        core._profile_lease_values,
        _profile_lease_views=lambda *args, **kwargs: view,
        previous=NS(
            _project=lambda context, value: value,
            _scope=lambda context: core.previous.observation.Scope(roles={}),
        ),
    )
    before = policy(parent, ctx, junctions=False).identity
    if mutation == "material":
        dm[:] = 7.0
    elif mutation == "indices":
        cell_i[:] = [1, 0]
    elif mutation == "unowned":
        other[:] = 10.0
    else:
        fields["Dm_cells"] = dm.copy()
    current = policy(parent, ctx, junctions=False).identity
    assert (current == before) is (mutation == "material" or mutation == "indices" and percent)
    assert ctx.dm is dm and ctx.cell_i is cell_i


@pytest.mark.parametrize("layer", ["profile", "trace"])
def test_inherited_hook_cannot_enter_even_an_unchanged_registered_raw_body(layer, tmp_path):
    from tests.unit import test_betse_native_seed_init_profiles as previous_controls

    ctx = previous_controls.context()
    ctx.inherited_hook_active, ctx.call_tracing = False, sys.call_tracing
    counts = []

    def registered_probe():
        counts.append("BODY_MUST_STAY_UNENTERED")

    def trigger():
        return None

    ctx.source_codes = ctx.allowed_codes = frozenset((registered_probe.__code__,))
    original = (sys.getprofile(), sys.gettrace())
    fired, locals_by_frame = [], {}

    def inherited_profile(frame, event, value):
        if original[0] is not None:
            original[0](frame, event, value)
        if (
            layer == "profile"
            and event == "call"
            and frame.f_code is trigger.__code__
            and not fired
        ):
            fired.append("profile")
            registered_probe()

    def inherited_trace(frame, event, value):
        prior = original[1] if event == "call" else locals_by_frame.get(id(frame))
        if prior is not None:
            returned = prior(frame, event, value)
            if callable(returned):
                locals_by_frame[id(frame)] = returned
        if layer == "trace" and event == "call" and frame.f_code is trigger.__code__ and not fired:
            fired.append("trace")
            registered_probe()
        if event == "return":
            locals_by_frame.pop(id(frame), None)
        return inherited_trace

    def epoch(context):
        return ("unchanged_private_metadata_epoch",)

    observer = clone(profiles._inherited_observer, _observer_epoch=epoch)
    account = contextmanager(
        clone(
            profiles._account.__wrapped__,
            _inherited_observer=observer,
            _observe=lambda *args: None,
        )
    )
    caught = None
    profiles._ACTIVE.append(ctx)
    try:
        sys.setprofile(inherited_profile)
        sys.settrace(inherited_trace)
        ctx.required_hooks = (sys.getprofile(), sys.gettrace())
        try:
            with account(ctx):
                trigger()
        except profiles.ProfilesRejected as error:
            caught = error
        assert caught is ctx.entry_error and fired == [layer] and counts == []
    finally:
        for index in (1, 0):
            (sys.setprofile, sys.settrace)[index](original[index])
        assert profiles._ACTIVE.pop() is ctx
        software.snapshot.write_json(
            tmp_path / "registered-metadata-probe.json",
            dict(
                layer=layer,
                attempted=bool(fired),
                delegate_calls=len(counts),
                rejected=caught is not None,
                actual_native_body=False,
                prior_profile_restored=sys.getprofile() is original[0],
                prior_trace_restored=sys.gettrace() is original[1],
            ),
        )
    assert sys.getprofile() is original[0] and sys.gettrace() is original[1]
