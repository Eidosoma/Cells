"""Fresh same-parameter INIT/SIM constructor timing, separately held.

The claim consumes an actual complete WorldReady owner before phase birth. It
shares the existing irreversible reservation and exclusion machinery with SEED
construction. It neither promotes a SEED phase nor issues Cells, Simulator,
callback, material, INIT-completion or checkpoint authority. A consumer must
authenticate its actual optional live inputs separately.

Only the original loaded native SimPhase constructor and its two original
helpers can witness the permitted parameter stores. No callable, phase,
namespace, timing dictionary or serialized receipt is accepted as authority.
"""

import ast
import builtins
import dis
import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock, get_ident
from types import FunctionType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_phase_construction_source as literal
from cells.processes import betse_native_parameter_world_construction as shared
from cells.processes import betse_native_phase_callbacks as callbacks

parameters, claims, prefix = shared.parameters, shared.claims, shared.prefix
PHASE_CONSTRUCTION_LAW = "betse_fresh_world_ready_init_sim_constructor_parameters@1"
RELEASE = "CELLS_NATIVE_PARAMETER_PHASE_CONSTRUCTION_RELEASED"
NATIVE = Path(callbacks.simulator.tissue.aliases.NATIVE)
PHASE = "betse/science/phase/phasecls.py"
PHASE_SHA256 = "e7c129aca1930fcb31884f32d4f2ebbb46d31113a66887a39c85ba0009b78ea8"
ENUM_SHA256 = "7ae73b8e56e6323d9e9d4c9519f9cf6cfcee46e1d75b6949b94c88045ba667d6"
METHODS = ("__init__", "_init_kludge", "_init_kludge_time")
STORES = ("_run_sim", "dt", "resample", "total_time", "t_resample")
TIMING_INPUTS = {
    "INIT": ("init_time_step", "init_time_sampling", "init_time_total"),
    "SIM": ("sim_time_step", "sim_time_sampling", "sim_time_total"),
}
PHASE_FIELDS = ("callbacks", "cells", "kind", "p", "sim", "cache", "dyna", "export_dirname")
MAX_SOURCE_CALLS = 100000
MAX_CAPTURE_ERRORS = 64
_LOCK, _ACTIVE, _FAILED = Lock(), [], []
_ISSUED = WeakKeyDictionary()
_PROOFS = tuple(getattr(literal.PhaseParameterTail, name) for name in METHODS[1:])
_ORIGINAL_BUILTINS = vars(builtins)


class PhaseConstructionRejected(ValueError):
    def __init__(self, reason, *, stage, claim=None, partial=None, capture_errors=()):
        super().__init__(reason)
        self.stage, self.phase_construction_claim, self.partial = stage, claim, partial
        self.capture_errors = tuple(capture_errors)


@dataclass(frozen=True, slots=True)
class PhaseParameterRecord:
    law: str
    source_identity: str | None
    parameter_load_identity: str
    kind: str | None
    phase_bindings: tuple
    before_identity: str
    after_identity: str | None
    work: tuple
    actual_source_calls: tuple
    stores: tuple
    constructor_completed: bool
    succeeded: bool
    primary_error_present: bool
    secondary_error_stages: tuple
    identity: str


class PhaseConstructionClaim:
    """One active construction; a record alone grants no phase authority."""

    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use construction with an actual fresh WorldReady owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live phase-parameter claims cannot be reconstructed")

    @property
    def parameters(self):
        _reused()
        context = _checked(self)
        _reused()
        return context.p

    def check(self):
        _reused()
        _checked(self)
        _reused()

    @property
    def record(self):
        context = _context(self)
        if context.active:
            raise PhaseConstructionRejected("No record before closure", stage="active", claim=self)
        if context.record is None:
            raise PhaseConstructionRejected(
                "Reservation failed before a closure record was available",
                stage="record_unavailable",
                claim=self,
                partial=context,
            )
        if (
            context.record is not context.original_record
            or _digest(record_document(context.record)) != context.record.identity
            or (context.record.succeeded and (context.invalid or context.capture_errors))
        ):
            raise PhaseConstructionRejected("Closed record changed", stage="record", claim=self)
        return context.record


def _digest(value):
    return parameters._digest(value)


def _nodes():
    path = NATIVE / PHASE
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != PHASE_SHA256:
        raise ValueError("Exact original phase source required")
    cls = callbacks.simulator._class(ast.parse(path.read_bytes()), "SimPhase")
    nodes = {name: callbacks.simulator._method(cls, name) for name in METHODS}
    proof = ast.parse(Path(literal.__file__).read_bytes())
    proof_cls = callbacks.simulator._class(proof, "PhaseParameterTail")
    for name in METHODS[1:]:
        actual = callbacks.simulator._method(proof_cls, name)
        if ast.dump(ast.Module(body=nodes[name].body, type_ignores=[])) != ast.dump(
            ast.Module(body=actual.body, type_ignores=[])
        ):
            raise ValueError("Complete original phase timing body changed: " + name)
    return nodes


def source_plan():
    nodes = _nodes()
    return dict(
        law=PHASE_CONSTRUCTION_LAW,
        native_phase=dict(path=str(NATIVE / PHASE), sha256=PHASE_SHA256),
        enum_source_sha256=ENUM_SHA256,
        literal_sha256=hashlib.sha256(Path(literal.__file__).read_bytes()).hexdigest(),
        methods={name: (node.lineno, node.end_lineno) for name, node in nodes.items()},
        shared_producer=hashlib.sha256(Path(shared.__file__).read_bytes()).hexdigest(),
        parameter_producer=hashlib.sha256(Path(parameters.__file__).read_bytes()).hexdigest(),
        parameters=parameters.source_plan(),
        shared_reservation_code_unchanged=_RESERVE.__code__ is shared._reserve.__code__,
        shared_history_code_unchanged=_HISTORY.__code__ is shared._source.__code__,
        kinds=("actual original SimPhaseKind.INIT", "actual original SimPhaseKind.SIM"),
        stores=STORES,
        timing_inputs=TIMING_INPUTS,
        max_source_call_entries=MAX_SOURCE_CALLS,
        source_work_scope=(
            "Actual native and retained wrapper call-entry events, including refused attempts; "
            "partial counts are explicitly incomplete after observation failure"
        ),
        mode="fresh WorldReady before native phase allocation; no earlier construction attempt",
        actual_ratio=(
            "Original native resample / dt result, observed and retained, never recomputed"
        ),
        optional_inputs=(
            "Retain original constructor cells/sim/callback arguments and exact return aliases; "
            "consumer must authenticate their actual owner/source authority independently"
        ),
        SEED_and_Seven_d9_47_interfaces_changed=False,
        native_phase_or_material_or_INIT_completion_admitted=False,
        native_execution_held=True,
    )


def record_document(value):
    return dict(
        law=value.law,
        source=value.source_identity,
        parameter_load=value.parameter_load_identity,
        kind=value.kind,
        actual_reference_bindings=value.phase_bindings,
        before=value.before_identity,
        after=value.after_identity,
        metadata_work=value.work,
        actual_source_calls=value.actual_source_calls,
        stores=value.stores,
        constructor_completed=value.constructor_completed,
        succeeded=value.succeeded,
        primary_error_present=value.primary_error_present,
        secondary_error_stages=value.secondary_error_stages,
        phase_owner_or_material_or_completed_INIT_admitted=False,
        independent_biological_cases=0,
    )


def _context(claim):
    if type(claim) is not PhaseConstructionClaim or claim not in _ISSUED:
        raise PhaseConstructionRejected(
            "Actual issued phase-parameter claim required", stage="claim"
        )
    context = _ISSUED[claim]
    if context.claim is not claim:
        raise PhaseConstructionRejected("Replaced claim edge", stage="claim", claim=claim)
    return context


def failed_context(claim):
    """Actual retained failed context only; no permission to retry or read p."""
    context = _context(claim)
    if context.active or not (context.invalid or context.source_error or context.capture_errors):
        raise PhaseConstructionRejected("Closed failed claim required", stage="failed", claim=claim)
    return context


def _native():
    # This is lazy and performs no native import, factory or source evaluation.
    _nodes()
    module = sys.modules.get("betse.science.phase.phasecls")
    enum_module = sys.modules.get("betse.science.enum.enumphase")
    if type(module) is not ModuleType or type(enum_module) is not ModuleType:
        raise PhaseConstructionRejected(
            "Actual original loaded phase/enum runtime prerequisite missing", stage="native_runtime"
        )
    for item, name in ((module, PHASE), (enum_module, "betse/science/enum/enumphase.py")):
        if Path(item.__file__).resolve() != NATIVE / name:
            raise ValueError("Foreign native phase/enum module")
    if (
        hashlib.sha256((NATIVE / "betse/science/enum/enumphase.py").read_bytes()).hexdigest()
        != ENUM_SHA256
    ):
        raise ValueError("Original phase-kind source changed")
    cls = vars(module)["SimPhase"]
    enum = vars(enum_module)["SimPhaseKind"]
    if (
        type(cls) is not type
        or cls.__bases__ != (object,)
        or cls.__new__ is not object.__new__
        or cls.__module__ != module.__name__
    ):
        raise ValueError("Original native phase class required")
    functions = {
        name: callbacks._source_function(vars(cls)[name], PHASE, name, "SimPhase")
        for name in METHODS
    }
    chains = {name: callbacks.simulator._chain(vars(cls)[name]) for name in METHODS}
    for chain in chains.values():
        for wrapper, wrapped in zip(chain, chain[1:], strict=False):
            # Beartype's real import-hook wrappers are retained, never replaced
            # by an unwrapped copy. __wrapped__ alone is not their call edge.
            closed = tuple(cell.cell_contents for cell in wrapper.__closure__ or ())
            keywords = tuple((wrapper.__kwdefaults__ or {}).values())
            if not any(value is wrapped for value in (*closed, *keywords)):
                raise ValueError("Native wrapper lacks its retained actual call-target edge")
    if any(function.__globals__.get("SimPhaseKind") is not enum for function in functions.values()):
        raise ValueError("Original phase/enum namespace association changed")
    return SimpleNamespace(
        module=module, enum_module=enum_module, cls=cls, enum=enum, methods=functions, chains=chains
    )


def _native_bindings(native):
    current = _native()
    if (
        current.module is not native.module
        or current.enum_module is not native.enum_module
        or current.cls is not native.cls
        or current.enum is not native.enum
        or any(current.methods[name] is not native.methods[name] for name in METHODS)
    ):
        raise ValueError("Original phase runtime dispatch changed")
    labels, objects = [], [native.module, native.enum_module, native.cls, native.enum]
    for cls in (native.cls, native.enum):
        objects.extend((cls.__bases__, cls.__mro__))
        for name, value in vars(cls).items():
            labels.append(("class", cls.__name__, name))
            objects.append(value)
    for name in METHODS:
        function = native.methods[name]
        chain = callbacks.simulator._chain(vars(native.cls)[name])
        objects.extend(
            atom for fn in chain for atom in prefix.parameters.inherited.tissue.aliases._atoms(fn)
        )
        for fn in chain:
            objects.extend((fn.__globals__, fn.__builtins__, fn.__kwdefaults__))
            for key, value in (fn.__kwdefaults__ or {}).items():
                labels.append((name, "wrapper_keyword", key))
                objects.append(value)
            namespace = fn.__globals__.get("__builtins__")
            namespace = vars(namespace) if type(namespace) is ModuleType else namespace
            if namespace is not fn.__builtins__ or namespace is not _ORIGINAL_BUILTINS:
                raise ValueError("Original cached builtins association changed")
        # Bind the actual reached lookup category as well as the value. A new
        # same-valued global shadow is still a namespace change.
        for instruction in dis.get_instructions(function):
            if instruction.opname == "LOAD_GLOBAL":
                key = instruction.argval
                global_name = key in function.__globals__
                namespace = function.__globals__ if global_name else function.__builtins__
                labels.append((name, key, "global" if global_name else "builtin"))
                objects.append(namespace[key])
    return tuple(labels), tuple(objects)


def _source(context):
    if context.guard is not context.original_guard or context.guard.thread != context.thread:
        raise ValueError("Original phase construction guard/thread association changed")
    _reused()
    _HISTORY(context)
    prefix.parameters.inherited._same(_native_bindings(context.native), context.native_bindings)


def _checked(claim):
    context = _context(claim)
    if context.guard is not context.original_guard:
        context.invalid = context.original_guard.invalid = True
        raise ValueError("Original phase construction guard was replaced")
    return _CHECKED(claim)


def _bytes(context, *, complete):
    fields = vars(context.p)
    names = tuple(fields)
    expected = tuple(name for name, _, _, _ in context.assignments)
    if names != (*context.before_names, *expected):
        context.invalid = context.original_guard.invalid = True
        raise ValueError("Unobserved, removed, reordered or foreign phase parameter store")
    if expected != STORES[: len(expected)]:
        raise ValueError("Original temporal store prefix/order required")
    prefix.parameters.inherited._same_graph(
        parameters._capture(context.source, names=context.before_names), context.before_graph
    )
    parameters.previous._same_cm(parameters._colormaps(context.source), context.before_cm)
    for name, value, _, _ in context.assignments:
        if fields[name] is not value:
            raise ValueError("Observed temporal scalar/array owner was replaced: " + name)
    if expected:
        flag = fields["_run_sim"]
        if type(flag) is not bool or flag is not (context.kind_name == "SIM"):
            raise ValueError("Exact native INIT/SIM flag required")
        for name, origin in zip(STORES[1:4], TIMING_INPUTS[context.kind_name], strict=True):
            if name in fields and fields[name] is not fields[origin]:
                raise ValueError("Original timing input assignment alias changed: " + name)
        prefix.parameters.inherited._same_graph(
            parameters._capture(context.source, names=expected), context.timing_graph
        )
    if complete:
        if expected != STORES or not context.constructor_completed:
            raise ValueError("Complete original constructor/timing source witness required")
        _phase(context)
        for role in METHODS:
            frame = context.frames.get(role)
            if (
                frame is None
                or frame.f_code is not context.native.methods[role].__code__
                or frame.f_globals is not context.native.methods[role].__globals__
                or frame.f_locals.get("self") is not context.phase
            ):
                raise ValueError("Original completed source frame association changed")
            if role != "__init__":
                parent = "__init__" if role == "_init_kludge" else "_init_kludge"
                if _caller(context, role, frame) is not context.frames[parent]:
                    raise ValueError("Original completed helper caller changed")
            elif _caller(context, role, frame) is not context.constructor_caller:
                raise ValueError("Original constructor wrapper/caller changed")
        for name, _, frame, line in context.assignments:
            role = "_init_kludge" if name == "_run_sim" else "_init_kludge_time"
            if (
                frame is not context.frames[role]
                or line != context.store_lines[(context.kind_name, name)]
            ):
                raise ValueError("Original completed store/frame/source line changed")
    return expected


def _phase(context):
    actual = context.phase
    if (
        actual is None
        or type(actual) is not context.native.cls
        or tuple(vars(actual)) != PHASE_FIELDS
        or actual.p is not context.p
        or actual.kind is not context.kind
        or actual.sim.dyna is not actual.dyna
    ):
        raise ValueError("Actual same native phase/parameter/kind/tail association changed")
    for name, value in context.phase_fields:
        if vars(actual)[name] is not value:
            raise ValueError("Original constructor output owner changed: " + name)
    for name, supplied in context.optional_inputs:
        if supplied is not None and vars(actual)[name] is not supplied:
            raise ValueError("Original optional live argument was replaced: " + name)
    export = "init_export_dirname" if context.kind_name == "INIT" else "sim_export_dirname"
    if actual.export_dirname is not vars(context.p)[export]:
        raise ValueError("Original export store alias changed")


def _caller(context, role, frame):
    caller = frame.f_back
    for wrapper in reversed(context.native.chains[role][:-1]):
        if caller is None or caller.f_code is not wrapper.__code__:
            _reject(context, "Actual retained native wrapper call chain required")
        caller = caller.f_back
    return caller


def _capture_error(context, stage, error, witness=None):
    if context.observation_error is None:
        context.observation_error = error
    if len(context.capture_errors) < MAX_CAPTURE_ERRORS:
        context.capture_errors += ((stage, error, witness),)
    else:
        context.raw_error_overflow = True


def _retain_error(context, stage, error, witness=None):
    """Independent bounded roots precede the fallible reporting function."""
    raw = (stage, error, witness)
    context.last_error = raw
    if len(context.raw_errors) < MAX_CAPTURE_ERRORS:
        context.raw_errors += (raw,)
    else:
        context.raw_error_overflow = True
    if context.observation_error is None:
        context.observation_error = error
    try:
        _capture_error(context, stage, error, witness)
    except BaseException as secondary:
        context.last_reporting_error = (stage, secondary, error)
        if len(context.reporting_errors) < MAX_CAPTURE_ERRORS:
            context.reporting_errors += (context.last_reporting_error,)
        else:
            context.raw_error_overflow = True
        context.invalid = context.original_guard.invalid = True


def _reject(context, reason):
    context.invalid = context.original_guard.invalid = True
    if context.entry_error is None:
        context.entry_error = PhaseConstructionRejected(
            reason, stage="source_entry", claim=context.claim, partial=context
        )
    raise context.entry_error


def _source_guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.observation_error is not None:
        _reject(context, "Incomplete observation; further constructor work forbidden")
    _checked(context.claim)
    if context.observing and (
        context.getters[0]() is not context.observers[0]
        or context.getters[1]() is not context.observers[1]
    ):
        _reject(context, "Both actual observation hooks required")


def _stores(context, frame, event):
    # Observe the previous original STORE_ATTR, never evaluate its RHS again.
    names = tuple(vars(context.p))
    known = tuple(name for name, _, _, _ in context.assignments)
    if names != (*context.before_names, *known):
        next_index = len(known)
        if (
            next_index >= len(STORES)
            or names != (*context.before_names, *STORES[: next_index + 1])
            or context.lines.get(id(frame))
            != context.store_lines[(context.kind_name, STORES[next_index])]
        ):
            _reject(context, "Parameter write did not follow its exact original source line")
        name = STORES[next_index]
        context.last_assignment = (name, vars(context.p)[name], frame, context.lines[id(frame)])
        context.assignments.append(context.last_assignment)
        context.timing_graph = parameters._capture(context.source, names=STORES[: next_index + 1])
    _bytes(context, complete=False)
    if event == "line":
        context.lines[id(frame)] = frame.f_lineno


def _observe(context, frame, event, arg):
    code = frame.f_code
    role = context.roles.get(code)
    known = role is not None or code.co_filename.startswith(str(NATIVE) + os.sep)
    if event == "exception" and known:
        context.pending[id(frame)] = arg[1]
    if event == "return" and known:
        context.last_raw = (code.co_qualname, frame, arg)
        if not _normal_return(frame) and context.primary is None:
            context.primary = context.pending.get(id(frame))
        context.raw_returns.append(context.last_raw)
    if role is None:
        return
    if event == "call":
        _source_guard(context)
        if role in context.frames:
            _reject(context, "Duplicate/reentrant original constructor or timing helper")
        if frame.f_globals is not context.native.methods[role].__globals__:
            _reject(context, "Original source namespace required")
        actual = frame.f_locals.get("self")
        if role == "__init__":
            constructor_caller = _caller(context, role, frame)
            if (
                context.phase is not None
                or type(actual) is not context.native.cls
                or vars(actual)
                or frame.f_locals.get("p") is not context.p
                or frame.f_locals.get("kind") is not context.kind
            ):
                _reject(context, "Fresh native phase birth on exact WorldReady p/kind required")
            context.phase = actual
            context.constructor_caller = constructor_caller
            context.optional_inputs = tuple(
                (name, frame.f_locals[name]) for name in ("cells", "sim", "callbacks")
            )
        else:
            parent = "__init__" if role == "_init_kludge" else "_init_kludge"
            if (
                actual is not context.phase
                or _caller(context, role, frame) is not context.frames.get(parent)
                or actual.p is not context.p
                or actual.kind is not context.kind
            ):
                _reject(context, "Exact original constructor/helper parent and phase required")
        context.frames[role] = frame
    if event in ("line", "return"):
        if context.frames.get(role) is not frame or frame.f_locals.get("self") is not context.phase:
            _reject(context, "Original retained source frame/self association changed")
        _stores(context, frame, event)
        _source_guard(context)
        if event == "return" and _normal_return(frame):
            if arg is not None:
                _reject(context, "Original constructor/helper return must be None")
            context.returned.append(role)
            if role == "__init__":
                if tuple(context.returned) != ("_init_kludge_time", "_init_kludge", "__init__"):
                    _reject(context, "Complete original nested timing/constructor order required")
                context.phase_fields = tuple(vars(context.phase).items())
                _phase(context)
                context.constructor_completed = True


def _normal_return(frame):
    return frame.f_lasti >= 0 and dis.opname[frame.f_code.co_code[frame.f_lasti]] in (
        "RETURN_VALUE",
        "RETURN_CONST",
    )


@contextmanager
def _account(context):
    old_profile, old_trace = context.required_hooks
    locals_before = {}

    def observed(frame, event, arg):
        try:
            _observe(context, frame, event, arg)
        except BaseException as error:
            if error is not context.entry_error:
                _retain_error(context, "observation_" + event, error, (frame, event, arg))
            if event not in ("exception", "return") or context.primary is None:
                raise

    def inherited(hook, frame, event, arg, layer):
        if hook is None or context.inherited_active:
            return None
        context.inherited_active = True
        try:
            return context.call_tracing(hook, (frame, event, arg))
        except BaseException as error:
            _retain_error(context, "inherited_" + layer, error, (frame, event, arg))
            if event not in ("exception", "return", "c_return", "c_exception"):
                raise
        finally:
            context.inherited_active = False

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code.co_filename.startswith(str(NATIVE) + os.sep)
            or frame.f_code in context.wrapper_codes
        ):
            context.last_call = (frame.f_code.co_filename, frame.f_code.co_qualname, frame)
            if len(context.actual_work) >= MAX_SOURCE_CALLS:
                _reject(context, "Declared constructor work bound exhausted")
            context.actual_work.append(context.last_call)
            if context.constructor_completed:
                _reject(context, "Native work after completed constructor is outside this claim")
        inherited(old_profile, frame, event, arg, "profile")
        if context.observing and (
            context.getters[0]() is not context.observers[0]
            or context.getters[1]() is not context.observers[1]
        ):
            _retain_error(
                context,
                "hook_identity",
                ValueError("Inherited hook changed observer"),
                (frame, event, arg),
            )
            if context.primary is not None:
                raise context.primary
            _reject(context, "Observation lost; source continuation stopped")

    def trace(frame, event, arg):
        observed(frame, event, arg)
        prior = old_trace if event == "call" else locals_before.get(id(frame))
        value = inherited(prior, frame, event, arg, "trace")
        # Return-hook loss must be sticky even when no next source line/call
        # arrives. Defer an unwind error while retaining its original primary.
        if context.observing and (
            context.getters[0]() is not context.observers[0]
            or context.getters[1]() is not context.observers[1]
        ):
            _retain_error(
                context,
                "hook_identity",
                ValueError("Inherited hook changed observer"),
                (frame, event, arg),
            )
            if context.primary is not None:
                raise context.primary
            _reject(context, "Observation lost; source continuation stopped")
        if event == "call" or value is not None:
            locals_before[id(frame)] = value
        if context.roles.get(frame.f_code) is not None and event in ("call", "line"):
            _source_guard(context)
        if event == "return":
            locals_before.pop(id(frame), None)
        return trace

    context.observers = (profile, trace)
    try:
        context.setters[0](profile)
        context.setters[1](trace)
        if any(
            getter() is not value
            for getter, value in zip(context.getters, context.observers, strict=True)
        ):
            raise ValueError("Both source observation hooks must be installed before work")
        context.observing = True
        yield
    except BaseException as error:
        selected = context.primary if context.primary is not None else context.entry_error
        if selected is None:
            selected = error
        context.primary = selected
        if selected is not None and selected is not error:
            _retain_error(context, "interrupted_primary", error, selected)
            raise selected  # noqa: B904 - retain exact source exception and cause.
        raise
    finally:
        context.observing = False
        for index in (1, 0):
            try:
                context.setters[index](context.required_hooks[index])
            except BaseException as error:
                context.last_error = ("hook_restore", error, index)
                try:
                    _retain_error(context, "hook_restore", error, index)
                except BaseException as secondary:
                    context.last_reporting_error = ("hook_restore", secondary, error)
                    context.invalid = context.original_guard.invalid = True
        samples = []
        for order in ((0, 1), (1, 0)):
            pair = [None, None]
            for index in order:
                try:
                    pair[index] = context.getters[index]()
                except BaseException as error:
                    context.last_error = ("hook_sample", error, index)
                    try:
                        _retain_error(context, "hook_sample", error, index)
                    except BaseException as secondary:
                        context.last_reporting_error = ("hook_sample", secondary, error)
                        context.invalid = context.original_guard.invalid = True
            samples.append(tuple(pair))
        context.final_hooks = tuple(samples)
        if any(pair[0] is not old_profile or pair[1] is not old_trace for pair in samples):
            context.invalid = context.original_guard.invalid = True


def _finish(context):
    succeeded = False
    try:
        if context.source_error is None:
            _checked(context.claim)
            _bytes(context, complete=True)
            if context.capture_errors or context.invalid or context.original_guard.invalid:
                raise ValueError("Incomplete/poisoned constructor observation")
            succeeded = True
        context.final_capture = parameters._capture(context.source)
    except BaseException as error:
        _retain_error(context, "final_capture_or_check", error)
    return succeeded


def _release(context):
    if context.registered:
        with claims._registry(context.loaded.owner):
            for stack, value in reversed(context.exclusion[1:]):
                if not stack or stack[-1] is not value:
                    raise ValueError("Phase parameter registry changed at closure")
                stack.pop()
        context.registered = False


def _recover_required(context):
    """Only direct restoration/sampling; no fallible error reporter is used."""
    for index in (1, 0):
        try:
            context.setters[index](context.required_hooks[index])
        except BaseException as error:
            context.last_error = ("required_hook_restore", error, index)
            context.raw_errors = (
                *context.raw_errors[-(MAX_CAPTURE_ERRORS - 1) :],
                context.last_error,
            )
            context.invalid = context.original_guard.invalid = True
    samples = []
    for order in ((0, 1), (1, 0)):
        pair = [None, None]
        for index in order:
            try:
                pair[index] = context.getters[index]()
            except BaseException as error:
                context.last_error = ("required_hook_sample", error, index)
                context.raw_errors = (
                    *context.raw_errors[-(MAX_CAPTURE_ERRORS - 1) :],
                    context.last_error,
                )
                context.invalid = context.original_guard.invalid = True
        samples.append(tuple(pair))
    context.final_hooks = tuple(samples)
    return all(
        pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
        for pair in samples
    )


def _record(context, succeeded):
    value = PhaseParameterRecord(
        PHASE_CONSTRUCTION_LAW,
        context.source_identity,
        context.parameter_record.identity,
        context.kind_name,
        (
            id(context.phase),
            tuple((name, id(value)) for name, value in context.optional_inputs),
            tuple((name, id(value)) for name, value in context.phase_fields),
        ),
        _digest(context.before_graph[1]),
        _digest(context.final_capture[1]) if hasattr(context, "final_capture") else None,
        tuple(context.work),
        tuple((file, name, id(frame)) for file, name, frame in context.actual_work),
        tuple(
            (name, id(value), id(frame), line) for name, value, frame, line in context.assignments
        ),
        context.constructor_completed,
        succeeded,
        context.source_error is not None,
        tuple(
            dict.fromkeys(
                (
                    *(row[0] for row in context.capture_errors),
                    *(row[0] for row in context.raw_errors),
                    *("report:" + row[0] for row in context.reporting_errors),
                )
            )
        ),
        "",
    )
    context.record = replace(value, identity=_digest(record_document(value)))
    context.original_record = context.record


@contextmanager
def construction(owner, *, kind, law_id, enabled=False):
    if enabled is not True or any(
        os.environ.get(name) != "1"
        for name in (
            RELEASE,
            parameters.RELEASE,
            parameters.previous.RELEASE,
        )
    ):
        raise PhaseConstructionRejected(
            "Fresh INIT/SIM parameter construction held", stage="release"
        )
    if type(law_id) is not str or law_id != PHASE_CONSTRUCTION_LAW:
        raise PhaseConstructionRejected("Exact INIT/SIM parameter source law required", stage="law")
    _reused()
    entry_hooks = (sys.getprofile(), sys.gettrace())
    entry_setters = (sys.setprofile, sys.settrace)
    entry_getters = (sys.getprofile, sys.gettrace)
    prior = (
        parameters._CONSTRUCTED.get(owner)
        if type(owner) is parameters.WorldReadyParametersOwner
        else None
    )
    try:
        context, claim = _RESERVE(owner)
    except BaseException as error:
        # A return hook can fail after consumption, before its tuple reaches
        # this caller. Recover only the exact newly issued edge, never an old
        # attempt or a replacement owner/context/closure receipt.
        candidate = (
            parameters._CONSTRUCTED.get(owner)
            if type(owner) is parameters.WorldReadyParametersOwner
            else None
        )
        actual = _ISSUED.get(candidate) if type(candidate) is PhaseConstructionClaim else None
        if prior is None and actual is not None and actual.owner is owner:
            actual.original_guard = actual.guard
            actual.source_error = error
            actual.active = actual.guard.active = False
            actual.invalid = actual.guard.invalid = actual.source.invalid = True
            actual.required_hooks = entry_hooks
            actual.stage = "reservation_return"
            if _ACTIVE and _ACTIVE[-1] is actual:
                _ACTIVE.pop()
            else:
                actual.capture_errors += (("reservation_stack", ValueError("Stack changed"), None),)
            try:
                actual.failed_capture = parameters._capture(actual.source)
            except BaseException as secondary:
                actual.capture_errors += (("reservation_partial", secondary, actual.p),)
            for index in (1, 0):
                try:
                    entry_setters[index](entry_hooks[index])
                except BaseException as secondary:
                    actual.capture_errors += (("reservation_hook_restore", secondary, index),)
            samples = []
            for order in ((0, 1), (1, 0)):
                pair = [None, None]
                for index in order:
                    try:
                        pair[index] = entry_getters[index]()
                    except BaseException as secondary:
                        actual.capture_errors += (("reservation_hook_sample", secondary, index),)
                samples.append(tuple(pair))
            actual.final_hooks = tuple(samples)
            _FAILED.append(actual)
            try:
                error.phase_construction_claim = candidate
            except BaseException as secondary:
                actual.capture_errors += (("reservation_exception_attachment", secondary, error),)
        raise
    context.original_guard = context.guard
    context.kind, context.kind_name = kind, None
    context.assignments, context.actual_work, context.raw_returns, context.returned = [], [], [], []
    context.frames, context.lines, context.pending = {}, {}, {}
    context.phase, context.phase_fields, context.optional_inputs = None, (), ()
    context.exclusion = _stacks(context)
    context.constructor_caller = None
    context.constructor_completed = False
    context.last_assignment = context.last_raw = context.last_call = context.timing_graph = None
    context.primary = context.entry_error = context.observation_error = None
    context.raw_errors, context.reporting_errors = (), ()
    context.last_error = context.last_reporting_error = None
    context.raw_error_overflow = False
    context.observing = context.inherited_active = False
    context.call_tracing = sys.call_tracing
    context.required_hooks = entry_hooks
    context.setters, context.getters = entry_setters, entry_getters
    context.cleanup_refusal = PhaseConstructionRejected(
        "Fresh phase parameter construction issued no success",
        stage="closure",
        claim=claim,
        partial=context,
    )
    primary = None
    succeeded = False
    try:
        if entry_getters[0]() is not entry_hooks[0] or entry_getters[1]() is not entry_hooks[1]:
            raise ValueError("Inherited hooks changed during pre-phase reservation")
        if (
            any(name in vars(context.p) for name in STORES)
            or context.loaded.owner in claims._CONSTRUCTED
        ):
            raise ValueError("Only a genuinely fresh pre-phase WorldReady parameter is accepted")
        context.native = _native()
        if type(kind) is not context.native.enum or not any(
            kind is getattr(context.native.enum, name) for name in TIMING_INPUTS
        ):
            raise ValueError("Actual original INIT/SIM kind required; SEED is a separate domain")
        context.kind_name = kind.name
        context.native_bindings = _native_bindings(context.native)
        context.roles = {fn.__code__: name for name, fn in context.native.methods.items()}
        context.wrapper_codes = frozenset(
            fn.__code__ for chain in context.native.chains.values() for fn in chain[:-1]
        )
        context.store_lines = _store_lines()
        context.source_identity, context.bindings = _digest(source_plan()), _bindings()
        with claims._registry(context.loaded.owner):
            if any(stack for stack, _ in context.exclusion[1:]):
                claims._busy(context.loaded.owner, "phase_parameter_construction_conflict")
            for stack, value in context.exclusion[1:]:
                stack.append(value)
            context.registered = True
            parameters.previous.previous.mod.subconfigs.paths._install_audit(context.guard)
        _checked(claim)
        with _account(context):
            yield claim
    except BaseException as error:
        primary = context.source_error = context.primary if context.primary is not None else error
        if error is not primary:
            context.last_error = ("interrupted_source", error, primary)
            try:
                _retain_error(context, "interrupted_source", error, primary)
            except BaseException as secondary:
                context.last_reporting_error = ("interrupted_source", secondary, error)
                context.invalid = context.original_guard.invalid = True
        raise primary  # noqa: B904 - keep the exact actual source exception and cause.
    finally:
        context.cleanup_blocked = False
        context.cleanup_skipped = ()
        for operation in ("finish", "release", "record", "attachment"):
            if operation == "record":
                # Retirement is independent of callbacks and their observers.
                # Never pop a foreign edge or rearm the consumed owner.
                for stack, value in reversed(context.exclusion[1:]):
                    if stack and stack[-1] is value:
                        try:
                            stack.pop()
                        except BaseException as error:
                            context.last_error = ("direct_retirement", error, stack)
                            context.raw_errors = (
                                *context.raw_errors[-(MAX_CAPTURE_ERRORS - 1) :],
                                context.last_error,
                            )
                            context.invalid = True
                context.registered = False
                context.active = context.original_guard.active = False
                try:
                    with _LOCK:
                        if _ACTIVE and _ACTIVE[-1] is context:
                            _ACTIVE.pop()
                        else:
                            context.invalid = True
                except BaseException as error:
                    context.last_error = ("own_retirement", error, None)
                    context.raw_errors = (
                        *context.raw_errors[-(MAX_CAPTURE_ERRORS - 1) :],
                        context.last_error,
                    )
                    context.invalid = True
                succeeded = bool(
                    succeeded
                    and primary is None
                    and not context.capture_errors
                    and not context.invalid
                    and not context.cleanup_blocked
                )
                if not succeeded:
                    context.invalid = context.original_guard.invalid = context.source.invalid = True
                    _FAILED.append(context)
            if operation == "attachment" and primary is None:
                continue
            healthy = False
            if not context.cleanup_blocked:
                try:
                    healthy = _recover_required(context)
                    # Check at THIS caller boundary too: a helper-return hook
                    # may have changed state after its internal final sample.
                    healthy = (
                        healthy
                        and context.getters[0]() is entry_hooks[0]
                        and context.getters[1]() is entry_hooks[1]
                    )
                except BaseException as error:
                    context.last_error = ("recovery_" + operation, error, None)
                    context.raw_errors = (
                        *context.raw_errors[-(MAX_CAPTURE_ERRORS - 1) :],
                        context.last_error,
                    )
                if not healthy:
                    context.cleanup_blocked = True
                    context.invalid = context.original_guard.invalid = True
            if context.cleanup_blocked:
                context.cleanup_skipped += (operation,)
                continue
            try:
                if operation == "finish":
                    succeeded = _finish(context)
                elif operation == "release":
                    _release(context)
                elif operation == "record":
                    _record(context, succeeded)
                else:
                    primary.phase_construction_claim = claim
            except BaseException as error:
                # Keep raw roots without invoking any reporter on a possibly
                # cleared hook. The NEXT callback gets its own recovery above.
                context.last_error = (operation + "_entry_or_return", error, primary)
                context.raw_errors = (
                    *context.raw_errors[-(MAX_CAPTURE_ERRORS - 1) :],
                    context.last_error,
                )
                context.invalid = context.original_guard.invalid = context.source.invalid = True
                succeeded = False
        # Even an unrecoverable earlier boundary gets one final independent
        # restoration attempt, but it never rearms skipped callbacks.
        try:
            final_healthy = _recover_required(context)
            final_healthy = (
                final_healthy
                and context.getters[0]() is entry_hooks[0]
                and context.getters[1]() is entry_hooks[1]
            )
        except BaseException as error:
            context.last_error = ("terminal_recovery", error, None)
            context.raw_errors = (
                *context.raw_errors[-(MAX_CAPTURE_ERRORS - 1) :],
                context.last_error,
            )
            final_healthy = False
        if not final_healthy:
            context.invalid = context.original_guard.invalid = context.source.invalid = True
        if primary is not None:
            raise primary
        elif not succeeded or context.invalid:
            raise context.cleanup_refusal


def _store_lines():
    result = {}
    for node in _nodes().values():
        for item in ast.walk(node):
            if not isinstance(item, ast.Assign) or len(item.targets) != 1:
                continue
            target = item.targets[0]
            if not (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Attribute)
                and isinstance(target.value.value, ast.Name)
                and target.value.value.id == "self"
                and target.value.attr == "p"
                and target.attr in STORES
            ):
                continue
            if target.attr in ("_run_sim", "t_resample"):
                for kind in TIMING_INPUTS:
                    result[(kind, target.attr)] = item.lineno
            else:
                for kind, names in TIMING_INPUTS.items():
                    if isinstance(item.value, ast.Attribute) and item.value.attr in names:
                        result[(kind, target.attr)] = item.lineno
    if set(result) != {(kind, name) for kind in TIMING_INPUTS for name in STORES}:
        raise ValueError("Complete original temporal store locations required")
    return result


def validate_closed_phase(claim, *, original_owner):
    """Same successful record; metadata only, no rearm or division replay."""
    context = _context(claim)
    if (
        original_owner is not context.owner
        or context.active
        or context.invalid
        or context.validating
        or context.source_error is not None
        or context.capture_errors
        or context.thread != get_ident()
        or context.guard is not context.original_guard
        or context.guard.thread != context.thread
        or context.guard.active
        or context.guard.invalid
        or not context.guard.audit_ready
        or context.record is None
        or context.record.succeeded is not True
    ):
        raise PhaseConstructionRejected(
            "Actual successful closed phase claim required",
            stage="closed",
            claim=claim,
            partial=context,
        )
    context.validating = True
    stacks = _stacks(context)
    paths = parameters.previous.previous.mod.subconfigs.paths
    validation = SimpleNamespace(
        invalid=False,
        guard=SimpleNamespace(
            thread=get_ident(),
            active=True,
            invalid=False,
            audit_ready=False,
            directory_depth=0,
            directory_calls=0,
            directory_targets=(),
            filesystem=[],
        ),
    )
    registered = False
    primary = release_error = None
    try:
        with claims._registry(context.loaded.owner):
            if any(stack for stack, _ in stacks):
                claims._busy(context.loaded.owner, "closed_phase_parameter_conflict")
            for stack, _ in stacks:
                stack.append(validation.guard if stack is paths._ACTIVE else validation)
            registered = True
            paths._install_audit(validation.guard)
        _source(context)
        _bytes(context, complete=True)
        prefix.parameters.inherited._same_graph(
            parameters._capture(context.source), context.final_capture
        )
        if (
            claim.record is not context.original_record
            or context.record.work != tuple(context.work)
            or context.record.actual_source_calls
            != tuple((file, name, id(frame)) for file, name, frame in context.actual_work)
            or context.record.stores
            != tuple(
                (name, id(value), id(frame), line)
                for name, value, frame, line in context.assignments
            )
            or context.record.phase_bindings
            != (
                id(context.phase),
                tuple((name, id(value)) for name, value in context.optional_inputs),
                tuple((name, id(value)) for name, value in context.phase_fields),
            )
            or context.record.kind != context.kind_name
            or not context.record.constructor_completed
            or context.record.before_identity != _digest(context.before_graph[1])
            or context.record.after_identity != _digest(context.final_capture[1])
            or validation.invalid
            or validation.guard.invalid
        ):
            raise ValueError("Original completed phase parameter record/exclusion changed")
        return context.original_record
    except BaseException as error:
        primary = error
        context.invalid = True
        raise PhaseConstructionRejected(
            "Closed parameter lineage is stale", stage="closed_drift", claim=claim, partial=context
        ) from error
    finally:
        if registered:
            try:
                with claims._registry(context.loaded.owner):
                    for stack, _ in reversed(stacks):
                        expected = validation.guard if stack is paths._ACTIVE else validation
                        if not stack or stack[-1] is not expected:
                            raise ValueError("Closed validation registry changed")
                        stack.pop()
            except BaseException as error:
                release_error = error
                context.invalid = True
                context.last_error = ("closed_validation_release", error, None)
                try:
                    _retain_error(context, "closed_validation_release", error)
                except BaseException as secondary:
                    context.last_reporting_error = ("closed_validation_release", secondary, error)
                    context.invalid = context.original_guard.invalid = True
        validation.guard.active = context.validating = False
        if primary is None and release_error is not None:
            raise PhaseConstructionRejected(
                "Closed validation release failed",
                stage="closed_release",
                claim=claim,
                partial=context,
            ) from release_error


def _bindings():
    functions = tuple(
        fn for fn in globals().values() if type(fn) is FunctionType and fn.__globals__ is globals()
    )
    return (), (
        PHASE_CONSTRUCTION_LAW,
        RELEASE,
        _LOCK,
        _ACTIVE,
        _ISSUED,
        _FAILED,
        PhaseConstructionClaim,
        PhaseConstructionRejected,
        PhaseParameterRecord,
        shared,
        parameters,
        claims,
        prefix,
        _RESERVE,
        _HISTORY,
        _CHECKED,
        _STACKS,
        *_PROOFS,
        *parameters._bindings()[1],
        *_reused()[1],
        *(
            atom
            for method in (
                PhaseConstructionClaim.parameters.fget,
                PhaseConstructionClaim.check,
                PhaseConstructionClaim.record.fget,
                PhaseConstructionClaim.__init__,
                PhaseConstructionClaim.__reduce_ex__,
                PhaseConstructionRejected.__init__,
            )
            for atom in prefix.parameters.inherited.tissue.aliases._atoms(method)
        ),
        *(
            atom
            for fn in functions
            for atom in prefix.parameters.inherited.tissue.aliases._atoms(fn)
        ),
    )


def _clone(function, **values):
    function = FunctionType(
        function.__code__,
        dict(function.__globals__, **values),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    return function


def _reused():
    labels, objects = [], []
    for original, actual, expected in _REUSED:
        if actual.__code__ is not original.__code__:
            raise ValueError("Shared claim algorithm was replaced")
        if actual.__builtins__ is not original.__builtins__:
            raise ValueError("Shared claim cached builtins changed")
        objects.extend((original, actual, actual.__globals__, actual.__builtins__))
        namespace = actual.__globals__.get("__builtins__")
        namespace = vars(namespace) if type(namespace) is ModuleType else namespace
        if namespace is not actual.__builtins__:
            raise ValueError("Shared claim construction namespace/cached builtins mismatch")
        for name, value, was_global in expected:
            if (name in actual.__globals__) is not was_global:
                raise ValueError("Shared claim lookup category changed: " + name)
            namespace = actual.__globals__ if name in actual.__globals__ else actual.__builtins__
            if namespace.get(name) is not value:
                raise ValueError("Shared claim reached namespace changed: " + name)
            labels.append((original.__name__, name, name in actual.__globals__))
            objects.append(value)
    return tuple(labels), tuple(objects)


# Exactly the accepted generic reservation/history/active-check algorithms.
# Their private namespace changes types/registries only; the old APIs and p
# remain untouched. No SEED claim, law, closure record or permission is reused.
_RESERVE = _clone(
    shared._reserve,
    _LOCK=_LOCK,
    _ACTIVE=_ACTIVE,
    _ISSUED=_ISSUED,
    WorldConstructionClaim=PhaseConstructionClaim,
    WorldConstructionRejected=PhaseConstructionRejected,
)
_STACKS = _clone(shared._stacks, _ACTIVE=_ACTIVE)
_stacks = _STACKS
_HISTORY = _clone(shared._source, _digest=_digest, source_plan=source_plan, _bindings=_bindings)
_CHECKED = _clone(
    shared._checked,
    _context=_context,
    _stacks=_stacks,
    _source=_source,
    _bytes=_bytes,
    WorldConstructionRejected=PhaseConstructionRejected,
)
_REUSED = tuple(
    (
        original,
        actual,
        tuple(
            (
                name,
                actual.__globals__.get(name, actual.__builtins__.get(name)),
                name in actual.__globals__,
            )
            for name in dict.fromkeys(
                item.argval for item in dis.get_instructions(actual) if item.opname == "LOAD_GLOBAL"
            )
        ),
    )
    for original, actual in (
        (shared._reserve, _RESERVE),
        (shared._stacks, _STACKS),
        (shared._source, _HISTORY),
        (shared._checked, _CHECKED),
    )
)
