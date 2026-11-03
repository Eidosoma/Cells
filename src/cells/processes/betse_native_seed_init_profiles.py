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
from types import (
    CodeType,
    FunctionType,
    MappingProxyType,
    MethodType,
    ModuleType,
    SimpleNamespace,
)
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_yaml_prefix as files
from cells.processes import betse_native_phase_callbacks as callbacks
from cells.processes import betse_native_seed_init_core as previous
from cells.processes import betse_native_seed_init_profiles_source as source
from cells.processes import betse_native_single_cell_image_mask_source as image_source
from cells.processes import betse_native_tissue_configuration_source as tissue_source

LAW_ID = "betse_same_seed_core_whole_init_profiles@1"
RELEASE = "CELLS_NATIVE_SEED_INIT_PROFILES_RELEASED"
PARENT_SOURCE_SHA256 = "96ebd0104a4a5ba2a05f3ab959c25a3046ef6e1019f08e4e9f7fef2240e8e419"
PARENT_REVIEW_SHA256 = "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d"
COORDINATOR_SOURCE_SHA256 = "025d28d2a5917f053ab7a2db1121c103d479ac3238e5ebd7b4b2df149b426127"
COORDINATOR_REVIEW_SHA256 = "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d"
DYNA_SOURCE_SHA256 = "4a930b68f6ce4f0140a96d00c03400e7e176e3639ef94cfdd160164af477a033"
DYNA_REVIEW_SHA256 = "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d"
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
_FORWARDED = WeakKeyDictionary()
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
    image_inputs: tuple
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
    work: tuple
    rng_events: tuple
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
        percent_native_effect=(
            "cell_i_copy = cells.cell_i[:] may be a view; retain native shuffle mutation of "
            "the same cell_i buffer and original All-picker aliases, never insert a copy"
        ),
        image_or_percent_requires=(
            "Actual retained image-file/runtime or global-MT owner; no fixture"
        ),
        image_authority=(
            "Optional explicit issued FileInput tuple bound to every actually retained "
            "image-picker filename; file bytes alone grant no geometry or phase authority"
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
    dyna = api._dependencies().stages[2]
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
        law_id=LAW_ID,
        parent_identity=value.parent_identity,
        source_identity=value.source_identity,
        image_inputs=tuple(item.identity for item in value.image_inputs),
    )


def _image_authority(inputs, profiles):
    if type(inputs) is not tuple or len(inputs) > 64:
        raise ValueError("Bounded explicit immutable image-file tuple required")
    actual = []
    for value in inputs:
        files._verify_file(value)
        if value.filename in actual:
            raise ValueError("Duplicate image-file authority")
        actual.append(value.filename)
    wanted = []
    for role, picker in profiles:
        if role == "TissuePickerImage":
            wanted.append(picker.filename)
    if set(actual) != set(wanted):
        raise ValueError("Missing or foreign source-selected image-file authority")


def from_core(owner, *, law_id, image_inputs=()):
    if type(law_id) is not str or law_id != LAW_ID:
        raise ProfilesRejected("Exact profile-source law required", stage="law")
    if _ACTIVE:
        _reject(_ACTIVE[-1], "Reentrant profile declaration")
    api = _ready()
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
        dyna_module = api._dependencies().stages[2]
        proof = SimpleNamespace(
            dyna=parent.phase.dyna,
            phase=parent.phase,
            p=parent.p,
            dyna_module=dyna_module,
            dyna_origin=dyna_module._OBJECTS.get(parent.phase.dyna),
            profiles=tuple(parent.phase.dyna.tissue_name_to_profile.items()),
        )
        if proof.dyna_origin is None:
            raise ProfilesRejected(
                "Original dyna constructor ancestry unavailable", stage="dyna_ancestry"
            )
        _profile_bindings(proof)
        _image_authority(image_inputs, _selected_pickers(proof))
        request = Request(owner, parent.trial.identity, _digest(source_plan()), image_inputs, "")
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
    if getattr(context, "inherited_hook_active", False):
        _reject(context, "Inherited observer may not enter a source continuation")
    if (
        sys.call_tracing is not context.call_tracing
        or sys.getprofile is not context.restore_getters[0]
        or sys.gettrace is not context.restore_getters[1]
        or sys.setprofile is not context.restore_setters[0]
        or sys.settrace is not context.restore_setters[1]
    ):
        _reject(context, "Original observer/cleanup builtins changed")
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
    old = context.last_raw_history
    context.last_raw = (role, frame, value)
    if old is not None and old[0] == role and old[1] is frame and old[2] is value:
        return
    # A failed history append remains an incomplete attempt, never an implicit
    # retry by the second observation layer. last_raw still retains the roots.
    context.last_raw_history = context.last_raw
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
        cells={
            k: v
            for k, v in vars(context.cells).items()
            if not stable or not context.percent_declared or k != "cell_i"
        },
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
    root.percent_views = context.percent_views
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


