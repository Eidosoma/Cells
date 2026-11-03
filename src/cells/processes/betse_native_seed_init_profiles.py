"""Held whole original tissue-profile mapping after actual SEED init_core.

The predecessor, coordinator and same-instance dyna routing remain explicitly
unadopted. Source compilation and metadata controls never issue a phase,
profile, material array or completed parent. Native picker/helper bodies are
reused, including their original empty, duplicate, image and RNG semantics.
"""

import ast
import builtins
import copy
import dis
import hashlib
import os
import sys
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, MappingProxyType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_phase_callbacks as callbacks
from cells.processes import betse_native_seed_init_core as previous
from cells.processes import betse_native_seed_init_profiles_source as source
from cells.processes import betse_native_single_cell_image_mask_source as image_source
from cells.processes import betse_native_tissue_configuration_source as tissue_source

LAW_ID = "betse_same_seed_core_whole_init_profiles@1"
RELEASE = "CELLS_NATIVE_SEED_INIT_PROFILES_RELEASED"
PARENT_SOURCE_SHA256 = PARENT_REVIEW_SHA256 = None
COORDINATOR_SOURCE_SHA256 = COORDINATOR_REVIEW_SHA256 = None
DYNA_SOURCE_SHA256 = DYNA_REVIEW_SHA256 = None
PROPOSED_CLAIM = "_claim_for_seed_profiles"
PROPOSED_CHECK = "_check_seed_profiles_authority"
PROPOSED_ROUTER = "_seed_init_profiles_api"
PROPOSED_PICKER_CALL = "_seed_profiles_picker_call"
CALLBACK_STATUS = "Creating tissue, surgery, and boundary profiles..."
MAPS = ("cell_target_inds", "env_target_inds", "tissue_target_inds")
IONS = ("Na", "K", "Cl", "Ca", "M", "P")
MAX_WORK = 100000
NATIVE = Path(previous._PREFIX.aliases.NATIVE)
NATIVE_PINS = {
    "betse/science/tissue/tishandler.py": (
        "057ddab87be773e5d338d0681bd503b12aee02861be0902d6ef46e1133d42f54"
    ),
    "betse/science/tissue/picker/tispickcls.py": (
        "c1c592ddc600479806da73c37ade7aecf19df0f49cd46706a74ad6bb9f1bc773"
    ),
    "betse/science/tissue/picker/tispickimage.py": (
        "75c5252998e73cce4f94d8ee03de5c206a82fae6caa1f33d0ae53260cef4a1ac"
    ),
    "betse/science/tissue/tisprofile.py": (
        "9477385aea149803d1f7f8611ce6e61550056f0f2ba9e5f91ab967ff3344eb4d"
    ),
    "betse/science/math/toolbox.py": (
        "a2a63fe1f44303fe05d2b1fbcfe9250e4575992f688cbe4cbd7fd99ef99e60a3"
    ),
    "betse/lib/numpy/nparray.py": (
        "f7c1362a5c6daf545b6a516e0ce06fe53242c13abd05a5f2520226b7dd222889"
    ),
    "betse/science/simrunner.py": previous.source.RUNNER_SHA256,
}
PICKER_FILE = "betse/science/tissue/picker/tispickcls.py"
IMAGE_FILE = "betse/science/tissue/picker/tispickimage.py"
PICKERS = ("TissuePickerAll", "TissuePickerColor", "TissuePickerIndices", "TissuePickerPercent")
HELPERS = (
    (PICKER_FILE, "TissuePickerABC", "pick_cells_and_mems"),
    *((PICKER_FILE, name, "pick_cells") for name in PICKERS),
    (IMAGE_FILE, "TissuePickerImage", "pick_cells"),
    (IMAGE_FILE, "TissuePickerImage", "get_image_mask"),
    (IMAGE_FILE, "TissuePickerImageMask", "__init__"),
    (IMAGE_FILE, "TissuePickerImageMask", "get_clipped_points_index"),
    ("betse/science/math/toolbox.py", None, "flatten"),
    ("betse/lib/numpy/nparray.py", None, "from_iterable"),
)
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_ACTIVE, _FAILED, _LOCK = [], [], RLock()
_PROOFS = (source.SeedProfiles.init_profiles, source.SeedProfilesCallSite.continue_seed)
_SOURCE_FILE, _PARENT_FILE = Path(source.__file__), Path(previous.__file__)


class ProfilesRejected(ValueError):
    def __init__(self, reason, *, stage, request=None, trial=None, partial=None):
        super().__init__(reason)
        self.stage, self.request, self.trial, self.partial = stage, request, trial, partial


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    core_owner: object
    parent_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live same-phase requests cannot be reconstructed")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    after: object
    events: tuple
    stream_before: object
    stream_after: object
    callback_completed: bool
    profile_order: tuple
    source_completed: bool
    identity: str


def _digest(value):
    return previous._digest(value)


def _node(tree, cls, name):
    rows = tree.body
    if cls is not None:
        rows = next(n for n in rows if isinstance(n, ast.ClassDef) and n.name == cls).body
    return next(n for n in rows if isinstance(n, ast.FunctionDef) and n.name == name)


def _body(node):
    return ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False)


