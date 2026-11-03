"""Pinned original INIT constructor/initializer catalog, with no body evaluation.

The selected constructor accepts an actual existing Cells object through its
original optional argument. This catalog supplies no loader, pickle, phase,
parameter-transition, callback, package or physical authority.
"""

import ast
import copy
import hashlib
from pathlib import Path
from types import CodeType

NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
PINS = {
    "betse/science/phase/phasecls.py": (
        "e7c129aca1930fcb31884f32d4f2ebbb46d31113a66887a39c85ba0009b78ea8"
    ),
    "betse/science/sim.py": "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43",
    "betse/science/simrunner.py": (
        "6a9389f106d717dc83ea1a594a64aa5bde278cef9a17b2a8ff01251b08d7be8a"
    ),
    "betse/science/tissue/tishandler.py": (
        "057ddab87be773e5d338d0681bd503b12aee02861be0902d6ef46e1133d42f54"
    ),
    "betse/science/math/cache/cacheabc.py": (
        "0dbcc8d32758db0a9aa78834ae1ad3c178c702cb4ca0e9e03a798c19c1621549"
    ),
    "betse/science/math/cache/cachevec.py": (
        "ae9550c6fba5f7c8a863e0b1ae13609110c0b977915e81dffc579ddb07446b5c"
    ),
}
SITES = {
    "phase": ("betse/science/phase/phasecls.py", "SimPhase", "__init__"),
    "phase_kludge": ("betse/science/phase/phasecls.py", "SimPhase", "_init_kludge"),
    "phase_time": ("betse/science/phase/phasecls.py", "SimPhase", "_init_kludge_time"),
    "simulator": ("betse/science/sim.py", "Simulator", "__init__"),
    "init_core": ("betse/science/sim.py", "Simulator", "init_core"),
    "initDenv": ("betse/science/sim.py", "Simulator", "initDenv"),
    "cache": ("betse/science/math/cache/cacheabc.py", "SimPhaseCaches", "__init__"),
    "cache_abc": ("betse/science/math/cache/cacheabc.py", "SimPhaseCacheABC", "__init__"),
    "cache_vector": (
        "betse/science/math/cache/cachevec.py",
        "SimPhaseCacheVectorCells",
        "__init__",
    ),
    "handler": ("betse/science/tissue/tishandler.py", "TissueHandler", "__init__"),
    "tissues": ("betse/science/tissue/tishandler.py", "TissueHandler", "_init_tissues"),
    "cuts": ("betse/science/tissue/tishandler.py", "TissueHandler", "_init_cuts"),
    "events": ("betse/science/tissue/tishandler.py", "TissueHandler", "_init_events"),
    "global_events": ("betse/science/tissue/tishandler.py", "TissueHandler", "_init_events_global"),
}


def _trees():
    result = {}
    for name, expected in PINS.items():
        path = NATIVE / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Original native source unavailable: " + name)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Changed original native source: " + name)
        result[name] = ast.parse(raw, filename=str(path))
    return result


def _method(tree, owner, name):
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == owner)
    return next(
        node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name
    )


def nodes():
    trees = _trees()
    return {
        key: _method(trees[path], owner, method) for key, (path, owner, method) in SITES.items()
    }


def code(key):
    """Extract a real source CodeType; compiling evaluates no class/module body."""
    if key not in SITES:
        raise ValueError("Unknown selected INIT source method")
    node = copy.deepcopy(nodes()[key])
    path, owner, _ = SITES[key]
    node.decorator_list, node.returns = [], None
    for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
        arg.annotation = None
    # Preserve zero-argument super's real class cell for cache_vector. The
    # consumer must bind it to the authenticated original native base class.
    cls = ast.ClassDef(name=owner, bases=[], keywords=[], body=[node], decorator_list=[])
    compiled = compile(
        ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
        str(NATIVE / path),
        "exec",
        dont_inherit=True,
    )
    class_code = next(
        value for value in compiled.co_consts if type(value) is CodeType and value.co_name == owner
    )
    return next(
        value
        for value in class_code.co_consts
        if type(value) is CodeType and value.co_name == node.name
    )


def source_plan():
    methods = nodes()
    trees = _trees()
    init = _method(trees["betse/science/simrunner.py"], "SimRunner", "init")
    calls = [node for node in ast.walk(init) if isinstance(node, ast.Call)]
    phase = next(
        node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "SimPhase"
    )
    supplied = tuple(keyword.arg for keyword in phase.keywords)
    if supplied != ("kind", "cells", "p", "callbacks") or any(
        key.arg == "sim" for key in phase.keywords
    ):
        raise ValueError("Original INIT retained-Cells/fresh-Simulator caller changed")
    return dict(
        native_sources=dict(PINS),
        sites=dict(SITES),
        methods={
            name: dict(
                lines=(node.lineno, node.end_lineno),
                body_sha256=hashlib.sha256(
                    ast.dump(ast.Module(body=node.body, type_ignores=[])).encode()
                ).hexdigest(),
            )
            for name, node in methods.items()
        },
        original_constructor_arguments=supplied,
        original_constructor_keeps_non_None_cells=True,
        original_constructor_omits_sim_and_creates_fresh_simulator=True,
        constructor_order=(
            "existing Cells argument",
            "fresh Simulator",
            "phase stores",
            "fresh caches",
            "fresh TissueHandler",
            "_init_kludge",
            "_init_kludge_time",
            "export_dirname",
        ),
        subsequent_method="fresh phase.sim.init_core(phase), including conditional initDenv",
        omitted_runner_authorities=(
            "seed pickle existence/automatic seeding",
            "loadWorld",
            "p_old compatibility",
            "SimRunner instance",
            "sim_info_report",
            "run_sim_core",
        ),
        type_check_and_full_package_authority=False,
        actual_source_or_native_execution=False,
    )