def _selected_pickers(context):
    selected = []
    for _, profile in context.profiles:
        picker = profile.picker
        roles = [role for role, item in context.dyna_origin.objects if item is picker]
        if len(roles) != 1:
            raise ValueError("Exact actual selected picker issuance required")
        selected.append((roles[0], picker))
    return tuple(selected)


def _bindings(context):
    _bootstrap(context)
    result = [
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        _FORWARDED,
        _ACTIVE,
        _LOCK,
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
        context.call_tracing,
        context.required_hooks,
        *context.required_hooks,
        context.restore_getters,
        *context.restore_getters,
        context.restore_setters,
        *context.restore_setters,
    ]
    for function in (*context.native_functions, *context.methods.values(), *context.callback_chain):
        result.extend(previous.previous._atoms(function))
    result.extend(previous._resolved_bindings(context.native_functions))
    result.extend((context.dm, context.dm.dtype, context.dm.base, context.parent.rng))
    if context.percent_declared:
        random = context.parent.numpy.random
        result.extend(
            (
                random,
                random.shuffle,
                random.mtrand,
                random.mtrand._rand,
                type(random.mtrand._rand),
                vars(type(random.mtrand._rand))["shuffle"],
            )
        )
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
    _check_fields(context)
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
    _image_authority(context.request.image_inputs, _selected_pickers(context))
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
    if vars(context.cells)["cell_i"] is not context.cell_i:
        raise ValueError("Native percent picker may not replace the issued cell_i owner")
    if not context.percent_active and _cell_epoch(context) != context.cell_epoch:
        raise ValueError("Cell index state changed outside the actual native percent call")
    if (
        not context.percent_active
        and previous.previous._rng(context.parent.parent).identity != context.expected_rng.identity
    ):
        raise ValueError("Global MT changed outside the original percent source call")


def _cell_epoch(context):
    return previous._CORE.caches.snapshot(context.cell_i).identity


