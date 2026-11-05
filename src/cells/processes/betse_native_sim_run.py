"""Held original report and full-calendar SIM on one actual constructor.

The live Simulator, Cells, Parameters, callback, molecular owners and RNG are
retained. No INIT claimant is recycled. The original run_sim_core body owns its
setup, events, arithmetic and context; a source instruction witness stops it
before native pickle. Only complete natural loop/context return may publish.
Source preparation/software controls are not numerical or parent admission.
"""

import dis
import gc
import hashlib
import json
import os
import struct
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary, WeakValueDictionary

from cells.processes import betse_native_init_sim_assembly as previous
from cells.processes import betse_native_sim_run_source as source
from cells.processes import betse_perturbations as native_streams

LAW_ID = "actual_retained_SIM_report_complete_original_FULL_loop_before_pickle@1"
RELEASE = "CELLS_NATIVE_SIM_RUN_RELEASED"
PARENT_SHA256 = PARENT_REVIEW_SHA256 = None
MAX_ITERATIONS, MAX_WORK, MAX_OBJECTS = 512, 100000, 8192
METADATA_COLLECTION_BYTES = 32 * 2**20
_LOCK, _ACTIVE, _FAILED = RLock(), [], []
_PREPARING, _PREPARATION_FAILURES = None, []
_LAST_PREPARATION_FAILURE = None
_REQUESTS, _CONSUMED, _ISSUED = (WeakKeyDictionary() for _ in range(3))
_IMPORTS, _IMPORT_ACTIVE, _IMPORT_FAILED = WeakKeyDictionary(), [], []
_IMPORT_API = None
_IMPORT_EXPORTS = []
base = previous.terminal.base
_RETENTION_API = tuple(
    (name, function, function.__code__, function.__globals__)
    for name in ("_retain_snapshot", "_column_bytes")
    for function in (vars(previous.terminal)[name],)
)


class SimRunRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None):
        super().__init__(reason)
        self.stage, self.partial = stage, partial


class _BeforeStorage(BaseException):
    pass


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    assembly_owner: object
    assembly_identity: str
    init_identity: str
    parameters_identity: str
    source_identity: str
    maximum: int
    iterations: int
    operator_mode: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Actual live SIM input authority cannot be hydrated")


@dataclass(frozen=True, slots=True)
class Iteration:
    ordinal: int
    source_time: object
    sampled: bool
    after: object
    graph: object
    rng: tuple
    event_calls: tuple
    callback_calls: tuple
    work_end: int


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    assembly_identity: str
    init_identity: str
    current_parameters_identity: str
    operator_mode: str
    before: object
    ready: object
    after: object
    calendar: object
    sampled: object
    dt: object
    iterations: tuple
    rng_before: tuple
    rng_after: tuple
    rng_calls: tuple
    work: tuple
    c_calls: tuple
    metadata_work: tuple
    raw_returns: tuple
    exceptions: tuple
    report_returned: bool
    loop_returned: bool
    context_returned: bool
    before_native_pickle: bool
    identity: str


def _digest(value):
    return previous._digest(value)


def _count(value):
    if type(value) is not int or not 1 <= value <= MAX_ITERATIONS:
        raise ValueError("Explicit complete SIM integer bound in [1,512] required")
    return value


def source_plan():
    return dict(
        law=LAW_ID,
        original=source.source_plan(),
        required_parent=(PARENT_SHA256, PARENT_REVIEW_SHA256),
        max_iterations=MAX_ITERATIONS,
        max_observed_work=MAX_WORK,
        metadata_accounting=dict(
            maximum_operation_records=MAX_WORK,
            retained_cache_operation="one complete fresh sweep; every nested validation counted",
            maximum_caches_per_sweep=9 + 3 * MAX_ITERATIONS,
            nested_attempts_are_work_not_independent_cases=True,
            source_and_C_call_budgets_unchanged=True,
        ),
        max_retained_objects=MAX_OBJECTS,
        fresh_runtime_import_observation_before_INIT_required=True,
        input="actual successful SimAssemblyOwner, never a cache/phase/receipt",
        full_state="all retained/current object fields, graph, layout, aliases, RNG and text",
        admitted_events="original zero/global K/Cl/Na/T/GJ/NaK; scheduled callbacks held",
        supplied_or_fresh_molecular_owner=False,
        unsupported=(
            "FAST",
            "native pickle",
            "cut",
            "pressure/flow/deformation",
            "voltage",
            "live noise",
            "GRN",
            "animation",
            "new molecule/channel/modulator setup",
        ),
        iteration_counts_are_work_not_independent_cases=True,
        numerical_reference_checkpoint_or_biological_admission=False,
    )


def _ready():
    if not all(previous.preparation._pin(v) for v in (PARENT_SHA256, PARENT_REVIEW_SHA256)):
        raise SimRunRejected(
            "Reviewed actual SIM constructor successor held", stage="producer_held"
        )
    file = Path(previous.__file__)
    if file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest() != PARENT_SHA256:
        raise SimRunRejected("Exact current constructor producer required", stage="producer")
    previous._ready()


def _runtime_import_api():
    """Unchanged existing import observer, privately scoped to this source roster."""
    global _IMPORT_API
    if _IMPORT_API is None:
        namespace = dict(
            vars(previous),
            source=source,
            LAW_ID=LAW_ID,
            RELEASE=RELEASE,
            _IMPORT_API=None,
            _IMPORTS=_IMPORTS,
            _IMPORT_ACTIVE=_IMPORT_ACTIVE,
            _IMPORT_FAILED=_IMPORT_FAILED,
        )
        original = previous._phase_import_api
        function = FunctionType(original.__code__, namespace, original.__name__)
        namespace["_phase_import_api"] = function
        _IMPORT_API = original, original.__code__, function, namespace
    original, code, function, namespace = _IMPORT_API
    if (
        previous._phase_import_api is not original
        or original.__code__ is not code
        or function.__code__ is not code
        or function.__globals__ is not namespace
        or function.__builtins__ is not original.__builtins__
        or namespace["source"] is not source
        or namespace["_IMPORTS"] is not _IMPORTS
        or namespace["_IMPORT_ACTIVE"] is not _IMPORT_ACTIVE
        or namespace["_IMPORT_FAILED"] is not _IMPORT_FAILED
    ):
        raise ValueError("Actual reused runtime import observer changed")
    return function()


@contextmanager
def observing_runtime_import(*, enabled=False):
    """Observe the existing fresh native import, never perform/replay an import."""
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise SimRunRejected("Native runtime import work held", stage="release")
    _ready()
    with _runtime_import_api()["observing_native_imports"](enabled=True) as proof:
        yield proof
    if not proof.published or proof.active or proof.primary is not None:
        raise ValueError("Successful actual runtime import closure required")
    exports = []
    for (owner_name, name), path in source.sites().items():
        module = sys.modules.get(path[:-3].replace("/", "."))
        origin = None if module is None else proof.loaded_codes.get(module.__name__)
        if origin is None:
            continue
        if not origin.returned or origin.primary is not None:
            raise ValueError("Actual complete original module loader required")
        owner = module if owner_name is None else vars(module).get(owner_name)
        if owner is None or not hasattr(owner, "__dict__"):
            continue
        actual = vars(owner).get(name)
        if type(actual) is FunctionType:
            exports.append((module, owner, name, actual))
    _IMPORT_EXPORTS.append((proof, tuple(exports)))


def request_document(value):
    return dict(
        law=LAW_ID,
        assembly=value.assembly_identity,
        INIT=value.init_identity,
        parameters=value.parameters_identity,
        source=value.source_identity,
        maximum=_count(value.maximum),
        iterations=_count(value.iterations),
        operator_mode=value.operator_mode,
    )


def from_assembly(owner, *, maximum, law_id):
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise SimRunRejected("Concurrent original SIM declaration", stage="reentrant")
        if type(law_id) is not str or law_id != LAW_ID:
            raise SimRunRejected("Exact original full SIM law required", stage="law")
        bound = _count(maximum)
        _ready()
        if type(owner) is not previous.SimAssemblyOwner:
            raise SimRunRejected("Actual live SIM constructor required", stage="owner")
        context = previous._authority(owner)
        count = _count(context.current.p.sim_tsteps)
        if count > bound:
            raise SimRunRejected(
                "Entire configured SIM calendar exceeds declaration", stage="count"
            )
        value = Request(
            owner,
            context.trial.identity,
            context.parent.trial.identity,
            context.current.record.identity,
            _digest(source_plan()),
            bound,
            count,
            context.parent.request.operator_mode,
            "",
        )
        value = replace(value, identity=_digest(request_document(value)))
        _REQUESTS[value] = context, context.trial, context.parent.trial, context.current.record
        return value


