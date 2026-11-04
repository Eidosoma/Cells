"""Held fresh original general-network setup on one actual INIT completion.

Native classes, source bodies and configuration are retained, never replaced
by the older projected component owners. All execution is conditional on the
explicit completion route and exact reviewed producer bindings.
"""

import ast
import builtins
import hashlib
import sys
from abc import ABCMeta
from collections import OrderedDict
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path
from threading import get_ident
from types import CodeType, FunctionType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_molecule_channels as channels
from cells.processes import betse_native_init_molecule_channels_source as channel_source
from cells.processes import betse_native_init_molecule_network_source as source
from cells.processes import betse_native_init_molecule_wrapper_authority as wrapper_authority

LAW_ID = "betse_actual_INIT_fresh_original_general_network@1"
COMPLETION_MODULE = "cells.processes.betse_native_init_dynamics_completion"
COMPLETION_SOURCE_SHA256 = None
COMPLETION_REVIEW_SHA256 = None
CONTRACT = None
PROPOSED_CONTRACT = "actual_active_CompletionClaim_native_molecules_source_frame@1"
ANCESTOR_CLAIM = "_claim_completion_molecule_ancestor"
ANCESTOR_CHECK = "_check_completion_molecule_ancestor"
MAX_WORK = 100000
# Literal native init_dynamics assignment plus bal_charge stores and dynamic
# setters from read_substances. Only the explicitly enabled source route may
# factor these; the retained material ancestor independently owns their buffers.
SIM_STORES = ("molecules", "cc_cells", "cc_env", "c_env_bound", "extra_rho_cells", "extra_rho_env")
_SESSIONS, _CLAIMED = WeakKeyDictionary(), WeakKeyDictionary()
_FAILED = []
_RUNTIME, _STORAGE_RUNTIME, _STEP_RUNTIME = (WeakKeyDictionary() for _ in range(3))


class MoleculeNetworkRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None):
        super().__init__(reason)
        self.stage, self.partial = stage, partial


class CaptureStop(MoleculeNetworkRejected):
    """Observation refusal; never substitutes for an active source error."""


class MoleculeSession:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only the actual active completion may bind native molecules")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live source/constructor authority cannot be decoded")


class MoleculeRuntimeClaim:
    """An actual storage/first-step child of the original molecular session."""

    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only the actual Completion descendant may bind runtime work")

    def __reduce_ex__(self, protocol):
        raise TypeError("A live runtime child cannot be decoded or replayed")


@dataclass(frozen=True, slots=True)
class RuntimeEvidence:
    kind: str
    session: object
    child: object
    source_completed: bool
    work: tuple
    c_calls: tuple
    exceptions: tuple
    raw_returns: tuple
    identity: str


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    source_completed: bool
    original_claim: object
    original_molecules: object
    original_core: object
    constructor_work: tuple
    source_work: tuple
    raw_returns: tuple
    dynamic_callbacks: tuple
    identity: str


def source_plan():
    return dict(
        law=LAW_ID,
        original=source.plan(),
        completion_source=COMPLETION_SOURCE_SHA256,
        completion_review=COMPLETION_REVIEW_SHA256,
        contract=CONTRACT,
        sim_effects=SIM_STORES,
        original_classes_instantiated=True,
        supplied_phase_or_network_owner=False,
        explicit_configuration_association="p.network_config is p._conf.get('general network')",
        unavailable=(
            "existing molecule reinitialize",
            "optimizer",
            "configured transporter expressions/flux",
            "channel families beyond original Nav1p3/Kv1p5/KLeak",
            "unowned molecule asymmetry/growth callback factories",
            "unissued outer factory/type-check wrapper execution",
        ),
        native_or_original_constructor_or_RNG_or_reference_release=False,
        default_channels=channels.source_plan(),
        actual_imported_wrapper_source=wrapper_authority.source_plan(),
        required_parent_source_successor=(
            "explicit native_molecules Request field and separate source/law gate",
            "Completion._molecule_api authenticates this exact source/review",
            "Completion observer/values/graph/dispatch transports the actual session",
            "retained INIT one-shot material ancestor claim/check before constructor entry",
        ),
        ordinary_Completion_path_is_not_enabled_network_authority=True,
        source_transport_implemented_but_unadopted=True,
        native_runtime=dict(
            bind_storage="bind_storage(session, *, completion, storage)",
            bind_first_step=("bind_first_step(session, *, completion, storage, electrical, step)"),
            claim="MoleculeRuntimeClaim",
            source_roster="runtime_members/runtime_codes",
            fields="runtime_permissions: original actual holders and native source fields",
            observer="observe_runtime(claim, *, child, frame, event, arg)",
            close="finish_runtime/validate_runtime(claim, *, child)",
            init_session_recreated_or_native_run_released=False,
            pumping_gating_boundary_clamp_mitochondrial_owners_unavailable=True,
            actual_imported_outer_wrapper_authority_still_required=True,
        ),
    )


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _ready():
    if (
        not _pin(COMPLETION_SOURCE_SHA256)
        or not _pin(COMPLETION_REVIEW_SHA256)
        or CONTRACT != PROPOSED_CONTRACT
    ):
        raise MoleculeNetworkRejected(
            "Reviewed actual molecular completion route remains held", stage="held"
        )
    api = sys.modules.get(COMPLETION_MODULE)
    if type(api) is not ModuleType:
        raise MoleculeNetworkRejected(
            "Actual original completion module must already be loaded", stage="module"
        )
    path = Path(__file__).parents[3] / ("src/" + COMPLETION_MODULE.replace(".", "/") + ".py")
    if (
        path.is_symlink()
        or Path(api.__file__).resolve() != path
        or hashlib.sha256(path.read_bytes()).hexdigest() != COMPLETION_SOURCE_SHA256
    ):
        raise MoleculeNetworkRejected(
            "Exact original molecular completion producer required", stage="producer"
        )
    adapter = vars(api).get("_molecule_api")
    fields = getattr(vars(api).get("Request"), "__dataclass_fields__", {})
    if (
        "native_molecules" not in fields
        or type(adapter) is not FunctionType
        or adapter.__globals__ is not vars(api)
    ):
        raise MoleculeNetworkRejected(
            "Explicit typed Completion source/observer successor is required",
            stage="completion_prerequisite",
        )
    if adapter() is not sys.modules[__name__]:
        raise MoleculeNetworkRejected("Different actual molecular source adapter", stage="producer")
    original = api.previous.previous
    for name in (ANCESTOR_CLAIM, ANCESTOR_CHECK):
        fn = vars(original).get(name)
        if type(fn) is not FunctionType or fn.__globals__ is not vars(original):
            raise MoleculeNetworkRejected(
                "Actual retained material/alias ancestor prerequisite missing: " + name,
                stage="material_ancestor_prerequisite",
            )
    return api


def _configuration(context):
    """Read actual retained associations; never fill or normalize native data."""
    p = context.p
    if context.phase.kind.name != "INIT" or p._run_sim is not False:
        raise MoleculeNetworkRejected("Same actual INIT phase required", stage="phase")
    if p.molecules_enabled is not True:
        raise MoleculeNetworkRejected(
            "Explicit enabled general-network configuration required", stage="configuration"
        )
    config = p.network_config
    if config is not p._conf.get("general network"):
        raise MoleculeNetworkRejected(
            "Original configuration submapping association changed", stage="configuration"
        )
    # Missing keys/types deliberately keep their original raw read failures.
    if config["implement network"] is not p.molecules_enabled:
        raise MoleculeNetworkRejected(
            "Original enabled-network flag association changed", stage="configuration"
        )
    if getattr(context.request, "native_molecules", False) is not True:
        raise MoleculeNetworkRejected(
            "Explicit actual molecular completion request is unavailable", stage="route"
        )
    if vars(context.sim).get("molecules") is not None:
        raise MoleculeNetworkRejected(
            "Fresh native constructor required; existing owner is not promoted",
            stage="existing_owner",
        )
    if config.get("transporters") not in (None, []):
        raise MoleculeNetworkRejected(
            "Configured transporter expressions/flux ownership remain unavailable",
            stage="transporter_owner",
        )
    try:
        channels.declarations(SimpleNamespace(config=config))
    except ValueError as error:
        raise MoleculeNetworkRejected(str(error), stage="channel_owner") from error
    if config.get("modulators") not in (None, []):
        raise MoleculeNetworkRejected(
            "Independent modulator owner is outside this setup domain", stage="modulator_owner"
        )
    optimization = config.get("optimization")
    if optimization is not None and optimization["optimize network"]:
        raise MoleculeNetworkRejected(
            "Original optimizer is a separate unreleased source domain", stage="optimizer"
        )
    for row in config["biomolecules"] or ():
        if row.get("initial asymmetry") not in (None, "None"):
            raise MoleculeNetworkRejected(
                "Original asymmetry factory authority is not supplied", stage="callback_owner"
            )
        growth = row.get("growth and decay")
        if growth not in (None, "None") and growth.get("modulator function") not in (None, "None"):
            raise MoleculeNetworkRejected(
                "Original growth callback factory authority is not supplied", stage="callback_owner"
            )
    return config


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = MoleculeNetworkRejected(reason, stage=context.stage, partial=context)
    raise context.entry_error


