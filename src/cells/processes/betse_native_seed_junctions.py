"""Held same-phase SEED gap junction and graph-network continuation.

The only parent is an actual completed InitProfiles stage. Four literal caller
statements invoke the original callbacks and actual Cells wrappers; no phase,
profile map, graph inverse or parameter object is supplied or reconstructed.
The native factorized inverse is retained, including its domain and errors.
"""

import ast
import builtins
import copy
import hashlib
import importlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FrameType, FunctionType, MappingProxyType, MethodType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_post_world_operators_source as graph_source
from cells.processes import betse_native_seed_init_core as core
from cells.processes import betse_native_seed_init_profiles as previous
from cells.processes import betse_native_seed_junctions_source as source
from cells.processes import betse_post_cut_mesh_contact_source as vector_source

LAW_ID = "betse_same_profiles_seed_junction_network@1"
RELEASE = "CELLS_NATIVE_SEED_JUNCTIONS_RELEASED"
PARENT_SOURCE_SHA256 = "b7b26b2bc6f8c78ba84bef3f19c44ba4ece4ab5cbfabfe17f4e0e8b85d0beadc"
PARENT_REVIEW_SHA256 = "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d"
COORDINATOR_SOURCE_SHA256 = "06c3bb8cba6b5038671f08a418d190842d146e91a6f9c3e655b11409587026d9"
COORDINATOR_REVIEW_SHA256 = "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d"
PROPOSED_CLAIM = "_claim_for_seed_junctions"
PROPOSED_CHECK = "_check_seed_junctions_authority"
PROPOSED_ROUTER = "_seed_junctions_api"
INIT_CONSUMER_MODULE = "cells.processes.betse_native_init_retained_world"
INIT_CONSUMER_INTERFACE_SHA256 = INIT_CONSUMER_REVIEW_SHA256 = None
INIT_PARENT_REVIEW_SHA256 = INIT_KEY_REVIEW_SHA256 = None
INIT_BINDING_KIND = "exact_retained_INIT_bytes_except_four_validated_backrefs@1"
INIT_BACK_REFERENCE_SLOTS = (
    "PARENT_SOURCE_SHA256",
    "PARENT_REVIEW_SHA256",
    "KEY_SOURCE_SHA256",
    "KEY_REVIEW_SHA256",
)
METHODS = ("redo_gj", "calc_gj_vects", "graphLaplacian")
RETURN_ORDER = ("calc_gj_vects", "redo_gj", "graphLaplacian")
CALLBACK_STATUSES = (
    "Creating gap junction connection network...",
    "Creating cell network Poisson solver...",
)
NUMPY_HELPERS = ("asarray", "ones", "sqrt", "diag", "dot")
OUTPUTS = {
    "redo_gj": ("cell_nn_connected", "num_nn", "average_nn", "gj_default_weights"),
    "calc_gj_vects": (
        "nn_mids",
        "nn_tx",
        "nn_ty",
        "nn_len",
        "nn_edges",
        "cell_nn_tx",
        "cell_nn_ty",
        "cell_to_nn_full",
    ),
    "graphLaplacian": ("lapGJinv", "lapGJ", "geom_weight"),
}
STORES = tuple(n for fields in OUTPUTS.values() for n in fields)
CELL_READS = (
    "cell_i",
    "cell_nn",
    "mem_i",
    "cell_to_mems",
    "nn_i",
    "mem_to_cells",
    "cell_nn_i",
    "mem_mids_flat",
    "cell_centres",
    "mesh",
    "M_sum_mems",
    "mem_sa",
    "mem_vol",
)
MESH_READS = ("vor_edge_len", "tri_edge_len", "delta_tri_0", "delta_tri_0_inv", "vor_sa")
NATIVE_PINS = {
    "betse/science/cells.py": source.CELLS_SHA256,
    "betse/science/simrunner.py": source.RUNNER_SHA256,
}
MAX_WORK = 100000
_WORLD, _PREFIX, _BASE, _CORE, _LITERAL = (
    core.previous,
    core._PREFIX,
    core._BASE,
    core._CORE,
    core._LITERAL,
)
_PARENT_FILE, _SOURCE_FILE = Path(previous.__file__), Path(source.__file__)
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_FORWARDED = WeakKeyDictionary()
_ACTIVE, _FAILED, _LOCK = [], (), RLock()
_LAST_FAILED = None
_PROOFS = (
    source.SeedJunctions.redo_gj,
    vector_source.CellKernel.calc_gj_vects,
    graph_source.PostWorldKernel.graphLaplacian,
    source.SeedJunctionsCallSite.continue_seed,
)


class JunctionsRejected(previous.ProfilesRejected):
    pass


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    profiles_owner: object
    parent_identity: str
    source_identity: str
    flux_operator: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Actual profile ownership cannot be restored")


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
    callbacks_completed: tuple
    method_returns: tuple
    source_completed: bool
    identity: str


def _digest(value):
    return core._digest(value)


def _node(tree, cls, name):
    return core._node(tree, cls, name)


def _body(node):
    rows = list(node.body)
    if (
        rows
        and isinstance(rows[0], ast.Expr)
        and isinstance(rows[0].value, ast.Constant)
        and isinstance(rows[0].value.value, str)
    ):
        rows = rows[1:]
    return ast.dump(ast.Module(body=rows, type_ignores=[]), include_attributes=False)


