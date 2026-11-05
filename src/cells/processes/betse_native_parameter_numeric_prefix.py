"""Original ordered general/time/world parameter prefix, never full Parameters.

Native arithmetic is compiled from the pinned original slice, not duplicated.
No actual numerical work is released by metadata preparation or synthetic tests.
"""

import ast
import copy
import io
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_construction_lease as claims
from cells.processes import betse_native_parameter_subconfigurations as previous

LAW_ID = "betse_native_parameter_general_time_world_prefix@1"
PREVIOUS_SHA256 = "3e49f8ebfd3cad35df7d642643fee8ebfd72115c34354c761194f7176102e7fb"
RELEASE = "CELLS_NATIVE_PARAMETER_NUMERIC_PREFIX_RELEASED"
START, STOP = 12, 29
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_LOCK, _ACTIVE = RLock(), []


class NumericPrefixRejected(ValueError):
    def __init__(
        self,
        reason,
        *,
        stage,
        request=None,
        partial=None,
        trial=None,
        source_error=None,
        capture_errors=(),
    ):
        super().__init__(reason)
        self.stage, self.request, self.partial, self.trial = stage, request, partial, trial
        self.source_error, self.capture_errors = source_error, tuple(capture_errors)


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    parent: previous.SubconfigurationsOwner
    before_trial_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live numeric-prefix requests cannot be serialized")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    before_trial_identity: str
    cache: object
    work: tuple
    stores: tuple
    source_completed: bool
    identity: str


def _digest(value):
    return previous._digest(value)


def _ast():
    native = previous.paths.prefix.parameters.inherited.tissue.aliases.NATIVE
    path = native / previous.paths.prefix.parameters.PARAMETERS
    cls = previous.paths.prefix.parameters.inherited._class(
        ast.parse(path.read_bytes()), "Parameters"
    )
    load = previous.paths.prefix.parameters.inherited._method(cls, "load")
    selected = load.body[START:STOP]
    if (
        ast.unparse(selected[0]) != "self.autoInit = self._conf['automatically run initialization']"
        or ast.unparse(selected[-1])
        != "self.use_centroids = self._conf['world options'].get('use centers', False)"
        or ast.unparse(load.body[STOP]) != "self.scheduled_options = {}"
    ):
        raise ValueError("Original numeric prefix boundaries changed")
    return path, cls, load, selected


def source_plan():
    import hashlib

    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PREVIOUS_SHA256:
        raise ValueError("Explicit same-parameter subconfiguration producer required")
    parent = previous.source_plan()
    path, cls, load, selected = _ast()
    fields = tuple(
        dict.fromkeys(
            n.targets[0].attr
            for statement in selected
            for n in ast.walk(statement)
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Attribute)
            and isinstance(n.targets[0].value, ast.Name)
            and n.targets[0].value.id == "self"
        )
    )
    return dict(
        law=LAW_ID,
        native_pins=parent["native_pins"],
        previous_producer=PREVIOUS_SHA256,
        construction_lease=claims.source_plan(),
        statement_slice=(START, STOP),
        source_lines=(selected[0].lineno, selected[-1].end_lineno),
        next_source_line=load.body[STOP].lineno,
        stores=fields,
        source_body_ast=_digest(ast.dump(ast.Module(body=selected, type_ignores=[]))),
        remaining=(
            "targeted/global declarations, network/GRN file authority, later scalar/material "
            "stores, final ion-profile construction"
        ),
        full_Parameters_ions_geometry_tissue_handler_phase_INIT_admitted=False,
    )


def _compile(context):
    path, cls, load, selected = _ast()
    native = previous.paths.prefix.parameters._method_original(context.birth.source, "load")
    expected = previous.paths.prefix.parameters._method_code(
        cls, "load", str(path), native_context=True
    )
    if (
        native.__globals__ is not vars(context.birth.source.modules["betse.science.parameters"])
        or previous.paths.prefix.parameters.inherited._code(native.__code__)
        != previous.paths.prefix.parameters.inherited._code(expected)
        or native.__defaults__ is not None
        or native.__kwdefaults__ is not None
    ):
        raise ValueError("Original Parameters.load source/header/namespace changed")
    for name, cell in zip(native.__code__.co_freevars, native.__closure__ or (), strict=True):
        if name == "__class__" and cell.cell_contents is not context.birth.source.cls:
            raise ValueError("Original Parameters.load class closure changed")
    cached = native.__globals__["__builtins__"]
    if type(cached) is not dict:
        cached = vars(cached)
    if cached is not native.__builtins__:
        raise ValueError("Original cached builtins/construction namespace changed")
    cls = copy.deepcopy(cls)
    previous.paths.prefix.parameters.inherited._method(cls, "load").body = copy.deepcopy(selected)
    code = previous.paths.prefix.parameters._method_code(cls, "load", str(path))
    if code.co_freevars:
        raise ValueError("Unexpected free variables in original scalar source slice")
    result = FunctionType(code, native.__globals__, native.__name__, native.__defaults__, None)
    if result.__builtins__ is not native.__builtins__:
        raise ValueError("Numeric slice cached builtins changed")
    return result, native


