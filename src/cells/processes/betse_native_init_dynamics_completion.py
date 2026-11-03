"""Held ordinary INIT dynamics tail on one actual retained prelude lineage.

The numerical body is the pinned original tail, including its unconditional
NumPy random call. Tissue participation is one live session, never another
phase/parameter owner. Actual source/runtime/ancestor adoption is still held.

Tissue contract: bind_completion(actual CompletionClaim, *, original_owner);
validate_active/closed(session, *, completion_claim) return the identical
session/evidence; source_members(session); state_roots(session);
wrapper_guard/dispatch(session, *, completion_claim, original, frame and actual
dispatch arguments); observe(session, *, completion_claim, frame, event, arg);
finish(session, *, completion_claim); validate_rng_call(...) -> RngWitness.
The active checker returns the identical claim and authenticates registry and
ancestor edges without recursively reading tissue state. claim.check() and
source dispatch perform the complete state/stream audit. record and failed
context are forensic data; none grants another construction or source epoch.
"""

import ast
import copy
import hashlib
import os
import sys
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, MappingProxyType, MethodType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_dynamics_completion_source as source
from cells.processes import betse_native_init_dynamics_prelude as previous

LAW_ID = "betse_same_actual_INIT_ordinary_dynamics_completion@1"
RELEASE = "CELLS_NATIVE_INIT_DYNAMICS_COMPLETION_RELEASED"
PARENT_SOURCE_SHA256 = None
PARENT_REVIEW_SHA256 = None
TISSUE_SOURCE_SHA256 = None
TISSUE_REVIEW_SHA256 = None
TISSUE_MODULE = "cells.processes.betse_native_init_tissue_dynamics"
PARENT_CLAIM = "_claim_for_init_dynamics_completion"
PARENT_CHECK = "_check_init_dynamics_completion_authority"
NATIVE = previous.NATIVE
SIM_FILE = previous.SIM_FILE
SIM_SHA256 = previous.NATIVE_PINS[SIM_FILE]
MAX_WORK = 100000
MAX_RNG_CALLS = 4096
NUMPY_HELPERS = ("asarray", "copy", "zeros", "ones", "sqrt", "dot")
SIM_STORES = (
    "D_env_base",
    "J_env_x",
    "J_env_y",
    "fluxes_env_x",
    "fluxes_env_y",
    "Dm_base",
    "Dm_scheduled",
    "P_mod",
    "P_base",
    "div_u_osmo",
    "channel_noise_factor",
    "Dm_cells",
    "gj_block",
    "NaKATP_block",
    "CaATP_block",
    "endo_retic",
    "cellso",
    "rho_pump",
    "rho_channel",
    "ko_env",
    "ko_cell",
    "cedl_env",
    "cedl_cell",
    "cedl",
    "sigma",
    "sigma_cell",
    "sigma_env",
    "rho_factor",
    "cgj",
)
TISSUE_API = (
    "bind_completion",
    "validate_active",
    "validate_closed",
    "source_members",
    "state_roots",
    "wrapper_guard",
    "dispatch",
    "finish",
    "validate_rng_call",
    "observe",
)
_REQUESTS, _CONSUMED, _RETIRED, _CLAIMS, _ISSUED = (WeakKeyDictionary() for _ in range(5))
_ACTIVE, _FAILED, _LOCK = [], [], RLock()


class CompletionRejected(ValueError):
    def __init__(self, reason, *, stage, request=None, trial=None, partial=None):
        super().__init__(reason)
        self.stage, self.request, self.trial, self.partial = stage, request, trial, partial


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    prelude_owner: object
    parent_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Actual live prelude lineage cannot be decoded from data")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    after: object
    stream_before: tuple
    stream_after: tuple
    rng_calls: tuple
    work: tuple
    c_calls: tuple
    raw_returns: tuple
    tissue_record: object
    source_completed: bool
    identity: str


def _digest(value):
    return previous._digest(value)


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _native_tree():
    path = NATIVE / SIM_FILE
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != SIM_SHA256:
        raise ValueError("Pinned whole original Simulator module required")
    return ast.parse(path.read_bytes())


def _node():
    full = previous._method(_native_tree(), "Simulator", "init_dynamics")
    if (full.lineno, full.end_lineno, len(full.body)) != (758, 1012, 45):
        raise ValueError("Exact original dynamics source extent required")
    if tuple(ast.unparse(n) for n in full.body[2:4]) != ("cells = phase.cells", "p = phase.p"):
        raise ValueError("Original alias-read statements changed")
    if ast.unparse(full.body[10]) != "phase.dyna.init_profiles(phase)":
        raise ValueError("Original post-prelude boundary changed")
    selected = copy.deepcopy(full)
    selected.body = [*copy.deepcopy(full.body[2:4]), *copy.deepcopy(full.body[10:])]
    proof = previous._method(
        ast.parse(Path(source.__file__).read_bytes()), "InitDynamicsCompletion", "init_dynamics"
    )
    if (
        ast.dump(ast.Module(body=proof.body, type_ignores=[]))
        != ast.dump(ast.Module(body=selected.body, type_ignores=[]))
        or previous._header(proof) != previous._header(full)
        or proof.decorator_list
        or proof.returns is not None
        or proof.type_params
    ):
        raise ValueError("Exact literal tail, alias reads or header changed")
    return selected


