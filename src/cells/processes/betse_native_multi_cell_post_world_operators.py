"""Native post-world vectors and DEC graph operators on the actual caller.

These two selected leaf methods form a source geometry/operator prerequisite.
They do not execute seed's earlier Simulator/profile/redo_gj calls, fabricate
their phase, admit normal ECM state, or change native numerical failures.
"""

import ast
import builtins
import hashlib
import sys
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_multi_cell_world_finalization as world
from cells.processes import betse_native_post_world_operators_source as source
from cells.processes import betse_post_cut_mesh_contact_source as vectors

core, multi, geometry, aliases = world.core, world.multi, world.geometry, world.aliases
environment = world.environment
LAW_ID = "betse_owned_multi_cell_post_world_geometry_operators@1"
METHODS = ("calc_gj_vects", "graphLaplacian")
OUTPUTS = {
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
STORES = tuple(name for names in OUTPUTS.values() for name in names)
_NATIVE = dict(
    calc_gj_vects=vectors.CellKernel.calc_gj_vects,
    graphLaplacian=source.PostWorldKernel.graphLaplacian,
)
_HELPERS = {name: getattr(source.np, name) for name in ("asarray", "sqrt", "diag", "dot")}
_LOG = source.logs.log_debug
INVALIDATED_OWNERS = world.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
_ISSUED, _ACTIVE = WeakKeyDictionary(), WeakKeyDictionary()
_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class Request:
    world_owner: world.WorldDataOwner
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


class PostWorldRejected(world.FinalizationRejected):
    pass


def _prefix(context):
    return world._prefix(context.parent)


def _scope(context):
    return world._scope(context.parent)


def _env(context):
    return world._contexts(context.parent)[1]


def _body(node):
    nodes = list(node.body)
    if (
        nodes
        and isinstance(nodes[0], ast.Expr)
        and isinstance(nodes[0].value, ast.Constant)
        and isinstance(nodes[0].value.value, str)
    ):
        nodes = nodes[1:]
    return ast.dump(ast.Module(body=nodes, type_ignores=[]))


def _verify_sources():
    pins = world._verify_sources()
    native = multi.callers.NATIVE_ROOT / "betse/science/cells.py"
    if hashlib.sha256(native.read_bytes()).hexdigest() != source.CELLS_SHA256:
        raise ValueError("Original post-world source changed")
    cls = next(
        n
        for n in ast.parse(native.read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "Cells"
    )
    for name, module, classname in (
        (METHODS[0], vectors, "CellKernel"),
        (METHODS[1], source, "PostWorldKernel"),
    ):
        original = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
        owned = next(
            n
            for n in ast.parse(Path(module.__file__).read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == classname
        )
        method = next(n for n in owned.body if isinstance(n, ast.FunctionDef) and n.name == name)
        if (
            _body(original) != _body(method)
            or source.NATIVE_LINES[name] != (original.lineno, original.end_lineno)
            or [a.arg for a in method.args.args] != ["self", "p"]
        ):
            raise ValueError("Literal post-world numerical body changed: " + name)
    for module in (source, vectors, sys.modules[__name__]):
        path = Path(module.__file__).resolve()
        pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pins


def _bindings():
    functions = (
        *_NATIVE.values(),
        *_HELPERS.values(),
        *_HELPERS_current(),
        _LOG,
        source.PostWorldKernel.graphLaplacian,
        vectors.CellKernel.calc_gj_vects,
        _helper,
        _invoke,
        _namespace,
        _namespace_bindings,
        _check,
        _immutable_state,
        _immutable_graphs,
        _registry_links,
        _snapshot,
        _check_outputs,
        _HELPERS_current,
        _bindings,
        _verify_sources,
        _body,
        _prefix,
        _scope,
        _env,
        _stop,
        _account,
        _locals,
        _authority,
        _validate,
        trial_record,
        request_record,
        world._authority,
        world._validate,
        world._check_inherited,
        world._claim_for_post_world_operators,
        builtins.len,
        builtins.range,
        builtins.enumerate,
    )
    return (
        *world._bindings(),
        source.np,
        vectors.np,
        _ISSUED,
        _ACTIVE,
        _LOCK,
        world._ISSUED,
        world._FORWARDED,
        source.logs,
        source.logs.log_debug,
        METHODS,
        STORES,
        tuple(OUTPUTS.items()),
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


def _HELPERS_current():
    return tuple(getattr(module.np, name) for module in (source, vectors) for name in _HELPERS)


def request_record(request):
    parent = world._authority(request.world_owner)
    return dict(
        law=LAW_ID,
        parent=parent.trial.identity,
        methods=METHODS,
        outputs=OUTPUTS,
        native_lines=source.NATIVE_LINES,
        source_boundary="selected post-world leaf geometry/operators; no seed caller continuation",
        parameter_authority="same actual owned cell_height; no added parameters",
        normal_ECM_phase_profile_material_field_admitted=False,
        invalidated_owners=INVALIDATED_OWNERS,
    )


def from_world(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise PostWorldRejected("Explicit post-world source law required", stage="opt_in")
    parent = world._validate(owner)
    if not parent.finished or not parent.trial.source_completed:
        raise PostWorldRejected(
            "Complete actual world data owner required", stage="world_owner", trial=parent.trial
        )
    request = Request(owner, "")
    return replace(request, identity=core.records._digest(request_record(request)))


def _registry_links(context):
    return (
        world._authority(context.request.world_owner),
        world._FORWARDED.get(context.request.world_owner),
        *world._registry_links(context.parent),
    )


def _snapshot(context):
    prefix, env = _prefix(context), _env(context)
    return _scope(context).snapshot(
        dict(
            parent_world=context.prior_trial.identity,
            caller=multi._project(
                prefix,
                {
                    name: value
                    for name, value in multi.callers._public(prefix.caller).items()
                    if name not in {"mesh", "grid_obj", "points_tree"}
                },
            ),
            mesh=multi._project(prefix, multi.initial._public_cache(prefix.kernel)),
            parameters=multi.callers._parameters(prefix.p),
            grid=dict(vars(env.grid)),
            trees=[environment._tree_state(tree) for tree in env.trees],
            Poisson_results=context.parent.parent.results,
            Poisson_helpers=context.parent.parent.helper_results,
            Poisson_inputs=context.parent.parent.helper_inputs,
            post_world_helpers=context.helpers,
        )
    )


def _immutable_state(context):
    prefix, env = _prefix(context), _env(context)
    return _scope(context).snapshot(
        dict(
            caller=multi._project(
                prefix,
                {
                    name: value
                    for name, value in multi.callers._public(prefix.caller).items()
                    if name not in {*STORES, "mesh", "grid_obj", "points_tree"}
                },
            ),
            mesh=multi._project(prefix, multi.initial._public_cache(prefix.kernel)),
            parameters=multi.callers._parameters(prefix.p),
            grid=dict(vars(env.grid)),
            trees=[environment._tree_state(tree) for tree in env.trees],
            original_outputs=context.original_fields,
            parent_tail_helpers=context.parent.helpers,
            Poisson_results=context.parent.parent.results,
            Poisson_helpers=context.parent.parent.helper_results,
            Poisson_inputs=context.parent.parent.helper_inputs,
            RNG=core.initial._rng_stream(prefix.rng).identity,
            image=multi._image_state(prefix).identity,
        )
    )


def _immutable_graphs(context):
    prefix, env = _prefix(context), _env(context)
    view = context.original_view
    vars(view).clear()
    vars(view).update(
        (name, value) for name, value in vars(prefix.caller).items() if name not in STORES
    )
    view._cells_actual_caller = prefix.caller
    view._cells_original_outputs = context.original_fields
    view._cells_parent_tail = context.parent.raw_state
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
        *_immutable_graphs(context),
        _scope(context).graph(context.raw_state, _prefix(context).p, _prefix(context).tape),
    )


def _check_outputs(context):
    caller = _prefix(context).caller
    active = set(OUTPUTS.get(context.current_method, ())) if context.executing else set()
    for name in STORES:
        if name in active:
            continue
        if name in context.output_values:
            if vars(caller).get(name) is not context.output_values[name]:
                raise ValueError("Actual completed post-world output changed: " + name)
            cache = context.output_snapshots[name]
            core.caches.validate(cache)
            if _scope(context).snapshot(getattr(caller, name)).identity != cache.identity:
                raise ValueError("Completed post-world output bytes changed: " + name)
        elif (name in vars(caller)) != (name in context.original_fields) or (
            name in context.original_fields
            and vars(caller)[name] is not context.original_fields[name]
        ):
            raise ValueError("Unreached post-world output changed: " + name)


def _check(context):
    parent = context.parent
    if (
        world._authority(context.request.world_owner) is not parent
        or parent.invalid
        or parent.active
        or parent.thread != get_ident()
        or parent.trial is not context.prior_trial
        or world._FORWARDED.get(context.request.world_owner) is not context.retirement
        or core.records._digest(world.trial_record(parent.trial)) != context.parent_signature
    ):
        raise ValueError("Original world epoch/trial/irreversible claim changed")
    fields = tuple(vars(parent).items())
    if len(fields) != len(context.parent_fields) or any(
        a != c or b is not d for (a, b), (c, d) in zip(fields, context.parent_fields, strict=True)
    ):
        raise ValueError("Retained world source context changed")
    world._check_inherited(parent)
    multi.accounting._check_binding_identity(_registry_links(context), context.registry_links)
    multi.accounting._check_binding_identity(_bindings(), context.bindings)
    if _verify_sources() != context.producers:
        raise ValueError("Post-world/inherited source producer changed")
    if context.active and _ACTIVE.get(_prefix(context).caller) is not context:
        raise ValueError("Post-world active driver registry changed")
    if hasattr(context, "methods"):
        multi.accounting._check_binding_identity(
            _namespace_bindings(context), context.namespace_bindings
        )
    if _immutable_state(context).identity != context.immutable_state.identity:
        raise ValueError("Original geometry/mesh/grid/image/parameters/RNG/operators changed")
    geometry.meshes._same_graphs(_immutable_graphs(context), context.immutable_graphs)
    _check_outputs(context)
    if context.finished and (
        context.applied != list(METHODS) or set(context.output_values) != set(STORES)
    ):
        raise ValueError("Post-world source method/output completion changed")


def _stop(context):
    if context.observation_error is not None:
        raise environment._CaptureStop()


def _helper(context, name, delegate, *args, **kwargs):
    _stop(context)
    if (
        not context.active
        or not context.executing
        or not context.body_busy
        or context.helper_busy
        or context.thread != get_ident()
        or _ACTIVE.get(_prefix(context).caller) is not context
    ):
        raise PostWorldRejected(
            "Native helper lacks active post-world source driver", stage="source_call_unavailable"
        )
    _check(context)
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
    context.last_completed_helper = (name, args, result)
    try:
        context.helpers.append((context.current_method, name, args, kwargs, result))
    except Exception as capture:
        geometry._remember_observation_error(context, capture, origin="helper_result", raw=result)
    environment._observe(context, name + "_return", result)
    _stop(context)
    _check(context)
    return result


def _namespace(context):
    def helper(name):
        def invoke(*a, **k):
            return _helper(context, name, _HELPERS[name], *a, **k)

        return invoke

    def log(*args):
        return _helper(context, "log_debug", _LOG, *args)

    proxy = SimpleNamespace(**{name: helper(name) for name in _HELPERS})
    methods = {}
    context.literal_methods = {}
    for name, function in _NATIVE.items():
        namespace = dict(
            function.__globals__,
            np=proxy,
            logs=SimpleNamespace(log_debug=log),
            len=builtins.len,
            range=builtins.range,
            enumerate=builtins.enumerate,
        )
        delegate = FunctionType(
            function.__code__,
            namespace,
            function.__name__,
            function.__defaults__,
            function.__closure__,
        )
        context.literal_methods[name] = delegate

        def entry(actual, p, name=name, delegate=delegate):
            if (
                not context.active
                or not context.executing
                or context.entry_permit != name
                or context.body_busy
                or context.thread != get_ident()
                or actual is not _prefix(context).caller
                or p is not _prefix(context).p
                or _ACTIVE.get(actual) is not context
            ):
                raise PostWorldRejected(
                    "Raw post-world source entry unavailable", stage="source_call_unavailable"
                )
            context.entry_permit = None
            context.body_busy = True
            try:
                return delegate(actual, p)
            finally:
                context.body_busy = False

        methods[name] = entry
    return methods


def _namespace_bindings(context):
    values = []
    for name in METHODS:
        function = context.literal_methods[name]
        namespace = function.__globals__
        values += [
            context.methods[name],
            function,
            namespace["np"],
            namespace["logs"],
            *vars(namespace["np"]).values(),
            namespace["logs"].log_debug,
            namespace["len"],
            namespace["range"],
            namespace["enumerate"],
        ]
    return tuple(atom for value in values for atom in aliases._atoms(value))


@contextmanager
def _account(work):
    with world._account(work):
        previous = sys.getprofile()

        def profile(frame, event, arg):
            if event == "call" and (
                (
                    frame.f_globals.get("__name__") == __name__
                    and frame.f_code.co_name in {"_invoke", "_helper", "entry"}
                )
                or frame.f_code in {function.__code__ for function in _NATIVE.values()}
            ):
                if len(work.work) >= 100000:
                    raise ValueError("Bounded post-world work ledger exhausted")
                work.work.append(
                    dict(
                        sequence=len(work.work),
                        phase=work.stage,
                        layer="post_world_body"
                        if frame.f_code in {f.__code__ for f in _NATIVE.values()}
                        else "post_world_wrapper",
                        module=frame.f_globals.get("__name__"),
                        method=frame.f_code.co_qualname,
                        entry_method=frame.f_code.co_name,
                        source_file=frame.f_code.co_filename,
                        status="entered_not_success_credit",
                    )
                )
            if previous is not None:
                previous(frame, event, arg)

        guards = (previous, sys.gettrace())
        sys.setprofile(profile)
        try:
            yield
        finally:
            sys.setprofile(guards[0])
            sys.settrace(guards[1])


@contextmanager
def _locals(context):
    previous = sys.getprofile()
    trace = sys.gettrace()
    codes = {function.__code__: name for name, function in context.literal_methods.items()}

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
        sys.settrace(trace)


def _invoke(context, name):
    _stop(context)
    _check(context)
    environment._observe(context, name + "_enter", _prefix(context).caller)
    _stop(context)
    context.current_method = name
    context.entry_permit = name
    context.executing = True
    try:
        result = context.methods[name](_prefix(context).caller, _prefix(context).p)
    except Exception:
        environment._observe(context, name + "_unwind", _prefix(context).caller)
        raise
    finally:
        context.executing = False
        context.entry_permit = None
        context.current_method = None
    context.last_completed_method = (name, result)
    environment._observe(context, name + "_return", result)
    _stop(context)
    return result


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
        native_seed_phase_profiles_redo_gj_or_field_admitted=False,
        invalidated_owners=INVALIDATED_OWNERS,
    )


class PostWorldOperatorOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the actual world owner source continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live native operators cannot be serialized")

    @property
    def cells(self):
        return _prefix(_validate(self)).caller

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not PostWorldOperatorOwner or owner not in _ISSUED:
        raise PostWorldRejected(
            "Issued native post-world operator owner unavailable", stage="post_world_owner"
        )
    return _ISSUED[owner]


def _validate(owner):
    context = _authority(owner)
    try:
        if context.invalid or context.active or context.thread != get_ident():
            raise ValueError("Invalid post-world operator epoch")
        _check(context)
        if (
            _snapshot(context).identity != context.trial.cache.identity
            or core.records._digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Changed sealed post-world trial/cache")
        geometry.meshes._same_graphs(_graphs(context), context.graphs)
    except Exception as error:
        context.invalid = True
        raise PostWorldRejected(
            "Stale native post-world operators refused",
            stage="post_world_drift",
            request=context.request,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def prepare_continuation(request, *, _work=None):
    if type(request) is not Request:
        raise PostWorldRejected(
            "Typed actual WorldDataOwner request required", stage="request_owner"
        )
    if _work is None:
        work = SimpleNamespace(stage="post_world_operators", work=[])
        with _account(work):
            return prepare_continuation(request, _work=work)
    parent = world._authority(request.world_owner)
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
        body_busy=False,
        current_method=None,
        entry_permit=None,
        finished=False,
        helpers=[],
        applied=[],
        events=[],
        stages=[],
        locals={},
        output_values={},
        output_snapshots={},
        original_fields={},
        original_view=SimpleNamespace(),
        stage="preflight",
        prefix=_work,
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
    )
    context.raw_state = SimpleNamespace(helpers=context.helpers, outputs=context.output_values)
    error = None
    with _LOCK, warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        try:
            # Retain only references actually available before validation.
            # A broken upstream link may itself be the primary refusal; final
            # cleanup/forensics must not traverse that broken chain again.
            context.actual_prefix = _prefix(context)
            context.actual_environment = _env(context)
            if (
                world._validate(request.world_owner) is not parent
                or core.records._digest(request_record(request)) != request.identity
            ):
                raise ValueError("Changed actual world source request")
            caller = _prefix(context).caller
            context.original_fields = {
                name: vars(caller)[name] for name in STORES if name in vars(caller)
            }
            context.producers, context.bindings = _verify_sources(), _bindings()
            context.parent_signature = core.records._digest(world.trial_record(parent.trial))
            context.parent_fields = tuple(vars(parent).items())
            context.stage = "baseline_capture"
            try:
                context.before = _snapshot(context)
                context.stream_before = core.initial._rng_stream(_prefix(context).rng)
                context.immutable_state = _immutable_state(context)
                context.immutable_graphs = _immutable_graphs(context)
            except Exception as capture:
                geometry._remember_observation_error(
                    context, capture, origin="baseline", raw=caller
                )
                raise environment._CaptureStop() from capture
            context.stage = "retirement"
            world._claim_for_post_world_operators(
                request.world_owner, expected=parent, transition=context.retirement
            )
            context.registry_links = _registry_links(context)
            context.stage = "namespace"
            context.methods = _namespace(context)
            context.namespace_bindings = _namespace_bindings(context)
            context.active = True
            _ACTIVE[caller] = context
            context.registered_caller = caller
            with _locals(context):
                for name in METHODS:
                    context.stage = _work.stage = name
                    _invoke(context, name)
                    try:
                        for field in OUTPUTS[name]:
                            context.output_values[field] = getattr(caller, field)
                            context.output_snapshots[field] = _scope(context).snapshot(
                                getattr(caller, field)
                            )
                        context.applied.append(name)
                        context.stages.append((name, _snapshot(context)))
                    except Exception as capture:
                        geometry._remember_observation_error(
                            context, capture, origin="stage_snapshot", raw=caller
                        )
                        raise environment._CaptureStop() from capture
                    _check(context)
            context.finished = True
            context.stage = "source_checks"
            _check(context)
        except Exception as failure:
            if not isinstance(failure, environment._CaptureStop):
                error = failure
        finally:
            context.active = context.executing = context.helper_busy = context.body_busy = False
            registered = getattr(context, "registered_caller", None)
            if registered is not None and _ACTIVE.get(registered) is context:
                _ACTIVE.pop(registered)
    prefix = getattr(context, "actual_prefix", None)
    env = getattr(context, "actual_environment", None)
    partial = dict(
        context=context,
        parent=parent,
        parent_trial=context.prior_trial,
        caller=getattr(prefix, "caller", None),
        parameters=getattr(prefix, "p", None),
        mesh=getattr(prefix, "kernel", None),
        grid=getattr(env, "grid", None),
        rng=getattr(prefix, "rng", None),
        original_fields=context.original_fields,
        completed_methods=context.applied,
        outputs=context.output_values,
        helpers=context.helpers,
        raw_locals=context.locals,
        stages=context.stages,
        events=context.events,
        work=_work.work,
        last_completed_helper=getattr(context, "last_completed_helper", None),
        last_completed_method=getattr(context, "last_completed_method", None),
        world_consumed=request.world_owner in world._FORWARDED,
        usable_child_available=False,
    )
    if context.observation_error is not None:
        raise PostWorldRejected(
            "Post-world observation failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=context.observation_error,
        ) from (error or context.observation_error)
    if getattr(context, "before", None) is None or getattr(context, "stream_before", None) is None:
        raise PostWorldRejected(
            "Post-world refused before complete baseline",
            stage=context.stage,
            request=request,
            trial=None,
            partial=partial,
            source_error=error,
        ) from error
    try:
        trial = Trial(
            request.identity,
            parent.trial.identity,
            context.before,
            _snapshot(context),
            tuple(context.stages),
            tuple(name for name, _ in context.events),
            tuple(dict(row) for row in _work.work),
            context.stream_before,
            core.initial._rng_stream(_prefix(context).rng),
            tuple(str(w.message) for w in caught_warnings),
            error is None,
            None if error is None else context.stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise PostWorldRejected(
            "Post-world trial sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error or capture)
    if error is not None:
        raise PostWorldRejected(
            "Original post-world source failed",
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
        owner = object.__new__(PostWorldOperatorOwner)
        _ISSUED[owner] = context
        return owner
    except Exception as capture:
        raise PostWorldRejected(
            "Post-world child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture


def require_normal_ecm_field(owner):
    context = _validate(owner)
    raise PostWorldRejected(
        "Native geometry operators are not a complete normal ECM initializer",
        stage="normal_ecm_prerequisites",
        trial=context.trial,
        partial=dict(
            missing=(
                "actual seed phase/Simulator.init_core",
                "native tissue profiles/redo_gj",
                "source ion/material/initializer parameter and cache owners",
                "field domain/operator numerical admission",
            ),
            M_sum_mem_to_ecm="unchanged native None",
            gradMem="unchanged native None",
            invalidated_owners=INVALIDATED_OWNERS,
            physical_checkpoint_admitted=False,
        ),
    )
