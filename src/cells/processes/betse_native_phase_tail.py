"""Prepared same-object SEED constructor tail; unavailable claims refuse.

Legacy47 mutation remains distinct from the prepared fresh-world interval,
which uses the coordinator's already-active actual claim through sealing.
Fresh-world provider/stage adoption remains unbound. No old read-only claim,
inspection or serialized phase authorizes _run_sim or complete phase use.
"""

import ast
import hashlib
import importlib
import os
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, MappingProxyType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_phase_dyna as previous
from cells.processes import betse_native_phase_tail_source as source

literal, aliases, core = previous.literal, previous.aliases, previous.core
LAW_ID = "betse_same_issued_seed_phase_constructor_tail@1"
RELEASE = "CELLS_NATIVE_PHASE_TAIL_RELEASED"
DYNA_SHA256 = "94d3f28adb304a8c6fcde2c4ca97fe3481393fb30799222c1be1ee58e810b187"
PHASE = "betse/science/phase/phasecls.py"
PHASE_SHA256 = "e7c129aca1930fcb31884f32d4f2ebbb46d31113a66887a39c85ba0009b78ea8"
# Bind only after Key supplies/reviews the NEW mutating successor. None is a
# refusal, not a provider extension point. The read-only d9 API is not reused.
KEY_MODULE = "cells.processes.betse_native_parameter_seed_tail"
KEY_FILE = "src/cells/processes/betse_native_parameter_seed_tail.py"
KEY_FACTORY = "seed_tail"
KEY_CLOSED_CHECK = "validate_closed"
KEY_LAW_ID = "betse_same_parameter_seed_tail_mutation@1"
KEY_LAW_ATTRIBUTE = "SEED_TAIL_LAW"
KEY_SHA256 = "47cac39970b7ac6bbf9dd2d3b40bf2b87d189980d7feb7ac1cf2d7ccaa406cdc"
KEY_REVIEW_SHA256 = "458188402076e2a3aa25a4aa44e3030b6f436ba79817465a844720c9ebb4bfb8"
KEY_CLAIM_TYPE = "SeedTailClaim"
KEY_ERROR_CONTEXT = "seed_tail_claim"
# Coordinated same-instance parent hooks; no supplied callback/phase authority.
PARENT_HOOKS = ("_claim_for_tail", "_check_runtime_authority", "_dispatch_tail")
METHODS = ("_init_kludge", "_init_kludge_time")
RETURN_ORDER = ("_init_kludge_time", "_init_kludge", "complete")
STORES = (("sim", "dyna"), ("parameters", "_run_sim"), ("phase", "export_dirname"))
_TAIL = source.PhaseConstructorTail.complete
_METHODS = {name: getattr(source.PhaseConstructorTail, name) for name in METHODS}
_REQUESTS, _CONSUMED, _ISSUED = (WeakKeyDictionary() for _ in range(3))
_LOCK, _ACTIVE = RLock(), []
WORLD_MODE = "fresh_world_ready_prephase_single_claim_seed_constructor"
_WORLD, _FORWARDED = WeakKeyDictionary(), WeakKeyDictionary()


def _world_api():
    return previous._world_api()


class TailRejected(ValueError):
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
        self.stage, self.request, self.trial = stage, request, trial
        self.partial, self.source_error, self.capture_error = partial, source_error, capture_error


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    dyna_owner: previous.PhaseDynaOwner
    parent_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Use the actual issued same-phase dyna child")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    cache: object
    stores: tuple
    stages: tuple
    events: tuple
    work: tuple
    method_entries: tuple
    entry_attempts: tuple
    parameter_claim: object
    completed: bool
    failure_stage: str | None
    identity: str


@dataclass(frozen=True, slots=True)
class _AncestryTape:
    """No growing tail observations participate in unchanged ancestry."""

    rng: object = None
    events: tuple = ()
    draws: tuple = ()
    locals: tuple = ()


def _digest(value):
    return previous._digest(value)


def _body(node):
    return previous.caches.previous._body(node)


def _statements(nodes):
    return ast.dump(ast.Module(body=nodes, type_ignores=[]))


def source_plan(*, mode=None):
    if mode is not None and (type(mode) is not str or mode != WORLD_MODE):
        raise ValueError("Exact explicit fresh-world source mode required")
    if (
        mode is None
        and hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != DYNA_SHA256
    ):
        raise ValueError("Explicitly adopted dyna producer required")
    path = aliases.NATIVE / PHASE
    if hashlib.sha256(path.read_bytes()).hexdigest() != PHASE_SHA256:
        raise ValueError("Pinned original phase source changed")
    parent = previous.source_plan(mode=mode)
    helper = previous.caches.previous.callbacks.simulator
    native = helper._class(ast.parse(path.read_bytes()), "SimPhase")
    own = helper._class(ast.parse(Path(source.__file__).read_bytes()), "PhaseConstructorTail")
    constructor = _body(helper._method(native, "__init__"))
    start = next(
        i
        for i, node in enumerate(constructor)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "_init_kludge"
    )
    selected = constructor[start:]
    if _statements(selected) != _statements(_body(helper._method(own, "complete"))):
        raise ValueError("Original constructor remainder changed")
    lines = {}
    for name in METHODS:
        original, copied = helper._method(native, name), helper._method(own, name)
        if _statements(_body(original)) != _statements(_body(copied)):
            raise ValueError("Original full kludge helper body changed: " + name)
        lines[name] = (original.lineno, original.end_lineno)
    return dict(
        law=LAW_ID,
        dyna_producer=None if mode is not None else DYNA_SHA256,
        native_pins=parent["native_pins"],
        original_phase_sha256=PHASE_SHA256,
        literal_sha256=hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
        constructor_lines=(selected[0].lineno, selected[-1].end_lineno),
        helper_lines=lines,
        selected_kind="same actual original SimPhaseKind.SEED only",
        native_store_order=STORES,
        parameter_fields_allowed=("_run_sim",),
        temporal_stores_allowed=(),
        parameter_contract_bound=mode is None and _key_bound(),
        key_producer=None if mode is not None else KEY_SHA256,
        key_dependency_review_sha256=None if mode is not None else KEY_REVIEW_SHA256,
        required_parent_hooks=PARENT_HOOKS,
        path_creation=False,
        INIT_SIM_full_Parameters_world_physics_or_checkpoint_admitted=False,
    )


def _key_bound():
    return all(
        type(value) is str and value
        for value in (
            KEY_MODULE,
            KEY_FILE,
            KEY_SHA256,
            KEY_REVIEW_SHA256,
            KEY_FACTORY,
            KEY_CLOSED_CHECK,
            KEY_CLAIM_TYPE,
            KEY_LAW_ID,
            KEY_LAW_ATTRIBUTE,
            KEY_ERROR_CONTEXT,
        )
    )


