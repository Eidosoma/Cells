"""Owned non-SVG multi-cell ordinary geometry, ECM and environment prefix.

The selected descriptor is constructed before parameter/caller birth. The
continuation consumes that actual caller once; no single-cell owner, supplied
grid, phase, cache hydration or physical/checkpoint admission is provided.
Actual native execution remains a separately coordinated source trial.
"""

import ast
import hashlib
import sys
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_multi_cell_caller as multi
from cells.processes import betse_native_single_cell_ecm_source as ecm_source
from cells.processes import betse_native_single_cell_environment_source as environment_source

core, geometry, aliases = multi.core, multi.captures, multi.atoms
LAW_ID = "betse_owned_non_SVG_multi_cell_ordinary_environment@1"
INVALIDATED_OWNERS = multi.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
METHODS = (*geometry.METHODS, "makeECM", "environment", "assign_grid_len", "make_maskM")
_METHODS = {
    **geometry._NATIVE,
    "makeECM": ecm_source.CellsECM.makeECM,
    **{
        name: getattr(environment_source.CellsEnvironment, name)
        for name in ("environment", "assign_grid_len", "make_maskM")
    },
}
_INIT, _GRID = ecm_source.FiniteDiffSolver.__init__, ecm_source.FiniteDiffSolver.cell_grid
_NATIVE_TREE = environment_source.cKDTree
_TREE_INIT, _TREE_QUERY, _TREE_BALL = (
    _NATIVE_TREE.__init__,
    _NATIVE_TREE.query,
    _NATIVE_TREE.query_ball_point,
)
_GRIDDATA, _GAUSSIAN = environment_source.interp.griddata, environment_source.gaussian_filter
_HELPERS = (
    "asarray",
    "array",
    "sqrt",
    "vstack",
    "zeros",
    "abs",
    "roll",
    "dot",
    "unique",
    "hstack",
    "linspace",
    "meshgrid",
    "column_stack",
    "ones",
    "sum",
    "round",
)
_TREE_FIELDS = ("data", "indices", "mins", "maxes", "n", "m", "leafsize", "boxsize")
_GRID_HELPERS = ("linspace", "meshgrid", "column_stack", "asarray")
_ISSUED, _GRIDS, _TREES = WeakKeyDictionary(), WeakKeyDictionary(), WeakKeyDictionary()
_FORWARDED = WeakKeyDictionary()
_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class Request:
    caller_request: multi.OrdinaryRequest
    identity: str


@dataclass(frozen=True, slots=True)
class ContinuationRequest:
    caller_owner: multi.MultiCellOwner
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    cache: object
    stages: tuple
    events: tuple
    work: tuple
    stream_before: object
    stream_after: object
    warnings: tuple
    source_completed: bool
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class EnvironmentRejected(ValueError):
    def __init__(
        self,
        reason,
        *,
        stage,
        request=None,
        trial=None,
        partial=None,
        source_error=None,
        capture_error=None,
    ):
        super().__init__(reason)
        self.stage, self.request, self.trial, self.partial = stage, request, trial, partial
        self.source_error, self.capture_error = source_error, capture_error


class _CaptureStop(Exception):
    pass


