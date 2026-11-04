"""Fresh selected tissue configuration and literal handler-constructor ownership.

This precedes a future fresh caller/phase. It is never attached to an existing
world or treated as full Parameters/YAML-file/path/decorator/phase authority.
init_profiles/redo_gj require genuine phase and initialized Simulator owners.
All actual factory/descriptor/constructor execution needs coordinated release.
"""

import ast
import builtins
import hashlib
import importlib
import json
import sys
import warnings
from collections.abc import Reversible
from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import Enum
from functools import lru_cache
from pathlib import Path
from threading import RLock, get_ident
from types import CellType, FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_single_cell_caller_lattice as callers
from cells.processes import betse_native_single_cell_core_preparation as core
from cells.processes import betse_native_single_cell_grid_alias as aliases
from cells.processes import betse_native_single_cell_initial_geometry as captures
from cells.processes import betse_native_tissue_configuration_source as source

LAW_ID = "betse_fresh_selected_tissue_configuration_constructor@1"
METHODS = ("__init__", "_init_tissues", "_init_cuts", "_init_events", "_init_events_global")
PARAMETER_METHODS = ("construct", "load")
_NATIVE = {name: getattr(source.TissueConstructor, name) for name in METHODS}
_STORES = {name: getattr(source.ParameterSubconfigurations, name) for name in PARAMETER_METHODS}
_REQUESTS, _CONSUMED, _ISSUED, _OBJECTS = (WeakKeyDictionary() for _ in range(4))
_LOCK = RLock()
_ACTIVE = []
INVALIDATED_OWNERS = core.INVALIDATED_OWNERS
_REVERSIBLE_HOOK = vars(Reversible)["__subclasshook__"]
_REVERSIBLE_HOOK_FUNCTION = _REVERSIBLE_HOOK.__func__
_REVERSIBLE_HOOK_CODE = _REVERSIBLE_HOOK_FUNCTION.__code__


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    configuration_json: str
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    cache: object
    stages: tuple
    events: tuple
    work: tuple
    warnings: tuple
    source_completed: bool
    failure_stage: str | None
    identity: str


class ConfigurationRejected(ValueError):
    def __init__(
        self,
        reason,
        *,
        stage,
        request=None,
        trial=None,
        partial=None,
        source_error=None,
        capture_error=None,
    ):
        super().__init__(reason)
        self.stage, self.request, self.trial, self.partial = stage, request, trial, partial
        self.source_error, self.capture_error = source_error, capture_error


def request_record(request):
    return dict(
        law=LAW_ID,
        configuration_json=request.configuration_json,
        parameter_constructor_lines=source.PARAMETER_CONSTRUCTOR_LINES,
        parameter_load_lines=source.PARAMETER_LOAD_LINES,
        handler_methods=METHODS,
        handler_lines=source.HANDLER_LINES,
        boundary=(
            "fresh selected subconfigurations -> handler constructor, before phase/profile mapping"
        ),
        no_existing_world_or_parameter_retrofit=True,
        full_Parameters_YAML_paths_decorators_phase_simulator_admitted=False,
        invalidated_owners=INVALIDATED_OWNERS,
    )