def _context(session, claim=None):
    if type(session) is not MoleculeSession or session not in _SESSIONS:
        raise MoleculeNetworkRejected(
            "Actual issued molecular source session required", stage="session"
        )
    context = _SESSIONS[session]
    if claim is not None and claim is not context.claim:
        _reject(context, "Different original CompletionClaim")
    return context


def _registry(context, *, closed=False):
    c = context.completion
    if (
        sys.modules.get(COMPLETION_MODULE) is not context.api
        or context.api._CLAIMS.get(context.claim) is not c
        or _SESSIONS.get(context.session) is not context
        or _CLAIMED.get(context.claim) is not context
        or c.request.prelude_owner is not context.original_owner
        or c.phase is not context.phase
        or c.p is not context.p
        or c.cells is not context.cells
        or c.sim is not context.sim
        or c.handler is not context.handler
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.phase.sim is not context.sim
        or context.phase.dyna is not context.handler
        or context.thread != get_ident()
        or context.invalid
        or context.p.network_config is not context.config
        or context.config is not context.p._conf.get("general network")
        or context.completion.molecule_session is not context.session
        or context.completion.molecule is not sys.modules.get(__name__)
        or not context.ancestor_claimed
        or vars(context.api.previous.previous).get(ANCESTOR_CLAIM) is not context.ancestor_claim
        or vars(context.api.previous.previous).get(ANCESTOR_CHECK) is not context.ancestor_check
    ):
        _reject(context, "Actual original molecular/phase/configuration/claim association changed")
    if closed:
        if c.active or c.invalid or c.trial is None or c.trial.source_completed is not True:
            _reject(context, "Actual successful closed completion required")
    elif (
        context.api.validate_active(context.claim, original_owner=context.original_owner)
        is not context.claim
    ):
        _reject(context, "Actual original active completion required")
    if context.ancestor_check(c.init_parent, c, context.session) is not c.init_parent:
        _reject(context, "Different original material/alias ancestor")


def _bindings(context):
    _class_associations(context)
    values = [context.api, context.api._CLAIMS, context.config, context.classes, context.functions]
    for module, path, pin, functions in getattr(context, "auxiliary_sources", ()):
        if (
            sys.modules.get(module.__name__) is not module
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != pin
        ):
            raise ValueError("Original channel/wrapper auxiliary source changed")
        values.extend((module, path, functions))
        for name, function, chain in functions:
            if vars(module).get(name) is not function:
                raise ValueError("Original auxiliary function export changed")
            for fn in chain:
                values.extend(_function_bindings(fn))
    atoms = context.initial._atoms
    for fn in (context.ancestor_claim, context.ancestor_check):
        values.extend(atoms(fn))
        values.extend(_function_bindings(fn))
    for role, cls in context.classes.items():
        values.extend((role, cls, *context.initial.factories._surface(cls)))
    for fn in context.source_functions:
        values.extend(atoms(fn))
        values.extend(_function_bindings(fn))
    for module, name, original in context.exports:
        if sys.modules.get(module.__name__) is not module or vars(module).get(name) is not original:
            raise ValueError("Original source module/class/method export changed: " + name)
        values.extend((module, name, original))
    values.extend(context.initial.core._resolved_bindings(context.source_functions))
    for path, pin in context.files:
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError("Original molecule-network source/dependency bytes changed")
    return tuple(values)


def _class_associations(context):
    """Bind reached factory lookups to the actual exported native classes."""
    groups = {
        "MasterOfMolecules": ("MasterOfNetworks",),
        "MasterOfNetworks": (
            "Molecule",
            "Reaction",
            "Transporter",
            "DynamicValue",
            "DynamicValueDict",
        ),
        "DynamicValueDict": ("DynamicValue",),
    }
    if "Channel" in context.classes:
        groups["MasterOfNetworks"] += ("Channel",)
    for (role, _), fn in context.functions.items():
        for name in groups.get(role, ()):
            if fn.__globals__.get(name) is not context.classes[name]:
                raise ValueError("Original native factory lookup changed: " + name)
        if "np" in fn.__globals__ and fn.__globals__["np"] is not context.completion.numpy:
            raise ValueError("Native molecule setup changed the actual NumPy namespace")
    reader = context.functions[("MasterOfMolecules", "read_mol_config")]
    if reader.__globals__.get("set_net_opts") is not context.functions[(None, "set_net_opts")]:
        raise ValueError("Original network plotting-options helper association changed")


def _class_header(cls, role):
    """Exact original base/metaclass; DynamicValueDict is genuinely an ABC."""
    meta, base = (ABCMeta, MutableMapping) if role == "DynamicValueDict" else (type, object)
    if type(cls) is not meta or cls.__bases__ != (base,):
        raise ValueError("Original native constructor base/metaclass required: " + role)


def _source_entry(actual, original, owner=None, attribute=None):
    # A spoofed __wrapped__ must not turn arbitrary outer code into native
    # factory authority. Instrumented outer wrappers need their own genuine
    # issued runtime recipe; we do not strip them off a class or execute them
    # just to discover that recipe.
    if actual is not original:
        try:
            wrapper_authority.validate(actual, original, owner=owner, attribute=attribute)
        except wrapper_authority.WrapperAuthorityRejected as error:
            raise MoleculeNetworkRejected(
                "Actual outer factory/type-check wrapper authority is unavailable",
                stage="wrapper_prerequisite",
            ) from error
    return original


def _check(context, *, closed=False):
    _registry(context, closed=closed)
    if context.capture_error is not None:
        raise MoleculeNetworkRejected(
            "Incomplete original source observation", stage="capture", partial=context
        )
    if context.bindings is not None:
        context.initial.core.previous._same(_bindings(context), context.bindings)
    _dynamic_associations(context)


def _function_bindings(fn):
    """Bind effective lookups, including the function's cached builtin mapping."""
    namespace, cached = fn.__globals__, fn.__builtins__
    provider = namespace.get("__builtins__")
    resolved = vars(provider) if type(provider) is ModuleType else provider
    if resolved is not cached or cached is not vars(builtins):
        raise ValueError("Actual original cached builtin/namespace association changed")
    result = [fn, fn.__code__, namespace, cached, fn.__defaults__, fn.__kwdefaults__]
    for cell in fn.__closure__ or ():
        result.extend((cell, cell.cell_contents))
    for name in fn.__code__.co_names:
        if name in namespace:
            value = namespace[name]
            if name in cached and value is not cached[name]:
                raise ValueError("Original source builtin was shadowed: " + name)
            result.extend(("global", name, value))
        elif name in cached:
            value = cached[name]
            result.extend(("builtin", name, value))
        else:
            result.extend(("absent", name))
            continue
        if type(value) is ModuleType:
            for member in fn.__code__.co_names:
                if member in vars(value):
                    result.extend((value, member, vars(value)[member]))
    return tuple(result)


def _callback_pair(context, callbacks):
    """Original nested functions and actual closed owners, without invoking them."""
    reader = context.functions[("MasterOfNetworks", "read_substances")]
    codes = context.initial._code_tree(reader.__code__)
    for fn in callbacks:
        if (
            type(fn) is not FunctionType
            or not any(fn.__code__ is code for code in codes)
            or fn.__globals__ is not reader.__globals__
            or fn.__builtins__ is not reader.__builtins__
        ):
            raise ValueError("Original reader-created getter/setter function required")
        freevars = dict(zip(fn.__code__.co_freevars, fn.__closure__ or (), strict=True))
        if not freevars or any(
            name not in ("self", "sim")
            or cell.cell_contents is not (context.core if name == "self" else context.sim)
            for name, cell in freevars.items()
        ):
            raise ValueError("Getter/setter closure detached from actual core/Simulator")
    return tuple(_function_bindings(fn) for fn in callbacks)


def _dynamic_associations(context):
    for row in context.frames.values():
        if not row.get("returned"):
            _argument_links(context, row)
    for actual, get, set_, frame, bindings in context.dynamic_callbacks:
        # At the constructor CALL event the slots are not assigned yet.
        if context.frames.get(id(frame), {}).get("returned"):
            if actual.get_value is not get or actual.set_value is not set_:
                raise ValueError("Original live DynamicValue slots changed")
        current = _callback_pair(context, (get, set_))
        for now, original in zip(current, bindings, strict=True):
            context.initial.core.previous._same(now, original)
    for actual, mapping, frame in context.dynamic_maps:
        if context.frames.get(id(frame), {}).get("returned"):
            if vars(actual).get("_key_to_dynamic_value") is not mapping:
                raise ValueError("Original live DynamicValueDict backing map changed")
    if getattr(context, "channel_records", ()):
        channels.validate_associations(context)


def _argument_links(context, row):
    for name, original in row.get("arguments", ()):
        if row["frame"].f_locals.get(name) is not original:
            raise ValueError("Original source argument/owner association changed: " + name)


