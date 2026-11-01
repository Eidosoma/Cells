"""Selected native grid_size descriptor on a fresh normalized parameter class.

This is read authority for one native YAML alias expression, not YAML loading,
full Parameters or package admission. Factory/import/getter execution is source
work and remains held. No descriptor value is eagerly stored or supplied.
"""

import ast
import hashlib
import importlib
import sys
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType, MethodType, SimpleNamespace
from weakref import WeakKeyDictionary

SELECTOR = "native_grid_size_yaml_alias@1"
EXPRESSION = "['general options']['comp grid size']"
_ALIASES, _READERS = WeakKeyDictionary(), WeakKeyDictionary()
_MODULE_AUTH = {}
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
NATIVE_PINS = {
    # Native source paths plus full SHA literals are intentionally kept together.
    # ruff: noqa: E501
    "betse/science/parameters.py": "f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e",
    "betse/lib/yaml/yamlalias.py": "cc87d9403c088a936a00187e33417b05ae2d26f64ee02b37d7857504cf3f0e37",
    "betse/util/type/descriptor/expralias.py": "96f5095f544894dd880a63cbdcb6333dbd178e0d64ed173b6afec384878a1986",
    "betse/util/type/cls/classes.py": "518cf58a45b621fae925595c3e3ed48dcba8c1f71df6718b10ffbe253710aab4",
    "betse/util/type/types.py": "9b8c83555b06a18bfb252d236c95c0d625699237e5c5cc671c085d282fc2c089",
    "betse/exceptions.py": "c78612e009270a8d054ea6c52e9e7014ce22e0131a929530e7c3ddc318765971",
}


def specification():
    return dict(
        selector=SELECTOR,
        expression=EXPRESSION,
        cls="int",
        castable=False,
        native_line=390,
        eager_store=False,
        full_Parameters_YAML=False,
        native_source_sha256=NATIVE_PINS,
    )


