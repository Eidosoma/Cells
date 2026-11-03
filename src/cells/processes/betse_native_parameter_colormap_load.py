"""One released, original same-p four-colormap load and retained successor.

No import/factory is used to discover dependencies. A genuine issued registry
state and loaded pinned runtime are required only at the guarded start. All
original helpers run through the unmodified compiled native four statements.
"""

import ast
import copy
import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

import numpy as np

from cells.processes import betse_native_parameter_colormap_runtime as runtime
from cells.processes import betse_native_parameter_colormap_state as state

LAW_ID = "betse_native_parameter_original_four_colormap_stores@1"
STATE_SHA256 = "7380129b5eb2b0177144785adaa410ed053e714403a168fe66a6d938d1ae4489"
RELEASE = "CELLS_NATIVE_PARAMETER_COLORMAP_LOAD_RELEASED"
MAX_WORK, MAX_LOOKUPS = 20000, 4
boundary, prefix = state.previous, state.prefix
mod = boundary.previous
claims = mod.claims
_LOCK, _ACTIVE = Lock(), []
_ISSUED, _CONSUMED, _PARENTS = (WeakKeyDictionary() for _ in range(3))


class ColormapLoadRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None, source_error=None, capture_errors=()):
        super().__init__(reason)
        self.stage, self.partial, self.source_error = stage, partial, source_error
        self.capture_errors = tuple(capture_errors)


@dataclass(frozen=True, slots=True)
class Trial:
    registry_identity: str
    boundary_identity: str
    parent_trial_identity: str
    before_identity: str
    after_identity: str
    work: tuple
    calls: tuple
    metadata_work: tuple
    source_completed: bool
    identity: str


class ColormapsOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use released prepare from an actual registry-state owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live native colormap successor is not a pickle/checkpoint")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


def _digest(value):
    return state._digest(value)


def _metadata_code():
    """Exact original metadata prefix; new whole-before graph replaces tail."""
    path = Path(mod.__file__)
    if hashlib.sha256(path.read_bytes()).hexdigest() != boundary.PREVIOUS_SHA256:
        raise ValueError("Exact unchanged modulator metadata producer required")
    tree = ast.parse(path.read_bytes())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_parent")
    removed = [ast.unparse(n) for n in node.body[-3:]]
    if (
        removed[0] != "fields = vars(context.p)"
        or "Earlier field order or unowned later parameter stores changed" not in removed[1]
        or removed[2]
        != "prefix.parameters.inherited._same_graph(_fields(context), context.before_graph)"
    ):
        raise ValueError("Original modulator stable-field guard boundary changed")
    selected = copy.deepcopy(node)
    selected.body = selected.body[:-3]
    code = boundary._context_code(node, str(path), replacement=selected)
    original = mod._parent
    prefix._function_bindings(original)
    function = FunctionType(code, original.__globals__, "_parent")
    if function.__builtins__ is not original.__builtins__:
        raise ValueError("Historical metadata cached builtins changed")
    return function, _digest(ast.dump(selected)), tuple(removed)


def source_plan():
    if state._file(state.__file__)[1] != STATE_SHA256:
        raise ValueError("Exact selected-registry source producer required")
    _, metadata_ast, replaced = _metadata_code()
    return dict(
        law=LAW_ID,
        state_producer=STATE_SHA256,
        state=state.source_plan(),
        runtime=runtime.declaration(),
        runtime_producer=(
            "src/cells/processes/betse_native_parameter_colormap_runtime.py",
            state._file(runtime.__file__)[1],
        ),
        source_lines=(1007, 1014),
        next_line=1017,
        native_statement_slice=(135, 139),
        native_source_unchanged=True,
        historical_metadata_ast=metadata_ast,
        replaced_p_field_tail=replaced,
        replacement="Exact actual whole-before p graph + only four literal stores/copy relations",
        max_source_work=MAX_WORK,
        max_lookups=MAX_LOOKUPS,
        original_helper_registry_copy_invocation_implemented=True,
        start_requires_explicit_release=True,
        callback_evaluations_allowed=False,
        complete_Parameters_ions_profiles_Simulator_INIT_admitted=False,
    )


def _fields(context):
    return prefix.graphs.capture(
        {name: vars(context.p)[name] for name in context.before_names},
        yaml_base=context.parent.birth.source.yaml,
        runtime_types=context.parent.runtime.runtime_types,
    )