def _actual_functions(api, completion):
    initial, origin = api.previous.previous, completion.init_parent
    callbacks = initial.caches.previous.callbacks
    # Existing process-local native import issuance, not a new module import or
    # an assertion based on matching arbitrary class/module names.
    callbacks.simulator.tissue.aliases._check_modules()
    native = origin.factories["Simulator"]
    original = callbacks._source_function(
        native.init_dynamics, "betse/science/sim.py", "init_dynamics", "Simulator"
    )
    factory = original.__globals__["MasterOfMolecules"]
    module = sys.modules.get("betse.science.chemistry.molecules")
    networks = sys.modules.get("betse.science.chemistry.networks")
    mapping = sys.modules.get("betse.util.type.iterable.mapping.mapcls")
    if (
        module is None
        or networks is None
        or mapping is None
        or vars(module).get("MasterOfMolecules") is not factory
    ):
        raise ValueError("Original actually loaded chemistry modules/factory required")
    classes = dict(MasterOfMolecules=factory)
    _class_header(factory, "MasterOfMolecules")
    if vars(mapping).get("MappingMutableType") is not MutableMapping:
        raise ValueError("Original canonical mutable-mapping base alias required")
    for role in {role for role, _ in source.SITES} - {"MasterOfMolecules", None}:
        owner = mapping if role in ("DynamicValue", "DynamicValueDict") else networks
        cls = vars(owner).get(role)
        _class_header(cls, role)
        classes[role] = cls
    functions, exports, entries = {}, [], []
    for role, cls in classes.items():
        owner = (
            mapping
            if role in ("DynamicValue", "DynamicValueDict")
            else (module if role == "MasterOfMolecules" else networks)
        )
        if (
            vars(owner).get(role) is not cls
            or cls.__name__ != role
            or cls.__module__ != owner.__name__
        ):
            raise ValueError("Actual original chemistry class export required: " + role)
        exports.append((owner, role, cls))
    for (role, name), relative in source.SITES.items():
        original_fn = (
            vars(sys.modules["betse.science.chemistry.netplot"])[name]
            if role is None
            else getattr(classes[role], name)
        )
        fn = callbacks._source_function(original_fn, relative, name, role)
        owner = sys.modules[relative[:-3].replace("/", ".")] if role is None else classes[role]
        _source_entry(original_fn, fn, owner, name)
        if api.previous._constant(fn.__code__) != api.previous._constant(source.code(role, name)):
            raise ValueError(
                "Exact whole-module native molecule method required: " + str(role) + "." + name
            )
        positional, keywords = source.defaults(role, name)
        if api.previous._constant(fn.__defaults__) != api.previous._constant(positional):
            raise ValueError(
                "Original native positional defaults changed: " + str(role) + "." + name
            )
        actual = fn.__kwdefaults__
        if (actual is None) != (keywords is None) or (
            actual is not None
            and (
                tuple(actual) != tuple(keywords)
                or any(
                    api.previous._constant(actual[key]) != api.previous._constant(keywords[key])
                    for key in keywords
                )
            )
        ):
            raise ValueError("Original native keyword defaults changed: " + str(role) + "." + name)
        functions[(role, name)] = fn
        entries.extend(callbacks.simulator._chain(original_fn))
        exports.append(
            (
                sys.modules[relative[:-3].replace("/", ".")],
                role or name,
                classes[role] if role else original_fn,
            )
        )
    functions[("Simulator", "get_ion")] = completion.parent.methods["get_ion"]
    if completion.p.network_config.get("channels") not in (None, []):
        extra_classes, extra_functions, extra_exports, extra_entries = channels.actual_functions(
            api, completion
        )
        classes.update(extra_classes)
        functions.update(extra_functions)
        exports.extend(extra_exports)
        entries.extend(extra_entries)
    return classes, functions, tuple(exports), tuple(entries)


def bind_completion(claim, *, original_owner):
    """One source-backed session; no supplied factory, phase, cache or owner."""
    api = _ready()
    c = api._active(claim)
    caller = sys._getframe(1)
    if (
        caller.f_code is not api.prepare.__code__
        or caller.f_globals is not vars(api)
        or caller.f_locals.get("context") is not c
        or c.molecule is not sys.modules[__name__]
        or c.molecule_session is not None
    ):
        raise MoleculeNetworkRejected(
            "Actual molecular Completion preparation frame required", stage="source_entry"
        )
    if c.request.prelude_owner is not original_owner or claim in _CLAIMED:
        raise MoleculeNetworkRejected("Original once-only molecular claim required", stage="claim")
    config = _configuration(c)
    session = object.__new__(MoleculeSession)
    context = SimpleNamespace(
        session=session,
        claim=claim,
        api=api,
        completion=c,
        original_owner=original_owner,
        initial=api.previous.previous,
        phase=c.phase,
        p=c.p,
        cells=c.cells,
        sim=c.sim,
        handler=c.handler,
        config=config,
        thread=get_ident(),
        active=True,
        invalid=False,
        stage="source_binding",
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        primary=None,
        raw_returns=[],
        work=[],
        constructors=[],
        frames={},
        pending={},
        objects=[],
        dynamic_callbacks=[],
        dynamic_maps=[],
        functions=None,
        classes=None,
        bindings=None,
        mom=None,
        core=None,
        reader_frame=None,
        reader_returned=False,
        evidence=None,
        finished=False,
        factory_attempted=False,
        method_dispatches=[],
        last_raw=None,
        last_source_error=None,
        ancestor_claim=vars(api.previous.previous)[ANCESTOR_CLAIM],
        ancestor_check=vars(api.previous.previous)[ANCESTOR_CHECK],
        ancestor_claimed=False,
        graph_roots_cache=None,
        channel_records=[],
    )
    _SESSIONS[session] = _CLAIMED[claim] = context
    c.molecule_session = session
    try:
        context.classes, context.functions, context.exports, entries = _actual_functions(api, c)
        context.files = tuple(
            (source.NATIVE / relative, pin) for relative, pin in source.PINS.items()
        )
        helpers = context.initial.core.previous.previous._native_helper_functions(
            (*context.functions.values(), *entries)
        )
        context.helper_functions = tuple(helpers)
        seen = set()
        context.source_functions = tuple(
            fn
            for fn in (*context.functions.values(), *entries, *context.helper_functions)
            if not (id(fn) in seen or seen.add(id(fn)))
        )
        context.auxiliary_sources = tuple(
            (
                module,
                Path(module.__file__),
                hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
                tuple(
                    (
                        name,
                        fn,
                        tuple(context.initial.caches.previous.callbacks.simulator._chain(fn)),
                    )
                    for name, fn in vars(module).items()
                    if type(fn) is FunctionType
                ),
            )
            for module in (channels, channel_source, wrapper_authority)
        )
        context.codes = frozenset(
            code
            for fn in context.source_functions
            for code in context.initial._code_tree(fn.__code__)
        )
        context.roles = {fn.__code__: key for key, fn in context.functions.items()}
        if context.ancestor_claim(c.init_parent, c, session) is not c.init_parent:
            raise MoleculeNetworkRejected(
                "Actual same-INIT material/alias ancestor claim required", stage="material_ancestor"
            )
        context.ancestor_claimed = True
        context.bindings = _bindings(context)
        context.stage = "original_molecule_initialization"
        return session
    except BaseException as primary:
        context.invalid, context.primary = True, primary
        _FAILED.append(context)
        raise


def _capture(context, origin, error, raw):
    context.last_capture = (origin, error, raw)
    if context.capture_error is None:
        context.capture_error = error
    try:
        context.capture_errors += (context.last_capture,)
    except BaseException as secondary:
        context.capture_reporting_error = (secondary, context.last_capture)


def construct(session, p, *, completion_claim, source_frame):
    context = _context(session, completion_claim)
    _check(context)
    c = context.completion
    if (
        p is not context.p
        or source_frame is not c.body_frame
        or source_frame.f_globals is not c.namespace
        or source_frame.f_lineno != 871
        or context.factory_attempted
        or vars(context.sim).get("molecules") is not None
    ):
        _reject(context, "Single original MasterOfMolecules(p) source call required")
    context.factory_attempted = True
    context.factory_frame = sys._getframe()
    try:
        returned = context.classes["MasterOfMolecules"](p)
        context.last_constructor_return = returned
        if (
            returned is not context.mom
            or type(returned) is not context.classes["MasterOfMolecules"]
        ):
            _reject(context, "Original observed molecule constructor/return association changed")
        return returned
    except BaseException as primary:
        if context.primary is None:
            context.primary = primary
        raise


def _descended(frame, ancestor):
    while frame is not None and frame is not ancestor:
        frame = frame.f_back
    return frame is ancestor and ancestor is not None


def observe(session, *, completion_claim, frame, event, arg):
    """Called by the existing ONE completion observer before inherited hooks."""
    context = _context(session, completion_claim)
    try:
        returned = _observe_event(context, frame, event, arg)
    except BaseException as error:
        # A CALL refusal must stop the body immediately. At unwind, retain the
        # actual source primary and the independent observation error instead.
        if event == "call":
            context.invalid = True
            if getattr(context, "entry_error", None) is None:
                context.entry_error = error
            if context.primary is None:
                context.primary = error
            raise
        _capture(context, "source_observation", error, (frame, event, arg))
        if context.primary is None:
            raise CaptureStop(
                "Incomplete original molecular observation", stage="capture", partial=context
            ) from error
        return
    if context.capture_error is not None and context.primary is None:
        raise CaptureStop(
            "Incomplete original molecular observation", stage="capture", partial=context
        ) from context.capture_error
    return returned