def _source_nodes():
    native = Path(_PREFIX.aliases.NATIVE)
    trees = {}
    for name, expected in NATIVE_PINS.items():
        path = native / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Exact original source required: " + name)
        trees[name] = ast.parse(path.read_bytes(), filename=str(path))
    repo = _SOURCE_FILE.parents[3]
    for name, expected in source.REUSED_SOURCE_PINS.items():
        path = repo / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Existing literal source changed: " + name)
    proofs = (
        (source, "SeedJunctions"),
        (vector_source, "CellKernel"),
        (graph_source, "PostWorldKernel"),
    )
    nodes = {}
    for name, (module, cls) in zip(METHODS, proofs, strict=True):
        original = _node(trees["betse/science/cells.py"], "Cells", name)
        proof = _node(ast.parse(Path(module.__file__).read_bytes()), cls, name)
        if _body(original) != _body(proof) or [a.arg for a in original.args.args] != [
            a.arg for a in proof.args.args
        ]:
            raise ValueError("Complete original method differs: " + name)
        nodes[name] = original
    caller = _node(trees["betse/science/simrunner.py"], "SimRunner", "seed")
    selected = [n for n in caller.body if n.lineno in (148, 150, 154, 156)]
    call = copy.deepcopy(
        _node(ast.parse(_SOURCE_FILE.read_bytes()), "SeedJunctionsCallSite", "continue_seed")
    )
    if len(selected) != 4 or _body(call) != ast.dump(
        ast.Module(body=selected, type_ignores=[]), include_attributes=False
    ):
        raise ValueError("Exact two callbacks and junction/network calls required")
    call.body, call.lineno, call.end_lineno = copy.deepcopy(selected), 148, 156
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
            / (
                "betse/science/simrunner.py"
                if name == "continue_seed"
                else "betse/science/cells.py"
            )
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
    return dict(
        law_id=LAW_ID,
        native_pins=dict(NATIVE_PINS),
        reused_source_pins=dict(source.REUSED_SOURCE_PINS),
        literal_sha256=hashlib.sha256(_SOURCE_FILE.read_bytes()).hexdigest(),
        bodies={
            n: dict(
                first_line=v.lineno,
                last_line=v.end_lineno,
                ast_sha256=hashlib.sha256(_body(v).encode()).hexdigest(),
            )
            for n, v in _source_nodes().items()
        },
        methods=METHODS,
        method_returns=RETURN_ORDER,
        callbacks=CALLBACK_STATUSES,
        caller_statements=(148, 150, 154, 156),
        outputs=OUTPUTS,
        numpy_helpers=NUMPY_HELPERS,
        additional_helpers=("logs.log_debug",),
        cell_reads=CELL_READS,
        mesh_reads=MESH_READS,
        parameter_reads=("cell_height",),
        profile_reads=("tissue_name_to_profile.items", "profile.is_gj_insular", "cell_target_inds"),
        source_quirks_preserved=(
            "num_nn/average_nn use original cell_nn, not connected map",
            "original empty-list division error",
            "original zero length sentinel -1",
            "original map order and duplicates",
            "existing delta_tri_0_inv factorization; no new inverse or nullspace policy",
        ),
        parent_source_pin=PARENT_SOURCE_SHA256,
        parent_review_pin=PARENT_REVIEW_SHA256,
        coordinator_source_pin=COORDINATOR_SOURCE_SHA256,
        coordinator_review_pin=COORDINATOR_REVIEW_SHA256,
        parent_hooks={
            PROPOSED_CLAIM: (
                "(owner, *, expected: exact retained previous.Trial, transition, entries)"
            ),
            PROPOSED_CHECK: (
                "(transition) -> same factored completed Profiles context; "
                "no stale cache validation"
            ),
        },
        router=PROPOSED_ROUTER,
        entries={
            "wrapper_guard": "(transition, original_assembly, wrapper_frame)",
            "dispatch": (
                "(transition, original_assembly, label, delegate, actual, args, kwargs, full_frame)"
            ),
        },
        immutable_parent_contract=(
            "same actual phase/p/cells/dyna/sim/grid/mesh/mask/callbacks/global MT",
            "same profile objects, target map references, insertion order, arrays and aliases",
            "only listed Cells output fields may change; all other data/reference edges exact",
            "single irreversible epoch; two original callbacks before their corresponding methods",
        ),
        inherited_flux_modes=_WORLD.FLUX_OPERATORS,
        original_flux_numerics_unchanged=True,
        caller_projection=(
            "four original SimRunner statements using actual p/callbacks; no SimRunner authority"
        ),
        stop_before=(
            "optional deform_tools",
            "save_cluster",
            "sim_info_report",
            "progressed_last",
            "INIT",
            "SIM",
        ),
        source_native_or_scientific_release=False,
        physical_admission=False,
    )


