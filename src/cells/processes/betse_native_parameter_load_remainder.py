"""Original final Parameters.load source and genuine pre-phase ownership.

The original method dispatch is retained: the compiled tail calls the actual
Parameters._load_ion_profile, which calls the actual _balance_charge. Expected
code is compiled independently from pinned AST, never substituted for a live
method/helper. No source or factory runs at import or metadata preparation.

The exact fresh predecessor connection is declared below. Actual use still
requires its release gates and genuine completed parent; a source connection
alone grants no parameter, phase or numerical admission.
"""

import ast
import builtins
import copy
import dis
import enum
import hashlib
import os
import sys
import typing
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock, get_ident
from types import CodeType, FunctionType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_initializer_constants as previous

LAW_ID = "betse_native_parameter_complete_load_remainder@1"
RELEASE = "CELLS_NATIVE_PARAMETER_LOAD_REMAINDER_RELEASED"
BASE_PREDECESSOR_SHA256 = "3fc51886956ae7f4fc0880b0fb6b5ec25f7c939c14a3ba31e0b012f717774f69"
# A separately pinned source candidate permits inspection only, never _hook admission.
SOURCE_CANDIDATE_PREDECESSOR_SHA256 = (
    "5c3d9538c50398eeaaf5437d93c60e8ec7b2c8f93ae95535a321d11e5b97274a"
)
# Exact fresh source connection; no release or actual parent authority is inferred.
HANDOFF_PRODUCER_SHA256 = "5c3d9538c50398eeaaf5437d93c60e8ec7b2c8f93ae95535a321d11e5b97274a"
HANDOFF_LAW = "betse_native_parameter_original_load_remainder_handoff@1"
HANDOFF_FACTORY = "remainder_handoff"
HANDOFF_CHECK = "validate_remainder_history"
HANDOFF_TYPE = "RemainderGrant"
HANDOFF_RECORD_TYPE = "RemainderRecord"
START, STOP, MAX_WORK = 203, 218, 20000
LOCAL_KEY = "__cells_retained_original_internal_parameters__"
PARAMETER_SHA256 = "f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e"
PROFILE_NAMES = ("BASIC", "BASIC_CA", "MAMMAL", "AMPHIBIAN", "CUSTOM")
REPLACED = ("wsx", "wsy")
prefix, claims = previous.prefix, previous.claims
_LOCK, _ACTIVE = Lock(), []
_ISSUED, _CONSUMED, _CONSTRUCTED = (WeakKeyDictionary() for _ in range(3))
_HOOK_GUARDS, _AUDIT_INSTALLED = [], False
_CALL_TRACING = sys.call_tracing


class _ObservationStop(RuntimeError):
    """One retained control sentinel, never a successful native return."""


class LoadRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None, source_error=None, capture_errors=()):
        super().__init__(reason)
        self.stage, self.partial, self.source_error = stage, partial, source_error
        self.capture_errors = tuple(capture_errors)


@dataclass(frozen=True, slots=True)
class LoadRecord:
    parent_identity: str
    source_identity: str
    load_cursor: int
    profile_name: str
    before_identity: str
    after_identity: str
    work: tuple
    observations: tuple
    source_completed: bool
    identity: str
    handoff_identity: str = ""
    handoff_work: tuple = ()


class WorldReadyParametersOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use released complete_load from the actual constants owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live pre-phase parameter authority cannot be serialized")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def record(self):
        return validate_completed_history(self)


def _digest(value):
    return previous._digest(value)


def _source():
    path = prefix.parameters.inherited.tissue.aliases.NATIVE / prefix.parameters.PARAMETERS
    if hashlib.sha256(path.read_bytes()).hexdigest() != PARAMETER_SHA256:
        raise ValueError("Exact original Parameters source required")
    tree = ast.parse(path.read_bytes())
    cls = prefix.parameters.inherited._class(tree, "Parameters")
    load = prefix.parameters.inherited._method(cls, "load")
    ion = prefix.parameters.inherited._method(cls, "_load_ion_profile")
    balance = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_balance_charge"
    )
    selected = load.body[START:STOP]
    if (
        len(load.body) != STOP
        or len(selected) != 15
        or ast.unparse(selected[0]) != "self.d_cell = self.cell_radius * 2"
        or ast.unparse(selected[1]) != "self.nx = int(self.wsx / self.d_cell)"
        or ast.unparse(selected[2]) != "self.ny = int(self.wsy / self.d_cell)"
        or ast.unparse(selected[-1]) != "self._load_ion_profile()"
    ):
        raise ValueError("Original diameter/grid/world/profile order changed")
    return path, cls, load, selected, ion, balance


def _stores(nodes):
    result = []
    for statement in nodes:
        for node in ast.walk(statement):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                for item in ast.walk(target):
                    if (
                        isinstance(item, ast.Attribute)
                        and isinstance(item.value, ast.Name)
                        and item.value.id == "self"
                        and item.attr not in result
                    ):
                        result.append(item.attr)
    return tuple(result)


def _branches(ion):
    node = next(n for n in ion.body if isinstance(n, ast.If))
    rows = []
    for name in PROFILE_NAMES:
        if ast.unparse(node.test) != "self.ion_profile is IonProfileType." + name:
            raise ValueError("Original ion-profile branch/order changed")
        rows.append(
            (
                name,
                _stores(node.body),
                _digest(ast.dump(ast.Module(body=node.body, type_ignores=[]))),
            )
        )
        if name != PROFILE_NAMES[-1]:
            if len(node.orelse) != 1 or not isinstance(node.orelse[0], ast.If):
                raise ValueError("Original profile elif chain changed")
            node = node.orelse[0]
    if len(node.orelse) != 1 or not isinstance(node.orelse[0], ast.Raise):
        raise ValueError("Original unknown-profile refusal changed")
    return tuple(rows)


def source_plan():
    path, _, load, selected, ion, balance = _source()
    producer = hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest()
    if producer not in (
        BASE_PREDECESSOR_SHA256,
        SOURCE_CANDIDATE_PREDECESSOR_SHA256,
        HANDOFF_PRODUCER_SHA256,
    ):
        raise ValueError("Explicit constants predecessor/successor producer required")
    return dict(
        law=LAW_ID,
        parameter_source=(str(path), PARAMETER_SHA256),
        statement_slice=(START, STOP),
        source_lines=(1127, 1154),
        load_cursor=STOP,
        tail_ast=_digest(ast.dump(ast.Module(body=selected, type_ignores=[]))),
        header_ast=_digest(ast.dump(load.args)),
        tail_stores=_stores(selected[:-1]),
        replaces=REPLACED,
        unchanged_earlier_volume="vol_env is not recomputed",
        profile_lines=(ion.lineno, ion.end_lineno),
        profile_ast=_digest(ast.dump(ion)),
        profiles=_branches(ion),
        profile_union=_stores(ion.body),
        balance_lines=(balance.lineno, balance.end_lineno),
        balance_ast=_digest(ast.dump(balance)),
        predecessor_base=BASE_PREDECESSOR_SHA256,
        adopted_handoff_producer=HANDOFF_PRODUCER_SHA256,
        source_candidate_producer=SOURCE_CANDIDATE_PREDECESSOR_SHA256,
        candidate_source_grants_runtime_admission=False,
        hook=dict(
            factory=HANDOFF_FACTORY,
            law=HANDOFF_LAW,
            grant=HANDOFF_TYPE,
            historical_check=HANDOFF_CHECK,
            record=HANDOFF_RECORD_TYPE,
        ),
        local_transport=(LOCAL_KEY, "actual retained iu from completed constants return"),
        native_bodies_copied_or_rewritten=False,
        native_dispatch=("tail", "ion_wrapper", "ion", "balance_wrapper", "balance"),
        wrappers="Original installed beartype return-None and two-sequence/tuple wrappers",
        capture_scalars=(
            "Existing YAML scalar types plus exact retained NumPy float64",
            "Original scalar object/type/binary64 bits/aliases; no live-value conversion",
        ),
        public_module_globals_patched=False,
        full_source_path_implemented=True,
        runtime_hook_available=HANDOFF_PRODUCER_SHA256 is not None,
        requires_no_ancestral_construction=True,
        material_phase_world_science_admitted=False,
    )