def _trees():
    trees = {}
    for name, expected in NATIVE_PINS.items():
        path = NATIVE / name
        if (
            not previous._pin(expected)
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Exact original source required: " + name)
        trees[name] = ast.parse(path.read_bytes(), filename=str(path))
    return trees


def _source_nodes():
    trees = _trees()
    method = _node(trees["betse/science/tissue/tishandler.py"], "TissueHandler", "init_profiles")
    proof = ast.parse(_SOURCE_FILE.read_bytes())
    if _body(method) != _body(_node(proof, "SeedProfiles", "init_profiles")):
        raise ValueError("Whole original profile mapping body changed")
    seed = _node(trees["betse/science/simrunner.py"], "SimRunner", "seed")
    selected = [n for n in seed.body if n.lineno in (143, 145)]
    call = copy.deepcopy(_node(proof, "SeedProfilesCallSite", "continue_seed"))
    if len(selected) != 2 or ast.dump(ast.Module(body=selected, type_ignores=[])) != _body(call):
        raise ValueError("Exact preceding callback/profile call site changed")
    call.body, call.lineno, call.end_lineno = copy.deepcopy(selected), 143, 145
    return dict(init_profiles=method, continue_seed=call)


def _compile(node, filename):
    node = copy.deepcopy(node)
    node.decorator_list, node.returns = [], None
    for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
        arg.annotation = None
    compiled = compile(
        ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
        filename,
        "exec",
        dont_inherit=True,
    )
    return next(c for c in compiled.co_consts if type(c) is CodeType)


def _constant(value):
    if type(value) is CodeType:
        return CodeType, _code_key(value)
    if type(value) is tuple:
        return tuple, tuple(_constant(item) for item in value)
    if type(value) is frozenset:
        return frozenset, frozenset(_constant(item) for item in value)
    return callbacks.simulator._constant(value)


def _code_key(code):
    # Reuse the established complete executable header/typed-bit comparison;
    # add the compiler's immutable membership sets used by reached helpers.
    compare = FunctionType(
        callbacks.simulator._code.__code__,
        dict(vars(callbacks.simulator), _constant=_constant),
    )
    return compare(code)


def _codes():
    return {
        name: _compile(
            node,
            str(
                NATIVE
                / (
                    "betse/science/simrunner.py"
                    if name == "continue_seed"
                    else "betse/science/tissue/tishandler.py"
                )
            ),
        )
        for name, node in _source_nodes().items()
    }


def source_plan():
    nodes, trees = _source_nodes(), _trees()
    helpers = {}
    for filename, cls, name in HELPERS:
        node = _node(trees[filename], cls, name)
        helpers[(cls + "." if cls else "") + name] = dict(
            file=filename,
            first_line=node.lineno,
            last_line=node.end_lineno,
            ast_sha256=hashlib.sha256(_body(node).encode()).hexdigest(),
        )
    return dict(
        law_id=LAW_ID,
        native_pins=dict(NATIVE_PINS),
        literal_sha256=hashlib.sha256(_SOURCE_FILE.read_bytes()).hexdigest(),
        method_lines=(nodes["init_profiles"].lineno, nodes["init_profiles"].end_lineno),
        caller_lines=(143, 145),
        helpers=helpers,
        maps=MAPS,
        ion_statement_order=IONS,
        parent_source_pin=PARENT_SOURCE_SHA256,
        parent_review_pin=PARENT_REVIEW_SHA256,
        coordinator_source_pin=COORDINATOR_SOURCE_SHA256,
        coordinator_review_pin=COORDINATOR_REVIEW_SHA256,
        dyna_source_pin=DYNA_SOURCE_SHA256,
        dyna_review_pin=DYNA_REVIEW_SHA256,
        parent_hooks={
            PROPOSED_CLAIM: "(owner, *, expected, transition, entries)",
            PROPOSED_CHECK: "(transition) -> same actual retired core context",
        },
        router=PROPOSED_ROUTER,
        entries=dict(
            wrapper_guard="(transition, original, frame)",
            dispatch="(transition, original, label, delegate, actual, args, kwargs, frame)",
            picker_dispatch=(
                "(transition, original_dyna_context, label, delegate, args, kwargs, frame)"
            ),
        ),
        picker_forwarder=PROPOSED_PICKER_CALL,
        dyna_ancestry=(
            "Original _OBJECTS context and runtime_types/factories edges authenticated by "
            "factored core handoff; no stale pre-core constructor validator"
        ),
        picker_semantics="Original order/duplicates/empty selections; no normalized targets",
        image_or_percent_requires=(
            "Actual retained image-file/runtime or global-MT owner; no fixture"
        ),
        stopped_before=("redo_gj", "init_events", "INIT", "SIM"),
        original_helpers_reused=True,
        source_native_or_scientific_release=False,
    )


def _ready():
    if not all(
        previous._pin(v)
        for v in (
            PARENT_SOURCE_SHA256,
            PARENT_REVIEW_SHA256,
            COORDINATOR_SOURCE_SHA256,
            COORDINATOR_REVIEW_SHA256,
            DYNA_SOURCE_SHA256,
            DYNA_REVIEW_SHA256,
        )
    ):
        raise ProfilesRejected(
            "Reviewed core/dyna routing remains unbound", stage="unbound_contract"
        )
    if (
        _PARENT_FILE.is_symlink()
        or hashlib.sha256(_PARENT_FILE.read_bytes()).hexdigest() != PARENT_SOURCE_SHA256
    ):
        raise ProfilesRejected("Exact core producer changed", stage="producer")
    api = previous._ready()
    if hashlib.sha256(Path(api.__file__).read_bytes()).hexdigest() != COORDINATOR_SOURCE_SHA256:
        raise ProfilesRejected("Exact coordinator producer changed", stage="producer")
    dyna = api._ready().stages[2]
    if hashlib.sha256(Path(dyna.__file__).read_bytes()).hexdigest() != DYNA_SOURCE_SHA256:
        raise ProfilesRejected("Exact dyna producer changed", stage="producer")
    route = vars(api).get(PROPOSED_ROUTER)
    if (
        type(route) is not FunctionType
        or route.__globals__ is not vars(api)
        or route() is not sys.modules[__name__]
    ):
        raise ProfilesRejected("Same-instance dyna dispatch remains held", stage="dispatch_held")
    for name in (PROPOSED_CLAIM, PROPOSED_CHECK):
        fn = vars(previous).get(name)
        if type(fn) is not FunctionType or fn.__globals__ is not vars(previous):
            raise ProfilesRejected(
                "Irreversible core handoff unavailable", stage="parent_hooks_held"
            )
    picker = vars(api).get(PROPOSED_PICKER_CALL)
    if type(picker) is not FunctionType or picker.__globals__ is not vars(api):
        raise ProfilesRejected("Same-instance picker forwarding remains held", stage="picker_held")
    _source_nodes()
    return api


def request_record(value):
    return dict(
        law_id=LAW_ID, parent_identity=value.parent_identity, source_identity=value.source_identity
    )


def from_core(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise ProfilesRejected("Exact profile-source law required", stage="law")
    if _ACTIVE:
        _reject(_ACTIVE[-1], "Reentrant profile declaration")
    _ready()
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant profile declaration")
        if type(owner) is not previous.InitCoreOwner or owner in _RETIRED:
            raise ProfilesRejected("Fresh actual core child required", stage="owner")
        parent = previous._authority(owner)
        if not parent.trial.source_completed or any(
            name in vars(parent.phase.dyna) for name in MAPS
        ):
            raise ProfilesRejected("Profiles require a complete unconsumed core", stage="parent")
        request = Request(owner, parent.trial.identity, _digest(source_plan()), "")
        request = replace(request, identity=_digest(request_record(request)))
        _REQUESTS[request] = (
            parent,
            parent.trial,
            previous._snapshot(parent),
            previous._graph(parent),
        )
        return request


def _capture_error(context, error, origin, raw):
    if context.observation_error is None:
        context.observation_error = error
    context.capture_errors += ((origin, error, raw),)


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = ProfilesRejected(
            reason, stage=context.stage, request=context.request, partial=context
        )
    raise context.entry_error


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.observation_error is not None:
        raise ProfilesRejected(
            "Incomplete observation; no further source work",
            stage=context.stage,
            request=context.request,
            partial=context,
        ) from context.observation_error
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        _reject(context, "Actual active same-thread profile epoch required")
    if context.observing and (
        sys.getprofile() is not context.observer_hooks[0]
        or sys.gettrace() is not context.observer_hooks[1]
    ):
        _reject(context, "Both active observation hooks required")


def _raw(context, role, frame, value):
    # The source return witness precedes every fallible copy/encoder/callback.
    old = context.last_raw
    if old is not None and old[0] == role and old[1] is frame and old[2] is value:
        return
    context.last_raw = (role, frame, value)
    context.raw_returns.append(context.last_raw)


def _normal_return(frame):
    index = frame.f_lasti
    return index >= 0 and dis.opname[frame.f_code.co_code[index]] in (
        "RETURN_VALUE",
        "RETURN_CONST",
    )


def _bootstrap(context):
    function, code, namespace = context.checker
    if (
        context.api._independent_atoms is not function
        or function.__code__ is not code
        or function.__globals__ is not namespace
    ):
        raise ValueError("Independent metadata checker changed")
    for name, helper, expected in context.metadata_helpers:
        if globals().get(name) is not helper:
            raise ValueError("Profile metadata helper replaced: " + name)
        previous.previous._same(function(helper), expected)


def _cache(context, value):
    return previous._cache(context.parent, value)


def _values(context, *, stable=False):
    handler = vars(context.dyna)
    sim = vars(context.sim)
    return dict(
        handler={k: v for k, v in handler.items() if not stable or k not in MAPS},
        simulator={k: v for k, v in sim.items() if not stable or k != "Dm_cells"},
        membrane_material=None if stable else sim["Dm_cells"],
        parameters=vars(context.p),
        cells=vars(context.cells),
        grid=vars(context.grid),
        profile_fields=tuple(
            (name, vars(profile), vars(profile.picker)) for name, profile in context.profiles
        ),
    )


def _snapshot(context):
    return _cache(context, _values(context))


def _edges(context):
    # Existing closed graph walker retains buffer/view and container aliases.
    root = context.graph_view
    root.handler = vars(context.dyna)
    root.simulator = vars(context.sim)
    root.parameters = vars(context.p)
    root.cells = vars(context.cells)
    root.grid = vars(context.grid)
    root.profile_fields = context.profile_fields
    parent = context.parent.parent
    return previous.previous._scope(parent).graph(root, root, context.graph_tape)


def _native(function, filename, cls, name):
    # The pinned @type_check is identity. Inspecting a supplied __wrapped__
    # chain could execute foreign descriptors and would hide an outer body.
    if type(function) is not FunctionType or "__wrapped__" in vars(function):
        raise ValueError("Original undecorated native helper required")
    core, chain = function, (function,)
    node = _node(_trees()[filename], cls, name)
    module = sys.modules.get(filename[:-3].replace("/", "."))
    if (
        len(chain) != 1
        or function is not core
        or type(function) is not FunctionType
        or type(core) is not FunctionType
        or type(module) is not ModuleType
        or core.__globals__ is not vars(module)
        or core.__builtins__ is not vars(builtins)
        or core.__name__ != name
        or core.__qualname__ != ((cls + ".") if cls else "") + name
        or core.__defaults__ is not None
        or core.__kwdefaults__ is not None
        or core.__closure__ is not None
        or core.__code__.co_filename != str(NATIVE / filename)
        or _code_key(core.__code__) != _code_key(_compile(node, str(NATIVE / filename)))
    ):
        raise ValueError("Original helper code/global/builtins required: " + name)
    for name in core.__code__.co_names:
        if (
            name in vars(builtins)
            and name in core.__globals__
            and core.__globals__[name] is not vars(builtins)[name]
        ):
            raise ValueError("Original helper builtin resolution changed: " + name)
    return core, chain


@lru_cache(maxsize=96)
def _native_module_codes(filename, pin):
    path = NATIVE / filename
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
        raise ValueError("Pinned reached helper file changed: " + filename)
    result = []

    def visit(code):
        result.append((code.co_qualname, code.co_firstlineno, code))
        for value in code.co_consts:
            if type(value) is CodeType:
                visit(value)

    visit(compile(path.read_bytes(), str(path), "exec", dont_inherit=True))
    return tuple(result)


def _verify_native_helpers(functions):
    pins = dict(tissue_source.SOURCE_PINS)
    for name, value in (*image_source.NATIVE_PINS.items(), *NATIVE_PINS.items()):
        if name in pins and pins[name] != value:
            raise ValueError("Original helper pin disagreement")
        pins[name] = value
    for function in functions:
        if type(function) is not FunctionType:
            continue
        filename = function.__code__.co_filename
        if not filename.startswith(str(NATIVE) + os.sep):
            continue
        relative = str(Path(filename).relative_to(NATIVE))
        pin = pins.get(relative)
        if pin is None:
            raise ValueError("Unqualified original helper source prerequisite: " + relative)
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != pin:
            raise ValueError("Actual reached helper file changed")
        targets = [
            code
            for name, line, code in _native_module_codes(relative, pin)
            if name == function.__code__.co_qualname and line == function.__code__.co_firstlineno
        ]
        if not any(_code_key(function.__code__) == _code_key(code) for code in targets):
            raise ValueError("Reached native helper differs from original executable")
        module = sys.modules.get(relative[:-3].replace("/", "."))
        if (
            type(module) is not ModuleType
            or function.__globals__ is not vars(module)
            or function.__builtins__ is not vars(builtins)
        ):
            raise ValueError("Reached helper cached builtins changed")
        for name in function.__code__.co_names:
            if (
                name in vars(builtins)
                and name in function.__globals__
                and function.__globals__[name] is not vars(builtins)[name]
            ):
                raise ValueError("Reached native helper builtin resolution changed")


def _profile_bindings(context):
    table = vars(context.dyna)["tissue_name_to_profile"]
    if type(table) not in (dict, OrderedDict):
        raise ValueError("Original ordered tissue table required")
    profiles = tuple(table.items())
    if len(profiles) != len(context.profiles) or any(
        a != x or b is not y for (a, b), (x, y) in zip(profiles, context.profiles, strict=True)
    ):
        raise ValueError("Original profile order/object identity changed")
    origin, module = context.dyna_origin, context.dyna_module
    if (
        module._OBJECTS.get(context.dyna) is not origin
        or origin.handler is not context.dyna
        or origin.phase is not context.phase
        or origin.p is not context.p
        or origin.constructor_completed is not True
    ):
        raise ValueError("Original completed constructor context changed")
    atoms = [
        table,
        module,
        module._OBJECTS,
        origin,
        origin.objects,
        origin.runtime_types,
        origin.factories,
    ]
    for name, profile in profiles:
        cls = type(profile)
        if module._OBJECTS.get(profile) is not origin or cls is not origin.runtime_types.get(
            "TissueProfile"
        ):
            raise ValueError("Original constructor-issued TissueProfile required")
        picker = profile.picker
        picker_cls = type(picker)
        roles = [role for role, value in origin.objects if value is picker]
        if (
            len(roles) != 1
            or module._OBJECTS.get(picker) is not origin
            or picker_cls is not origin.runtime_types.get(roles[0])
        ):
            raise ValueError("Original picker registry/runtime class required")
        if roles[0] not in (*PICKERS, "TissuePickerImage"):
            raise ValueError("Unknown native picker refused")
        atoms.extend(
            (
                name,
                profile,
                cls,
                picker,
                picker_cls,
                origin.factories["TissueProfile"],
                origin.factories[roles[0]],
                *module._surface(cls),
                *module._surface(picker_cls),
            )
        )
    return tuple(atoms)


def _bindings(context):
    _bootstrap(context)
    result = [
        context.api,
        context.parent_claim,
        context.parent_check,
        context.dyna,
        context.original_wrapper,
        context.delegate,
        context.source_globals,
        context.picker_forwarder,
        *context.source_globals.values(),
        *_profile_bindings(context),
    ]
    for function in (*context.native_functions, *context.methods.values(), *context.callback_chain):
        result.extend(previous.previous._atoms(function))
    result.extend(previous._resolved_bindings(context.native_functions))
    result.extend((context.dm, context.dm.dtype, context.dm.base, context.parent.rng))
    return tuple(result)


def _same_bindings(actual, expected):
    # Shape/stride value tuples need numerical equality; all authority edges use is.
    if len(actual) != len(expected) or any(
        a is not b for a, b in zip(actual, expected, strict=True)
    ):
        raise ValueError("Retained source/profile/helper authority changed")


def _check(context, *, closed=False):
    if not closed:
        _guard(context)
    if (
        _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.core_owner) is not context
        or context.api is not _ready()
        or context.parent_check(context) is not context.parent
        or context.phase.p is not context.p
        or context.phase.sim is not context.sim
        or context.phase.cells is not context.cells
        or context.phase.dyna is not context.dyna
        or context.sim.dyna is not context.dyna
        or context.phase.callbacks is not context.callback
        or vars(context.sim)["Dm_cells"] is not context.dm
        or _digest(request_record(context.request)) != context.request.identity
        or _digest(source_plan()) != context.request.source_identity
    ):
        raise ValueError("Exact same-phase core/profile source association changed")
    _same_bindings(_bindings(context), context.bindings)
    if _cache(context, _values(context, stable=True)).identity != context.stable:
        raise ValueError("Profiles changed stores outside native target maps/Dm_cells")
    current = (
        context.dm.dtype.str,
        context.dm.shape,
        context.dm.strides,
        context.dm.flags.writeable,
        context.dm.__array_interface__["data"][0],
    )
    if current != context.dm_layout:
        raise ValueError("Core-issued material buffer/layout changed")


def _namespace(context):
    wrapper = vars(type(context.dyna)).get("init_profiles")
    if type(wrapper) is not FunctionType:
        raise ValueError("Future genuine same-instance dyna wrapper required")
    closure = dict(
        zip(
            wrapper.__code__.co_freevars,
            (c.cell_contents for c in wrapper.__closure__ or ()),
            strict=True,
        )
    )
    delegate = closure.get("delegate")
    context.dyna_module = context.api._ready().stages[2]
    context.dyna_origin = context.dyna_module._OBJECTS.get(context.dyna)
    if context.dyna_origin is None or closure.get("context") is not context.dyna_origin:
        raise ValueError("Actual original dyna constructor/wrapper context required")
    context.picker_forwarder = vars(context.api)[PROPOSED_PICKER_CALL]
    context.environment_store_line = next(
        n.lineno
        for n in ast.walk(_source_nodes()["init_profiles"])
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Name)
        and n.value.id == "ecm_targs_mem"
    )
    original, chain = _native(
        delegate, "betse/science/tissue/tishandler.py", "TissueHandler", "init_profiles"
    )
    context.original_wrapper, context.delegate = wrapper, delegate
    context.original, context.source_globals = original, original.__globals__
    context.methods = {
        name: FunctionType(code, context.source_globals, name) for name, code in _codes().items()
    }
    context.callback_chain = tuple(
        callbacks.simulator._chain(context.callback.progressed_next.__func__)
    )
    functions = list(chain)
    for filename, cls, name in HELPERS:
        module = sys.modules.get(filename[:-3].replace("/", "."))
        if module is None:
            raise ValueError("Original picker/mapping helper module unavailable")
        owner = module if cls is None else vars(module)[cls]
        function = vars(owner).get(name)
        # Inherited pick_cells_and_mems is bound once on the actual ABC.
        _, helper_chain = _native(function, filename, cls, name)
        functions.extend(helper_chain)
    context.native_functions = previous.previous.previous._native_helper_functions(tuple(functions))
    context.native_functions = tuple(dict.fromkeys((*functions, *context.native_functions)))
    _verify_native_helpers(context.native_functions)
    context.picker_delegates = {}
    for role in (*PICKERS, "TissuePickerImage"):
        native_cls = context.dyna_origin.factories.get(role)
        if native_cls is None:
            continue
        for name in ("pick_cells_and_mems", "pick_cells", "get_image_mask"):
            delegate = getattr(native_cls, name, None)
            if type(delegate) is FunctionType:
                context.picker_delegates[role + "." + name] = delegate
    context.pick_code = _compile(
        _node(_trees()[PICKER_FILE], "TissuePickerABC", "pick_cells_and_mems"),
        str(NATIVE / PICKER_FILE),
    )
    context.pick_code = next(
        fn.__code__
        for fn in context.native_functions
        if fn.__code__.co_name == "pick_cells_and_mems"
        and _code_key(fn.__code__) == _code_key(context.pick_code)
    )
    context.allowed_codes = frozenset(
        code
        for fn in (
            *context.native_functions,
            *context.callback_chain,
            *context.methods.values(),
            wrapper,
        )
        if type(fn) is FunctionType
        for code in previous.previous.previous.previous._code_tree(fn.__code__)
    )