def request_record(value):
    return dict(
        law=LAW_ID,
        before=value.before_trial_identity,
        source=value.source_identity,
        same_p=True,
        no_replay=True,
    )


def from_subconfigurations(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise NumericPrefixRejected("Explicit numeric prefix law required", stage="law")
    with claims.inspection(owner) as claim:
        plan = source_plan()
        parent = claims._parent(claim)
        if any(name in vars(parent.p) for name in plan["stores"]):
            raise NumericPrefixRejected(
                "Numeric prefix may not retrofit existing stores", stage="fresh_numeric_epoch"
            )
        value = Request(owner, parent.trial.identity, _digest(plan), "")
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (
            parent,
            parent.p,
            parent.config,
            parent.trial,
            parent.graph,
            parent.authority,
        )
        return value


@contextmanager
def _handoff(context):
    context.guard = claims.retire(context.lease, context.parent)
    yield


def _stable(context):
    fields = vars(context.p)
    if tuple(fields)[: len(context.before_names)] != context.before_names or not set(
        fields
    ).issubset(set(context.before_names) | set(context.plan["stores"])):
        raise ValueError("Numeric source changed unrelated field layout")
    return previous.paths.prefix.graphs.capture(
        {name: fields[name] for name in context.before_names},
        yaml_base=context.birth.source.yaml,
        runtime_types=context.parent.runtime_types,
    )


def _check(context):
    request = context.request
    old = _REQUESTS.get(request)
    if (
        context.invalid
        or context.thread != get_ident()
        or context.guard.invalid
        or context.guard.active is not context.active
        or _CONSUMED.get(request) is not context
        or _CLAIMED.get(request.parent) is not context
        or old is None
        or _digest(request_record(request)) != request.identity
    ):
        raise ValueError("Original one-shot numeric prefix epoch changed")
    if (
        context.parent is not old[0]
        or context.p is not old[1]
        or context.config is not old[2]
        or context.parent.trial is not old[3]
        or context.parent.graph is not old[4]
        or context.parent.authority is not old[5]
        or not context.parent.invalid
        or context.parent.active
        or context.p._conf is not context.config
        or vars(context.p).get("config") is not context.config
        or type(context.p) is not context.birth.source.cls
    ):
        raise ValueError("Original same-p/subconfiguration/config association changed")
    previous.paths.prefix.parameters.inherited._same(_bindings(), context.bindings)
    previous.paths.prefix.parameters.inherited._same(previous._bindings(), context.parent.bindings)
    previous.paths.prefix.parameters.inherited._same(
        previous.paths.prefix._function_bindings(context.function), context.function_bindings
    )
    previous.paths.prefix.parameters.inherited._same(
        previous.paths.prefix._function_bindings(context.original), context.original_bindings
    )
    previous.paths.prefix.parameters.inherited._same(
        previous._native_bindings(context.parent), context.parent.native_bindings
    )
    previous.paths.prefix.parameters.inherited._same(
        previous.paths.prefix.parameters._runtime(context.birth.source), context.birth.runtime
    )
    previous.paths.prefix.parameters.inherited._same_graph(_stable(context), context.stable)
    previous._loaded(context.parent)
    previous.paths._computed(context.parent.parent)
    previous.paths.prefix._verify_file(context.parent.parent.yaml.request.file)
    if _digest(source_plan()) != request.source_identity:
        raise ValueError("Numeric prefix producer changed")


@contextmanager
def _observe(context):
    with previous.paths.prefix.parameters._observe(context):
        previous_profile, trace = sys.getprofile(), sys.gettrace()

        def profile(frame, event, arg):
            if event == "c_call" and getattr(arg, "__name__", None) in {
                "write",
                "writelines",
                "truncate",
            }:
                stream = getattr(arg, "__self__", None)
                if (
                    isinstance(stream, io.IOBase)
                    and stream is not sys.stdout
                    and stream is not sys.stderr
                ):
                    raise ValueError("Numeric prefix file writer refused")
            if previous_profile is not None:
                previous_profile(frame, event, arg)

        sys.setprofile(profile)
        try:
            yield
        finally:
            sys.setprofile(previous_profile)
            sys.settrace(trace)


def _invoke(context):
    with previous.paths.prefix.parameters.inherited.tissue.aliases.issuing_native_imports(
        previous.paths.prefix.parameters.inherited.tissue.source.SOURCE_PINS
    ):
        return context.function(context.p)


def _bindings():
    functions = (
        _ast,
        source_plan,
        _compile,
        request_record,
        from_subconfigurations,
        _handoff,
        _handoff.__wrapped__,
        _stable,
        _check,
        _observe,
        _observe.__wrapped__,
        _invoke,
        _bindings,
        trial_record,
        _validate,
        prepare,
        _prepare,
        require_ions,
    )
    return (
        (),
        (
            _REQUESTS,
            _CONSUMED,
            _CLAIMED,
            _ISSUED,
            _LOCK,
            _ACTIVE,
            LAW_ID,
            PREVIOUS_SHA256,
            RELEASE,
            START,
            STOP,
            *claims._bindings()[1],
            *(
                atom
                for fn in functions
                for atom in previous.paths.prefix.parameters.inherited.tissue.aliases._atoms(fn)
            ),
        ),
    )


def trial_record(value):
    return dict(
        law=LAW_ID,
        request=value.request_identity,
        before=value.before_trial_identity,
        cache=value.cache.identity,
        work=value.work,
        stores=value.stores,
        source_completed=value.source_completed,
        full_Parameters_or_ions_admitted=False,
    )


class NumericPrefixOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use same-p ordered numeric source prefix")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live numeric prefix owners cannot be serialized")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not NumericPrefixOwner or owner not in _ISSUED:
        raise NumericPrefixRejected("Issued numeric prefix owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced numeric prefix owner")
        _check(context)
        if not all(name in vars(context.p) for name in context.plan["stores"]):
            raise ValueError("Original numeric stores incomplete")
        previous.paths.prefix.parameters.inherited._same_graph(
            previous.paths.prefix._capture(context.view), context.graph
        )
        previous.paths.prefix.parameters.inherited._same(
            previous.paths.prefix._class_bindings(context.runtime_types), context.runtime_classes
        )
        kinds, files, namespaces = previous.paths.prefix._runtime_types(context.view)
        if kinds != context.runtime_types or files != context.runtime_files:
            raise ValueError("Numeric prefix runtime inventory changed")
        previous.paths.prefix.parameters.inherited._same(namespaces, context.runtime_namespaces)
        caches = previous.paths.prefix.parameters.inherited.tissue.core.caches
        caches.validate(context.trial.cache)
        if (
            caches.snapshot(context.graph[1]).identity != context.trial.cache.identity
            or _digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Numeric graph/trial association changed")
    except BaseException as error:
        context.invalid = True
        raise NumericPrefixRejected(
            "Stale numeric prefix owner refused",
            stage="owner_drift",
            request=context.request,
            partial=context,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def prepare(request, *, enabled=False):
    if (
        enabled is not True
        or os.environ.get(RELEASE) != "1"
        or os.environ.get(previous.RELEASE) != "1"
    ):
        raise NumericPrefixRejected(
            "Actual native numeric prefix remains held", stage="release", request=request
        )
    if _ACTIVE:
        _ACTIVE[-1].invalid = True
        raise NumericPrefixRejected(
            "Reentrant numeric prefix refused", stage="reentrant", request=request
        )
    if (
        type(request) is not Request
        or request not in _REQUESTS
        or _digest(request_record(request)) != request.identity
    ):
        raise NumericPrefixRejected(
            "Issued exact numeric prefix request required", stage="request", request=request
        )
    if request in _CONSUMED or request.parent in _CLAIMED:
        raise NumericPrefixRejected(
            "Numeric prefix attempt consumed", stage="consumed", request=request
        )
    with claims._advance(request.parent) as claim:
        return _prepare(request, claim)


def _prepare(request, claim):
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise NumericPrefixRejected(
                "Reentrant numeric prefix refused", stage="reentrant", request=request
            )
        if (
            type(request) is not Request
            or request not in _REQUESTS
            or _digest(request_record(request)) != request.identity
        ):
            raise NumericPrefixRejected(
                "Issued exact numeric prefix request required", stage="request", request=request
            )
        if request in _CONSUMED or request.parent in _CLAIMED:
            raise NumericPrefixRejected(
                "Numeric prefix attempt consumed", stage="consumed", request=request
            )
        context = SimpleNamespace(
            request=request,
            lease=claim,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="numeric_admission",
            work=[],
            locals={},
            observation_error=None,
            observation_errors=(),
            observation_origin=None,
            observation_raw=None,
            source_completed=False,
        )
        _CONSUMED[request] = _CLAIMED[request.parent] = context
        _ACTIVE.append(context)
        error = None
        try:
            context.bindings = _bindings()
            context.plan = source_plan()
            context.parent = claims._parent(claim)
            context.p = context.parent.p
            context.config = context.parent.config
            context.birth = context.parent.birth
            if any(name in vars(context.p) for name in context.plan["stores"]):
                raise ValueError("Numeric prefix cannot overwrite existing stores")
            context.function, context.original = _compile(context)
            context.function_bindings = previous.paths.prefix._function_bindings(context.function)
            context.original_bindings = previous.paths.prefix._function_bindings(context.original)
            context.before_names = tuple(vars(context.p))
            context.stable = _stable(context)
            with _handoff(context):
                _check(context)
                context.stage = "native_general_time_world"
                with _observe(context):
                    _invoke(context)
                context.source_completed = True
                if context.observation_error is None:
                    _check(context)
                    if not all(name in vars(context.p) for name in context.plan["stores"]):
                        raise ValueError("Native numeric source returned incomplete stores")
                    context.stage = "numeric_capture"
                    context.file_record = context.parent.parent.file_record
                    context.view = SimpleNamespace(
                        p=context.p,
                        parent=context.birth,
                        file_record=context.file_record,
                        runtime_types=context.parent.runtime_types,
                    )
                    context.runtime_types, context.runtime_files, context.runtime_namespaces = (
                        previous.paths.prefix._runtime_types(context.view)
                    )
                    context.runtime_classes = previous.paths.prefix._class_bindings(
                        context.runtime_types
                    )
                    context.view.runtime_types = context.runtime_types
                    context.graph = previous.paths.prefix._capture(context.view)
                    cache = previous.paths.prefix.parameters.inherited.tissue.core.caches.snapshot(
                        context.graph[1]
                    )
                    trial = Trial(
                        request.identity,
                        context.parent.trial.identity,
                        cache,
                        tuple(context.work),
                        tuple(context.plan["stores"]),
                        True,
                        "",
                    )
                    context.trial = replace(trial, identity=_digest(trial_record(trial)))
                    _check(context)
                    previous.paths.prefix.parameters.inherited._same_graph(
                        previous.paths.prefix._capture(context.view), context.graph
                    )
                    owner = object.__new__(NumericPrefixOwner)
                    _check(context)
                    context.owner = owner
                    _ISSUED[owner] = context
                    return owner
        except BaseException as primary:
            if context.stage == "numeric_capture":
                previous.paths.prefix.parameters.inherited.tissue.captures._remember_observation_error(
                    context, primary, origin=context.stage, raw=context
                )
            else:
                error = primary
        finally:
            context.active = False
            _ACTIVE.pop()
        context.invalid = True
        refusal = NumericPrefixRejected(
            "Numeric source prefix issued no child",
            stage=context.stage,
            request=request,
            partial=context,
            source_error=error,
            capture_errors=context.observation_errors,
        )
        raise refusal from (error if error is not None else context.observation_error)


def require_ions(owner):
    context = _validate(owner)
    raise NumericPrefixRejected(
        "Earlier event/network/GRN/scalar stores and the final ion-profile call remain unavailable",
        stage="ion_profile_prerequisites",
        request=context.request,
        trial=context.trial,
        partial=dict(
            next_source_line=source_plan()["next_source_line"],
            ions_full_Parameters_phase_INIT_admitted=False,
        ),
    )
