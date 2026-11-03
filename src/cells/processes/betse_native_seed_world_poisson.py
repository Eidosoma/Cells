"""Prepared Poisson continuation of an actually issued SEED geometry owner.

The original value solver and both original progress callbacks are retained.
The explicit disabled variant omits only the flux solve and stores None. The
original variant retains the unchanged scaled operator/default pinv, including
its known unqualified flux numerics. Neither variant admits a physical solver,
an INIT phase or an ordinary checkpoint. The six final ordinary make_world
stores are retained in the same claim; no gap-junction operator is evaluated.

Geometry retirement/routing and the coordinator's descendant-field permission
must be adopted separately. Unset producer pins and missing hooks refuse before
owner acquisition. No saved buffer, normalized field or supplied phase is an
executable parent.
"""

import ast
import builtins
import copy
import hashlib
import os
import sys
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FrameType, FunctionType, MappingProxyType, MethodType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_make_world_tail_source as tail
from cells.processes import betse_native_seed_world_geometry as previous
from cells.processes import betse_native_single_cell_poisson_observation as observation
from cells.processes import betse_native_single_cell_poisson_source as source

LAW_ID = "betse_same_seed_actual_environment_Poisson_modes@1"
RELEASE = "CELLS_NATIVE_SEED_WORLD_POISSON_RELEASED"
FLUX_OPERATORS = ("original", "disabled")
PARENT_SOURCE_SHA256 = PARENT_REVIEW_SHA256 = None
PARENT_MODULE = "cells.processes.betse_native_seed_world_geometry"
LITERAL_SHA256 = "418f3c47ee93b606554c2dce7ceeba500f6731e96b7a2e8f04c65fc28be58141"
OBSERVATION_SHA256 = "5d770e303966342898ff4c6d420997041934ccc873a0f62c3277fb2628b3dafb"
TAIL_SHA256 = "4f7b4e776a1408e978967824cae9ed1402906c1a41da3ee1591522ea4273856a"
PROPOSED_CLAIM = "_claim_for_world_poisson"
PROPOSED_CHECK = "_check_world_poisson_authority"
PROPOSED_ROUTER = "_world_seed_poisson_api"
METHODS = ("environment_voltage", "environment_current")
FIELDS = ("lapENVinv", "lapENV_P_inv")
TAIL_METHODS = (
    "clear_lapGJinv",
    "clear_lapGJ",
    "clear_M_sum_mem_to_ecm",
    "clear_gradMem",
    "coerce_cell_i",
    "default_gj_weights",
)
TAIL_FIELDS = ("lapGJinv", "lapGJ", "M_sum_mem_to_ecm", "gradMem", "cell_i", "gj_default_weights")
STAGES = (*METHODS, *TAIL_METHODS)
NEW_FIELDS = (*FIELDS, *TAIL_FIELDS[:4], TAIL_FIELDS[5])
CALLBACK_STATUSES = (
    "Creating environmental voltage Poisson solver...",
    "Creating environmental current Poisson solver...",
)
CALLER_LINES = ((499, 500, 503, 504), (507, 508, 511, 512))
MAX_WORK = previous.MAX_WORK
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_ACTIVE, _LOCK = [], RLock()
_BASE = previous._BASE
_PREFIX = _BASE.image.prefix
_CORE = _BASE.image.images.core
_LITERAL = _PREFIX.literal
_LITERAL_OPERATOR = source.FiniteDiffPoisson.makeLaplacian
_CALLER_PROOFS = tuple(getattr(source.CellsPoisson, name) for name in METHODS)
_TAIL_PROOFS = tuple(getattr(tail.CellsWorldTail, name) for name in TAIL_METHODS)
_PARENT_FILE, _SOURCE_FILE, _OBSERVATION_FILE = (
    Path(module.__file__) for module in (previous, source, observation)
)
_TAIL_FILE = Path(tail.__file__)


class PoissonRejected(previous.GeometryRejected):
    pass


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    geometry_owner: object
    parent_identity: str
    source_identity: str
    flux_operator: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("An actual process-local SEED geometry owner is required")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    flux_operator: str
    flux_solve_attempted: bool
    flux_solve_returned: bool
    flux_inverse_absent: bool
    before: object
    cache: object
    stages: tuple
    callback_statuses: tuple
    boundary_dictionaries: tuple
    tail_stores: tuple
    stream_before: object
    stream_after: object
    work: tuple
    warnings: tuple
    source_completed: bool
    failure_stage: str | None
    source_failure: str | None
    capture_failure: str | None
    identity: str


def _policy(flux_operator):
    if type(flux_operator) is not str or flux_operator not in FLUX_OPERATORS:
        raise PoissonRejected("Explicit original or disabled flux operator required", stage="mode")
    return flux_operator


def _digest(value):
    return previous._digest(value)


def _same(actual, expected):
    return previous._same(actual, expected)


def _atoms(value):
    return previous._atoms(value)


def _statement_body(node):
    """Pure AST metadata; do not enter a phase implementation for inspection."""
    body = node.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _source_nodes():
    root = _PREFIX.aliases.NATIVE
    native = root / "betse/science/cells.py"
    grid = root / "betse/science/math/finitediff.py"
    payloads = []
    for path, expected in (
        (native, source.CELLS_SHA256),
        (grid, source.GRID_SHA256),
        (_SOURCE_FILE, LITERAL_SHA256),
        (_OBSERVATION_FILE, OBSERVATION_SHA256),
        (_TAIL_FILE, TAIL_SHA256),
    ):
        raw = path.read_bytes()
        if path.is_symlink() or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Pinned original Poisson/observation producer changed: " + str(path))
        payloads.append(raw)
    trees = tuple(ast.parse(raw) for raw in payloads[:3])

    def method(tree, owner, name):
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
        return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)

    caller = method(trees[0], "Cells", "make_world")
    blocks = tuple(tuple(n for n in caller.body if n.lineno in lines) for lines in CALLER_LINES)
    for name, block, status in zip(METHODS, blocks, CALLBACK_STATUSES, strict=True):
        literal = method(trees[2], "CellsPoisson", name)
        if len(block) != 3 or ast.dump(
            ast.Module(body=list(block[1:]), type_ignores=[])
        ) != ast.dump(ast.Module(body=list(literal.body), type_ignores=[])):
            raise ValueError("Original selected callback/boundary/assignment order changed")
        callback = block[0]
        if ast.unparse(callback) != "phase.callbacks.progressed_next(status=" + repr(status) + ")":
            raise ValueError("Original progress callback status or receiver changed")
    original = method(trees[1], "FiniteDiffSolver", "makeLaplacian")
    literal = method(trees[2], "FiniteDiffPoisson", "makeLaplacian")
    if ast.dump(original.args) != ast.dump(literal.args) or ast.dump(
        ast.Module(body=_statement_body(original), type_ignores=[])
    ) != ast.dump(ast.Module(body=_statement_body(literal), type_ignores=[])):
        raise ValueError("Literal default-boundary scaled Laplacian/pinv body changed")
    tail_tree = ast.parse(payloads[4])
    stores = tuple(n for n in caller.body if n.lineno in tail.STORE_LINES)
    if len(stores) != 6 or tail.STORE_NAMES != TAIL_FIELDS:
        raise ValueError("Original six-store world tail changed")
    for name, store in zip(TAIL_METHODS, stores, strict=True):
        literal = method(tail_tree, "CellsWorldTail", name)
        if ast.dump(ast.Module(body=[store], type_ignores=[])) != ast.dump(
            ast.Module(body=literal.body, type_ignores=[])
        ):
            raise ValueError("Original world-tail store or helper changed")
    return native, blocks, stores


