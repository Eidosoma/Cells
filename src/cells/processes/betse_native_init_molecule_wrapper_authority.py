"""Fresh imported beartype provenance for original molecule/channel methods.

The observer runs around the EXISTING native import operation. It never calls
a decorator, code generator, wrapper, constructor or native method itself.
Already imported native targets cannot acquire retrospective issuance.
"""

import ast
import builtins
import contextlib
import dis
import functools
import hashlib
import importlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_dynamics_prelude as typed
from cells.processes import betse_native_init_molecule_channels_source as channels
from cells.processes import betse_native_init_molecule_network_source as network

RELEASE = "CELLS_NATIVE_INIT_MOLECULE_WRAPPER_RELEASED"
LAW = "fresh_original_molecule_channel_imported_beartype_factory@1"
ROOTS = (
    Path("/mnt/workspaces/Cells/beartype-overlay-0.22.9-20261031-01"),
    Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages"),
)
LIBRARIES = {
    # Source paths and exact library bytes are intentionally kept together.
    # ruff: noqa: E501
    "beartype._decor._nontype.decornontype": "7dcb3fa458601f813aded9551c86f6db5d45aa5c5181a6925d2f2a343d7ff3c9",
    "beartype._decor._nontype._wrap.wrapmain": "3fc2f8162accefcbb75192503450c0d8120719a1bf653215ee6ee86540b82a6f",
    "beartype._util.func.utilfuncmake": "9190bbf6126b820b4e4259bd130dc5406c2b5ee0e17942ad7ac359822e6f776f",
    "beartype._check.metadata.metacheck": "029a5dab742c77b1a3cc44fd75751a35cb5664913bc5499374de6abc1e74e558",
    "beartype._conf.confmain": "4fbe9f5482c9f82b98737e91c3b4b6d3e338342906863d4bfcad8d98eb0ddf22",
    "beartype.claw._importlib._clawimpload": "6279c7a280ce26e884d0c5db3e965380048ad21fd2dcc9b9ca6e871dd9fa2cae",
}
MAX_FACTORIES = 512
# Tissue once, Simulator import/constructor twice, callbacks once.
MAX_GUARD_SCOPES = 4
# One literal metadata helper, never a policy for general mutable globals.
COUNTER_HELPER = (
    "betse/util/type/iterable/mapping/mapcls.py",
    "15a88829cbb5fc9fc9d60c0a8b4e7ea120f86d06ceb7e1876d55862ee060ad58",
    "_get_default_dict_class_name",
    "_DEFAULT_DICT_ID",
)
MAX_COUNTER_CALLS = 64
# One original generator export, reconstructed by the pinned Beartype helper.
CONTEXT_EXPORT = (
    "betse/util/type/contexts.py",
    "66fad70e4b3458f3d24e66c93c741628112be7ba591d745e034529caaa8da8ef",
    "noop_context",
)
CONTEXT_STDLIB = (
    (
        "contextlib",
        "/usr/lib/python3.13/contextlib.py",
        "c1e0d67b2007de11ae93cd36cf6faf38d9ab32656a832d592a49325eec579f96",
    ),
    (
        "functools",
        "/usr/lib/python3.13/functools.py",
        "7aa8725afbe9b9fc47a825b4e7c0330fa374432f481d7be8202b96f56eeac9a0",
    ),
)
GUARD_SOURCES = (
    (
        "betse_native_tissue_configuration",
        "_account",
        "e9f8c93b7bfe856532f68f7406c07e5666b2ebb60d8e71c19a69bb765d4bb99e",
    ),
    (
        "betse_native_simulator_construction",
        "_observe",
        "6f94d0cf79191c952a7055a63865080ffe1693c8798c6ee73aa24ad24c8d5884",
    ),
    (
        "betse_native_phase_callbacks",
        "_observe",
        "63ecf075fd2b781c84156c732366def11729349124ae3652ae72506c4c467698",
    ),
)
_ACTIVE, _FAILED, _LOCK = [], [], RLock()
_ISSUED = WeakKeyDictionary()


class WrapperAuthorityRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None):
        super().__init__(reason)
        self.stage, self.partial = stage, partial


@dataclass(frozen=True, slots=True)
class ImportEvidence:
    law: str
    source_completed: bool
    factories: int
    generated: int
    raw_returns: tuple
    source_errors: tuple


def source_plan():
    return dict(
        law=LAW,
        release=RELEASE,
        libraries=LIBRARIES,
        native_sources={**network.PINS, **channels.PINS},
        observe_existing_import_order_not_preload_or_redecorate=True,
        required_window=(
            "Before first native target module import, through successful import completion"
        ),
        original_factory_generator_or_wrapper_invoked_by_observer=False,
        retrospective_or_decoded_or_supplied_wrapper_authority=False,
        nested_guard_sources=GUARD_SOURCES,
        max_nested_guard_scopes=MAX_GUARD_SCOPES,
        nested_guards_require_actual_issued_context_and_monitored_suspended_frame=True,
        late_global_resolution="absent factory-time names, later pinned declarations, actual module return",
        factory_atoms_and_existing_lookups_may_not_be_refreshed=True,
        witnessed_metadata_counter_helper=COUNTER_HELPER,
        max_metadata_counter_calls=MAX_COUNTER_CALLS,
        unobserved_callback_or_closed_counter_effects_refuse=True,
        witnessed_contextmanager_export=CONTEXT_EXPORT,
        contextmanager_runtime_sources=CONTEXT_STDLIB,
        contextmanager_reconstruction_requires_actual_entry_return_and_delegate=True,
        contextmanager_annotation_alias_update="only actual generator factory return snapshot; preserve pre-factory value",
        no_Parameters_phase_material_or_scientific_admission=True,
    )


def _items(value):
    if value is None:
        return None
    if type(value) is not dict:
        raise ValueError("Actual function dictionary required")
    return tuple(value.items())


def _function_state(function):
    if type(function) is not FunctionType:
        raise ValueError("Actual Python source function required")
    namespace, cached = function.__globals__, function.__builtins__
    provider = namespace.get("__builtins__")
    resolved = vars(provider) if type(provider) is ModuleType else provider
    if cached is not vars(builtins) or resolved is not cached:
        raise ValueError("Actual cached builtin/namespace dictionary required")
    values = [
        function,
        function.__code__,
        namespace,
        cached,
        function.__defaults__,
        function.__kwdefaults__,
    ]
    values.extend(function.__defaults__ or ())
    for key, value in _items(function.__kwdefaults__) or ():
        values.extend((key, value))
    for cell in function.__closure__ or ():
        values.extend((cell, cell.cell_contents))
    for name in function.__code__.co_names:
        if name in namespace:
            value = namespace[name]
            if (
                name in cached
                and value is not cached[name]
                and name not in ("__name__", "__doc__", "__package__", "__loader__", "__spec__")
            ):
                raise ValueError("Source builtin lookup shadowed: " + name)
            values.extend((name, value))
        elif name in cached:
            values.extend((name, cached[name]))
    return tuple(values)


def _wrapper_state(function, backend):
    values = list(_function_state(function))
    values.append(function.__annotations__)
    for key, value in _items(function.__annotations__):
        values.extend((key, value))
    for key, value in vars(function).items():
        values.extend((key, value))
    defaults = function.__kwdefaults__ or {}
    for value in defaults.values():
        if type(value) is FunctionType and value is not defaults.get("__beartype_func"):
            values.extend(_function_state(value))
    for name, cls in (
        ("__beartype_check_meta", backend.metadata),
        ("__beartype_conf", backend.configuration),
    ):
        value = defaults.get(name)
        if value is None:
            continue
        if type(value) is not cls:
            raise ValueError("Original wrapper metadata/configuration type changed")
        values.append(value)
        for slot in cls.__slots__:
            if slot == "__weakref__":
                continue
            item = object.__getattribute__(value, slot)
            values.extend((slot, item))
            if type(item) is dict:
                for key, member in item.items():
                    values.extend((key, member))
            if type(item) is backend.configuration:
                for conf_slot in backend.configuration.__slots__:
                    if conf_slot != "__weakref__":
                        values.extend((conf_slot, object.__getattribute__(item, conf_slot)))
    return tuple(values)


def _original_header(function):
    """A module may gain later globals while importing; its method may not change."""
    provider = function.__globals__.get("__builtins__")
    resolved = vars(provider) if type(provider) is ModuleType else provider
    if resolved is not function.__builtins__ or resolved is not vars(builtins):
        raise ValueError("Original cached builtin/namespace dictionary changed")
    result = [
        function,
        function.__code__,
        function.__globals__,
        function.__builtins__,
        function.__defaults__,
        function.__kwdefaults__,
    ]
    result.extend(function.__defaults__ or ())
    for key, value in _items(function.__kwdefaults__) or ():
        result.extend((key, value))
    for cell in function.__closure__ or ():
        result.extend((cell, cell.cell_contents))
    return tuple(result)


def _same(current, original):
    if len(current) != len(original) or any(
        a is not b for a, b in zip(current, original, strict=True)
    ):
        raise ValueError("Actual source/closure/default/builtin binding changed")


