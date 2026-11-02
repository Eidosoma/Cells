"""Actual same-p input/source authority before native colormap lookups.

Read-only boundary: compile the next four original statements and retain their
actual aliases, helper, registry and dispatch. No lookup, returned-colormap
ownership, parameter advancement or remaining load/ion/phase admission.
"""

import ast
import builtins
import copy
import hashlib
import sys
from collections.abc import Collection, Container, Iterable, Mapping, Sized
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import get_ident
from types import CodeType, FunctionType, GetSetDescriptorType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_modulators as previous

LAW_ID = "betse_native_parameter_colormap_input_source_boundary@1"
PREVIOUS_SHA256 = "18fa6a451c4dfd7951d6d699e1ce6d3332a8754e126eba40adc18acc453d2dc2"
COLORMAP_SHA256 = "d19b467347ea69ea090241dbee61735bcd57f77777ea3a086c41cef5dcd3f820"
START, STOP = 135, 139
ROLES = (
    ("default_cm", "colormap_diverging_name", "default colormap"),
    ("background_cm", "colormap_sequential_name", "background colormap"),
    ("gj_cm", "colormap_gj_name", "gj colormap"),
    ("network_cm", "colormap_grn_name", "network colormap"),
)
prefix, claims = previous.prefix, previous.claims
_ISSUED, _ACTIVE = WeakKeyDictionary(), []


class ColormapBoundaryRejected(ValueError):
    def __init__(self, reason, *, stage, parent=None, partial=None, capture_errors=()):
        super().__init__(reason)
        self.stage, self.parent, self.partial = stage, parent, partial
        self.capture_errors = tuple(capture_errors)


@dataclass(frozen=True, slots=True)
class Binding:
    parent_trial_identity: str
    source_identity: str
    names: tuple
    registered: tuple
    runtime_files: tuple
    identity: str


class ColormapBoundary:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the actual completed modulator owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live colormap input authority cannot be serialized")

    @property
    def binding(self):
        return _validate(self).binding

    @property
    def parameters(self):
        return _validate(self).p


def _digest(value):
    return previous._digest(value)


def _ast():
    path, cls, load, _ = previous._ast()
    selected = load.body[START:STOP]
    expected = [
        f"self.{store} = mplcolormap.get_colormap(self.{alias})" for store, alias, _ in ROLES
    ]
    if (
        START != previous.STOP
        or [ast.unparse(n) for n in selected] != expected
        or ast.unparse(load.body[STOP]) != "ro = self._conf['results options']"
    ):
        raise ValueError("Original contiguous modulator/colormap/export boundary changed")
    for _, alias, key in ROLES:
        node = next(
            n
            for n in cls.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == alias for t in n.targets)
        )
        if ast.unparse(node.value) != f"yaml_alias(\"['results options']['{key}']\", str)":
            raise ValueError("Original colormap alias declaration changed")
    return path, cls, load, selected


