"""Same-caller ordinary initial geometry methods, stopping before makeECM.

This is an explicit normalized-method boundary. It never calls or fabricates
make_world/SimPhase/callback/package authority. Actual source work remains held.
The original object-array, empty/degenerate and operator failures are retained.
"""

import ast
import hashlib
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary, WeakSet

from cells.processes import betse_native_single_cell_caller_completion as completion
from cells.processes import betse_post_cut_mesh_contact_source as source

parameters = completion.parameters
core, callers, meshes = completion.core, completion.callers, completion.meshes
images = completion.images
LAW_ID = "betse_owned_single_cell_initial_geometry_methods@1"
INVALIDATED_OWNERS = core.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
SOURCE_SHA256 = "432e2453c4b5e0a4d46eb46c79bb1440093a042caa44ac2d00e09d20130de4b7"
METHODS = ("cellVerts", "cellMatrices", "cell_vols", "mem_processing", "near_neigh")
_NATIVE = {name: getattr(source.CellKernel, name) for name in METHODS}
_NUMPY_HELPERS = ("asarray", "array", "sqrt", "vstack", "zeros", "abs", "roll", "dot")
_ISSUED = WeakKeyDictionary()
_FORWARDED = WeakKeyDictionary()
_BUSY = WeakSet()
_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class Request:
    prefix_request: completion.Request
    identity: str


@dataclass(frozen=True, slots=True)
class ContinuationRequest:
    caller_owner: completion.CallerOwner
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    cache: object
    stages: tuple
    work: tuple
    stream_before: object
    stream_after: object
    source_completed: bool
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str
    parameter_projection: str = parameters.GEOMETRY
    parameter_store_roster: tuple = ()
    parameter_store_lines: tuple = ()


class GeometryRejected(ValueError):
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
    pins = completion._verify_sources()
    path = Path(source.__file__).resolve()
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Reviewed native geometry transcription changed")
    native = callers.NATIVE_ROOT / "betse/science/cells.py"
    original = ast.parse(native.read_text())
    cls = next(n for n in original.body if isinstance(n, ast.ClassDef) and n.name == "Cells")
    transcribed = ast.parse(path.read_text())
    dst = next(
        n for n in transcribed.body if isinstance(n, ast.ClassDef) and n.name == "CellKernel"
    )
    for name in METHODS:
        a = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
        b = next(n for n in dst.body if isinstance(n, ast.FunctionDef) and n.name == name)
        if ast.dump(ast.Module(body=a.body, type_ignores=[])) != ast.dump(
            ast.Module(body=b.body, type_ignores=[])
        ):
            raise ValueError("Literal ordinary-initialization method changed: " + name)
    for file in (path, Path(__file__).resolve(), Path(completion.__file__).resolve()):
        pins[str(file)] = hashlib.sha256(file.read_bytes()).hexdigest()
    return pins


def _callable_bindings(methods):
    return tuple(part for method in methods for part in (method, getattr(method, "__code__", None)))


def _bindings():
    return _callable_bindings(
        (
            *_NATIVE.values(),
            source.flatten,
            source.cKDTree,
            *(getattr(source.np, name) for name in _NUMPY_HELPERS),
            source.np.linalg.norm,
            source.np.linalg.pinv,
            source.copy.deepcopy,
        )
    )


def _namespace_bindings(methods, context):
    bindings = []
    for name in METHODS:
        method = methods[name]
        namespace = method.__globals__
        np, math, tb, logs = (namespace[key] for key in ("np", "math", "tb", "logs"))
        if logs.context is not context:
            raise ValueError("Geometry log observer context changed")
        flatten = tb.flatten
        copy = flatten.__globals__["copy"]
        log_method = logs.log_info
        # Attribute lookup creates a new bound-method object. Retain the exact
        # underlying callable/code and receiver instead of that temporary view.
        log_callable = getattr(log_method, "__func__", log_method)
        bindings.extend(
            (
                method,
                method.__code__,
                np,
                np.linalg,
                namespace["cKDTree"],
                math,
                tb,
                copy,
                logs,
                getattr(log_method, "__self__", None),
            )
        )
        bindings.extend(
            _callable_bindings(
                (
                    *(getattr(np, helper) for helper in _NUMPY_HELPERS),
                    np.linalg.norm,
                    np.linalg.pinv,
                    namespace["cKDTree"],
                    flatten,
                    copy.deepcopy,
                    log_callable,
                )
            )
        )
    return tuple(bindings)


