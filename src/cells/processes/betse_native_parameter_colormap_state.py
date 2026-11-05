"""Read-only selected colormap registry state, never lookup/return authority.

Derive entries from the issued same-p input boundary. Reuse the closed graph
encoder for data/arrays; retain live object and callback/source associations
separately. No evaluator, lookup, constructor, decoder or parameter write.
"""

import ast
import builtins
import dis
import functools
import hashlib
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from types import (
    BuiltinFunctionType,
    CodeType,
    FunctionType,
    MethodType,
    ModuleType,
    SimpleNamespace,
)
from weakref import WeakKeyDictionary

import numpy as np

from cells.processes import betse_native_parameter_colormaps as previous
from cells.processes import betse_normal_ecm_molecule_checkpoint_codec as codec

LAW_ID = "betse_native_parameter_selected_colormap_registry_state@1"
PREVIOUS_SHA256 = "8b7be0abed085d60b14abe8429684e2025fce78d64cc66f94eeffcc94af5dde1"
MAX_OBJECTS, MAX_DEPTH, MAX_CALLBACKS = 25000, 64, 256
NUMPY_SCALARS = tuple(
    cls for cls in np.sctypeDict.values() if type(cls) is type and issubclass(cls, np.generic)
)
BUILTIN_CLASSES = tuple(
    cls for cls in vars(builtins).values() if type(cls) is type and not cls.__flags__ & (1 << 9)
)
_ISSUED, _ACTIVE = WeakKeyDictionary(), []
prefix = previous.prefix


class ColormapStateRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None, source_error=None):
        super().__init__(reason)
        self.stage, self.partial, self.source_error = stage, partial, source_error


@dataclass(frozen=True, slots=True)
class Record:
    boundary_identity: str
    source_identity: str
    graph_identity: str
    role_entries: tuple
    array_copies: int
    callback_inspections: int
    metadata_work: tuple
    runtime_files: tuple
    identity: str


class ColormapRegistryState:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use capture_registry from an actual issued boundary")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live registry state is not native persistence")

    @property
    def record(self):
        return _validate(self).record


def _digest(value):
    return previous._digest(value)


def _one_of(value, choices):
    return any(value is choice for choice in choices)


def _file(path):
    if type(path) is not str:
        raise ValueError("Declared source pathname string required")
    path = Path(path).resolve(strict=True)
    with path.open("rb") as stream:
        return str(path), hashlib.file_digest(stream, "sha256").hexdigest()


def source_plan():
    if _file(previous.__file__)[1] != PREVIOUS_SHA256:
        raise ValueError("Exact explicitly bound colormap input producer required")
    return dict(
        law=LAW_ID,
        input_source=previous.source_plan(),
        input_producer=PREVIOUS_SHA256,
        data_encoder=(
            "src/cells/processes/betse_normal_ecm_molecule_checkpoint_codec.py",
            _file(codec.__file__)[1],
        ),
        max_objects=MAX_OBJECTS,
        max_depth=MAX_DEPTH,
        max_callbacks=MAX_CALLBACKS,
        selected_registry_only=True,
        callback_scope=(
            "canonical module functions/class methods and partials; local closures refuse"
        ),
        array_scope="unchanged closed encoder layout/storage policy; unsupported views refuse",
        callback_evaluations=0,
        lookups=0,
        constructors=0,
        parameter_advanced=False,
        returned_objects_owned=False,
        native_pickle_or_decode=False,
        INIT_admitted=False,
    )


def _classes(bound):
    colors = sys.modules.get("matplotlib.colors")
    if type(colors) is not ModuleType:
        raise ColormapStateRejected(
            "Actual retained Matplotlib colors module absent", stage="runtime"
        )
    filename, pin = _file(vars(colors)["__file__"])
    if not filename.endswith(".py"):
        raise ValueError("Readable Matplotlib class source required")
    tree = ast.parse(Path(filename).read_bytes())
    kinds, objects = [], [colors, vars(colors)]
    for name in ("Colormap", "LinearSegmentedColormap", "ListedColormap"):
        cls = vars(colors).get(name)
        if type(cls) is not type or cls.__module__ != vars(colors)["__name__"]:
            raise ValueError("Actual canonical colormap class required")
        if name != "ListedColormap" and vars(bound.api.module).get(name) is not cls:
            raise ValueError("Native helper/colormap class association changed")
        node = prefix.parameters.inherited._class(tree, name)
        init = vars(cls).get("__init__")
        if init is not None:
            function = prefix.parameters.inherited._chain(init)[-1]
            method = prefix.parameters.inherited._method(node, "__init__")
            expected = previous._context_code(method, filename)
            if (
                function.__globals__ is not vars(colors)
                or function.__code__.co_qualname != expected.co_qualname
                or prefix.parameters.inherited._code(function.__code__)
                != prefix.parameters.inherited._code(expected)
            ):
                raise ValueError("Colormap constructor source changed")
        kinds.append(cls)
        objects.extend(prefix.parameters.inherited.tissue._surface(cls))
    return tuple(kinds), ((filename, pin),), ((), tuple(objects))