def source_pins():
    pins = {}
    for name, expected in NATIVE_PINS.items():
        digest = hashlib.sha256((NATIVE / name).read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError("Original selected native descriptor source unavailable or changed")
        pins[str(NATIVE / name)] = digest
    return pins


def _atoms(fn):
    seen, result = set(), []

    def visit(value):
        if id(value) in seen:
            return
        seen.add(id(value))
        result.append(value)
        # FunctionType itself exposes member descriptors named __code__ and
        # __closure__. Only actual Python functions/methods own these values;
        # callable classes and other objects retain their identity here.
        if type(value) in (FunctionType, MethodType):
            result.append(value.__code__)
            for cell in value.__closure__ or ():
                result.append(cell)
                visit(cell.cell_contents)
            for item in value.__defaults__ or ():
                visit(item)

    visit(fn)
    return tuple(result)


def _descriptor_from_source():
    """Execute the actual selected factory and class assignment, lazily."""
    pins = source_pins()
    _check_modules()
    old_path = list(sys.path)
    sys.path.insert(0, str(NATIVE))
    try:
        yaml = importlib.import_module("betse.lib.yaml.yamlalias")
        expr = importlib.import_module("betse.util.type.descriptor.expralias")
        classes = importlib.import_module("betse.util.type.cls.classes")
        imported = _module_records()
        tree = ast.parse((NATIVE / "betse/science/parameters.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Parameters")
        store = next(
            n
            for n in cls.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "grid_size" for t in n.targets)
        )
        expected = ast.parse("grid_size = yaml_alias(" + repr(EXPRESSION) + ", int)").body[0]
        if ast.dump(store) != ast.dump(expected):
            raise ValueError("Original grid_size descriptor declaration changed")
        namespace = {"yaml_alias": yaml.yaml_alias}
        occurrence_before = expr._EXPR_ALIAS_ID
        exec(
            compile(
                ast.Module(body=[store], type_ignores=[]),
                str(NATIVE / "betse/science/parameters.py"),
                "exec",
            ),
            namespace,
        )
        native = namespace["grid_size"]
        modules = _module_records()
        if any(modules.get(name) != record for name, record in imported.items()):
            raise ValueError("Native descriptor import producer changed during factory execution")
        if source_pins() != pins:
            raise ValueError("Native descriptor producers changed during factory work")
        info = SimpleNamespace(
            native=native,
            factories=(
                yaml.yaml_alias,
                expr.expr_alias,
                expr._get_expr_alias_class_name,
                classes.define_class,
            ),
            modules=modules,
            pins=pins,
            occurrence=(occurrence_before, expr._EXPR_ALIAS_ID, type(native).__name__),
        )
        for name, record in modules.items():
            _MODULE_AUTH[name] = (record, _module_bindings(record[0]))
        return info
    finally:
        sys.path[:] = old_path


def _module_records():
    records = {}
    for name, module in tuple(sys.modules.items()):
        if name == "betse" or name.startswith("betse."):
            file = getattr(module, "__file__", None)
            if not file:
                raise ValueError("Native descriptor source module origin unavailable")
            path = Path(file).resolve()
            if not path.is_relative_to(NATIVE):
                raise ValueError("Native descriptor imported an unavailable source origin")
            records[name] = (module, path, hashlib.sha256(path.read_bytes()).hexdigest())
    return records


def _module_bindings(module):
    return tuple(
        (name, _atoms(fn))
        for name, fn in vars(module).items()
        if callable(fn) or name == "_YAML_ALIAS_BASE_CLASSES"
    )


def _check_modules():
    for name, record in _module_records().items():
        issued = _MODULE_AUTH.get(name)
        if issued is None or issued[0] != record:
            raise ValueError("Native descriptor module lacks fresh process-local source issuance")
        current, retained = _module_bindings(record[0]), issued[1]
        if len(current) != len(retained) or any(
            a != b or len(x) != len(y) or any(i is not j for i, j in zip(x, y, strict=True))
            for (a, x), (b, y) in zip(current, retained, strict=True)
        ):
            raise ValueError("Native descriptor module callable/code authority changed")


@contextmanager
def issuing_native_imports(pins):
    """Authenticate additional pinned native factories without patching modules.

    This is import issuance, not factory/body success or Parameters admission.
    A failed import leaves its actual partial namespace unissued and refuses
    subsequent native owner use; it is never silently removed or authorized.
    """
    _check_modules()
    before = _module_records()
    for relative, expected in pins.items():
        path = (NATIVE / relative).resolve()
        if (
            not path.is_relative_to(NATIVE)
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Selected native import producer unavailable or changed")
    old_path = list(sys.path)
    sys.path.insert(0, str(NATIVE))
    try:
        yield
        after = _module_records()
        for name, record in after.items():
            relative = str(record[1].relative_to(NATIVE))
            if pins.get(relative) != record[2]:
                if before.get(name) != record:
                    raise ValueError("Native import escaped its exact pinned source closure")
            if name in before and before[name] != record:
                raise ValueError("Existing native import identity or bytes changed")
            if name in before:
                current, retained = _module_bindings(record[0]), _MODULE_AUTH[name][1]
                if len(current) != len(retained) or any(
                    a != b or len(x) != len(y) or any(i is not j for i, j in zip(x, y, strict=True))
                    for (a, x), (b, y) in zip(current, retained, strict=True)
                ):
                    raise ValueError("Existing native callable/code changed during import")
        for relative, expected in pins.items():
            if hashlib.sha256((NATIVE / relative).read_bytes()).hexdigest() != expected:
                raise ValueError("Native source changed during import issuance")
        issued = {name: (record, _module_bindings(record[0])) for name, record in after.items()}
        _MODULE_AUTH.update(issued)
    finally:
        sys.path[:] = old_path


def _bindings(info):
    native = info.native
    cls = type(native)
    functions = (
        *info.factories,
        cls.__init__,
        cls.__get__,
        cls.__set__,
        _GridAlias.__get__,
        _GridAlias.__set__,
        _descriptor_from_source,
        issuing_native_imports,
        _check_modules,
        _module_bindings,
        _module_records,
        _dispatch_bindings,
        source_pins,
        prepare_runtime,
        reading,
    )
    values = (
        native,
        cls,
        cls.__mro__,
        info.runtime,
        info.runtime.__mro__,
        type(info.wrapper),
        info.occurrence,
        native.expr_alias_cls,
        cls.__get__.__globals__.get("BetseExprAliasException"),
        cls.__get__.__globals__.get("BetseTypeException"),
    )
    return (
        *values,
        *_dispatch_bindings(info.runtime),
        *(_atom for fn in functions for _atom in _atoms(fn)),
    )


def _dispatch_bindings(runtime):
    """Read class dictionaries without invoking the instance lookup surface."""
    mro = type.__getattribute__(runtime, "__mro__")
    result = []
    for base in mro:
        result.append(base)
        for name, value in type.__getattribute__(base, "__dict__").items():
            result.extend((name, value))
    for name in ("__getattribute__", "__getattr__"):
        result.append(name)
        for base in mro:
            namespace = type.__getattribute__(base, "__dict__")
            if name in namespace:
                result.append(base)
                result.extend(_atoms(namespace[name]))
                break
        else:
            result.append(None)
    return tuple(result)


def validate(info):
    current = _bindings(info)
    if len(current) != len(info.bindings) or any(
        a is not b for a, b in zip(current, info.bindings, strict=True)
    ):
        raise ValueError("Selected native grid descriptor callable/type authority changed")
    if info.native.expr_alias_cls is not int or vars(info.native) != info.native_state:
        raise ValueError("Selected native grid descriptor state changed")
    if info.occurrence[2] != type(info.native).__name__:
        raise ValueError("Original selected descriptor occurrence changed")
    if source_pins() != info.pins:
        raise ValueError("Selected native descriptor source changed")
    for name, (module, path, sha) in info.modules.items():
        if (
            sys.modules.get(name) is not module
            or hashlib.sha256(path.read_bytes()).hexdigest() != sha
        ):
            raise ValueError("Native descriptor imported producer changed")
    if info.modules:
        _check_modules()
    if vars(info.runtime)["grid_size"] is not info.wrapper:
        raise ValueError("Fresh parameter grid descriptor was replaced")


class _GridAlias:
    def __get__(self, instance, owner):
        if instance is None:
            return self
        reader = _READERS.get(instance)
        info = _ALIASES.get(self)
        if reader is None or info is None or reader.parameter_info is not info or not reader.active:
            raise ValueError("Native grid_size read lacks active owned makeECM authority")
        reader.check()
        validate(info)
        if reader.descriptor_read_started:
            raise ValueError("Selected native grid_size read was already attempted")
        reader.descriptor_read_started = True
        reader.descriptor_read_instance = instance
        reader.descriptor_read_native = info.native
        reader.descriptor_read_epoch = reader.retirement
        reader.observe("grid_size_read_enter", instance)
        try:
            value = type(info.native).__get__(info.native, instance, owner)
            reader.descriptor_read_completed = True
            reader.descriptor_read_return_instance = instance
            reader.observe("grid_size_read_success", (instance, value))
            return value
        finally:
            reader.observe("grid_size_read_return_or_unwind", instance)

    def __set__(self, instance, value):
        raise ValueError("Native grid_size writes are outside selected read authority")


def prepare_runtime(base):
    info = _descriptor_from_source()
    info.wrapper = _GridAlias()
    info.runtime = type("_OwnedGridParameters", (base,), {"grid_size": info.wrapper})
    info.bindings = _bindings(info)
    info.native_state = dict(vars(info.native))
    _ALIASES[info.wrapper] = info
    validate(info)
    return info


@contextmanager
def reading(p, reader):
    if p in _READERS:
        raise ValueError("Selected native descriptor read is reentrant")
    _READERS[p] = reader
    try:
        yield
    finally:
        _READERS.pop(p, None)