def _key_api():
    if not _key_bound():
        raise TailRejected("New same-p SEED-tail mutation issuer is unbound", stage="key_contract")
    root = Path(__file__).resolve().parents[3]
    path = root / KEY_FILE
    if (
        path.is_symlink()
        or not path.is_file()
        or (hashlib.sha256(path.read_bytes()).hexdigest() != KEY_SHA256)
    ):
        raise TailRejected("Exact new Key producer unavailable", stage="key_producer")
    api = importlib.import_module(KEY_MODULE)
    if (
        sys.modules.get(KEY_MODULE) is not api
        or Path(api.__file__).resolve() != path
        or getattr(api, KEY_LAW_ATTRIBUTE, None) != KEY_LAW_ID
        or not isinstance(getattr(api, KEY_CLAIM_TYPE, None), type)
        or not callable(getattr(api, KEY_FACTORY, None))
        or not callable(getattr(api, KEY_CLOSED_CHECK, None))
    ):
        raise TailRejected("Actual new Key mutation API required", stage="key_contract")
    return api


def _parent_api():
    # Ordinary dyna validation remains unchanged until a later coordinated
    # source successor implements these exact same-object routes.
    for name in PARENT_HOOKS:
        function = getattr(previous, name, None)
        if type(function) is not FunctionType or function.__globals__ is not vars(previous):
            raise TailRejected("Genuine dyna continuation hooks unavailable", stage="dyna_contract")


def request_record(request):
    return dict(
        law=LAW_ID,
        parent=request.parent_identity,
        source=request.source_identity,
        kind="actual original SEED",
        supplied_phase_or_parameter=False,
    )


