"""Owned value/flux environmental Poisson source continuation.

This selected method boundary excludes make_world callbacks and every store
after lapENV_P_inv. Live source ownership is process local; operators, numerical
accuracy, physics and ordinary checkpoints require separate qualification.
"""

import ast
import hashlib
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_single_cell_environment as environment
from cells.processes import betse_native_single_cell_poisson_observation as observation
from cells.processes import betse_native_single_cell_poisson_source as source

ecm, geometry, core = environment.ecm, environment.geometry, environment.core
LAW_ID = "betse_owned_single_cell_environment_Poisson@1"
INVALIDATED_OWNERS = environment.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
METHODS = ("environment_voltage", "environment_current")
_CALLER = {name: getattr(source.CellsPoisson, name) for name in METHODS}
_LAPLACIAN = source.FiniteDiffPoisson.makeLaplacian
_ZEROS, _PINV = source.np.zeros, source.np.linalg.pinv
_ISSUED, _GRIDS = WeakKeyDictionary(), WeakKeyDictionary()
_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class Request:
    environment_request: environment.Request
    identity: str


@dataclass(frozen=True, slots=True)
class ContinuationRequest:
    environment_owner: environment.EnvironmentOwner
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


class PoissonRejected(ValueError):
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


def _verify_sources():
    pins = environment._verify_sources()
    native = geometry.callers.NATIVE_ROOT / "betse/science"
    trees = {}
    for key, path, expected in (
        ("cells", native / "cells.py", source.CELLS_SHA256),
        ("grid", native / "math/finitediff.py", source.GRID_SHA256),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Original environmental Poisson source changed")
        trees[key] = ast.parse(path.read_text())
    owned = ast.parse(Path(source.__file__).read_text())
    original_grid = next(
        n
        for n in trees["grid"].body
        if isinstance(n, ast.ClassDef) and n.name == "FiniteDiffSolver"
    )
    original_method = next(
        n
        for n in original_grid.body
        if isinstance(n, ast.FunctionDef) and n.name == "makeLaplacian"
    )
    copied_grid = next(
        n for n in owned.body if isinstance(n, ast.ClassDef) and n.name == "FiniteDiffPoisson"
    )
    copied_method = next(n for n in copied_grid.body if isinstance(n, ast.FunctionDef))
    if ast.dump(original_method.args) != ast.dump(copied_method.args) or ast.dump(
        ast.Module(body=original_method.body, type_ignores=[])
    ) != ast.dump(ast.Module(body=copied_method.body, type_ignores=[])):
        raise ValueError("Literal MAC makeLaplacian signature/body changed")
    original_cells = next(
        n for n in trees["cells"].body if isinstance(n, ast.ClassDef) and n.name == "Cells"
    )
    world = next(
        n for n in original_cells.body if isinstance(n, ast.FunctionDef) and n.name == "make_world"
    )
    copied_cells = next(
        n for n in owned.body if isinstance(n, ast.ClassDef) and n.name == "CellsPoisson"
    )
    for name, lines in zip(METHODS, source.CALLER_LINES, strict=True):
        actual = [n for n in world.body if n.lineno in lines]
        copied = next(
            n for n in copied_cells.body if isinstance(n, ast.FunctionDef) and n.name == name
        )
        if len(actual) != 2 or ast.dump(ast.Module(body=actual, type_ignores=[])) != ast.dump(
            ast.Module(body=copied.body, type_ignores=[])
        ):
            raise ValueError("Literal value/flux caller statements changed")
    for module in (source, observation, sys.modules[__name__]):
        path = Path(module.__file__).resolve()
        pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pins


def _prefix(context):
    return context.parent.parent.parent.parent


def _bindings():
    functions = (
        *_CALLER.values(),
        _LAPLACIAN,
        _ZEROS,
        _PINV,
        source.np.zeros,
        source.np.linalg.pinv,
        source.CellsPoisson.environment_voltage,
        source.CellsPoisson.environment_current,
        source.FiniteDiffPoisson.makeLaplacian,
        ecm._GridRuntime.makeLaplacian,
        environment._claim_for_Poisson,
        _grid_call,
        _helper,
        _stop,
        _namespace,
        _namespace_bindings,
        _parent_epoch,
        _observation,
    )
    return (
        source.np,
        source.np.linalg,
        *observation.bindings(environment),
        *ecm.aliases._dispatch_bindings(ecm._GridRuntime),
        *(atom for function in functions for atom in ecm.aliases._atoms(function)),
    )


def _defaults():
    return core.records._digest(core.records.record(_LAPLACIAN.__defaults__))


def from_core(parent, configuration, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise PoissonRejected("Explicit Poisson source law required", stage="opt_in")
    prefix = environment.from_core(parent, configuration, law_id=environment.LAW_ID)
    return Request(prefix, core.records._digest(dict(law=LAW_ID, environment=prefix.identity)))


def _preflight(owner):
    parent = environment._validate(owner)
    if not parent.finished or not parent.trial.source_completed:
        raise PoissonRejected(
            "Completed actual environment owner required", stage="environment_owner"
        )
    return parent


def request_record(request):
    parent = environment._authority(request.environment_owner)
    return dict(
        law=LAW_ID,
        parent=parent.trial.identity,
        methods=METHODS,
        boundaries=("N,S,E,W=value", "N,S,E,W=flux"),
        boundary="before lapGJ stores after second makeLaplacian",
        invalidated_owners=INVALIDATED_OWNERS,
        full_make_world_phase_physical_checkpoint=False,
        observation_policy=observation.specification(),
    )


def from_environment(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise PoissonRejected("Explicit Poisson source law required", stage="opt_in")
    _preflight(owner)
    request = ContinuationRequest(owner, "")
    return replace(request, identity=core.records._digest(request_record(request)))


def _stop(context):
    if context.observation_error is not None:
        raise ecm._CaptureStop()


def _helper(context, name, delegate, *args, **kwargs):
    _stop(context)
    _check(context)
    if not context.active or not context.grid_busy or context.thread != get_ident():
        raise PoissonRejected(
            "Operator helper lacks active issued source", stage="source_call_unavailable"
        )
    if name == "pinv" and args:
        # Keep the scaled operator even if pinv fails before a return pair
        # exists. This is raw partial evidence, not an extra wire helper row.
        try:
            context.helper_inputs.append((context.stage, name, args[0]))
        except Exception as capture:
            geometry._remember_observation_error(context, capture, origin="pinv_input", raw=args)
        _stop(context)
    ecm._observe(context, name + "_enter", (args, kwargs))
    _stop(context)
    try:
        result = delegate(*args, **kwargs)
    except Exception:
        ecm._observe(context, name + "_unwind", (args, kwargs))
        raise
    # Preserve the actual output even when the following observation fails.
    context.helper_results.append((context.stage, name, result))
    ecm._observe(context, name + "_return", result)
    _stop(context)
    return result


def _namespace(context):
    def zeros(*args, **kwargs):
        return _helper(context, "zeros", _ZEROS, *args, **kwargs)

    def pinv(*args, **kwargs):
        return _helper(context, "pinv", _PINV, *args, **kwargs)

    namespace = dict(
        source.__dict__, np=SimpleNamespace(zeros=zeros, linalg=SimpleNamespace(pinv=pinv))
    )
    operator = FunctionType(
        _LAPLACIAN.__code__,
        namespace,
        _LAPLACIAN.__name__,
        _LAPLACIAN.__defaults__,
        _LAPLACIAN.__closure__,
    )
    methods = {
        name: FunctionType(
            fn.__code__, dict(source.__dict__), fn.__name__, fn.__defaults__, fn.__closure__
        )
        for name, fn in _CALLER.items()
    }
    return methods, operator


def _namespace_bindings(context):
    functions = [*context.methods.values(), context.operator]
    namespace = context.operator.__globals__
    return (
        namespace["np"],
        namespace["np"].linalg,
        *(
            atom
            for fn in (*functions, namespace["np"].zeros, namespace["np"].linalg.pinv)
            for atom in ecm.aliases._atoms(fn)
        ),
    )


def _grid_call(grid, *args, **kwargs):
    context = _GRIDS.get(grid)
    if (
        context is None
        or not context.active
        or not context.executing
        or context.thread != get_ident()
        or context.grid_busy
    ):
        raise PoissonRejected(
            "Raw makeLaplacian lacks active issued caller", stage="source_call_unavailable"
        )
    _stop(context)
    _check(context)
    caller = _prefix(context).caller
    frame = sys._getframe(2)
    method = context.methods.get(context.stage)
    if (
        method is None
        or frame.f_code is not method.__code__
        or frame.f_globals is not method.__globals__
        or frame.f_locals.get("self") is not caller
    ):
        raise PoissonRejected(
            "makeLaplacian must be called by its literal caller", stage="source_call_unavailable"
        )
    expected = "value" if context.stage == METHODS[0] else "flux"
    if (
        args
        or tuple(kwargs) != ("bound",)
        or type(kwargs["bound"]) is not dict
        or kwargs["bound"] != dict.fromkeys(("N", "S", "E", "W"), expected)
        or len(context.attempted) != METHODS.index(context.stage)
    ):
        raise PoissonRejected(
            "Native value/flux source order or boundary dictionary changed", stage="boundary_order"
        )
    context.attempted.append(context.stage)
    ecm._observe(context, "makeLaplacian_enter", (grid, kwargs["bound"]))
    _stop(context)
    context.grid_busy = True
    try:
        result = context.operator(grid, **kwargs)
    except Exception:
        ecm._observe(context, "makeLaplacian_unwind", grid)
        raise
    finally:
        context.grid_busy = False
    context.results.append((context.stage, result))
    ecm._observe(context, "makeLaplacian_return", result)
    _stop(context)
    return result


def _snapshot(context):
    scope = _observation(context)
    return scope.snapshot(
        dict(
            environment=scope.environment_snapshot(context.parent, environment).identity,
            results=context.results,
            helpers=context.helper_results,
        )
    )


def _observation(context):
    roles = {}

    def retain(stage, role, value):
        name = stage + "." + role
        if name in roles and roles[name] is not value:
            raise ValueError("Poisson helper/return identity differs for role " + name)
        roles[name] = value

    for stage, name, value in context.helper_results:
        if name == "zeros":
            retain(stage, "Z", value)
        elif name == "pinv":
            retain(stage, "P", value)
    for stage, name, value in context.helper_inputs:
        if name == "pinv":
            retain(stage, "A", value)
    for stage, pair in context.results:
        if type(pair) is tuple and len(pair) == 2:
            retain(stage, "A", pair[0])
            retain(stage, "P", pair[1])
    return observation.Scope(
        roles={name: roles[name] for name in observation.ROLE_NAMES if name in roles}
    )


def _parent_epoch(context):
    """Only the two inverse assignments may change the continuing parent.

    The stable view is an identity audit of real references, never a source
    object or a computation input. Operator helpers cannot silently replace an
    equal grid array, alter earlier masks or advance the continuing RNG.
    """
    prefix = _prefix(context)
    caller = geometry.meshes._caller_without_mesh(prefix.caller)
    for name in ("grid_obj", "points_tree", "lapENVinv", "lapENV_P_inv"):
        caller.pop(name, None)
    state = dict(
        caller=caller,
        grid=dict(vars(context.parent.parent.grid)),
        parameters=geometry.callers._parameters(prefix.p),
        trees=[environment._tree_state(tree) for tree in context.parent.trees],
        RNG=core.initial._rng_stream(prefix.rng).identity,
    )
    # Keep the view/container identities stable. Fresh dictionaries from the
    # cache projection must not appear as new purported source references.
    edges = dict(actual_caller=prefix.caller, actual_grid=context.parent.parent.grid)
    edges.update(("caller_" + name, value) for name, value in caller.items())
    edges.update(
        ("grid_" + name, value) for name, value in vars(context.parent.parent.grid).items()
    )
    for index, tree in enumerate(context.parent.trees):
        edges["tree_" + str(index)] = tree
        edges.update(
            ("tree_" + str(index) + "_" + name, value)
            for name, value in environment._tree_state(tree).items()
        )
    vars(context.parent_view).clear()
    vars(context.parent_view).update(edges)
    return (
        core.caches.snapshot(state).identity,
        geometry.callers._graph(context.parent_view, prefix.p, prefix.mesh_context.graph_tape),
    )


def _graphs(context):
    prefix = _prefix(context)
    scope = _observation(context)
    return (
        *scope.environment_graphs(context.parent, environment),
        scope.graph(context.raw_state, prefix.p, prefix.mesh_context.graph_tape),
    )


def _check(context):
    parent, grid = context.parent, context.parent.parent.grid
    if (
        environment._authority(context.request.environment_owner) is not parent
        or parent.invalid
        or parent.active
        or parent.thread != get_ident()
        or parent.trial is not context.prior_trial
        or core.records._digest(environment.trial_record(parent.trial)) != context.parent_signature
        or environment._FORWARDED.get(context.request.environment_owner) is not context.retirement
    ):
        raise ValueError("Original environment lineage or irreversible Poisson claim changed")
    # Check live authority, never reopen the consumed parent's pre-Poisson cache.
    environment._check(parent)
    epoch, graph = _parent_epoch(context)
    if epoch != context.parent_epoch:
        raise ValueError("Continuing environment/grid/parameter/RNG epoch changed")
    geometry.meshes._same_graphs((graph,), (context.parent_graph,))
    if (
        type(grid) is not ecm._GridRuntime
        or ecm._GRIDS.get(grid) is not parent.parent
        or _prefix(context).caller.grid_obj is not grid
        or _GRIDS.get(grid) is not context
    ):
        raise ValueError("Actual continuing grid/constructor relationship changed")
    ecm.completion._check_binding_identity(_bindings(), context.bindings)
    if hasattr(context, "operator"):
        ecm.completion._check_binding_identity(
            _namespace_bindings(context), context.namespace_bindings
        )
    if _defaults() != context.defaults or _verify_sources() != context.producers:
        raise ValueError("Poisson source/helper/default authority changed")
    if context.finished:
        caller = _prefix(context).caller
        if (
            context.attempted != list(METHODS)
            or [name for name, _ in context.results] != list(METHODS)
            or any(type(pair) is not tuple or len(pair) != 2 for _, pair in context.results)
            or caller.lapENVinv is not context.results[0][1][1]
            or caller.lapENV_P_inv is not context.results[1][1][1]
        ):
            raise ValueError("Original Poisson returns/assignments/order changed")


def trial_record(trial):
    return dict(
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
        invalidated_owners=INVALIDATED_OWNERS,
        full_make_world_phase_operators_physical_checkpoint_qualified=False,
        observation_policy=observation.specification(),
    )


class PoissonOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the owned environmental Poisson entry")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live Poisson authority cannot be serialized")

    @property
    def cells(self):
        return _prefix(_validate(self)).caller

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not PoissonOwner or owner not in _ISSUED:
        raise PoissonRejected("Issued Poisson source owner unavailable", stage="poisson_owner")
    return _ISSUED[owner]


def _validate(owner):
    context = _authority(owner)
    try:
        if context.invalid or context.active or context.thread != get_ident():
            raise ValueError("Invalid completed Poisson authority")
        _check(context)
        if (
            _snapshot(context).identity != context.trial.cache.identity
            or core.records._digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Changed sealed environmental Poisson source state")
        geometry.meshes._same_graphs(_graphs(context), context.graphs)
        for cache in (
            context.trial.before,
            context.trial.cache,
            *(v for _, v in context.trial.stages),
        ):
            core.caches.validate(cache)
    except Exception as error:
        context.invalid = True
        raise PoissonRejected(
            "Stale Poisson source owner",
            stage="poisson_drift",
            request=context.request,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


@contextmanager
def _account(context):
    with environment._account(context):
        previous = sys.getprofile()

        def profile(frame, event, arg):
            module = frame.f_globals.get("__name__", "")
            if event == "call" and (
                module == source.__name__
                or module == __name__
                and frame.f_code.co_name in {"_grid_call", "_helper"}
            ):
                context.work.append(
                    dict(
                        sequence=len(context.work),
                        phase=context.stage,
                        layer="body" if module == source.__name__ else "operator_wrapper",
                        module=module,
                        method=frame.f_code.co_qualname,
                        entry_method=frame.f_code.co_name,
                        helper_operation=frame.f_locals.get("name")
                        if frame.f_code.co_name == "_helper"
                        else None,
                        helper_result_role=(
                            context.stage
                            + "."
                            + ("Z" if frame.f_locals.get("name") == "zeros" else "P")
                        )
                        if frame.f_code.co_name == "_helper"
                        else None,
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
    codes = {method.__code__: name for name, method in context.methods.items()}
    codes[context.operator.__code__] = "makeLaplacian"

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


def prepare_continuation(request, *, _work=None):
    if type(request) is not ContinuationRequest:
        raise PoissonRejected("Typed live environment owner required", stage="request_owner")
    if _work is None:
        work = SimpleNamespace(stage="environment_Poisson", work=[])
        with _account(work):
            return prepare_continuation(request, _work=work)
    parent = environment._authority(request.environment_owner)
    context = SimpleNamespace(
        request=request,
        parent=parent,
        prior_trial=parent.trial,
        retirement=object(),
        thread=get_ident(),
        invalid=False,
        active=False,
        executing=False,
        grid_busy=False,
        finished=False,
        attempted=[],
        results=[],
        helper_results=[],
        helper_inputs=[],
        events=[],
        locals={},
        stages=[],
        stage="preflight",
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
        prefix=_work,
    )
    context.raw_state = SimpleNamespace(
        results=context.results, helpers=context.helper_results, inputs=context.helper_inputs
    )
    context.parent_view = SimpleNamespace()
    error = None
    with _LOCK:
        try:
            if (
                _preflight(request.environment_owner) is not parent
                or core.records._digest(request_record(request)) != request.identity
            ):
                raise ValueError("Changed retained Poisson request")
            context.producers, context.bindings = _verify_sources(), _bindings()
            context.defaults = _defaults()
            context.parent_signature = core.records._digest(environment.trial_record(parent.trial))
            context.before = _snapshot(context)
            context.stream_before = core.initial._rng_stream(_prefix(context).rng)
            context.parent_epoch, context.parent_graph = _parent_epoch(context)
            context.stage = "retirement"
            environment._claim_for_Poisson(
                request.environment_owner, expected=parent, transition=context.retirement
            )
            _GRIDS[parent.parent.grid] = context
            context.stage = "namespace"
            context.methods, context.operator = _namespace(context)
            context.namespace_bindings = _namespace_bindings(context)
            context.active = True
            with _locals(context):
                for name in METHODS:
                    context.stage = _work.stage = name
                    _check(context)
                    context.executing = True
                    try:
                        context.methods[name](_prefix(context).caller)
                    finally:
                        context.executing = False
                    _stop(context)
                    try:
                        context.stages.append((name, _snapshot(context)))
                    except Exception as capture:
                        geometry._remember_observation_error(
                            context, capture, origin="stage_snapshot", raw=_prefix(context).caller
                        )
                        raise ecm._CaptureStop() from capture
                    _check(context)
            context.finished = True
            context.stage = "source_checks"
            _check(context)
        except Exception as failure:
            if not isinstance(failure, ecm._CaptureStop):
                error = failure
        finally:
            context.active = context.executing = context.grid_busy = False
    partial = dict(
        context=context,
        parent_trial=context.prior_trial,
        caller=_prefix(context).caller,
        parameters=_prefix(context).p,
        mesh=_prefix(context).mesh_context.kernel,
        grid=parent.parent.grid,
        rng=_prefix(context).rng,
        trees=parent.trees,
        stage=context.stage,
        events=context.events,
        raw_locals=context.locals,
        stages=context.stages,
        work=_work.work,
        results=context.results,
        helper_results=context.helper_results,
        helper_inputs=context.helper_inputs,
        observation_errors=context.observation_errors,
        observation_raw=context.observation_raw,
        environment_consumed=request.environment_owner in environment._FORWARDED,
        usable_Poisson_child_available=False,
    )
    if context.observation_error is not None:
        raise PoissonRejected(
            "Poisson observation failed",
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
            core.initial._rng_stream(_prefix(context).rng),
            error is None,
            None if error is None else context.stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise PoissonRejected(
            "Poisson trial sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error if error is not None else capture)
    if error is not None:
        raise PoissonRejected(
            "Original Poisson source attempt failed",
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
        child = object.__new__(PoissonOwner)
        _ISSUED[child] = context
        return child
    except Exception as capture:
        raise PoissonRejected(
            "Poisson child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture


def prepare(request):
    if (
        type(request) is not Request
        or core.records._digest(dict(law=LAW_ID, environment=request.environment_request.identity))
        != request.identity
    ):
        raise PoissonRejected("Typed fresh Poisson prefix required", stage="request_owner")
    context = SimpleNamespace(stage="environment_prefix", work=[], parent=None)
    try:
        with _account(context):
            context.parent = environment.prepare(request.environment_request)
            return prepare_continuation(
                from_environment(context.parent, law_id=LAW_ID), _work=context
            )
    except Exception as error:
        raise PoissonRejected(
            "Owned Poisson prefix failed",
            stage=context.stage,
            request=request,
            partial=dict(parent=context.parent, prefix=context, work=context.work),
            source_error=error,
        ) from error


def require_full_make_world(owner, *, phase=None):
    context = _validate(owner)
    raise PoissonRejected(
        "Subsequent stores/full make_world/phase remain held",
        stage="make_world_held",
        trial=context.trial,
        partial=dict(
            invalidated_owners=INVALIDATED_OWNERS,
            supplied_phase=phase,
            physical_checkpoint_general_DEC_admitted=False,
        ),
    )