def _namespace_constants(methods):
    values = []
    for name in METHODS:
        pi = methods[name].__globals__["math"].pi
        if type(pi) is not float:
            raise ValueError("Geometry math.pi type changed")
        # Compare exact float bits, separately from identity-based callable and
        # object bindings. Do not accept equal values with a different type.
        values.append(float.hex(pi))
    return tuple(values)


def from_core(parent, configuration, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise GeometryRejected("Explicit initial-geometry method law required", stage="opt_in")
    p = parameters.from_core(
        parent, configuration, law_id=parameters.GEOMETRY_LAW_ID, projection=parameters.GEOMETRY
    )
    prefix = completion.Request(
        p,
        core.records._digest(dict(law=completion.LAW_ID, parameters=parameters.request_record(p))),
    )
    value = Request(prefix, "")
    return replace(value, identity=core.records._digest(dict(law=LAW_ID, prefix=prefix.identity)))


def _preflight(owner):
    context = completion._validate(owner)
    parameter = parameters._validate_binding(
        context.parameter_owner, context.mesh_context.parent_caller["request"], context.p
    )
    if (
        parameter.request.projection not in (parameters.GEOMETRY, parameters.ENVIRONMENT)
        or parameter.trial.projection != parameter.request.projection
        or parameter.trial.store_roster != parameters._projection(parameter.request.projection)[3]
    ):
        raise GeometryRejected(
            "Fresh original cell_space/scale_cell/tm parameter stores are unavailable",
            stage="geometry_parameter_prerequisite",
            trial=context.trial,
        )
    return context


def request_record(request):
    parent = completion._authority(request.caller_owner)
    parameter = parameters._authority(parent.parameter_owner).trial
    return dict(
        law=LAW_ID,
        parent=parent.trial.identity,
        parameter=parameters._authority(parent.parameter_owner).trial.identity,
        parameter_projection=parameter.projection,
        parameter_store_roster=parameter.store_roster,
        parameter_store_lines=parameter.store_lines,
        methods=METHODS,
        boundary="ordinary make_world normalized methods; stop before makeECM",
        phase_callback_package_admitted=False,
        invalidated_owners=INVALIDATED_OWNERS,
    )


def from_caller(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise GeometryRejected("Explicit initial-geometry method law required", stage="opt_in")
    _preflight(owner)
    request = ContinuationRequest(owner, "")
    return replace(request, identity=core.records._digest(request_record(request)))


def _snapshot(context):
    return completion._snapshot(context.parent)


class _Logs:
    """Observational log sink; not native logging or phase/callback authority."""

    def __init__(self, context):
        self.context = context

    def log_info(self, *args):
        try:
            self.context.logs.append(args)
        except Exception as capture:
            _remember_observation_error(self.context, capture, origin="log_info", raw=args)


def _remember_observation_error(context, error, *, origin, raw):
    # Defer observer errors until the method boundary. Raising from a profile
    # return/unwind hook or a source finally/log call would erase its primary
    # exception and disable the profiler/native guard.
    if context.observation_error is None:
        context.observation_error = error
        context.observation_origin = origin
        context.observation_raw = raw
    context.observation_errors = (*context.observation_errors, (origin, error))


def _capture_locals(context, name, frame):
    context.locals[name] = dict(frame.f_locals)


def _namespace(context):
    # Keep original helpers and numerical implementation. The per-attempt log
    # sink observes messages, explicitly outside package/callback authority.
    namespace = dict(source.__dict__)
    namespace["logs"] = _Logs(context)
    return {
        name: FunctionType(
            _NATIVE[name].__code__,
            namespace,
            name,
            _NATIVE[name].__defaults__,
            _NATIVE[name].__closure__,
        )
        for name in METHODS
    }


@contextmanager
def _retain_locals(context):
    previous = sys.getprofile()
    codes = {method.__code__: name for name, method in context.methods.items()}

    def profile(frame, event, arg):
        if frame.f_code in codes and event == "return":
            # A return notification also occurs on exception unwinding. These
            # are raw last locals, not success credit or hydration instructions.
            try:
                _capture_locals(context, codes[frame.f_code], frame)
            except Exception as capture:
                _remember_observation_error(context, capture, origin="return_locals", raw=frame)
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)


def trial_record(trial):
    return dict(
        request=trial.request_identity,
        parent=trial.parent_identity,
        cache=trial.cache.identity,
        stages=[(name, cache.identity) for name, cache in trial.stages],
        work=trial.work,
        stream_before=trial.stream_before.identity,
        stream_after=trial.stream_after.identity,
        source_completed=trial.source_completed,
        parameter_projection=trial.parameter_projection,
        parameter_store_roster=trial.parameter_store_roster,
        parameter_store_lines=trial.parameter_store_lines,
        failure_stage=trial.failure_stage,
        failure_type=trial.failure_type,
        failure_message=trial.failure_message,
        physical_general_DEC_checkpoint_admitted=False,
        phase_callback_package_admitted=False,
        invalidated_owners=INVALIDATED_OWNERS,
    )


class GeometryOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the owned initial-geometry continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live initial-geometry source authority cannot be serialized")

    @property
    def cells(self):
        return _validate(self).parent.caller

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not GeometryOwner or owner not in _ISSUED:
        raise GeometryRejected("Issued geometry-method owner unavailable", stage="geometry_owner")
    return _ISSUED[owner]


def _parent_signature(parent):
    return core.records._digest(completion.trial_record(parent.trial))


def _check(context):
    parent = context.parent
    if (
        completion._authority(context.request.caller_owner) is not parent
        or parent.invalid
        or parent.trial is not context.prior_trial
        or completion._FORWARDED.get(context.request.caller_owner) is not context.retirement
        or completion._parent_records(parent.mesh_context) != context.mesh_parent_records
        or _parent_signature(parent) != context.parent_signature
    ):
        raise ValueError("Original caller lineage or irreversible geometry claim changed")
    completion._check_binding_identity(completion._bindings(), parent.bindings)
    completion._check_runtime_authority(parent)
    mesh = parent.mesh_context
    if (
        parent.caller.mesh is not mesh.kernel
        or mesh.rng is not parent.rng
        or mesh.kernel._cells_rng.rng is not parent.rng
        or mesh.parent_caller["invalid"]
        or mesh.parent_image["invalid"]
        or completion.callers._retirement_token(mesh.parent_image["request"].caller)
        is not mesh.retirement
    ):
        raise ValueError("Original caller/mesh/RNG links changed")
    parameter = parameters._validate_binding(
        parent.parameter_owner, mesh.parent_caller["request"], parent.p
    )
    if (
        parameter.trial.projection not in (parameters.GEOMETRY, parameters.ENVIRONMENT)
        or (parameter.trial.projection, parameter.trial.store_roster, parameter.trial.store_lines)
        != context.parameter_signature
    ):
        raise ValueError("Original geometry parameter projection/store roster changed")
    completion._check_binding_identity(_bindings(), context.bindings)
    completion._check_binding_identity(
        _namespace_bindings(context.methods, context), context.namespace_bindings
    )
    if _namespace_constants(context.methods) != context.namespace_constants:
        raise ValueError("Geometry math.pi value changed")
    if _verify_sources() != context.producers:
        raise ValueError("Geometry source/helper bindings changed")
    if (
        core.caches.snapshot(core.initial._public_cache(mesh.kernel)).identity
        != context.mesh_before.identity
    ):
        raise ValueError("Geometry methods changed the retained DEC mesh")
    if core.initial._rng_stream(parent.rng).identity != context.stream_before.identity:
        raise ValueError("Geometry methods changed the continuing RNG epoch")


def _validate(owner):
    context = _authority(owner)
    if owner in _FORWARDED:
        raise GeometryRejected(
            "Geometry epoch was consumed by a makeECM attempt",
            stage="geometry_epoch_consumed",
            trial=context.trial,
        )
    try:
        if context.invalid or context.thread != get_ident():
            raise ValueError("Invalid initial-geometry source owner")
        _check(context)
        if (
            context.trial.parameter_projection,
            context.trial.parameter_store_roster,
            context.trial.parameter_store_lines,
        ) != context.parameter_signature:
            raise ValueError("Sealed geometry trial changed its parameter projection/store roster")
        if _snapshot(context).identity != context.trial.cache.identity:
            raise ValueError("Changed geometry-method state")
        if core.records._digest(trial_record(context.trial)) != context.trial.identity:
            raise ValueError("Changed sealed geometry trial")
        meshes._same_graphs(meshes._graphs(context.parent.mesh_context), context.graphs)
        for cache in (context.trial.cache, *(cache for _, cache in context.trial.stages)):
            core.caches.validate(cache)
    except Exception as error:
        context.invalid = True
        raise GeometryRejected(
            "Stale initial-geometry method owner",
            stage="geometry_drift",
            request=context.request,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def _claim_for_makeECM(owner, *, expected, transition):
    with _LOCK:
        context = _validate(owner)
        if context is not expected:
            raise GeometryRejected("Changed actual geometry owner", stage="geometry_owner")
        _FORWARDED[owner] = transition
        return context


def prepare_continuation(request, *, _prefix=None):
    if type(request) is not ContinuationRequest:
        raise GeometryRejected("Typed retained caller continuation required", stage="request_owner")
    if _prefix is None:
        accounting = SimpleNamespace(stage="initial_geometry", work=[], request=request)
        with completion._account_prefix(
            accounting, _source_modules=(source,), _entry_names=(*METHODS, "flatten")
        ):
            return prepare_continuation(request, _prefix=accounting)
    parent = completion._authority(request.caller_owner)
    context = SimpleNamespace(
        request=request,
        parent=parent,
        prior_trial=parent.trial,
        thread=get_ident(),
        invalid=False,
        retirement=object(),
        stage="preflight",
        stages=[],
        logs=[],
        locals={},
        producers=_verify_sources(),
        bindings=_bindings(),
        stream_before=None,
        prefix=_prefix,
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
    )
    error = None
    with _LOCK:
        if parent.caller in _BUSY:
            raise GeometryRejected(
                "Initial geometry is reentrant", stage="geometry_reentrant", request=request
            )
        _BUSY.add(parent.caller)
        try:
            if (
                _preflight(request.caller_owner) is not parent
                or core.records._digest(request_record(request)) != request.identity
            ):
                raise ValueError("Initial geometry request changed")
            context.parent_signature = _parent_signature(parent)
            parameter = parameters._authority(parent.parameter_owner).trial
            context.parameter_signature = (
                parameter.projection,
                parameter.store_roster,
                parameter.store_lines,
            )
            context.mesh_parent_records = completion._parent_records(parent.mesh_context)
            context.mesh_before = core.caches.snapshot(
                core.initial._public_cache(parent.mesh_context.kernel)
            )
            context.stream_before = core.initial._rng_stream(parent.rng)
            context.stages.append(("before", _snapshot(context)))
            context.stage = "retirement"
            completion._claim_for_initial_geometry(
                request.caller_owner, expected=parent, transition=context.retirement
            )
            context.stage = "namespace"
            context.methods = _namespace(context)
            context.namespace_bindings = _namespace_bindings(context.methods, context)
            context.namespace_constants = _namespace_constants(context.methods)
            with _retain_locals(context):
                for name in METHODS:
                    context.stage = name
                    if _prefix is not None:
                        _prefix.stage = "initial_geometry." + name
                    context.methods[name](parent.caller, parent.p)
                    if context.observation_error is not None:
                        break
                    try:
                        stage_snapshot = _snapshot(context)
                    except Exception as capture:
                        _remember_observation_error(
                            context, capture, origin="stage_snapshot", raw=parent.caller
                        )
                        raise
                    context.stages.append((name, stage_snapshot))
                    _check(context)
            if context.observation_error is None:
                context.stage = "source_checks"
                _check(context)
        except Exception as failure:
            if failure is not context.observation_error:
                error = failure
        finally:
            _BUSY.discard(parent.caller)
    partial = dict(
        context=context,
        parent_trial=context.prior_trial,
        caller=parent.caller,
        parameters=parent.p,
        mesh=parent.mesh_context.kernel,
        rng=parent.rng,
        source_stage=context.stage,
        stages=context.stages,
        raw_locals=context.locals,
        logs=context.logs,
        observation_errors=context.observation_errors,
        observation_origin=context.observation_origin,
        observation_raw=context.observation_raw,
        work=tuple(dict(entry) for entry in _prefix.work),
        caller_epoch_consumed=request.caller_owner in completion._FORWARDED,
        usable_geometry_child_available=False,
    )
    if context.observation_error is not None:
        raise GeometryRejected(
            "Initial geometry stage observation failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=context.observation_error,
        ) from (error if error is not None else context.observation_error)
    try:
        if context.stream_before is None:
            raise ValueError("Geometry failed before a complete source trial")
        trial = Trial(
            request.identity,
            context.prior_trial.identity,
            _snapshot(context),
            tuple(context.stages),
            () if _prefix is None else tuple(dict(entry) for entry in _prefix.work),
            context.stream_before,
            core.initial._rng_stream(parent.rng),
            error is None,
            None if error is None else context.stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
            *context.parameter_signature,
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise GeometryRejected(
            "Initial geometry source sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error if error is not None else capture)
    if error is not None:
        raise GeometryRejected(
            "Original initial geometry method failed",
            stage=context.stage,
            request=request,
            trial=trial,
            partial=partial,
            source_error=error,
        ) from error
    try:
        context.trial = trial
        _check(context)
        context.graphs = meshes._graphs(parent.mesh_context)
        child = object.__new__(GeometryOwner)
        _ISSUED[child] = context
        return child
    except Exception as capture:
        raise GeometryRejected(
            "Geometry child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture


def _prefix(request):
    return completion.prepare(request)


def prepare(request):
    if (
        type(request) is not Request
        or core.records._digest(dict(law=LAW_ID, prefix=request.prefix_request.identity))
        != request.identity
    ):
        raise GeometryRejected(
            "Unchanged typed geometry prefix required", stage="request_owner", request=request
        )
    context = SimpleNamespace(stage="caller_prefix", work=[], parent=None, request=request)
    try:
        with completion._account_prefix(
            context,
            _source_modules=(source, parameters.geometry_source),
            _entry_names=(*METHODS, "flatten"),
        ):
            context.parent = _prefix(request.prefix_request)
            context.stage = "initial_geometry"
            child = prepare_continuation(
                from_caller(context.parent, law_id=LAW_ID), _prefix=context
            )
        return child
    except Exception as error:
        raise GeometryRejected(
            "Owned initial-geometry source prefix failed",
            stage=context.stage,
            request=request,
            partial=dict(parent=context.parent, work=context.work, prefix=context),
            source_error=error,
        ) from error


def require_makeECM(owner, *, phase=None):
    context = _validate(owner)
    raise GeometryRejected(
        "makeECM/environment/grid/Poisson and full phase authority remain unavailable",
        stage="ECM_environment_held",
        trial=context.trial,
        partial=dict(
            supplied_phase=phase,
            invalidated_owners=INVALIDATED_OWNERS,
            general_DEC_physical_checkpoint_admitted=False,
        ),
    )