def _hook():
    if type(HANDOFF_PRODUCER_SHA256) is not str:
        raise LoadRejected(
            "Reviewed constants remainder-handoff successor is unavailable",
            stage="predecessor_handoff",
        )
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != HANDOFF_PRODUCER_SHA256:
        raise LoadRejected("Explicit hook producer mismatch", stage="predecessor_producer")
    if (
        not callable(vars(previous).get(HANDOFF_FACTORY))
        or not callable(vars(previous).get(HANDOFF_CHECK))
        or not isinstance(vars(previous).get(HANDOFF_TYPE), type)
        or not isinstance(vars(previous).get(HANDOFF_RECORD_TYPE), type)
    ):
        raise LoadRejected("Typed remainder-handoff exports incomplete", stage="predecessor_api")
    return previous


def _ancestry(parent):
    colormap, modulator = parent.parent, parent.parent.parent
    grn = modulator.parent
    loaded = grn.authority.loaded
    seven = previous.previous.mod.subconfigs
    if (
        previous._ISSUED.get(parent.owner) is not parent
        or previous.previous._ISSUED.get(colormap.owner) is not colormap
        or previous.previous.mod._ISSUED.get(modulator.owner) is not modulator
        or previous.previous.mod.previous._ISSUED.get(grn.owner) is not grn
        or seven._ISSUED.get(loaded.owner) is not loaded
        or any(value.p is not parent.p for value in (colormap, modulator, grn, loaded))
    ):
        raise ValueError("Actual same-p constants/colormap/GRN/seven-load lineage required")
    if loaded.owner in claims._CONSTRUCTED:
        raise LoadRejected(
            "Ancestral construction attempt prevents fresh pre-phase authority",
            stage="prior_construction",
            partial=loaded.owner,
        )
    return loaded


def _cached(function):
    value = function.__globals__.get("__builtins__")
    resolved = value if type(value) is dict else vars(value)
    if resolved is not function.__builtins__:
        raise ValueError("Original construction namespace/cached builtins differ")


def _canonical(function, expected, namespace):
    if (
        type(function) is not FunctionType
        or function.__globals__ is not namespace
        or function.__defaults__ is not None
        or function.__kwdefaults__ is not None
        or function.__closure__ is not None
        or function.__code__.co_filename != expected.co_filename
        or function.__code__.co_qualname != expected.co_qualname
        or prefix.parameters.inherited._code(function.__code__)
        != prefix.parameters.inherited._code(expected)
    ):
        raise ValueError("Original executable header/body/namespace changed")
    _cached(function)
    return prefix._function_bindings(function)


def _balance_wrapper_code(sequence_name):
    """Compile the pinned library's narrow wrapper shape, without calling it."""
    checks = ""
    for index, name in enumerate(("concentrations", "zs")):
        checks += f"""
    __beartype_pith_0 = (args[{index}] if __beartype_args_len > {index}
        else kwargs.get({name!r}, __beartype_get_violation))
    if __beartype_pith_0 is not __beartype_get_violation:
        if not isinstance(__beartype_pith_0, {sequence_name}):
            __beartype_violation = __beartype_get_violation(
                check_meta=__beartype_check_meta, pith_name={name!r}, pith_value=__beartype_pith_0)
            raise __beartype_violation
"""
    text = f"""def wrapper(*args, {sequence_name}=None,
    __beartype_get_violation=None, __beartype_conf=None,
    __beartype_check_meta=None, __beartype_func=None, **kwargs):
    __beartype_args_len = len(args)
{checks}
    __beartype_pith_0 = __beartype_func(*args, **kwargs)
    if True:
        if not isinstance(__beartype_pith_0, tuple):
            __beartype_violation = __beartype_get_violation(
                check_meta=__beartype_check_meta, pith_name='return', pith_value=__beartype_pith_0)
            raise __beartype_violation
    return __beartype_pith_0
"""
    module = compile(text, "<balance-wrapper-metadata>", "exec", dont_inherit=True)
    return next(code for code in module.co_consts if type(code) is CodeType)


def _balance_wrapper_bindings(wrapper, original, ion_wrapper, namespace):
    """Bind the installed module-level wrapper to the authenticated package hook.

    The ion wrapper has already authenticated the pinned library's violation
    helpers and configuration. The module helper must use those exact objects,
    with its own original function/annotations and no class stack.
    """
    chain = prefix.parameters.inherited._chain(wrapper)
    if len(chain) != 2 or chain[1] is not original:
        raise ValueError("Actual installed balance wrapper/delegate required")
    defaults, source_defaults = wrapper.__kwdefaults__, ion_wrapper.__kwdefaults__
    types_module, array_module = sys.modules.get("betse.util.type.types"), namespace.get("np")
    if type(types_module) is not ModuleType or type(array_module) is not ModuleType:
        raise ValueError("Actual native sequence/array providers required")
    sequences = namespace.get("SequenceTypes")
    if (
        type(sequences) is not tuple
        or len(sequences) != 2
        or vars(types_module).get("SequenceTypes") is not sequences
        or sequences[0] is not Sequence
        or sequences[1] is not vars(array_module).get("ndarray")
    ):
        raise ValueError("Actual native SequenceTypes members required")
    if type(defaults) is not dict or len(defaults) != 5:
        raise ValueError("Original balance wrapper keyword roster required")
    sequence_name = next(iter(defaults))
    union = defaults[sequence_name]
    annotations = original.__annotations__
    hint = annotations.get("concentrations")
    arguments = vars(original).get("__beartype_args_lens")
    meta, conf = defaults.get("__beartype_check_meta"), defaults.get("__beartype_conf")
    if (
        type(union) is not tuple
        or len(union) != 2
        # The pinned union factory may canonicalize class order using its
        # process-local cache. Retain that actual tuple; admit only these exact
        # two members, never replace/reorder the installed union.
        or not (
            union[0] is sequences[0]
            and union[1] is sequences[1]
            or union[0] is sequences[1]
            and union[1] is sequences[0]
        )
        or sequence_name != "__beartype_object_" + str(id(union))
        or tuple(defaults)[1:] != tuple(source_defaults)[1:]
        or defaults["__beartype_func"] is not original
        or defaults["__beartype_get_violation"] is not source_defaults["__beartype_get_violation"]
        or conf is not source_defaults["__beartype_conf"]
        or type(meta) is not type(source_defaults["__beartype_check_meta"])
        or tuple(annotations) != ("concentrations", "zs", "return")
        or annotations["zs"] is not hint
        or annotations["return"] is not tuple
        or typing.get_origin(hint) is not typing.Union
        or typing.get_args(hint) != sequences
        or wrapper.__annotations__ is not annotations
        or vars(wrapper).get("__wrapped__") is not original
        or vars(wrapper).get("__beartype_wrapper") is not True
        or set(vars(wrapper)) != {"__wrapped__", "__beartype_wrapper", "__beartype_args_lens"}
        or type(arguments) is not tuple
        or len(arguments) != 4
        or tuple(type(value) for value in arguments) != (int, int, bool, bool)
        or arguments != (2, 0, False, False)
        or vars(wrapper)["__beartype_args_lens"] is not arguments
        or wrapper.__defaults__ is not None
        or wrapper.__closure__ is not None
        or tuple(wrapper.__globals__) != ("__builtins__",)
        or wrapper.__builtins__ is not vars(builtins)
        or object.__getattribute__(meta, "func") is not original
        or object.__getattribute__(meta, "conf") is not conf
        or object.__getattribute__(meta, "func_annotations") is not annotations
        or object.__getattribute__(meta, "cls_stack") is not None
        or object.__getattribute__(conf, "_is_violation_param_warn") is not False
        or prefix.parameters.inherited._code(wrapper.__code__)
        != prefix.parameters.inherited._code(_balance_wrapper_code(sequence_name))
    ):
        raise ValueError("Original balance wrapper code/default/metadata association changed")
    _cached(wrapper)
    return (
        *prefix.parameters.inherited.tissue._factory_atoms(wrapper),
        types_module,
        sequences,
        *sequences,
        union,
        *union,
        annotations,
        *annotations.keys(),
        *annotations.values(),
        meta,
        conf,
        arguments,
        *arguments,
    )