def _counter_register(context, row):
    relative, pin, name, counter = COUNTER_HELPER
    if row.target[0] != (None, name) or row.origin.name != relative[:-3].replace("/", "."):
        return
    path = network.NATIVE / relative
    if (
        {**network.PINS, **channels.PINS}.get(relative) != pin
        or path.is_symlink()
        or hashlib.sha256(path.read_bytes()).hexdigest() != pin
        or row.original.__code__.co_names != (counter, "str")
        or row.original.__defaults__ is not None
        or row.original.__kwdefaults__ is not None
        or row.original.__closure__ is not None
        or vars(row.module).get(name) is not row.output
        or type(vars(row.module).get(counter)) is not int
        or vars(row.module)[counter] != 0
        or any(effect.row.module is row.module for effect in context.counter_effects)
    ):
        raise ValueError("Fresh pinned metadata counter/helper authority required")
    effect = SimpleNamespace(
        context=context,
        row=row,
        namespace=vars(row.module),
        name=name,
        counter=counter,
        initial=vars(row.module)[counter],
        value=vars(row.module)[counter],
        original_code=row.original.__code__,
        output_code=row.output.__code__,
        original_labels=(row.original.__module__, row.original.__name__, row.original.__qualname__),
        output_labels=(row.output.__module__, row.output.__name__, row.output.__qualname__),
        history=[],
        pending=[],
        frames={},
        attempt=None,
        failed=False,
    )
    row.counter_effect = effect
    context.counter_effects.append(effect)
    context.counter_codes[effect.original_code] = (effect, "body")
    if row.output is not row.original:
        context.counter_codes[effect.output_code] = (effect, "wrapper")


def _counter_atoms(row, function, current, before, counter):
    effect = getattr(row, "counter_effect", None)
    if effect is None or function is not row.original:
        return _same(current, before)
    # The pinned no-argument helper has exactly these two reached names and
    # the unchanged six header atoms. Only its own counter-value lane varies.
    if len(current) != len(before) or before[7] is not effect.initial or current[7] is not counter:
        raise ValueError("Witnessed metadata counter binding changed")
    _same(current[:7], before[:7])
    _same(current[8:], before[8:])


def _counter_check(effect, candidate=None):
    row, context = effect.row, effect.context
    registered = context.counter_codes.get(effect.original_code)
    if (
        effect.failed
        or context.thread != get_ident()
        or getattr(row, "counter_effect", None) is not effect
        or not any(item is effect for item in context.counter_effects)
        or type(registered) is not tuple
        or len(registered) != 2
        or registered[0] is not effect
        or type(registered[1]) is not str
        or registered[1] != "body"
        or effect.namespace is not vars(row.module)
        or type(effect.name) is not str
        or effect.name != COUNTER_HELPER[2]
        or type(effect.counter) is not str
        or effect.counter != COUNTER_HELPER[3]
        or type(effect.initial) is not int
        or effect.initial != 0
        or effect.namespace.get(effect.name) is not row.output
        or row.original.__code__ is not effect.original_code
        or row.output.__code__ is not effect.output_code
        or not row.origin.module_published
    ):
        raise ValueError("Actual original metadata counter callable/record changed")
    previous = effect.initial
    for attempt in effect.history:
        if (
            not attempt.completed
            or attempt.primary is not None
            or type(attempt.ordinal) is not int
            or not 0 <= attempt.ordinal < len(context.counter_attempts)
            or context.counter_attempts[attempt.ordinal] is not attempt
            or attempt.before is not previous
            or attempt.callee is not row.original
            or attempt.frame.f_code is not effect.original_code
            or attempt.frame.f_globals is not effect.namespace
            or type(attempt.after) is not int
            or attempt.after != previous + 1
            or type(attempt.output) is not str
            or attempt.output != "__DefaultDict" + str(attempt.after)
            or (
                row.output is not row.original
                and (
                    attempt.wrapper.f_code is not effect.output_code
                    or attempt.frame.f_back is not attempt.wrapper
                )
            )
        ):
            raise ValueError("Complete ordered metadata counter witnesses required")
        previous = attempt.after
    if previous is not effect.value:
        raise ValueError("Original metadata counter history changed")
    _same(
        (row.original.__module__, row.original.__name__, row.original.__qualname__),
        effect.original_labels,
    )
    _same(
        (row.output.__module__, row.output.__name__, row.output.__qualname__), effect.output_labels
    )
    value = effect.value if candidate is None else candidate
    if (
        type(effect.namespace.get(effect.counter)) is not int
        or effect.namespace[effect.counter] is not value
    ):
        raise ValueError("Unwitnessed metadata counter change")
    _counter_atoms(
        row,
        row.original,
        _wrapper_state(row.original, context.backend),
        row.original_bindings,
        value,
    )
    _counter_atoms(
        row,
        row.output,
        _record_function(row, context.backend),
        row.published_bindings if row.published_bindings is not None else row.bindings,
        value,
    )


def _counter_call(context, caller, function):
    found = context.counter_codes.get(function.__code__) if type(function) is FunctionType else None
    if found is None:
        return
    effect, role = found
    context.counter_raw.append((caller, "call", function))
    if context.capture_error is not None:
        raise ValueError("Incomplete metadata counter observation")
    validate_import_guards(context)
    _counter_check(effect)
    row = effect.row
    expected = row.original if role == "body" else row.output
    if (
        function is not expected
        or effect.pending
        or (role == "wrapper" and effect.frames)
        or (
            role == "body"
            and (
                effect.attempt is not None
                or (
                    row.output is not row.original
                    and (
                        len(effect.frames) != 1
                        or effect.frames.get(id(caller), (None, None))[0] is not caller
                        or caller.f_code is not effect.output_code
                    )
                )
            )
        )
    ):
        raise ValueError("Actual once-only original helper call required")
    effect.pending.append((function, caller, role))


def _counter_commit(effect, output):
    attempt = effect.attempt
    if (
        attempt is None
        or attempt.primary is not None
        or attempt.after is None
        or output is not attempt.output
        or attempt.completed
        or type(attempt.ordinal) is not int
        or not 0 <= attempt.ordinal < len(effect.context.counter_attempts)
        or effect.context.counter_attempts[attempt.ordinal] is not attempt
    ):
        raise ValueError("Complete original helper return required")
    _counter_check(effect, candidate=attempt.after)
    attempt.completed = True
    effect.history.append(attempt)
    effect.value, effect.attempt = attempt.after, None


def _counter_event(context, effect, role, frame, event, value):
    # Raw returns/unwinds precede every fallible observer/binding operation.
    raw = (frame, event, value)
    context.counter_raw.append(raw)
    if event == "unwind":
        context.source_errors.append(raw)
        effect.failed = True
        if effect.attempt is not None:
            effect.attempt.primary = value
        effect.frames.pop(id(frame), None)
        return
    validate_import_guards(context)
    if event == "start":
        if not effect.pending or context.capture_error is not None:
            raise ValueError("Actual helper CALL witness required before body")
        function, caller, expected_role = effect.pending.pop()
        if (
            expected_role != role
            or caller is not frame.f_back
            or frame.f_code is not function.__code__
            or frame.f_globals is not function.__globals__
        ):
            raise ValueError("Exact helper callable/frame ancestry required")
        _counter_check(effect)
        effect.frames[id(frame)] = (frame, role)
        if role == "body":
            if len(context.counter_attempts) >= MAX_COUNTER_CALLS:
                raise ValueError("Bounded metadata counter work exhausted")
            attempt = SimpleNamespace(
                ordinal=len(context.counter_attempts),
                callee=function,
                frame=frame,
                wrapper=caller if effect.row.output is not effect.row.original else None,
                before=effect.value,
                after=None,
                output=None,
                primary=None,
                completed=False,
            )
            effect.attempt = attempt
            context.counter_attempts.append(attempt)
        return
    if effect.frames.get(id(frame), (None, None)) != (frame, role):
        raise ValueError("Actual retained helper return frame required")
    if role == "body":
        attempt = effect.attempt
        after = effect.namespace.get(effect.counter)
        if (
            attempt is None
            or attempt.frame is not frame
            or type(after) is not int
            or after != attempt.before + 1
            or type(value) is not str
            or value != "__DefaultDict" + str(after)
        ):
            raise ValueError("Original counter increment/result correspondence required")
        attempt.after, attempt.output = after, value
    if role == "wrapper" or effect.row.output is effect.row.original:
        _counter_commit(effect, value)
    effect.frames.pop(id(frame))


def _guard_sources():
    """Bind already loaded guard definitions; never import or enter a child."""
    result = {}
    for name, attribute, pin in GUARD_SOURCES:
        module = sys.modules.get("cells.processes." + name)
        if module is None:
            continue
        path = Path(__file__).with_name(name + ".py")
        if (
            type(module) is not ModuleType
            or Path(module.__file__).resolve() != path.resolve()
            or hashlib.sha256(path.read_bytes()).hexdigest() != pin
        ):
            raise ValueError("Exact nested import guard source required")
        api = vars(module).get(attribute)
        body = getattr(api, "__wrapped__", None)
        helper = next(
            c
            for c in contextmanager.__code__.co_consts
            if type(c) is CodeType and c.co_name == "helper"
        )
        if (
            type(api) is not FunctionType
            or api.__code__ is not helper
            or api.__globals__ is not contextmanager.__globals__
            or type(body) is not FunctionType
            or api.__closure__ is None
            or len(api.__closure__) != 1
            or api.__closure__[0].cell_contents is not body
            or body.__globals__ is not vars(module)
            or typed._constant(body.__code__)
            != typed._constant(_library_code(path, None, attribute))
        ):
            raise ValueError("Actual nested import guard factory/body required")
        nested = next(
            c for c in body.__code__.co_consts if type(c) is CodeType and c.co_name == "profile"
        )
        instructions = tuple(dis.get_instructions(body))
        # CPython 3.13 suspends f_lasti at the following RESUME. Both offsets
        # must come from the actual original YIELD_VALUE/RESUME pair.
        suspended = {i.offset for i in instructions if i.opname == "YIELD_VALUE"}
        suspended.update(
            after.offset
            for before, after in zip(instructions, instructions[1:], strict=False)
            if before.opname == "YIELD_VALUE" and after.opname == "RESUME"
        )
        result[body.__code__] = SimpleNamespace(
            module=module,
            attribute=attribute,
            api=api,
            body=body,
            api_state=_function_state(api),
            state=_function_state(body),
            nested=nested,
            active=vars(module)["_ACTIVE"],
            consumed=vars(module)["_CONSUMED"],
            yields=frozenset(suspended),
        )
    return result


