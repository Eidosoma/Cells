"""Contiguous same-p native modulator declarations, before colormap loading.

The actual issued GRN owner is retired once. Earlier stores and source/runtime
associations remain audited from their retained objects, never a reissued owner
or a restored cache. Actual source/float work needs both explicit releases.
"""

import ast
import copy
import hashlib
import os
import struct
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_grn_variables as previous

LAW_ID = "betse_native_parameter_contiguous_modulators@1"
PREVIOUS_SHA256 = "807a95be3521e60721af0d2cfd49dd0048a110e908851c63fd0f357ab703c949"
RELEASE = "CELLS_NATIVE_PARAMETER_MODULATORS_RELEASED"
START, STOP = 109, 135
prefix, claims, subconfigs = previous.prefix, previous.claims, previous.subconfigs
_FLOAT = float
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_ACTIVE = []


class ModulatorsRejected(ValueError):
    def __init__(
        self, reason, *, stage, request=None, partial=None, source_error=None, capture_errors=()
    ):
        super().__init__(reason)
        self.stage, self.request, self.partial = stage, request, partial
        self.source_error, self.capture_errors = source_error, tuple(capture_errors)


class _ObserverStop(RuntimeError):
    pass


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    parent: previous.GrnVariablesOwner
    parent_trial_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live modulator requests cannot be serialized")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_trial_identity: str
    cache: object
    source_work: tuple
    metadata_work: tuple
    stores: tuple
    source_completed: bool
    identity: str


def _digest(value):
    return previous._digest(value)


def _ast():
    path, cls, load, _ = previous._ast()
    selected = load.body[START:STOP]
    if (
        START != previous.STOP
        or len(selected) != 26
        or ast.unparse(selected[0]) != "self.gradient_x_properties = {}"
        or ast.unparse(selected[-1].test) != "chk2 is not None"
        or ast.unparse(selected[-1].orelse[0]) != "self.mod_single_cell_offset = None"
        or ast.unparse(load.body[STOP])
        != "self.default_cm = mplcolormap.get_colormap(self.colormap_diverging_name)"
    ):
        raise ValueError("Original contiguous modulator/colormap boundary changed")
    return path, cls, load, selected


def source_plan():
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PREVIOUS_SHA256:
        raise ValueError("Exact accepted completed GRN producer required")
    parent = previous.source_plan()
    _, _, load, selected = _ast()
    stores = tuple(
        dict.fromkeys(
            n.targets[0].attr
            for stmt in selected
            for n in ast.walk(stmt)
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Attribute)
            and isinstance(n.targets[0].value, ast.Name)
            and n.targets[0].value.id == "self"
        )
    )
    return dict(
        law=LAW_ID,
        predecessor=PREVIOUS_SHA256,
        native_pins=parent["native_pins"],
        statement_slice=(START, STOP),
        source_lines=(selected[0].lineno, selected[-1].end_lineno),
        source_body_ast=_digest(ast.dump(ast.Module(body=selected, type_ignores=[]))),
        stores=stores,
        next_source_line=load.body[STOP].lineno,
        next_prerequisite=(
            "actual original mplcolormap.get_colormap and alias/config/runtime authority"
        ),
        native_float_call_sites=17,
        optional_float_call_sites=1,
        projection=False,
        replacement_parameter=False,
        full_Parameters_constants_ions_constructor_phase_INIT_admitted=False,
    )


def _fields(context):
    return prefix.graphs.capture(
        {n: vars(context.p)[n] for n in context.before},
        yaml_base=context.birth.source.yaml,
        runtime_types=context.runtime.runtime_types,
    )


def _refs(parent):
    return (
        parent.p,
        parent.parent,
        parent.parent_owner,
        parent.birth,
        parent.runtime,
        parent.authority,
        parent.ancestry,
        parent.view,
        parent.graph,
        parent.trial,
        parent.request,
        parent.function,
        parent.function_bindings,
        parent.methods,
        parent.native_bindings,
        parent.bindings,
        parent.counts,
        parent.completed,
        parent.decoded,
        parent.stream,
        parent.parser,
    )