def _parent_refs(context):
    return tuple((name, value) for name, value in vars(context.parent).items() if name != "invalid")


def _stacks(context):
    return ((_ACTIVE, context), *boundary._stacks(context), (state._ACTIVE, context))


def _reserve(owner):
    if type(owner) is not state.ColormapRegistryState or owner not in state._ISSUED:
        raise ColormapLoadRejected("Actual issued selected-registry owner required", stage="owner")
    source = state._ISSUED[owner]
    bound = source.bound
    if not _LOCK.acquire(blocking=False):
        raise ColormapLoadRejected("Colormap reservation busy", stage="reservation")
    try:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise ColormapLoadRejected("Reentrant colormap source refused", stage="reentrant")
        if owner in _CONSUMED or bound.parent_owner in _PARENTS:
            raise ColormapLoadRejected("Original colormap attempt consumed", stage="consumed")
        context = SimpleNamespace(
            source_owner=owner,
            source=source,
            bound=bound,
            parent_owner=bound.parent_owner,
            parent=bound.parent,
            p=bound.p,
            thread=get_ident(),
            active=True,
            invalid=False,
            retired=False,
            registered=False,
            source_error=None,
            capture_errors=(),
            observation_errors=(),
            stage="admission",
            work=[],
            metadata_work=[],
            raw=[],
            events=[],
            calls=dict(slice=0, helper=0, registry=0, checked=0, copy=0, copy_body=0, np_copy=0),
            returns={
                name: []
                for name in (
                    "slice",
                    "helper",
                    "registry",
                    "checked",
                    "copy",
                    "copy_body",
                    "np_copy",
                )
            },
            source_completed=False,
            failure_capture=None,
            after=None,
            validating=False,
            observations=[],
            validations=[],
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
        _CONSUMED[owner] = _PARENTS[bound.parent_owner] = context
        _ACTIVE.append(context)
        return context
    finally:
        _LOCK.release()


def _historical_metadata(context, parent):
    function = context.metadata_function
    prefix.parameters.inherited._same(
        prefix._function_bindings(function), context.metadata_function_bindings
    )
    function(parent)
    prefix.parameters.inherited._same(
        prefix._function_bindings(context.metadata_function), context.metadata_function_bindings
    )


def _history(context):
    source, bound, parent = context.source, context.bound, context.parent
    if (
        state._ISSUED.get(context.source_owner) is not source
        or source.owner is not context.source_owner
        or source.bound is not bound
        or boundary._ISSUED.get(source.boundary) is not bound
        or mod._ISSUED.get(context.parent_owner) is not parent
        or parent.owner is not context.parent_owner
        or parent.p is not context.p
        or parent.invalid is not context.retired
        or parent.active
        or parent.guard.invalid
        or source.invalid is not context.retired
        or source.active
        or source.validating
        or source.source_error is not None
        or source.record is not context.registry_record
        or source.record is not source.original_record
        or bound.parent is not parent
        or bound.p is not context.p
        or bound.parent_owner is not context.parent_owner
        or bound.claim.invalid
        or bound.claim.guard.invalid
        or bound.claim.capture_errors
        or bound.binding is not context.boundary_record
        or bound.original is not parent.function
        or bound.function is not context.function
    ):
        raise ValueError("Historical original registry/input/parameter retirement relation changed")
    current = _parent_refs(context)
    if len(current) != len(context.parent_refs) or any(
        a[0] != b[0] or a[1] is not b[1] for a, b in zip(current, context.parent_refs, strict=True)
    ):
        raise ValueError("Historical modulator record/source metadata changed")
    _historical_metadata(context, parent)
    prefix.parameters.inherited._same(mod._bindings(), parent.bindings)
    prefix.parameters.inherited._same(state._bindings(), source.bindings)
    prefix.parameters.inherited._same(
        prefix._function_bindings(parent.function), parent.function_bindings
    )
    if (
        _digest(mod.trial_record(parent.trial)) != parent.trial.identity
        or _digest(boundary.binding_record(bound.binding)) != bound.binding.identity
        or _digest(state.record_document(source.record)) != source.record.identity
        or source.record.graph_identity != source.capture.identity
        or source.record.metadata_work != tuple(source.work)
        or _digest(state.source_plan()) != source.record.source_identity
    ):
        raise ValueError("Original typed successful records/source identity changed")
    prefix.parameters.inherited._same(boundary._bindings(), bound.bindings)
    names_before, values_before = bound.before
    if names_before != tuple(vars(parent)) or any(
        (old is not False if name == "invalid" else vars(parent)[name] is not old)
        for name, old in zip(names_before, values_before, strict=True)
    ):
        raise ValueError("Original input boundary's historical parent metadata changed")
    names, aliases = boundary._configuration(parent)
    if any(a is not b for a, b in zip(names, bound.binding.names, strict=True)):
        raise ValueError("Actual raw source alias/name association changed")
    prefix.parameters.inherited._same(aliases, bound.aliases)
    prefix.parameters.inherited._same(
        boundary._native_bindings(boundary._native(parent)), bound.native_bindings
    )
    prefix.parameters.inherited._same(
        prefix._function_bindings(bound.function), bound.function_bindings
    )
    if _digest(boundary.source_plan()) != bound.source_identity:
        raise ValueError("Original input source domain changed")
    holder = SimpleNamespace(partial_capture=None)
    observed = state._observe(bound, holder)
    context.observations.append(("registry_rebind", observed.array_copies, observed.callbacks))
    state._same(observed, source.capture)
    prefix.parameters.inherited._same_graph(_fields(context), context.before_graph)
    fields = vars(context.p)
    appended = tuple(fields)[len(context.before_names) :]
    expected = tuple(row[0] for row in boundary.ROLES)
    if (
        tuple(fields)[: len(context.before_names)] != context.before_names
        or appended != expected[: len(appended)]
    ):
        raise ValueError("Old parameter layout or original four-store prefix changed")
    if len(appended) > 4:
        raise ValueError("Unowned later parameter stores")


def _check(context):
    if (
        context.invalid
        or context.guard.invalid
        or context.thread != get_ident()
        or not context.guard.audit_ready
        or _CONSUMED.get(context.source_owner) is not context
        or _PARENTS.get(context.parent_owner) is not context
    ):
        raise ValueError("Poisoned/foreign colormap source epoch")
    if context.active and any(
        not stack or stack[-1] is not value for stack, value in _stacks(context)
    ):
        raise ValueError("Colormap shared activity changed")
    if _digest(source_plan()) != context.source_identity:
        raise ValueError("Colormap load source domain changed")
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    prefix.parameters.inherited._same(
        runtime.bindings(runtime.bind(context.bound, context.kinds)), context.runtime_bindings
    )
    _history(context)


@contextmanager
def _claim(context):
    primary = None
    try:
        context.registry_record = state._validate(context.source_owner).record
        context.boundary_record = context.bound.binding
        context.plan = source_plan()
        context.source_identity = _digest(context.plan)
        context.before_names = tuple(vars(context.p))
        if any(store in vars(context.p) for store, _, _ in boundary.ROLES):
            raise ValueError("Existing colormap stores cannot be retrofitted")
        context.before_graph = _fields(context)
        if any(value is context.p for value in context.before_graph[0]):
            raise ValueError("Exposed p back-reference cannot isolate this source domain")
        context.parent_refs = _parent_refs(context)
        context.metadata_function, _, _ = _metadata_code()
        context.metadata_function_bindings = prefix._function_bindings(context.metadata_function)
        context.kinds, _, _ = state._classes(context.bound)
        context.runtime = runtime.bind(context.bound, context.kinds)
        context.runtime_bindings = runtime.bindings(context.runtime)
        context.function = context.bound.function
        context.bindings = _bindings()
        context.metadata_work.append(("actual_parent_registry_runtime_verification", "completed"))
        with claims._registry(context.parent_owner):
            if any(stack for stack, _ in _stacks(context)[1:]):
                claims._busy(context.parent_owner, "colormap_load_conflict")
            for stack, value in _stacks(context)[1:]:
                stack.append(value)
            context.registered = True
            mod.subconfigs.paths._install_audit(context.guard)
            _check(context)
            context.parent.invalid = context.source.invalid = context.retired = True
        context.stage = "original_four_stores"
        _check(context)
        yield
    except BaseException as error:
        primary = error
        context.claim_error = error
        raise
    finally:
        if context.registered:
            try:
                with claims._registry(context.parent_owner):
                    for stack, value in reversed(_stacks(context)[1:]):
                        if not stack or stack[-1] is not value:
                            raise ValueError("Colormap registry changed at release")
                        stack.pop()
            except BaseException as error:
                context.capture_errors += (("claim_release", error),)
        context.active = context.guard.active = False
        if _ACTIVE and _ACTIVE[-1] is context:
            _ACTIVE.pop()
        else:
            context.capture_errors += (("own_release", ValueError("Colormap reservation changed")),)
        if primary is not None:
            try:
                primary.colormap_load = context
            except BaseException as error:
                context.capture_errors += (("exception_evidence", error),)
        elif context.capture_errors:
            context.invalid = True
            raise ColormapLoadRejected(
                "Colormap claim closure failed",
                stage="claim_release",
                partial=context,
                capture_errors=context.capture_errors,
            )


def _roles(context):
    roles = {context.function.__code__: "slice"}
    for role, function in (
        ("helper", context.bound.api.helper),
        ("registry", context.bound.api.getter),
        ("checked", context.runtime.checked),
        ("np_copy", context.runtime.np_core),
    ):
        roles[prefix.parameters.inherited._chain(function)[-1].__code__] = role
    for name, _cls, _function, core, _ in context.runtime.methods:
        roles[core.__code__] = "copy" if name == "copy" else "copy_body"
    return roles


def _registry_check(context):
    api = context.bound.api
    namespace, mapping, surface = boundary._registry_state(api.registry, api.kind, api.cm)
    if namespace is not api.registry_namespace or mapping is not api.mapping:
        raise ValueError("Original registry live dictionary/mapping changed")
    prefix.parameters.inherited._same(surface, api.registry_surface)


def _entry(context, role, frame):
    # Full source/data checks bracket the native call. Each actual entry still
    # checks the exclusive live epoch before counting or entering its body.
    if (
        context.invalid
        or context.guard.invalid
        or context.thread != get_ident()
        or not context.active
        or not context.retired
        or _CONSUMED.get(context.source_owner) is not context
        or context.parent.p is not context.p
        or not context.parent.invalid
        or any(not stack or stack[-1] is not value for stack, value in _stacks(context))
    ):
        raise ValueError("Foreign/poisoned actual colormap entry epoch")
    # In particular, guard __getattribute__/_cmaps before the registry body can
    # resolve self._cmaps; a later equal mapping comparison is insufficient.
    _registry_check(context)
    context.calls[role] += 1
    maximum = 1 if role == "slice" else MAX_LOOKUPS
    if context.calls[role] > maximum:
        raise ValueError("Duplicate original colormap source/helper attempt")
    local = frame.f_locals
    index = context.calls["helper"] - 1
    if role == "slice":
        if local.get("self") is not context.p:
            raise ValueError("Foreign parameter source receiver")
    elif role == "helper":
        if local.get("name") is not context.bound.binding.names[index]:
            raise ValueError("Original alias/helper input order changed")
    elif role == "registry":
        if (
            local.get("self") is not context.bound.api.registry
            or local.get("item") is not context.bound.binding.names[index]
        ):
            raise ValueError("Original registry receiver/key changed")
    elif role == "checked":
        if (
            local.get("mapping") is not context.bound.api.mapping
            or local.get("kwargs", {}).get("colormap") is not context.bound.binding.names[index]
            or local.get("_error_cls") is not KeyError
        ):
            raise ValueError("Original checked lookup mapping/key/error type changed")
    elif role == "np_copy":
        source = context.bound.api.mapping[context.bound.binding.names[index]]
        if local.get("a") is not vars(source).get("_lut"):
            raise ValueError("Actual NumPy copy source buffer changed")
    else:
        name = context.bound.binding.names[index]
        if local.get("self") is not context.bound.api.mapping.get(name):
            raise ValueError("Original copy receiver changed")


def _copy_locals(frame):
    return dict(frame.f_locals)


def _trace_registry(context, frame, stage):
    context.trace_observations.append((stage, frame, frame.f_lasti))
    try:
        if context.invalid:
            raise ValueError("Poisoned registry trace admission")
        _registry_check(context)
    except BaseException as error:
        context.invalid = True
        context.observation_errors += (("registry_trace_" + stage, error),)
        raise


def _returned(context, role, frame, value):
    context.raw_last = (role, frame, value)
    context.raw.append(context.raw_last)  # Before every fallible observer copy.
    context.returns[role].append(value)
    context.events.append((role, "return_or_unwind", _copy_locals(frame)))


@contextmanager
def _observe(context):
    prior, trace = sys.getprofile(), sys.gettrace()
    roles = _roles(context)
    watcher = SimpleNamespace(
        depth=0,
        ready=False,
        locals={},
        frames=set(),
        opcodes={},
        primary=None,
        primary_traceback=None,
        stopped=False,
        exceptions={},
        stop=ValueError("Colormap source guard recovery refused continuation"),
    )
    context.observer_state = watcher
    hooks = dict(
        set_profile=sys.setprofile,
        set_trace=sys.settrace,
        get_profile=sys.getprofile,
        get_trace=sys.gettrace,
    )
    context.trace_observations = []
    forbidden = {
        value.__code__ for value in context.source.capture.objects if type(value) is FunctionType
    }
    for cls in context.kinds:
        for name in ("__call__", "__eq__", "_init", "_ensure_inited"):
            value = getattr(cls, name, None)
            if type(value) is FunctionType:
                forbidden.add(value.__code__)

    def inherited(function, frame, event, arg, *, kind="profile"):
        if watcher.stopped:
            return None  # Final recovery never rearms inherited callbacks.
        if function is None or watcher.depth:
            return None
        watcher.depth += 1
        try:
            return sys.call_tracing(function, (frame, event, arg))
        except BaseException as error:
            label = "inherited_" if kind == "profile" else "inherited_trace_"
            context.observation_errors += ((label + event, error),)
            if event not in ("return", "exception"):
                raise
        finally:
            watcher.depth -= 1
            if watcher.ready:
                observed = {}
                for name in ("profile", "trace"):
                    try:
                        observed[name] = hooks["get_" + name]()
                    except BaseException as error:
                        observed[name] = object()
                        context.observation_errors += (("active_sample_" + name, error),)
                        watcher.stopped = context.invalid = True
                if observed["profile"] is not profile or observed["trace"] is not traced:
                    watcher.stopped = context.invalid = True
                    context.observation_errors += (
                        ("inherited_hook_change", ValueError("Source hooks changed")),
                    )
                    for name, value in (("profile", profile), ("trace", traced)):
                        try:
                            hooks["set_" + name](value)
                        except BaseException as error:
                            context.observation_errors += (("active_restore_" + name, error),)
                            watcher.stopped = True
                    for name, expected in (("profile", profile), ("trace", traced)):
                        try:
                            if hooks["get_" + name]() is not expected:
                                raise ValueError("Required source hook restoration incomplete")
                        except BaseException as error:
                            context.observation_errors += (("active_verify_" + name, error),)
                            watcher.stopped = True
                for active in tuple(watcher.frames):
                    for name, value in (
                        ("f_trace", traced),
                        ("f_trace_lines", True),
                        ("f_trace_opcodes", True),
                    ):
                        try:
                            setattr(active, name, value)
                        except BaseException as error:
                            context.observation_errors += (("active_frame_" + name, error),)
                            watcher.stopped = context.invalid = True
                if watcher.stopped and watcher.primary is None and event in ("return", "exception"):
                    raise watcher.stop

    def traced(frame, event, arg):
        role = roles.get(frame.f_code)
        if event == "exception" and role is not None and not watcher.depth:
            context.raw_exception = (frame, arg)
            if arg[1] is not watcher.stop:
                watcher.exceptions[frame] = (arg[1], arg[2])
        if event == "return" and role is not None and arg is None and frame in watcher.exceptions:
            watcher.primary, watcher.primary_traceback = watcher.exceptions[frame]
        if watcher.stopped and role is not None and event in ("call", "line", "opcode"):
            raise watcher.stop
        guarded = role is not None or watcher.depth > 0
        if event in ("call", "line", "opcode") and guarded and watcher.ready:
            _trace_registry(context, frame, "before_" + event)
        if event == "call" and role is not None:
            watcher.frames.add(frame)
            watcher.opcodes[frame] = frame.f_trace_opcodes
        function = trace if event == "call" else watcher.locals.get(frame)
        if event != "opcode" or watcher.opcodes.get(frame, False):
            result = inherited(function, frame, event, arg, kind="trace")
            if result is not None:
                watcher.locals[frame] = result
            elif event == "call":
                watcher.locals.pop(frame, None)
        if event == "call" and role is not None:
            watcher.opcodes[frame] = watcher.opcodes[frame] or frame.f_trace_opcodes
            frame.f_trace = traced
            frame.f_trace_lines = True
            frame.f_trace_opcodes = True
        if event in ("call", "line", "opcode") and guarded and watcher.ready:
            _trace_registry(context, frame, "after_" + event)
        if event == "return":
            watcher.frames.discard(frame)
            watcher.locals.pop(frame, None)
            watcher.opcodes.pop(frame, None)
        return traced if role is not None or watcher.locals.get(frame) is not None else None

    def profile(frame, event, arg):
        code = frame.f_code
        if event == "return" and arg is None and frame in watcher.exceptions:
            watcher.primary, watcher.primary_traceback = watcher.exceptions[frame]
        if event == "call":
            if code in forbidden:
                raise ValueError("Colormap evaluator/initializer callback is outside lookup scope")
            role = roles.get(code)
            if role is not None:
                _entry(context, role, frame)
            if (
                role is not None
                or code.co_filename.startswith(str(runtime.SITE) + "/")
                or code.co_filename.startswith(
                    str(prefix.parameters.inherited.tissue.aliases.NATIVE) + "/"
                )
            ):
                if len(context.work) >= MAX_WORK:
                    raise ValueError("Bounded actual colormap source work exhausted")
                context.work.append(
                    (
                        len(context.work),
                        role or "nested_source",
                        code.co_filename,
                        code.co_qualname,
                        "entered_not_independent_case",
                    )
                )
        role = roles.get(code)
        if event == "return" and role is not None:
            try:
                _returned(context, role, frame, arg)
            except BaseException as error:
                context.observation_errors += ((role + "_return_capture", error),)
        inherited(prior, frame, event, arg)
        if event == "call" and role is not None:
            # The inherited call hook also precedes the native body. Recheck
            # its final registry surface before returning permission to enter.
            _registry_check(context)

    try:
        hooks["set_profile"](profile)
        hooks["set_trace"](traced)
        watcher.ready = True
        yield
    except BaseException as error:
        if watcher.primary is not None:
            # The caller's inner catch may already have retained our recovery
            # sentinel. Keep the public source error canonical with the exact
            # primary rethrown here, preserving the displaced error separately.
            retained = vars(context).get("source_error")
            if retained is not None and retained is not watcher.primary:
                context.observation_errors += (("displaced_source_error", retained),)
            if error is not watcher.primary and error is not retained:
                context.observation_errors += (("displaced_observer_error", error),)
            context.source_error = watcher.primary
            if error is not watcher.primary:
                raise BaseException.with_traceback(watcher.primary, watcher.primary_traceback)  # noqa: B904
        raise
    finally:
        watcher.ready = False
        for name, setter, value in (
            ("profile_restore", hooks["set_profile"], prior),
            ("trace_restore", hooks["set_trace"], trace),
        ):
            try:
                setter(value)
            except BaseException as error:
                context.observation_errors += ((name, error),)
        for name, expected in (("profile", prior), ("trace", trace)):
            try:
                if hooks["get_" + name]() is not expected:
                    raise ValueError("Final source hook restoration incomplete")
            except BaseException as error:
                context.observation_errors += (("final_sample_" + name, error),)
                watcher.stopped = context.invalid = True


def _invoke(context):
    return context.function(context.p)


def _copy_relation(source, value):
    if value is source or type(value) is not type(source) or vars(value) is vars(source):
        raise ValueError("Original lookup must return a fresh same-class shallow copy")
    if tuple(vars(value)) != tuple(vars(source)):
        raise ValueError("Native copy lost/reordered fields")
    for name, original in vars(source).items():
        actual = vars(value)[name]
        if name == "_lut" and vars(source).get("_isinit") is True:
            if (
                type(original) is not np.ndarray
                or type(actual) is not np.ndarray
                or actual is original
                or np.shares_memory(actual, original)
                or actual.base is not None
                or actual.dtype.str != original.dtype.str
                or actual.shape != original.shape
                or not actual.flags.writeable
                or actual.tobytes(order="A") != original.tobytes(order="A")
            ):
                raise ValueError("Initialized native LUT copy ownership/bytes changed")
        elif actual is not original:
            raise ValueError("Native shallow field/callback/storage relationship changed")


def _outputs(context):
    expected = tuple(row[0] for row in boundary.ROLES)
    if tuple(vars(context.p))[len(context.before_names) :] != expected:
        raise ValueError("All four original stores in literal order required")
    lut_copies = sum(
        vars(context.bound.api.mapping[name]).get("_isinit") is True
        for name in context.bound.binding.names
    )
    if context.calls != dict(
        slice=1, helper=4, registry=4, checked=4, copy=4, copy_body=4, np_copy=lut_copies
    ):
        raise ValueError("Incomplete/duplicated actual helper/registry/copy accounting")
    if (
        len(context.returns["slice"]) != 1
        or context.returns["slice"][0] is not None
        or len(context.returns["np_copy"]) != lut_copies
        or any(
            len(values) != 4
            for role, values in context.returns.items()
            if role not in ("slice", "np_copy")
        )
    ):
        raise ValueError("Complete actual return observations required")
    values = []
    lut_index = 0
    for index, (store, _, _) in enumerate(boundary.ROLES):
        value = vars(context.p)[store]
        original = context.bound.api.mapping[context.bound.binding.names[index]]
        if context.returns["checked"][index] is not original or any(
            context.returns[role][index] is not value
            for role in ("helper", "registry", "copy", "copy_body")
        ):
            raise ValueError("Actual child return/source/store association changed")
        _copy_relation(original, value)
        if vars(original).get("_isinit") is True:
            if vars(value)["_lut"] is not context.returns["np_copy"][lut_index]:
                raise ValueError("Actual NumPy return/LUT store association changed")
            lut_index += 1
        if any(value is earlier for earlier in values):
            raise ValueError("Repeated names must still receive independent native copies")
        values.append(value)


def _graph(context):
    roots = {}
    for index, (store, _, _) in enumerate(boundary.ROLES):
        name = context.bound.binding.names[index]
        roots["registry_" + store] = context.bound.api.mapping.get(name)
        roots["returned_" + store] = vars(context.p).get(store)
    capture = state._Capture(context.kinds)
    context.partial_capture = capture
    return capture.capture(roots)


def trial_record(value):
    return dict(
        law=LAW_ID,
        registry=value.registry_identity,
        boundary=value.boundary_identity,
        parent=value.parent_trial_identity,
        before=value.before_identity,
        after=value.after_identity,
        work=value.work,
        calls=value.calls,
        metadata_work=value.metadata_work,
        source_completed=value.source_completed,
        source_lines=(1007, 1014),
        callback_evaluations=0,
        biological_cases=0,
        full_Parameters_INIT_admitted=False,
    )


def prepare(owner, *, law_id, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1" or os.environ.get(mod.RELEASE) != "1":
        raise ColormapLoadRejected("Original colormap source remains held", stage="release")
    if type(law_id) is not str or law_id != LAW_ID:
        raise ColormapLoadRejected("Explicit original four-store law required", stage="law")
    context = _reserve(owner)
    with _claim(context):
        primary = None
        try:
            with _observe(context):
                try:
                    _invoke(context)
                except BaseException as error:
                    context.source_error = error
                    raise
            context.source_completed = True
            if context.observation_errors:
                raise ValueError("Original reached-output observation incomplete")
            _check(context)
            _outputs(context)
            context.after = _graph(context)
            context.metadata_work.append(("closed_return_array_copies", context.after.array_copies))
            value = Trial(
                context.registry_record.identity,
                context.boundary_record.identity,
                context.parent.trial.identity,
                _digest(context.before_graph[1]),
                context.after.identity,
                tuple(context.work),
                tuple(context.calls.items()),
                (*context.metadata_work, *context.observations),
                True,
                "",
            )
            context.trial = replace(value, identity=_digest(trial_record(value)))
            context.original_trial = context.trial
            result = object.__new__(ColormapsOwner)
            context.owner = result
            _ISSUED[result] = context
            return result
        except BaseException as error:
            primary = error
        context.operation_error = primary
        try:
            context.failure_capture = _graph(context)
        except BaseException as error:
            context.capture_errors += (("failure_capture", error),)
        context.invalid = True
        raise ColormapLoadRejected(
            "Original colormap load issued no successor",
            stage=context.stage,
            partial=context,
            source_error=context.source_error,
            capture_errors=(*context.observation_errors, *context.capture_errors),
        ) from primary


def _validate(owner):
    if type(owner) is not ColormapsOwner or owner not in _ISSUED:
        raise ColormapLoadRejected("Actual issued colormap successor required", stage="owner")
    context = _ISSUED[owner]
    if context.active or context.validating or _ACTIVE:
        raise ColormapLoadRejected("Active/overlapping colormap successor", stage="state")
    context.validating = True
    validation = SimpleNamespace(
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
        invalid=False,
    )
    registered = False
    primary, release_error = None, None
    context.validations.append(("successor_validation", "attempted", len(context.observations)))
    try:
        with claims._registry(context.parent_owner):
            if any(stack for stack, _ in _stacks(context)):
                claims._busy(context.parent_owner, "colormap_validation_conflict")
            for stack, _ in _stacks(context):
                stack.append(
                    validation if stack is not mod.subconfigs.paths._ACTIVE else validation.guard
                )
            registered = True
            mod.subconfigs.paths._install_audit(validation.guard)
        if (
            context.owner is not owner
            or context.source_completed is not True
            or context.source_error is not None
            or context.observation_errors
            or context.capture_errors
            or context.trial.work != tuple(context.work)
            or context.trial.calls != tuple(context.calls.items())
        ):
            raise ValueError("Original successful owner/completion/work record changed")
        _check(context)
        _outputs(context)
        actual = _graph(context)
        # _Capture returns the same closed-data interface used by state._same,
        # with class/file surfaces already checked through registry _history.
        if (
            actual.identity != context.after.identity
            or len(actual.objects) != len(context.after.objects)
            or any(a is not b for a, b in zip(actual.objects, context.after.objects, strict=True))
            or context.after.encoder.arrays is not context.after.arrays
            or context.after.encoder.nodes is not context.after.tree["nodes"]
            or context.after.encoder.seal(context.after.tree) != context.after.identity
            or context.trial is not context.original_trial
            or _digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Current returned graph/evidence/trial changed")
        if validation.invalid or validation.guard.invalid:
            raise ValueError("Readonly successor validation poisoned")
        context.validations.append(
            ("successor_validation", "completed", actual.array_copies, len(context.observations))
        )
        return context
    except BaseException as error:
        primary = error
        context.invalid = True
        raise ColormapLoadRejected(
            "Stale original colormap successor", stage="drift", partial=context, source_error=error
        ) from error
    finally:
        if registered:
            try:
                with claims._registry(context.parent_owner):
                    for stack, _ in reversed(_stacks(context)):
                        expected = (
                            validation.guard
                            if stack is mod.subconfigs.paths._ACTIVE
                            else validation
                        )
                        if not stack or stack[-1] is not expected:
                            raise ValueError("Readonly colormap validation registry changed")
                        stack.pop()
            except BaseException as error:
                context.capture_errors += (("validation_release", error),)
                context.invalid = True
                release_error = error
        validation.guard.active = False
        context.validating = False
        if primary is None and release_error is not None:
            raise ColormapLoadRejected(
                "Readonly successor closure failed",
                stage="validation_release",
                partial=context,
                source_error=release_error,
            ) from release_error


def require_continuation(owner):
    context = _validate(owner)
    raise ColormapLoadRejected(
        "Next contiguous results options/constants/ion-profile stage required",
        stage="next_prerequisite",
        partial=dict(
            next_source_line=1017, completed_four_stores=True, trial=context.trial.identity
        ),
    )


def _bindings():
    functions = (
        _digest,
        _metadata_code,
        source_plan,
        _fields,
        _parent_refs,
        _stacks,
        _reserve,
        _historical_metadata,
        _history,
        _check,
        _claim,
        _claim.__wrapped__,
        _roles,
        _registry_check,
        _entry,
        _copy_locals,
        _trace_registry,
        _returned,
        _observe,
        _observe.__wrapped__,
        _invoke,
        _copy_relation,
        _outputs,
        _graph,
        trial_record,
        prepare,
        _validate,
        require_continuation,
        _bindings,
        ColormapsOwner.__init__,
        ColormapsOwner.__reduce_ex__,
        ColormapsOwner.parameters.fget,
        ColormapsOwner.trial.fget,
        runtime.declaration,
        runtime.inspect_reference,
        runtime.bind,
        runtime.bindings,
        runtime._loaded,
        runtime._method,
        runtime._functions,
        runtime._numpy_copy,
        runtime._copy_exports,
        runtime._copy_delegates,
    )
    return (), (
        LAW_ID,
        STATE_SHA256,
        RELEASE,
        MAX_WORK,
        MAX_LOOKUPS,
        _LOCK,
        _ACTIVE,
        _ISSUED,
        _CONSUMED,
        _PARENTS,
        ColormapsOwner,
        ColormapLoadRejected,
        Trial,
        np.copy,
        np.shares_memory,
        np.ndarray,
        get_ident,
        *state._bindings()[1],
        *(
            atom
            for fn in functions
            for atom in prefix.parameters.inherited.tissue.aliases._atoms(fn)
        ),
    )
