"""Actual native Simulator construction after a retained tissue prelude.

This owns the original, empty Simulator constructor and its live result. It
does not supply a SimPhase, full Parameters/path/time authority, initialized
material, or an INIT parent. Imports and constructor calls require release.
The parameter and handler links are retained Cells ancestry: the native
no-argument constructor assigns neither p nor dyna to its empty instance.
"""

import ast
import builtins
import dis
import hashlib
import importlib
import os
import struct
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_tissue_configuration as tissue

LAW_ID = "betse_retained_tissue_native_simulator_constructor@1"
RELEASE = "CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED"
MAX_WORK = 10000
SIM_FILE = "betse/science/sim.py"
PHASE_FILE = "betse/science/phase/phasecls.py"
UPSTREAM_PINS = {
    "betse_native_tissue_configuration": (
        "e9f8c93b7bfe856532f68f7406c07e5666b2ebb60d8e71c19a69bb765d4bb99e"
    ),
    "betse_native_tissue_configuration_source": (
        "dc31809ca02a4a9de222da33d58bce1684db0f13f75fa128a288e9cba8dd45ae"
    ),
    "betse_native_single_cell_grid_alias": (
        "bc450958317ab611400f46d26b7c6a242b0ac96bf4c801af4ff99a2f2b7f9e50"
    ),
}
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_LOCK, _ACTIVE = RLock(), []


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    parent: tissue.TissueConfigurationOwner
    parent_trial_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live construction requests cannot be serialized or restored")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    cache: object
    work: tuple
    observations: tuple
    constructor_completed: bool
    failure_stage: str | None
    identity: str


class ConstructionRejected(ValueError):
    def __init__(
        self,
        reason,
        *,
        stage,
        request=None,
        trial=None,
        partial=None,
        source_error=None,
        capture_errors=(),
    ):
        super().__init__(reason)
        self.stage, self.request, self.trial = stage, request, trial
        self.partial, self.source_error = partial, source_error
        self.capture_errors = tuple(capture_errors)


def _class(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)


def _method(cls, name):
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)


def source_plan():
    """Read/compile source metadata only; never import native code or call it."""
    dependencies = {}
    for module in (tissue, tissue.source, tissue.aliases):
        name = module.__name__.rsplit(".", 1)[-1]
        actual = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        if actual != UPSTREAM_PINS[name]:
            raise ValueError("Retained tissue constructor dependency changed: " + name)
        dependencies[name] = actual
    pins = {}
    for name, expected in tissue.source.SOURCE_PINS.items():
        path = tissue.aliases.NATIVE / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("Pinned Simulator prerequisite source changed: " + name)
        pins[name] = actual
    sim = _class(ast.parse((tissue.aliases.NATIVE / SIM_FILE).read_bytes()), "Simulator")
    constructor = _method(sim, "__init__")
    header = ast.FunctionDef(
        name=constructor.name,
        args=constructor.args,
        body=[ast.Pass()],
        decorator_list=constructor.decorator_list,
        returns=constructor.returns,
        type_comment=constructor.type_comment,
        type_params=constructor.type_params,
    )
    expected = ast.parse("def __init__(self) -> None: pass").body[0]
    if ast.dump(header) != ast.dump(expected):
        raise ValueError("Native Simulator constructor header/decorators changed")
    body = constructor.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and type(body[0].value.value) is str
    ):
        body = body[1:]
    if len(body) != 1 or not isinstance(body[0], ast.Pass):
        raise ValueError("Native Simulator constructor is no longer the empty source body")
    phase = _class(ast.parse((tissue.aliases.NATIVE / PHASE_FILE).read_bytes()), "SimPhase")
    return dict(
        law=LAW_ID,
        native_pins=pins,
        dependencies=dependencies,
        simulator_constructor_lines=(constructor.lineno, constructor.end_lineno),
        simulator_constructor_ast=hashlib.sha256(ast.dump(constructor).encode()).hexdigest(),
        phase_constructor_lines=(
            _method(phase, "__init__").lineno,
            _method(phase, "__init__").end_lineno,
        ),
        parameter_authority="retained selected tissue projection, not full Parameters/YAML",
        phase_prerequisites=(
            "actual default callbacks and application-metadata/testing authority",
            "fresh Cells constructed from this exact parameter instance",
            "native phase/cache/tissue construction in original caller order",
            "genuine parameter path and INIT time descriptor/load authority",
            "Simulator.init_core ion/material ownership before tissue profile writes",
        ),
        phase_or_INIT_or_physical_or_checkpoint_admitted=False,
    )