def _global_bindings(function):
    base = prefix._function_bindings(function)
    labels, objects = list(base[0]), list(base[1])
    instructions = tuple(dis.get_instructions(function))
    for index, instruction in enumerate(instructions):
        if instruction.opname != "LOAD_GLOBAL":
            continue
        name = instruction.argval
        value = function.__globals__.get(name, function.__builtins__.get(name))
        for following in instructions[index + 1 :]:
            if following.opname != "LOAD_ATTR" or type(value) is not ModuleType:
                break
            key = following.argval
            if key not in vars(value):
                raise ValueError("Unowned lazy callback global attribute")
            labels.append((name, key))
            value = vars(value)[key]
            objects.append(value)
    return tuple(labels), tuple(objects)


def _global_values(function):
    values = {}
    instructions = tuple(dis.get_instructions(function))
    for index, instruction in enumerate(instructions):
        if instruction.opname != "LOAD_GLOBAL":
            continue
        name = instruction.argval
        value = function.__globals__.get(name, function.__builtins__.get(name))
        values[name] = value
        for following in instructions[index + 1 :]:
            if following.opname != "LOAD_ATTR" or type(value) is not ModuleType:
                break
            key = following.argval
            if key not in vars(value):
                raise ValueError("Unowned lazy callback global attribute")
            name += "." + key
            value = vars(value)[key]
            values[name] = value
    return values


def _member(root, target):
    seen, pending = set(), [root]
    while pending:
        value = pending.pop()
        if value is target:
            return True
        if id(value) in seen:
            continue
        seen.add(id(value))
        if len(seen) > MAX_OBJECTS:
            raise ValueError("Bounded callback source membership exhausted")
        if type(value) is dict:
            pending.extend(dict.values(value))
        elif _one_of(type(value), (list, tuple)):
            pending.extend(value)
    return False


def _function(function, kinds):
    if type(function) is not FunctionType or function.__closure__:
        raise ValueError("Unowned callback or factory-local closure")
    module_name = function.__module__
    if type(module_name) is not str or not module_name.startswith("matplotlib."):
        raise ValueError("Callback lacks actual Matplotlib module authority")
    module = sys.modules.get(module_name)
    actual_name = vars(module).get("__name__") if type(module) is ModuleType else None
    if type(actual_name) is not str or actual_name != module_name:
        raise ValueError("Callback lacks actual Matplotlib module authority")
    if function.__globals__ is not vars(module):
        raise ValueError("Callback lacks actual Matplotlib module authority")
    filename, pin = _file(vars(module)["__file__"])
    if filename != str(Path(function.__code__.co_filename).resolve()):
        raise ValueError("Callback code/source path mismatch")
    tree = ast.parse(Path(filename).read_bytes())
    # Module functions/lambdas must be retained by that actual module's data.
    # Bound class methods use the exact approved actual class surface instead.
    declared = _member(vars(module), function)
    if not declared:
        declared = any(
            function
            is (value.__func__ if _one_of(type(value), (classmethod, staticmethod)) else value)
            for cls in kinds
            for value in vars(cls).values()
        )
    if not declared:
        raise ValueError("Foreign callback identity outside declared module/class data")
    candidates = []
    code = compile(tree, filename, "exec", dont_inherit=True)

    def visit(value):
        if type(value) is CodeType:
            candidates.append(value)
            for constant in value.co_consts:
                visit(constant)

    visit(code)
    if not any(
        prefix.parameters.inherited._code(c) == prefix.parameters.inherited._code(function.__code__)
        for c in candidates
    ):
        raise ValueError("Callback executable does not match retained source")
    return (filename, pin), _global_bindings(function)


