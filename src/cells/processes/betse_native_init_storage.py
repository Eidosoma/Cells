"""Held literal INIT storage reset on a real issued DynamicsOwner.

This method boundary follows dynamics without claiming the unexecuted enclosing
run_sim_core guard/report or any voltage/time-loop/checkpoint authority.
"""

import ast
import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FrameType, FunctionType, MappingProxyType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_dynamics_completion as previous
from cells.processes import betse_native_init_storage_source as source
from cells.processes import betse_native_world_phase_construction as interfaces

LAW_ID = "betse_actual_INIT_DynamicsOwner_clear_storage@1"
RELEASE = "CELLS_NATIVE_INIT_STORAGE_RELEASED"
PARENT_SOURCE_SHA256 = '3daedf90ed77a6d078239dcb3302c6de6a6f35f5709581e0a01223e7cab338ed'
# Narrow consumer interface/source review, not Root numerical/native release.
PARENT_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
PARENT_CLAIM = "_claim_for_init_storage"
PARENT_CHECK = "_check_init_storage_authority"
PROPOSED_PARENT_CLAIM = "_claim_for_init_storage"
PROPOSED_PARENT_CHECK = "_check_init_storage_authority"
ELECTRICAL_MODULE = "cells.processes.betse_native_init_electrical"
ELECTRICAL_INTERFACE_SHA256 = '4e119406730d987b2f3ba199367412fd14971d465eb89f58fdbc0cee71ea8a3f'
ELECTRICAL_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
ELECTRICAL_PARENT_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
ELECTRICAL_BACK_REFERENCE_SLOTS = ("PARENT_SOURCE_SHA256", "PARENT_REVIEW_SHA256")
ELECTRICAL_BINDING_KIND = "exact_INIT_electrical_bytes_except_two_storage_backrefs@1"
ELECTRICAL_ANCESTOR_CLAIM = '_claim_electrical_ancestor'
ELECTRICAL_ANCESTOR_CHECK = '_check_electrical_ancestor'
FIRST_STEP_ANCESTOR_CLAIM = FIRST_STEP_ANCESTOR_CHECK = None
SHORT_INIT_ANCESTOR_CLAIM = '_claim_short_init_ancestor'
SHORT_INIT_ANCESTOR_CHECK = '_check_short_init_ancestor'
TERMINAL_INIT_ANCESTOR_CLAIM = '_claim_terminal_init_ancestor'
TERMINAL_INIT_ANCESTOR_CHECK = '_check_terminal_init_ancestor'
NATIVE = previous.NATIVE
SIM_FILE = previous.SIM_FILE
MAX_WORK = 100000
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_ACTIVE, _FAILED, _LOCK = [], [], RLock()
_ELECTRICAL_FORWARDED, _ELECTRICAL_LEASES = WeakKeyDictionary(), WeakKeyDictionary()


class StorageRejected(ValueError):
    def __init__(self, reason, *, stage, request=None, trial=None, partial=None):
        super().__init__(reason)
        self.stage, self.request, self.trial, self.partial = stage, request, trial, partial


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    dynamics_owner: object
    parent_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("A live storage request cannot be hydrated")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    after: object
    stream_before: tuple
    stream_after: tuple
    stores: tuple
    work: tuple
    c_calls: tuple
    raw_returns: tuple
    source_completed: bool
    identity: str


@dataclass(frozen=True, slots=True)
class _ElectricalBinding:
    module: object
    ancestor_module: object
    claim: object
    check: object
    atoms: tuple


def _digest(value):
    return previous._digest(value)


def _node():
    path = NATIVE / SIM_FILE
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != source.SIM_SHA256:
        raise ValueError("Exact original Simulator source required")
    tree = ast.parse(path.read_bytes())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Simulator")
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "clear_storage")
    literal = ast.parse(Path(source.__file__).read_bytes())
    owner = next(n for n in literal.body if isinstance(n, ast.ClassDef) and n.name == "InitStorage")
    selected = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == node.name)
    if (node.lineno, node.end_lineno) != (1680, 1786) or ast.dump(
        ast.Module(body=node.body, type_ignores=[])
    ) != ast.dump(ast.Module(body=selected.body, type_ignores=[])):
        raise ValueError("Entire original storage body/order changed")
    return node


def _code():
    _node()
    module = compile(
        (NATIVE / SIM_FILE).read_bytes(), str(NATIVE / SIM_FILE), "exec", dont_inherit=True
    )
    cls = next(c for c in module.co_consts if type(c) is CodeType and c.co_name == "Simulator")
    return next(c for c in cls.co_consts if type(c) is CodeType and c.co_name == "clear_storage")


def _stores():
    # ast.walk breadth ordering is unsuitable here: retain original source order.
    nodes = [n for n in ast.walk(_node()) if isinstance(n, ast.Assign)]
    result = []
    for node in sorted(nodes, key=lambda n: (n.lineno, n.col_offset)):
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                result.append((node.lineno, target.attr))
    if len(result) != 52 or len({name for _, name in result}) != 51:
        raise ValueError("Original 52 stores/51 fields, including duplicate vm_ave_time, required")
    return tuple(result)


def source_plan():
    node = _node()
    reads = tuple(
        sorted(
            {
                n.attr
                for n in ast.walk(node)
                if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name)
                and n.value.id == "p"
            }
        )
    )
    return dict(
        law=LAW_ID,
        source={SIM_FILE: source.SIM_SHA256},
        lines=(1680, 1786),
        stores=_stores(),
        parameter_reads=reads,
        parent_source=PARENT_SOURCE_SHA256,
        parent_review=PARENT_REVIEW_SHA256,
        actual_parent_hooks=(PARENT_CLAIM, PARENT_CHECK),
        proposed_parent_hooks=(PROPOSED_PARENT_CLAIM, PROPOSED_PARENT_CHECK),
        two_unconditional_zeros_and_optional_phi_zeros=True,
        original_vm_ave_time_second_allocation_retained=True,
        optional_delegates=(
            "molecules.core.clear_cache",
            "grn.core.clear_cache",
            "endo_retic.clear_cache",
        ),
        native_Ca_dyn_guard_is_unconditional=True,
        optional_owner_authority_unavailable=True,
        unchanged_constructor_phase_p_cells_mesh_grid_handler_RNG=True,
        unexecuted_report_guard_run_sim_core_not_credited=True,
        stop_before=(
            "update_V",
            "_plot_loop",
            "time vector",
            "progress_ranged",
            "solver loop",
            "pickling",
        ),
        actual_source_RNG_operator_reference_or_scientific_release=False,
        electrical_handoff=dict(
            module=ELECTRICAL_MODULE,
            interface=ELECTRICAL_INTERFACE_SHA256,
            review=ELECTRICAL_REVIEW_SHA256,
            claim="_claim_for_electrical",
            check="_check_electrical_authority",
            original_runtime_method="Simulator.update_V",
            get_current_is_a_module_helper=True,
            inherited_completion_ancestor=ELECTRICAL_ANCESTOR_CLAIM,
            inherited_completion_check=ELECTRICAL_ANCESTOR_CHECK,
            source_derived_sim_fields=27,
            actual_execution_or_admission=False,
        ),
        all11_postcut_owners_and12_cases_held=True,
    )


def _ready():
    if (
        not previous._pin(PARENT_SOURCE_SHA256)
        or not previous._pin(PARENT_REVIEW_SHA256)
        or PARENT_CLAIM != PROPOSED_PARENT_CLAIM
        or PARENT_CHECK != PROPOSED_PARENT_CHECK
    ):
        raise StorageRejected(
            "Reviewed actual DynamicsOwner storage contract unavailable", stage="held"
        )
    path = Path(previous.__file__)
    if path.is_symlink() or not path.is_file():
        raise StorageRejected("Original regular dynamics producer required", stage="producer")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SOURCE_SHA256:
        raise StorageRejected("Original reviewed dynamics producer changed", stage="producer")
    compiled = compile(raw, str(path), "exec", dont_inherit=True)
    codes = {value.co_name: value for value in compiled.co_consts if type(value) is CodeType}
    for name in (PARENT_CLAIM, PARENT_CHECK):
        function = vars(previous).get(name)
        if (
            type(function) is not FunctionType
            or function.__globals__ is not vars(previous)
            or function.__code__ != codes.get(name)
            or function.__code__.co_filename != str(path)
            or function.__name__ != name
            or function.__qualname__ != name
            or function.__closure__ is not None
            or function.__defaults__ is not None
            or function.__kwdefaults__ is not None
        ):
            raise StorageRejected(
                "Actual one-shot storage ownership hook unavailable", stage="hook"
            )
    return previous