def _guard_binding(provider):
    if (
        vars(provider.module).get(provider.attribute) is not provider.api
        or provider.api.__wrapped__ is not provider.body
        or provider.api.__closure__[0].cell_contents is not provider.body
        or vars(provider.module).get("_ACTIVE") is not provider.active
        or vars(provider.module).get("_CONSUMED") is not provider.consumed
    ):
        raise ValueError("Original nested import guard bindings changed")
    _same(_function_state(provider.body), provider.state)
    _same(_function_state(provider.api), provider.api_state)


def _guard_profile(row):
    _same(_function_state(row.profile), row.state)
    if row.selection is not None:
        cells = dict(
            zip(row.profile.__code__.co_freevars, row.profile.__closure__ or (), strict=True)
        )
        selected = cells["selected"].cell_contents
        if (
            type(selected) is not set
            or len(selected) != len(row.selection)
            or any(not any(code is old for old in row.selection) for code in selected)
        ):
            raise ValueError("Original guard code selection changed")


def validate_import_guards(context):
    """Authenticate the actual live hook chain, without entering any owner."""
    if (
        not _ACTIVE
        or _ACTIVE[-1] is not context
        or not context.active
        or context.thread != get_ident()
    ):
        raise WrapperAuthorityRejected("Actual active import observer required", stage="guards")
    if context.guard_error is not None:
        raise context.guard_error
    expected = context.original_hooks
    try:
        for row in context.guard_frames:
            frame, provider = row.frame, row.provider
            _guard_binding(provider)
            child = frame.f_locals.get("context")
            if (
                frame.f_globals is not vars(provider.module)
                or frame.f_code is not provider.body.__code__
                or frame.f_lasti not in provider.yields
                or child is not row.child
                or type(child) is not SimpleNamespace
                or child.active is not True
                or type(child.thread) is not int
                or child.thread != get_ident()
                or not provider.active
                or provider.active[-1] is not child
                or provider.consumed.get(child.request) is not child
                or frame.f_locals.get("previous") is not expected[0]
                or frame.f_locals.get("trace") is not expected[1]
            ):
                context.guard_failure = dict(
                    instruction=frame.f_lasti,
                    yield_offsets=tuple(provider.yields),
                    code_matches=frame.f_code is provider.body.__code__,
                    child_matches=child is row.child,
                    child_active=vars(child).get("active")
                    if type(child) is SimpleNamespace
                    else None,
                    child_thread=vars(child).get("thread")
                    if type(child) is SimpleNamespace
                    else None,
                    current_thread=get_ident(),
                    active_matches=bool(provider.active) and provider.active[-1] is child,
                    consumed_matches=provider.consumed.get(row.child.request) is child,
                    previous_matches=frame.f_locals.get("previous") is expected[0],
                    trace_matches=frame.f_locals.get("trace") is expected[1],
                )
                raise ValueError("Actual suspended nested import guard ancestry required")
            profile = frame.f_locals.get("profile")
            if (
                type(profile) is not FunctionType
                or profile.__code__ is not provider.nested
                or profile.__globals__ is not vars(provider.module)
            ):
                raise ValueError("Actual nested import guard callback required")
            cells = dict(zip(profile.__code__.co_freevars, profile.__closure__ or (), strict=True))
            if (
                "previous" not in cells
                or cells["previous"].cell_contents is not expected[0]
                or "context" not in cells
                or cells["context"].cell_contents is not child
                or any(
                    cell.cell_contents is not frame.f_locals[name] for name, cell in cells.items()
                )
            ):
                raise ValueError("Original nested import guard closure/delegation changed")
            if row.profile is None:
                row.profile, row.state = profile, _function_state(profile)
                selected = cells.get("selected")
                if selected is not None:
                    value = selected.cell_contents
                    if type(value) is not set or any(type(code) is not CodeType for code in value):
                        raise ValueError("Original guard code selection required")
                    row.selection = tuple(value)
            if row.profile is not profile:
                raise ValueError("Issued nested import guard callback identity changed")
            _guard_profile(row)
            expected = profile, expected[1]
        if sys.getprofile() is not expected[0] or sys.gettrace() is not expected[1]:
            raise ValueError("Inherited import guards changed during factory work")
    except BaseException as error:
        context.guard_error = error
        context.hook_losses.append(("guard_chain", error))
        raise
    return expected


def _guard_event(context, provider, frame, event, value):
    """Observe real guard generator lifetime; never register a supplied hook."""
    context.guard_raw.append((frame, event, value))
    if event == "start":
        validate_import_guards(context)
        _guard_binding(provider)
        child = frame.f_locals.get("context")
        if (
            frame.f_globals is not vars(provider.module)
            or type(child) is not SimpleNamespace
            or child.active is not True
            or type(child.thread) is not int
            or child.thread != get_ident()
            or not provider.active
            or provider.active[-1] is not child
            or provider.consumed.get(child.request) is not child
        ):
            raise ValueError("Issued active child required before import guard entry")
        if len(context.guard_closed) >= MAX_GUARD_SCOPES or any(
            row.child is child for row in context.guard_frames
        ):
            raise ValueError("Bounded exclusive child import guard required")
        context.guard_frames.append(
            SimpleNamespace(
                provider=provider,
                frame=frame,
                child=child,
                profile=None,
                state=None,
                selection=None,
                parent_hooks=(sys.getprofile(), sys.gettrace()),
            )
        )
        return
    if not context.guard_frames or context.guard_frames[-1].frame is not frame:
        raise ValueError("Ordered actual import guard closure required")
    row = context.guard_frames.pop()
    context.guard_closed.append(row)
    _guard_binding(provider)
    if row.profile is not None:
        _guard_profile(row)
    if sys.getprofile() is not row.parent_hooks[0] or sys.gettrace() is not row.parent_hooks[1]:
        raise ValueError("Nested import guard did not restore its actual parent")
    validate_import_guards(context)


def _library_code(path, role, name):
    full = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    if role is not None:
        full = next(
            item for item in full.co_consts if type(item) is CodeType and item.co_name == role
        )
    return next(item for item in full.co_consts if type(item) is CodeType and item.co_name == name)


def _context_backend(decorator):
    """Bind the original factory/closure bodies without invoking either."""
    for module, (name, filename, pin) in zip((contextlib, functools), CONTEXT_STDLIB, strict=True):
        path = Path(filename)
        if (
            sys.modules.get(name) is not module
            or vars(module).get("__file__") != filename
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != pin
        ):
            raise ValueError("Pinned contextmanager runtime source required")
    factory = vars(contextlib).get("contextmanager")
    if factory is not contextmanager:
        raise ValueError("Original contextmanager factory export required")
    if vars(contextlib).get("wraps") is not vars(functools).get("wraps"):
        raise ValueError("Original contextmanager wraps dispatch required")
    functions = (
        (factory, contextlib, "contextmanager"),
        (functools.wraps, functools, "wraps"),
        (functools.update_wrapper, functools, "update_wrapper"),
        (decorator.beartype_nontype, decorator, "beartype_nontype"),
    )
    for function, module, name in functions:
        if (
            type(function) is not FunctionType
            or function.__globals__ is not vars(module)
            or typed._constant(function.__code__)
            != typed._constant(_library_code(Path(module.__file__), None, name))
        ):
            raise ValueError("Original contextmanager dispatch body required")
        _function_state(function)
    helper = next(
        code
        for code in factory.__code__.co_consts
        if type(code) is CodeType and code.co_name == "helper"
    )
    return factory, helper, functions


def _context_helper(function, delegate, backend):
    """The live, observed stdlib closure; no unwrap-by-value substitution."""
    if (
        type(function) is not FunctionType
        or function.__code__ is not backend.context_helper
        or function.__globals__ is not vars(contextlib)
        or function.__defaults__ is not None
        or function.__kwdefaults__ is not None
        or function.__code__.co_freevars != ("func",)
        or type(function.__closure__) is not tuple
        or len(function.__closure__) != 1
        or function.__closure__[0].cell_contents is not delegate
        or vars(function).get("__wrapped__") is not delegate
        or function.__annotations__ is not delegate.__annotations__
        or any(
            getattr(function, name) is not getattr(delegate, name)
            for name in ("__name__", "__qualname__", "__module__", "__doc__")
        )
    ):
        raise ValueError("Actual contextmanager export/closure/delegate required")
    return _wrapper_state(function, backend)


def _context_bindings(backend):
    if vars(contextlib).get("wraps") is not backend.context_functions[1][0]:
        raise ValueError("Original contextmanager wraps dispatch changed")
    for (function, module, name), expected in zip(
        backend.context_functions, backend.context_states, strict=True
    ):
        if vars(module).get(name) is not function:
            raise ValueError("Original contextmanager runtime export changed")
        _same(_function_state(function), expected)