def _protocol(parent):
    return prefix.graphs.capture(
        dict(
            counts=parent.counts,
            completed=parent.completed,
            enabled=parent.enabled,
            decoded_observed=parent.decoded_observed,
            source_completed=parent.source_completed,
            work=parent.work,
            metadata_work=parent.metadata_work,
            observations=parent.trial.observations,
        ),
        yaml_base=parent.birth.source.yaml,
        runtime_types=parent.runtime.runtime_types,
    )


def _parent(context):
    parent = context.parent
    if (
        previous._ISSUED.get(context.parent_owner) is not parent
        or parent.owner is not context.parent_owner
        or parent.p is not context.p
        or parent.active is not False
        or parent.guard.active is not False
        or parent.guard.invalid
        or parent.invalid is not context.retired
        or parent.source_completed is not True
        or parent.source_error is not None
        or parent.capture_errors
        or parent.observation_error is not None
        or any(a is not b for a, b in zip(_refs(parent), context.parent_refs, strict=True))
        or _digest(previous.trial_record(parent.trial)) != context.parent_trial_identity
        or _digest(parent.graph[1]) != context.parent_graph_identity
        or parent.request.source_identity != _digest(previous.source_plan())
        or previous._digest(previous.request_record(parent.request)) != parent.request.identity
        or previous._CONSUMED.get(parent.request) is not parent
        or previous._CLAIMED.get(parent.parent_owner) is not parent
    ):
        raise ValueError("Original completed GRN/parameter/source epoch changed")
    prefix.parameters.inherited._same_graph(_protocol(parent), context.parent_protocol)
    if tuple((e["role"], e["event"]) for e in parent.events) != parent.trial.observations:
        raise ValueError("Original GRN event accounting changed")
    prefix.parameters.inherited._same(previous._bindings(), parent.bindings)
    prefix.parameters.inherited._same(previous._ancestry(parent), parent.ancestry)
    previous.previous.previous._check(parent.parent.bound)
    prefix.parameters.inherited._same(
        prefix._function_bindings(parent.function), parent.function_bindings
    )
    prefix.parameters.inherited._same(previous._native_bindings(parent), parent.native_bindings)
    if parent.parser is not None:
        previous.previous._parser_receiver(parent.parent.api, parent.parser)
    prefix.parameters.inherited.tissue.core.caches.validate(parent.trial.cache)
    if (
        prefix.parameters.inherited.tissue.core.caches.snapshot(parent.graph[1]).identity
        != parent.trial.cache.identity
    ):
        raise ValueError("Historical GRN cache evidence changed")
    # Values come from the actual p, not a filtered/reconstructed Parameters.
    # New fields are allowed only by this exact contiguous source domain.
    fields = vars(context.p)
    if tuple(fields)[: len(context.before)] != context.before or not set(fields).issubset(
        set(context.before) | set(context.plan["stores"])
    ):
        raise ValueError("Earlier field order or unowned later parameter stores changed")
    prefix.parameters.inherited._same_graph(_fields(context), context.before_graph)


def _stacks(context):
    return ((_ACTIVE, context), *previous._stacks(context))