def _native_helpers(cls, namespace, cls_ast, balance_ast, path):
    ion_wrapper, balance_wrapper = (
        vars(cls).get("_load_ion_profile"),
        namespace.get("_balance_charge"),
    )
    ion_chain = prefix.parameters.inherited._chain(ion_wrapper)
    balance_chain = prefix.parameters.inherited._chain(balance_wrapper)
    if len(ion_chain) != 2 or len(balance_chain) != 2:
        raise ValueError("Actual package-installed ion and balance wrappers required")
    ion, balance = ion_chain[1], balance_chain[1]
    ion_atoms = prefix.parameters._method_wrapper_bindings(ion_wrapper, cls)
    ion_binding = _canonical(
        ion,
        prefix.parameters._method_code(
            cls_ast, "_load_ion_profile", str(path), native_context=True
        ),
        namespace,
    )
    balance_binding = _canonical(
        balance, previous.previous.boundary._context_code(balance_ast, str(path)), namespace
    )
    balance_atoms = _balance_wrapper_bindings(balance_wrapper, balance, ion_wrapper, namespace)
    return SimpleNamespace(
        ion=ion,
        balance=balance,
        ion_wrapper=ion_wrapper,
        balance_wrapper=balance_wrapper,
        atoms=(*ion_atoms, *balance_atoms, *ion_binding[1], *balance_binding[1]),
    )


def _descriptor(cls, name):
    owner = next((base for base in cls.__mro__ if name in vars(base)), None)
    if owner is None:
        raise ValueError("Actual original descriptor absent: " + name)
    value = vars(owner)[name]
    function = vars(type(value)).get("__get__")
    if type(function) is not FunctionType:
        raise ValueError("Actual source-backed descriptor required: " + name)
    return value, function


def _native(context):
    path, cls_ast, _, _, ion_ast, balance_ast = _source()
    birth = context.parent.parent.parent.birth
    cls = birth.source.cls
    module = birth.source.modules["betse.science.parameters"]
    namespace = vars(module)
    if (
        type(module) is not ModuleType
        or Path(module.__file__).resolve() != path
        or type(context.p) is not cls
        or vars(context.p).get("_conf") is not context.config
        or "_load_ion_profile" in vars(context.p)
    ):
        raise ValueError("Original actual Parameters class/module/receiver required")
    helpers = _native_helpers(cls, namespace, cls_ast, balance_ast, path)
    ion, balance = helpers.ion, helpers.balance
    # These are reached by the original helper; no constructor/evaluator call.
    for function, names in ((ion, ("float",)), (balance, ("zip", "abs"))):
        for name in names:
            if name in namespace or function.__builtins__.get(name) is not vars(builtins)[name]:
                raise ValueError("Original reached builtin lookup shadowed: " + name)
    enum_cls = namespace.get("IonProfileType")
    enum_module = sys.modules.get("betse.science.enum.enumconf")
    if (
        type(enum_cls) is not enum.EnumType
        or enum_module is None
        or vars(enum_module).get("IonProfileType") is not enum_cls
    ):
        raise ValueError("Actual native ion-profile enum required")
    members = tuple((name, enum_cls.__members__[name]) for name in PROFILE_NAMES)
    array_module = namespace.get("np")
    core = sys.modules.get("numpy._core._multiarray_umath")
    if (
        type(array_module) is not ModuleType
        or core is None
        or vars(array_module).get("sign") is not vars(core).get("sign")
    ):
        raise ValueError("Original NumPy sign dispatch required")
    loaded = context.loaded
    base = vars(context.p)["tissue_default"]
    if (
        loaded.authority.objects["tissue_default"] is not base
        or type(base) is not loaded.authority.classes["SimConfTissueDefault"]
        or vars(base).get("_conf")
        is not context.config["tissue profile definition"]["tissue"]["default"]
        or not any(value is base for value in loaded.before_objects)
    ):
        raise ValueError("Original loaded tissue-default/permeability authority required")
    alias, getter = _descriptor(cls, "ion_profile")
    dm = tuple(
        (name, *_descriptor(type(base), name))
        for name in ("Dm_Na", "Dm_K", "Dm_Cl", "Dm_Ca", "Dm_P", "Dm_M")
    )
    references = [
        cls,
        module,
        namespace,
        base,
        enum_cls,
        enum_module,
        array_module,
        vars(array_module)["sign"],
        alias,
        getter,
    ]
    references.extend(prefix.parameters.inherited.tissue._surface(cls))
    references.extend(prefix.parameters.inherited.tissue._surface(type(base)))
    for name, descriptor, function in dm:
        references.extend((name, descriptor, function, *prefix._function_bindings(function)[1]))
    references.extend((*helpers.atoms, *prefix._function_bindings(getter)[1]))
    references.extend(value for _, value in members)
    return SimpleNamespace(
        ion=ion,
        balance=balance,
        ion_wrapper=helpers.ion_wrapper,
        balance_wrapper=helpers.balance_wrapper,
        cls=cls,
        namespace=namespace,
        base=base,
        members=members,
        alias=alias,
        getter=getter,
        dm=dm,
        bindings=((), tuple(references)),
    )


def _compile(context):
    path, cls, _, selected, _, _ = _source()
    original = context.parent.function
    prefix._function_bindings(original)
    _cached(original)
    for name in ("float", "int"):
        if (
            name in original.__globals__
            or original.__builtins__.get(name) is not vars(builtins)[name]
        ):
            raise ValueError("Original numeric constructor resolution changed")
    if original.__globals__ is not context.api.namespace:
        raise ValueError("Original tail must retain actual Parameters namespace")
    cls = copy.deepcopy(cls)
    transport = ast.parse("iu = kwargs[" + repr(LOCAL_KEY) + "]").body[0]
    prefix.parameters.inherited._method(cls, "load").body = [transport, *copy.deepcopy(selected)]
    code = prefix.parameters._method_code(cls, "load", str(path))
    if code.co_freevars:
        raise ValueError("Unexpected closure in exact load tail")
    function = FunctionType(code, original.__globals__, original.__name__, None, None)
    if function.__builtins__ is not original.__builtins__:
        raise ValueError("Tail private cached builtins changed")
    return function


def _capture_scalar_type():
    """Use the already-bound native scalar registry, not a caller-supplied type."""
    registry = previous.previous.state
    array = registry.np
    if type(array) is not ModuleType or sys.modules.get("numpy") is not array:
        raise ValueError("Actual retained NumPy metadata namespace required")
    scalar = vars(array).get("float64")
    if (
        type(scalar) is not type
        or scalar.__module__ != "numpy"
        or scalar.__name__ != "float64"
        or scalar.__flags__ & (1 << 9)
        or not issubclass(scalar, float)
        or not any(scalar is kind for kind in registry.NUMPY_SCALARS)
    ):
        raise ValueError("Exact retained NumPy float64 class required")
    return scalar


def _capture(context, *, names=None):
    names = tuple(vars(context.p)) if names is None else names
    birth = context.parent.parent.parent.birth
    runtime = context.parent.parent.parent.runtime
    return prefix.graphs.capture(
        {name: vars(context.p)[name] for name in names if name not in previous.CM_STORES},
        yaml_base=birth.source.yaml,
        runtime_types=runtime.runtime_types | {_capture_scalar_type()},
    )


def _colormaps(context):
    return previous._cm_graph(context.parent.parent)


def _stacks(context):
    return ((_ACTIVE, context), *previous._stacks(context))