def _ready():
    if not all(
        core._pin(v)
        for v in (
            PARENT_SOURCE_SHA256,
            PARENT_REVIEW_SHA256,
            COORDINATOR_SOURCE_SHA256,
            COORDINATOR_REVIEW_SHA256,
        )
    ):
        raise JunctionsRejected(
            "Actual profiles/junction routing remains held", stage="unbound_contract"
        )
    if (
        Path(previous.__file__) != _PARENT_FILE
        or _PARENT_FILE.is_symlink()
        or hashlib.sha256(_PARENT_FILE.read_bytes()).hexdigest() != PARENT_SOURCE_SHA256
    ):
        raise JunctionsRejected("Reviewed profile producer required", stage="producer")
    api = previous._ready()
    path = Path(api.__file__)
    if (
        path.is_symlink()
        or hashlib.sha256(path.read_bytes()).hexdigest() != COORDINATOR_SOURCE_SHA256
    ):
        raise JunctionsRejected("Reviewed coordinator producer required", stage="producer")
    route = vars(api).get(PROPOSED_ROUTER)
    if (
        type(route) is not FunctionType
        or route.__globals__ is not vars(api)
        or route() is not sys.modules[__name__]
    ):
        raise JunctionsRejected("Actual Cells route remains closed", stage="dispatch_held")
    for name in (PROPOSED_CLAIM, PROPOSED_CHECK):
        fn = vars(previous).get(name)
        if type(fn) is not FunctionType or fn.__globals__ is not vars(previous):
            raise JunctionsRejected(
                "Actual profile retirement unavailable", stage="parent_hooks_held"
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


def from_profiles(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise JunctionsRejected("Explicit whole junction/network law required", stage="law")
    _ready()
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant profile declaration")
        if type(owner) is not previous.ProfilesOwner or owner in _RETIRED:
            raise JunctionsRejected("Fresh actual completed profile owner required", stage="owner")
        parent = previous._authority(owner)
        world = parent.parent.parent
        if (
            parent.trial.source_completed is not True
            or world.request.flux_operator not in _WORLD.FLUX_OPERATORS
        ):
            raise JunctionsRejected(
                "Complete same-phase profiles with original flux mode required", stage="parent"
            )
        value = Request(
            owner, parent.trial.identity, _digest(source_plan()), world.request.flux_operator, ""
        )
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (
            parent,
            parent.trial,
            previous._snapshot(parent).identity,
            previous._edges(parent),
            _WORLD._rng(world).identity,
        )
        return value


def _cache(context, value):
    return previous._cache(context.parent, value)


def _values(context, *, stable=False):
    value = previous._values(context.parent)
    if stable:
        context.stable_caller.clear()
        context.stable_caller.update(
            (n, v) for n, v in vars(context.cells).items() if n not in STORES
        )
        value["cells"] = context.stable_caller
    return value


def _snapshot(context):
    return _cache(
        context,
        dict(
            state=_values(context),
            flux_operator=context.request.flux_operator,
            raw_history=context.events,
        ),
    )


def _graph(context, *, stable=False):
    view = context.stable_view if stable else context.graph_view
    if stable:
        context.stable_caller.clear()
        context.stable_caller.update(
            (n, v) for n, v in vars(context.cells).items() if n not in STORES
        )
    view.cells = context.stable_caller if stable else vars(context.cells)
    view.parameters, view.simulator, view.handler = (
        vars(context.p),
        vars(context.sim),
        vars(context.dyna),
    )
    view.mesh, view.grid = vars(context.mesh), vars(context.grid)
    view.profiles = context.profile_views
    return _WORLD._scope(context.world).graph(view, view, context.graph_tape)


def _immutable(context):
    return _cache(context, _values(context, stable=True)).identity, _WORLD._rng(
        context.world
    ).identity


def _check_fields(context):
    _bootstrap(context)
    if (
        type(context.request) is not Request
        or _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.profiles_owner) is not context
        or context.invalid
        or context.thread != get_ident()
        or context.parent is not context.refs[0]
        or context.parent.trial is not context.refs[1]
        or context.phase is not context.parent.phase
        or context.phase.cells is not context.cells
        or context.phase.p is not context.p
        or context.phase.sim is not context.sim
        or context.phase.dyna is not context.dyna
    ):
        raise ValueError("Actual irreversible profile/junction relation changed")
    names = tuple(vars(context.cells))
    expected = [n for n in context.original_names]
    for method in context.entered:
        for name in OUTPUTS[method]:
            if name not in expected:
                expected.append(name)
    added = tuple(n for n in names if n not in context.original_names)
    allowed = tuple(n for n in expected if n not in context.original_names)
    if (
        names[: len(context.original_names)] != context.original_names
        or added != allowed[: len(added)]
    ):
        raise ValueError("Unowned, missing original, or out-of-order Cells output store")
    if len(added) > len(allowed):
        raise ValueError("Undeclared Cells output field")


def _bindings(context):
    _bootstrap(context)
    functions = (
        context.parent_claim,
        context.parent_check,
        *_PROOFS,
        *context.original_methods.values(),
        *context.methods.values(),
        *context.original_wrappers.values(),
        *context.wrappers.values(),
        *context.helper_functions,
        *context.callback_chain,
        _PREFIX._callback_values,
        previous._profile_bindings,
        core._descriptor_helpers,
        core._resolved_bindings,
        _WORLD._scope,
        _WORLD._project,
        _WORLD._rng,
        _init_consumer_binding,
        _init_consumer_api,
        _init_route,
        _claim_for_init_phase,
        _check_init_phase_authority,
        *context.restore_setters,
        *context.restore_getters,
        context.call_tracing,
    )
    return (
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        _FORWARDED,
        _ACTIVE,
        _LOCK,
        INIT_CONSUMER_MODULE,
        INIT_CONSUMER_INTERFACE_SHA256,
        INIT_CONSUMER_REVIEW_SHA256,
        INIT_PARENT_REVIEW_SHA256,
        INIT_KEY_REVIEW_SHA256,
        INIT_BINDING_KIND,
        INIT_BACK_REFERENCE_SLOTS,
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
        context.parent_claim,
        context.parent_check,
        context.entries,
        *(v for pair in context.entries.items() for v in pair),
        *previous._profile_bindings(context.parent),
        *(
            v
            for cls in (
                type(context.phase),
                type(context.cells),
                type(context.p),
                type(context.dyna),
                type(context.sim),
                type(context.mesh),
                type(context.grid),
                type(context.callback),
                context.numpy.ndarray,
            )
            for v in (cls, *_LITERAL._surface(cls))
        ),
        context.numpy,
        *(getattr(context.numpy, n) for n in NUMPY_HELPERS),
        context.native_globals,
        context.native_globals["np"],
        context.native_globals["logs"],
        context.native_globals["logs"].log_debug,
        *(v for fn in functions for v in _WORLD._atoms(fn)),
        *core._resolved_bindings((*context.helper_functions, *context.callback_helpers)),
        *(
            v
            for fn in (*context.methods.values(), *context.wrappers.values())
            for v in (fn.__globals__, *fn.__globals__.values())
        ),
        *(
            getattr(builtins, n)
            for n in ("len", "range", "enumerate", "sum", "int", "object", "vars")
        ),
    )


def _check(context):
    if context.active:
        _guard(context)
    if (
        _ready() is not context.api
        or context.parent_check(context) is not context.parent
        or context.parent.trial is not context.refs[1]
        or context.phase is not context.parent.phase
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.phase.dyna is not context.dyna
        or context.phase.sim is not context.sim
        or context.sim.dyna is not context.dyna
        or context.phase.callbacks is not context.callback
        or context.cells.grid_obj is not context.grid
        or context.cells.mesh is not context.mesh
        or context.world.mask is not context.mask
        or context.world.rng is not context.rng
        or context.world.request.flux_operator != context.request.flux_operator
        or vars(context.caller) != {"_callbacks": context.callback, "_p": context.p}
        or _digest(request_record(context.request)) != context.request.identity
        or _digest(source_plan()) != context.request.source_identity
    ):
        raise ValueError("Actual profile/phase/caller/parameter/world association changed")
    method = context.callback.progressed_next
    if (
        type(method) is not MethodType
        or method.__self__ is not context.callback
        or method.__func__ is not context.callback_chain[0]
    ):
        raise ValueError("Actual original callback changed")
    _WORLD._same(_bindings(context), context.bindings)
    _check_fields(context)
    if _immutable(context) != context.immutable:
        raise ValueError("Junctions changed a profile/map/parameter/field/global-MT value")
    graph = _graph(context, stable=True)
    _WORLD._same(graph[0], context.stable_graph[0])
    if graph[1] != context.stable_graph[1]:
        raise ValueError("Junctions changed a stable map/object/alias edge")


def _namespace(context):
    callbacks = _BASE.image.prefix.previous.previous.caches.previous.callbacks
    context.original_methods = {}
    for name in METHODS:
        wrapper = vars(type(context.cells)).get(name)
        if type(wrapper) is not FunctionType:
            raise ValueError("Actual original Cells wrapper required")
        closure = dict(
            zip(
                wrapper.__code__.co_freevars,
                (c.cell_contents for c in wrapper.__closure__ or ()),
                strict=True,
            )
        )
        delegate = closure.get("delegate")
        original = callbacks._source_function(delegate, "betse/science/cells.py", name, "Cells")
        if (
            original not in tuple(callbacks.simulator._chain(delegate))
            or type(original) is not FunctionType
            or closure.get("context") is not context.assembly
        ):
            raise ValueError("Same original Cells method/assembly required")
        context.original_methods[name] = original
        context.original_wrappers[name], context.native_delegates[name] = wrapper, delegate
    context.native_globals = context.original_methods["redo_gj"].__globals__
    if any(
        fn.__globals__ is not context.native_globals for fn in context.original_methods.values()
    ):
        raise ValueError("Original Cells shared module namespace required")
    context.numpy = context.native_globals["np"]
    helpers = {n: getattr(context.numpy, n) for n in NUMPY_HELPERS}
    helpers["log_debug"] = context.native_globals["logs"].log_debug
    context.helpers = MappingProxyType(helpers)
    descriptors = core._descriptor_helpers(
        (
            (type(context.p), ("cell_height",)),
            (type(context.cells), CELL_READS),
            (type(context.mesh), MESH_READS),
            (type(context.phase), ("p", "cells", "sim", "dyna", "callbacks")),
            (type(context.dyna), ("tissue_name_to_profile", "cell_target_inds")),
            *((type(profile), ("is_gj_insular",)) for _, profile in context.parent.profiles),
        )
    )
    leaves = tuple(helpers.values()) + tuple(
        v
        for fn in helpers.values()
        for attr in ("__wrapped__", "_implementation")
        if (v := getattr(fn, attr, None)) is not None
    )
    context.helper_functions = _WORLD.previous._native_helper_functions((*leaves, *descriptors))
    for name in helpers:

        def observed(*args, _name=name, **kwargs):
            return _helper(context, _name, context.helpers[_name], args, kwargs, sys._getframe())

        context.wrappers[name] = observed
    namespace = dict(
        context.native_globals,
        np=SimpleNamespace(**{n: context.wrappers[n] for n in NUMPY_HELPERS}),
        logs=SimpleNamespace(log_debug=context.wrappers["log_debug"]),
    )
    context.methods = {
        name: FunctionType(fn.__code__, namespace, name, fn.__defaults__, fn.__closure__)
        for name, fn in context.original_methods.items()
    }
    context.methods["continue_seed"] = FunctionType(
        _codes()["continue_seed"], namespace, "continue_seed"
    )
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
        raise ValueError("Actual original callback body required")
    context.callback_helpers = _WORLD.previous._native_helper_functions(context.callback_chain)
    context.allowed_codes = frozenset(
        code
        for fn in (
            *context.methods.values(),
            *context.original_wrappers.values(),
            *context.helper_functions,
            *context.callback_helpers,
        )
        if type(fn) is FunctionType
        for code in _WORLD.previous.previous._code_tree(fn.__code__)
    )
    context.body_codes = {context.methods[n].__code__: n for n in METHODS}
    context.wrapper_codes = {fn.__code__ for fn in context.original_wrappers.values()}
    context.callback_codes = frozenset(fn.__code__ for fn in context.callback_chain)


def _admit_wrapper(context, frame):
    name = frame.f_locals.get("method")
    nested = name == "calc_gj_vects"
    parent = context.frames.get("redo_gj") if nested else context.caller_frame
    expected_name = "redo_gj" if nested else "continue_seed"
    args = (context.phase,) if name == "redo_gj" else (context.p,)
    if (
        name not in METHODS
        or frame.f_back is not parent
        or parent is None
        or parent.f_code is not context.methods[expected_name].__code__
        or frame.f_code is not context.original_wrappers[name].__code__
        or frame.f_locals.get("actual") is not context.cells
        or frame.f_locals.get("context") is not context.assembly
        or frame.f_locals.get("name") != "Cells"
        or frame.f_locals.get("delegate") is not context.native_delegates[name]
        or tuple(id(x) for x in frame.f_locals.get("args", ())) != tuple(id(x) for x in args)
        or frame.f_locals.get("kwargs")
        or name in context.entered
    ):
        _reject(context, "Actual same-Cells wrapper receiver/arguments/ancestry required")
    expected_entered = METHODS[: METHODS.index(name)]
    expected_callbacks = (0, 1) if name == "graphLaplacian" else (0,)
    if (
        tuple(context.entered) != expected_entered
        or tuple(context.callbacks_completed) != expected_callbacks
    ):
        _reject(context, "Original callback/redo/nested vectors/network order required")
    if name == "graphLaplacian" and tuple(n for n, _ in context.method_returns) != RETURN_ORDER[:2]:
        _reject(context, "redo_gj must complete before graph network")
    context.wrapper_claims[id(frame)] = (frame, name)


def _dispatch(context, original, label, delegate, actual, args, kwargs, dispatch_frame):
    _guard(context)
    native = None if type(dispatch_frame) is not FrameType else dispatch_frame.f_back
    wrapper = None if native is None else native.f_back
    claim = None if wrapper is None else context.wrapper_claims.get(id(wrapper))
    name = None if claim is None else claim[1]
    expected = (context.phase,) if name == "redo_gj" else (context.p,)
    if (
        claim is None
        or claim[0] is not wrapper
        or original is not context.assembly
        or actual is not context.cells
        or label != "Cells." + name
        or delegate is not context.native_delegates[name]
        or type(args) is not tuple
        or len(args) != len(expected)
        or any(a is not b for a, b in zip(args, expected, strict=True))
        or kwargs
        or native.f_code is not context.native_call_code
    ):
        _reject(context, "Original full-frame Cells dispatch required")
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
            _reject(context, "Original Cells methods return None")
        _record(context, name + ".completed", dict(vars(actual)))
        _check(context)
        return result
    finally:
        context.dispatch_frames.pop(name, None)
        context.stage = "redo_gj" if name == "calc_gj_vects" else "caller"


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
    frame, role, name = row["frame"], row["role"], row["name"]
    if (
        frame.f_back is not row["parent"]
        or frame.f_code is not row["code"]
        or frame.f_globals is not row["globals"]
    ):
        _reject(context, "Actual frame ancestry changed")
    local = frame.f_locals
    if role == "caller":
        if local.get("self") is not context.caller or local.get("phase") is not context.phase:
            _reject(context, "Actual caller receiver/phase changed")
    elif role == "wrapper":
        _admit_wrapper(context, frame)
    elif role == "body":
        arg, expected = ("phase", context.phase) if name == "redo_gj" else ("p", context.p)
        if local.get("self") is not context.cells or local.get(arg) is not expected:
            _reject(context, "Actual Cells body receiver/argument changed")
    elif role == "callback":
        receiver, status = _PREFIX._callback_values(frame)
        if (
            receiver is not context.callback
            or type(status) is not str
            or status != CALLBACK_STATUSES[row["epoch"]]
            or status is not row["status"]
            or frame.f_code is not context.callback_chain[row["callback_index"]].__code__
        ):
            _reject(context, "Actual callback receiver/status/chain changed")
    elif role == "helper" and context.active_helper is not row["helper"]:
        _reject(context, "Actual helper ownership changed")


def _admit_frame(context, frame):
    selected = _frame_role(context, frame)
    if selected is None:
        if (
            frame.f_code.co_filename.startswith(str(_PREFIX.aliases.NATIVE) + os.sep)
            and frame.f_code not in context.allowed_codes
        ):
            _reject(context, "Unbound native helper or later SEED stage entry")
        return None
    _guard(context)
    old = context.admitted.get(id(frame))
    if old is not None:
        if old["frame"] is not frame or old["returned"]:
            _reject(context, "Admitted frame cannot be reused")
        _validate_frame(context, old)
        _check(context)
        return old
    role, name = selected
    row = dict(
        frame=frame,
        role=role,
        name=name,
        code=frame.f_code,
        globals=frame.f_globals,
        parent=frame.f_back,
        call_layers=set(),
        return_layers=set(),
        returned=False,
        raw_return_seen=False,
        raw_return=None,
        source_error=None,
    )
    context.admitted[id(frame)] = row
    if role == "caller":
        if context.caller_frame is not None or frame.f_back is not context.driver_frame:
            _reject(context, "Single original caller entry required")
        context.caller_frame = frame
    elif role == "wrapper":
        _admit_wrapper(context, frame)
    elif role == "body":
        if (
            frame.f_back is not context.dispatch_frames.get(name)
            or name in context.frames
            or frame.f_globals is not context.methods[name].__globals__
        ):
            _reject(context, "Single original Cells body dispatch required")
        context.frames[name] = frame
    elif role == "callback":
        if frame.f_back is context.caller_frame:
            epoch = len(context.callback_frames)
            if epoch >= 2 or tuple(context.callbacks_completed) != tuple(range(epoch)):
                _reject(context, "Exactly two sequential callback epochs required")
            wanted = () if epoch == 0 else RETURN_ORDER[:2]
            if tuple(n for n, _ in context.method_returns) != wanted:
                _reject(context, "Callback must follow its original source predecessor")
            context.callback_frames.append([])
            context.callback_returned.append([])
        else:
            epoch = len(context.callback_frames) - 1
            if epoch < 0:
                _reject(context, "Callback outer frame missing")
        frames = context.callback_frames[epoch]
        at = len(frames)
        parent = context.caller_frame if at == 0 else frames[-1]
        if (
            at >= len(context.callback_chain)
            or frame.f_back is not parent
            or context.callback_returned[epoch]
        ):
            _reject(context, "Original full callback frame order required")
        fn = context.callback_chain[at]
        receiver, status = _PREFIX._callback_values(frame)
        if (
            frame.f_code is not fn.__code__
            or frame.f_globals is not fn.__globals__
            or receiver is not context.callback
            or type(status) is not str
            or status != CALLBACK_STATUSES[epoch]
            or (at and status is not context.callback_statuses[epoch])
        ):
            _reject(context, "Actual callback receiver/status/native chain required")
        if not at:
            context.callback_statuses.append(status)
        frames.append(frame)
        row.update(epoch=epoch, callback_index=at, status=status)
    else:
        helper = context.active_helper
        if frame.f_back is not context.helper_frame or frame.f_globals is not helper[1].__globals__:
            _reject(context, "Actual helper delegate frame required")
        row["helper"] = helper
    _validate_frame(context, row)
    _check(context)
    return row


def _observe(context, frame, event, arg, *, layer="trace"):
    if event == "call":
        row = _admit_frame(context, frame)
        if row is not None:
            if layer in row["call_layers"]:
                _reject(context, "Duplicate hook call for activation")
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
        try:
            context.source_exceptions.append((row["name"], arg[1], frame.f_lasti))
        except BaseException as error:
            _capture_failure(context, error, "exception_history", context.last_source_exception)
    elif event == "return":
        context.last_source_return = (frame, arg, row["source_error"])
        if not row["raw_return_seen"]:
            row["raw_return"], row["raw_return_seen"] = arg, True
            if row["role"] == "helper":
                context.last_helper_return = (row["name"], arg, row["source_error"])
            try:
                context.raw_returns.append((row["name"], arg))
            except BaseException as error:
                _capture_failure(context, error, "return_history", context.last_source_return)
        elif row["raw_return"] is not arg:
            _reject(context, "Trace/profile raw return identity changed")
        row["return_layers"].add(layer)
        if row["return_layers"] == {"trace", "profile"}:
            row["returned"] = True
            if row["role"] == "body":
                context.frames.pop(row["name"], None)
            elif row["role"] == "callback":
                epoch, at = row["epoch"], row["callback_index"]
                expected = len(context.callback_chain) - 1 - len(context.callback_returned[epoch])
                if (
                    len(context.callback_frames[epoch]) != len(context.callback_chain)
                    or at != expected
                ):
                    if row["source_error"] is None and context.primary is None:
                        _reject(context, "Incomplete callback chain return")
                else:
                    context.callback_returned[epoch].append(at)
                if row["source_error"] is not None and context.callback_exception is None:
                    context.callback_exception = row["source_error"]
                if at == 0 and context.callback_exception is None:
                    context.callbacks_completed.append(epoch)
    if event in ("exception", "return"):
        try:
            context.locals[row["name"] or row["role"]] = dict(frame.f_locals)
        except BaseException as error:
            _capture_failure(context, error, "raw_locals_" + event, frame)
    return row


def _raw_partial(context):
    return dict(
        phase=context.phase,
        parameters=context.p,
        caller=context.cells,
        handler=context.dyna,
        simulator=context.sim,
        mesh=context.mesh,
        grid=context.grid,
        mask=context.mask,
        raw_fields=dict(vars(context.cells)),
        locals=context.locals,
        source_error=context.primary,
        source_exceptions=context.source_exceptions,
        last_source_exception=context.last_source_exception,
        last_source_return=context.last_source_return,
        last_helper=context.last_helper,
        last_helper_return=context.last_helper_return,
        helper_inputs=context.helper_inputs,
        helper_returns=context.helper_returns,
        method_returns=context.method_returns,
        raw_returns=context.raw_returns,
        events=context.events,
        admitted_frames=context.admitted,
        callback_frames=context.callback_frames,
        capture_errors=context.capture_errors,
        cleanup_errors=context.cleanup_errors,
    )


def _complete(context):
    if (
        tuple(context.entered) != METHODS
        or tuple(n for n, _ in context.method_returns) != RETURN_ORDER
        or any(v is not None for _, v in context.method_returns)
        or tuple(context.callbacks_completed) != (0, 1)
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
        or any(name not in vars(context.cells) for name in STORES)
    ):
        raise ValueError("Whole original callbacks/redo/vectors/network completion required")


def trial_record(value):
    return dict(
        request_identity=value.request_identity,
        parent_identity=value.parent_identity,
        flux_operator=value.flux_operator,
        before=value.before.identity,
        cache=value.cache.identity,
        stages=tuple((n, c.identity) for n, c in value.stages),
        stream_before=value.stream_before.identity,
        stream_after=value.stream_after.identity,
        callbacks_completed=value.callbacks_completed,
        method_returns=value.method_returns,
        source_completed=value.source_completed,
    )


def _context(request, refs, api):
    parent, phase = refs[0], refs[0].phase
    world = parent.parent.parent
    return SimpleNamespace(
        request=request,
        refs=refs,
        parent=parent,
        api=api,
        world=world,
        phase=phase,
        cells=phase.cells,
        p=phase.p,
        dyna=phase.dyna,
        sim=phase.sim,
        grid=parent.grid,
        mesh=world.mesh,
        mask=world.mask,
        rng=world.rng,
        callback=phase.callbacks,
        assembly=parent.assembly,
        native_call_code=world.parent.prefix.native_call_code,
        original_names=tuple(vars(phase.cells)),
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
        callback_frames=[],
        callback_returned=[],
        callback_statuses=[],
        callback_exception=None,
        callbacks_completed=[],
        required_hooks=(sys.getprofile(), sys.gettrace()),
        restore_setters=(sys.setprofile, sys.settrace),
        restore_getters=(sys.getprofile, sys.gettrace),
        graph_view=SimpleNamespace(),
        stable_view=SimpleNamespace(),
        stable_caller={},
        profile_views=tuple((vars(p), vars(p.picker)) for _, p in parent.profiles),
        graph_tape=SimpleNamespace(rng=world.rng, events=(), draws=(), locals={}),
    )


def prepare(request, *, enabled=False):
    global _LAST_FAILED
    api = _ready()
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise JunctionsRejected("Actual junction/network remains held", stage="release")
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant junction claim")
        if type(request) is not Request or request not in _REQUESTS:
            raise JunctionsRejected(
                "Actual process-local profile request required", stage="request"
            )
        if request in _CONSUMED or request.profiles_owner in _RETIRED:
            raise JunctionsRejected("Profile epoch consumed", stage="consumed")
        refs = _REQUESTS[request]
        parent = previous._authority(request.profiles_owner)
        graph = previous._edges(parent)
        if (
            parent is not refs[0]
            or parent.trial is not refs[1]
            or previous._snapshot(parent).identity != refs[2]
            or graph[1] != refs[3][1]
            or _WORLD._rng(parent.parent.parent).identity != refs[4]
        ):
            raise JunctionsRejected("Original completed profile parent changed", stage="parent")
        _WORLD._same(graph[0], refs[3][0])
        context = _context(request, refs, api)
        context.driver_frame = sys._getframe()
        _CONSUMED[request] = _RETIRED[request.profiles_owner] = context
        _ACTIVE.append(context)
        try:
            context.parent_claim, context.parent_check = (
                vars(previous)[PROPOSED_CLAIM],
                vars(previous)[PROPOSED_CHECK],
            )
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
                request.profiles_owner,
                expected=refs[1],
                transition=context,
                entries=context.entries,
            )
            _namespace(context)
            context.caller = SimpleNamespace(_callbacks=context.callback, _p=context.p)
            context.bindings = _bindings(context)
            context.immutable, context.stable_graph = (
                _immutable(context),
                _graph(context, stable=True),
            )
            context.before, context.stream_before = _snapshot(context), _WORLD._rng(context.world)
            _check(context)
            with _account(context):
                context.stage = "caller"
                context.methods["continue_seed"](context.caller, context.phase)
            _guard(context)
            _complete(context)
            _check(context)
            context.cache, context.stream_after, context.graph = (
                _snapshot(context),
                _WORLD._rng(context.world),
                _graph(context),
            )
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
                tuple(context.callbacks_completed),
                tuple(context.method_returns),
                True,
                "",
            )
            context.trial = replace(trial, identity=_digest(trial_record(trial)))
            _caller_restore(context)
            if not context.hooks_safe or context.cleanup_errors:
                raise ValueError("Final observer identities not safely restored")
            context.active = False
            owner = object.__new__(JunctionsOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            selected = context.primary if context.primary is not None else error
            context.failure_error, _LAST_FAILED = selected, context
            try:
                _failure(context, selected)
            except BaseException as secondary:
                if secondary is not selected:
                    context.failure_entry_error, context.metadata_stopped = secondary, True
            # Keep a protected call boundary even if a prior hook rejects this helper.
            try:
                _caller_restore(context)
            except BaseException as secondary:
                context.cleanup_errors += (("caller_restore_entry", secondary, None),)
                for i in (1, 0):
                    try:
                        context.restore_setters[i](context.required_hooks[i])
                    except BaseException as cleanup:
                        context.cleanup_errors += (("direct_restore", cleanup, i),)
            raise selected  # noqa: B904
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True


class JunctionsOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use actual completed-profile continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No restored or supplied junction/network owner")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not JunctionsOwner or owner not in _ISSUED:
        raise JunctionsRejected("Actual issued junction child required", stage="owner")
    context = _ISSUED[owner]
    if owner in _FORWARDED or hasattr(context, "init_transition"):
        raise JunctionsRejected(
            "SEED endpoint was irreversibly consumed by INIT",
            stage="forwarded",
            trial=context.trial,
            partial=context,
        )
    if context.active or context.invalid or context.validating:
        raise JunctionsRejected("Junction epoch unavailable", stage="owner")
    context.validating = True
    try:
        _check(context)
        _complete(context)
        graph = _graph(context)
        _WORLD._same(graph[0], context.graph[0])
        if (
            graph[1] != context.graph[1]
            or context.trial.source_completed is not True
            or context.trial.identity != _digest(trial_record(context.trial))
            or context.trial.cache.identity != _snapshot(context).identity
        ):
            raise ValueError("Actual junction/network/alias evidence changed")
    except BaseException as error:
        _failure(context, error)
    finally:
        context.validating = False
    return context


def _init_consumer_binding(payload):
    api = _ready()
    scope = dict(
        vars(api),
        HELPER_BACK_REFERENCE_SLOTS=INIT_BACK_REFERENCE_SLOTS,
        HELPER_BINDING_KIND=INIT_BINDING_KIND,
    )
    return FunctionType(api._helper_binding.__code__, scope)(payload)


def _init_consumer_api():
    api = _ready()
    if not all(
        core._pin(value)
        for value in (
            INIT_CONSUMER_INTERFACE_SHA256,
            INIT_CONSUMER_REVIEW_SHA256,
            INIT_PARENT_REVIEW_SHA256,
            INIT_KEY_REVIEW_SHA256,
        )
    ):
        raise JunctionsRejected(
            "Reviewed actual INIT continuation remains unbound", stage="INIT_held"
        )
    path = Path(__file__).parents[3] / ("src/" + INIT_CONSUMER_MODULE.replace(".", "/") + ".py")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Original INIT consumer source required")
    raw = path.read_bytes()
    identity, backrefs = _init_consumer_binding(raw)
    if (
        identity != INIT_CONSUMER_INTERFACE_SHA256
        or tuple(name for name, _ in backrefs) != INIT_BACK_REFERENCE_SLOTS
    ):
        raise ValueError("Exact INIT consumer bytes outside four back-reference literals changed")
    refs = dict(backrefs)
    if (
        refs["PARENT_SOURCE_SHA256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        or refs["PARENT_REVIEW_SHA256"] != INIT_PARENT_REVIEW_SHA256
        or refs["KEY_REVIEW_SHA256"] != INIT_KEY_REVIEW_SHA256
        or not core._pin(refs["KEY_SOURCE_SHA256"])
    ):
        raise ValueError("Actual full endpoint/Key source/review back-reference changed")
    module = importlib.import_module(INIT_CONSUMER_MODULE)
    if (
        sys.modules.get(INIT_CONSUMER_MODULE) is not module
        or Path(module.__file__).resolve() != path
        or path.read_bytes() != raw
        or any(getattr(module, name) != value for name, value in backrefs)
        or module.previous is not sys.modules[__name__]
    ):
        raise ValueError("Original actual INIT consumer namespace changed")
    api._source_interface(
        module,
        raw,
        path,
        (
            "prepare",
            "_ready",
            "_capture_seed_lease",
            "_check_seed_lease",
        ),
    )
    key = module._ready()
    if hashlib.sha256(Path(key.__file__).read_bytes()).hexdigest() != refs["KEY_SOURCE_SHA256"]:
        raise ValueError("Actual full reviewed INIT parameter producer changed")
    return module


def _init_route(parent):
    module = _init_consumer_api()
    child, owner = getattr(parent, "init_transition", None), getattr(parent, "owner", None)
    if (
        child is None
        or owner is None
        or _ISSUED.get(owner) is not parent
        or _FORWARDED.get(owner) is not child
        or parent.active
        or parent.invalid
        or child.invalid
        or type(child.request) is not module.Request
        or child.request.seed_owner is not owner
        or module._REQUESTS.get(child.request) is not child.refs
        or module._CONSUMED.get(child.request) is not child
        or module._RETIRED.get(owner) is not child
        or child.parent is not parent
        or child.refs[0] is not parent
        or child.refs[1] is not parent.trial
        or child.p is not parent.p
        or child.cells is not parent.cells
        or child.callback is not parent.phase.callbacks
        or child.refs[4] is not parent.world.world
        or child.seed_claim is not child.refs[4].claim
        or child.refs[5] is not child.seed_claim
        or child.refs[6] is not child.refs[4].parameter_record
        or child.seed_owner is not child.refs[4].request.world_parameters
        or child.thread != parent.thread
        or child.thread != get_ident()
    ):
        raise ValueError(
            "Actual SEED/INIT issuance, retirement or same-p/Cells relationship changed"
        )
    return child, module


def _claim_for_init_phase(owner, *, expected, transition):
    module = _init_consumer_api()
    caller = sys._getframe(1)
    with _LOCK:
        parent = _ISSUED.get(owner) if type(owner) is JunctionsOwner else None
        if (
            parent is None
            or parent.trial is not expected
            or caller.f_code is not module.prepare.__code__
            or not module._ACTIVE
            or module._ACTIVE[-1] is not transition
        ):
            raise JunctionsRejected(
                "Actual active retained-world INIT issuer required", stage="entry"
            )
        if owner in _FORWARDED or hasattr(parent, "init_transition"):
            raise JunctionsRejected("SEED-to-INIT endpoint epoch consumed", stage="consumed")
        if (
            parent.active
            or parent.invalid
            or parent.validating
            or parent.owner is not owner
            or transition.driver_frame is not caller
            or transition.parent is not parent
            or transition.claim is not None
            or transition.parameter_record is not None
            or type(transition.request) is not module.Request
            or transition.request.seed_owner is not owner
            or module._REQUESTS.get(transition.request) is not transition.refs
            or module._CONSUMED.get(transition.request) is not transition
            or module._RETIRED.get(owner) is not transition
            or transition.refs[0] is not parent
            or transition.refs[1] is not expected
            or transition.p is not parent.p
            or transition.cells is not parent.cells
            or transition.callback is not parent.phase.callbacks
            or transition.thread != parent.thread
            or transition.thread != get_ident()
        ):
            parent.invalid = transition.invalid = True
            raise ValueError("Original SEED endpoint/INIT claim ancestry changed")
        parent.init_transition = transition
        try:
            _FORWARDED[owner] = transition
            _check(parent)
            _complete(parent)
            if (
                parent.trial.identity != _digest(trial_record(parent.trial))
                or parent.trial.cache.identity != _snapshot(parent).identity
            ):
                raise ValueError("Original completed SEED endpoint changed before INIT")
            graph = _graph(parent)
            _WORLD._same(graph[0], parent.graph[0])
            if graph[1] != parent.graph[1] or _init_route(parent)[0] is not transition:
                raise ValueError("Original endpoint graph or retirement changed")
            module._capture_seed_lease(transition)
        except BaseException:
            parent.invalid = transition.invalid = True
            raise
        return parent


def _check_init_phase_authority(transition, *, parameter_claim, parameter_record):
    parent = transition.parent
    child, module = _init_route(parent)
    if (
        child is not transition
        or parameter_claim is not transition.claim
        or parameter_record is not transition.parameter_record
    ):
        raise ValueError("Different actual INIT parameter transition/record")
    module._check_seed_lease(transition)
    if parameter_claim is None:
        if parameter_record is not None or transition.phase is not None:
            raise ValueError("No phase/closed record may appear before its real parameter claim")
    elif parameter_record is None:
        if (
            type(parameter_claim) is not getattr(transition.key, module.PARAMETER_CLAIM)
            or parameter_claim.parameters is not transition.p
        ):
            raise ValueError("Actual active same-p INIT claim required")
        parameter_claim.check()
    elif (
        getattr(transition.key, module.PARAMETER_CHECK)(
            parameter_claim, seed_claim=transition.seed_claim, original_owner=transition.seed_owner
        )
        is not parameter_record
    ):
        raise ValueError("Exact successful closed INIT parameter record required")
    return parent


def require_later_seed(owner):
    context = _authority(owner)
    raise JunctionsRejected(
        "Deformation/save/INIT remains separate and held",
        stage="later_seed_held",
        request=context.request,
        trial=context.trial,
    )


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
            ValueError("Active outer/junction hook identity changed"),
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
        raise JunctionsRejected("Active same-thread junction claim required", stage=context.stage)


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = JunctionsRejected(
            reason, stage=context.stage, request=context.request, partial=context
        )
    raise context.entry_error


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


def _bootstrap(context):
    function, code, namespace = context.checker
    if (
        context.api._independent_atoms is not function
        or function.__code__ is not code
        or function.__globals__ is not namespace
    ):
        raise ValueError("Independent junction helper checker changed")
    for name, helper, atoms in context.metadata_helpers:
        if globals().get(name) is not helper:
            raise ValueError("Junction metadata helper replaced: " + name)
        current = function(helper)
        if len(current) != len(atoms) or any(
            a is not b for a, b in zip(current, atoms, strict=True)
        ):
            raise ValueError("Junction metadata helper code/default/closure changed: " + name)


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
            if (
                context.primary is None
                and context.observation_error is None
                and context.entry_error is None
            ):
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


def _wrapper_guard(context, original, wrapper):
    _guard(context)
    claim = context.wrapper_claims.get(id(wrapper))
    if claim is None or claim[0] is not wrapper or original is not context.assembly:
        _reject(context, "Unclaimed original Simulator wrapper")
    _check(context)


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
                selected.seed_junctions_partial = context
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


def _caller_restore(context):
    context.hooks_safe = False
    try:
        _restore(context)
    except BaseException as error:
        context.cleanup_errors += (("restore_entry_or_return", error, None),)
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
    if not context.hooks_safe:
        context.invalid = True