class _Capture:
    def __init__(self, kinds):
        self.kinds, self.objects, self.memo = kinds, [], {}
        self.callbacks, self.bindings, self.files = 0, [], set()
        self.encoder = codec.Encoder()

    def globals(self, function, depth):
        result = {}
        for name, value in _global_values(function).items():
            kind = type(value)
            if kind is ModuleType:
                module_name = vars(value).get("__name__")
                if type(module_name) is not str or not (
                    module_name in ("numpy", "math", "builtins")
                    or module_name.startswith(("numpy.", "matplotlib."))
                ):
                    raise ValueError("Unowned callback global module")
                filename = vars(value).get("__file__")
                if filename is not None:
                    self.files.add(_file(filename))
                result[name] = dict(
                    tag="module_reference",
                    name=module_name,
                    file=None if filename is None else _file(filename),
                )
            elif kind is BuiltinFunctionType:
                receiver = value.__self__
                if receiver is not None and type(receiver) is not ModuleType:
                    raise ValueError("Unowned builtin callback receiver")
                self.objects.append(value)
                result[name] = dict(
                    tag="builtin_reference", module=value.__module__, name=value.__qualname__
                )
            elif kind is np.ufunc:
                self.objects.append(value)  # Immutable reached builtin identity.
                result[name] = dict(
                    tag="ufunc_reference",
                    name=value.__name__,
                    nin=value.nin,
                    nout=value.nout,
                    signatures=value.types,
                )
            elif _one_of(value, BUILTIN_CLASSES):
                self.objects.append(value)
                result[name] = dict(
                    tag="builtin_class_reference", module=value.__module__, name=value.__qualname__
                )
            else:
                # Includes mutable coefficient data and Python helper functions.
                # Local recursion/unsupported helpers refuse under the encoder.
                result[name] = self.walk(value, depth + 1)
        return result

    def walk(self, value, depth=0):
        if depth > MAX_DEPTH or len(self.objects) > MAX_OBJECTS:
            raise ValueError("Bounded selected colormap state exhausted")
        kind = type(value)
        if value is None or _one_of(kind, (str, bytes, int, float, bool)):
            self.objects.append(value)
            return value
        if id(value) in self.memo:
            return self.memo[id(value)]
        self.objects.append(value)
        if kind is np.ndarray or _one_of(kind, NUMPY_SCALARS):
            result = dict(tag="array" if kind is np.ndarray else "scalar", value=value)
            self.memo[id(value)] = result
            if kind is np.ndarray:
                self.objects.append(value.base)
                result.update(
                    shape=value.shape,
                    strides=value.strides,
                    writeable=bool(value.flags.writeable),
                    data_pointer=value.__array_interface__["data"][0],
                )
            return result  # Original array passes to the unchanged encoder.
        if _one_of(kind, (dict, list, tuple)):
            result = {} if kind is dict else []
            self.memo[id(value)] = result
            if kind is dict:
                for key, item in value.items():
                    result[self.walk(key, depth + 1)] = self.walk(item, depth + 1)
            else:
                result.extend(self.walk(item, depth + 1) for item in value)
                if kind is tuple:
                    result = tuple(result)
                    self.memo[id(value)] = result
            return result
        result = {}
        self.memo[id(value)] = result
        if _one_of(kind, self.kinds):
            if any(vars(cls).get("__slots__") for cls in kind.__mro__):
                raise ValueError("Unowned colormap slots")
            result.update(
                tag="colormap",
                kind=kind.__name__,
                state=self.walk(object.__getattribute__(value, "__dict__"), depth + 1),
            )
        elif _one_of(value, self.kinds) or _one_of(value, (str, int, float, bool)):
            result.update(tag="class_reference", module=value.__module__, name=value.__qualname__)
        elif kind is FunctionType:
            self.callbacks += 1
            if self.callbacks > MAX_CALLBACKS:
                raise ValueError("Bounded callback declarations exhausted")
            source, bindings = _function(value, self.kinds)
            self.files.add(source)
            self.bindings.append(bindings)
            result.update(
                tag="source_callback",
                name=value.__qualname__,
                source=source,
                defaults=self.walk(value.__defaults__, depth + 1),
                keyword_defaults=self.walk(value.__kwdefaults__, depth + 1),
                attributes=self.walk(value.__dict__, depth + 1),
                annotations=self.walk(value.__annotations__, depth + 1),
                globals=self.globals(value, depth + 1),
            )
        elif kind is MethodType:
            if not _one_of(value.__self__, self.kinds):
                raise ValueError("Unowned callback receiver")
            result.update(
                tag="class_method",
                receiver=self.walk(value.__self__, depth + 1),
                function=self.walk(value.__func__, depth + 1),
            )
        elif kind is functools.partial:
            result.update(
                tag="partial",
                function=self.walk(value.func, depth + 1),
                args=self.walk(value.args, depth + 1),
                keywords=self.walk(value.keywords, depth + 1),
                attributes=self.walk(value.__dict__, depth + 1),
            )
        else:
            raise ValueError("Unowned selected colormap state")
        return result

    def capture(self, roots):
        # Role roots are a fresh observation envelope, not a native container.
        data = {key: self.walk(value) for key, value in roots.items()}
        tree = self.encoder.capture(data)
        return SimpleNamespace(
            tree=tree,
            arrays=self.encoder.arrays,
            identity=self.encoder.seal(tree),
            encoder=self.encoder,
            objects=tuple(self.objects),
            bindings=tuple(self.bindings),
            files=tuple(sorted(self.files)),
            callbacks=self.callbacks,
            array_copies=len(self.encoder.arrays),
        )