@contextmanager
def _claim(owner):
    if type(owner) is not previous.GrnVariablesOwner or owner not in previous._ISSUED:
        previous._validate(owner)
        raise AssertionError("Unissued GRN validator returned")
    parent = previous._ISSUED[owner]
    context = SimpleNamespace(
        parent_owner=owner,
        parent=parent,
        p=parent.p,
        birth=parent.birth,
        runtime=parent.runtime,
        thread=get_ident(),
        active=True,
        invalid=False,
        retired=False,
        stage="admission",
        work=[],
        metadata_work=[],
        events=[],
        locals={},
        raw_return=None,
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
        capture_errors=(),
        source_error=None,
        source_completed=False,
        entries=0,
        returns=0,
        failure_graph=None,
        source_return_graph=None,
        stop=_ObserverStop("Modulator observation incomplete"),
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
        if any(stack for stack, _ in _stacks(context)):
            claims._busy(owner, "modulators_conflict")
        for stack, value in _stacks(context):
            stack.append(value)
    try:
        subconfigs.paths._install_audit(context.guard)
        context.metadata_work.append(("GRN_parent_verification", "attempted"))
        if previous._validate(owner) is not parent:
            raise ValueError("Foreign GRN parent verification")
        context.metadata_work.append(("GRN_parent_verification", "completed"))
        context.plan = source_plan()
        context.before = tuple(vars(context.p))
        if set(context.before) & set(context.plan["stores"]):
            raise ValueError("Modulator stores cannot retrofit an existing parameter")
        context.parent_refs, context.parent_protocol = _refs(parent), _protocol(parent)
        context.parent_trial_identity, context.parent_graph_identity = (
            parent.trial.identity,
            _digest(parent.graph[1]),
        )
        context.before_graph = _fields(context)
        context.bindings = _bindings()
        yield context
    except BaseException as error:
        context.operation_error = error
        raise
    finally:
        try:
            if context.retired:
                if parent.invalid is not True:
                    raise ValueError("Retired GRN owner rearmed")
            else:
                previous._validate(owner)
            if context.invalid or context.guard.invalid:
                raise ValueError("Poisoned modulator claim")
        except BaseException as error:
            context.capture_errors += (("claim_exit", error),)
        try:
            with claims._registry(owner):
                for stack, value in reversed(_stacks(context)):
                    if not stack or stack[-1] is not value:
                        raise ValueError("Modulator activity registry changed")
                    stack.pop()
        except BaseException as error:
            context.capture_errors += (("claim_release", error),)
        context.active = context.guard.active = False
        failed = (
            getattr(context, "operation_error", None) is not None
            or context.invalid
            or bool(context.capture_errors)
        )
        if failed:
            context.invalid = context.guard.invalid = parent.invalid = True
        primary = getattr(context, "operation_error", None)
        if primary is not None:
            try:
                primary.modulators_claim = context
            except BaseException as error:
                context.capture_errors += (("exception_evidence", error),)
        elif failed:
            raise ModulatorsRejected(
                "Modulator claim issued no child",
                stage="claim_exit",
                partial=context,
                capture_errors=context.capture_errors,
            ) from context.capture_errors[0][1]


def request_record(value):
    return dict(
        law=LAW_ID,
        parent=value.parent_trial_identity,
        source=value.source_identity,
        same_p=True,
        once=True,
    )


def from_grn(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise ModulatorsRejected("Explicit contiguous modulator law required", stage="law")
    with _claim(owner) as context:
        value = Request(owner, context.parent_trial_identity, _digest(context.plan), "")
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (context.parent_refs, value.identity)
        return value


def _compile(context):
    original = context.parent.parent.bound.original
    prefix._function_bindings(original)
    if "float" in original.__globals__ or original.__builtins__.get("float") is not _FLOAT:
        raise ValueError("Original modulator float resolution changed")
    path, cls, _, selected = _ast()
    cls = copy.deepcopy(cls)
    prefix.parameters.inherited._method(cls, "load").body = copy.deepcopy(selected)
    code = prefix.parameters._method_code(cls, "load", str(path))
    if code.co_freevars:
        raise ValueError("Unowned modulator source closure")
    function = FunctionType(code, original.__globals__, original.__name__, None, None)
    if function.__builtins__ is not original.__builtins__:
        raise ValueError("Modulator cached builtins changed")
    return function


def _check(context):
    if (
        context.invalid
        or context.guard.invalid
        or context.thread != get_ident()
        or context.active is not context.guard.active
        or not context.guard.audit_ready
    ):
        raise ValueError("Closed/poisoned/foreign modulator epoch")
    if context.active and any(
        not stack or stack[-1] is not value for stack, value in _stacks(context)
    ):
        raise ValueError("Modulator active registry changed")
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    if _digest(source_plan()) != _digest(context.plan):
        raise ValueError("Modulator source domain changed")
    _parent(context)
    if hasattr(context, "function"):
        prefix.parameters.inherited._same(
            prefix._function_bindings(context.function), context.function_bindings
        )
        if (
            context.request.identity != _REQUESTS[context.request][1]
            or _digest(request_record(context.request)) != context.request.identity
            or context.request.source_identity != _digest(context.plan)
        ):
            raise ValueError("Issued modulator source request changed")


def _capture(context, origin, error, raw):
    prefix.parameters.inherited.tissue.captures._remember_observation_error(
        context, error, origin=origin, raw=raw
    )


def _copy_locals(frame):
    return dict(frame.f_locals)


def _returned(context, frame, value):
    context.raw_return = (frame, value)
    local = _copy_locals(frame)
    context.locals = local
    context.source_return_graph = prefix.graphs.capture(
        dict(vars(context.p)),
        yaml_base=context.birth.source.yaml,
        runtime_types=context.runtime.runtime_types,
    )
    context.events.append(("return", local))
    context.returns += 1


@contextmanager
def _observe(context):
    prior, trace = sys.getprofile(), sys.gettrace()

    def profile(frame, event, arg):
        selected = frame.f_code is context.function.__code__
        if selected and event == "call":
            _check(context)
            context.entries += 1
            if context.entries != 1 or frame.f_locals.get("self") is not context.p:
                raise ValueError("Duplicate/foreign modulator source entry")
            context.events.append(("entry", dict(frame.f_locals)))
        elif selected and event == "return":
            try:
                _returned(context, frame, arg)
            except BaseException as error:
                _capture(context, "modulator_return_capture", error, (frame, arg))
        if prior is not None:
            if selected and event == "return":
                try:
                    prior(frame, event, arg)
                except BaseException as error:
                    _capture(context, "inherited_return_capture", error, (frame, arg))
            else:
                prior(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(prior)
        sys.settrace(trace)


def _invoke(context):
    context.work.append(
        dict(
            sequence=len(context.work),
            layer="original_modulator_slice",
            status="attempt_not_case_credit",
            scalar_conversion_attempts="inside_literal_source; no separate completed-scalar claim",
        )
    )
    return context.function(context.p)


def _outputs(context):
    fields, cfg = vars(context.p), vars(context.p)["_conf"]["modulator function properties"]
    if context.source_return_graph is None:
        raise ValueError("Complete original modulator return capture required")
    prefix.parameters.inherited._same_graph(
        prefix.graphs.capture(
            dict(fields),
            yaml_base=context.birth.source.yaml,
            runtime_types=context.runtime.runtime_types,
        ),
        context.source_return_graph,
    )
    if tuple(fields)[len(context.before) :] != context.plan["stores"]:
        raise ValueError("Original modulator store order incomplete")
    names = (
        "gradient_x_properties",
        "gradient_y_properties",
        "gradient_r_properties",
        "periodic_properties",
        "f_scan_properties",
    )
    values = tuple(fields[n] for n in names)
    if (
        len({id(v) for v in values}) != 5
        or any(type(v) is not dict for v in values)
        or any(v is old for v in values for old in context.before_graph[0])
    ):
        raise ValueError("Actual fresh distinct native modulator dictionaries required")
    for value, keys in zip(
        values,
        (("slope", "x-offset", "z-offset", "exponent"),) * 3
        + (("frequency", "phase"), ("f start", "f stop", "f slope")),
        strict=True,
    ):
        if tuple(value) != keys:
            raise ValueError("Original modulator key ordering changed")
        if any(type(v) is not float for k, v in value.items() if k != "f slope"):
            raise ValueError("Original float result type changed")
    if fields["f_scan_properties"]["f slope"] is not None:
        raise ValueError("Sweep slope must remain unset until genuine factory mutation")
    bitmap, single = cfg.get("gradient_bitmap"), cfg.get("single_cell")
    if (
        context.locals.get("self") is not context.p
        or context.locals.get("chk") is not bitmap
        or context.locals.get("chk2") is not single
    ):
        raise ValueError("Original final source locals/configuration associations changed")
    if (
        context.entries != 1
        or context.returns != 1
        or context.raw_return is None
        or context.raw_return[1] is not None
    ):
        raise ValueError("Original modulator source did not return once normally")
    if bitmap is None:
        if fields["grad_bm_fn"] is not None or fields["grad_bm_offset"] is not None:
            raise ValueError("Absent bitmap branch changed")
    elif fields["grad_bm_fn"] is not bitmap["file"] or (
        "z-offset" in bitmap and fields["grad_bm_offset"] is not bitmap["z-offset"]
    ):
        raise ValueError("Original bitmap declaration alias changed")
    elif "z-offset" not in bitmap and (
        type(fields["grad_bm_offset"]) is not float
        or struct.pack(">d", fields["grad_bm_offset"]) != b"\x00" * 8
    ):
        raise ValueError("Original bitmap offset default changed")
    if (single is None and fields["mod_single_cell_offset"] is not None) or (
        single is not None and type(fields["mod_single_cell_offset"]) is not float
    ):
        raise ValueError("Original single-cell declaration branch changed")


def trial_record(value):
    return dict(
        law=LAW_ID,
        request=value.request_identity,
        parent=value.parent_trial_identity,
        cache=value.cache.identity,
        source_work=value.source_work,
        metadata_work=value.metadata_work,
        stores=value.stores,
        source_completed=value.source_completed,
        full_Parameters_constants_ions_constructor_phase_INIT_admitted=False,
    )


class ModulatorsOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use actual once-only GRN-to-modulator continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live modulator owners cannot be serialized")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not ModulatorsOwner or owner not in _ISSUED:
        raise ModulatorsRejected("Actual issued modulator owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced modulator owner")
        _check(context)
        _outputs(context)
        prefix.parameters.inherited._same_graph(prefix._capture(context.view), context.graph)
        cache = prefix.parameters.inherited.tissue.core.caches
        cache.validate(context.trial.cache)
        if (
            _digest(trial_record(context.trial)) != context.trial.identity
            or cache.snapshot(context.graph[1]).identity != context.trial.cache.identity
        ):
            raise ValueError("Modulator result/trial changed")
        kinds, files, namespaces = prefix._runtime_types(context.view)
        if kinds != context.runtime.runtime_types or files != context.runtime.runtime_files:
            raise ValueError("Unowned modulator runtime introduced")
        prefix.parameters.inherited._same(namespaces, context.runtime.runtime_namespaces)
    except BaseException as error:
        context.invalid = True
        raise ModulatorsRejected(
            "Stale modulator owner", stage="owner_drift", partial=context, source_error=error
        ) from error
    return context


def prepare(request, *, enabled=False):
    if (
        enabled is not True
        or os.environ.get(RELEASE) != "1"
        or os.environ.get(previous.RELEASE) != "1"
    ):
        raise ModulatorsRejected(
            "Original modulator source/float work held", stage="release", request=request
        )
    if _ACTIVE:
        _ACTIVE[-1].invalid = True
        raise ModulatorsRejected(
            "Reentrant modulator work refused", stage="reentrant", request=request
        )
    if (
        type(request) is not Request
        or request not in _REQUESTS
        or _digest(request_record(request)) != request.identity
    ):
        raise ModulatorsRejected(
            "Issued same-p modulator request required", stage="request", request=request
        )
    if request in _CONSUMED or request.parent in _CLAIMED:
        raise ModulatorsRejected("Modulator attempt consumed", stage="consumed", request=request)
    with _claim(request.parent) as context:
        _CONSUMED[request] = _CLAIMED[request.parent] = context
        context.request = request
        primary = None
        try:
            old = _REQUESTS[request]
            if (
                any(a is not b for a, b in zip(context.parent_refs, old[0], strict=True))
                or request.identity != old[1]
                or request.parent_trial_identity != context.parent_trial_identity
                or request.source_identity != _digest(context.plan)
            ):
                raise ValueError("Actual issued modulator source/parent association changed")
            context.stage = "source_binding"
            context.function = _compile(context)
            context.function_bindings = prefix._function_bindings(context.function)
            _check(context)
            with claims._registry(context.parent_owner):
                if (
                    context.parent.invalid
                    or previous._ISSUED.get(context.parent_owner) is not context.parent
                ):
                    raise ValueError("GRN owner changed at retirement")
                context.parent.invalid = context.retired = True
                context.metadata_work.append(("GRN_parent_retirement", "completed"))
            context.stage = "native_modulators"
            with _observe(context):
                _invoke(context)
            context.source_completed = True
            if context.observation_error is not None:
                raise context.stop
            _check(context)
            _outputs(context)
            context.stage = "graph_capture"
            context.view = SimpleNamespace(
                p=context.p,
                parent=context.birth,
                file_record=context.runtime.file_record,
                runtime_types=context.runtime.runtime_types,
            )
            kinds, files, namespaces = prefix._runtime_types(context.view)
            if kinds != context.runtime.runtime_types or files != context.runtime.runtime_files:
                raise ValueError("Unowned modulator runtime introduced")
            prefix.parameters.inherited._same(namespaces, context.runtime.runtime_namespaces)
            context.graph = prefix._capture(context.view)
            cache = prefix.parameters.inherited.tissue.core.caches.snapshot(context.graph[1])
            value = Trial(
                request.identity,
                context.parent_trial_identity,
                cache,
                tuple(context.work),
                tuple(context.metadata_work),
                context.plan["stores"],
                True,
                "",
            )
            context.trial = replace(value, identity=_digest(trial_record(value)))
            _check(context)
            owner = object.__new__(ModulatorsOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            if error is not context.stop:
                primary = error
        context.source_error = primary
        try:
            context.failure_graph = prefix.graphs.capture(
                dict(vars(context.p)),
                yaml_base=context.birth.source.yaml,
                runtime_types=context.runtime.runtime_types,
            )
        except BaseException as error:
            context.capture_errors += (("failure_graph", error),)
        context.invalid = True
        raise ModulatorsRejected(
            "Original modulator source issued no child",
            stage=context.stage,
            request=request,
            partial=context,
            source_error=primary,
            capture_errors=(*context.observation_errors, *context.capture_errors),
        ) from (primary if primary is not None else context.observation_error)


def require_continuation(owner):
    context = _validate(owner)
    raise ModulatorsRejected(
        "Original colormap/export/constants/ion-profile authority remains required",
        stage="next_prerequisite",
        partial=dict(
            next_source_line=1007,
            same_p=True,
            current_trial=context.trial.identity,
            no_native_colormap_or_ion_work=True,
        ),
    )


def _bindings():
    functions = (
        _digest,
        _ast,
        source_plan,
        _fields,
        _refs,
        _protocol,
        _parent,
        _stacks,
        _claim,
        _claim.__wrapped__,
        request_record,
        from_grn,
        _compile,
        _check,
        _capture,
        _copy_locals,
        _returned,
        _observe,
        _observe.__wrapped__,
        _invoke,
        _outputs,
        trial_record,
        _validate,
        prepare,
        require_continuation,
        _bindings,
        ModulatorsOwner.__init__,
        ModulatorsOwner.__reduce_ex__,
        ModulatorsOwner.parameters.fget,
        ModulatorsOwner.trial.fget,
    )
    return (
        (),
        (
            LAW_ID,
            PREVIOUS_SHA256,
            RELEASE,
            START,
            STOP,
            _FLOAT,
            _REQUESTS,
            _CONSUMED,
            _CLAIMED,
            _ISSUED,
            _ACTIVE,
            ModulatorsOwner,
            Request,
            Trial,
            ModulatorsRejected,
            get_ident,
            struct.pack,
            *claims._bindings()[1],
            *(
                atom
                for f in functions
                for atom in prefix.parameters.inherited.tissue.aliases._atoms(f)
            ),
        ),
    )
