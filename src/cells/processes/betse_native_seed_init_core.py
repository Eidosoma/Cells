"""Held whole native SEED init_core, on the actual completed-world Simulator.

This is source preparation, not an INIT phase or an executable checkpoint.
The preceding SimRunner callback is a literal two-statement call-site projection
using the actual phase callback. No SimRunner, phase, Simulator, parameter or
world is manufactured. Upstream retirement and wrapper routing must be adopted
explicitly; unset pins refuse before reading a supplied parent.
"""

import ast
import builtins
import copy
import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import (
    CodeType,
    FrameType,
    FunctionType,
    MappingProxyType,
    MethodType,
    ModuleType,
    SimpleNamespace,
)
from weakref import WeakKeyDictionary

from cells.processes import betse_native_seed_init_core_source as source
from cells.processes import betse_native_seed_world_poisson as previous

LAW_ID = "betse_same_completed_seed_world_whole_init_core@1"
RELEASE = "CELLS_NATIVE_SEED_INIT_CORE_RELEASED"
PARENT_SOURCE_SHA256 = "39539d52b750fd75787a2897efc564ad4ca886381ab09acf1560159aa815ba33"
PARENT_REVIEW_SHA256 = "a4fd24cebcb04930a7d4d884a18b0e2368020510d7d57e6be72f4b213cad1bbb"
COORDINATOR_SOURCE_SHA256 = "df9e0e0e260a2df648015d4bd5c15dfbacbaa9f0302145e2b7deb8aec6af07d0"
COORDINATOR_REVIEW_SHA256 = "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d"
LITERAL_SHA256 = "e5583ce17462e47e78b47556253429ecdabfc29ebb509f166c54cb283bc2ed1c"
PROPOSED_CLAIM = "_claim_for_seed_init_core"
PROPOSED_CHECK = "_check_seed_init_core_authority"
PROPOSED_ROUTER = "_seed_init_core_api"
METHODS = ("init_core", "initDenv")
CALLBACK_STATUS = "Creating core computational matrices..."
NUMPY_HELPERS = ("zeros", "ones", "asarray", "copy", "hstack")
NATIVE_PINS = {
    "betse/science/sim.py": source.SIM_SHA256,
    "betse/science/simrunner.py": source.RUNNER_SHA256,
}
PARAMETER_READS = (
    "is_ecm",
    "T",
    "vol_env",
    "ions_dict",
    "ion_long_name",
    "cell_concs",
    "env_concs",
    "mem_perms",
    "free_diff",
    "ion_charge",
    "molar_mass",
    "Dtj_rel",
    "cCa_er",
    "z_Ca",
    "z_M",
    "D_adh",
    "D_tj",
    "er",
)
CELL_READS = (
    "mem_i",
    "cell_i",
    "xypts",
    "X",
    "nn_i",
    "gj_default_weights",
    "gj_len",
    "mem_to_cells",
    "envInds_inClust",
    "all_bound_mem_inds",
    "interior_bound_mem_inds",
    "ecm_inds_bound_cell",
)
MAX_WORK = 100000
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_FORWARDED = WeakKeyDictionary()
_ACTIVE, _FAILED, _LOCK = [], (), RLock()
_LAST_FAILED = None
_BASE, _PREFIX, _CORE, _LITERAL = (
    previous._BASE,
    previous._PREFIX,
    previous._CORE,
    previous._LITERAL,
)
_PARENT_FILE, _SOURCE_FILE = Path(previous.__file__), Path(source.__file__)
_PROOFS = (
    source.SeedCore.init_core,
    source.SeedCore.initDenv,
    source.SeedCoreCallSite.continue_seed,
)


class InitCoreRejected(previous.PoissonRejected):
    pass


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    world_owner: object
    parent_identity: str
    source_identity: str
    flux_operator: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Actual completed world ownership cannot be restored")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    flux_operator: str
    before: object
    cache: object
    stages: tuple
    events: tuple
    stream_before: object
    stream_after: object
    callback_completed: bool
    method_returns: tuple
    source_completed: bool
    source_failure: str | None
    capture_failures: tuple
    identity: str


def _digest(value):
    return previous._digest(value)


def _node(tree, cls, name):
    return next(
        n
        for c in tree.body
        if isinstance(c, ast.ClassDef) and c.name == cls
        for n in c.body
        if isinstance(n, ast.FunctionDef) and n.name == name
    )


def _body(node):
    return ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False)


def _source_nodes():
    """Exact original bytes and complete bodies; compiling is not evaluation."""
    native = Path(_PREFIX.aliases.NATIVE)
    trees = {}
    for name, expected in NATIVE_PINS.items():
        path = native / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Original source changed: " + name)
        trees[name] = ast.parse(path.read_bytes(), filename=str(path))
    if (
        _SOURCE_FILE.is_symlink()
        or hashlib.sha256(_SOURCE_FILE.read_bytes()).hexdigest() != LITERAL_SHA256
    ):
        raise ValueError("Selected whole core literal changed")
    proof = ast.parse(_SOURCE_FILE.read_bytes())
    nodes = {name: _node(trees["betse/science/sim.py"], "Simulator", name) for name in METHODS}
    for name, original in nodes.items():
        if _body(original) != _body(_node(proof, "SeedCore", name)):
            raise ValueError("Whole original core/helper body differs: " + name)
    seed = _node(trees["betse/science/simrunner.py"], "SimRunner", "seed")
    selected = [n for n in seed.body if n.lineno in (138, 140)]
    if len(selected) != 2:
        raise ValueError("Original preceding callback/call boundary changed")
    call = copy.deepcopy(_node(proof, "SeedCoreCallSite", "continue_seed"))
    if ast.dump(ast.Module(body=selected, type_ignores=[])) != _body(call):
        raise ValueError("Original callback then core call differs")
    call.body = copy.deepcopy(selected)
    call.lineno, call.end_lineno = 138, 140
    nodes["continue_seed"] = call
    return nodes


def _codes():
    result = {}
    for name, original in _source_nodes().items():
        node = copy.deepcopy(original)
        node.decorator_list, node.returns = [], None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        filename = str(
            Path(_PREFIX.aliases.NATIVE)
            / ("betse/science/simrunner.py" if name == "continue_seed" else "betse/science/sim.py")
        )
        compiled = compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            filename,
            "exec",
            dont_inherit=True,
        )
        result[name] = next(
            c for c in compiled.co_consts if type(c) is CodeType and c.co_name == name
        )
    return result


def source_plan():
    nodes = _source_nodes()
    return dict(
        law_id=LAW_ID,
        native_pins=dict(NATIVE_PINS),
        literal_sha256=LITERAL_SHA256,
        bodies={
            name: dict(
                first_line=n.lineno,
                last_line=n.end_lineno,
                ast_sha256=hashlib.sha256(_body(n).encode()).hexdigest(),
            )
            for name, n in nodes.items()
        },
        methods=METHODS,
        callback=CALLBACK_STATUS,
        callback_source_lines=(138, 139, 140),
        parent_source_pin=PARENT_SOURCE_SHA256,
        parent_review_pin=PARENT_REVIEW_SHA256,
        coordinator_source_pin=COORDINATOR_SOURCE_SHA256,
        coordinator_review_pin=COORDINATOR_REVIEW_SHA256,
        parent_hooks={
            PROPOSED_CLAIM: (
                "(owner, *, expected: exact retained previous.Trial, transition, entries)"
            ),
            PROPOSED_CHECK: "(transition) -> same factored completed-world parent",
        },
        router=PROPOSED_ROUTER,
        entries={
            "wrapper_guard": "(transition, original, wrapper_frame)",
            "dispatch": "(transition, original, label, delegate, actual, args, kwargs, frame)",
        },
        immutable_parent_contract=(
            "same phase/sim/p/caller/grid/mesh/mask/global MT",
            "same closed parameter claim and callbacks/dyna/cache/export",
            "all world fields/operators and flux policy unchanged",
            "only actual sim core stores may change after irreversible retirement",
        ),
        numpy_helpers=NUMPY_HELPERS,
        additional_helpers=("logs.log_info", "gaussian_filter"),
        ndarray_methods=("reshape", "max"),
        parameter_reads=PARAMETER_READS,
        cell_reads=CELL_READS,
        branches="initDenv only when original p.is_ecm is true; original ion insertion order",
        inherited_flux_modes=previous.FLUX_OPERATORS,
        original_flux_numerics_unchanged=True,
        caller_projection=(
            "two original SimRunner statements; actual callback, no SimRunner authority"
        ),
        source_native_or_scientific_release=False,
        INIT_or_physical_admission=False,
        stop_before="phase.dyna.init_profiles and all later SimRunner.seed work",
    )


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _ready():
    if not all(
        _pin(v)
        for v in (
            PARENT_SOURCE_SHA256,
            PARENT_REVIEW_SHA256,
            COORDINATOR_SOURCE_SHA256,
            COORDINATOR_REVIEW_SHA256,
        )
    ):
        raise InitCoreRejected(
            "Actual world/core producer adoption remains held", stage="unbound_contract"
        )
    if (
        Path(previous.__file__) != _PARENT_FILE
        or _PARENT_FILE.is_symlink()
        or hashlib.sha256(_PARENT_FILE.read_bytes()).hexdigest() != PARENT_SOURCE_SHA256
    ):
        raise InitCoreRejected("Reviewed completed-world producer required", stage="producer")
    api = previous._ready()
    path = Path(api.__file__)
    if (
        path.is_symlink()
        or hashlib.sha256(path.read_bytes()).hexdigest() != COORDINATOR_SOURCE_SHA256
    ):
        raise InitCoreRejected("Reviewed coordinator producer required", stage="producer")
    route = getattr(api, PROPOSED_ROUTER, None)
    if (
        type(route) is not FunctionType
        or route.__globals__ is not vars(api)
        or route() is not sys.modules[__name__]
    ):
        raise InitCoreRejected("Actual Simulator route remains closed", stage="dispatch_held")
    for name in (PROPOSED_CLAIM, PROPOSED_CHECK):
        fn = getattr(previous, name, None)
        if type(fn) is not FunctionType or fn.__globals__ is not vars(previous):
            raise InitCoreRejected(
                "Completed-world retirement unavailable", stage="parent_hooks_held"
            )
    _source_nodes()
    return api