def _history(context):
    if (
        previous._ISSUED.get(context.parent_owner) is not context.parent
        or context.parent.owner is not context.parent_owner
        or context.parent.p is not context.p
        or context.parent.trial is not context.parent_trial
        or _digest(previous.trial_record(context.parent_trial)) != context.parent_trial.identity
        or _ancestry(context.parent) is not context.loaded
    ):
        raise ValueError("Original completed parameter lineage changed")
    api = _hook()
    before_work = context.grant.metadata_work
    record = vars(api)[HANDOFF_CHECK](context.grant, original_owner=context.parent_owner)
    after_work = context.grant.metadata_work
    if after_work[: len(before_work)] != before_work:
        raise ValueError("Retained grant metadata work prefix changed")
    context.metadata_work.append(
        ("actual_grant_history_validation", after_work[len(before_work) :])
    )
    if (
        record is not context.grant_record
        or context.grant.record is not record
        or type(record) is not vars(api)[HANDOFF_RECORD_TYPE]
        or record.succeeded is not True
    ):
        raise ValueError("Actual successful closed predecessor handoff required")
    if _digest(source_plan()) != context.source_identity:
        raise ValueError("Load remainder source/hook producer changed")
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    prefix.parameters.inherited._same(_native(context).bindings, context.api.bindings)
    prefix.parameters.inherited._same(
        prefix._function_bindings(context.function), context.function_bindings
    )


def _copy_locals(frame):
    return dict(frame.f_locals)


def _returned(context, role, frame, value):
    context.raw_return = (role, frame, value)
    context.raw_returns.append(context.raw_return)  # Before any fallible copy.
    context.returns[role].append(value)
    context.locals[role] = _copy_locals(frame)


def _spans(code, nodes, operation):
    instructions = tuple(dis.get_instructions(code))
    rows = []
    for node in nodes:
        matches = []
        for index, item in enumerate(instructions):
            position = item.positions
            if (
                item.opname.startswith(operation)
                and position.lineno == node.lineno
                and position.col_offset == node.col_offset
                and position.end_lineno == node.end_lineno
                and position.end_col_offset == node.end_col_offset
            ):
                end = (
                    instructions[index + 1].offset
                    if index + 1 < len(instructions)
                    else len(code.co_code)
                )
                matches.append((item.offset, end))
        if len(matches) != 1:
            raise ValueError("Exact original source call/attribute instruction required")
        rows.append(matches[0])
    return tuple(rows)


def _call_sites(context):
    _, _, _, tail, ion, _ = _source()
    balances = sorted(
        (
            n
            for n in ast.walk(ion)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "_balance_charge"
        ),
        key=lambda n: n.lineno,
    )
    aliases = sorted(
        (n for n in ast.walk(ion) if isinstance(n, ast.Attribute) and n.attr == "ion_profile"),
        key=lambda n: n.lineno,
    )
    if len(balances) != 2 * len(PROFILE_NAMES) or any(
        len(n.args) != 2 or any(not isinstance(arg, ast.Name) for arg in n.args) for n in balances
    ):
        raise ValueError("Original profile helper argument/order declaration changed")
    return dict(
        ion=_spans(context.function.__code__, [tail[-1].value], "CALL"),
        balance=_spans(context.api.ion.__code__, balances, "CALL"),
        balance_arguments=tuple(tuple(arg.id for arg in n.args) for n in balances),
        ion_alias=_spans(context.api.ion.__code__, aliases, "LOAD_ATTR"),
    )


def _wrapper_delegate_span(function):
    instructions = tuple(dis.get_instructions(function))
    calls = [i for i, value in enumerate(instructions) if value.opname == "CALL_FUNCTION_EX"]
    if len(calls) != 1 or not any(
        value.opname == "LOAD_FAST" and value.argval == "__beartype_func"
        for value in instructions[: calls[0]]
    ):
        raise ValueError("One original wrapper delegate call required")
    index = calls[0]
    return ((instructions[index].offset, instructions[index + 1].offset),)


def _wrapper_state(function):
    """Cheap identity checks at source boundaries, including hidden delegates."""
    atoms = list(prefix.parameters.inherited.tissue._factory_atoms(function))
    atoms.extend((function.__globals__, function.__builtins__, function.__annotations__))
    atoms.extend(function.__annotations__.keys())
    atoms.extend(function.__annotations__.values())
    for candidate in (function, function.__wrapped__):
        arguments = vars(candidate).get("__beartype_args_lens")
        atoms.append(arguments)
        if type(arguments) is tuple:
            atoms.extend(arguments)
    for name in ("len", "isinstance", "tuple"):
        atoms.extend((function.__globals__.get(name), function.__builtins__.get(name)))
    meta = function.__kwdefaults__["__beartype_check_meta"]
    for name in ("func", "func_annotations", "conf", "cls_stack"):
        atoms.append(object.__getattribute__(meta, name))
    return tuple(atoms)


def _check_wrappers(context, state):
    for role, wrapper, retained in state.wrapper_states:
        if getattr(context.api, role + "_wrapper") is not wrapper:
            raise ValueError("Retained original wrapper association changed")
        if role == "ion":
            slot = vars(context.api.cls).get("_load_ion_profile")
        else:
            slot = context.api.namespace.get("_balance_charge")
        current = _wrapper_state(wrapper)
        if (
            slot is not wrapper
            or len(current) != len(retained)
            or any(a is not b for a, b in zip(current, retained, strict=True))
        ):
            raise ValueError("Installed original wrapper/delegate state changed")


def _fault(context, state, stage, error):
    state.errors.append((stage, error))
    state.pending = True
    context.invalid = True


def _reject_entry(context, state, reason):
    error = ValueError(reason)
    state.rejections.append(error)
    _fault(context, state, "entry_refusal", error)
    raise error


def _hook_audit(event, args):
    if event not in ("sys.setprofile", "sys.settrace"):
        return
    for state in tuple(_HOOK_GUARDS):
        if state.thread == get_ident() and state.inherited_depth:
            state.context.hook_mutation_attempts.append((event, args))
            if state.rejections:
                # CPython can clear tracing while propagating a rejected raw
                # call. Refuse that change too, preserving the first sticky
                # rejection instead of replacing it with a cleanup exception.
                raise state.rejections[0]
            _reject_entry(state.context, state, "Inherited observer may not disable source guards")


def _install_hook_audit():
    global _AUDIT_INSTALLED
    if not _AUDIT_INSTALLED:
        sys.addaudithook(_hook_audit)
        _AUDIT_INSTALLED = True


def _inside(frame, spans):
    return next((index for index, (lo, hi) in enumerate(spans) if lo <= frame.f_lasti < hi), None)


def _frame_role(context, state, frame):
    role = state.roles.get(frame.f_code)
    if role is not None:
        return role
    parent = frame.f_back
    if parent is not None and parent is context.invoker_frame:
        return "tail"
    if parent is state.live.get("tail") and _inside(parent, state.sites["ion"]) is not None:
        return "ion_wrapper" if "ion_wrapper" in state.codes else "ion"
    for role in ("ion", "balance"):
        wrapper = role + "_wrapper"
        if parent is not None and parent is state.live.get(wrapper):
            if _inside(parent, state.sites[wrapper]) is not None:
                return role
    if parent is not None and parent is state.live.get("ion"):
        if _inside(parent, state.sites["balance"]) is not None:
            return "balance_wrapper" if "balance_wrapper" in state.codes else "balance"
        if _inside(parent, state.sites["ion_alias"]) is not None:
            return "ion_alias"
    return None


