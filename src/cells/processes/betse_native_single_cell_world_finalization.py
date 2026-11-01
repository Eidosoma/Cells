"""Owned single-cell make_world data tail; no phase or physical-world admission.

Only six original stores may change the issued continuing caller. The original
Poisson/environment handles stay consumed; their pre-tail caches are evidence,
never validators against the legitimately coerced cell_i or new defaults.
"""

import ast
import builtins
import hashlib
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_make_world_tail_source as source
from cells.processes import betse_native_single_cell_poisson as poisson

environment, ecm, geometry, core = poisson.environment, poisson.ecm, poisson.geometry, poisson.core
completion, parameters, meshes, callers = (
    geometry.completion,
    geometry.parameters,
    geometry.meshes,
    geometry.callers,
)
images, aliases = meshes.images, ecm.aliases
LAW_ID = "betse_owned_single_cell_make_world_data_tail@1"
INVALIDATED_OWNERS = poisson.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
METHODS = (
    "clear_lapGJinv",
    "clear_lapGJ",
    "clear_M_sum_mem_to_ecm",
    "clear_gradMem",
    "coerce_cell_i",
    "default_gj_weights",
)
STORES = source.STORE_NAMES
_NATIVE = {name: getattr(source.CellsWorldTail, name) for name in METHODS}
_ASARRAY, _ONES, _LEN = source.np.asarray, source.np.ones, builtins.len
_ISSUED = WeakKeyDictionary()
_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class Request:
    poisson_request: poisson.Request
    identity: str


@dataclass(frozen=True, slots=True)
class ContinuationRequest:
    poisson_owner: poisson.PoissonOwner
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
    source_completed: bool
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class FinalizationRejected(poisson.PoissonRejected):
    pass


def _verify_sources():
    pins = poisson._verify_sources()
    original_path = geometry.callers.NATIVE_ROOT / "betse/science/cells.py"
    if hashlib.sha256(original_path.read_bytes()).hexdigest() != source.CELLS_SHA256:
        raise ValueError("Original make_world data-tail authority changed")
    native = next(
        node
        for node in ast.parse(original_path.read_text()).body
        if isinstance(node, ast.ClassDef) and node.name == "Cells"
    )
    world = next(
        node
        for node in native.body
        if isinstance(node, ast.FunctionDef) and node.name == "make_world"
    )
    selected = [node for node in world.body if node.lineno in source.STORE_LINES]
    owned = next(
        node
        for node in ast.parse(Path(source.__file__).read_text()).body
        if isinstance(node, ast.ClassDef) and node.name == "CellsWorldTail"
    )
    methods = [
        next(node for node in owned.body if isinstance(node, ast.FunctionDef) and node.name == name)
        for name in METHODS
    ]
    if len(selected) != 6 or source.STORE_LINES != (517, 518, 521, 522, 525, 526):
        raise ValueError("Exact six native tail statements required")
    if tuple(node.targets[0].attr for node in selected) != STORES:
        raise ValueError("Native tail store roster/order changed")
    for statement, method in zip(selected, methods, strict=True):
        if (
            len(method.body) != 1
            or ast.dump(statement) != ast.dump(method.body[0])
            or [arg.arg for arg in method.args.args] != ["self"]
        ):
            raise ValueError("Literal make_world data store changed")
    for module in (source, sys.modules[__name__]):
        path = Path(module.__file__).resolve()
        pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pins


def _prefix(context):
    return poisson._prefix(context.parent)


def _scope(context):
    return poisson._observation(context.parent)


def _parts(context):
    parent = context.parent
    env = parent.parent
    grid = env.parent
    geometric = grid.parent
    caller = geometric.parent
    mesh = caller.mesh_context
    parameter = parameters._authority(caller.parameter_owner)
    return parent, env, grid, geometric, caller, mesh, parameter


def _contexts(context):
    return _parts(context)


def _parent_fields(context):
    parts = _parts(context)
    objects = (*parts, parts[5].parent_caller, parts[5].parent_image)
    return tuple(
        (
            ("actual_context", value),
            *tuple((value if isinstance(value, dict) else vars(value)).items()),
        )
        for value in objects
    )


def _registry_links(context):
    parent, env, grid, geometric, caller, mesh, parameter = _parts(context)
    links = (
        (poisson._authority(context.request.poisson_owner), parent),
        (environment._authority(parent.request.environment_owner), env),
        (environment._FORWARDED.get(parent.request.environment_owner), parent.retirement),
        (ecm._authority(env.request.ecm_owner), grid),
        (ecm._FORWARDED.get(env.request.ecm_owner), env.retirement),
        (geometry._authority(grid.request.geometry_owner), geometric),
        (geometry._FORWARDED.get(grid.request.geometry_owner), grid.retirement),
        (completion._authority(geometric.request.caller_owner), caller),
        (completion._FORWARDED.get(geometric.request.caller_owner), geometric.retirement),
        (meshes._authority(caller.request.mesh_owner), mesh),
        (meshes._FORWARDED.get(caller.request.mesh_owner), caller.retirement),
        (images._authority(mesh.request.image_owner), mesh.parent_image),
        (callers._authority(mesh.parent_image["request"].caller), mesh.parent_caller),
        (callers._retirement_token(mesh.parent_image["request"].caller), mesh.retirement),
        (parameters._CLAIMED.get(caller.parameter_owner), mesh.parent_caller["request"]),
        (parameter.p, caller.p),
        (parameter.trial, caller.parameter_trial),
        (parameter.descriptor_info, grid.parameter_info),
        (ecm._GRIDS.get(grid.grid), grid),
        (poisson._GRIDS.get(grid.grid), parent),
        (caller.caller.mesh, mesh.kernel),
        (caller.caller.grid_obj, grid.grid),
        (mesh.kernel._cells_observer, mesh.observer),
        (mesh.kernel._cells_rng, caller.rng_wrapper),
        (mesh.kernel._cells_rng.observer, mesh.observer),
        (mesh.kernel._cells_rng.rng, caller.rng),
        (mesh.rng, caller.rng),
        (mesh.parent_caller["parameters"], caller.p),
    )
    if (
        any(actual is not expected for actual, expected in links)
        or mesh.parent_caller["invalid"]
        or mesh.parent_image["invalid"]
        or not mesh.parent_caller.get("continuation_consumed")
        or not mesh.parent_image.get("continuation_consumed")
    ):
        raise ValueError(
            "Original single-cell issuance, retirement, parameter or observer relationship changed"
        )
    return (
        *[actual for actual, _ in links],
        parameter,
        meshes._ACTIVE.get(mesh.kernel),
        parameters._ACTIVE.get(caller.p),
        *[environment._TREES.get(tree) for tree in env.trees],
    )


def _inherited_bindings(context):
    parent, env, grid, geometric, caller, mesh, parameter = _parts(context)
    modules = (poisson, environment, ecm, geometry, completion, meshes, parameters)
    functions = (
        poisson._check,
        poisson._validate,
        poisson._observation,
        poisson._snapshot,
        poisson._graphs,
        poisson._claim_for_world_tail,
        environment._check,
        ecm._check,
        geometry._check,
        completion._check_runtime_authority,
        parameters._validate_binding,
        callers._authority,
        callers._retirement_token,
        images._authority,
        _image_state,
        _observer_state,
    )
    values = tuple(atom for module in modules for atom in module._bindings())
    values += (
        *callers._bindings(caller.caller),
        *poisson._namespace_bindings(parent),
        *environment._namespace_bindings(env.methods),
        *ecm._namespace_bindings(grid.method),
        *geometry._namespace_bindings(geometric.methods, geometric),
        *(atom for function in functions for atom in aliases._atoms(function)),
    )
    for cls in (type(caller.caller), type(caller.p), type(mesh.kernel), type(grid.grid)):
        values += aliases._dispatch_bindings(cls)
        values += tuple(
            atom
            for base in cls.__mro__
            for fn in vars(base).values()
            if isinstance(fn, FunctionType)
            for atom in aliases._atoms(fn)
        )
    # cell_grid runs its original globals, independently of the copied makeECM
    # namespace. Retain exactly the reached helper closure, without patching it.
    native_np = ecm._GRID.__globals__.get("np")
    values += (native_np,)
    if native_np is not None:
        values += tuple(
            atom
            for name in ("linspace", "meshgrid", "column_stack", "asarray")
            for atom in aliases._atoms(getattr(native_np, name))
        )
    values += (*aliases._atoms(grid.check), *aliases._atoms(grid.observe))
    return values