def request_record(value):
    return dict(
        law_id=LAW_ID,
        parent_identity=value.parent_identity,
        source_identity=value.source_identity,
        flux_operator=value.flux_operator,
    )


def from_world(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise InitCoreRejected("Explicit whole native core law required", stage="law")
    _ready()
    with _LOCK:
        if owner in _RETIRED:
            raise InitCoreRejected("World epoch already consumed", stage="consumed")
        parent = previous._authority(owner)
        if (
            parent.trial.source_completed is not True
            or parent.request.flux_operator not in previous.FLUX_OPERATORS
        ):
            raise InitCoreRejected(
                "Complete actual world with explicit flux mode required", stage="parent"
            )
        value = Request(
            owner, parent.trial.identity, _digest(source_plan()), parent.request.flux_operator, ""
        )
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (parent, parent.trial, previous._epoch(parent))
        return value


def _capture_failure(context, error, stage, raw):
    context.last_capture_error = (stage, error, raw)
    if context.observation_error is None:
        context.observation_error = error
    try:
        context.capture_errors += ((stage, error, raw),)
    except BaseException as secondary:
        context.capture_history_error = (secondary, context.last_capture_error)


def _guard(context):
    if getattr(context, "inherited_hook_active", False):
        _reject(context, "Reentrant work from inherited observer")
    if context.entry_error is not None:
        raise context.entry_error
    if context.observation_error is not None:
        raise _LITERAL._CaptureStop() from context.observation_error
    if getattr(context, "observing", False) and (
        context.restore_getters[0]() is not context.observer_hooks[0]
        or context.restore_getters[1]() is not context.observer_hooks[1]
    ):
        _capture_failure(
            context,
            ValueError("Active outer/core hook identity changed"),
            "active_hooks",
            context.observer_hooks,
        )
        raise _LITERAL._CaptureStop() from context.observation_error
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        raise InitCoreRejected("Active same-thread core claim required", stage=context.stage)


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = InitCoreRejected(
            reason, stage=context.stage, request=context.request, partial=context
        )
    raise context.entry_error


def _cache(context, value):
    return previous._scope(context.parent).snapshot(previous._project(context.parent, value))


def _snapshot(context):
    return _cache(
        context,
        dict(
            simulator=vars(context.sim),
            caller=vars(context.cells),
            parameters=vars(context.p),
            grid=vars(context.grid),
            flux_operator=context.request.flux_operator,
            raw_history=context.events,
        ),
    )


def _graph(context):
    context.graph_view.simulator = vars(context.sim)
    context.graph_view.caller = vars(context.cells)
    context.graph_view.parameters = vars(context.p)
    context.graph_view.raw_history = context.events
    return previous._scope(context.parent).graph(
        context.graph_view, context.graph_view, context.graph_tape
    )


def _bootstrap(context):
    function, code, namespace = context.checker
    if (
        context.api._independent_atoms is not function
        or function.__code__ is not code
        or function.__globals__ is not namespace
    ):
        raise ValueError("Independent core helper checker changed")
    for name, helper, atoms in context.metadata_helpers:
        if globals().get(name) is not helper:
            raise ValueError("Core metadata helper replaced: " + name)
        current = function(helper)
        if len(current) != len(atoms) or any(
            a is not b for a, b in zip(current, atoms, strict=True)
        ):
            raise ValueError("Core metadata helper code/default/closure changed: " + name)


def _raw_partial(context):
    # Direct live references are preserved independently of all cache encoders.
    return dict(
        phase=context.phase,
        simulator=context.sim,
        parameters=context.p,
        caller=context.cells,
        grid=context.grid,
        mesh=context.mesh,
        mask=context.mask,
        simulator_fields=dict(vars(context.sim)),
        method_locals=dict(context.locals),
        events=tuple(context.events),
        helper_inputs=tuple(context.helper_inputs),
        helper_returns=tuple(context.helper_returns),
        last_helper=context.last_helper,
        method_returns=tuple(context.method_returns),
        source_error=context.primary,
        last_source_exception=context.last_source_exception,
        last_source_return=context.last_source_return,
        last_helper_return=context.last_helper_return,
        source_exceptions=tuple(context.source_exceptions),
        raw_returns=tuple(context.raw_returns),
        admitted_frames=context.admitted,
        callback_frames=tuple(context.callback_frames),
        callback_returned=tuple(context.callback_returned),
        capture_errors=context.capture_errors,
        cleanup_errors=context.cleanup_errors,
    )


def _record(context, name, raw):
    # The raw value is installed BEFORE any observer; no serializer replaces it.
    context.last_observation = (name, raw)
    if len(context.events) >= MAX_WORK:
        _reject(context, "Bounded core observation work exhausted")
    try:
        context.events.append((name, raw))
    except BaseException as error:
        _capture_failure(context, error, "event_history", context.last_observation)
        _guard(context)
    try:
        context.stages.append((name, _cache(context, raw)))
    except BaseException as error:
        _capture_failure(context, error, name, raw)
    _guard(context)


def _immutable(context):
    # Parent check authenticates all reference edges including inherited
    # registries. This additional value seal permits no p/caller/MT mutation.
    value = dict(
        parameters=vars(context.p),
        caller=vars(context.cells),
        grid=vars(context.grid),
        simulator_prefix={k: vars(context.sim).get(k) for k in context.original_sim_fields},
    )
    return _cache(context, value).identity, previous._rng(context.parent).identity


def _bindings(context):
    _bootstrap(context)
    functions = (
        context.parent_claim,
        context.parent_check,
        _dispatch,
        _wrapper_guard,
        _guard,
        _check,
        _check_fields,
        _profiles_route,
        _profile_ancestor_members,
        _profile_ancestor_bindings,
        _profile_ancestor_edges,
        _check_profile_ancestor_edges,
        _profile_lease_views,
        _profile_lease_values,
        _profile_lease_graph,
        _capture_profile_lease,
        _claim_for_seed_profiles,
        _check_seed_profiles_authority,
        _claim_profile_junction_permission,
        _check_profile_lease_projection,
        _record,
        _helper,
        _account.__wrapped__,
        _restore,
        _frame_role,
        _validate_frame,
        _admit_frame,
        _observe,
        _after_observer,
        _PREFIX._callback_values,
        sys.call_tracing,
        *_PROOFS,
        *context.original_methods.values(),
        *context.helper_functions,
        *context.methods.values(),
        *context.wrappers.values(),
        *context.callback_chain,
        *context.callback_helpers,
        _CORE.caches.snapshot,
        previous._scope,
        previous._project,
        ast.parse,
        builtins.compile,
        hashlib.sha256,
    )
    return (
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        _FORWARDED,
        _ACTIVE,
        _LOCK,
        context.api,
        context.required_hooks,
        *context.required_hooks,
        context.restore_setters,
        *context.restore_setters,
        context.restore_getters,
        *context.restore_getters,
        context.call_tracing,
        context.helpers,
        *(v for pair in context.helpers.items() for v in pair),
        *(
            getattr(helper, attr, None)
            for helper in context.helpers.values()
            for attr in ("__wrapped__", "_implementation")
        ),
        context.parent_claim,
        context.parent_check,
        context.entries,
        *(v for pair in context.entries.items() for v in pair),
        *(
            v
            for cls in (
                type(context.phase),
                type(context.sim),
                type(context.p),
                type(context.cells),
            )
            for v in (cls, *_LITERAL._surface(cls))
        ),
        context.numpy,
        *(getattr(context.numpy, n) for n in NUMPY_HELPERS),
        context.numpy.ndarray,
        context.numpy.ndarray.reshape,
        context.numpy.ndarray.max,
        context.original_methods["init_core"].__globals__,
        context.original_methods["init_core"].__globals__["np"],
        context.original_methods["init_core"].__globals__["logs"],
        context.original_methods["init_core"].__globals__["logs"].log_info,
        context.original_methods["initDenv"].__globals__["gaussian_filter"],
        *(v for fn in functions for v in previous._atoms(fn)),
        *_resolved_bindings((*context.helper_functions, *context.callback_helpers)),
        *(
            v
            for fn in (*context.methods.values(), *context.wrappers.values())
            for v in (fn.__globals__, *fn.__globals__.values())
        ),
        *(getattr(builtins, n) for n in ("len", "list", "setattr", "vars", "enumerate")),
    )


def _resolved_bindings(functions):
    """Retain reached Python globals and module exports without lazy lookup.

    The existing helper closure follows wrapped/implementation/closure/default
    delegates. This adds the resolved names used by those bodies, including
    ndimage support and logging, rather than pinning a function's code alone.
    """
    result = []
    for function in functions:
        namespace, names = function.__globals__, function.__code__.co_names
        result.extend((function, namespace))
        for name in names:
            if name not in namespace:
                continue
            value = namespace[name]
            result.extend((name, value))
            values = [value]
            if type(value) is ModuleType:
                exports = vars(value)
                result.extend((exports,))
                for member in names:
                    if member in exports:
                        result.extend((member, exports[member]))
                        values.append(exports[member])
            for resolved in values:
                if type(resolved) in (FunctionType, MethodType) or callable(resolved):
                    result.extend(previous._atoms(resolved))
                elif type(resolved) is dict:
                    result.extend(atom for pair in resolved.items() for atom in pair)
    return tuple(result)


def _check(context):
    _guard(context) if context.active else None
    _check_fields(context)
    if (
        _ready() is not context.api
        or context.parent_check(context) is not context.parent
        or context.parent.trial is not context.refs[1]
        or context.phase is not context.parent.phase
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.phase.sim is not context.sim
        or context.phase.callbacks is not context.callback
        or vars(context.caller) != {"_callbacks": context.callback}
        or context.cells.grid_obj is not context.grid
        or context.cells.mesh is not context.mesh
        or context.parent.mask is not context.mask
        or context.parent.rng is not context.rng
        or context.parent.request.flux_operator != context.request.flux_operator
        or _digest(request_record(context.request)) != context.request.identity
        or _digest(source_plan()) != context.request.source_identity
    ):
        raise ValueError("Actual completed world/core identity or closed source changed")
    method = context.callback.progressed_next
    if (
        type(method) is not MethodType
        or method.__self__ is not context.callback
        or method.__func__ is not context.callback_chain[0]
    ):
        raise ValueError("Actual original callback changed")
    previous._same(_bindings(context), context.bindings)
    if _immutable(context) != context.immutable:
        raise ValueError("Core changed a completed-world/prefix field or global MT")


def _check_fields(context):
    """Registry-only Simulator projection permission; never stale parent caches."""
    _bootstrap(context)
    if (
        type(context.request) is not Request
        or _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.world_owner) is not context
        or context.invalid
        or context.thread != get_ident()
        or context.parent is not context.refs[0]
        or context.parent.trial is not context.refs[1]
        or context.phase is not context.parent.phase
        or context.phase.sim is not context.sim
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or type(context.original_sim_fields) is not tuple
    ):
        raise ValueError("Actual irreversible same-Simulator core ownership changed")
    names = tuple(vars(context.sim))
    if names[: len(context.original_sim_fields)] != context.original_sim_fields:
        raise ValueError("Original Simulator field roster was removed or reordered")
    if not context.entered and names != context.original_sim_fields:
        raise ValueError("Simulator fields appeared before actual core body entry")
    if tuple(context.entered) not in ((), ("init_core",), ("init_core", "initDenv")):
        raise ValueError("Unowned Simulator body entry roster")
    return names


