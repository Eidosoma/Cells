"""Private original-file namespaces for the independent multi-cell prefix.

This module imports only the standard library. The caller authenticates the
prepared AST groups and supplies the numerical libraries, image decoder, RNG
and log callback. ``build`` executes definitions and constant assignments, not
constructors, source methods, image decoding or numerical operators. It neither
imports the BETSE package nor installs substitutes in ``sys.modules``.

The normalized enum, three runtime type aliases and postponed annotations are
explicit adapters shared with the earlier independent prefix. This is not a
complete native package loader. Unprepared imports (including optional display
and caller-name helpers) fail when reached; their original branches stay intact.
"""

import __future__

import ast
import builtins
import copy
import hashlib
import math
import os.path
import sys
from abc import ABCMeta, abstractmethod
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from types import GeneratorType, ModuleType, SimpleNamespace

NUMPY_C_API_IMPORT = ("numpy._core._methods", (), 0)

# Definition order, not scientific execution order. Lazy original imports use
# these same private modules, including helpers added after the shared groups.
MODULE_ORDER = (
    "betse.exceptions",
    "betse.util.type.types",
    "betse.util.type.iterable.sequences",
    "betse.util.type.iterable.generators",
    "betse.util.type.cls.classes",
    "betse.lib.numpy.nparray",
    "betse.lib.numpy.npscalar",
    "betse.util.type.iterable.iterables",
    "betse.util.math.geometry.geopoint",
    "betse.util.type.numeric.floats",
    "betse.util.math.geometry.polygon.geopoly",
    "betse.util.math.geometry.polygon.geopolyconvex",
    "betse.util.math.mathoper",
    "betse.util.path.pathnames",
    "betse.util.path.dirs",
    "betse.util.path.paths",
    "betse.util.path.files",
    "betse.lib.pil.pilnumpy",
    "betse.util.math.mathinterp",
    "betse.science.math.toolbox",
    "betse.science.tissue.picker.tispickcls",
    "betse.science.tissue.picker.tispickimage",
    "betse.science.math.mesh",
    "betse.science.cells",
    "betse.science.parameters",
)

EXPORTS = {
    "Cells": ("betse.science.cells", "Cells"),
    "DECMesh": ("betse.science.math.mesh", "DECMesh"),
    "TissuePickerImage": ("betse.science.tissue.picker.tispickimage", "TissuePickerImage"),
    "TissuePickerImageMask": (
        "betse.science.tissue.picker.tispickimage",
        "TissuePickerImageMask",
    ),
    "store_parameters": ("betse.science.parameters", "store_parameters"),
}

# Only names needed by the retained definitions are bound. Each direct import
# resolves to the function/class in its original private module, not a flattened
# namespace with competing same-named functions.
DIRECT = {
    "betse.lib.numpy.nparray": {
        "sequences": "betse.util.type.iterable.sequences",
    },
    "betse.util.math.geometry.geopoint": {
        "iterables": "betse.util.type.iterable.iterables",
        "BetseMathLineException": "betse.exceptions:BetseMathLineException",
        "BetseMathPointException": "betse.exceptions:BetseMathPointException",
    },
    "betse.util.math.geometry.polygon.geopoly": {
        "BetseMathPolygonException": "betse.exceptions:BetseMathPolygonException",
    },
    "betse.util.math.geometry.polygon.geopolyconvex": {
        "geopoint": "betse.util.math.geometry.geopoint",
        "geopoly": "betse.util.math.geometry.polygon.geopoly",
        "iterables": "betse.util.type.iterable.iterables",
    },
    "betse.util.path.pathnames": {
        "BetsePathnameException": "betse.exceptions:BetsePathnameException",
    },
    "betse.util.path.files": {
        "BetseFileException": "betse.exceptions:BetseFileException",
    },
    "betse.lib.pil.pilnumpy": {
        "files": "betse.util.path.files",
        "pathnames": "betse.util.path.pathnames",
        "nparray": "betse.lib.numpy.nparray",
    },
    "betse.util.math.mathinterp": {
        "BetseMathInterpolationException": "betse.exceptions:BetseMathInterpolationException",
    },
    "betse.science.tissue.picker.tispickcls": {
        "nparray": "betse.lib.numpy.nparray",
        "toolbox": "betse.science.math.toolbox",
    },
    "betse.science.tissue.picker.tispickimage": {
        "BetseImageException": "betse.exceptions:BetseImageException",
        "pilnumpy": "betse.lib.pil.pilnumpy",
        "ImageModeType": "betse.lib.pil.pilnumpy:ImageModeType",
        "TissuePickerABC": "betse.science.tissue.picker.tispickcls:TissuePickerABC",
        "interp2d_linear": "betse.util.math.mathinterp:interp2d_linear",
        "files": "betse.util.path.files",
        "pathnames": "betse.util.path.pathnames",
    },
    "betse.science.math.mesh": {
        "BetseMathMeshException": "betse.exceptions:BetseMathMeshException",
        "is_convex": "betse.util.math.geometry.polygon.geopoly:is_convex",
        "is_cyclic_quad": "betse.util.math.geometry.polygon.geopoly:is_cyclic_quad",
        "orient_counterclockwise": (
            "betse.util.math.geometry.polygon.geopoly:orient_counterclockwise"
        ),
        "clip_counterclockwise": (
            "betse.util.math.geometry.polygon.geopolyconvex:clip_counterclockwise"
        ),
        "det1d": "betse.util.math.mathoper:det1d",
    },
    "betse.science.cells": {
        "BetseSimConfException": "betse.exceptions:BetseSimConfException",
        "DECMesh": "betse.science.math.mesh:DECMesh",
    },
    "betse.science.parameters": {"pathnames": "betse.util.path.pathnames"},
    "betse.util.type.iterable.iterables": {
        "BetseIterableException": "betse.exceptions:BetseIterableException",
    },
}


class RuntimeAssemblyError(ValueError):
    """Definition-time failure with the untouched partial private namespaces."""

    def __init__(self, module, source_error, modules, metadata):
        super().__init__("Independent namespace assembly failed: " + module)
        self.module = module
        self.source_error = source_error
        self.modules = {name: vars(value) for name, value in modules.items()}
        self.metadata = metadata


class _Numpy:
    """Delegate array operations while retaining the supplied private RNG."""

    def __init__(self, module, rng):
        self._module = module
        self.random = rng

    def __getattr__(self, name):
        return getattr(self._module, name)


def _module_name(relative):
    if type(relative) is not str:
        raise ValueError("Original relative source path required")
    path = Path(relative)
    name = relative.removesuffix(".py").replace("/", ".")
    if (
        not relative.endswith(".py")
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != relative
        or name not in MODULE_ORDER
    ):
        raise ValueError("Undeclared original module: " + relative)
    return name


def _imports(nodes):
    result = set()
    for root in nodes:
        for node in ast.walk(root):
            if isinstance(node, ast.Import):
                result.update((item.name, (), 0) for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                result.add((node.module or "", tuple(item.name for item in node.names), node.level))
    return result


def compile_groups(groups, *, native_root):
    """Compile source groups and describe imports without evaluating any AST.

    Authentication of the exact selected ASTs is the source assembler's job;
    this record binds both the supplied ASTs and their current original files.
    It does not infer literal-source correspondence from the file hashes alone.
    """
    root = Path(native_root).resolve(strict=True)
    selected = {}
    for relative, nodes in groups:
        name = _module_name(relative)
        for node in nodes:
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign)):
                raise ValueError("Only prepared definitions/constants may execute at module scope")
        selected.setdefault(name, []).extend(copy.deepcopy(nodes))
    if set(selected) != set(MODULE_ORDER):
        raise ValueError("Complete declared original namespace roster required")
    codes, requests, descriptions = {}, {}, {}
    for name in MODULE_ORDER:
        nodes = selected[name]
        definitions = []
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                definitions.append(node.name)
            else:
                if any(not isinstance(target, ast.Name) for target in node.targets):
                    raise ValueError("Module constants require plain names")
                definitions.extend(target.id for target in node.targets)
        if len(definitions) != len(set(definitions)):
            raise ValueError("Duplicate definition in original module: " + name)
        relative = name.replace(".", "/") + ".py"
        path = root / relative
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError("Original module must be a contained regular file: " + relative)
        module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
        codes[name] = compile(
            module,
            str(path),
            "exec",
            flags=__future__.annotations.compiler_flag,
            dont_inherit=True,
        )
        requests[name] = _imports(nodes)
        sites = {}

        def sites_in(body, output, prefix=""):
            for node in body:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    key = prefix + node.name
                    output[key] = {
                        "first_line": node.lineno,
                        "last_line": node.end_lineno,
                        "ast_sha256": hashlib.sha256(
                            ast.dump(node, include_attributes=False).encode()
                        ).hexdigest(),
                    }
                    sites_in(node.body, output, key + ".")

        sites_in(nodes, sites)
        descriptions[name] = {
            "file": str(path),
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "ast_sha256": hashlib.sha256(
                ast.dump(module, include_attributes=False).encode()
            ).hexdigest(),
            "definitions": definitions,
            "sites": sites,
            "imports": [
                {"name": imported, "fromlist": list(items), "level": level}
                for imported, items, level in sorted(requests[name])
            ],
        }
    metadata = {
        "kind": "cells.independent_multi_caller_namespace@1",
        "native_root": str(root),
        "modules": descriptions,
        "definition_order": list(MODULE_ORDER),
        "ast_authentication": "caller must bind the independently prepared literal AST groups",
        "annotations": (
            "postponed with the Python future compiler flag; not native type evaluation"
        ),
        "normalized_adapters": {
            "CellLatticeType": ["HEX", "SQUARE"],
            "SequenceTypes": ["collections.abc.Sequence", "supplied numpy.ndarray"],
            "NumpyArrayType": "supplied numpy.ndarray",
            "GeneratorType": "types.GeneratorType",
        },
        "external_dependencies": [
            "supplied numpy with private rng",
            "supplied image decoder",
            "supplied spline, hull, delaunay, tree",
            "supplied log callback",
            "stdlib abc, builtins, collections.abc, copy, enum, math, os.path, types",
        ],
        "import_policy": (
            "exact declared imports into prepared private modules or supplied numpy; "
            "one explicitly bound already-loaded NumPy C-API helper request"
        ),
        "implicit_numpy_c_api_import": {
            "name": NUMPY_C_API_IMPORT[0],
            "fromlist": [],
            "level": 0,
            "policy": "same supplied NumPy/core/methods objects already in sys.modules; no loader",
        },
        "unsupported_imports": [
            "matplotlib optional display branches",
            "betse.util.type.call.callers optional unimplemented-method exception",
        ],
        "sys_modules_modified": False,
        "constructors_methods_rng_decode_or_operators_executed": False,
        "full_package_or_phase_admission": False,
    }
    return codes, requests, metadata


def _private_modules(metadata):
    modules = {}
    for name in MODULE_ORDER:
        parts = name.split(".")
        for index in range(1, len(parts) + 1):
            current = ".".join(parts[:index])
            if current not in modules:
                module = modules[current] = ModuleType(current)
                module.__package__ = current.rpartition(".")[0]
                if current in metadata["modules"]:
                    module.__file__ = metadata["modules"][current]["file"]
                else:
                    module.__path__ = []
            if index > 1:
                setattr(modules[".".join(parts[: index - 1])], parts[index - 1], modules[current])
    return modules


def _cached_numpy_helpers(numpy):
    """Retain preloaded helpers without importing or running numerical code."""
    if type(numpy) is not ModuleType:
        return None
    core = vars(numpy).get("_core")
    methods = vars(core).get("_methods") if type(core) is ModuleType else None
    if type(methods) is not ModuleType:
        return None
    return numpy, core, methods