def _wrapper_guard(context, original, frame):
    _guard(context)
    if (
        original is not context.dyna_origin
        or frame.f_code is not context.original_wrapper.__code__
        or frame.f_back is not context.caller_frame
        or frame.f_locals.get("self") is not context.dyna
        or context.wrapper_frame is not None
        or not context.callback_completed
    ):
        _reject(context, "Single same-instance profile wrapper after callback required")
    context.wrapper_frame = frame
    _check(context)


def _dispatch(context, original, label, delegate, actual, args, kwargs, frame):
    _guard(context)
    if (
        original is not context.dyna_origin
        or label != "init_profiles"
        or delegate is not context.delegate
        or actual is not context.dyna
        or type(args) is not tuple
        or len(args) != 1
        or args[0] is not context.phase
        or kwargs
        or frame.f_back is not context.wrapper_frame
        or context.dispatch_frame is not None
    ):
        _reject(context, "Exact native profile method/phase dispatch required")
    _check(context)
    context.dispatch_frame = frame
    return context.methods["init_profiles"](context.dyna, context.phase)


def _picker_dispatch(context, original, label, delegate, args, kwargs, frame):
    _guard(context)
    if (
        original is not context.dyna_origin
        or context.picker_delegates.get(label) is not delegate
        or frame is not sys._getframe(1)
        or frame.f_code is not context.picker_forwarder.__code__
        or type(args) is not tuple
        or not args
        or context.dyna_module._OBJECTS.get(args[0]) is not original
    ):
        _reject(context, "Exact original constructor-issued picker dispatch required")
    role, name = label.split(".")
    if type(args[0]) is not original.runtime_types[role]:
        _reject(context, "Actual picker runtime class changed")
    cells = args[1] if len(args) > 1 else kwargs.get("cells")
    p = args[2] if len(args) > 2 else kwargs.get("p")
    if cells is not context.cells or (name != "get_image_mask" and p is not context.p):
        _reject(context, "Actual same-phase picker arguments required")
    _check(context)
    context.helper_frames.append(sys._getframe())
    try:
        return delegate(*args, **kwargs)
    finally:
        context.helper_frames.pop()