def request_record(request):
    return dict(
        law=LAW_ID,
        parent_trial_identity=request.parent_trial_identity,
        same_live_parameter_and_tissue_owner=True,
        parameter_projection="selected tissue configuration",
        full_Parameters_or_phase_authority=False,
    )


def from_tissue(parent, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise ConstructionRejected(
            "Explicit Simulator constructor source law required", stage="request_law"
        )
    context = tissue._validate(parent)
    if context.trial.source_completed is not True:
        raise ConstructionRejected(
            "Completed actual tissue constructor owner required", stage="parent_completion"
        )
    value = Request(parent, context.trial.identity, "")
    value = replace(value, identity=tissue.core.records._digest(request_record(value)))
    _REQUESTS[value] = (context, context.p, context.handler, context.trial)
    return value


def _parent(request):
    if type(request) is not Request or request not in _REQUESTS:
        raise ConstructionRejected(
            "Issued live typed constructor request required", stage="request_owner", request=request
        )
    retained = _REQUESTS[request]
    context = tissue._validate(request.parent)
    if (
        context is not retained[0]
        or context.p is not retained[1]
        or context.handler is not retained[2]
        or context.trial is not retained[3]
        or context.trial.source_completed is not True
        or context.trial.identity != request.parent_trial_identity
        or tissue.core.records._digest(request_record(request)) != request.identity
    ):
        raise ConstructionRejected(
            "Original tissue/parameter/request association changed",
            stage="parent_association",
            request=request,
        )
    return context


def _constant(value):
    if type(value) is CodeType:
        return (CodeType, _code(value))
    if type(value) is float:
        return (float, struct.pack(">d", value))
    if type(value) is complex:
        return (complex, struct.pack(">dd", value.real, value.imag))
    if type(value) is tuple:
        return (tuple, tuple(_constant(v) for v in value))
    if value is None or type(value) in (str, bytes, int, bool):
        return (type(value), value)
    raise ValueError("Unsupported constructor executable constant")


def _code(code):
    return (
        code.co_code,
        code.co_exceptiontable,
        code.co_stacksize,
        code.co_argcount,
        code.co_posonlyargcount,
        code.co_kwonlyargcount,
        code.co_nlocals,
        code.co_flags,
        code.co_varnames,
        code.co_names,
        code.co_freevars,
        code.co_cellvars,
        tuple(_constant(c) for c in code.co_consts),
    )


def _chain(function):
    chain, seen = [], set()
    while True:
        if type(function) is not FunctionType or id(function) in seen or len(chain) >= 8:
            raise ValueError("Unsupported native constructor wrapper ownership")
        seen.add(id(function))
        chain.append(function)
        if not hasattr(function, "__wrapped__"):
            return tuple(chain)
        function = function.__wrapped__


def _canonical(module):
    """Require the actual issued module/class; never build a replacement class."""
    tissue.aliases._check_modules()
    if (
        sys.modules.get("betse.science.sim") is not module
        or Path(module.__file__).resolve() != tissue.aliases.NATIVE / SIM_FILE
        or module.Simulator.__module__ != module.__name__
        or module.Simulator.__bases__ != (object,)
        or type(module.Simulator) is not type
    ):
        raise ValueError("Canonical original Simulator module/class required")
    chain = _chain(module.Simulator.__init__)
    original = chain[-1]
    node = _method(
        _class(ast.parse((tissue.aliases.NATIVE / SIM_FILE).read_bytes()), "Simulator"), "__init__"
    )
    # Compile the original definition without executing even its module body.
    unit = compile(
        ast.Module(body=[node], type_ignores=[]),
        str(tissue.aliases.NATIVE / SIM_FILE),
        "exec",
        dont_inherit=True,
    )
    expected = next(c for c in unit.co_consts if type(c) is CodeType)
    if (
        original.__globals__ is not vars(module)
        or original.__code__.co_filename != str(tissue.aliases.NATIVE / SIM_FILE)
        or _code(original.__code__) != _code(expected)
    ):
        raise ValueError("Native original constructor executable correspondence changed")
    for function in chain:
        namespace = function.__globals__.get("__builtins__")
        namespace = vars(namespace) if type(namespace) is type(builtins) else namespace
        if namespace is not function.__builtins__ or namespace is not vars(builtins):
            raise ValueError("Native constructor cached builtins association changed")
    return module.Simulator


def _acquire_native():
    with tissue.aliases.issuing_native_imports(tissue.source.SOURCE_PINS):
        module = importlib.import_module("betse.science.sim")
    _canonical(module)
    return module


def _runtime(module):
    cls = _canonical(module)
    objects = [module, vars(module), cls, cls.__bases__, cls.__mro__]
    labels = []
    for name, value in vars(cls).items():
        labels.append(name)
        objects.append(value)
    for function in _chain(cls.__init__):
        objects.extend(
            (
                function,
                function.__code__,
                function.__globals__,
                function.__builtins__,
                function.__defaults__,
                function.__kwdefaults__,
                function.__annotations__,
            )
        )
        for cell in function.__closure__ or ():
            objects.extend((cell, cell.cell_contents))
        for name, value in (
            ("defaults", function.__defaults__),
            ("keyword_defaults", function.__kwdefaults__),
            ("annotations", function.__annotations__),
        ):
            labels.append((name, type(value).__name__))
            if value is None:
                continue
            pairs = value.items() if type(value) is dict else enumerate(value)
            for key, item in pairs:
                if type(key) not in (str, int):
                    raise ValueError("Unsupported constructor binding key")
                if type(item) in (dict, list, set, bytearray):
                    raise ValueError("Unsupported mutable constructor binding value")
                labels.append((name, key))
                objects.extend(tissue.aliases._atoms(item))
        for instruction in dis.get_instructions(function):
            if instruction.opname == "LOAD_GLOBAL":
                name = instruction.argval
                local = name in function.__globals__
                labels.append((name, local))
                objects.append(function.__globals__[name] if local else function.__builtins__[name])
    return tuple(labels), tuple(objects)


def _same(actual, retained):
    if (
        actual[0] != retained[0]
        or len(actual[1]) != len(retained[1])
        or any(a is not b for a, b in zip(actual[1], retained[1], strict=True))
    ):
        raise ValueError("Native Simulator class/callback/runtime reference changed")


def _copy_locals(frame):
    return dict(frame.f_locals)


@contextmanager
def _observe(context):
    previous, trace = sys.getprofile(), sys.gettrace()

    def profile(frame, event, arg):
        reached = (
            frame.f_code.co_filename.startswith(str(tissue.aliases.NATIVE) + "/")
            or frame.f_code in context.constructor_codes
        )
        if reached and event == "call":
            if len(context.work) >= MAX_WORK:
                raise ValueError("Bounded native constructor work ledger exhausted")
            context.work.append(
                dict(
                    sequence=len(context.work),
                    stage=context.stage,
                    method=frame.f_code.co_qualname,
                    source_file=frame.f_code.co_filename,
                    constructor_body=frame.f_code in context.constructor_codes,
                )
            )
        if frame.f_code in context.constructor_codes and event in ("call", "return"):
            try:
                raw = _copy_locals(frame)
                context.raw_locals.append((event, raw))
                if "self" in raw:
                    context.partial_instance = raw["self"]
                context.observations.append(
                    dict(
                        event=event,
                        classification="entry" if event == "call" else "return_or_unwind",
                        method=frame.f_code.co_qualname,
                    )
                )
            except BaseException as error:
                context.capture_errors.append(("constructor_locals", error))
        if previous is not None:
            if event in {"return", "c_return", "c_exception"}:
                try:
                    previous(frame, event, arg)
                except BaseException as error:
                    # CPython emits return(None) for both a normal return
                    # and an exception unwind. A failing inherited observer
                    # must not replace the source exception already unwinding.
                    label = "inherited_profile_" + context.stage + "_" + event
                    context.capture_errors.append((label, error))
                    try:
                        context.raw_locals.append((label, _copy_locals(frame)))
                    except BaseException as capture:
                        context.capture_errors.append((label + "_locals", capture))
            else:
                # Entry guards still reject before the native body runs.
                previous(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)


def _snapshot(context):
    return tissue.core.caches.snapshot(
        dict(
            parent_trial_identity=context.request.parent_trial_identity,
            parent_configuration_identity=context.parent.trial.cache.identity,
            simulator_fields=vars(context.instance),
            same_actual_parameter=True,
            same_actual_tissue_handler=True,
            constructor_completed=context.completed,
        )
    )


def _graph(context):
    return tissue.callers._graph(context.view, context.p, context.tape)


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        cache=trial.cache.identity,
        work=trial.work,
        observations=trial.observations,
        constructor_completed=trial.constructor_completed,
        failure_stage=trial.failure_stage,
        phase_or_INIT_admitted=False,
    )


class SimulatorOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use released native Simulator construction")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live Simulator authority cannot be serialized or restored")

    @property
    def simulator(self):
        return _validate(self).instance

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def tissue_handler(self):
        return _validate(self).handler

    @property
    def trial(self):
        return _validate(self).trial


def _check(context):
    if (
        context.invalid
        or context.thread != get_ident()
        or _CONSUMED.get(context.request) is not context
        or _CLAIMED.get(context.request.parent) is not context
    ):
        raise ValueError("Native constructor occurrence/lineage changed")
    if _parent(context.request) is not context.parent:
        raise ValueError("Actual retained tissue context changed")
    if source_plan() != context.plan:
        raise ValueError("Native constructor producer changed")
    _same(_bindings(), context.bindings)
    _same(_runtime(context.module), context.runtime)
    if (
        type(context.instance) is not context.module.Simulator
        or vars(context.instance)
        or context.partial_instance is not context.instance
    ):
        raise ValueError("Original empty Simulator result/allocated instance changed")


def _validate(owner):
    if type(owner) is not SimulatorOwner or owner not in _ISSUED:
        raise ConstructionRejected("Issued actual Simulator owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active or replaced Simulator owner")
        _check(context)
        if context.trial.cache.identity != _snapshot(
            context
        ).identity or context.trial.identity != tissue.core.records._digest(
            trial_record(context.trial)
        ):
            raise ValueError("Retained Simulator constructor trial changed")
        _same_graph(_graph(context), context.graph)
    except BaseException as error:
        context.invalid = True
        raise ConstructionRejected(
            "Stale Simulator owner refused",
            stage="owner_drift",
            request=context.request,
            trial=context.trial,
            partial=context,
            source_error=error,
        ) from error
    return context