def _observe_event(context, frame, event, arg):
    if event == "exception":
        context.last_source_error = (frame, arg[1])
        try:
            context.pending[id(frame)] = arg[1]
        except BaseException as capture:
            if context.primary is None:
                context.primary = arg[1]
            _capture(context, "exception_record", capture, (frame, arg))
    if event == "return":
        context.last_raw = (frame, arg)
        if not context.initial._normal_return(frame) and context.primary is None:
            context.primary = context.pending.get(id(frame))
    if event == "call":
        _check(context)
        if len(context.work) >= MAX_WORK or not any(frame.f_code is code for code in context.codes):
            _reject(context, "Bounded original molecule source entry required")
        role = context.roles.get(frame.f_code)
        row = dict(
            frame=frame, code=frame.f_code, globals=frame.f_globals, role=role, returned=False
        )
        context.last_attempt = row
        try:
            context.work.append(row)
        except BaseException as capture:
            _capture(context, "entry_record", capture, row)
            raise MoleculeNetworkRejected(
                "Incomplete source admission", stage="capture", partial=context
            ) from capture
        if role is not None:
            name, method = role
            fn = context.functions[role]
            if frame.f_globals is not fn.__globals__:
                _reject(context, "Original molecular function namespace changed")
            actual = frame.f_locals.get("self")
            count = fn.__code__.co_argcount + fn.__code__.co_kwonlyargcount
            names = fn.__code__.co_varnames[:count]
            authorities = dict(
                sim=context.sim, cells=context.cells, p=context.p, phase=context.phase
            )
            configs = dict(
                config_substances="biomolecules",
                config_reactions="reactions",
                config_transporters="transporters",
                config_channels="channels",
                config_modulators="modulators",
                net_plot_opts="network plotting",
            )
            authorities.update((key, context.config.get(field)) for key, field in configs.items())
            row["arguments"] = tuple((key, authorities[key]) for key in names if key in authorities)
            _argument_links(context, row)
            if (
                role in channel_source.SITES
                and method != "__init__"
                and channels.admit_setup(context, role, frame)
            ):
                pass
            elif name is None:
                if actual is not context.core or not _descended(frame.f_back, context.reader_frame):
                    _reject(context, "Original network plotting-options helper/receiver required")
            elif role == ("Simulator", "get_ion"):
                if actual is not context.sim or not _descended(frame.f_back, context.reader_frame):
                    _reject(context, "Original source-reached ion lookup receiver required")
            elif method == "__init__":
                if type(actual) is not context.classes[name] or any(
                    actual is prior for _, prior in context.objects
                ):
                    _reject(context, "Fresh actual original constructor instance required")
                if name == "MasterOfMolecules":
                    if frame.f_locals.get("p") is not context.p or not _descended(
                        frame.f_back, context.factory_frame
                    ):
                        _reject(context, "Original molecule constructor detached from factory")
                    context.mom = actual
                elif not _descended(frame.f_back, context.reader_frame):
                    _reject(context, "Native child constructor detached from original reader")
                if name == "MasterOfNetworks":
                    if (
                        frame.f_locals.get("sim") is not context.sim
                        or frame.f_locals.get("cells") is not context.cells
                        or frame.f_locals.get("p") is not context.p
                        or frame.f_locals.get("config_substances")
                        is not context.config["biomolecules"]
                    ):
                        _reject(context, "Original core constructor inputs changed")
                    context.core = actual
                context.objects.append((name, actual))
                context.constructors.append((name, actual, frame))
                if name == "DynamicValue":
                    callbacks = frame.f_locals.get("get_value"), frame.f_locals.get("set_value")
                    bindings = _callback_pair(context, callbacks)
                    context.dynamic_callbacks.append((actual, *callbacks, frame, bindings))
                elif name == "DynamicValueDict":
                    mapping = frame.f_locals.get("key_to_dynamic_value")
                    context.dynamic_maps.append((actual, mapping, frame))
            elif role == ("MasterOfMolecules", "read_mol_config"):
                if (
                    actual is not context.mom
                    or vars(context.sim).get("molecules") is not actual
                    or frame.f_locals.get("phase") is not context.phase
                    or context.reader_frame is not None
                    or not _descended(frame.f_back, context.completion.body_frame)
                ):
                    _reject(context, "Original assigned molecule owner/reader/phase order changed")
                context.reader_frame = frame
            elif not any(actual is value for _, value in context.objects) or not _descended(
                frame.f_back, context.reader_frame
            ):
                _reject(context, "Original method receiver/source ancestry changed")
        elif not _descended(frame.f_back, context.reader_frame) and not _descended(
            frame.f_back, getattr(context, "factory_frame", None)
        ):
            _reject(context, "Molecular helper is detached from original setup")
        context.frames[id(frame)] = row
        return
    row = context.frames.get(id(frame))
    if row is None:
        return
    if row["frame"] is not frame or row["globals"] is not frame.f_globals:
        _reject(context, "Original molecular frame/namespace changed")
    if event == "return":
        try:
            context.raw_returns.append(context.last_raw)
        except BaseException as capture:
            _capture(context, "return_record", capture, context.last_raw)
        row["returned"] = True
        if getattr(context, "channel_records", ()):
            channels.returned_setup(context, frame)
        if frame is context.reader_frame and context.initial._normal_return(frame):
            context.reader_returned = arg is None


def source_members(session):
    context = _context(session)
    _registry(context)
    return tuple(context.source_functions)


def owns_source_frame(session, frame):
    """Routing predicate only; it cannot supply a source/owner permission."""
    context = _context(session)
    return _descended(frame, context.reader_frame)


def observes_source_frame(session, frame):
    """Do not attribute a shared logger/NumPy helper outside this source leg."""
    context = _context(session)
    if _descended(frame, context.reader_frame) or _descended(
        frame, getattr(context, "factory_frame", None)
    ):
        return True
    reader = context.functions[("MasterOfMolecules", "read_mol_config")]
    return frame.f_code is reader.__code__ and _descended(
        frame.f_back, context.completion.body_frame
    )


def wrapper_guard(session, *, completion_claim, original, frame):
    context = _context(session, completion_claim)
    _check(context)
    c = context.completion
    wrapper = vars(type(context.sim)).get("get_ion")
    if (
        original is not c.init_parent
        or frame.f_locals.get("context") is not original
        or frame.f_locals.get("name") != "Simulator"
        or frame.f_locals.get("method") != "get_ion"
        or frame.f_locals.get("actual") is not context.sim
        or type(wrapper) is not FunctionType
        or frame.f_code is not wrapper.__code__
        or frame.f_globals is not wrapper.__globals__
        or not _descended(frame.f_back, context.reader_frame)
        or frame.f_locals.get("delegate") is not original.factories["Simulator"].get_ion
    ):
        _reject(context, "Original same-Simulator get_ion wrapper/source association required")
    for name, cell in zip(wrapper.__code__.co_freevars, wrapper.__closure__ or (), strict=True):
        if frame.f_locals.get(name) is not cell.cell_contents:
            _reject(context, "Original get_ion wrapper closure changed")
    context.last_wrapper = frame


def dispatch(session, *, completion_claim, original, label, delegate, actual, args, kwargs, frame):
    context = _context(session, completion_claim)
    _check(context)
    if (
        original is not context.completion.init_parent
        or label != "Simulator.get_ion"
        or actual is not context.sim
        or delegate is not original.factories["Simulator"].get_ion
        or len(args) != 1
        or type(args[0]) is not str
        or kwargs
        or frame.f_code is not context.initial._invoke.__code__
        or frame.f_globals is not vars(context.initial)
        or frame.f_back is not getattr(context, "last_wrapper", None)
    ):
        _reject(context, "Original once-claimed molecular ion lookup required")
    context.last_wrapper = None
    raw = (frame, args, None)
    context.last_ion_call = raw
    context.method_dispatches.append(raw)
    # Reuse the original verified body already held by the true Prelude owner.
    returned = context.completion.parent.methods["get_ion"](actual, *args)
    context.last_ion_return = (frame, returned)
    return returned


def state_roots(session):
    """Live holders only; slotted closures are retained separately, never run."""
    context = _context(session)
    return tuple(
        ("molecular_" + role, actual)
        for role, actual in context.objects
        if hasattr(actual, "__dict__")
    )


def graph_roots(session):
    """Explicit live slot/closure/default edges for the existing closed graph walker."""
    context = _context(session)
    _dynamic_associations(context)
    cache = getattr(context, "graph_roots_cache", None)
    if cache is None:
        cache = context.graph_roots_cache = dict(
            constructor_objects=context.objects,
            callback_rows=[],
            mapping_rows=[],
            dynamic_slots=[],
            callback_edges=[],
            mapping_edges=[],
            source_returns=context.raw_returns,
        )
    if (
        cache["constructor_objects"] is not context.objects
        or cache["source_returns"] is not context.raw_returns
    ):
        raise ValueError("Original source graph holder association changed")
    for name, rows in (
        ("callback_rows", context.dynamic_callbacks),
        ("mapping_rows", context.dynamic_maps),
    ):
        retained = cache[name]
        if len(rows) < len(retained) or any(
            row is not rows[index] for index, row in enumerate(retained)
        ):
            raise ValueError("Original constructor observation row was replaced or omitted")
        for row in rows[len(retained) :]:
            if name == "callback_rows":
                actual, get, set_, _, _ = row
                cache["dynamic_slots"].append((actual, get, set_))
                for fn in (get, set_):
                    cache["callback_edges"].append(
                        (
                            fn,
                            fn.__code__,
                            fn.__defaults__,
                            fn.__kwdefaults__,
                            tuple((cell, cell.cell_contents) for cell in fn.__closure__ or ()),
                        )
                    )
            else:
                actual, mapping, _ = row
                cache["mapping_edges"].append((actual, mapping))
            retained.append(row)
    return cache