def _caller_code(stage, flux_operator):
    """Compile/extract a pinned statement slice; never exec a native module."""
    _policy(flux_operator)
    if stage not in STAGES:
        raise ValueError("Unknown original Poisson stage")
    native, blocks, stores = _source_nodes()
    body = copy.deepcopy(
        list(blocks[METHODS.index(stage)])
        if stage in METHODS
        else [stores[TAIL_METHODS.index(stage)]]
    )
    if stage == METHODS[1] and flux_operator == "disabled":
        # The callback and original flux dictionary remain exact. No zero,
        # projected, reconstructed or replacement flux matrix is constructed.
        body[-1] = ast.copy_location(
            ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()), attr=FIELDS[1], ctx=ast.Store()
                    )
                ],
                value=ast.Constant(value=None),
            ),
            body[-1],
        )
    node = ast.FunctionDef(
        name=stage,
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self"), ast.arg(arg="phase")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=body,
        decorator_list=[],
        lineno=body[0].lineno,
        col_offset=0,
        end_lineno=body[-1].end_lineno,
        end_col_offset=body[-1].end_col_offset,
    )
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    compiled = compile(module, str(native), "exec", dont_inherit=True)
    return next(
        value for value in compiled.co_consts if type(value) is CodeType and value.co_name == stage
    )


def source_plan(*, flux_operator="original"):
    _policy(flux_operator)
    _source_nodes()
    return dict(
        law=LAW_ID,
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        flux_operator=flux_operator,
        parent=PARENT_MODULE,
        parent_source_pin=PARENT_SOURCE_SHA256,
        parent_review_pin=PARENT_REVIEW_SHA256,
        literal_sha256=LITERAL_SHA256,
        observation_sha256=OBSERVATION_SHA256,
        tail_literal_sha256=TAIL_SHA256,
        original_cells=source.CELLS_SHA256,
        original_grid=source.GRID_SHA256,
        caller_lines=CALLER_LINES,
        callback_statuses=CALLBACK_STATUSES,
        stages=STAGES,
        caller_fields=NEW_FIELDS,
        replaced_field="cell_i: exact returned asarray; original list/alias retained",
        tail_store_lines=tail.STORE_LINES,
        tail_stores=TAIL_FIELDS,
        value_solve="original scaled A and unchanged default np.linalg.pinv",
        flux_solve="same original operator" if flux_operator == "original" else "not called",
        disabled_flux_inverse="exact None; no replacement array",
        disabled_keeps_flux_boundary_dictionary=True,
        same_actual_phase_caller_p_grid_mesh_image_global_MT=True,
        geometry_hooks={
            PROPOSED_CLAIM: "(owner, *, expected, transition, entries)",
            PROPOSED_CHECK: "(transition) -> original factored parent",
        },
        grid_dispatch=(
            "entries['Grid.makeLaplacian'](transition, original, grid, args, kwargs, wrapper)"
        ),
        coordinator_router=PROPOSED_ROUTER,
        requires_descendant_field_permission=True,
        source_native_reference_or_scientific_release=False,
        operator_numerical_or_physical_admission=False,
        known_original_flux_issue_not_repaired=True,
        capacity=observation.specification(),
        stop_before=("gap-junction operator", "INIT", "checkpoint"),
        complete_selected_make_world_store_boundary=True,
    )


def _ready():
    if not all(
        type(v) is str and len(v) == 64 and all(c in "0123456789abcdef" for c in v)
        for v in (PARENT_SOURCE_SHA256, PARENT_REVIEW_SHA256)
    ):
        raise PoissonRejected("Geometry/Poisson adoption held", stage="unbound_contract")
    if (
        Path(previous.__file__) != _PARENT_FILE
        or _PARENT_FILE.is_symlink()
        or (hashlib.sha256(_PARENT_FILE.read_bytes()).hexdigest() != PARENT_SOURCE_SHA256)
    ):
        raise PoissonRejected("Reviewed genuine geometry producer required", stage="producer")
    api = previous._ready()
    loader = getattr(api, PROPOSED_ROUTER, None)
    if type(loader) is not FunctionType or loader() is not sys.modules.get(__name__):
        raise PoissonRejected("Original same-grid Poisson route unavailable", stage="dispatch_held")
    for name in (PROPOSED_CLAIM, PROPOSED_CHECK):
        function = getattr(previous, name, None)
        if type(function) is not FunctionType or function.__globals__ is not vars(previous):
            raise PoissonRejected(
                "Actual geometry retirement hooks unavailable", stage="parent_hooks_held"
            )
    _source_nodes()
    return api


def request_record(value):
    return dict(
        law=LAW_ID,
        parent=value.parent_identity,
        source=value.source_identity,
        flux_operator=value.flux_operator,
    )


def from_geometry(owner, *, law_id, flux_operator):
    _policy(flux_operator)
    if type(law_id) is not str or law_id != LAW_ID:
        raise PoissonRejected("Explicit same-SEED Poisson law required", stage="law")
    if _ACTIVE:
        _reject(_ACTIVE[-1], None, "Reentrant Poisson request")
    _ready()
    if type(owner) is not previous.GeometryOwner or owner in _RETIRED:
        raise PoissonRejected("Fresh issued geometry owner required", stage="owner")
    parent = previous._authority(owner)
    if any(name in vars(parent.cells) for name in NEW_FIELDS):
        raise PoissonRejected("Geometry already contains Poisson assignments", stage="owner")
    value = Request(
        owner,
        parent.trial.identity,
        _digest(source_plan(flux_operator=flux_operator)),
        flux_operator,
        "",
    )
    value = replace(value, identity=_digest(request_record(value)))
    _REQUESTS[value] = (parent, parent.trial, previous._epoch(parent))
    return value


def _attempt(context, name, frame, layer):
    return previous._attempt(context, name, frame, layer)