def _namespace(context):
    callbacks = _BASE.image.prefix.previous.previous.caches.previous.callbacks
    context.original_methods = {}
    for name in METHODS:
        wrapper = vars(type(context.sim)).get(name)
        if type(wrapper) is not FunctionType:
            raise ValueError("Actual original Simulator wrapper required")
        closure = dict(
            zip(
                wrapper.__code__.co_freevars,
                (c.cell_contents for c in wrapper.__closure__ or ()),
                strict=True,
            )
        )
        delegate = closure.get("delegate")
        chain = tuple(callbacks.simulator._chain(delegate))
        original = callbacks._source_function(delegate, "betse/science/sim.py", name, "Simulator")
        if original not in chain or type(original) is not FunctionType:
            raise ValueError("Exact original Simulator method chain required")
        context.original_methods[name] = original
        context.original_wrappers[name] = wrapper
        context.native_delegates[name] = closure.get("delegate")
        if closure.get("context") is not context.assembly:
            raise ValueError("Same actual constructed Simulator assembly required")
    core = context.original_methods["init_core"]
    denv = context.original_methods["initDenv"]
    context.numpy = core.__globals__["np"]
    if denv.__globals__["np"] is not context.numpy:
        raise ValueError("Original core/helper NumPy must be shared")
    helpers = {name: getattr(context.numpy, name) for name in NUMPY_HELPERS}
    helpers.update(
        log_info=core.__globals__["logs"].log_info,
        gaussian_filter=denv.__globals__["gaussian_filter"],
    )
    context.helpers = MappingProxyType(helpers)
    leaves = tuple(helpers.values()) + tuple(
        member
        for value in helpers.values()
        for attr in ("__wrapped__", "_implementation")
        if (member := getattr(value, attr, None)) is not None
    )
    context.descriptor_helpers = _descriptor_helpers(
        (
            (type(context.p), PARAMETER_READS),
            (type(context.cells), CELL_READS),
            (type(context.phase), ("p", "cells", "sim", "callbacks")),
        )
    )
    context.helper_functions = previous.previous._native_helper_functions(
        (*leaves, *context.descriptor_helpers)
    )
    for name in helpers:

        def observed(*args, _name=name, **kwargs):
            return _helper(context, _name, context.helpers[_name], args, kwargs, sys._getframe())

        context.wrappers[name] = observed
    namespace = dict(
        core.__globals__,
        np=SimpleNamespace(**{n: context.wrappers[n] for n in NUMPY_HELPERS}),
        logs=SimpleNamespace(log_info=context.wrappers["log_info"]),
        gaussian_filter=context.wrappers["gaussian_filter"],
    )
    context.methods = {name: FunctionType(code, namespace, name) for name, code in _codes().items()}
    context.callback_chain = tuple(
        callbacks.simulator._chain(context.callback.progressed_next.__func__)
    )
    body = context.callback_chain[-1]
    path = Path(body.__code__.co_filename)
    if (
        not path.is_relative_to(_PREFIX.aliases.NATIVE)
        or callbacks._source_function(
            context.callback.progressed_next.__func__,
            str(path.relative_to(_PREFIX.aliases.NATIVE)),
            "progressed_next",
            body.__qualname__.split(".")[-2],
        )
        is not body
    ):
        raise ValueError("Actual original progressed_next body required")
    context.callback_helpers = previous.previous._native_helper_functions(context.callback_chain)
    context.allowed_codes = frozenset(
        code
        for fn in (
            *context.methods.values(),
            *context.original_wrappers.values(),
            *context.helper_functions,
            *context.callback_helpers,
        )
        if type(fn) is FunctionType
        for code in previous.previous.previous._code_tree(fn.__code__)
    )
    context.body_codes = {context.methods[n].__code__: n for n in METHODS}
    context.wrapper_codes = {fn.__code__ for fn in context.original_wrappers.values()}
    context.callback_codes = frozenset(fn.__code__ for fn in context.callback_chain)


def _descriptor_helpers(owners):
    """Static lookup only: retain the selected actual attribute-read route."""
    functions = []
    for cls, fields in owners:
        for name in (*fields, "__getattribute__", "__getattr__"):
            member = next((vars(base)[name] for base in cls.__mro__ if name in vars(base)), None)
            if type(member) is FunctionType:
                functions.append(member)
            elif type(member) is property and member.fget is not None:
                functions.append(member.fget)
            elif member is not None:
                getter = next(
                    (
                        vars(base).get("__get__")
                        for base in type(member).__mro__
                        if "__get__" in vars(base)
                    ),
                    None,
                )
                if type(getter) is FunctionType:
                    functions.append(getter)
    return tuple(functions)


