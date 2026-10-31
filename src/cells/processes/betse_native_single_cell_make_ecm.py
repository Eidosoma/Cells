"""Owned ordinary makeECM continuation, stopping before environment.

Only fresh selected grid-descriptor parameters and the same issued live caller
may continue. No supplied grid, ordinary checkpoint, phase, physical or general
DEC authority is admitted. Actual native work remains held for qualification.
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

from cells.processes import betse_native_single_cell_ecm_source as source
from cells.processes import betse_native_single_cell_grid_alias as aliases
from cells.processes import betse_native_single_cell_initial_geometry as geometry

core, parameters, completion = geometry.core, geometry.parameters, geometry.completion
LAW_ID = "betse_owned_single_cell_makeECM@1"
INVALIDATED_OWNERS = geometry.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
_MAKE, _INIT, _GRID = (
    source.CellsECM.makeECM,
    source.FiniteDiffSolver.__init__,
    source.FiniteDiffSolver.cell_grid,
)
_ISSUED, _GRIDS = WeakKeyDictionary(), WeakKeyDictionary()
_FORWARDED = WeakKeyDictionary()
_LOCK = RLock()
_HELPERS = ("unique", "asarray", "vstack", "hstack", "linspace", "meshgrid", "column_stack")


@dataclass(frozen=True, slots=True)
class Request:
    geometry_request: geometry.Request
    identity: str


@dataclass(frozen=True, slots=True)
class ContinuationRequest:
    geometry_owner: geometry.GeometryOwner
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    cache: object
    stream_before: object
    stream_after: object
    events: tuple
    work: tuple
    source_completed: bool
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class EcmRejected(ValueError):
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
    pins = geometry._verify_sources()
    for rel, name, methods in (
        ("betse/science/cells.py", "Cells", ("makeECM",)),
        ("betse/science/math/finitediff.py", "FiniteDiffSolver", ("__init__", "cell_grid")),
    ):
        path = geometry.callers.NATIVE_ROOT / rel
        expected = source.CELLS_SHA256 if name == "Cells" else source.GRID_SHA256
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Original makeECM/grid source changed")
        original = next(
            n
            for n in ast.parse(path.read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == name
        )
        owned = next(
            n
            for n in ast.parse(Path(source.__file__).read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == ("CellsECM" if name == "Cells" else name)
        )
        for method in methods:
            left = next(
                n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == method
            )
            right = next(
                n for n in owned.body if isinstance(n, ast.FunctionDef) and n.name == method
            )
            if ast.dump(ast.Module(body=left.body, type_ignores=[])) != ast.dump(
                ast.Module(body=right.body, type_ignores=[])
            ):
                raise ValueError("Literal makeECM/grid body changed")
    for module in (source, aliases, sys.modules[__name__]):
        path = Path(module.__file__).resolve()
        pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pins


def _bindings():
    functions = (
        _MAKE,
        _INIT,
        _GRID,
        _GridRuntime.__init__,
        _GridRuntime.cell_grid,
        _construct_grid,
        _active,
        _require_descriptor_read,
        _stop_observation,
        aliases._GridAlias.__get__,
        aliases._GridAlias.__set__,
    )
    return (
        _GridRuntime,
        _GridRuntime.__mro__,
        source.FiniteDiffSolver,
        source.CellsECM,
        *geometry._callable_bindings(functions),
        source.np,
        source.cKDTree,
        *geometry._callable_bindings(getattr(source.np, name) for name in _HELPERS),
        getattr(source.cKDTree, "query", None),
        getattr(source.cKDTree, "query_ball_point", None),
    )


def from_core(parent, configuration, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise EcmRejected("Explicit owned makeECM law required", stage="opt_in")
    p = parameters.from_core(
        parent,
        configuration,
        law_id=parameters.GEOMETRY_LAW_ID,
        projection=parameters.GEOMETRY,
        grid_descriptor=aliases.SELECTOR,
    )
    prefix = completion.Request(
        p,
        core.records._digest(dict(law=completion.LAW_ID, parameters=parameters.request_record(p))),
    )
    geo = geometry.Request(
        prefix, core.records._digest(dict(law=geometry.LAW_ID, prefix=prefix.identity))
    )
    value = Request(geo, "")
    return replace(value, identity=core.records._digest(dict(law=LAW_ID, geometry=geo.identity)))


def _preflight(owner):
    geo = geometry._validate(owner)
    parameter = parameters._authority(geo.parent.parameter_owner)
    if parameter.grid_descriptor != aliases.SELECTOR or parameter.descriptor_info is None:
        raise EcmRejected(
            "Fresh selected grid_size descriptor authority unavailable; no retrofit",
            stage="grid_descriptor_prerequisite",
            trial=geo.trial,
        )
    aliases.validate(parameter.descriptor_info)
    if hasattr(geo.parent.caller, "grid_obj"):
        raise EcmRejected("Supplied/pre-existing grid ownership unavailable", stage="grid_owner")
    return geo, parameter


def request_record(request):
    parent = geometry._authority(request.geometry_owner)
    parameter = parameters._authority(parent.parent.parameter_owner)
    return dict(
        law=LAW_ID,
        geometry_trial=parent.trial.identity,
        parameter_trial=parameter.trial.identity,
        selected_descriptor=parameter.trial.descriptor_proof,
        boundary="ordinary makeECM; stop before environment",
        invalidated_owners=INVALIDATED_OWNERS,
        physical_checkpoint_admitted=False,
    )


def from_geometry(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise EcmRejected("Explicit owned makeECM law required", stage="opt_in")
    _preflight(owner)
    request = ContinuationRequest(owner, "")
    return replace(request, identity=core.records._digest(request_record(request)))


def _snapshot(context):
    caller = geometry.meshes._caller_without_mesh(context.parent.parent.caller)
    caller.pop("grid_obj", None)
    return core.caches.snapshot(
        dict(
            caller=caller,
            mesh=core.initial._public_cache(context.parent.parent.mesh_context.kernel),
            parameters=geometry.callers._parameters(context.parent.parent.p),
            grid=None if context.grid is None else dict(vars(context.grid)),
        )
    )


def _observe(context, kind, raw):
    try:
        context.events.append((kind, raw))
    except Exception as capture:
        geometry._remember_observation_error(context, capture, origin=kind, raw=raw)


def _active(grid):
    context = _GRIDS.get(grid)
    if (
        context is None
        or not context.active
        or context.thread != get_ident()
        or type(grid) is not _GridRuntime
    ):
        raise EcmRejected(
            "Raw grid source call lacks active issued driver", stage="source_call_unavailable"
        )
    if context.observation_error is not None:
        raise _CaptureStop()
    _check(context)
    return context


def _require_descriptor_read(context):
    p = context.parent.parent.p
    if (
        context.descriptor_read_started is not True
        or context.descriptor_read_completed is not True
        or context.descriptor_read_instance is not p
        or context.descriptor_read_return_instance is not p
        or context.descriptor_read_native is not context.parameter_info.native
        or context.descriptor_read_epoch is not context.retirement
    ):
        raise ValueError(
            "Owned grid_size descriptor read did not complete on the same parameter epoch"
        )


def _stop_observation(context):
    if context.observation_error is not None:
        raise _CaptureStop()


class _GridRuntime(source.FiniteDiffSolver):
    def __init__(self):
        context = _active(self)
        if context.constructed or context.constructing:
            raise EcmRejected("Native grid constructor already completed", stage="grid_constructor")
        context.stage = "grid_constructor"
        context.prefix.stage = "grid_constructor"
        _observe(context, "grid_constructor_enter", self)
        context.constructing = True
        try:
            _INIT(self)
        except Exception:
            _observe(context, "grid_constructor_unwind", self)
            raise
        finally:
            context.constructing = False
        context.constructed = True
        _observe(context, "grid_constructor_return", self)
        _stop_observation(context)
        context.stage = "makeECM"
        context.prefix.stage = "makeECM"

    def cell_grid(self, *args):
        context = _active(self)
        if (
            not context.constructed
            or context.initialized
            or context.initializing
            or context.parent.parent.caller.grid_obj is not self
        ):
            raise EcmRejected(
                "Actual grid constructor/assignment/init order unavailable", stage="cell_grid"
            )
        context.stage = "cell_grid"
        context.prefix.stage = "cell_grid"
        _observe(context, "cell_grid_enter_after_assignment", self)
        context.initializing = True
        try:
            _GRID(self, *args)
        except Exception:
            _observe(context, "cell_grid_unwind", self)
            raise
        finally:
            context.initializing = False
        context.initialized = True
        _observe(context, "cell_grid_return", self)
        _stop_observation(context)
        context.stage = "makeECM"
        context.prefix.stage = "makeECM"

    def __reduce_ex__(self, protocol):
        raise TypeError("Native live grid authority cannot be serialized")


def _construct_grid(context):
    if not context.active or context.grid is not None or context.thread != get_ident():
        raise EcmRejected("Fresh native grid construction unavailable", stage="grid_constructor")
    if context.observation_error is not None:
        raise _CaptureStop()
    _check(context)
    _require_descriptor_read(context)
    grid = object.__new__(_GridRuntime)
    context.grid = grid
    _GRIDS[grid] = context
    grid.__init__()
    return grid


def _namespace(context):
    def constructor():
        return _construct_grid(context)

    namespace = dict(source.__dict__, fd=SimpleNamespace(FiniteDiffSolver=constructor))
    return FunctionType(
        _MAKE.__code__, namespace, _MAKE.__name__, _MAKE.__defaults__, _MAKE.__closure__
    )


def _namespace_bindings(method):
    namespace = method.__globals__
    return (
        method,
        method.__code__,
        namespace["np"],
        namespace["fd"],
        namespace["cKDTree"],
        *aliases._atoms(namespace["fd"].FiniteDiffSolver),
        *geometry._callable_bindings(getattr(namespace["np"], name) for name in _HELPERS),
        getattr(namespace["cKDTree"], "query", None),
        getattr(namespace["cKDTree"], "query_ball_point", None),
    )


@contextmanager
def _locals(context):
    previous = sys.getprofile()
    codes = {
        context.method.__code__: "makeECM",
        _INIT.__code__: "grid_constructor",
        _GRID.__code__: "cell_grid",
    }

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


def _check(context):
    parent = context.parent
    if (
        geometry._authority(context.request.geometry_owner) is not parent
        or parent.invalid
        or parent.thread != get_ident()
        or parent.trial is not context.prior_trial
        or core.records._digest(geometry.trial_record(parent.trial)) != context.parent_signature
        or geometry._FORWARDED.get(context.request.geometry_owner) is not context.retirement
    ):
        raise ValueError("Original geometry lineage or irreversible ECM claim changed")
    geometry._check(parent)
    parameter = parameters._authority(parent.parent.parameter_owner)
    if parameter.descriptor_info is not context.parameter_info:
        raise ValueError("Original selected parameter descriptor changed")
    aliases.validate(context.parameter_info)
    completion._check_binding_identity(_bindings(), context.bindings)
    if hasattr(context, "method"):
        completion._check_binding_identity(
            _namespace_bindings(context.method), context.namespace_bindings
        )
    if _verify_sources() != context.producers:
        raise ValueError("Owned ECM source/helper producer changed")
    if context.grid is not None or context.finished:
        _require_descriptor_read(context)
    if context.finished:
        caller, grid = parent.parent.caller, context.grid
        if (
            not context.constructed
            or not context.initialized
            or _GRIDS.get(grid) is not context
            or type(grid) is not _GridRuntime
        ):
            raise ValueError("Native grid did not complete on its issued object")
        pairs = (
            (caller.grid_obj, grid),
            (caller.X, grid.cents_X),
            (caller.Y, grid.cents_Y),
            (caller.xypts, grid.xy_cents),
            (caller.map_ij2k, grid.map_ij2k_cents),
            (caller.all_points_cell_i, caller.cell_i),
        )
        if any(a is not b for a, b in pairs):
            raise ValueError("Original grid/ECM aliases changed")


def trial_record(trial):
    return dict(
        request=trial.request_identity,
        parent=trial.parent_identity,
        before=trial.before.identity,
        cache=trial.cache.identity,
        stream_before=trial.stream_before.identity,
        stream_after=trial.stream_after.identity,
        events=trial.events,
        work=trial.work,
        source_completed=trial.source_completed,
        failure_stage=trial.failure_stage,
        failure_type=trial.failure_type,
        failure_message=trial.failure_message,
        invalidated_owners=INVALIDATED_OWNERS,
        full_Parameters_phase_environment_physical_checkpoint=False,
    )


class EcmOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use prepare/from_geometry for owned makeECM")

    def __reduce_ex__(self, protocol):
        raise TypeError("Owned native ECM authority cannot be serialized")

    @property
    def cells(self):
        return _validate(self).parent.parent.caller

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not EcmOwner or owner not in _ISSUED:
        raise EcmRejected("Issued live ECM authority unavailable", stage="ecm_owner")
    return _ISSUED[owner]


def _graphs(context):
    return (
        *geometry.meshes._graphs(context.parent.parent.mesh_context),
        geometry.callers._graph(
            context.grid, context.parent.parent.p, context.parent.parent.mesh_context.graph_tape
        ),
    )


def _validate(owner):
    context = _authority(owner)
    if owner in _FORWARDED:
        raise EcmRejected(
            "ECM epoch was consumed by an environment attempt",
            stage="ecm_epoch_consumed",
            trial=context.trial,
        )
    try:
        if context.invalid or context.thread != get_ident() or context.active:
            raise ValueError("Invalid completed ECM authority")
        _check(context)
        if _snapshot(context).identity != context.trial.cache.identity:
            raise ValueError("Changed ECM/grid state")
        if core.records._digest(trial_record(context.trial)) != context.trial.identity:
            raise ValueError("Changed sealed ECM trial")
        geometry.meshes._same_graphs(_graphs(context), context.graphs)
        core.caches.validate(context.trial.cache)
    except Exception as error:
        context.invalid = True
        raise EcmRejected(
            "Stale live ECM owner",
            stage="ecm_drift",
            trial=context.trial,
            request=context.request,
            source_error=error,
        ) from error
    return context


def _claim_for_environment(owner, *, expected, transition):
    with _LOCK:
        context = _validate(owner)
        if context is not expected:
            raise EcmRejected("Actual ECM owner changed", stage="ecm_owner")
        _FORWARDED[owner] = transition
        return context


@contextmanager
def _account(context):
    with completion._account_prefix(
        context,
        _source_modules=(source, aliases, geometry.source, parameters.geometry_source),
        _entry_names=(
            "makeECM",
            "cell_grid",
            "__get__",
            "_descriptor_from_source",
            *geometry.METHODS,
        ),
    ):
        previous = sys.getprofile()

        def profile(frame, event, arg):
            module = frame.f_globals.get("__name__", "")
            if event == "call" and (module == "betse" or module.startswith("betse.")):
                context.work.append(
                    dict(
                        sequence=len(context.work),
                        phase=context.stage,
                        layer="native_descriptor_factory_or_read",
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


def prepare_continuation(request, *, _work=None):
    if type(request) is not ContinuationRequest:
        raise EcmRejected("Typed actual geometry owner required", stage="request_owner")
    if _work is None:
        work = SimpleNamespace(stage="makeECM", work=[])
        with _account(work):
            return prepare_continuation(request, _work=work)
    parent = geometry._authority(request.geometry_owner)
    context = SimpleNamespace(
        request=request,
        parent=parent,
        prior_trial=parent.trial,
        thread=get_ident(),
        retirement=object(),
        invalid=False,
        active=False,
        grid=None,
        constructed=False,
        constructing=False,
        initialized=False,
        initializing=False,
        descriptor_read_started=False,
        descriptor_read_completed=False,
        descriptor_read_instance=None,
        descriptor_read_return_instance=None,
        descriptor_read_native=None,
        descriptor_read_epoch=None,
        finished=False,
        stage="preflight",
        events=[],
        locals={},
        snapshots=[],
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
        prefix=_work,
    )
    error = None
    with _LOCK:
        try:
            actual, parameter = _preflight(request.geometry_owner)
            if (
                actual is not parent
                or core.records._digest(request_record(request)) != request.identity
            ):
                raise ValueError("Original ECM continuation request changed")
            context.parameter_info = parameter.descriptor_info
            context.parent_signature = core.records._digest(geometry.trial_record(parent.trial))
            context.producers, context.bindings = _verify_sources(), _bindings()
            context.before = _snapshot(context)
            context.snapshots.append(("before", context.before))
            context.stream_before = core.initial._rng_stream(parent.parent.rng)
            context.stage = "retirement"
            geometry._claim_for_makeECM(
                request.geometry_owner, expected=parent, transition=context.retirement
            )
            context.stage = "namespace"
            context.method = _namespace(context)
            context.namespace_bindings = _namespace_bindings(context.method)
            context.active = True
            context.check = lambda: _check(context)
            context.observe = lambda kind, raw: _observe(context, kind, raw)
            context.stage = _work.stage = "makeECM"
            with aliases.reading(parent.parent.p, context), _locals(context):
                context.method(parent.parent.caller, parent.parent.p)
            if context.observation_error is None:
                context.finished = True
                context.stage = "source_checks"
                _check(context)
        except Exception as failure:
            if not isinstance(failure, _CaptureStop):
                error = failure
        finally:
            context.active = False
    partial = dict(
        context=context,
        parent_trial=context.prior_trial,
        caller=parent.parent.caller,
        parameters=parent.parent.p,
        mesh=parent.parent.mesh_context.kernel,
        grid=context.grid,
        rng=parent.parent.rng,
        stage=context.stage,
        events=context.events,
        raw_locals=context.locals,
        snapshots=context.snapshots,
        work=_work.work,
        observation_errors=context.observation_errors,
        observation_origin=context.observation_origin,
        observation_raw=context.observation_raw,
        descriptor_read=dict(
            started=context.descriptor_read_started,
            completed=context.descriptor_read_completed,
            instance=context.descriptor_read_instance,
            returned_instance=context.descriptor_read_return_instance,
            native=context.descriptor_read_native,
            epoch=context.descriptor_read_epoch,
        ),
        grid_stage=dict(constructed=context.constructed, initialized=context.initialized),
        geometry_consumed=request.geometry_owner in geometry._FORWARDED,
        usable_ecm_child_available=False,
    )
    if context.observation_error is not None:
        raise EcmRejected(
            "ECM observation failed",
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
            context.stream_before,
            core.initial._rng_stream(parent.parent.rng),
            tuple(kind for kind, _ in context.events),
            tuple(dict(e) for e in _work.work),
            error is None,
            None if error is None else context.stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise EcmRejected(
            "ECM trial sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error if error is not None else capture)
    if error is not None:
        raise EcmRejected(
            "Original ECM source/ownership attempt failed",
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
        child = object.__new__(EcmOwner)
        _ISSUED[child] = context
        return child
    except Exception as capture:
        raise EcmRejected(
            "ECM child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture


def prepare(request):
    if (
        type(request) is not Request
        or core.records._digest(dict(law=LAW_ID, geometry=request.geometry_request.identity))
        != request.identity
    ):
        raise EcmRejected("Typed fresh makeECM prefix request required", stage="request_owner")
    context = SimpleNamespace(stage="geometry_prefix", work=[], parent=None)
    try:
        with _account(context):
            context.parent = geometry.prepare(request.geometry_request)
            context.stage = "makeECM"
            return prepare_continuation(from_geometry(context.parent, law_id=LAW_ID), _work=context)
    except Exception as error:
        raise EcmRejected(
            "Owned makeECM prefix failed",
            stage=context.stage,
            request=request,
            partial=dict(parent=context.parent, prefix=context, work=context.work),
            source_error=error,
        ) from error


def require_environment(owner, *, phase=None):
    context = _validate(owner)
    raise EcmRejected(
        "environment/mask/Poisson and full phase authority remain unavailable",
        stage="environment_held",
        trial=context.trial,
        partial=dict(
            invalidated_owners=INVALIDATED_OWNERS,
            supplied_phase=phase,
            full_Parameters_physical_checkpoint_admitted=False,
        ),
    )