def _observe(context, frame, event, arg):
    if event not in ("call", "return", "exception", "line"):
        return
    code = frame.f_code
    is_body = code in (
        context.methods["init_profiles"].__code__,
        context.methods["continue_seed"].__code__,
    )
    is_callback = code is context.callback_chain[0].__code__
    native = code.co_filename.startswith(str(NATIVE) + os.sep)
    if not (native or is_body or is_callback):
        return
    if event == "return" and (native or is_body or is_callback):
        _raw(context, code.co_qualname, frame, arg)
        context.events.append((code.co_qualname, arg))
        if code is context.pick_code and _normal_return(frame):
            body = frame.f_back
            if (
                not context.helper_frames
                or body is not context.helper_frames[-1]
                or type(arg) is not tuple
                or len(arg) != 2
            ):
                _reject(context, "Original picker return requires actual profile body association")
            fields = context.body_frame.f_locals
            profile = fields["tissue_profile"]
            if frame.f_locals.get("self") is not profile.picker:
                _reject(context, "Actual profile/picker owner changed")
            context.picks.append((fields["tissue_name"], profile, profile.picker, arg[0], arg[1]))
    if event == "exception" and (is_body or is_callback):
        context.source_exceptions.append((frame, arg[1]))
        if (
            context.primary is None
            and context.observation_error is None
            and context.entry_error is None
        ):
            context.primary = arg[1]
    if event == "call":
        _guard(context)
        if len(context.work) >= MAX_WORK:
            _reject(context, "Declared profile work bound exhausted")
        if native:
            if code not in context.allowed_codes:
                _reject(context, "Unknown native helper or later redo_gj entry")
            context.work.append((code.co_filename, code.co_qualname, frame))
        if code is context.methods["continue_seed"].__code__:
            if context.caller_frame is not None or frame.f_back is not context.driver_frame:
                _reject(context, "Single original callback/profile call-site entry required")
            context.caller_frame = frame
        elif code is context.methods["init_profiles"].__code__:
            if context.body_frame is not None or frame.f_back is not context.dispatch_frame:
                _reject(context, "Profile body requires exact original dyna dispatch")
            context.body_frame = frame
        if is_callback:
            if context.callback_entered or frame.f_back is not context.caller_frame:
                _reject(context, "Exact original preceding callback order required")
            context.callback_entered = True
        if is_body or is_callback:
            _check(context)
        else:
            _same_bindings(_bindings(context), context.bindings)
    if is_body:
        if event == "line":
            _guard(context)
            _same_bindings(_bindings(context), context.bindings)
            if (
                code is context.methods["init_profiles"].__code__
                and frame.f_lineno == context.environment_store_line
            ):
                fields = frame.f_locals
                context.environment_returns.append(
                    (
                        fields["tissue_name"],
                        fields["tissue_profile"],
                        fields["ecm_targs_mem"],
                    )
                )
        context.locals[code.co_name] = dict(frame.f_locals)
        if event == "return" and code is context.methods["init_profiles"].__code__:
            context.body_returned = True
            context.body_return = arg
    if is_callback and event == "return":
        context.callback_returned = True
        context.callback_completed = not any(f.f_code is code for f, _ in context.source_exceptions)