def source_plan():
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PREVIOUS_SHA256:
        raise ValueError("Exact modulator producer required; no silent predecessor adoption")
    parent = previous.source_plan()
    path, _, load, selected = _ast()
    helper = (
        prefix.parameters.inherited.tissue.aliases.NATIVE / "betse/lib/matplotlib/mplcolormap.py"
    )
    if hashlib.sha256(helper.read_bytes()).hexdigest() != COLORMAP_SHA256:
        raise ValueError("Exact original colormap helper source required")
    node = next(
        n
        for n in ast.parse(helper.read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "get_colormap"
    )
    if ast.unparse(node.body[-1]) != "return colormaps[name]":
        raise ValueError("Original registry lookup source changed")
    return dict(
        law=LAW_ID,
        predecessor=PREVIOUS_SHA256,
        native_pins=parent["native_pins"],
        statement_slice=(START, STOP),
        source_lines=(selected[0].lineno, selected[-1].end_lineno),
        source_body_ast=_digest(ast.dump(ast.Module(body=selected, type_ignores=[]))),
        parameter_source=str(path),
        helper_source=str(helper),
        helper_sha256=COLORMAP_SHA256,
        helper_ast=_digest(ast.dump(node)),
        roles=ROLES,
        next_source_line=load.body[STOP].lineno,
        metadata_only=True,
        alias_getters_invoked=False,
        native_lookup_calls=0,
        returned_colormap_objects_owned=False,
        parameter_advanced=False,
        next_prerequisite=(
            "Released original lookups plus complete returned-colormap "
            "state/callback/storage ownership"
        ),
        constants_ions_profiles_Simulator_INIT_admitted=False,
    )


def _refs(parent):
    return tuple(vars(parent)), tuple(vars(parent).values())


def _stacks(context):
    return ((_ACTIVE, context), *previous._stacks(context))


@contextmanager
def _inspection(owner):
    if type(owner) is not previous.ModulatorsOwner or owner not in previous._ISSUED:
        previous._validate(owner)
        raise AssertionError("Unissued modulator validator returned")
    parent = previous._ISSUED[owner]
    context = SimpleNamespace(
        parent_owner=owner,
        parent=parent,
        p=parent.p,
        thread=get_ident(),
        active=True,
        invalid=False,
        work=[],
        capture_errors=(),
        primary=None,
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
    with claims._registry(owner):
        if any(stack for stack, _ in _stacks(context)):
            claims._busy(owner, "colormap_boundary_conflict")
        for stack, value in _stacks(context):
            stack.append(value)
    try:
        previous.subconfigs.paths._install_audit(context.guard)
        context.work.append(("actual_modulator_owner_verification", "attempted"))
        if previous._validate(owner) is not parent:
            raise ValueError("Foreign modulator verification result")
        context.work.append(("actual_modulator_owner_verification", "completed"))
        context.before = _refs(parent)
        yield context
    except BaseException as error:
        context.primary = error
        raise
    finally:
        try:
            if context.invalid or context.guard.invalid or previous._validate(owner) is not parent:
                raise ValueError("Read-only colormap inspection poisoned")
            if hasattr(context, "before"):
                prefix.parameters.inherited._same(_refs(parent), context.before)
        except BaseException as error:
            context.capture_errors += (("inspection_exit", error),)
        try:
            with claims._registry(owner):
                for stack, value in reversed(_stacks(context)):
                    if not stack or stack[-1] is not value:
                        raise ValueError("Colormap inspection registry changed")
                    stack.pop()
        except BaseException as error:
            context.capture_errors += (("inspection_release", error),)
        context.active = context.guard.active = False
        if context.primary is not None:
            try:
                context.primary.colormap_boundary = context
            except BaseException as error:
                context.capture_errors += (("exception_evidence", error),)
        elif context.capture_errors:
            context.invalid = True
            raise ColormapBoundaryRejected(
                "Read-only inspection issued no authority",
                stage="inspection_exit",
                parent=owner,
                partial=context,
                capture_errors=context.capture_errors,
            ) from context.capture_errors[0][1]


def _configuration(parent):
    cls = parent.birth.source.cls
    if type(parent.p) is not cls or vars(parent.p).get("_conf") is not parent.birth.p._conf:
        raise ValueError("Actual issued parameter/class/configuration required")
    cfg = vars(parent.p)["_conf"]["results options"]
    names, objects = [], [cls, cfg]
    for _, alias, key in ROLES:
        if alias in vars(parent.p):
            raise ValueError("A supplied colormap alias value cannot replace the native descriptor")
        descriptor = vars(cls).get(alias)
        if descriptor is None or not hasattr(type(descriptor), "__get__"):
            raise ValueError("Actual retained native colormap alias descriptor required")
        raw = cfg[key]
        if not isinstance(raw, str):
            raise ColormapBoundaryRejected(
                "Native str alias input authority unavailable", stage="alias_input"
            )
        names.append(raw)
        objects.extend((descriptor, type(descriptor), raw))
        objects.extend(prefix.parameters.inherited.tissue._surface(type(descriptor)))
    return tuple(names), ((), tuple(objects))


def _compile(parent):
    original = parent.function
    prefix._function_bindings(original)
    module = parent.birth.source.modules["betse.science.parameters"]
    if original.__globals__ is not vars(module):
        raise ValueError("Actual original parameter namespace required")
    path, cls, _, selected = _ast()
    cls = copy.deepcopy(cls)
    prefix.parameters.inherited._method(cls, "load").body = copy.deepcopy(selected)
    code = prefix.parameters._method_code(cls, "load", str(path))
    if code.co_freevars:
        raise ValueError("Colormap slice unexpectedly requires a closure")
    function = FunctionType(code, original.__globals__, original.__name__, None, None)
    if function.__builtins__ is not original.__builtins__:
        raise ValueError("Colormap source cached builtins changed")
    return function, original


def _code(node, filename, name):
    value = compile(
        ast.Module(body=[copy.deepcopy(node)], type_ignores=[]), filename, "exec", dont_inherit=True
    )
    return next(c for c in value.co_consts if type(c) is CodeType and c.co_name == name)


def _undecorated(function, module, path, node, *, decorators=()):
    """Authenticate the executable function itself, never a spoofed wrapped core."""
    if (
        type(function) is not FunctionType
        or function.__globals__ is not vars(module)
        or function.__name__ != node.name
        or function.__closure__ is not None
        or "__wrapped__" in vars(function)
        or tuple(ast.unparse(value) for value in node.decorator_list) != decorators
        or prefix.parameters.inherited._code(function.__code__)
        != prefix.parameters.inherited._code(_code(node, str(path), node.name))
    ):
        raise ValueError("Original undecorated helper outer executable/globals required")

    def default(value):
        if isinstance(value, ast.Constant) and type(value.value) in (type(None), bool, int, str):
            return value.value
        if isinstance(value, ast.Name) and value.id in ("ValueError", "KeyError"):
            original = vars(builtins)[value.id]
            if value.id in vars(module) or function.__builtins__.get(value.id) is not original:
                raise ValueError("Original helper default builtin resolution changed")
            return original
        raise ValueError("Undeclared original helper default")

    def same(actual, expected):
        if type(expected) is type:
            return actual is expected
        return type(actual) is type(expected) and actual == expected

    expected = tuple(default(value) for value in node.args.defaults)
    actual = function.__defaults__
    if (
        actual is not None
        if not expected
        else type(actual) is not tuple
        or len(actual) != len(expected)
        or any(not same(a, b) for a, b in zip(actual, expected, strict=True))
    ):
        raise ValueError("Original undecorated helper positional defaults changed")
    keywords = {
        arg.arg: default(value)
        for arg, value in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
        if value is not None
    }
    actual_keywords = function.__kwdefaults__
    if (
        actual_keywords is not None
        if not keywords
        else type(actual_keywords) is not dict
        or tuple(actual_keywords) != tuple(keywords)
        or any(not same(actual_keywords[name], value) for name, value in keywords.items())
    ):
        raise ValueError("Original undecorated helper keyword defaults changed")
    return (prefix._function_bindings(function),)


def _canonical(function, module, path, node):
    if not node.decorator_list:
        return _undecorated(function, module, path, node)
    if type(function) is not FunctionType:
        raise ValueError("Exact original colormap helper callable required")
    core = prefix.parameters.inherited._chain(function)[-1]
    expected = _code(node, str(path), node.name)
    if core.__globals__ is not vars(module) or prefix.parameters.inherited._code(
        core.__code__
    ) != prefix.parameters.inherited._code(expected):
        raise ValueError("Original colormap helper executable/globals changed")
    return tuple(
        prefix._function_bindings(fn) for fn in prefix.parameters.inherited._chain(function)
    )


def _registry_surface(kind, cm):
    """Check class dispatch before touching any registry instance attribute."""
    if type(cm) is not ModuleType or type(kind) is not type(Mapping):
        raise ValueError("Original registry metaclass required")
    namespace = type.__getattribute__(kind, "__dict__")
    module_name = vars(cm).get("__name__")
    declared_module = namespace.get("__module__")
    bases = type.__getattribute__(kind, "__bases__")
    expected = (kind, Mapping, Collection, Sized, Iterable, Container, object)
    mro = type.__getattribute__(kind, "__mro__")
    if (
        vars(cm).get("Mapping") is not Mapping
        or type(module_name) is not str
        or type(declared_module) is not str
        or declared_module != module_name
        or type.__getattribute__(kind, "__name__") != "ColormapRegistry"
        or len(bases) != 1
        or bases[0] is not Mapping
        or len(mro) != len(expected)
        or any(a is not b for a, b in zip(mro, expected, strict=True))
    ):
        raise ValueError("Original registry class/MRO association changed")
    descriptor = namespace.get("__dict__")
    if (
        type(descriptor) is not GetSetDescriptorType
        or descriptor.__objclass__ is not kind
        or descriptor.__name__ != "__dict__"
    ):
        raise ValueError("Original registry instance dictionary descriptor changed")
    labels, objects = [], [kind, cm, descriptor]
    for base in mro:
        fields = type.__getattribute__(base, "__dict__")
        if (
            "_cmaps" in fields
            or "__getattr__" in fields
            or (base is not object and "__getattribute__" in fields)
            or (base is not object and "__class__" in fields)
            or (base is not kind and "__dict__" in fields)
        ):
            raise ValueError("Foreign registry attribute dispatch/descriptor")
        # Retain the actual surfaces, not just equality of the selected mapping.
        labels.append(tuple(fields))
        objects.extend((base, *fields.values()))
        for value in fields.values():
            if type(value) is FunctionType:
                objects.extend(
                    (
                        value.__code__,
                        value.__globals__,
                        value.__builtins__,
                        value.__defaults__,
                        value.__kwdefaults__,
                        value.__closure__,
                    )
                )
    return tuple(labels), tuple(objects)


def _registry_state(registry, kind, cm):
    surface = _registry_surface(kind, cm)
    if type(registry) is not kind:
        raise ValueError("Original registry instance required")
    namespace = object.__getattribute__(registry, "__dict__")
    if (
        type(namespace) is not dict
        or "__getitem__" in namespace
        or type(namespace.get("_cmaps")) is not dict
    ):
        raise ValueError("Original registry instance mapping/dispatch changed")
    return namespace, namespace["_cmaps"], surface


def _native(parent):
    parameter_module = parent.birth.source.modules["betse.science.parameters"]
    module = vars(parameter_module).get("mplcolormap")
    path = prefix.parameters.inherited.tissue.aliases.NATIVE / "betse/lib/matplotlib/mplcolormap.py"
    if (
        type(module) is not ModuleType
        or sys.modules.get("betse.lib.matplotlib.mplcolormap") is not module
        or Path(vars(module).get("__file__", "")).resolve() != path
        or parent.runtime.runtime_files.get(str(path)) != COLORMAP_SHA256
    ):
        raise ColormapBoundaryRejected(
            "Actual born mplcolormap runtime required", stage="native_runtime"
        )
    if hashlib.sha256(path.read_bytes()).hexdigest() != COLORMAP_SHA256:
        raise ValueError("Native colormap runtime source changed")
    root, cm = sys.modules.get("matplotlib"), sys.modules.get("matplotlib.cm")
    if type(root) is not ModuleType or type(cm) is not ModuleType:
        raise ColormapBoundaryRejected(
            "Actual imported Matplotlib registry authority absent", stage="registry"
        )
    registry = vars(module).get("colormaps")
    kind = vars(cm).get("ColormapRegistry")
    if vars(root).get("colormaps") is not registry:
        raise ValueError("Actual original Matplotlib registry/dispatch required")
    registry_namespace, mapping, registry_surface = _registry_state(registry, kind, cm)
    helper = vars(module).get("get_colormap")
    getter = vars(kind).get("__getitem__")
    node = next(
        n
        for n in ast.parse(path.read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "get_colormap"
    )
    helper_bindings = _canonical(helper, module, path, node)
    cm_path = Path(vars(cm).get("__file__", "")).resolve(strict=True)
    if cm_path.suffix != ".py":
        raise ValueError("Readable original Matplotlib registry source required")
    cls = prefix.parameters.inherited._class(ast.parse(cm_path.read_bytes()), "ColormapRegistry")
    method = prefix.parameters.inherited._method(cls, "__getitem__")
    getter_bindings = _canonical(getter, cm, cm_path, method)
    return SimpleNamespace(
        module=module,
        helper=helper,
        registry=registry,
        kind=kind,
        mapping=mapping,
        registry_namespace=registry_namespace,
        registry_surface=registry_surface,
        helper_bindings=helper_bindings,
        getter=getter,
        getter_bindings=getter_bindings,
        mpl=root,
        cm=cm,
        files=(
            (str(path), COLORMAP_SHA256),
            (str(cm_path), hashlib.sha256(cm_path.read_bytes()).hexdigest()),
        ),
    )


def _native_bindings(api):
    namespace, mapping, surface = _registry_state(api.registry, api.kind, api.cm)
    if namespace is not api.registry_namespace or mapping is not api.mapping:
        raise ValueError("Original registry dictionary/mapping identity changed")
    prefix.parameters.inherited._same(surface, api.registry_surface)
    # Entries are opaque historical identities here, never result/state authority.
    rows = tuple(api.mapping.items())
    objects = [
        api.module,
        api.helper,
        api.registry,
        api.kind,
        api.mapping,
        api.getter,
        api.mpl,
        api.cm,
        namespace,
        *surface[1],
    ]
    for key, value in rows:
        objects.extend((key, value))
    for bindings in (*api.helper_bindings, *api.getter_bindings):
        objects.extend(bindings[1])
    return (tuple(key for key, _ in rows), api.files, surface[0]), tuple(objects)


def binding_record(value):
    return dict(
        law=LAW_ID,
        parent=value.parent_trial_identity,
        source=value.source_identity,
        names=value.names,
        registered=value.registered,
        runtime_files=value.runtime_files,
        metadata_only=True,
        lookups=0,
        parameter_advanced=False,
        result_objects_owned=False,
    )


def prepare(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise ColormapBoundaryRejected(
            "Explicit colormap input law required", stage="law", parent=owner
        )
    with _inspection(owner) as claim:
        parent = claim.parent
        plan = source_plan()
        claim.work.append(("original_alias_configuration_binding", "attempted"))
        names, aliases = _configuration(parent)
        claim.work.append(("original_alias_configuration_binding", "completed"))
        function, original = _compile(parent)
        claim.work.append(("literal_four_statement_compilation", "completed_not_executed"))
        api = _native(parent)
        native_bindings = _native_bindings(api)
        value = Binding(
            parent.trial.identity,
            _digest(plan),
            names,
            tuple(name in api.mapping for name in names),
            api.files,
            "",
        )
        value = replace(value, identity=_digest(binding_record(value)))
        boundary = object.__new__(ColormapBoundary)
        context = SimpleNamespace(
            owner=boundary,
            parent_owner=owner,
            parent=parent,
            p=parent.p,
            before=_refs(parent),
            claim=claim,
            binding=value,
            aliases=aliases,
            function=function,
            original=original,
            function_bindings=prefix._function_bindings(function),
            original_bindings=prefix._function_bindings(original),
            api=api,
            native_bindings=native_bindings,
            source_identity=_digest(plan),
            bindings=_bindings(),
            work=claim.work,
        )
        _ISSUED[boundary] = context
        _check(context)
        return boundary


def _check(context):
    if (
        previous._ISSUED.get(context.parent_owner) is not context.parent
        or context.p is not context.parent.p
        or context.claim.invalid
        or context.claim.guard.invalid
        or context.claim.capture_errors
    ):
        raise ValueError("Original colormap boundary/parent/inspection changed")
    prefix.parameters.inherited._same(_refs(context.parent), context.before)
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    if _digest(source_plan()) != context.source_identity:
        raise ValueError("Issued colormap source domain changed")
    if context.binding.source_identity != context.source_identity:
        raise ValueError("Colormap binding source changed")
    if _digest(binding_record(context.binding)) != context.binding.identity:
        raise ValueError("Colormap binding record changed")
    names, aliases = _configuration(context.parent)
    if any(a is not b for a, b in zip(names, context.binding.names, strict=True)):
        raise ValueError("Original raw colormap name objects changed")
    prefix.parameters.inherited._same(aliases, context.aliases)
    function, original = _compile(context.parent)
    if (
        original is not context.original
        or function.__code__ != context.function.__code__
        or function.__globals__ is not context.function.__globals__
    ):
        raise ValueError("Original colormap executable association changed")
    prefix.parameters.inherited._same(
        prefix._function_bindings(context.function), context.function_bindings
    )
    prefix.parameters.inherited._same(
        prefix._function_bindings(original), context.original_bindings
    )
    prefix.parameters.inherited._same(
        _native_bindings(_native(context.parent)), context.native_bindings
    )
    if context.binding.registered != tuple(n in context.api.mapping for n in names):
        raise ValueError("Original missing/registered lookup classification changed")


def _validate(owner):
    if type(owner) is not ColormapBoundary or owner not in _ISSUED:
        raise ColormapBoundaryRejected("Actual issued colormap boundary required", stage="owner")
    context = _ISSUED[owner]
    with _inspection(context.parent_owner):
        _check(context)
    return context


def require_lookup(owner):
    context = _validate(owner)
    raise ColormapBoundaryRejected(
        "Original lookup execution and closed returned-colormap ownership remain required",
        stage="lookup_result_prerequisite",
        parent=context.parent_owner,
        partial=dict(
            binding=binding_record(context.binding),
            current_parameter_advanced=False,
            source_lines=(1007, 1014),
            next_after_complete_lookup=1017,
            arbitrary_callback_or_supplied_colormap_admitted=False,
        ),
    )


def _bindings():
    functions = (
        _digest,
        _ast,
        source_plan,
        _refs,
        _stacks,
        _inspection,
        _inspection.__wrapped__,
        _configuration,
        _compile,
        _code,
        _undecorated,
        _canonical,
        _registry_surface,
        _registry_state,
        _native,
        _native_bindings,
        binding_record,
        prepare,
        _check,
        _validate,
        require_lookup,
        _bindings,
        ColormapBoundary.__init__,
        ColormapBoundary.__reduce_ex__,
        ColormapBoundary.parameters.fget,
        ColormapBoundary.binding.fget,
    )
    return (), (
        LAW_ID,
        PREVIOUS_SHA256,
        COLORMAP_SHA256,
        START,
        STOP,
        ROLES,
        _ISSUED,
        _ACTIVE,
        ColormapBoundary,
        ColormapBoundaryRejected,
        Binding,
        get_ident,
        *previous._bindings()[1],
        *(
            atom
            for fn in functions
            for atom in prefix.parameters.inherited.tissue.aliases._atoms(fn)
        ),
    )
