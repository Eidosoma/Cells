"""Held fresh INIT construction on an actual retained live SEED world.

No pickle/cache reader or SEED relabelling supplies authority. The public
optional Cells argument is the original retained object; the Simulator,
caches, handler and phase are newly constructed by the selected source.
"""

import builtins
import contextlib
import hashlib
import importlib
import json
import os
import sys
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, MethodType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_retained_world_source as source
from cells.processes import betse_native_phase_caches as caches
from cells.processes import betse_native_seed_init_core as core
from cells.processes import betse_native_seed_junctions as previous
from cells.processes import betse_native_tissue_configuration as factories
from cells.processes import betse_native_tissue_configuration_source as tissue_source

LAW_ID = "betse_actual_retained_seed_cells_fresh_INIT_constructor_and_core@1"
RELEASE = "CELLS_NATIVE_INIT_RETAINED_WORLD_RELEASED"
KEY_MODULE = "cells.processes.betse_native_parameter_seed_init_transition"
KEY_SOURCE_SHA256 = None
KEY_REVIEW_SHA256 = None
PARENT_SOURCE_SHA256 = None
PARENT_REVIEW_SHA256 = None
SOURCE_SHA256 = None
DYNAMICS_MODULE = "cells.processes.betse_native_init_dynamics_prelude"
DYNAMICS_INTERFACE_SHA256 = DYNAMICS_REVIEW_SHA256 = None
DYNAMICS_PARENT_REVIEW_SHA256 = None
DYNAMICS_BINDING_KIND = "exact_INIT_prelude_bytes_except_two_validated_parent_backrefs@1"
DYNAMICS_BACK_REFERENCE_SLOTS = ("PARENT_SOURCE_SHA256", "PARENT_REVIEW_SHA256")
DYNAMICS_HELPERS = ("initDenv", "get_ion")
DYNAMICS_STORES = (
    "smooth_weight_mem",
    "smooth_weight_o",
    "gj_funk",
    "D_env",
    "D_env_weight",
    "D_env_weight_base",
    "TJ_modulator",
    "TJ_targets",
    "Chi",
    "c_env_bound",
)
PARENT_CLAIM = "_claim_for_init_phase"
PARENT_CHECK = "_check_init_phase_authority"
PARAMETER_FACTORY = "seed_to_init"
PARAMETER_CHECK = "validate_closed_init"
PARAMETER_CLAIM = "SeedInitClaim"
TIMING_FIELDS = ("_run_sim", "dt", "resample", "total_time", "t_resample")
MAX_WORK = 100000
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED, _OBJECTS = (WeakKeyDictionary() for _ in range(5))
_FORWARDED = WeakKeyDictionary()
_DYNAMICS_LEASES = WeakKeyDictionary()
_ACTIVE, _FAILED, _LOCK = [], [], RLock()
_LAST_FAILED = None
_SOURCE_FILE = Path(source.__file__)
_SURFACE_ORIGINAL = factories._surface
_SURFACE_CODE = _SURFACE_ORIGINAL.__code__
_SURFACE_ALIASES = factories.aliases
_SURFACE_LEAF = _SURFACE_ALIASES._atoms
_SURFACE_LEAF_CODE = _SURFACE_LEAF.__code__
_SURFACE_LEAF_GLOBALS = tuple(
    (name, _SURFACE_LEAF.__globals__[name])
    for name in _SURFACE_LEAF_CODE.co_names
    if name in _SURFACE_LEAF.__globals__
)
_SURFACE_GLOBALS = tuple(
    (name, _SURFACE_ORIGINAL.__globals__[name])
    for name in _SURFACE_CODE.co_names
    if name in _SURFACE_ORIGINAL.__globals__ and name != "aliases"
)
_STAGES = ("phase_constructor", "init_core")
_PHASE_FIELDS = (
    "callbacks",
    "cells",
    "kind",
    "p",
    "sim",
    "cache",
    "dyna",
    "export_dirname",
)


class InitRejected(ValueError):
    def __init__(
        self,
        message,
        *,
        stage,
        request=None,
        trial=None,
        partial=None,
        source_error=None,
        capture_error=None,
    ):
        super().__init__(message)
        self.stage, self.request, self.trial = stage, request, trial
        self.partial, self.source_error, self.capture_error = partial, source_error, capture_error


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    seed_owner: object
    parent_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("A retained live Cells owner cannot be rehydrated")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    after: object
    stage_caches: tuple
    work: tuple
    events: tuple
    stream_before: object
    stream_after: object
    parameter_record: object
    source_completed: bool
    identity: str


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def source_plan():
    return dict(
        law=LAW_ID,
        literal=source.source_plan(),
        native_execution_released=False,
        key_module=KEY_MODULE,
        key_source=KEY_SOURCE_SHA256,
        key_review=KEY_REVIEW_SHA256,
        parent_source=PARENT_SOURCE_SHA256,
        parent_review=PARENT_REVIEW_SHA256,
        source_pin=SOURCE_SHA256,
        native_namespace_contract=(
            "Key automatic private consumer binding and exact two-backref template"
        ),
        native_namespace_status=(
            "Implemented against the actual seed_to_init private consumer contract; "
            "producer/consumer review pins remain unadopted."
        ),
        source_stages=_STAGES,
        parameter_api=dict(
            factory=PARAMETER_FACTORY, claim=PARAMETER_CLAIM, closed=PARAMETER_CHECK
        ),
        parent_hooks={
            PARENT_CLAIM: "(owner, *, expected=exact retained Trial, transition)",
            PARENT_CHECK: (
                "(transition, *, parameter_claim, parameter_record) -> same original parent"
            ),
        },
        old_objects=(
            "Same actual p, Cells, mesh, grid, image and global MT; no saved-owner hydration"
        ),
        new_objects="Fresh actual INIT phase, Simulator, caches/weak phase links and TissueHandler",
        parameter_stores=TIMING_FIELDS,
        source_order=(
            "Claim -> original optional-Cells constructor -> full init_core -> "
            "seal inside claim -> exact closed check -> issue"
        ),
        omitted_pickle_and_loader_authority=True,
        no_ordinary_resume_or_physical_admission=True,
        dynamics_handoff=dict(
            module=DYNAMICS_MODULE,
            interface=DYNAMICS_INTERFACE_SHA256,
            review=DYNAMICS_REVIEW_SHA256,
            parent_review=DYNAMICS_PARENT_REVIEW_SHA256,
            same_phase_original_helpers=DYNAMICS_HELPERS,
            permitted_Simulator_fields=DYNAMICS_STORES,
            prefix_only=True,
            full_init_dynamics_or_time_loop_admitted=False,
        ),
        stop_before=("sim_info_report", "run_sim_core", "init_dynamics", "INIT time loop"),
        invalidated_owners=11,
        held_postcut_cases=12,
    )


def _ready():
    if not all(
        _pin(value)
        for value in (
            KEY_SOURCE_SHA256,
            KEY_REVIEW_SHA256,
            PARENT_SOURCE_SHA256,
            PARENT_REVIEW_SHA256,
            SOURCE_SHA256,
        )
    ):
        raise InitRejected(
            "Reviewed post-SEED claim and retained-world handoff remain unbound",
            stage="unbound_contract",
        )
    for path, expected in (
        (Path(previous.__file__), PARENT_SOURCE_SHA256),
        (_SOURCE_FILE, SOURCE_SHA256),
    ):
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise InitRejected("Changed reviewed source", stage="producer")
    path = Path(__file__).resolve().parents[3] / ("src/" + KEY_MODULE.replace(".", "/") + ".py")
    if (
        path.is_symlink()
        or not path.is_file()
        or hashlib.sha256(path.read_bytes()).hexdigest() != KEY_SOURCE_SHA256
    ):
        raise InitRejected("Actual accepted parameter transition unavailable", stage="key_producer")
    key = importlib.import_module(KEY_MODULE)
    if sys.modules.get(KEY_MODULE) is not key or Path(key.__file__).resolve() != path:
        raise InitRejected("Actual canonical parameter producer required", stage="key_producer")
    _key_interface(key, path.read_bytes(), path)
    _key_private_contract(key)
    if type(getattr(key, PARAMETER_CLAIM, None)) is not type:
        raise InitRejected("Actual parameter claim type unavailable", stage="key_interface")
    for name in (PARENT_CLAIM, PARENT_CHECK):
        fn = getattr(previous, name, None)
        if type(fn) is not FunctionType or fn.__globals__ is not vars(previous):
            raise InitRejected(
                "Actual irreversible endpoint handoff unavailable", stage="parent_hook"
            )
    return key