def request_record(value):
    return dict(law=LAW_ID, parent=value.parent_identity, source=value.source_identity)


def from_dynamics(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise StorageRejected("Exact storage source law required", stage="law")
    _ready()
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant storage declaration")
        if type(owner) is not previous.DynamicsOwner or owner in _RETIRED:
            raise StorageRejected("Original unconsumed DynamicsOwner required", stage="owner")
        parent = previous._authority(owner)
        if parent.phase.kind.name != "INIT" or parent.p._run_sim is not False:
            raise StorageRejected("Actual existing INIT phase required", stage="phase")
        value = Request(owner, parent.trial.identity, _digest(source_plan()), "")
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (
            parent,
            parent.trial,
            previous._snapshot(parent),
            previous._graph(parent),
        )
        return value


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = StorageRejected(
            reason, stage=context.stage, request=context.request, partial=context
        )
    raise context.entry_error


def _capture(context, origin, error, raw):
    context.last_capture = (origin, error, raw)
    if context.capture_error is None:
        context.capture_error = error
    try:
        context.capture_errors += (context.last_capture,)
    except BaseException as secondary:
        context.raw_capture_append_error = (secondary, error, raw)


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.capture_error is not None:
        raise StorageRejected(
            "Storage observation incomplete; no next source", stage="capture", partial=context
        ) from context.capture_error
    if context.inherited:
        _reject(context, "Inherited observer cannot enter storage source")
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        _reject(context, "Actual exclusive storage epoch required")
    if (
        sys.setprofile is not context.setters[0]
        or sys.settrace is not context.setters[1]
        or sys.getprofile is not context.getters[0]
        or sys.gettrace is not context.getters[1]
        or sys.call_tracing is not context.call_tracing
    ):
        _reject(context, "Original observer controls changed")
    if context.observing and (
        context.getters[0]() is not context.observers[0]
        or context.getters[1]() is not context.observers[1]
    ):
        _reject(context, "Both source observers required before continuation")


def _values(context, *, stable=False):
    # Retain the already-issued parameter/subconfiguration roots as well as
    # the continuing phase/runtime participants. Completion uses this same
    # original INIT projector; rebuilding only its later object roster loses
    # genuine pre-phase wrappers referenced by vars(p).
    projector = previous.previous.previous._projector(context.parent.init_parent)
    projector.objects = [*projector.objects, *previous._objects(context.parent)]
    project = previous.previous.previous.core._LITERAL._project

    def fields(actual):
        ignored = context.store_fields if stable and actual is context.sim else frozenset()
        if stable:
            ignored |= next(
                (names for owner, names in context.molecule_permissions if owner is actual),
                frozenset(),
            )
        values = {name: value for name, value in vars(actual).items() if name not in ignored}
        if getattr(context, "molecule_claim", None) is not None:
            values = context.molecule.project_state(context.parent.molecule_session, values)
        return project(projector, values)

    return dict(
        simulator=fields(context.sim),
        parameters=project(projector, vars(context.p)),
        cells=project(projector, vars(context.cells)),
        objects=tuple(
            (role, fields(actual))
            for role, actual in previous._objects(context.parent)
            if actual is not context.sim
        ),
    )


def _snapshot(context, *, stable=False):
    return previous._scope(context.parent).snapshot(_values(context, stable=stable))


def _graph(context):
    context.graph_fields[:] = [vars(actual) for _, actual in previous._objects(context.parent)]
    return previous._scope(context.parent).graph(
        context.graph_view, context.graph_view, context.graph_tape
    )


def _epoch(context):
    return (
        _snapshot(context).identity,
        _graph(context),
        tuple(value.identity for value in previous._streams(context.parent)),
    )


def _bootstrap(context):
    fn, code, scope = context.checker
    if context.atoms is not fn or fn.__code__ is not code or fn.__globals__ is not scope:
        raise ValueError("Original independent storage metadata checker changed")
    for name, helper, retained in context.metadata:
        if globals().get(name) is not helper:
            raise ValueError("Original storage helper replaced: " + name)
        current = context.atoms(helper)
        if len(current) != len(retained) or any(
            a is not b for a, b in zip(current, retained, strict=True)
        ):
            raise ValueError("Original storage helper code/default/closure changed: " + name)


def _observer_bindings(context):
    return previous._observer_bindings(context)


def _bind_molecule_runtime(context, *, kind):
    """Use only the participant already issued by the actual parent claim."""
    parent = context.parent
    context.molecule = None
    context.molecule_claim = context.molecule_record = None
    context.molecule_functions = context.molecule_members = context.molecule_expressions = ()
    context.molecule_permissions = ()
    context.molecule_codes = frozenset()
    if not parent.request.native_molecules:
        return
    if kind not in ("storage", "first_step"):
        raise ValueError("Exact molecular child epoch required")
    lease = parent.storage_lease if kind == "storage" else parent.first_step_descendant
    api, claim = parent.molecule, lease.molecule_claim
    functions = tuple(
        (name, vars(api)[name])
        for name in (
            "validate_runtime_active",
            "validate_runtime",
            "runtime_members",
            "runtime_codes",
            "runtime_permissions",
            "observe_runtime",
            "finish_runtime",
            "project_state",
            "runtime_failed_context",
        )
    )
    if any(type(fn) is not FunctionType or fn.__globals__ is not vars(api) for _, fn in functions):
        raise ValueError("Actual original molecular runtime public functions required")
    if api.validate_runtime_active(claim, child=context) is not claim:
        raise ValueError("Different actual molecular runtime claimant")
    # Retain the real claim before fallible roster/capture work. Its original
    # parent lease also retains it if this helper's own entry is interrupted.
    context.molecule, context.molecule_claim = api, claim
    context.molecule_functions = functions
    context.molecule_function_atoms = tuple(context.atoms(fn) for _, fn in functions)
    members, expressions = api.runtime_members(claim), api.runtime_codes(claim)
    if type(members) is not tuple or any(type(fn) is not FunctionType for fn in members):
        raise ValueError("Actual original molecular runtime source roster required")
    if type(expressions) is not tuple or any(type(code) is not CodeType for code in expressions):
        raise ValueError("Actual original molecular expression code roster required")
    context.molecule_members, context.molecule_expressions = members, expressions
    context.molecule_permissions = api.runtime_permissions(claim)
    _merge_permissions((), context.molecule_permissions)
    initial = previous.previous.previous
    context.molecule_codes = frozenset(
        (*expressions, *(code for fn in members for code in initial._code_tree(fn.__code__)))
    )
    context.allowed_codes |= context.molecule_codes


def _merge_permissions(original, additional):
    """Union fields by actual holder identity, never first-match shadowing."""
    rows = []
    for owner, fields in (*original, *additional):
        if type(fields) is not frozenset or any(type(name) is not str for name in fields):
            raise ValueError("Exact original runtime field permissions required")
        index = next((i for i, (actual, _) in enumerate(rows) if owner is actual), None)
        if index is None:
            rows.append((owner, fields))
        else:
            rows[index] = (owner, rows[index][1] | fields)
    return tuple(rows)


def _molecule_runtime_bindings(context):
    if getattr(context, "short_runtime", None) is not None:
        return _short_runtime_bindings(context)
    if context.molecule_claim is None:
        if context.parent.request.native_molecules:
            raise ValueError("Enabled molecular runtime cannot lose its issued claimant")
        return ()
    api, claim = context.molecule, context.molecule_claim
    if api is not context.parent.molecule:
        raise ValueError("Original runtime provider replaced")
    values = [api, claim, context.molecule_permissions, context.molecule_codes]
    for (name, fn), expected in zip(
        context.molecule_functions, context.molecule_function_atoms, strict=True
    ):
        if vars(api).get(name) is not fn:
            raise ValueError("Original molecular runtime function replaced: " + name)
        current = context.atoms(fn)
        previous._same_refs(current, expected)
        values.extend(current)
    previous._same_refs(api.runtime_members(claim), context.molecule_members)
    previous._same_refs(api.runtime_codes(claim), context.molecule_expressions)
    if api.runtime_permissions(claim) is not context.molecule_permissions:
        raise ValueError("Original molecular runtime permission association changed")
    if context.molecule_record is None:
        if api.validate_runtime_active(claim, child=context) is not claim:
            raise ValueError("Original active runtime claim changed")
    elif api.validate_runtime(claim, child=context) is not context.molecule_record:
        raise ValueError("Original closed runtime record changed")
    for fn in context.molecule_members:
        values.extend(context.atoms(fn))
    values.extend(context.molecule_expressions)
    return tuple(values)


def _short_runtime_bindings(context):
    """Separate N-runtime provider; the original session projector stays real."""
    api, claim = context.short_runtime, context.molecule_claim
    if (
        type(api) is not ModuleType
        or sys.modules.get("cells.processes.betse_native_init_molecule_short_runtime") is not api
        or context.molecule is not context.parent.molecule
        or claim is None
        or not previous._pin(context.short_runtime_source_sha256)
    ):
        raise ValueError("Actual separate short-runtime/session authority required")
    path = Path(api.__file__)
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != (
        context.short_runtime_source_sha256
    ):
        raise ValueError("Original short-runtime producer changed")
    values = [api, claim, context.molecule, context.molecule_permissions, context.molecule_codes]
    for (provider, name, fn), expected in zip(
        context.short_runtime_functions, context.short_runtime_function_atoms, strict=True
    ):
        if provider not in (api, context.molecule) or vars(provider).get(name) is not fn:
            raise ValueError("Original short-runtime/session function replaced: " + name)
        current = context.atoms(fn)
        previous._same_refs(current, expected)
        values.extend((provider, name, *current))
    if (
        api.session_of(claim, child=context) is not context.parent.molecule_session
        or api.session_provider(claim, child=context) is not context.molecule
    ):
        raise ValueError("Original molecular session/provider association changed")
    previous._same_refs(api.runtime_members(claim), context.molecule_members)
    previous._same_refs(api.runtime_codes(claim), context.molecule_expressions)
    if api.runtime_permissions(claim) is not context.molecule_permissions:
        raise ValueError("Original short-runtime permission association changed")
    if context.molecule_record is None:
        if api.validate_runtime_active(claim, child=context) is not claim:
            raise ValueError("Original active short-runtime claim changed")
    elif api.validate_runtime(claim, child=context) is not context.molecule_record:
        raise ValueError("Original closed short-runtime record changed")
    for fn in context.molecule_members:
        values.extend(context.atoms(fn))
    values.extend(context.molecule_expressions)
    return tuple(values)


def _binding(context):
    _bootstrap(context)
    initial = previous.previous.previous
    values = [
        context.parent,
        context.parent.trial,
        context.phase,
        context.p,
        context.cells,
        context.sim,
        context.handler,
        context.cache,
        context.original,
        context.namespace,
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        _ELECTRICAL_FORWARDED,
        _ELECTRICAL_LEASES,
        ELECTRICAL_INTERFACE_SHA256,
        ELECTRICAL_REVIEW_SHA256,
        ELECTRICAL_PARENT_REVIEW_SHA256,
        ELECTRICAL_ANCESTOR_CLAIM,
        ELECTRICAL_ANCESTOR_CHECK,
        FIRST_STEP_ANCESTOR_CLAIM,
        FIRST_STEP_ANCESTOR_CHECK,
        SHORT_INIT_ANCESTOR_CLAIM,
        SHORT_INIT_ANCESTOR_CHECK,
        TERMINAL_INIT_ANCESTOR_CLAIM,
        TERMINAL_INIT_ANCESTOR_CHECK,
        context.entries,
        context.metadata,
        *_observer_bindings(context),
        *_molecule_runtime_bindings(context),
    ]
    for _, function, _ in context.metadata:
        values.extend(context.atoms(function))
    for function in (
        context.parent_claim,
        context.parent_check,
        context.method,
        context.zeros,
        context.zero_wrapper,
        *context.runtime_functions,
    ):
        values.extend(initial._atoms(function))
    for name in context.namespace_keys:
        value = context.namespace[name]
        values.extend((name, value, *initial._atoms(value)))
    if tuple(context.namespace) != context.namespace_keys:
        raise ValueError("Exact copied source namespace roster changed")
    if (
        tuple(vars(context.numpy_view)) != ("zeros",)
        or context.numpy_view.zeros is not context.zero_wrapper
    ):
        raise ValueError("Exact reached NumPy helper facade changed")
    values.extend(initial._atoms(context.numpy.zeros))
    return tuple(values)


def _check(context, *, closed=False):
    _bootstrap(context)
    if not closed:
        _guard(context)
    if (
        _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.dynamics_owner) is not context
        or context.parent is not context.refs[0]
        or context.parent.trial is not context.refs[1]
        or context.parent_check(context) is not context.parent
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.phase.sim is not context.sim
        or context.phase.dyna is not context.handler
        or context.phase.cache is not context.cache
        or context.request.identity != _digest(request_record(context.request))
        or context.request.source_identity != _digest(source_plan())
    ):
        raise ValueError("Original storage/parent/phase/caller ownership changed")
    if context.bindings is not None:
        previous._same_refs(_binding(context), context.bindings)
    if (
        context.stable is not None
        and _snapshot(context, stable=True).identity != context.stable.identity
    ):
        raise ValueError("Storage changed an unowned original value")
    if tuple(value.identity for value in previous._streams(context.parent)) != context.stream_ids:
        raise ValueError("Storage or observer advanced an original RNG stream")


def _zero(context, args, kwargs, frame):
    _check(context)
    if frame is not context.body_frame or frame.f_globals is not context.namespace:
        _reject(context, "zeros must be reached by actual original clear_storage")
    row = dict(frame=frame, args=args, kwargs=kwargs, returned=False, raw_return=None)
    context.last_helper = row
    context.helper_calls.append(row)
    try:
        value = context.zeros(*args, **kwargs)
        row["raw_return"] = context.last_helper_return = value
        row["returned"] = True
        return value
    except BaseException as error:
        row["primary"] = error
        if context.primary is None:
            context.primary = error
        raise


def _namespace(context):
    initial = previous.previous.previous
    native = context.parent.init_parent.factories["Simulator"]
    chain = initial.caches.previous.callbacks.simulator._chain(native.clear_storage)
    original = chain[-1]
    if (
        type(original) is not FunctionType
        or original.__code__.co_filename != str(NATIVE / SIM_FILE)
        or previous.previous._constant(original.__code__) != previous.previous._constant(_code())
    ):
        raise ValueError("Actual original whole-module storage executable required")
    context.original = original
    context.numpy = original.__globals__["np"]
    if context.numpy is not context.parent.numpy:
        raise ValueError("Original same-dynamics NumPy namespace required")
    context.zeros = context.numpy.zeros

    def zeros(*args, **kwargs):
        return _zero(context, args, kwargs, sys._getframe(1))

    context.zero_wrapper = zeros
    context.numpy_view = SimpleNamespace(zeros=zeros)
    context.namespace = dict(original.__globals__, np=context.numpy_view)
    context.namespace_keys = tuple(context.namespace)
    context.method = FunctionType(_code(), context.namespace, "clear_storage")
    context.expected_body = context.method.__code__
    context.allowed_codes = frozenset((context.expected_body,))
    context.runtime_functions = (type(context.sim).clear_storage,)