def from_dyna(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise TailRejected("Explicit same-SEED constructor-tail law required", stage="law")
    plan = source_plan()
    parent = previous._validate(owner)
    phase = parent.phase
    prefix = parent.parent.parent
    enum = type(phase.kind)
    if phase.kind is not prefix.kind or phase.kind is not getattr(enum, "SEED", None):
        raise TailRejected("Only the genuine existing SEED owner is supported", stage="phase_kind")
    request = Request(owner, parent.trial.identity, _digest(plan), "")
    request = replace(request, identity=_digest(request_record(request)))
    _REQUESTS[request] = (
        parent,
        parent.trial,
        phase,
        phase.p,
        phase.sim,
        phase.cells,
        phase.cache,
        phase.dyna,
        prefix,
        parent.constructor_claim,
        parent.refs[4],
        parent.constructor_claim_record,
        _cache_issuance_records(parent.parent),
    )
    return request


def _bindings():
    functions = (
        _world_api,
        _world_phase_construct,
        _world_phase_check,
        _world_phase_seal,
        _world_phase_check_seal,
        _claim_for_seed_world,
        _check_world_authority,
        _dispatch_seed_world,
        _digest,
        _body,
        _statements,
        source_plan,
        _key_bound,
        _key_api,
        _parent_api,
        request_record,
        from_dyna,
        _bindings,
        _key_bindings,
        _acquire,
        _native_bindings,
        _runtime_bindings,
        _cache_issuance_records,
        _registry_links,
        _namespace,
        _namespace_bindings,
        _complete_body,
        _helper_body,
        _guard,
        _check,
        _parameter_check,
        _allowed_state,
        _objects,
        _projector,
        _stable_snapshot,
        _stable_graph,
        _snapshot,
        _graph,
        _capture_state,
        _new_attempt,
        _reject_entry,
        _claim_entry,
        _entry_document,
        _attempt_document,
        _invoke,
        _admit_body,
        _account,
        _account.__wrapped__,
        _claim,
        _claim.__wrapped__,
        _partial,
        trial_record,
        _validate,
        prepare,
        require_phase,
        _TAIL,
        *_METHODS.values(),
    )
    return (
        WORLD_MODE,
        _WORLD,
        _FORWARDED,
        _REQUESTS,
        _CONSUMED,
        _ISSUED,
        _LOCK,
        _ACTIVE,
        LAW_ID,
        RELEASE,
        DYNA_SHA256,
        PHASE_SHA256,
        METHODS,
        RETURN_ORDER,
        STORES,
        PARENT_HOOKS,
        KEY_MODULE,
        KEY_FILE,
        KEY_SHA256,
        KEY_REVIEW_SHA256,
        KEY_FACTORY,
        KEY_CLOSED_CHECK,
        KEY_CLAIM_TYPE,
        KEY_LAW_ID,
        KEY_LAW_ATTRIBUTE,
        KEY_ERROR_CONTEXT,
        _AncestryTape,
        *literal._surface(_AncestryTape),
        *(atom for function in functions for atom in aliases._atoms(function)),
        *(atom for name in PARENT_HOOKS for atom in aliases._atoms(getattr(previous, name, None))),
        *(
            atom
            for function in (
                sys._getframe,
                sys.getprofile,
                sys.setprofile,
                sys.gettrace,
                sys.settrace,
            )
            for atom in aliases._atoms(function)
        ),
    )


def _key_bindings(api):
    cls = getattr(api, KEY_CLAIM_TYPE)
    return (
        api,
        cls,
        *literal._surface(cls),
        *(
            atom
            for name in (KEY_FACTORY, KEY_CLOSED_CHECK)
            for atom in aliases._atoms(getattr(api, name))
        ),
    )


def _acquire(context):
    # Authenticate retained native classes/namespaces; no import/constructor.
    native = context.refs[8].factories["SimPhase"]
    helper = previous.caches.previous.callbacks
    for name in ("__init__", *METHODS):
        helper._source_function(getattr(native, name), PHASE, name, "SimPhase")
    original = helper.simulator._chain(native.__init__)[-1]
    namespace = original.__globals__
    context.native_phase = native
    context.enum = namespace["SimPhaseKind"]
    context.exception = namespace["BetseSimPhaseException"]
    if type(context.phase.kind) is not context.enum or context.phase.kind is not context.enum.SEED:
        raise ValueError("Actual native SEED enumeration required")
    context.native_bindings = _native_bindings(context)


def _native_bindings(context):
    return (
        context.native_phase,
        *literal._surface(context.native_phase),
        context.enum,
        *literal._surface(context.enum),
        context.enum.SEED,
        context.enum.INIT,
        context.enum.SIM,
        context.exception,
        *literal._surface(context.exception),
        *(
            atom
            for name in ("__init__", *METHODS)
            for atom in aliases._atoms(getattr(context.native_phase, name))
        ),
    )


def _runtime_bindings(context):
    prefix = context.refs[8]
    objects = (("SimPhase", context.phase), ("Cells", context.refs[5]), ("Simulator", context.sim))
    result = []
    for role, actual in objects:
        cls = prefix.runtime_types[role]
        if type(actual) is not cls:
            raise ValueError("Original issued runtime class changed: " + role)
        result.extend((role, actual, cls, *previous._surface(cls)))
    # Retain actual owned wrappers and their closure links to the original
    # native delegates. No instance method/class substitution is permitted.
    for name in METHODS:
        wrapper = vars(type(context.phase)).get(name)
        delegate = getattr(prefix.factories["SimPhase"], name)
        if type(wrapper) is not FunctionType:
            raise ValueError("Original phase helper wrapper unavailable: " + name)
        cells = dict(zip(wrapper.__code__.co_freevars, wrapper.__closure__ or (), strict=True))
        if "delegate" not in cells or cells["delegate"].cell_contents is not delegate:
            raise ValueError("Original phase helper delegate link changed: " + name)
        result.extend((name, *aliases._atoms(wrapper), *aliases._atoms(delegate)))
    return tuple(result)


def _cache_issuance_records(cache):
    records = []
    for role, actual in cache.objects:
        issued = previous.caches._OBJECTS.get(actual)
        if (
            type(issued) is not tuple
            or len(issued) != 2
            or issued[0] is not cache
            or type(issued[1]) is not type(role)
            or issued[1] != role
        ):
            raise ValueError("Original cache object context/role tuple changed: " + role)
        # Retain the actual producer-issued tuple, not a reconstructed entry.
        records.append((role, actual, issued))
    return tuple(records)


def _registry_links(context):
    # Compare raw issuance/retirement references only. This must not reopen
    # pre-tail parameter/cache snapshots after the legitimate _run_sim store.
    parent, cache, prefix = context.parent, context.parent.parent, context.refs[8]
    caches, assembly = previous.caches, previous.caches.previous
    pairs = [
        ("dyna_request", previous._REQUESTS, parent.request, parent.refs),
        ("dyna_attempt", previous._CONSUMED, parent.request, parent),
        ("dyna_issuer", previous._ISSUED, context.request.dyna_owner, parent),
        ("cache_request", caches._REQUESTS, cache.request, prefix),
        ("cache_attempt", caches._CONSUMED, cache.request, cache),
        ("cache_issuer", caches._ISSUED, parent.request.cache_owner, cache),
        (
            "cache_retirement",
            getattr(caches, "_FORWARDED", None),
            parent.request.cache_owner,
            parent,
        ),
        ("assembly_request", assembly._REQUESTS, prefix.request, prefix.parents),
        ("assembly_attempt", assembly._CONSUMED, prefix.request, prefix),
        ("assembly_parameter_claim", assembly._CLAIMED, prefix.request.parameters, prefix),
        ("assembly_issuer", assembly._ISSUED, cache.request.phase_owner, prefix),
        ("assembly_retirement", assembly._FORWARDED, cache.request.phase_owner, cache),
        (
            "callback_issuer",
            assembly.callbacks._ISSUED,
            prefix.request.callbacks,
            prefix.parents[4],
        ),
    ]
    for label, registry, objects, expected in (
        ("assembly_object", assembly._OBJECTS, prefix.objects, prefix),
        ("dyna_object", previous._OBJECTS, parent.objects, parent),
    ):
        pairs.extend((label + ":" + role, registry, actual, expected) for role, actual in objects)
    result = []
    for label, registry, key, expected in pairs:
        if registry is None or registry.get(key) is not expected:
            raise ValueError("Original inherited registry link changed: " + label)
        # Labels above diagnose a failed edge; freshly concatenated labels
        # are not producer-issued reference atoms. Retain the actual edge.
        result.extend((registry, key, expected))
    records = _cache_issuance_records(cache)
    original = context.refs[12]
    if len(records) != len(original):
        raise ValueError("Original cache raw object roster changed")
    for (role, actual, issued), (old_role, old_actual, old_issued) in zip(
        records, original, strict=True
    ):
        if (
            type(role) is not type(old_role)
            or role != old_role
            or actual is not old_actual
            or (issued is not old_issued)
        ):
            raise ValueError("Original cache issuance tuple reference changed: " + role)
        result.extend((caches._OBJECTS, actual, issued, issued[0], issued[1]))
    if getattr(cache, "dyna_transition", None) is not parent or (
        getattr(prefix, "cache_transition", None) is not cache
    ):
        raise ValueError("Original inherited irreversible transition marker changed")
    result.extend((cache, cache.dyna_transition, prefix, prefix.cache_transition))
    return tuple(result)


def _namespace(context):
    namespace = dict(SimPhaseKind=context.enum, BetseSimPhaseException=context.exception)
    context.bodies = {
        "complete": FunctionType(_TAIL.__code__, dict(_TAIL.__globals__, **namespace)),
        **{
            name: FunctionType(function.__code__, dict(function.__globals__, **namespace))
            for name, function in _METHODS.items()
        },
    }

    def complete(actual, kind, p):
        return _complete_body(context, actual, kind, p, sys._getframe())

    def helper(name):
        def invoke(actual):
            return _helper_body(context, name, actual, sys._getframe())

        return invoke

    context.complete = complete
    context.methods = {name: helper(name) for name in METHODS}

    def entry(name):
        def invoke(actual, *, source_frame):
            return _invoke(context, name, actual, source_frame)

        return invoke

    # A future genuine parent dispatch supplies the actual native-wrapper
    # caller frame, never an inspection record or user-supplied permission.
    context.entries = MappingProxyType({name: entry(name) for name in METHODS})
    context.namespace_bindings = _namespace_bindings(context)


def _namespace_bindings(context):
    return (
        context.entries,
        *(
            atom
            for name, function in context.entries.items()
            for atom in (name, *aliases._atoms(function))
        ),
        *(
            atom
            for function in (context.complete, *context.methods.values())
            for atom in aliases._atoms(function)
        ),
        *(
            atom
            for function in context.bodies.values()
            for atom in (
                function.__globals__,
                function.__globals__["SimPhaseKind"],
                function.__globals__["BetseSimPhaseException"],
                *aliases._atoms(function),
            )
        ),
    )


def _complete_body(context, actual, kind, p, invocation):
    attempt = _new_attempt(context, "complete", "tail_body_wrapper", invocation)
    if (
        context.complete_invocation is not None
        or invocation.f_back is not context.driver_frame
        or actual is not context.phase
        or kind is not context.enum.SEED
        or p is not context.p
    ):
        _reject_entry(context, attempt, "Constructor remainder requires its actual driver call")
    context.complete_invocation = sys._getframe()
    attempt["status"] = attempt["work"]["admission"] = "claimed"
    _guard(context)
    _check(context)
    return context.bodies["complete"](actual, kind, p)


def _helper_body(context, name, actual, invocation):
    attempt = _new_attempt(context, name, "tail_body_wrapper", invocation)
    record = context.stack[-1] if context.stack else None
    if (
        record is None
        or record["method"] != name
        or record["status"] != "calling_body"
        or invocation.f_back is not record["invocation"]
        or record["body_invocation"] is not None
        or actual is not context.phase
    ):
        _reject_entry(context, attempt, "Helper delegate requires its actual claimed wrapper")
    record["body_invocation"] = sys._getframe()
    attempt["status"] = attempt["work"]["admission"] = "claimed"
    _guard(context)
    _check(context)
    return context.bodies[name](actual)


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if getattr(context, "world_mode", None) == WORLD_MODE:
        return _world_api()._world_stage_guard(context)
    previous.handler._stop(context)
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or (not _ACTIVE or _ACTIVE[-1] is not context)
    ):
        raise TailRejected("Unavailable tail source entry", stage="source_entry")