def _reject(context, row, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = PoissonRejected(
            reason,
            stage=context.stage,
            request=context.request,
            trial=context.trial,
            partial=context,
        )
    if row is not None:
        row["state"] = "rejected"
    raise context.entry_error


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.observation_error is not None:
        raise _LITERAL._CaptureStop() from context.observation_error
    if (
        context.invalid
        or not context.active
        or context.thread != get_ident()
        or (not _ACTIVE or _ACTIVE[-1] is not context)
    ):
        _reject(context, None, "Actual active Poisson epoch required")


def _capture_failure(context, error, origin, raw):
    if context.observation_error is None:
        context.observation_error = error
    context.capture_errors += ((origin, error, raw),)


def _bootstrap(context):
    function, code, namespace = context.checker
    if (
        context.api._independent_atoms is not function
        or function.__code__ is not code
        or (function.__globals__ is not namespace)
    ):
        raise ValueError("Original independent Poisson metadata checker changed")
    for name, helper, atoms in context.metadata_helpers:
        if globals().get(name) is not helper:
            raise ValueError("Original Poisson helper replaced: " + name)
        _same(function(helper), atoms)


def _roles(context):
    roles = {}

    def put(stage, role, value):
        name = stage + "." + role
        if name in roles and roles[name] is not value:
            raise ValueError("Poisson helper/input/return identity changed: " + name)
        roles[name] = value

    for stage, name, value in context.helper_results:
        if name not in ("zeros", "pinv"):
            raise ValueError("Unknown retained Poisson helper")
        put(stage, "Z" if name == "zeros" else "P", value)
    for stage, name, value in context.helper_inputs:
        if name != "pinv":
            raise ValueError("Unknown retained Poisson input")
        put(stage, "A", value)
    for stage, pair in context.results:
        if type(pair) is not tuple or len(pair) != 2:
            raise ValueError("Original Laplacian must return its complete A/P pair")
        put(stage, "A", pair[0])
        put(stage, "P", pair[1])
    if any(name not in observation.ROLE_NAMES for name in roles):
        raise ValueError("Unknown Poisson role")
    if context.request.flux_operator == "disabled" and any(
        name.startswith(METHODS[1] + ".") for name in roles
    ):
        raise ValueError("Disabled flux mode acquired an operator array")
    return {name: roles[name] for name in observation.ROLE_NAMES if name in roles}


def _scope(context):
    return observation.Scope(roles=_roles(context))


def _rng(context):
    return _PREFIX._rng_state(context)


def _project(context, value):
    return _LITERAL._project(context.parent.projector, value)


def _snapshot(context):
    return _scope(context).snapshot(
        dict(
            caller=_project(context, vars(context.cells)),
            grid=_project(context, vars(context.grid)),
            results=context.results,
            helpers=context.helper_results,
            inputs=context.helper_inputs,
            tail_helpers=context.tail_results,
            tail_inputs=context.tail_inputs,
            tail_stores=context.tail_stores,
            original_cell_i=context.original_cell_i,
            flux_operator=context.request.flux_operator,
        )
    )


def _bind_holder_views(context):
    """Persistent baseline views, with original holder identities kept separately."""
    parent = context.parent
    if len(parent.objects) != len(parent.holders):
        raise ValueError("Original geometry object/holder roster changed")
    links = []
    for pair, holder in zip(parent.objects, parent.holders, strict=True):
        if type(pair) is not tuple or len(pair) != 2 or vars(pair[1]) is not holder:
            raise ValueError("Original geometry holder is not its actual object dictionary")
        projected = context.stable_view.caller if pair[1] is context.cells else holder
        links.append((pair, holder, projected))
    context.holder_links = tuple(links)
    context.baseline_holders = tuple(projected for _, _, projected in links)


def _holder_views(context):
    parent = context.parent
    if (
        parent.objects is not context.parent_objects
        or parent.holders is not context.parent_holders
        or len(parent.objects) != len(context.holder_links)
        or len(parent.holders) != len(context.holder_links)
    ):
        raise ValueError("Original geometry object/holder registry changed")
    for pair, holder, (original_pair, original_holder, projected) in zip(
        parent.objects, parent.holders, context.holder_links, strict=True
    ):
        if (
            pair is not original_pair
            or holder is not original_holder
            or vars(pair[1]) is not holder
            or projected is not (context.stable_view.caller if pair[1] is context.cells else holder)
        ):
            raise ValueError("Original geometry holder/reference identity changed")
    return context.baseline_holders


def _graph(context, *, baseline=False):
    holders = _holder_views(context)
    view = context.stable_view if baseline else context.final_view
    view.caller.clear()
    view.caller.update(
        (name, value)
        for name, value in vars(context.cells).items()
        if not baseline or name not in NEW_FIELDS
    )
    if baseline:
        view.caller["cell_i"] = context.original_cell_i
    view.grid = vars(context.grid)
    view.issued_roots = context.parent.projector.objects
    view.helper_buffers = context.parent.helper_views
    view.objects = context.parent.objects
    view.holders = holders if baseline else context.parent.holders
    view.original_cell_i = context.original_cell_i
    view.tail_inputs = () if baseline else context.tail_inputs
    view.tail_results = () if baseline else context.tail_results
    view.tail_stores = () if baseline else context.tail_stores
    view.operator_roots.clear()
    if not baseline:
        view.operator_roots.update(_roles(context))
    return _scope(context).graph(view, view, context.stable_tape)


def _immutable(context):
    caller = {k: v for k, v in vars(context.cells).items() if k not in NEW_FIELDS}
    caller["cell_i"] = context.original_cell_i
    values = dict(
        caller=_project(context, caller),
        grid=_project(context, vars(context.grid)),
        original_cell_i=context.original_cell_i,
    )
    return _CORE.caches.snapshot(values).identity, _graph(context, baseline=True)


def _epoch(context):
    return _snapshot(context).identity, _graph(context), _rng(context).identity


def _same_epoch(context, old):
    current = _epoch(context)
    _same(current[1][0], old[1][0])
    if current[0] != old[0] or current[1][1] != old[1][1] or current[2] != old[2]:
        raise ValueError("Observer changed actual Poisson data/reference/global-MT state")


def _check_fields(context):
    """Registry-only descendant permission for future geometry/WPC hooks."""
    _bootstrap(context)
    if (
        _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.geometry_owner) is not context
        or context.invalid
    ):
        raise ValueError("Actual irreversible geometry-to-Poisson registry changed")
    names = tuple(vars(context.cells))
    added = names[len(context.original_names) :]
    allowed = (
        *FIELDS[: context.assignment_allowed],
        *TAIL_FIELDS[: min(context.tail_allowed, 4)],
        *((TAIL_FIELDS[5],) if context.tail_allowed == 6 else ()),
    )
    if names != (*context.original_names, *allowed[: len(added)]) or len(added) > len(allowed):
        raise ValueError("Unowned/out-of-order inverse field assignment")
    for index, name in enumerate(added[:2]):
        if index == 1 and context.request.flux_operator == "disabled":
            if vars(context.cells)[name] is not None:
                raise ValueError("Disabled flux inverse must be exactly None")
        else:
            pairs = [pair for stage, pair in context.results if stage == METHODS[index]]
            if len(pairs) != 1 or vars(context.cells)[name] is not pairs[0][1]:
                raise ValueError("Caller assignment lost the actual returned inverse")
    for name in added[2:6]:
        if vars(context.cells)[name] is not None:
            raise ValueError("Original world-tail clear store changed")
    if context.cells.all_points_cell_i is not context.original_all_points_cell_i:
        raise ValueError("Original all_points_cell_i list alias replaced")
    if context.cells.cell_i is not context.original_cell_i:
        results = [value for name, value in context.tail_results if name == "asarray"]
        if context.tail_allowed < 5 or len(results) != 1 or context.cells.cell_i is not results[0]:
            raise ValueError("cell_i must retain the exact original asarray result")
    if "gj_default_weights" in added:
        results = [value for name, value in context.tail_results if name == "ones"]
        if len(results) != 1 or context.cells.gj_default_weights is not results[0]:
            raise ValueError("Default gap-junction weights lost the actual ones result")
    return names


def _bindings(context):
    _bootstrap(context)
    functions = (
        context.parent_claim,
        context.parent_check,
        previous._authority,
        previous._check_fields,
        previous._native_helper_functions,
        _PREFIX._account.__wrapped__,
        _BASE._recover,
        _LITERAL_OPERATOR,
        *_CALLER_PROOFS,
        *_TAIL_PROOFS,
        context.original_operator,
        context.zeros,
        context.pinv,
        context.asarray,
        context.ones,
        *context.callback_chain,
        *context.callback_helpers,
        _CORE.caches.snapshot,
        _CORE.caches.validate,
        observation.Scope.__init__,
        observation.Scope.snapshot,
        observation.Scope.graph,
        observation.Scope.layout,
        observation.specification,
        observation._clone,
        observation._namespace,
        observation._defaults,
        ast.parse,
        ast.dump,
        ast.fix_missing_locations,
        builtins.compile,
        copy.deepcopy,
        hashlib.sha256,
        sys._getframe,
        _statement_body,
        previous.previous._ObserverSystem.__init__,
        previous.previous._ObserverSystem.setprofile,
        previous.previous._ObserverSystem.settrace,
        previous.previous._protocol_event,
        _PREFIX._callback_values,
        _PREFIX._callback_receiver,
    )
    return (
        LAW_ID,
        RELEASE,
        FLUX_OPERATORS,
        PARENT_SOURCE_SHA256,
        PARENT_REVIEW_SHA256,
        LITERAL_SHA256,
        OBSERVATION_SHA256,
        TAIL_SHA256,
        METHODS,
        FIELDS,
        STAGES,
        NEW_FIELDS,
        TAIL_METHODS,
        TAIL_FIELDS,
        CALLBACK_STATUSES,
        CALLER_LINES,
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        _ACTIVE,
        _LOCK,
        previous,
        source,
        tail,
        observation,
        context.api,
        context.parent_claim,
        context.parent_check,
        context.parent.forbidden_callback_codes,
        *context.parent.forbidden_callback_codes,
        context.callback_codes,
        *context.callback_codes,
        context.forbidden_callback_codes,
        *context.forbidden_callback_codes,
        context.entries,
        *(atom for pair in context.entries.items() for atom in pair),
        type(context.cells),
        *_LITERAL._surface(type(context.cells)),
        type(context.grid),
        *_LITERAL._surface(type(context.grid)),
        type(context.p),
        *_LITERAL._surface(type(context.p)),
        context.original_operator.__globals__,
        context.original_operator.__globals__["np"],
        context.numpy,
        context.numpy.linalg,
        context.numpy.zeros,
        context.numpy.linalg.pinv,
        context.numpy.asarray,
        context.numpy.ones,
        *_LITERAL._surface(observation.Scope),
        *_LITERAL._surface(_ObserverSystem),
        observation.MAX_MATRIX_SIDE,
        observation.MAX_OPERATOR_ELEMENTS,
        observation.MAX_OPERATOR_ARRAYS,
        observation.ROLE_NAMES,
        _CORE.caches.MAX_ARRAY_ELEMENTS,
        _CORE.caches.MAX_TREE_NODES,
        _CORE.caches.MAX_TREE_DEPTH,
        *(atom for fn in functions for atom in _atoms(fn)),
        *(
            atom
            for fn in (
                *context.methods.values(),
                context.operator,
                context.operator.__globals__["np"].zeros,
                context.operator.__globals__["np"].linalg.pinv,
                context.tail_namespace["np"].asarray,
                context.tail_namespace["np"].ones,
            )
            for atom in (fn.__globals__, *fn.__globals__.values(), *_atoms(fn))
        ),
    )


