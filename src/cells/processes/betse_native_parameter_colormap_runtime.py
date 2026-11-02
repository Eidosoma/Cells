"""Pinned retained reference library, inspected without importing factories."""

import ast
import base64
import csv
import io
import sys
from gc import get_referents
from pathlib import Path
from types import ModuleType, SimpleNamespace

from cells.processes import betse_native_parameter_colormap_state as state

SITE = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")
PINS = {
    "matplotlib/__init__.py": "37abb78e74e9e0085a4e306a919606ffa8ff3c263def80ae2f4d938cfa79cd32",
    "matplotlib/cm.py": "a5d73bc2645cbb3b341490f68f9042683ce710cd6a89efd4c0bf5052d274ebaa",
    "matplotlib/colors.py": "ef4173f9e8310bc75714e32c3855719c27916c6c651b5c94e39f00163842cf04",
    "matplotlib/_cm.py": "44dc9e0f2801d1a04a4abc9f88bbea672ebcf2e1fd9efc4fac49e8fea9ed4f96",
    "matplotlib/_api/__init__.py": (
        "7e262cedd8ce1a1660c2e2caa63adeb078c29e36bd541b8e6f773cfed4c3c782"
    ),
    "matplotlib-3.11.2.dist-info/METADATA": (
        "e5f532226d1025af2dd15ff951df27391f66d46403b8244ea61e6b8eb3e4d806"
    ),
    "matplotlib-3.11.2.dist-info/RECORD": (
        "44ab3f0baf8618d97cbe96cbe55debdcca3fb12f0b7159361dc540d2fb733876"
    ),
    "numpy-2.5.3.dist-info/METADATA": (
        "451a9b8028000588e66b0b415587b6aef0bbc51a96d8e8a0cba0dc23acf64f99"
    ),
    "numpy-2.5.3.dist-info/RECORD": (
        "7303d8896015c2544271821eaa20431044b67a4402fa76475dfb5d5553aae629"
    ),
}
prefix = state.prefix
REACHED_API_HELPERS = ("getitem_checked", "list_suggestion_error_msg")


def declaration():
    return dict(
        site=str(SITE),
        matplotlib="3.11.2",
        numpy="2.5.3",
        python="3.13",
        files=dict(PINS),
        install_or_shared_runtime_change=False,
        actual_import_or_factory=False,
        execution_python="/mnt/workspaces/Cells/venv-betse/bin/python",
        preparation="Source inspection only; genuine issued parent and explicit release required.",
    )


def inspect_reference():
    """Read only; no importlib, native import, factory, or evaluator calls."""
    result = {}
    for name, pin in PINS.items():
        path = SITE / name
        if not path.is_file() or state._file(str(path))[1] != pin:
            raise ValueError("Pinned retained colormap dependency unavailable: " + name)
        result[name] = pin
    records = {}
    for package, version in (("matplotlib", "3.11.2"), ("numpy", "2.5.3")):
        rows = csv.reader(io.StringIO((SITE / f"{package}-{version}.dist-info/RECORD").read_text()))
        records[package] = {row[0]: (row[1], row[2]) for row in rows}
    for name in ("numpy/__init__.py", "numpy/lib/_function_base_impl.py"):
        item, size = records["numpy"][name]
        if not item.startswith("sha256="):
            raise ValueError("Original NumPy copy source RECORD hash absent")
        path = SITE / name
        pin = state._file(str(path))[1]
        encoded = base64.urlsafe_b64encode(bytes.fromhex(pin)).rstrip(b"=").decode()
        if encoded != item.split("=", 1)[1] or path.stat().st_size != int(size):
            raise ValueError("Original NumPy copy source changed")
        result[name] = pin
    return dict(declaration(), verified_files=result)


def _loaded(name, relative):
    module = sys.modules.get(name)
    if type(module) is not ModuleType:
        raise ValueError("Genuine retained library module must already be loaded: " + name)
    filename = vars(module).get("__file__")
    if type(filename) is not str or Path(filename).resolve() != SITE / relative:
        raise ValueError("Foreign retained-library module origin: " + name)
    return module


def _copy_exports(np, module):
    if type(np) is not ModuleType or type(module) is not ModuleType:
        raise ValueError("Original NumPy public/implementation modules required")
    value = vars(np).get("copy")
    if value is None or value is not vars(module).get("copy"):
        raise ValueError("Original NumPy public/module copy exports differ")
    return value