def _bindings():
    functions = (
        *_NATIVE.values(),
        _ASARRAY,
        _ONES,
        _LEN,
        source.np.asarray,
        source.np.ones,
        builtins.len,
        *[getattr(source.CellsWorldTail, name) for name in METHODS],
        _helper,
        _invoke,
        _namespace,
        _namespace_bindings,
        _parent_fields,
        _registry_links,
        _inherited_bindings,
        _immutable_state,
        _immutable_graphs,
        _check_fields,
        _scope,
    )
    return (
        source.np,
        STORES,
        source.STORE_NAMES,
        source.STORE_LINES,
        *poisson.observation.bindings(environment),
        *(
            atom
            for function in functions
            for value in (
                function,
                getattr(function, "__wrapped__", None),
                getattr(function, "_implementation", None),
            )
            for atom in aliases._atoms(value)
        ),
    )


def from_core(parent, configuration, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise FinalizationRejected("Explicit single-cell data-tail law required", stage="opt_in")
    request = poisson.from_core(parent, configuration, law_id=poisson.LAW_ID)
    return Request(request, core.records._digest(dict(law=LAW_ID, poisson=request.identity)))


def request_record(request):
    parent = poisson._authority(request.poisson_owner)
    return dict(
        law=LAW_ID,
        parent=parent.trial.identity,
        methods=METHODS,
        stores=STORES,
        native_lines=source.STORE_LINES,
        boundary="after six data stores only",
        gap_junction_Laplacian_constructed=False,
        full_make_world_phase_physical_checkpoint=False,
        invalidated_owners=INVALIDATED_OWNERS,
        observation_policy=poisson.observation.specification(),
    )


def _preflight(owner):
    parent = poisson._validate(owner)
    if not parent.finished or not parent.trial.source_completed:
        raise FinalizationRejected(
            "Complete issued single-cell Poisson required", stage="poisson_owner"
        )
    return parent


def from_poisson(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise FinalizationRejected("Explicit data-tail law required", stage="opt_in")
    _preflight(owner)
    request = ContinuationRequest(owner, "")
    return replace(request, identity=core.records._digest(request_record(request)))


def _stop(context):
    if context.observation_error is not None:
        raise ecm._CaptureStop()


def _helper(context, name, delegate, *args, **kwargs):
    _stop(context)
    _check(context)
    if (
        not context.active
        or not context.executing
        or context.helper_busy
        or context.thread != get_ident()
    ):
        raise FinalizationRejected(
            "Tail helper lacks active original caller", stage="source_call_unavailable"
        )
    caller = _prefix(context).caller
    frame = sys._getframe(2)
    method = context.methods[context.stage]
    expected = (
        "asarray"
        if context.stage == METHODS[4]
        else "ones"
        if context.stage == METHODS[5]
        else None
    )
    if (
        name != expected
        or kwargs
        or len(args) != 1
        or frame.f_code is not method.__code__
        or frame.f_globals is not method.__globals__
        or frame.f_locals.get("self") is not caller
        or any(record[0] == name for record in context.helpers)
        or name == "asarray"
        and args[0] is not context.original_fields["cell_i"]
        or name == "ones"
        and (type(args[0]) is not int or args[0] != _LEN(caller.mem_i))
    ):
        raise FinalizationRejected("Literal tail helper/input/order changed", stage="helper_order")
    ecm._observe(context, name + "_enter", (args, kwargs))
    _stop(context)
    context.helper_busy = True
    try:
        result = delegate(*args, **kwargs)
    except Exception:
        ecm._observe(context, name + "_unwind", (args, kwargs))
        raise
    finally:
        context.helper_busy = False
    context.last_completed_helper = (name, result)
    if name == "ones":
        value = result
        while isinstance(value, source.np.ndarray):
            if any(value is original for original in context.preexisting_objects):
                raise ValueError("Native weights allocation aliases a preexisting source object")
            value = value.base
    try:
        context.helpers.append((name, result))
    except Exception as capture:
        geometry._remember_observation_error(context, capture, origin="helper_result", raw=result)
    ecm._observe(context, name + "_return", result)
    _stop(context)
    _check(context)
    return result


def _namespace(context):
    def asarray(*args, **kwargs):
        return _helper(context, "asarray", _ASARRAY, *args, **kwargs)

    def ones(*args, **kwargs):
        return _helper(context, "ones", _ONES, *args, **kwargs)

    namespace = dict(source.__dict__, np=SimpleNamespace(asarray=asarray, ones=ones), len=_LEN)
    return {
        name: FunctionType(
            function.__code__,
            namespace,
            function.__name__,
            function.__defaults__,
            function.__closure__,
        )
        for name, function in _NATIVE.items()
    }


def _namespace_bindings(context):
    namespace = context.methods[METHODS[0]].__globals__
    return (
        namespace["np"],
        *(
            atom
            for function in (
                *context.methods.values(),
                namespace["np"].asarray,
                namespace["np"].ones,
                namespace["len"],
            )
            for atom in aliases._atoms(function)
        ),
    )


def _snapshot(context):
    caller = {
        name: value
        for name, value in callers._public(_prefix(context).caller).items()
        if name not in {"mesh", "grid_obj", "points_tree"}
    }
    return _scope(context).snapshot(
        dict(
            poisson=poisson._snapshot(context.parent).identity,
            caller=caller,
            retained_tail=context.original_fields,
            helpers=context.helpers,
        )
    )


def _image_state(prefix):
    mesh = prefix.mesh_context
    prelude = mesh.parent_caller["request"].core_request.initial_request.upstream[2]
    images._file_bytes(prelude.image)
    return images._audit(mesh.parent_image["tape"], prelude)


def _observer_state(prefix):
    observer = prefix.mesh_context.observer
    return core.caches.snapshot(
        dict(
            stack=observer.stack,
            ids=observer.ids,
            events=[
                (event.sequence, event.kind, event.method, event.depth, event.payload.identity)
                for event in observer.events
            ],
        )
    )


def _immutable_state(context):
    parent, env, grid, geometric, caller, mesh, parameter = _parts(context)
    fields = {
        name: value
        for name, value in callers._public(caller.caller).items()
        if name not in {*STORES, "mesh", "grid_obj", "points_tree"}
    }
    return _scope(context).snapshot(
        dict(
            caller=fields,
            mesh=core.initial._public_cache(mesh.kernel),
            parameters=callers._parameters(caller.p),
            grid=dict(vars(grid.grid)),
            trees=[environment._tree_state(tree) for tree in env.trees],
            original_tail=context.original_fields,
            results=parent.results,
            helpers=parent.helper_results,
            inputs=parent.helper_inputs,
            RNG=core.initial._rng_stream(caller.rng).identity,
            image=_image_state(caller).identity,
            observer=_observer_state(caller).identity,
        )
    )


def _immutable_graphs(context):
    parent, env, grid, geometric, caller, mesh, parameter = _parts(context)
    view = context.original_view
    vars(view).clear()
    vars(view).update(
        (name, value) for name, value in vars(caller.caller).items() if name not in STORES
    )
    view._cells_actual_caller = caller.caller
    view._cells_original_tail = context.original_fields
    view._cells_operator_evidence = parent.raw_state
    scope = _scope(context)
    graphs = [
        scope.graph(view, caller.p, mesh.graph_tape),
        scope.graph(mesh.kernel, caller.p, mesh.graph_tape),
        images._graph(mesh.parent_image["tape"]),
        scope.graph(grid.grid, caller.p, mesh.graph_tape),
    ]
    for tree in env.trees:
        record = environment._TREES[tree]
        vars(record.view).clear()
        vars(record.view).update(environment._tree_state(tree))
        record.view.native_tree = tree
        graphs.append(scope.graph(record.view, caller.p, record.tape))
    return tuple(graphs)


def _graphs(context):
    return (
        *poisson._graphs(context.parent),
        _scope(context).graph(
            context.raw_state, _prefix(context).p, _prefix(context).mesh_context.graph_tape
        ),
    )


def _check_fields(context):
    caller = _prefix(context).caller
    for index, name in enumerate(STORES):
        if name in context.applied:
            expected = (
                None
                if index < 4
                else next(
                    result
                    for helper, result in context.helpers
                    if helper == ("asarray" if index == 4 else "ones")
                )
            )
            if getattr(caller, name) is not expected:
                raise ValueError("Completed native data-tail assignment changed: " + name)
        elif (
            (name in vars(caller)) != (name in context.original_fields)
            or name in context.original_fields
            and getattr(caller, name) is not context.original_fields[name]
        ):
            raise ValueError("Unreached data-tail field changed: " + name)
    for name, cache in context.output_snapshots.items():
        core.caches.validate(cache)
        if _scope(context).snapshot(getattr(caller, name)).identity != cache.identity:
            raise ValueError("Completed tail output bytes changed: " + name)


def _check(context):
    parent, env, grid, geometric, caller, mesh, parameter = _parts(context)
    if (
        poisson._authority(context.request.poisson_owner) is not parent
        or parent.invalid
        or parent.active
        or parent.thread != get_ident()
        or parent.trial is not context.prior_trial
        or core.records._digest(poisson.trial_record(parent.trial)) != context.parent_signature
        or poisson._FORWARDED.get(context.request.poisson_owner) is not context.retirement
        or tuple(_scope(context).roles) != tuple(context.operator_roles)
        or len(_scope(context).roots) != 6
        or any(
            _scope(context).roles[name] is not value
            for name, value in context.operator_roles.items()
        )
    ):
        raise ValueError(
            "Original single-cell Poisson parent, claim, trial or six operator roots changed"
        )
    for current, old in zip(_parent_fields(context), context.parent_fields, strict=True):
        if len(current) != len(old) or any(
            name != old_name or value is not old_value
            for (name, value), (old_name, old_value) in zip(current, old, strict=True)
        ):
            raise ValueError("Retained original single-cell context changed")
    completion._check_binding_identity(_registry_links(context), context.registry_links)
    completion._check_binding_identity(_inherited_bindings(context), context.inherited_bindings)
    completion._check_binding_identity(_bindings(), context.bindings)
    if hasattr(context, "methods"):
        completion._check_binding_identity(_namespace_bindings(context), context.namespace_bindings)
    if poisson._defaults() != parent.defaults or _verify_sources() != context.producers:
        raise ValueError("Original source, helper or Poisson default authority changed")
    aliases.validate(grid.parameter_info)
    ecm._require_descriptor_read(grid)
    if (
        parameter.descriptor_info is not grid.parameter_info
        or type(caller.p) is not parameter.runtime
        or caller.p._conf is not parameter.configuration
        or parameter.request.projection != parameters.ENVIRONMENT
        or parameter.trial.store_roster != parameters._projection(parameters.ENVIRONMENT)[3]
        or parameter.trial.store_lines != tuple(environment.source.STORE_LINES)
    ):
        raise ValueError("Original single-cell ENV13 parameter projection/descriptor changed")
    if geometry._namespace_constants(geometric.methods) != geometric.namespace_constants:
        raise ValueError("Inherited exact geometry constants changed")
    if _immutable_state(context).identity != context.immutable_state.identity:
        raise ValueError(
            "Preexisting single-cell caller/parameter/mesh/image/grid/RNG/operator bytes changed"
        )
    meshes._same_graphs(_immutable_graphs(context), context.immutable_graphs)
    _check_fields(context)
    if context.finished:
        if context.applied != list(STORES) or [name for name, _ in context.helpers] != [
            "asarray",
            "ones",
        ]:
            raise ValueError("Six-store single-cell completion/helper order changed")
        for cache in (
            parent.trial.before,
            parent.trial.cache,
            *(cache for _, cache in parent.trial.stages),
        ):
            core.caches.validate(cache)


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
        source_completed=trial.source_completed,
        failure_stage=trial.failure_stage,
        failure_type=trial.failure_type,
        failure_message=trial.failure_message,
        stores=STORES,
        native_lines=source.STORE_LINES,
        gap_junction_Laplacian_constructed=False,
        full_make_world_phase_physical_checkpoint=False,
        invalidated_owners=INVALIDATED_OWNERS,
        observation_policy=poisson.observation.specification(),
    )


class WorldDataOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the owned single-cell data-tail entry")

    def __reduce_ex__(self, protocol):
        raise TypeError("Process-local data-tail authority cannot be serialized")

    @property
    def cells(self):
        return _prefix(_validate(self)).caller

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not WorldDataOwner or owner not in _ISSUED:
        raise FinalizationRejected(
            "Issued single-cell data-tail owner unavailable", stage="world_data_owner"
        )
    return _ISSUED[owner]


def _validate(owner):
    context = _authority(owner)
    try:
        if context.invalid or context.active or context.thread != get_ident():
            raise ValueError("Invalid completed data-tail epoch")
        _check(context)
        if (
            _snapshot(context).identity != context.trial.cache.identity
            or core.records._digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Changed sealed data-tail source state")
        geometry.meshes._same_graphs(_graphs(context), context.graphs)
        for cache in (
            context.trial.before,
            context.trial.cache,
            *(cache for _, cache in context.trial.stages),
        ):
            core.caches.validate(cache)
    except Exception as error:
        context.invalid = True
        raise FinalizationRejected(
            "Stale data-tail source owner",
            stage="world_data_drift",
            request=context.request,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


@contextmanager
def _account(work):
    with poisson._account(work):
        previous = sys.getprofile()

        def profile(frame, event, arg):
            module = frame.f_globals.get("__name__", "")
            if event == "call" and (
                module == source.__name__
                or module == __name__
                and frame.f_code.co_name in {"_invoke", "_helper"}
            ):
                if len(work.work) >= 100000:
                    raise ValueError("Bounded prefix work ledger exhausted")
                work.work.append(
                    dict(
                        sequence=len(work.work),
                        phase=work.stage,
                        layer="body" if module == source.__name__ else "tail_wrapper",
                        module=module,
                        method=frame.f_code.co_qualname,
                        entry_method=frame.f_code.co_name,
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


@contextmanager
def _locals(context):
    previous = sys.getprofile()
    codes = {function.__code__: name for name, function in context.methods.items()}

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


def _invoke(context, name):
    _stop(context)
    _check(context)
    ecm._observe(context, name + "_enter", _prefix(context).caller)
    _stop(context)
    context.executing = True
    try:
        result = context.methods[name](_prefix(context).caller)
    except Exception:
        ecm._observe(context, name + "_unwind", _prefix(context).caller)
        raise
    finally:
        context.executing = False
    context.last_completed_method = (name, result)
    _stop(context)
    try:
        context.applied.append(STORES[METHODS.index(name)])
    except Exception as capture:
        geometry._remember_observation_error(
            context, capture, origin="completed_store", raw=_prefix(context).caller
        )
    ecm._observe(context, name + "_return", result)
    _stop(context)
    _check(context)
    return result


def prepare_continuation(request, *, _work=None):
    if type(request) is not ContinuationRequest:
        raise FinalizationRejected(
            "Typed issued single-cell Poisson owner required", stage="request_owner"
        )
    if _work is None:
        work = SimpleNamespace(stage="world_data_tail", work=[])
        with _account(work):
            return prepare_continuation(request, _work=work)
    parent = poisson._authority(request.poisson_owner)
    context = SimpleNamespace(
        request=request,
        parent=parent,
        prior_trial=parent.trial,
        retirement=object(),
        thread=get_ident(),
        invalid=False,
        active=False,
        executing=False,
        helper_busy=False,
        finished=False,
        helpers=[],
        applied=[],
        events=[],
        stages=[],
        locals={},
        output_snapshots={},
        stage="preflight",
        prefix=_work,
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
    )
    context.raw_state = SimpleNamespace(helpers=context.helpers, applied=context.applied)
    context.original_view = SimpleNamespace()
    caller = None
    context.original_fields = {}
    error = None
    with _LOCK:
        try:
            if (
                _preflight(request.poisson_owner) is not parent
                or core.records._digest(request_record(request)) != request.identity
            ):
                raise ValueError("Changed retained data-tail request")
            caller = _prefix(context).caller
            context.original_fields = {
                name: vars(caller)[name] for name in STORES if name in vars(caller)
            }
            context.producers, context.bindings = _verify_sources(), _bindings()
            context.parent_signature = core.records._digest(poisson.trial_record(parent.trial))
            context.operator_roles = dict(_scope(context).roles)
            context.parent_fields = _parent_fields(context)
            context.registry_links = _registry_links(context)
            context.inherited_bindings = _inherited_bindings(context)
            context.before = _snapshot(context)
            context.stream_before = core.initial._rng_stream(_prefix(context).rng)
            context.immutable_state = _immutable_state(context)
            context.immutable_graphs = _immutable_graphs(context)
            context.preexisting_objects = tuple(
                value for objects, _ in context.immutable_graphs for value in objects
            )
            context.stage = "retirement"
            poisson._claim_for_world_tail(
                request.poisson_owner, expected=parent, transition=context.retirement
            )
            context.stage = "namespace"
            context.methods = _namespace(context)
            context.namespace_bindings = _namespace_bindings(context)
            context.active = True
            with _locals(context):
                for name, store in zip(METHODS, STORES, strict=True):
                    context.stage = _work.stage = name
                    _invoke(context, name)
                    try:
                        context.output_snapshots[store] = _scope(context).snapshot(
                            getattr(caller, store)
                        )
                        context.stages.append((name, _snapshot(context)))
                    except Exception as capture:
                        geometry._remember_observation_error(
                            context, capture, origin="stage_snapshot", raw=caller
                        )
                        raise ecm._CaptureStop() from capture
            context.finished = True
            context.stage = "source_checks"
            _check(context)
        except Exception as failure:
            if not isinstance(failure, ecm._CaptureStop):
                error = failure
        finally:
            context.active = context.executing = context.helper_busy = False
    try:
        prefix = _prefix(context)
    except Exception:
        prefix = None
    if caller is None:
        caller = getattr(prefix, "caller", None)
    partial = dict(
        context=context,
        parent=parent,
        parent_trial=context.prior_trial,
        caller=caller,
        parameters=getattr(prefix, "p", None),
        mesh=getattr(getattr(prefix, "mesh_context", None), "kernel", None),
        rng=getattr(prefix, "rng", None),
        mask=getattr(
            getattr(getattr(prefix, "mesh_context", None), "parent_image", {}).get("tape"),
            "mask",
            None,
        ),
        grid=getattr(getattr(getattr(parent, "parent", None), "parent", None), "grid", None),
        original_fields=context.original_fields,
        applied=context.applied,
        actual_tail_fields=None
        if caller is None
        else {name: vars(caller)[name] for name in STORES if name in vars(caller)},
        stages=context.stages,
        events=context.events,
        raw_locals=context.locals,
        helpers=context.helpers,
        last_completed_helper=getattr(context, "last_completed_helper", None),
        last_completed_method=getattr(context, "last_completed_method", None),
        work=_work.work,
        stage=context.stage,
        observation_errors=context.observation_errors,
        observation_raw=context.observation_raw,
        poisson_consumed=request.poisson_owner in poisson._FORWARDED,
        usable_data_tail_child_available=False,
    )
    if context.observation_error is not None:
        raise FinalizationRejected(
            "Data-tail observation failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=context.observation_error,
        ) from (error if error is not None else context.observation_error)
    if getattr(context, "before", None) is None or getattr(context, "stream_before", None) is None:
        raise FinalizationRejected(
            "Data-tail refused before complete baseline capture",
            stage=context.stage,
            request=request,
            trial=None,
            partial=partial,
            source_error=error,
        ) from error
    try:
        trial = Trial(
            request.identity,
            context.prior_trial.identity,
            context.before,
            _snapshot(context),
            tuple(context.stages),
            tuple(name for name, _ in context.events),
            tuple(dict(row) for row in _work.work),
            context.stream_before,
            core.initial._rng_stream(_prefix(context).rng),
            error is None,
            None if error is None else context.stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise FinalizationRejected(
            "Data-tail trial sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error if error is not None else capture)
    if error is not None:
        raise FinalizationRejected(
            "Original data-tail source failed",
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
        owner = object.__new__(WorldDataOwner)
        _ISSUED[owner] = context
        return owner
    except Exception as capture:
        raise FinalizationRejected(
            "Data-tail child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture


def prepare(request):
    if (
        type(request) is not Request
        or type(request.poisson_request) is not poisson.Request
        or request.identity
        != core.records._digest(dict(law=LAW_ID, poisson=request.poisson_request.identity))
    ):
        raise FinalizationRejected(
            "Typed fresh single-cell data-tail request required", stage="request_owner"
        )
    work = SimpleNamespace(stage="poisson_prefix", work=[], parent=None)
    try:
        work.parent = poisson.prepare(request.poisson_request)
        work.work[:] = [
            dict(row, sequence=index, component="single_Poisson_prefix")
            for index, row in enumerate(work.parent.trial.work)
        ]
        with _account(work):
            return prepare_continuation(from_poisson(work.parent, law_id=LAW_ID), _work=work)
    except Exception as error:
        raw = getattr(error, "partial", None)
        if work.parent is None and isinstance(raw, dict) and isinstance(raw.get("work"), list):
            work.work[:] = [dict(row) for row in raw["work"]]
        raise FinalizationRejected(
            "Owned data-tail prefix failed",
            stage=work.stage,
            request=request,
            partial=dict(parent=work.parent, prefix=work, work=work.work, source_partial=raw),
            source_error=error,
        ) from error


def require_full_make_world(owner, *, phase=None):
    context = _validate(owner)
    raise FinalizationRejected(
        "Data stores do not confer phase/callback/package make_world authority",
        stage="full_make_world_held",
        trial=context.trial,
        partial=dict(
            phase=phase,
            gap_junction_Laplacian_constructed=False,
            invalidated_owners=INVALIDATED_OWNERS,
            physical_checkpoint_full_world_admitted=False,
        ),
    )