def _check(context):
    _bootstrap(context)
    if context.active:
        _guard(context)
    if (
        _ready() is not context.api
        or context.parent_check(context) is not context.parent
        or context.parent.trial is not context.refs[1]
        or context.request.parent_identity != context.refs[1].identity
        or context.phase is not context.parent.phase
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.cells.grid_obj is not context.grid
        or context.cells.mesh is not context.mesh
        or context.mask is not context.parent.mask
        or context.rng is not context.parent.rng
        or context.parent.grid is not context.grid
        or context.world is not context.parent.prefix.parent.world_transition
        or context.world.claim is not context.claim
        or context.world.parameter_record is not context.closed_record
        or context.closed_record is None
        or context.world.active
        or context.world.invalid
        or context.parent.projector.objects is not context.projector_objects
        or context.parent.objects is not context.parent_objects
        or context.parent.holders is not context.parent_holders
        or _digest(request_record(context.request)) != context.request.identity
        or _digest(source_plan(flux_operator=context.request.flux_operator))
        != context.request.source_identity
    ):
        raise ValueError("Actual closed SEED claim/phase/caller/p/grid/mesh/image lineage changed")
    _check_fields(context)
    _same(
        tuple(atom for pair in context.parent.projector.objects for atom in pair),
        context.projector_atoms,
    )
    callback = context.phase.callbacks.progressed_next
    if (
        type(callback) is not MethodType
        or callback.__self__ is not context.callback
        or (callback.__func__ is not context.callback_chain[0])
    ):
        raise ValueError("Actual phase callback receiver or method changed")
    _same(_bindings(context), context.bindings)
    if _digest(context.original_operator.__defaults__) != context.defaults:
        raise ValueError("Original Laplacian defaults changed")
    current = _immutable(context)
    _same(current[1][0], context.immutable[1][0])
    if current[0] != context.immutable[0] or current[1][1] != context.immutable[1][1]:
        raise ValueError("Pre-Poisson caller/grid values or reference edges changed")
    if _rng(context).identity != context.refs[1].stream_after.identity:
        raise ValueError("Poisson must retain the same global MT state without a draw")
    for stage, cache, roots in context.completed_outputs:
        current_roles = tuple(
            (name, value) for name, value in _roles(context).items() if name.startswith(stage + ".")
        )
        _same(tuple(v for _, v in current_roles), tuple(v for _, v in roots))
        if tuple(n for n, _ in current_roles) != tuple(n for n, _ in roots) or (
            _scope(context).snapshot(dict(current_roles)).identity != cache.identity
        ):
            raise ValueError("Completed operator buffers changed")


def _namespace(context):
    callbacks = _BASE.image.prefix.previous.previous.caches.previous.callbacks
    original = context.parent.grid_original_type.makeLaplacian
    checked = callbacks._source_function(
        original, "betse/science/math/finitediff.py", "makeLaplacian", "FiniteDiffSolver"
    )
    if checked is not original or type(original) is not FunctionType:
        raise ValueError("Exact original grid operator body required")
    context.original_operator = original
    context.numpy = original.__globals__["np"]
    if context.numpy is not source.np:
        raise ValueError("Original grid and literal NumPy producers differ")
    context.zeros, context.pinv = context.numpy.zeros, context.numpy.linalg.pinv
    context.asarray, context.ones = context.numpy.asarray, context.numpy.ones
    context.defaults = _digest(original.__defaults__)
    if context.defaults != _digest(_LITERAL_OPERATOR.__defaults__):
        raise ValueError("Original unchanged default boundary dictionary required")

    def zeros(*args, **kwargs):
        return _helper(context, "zeros", context.zeros, args, kwargs, sys._getframe())

    def pinv(*args, **kwargs):
        return _helper(context, "pinv", context.pinv, args, kwargs, sys._getframe())

    def asarray(*args, **kwargs):
        return _tail_helper(context, "asarray", context.asarray, args, kwargs, sys._getframe())

    def ones(*args, **kwargs):
        return _tail_helper(context, "ones", context.ones, args, kwargs, sys._getframe())

    namespace = dict(
        original.__globals__, np=SimpleNamespace(zeros=zeros, linalg=SimpleNamespace(pinv=pinv))
    )
    context.operator = FunctionType(
        original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__
    )
    context.tail_namespace = dict(
        context.parent.native_namespace, np=SimpleNamespace(asarray=asarray, ones=ones)
    )
    context.methods = {
        name: FunctionType(
            _caller_code(name, context.request.flux_operator),
            context.tail_namespace
            if name in TAIL_METHODS
            else dict(context.parent.native_namespace),
            name,
        )
        for name in STAGES
    }
    method = context.phase.callbacks.progressed_next
    if type(method) is not MethodType or method.__self__ is not context.phase.callbacks:
        raise ValueError("Actual bound phase progress callback required")
    context.callback = method.__self__
    chain = tuple(callbacks.simulator._chain(method.__func__))
    if not chain or any(type(fn) is not FunctionType for fn in chain):
        raise ValueError("Actual progressed_next wrapper/body chain required")
    body = chain[-1]
    path = Path(body.__code__.co_filename)
    if (
        not path.is_relative_to(_PREFIX.aliases.NATIVE)
        or callbacks._source_function(
            method.__func__,
            str(path.relative_to(_PREFIX.aliases.NATIVE)),
            "progressed_next",
            body.__qualname__.split(".")[-2],
        )
        is not body
    ):
        raise ValueError("Exact original progressed_next source body required")
    _select_callbacks(context, chain)
    context.callback_helpers = previous._native_helper_functions(context.callback_chain)
    context.body_codes = {fn.__code__: name for name, fn in context.methods.items()}
    context.body_codes[context.operator.__code__] = "Grid.makeLaplacian"
    context.body_codes[zeros.__code__] = "zeros_wrapper"
    context.body_codes[pinv.__code__] = "pinv_wrapper"
    context.body_codes[asarray.__code__] = "asarray_wrapper"
    context.body_codes[ones.__code__] = "ones_wrapper"
    context.body_codes[vars(type(context.grid))["makeLaplacian"].__code__] = "grid_wrapper"
    for fn in context.callback_helpers:
        context.body_codes.setdefault(fn.__code__, "callback_helper")
    context.generator_sites = MappingProxyType({})