def _key_interface(key, raw, path):
    """Metadata only: authenticate the real contextmanager plus original bodies."""
    compiled = compile(raw, str(path), "exec", dont_inherit=True)
    codes = {value.co_name: value for value in compiled.co_consts if type(value) is CodeType}
    helper = next(
        value
        for value in contextlib.contextmanager.__code__.co_consts
        if type(value) is CodeType and value.co_name == "helper"
    )
    for name in (PARAMETER_FACTORY, PARAMETER_CHECK, "consumer_interface"):
        fn = getattr(key, name, None)
        body = fn
        if name == PARAMETER_FACTORY:
            body = getattr(fn, "__wrapped__", None)
            if (
                type(fn) is not FunctionType
                or fn.__code__ is not helper
                or fn.__globals__ is not vars(contextlib)
                or fn.__code__.co_freevars != ("func",)
                or fn.__closure__ is None
                or len(fn.__closure__) != 1
                or fn.__closure__[0].cell_contents is not body
            ):
                raise InitRejected(
                    "Original public contextmanager wrapper required", stage="key_interface"
                )
        if (
            type(body) is not FunctionType
            or body.__globals__ is not vars(key)
            or body.__code__ != codes.get(name)
            or body.__code__.co_filename != str(path)
            or body.__name__ != name
            or body.__qualname__ != name
            or body.__closure__ is not None
        ):
            raise InitRejected(
                "Actual exact public parameter method required", stage="key_interface"
            )
    factory = getattr(key, PARAMETER_FACTORY).__wrapped__
    if (
        factory.__kwdefaults__ != {"enabled": False}
        or type(factory.__kwdefaults__["enabled"]) is not bool
    ):
        raise InitRejected("Original typed release default required", stage="key_interface")


def _key_private_contract(key):
    if (
        getattr(key, "CONSUMER_MODULE", None) != __name__
        or not _pin(getattr(key, "CONSUMER_INTERFACE_SHA256", None))
        or not _pin(getattr(key, "CONSUMER_REVIEW_SHA256", None))
        or not _pin(getattr(key, "CONSUMER_KEY_REVIEW_SHA256", None))
        or key.CONSUMER_KEY_REVIEW_SHA256 != KEY_REVIEW_SHA256
    ):
        raise InitRejected(
            "Actual reviewed Key private consumer contract remains unbound",
            stage="namespace_contract",
        )
    identity, backrefs = key.consumer_interface(Path(__file__).read_bytes())
    if identity != key.CONSUMER_INTERFACE_SHA256 or backrefs != (
        ("KEY_SOURCE_SHA256", KEY_SOURCE_SHA256),
        ("KEY_REVIEW_SHA256", KEY_REVIEW_SHA256),
    ):
        raise InitRejected(
            "Actual two-backref consumer binding changed", stage="namespace_contract"
        )


def request_record(value):
    return dict(law=LAW_ID, parent=value.parent_identity, source=value.source_identity)