def _wrapper_guard(context, original, frame):
    _check(context)
    context.last_wrapper_attempt = frame
    if (
        original is not context.parent.init_parent
        or type(frame) is not FrameType
        or frame.f_locals.get("method") != "clear_storage"
        or frame.f_locals.get("name") != "Simulator"
        or frame.f_locals.get("actual") is not context.sim
        or frame.f_locals.get("context") is not original
        or frame.f_back is not context.driver_frame
        or context.wrapper_claim is not None
    ):
        _reject(context, "Actual same-instance once-only Simulator wrapper required")
    function = vars(type(context.sim))["clear_storage"]
    if frame.f_code is not function.__code__ or frame.f_globals is not function.__globals__:
        _reject(context, "Original storage wrapper code/namespace changed")
    for name, cell in zip(function.__code__.co_freevars, function.__closure__ or (), strict=True):
        if frame.f_locals.get(name) is not cell.cell_contents:
            _reject(context, "Actual original wrapper closure changed")
    context.wrapper_claim = frame


def _dispatch(context, original, label, delegate, actual, args, kwargs, frame):
    _check(context)
    context.last_dispatch = (original, label, delegate, actual, args, kwargs, frame)
    initial = previous.previous.previous
    if (
        original is not context.parent.init_parent
        or label != "Simulator.clear_storage"
        or actual is not context.sim
        or len(args) != 2
        or kwargs
        or args[0] is not context.cells
        or args[1] is not context.p
        or frame.f_code is not initial._invoke.__code__
        or frame.f_globals is not vars(initial)
        or frame.f_back is not context.wrapper_claim
        or delegate is not original.factories["Simulator"].clear_storage
        or context.dispatched
    ):
        _reject(context, "Original once-claimed storage call/arguments required")
    context.dispatched = True
    context.body_driver = sys._getframe()
    value = context.method(actual, *args)
    context.last_raw = (context.body_frame, value)
    _check(context)
    if value is not None:
        _reject(context, "Original storage source returns None")
    return value


def _finish_pending_store(context, *, normal=True):
    pending = context.pending_store
    if pending is None:
        return
    context.pending_store = None
    line, name, before, existed = pending
    context.last_store_attempt = (pending, context.sim, normal)
    raw = None
    try:
        holder = vars(context.sim)
        raw = (line, name, before, holder.get(name), name in holder, normal)
        context.last_store = raw
        context.stores.append(raw)
    except BaseException as error:
        _capture(
            context, "store_capture", error, raw if raw is not None else context.last_store_attempt
        )


def _optional_line(context, frame):
    site = context.optional_lines.get(frame.f_lineno)
    if site is None:
        return
    field = site
    # A genuinely absent native attribute is allowed to raise its ORIGINAL
    # AttributeError at this source position after all preceding stores.
    if field not in vars(context.sim):
        return
    context.last_optional = (field, vars(context.sim)[field], frame)
    if field == "molecules" and getattr(context, "molecule_claim", None) is not None:
        _molecule_runtime_bindings(context)
        return
    _reject(
        context, "Reached optional clear_cache owner has no adopted original dispatch authority"
    )


def _observe(context, frame, event, arg):
    if frame.f_code in getattr(context, "molecule_codes", ()):
        context.molecule.observe_runtime(
            context.molecule_claim, child=context, frame=frame, event=event, arg=arg
        )
        return
    if event == "call":
        row = dict(
            frame=frame,
            code=frame.f_code,
            globals=frame.f_globals,
            returned=False,
            body_started=False,
        )
        context.last_attempt = row
        try:
            context.work.append(row)
        except BaseException as error:
            _capture(context, "body_attempt", error, row)
        _check(context)
        if (
            frame.f_code is not context.expected_body
            or context.body_frame is not None
            or frame.f_back is not context.body_driver
            or frame.f_globals is not context.namespace
            or frame.f_locals.get("self") is not context.sim
            or frame.f_locals.get("cells") is not context.cells
            or frame.f_locals.get("p") is not context.p
            or len(context.work) > MAX_WORK
        ):
            _reject(context, "Actual once-dispatched original storage body required")
        context.body_frame = frame
        context.frames[id(frame)] = row
        row["body_started"] = True
    row = context.frames.get(id(frame))
    if row is None:
        return
    if event == "exception":
        context.last_source_error = (frame, arg[1])
        try:
            context.pending[id(frame)] = arg[1]
        except BaseException as error:
            if context.primary is None:
                context.primary = arg[1]
            _capture(context, "source_exception", error, (frame, arg))
    if event == "line":
        _finish_pending_store(context)
        _check(context)
        _optional_line(context, frame)
        name = context.store_lines.get(frame.f_lineno)
        if name is not None:
            holder = vars(context.sim)
            context.pending_store = (frame.f_lineno, name, holder.get(name), name in holder)
    if event == "return":
        context.last_raw = (frame, arg)
        normal = None
        try:
            normal = previous.previous.previous._normal_return(frame)
            if not normal and context.primary is None:
                original = context.pending.get(id(frame))
                if original is not None:
                    # Preserve this before any fallible witness/capture helper
                    # (including rejection of the helper's own entry).
                    context.primary = original
        except BaseException as error:
            _capture(context, "return_classification", error, context.last_raw)
        try:
            context.observer_namespace["_witness"](context, frame, arg)
        except BaseException as error:
            _capture(context, "return_witness", error, context.last_raw)
        try:
            _finish_pending_store(context, normal=normal)
        except BaseException as error:
            _capture(context, "return_store_capture", error, (context.pending_store, frame, arg))
        try:
            context.raw_returns.append(context.last_raw)
            context.locals[id(frame)] = dict(frame.f_locals)
            row["returned"] = True
        except BaseException as error:
            _capture(context, "return_locals", error, context.last_raw)
        context.return_classification = normal
        context.body_returned = normal is True