@contextmanager
def _account(context):
    old_profile, old_trace = context.required_hooks
    previous_locals = {}

    def profile(frame, event, arg):
        if old_profile is not None:
            try:
                old_profile(frame, event, arg)
            except BaseException as error:
                _capture_error(context, error, "inherited_profile", (frame, event, arg))
                if event not in ("return", "c_return", "c_exception"):
                    raise
        if (
            sys.getprofile() is not context.observer_hooks[0]
            or sys.gettrace() is not context.observer_hooks[1]
        ):
            error = ValueError("Inherited profile callback changed an active hook")
            _capture_error(context, error, "hook_identity", (frame, event, arg))
            if context.primary is None or event not in ("return", "c_return", "c_exception"):
                raise error

    def trace(frame, event, arg):
        # Our direct error/return witness is installed before inherited hooks.
        known = frame.f_code in context.source_codes or frame.f_code in context.allowed_codes
        if event == "exception" and known:
            context.pending_errors[id(frame)] = arg[1]
            if frame.f_code in context.source_codes and context.primary is None:
                context.primary = arg[1]
        if event == "return" and known:
            _raw(context, frame.f_code.co_qualname, frame, arg)
            if not _normal_return(frame) and context.primary is None:
                context.primary = context.pending_errors.get(id(frame))
        prior = old_trace if event == "call" else previous_locals.get(id(frame))
        try:
            if prior is not None:
                try:
                    local = prior(frame, event, arg)
                    if callable(local):
                        previous_locals[id(frame)] = local
                except BaseException as error:
                    _capture_error(context, error, "inherited_trace", (frame, event, arg))
                    if event != "return" or context.primary is None:
                        raise
            try:
                _observe(context, frame, event, arg)
            except BaseException as error:
                if error is not context.entry_error:
                    _capture_error(context, error, "observer", (frame, event, arg))
                if event != "return" or context.primary is None:
                    raise
        finally:
            if event == "return":
                previous_locals.pop(id(frame), None)
                context.pending_errors.pop(id(frame), None)
        return trace

    context.observer_hooks = (profile, trace)
    try:
        context.restore_setters[0](profile)
        context.restore_setters[1](trace)
        context.observing = True
        yield
    finally:
        context.observing = False
        _restore(context)


