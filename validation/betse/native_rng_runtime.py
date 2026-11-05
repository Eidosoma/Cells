"""File or interpreter provenance for RNG implementations; never read RNG state.

Shared observation metadata is deliberately independent of either model driver.
The original all-file runtime document remains valid. A built-in component uses
an explicit versioned record and is never described as a loaded shared library.
"""

import _imp
import importlib.machinery
import re
import sys
from pathlib import Path
from types import MethodDescriptorType, ModuleType

FILE = "validation/betse/native_rng_runtime.py"
KIND = "cells.rng_runtime_provenance@2"
MODULES = (
    "numpy",
    "numpy.random",
    "numpy.random.mtrand",
    "numpy.random._mt19937",
    "numpy.random.bit_generator",
    "random",
    "_random",
)
METHODS = ("seed", "getstate", "setstate", "random", "getrandbits")
BUILTIN_KIND = "cpython_builtin_module"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _pin(row):
    return (
        type(row) is dict
        and set(row) == {"path", "sha256"}
        and type(row["path"]) is str
        and Path(row["path"]).is_absolute()
        and type(row["sha256"]) is str
        and re.fullmatch("[0-9a-f]{64}", row["sha256"]) is not None
    )


def _builtin(name, module, executable):
    """Inspect the actual imported C type and loader without invoking either."""
    require(
        name == "_random"
        and type(module) is ModuleType
        and sys.modules.get(name) is module
        and vars(module).get("__name__") == name
        and vars(module).get("__file__") is None
        and name in sys.builtin_module_names
        and _imp.is_builtin(name) > 0
        and sys.implementation.name == "cpython",
        "Actual CPython built-in _random module required",
    )
    spec = vars(module).get("__spec__")
    loader = importlib.machinery.BuiltinImporter
    bootstrap = sys.modules.get("_frozen_importlib")
    require(
        type(bootstrap) is ModuleType
        and vars(bootstrap).get("BuiltinImporter") is loader
        and type(loader) is type
        and loader.__module__ == "_frozen_importlib"
        and loader.__qualname__ == "BuiltinImporter"
        and type(spec) is importlib.machinery.ModuleSpec
        and spec.name == name
        and spec.origin == "built-in"
        and spec.loader is loader
        and vars(module).get("__loader__") is loader
        and spec.has_location is False
        and spec.cached is None
        and spec.submodule_search_locations is None
        and not vars(spec).get("_initializing", False),
        "Actual built-in module/spec/loader association required",
    )
    native = vars(module).get("Random")
    python = sys.modules.get("random")
    require(
        type(native) is type
        and native.__module__ == "_random"
        and native.__qualname__ == "Random"
        and native.__bases__ == (object,)
        and all(
            type(vars(native).get(name)) is MethodDescriptorType
            and vars(native)[name].__objclass__ is native
            and vars(native)[name].__name__ == name
            for name in METHODS
        )
        and type(python) is ModuleType
        and vars(python).get("_random") is module
        and type(vars(python).get("Random")) is type
        and vars(python)["Random"].__bases__ == (native,)
        and type(vars(python).get("_inst")) is vars(python)["Random"],
        "Actual C Random type and Python random receiver ancestry required",
    )
    require(_pin(executable), "Bound interpreter executable required")
    return dict(
        kind=BUILTIN_KIND,
        name=name,
        origin="built-in",
        loader="_frozen_importlib.BuiltinImporter",
        has_location=False,
        cached=None,
        submodule_search_locations=None,
        export="_random.Random",
        methods=list(METHODS),
        executable_sha256=executable["sha256"],
    )


def _binding(inventory):
    files, builtins = {}, {}
    require(_pin(inventory.get("executable")), "Actual runtime executable required")
    for name in MODULES:
        module = sys.modules.get(name)
        require(type(module) is ModuleType, "Actual RNG runtime module required: " + name)
        if name in inventory["loaded_files"]:
            row = inventory["loaded_files"][name]
            require(
                _pin(row)
                and vars(module).get("__file__") is not None
                and str(Path(vars(module)["__file__"]).resolve()) == row["path"]
                and name not in inventory["modules_without_files"],
                "RNG file inventory and actual module disagree",
            )
            files[name] = row
        else:
            require(
                inventory["modules_without_files"].count(name) == 1,
                "Missing RNG module is not a declared built-in",
            )
            builtins[name] = _builtin(name, module, inventory["executable"])
    result = dict(
        python=inventory["python"],
        executable=inventory["executable"],
        numpy_version=vars(sys.modules["numpy"])["__version__"],
        files=files,
    )
    if builtins:
        result.update(
            kind=KIND,
            builtins=builtins,
            interpreter=dict(
                implementation=sys.implementation.name,
                cache_tag=sys.implementation.cache_tag,
                hexversion=sys.hexversion,
                builtin_module_names=list(sys.builtin_module_names),
            ),
        )
    validate(result)
    return result