def _class_code(module_code, cls, method):
    owner = next(c for c in module_code.co_consts if type(c) is CodeType and c.co_name == cls)
    return next(c for c in owner.co_consts if type(c) is CodeType and c.co_name == method)


def _code():
    # Python3.13 compilation context affects LOAD_ATTR call hints. Compile in
    # the genuine whole-module/class context without executing its module body.
    tree = _native_tree()
    cls = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == "Simulator")
    full = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "init_dynamics")
    cls.body[cls.body.index(full)] = _node()
    compiled = compile(
        ast.fix_missing_locations(tree), str(NATIVE / SIM_FILE), "exec", dont_inherit=True
    )
    return _class_code(compiled, "Simulator", "init_dynamics")


def source_plan():
    node = _node()
    return dict(
        law=LAW_ID,
        source={SIM_FILE: SIM_SHA256},
        extent=(809, 1012),
        original_tail_statements=35,
        original_alias_reads=(778, 779),
        full_module_compile_context=True,
        prefix_replayed=False,
        statement_lines=tuple((n.lineno, n.end_lineno) for n in node.body),
        actual_parent_required="Issued PreludeOwner; same actual INIT phase/p/Cells/sim/handler",
        one_active_claim_through_tissue_profiles_noise_events_and_sealing=True,
        mandatory_channel_rng_even_if_level_zero=True,
        source_order=(
            "init_profiles",
            "environment/material bases",
            "NumPy channel RNG",
            "blocking/disabled optional branches",
            "cellso alias",
            "init_events",
            "screening/conductivity/geometry factors",
            "FAST branch unavailable",
        ),
        simulated_parameter_or_phase_or_world_constructed=False,
        permitted_cell_change="Percent picker shuffles the original cell_i full slice view only",
        rng_owners=(
            "actual continuing NumPy mtrand._rand",
            "actual native shuffle.__self__ stdlib _inst",
        ),
        unavailable=(
            "calcium EndoRetic owner",
            "molecule/GRN fresh or reload owner",
            "pressure/flow/deformation helpers",
            "FAST solver",
        ),
        maximum_work=MAX_WORK,
        maximum_rng_source_calls=MAX_RNG_CALLS,
        parent_source=PARENT_SOURCE_SHA256,
        parent_review=PARENT_REVIEW_SHA256,
        tissue_source=TISSUE_SOURCE_SHA256,
        tissue_review=TISSUE_REVIEW_SHA256,
        parent_hooks=(PARENT_CLAIM, PARENT_CHECK),
        tissue_API=TISSUE_API,
        actual_native_RNG_source_or_reference_release=False,
        time_vector_solver_storage_updateV_pickle_or_completed_INIT_admission=False,
    )


def _ready():
    if not all(
        _pin(value)
        for value in (
            PARENT_SOURCE_SHA256,
            PARENT_REVIEW_SHA256,
            TISSUE_SOURCE_SHA256,
            TISSUE_REVIEW_SHA256,
        )
    ):
        raise CompletionRejected(
            "Reviewed parent/tissue source adoption remains held", stage="unbound"
        )
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PARENT_SOURCE_SHA256:
        raise CompletionRejected("Original prelude producer changed", stage="parent_source")
    for name in (PARENT_CLAIM, PARENT_CHECK):
        function = vars(previous).get(name)
        if type(function) is not FunctionType or function.__globals__ is not vars(previous):
            raise CompletionRejected(
                "Actual prelude retirement/advanced-stream authority unavailable", stage="handoff"
            )
    tissue = sys.modules.get(TISSUE_MODULE)
    if tissue is None:
        raise CompletionRejected(
            "Actual source-backed tissue participant must already be loaded", stage="tissue"
        )
    if (
        Path(tissue.__file__).is_symlink()
        or hashlib.sha256(Path(tissue.__file__).read_bytes()).hexdigest() != TISSUE_SOURCE_SHA256
    ):
        raise CompletionRejected(
            "Original tissue participant producer changed", stage="tissue_source"
        )
    for name in TISSUE_API:
        function = vars(tissue).get(name)
        if type(function) is not FunctionType or function.__globals__ is not vars(tissue):
            raise CompletionRejected(
                "Exact declared tissue API required: " + name, stage="tissue_API"
            )
    return tissue


def request_record(value):
    return dict(law=LAW_ID, parent=value.parent_identity, source=value.source_identity)


def _domain(parent):
    p, phase = parent.p, parent.phase
    if phase.kind.name != "INIT" or p._run_sim is not False or p.is_ecm is not True:
        raise CompletionRejected("Actual ordinary normal-ECM INIT phase required", stage="domain")
    requested = []
    if p.ions_dict["Ca"] == 1 and p.Ca_dyn:
        requested.append((857, "EndoRetic"))
    for name, line in (
        ("molecules_enabled", 866),
        ("grn_enabled", 884),
        ("deform_osmo", 902),
        ("fluid_flow", 907),
        ("deformation", 927),
    ):
        if getattr(p, name):
            requested.append((line, name))
    namespace = parent.original_globals
    solver_type = namespace["SolverType"]
    if p.solver_type is not solver_type.FULL:
        requested.append((1011, "FAST or unknown solver"))
    if requested:
        raise CompletionRejected(
            "Genuine optional owners unavailable: " + repr(requested), stage="unavailable_branch"
        )


def from_prelude(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise CompletionRejected("Exact completion law required", stage="law")
    _ready()
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant completion declaration")
        if type(owner) is not previous.PreludeOwner or owner in _RETIRED:
            raise CompletionRejected("Actual unconsumed PreludeOwner required", stage="owner")
        parent = previous._authority(owner)
        _domain(parent)
        value = Request(owner, parent.trial.identity, _digest(source_plan()), "")
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (
            parent,
            parent.trial,
            previous._snapshot(parent),
            previous._graph(parent),
        )
        return value


class CompletionClaim:
    """One actual active participation capability; data/records grant none."""

    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only actual completion preparation issues a claim")

    def __reduce_ex__(self, protocol):
        raise TypeError("Actual active completion cannot be decoded or replayed")

    @property
    def parameters(self):
        context = _active(self)
        _check(context)
        return context.p

    @property
    def phase(self):
        context = _active(self)
        _check(context)
        return context.phase

    def check(self):
        _check(_active(self))

    @property
    def record(self):
        context = _CLAIMS.get(self)
        if context is None or context.active or context.invalid or context.trial is None:
            raise CompletionRejected("No successful closed completion record", stage="record")
        return context.trial


def validate_active(claim, *, original_owner):
    """Authenticate a live participation edge, without recursive tissue reads.

    Source dispatch and claim.check() perform the complete value/stream audit.
    This registry/ancestor surface is safe for a tissue validator called FROM
    that audit; it neither executes source work nor grants an extra epoch.
    """
    context = _active(claim)
    if context.request.prelude_owner is not original_owner:
        _reject(context, "Different original prelude owner")
    return claim


def _active(claim):
    if type(claim) is not CompletionClaim or claim not in _CLAIMS:
        raise CompletionRejected("Actual issued active CompletionClaim required", stage="claim")
    context = _CLAIMS[claim]
    _guard(context)
    _registry(context)
    return context


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = CompletionRejected(
            reason, stage=context.stage, request=context.request, partial=context
        )
    raise context.entry_error


def _guard(context):
    return context.observer_namespace["_guard"](context)


def _scope(context):
    return previous._scope(context.parent)


def _objects(context):
    objects = list(context.init_parent.objects)
    if context.parent.gap is not None:
        objects.append(("gap_dynamics", context.parent.gap))
    if context.tissue_session is not None:
        for role, value in context.tissue.state_roots(context.tissue_session):
            if not any(value is actual for _, actual in objects):
                objects.append((role, value))
    return objects


def _values(context, *, stable=False):
    projector = previous.previous._projector(context.init_parent)
    projector.objects = [*projector.objects, *_objects(context)]
    project = previous.previous.core._LITERAL._project
    sim = {k: v for k, v in vars(context.sim).items() if not stable or k not in SIM_STORES}
    cells = {k: v for k, v in vars(context.cells).items() if not stable or k != "cell_i"}
    return dict(
        simulator=project(projector, sim),
        cells=project(projector, cells),
        parameters=project(projector, vars(context.p)),
        objects=tuple(
            (role, project(projector, vars(actual)))
            for role, actual in _objects(context)
            if not stable or all(actual is not item for item in (context.sim, context.phase.dyna))
        ),
        handler=None if stable else project(projector, vars(context.phase.dyna)),
    )


def _snapshot(context, *, stable=False):
    return _scope(context).snapshot(_values(context, stable=stable))


def _graph(context):
    context.graph_fields[:] = [vars(value) for _, value in _objects(context)]
    return _scope(context).graph(context.graph_view, context.graph_view, context.graph_tape)


def _streams(context):
    if (
        context.numpy.random.mtrand._rand is not context.np_rng
        or context.numpy.random.random.__self__ is not context.np_rng
        or context.stdlib._inst is not context.std_rng
        or context.shuffle.__self__ is not context.std_rng
    ):
        raise ValueError("Actual NumPy/stdlib RNG instance association changed")
    first = previous.previous._rng(context.init_parent)
    second = _scope(context).snapshot(context.std_getstate())
    return first, second


def _epoch(context):
    return (
        _snapshot(context).identity,
        _graph(context),
        tuple(v.identity for v in _streams(context)),
    )


def _cell_snapshot(context):
    if context.cells.cell_i is not context.cell_i:
        raise ValueError("Original cell_i array object replaced")
    return _scope(context).snapshot(context.cell_i)


def _same_refs(actual, expected):
    previous.previous.core.previous._same(actual, expected)


def _binding(context):
    functions = (
        context.parent_claim,
        context.parent_check,
        *context.methods.values(),
        *context.source_functions,
        *context.helper_functions,
        context.np_random,
        context.shuffle,
        context.std_getstate,
    )
    values = [
        context.parent,
        context.parent_trial,
        context.phase,
        context.p,
        context.cells,
        context.sim,
        context.callback,
        context.claim,
        context.tissue,
        context.tissue_session,
        context.np_rng,
        context.std_rng,
        context.np_random,
        context.shuffle,
        context.entries,
        context.namespace,
        context.observer_namespace,
    ]
    for function in functions:
        values.extend(previous.previous._atoms(function))
    for name in TISSUE_API:
        values.extend(previous.previous._atoms(vars(context.tissue)[name]))
    values.extend(
        previous.previous.core._resolved_bindings(
            tuple(f for f in functions if type(f) is FunctionType)
        )
    )
    values.extend((context.numpy, *(getattr(context.numpy, n) for n in NUMPY_HELPERS)))
    return tuple(values)


def _registry(context):
    if (
        _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.prelude_owner) is not context
        or _CLAIMS.get(context.claim) is not context
        or _REQUESTS.get(context.request) is not context.refs
        or context.parent is not context.refs[0]
        or context.parent.trial is not context.refs[1]
        or context.parent_check(context) is not context.parent
        or context.phase is not context.parent.phase
        or context.phase.p is not context.p
        or context.phase.sim is not context.sim
        or context.phase.cells is not context.cells
        or context.phase.dyna is not context.handler
        or context.phase.callbacks is not context.callback
        or context.invalid
        or context.thread != get_ident()
        or context.request.identity != _digest(request_record(context.request))
        or context.request.source_identity != _digest(source_plan())
    ):
        raise ValueError("Original one-shot completion/Prelude/phase/source association changed")


def _check(context, *, closed=False):
    if not closed:
        _guard(context)
    _registry(context)
    if context.bindings is not None:
        _same_refs(_binding(context), context.bindings)
    if (
        context.stable is not None
        and _snapshot(context, stable=True).identity != context.stable.identity
    ):
        raise ValueError("Unowned parameter/geometry/Simulator field changed")
    if context.draw_active is None and tuple(v.identity for v in _streams(context)) != tuple(
        v.identity for v in context.current_streams
    ):
        raise ValueError("Unobserved NumPy or stdlib RNG advancement")
    if _cell_snapshot(context).identity != context.current_cell_i.identity:
        raise ValueError("Unwitnessed cell_i buffer mutation")
    if not closed and context.tissue_session is not None:
        if (
            context.tissue.validate_active(context.tissue_session, completion_claim=context.claim)
            is not context.tissue_session
        ):
            raise ValueError("Different actual active tissue participation")


def _capture(context, origin, error, raw):
    return context.observer_namespace["_record_capture"](context, origin, error, raw)


def _helper(context, name, delegate, args, kwargs, frame):
    _check(context)
    if frame is not context.body_frame or frame.f_globals is not context.namespace:
        _reject(context, "Numerical/copy helper must be reached by the actual original tail")
    row = dict(
        name=name,
        delegate=delegate,
        args=args,
        kwargs=kwargs,
        frame=frame,
        returned=False,
        raw_return=None,
        error=None,
    )
    context.last_helper = row
    context.helper_calls.append(row)
    if len(context.work) + len(context.helper_calls) > MAX_WORK:
        _reject(context, "Bounded actual helper work exhausted")
    try:
        value = delegate(*args, **kwargs)
        row["raw_return"] = context.last_helper_return = value
        row["returned"] = True
        return value
    except BaseException as error:
        row["error"] = error
        if context.primary is None:
            context.primary = error
        raise


def rng_call(claim, *, participant, library, operation, delegate, args, kwargs, source_frame):
    """Invoke an actual original source-issued RNG delegate exactly once.

    Tissue calls need the actual typed participant and its original-frame
    witness. Tail random(mdl) has a distinct direct source-frame check. Neither
    an equal array nor a supplied RNG/state/receipt grants permission.
    """
    context = _active(claim)
    _check(context)
    if context.draw_active is not None or len(context.rng_calls) >= MAX_RNG_CALLS:
        _reject(context, "One active bounded original RNG source call required")
    if type(args) is not tuple or type(kwargs) is not dict:
        _reject(context, "Original actual RNG call argument containers required")
    view = None
    if participant is None:
        if (
            library != "numpy"
            or operation != "random"
            or delegate is not context.np_random
            or source_frame is not context.body_frame
            or source_frame.f_globals is not context.namespace
            or len(args) != 1
            or args[0] is not context.sim.mdl
            or kwargs
        ):
            _reject(context, "Exact unconditional native random(mdl) call required")
        context.channel_random_attempts += 1
        if context.channel_random_attempts != 1:
            _reject(context, "Duplicate native channel RNG call")
    else:
        if participant is not context.tissue_session:
            _reject(context, "Foreign tissue RNG participation")
        witness = context.tissue.validate_rng_call(
            participant,
            completion_claim=claim,
            library=library,
            operation=operation,
            delegate=delegate,
            args=args,
            kwargs=kwargs,
            source_frame=source_frame,
        )
        if (
            type(witness) is not context.tissue.RngWitness
            or witness.source_frame is not source_frame
        ):
            _reject(context, "Actual source-backed immutable tissue RNG witness required")
        if library == "numpy" and operation in ("shuffle", "choice"):
            if delegate.__self__ is not context.np_rng:
                _reject(context, "Original continuing NumPy shuffle owner required")
        elif library == "stdlib" and operation == "shuffle":
            if (
                delegate.__self__ is not context.std_rng
                or delegate.__func__ is not context.shuffle.__func__
            ):
                _reject(context, "Original native stdlib shuffle owner/function required")
        else:
            _reject(context, "Unowned RNG source operation")
        if witness.cell_i_view is not None:
            view = witness.cell_i_view
            if (
                library != "numpy"
                or operation != "shuffle"
                or len(args) != 1
                or args[0] is not view
                or source_frame.f_locals.get("cell_i_copy") is not view
                or type(view) is not context.numpy.ndarray
                or view.shape != context.cell_i.shape
                or view.dtype != context.cell_i.dtype
                or view.strides != context.cell_i.strides
                or view.ctypes.data != context.cell_i.ctypes.data
            ):
                _reject(context, "Actual original percent-picker full slice view required")
    row = SimpleNamespace(
        index=len(context.rng_calls),
        library=library,
        operation=operation,
        delegate=delegate,
        args=args,
        kwargs=kwargs,
        source_frame=source_frame,
        participant=participant,
        before=_streams(context),
        after=None,
        cell_before=_cell_snapshot(context),
        returned=False,
        raw_return=None,
        primary=None,
        capture_errors=(),
    )
    context.last_rng = context.draw_active = row
    context.rng_calls.append(row)
    before_items = (
        Counter(item.tobytes() for item in context.cell_i.flat) if view is not None else None
    )
    primary = None
    try:
        returned = delegate(*args, **kwargs)
        row.raw_return = context.last_rng_return = returned
        row.returned = True
    except BaseException as error:
        row.primary = primary = error
        if context.primary is None:
            context.primary = error
    finally:
        try:
            row.after = _streams(context)
            context.current_streams = row.after
        except BaseException as error:
            row.capture_errors += (("stream_after", error),)
            _capture(context, "rng_after", error, row)
        try:
            if view is not None:
                if Counter(item.tobytes() for item in context.cell_i.flat) != before_items:
                    raise ValueError("Original shuffle changed cell index membership/bits")
                context.current_cell_i = _cell_snapshot(context)
            elif _cell_snapshot(context).identity != row.cell_before.identity:
                raise ValueError("A non-percent RNG call changed cell_i")
        except BaseException as error:
            row.capture_errors += (("cell_i_after", error),)
            _capture(context, "rng_cell_i", error, row)
        context.draw_active = None
    if primary is not None:
        raise primary
    _check(context)
    return row.raw_return


def _wrapper_guard(context, original, frame):
    _check(context)
    if original is not context.init_parent:
        _reject(context, "Original retained INIT constructor context required")
    return context.tissue.wrapper_guard(
        context.tissue_session, completion_claim=context.claim, original=original, frame=frame
    )


def _dispatch(context, original, label, delegate, actual, args, kwargs, frame):
    _check(context)
    if original is not context.init_parent:
        _reject(context, "Actual same-INIT source context required")
    return context.tissue.dispatch(
        context.tissue_session,
        completion_claim=context.claim,
        original=original,
        label=label,
        delegate=delegate,
        actual=actual,
        args=args,
        kwargs=kwargs,
        frame=frame,
    )


def _namespace(context):
    native = context.init_parent.factories["Simulator"]
    callbacks = previous.previous.caches.previous.callbacks
    original = callbacks._source_function(
        native.init_dynamics, SIM_FILE, "init_dynamics", "Simulator"
    )
    globals_before = original.__globals__
    context.source_functions = (original,)
    context.numpy = globals_before["np"]
    context.np_rng = context.numpy.random.mtrand._rand
    if context.init_parent.parent.rng is not context.np_rng:
        raise ValueError("Actual source NumPy RNG does not continue the retained world")
    context.np_random = context.numpy.random.random
    tissue_module = sys.modules.get("betse.science.tissue.tishandler")
    if tissue_module is None:
        raise ValueError("Original actually loaded TissueHandler module required")
    context.shuffle = vars(tissue_module)["shuffle"]
    context.stdlib = sys.modules.get("random")
    if (
        context.stdlib is None
        or type(context.shuffle) is not MethodType
        or context.shuffle.__self__ is not context.stdlib._inst
    ):
        raise ValueError("Original native stdlib global shuffle instance required")
    context.std_rng = context.shuffle.__self__
    context.std_getstate = context.std_rng.getstate
    helpers = {name: getattr(context.numpy, name) for name in NUMPY_HELPERS}
    helpers.update(
        gaussian_filter=globals_before["gaussian_filter"], python_copy=globals_before["copy"].copy
    )
    context.original_helpers = MappingProxyType(helpers)
    wrappers = {}
    for name, delegate in helpers.items():

        def wrapped(*args, _name=name, _delegate=delegate, **kwargs):
            return _helper(context, _name, _delegate, args, kwargs, sys._getframe(1))

        wrappers[name] = wrapped

    def random(size):
        return rng_call(
            context.claim,
            participant=None,
            library="numpy",
            operation="random",
            delegate=context.np_random,
            args=(size,),
            kwargs={},
            source_frame=sys._getframe(1),
        )

    def unavailable(*args, **kwargs):
        _reject(context, "Unowned optional native factory/helper attempted entry")

    namespace = dict(
        globals_before,
        np=SimpleNamespace(
            **{name: wrappers[name] for name in NUMPY_HELPERS},
            random=SimpleNamespace(random=random),
        ),
        copy=SimpleNamespace(copy=wrappers["python_copy"], deepcopy=unavailable),
        gaussian_filter=wrappers["gaussian_filter"],
        EndoRetic=unavailable,
        MasterOfMolecules=unavailable,
        MasterOfGenes=unavailable,
    )
    context.namespace = namespace
    context.methods = {"init_dynamics": FunctionType(_code(), namespace, "init_dynamics")}
    context.expected_body = context.methods["init_dynamics"].__code__
    context.helper_functions = previous.previous.core.previous.previous._native_helper_functions(
        tuple(helpers.values())
    )
    context.allowed_codes = frozenset(
        code
        for fn in (*context.methods.values(), *context.helper_functions)
        for code in previous.previous._code_tree(fn.__code__)
    )


def _observe(context, frame, event, arg):
    # A directly retained raw return/exception precedes the participant's
    # fallible locals copy. Its observer precedes every inherited callback.
    if event == "exception":
        context.pending[id(frame)] = arg[1]
    if event == "return" and any(frame.f_code is code for code in context.allowed_codes):
        context.observer_namespace["_witness"](context, frame, arg)
    if context.tissue_session is not None and any(
        frame.f_code is code for code in context.tissue_codes
    ):
        context.tissue.observe(
            context.tissue_session,
            completion_claim=context.claim,
            frame=frame,
            event=event,
            arg=arg,
        )
    if event == "call":
        selected = any(frame.f_code is code for code in context.allowed_codes)
        native = frame.f_code.co_filename.startswith(str(NATIVE) + os.sep)
        if not selected and not native:
            return
        attempt = dict(
            frame=frame,
            code=frame.f_code,
            globals=frame.f_globals,
            function=frame.f_code.co_qualname,
            returned=False,
            body_started=False,
        )
        context.last_attempt = attempt
        context.work.append(attempt)
        _check(context)
        if not selected or len(context.work) + len(context.helper_calls) > MAX_WORK:
            _reject(context, "Unknown/later source entry or work bound exhausted")
        if frame.f_code is context.expected_body:
            if (
                context.body_frame is not None
                or frame.f_back is not context.driver_frame
                or frame.f_globals is not context.namespace
                or frame.f_locals.get("self") is not context.sim
                or frame.f_locals.get("phase") is not context.phase
            ):
                _reject(context, "Actual original tail driver/receiver/phase required")
            context.body_frame = frame
        else:
            ancestor = frame.f_back
            while ancestor is not None and ancestor is not context.body_frame:
                ancestor = ancestor.f_back
            if ancestor is None or context.body_frame is None:
                _reject(context, "Actual selected helper is detached from original tail")
        context.frames[id(frame)] = attempt
        attempt["body_started"] = True
    row = context.frames.get(id(frame))
    if row is None:
        return
    if row["frame"] is not frame or row["globals"] is not frame.f_globals:
        _reject(context, "Original admitted source frame/namespace changed")
    if event == "exception":
        context.pending[id(frame)] = arg[1]
    if event == "line":
        _check(context)
    if event == "return":
        context.observer_namespace["_witness"](context, frame, arg)
        try:
            context.raw_returns.append(context.last_raw)
            context.locals[id(frame)] = dict(frame.f_locals)
        except BaseException as error:
            _capture(context, "source_return", error, context.last_raw)
        row["returned"] = True
        if frame is context.body_frame and previous.previous._normal_return(frame):
            context.body_returned, context.body_return = True, arg


def _observer_recipe(context):
    # Reuse exact prelude observation code in an owned private namespace. The
    # only declared substitutions are this tail's checker/snapshot/admission.
    namespace = dict(
        vars(previous),
        previous=previous.previous,
        DynamicsRejected=CompletionRejected,
        _check=_check,
        _reject=_reject,
        _observe=_observe,
        _epoch=_epoch,
        MAX_WORK=MAX_WORK,
        _ACTIVE=_ACTIVE,
    )
    for name in (
        "_record_capture",
        "_guard",
        "_witness",
        "_delegate",
        "_same_epoch",
        "_inherited",
        "_recover_hooks",
    ):
        fn = vars(previous)[name]
        namespace[name] = FunctionType(
            fn.__code__, namespace, name, fn.__defaults__, fn.__closure__
        )
    inherited = namespace["_inherited"]

    def inherited_with_rng_guard(current, observer, frame, event, arg):
        owner = getattr(arg, "__self__", None) if event == "c_call" else None
        sampling = event == "c_call" and getattr(arg, "__name__", None) in ("get_state", "getstate")
        if (owner is current.np_rng or owner is current.std_rng) and not sampling:
            if current.draw_active is None:
                _reject(current, "Unwitnessed call on an owned global RNG")
            row = current.draw_active
            expected_owner = current.np_rng if row.library == "numpy" else current.std_rng
            if owner is not expected_owner:
                _reject(current, "RNG call changed actual source stream")
        return inherited(current, observer, frame, event, arg)

    namespace["_inherited"] = inherited_with_rng_guard
    original = previous._account.__wrapped__
    account = FunctionType(
        original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__
    )
    context.observer_namespace = namespace
    context.account = contextmanager(account)