def _restore(context):
    return previous._BASE._recover(context)


def _complete(context):
    if (
        not context.callback_completed
        or not context.body_returned
        or context.body_return is not None
        or context.primary is not None
        or context.invalid
        or context.observation_error is not None
        or context.entry_error is not None
        or context.cleanup_errors
    ):
        raise ValueError("Whole original callback/profile completion required")
    if tuple(name for name in vars(context.dyna) if name not in context.original_names) != MAPS:
        raise ValueError("Exact three original target-map stores required")
    names = tuple(name for name, _ in context.profiles)
    if (
        tuple(context.dyna.cell_target_inds) != names
        or tuple(context.dyna.tissue_target_inds) != names
    ):
        raise ValueError("Every original profile/empty result must retain its order")
    if len(context.picks) != len(context.profiles):
        raise ValueError("Every original picker return must be retained once")
    environment = []
    for (name, profile), (picked_name, actual_profile, picker, cells, mems) in zip(
        context.profiles, context.picks, strict=True
    ):
        if (
            name != picked_name
            or actual_profile is not profile
            or picker is not profile.picker
            or context.dyna.cell_target_inds[name] is not cells
            or context.dyna.tissue_target_inds[name] is not mems
        ):
            raise ValueError("Native target stores must retain the exact actual picker returns")
        if len(cells) and context.p.is_ecm:
            environment.append(name)
    if tuple(context.dyna.env_target_inds) != tuple(environment):
        raise ValueError("Environment maps require the original nonempty/ECM branches")
    if tuple(row[0] for row in context.environment_returns) != tuple(environment):
        raise ValueError("Every original environment-target list must be retained")
    profiles = dict(context.profiles)
    for name, profile, targets in context.environment_returns:
        if profile is not profiles[name] or context.dyna.env_target_inds[name] is not targets:
            raise ValueError("Environment map lost its actual source-produced list")


