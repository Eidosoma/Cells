"""Owned multi-cell make_world data tail; no phase or physical-world admission.

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
from cells.processes import betse_native_multi_cell_poisson as poisson

environment, multi, core, geometry, aliases = (
    poisson.environment,
    poisson.multi,
    poisson.core,
    poisson.geometry,
    poisson.aliases,
)
LAW_ID = "betse_owned_non_SVG_multi_cell_make_world_data_tail@1"
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
_FORWARDED = WeakKeyDictionary()
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


def _contexts(context):
    return context.parent, context.parent.parent, _prefix(context)


def _parent_fields(context):
    # Context objects are retained as actual references. Nothing here is a
    # stand-in caller, hydration input or replacement scientific state.
    return tuple(tuple(vars(parent).items()) for parent in _contexts(context))


def _registry_links(context):
    parent, env, prefix = _contexts(context)
    caller_prefix = multi._authority(env.request.caller_owner)
    caller_retirement = multi._FORWARDED.get(env.request.caller_owner)
    if caller_prefix is not prefix or caller_retirement is not env.retirement:
        raise ValueError("Original multi-cell caller issuance or retirement link changed")
    mesh = prefix.kernel
    rng_wrapper = mesh._cells_rng
    return (
        poisson._authority(context.request.poisson_owner),
        environment._authority(parent.request.environment_owner),
        environment._FORWARDED.get(parent.request.environment_owner),
        caller_prefix,
        caller_retirement,
        environment._GRIDS.get(env.grid),
        poisson._GRIDS.get(env.grid),
        prefix.caller.mesh,
        prefix.caller.grid_obj,
        mesh.image_mask,
        mesh._cells_observer,
        rng_wrapper,
        rng_wrapper.observer,
        getattr(rng_wrapper, "rng", None),
        multi._ACTIVE.get(mesh),
        *[environment._TREES.get(tree) for tree in env.trees],
    )


def _inherited_bindings(context):
    parent, env, prefix = _contexts(context)
    functions = (
        poisson._check,
        poisson._validate,
        poisson._observation,
        poisson._snapshot,
        poisson._graphs,
        poisson._claim_for_world_tail,
        environment._check,
        environment._bindings,
        environment._namespace_bindings,
        multi._check,
        multi._bindings,
        multi._namespace_bindings,
    )
    result = (
        *poisson._bindings(),
        *environment._bindings(),
        *multi._bindings(),
        *poisson._namespace_bindings(parent),
        *(atom for function in functions for atom in aliases._atoms(function)),
        *aliases._dispatch_bindings(type(prefix.caller)),
    )
    if hasattr(env, "methods"):
        result += environment._namespace_bindings(env)
    if hasattr(env, "read_callbacks"):
        result += (*aliases._atoms(env.check), *aliases._atoms(env.observe))
    if hasattr(prefix, "caller_method"):
        result += multi._namespace_bindings(prefix)
    return result


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
        _check_inherited,
        _claim_for_post_world_operators,
        _scope,
    )
    return (
        source.np,
        STORES,
        source.STORE_NAMES,
        source.STORE_LINES,
        *poisson._observation_bindings(),
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


def from_lifecycle(request, state, configuration, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise FinalizationRejected("Explicit data-tail law required", stage="opt_in")
    parent = poisson.from_lifecycle(request, state, configuration, law_id=poisson.LAW_ID)
    return Request(parent, core.records._digest(dict(law=LAW_ID, poisson=parent.identity)))


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
            "Complete issued multi-cell Poisson required", stage="poisson_owner"
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
        raise environment._CaptureStop()


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
    environment._observe(context, name + "_enter", (args, kwargs))
    _stop(context)
    context.helper_busy = True
    try:
        result = delegate(*args, **kwargs)
    except Exception:
        environment._observe(context, name + "_unwind", (args, kwargs))
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
    environment._observe(context, name + "_return", result)
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
    # Same canonical cache schema and complete operator columns. The accepted
    # producer sees the actual continuing caller, including its six new fields.
    return _scope(context).snapshot(
        dict(
            poisson=poisson._snapshot(context.parent).identity,
            caller=multi._project(
                _prefix(context),
                {
                    name: value
                    for name, value in multi.callers._public(_prefix(context).caller).items()
                    if name not in {"mesh", "grid_obj", "points_tree"}
                },
            ),
            retained_tail=context.original_fields,
            helpers=context.helpers,
        )
    )


def _immutable_state(context):
    parent, env, prefix = _contexts(context)
    caller = {
        name: value
        for name, value in multi.callers._public(prefix.caller).items()
        if name not in {*STORES, "mesh", "grid_obj", "points_tree"}
    }
    return _scope(context).snapshot(
        dict(
            caller=multi._project(prefix, caller),
            mesh=multi._project(prefix, multi.initial._public_cache(prefix.kernel)),
            parameters=multi.callers._parameters(prefix.p),
            grid=dict(vars(env.grid)),
            trees=[environment._tree_state(tree) for tree in env.trees],
            original_tail=context.original_fields,
            results=parent.results,
            helpers=parent.helper_results,
            inputs=parent.helper_inputs,
            RNG=core.initial._rng_stream(prefix.rng).identity,
            image=multi._image_state(prefix).identity,
        )
    )


def _immutable_graphs(context):
    parent, env, prefix = _contexts(context)
    view = context.original_view
    vars(view).clear()
    vars(view).update(
        (name, value) for name, value in vars(prefix.caller).items() if name not in STORES
    )
    view._cells_actual_caller = prefix.caller
    view._cells_original_tail = context.original_fields
    view._cells_operator_evidence = parent.raw_state
    scope = _scope(context)
    graphs = [
        scope.graph(view, prefix.p, prefix.tape),
        scope.graph(prefix.kernel, prefix.p, prefix.tape),
        multi.images._graph(prefix.image_tape),
        scope.graph(env.grid, prefix.p, prefix.tape),
    ]
    for tree in env.trees:
        record = environment._TREES[tree]
        vars(record.view).clear()
        vars(record.view).update(environment._tree_state(tree))
        record.view.native_tree = tree
        graphs.append(scope.graph(record.view, prefix.p, record.tape))
    return tuple(graphs)


def _graphs(context):
    return (
        *poisson._graphs(context.parent),
        _scope(context).graph(context.raw_state, _prefix(context).p, _prefix(context).tape),
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


def _check_inherited(context):
    parent, env, prefix = _contexts(context)
    if (
        poisson._authority(context.request.poisson_owner) is not parent
        or parent.invalid
        or parent.active
        or parent.thread != get_ident()
        or parent.trial is not context.prior_trial
        or core.records._digest(poisson.trial_record(parent.trial)) != context.parent_signature
        or poisson._FORWARDED.get(context.request.poisson_owner) is not context.retirement
        or _scope(context).roles.keys() != context.operator_roles.keys()
        or any(
            _scope(context).roles[name] is not value
            for name, value in context.operator_roles.items()
        )
    ):
        raise ValueError("Original Poisson parent/trial/claim/operator identities changed")
    for current, old in zip(_parent_fields(context), context.parent_fields, strict=True):
        if len(current) != len(old) or any(
            name != old_name or value is not old_value
            for (name, value), (old_name, old_value) in zip(current, old, strict=True)
        ):
            raise ValueError("Retained original source context changed")
    multi.accounting._check_binding_identity(_registry_links(context), context.registry_links)
    multi.accounting._check_binding_identity(
        _inherited_bindings(context), context.inherited_bindings
    )
    if poisson._defaults() != parent.defaults:
        raise ValueError("Original completed Poisson default arguments changed")
    info = getattr(prefix, "parameter_info", None)
    if info is not None:
        aliases.validate(info)
        if env.parameter_info is not info or type(prefix.p) is not info.runtime:
            raise ValueError("Original fresh descriptor-bearing parameter ownership changed")
        environment._require_descriptor_read(env)
    if hasattr(env, "namespace_constants") and (
        geometry._namespace_constants(env.methods) != env.namespace_constants
    ):
        raise ValueError("Inherited exact geometry constants changed")
    multi.accounting._check_binding_identity(_bindings(), context.bindings)
    if hasattr(context, "methods"):
        multi.accounting._check_binding_identity(
            _namespace_bindings(context), context.namespace_bindings
        )
    if _verify_sources() != context.producers:
        raise ValueError("Native data-tail/inherited source authority changed")


def _check(context):
    _check_inherited(context)
    parent = context.parent
    if _immutable_state(context).identity != context.immutable_state.identity:
        raise ValueError("Preexisting caller/mesh/grid/parameter/image/RNG/operator bytes changed")
    geometry.meshes._same_graphs(_immutable_graphs(context), context.immutable_graphs)
    _check_fields(context)
    if context.finished and (
        context.applied != list(STORES)
        or [name for name, _ in context.helpers] != ["asarray", "ones"]
    ):
        raise ValueError("Six-store data-tail completion/helper order changed")
    if context.finished:
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
        raise TypeError("Use the owned multi-cell data-tail entry")

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
            "Issued multi-cell data-tail owner unavailable", stage="world_data_owner"
        )
    return _ISSUED[owner]


def _validate(owner):
    context = _authority(owner)
    if owner in _FORWARDED:
        raise FinalizationRejected(
            "World data epoch was consumed by a post-world operator attempt",
            stage="world_data_epoch_consumed",
            request=context.request,
            trial=context.trial,
        )
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


def _claim_for_post_world_operators(owner, *, expected, transition):
    """Irreversible claim after validating this exact source owner once."""
    with _LOCK:
        if transition is None or owner in _FORWARDED or _validate(owner) is not expected:
            raise FinalizationRejected(
                "World data continuation already claimed or changed",
                stage="world_data_epoch_consumed",
                trial=getattr(expected, "trial", None),
            )
        _FORWARDED[owner] = transition


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
    environment._observe(context, name + "_enter", _prefix(context).caller)
    _stop(context)
    context.executing = True
    try:
        result = context.methods[name](_prefix(context).caller)
    except Exception:
        environment._observe(context, name + "_unwind", _prefix(context).caller)
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
    environment._observe(context, name + "_return", result)
    _stop(context)
    _check(context)
    return result


def prepare_continuation(request, *, _work=None):
    if type(request) is not ContinuationRequest:
        raise FinalizationRejected(
            "Typed issued multi-cell Poisson owner required", stage="request_owner"
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
                        raise environment._CaptureStop() from capture
            context.finished = True
            context.stage = "source_checks"
            _check(context)
        except Exception as failure:
            if not isinstance(failure, environment._CaptureStop):
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
        mesh=getattr(prefix, "kernel", None),
        rng=getattr(prefix, "rng", None),
        mask=getattr(prefix, "mask", None),
        grid=getattr(getattr(parent, "parent", None), "grid", None),
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
            "Typed fresh multi-cell data-tail request required", stage="request_owner"
        )
    work = SimpleNamespace(stage="poisson_prefix", work=[], parent=None)
    try:
        work.parent = poisson.prepare(request.poisson_request)
        work.work[:] = [
            dict(row, sequence=index, component="multi_Poisson_prefix")
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