def _select_callbacks(context, authenticated_chain):
    """Called only after original-source/receiver authentication in _namespace."""
    if (
        type(authenticated_chain) is not tuple
        or not authenticated_chain
        or any(type(fn) is not FunctionType for fn in authenticated_chain)
    ):
        raise ValueError("Authenticated actual callback chain required")
    context.callback_chain = authenticated_chain
    context.callback_codes = frozenset(fn.__code__ for fn in authenticated_chain)
    context.forbidden_callback_codes = frozenset(
        context.parent.forbidden_callback_codes
    ).difference(context.callback_codes)


def _callback_enter(context, frame, row):
    index = METHODS.index(context.stage)
    occurrence = context.callback_occurrence
    if occurrence is None or occurrence["stage"] != context.stage:
        occurrence = dict(
            stage=context.stage, frames=[], returned=(), status=None, source_error=None
        )
        context.callback_occurrence = occurrence
    at = len(occurrence["frames"])
    receiver, status = _PREFIX._callback_values(frame)
    parent = context.caller_frame if at == 0 else occurrence["frames"][-1]
    if (
        at >= len(context.callback_chain)
        or frame.f_code is not context.callback_chain[at].__code__
        or frame.f_back is not parent
        or receiver is not context.callback
        or type(status) is not str
        or status != CALLBACK_STATUSES[index]
        or (at == 0 and len(context.callbacks_completed) != index)
    ):
        _reject(context, row, "Actual ordered progress callback frame/status required")
    if at and status is not occurrence["status"]:
        _reject(context, row, "Callback wrapper replaced the status object")
    occurrence["status"] = status
    occurrence["frames"].append(frame)
    row["callback_index"] = at


def _callback_return(context, frame, error):
    row = context.admitted[id(frame)]
    occurrence = context.callback_occurrence
    index = row["callback_index"]
    if (
        len(occurrence["frames"]) != len(context.callback_chain)
        or occurrence["frames"][index] is not frame
        or index != len(context.callback_chain) - 1 - len(occurrence["returned"])
    ):
        raise ValueError("Actual callback return order changed")
    occurrence["returned"] += (index,)
    if error is not None and occurrence["source_error"] is None:
        occurrence["source_error"] = error
    if index == 0 and occurrence["source_error"] is None:
        context.callbacks_completed.append(occurrence["status"])
        if context.stage == METHODS[1] and context.request.flux_operator == "disabled":
            context.assignment_allowed = 2


def _admit(context, frame):
    prior = context.admitted.get(id(frame))
    if prior is not None and prior["frame"] is frame:
        _guard(context)
        if prior["state"] != "admitted":
            _reject(context, prior, "Repeated completed Poisson source entry")
        return
    name = context.body_codes.get(frame.f_code, "callback")
    row = _attempt(context, name, frame, "native_body")
    context.admitted[id(frame)] = row
    _guard(context)
    parent = frame.f_back
    if frame.f_code in context.callback_codes:
        _callback_enter(context, frame, row)
        valid = True
    elif name in STAGES:
        valid = (
            context.stage == name
            and parent is context.driver_frame
            and context.executing
            and name not in context.entered_stages
            and frame.f_globals is context.methods[name].__globals__
            and frame.f_locals.get("self") is context.cells
            and frame.f_locals.get("phase") is context.phase
        )
        if valid:
            context.entered_stages.append(name)
            context.caller_frame = frame
    elif name == "grid_wrapper":
        valid = (
            parent is context.caller_frame
            and frame.f_locals.get("actual") is context.grid
            and frame.f_locals.get("context") is context.parent
            and frame.f_locals.get("name") == "makeLaplacian"
            and frame.f_locals.get("delegate") is context.original_operator
        )
    elif name == "Grid.makeLaplacian":
        valid = (
            parent is context.grid_delegate_frame
            and context.grid_busy
            and frame.f_locals.get("self") is context.grid
            and frame.f_globals is context.operator.__globals__
        )
        if valid:
            context.operator_frame = frame
    elif name in ("zeros_wrapper", "pinv_wrapper"):
        valid = parent is context.operator_frame and context.grid_busy
    elif name in ("asarray_wrapper", "ones_wrapper"):
        valid = (
            parent is context.caller_frame and context.stage in TAIL_METHODS and context.executing
        )
    else:
        parent_row = None if parent is None else context.admitted.get(id(parent))
        valid = (
            parent_row is not None
            and parent_row["frame"] is parent
            and parent_row["state"] == "admitted"
            and parent_row["body_started"]
        )
    if not valid:
        _reject(context, row, "Unclaimed/reentrant same-grid Poisson entry: " + name)
    row["state"] = "admitted"


def _capture(context, frame, event):
    context.last_raw_frame = frame
    context.locals[(context.stage, frame.f_code.co_qualname, event)] = dict(frame.f_locals)
    row = context.admitted.get(id(frame))
    if row is None or row["frame"] is not frame:
        raise ValueError("Raw observation lacks admitted source frame")
    if event == "exception":
        error = sys.exc_info()[1]
        if error is not None and not isinstance(error, _LITERAL._CaptureStop):
            row["source_error"] = error
    if frame is context.caller_frame and context.stage in METHODS and "bdic" in frame.f_locals:
        value = frame.f_locals["bdic"]
        expected = "value" if context.stage == METHODS[0] else "flux"
        if (
            type(value) is not dict
            or tuple(value) != ("N", "S", "E", "W")
            or value != dict.fromkeys(value, expected)
        ):
            _reject(context, row, "Original boundary dictionary changed")
        context.boundaries[context.stage] = value


class _ObserverSystem(previous.previous._ObserverSystem):
    def _gate(self, frame, event):
        if event == "call" and frame.f_code not in self.context.body_codes:
            if frame.f_code.co_filename.startswith(self.context.native_root):
                _reject(self.context, None, "Unbound native callback/operator body")

    def _result(self, frame, event, result):
        if event == "return" and frame.f_code in self.context.body_codes:
            # Actual Python returns precede inherited return observers. A
            # return event alone is not completion: unwind errors stay raw.
            self.context.last_observed_return = (frame, result)
            if frame is self.context.operator_frame:
                raw = (self.context.stage, result, frame)
                self.context.last_raw_operator_return = raw
                try:
                    self.context.raw_operator_returns.append(raw)
                except BaseException as error:
                    # This callback also observes exception unwinds. Keep the
                    # immediate raw return first and defer observation refusal:
                    # raising here would replace the actual source exception.
                    if self.context.observation_error is None:
                        self.context.observation_error = error
                    try:
                        self.context.capture_errors += (("raw_operator_return", error, raw),)
                    except BaseException as secondary:
                        self.context.capture_reporting_errors += (
                            ("raw_operator_return", secondary, error, raw),
                        )


def _observer_bindings(context=None):
    context = _ACTIVE[-1] if context is None else context
    _bootstrap(context)
    return (
        context.observer_scope,
        context.observer_function,
        context.observer_system,
        context.observer_system.context,
        context.observer_system.setters,
        context.observer_system.getters,
        context.observer_system.codes,
        *(atom for pair in context.observer_scope.items() for atom in pair),
        *(
            atom
            for fn in (
                _admit,
                _capture,
                _guard,
                _check,
                _epoch,
                _same_epoch,
                _capture_failure,
                _reject,
                _callback_return,
            )
            for atom in _atoms(fn)
        ),
    )


@contextmanager
def _account(context):
    namespace = dict(vars(_PREFIX))
    for name in (
        "_observer_bindings",
        "_admit",
        "_capture",
        "_guard",
        "_check",
        "_epoch",
        "_same_epoch",
        "_capture_failure",
        "_reject",
        "_callback_return",
    ):
        namespace[name] = globals()[name]
    context.observer_system = _ObserverSystem(context)
    namespace["sys"] = context.observer_system
    original = _PREFIX._account.__wrapped__
    function = FunctionType(
        original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__
    )
    context.observer_scope, context.observer_function = namespace, function
    context.observer_bindings = _observer_bindings(context)
    with contextmanager(function)(context):
        yield