def trial_record(value):
    return dict(
        request_identity=value.request_identity,
        parent_identity=value.parent_identity,
        before=value.before.identity,
        after=value.after.identity,
        stream_before=value.stream_before.identity,
        stream_after=value.stream_after.identity,
        callback_completed=value.callback_completed,
        profile_order=value.profile_order,
        events=tuple((name, id(raw)) for name, raw in value.events),
        source_completed=value.source_completed,
    )


def _failure(context, primary):
    context.invalid = True
    selected = context.primary if context.primary is not None else primary
    context.failure_error = selected
    _FAILED.append(context)
    if selected is not primary:
        _capture_error(context, primary, "interrupted_primary", selected)
    # Retain exact live roots even when the bounded observation is unavailable.
    context.partial = dict(
        phase=context.phase,
        dyna=context.dyna,
        simulator=context.sim,
        parameters=context.p,
        cells=context.cells,
        raw_returns=context.raw_returns,
        source_exceptions=context.source_exceptions,
        locals=context.locals,
        work=context.work,
        primary=selected,
        capture_errors=context.capture_errors,
    )
    try:
        selected.seed_init_profiles_partial = context
    except BaseException as error:
        _capture_error(context, error, "exception_attachment", selected)
    raise selected


def _context(request, refs, api):
    parent = refs[0]
    phase = parent.phase
    dyna, sim = phase.dyna, phase.sim
    dm = vars(sim)["Dm_cells"]
    return SimpleNamespace(
        request=request,
        refs=refs,
        parent=parent,
        api=api,
        phase=phase,
        dyna=dyna,
        sim=sim,
        p=phase.p,
        cells=phase.cells,
        grid=parent.grid,
        callback=phase.callbacks,
        assembly=parent.assembly,
        dm=dm,
        dm_layout=(
            dm.dtype.str,
            dm.shape,
            dm.strides,
            dm.flags.writeable,
            dm.__array_interface__["data"][0],
        ),
        profiles=tuple(dyna.tissue_name_to_profile.items()),
        original_names=tuple(vars(dyna)),
        active=True,
        invalid=False,
        validating=False,
        observing=False,
        thread=get_ident(),
        stage="claim",
        trial=None,
        before=None,
        after=None,
        primary=None,
        entry_error=None,
        observation_error=None,
        capture_errors=(),
        cleanup_errors=(),
        raw_returns=[],
        picks=[],
        helper_frames=[],
        environment_returns=[],
        last_raw=None,
        source_exceptions=[],
        pending_errors={},
        work=[],
        events=[],
        locals={},
        callback_entered=False,
        callback_returned=False,
        callback_completed=False,
        body_returned=False,
        body_return=None,
        caller_frame=None,
        wrapper_frame=None,
        dispatch_frame=None,
        body_frame=None,
        required_hooks=(sys.getprofile(), sys.gettrace()),
        restore_setters=(sys.setprofile, sys.settrace),
        restore_getters=(sys.getprofile, sys.gettrace),
        graph_tape=SimpleNamespace(rng=parent.rng, events=(), draws=(), locals={}),
        graph_view=SimpleNamespace(),
        profile_fields=tuple(
            (name, vars(profile), vars(profile.picker))
            for name, profile in dyna.tissue_name_to_profile.items()
        ),
    )