def _parameter_check(context):
    if context.active:
        context.claim.check()
        if context.claim.parameters is not context.p:
            raise ValueError("New mutation claim lost the original p")
    else:
        # Deliberately NOT previous._closed_claim or the old cache validators.
        record = getattr(context.key, KEY_CLOSED_CHECK)(
            context.claim, dyna_claim=context.refs[9], original_lease=context.refs[10]
        )
        if record is not context.claim_record or context.claim.record is not record:
            raise ValueError("Original successor parameter record changed")


def _allowed_state(context):
    holders = dict(phase=context.phase, sim=context.sim, parameters=context.p)
    present = tuple((role, name) for role, name in STORES if name in vars(holders[role]))
    if present != STORES[: len(present)]:
        raise ValueError("Native tail stores are not an ordered prefix")
    expected = (context.handler, False, context.export_path)
    for (role, name), value in zip(present, expected, strict=False):
        if vars(holders[role])[name] is not value:
            raise ValueError("Original tail value/alias changed: " + role + "." + name)
    for role, actual in holders.items():
        extra = tuple(name for owner, name in present if owner == role)
        if tuple(vars(actual)) != (*context.field_names[role], *extra):
            raise ValueError("Unrelated or reordered tail fields: " + role)
    return present


def _check(context):
    if getattr(context, "world_mode", None) == WORLD_MODE:
        _world_api()._world_stage_runtime(context)
        if hasattr(context, "field_names"):
            _allowed_state(context)
        return
    if (
        context.invalid
        or context.thread != get_ident()
        or _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or previous._ISSUED.get(context.request.dyna_owner) is not context.parent
        or getattr(previous, "_FORWARDED", {}).get(context.request.dyna_owner) is not context
        or getattr(context.parent, "tail_transition", None) is not context
    ):
        raise ValueError("Original irreversible dyna-to-tail epoch changed")
    previous._check_runtime_authority(context.parent)
    literal._same(_registry_links(context), context.inherited_links)
    literal._same(_runtime_bindings(context), context.runtime_bindings)
    if (
        context.parent.phase is not context.phase
        or context.parent.trial is not context.refs[1]
        or context.phase.p is not context.p
        or context.phase.sim is not context.sim
        or context.phase.cells is not context.refs[5]
        or context.phase.cache is not context.refs[6]
        or context.phase.dyna is not context.handler
        or context.phase.kind is not context.enum.SEED
        or context.parent.constructor_claim is not context.refs[9]
        or context.parent.refs[4] is not context.refs[10]
        or context.parent.constructor_claim_record is not context.refs[11]
    ):
        raise ValueError("Original phase/sim/cache/handler/parameter ancestry changed")
    if _digest(request_record(context.request)) != context.request.identity or (
        _digest(source_plan()) != context.request.source_identity
    ):
        raise ValueError("Tail request/source changed")
    literal._same(_bindings(), context.bindings)
    if _key_api() is not context.key:
        raise ValueError("New parameter issuer changed")
    literal._same(_key_bindings(context.key), context.key_bindings)
    literal._same(_native_bindings(context), context.native_bindings)
    literal._same(_namespace_bindings(context), context.namespace_bindings)
    _parameter_check(context)
    _allowed_state(context)
    if _stable_snapshot(context).identity != context.before.identity:
        raise ValueError("Field outside the three exact tail stores changed")
    graph = _stable_graph(context)
    literal._same(graph[0], context.before_graph[0])
    if graph[1] != context.before_graph[1]:
        raise ValueError("Inherited reference edges outside tail stores changed")


def _objects(parent):
    candidates = [
        ("parameters", parent.p),
        ("callback", parent.phase.callbacks),
        *parent.inherited_objects,
        *parent.objects,
    ]
    seen, objects = set(), []
    for role, actual in candidates:
        if id(actual) not in seen:
            seen.add(id(actual))
            objects.append((role, actual))
    return objects


def _projector(context):
    if getattr(context, "world_mode", None) == WORLD_MODE:
        return _world_api()._world_projector(context)
    # Parameter/configuration wrappers and weak proxies stay references to
    # their original issued producers; they are not serialized or hydrated as
    # fresh objects by this tail snapshot.
    return SimpleNamespace(
        objects=[
            *context.objects,
            *(("inherited", value) for value in context.refs[8].parents[0].graph[0]),
            *(("proxy", value) for _, value in context.parent.parent.proxy_returns),
        ]
    )


def _stable_snapshot(context):
    projector = _projector(context)
    ignored = {
        id(context.phase): {"export_dirname"},
        id(context.sim): {"dyna"},
        id(context.p): {"_run_sim"},
    }
    return core.caches.snapshot(
        [
            dict(
                role=role,
                fields=literal._project(
                    projector,
                    {
                        name: value
                        for name, value in vars(actual).items()
                        if name not in ignored.get(id(actual), ())
                    },
                ),
            )
            for role, actual in context.objects
        ]
    )


def _stable_graph(context):
    ignored = {
        id(context.phase): {"export_dirname"},
        id(context.sim): {"dyna"},
        id(context.p): {"_run_sim"},
    }
    for fields, (_, actual) in zip(context.stable_fields, context.objects, strict=True):
        fields.clear()
        fields.update(
            {
                name: value
                for name, value in vars(actual).items()
                if name not in ignored.get(id(actual), ())
            }
        )
    return literal.callers._graph(context.stable_view, context.stable_view, context.stable_tape)


def _snapshot(context):
    projector = _projector(context)
    return core.caches.snapshot(
        [
            dict(role=role, fields=literal._project(projector, vars(actual)))
            for role, actual in context.objects
        ]
    )


def _graph(context):
    for fields, (_, actual) in zip(context.all_fields, context.objects, strict=True):
        fields.clear()
        fields.update(vars(actual))
    return literal.callers._graph(context.all_view, context.all_view, context.tape)


def _capture_state(context, frame, event):
    # Raw object/field references are retained before typed projection.
    context.raw_state = (dict(vars(context.phase)), dict(vars(context.sim)), dict(vars(context.p)))
    present = _allowed_state(context)
    for role, name in present[len(context.stores) :]:
        actual = dict(phase=context.phase, sim=context.sim, parameters=context.p)[role]
        context.stores.append(
            dict(
                sequence=len(context.stores),
                role=role,
                field=name,
                value=vars(actual)[name],
                method=frame.f_code.co_name,
                event=event,
            )
        )
    context.locals[(frame.f_code.co_filename, frame.f_code.co_qualname)] = dict(frame.f_locals)


def _new_attempt(context, name, layer, frame):
    attempt = dict(
        sequence=len(context.attempts),
        method=name,
        layer=layer,
        frame=frame,
        status="attempted",
        body_started=False,
        work=None,
    )
    if len(context.attempts) >= 100000 or len(context.work) >= 100000:
        # One separate raw overflow slot preserves the last rejected frame
        # without enlarging either bounded ordered ledger.
        context.overflow_attempt = attempt
        _reject_entry(context, attempt, "Bounded tail attempt/work ledger exhausted")
    work = dict(
        sequence=len(context.work),
        layer=layer,
        method=name,
        phase=context.stage,
        attempt_sequence=attempt["sequence"],
        admission="pending",
        body_started=False,
        entry_is_case=False,
    )
    attempt["work"] = work
    context.attempts.append(attempt)
    context.work.append(work)
    return attempt