def project_state(session, value, memo=None):
    """Evidence view only; original live callbacks/maps are never evaluated.

    Object/array alias and layout validation still uses the actual state graph.
    These tokens allow the closed value encoder to describe native slotted
    mappings without manufacturing a replacement runtime mapping or callable.
    """
    context = _context(session)
    memo = {} if memo is None else memo
    if type(value) is context.classes["DynamicValue"]:
        rows = [row for row in context.dynamic_callbacks if row[0] is value]
        if len(rows) != 1 or value.get_value is not rows[0][1] or value.set_value is not rows[0][2]:
            _reject(context, "Original constructor-created dynamic callback association changed")
        return dict(
            original_dynamic_value=next(
                index for index, (_, actual) in enumerate(context.objects) if actual is value
            )
        )
    if type(value) is context.classes["DynamicValueDict"]:
        rows = [row for row in context.dynamic_maps if row[0] is value]
        if len(rows) != 1 or vars(value).get("_key_to_dynamic_value") is not rows[0][1]:
            _reject(context, "Original constructor-created dynamic mapping association changed")
        return dict(
            original_dynamic_mapping=tuple(
                (key, project_state(session, actual, memo)) for key, actual in rows[0][1].items()
            )
        )
    if type(value) in (dict, OrderedDict, list, tuple):
        if id(value) in memo:
            return memo[id(value)]
        if type(value) in (dict, OrderedDict):
            result = {}
            memo[id(value)] = result
            result.update((key, project_state(session, item, memo)) for key, item in value.items())
        else:
            result = []
            memo[id(value)] = result
            result.extend(project_state(session, item, memo) for item in value)
            if type(value) is tuple:
                result = tuple(result)
                memo[id(value)] = result
        return result
    return value


def validate_active(session, *, completion_claim):
    context = _context(session, completion_claim)
    _check(context)
    return session


def finish(session, *, completion_claim):
    context = _context(session, completion_claim)
    _check(context)
    if (
        not context.reader_returned
        or context.primary is not None
        or context.capture_error is not None
        or context.mom is None
        or context.core is None
        or context.sim.molecules is not context.mom
        or context.mom.core is not context.core
        or any(not row["returned"] for row in context.work)
    ):
        _reject(context, "Complete original fresh molecule/configuration setup required")
    if channels.declarations(context):
        channels.finish_setup(context)
    record = SourceEvidence(
        True,
        context.claim,
        context.mom,
        context.core,
        tuple(context.constructors),
        tuple(context.work),
        tuple(context.raw_returns),
        tuple(context.dynamic_callbacks),
        "",
    )
    identity = context.api._digest(
        dict(
            claim=id(context.claim),
            mom=id(context.mom),
            core=id(context.core),
            work=tuple((id(row["frame"]), row["returned"]) for row in context.work),
        )
    )
    context.evidence = SourceEvidence(
        *tuple(getattr(record, name) for name in record.__dataclass_fields__ if name != "identity"),
        identity,
    )
    context.active, context.finished = False, True
    return context.evidence


def validate_closed(session, *, completion_claim):
    context = _context(session, completion_claim)
    if context.active or not context.finished or context.evidence is None:
        _reject(context, "Original successfully finished molecular source session required")
    _check(context, closed=True)
    if context.sim.molecules is not context.mom or context.mom.core is not context.core:
        _reject(context, "Original fresh molecular owner/core association changed")
    return context.evidence


def failed_context(session):
    """Actual retained live partial only; never a retry/replay capability."""
    context = _context(session)
    if context.evidence is not None or not (
        context.primary is not None or context.capture_error is not None or context.invalid
    ):
        raise MoleculeNetworkRejected("No actual failed molecular source prefix", stage="failure")
    return context