def _fail(context, reason, stage="runtime"):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = SimRunRejected(reason, stage=stage, partial=context)
    raise context.entry_error


def _metadata(context, label, function, *args, **kwargs):
    if len(context.metadata_work) >= MAX_WORK:
        _fail(context, "Declared metadata observation work exhausted", "metadata_work")
    return previous._metadata(context, label, function, *args, **kwargs)


def _domain(parent):
    phase, p, sim = parent.phase, parent.current.p, parent.parent.sim
    if phase.kind is not parent.native.enum.SIM or p._run_sim is not True:
        raise ValueError("Actual SIM phase and exact native _run_sim=True required")
    core = previous.timing.callbacks._source_function(
        vars(type(sim))["run_sim_core"], source.SIM, "run_sim_core", "Simulator"
    )
    enum = core.__globals__["SolverType"]
    if p.solver_type is not enum.FULL or p.is_ecm is not True:
        raise ValueError("Actual original FULL ordinary ECM route required")
    for name in ("fluid_flow", "deform_osmo", "deformation", "sim_eosmosis", "grn_enabled"):
        if getattr(p, name) not in (False, 0):
            raise ValueError("Unsupported original SIM branch: " + name)
    if p.dynamic_noise != 0 or p.anim.is_while_sim or (p.ions_dict["Ca"] == 1 and p.Ca_dyn):
        raise ValueError("Live noise/animation/calcium organelle scope unavailable")
    for key, value in p.scheduled_options.items():
        if type(value) not in (int, float) or value != 0:
            raise ValueError("Actual scheduled callback/runtime owner prerequisite: " + key)
    if phase.dyna.event_cut is not None or phase.dyna._event_voltage is not None:
        raise ValueError("Cut/voltage event ownership unavailable")
    if set(p.global_options) - {
        "K_env",
        "Cl_env",
        "Na_env",
        "T_change",
        "gj_block",
        "NaKATP_block",
    }:
        raise ValueError("Unknown global event configuration")
    if p.molecules_enabled:
        mom = sim.molecules
        if mom is None or mom.core is None:
            raise ValueError("Actual retained molecular INIT owner required")
        conf = p.network_config
        if type(conf) is not dict:
            raise ValueError("Actual complete-load molecular configuration required")
        if conf.get("channels") is not None or conf.get("modulators") is not None:
            raise ValueError("New SIM channel/modulator authority remains unavailable")
        if mom.core.mit_enabled is not False or conf.get("transporters") is not None:
            raise ValueError("SIM mitochondrial/transporter runtime authority unavailable")
    return core


def _same(actual, saved):
    previous.wrappers._same(actual, saved)


def _attributes(function):
    """Exact reached module attribute lookup, without invoking descriptors."""
    result = []
    pending = [function.__code__]
    while pending:
        code = pending.pop()
        pending.extend(c for c in code.co_consts if type(c) is CodeType)
        sequence = tuple(dis.get_instructions(code))
        for index, instruction in enumerate(sequence):
            if instruction.opname != "LOAD_GLOBAL":
                continue
            name = instruction.argval
            value = function.__globals__.get(name, function.__builtins__.get(name))
            if type(value) is not ModuleType:
                continue
            for next_ in sequence[index + 1 :]:
                if next_.opname not in ("LOAD_ATTR", "LOAD_METHOD"):
                    break
                holder, attribute = value, next_.argval
                if type(holder) is not ModuleType or attribute not in vars(holder):
                    break
                value = vars(holder)[attribute]
                result.append((holder, attribute, value))
    return tuple(result)


def _bind_runtime(context):
    """Actual import-issued functions only; equal copied code is insufficient."""
    api = _runtime_import_api()
    context.functions, context.codes, context.members = [], {}, []
    context.import_bindings = []
    exported = tuple(
        row
        for proof, rows in _IMPORT_EXPORTS
        if proof.published and proof.primary is None and not proof.active
        for row in rows
    )
    for (owner_name, name), path in source.sites().items():
        module = sys.modules.get(path[:-3].replace("/", "."))
        if type(module) is not ModuleType:
            continue  # An unreached module is not imported by this adapter.
        if Path(module.__file__).resolve() != source.NATIVE / path:
            raise ValueError("Actual original native module required")
        owner = module if owner_name is None else vars(module).get(owner_name)
        if owner is None or not hasattr(owner, "__dict__"):
            continue
        actual = vars(owner).get(name)
        if type(actual) is not FunctionType:
            continue  # A reached descriptor is refused by entry/source checks.
        if not any(
            row[0] is module and row[1] is owner and row[2] == name and row[3] is actual
            for row in exported
        ):
            # Unobserved/preloaded exports cannot acquire authority by passing
            # a source-code equality check during later preparation.
            continue
        chain = previous.preparation.observation._chain(actual)
        body = chain[-1]
        if previous.preparation.observation._code(body.__code__) != (
            previous.preparation.observation._code(source.import_code(owner_name, name))
        ):
            raise ValueError("Complete actual original runtime executable required")
        # Only genuine import-observed decoration establishes wrapper authority.
        # An undecorated function is tied to the actual observed native loader.
        if len(chain) > 1 or actual in _IMPORTS:
            if name == "noop_context":
                if actual is not context.assembly.parent.external["noop_context"]:
                    raise ValueError("Original retained contextmanager helper required")
            else:
                api["validate"](actual, body, owner=owner, attribute=name)
                context.import_bindings.append((actual, body, owner, name))
        else:
            origins = [row[0] for row in _IMPORTS.values() if row[0].published]
            if not origins or not any(module.__name__ in c.loaded_codes for c in origins):
                raise ValueError("Fresh runtime module loader observation prerequisite")
        context.members.append((owner, name, actual))
        for function in chain:
            state = previous.wrappers._function_state(function)
            attributes = _attributes(function)
            context.functions.append((function, state, attributes))
            context.codes[function.__code__] = (function, owner, name, function is body)
    old = context.assembly.parent
    # Existing authenticated logging/noop support contains stdlib wrappers as
    # well as native helpers. Borrow identities/code only, never an INIT claim.
    chains = [entry.chain for entry in old.log_support]
    chains.extend(old.logger_chains.values())
    for chain in chains:
        for fn in chain:
            if type(fn) is FunctionType:
                context.codes.setdefault(fn.__code__, (fn, None, fn.__name__, False))
                context.functions.append(
                    (fn, previous.wrappers._function_state(fn), _attributes(fn))
                )
    for fn in (old.noop_generator, *old.noop_methods):
        context.codes.setdefault(fn.__code__, (fn, None, fn.__name__, fn is old.noop_generator))
        context.functions.append((fn, previous.wrappers._function_state(fn), _attributes(fn)))
    shuffle = old.parent.shuffle.__func__
    randbelow = type(old.parent.std_rng)._randbelow
    for fn in (shuffle, randbelow):
        context.codes[fn.__code__] = (fn, None, fn.__name__, False)
        context.functions.append((fn, previous.wrappers._function_state(fn), _attributes(fn)))
    completion = old.parent
    if completion.molecule_session is not None:
        original = completion.molecule._context(completion.molecule_session)
        for _, get, set_, _, _ in original.dynamic_callbacks:
            for fn in (get, set_):
                context.codes[fn.__code__] = (fn, None, fn.__name__, False)
                context.functions.append(
                    (fn, previous.wrappers._function_state(fn), _attributes(fn))
                )
    for role in source.METHODS:
        expected = source.code(role)
        if not any(
            previous.preparation.observation._code(c)
            == previous.preparation.observation._code(expected)
            for c in context.codes
        ):
            raise ValueError("Actual runtime source prerequisite: " + role)
    # Bind the actual inherited callback chain rather than accepting a callback.
    base._callback_methods(context)
    context.callback_methods = {n: v[-1] for n, v in context.callback_chains.items()}
    context.callback_binding = base._callback_bindings(context)
    for name, chain in context.callback_chains.items():
        for function in chain:
            context.codes[function.__code__] = (
                function,
                context.callback_owner,
                name,
                function is chain[-1],
            )
    for code, row in tuple(context.codes.items()):
        for child in _descendant_codes(code):
            context.nested_codes.setdefault(child, []).append((code, row[0].__globals__))
    libraries = []
    for _, _, attributes in context.functions:
        for _, _, value in attributes:
            if callable(value) and not any(value is old_value for old_value, _ in libraries):
                libraries.append((value, base.previous._callable_atoms(old, value)))
    context.library_bindings = tuple(libraries)


def _bindings(context):
    _ready()
    previous._run_reservation(context.reservation)
    previous._metadata_guard(context.assembly)
    context.assembly.parent.runtime["_bootstrap"](context.assembly.parent)
    if context.request.source_identity != _digest(source_plan()):
        raise ValueError("Original issued complete SIM source plan changed")
    _entry_bindings(context)
    for namespace, name, actual in context.assembly.parent.original_members:
        if namespace.get(name) is not actual:
            raise ValueError("Inherited original runtime helper changed: " + name)
    if context.solver_context is not None:
        manager, generator = context.noop_object
        if (
            context.solver_context is not manager
            or vars(manager).get("gen") is not generator
            or type(manager) is not context.assembly.parent.noop_type
            or generator.gi_code is not context.assembly.parent.noop_generator.__code__
            or (context.context_returned and generator.gi_frame is not None)
        ):
            raise ValueError("Actual original solver context/generator association changed")


def _entry_bindings(context):
    """Live lookup/code guards, without filesystem work at every instruction."""
    for function, body, owner, name in context.import_bindings:
        context.import_api["validate"](function, body, owner=owner, attribute=name)
    for owner, name, actual in context.members:
        if vars(owner).get(name) is not actual:
            raise ValueError("Actual original runtime class/module dispatch changed: " + name)
    for function, state, attributes in context.functions:
        _same(previous.wrappers._function_state(function), state)
        for holder, name, actual in attributes:
            if vars(holder).get(name) is not actual:
                raise ValueError("Reached original module helper changed: " + name)
    _same(base._callback_bindings(context), context.callback_binding)
    for function, saved in context.library_bindings:
        _same(base.previous._callable_atoms(context.assembly.parent, function), saved)
    if context.expressions is not None:
        context.assembly.parent.parent.molecule._runtime_expressions(context.expressions)


def _links(context):
    if (
        context.invalid
        or context.thread != get_ident()
        or _CONSUMED.get(context.request) is not context
        or _REQUESTS.get(context.request) is not context.refs
        or context.request.identity != _digest(request_document(context.request))
        or context.request.source_identity != context.source_identity
    ):
        raise ValueError("Actual exclusive SIM source/request epoch changed")
    a = context.assembly
    if (
        context.refs[0] is not a
        or context.refs[1] is not a.trial
        or context.refs[2] is not a.parent.trial
        or context.refs[3] is not a.current.record
        or context.phase is not a.phase
        or context.sim is not a.parent.sim
        or context.cells is not a.parent.cells
        or context.p is not a.current.p
        or context.phase.sim is not context.sim
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.phase.dyna is not context.handler
        or context.sim.dyna is not context.handler
        or context.phase.callbacks is not context.callback
        or context.phase.kind is not a.native.enum.SIM
        or context.p._run_sim is not True
        or type(context.p.sim_tsteps) is not int
        or context.p.sim_tsteps != context.request.iterations
        or base._operator_mode(context.cells) != context.request.operator_mode
    ):
        raise ValueError("Original INIT/current-p/SIM/cache/handler ancestry changed")


def _streams(context):
    """Keep original stream evidence and exact actual NumPy state separately.

    NativeStream is the historical finite JSON observation, not a Cache. Read
    the real issued singleton again without drawing/reseeding; never recreate
    its binary state by parsing JSON. If the historical reader refuses, retain
    the available bit-preserving Cache and original exception, then refuse too.
    """
    completion = context.assembly.parent.parent
    row = dict(raw_state=None, numpy=None, original=None, stdlib=None, primary=None)
    context.last_stream_observation = row
    context.source_rng_observations.append(row)
    try:
        raw = _metadata(
            context, "actual_NumPy_get_state_binary_observation", completion.np_rng.get_state
        )
        row["raw_state"] = raw
        numpy = completion.numpy
        if (
            type(raw) is not tuple
            or len(raw) != 5
            or raw[0] != "MT19937"
            or type(raw[1]) is not numpy.ndarray
            or raw[1].dtype != numpy.dtype("uint32")
            or raw[1].shape != (624,)
            or type(raw[2]) is not int
            or not 0 <= raw[2] <= 624
            or type(raw[3]) is not int
            or raw[3] not in (0, 1)
            or type(raw[4]) is not float
        ):
            raise ValueError("Complete actual MT19937 state observation required")
        row["numpy"] = _metadata(
            context, "typed_NumPy_binary_state_snapshot", context.scope.snapshot, raw
        )
        first, second = _metadata(
            context,
            "original_NativeStream_and_stdlib_state_readers",
            base.previous.storage.previous._streams,
            completion,
        )
        row["original"], row["stdlib"] = first, second
        if type(first) is not native_streams.NativeStream or (
            first.numpy_version != numpy.__version__
        ):
            raise ValueError("Actual original NativeStream observation required")
        original = json.loads(first.state_json)
        if (
            type(original) is not list
            or len(original) != 5
            or original[0] != raw[0]
            or original[1] != raw[1].tolist()
            or type(original[2]) is not int
            or type(original[3]) is not int
            or original[2:4] != list(raw[2:4])
            or type(original[4]) is not float
            or struct.pack("!d", original[4]) != struct.pack("!d", raw[4])
        ):
            raise ValueError("Original JSON observation and actual NumPy state disagree")
        previous.terminal.retained_cache.validate(second)
        return row["numpy"], second
    except BaseException as error:
        row["primary"] = error
        raise


def _field_objects(objects):
    """Exact ordered rows encoded by the value snapshot; retain alias repeats."""
    return tuple(
        (role, actual)
        for role, actual in objects
        if not isinstance(actual, (ModuleType, FunctionType, type)) and hasattr(actual, "__dict__")
    )


def _retain_field_objects(context, fields):
    previous_fields = context.observation_field_objects
    if len(fields) < len(previous_fields) or any(
        role != previous_fields[i][0] or actual is not previous_fields[i][1]
        for i, (role, actual) in enumerate(fields[: len(previous_fields)])
    ):
        raise ValueError("Actual SIM observation field-object order/identity changed")
    previous_fields.extend(fields[len(previous_fields) :])


def _observation_roster(context):
    objects, fields = tuple(context.root_objects), tuple(context.observation_field_objects)
    expected = _field_objects(objects)
    if len(expected) != len(fields) or any(
        role != expected_role or actual is not expected_actual
        for (role, actual), (expected_role, expected_actual) in zip(fields, expected, strict=True)
    ):
        raise ValueError("Actual full projector/field-object roster association changed")
    return objects, fields


def _snapshot(context):
    """Reuse original closed value and graph encoders; all actual roots retained."""
    initial = base.previous.storage.previous.previous.previous
    projector = initial._projector(context.assembly.parent.parent.init_parent)
    roots = list(projector.objects)
    for role, obj in (
        *context.assembly.parent.objects,
        *context.assembly.constructor_state[3],
        *context.added_objects,
    ):
        if not any(obj is current for _, current in roots):
            roots.append((role, obj))
    if len(roots) > MAX_OBJECTS:
        raise ValueError("Bounded actual SIM source object roster exhausted")
    projector.objects = roots
    project = initial.core._LITERAL._project
    completion = context.assembly.parent.parent
    values, fields = [], []
    field_objects = _field_objects(roots)
    for role, obj in field_objects:
        holder = vars(obj)
        value = holder
        if completion.molecule_session is not None:
            value = completion.molecule.project_state(completion.molecule_session, value)
        values.append((role, project(projector, value)))
        fields.append((role, obj, holder))
    fresh = context.scope.snapshot(
        (
            tuple(values),
            ("actual_runtime_calendar", context.calendar, context.sampled, context.p.dt),
        )
    )
    cache = _retain_observation(context, fresh)
    if len(roots) < len(context.root_objects) or any(
        role != context.root_objects[i][0] or obj is not context.root_objects[i][1]
        for i, (role, obj) in enumerate(roots[: len(context.root_objects)])
    ):
        raise ValueError("Actual continuing SIM root roster was replaced/omitted")
    context.root_objects.extend(roots[len(context.root_objects) :])
    _retain_field_objects(context, field_objects)
    context.root_fields[:] = [holder for _, _, holder in fields]
    context.graph_view.objects = context.root_objects
    context.graph_view.fields = context.root_fields
    context.graph_calendar[:] = [context.calendar, context.sampled, context.solver_context]
    context.graph_view.calendar = context.graph_calendar
    if completion.molecule_session is not None:
        context.graph_view.molecular = completion.molecule.graph_roots(completion.molecule_session)
    graph = context.scope.graph(context.graph_view, context.graph_view, context.graph_tape)
    return cache, graph, _streams(context)


def _stable(context):
    # No Cells/old-p/current-p retrofit, temporal factory or topology mutation
    # is part of this version. Global events mutate the retained sim/handler.
    initial = base.previous.storage.previous.previous.previous
    projector = initial._projector(context.assembly.parent.parent.init_parent)
    projector.objects = [*projector.objects, *context.assembly.constructor_state[3]]
    project = initial.core._LITERAL._project
    fresh = context.scope.snapshot(
        tuple(
            project(projector, vars(obj))
            for obj in (context.cells, context.assembly.parent.p, context.p, context.phase)
        )
    )
    return _retain_observation(context, fresh)


def _retain_observation(context, fresh):
    """Only retained bytes share; live capture and exact validation stay fresh.

    Reuse the reviewed terminal helper without changing a native object, live
    graph, column descriptor, array axis or any cache default. The context-local
    weak pool and independent headers preserve every complete observation.
    """
    for name, function, code, namespace in _RETENTION_API:
        if (
            vars(previous.terminal).get(name) is not function
            or function.__code__ is not code
            or function.__globals__ is not namespace
            or namespace is not vars(previous.terminal)
        ):
            raise ValueError("Original immutable observation storage helper changed")
    result = _metadata(
        context,
        "complete_fresh_observation_immutable_column_retention",
        _RETENTION_API[0][1],
        context,
        fresh,
    )
    if (
        result.identity != fresh.identity
        or result.descriptor_json != fresh.descriptor_json
        or result.all_finite is not fresh.all_finite
        or len(result.columns) != len(fresh.columns)
    ):
        raise ValueError("Complete fresh observation changed during immutable storage sharing")
    # The unchanged recursive cache encoders/validators can leave temporary
    # closure cycles holding fresh columns. Bound their collection interval;
    # the complete live capture, retained data and cache limits stay unchanged.
    context.retention_since_collection_bytes += sum(c.values.nbytes for c in fresh.columns)
    if context.retention_since_collection_bytes >= METADATA_COLLECTION_BYTES:
        processed = context.retention_since_collection_bytes
        reclaimed = _metadata(context, "unreachable_metadata_cycle_collection", gc.collect)
        context.metadata_collections.append((len(context.retention_work), processed, reclaimed))
        context.retention_since_collection_bytes = 0
    return result


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.capture_errors or context.last_capture is not None:
        raise SimRunRejected(
            "Incomplete observation prevents further work", stage="capture", partial=context
        ) from (context.capture_errors[0][1] if context.capture_errors else context.last_capture[1])
    if not context.active or not _ACTIVE or _ACTIVE[-1] is not context or context.inherited:
        _fail(context, "Actual exclusive original SIM interval required")
    _links(context)
    if context.observing and (sys.getprofile(), sys.gettrace()) != context.observers:
        _fail(context, "Both source/inherited observer hooks required")


def _capture(context, label, error, raw=None):
    # Raw direct returns/exceptions are retained BEFORE fallible secondary work.
    context.last_capture = (label, error, raw)
    try:
        context.capture_errors.append(context.last_capture)
    except BaseException as secondary:
        context.last_capture_recording_error = (label, secondary, context.last_capture)


def _normal(frame):
    return previous.timing._normal_return(frame)


def _context(request, refs):
    assembly = refs[0]
    parent = assembly.parent
    pool = WeakValueDictionary()
    return SimpleNamespace(
        request=request,
        refs=refs,
        assembly=assembly,
        reservation=None,
        phase=assembly.phase,
        p=assembly.current.p,
        old_p=parent.p,
        sim=parent.sim,
        cells=parent.cells,
        handler=assembly.phase.dyna,
        callback=assembly.phase.callbacks,
        initial=parent.initial,
        scope=base.previous.storage.previous._scope(parent.parent),
        graph_tape=parent.graph_tape,
        graph_view=SimpleNamespace(),
        added_objects=[],
        active=True,
        invalid=False,
        thread=get_ident(),
        observing=False,
        inherited=False,
        metadata_work=[],
        retained_validation_work=[],
        retained_validation_attempts=0,
        retained_validation_returns=0,
        retained_validation_active=False,
        last_retained_validation=None,
        work=[],
        c_calls=[],
        raw_returns=[],
        exceptions=[],
        pending={},
        rng_calls=[],
        pending_rng=[],
        frames={},
        capture_errors=[],
        cleanup_errors=[],
        last_cleanup_error=None,
        last_cleanup_recording_error=None,
        final_hooks=None,
        source_error=None,
        entry_error=None,
        primary=None,
        last_capture=None,
        last_capture_recording_error=None,
        unwinds=[],
        trial=None,
        owner=None,
        phase_stage="report",
        functions=[],
        codes={},
        members=[],
        callback_nodes={},
        callback_methods={},
        callback_chains={},
        callback_lookups={},
        callback_sites={},
        source_files={},
        calendar=None,
        sampled=None,
        solver_context=None,
        calendar_raw=None,
        loop_frame=None,
        core_frame=None,
        noop_frame=None,
        current=None,
        iterations=[],
        event_calls=[],
        callback_calls=[],
        sample_calls=[],
        report_returned=False,
        loop_returned=False,
        context_returned=False,
        boundary_seen=False,
        stop=_BeforeStorage(),
        boundaries=source.boundaries(),
        core_roles={},
        before=None,
        ready=None,
        after=None,
        stable=None,
        observers=None,
        last_raw=None,
        import_bindings=[],
        import_api=None,
        source_identity=request.source_identity,
        nested_codes={},
        root_objects=[],
        root_fields=[],
        observation_field_objects=[],
        graph_calendar=[None, None, None],
        expressions=None,
        noop_object=None,
        library_bindings=(),
        sealed_identity=None,
        source_rng_observations=[],
        last_stream_observation=None,
        retained_columns=pool,
        retained_columns_record=pool,
        retention_work=[],
        last_retention_raw=None,
        retention_since_collection_bytes=0,
        metadata_collections=[],
    )


def _descendant_codes(code):
    for child in code.co_consts:
        if type(child) is CodeType:
            yield child
            yield from _descendant_codes(child)


def _bind_expressions(context):
    """Rebind actual freshly written expression text; compile metadata only."""
    if not context.p.molecules_enabled:
        return
    completion = context.assembly.parent.parent
    module = completion.molecule
    original = module._context(completion.molecule_session)
    if context.sim.molecules is not original.mom or context.sim.molecules.core is not original.core:
        _fail(context, "Native SIM reload may not replace original molecular owners", "molecules")
    rows = []
    for obj in original.core.molecules.values():
        if any(
            getattr(obj, field)
            for field in ("active_pumping", "ion_channel_gating", "change_bounds", "cell_clamp")
        ):
            _fail(context, "Unsupported original molecule runtime branch", "molecules")
        rows.append((obj, "gad_eval_string"))
    for collection in (original.core.reactions, original.core.reactions_env):
        rows.extend((obj, "reaction_eval_string") for obj in collection.values())
    expressions, bindings = [], []
    namespace = original.functions[("MasterOfNetworks", "run_loop")].__globals__
    for obj, name in rows:
        text = vars(obj).get(name)
        if type(text) is not str or len(text) > 1048576:
            _fail(context, "Bounded actual native expression text required", "molecules")
        code = compile(text, "<string>", "eval", dont_inherit=True)
        probe = FunctionType(code, namespace)
        expressions.append((obj, name, text, code))
        bindings.append((probe, module._function_bindings(probe)))
    context.expressions = SimpleNamespace(
        original=original, expressions=tuple(expressions), expression_bindings=tuple(bindings)
    )
    module._runtime_expressions(context.expressions)


def _role(context, code):
    return context.core_roles.get(code)


def _bind_roles(context):
    for role in source.METHODS:
        expected = previous.preparation.observation._code(source.code(role))
        candidates = [
            code
            for code, row in context.codes.items()
            if row[3] and previous.preparation.observation._code(code) == expected
        ]
        if len(candidates) != 1:
            raise ValueError("One actual original source body required: " + role)
        context.core_roles[candidates[0]] = role


def _calendar(context, frame, raw):
    context.calendar_raw = (frame, raw)
    if type(raw) is not tuple or len(raw) != 3 or context.calendar is not None:
        _fail(context, "One complete actual native calendar return required", "calendar")
    calendar, sampled, manager = raw
    numpy = context.assembly.parent.numpy
    if (
        type(calendar) is not numpy.ndarray
        or calendar.ndim != 1
        or calendar.dtype.kind != "f"
        or calendar.dtype.itemsize != 8
        or len(calendar) != context.request.iterations
        or type(sampled) is not set
        or not numpy.isfinite(calendar).all()
        or any(type(t) is not numpy.float64 or not numpy.isfinite(t) for t in sampled)
        or any(t not in calendar for t in sampled)
    ):
        _fail(
            context, "Complete unchanged original bounded calendar/sample axes required", "calendar"
        )
    old = context.assembly.parent
    cls, generator = old.noop_type, old.noop_generator
    if type(manager) is not cls or manager.gen.gi_code is not generator.__code__:
        _fail(context, "Actual original no-animation solver context required", "calendar")
    context.calendar, context.sampled, context.solver_context = raw
    context.noop_frame = manager.gen.gi_frame
    context.noop_object = manager, manager.gen
    context.calendar_snapshot = context.scope.snapshot((calendar, sampled, context.p.dt))


def _finish_iteration(context):
    if context.current is None:
        return
    ordinal, label, sampled, event_start, callback_start = context.current
    events = tuple(context.event_calls[event_start:])
    callbacks = tuple(context.callback_calls[callback_start:])
    if tuple(role for role, _, _ in events) != (
        "events",
        "global_events",
        "tissue_events",
        "make_changes",
    ):
        _fail(context, "Duplicate, omitted or out-of-order original event application", "events")
    sampled_calls = [row for row in callbacks if row[0] == "progressed_next"]
    if len(sampled_calls) != int(sampled):
        _fail(context, "Duplicate/omitted sampled callback", "sampling")
    samples = [row for row in context.sample_calls if row[0] == ordinal]
    if len(samples) != int(sampled) or any(row[1] is not label for row in samples):
        _fail(context, "Duplicate/omitted native time-storage call", "sampling")
    _bindings(context)
    if _stable(context).identity != context.stable.identity:
        _fail(context, "Unowned parameter/geometry/phase change", "stable_state")
    after, graph, streams = _metadata(
        context, "actual_SIM_iteration_full_state_graph_RNG", _snapshot, context
    )
    context.iterations.append(
        Iteration(
            ordinal, label, sampled, after, graph, streams, events, callbacks, len(context.work)
        )
    )
    context.current = None


def _begin_iteration(context, frame):
    ordinal = len(context.iterations)
    if context.current is not None or ordinal >= context.request.iterations:
        _fail(context, "Duplicate or excess original iteration entry", "iteration")
    label = frame.f_locals.get("t")
    if type(label) is not context.assembly.parent.numpy.float64 or (
        struct.pack("!d", label) != struct.pack("!d", context.calendar[ordinal])
    ):
        _fail(context, "Absolute original calendar ordinal/time changed", "iteration")
    context.current = (
        ordinal,
        label,
        label in context.sampled,
        len(context.event_calls),
        len(context.callback_calls),
    )


def _source_entry(context, frame, row):
    function, owner, name, is_body = row
    if frame.f_globals is not function.__globals__ or frame.f_code is not function.__code__:
        _fail(context, "Original source function/global identity required", "source")
    for key, value in (function.__kwdefaults__ or {}).items():
        if key.startswith("__beartype_") and frame.f_locals.get(key) is not value:
            _fail(context, "Actual wrapper hidden delegate/default changed", "dispatch")
    if (
        is_body
        and getattr(owner, "__name__", None) == "Simulator"
        and (frame.f_locals.get("self") is not context.sim)
    ):
        _fail(context, "Actual retained Simulator receiver required", "dispatch")
    if isinstance(owner, type):
        receiver = frame.f_locals.get("self")
        if receiver is not None and name in vars(receiver):
            _fail(context, "Native instance method shadowing refused", "dispatch")
    role = _role(context, frame.f_code)
    if role == "report":
        if context.phase_stage != "report" or context.report_returned:
            _fail(context, "One original report before run_core required", "order")
    elif role == "run_core":
        if not context.report_returned or context.core_frame is not None:
            _fail(context, "One original run_core after report required", "order")
        context.core_frame, context.phase_stage = frame, "setup"
    elif role == "loop":
        if context.calendar is None or context.loop_frame is not None:
            _fail(context, "One full original loop after actual calendar required", "order")
        if (
            frame.f_locals.get("phase") is not context.phase
            or frame.f_locals.get("time_steps") is not context.calendar
            or frame.f_locals.get("time_steps_sampled") is not context.sampled
            or frame.f_locals.get("anim_cells") is not None
        ):
            _fail(context, "Original actual loop arguments/axes required", "calendar")
        context.loop_frame, context.phase_stage = frame, "loop"
        context.ready = _metadata(context, "actual_SIM_after_setup_full_state", _snapshot, context)
    if is_body and role in ("events", "global_events", "tissue_events", "make_changes"):
        current = context.current
        if current is None or frame.f_locals.get("self") is not context.handler:
            _fail(context, "Original handler in active actual SIM iteration required", "events")
        if role == "events" and frame.f_back is not context.loop_frame:
            # The immediate parent may be its actual imported type-check wrapper.
            caller = frame.f_back
            if caller is None or caller.f_back is not context.loop_frame:
                _fail(context, "Original loop-to-event callsite required", "events")
        if role != "make_changes" and (
            frame.f_locals.get("phase") is not context.phase
            or frame.f_locals.get("t") is not current[1]
        ):
            _fail(context, "Event phase/time owner changed", "events")
        offset = len(context.event_calls) - current[3]
        expected = ("events", "global_events", "tissue_events", "make_changes")
        if offset >= len(expected) or role != expected[offset]:
            _fail(context, "Duplicate/omitted/out-of-order event entry", "events")
        context.event_calls.append((role, frame, current[1]))
    if is_body and name in context.callback_methods:
        if frame.f_locals.get("self") is not context.callback:
            _fail(context, "Actual retained callback required", "callback")
        if name == "progress_ranged" and (
            context.calendar is None
            or context.loop_frame is not None
            or any(row[0] == name for row in context.callback_calls)
            or type(frame.f_locals.get("progress_max")) is not int
            or frame.f_locals["progress_max"] != len(context.sampled)
        ):
            _fail(context, "One actual sampled-calendar range callback required", "callback")
        context.callback_calls.append((name, frame, context.current))
    if is_body and role == "sample":
        if (
            context.current is None
            or not context.current[2]
            or frame.f_locals.get("t") is not context.current[1]
            or frame.f_locals.get("cells") is not context.cells
            or frame.f_locals.get("p") is not context.p
            or any(row[0] == context.current[0] for row in context.sample_calls)
        ):
            _fail(context, "Actual single sampled iteration storage owner required", "sampling")
        context.sample_calls.append((context.current[0], context.current[1], frame))
    if is_body and name == "__init__":
        actual = frame.f_locals.get("self")
        if actual is not None and not any(actual is value for _, value in context.added_objects):
            context.added_objects.append((frame.f_code.co_qualname, actual))


def _observe(context, frame, event, arg):
    row = context.codes.get(frame.f_code)
    if row is None and frame.f_code in context.nested_codes:
        allowed = context.nested_codes[frame.f_code]
        if not any(
            frame.f_globals is namespace
            and frame.f_back is not None
            and frame.f_back.f_code is parent
            for parent, namespace in allowed
        ):
            _fail(context, "Original nested source/closure callsite required", "source")
        if event == "call":
            _guard(context)
            context.work.append((frame, frame.f_code, frame.f_globals))
        return
    if row is None and frame.f_code.co_filename == "<string>" and context.expressions is not None:
        original = context.expressions.original
        namespace = original.functions[("MasterOfNetworks", "run_loop")].__globals__
        matched = any(
            original.api.previous._constant(code) == original.api.previous._constant(frame.f_code)
            for _, _, _, code in context.expressions.expressions
        )
        caller = frame.f_back
        if (
            not matched
            or frame.f_globals is not namespace
            or caller is None
            or caller.f_code.co_name != "run_loop"
            or frame.f_locals is not caller.f_locals.get("localo")
            or context.current is None
            or frame.f_locals.get("phase") is not context.phase
            or frame.f_locals.get("t") is not context.current[1]
        ):
            _fail(
                context,
                "Actual native eval text/global/local/time association required",
                "expression",
            )
        if event == "call":
            _guard(context)
            context.work.append((frame, frame.f_code, frame.f_globals))
        return
    if row is None:
        if frame.f_code.co_filename.startswith(str(source.NATIVE) + os.sep):
            # No unknown original code, supplied callback or native namespace
            # acquires authority by being reached. Capture an honest prerequisite.
            _fail(
                context,
                "Unbound actual native helper: " + frame.f_code.co_qualname,
                "native_helper_prerequisite",
            )
        return
    role = _role(context, frame.f_code)
    if event == "call":
        _guard(context)
        _entry_bindings(context)
        if len(context.work) + len(context.c_calls) >= MAX_WORK:
            _fail(context, "Actual declared SIM source work exhausted", "work")
        context.work.append((frame, frame.f_code, frame.f_globals))
        context.frames[id(frame)] = frame
        _source_entry(context, frame, row)
        if role in ("run_core", "loop"):
            frame.f_trace_opcodes = True
    elif event in ("line", "opcode"):
        _guard(context)
        # Check bindings after inherited line/opcode callbacks before another
        # source instruction can reach a replaced helper or receiver.
        _entry_bindings(context)
        if frame is context.loop_frame and event == "opcode":
            if frame.f_lasti == context.boundaries["for_iter"]:
                _finish_iteration(context)
            elif frame.f_lasti == context.boundaries["iteration"]:
                _begin_iteration(context, frame)
        if (
            frame is context.core_frame
            and event == "opcode"
            and (frame.f_lasti == context.boundaries["stop"])
        ):
            context.boundary_seen = True
            instability = frame.f_locals.get("exception_instability")
            if instability is not None:
                context.source_error = instability
                raise instability
            if not context.loop_returned or not context.context_returned:
                _fail(context, "Natural loop and normal context return required", "completion")
            raise context.stop
    elif event == "return" and _normal(frame):
        if role == "report":
            context.report_returned, context.phase_stage = True, "run_core"
        elif role == "calendar":
            _calendar(context, frame, arg)
        elif role == "reload":
            _metadata(
                context, "actual_SIM_native_reload_expression_binding", _bind_expressions, context
            )
        elif role == "loop":
            _finish_iteration(context)
            if len(context.iterations) != context.request.iterations:
                _fail(context, "Full actual SIM calendar did not exhaust", "completion")
            context.loop_returned = True
        elif frame is context.noop_frame:
            context.context_returned = context.loop_returned
    elif event == "exception" and type(arg) is tuple and arg[1] is not context.stop:
        context.pending[id(frame)] = arg[1]
        context.exceptions.append((frame, arg[1]))


def _recover(context, prior):
    """Independent finite recovery; a secondary hook error never masks primary."""
    for label, getter, setter, original in (
        ("trace", sys.gettrace, sys.settrace, prior[1]),
        ("profile", sys.getprofile, sys.setprofile, prior[0]),
    ):
        for attempt in range(3):
            try:
                setter(original)
                if getter() is original:
                    break
            except BaseException as error:
                context.last_cleanup_error = (label, attempt, error)
                try:
                    context.cleanup_errors.append(context.last_cleanup_error)
                except BaseException as secondary:
                    context.last_cleanup_recording_error = (secondary, context.last_cleanup_error)
    values = []
    for label, getter in (("profile", sys.getprofile), ("trace", sys.gettrace)):
        try:
            values.append(getter())
        except BaseException as error:
            context.last_cleanup_error = (label + "_final", None, error)
            try:
                context.cleanup_errors.append(context.last_cleanup_error)
            except BaseException as secondary:
                context.last_cleanup_recording_error = (secondary, context.last_cleanup_error)
            values.append(None)
    context.final_hooks = tuple(values)
    final = context.final_hooks[0] is prior[0] and context.final_hooks[1] is prior[1]
    if not final:
        context.last_cleanup_error = (
            "final_hooks",
            None,
            ValueError("Original hooks not restored"),
        )
        try:
            context.cleanup_errors.append(context.last_cleanup_error)
        except BaseException as secondary:
            context.last_cleanup_recording_error = (secondary, context.last_cleanup_error)
    return final


def _profile_event(context, frame, event, arg):
    if event not in ("c_call", "c_return", "c_exception"):
        return
    original_streams = context.assembly.parent.parent
    rng = (
        getattr(arg, "__self__", None) is original_streams.np_rng
        or getattr(arg, "__self__", None) is original_streams.std_rng
    )
    if frame.f_code not in context.codes and not rng:
        return
    context.last_raw = (frame, event, arg)
    if len(context.work) + len(context.c_calls) >= MAX_WORK:
        _fail(context, "Declared actual source/C work exhausted", "work")
    context.c_calls.append(context.last_raw)
    if rng and event == "c_call":
        _guard(context)
        if frame.f_code not in context.codes:
            _fail(context, "Actual original RNG source frame required", "RNG")
        row = dict(frame=frame, delegate=arg, before=None, after=None, outcome="entered")
        context.rng_calls.append(row)
        context.pending_rng.append(row)
        row["before"] = _metadata(context, "actual_RNG_entry_state_observation", _streams, context)
    elif rng:
        if not context.pending_rng:
            _fail(context, "RNG exit without actual entry", "RNG")
        row = context.pending_rng.pop()
        if row["delegate"] is not arg or row["frame"] is not frame:
            _fail(context, "Actual RNG source/delegate pairing changed", "RNG")
        row["outcome"] = event
        row["after"] = _metadata(context, "actual_RNG_exit_state_observation", _streams, context)
    if event == "c_call":
        _guard(context)
        _entry_bindings(context)


def _execute(context):
    # Both are actual original bound methods; no private numerical namespace,
    # replacement equation, calendar, callback or partial-loop execution.
    context.sim.sim_info_report(context.phase)
    context.sim.run_sim_core(context.phase)
    _fail(context, "Original run returned without pre-storage witness", "boundary")


def _run_observed(context):
    prior = sys.getprofile(), sys.gettrace()
    local_traces, primary, primary_cause = {}, None, None

    def capture(label, error, raw):
        # The witness survives a recorder's own entry/append refusal. Such a
        # secondary failure must neither replace an escaping source exception
        # nor allow a later delegate to proceed as if capture were complete.
        context.last_capture = (label, error, raw)
        try:
            _capture(context, label, error, raw)
        except BaseException as secondary:
            context.last_capture_recording_error = (label, secondary, context.last_capture)

    def inherited(function, frame, event, arg):
        if function is None:
            return None
        context.inherited = True
        try:
            if not context.observing:
                # End only our source/state observation. The inherited hook
                # still owns admission and cleanup events until it is restored.
                return function(frame, event, arg)
            before = _metadata(context, "before_inherited_observer_live_state", _snapshot, context)
            result = function(frame, event, arg)
            after = _metadata(context, "after_inherited_observer_live_state", _snapshot, context)
            if before[0].identity != after[0].identity or tuple(v.identity for v in before[2]) != (
                tuple(v.identity for v in after[2])
            ):
                raise ValueError("Inherited observer mutated actual source state/RNG")
            _same(before[1][0], after[1][0])
            if before[1][1] != after[1][1]:
                raise ValueError("Inherited observer mutated actual source aliases/layout")
            return result
        except BaseException as error:
            capture("inherited_" + event, error, (frame, arg))
            if event not in ("exception", "return", "c_return", "c_exception"):
                raise
            return None
        finally:
            context.inherited = False

    def profile(frame, event, arg):
        if not context.observing:
            inherited(prior[0], frame, event, arg)
            return
        # Keep the direct raw event even when an inherited observer fails.
        try:
            _profile_event(context, frame, event, arg)
        except BaseException as error:
            if event not in ("c_return", "c_exception", "return"):
                raise
            capture("profile_observation_" + event, error, (frame, arg))
        inherited(prior[0], frame, event, arg)
        if event == "c_call" and frame.f_code in context.codes:
            _guard(context)
            _entry_bindings(context)

    def trace(frame, event, arg):
        if not context.observing:
            fn = prior[1] if event == "call" else local_traces.get(id(frame))
            result = inherited(fn, frame, event, arg)
            if event == "return":
                local_traces.pop(id(frame), None)
            elif result is not None:
                local_traces[id(frame)] = result
            return trace if result is not None else None
        relevant = (
            frame.f_code in context.codes
            or frame.f_code in context.nested_codes
            or frame.f_code.co_filename == "<string>"
            and context.expressions is not None
        )
        if relevant and event in ("return", "exception"):
            context.last_raw = (frame, event, arg)
            try:
                if event == "exception" and arg[1] is not context.stop:
                    context.pending[id(frame)] = arg[1]
                context.raw_returns.append(context.last_raw)
            except BaseException as error:
                capture("raw_source_" + event, error, (frame, arg))
        fn = prior[1] if event == "call" else local_traces.get(id(frame))
        result = inherited(fn, frame, event, arg)
        if result is not None:
            local_traces[id(frame)] = result
        try:
            _observe(context, frame, event, arg)
        except BaseException as error:
            if error is context.stop:
                raise
            if event in ("return", "exception"):
                capture("source_observation_" + event, error, (frame, arg))
            else:
                raise
        if relevant and event == "return" and not _normal(frame):
            pending = context.pending.get(id(frame))
            if pending is not None and pending is not context.stop:
                # A helper may unwind into an original caller's supported
                # FileNotFoundError/ESTALE retry. Retain it as pending forensic
                # evidence; only an error escaping _execute is a primary.
                try:
                    context.unwinds.append((frame, pending))
                except BaseException as error:
                    capture("source_unwind", error, (frame, pending))
        elif relevant and event == "return":
            context.pending.pop(id(frame), None)
        if event == "return":
            local_traces.pop(id(frame), None)
        return trace

    context.observers = profile, trace
    try:
        sys.setprofile(profile)
        sys.settrace(trace)
        context.observing = True
        _execute(context)
    except BaseException as error:
        if error is not context.stop:
            primary = context.source_error if context.source_error is not None else error
            primary_cause = primary.__cause__
            if any(pending is error for pending in context.pending.values()):
                context.source_error = error
            context.primary = primary
        elif not context.boundary_seen:
            primary = SimRunRejected("Foreign boundary sentinel", stage="boundary", partial=context)
            primary_cause = error
            context.primary = primary
    finally:
        context.observing = False
        try:
            _recover(context, prior)
        except BaseException as error:
            # An inherited helper-entry hook can reject _recover before its
            # body runs. Recovery therefore has an independent caller boundary.
            context.last_cleanup_error = ("recovery_entry", None, error)
            try:
                context.cleanup_errors.append(context.last_cleanup_error)
            except BaseException as secondary:
                context.last_cleanup_recording_error = (secondary, context.last_cleanup_error)
        finally:
            # Never short-circuit the second hook, even if its peer/getter or
            # the secondary evidence writer fails. Limits remain finite.
            for label, getter, setter, original in (
                ("trace", sys.gettrace, sys.settrace, prior[1]),
                ("profile", sys.getprofile, sys.setprofile, prior[0]),
            ):
                for attempt in range(3):
                    try:
                        if getter() is not original:
                            setter(original)
                        if getter() is original:
                            break
                    except BaseException as error:
                        context.last_cleanup_error = (label, attempt, error)
                        try:
                            context.cleanup_errors.append(context.last_cleanup_error)
                        except BaseException as secondary:
                            context.last_cleanup_recording_error = (
                                secondary,
                                context.last_cleanup_error,
                            )
            final = []
            for label, getter in (("profile", sys.getprofile), ("trace", sys.gettrace)):
                try:
                    final.append(getter())
                except BaseException as error:
                    context.last_cleanup_error = (label + "_final", None, error)
                    try:
                        context.cleanup_errors.append(context.last_cleanup_error)
                    except BaseException as secondary:
                        context.last_cleanup_recording_error = (
                            secondary,
                            context.last_cleanup_error,
                        )
                    final.append(None)
            context.final_hooks = tuple(final)
    if primary is not None:
        raise primary from primary_cause
    if (
        context.final_hooks[0] is not prior[0]
        or context.final_hooks[1] is not prior[1]
        or context.capture_errors
        or context.cleanup_errors
        or context.last_capture is not None
        or context.last_cleanup_error is not None
    ):
        raise SimRunRejected(
            "Incomplete source/observer recovery", stage="capture", partial=context
        )


def record_document(value):
    return dict(
        law=LAW_ID,
        request=value.request_identity,
        assembly=value.assembly_identity,
        INIT=value.init_identity,
        parameters=value.current_parameters_identity,
        operator_mode=value.operator_mode,
        before=value.before.identity,
        ready=value.ready[0].identity,
        after=value.after[0].identity,
        calendar=value.calendar.identity,
        sampled=value.sampled.identity,
        dt=struct.pack("!d", value.dt).hex(),
        iterations=tuple(
            (
                r.ordinal,
                struct.pack("!d", r.source_time).hex(),
                r.sampled,
                r.after.identity,
                tuple(v.identity for v in r.rng),
                r.work_end,
                _digest(r.graph[1]),
                tuple((role, id(frame), id(t)) for role, frame, t in r.event_calls),
                tuple((name, id(frame)) for name, frame, _ in r.callback_calls),
            )
            for r in value.iterations
        ),
        streams=(
            tuple(v.identity for v in value.rng_before),
            tuple(v.identity for v in value.rng_after),
        ),
        rng_calls=tuple(
            (
                id(row["frame"]),
                id(row["delegate"]),
                row["outcome"],
                None if row["before"] is None else tuple(v.identity for v in row["before"]),
                None if row["after"] is None else tuple(v.identity for v in row["after"]),
            )
            for row in value.rng_calls
        ),
        calls=tuple((id(f), id(c), id(ns)) for f, c, ns in value.work),
        metadata_work=value.metadata_work,
        c_calls=tuple((id(f), kind, id(fn)) for f, kind, fn in value.c_calls),
        raw=tuple((id(f), event, id(raw)) for f, event, raw in value.raw_returns),
        exceptions=tuple((id(f), id(error)) for f, error in value.exceptions),
        report=value.report_returned,
        loop=value.loop_returned,
        context=value.context_returned,
        before_native_pickle=value.before_native_pickle,
    )


def prepare(request, *, enabled=False):
    """Reserve the attempt before source admission or context construction."""
    global _PREPARING, _LAST_PREPARATION_FAILURE
    if _PREPARING is not None:
        attempt = _PREPARING
        attempt["invalid"] = True
        if attempt["entry_error"] is None:
            attempt["entry_error"] = SimRunRejected(
                "Concurrent original SIM attempt", stage="reentrant", partial=attempt
            )
        if attempt["context"] is not None:
            attempt["context"].invalid = True
            attempt["context"].entry_error = attempt["entry_error"]
        raise attempt["entry_error"]
    attempt = dict(
        request=request,
        context=None,
        invalid=False,
        entry_error=None,
        primary=None,
        consumed=False,
        active=True,
        recording_error=None,
    )
    _PREPARING = attempt
    try:
        if enabled is not True or os.environ.get(RELEASE) != "1":
            raise SimRunRejected("Actual original SIM work remains held", stage="release")
        result = _prepare(request, attempt)
        _preparation_guard(attempt)
        return result
    except BaseException as error:
        attempt["primary"], attempt["invalid"] = error, True
        context = attempt["context"]
        if context is not None:
            context.invalid = True
            if context.owner is not None:
                try:
                    _ISSUED.pop(context.owner, None)
                except BaseException as secondary:
                    attempt["recording_error"] = ("withdraw_issued", secondary)
        _LAST_PREPARATION_FAILURE = attempt
        try:
            _PREPARATION_FAILURES.append(attempt)
        except BaseException as secondary:
            attempt["recording_error"] = ("failure_ledger", secondary)
        if isinstance(error, SimRunRejected):
            if error.partial is None:
                try:
                    error.partial = context if context is not None else attempt
                except BaseException as secondary:
                    attempt["recording_error"] = ("failure_attachment", secondary)
            raise
        raise SimRunRejected(
            "Original SIM admission failed", stage="admission", partial=attempt
        ) from error
    finally:
        attempt["active"] = False
        if _PREPARING is attempt:
            _PREPARING = None
        else:
            attempt["invalid"] = True


def _preparation_guard(attempt):
    if _PREPARING is not attempt or attempt["invalid"] or attempt["entry_error"] is not None:
        if attempt["entry_error"] is None:
            attempt["entry_error"] = SimRunRejected(
                "Original SIM admission reservation changed", stage="reentrant", partial=attempt
            )
        raise attempt["entry_error"]