def _reject_entry(context, attempt, reason):
    if attempt is None or not (
        any(item is attempt for item in context.attempts)
        or getattr(context, "overflow_attempt", None) is attempt
    ):
        attempt = _new_attempt(context, "unclaimed", "tail_entry_refusal", sys._getframe(1))
    context.invalid = True
    attempt.update(status="rejected", reason=reason)
    if attempt["work"] is not None:
        attempt["work"].update(admission="rejected", reason=reason)
    context.last_rejected_attempt = attempt
    if context.entry_error is None:
        context.entry_error = TailRejected(reason, stage="method_entry", request=context.request)
    raise context.entry_error


def _claim_entry(context, name, actual, source_frame, invocation):
    attempt = _new_attempt(context, name, "tail_entry_attempt", invocation)
    if (
        context.invalid
        or not context.active
        or context.thread != get_ident()
        or (
            not _ACTIVE
            or _ACTIVE[-1] is not context
            or actual is not context.phase
            or name not in METHODS
            or name in context.claims
        )
    ):
        _reject_entry(context, attempt, "Repeated, foreign or unavailable tail helper entry")
    entry = invocation.f_back
    dispatch = None if entry is None else entry.f_back
    route = None if dispatch is None else dispatch.f_back
    wrapper = None if route is None else route.f_back
    member = getattr(type(context.phase), name, None)
    parent = context.stack[-1] if context.stack else None
    expected = context.complete_frame if parent is None else parent["body"]
    if (
        dispatch is None
        or dispatch.f_code is not previous._dispatch_tail.__code__
        or dispatch.f_locals.get("transition") is not context
        or route is None
        or route.f_code is not previous.caches.previous._native_call.__code__
        or route.f_locals.get("context") is not context.refs[8]
        or wrapper is None
        or type(member) is not FunctionType
        or wrapper.f_code is not member.__code__
        or wrapper.f_locals.get("actual") is not actual
        or wrapper.f_back is not source_frame
        or source_frame is not expected
        or source_frame is None
        or (parent is None and (name != "_init_kludge" or context.root_claimed))
        or (
            parent is not None
            and (
                parent["method"] != "_init_kludge"
                or name != "_init_kludge_time"
                or parent["status"] != "calling_body"
                or parent["child_claimed"]
            )
        )
    ):
        _reject_entry(context, attempt, "Helper must enter through its actual ordered source frame")
    if parent is None:
        context.root_claimed = True
    else:
        parent["child_claimed"] = True
    record = dict(
        method=name,
        invocation=invocation,
        body_invocation=None,
        body=None,
        child_claimed=False,
        status="claimed",
        attempt=attempt,
    )
    attempt["status"] = "claimed"
    attempt["work"]["admission"] = "claimed"
    context.claims[name] = record
    context.stack.append(record)
    return record


def _entry_document(context):
    return tuple(
        dict(
            method=name,
            status=value["status"],
            body_entered=value["body"] is not None,
            child_claimed=value["child_claimed"],
        )
        for name, value in context.claims.items()
    )


def _attempt_document(context):
    return tuple(
        dict(
            sequence=attempt["sequence"],
            method=attempt["method"],
            layer=attempt["layer"],
            status=attempt["status"],
            body_started=attempt["body_started"],
            hook_deliveries=attempt.get("hooks", ()),
            reason=attempt.get("reason"),
            frame=(attempt["frame"].f_code.co_filename, attempt["frame"].f_code.co_qualname)
            if attempt["frame"] is not None
            else None,
        )
        for attempt in context.attempts
    )


def _invoke(context, name, actual, source_frame):
    record = _claim_entry(context, name, actual, source_frame, sys._getframe())
    primary = None
    try:
        _guard(context)
        _check(context)
        previous.handler._event(context, name + "_enter", actual)
        _guard(context)
        _check(context)
        record["status"] = "calling_body"
        result = context.methods[name](actual)
        context.last_completed = (name, actual, result)
        if name == "_init_kludge" and not record["child_claimed"]:
            _reject_entry(context, record["attempt"], "Missing original time-helper call")
        context.stages.append(name)
        previous.handler._event(context, name + "_return", result)
        _guard(context)
        _check(context)
        return result
    except BaseException as error:
        primary = error
        previous.handler._event(context, name + "_unwind", actual)
        raise
    finally:
        try:
            if not context.stack or context.stack[-1] is not record:
                raise ValueError("Tail method stack changed")
            context.stack.pop()
            record["status"] = record["attempt"]["status"] = (
                "returned" if primary is None else "failed"
            )
            record["attempt"]["work"]["admission"] = record["status"]
        except BaseException as capture:
            previous.handler.captures._remember_observation_error(
                context, capture, origin="tail_entry_release", raw=record
            )


def _admit_body(context, frame):
    existing = context.admitted_frames.get(id(frame))
    if existing is not None and existing["frame"] is frame:
        return existing
    name = next((name for name, fn in context.bodies.items() if fn.__code__ is frame.f_code), None)
    attempt = _new_attempt(context, name or frame.f_code.co_qualname, "literal_body_attempt", frame)
    if (
        context.invalid
        or not context.active
        or context.thread != get_ident()
        or (not _ACTIVE or _ACTIVE[-1] is not context or name is None)
    ):
        _reject_entry(context, attempt, "Unavailable or unselected raw tail body")
    if name == "complete":
        if (
            context.complete_frame is not None
            or frame.f_back is not context.complete_invocation
            or (
                frame.f_locals.get("self") is not context.phase
                or frame.f_locals.get("kind") is not context.enum.SEED
                or frame.f_locals.get("p") is not context.p
            )
        ):
            _reject_entry(context, attempt, "Unclaimed constructor remainder")
        context.complete_frame = frame
    else:
        record = context.stack[-1] if context.stack else None
        if (
            record is None
            or record["status"] != "calling_body"
            or record["body"] is not None
            or (
                frame.f_code is not context.bodies[record["method"]].__code__
                or frame.f_back is not record["body_invocation"]
                or frame.f_locals.get("self") is not context.phase
            )
        ):
            _reject_entry(context, attempt, "Unclaimed or detached tail body")
        record["body"] = frame
    attempt["status"] = attempt["work"]["admission"] = "admitted"
    context.admitted_frames[id(frame)] = attempt
    return attempt