def _effect_fields(node, receiver):
    """Original attribute/subscript/list stores; never evaluate an expression."""
    fields = set()
    for value in ast.walk(node):
        if isinstance(value, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
            targets = (
                value.targets if isinstance(value, (ast.Assign, ast.Delete)) else (value.target,)
            )
        elif isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
            targets = (
                (value.func.value,) if value.func.attr in ("append", "extend", "clear") else ()
            )
        else:
            continue
        for target in targets:
            for member in ast.walk(target):
                if (
                    isinstance(member, ast.Attribute)
                    and isinstance(member.value, ast.Name)
                    and member.value.id == receiver
                ):
                    fields.add(member.attr)
    return frozenset(fields)


def _runtime_field_table(kind):
    """Derive actual class fields from the pinned native method/loop bodies."""
    if kind not in ("storage", "first_step"):
        raise ValueError("Exact molecular runtime epoch required")
    names = ("clear_cache",) if kind == "storage" else source.RUNTIME_NETWORK_METHODS[1:]
    table = {"MasterOfNetworks": set(), "Molecule": set(), "Transporter": set(), "Reaction": set()}
    mapping = {"molecules": "Molecule", "transporters": "Transporter", "reactions": "Reaction"}
    for name in names:
        node = source.node("MasterOfNetworks", name)
        table["MasterOfNetworks"].update(_effect_fields(node, "self"))
        if name == "run_loop":
            table["Molecule"].update(_effect_fields(node, "obj"))
        elif name == "run_loop_transporters":
            table["Transporter"].update(_effect_fields(node, "obj"))
        if name in ("clear_cache", "write_data"):
            for loop in (item for item in node.body if isinstance(item, ast.For)):
                iterator = loop.iter
                field = iterator.attr if isinstance(iterator, ast.Attribute) else None
                if field in mapping:
                    table[mapping[field]].update(_effect_fields(loop, "obj"))
    if kind == "first_step":
        for name in source.RUNTIME_MOLECULE_METHODS:
            table["Molecule"].update(_effect_fields(source.node("Molecule", name), "self"))
        table["Simulator"] = set(_effect_fields(source.node("MasterOfNetworks", "run_loop"), "sim"))
        # The original reader-created setters write the same actual ionic
        # buffers as initialization, never a copied dynamic mapping.
        table["Simulator"].update(("cc_cells", "cc_env", "c_env_bound"))
    return {role: frozenset(fields) for role, fields in table.items()}


def _runtime_route(runtime):
    original, c, child = runtime.original, runtime.original.completion, runtime.child
    _check(original, closed=True)
    if (
        _RUNTIME.get(runtime.claim) is not runtime
        or runtime.registry.get(original.session) is not runtime
        or c is not runtime.completion
        or runtime.thread != get_ident()
        or runtime.invalid
        or child.parent is not c
        or child.phase is not original.phase
        or child.p is not original.p
        or child.cells is not original.cells
        or child.sim is not original.sim
        or child.invalid
        or child.thread != runtime.thread
    ):
        raise MoleculeNetworkRejected(
            "Original runtime/session/child ancestry changed", stage="runtime"
        )
    if runtime.kind == "storage":
        actual, module = original.api._storage_route(c)
        if (
            actual is not child
            or module is not runtime.module
            or c.storage_lease.molecule_claim is not runtime.claim
        ):
            raise ValueError("Different original molecular storage child")
    else:
        lease = original.api._first_step_route(c, runtime.storage, runtime.electrical, child)
        if lease.module is not runtime.module or lease.molecule_claim is not runtime.claim:
            raise ValueError("Different original molecular first-step child")
    _runtime_expressions(runtime)
    _runtime_mappings(runtime)
    return runtime


def _runtime_mappings(runtime):
    if type(runtime.dynamic_maps) is not tuple:
        raise ValueError("Original runtime dynamic mapping roster changed")
    for actual, mapping, entries in runtime.dynamic_maps:
        current = tuple(mapping.items())
        if (
            vars(actual).get("_key_to_dynamic_value") is not mapping
            or len(current) != len(entries)
            or any(
                key is not original_key or value is not original_value
                for (key, value), (original_key, original_value) in zip(
                    current, entries, strict=True
                )
            )
        ):
            raise ValueError("Original dynamic keys/order/slot aliases changed during runtime")


def _runtime_expressions(runtime):
    original = runtime.original
    if (
        type(runtime.expressions) is not tuple
        or type(runtime.expression_bindings) is not tuple
        or len(runtime.expressions) != len(runtime.expression_bindings)
    ):
        raise ValueError("Complete immutable initialized expression roster required")
    for (owner, field, text, code), (probe, expected) in zip(
        runtime.expressions, runtime.expression_bindings, strict=True
    ):
        if (
            vars(owner).get(field) is not text
            or type(code) is not CodeType
            or type(probe) is not FunctionType
            or probe.__code__ is not code
            or probe.__globals__
            is not original.functions[("MasterOfNetworks", "run_loop")].__globals__
        ):
            raise ValueError("Actual initialized network expression association changed")
        original.initial.core.previous._same(_function_bindings(probe), expected)


def _runtime_context(claim):
    if type(claim) is not MoleculeRuntimeClaim or claim not in _RUNTIME:
        raise MoleculeNetworkRejected(
            "Actual issued molecular runtime claim required", stage="runtime_claim"
        )
    return _runtime_route(_RUNTIME[claim])


def _bind_runtime(session, completion, child, kind, module, *, storage=None, electrical=None):
    caller = sys._getframe(1)
    entry = bind_storage if kind == "storage" else bind_first_step
    child_name = "storage" if kind == "storage" else "step"
    if (
        kind not in ("storage", "first_step")
        or caller.f_code is not entry.__code__
        or caller.f_globals is not globals()
        or caller.f_locals.get("session") is not session
        or caller.f_locals.get("completion") is not completion
        or caller.f_locals.get(child_name) is not child
    ):
        raise MoleculeNetworkRejected(
            "Actual public runtime binder frame required", stage="runtime_entry"
        )
    original = _context(session, completion.claim)
    _check(original, closed=True)
    if original.completion is not completion or child.parent is not completion:
        raise ValueError("Original closed molecule participant/Completion required")
    registry = _STORAGE_RUNTIME if kind == "storage" else _STEP_RUNTIME
    if session in registry:
        raise MoleculeNetworkRejected(
            "Molecular descendant epoch already attempted", stage="runtime_consumed"
        )
    claim = object.__new__(MoleculeRuntimeClaim)
    runtime = SimpleNamespace(
        claim=claim,
        original=original,
        completion=completion,
        child=child,
        kind=kind,
        module=module,
        storage=storage,
        electrical=electrical,
        registry=registry,
        thread=get_ident(),
        invalid=False,
        active=True,
        primary=None,
        primary_origin=None,
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        last_raw=None,
        raw_returns=[],
        c_calls=[],
        work=[],
        frames={},
        pending={},
        top_calls=[],
        source_exceptions=[],
        expressions=[],
        expression_bindings=[],
        dynamic_maps=(),
        record=None,
        permissions=(),
    )
    _RUNTIME[claim] = registry[session] = runtime
    lease = completion.storage_lease if kind == "storage" else completion.first_step_descendant
    lease.molecule_claim = claim
    try:
        if original.core.mit_enabled is not False:
            raise ValueError("Original mitochondrial runtime owner remains unavailable")
        if original.core.transporters:
            raise ValueError("Configured transporter runtime expressions/flux remain unavailable")
        if getattr(original.core, "modulators", {}):
            raise ValueError("Independent modulator runtime owners remain unavailable")
        if kind == "first_step":
            old = _STORAGE_RUNTIME.get(session)
            if old is None or old.record is None or old.child is not storage:
                raise ValueError("Actual completed molecular storage epoch required")
            _runtime_route(old)
            runtime.dynamic_maps = old.dynamic_maps
            for obj in original.core.molecules.values():
                if any(
                    getattr(obj, field)
                    for field in (
                        "active_pumping",
                        "ion_channel_gating",
                        "change_bounds",
                        "cell_clamp",
                    )
                ):
                    raise ValueError(
                        "Original pumping/gating/boundary/clamp runtime owner unavailable"
                    )
                text = obj.gad_eval_string
                if type(text) is not str:
                    raise ValueError("Actual initialized growth/decay expression required")
                runtime.expressions.append(
                    (
                        obj,
                        "gad_eval_string",
                        text,
                        compile(text, "<string>", "eval", dont_inherit=True),
                    )
                )
            for collection in (original.core.reactions, original.core.reactions_env):
                for obj in collection.values():
                    text = obj.reaction_eval_string
                    if type(text) is not str:
                        raise ValueError("Actual initialized reaction expression required")
                    runtime.expressions.append(
                        (
                            obj,
                            "reaction_eval_string",
                            text,
                            compile(text, "<string>", "eval", dont_inherit=True),
                        )
                    )
            for record in getattr(original, "channel_records", ()):
                channel = record["channel"]
                if channel.init_active is True:
                    text = channel.alpha_eval_string
                    if type(text) is not str:
                        raise ValueError("Actual original channel influence expression required")
                    runtime.expressions.append(
                        (
                            channel,
                            "alpha_eval_string",
                            text,
                            compile(text, "<string>", "eval", dont_inherit=True),
                        )
                    )
        if kind == "storage":
            rows = []
            for actual, mapping, _ in original.dynamic_maps:
                if type(mapping) not in (dict, OrderedDict):
                    raise ValueError("Original closed dictionary backing authority required")
                rows.append((actual, mapping, tuple(mapping.items())))
            runtime.dynamic_maps = tuple(rows)
        if kind == "first_step":
            namespace = original.functions[("MasterOfNetworks", "run_loop")].__globals__
            for _, _, _, code in runtime.expressions:
                # Lookup metadata only. Never call this probe or supply it
                # as native executable/callback authority.
                probe = FunctionType(code, namespace)
                runtime.expression_bindings.append((probe, _function_bindings(probe)))
        runtime.expressions = tuple(runtime.expressions)
        runtime.expression_bindings = tuple(runtime.expression_bindings)
        table = _runtime_field_table(kind)
        # These original branches are explicitly disabled by the runtime
        # domain, so their fields do not acquire mutation permission.
        table["MasterOfNetworks"] -= frozenset(
            ("vmit_time", "reaction_rates_mit", "delta_conc_mit", "mit_concs", "mit")
        )
        table["Molecule"] -= frozenset(("c_mit_time",))
        rows = [(actual, table[role]) for role, actual in original.objects if role in table]
        if kind == "first_step":
            sim_fields = table["Simulator"]
            if getattr(original, "channel_records", ()):
                sim_fields |= frozenset(("cc_at_mem",))
            rows.append((original.sim, sim_fields))
        if getattr(original, "channel_records", ()):
            rows.extend(channels.permission_rows(original, kind))
        if len({id(owner) for owner, _ in rows}) != len(rows):
            raise ValueError("Each original runtime holder must have one declared role")
        runtime.permissions = tuple(rows)
        return claim
    except BaseException as primary:
        runtime.invalid, runtime.primary = True, primary
        try:
            _FAILED.append(runtime)
        except BaseException as capture:
            _capture(runtime, "failure_registry", capture, primary)
        try:
            primary.molecule_runtime_partial = runtime
        except BaseException as capture:
            _capture(runtime, "failure_attachment", capture, primary)
        raise


def bind_storage(session, *, completion, storage):
    """Called only by actual Completion storage claim, after its lease exists."""
    original, frame = _context(session), sys._getframe(1)
    api = original.api
    if (
        frame.f_code is not api._claim_for_init_storage.__code__
        or frame.f_globals is not vars(api)
        or frame.f_locals.get("context") is not completion
        or frame.f_locals.get("transition") is not storage
        or storage.body_frame is not None
        or not storage.active
    ):
        raise MoleculeNetworkRejected(
            "Actual still-unrun storage claim frame required", stage="runtime_entry"
        )
    child, module = api._storage_route(completion)
    if child is not storage:
        raise ValueError("Different original storage claimant")
    return _bind_runtime(session, completion, storage, "storage", module)


def bind_first_step(session, *, completion, storage, electrical, step):
    """Called after the actual first-step ancestor reservation, before setup."""
    original, frame = _context(session), sys._getframe(1)
    api = original.api
    if (
        frame.f_code is not api._claim_first_step_ancestor.__code__
        or frame.f_globals is not vars(api)
        or frame.f_locals.get("context") is not completion
        or frame.f_locals.get("transition") is not step
        or step.setup_frame is not None
        or step.loop_frame is not None
        or step.work
        or not step.active
        or step.invalid
    ):
        raise MoleculeNetworkRejected(
            "Actual still-unrun first-step claim frame required", stage="runtime_entry"
        )
    lease = api._first_step_route(completion, storage, electrical, step)
    return _bind_runtime(
        session,
        completion,
        step,
        "first_step",
        lease.module,
        storage=storage,
        electrical=electrical,
    )


def runtime_permissions(claim):
    """Exact actual holders and pinned-source fields; no caller-supplied rows."""
    return _runtime_context(claim).permissions


def runtime_members(claim):
    runtime = _runtime_context(claim)
    return (
        *runtime.original.source_functions,
        *(fn for _, get, set_, _, _ in runtime.original.dynamic_callbacks for fn in (get, set_)),
    )


def runtime_codes(claim):
    runtime = _runtime_context(claim)
    return tuple(code for _, _, _, code in runtime.expressions)


def observes_runtime_frame(claim, frame):
    """Routing only: common helpers outside the molecular leg are not ours."""
    runtime = _runtime_context(claim)
    original = runtime.original
    _, role, arguments, _ = _runtime_resolution(runtime, frame)
    if (
        role is not None
        and role[0] == "MasterOfNetworks"
        and arguments.get("self") is original.core
    ):
        return True
    ancestor = frame.f_back
    masters = tuple(
        fn for (role, _), fn in original.functions.items() if role == "MasterOfNetworks"
    )
    while ancestor is not None:
        row = runtime.frames.get(id(ancestor))
        if row is not None and row["frame"] is ancestor and not row["returned"]:
            if any(
                ancestor.f_code is fn.__code__ or row.get("wrapper_for") is fn for fn in masters
            ):
                return True
        ancestor = ancestor.f_back
    return False


def runtime_wrapper_guard(claim, *, child, original, frame):
    runtime = _runtime_context(claim)
    context = runtime.original
    wrapper = vars(type(context.sim)).get("get_ion")
    caller = frame.f_back
    source_function = context.functions[("MasterOfNetworks", "run_loop_channels")]
    if (
        runtime.kind != "first_step"
        or child is not runtime.child
        or original is not context.completion.init_parent
        or type(wrapper) is not FunctionType
        or frame.f_code is not wrapper.__code__
        or frame.f_globals is not wrapper.__globals__
        or frame.f_locals.get("context") is not original
        or frame.f_locals.get("name") != "Simulator"
        or frame.f_locals.get("method") != "get_ion"
        or frame.f_locals.get("actual") is not context.sim
        or caller.f_code is not source_function.__code__
        or caller.f_globals is not source_function.__globals__
        or caller.f_locals.get("self") is not context.core
        or not observes_runtime_frame(claim, caller)
    ):
        _runtime_error(runtime, "Actual source-reached runtime ion wrapper required")
    for name, cell in zip(wrapper.__code__.co_freevars, wrapper.__closure__ or (), strict=True):
        if frame.f_locals.get(name) is not cell.cell_contents:
            _runtime_error(runtime, "Original runtime ion wrapper closure changed")
    runtime.ion_wrapper = frame


def runtime_dispatch(claim, *, child, original, label, delegate, actual, args, kwargs, frame):
    runtime = _runtime_context(claim)
    context = runtime.original
    wrapper = getattr(runtime, "ion_wrapper", None)
    if (
        child is not runtime.child
        or original is not context.completion.init_parent
        or label != "Simulator.get_ion"
        or actual is not context.sim
        or delegate is not original.factories["Simulator"].get_ion
        or frame.f_code is not context.initial._invoke.__code__
        or frame.f_globals is not vars(context.initial)
        or frame.f_back is not wrapper
        or wrapper is None
        or len(args) != 1
        or kwargs
        or args[0] is not wrapper.f_back.f_locals.get("ion")
    ):
        _runtime_error(runtime, "Actual once-claimed runtime ion dispatch required")
    runtime.ion_wrapper = None
    runtime.ion_driver = sys._getframe()
    runtime.last_ion_arguments = args
    value = context.completion.parent.methods["get_ion"](actual, *args)
    runtime.last_ion_return = value
    return value


def _runtime_error(runtime, reason):
    runtime.invalid = True
    error = MoleculeNetworkRejected(reason, stage="runtime_source", partial=runtime)
    if getattr(runtime, "entry_error", None) is None:
        runtime.entry_error = error
    if runtime.primary is None:
        runtime.primary = error
        runtime.primary_origin = "entry"
    raise error


def _runtime_observer(runtime, caller, frame, event, arg):
    observer = runtime.child.observer_namespace.get("_observe")
    if (
        type(observer) is not FunctionType
        or caller.f_code is not observer.__code__
        or caller.f_globals is not observer.__globals__
        or caller.f_locals.get("context") is not runtime.child
        or caller.f_locals.get("frame") is not frame
        or caller.f_locals.get("event") is not event
        or caller.f_locals.get("arg") is not arg
    ):
        _runtime_error(runtime, "Only the actual original child observer may report runtime work")


def _runtime_resolution(runtime, frame):
    original = runtime.original
    functions = (
        *original.source_functions,
        *(fn for _, get, set_, _, _ in original.dynamic_callbacks for fn in (get, set_)),
    )
    function = next(
        (
            fn
            for fn in functions
            if fn.__code__ is frame.f_code
            and fn.__globals__ is frame.f_globals
            and all(
                frame.f_locals.get(name) is cell.cell_contents
                for name, cell in zip(fn.__code__.co_freevars, fn.__closure__ or (), strict=True)
            )
        ),
        None,
    )
    if function is None:
        return None, None, None, None
    role = next((key for key, fn in original.functions.items() if fn is function), None)
    arguments, delegate = frame.f_locals, None
    defaults = function.__kwdefaults__ or {}
    candidate = defaults.get("__beartype_func")
    selected = next((key for key, fn in original.functions.items() if fn is candidate), None)
    if selected is not None:
        if vars(function).get("__wrapped__") is not candidate:
            _runtime_error(runtime, "Actual observed wrapper/delegate edge changed")
        owner = original.classes[selected[0]]
        wrapper_authority.validate(function, candidate, owner=owner, attribute=selected[1])
        if any(frame.f_locals.get(name) is not value for name, value in defaults.items()):
            _runtime_error(runtime, "Source call replaced a hidden wrapper binding")
        args, kwargs = frame.f_locals.get("args"), frame.f_locals.get("kwargs")
        if type(args) is not tuple or type(kwargs) is not dict:
            _runtime_error(runtime, "Actual original wrapper argument holders required")
        names = candidate.__code__.co_varnames[: candidate.__code__.co_argcount]
        arguments = dict(zip(names, args, strict=False))
        for name, value in kwargs.items():
            if name in arguments:
                _runtime_error(runtime, "Duplicate original wrapper argument")
            arguments[name] = value
        role, delegate = selected, candidate
    return function, role, arguments, delegate


def _runtime_entry(runtime, frame):
    original = runtime.original
    root = runtime.child.body_frame if runtime.kind == "storage" else runtime.child.loop_frame
    if root is None or not _descended(frame.f_back, root):
        _runtime_error(runtime, "Runtime source is detached from the actual original child body")
    function, role, arguments, wrapper_for = _runtime_resolution(runtime, frame)
    expression = next(
        (
            code
            for _, _, _, code in runtime.expressions
            if original.api.previous._constant(code)
            == original.api.previous._constant(frame.f_code)
        ),
        None,
    )
    if function is None:
        if (
            expression is None
            or frame.f_globals
            is not original.functions[("MasterOfNetworks", "run_loop")].__globals__
        ):
            _runtime_error(runtime, "Unowned source or generated expression reached runtime")
        parent = frame.f_back
        runners = tuple(
            fn
            for (role, name), fn in original.functions.items()
            if role == "MasterOfNetworks" and name in ("run_loop", "run_loop_channels")
        )
        if not any(
            parent.f_code is runner.__code__ for runner in runners
        ) or frame.f_locals is not parent.f_locals.get("localo"):
            _runtime_error(runtime, "Original eval globals/locals/source-frame association changed")
        authorities = dict(
            self=original.core,
            phase=original.phase,
            sim=original.sim,
            cells=original.cells,
            p=original.p,
            t=root.f_locals.get("t"),
        )
        for name in frame.f_code.co_names:
            if name in frame.f_locals and (
                name not in authorities or frame.f_locals[name] is not authorities[name]
            ):
                _runtime_error(runtime, "Unowned or foreign eval local resolution: " + name)
        return
    if frame.f_globals is not function.__globals__:
        _runtime_error(runtime, "Original runtime function namespace changed")
    wrapped_parent = runtime.frames.get(id(frame.f_back))
    wrapped_parent = (
        wrapped_parent
        if wrapped_parent is not None
        and wrapped_parent["frame"] is frame.f_back
        and wrapped_parent.get("wrapper_for") is function
        else None
    )
    if wrapped_parent is not None:
        if wrapped_parent.get("body_dispatched"):
            _runtime_error(runtime, "Wrapper may dispatch its original body only once")
        wrapped_parent["body_dispatched"] = True
    if role is not None:
        channel_call = role in channel_source.SITES and channels.runtime_admit(
            original, role, frame, runtime
        )
        if (
            role not in source.RUNTIME_SITES
            and role[0] not in ("DynamicValueDict", "Simulator")
            and not channel_call
        ):
            _runtime_error(runtime, "Initialization/reload source cannot be replayed as runtime")
        actual = arguments.get("self")
        if role[0] == "MasterOfNetworks":
            if actual is not original.core:
                _runtime_error(runtime, "Different actual network core")
            name = role[1]
            if name in (
                "clear_cache",
                "clear_run_loop",
                "run_loop",
                "run_loop_transporters",
                "run_loop_channels",
                "run_loop_modulators",
                "write_data",
                "report",
            ):
                caller = frame.f_back
                stored = runtime.child.frames.get(id(caller))
                same_body = (
                    wrapped_parent is not None
                    or caller is root
                    or (
                        runtime.kind == "first_step"
                        and name in ("write_data", "report")
                        and stored is not None
                        and stored["frame"] is caller
                        and caller.f_locals.get("self") is original.sim
                        and any(
                            caller.f_code is method.__code__
                            and caller.f_globals is method.__globals__
                            for method in runtime.child.methods.values()
                        )
                    )
                )
                if not same_body:
                    _runtime_error(runtime, "Original top-level network call has a foreign parent")
                calls = runtime.top_calls
                if wrapped_parent is not None:
                    # The outer observed wrapper already owns this one call.
                    expected_body = wrapped_parent["wrapper_for"]
                    if expected_body is not function:
                        _runtime_error(runtime, "Different original wrapped runtime body")
                    calls = None
                if calls is None:
                    valid = True
                elif runtime.kind == "storage":
                    valid = name == "clear_cache" and not calls
                else:
                    expected = ["clear_run_loop"]
                    if original.mom.transporters:
                        expected.append("run_loop_transporters")
                    if original.mom.channels:
                        expected.append("run_loop_channels")
                    expected.append("run_loop")
                    expected.extend(("write_data", "report"))
                    valid = len(calls) < len(expected) and name == expected[len(calls)]
                if not valid:
                    _runtime_error(
                        runtime, "Duplicate, omitted or out-of-order original network call"
                    )
                if calls is not None:
                    calls.append(name)
        elif role == ("Simulator", "get_ion"):
            if actual is not original.sim or frame.f_back is not getattr(
                runtime, "ion_driver", None
            ):
                _runtime_error(runtime, "Original source-owned runtime ion body required")
        elif not any(actual is owner for _, owner in original.objects):
            _runtime_error(runtime, "Different original runtime object")
    else:
        parent = frame.f_back
        accepted = runtime.frames.get(id(parent))
        if parent is not root and (
            accepted is None or accepted["frame"] is not parent or accepted["returned"]
        ):
            _runtime_error(runtime, "Reached helper has no admitted immediate source parent")
    # Helpers and keyword-only parameters carry the SAME real owners as
    # listed methods. Matching code/globals or root descent is insufficient.
    code = function.__code__ if wrapper_for is None else wrapper_for.__code__
    names = code.co_varnames[: code.co_argcount + code.co_kwonlyargcount]
    for name, authority in (
        ("phase", original.phase),
        ("p", original.p),
        ("cells", original.cells),
        ("sim", original.sim),
    ):
        if name in names and arguments.get(name) is not authority:
            _runtime_error(runtime, "Runtime argument authority changed: " + name)
    if "t" in names and arguments.get("t") is not root.f_locals.get("t"):
        _runtime_error(runtime, "Actual original runtime source clock changed")
    return wrapper_for


def observe_runtime(claim, *, child, frame, event, arg):
    """Use the child's one existing observer; keep raw and capture errors apart."""
    if type(claim) is not MoleculeRuntimeClaim or claim not in _RUNTIME:
        raise MoleculeNetworkRejected(
            "Actual issued molecular runtime claim required", stage="runtime_claim"
        )
    runtime = _RUNTIME[claim]
    if event == "return":
        runtime.last_raw = (frame, arg)
    elif event == "exception":
        runtime.last_source_error = (frame, arg[1])
    try:
        if event == "exception":
            runtime.pending[id(frame)] = arg[1]
            runtime.source_exceptions.append((frame, arg[1]))
        if (
            event == "return"
            and not runtime.original.initial._normal_return(frame)
            and getattr(runtime, "primary_origin", None) != "source"
        ):
            source_primary = runtime.pending.get(id(frame))
            if source_primary is not None:
                runtime.primary, runtime.primary_origin = source_primary, "source"
        _runtime_observer(runtime, sys._getframe(1), frame, event, arg)
        _runtime_route(runtime)
        if runtime.capture_error is not None and event not in (
            "exception",
            "return",
            "c_exception",
        ):
            raise CaptureStop(
                "Runtime observation already incomplete", stage="runtime_capture", partial=runtime
            ) from runtime.capture_error
        if child is not runtime.child or not runtime.active:
            _runtime_error(runtime, "Actual active runtime child required")
        if event == "call":
            if len(runtime.work) >= MAX_WORK:
                _runtime_error(runtime, "Bounded runtime source work exhausted")
            row = dict(frame=frame, code=frame.f_code, returned=False)
            runtime.work.append(row)
            row["wrapper_for"] = _runtime_entry(runtime, frame)
            runtime.frames[id(frame)] = row
        elif event == "return":
            row = runtime.frames.get(id(frame))
            if row is None or row["frame"] is not frame:
                _runtime_error(runtime, "Return without original runtime entry")
            runtime.raw_returns.append(runtime.last_raw)
            row["returned"] = runtime.original.initial._normal_return(frame)
        elif event in ("c_call", "c_return", "c_exception"):
            row = runtime.frames.get(id(frame))
            if row is None or row["frame"] is not frame:
                _runtime_error(runtime, "Native C call without original runtime source entry")
            if len(runtime.work) + len(runtime.c_calls) >= MAX_WORK:
                _runtime_error(runtime, "Bounded runtime source work exhausted")
            runtime.c_calls.append((frame, event, arg))
    except BaseException as error:
        if event == "call":
            runtime.invalid = True
            if getattr(runtime, "entry_error", None) is None:
                runtime.entry_error = error
            if runtime.primary is None:
                runtime.primary, runtime.primary_origin = error, "entry"
            raise
        if event == "exception" and getattr(runtime, "primary_origin", None) != "source":
            runtime.primary, runtime.primary_origin = arg[1], "source"
        _capture(runtime, event, error, (frame, arg))
        # A C unwind profile event carries the delegate, not its active error.
        # Let the original trace/unwind publish that error before refusing.
        if event not in ("exception", "c_exception") and (
            runtime.primary is None or event != "return"
        ):
            raise CaptureStop(
                "Incomplete runtime observation", stage="runtime_capture", partial=runtime
            ) from error


def _runtime_record_data(runtime):
    return dict(
        kind=runtime.kind,
        child=id(runtime.child),
        session=id(runtime.original.session),
        work=tuple((id(row["frame"]), row["returned"]) for row in runtime.work),
        returns=tuple((id(frame), id(value)) for frame, value in runtime.raw_returns),
        c_calls=tuple(
            (id(frame), event, id(delegate)) for frame, event, delegate in runtime.c_calls
        ),
        exceptions=tuple((id(frame), id(error)) for frame, error in runtime.source_exceptions),
        top_calls=tuple(runtime.top_calls),
    )


def finish_runtime(claim, *, child):
    runtime = _runtime_context(claim)
    caller = sys._getframe(1)
    if (
        caller.f_code is not runtime.module.prepare.__code__
        or caller.f_globals is not vars(runtime.module)
        or caller.f_locals.get("context") is not child
        or child.observing
        or child.primary is not None
        or child.capture_error is not None
        or not (child.body_returned if runtime.kind == "storage" else child.iteration_complete)
    ):
        _runtime_error(runtime, "Only the actual completed child preparation may seal runtime")
    if child is not runtime.child or not runtime.active:
        _runtime_error(runtime, "One original active runtime finish required")
    if runtime.primary is not None:
        raise runtime.primary
    expected = ["clear_cache"] if runtime.kind == "storage" else ["clear_run_loop"]
    if runtime.kind == "first_step":
        if runtime.original.mom.transporters:
            expected.append("run_loop_transporters")
        if runtime.original.mom.channels:
            expected.append("run_loop_channels")
        expected.append("run_loop")
    calls = runtime.top_calls
    if (
        calls not in (expected, expected + ["write_data", "report"])
        or runtime.primary is not None
        or runtime.capture_error is not None
        or not runtime.work
        or any(not row["returned"] for row in runtime.work)
    ):
        _runtime_error(runtime, "Incomplete original network runtime work")
    identity = runtime.original.api._digest(_runtime_record_data(runtime))
    record = RuntimeEvidence(
        runtime.kind,
        runtime.original.session,
        child,
        True,
        tuple(runtime.work),
        tuple(runtime.c_calls),
        tuple(runtime.source_exceptions),
        tuple(runtime.raw_returns),
        identity,
    )
    runtime.record, runtime.active = record, False
    return record


def validate_runtime(claim, *, child):
    runtime = _runtime_context(claim)
    if child is not runtime.child or runtime.active or runtime.record is None:
        _runtime_error(runtime, "Actual completed original runtime record required")
    record = runtime.record
    if (
        record.kind != runtime.kind
        or record.child is not child
        or record.session is not runtime.original.session
        or record.source_completed is not True
        or record.identity != runtime.original.api._digest(_runtime_record_data(runtime))
        or len(record.work) != len(runtime.work)
        or any(a is not b for a, b in zip(record.work, runtime.work, strict=True))
        or len(record.raw_returns) != len(runtime.raw_returns)
        or any(a is not b for a, b in zip(record.raw_returns, runtime.raw_returns, strict=True))
        or len(record.c_calls) != len(runtime.c_calls)
        or any(a is not b for a, b in zip(record.c_calls, runtime.c_calls, strict=True))
        or len(record.exceptions) != len(runtime.source_exceptions)
        or any(
            a is not b for a, b in zip(record.exceptions, runtime.source_exceptions, strict=True)
        )
    ):
        _runtime_error(runtime, "Original closed runtime work/return record changed")
    return runtime.record


def validate_runtime_active(claim, *, child):
    runtime = _runtime_context(claim)
    if child is not runtime.child or not runtime.active or runtime.record is not None:
        _runtime_error(runtime, "Actual active original runtime child required")
    return claim


def runtime_failed_context(claim):
    """Forensic actual partial only; no validator/retry/source permission."""
    if type(claim) is not MoleculeRuntimeClaim or claim not in _RUNTIME:
        raise MoleculeNetworkRejected(
            "Actual issued molecular runtime claim required", stage="runtime_claim"
        )
    runtime = _RUNTIME[claim]
    if runtime.record is not None or not (
        runtime.invalid or runtime.primary is not None or runtime.capture_error is not None
    ):
        raise MoleculeNetworkRejected("No failed molecular runtime prefix", stage="runtime_failure")
    return runtime