def _observe(bound, holder):
    kinds, files, bindings = _classes(bound)
    roots, roles = {}, []
    for store, alias, _ in previous.ROLES:
        index = [r[0] for r in previous.ROLES].index(store)
        name = bound.binding.names[index]
        if name in bound.api.mapping:
            value = bound.api.mapping[name]
            if not _one_of(type(value), kinds):
                raise ValueError("Registry entry has unowned colormap type")
            roots[store] = value
            roles.append((store, alias, name, True))
        else:
            roots[store] = None
            roles.append((store, alias, name, False))
    capture = _Capture(kinds)
    holder.partial_capture = capture
    try:
        result = capture.capture(roots)
        result.classes, result.class_files, result.class_bindings = kinds, files, bindings
        result.roles = tuple(roles)
        return result
    except BaseException:
        raise  # The owned holder already retains partial arrays/nodes/refs.


def record_document(value):
    return dict(
        law=LAW_ID,
        boundary=value.boundary_identity,
        source=value.source_identity,
        graph=value.graph_identity,
        roles=value.role_entries,
        array_copies=value.array_copies,
        callback_inspections=value.callback_inspections,
        metadata_work=value.metadata_work,
        runtime_files=value.runtime_files,
        registry_only=True,
        callback_evaluations=0,
        original_lookups=0,
        parameter_advanced=False,
        returned_object_authority=False,
    )


def _same(actual, retained):
    if (
        retained.encoder.arrays is not retained.arrays
        or retained.encoder.nodes is not retained.tree["nodes"]
        or retained.encoder.seal(retained.tree) != retained.identity
    ):
        raise ValueError("Retained closed colormap evidence changed")
    if actual.identity != retained.identity or len(actual.objects) != len(retained.objects):
        raise ValueError("Selected registry data/graph changed")
    if any(a is not b for a, b in zip(actual.objects, retained.objects, strict=True)):
        raise ValueError("Selected registry object/storage/alias association changed")
    prefix.parameters.inherited._same(actual.class_bindings, retained.class_bindings)
    if actual.class_files != retained.class_files or actual.files != retained.files:
        raise ValueError("Colormap/callback source bytes changed")
    if len(actual.bindings) != len(retained.bindings):
        raise ValueError("Callback count changed")
    for current, old in zip(actual.bindings, retained.bindings, strict=True):
        prefix.parameters.inherited._same(current, old)


def _bound(boundary):
    if type(boundary) is not previous.ColormapBoundary or boundary not in previous._ISSUED:
        previous._validate(boundary)
        raise AssertionError("Unissued input validator returned")
    return previous._ISSUED[boundary]