def _record(context, name, raw):
    old = None
    try:
        old = _epoch(context)
        context.events.append((context.stage, name, raw))
    except BaseException as error:
        _capture_failure(context, error, name, raw)
    if old is not None:
        try:
            _same_epoch(context, old)
        except BaseException as error:
            _capture_failure(context, error, name + "_state", raw)
    _guard(context)


def _helper(context, name, delegate, args, kwargs, wrapper):
    _guard(context)
    _check(context)
    expected = ("zeros", "pinv")
    seen = [n for stage, n in context.helper_attempts if stage == context.stage]
    row = context.admitted.get(id(wrapper))
    if (
        type(wrapper) is not FrameType
        or sys._getframe(1) is not wrapper
        or row is None
        or row["frame"] is not wrapper
        or row["state"] != "admitted"
        or not row["body_started"]
        or not context.grid_busy
        or context.helper_busy
        or wrapper.f_back is not context.operator_frame
        or len(seen) >= 2
        or name != expected[len(seen)]
        or kwargs
        or delegate is not (context.zeros if name == "zeros" else context.pinv)
    ):
        _reject(context, None, "Raw/reentrant Poisson numerical helper")
    if name == "zeros":
        shape = context.grid.cents_shape
        side = shape[0] * shape[1]
        if args != ((side, side),):
            _reject(context, None, "Original zeros allocation shape changed")
    elif len(args) != 1 or args[0] is not context.operator_frame.f_locals.get("A"):
        _reject(context, None, "pinv did not receive the actual scaled operator")
    try:
        context.helper_attempts.append((context.stage, name))
    except BaseException as error:
        _capture_failure(context, error, "helper_attempt", (name, args, kwargs))
        _guard(context)
    context.helper_busy = True
    try:
        if name == "pinv":
            context.last_helper_input = (context.stage, name, args[0])
            try:
                context.helper_inputs.append(context.last_helper_input)
            except BaseException as error:
                _capture_failure(context, error, "pinv_input", context.last_helper_input)
                _guard(context)
        _record(context, name + "_enter", (args, kwargs))
        try:
            result = delegate(*args, **kwargs)
        except BaseException as error:
            if context.primary is None:
                context.primary = error
            raise
        context.last_helper_return = (context.stage, name, result)
        try:
            context.helper_results.append(context.last_helper_return)
        except BaseException as error:
            _capture_failure(context, error, name + "_retain", result)
        _record(context, name + "_return", result)
        return result
    finally:
        context.helper_busy = False


def _tail_helper(context, name, delegate, args, kwargs, wrapper):
    """Two original data conversions, not an operator or a substitute caller."""
    _guard(context)
    _check(context)
    expected = "asarray" if context.stage == TAIL_METHODS[4] else "ones"
    required_stage = TAIL_METHODS[4] if name == "asarray" else TAIL_METHODS[5]
    row = context.admitted.get(id(wrapper))
    if (
        type(wrapper) is not FrameType
        or sys._getframe(1) is not wrapper
        or row is None
        or row["frame"] is not wrapper
        or row["state"] != "admitted"
        or not row["body_started"]
        or name not in ("asarray", "ones")
        or context.stage != required_stage
        or name != expected
        or not context.executing
        or context.helper_busy
        or wrapper.f_back is not context.caller_frame
        or kwargs
        or len(args) != 1
        or name in context.tail_attempts
        or delegate is not (context.asarray if name == "asarray" else context.ones)
    ):
        _reject(context, None, "Unclaimed/reentrant final world data helper")
    if name == "asarray":
        if (
            args[0] is not context.original_cell_i
            or context.cells.cell_i is not context.original_cell_i
        ):
            _reject(context, None, "Original cell_i list must reach asarray unchanged")
    elif type(args[0]) is not int or args[0] != len(context.cells.mem_i):
        _reject(context, None, "Original membrane count must reach ones unchanged")
    context.last_tail_input = (name, args, kwargs)
    try:
        context.tail_inputs.append(context.last_tail_input)
        context.tail_attempts.append(name)
    except BaseException as error:
        _capture_failure(context, error, "tail_input", context.last_tail_input)
        _guard(context)
    context.helper_busy = True
    try:
        _record(context, name + "_enter", context.last_tail_input)
        try:
            result = delegate(*args, **kwargs)
        except BaseException as error:
            if context.primary is None:
                context.primary = error
            raise
        context.last_tail_return = (name, result)
        try:
            context.tail_results.append(context.last_tail_return)
        except BaseException as error:
            _capture_failure(context, error, "tail_return", context.last_tail_return)
        _record(context, name + "_return", result)
        return result
    finally:
        context.helper_busy = False


def _grid_call(context, original, grid, args, kwargs, wrapper):
    """Future geometry route; the actual grid wrapper is never replaced."""
    _guard(context)
    _check(context)
    row = context.admitted.get(id(wrapper))
    index = METHODS.index(context.stage)
    selected = METHODS if context.request.flux_operator == "original" else METHODS[:1]
    expected = "value" if index == 0 else "flux"
    if (
        context.grid_busy
        or not context.executing
        or context.stage not in selected
        or original is not context.original_operator
        or grid is not context.grid
        or args
        or row is None
        or row["frame"] is not wrapper
        or row["state"] != "admitted"
        or not row["body_started"]
        or wrapper.f_back is not context.caller_frame
        or len(context.attempted) != index
        or len(context.callbacks_completed) != index + 1
        or tuple(kwargs) != ("bound",)
        or type(kwargs["bound"]) is not dict
        or tuple(kwargs["bound"]) != ("N", "S", "E", "W")
        or kwargs["bound"] != dict.fromkeys(("N", "S", "E", "W"), expected)
    ):
        _reject(context, row, "Original callback/value/flux same-grid dispatch order required")
    try:
        context.attempted.append(context.stage)
    except BaseException as error:
        _capture_failure(context, error, "operator_attempt", (grid, args, kwargs))
        _guard(context)
    context.grid_busy = True
    context.grid_delegate_frame = sys._getframe()
    try:
        _record(context, "operator_enter", kwargs["bound"])
        try:
            result = context.operator(grid, **kwargs)
        except BaseException as error:
            if context.primary is None:
                if context.pending_source_error is not None:
                    context.primary = context.pending_source_error
                elif not isinstance(error, _LITERAL._CaptureStop):
                    context.primary = error
            raise
        context.last_operator_return = (context.stage, result)
        try:
            context.results.append(context.last_operator_return)
        except BaseException as error:
            _capture_failure(context, error, "operator_return", result)
        _record(context, "operator_return", result)
        context.assignment_allowed = index + 1
        return result
    finally:
        context.grid_busy = False
        context.grid_delegate_frame = None


def trial_record(value):
    return dict(
        request=value.request_identity,
        parent=value.parent_identity,
        flux_operator=value.flux_operator,
        flux_solve_attempted=value.flux_solve_attempted,
        flux_solve_returned=value.flux_solve_returned,
        flux_inverse_absent=value.flux_inverse_absent,
        before=None if value.before is None else value.before.identity,
        cache=None if value.cache is None else value.cache.identity,
        stages=tuple((name, cache.identity) for name, cache in value.stages),
        callbacks=value.callback_statuses,
        boundaries=value.boundary_dictionaries,
        tail_stores=value.tail_stores,
        before_MT=None if value.stream_before is None else value.stream_before.identity,
        after_MT=None if value.stream_after is None else value.stream_after.identity,
        work=value.work,
        warnings=value.warnings,
        completed=value.source_completed,
        stage=value.failure_stage,
        source_error=value.source_failure,
        capture_error=value.capture_failure,
    )