def _context_call(context, caller, function, arg0, offset):
    """Authenticate the selected callable, before caller locals can self-restore."""
    # Keep the selected CALL operands before target/caller inspection can fail.
    context.context_call_raw.append((caller, function, arg0, offset))
    parent = context.frames.get(id(caller))
    if parent is not None and parent[0] is caller and parent[1] == "context":
        owner = parent[2]
        kind, target = "reconstructed", owner.target
        expected = None if owner.row is None else owner.row.output
    else:
        target = _target(arg0, sys._getframe())
        if target is None or target[0] != (None, CONTEXT_EXPORT[2]):
            return
        kind, owner, expected = "original", None, arg0
        if caller is not target[2]:
            raise ValueError("Direct original contextmanager CALL caller required")
    if context.capture_error is not None:
        raise ValueError("Incomplete contextmanager CALL observation")
    validate_import_guards(context)
    _context_bindings(context.backend)
    if (
        function is not context.backend.context_factory
        or type(arg0) is not FunctionType
        or arg0 is not expected
        or len(context.context_calls) >= 2
        or any(
            old.frame is None or (old.kind == kind and old.caller is caller)
            for old in context.context_calls
        )
    ):
        raise ValueError("Actual selected original contextmanager callable required")
    witness = SimpleNamespace(
        context=context,
        ordinal=len(context.context_calls),
        kind=kind,
        caller=caller,
        caller_code=caller.f_code,
        callee=function,
        callee_code=function.__code__,
        arg0=arg0,
        offset=offset,
        target=target,
        owner=owner,
        frame=None,
        returned=False,
        output=None,
        primary=None,
    )
    context.context_calls.append(witness)


def _context_call_entry(context, frame, kind, arg0, owner=None):
    candidates = [
        old
        for old in context.context_calls
        if old.frame is None and old.caller is frame.f_back and old.kind == kind
    ]
    if len(candidates) != 1:
        raise ValueError("Actual contextmanager CALL witness required before entry")
    witness = candidates[0]
    if (
        witness.context is not context
        or witness.callee is not context.backend.context_factory
        or witness.callee_code is not frame.f_code
        or witness.caller_code is not frame.f_back.f_code
        or witness.arg0 is not arg0
        or frame.f_locals.get("func") is not arg0
        or witness.owner is not owner
    ):
        raise ValueError("Selected contextmanager CALL/entry association changed")
    witness.frame = frame
    return witness


def _context_call_check(context, witness, frame, kind, arg0, owner, output):
    if (
        witness.context is not context
        or type(witness.ordinal) is not int
        or not 0 <= witness.ordinal < len(context.context_calls)
        or context.context_calls[witness.ordinal] is not witness
        or witness.kind != kind
        or witness.owner is not owner
        or witness.callee is not context.backend.context_factory
        or witness.callee_code is not context.backend.context_factory.__code__
        or witness.frame is not frame
        or witness.caller is not frame.f_back
        or witness.caller_code is not witness.caller.f_code
        or witness.arg0 is not arg0
        or frame.f_locals.get("func") is not arg0
        or not witness.returned
        or witness.primary is not None
        or witness.output is not output
    ):
        raise ValueError("Retained actual contextmanager CALL witness changed")


def _context_event(context, role, frame, event, value):
    """Retain actual reconstruction entry/return, never call a decorator."""
    backend = context.backend
    if event == "start":
        _context_bindings(backend)
        if role == "context":
            function = frame.f_locals.get("func")
            if type(function) is not FunctionType:
                return
            generator = vars(function).get("__wrapped__")
            target = _target(generator, frame)
            if target is None:
                return
            relative, pin, name = CONTEXT_EXPORT
            path = network.NATIVE / relative
            if (
                target[0] != (None, name)
                or {**network.PINS, **channels.PINS}.get(relative) != pin
                or frame.f_locals.get("func_contextmanager") is not backend.context_factory
                or frame.f_back.f_code is not backend.context_dispatch.__code__
                or frame.f_back.f_globals is not backend.context_dispatch.__globals__
                or frame.f_back.f_locals.get("obj") is not function
            ):
                raise ValueError("Original pinned contextmanager dispatch required")
            node = next(
                n
                for n in ast.parse(path.read_bytes()).body
                if isinstance(n, ast.FunctionDef) and n.name == name
            )
            if (
                path.is_symlink()
                or hashlib.sha256(path.read_bytes()).hexdigest() != pin
                or len(node.decorator_list) != 1
                or ast.dump(node.decorator_list[0])
                != ast.dump(ast.Name(id="contextmanager", ctx=ast.Load()))
            ):
                raise ValueError("Original single contextmanager declaration required")
            _import_ancestry(context, target)
            origins = [
                old
                for old in context.source_context_factories
                if old.output is function
                and old.generator is generator
                and old.returned
                and old.primary is None
            ]
            if len(origins) != 1:
                raise ValueError("Actual original contextmanager factory return required")
            initial = _context_helper(function, generator, backend)
            _same(initial, origins[0].bindings)
            if type(generator.__annotations__) is not dict or tuple(generator.__annotations__) != (
                "return",
            ):
                raise ValueError("Exact original contextmanager annotation roster required")
            item = SimpleNamespace(
                context=context,
                frame=frame,
                input=function,
                generator=generator,
                input_bindings=initial,
                target=target,
                row=None,
                factory_frame=None,
                factory_output=None,
                output=None,
                returned=False,
                primary=None,
                bindings=None,
                source_factory=origins[0],
                annotation_dictionary=generator.__annotations__,
                annotation_before=tuple(generator.__annotations__.items()),
                annotation_after=None,
            )
            context.context_exports.append(item)
        else:
            parent = context.frames.get(id(frame.f_back))
            if parent is None or parent[0] is not frame.f_back or parent[1] != "context":
                generator = frame.f_locals.get("func")
                target = _target(generator, frame)
                if target is None:
                    return
                relative, pin, name = CONTEXT_EXPORT
                if (
                    target[0] != (None, name)
                    or {**network.PINS, **channels.PINS}.get(relative) != pin
                    or frame.f_back is not target[2]
                    or vars(target[1]).get("contextmanager") is not backend.context_factory
                    or any(old.target[1] is target[1] for old in context.source_context_factories)
                ):
                    raise ValueError("Once-only direct native contextmanager factory required")
                _import_ancestry(context, target)
                item = SimpleNamespace(
                    context=context,
                    frame=frame,
                    target=target,
                    generator=generator,
                    output=None,
                    bindings=None,
                    returned=False,
                    primary=None,
                )
                item.call_witness = _context_call_entry(context, frame, "original", generator)
                item.call_witness.owner = item
                context.source_context_factories.append(item)
                context.frames[id(frame)] = (frame, "context_original", item)
                return
            item = parent[2]
            row = item.row
            if (
                item.factory_frame is not None
                or row is None
                or not row.returned
                or row.primary is not None
                or frame.f_locals.get("func") is not row.output
                or item.frame.f_locals.get("generator_checked") is not row.output
            ):
                raise ValueError("Actual checked generator/factory input required")
            item.factory_frame = frame
            item.factory_call = _context_call_entry(
                context, frame, "reconstructed", row.output, item
            )
        context.frames[id(frame)] = (frame, role, item)
        return
    found = context.frames.get(id(frame))
    if found is None or found[0] is not frame or found[1] not in (role, "context_original"):
        return
    item = found[2]
    context.last_raw = (frame, event, value)
    if event == "unwind":
        context.source_errors.append(context.last_raw)
        item.primary = value
        if found[1] == "context_original":
            item.call_witness.primary = value
        elif role == "context_factory":
            item.factory_call.primary = value
        return
    context.raw_returns.append(context.last_raw)
    if found[1] == "context_original":
        item.output, item.returned = value, True
        item.call_witness.output, item.call_witness.returned = value, True
        if value is not frame.f_locals.get("helper"):
            raise ValueError("Actual original contextmanager closure return required")
        item.bindings = _context_helper(value, item.generator, backend)
    elif role == "context_factory":
        item.factory_output = value
        item.factory_call.output, item.factory_call.returned = value, True
        if value is not frame.f_locals.get("helper"):
            raise ValueError("Actual reconstructed contextmanager closure return required")
        item.bindings = _context_helper(value, item.row.output, backend)
    else:
        item.output, item.returned = value, True
        if (
            value is not item.factory_output
            or item.factory_frame is None
            or item.primary is not None
        ):
            raise ValueError("Actual completed contextmanager reconstruction required")
        _context_export(item.row, backend)


def _context_alias_bindings(item, function, expected, backend):
    """Transport only the shared annotation seen at actual factory return."""
    row = item.row
    before, after = item.annotation_before, item.annotation_after
    offset = len(row.factory_original_function)
    if (
        not row.returned
        or row.primary is not None
        or after is None
        or len(before) != 1
        or len(after) != 1
        or before[0][0] is not after[0][0]
        or row.original.__annotations__ is not item.annotation_dictionary
        or row.factory_original_bindings[offset] is not item.annotation_dictionary
        or row.factory_original_bindings[offset + 1] is not after[0][0]
        or row.factory_original_bindings[offset + 2] is not after[0][1]
    ):
        raise ValueError("Actual generator factory annotation witness required")
    current = _context_helper(function, row.original, backend)
    prefix = len(_function_state(function))
    if (
        expected[prefix] is not item.annotation_dictionary
        or expected[prefix + 1] is not before[0][0]
        or expected[prefix + 2] is not before[0][1]
    ):
        raise ValueError("Original pre-factory annotation alias changed")
    allowed = list(expected)
    allowed[prefix + 2] = after[0][1]
    _same(current, tuple(allowed))