def from_configuration(configuration, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID or type(configuration) is not dict:
        raise ConfigurationRejected(
            "Explicit selected configuration source law required", stage="request"
        )
    text = json.dumps(configuration, allow_nan=False, sort_keys=True, separators=(",", ":"))
    if len(text.encode()) > 65536:
        raise ConfigurationRejected("Bounded selected configuration exceeded", stage="request")
    value = Request(text, "")
    value = replace(value, identity=core.records._digest(request_record(value)))
    _REQUESTS[value] = value.identity
    return value


def _body(node):
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return ast.dump(ast.Module(body=body, type_ignores=[]))


def _verify_sources():
    pins = {}
    for relative, expected in source.SOURCE_PINS.items():
        path = aliases.NATIVE / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("Pinned native tissue prerequisite changed: " + relative)
        pins[str(path)] = actual
    for module in (source, aliases, sys.modules[__name__]):
        pins[str(Path(module.__file__).resolve())] = hashlib.sha256(
            Path(module.__file__).read_bytes()
        ).hexdigest()
    proof_paths = (
        str(aliases.NATIVE / "betse/science/parameters.py"),
        str(aliases.NATIVE / "betse/science/tissue/tishandler.py"),
        str(Path(source.__file__).resolve()),
    )
    _verify_bodies(tuple((path, pins[path]) for path in proof_paths))
    return pins


@lru_cache(maxsize=8)
def _verify_bodies(producer_key):
    # Every use still hashes every producer. Identical pinned bytes reuse only
    # their parsed AST correspondence proof, never live state/owner authority.
    for path, expected in producer_key:
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("Native source changed during AST proof")
    tree = ast.parse((aliases.NATIVE / "betse/science/tissue/tishandler.py").read_text())
    native = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TissueHandler")
    own = next(
        n
        for n in ast.parse(Path(source.__file__).read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "TissueConstructor"
    )
    for name in METHODS:
        a = next(n for n in native.body if isinstance(n, ast.FunctionDef) and n.name == name)
        b = next(n for n in own.body if isinstance(n, ast.FunctionDef) and n.name == name)
        if _body(a) != _body(b) or source.HANDLER_LINES[name] != (a.lineno, a.end_lineno):
            raise ValueError("Literal handler constructor body changed: " + name)
    p = next(
        n
        for n in ast.parse((aliases.NATIVE / "betse/science/parameters.py").read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "Parameters"
    )
    own_p = next(
        n
        for n in ast.parse(Path(source.__file__).read_text()).body
        if isinstance(n, ast.ClassDef) and n.name == "ParameterSubconfigurations"
    )
    for name, native_name, lines in (
        ("construct", "__init__", source.PARAMETER_CONSTRUCTOR_LINES),
        ("load", "load", source.PARAMETER_LOAD_LINES),
    ):
        a = next(n for n in p.body if isinstance(n, ast.FunctionDef) and n.name == native_name)
        b = next(n for n in own_p.body if isinstance(n, ast.FunctionDef) and n.name == name)
        if ast.dump(
            ast.Module(body=[n for n in a.body if n.lineno in lines], type_ignores=[])
        ) != _body(b):
            raise ValueError("Selected original parameter stores/load order changed")


_FACTORY_MODULES = {
    "SimConfCutListItem": "betse.science.config.model.conftis",
    "SimConfTissueDefault": "betse.science.config.model.conftis",
    "SimConfTissueListItem": "betse.science.config.model.conftis",
    "YamlList": "betse.lib.yaml.abc.yamllistabc",
    "TissueProfile": "betse.science.tissue.tisprofile",
    "CutProfile": "betse.science.tissue.tisprofile",
    "TissuePickerAll": "betse.science.tissue.picker.tispickcls",
    "TissuePickerColor": "betse.science.tissue.picker.tispickcls",
    "TissuePickerIndices": "betse.science.tissue.picker.tispickcls",
    "TissuePickerPercent": "betse.science.tissue.picker.tispickcls",
    "TissuePickerImage": "betse.science.tissue.picker.tispickimage",
    "SimEventCut": "betse.science.tissue.event.tisevecut",
    "SimEventPulseVoltage": "betse.science.tissue.event.tisevevolt",
}


def _native_setup(context):
    # No native package import occurs at module import or request preparation.
    with aliases.issuing_native_imports(source.SOURCE_PINS):
        yaml = importlib.import_module("betse.lib.yaml.yamlalias")
        expr = importlib.import_module("betse.util.type.descriptor.expralias")
        enum = importlib.import_module("betse.science.enum.enumconf")
        errors = importlib.import_module("betse.exceptions")
        namespace = dict(yaml_alias=yaml.yaml_alias)
        cls = next(
            n
            for n in ast.parse((aliases.NATIVE / "betse/science/parameters.py").read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == "Parameters"
        )
        node = next(
            n
            for n in cls.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "is_tissue_profiles" for t in n.targets)
        )
        before = expr._EXPR_ALIAS_ID
        exec(
            compile(
                ast.Module(body=[node], type_ignores=[]),
                str(aliases.NATIVE / "betse/science/parameters.py"),
                "exec",
            ),
            namespace,
        )
        context.descriptor_occurrence = (
            before,
            expr._EXPR_ALIAS_ID,
            type(namespace["is_tissue_profiles"]).__name__,
        )
        context.factories = {
            name: getattr(importlib.import_module(module), name)
            for name, module in _FACTORY_MODULES.items()
            if name not in ("TissuePickerImage", "SimEventCut", "SimEventPulseVoltage")
        }
        context.symbols = dict(
            CellsPickerType=enum.CellsPickerType,
            BetseSimTissueException=errors.BetseSimTissueException,
        )
        context.descriptor = namespace["is_tissue_profiles"]
        context.modules = aliases._module_records()


def _lazy_factory(context, name):
    if name not in context.factories:
        with aliases.issuing_native_imports(source.SOURCE_PINS):
            context.factories[name] = getattr(importlib.import_module(_FACTORY_MODULES[name]), name)
            context.modules = aliases._module_records()
        context.native_bindings = _native_bindings(context)
    return context.factories[name]


def _surface(cls):
    result = []
    for base in cls.__mro__:
        result += [base, base.__mro__]
        for name, value in vars(base).items():
            result += [name, *aliases._atoms(value)]
            if isinstance(value, (classmethod, staticmethod)):
                result += list(aliases._atoms(value.__func__))
            elif isinstance(value, property):
                for function in (value.fget, value.fset, value.fdel):
                    result += list(aliases._atoms(function))
            elif not isinstance(value, type) and hasattr(type(value), "__get__"):
                for method in ("__get__", "__set__", "__delete__"):
                    result += list(aliases._atoms(getattr(type(value), method, None)))
            if isinstance(value, _Descriptor):
                result += [value.native, value.name]
            if name == "make_list":
                function = value.__func__ if isinstance(value, classmethod) else value
                if type(function) is FunctionType:
                    result += list(_factory_atoms(function))
    return tuple(result)


def _factory_atoms(function):
    """Bind the decorator's actual defaults/delegate, not only its outer code."""
    seen, atoms = set(), []

    def visit(value):
        atoms.append(value)
        if type(value) is not FunctionType or id(value) in seen:
            return
        seen.add(id(value))
        if len(seen) > 128:
            raise ValueError("Bounded factory callable graph exceeded")
        atoms.extend((value.__code__, value.__globals__, value.__defaults__, value.__kwdefaults__))
        visit(value.__globals__.get("YamlList"))
        for item in value.__defaults__ or ():
            visit(item)
        for key, item in (value.__kwdefaults__ or {}).items():
            atoms.append(key)
            visit(item)
        atoms.append(value.__closure__)
        for cell in value.__closure__ or ():
            atoms.append(cell)
            visit(cell.cell_contents)
        visit(vars(value).get("__wrapped__"))

    visit(function)
    return tuple(atoms)


def _copy_factory(original, constructor):
    """Keep decorator checks while redirecting only the owned list constructor.

    Beartype stores its delegate in keyword defaults. Copying only the outer
    CodeType either loses those arguments or calls the unredirected original
    body. Clone the bounded wrapped chain and its exact delegate references;
    all source functions, cells, defaults and module namespaces stay untouched.
    """
    chain, function = [], original
    while function is not None:
        if type(function) is not FunctionType or function in chain or len(chain) >= 16:
            raise ValueError("Exact acyclic Python factory wrapper chain required")
        chain.append(function)
        function = vars(function).get("__wrapped__")
    copies, cells = {}, {}
    for function in reversed(chain):
        closure = None
        if function.__closure__ is not None:
            closure = []
            for cell in function.__closure__:
                if any(cell.cell_contents is item for item in chain):
                    pair = cells.setdefault(id(cell), (cell, CellType()))
                    closure.append(pair[1])
                else:
                    closure.append(cell)
            closure = tuple(closure)
        copies[function] = FunctionType(
            function.__code__,
            dict(function.__globals__, YamlList=constructor),
            function.__name__,
            function.__defaults__,
            closure,
        )

    def copied(value):
        return copies[value] if type(value) is FunctionType and value in copies else value

    for old_cell, new_cell in cells.values():
        new_cell.cell_contents = copied(old_cell.cell_contents)
    for function, clone in copies.items():
        if function.__defaults__ is not None:
            clone.__defaults__ = tuple(copied(value) for value in function.__defaults__)
        if function.__kwdefaults__ is not None:
            clone.__kwdefaults__ = {
                key: copied(value) for key, value in function.__kwdefaults__.items()
            }
        clone.__dict__.update(vars(function))
        if "__wrapped__" in vars(function):
            clone.__wrapped__ = copied(function.__wrapped__)
        clone.__annotations__ = dict(function.__annotations__)
        clone.__qualname__, clone.__module__, clone.__doc__ = (
            function.__qualname__,
            function.__module__,
            function.__doc__,
        )
    return copies[original]


def _native_bindings(context):
    return (
        context.descriptor,
        *_surface(type(context.descriptor)),
        *(atom for cls in context.factories.values() for atom in _surface(cls)),
        *(item for name, symbol in context.symbols.items() for item in (name, symbol)),
        *(
            atom
            for fn in (aliases.issuing_native_imports, _native_setup, _lazy_factory)
            for atom in aliases._atoms(fn)
        ),
    )


def _bindings():
    return (
        _REQUESTS,
        _CONSUMED,
        _ISSUED,
        _OBJECTS,
        _ACTIVE,
        _LOCK,
        aliases._MODULE_AUTH,
        Reversible,
        _REVERSIBLE_HOOK,
        _REVERSIBLE_HOOK_FUNCTION,
        _REVERSIBLE_HOOK_CODE,
        _REVERSIBLE_HOOK_FUNCTION.__globals__.get("Reversible"),
        *(
            atom
            for function in (
                *_NATIVE.values(),
                *_STORES.values(),
                _verify_sources,
                _verify_bodies,
                _verify_bodies.__wrapped__,
                _body,
                _bindings,
                _native_bindings,
                _surface,
                _factory_atoms,
                _copy_factory,
                _invoke,
                _native_call,
                _make,
                _runtime_type,
                _namespace,
                _snapshot,
                _graph,
                _configuration_graph,
                _check,
                _event,
                _stop,
                _native_setup,
                _lazy_factory,
                aliases._check_modules,
                aliases._module_records,
                aliases._module_bindings,
                aliases._atoms,
                aliases.issuing_native_imports,
                _guard,
                _account,
                _namespace_bindings,
                _project,
                _same,
                _validate,
            )
            for atom in aliases._atoms(function)
        ),
    )


def _stop(context):
    if context.observation_error is not None:
        raise _CaptureStop()


class _CaptureStop(Exception):
    pass


def _event(context, kind, raw):
    try:
        context.events.append((kind, raw))
    except Exception as capture:
        captures._remember_observation_error(context, capture, origin=kind, raw=raw)


def _guard(context):
    _stop(context)
    if (
        not context.active
        or not _ACTIVE
        or _ACTIVE[-1] is not context
        or context.thread != get_ident()
    ):
        raise ConfigurationRejected(
            "Native tissue source entry unavailable", stage="source_call_unavailable"
        )


@contextmanager
def _account(context):
    """One ordered work ledger; wrapper/body layers are not additive cases."""
    previous, trace = sys.getprofile(), sys.gettrace()
    native_root = str(aliases.NATIVE) + "/"
    selected = {
        f.__code__ for f in (*_NATIVE.values(), *_STORES.values(), _native_setup, _lazy_factory)
    }

    def profile(frame, event, arg):
        reached = frame.f_code.co_filename.startswith(native_root) or frame.f_code in selected
        if reached and event == "call":
            if len(context.work) >= 100000:
                raise ValueError("Bounded tissue work ledger exhausted")
            context.work.append(
                dict(
                    sequence=len(context.work),
                    layer="actual_native_body"
                    if frame.f_code.co_filename.startswith(native_root)
                    else "selected_source_body",
                    phase=context.stage,
                    method=frame.f_code.co_qualname,
                    source_file=frame.f_code.co_filename,
                    status="entered_not_success_credit",
                )
            )
        if (
            reached
            and event == "return"
            and (
                frame.f_code in selected
                or frame.f_code.co_name in ("__init__", "load", "make_list", "__get__", *_NATIVE)
            )
        ):
            try:
                context.locals[(frame.f_code.co_filename, frame.f_code.co_qualname)] = dict(
                    frame.f_locals
                )
            except Exception as capture:
                captures._remember_observation_error(
                    context, capture, origin="raw_locals", raw=frame
                )
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)


def _native_call(context, label, function, *args, **kwargs):
    _guard(context)
    _check(context)
    _event(context, label + "_enter", (args, kwargs))
    _stop(context)
    context.work.append(
        dict(
            sequence=len(context.work),
            layer="native_factory_or_method_wrapper",
            method=label,
            status="entered_not_success_credit",
        )
    )
    try:
        result = function(*args, **kwargs)
    except Exception:
        _event(context, label + "_unwind", (args, kwargs))
        raise
    context.last_completed = (label, result)
    _event(context, label + "_return", result)
    _stop(context)
    return result


class _Descriptor:
    def __init__(self, native, name):
        self.native, self.name = native, name

    def __get__(self, actual, owner=None):
        if actual is None:
            return self
        context = _OBJECTS[actual]
        return _native_call(context, self.name + ".__get__", self.native.__get__, actual, owner)

    def __set__(self, actual, value):
        context = _OBJECTS[actual]
        return _native_call(context, self.name + ".__set__", self.native.__set__, actual, value)


def _runtime_type(context, name):
    _guard(context)
    if name in context.runtime_types:
        return context.runtime_types[name]
    native = _lazy_factory(context, name)
    namespace = {}

    def guarded(method, delegate):
        def invoke(actual, *args, **kwargs):
            _guard(context)
            if actual not in _OBJECTS:
                # Only actual nested native construction may introduce an item.
                if method != "__init__":
                    raise ValueError("Unissued native configuration object")
                _OBJECTS[actual] = context
                context.objects.append((name, actual))
            if _OBJECTS[actual] is not context:
                raise ValueError("Foreign native configuration object")
            return _native_call(context, name + "." + method, delegate, actual, *args, **kwargs)

        return invoke

    seen = set()
    for base in native.__mro__:
        for method, member in vars(base).items():
            if method in seen:
                continue
            seen.add(method)
            if method == "__subclasshook__" and base is Reversible:
                if (
                    member is not _REVERSIBLE_HOOK
                    or member.__func__ is not _REVERSIBLE_HOOK_FUNCTION
                    or member.__func__.__code__ is not _REVERSIBLE_HOOK_CODE
                    or member.__func__.__globals__.get("Reversible") is not Reversible
                ):
                    raise ValueError("Original stdlib Reversible subclass hook required")
                # ABCMeta visits registered subclasses during unrelated type
                # checks (including YAML return validation). Keep this exact
                # inherited metadata hook; it returns NotImplemented for our
                # derived class and grants no native method/factory entry.
                # Its class/function/code remain in the full MRO surface.
                continue
            if isinstance(member, FunctionType):
                namespace[method] = guarded(method, member)
            elif isinstance(member, classmethod):

                def class_entry(cls, *a, _method=method, _delegate=member.__func__, **k):
                    _guard(context)
                    return _native_call(context, name + "." + _method, _delegate, cls, *a, **k)

                namespace[method] = classmethod(class_entry)
            elif isinstance(member, staticmethod):

                def static_entry(*a, _method=method, _delegate=member.__func__, **k):
                    _guard(context)
                    return _native_call(context, name + "." + _method, _delegate, *a, **k)

                namespace[method] = staticmethod(static_entry)
            elif (
                isinstance(member, property)
                or not isinstance(member, (type, classmethod, staticmethod))
                and hasattr(type(member), "__get__")
                and not method.startswith("__")
            ):
                namespace[method] = _Descriptor(member, name + "." + method)
    # Native classmethod body returns YamlList; its copied namespace redirects
    # only that constructor to the owned subclass, without patching the module.
    if hasattr(native, "make_list"):
        original = native.make_list.__func__
        delegate = _copy_factory(original, lambda *x, **y: _make(context, "YamlList", *x, **y))

        def make_list(cls, *a, **k):
            _guard(context)
            return _native_call(context, name + ".make_list", delegate, cls, *a, **k)

        namespace["make_list"] = classmethod(make_list)
    namespace["__reduce_ex__"] = lambda *a: (_ for _ in ()).throw(
        TypeError("Live tissue objects cannot be serialized")
    )
    result = type("Owned" + name, (native,), namespace)
    context.runtime_types[name] = result
    context.runtime_bindings[name] = _surface(result)
    return result


def _make(context, name, /, *args, **kwargs):
    _guard(context)
    cls = _runtime_type(context, name)
    actual = object.__new__(cls)
    _OBJECTS[actual] = context
    context.objects.append((name, actual))
    context.work.append(
        dict(
            sequence=len(context.work),
            layer="native_factory_allocation",
            method=name,
            status="allocated_not_success_credit",
        )
    )
    cls.__init__(actual, *args, **kwargs)
    return actual


def _namespace(context):
    from collections import OrderedDict

    class Factory:
        def __init__(self, name):
            self.name = name

        def __call__(self, *a, **k):
            return _make(context, self.name, *a, **k)

        def make_list(self):
            _guard(context)
            return _runtime_type(context, self.name).make_list()

    def log(*args):
        return _native_call(context, "log", lambda *a: None, *args)

    namespace = dict(
        context.symbols,
        **{name: Factory(name) for name in _FACTORY_MODULES},
        OrderedDict=OrderedDict,
        logs=SimpleNamespace(log_warning=log),
        bool=builtins.bool,
        enumerate=builtins.enumerate,
    )
    methods = {}
    for name, function in {**{("p_" + n): f for n, f in _STORES.items()}, **_NATIVE}.items():
        methods[name] = FunctionType(
            function.__code__,
            dict(function.__globals__, **namespace),
            function.__name__,
            function.__defaults__,
            function.__closure__,
        )
    context.methods = methods

    def handler_method(name):
        def entry(actual, p):
            _guard(context)
            if actual is not context.handler or p is not context.p:
                raise ValueError("Foreign handler or parameters")
            return _invoke(context, name, actual, p)

        return entry

    runtime = type(
        "OwnedTissueConstructor",
        (source.TissueConstructor,),
        {name: handler_method(name) for name in METHODS},
    )
    context.handler = object.__new__(runtime)
    descriptor = _Descriptor(context.descriptor, "is_tissue_profiles")
    pclass = type("SelectedTissueParameters", (), {"is_tissue_profiles": descriptor})
    context.p = object.__new__(pclass)
    context.p._conf = context.configuration
    _OBJECTS[context.p] = context
    context.objects.extend((("parameters", context.p), ("handler", context.handler)))
    context.namespace_bindings = _namespace_bindings(context)


def _namespace_bindings(context):
    return (
        *_surface(type(context.p)),
        *_surface(type(context.handler)),
        *(atom for function in context.methods.values() for atom in aliases._atoms(function)),
        *(
            atom
            for function in context.methods.values()
            for key in ("OrderedDict", "bool", "enumerate")
            for atom in aliases._atoms(function.__globals__[key])
        ),
        *(
            item
            for function in context.methods.values()
            for key in _FACTORY_MODULES
            for item in (
                function.__globals__[key],
                function.__globals__[key].name,
                *aliases._atoms(type(function.__globals__[key]).__call__),
                *aliases._atoms(type(function.__globals__[key]).make_list),
            )
        ),
        *(
            item
            for function in context.methods.values()
            for item in (
                function.__globals__["logs"],
                *aliases._atoms(function.__globals__["logs"].log_warning),
            )
        ),
    )


def _invoke(context, name, actual, *args):
    _guard(context)
    _check(context)
    _event(context, name + "_enter", actual)
    _stop(context)
    context.work.append(
        dict(
            sequence=len(context.work),
            layer="selected_literal_body",
            method=name,
            status="entered_not_success_credit",
        )
    )
    try:
        value = context.methods[name](actual, *args)
    except Exception:
        _event(context, name + "_unwind", actual)
        raise
    context.last_completed = (name, value)
    _event(context, name + "_return", value)
    _stop(context)
    return value


def _project(context, value):
    if any(value is obj for _, obj in context.objects):
        return dict(
            owned_reference=next(i for i, (_, obj) in enumerate(context.objects) if value is obj)
        )
    if isinstance(value, type):
        return dict(native_type=value.__module__ + "." + value.__qualname__)
    if isinstance(value, Enum):
        return dict(native_enum=type(value).__name__, name=value.name, value=value.value)
    if isinstance(value, dict):
        return {k: _project(context, v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(_project(context, v) for v in value)
    return value


def _snapshot(context):
    return core.caches.snapshot(
        dict(
            configuration=context.configuration,
            objects=[
                dict(kind=name, fields=_project(context, vars(obj)))
                for name, obj in context.objects
            ],
            stages=context.completed,
            descriptor_occurrence=getattr(context, "descriptor_occurrence", None),
        )
    )


def _graph(context):
    view = context.graph_view
    if not hasattr(context, "graph_fields"):
        context.graph_fields = []
    context.graph_fields.clear()
    context.graph_fields.extend(vars(obj) for _, obj in context.objects)
    vars(view).clear()
    vars(view).update(
        objects=context.objects,
        fields=context.graph_fields,
        configuration=context.configuration,
        descriptor=context.descriptor,
    )
    return callers._graph(view, view, context.tape)


def _same(actual, retained):
    if len(actual) != len(retained) or any(
        a is not b for a, b in zip(actual, retained, strict=True)
    ):
        raise ValueError("Tissue callable/reference binding changed")


def _configuration_graph(context):
    return callers._graph(
        context.configuration_view, context.configuration_view, context.configuration_tape
    )


def _check(context):
    if (
        _CONSUMED.get(context.request) is not context
        or _REQUESTS.get(context.request) != context.request.identity
        or core.records._digest(request_record(context.request)) != context.request.identity
        or context.thread != get_ident()
    ):
        raise ValueError("Original configuration occurrence/claim changed")
    if _verify_sources() != context.producers:
        raise ValueError("Tissue source producer changed")
    if core.caches.snapshot(context.configuration).identity != context.configuration_cache.identity:
        raise ValueError("Original retained configuration bytes changed")
    objects, edges = _configuration_graph(context)
    old_objects, old_edges = context.configuration_graph
    if (
        len(objects) != len(old_objects)
        or any(a is not b for a, b in zip(objects, old_objects, strict=True))
        or edges != old_edges
    ):
        raise ValueError("Original retained configuration reference edges changed")
    if hasattr(context, "p") and vars(context.p).get("_conf") is not context.configuration:
        raise ValueError("Actual parameter configuration association changed")
    _same(_bindings(), context.bindings)
    if hasattr(context, "native_bindings"):
        _same(_native_bindings(context), context.native_bindings)
    if hasattr(context, "namespace_bindings"):
        _same(_namespace_bindings(context), context.namespace_bindings)
    for name, cls in context.runtime_types.items():
        _same(_surface(cls), context.runtime_bindings[name])
    for name, obj in context.objects:
        if name != "handler" and _OBJECTS.get(obj) is not context:
            raise ValueError("Native object issuance changed")
    if hasattr(context, "modules"):
        aliases._check_modules()
        for name, record in context.modules.items():
            if aliases._module_records().get(name) != record:
                raise ValueError("Native factory import changed")


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        cache=trial.cache.identity,
        stages=[(name, cache.identity) for name, cache in trial.stages],
        events=trial.events,
        work=trial.work,
        warnings=trial.warnings,
        source_completed=trial.source_completed,
        failure_stage=trial.failure_stage,
        phase_profile_mapping_or_simulator_admitted=False,
    )


class TissueConfigurationOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use fresh selected configuration construction")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live tissue prelude cannot be serialized")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def handler(self):
        return _validate(self).handler

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not TissueConfigurationOwner or owner not in _ISSUED:
        raise ConfigurationRejected("Issued tissue configuration owner unavailable", stage="owner")
    return _ISSUED[owner]


def _validate(owner):
    context = _authority(owner)
    try:
        if context.invalid or context.active or context.owner is not owner:
            raise ValueError("Invalid tissue configuration epoch")
        _check(context)
        if (
            _snapshot(context).identity != context.trial.cache.identity
            or core.records._digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Tissue constructor cache/trial changed")
        objects, edges = _graph(context)
        old_objects, old_edges = context.graph
        if (
            len(objects) != len(old_objects)
            or any(a is not b for a, b in zip(objects, old_objects, strict=True))
            or edges != old_edges
        ):
            raise ValueError("Tissue configuration alias/reference edges changed")
    except Exception as error:
        context.invalid = True
        raise ConfigurationRejected(
            "Stale tissue configuration owner refused",
            stage="owner_drift",
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def prepare(request):
    if (
        type(request) is not Request
        or _REQUESTS.get(request) != request.identity
        or core.records._digest(request_record(request)) != request.identity
    ):
        raise ConfigurationRejected(
            "Issued typed configuration request required", stage="request", request=request
        )
    context = SimpleNamespace(
        request=request,
        configuration=json.loads(request.configuration_json),
        thread=get_ident(),
        active=False,
        invalid=False,
        stage="retirement",
        events=[],
        work=[],
        locals={},
        completed=[],
        stages=[],
        objects=[],
        runtime_types={},
        runtime_bindings={},
        graph_view=SimpleNamespace(),
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
    )
    context.tape = SimpleNamespace(rng=None, events=context.events, draws=[], locals=context.locals)
    error = None
    with _LOCK, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if request in _CONSUMED:
            raise ConfigurationRejected(
                "Configuration attempt already consumed",
                stage="consumed",
                request=request,
                partial=dict(original_context=_CONSUMED[request]),
            )
        _CONSUMED[request] = context
        context.active = True
        _ACTIVE.append(context)
        try:
            context.producers, context.bindings = _verify_sources(), _bindings()
            context.configuration_cache = core.caches.snapshot(context.configuration)
            context.configuration_view = SimpleNamespace(configuration=context.configuration)
            context.configuration_tape = SimpleNamespace(rng=None, events=(), draws=(), locals={})
            context.configuration_graph = _configuration_graph(context)
            context.stage = "native_factory_descriptor_setup"
            with _account(context):
                context.work.append(
                    dict(
                        sequence=len(context.work),
                        layer="descriptor_factory_import_setup",
                        method="_native_setup",
                        status="entered_not_success_credit",
                    )
                )
                _native_setup(context)
                _stop(context)
                context.native_bindings = _native_bindings(context)
                context.stage = "namespace"
                _namespace(context)
                for name, actual, args in (
                    ("p_construct", context.p, ()),
                    ("p_load", context.p, ()),
                    ("__init__", context.handler, (context.p,)),
                ):
                    context.stage = name
                    _invoke(context, name, actual, *args)
                    context.completed.append(name)
                    try:
                        context.stages.append((name, _snapshot(context)))
                    except Exception as capture:
                        captures._remember_observation_error(
                            context, capture, origin="stage_snapshot", raw=actual
                        )
                        raise _CaptureStop() from capture
                context.stage = "source_checks"
                _check(context)
        except Exception as failure:
            if not isinstance(failure, _CaptureStop):
                error = failure
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
    partial = dict(
        context=context,
        request=request,
        parameters=getattr(context, "p", None),
        handler=getattr(context, "handler", None),
        raw_objects=context.objects,
        events=context.events,
        work=context.work,
        completed=context.completed,
        stages=context.stages,
        raw_locals=context.locals,
        last_completed=getattr(context, "last_completed", None),
        configuration=context.configuration,
        consumed=True,
        usable_child_available=False,
    )
    if context.observation_error is not None:
        raise ConfigurationRejected(
            "Tissue observation failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=context.observation_error,
        ) from (error or context.observation_error)
    try:
        trial = Trial(
            request.identity,
            _snapshot(context),
            tuple(context.stages),
            tuple(name for name, _ in context.events),
            tuple(context.work),
            tuple(str(w.message) for w in caught),
            error is None,
            None if error is None else context.stage,
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise ConfigurationRejected(
            "Tissue final capture failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error or capture)
    if error is not None:
        raise ConfigurationRejected(
            "Native tissue prerequisite failed",
            stage=context.stage,
            request=request,
            trial=trial,
            partial=partial,
            source_error=error,
        ) from error
    try:
        context.trial = trial
        _check(context)
        context.graph = _graph(context)
        owner = object.__new__(TissueConfigurationOwner)
        context.owner = owner
        _ISSUED[owner] = context
        return owner
    except Exception as capture:
        raise ConfigurationRejected(
            "Tissue child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture


def require_profile_mapping(owner, *, phase=None):
    context = _validate(owner)
    raise ConfigurationRejected(
        "Genuine fresh same-parameter caller/phase and Simulator.init_core ownership required",
        stage="profile_mapping_prerequisites",
        trial=context.trial,
        partial=dict(
            missing=(
                "fresh caller using this exact pre-phase parameter instance",
                "full native parameter ion/material and phase/Simulator ownership",
                "source Simulator.init_core before init_profiles Dm_cells writes",
                "init_profiles then redo_gj in seed order",
            ),
            supplied_phase_refused=phase is not None,
            invalidated_owners=INVALIDATED_OWNERS,
            physical_checkpoint_admitted=False,
        ),
    )
