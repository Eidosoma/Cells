"""Held fresh INIT construction on an actual retained live SEED world.

No pickle/cache reader or SEED relabelling supplies authority. The public
optional Cells argument is the original retained object; the Simulator,
caches, handler and phase are newly constructed by the selected source.
"""

import ast
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
from functools import lru_cache
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
from cells.processes import betse_native_world_phase_construction as metadata_api

LAW_ID = "betse_actual_retained_seed_cells_fresh_INIT_constructor_and_core@1"
RELEASE = "CELLS_NATIVE_INIT_RETAINED_WORLD_RELEASED"
KEY_MODULE = "cells.processes.betse_native_parameter_seed_init_transition"
KEY_SOURCE_SHA256 = '0808a04ce9ddba81d86816d1167a7b516c55f3699f8593250c7dddef649e79c2'
KEY_REVIEW_SHA256 = '6618312fe2cbf5aac3b5f05bf80f8a7676dab56a3a5585bd4f1cfa948643fc01'
PARENT_SOURCE_SHA256 = 'ce9fa8187c944bee728a0a5c240519e439abde15a4f131aabb71c2287aecc482'
PARENT_REVIEW_SHA256 = '6de2b20d888948f3eab03a71729c1bc49113d5ba650c599a5fe13453017884cf'
SOURCE_SHA256 = 'e0f5b1d8e8a412d51dc30c8f1788c9ff9638afa85ff4eb3a934418f425fec5b5'
DYNAMICS_MODULE = "cells.processes.betse_native_init_dynamics_prelude"
DYNAMICS_INTERFACE_SHA256 = '7e818ffdb396672f53c610f315b6ca3ce7acddedd1e8fbfa67a1ed818ca39054'
DYNAMICS_REVIEW_SHA256 = '1550f3033aa2e56573135bff934a93795a3169e129b6c4a17e8a787447bfa710'
DYNAMICS_PARENT_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
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
_COMPLETION_INITIAL_LEASES = WeakKeyDictionary()
_STORAGE_INITIAL_LEASES = WeakKeyDictionary()
_ELECTRICAL_INITIAL_LEASES = WeakKeyDictionary()
_FIRST_STEP_INITIAL_LEASES = WeakKeyDictionary()
_SHORT_INIT_INITIAL_LEASES = WeakKeyDictionary()
_TERMINAL_INIT_INITIAL_LEASES = WeakKeyDictionary()
_MOLECULE_INITIAL_LEASES = WeakKeyDictionary()
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
        completion_handoff=dict(
            actual_provider_route="Prelude._completion_route(actual_prelude_context)",
            ancestor_claim=(
                "_claim_completion_ancestor(actual_INIT, actual_Prelude, actual_completion)"
            ),
            claim_before_any_completion_body=True,
            permitted_changes="Exact source-derived handler stores and Key Simulator stores",
            cell_i=(
                "Same object/base/layout; bits and global MT audited by actual successor witnesses"
            ),
            supplied_phase_parameter_cache_RNG_or_rearmed_epoch_authority=False,
            native_source_or_time_loop_release=False,
        ),
        storage_handoff=dict(
            ancestor_claim=(
                "_claim_storage_ancestor(actual_INIT, actual_completion, actual_storage)"
            ),
            wrapper="Original same-instance Simulator.clear_storage only",
            permitted_changes="Original 52 ordered stores/51 Simulator fields",
            previous_trials_leases_and_raw_objects_preserved=True,
            native_source_or_time_loop_release=False,
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
        completion = getattr(context.dynamics_transition, "completion_transition", None)
        storage = getattr(completion, "storage_transition", None)
        electrical = getattr(storage, "electrical_transition", None)
        first_step, route = _advance_child(context, electrical)
        if first_step is not None:
            first = getattr(first_step, "first_failure", None)
            if first is not None and first[0] == "source":
                raise first[1]
            if first_step.entry_error is not None:
                raise first_step.entry_error
            if getattr(first_step, "failure_error", None) is not None:
                raise first_step.failure_error
            current, api, *_ = route(context)
            current.entries["wrapper_guard"](current, context, sys._getframe(1))
            return
        for error in (
            context.entry_error,
            getattr(context.dynamics_transition, "entry_error", None),
            getattr(completion, "entry_error", None),
            getattr(storage, "entry_error", None),
            getattr(electrical, "entry_error", None),
            getattr(storage, "electrical_error", None),
            getattr(completion, "storage_error", None),
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
        _COMPLETION_INITIAL_LEASES,
        _STORAGE_INITIAL_LEASES,
        _ELECTRICAL_INITIAL_LEASES,
        _FIRST_STEP_INITIAL_LEASES,
        _SHORT_INIT_INITIAL_LEASES,
        _TERMINAL_INIT_INITIAL_LEASES,
        _MOLECULE_INITIAL_LEASES,
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
        metadata_api,
        _METADATA_FILE,
        _METADATA_TOOLS,
        _METADATA_CACHES,
        _source_templates,
        _dynamics_template,
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
    for _, _, original, state in _METADATA_TOOLS:
        result.append(original)
        if state is not None:
            result.extend(_metadata_function_state(original))
    for _, wrapper, body, _ in _METADATA_CACHES:
        result.extend((wrapper, wrapper.__wrapped__, *_metadata_function_state(body)))
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
    completion = _completion_initial_lease(context)
    values = _seed_values(context) if completion is None else _completion_seed_values(context)
    expected = lease.values if completion is None else completion.seed_values
    if values.identity != expected.identity or (
        completion is None and _rng(context).identity != lease.stream.identity
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
    if (
        _completion_initial_lease(context) is None
        and _rng(context).identity != context.stream_before.identity
    ):
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
        completion = getattr(context.dynamics_transition, "completion_transition", None)
        storage = getattr(completion, "storage_transition", None)
        electrical = getattr(storage, "electrical_transition", None)
        first_step, route = _advance_child(context, electrical)
        if first_step is not None:
            first = getattr(first_step, "first_failure", None)
            if first is not None and first[0] == "source":
                raise first[1]
            if first_step.entry_error is not None:
                raise first_step.entry_error
            if getattr(first_step, "failure_error", None) is not None:
                raise first_step.failure_error
            current, api, *_ = route(context)
            return current.entries["dispatch"](
                current, context, label, delegate, args[0], args[1:], kwargs, sys._getframe()
            )
        for error in (
            context.entry_error,
            getattr(context.dynamics_transition, "entry_error", None),
            getattr(completion, "entry_error", None),
            getattr(storage, "entry_error", None),
            getattr(electrical, "entry_error", None),
            getattr(storage, "electrical_error", None),
            getattr(completion, "storage_error", None),
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
            electrical = _electrical_runtime(context)
            if electrical is not None:
                current = electrical[0]
                return current.entries["dispatch"](
                    current, context, label, delegate, args[0], args[1:], kwargs, sys._getframe()
                )
            storage = _storage_runtime(context)
            if storage is not None:
                current = storage[0]
                return current.entries["dispatch"](
                    current, context, label, delegate, args[0], args[1:], kwargs, sys._getframe()
                )
            forwarded = _completion_runtime(context)
            if forwarded is not None:
                current, _, _, _ = forwarded
                return current.entries["dispatch"](
                    current, context, label, delegate, args[0], args[1:], kwargs, sys._getframe()
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


def _metadata_function_state(function):
    namespace, cached = function.__globals__, function.__builtins__
    declared = namespace.get("__builtins__")
    if (vars(declared) if type(declared) is ModuleType else declared) is not cached:
        raise ValueError("Original metadata cached builtins required")
    values = [
        function,
        function.__code__,
        namespace,
        cached,
        declared,
        function.__defaults__,
        function.__kwdefaults__,
        function.__closure__,
    ]
    values.extend(function.__defaults__ or ())
    for key, value in (function.__kwdefaults__ or {}).items():
        values.extend((key, value))
    for cell in function.__closure__ or ():
        values.extend((cell, cell.cell_contents))
    for name in function.__code__.co_names:
        if name in namespace:
            value = namespace[name]
            values.extend((name, value))
            if type(value) is FunctionType:
                values.extend((value.__code__, value.__defaults__, value.__kwdefaults__))
        elif name in cached:
            values.extend((name, cached[name]))
    return tuple(values)


def _same_metadata(current, original):
    if len(current) != len(original) or any(
        a is not b for a, b in zip(current, original, strict=True)
    ):
        raise ValueError("Original source metadata dependency changed")


def _immutable_metadata_default(value):
    if type(value) in (type(None), bool, int, float, complex, str, bytes):
        return value
    if type(value) is tuple:
        for child in value:
            _immutable_metadata_default(child)
        return value
    raise ValueError("Only immutable defaults in this source interface are supported")


@lru_cache(maxsize=16, typed=True)
def _source_templates(payload, filename, names):
    """Immutable syntax/code only, keyed by every exact source byte and path."""
    code = builtins.compile(payload, filename, "exec", dont_inherit=True, optimize=0)
    definitions = {
        node.name: node for node in ast.parse(payload).body if isinstance(node, ast.FunctionDef)
    }
    codes = {value.co_name: value for value in code.co_consts if type(value) is CodeType}
    rows = []
    for name in names:
        node = definitions.get(name)
        if node is None or node.decorator_list or name not in codes:
            raise ValueError("Actual undecorated source definition required: " + name)
        defaults = tuple(
            _immutable_metadata_default(ast.literal_eval(item)) for item in node.args.defaults
        )
        keywords = tuple(
            (arg.arg, _immutable_metadata_default(ast.literal_eval(value)))
            for arg, value in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
            if value is not None
        )
        rows.append((name, codes[name], defaults, keywords))
    return tuple(rows)


def _live_source_interface(module, payload, path, names):
    if (
        type(payload) is not bytes
        or len(payload) > 2**21
        or type(names) is not tuple
        or len(names) > 64
        or any(type(name) is not str for name in names)
    ):
        raise ValueError("Bounded exact source bytes and immutable selectors required")
    filename = str(path)
    checked = []
    for name, code, defaults, keywords in _source_templates(payload, filename, names):
        function = vars(module).get(name)
        if (
            type(function) is not FunctionType
            or function.__globals__ is not vars(module)
            or function.__code__ != code
            or function.__code__.co_filename != filename
            or function.__closure__ is not None
            or function.__name__ != name
            or function.__qualname__ != name
        ):
            raise ValueError("Actual exact source function/code required: " + name)
        actual, declared = function.__defaults__ or (), function.__kwdefaults__ or {}
        expected = dict(keywords)
        if (
            actual != defaults
            or declared != expected
            or any(type(a) is not type(b) for a, b in zip(actual, defaults, strict=True))
            or any(type(declared[key]) is not type(value) for key, value in keywords)
        ):
            raise ValueError("Original source interface defaults changed: " + name)
        checked.append(function)
    return tuple(checked)


def _check_metadata_tools(api):
    if (
        api is not metadata_api
        or sys.modules.get("cells.processes.betse_native_world_phase_construction") is not api
    ):
        raise ValueError("Actual original source metadata namespace required")
    for owner, name, original, state in _METADATA_TOOLS:
        if vars(owner).get(name) is not original:
            raise ValueError("Original source metadata alias changed: " + name)
        if state is not None:
            _same_metadata(_metadata_function_state(original), state)
    for name, wrapper, body, state in _METADATA_CACHES:
        if globals().get(name) is not wrapper or wrapper.__wrapped__ is not body:
            raise ValueError("Original immutable source template cache changed")
        _same_metadata(_metadata_function_state(body), state)


def _check_metadata_api(api):
    _check_metadata_tools(api)
    filename = vars(api).get("__file__")
    if type(filename) is not str:
        raise ValueError("Original source metadata file association changed")
    original_path = Path(filename)
    if original_path.is_symlink() or original_path.resolve() != _METADATA_FILE:
        raise ValueError("Original source metadata file association changed")
    # Fresh bytes and live functions are checked on EVERY use. Only immutable
    # parsed syntax/compiled CodeTypes are reused, never a validation result.
    _live_source_interface(
        api,
        original_path.read_bytes(),
        original_path,
        ("_helper_binding", "_source_interface", "_pin"),
    )


def _metadata_source_interface(api, module, payload, path, names):
    _check_metadata_api(api)
    return _live_source_interface(module, payload, path, names)


@lru_cache(maxsize=16, typed=True)
def _dynamics_template(payload, kind, slots):
    scope = dict(vars(metadata_api), HELPER_BACK_REFERENCE_SLOTS=slots, HELPER_BINDING_KIND=kind)
    return FunctionType(metadata_api._helper_binding.__code__, scope)(payload)


_METADATA_FILE = Path(metadata_api.__file__).resolve()
_METADATA_TOOLS = tuple(
    (owner, name, value, _metadata_function_state(value) if type(value) is FunctionType else None)
    for owner, names in (
        (
            metadata_api,
            (
                "_helper_binding",
                "_source_interface",
                "_pin",
                "ast",
                "builtins",
                "hashlib",
                "json",
                "CodeType",
                "FunctionType",
            ),
        ),
        (
            ast,
            (
                "parse",
                "walk",
                "iter_fields",
                "iter_child_nodes",
                "literal_eval",
                "Name",
                "Store",
                "Assign",
                "Constant",
                "FunctionDef",
            ),
        ),
        (builtins, ("compile",)),
        (hashlib, ("sha256",)),
        (json, ("dumps",)),
    )
    for name in names
    for value in (vars(owner)[name],)
)
_METADATA_CACHES = tuple(
    (name, wrapper, wrapper.__wrapped__, _metadata_function_state(wrapper.__wrapped__))
    for name, wrapper in (
        ("_source_templates", _source_templates),
        ("_dynamics_template", _dynamics_template),
    )
)


def _dynamics_binding(payload):
    """Existing exact-byte binder; only the two validated parent literals vary."""
    api = previous._ready()
    _check_metadata_api(api)
    if (
        type(payload) is not bytes
        or len(payload) > 2**21
        or type(DYNAMICS_BINDING_KIND) is not str
        or type(DYNAMICS_BACK_REFERENCE_SLOTS) is not tuple
        or any(type(name) is not str for name in DYNAMICS_BACK_REFERENCE_SLOTS)
    ):
        raise ValueError("Bounded exact source template and immutable backrefs required")
    return _dynamics_template(payload, DYNAMICS_BINDING_KIND, DYNAMICS_BACK_REFERENCE_SLOTS)


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
    names = ("prepare", "_ready", "_wrapper_guard", "_dispatch")
    functions = _metadata_source_interface(api, module, raw, path, names)
    if any(vars(module).get(name) is not fn for name, fn in zip(names, functions, strict=True)):
        raise ValueError("Original dynamics source alias changed before readiness")
    functions[1]()
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


def _completion_runtime(parent):
    """Authenticate Key's real forwarded claim, preserving the original route."""
    prelude, module = _dynamics_route(parent)
    marker = getattr(prelude, "completion_transition", None)
    if marker is None:
        return None
    route = vars(module).get("_completion_route")
    if type(route) is not FunctionType or route.__globals__ is not vars(module):
        raise ValueError("Actual reviewed prelude completion routing is unavailable")
    path = Path(module.__file__)
    raw = path.read_bytes()
    if _dynamics_binding(raw)[0] != DYNAMICS_INTERFACE_SHA256:
        raise ValueError("Original completion route producer changed before entry")
    proved = _metadata_source_interface(
        previous._ready(), module, raw, path, ("_completion_route",)
    )
    if proved != (route,) or vars(module).get("_completion_route") is not route:
        raise ValueError("Original completion route changed before invocation")
    transition, api = route(prelude)
    if (
        transition is not marker
        or transition.parent is not prelude
        or transition.init_parent is not parent
        or type(transition.claim) is not api.CompletionClaim
        or api._CLAIMS.get(transition.claim) is not transition
        or transition.phase is not parent.phase
        or transition.p is not parent.p
        or transition.cells is not parent.cells
        or transition.sim is not parent.phase.sim
        or transition.handler is not parent.phase.dyna
    ):
        raise ValueError("Actual same-INIT CompletionClaim ancestry changed")
    return transition, api, prelude, module


def _completion_initial_lease(parent):
    owner = getattr(parent, "owner", None)
    if owner is None:
        return None
    lease = _COMPLETION_INITIAL_LEASES.get(owner)
    if lease is None:
        return None
    if lease.status == "claiming":
        frame = sys._getframe(1)
        while frame is not None and frame is not lease.claim_frame:
            frame = frame.f_back
        if frame is None:
            raise ValueError("Incomplete completion reservation cannot authenticate a caller")
        return None
    actual = _completion_runtime(parent)
    if (
        lease.status != "ready"
        or actual is None
        or actual[0] is not lease.transition
        or actual[2] is not lease.prelude
        or lease.parent is not parent
        or getattr(parent, "completion_initial_lease", None) is not lease
        or parent.dynamics_lease is not lease.original_lease
        or parent.seed_lease is not lease.seed_lease
        or parent.trial is not lease.trial
        or parent.parameter_record is not lease.parameter_record
    ):
        raise ValueError("Original irreversible completion/INIT lease association changed")
    _completion_cell_layout(parent, lease)
    return lease


def _completion_cell_layout(parent, lease):
    array = parent.cells.cell_i
    shape = (
        array.dtype.str,
        tuple(array.shape),
        tuple(array.strides),
        array.ctypes.data,
        bool(array.flags.writeable),
        bool(array.flags.c_contiguous),
        bool(array.flags.f_contiguous),
    )
    if (
        array is not lease.cell_i
        or type(array) is not lease.cell_type
        or array.base is not lease.cell_base
        or shape != lease.cell_layout
    ):
        raise ValueError("Original cell_i identity/base/layout changed during source shuffle")


def _completion_projection(parent, lease):
    for (_, actual), holder, names, target in zip(
        lease.objects, lease.holders, lease.names, lease.fields, strict=True
    ):
        if vars(actual) is not holder:
            raise ValueError("Original INIT holder changed during completion")
        allowed = (
            lease.sim_fields
            if actual is parent.phase.sim
            else (lease.handler_fields if actual is parent.phase.dyna else frozenset())
        )
        if tuple(name for name in holder if name not in allowed) != tuple(
            name for name in names if name not in allowed
        ):
            raise ValueError("Completion changed an unowned original field roster")
        target.clear()
        target.update((name, holder[name]) for name in names if name not in allowed)
    return lease.view


def _completion_initial_values(parent, lease):
    view = _completion_projection(parent, lease)
    # Observation projection only. The actual original array is retained and
    # layout-checked; its bits/MT are owned by the real successor's source-call
    # witnesses and full final snapshot, never an old pre-shuffle validator.
    fields = tuple(
        {
            name: value
            for name, value in target.items()
            if actual is not parent.cells or name != "cell_i"
        }
        for (_, actual), target in zip(lease.objects, view.fields, strict=True)
    )
    projector = _projector(parent)
    projector.objects.extend(("actual_cell_i_alias", value) for value in lease.cell_aliases)
    return core.previous._scope(parent.parent.world).snapshot(
        core._LITERAL._project(projector, fields)
    )


def _completion_seed_values(parent):
    view = _seed_projection(parent)
    fields = tuple(
        {
            name: value
            for name, value in target.items()
            if actual is not parent.cells or name != "cell_i"
        }
        for (_, actual), target in zip(parent.seed_lease.objects, view.fields, strict=True)
    )
    lease = _COMPLETION_INITIAL_LEASES[parent.owner]
    projector = SimpleNamespace(
        objects=[
            *parent.seed_lease.projector.objects,
            *(("actual_cell_i_alias", value) for value in lease.cell_aliases),
        ]
    )
    return core.previous._scope(parent.parent.world).snapshot(
        core._LITERAL._project(projector, fields)
    )


def _completion_cell_aliases(parent):
    """Retain preexisting true array aliases, including old All-picker views.

    Only the actual cell_i or views whose actual .base chain reaches it are
    opaque to the historical bit comparison. Their objects/base/layout remain
    in the original full reference graph; unrelated equal arrays stay numeric.
    """
    original = parent.cells.cell_i
    array_type = type(original)
    seen, result = set(), []

    def visit(value, depth=0):
        if depth > 48 or len(seen) > 100000:
            raise ValueError("Bounded historical cell-index alias graph exhausted")
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, array_type):
            base, bases = value, set()
            while isinstance(base, array_type) and id(base) not in bases:
                if base is original:
                    result.append(value)
                    break
                bases.add(id(base))
                base = base.base
            if value.dtype.hasobject:
                for item in value.flat:
                    visit(item, depth + 1)
        elif type(value) is dict:
            for item in value.values():
                visit(item, depth + 1)
        elif type(value) in (tuple, list):
            for item in value:
                visit(item, depth + 1)

    visit(_seed_projection(parent).fields)
    visit(_dynamics_projection(parent).fields)
    if not any(value is original for value in result):
        result.append(original)
    return tuple(result)


def _claim_completion_ancestor(parent, prelude, transition):
    """Called by the genuine Key prelude claim before any completion body."""
    actual = _completion_runtime(parent)
    if actual is None or actual[0] is not transition or actual[2] is not prelude:
        raise ValueError("Actual provider-issued completion transition required")
    module = actual[3]
    frame = sys._getframe(1)
    if (
        frame.f_code is not module._claim_for_init_dynamics_completion.__code__
        or frame.f_globals is not vars(module)
        or frame.f_locals.get("context") is not prelude
        or frame.f_locals.get("transition") is not transition
        or transition.body_frame is not None
        or not transition.active
    ):
        raise ValueError("Actual original prelude transfer must precede every completion body")
    if parent.owner in _COMPLETION_INITIAL_LEASES:
        _reject_completion_reservation(parent, transition)
    lease = SimpleNamespace(
        parent=parent,
        prelude=prelude,
        transition=transition,
        claim_frame=sys._getframe(),
        status="claiming",
        original_lease=parent.dynamics_lease,
        seed_lease=parent.seed_lease,
        trial=parent.trial,
        parameter_record=parent.parameter_record,
        frames={},
        attempts=[],
    )
    _COMPLETION_INITIAL_LEASES[parent.owner] = lease
    parent.completion_initial_lease = lease
    try:
        # Authenticate the OLD epoch exactly once before excluding the newly
        # owned fields. A refused attempt is never lazily captured later.
        _check(parent, closed=True)
        _completion(parent)
        if _dynamics_values(parent).identity != parent.dynamics_lease.values.identity:
            raise ValueError("Original INIT state changed before completion retirement")
        graph = _dynamics_graph(parent)
        core.previous._same(graph[0], parent.dynamics_lease.graph[0])
        if graph[1] != parent.dynamics_lease.graph[1]:
            raise ValueError("Original INIT aliases changed before completion retirement")
        tissue = transition.tissue
        nodes = tissue._source_nodes()
        lease.handler_fields = frozenset(
            node.attr
            for method in nodes.values()
            for node in ast.walk(method)
            if isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Store)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        )
        lease.sim_fields = frozenset((*DYNAMICS_STORES, *actual[1].SIM_STORES))
        lease.objects = parent.dynamics_lease.objects
        lease.holders = tuple(vars(value) for _, value in lease.objects)
        lease.names = tuple(tuple(vars(value)) for _, value in lease.objects)
        lease.fields = [{} for _ in lease.objects]
        lease.view = SimpleNamespace(
            objects=lease.objects, fields=lease.fields, weak_proxies=parent.proxies
        )
        lease.tape = SimpleNamespace(rng=parent.parent.rng, events=(), draws=(), locals={})
        lease.cell_i, lease.cell_type = parent.cells.cell_i, type(parent.cells.cell_i)
        array = lease.cell_i
        lease.cell_base = array.base
        lease.cell_layout = (
            array.dtype.str,
            tuple(array.shape),
            tuple(array.strides),
            array.ctypes.data,
            bool(array.flags.writeable),
            bool(array.flags.c_contiguous),
            bool(array.flags.f_contiguous),
        )
        lease.cell_aliases = _completion_cell_aliases(parent)
        lease.values = _completion_initial_values(parent, lease)
        lease.seed_values = _completion_seed_values(parent)
        lease.graph = core.previous._scope(parent.parent.world).graph(
            lease.view, lease.view, lease.tape
        )
        lease.status = "ready"
        return parent
    except BaseException as error:
        primary = parent.entry_error if parent.entry_error is not None else error
        lease.status, lease.primary = "failed", primary
        if error is not primary:
            lease.secondary = (error, primary)
        parent.invalid = transition.invalid = True
        raise primary  # noqa: B904 -- preserve the original cause; secondary is retained above.


def _reject_completion_reservation(parent, transition):
    transition.invalid = True
    _reject(parent, "Original completion/INIT ancestry epoch was already attempted")


def _storage_runtime(parent):
    """Authenticate the real completion's original storage registry route."""
    actual = _completion_runtime(parent)
    if actual is None or getattr(actual[0], "storage_transition", None) is None:
        return None
    completion, provider, _, _ = actual
    route = vars(provider).get("_storage_route")
    if type(route) is not FunctionType or route.__globals__ is not vars(provider):
        raise ValueError("Actual original completion/storage route unavailable")
    path = Path(provider.__file__)
    raw = path.read_bytes()
    # The original prelude route has already authenticated the complete
    # producer bytes/backrefs. Also authenticate the reached callable before
    # invoking it; a retained module or file hash alone is not code authority.
    previous._ready()._source_interface(provider, raw, path, ("_storage_route",))
    transition, api = route(completion)
    if (
        transition is not completion.storage_transition
        or transition.parent is not completion
        or completion.init_parent is not parent
        or transition.phase is not parent.phase
        or transition.p is not parent.p
        or transition.cells is not parent.cells
        or transition.sim is not parent.phase.sim
        or transition.handler is not parent.phase.dyna
    ):
        raise ValueError("Actual same-INIT storage/phase ancestry changed")
    return transition, api, completion, provider


def _molecule_initial_lease(parent):
    """Custody of the original material epoch, never an executable owner."""
    lease = _MOLECULE_INITIAL_LEASES.get(parent.owner)
    if lease is None:
        return None
    if lease.status == "claiming":
        frame = sys._getframe(1)
        while frame is not None and frame is not lease.claim_frame:
            frame = frame.f_back
        if frame is None:
            raise ValueError("Incomplete material reservation cannot authenticate a caller")
        return None
    actual = _completion_runtime(parent)
    if (
        lease.status != "ready"
        or actual is None
        or actual[0] is not lease.completion
        or getattr(parent, "molecule_initial_lease", None) is not lease
        or _COMPLETION_INITIAL_LEASES.get(parent.owner) is not lease.original
        or parent.completion_initial_lease is not lease.original
        or lease.parent is not parent
        or lease.completion.molecule is not lease.module
        or lease.completion.molecule_session is not lease.session
        or lease.module._SESSIONS is not lease.sessions
        or lease.module._CLAIMED is not lease.claims
        or lease.sessions.get(lease.session) is not lease.participant
        or lease.claims.get(lease.completion.claim) is not lease.participant
        or lease.participant.completion is not lease.completion
        or lease.participant.session is not lease.session
        or lease.participant.ancestor_claim is not _claim_completion_molecule_ancestor
        or lease.participant.ancestor_check is not _check_completion_molecule_ancestor
        or lease.module.SIM_STORES is not lease.stores
    ):
        raise ValueError("Original molecular material/Completion registry links changed")
    for name, function, atoms in lease.functions:
        if vars(lease.module).get(name) is not function:
            raise ValueError("Original material participant callable replaced: " + name)
        core.previous._same(parent.atoms(function), atoms)
    return lease


def _claim_completion_molecule_ancestor(parent, completion, session):
    """Retire material fields only from the real, still-unrun molecular binder."""
    actual = _completion_runtime(parent)
    module, frame = getattr(completion, "molecule", None), sys._getframe(1)
    function = vars(module).get("bind_completion") if type(module) is ModuleType else None
    participant = (
        module._SESSIONS.get(session)
        if type(function) is FunctionType and type(session) is module.MoleculeSession
        else None
    )
    if (
        actual is None
        or actual[0] is not completion
        or completion.request.native_molecules is not True
        or function.__globals__ is not vars(module)
        or frame.f_code is not function.__code__
        or frame.f_globals is not vars(module)
        or frame.f_locals.get("session") is not session
        or frame.f_locals.get("context") is not participant
        or participant is None
        or participant.completion is not completion
        or participant.session is not session
        or module._CLAIMED.get(completion.claim) is not participant
        or completion.molecule_session is not session
        or not completion.active
        or completion.body_frame is not None
        or participant.factory_attempted
    ):
        raise ValueError("Actual pre-constructor molecular binder/claim required")
    with _LOCK:
        if parent.owner in _MOLECULE_INITIAL_LEASES:
            completion.invalid = participant.invalid = True
            _reject(parent, "Original molecular material epoch already attempted")
        lease = SimpleNamespace(
            parent=parent,
            completion=completion,
            session=session,
            participant=participant,
            module=module,
            sessions=module._SESSIONS,
            claims=module._CLAIMED,
            original=parent.completion_initial_lease,
            claim_frame=sys._getframe(),
            status="claiming",
        )
        _MOLECULE_INITIAL_LEASES[parent.owner] = parent.molecule_initial_lease = lease
        try:
            # Authenticate the complete old epoch BEFORE excluding any field.
            _check_init_dynamics_prelude_authority(completion.parent)
            stores = module.SIM_STORES
            if stores != (
                "molecules",
                "cc_cells",
                "cc_env",
                "c_env_bound",
                "extra_rho_cells",
                "extra_rho_env",
            ):
                raise ValueError("Exact original molecular Simulator material stores required")
            lease.stores = stores
            lease.functions = tuple(
                (name, fn, parent.atoms(fn))
                for name in ("bind_completion", "_context", "project_state", "state_roots")
                for fn in (vars(module)[name],)
            )
            original = lease.original
            lease.sim_fields = original.sim_fields | frozenset(stores)
            lease.handler_fields, lease.objects = original.handler_fields, original.objects
            lease.holders = tuple(vars(value) for _, value in lease.objects)
            lease.names = tuple(tuple(holder) for holder in lease.holders)
            lease.fields = [{} for _ in lease.objects]
            lease.view = SimpleNamespace(
                objects=lease.objects, fields=lease.fields, weak_proxies=parent.proxies
            )
            lease.tape = SimpleNamespace(rng=parent.parent.rng, events=(), draws=(), locals={})
            for name in ("cell_i", "cell_type", "cell_base", "cell_layout", "cell_aliases"):
                setattr(lease, name, getattr(original, name))
            lease.values = _completion_initial_values(parent, lease)
            lease.graph = core.previous._scope(parent.parent.world).graph(
                lease.view, lease.view, lease.tape
            )
            lease.status = "ready"
            return parent
        except BaseException as error:
            primary = parent.entry_error if parent.entry_error is not None else error
            lease.status, lease.primary = "failed", primary
            if error is not primary:
                lease.secondary = (error, primary)
            parent.invalid = completion.invalid = participant.invalid = True
            raise primary  # noqa: B904 -- preserve original cause, retain secondary separately.


def _check_completion_molecule_ancestor(parent, completion, session):
    lease = _molecule_initial_lease(parent)
    if lease is None or lease.completion is not completion or lease.session is not session:
        raise ValueError("Original molecular material reservation required")
    if _check_init_dynamics_prelude_authority(completion.parent) is not parent:
        raise ValueError("Different original material ancestry")
    return parent


def _storage_initial_lease(parent):
    owner = getattr(parent, "owner", None)
    lease = _STORAGE_INITIAL_LEASES.get(owner) if owner is not None else None
    if lease is None:
        return None
    if lease.status == "claiming":
        frame = sys._getframe(1)
        while frame is not None and frame is not lease.claim_frame:
            frame = frame.f_back
        if frame is None:
            raise ValueError("Incomplete storage reservation cannot authenticate a caller")
        return None
    actual = _storage_runtime(parent)
    if (
        lease.status != "ready"
        or actual is None
        or actual[0] is not lease.transition
        or actual[2] is not lease.completion
        or lease.parent is not parent
        or getattr(parent, "storage_initial_lease", None) is not lease
        or _COMPLETION_INITIAL_LEASES.get(owner) is not lease.original_lease
        or parent.completion_initial_lease is not lease.original_lease
        or parent.dynamics_lease is not lease.dynamics_lease
        or parent.seed_lease is not lease.seed_lease
        or parent.trial is not lease.trial
        or parent.parameter_record is not lease.parameter_record
    ):
        raise ValueError("Original irreversible storage/INIT lease association changed")
    _completion_cell_layout(parent, lease)
    return lease


def _storage_initial_values(parent, lease):
    # The same projection/typed codec and actual array aliases are retained.
    # Only the original Simulator's explicitly declared storage fields are
    # additionally owned by the once-retired successor, never other objects.
    return _completion_initial_values(parent, lease)


def _claim_storage_ancestor(parent, completion, transition):
    """Claimed by the actual DynamicsOwner issuer before any storage body."""
    actual = _storage_runtime(parent)
    if actual is None or actual[0] is not transition or actual[2] is not completion:
        raise ValueError("Actual provider-issued storage transition required")
    provider, frame = actual[3], sys._getframe(1)
    if (
        frame.f_code is not provider._claim_for_init_storage.__code__
        or frame.f_globals is not vars(provider)
        or frame.f_locals.get("context") is not completion
        or frame.f_locals.get("transition") is not transition
        or transition.body_frame is not None
        or not transition.active
    ):
        raise ValueError("Actual original Dynamics transfer must precede storage source")
    with _LOCK:
        if parent.owner in _STORAGE_INITIAL_LEASES:
            transition.invalid = completion.invalid = True
            _reject(parent, "Original storage/INIT ancestry epoch was already attempted")
        lease = SimpleNamespace(
            parent=parent,
            completion=completion,
            transition=transition,
            claim_frame=sys._getframe(),
            status="claiming",
            original_lease=parent.completion_initial_lease,
            dynamics_lease=parent.dynamics_lease,
            seed_lease=parent.seed_lease,
            trial=parent.trial,
            parameter_record=parent.parameter_record,
            frames={},
            attempts=[],
        )
        _STORAGE_INITIAL_LEASES[parent.owner] = lease
        parent.storage_initial_lease = lease
        try:
            # This is the final validation of the previous data epoch. Once
            # sealed, the new projection is used instead of stale histories
            # or flux arrays; the old lease is preserved, never rewritten.
            _check_init_dynamics_prelude_authority(completion.parent)
            original = _molecule_initial_lease(parent) or lease.original_lease
            fields = tuple(name for _, name in actual[1]._stores())
            if len(fields) != 52 or len(set(fields)) != 51:
                raise ValueError("Exact original 52 stores/51 Simulator fields required")
            lease.sim_fields = original.sim_fields | frozenset(fields)
            lease.handler_fields = original.handler_fields
            lease.objects = original.objects
            lease.holders = tuple(vars(value) for _, value in lease.objects)
            lease.names = tuple(tuple(vars(value)) for _, value in lease.objects)
            lease.fields = [{} for _ in lease.objects]
            lease.view = SimpleNamespace(
                objects=lease.objects, fields=lease.fields, weak_proxies=parent.proxies
            )
            lease.tape = SimpleNamespace(rng=parent.parent.rng, events=(), draws=(), locals={})
            for name in ("cell_i", "cell_type", "cell_base", "cell_layout", "cell_aliases"):
                setattr(lease, name, getattr(original, name))
            lease.values = _storage_initial_values(parent, lease)
            lease.graph = core.previous._scope(parent.parent.world).graph(
                lease.view, lease.view, lease.tape
            )
            lease.status = "ready"
            return parent
        except BaseException as error:
            primary = next(
                (
                    value
                    for value in (
                        parent.entry_error,
                        getattr(completion, "entry_error", None),
                        getattr(transition, "entry_error", None),
                    )
                    if value is not None
                ),
                error,
            )
            lease.status, lease.primary = "failed", primary
            if error is not primary:
                lease.secondary = (error, primary)
            parent.invalid = completion.invalid = transition.invalid = True
            raise primary  # noqa: B904 -- keep original cause; secondary is retained above.


def _electrical_runtime(parent):
    """Authenticate the actual leaf without changing the original routes."""
    actual = _storage_runtime(parent)
    if actual is None or getattr(actual[0], "electrical_transition", None) is None:
        return None
    storage, provider, completion, completion_api = actual
    route = vars(provider).get("_electrical_route")
    if type(route) is not FunctionType or route.__globals__ is not vars(provider):
        raise ValueError("Actual storage/electrical source route unavailable")
    retained = _atoms(route)
    path = Path(provider.__file__)
    previous._ready()._source_interface(provider, path.read_bytes(), path, ("_electrical_route",))
    current = _atoms(route)
    if (
        vars(provider).get("_electrical_route") is not route
        or len(current) != len(retained)
        or any(a is not b for a, b in zip(current, retained, strict=True))
    ):
        raise ValueError("Authenticated original electrical route changed before invocation")
    transition, api = route(storage)
    if (
        transition is not storage.electrical_transition
        or transition.storage_parent is not storage
        or transition.parent is not completion
        or transition.phase is not parent.phase
        or transition.sim is not parent.phase.sim
        or transition.cells is not parent.cells
        or transition.p is not parent.p
        or transition.handler is not parent.phase.dyna
    ):
        raise ValueError("Actual same-INIT electrical ancestry changed")
    return transition, api, storage, completion, completion_api


def _electrical_initial_lease(parent):
    owner = getattr(parent, "owner", None)
    lease = _ELECTRICAL_INITIAL_LEASES.get(owner) if owner is not None else None
    if lease is None:
        return None
    if lease.status == "claiming":
        frame = sys._getframe(1)
        while frame is not None and frame is not lease.claim_frame:
            frame = frame.f_back
        if frame is None:
            raise ValueError("Incomplete electrical reservation cannot authenticate a caller")
        return None
    actual = _electrical_runtime(parent)
    if (
        lease.status != "ready"
        or actual is None
        or actual[0] is not lease.transition
        or actual[2] is not lease.storage
        or actual[3] is not lease.completion
        or lease.parent is not parent
        or getattr(parent, "electrical_initial_lease", None) is not lease
        or _STORAGE_INITIAL_LEASES.get(owner) is not lease.original_lease
        or parent.storage_initial_lease is not lease.original_lease
        or parent.completion_initial_lease is not lease.completion_lease
        or parent.dynamics_lease is not lease.dynamics_lease
        or parent.seed_lease is not lease.seed_lease
        or parent.trial is not lease.trial
        or parent.parameter_record is not lease.parameter_record
    ):
        raise ValueError("Original irreversible electrical/INIT lease association changed")
    _completion_cell_layout(parent, lease)
    return lease


def _claim_electrical_ancestor(parent, completion, storage, transition):
    """The actual Completion grandchild issuer claims this once before stores."""
    actual = _electrical_runtime(parent)
    if (
        actual is None
        or actual[0] is not transition
        or actual[2] is not storage
        or actual[3] is not completion
    ):
        raise ValueError("Actual provider-issued electrical transition required")
    provider, frame = actual[4], sys._getframe(1)
    claim = vars(provider).get("_claim_electrical_ancestor")
    if (
        type(claim) is not FunctionType
        or claim.__globals__ is not vars(provider)
        or frame.f_code is not claim.__code__
        or frame.f_globals is not vars(provider)
        or claim.__code__.co_argcount != 3
        or any(
            frame.f_locals.get(name) is not expected
            for name, expected in zip(
                claim.__code__.co_varnames[:3], (completion, storage, transition), strict=True
            )
        )
        or transition.body_frame is not None
        or not transition.active
    ):
        raise ValueError("Actual original Completion claim must precede electrical source")
    with _LOCK:
        if parent.owner in _ELECTRICAL_INITIAL_LEASES:
            transition.invalid = storage.invalid = completion.invalid = True
            _reject(parent, "Original electrical/INIT ancestry epoch already attempted")
        lease = SimpleNamespace(
            parent=parent,
            completion=completion,
            storage=storage,
            transition=transition,
            claim_frame=sys._getframe(),
            status="claiming",
            original_lease=parent.storage_initial_lease,
            completion_lease=parent.completion_initial_lease,
            dynamics_lease=parent.dynamics_lease,
            seed_lease=parent.seed_lease,
            trial=parent.trial,
            parameter_record=parent.parameter_record,
            frames={},
            attempts=[],
        )
        _ELECTRICAL_INITIAL_LEASES[parent.owner] = lease
        parent.electrical_initial_lease = lease
        try:
            _check_init_dynamics_prelude_authority(completion.parent)
            original = lease.original_lease
            fields = frozenset(name for _, _, name in actual[1]._stores(actual[1]._definitions()))
            if len(fields) != 27:
                raise ValueError("Exact source-derived27 electrical fields required")
            lease.sim_fields = original.sim_fields | fields
            lease.handler_fields = original.handler_fields
            lease.objects = original.objects
            lease.holders = tuple(vars(value) for _, value in lease.objects)
            lease.names = tuple(tuple(vars(value)) for _, value in lease.objects)
            lease.fields = [{} for _ in lease.objects]
            lease.view = SimpleNamespace(
                objects=lease.objects, fields=lease.fields, weak_proxies=parent.proxies
            )
            lease.tape = SimpleNamespace(rng=parent.parent.rng, events=(), draws=(), locals={})
            for name in ("cell_i", "cell_type", "cell_base", "cell_layout", "cell_aliases"):
                setattr(lease, name, getattr(original, name))
            lease.values = _storage_initial_values(parent, lease)
            lease.graph = core.previous._scope(parent.parent.world).graph(
                lease.view, lease.view, lease.tape
            )
            lease.status = "ready"
            return parent
        except BaseException as error:
            primary = next(
                (
                    value
                    for value in (
                        parent.entry_error,
                        getattr(completion, "entry_error", None),
                        getattr(storage, "entry_error", None),
                        getattr(transition, "entry_error", None),
                    )
                    if value is not None
                ),
                error,
            )
            lease.status, lease.primary = "failed", primary
            if error is not primary:
                lease.secondary = (error, primary)
            parent.invalid = completion.invalid = storage.invalid = transition.invalid = True
            raise primary  # noqa: B904 -- preserve primary/cause; retain secondary separately.


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
    completion = getattr(transition, "completion_transition", None)
    storage = getattr(completion, "storage_transition", None)
    electrical = getattr(storage, "electrical_transition", None)
    step = getattr(electrical, "first_step_transition", None)
    terminal = getattr(electrical, "terminal_init_transition", None)
    if terminal is not None and getattr(terminal, "claimed", False):
        if step is not None or getattr(electrical, "short_init_transition", None) is not None:
            raise ValueError("Exclusive natural terminal ancestry required")
        return _check_terminal_init_ancestor(parent, completion, storage, electrical, terminal)
    if step is not None and getattr(step, "claimed", False):
        return _check_first_step_ancestor(parent, completion, storage, electrical, step)
    if _dynamics_route(parent)[0] is not transition:
        raise ValueError("Different original dynamics transition")
    _check(parent, closed=True)
    _completion(parent)
    electrical = _electrical_initial_lease(parent)
    if electrical is not None:
        if _storage_initial_values(parent, electrical).identity != electrical.values.identity:
            raise ValueError("Electrical source changed an unowned original INIT value")
        graph = core.previous._scope(parent.parent.world).graph(
            electrical.view, electrical.view, electrical.tape
        )
        core.previous._same(graph[0], electrical.graph[0])
        if graph[1] != electrical.graph[1]:
            raise ValueError("Electrical source changed an immutable original reference edge")
        return parent
    storage = _storage_initial_lease(parent)
    if storage is not None:
        if _storage_initial_values(parent, storage).identity != storage.values.identity:
            raise ValueError("Storage changed an unowned original INIT value")
        graph = core.previous._scope(parent.parent.world).graph(
            storage.view, storage.view, storage.tape
        )
        core.previous._same(graph[0], storage.graph[0])
        if graph[1] != storage.graph[1]:
            raise ValueError("Storage changed an original immutable reference edge")
        return parent
    forwarded = _completion_initial_lease(parent)
    if forwarded is not None:
        forwarded = _molecule_initial_lease(parent) or forwarded
        if _completion_initial_values(parent, forwarded).identity != forwarded.values.identity:
            raise ValueError("Completion changed an unowned original INIT value")
        graph = core.previous._scope(parent.parent.world).graph(
            forwarded.view, forwarded.view, forwarded.tape
        )
        core.previous._same(graph[0], forwarded.graph[0])
        if graph[1] != forwarded.graph[1]:
            raise ValueError("Completion changed an original immutable reference edge")
        return parent
    lease = parent.dynamics_lease
    core._check_profile_ancestor_edges(lease)
    if _dynamics_values(parent).identity != lease.values.identity:
        raise ValueError("Dynamics changed original non-owned INIT state")
    graph = _dynamics_graph(parent)
    core.previous._same(graph[0], lease.graph[0])
    if graph[1] != lease.graph[1]:
        raise ValueError("Dynamics changed an original immutable reference edge")
    return parent


def _first_step_runtime(parent):
    actual = _electrical_runtime(parent)
    if actual is None or getattr(actual[0], "first_step_transition", None) is None:
        return None
    electrical, provider, storage, completion, completion_api = actual
    function = vars(provider).get("_first_step_route")
    if type(function) is not FunctionType:
        raise ValueError("Actual original electrical first-step route unavailable")
    retained = _atoms(function)
    path = Path(provider.__file__)
    previous._ready()._source_interface(provider, path.read_bytes(), path, ("_first_step_route",))
    if vars(provider).get("_first_step_route") is not function:
        raise ValueError("Proved first-step routing slot changed")
    current = _atoms(function)
    if len(current) != len(retained) or any(
        a is not b for a, b in zip(current, retained, strict=True)
    ):
        raise ValueError("Proved first-step route code/default changed")
    step, module = function(electrical)
    if (
        step.electrical_parent is not electrical
        or step.parent is not completion
        or step.initial is not parent
        or step.phase is not parent.phase
        or step.sim is not parent.phase.sim
        or step.cells is not parent.cells
        or step.p is not parent.p
    ):
        raise ValueError("Original same-INIT first-step ancestry changed")
    return step, module, electrical, storage, completion, completion_api


def _advance_child(parent, electrical):
    first = getattr(electrical, "first_step_transition", None)
    short = getattr(electrical, "short_init_transition", None)
    terminal = getattr(electrical, "terminal_init_transition", None)
    if terminal is not None:
        if first is not None or short is not None:
            _reject(parent, "Mutually exclusive actual INIT advance routes required")
        return terminal, _terminal_init_runtime
    if first is not None and short is not None:
        _reject(parent, "Mutually exclusive actual INIT advance routes required")
    return (short, _short_init_runtime) if short is not None else (first, _first_step_runtime)


def _short_init_runtime(parent):
    actual = _electrical_runtime(parent)
    if actual is None or getattr(actual[0], "short_init_transition", None) is None:
        return None
    electrical, provider, storage, completion, completion_api = actual
    if getattr(electrical, "first_step_transition", None) is not None:
        raise ValueError("Completed/active first-step cannot become continuous INIT")
    function = vars(provider).get("_short_init_route")
    if type(function) is not FunctionType or function.__globals__ is not vars(provider):
        raise ValueError("Actual original short-history electrical route unavailable")
    retained = _atoms(function)
    path = Path(provider.__file__)
    previous._ready()._source_interface(provider, path.read_bytes(), path, ("_short_init_route",))
    if vars(provider).get("_short_init_route") is not function:
        raise ValueError("Actual short-history routing slot changed")
    core.previous._same(_atoms(function), retained)
    child, module = function(electrical)
    if (
        child.electrical_parent is not electrical
        or child.parent is not completion
        or child.storage_parent is not storage
        or child.initial is not parent
        or child.phase is not parent.phase
        or child.sim is not parent.phase.sim
        or child.cells is not parent.cells
        or child.p is not parent.p
    ):
        raise ValueError("Original same-INIT short-history ancestry changed")
    return child, module, electrical, storage, completion, completion_api


def _claim_first_step_ancestor(parent, completion, storage, electrical, transition):
    """Reserved for Key's actual reviewed first-step ancestor transfer."""
    actual = _first_step_runtime(parent)
    if (
        actual is None
        or actual[0] is not transition
        or any(
            (
                a is not b
                for a, b in zip(actual[2:5], (electrical, storage, completion), strict=True)
            )
        )
    ) or parent.owner in _TERMINAL_INIT_INITIAL_LEASES:
        raise ValueError("Actual original first-step runtime ancestry required")
    module = actual[5]
    storage_api = sys.modules.get("cells.processes.betse_native_init_storage")
    name = (
        vars(storage_api).get("FIRST_STEP_ANCESTOR_CLAIM")
        if type(storage_api) is ModuleType
        else None
    )
    function = vars(module).get(name) if type(name) is str else None
    frame = sys._getframe(1)
    if (
        type(function) is not FunctionType
        or frame.f_code is not function.__code__
        or frame.f_globals is not vars(module)
        or (not transition.active)
        or (transition.setup_frame is not None)
        or transition.claimed
        or (parent.owner in _FIRST_STEP_INITIAL_LEASES)
        or (parent.owner in _SHORT_INIT_INITIAL_LEASES)
    ):
        parent.invalid = transition.invalid = True
        raise ValueError("Actual once-only Key first-step reservation required")
    lease = SimpleNamespace(
        parent=parent,
        completion=completion,
        storage=storage,
        electrical=electrical,
        child=transition,
        original=parent.electrical_initial_lease,
        status="claiming",
    )
    _FIRST_STEP_INITIAL_LEASES[parent.owner] = parent.first_step_initial_lease = lease
    lease.status = "reserved"
    return parent


def _check_first_step_ancestor(parent, completion, storage, electrical, transition):
    lease = _FIRST_STEP_INITIAL_LEASES.get(parent.owner)
    actual = _first_step_runtime(parent)
    if (
        lease is None
        or lease is not getattr(parent, "first_step_initial_lease", None)
        or lease.status != "reserved"
        or (actual is None)
        or (actual[0] is not transition)
        or (lease.parent is not parent)
        or (lease.completion is not completion)
        or (lease.storage is not storage)
        or (lease.electrical is not electrical)
        or (lease.child is not transition)
        or (lease.original is not parent.electrical_initial_lease)
        or (_ELECTRICAL_INITIAL_LEASES.get(parent.owner) is not lease.original)
    ) or parent.owner in _TERMINAL_INIT_INITIAL_LEASES:
        raise ValueError("Retained original first-step ancestor lease changed")
    if actual[1]._check_ancestor_metadata(transition) is not electrical:
        raise ValueError("Different factored first-step electrical ancestry")
    return parent


def _claim_short_init_ancestor(parent, completion, storage, electrical, transition):
    actual = _short_init_runtime(parent)
    if (
        actual is None
        or actual[0] is not transition
        or any(
            (
                a is not b
                for a, b in zip(actual[2:5], (electrical, storage, completion), strict=True)
            )
        )
    ):
        raise ValueError("Actual original short-history runtime ancestry required")
    module = actual[5]
    function = vars(module).get("_claim_short_init_ancestor")
    frame = sys._getframe(1)
    with _LOCK:
        if (
            type(function) is not FunctionType
            or function.__globals__ is not vars(module)
            or frame.f_code is not function.__code__
            or (frame.f_globals is not vars(module))
            or (frame.f_locals.get("context") is not completion)
            or (frame.f_locals.get("storage") is not storage)
            or (frame.f_locals.get("electrical") is not electrical)
            or (frame.f_locals.get("transition") is not transition)
            or (not transition.active)
            or (transition.setup_frame is not None)
            or (transition.loop_frame is not None)
            or transition.claimed
            or (parent.owner in _FIRST_STEP_INITIAL_LEASES)
            or (parent.owner in _SHORT_INIT_INITIAL_LEASES)
        ) or parent.owner in _TERMINAL_INIT_INITIAL_LEASES:
            parent.invalid = transition.invalid = True
            raise ValueError("Actual once-only Key short-history reservation required")
        lease = SimpleNamespace(
            parent=parent,
            completion=completion,
            storage=storage,
            electrical=electrical,
            child=transition,
            original=parent.electrical_initial_lease,
            iterations=transition.request.iterations,
            status="reserved",
        )
        _SHORT_INIT_INITIAL_LEASES[parent.owner] = parent.short_init_initial_lease = lease
        return parent


def _check_short_init_ancestor(parent, completion, storage, electrical, transition):
    lease = _SHORT_INIT_INITIAL_LEASES.get(parent.owner)
    actual = _short_init_runtime(parent)
    if (
        lease is None
        or lease is not getattr(parent, "short_init_initial_lease", None)
        or lease.status != "reserved"
        or (actual is None)
        or (actual[0] is not transition)
        or (lease.parent is not parent)
        or (lease.completion is not completion)
        or (lease.storage is not storage)
        or (lease.electrical is not electrical)
        or (lease.child is not transition)
        or (lease.original is not parent.electrical_initial_lease)
        or (_ELECTRICAL_INITIAL_LEASES.get(parent.owner) is not lease.original)
        or (transition.request.iterations != lease.iterations)
        or (parent.owner in _FIRST_STEP_INITIAL_LEASES)
    ) or parent.owner in _TERMINAL_INIT_INITIAL_LEASES:
        raise ValueError("Retained original bounded INIT ancestor lease changed")
    if actual[1]._check_ancestor_metadata(transition) is not electrical:
        raise ValueError("Different factored short-history electrical ancestry")
    return parent


def _dynamics_wrapper_guard(parent, frame):
    child, module = _dynamics_route(parent)
    raw = (frame, dict(frame.f_locals))
    parent.last_dynamics_attempt = raw
    if len(parent.dynamics_attempts) >= MAX_WORK:
        _reject(parent, "Bounded original helper wrapper attempt ledger exhausted")
    parent.dynamics_attempts.append(raw)
    if _electrical_runtime(parent) is not None:
        _electrical_wrapper_guard(parent, frame)
        return
    if _storage_runtime(parent) is not None:
        _storage_wrapper_guard(parent, frame)
        return
    if _completion_runtime(parent) is not None:
        _completion_wrapper_guard(parent, frame)
        return
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
    if _electrical_runtime(parent) is not None:
        _electrical_dispatch_guard(parent, label, delegate, args, kwargs, frame)
        return
    if _storage_runtime(parent) is not None:
        _storage_dispatch_guard(parent, label, delegate, args, kwargs, frame)
        return
    if _completion_runtime(parent) is not None:
        _completion_dispatch_guard(parent, label, delegate, args, kwargs, frame)
        return
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


def _completion_wrapper_guard(parent, frame):
    current, api, _, _ = _completion_runtime(parent)
    lease = _completion_initial_lease(parent)
    lease.last_attempt = (frame, dict(frame.f_locals))
    if len(lease.attempts) >= MAX_WORK:
        _reject(parent, "Bounded original completion wrapper attempts exhausted")
    lease.attempts.append(lease.last_attempt)
    api._guard(current)
    role, method = frame.f_locals.get("name"), frame.f_locals.get("method")
    permitted = (
        ("init_profiles", "init_events", "_finalize_events_global", "_finalize_events_tissue")
        if role == "TissueHandler"
        else (
            ("pick_cells_and_mems", "pick_cells", "get_image_mask")
            if role
            in (
                "TissuePickerAll",
                "TissuePickerColor",
                "TissuePickerIndices",
                "TissuePickerPercent",
                "TissuePickerImage",
            )
            else ()
        )
    )
    function = (
        vars(parent.runtime_types[role]).get(method) if role in parent.runtime_types else None
    )
    actual = frame.f_locals.get("actual")
    if (
        method not in permitted
        or type(function) is not FunctionType
        or frame.f_code is not function.__code__
        or frame.f_globals is not function.__globals__
        or frame.f_locals.get("context") is not parent
        or type(actual) is not parent.runtime_types[role]
        or _OBJECTS.get(actual) is not parent
        or frame.f_locals.get("delegate") is not getattr(parent.factories[role], method)
        or id(frame) in lease.frames
    ):
        _reject(parent, "Actual original INIT handler/picker runtime wrapper required")
    for name, cell in zip(function.__code__.co_freevars, function.__closure__ or (), strict=True):
        if frame.f_locals.get(name) is not cell.cell_contents:
            _reject(parent, "Original completion wrapper closure/cell changed")
    args, kwargs = frame.f_locals.get("args"), frame.f_locals.get("kwargs")
    if type(args) is not tuple or type(kwargs) is not dict:
        _reject(parent, "Actual original wrapper argument containers required")
    claim = SimpleNamespace(
        frame=frame,
        function=function,
        actual=actual,
        role=role,
        method=method,
        args=args,
        kwargs=kwargs,
        arg_refs=tuple(args),
        keyword_refs=tuple(kwargs.items()),
        dispatched=False,
    )
    lease.frames[id(frame)] = claim
    api._wrapper_guard(current, parent, frame)
    if lease.frames.get(id(frame)) is not claim or claim.dispatched:
        _reject(parent, "Original completion entry claim changed during observation")


def _completion_dispatch_guard(parent, label, delegate, args, kwargs, frame):
    current, api, _, _ = _completion_runtime(parent)
    lease = _completion_initial_lease(parent)
    api._guard(current)
    wrapper = frame.f_back
    claim = lease.frames.get(id(wrapper))
    if (
        claim is None
        or claim.frame is not wrapper
        or claim.dispatched
        or label != claim.role + "." + claim.method
        or claim.function is not vars(parent.runtime_types[claim.role]).get(claim.method)
        or delegate is not getattr(parent.factories[claim.role], claim.method)
        or not args
        or args[0] is not claim.actual
        or frame.f_code is not _invoke.__code__
        or frame.f_globals is not globals()
        or wrapper.f_locals.get("args") is not claim.args
        or wrapper.f_locals.get("kwargs") is not claim.kwargs
        or len(args) != len(claim.arg_refs) + 1
        or any(a is not b for a, b in zip(args[1:], claim.arg_refs, strict=True))
        or tuple(kwargs.items()) != claim.keyword_refs
    ):
        _reject(parent, "Actual once-claimed same-instance completion dispatch required")
    claim.dispatched, claim.invocation = True, frame


def _storage_wrapper_guard(parent, frame):
    current, api, _, _ = _storage_runtime(parent)
    lease = _storage_initial_lease(parent)
    lease.last_attempt = (frame, dict(frame.f_locals))
    if len(lease.attempts) >= MAX_WORK:
        _reject(parent, "Bounded original storage wrapper attempts exhausted")
    lease.attempts.append(lease.last_attempt)
    api._guard(current)
    function = vars(parent.runtime_types["Simulator"]).get("clear_storage")
    if (
        frame.f_locals.get("name") != "Simulator"
        or frame.f_locals.get("method") != "clear_storage"
        or type(function) is not FunctionType
        or frame.f_code is not function.__code__
        or frame.f_globals is not function.__globals__
        or frame.f_locals.get("context") is not parent
        or frame.f_locals.get("actual") is not parent.phase.sim
        or type(parent.phase.sim) is not parent.runtime_types["Simulator"]
        or _OBJECTS.get(parent.phase.sim) is not parent
        or frame.f_locals.get("delegate") is not parent.factories["Simulator"].clear_storage
        or frame.f_back is not current.driver_frame
        or id(frame) in lease.frames
    ):
        _reject(parent, "Only the actual same-instance original storage wrapper may enter")
    for name, cell in zip(function.__code__.co_freevars, function.__closure__ or (), strict=True):
        if frame.f_locals.get(name) is not cell.cell_contents:
            _reject(parent, "Original storage wrapper closure/frame changed")
    args, kwargs = frame.f_locals.get("args"), frame.f_locals.get("kwargs")
    if type(args) is not tuple or type(kwargs) is not dict:
        _reject(parent, "Actual original storage wrapper argument containers required")
    claim = SimpleNamespace(
        frame=frame,
        function=function,
        args=args,
        kwargs=kwargs,
        arg_refs=tuple(args),
        keyword_refs=tuple(kwargs.items()),
        dispatched=False,
    )
    lease.frames[id(frame)] = claim
    api._wrapper_guard(current, parent, frame)
    if (
        lease.frames.get(id(frame)) is not claim
        or claim.dispatched
        or frame.f_locals.get("args") is not claim.args
        or frame.f_locals.get("kwargs") is not claim.kwargs
    ):
        _reject(parent, "Original storage wrapper claim changed during observation")


def _storage_dispatch_guard(parent, label, delegate, args, kwargs, frame):
    current, api, _, _ = _storage_runtime(parent)
    lease = _storage_initial_lease(parent)
    api._guard(current)
    wrapper = frame.f_back
    claim = lease.frames.get(id(wrapper))
    if (
        claim is None
        or claim.frame is not wrapper
        or claim.dispatched
        or label != "Simulator.clear_storage"
        or claim.function is not vars(parent.runtime_types["Simulator"]).get("clear_storage")
        or delegate is not parent.factories["Simulator"].clear_storage
        or frame.f_code is not _invoke.__code__
        or frame.f_globals is not globals()
        or wrapper.f_back is not current.driver_frame
        or not args
        or args[0] is not parent.phase.sim
        or len(args) != 3
        or args[1] is not parent.cells
        or args[2] is not parent.p
        or kwargs
        or wrapper.f_locals.get("args") is not claim.args
        or wrapper.f_locals.get("kwargs") is not claim.kwargs
        or len(args) != len(claim.arg_refs) + 1
        or any(a is not b for a, b in zip(args[1:], claim.arg_refs, strict=True))
        or tuple(kwargs.items()) != claim.keyword_refs
    ):
        _reject(parent, "Actual once-claimed original storage dispatch required")
    claim.dispatched, claim.invocation = True, frame


def _electrical_wrapper_guard(parent, frame):
    current, api, _, _, _ = _electrical_runtime(parent)
    lease = _electrical_initial_lease(parent)
    lease.last_attempt = (frame, dict(frame.f_locals))
    if len(lease.attempts) >= MAX_WORK:
        _reject(parent, "Bounded original electrical wrapper attempts exhausted")
    lease.attempts.append(lease.last_attempt)
    api._guard(current)
    function = vars(parent.runtime_types["Simulator"]).get("update_V")
    if (
        frame.f_locals.get("name") != "Simulator"
        or frame.f_locals.get("method") != "update_V"
        or type(function) is not FunctionType
        or frame.f_code is not function.__code__
        or frame.f_globals is not function.__globals__
        or frame.f_locals.get("context") is not parent
        or frame.f_locals.get("actual") is not parent.phase.sim
        or type(parent.phase.sim) is not parent.runtime_types["Simulator"]
        or _OBJECTS.get(parent.phase.sim) is not parent
        or frame.f_locals.get("delegate") is not parent.factories["Simulator"].update_V
        or frame.f_back is not current.driver_frame
        or id(frame) in lease.frames
    ):
        _reject(parent, "Only the actual original Simulator.update_V wrapper may enter")
    for name, cell in zip(function.__code__.co_freevars, function.__closure__ or (), strict=True):
        if frame.f_locals.get(name) is not cell.cell_contents:
            _reject(parent, "Original electrical wrapper closure/frame changed")
    args, kwargs = frame.f_locals.get("args"), frame.f_locals.get("kwargs")
    if type(args) is not tuple or type(kwargs) is not dict:
        _reject(parent, "Actual original electrical argument containers required")
    claim = SimpleNamespace(
        frame=frame,
        function=function,
        args=args,
        kwargs=kwargs,
        arg_refs=tuple(args),
        keyword_refs=tuple(kwargs.items()),
        dispatched=False,
    )
    lease.frames[id(frame)] = claim
    api._wrapper_guard(current, parent, frame)
    if (
        lease.frames.get(id(frame)) is not claim
        or claim.dispatched
        or frame.f_locals.get("args") is not claim.args
        or frame.f_locals.get("kwargs") is not claim.kwargs
    ):
        _reject(parent, "Original electrical wrapper claim changed during observation")


def _electrical_dispatch_guard(parent, label, delegate, args, kwargs, frame):
    current, api, _, _, _ = _electrical_runtime(parent)
    lease = _electrical_initial_lease(parent)
    api._guard(current)
    wrapper = frame.f_back
    claim = lease.frames.get(id(wrapper))
    if (
        claim is None
        or claim.frame is not wrapper
        or claim.dispatched
        or label != "Simulator.update_V"
        or claim.function is not vars(parent.runtime_types["Simulator"]).get("update_V")
        or delegate is not parent.factories["Simulator"].update_V
        or frame.f_code is not _invoke.__code__
        or frame.f_globals is not globals()
        or wrapper.f_back is not current.driver_frame
        or not args
        or args[0] is not parent.phase.sim
        or len(args) != 3
        or args[1] is not parent.cells
        or args[2] is not parent.p
        or kwargs
        or wrapper.f_locals.get("args") is not claim.args
        or wrapper.f_locals.get("kwargs") is not claim.kwargs
        or len(args) != len(claim.arg_refs) + 1
        or any(a is not b for a, b in zip(args[1:], claim.arg_refs, strict=True))
        or tuple(kwargs.items()) != claim.keyword_refs
    ):
        _reject(parent, "Actual once-claimed original electrical dispatch required")
    claim.dispatched, claim.invocation = True, frame


# Separate held natural-terminal ancestry; no selected-history reuse.


def _terminal_init_runtime(parent):
    actual = _electrical_runtime(parent)
    if actual is None or getattr(actual[0], "terminal_init_transition", None) is None:
        return None
    electrical, provider, storage, completion, completion_api = actual
    if (
        getattr(electrical, "first_step_transition", None) is not None
        or getattr(electrical, "short_init_transition", None) is not None
    ):
        raise ValueError("Completed/active first-step cannot become continuous INIT")
    function = vars(provider).get("_terminal_init_route")
    if type(function) is not FunctionType or function.__globals__ is not vars(provider):
        raise ValueError("Actual original natural-terminal electrical route unavailable")
    retained = _atoms(function)
    path = Path(provider.__file__)
    previous._ready()._source_interface(
        provider, path.read_bytes(), path, ("_terminal_init_route",)
    )
    if vars(provider).get("_terminal_init_route") is not function:
        raise ValueError("Actual natural-terminal routing slot changed")
    core.previous._same(_atoms(function), retained)
    child, module = function(electrical)
    if (
        child.electrical_parent is not electrical
        or child.parent is not completion
        or child.storage_parent is not storage
        or (child.initial is not parent)
        or (child.phase is not parent.phase)
        or (child.sim is not parent.phase.sim)
        or (child.cells is not parent.cells)
        or (child.p is not parent.p)
    ):
        raise ValueError("Original same-INIT natural-terminal ancestry changed")
    return (child, module, electrical, storage, completion, completion_api)


def _claim_terminal_init_ancestor(parent, completion, storage, electrical, transition):
    actual = _terminal_init_runtime(parent)
    if (
        actual is None
        or actual[0] is not transition
        or any(
            (
                a is not b
                for a, b in zip(actual[2:5], (electrical, storage, completion), strict=True)
            )
        )
    ):
        raise ValueError("Actual original natural-terminal runtime ancestry required")
    module = actual[5]
    function = vars(module).get("_claim_terminal_init_ancestor")
    frame = sys._getframe(1)
    with _LOCK:
        if (
            type(function) is not FunctionType
            or function.__globals__ is not vars(module)
            or frame.f_code is not function.__code__
            or (frame.f_globals is not vars(module))
            or (frame.f_locals.get("context") is not completion)
            or (frame.f_locals.get("storage") is not storage)
            or (frame.f_locals.get("electrical") is not electrical)
            or (frame.f_locals.get("transition") is not transition)
            or (not transition.active)
            or (transition.setup_frame is not None)
            or (transition.loop_frame is not None)
            or transition.claimed
            or (parent.owner in _FIRST_STEP_INITIAL_LEASES)
            or (parent.owner in _TERMINAL_INIT_INITIAL_LEASES)
        ) or (
            parent.owner in _SHORT_INIT_INITIAL_LEASES
            or transition.request.iterations
            != actual[1]._configured_count(parent.p.init_tsteps, transition.request.maximum)
        ):
            parent.invalid = transition.invalid = True
            raise ValueError("Actual once-only Key natural-terminal reservation required")
        lease = SimpleNamespace(
            parent=parent,
            completion=completion,
            storage=storage,
            electrical=electrical,
            child=transition,
            original=parent.electrical_initial_lease,
            iterations=transition.request.iterations,
            status="reserved",
            maximum=transition.request.maximum,
        )
        _TERMINAL_INIT_INITIAL_LEASES[parent.owner] = parent.terminal_init_initial_lease = lease
        return parent


def _check_terminal_init_ancestor(parent, completion, storage, electrical, transition):
    lease = _TERMINAL_INIT_INITIAL_LEASES.get(parent.owner)
    actual = _terminal_init_runtime(parent)
    if (
        lease is None
        or lease is not getattr(parent, "terminal_init_initial_lease", None)
        or lease.status != "reserved"
        or (actual is None)
        or (actual[0] is not transition)
        or (lease.parent is not parent)
        or (lease.completion is not completion)
        or (lease.storage is not storage)
        or (lease.electrical is not electrical)
        or (lease.child is not transition)
        or (lease.original is not parent.electrical_initial_lease)
        or (_ELECTRICAL_INITIAL_LEASES.get(parent.owner) is not lease.original)
        or (transition.request.iterations != lease.iterations)
        or (parent.owner in _FIRST_STEP_INITIAL_LEASES)
    ) or (
        parent.owner in _SHORT_INIT_INITIAL_LEASES
        or transition.request.maximum != lease.maximum
        or transition.request.iterations
        != actual[1]._configured_count(parent.p.init_tsteps, lease.maximum)
    ):
        raise ValueError("Retained original bounded INIT ancestor lease changed")
    if actual[1]._check_ancestor_metadata(transition) is not electrical:
        raise ValueError("Different factored natural-terminal electrical ancestry")
    return parent