def binding():
    """Read module/interpreter provenance only; no seed/getstate/draw is called."""
    from validation.betse import betse_normal_channel_join_runtime as runtime

    return _binding(runtime.inventory())


def validate(value):
    legacy = {"python", "executable", "numpy_version", "files"}
    require(
        type(value) is dict
        and set(value) in (legacy, legacy | {"kind", "builtins", "interpreter"})
        and all(type(value[k]) is str and value[k] for k in ("python", "numpy_version"))
        and _pin(value["executable"])
        and type(value["files"]) is dict
        and all(type(name) is str and _pin(row) for name, row in value["files"].items()),
        "Exact RNG runtime file/interpreter schema required",
    )
    if "kind" not in value:
        require(set(value["files"]) == set(MODULES), "Complete file-backed RNG runtime required")
        return
    require(
        value["kind"] == KIND
        and type(value["builtins"]) is dict
        and set(value["builtins"]) == {"_random"}
        and set(value["files"]) == set(MODULES) - {"_random"},
        "Explicit complete disjoint RNG origins required",
    )
    interpreter = value["interpreter"]
    require(
        type(interpreter) is dict
        and set(interpreter)
        == {"implementation", "cache_tag", "hexversion", "builtin_module_names"}
        and interpreter["implementation"] == "cpython"
        and type(interpreter["hexversion"]) is int
        and 0 <= interpreter["hexversion"] < 2**32
        and type(interpreter["builtin_module_names"]) is list
        and 1 <= len(interpreter["builtin_module_names"]) <= 1024
        and all(type(name) is str and name for name in interpreter["builtin_module_names"])
        and interpreter["builtin_module_names"] == sorted(set(interpreter["builtin_module_names"]))
        and "_random" in interpreter["builtin_module_names"],
        "Exact CPython built-in interpreter declaration required",
    )
    version = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value["python"])
    require(version is not None, "Exact interpreter version required for built-in provenance")
    parts = tuple(int(v) for v in version.groups())
    require(
        parts == tuple((interpreter["hexversion"] >> shift) & 255 for shift in (24, 16, 8))
        and interpreter["cache_tag"] == "cpython-" + str(parts[0]) + str(parts[1]),
        "Built-in interpreter version/cache tag differs",
    )
    expected = dict(
        kind=BUILTIN_KIND,
        name="_random",
        origin="built-in",
        loader="_frozen_importlib.BuiltinImporter",
        has_location=False,
        cached=None,
        submodule_search_locations=None,
        export="_random.Random",
        methods=list(METHODS),
        executable_sha256=value["executable"]["sha256"],
    )
    actual = value["builtins"]["_random"]
    require(
        type(actual) is dict
        and actual == expected
        and actual["has_location"] is False
        and type(actual["methods"]) is list,
        "Built-in module is not bound to its actual interpreter",
    )


def validate_saved(reader, value, *, executable, runtime_roots, final, completed):
    """Authenticate saved origins against the independently retained inventory."""
    validate(value)
    require(value["executable"] == executable, "Initial RNG interpreter executable changed")
    reader.bind(executable)
    roots = [Path(path) for path in runtime_roots]
    for row in value["files"].values():
        path = reader.bind(row)
        require(
            any(path.is_relative_to(root) for root in roots), "Undeclared initial RNG file origin"
        )
    if final is None:
        require(not completed, "Completed RNG witness needs final runtime evidence")
        return
    match_inventory(value, final)


def match_inventory(value, actual):
    """Match an independently authenticated inventory; this grants no root policy.

    The reference's existing reader binds every file and its full parent runtime.
    Root additionally enforces declared directories through ``validate_saved``.
    """
    validate(value)
    require(
        actual.get("python") == value["python"]
        and actual.get("executable") == value["executable"]
        and all(actual["loaded_files"].get(name) == row for name, row in value["files"].items()),
        "Initial RNG runtime differs from actual loaded producers",
    )
    for name in value.get("builtins", {}):
        require(
            name not in actual["loaded_files"]
            and type(actual.get("modules_without_files")) is list
            and actual["modules_without_files"].count(name) == 1,
            "Saved built-in RNG origin differs from actual runtime inventory",
        )