def _admit(context, state, frame, role):
    if frame in state.frames:
        if (
            state.inherited_depth
            or state.pending
            or context.invalid
            or not context.active
            or context.thread != get_ident()
            or frame.f_code is not state.codes[role]
            or state.frames[frame] != role
        ):
            _reject_entry(context, state, "Existing original frame lost its admission epoch")
        return  # Trace/profile report the same actual frame, not two entries.
    context.raw_entry = (role, frame)
    context.entry_witnesses.append((role, frame, frame.f_back, frame.f_lasti))
    context.entries[role] += 1
    if (
        state.inherited_depth
        or state.pending
        or context.invalid
        or not context.active
        or context.thread != get_ident()
        or frame.f_code is not state.codes[role]
        or context.entries[role]
        > dict(tail=1, ion_wrapper=1, ion=1, balance_wrapper=2, balance=2, ion_alias=6)[role]
    ):
        _reject_entry(context, state, "Rejected original source entry is sticky")
    parent, local = frame.f_back, frame.f_locals
    if role == "tail":
        valid = (
            parent is context.invoker_frame and not state.stack and local.get("self") is context.p
        )
    elif role == "ion" and "ion_wrapper" in state.codes:
        valid = (
            parent is state.live.get("ion_wrapper")
            and state.stack[-1:] == [parent]
            and _inside(parent, state.sites["ion_wrapper"]) == 0
            and parent.f_locals.get("__beartype_func") is context.api.ion
            and local.get("self") is context.p
        )
    elif role in ("ion", "ion_wrapper"):
        valid = (
            parent is state.live.get("tail")
            and state.stack[-1:] == [parent]
            and _inside(parent, state.sites["ion"]) == 0
            and (
                local.get("self") is context.p
                if role == "ion"
                else type(local.get("args")) is tuple
                and len(local["args"]) == 1
                and local["args"][0] is context.p
                and local.get("kwargs") == {}
                and local.get("__beartype_func") is context.api.ion
            )
        )
    elif role == "ion_alias":
        index = (
            _inside(parent, state.sites["ion_alias"]) if parent is state.live.get("ion") else None
        )
        valid = (
            index is not None
            and state.stack[-1:] == [parent]
            and index > state.alias_site
            and local.get("self_descriptor") is context.api.alias
            and local.get("self") is context.p
        )
        if valid:
            state.alias_site = index
    elif role == "balance" and "balance_wrapper" in state.codes:
        args = parent.f_locals.get("args") if parent is not None else None
        valid = (
            parent is state.live.get("balance_wrapper")
            and state.stack[-1:] == [parent]
            and _inside(parent, state.sites["balance_wrapper"]) == 0
            and parent.f_locals.get("__beartype_func") is context.api.balance
            and type(args) is tuple
            and len(args) == 2
            and local.get("concentrations") is args[0]
            and local.get("zs") is args[1]
        )
        if valid:
            context.balance_inputs.append(args)
    else:
        index = _inside(parent, state.sites["balance"]) if parent is state.live.get("ion") else None
        selected = context.returns["ion_alias"][-1] if context.returns["ion_alias"] else None
        profile = next(
            (i for i, (_, member) in enumerate(context.api.members) if selected is member), None
        )
        valid = (
            index is not None
            and profile is not None
            and state.stack[-1:] == [parent]
            and index == profile * 2 + context.entries[role] - 1
        )
        if role == "balance_wrapper":
            args = local.get("args")
            valid = (
                valid
                and type(args) is tuple
                and len(args) == 2
                and local.get("kwargs") == {}
                and local.get("__beartype_func") is context.api.balance
            )
            concentrations, zs = args if type(args) is tuple and len(args) == 2 else (None, None)
        else:
            concentrations, zs = local.get("concentrations"), local.get("zs")
            context.balance_inputs.append((concentrations, zs))
        if valid:
            names = state.sites["balance_arguments"][index]
            valid = (
                concentrations is parent.f_locals.get(names[0])
                and zs is parent.f_locals.get(names[1])
                and type(concentrations) is list
                and type(zs) is list
                and 3 <= len(concentrations) == len(zs) <= 5
            )
    if not valid:
        _reject_entry(context, state, "Exact original helper parent/frame/order/arguments required")
    state.frames[frame] = role
    state.live[role] = frame
    state.stack.append(frame)
    frame.f_trace = state.traced
    frame.f_trace_lines = True
    frame.f_trace_opcodes = True


def _safe_boundary(context, state):
    if state.pending or context.invalid:
        raise state.stop
    try:
        _check_wrappers(context, state)
    except BaseException as error:
        _fault(context, state, "wrapper_drift", error)
        raise


def _recover_hooks(
    expected_profile, expected_trace, *, set_profile, set_trace, get_profile, get_trace
):
    """Independent operations; two bounded state-based recovery rounds."""
    errors, samples = [], []
    current = dict(profile=object(), trace=object())
    for attempt in range(3):
        for name, setter, expected in (
            ("profile", set_profile, expected_profile),
            ("trace", set_trace, expected_trace),
        ):
            if attempt == 0 or current[name] is not expected:
                try:
                    setter(expected)
                except BaseException as error:
                    errors.append((name + "_restore_" + str(attempt), error))
        # Sample both after *all* setters; one setter/callback can clear the other.
        for name, getter in (("profile", get_profile), ("trace", get_trace)):
            try:
                current[name] = getter()
                samples.append((attempt, name, current[name]))
            except BaseException as error:
                current[name] = object()
                errors.append((name + "_sample_" + str(attempt), error))
        if current["profile"] is expected_profile and current["trace"] is expected_trace:
            break
        errors.append(
            (
                "hook_identity_drift_" + str(attempt),
                ValueError("A restoration action cleared or replaced a hook"),
            )
        )
    clean = current["profile"] is expected_profile and current["trace"] is expected_trace
    if not clean:
        errors.append(("final_hook_identity", ValueError("Both original hooks must be restored")))
    return dict(
        errors=tuple(errors),
        samples=tuple(samples),
        expected_profile=expected_profile,
        expected_trace=expected_trace,
        final_profile=current["profile"],
        final_trace=current["trace"],
        identities_match=clean,
        clean=clean and not errors,
    )


def _observer_bookkeeping(context, errors, recovery):
    context.capture_errors += tuple(errors)
    context.observer_recovery = recovery


def _invoke(context):
    state = context.observer_state
    context.invocation_attempts += 1
    if state.inherited_depth or context.invoker_frame is not None:
        _reject_entry(context, state, "Original tail may be invoked once only")
    _safe_boundary(context, state)
    context.invoker_frame = sys._getframe()
    return context.function(context.p, **{LOCAL_KEY: context.internal})


