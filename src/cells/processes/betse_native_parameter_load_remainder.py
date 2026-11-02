"""Original final Parameters.load source and genuine pre-phase ownership.

The original method dispatch is retained: the compiled tail calls the actual
Parameters._load_ion_profile, which calls the actual _balance_charge. Expected
code is compiled independently from pinned AST, never substituted for a live
method/helper. No source or factory runs at import or metadata preparation.

Execution awaits the explicit predecessor handoff window. The missing hook is
a runtime prerequisite; the complete source/observer/commit path is below.
"""

import ast
import builtins
import copy
import enum
import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock, get_ident
from types import FunctionType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_initializer_constants as previous

LAW_ID = "betse_native_parameter_complete_load_remainder@1"
RELEASE = "CELLS_NATIVE_PARAMETER_LOAD_REMAINDER_RELEASED"
BASE_PREDECESSOR_SHA256 = "3fc51886956ae7f4fc0880b0fb6b5ec25f7c939c14a3ba31e0b012f717774f69"
# Adoption is explicit after Root opens/reviews the predecessor hook window.
HANDOFF_PRODUCER_SHA256 = None
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
    if producer not in (BASE_PREDECESSOR_SHA256, HANDOFF_PRODUCER_SHA256):
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
        hook=dict(
            factory=HANDOFF_FACTORY,
            law=HANDOFF_LAW,
            grant=HANDOFF_TYPE,
            historical_check=HANDOFF_CHECK,
            record=HANDOFF_RECORD_TYPE,
        ),
        local_transport=(LOCAL_KEY, "actual retained iu from completed constants return"),
        native_bodies_copied_or_rewritten=False,
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
        or prefix.parameters.inherited._code(function.__code__)
        != prefix.parameters.inherited._code(expected)
    ):
        raise ValueError("Original executable header/body/namespace changed")
    _cached(function)
    return prefix._function_bindings(function)


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
    ion = vars(cls).get("_load_ion_profile")
    balance = namespace.get("_balance_charge")
    ion_binding = _canonical(
        ion, prefix.parameters._method_code(cls_ast, "_load_ion_profile", str(path)), namespace
    )
    balance_binding = _canonical(
        balance,
        previous.previous.boundary._code(balance_ast, str(path), balance_ast.name),
        namespace,
    )
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
    references.extend((*ion_binding[1], *balance_binding[1], *prefix._function_bindings(getter)[1]))
    references.extend(value for _, value in members)
    return SimpleNamespace(
        ion=ion,
        balance=balance,
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


def _capture(context, *, names=None):
    names = tuple(vars(context.p)) if names is None else names
    birth = context.parent.parent.parent.birth
    runtime = context.parent.parent.parent.runtime
    return prefix.graphs.capture(
        {name: vars(context.p)[name] for name in names if name not in previous.CM_STORES},
        yaml_base=birth.source.yaml,
        runtime_types=runtime.runtime_types,
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
    record = vars(api)[HANDOFF_CHECK](context.grant, original_owner=context.parent_owner)
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


@contextmanager
def _observe(context):
    prior, trace = sys.getprofile(), sys.gettrace()
    roles = {
        context.function.__code__: "tail",
        context.api.ion.__code__: "ion",
        context.api.balance.__code__: "balance",
        context.api.getter.__code__: "ion_alias",
    }
    native = str(prefix.parameters.inherited.tissue.aliases.NATIVE) + "/"

    def profile(frame, event, arg):
        role = roles.get(frame.f_code)
        if event == "call":
            if role and (context.invalid or not context.active or context.thread != get_ident()):
                raise ValueError("Poisoned/foreign load-remainder entry")
            if role:
                context.entries[role] += 1
                if context.entries[role] > dict(tail=1, ion=1, balance=2, ion_alias=5)[role]:
                    raise ValueError("Duplicate original load/profile/helper attempt")
                if role in ("tail", "ion") and frame.f_locals.get("self") is not context.p:
                    raise ValueError("Foreign native parameter receiver")
                if role == "balance":
                    context.raw_entry = (role, frame)
                    local = frame.f_locals
                    concentrations, zs = local.get("concentrations"), local.get("zs")
                    context.balance_inputs.append((concentrations, zs))
                    if (
                        type(concentrations) is not list
                        or type(zs) is not list
                        or not 3 <= len(concentrations) == len(zs) <= 5
                    ):
                        raise ValueError("Original bounded profile helper inputs required")
                if role == "ion_alias" and (
                    frame.f_locals.get("self_descriptor") is not context.api.alias
                    or frame.f_locals.get("self") is not context.p
                ):
                    raise ValueError("Original ion-profile alias/receiver changed")
            if role or frame.f_code.co_filename.startswith(native):
                if len(context.work) >= MAX_WORK:
                    raise ValueError("Bounded original load/profile work exhausted")
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
                context.capture_errors += ((role + "_return", error),)
        if prior is not None:
            if event == "return":
                try:
                    prior(frame, event, arg)
                except BaseException as error:
                    context.capture_errors += (("inherited_return", error),)
            else:
                prior(frame, event, arg)

    try:
        sys.setprofile(profile)
        yield
    finally:
        for name, setter, value in (
            ("profile_restore", sys.setprofile, prior),
            ("trace_restore", sys.settrace, trace),
        ):
            try:
                setter(value)
            except BaseException as error:
                context.capture_errors += ((name, error),)


def _outputs(context):
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
        with vars(api)[HANDOFF_FACTORY](owner, law_id=HANDOFF_LAW, enabled=True) as grant:
            context.grant = grant
            if type(grant) is not vars(api)[HANDOFF_TYPE] or grant.parameters is not context.p:
                raise ValueError("Actual typed predecessor mutation grant required")
            grant.check()
            with _observe(context):
                try:
                    context.function(context.p, **{LOCAL_KEY: context.internal})
                except BaseException as error:
                    context.source_error = error
                    raise
            context.source_completed = True
            if context.capture_errors or context.invalid:
                raise ValueError("Original reached-output capture/exclusion incomplete")
            grant.check()
            context.profile_name = _outputs(context)
            context.after_graph = _capture(context)
            context.after_cm = _colormaps(context)
        context.grant_record = grant.record
        _history(context)
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
        _descriptor,
        _native,
        _compile,
        _capture,
        _colormaps,
        _stacks,
        _history,
        _copy_locals,
        _returned,
        _observe,
        _observe.__wrapped__,
        _outputs,
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
        WorldReadyParametersOwner,
        *previous._bindings()[1],
        *(
            atom
            for function in functions
            for atom in prefix.parameters.inherited.tissue.aliases._atoms(function)
        ),
    )