def _same_graph(actual, retained):
    if (
        len(actual[0]) != len(retained[0])
        or actual[1] != retained[1]
        or any(a is not b for a, b in zip(actual[0], retained[0], strict=True))
    ):
        raise ValueError("Simulator/parameter/tissue alias graph changed")


def _bindings():
    functions = (
        source_plan,
        request_record,
        from_tissue,
        _parent,
        _constant,
        _code,
        _chain,
        _canonical,
        _acquire_native,
        _runtime,
        _same,
        _copy_locals,
        _observe,
        _observe.__wrapped__,
        _snapshot,
        _graph,
        trial_record,
        _check,
        _validate,
        _same_graph,
        _bindings,
        prepare,
        require_phase,
        tissue._validate,
        tissue.core.caches.snapshot,
        tissue.aliases.issuing_native_imports,
        tissue.aliases._check_modules,
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
            *(atom for function in functions for atom in tissue.aliases._atoms(function)),
        ),
    )


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise ConstructionRejected(
            "Actual Simulator construction remains held", stage="release", request=request
        )
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise ConstructionRejected(
                "Reentrant native Simulator construction refused",
                stage="reentrant",
                request=request,
            )
        if type(request) is not Request or request not in _REQUESTS:
            raise ConstructionRejected(
                "Issued live typed constructor request required",
                stage="request_owner",
                request=request,
            )
        if request in _CONSUMED or request.parent in _CLAIMED:
            raise ConstructionRejected(
                "Actual constructor attempt already consumed", stage="consumed", request=request
            )
        context = SimpleNamespace(
            request=request,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="parent",
            work=[],
            observations=[],
            raw_locals=[],
            capture_errors=[],
            constructor_codes=(),
            partial_instance=None,
            import_completed=False,
            completed=False,
        )
        _CONSUMED[request] = _CLAIMED[request.parent] = context
        _ACTIVE.append(context)
        error = None
        try:
            context.parent = _parent(request)
            context.p, context.handler = context.parent.p, context.parent.handler
            context.plan = source_plan()
            context.bindings = _bindings()
            context.stage = "native_import"
            with _observe(context):
                context.module = _acquire_native()
            context.import_completed = True
            if context.capture_errors:
                context.stage = "import_capture"
            else:
                context.runtime = _runtime(context.module)
                context.constructor_codes = tuple(
                    f.__code__ for f in _chain(context.module.Simulator.__init__)
                )
                context.stage = "simulator_constructor"
                with _observe(context):
                    context.instance = context.module.Simulator()
                context.completed = True
                if not context.capture_errors:
                    context.stage = "constructor_association"
                    _check(context)
                else:
                    context.stage = "constructor_capture"
        except BaseException as primary:
            error = primary
        try:
            if error is None and not context.capture_errors:
                context.stage = "constructor_capture"
                cache = _snapshot(context)
                trial = Trial(
                    request.identity,
                    cache,
                    tuple(context.work),
                    tuple(context.observations),
                    True,
                    None,
                    "",
                )
                context.trial = replace(
                    trial, identity=tissue.core.records._digest(trial_record(trial))
                )
                context.view = SimpleNamespace(
                    parameter_owner=request.parent,
                    parameters=context.p,
                    tissue_handler=context.handler,
                    simulator=context.instance,
                    fields=(vars(context.p), vars(context.handler), vars(context.instance)),
                )
                context.tape = SimpleNamespace(rng=None, events=context.work, draws=(), locals={})
                context.graph = _graph(context)
                _check(context)
                owner = object.__new__(SimulatorOwner)
                context.owner = owner
                _ISSUED[owner] = context
                return owner
        except BaseException as capture:
            context.capture_errors.append((context.stage, capture))
        finally:
            context.active = False
            _ACTIVE.pop()
        context.invalid = True
        refusal = ConstructionRejected(
            "Actual Simulator construction did not issue an owner",
            stage=context.stage,
            request=request,
            partial=context,
            source_error=error,
            capture_errors=context.capture_errors,
        )
        raise refusal from (error if error is not None else context.capture_errors[0][1])


def require_phase(owner, *, supplied_phase=None):
    """A constructor owner never becomes INIT authority through a supplied phase."""
    context = _validate(owner)
    raise ConstructionRejected(
        "Genuine native phase and complete parameter/caller authority unavailable",
        stage="phase_prerequisites",
        request=context.request,
        trial=context.trial,
        partial=dict(
            missing=context.plan["phase_prerequisites"],
            supplied_phase_refused=supplied_phase is not None,
            full_Parameters_or_INIT_or_checkpoint_admitted=False,
        ),
    )