def _prepare(request, attempt):
    _preparation_guard(attempt)
    if attempt["request"] is not request:
        attempt["invalid"] = True
        raise SimRunRejected(
            "Original admission request association changed", stage="request", partial=attempt
        )
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise SimRunRejected("Concurrent original SIM attempt", stage="reentrant")
        issued = type(request) is Request and request in _REQUESTS
        if issued:
            if request in _CONSUMED:
                raise SimRunRejected("Original SIM request already attempted", stage="consumed")
            _CONSUMED[request] = attempt
            attempt["consumed"] = True
        _ready()
        _preparation_guard(attempt)
        if not issued:
            raise SimRunRejected("Actual issued full SIM request required", stage="request")
        context = _context(request, _REQUESTS[request])
        attempt["context"] = context
        _CONSUMED[request] = context
        _preparation_guard(attempt)
        _ACTIVE.append(context)
        try:
            _metadata(
                context,
                "actual_original_constructor_final_verification",
                previous._authority,
                request.assembly_owner,
            )
            if context.request.source_identity != _digest(source_plan()):
                _fail(context, "Issued exact SIM source plan changed", "source")
            _metadata(context, "actual_native_SIM_domain_verification", _domain, context.assembly)
            context.reservation = _metadata(
                context,
                "actual_constructor_irreversible_run_retirement",
                previous.reserve_for_run,
                request.assembly_owner,
                expected_trial=context.refs[1],
                law_id=previous.RUN_RESERVATION_LAW,
                enabled=True,
            )
            _links(context)
            _metadata(
                context, "actual_runtime_import_source_helper_binding", _bind_runtime, context
            )
            context.import_api = _runtime_import_api()
            _bind_roles(context)
            context.stable = _metadata(
                context, "original_geometry_parameter_phase_state", _stable, context
            )
            before = _metadata(
                context, "actual_SIM_before_complete_state_graph_RNG", _snapshot, context
            )
            context.before = before
            _run_observed(context)
            _links(context)
            _bindings(context)
            if (
                not context.report_returned
                or not context.loop_returned
                or not context.context_returned
                or not context.boundary_seen
                or context.current is not None
                or len(context.iterations) != request.iterations
                or context.primary is not None
                or context.source_error is not None
                or context.capture_errors
                or context.cleanup_errors
                or context.ready is None
            ):
                _fail(
                    context,
                    "Complete natural report/setup/loop/context evidence required",
                    "completion",
                )
            if _stable(context).identity != context.stable.identity:
                _fail(context, "Unowned geometry/parameter/phase change", "stable_state")
            context.after = _metadata(
                context, "actual_SIM_final_complete_state_graph_RNG", _snapshot, context
            )
            value = Trial(
                request.identity,
                request.assembly_identity,
                request.init_identity,
                request.parameters_identity,
                request.operator_mode,
                before[0],
                context.ready,
                context.after,
                context.scope.snapshot(context.calendar),
                context.scope.snapshot(context.sampled),
                context.p.dt,
                tuple(context.iterations),
                before[2],
                context.after[2],
                tuple(context.rng_calls),
                tuple(context.work),
                tuple(context.c_calls),
                tuple(
                    (row["sequence"], row["call"], row["status"]) for row in context.metadata_work
                ),
                tuple(context.raw_returns),
                tuple(context.exceptions),
                True,
                True,
                True,
                True,
                "",
            )
            context.trial = replace(value, identity=_digest(record_document(value)))
            context.sealed_identity = context.trial.identity
        except BaseException as error:
            context.invalid = True
            context.primary = context.source_error if context.source_error is not None else error
            _FAILED.append(context)
            rejected = SimRunRejected(
                "Original SIM failed/refused", stage=context.phase_stage, partial=context
            )
            raise rejected from context.primary
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
        owner = object.__new__(SimRunOwner)
        context.owner = owner
        _ISSUED[owner] = context
        return owner


class SimRunOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only complete actual native SIM preparation issues this owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live complete SIM authority cannot be hydrated")

    @property
    def trial(self):
        return validate_sim(self)


def _validate_retained(context):
    """One bounded operation, with exact work for every fresh cache validation.

    This is ledger compaction, not a reused validation result. Every occurrence
    (including repeated aliases) still reaches the original validator on every
    public authority check. A sweep has at most 9 + 3*512 caches. Source/C-call
    caps and the metadata operation-record cap remain unchanged; nested calls,
    raw failed cache and absolute attempted-work index are retained separately.
    """
    if context.retained_validation_active:
        _fail(context, "Reentrant retained-cache validation", "retained_validation")
    if context.entry_error is not None:
        raise context.entry_error
    context.retained_validation_active = True
    try:
        return _retained_validation_sweep(context)
    finally:
        context.retained_validation_active = False


def _retained_validation_sweep(context):
    count = _count(len(context.trial.iterations))
    if context.entry_error is not None:
        raise context.entry_error
    if (
        type(context.trial.rng_before) is not tuple
        or type(context.trial.rng_after) is not tuple
        or len(context.trial.rng_before) != 2
        or len(context.trial.rng_after) != 2
        or any(type(row.rng) is not tuple or len(row.rng) != 2 for row in context.trial.iterations)
    ):
        raise ValueError("Both complete RNG caches required at every retained boundary")
    caches = (
        context.trial.before,
        context.trial.ready[0],
        context.trial.after[0],
        context.trial.calendar,
        context.trial.sampled,
        *context.trial.rng_before,
        *context.trial.rng_after,
        *(row.after for row in context.trial.iterations),
        *(value for row in context.trial.iterations for value in row.rng),
    )
    if len(caches) != 9 + 3 * count:
        raise ValueError("Complete fixed/iteration retained-cache roster required")
    row = dict(
        sequence=len(context.retained_validation_work),
        metadata_sequence=len(context.metadata_work) - 1,
        attempt_start=context.retained_validation_attempts,
        expected=len(caches),
        attempted=0,
        returned=0,
        status="entered",
        failure_index=None,
        failure_cache=None,
        primary=None,
    )
    context.retained_validation_work.append(row)
    if context.entry_error is not None:
        row["status"], row["primary"] = "failed", context.entry_error
        raise context.entry_error
    for index, cache in enumerate(caches):
        absolute = context.retained_validation_attempts
        context.last_retained_validation = (row, absolute, index, cache)
        row["attempted"] += 1
        context.retained_validation_attempts += 1
        try:
            previous.terminal.retained_cache.validate(cache)
            row["returned"] += 1
            context.retained_validation_returns += 1
            if context.entry_error is not None:
                raise context.entry_error
        except BaseException as error:
            # Preserve the exact live input/error before fallible recovery
            # or a caller's evidence writer. No success row is fabricated.
            context.last_retained_validation = (row, absolute, index, cache, error)
            row["failure_index"], row["failure_cache"], row["primary"] = index, cache, error
            row["status"] = "failed"
            raise
    row["status"] = "returned"


def _retained_validation_document(context):
    """Exact completed/current work counts; no mutable ledger rows are exposed."""
    return dict(
        attempted=context.retained_validation_attempts,
        returned=context.retained_validation_returns,
        sweeps=tuple(
            (
                row["sequence"],
                row["metadata_sequence"],
                row["attempt_start"],
                row["expected"],
                row["attempted"],
                row["returned"],
                row["status"],
                row["failure_index"],
            )
            for row in context.retained_validation_work
        ),
        fresh_validation_of_every_occurrence=True,
        capacity_or_scientific_admission=False,
    )


def _authority(owner):
    if type(owner) is not SimRunOwner or owner not in _ISSUED:
        raise SimRunRejected("Actual issued complete SIM owner required", stage="owner")
    context = _ISSUED[owner]
    if context.owner is not owner or context.active or context.invalid:
        raise SimRunRejected("Original closed SIM owner changed", stage="owner", partial=context)
    _links(context)
    _bindings(context)
    if context.trial.identity != context.sealed_identity or context.trial.identity != _digest(
        record_document(context.trial)
    ):
        raise ValueError("Original complete SIM trial changed")
    if (
        _metadata(context, "closed_SIM_original_stable_state_validation", _stable, context).identity
        != context.stable.identity
    ):
        raise ValueError("Original closed SIM geometry/parameter/phase state changed")
    _metadata(
        context,
        "closed_SIM_complete_retained_cache_validation",
        _validate_retained,
        context,
    )
    current = _metadata(
        context, "actual_closed_SIM_live_value_graph_RNG_verification", _snapshot, context
    )
    if current[0].identity != context.after[0].identity:
        raise ValueError("Actual retained SIM values changed")
    _same(current[1][0], context.after[1][0])
    if current[1][1] != context.after[1][1] or tuple(v.identity for v in current[2]) != (
        tuple(v.identity for v in context.after[2])
    ):
        raise ValueError("Actual retained SIM graph/layout/aliases/RNG changed")
    return context


def validate_sim(owner):
    """Identical authenticated full-loop trial; no storage/physical acceptance."""
    return _authority(owner).trial


def completed_sim(owner):
    """Live source comparison surface, distinct from serialized parent admission."""
    context = _authority(owner)
    objects, field_objects = _observation_roster(context)
    return dict(
        owner=owner,
        trial=context.trial,
        phase=context.phase,
        sim=context.sim,
        cells=context.cells,
        old_p=context.old_p,
        current_p=context.p,
        completed_INIT=context.refs[2],
        constructor=context.refs[1],
        callback=context.callback,
        iterations=context.trial.iterations,
        before=context.trial.before,
        after=context.trial.after,
        calendar=context.trial.calendar,
        sampled=context.trial.sampled,
        dt=context.trial.dt,
        operator_mode=context.trial.operator_mode,
        observation_objects=objects,
        observation_field_objects=field_objects,
        source_rng_observations=tuple(context.source_rng_observations),
        retained_cache_validation_work=_retained_validation_document(context),
        before_native_pickle=True,
        native_pickle_or_checkpoint_or_physical_admission=False,
    )
