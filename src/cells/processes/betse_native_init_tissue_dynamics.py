"""Held same-INIT tissue profile/event participation in dynamics completion.

The two native entry points belong to ONE live completion interval; no
intermediate closed owner, SEED substitution or supplied phase confers entry.
The actual completion producer/claim contract must be adopted explicitly.
"""

import ast
import builtins
import hashlib
import importlib
import sys
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import RLock, get_ident
from types import (
    CodeType,
    FrameType,
    FunctionType,
    MappingProxyType,
    MethodType,
    ModuleType,
    SimpleNamespace,
)
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_dynamics_prelude as prelude
from cells.processes import betse_native_init_retained_world as initial
from cells.processes import betse_native_init_tissue_dynamics_source as source
from cells.processes import betse_native_seed_init_profiles as profiles

LAW_ID = "betse_same_INIT_completion_tissue_profiles_events@1"
MODE = "actual_active_completion_claim_same_handler_two_ordered_entries@1"
COMPLETION_MODULE = "cells.processes.betse_native_init_dynamics_completion"
COMPLETION_SOURCE_SHA256 = COMPLETION_REVIEW_SHA256 = None
# This is NOT an accepted or injectable API. Key's real public contract must
# replace None in a reviewed source successor before any owner is inspected.
COMPLETION_CONTRACT = None
PROPOSED_CONTRACT = "actual_CompletionClaim_registry_and_single_observer@1"
METHODS = ("init_profiles", "init_events", "_finalize_events_global", "_finalize_events_tissue")
MAPS = ("cell_target_inds", "env_target_inds", "tissue_target_inds")
IONS = ("Na", "K", "Cl", "Ca", "M", "P")
MODULATORS = (
    "periodic",
    "f_sweep",
    "single_cell",
    "gradient_x",
    "gradient_y",
    "gradient_r",
    "gradient_bitmap",
)
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
HANDLER = "betse/science/tissue/tishandler.py"
MODULATE = "betse/science/math/modulate.py"
PINS = {
    **{
        name: value
        for name, value in profiles.NATIVE_PINS.items()
        if name != "betse/science/simrunner.py"
    },
    MODULATE: "c29f4ae27930f00780736e075183e61f44263dd0caa9d7c2f9a30971f616bff7",
}
MAX_WORK = 100000
_SESSIONS, _CLAIMED = WeakKeyDictionary(), WeakKeyDictionary()
_WITNESSES = WeakKeyDictionary()
_FAILED, _LOCK = [], RLock()


class TissueDynamicsRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None):
        super().__init__(reason)
        self.stage, self.partial = stage, partial


class CaptureStop(TissueDynamicsRejected):
    """Secondary observation refusal; never an invented primary source error."""


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    completion_claim: object
    init_trial: object
    calls: tuple
    wrapper_attempts: tuple
    dispatch_attempts: tuple
    source_work: tuple
    helper_calls: tuple
    numpy_epochs: tuple
    stdlib_epochs: tuple
    partial_returns: tuple
    source_completed: bool
    work_views_are_non_additive: bool


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class RngWitness:
    """An issued source-call witness, never a supplied RNG/state capability."""

    completion_claim: object
    source_frame: object
    operation: str
    cell_i_view: object

    def __reduce_ex__(self, protocol):
        raise TypeError("A live source-frame witness cannot be serialized")


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _trees():
    result = {}
    for name, expected in PINS.items():
        path = NATIVE / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Exact original tissue/helper source unavailable: " + name)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Exact original tissue/helper source changed: " + name)
        result[name] = ast.parse(raw, filename=str(path))
    return result


def _method(tree, cls, name):
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == cls)
    return next(
        node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _body(node):
    return ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False)


def _source_nodes():
    trees = _trees()
    native = {name: _method(trees[HANDLER], "TissueHandler", name) for name in METHODS}
    literal = ast.parse(Path(source.__file__).read_bytes())
    reused = ast.parse(Path(profiles.source.__file__).read_bytes())
    if source.InitTissueDynamics.init_profiles is not profiles.source.SeedProfiles.init_profiles:
        raise ValueError("Whole original shared profile method must remain the same literal")
    for name, original in native.items():
        selected = (
            _method(reused, "SeedProfiles", name)
            if name == "init_profiles"
            else _method(literal, "InitTissueDynamics", name)
        )
        if _body(original) != _body(selected):
            raise ValueError("Whole original method/branch/store order changed: " + name)
    return native