@contextmanager
def _observe(context):
    prior, trace = sys.getprofile(), sys.gettrace()
    codes = dict(
        tail=context.function.__code__,
        ion=context.api.ion.__code__,
        balance=context.api.balance.__code__,
        ion_alias=context.api.getter.__code__,
    )
    sites = _call_sites(context)
    wrapper_states = []
    for role in ("ion", "balance"):
        wrapper = getattr(context.api, role + "_wrapper", None)
        if wrapper is not None:
            codes[role + "_wrapper"] = wrapper.__code__
            sites[role + "_wrapper"] = _wrapper_delegate_span(wrapper)
            wrapper_states.append((role, wrapper, _wrapper_state(wrapper)))
            context.entries[role + "_wrapper"] = 0
            context.returns[role + "_wrapper"] = []
    roles = {code: role for role, code in codes.items()}
    native = str(prefix.parameters.inherited.tissue.aliases.NATIVE) + "/"
    state = SimpleNamespace(
        context=context,
        thread=get_ident(),
        roles=roles,
        codes=codes,
        sites=sites,
        wrapper_states=tuple(wrapper_states),
        frames={},
        live={},
        stack=[],
        alias_site=-1,
        inherited_depth=0,
        errors=[],
        rejections=[],
        pending=False,
        stop=_ObservationStop("Original load observation refused continuation"),
        primary=None,
        primary_traceback=None,
        observer_entry_error=None,
        observer_entry_traceback=None,
        prior_traces={},
        delegated=set(),
        active_recoveries=[],
        hooks_ready=False,
    )
    context.observer_state = state
    context.invoker_frame = None
    context.invocation_attempts = 0
    context.entry_witnesses, context.exception_witnesses, context.hook_mutation_attempts = (
        [],
        [],
        [],
    )
    context.delegates = dict.fromkeys(roles.values(), 0)
    context.source_instructions = 0
    original_errors = context.capture_errors
    setters = dict(
        set_profile=sys.setprofile,
        set_trace=sys.settrace,
        get_profile=sys.getprofile,
        get_trace=sys.gettrace,
    )

    def forward(function, frame, event, arg):
        if function is None or state.inherited_depth:
            return None
        state.inherited_depth += 1
        callback_primary = None
        try:
            # CPython disables tracing inside profile callbacks. Restore it
            # while calling the inherited observer so raw helper reentry is
            # subject to the same before-bytecode admission checks.
            return _CALL_TRACING(function, (frame, event, arg))
        except BaseException as error:
            callback_primary = error
            if (
                event == "call"
                and state.observer_entry_error is None
                and error is not state.stop
                and not any(error is item for item in state.rejections)
            ):
                state.observer_entry_error = error
                state.observer_entry_traceback = error.__traceback__
            _fault(context, state, "inherited_" + event, error)
            if event != "return":
                raise  # Immediate call-entry guard refusals stay immediate.
        finally:
            state.inherited_depth -= 1
            current_profile, current_trace = profile, traced
            if state.hooks_ready and not state.inherited_depth:
                observed = {}
                for name in ("profile", "trace"):
                    try:
                        observed[name] = setters["get_" + name]()
                    except BaseException as error:
                        observed[name] = object()
                        _fault(context, state, "active_" + name + "_sample", error)
                current_profile, current_trace = observed["profile"], observed["trace"]
            if (
                state.hooks_ready
                and not state.inherited_depth
                and (current_profile is not profile or current_trace is not traced)
            ):
                _fault(
                    context,
                    state,
                    "active_hook_change",
                    ValueError("Observer entry cleared a source hook"),
                )
                recovered = _recover_hooks(profile, traced, **setters)
                state.active_recoveries.append(recovered)
                for stage, error in recovered["errors"]:
                    _fault(context, state, "active_" + stage, error)
                for live_frame in tuple(state.frames):
                    try:
                        live_frame.f_trace = traced
                        live_frame.f_trace_opcodes = True
                    except BaseException as error:
                        _fault(context, state, "active_frame_trace_recovery", error)
                if not recovered["identities_match"] and (
                    callback_primary is None or event == "return"
                ):
                    raise state.stop
            if state.hooks_ready and not state.inherited_depth:
                for live_frame in tuple(state.frames):
                    if (
                        live_frame.f_trace is not traced
                        or not live_frame.f_trace_lines
                        or not live_frame.f_trace_opcodes
                    ):
                        _fault(
                            context,
                            state,
                            "active_frame_trace_change",
                            ValueError("Inherited observer changed a source frame trace"),
                        )
                        try:
                            live_frame.f_trace = traced
                            live_frame.f_trace_lines = True
                            live_frame.f_trace_opcodes = True
                        except BaseException as error:
                            _fault(context, state, "frame_trace_recovery", error)
                            if callback_primary is None or event == "return":
                                raise state.stop from error

    def traced(frame, event, arg):
        role = _frame_role(context, state, frame)
        if event == "call" and role is not None:
            _admit(context, state, frame, role)
            frame.f_trace_opcodes = True
        elif (
            event == "call"
            and state.inherited_depth
            and frame.f_code.co_filename.startswith(native)
        ):
            _reject_entry(context, state, "Inherited observer cannot enter unowned native source")
        source_frame = frame
        if event == "exception" and not state.inherited_depth:
            while source_frame is not None and source_frame not in state.frames:
                source_frame = source_frame.f_back
        if event == "exception" and not state.inherited_depth and source_frame is not None:
            context.raw_exception = (frame, arg)
            error = arg[1]
            if error is not state.stop and not any(error is e for _, e in state.errors):
                if state.primary is None:
                    state.primary, state.primary_traceback = error, arg[2]
                context.exception_witnesses.append((frame, arg))
        if role is not None and event in ("line", "opcode"):
            _safe_boundary(context, state)
        if not state.inherited_depth:
            inherited = trace if event == "call" else state.prior_traces.get(frame)
            if event != "opcode":  # The original tracer did not request new opcode work.
                result = forward(inherited, frame, event, arg)
                if event == "call" or result is not None:
                    state.prior_traces[frame] = result
        if role is not None and event in ("line", "opcode"):
            _safe_boundary(context, state)
            if frame not in state.delegated:
                state.delegated.add(frame)
                context.delegates[role] += 1
            if event == "opcode":
                context.source_instructions += 1
                if context.source_instructions > MAX_WORK:
                    _reject_entry(
                        context, state, "Bounded original source instruction work exhausted"
                    )
        if event == "return":
            if frame in state.frames:
                if not state.stack or state.stack[-1] is not frame:
                    _fault(
                        context,
                        state,
                        "return_frame_order",
                        ValueError("Original frame stack changed"),
                    )
                else:
                    state.stack.pop()
                state.live.pop(state.frames.pop(frame), None)
            state.prior_traces.pop(frame, None)
        return traced if role is not None or state.prior_traces.get(frame) is not None else None

    def profile(frame, event, arg):
        role = _frame_role(context, state, frame)
        if event == "call":
            if role is not None:
                _admit(context, state, frame, role)
                _safe_boundary(context, state)
            if role or frame.f_code.co_filename.startswith(native):
                if len(context.work) >= MAX_WORK:
                    _reject_entry(context, state, "Bounded original load/profile work exhausted")
                context.work.append(
                    (
                        len(context.work),
                        role or "nested_native",
                        frame.f_code.co_filename,
                        frame.f_code.co_qualname,
                        "entered_not_biological_case",
                    )
                )
        elif event == "return" and role:
            try:
                _returned(context, role, frame, arg)
            except BaseException as error:
                _fault(context, state, role + "_return", error)
        forward(prior, frame, event, arg)
        if event == "call" and role is not None:
            _safe_boundary(context, state)

    primary = None
    recovery = None
    state.traced = traced
    try:
        _install_hook_audit()
        _HOOK_GUARDS.append(state)
        setup = _recover_hooks(profile, traced, **setters)
        context.observer_setup = setup
        for stage, error in setup["errors"]:
            _fault(context, state, "setup_" + stage, error)
        state.hooks_ready = True
        _safe_boundary(context, state)
        yield
        _safe_boundary(context, state)
    except BaseException as error:
        primary = error
        observation_error = any(error is item for _, item in state.errors)
        if state.primary is not None and (error is state.stop or observation_error):
            context.source_error = state.primary
            primary = state.primary
            # Rethrow the exact original source exception and its existing cause.
            raise BaseException.with_traceback(state.primary, state.primary_traceback)  # noqa: B904
        if error is state.stop and state.observer_entry_error is not None:
            # A guarded native finally can encounter the sticky stop while
            # unwinding the immediate entry rejection. Retain that original
            # observer exception without labelling it as a source failure.
            primary = state.observer_entry_error
            raise BaseException.with_traceback(primary, state.observer_entry_traceback)  # noqa: B904
        if error is not state.stop and not observation_error:
            context.source_error = error
        raise
    finally:
        state.hooks_ready = False
        cleanup_errors, samples = [], []
        helper_recovery = None
        metadata_stopped = any(
            name.startswith(("setup_", "active_", "frame_trace_")) for name, _ in state.errors
        )
        bookkeeping_called = False
        try:
            # An inherited profiler/tracer can reject the helper's *entry*,
            # before its internal protection exists. Keep that secondary error
            # separate and still perform the independent cleanup below.
            try:
                helper_recovery = _recover_hooks(prior, trace, **setters)
                cleanup_errors += helper_recovery["errors"]
                metadata_stopped = metadata_stopped or not helper_recovery["clean"]
            except BaseException as error:
                cleanup_errors += [("final_hook_recovery", error)]
                metadata_stopped = True
            # A later successful final cleanup cannot grant continuation after
            # this checkpoint has failed. In particular, do not enter a
            # bookkeeping callback while an inherited hook is absent.
            if not metadata_stopped:
                for name, expected in (("profile", prior), ("trace", trace)):
                    try:
                        if setters["get_" + name]() is not expected:
                            raise ValueError("Required hooks absent before bookkeeping")
                    except BaseException as error:
                        cleanup_errors += [("before_bookkeeping_" + name, error)]
                        metadata_stopped = True
            if not metadata_stopped:
                try:
                    bookkeeping_called = True
                    _observer_bookkeeping(
                        context, (*state.errors, *cleanup_errors), helper_recovery
                    )
                except BaseException as error:
                    cleanup_errors += [("observer_bookkeeping", error)]
        finally:
            # No helper entry is needed to retire the guard or recover both
            # hooks. This also samples after fallible bookkeeping callbacks.
            for index in range(len(_HOOK_GUARDS) - 1, -1, -1):
                if _HOOK_GUARDS[index] is state:
                    del _HOOK_GUARDS[index]
            current = dict(profile=object(), trace=object())
            for attempt in range(4):
                if attempt:
                    for name, expected in (("profile", prior), ("trace", trace)):
                        try:
                            setters["set_" + name](expected)
                        except BaseException as error:
                            cleanup_errors += [
                                ("final_" + name + "_restore_" + str(attempt), error)
                            ]
                # Both samples follow *both* setters, independently of errors.
                for name in ("profile", "trace"):
                    try:
                        current[name] = setters["get_" + name]()
                        samples += [(attempt, name, current[name])]
                    except BaseException as error:
                        current[name] = object()
                        cleanup_errors += [("final_" + name + "_sample_" + str(attempt), error)]
                if current["profile"] is prior and current["trace"] is trace:
                    break
                cleanup_errors += [
                    (
                        "final_hook_identity_" + str(attempt),
                        ValueError("Both original hooks must be independently restored"),
                    )
                ]
            identities_match = current["profile"] is prior and current["trace"] is trace
            recovery = dict(
                helper=helper_recovery,
                errors=tuple(cleanup_errors),
                samples=tuple(samples),
                expected_profile=prior,
                expected_trace=trace,
                final_profile=current["profile"],
                final_trace=current["trace"],
                identities_match=identities_match,
                clean=identities_match and not cleanup_errors,
                metadata_stopped=metadata_stopped or bool(cleanup_errors),
                bookkeeping_called=bookkeeping_called,
            )
            state.errors += cleanup_errors
            if cleanup_errors:
                state.pending = context.invalid = True
            # These plain data stores are after the last fallible callback.
            context.capture_errors = (*original_errors, *state.errors)
            context.observer_recovery = recovery
        if primary is None and state.errors:
            raise state.stop