def _observer_recipe(context):
    origin = previous.previous
    namespace = dict(
        vars(origin),
        previous=previous.previous.previous,
        DynamicsRejected=StorageRejected,
        _ACTIVE=_ACTIVE,
        _guard=_guard,
        _check=_check,
        _reject=_reject,
        _observe=_observe,
        _epoch=_epoch,
        MAX_WORK=MAX_WORK,
    )
    for name in (
        "_record_capture",
        "_witness",
        "_delegate",
        "_same_epoch",
        "_inherited",
        "_recover_hooks",
    ):
        function = vars(origin)[name]
        namespace[name] = FunctionType(
            function.__code__, namespace, name, function.__defaults__, function.__closure__
        )
    base_inherited = namespace["_inherited"]

    def inherited(current, observer, frame, event, arg):
        if (
            event in ("c_call", "c_return", "c_exception")
            and frame.f_code in current.molecule_codes
        ):
            # The existing trace owns Python entries/returns. Its paired
            # profile supplies the original C transcript to that SAME child
            # observer, before forwarding the inherited profile callback.
            namespace["_observe"](current, frame, event, arg)
        return base_inherited(current, observer, frame, event, arg)

    namespace["_inherited"] = inherited
    function = origin._account.__wrapped__
    context.observer_namespace = namespace
    account = FunctionType(
        function.__code__,
        namespace,
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    context.account = context.observer_account = contextmanager(account)
    context.observer_refs = tuple(namespace.items())
    context.observer_functions = tuple(
        namespace[name]
        for name in (
            "_record_capture",
            "_guard",
            "_check",
            "_reject",
            "_observe",
            "_witness",
            "_delegate",
            "_same_epoch",
            "_inherited",
            "_epoch",
            "_recover_hooks",
        )
    ) + (base_inherited, account, context.account)


def _context(request, refs):
    parent = refs[0]
    fields = [vars(actual) for _, actual in previous._objects(parent)]
    view = SimpleNamespace(objects=previous._objects(parent), fields=fields)
    store_lines = dict(_stores())
    optional = {}
    for node in ast.walk(_node()):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            text = ast.unparse(node.value)
            for field in ("molecules", "grn", "endo_retic"):
                if text.startswith("self." + field + ".") and text.endswith("clear_cache()"):
                    optional[node.lineno] = field
    return SimpleNamespace(
        request=request,
        refs=refs,
        parent=parent,
        phase=parent.phase,
        p=parent.p,
        cells=parent.cells,
        sim=parent.sim,
        handler=parent.handler,
        cache=parent.phase.cache,
        thread=get_ident(),
        active=True,
        invalid=False,
        inherited=False,
        observing=False,
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        primary=None,
        trial=None,
        validating=False,
        before=None,
        after=None,
        stable=None,
        bindings=None,
        entries=None,
        stage="storage_retirement",
        frames={},
        pending={},
        work=[],
        c_calls=[],
        raw_returns=[],
        locals={},
        helper_calls=[],
        stores=[],
        pending_store=None,
        store_lines=store_lines,
        store_fields=frozenset(store_lines.values()),
        optional_lines=optional,
        body_frame=None,
        body_driver=None,
        body_returned=False,
        wrapper_claim=None,
        dispatched=False,
        driver_frame=None,
        last_raw=None,
        setters=(sys.setprofile, sys.settrace),
        getters=(sys.getprofile, sys.gettrace),
        call_tracing=sys.call_tracing,
        required_hooks=(sys.getprofile(), sys.gettrace()),
        observers=None,
        cleanup_errors=(),
        hooks_safe=False,
        graph_fields=fields,
        graph_view=view,
        graph_tape=SimpleNamespace(rng=parent.np_rng, events=(), draws=(), locals={}),
        molecule=None,
        molecule_claim=None,
        molecule_record=None,
        molecule_permissions=(),
        molecule_codes=frozenset(),
    )


def trial_record(value):
    return dict(
        request=value.request_identity,
        parent=value.parent_identity,
        before=value.before.identity,
        after=value.after.identity,
        streams_before=value.stream_before,
        streams_after=value.stream_after,
        stores=tuple(
            (row[0], row[1], id(row[2]), id(row[3]), row[4], row[5]) for row in value.stores
        ),
        work=tuple((id(row["frame"]), row["returned"]) for row in value.work),
        source_completed=value.source_completed,
        storage_is_not_voltage_or_time_loop=True,
    )


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise StorageRejected("Actual storage source remains held", stage="release")
    api = _ready()
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant storage preparation")
        if type(request) is not Request or request not in _REQUESTS:
            raise StorageRejected("Actual issued Request required", stage="request")
        if request in _CONSUMED or request.dynamics_owner in _RETIRED:
            raise StorageRejected("Storage epoch already attempted", stage="consumed")
        refs = _REQUESTS[request]
        parent = api._authority(request.dynamics_owner)
        graph = api._graph(parent)
        api._same_refs(graph[0], refs[3][0])
        if (
            parent is not refs[0]
            or parent.trial is not refs[1]
            or api._snapshot(parent).identity != refs[2].identity
            or graph[1] != refs[3][1]
        ):
            raise StorageRejected("Original dynamics epoch changed", stage="parent")
        context = _context(request, refs)
        context.atoms, context.checker = parent.init_parent.atoms, parent.init_parent.checker
        context.metadata = tuple(
            (name, function, context.atoms(function))
            for name, function in globals().items()
            if type(function) is FunctionType and function.__globals__ is globals()
        )
        _CONSUMED[request] = _RETIRED[request.dynamics_owner] = context
        _ACTIVE.append(context)
        primary = None
        try:
            context.parent_claim, context.parent_check = (
                getattr(api, PARENT_CLAIM),
                getattr(api, PARENT_CHECK),
            )
            context.entries = MappingProxyType(
                dict(wrapper_guard=_wrapper_guard, dispatch=_dispatch)
            )
            context.stream_ids = tuple(value.identity for value in previous._streams(parent))
            context.parent_claim(
                request.dynamics_owner,
                expected=refs[1],
                transition=context,
                entries=context.entries,
            )
            _observer_recipe(context)
            _namespace(context)
            _bind_molecule_runtime(context, kind="storage")
            context.stream_ids = tuple(value.identity for value in previous._streams(parent))
            context.bindings = _binding(context)
            context.before = _snapshot(context)
            context.stable = _snapshot(context, stable=True)
            context.stage = "actual_original_clear_storage"
            with context.account(context):
                _run(context)
            _check(context)
            if (
                not context.body_returned
                or context.primary is not None
                or context.capture_error is not None
            ):
                raise StorageRejected(
                    "Original storage source incomplete", stage="sealing", partial=context
                )
            if context.molecule_claim is not None:
                context.molecule_record = context.molecule.finish_runtime(
                    context.molecule_claim, child=context
                )
            context.after = _snapshot(context)
            context.after_graph = _graph(context)
            value = Trial(
                request.identity,
                request.parent_identity,
                context.before,
                context.after,
                context.stream_ids,
                tuple(v.identity for v in previous._streams(parent)),
                tuple(context.stores),
                tuple(context.work),
                tuple(context.c_calls),
                tuple(context.raw_returns),
                True,
                "",
            )
            context.trial = replace(value, identity=_digest(trial_record(value)))
        except BaseException as error:
            primary = context.entry_error if context.entry_error is not None else context.primary
            if primary is None:
                primary = error
            context.invalid = True
            context.failure_error = primary
            try:
                _FAILED.append(context)
            except BaseException as capture:
                context.retention_error = (capture, primary, context)
            try:
                primary.init_storage_partial = context
            except BaseException as capture:
                context.attachment_error = (capture, primary)
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
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
            context.hooks_safe = all(
                a is context.required_hooks[0] and b is context.required_hooks[1]
                for a, b in samples
            )
        if primary is not None:
            raise primary
        if context.invalid or context.cleanup_errors or not context.hooks_safe:
            raise StorageRejected("Storage closure refused", stage="closure", partial=context)
        owner = object.__new__(StorageOwner)
        context.owner = owner
        _ISSUED[owner] = (context, context.trial)
        return owner


def _run(context):
    context.driver_frame = sys._getframe()
    return context.sim.clear_storage(context.cells, context.p)


class StorageOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only genuine storage preparation issues a live owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("No cache, serialization or checkpoint hydration")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not StorageOwner or owner not in _ISSUED:
        raise StorageRejected("Actual issued StorageOwner required", stage="owner")
    context, trial = _ISSUED[owner]
    if owner in _ELECTRICAL_FORWARDED or hasattr(context, "electrical_transition"):
        raise StorageRejected(
            "Storage epoch consumed by its electrical successor",
            stage="electrical_forwarded",
            trial=trial,
            partial=context,
        )
    _reserve_validation(context)
    try:
        _closed_storage_epoch(context, trial)
        return context
    except BaseException:
        context.invalid = True
        raise
    finally:
        context.validating = False


def _closed_storage_epoch(context, trial):
    """The original complete proof, used once before electrical mutation."""
    _ready()
    _check(context, closed=True)
    graph = _graph(context)
    previous._same_refs(graph[0], context.after_graph[0])
    if (
        graph[1] != context.after_graph[1]
        or _snapshot(context).identity != context.after.identity
        or context.trial is not trial
        or trial.source_completed is not True
        or trial.identity != _digest(trial_record(trial))
        or context.primary is not None
        or context.capture_error is not None
        or context.cleanup_errors
        or not context.hooks_safe
        or context.invalid
    ):
        raise StorageRejected("Closed storage values/aliases/source changed", stage="owner")


def _electrical_binding(payload):
    return FunctionType(
        previous._storage_binding.__code__,
        dict(
            vars(previous),
            STORAGE_BACK_REFERENCE_SLOTS=ELECTRICAL_BACK_REFERENCE_SLOTS,
            STORAGE_BINDING_KIND=ELECTRICAL_BINDING_KIND,
        ),
    )(payload)


def _electrical_api():
    if not all(
        previous._pin(value)
        for value in (
            ELECTRICAL_INTERFACE_SHA256,
            ELECTRICAL_REVIEW_SHA256,
            ELECTRICAL_PARENT_REVIEW_SHA256,
        )
    ) or any(
        type(name) is not str for name in (ELECTRICAL_ANCESTOR_CLAIM, ELECTRICAL_ANCESTOR_CHECK)
    ):
        raise StorageRejected(
            "Actual reviewed electrical handoff remains held", stage="electrical_held"
        )
    _ready()
    parent_path = Path(previous.__file__)
    parent_code = compile(parent_path.read_bytes(), str(parent_path), "exec", dont_inherit=True)
    parent_functions = {
        value.co_name: value for value in parent_code.co_consts if type(value) is CodeType
    }
    functions, atoms = [], []
    for name in (ELECTRICAL_ANCESTOR_CLAIM, ELECTRICAL_ANCESTOR_CHECK):
        function = vars(previous).get(name)
        if type(function) is not FunctionType:
            raise StorageRejected(
                "Actual Completion electrical contract unavailable", stage="electrical_ancestor"
            )
        retained = _electrical_atoms(function)
        if (
            function.__globals__ is not vars(previous)
            or function.__code__ != parent_functions.get(name)
            or function.__code__.co_filename != str(parent_path)
            or function.__closure__ is not None
            or function.__defaults__ is not None
            or function.__kwdefaults__ is not None
        ):
            raise StorageRejected(
                "Actual Completion electrical contract unavailable", stage="electrical_ancestor"
            )
        functions.append(function)
        atoms.append(retained)
    path = Path(__file__).parents[3] / ("src/" + ELECTRICAL_MODULE.replace(".", "/") + ".py")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Actual original electrical consumer required")
    raw = path.read_bytes()
    identity, backrefs = _electrical_binding(raw)
    if identity != ELECTRICAL_INTERFACE_SHA256 or backrefs != (
        ("PARENT_SOURCE_SHA256", hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        ("PARENT_REVIEW_SHA256", ELECTRICAL_PARENT_REVIEW_SHA256),
    ):
        raise ValueError("Original electrical source or storage back-reference changed")
    module = sys.modules.get(ELECTRICAL_MODULE)
    if (
        type(module) is not ModuleType
        or module.storage is not sys.modules[__name__]
        or Path(module.__file__).resolve() != path
        or module.PARENT_CLAIM != "_claim_for_electrical"
        or module.PARENT_CHECK != "_check_electrical_authority"
        or any(getattr(module, name) != value for name, value in backrefs)
    ):
        raise ValueError("Actual original electrical namespace/handoff changed")
    module.interfaces._source_interface(
        module,
        raw,
        path,
        ("prepare", "_ready", "_call_parent", "_wrapper_guard", "_dispatch", "_run", "_stores"),
    )
    module._ready()
    binding = _ElectricalBinding(module, previous, *functions, tuple(atoms))
    _check_electrical_binding(binding)
    return binding


def _electrical_atoms(function):
    return previous.previous.previous._atoms(function)


def _check_electrical_binding(binding):
    if (
        type(binding) is not _ElectricalBinding
        or binding.ancestor_module is not previous
        or vars(previous).get(ELECTRICAL_ANCESTOR_CLAIM) is not binding.claim
        or vars(previous).get(ELECTRICAL_ANCESTOR_CHECK) is not binding.check
    ):
        raise ValueError("Authenticated electrical ancestor slot changed")
    for function, retained in zip((binding.claim, binding.check), binding.atoms, strict=True):
        current = _electrical_atoms(function)
        if len(current) != len(retained) or any(
            a is not b for a, b in zip(current, retained, strict=True)
        ):
            raise ValueError("Authenticated electrical ancestor code/default/delegate changed")


def _electrical_route(context):
    """Registry/frame authentication; never reopen the previous numeric epoch."""
    binding = _electrical_api()
    module = binding.module
    owner = getattr(context, "owner", None)
    if type(owner) is not StorageOwner:
        raise ValueError("Actual issued original StorageOwner required")
    issued = _ISSUED.get(owner)
    lease, child = _ELECTRICAL_LEASES.get(owner), getattr(context, "electrical_transition", None)
    if (
        issued is None
        or issued[0] is not context
        or issued[1] is not context.trial
        or lease is None
        or context.electrical_lease is not lease
        or lease.parent is not context
        or lease.child is not child
        or _ELECTRICAL_FORWARDED.get(owner) is not child
        or context.active
        or context.invalid
        or context.thread != get_ident()
        or child.invalid
        or child.thread != context.thread
        or type(child.request) is not module.Request
        or child.request.storage_owner is not owner
        or module._REQUESTS.get(child.request) is not child.refs
        or module._CONSUMED.get(child.request) is not child
        or module._RETIRED.get(owner) is not child
        or child.storage_parent is not context
        or child.parent is not context.parent
        or child.refs[0] is not context
        or child.refs[1] is not lease.trial
        or child.phase is not context.phase
        or child.sim is not context.sim
        or child.cells is not context.cells
        or child.p is not context.p
        or child.handler is not context.handler
        or child.cache is not context.cache
        or child.entries is not lease.entries
        or tuple(lease.entries) != ("wrapper_guard", "dispatch")
        or lease.entries["wrapper_guard"] is not module._wrapper_guard
        or lease.entries["dispatch"] is not module._dispatch
    ):
        raise ValueError("Original one-shot storage/electrical registry ancestry changed")
    _check_electrical_binding(lease.ancestor_binding)
    if lease.ancestor_binding.module is not module:
        raise ValueError("Authenticated original electrical producer changed")
    if child.active:
        if not module._ACTIVE or module._ACTIVE[-1] is not child:
            raise ValueError("Actual exclusive electrical transition required")
    else:
        published = module._ISSUED.get(getattr(child, "owner", None))
        if (
            type(getattr(child, "owner", None)) is not module.ElectricalOwner
            or published is None
            or published[0] is not child
            or published[1] is not child.trial
            or child.trial.completed is not True
        ):
            raise ValueError("Actual successful closed electrical record required")
    frame = child.body_frame
    if frame is not None:
        row = child.frames.get(id(frame))
        if (
            row is None
            or row["frame"] is not frame
            or not row["body_started"]
            or frame.f_code is not child.expected_body
            or frame.f_globals is not child.methods["update_V"].__globals__
            or frame.f_locals.get("self") is not context.sim
            or frame.f_locals.get("cells") is not context.cells
            or frame.f_locals.get("p") is not context.p
            or frame.f_back is not child.body_driver
            or child.body_driver.f_code is not module._dispatch.__code__
            or (lease.body_frame is not None and lease.body_frame is not frame)
        ):
            raise ValueError("Original electrical body/frame association changed")
        lease.body_frame = frame
    elif lease.body_frame is not None:
        raise ValueError("Observed original electrical body disappeared")
    return child, module


def _electrical_values(context):
    lease = context.electrical_lease
    for (_, actual), holder, names, target in zip(
        lease.objects, lease.holders, lease.names, lease.fields, strict=True
    ):
        if vars(actual) is not holder:
            raise ValueError("Original storage object holder changed during electrical work")
        ignored = lease.allowed if actual is context.sim else frozenset()
        if tuple(name for name in holder if name not in ignored) != tuple(
            name for name in names if name not in ignored
        ):
            raise ValueError("Electrical work changed an unowned field roster")
        target.clear()
        target.update((name, holder[name]) for name in names if name not in ignored)
    initial = previous.previous.previous
    projector = initial._projector(context.parent.init_parent)
    projector.objects = [*projector.objects, *lease.objects]
    values = tuple(lease.fields)
    if context.molecule_claim is not None:
        values = context.molecule.project_state(context.parent.molecule_session, values)
    return previous._scope(context.parent).snapshot(
        initial.core._LITERAL._project(projector, values)
    )


def _electrical_graph(context):
    _electrical_values(context)
    lease = context.electrical_lease
    return previous._scope(context.parent).graph(lease.view, lease.view, lease.tape)


def _claim_for_electrical(owner, *, expected, transition, entries):
    """One irreversible transfer by Root's actual guarded parent call."""
    binding = _electrical_api()
    module = binding.module
    frame = sys._getframe(1)
    with _LOCK:
        issued = _ISSUED.get(owner) if type(owner) is StorageOwner else None
        if (
            issued is None
            or issued[1] is not expected
            or frame.f_code is not module._call_parent.__code__
            or frame.f_globals is not vars(module)
            or frame.f_locals.get("context") is not transition
            or frame.f_locals.get("operation") != "claim"
            or frame.f_locals.get("function") is not _claim_for_electrical
            or frame.f_back is None
            or frame.f_back.f_code is not module.prepare.__code__
            or frame.f_back.f_locals.get("context") is not transition
            or not module._ACTIVE
            or module._ACTIVE[-1] is not transition
        ):
            raise StorageRejected(
                "Actual electrical issuer parent call required", stage="electrical_entry"
            )
        context = issued[0]
        if owner in _ELECTRICAL_FORWARDED or hasattr(context, "electrical_transition"):
            raise StorageRejected("Electrical epoch already attempted", stage="electrical_consumed")
        if (
            context.active
            or context.invalid
            or context.validating
            or context.owner is not owner
            or transition.storage_parent is not context
            or transition.parent is not context.parent
            or transition.refs[1] is not expected
            or transition.entries is not entries
            or transition.thread != context.thread
            or context.thread != get_ident()
        ):
            context.invalid = transition.invalid = True
            raise ValueError("Original closed storage/electrical association changed")
        _ELECTRICAL_FORWARDED[owner] = transition
        context.electrical_transition = transition
        try:
            _closed_storage_epoch(context, expected)
            fields = frozenset(name for _, _, name in module._stores(module._definitions()))
            if len(fields) != 27:
                raise ValueError("Exact source-derived27 electrical Simulator fields required")
            objects = list(previous._objects(context.parent))
            for role, actual in (("parameters", context.p), ("cells", context.cells)):
                if not any(actual is value for _, value in objects):
                    objects.append((role, actual))
            objects = tuple(objects)
            ancestor = binding.claim
            lease = SimpleNamespace(
                parent=context,
                child=transition,
                trial=expected,
                entries=entries,
                bindings=context.bindings,
                metadata=context.metadata,
                refs=context.refs,
                streams=tuple(value.identity for value in previous._streams(context.parent)),
                allowed=fields,
                objects=objects,
                holders=tuple(vars(value) for _, value in objects),
                names=tuple(tuple(vars(value)) for _, value in objects),
                fields=[{} for _ in objects],
                ancestor=ancestor,
                ancestor_binding=binding,
                body_frame=None,
            )
            lease.view = SimpleNamespace(objects=objects, fields=lease.fields)
            lease.tape = SimpleNamespace(rng=context.parent.np_rng, events=(), draws=(), locals={})
            context.electrical_lease = lease
            _ELECTRICAL_LEASES[owner] = lease
            _check_electrical_binding(binding)
            if ancestor(context.parent, context, transition) is not context.parent:
                raise ValueError("Actual Completion/electrical ancestor claim unavailable")
            _check_electrical_binding(binding)
            lease.values, lease.graph = _electrical_values(context), _electrical_graph(context)
            _check_electrical_authority(transition)
            return context
        except BaseException as error:
            primary = _retain_electrical_failure(context, transition, error)
            raise primary  # noqa: B904 -- retain original entry/cause and secondary above.


def _retain_electrical_failure(context, transition, error):
    primary = next(
        (
            value
            for value in (context.entry_error, getattr(transition, "entry_error", None))
            if value is not None
        ),
        error,
    )
    context.electrical_error = primary
    if primary is not error:
        context.electrical_capture_error = (error, primary)
    context.invalid = transition.invalid = True
    return primary


def _check_electrical_authority(transition):
    history = getattr(transition, "short_init_transition", None)
    forwarded = getattr(transition, "first_step_transition", None)
    terminal = getattr(transition, "terminal_init_transition", None)
    if terminal is not None:
        if history is not None or forwarded is not None:
            transition.invalid = terminal.invalid = True
            raise ValueError("Electrical epoch cannot have multiple INIT descendants")
        if getattr(terminal, "claimed", False):
            _check_terminal_init_ancestor(transition, terminal)
            return transition.storage_parent
    if history is not None and forwarded is not None:
        transition.invalid = history.invalid = forwarded.invalid = True
        raise ValueError("Electrical epoch cannot have two selected descendants")
    if history is not None and getattr(history, "claimed", False):
        _check_short_init_ancestor(transition, history)
        return transition.storage_parent
    if forwarded is not None and getattr(forwarded, "claimed", False):
        _check_first_step_ancestor(transition, forwarded)
        return transition.storage_parent
    context = transition.storage_parent
    if _electrical_route(context)[0] is not transition:
        raise ValueError("Different original electrical transition")
    lease = context.electrical_lease
    _ready()
    _bootstrap(context)
    if (
        context.trial is not lease.trial
        or context.trial.identity != _digest(trial_record(context.trial))
        or context.bindings is not lease.bindings
        or context.metadata is not lease.metadata
        or context.refs is not lease.refs
        or vars(previous).get(ELECTRICAL_ANCESTOR_CLAIM) is not lease.ancestor
        or tuple(value.identity for value in previous._streams(context.parent)) != lease.streams
    ):
        raise ValueError("Original completed storage/electrical metadata changed")
    # Key's successor proof must factor its own inherited old data. Its exact
    # new contract remains unbound until delivered; no stale validator fallback.
    checker = lease.ancestor_binding.check
    _check_electrical_binding(lease.ancestor_binding)
    if checker(context.parent, context, transition) is not context.parent:
        raise ValueError("Actual factored Completion/electrical checker unavailable")
    _check_electrical_binding(lease.ancestor_binding)
    previous._same_refs(_binding(context), lease.bindings)
    if transition.body_frame is None:
        # Before the first literal body frame, even its future27 fields still
        # belong to the sealed Storage epoch. Never capture an observer's
        # pre-entry mutation as an allowed electrical baseline.
        if _snapshot(context).identity != context.after.identity:
            raise ValueError("Original storage state changed before electrical body entry")
        entry_graph = _graph(context)
        previous._same_refs(entry_graph[0], context.after_graph[0])
        if entry_graph[1] != context.after_graph[1]:
            raise ValueError("Original storage aliases changed before electrical body entry")
    if _electrical_values(context).identity != lease.values.identity:
        raise ValueError("Electrical work changed an unowned original storage value")
    graph = _electrical_graph(context)
    previous._same_refs(graph[0], lease.graph[0])
    if graph[1] != lease.graph[1]:
        raise ValueError("Electrical work changed an original immutable storage reference edge")
    return context


def _first_step_key_api():
    """Proposed Key seam, closed until its actual reviewed names are adopted."""
    if any(
        type(name) is not str for name in (FIRST_STEP_ANCESTOR_CLAIM, FIRST_STEP_ANCESTOR_CHECK)
    ):
        raise StorageRejected(
            "Actual reviewed Key first-step ancestor contract unavailable",
            stage="first_step_ancestor_held",
        )
    _ready()
    path = Path(previous.__file__)
    raw = path.read_bytes()
    compiled = compile(raw, str(path), "exec", dont_inherit=True)
    codes = {code.co_name: code for code in compiled.co_consts if type(code) is CodeType}
    functions = []
    for name in (FIRST_STEP_ANCESTOR_CLAIM, FIRST_STEP_ANCESTOR_CHECK):
        function = vars(previous).get(name)
        if type(function) is not FunctionType:
            raise ValueError("Actual typed Key first-step callback required")
        retained = _electrical_atoms(function)
        if (
            function.__globals__ is not vars(previous)
            or function.__code__ != codes.get(name)
            or function.__closure__ is not None
            or function.__defaults__ is not None
            or function.__kwdefaults__ is not None
        ):
            raise ValueError("Actual original Key first-step source/defaults required")
        functions.append((name, function, retained))
    return tuple(functions)


def _check_first_step_key_binding(functions):
    for name, function, retained in functions:
        if vars(previous).get(name) is not function:
            raise ValueError("Proved Key first-step slot changed")
        previous._same_refs(_electrical_atoms(function), retained)


def _claim_first_step_ancestor(electrical, transition):
    functions = _first_step_key_api()
    context = electrical.storage_parent
    binding = _electrical_api()
    module = binding.module
    frame = sys._getframe(1)
    if (
        frame.f_code is not module._claim_for_first_step.__code__
        or frame.f_globals is not vars(module)
        or frame.f_locals.get("context") is not electrical
        or (frame.f_locals.get("transition") is not transition)
        or (module._FORWARDED.get(electrical.owner) is not transition)
        or (context.electrical_transition is not electrical)
    ) or hasattr(context, "terminal_init_transition"):
        raise ValueError("Actual electrical first-step claim frame/ancestry required")
    context.first_step_transition = transition
    context.first_step_key_functions = functions
    try:
        _check_first_step_key_binding(functions)
        result = functions[0][1](context.parent, context, electrical, transition)
        _check_first_step_key_binding(functions)
        if result is not context.parent:
            raise ValueError("Different actual Completion first-step ancestor")
    except BaseException as error:
        _retain_electrical_failure(context, transition, error)
        raise
    return context


def _check_first_step_ancestor(electrical, transition):
    context = electrical.storage_parent
    functions = context.first_step_key_functions
    if (
        context.first_step_transition is not transition
        or context.electrical_transition is not electrical
    ) or getattr(context, "terminal_init_transition", None) is not None:
        raise ValueError("Original Storage/first-step parent association changed")
    _check_first_step_key_binding(functions)
    result = functions[1][1](context.parent, context, electrical, transition)
    _check_first_step_key_binding(functions)
    if result is not context.parent:
        raise ValueError("Different actual checked Completion ancestor")
    return context


def _short_init_key_api():
    """Exact distinct Completion seam, unavailable until explicitly adopted."""
    names = (SHORT_INIT_ANCESTOR_CLAIM, SHORT_INIT_ANCESTOR_CHECK)
    if names != ("_claim_short_init_ancestor", "_check_short_init_ancestor"):
        raise StorageRejected(
            "Reviewed Key short-history ancestor contract unavailable",
            stage="short_init_ancestor_held",
        )
    _ready()
    path = Path(previous.__file__)
    raw = path.read_bytes()
    compiled = compile(raw, str(path), "exec", dont_inherit=True)
    codes = {code.co_name: code for code in compiled.co_consts if type(code) is CodeType}
    functions = []
    for name in names:
        function = vars(previous).get(name)
        if (
            type(function) is not FunctionType
            or function.__globals__ is not vars(previous)
            or function.__code__ != codes.get(name)
            or function.__closure__ is not None
            or function.__defaults__ is not None
            or function.__kwdefaults__ is not None
        ):
            raise ValueError("Actual original Key short-history source/defaults required")
        functions.append((name, function, _electrical_atoms(function)))
    return tuple(functions)


def _claim_short_init_ancestor(electrical, transition):
    functions = _short_init_key_api()
    context = electrical.storage_parent
    binding = _electrical_api()
    module = binding.module
    frame = sys._getframe(1)
    if (
        frame.f_code is not module._claim_for_short_init.__code__
        or frame.f_globals is not vars(module)
        or frame.f_locals.get("context") is not electrical
        or (frame.f_locals.get("transition") is not transition)
        or (module._FORWARDED.get(electrical.owner) is not transition)
        or (context.electrical_transition is not electrical)
        or hasattr(context, "short_init_transition")
        or hasattr(context, "first_step_transition")
    ) or hasattr(context, "terminal_init_transition"):
        raise ValueError("Actual once-only electrical short-history claim frame required")
    context.short_init_transition = transition
    context.short_init_key_functions = functions
    try:
        _check_first_step_key_binding(functions)
        result = functions[0][1](context.parent, context, electrical, transition)
        _check_first_step_key_binding(functions)
        if result is not context.parent:
            raise ValueError("Different actual Completion short-history ancestor")
    except BaseException as error:
        _retain_electrical_failure(context, transition, error)
        raise
    return context


def _check_short_init_ancestor(electrical, transition):
    context = electrical.storage_parent
    if (
        context.short_init_transition is not transition
        or context.electrical_transition is not electrical
        or getattr(context, "first_step_transition", None) is not None
    ) or getattr(context, "terminal_init_transition", None) is not None:
        raise ValueError("Original Storage/short-history parent association changed")
    functions = context.short_init_key_functions
    _check_first_step_key_binding(functions)
    result = functions[1][1](context.parent, context, electrical, transition)
    _check_first_step_key_binding(functions)
    if result is not context.parent:
        raise ValueError("Different checked Completion short-history ancestor")
    return context


def _reserve_validation(context):
    if context.validating:
        context.invalid = True
        raise StorageRejected("Reentrant closed storage validation", stage="owner", partial=context)
    if context.active or context.invalid:
        raise StorageRejected("No successful closed storage epoch", stage="owner")
    context.validating = True


# Separate held natural-terminal ancestry; no selected-history reuse.


def _terminal_init_key_api():
    """Exact distinct Completion seam, unavailable until explicitly adopted."""
    names = (TERMINAL_INIT_ANCESTOR_CLAIM, TERMINAL_INIT_ANCESTOR_CHECK)
    if names != ("_claim_terminal_init_ancestor", "_check_terminal_init_ancestor"):
        raise StorageRejected(
            "Reviewed Key natural-terminal ancestor contract unavailable",
            stage="terminal_init_ancestor_held",
        )
    _ready()
    path = Path(previous.__file__)
    raw = path.read_bytes()
    interfaces._source_interface(previous, raw, path, names)
    compiled = compile(raw, str(path), "exec", dont_inherit=True)
    codes = {code.co_name: code for code in compiled.co_consts if type(code) is CodeType}
    functions = []
    for name in names:
        function = vars(previous).get(name)
        if (
            type(function) is not FunctionType
            or function.__globals__ is not vars(previous)
            or function.__code__ != codes.get(name)
            or (function.__closure__ is not None)
            or (function.__defaults__ is not None)
            or (function.__kwdefaults__ is not None)
        ):
            raise ValueError("Actual original Key natural-terminal source/defaults required")
        functions.append((name, function, _electrical_atoms(function)))
    return tuple(functions)


def _claim_terminal_init_ancestor(electrical, transition):
    functions = _terminal_init_key_api()
    context = electrical.storage_parent
    binding = _electrical_api()
    module = binding.module
    frame = sys._getframe(1)
    if (
        frame.f_code is not module._claim_for_terminal_init.__code__
        or frame.f_globals is not vars(module)
        or frame.f_locals.get("context") is not electrical
        or (frame.f_locals.get("transition") is not transition)
        or (module._FORWARDED.get(electrical.owner) is not transition)
        or (context.electrical_transition is not electrical)
        or hasattr(context, "terminal_init_transition")
        or hasattr(context, "first_step_transition")
    ) or hasattr(context, "short_init_transition"):
        raise ValueError("Actual once-only electrical natural-terminal claim frame required")
    context.terminal_init_transition = transition
    context.terminal_init_key_functions = functions
    try:
        _check_first_step_key_binding(functions)
        result = functions[0][1](context.parent, context, electrical, transition)
        _check_first_step_key_binding(functions)
        if result is not context.parent:
            raise ValueError("Different actual Completion natural-terminal ancestor")
    except BaseException as error:
        _retain_electrical_failure(context, transition, error)
        raise
    return context


def _check_terminal_init_ancestor(electrical, transition):
    context = electrical.storage_parent
    if (
        context.terminal_init_transition is not transition
        or context.electrical_transition is not electrical
        or getattr(context, "first_step_transition", None) is not None
    ) or getattr(context, "short_init_transition", None) is not None:
        raise ValueError("Original Storage/natural-terminal parent association changed")
    functions = context.terminal_init_key_functions
    _check_first_step_key_binding(functions)
    result = functions[1][1](context.parent, context, electrical, transition)
    _check_first_step_key_binding(functions)
    if result is not context.parent:
        raise ValueError("Different checked Completion natural-terminal ancestor")
    return context