def _verify_sources():
    pins = multi._verify_sources()
    native = multi.callers.NATIVE_ROOT
    for relative, expected, clsname, owned, methods in (
        (
            "betse/science/cells.py",
            ecm_source.CELLS_SHA256,
            "Cells",
            geometry.source,
            geometry.METHODS,
        ),
        ("betse/science/cells.py", ecm_source.CELLS_SHA256, "Cells", ecm_source, ("makeECM",)),
        (
            "betse/science/cells.py",
            environment_source.NATIVE_CELLS_SHA256,
            "Cells",
            environment_source,
            ("environment", "make_maskM"),
        ),
        (
            "betse/science/math/finitediff.py",
            ecm_source.GRID_SHA256,
            "FiniteDiffSolver",
            ecm_source,
            ("__init__", "cell_grid"),
        ),
    ):
        path = native / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Original ordinary multi-cell source changed")
        original = next(
            n
            for n in ast.parse(path.read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == clsname
        )
        owned_name = {
            geometry.source: "CellKernel",
            ecm_source: "CellsECM",
            environment_source: "CellsEnvironment",
        }[owned]
        if clsname == "FiniteDiffSolver":
            owned_name = clsname
        dst = next(
            n
            for n in ast.parse(Path(owned.__file__).read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == owned_name
        )
        for name in methods:
            left = next(
                n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == name
            )
            right = next(n for n in dst.body if isinstance(n, ast.FunctionDef) and n.name == name)
            if ast.dump(ast.Module(body=left.body, type_ignores=[])) != ast.dump(
                ast.Module(body=right.body, type_ignores=[])
            ):
                raise ValueError("Literal ordinary multi-cell body changed: " + name)
    cells = next(
        n
        for n in ast.parse((native / "betse/science/cells.py").read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "Cells"
    )
    world = next(n for n in cells.body if isinstance(n, ast.FunctionDef) and n.name == "make_world")
    assignment = next(
        n
        for n in world.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "grid_len" for t in n.targets)
    )
    destination = next(
        n
        for n in ast.parse(Path(environment_source.__file__).read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "CellsEnvironment"
    )
    copied_assignment = next(
        n
        for n in destination.body
        if isinstance(n, ast.FunctionDef) and n.name == "assign_grid_len"
    )
    if ast.dump(ast.Module(body=[assignment], type_ignores=[])) != ast.dump(
        ast.Module(body=copied_assignment.body, type_ignores=[])
    ):
        raise ValueError("Literal grid_len assignment changed")
    pins.update(aliases.source_pins())
    for module in (
        geometry,
        geometry.source,
        ecm_source,
        environment_source,
        sys.modules[__name__],
    ):
        file = Path(module.__file__).resolve()
        pins[str(file)] = hashlib.sha256(file.read_bytes()).hexdigest()
    return pins


def from_lifecycle(request, state, configuration, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise EnvironmentRejected("Explicit multi-cell environment law required", stage="opt_in")
    caller = multi.from_lifecycle_ordinary(
        request, state, configuration, law_id=multi.ORDINARY_LAW_ID
    )
    value = Request(caller, "")
    return replace(value, identity=core.records._digest(dict(law=LAW_ID, caller=caller.identity)))


def _preflight(owner):
    parent = multi._validate(owner)
    if (
        type(parent.request) is not multi.OrdinaryRequest
        or type(parent.trial) is not multi.OrdinaryTrial
        or not parent.trial.source_completed
        or parent.request.grid_descriptor != aliases.SELECTOR
        or parent.parameter_info is None
        or type(parent.p) is not parent.parameter_info.runtime
        or parent.trial.descriptor_proof != parent.descriptor_proof
        or parent.p.plot_grid_size != 50
    ):
        raise EnvironmentRejected(
            "Fresh selected descriptor/20-store source authority required; no retrofit",
            stage="parameter_prerequisite",
            trial=parent.trial,
        )
    aliases.validate(parent.parameter_info)
    return parent


def request_record(request):
    parent = multi._authority(request.caller_owner)
    return dict(
        law=LAW_ID,
        parent=parent.trial.identity,
        parameter_mode=multi.ORDINARY_LAW_ID,
        selected_stores=multi.source.STORE_LINES,
        selected_store_AST=multi.source.STORES_AST_SHA256,
        descriptor=aliases.specification(),
        methods=METHODS,
        boundary="after make_maskM, before environmental makeLaplacian",
        invalidated_owners=INVALIDATED_OWNERS,
        full_Parameters_YAML_phase_physical_checkpoint=False,
    )


def from_caller(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise EnvironmentRejected("Explicit multi-cell environment law required", stage="opt_in")
    _preflight(owner)
    request = ContinuationRequest(owner, "")
    return replace(request, identity=core.records._digest(request_record(request)))


def _stop(context):
    if context.observation_error is not None:
        raise _CaptureStop()


def _observe(context, kind, raw):
    try:
        context.events.append((kind, raw))
    except Exception as capture:
        geometry._remember_observation_error(context, capture, origin=kind, raw=raw)


def _operation(context, name, delegate, *args, **kwargs):
    _stop(context)
    if not context.active or not context.executing or context.thread != get_ident():
        raise EnvironmentRejected(
            "Helper lacks active owned driver", stage="source_call_unavailable"
        )
    _check(context)
    _observe(context, name + "_enter", (args, kwargs))
    _stop(context)  # Never enter a helper after a failed enter observation.
    try:
        value = delegate(*args, **kwargs)
    except Exception:
        _observe(context, name + "_unwind", (args, kwargs))
        raise
    # Completion and raw output precede fallible observation. These flags do
    # not grant a child when local/event capture or later sealing fails.
    context.last_completed_helper = (name, args, value)
    if name == "grid_constructor":
        context.constructed = True
    elif name == "cell_grid":
        context.initialized = True
    elif name == "tree_constructor":
        _TREES[args[0]].constructed = True
    try:
        context.helper_results.append((name, value))
    except Exception as capture:
        geometry._remember_observation_error(context, capture, origin="helper_result", raw=value)
    _observe(context, name + "_return", value)
    _stop(context)
    return value


def _require_descriptor_read(context):
    if (
        context.descriptor_read_started is not True
        or context.descriptor_read_completed is not True
        or context.descriptor_read_instance is not context.parent.p
        or context.descriptor_read_return_instance is not context.parent.p
        or context.descriptor_read_native is not context.parameter_info.native
        or context.descriptor_read_epoch is not context.retirement
    ):
        raise ValueError("Same-parameter native grid_size read did not enter and complete")


def _active_grid(grid):
    context = _GRIDS.get(grid)
    if (
        context is None
        or type(grid) is not _GridRuntime
        or not context.active
        or not context.executing
        or context.thread != get_ident()
    ):
        raise EnvironmentRejected(
            "Raw grid lacks active issued driver", stage="source_call_unavailable"
        )
    _stop(context)
    _check(context)
    return context


class _GridRuntime(ecm_source.FiniteDiffSolver):
    def __init__(self):
        context = _active_grid(self)
        if context.constructing or context.constructed:
            raise EnvironmentRejected(
                "Grid constructor already attempted", stage="grid_constructor"
            )
        context.constructing = True
        context.stage = context.prefix.stage = "grid_constructor"
        try:
            _operation(context, "grid_constructor", _INIT, self)
            context.constructed = True
        finally:
            context.constructing = False
        context.stage = context.prefix.stage = "makeECM"

    def cell_grid(self, *args):
        context = _active_grid(self)
        if (
            not context.constructed
            or context.initializing
            or context.initialized
            or context.parent.caller.grid_obj is not self
        ):
            raise EnvironmentRejected(
                "Constructor/assignment/cell_grid order changed", stage="cell_grid"
            )
        context.initializing = True
        context.stage = context.prefix.stage = "cell_grid"
        _observe(context, "cell_grid_enter_after_exact_assignment", self)
        _stop(context)
        try:
            _operation(context, "cell_grid", _GRID, self, *args)
            context.initialized = True
        finally:
            context.initializing = False
        context.stage = context.prefix.stage = "makeECM"

    def makeLaplacian(self, *args, **kwargs):
        from cells.processes import betse_native_multi_cell_poisson as poisson

        return poisson._grid_call(self, *args, **kwargs)

    def __reduce_ex__(self, protocol):
        raise TypeError("Live grid authority cannot be serialized")


def _construct_grid(context):
    if (
        not context.active
        or not context.executing
        or context.grid is not None
        or context.thread != get_ident()
    ):
        raise EnvironmentRejected("Fresh grid construction unavailable", stage="grid_constructor")
    _stop(context)
    _check(context)
    _require_descriptor_read(context)
    grid = context.grid = object.__new__(_GridRuntime)
    _GRIDS[grid] = context
    grid.__init__()
    return grid


def _active_tree(tree):
    record = _TREES.get(tree)
    if record is None or type(tree) is not _TreeRuntime:
        raise EnvironmentRejected("Tree lacks process-local issuance", stage="tree_owner")
    context = record.context
    if not context.active or not context.executing or context.thread != get_ident() or record.busy:
        raise EnvironmentRejected("Raw tree lacks active driver", stage="source_call_unavailable")
    _stop(context)
    _check(context)
    return record


class _TreeRuntime(_NATIVE_TREE):
    def __new__(cls, *args, **kwargs):
        raise EnvironmentRejected("Use actual source tree factory", stage="source_call_unavailable")

    def __init__(self, *args, **kwargs):
        record = _active_tree(self)
        if record.constructed:
            raise EnvironmentRejected(
                "Tree constructor already attempted", stage="tree_constructor"
            )
        record.busy = True
        try:
            _operation(record.context, "tree_constructor", _TREE_INIT, self, *args, **kwargs)
            record.constructed = True
        finally:
            record.busy = False

    def query(self, *args, **kwargs):
        return _tree_call(self, "tree_query", _TREE_QUERY, *args, **kwargs)

    def query_ball_point(self, *args, **kwargs):
        return _tree_call(self, "tree_query_ball_point", _TREE_BALL, *args, **kwargs)

    @property
    def tree(self):
        raise EnvironmentRejected("Lazy native tree nodes remain held", stage="tree_view_held")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live tree authority cannot be serialized")

    def __getstate__(self):
        raise TypeError("Tree checkpoint export remains held")

    def __setstate__(self, state):
        raise TypeError("Native tree cannot be hydrated")


def _tree_call(tree, name, delegate, *args, **kwargs):
    record = _active_tree(tree)
    if not record.constructed:
        raise EnvironmentRejected("Tree constructor did not complete", stage="tree_constructor")
    record.busy = True
    try:
        return _operation(record.context, name, delegate, tree, *args, **kwargs)
    finally:
        record.busy = False


def _refuse_tree_method(name):
    def refuse(self, *args, **kwargs):
        raise EnvironmentRejected("Unqualified tree method: " + name, stage="tree_method_held")

    return refuse


_REFUSED_TREE_METHODS = tuple(
    name
    for name, value in vars(_NATIVE_TREE).items()
    if callable(value) and not name.startswith("_") and name not in {"query", "query_ball_point"}
)
for _name in _REFUSED_TREE_METHODS:
    setattr(_TreeRuntime, _name, _refuse_tree_method(_name))


def _allocate_native_tree():
    return _NATIVE_TREE.__new__(_TreeRuntime)


def _new_tree(context, *args, **kwargs):
    _stop(context)
    if not context.active or not context.executing or context.thread != get_ident():
        raise EnvironmentRejected(
            "Tree construction lacks source driver", stage="source_call_unavailable"
        )
    _check(context)
    tree = _allocate_native_tree()
    _TREES[tree] = SimpleNamespace(
        context=context,
        constructed=False,
        busy=False,
        view=SimpleNamespace(),
        tape=SimpleNamespace(rng=None, events=[], draws=[], locals={}),
    )
    context.trees.append(tree)
    tree.__init__(*args, **kwargs)
    return tree


def _tree_state(tree):
    result = {}
    for name in _TREE_FIELDS:
        try:
            result[name] = getattr(tree, name)
        except AttributeError:
            result[name] = ("unavailable", name)
    return result


def _snapshot(context):
    parent = context.parent
    caller = {
        k: v
        for k, v in multi.callers._public(parent.caller).items()
        if k not in {"mesh", "grid_obj", "points_tree"}
    }
    return core.caches.snapshot(
        dict(
            caller=multi._project(parent, caller),
            mesh=multi._project(parent, multi.initial._public_cache(parent.kernel)),
            parameters=multi.callers._parameters(parent.p),
            grid=None if context.grid is None else dict(vars(context.grid)),
            trees=[_tree_state(tree) for tree in context.trees],
        )
    )


def _graphs(context):
    parent = context.parent
    graphs = list(multi._graphs(parent))
    if context.grid is not None:
        graphs.append(multi.callers._graph(context.grid, parent.p, parent.tape))
    for tree in context.trees:
        record = _TREES[tree]
        vars(record.view).clear()
        vars(record.view).update(_tree_state(tree))
        record.view.native_tree = tree  # Evidence only; never a computation input.
        graphs.append(multi.callers._graph(record.view, parent.p, record.tape))
    return tuple(graphs)


def _immutable_graphs(context):
    """Evidence edges for the unchanged part of the consumed parent epoch."""
    parent = context.parent
    # Only cell_vol among the preexisting caller fields is overwritten by the
    # selected ordinary block. New geometry fields are not pre-parent caches.
    vars(context.original_view).clear()
    vars(context.original_view).update(
        (name, getattr(parent.caller, name)) for name in context.original_names
    )
    return (
        multi.callers._graph(context.original_view, parent.p, parent.tape),
        multi.callers._graph(parent.kernel, parent.p, parent.tape),
        multi.images._graph(parent.image_tape),
    )


def _immutable_state(context):
    parent = context.parent
    return core.caches.snapshot(
        multi._project(
            parent,
            dict(
                original_caller=vars(context.original_view),
                parameters=multi.callers._parameters(parent.p),
                mesh=multi.initial._public_cache(parent.kernel),
            ),
        )
    )


def _grid_numpy_bindings():
    # cell_grid is called directly: its globals are not the copied makeECM
    # namespace. Retain both the source-module NumPy and actual delegate's
    # global binding, with exact reached callable/implementation code atoms.
    delegate_numpy = _GRID.__globals__.get("np")
    values = [_GRID_HELPERS, ecm_source.np, _GRID.__globals__, delegate_numpy]
    for numpy in (ecm_source.np, delegate_numpy):
        for name in _GRID_HELPERS:
            helper = getattr(numpy, name)
            for function in (
                helper,
                getattr(helper, "__wrapped__", None),
                getattr(helper, "_implementation", None),
            ):
                values.extend(aliases._atoms(function))
    return tuple(values)


def _bindings():
    functions = (
        *_METHODS.values(),
        _INIT,
        _GRID,
        _TREE_INIT,
        _TREE_QUERY,
        _TREE_BALL,
        _GRIDDATA,
        _GAUSSIAN,
        _construct_grid,
        _allocate_native_tree,
        _new_tree,
        _operation,
        _invoke_method,
        _active_grid,
        _active_tree,
        _tree_call,
        _immutable_graphs,
        _immutable_state,
        _grid_numpy_bindings,
        aliases.reading,
        aliases._GridAlias.__get__,
        aliases._GridAlias.__set__,
        geometry._Logs.log_info,
        geometry.source.flatten,
        geometry.source.copy.deepcopy,
        *(getattr(geometry.source.np, name) for name in _HELPERS),
        geometry.source.np.linalg.norm,
        geometry.source.np.linalg.pinv,
    )
    return (
        *[
            atom
            for cls in (_GridRuntime, _TreeRuntime, geometry._Logs)
            for atom in aliases._dispatch_bindings(cls)
        ],
        *[atom for fn in functions for atom in aliases._atoms(fn)],
        _NATIVE_TREE,
        ecm_source.FiniteDiffSolver,
        geometry.source.np,
        geometry.source.np.linalg,
        geometry.source.math,
        geometry.source.tb,
        geometry.source.copy,
        environment_source.interp,
        *_grid_numpy_bindings(),
    )


def _namespace(context):
    def tree(*args, **kwargs):
        return _new_tree(context, *args, **kwargs)

    def constructor():
        return _construct_grid(context)

    def interpolate(*args, **kwargs):
        return _operation(context, "griddata", _GRIDDATA, *args, **kwargs)

    def smooth(*args, **kwargs):
        return _operation(context, "gaussian_filter", _GAUSSIAN, *args, **kwargs)

    namespaces = {
        "geometry": dict(geometry.source.__dict__, logs=geometry._Logs(context), cKDTree=tree),
        "ECM": dict(
            ecm_source.__dict__, fd=SimpleNamespace(FiniteDiffSolver=constructor), cKDTree=tree
        ),
        "environment": dict(
            environment_source.__dict__,
            cKDTree=tree,
            interp=SimpleNamespace(griddata=interpolate),
            gaussian_filter=smooth,
        ),
    }
    return {
        name: FunctionType(
            fn.__code__,
            namespaces[
                "geometry"
                if name in geometry.METHODS
                else "ECM"
                if name == "makeECM"
                else "environment"
            ],
            fn.__name__,
            fn.__defaults__,
            fn.__closure__,
        )
        for name, fn in _METHODS.items()
    }


def _namespace_bindings(context):
    methods = context.methods
    result = list(
        geometry._namespace_bindings({name: methods[name] for name in geometry.METHODS}, context)
    )
    for name in METHODS:
        fn, namespace = methods[name], methods[name].__globals__
        result.extend(aliases._atoms(fn))
        result.append(namespace["np"])
        result.extend(aliases._atoms(namespace["cKDTree"]))
        if name == "makeECM":
            result.append(namespace["fd"])
            result.extend(aliases._atoms(namespace["fd"].FiniteDiffSolver))
        elif name not in geometry.METHODS:
            result.extend((namespace["tb"], namespace["interp"]))
            for helper in (
                namespace["tb"].flatten,
                namespace["tb"].flatten.__globals__["copy"].deepcopy,
                namespace["interp"].griddata,
                namespace["gaussian_filter"],
            ):
                result.extend(aliases._atoms(helper))
        for helper in _HELPERS:
            result.extend(aliases._atoms(getattr(namespace["np"], helper)))
    return tuple(result)


def _invoke_method(context, name):
    if name == "assign_grid_len":
        return context.methods[name](context.parent.caller)
    return context.methods[name](context.parent.caller, context.parent.p)


def _check(context):
    parent = context.parent
    if (
        multi._authority(context.request.caller_owner) is not parent
        or parent.invalid
        or parent.active
        or parent.thread != get_ident()
        or parent.trial is not context.prior_trial
        or core.records._digest(multi.trial_record(parent.trial)) != context.parent_signature
        or multi._FORWARDED.get(context.request.caller_owner) is not context.retirement
    ):
        raise ValueError("Original multi-cell trial or irreversible continuation claim changed")
    # Do not reopen the consumed validator or compare new caller fields with
    # its pre-geometry caches. This checks inherited source/observer/alias links.
    multi._check(parent)
    geometry.meshes._same_graphs(_immutable_graphs(context), context.immutable_graphs)
    if (
        _immutable_state(context).identity != context.immutable_state.identity
        or multi.initial._rng_stream(parent.rng).identity != context.stream_before.identity
        or multi._image_state(parent).identity != context.image_identity
    ):
        raise ValueError(
            "Unchanged parent parameters/mesh/image/RNG or original caller fields drifted"
        )
    if (
        type(parent.request) is not multi.OrdinaryRequest
        or type(parent.trial) is not multi.OrdinaryTrial
        or parent.parameter_info is not context.parameter_info
        or parent.descriptor_proof != context.descriptor_proof
        or parent.trial.descriptor_proof != context.descriptor_proof
        or type(parent.p) is not context.parameter_info.runtime
    ):
        raise ValueError("Fresh native descriptor birth provenance changed")
    aliases.validate(context.parameter_info)
    if _verify_sources() != context.producers:
        raise ValueError("Multi-cell ordinary source producer changed")
    multi.accounting._check_binding_identity(_bindings(), context.bindings)
    if hasattr(context, "methods"):
        multi.accounting._check_binding_identity(
            _namespace_bindings(context), context.namespace_bindings
        )
        if geometry._namespace_constants(context.methods) != context.namespace_constants:
            raise ValueError("Exact geometry constants changed")
    if hasattr(context, "read_callbacks"):
        multi.accounting._check_binding_identity(
            (*aliases._atoms(context.check), *aliases._atoms(context.observe)),
            context.read_callbacks,
        )
    if context.grid is not None or context.finished:
        _require_descriptor_read(context)
        if type(context.grid) is not _GridRuntime or _GRIDS.get(context.grid) is not context:
            raise ValueError("Actual source grid issuance changed")
    for tree in context.trees:
        record = _TREES.get(tree)
        if type(tree) is not _TreeRuntime or record is None or record.context is not context:
            raise ValueError("Actual source tree issuance changed")
    if context.finished:
        caller, grid = parent.caller, context.grid
        pairs = (
            (caller.grid_obj, grid),
            (caller.X, grid.cents_X),
            (caller.Y, grid.cents_Y),
            (caller.xypts, grid.xy_cents),
            (caller.map_ij2k, grid.map_ij2k_cents),
            (caller.all_points_cell_i, caller.cell_i),
            (caller.voronoi_centres, caller.xypts),
        )
        if (
            not context.constructed
            or not context.initialized
            or any(a is not b for a, b in pairs)
            or type(caller.grid_len) is not int
            or caller.grid_len != len(caller.xypts)
            or not context.trees
            or not any(caller.points_tree is t for t in context.trees)
            or any(not _TREES[t].constructed for t in context.trees)
        ):
            raise ValueError("Original geometry/ECM/environment completion or aliases changed")


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        parent=trial.parent_identity,
        before=trial.before.identity,
        cache=trial.cache.identity,
        stages=[(name, cache.identity) for name, cache in trial.stages],
        events=trial.events,
        work=trial.work,
        stream_before=trial.stream_before.identity,
        stream_after=trial.stream_after.identity,
        warnings=trial.warnings,
        source_completed=trial.source_completed,
        failure_stage=trial.failure_stage,
        failure_type=trial.failure_type,
        failure_message=trial.failure_message,
        invalidated_owners=INVALIDATED_OWNERS,
        full_make_world_Poisson_physical_checkpoint=False,
    )


class EnvironmentOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the owned multi-cell ordinary source entry")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live multi-cell environment authority cannot be serialized")

    @property
    def cells(self):
        return _validate(self).parent.caller

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not EnvironmentOwner or owner not in _ISSUED:
        raise EnvironmentRejected(
            "Issued multi-cell environment unavailable", stage="environment_owner"
        )
    return _ISSUED[owner]


def _validate(owner):
    context = _authority(owner)
    if owner in _FORWARDED:
        raise EnvironmentRejected(
            "Multi-cell environment epoch was consumed by a Poisson attempt",
            stage="environment_epoch_consumed",
            trial=context.trial,
            request=context.request,
        )
    try:
        if context.invalid or context.active or context.thread != get_ident():
            raise ValueError("Invalid multi-cell environment epoch")
        _check(context)
        if (
            _snapshot(context).identity != context.trial.cache.identity
            or core.records._digest(trial_record(context.trial)) != context.trial.identity
            or multi.initial._rng_stream(context.parent.rng).identity
            != context.trial.stream_after.identity
            or multi._image_state(context.parent).identity != context.image_identity
        ):
            raise ValueError("Changed multi-cell environment cache/RNG/image/trial")
        geometry.meshes._same_graphs(_graphs(context), context.graphs)
        for cache in (
            context.trial.before,
            context.trial.cache,
            *(cache for _, cache in context.trial.stages),
        ):
            core.caches.validate(cache)
    except Exception as error:
        context.invalid = True
        raise EnvironmentRejected(
            "Stale multi-cell environment refused",
            stage="environment_drift",
            request=context.request,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def _claim_for_Poisson(owner, *, expected, transition):
    with _LOCK:
        context = _validate(owner)
        if context is not expected:
            raise EnvironmentRejected(
                "Actual multi-cell environment changed", stage="environment_owner"
            )
        _FORWARDED[owner] = transition
        return context


@contextmanager
def _locals(context):
    previous = sys.getprofile()
    codes = {fn.__code__: name for name, fn in context.methods.items()}
    codes.update({_INIT.__code__: "grid_constructor", _GRID.__code__: "cell_grid"})

    def profile(frame, event, arg):
        if event == "return" and frame.f_code in codes:
            try:
                geometry._capture_locals(context, codes[frame.f_code], frame)
            except Exception as capture:
                geometry._remember_observation_error(
                    context, capture, origin="raw_locals", raw=frame
                )
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)


@contextmanager
def _account(work):
    # One primary ledger: child trials retain their own views, never additive
    # case/work credit. Failed body entries and isolated authentication remain.
    with multi.accounting._account_prefix(
        work,
        _source_modules=(geometry.source, ecm_source, environment_source, aliases),
        _entry_names=(
            *METHODS,
            "cell_grid",
            "_construct_grid",
            "_new_tree",
            "query",
            "query_ball_point",
            "_operation",
            "_invoke_method",
            "_new_parameters",
        ),
    ):
        previous = sys.getprofile()

        def profile(frame, event, arg):
            module, name = frame.f_globals.get("__name__", ""), frame.f_code.co_name
            if event == "call" and (
                module == "betse"
                or module.startswith("betse.")
                or module == __name__
                and name
                in {
                    "_construct_grid",
                    "__init__",
                    "cell_grid",
                    "_new_tree",
                    "query",
                    "query_ball_point",
                    "_operation",
                    "_invoke_method",
                }
            ):
                if len(work.work) >= 100000:
                    raise ValueError("Bounded prefix work ledger exhausted")
                work.work.append(
                    dict(
                        sequence=len(work.work),
                        phase=work.stage,
                        execution="source",
                        layer="native_descriptor"
                        if module.startswith("betse")
                        else "helper_wrapper",
                        module=module,
                        method=frame.f_code.co_qualname,
                        entry_method=name,
                        source_file=frame.f_code.co_filename,
                        status="entered_not_success_credit",
                    )
                )
            if previous is not None:
                previous(frame, event, arg)

        sys.setprofile(profile)
        try:
            yield
        finally:
            sys.setprofile(previous)


def prepare_continuation(request, *, _work=None):
    if type(request) is not ContinuationRequest:
        raise EnvironmentRejected("Typed actual multi-cell caller required", stage="request_owner")
    if _work is None:
        work = SimpleNamespace(stage="multi_environment", work=[])
        with _account(work):
            return prepare_continuation(request, _work=work)
    parent = multi._authority(request.caller_owner)
    context = SimpleNamespace(
        request=request,
        parent=parent,
        prior_trial=parent.trial,
        retirement=object(),
        parameter_info=getattr(parent, "parameter_info", None),
        descriptor_proof=getattr(parent, "descriptor_proof", ()),
        thread=get_ident(),
        invalid=False,
        active=False,
        executing=False,
        finished=False,
        grid=None,
        constructing=False,
        constructed=False,
        initializing=False,
        initialized=False,
        trees=[],
        events=[],
        logs=[],
        locals={},
        stages=[],
        helper_results=[],
        stage="preflight",
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
        prefix=_work,
        before=None,
        stream_before=None,
        descriptor_read_started=False,
        descriptor_read_completed=False,
        descriptor_read_instance=None,
        descriptor_read_return_instance=None,
        descriptor_read_native=None,
        descriptor_read_epoch=None,
    )
    error = None
    with _LOCK, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            if (
                _preflight(request.caller_owner) is not parent
                or core.records._digest(request_record(request)) != request.identity
            ):
                raise ValueError("Changed multi-cell continuation request")
            context.producers, context.bindings = _verify_sources(), _bindings()
            context.parent_signature = core.records._digest(multi.trial_record(parent.trial))
            context.before = _snapshot(context)
            context.stream_before = multi.initial._rng_stream(parent.rng)
            context.image_identity = multi._image_state(parent).identity
            context.original_names = tuple(
                name for name in vars(parent.caller) if name not in {"mesh", "cell_vol"}
            )
            context.original_view = SimpleNamespace()
            context.immutable_graphs = _immutable_graphs(context)
            context.immutable_state = _immutable_state(context)
            context.stage = _work.stage = "retirement"
            multi._claim_for_environment(
                request.caller_owner, expected=parent, transition=context.retirement
            )
            context.stage = _work.stage = "namespace"
            context.methods = _namespace(context)
            context.namespace_bindings = _namespace_bindings(context)
            context.namespace_constants = geometry._namespace_constants(context.methods)
            context.check = lambda: _check(context)

            def read_observer(kind, raw):
                _observe(context, kind, raw)
                # During a native getter unwind, defer capture failure so its
                # primary exception/cause survives the descriptor's finally.
                if sys.exception() is None:
                    _stop(context)

            context.observe = read_observer
            context.read_callbacks = (
                *aliases._atoms(context.check),
                *aliases._atoms(context.observe),
            )
            context.active = True
            with _locals(context):
                for name in METHODS:
                    context.stage = _work.stage = name
                    _check(context)
                    context.executing = True
                    try:
                        if name == "makeECM":
                            with aliases.reading(parent.p, context):
                                _invoke_method(context, name)
                        else:
                            _invoke_method(context, name)
                    finally:
                        context.executing = False
                    _stop(context)
                    try:
                        context.stages.append((name, _snapshot(context)))
                    except Exception as capture:
                        geometry._remember_observation_error(
                            context, capture, origin="stage_snapshot", raw=parent.caller
                        )
                        raise _CaptureStop() from capture
                    _check(context)
            context.finished = True
            context.stage = _work.stage = "source_checks"
            _check(context)
        except Exception as failure:
            if not isinstance(failure, _CaptureStop):
                error = failure
        finally:
            context.active = context.executing = False
    partial = dict(
        context=context,
        parent_trial=context.prior_trial,
        caller=parent.caller,
        parameters=parent.p,
        mesh=parent.kernel,
        mask=parent.mask,
        rng=parent.rng,
        parameter_info=context.parameter_info,
        grid=context.grid,
        trees=context.trees,
        raw_locals=context.locals,
        helper_results=context.helper_results,
        last_completed_helper=getattr(context, "last_completed_helper", None),
        warnings=caught,
        events=context.events,
        logs=context.logs,
        stages=context.stages,
        work=_work.work,
        stage=context.stage,
        observation_errors=context.observation_errors,
        observation_raw=context.observation_raw,
        caller_consumed=request.caller_owner in multi._FORWARDED,
        usable_environment_child_available=False,
    )
    if context.observation_error is not None:
        raise EnvironmentRejected(
            "Multi-cell observation failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=context.observation_error,
        ) from (error if error is not None else context.observation_error)
    try:
        trial = Trial(
            request.identity,
            context.prior_trial.identity,
            context.before,
            _snapshot(context),
            tuple(context.stages),
            tuple(name for name, _ in context.events),
            tuple(dict(e) for e in _work.work),
            context.stream_before,
            multi.initial._rng_stream(parent.rng),
            tuple(str(item.message) for item in caught),
            error is None,
            None if error is None else context.stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise EnvironmentRejected(
            "Multi-cell trial sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error if error is not None else capture)
    if error is not None:
        raise EnvironmentRejected(
            "Original multi-cell ordinary source failed",
            stage=context.stage,
            request=request,
            trial=trial,
            partial=partial,
            source_error=error,
        ) from error
    try:
        context.trial = trial
        _check(context)
        context.graphs = _graphs(context)
        child = object.__new__(EnvironmentOwner)
        _ISSUED[child] = context
        return child
    except Exception as capture:
        raise EnvironmentRejected(
            "Multi-cell child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture


def prepare(request):
    if (
        type(request) is not Request
        or type(request.caller_request) is not multi.OrdinaryRequest
        or core.records._digest(dict(law=LAW_ID, caller=request.caller_request.identity))
        != request.identity
    ):
        raise EnvironmentRejected(
            "Typed fresh descriptor-bearing prefix required", stage="request_owner"
        )
    work = SimpleNamespace(stage="multi_caller_prefix", work=[], parent=None)
    try:
        work.parent = multi.prepare(request.caller_request)
        # Complete non-additive composition: copy the sealed prefix attempt
        # ledger once, then append only continuation attempts. Authentication,
        # descriptor construction and failed native entries stay in that prefix.
        retained = tuple(dict(row) for row in work.parent.trial.work)
        work.work[:] = [
            dict(row, sequence=i, component="multi_caller_prefix") for i, row in enumerate(retained)
        ]
        with _account(work):
            return prepare_continuation(from_caller(work.parent, law_id=LAW_ID), _work=work)
    except Exception as error:
        raw = getattr(error, "partial", None)
        if work.parent is None and isinstance(raw, dict) and isinstance(raw.get("work"), list):
            work.work[:] = [dict(row) for row in raw["work"]]
        raise EnvironmentRejected(
            "Owned multi-cell prefix failed",
            stage=work.stage,
            request=request,
            partial=dict(parent=work.parent, prefix=work, work=work.work, source_partial=raw),
            source_error=error,
        ) from error


def require_Poisson(owner, *, phase=None):
    context = _validate(owner)
    raise EnvironmentRejected(
        "Multi-cell Poisson/full phase continuation remains held",
        stage="Poisson_held",
        trial=context.trial,
        partial=dict(
            invalidated_owners=INVALIDATED_OWNERS,
            supplied_phase=phase,
            physical_checkpoint_admitted=False,
        ),
    )