def _partial(context):
    return dict(
        context=context,
        request=context.request,
        parent=context.parent,
        parent_trial=context.refs[1],
        phase=context.phase,
        p=context.p,
        caller=context.cells,
        grid=context.grid,
        mesh=context.mesh,
        image=context.mask,
        global_MT=context.rng,
        closed_claim=context.claim,
        closed_parameter_record=context.closed_record,
        results=context.results,
        helper_inputs=context.helper_inputs,
        helper_results=context.helper_results,
        raw_operator_returns=context.raw_operator_returns,
        last_helper_input=context.last_helper_input,
        last_helper_return=context.last_helper_return,
        last_operator_return=context.last_operator_return,
        last_observed_return=context.last_observed_return,
        last_raw_operator_return=context.last_raw_operator_return,
        locals=context.locals,
        original_cell_i=context.original_cell_i,
        original_all_points_cell_i=context.original_all_points_cell_i,
        tail_stores=context.tail_stores,
        tail_inputs=context.tail_inputs,
        tail_results=context.tail_results,
        last_tail_input=context.last_tail_input,
        last_tail_return=context.last_tail_return,
        events=context.events,
        stages=context.stages,
        work=context.work,
        primary=context.primary,
        capture_errors=context.capture_errors,
        cleanup_errors=context.cleanup_errors,
        trial=context.trial,
    )


def _failure(context, primary, capture):
    context.invalid = True
    raw = context
    try:
        raw = _partial(context)
    except BaseException as error:
        context.capture_errors += (("failure_partial", error, context),)
        if capture is None:
            capture = error
    try:
        error = PoissonRejected(
            "Actual same-SEED Poisson continuation failed",
            stage=context.stage,
            request=context.request,
            trial=context.trial,
            partial=raw,
            source_error=primary,
            capture_error=capture,
        )
    except BaseException as secondary:
        context.capture_errors += (("failure_exception", secondary, raw),)
        if primary is not None:
            raise primary  # noqa: B904
        if capture is not None:
            raise capture  # noqa: B904
        raise
    raise error from primary


def _complete(context):
    selected = METHODS if context.request.flux_operator == "original" else METHODS[:1]
    if (
        tuple(context.attempted) != selected
        or tuple(name for name, _ in context.results) != selected
        or tuple(context.callbacks_completed) != CALLBACK_STATUSES
        or tuple(context.boundaries) != METHODS
        or tuple(context.completed_stages) != STAGES
        or tuple(context.entered_stages) != STAGES
    ):
        raise ValueError("Incomplete original callbacks/boundaries/Poisson stages")
    if tuple(context.helper_attempts) != tuple(
        (stage, name) for stage in selected for name in ("zeros", "pinv")
    ):
        raise ValueError("Original zeros/default-pinv helper order incomplete")
    roles = _roles(context)
    names = (
        observation.ROLE_NAMES
        if context.request.flux_operator == "original"
        else observation.ROLE_NAMES[:3]
    )
    if tuple(roles) != names or len(_scope(context).roots) != len(names):
        raise ValueError("Actual distinct Z/A/P roots are incomplete")
    if context.request.flux_operator == "disabled" and context.cells.lapENV_P_inv is not None:
        raise ValueError("Disabled flux inverse must remain explicitly absent")
    if (
        tuple(context.tail_attempts) != ("asarray", "ones")
        or tuple(name for name, _ in context.tail_results) != ("asarray", "ones")
        or tuple(name for name, _ in context.tail_stores) != TAIL_FIELDS
        or context.tail_allowed != 6
        or context.cells.cell_i is not context.tail_results[0][1]
        or context.cells.gj_default_weights is not context.tail_results[1][1]
    ):
        raise ValueError("Incomplete original six-store data tail")


def _finish_store(context, name):
    index = TAIL_METHODS.index(name)
    field = TAIL_FIELDS[index]
    value = vars(context.cells)[field]
    context.last_store = (field, value)
    if index < 4 and value is not None:
        raise ValueError("Original final clear store changed")
    if index >= 4:
        helper = "asarray" if index == 4 else "ones"
        actual = [result for label, result in context.tail_results if label == helper]
        if len(actual) != 1 or value is not actual[0]:
            raise ValueError("Final assignment differs from its actual helper return")
    context.tail_stores.append(context.last_store)