def _helper(context, name, delegate, args, kwargs, wrapper):
    _guard(context)
    frame = wrapper.f_back
    if (
        type(frame) is not FrameType
        or frame.f_code not in context.body_codes
        or context.frames.get(context.body_codes[frame.f_code]) is not frame
        or context.helpers.get(name) is not delegate
        or context.helper_busy
    ):
        _reject(context, "Only the actual active original body may call its bound helper")
    context.helper_busy = True
    context.last_helper = (name, args, kwargs, None)
    try:
        try:
            context.helper_inputs.append((name, args, kwargs))
        except BaseException as error:
            _capture_failure(context, error, "helper_input_history", context.last_helper)
            _guard(context)
        _check(context)
        _record(context, name + ".input", (args, kwargs))
        context.active_helper = (name, delegate, args, kwargs)
        context.helper_frame = sys._getframe()
        try:
            result = delegate(*args, **kwargs)
        except BaseException as error:
            if context.primary is None:
                context.primary = error
            raise
        context.last_helper = (name, args, kwargs, result)
        context.last_helper_return = (name, result, None)
        try:
            context.helper_returns.append((name, result))
        except BaseException as error:
            _capture_failure(context, error, "helper_return_history", context.last_helper)
        _guard(context)
        _record(context, name + ".return", result)
        _check(context)
        return result
    finally:
        context.helper_busy = False
        context.active_helper = None
        context.helper_frame = None


def _admit_wrapper(context, frame):
    parent = frame.f_back
    name = frame.f_locals.get("method")
    if name not in METHODS:
        _reject(context, "Only original core and diffusion helper wrappers are allowed")
    expected = context.methods["continue_seed" if name == "init_core" else "init_core"].__code__
    actual_parent = context.caller_frame if name == "init_core" else context.frames.get("init_core")
    expected_args = (context.phase,) if name == "init_core" else (context.cells, context.p)
    if (
        name not in METHODS
        or parent is not actual_parent
        or parent is None
        or parent.f_code is not expected
        or frame.f_code is not context.original_wrappers[name].__code__
        or frame.f_locals.get("actual") is not context.sim
        or frame.f_locals.get("context") is not context.assembly
        or frame.f_locals.get("name") != "Simulator"
        or frame.f_locals.get("delegate") is not context.native_delegates[name]
        or tuple(id(x) for x in frame.f_locals.get("args", ()))
        != tuple(id(x) for x in expected_args)
        or frame.f_locals.get("kwargs")
        or name in context.entered
    ):
        _reject(context, "Original same-Simulator caller/wrapper arguments required")
    if name == "init_core" and not context.callback_completed:
        _reject(context, "Original preceding callback must return before core entry")
    context.wrapper_claims[id(frame)] = (frame, name)


def _wrapper_guard(context, original, wrapper):
    _guard(context)
    claim = context.wrapper_claims.get(id(wrapper))
    if claim is None or claim[0] is not wrapper or original is not context.assembly:
        _reject(context, "Unclaimed original Simulator wrapper")
    _check(context)


def _dispatch(context, original, label, delegate, actual, args, kwargs, dispatch_frame):
    _guard(context)
    native = None if type(dispatch_frame) is not FrameType else dispatch_frame.f_back
    wrapper = None if native is None else native.f_back
    claim = None if wrapper is None else context.wrapper_claims.get(id(wrapper))
    name = None if claim is None else claim[1]
    expected = (context.phase,) if name == "init_core" else (context.cells, context.p)
    if (
        claim is None
        or claim[0] is not wrapper
        or original is not context.assembly
        or actual is not context.sim
        or label != "Simulator." + name
        or delegate is not context.native_delegates[name]
        or type(args) is not tuple
        or len(args) != len(expected)
        or any(a is not b for a, b in zip(args, expected, strict=True))
        or kwargs
        or native.f_code is not context.native_call_code
    ):
        _reject(context, "Original full-frame Simulator dispatch required")
    _check(context)
    context.entered.append(name)
    context.stage = name
    context.dispatch_frames[name] = sys._getframe()
    try:
        try:
            result = context.methods[name](actual, *args, **kwargs)
        except BaseException as error:
            if (
                context.primary is None
                and context.observation_error is None
                and context.entry_error is None
            ):
                context.primary = error
            raise
        context.last_method_return = (name, result)
        try:
            context.method_returns.append((name, result))
        except BaseException as error:
            _capture_failure(context, error, "method_return_history", context.last_method_return)
        _guard(context)
        if result is not None:
            raise ValueError("Original core methods return None")
        _record(context, name + ".completed", dict(vars(actual)))
        _check(context)
        return result
    finally:
        context.dispatch_frames.pop(name, None)
        context.stage = "init_core" if name == "initDenv" else "caller"


def _frame_role(context, frame):
    code = frame.f_code
    if code in context.wrapper_codes:
        return "wrapper", None
    if code is context.methods["continue_seed"].__code__:
        return "caller", "continue_seed"
    if code in context.body_codes:
        return "body", context.body_codes[code]
    if code in context.callback_codes:
        return "callback", None
    helper = context.active_helper
    if helper is not None and type(helper[1]) is FunctionType and code is helper[1].__code__:
        return "helper", helper[0]
    return None


def _validate_frame(context, row):
    """Recheck actual frame/arguments after either inherited callback."""
    frame, role, name = row["frame"], row["role"], row["name"]
    if (
        frame.f_back is not row["parent"]
        or frame.f_code is not row["code"]
        or frame.f_globals is not row["globals"]
    ):
        _reject(context, "Actual admitted frame ancestry changed")
    local = frame.f_locals
    if role == "caller":
        if local.get("self") is not context.caller or local.get("phase") is not context.phase:
            _reject(context, "Actual caller receiver/phase changed")
    elif role == "wrapper":
        _admit_wrapper(context, frame)
    elif role == "body":
        if (
            local.get("self") is not context.sim
            or (name == "init_core" and local.get("phase") is not context.phase)
            or (
                name == "initDenv"
                and (local.get("cells") is not context.cells or local.get("p") is not context.p)
            )
        ):
            _reject(context, "Actual Simulator body receiver/arguments changed")
    elif role == "callback":
        receiver, status = _PREFIX._callback_values(frame)
        if (
            receiver is not context.callback
            or type(status) is not str
            or status != CALLBACK_STATUS
            or status is not row["status"]
        ):
            _reject(context, "Actual callback receiver/status changed")
        if frame.f_code is not context.callback_chain[row["callback_index"]].__code__:
            _reject(context, "Original callback chain changed")
    elif role == "helper":
        if context.active_helper is not row["helper"]:
            _reject(context, "Actual helper call ownership changed")


def _admit_frame(context, frame):
    selected = _frame_role(context, frame)
    if selected is None:
        if (
            frame.f_code.co_filename.startswith(str(_PREFIX.aliases.NATIVE) + os.sep)
            and frame.f_code not in context.allowed_codes
        ):
            _reject(context, "Unbound native helper or later source body")
        return None
    _guard(context)
    if context.inherited_hook_active:
        _reject(context, "Reentrant source entry from an inherited observer")
    old = context.admitted.get(id(frame))
    if old is not None:
        if old["frame"] is not frame or old["returned"]:
            _reject(context, "Repeated completed source frame")
        _validate_frame(context, old)
        return old
    role, name = selected
    row = dict(
        frame=frame,
        parent=frame.f_back,
        code=frame.f_code,
        globals=frame.f_globals,
        role=role,
        name=name,
        returned=False,
        call_layers=set(),
        return_layers=set(),
        source_error=None,
        raw_return=None,
        raw_return_seen=False,
    )
    # Publish the claim before inherited observers, including any caught reentry.
    context.admitted[id(frame)] = row
    if role == "wrapper":
        _admit_wrapper(context, frame)
    elif role == "caller":
        if (
            context.caller_frame is not None
            or frame.f_back is not context.driver_frame
            or frame.f_globals is not context.methods[name].__globals__
        ):
            _reject(context, "Exactly one actual-phase caller frame required")
        context.caller_frame = frame
    elif role == "body":
        if (
            frame.f_back is not context.dispatch_frames.get(name)
            or name in context.frames
            or frame.f_globals is not context.methods[name].__globals__
        ):
            _reject(context, "Core body requires its single original dispatch")
        context.frames[name] = frame
    elif role == "callback":
        at = len(context.callback_frames)
        expected_parent = context.caller_frame if at == 0 else context.callback_frames[-1]
        if (
            at >= len(context.callback_chain)
            or context.callback_completed
            or context.callback_returned
            or frame.f_back is not expected_parent
        ):
            _reject(context, "Original complete callback frame order required")
        function = context.callback_chain[at]
        receiver, status = _PREFIX._callback_values(frame)
        if (
            frame.f_code is not function.__code__
            or frame.f_globals is not function.__globals__
            or receiver is not context.callback
            or type(status) is not str
            or status != CALLBACK_STATUS
            or (at and status is not context.callback_status)
        ):
            _reject(context, "Actual callback receiver/status/native chain required")
        context.callback_status = status
        context.callback_frames.append(frame)
        context.callback_frame = context.callback_frames[0]
        row.update(callback_index=at, status=status)
    else:
        helper = context.active_helper
        if frame.f_back is not context.helper_frame or frame.f_globals is not helper[1].__globals__:
            _reject(context, "Actual helper delegate frame required")
        row["helper"] = helper
    _validate_frame(context, row)
    _check(context)
    return row