def _module_codes(path):
    """Compile the WHOLE pinned module, never evaluate its module/class body.

    Python 3.13 can specialize an isolated FunctionDef differently. Retain the
    actual original module/class compilation context for executable binding.
    """
    raw = (NATIVE / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINS[path]:
        raise ValueError("Original compiled helper source changed")
    return compile(raw, str(NATIVE / path), "exec", dont_inherit=True)


def _codes():
    _source_nodes()
    compiled = _module_codes(HANDLER)
    owner = next(
        value
        for value in compiled.co_consts
        if type(value) is CodeType and value.co_name == "TissueHandler"
    )
    return {
        name: next(
            value for value in owner.co_consts if type(value) is CodeType and value.co_name == name
        )
        for name in METHODS
    }


def _modulator_codes():
    compiled = _module_codes(MODULATE)
    return {
        name: next(
            value
            for value in compiled.co_consts
            if type(value) is CodeType and value.co_name == name
        )
        for name in MODULATORS
    }


def source_plan():
    nodes = _source_nodes()
    return dict(
        law=LAW_ID,
        mode=MODE,
        native_sources=PINS,
        methods={name: (node.lineno, node.end_lineno) for name, node in nodes.items()},
        completion_module=COMPLETION_MODULE,
        completion_source=COMPLETION_SOURCE_SHA256,
        completion_review=COMPLETION_REVIEW_SHA256,
        actual_contract=COMPLETION_CONTRACT,
        proposed_contract=PROPOSED_CONTRACT,
        proposed_participation=(
            "One actual active completion claim before either entry, "
            "exact same retained INIT phase/handler",
            "init_profiles then Key original intervening Simulator body then init_events",
            "Fallible session sealing inside that same active completion interval",
        ),
        own_effects=dict(handler_maps=MAPS, simulator=("Dm_cells",), cell_array=("cell_i",)),
        source_quirks=(
            "percent picker cells.cell_i[:] remains a VIEW and original NumPy shuffle mutates it",
            "gj_block uses actual stdlib shuffle on a COPY but selects targets from original mem_i",
            "gradient_y/gradient_r original x-offset lookups remain unchanged",
            "selected native empty/index/object-array/interpolation errors remain source failures",
            "event finalization returns closures; "
            "event firing and time evaluation remain later work",
        ),
        rng_contract=(
            "Original continuing NumPy global MT for percent/single_cell, no supplied/reset state",
            "Actual imported stdlib shuffle receiver/global instance for gj_block, "
            "lazy complete epochs",
            "Advancement allowed only with original reached source-frame/call evidence",
        ),
        helpers=profiles.HELPERS,
        modulators=MODULATORS,
        bitmap_source_requires_actual_owned_input_authority=True,
        image_picker_file_and_new_mask_ownership_remain_unavailable=True,
        required_provider_hooks=(
            "original INIT wrapper guard/dispatch through actual active completion",
            "factored original prelude authority after witnessed RNG/cell_i changes",
            "single shared observer admits tissue body before inherited callbacks",
        ),
        original_bodies_compiled_in_whole_module_context=True,
        no_seed_owner_or_saved_state_or_fake_phase_authority=True,
        native_reference_RNG_operator_or_scientific_release=False,
        all11_invalid_owners_and12_postcut_cases_held=True,
    )


def _ready():
    if (
        not _pin(COMPLETION_SOURCE_SHA256)
        or not _pin(COMPLETION_REVIEW_SHA256)
        or COMPLETION_CONTRACT != PROPOSED_CONTRACT
    ):
        raise TissueDynamicsRejected(
            "Actual active completion claim contract remains unavailable", stage="completion_held"
        )
    path = Path(__file__).parents[3] / ("src/" + COMPLETION_MODULE.replace(".", "/") + ".py")
    if (
        path.is_symlink()
        or not path.is_file()
        or hashlib.sha256(path.read_bytes()).hexdigest() != COMPLETION_SOURCE_SHA256
    ):
        raise TissueDynamicsRejected(
            "Exact reviewed completion producer required", stage="producer"
        )
    module = importlib.import_module(COMPLETION_MODULE)
    if sys.modules.get(COMPLETION_MODULE) is not module or Path(module.__file__).resolve() != path:
        raise ValueError("Actual original completion namespace required")
    return module


def _same_refs(actual, expected):
    if len(actual) != len(expected) or any(
        a is not b for a, b in zip(actual, expected, strict=True)
    ):
        raise ValueError("Original callable/registry/reference authority changed")


def _sampler(context):
    function, code, namespace, references = context.atom_binding
    if (
        initial.core.previous.previous._atoms is not function
        or function.__code__ is not code
        or function.__globals__ is not namespace
        or any(namespace.get(name) is not value for name, value in references)
    ):
        raise ValueError("Original independent callable-atom checker changed")
    return function


def _api_bindings(context):
    atoms = _sampler(context)
    module = context.api
    values = [module, vars(module), context.claim_registry, context.claim_type]
    for name in ("validate_active", "rng_call"):
        function = vars(module).get(name)
        if type(function) is not FunctionType or function.__globals__ is not vars(module):
            raise ValueError("Actual completion checker/RNG function required")
        values.extend(atoms(function))
    return tuple(values)


def _registry(context, *, closed=False):
    if (
        sys.modules.get(COMPLETION_MODULE) is not context.api
        or vars(context.api).get("_CLAIMS") is not context.claim_registry
        or vars(context.api).get("CompletionClaim") is not context.claim_type
        or context.claim_registry.get(context.claim) is not context.completion
        or type(context.claim) is not context.claim_type
        or _CLAIMED.get(context.claim) is not context
        or _SESSIONS.get(context.session) is not context
        or context.completion.request.prelude_owner is not context.original_owner
        or context.completion.init_parent is not context.initial
        or context.completion.phase is not context.phase
        or context.completion.p is not context.p
        or context.completion.cells is not context.cells
        or context.completion.sim is not context.sim
        or context.completion.handler is not context.handler
        or context.thread != get_ident()
    ):
        _reject(context, "Actual original completion/session/INIT issuance links changed")
    if closed:
        if (
            context.completion.active
            or context.completion.invalid
            or context.completion.trial is None
            or not context.completion.trial.source_completed
        ):
            _reject(context, "Only the actual successful closed completion can retain this session")
    elif (
        context.api.validate_active(context.claim, original_owner=context.original_owner)
        is not context.claim
    ):
        _reject(context, "Actual active original completion claim required")


def _bindings(context):
    atoms = _sampler(context)
    values = [
        _SESSIONS,
        _CLAIMED,
        _WITNESSES,
        context.initial,
        context.initial.trial,
        context.phase,
        context.p,
        context.cells,
        context.sim,
        context.handler,
        context.session,
        context.claim,
        context.original_owner,
        context.api,
        context.methods,
        context.native_globals,
        context.numpy,
        context.np_rng,
        *_profile_ancestry(context),
    ]
    for role in ("TissueHandler", *context.picker_methods):
        values.extend(initial._surface(context.initial.runtime_types[role]))
        values.extend(initial._surface(context.initial.factories[role]))
    for function in (*context.native_functions, *context.private_functions):
        values.extend(atoms(function))
        if type(function) is FunctionType:
            values.extend((function.__globals__, function.__builtins__))
            for name in function.__code__.co_names:
                if name in function.__globals__:
                    value = function.__globals__[name]
                    values.extend((name, value, *atoms(value)))
    for namespace, original, keys in context.namespace_bindings:
        values.extend((namespace, original))
        for name in keys:
            value = vars(namespace).get(name)
            actual = vars(original).get(name)
            values.extend((name, value, *atoms(value), actual, *atoms(actual)))
    if context.stdlib_binding is not None:
        values.extend(atoms(context.stdlib_shuffle))
        values.extend(atoms(context.stdlib_getstate))
    values.extend(_api_bindings(context))
    return tuple(values)


def _check(context, *, closed=False):
    _same_refs(_api_bindings(context), context.api_binding)
    _registry(context, closed=closed)
    if context.bindings is not None:
        _same_refs(_bindings(context), context.bindings)
    if context.stdlib_binding is not None:
        _check_stdlib(context)
    if context.initial.phase is not context.phase or context.phase.p is not context.p:
        _reject(context, "Actual retained INIT phase/parameter ancestry changed")


def _context(session, completion_claim=None):
    if type(session) is not TissueSession or session not in _SESSIONS:
        raise TissueDynamicsRejected("Actual issued tissue participation required", stage="session")
    context = _SESSIONS[session]
    if completion_claim is not None and completion_claim is not context.claim:
        _reject(context, "Different original completion claim")
    return context


def _record_failure(context, primary):
    context.invalid = True
    context.failure_primary = primary
    try:
        _FAILED.append(context)
    except BaseException as capture:
        context.retention_error = (capture, primary, context)
    try:
        primary.init_tissue_dynamics_partial = context
    except BaseException as capture:
        context.attachment_error = (capture, primary, context)


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = TissueDynamicsRejected(reason, stage=context.stage, partial=context)
    raise context.entry_error


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.capture_error is not None:
        if context.capture_stop is None:
            context.capture_stop = CaptureStop(
                "Incomplete tissue observation; no later source", stage="capture", partial=context
            )
        raise context.capture_stop from context.capture_error
    if context.invalid or not context.active or context.finished or context.thread != get_ident():
        _reject(context, "Actual exclusive tissue participation is unavailable")
    if context.observer_active:
        _reject(context, "An inherited observer cannot seize a tissue/helper entry")
    if _SESSIONS.get(context.session) is not context or _CLAIMED.get(context.claim) is not context:
        _reject(context, "Actual tissue claim/session issuance changed")
    _check(context)


def _capture(context, origin, error, raw):
    context.last_capture = (origin, error, raw)
    if context.capture_error is None:
        context.capture_error = error
    try:
        context.capture_errors += (context.last_capture,)
    except BaseException as secondary:
        context.retention_error = (secondary, error, raw)


def _profile_ancestry(context):
    """Fresh INIT constructor issuance, never the old SEED dyna registry."""
    origin, handler = context.initial, context.handler
    if (
        origin.phase is not context.phase
        or context.phase.dyna is not handler
        or context.phase.sim is not context.sim
        or context.sim.dyna is not handler
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.phase.kind is not origin.kind
        or origin.kind.name != "INIT"
        or context.p._run_sim is not False
        or initial._OBJECTS.get(handler) is not origin
        or type(handler) is not origin.runtime_types["TissueHandler"]
        or not any(
            role == "TissueHandler" and actual is handler
            for role, actual in origin.completed_objects
        )
    ):
        raise ValueError("Actual completed fresh INIT handler/phase associations required")
    table = vars(handler)["tissue_name_to_profile"]
    if type(table) not in (dict, OrderedDict):
        raise ValueError("Original ordered tissue-profile table required")
    actual = tuple(table.items())
    if len(actual) != len(context.profiles) or any(
        name != expected_name or profile is not expected
        for (name, profile), (expected_name, expected) in zip(actual, context.profiles, strict=True)
    ):
        raise ValueError("Original profile insertion order/object identities changed")
    atoms = [
        origin,
        initial._OBJECTS,
        table,
        origin.objects,
        origin.runtime_types,
        origin.factories,
    ]
    for name, profile in actual:
        picker = profile.picker
        roles = tuple(role for role, value in origin.objects if value is picker)
        if (
            initial._OBJECTS.get(profile) is not origin
            or type(profile) is not origin.runtime_types["TissueProfile"]
            or len(roles) != 1
            or roles[0] not in (*profiles.PICKERS, "TissuePickerImage")
            or initial._OBJECTS.get(picker) is not origin
            or type(picker) is not origin.runtime_types[roles[0]]
        ):
            raise ValueError("Actual fresh constructor-issued profile and picker required")
        atoms.extend((name, profile, type(profile), picker, type(picker), roles[0]))
    return tuple(atoms)


def _raw_return(context, origin, raw):
    # The actual result survives rejection at the following observer entry.
    context.last_raw_return = (origin, raw)
    try:
        context.returns.append(context.last_raw_return)
    except BaseException as capture:
        _capture(context, "raw_return_history", capture, context.last_raw_return)


def _wrapper_guard(context, original, frame):
    attempt = dict(original=original, frame=frame, admitted=False)
    context.last_wrapper_attempt = attempt
    try:
        if len(context.wrapper_attempts) >= MAX_WORK:
            _reject(context, "Bounded attempted wrapper work exhausted")
        context.wrapper_attempts.append(attempt)
    except BaseException as capture:
        if capture is context.entry_error:
            raise
        _capture(context, "wrapper_attempt", capture, attempt)
    _guard(context)
    if type(frame) is not FrameType or original is not context.initial:
        _reject(context, "Actual original INIT runtime wrapper required")
    fields = frame.f_locals
    role, method = fields.get("name"), fields.get("method")
    allowed = METHODS if role == "TissueHandler" else context.picker_methods.get(role, ())
    function = (
        vars(context.initial.runtime_types[role]).get(method)
        if role in context.initial.runtime_types
        else None
    )
    if (
        method not in allowed
        or type(function) is not FunctionType
        or frame.f_code is not function.__code__
        or frame.f_globals is not function.__globals__
        or fields.get("context") is not original
        or fields.get("delegate") is not getattr(original.factories[role], method)
        or initial._OBJECTS.get(fields.get("actual")) is not original
        or context.observer_active
    ):
        _reject(context, "Original issued method/closure/receiver association changed")
    for name, cell in zip(function.__code__.co_freevars, function.__closure__ or (), strict=True):
        if fields.get(name) is not cell.cell_contents:
            _reject(context, "Actual wrapper closure cells changed")
    if id(frame) in context.wrapper_claims:
        _reject(context, "Repeated/reentrant tissue wrapper entry")
    outer = frame.f_back
    if role == "TissueHandler":
        if method in ("init_profiles", "init_events"):
            if (
                context.stack
                or context.pending_top is not None
                or outer is not context.completion.body_frame
            ):
                _reject(context, "Tissue entry detached from actual completion source")
            expected = (
                ("init_profiles", "init_events")[len(context.top_entered)]
                if len(context.top_entered) < 2
                else None
            )
            if method != expected:
                _reject(context, "Original tissue entry order was repeated or changed")
            context.pending_top = frame
            context.top_entered.append(method)
        elif (
            not context.stack
            or context.stack[-1]["name"] != "init_events"
            or outer is not context.stack[-1]["body"]
        ):
            _reject(context, "Event finalizer must be called by actual init_events body")
        else:
            expected = (
                ("_finalize_events_global", "_finalize_events_tissue")[
                    len(context.finalizer_entered)
                ]
                if len(context.finalizer_entered) < 2
                else None
            )
            if method != expected:
                _reject(context, "Original event finalizer order was repeated or changed")
            context.finalizer_entered.append(method)
    elif not context.stack or not any(outer is body for body in context.source_frames):
        _reject(context, "Picker wrapper detached from actual original tissue source")
    context.wrapper_claims[id(frame)] = (frame, function, role, method, fields.get("actual"))
    attempt["admitted"] = True


def _dispatch(context, original, label, delegate, actual, args, kwargs, frame):
    context.last_dispatch_attempt = (original, label, delegate, actual, args, kwargs, frame)
    try:
        if len(context.dispatch_attempts) >= MAX_WORK:
            _reject(context, "Bounded attempted dispatch work exhausted")
        context.dispatch_attempts.append(context.last_dispatch_attempt)
    except BaseException as capture:
        if capture is context.entry_error:
            raise
        _capture(context, "dispatch_attempt", capture, context.last_dispatch_attempt)
    _guard(context)
    role, name = label.split(".", 1)
    wrapper = frame.f_back
    claim = context.wrapper_claims.get(id(wrapper))
    if (
        original is not context.initial
        or claim is None
        or claim[0] is not wrapper
        or claim[2] != role
        or claim[3] != name
        or claim[4] is not actual
        or frame.f_code is not initial._invoke.__code__
        or not _ancestor(frame, sys._getframe())
        or delegate is not getattr(original.factories[role], name)
        or id(wrapper) in context.dispatched_wrappers
    ):
        _reject(context, "Actual once-admitted same-instance method dispatch required")
    if role == "TissueHandler" and (
        actual is not context.handler or kwargs or len(args) != 1 or args[0] is not context.phase
    ):
        _reject(context, "Original same-phase TissueHandler argument required")
    if role != "TissueHandler":
        cells = args[0] if args else kwargs.get("cells")
        p = args[1] if len(args) > 1 else kwargs.get("p")
        if cells is not context.cells or (name != "get_image_mask" and p is not context.p):
            _reject(context, "Original actual picker cells/parameter association required")
    context.dispatched_wrappers.add(id(wrapper))
    call = dict(
        name=name, role=role, actual=actual, frame=sys._getframe(), body=None, returned=False
    )
    context.stack.append(call)
    context.last_attempt = call
    try:
        result = context.methods[(role, name)](actual, *args, **kwargs)
        _raw_return(context, label, result)
        call["returned"] = True
        _guard(context)
        if role == "TissueHandler" and name in ("init_profiles", "init_events"):
            if result is not None:
                _reject(context, "Original TissueHandler source returns None")
            context.top_calls.append((name, call))
            context.pending_top = None
        return result
    except BaseException as error:
        if (
            context.primary is None
            and context.entry_error is None
            and not isinstance(error, CaptureStop)
        ):
            context.primary = error
        raise
    finally:
        if context.stack and context.stack[-1] is call:
            context.stack.pop()
        else:
            context.invalid = True


class TissueSession:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Actual active completion must issue the participation session")

    def __reduce_ex__(self, protocol):
        raise TypeError("A tissue participation cannot be serialized or hydrated")


def _chain(function):
    return initial.caches.previous.callbacks.simulator._chain(function)


def _original(function, path, owner, name):
    chain = _chain(function)
    if not chain or type(chain[-1]) is not FunctionType:
        raise ValueError("Actual original loaded tissue/helper function required")
    actual = chain[-1]
    module = _module_codes(path)
    parent = (
        module
        if owner is None
        else next(
            value
            for value in module.co_consts
            if type(value) is CodeType and value.co_name == owner
        )
    )
    expected = next(
        value for value in parent.co_consts if type(value) is CodeType and value.co_name == name
    )
    loaded = sys.modules.get(path[:-3].replace("/", "."))
    if (
        actual.__code__.co_filename != str(NATIVE / path)
        or prelude._constant(actual.__code__) != prelude._constant(expected)
        or type(loaded) is not ModuleType
        or actual.__globals__ is not vars(loaded)
        or actual.__builtins__ is not vars(builtins)
    ):
        raise ValueError("Exact whole-module original executable helper required: " + name)
    return actual, chain


def _bind_methods(context):
    """Retain native bodies/closures; never execute or attach a new method."""
    origin = context.initial
    handler = origin.factories["TissueHandler"]
    context.methods, originals = {}, []
    for name in METHODS:
        native = getattr(handler, name)
        original, chain = _original(native, HANDLER, "TissueHandler", name)
        context.methods[("TissueHandler", name)] = original
        originals.extend(chain)
    globals_ = context.methods[("TissueHandler", "init_profiles")].__globals__
    if (
        globals_["np"] is not context.methods[("TissueHandler", "init_events")].__globals__["np"]
        or globals_["np"] is not context.numpy
    ):
        raise ValueError("Actual same native tissue/Simulator NumPy namespace required")
    context.native_globals = globals_
    context.picker_methods = {}
    for role in (*profiles.PICKERS, "TissuePickerImage"):
        native_class = origin.factories.get(role)
        if native_class is None:
            continue
        roster = []
        for name in ("pick_cells_and_mems", "pick_cells", "get_image_mask"):
            native = getattr(native_class, name, None)
            if type(native) is not FunctionType:
                continue
            body = _chain(native)[-1]
            owner = body.__qualname__.split(".")[0]
            filename = str(Path(body.__code__.co_filename).relative_to(NATIVE))
            original, chain = _original(native, filename, owner, name)
            context.methods[(role, name)] = original
            originals.extend(chain)
            roster.append(name)
        context.picker_methods[role] = tuple(roster)
    mod = globals_["mod"]
    if (
        type(mod) is not ModuleType
        or sys.modules.get("betse.science.math.modulate") is not mod
        or Path(mod.__file__) != NATIVE / MODULATE
    ):
        raise ValueError("Actual original native modulator namespace required")
    context.modulators = {}
    for name in MODULATORS:
        original, chain = _original(vars(mod)[name], MODULATE, None, name)
        context.modulators[name] = original
        originals.extend(chain)
    context.modulator_namespace = mod
    reached = initial.core.previous.previous._native_helper_functions(originals)
    context.native_functions = tuple(
        {id(value): value for value in (*originals, *reached)}.values()
    )
    _verify_functions(context.native_functions)
    context.original_methods = MappingProxyType(dict(context.methods))
    _private_namespaces(context)
    original_codes = {
        value.__code__
        for value in (*context.original_methods.values(), *context.modulators.values())
    }
    context.source_functions = {
        value.__code__: value
        for value in context.native_functions
        if value.__code__ not in original_codes
    }
    context.source_functions.update(
        (value.__code__, value)
        for value in (*context.methods.values(), *context.private_modulators.values())
    )
    context.source_codes = frozenset(
        code
        for value in context.source_functions.values()
        for code in initial._code_tree(value.__code__)
    )
    context.methods = MappingProxyType(context.methods)
    context.profile_binding = _profile_ancestry(context)


def _verify_functions(functions):
    """Original whole-module executable/helper closure, never a producer oracle."""
    pins = dict(profiles.tissue_source.SOURCE_PINS)
    pins.update(profiles.image_source.NATIVE_PINS)
    pins.update(PINS)
    for function in functions:
        if type(function) is not FunctionType:
            continue
        filename = function.__code__.co_filename
        if not filename.startswith(str(NATIVE) + "/"):
            continue
        relative = str(Path(filename).relative_to(NATIVE))
        expected = pins.get(relative)
        path = Path(filename)
        if (
            expected is None
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Reached original helper source remains unavailable: " + relative)
        # The shared utility returns whole-module/class-context CodeTypes only.
        candidates = profiles._native_module_codes(relative, expected)
        if not any(
            name == function.__code__.co_qualname
            and line == function.__code__.co_firstlineno
            and prelude._constant(code) == prelude._constant(function.__code__)
            for name, line, code in candidates
        ):
            raise ValueError("Reached helper differs from whole original module executable")
        module = sys.modules.get(relative[:-3].replace("/", "."))
        if type(module) is not ModuleType or function.__globals__ is not vars(module):
            raise ValueError("Actual original loaded helper namespace required")


def _helper_call(context, name, delegate, args, kwargs, source_frame):
    _guard(context)
    if not any(source_frame is frame for frame in context.source_frames):
        _reject(context, "Actual reached original tissue/helper frame required")
    row = dict(
        name=name,
        delegate=delegate,
        source_frame=source_frame,
        args=args,
        kwargs=kwargs,
        returned=False,
        raw_return=None,
        error=None,
    )
    context.last_helper = row
    if len(context.work) + len(context.helper_calls) >= MAX_WORK:
        _reject(context, "Bounded tissue helper work exhausted")
    context.helper_calls.append(row)
    try:
        returned = delegate(*args, **kwargs)
        row["raw_return"], row["returned"] = returned, True
        _raw_return(context, name, returned)
        _guard(context)
        return returned
    except BaseException as error:
        row["error"] = error
        if (
            context.primary is None
            and context.entry_error is None
            and not isinstance(error, CaptureStop)
        ):
            context.primary = error
        raise


def _private_namespaces(context):
    """Original CodeTypes on declared private facades; no global/class patch."""
    context.private_functions, context.namespace_bindings = [], []
    numpy = context.numpy
    if type(numpy) is not ModuleType or sys.modules.get("numpy") is not numpy:
        raise ValueError("Actual original continuing NumPy module required")
    random = numpy.random
    context.np_rng = random.mtrand._rand
    if context.np_rng is not context.completion.np_rng:
        raise ValueError("Actual continuing INIT NumPy RNG required")
    context.rng_delegates = {
        ("numpy", "shuffle"): random.shuffle,
        ("numpy", "choice"): random.choice,
        ("stdlib", "shuffle"): context.native_globals["shuffle"],
    }
    bridges = {}
    for library, operation in context.rng_delegates:

        def bridge(*args, _library=library, _operation=operation, **kwargs):
            return _rng_bridge(context, _library, _operation, args, kwargs, sys._getframe(1))

        bridges[(library, operation)] = bridge
        context.private_functions.append(bridge)
    names = (
        "copy",
        "zeros",
        "sqrt",
        "max",
        "linspace",
        "asarray",
        "flipud",
        "meshgrid",
        "column_stack",
        "sin",
    )
    helpers = {}
    for name in names:
        delegate = getattr(numpy, name)

        def helper(*args, _name=name, _delegate=delegate, **kwargs):
            return _helper_call(context, "np." + _name, _delegate, args, kwargs, sys._getframe(1))

        helpers[name] = helper
        context.private_functions.append(helper)
    random_view = SimpleNamespace(
        shuffle=bridges[("numpy", "shuffle")], choice=bridges[("numpy", "choice")]
    )
    numpy_view = SimpleNamespace(**helpers, random=random_view, pi=numpy.pi, float64=numpy.float64)
    context.namespace_bindings.extend(
        (
            (random_view, random, tuple(vars(random_view))),
            (numpy_view, numpy, tuple(vars(numpy_view))),
        )
    )
    private_globals = {}

    def clone(original):
        key = id(original.__globals__)
        if key not in private_globals:
            private_globals[key] = dict(original.__globals__, np=numpy_view)
        namespace = private_globals[key]
        function = FunctionType(
            original.__code__,
            namespace,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        function.__kwdefaults__ = original.__kwdefaults__
        context.private_functions.append(function)
        return function

    context.methods = {key: clone(value) for key, value in context.original_methods.items()}
    context.private_modulators = {name: clone(value) for name, value in context.modulators.items()}
    mod_view = SimpleNamespace(**context.private_modulators)
    context.namespace_bindings.append(
        (mod_view, context.modulator_namespace, tuple(vars(mod_view)))
    )
    namespace = context.methods[("TissueHandler", "init_profiles")].__globals__
    namespace["mod"] = mod_view
    namespace["shuffle"] = bridges[("stdlib", "shuffle")]
    context.private_globals = tuple(private_globals.values())


def _rng_bridge(context, library, operation, args, kwargs, source_frame):
    _guard(context)
    if context.pending_rng is not None:
        _reject(context, "Repeated/reentrant tissue RNG bridge")
    delegate = context.rng_delegates[(library, operation)]
    attempt = dict(
        library=library,
        operation=operation,
        delegate=delegate,
        args=args,
        kwargs=kwargs,
        source_frame=source_frame,
        claimed=False,
        returned=False,
    )
    context.last_rng_attempt = context.pending_rng = attempt
    try:
        returned = context.api.rng_call(
            context.claim,
            participant=context.session,
            library=library,
            operation=operation,
            delegate=delegate,
            args=args,
            kwargs=kwargs,
            source_frame=source_frame,
        )
        attempt["raw_return"], attempt["returned"] = returned, True
        _raw_return(context, library + "." + operation, returned)
        # Retain the ACTUAL completion row; this is not additive RNG/case credit.
        row = context.completion.last_rng
        if row.participant is not context.session or row.source_frame is not source_frame:
            _reject(context, "Original completion RNG receipt association changed")
        if library == "numpy":
            context.numpy_epochs.append(row)
        else:
            context.stdlib_epochs.append(row)
        _guard(context)
        return returned
    except BaseException as error:
        if (
            context.primary is None
            and context.entry_error is None
            and not isinstance(error, CaptureStop)
        ):
            context.primary = error
        raise
    finally:
        context.pending_rng = None


def _stdlib_shuffle(context):
    """Adopt the already-loaded original global stream; never construct/reseed."""
    module = sys.modules.get("random")
    function = context.native_globals["shuffle"]
    if (
        type(module) is not ModuleType
        or type(function) is not MethodType
        or function.__self__ is not vars(module).get("_inst")
        or function.__func__ is not vars(vars(module)["Random"])["shuffle"]
        or vars(module).get("shuffle") is not function
        or type(function.__self__) is not vars(module)["Random"]
    ):
        raise ValueError("Actual already-imported stdlib global shuffle authority required")
    context.stdlib_rng, context.stdlib_shuffle = function.__self__, function
    context.stdlib_module = module
    context.stdlib_shuffle_code = function.__func__.__code__
    context.stdlib_getstate = vars(module)["Random"].getstate
    context.stdlib_binding = (
        module,
        vars(module),
        function.__self__,
        function.__func__,
        function.__func__.__code__,
        context.stdlib_getstate,
        context.stdlib_getstate.__code__,
    )


def _check_stdlib(context):
    module, namespace, rng, function, code, reader, reader_code = context.stdlib_binding
    current = namespace.get("shuffle")
    if (
        sys.modules.get("random") is not module
        or vars(module) is not namespace
        or namespace.get("_inst") is not rng
        or type(current) is not MethodType
        or current.__self__ is not rng
        or current.__func__ is not function
        or function.__code__ is not code
        or vars(namespace["Random"])["getstate"] is not reader
        or reader.__code__ is not reader_code
    ):
        _reject(context, "Original stdlib shuffle/stream/reader association changed")


def _ancestor(expected, frame):
    while frame is not None:
        if frame is expected:
            return True
        frame = frame.f_back
    return False


def _observe(context, frame, event, arg):
    """Source-body observation entry for the single completion-owned observer."""
    selected = frame.f_code in context.source_codes
    if event == "call":
        native = frame.f_code.co_filename.startswith(str(NATIVE) + "/")
        if not selected and not native:
            return
        row = dict(
            frame=frame,
            code=frame.f_code,
            globals=frame.f_globals,
            returned=False,
            body_started=False,
        )
        context.last_attempt = row
        if len(context.work) >= MAX_WORK:
            _reject(context, "Bounded original tissue work ledger exhausted")
        try:
            context.work.append(row)
        except BaseException as capture:
            _capture(context, "attempt_record", capture, row)
        _guard(context)
        if not selected:
            _reject(context, "Unbound native tissue helper attempted entry")
        if id(frame) in context.frames or not context.stack:
            _reject(context, "Raw/reentrant tissue source entry")
        function = context.source_functions.get(frame.f_code)
        if function is not None and frame.f_globals is not function.__globals__:
            _reject(context, "Original helper code cannot use a substituted namespace")
        call = context.stack[-1]
        method = context.methods[(call["role"], call["name"])]
        if frame.f_code is method.__code__:
            if (
                frame.f_back is not call["frame"]
                or call["body"] is not None
                or frame.f_locals.get("self") is not call["actual"]
            ):
                _reject(context, "Original tissue body detached from guarded dispatch")
            call["body"] = frame
        else:
            ancestor = frame.f_back
            while ancestor is not None and ancestor is not call["body"]:
                ancestor = ancestor.f_back
            if ancestor is not call["body"]:
                _reject(context, "Helper detached from actual original tissue body")
        if frame.f_code.co_name == "gradient_bitmap":
            _reject(context, "Selected bitmap modulator needs its genuine owned file prerequisite")
        if call["role"] == "TissuePickerImage":
            _reject(context, "Selected image picker needs its genuine owned file/mask prerequisite")
        context.frames[id(frame)] = row
        context.source_frames.add(frame)
        row["body_started"] = True
        return
    row = context.frames.get(id(frame))
    if row is None:
        return
    if (
        frame is not row["frame"]
        or frame.f_code is not row["code"]
        or frame.f_globals is not row["globals"]
    ):
        _reject(context, "Original observed tissue frame/code identity changed")
    if event == "exception":
        context.last_source_error = (frame, arg[1])
        try:
            context.pending[id(frame)] = arg[1]
        except BaseException as capture:
            if context.primary is None:
                context.primary = arg[1]
            _capture(context, "source_exception_record", capture, (frame, arg))
    if event == "line" and frame.f_code.co_name == "pick_cells" and "cell_i_copy" in frame.f_locals:
        picker, view = frame.f_locals.get("self"), frame.f_locals["cell_i_copy"]
        try:
            if not any(old[0] is frame for old in context.percent_views):
                context.percent_views.append((frame, picker, view, context.cells.cell_i))
        except BaseException as capture:
            _capture(context, "percent_view_record", capture, (frame, picker, view))
        _guard(context)
    if event == "return":
        context.last_frame_return = (frame, arg)
        if not initial._normal_return(frame) and context.primary is None:
            context.primary = context.pending.get(id(frame))
        try:
            context.raw_frames.append(context.last_frame_return)
            context.locals[id(frame)] = dict(frame.f_locals)
        except BaseException as capture:
            _capture(context, "frame_return", capture, context.last_frame_return)
        row["returned"] = True


def _seal(context):
    _guard(context)
    _profile_ancestry(context)
    if (
        tuple(name for name, _ in context.top_calls) != ("init_profiles", "init_events")
        or context.stack
        or any(not row["returned"] for row in context.work)
        or any(not row["returned"] for row in context.helper_calls)
        or context.pending_rng is not None
        or context.primary is not None
        or context.capture_error is not None
    ):
        _reject(context, "Both original tissue entries and all helpers must complete in order")
    evidence = SourceEvidence(
        context.claim,
        context.initial.trial,
        tuple(context.top_calls),
        tuple(context.wrapper_attempts),
        tuple(context.dispatch_attempts),
        tuple(context.work),
        tuple(context.helper_calls),
        tuple(context.numpy_epochs),
        tuple(context.stdlib_epochs),
        tuple(context.returns),
        True,
        True,
    )
    context.evidence = evidence
    return evidence


def bind_completion(completion_claim, *, original_owner):
    """Join the genuine active Key claim once; no phase/metadata is supplied.

    Producer and contract adoption remain closed. The real provider registry,
    rather than an inspection object, supplies every continuing live reference.
    """
    module = _ready()
    sampler = initial.core.previous.previous._atoms
    namespace = sampler.__globals__
    atom_binding = (
        sampler,
        sampler.__code__,
        namespace,
        tuple((name, namespace[name]) for name in sampler.__code__.co_names if name in namespace),
    )
    claim_type, registry = vars(module).get("CompletionClaim"), vars(module).get("_CLAIMS")
    if type(completion_claim) is not claim_type or type(registry) is not WeakKeyDictionary:
        raise TissueDynamicsRejected(
            "Actual provider-issued CompletionClaim required", stage="claim"
        )
    if completion_claim not in registry:
        raise TissueDynamicsRejected("Actual provider claim registry required", stage="claim")
    completion = registry[completion_claim]
    with _LOCK:
        if completion_claim in _CLAIMED:
            prior = _CLAIMED[completion_claim]
            _reject(prior, "Completion participation is irrevocably single-use")
        # Reserve BEFORE callbacks/fallible method/source authentication. A
        # refused preparation keeps this actual claim consumed and its partials.
        context = SimpleNamespace(
            api=module,
            claim_type=claim_type,
            claim_registry=registry,
            completion=completion,
            claim=completion_claim,
            original_owner=original_owner,
            session=object.__new__(TissueSession),
            atom_binding=atom_binding,
            initial=completion.init_parent,
            phase=completion.phase,
            p=completion.p,
            cells=completion.cells,
            sim=completion.sim,
            handler=completion.handler,
            thread=get_ident(),
            active=True,
            finished=False,
            invalid=False,
            observer_active=False,
            stage="tissue_binding",
            entry_error=None,
            capture_error=None,
            capture_stop=None,
            capture_errors=(),
            primary=None,
            failure_primary=None,
            retention_error=None,
            attachment_error=None,
            bindings=None,
            api_binding=None,
            stdlib_binding=None,
            evidence=None,
            stack=[],
            top_entered=[],
            top_calls=[],
            finalizer_entered=[],
            pending_top=None,
            wrapper_claims={},
            wrapper_attempts=[],
            dispatch_attempts=[],
            dispatched_wrappers=set(),
            frames={},
            source_frames=set(),
            pending={},
            work=[],
            helper_calls=[],
            returns=[],
            raw_frames=[],
            locals={},
            numpy_epochs=[],
            stdlib_epochs=[],
            percent_views=[],
            pending_rng=None,
            witnesses=[],
            added_objects=[],
            last_raw_return=None,
            last_capture=None,
        )
        _CLAIMED[completion_claim] = context
        _SESSIONS[context.session] = context
        try:
            context.api_binding = _api_bindings(context)
            _registry(context)
            context.numpy = completion.numpy
            table = vars(context.handler)["tissue_name_to_profile"]
            context.profiles = tuple(table.items())
            _bind_methods(context)
            _stdlib_shuffle(context)
            context.bindings = _bindings(context)
            _guard(context)
            context.stage = "tissue_entries"
            return context.session
        except BaseException as primary:
            context.active = False
            _record_failure(context, primary)
            raise


def validate_active(session, *, completion_claim):
    context = _context(session, completion_claim)
    if context.entry_error is not None:
        raise context.entry_error
    if context.invalid or context.capture_error is not None:
        _reject(context, "Failed tissue participation cannot validate an active completion")
    # A sealed participant is read-only while Key performs its own fallible
    # sealing INSIDE the still-active completion claim. No entry is re-armed.
    if not context.active and not context.finished:
        _reject(context, "Actual tissue participation is unavailable")
    _check(context)
    return session


def validate_closed(session, *, completion_claim):
    context = _context(session, completion_claim)
    if context.active or not context.finished or context.invalid or context.evidence is None:
        _reject(context, "No successfully sealed closed tissue participation")
    _check(context, closed=True)
    return context.evidence


def source_members(session):
    """Exact source functions for the ONE provider-owned admission observer."""
    context = _context(session)
    _registry(context)
    return tuple(context.source_functions.values())


def state_roots(session):
    """Retain genuine added holders, including after a refused partial trial.

    This is forensic identity traversal, not permission to enter native work.
    Arrays/maps remain in the actual handler/caller fields, not invented owners.
    """
    context = _context(session)
    if _CLAIMED.get(context.claim) is not context:
        raise ValueError("Original forensic tissue claim/session link changed")
    return tuple(context.added_objects)


def wrapper_guard(session, *, completion_claim, original, frame):
    return _wrapper_guard(_context(session, completion_claim), original, frame)


def dispatch(session, *, completion_claim, original, label, delegate, actual, args, kwargs, frame):
    return _dispatch(
        _context(session, completion_claim), original, label, delegate, actual, args, kwargs, frame
    )


def observe(session, *, completion_claim, frame, event, arg):
    """Admission before inherited callbacks, using the existing shared hooks."""
    context = _context(session, completion_claim)
    # The provider authenticates and chains both inherited hooks. This module
    # never installs/removes a second profiler/trace or calls an observer itself.
    return _observe(context, frame, event, arg)


def finish(session, *, completion_claim):
    context = _context(session, completion_claim)
    try:
        evidence = _seal(context)
        context.active, context.finished = False, True
        return evidence
    except BaseException as primary:
        context.active = False
        _record_failure(context, primary)
        raise


def validate_rng_call(
    session, *, completion_claim, library, operation, delegate, args, kwargs, source_frame
):
    context = _context(session, completion_claim)
    _guard(context)
    attempt = context.pending_rng
    if (
        attempt is None
        or attempt["claimed"]
        or attempt["library"] != library
        or attempt["operation"] != operation
        or attempt["delegate"] is not delegate
        or attempt["args"] is not args
        or attempt["kwargs"] is not kwargs
        or attempt["source_frame"] is not source_frame
        or not any(source_frame is frame for frame in context.source_frames)
        or context.frames[id(source_frame)]["returned"]
        or not context.stack
    ):
        _reject(context, "Actual pending original tissue RNG source call required")
    current = context.source_functions.get(source_frame.f_code)
    if current is None or source_frame.f_globals is not current.__globals__:
        _reject(context, "Original RNG source CodeType/private namespace changed")
    view = None
    if library == "numpy" and operation == "shuffle":
        if current is not context.methods.get(("TissuePickerPercent", "pick_cells")):
            _reject(context, "Only original percent-picker slice may call NumPy shuffle")
        view = source_frame.f_locals.get("cell_i_copy")
        if len(args) != 1 or args[0] is not view or kwargs:
            _reject(context, "Actual original percent-picker view/arguments required")
    elif library == "numpy" and operation == "choice":
        if (
            current is not context.private_modulators["single_cell"]
            or len(args) != 1
            or args[0] is not context.cells.bflags_cells
            or kwargs
        ):
            _reject(context, "Only original single_cell boundary choice is owned")
    elif library == "stdlib" and operation == "shuffle":
        if (
            current is not context.methods[("TissueHandler", "_finalize_events_global")]
            or len(args) != 1
            or args[0] is not source_frame.f_locals.get("mem_i_copy")
            or args[0] is context.cells.mem_i
            or kwargs
        ):
            _reject(context, "Only original copied global-event membrane array may shuffle")
    else:
        _reject(context, "Unowned tissue RNG operation")
    attempt["claimed"] = True
    witness = RngWitness(context.claim, source_frame, operation, view)
    _WITNESSES[witness] = (context, attempt)
    context.witnesses.append(witness)
    return witness