def _accept_percent_view(context, view):
    cell_i = context.cell_i
    np = context.parent.numpy
    if (
        not context.percent_declared
        or not context.percent_active
        or type(view) is not np.ndarray
        or view is cell_i
        or view.dtype != cell_i.dtype
        or view.shape != cell_i.shape
        or view.strides != cell_i.strides
        or view.__array_interface__["data"][0] != cell_i.__array_interface__["data"][0]
    ):
        raise ValueError("Exact original percent slice/view association required")

    def root(value):
        for _ in range(16):
            if type(value.base) is not np.ndarray:
                return value
            value = value.base
        raise ValueError("Bounded original array base chain required")

    if root(view) is not root(cell_i) or (cell_i.size and not np.shares_memory(view, cell_i)):
        raise ValueError("Original percent view must retain the same actual storage root")


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
    context.dyna_module = context.api._dependencies().stages[2]
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
    if context.source_globals["np"] is not context.parent.numpy:
        raise ValueError("Actual core/profile NumPy owner must be identical")
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
    context.percent_code = next(
        fn.__code__
        for fn in context.native_functions
        if fn.__qualname__ == "TissuePickerPercent.pick_cells"
    )
    used = tuple(profile.picker for _, profile in context.profiles)
    context.percent_declared = any(
        role == "TissuePickerPercent" and any(value is picker for picker in used)
        for role, value in context.dyna_origin.objects
    )
    context.shuffle = None
    context.shuffle_code = None
    if context.percent_declared:
        random = context.parent.numpy.random
        context.shuffle = random.shuffle
        if (
            type(context.shuffle) is not MethodType
            or context.shuffle.__self__ is not context.parent.rng
            or context.shuffle.__name__ != "shuffle"
            or context.shuffle.__func__ is not vars(type(context.parent.rng))["shuffle"]
            or type(context.parent.rng) is not vars(random.mtrand)["RandomState"]
            or random.mtrand._rand is not context.parent.rng
            or vars(random.mtrand).get("shuffle") is not context.shuffle
        ):
            raise ValueError("Actual source-owned global NumPy shuffle required")
        context.shuffle_code = context.shuffle.__func__.__code__
    context.cell_epoch = _cell_epoch(context)
    _image_authority(context.request.image_inputs, _selected_pickers(context))
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
        or frame is not sys._getframe(1)
        or frame.f_back is not context.wrapper_frame
        or context.forwarding_frame is not None
        or context.dispatch_frame is not None
    ):
        _reject(context, "Exact native profile method/phase dispatch required")
    _check(context)
    context.forwarding_frame = frame
    context.dispatch_frame = sys._getframe()
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
    percent = label == "TissuePickerPercent.pick_cells"
    if percent:
        if context.percent_active:
            _reject(context, "Reentrant percent picker mutation")
        context.percent_active = True
        before = len(context.percent_views)
    context.helper_frames.append(sys._getframe())
    try:
        returned = delegate(*args, **kwargs)
        if percent:
            if len(context.percent_views) != before + 1:
                _reject(context, "Exact actual percent source view witness required")
            picker, view = context.percent_views[-1]
            if picker is not args[0]:
                _reject(context, "Percent view lost its actual picker owner")
            _accept_percent_view(context, view)
            context.cell_epoch = _cell_epoch(context)
            context.expected_rng = previous.previous._rng(context.parent.parent)
        return returned
    finally:
        context.helper_frames.pop()
        if percent:
            context.percent_active = False


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
        if code is context.percent_code and _normal_return(frame):
            fields = frame.f_locals
            view = fields["cell_i_copy"]
            _accept_percent_view(context, view)
            context.percent_views.append((fields["self"], view))
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
            if (
                context.body_frame is not None
                or frame.f_back is not context.dispatch_frame
                or context.dispatch_frame.f_back is not context.forwarding_frame
                or context.forwarding_frame.f_back is not context.wrapper_frame
            ):
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
        if context.inherited_hook_active:
            if event == "call" and (
                frame.f_code in context.source_codes
                or frame.f_code in context.allowed_codes
                or frame.f_code.co_filename.startswith(str(NATIVE) + os.sep)
            ):
                _reject(context, "Inherited observer attempted a raw native/source entry")
            return
        if (
            context.percent_active
            and (arg is context.shuffle or frame.f_code is context.shuffle_code)
            and event in ("call", "return", "c_call", "c_return", "c_exception")
        ):
            context.rng_events.append((event, frame, context.shuffle))
        if old_profile is not None:
            try:
                _inherited_observer(context, old_profile, frame, event, arg)
            except BaseException as error:
                _capture_error(context, error, "inherited_profile", (frame, event, arg))
                if event not in ("return", "c_return", "c_exception"):
                    raise
        if context.observing and (
            sys.getprofile() is not context.observer_hooks[0]
            or sys.gettrace() is not context.observer_hooks[1]
        ):
            first = context.observation_error
            error = ValueError("Inherited profile callback changed an active hook")
            _capture_error(context, error, "hook_identity", (frame, event, arg))
            if context.primary is None or event not in ("return", "c_return", "c_exception"):
                raise first if first is not None else error

    def trace(frame, event, arg):
        if context.inherited_hook_active:
            if event == "call" and (
                frame.f_code in context.source_codes
                or frame.f_code in context.allowed_codes
                or frame.f_code.co_filename.startswith(str(NATIVE) + os.sep)
            ):
                _reject(context, "Inherited observer attempted a raw native/source entry")
            return trace
        # Our direct error/return witness is installed before inherited hooks.
        known = frame.f_code in context.source_codes or frame.f_code in context.allowed_codes
        if event == "exception" and known:
            context.pending_errors[id(frame)] = arg[1]
            if frame.f_code in context.source_codes and context.primary is None:
                context.primary = arg[1]
        if event == "return" and known:
            # The helper unwind and live return roots precede every fallible
            # history append, including helpers outside source_codes.
            context.last_raw = (frame.f_code.co_qualname, frame, arg)
            if not _normal_return(frame) and context.primary is None:
                context.primary = context.pending_errors.get(id(frame))
            try:
                _raw(context, frame.f_code.co_qualname, frame, arg)
            except BaseException as error:
                _capture_error(context, error, "raw_return_history", context.last_raw)
                if context.primary is None:
                    raise
        prior = old_trace if event == "call" else previous_locals.get(id(frame))
        try:
            if prior is not None:
                try:
                    local = _inherited_observer(context, prior, frame, event, arg)
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
        if (
            context.restore_getters[0]() is not profile
            or context.restore_getters[1]() is not trace
            or context.observation_error is not None
        ):
            raise ProfilesRejected(
                "Both original hooks must be installed before source work",
                stage="observation_setup",
            )
        context.observing = True
        yield
    except BaseException as error:
        selected = context.primary if context.primary is not None else context.entry_error
        if selected is not None and selected is not error:
            _capture_error(context, error, "interrupted_primary", selected)
            raise selected  # noqa: B904 - preserve the exact original exception/cause.
        raise
    finally:
        context.observing = False
        context.hooks_safe = False
        try:
            if not _restore(context):
                raise ValueError("Original restoration did not recover both hooks")
        except BaseException as error:
            context.cleanup_errors += (("restore_entry_or_return", error, None),)
        # A prior hook may reject _restore itself before its body can recover.
        # These independent caller-boundary attempts must still reach BOTH.
        for index in (1, 0):
            try:
                context.restore_setters[index](context.required_hooks[index])
            except BaseException as error:
                context.cleanup_errors += (("caller_restore", error, index),)
        samples = []
        for order in ((0, 1), (1, 0)):
            pair = [None, None]
            for index in order:
                try:
                    pair[index] = context.restore_getters[index]()
                except BaseException as error:
                    context.cleanup_errors += (("caller_sample", error, index),)
            samples.append(tuple(pair))
        context.final_hook_samples = tuple(samples)
        context.hooks_safe = all(
            pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
            for pair in samples
        )
        if not context.hooks_safe:
            context.invalid = True
        if context.cleanup_errors and context.observation_error is None:
            context.observation_error = context.cleanup_errors[0][1]


