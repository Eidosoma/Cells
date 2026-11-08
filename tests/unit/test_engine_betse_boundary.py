"""BETSE stays an external reference: guard the engine/frozen-tooling boundary.

See AGENTS.md ("BETSE's role"). The frozen `betse_native_*` and `betse_normal_*`
modules re-host or transcribe BETSE; engine code must not come to depend on them,
live modules must not import the BETSE package, and the frozen set must not grow.
"""

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
FROZEN = re.compile(r"^cells\.processes\.betse_(native|normal)_")
ENGINE_PREFIXES = (
    "cells.models.",
    "cells.core.",
    "cells.numerics.",
    "cells.ensemble.",
    "cells.assembly",
)
# Known helper-only coupling (record/_digest/_array via the mesh-preparation path),
# present at checkpoint 7e9873a. Remove entries as the helpers are decoupled.
HELPER_ONLY = {
    "cells.core.active_ecm_polygon_preparation",
    "cells.core.active_polygon_physiology_preparation",
    "cells.core.conservative_polygon_tissue_preparation",
    "cells.core.finite_ecm_polygon_preparation",
}
HELPER_TARGETS = {"cells.processes.betse_normal_current"}
FROZEN_FILES_AT_CHECKPOINT = 207


def _modules():
    modules = {}
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).with_suffix("")
        parts = rel.parts[:-1] if rel.name == "__init__" else rel.parts
        modules[".".join(parts)] = path
    return modules


def _imports(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                parts = parts[: len(parts) - (node.level - 1)]
                base = ".".join([*parts, base] if base else parts)
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
        elif (
            isinstance(node, ast.Call)
            and getattr(node.func, "attr", getattr(node.func, "id", "")) == "import_module"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.add(node.args[0].value)
    return found


def _graph():
    modules = _modules()
    raw = {name: _imports(path, name) for name, path in modules.items()}
    return modules, raw


def _closure(graph, start):
    seen, stack = set(), [start]
    while stack:
        for target in graph.get(stack.pop(), ()):
            if target not in seen:
                seen.add(target)
                stack.append(target)
    return seen


def test_engine_modules_do_not_reach_frozen_betse_tooling():
    modules, raw = _graph()
    graph = {name: {m for m in found if m in modules} for name, found in raw.items()}
    frozen = {name for name in modules if FROZEN.match(name)}
    violations = {}
    for name in modules:
        if not name.startswith(ENGINE_PREFIXES):
            continue
        reached = _closure(graph, name) & frozen
        if not reached:
            continue
        if name in HELPER_ONLY and reached <= HELPER_TARGETS:
            continue
        violations[name] = sorted(reached)
    assert not violations, violations


def _loads_betse(path):
    """Imports, module-path strings ("betse.science.sim") or the BETSE source tree."""
    text = path.read_text(encoding="utf-8")
    if "betse-v1.5.0" in text:
        return True
    for node in ast.walk(ast.parse(text)):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            names = [node.module or ""]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names = [node.value]
        if any(re.match(r"^betse(\.[A-Za-z_]\w*)*$", item) for item in names):
            return True
    return False


def test_live_modules_do_not_load_betse():
    loaders = sorted(
        name for name, path in _modules().items() if not FROZEN.match(name) and _loads_betse(path)
    )
    assert not loaders, loaders


def test_frozen_betse_tooling_does_not_grow():
    frozen = [name for name in _modules() if FROZEN.match(name)]
    assert len(frozen) <= FROZEN_FILES_AT_CHECKPOINT, len(frozen)
