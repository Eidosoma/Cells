"""Declared mapping probes under a read-only lease of the actual multi caller.

Two selected literal methods and helpers; no geometry/phase/field constructor,
supplied-state hydration, mask repair or numerical/physical admission. Actual
conversion/interpolation/source execution remains coordinated work.
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
from cells.processes import betse_native_tissue_to_grid_source as source

core, multi, geometry, aliases = world.core, world.multi, world.geometry, world.aliases
LAW_ID = "betse_actual_multi_caller_declared_mapping_probes@1"
METHODS = ("map_cells_centre_to_grids_centre", "map_cells_centre_to_points")
_NATIVE = {name: getattr(source.CellMappings, name) for name in METHODS}
_FROM, _SEQUENCE = source.from_iterable, source.is_sequence
_ASARRAY, _GRIDDATA = source.np.asarray, source.interp.griddata
_LOCK = RLock()
_ISSUED = WeakKeyDictionary()
_LEASE_REQUESTS = WeakKeyDictionary()
INVALIDATED_OWNERS = world.INVALIDATED_OWNERS


@dataclass(frozen=True, slots=True)
class Probe:
    name: str
    method: str
    data: object
    target_points: object = None
    interp_method: str = "linear"
    data_factor: object = 1


@dataclass(frozen=True, slots=True)
class Request:
    world_owner: world.WorldDataOwner
    probes: tuple
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    after: object
    results: tuple
    events: tuple
    work: tuple
    warnings: tuple
    source_completed: bool
    failure_stage: str | None
    identity: str


class MappingRejected(world.FinalizationRejected):
    pass


def _body(node):
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return ast.dump(ast.Module(body=body, type_ignores=[]))


def _signature(node):
    args = node.args
    return ast.dump(
        ast.arguments(
            posonlyargs=[ast.arg(arg=a.arg) for a in args.posonlyargs],
            args=[ast.arg(arg=a.arg) for a in args.args],
            vararg=None if args.vararg is None else ast.arg(arg=args.vararg.arg),
            kwonlyargs=[ast.arg(arg=a.arg) for a in args.kwonlyargs],
            kw_defaults=args.kw_defaults,
            kwarg=None if args.kwarg is None else ast.arg(arg=args.kwarg.arg),
            defaults=args.defaults,
        )
    )


def _verify_sources():
    pins = world._verify_sources()
    for relative, expected in source.SOURCE_PINS.items():
        path = multi.callers.NATIVE_ROOT / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Original mapping/helper source changed")
        pins[str(path)] = expected
    native = next(
        n
        for n in ast.parse((multi.callers.NATIVE_ROOT / "betse/science/cells.py").read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "Cells"
    )
    own_tree = ast.parse(Path(source.__file__).read_text())
    owned = next(
        n for n in own_tree.body if isinstance(n, ast.ClassDef) and n.name == "CellMappings"
    )
    for name in METHODS:
        a = next(n for n in native.body if isinstance(n, ast.FunctionDef) and n.name == name)
        b = next(n for n in owned.body if isinstance(n, ast.FunctionDef) and n.name == name)
        if (
            _body(a) != _body(b)
            or _signature(a) != _signature(b)
            or source.NATIVE_LINES[name] != (a.lineno, a.end_lineno)
        ):
            raise ValueError("Literal mapping body/order changed")
    for path, name in (
        ("betse/lib/numpy/nparray.py", "from_iterable"),
        ("betse/util/type/iterable/sequences.py", "is_sequence"),
    ):
        a = next(
            n
            for n in ast.parse((multi.callers.NATIVE_ROOT / path).read_text()).body
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
        b = next(n for n in own_tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        if (
            _body(a) != _body(b)
            or _signature(a) != _signature(b)
            or source.NATIVE_LINES[name] != (a.lineno, a.end_lineno)
        ):
            raise ValueError("Literal iterable/sequence helper changed")
    exceptions = ast.parse((multi.callers.NATIVE_ROOT / "betse/exceptions.py").read_text())
    for name in (
        "BetseException",
        "BetseTypeException",
        "BetseIterableException",
        "BetseSequenceException",
    ):
        a = next(n for n in exceptions.body if isinstance(n, ast.ClassDef) and n.name == name)
        b = next(n for n in own_tree.body if isinstance(n, ast.ClassDef) and n.name == name)
        if ast.dump(a) != ast.dump(b):
            raise ValueError("Literal selected exception hierarchy changed")
    for module in (source, sys.modules[__name__]):
        pins[str(Path(module.__file__).resolve())] = hashlib.sha256(
            Path(module.__file__).read_bytes()
        ).hexdigest()
    return pins


def _verify_pin_bytes(pins):
    """Reuse an AST proof only while every exact producer byte is unchanged."""
    for name, expected in pins.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != expected:
            raise ValueError("Retained source-correspondence producer changed")
    return dict(pins)


def _bindings():
    functions = (
        *_NATIVE.values(),
        _FROM,
        _SEQUENCE,
        _ASARRAY,
        _GRIDDATA,
        source.np.asarray,
        source.interp.griddata,
        source.from_iterable,
        source.is_sequence,
        _verify_sources,
        _verify_pin_bytes,
        _body,
        _signature,
        _bindings,
        _check,
        _event,
        _stop,
        _helper,
        _invoke,
        _namespace,
        _namespace_bindings,
        _request_record,
        _probe_record,
        _snapshot_inputs,
        _graphs,
        _account,
        _deliver_prior_profile,
        _validate,
        _authority,
        _authorize_lease,
        from_world,
        prepare,
        trial_record,
        MappingOwner.results.fget,
        MappingOwner.trial.fget,
        multi._mapping_read_lease,
        multi._mapping_entry,
        multi._lease_callbacks,
        multi._check_mapping_lease,
        multi._Caller.__setattr__,
        multi._Caller.map_cells_centre_to_grids_centre,
        multi._Caller.map_cells_centre_to_points,
        world._validate,
        world._authority,
        world._snapshot,
        world._graphs,
        world._bindings,
        builtins.len,
        builtins.tuple,
        builtins.all,
        builtins.isinstance,
    )
    return (
        *world._bindings(),
        source.np,
        source.interp,
        source.SequenceTypes,
        source.NumpyArrayType,
        source.BetseSequenceException,
        source.BetseSequenceException.__mro__,
        *aliases._atoms(source.BetseSequenceException.__init__),
        *aliases._atoms(source.BetseSequenceException.__new__),
        multi._READ_LEASES,
        multi._ReadLease,
        _ISSUED,
        _LEASE_REQUESTS,
        _LOCK,
        *(
            atom
            for fn in functions
            for value in (
                fn,
                getattr(fn, "__wrapped__", None),
                getattr(fn, "_implementation", None),
            )
            for atom in aliases._atoms(value)
        ),
    )


def _probe_record(probe):
    if (
        type(probe) is not Probe
        or type(probe.name) is not str
        or not probe.name
        or probe.method not in ("grids", "points")
    ):
        raise MappingRejected("Exact declared probe required", stage="probe")
    if type(probe.interp_method) is not str:
        raise MappingRejected("Declare interpolation method string", stage="probe")
    if probe.method == "grids" and (
        probe.target_points is not None
        or type(probe.data_factor) is not int
        or probe.data_factor != 1
    ):
        raise MappingRejected(
            "Grid targets and factor come only from the actual caller", stage="probe"
        )
    cache = core.caches.snapshot(
        dict(data=probe.data, target_points=probe.target_points, data_factor=probe.data_factor)
    )
    return dict(
        name=probe.name,
        method=probe.method,
        inputs=cache.identity,
        interp_method=probe.interp_method,
    )


def _request_record(request):
    parent = world._authority(request.world_owner)
    return dict(
        law=LAW_ID,
        parent=parent.trial.identity,
        probes=[_probe_record(p) for p in request.probes],
        native_source_lines=source.NATIVE_LINES,
        boundary="selected read-only mapping methods; no phase/field admission",
        metadata_verification="mapping AST proof plus exact bytes; unchanged live parent validator",
        invalidated_owners=INVALIDATED_OWNERS,
    )


def from_world(owner, probes, *, law_id):
    if (
        type(law_id) is not str
        or law_id != LAW_ID
        or type(probes) is not tuple
        or not 1 <= len(probes) <= 8
    ):
        raise MappingRejected("Explicit bounded tuple of declared probes required", stage="request")
    parent = world._validate(owner)
    if not parent.finished or not parent.trial.source_completed:
        raise MappingRejected("Completed actual world data owner required", stage="parent")
    if len({p.name for p in probes if type(p) is Probe}) != len(probes):
        raise MappingRejected("Unique declared probe names required", stage="probe")
    request = Request(owner, probes, "")
    return replace(request, identity=core.records._digest(_request_record(request)))


def _snapshot_inputs(context):
    return core.caches.snapshot(
        [
            dict(data=p.data, target_points=p.target_points, data_factor=p.data_factor)
            for p in context.request.probes
        ]
    )


def _graphs(context):
    return multi.callers._graph(context.view, context.view, context.tape)


def _namespace_bindings(context):
    values = []
    for fn in context.methods.values():
        ns = fn.__globals__
        values.extend(
            (
                fn,
                ns["nparray"],
                ns["nparray"].from_iterable,
                ns["interp"],
                ns["interp"].griddata,
                ns["len"],
                ns["BetseSequenceException"],
            )
        )
    values.extend(
        (
            context.from_iterable,
            context.sequence,
            context.from_iterable.__globals__["sequences"],
            context.from_iterable.__globals__["sequences"].is_sequence,
            context.from_iterable.__globals__["np"],
            context.from_iterable.__globals__["np"].asarray,
            context.sequence.__globals__["SequenceTypes"],
            context.sequence.__globals__["all"],
            context.sequence.__globals__["isinstance"],
            context.from_iterable.__globals__["tuple"],
        )
    )
    return tuple(atom for fn in values for atom in aliases._atoms(fn))


def _check(context):
    if (
        context.thread != get_ident()
        or world._authority(context.request.world_owner) is not context.parent
    ):
        raise ValueError("Actual mapping parent/thread changed")
    multi.accounting._check_binding_identity(_bindings(), context.bindings)
    if (
        world._validate(context.request.world_owner) is not context.parent
        or context.parent.trial is not context.parent_trial
    ):
        raise ValueError("Retained actual world authority changed")
    if core.records._digest(_request_record(context.request)) != context.request.identity:
        raise ValueError("Declared probes/request changed")
    _verify_pin_bytes(context.producers)
    if _snapshot_inputs(context).identity != context.input_cache.identity:
        raise ValueError("Declared source input bytes changed")
    geometry.meshes._same_graphs((_graphs(context),), (context.input_graph,))
    if hasattr(context, "methods"):
        multi.accounting._check_binding_identity(
            _namespace_bindings(context), context.namespace_bindings
        )
    if context.active:
        lease = multi._READ_LEASES.get(context.caller)
        multi._check_mapping_lease(lease)
        if (
            lease is None
            or _LEASE_REQUESTS.get(context.caller) is not context
            or lease.token is not context.token
            or lease.invoke is not context.invoke
            or lease.check is not context.check
        ):
            raise ValueError("Actual caller read-only lease changed")


def _event(context, name, value):
    try:
        context.events.append((name, value))
    except Exception as capture:
        geometry._remember_observation_error(context, capture, origin=name, raw=value)


def _stop(context):
    if context.observation_error is not None:
        raise world.poisson.environment._CaptureStop()


def _helper(context, name, delegate, /, *args, **kwargs):
    _stop(context)
    if not context.active or not context.depth or context.helper_busy:
        raise MappingRejected(
            "Mapping helper outside active source call", stage="source_call_unavailable"
        )
    _check(context)
    _event(context, name + "_enter", (args, kwargs))
    _stop(context)
    context.helper_busy = True
    context.work.append(
        dict(
            sequence=len(context.work),
            layer="helper_wrapper",
            method=name,
            status="entered_not_success_credit",
        )
    )
    try:
        value = delegate(*args, **kwargs)
    except Exception:
        _event(context, name + "_unwind", (args, kwargs))
        raise
    finally:
        context.helper_busy = False
    context.last_completed = (name, args, kwargs, value)
    try:
        context.helpers.append(context.last_completed)
    except Exception as capture:
        geometry._remember_observation_error(context, capture, origin="helper_result", raw=value)
    _event(context, name + "_return", value)
    _stop(context)
    _check(context)
    return value


def _invoke(context, name, actual, /, *args, **kwargs):
    _stop(context)
    if not context.active or actual is not context.caller or context.helper_busy:
        raise MappingRejected(
            "Mapping source call outside exact caller lease", stage="source_call_unavailable"
        )
    if context.depth and (context.depth != 1 or context.method != METHODS[0] or name != METHODS[1]):
        raise MappingRejected("Unexpected/reentrant mapping source method", stage="mapping_reentry")
    _check(context)
    _event(context, name + "_enter", (args, kwargs))
    _stop(context)
    previous = context.method
    context.method = name
    context.depth += 1
    try:
        value = context.methods[name](actual, *args, **kwargs)
    except Exception:
        _event(context, name + "_unwind", (args, kwargs))
        raise
    finally:
        context.depth -= 1
        context.method = previous
    context.last_completed = (name, args, kwargs, value)
    _event(context, name + "_return", value)
    _stop(context)
    _check(context)
    return value


def _namespace(context):
    def helper(name, delegate):
        def entry(*a, **k):
            return _helper(context, name, delegate, *a, **k)

        return entry

    context.sequence = FunctionType(
        _SEQUENCE.__code__,
        dict(
            _SEQUENCE.__globals__,
            SequenceTypes=source.SequenceTypes,
            all=builtins.all,
            isinstance=builtins.isinstance,
        ),
        _SEQUENCE.__name__,
        _SEQUENCE.__defaults__,
        _SEQUENCE.__closure__,
    )
    context.from_iterable = FunctionType(
        _FROM.__code__,
        dict(
            _FROM.__globals__,
            sequences=SimpleNamespace(is_sequence=context.sequence),
            np=SimpleNamespace(asarray=helper("asarray", _ASARRAY)),
            tuple=builtins.tuple,
        ),
        _FROM.__name__,
        _FROM.__defaults__,
        _FROM.__closure__,
    )

    def convert(*a, **k):
        # The literal helper may enter guarded asarray, so it is not itself
        # marked helper_busy. Its source call/locals are independently logged.
        if not context.active or not context.depth:
            raise MappingRejected(
                "Conversion outside mapping lease", stage="source_call_unavailable"
            )
        _check(context)
        return context.from_iterable(*a, **k)

    namespace = dict(
        nparray=SimpleNamespace(from_iterable=convert),
        interp=SimpleNamespace(griddata=helper("griddata", _GRIDDATA)),
    )
    context.methods = {
        name: FunctionType(
            fn.__code__,
            dict(
                fn.__globals__,
                **namespace,
                len=builtins.len,
                BetseSequenceException=source.BetseSequenceException,
            ),
            fn.__name__,
            fn.__defaults__,
            fn.__closure__,
        )
        for name, fn in _NATIVE.items()
    }
    context.namespace_bindings = _namespace_bindings(context)


@contextmanager
def _account(context):
    with world._account(context.work_context):
        previous, trace = sys.getprofile(), sys.gettrace()
        codes = {fn.__code__ for fn in (*_NATIVE.values(), _FROM, _SEQUENCE)}

        def profile(frame, event, arg):
            # Keep original attempted-entry accounting and ledger limits.
            # Entry rejections still propagate before the body executes.
            if frame.f_code in codes and event == "call":
                if len(context.work) >= 100000:
                    raise ValueError("Mapping work ledger exhausted")
                context.work.append(
                    dict(
                        sequence=len(context.work),
                        layer="literal_source_body",
                        method=frame.f_code.co_qualname,
                        status="entered_not_success_credit",
                    )
                )
            if event in ("call", "c_call"):
                _deliver_prior_profile(context, previous, frame, event, arg)
            if frame.f_code in codes and event == "return":
                try:
                    context.locals[(frame.f_code.co_filename, frame.f_code.co_qualname)] = dict(
                        frame.f_locals
                    )
                except Exception as capture:
                    geometry._remember_observation_error(
                        context, capture, origin="raw_locals", raw=frame
                    )
            if event not in ("call", "c_call"):
                _deliver_prior_profile(context, previous, frame, event, arg)

        sys.setprofile(profile)
        try:
            yield
            _stop(context)
        finally:
            sys.setprofile(previous)
            sys.settrace(trace)


def _deliver_prior_profile(context, previous, frame, event, arg):
    if previous is None:
        return
    if event in ("call", "c_call"):
        previous(frame, event, arg)
        return
    try:
        previous(frame, event, arg)
    except Exception as capture:
        geometry._remember_observation_error(
            context,
            capture,
            origin="inherited_profile_" + event,
            raw=(frame, event, arg),
        )


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        parent=trial.parent_identity,
        before=trial.before.identity,
        after=trial.after.identity,
        results=[(name, cache.identity) for name, cache in trial.results],
        events=trial.events,
        work=trial.work,
        warnings=trial.warnings,
        source_completed=trial.source_completed,
        failure_stage=trial.failure_stage,
        invalidated_owners=INVALIDATED_OWNERS,
        physical_field_phase_admitted=False,
    )


class MappingOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use actual caller probe execution")

    def __reduce_ex__(self, protocol):
        raise TypeError("Read-only live mapping authority cannot be serialized")

    @property
    def results(self):
        return tuple(_validate(self).results.items())

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not MappingOwner or owner not in _ISSUED:
        raise MappingRejected("Issued mapping owner required", stage="mapping_owner")
    return _ISSUED[owner]


def _authorize_lease(caller, token, check, invoke):
    context = _LEASE_REQUESTS.get(caller)
    if (
        context is None
        or context.caller is not caller
        or context.token is not token
        or context.check is not check
        or context.invoke is not invoke
        or context.active
        or context.invalid
        or context.thread != get_ident()
        or not hasattr(context, "before")
        or type(context.request) is not Request
        or world._authority(context.request.world_owner) is not context.parent
    ):
        raise MappingRejected(
            "Issued world mapping request required for lease", stage="mapping_lease_issuer"
        )


def _validate(owner):
    context = _authority(owner)
    try:
        if context.invalid or context.active or context.owner is not owner:
            raise ValueError("Invalid mapping source epoch")
        _check(context)
        if world._snapshot(context.parent).identity != context.trial.before.identity:
            raise ValueError("Caller geometry/operators/masks changed")
        if core.records._digest(trial_record(context.trial)) != context.trial.identity:
            raise ValueError("Mapping trial identity changed")
        for name, result in context.results.items():
            if core.caches.snapshot(result).identity != dict(context.trial.results)[name].identity:
                raise ValueError("Mapping output changed")
        geometry.meshes._same_graphs(
            (multi.callers._graph(context.output_view, context.output_view, context.tape),),
            (context.output_graph,),
        )
    except Exception as error:
        context.invalid = True
        raise MappingRejected(
            "Stale mapping result refused",
            stage="mapping_drift",
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def prepare(request):
    if type(request) is not Request:
        raise MappingRejected("Typed mapping request required", stage="request", request=request)
    try:
        parent = world._authority(request.world_owner)
        caller = world._prefix(parent).caller
    except Exception as error:
        raise MappingRejected(
            "Actual world mapping authority unavailable",
            stage="preflight",
            request=request,
            trial=None,
            partial=dict(world_owner=request.world_owner, usable_child_available=False),
            source_error=error,
        ) from error
    context = SimpleNamespace(
        request=request,
        parent=parent,
        parent_trial=parent.trial,
        caller=caller,
        token=object(),
        thread=get_ident(),
        active=False,
        invalid=False,
        depth=0,
        method=None,
        helper_busy=False,
        events=[],
        helpers=[],
        locals={},
        results={},
        result_caches=[],
        work=[],
        stage="preflight",
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
    )
    context.work_context = SimpleNamespace(stage="mapping_probes", work=context.work)
    context.view = SimpleNamespace(
        inputs=tuple((p.data, p.target_points, p.data_factor) for p in request.probes)
    )
    context.tape = SimpleNamespace(rng=None, events=(), draws=(), locals={})
    error = None
    with _LOCK, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            if caller in _LEASE_REQUESTS:
                raise MappingRejected(
                    "Mapping request already active on caller", stage="mapping_reentry"
                )
            if (
                world._validate(request.world_owner) is not parent
                or core.records._digest(_request_record(request)) != request.identity
            ):
                raise ValueError("Changed mapping request/parent")
            context.producers, context.bindings = _verify_sources(), _bindings()
            context.input_cache = _snapshot_inputs(context)
            context.input_graph = _graphs(context)
            context.before = world._snapshot(parent)
            _namespace(context)
            context.check = lambda: _check(context)
            context.invoke = lambda name, actual, *a, **k: _invoke(context, name, actual, *a, **k)
            _LEASE_REQUESTS[caller] = context
            with multi._mapping_read_lease(
                caller, token=context.token, check=context.check, invoke=context.invoke
            ):
                context.active = True
                try:
                    with _account(context):
                        for probe in request.probes:
                            _stop(context)
                            context.stage = context.work_context.stage = probe.name
                            if probe.method == "grids":
                                value = caller.map_cells_centre_to_grids_centre(
                                    probe.data, interp_method=probe.interp_method
                                )
                            else:
                                value = caller.map_cells_centre_to_points(
                                    probe.data,
                                    probe.target_points,
                                    interp_method=probe.interp_method,
                                    data_factor=probe.data_factor,
                                )
                            context.last_probe_result = (probe.name, value)
                            try:
                                context.results[probe.name] = value
                                context.result_caches.append(
                                    (probe.name, core.caches.snapshot(value))
                                )
                            except Exception as capture:
                                geometry._remember_observation_error(
                                    context, capture, origin="result_capture", raw=value
                                )
                                raise world.poisson.environment._CaptureStop() from capture
                            _check(context)
                finally:
                    context.active = False
            context.stage = "final_checks"
            _check(context)
        except Exception as failure:
            if not isinstance(failure, world.poisson.environment._CaptureStop):
                error = failure
        finally:
            context.active = False
            if _LEASE_REQUESTS.get(caller) is context:
                _LEASE_REQUESTS.pop(caller)
    partial = dict(
        context=context,
        parent=parent,
        parent_trial=context.parent_trial,
        caller=caller,
        probes=request.probes,
        results=context.results,
        helpers=context.helpers,
        events=context.events,
        work=context.work,
        raw_locals=context.locals,
        observation_errors=context.observation_errors,
        observation_origin=context.observation_origin,
        observation_raw=context.observation_raw,
        last_completed=getattr(context, "last_completed", None),
        last_probe_result=getattr(context, "last_probe_result", None),
        read_only_lease_released=caller not in multi._READ_LEASES,
        usable_child_available=False,
    )
    if context.observation_error is not None:
        raise MappingRejected(
            "Mapping observation failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=context.observation_error,
        ) from (error if error is not None else context.observation_error)
    if not hasattr(context, "before"):
        raise MappingRejected(
            "Mapping refused before baseline",
            stage=context.stage,
            request=request,
            trial=None,
            partial=partial,
            source_error=error,
        ) from error
    try:
        after = world._snapshot(parent)
        if after.identity != context.before.identity:
            raise ValueError("Read-only mapping changed caller geometry/operators/masks")
        trial = Trial(
            request.identity,
            parent.trial.identity,
            context.before,
            after,
            tuple(context.result_caches),
            tuple(name for name, _ in context.events),
            tuple(context.work),
            tuple(str(w.message) for w in caught),
            error is None,
            None if error is None else context.stage,
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise MappingRejected(
            "Mapping trial sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error if error is not None else capture)
    if error is not None:
        raise MappingRejected(
            "Native mapping source failed",
            stage=context.stage,
            request=request,
            trial=trial,
            partial=partial,
            source_error=error,
        ) from error
    try:
        context.trial = trial
        context.owner = object.__new__(MappingOwner)
        _check(context)
        context.output_view = SimpleNamespace(results=context.results, helpers=context.helpers)
        context.output_graph = multi.callers._graph(
            context.output_view, context.output_view, context.tape
        )
        _ISSUED[context.owner] = context
        return context.owner
    except Exception as capture:
        raise MappingRejected(
            "Mapping child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture
