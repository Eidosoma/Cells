"""Pinned original import machinery, with two explicit source-read selections.

This module imports no model or beartype at import time. A future released
worker resolves the real PathFinder loader. Its adapter changes source reads,
not beartype's get_code/source_to_code, transformer, decorators or registration.
Synthetic packages can exercise the same machinery without importing BETSE.
"""

import ast
import builtins
import hashlib
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import struct
import sys
from pathlib import Path
from types import CodeType, FunctionType, MethodDescriptorType, MethodType, ModuleType

FILE = "validation/betse/native_reference_imports.py"
KIND = "cells.original_package_native_import_lifecycle@1"
BEARTYPE_ROOT = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages/beartype")
BEARTYPE_TREE_SHA256 = "ca9a4ca05af88968c8c8d0d9c987ef431099b07f7238437154cd479c141a9101"
BEARTYPE_FILES, BEARTYPE_BYTES = 420, 4565969
BEARTYPE_NAMESPACES = ("beartype._data.claw",)
MAX_FILE_BYTES, MAX_MODULES = 8 * 2**20, 4096
SIM_ENTRY = "_retained_init_sim_reference"
COMPILER_ROLES = {
    "get_code": ("claw/_importlib/_clawimpload.py", "BeartypeSourceFileLoader.get_code"),
    "source_to_code": (
        "claw/_importlib/_clawimpload.py",
        "BeartypeSourceFileLoader.source_to_code",
    ),
    "configuration": ("claw/_package/clawpkgtrie.py", "get_package_conf_or_none"),
    "path_hook_factory": ("claw/_importlib/clawimpmain.py", "add_beartype_pathhook"),
}
SELECTED_NATIVE_FILES = {
    "betse/science/sim.py": "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43",
    "betse/science/cells.py": "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2",
}
_ISSUED = {}


class ImportRejected(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ImportRejected(message)


def seal(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def code_sha256(code):
    require(type(code) is CodeType, "Actual compiled module code required")
    # marshal encodes incidental reference/interning state. Those bytes may
    # differ for equal independently compiled code. Hash every code field and
    # typed constant instead, including IEEE bits, line/exception tables and
    # nested code, without executing a body or weakening any comparison.
    return seal(_code_record(code))


def _constant(value):
    kind = type(value)
    if kind is CodeType:
        return dict(kind="code", value=_code_record(value))
    if value is None or value is Ellipsis:
        return dict(kind="None" if value is None else "Ellipsis")
    if kind in (bool, int, str):
        return dict(kind=kind.__name__, value=value)
    if kind is bytes:
        return dict(kind="bytes", value=value.hex())
    if kind is float:
        return dict(kind="float64", bits=struct.pack("!d", value).hex())
    if kind is complex:
        return dict(kind="complex128", bits=struct.pack("!dd", value.real, value.imag).hex())
    if kind in (tuple, frozenset):
        items = [_constant(v) for v in value]
        if kind is frozenset:
            items.sort(key=lambda v: json.dumps(v, sort_keys=True))
        return dict(kind=kind.__name__, items=items)
    raise ImportRejected("Unsupported code constant type: " + kind.__qualname__)


def _code_record(code):
    return dict(
        names={
            name: getattr(code, name)
            for name in (
                "co_name",
                "co_qualname",
                "co_filename",
                "co_firstlineno",
                "co_flags",
                "co_argcount",
                "co_posonlyargcount",
                "co_kwonlyargcount",
                "co_nlocals",
                "co_stacksize",
            )
        },
        rosters={
            name: list(getattr(code, name))
            for name in (
                "co_names",
                "co_varnames",
                "co_freevars",
                "co_cellvars",
            )
        },
        bytes={
            name: getattr(code, name).hex()
            for name in (
                "co_code",
                "co_linetable",
                "co_exceptiontable",
            )
        },
        constants=[_constant(value) for value in code.co_consts],
    )


def specification():
    return dict(
        kind=KIND,
        beartype_root=str(BEARTYPE_ROOT),
        beartype_tree_sha256=BEARTYPE_TREE_SHA256,
        beartype_files=BEARTYPE_FILES,
        beartype_bytes=BEARTYPE_BYTES,
        beartype_namespace_modules=list(BEARTYPE_NAMESPACES),
        resolution="actual_PathFinder_then_native_registered_beartype_path_hook",
        selection="authenticated_source_bytes_before_native_get_code_and_AST_transform",
        root="ordinary_SourceFileLoader_before_original_beartype_this_package_registration",
        descendants="exact_BeartypeSourceFileLoader_and_same_native_package_configuration",
        bytecode_cache_reads=False,
        bytecode_cache_writes=False,
        code_witness="actual_native_transformed_module_code_and_completed_export_bindings",
        code_digest="typed_all_CodeType_fields_and_constant_bits@1",
        saved_module_and_export_hashes="source_forensics_not_independent_compilation_equality",
        saved_selections="exact_mode_pinned_module_bytes_and_closed_descriptor_roster",
        standalone_raw_AST_is_runtime_authority=False,
        native_builtin_export_terminal="exact_object.__sizeof___method_descriptor_only",
        selected_SIM_caller="one_native_compiled_typed_factory_in_same_original_globals",
        source_or_scientific_execution_released=False,
    )


def _read(path):
    path = Path(path)
    require(
        path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
        "Literal nonlinked source path required",
    )
    require(
        path.is_file() and path.stat().st_size <= MAX_FILE_BYTES, "Bounded source file required"
    )
    raw = path.read_bytes()
    return raw, hashlib.sha256(raw).hexdigest()


def _tree():
    rows = {}
    for path in sorted(BEARTYPE_ROOT.rglob("*.py")):
        raw, digest = _read(path)
        rows[str(path.relative_to(BEARTYPE_ROOT))] = dict(sha256=digest, bytes=len(raw))
    require(
        len(rows) == BEARTYPE_FILES
        and sum(row["bytes"] for row in rows.values()) == BEARTYPE_BYTES
        and seal(rows) == BEARTYPE_TREE_SHA256,
        "Pinned beartype source tree changed",
    )
    return rows


def _atom(value, seen=None):
    """Retain callable/code/cells/defaults, without traversing mutable module globals."""
    seen = set() if seen is None else seen
    kind = type(value)
    if value is None or kind in (str, int, bool, bytes):
        return kind, value
    if kind is float:
        return kind, struct.pack("!d", value)
    if id(value) in seen:
        return kind, id(value)
    seen.add(id(value))
    if kind is FunctionType:
        return (
            kind,
            id(value),
            id(value.__code__),
            value.__code__,
            id(value.__globals__),
            _atom(value.__defaults__, seen),
            _atom(value.__kwdefaults__, seen),
            tuple((id(cell), _atom(cell.cell_contents, seen)) for cell in value.__closure__ or ()),
            _atom(vars(value).get("__wrapped__"), seen),
        )
    if kind is MethodType:
        return kind, id(value.__self__), _atom(value.__func__, seen)
    if kind in (tuple, list):
        return kind, id(value), tuple(_atom(v, seen) for v in value)
    if kind is dict:
        return kind, id(value), tuple((_atom(k, seen), _atom(v, seen)) for k, v in value.items())
    return kind, id(value)


def _codes(unit):
    pending, found = [unit], {}
    while pending:
        code = pending.pop()
        found.setdefault(code.co_qualname, []).append(code)
        pending.extend(v for v in code.co_consts if type(v) is CodeType)
    return found


class Runtime:
    """Authenticate the installed compiler before importing any original module."""

    def __init__(self):
        require(sys.dont_write_bytecode is True, "Native reference requires -B")
        self.files = _tree()
        spec = importlib.util.find_spec("beartype")
        require(
            spec is not None and spec.origin == str(BEARTYPE_ROOT / "__init__.py"),
            "Exact pinned beartype import origin required",
        )
        self.loader_module = importlib.import_module("beartype.claw._importlib._clawimpload")
        self.trie = importlib.import_module("beartype.claw._package.clawpkgtrie")
        self.state_module = importlib.import_module("beartype.claw._clawstate")
        self.hook_module = importlib.import_module("beartype.claw._importlib.clawimpmain")
        self.transformer_module = importlib.import_module("beartype.claw._ast.clawastmain")
        self.loader_type = self.loader_module.BeartypeSourceFileLoader
        self.get_conf = self.trie.get_package_conf_or_none
        self.state = self.state_module.claw_state
        self._bindings = self.bindings()
        self._verify_definitions()
        self.verify()

    def bindings(self):
        loader = self.loader_module
        transform = self.transformer_module.BeartypeNodeTransformer
        return (
            self.loader_type,
            loader.BeartypeSourceFileLoader,
            self.loader_type.__mro__,
            _atom(self.loader_type.__init__),
            _atom(self.loader_type.get_code),
            _atom(self.loader_type.source_to_code),
            _atom(loader.decode_source),
            _atom(vars(loader).get("compile", builtins.compile)),
            type(loader.PyCF_ONLY_AST),
            loader.PyCF_ONLY_AST,
            loader._bootstrap_external,
            _atom(loader.cache_from_source_beartype),
            _atom(loader.cache_from_source_original),
            loader.BeartypeNodeTransformer,
            self.transformer_module.BeartypeNodeTransformer,
            _atom(transform.visit),
            _atom(transform.generic_visit),
            tuple((k, _atom(v)) for k, v in vars(transform).items() if type(v) is FunctionType),
            self.trie.get_package_conf_or_none,
            _atom(self.trie.get_package_conf_or_none),
            self.state_module.claw_state,
            _atom(self.hook_module.add_beartype_pathhook),
            importlib.machinery.PathFinder.find_spec.__func__,
        )

    def _verify_definitions(self):
        for fn in (
            self.loader_type.__init__,
            self.loader_type.get_code,
            self.loader_type.source_to_code,
            self.get_conf,
            self.hook_module.add_beartype_pathhook,
            *[
                v
                for v in vars(self.transformer_module.BeartypeNodeTransformer).values()
                if type(v) is FunctionType
            ],
        ):
            raw, _ = _read(Path(fn.__code__.co_filename))
            compiled = compile(raw, fn.__code__.co_filename, "exec", dont_inherit=True)
            matches = _codes(compiled).get(fn.__qualname__, ())
            require(len(matches) == 1 and fn.__code__ == matches[0], "Loaded compiler code drift")

    def verify(self, *, sources=True):
        require(
            self.bindings() == self._bindings, "Native compiler callable/registry authority drift"
        )
        require(
            self.get_conf is self.trie.get_package_conf_or_none, "Native configuration getter drift"
        )
        for name, module in tuple(sys.modules.items()):
            if name == "beartype" or name.startswith("beartype."):
                require(type(module) is ModuleType, "Actual beartype module required")
                if module.__file__ is None:
                    self.namespace_record(name, module)
                    continue
                path = Path(module.__file__)
                relative = str(path.relative_to(BEARTYPE_ROOT))
                require(relative in self.files, "Unpinned beartype module")
                if sources:
                    _, digest = _read(path)
                    require(
                        digest == self.files[relative]["sha256"], "Loaded beartype source changed"
                    )

    def record(self):
        self.verify()
        modules, namespaces = {}, {}
        for name, module in tuple(sys.modules.items()):
            if name == "beartype" or name.startswith("beartype."):
                if module.__file__ is None:
                    namespaces[name] = self.namespace_record(name, module)
                    continue
                path = Path(module.__file__)
                modules[name] = dict(
                    path=str(path),
                    sha256=self.files[str(path.relative_to(BEARTYPE_ROOT))]["sha256"],
                )
        components = {
            name: dict(
                file=fn.__code__.co_filename,
                qualified=fn.__qualname__,
                code_sha256=code_sha256(fn.__code__),
            )
            for name, fn in (
                ("get_code", self.loader_type.get_code),
                ("source_to_code", self.loader_type.source_to_code),
                ("configuration", self.get_conf),
                ("path_hook_factory", self.hook_module.add_beartype_pathhook),
            )
        }
        return dict(
            policy=specification(),
            files=self.files,
            loaded_modules=modules,
            namespace_modules=namespaces,
            compiler_components=components,
        )

    def namespace_record(self, name, module):
        require(name in BEARTYPE_NAMESPACES, "Undeclared compiler namespace module")
        path = BEARTYPE_ROOT.joinpath(*name.split(".")[1:])
        require(
            module.__file__ is None
            and module.__spec__.origin is None
            and type(module.__loader__) is importlib.machinery.NamespaceLoader
            and list(module.__path__) == [str(path)]
            and list(module.__spec__.submodule_search_locations) == [str(path)]
            and not any(p.is_symlink() for p in (path, *path.parents))
            and not (path / "__init__.py").exists()
            and any(
                key.startswith(str(path.relative_to(BEARTYPE_ROOT)) + "/") for key in self.files
            ),
            "Exact pinned compiler namespace path/loader required",
        )
        return dict(
            paths=[str(path)],
            loader="_frozen_importlib_external.NamespaceLoader",
            source_tree_sha256=BEARTYPE_TREE_SHA256,
        )


class _SelectedSource:
    """Only I/O/capture overrides; native compiler methods are inherited unchanged."""

    def get_data(self, path):
        if path.endswith(".pyc"):
            raise OSError("Reference bytecode cache reuse is forbidden")
        owner = self._original_owner
        owner._check_loader(self)
        require(
            self._original_compiling and self._original_stage == "executing",
            "Source reads require the active native compile",
        )
        require(path == self.path, "Only the exact declared source read is available")
        raw, digest = _read(Path(path))
        row = owner.inventory[self._original_relative]
        require(digest == row["sha256"], "Original module source drift")
        selected, changes = owner.select(self._original_relative, raw, owner.mode)
        require(type(selected) is bytes, "Selected source bytes required")
        self._original_read = dict(
            path=path,
            sha256=digest,
            selected_sha256=hashlib.sha256(selected).hexdigest(),
            selections=changes,
        )
        return selected

    def set_data(self, path, data, **kwargs):
        raise ImportRejected("Original reference bytecode writes are forbidden")

    def get_code(self, fullname):
        owner = self._original_owner
        owner._check_loader(self)
        require(
            fullname == self.name
            and self._original_code is None
            and self._original_stage == "executing"
            and not self._original_compiling
            and owner in sys.meta_path,
            "One fresh native module compile required",
        )
        before = self._original_runtime.loader_module._bootstrap_external.cache_from_source
        primary = None
        self._original_compiling = True
        try:
            code = self._original_base.get_code(self, fullname)
        except BaseException as error:
            primary = error
            raise
        finally:
            self._original_compiling = False
            if (
                self._original_runtime.loader_module._bootstrap_external.cache_from_source
                is not before
            ):
                error = ImportRejected("Native compiler cache hook was not restored")
                self._original_captures.append(error)
                if primary is None:
                    raise error
        require(
            type(code) is CodeType and self._original_read is not None,
            "Fresh source compilation required",
        )
        expected_conf = self._original_conf
        require(
            expected_conf is None
            or self._module_conf is expected_conf
            and self._module_name == fullname,
            "Actual native import configuration changed",
        )
        self._original_code = code
        return code

    def source_to_code(self, data, path, *, _optimize=-1):
        self._original_owner._check_loader(self)
        require(
            self._original_compiling
            and self._original_stage == "executing"
            and self._original_owner in sys.meta_path
            and path == self.path
            and self._original_transforms == 0
            and type(data) is bytes
            and self._original_read is not None
            and hashlib.sha256(data).hexdigest() == self._original_read["selected_sha256"],
            "Actual active selected-source compiler boundary required",
        )
        self._original_transforms += 1
        return self._original_base.source_to_code(self, data, path, _optimize=_optimize)

    def exec_module(self, module):
        owner = self._original_owner
        owner._check_loader(self)
        require(self._original_module is None, "Original module execution is one-shot")
        self._original_module = module
        self._original_stage = "executing"
        pending = None
        try:
            self._original_base.exec_module(self, module)
            self._original_source_returned = True
            self._original_exports = owner._exports(module)
            self._original_stage = "completed"
        except BaseException as error:
            pending = error
            if self._original_source_returned:
                self._original_captures.append(error)
                self._original_stage = "capture_failed"
            else:
                self._original_error = error
                self._original_stage = "failed"
            raise
        finally:
            try:
                owner._update(self)
            except BaseException as error:
                self._original_captures.append(error)
                if pending is None:
                    raise


class Package(importlib.abc.MetaPathFinder):
    def __init__(self, root, inventory, mode, select, *, namespace="betse"):
        self.root, self.inventory, self.mode = Path(root), inventory, mode
        self.select, self.namespace = select, namespace
        self.loaded, self.used, self.runtime = {}, False, None
        self._loaders, self._classes, self._registration = {}, {}, None
        self._selection_binding = _atom(select)
        self._adapter_binding = self._adapter_atoms()
        self._origins = {}
        self._programs = {}
        self._class_shapes, self._base_atoms = {}, {}
        self._metadata_binding = (str(self.root), id(inventory), seal(inventory), mode, namespace)
        self._selection_globals = {
            name: _atom(select.__globals__[name])
            for name in select.__code__.co_names
            if name in select.__globals__ and type(select.__globals__[name]) is FunctionType
        }

    @staticmethod
    def _adapter_atoms():
        return tuple(
            (name, _atom(fn))
            for name, fn in vars(_SelectedSource).items()
            if type(fn) is FunctionType
        )

    @staticmethod
    def _base_binding(base):
        return tuple(
            (name, _atom(getattr(base, name)))
            for name in ("get_code", "source_to_code", "exec_module", "get_data")
        )

    def __enter__(self):
        require(not self.used, "Original package workflow is one-shot")
        require(
            not any(n == self.namespace or n.startswith(self.namespace + ".") for n in sys.modules),
            "Fresh original package required",
        )
        self.used = True
        self.runtime = Runtime()
        require(
            self.runtime.get_conf(self.namespace) is None, "Original package must register itself"
        )
        sys.meta_path.insert(0, self)
        return self

    def __exit__(self, kind, error, tb):
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        return False

    def find_spec(self, fullname, path=None, target=None):
        if fullname != self.namespace and not fullname.startswith(self.namespace + "."):
            return None
        require(
            self.used and self in sys.meta_path and target is None,
            "Active one-shot original import required",
        )
        require(
            fullname not in self._loaders and len(self._loaders) < MAX_MODULES,
            "Original reload/capacity refused",
        )
        self.runtime.verify(sources=False)
        stem = fullname.replace(".", "/")
        relative = stem + "/__init__.py"
        package = relative in self.inventory
        if not package:
            relative = stem + ".py"
        require(relative in self.inventory, "Undeclared original module: " + fullname)
        expected = str(self.root / relative)
        search = [str(self.root)] if fullname == self.namespace else path
        spec = importlib.machinery.PathFinder.find_spec(fullname, search)
        require(
            spec is not None and spec.origin == expected,
            "Actual PathFinder original origin mismatch",
        )
        native = spec.loader
        conf = self.runtime.get_conf(fullname)
        if fullname == self.namespace:
            require(
                conf is None and type(native) is importlib.machinery.SourceFileLoader,
                "Ordinary unhooked root loader required",
            )
        else:
            registered = self.runtime.get_conf(self.namespace)
            require(
                conf is not None
                and conf is registered
                and type(native) is self.runtime.loader_type
                and self.runtime.state.beartype_pathhook in sys.path_hooks,
                "Actual original beartype registration/path-hook loader required",
            )
            if self._registration is None:
                self._registration = registered, self.runtime.state.beartype_pathhook
            require(
                self._registration[0] is registered
                and self._registration[1] is self.runtime.state.beartype_pathhook,
                "Original registration epoch changed",
            )
        base = type(native)
        if base not in self._classes:
            self._classes[base] = type(
                "SelectedOriginalSourceLoader", (_SelectedSource, base), {"__module__": __name__}
            )
            self._class_shapes[base] = tuple(vars(self._classes[base]).items())
            self._base_atoms[base] = self._base_binding(base)
        loader = self._classes[base](fullname, expected)
        loader._original_owner, loader._original_runtime = self, self.runtime
        loader._original_native, loader._original_base = native, base
        loader._original_relative, loader._original_conf = relative, conf
        loader._original_read = loader._original_code = loader._original_module = None
        loader._original_exports, loader._original_stage, loader._original_error = (
            {},
            "resolved",
            None,
        )
        loader._original_captures = []
        loader._original_compiling, loader._original_transforms = False, 0
        loader._original_source_returned = False
        self._loaders[fullname] = loader
        self._origins[loader] = (native, base, conf, type(loader), fullname, expected, relative)
        _ISSUED[loader] = self
        spec.loader = loader
        loader._original_spec = spec
        return spec

    def _check_loader(self, loader):
        origin = self._origins.get(loader)
        require(
            _ISSUED.get(loader) is self
            and self._loaders.get(loader.name) is loader
            and type(loader) is self._classes.get(loader._original_base)
            and tuple(vars(type(loader)).items()) == self._class_shapes.get(loader._original_base)
            and self._base_binding(loader._original_base)
            == self._base_atoms.get(loader._original_base)
            and loader._original_runtime is self.runtime
            and _atom(self.select) == self._selection_binding
            and self._adapter_atoms() == self._adapter_binding
            and self._metadata_binding
            == (str(self.root), id(self.inventory), seal(self.inventory), self.mode, self.namespace)
            and {name: _atom(self.select.__globals__.get(name)) for name in self._selection_globals}
            == self._selection_globals
            and origin is not None
            and origin[0] is loader._original_native
            and origin[1] is loader._original_base
            and origin[2] is loader._original_conf
            and origin[3] is type(loader)
            and origin[4:] == (loader.name, loader.path, loader._original_relative),
            "Actual issued loader/selection authority changed",
        )
        require(
            type(loader._original_native) is loader._original_base,
            "Original PathFinder loader identity changed",
        )
        require(
            loader._original_native.name == loader.name
            and loader._original_native.path == loader.path,
            "Native finder loader path drift",
        )
        self.runtime.verify(sources=False)

    @staticmethod
    def _exports(module):
        exports = {}
        for name, value in tuple(vars(module).items()):
            if type(value) is FunctionType and value.__module__ == module.__name__:
                exports[name] = value, _atom(value)
            elif isinstance(value, type) and value.__module__ == module.__name__:
                exports[name] = value, (type(value), id(value))
                for attr, fn in tuple(vars(value).items()):
                    if type(fn) in (staticmethod, classmethod):
                        fn = fn.__func__
                    if type(fn) is FunctionType:
                        exports[name + "." + attr] = fn, _atom(fn)
        return exports

    def _update(self, loader):
        read = loader._original_read or {}
        self.loaded[loader.name] = dict(
            **read,
            stage=loader._original_stage,
            loader_base=loader._original_base.__module__ + "." + loader._original_base.__qualname__,
            native_beartype=loader._original_conf is not None,
            module_code_sha256=None
            if loader._original_code is None
            else code_sha256(loader._original_code),
            bytecode_cache_used=False,
            capture_errors=[type(error).__name__ for error in loader._original_captures],
            source_returned=loader._original_source_returned,
            source_error=None
            if loader._original_error is None
            else type(loader._original_error).__module__
            + "."
            + type(loader._original_error).__qualname__,
            export_code_witnesses=self._export_witnesses(loader),
        )

    @staticmethod
    def _export_witnesses(loader):
        values = {}
        for name, (fn, _) in loader._original_exports.items():
            if type(fn) is not FunctionType:
                continue
            seen, chain = set(), []
            while fn is not None:
                if type(fn) is MethodDescriptorType and fn is object.__sizeof__:
                    chain.append(
                        dict(
                            kind="builtin_terminal",
                            module="builtins",
                            qualified="object.__sizeof__",
                            descriptor_type="builtins.method_descriptor",
                        )
                    )
                    break
                require(
                    type(fn) is FunctionType and id(fn) not in seen and len(chain) < 16,
                    "Bounded actual export delegate chain required: "
                    + name
                    + " -> "
                    + type(fn).__module__
                    + "."
                    + type(fn).__qualname__,
                )
                seen.add(id(fn))
                chain.append(
                    dict(
                        kind="python_code",
                        file=fn.__code__.co_filename,
                        qualified=fn.__qualname__,
                        code_sha256=code_sha256(fn.__code__),
                    )
                )
                fn = vars(fn).get("__wrapped__")
            values[name] = chain
        return values

    def owns(self, module):
        require(type(module) is ModuleType, "Actual original module required")
        loader = self._loaders.get(module.__name__)
        require(loader is not None, "Original module was not issued by this package")
        self._check_loader(loader)
        require(
            loader._original_stage == "completed"
            and loader._original_module is module
            and not loader._original_captures
            and sys.modules.get(module.__name__) is module
            and module.__loader__ is loader
            and module.__spec__ is loader._original_spec
            and module.__spec__.loader is loader
            and module.__spec__.origin == module.__file__ == loader.path,
            "Actual completed original module/loader/spec changed",
        )
        return loader

    def export(self, name, qualified):
        module = sys.modules.get(name)
        loader = self.owns(module)
        value = module
        parts = qualified.split(".")
        for index, part in enumerate(parts):
            value = vars(value)[part]
            if index < len(parts) - 1:
                require(
                    value is loader._original_exports[".".join(parts[: index + 1])][0],
                    "Original exported holder changed",
                )
        if type(value) in (staticmethod, classmethod):
            value = value.__func__
        retained, binding = loader._original_exports[qualified]
        require(
            value is retained and _atom(value) == binding,
            "Original export/wrapper/code binding changed",
        )
        return value

    def code_for(self, name, qualified):
        loader = self.owns(sys.modules.get(name))
        found = _codes(loader._original_code).get(qualified, ())
        require(len(found) == 1, "Unique actual transformed original code required")
        return found[0]

    def _bind_SIM_caller(self, module, unit):
        """One native compiler attempt for the explicit private retained caller."""
        self.verify()
        parent = self.owns(module)
        require(
            not self._programs
            and type(unit) is ast.Module
            and len(unit.body) == 1
            and type(unit.body[0]) is ast.FunctionDef
            and unit.body[0].name == SIM_ENTRY
            and not unit.body[0].decorator_list
            and [arg.arg for arg in unit.body[0].args.args] == ["self", "sim", "cells", "p_old"],
            "Exact one-shot retained SIM caller factory required",
        )
        raw = ast.unparse(unit).encode() + b"\n"
        original_raw, original_sha = _read(Path(parent.path))
        require(
            original_sha == self.inventory[parent._original_relative]["sha256"],
            "Actual parent caller source changed",
        )
        spec = importlib.machinery.PathFinder.find_spec(
            module.__name__, list(sys.modules[module.__package__].__path__)
        )
        require(
            spec is not None
            and spec.origin == parent.path
            and type(spec.loader) is self.runtime.loader_type
            and self.runtime.get_conf(module.__name__) is parent._original_conf,
            "Same original path-hook compiler/configuration required",
        )
        base, owner = type(spec.loader), self

        class ProgramSource(base):
            def get_data(actual, path):
                if path.endswith(".pyc"):
                    raise OSError("No selected-caller bytecode reuse")
                owner._check_loader(parent)
                require(
                    path == parent.path and _read(Path(path)) == (original_raw, original_sha),
                    "Exact live caller source required",
                )
                return raw

            def set_data(actual, path, data, **kwargs):
                raise ImportRejected("No selected-caller bytecode writes")

        native = ProgramSource(module.__name__, parent.path)
        state = dict(
            stage="compiling",
            parent=parent,
            native=native,
            raw_source=raw,
            original_source_sha256=original_sha,
            source_sha256=hashlib.sha256(raw).hexdigest(),
            AST_sha256=hashlib.sha256(ast.dump(unit).encode()).hexdigest(),
            code=None,
            function=None,
            error=None,
        )
        self._programs[module.__name__] = state
        before = dict(vars(module))
        try:
            code = base.get_code(native, module.__name__)
            state["code"] = code
            require(
                native._module_conf is parent._original_conf
                and native._module_name == module.__name__,
                "Actual selected-caller beartype compiler did not enter",
            )
            require(SIM_ENTRY not in before, "Caller factory cannot overwrite an existing symbol")
            exec(code, vars(module))
            require(
                all(vars(module).get(key) is value for key, value in before.items()),
                "Selected caller factory changed an existing original global",
            )
            require(
                all(
                    key == SIM_ENTRY or key.startswith("__beartype")
                    for key in vars(module).keys() - before.keys()
                ),
                "Unexpected selected-caller namespace write",
            )
            function = vars(module)[SIM_ENTRY]
            require(
                type(function) is FunctionType, "Actual native-decorated selected caller required"
            )
            state["function"], state["binding"] = function, _atom(function)
            state["stage"] = "completed"
        except BaseException as error:
            state["error"], state["stage"] = error, "failed"
            raise
        return function

    def program_export(self, name, entry):
        require(entry == SIM_ENTRY and name in self._programs, "Actual selected caller unavailable")
        module = sys.modules.get(name)
        self.owns(module)
        state = self._programs[name]
        function = vars(module).get(entry)
        require(
            state["stage"] == "completed"
            and function is state["function"]
            and _atom(function) == state["binding"],
            "Selected caller wrapper/delegate/code changed",
        )
        return function

    def program_code(self, name, entry):
        self.program_export(name, entry)
        found = _codes(self._programs[name]["code"]).get(entry, ())
        require(len(found) == 1, "Actual transformed selected caller code required")
        return found[0]

    def verify(self):
        require(self.used and self.runtime is not None, "Original package was not entered")
        self.runtime.verify()
        if self._registration is not None:
            conf, hook = self._registration
            require(
                self.runtime.get_conf(self.namespace) is conf
                and self.runtime.state.beartype_pathhook is hook
                and hook in sys.path_hooks,
                "Original package registration changed",
            )
        for name, loader in self._loaders.items():
            self.owns(sys.modules.get(name))
            _, digest = _read(Path(loader.path))
            require(
                digest == self.inventory[loader._original_relative]["sha256"],
                "Original source bytes changed",
            )
        for name in self._programs:
            self.program_export(name, SIM_ENTRY)

    def record(self):
        return dict(
            kind=KIND,
            mode=self.mode,
            policy=specification(),
            runtime=None if self.runtime is None else self.runtime.record(),
            modules=self.loaded,
            programs={
                name: dict(
                    stage=row["stage"],
                    source_sha256=row["source_sha256"],
                    original_source_sha256=row["original_source_sha256"],
                    AST_sha256=row["AST_sha256"],
                    module_code_sha256=None if row["code"] is None else code_sha256(row["code"]),
                    loader_base=self.runtime.loader_type.__module__
                    + "."
                    + self.runtime.loader_type.__qualname__,
                    native_beartype=True,
                    entry=SIM_ENTRY,
                )
                for name, row in self._programs.items()
            },
        )


def owner_of(module):
    require(type(module) is ModuleType, "Original module required")
    owner = _ISSUED.get(module.__loader__)
    require(owner is not None, "Actual process-local original loader issuance unavailable")
    owner.owns(module)
    return owner


def expected_selections(native_root, native, mode):
    """Independently derive the two byte selections; no original body is run.

    Readers authenticate the original file pins and mode before accepting the
    producer's descriptions. Every other imported module must remain byte exact.
    This is source-text validation, not independent beartype code reconstruction.
    """
    require(type(mode) is str and mode in ("original", "disabled"), "Exact selection mode required")
    result = {}
    for relative, expected_pin in SELECTED_NATIVE_FILES.items():
        path = Path(native_root) / relative
        raw, digest = _read(path)
        require(
            digest == expected_pin == native[relative]["sha256"],
            "Pinned selected-module source changed",
        )
        tree = ast.parse(raw)
        class_name, method_name = (
            ("Simulator", "run_sim_core")
            if relative.endswith("sim.py")
            else ("Cells", "make_world")
        )
        classes = [
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        require(len(classes) == 1, "Unique selected original class required")
        methods = [
            node
            for node in classes[0].body
            if isinstance(node, ast.FunctionDef) and node.name == method_name
        ]
        require(len(methods) == 1, "Unique selected original method required")
        method, edits, descriptors = methods[0], [], []
        if relative.endswith("sim.py"):
            require(
                len(method.body) >= 2
                and ast.unparse(method.body[-2]) == "self._pickle_phase(phase)"
                and isinstance(method.body[-1], ast.If)
                and ast.unparse(method.body[-1].test) == "exception_instability is not None",
                "Exact original terminal suffix required",
            )
            descriptors.append(
                dict(
                    method="Simulator.run_sim_core",
                    first_excluded_line=method.body[-2].lineno,
                    retained_statement_sha256=hashlib.sha256(
                        ast.dump(
                            ast.Module(body=method.body[:-2], type_ignores=[]),
                            include_attributes=False,
                        ).encode()
                    ).hexdigest(),
                    retained_native_instability_checked_by_observer=True,
                )
            )
            edits.extend((node, b"") for node in method.body[-2:])
        elif mode == "disabled":
            stores = [
                node
                for node in method.body
                if isinstance(node, ast.Assign)
                and ast.unparse(node.targets[0]) == "(_, self.lapENV_P_inv)"
            ]
            require(
                len(stores) == 1
                and isinstance(stores[0].value, ast.Call)
                and ast.unparse(stores[0].value.func) == "self.grid_obj.makeLaplacian",
                "Unique original flux inverse call required",
            )
            edits.append((stores[0].value, b"(None, None)"))
            descriptors.append(
                dict(method="Cells.make_world", omitted_flux_call_line=stores[0].lineno)
            )
        offsets, total = [], 0
        for line in raw.splitlines(keepends=True):
            offsets.append(total)
            total += len(line)
        spans = []
        for node, value in edits:
            start = offsets[node.lineno - 1] + node.col_offset
            end = offsets[node.end_lineno - 1] + node.end_col_offset
            segment = raw[start:end]
            require(
                len(value) <= len(segment) and (not value or b"\n" not in segment),
                "Exact selected-byte replacement span required",
            )
            spaces = bytes(c if c in (10, 13) else 32 for c in segment)
            spans.append((start, end, value + spaces[len(value) :]))
        selected = raw
        for start, end, replacement in sorted(spans, reverse=True):
            selected = selected[:start] + replacement + selected[end:]
        result[relative] = dict(
            selected_sha256=hashlib.sha256(selected).hexdigest(), selections=descriptors
        )
    return result


def validate_record(record, producers, native, native_root, *, mode, selections, namespace="betse"):
    """Stdlib-only saved-reader contract. This never imports a runtime or model."""
    require(
        type(record) is dict
        and set(record) == {"kind", "mode", "policy", "runtime", "modules", "programs"},
        "Exact native import record required",
    )
    require(
        record["kind"] == KIND and seal(record["policy"]) == seal(specification()),
        "Native import policy changed",
    )
    require(
        type(mode) is str
        and mode in ("original", "disabled")
        and type(record["mode"]) is str
        and record["mode"] == mode,
        "Exact expected flux mode required",
    )
    selected = expected_selections(native_root, native, mode) if namespace == "betse" else {}
    require(
        type(selections) is dict
        and seal(selections) == seal({path: row["selections"] for path, row in selected.items()}),
        "Declared selected-module roster differs from exact mode/source",
    )
    runtime = record["runtime"]
    require(
        type(runtime) is dict
        and set(runtime)
        == {"policy", "files", "loaded_modules", "namespace_modules", "compiler_components"},
        "Pinned compiler record required",
    )
    files = runtime["files"]
    require(
        seal(runtime["policy"]) == seal(specification())
        and type(files) is dict
        and len(files) == BEARTYPE_FILES
        and seal(files) == BEARTYPE_TREE_SHA256
        and sum(row["bytes"] for row in files.values()) == BEARTYPE_BYTES,
        "Saved beartype source tree differs from pinned compiler",
    )
    require(
        type(runtime["loaded_modules"]) is dict and runtime["loaded_modules"],
        "Reached compiler modules required",
    )
    for name, pin in runtime["loaded_modules"].items():
        require(
            name == "beartype" or name.startswith("beartype."), "Exact compiler namespace required"
        )
        relative = str(Path(pin["path"]).relative_to(BEARTYPE_ROOT))
        require(
            pin == dict(path=str(BEARTYPE_ROOT / relative), sha256=files[relative]["sha256"]),
            "Saved compiler origin/hash drift",
        )
    namespaces = runtime["namespace_modules"]
    require(
        type(namespaces) is dict and set(namespaces) <= set(BEARTYPE_NAMESPACES),
        "Exact declared compiler namespaces required",
    )
    for name, row in namespaces.items():
        require(
            row
            == dict(
                paths=[str(BEARTYPE_ROOT.joinpath(*name.split(".")[1:]))],
                loader="_frozen_importlib_external.NamespaceLoader",
                source_tree_sha256=BEARTYPE_TREE_SHA256,
            ),
            "Saved compiler namespace drift",
        )
    components = runtime["compiler_components"]
    require(
        type(components) is dict
        and set(components) == {"get_code", "source_to_code", "configuration", "path_hook_factory"},
        "Exact native compiler code witness roster required",
    )
    for role, row in components.items():
        require(
            type(row) is dict and set(row) == {"file", "qualified", "code_sha256"},
            "Exact compiler code witness required",
        )
        path = Path(row["file"])
        expected_file, expected_qualified = COMPILER_ROLES[role]
        require(
            path == BEARTYPE_ROOT / expected_file and row["qualified"] == expected_qualified,
            "Native compiler role/file/qualified-name association changed",
        )
        relative = str(path.relative_to(BEARTYPE_ROOT))
        raw, digest = _read(path)
        require(digest == files[relative]["sha256"], "Saved compiler body source drift")
        found = _codes(compile(raw, str(path), "exec", dont_inherit=True)).get(row["qualified"], ())
        require(
            len(found) == 1 and code_sha256(found[0]) == row["code_sha256"],
            "Saved actual compiler code differs from pinned source",
        )
    require(
        type(producers) is dict and namespace in producers and record["modules"] == producers,
        "Complete native module lifecycle roster required",
    )
    for name, row in producers.items():
        require(
            name == namespace or name.startswith(namespace + "."),
            "Exact original module namespace required",
        )
        require(
            type(row) is dict
            and set(row)
            == {
                "path",
                "sha256",
                "selected_sha256",
                "selections",
                "stage",
                "loader_base",
                "native_beartype",
                "module_code_sha256",
                "bytecode_cache_used",
                "capture_errors",
                "source_returned",
                "source_error",
                "export_code_witnesses",
            },
            "Exact original loader witness schema required",
        )
        relative = str(Path(row["path"]).relative_to(Path(native_root)))
        stem = name.replace(".", "/")
        expected_path = stem + "/__init__.py" if stem + "/__init__.py" in native else stem + ".py"
        require(relative == expected_path, "Original module name/path association changed")
        require(native[relative]["sha256"] == row["sha256"], "Original module source hash drift")
        hooked = name != namespace
        expected = (
            "beartype.claw._importlib._clawimpload.BeartypeSourceFileLoader"
            if hooked
            else "_frozen_importlib_external.SourceFileLoader"
        )
        require(
            row["stage"] == "completed"
            and row["native_beartype"] is hooked
            and row["loader_base"] == expected
            and row["bytecode_cache_used"] is False
            and row["capture_errors"] == []
            and row["source_returned"] is True
            and row["source_error"] is None,
            "Original native compiler lifecycle incomplete",
        )
        for field in ("sha256", "selected_sha256", "module_code_sha256"):
            require(
                type(row[field]) is str
                and len(row[field]) == 64
                and all(c in "0123456789abcdef" for c in row[field]),
                "Typed code/source digest required",
            )
        require(type(row["selections"]) is list, "Declared source selections required")
        target = selected.get(relative, dict(selected_sha256=row["sha256"], selections=[]))
        require(
            row["selected_sha256"] == target["selected_sha256"]
            and seal(row["selections"]) == seal(target["selections"]),
            "Selected module bytes/descriptors differ from exact declared mode",
        )
        require(type(row["export_code_witnesses"]) is dict, "Exact export code witnesses required")
        for qualified, chain in row["export_code_witnesses"].items():
            require(
                type(qualified) is str and type(chain) is list and 1 <= len(chain) <= 16,
                "Bounded ordered export wrapper chain required",
            )
            for entry in chain:
                require(
                    type(entry) is dict
                    and (
                        entry
                        == dict(
                            kind="builtin_terminal",
                            module="builtins",
                            qualified="object.__sizeof__",
                            descriptor_type="builtins.method_descriptor",
                        )
                        or set(entry) == {"kind", "file", "qualified", "code_sha256"}
                        and entry["kind"] == "python_code"
                        and all(type(v) is str for v in entry.values())
                        and len(entry["code_sha256"]) == 64
                    ),
                    "Typed export/code witness required",
                )
        if not row["selections"]:
            require(row["selected_sha256"] == row["sha256"], "Undeclared source-byte selection")
    programs = record["programs"]
    require(
        type(programs) is dict and len(programs) <= 1, "Bounded selected-caller compiler roster"
    )
    for name, row in programs.items():
        require(
            name in producers
            and type(row) is dict
            and set(row)
            == {
                "stage",
                "source_sha256",
                "original_source_sha256",
                "AST_sha256",
                "module_code_sha256",
                "loader_base",
                "native_beartype",
                "entry",
            },
            "Exact selected-caller compiler witness required",
        )
        require(
            row["stage"] == "completed"
            and row["native_beartype"] is True
            and row["entry"] == SIM_ENTRY
            and row["loader_base"]
            == "beartype.claw._importlib._clawimpload.BeartypeSourceFileLoader"
            and row["original_source_sha256"] == producers[name]["sha256"],
            "Selected-caller native compiler lifecycle incomplete",
        )
        for field in (
            "source_sha256",
            "original_source_sha256",
            "AST_sha256",
            "module_code_sha256",
        ):
            require(
                type(row[field]) is str
                and len(row[field]) == 64
                and all(c in "0123456789abcdef" for c in row[field]),
                "Typed selected-caller code/source digest required",
            )
    return runtime["loaded_modules"]


def validate_runtime(record, inventory):
    compiler = record["runtime"]
    for name, pin in compiler["loaded_modules"].items():
        require(inventory["loaded_files"].get(name) == pin, "Compiler loaded-file witness drift")
    for name in compiler["namespace_modules"]:
        require(
            name in inventory["modules_without_files"], "Actual compiler namespace witness absent"
        )