def _context(request, refs, parent, tissue):
    init = parent.parent
    value = SimpleNamespace(
        request=request,
        refs=refs,
        parent=parent,
        parent_trial=refs[1],
        init_parent=init,
        phase=parent.phase,
        p=parent.p,
        cells=parent.cells,
        sim=parent.sim,
        handler=parent.phase.dyna,
        callback=parent.callback,
        tissue=tissue,
        tissue_session=None,
        tissue_record=None,
        tissue_functions=(),
        tissue_codes=frozenset(),
        claim=None,
        bindings=None,
        stable=None,
        stage="parent_retirement",
        thread=get_ident(),
        active=True,
        invalid=False,
        validating=False,
        primary=None,
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        cleanup_errors=(),
        last_capture=None,
        reporting_failure=None,
        observing=False,
        inherited=False,
        work=[],
        frames={},
        pending={},
        raw_returns=[],
        locals={},
        c_calls=[],
        helper_calls=[],
        rng_calls=[],
        draw_active=None,
        last_rng=None,
        last_rng_return=None,
        channel_random_attempts=0,
        body_frame=None,
        body_returned=False,
        body_return=None,
        trial=None,
        before=None,
        after=None,
        after_graph=None,
        graph_fields=[],
        required_hooks=(sys.getprofile(), sys.gettrace()),
        setters=(sys.setprofile, sys.settrace),
        getters=(sys.getprofile, sys.gettrace),
        call_tracing=sys.call_tracing,
        hooks_safe=True,
        last_raw=None,
        cell_i=parent.cells.cell_i,
    )
    value.graph_view = SimpleNamespace(
        fields=value.graph_fields,
        parameters=vars(value.p),
        cells=vars(value.cells),
        source_work=value.work,
        rng_records=value.rng_calls,
    )
    value.graph_tape = SimpleNamespace(
        rng=init.graph_tape.rng, events=value.raw_returns, draws=value.c_calls, locals=value.locals
    )
    return value


def _run(context):
    context.driver_frame = sys._getframe()
    return context.methods["init_dynamics"](context.sim, context.phase)


def _finish(context):
    if (
        not context.body_returned
        or context.body_return is not None
        or context.primary is not None
        or context.capture_error is not None
        or context.cleanup_errors
        or context.draw_active is not None
        or context.channel_random_attempts != 1
        or any(not row["returned"] for row in context.work)
    ):
        raise ValueError("Complete original tail, mandatory RNG and observations required")
    context.tissue_record = context.tissue.finish(
        context.tissue_session, completion_claim=context.claim
    )
    if context.tissue_record is None:
        raise ValueError("Actual successful tissue participation record required")
    _check(context)


def _rng_record(row):
    return dict(
        index=row.index,
        library=row.library,
        operation=row.operation,
        source_frame=id(row.source_frame),
        delegate=id(row.delegate),
        before=tuple(v.identity for v in row.before),
        after=None if row.after is None else tuple(v.identity for v in row.after),
        returned=row.returned,
        raw_return=id(row.raw_return),
        primary=None if row.primary is None else id(row.primary),
        metadata_capture_complete=not row.capture_errors,
        independent_case=False,
    )