def _check_numpy_helpers(binding, proxy):
    if binding is None or type(proxy) is not _Numpy or proxy._module is not binding[0]:
        raise ImportError("Unbound cached NumPy C-API helper")
    numpy, core, methods = binding
    if (
        any(
            sys.modules.get(name) is not module or vars(module).get("__name__") != name
            for name, module in zip(
                ("numpy", "numpy._core", NUMPY_C_API_IMPORT[0]), binding, strict=True
            )
        )
        or vars(numpy).get("_core") is not core
        or vars(core).get("_methods") is not methods
    ):
        raise ImportError("Changed cached NumPy C-API helper ownership")


def _importer(owner, requests, modules, numpy, cached_helpers=None):
    def imports(name, globals=None, locals=None, fromlist=(), level=0):
        key = (name, tuple(fromlist or ()), level)
        if key == NUMPY_C_API_IMPORT:
            # ndarray.mean() calls this from the original caller's globals.
            # Match an ordinary empty-fromlist import's root return. NumPy's
            # C API then obtains the already-loaded helper from sys.modules.
            # Retain the private RNG proxy and never invoke an import loader.
            _check_numpy_helpers(cached_helpers, numpy)
            return numpy
        if level or "*" in key[1] or key not in requests:
            raise ImportError("Undeclared independent import in " + owner + ": " + str(name))
        if name == "numpy":
            target = numpy
        elif name in modules:
            target = modules[name]
        else:
            raise ImportError("Unprepared independent import in " + owner + ": " + name)
        for attribute in key[1]:
            if not hasattr(target, attribute):
                raise ImportError("Unprepared imported member: " + name + "." + attribute)
        return target if key[1] or name == "numpy" else modules[name.split(".")[0]]

    return imports


def build(groups, *, native_root, numpy, image, spline, hull, delaunay, tree, rng, log):
    """Build fresh original namespaces; the guarded caller owns later execution."""
    codes, requests, metadata = compile_groups(groups, native_root=native_root)
    modules = _private_modules(metadata)
    proxy = _Numpy(numpy, rng)
    cached_helpers = _cached_numpy_helpers(numpy)
    lattice = Enum("CellLatticeType", ("HEX", "SQUARE"))
    external = dict(
        ABCMeta=ABCMeta,
        abstractmethod=abstractmethod,
        Enum=Enum,
        np=proxy,
        array=numpy.array,
        ndarray=numpy.ndarray,
        math=math,
        copy=copy,
        SequenceTypes=(Sequence, numpy.ndarray),
        NumpyArrayType=numpy.ndarray,
        GeneratorType=GeneratorType,
        os_path=os.path,
        Image=image,
        RectBivariateSpline=spline,
        ConvexHull=hull,
        Delaunay=delaunay,
        cKDTree=tree,
        CellLatticeType=lattice,
        logs=SimpleNamespace(log_info=log, log_warning=log, log_debug=log),
    )
    for name in MODULE_ORDER:
        namespace = vars(modules[name])
        namespace.update(external)
        namespace["__builtins__"] = dict(
            vars(builtins),
            __import__=_importer(name, requests[name], modules, proxy, cached_helpers),
        )
        try:
            if name not in {"betse.exceptions", "betse.util.type.types"}:
                namespace["type_check"] = modules["betse.util.type.types"].type_check
            for key, declared in DIRECT.get(name, {}).items():
                module, _, attribute = declared.partition(":")
                value = modules[module]
                namespace[key] = getattr(value, attribute) if attribute else value
            exec(codes[name], namespace)
        except Exception as error:
            raise RuntimeAssemblyError(name, error, modules, metadata) from error
    try:
        result = {
            key: getattr(modules[module], attribute) for key, (module, attribute) in EXPORTS.items()
        }
    except Exception as error:
        raise RuntimeAssemblyError("exports", error, modules, metadata) from error
    result.update(
        CellLatticeType=lattice,
        modules={name: vars(modules[name]) for name in MODULE_ORDER},
        metadata=metadata,
    )
    return result