def _observe(context, frame, event, arg, *, layer="trace"):
    """Admission and minimal raw retention always precede inherited observers.

    A trace/profile pair shares one claimed frame and one logical return. The
    raw exception/result is installed before locals copies or history appends.
    Fallible copies cannot erase it, nor replace the actual source exception.
    """
    if event == "call":
        row = _admit_frame(context, frame)
        if row is not None:
            if layer in row["call_layers"]:
                _reject(context, "Duplicate observer entry for the same activation")
            row["call_layers"].add(layer)
        return row
    row = context.admitted.get(id(frame))
    if row is None or row["frame"] is not frame:
        return None
    if event == "exception":
        context.last_source_exception = (frame, arg)
        row["source_error"] = arg[1]
        if (
            context.primary is None
            and arg[1] is not context.entry_error
            and arg[1] is not context.observation_error
            and not isinstance(arg[1], _LITERAL._CaptureStop)
        ):
            context.primary = arg[1]
        # Original selected methods have no handlers; helper/callback unwinds
        # keep this exact pending error rather than an observer replacement.
        try:
            context.source_exceptions.append((row["name"], arg[1], frame.f_lasti))
        except BaseException as error:
            _capture_failure(context, error, "exception_history", context.last_source_exception)
    elif event == "return":
        context.last_source_return = (frame, arg, row["source_error"])
        if not row["raw_return_seen"]:
            row["raw_return"] = arg
            row["raw_return_seen"] = True
            if row["role"] == "helper":
                context.last_helper_return = (row["name"], arg, row["source_error"])
            if row["role"] == "callback" and row["callback_index"] == 0:
                context.callback_return = arg
            try:
                context.raw_returns.append((row["name"], arg))
            except BaseException as error:
                _capture_failure(context, error, "return_history", context.last_source_return)
        elif row["raw_return"] is not arg:
            _reject(context, "Trace/profile raw return identity changed")
        row["return_layers"].add(layer)
        # Completion is recorded once after both real hooks have seen this return.
        if row["return_layers"] == {"trace", "profile"}:
            row["returned"] = True
            if row["role"] == "body":
                context.frames.pop(row["name"], None)
            elif row["role"] == "callback":
                index = row["callback_index"]
                if len(context.callback_frames) != len(context.callback_chain) or index != len(
                    context.callback_chain
                ) - 1 - len(context.callback_returned):
                    if row["source_error"] is None and context.primary is None:
                        _reject(context, "Incomplete callback chain return")
                else:
                    context.callback_returned.append(index)
                if row["source_error"] is not None and context.callback_exception is None:
                    context.callback_exception = row["source_error"]
                if index == 0 and context.callback_exception is None:
                    context.callback_completed = True
    if event in ("exception", "return"):
        try:
            context.locals[row["name"] or row["role"]] = dict(frame.f_locals)
        except BaseException as error:
            _capture_failure(context, error, "raw_locals_" + event, frame)
    return row


def _after_observer(context, row, event):
    if row is None:
        return
    if event == "call":
        try:
            _guard(context)
            _validate_frame(context, row)
            _check(context)
        except BaseException as error:
            if error is not context.entry_error:
                _capture_failure(context, error, "observer_postcheck", row["frame"])
            raise


def _restore(context):
    # Shared independently protected restoration, both orderings sampled.
    healthy = _BASE._recover(context)
    if not healthy and context.observation_error is None:
        _capture_failure(
            context,
            ValueError("Both original hooks must be restored"),
            "hook_identity",
            context.final_hook_samples,
        )
    return healthy


@contextmanager
def _account(context):
    old_profile, old_trace = context.required_hooks
    previous_locals = {}

    def observed(frame, event, arg, layer):
        row = None
        try:
            row = _observe(context, frame, event, arg, layer=layer)
        except BaseException as error:
            if error is not context.entry_error:
                _capture_failure(context, error, "observer_" + event, (frame, event, arg))
            if event not in ("exception", "return"):
                raise
        return row

    def forward(prior, frame, event, arg, layer):
        if prior is None or context.inherited_hook_active:
            return None
        context.inherited_hook_active = True
        try:
            # Re-enable observation for source reentry from a prior hook. Nested
            # metadata is not recursively forwarded to that same prior hook.
            return context.call_tracing(prior, (frame, event, arg))
        except BaseException as error:
            _capture_failure(
                context, error, "inherited_" + layer + "_" + event, (frame, event, arg)
            )
            if event not in ("return", "exception", "c_return", "c_exception"):
                raise
        finally:
            context.inherited_hook_active = False

    def profile(frame, event, arg):
        row = observed(frame, event, arg, "profile")
        forward(old_profile, frame, event, arg, "profile")
        _after_observer(context, row, event)

    def trace(frame, event, arg):
        row = observed(frame, event, arg, "trace")
        prior = old_trace if event == "call" else previous_locals.get(id(frame))
        value = forward(prior, frame, event, arg, "trace")
        if event == "call" or value is not None:
            previous_locals[id(frame)] = value
        _after_observer(context, row, event)
        if event == "return":
            previous_locals.pop(id(frame), None)
        return trace

    context.observer_hooks = (profile, trace)
    try:
        context.restore_setters[0](profile)
        context.restore_setters[1](trace)
        context.observing = True
        yield
        _guard(context)
    except BaseException as error:
        context.escaping_error = error
        selected = context.primary if context.primary is not None else context.entry_error
        if selected is not None and selected is not error:
            raise selected  # noqa: B904 - actual primary/cause survives secondary observer failure.
        raise
    finally:
        context.observing = False
        context.hooks_safe = False
        try:
            _restore(context)
        except BaseException as cleanup:
            context.cleanup_errors += (("restore_entry_or_return", cleanup, None),)
        for index in (1, 0):
            try:
                context.restore_setters[index](context.required_hooks[index])
            except BaseException as cleanup:
                context.cleanup_errors += (("caller_restore", cleanup, index),)
        samples = []
        for order in ((0, 1), (1, 0)):
            pair = [None, None]
            for index in order:
                try:
                    pair[index] = context.restore_getters[index]()
                except BaseException as cleanup:
                    context.cleanup_errors += (("caller_sample", cleanup, index),)
            samples.append(tuple(pair))
        context.final_hook_samples = tuple(samples)
        context.hooks_safe = all(
            pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
            for pair in samples
        )
        if not context.hooks_safe:
            context.invalid = True
        if context.cleanup_errors and context.observation_error is None:
            context.observation_error = context.cleanup_errors[0][1]


def trial_record(value):
    return dict(
        request_identity=value.request_identity,
        parent_identity=value.parent_identity,
        flux_operator=value.flux_operator,
        before=None if value.before is None else value.before.identity,
        cache=None if value.cache is None else value.cache.identity,
        stages=tuple((name, cache.identity) for name, cache in value.stages),
        stream_before=None if value.stream_before is None else value.stream_before.identity,
        stream_after=None if value.stream_after is None else value.stream_after.identity,
        callback_completed=value.callback_completed,
        method_returns=value.method_returns,
        source_completed=value.source_completed,
        source_failure=value.source_failure,
        capture_failures=value.capture_failures,
    )