def _context_export(row, backend):
    item = getattr(row, "context_export", None)
    if item is None:
        return row.output
    _context_bindings(backend)
    origin = item.source_factory
    if (
        item.row is not row
        or not item.returned
        or item.primary is not None
        or not any(item is old for old in item.context.context_exports)
        or item.generator is not row.original
        or item.target[1] is not row.module
        or item.factory_frame is None
        or item.factory_output is not item.output
        or item.factory_frame.f_code is not backend.context_factory.__code__
        or item.factory_frame.f_globals is not backend.context_factory.__globals__
        or item.factory_frame.f_back is not item.frame
        or item.factory_frame.f_locals.get("func") is not row.output
        or item.factory_frame.f_locals.get("helper") is not item.output
        or item.frame.f_code is not backend.functions["context"].__code__
        or item.frame.f_locals.get("generator_checked") is not row.output
        or item.frame.f_locals.get("generator_checked_contextmanager") is not item.output
        or item.frame.f_locals.get("func_contextmanager") is not backend.context_factory
        or item.frame.f_locals.get("func") is not item.input
        or not any(origin is old for old in item.context.source_context_factories)
        or not origin.returned
        or origin.primary is not None
        or origin.output is not item.input
        or origin.generator is not row.original
        or origin.target[1] is not row.module
        or origin.frame.f_back is not row.ancestor
        or origin.frame.f_code is not backend.context_factory.__code__
        or origin.frame.f_globals is not backend.context_factory.__globals__
        or origin.frame.f_locals.get("func") is not row.original
        or origin.frame.f_locals.get("helper") is not item.input
        or vars(row.module).get("contextmanager") is not backend.context_factory
    ):
        raise ValueError("Actual retained contextmanager reconstruction changed")
    _context_alias_bindings(item, item.input, item.input_bindings, backend)
    _context_alias_bindings(item, origin.output, origin.bindings, backend)
    _same(_context_helper(item.output, row.output, backend), item.bindings)
    _context_call_check(
        item.context,
        origin.call_witness,
        origin.frame,
        "original",
        row.original,
        origin,
        item.input,
    )
    _context_call_check(
        item.context,
        item.factory_call,
        item.factory_frame,
        "reconstructed",
        row.output,
        item,
        item.output,
    )
    return item.output


def _backend():
    """Lazy genuine imports; only the explicitly released observer enters here."""
    modules = {}
    for name, pin in LIBRARIES.items():
        module = importlib.import_module(name)
        path = Path(module.__file__)
        relative = Path(name.replace(".", "/") + ".py")
        if path.is_symlink() or not any(path.resolve() == root / relative for root in ROOTS):
            raise ValueError("Original retained beartype source origin required")
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError("Pinned original beartype library required")
        modules[name] = module
    decorator = modules["beartype._decor._nontype.decornontype"]
    maker = modules["beartype._util.func.utilfuncmake"]
    generator = modules["beartype._decor._nontype._wrap.wrapmain"]
    functions = dict(
        decorator=decorator.beartype_func,
        generate=generator.generate_code,
        make=maker.make_func,
        loader=modules["beartype.claw._importlib._clawimpload"].BeartypeSourceFileLoader.get_code,
        context=decorator._beartype_func_contextlib_contextmanager,
    )
    if (
        decorator.generate_code is not functions["generate"]
        or decorator.make_func is not functions["make"]
    ):
        raise ValueError("Actual imported decorator/generator/maker aliases required")
    for role, fn in functions.items():
        module = sys.modules[fn.__module__]
        path = Path(module.__file__)
        if fn.__globals__ is not vars(module) or typed._constant(fn.__code__) != typed._constant(
            _library_code(
                path, "BeartypeSourceFileLoader" if role == "loader" else None, fn.__name__
            )
        ):
            raise ValueError("Exact original beartype function body required: " + role)
        _function_state(fn)
    context_factory, context_helper, context_functions = _context_backend(decorator)
    functions["context_factory"] = context_factory
    return SimpleNamespace(
        modules=modules,
        functions=functions,
        states=tuple((fn, _function_state(fn)) for fn in functions.values())
        + tuple((fn, _function_state(fn)) for fn, _, _ in context_functions),
        context_factory=context_factory,
        context_helper=context_helper,
        context_dispatch=decorator.beartype_nontype,
        context_functions=context_functions,
        context_states=tuple(_function_state(fn) for fn, _, _ in context_functions),
        metadata=modules["beartype._check.metadata.metacheck"].BeartypeCheckMeta,
        configuration=modules["beartype._conf.confmain"].BeartypeConf,
        loader_type=modules["beartype.claw._importlib._clawimpload"].BeartypeSourceFileLoader,
    )


def _target(function, frame):
    if type(function) is not FunctionType:
        return None
    pieces = function.__qualname__.split(".")
    key = (None, pieces[0]) if len(pieces) == 1 else tuple(pieces)
    sites = {**network.SITES, **channels.SITES}
    if key not in sites:
        return None
    relative = sites[key]
    module_name = relative[:-3].replace("/", ".")
    module = sys.modules.get(module_name)
    path = network.NATIVE / relative
    if (
        type(module) is not ModuleType
        or function.__globals__ is not vars(module)
        or function.__code__.co_filename != str(path)
    ):
        return None
    compiler = channels if key in channels.SITES else network
    if typed._constant(function.__code__) != typed._constant(compiler.code(*key)):
        raise ValueError("Actual original native method code required")
    spec = vars(module).get("__spec__")
    if spec is None or spec.name != module_name or spec._initializing is not True:
        raise ValueError("Fresh original import frame required; retrospective decoration refused")
    ancestor = frame.f_back
    while ancestor is not None and not (
        ancestor.f_code.co_name == "<module>"
        and ancestor.f_globals is vars(module)
        and ancestor.f_code.co_filename == str(path)
    ):
        ancestor = ancestor.f_back
    if ancestor is None:
        raise ValueError("Actual native module-execution ancestry required")
    return key, module, ancestor


def _import_ancestry(context, target):
    _, module, ancestor = target
    origin = context.loaded_codes.get(module.__name__)
    if (
        origin is None
        or origin.output is not ancestor.f_code
        or vars(module)["__spec__"].loader is not origin.loader
        or not origin.returned
        or origin.primary is not None
    ):
        raise ValueError("Actual observed native loader/code/module ancestry required")


def _record_function(row, backend):
    function, original = row.output, row.original
    _same(_original_header(original), row.original_header)
    if function is original:
        if row.generated != "" or row.make is not None:
            raise ValueError("Only actual observed no-code decoration may return original function")
        return _wrapper_state(function, backend)
    if type(function) is not FunctionType or row.make is None:
        raise ValueError("Actual observed make_func return required")
    made = row.make
    if (
        made.output is not function
        or made.primary is not None
        or made.original is not original
        or made.text is not row.generated
        or vars(function).get("__wrapped__") is not original
        or vars(function).get("__beartype_wrapper") is not True
        or function.__globals__ is not made.globals
        or function.__code__
        is not next(
            code
            for code in made.compiled.co_consts
            if type(code) is CodeType and code.co_name == made.name
        )
        or type(function.__kwdefaults__) is not dict
        or any(function.__kwdefaults__.get(name) is not value for name, value in made.scope)
        or function.__kwdefaults__.get("__beartype_func") is not original
        or function.__annotations__ is not original.__annotations__
    ):
        raise ValueError("Original wrapper/code/scope/delegate return association changed")
    probe = compile(row.generated.strip(), made.filename, "exec", dont_inherit=True)
    if typed._constant(probe) != typed._constant(made.compiled):
        raise ValueError("Actual generated executable constants differ from observed source")
    meta = function.__kwdefaults__.get("__beartype_check_meta")
    if (
        type(meta) is not backend.metadata
        or object.__getattribute__(meta, "func") is not original
        or object.__getattribute__(meta, "conf") is not row.conf
        or object.__getattribute__(meta, "cls_stack") is not row.stack
        or object.__getattribute__(meta, "func_annotations") is not original.__annotations__
    ):
        raise ValueError(
            "Original check-time function/configuration/class/annotation edges changed"
        )
    return _wrapper_state(function, backend)


def _global_resolutions(function):
    return tuple(
        (name, function.__globals__, function.__globals__[name])
        if name in function.__globals__
        else (name, function.__builtins__, function.__builtins__[name])
        if name in function.__builtins__
        else (name, None, None)
        for name in function.__code__.co_names
    )


def _declaration_writes(tree, name):
    """Count module-scope bindings, excluding class/function-local namespaces."""
    pending, count = list(tree.body), 0
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            count += node.name == name
            continue
        targets = ()
        if isinstance(node, (ast.Assign, ast.Delete)):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.For, ast.AsyncFor)):
            targets = (node.target,)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            count += sum((alias.asname or alias.name.split(".")[0]) == name for alias in node.names)
        for target in targets:
            count += any(
                isinstance(item, ast.Name)
                and item.id == name
                and isinstance(item.ctx, (ast.Store, ast.Del))
                for item in ast.walk(target)
            )
        pending.extend(ast.iter_child_nodes(node))
    return count


def _immutable_default(value, depth=0):
    # Close admission before the shared constant encoder can compare types or
    # values. A foreign metaclass must never participate in these decisions.
    kind = type(value)
    if any(kind is allowed for allowed in (type(None), bool, int, float, complex, str, bytes)):
        return True
    return (
        kind is tuple
        and depth < 16
        and len(value) <= 512
        and all(_immutable_default(item, depth + 1) for item in value)
    )