def prepare(request, *, enabled=False):
    api = _ready()
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise PoissonRejected("Actual same-SEED Poisson remains held", stage="release")
    if _ACTIVE:
        _reject(_ACTIVE[-1], None, "Reentrant Poisson continuation")
    if type(request) is not Request or request not in _REQUESTS:
        raise PoissonRejected("Actual issued geometry request required", stage="request")
    with _LOCK:
        if request in _CONSUMED or request.geometry_owner in _RETIRED:
            raise PoissonRejected(
                "Geometry Poisson epoch consumed", stage="consumed", request=request
            )
        refs = _REQUESTS[request]
        parent = previous._authority(request.geometry_owner)
        if parent is not refs[0] or parent.trial is not refs[1]:
            raise PoissonRejected("Actual retained geometry changed", stage="parent")
        world = parent.prefix.parent.world_transition
        context = SimpleNamespace(
            request=request,
            refs=refs,
            parent=parent,
            api=api,
            phase=parent.phase,
            p=parent.p,
            cells=parent.cells,
            grid=parent.grid,
            mesh=parent.mesh,
            mask=parent.mask,
            rng=parent.rng,
            rand=parent.rand,
            world=world,
            claim=world.claim,
            closed_record=world.parameter_record,
            draw_active=False,
            thread=get_ident(),
            active=True,
            invalid=False,
            validating=False,
            stage="geometry_retirement",
            trial=None,
            before=None,
            stream_before=None,
            stream_after=None,
            driver_frame=sys._getframe(),
            entered_stages=[],
            completed_stages=[],
            work=[],
            events=[],
            locals={},
            stages=[],
            completed_outputs=[],
            admitted={},
            attempted=[],
            results=[],
            helper_inputs=[],
            helper_results=[],
            helper_attempts=[],
            raw_operator_returns=[],
            callbacks_completed=[],
            boundaries={},
            tail_attempts=[],
            tail_results=[],
            tail_inputs=[],
            tail_stores=[],
            tail_allowed=0,
            last_tail_input=None,
            last_tail_return=None,
            last_store=None,
            original_cell_i=parent.cells.cell_i,
            original_all_points_cell_i=parent.cells.all_points_cell_i,
            callback_occurrence=None,
            caller_frame=None,
            operator_frame=None,
            grid_delegate_frame=None,
            grid_busy=False,
            helper_busy=False,
            executing=False,
            entry_error=None,
            observation_error=None,
            pending_source_error=None,
            primary=None,
            capture_errors=(),
            capture_reporting_errors=(),
            cleanup_errors=(),
            last_helper_input=None,
            last_helper_return=None,
            last_operator_return=None,
            last_observed_return=None,
            last_raw_operator_return=None,
            assignment_allowed=0,
            caught=[],
            callback_codes=frozenset(),
            forbidden_callback_codes=parent.forbidden_callback_codes,
            required_hooks=(sys.getprofile(), sys.gettrace()),
            restore_setters=(sys.setprofile, sys.settrace),
            restore_getters=(sys.getprofile, sys.gettrace),
            native_root=str(_PREFIX.aliases.NATIVE),
            stable_view=SimpleNamespace(caller={}, grid=None, operator_roots={}),
            final_view=SimpleNamespace(caller={}, grid=None, operator_roots={}),
            stable_tape=SimpleNamespace(rng=parent.rng, events=(), draws=(), locals={}),
        )
        _CONSUMED[request] = _RETIRED[request.geometry_owner] = context
        _ACTIVE.append(context)
        primary = capture = None
        healthy = False
        try:
            context.checker = (
                api._independent_atoms,
                api._independent_atoms.__code__,
                api._independent_atoms.__globals__,
            )
            context.metadata_helpers = tuple(
                (name, fn, api._independent_atoms(fn))
                for name, fn in globals().items()
                if type(fn) is FunctionType and fn.__globals__ is globals()
            )
            context.plan = source_plan(flux_operator=request.flux_operator)
            context.projector_objects = parent.projector.objects
            context.projector_atoms = tuple(
                atom for pair in parent.projector.objects for atom in pair
            )
            context.parent_objects, context.parent_holders = parent.objects, parent.holders
            _bind_holder_views(context)
            context.original_names = tuple(vars(context.cells))
            if any(name in context.original_names for name in NEW_FIELDS):
                raise ValueError("Geometry parent already contains Poisson fields")
            if (
                type(context.original_cell_i) is not list
                or context.original_all_points_cell_i is not context.original_cell_i
            ):
                raise ValueError("Original cell_i list/all_points_cell_i alias required")
            context.parent_claim = getattr(previous, PROPOSED_CLAIM)
            context.parent_check = getattr(previous, PROPOSED_CHECK)
            context.entries = MappingProxyType({"Grid.makeLaplacian": _grid_call})
            if (
                context.parent_claim(
                    request.geometry_owner,
                    expected=parent,
                    transition=context,
                    entries=context.entries,
                )
                is not parent
            ):
                raise ValueError("Different genuine geometry owner retired")
            previous._same_epoch(parent, refs[2])
            context.before, context.stream_before = _snapshot(context), _rng(context)
            context.immutable = _immutable(context)
            _namespace(context)
            context.bindings = _bindings(context)
            _check(context)
            with warnings.catch_warnings(record=True) as caught:
                context.caught = caught
                with _account(context):
                    for name in STAGES:
                        context.stage, context.executing = name, True
                        if name in TAIL_METHODS:
                            context.tail_allowed = TAIL_METHODS.index(name) + 1
                        context.methods[name](context.cells, context.phase)
                        context.executing = False
                        if name in TAIL_METHODS:
                            _finish_store(context, name)
                        _guard(context)
                        _check(context)
                        if name in METHODS:
                            roots = tuple(
                                (role, value)
                                for role, value in _roles(context).items()
                                if role.startswith(name + ".")
                            )
                            context.completed_outputs.append(
                                (name, _scope(context).snapshot(dict(roots)), roots)
                            )
                        context.stages.append((name, _snapshot(context)))
                        context.completed_stages.append(name)
                    _complete(context)
        except BaseException as error:
            primary = context.primary
            if primary is None and not (
                isinstance(error, _LITERAL._CaptureStop) and context.observation_error is not None
            ):
                primary = (
                    context.pending_source_error
                    if context.pending_source_error is not None
                    else error
                )
            context.primary = primary
        finally:
            context.executing = False
            try:
                healthy = _BASE._recover(context)
            except BaseException as error:
                context.cleanup_errors += (("recovery_entry", error, context),)
                # A guard can reject before the helper body. Independently
                # attempt both original hooks here without rendering errors.
                for index in (1, 0):
                    try:
                        context.restore_setters[index](context.required_hooks[index])
                    except BaseException as secondary:
                        context.cleanup_errors += (("direct_restore", secondary, index),)
                samples = []
                for order in ((0, 1), (1, 0)):
                    pair = [None, None]
                    for index in order:
                        try:
                            pair[index] = context.restore_getters[index]()
                        except BaseException as secondary:
                            context.cleanup_errors += (("direct_sample", secondary, index),)
                    samples.append(tuple(pair))
                context.final_hook_samples = tuple(samples)
                healthy = all(
                    pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
                    for pair in samples
                )
            if context.cleanup_errors and context.observation_error is None:
                context.observation_error = context.cleanup_errors[0][1]
            capture = context.observation_error
        if healthy:
            try:
                context.stream_after = _rng(context)
                value = Trial(
                    request.identity,
                    request.parent_identity,
                    request.flux_operator,
                    METHODS[1] in context.attempted,
                    any(name == METHODS[1] for name, _ in context.results),
                    FIELDS[1] in vars(context.cells) and vars(context.cells)[FIELDS[1]] is None,
                    context.before,
                    _snapshot(context),
                    tuple(context.stages),
                    tuple(context.callbacks_completed),
                    tuple((name, dict(bound)) for name, bound in context.boundaries.items()),
                    tuple(
                        (name, _scope(context).snapshot(value).identity)
                        for name, value in context.tail_stores
                    ),
                    context.stream_before,
                    context.stream_after,
                    tuple((r["sequence"], r["name"], r["layer"], r["state"]) for r in context.work),
                    tuple(
                        (
                            w.category.__module__,
                            w.category.__qualname__,
                            str(w.message),
                            w.filename,
                            w.lineno,
                        )
                        for w in context.caught
                    ),
                    primary is None
                    and capture is None
                    and tuple(context.completed_stages) == STAGES,
                    context.stage if primary is not None or capture is not None else None,
                    None if primary is None else type(primary).__qualname__,
                    None if capture is None else type(capture).__qualname__,
                    "",
                )
                context.trial = replace(value, identity=_digest(trial_record(value)))
                if primary is None and capture is None:
                    _complete(context)
                    _check(context)
                    context.graph = _graph(context)
            except BaseException as error:
                context.capture_errors += (("sealing", error, context),)
                if capture is None:
                    capture = error
        try:
            healthy = _BASE._recover(context) and healthy
        except BaseException as error:
            context.cleanup_errors += (("final_recovery_entry", error, context),)
            healthy = False
            for index in (1, 0):
                try:
                    context.restore_setters[index](context.required_hooks[index])
                except BaseException as secondary:
                    context.cleanup_errors += (("final_direct_restore", secondary, index),)
        # No formatter, recorder or setter precedes the two final complete
        # samples. Cleanup failures invalidate even a subsequently restored run.
        samples = []
        for order in ((0, 1), (1, 0)):
            pair = [None, None]
            for index in order:
                try:
                    pair[index] = context.restore_getters[index]()
                except BaseException as error:
                    context.cleanup_errors += (("terminal_sample", error, index),)
            samples.append(tuple(pair))
        context.final_hook_samples = tuple(samples)
        healthy = healthy and all(
            pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
            for pair in samples
        )
        if context.cleanup_errors and context.observation_error is None:
            context.observation_error = context.cleanup_errors[0][1]
        if capture is None:
            capture = context.observation_error
        context.active = False
        if _ACTIVE and _ACTIVE[-1] is context:
            _ACTIVE.pop()
        else:
            context.invalid = True
        if (
            primary is not None
            or capture is not None
            or context.trial is None
            or not healthy
            or context.invalid
        ):
            if not healthy:
                if primary is not None:
                    raise primary
                if capture is not None:
                    raise capture
                raise RuntimeError("Inherited hooks unavailable; raw Poisson context retained")
            _failure(context, primary, capture)
        try:
            owner = object.__new__(PoissonOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            _failure(context, error, capture)


class PoissonOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the genuine geometry-to-Poisson continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No supplied matrices or ordinary executable checkpoint")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not PoissonOwner or owner not in _ISSUED:
        raise PoissonRejected("Actually issued SEED Poisson child required", stage="owner")
    context = _ISSUED[owner]
    if context.active or context.invalid or context.validating:
        _reject(context, None, "Unavailable Poisson child")
    context.validating = True
    try:
        _check(context)
        _complete(context)
        if (
            context.trial.source_completed is not True
            or context.trial.identity != _digest(trial_record(context.trial))
            or context.trial.cache.identity != _snapshot(context).identity
            or context.trial.tail_stores
            != tuple(
                (name, _scope(context).snapshot(value).identity)
                for name, value in context.tail_stores
            )
        ):
            raise ValueError("Completed Poisson mode/trial/cache changed")
        graph = _graph(context)
        _same(graph[0], context.graph[0])
        if graph[1] != context.graph[1]:
            raise ValueError("Actual completed operator references changed")
    except BaseException as error:
        _failure(context, error, context.observation_error)
    finally:
        context.validating = False
    return context


def require_INIT(owner):
    context = _authority(owner)
    raise PoissonRejected(
        "Completed selected world is not actual INIT authority",
        stage="INIT_held",
        request=context.request,
        trial=context.trial,
    )