def _observer_epoch(context):
    # Only the newly mutable source buffers/maps need per-callback content
    # witnesses. Full immutable ancestry is still checked by the parent lease.
    values = dict(
        Dm_cells=context.dm,
        cell_i=context.cell_i,
        maps={name: vars(context.dyna)[name] for name in MAPS if name in vars(context.dyna)},
    )
    metadata = tuple(
        id(getattr(context, name))
        for name in (
            "request",
            "refs",
            "parent",
            "api",
            "phase",
            "p",
            "cells",
            "sim",
            "dyna",
            "dm",
            "cell_i",
            "expected_rng",
            "percent_active",
            "active",
            "invalid",
            "thread",
            "entries",
            "parent_claim",
            "parent_check",
            "call_tracing",
        )
    )
    maps = tuple(
        (name, id(vars(context.dyna)[name])) for name in MAPS if name in vars(context.dyna)
    )
    return (
        _cache(context, values).identity,
        previous.previous._rng(context.parent.parent).identity,
        metadata,
        maps,
    )


def _observer_delegate(observer, frame, event, arg):
    return observer(frame, event, arg)


def _inherited_observer(context, observer, frame, event, arg):
    if context.inherited_hook_active:
        _reject(context, "Reentrant inherited source observer")
    before = _observer_epoch(context)
    context.inherited_hook_active = True
    primary = None
    try:
        return context.call_tracing(_observer_delegate, (observer, frame, event, arg))
    except BaseException as error:
        primary = error
        raise
    finally:
        context.inherited_hook_active = False
        capture = None
        try:
            if _observer_epoch(context) != before:
                raise ValueError("Inherited observer changed material/maps/indices/MT or authority")
        except BaseException as error:
            capture = error
            context.last_observer_capture = (error, frame, event, arg)
            try:
                _capture_error(context, error, "inherited_mutation_or_capture", (frame, event, arg))
            except BaseException as secondary:
                context.observer_capture_error = (secondary, context.last_observer_capture)
        if context.entry_error is not None:
            raise context.entry_error
        if primary is None and context.primary is None and capture is not None:
            raise capture


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
        work=tuple((file, name, id(frame)) for file, name, frame in value.work),
        rng_events=tuple(
            (event, id(frame), id(delegate)) for event, frame, delegate in value.rng_events
        ),
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
        last_raw=context.last_raw,
        last_raw_history=context.last_raw_history,
        source_exceptions=context.source_exceptions,
        locals=context.locals,
        work=context.work,
        primary=selected,
        capture_errors=context.capture_errors,
        cleanup_errors=context.cleanup_errors,
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
        inherited_hook_active=False,
        call_tracing=sys.call_tracing,
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
        last_raw_history=None,
        source_exceptions=[],
        pending_errors={},
        percent_declared=False,
        percent_active=False,
        percent_views=[],
        rng_events=[],
        cell_i=phase.cells.cell_i,
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
        forwarding_frame=None,
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
            context.expected_rng = context.stream_before
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
                tuple(context.work),
                tuple(context.rng_events),
                context.stream_before,
                context.stream_after,
                context.callback_completed,
                tuple(n for n, _ in context.profiles),
                True,
                "",
            )
            context.trial = replace(trial, identity=_digest(trial_record(trial)))
            # Recheck after all fallible completion/graph capture work. As at
            # the observer boundary, helper-entry rejection cannot prevent
            # independent restoration or mask an earlier source exception.
            try:
                if not _restore(context):
                    raise ValueError("Original restoration did not recover both hooks")
            except BaseException as error:
                context.cleanup_errors += (("publication_restore_entry_or_return", error, None),)
            for index in (1, 0):
                try:
                    context.restore_setters[index](context.required_hooks[index])
                except BaseException as error:
                    context.cleanup_errors += (("publication_restore", error, index),)
            samples = []
            for order in ((0, 1), (1, 0)):
                pair = [None, None]
                for index in order:
                    try:
                        pair[index] = context.restore_getters[index]()
                    except BaseException as error:
                        context.cleanup_errors += (("publication_sample", error, index),)
                samples.append(tuple(pair))
            context.final_hook_samples = tuple(samples)
            context.hooks_safe = all(
                pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
                for pair in samples
            )
            if not context.hooks_safe or context.cleanup_errors:
                raise ValueError("Both original hooks must be restored before publication")
            context.active = False
            owner = object.__new__(ProfilesOwner)
            context.owner = owner
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