@contextmanager
def _account(context):
    get_profile, get_trace = sys.getprofile, sys.gettrace
    set_profile, set_trace = sys.setprofile, sys.settrace
    prior_profile, prior_trace = get_profile(), get_trace()
    codes = {fn.__code__ for fn in context.bodies.values()}
    traces = {}
    frame_errors = {}
    primary, setup_stage = None, None
    context.hook_states = (("before", prior_profile, prior_trace),)
    context.hook_attempts = ()
    context.hook_secondary_errors = ()

    def remember(error, origin, raw):
        previous.handler.captures._remember_observation_error(
            context, error, origin=origin, raw=raw
        )

    def profile(frame, event, arg):
        selected = frame.f_code in codes
        if selected and event == "call":
            attempt = _admit_body(context, frame)
            attempt["hooks"] = (*attempt.get("hooks", ()), "profile")
            _guard(context)
            _check(context)
        if prior_profile is not None:
            if event in ("call", "c_call"):
                prior_profile(frame, event, arg)
            else:
                try:
                    prior_profile(frame, event, arg)
                except BaseException as error:
                    remember(error, "prior_profile_" + event, (frame, event, arg))
        if selected and event == "call":
            _guard(context)
            _check(context)

    def trace(frame, event, arg):
        selected = frame.f_code in codes
        if selected and event == "call":
            # Trace may be delivered before profile. Both share this exact
            # frame's reservation, before either inherited observer runs.
            attempt = _admit_body(context, frame)
            attempt["hooks"] = (*attempt.get("hooks", ()), "trace")
            _guard(context)
            _check(context)
        if selected and event == "exception":
            frame_errors[id(frame)] = arg[1]
            if context.pending_source_error is None and not (
                isinstance(arg[1], literal._CaptureStop) and context.observation_error is not None
            ):
                context.pending_source_error = arg[1]
        if selected and event in ("line", "return", "exception"):
            try:
                _capture_state(context, frame, event)
            except BaseException as error:
                remember(error, "tail_state_" + event, frame)
        if selected and event == "line":
            _guard(context)
            _check(context)
        delegate = prior_trace if event == "call" else traces.get(id(frame))
        if delegate is not None:
            if event in ("return", "exception"):
                try:
                    returned = delegate(frame, event, arg)
                    if returned is not None:
                        traces[id(frame)] = returned
                except BaseException as error:
                    remember(error, "prior_trace_" + event, (frame, event, arg))
            else:
                returned = delegate(frame, event, arg)
                if event == "call" or returned is not None:
                    traces[id(frame)] = returned
        if event == "call" and not selected and traces.get(id(frame)) is None:
            return None
        if event == "return":
            traces.pop(id(frame), None)
            if selected and id(frame) in context.admitted_frames:
                attempt = context.admitted_frames[id(frame)]
                status = "failed" if id(frame) in frame_errors else "returned"
                attempt["status"] = attempt["work"]["admission"] = status
        if selected and event in ("call", "line"):
            _guard(context)
            _check(context)
            if event == "line":
                attempt = context.admitted_frames[id(frame)]
                attempt["body_started"] = attempt["work"]["body_started"] = True
        return trace

    try:
        _guard(context)
        setup_stage = "profile_install"
        context.hook_attempts += ((setup_stage, profile),)
        set_profile(profile)
        setup_stage = "trace_install"
        context.hook_attempts += ((setup_stage, trace),)
        set_trace(trace)
        setup_stage = None
        yield
        _guard(context)
    except BaseException as error:
        if setup_stage is not None:
            context.hook_setup_error = error
        primary = (
            context.entry_error
            if context.entry_error is not None
            else context.pending_source_error
            if context.pending_source_error is not None
            else error
        )
        context.hook_primary = primary
        failure_state = {}
        try:
            failure_state["profile"] = get_profile()
        except BaseException as capture:
            context.hook_secondary_errors += (("profile_failure_state", capture),)
        try:
            failure_state["trace"] = get_trace()
        except BaseException as capture:
            context.hook_secondary_errors += (("trace_failure_state", capture),)
        context.hook_states += (("failure", failure_state),)
        if primary is not error:
            context.hook_secondary_errors += (("observer_execution", error),)
            raise primary  # noqa: B904 -- Preserve the original primary's explicit cause.
        raise
    finally:
        # Setters may install and then raise. Never rely on a successful
        # return to decide whether either previous hook needs restoration.
        cleanup = ()
        try:
            try:
                context.hook_attempts += (("trace_restore", prior_trace),)
                set_trace(prior_trace)
            except BaseException as error:
                cleanup += (("trace_restore", error),)
            finally:
                try:
                    context.hook_attempts += (("profile_restore", prior_profile),)
                    set_profile(prior_profile)
                except BaseException as error:
                    cleanup += (("profile_restore", error),)
            state = {}
            try:
                state["profile"] = get_profile()
            except BaseException as error:
                cleanup += (("profile_state", error),)
            try:
                state["trace"] = get_trace()
            except BaseException as error:
                cleanup += (("trace_state", error),)
            context.hook_states += (("after_restore", state),)
            # One bounded recovery attempt for a setter/observer which refused
            # before changing state. Both recoveries remain independent.
            try:
                if "trace" not in state or state["trace"] is not prior_trace:
                    context.hook_attempts += (("trace_restore_retry", prior_trace),)
                    set_trace(prior_trace)
            except BaseException as error:
                cleanup += (("trace_restore_retry", error),)
            finally:
                try:
                    if "profile" not in state or state["profile"] is not prior_profile:
                        context.hook_attempts += (("profile_restore_retry", prior_profile),)
                        set_profile(prior_profile)
                except BaseException as error:
                    cleanup += (("profile_restore_retry", error),)
            final_state = {}
            try:
                final_state["profile"] = get_profile()
            except BaseException as error:
                cleanup += (("profile_final_state", error),)
            try:
                final_state["trace"] = get_trace()
            except BaseException as error:
                cleanup += (("trace_final_state", error),)
            context.hook_states += (("final", final_state),)
            if final_state.get("profile", object()) is not prior_profile or (
                final_state.get("trace", object()) is not prior_trace
            ):
                cleanup += (("hook_restoration_incomplete", ValueError("Hooks were not restored")),)
        except BaseException as error:
            cleanup += (("hook_cleanup_observation", error),)
        context.hook_cleanup_errors = cleanup
        # Retain failures without invoking a possibly still-installed observer
        # again while recording its own cleanup failure.
        for origin, error in (*context.hook_secondary_errors, *cleanup):
            if context.observation_error is None:
                context.observation_error = error
                context.observation_origin = origin
                context.observation_raw = context.hook_states
            context.observation_errors += ((origin, error),)
        if primary is None:
            _guard(context)


@contextmanager
def _claim(context):
    try:
        with getattr(context.key, KEY_FACTORY)(
            context.refs[9], original_lease=context.refs[10], law_id=KEY_LAW_ID, enabled=True
        ) as claim:
            if type(claim) is not getattr(context.key, KEY_CLAIM_TYPE):
                raise ValueError("Actual newly issued mutation claim required")
            context.claim = claim
            _parameter_check(context)
            yield
    except BaseException as error:
        context.claim_error = error
        try:
            context.claim_partial = getattr(
                error, KEY_ERROR_CONTEXT, getattr(error, "partial", None)
            )
        except BaseException as capture:
            previous.handler.captures._remember_observation_error(
                context, capture, origin="tail_claim_failure", raw=error
            )
        raise
    finally:
        if hasattr(context, "claim"):
            try:
                context.claim_record = context.claim.record
            except BaseException as capture:
                previous.handler.captures._remember_observation_error(
                    context, capture, origin="tail_claim_record", raw=context.claim
                )