def _copy_delegates(value, core, module):
    argument = vars(module).get("_copy_dispatcher")
    if (
        type(argument) is not state.FunctionType
        or argument.__globals__ is not vars(module)
        or argument.__name__ != "_copy_dispatcher"
        or argument.__qualname__ != "_copy_dispatcher"
    ):
        raise ValueError("Original named NumPy argument dispatcher required")
    node = next(
        n
        for n in ast.parse((SITE / "numpy/lib/_function_base_impl.py").read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "_copy_dispatcher"
    )
    bindings = state.previous._canonical(
        argument, module, SITE / "numpy/lib/_function_base_impl.py", node
    )
    # CPython GC traversal reads the authenticated C object's actual owned
    # edges. A public __wrapped__ or a function stored in its attribute dict
    # alone cannot authenticate the separate argument-dispatch delegate.
    direct = tuple(item for item in get_referents(value) if type(item) is state.FunctionType)
    if (
        len(direct) != 2
        or sum(item is argument for item in direct) != 1
        or sum(item is core for item in direct) != 1
    ):
        raise ValueError("Original NumPy argument-dispatch ownership is opaque or changed")
    return argument, bindings, direct


def _numpy_copy(np, report):
    # NumPy 2.5 wraps copy in its retained C dispatcher, not a Python decorator.
    source = _loaded("numpy.lib._function_base_impl", "numpy/lib/_function_base_impl.py")
    value = _copy_exports(np, source)
    module = sys.modules.get("numpy._core._multiarray_umath")
    if type(module) is not ModuleType:
        raise ValueError("Actual NumPy copy dispatcher module absent")
    filename = Path(vars(module)["__file__"]).resolve(strict=True)
    relative = str(filename.relative_to(SITE))
    rows = dict(
        (r[0], (r[1], r[2]))
        for r in csv.reader(io.StringIO((SITE / "numpy-2.5.3.dist-info/RECORD").read_text()))
    )
    encoded, size = rows[relative]
    pin = state._file(str(filename))[1]
    actual = base64.urlsafe_b64encode(bytes.fromhex(pin)).rstrip(b"=").decode()
    if encoded != "sha256=" + actual or filename.stat().st_size != int(size):
        raise ValueError("Original NumPy dispatcher binary changed")
    report["verified_files"][relative] = pin
    dispatcher = vars(module).get("_ArrayFunctionDispatcher")
    if type(dispatcher) is not type or type(value) is not dispatcher:
        raise ValueError("Original NumPy copy dispatcher identity changed")
    flags = type.__getattribute__(dispatcher, "__flags__")
    if (
        flags & (1 << 9)  # A supplied Python/heap type is not the pinned C type.
        or not flags & (1 << 8)  # CPython Py_TPFLAGS_IMMUTABLETYPE.
        or type.__getattribute__(dispatcher, "__module__") != "numpy"
        or type.__getattribute__(dispatcher, "__name__") != "_ArrayFunctionDispatcher"
    ):
        raise ValueError("Original immutable NumPy dispatcher class required before access")
    core = object.__getattribute__(value, "__wrapped__")
    argument, bindings, direct = _copy_delegates(value, core, source)
    return value, core, argument, bindings, direct, (np, source, module, dispatcher)


def _method(cls, name, module, tree, filename):
    owner = next(base for base in cls.__mro__ if name in vars(base))
    function = vars(owner)[name]
    if type(function) in (classmethod, staticmethod):
        function = function.__func__
    core = prefix.parameters.inherited._chain(function)[-1]
    node = prefix.parameters.inherited._class(tree, owner.__name__)
    code = prefix.parameters._method_code(node, name, filename)
    if core.__globals__ is not vars(module) or prefix.parameters.inherited._code(
        core.__code__
    ) != prefix.parameters.inherited._code(code):
        raise ValueError("Original colormap copy method changed")
    return (
        function,
        core,
        tuple(prefix._function_bindings(fn) for fn in prefix.parameters.inherited._chain(function)),
    )


def _functions(module):
    """Bind actual source bodies, including reached error-path API helpers."""
    filename = vars(module)["__file__"]
    tree = ast.parse(Path(filename).read_bytes())
    # These names are reached by getitem_checked, including its missing-name
    # path. A foreign-globals replacement must not disappear from inventory.
    for name in REACHED_API_HELPERS:
        value = vars(module).get(name)
        node = next(
            (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), None
        )
        if (
            node is None
            or type(value) is not state.FunctionType
            or value.__globals__ is not vars(module)
            or value.__name__ != name
            or value.__qualname__ != name
        ):
            raise ValueError("Original named retained API helper required: " + name)
        state.previous._canonical(value, module, Path(filename), node)
    code = compile(tree, filename, "exec", dont_inherit=True)
    expected = []

    def visit(value):
        if type(value) is type(code):
            if value.co_flags & 2:  # Function body, not a module/class namespace.
                expected.append(prefix.parameters.inherited._code(value))
            for item in value.co_consts:
                visit(item)

    visit(code)
    rows = []
    for name, value in vars(module).items():
        if type(value) is not state.FunctionType or value.__globals__ is not vars(module):
            continue
        core = prefix.parameters.inherited._chain(value)[-1]
        if prefix.parameters.inherited._code(core.__code__) not in expected:
            raise ValueError("Original retained API helper body changed")
        rows.append((name, state._global_bindings(value)))
    return tuple(rows)


def bind(bound, kinds):
    report = inspect_reference()  # Execution-time lazy dependency check.
    mpl = _loaded("matplotlib", "matplotlib/__init__.py")
    cm = _loaded("matplotlib.cm", "matplotlib/cm.py")
    colors = _loaded("matplotlib.colors", "matplotlib/colors.py")
    api = _loaded("matplotlib._api", "matplotlib/_api/__init__.py")
    np = _loaded("numpy", "numpy/__init__.py")
    if (
        bound.api.mpl is not mpl
        or bound.api.cm is not cm
        or vars(cm).get("_api") is not api
        or vars(colors).get("np") is not np
        or vars(bound.api.module).get("np") is not np
        or state.np is not np
    ):
        raise ValueError("Actual retained library/parameter runtime association changed")
    path = SITE / "matplotlib/colors.py"
    tree = ast.parse(path.read_bytes())
    methods = []
    for cls in kinds:
        if type.__getattribute__(cls, "__new__") is not object.__new__:
            raise ValueError("Foreign colormap allocation factory")
        for name in ("copy", "__copy__"):
            methods.append((name, cls, *_method(cls, name, colors, tree, str(path))))
    checked = vars(api)["getitem_checked"]
    node = next(
        n
        for n in ast.parse((SITE / "matplotlib/_api/__init__.py").read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "getitem_checked"
    )
    checked_bindings = state.previous._canonical(
        checked, api, SITE / "matplotlib/_api/__init__.py", node
    )
    np_copy, np_core, np_dispatcher, np_dispatcher_bindings, np_edges, np_exports = _numpy_copy(
        np, report
    )
    np_module = _loaded("numpy.lib._function_base_impl", "numpy/lib/_function_base_impl.py")
    np_node = next(
        n
        for n in ast.parse((SITE / "numpy/lib/_function_base_impl.py").read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "copy"
    )
    np_bindings = state.previous._canonical(
        np_core, np_module, SITE / "numpy/lib/_function_base_impl.py", np_node
    )
    return SimpleNamespace(
        report=report,
        methods=tuple(methods),
        checked=checked,
        checked_core=prefix.parameters.inherited._chain(checked)[-1],
        checked_bindings=checked_bindings,
        api_helpers=_functions(api),
        np_copy=np_copy,
        np_core=np_core,
        np_bindings=np_bindings,
        np_dispatcher=np_dispatcher,
        np_dispatcher_bindings=np_dispatcher_bindings,
        np_edges=np_edges,
        np_exports=np_exports,
    )


def bindings(value):
    objects = [
        value.checked,
        value.checked_core,
        value.np_copy,
        value.np_core,
        value.np_dispatcher,
        *value.np_edges,
        *value.np_exports,
    ]
    labels = []
    for name, cls, function, core, rows in value.methods:
        labels.append((name, cls.__name__))
        objects.extend((cls, function, core))
        for row in rows:
            objects.extend(row[1])
    for row in value.checked_bindings:
        objects.extend(row[1])
    for row in value.np_bindings:
        objects.extend(row[1])
    for row in value.np_dispatcher_bindings:
        objects.extend(row[1])
    for name, row in value.api_helpers:
        labels.append(("api_helper", name))
        objects.extend(row[1])
    return (tuple(labels), tuple(sorted(value.report["verified_files"].items()))), tuple(objects)