def _check_fields(context):
    """Only the actual profile stage may append the three original handler maps."""
    _bootstrap(context)
    if (
        type(context.request) is not Request
        or _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.core_owner) is not context
        or context.invalid
        or context.thread != get_ident()
        or context.parent is not context.refs[0]
        or context.parent.trial is not context.refs[1]
        or context.phase is not context.parent.phase
        or context.phase.dyna is not context.dyna
        or context.phase.sim is not context.sim
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
    ):
        raise ValueError("Actual irreversible core/profile relation changed")
    names = tuple(vars(context.dyna))
    added = names[len(context.original_names) :]
    if names != (*context.original_names, *MAPS[: len(added)]) or len(added) > len(MAPS):
        raise ValueError("Handler stores escaped the original three-map roster")
    for name in added:
        if type(vars(context.dyna)[name]) is not dict:
            raise ValueError("Original profile target maps must remain actual dictionaries")
    return names


def _junctions_route(parent):
    module = _ready()._seed_junctions_api()
    child, owner = getattr(parent, "junctions", None), getattr(parent, "owner", None)
    if (
        child is None
        or owner is None
        or _ISSUED.get(owner) is not parent
        or _FORWARDED.get(owner) is not child
        or parent.active
        or parent.invalid
        or child.invalid
        or type(child.request) is not module.Request
        or child.request.profiles_owner is not owner
        or module._REQUESTS.get(child.request) is not child.refs
        or module._CONSUMED.get(child.request) is not child
        or module._RETIRED.get(owner) is not child
        or child.parent is not parent
        or child.refs[0] is not parent
        or child.refs[1] is not parent.trial
        or any(
            getattr(child, name) is not getattr(parent, name)
            for name in ("phase", "sim", "p", "cells", "dyna", "grid")
        )
        or child.world is not parent.parent.parent
        or child.thread != parent.thread
        or child.thread != get_ident()
        or tuple(child.entries) != ("wrapper_guard", "dispatch")
        or child.entries["wrapper_guard"] is not module._wrapper_guard
        or child.entries["dispatch"] is not module._dispatch
    ):
        raise ValueError("Actual profile/junction issuance or retirement edge changed")
    return child, module


def _junctions_values(parent):
    module = _ready()._seed_junctions_api()
    values = _values(parent)
    values["cells"] = {
        name: value for name, value in vars(parent.cells).items() if name not in module.STORES
    }
    return _cache(parent, values)


def _junctions_graph(parent):
    module = _ready()._seed_junctions_api()
    view = parent.junctions_view
    parent.junctions_cells.clear()
    parent.junctions_cells.update(
        (name, value) for name, value in vars(parent.cells).items() if name not in module.STORES
    )
    view.cells = parent.junctions_cells
    view.simulator, view.parameters, view.handler = (
        vars(parent.sim),
        vars(parent.p),
        vars(parent.dyna),
    )
    view.mesh, view.grid = vars(parent.parent.mesh), vars(parent.grid)
    view.profiles, view.percent_views = parent.profile_fields, parent.percent_views
    return previous.previous._scope(parent.parent.parent).graph(view, view, parent.graph_tape)