def from_seed(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise InitRejected("Explicit retained-world INIT law required", stage="law")
    _ready()
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant INIT declaration")
        if type(owner) is not previous.JunctionsOwner or owner in _RETIRED:
            raise InitRejected("Fresh issued live junction endpoint required", stage="owner")
        parent = previous._authority(owner)
        world = parent.world.world
        if (
            parent.trial.source_completed is not True
            or world.active
            or world.invalid
            or world.parameter_record is None
            or parent.phase.p is not world.p
            or parent.phase.cells is not parent.cells
        ):
            raise InitRejected("Actual completed same-p SEED endpoint required", stage="parent")
        value = Request(owner, parent.trial.identity, _digest(source_plan()), "")
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (
            parent,
            parent.trial,
            previous._snapshot(parent),
            previous._graph(parent),
            world,
            world.claim,
            world.parameter_record,
            world.request.world_parameters,
            parent.p,
            parent.cells,
            parent.phase.callbacks,
        )
        return value


def _capture(context, error, origin, raw):
    context.last_capture = (origin, error, raw)
    if context.capture_error is None:
        context.capture_error = error
    try:
        context.capture_errors += (context.last_capture,)
    except BaseException as secondary:
        context.capture_append_error = (secondary, context.last_capture)


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = InitRejected(
            reason,
            stage=context.stage,
            request=context.request,
            trial=context.trial,
            partial=context,
        )
    raise context.entry_error


def _guard(context):
    if getattr(context, "dynamics_transition", None) is not None:
        for error in (
            context.entry_error,
            getattr(context.dynamics_transition, "entry_error", None),
            getattr(context, "dynamics_error", None),
        ):
            if error is not None:
                raise error
        context.last_dynamics_raw = sys._getframe(1)
        try:
            _dynamics_wrapper_guard(context, context.last_dynamics_raw)
        except BaseException as error:
            context.dynamics_error = error
            context.invalid = context.dynamics_transition.invalid = True
            raise
        return
    if context.entry_error is not None:
        raise context.entry_error
    if context.capture_error is not None:
        raise InitRejected(
            "Incomplete observation; no later delegate",
            stage=context.stage,
            partial=context,
            capture_error=context.capture_error,
        ) from context.capture_error
    if context.inherited:
        _reject(context, "An inherited observer cannot enter native/source work")
    _system_authority(context)
    if context.observing and (
        context.restore_getters[0]() is not context.observer_hooks[0]
        or context.restore_getters[1]() is not context.observer_hooks[1]
    ):
        _reject(context, "Both active source observers are required before further work")
    if (
        context.invalid
        or not context.active
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        _reject(context, "Actual active same-thread INIT continuation required")


def _system_authority(context):
    if (
        sys.setprofile is not context.restore_setters[0]
        or sys.settrace is not context.restore_setters[1]
        or sys.getprofile is not context.restore_getters[0]
        or sys.gettrace is not context.restore_getters[1]
        or sys.call_tracing is not context.call_tracing
    ):
        raise ValueError("Original hook setter/getter/call_tracing authority changed")


def _atoms(value):
    return core.previous.previous._atoms(value)


def _surface_atoms(value):
    # The original grid-alias sampler visits non-function leaves exactly once
    # and returns only their identity. Avoid its recursive Python visitor for
    # these leaves; functions/methods still enter the ORIGINAL live sampler.
    if type(value) not in (FunctionType, MethodType):
        return (value,)
    if (
        _SURFACE_ALIASES._atoms is not _SURFACE_LEAF
        or _SURFACE_LEAF.__code__ is not _SURFACE_LEAF_CODE
        or any(
            _SURFACE_LEAF.__globals__.get(name) is not item for name, item in _SURFACE_LEAF_GLOBALS
        )
    ):
        raise ValueError("Original live callable sampler changed before its entry")
    return _SURFACE_LEAF(value)


def _surface(cls):
    if (
        factories._surface is not _SURFACE_ORIGINAL
        or _SURFACE_ORIGINAL.__code__ is not _SURFACE_CODE
        or factories.aliases is not _SURFACE_ALIASES
        or _SURFACE_ALIASES._atoms is not _SURFACE_LEAF
        or _SURFACE_LEAF.__code__ is not _SURFACE_LEAF_CODE
        or any(
            _SURFACE_ORIGINAL.__globals__.get(name) is not value for name, value in _SURFACE_GLOBALS
        )
    ):
        raise ValueError("Original live class-surface sampler authority changed")
    namespace = dict(_SURFACE_ORIGINAL.__globals__, aliases=SimpleNamespace(_atoms=_surface_atoms))
    return FunctionType(_SURFACE_CODE, namespace)(cls)


def _bootstrap(context):
    fn, code, scope = context.checker
    if context.atoms is not fn or fn.__code__ is not code or fn.__globals__ is not scope:
        raise ValueError("Original independent metadata checker changed")
    for name, helper, retained in context.metadata:
        if globals().get(name) is not helper:
            raise ValueError("INIT continuation metadata helper replaced: " + name)
        current = context.atoms(helper)
        if len(current) != len(retained) or any(
            a is not b for a, b in zip(current, retained, strict=True)
        ):
            raise ValueError("INIT continuation helper code/default/closure changed: " + name)


def _binding(context):
    _bootstrap(context)
    result = [
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        _OBJECTS,
        _FORWARDED,
        _DYNAMICS_LEASES,
        _ACTIVE,
        _LOCK,
        context.key,
        context.parent_claim,
        context.parent_check,
        context.restore_setters,
        *context.restore_setters,
        context.restore_getters,
        *context.restore_getters,
        context.call_tracing,
        context.factories,
        context.runtime_types,
        context.objects,
        context.allowed_functions,
        context.allowed_codes,
        context.selected,
        context.methods,
        context.delegates,
        DYNAMICS_MODULE,
        DYNAMICS_INTERFACE_SHA256,
        DYNAMICS_REVIEW_SHA256,
        DYNAMICS_PARENT_REVIEW_SHA256,
        DYNAMICS_BINDING_KIND,
        DYNAMICS_BACK_REFERENCE_SLOTS,
        DYNAMICS_HELPERS,
        DYNAMICS_STORES,
        _SURFACE_ORIGINAL,
        _SURFACE_CODE,
        _SURFACE_ALIASES,
        _SURFACE_LEAF,
        _SURFACE_LEAF_CODE,
        _SURFACE_LEAF_GLOBALS,
        _SURFACE_GLOBALS,
    ]
    for name in (PARAMETER_FACTORY, PARAMETER_CHECK):
        result.extend(_atoms(getattr(context.key, name)))
    for role, cls in context.factories.items():
        result.extend((role, cls, *_surface(cls)))
    for role, cls in context.runtime_types.items():
        result.extend((role, cls, *_surface(cls)))
    for fn in (*context.native_functions, *context.methods.values(), *context.allowed_functions):
        result.extend(_atoms(fn))
        result.append(fn.__globals__)
        for name in fn.__code__.co_names:
            if name in fn.__globals__:
                value = fn.__globals__[name]
                result.extend((name, value))
                if type(value) in (FunctionType, MethodType):
                    result.extend(_atoms(value))
    return tuple(result)


def _projector(context):
    return SimpleNamespace(
        objects=[
            *context.parent.world.parent.projector.objects,
            *context.objects,
            *(("weak_phase", value) for value in context.proxies),
            ("retained_cells", context.cells),
            ("parameters", context.p),
            ("callback", context.callback),
        ]
    )


def _seed_projection(context):
    lease = context.seed_lease
    for (_, actual), holder, names, target in zip(
        lease.objects, lease.holders, lease.names, lease.fields, strict=True
    ):
        if vars(actual) is not holder:
            raise ValueError("Original SEED source object's holder dictionary changed")
        current = tuple(holder)
        if actual is context.p:
            if tuple(name for name in current if name not in TIMING_FIELDS) != tuple(
                name for name in names if name not in TIMING_FIELDS
            ):
                raise ValueError("Unowned original parameter field roster changed")
        elif current != names:
            raise ValueError("Original historical phase/Simulator/Cells/handler stores changed")
        target.clear()
        target.update(
            (name, holder[name])
            for name in names
            if actual is not context.p or name not in TIMING_FIELDS
        )
    return lease.view


def _seed_values(context):
    view = _seed_projection(context)
    projected = core._LITERAL._project(context.seed_lease.projector, view.fields)
    return core.previous._scope(context.parent.world).snapshot(projected)


def _seed_graph(context):
    view = _seed_projection(context)
    return core.previous._scope(context.parent.world).graph(view, view, context.seed_lease.tape)


def _seed_edge_records(module, current):
    roots = [current, getattr(current, "request", None), getattr(current, "owner", None)]
    roots.extend(value for _, value in getattr(current, "objects", ()))
    registries = []
    for name in (
        "_REQUESTS",
        "_CONSUMED",
        "_RETIRED",
        "_ISSUED",
        "_FORWARDED",
        "_OBJECTS",
        "_WORLD",
        "_MESHES",
        "_GRIDS",
        "_MESH_ANCESTRY",
        "_TAIL_ROUTES",
        "_DYNAMICS_LEASES",
    ):
        registry = vars(module).get(name)
        if registry is None:
            continue
        if type(registry) is ModuleType:
            if name != "_WORLD":
                raise ValueError("An actual declared issuance registry is required: " + name)
            # The endpoint's _WORLD names its original Poisson MODULE. Retain
            # that exact alias edge; do not pretend that it has issued entries.
            registries.append((name, registry, ()))
            continue
        if type(registry) not in (dict, WeakKeyDictionary):
            raise ValueError("An actual declared issuance registry is required: " + name)
        entries = []
        for key, value in registry.items():
            target = value[0] if type(value) is tuple and value else value
            if target is current or any(key is root or value is root for root in roots):
                entries.append((key, value, tuple(value) if type(value) is tuple else ()))
        registries.append((name, registry, tuple(entries)))
    fields = tuple(
        (name, getattr(current, name))
        for name in (
            "request",
            "refs",
            "trial",
            "parent",
            "phase",
            "p",
            "cells",
            "sim",
            "dyna",
            "grid",
            "mesh",
            "rng",
            "mask",
            "objects",
            "holders",
            "runtime_types",
            "entries",
        )
        if hasattr(current, name)
    )
    return module, current, fields, tuple(registries)


def _capture_seed_lease(context):
    """Called once by the actual endpoint claim, before any p/phase mutation."""
    caller = sys._getframe(1)
    if (
        caller.f_code is not getattr(previous, PARENT_CLAIM).__code__
        or caller.f_locals.get("transition") is not context
        or previous._init_route(context.parent)[0] is not context
        or context.claim is not None
        or context.phase is not None
        or hasattr(context, "seed_lease")
    ):
        raise ValueError("Actual fresh irreversible endpoint claim required")
    parent, world = context.parent, context.refs[4]
    original_core = parent.parent.parent
    members = [
        *core._profile_ancestor_members(original_core),
        (previous.previous, parent.parent),
        (previous, parent),
    ]
    members.extend((module, module._WORLD[world.request]) for module in world.api.stages)
    edges = core._profile_ancestor_edges(original_core)
    edges += tuple(_seed_edge_records(module, current) for module, current in members)
    objects = []
    for _, current in members:
        for pair in getattr(current, "objects", ()):
            if hasattr(pair[1], "__dict__") and not any(old is pair[1] for _, old in objects):
                objects.append(pair)
    for role, actual in (
        ("parameters", context.p),
        ("old_phase", parent.phase),
        ("old_simulator", parent.sim),
        ("old_handler", parent.dyna),
        ("Cells", context.cells),
        ("mesh", parent.mesh),
        ("grid", parent.grid),
    ):
        if not any(old is actual for _, old in objects):
            objects.append((role, actual))
    fields = [{} for _ in objects]
    lease = SimpleNamespace(
        edges=edges,
        objects=tuple(objects),
        holders=tuple(vars(actual) for _, actual in objects),
        names=tuple(tuple(vars(actual)) for _, actual in objects),
        fields=fields,
        view=SimpleNamespace(objects=tuple(objects), fields=fields),
        tape=SimpleNamespace(rng=parent.rng, events=(), draws=(), locals={}),
        projector=SimpleNamespace(
            objects=[
                *parent.world.parent.projector.objects,
                *objects,
                *world.world_proxy_roots.values(),
            ]
        ),
        samplers=[],
        files=[],
        stream=_rng(context),
    )
    context.seed_lease = lease
    candidates = []
    for module, current in members:
        if hasattr(module, "_bindings"):
            fn = module._bindings
            args = () if fn.__code__.co_argcount == 0 else (current,)
            candidates.append((module, "_bindings", args))
        elif hasattr(module, "_binding"):
            candidates.append((module, "_binding", (current,)))
        for name in ("_native_bindings", "_namespace_bindings", "_scope_bindings"):
            marker = name.removeprefix("_")
            if hasattr(current, marker) and hasattr(module, name):
                candidates.append((module, name, (current,)))
    candidates.append((parent.api, "_bindings", (world,)))
    for module, name, args in candidates:
        fn = getattr(module, name)
        atoms = context.atoms(fn)
        saved = tuple(fn(*args))
        lease.samplers.append((module, name, fn, atoms, args, saved))
        path = Path(module.__file__)
        if all(path != old for old, _ in lease.files):
            lease.files.append((path, hashlib.sha256(path.read_bytes()).hexdigest()))
    lease.values, lease.graph = _seed_values(context), _seed_graph(context)
    return lease


def _check_seed_lease(context):
    """Factored original authority; never reopen a pre-timing SEED validator."""
    lease = context.seed_lease
    core._check_profile_ancestor_edges(lease)
    for path, expected in lease.files:
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Retained original SEED producer bytes changed")
    for module, name, fn, atoms, args, saved in lease.samplers:
        if getattr(module, name) is not fn:
            raise ValueError("Retained original authority sampler replaced")
        current = context.atoms(fn)
        if len(current) != len(atoms) or any(
            a is not b for a, b in zip(current, atoms, strict=True)
        ):
            raise ValueError("Retained original authority sampler code/delegate changed")
        actual = tuple(fn(*args))
        if len(actual) != len(saved) or any(a is not b for a, b in zip(actual, saved, strict=True)):
            raise ValueError("Retained original source/callable/runtime binding changed")
    if (
        _seed_values(context).identity != lease.values.identity
        or _rng(context).identity != lease.stream.identity
    ):
        raise ValueError("INIT changed a historical source value or continuing MT")
    graph = _seed_graph(context)
    core.previous._same(graph[0], lease.graph[0])
    if graph[1] != lease.graph[1]:
        raise ValueError("INIT changed an original source holder/array/alias/reference edge")


def _snapshot(context):
    values = dict(
        objects=tuple(
            dict(role=role, fields=core._LITERAL._project(_projector(context), vars(actual)))
            for role, actual in context.objects
        ),
        retained_cells=core._LITERAL._project(_projector(context), vars(context.cells)),
        parameters=core._LITERAL._project(_projector(context), vars(context.p)),
    )
    return core.previous._scope(context.parent.world).snapshot(values)


def _graph(context):
    context.graph_fields[:] = [vars(actual) for _, actual in context.objects]
    context.graph_view.objects = context.objects
    context.graph_view.fields = context.graph_fields
    context.graph_view.retained_cells = vars(context.cells)
    context.graph_view.parameters = vars(context.p)
    context.graph_view.weak_proxies = context.proxies
    return core.previous._scope(context.parent.world).graph(
        context.graph_view, context.graph_view, context.graph_tape
    )


def _rng(context):
    return core.previous._rng(context.parent.world)


def _check(context, *, closed=False):
    _bootstrap(context)
    _system_authority(context)
    if not closed:
        _guard(context)
    if (
        _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.seed_owner) is not context
        or context.parent is not context.refs[0]
        or context.parent.trial is not context.refs[1]
        or context.cells is not context.refs[9]
        or context.p is not context.refs[8]
        or context.callback is not context.refs[10]
        or context.seed_claim is not context.refs[5]
        or context.seed_owner is not context.refs[7]
        or context.key is not _ready()
        or _digest(request_record(context.request)) != context.request.identity
        or _digest(context.plan) != context.request.source_identity
    ):
        raise ValueError("Exact retained-world request/parameter/callback ancestry changed")
    core.previous._same(_binding(context), context.bindings)
    for path, expected in context.source_files:
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Reached actual native source bytes changed")
    if (
        context.parent_check(
            context, parameter_claim=context.claim, parameter_record=context.parameter_record
        )
        is not context.parent
    ):
        raise ValueError("Different retained live endpoint after INIT retirement")
    if context.parameter_record is None:
        if (
            type(context.claim) is not getattr(context.key, PARAMETER_CLAIM)
            or context.claim.parameters is not context.p
        ):
            raise ValueError("Actual active same-p parameter continuation required")
        context.claim.check()
    elif (
        getattr(context.key, PARAMETER_CHECK)(
            context.claim, seed_claim=context.seed_claim, original_owner=context.seed_owner
        )
        is not context.parameter_record
    ):
        raise ValueError("Exact successful closed INIT parameter record required")
    if _rng(context).identity != context.stream_before.identity:
        raise ValueError("Constructor/init_core unexpectedly changed the continuing MT")
    for actual, holder in context.holders:
        if vars(actual) is not holder or _OBJECTS.get(actual) is not context:
            raise ValueError("New source object/attribute-holder issuance changed")
    if context.phase is not None:
        fields = vars(context.phase)
        names = tuple(fields)
        if names != _PHASE_FIELDS[: len(names)] or len(names) > len(_PHASE_FIELDS):
            raise ValueError("Original phase store order changed")
        for name, expected in (
            ("p", context.p),
            ("cells", context.cells),
            ("callbacks", context.callback),
            ("kind", context.kind),
        ):
            if name in fields and fields[name] is not expected:
                raise ValueError("Original constructor alias changed: " + name)
        for name, role in (
            ("sim", "Simulator"),
            ("cache", "SimPhaseCaches"),
            ("dyna", "TissueHandler"),
        ):
            if name in fields and not any(
                actual is fields[name] and issued == role
                for issued, actual in context.completed_objects
            ):
                raise ValueError("Phase assigned object before its actual constructor completed")
        if "sim" in fields and fields["sim"] is context.parent.sim:
            raise ValueError("INIT must construct a fresh Simulator")


def _event(context, name, raw):
    context.last_raw = (name, raw)
    try:
        context.events.append(context.last_raw)
    except BaseException as error:
        _capture(context, error, "event", context.last_raw)
    _guard(context)


def _namespace(context):
    methods = {
        name: getattr(factories._Descriptor, name) for name in ("__init__", "__get__", "__set__")
    }
    scope = dict(
        vars(factories),
        _guard=_guard,
        _native_call=_invoke,
        _OBJECTS=_OBJECTS,
        _surface=factories._surface,
        _lazy_factory=lambda current, role: current.factories[role],
    )
    descriptor = type(
        "InitSourceDescriptor",
        (),
        {
            name: FunctionType(fn.__code__, scope, fn.__name__, fn.__defaults__, fn.__closure__)
            for name, fn in methods.items()
        },
    )
    scope["_Descriptor"] = descriptor
    context.factory_scope = scope
    context.make = FunctionType(factories._make.__code__, scope)
    scope["_runtime_type"] = FunctionType(factories._runtime_type.__code__, scope)
    context.import_namespaces = {}
    for module_name, roles in context.import_roster.items():
        context.import_namespaces[module_name] = SimpleNamespace(
            **{
                role: (lambda *args, _role=role, **kwargs: _make(context, _role, *args, **kwargs))
                for role in roles
            }
        )
    for role in context.factories:
        scope["_runtime_type"](context, role)
    context.methods, context.delegates = {}, {}
    for role, name in context.selected:
        native = getattr(context.factories[role], name)
        chain = caches.previous.callbacks.simulator._chain(native)
        original = chain[-1]
        namespace = dict(original.__globals__)
        namespace["__builtins__"] = dict(
            vars(builtins), __import__=lambda *args, **kwargs: _imports(context, *args, **kwargs)
        )
        for factory_name in context.factory_names:
            if factory_name in namespace:
                namespace[factory_name] = lambda *args, _role=factory_name, **kwargs: _make(
                    context, _role, *args, **kwargs
                )
        method = FunctionType(
            original.__code__,
            namespace,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        method.__kwdefaults__ = original.__kwdefaults__
        context.methods[(role, name)] = method
        context.delegates[(role, name)] = native
    # Reach the original source helpers through ORIGINAL globals. Traversing
    # copied constructor globals would follow our private factory lambdas into
    # the driver itself, misclassifying its guards/dispatcher as native bodies.
    reached = core.previous.previous._native_helper_functions(context.native_functions)
    context.allowed_functions = tuple(
        {id(fn): fn for fn in (*reached, *context.methods.values())}.values()
    )
    for fn in context.allowed_functions:
        path = Path(fn.__code__.co_filename)
        if path.is_absolute() and path.is_relative_to(source.NATIVE):
            name = str(path.relative_to(source.NATIVE))
            expected = tissue_source.SOURCE_PINS.get(name)
            if (
                expected is None
                or path.is_symlink()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected
            ):
                raise ValueError("Unpinned reached native helper: " + name)
            if (path, expected) not in context.source_files:
                context.source_files.append((path, expected))
    context.allowed_codes = frozenset(
        code for fn in context.allowed_functions for code in _code_tree(fn.__code__)
    )


def _code_tree(code):
    result = [code]
    for child in code.co_consts:
        if type(child) is CodeType:
            result.extend(_code_tree(child))
    return tuple(result)


def _normal_return(frame):
    return previous.previous._normal_return(frame)


def _admit(context, frame):
    old = context.frames.get(id(frame))
    if old is not None:
        if old["frame"] is not frame or old["returned"]:
            _reject(context, "Repeated or replaced completed native frame")
        return old
    selected = frame.f_code in context.allowed_codes
    native = frame.f_code.co_filename.startswith(str(source.NATIVE) + os.sep)
    if not selected and not native:
        return None
    row = dict(
        sequence=len(context.work),
        layer="native_call_or_selected_body",
        stage=context.stage,
        filename=frame.f_code.co_filename,
        function=frame.f_code.co_qualname,
        body_started=False,
        status="attempted",
        entry_is_case=False,
    )
    attempt = dict(
        frame=frame, work=row, returned=False, code=frame.f_code, globals=frame.f_globals
    )
    context.last_frame_attempt = attempt
    context.work.append(row)
    if len(context.work) > MAX_WORK:
        _reject(context, "Bounded original-source work log exhausted")
    _guard(context)
    if not selected:
        _reject(context, "An unbound native helper/body attempted entry")
    invocation = context.invocations[-1] if context.invocations else None
    if invocation is None:
        _reject(context, "Source entry requires an actual guarded constructor/core invocation")
    method = context.methods[(invocation["role"], invocation["method"])]
    if frame.f_code is method.__code__:
        if frame.f_back is not invocation["frame"] or invocation["body"] is not None:
            _reject(context, "Raw or reentrant selected source body")
        if frame.f_locals.get("self") is not invocation["actual"]:
            _reject(context, "Different actual source receiver")
        invocation["body"] = frame
    else:
        ancestor = frame.f_back
        while ancestor is not None and ancestor is not invocation["body"]:
            if ancestor is context.source_frame:
                break
            ancestor = ancestor.f_back
        if ancestor is not invocation["body"]:
            _reject(context, "Helper source entry is detached from its original active body")
    context.frames[id(frame)] = attempt
    row["status"], row["body_started"] = "admitted", True
    return attempt


def _observe(context, frame, event, arg):
    if event == "call":
        _admit(context, frame)
    row = context.frames.get(id(frame))
    if row is None:
        return
    if (
        row["frame"] is not frame
        or frame.f_code is not row["code"]
        or frame.f_globals is not row["globals"]
    ):
        _reject(context, "Actual source frame/code/namespace changed")
    if event == "exception":
        context.pending[id(frame)] = arg[1]
        context.last_source_exception = (frame, arg[1])
    if event == "return":
        # Direct roots precede ALL fallible copying/append/observers.
        context.last_raw_return = (frame, arg)
        if not _normal_return(frame):
            original = context.pending.get(id(frame))
            if (
                context.primary is None
                and context.capture_error is None
                and context.entry_error is None
            ):
                context.primary = original
        if type(arg) in weakref.ProxyTypes and not any(arg is value for value in context.proxies):
            context.proxies.append(arg)
        try:
            context.locals[(frame.f_code.co_filename, frame.f_code.co_qualname)] = dict(
                frame.f_locals
            )
            context.raw_returns.append(context.last_raw_return)
        except BaseException as error:
            _capture(context, error, "source_return_locals", context.last_raw_return)
        row["returned"] = True
        row["work"]["status"] = "returned_or_unwound"


def _epoch(context):
    return _snapshot(context).identity, _graph(context), _rng(context).identity


def _same_epoch(context, old):
    current = _epoch(context)
    core.previous._same(current[1][0], old[1][0])
    if current[0] != old[0] or current[1][1] != old[1][1] or current[2] != old[2]:
        raise ValueError("Inherited observer changed source values/reference edges/global MT")


def _observer_delegate(observer, frame, event, arg):
    return observer(frame, event, arg)


def _inherited(context, delegate, frame, event, arg):
    if delegate is None:
        return None
    if context.inherited:
        _reject(context, "Reentrant inherited observer")
    old = _epoch(context)
    context.inherited = True
    primary = None
    try:
        return context.call_tracing(_observer_delegate, (delegate, frame, event, arg))
    except BaseException as error:
        primary = error
        raise
    finally:
        context.inherited = False
        capture = None
        try:
            _same_epoch(context, old)
            if context.observing and (
                context.restore_getters[0]() is not context.observer_hooks[0]
                or context.restore_getters[1]() is not context.observer_hooks[1]
            ):
                raise ValueError("Inherited observer disabled or replaced an active hook")
        except BaseException as error:
            capture = error
            _capture(context, error, "inherited_observer_state", (frame, event, arg))
        if context.entry_error is not None:
            raise context.entry_error
        if primary is None and context.primary is None and capture is not None:
            raise capture


def _restore(context):
    for index in (1, 0):
        try:
            context.restore_setters[index](context.required_hooks[index])
        except BaseException as error:
            context.cleanup_errors += (("restore", error, index),)
    samples = []
    for order in ((0, 1), (1, 0)):
        pair = [None, None]
        for index in order:
            try:
                pair[index] = context.restore_getters[index]()
            except BaseException as error:
                context.cleanup_errors += (("restore_sample", error, index),)
        samples.append(tuple(pair))
    context.final_hook_samples = tuple(samples)
    context.hooks_safe = all(
        pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
        for pair in samples
    )
    return context.hooks_safe and not context.cleanup_errors


@contextmanager
def _account(context):
    previous_profile, previous_trace = context.required_hooks
    locals_by_frame = {}
    primary = None

    def profile(frame, event, arg):
        if context.inherited:
            if event == "call" and (
                frame.f_code in context.allowed_codes
                or frame.f_code.co_filename.startswith(str(source.NATIVE) + os.sep)
            ):
                _reject(context, "Observer attempted raw source entry")
            return
        if event == "call":
            _admit(context, frame)
        try:
            _inherited(context, previous_profile, frame, event, arg)
        except BaseException as error:
            _capture(context, error, "inherited_profile", (frame, event, arg))
            if event not in ("return", "c_return", "c_exception") or context.primary is None:
                raise

    def trace(frame, event, arg):
        selected = frame.f_code in context.allowed_codes
        native = frame.f_code.co_filename.startswith(str(source.NATIVE) + os.sep)
        if context.inherited:
            if event == "call" and (selected or native):
                _reject(context, "Observer attempted raw source entry")
            return trace
        # Native exception and raw return witnesses precede inherited callbacks.
        if selected or native:
            try:
                _observe(context, frame, event, arg)
            except BaseException as error:
                if error is not context.entry_error:
                    _capture(context, error, "source_observation", (frame, event, arg))
                if event != "return" or context.primary is None:
                    raise
        prior = previous_trace if event == "call" else locals_by_frame.get(id(frame))
        try:
            local = _inherited(context, prior, frame, event, arg)
            if callable(local):
                locals_by_frame[id(frame)] = local
        except BaseException as error:
            _capture(context, error, "inherited_trace", (frame, event, arg))
            if event != "return" or context.primary is None:
                raise
        finally:
            if event == "return":
                locals_by_frame.pop(id(frame), None)
                context.pending.pop(id(frame), None)
        return trace

    context.observer_hooks = (profile, trace)
    try:
        context.restore_setters[0](profile)
        context.restore_setters[1](trace)
        if context.restore_getters[0]() is not profile or context.restore_getters[1]() is not trace:
            raise ValueError("Both source observers must be installed before source execution")
        context.observing = True
        yield
    except BaseException as error:
        selected = context.entry_error if context.entry_error is not None else context.primary
        primary = selected if selected is not None else error
        if selected is not None and selected is not error:
            _capture(context, error, "interrupted_primary", selected)
            raise selected  # noqa: B904 - retain exact primary/cause.
        raise
    finally:
        context.observing = False
        cleanup = None
        try:
            _restore(context)
        except BaseException as error:
            cleanup = error
            context.cleanup_errors += (("restore_entry_or_return", error, None),)
        # Independent caller-boundary recovery if a hook rejects _restore's
        # own entry. Both setters and BOTH post-restoration samples are tried.
        for index in (1, 0):
            try:
                context.restore_setters[index](context.required_hooks[index])
            except BaseException as error:
                context.cleanup_errors += (("caller_restore", error, index),)
        samples = []
        for order in ((0, 1), (1, 0)):
            pair = [None, None]
            for index in order:
                try:
                    pair[index] = context.restore_getters[index]()
                except BaseException as error:
                    context.cleanup_errors += (("caller_sample", error, index),)
            samples.append(tuple(pair))
        context.final_hook_samples = tuple(samples)
        context.hooks_safe = all(
            pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
            for pair in samples
        )
        if not context.hooks_safe or context.cleanup_errors:
            context.invalid = True
            if primary is None and context.primary is None and context.entry_error is None:
                raise (
                    cleanup
                    if cleanup is not None
                    else ValueError("Original observer restoration incomplete")
                )


def _imports(context, name, globals=None, locals=None, fromlist=(), level=0):
    _guard(context)
    if level != 0 or name not in context.import_namespaces or not fromlist:
        raise ValueError("Only the original selected constructor imports are admitted")
    namespace = context.import_namespaces[name]
    if any(not hasattr(namespace, field) for field in fromlist):
        raise ValueError("Unselected imported constructor")
    _event(context, "constructor_import", (name, tuple(fromlist)))
    return namespace


def _make(context, role, /, *args, **kwargs):
    _guard(context)
    caller = sys._getframe(1)
    if role == "SimPhase":
        if (
            context.phase is not None
            or caller is not context.source_frame
            or context.stage != "phase_constructor"
        ):
            _reject(context, "One fresh original phase constructor required")
    elif not context.invocations:
        _reject(context, "Nested object creation requires its actual source body")
    actual = context.make(context, role, *args, **kwargs)
    context.completed_objects.append((role, actual))
    if role == "SimPhase":
        context.phase = actual
    return actual


def _sync_objects(context):
    """A new holder can appear only at its guarded, registered __init__ entry."""
    for role, actual in context.objects:
        if not any(old is actual for old, _ in context.holders):
            if (
                _OBJECTS.get(actual) is not context
                or type(actual) is not context.runtime_types[role]
            ):
                _reject(context, "A foreign constructor object entered the issuance roster")
            context.holders.append((actual, vars(actual)))


def _invoke(context, label, delegate, *args, **kwargs):
    if getattr(context, "dynamics_transition", None) is not None:
        for error in (
            context.entry_error,
            getattr(context.dynamics_transition, "entry_error", None),
            getattr(context, "dynamics_error", None),
        ):
            if error is not None:
                raise error
        context.last_dynamics_raw = (sys._getframe(), label, delegate, args, kwargs)
        try:
            transition, _ = _dynamics_route(context)
            _dynamics_dispatch_guard(
                context, transition, label, delegate, args, kwargs, sys._getframe()
            )
            # Keep this DIRECT call: Key authenticates this actual _invoke
            # frame and its original wrapper/prefix caller, not a substitute.
            return transition.entries["dispatch"](
                transition, context, label, delegate, args[0], args[1:], kwargs, sys._getframe()
            )
        except BaseException as error:
            context.dynamics_error = error
            context.invalid = context.dynamics_transition.invalid = True
            raise
    _guard(context)
    if not args or _OBJECTS.get(args[0]) is not context:
        _reject(context, "Actual new constructor-issued object required")
    role, method = label.split(".", 1)
    selected = context.methods.get((role, method))
    if selected is None or context.delegates[(role, method)] is not delegate:
        _reject(context, "Unselected raw method or changed original delegate")
    actual = args[0]
    if type(actual) is not context.runtime_types[role]:
        _reject(context, "Original constructor runtime type changed")
    _sync_objects(context)
    frame = sys._getframe()
    parent = frame.f_back.f_back
    if not _entry_allowed(context, role, method, actual, args, kwargs, parent):
        _reject(context, "Original constructor/core entry order or nesting changed")
    attempt = dict(
        frame=frame,
        role=role,
        method=method,
        actual=actual,
        args=args,
        kwargs=kwargs,
        body=None,
        returned=False,
    )
    context.invocations.append(attempt)
    context.last_attempt = attempt
    context.attempts.append(attempt)
    try:
        _check(context)
        _event(context, label + "_enter", (args, kwargs))
        try:
            returned = selected(*args, **kwargs)
        except BaseException as error:
            if (
                context.primary is None
                and context.entry_error is None
                and context.capture_error is None
            ):
                context.primary = error
            raise
        context.last_method_return = (label, returned)
        attempt["returned"] = True
        context.method_returns.append((role, method, actual, returned))
        _event(context, label + "_return", returned)
        _check(context)
        return returned
    finally:
        if context.invocations and context.invocations[-1] is attempt:
            context.invocations.pop()
        else:
            context.invalid = True


def _entry_allowed(context, role, method, actual, args, kwargs, parent):
    if method == "__init__":
        if parent is None or parent.f_code is not factories._make.__code__:
            return False
        if role == "SimPhase":
            context.phase = actual  # Raw allocation retained before any source store.
            return (
                kwargs.get("kind") is context.kind
                and kwargs.get("p") is context.p
                and kwargs.get("cells") is context.cells
                and kwargs.get("callbacks") is context.callback
                and "sim" not in kwargs
            )
        return bool(context.invocations)
    if role == "SimPhase" and method in ("_init_kludge", "_init_kludge_time"):
        expected = "__init__" if method == "_init_kludge" else "_init_kludge"
        return (
            bool(context.invocations)
            and context.invocations[-1]["role"] == role
            and context.invocations[-1]["method"] == expected
            and parent is context.invocations[-1]["body"]
        )
    if role == "TissueHandler" and method in (
        "_init_tissues",
        "_init_cuts",
        "_init_events",
        "_init_events_global",
    ):
        expected = "_init_events" if method == "_init_events_global" else "__init__"
        return (
            bool(context.invocations)
            and context.invocations[-1]["role"] == role
            and context.invocations[-1]["method"] == expected
            and parent is context.invocations[-1]["body"]
        )
    if role == "Simulator" and method == "init_core":
        return (
            context.stage == "init_core"
            and not context.invocations
            and parent is context.source_frame
            and len(args) == 2
            and args[1] is context.phase
            and not kwargs
        )
    if role == "Simulator" and method == "initDenv":
        return (
            bool(context.invocations)
            and context.invocations[-1]["role"] == role
            and context.invocations[-1]["method"] == "init_core"
            and parent is context.invocations[-1]["body"]
            and len(args) == 3
            and args[1] is context.cells
            and args[2] is context.p
            and not kwargs
        )
    return False


def _acquire(context):
    assembly = SimpleNamespace()
    caches.previous._acquire(assembly)
    cache = SimpleNamespace()
    caches._acquire(cache)
    handler = SimpleNamespace()
    dyna = core._BASE.image.prefix.previous.previous
    dyna._acquire(handler)
    context.factories = {
        **assembly.factories,
        **cache.factories,
        **handler.factories,
        "TissueHandler": handler.native_handler,
    }
    context.kind = assembly.kind.__class__.INIT
    if context.kind is assembly.kind or context.kind.name != "INIT":
        raise ValueError("Genuine original native INIT enum required")
    context.import_roster = {name: tuple(roles) for name, roles in caches.IMPORTS.items()}
    context.import_roster.update(
        {name: tuple(roles) for name, roles in caches.previous.IMPORTS.items()}
    )
    context.factory_names = tuple(context.factories)
    selected = {
        ("SimPhase", "__init__"),
        ("SimPhase", "_init_kludge"),
        ("SimPhase", "_init_kludge_time"),
        ("Simulator", "__init__"),
        ("Simulator", "init_core"),
        ("Simulator", "initDenv"),
        *((role, "__init__") for role in cache.factories),
        *(("TissueHandler", name) for name in dyna.METHODS),
    }
    for role in handler.factories:
        selected.add((role, "__init__"))
    context.selected = tuple(sorted(selected))
    for role, name in context.selected:
        member = getattr(context.factories[role], name)
        chain = caches.previous.callbacks.simulator._chain(member)
        if not chain or type(chain[-1]) is not FunctionType:
            raise ValueError("Actual original constructor/method chain required")
        body = chain[-1]
        native_path = Path(body.__code__.co_filename)
        if not native_path.is_relative_to(source.NATIVE):
            raise ValueError("Original native method source filename required")
        owner_name = body.__qualname__.split(".")[0]
        caches.previous.callbacks._source_function(
            member, str(native_path.relative_to(source.NATIVE)), name, owner_name
        )
    context.native_functions = tuple(
        fn
        for role, name in context.selected
        for fn in caches.previous.callbacks.simulator._chain(getattr(context.factories[role], name))
    )
    context.source_files = []
    for fn in context.native_functions:
        original_path = Path(fn.__code__.co_filename)
        if original_path.is_relative_to(source.NATIVE):
            name = str(original_path.relative_to(source.NATIVE))
            expected = tissue_source.SOURCE_PINS.get(name)
            if (
                expected is None
                or original_path.is_symlink()
                or hashlib.sha256(original_path.read_bytes()).hexdigest() != expected
            ):
                raise ValueError("Unpinned actual constructor/helper source: " + name)
            pair = (original_path, expected)
            if pair not in context.source_files:
                context.source_files.append(pair)


def _raw_context(request, refs, key):
    parent = refs[0]
    return SimpleNamespace(
        request=request,
        refs=refs,
        parent=parent,
        key=key,
        seed_claim=refs[5],
        seed_owner=refs[7],
        p=refs[8],
        cells=refs[9],
        callback=refs[10],
        claim=None,
        parameter_record=None,
        thread=get_ident(),
        active=True,
        invalid=False,
        validating=False,
        inherited=False,
        observing=False,
        stage="endpoint_retirement",
        driver_frame=None,
        phase=None,
        trial=None,
        primary=None,
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        cleanup_errors=(),
        work=[],
        events=[],
        locals={},
        attempts=[],
        invocations=[],
        method_returns=[],
        raw_returns=[],
        frames={},
        pending={},
        last_raw_return=None,
        last_source_exception=None,
        objects=[],
        holders=[],
        proxies=[],
        completed_objects=[],
        runtime_types={},
        runtime_bindings={},
        graph_view=SimpleNamespace(),
        graph_fields=[],
        graph_tape=SimpleNamespace(rng=parent.rng, events=(), draws=(), locals={}),
        native_functions=(),
        methods={},
        before=None,
        after=None,
        stage_caches=[],
        stream_before=None,
        stream_after=None,
        private_seal=None,
        last_raw=None,
        required_hooks=(sys.getprofile(), sys.gettrace()),
        restore_setters=(sys.setprofile, sys.settrace),
        restore_getters=(sys.getprofile, sys.gettrace),
        call_tracing=sys.call_tracing,
        hooks_safe=True,
    )


def _retain(context, primary):
    global _LAST_FAILED
    _LAST_FAILED = context
    context.invalid = True
    context.failure_error = primary
    try:
        context.failed_parameter_claim = getattr(primary, "seed_init_claim", None)
    except BaseException as capture:
        context.failed_claim_capture = (capture, primary)
    try:
        _FAILED.append(context)
    except BaseException as capture:
        context.failure_append_error = (capture, context)
    try:
        primary.init_retained_world_partial = context
    except BaseException as capture:
        context.failure_attachment_error = (capture, context)


def _closed(context):
    if type(context.claim) is not getattr(context.key, PARAMETER_CLAIM):
        raise ValueError("Actual issued post-SEED transition claim required")
    record = context.claim.record
    context.raw_record = record
    actual = getattr(context.key, PARAMETER_CHECK)(
        context.claim,
        seed_claim=context.seed_claim,
        original_owner=context.seed_owner,
    )
    if actual is not record:
        raise ValueError("Exact successful original INIT claim/parameter record required")
    context.parameter_record = record
    return record


def _seal(context):
    _check(context)
    phase = context.phase
    if (
        phase is context.parent.phase
        or phase.cells is not context.cells
        or phase.p is not context.p
        or phase.sim is context.parent.sim
        or phase.kind is not context.kind
        or tuple(vars(phase)) != _PHASE_FIELDS
        or phase.sim.dyna is not phase.dyna
        or phase.export_dirname is not context.p.init_export_dirname
        or phase.cache is context.parent.phase.cache
        or phase.dyna is context.parent.dyna
        or context.invocations
        or context.primary is not None
        or context.capture_error is not None
        or not context.hooks_safe
        or context.cleanup_errors
    ):
        raise ValueError("Complete genuine fresh INIT constructor/core result required")
    _completion(context)
    context.after, context.stream_after = _snapshot(context), _rng(context)
    context.graph = _graph(context)
    context.private_seal = (phase, context.after, context.graph)


def _check_post_claim_seal(context):
    if (
        context.private_seal[0] is not context.phase
        or _snapshot(context).identity != context.private_seal[1].identity
    ):
        raise ValueError("Post-claim callback changed the sealed source state")
    current = _graph(context)
    core.previous._same(current[0], context.private_seal[2][0])
    if current[1] != context.private_seal[2][1]:
        raise ValueError("Post-claim callback changed a sealed alias/reference edge")


def _completion(context):
    required = (
        ("SimPhase", "__init__"),
        ("SimPhase", "_init_kludge"),
        ("SimPhase", "_init_kludge_time"),
        ("Simulator", "__init__"),
        ("Simulator", "init_core"),
        ("SimPhaseCaches", "__init__"),
        *(
            ("TissueHandler", name)
            for name in (
                "__init__",
                "_init_tissues",
                "_init_cuts",
                "_init_events",
                "_init_events_global",
            )
        ),
    )
    completed = tuple((role, method) for role, method, actual, returned in context.method_returns)
    if any(completed.count(key) != 1 for key in required):
        raise ValueError("Every selected constructor/helper/core call must complete exactly once")
    if completed.count(("Simulator", "initDenv")) != int(bool(context.p.is_ecm)):
        raise ValueError("Original conditional initDenv source completion required")
    if any(returned is not None for _, _, _, returned in context.method_returns):
        raise ValueError("Original selected constructors/core methods return None")
    if any(not row["returned"] for row in context.frames.values()):
        raise ValueError("Unfinished admitted source/helper frame")


def _coordinate(context):
    """One real parameter claim through source construction and fallible sealing."""
    context.source_frame = sys._getframe()
    key = context.key
    with getattr(key, PARAMETER_FACTORY)(
        context.seed_claim,
        original_owner=context.seed_owner,
        law_id=key.SEED_INIT_LAW,
        enabled=True,
    ) as claim:
        context.claim = claim
        if type(claim) is not getattr(key, PARAMETER_CLAIM) or claim.parameters is not context.p:
            raise ValueError("Actual same-p post-SEED transition required")
        with _account(context):
            context.stage = "phase_constructor"
            _make(
                context,
                "SimPhase",
                kind=context.kind,
                p=context.p,
                cells=context.cells,
                callbacks=context.callback,
            )
            context.stage_caches.append((context.stage, _snapshot(context)))
            context.stage = "init_core"
            context.phase.sim.init_core(context.phase)
            context.stage_caches.append((context.stage, _snapshot(context)))
            _seal(context)
    context.stage = "closed_parameter_validation"
    _closed(context)


def prepare(request, *, enabled=False):
    global _LAST_FAILED
    key = _ready()
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise InitRejected("Actual retained-world INIT construction remains held", stage="release")
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant INIT preparation")
        if type(request) is not Request or request not in _REQUESTS:
            raise InitRejected("Actual retained endpoint request required", stage="request")
        if request in _CONSUMED or request.seed_owner in _RETIRED:
            raise InitRejected("Retained SEED endpoint epoch consumed", stage="consumed")
        refs = _REQUESTS[request]
        parent = previous._authority(request.seed_owner)
        if (
            parent is not refs[0]
            or parent.trial is not refs[1]
            or previous._snapshot(parent).identity != refs[2].identity
        ):
            raise InitRejected("Original retained endpoint changed", stage="parent")
        graph = previous._graph(parent)
        core.previous._same(graph[0], refs[3][0])
        if graph[1] != refs[3][1]:
            raise InitRejected("Original retained endpoint aliases changed", stage="parent")
        context = _raw_context(request, refs, key)
        context.driver_frame = sys._getframe()
        _CONSUMED[request] = _RETIRED[request.seed_owner] = context
        _ACTIVE.append(context)
        try:
            context.atoms = parent.api._independent_atoms
            context.checker = (context.atoms, context.atoms.__code__, context.atoms.__globals__)
            context.metadata = tuple(
                (name, fn, context.atoms(fn))
                for name, fn in globals().items()
                if type(fn) is FunctionType and fn.__globals__ is globals()
            )
            context.plan = source_plan()
            context.parent_claim, context.parent_check = (
                getattr(previous, PARENT_CLAIM),
                getattr(previous, PARENT_CHECK),
            )
            context.parent_claim(request.seed_owner, expected=refs[1], transition=context)
            _acquire(context)
            _namespace(context)
            context.bindings = _binding(context)
            context.before, context.stream_before = _snapshot(context), _rng(context)
            # The actual one-shot transition begins before the first phase
            # allocation and stays active through fallible source sealing.
            _coordinate(context)
            _check(context, closed=True)
            _check_post_claim_seal(context)
            trial = Trial(
                request.identity,
                request.parent_identity,
                context.before,
                context.after,
                tuple(context.stage_caches),
                tuple(context.work),
                tuple(context.events),
                context.stream_before,
                context.stream_after,
                context.parameter_record,
                True,
                "",
            )
            context.trial = replace(trial, identity=_digest(trial_record(trial)))
            context.active = False
            owner = object.__new__(InitOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            primary = (
                context.entry_error
                if context.entry_error is not None
                else context.primary
                if context.primary is not None
                else error
            )
            context.failure_error = primary
            context.invalid = True
            _LAST_FAILED = context
            try:
                _retain(context, primary)
            except BaseException as secondary:
                context.retention_entry_error = (secondary, primary, context)
            raise primary  # noqa: B904 - retain the exact original exception/cause.
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True


def trial_record(value):
    return dict(
        request=value.request_identity,
        parent=value.parent_identity,
        before=value.before.identity,
        after=value.after.identity,
        stages=tuple((name, cache.identity) for name, cache in value.stage_caches),
        work=value.work,
        events=tuple((name, id(raw)) for name, raw in value.events),
        before_MT=value.stream_before.identity,
        after_MT=value.stream_after.identity,
        parameter_record=id(value.parameter_record),
        source_completed=value.source_completed,
    )


class InitOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the actual retained-world INIT constructor")

    def __reduce_ex__(self, protocol):
        raise TypeError("No pickle/checkpoint admission")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    global _LAST_FAILED
    if type(owner) is not InitOwner or owner not in _ISSUED:
        raise InitRejected("Actually issued INIT constructor/core owner required", stage="owner")
    context = _ISSUED[owner]
    if owner in _FORWARDED or hasattr(context, "dynamics_transition"):
        raise InitRejected(
            "INIT core epoch consumed by its dynamics prelude",
            stage="forwarded",
            trial=context.trial,
            partial=context,
        )
    if context.active or context.invalid or context.validating:
        raise InitRejected("INIT owner epoch unavailable", stage="owner")
    context.validating = True
    try:
        _check(context, closed=True)
        graph = _graph(context)
        core.previous._same(graph[0], context.graph[0])
        if (
            graph[1] != context.graph[1]
            or context.trial.identity != _digest(trial_record(context.trial))
            or context.trial.after.identity != _snapshot(context).identity
        ):
            raise ValueError("Completed INIT source/cache/reference epoch changed")
    except BaseException as error:
        context.failure_error = error
        context.invalid = True
        _LAST_FAILED = context
        try:
            _retain(context, error)
        except BaseException as secondary:
            context.retention_entry_error = (secondary, error, context)
        raise
    finally:
        context.validating = False
    return context


def _dynamics_binding(payload):
    """Existing exact-byte binder; only the two validated parent literals vary."""
    api = previous._ready()
    scope = dict(
        vars(api),
        HELPER_BACK_REFERENCE_SLOTS=DYNAMICS_BACK_REFERENCE_SLOTS,
        HELPER_BINDING_KIND=DYNAMICS_BINDING_KIND,
    )
    return FunctionType(api._helper_binding.__code__, scope)(payload)


def _dynamics_api():
    if not all(
        _pin(value)
        for value in (
            DYNAMICS_INTERFACE_SHA256,
            DYNAMICS_REVIEW_SHA256,
            DYNAMICS_PARENT_REVIEW_SHA256,
        )
    ):
        raise InitRejected(
            "Reviewed actual dynamics handoff remains unbound", stage="dynamics_held"
        )
    path = Path(__file__).parents[3] / ("src/" + DYNAMICS_MODULE.replace(".", "/") + ".py")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Original actual dynamics consumer source required")
    raw = path.read_bytes()
    identity, backrefs = _dynamics_binding(raw)
    if identity != DYNAMICS_INTERFACE_SHA256 or backrefs != (
        ("PARENT_SOURCE_SHA256", hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        ("PARENT_REVIEW_SHA256", DYNAMICS_PARENT_REVIEW_SHA256),
    ):
        raise ValueError("Exact dynamics consumer bytes or full parent back-reference changed")
    module = importlib.import_module(DYNAMICS_MODULE)
    if (
        sys.modules.get(DYNAMICS_MODULE) is not module
        or Path(module.__file__).resolve() != path
        or module.previous is not sys.modules[__name__]
        or path.read_bytes() != raw
        or any(getattr(module, name) != value for name, value in backrefs)
        or module.METHODS != ("init_dynamics", *DYNAMICS_HELPERS)
        or module.SIM_STORES != DYNAMICS_STORES
    ):
        raise ValueError("Actual original dynamics namespace/method/store contract changed")
    api = previous._ready()
    api._source_interface(module, raw, path, ("prepare", "_ready", "_wrapper_guard", "_dispatch"))
    module._ready()
    return module


def _dynamics_route(parent):
    module = _dynamics_api()
    child, owner = getattr(parent, "dynamics_transition", None), getattr(parent, "owner", None)
    if (
        child is None
        or owner is None
        or _ISSUED.get(owner) is not parent
        or _FORWARDED.get(owner) is not child
        or parent.active
        or parent.invalid
        or child.invalid
        or child.thread != get_ident()
        or parent.thread != child.thread
        or type(child.request) is not module.Request
        or child.request.init_owner is not owner
        or module._REQUESTS.get(child.request) is not child.refs
        or module._CONSUMED.get(child.request) is not child
        or module._RETIRED.get(owner) is not child
        or child.parent is not parent
        or child.refs[0] is not parent
        or child.refs[1] is not parent.trial
        or child.parent_trial is not parent.trial
        or child.parent_record is not parent.parameter_record
        or child.phase is not parent.phase
        or child.p is not parent.p
        or child.cells is not parent.cells
        or child.sim is not parent.phase.sim
        or child.callback is not parent.callback
        or child.entries is not parent.dynamics_entries
        or tuple(child.entries) != ("dispatch", "wrapper_guard")
        or child.entries["dispatch"] is not module._dispatch
        or child.entries["wrapper_guard"] is not module._wrapper_guard
    ):
        raise ValueError(
            "Original INIT/dynamics issuance, retirement or same-phase ancestry changed"
        )
    lease = _DYNAMICS_LEASES.get(owner)
    if lease is None:
        if sys._getframe(1).f_code is not _claim_for_init_dynamics_prelude.__code__:
            raise ValueError("Dynamics authority unavailable before its original lease seals")
    elif (
        getattr(parent, "dynamics_lease", None) is not lease
        or parent.dynamics_entries is not lease.entries
        or parent.dynamics_frames is not lease.frames
        or parent.dynamics_attempts is not lease.attempts
        or lease.transition is not child
    ):
        raise ValueError("Original dynamics lease/frame/entry identity changed")
    return child, module


def _dynamics_projection(context):
    lease = context.dynamics_lease
    for (_, actual), holder, names, target in zip(
        lease.objects, lease.holders, lease.names, lease.fields, strict=True
    ):
        if vars(actual) is not holder:
            raise ValueError("Original INIT object holder changed during dynamics")
        current = tuple(holder)
        if actual is context.phase.sim:
            if tuple(name for name in current if name not in DYNAMICS_STORES) != tuple(
                name for name in names if name not in DYNAMICS_STORES
            ):
                raise ValueError("Unowned original Simulator field roster changed")
        elif current != names:
            raise ValueError("Original non-Simulator field roster changed during dynamics")
        target.clear()
        target.update(
            (name, holder[name])
            for name in names
            if actual is not context.phase.sim or name not in DYNAMICS_STORES
        )
    return lease.view


def _dynamics_values(context):
    view = _dynamics_projection(context)
    return core.previous._scope(context.parent.world).snapshot(
        core._LITERAL._project(_projector(context), view.fields)
    )


def _dynamics_graph(context):
    view = _dynamics_projection(context)
    return core.previous._scope(context.parent.world).graph(view, view, context.dynamics_lease.tape)


def _capture_dynamics_lease(context):
    if (
        sys._getframe(1).f_code is not _claim_for_init_dynamics_prelude.__code__
        or sys._getframe(1).f_locals.get("parent") is not context
        or context.owner in _DYNAMICS_LEASES
        or hasattr(context, "dynamics_lease")
    ):
        raise ValueError("Only the original once-retired INIT claim may seal its immutable lease")
    objects = list(context.objects)
    for role, value in (("retained_cells", context.cells), ("parameters", context.p)):
        if not any(actual is value for _, actual in objects):
            objects.append((role, value))
    fields = [{} for _ in objects]
    context.dynamics_lease = SimpleNamespace(
        objects=tuple(objects),
        holders=tuple(vars(actual) for _, actual in objects),
        names=tuple(tuple(vars(actual)) for _, actual in objects),
        fields=fields,
        view=SimpleNamespace(objects=tuple(objects), fields=fields, weak_proxies=context.proxies),
        tape=SimpleNamespace(rng=context.parent.rng, events=(), draws=(), locals={}),
        edges=(_seed_edge_records(sys.modules[__name__], context),),
        entries=context.dynamics_entries,
        frames=context.dynamics_frames,
        attempts=context.dynamics_attempts,
        transition=context.dynamics_transition,
    )
    _DYNAMICS_LEASES[context.owner] = context.dynamics_lease
    context.dynamics_lease.values = _dynamics_values(context)
    context.dynamics_lease.graph = _dynamics_graph(context)


def _claim_for_init_dynamics_prelude(owner, *, expected, transition, entries):
    """Retire the actual core epoch before fallible prelude authentication."""
    module = _dynamics_api()
    frame = sys._getframe(1)
    with _LOCK:
        parent = _ISSUED.get(owner) if type(owner) is InitOwner else None
        if (
            parent is None
            or parent.trial is not expected
            or frame.f_code is not module.prepare.__code__
            or frame.f_globals is not vars(module)
            or frame.f_locals.get("context") is not transition
            or not module._ACTIVE
            or module._ACTIVE[-1] is not transition
        ):
            raise InitRejected("Actual active dynamics issuer required", stage="dynamics_entry")
        if owner in _FORWARDED or hasattr(parent, "dynamics_transition"):
            raise InitRejected("INIT epoch already attempted", stage="dynamics_consumed")
        if (
            parent.active
            or parent.invalid
            or parent.validating
            or parent.owner is not owner
            or transition.parent is not parent
            or transition.parent_trial is not expected
            or transition.parent_record is not parent.parameter_record
            or transition.entries is not entries
            or tuple(entries) != ("dispatch", "wrapper_guard")
            or entries["dispatch"] is not module._dispatch
            or entries["wrapper_guard"] is not module._wrapper_guard
            or transition.thread != parent.thread
            or transition.thread != get_ident()
        ):
            parent.invalid = transition.invalid = True
            raise ValueError("Original closed INIT/dynamics claim association changed")
        parent.dynamics_transition = transition
        try:
            _FORWARDED[owner] = transition
            parent.dynamics_entries = entries
            parent.dynamics_frames = {}
            parent.dynamics_attempts = []
            if _dynamics_route(parent)[0] is not transition:
                raise ValueError("Actual dynamics retirement route changed")
            _check(parent, closed=True)
            _completion(parent)
            graph = _graph(parent)
            core.previous._same(graph[0], parent.graph[0])
            if (
                graph[1] != parent.graph[1]
                or parent.trial.source_completed is not True
                or parent.trial.identity != _digest(trial_record(parent.trial))
                or _snapshot(parent).identity != parent.trial.after.identity
            ):
                raise ValueError("Actual complete INIT source epoch changed before dynamics")
            _capture_dynamics_lease(parent)
        except BaseException as error:
            parent.dynamics_error = error
            parent.invalid = transition.invalid = True
            raise
        return parent


def _check_init_dynamics_prelude_authority(transition):
    """Live source/registry authority plus immutable projection, no stale cache check."""
    parent = transition.parent
    if _dynamics_route(parent)[0] is not transition:
        raise ValueError("Different original dynamics transition")
    _check(parent, closed=True)
    _completion(parent)
    lease = parent.dynamics_lease
    core._check_profile_ancestor_edges(lease)
    if _dynamics_values(parent).identity != lease.values.identity:
        raise ValueError("Dynamics changed original non-owned INIT state")
    graph = _dynamics_graph(parent)
    core.previous._same(graph[0], lease.graph[0])
    if graph[1] != lease.graph[1]:
        raise ValueError("Dynamics changed an original immutable reference edge")
    return parent


def _dynamics_wrapper_guard(parent, frame):
    child, module = _dynamics_route(parent)
    raw = (frame, dict(frame.f_locals))
    parent.last_dynamics_attempt = raw
    if len(parent.dynamics_attempts) >= MAX_WORK:
        _reject(parent, "Bounded original helper wrapper attempt ledger exhausted")
    parent.dynamics_attempts.append(raw)
    name = frame.f_locals.get("method")
    function = vars(parent.runtime_types["Simulator"]).get(name)
    if (
        name not in DYNAMICS_HELPERS
        or type(function) is not FunctionType
        or frame.f_code is not function.__code__
        or frame.f_globals is not function.__globals__
        or frame.f_locals.get("actual") is not parent.phase.sim
        or frame.f_locals.get("name") != "Simulator"
        or frame.f_locals.get("context") is not parent
        or frame.f_locals.get("delegate") is not getattr(parent.factories["Simulator"], name)
        or _OBJECTS.get(parent.phase.sim) is not parent
        or not child.active
        or not module._ACTIVE
        or module._ACTIVE[-1] is not child
        or frame.f_back is not child.body_frame
    ):
        _reject(parent, "Only the issued original helper wrapper in the actual prefix may enter")
    for name, cell in zip(function.__code__.co_freevars, function.__closure__ or (), strict=True):
        if frame.f_locals.get(name) is not cell.cell_contents:
            _reject(parent, "Original helper wrapper closure/frame association changed")
    if id(frame) in parent.dynamics_frames:
        _reject(parent, "Original helper wrapper frame already claimed")
    args, kwargs = frame.f_locals.get("args"), frame.f_locals.get("kwargs")
    if type(args) is not tuple or type(kwargs) is not dict:
        _reject(parent, "Actual original wrapper argument containers required")
    claim = SimpleNamespace(
        frame=frame,
        function=function,
        dispatched=False,
        invocation=None,
        args=args,
        kwargs=kwargs,
        arg_refs=tuple(args),
        keyword_refs=tuple(kwargs.items()),
    )
    parent.dynamics_frames[id(frame)] = claim
    module._wrapper_guard(child, parent, frame)
    if (
        parent.dynamics_frames.get(id(frame)) is not claim
        or claim.frame is not frame
        or claim.dispatched
        or frame.f_locals.get("args") is not claim.args
        or frame.f_locals.get("kwargs") is not claim.kwargs
        or tuple(claim.kwargs.items()) != claim.keyword_refs
    ):
        _reject(parent, "Observer changed or consumed the claimed helper wrapper")


def _dynamics_dispatch_guard(parent, child, label, delegate, args, kwargs, frame):
    wrapper = frame.f_back
    claim = parent.dynamics_frames.get(id(wrapper))
    method = label.removeprefix("Simulator.")
    if (
        label != "Simulator." + method
        or method not in DYNAMICS_HELPERS
        or claim is None
        or claim.frame is not wrapper
        or claim.dispatched
        or claim.function is not vars(parent.runtime_types["Simulator"]).get(method)
        or wrapper.f_back is not child.body_frame
        or not args
        or args[0] is not parent.phase.sim
        or delegate is not getattr(parent.factories["Simulator"], method)
        or kwargs
        or len(args) != len(claim.arg_refs) + 1
        or any(a is not b for a, b in zip(args[1:], claim.arg_refs, strict=True))
        or wrapper.f_locals.get("args") is not claim.args
        or wrapper.f_locals.get("kwargs") is not claim.kwargs
        or tuple(claim.kwargs.items()) != claim.keyword_refs
        or frame.f_code is not _invoke.__code__
        or frame.f_globals is not globals()
    ):
        _reject(parent, "Actual once-claimed Simulator helper dispatch required")
    expected = (parent.cells, parent.p) if method == "initDenv" else None
    if (
        expected is not None
        and (len(args) != 3 or any(a is not b for a, b in zip(args[1:], expected, strict=True)))
        or method == "get_ion"
        and (len(args) != 2 or type(args[1]) is not str)
    ):
        _reject(parent, "Original helper arguments changed before dispatch")
    claim.dispatched, claim.invocation = True, frame