def _failure(context, primary):
    global _FAILED, _LAST_FAILED
    context.invalid = True
    selected = context.primary if context.primary is not None else primary
    context.failure_error = selected
    _LAST_FAILED = context  # No formatter/append/delegate is needed for this root.
    try:
        _FAILED = (*_FAILED, context)
    except BaseException as error:
        context.raw_retention_error = error
    context.partial = context
    if primary is not selected:
        context.last_capture_error = ("interrupted_primary", primary, selected)
        context.capture_errors += (context.last_capture_error,)
    # No callback is permitted on a false or stale hook-health claim.
    for phase in ("partial", "attachment"):
        samples = []
        for order in ((0, 1), (1, 0)):
            pair = [None, None]
            for index in order:
                try:
                    pair[index] = context.restore_getters[index]()
                except BaseException as error:
                    context.cleanup_errors += (("failure_before_sample", error, index),)
            samples.append(tuple(pair))
        context.hooks_safe = all(
            pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
            for pair in samples
        )
        if not context.hooks_safe or context.metadata_stopped:
            context.metadata_stopped = True
            break
        try:
            if phase == "partial":
                context.partial = _raw_partial(context)
            else:
                selected.seed_init_core_partial = context
        except BaseException as error:
            context.last_capture_error = (phase, error, context)
            if context.observation_error is None:
                context.observation_error = error
            context.capture_errors += (context.last_capture_error,)
        samples = []
        for order in ((0, 1), (1, 0)):
            pair = [None, None]
            for index in order:
                try:
                    pair[index] = context.restore_getters[index]()
                except BaseException as error:
                    context.cleanup_errors += (("failure_after_sample", error, index),)
            samples.append(tuple(pair))
        context.hooks_safe = all(
            pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
            for pair in samples
        )
        if not context.hooks_safe:
            context.metadata_stopped = True
    # A rejected observer/attachment entry may have disabled a hook. Recovery
    # does not reauthorize any later metadata callback in this failed epoch.
    for index in (1, 0):
        try:
            context.restore_setters[index](context.required_hooks[index])
        except BaseException as error:
            context.cleanup_errors += (("failure_final_restore", error, index),)
    samples = []
    for order in ((0, 1), (1, 0)):
        pair = [None, None]
        for index in order:
            try:
                pair[index] = context.restore_getters[index]()
            except BaseException as error:
                context.cleanup_errors += (("failure_final_sample", error, index),)
        samples.append(tuple(pair))
    context.final_hook_samples = tuple(samples)
    context.hooks_safe = all(
        pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
        for pair in samples
    )
    raise selected


def _complete(context):
    entered = ("init_core", "initDenv") if context.ecm else ("init_core",)
    returned = ("initDenv", "init_core") if context.ecm else ("init_core",)
    if (
        tuple(context.entered) != entered
        or tuple(name for name, value in context.method_returns) != returned
        or any(value is not None for _, value in context.method_returns)
        or not context.callback_completed
        or context.callback_exception is not None
        or context.frames
        or context.primary is not None
        or context.observation_error is not None
        or context.entry_error is not None
        or context.cleanup_errors
        or not context.hooks_safe
        or any(
            row["call_layers"] != {"trace", "profile"}
            or row["return_layers"] != {"trace", "profile"}
            for row in context.admitted.values()
        )
    ):
        raise ValueError("Whole original callback/core/helper completion required")


def _context(request, refs, api):
    parent = refs[0]
    return SimpleNamespace(
        request=request,
        refs=refs,
        parent=parent,
        api=api,
        phase=parent.phase,
        sim=parent.phase.sim,
        p=parent.p,
        cells=parent.cells,
        grid=parent.grid,
        mesh=parent.mesh,
        mask=parent.mask,
        rng=parent.rng,
        callback=parent.phase.callbacks,
        assembly=parent.parent.assembly,
        native_call_code=parent.parent.prefix.native_call_code,
        original_sim_fields=tuple(vars(parent.phase.sim)),
        ecm=parent.p.is_ecm,
        active=True,
        observing=False,
        invalid=False,
        validating=False,
        thread=get_ident(),
        stage="claim",
        before=None,
        cache=None,
        trial=None,
        stream_before=None,
        stream_after=None,
        primary=None,
        observation_error=None,
        entry_error=None,
        partial=None,
        capture_errors=(),
        cleanup_errors=(),
        events=[],
        stages=[],
        locals={},
        helper_inputs=[],
        helper_returns=[],
        last_helper=None,
        last_observation=None,
        helper_busy=False,
        active_helper=None,
        helper_frame=None,
        last_helper_return=None,
        last_source_exception=None,
        last_source_return=None,
        last_capture_error=None,
        capture_history_error=None,
        admitted={},
        inherited_hook_active=False,
        call_tracing=sys.call_tracing,
        hooks_safe=True,
        metadata_stopped=False,
        entered=[],
        method_returns=[],
        raw_returns=[],
        source_exceptions=[],
        last_method_return=None,
        frames={},
        dispatch_frames={},
        wrapper_claims={},
        original_wrappers={},
        native_delegates={},
        wrappers={},
        caller_frame=None,
        callback_frame=None,
        callback_frames=[],
        callback_returned=[],
        callback_status=None,
        callback_exception=None,
        callback_return=None,
        callback_completed=False,
        required_hooks=(sys.getprofile(), sys.gettrace()),
        restore_setters=(sys.setprofile, sys.settrace),
        restore_getters=(sys.getprofile, sys.gettrace),
        graph_view=SimpleNamespace(),
        graph_tape=SimpleNamespace(rng=parent.rng, events=(), draws=(), locals={}),
    )