def capture_registry(boundary, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise ColormapStateRejected("Explicit selected-registry law required", stage="law")
    bound = _bound(boundary)
    if _ACTIVE:
        _ACTIVE[-1].invalid = True
        raise ColormapStateRejected("Overlapping registry capture refused", stage="overlap")
    context = SimpleNamespace(
        boundary=boundary,
        bound=bound,
        active=True,
        invalid=False,
        stage="registry_capture",
        work=[],
        validations=[],
        source_error=None,
        validating=False,
        partial_capture=None,
    )
    _ACTIVE.append(context)
    try:
        with previous._inspection(bound.parent_owner):
            previous._check(bound)
            context.plan = source_plan()
            context.work.append(("registry_state_inspection", "attempted"))
            context.capture = _observe(bound, context)
            context.work.append(("registry_state_inspection", "completed_no_evaluation"))
            context.work.append(("closed_encoder_array_copies", context.capture.array_copies))
            context.work.append(("source_callback_inspections", context.capture.callbacks))
            previous._check(bound)
            if context.invalid:
                raise ValueError("Registry inspection poisoned")
            record = Record(
                bound.binding.identity,
                _digest(context.plan),
                context.capture.identity,
                context.capture.roles,
                context.capture.array_copies,
                context.capture.callbacks,
                tuple(context.work),
                tuple(sorted(set(context.capture.class_files) | set(context.capture.files))),
                "",
            )
            record = replace(record, identity=_digest(record_document(record)))
            context.record = context.original_record = record
            context.bindings = _bindings()
            owner = object.__new__(ColormapRegistryState)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
    except BaseException as error:
        context.source_error = error
        context.invalid = True
        raise ColormapStateRejected(
            "Registry capture issued no state authority",
            stage=context.stage,
            partial=context,
            source_error=error,
        ) from error
    finally:
        context.active = False
        if _ACTIVE and _ACTIVE[-1] is context:
            _ACTIVE.pop()


def _validate(owner):
    if type(owner) is not ColormapRegistryState or owner not in _ISSUED:
        raise ColormapStateRejected("Actual issued registry state required", stage="owner")
    context = _ISSUED[owner]
    if context.active or context.invalid or context.validating or _ACTIVE:
        raise ColormapStateRejected("Closed/poisoned/overlapping registry state", stage="state")
    context.validating = True
    context.validations.append(("registry_state_verification", "attempted"))
    try:
        bound = _bound(context.boundary)
        if bound is not context.bound:
            raise ValueError("Original input boundary changed")
        with previous._inspection(bound.parent_owner):
            previous._check(bound)
            prefix.parameters.inherited._same(_bindings(), context.bindings)
            if _digest(source_plan()) != context.record.source_identity:
                raise ValueError("Registry-state source domain changed")
            if (
                context.record is not context.original_record
                or _digest(record_document(context.record)) != context.record.identity
                or context.record.boundary_identity != bound.binding.identity
            ):
                raise ValueError("Original registry record association changed")
            actual = _observe(bound, context)
            _same(actual, context.capture)
        context.validations.append(
            (
                "registry_state_verification",
                "completed_no_evaluation",
                actual.array_copies,
                actual.callbacks,
            )
        )
        return context
    except BaseException as error:
        context.invalid = True
        raise ColormapStateRejected(
            "Stale selected registry state", stage="drift", partial=context, source_error=error
        ) from error
    finally:
        context.validating = False


def require_lookup_result(owner):
    context = _validate(owner)
    raise ColormapStateRejected(
        "Registry state is not an original lookup return or parameter advance",
        stage="lookup_return_prerequisite",
        partial=context,
    )


def _bindings():
    functions = (
        _digest,
        _one_of,
        _file,
        source_plan,
        _classes,
        _global_bindings,
        _global_values,
        _member,
        _function,
        _Capture.__init__,
        _Capture.globals,
        _Capture.walk,
        _Capture.capture,
        _observe,
        record_document,
        _same,
        _bound,
        capture_registry,
        _validate,
        require_lookup_result,
        _bindings,
        ColormapRegistryState.__init__,
        ColormapRegistryState.__reduce_ex__,
        ColormapRegistryState.record.fget,
    )
    return (), (
        LAW_ID,
        PREVIOUS_SHA256,
        MAX_OBJECTS,
        MAX_DEPTH,
        MAX_CALLBACKS,
        NUMPY_SCALARS,
        BUILTIN_CLASSES,
        _ISSUED,
        _ACTIVE,
        ColormapRegistryState,
        ColormapStateRejected,
        Record,
        codec.Encoder,
        codec.require,
        codec.registry,
        codec.json_bytes,
        codec.digest,
        codec.struct.pack,
        np.array,
        np.asarray,
        np.shares_memory,
        np.ndarray,
        np.generic,
        np.ufunc,
        *previous._bindings()[1],
        *(
            atom
            for fn in (
                *functions,
                codec.Encoder.__init__,
                codec.Encoder.encode,
                codec.Encoder.capture,
                codec.Encoder.seal,
                codec.Limits.check,
            )
            for atom in prefix.parameters.inherited.tissue.aliases._atoms(fn)
        ),
    )
