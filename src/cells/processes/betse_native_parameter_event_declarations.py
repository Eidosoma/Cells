"""Contiguous native event declarations after numeric prefix, before files.

Compile original load[29:61], preserving its bool/float calls and aliases.
Declaring pressure/cutting/voltage-related data does not admit event execution,
full Parameters, a phase, ions, network/GRN files or INIT. No decoder exists.
"""

import ast
import copy
import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_numeric_prefix as previous

LAW_ID = "betse_native_parameter_event_declarations@1"
PREVIOUS_SHA256 = "84a7d5bb9f4564d61b9dc18ba547c2221faf99f04aff33ecb23182f28720f621"
CLAIMS_SHA256 = "5e942391adc112382e6bc38dcf252f5f615d22ef2f98dbdaa6c00484cdb89ff4"
RELEASE = "CELLS_NATIVE_PARAMETER_EVENT_DECLARATIONS_RELEASED"
START, STOP = 29, 61
SCHEDULED = ("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "pressure", "ecmJ")
GLOBAL = ("K_env", "Cl_env", "Na_env", "gj_block", "T_change", "NaKATP_block")
_BOOL, _FLOAT = bool, float
claims, prefix = previous.claims, previous.previous.paths.prefix
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_ACTIVE = []


class DeclarationsRejected(ValueError):
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
    parent: previous.NumericPrefixOwner
    before_trial_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live declaration requests cannot be serialized")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    before_trial_identity: str
    cache: object
    source_work: tuple
    metadata_work: tuple
    stores: tuple
    source_completed: bool
    identity: str


def _digest(value):
    return previous._digest(value)


def _ast():
    path = prefix.parameters.inherited.tissue.aliases.NATIVE / prefix.parameters.PARAMETERS
    cls = prefix.parameters.inherited._class(ast.parse(path.read_bytes()), "Parameters")
    load = prefix.parameters.inherited._method(cls, "load")
    selected = load.body[START:STOP]
    if (
        ast.unparse(selected[0]) != "self.scheduled_options = {}"
        or ast.unparse(selected[-1])
        != "self.network_config = self._conf.get('general network', None)"
        or ast.unparse(load.body[STOP].test) != "self.network_config is not None"
    ):
        raise ValueError("Native event declaration/file boundary changed")
    return path, cls, load, selected


def source_plan():
    for module, pin in ((previous, PREVIOUS_SHA256), (claims, CLAIMS_SHA256)):
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != pin:
            raise ValueError("Explicit numeric/shared-claim producer required")
    parent = previous.source_plan()
    path, cls, load, selected = _ast()
    if parent["statement_slice"] != (12, START):
        raise ValueError("Contiguous genuine numeric prefix required")
    stores = tuple(
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
        numeric_producer=PREVIOUS_SHA256,
        claims_producer=CLAIMS_SHA256,
        native_pins=parent["native_pins"],
        statement_slice=(START, STOP),
        source_lines=(selected[0].lineno, selected[-1].end_lineno),
        source_body_ast=_digest(ast.dump(ast.Module(body=selected, type_ignores=[]))),
        stores=stores,
        scheduled_order=SCHEDULED,
        global_order=GLOBAL,
        next_source_line=load.body[STOP].lineno,
        next_requires=(
            "original network branch/local YAML version and expression-data file authority"
        ),
        events_callbacks_files_full_Parameters_phase_INIT_admitted=False,
    )


def _compile(context):
    # Reuse the existing original function/header/class/cached-builtins check;
    # its numeric code object is prepared, never evaluated or replayed.
    _, native = previous._compile(context)
    for name, expected in (("bool", _BOOL), ("float", _FLOAT)):
        if name in native.__globals__ or native.__builtins__.get(name) is not expected:
            raise ValueError("Original declaration builtin resolution changed: " + name)
    path, cls, load, selected = _ast()
    cls = copy.deepcopy(cls)
    prefix.parameters.inherited._method(cls, "load").body = copy.deepcopy(selected)
    code = prefix.parameters._method_code(cls, "load", str(path))
    if code.co_freevars:
        raise ValueError("Unexpected earlier local/closure dependency")
    function = FunctionType(code, native.__globals__, native.__name__, None, None)
    if function.__builtins__ is not native.__builtins__:
        raise ValueError("Declaration cached builtins changed")
    return function, native


def _stable(context):
    fields = vars(context.p)
    if tuple(fields)[: len(context.before_names)] != context.before_names:
        raise ValueError("Original parameter field order changed")
    if not set(fields).issubset(set(context.before_names) | set(context.plan["stores"])):
        raise ValueError("Unrelated later parameter store appeared")
    return prefix.graphs.capture(
        {name: fields[name] for name in context.before_names},
        yaml_base=context.birth.source.yaml,
        runtime_types=context.parent.runtime_types,
    )


def _refs(parent):
    return (
        parent.p,
        parent.config,
        parent.birth,
        parent.trial,
        parent.graph,
        parent.parent,
        parent.view,
        parent.runtime_types,
        parent.runtime_files,
        parent.runtime_namespaces,
    )


def _check(context):
    parent = context.parent
    if (
        context.invalid
        or context.thread != get_ident()
        or context.guard.invalid
        or context.active is not context.guard.active
        or not context.guard.audit_ready
        or previous._ISSUED.get(context.owner_parent) is not parent
        or parent.owner is not context.owner_parent
        or parent.active
        or parent.source_completed is not True
        or parent.trial.source_completed is not True
        or parent.invalid is not context.retired
        or any(a is not b for a, b in zip(_refs(parent), context.before, strict=True))
    ):
        raise ValueError("Original numeric parent/claim epoch changed")
    if context.active and any(
        not stack or stack[-1] is not value
        for stack, value in (
            (_ACTIVE, context),
            (previous._ACTIVE, context),
            (claims._ACTIVE, context),
            (previous.previous._ACTIVE, context),
            (previous.previous.paths._ACTIVE, context.guard),
        )
    ):
        raise ValueError("Shared declaration registry changed")
    if (
        context.p is not parent.p
        or context.p._conf is not context.config
        or type(context.p) is not context.birth.source.cls
    ):
        raise ValueError("Actual same-p/configuration/birth association changed")
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    prefix.parameters.inherited._same(previous._bindings(), parent.bindings)
    prefix.parameters.inherited._same(previous.previous._bindings(), parent.parent.bindings)
    prefix.parameters.inherited._same(
        previous.previous._native_bindings(parent.parent), parent.parent.native_bindings
    )
    prefix.parameters.inherited._same(
        prefix.parameters._runtime(context.birth.source), context.birth.runtime
    )
    prefix.parameters.inherited._same(
        prefix._function_bindings(parent.function), parent.function_bindings
    )
    prefix.parameters.inherited._same(
        prefix._function_bindings(parent.original), parent.original_bindings
    )
    if (
        _digest(parent.graph[1]) != context.parent_graph_identity
        or _digest(previous.trial_record(parent.trial)) != parent.trial.identity
    ):
        raise ValueError("Retained numeric graph/trial was resealed or changed")
    prefix.parameters.inherited.tissue.core.caches.validate(parent.trial.cache)
    previous.previous._loaded(parent.parent)
    previous.previous.paths._computed(parent.parent.parent)
    prefix._verify_file(parent.parent.parent.yaml.request.file)
    prefix.parameters.inherited._same_graph(_stable(context), context.stable)
    if _digest(source_plan()) != context.source_identity:
        raise ValueError("Declaration producer changed")
    if hasattr(context, "function"):
        prefix.parameters.inherited._same(
            prefix._function_bindings(context.function), context.function_bindings
        )
        prefix.parameters.inherited._same(
            prefix._function_bindings(context.original), context.original_bindings
        )


def _declarations(context):
    p = context.p
    fields = vars(p)
    if tuple(fields)[len(context.before_names) :] != context.plan["stores"]:
        raise ValueError("Incomplete or reordered declaration stores")
    for name, order in (("scheduled_options", SCHEDULED), ("global_options", GLOBAL)):
        table = fields[name]
        if type(table) is not dict or tuple(table) != order:
            raise ValueError("Native declaration table key order changed: " + name)
        for key, value in table.items():
            if type(value) is int and value == 0:
                continue
            length = (
                5
                if key == "ecmJ"
                else 6
                if name == "scheduled_options"
                else 3
                if key == "NaKATP_block"
                else 4
            )
            if type(value) is not list or len(value) != length:
                raise ValueError("Native declaration shape changed: " + key)
    for key, raw, index in (
        ("Na_mem", "change Na mem", 4),
        ("K_mem", "change K mem", 4),
        ("Cl_mem", "change Cl mem", 4),
        ("Ca_mem", "change Ca mem", 4),
        ("pressure", "apply pressure", 4),
        ("ecmJ", "break ecm junctions", 3),
    ):
        value = p.scheduled_options[key]
        if type(value) is list and value[index] is not context.config[raw]["apply to"]:
            raise ValueError("Actual declared target alias changed: " + key)
    if p.event_cut_profile_names is not context.config["cutting event"]["apply to"]:
        raise ValueError("Actual cutting target alias changed")
    if (
        p.Ca_dyn is not False
        or type(p.event_cut_time) is not float
        or p.event_cut_time.hex() != "0x0.0p+0"
        or p.network_config is not context.config.get("general network", None)
    ):
        raise ValueError("Original fixed declaration/network alias changed")


def _work(context, kind, stage, status):
    context.work.append((len(context.work), kind, stage, status))


@contextmanager
def _claim(owner, purpose):
    if type(owner) is not previous.NumericPrefixOwner or owner not in previous._ISSUED:
        previous._validate(owner)
        raise AssertionError("Unissued numeric validator returned")
    parent = previous._ISSUED[owner]
    context = SimpleNamespace(
        owner_parent=owner,
        parent=parent,
        thread=get_ident(),
        active=True,
        invalid=False,
        retired=False,
        purpose=purpose,
        stage="claim",
        work=[],
        source_work=[],
        locals={},
        observation_error=None,
        observation_errors=(),
        source_completed=False,
        observation_origin=None,
        observation_raw=None,
        capture_errors=(),
        source_error=None,
        guard=SimpleNamespace(
            thread=get_ident(),
            active=True,
            invalid=False,
            directory_depth=0,
            directory_calls=0,
            directory_targets=(),
            filesystem=[],
            audit_ready=False,
        ),
    )
    with claims._registry(owner):
        if (
            _ACTIVE
            or previous._ACTIVE
            or claims._ACTIVE
            or previous.previous._ACTIVE
            or previous.previous.paths._ACTIVE
        ):
            claims._busy(owner, "declaration_claim_conflict")
        _ACTIVE.append(context)
        previous._ACTIVE.append(context)
        claims._ACTIVE.append(context)
        previous.previous._ACTIVE.append(context)
        previous.previous.paths._ACTIVE.append(context.guard)
    try:
        previous.previous.paths._install_audit(context.guard)
        context.bindings = _bindings()
        _work(context, "numeric_parent_validation", "entry", "attempted")
        if previous._validate(owner) is not parent:
            raise ValueError("Foreign numeric parent")
        _work(context, "numeric_parent_validation", "entry", "completed")
        if parent.source_completed is not True or parent.trial.source_completed is not True:
            raise DeclarationsRejected(
                "Actual completed numeric prefix required", stage="numeric_parent", partial=context
            )
        context.p, context.config, context.birth = parent.p, parent.config, parent.birth
        context.before = _refs(parent)
        context.parent_graph_identity = _digest(parent.graph[1])
        context.plan = source_plan()
        context.source_identity = _digest(context.plan)
        context.before_names = tuple(vars(context.p))
        context.stable = _stable(context)
        _check(context)
        yield context
    except BaseException as error:
        context.source_error = error
        raise
    finally:
        try:
            if hasattr(context, "before"):
                _check(context)
                if not context.retired:
                    _work(context, "numeric_parent_validation", "exit", "attempted")
                    previous._validate(owner)
                    _work(context, "numeric_parent_validation", "exit", "completed")
        except BaseException as error:
            context.capture_errors += (("claim_exit", error),)
        try:
            with claims._registry(owner):
                for stack, value in (
                    (previous.previous.paths._ACTIVE, context.guard),
                    (previous.previous._ACTIVE, context),
                    (claims._ACTIVE, context),
                    (previous._ACTIVE, context),
                    (_ACTIVE, context),
                ):
                    if not stack or stack[-1] is not value:
                        raise ValueError("Declaration registry changed before release")
                    stack.pop()
        except BaseException as error:
            context.capture_errors += (("claim_release", error),)
        failed = (
            context.source_error is not None
            or context.invalid
            or context.guard.invalid
            or bool(context.capture_errors)
        )
        context.active = context.guard.active = False
        if failed:
            context.invalid = context.guard.invalid = parent.invalid = True
        if context.source_error is not None:
            try:
                context.source_error.parameter_declaration_claim = context
            except BaseException as error:
                context.capture_errors += (("exception_evidence", error),)
        elif failed:
            raise DeclarationsRejected(
                "Declaration claim issued no success",
                stage="claim_exit",
                partial=context,
                capture_errors=context.capture_errors,
            ) from (context.capture_errors[0][1] if context.capture_errors else None)


def request_record(value):
    return dict(
        law=LAW_ID,
        parent=value.before_trial_identity,
        source=value.source_identity,
        same_p=True,
        no_replay=True,
    )


def from_numeric(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise DeclarationsRejected("Explicit declaration law required", stage="law")
    with _claim(owner, "request") as context:
        if any(name in vars(context.p) for name in context.plan["stores"]):
            raise DeclarationsRejected(
                "Declaration stores already exist", stage="fresh_epoch", partial=context
            )
        value = Request(owner, context.parent.trial.identity, context.source_identity, "")
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = context.before
        return value


def _retire(context):
    _check(context)
    with claims._registry(context.owner_parent):
        if (
            context.invalid
            or context.guard.invalid
            or context.parent.invalid
            or previous._ISSUED.get(context.owner_parent) is not context.parent
        ):
            raise ValueError("Numeric parent changed at retirement")
        context.parent.invalid = True
        context.retired = True
        _work(context, "numeric_parent_retirement", "commit", "completed")


def _invoke(context):
    context.source_work.append(
        dict(operation="native_event_declaration_slice", status="attempted", independent_cases=0)
    )
    with prefix.parameters.inherited.tissue.aliases.issuing_native_imports(
        prefix.parameters.inherited.tissue.source.SOURCE_PINS
    ):
        result = context.function(context.p)
    context.source_work.append(
        dict(operation="native_event_declaration_slice", status="returned", independent_cases=0)
    )
    return result


def trial_record(value):
    return dict(
        law=LAW_ID,
        request=value.request_identity,
        parent=value.before_trial_identity,
        cache=value.cache.identity,
        source_work=value.source_work,
        metadata_work=value.metadata_work,
        stores=value.stores,
        source_completed=value.source_completed,
        files_events_phase_INIT_admitted=False,
    )


class EventDeclarationsOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the issued numeric-to-declarations continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live declaration owners cannot be serialized")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not EventDeclarationsOwner or owner not in _ISSUED:
        raise DeclarationsRejected("Issued event declaration owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced declaration owner")
        _check(context)
        _declarations(context)
        prefix.parameters.inherited._same_graph(prefix._capture(context.view), context.graph)
        kinds, files, namespaces = prefix._runtime_types(context.view)
        if kinds != context.parent.runtime_types or files != context.parent.runtime_files:
            raise ValueError("Original runtime inventory changed")
        prefix.parameters.inherited._same(namespaces, context.parent.runtime_namespaces)
        prefix.parameters.inherited.tissue.core.caches.validate(context.trial.cache)
        if (
            _digest(trial_record(context.trial)) != context.trial.identity
            or prefix.parameters.inherited.tissue.core.caches.snapshot(context.graph[1]).identity
            != context.trial.cache.identity
        ):
            raise ValueError("Declaration graph/cache/trial changed")
    except BaseException as error:
        context.invalid = True
        raise DeclarationsRejected(
            "Stale declaration owner refused",
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
        or os.environ.get(previous.previous.RELEASE) != "1"
    ):
        raise DeclarationsRejected(
            "Actual native declarations remain held", stage="release", request=request
        )
    if _ACTIVE:
        _ACTIVE[-1].invalid = True
        raise DeclarationsRejected(
            "Reentrant declarations refused", stage="reentrant", request=request
        )
    if (
        type(request) is not Request
        or request not in _REQUESTS
        or _digest(request_record(request)) != request.identity
    ):
        raise DeclarationsRejected(
            "Issued exact declaration request required", stage="request", request=request
        )
    if request in _CONSUMED or request.parent in _CLAIMED:
        raise DeclarationsRejected(
            "Declaration attempt consumed", stage="consumed", request=request
        )
    with _claim(request.parent, "advance") as context:
        context.request = request
        _CONSUMED[request] = _CLAIMED[request.parent] = context
        error = None
        try:
            if any(a is not b for a, b in zip(context.before, _REQUESTS[request], strict=True)):
                raise ValueError("Original requested numeric epoch changed")
            if any(name in vars(context.p) for name in context.plan["stores"]):
                raise ValueError("Declarations may not retrofit existing stores")
            context.stage = "source_preparation"
            _work(context, "source_header_compilation", context.stage, "attempted")
            context.function, context.original = _compile(context)
            _work(context, "source_header_compilation", context.stage, "completed")
            context.function_bindings = prefix._function_bindings(context.function)
            context.original_bindings = prefix._function_bindings(context.original)
            _retire(context)
            context.stage = "native_event_declarations"
            with previous._observe(context):
                _invoke(context)
            context.source_completed = True
            if context.observation_error is not None:
                raise context.observation_error
            _check(context)
            _declarations(context)
            context.stage = "declaration_capture"
            context.view = SimpleNamespace(
                p=context.p,
                parent=context.birth,
                file_record=context.parent.file_record,
                runtime_types=context.parent.runtime_types,
            )
            kinds, files, namespaces = prefix._runtime_types(context.view)
            if kinds != context.parent.runtime_types or files != context.parent.runtime_files:
                raise ValueError("Declaration runtime inventory changed")
            prefix.parameters.inherited._same(namespaces, context.parent.runtime_namespaces)
            context.graph = prefix._capture(context.view)
            cache = prefix.parameters.inherited.tissue.core.caches.snapshot(context.graph[1])
            trial = Trial(
                request.identity,
                context.parent.trial.identity,
                cache,
                tuple(context.source_work),
                tuple(context.work),
                tuple(context.plan["stores"]),
                True,
                "",
            )
            context.trial = replace(trial, identity=_digest(trial_record(trial)))
            _check(context)
            prefix.parameters.inherited._same_graph(prefix._capture(context.view), context.graph)
            owner = object.__new__(EventDeclarationsOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as primary:
            if context.stage == "declaration_capture" or primary is context.observation_error:
                prefix.parameters.inherited.tissue.captures._remember_observation_error(
                    context, primary, origin=context.stage, raw=context
                )
            else:
                error = primary
        context.invalid = True
        raise DeclarationsRejected(
            "Native declaration continuation issued no child",
            stage=context.stage,
            request=request,
            partial=context,
            source_error=error,
            capture_errors=context.observation_errors,
        ) from (error if error is not None else context.observation_error)


def require_network(owner):
    context = _validate(owner)
    raise DeclarationsRejected(
        "Original network/GRN/file-load authority remains unavailable",
        stage="network_file_authority",
        partial=dict(
            next_source_line=source_plan()["next_source_line"],
            network_config=context.p.network_config,
            GRN_files_events_phase_INIT_admitted=False,
        ),
        trial=context.trial,
    )


def _bindings():
    functions = (
        _digest,
        _ast,
        source_plan,
        _compile,
        _stable,
        _refs,
        _check,
        _declarations,
        _work,
        _claim,
        _claim.__wrapped__,
        request_record,
        from_numeric,
        _retire,
        _invoke,
        trial_record,
        _validate,
        prepare,
        require_network,
        _bindings,
    )
    return (
        (),
        (
            LAW_ID,
            PREVIOUS_SHA256,
            CLAIMS_SHA256,
            RELEASE,
            START,
            STOP,
            SCHEDULED,
            GLOBAL,
            _BOOL,
            _FLOAT,
            _REQUESTS,
            _CONSUMED,
            _CLAIMED,
            _ISSUED,
            _ACTIVE,
            previous._ACTIVE,
            *claims._bindings()[1],
            *(
                atom
                for fn in functions
                for atom in prefix.parameters.inherited.tissue.aliases._atoms(fn)
            ),
        ),
    )