def _unwrapped_signature(function, node, path, role, module, owner=None):
    """Closed source headers only; no annotation/default expression evaluation."""
    expected = _library_code(path, role, node.name)
    defaults = tuple(ast.literal_eval(item) for item in node.args.defaults) or None
    keywords = {
        arg.arg: ast.literal_eval(default)
        for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
        if default is not None
    } or None
    args = (
        *node.args.posonlyargs,
        *node.args.args,
        *node.args.kwonlyargs,
        *((node.args.vararg,) if node.args.vararg is not None else ()),
        *((node.args.kwarg,) if node.args.kwarg is not None else ()),
    )
    if (
        type(function) is not FunctionType
        or function.__globals__ is not vars(module)
        or typed._constant(function.__code__) != typed._constant(expected)
        or type(function.__module__) is not str
        or function.__module__ != module.__name__
        or type(function.__name__) is not str
        or function.__name__ != node.name
        or type(function.__qualname__) is not str
        or function.__qualname__ != ((role + ".") if role is not None else "") + node.name
        or not _immutable_default(defaults)
        or not _immutable_default(function.__defaults__)
        or typed._constant(function.__defaults__) != typed._constant(defaults)
        or (function.__kwdefaults__ is not None and type(function.__kwdefaults__) is not dict)
        or any(
            type(key) is not str or not _immutable_default(value)
            for key, value in (function.__kwdefaults__ or {}).items()
        )
        or (function.__kwdefaults__ is None) != (keywords is None)
        or typed._constant(tuple((function.__kwdefaults__ or {}).items()))
        != typed._constant(tuple((keywords or {}).items()))
        or node.returns is not None
        or any(arg.annotation is not None for arg in args)
        or type(function.__annotations__) is not dict
        or function.__annotations__
    ):
        raise ValueError("Complete original unwrapped source-method header required")
    free = expected.co_freevars
    closure = function.__closure__
    if not free:
        if closure is not None:
            raise ValueError("Unexpected unwrapped source-method closure")
    elif (
        free != ("__class__",)
        or owner is None
        or type(closure) is not tuple
        or len(closure) != 1
        or closure[0].cell_contents is not owner
    ):
        raise ValueError("Original source-method class closure required")
    # Includes actual cached builtins and every reached global identity.
    _function_state(function)


def _class_surface(value):
    return (
        value,
        type.__getattribute__(value, "__bases__"),
        type.__getattribute__(value, "__mro__"),
        type.__getattribute__(value, "__qualname__"),
        *(atom for pair in vars(value).items() for atom in pair),
    )


def _retain_declaration(row, name, value, methods, backend):
    row.declaration_bindings.append(
        SimpleNamespace(
            name=name,
            value=value,
            namespace=vars(row.module),
            surface=_class_surface(value) if methods is not None else None,
            methods=tuple(
                (key, function, _wrapper_state(function, backend)) for key, function in methods
            )
            if methods is not None
            else ((None, value, _wrapper_state(value, backend)),),
        )
    )


def _check_declarations(row, backend):
    for declaration in getattr(row, "declaration_bindings", ()):
        if declaration.namespace.get(declaration.name) is not declaration.value:
            raise ValueError("Retained source declaration identity changed")
        if declaration.surface is not None:
            _same(_class_surface(declaration.value), declaration.surface)
        for name, function, state in declaration.methods:
            if name is not None and vars(declaration.value).get(name) is not function:
                raise ValueError("Retained source class-method identity changed")
            _same(_wrapper_state(function, backend), state)


def _published_global(context, row, name, value):
    """A newly resolved name must be a later original source declaration."""
    origin = row.origin
    path = network.NATIVE / (origin.name.replace(".", "/") + ".py")
    relative = str(path.relative_to(network.NATIVE))
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != {**network.PINS, **channels.PINS}[relative]:
        raise ValueError("Original publication source changed")
    tree = ast.parse(raw)
    definitions = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and node.name == name
        and node.end_lineno >= row.original.__code__.co_firstlineno
    ]
    if len(definitions) != 1 or _declaration_writes(tree, name) != 1:
        raise ValueError("New source lookup has no unique later declaration: " + name)
    node = definitions[0]
    if isinstance(node, ast.ClassDef):
        observed = [
            other
            for other in context.rows
            if other.module is row.module and other.stack is not None and other.target[0][0] == name
        ]
        if observed:
            if any(other.stack[0] is not value for other in observed):
                raise ValueError("Actual later class/factory identity changed")
            return
        # Unwrapped, unselected classes still require every source method;
        # arbitrary wrapper chains or supplied namespace objects are refused.
        if (
            type(value) is not type
            or type(vars(value).get("__module__")) is not str
            or type(type.__getattribute__(value, "__qualname__")) is not str
            or vars(value)["__module__"] != origin.name
            or type.__getattribute__(value, "__qualname__") != name
        ):
            raise ValueError("Original later class declaration required")
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
        if not methods:
            raise ValueError("Later class has no retained source-method correspondence")
        for method in methods:
            function = vars(value).get(method.name)
            _unwrapped_signature(function, method, path, name, row.module, owner=value)
        _retain_declaration(
            row,
            name,
            value,
            tuple((method.name, vars(value)[method.name]) for method in methods),
            context.backend,
        )
    else:
        observed = [
            other
            for other in context.rows
            if other.module is row.module and other.target[0] == (None, name)
        ]
        if observed:
            if any(other.output is not value for other in observed):
                raise ValueError("Actual later function/factory identity changed")
            return
        _unwrapped_signature(value, node, path, None, row.module)
        _retain_declaration(row, name, value, None, context.backend)


def _publish_module(context, origin, frame, event, value):
    context.module_raw.append((frame, event, value))
    module = sys.modules.get(origin.name)
    spec = None if type(module) is not ModuleType else vars(module).get("__spec__")
    if (
        frame.f_code is not origin.output
        or frame.f_code.co_name != "<module>"
        or type(module) is not ModuleType
        or frame.f_globals is not vars(module)
        or type(vars(module).get("__name__")) is not str
        or vars(module)["__name__"] != origin.name
        or spec is None
        or spec.loader is not origin.loader
        or spec._initializing is not True
    ):
        raise ValueError("Actual original loaded module execution required")
    if event == "start":
        if origin.module_frame is not None:
            raise ValueError("Original module execution may not be repeated")
        origin.module_frame = frame
        return
    if origin.module_frame is not frame:
        raise ValueError("Original source module frame changed")
    if event == "unwind":
        origin.module_error = value
        return
    if value is not None or origin.module_published:
        raise ValueError("Single successful original module return required")
    for row in context.rows:
        if row.origin is not origin:
            continue
        if row.ancestor is not frame or not row.returned or row.primary is not None:
            raise ValueError("Complete factory/module publication ancestry required")
        current = _record_function(row, context.backend)
        original = _wrapper_state(row.original, context.backend)
        state = _function_state(row.original)
        # Preserve the original delegate too, including generated-wrapper cases.
        # Only absent names may gain a witnessed later declaration here.
        _same(
            original[len(state) :],
            row.factory_original_bindings[len(row.factory_original_function) :],
        )
        for (name, scope, old), (new_name, new_scope, new) in zip(
            row.factory_globals, _global_resolutions(row.original), strict=True
        ):
            if name is not new_name:
                raise ValueError("Original function lookup roster changed")
            if scope is not None:
                if scope is not new_scope or old is not new:
                    raise ValueError("Existing factory-time lookup changed: " + name)
            elif new_scope is not None:
                if new_scope is not vars(module):
                    raise ValueError("Previously absent builtin lookup changed")
                _published_global(context, row, name, new)
        if row.output is row.original:
            row.published_bindings = current
        else:
            _same(current, row.bindings)
        row.original_bindings = original
    origin.module_published = True
    for row in context.rows:
        if row.origin is origin:
            _counter_register(context, row)


def _observe(context, frame, event, value):
    """Only canonical monitored events arrive here; no factory/body is called."""
    role = context.codes.get(frame.f_code)
    if role is None:
        return
    if event == "start":
        if context.capture_error is not None:
            raise WrapperAuthorityRejected(
                "Incomplete factory capture prevents more work", stage="capture", partial=context
            )
        for function, expected in context.backend.states:
            _same(_function_state(function), expected)
        if role in ("context", "context_factory"):
            _context_event(context, role, frame, event, value)
            return
        if role == "loader":
            name = frame.f_locals.get("fullname")
            relative = name.replace(".", "/") + ".py" if type(name) is str else None
            if relative not in {**network.PINS, **channels.PINS}:
                return
            loader = frame.f_locals.get("self")
            if (
                type(loader) is not context.backend.loader_type
                or loader.name != name
                or Path(loader.path).resolve() != network.NATIVE / relative
                or name in context.loaded_codes
            ):
                raise ValueError("Fresh actual native source loader required")
            row = SimpleNamespace(
                loader=loader,
                name=name,
                output=None,
                primary=None,
                returned=False,
                module_frame=None,
                module_published=False,
                module_error=None,
            )
            context.loaded_codes[name] = row
            context.frames[id(frame)] = (frame, role, row)
        elif role == "decorator":
            original = frame.f_locals["func"]
            target = _target(original, frame)
            if target is None:
                return
            _import_ancestry(context, target)
            if len(context.rows) >= MAX_FACTORIES:
                raise ValueError("Bounded native factory observation exhausted")
            key, module, ancestor = target
            kwargs = frame.f_locals["kwargs"]
            stack = kwargs.get("cls_stack")
            if key[0] is not None and (
                type(stack) is not tuple
                or len(stack) != 1
                or vars(stack[0]).get(key[1]) is not original
            ):
                raise ValueError("Actual original class/undecorated method association required")
            row = SimpleNamespace(
                frame=frame,
                original=original,
                target=target,
                stack=stack,
                conf=frame.f_locals["conf"],
                module=module,
                ancestor=ancestor,
                generated=None,
                generate_frame=None,
                make=None,
                output=None,
                returned=False,
                primary=None,
                bindings=None,
                original_header=_original_header(original),
                original_bindings=None,
                origin=context.loaded_codes.get(module.__name__),
                factory_function=None,
                factory_globals=None,
                factory_original_function=None,
                factory_original_bindings=None,
                published_bindings=None,
                declaration_bindings=[],
                context_export=None,
            )
            parent = context.frames.get(id(frame.f_back))
            if parent is not None and parent[0] is frame.f_back and parent[1] == "context":
                item = parent[2]
                if item.row is not None or item.generator is not original or stack is not None:
                    raise ValueError("Single actual contextmanager generator factory required")
                item.row, row.context_export = row, item
            context.rows.append(row)
            context.frames[id(frame)] = (frame, role, row)
        else:
            parent = context.frames.get(id(frame.f_back))
            if parent is None or parent[0] is not frame.f_back or parent[1] != "decorator":
                return
            row = parent[2]
            if role == "generate":
                if row.generate_frame is not None:
                    raise ValueError("Duplicate original generator entry")
                row.generate_frame = frame
            else:
                if row.make is not None or frame.f_locals["func_wrapped"] is not row.original:
                    raise ValueError("Original once-only wrapper maker/delegate required")
                scope = frame.f_locals["func_locals"]
                if type(scope) is not dict or frame.f_locals["func_code"] is not row.generated:
                    raise ValueError("Actual generated text and scope association required")
                row.make = SimpleNamespace(
                    frame=frame,
                    original=row.original,
                    text=row.generated,
                    name=frame.f_locals["func_name"],
                    scope=tuple(scope.items()),
                    output=None,
                    primary=None,
                    globals=None,
                    compiled=None,
                    filename=None,
                )
            context.frames[id(frame)] = (frame, role, row)
        return
    if role in ("context", "context_factory"):
        _context_event(context, role, frame, event, value)
        return
    found = context.frames.get(id(frame))
    if found is None or found[0] is not frame:
        return
    row = found[2]
    context.last_raw = (frame, event, value)
    if event == "unwind":
        context.source_errors.append(context.last_raw)
        if role == "make":
            row.make.primary = value
        else:
            row.primary = value
        return
    context.raw_returns.append(context.last_raw)
    if role == "loader":
        row.output, row.returned = value, True
        if type(value) is not CodeType:
            raise ValueError("Actual native imported module code required")
        context.module_codes[value] = row
    elif role == "generate":
        row.generated = value
    elif role == "make":
        made = row.make
        made.output = value
        made.globals = frame.f_locals.get("func_globals")
        made.compiled = frame.f_locals.get("func_code_compiled")
        made.filename = frame.f_locals.get("func_filename")
    else:
        row.output, row.returned = value, True
        # No pooled decor_meta fields survive as authority. Capture final
        # defaults/metadata now, before that pooled object can be reused.
        row.bindings = _record_function(row, context.backend)
        row.factory_function = _function_state(row.output)
        row.factory_globals = _global_resolutions(row.original)
        row.factory_original_function = _function_state(row.original)
        row.factory_original_bindings = _wrapper_state(row.original, context.backend)
        if row.context_export is not None:
            item = row.context_export
            if row.original.__annotations__ is not item.annotation_dictionary:
                raise ValueError("Actual generator factory annotation dictionary changed")
            item.annotation_after = tuple(row.original.__annotations__.items())


def _binding(row, backend):
    _check_declarations(row, backend)
    effect = getattr(row, "counter_effect", None)
    if effect is not None:
        _counter_check(effect)
    expected = (
        row.published_bindings
        if getattr(row, "published_bindings", None) is not None
        else row.bindings
    )
    if effect is None:
        _same(_record_function(row, backend), expected)
    else:
        _counter_atoms(row, row.output, _record_function(row, backend), expected, effect.value)
    if type(row.original_bindings) is not tuple or not row.original_bindings:
        raise ValueError("Complete post-import native method binding required")
    if effect is None:
        _same(_wrapper_state(row.original, backend), row.original_bindings)
    else:
        _counter_atoms(
            row,
            row.original,
            _wrapper_state(row.original, backend),
            row.original_bindings,
            effect.value,
        )
    role, name = row.target[0]
    owner = row.module if role is None else row.stack[0]
    if role is not None and vars(row.module).get(role) is not owner:
        raise ValueError("Actual native module/class publication changed")
    if vars(owner).get(name) is not _context_export(row, backend):
        raise ValueError("Actual imported owner/export method changed")
    return row.original


@contextmanager
def observing_native_imports(*, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1" or not __debug__:
        raise WrapperAuthorityRejected("Actual wrapper/import work remains held", stage="release")
    with _LOCK:
        if _ACTIVE:
            raise WrapperAuthorityRejected(
                "Exclusive fresh import observer required", stage="reentry"
            )
        targets = {
            relative[:-3].replace("/", ".") for relative in {**network.PINS, **channels.PINS}
        }
        if any(name in sys.modules for name in targets):
            raise WrapperAuthorityRejected(
                "Native targets already imported; cannot issue retrospectively", stage="fresh"
            )
        backend = _backend()
        guards = _guard_sources()
        before = sys.getprofile(), sys.gettrace()
        monitor = sys.monitoring
        original = tuple((monitor.get_tool(i), monitor.get_events(i)) for i in range(6))
        slots = [i for i, (name, _) in enumerate(original) if name is None]
        if not slots:
            raise WrapperAuthorityRejected(
                "Independent monitoring slot unavailable", stage="monitor"
            )
        tool = slots[-1]
        context = SimpleNamespace(
            backend=backend,
            codes={fn.__code__: name for name, fn in backend.functions.items()},
            rows=[],
            loaded_codes={},
            module_codes={},
            module_raw=[],
            frames={},
            raw_returns=[],
            source_errors=[],
            last_raw=None,
            capture_error=None,
            capture_errors=[],
            primary=None,
            record=None,
            published=False,
            hook_losses=[],
            thread=get_ident(),
            active=True,
            tool=tool,
            original_hooks=before,
            guard_providers=guards,
            guard_frames=[],
            guard_closed=[],
            guard_raw=[],
            guard_error=None,
            counter_effects=[],
            counter_codes={},
            counter_attempts=[],
            counter_raw=[],
            context_exports=[],
            source_context_factories=[],
            context_calls=[],
            context_call_raw=[],
            monitor_original=original,
            monitor_final=None,
            monitor_before_cleanup=None,
            monitor_losses=[],
            monitor_callbacks=[],
            monitor_local_events=(),
            expected_events=(
                monitor.events.PY_START
                | monitor.events.PY_RETURN
                | monitor.events.PY_UNWIND
                | monitor.events.CALL
            ),
        )
        context.tool_label = "Cells original molecule wrapper import:" + str(id(context))
        _ACTIVE.append(context)

        def report(event, code, offset, value=None):
            if (
                code not in context.codes
                and code not in context.guard_providers
                and code not in context.module_codes
                and code not in context.counter_codes
            ):
                return
            frame = sys._getframe(2)
            if event != "start":
                # Raw source/unwind witness precedes every fallible guard or capture.
                context.last_raw = (frame, event, value)
            try:
                if frame.f_code is not code:
                    raise ValueError("Actual monitored factory frame required")
                if code in context.guard_providers:
                    _guard_event(context, context.guard_providers[code], frame, event, value)
                elif code in context.counter_codes:
                    effect, role = context.counter_codes[code]
                    _counter_event(context, effect, role, frame, event, value)
                elif code in context.module_codes:
                    validate_import_guards(context)
                    _publish_module(context, context.module_codes[code], frame, event, value)
                else:
                    validate_import_guards(context)
                    _observe(context, frame, event, value)
            except BaseException as error:
                if context.capture_error is None:
                    context.capture_error = error
                context.capture_errors.append((event, error, frame, value))
                if event == "start":
                    raise

        def start(code, offset):
            report("start", code, offset)

        def returned(code, offset, value):
            report("return", code, offset, value)

        def unwound(code, offset, value):
            report("unwind", code, offset, value)

        def called(code, offset, function, arg0):
            factory = getattr(backend, "context_factory", None)
            contextual = (
                type(function) is FunctionType
                and type(factory) is FunctionType
                and function.__code__ is factory.__code__
            )
            if type(function) is not FunctionType or (
                function.__code__ not in context.counter_codes and not contextual
            ):
                return
            caller = None
            try:
                caller = sys._getframe(1)
                if caller.f_code is not code:
                    raise ValueError("Actual metadata helper caller frame required")
                if contextual:
                    _context_call(context, caller, function, arg0, offset)
                else:
                    _counter_call(context, caller, function)
            except BaseException as error:
                if context.capture_error is None:
                    context.capture_error = error
                context.capture_errors.append(("call", error, caller, function))
                raise

        reserved, primary, cleanup = False, None, []
        try:
            monitor.use_tool_id(tool, context.tool_label)
            reserved = True
            for event, callback in (
                (monitor.events.PY_START, start),
                (monitor.events.PY_RETURN, returned),
                (monitor.events.PY_UNWIND, unwound),
                (monitor.events.CALL, called),
            ):
                prior = monitor.register_callback(tool, event, callback)
                context.monitor_callbacks.append((event, callback, prior))
            # Stable for the whole window. Late expansion would invalidate an
            # inner observer's exact snapshot of this still-active outer tool.
            monitor.set_events(tool, context.expected_events)
            yield context
            if (
                not context.rows
                or context.capture_error is not None
                or context.hook_losses
                or context.guard_frames
                or any(
                    not call.returned or call.primary is not None for call in context.context_calls
                )
                or any(not row.returned or row.primary is not None for row in context.rows)
                or any(
                    effect.failed or effect.pending or effect.frames or effect.attempt is not None
                    for effect in context.counter_effects
                )
            ):
                raise WrapperAuthorityRejected(
                    "Complete original import/factory capture required",
                    stage="capture",
                    partial=context,
                ) from context.capture_error
            for row in context.rows:
                # Later declarations in the actual native module are now
                # complete. Preserve their real resolutions, not an early
                # incomplete import snapshot or a supplied namespace.
                if getattr(row, "origin", None) is not None:
                    if not row.origin.module_published or row.origin.module_error is not None:
                        raise ValueError("Successful original source publication required")
                else:
                    # Conditional/legacy unobserved-loader models retain the
                    # original strict equality; no late lookup may be refreshed.
                    row.original_bindings = _wrapper_state(row.original, backend)
                _binding(row, backend)
            context.record = ImportEvidence(
                LAW,
                True,
                len(context.rows),
                sum(row.make is not None for row in context.rows),
                tuple(context.raw_returns),
                tuple(context.source_errors),
            )
        except BaseException as error:
            primary, context.primary = error, error
            try:
                _FAILED.append(context)
            except BaseException as secondary:
                context.retention_error = (secondary, error)
            raise
        finally:
            if reserved:
                owned = False
                try:
                    context.monitor_before_cleanup = (
                        monitor.get_tool(tool),
                        monitor.get_events(tool),
                    )
                    owned = context.monitor_before_cleanup[0] is context.tool_label
                    if not owned or context.monitor_before_cleanup[1] != context.expected_events:
                        context.monitor_losses.append(
                            ("own_tool_or_events", context.monitor_before_cleanup)
                        )
                except BaseException as error:
                    cleanup.append(("monitor_before_cleanup", error))
                if owned:
                    try:
                        codes = {
                            id(code): code
                            for collection in (
                                context.codes,
                                context.guard_providers,
                                context.module_codes,
                                context.counter_codes,
                            )
                            for code in collection
                        }
                        for row in context.rows:
                            for function in (row.original, row.output):
                                if type(function) is FunctionType:
                                    codes[id(function.__code__)] = function.__code__
                        locals_before = []
                        for code in codes.values():
                            try:
                                mask = monitor.get_local_events(tool, code)
                                locals_before.append((code, mask))
                                if mask:
                                    context.monitor_losses.append(("local_events", code, mask))
                                    monitor.set_local_events(tool, code, 0)
                            except BaseException as error:
                                cleanup.append(("local_events", error))
                        context.monitor_local_events = tuple(locals_before)
                    except BaseException as error:
                        # Installed hooks may reject id(), values(), iteration
                        # or capture itself. Teardown below must still run.
                        cleanup.append(("local_events_bookkeeping", error))
                    try:
                        monitor.set_events(tool, 0)
                    except BaseException as error:
                        cleanup.append(("set_events", error))
                    for _retry in (0, 1):
                        try:
                            for event, callback, prior in context.monitor_callbacks:
                                try:
                                    replaced = monitor.register_callback(tool, event, prior)
                                    if replaced is not callback:
                                        context.monitor_losses.append(("callback", event, replaced))
                                except BaseException as error:
                                    cleanup.append(("register_callback", error))
                            break
                        except BaseException as error:
                            cleanup.append(("callback_bookkeeping", error))
                    try:
                        monitor.free_tool_id(tool)
                    except BaseException as error:
                        cleanup.append(("free_tool_id", error))
            for name, prior in (("profile", before[0]), ("trace", before[1])):
                try:
                    getter, setter = getattr(sys, "get" + name), getattr(sys, "set" + name)
                    if getter() is not prior:
                        context.hook_losses.append(("cleanup", getter.__name__))
                        setter(prior)
                except BaseException as error:
                    cleanup.append(("hook_restore", error))
            context.active = False
            for _retry in (0, 1):
                try:
                    if not _ACTIVE or _ACTIVE[-1] is not context:
                        raise ValueError("Actual import context stack changed")
                    _ACTIVE.pop()
                    break
                except BaseException as error:
                    cleanup.append(("active_stack", error))
            final = None
            try:
                final = tuple((monitor.get_tool(i), monitor.get_events(i)) for i in range(6))
            except BaseException as error:
                cleanup.append(("monitor_final", error))
            context.monitor_final = final
            restored_hooks = []
            for name, prior in (("profile", before[0]), ("trace", before[1])):
                try:
                    getter = getattr(sys, "get" + name)
                    restored_hooks.append(getter() is prior)
                except BaseException as error:
                    cleanup.append(("hook_final", error))
                    restored_hooks.append(False)
            try:
                context.hooks_restored = all(restored_hooks)
                context.monitor_restored = final is not None and all(
                    name is old_name
                    and type(mask) is int
                    and type(old_mask) is int
                    and mask == old_mask
                    for (name, mask), (old_name, old_mask) in zip(final, original, strict=True)
                )
            except BaseException as error:
                context.hooks_restored = context.monitor_restored = False
                cleanup.append(("cleanup_summary", error))
            try:
                context.cleanup = tuple(cleanup)
            except BaseException as error:
                context.cleanup = cleanup
                context.cleanup_summary_error = error
                context.hooks_restored = False
            if primary is None and (
                cleanup
                or context.hook_losses
                or context.monitor_losses
                or not context.hooks_restored
                or not context.monitor_restored
            ):
                context.record = None
                error = WrapperAuthorityRejected(
                    "Import observer cleanup incomplete", stage="cleanup", partial=context
                )
                context.primary = error
                _FAILED.append(context)
                raise error
        try:
            # Teardown callbacks may have run since the pre-cleanup checks.
            # Validate their actual retained effects before publishing anything.
            for row in context.rows:
                _binding(row, backend)
            for row in context.rows:
                _ISSUED[row.output] = (context, row)
            # Delegate/binding/registry callbacks run after the earlier samples.
            # Sample again only after all of that fallible work; any loss stays
            # a refusal even when independent recovery restores the hooks.
            context.cleanup_monitor_final = context.monitor_final
            context.publication_monitor_final = None
            monitoring_changed = False
            try:
                final = tuple((monitor.get_tool(i), monitor.get_events(i)) for i in range(6))
                context.publication_monitor_final = final
                monitoring_changed = not all(
                    name is old_name
                    and type(mask) is int
                    and type(old_mask) is int
                    and mask == old_mask
                    for (name, mask), (old_name, old_mask) in zip(final, original, strict=True)
                )
            except BaseException as error:
                context.publication_monitor_error = error
                final = None
                monitoring_changed = True
            context.monitor_final = final
            if monitoring_changed:
                context.monitor_restored = False
                context.monitor_losses.append(("publication", final))
            publication_losses = []
            context.publication_hook_samples = []
            for name, prior in (("profile", before[0]), ("trace", before[1])):
                try:
                    actual = getattr(sys, "get" + name)()
                    context.publication_hook_samples.append((name, actual))
                    if actual is not prior:
                        publication_losses.append(name)
                except BaseException as error:
                    context.publication_hook_samples.append((name, error))
                    publication_losses.append(name)
            if publication_losses:
                context.hook_losses.append(("publication", tuple(publication_losses)))
                context.hooks_restored = False
            if monitoring_changed or publication_losses:
                raise WrapperAuthorityRejected(
                    "Import observer final monitoring changed"
                    if monitoring_changed
                    else "Import observer final hooks changed",
                    stage="publication",
                    partial=context,
                )
            context.published = True
        except BaseException as error:
            context.record, context.primary = None, error
            context.publication_recovery_errors = []
            for row in context.rows:
                try:
                    issued = _ISSUED.get(row.output)
                    if issued is not None and issued[0] is context and issued[1] is row:
                        del _ISSUED[row.output]
                except BaseException as secondary:
                    context.publication_recovery_errors.append(("registry", secondary))
            for name, prior in (("profile", before[0]), ("trace", before[1])):
                try:
                    if getattr(sys, "get" + name)() is not prior:
                        getattr(sys, "set" + name)(prior)
                except BaseException as secondary:
                    context.publication_recovery_errors.append((name, secondary))
            try:
                _FAILED.append(context)
            except BaseException as secondary:
                context.retention_error = (secondary, error)
            raise


def validate(function, original, *, owner, attribute):
    issued = _ISSUED.get(function) if type(function) is FunctionType else None
    if issued is None:
        raise WrapperAuthorityRejected(
            "Actual observed imported wrapper required", stage="unissued"
        )
    context, row = issued
    expected_owner = row.module if row.target[0][0] is None else row.stack[0]
    if (
        context.active
        or not context.published
        or context.record is None
        or context.primary is not None
        or context.thread != get_ident()
        or row.original is not original
        or owner is not expected_owner
        or attribute != row.target[0][1]
        or not context.hooks_restored
        or not context.monitor_restored
    ):
        raise WrapperAuthorityRejected(
            "Original closed imported wrapper association changed", stage="association"
        )
    for fn, expected in context.backend.states:
        _same(_function_state(fn), expected)
    return _binding(row, context.backend)