def trial_record(value):
    return dict(
        request=value.request_identity,
        parent=value.parent_identity,
        before=value.before.identity,
        after=value.after.identity,
        stream_before=tuple(v.identity for v in value.stream_before),
        stream_after=tuple(v.identity for v in value.stream_after),
        rng_calls=tuple(_rng_record(row) for row in value.rng_calls),
        work=tuple(
            (row["code"].co_filename, row["function"], id(row["frame"]), row["returned"])
            for row in value.work
        ),
        c_calls=tuple((id(frame), event, id(delegate)) for frame, event, delegate in value.c_calls),
        raw_returns=tuple((id(frame), id(raw)) for frame, raw in value.raw_returns),
        tissue_record=id(value.tissue_record),
        tail_source_completed=value.source_completed,
        whole_init_dynamics_source_equivalence="Same state; split original-body projections",
        timesteps_completed=0,
        completed_INIT_or_independent_case=False,
    )


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise CompletionRejected("Actual source/RNG completion remains held", stage="release")
    tissue = _ready()
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant completion preparation")
        if type(request) is not Request or request not in _REQUESTS:
            raise CompletionRejected(
                "Actual issued process-local Request required", stage="request"
            )
        if request in _CONSUMED or request.prelude_owner in _RETIRED:
            raise CompletionRejected("Original prelude epoch already attempted", stage="consumed")
        refs = _REQUESTS[request]
        parent = previous._authority(request.prelude_owner)
        _domain(parent)
        graph = previous._graph(parent)
        _same_refs(graph[0], refs[3][0])
        if (
            parent is not refs[0]
            or parent.trial is not refs[1]
            or previous._snapshot(parent).identity != refs[2].identity
            or graph[1] != refs[3][1]
            or request.identity != _digest(request_record(request))
            or request.source_identity != _digest(source_plan())
        ):
            raise CompletionRejected("Original closed prelude source/state changed", stage="parent")
        context = _context(request, refs, parent, tissue)
        claim = object.__new__(CompletionClaim)
        context.claim = claim
        _CLAIMS[claim] = _CONSUMED[request] = _RETIRED[request.prelude_owner] = context
        _ACTIVE.append(context)
        primary = None
        try:
            context.parent_claim, context.parent_check = (
                getattr(previous, PARENT_CLAIM),
                getattr(previous, PARENT_CHECK),
            )
            context.entries = MappingProxyType(
                dict(
                    wrapper_guard=_wrapper_guard,
                    dispatch=_dispatch,
                    validate_active=validate_active,
                    rng_call=rng_call,
                )
            )
            context.parent_claim(
                request.prelude_owner, expected=refs[1], transition=context, entries=context.entries
            )
            _observer_recipe(context)
            _namespace(context)
            context.current_streams = context.stream_before = _streams(context)
            context.current_cell_i = _cell_snapshot(context)
            context.stage = "tissue_source_binding"
            context.tissue_session = tissue.bind_completion(
                claim, original_owner=request.prelude_owner
            )
            if context.tissue_session is None:
                raise ValueError("Actual typed source-backed tissue session required")
            context.tissue_functions = tissue.source_members(context.tissue_session)
            if type(context.tissue_functions) is not tuple or any(
                type(fn) is not FunctionType for fn in context.tissue_functions
            ):
                raise ValueError("Bound actual tissue original function roster required")
            context.allowed_codes = frozenset(
                (
                    *context.allowed_codes,
                    *(
                        code
                        for fn in context.tissue_functions
                        for code in previous.previous._code_tree(fn.__code__)
                    ),
                )
            )
            context.tissue_codes = frozenset(
                code
                for fn in context.tissue_functions
                for code in previous.previous._code_tree(fn.__code__)
            )
            context.bindings = _binding(context)
            context.before = _snapshot(context)
            context.stable = _snapshot(context, stable=True)
            context.stage = "actual_original_INIT_dynamics_tail"
            with context.account(context):
                context.raw_tail_return = _run(context)
            _finish(context)
            context.after = _snapshot(context)
            context.after_graph = _graph(context)
            streams_after = _streams(context)
            record = Trial(
                request.identity,
                request.parent_identity,
                context.before,
                context.after,
                context.stream_before,
                streams_after,
                tuple(context.rng_calls),
                tuple(context.work),
                tuple(context.c_calls),
                tuple(context.raw_returns),
                context.tissue_record,
                True,
                "",
            )
            context.trial = replace(record, identity=_digest(trial_record(record)))
        except BaseException as error:
            primary = context.primary if context.primary is not None else error
            context.primary, context.invalid = primary, True
            _FAILED.append(context)
            try:
                primary.init_dynamics_completion_partial = context
                primary.completion_claim = claim
            except BaseException as secondary:
                context.cleanup_errors += (("attachment", secondary, primary),)
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
            # Independent trusted recovery after every fallible source/record
            # callback, preserving original primary/cause and all secondary rows.
            for index in (1, 0):
                try:
                    context.setters[index](context.required_hooks[index])
                except BaseException as error:
                    context.cleanup_errors += (("terminal_restore", error, index),)
            samples = []
            for order in ((0, 1), (1, 0)):
                pair = [None, None]
                for index in order:
                    try:
                        pair[index] = context.getters[index]()
                    except BaseException as error:
                        context.cleanup_errors += (("terminal_sample", error, index),)
                samples.append(tuple(pair))
            context.final_hooks = tuple(samples)
            context.hooks_safe = all(
                a is context.required_hooks[0] and b is context.required_hooks[1]
                for a, b in samples
            )
        if primary is not None:
            raise primary
        if context.invalid or context.cleanup_errors or not context.hooks_safe:
            context.invalid = True
            _FAILED.append(context)
            raise CompletionRejected(
                "Completion observation/publication refused", stage="closure", partial=context
            )
        owner = object.__new__(DynamicsOwner)
        _ISSUED[owner] = (context, context.trial)
        return owner


class DynamicsOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only actual same-phase completion issues an owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("No native checkpoint or decoded owner authority")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not DynamicsOwner or owner not in _ISSUED:
        raise CompletionRejected("Actual issued DynamicsOwner required", stage="owner")
    context, issued = _ISSUED[owner]
    if context.active or context.invalid or context.validating:
        raise CompletionRejected("Closed completion epoch unavailable", stage="owner")
    context.validating = True
    try:
        _ready()
        _check(context, closed=True)
        if (
            context.tissue.validate_closed(context.tissue_session, completion_claim=context.claim)
            is not context.tissue_record
        ):
            raise ValueError("Original successful tissue participation record changed")
        graph = _graph(context)
        _same_refs(graph[0], context.after_graph[0])
        if (
            graph[1] != context.after_graph[1]
            or _snapshot(context).identity != context.after.identity
            or context.trial is not issued
            or issued.identity != _digest(trial_record(issued))
        ):
            raise ValueError("Closed original tail values/aliases/work/record changed")
        return context
    except BaseException:
        context.invalid = True
        raise
    finally:
        context.validating = False


def failed_context(claim):
    if type(claim) is not CompletionClaim or claim not in _CLAIMS:
        raise CompletionRejected("Actual issued completion claim required", stage="claim")
    context = _CLAIMS[claim]
    if context.active or not context.invalid:
        raise CompletionRejected("No closed failed completion attempt", stage="failure")
    return context