def _claim_for_seed_junctions(owner, *, expected, transition, entries):
    module = _ready()._seed_junctions_api()
    caller = sys._getframe(1)
    with _LOCK:
        parent = _ISSUED.get(owner) if type(owner) is ProfilesOwner else None
        if (
            parent is None
            or parent.trial is not expected
            or caller.f_code is not module.prepare.__code__
            or not module._ACTIVE
            or module._ACTIVE[-1] is not transition
        ):
            raise ProfilesRejected("Actual active junction issuer required", stage="entry")
        if owner in _FORWARDED or hasattr(parent, "junctions"):
            raise ProfilesRejected("Profile junction epoch consumed", stage="consumed")
        if (
            parent.active
            or parent.validating
            or parent.invalid
            or parent.owner is not owner
            or transition.driver_frame is not caller
            or transition.parent is not parent
            or type(transition.request) is not module.Request
            or transition.request.profiles_owner is not owner
            or module._REQUESTS.get(transition.request) is not transition.refs
            or module._CONSUMED.get(transition.request) is not transition
            or module._RETIRED.get(owner) is not transition
            or transition.refs[0] is not parent
            or transition.refs[1] is not expected
            or any(
                getattr(transition, name) is not getattr(parent, name)
                for name in ("phase", "p", "cells", "sim", "grid", "dyna")
            )
            or transition.world is not parent.parent.parent
            or transition.thread != parent.thread
            or transition.thread != get_ident()
            or entries is not transition.entries
            or tuple(entries) != ("wrapper_guard", "dispatch")
            or entries["wrapper_guard"] is not module._wrapper_guard
            or entries["dispatch"] is not module._dispatch
        ):
            parent.invalid = transition.invalid = True
            raise ValueError("Actual same-phase profile/junction entry or ancestry changed")
        parent.junctions = transition
        try:
            _FORWARDED[owner] = transition
            previous._claim_profile_junction_permission(parent, transition)
            _check(parent, closed=True)
            _complete(parent)
            if (
                parent.trial.identity != _digest(trial_record(parent.trial))
                or parent.trial.after.identity != _snapshot(parent).identity
            ):
                raise ValueError("Original completed profile trial/cache changed")
            graph = _edges(parent)
            previous.previous._same(graph[0], parent.graph[0])
            if graph[1] != parent.graph[1]:
                raise ValueError("Original completed profile aliases changed")
            parent.junctions_view, parent.junctions_cells = SimpleNamespace(), {}
            parent.junctions_values = _junctions_values(parent)
            parent.junctions_graph = _junctions_graph(parent)
        except BaseException:
            parent.invalid = transition.invalid = True
            raise
        return parent


def _check_seed_junctions_authority(transition):
    parent = transition.parent
    if _junctions_route(parent)[0] is not transition:
        raise ValueError("Different actual junction continuation")
    _bootstrap(parent)
    _check_fields(parent)
    if previous._check_seed_profiles_authority(parent) is not parent.parent:
        raise ValueError("Different original core/profile ancestry")
    _same_bindings(_bindings(parent), parent.bindings)
    _image_authority(parent.request.image_inputs, _selected_pickers(parent))
    _complete(parent)
    if (
        parent.trial is not transition.refs[1]
        or parent.trial.source_completed is not True
        or parent.trial.identity != _digest(trial_record(parent.trial))
        or _junctions_values(parent).identity != parent.junctions_values.identity
        or _cell_epoch(parent) != parent.cell_epoch
        or previous.previous._rng(parent.parent.parent).identity != parent.stream_after.identity
    ):
        raise ValueError("Junctions changed a retained profile/material/index/MT value")
    graph = _junctions_graph(parent)
    previous.previous._same(graph[0], parent.junctions_graph[0])
    if graph[1] != parent.junctions_graph[1]:
        raise ValueError("Junctions changed a retained profile/material/reference edge")
    return parent


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
    if owner in _FORWARDED or hasattr(context, "junctions"):
        raise ProfilesRejected(
            "Profile epoch was irreversibly consumed by junctions",
            stage="forwarded",
            trial=context.trial,
            partial=context,
        )
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