def _partial(context):
    return dict(
        context=context,
        parent=context.parent,
        parent_trial=context.refs[1],
        phase=context.phase,
        parameters=context.p,
        sim=context.sim,
        handler=context.handler,
        source_objects=context.objects,
        inherited_links=getattr(context, "inherited_links", None),
        raw_state=getattr(context, "raw_state", None),
        raw_locals=context.locals,
        stores=context.stores,
        stages=context.stages,
        events=context.events,
        work=context.work,
        attempts=context.attempts,
        overflow_attempt=getattr(context, "overflow_attempt", None),
        last_rejected_attempt=getattr(context, "last_rejected_attempt", None),
        method_entries=_entry_document(context),
        entry_attempts=_attempt_document(context),
        entry_error=context.entry_error,
        last_completed=getattr(context, "last_completed", None),
        claim=getattr(context, "claim", None),
        claim_error=getattr(context, "claim_error", None),
        claim_partial=getattr(context, "claim_partial", None),
        claim_record=getattr(context, "claim_record", None),
        hook_primary=getattr(context, "hook_primary", None),
        hook_setup_error=getattr(context, "hook_setup_error", None),
        hook_attempts=getattr(context, "hook_attempts", ()),
        hook_states=getattr(context, "hook_states", ()),
        hook_cleanup_errors=getattr(context, "hook_cleanup_errors", ()),
        hook_secondary_errors=getattr(context, "hook_secondary_errors", ()),
        usable_child_available=False,
    )


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        parent=trial.parent_identity,
        before=trial.before.identity,
        cache=trial.cache.identity,
        stores=trial.stores,
        stages=trial.stages,
        events=trial.events,
        work=trial.work,
        method_entries=trial.method_entries,
        entry_attempts=trial.entry_attempts,
        parameter_claim=None if trial.parameter_claim is None else asdict(trial.parameter_claim),
        completed=trial.completed,
        failure_stage=trial.failure_stage,
        prior_dyna_work_is_separate_and_non_additive=True,
        body_wrapper_work_is_non_additive=True,
        full_phase_world_physical_or_checkpoint_admitted=False,
    )


class PhaseTailOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the genuine issued SEED tail continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No cache hydration or ordinary checkpoint authority")

    @property
    def partial_phase(self):
        return _validate(self).phase

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not PhaseTailOwner or owner not in _ISSUED:
        raise TailRejected("Actual issued SEED-tail child required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active or replaced tail owner")
        _check(context)
        if (
            _allowed_state(context) != STORES
            or tuple(context.stages) != RETURN_ORDER
            or (
                context.stack
                or set(context.claims) != set(METHODS)
                or _entry_document(context) != context.trial.method_entries
                or _attempt_document(context) != context.trial.entry_attempts
                or _snapshot(context).identity != context.trial.cache.identity
                or _digest(trial_record(context.trial)) != context.trial.identity
            )
        ):
            raise ValueError("Sealed tail state changed")
        current = _graph(context)
        literal._same(current[0], context.graph[0])
        if current[1] != context.graph[1]:
            raise ValueError("Sealed tail reference edges changed")
    except BaseException as error:
        context.invalid = True
        raise TailRejected(
            "Stale tail child",
            stage="owner_drift",
            request=context.request,
            trial=context.trial,
            partial=context,
            source_error=error,
        ) from error
    return context


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise TailRejected("Actual SEED tail remains held", stage="release", request=request)
    key = _key_api()
    _parent_api()
    with _LOCK:
        if _ACTIVE:
            _reject_entry(_ACTIVE[-1], None, "Reentrant SEED tail attempt")
        if type(request) is not Request or request not in _REQUESTS:
            raise TailRejected(
                "Actual issued dyna request required", stage="request", request=request
            )
        if request in _CONSUMED:
            raise TailRejected("SEED tail attempt consumed", stage="consumed", request=request)
        refs = _REQUESTS[request]
        context = SimpleNamespace(
            request=request,
            refs=refs,
            parent=refs[0],
            phase=refs[2],
            p=refs[3],
            sim=refs[4],
            handler=refs[7],
            key=key,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="parent_preflight",
            events=[],
            work=[],
            locals={},
            stages=[],
            stores=[],
            attempts=[],
            claims={},
            stack=[],
            root_claimed=False,
            entry_error=None,
            observation_error=None,
            observation_errors=(),
            observation_origin=None,
            observation_raw=None,
            driver_frame=sys._getframe(),
            complete_frame=None,
            complete_invocation=None,
            admitted_frames={},
            pending_source_error=None,
            objects=_objects(refs[0]),
        )
        context.tape = SimpleNamespace(
            rng=None, events=context.events, draws=(), locals=context.locals
        )
        context.stable_tape = _AncestryTape()
        context.stable_fields = [{} for _ in context.objects]
        context.all_fields = [{} for _ in context.objects]
        context.stable_view = SimpleNamespace(objects=context.objects, fields=context.stable_fields)
        context.all_view = SimpleNamespace(objects=context.objects, fields=context.all_fields)
        _CONSUMED[request] = context
        _ACTIVE.append(context)
        primary = None
        try:
            if previous._validate(request.dyna_owner) is not context.parent:
                raise ValueError("Original dyna parent changed")
            context.inherited_links = _registry_links(context)
            context.runtime_bindings = _runtime_bindings(context)
            context.field_names = {
                role: tuple(vars(actual))
                for role, actual in (
                    ("phase", context.phase),
                    ("sim", context.sim),
                    ("parameters", context.p),
                )
            }
            if any(name in context.field_names[role] for role, name in STORES):
                raise ValueError("No retrofitting a previously attempted tail")
            context.export_path = vars(context.p)["init_export_dirname"]
            context.before, context.before_graph = _stable_snapshot(context), _stable_graph(context)
            context.bindings, context.key_bindings = _bindings(), _key_bindings(key)
            _acquire(context)
            _namespace(context)
            context.stage = "dyna_retirement"
            if (
                previous._claim_for_tail(
                    request.dyna_owner,
                    expected=context.parent,
                    transition=context,
                    entries=context.entries,
                )
                is not context.parent
            ):
                raise ValueError("Tail retirement returned a foreign parent")
            with _claim(context):
                _check(context)
                context.stage = "literal_seed_constructor_tail"
                with _account(context):
                    context.complete(context.phase, context.enum.SEED, context.p)
                    context.last_completed = ("complete", context.phase, None)
                    context.stages.append("complete")
                    _guard(context)
                    _check(context)
        except BaseException as error:
            if not isinstance(error, literal._CaptureStop) or context.observation_error is None:
                primary = error
        finally:
            context.active = False
            _ACTIVE.pop()
        partial = _partial(context)
        capture, trial = context.observation_error, None
        try:
            if hasattr(context, "before"):
                record = getattr(context, "claim_record", None)
                if record is not None and not is_dataclass(record):
                    raise ValueError("Typed actual successor parameter record required")
                projector = _projector(context)
                stores = tuple(literal._project(projector, value) for value in context.stores)
                value = Trial(
                    request.identity,
                    refs[1].identity,
                    context.before,
                    _snapshot(context),
                    stores,
                    tuple(context.stages),
                    tuple(name for name, _ in context.events),
                    tuple(context.work),
                    _entry_document(context),
                    _attempt_document(context),
                    record,
                    primary is None and capture is None and tuple(context.stages) == RETURN_ORDER,
                    None if primary is None and capture is None else context.stage,
                    "",
                )
                trial = replace(value, identity=_digest(trial_record(value)))
                context.trial = trial
        except BaseException as error:
            raise TailRejected(
                "Tail trial sealing failed",
                stage="capture",
                request=request,
                partial=partial,
                source_error=primary,
                capture_error=error,
            ) from (primary if primary is not None else error)
        if primary is not None or capture is not None or trial is None:
            raise TailRejected(
                "Original SEED tail refused",
                stage=context.stage,
                request=request,
                trial=trial,
                partial=partial,
                source_error=primary,
                capture_error=capture,
            ) from (primary if primary is not None else capture)
        try:
            _check(context)
            if _allowed_state(context) != STORES or tuple(context.stages) != RETURN_ORDER:
                raise ValueError("Incomplete original tail order")
            context.graph = _graph(context)
            context.owner = object.__new__(PhaseTailOwner)
            _ISSUED[context.owner] = context
            return context.owner
        except BaseException as error:
            context.invalid = True
            raise TailRejected(
                "Tail child sealing failed",
                stage="capture",
                request=request,
                trial=trial,
                partial=partial,
                capture_error=error,
            ) from error