def prepare(request, *, enabled=False):
    if _ACTIVE:
        _reject(_ACTIVE[-1], "Reentrant profile attempt")
    api = _ready()
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise ProfilesRejected("Actual native profile mapping remains held", stage="release")
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant profile attempt")
        if type(request) is not Request or request not in _REQUESTS:
            raise ProfilesRejected("Actual process-local core request required", stage="request")
        if request in _CONSUMED or request.core_owner in _RETIRED:
            raise ProfilesRejected("Core epoch already consumed", stage="consumed")
        refs = _REQUESTS[request]
        parent = previous._authority(request.core_owner)
        if (
            parent is not refs[0]
            or parent.trial is not refs[1]
            or previous._snapshot(parent).identity != refs[2].identity
        ):
            raise ProfilesRejected("Original completed core changed", stage="parent")
        previous.previous._same(previous._graph(parent)[0], refs[3][0])
        if previous._graph(parent)[1] != refs[3][1]:
            raise ProfilesRejected("Original completed core graph changed", stage="parent")
        context = _context(request, refs, api)
        context.driver_frame = sys._getframe()
        _CONSUMED[request] = _RETIRED[request.core_owner] = context
        _ACTIVE.append(context)
        try:
            context.parent_claim = vars(previous)[PROPOSED_CLAIM]
            context.parent_check = vars(previous)[PROPOSED_CHECK]
            checker = context.api._independent_atoms
            context.checker = (checker, checker.__code__, checker.__globals__)
            context.metadata_helpers = tuple(
                (name, fn, checker(fn))
                for name, fn in globals().items()
                if type(fn) is FunctionType and fn.__globals__ is globals()
            )
            context.entries = MappingProxyType(
                dict(
                    wrapper_guard=_wrapper_guard,
                    dispatch=_dispatch,
                    picker_dispatch=_picker_dispatch,
                )
            )
            context.parent_claim(
                request.core_owner, expected=refs[1], transition=context, entries=context.entries
            )
            _namespace(context)
            context.source_codes = frozenset(
                fn.__code__ for fn in (*context.methods.values(), *context.callback_chain)
            )
            context.caller = SimpleNamespace(_callbacks=context.callback)
            context.bindings = _bindings(context)
            context.stable = _cache(context, _values(context, stable=True)).identity
            context.before = _snapshot(context)
            context.stream_before = previous.previous._rng(parent.parent)
            _check(context)
            with _account(context):
                context.stage = "original_callback_then_profiles"
                context.methods["continue_seed"](context.caller, context.phase)
            _complete(context)
            _check(context)
            context.after = _snapshot(context)
            context.graph = _edges(context)
            context.stream_after = previous.previous._rng(parent.parent)
            trial = Trial(
                request.identity,
                request.parent_identity,
                context.before,
                context.after,
                tuple(context.events),
                context.stream_before,
                context.stream_after,
                context.callback_completed,
                tuple(n for n, _ in context.profiles),
                True,
                "",
            )
            context.trial = replace(trial, identity=_digest(trial_record(trial)))
            if not _restore(context):
                raise ValueError("Both original hooks must be restored before publication")
            context.active = False
            owner = object.__new__(ProfilesOwner)
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            _failure(context, error)
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True


class ProfilesOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use actual complete-core profile continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live profile owners cannot be restored or supplied")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not ProfilesOwner or owner not in _ISSUED:
        raise ProfilesRejected("Actual issued profile owner required", stage="owner")
    context = _ISSUED[owner]
    if context.active or context.invalid or context.validating:
        raise ProfilesRejected("Profile epoch unavailable", stage="owner")
    context.validating = True
    try:
        _check(context, closed=True)
        _complete(context)
        graph = _edges(context)
        previous.previous._same(graph[0], context.graph[0])
        if (
            graph[1] != context.graph[1]
            or _snapshot(context).identity != context.after.identity
            or previous.previous._rng(context.parent.parent).identity
            != context.stream_after.identity
            or context.trial.identity != _digest(trial_record(context.trial))
        ):
            raise ValueError("Actual profile/material/alias/RNG graph changed")
    except BaseException as error:
        _failure(context, error)
    finally:
        context.validating = False
    return context


def require_redo_gj(owner):
    context = _authority(owner)
    raise ProfilesRejected(
        "Later redo_gj/INIT requires separate actual authority",
        stage="redo_gj_held",
        request=context.request,
        trial=context.trial,
    )