def _accounting(context):
    return (
        tuple(context.entries.items()),
        tuple(context.delegates.items()),
        context.invocation_attempts,
        context.source_instructions,
        len(context.entry_witnesses),
        len(context.raw_returns),
    )


def _outputs(context):
    for role, count in (("ion", 1), ("balance", 2)):
        if getattr(context.api, role + "_wrapper", None) is not None:
            returned, wrapped = context.returns[role], context.returns[role + "_wrapper"]
            if (
                context.entries[role + "_wrapper"] != count
                or len(returned) != count
                or len(wrapped) != count
                or any(a is not b for a, b in zip(returned, wrapped, strict=True))
            ):
                raise ValueError("Actual original wrapper/body return identity required")
    aliases = context.returns["ion_alias"]
    selected = next(
        (
            (name, member)
            for name, member in context.api.members
            if aliases and aliases[-1] is member
        ),
        None,
    )
    if selected is None or any(value is not selected[1] for value in aliases):
        raise ValueError("Actual original ion-profile selector returns required")
    name = selected[0]
    if len(aliases) != PROFILE_NAMES.index(name) + 1:
        raise ValueError("Original native ion dispatch/order changed")
    if (
        context.entries["tail"] != 1
        or context.entries["ion"] != 1
        or context.entries["balance"] != 2
        or context.delegates != context.entries
        or context.invocation_attempts != 1
        or not 0 < context.source_instructions <= MAX_WORK
        or len(context.returns["tail"]) != 1
        or context.returns["tail"][0] is not None
        or len(context.returns["ion"]) != 1
        or context.returns["ion"][0] is not None
        or len(context.returns["balance"]) != 2
        or context.locals["ion"].get("base") is not context.api.base
        or context.locals["tail"].get("iu") is not context.internal
    ):
        raise ValueError("Complete original tail/profile/helper observations required")
    for index, fields in enumerate((("conc_env_m", "z_M_env"), ("cM_cell", "z_M_cell"))):
        value = context.returns["balance"][index]
        if (
            type(value) is not tuple
            or len(value) != 2
            or any(
                vars(context.p)[field] is not item
                for field, item in zip(fields, value, strict=True)
            )
        ):
            raise ValueError("Actual charge-balance return/store association changed")
    profile_stores = dict((n, fields) for n, fields, _ in context.plan["profiles"])[name]
    expected = (
        *context.before_names,
        *(n for n in context.plan["tail_stores"] if n not in REPLACED),
        *profile_stores,
    )
    if tuple(vars(context.p)) != expected:
        raise ValueError("Original complete-load field order/roster changed")
    if context.p.vol_env is not context.original_volume:
        raise ValueError("Original earlier vol_env may not be recomputed")
    return name


def record_document(value):
    return dict(
        law=LAW_ID,
        parent=value.parent_identity,
        source=value.source_identity,
        load_cursor=value.load_cursor,
        profile=value.profile_name,
        before=value.before_identity,
        after=value.after_identity,
        work=value.work,
        observations=value.observations,
        handoff_identity=value.handoff_identity,
        handoff_work=value.handoff_work,
        source_completed=value.source_completed,
        phase_admitted=False,
        material_admitted=False,
        biological_cases=0,
    )


def complete_load(owner, *, law_id, enabled=False):
    if enabled is not True or any(
        os.environ.get(gate) != "1"
        for gate in (
            RELEASE,
            previous.RELEASE,
            previous.previous.RELEASE,
            previous.previous.mod.RELEASE,
        )
    ):
        raise LoadRejected("Original load remainder stays held", stage="release")
    if type(law_id) is not str or law_id != LAW_ID:
        raise LoadRejected("Explicit complete-load remainder law required", stage="law")
    api = _hook()  # Missing hook refuses before retirement or numerical work.
    if type(owner) is not previous.ConstantsOwner or owner not in previous._ISSUED:
        raise LoadRejected("Actual completed constants owner required", stage="owner")
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise LoadRejected("Reentrant remainder attempt", stage="reentrant")
        if owner in _CONSUMED:
            raise LoadRejected("Remainder attempt consumed", stage="consumed")
        parent = previous._ISSUED[owner]
        context = SimpleNamespace(
            parent_owner=owner,
            parent=parent,
            p=parent.p,
            thread=get_ident(),
            active=True,
            invalid=False,
            validating=False,
            source_error=None,
            capture_errors=(),
            work=[],
            metadata_work=[],
            raw_returns=[],
            raw_return=None,
            raw_entry=None,
            locals={},
            entries=dict(tail=0, ion=0, balance=0, ion_alias=0),
            returns=dict(tail=[], ion=[], balance=[], ion_alias=[]),
            balance_inputs=[],
            stage="admission",
            source_completed=False,
            owner=None,
        )
        _CONSUMED[owner] = context
        _ACTIVE.append(context)
    primary = None
    try:
        context.loaded = _ancestry(parent)
        context.parent_trial = parent.trial
        context.config = vars(context.p)["_conf"]
        context.before_names = tuple(vars(context.p))
        context.internal = parent.locals.get("iu")
        if context.internal is not context.config["internal parameters"] or "_run_sim" in vars(
            context.p
        ):
            raise LoadRejected(
                "Actual retained iu/fresh pre-phase parameter required", stage="source_frame"
            )
        context.original_volume = vars(context.p)["vol_env"]
        context.before_graph = _capture(context)
        context.plan = source_plan()
        context.source_identity = _digest(context.plan)
        context.api = _native(context)
        context.function = _compile(context)
        context.function_bindings = prefix._function_bindings(context.function)
        context.bindings = _bindings()
        context.stage = "original_load_tail_profile"
        # Retain the actual object even when __enter__ refuses; no successful grant is inferred.
        context.grant = vars(api)[HANDOFF_FACTORY](owner, law_id=HANDOFF_LAW, enabled=True)
        with context.grant as grant:
            if type(grant) is not vars(api)[HANDOFF_TYPE] or grant.parameters is not context.p:
                raise ValueError("Actual typed predecessor mutation grant required")
            grant.check()
            with _observe(context):
                _invoke(context)
            context.source_completed = True
            if context.capture_errors or context.invalid:
                raise ValueError("Original reached-output capture/exclusion incomplete")
            grant.check()
            context.profile_name = _outputs(context)
            context.after_graph = _capture(context)
            context.after_cm = _colormaps(context)
        context.grant_record = grant.record
        _history(context)
        context.accounting = _accounting(context)
        context.work.append(
            (
                len(context.work),
                "source_attempt_delegate_instruction_accounting",
                context.accounting,
            )
        )
        value = LoadRecord(
            parent.trial.identity,
            context.source_identity,
            STOP,
            context.profile_name,
            _digest(context.before_graph[1]),
            _digest(context.after_graph[1]),
            tuple(context.work),
            tuple(
                (name, context.entries[name], len(context.returns[name]))
                for name in context.entries
            ),
            True,
            "",
            handoff_identity=context.grant_record.identity,
            handoff_work=context.grant_record.work,
        )
        context.record = replace(value, identity=_digest(record_document(value)))
        context.original_record = context.record
        with _LOCK:
            if (
                _CONSUMED.get(owner) is not context
                or context.invalid
                or _ancestry(parent) is not context.loaded
            ):
                raise ValueError("Original remainder parent/commit epoch changed")
            result = object.__new__(WorldReadyParametersOwner)
            context.owner = result
            _ISSUED[result] = context
        return result
    except BaseException as error:
        primary = error
        context.invalid = True
        context.operation_error = error
        try:
            context.failure_capture = _capture(context)
        except BaseException as secondary:
            context.capture_errors += (("failure_capture", secondary),)
        try:
            error.parameter_load_remainder = context
        except BaseException as secondary:
            context.capture_errors += (("exception_attachment", secondary),)
        raise LoadRejected(
            "Original remainder issued no WorldReady owner",
            stage=context.stage,
            partial=context,
            source_error=context.source_error,
            capture_errors=context.capture_errors,
        ) from primary
    finally:
        context.active = False
        with _LOCK:
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
                context.capture_errors += (
                    ("reservation_release", ValueError("Remainder reservation changed")),
                )
                if primary is None:
                    raise LoadRejected(
                        "Remainder reservation closure failed", stage="closure", partial=context
                    )