def require_phase(owner):
    context = _validate(owner)
    raise TailRejected(
        "Full Parameters, populated world, init_profiles, init_core and physics remain held",
        stage="phase_incomplete",
        request=context.request,
        trial=context.trial,
        partial=context,
    )


def _world_phase_construct(
    transition, *, world_owner, construction_claim, callback_owner, predecessor
):
    api = _world_api()
    context = api._world_stage_begin(
        sys.modules[__name__],
        3,
        transition,
        world_owner,
        construction_claim,
        callback_owner,
        predecessor,
        sys._getframe(),
    )
    prefix = transition.api.stages[0]._WORLD[transition.request]
    context.phase, context.sim, context.handler = (
        predecessor.phase,
        predecessor.sim,
        predecessor.handler,
    )
    context.claim = construction_claim  # Same ACTIVE interval; no d9/47 claim or record.
    context.refs = (
        context.parent,
        predecessor.trial,
        context.phase,
        context.p,
        context.sim,
        context.phase.cells,
        predecessor.cache,
        context.handler,
        prefix,
    )
    context.objects = api._world_objects(transition, 2)
    context.stages, context.stores, context.attempts, context.stack = [], [], [], []
    context.claims, context.admitted_frames = {}, {}
    context.root_claimed = False
    context.driver_frame = sys._getframe()
    context.complete_frame = context.complete_invocation = None
    context.pending_source_error = None
    primary = None
    try:
        context.field_names = {
            role: tuple(vars(actual))
            for role, actual in (
                ("phase", context.phase),
                ("sim", context.sim),
                ("parameters", context.p),
            )
        }
        if any(name in context.field_names[role] for role, name in STORES):
            raise ValueError("Fresh-world SEED tail may not retrofit existing stores")
        context.export_path = vars(context.p)["init_export_dirname"]
        _acquire(context)
        _namespace(context)
        assembly = transition.api.stages[0]
        with assembly._LOCK:
            if hasattr(prefix, "world_tail") or context.phase in assembly._TAIL_ROUTES:
                raise ValueError("Fresh-world helper route was already attempted")
            prefix.world_tail = context
            assembly._TAIL_ROUTES[context.phase] = context
            context.world_route_issued = True
        context.stage = "fresh_world_original_seed_tail"
        with _account(context):
            context.complete(context.phase, context.enum.SEED, context.p)
            context.last_completed = ("complete", context.phase, None)
            context.stages.append("complete")
            _guard(context)
            _check(context)
        if _allowed_state(context) != STORES or tuple(context.stages) != RETURN_ORDER:
            raise ValueError("Original same-claim SEED tail incomplete")
        context.completed = True
    except BaseException as error:
        if not isinstance(error, literal._CaptureStop) or context.observation_error is None:
            primary = error
    return api._world_stage_finish(context, primary)


def _world_phase_check(
    evidence, *, transition, world_owner, construction_claim, predecessor, closed_record
):
    result = _world_api()._world_stage_check(
        sys.modules[__name__],
        evidence,
        transition,
        world_owner,
        construction_claim,
        predecessor,
        closed_record,
    )
    context = result.authority
    if _allowed_state(context) != STORES or tuple(context.stages) != RETURN_ORDER or context.stack:
        raise ValueError("Original fresh-world SEED helper/store order changed")
    return result


def _world_phase_seal(evidence, *, transition, world_owner, construction_claim, stages):
    return _world_api()._world_seal(evidence, transition, world_owner, construction_claim, stages)


def _world_phase_check_seal(seal, *, transition, world_owner, construction_claim, closed_record):
    return _world_api()._world_check_seal(
        seal, transition, world_owner, construction_claim, closed_record
    )


def _claim_for_seed_world(owner, *, expected, transition, entries):
    return _world_api()._world_claim_prefix(owner, expected, transition, entries)


def _check_world_authority(context):
    return _world_api()._world_after_prefix_claim(context)


def _dispatch_seed_world(prefix, label, delegate, actual, *args, **kwargs):
    api = _world_api()
    retained = api._world_forwarded(prefix.world_transition)
    if retained is not None and hasattr(retained, "voronoi_image"):
        context = prefix.world_transition.api.helpers._voronoi_route(retained)
        return api._world_voronoi_api()._dispatch(
            context, prefix, label, delegate, actual, args, kwargs, sys._getframe()
        )
    context = api._world_prefix_route(prefix)
    caller = sys._getframe(1)
    wrapper = caller.f_back
    module = sys.modules["cells.processes.betse_native_seed_world_prefix"]
    if (
        caller.f_code is not previous.caches.previous._native_call.__code__
        or caller.f_locals.get("context") is not prefix
        or label not in module.METHODS
        or label.split(".")[0] not in ("Cells", "SimPhase")
        or actual is not (context.cells if label.startswith("Cells.") else context.phase)
        or delegate is not getattr(prefix.factories[label.split(".")[0]], label.split(".")[1])
    ):
        module._reject(context, None, "Unadmitted actual world-prefix dispatch")
    return context.entries[label](actual, *args, source_frame=wrapper.f_back, **kwargs)