def prepare(request, *, enabled=False):
    global _LAST_FAILED
    api = _ready()
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise InitCoreRejected("Actual whole core remains held", stage="release")
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant core claim")
        if type(request) is not Request or request not in _REQUESTS:
            raise InitCoreRejected("Actual process-local request required", stage="request")
        if request in _CONSUMED or request.world_owner in _RETIRED:
            raise InitCoreRejected("World epoch consumed", stage="consumed", request=request)
        refs = _REQUESTS[request]
        parent = previous._authority(request.world_owner)
        if parent is not refs[0] or parent.trial is not refs[1]:
            raise InitCoreRejected("Actual original completed world changed", stage="parent")
        previous._same_epoch(parent, refs[2])
        context = _context(request, refs, api)
        context.driver_frame = sys._getframe()
        # Irreversible even on failed hook acquisition, namespace or observer setup.
        _CONSUMED[request] = _RETIRED[request.world_owner] = context
        _ACTIVE.append(context)
        try:
            context.parent_claim = getattr(previous, PROPOSED_CLAIM)
            context.parent_check = getattr(previous, PROPOSED_CHECK)
            checker = context.api._independent_atoms
            context.checker = (checker, checker.__code__, checker.__globals__)
            context.metadata_helpers = tuple(
                (name, fn, checker(fn))
                for name, fn in globals().items()
                if type(fn) is FunctionType and fn.__globals__ is globals()
            )
            context.entries = MappingProxyType(
                dict(wrapper_guard=_wrapper_guard, dispatch=_dispatch)
            )
            context.parent_claim(
                request.world_owner, expected=refs[1], transition=context, entries=context.entries
            )
            _namespace(context)
            context.caller = SimpleNamespace(_callbacks=context.callback)
            context.bindings = _bindings(context)
            context.immutable = _immutable(context)
            context.before, context.stream_before = _snapshot(context), previous._rng(parent)
            _check(context)
            with _account(context):
                context.stage = "caller"
                context.methods["continue_seed"](context.caller, context.phase)
            _guard(context)
            _complete(context)
            _check(context)
            context.cache, context.stream_after = _snapshot(context), previous._rng(parent)
            context.graph = _graph(context)
            trial = Trial(
                request.identity,
                request.parent_identity,
                request.flux_operator,
                context.before,
                context.cache,
                tuple(context.stages),
                tuple(context.events),
                context.stream_before,
                context.stream_after,
                context.callback_completed,
                tuple(context.method_returns),
                True,
                None,
                (),
                "",
            )
            context.trial = replace(trial, identity=_digest(trial_record(trial)))
            context.hooks_safe = False
            try:
                _restore(context)
            except BaseException as cleanup:
                context.cleanup_errors += (("restore_entry_or_return", cleanup, None),)
            for index in (1, 0):
                try:
                    context.restore_setters[index](context.required_hooks[index])
                except BaseException as cleanup:
                    context.cleanup_errors += (("caller_restore", cleanup, index),)
            samples = []
            for order in ((0, 1), (1, 0)):
                pair = [None, None]
                for index in order:
                    try:
                        pair[index] = context.restore_getters[index]()
                    except BaseException as cleanup:
                        context.cleanup_errors += (("caller_sample", cleanup, index),)
                samples.append(tuple(pair))
            context.final_hook_samples = tuple(samples)
            context.hooks_safe = all(
                pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
                for pair in samples
            )
            if not context.hooks_safe or context.cleanup_errors:
                raise ValueError("Final original observer identities not safely restored")
            context.active = False
            owner = object.__new__(InitCoreOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            selected = context.primary if context.primary is not None else error
            context.failure_error = selected
            _LAST_FAILED = context
            try:
                _failure(context, selected)
            except BaseException as secondary:
                if secondary is not selected:
                    context.failure_entry_error = secondary
                    context.metadata_stopped = True
            context.hooks_safe = False
            try:
                _restore(context)
            except BaseException as cleanup:
                context.cleanup_errors += (("restore_entry_or_return", cleanup, None),)
            for index in (1, 0):
                try:
                    context.restore_setters[index](context.required_hooks[index])
                except BaseException as cleanup:
                    context.cleanup_errors += (("caller_restore", cleanup, index),)
            samples = []
            for order in ((0, 1), (1, 0)):
                pair = [None, None]
                for index in order:
                    try:
                        pair[index] = context.restore_getters[index]()
                    except BaseException as cleanup:
                        context.cleanup_errors += (("caller_sample", cleanup, index),)
                samples.append(tuple(pair))
            context.final_hook_samples = tuple(samples)
            context.hooks_safe = all(
                pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
                for pair in samples
            )
            raise selected  # noqa: B904 - preserve the actual primary and explicit cause.
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True


class InitCoreOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the actual completed-world continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No normalized core or saved executable owner")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not InitCoreOwner or owner not in _ISSUED:
        raise InitCoreRejected("Actual issued core child required", stage="owner")
    context = _ISSUED[owner]
    if owner in _FORWARDED or hasattr(context, "profiles"):
        raise InitCoreRejected(
            "Core epoch was irreversibly forwarded to profiles",
            stage="forwarded",
            trial=context.trial,
            partial=context,
        )
    if context.active or context.invalid or context.validating:
        raise InitCoreRejected("Core child unavailable", stage="owner")
    context.validating = True
    try:
        _check(context)
        _complete(context)
        graph = _graph(context)
        previous._same(graph[0], context.graph[0])
        if graph[1] != context.graph[1]:
            raise ValueError("Completed core actual alias edges changed")
        if (
            context.trial.source_completed is not True
            or context.trial.request_identity != context.request.identity
            or context.trial.parent_identity != context.request.parent_identity
            or context.trial.flux_operator != context.request.flux_operator
            or len(context.trial.events) != len(context.events)
            or any(
                a != b or x is not y
                for (a, x), (b, y) in zip(context.trial.events, context.events, strict=True)
            )
            or context.trial.identity != _digest(trial_record(context.trial))
            or context.trial.cache.identity != _snapshot(context).identity
        ):
            raise ValueError("Completed core cache or trial changed")
    except BaseException as error:
        _failure(context, error)
    finally:
        context.validating = False
    return context


def _profiles_route(parent):
    module = _ready()._seed_init_profiles_api()
    child, owner = getattr(parent, "profiles", None), getattr(parent, "owner", None)
    if (
        child is None
        or owner is None
        or _ISSUED.get(owner) is not parent
        or _FORWARDED.get(owner) is not child
        or parent.active
        or parent.invalid
        or child.invalid
        or type(child.request) is not module.Request
        or child.request.core_owner is not owner
        or module._REQUESTS.get(child.request) is not child.refs
        or module._CONSUMED.get(child.request) is not child
        or module._RETIRED.get(owner) is not child
        or child.parent is not parent
        or child.refs[0] is not parent
        or child.refs[1] is not parent.trial
        or child.phase is not parent.phase
        or child.sim is not parent.sim
        or child.p is not parent.p
        or child.cells is not parent.cells
        or child.grid is not parent.grid
        or child.dyna is not parent.phase.dyna
        or child.thread != parent.thread
        or child.thread != get_ident()
        or tuple(child.entries) != ("wrapper_guard", "dispatch", "picker_dispatch")
        or any(child.entries[name] is not getattr(module, "_" + name) for name in child.entries)
    ):
        raise ValueError("Actual core/profile issuance or retirement edge changed")
    return child, module


def _profile_ancestor_members(parent):
    operators = parent.parent
    geometry, lifecycle = operators.parent, operators.parent.parent
    constructor, image = lifecycle.parent, lifecycle.parent.parent
    return (
        (previous, operators),
        (previous.previous, geometry),
        (previous.previous.previous, lifecycle),
        (_BASE, constructor),
        (_BASE.image, image),
        (_PREFIX, image.parent),
        (sys.modules[__name__], parent),
    )


def _profile_ancestor_bindings(parent):
    """Reauthenticate real code/issuance links; never invoke a retired state validator."""
    operators, geometry = parent.parent, parent.parent.parent
    lifecycle, constructor = geometry.parent, geometry.parent.parent
    image, prefix = constructor.parent, constructor.parent.parent
    api, construction = parent.api, parent.assembly.world_transition
    _bootstrap(parent)
    if (
        previous._seed_core_route(operators)[0] is not parent
        or previous.previous._poisson_route(geometry)[0] is not operators
        or previous.previous.previous._geometry_route(lifecycle)[0] is not geometry
        or _BASE._lifecycle_route(constructor)[0] is not lifecycle
        or _BASE.image._mesh_route(image) is not constructor
        or _PREFIX._voronoi_route(prefix) is not image
    ):
        raise ValueError("Original prefix/image/mesh/lifecycle/geometry chain changed")
    api._world_parameter_authority(construction)
    api._world_live_aliases(construction)
    api._compare_bindings(construction)
    api._world_stage_authority(construction.evidence[-1].authority)
    _BASE.image._check_mesh_authority(constructor)
    for module, context, function in (
        (previous, operators, "_bindings"),
        (previous.previous, geometry, "_binding"),
        (previous.previous.previous, lifecycle, "_bindings"),
        (_BASE, constructor, "_bindings"),
    ):
        _same = previous._same
        _same(getattr(module, function)(context), context.bindings)
    previous._same(_bindings(parent), parent.bindings)
    _complete(parent)


def _profile_ancestor_edges(parent):
    """Strong references to existing registry objects and their exact issued entries."""
    edges = []
    members = list(_profile_ancestor_members(parent))
    world = parent.assembly.world_transition
    members.extend((module, module._WORLD[world.request]) for module in world.api.stages)
    attributes = (
        "request",
        "refs",
        "trial",
        "parent",
        "phase",
        "p",
        "cells",
        "sim",
        "mesh",
        "mask",
        "rng",
        "grid",
        "objects",
        "holders",
        "projector",
        "entries",
        "runtime_types",
    )
    registry_names = (
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
    )
    for module, context in members:
        roots = [context, getattr(context, "request", None), getattr(context, "refs", None)]
        roots.extend(value for _, value in getattr(context, "objects", ()))
        fields = tuple(
            (name, getattr(context, name)) for name in attributes if hasattr(context, name)
        )
        registries = []
        for name in registry_names:
            registry = vars(module).get(name)
            if registry is None:
                continue
            records = []
            for key, value in registry.items():
                target = value[0] if type(value) is tuple and value else value
                if target is context or any(key is root or value is root for root in roots):
                    records.append((key, value, tuple(value) if type(value) is tuple else ()))
            registries.append((name, registry, tuple(records)))
        edges.append((module, context, fields, tuple(registries)))
    return tuple(edges)


def _check_profile_ancestor_edges(lease):
    for module, context, fields, registries in lease.edges:
        if any(getattr(context, name) is not value for name, value in fields):
            raise ValueError("Retained original context/request/trial/holder identity changed")
        for name, registry, records in registries:
            if vars(module).get(name) is not registry:
                raise ValueError("Original inherited issuance registry replaced")
            for key, value, elements in records:
                if registry.get(key) is not value or (
                    type(value) is tuple
                    and (
                        len(value) != len(elements)
                        or any(a is not b for a, b in zip(value, elements, strict=True))
                    )
                ):
                    raise ValueError("Original inherited issuance/retirement tuple changed")


def _profile_lease_views(parent, profile, *, junctions):
    module = parent.api._seed_init_profiles_api()
    current, expected = _profiles_route(parent)
    if current is not profile or expected is not module:
        raise ValueError("Different actual profile continuation")
    lease = parent.profile_lease
    view, fields = lease.views[int(junctions)]
    for (role, actual), holder, names, target in zip(
        lease.objects, lease.holders, lease.names, fields, strict=True
    ):
        if vars(actual) is not holder:
            raise ValueError("Original source object's attribute dictionary was replaced")
        current_names = tuple(holder)
        if actual is parent.phase.dyna:
            module._check_fields(profile)
        elif actual is parent.cells and junctions:
            child, issuer = module._junctions_route(profile)
            issuer._check_fields(child)
        elif current_names != names:
            raise ValueError("An unowned source field was added, removed or reordered: " + role)
        target.clear()
        target.update(
            (name, holder[name])
            for name in names
            if not (actual is parent.cells and junctions and name in lease.junction_fields)
        )
    view.fields = fields
    return view


def _profile_lease_values(parent, profile, *, junctions):
    view = _profile_lease_views(parent, profile, junctions=junctions)
    projected = previous._project(parent.parent, view.fields)
    buffers = [("Dm_cells", profile.dm)]
    if parent.profile_lease.percent:
        buffers.append(("cell_i", profile.cell_i))

    def observe(value):
        for role, actual in buffers:
            if value is actual:
                return dict(
                    source_owned_buffer=role,
                    dtype=actual.dtype.str,
                    shape=actual.shape,
                    strides=actual.strides,
                    writeable=actual.flags.writeable,
                    pointer=actual.__array_interface__["data"][0],
                )
        if type(value) is dict:
            return {key: observe(item) for key, item in value.items()}
        if type(value) is list:
            return [observe(item) for item in value]
        if type(value) is tuple:
            return tuple(observe(item) for item in value)
        return value

    return previous._scope(parent.parent).snapshot(observe(projected))


def _profile_lease_graph(parent, profile, *, junctions):
    view = _profile_lease_views(parent, profile, junctions=junctions)
    return previous._scope(parent.parent).graph(view, view, parent.profile_lease.tape)


def _capture_profile_lease(parent, profile):
    parent.api._seed_init_profiles_api()
    dyna = parent.assembly.world_transition.api.stages[2]
    origin = dyna._OBJECTS.get(profile.dyna)
    if origin is None or origin.handler is not profile.dyna or origin.phase is not parent.phase:
        raise ValueError("Actual preborn same-parameter handler required")
    percent = any(
        role == "TissuePickerPercent" and any(item.picker is actual for _, item in profile.profiles)
        for role, actual in origin.objects
    )
    objects = list(parent.parent.parent.objects)
    for role, actual in (
        ("cells", parent.cells),
        ("simulator", parent.sim),
        ("handler", profile.dyna),
        ("mesh", parent.mesh),
        ("grid", parent.grid),
    ):
        if not any(item is actual for _, item in objects):
            objects.append((role, actual))
    objects = tuple((role, actual) for role, actual in objects if hasattr(actual, "__dict__"))
    views = []
    for _ in (False, True):
        fields = [{} for _ in objects]
        views.append((SimpleNamespace(objects=objects, fields=fields), fields))
    # Both projections start from the SAME actual sealed pre-profile state.
    # The second is usable only after the typed future junction retirement.
    junction_fields = parent.api._seed_junctions_api().STORES
    lease = SimpleNamespace(
        parent=parent,
        profile=profile,
        origin=origin,
        percent=percent,
        objects=objects,
        holders=tuple(vars(actual) for _, actual in objects),
        names=tuple(tuple(vars(actual)) for _, actual in objects),
        views=tuple(views),
        tape=SimpleNamespace(rng=parent.rng, events=(), draws=(), locals={}),
        junction_fields=junction_fields,
        edges=_profile_ancestor_edges(parent),
    )
    parent.profile_lease = lease
    # No junction source/owner exists yet. Populate the immutable second
    # projection directly from the same holders; use requires the real route.
    for target, holder, names in zip(views[1][1], lease.holders, lease.names, strict=True):
        target.update(
            (name, holder[name])
            for name in names
            if holder is not vars(parent.cells) or name not in junction_fields
        )
    lease.values = (_profile_lease_values(parent, profile, junctions=False), None)
    lease.graphs = (_profile_lease_graph(parent, profile, junctions=False), None)
    # The optional descendant projection is sealed lazily at its real claim,
    # after first checking the current non-junction lease. No parent reset.
    return lease


def _claim_for_seed_profiles(owner, *, expected, transition, entries):
    module = _ready()._seed_init_profiles_api()
    caller = sys._getframe(1)
    with _LOCK:
        parent = _ISSUED.get(owner) if type(owner) is InitCoreOwner else None
        if (
            parent is None
            or parent.trial is not expected
            or caller.f_code is not module.prepare.__code__
            or not module._ACTIVE
            or module._ACTIVE[-1] is not transition
        ):
            raise InitCoreRejected("Actual active profile issuer required", stage="entry")
        if owner in _FORWARDED or hasattr(parent, "profiles"):
            raise InitCoreRejected("Core profile epoch consumed", stage="consumed")
        if (
            parent.active
            or parent.validating
            or parent.invalid
            or parent.owner is not owner
            or transition.driver_frame is not caller
            or transition.parent is not parent
            or type(transition.request) is not module.Request
            or transition.request.core_owner is not owner
            or module._REQUESTS.get(transition.request) is not transition.refs
            or module._CONSUMED.get(transition.request) is not transition
            or module._RETIRED.get(owner) is not transition
            or transition.refs[0] is not parent
            or transition.refs[1] is not expected
            or any(
                getattr(transition, name) is not getattr(parent, name)
                for name in ("phase", "p", "cells", "sim", "grid")
            )
            or transition.dyna is not parent.phase.dyna
            or transition.thread != parent.thread
            or transition.thread != get_ident()
            or entries is not transition.entries
            or tuple(entries) != ("wrapper_guard", "dispatch", "picker_dispatch")
            or any(entries[name] is not getattr(module, "_" + name) for name in entries)
        ):
            parent.invalid = transition.invalid = True
            raise ValueError("Actual same-phase core/profile entry or ancestry changed")
        parent.profiles = transition
        try:
            _FORWARDED[owner] = transition
            _check(parent)
            _complete(parent)
            if (
                parent.trial.identity != _digest(trial_record(parent.trial))
                or parent.trial.cache.identity != _snapshot(parent).identity
            ):
                raise ValueError("Original complete core trial/cache changed before profiles")
            graph = _graph(parent)
            previous._same(graph[0], parent.graph[0])
            if graph[1] != parent.graph[1]:
                raise ValueError("Original complete core reference edges changed")
            _capture_profile_lease(parent, transition)
        except BaseException:
            parent.invalid = transition.invalid = True
            raise
        return parent


def _check_seed_profiles_authority(transition):
    parent = transition.parent
    if (
        _profiles_route(parent)[0] is not transition
        or parent.profile_lease.profile is not transition
    ):
        raise ValueError("Different actual profile continuation/lease")
    lease = parent.profile_lease
    _check_profile_ancestor_edges(lease)
    _profile_ancestor_bindings(parent)
    junctions = hasattr(transition, "junctions")
    if junctions:
        _ready()._seed_init_profiles_api()._junctions_route(transition)
    index = int(junctions)
    _check_profile_lease_projection(parent, transition, index)
    return parent


def _check_profile_lease_projection(parent, profile, index):
    lease = parent.profile_lease
    if index not in (0, 1) or lease.values[index] is None or lease.graphs[index] is None:
        raise ValueError("No sealed actual junction continuation permission")
    if (
        _profile_lease_values(parent, profile, junctions=bool(index)).identity
        != lease.values[index].identity
    ):
        raise ValueError("Profiles changed an immutable inherited value/buffer layout")
    graph = _profile_lease_graph(parent, profile, junctions=bool(index))
    previous._same(graph[0], lease.graphs[index][0])
    if graph[1] != lease.graphs[index][1]:
        raise ValueError("Profiles changed an inherited object/alias/reference edge")


def _claim_profile_junction_permission(profile, junction):
    """One typed handoff selects a new observation projection, never old source data."""
    parent = profile.parent
    module = _ready()._seed_init_profiles_api()
    issuer = _ready()._seed_junctions_api()
    caller = sys._getframe(1)
    if (
        caller.f_code is not module._claim_for_seed_junctions.__code__
        or caller.f_locals.get("transition") is not junction
        or _profiles_route(parent)[0] is not profile
        or module._junctions_route(profile)[0] is not junction
        or not issuer._ACTIVE
        or issuer._ACTIVE[-1] is not junction
        or junction.entered
        or junction.method_returns
        or parent.profile_lease.values[1] is not None
        or parent.profile_lease.graphs[1] is not None
    ):
        raise ValueError("Actual fresh profile/junction transition required")
    lease = parent.profile_lease
    _check_profile_ancestor_edges(lease)
    _profile_ancestor_bindings(parent)
    _check_profile_lease_projection(parent, profile, 0)
    # Both new observations precede the first original junction body/helper.
    # A failed observation leaves the already-consumed parents consumed.
    lease.junction_permission = junction
    values = _profile_lease_values(parent, profile, junctions=True)
    graph = _profile_lease_graph(parent, profile, junctions=True)
    lease.values, lease.graphs = (lease.values[0], values), (lease.graphs[0], graph)


def require_INIT(owner):
    context = _authority(owner)
    raise InitCoreRejected(
        "SEED core is not actual INIT/physics authority",
        stage="INIT_held",
        request=context.request,
        trial=context.trial,
    )
