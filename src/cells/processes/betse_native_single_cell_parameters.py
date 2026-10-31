"""Fresh normalized parameter ownership before Cells construction/lattice work.

Only the retained scalar stores plus the original cell-height lookup are owned.
No YAML, full Parameters, SimPhase, package or physical authority is supplied.
The live instance is constructed once, then claimed by one actual caller request.
"""

import ast
import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_single_cell_caller_completion_source as source
from cells.processes import betse_native_single_cell_caller_lattice as callers
from cells.processes import betse_native_single_cell_geometry_parameter_source as geometry_source

core = callers.core
LAW_ID = "betse_owned_single_cell_normalized_height_parameters@1"
GEOMETRY_LAW_ID = "betse_owned_single_cell_normalized_initial_geometry_parameters@1"
HEIGHT = "height"
GEOMETRY = "initial_geometry"
HELD_UNQUALIFIED_SOURCE_STAGE = True
_ACTIVE, _ISSUED, _CLAIMED = WeakKeyDictionary(), WeakKeyDictionary(), WeakKeyDictionary()
_PARAMETER_STORES = source.ParameterStores.initialize_source_stores
_GEOMETRY_STORES = geometry_source.ParameterStores.initialize_source_stores
_EXPECTED_STORES = (
    "_conf",
    "world_len",
    "cell_radius",
    "cell_lattice_disorder",
    "cell_lattice_type",
    "wsx",
    "wsy",
    "cell_height",
    "ac",
    "d_cell",
    "nx",
    "ny",
    "wsx",
    "wsy",
)


@dataclass(frozen=True, slots=True)
class Request:
    core_request: core.Request
    configuration_json: str
    identity: str
    projection: str = HEIGHT


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    cache: object
    stores: tuple
    source_completed: bool
    failure_type: str | None
    failure_message: str | None
    identity: str
    projection: str = HEIGHT
    store_roster: tuple = ()
    store_lines: tuple = ()
    stores_ast_sha256: str = ""