def _context(owner):
    if type(owner) is not WorldReadyParametersOwner or owner not in _ISSUED:
        raise LoadRejected("Actual issued complete-load owner required", stage="owner")
    context = _ISSUED[owner]
    if context.owner is not owner:
        raise LoadRejected("Replaced complete-load registry edge", stage="owner")
    return context


def validate_completed_history(owner):
    """Actual closed source history, not permission to read a mutated p."""
    context = _context(owner)
    if (
        context.active
        or context.invalid
        or context.source_error is not None
        or context.thread != get_ident()
        or context.source_completed is not True
        or context.capture_errors
        or _CONSUMED.get(context.parent_owner) is not context
        or context.record is not context.original_record
        or context.record.load_cursor != STOP
        or context.record.source_completed is not True
        or context.record.source_identity != context.source_identity
        or context.record.profile_name != context.profile_name
        or context.record.before_identity != _digest(context.before_graph[1])
        or context.record.after_identity != _digest(context.after_graph[1])
        or context.record.observations
        != tuple(
            (name, context.entries[name], len(context.returns[name])) for name in context.entries
        )
        or context.after_cm.identity != context.parent.parent.original_trial.after_identity
        or context.record.work != tuple(context.work)
        or context.record.handoff_identity != context.grant_record.identity
        or context.record.handoff_work != context.grant_record.work
        or context.accounting != _accounting(context)
        or _digest(record_document(context.record)) != context.record.identity
    ):
        raise LoadRejected(
            "Incomplete/stale complete-load history", stage="history", partial=context
        )
    _history(context)
    return context.record


def _validate(owner):
    context = _context(owner)
    if context.active or context.validating or _ACTIVE:
        raise LoadRejected(
            "Active/overlapping complete-load validation", stage="state", partial=context
        )
    validation = SimpleNamespace(
        invalid=False,
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
    context.validating = True
    registered = False
    primary = release_error = None
    paths = previous.previous.mod.subconfigs.paths
    try:
        with claims._registry(context.loaded.owner):
            if any(stack for stack, _ in _stacks(context)):
                claims._busy(context.loaded.owner, "complete_load_validation_conflict")
            for stack, _ in _stacks(context):
                stack.append(validation.guard if stack is paths._ACTIVE else validation)
            registered = True
            paths._install_audit(validation.guard)
        validate_completed_history(owner)
        if owner in _CONSTRUCTED or "_run_sim" in vars(context.p):
            raise LoadRejected(
                "Parameter owner consumed by construction", stage="constructed", partial=context
            )
        prefix.parameters.inherited._same_graph(_capture(context), context.after_graph)
        previous._same_cm(_colormaps(context), context.after_cm)
        _outputs(context)
        if validation.invalid or validation.guard.invalid:
            raise ValueError("Read-only complete-load validation poisoned")
        return context
    except BaseException as error:
        primary = error
        context.invalid = True
        raise
    finally:
        if registered:
            try:
                with claims._registry(context.loaded.owner):
                    for stack, _ in reversed(_stacks(context)):
                        expected = validation.guard if stack is paths._ACTIVE else validation
                        if not stack or stack[-1] is not expected:
                            raise ValueError("Complete-load validation registry changed")
                        stack.pop()
            except BaseException as error:
                release_error = error
                context.invalid = True
                context.capture_errors += (("validation_release", error),)
        validation.guard.active = False
        context.validating = False
        if primary is None and release_error is not None:
            raise LoadRejected(
                "Complete-load validation closure failed", stage="closure", partial=context
            ) from release_error


def _bindings():
    functions = (
        _digest,
        _source,
        _stores,
        _branches,
        source_plan,
        _hook,
        _ancestry,
        _cached,
        _canonical,
        _balance_wrapper_code,
        _balance_wrapper_bindings,
        _native_helpers,
        _descriptor,
        _native,
        _compile,
        _capture_scalar_type,
        _capture,
        _colormaps,
        _stacks,
        _history,
        _copy_locals,
        _returned,
        _spans,
        _call_sites,
        _wrapper_delegate_span,
        _wrapper_state,
        _check_wrappers,
        _fault,
        _reject_entry,
        _hook_audit,
        _install_hook_audit,
        _inside,
        _frame_role,
        _admit,
        _safe_boundary,
        _recover_hooks,
        _observer_bookkeeping,
        _invoke,
        _observe,
        _observe.__wrapped__,
        _outputs,
        _accounting,
        record_document,
        complete_load,
        _context,
        validate_completed_history,
        _validate,
        _bindings,
        WorldReadyParametersOwner.parameters.fget,
        WorldReadyParametersOwner.record.fget,
    )
    return (), (
        LAW_ID,
        RELEASE,
        BASE_PREDECESSOR_SHA256,
        SOURCE_CANDIDATE_PREDECESSOR_SHA256,
        HANDOFF_PRODUCER_SHA256,
        HANDOFF_LAW,
        HANDOFF_FACTORY,
        HANDOFF_CHECK,
        HANDOFF_TYPE,
        HANDOFF_RECORD_TYPE,
        START,
        STOP,
        LOCAL_KEY,
        MAX_WORK,
        PARAMETER_SHA256,
        PROFILE_NAMES,
        REPLACED,
        _LOCK,
        _ACTIVE,
        _ISSUED,
        _CONSUMED,
        _CONSTRUCTED,
        _HOOK_GUARDS,
        _CALL_TRACING,
        _ObservationStop,
        WorldReadyParametersOwner,
        *previous._bindings()[1],
        *(
            atom
            for function in functions
            for atom in prefix.parameters.inherited.tissue.aliases._atoms(function)
        ),
    )