class ParameterRejected(ValueError):
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
    pins = callers._verify_sources()
    original = callers.NATIVE_ROOT / "betse/science/parameters.py"
    if hashlib.sha256(original.read_bytes()).hexdigest() != source.NATIVE_PARAMETERS_SHA256:
        raise ValueError("Original Parameters source changed")
    for module in (source, geometry_source):
        tree = ast.parse(Path(module.__file__).read_text())
        cls = next(
            n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ParameterStores"
        )
        body = next(n for n in cls.body if isinstance(n, ast.FunctionDef)).body
        if (
            hashlib.sha256(ast.dump(ast.Module(body=body, type_ignores=[])).encode()).hexdigest()
            != module.STORES_AST_SHA256
        ):
            raise ValueError("Changed literal ordered parameter stores")
    for path in (
        Path(__file__),
        Path(source.__file__),
        Path(geometry_source.__file__),
        Path(callers.__file__),
        original,
    ):
        pins[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pins


def request_record(request):
    projection = _projection(request.projection)
    return dict(
        law=projection[0],
        projection=request.projection,
        core_request_identity=request.core_request.identity,
        core_request=core.request_record(request.core_request),
        configuration_json=request.configuration_json,
        source_store_lines=projection[1].STORE_LINES,
        store_roster=projection[3],
        stores_ast_sha256=projection[1].STORES_AST_SHA256,
        normalized_configuration_only=True,
        full_Parameters_YAML_phase_package=False,
    )


def _projection(name):
    if name == HEIGHT:
        return LAW_ID, source, _PARAMETER_STORES, _EXPECTED_STORES
    if name == GEOMETRY:
        return (
            GEOMETRY_LAW_ID,
            geometry_source,
            _GEOMETRY_STORES,
            (
                "_conf",
                "world_len",
                "cell_radius",
                "cell_lattice_disorder",
                "cell_lattice_type",
                "wsx",
                "wsy",
                "cell_height",
                "cell_space",
                "ac",
                "scale_cell",
                "tm",
                "d_cell",
                "nx",
                "ny",
                "wsx",
                "wsy",
            ),
        )
    raise ParameterRejected("Unknown normalized parameter projection", stage="projection")


def from_core(parent, configuration, *, law_id, projection=HEIGHT):
    if (
        law_id != _projection(projection)[0]
        or type(law_id) is not str
        or type(parent) is not core.Request
    ):
        raise ParameterRejected(
            "Typed core evidence and explicit parameter law required", stage="request_owner"
        )
    callers._precheck(parent)
    if core.records._digest(core.request_record(parent)) != parent.identity:
        raise ParameterRejected(
            "Original core request identity is inconsistent", stage="upstream_identity"
        )
    text = json.dumps(configuration, allow_nan=False, separators=(",", ":"))
    if type(configuration) is not dict or len(text.encode()) > 65536:
        raise ParameterRejected(
            "Bounded normalized configuration mapping required", stage="configuration"
        )
    value = Request(parent, text, "", projection)
    return replace(value, identity=core.records._digest(request_record(value)))


def _context(p):
    context = _ACTIVE.get(p)
    if context is None or context.thread != get_ident():
        raise ParameterRejected(
            "Parameter constructor/stores lack active source driver",
            stage="source_call_unavailable",
        )
    return context


class _Runtime(callers._Parameters):
    def __init__(self, recipe, configuration):
        _context(self)
        self._conf = configuration
        # Existing explicit normalized scalar boundary; dynamic dispatch below
        # executes the nine original stores on this same actual instance.
        super().__init__(recipe)

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        context = _ACTIVE.get(self)
        if context is not None:
            context.stores.append((name, core.caches.snapshot(callers._parameters(self))))

    def initialize_source_stores(self):
        context = _context(self)
        return context.store_method(self)

    def __reduce_ex__(self, protocol):
        raise TypeError("Live normalized parameter authority cannot be serialized")


def _construct(p, recipe, configuration):
    p.__init__(recipe, configuration)


def _bindings():
    methods = (
        _construct,
        _PARAMETER_STORES,
        _GEOMETRY_STORES,
        _Runtime.__init__,
        _Runtime.__setattr__,
        _Runtime.initialize_source_stores,
        callers._Parameters.__init__,
    )
    return tuple(part for method in methods for part in (method, method.__code__))


def trial_record(trial):
    return dict(
        request=trial.request_identity,
        projection=trial.projection,
        store_roster=trial.store_roster,
        store_lines=trial.store_lines,
        stores_ast_sha256=trial.stores_ast_sha256,
        cache=trial.cache.identity,
        stores=[(name, cache.identity) for name, cache in trial.stores],
        source_completed=trial.source_completed,
        failure_type=trial.failure_type,
        failure_message=trial.failure_message,
        full_Parameters_YAML_phase_package=False,
        physical_checkpoint_admitted=False,
    )


class ParameterOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use prepare_parameters with retained typed inputs")

    def __reduce_ex__(self, protocol):
        raise TypeError("Parameter source authority is process-local")

    @property
    def parameters(self):
        if self in _CLAIMED:
            raise ParameterRejected(
                "Parameter epoch already claimed by a caller", stage="parameter_epoch_consumed"
            )
        return _validate(self).p

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not ParameterOwner or owner not in _ISSUED:
        raise ParameterRejected(
            "Issued parameter source authority unavailable", stage="parameter_owner"
        )
    return _ISSUED[owner]


def _graph(context):
    return callers._graph(context.p, context.p, context.graph_tape)


def _validate(owner):
    context = _authority(owner)
    try:
        if (
            context.invalid
            or context.thread != get_ident()
            or _verify_sources() != context.producers
        ):
            raise ValueError("Changed parameter source authority")
        if type(context.p) is not _Runtime or context.p._conf is not context.configuration:
            raise ValueError("Original parameter/configuration identity changed")
        if core.records._digest(request_record(context.request)) != context.request.identity:
            raise ValueError("Changed typed parameter request")
        selected = _projection(context.projection)
        if (
            context.request.identity != context.request_identity
            or context.trial.request_identity != context.request_identity
            or context.request.projection != context.projection
            or context.trial.projection != context.projection
            or context.trial.store_roster != context.store_roster
            or context.store_roster != selected[3]
            or tuple(name for name, _ in context.trial.stores) != context.store_roster
            or context.trial.store_lines != tuple(selected[1].STORE_LINES)
            or context.trial.stores_ast_sha256 != selected[1].STORES_AST_SHA256
            or selected[2] is not context.store_method
            or selected[2].__code__ is not context.store_code
        ):
            raise ValueError("Original projection/store roster or method authority changed")
        if _bindings() != context.bindings:
            raise ValueError("Changed parameter constructor/store code")
        if (
            core.caches.snapshot(callers._parameters(context.p)).identity
            != context.trial.cache.identity
        ):
            raise ValueError("Changed parameter source cache")
        if core.records._digest(trial_record(context.trial)) != context.trial.identity:
            raise ValueError("Changed sealed parameter source trial")
        for cache in (context.trial.cache, *(c for _, c in context.trial.stores)):
            core.caches.validate(cache)
        objects, edges = _graph(context)
        old_objects, old_edges = context.graph
        if (
            edges != old_edges
            or len(objects) != len(old_objects)
            or any(a is not b for a, b in zip(objects, old_objects, strict=True))
        ):
            raise ValueError("Changed parameter/configuration reference edges")
    except Exception as error:
        context.invalid = True
        raise ParameterRejected(
            "Stale normalized parameter owner",
            stage="parameter_drift",
            request=context.request,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def _claim_for_caller(owner, request, recipe):
    _authority(owner)
    if owner in _CLAIMED:
        raise ParameterRejected(
            "Parameters already claimed by an attempted caller", stage="parameter_epoch_consumed"
        )
    context = _validate(owner)
    if request.core_request is not context.request.core_request or recipe != context.recipe:
        raise ParameterRejected(
            "Actual caller does not own these parameter inputs", stage="caller_identity"
        )
    _CLAIMED[owner] = request
    return context.p


def _validate_binding(owner, request, p):
    context = _validate(owner)
    if (
        _CLAIMED.get(owner) is not request
        or context.p is not p
        or request.core_request is not context.request.core_request
    ):
        raise ParameterRejected(
            "Original claimed caller/parameter relationship unavailable", stage="caller_identity"
        )
    return context


def prepare_parameters(request):
    if type(request) is not Request:
        raise ParameterRejected(
            "Typed normalized parameter request required", stage="request_owner"
        )
    if (
        type(request.configuration_json) is not str
        or len(request.configuration_json.encode()) > 65536
    ):
        raise ParameterRejected(
            "Bounded normalized configuration text required", stage="configuration", request=request
        )
    configuration = json.loads(request.configuration_json)
    if type(configuration) is not dict:
        raise ParameterRejected(
            "Normalized configuration must be a mapping", stage="configuration", request=request
        )
    if core.records._digest(request_record(request)) != request.identity:
        raise ParameterRejected(
            "Changed normalized parameter request", stage="request_identity", request=request
        )
    callers._precheck(request.core_request)
    if (
        core.records._digest(core.request_record(request.core_request))
        != request.core_request.identity
    ):
        raise ParameterRejected(
            "Original core request identity is inconsistent",
            stage="upstream_identity",
            request=request,
        )
    producers = _verify_sources()
    recipe = request.core_request.initial_request.upstream[0].definition
    p = object.__new__(_Runtime)
    selected = _projection(request.projection)
    context = SimpleNamespace(
        request=request,
        p=p,
        recipe=recipe,
        configuration=configuration,
        stores=[],
        thread=get_ident(),
        producers=producers,
        bindings=_bindings(),
        invalid=False,
        request_identity=request.identity,
        projection=request.projection,
        store_roster=selected[3],
        store_method=selected[2],
        store_code=selected[2].__code__,
    )
    error = None
    _ACTIVE[p] = context
    try:
        _construct(p, recipe, configuration)
        if (
            p._conf is not configuration
            or type(p.cell_height) is not float
            or context.request.identity != context.request_identity
            or context.request.projection != context.projection
            or tuple(name for name, _ in context.stores) != context.store_roster
            or _bindings() != context.bindings
        ):
            raise ValueError("Original parameter object/ordered store sequence did not complete")
    except Exception as failure:
        error = failure
    finally:
        _ACTIVE.pop(p, None)
    partial = dict(
        parameters=p,
        configuration=configuration,
        stores=context.stores,
        request=request,
        usable_parameter_owner_available=False,
    )
    try:
        cache = core.caches.snapshot(callers._parameters(p))
        trial = Trial(
            request.identity,
            cache,
            tuple(context.stores),
            error is None,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
            context.projection,
            context.store_roster,
            tuple(selected[1].STORE_LINES),
            selected[1].STORES_AST_SHA256,
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise ParameterRejected(
            "Parameter source sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error if error is not None else capture)
    if error is not None:
        raise ParameterRejected(
            "Original parameter construction failed",
            stage="parameter_stores",
            request=request,
            trial=trial,
            partial=partial,
            source_error=error,
        ) from error
    try:
        if _verify_sources() != producers:
            raise ValueError("Parameter producer drift during construction")
        context.trial = trial
        context.graph_tape = SimpleNamespace(
            rng=None, events=[name for name, _ in context.stores], draws=[], locals={}
        )
        context.graph = _graph(context)
        owner = object.__new__(ParameterOwner)
        _ISSUED[owner] = context
        return owner
    except Exception as capture:
        raise ParameterRejected(
            "Parameter owner issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture
