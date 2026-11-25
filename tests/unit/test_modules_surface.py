"""cells.modules, the provisional import surface (docs/CORE_SEAMS_DESIGN.md §8.5; D195; seam F).

- It re-exports exactly §8.5's names that exist today (with Citation, the lead's addition, and
  the templates a family builds its own interfaces on, Law and FamilyOperator: §15), each the
  internal object itself, imported from where it lives and never copied (planted: a surface
  holding one copied constant and one wrapped helper, which the same check must catch). A
  registration entry stays module stage 1's, fenced.
- It says "provisional" where contributors read it.
- KindRates lives in the kind contract, and @3's module re-exports the same object.
- The guard (§8.5): a module under laws/ imports from Cells only the surface and laws/, one
  under kinds/ also kinds/; the kinds' imports the surface does not carry yet are recorded line
  by line (PENDING), so a new violation fails and so does a recorded one that is gone (planted: a
  registry import, a function's own import, a whole-module import, `from cells import` of a core
  package, and a kind's registry import, each refused, beside admitted surface, laws/, kinds/ and
  relative imports).
- Each name resolves on first use, so importing the surface, or a declaration type from it,
  loads no model, kernel or numerics module: a law module the core imports may import the
  surface without an import cycle (planted: the eager surface's first import, which loads the
  models; the cycle itself is probed in core-pass-f-20261118/probes/cycle.log).
"""

import ast
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import cells.modules as surface
from cells.models import surface_pump_v3
from cells.registry import kind_registry

HOMES = {  # Each name's own module: where it is defined.
    "cells.registry.laws": (
        "Law",
        "ChannelLaw",
        "CycleLaw",
        "RouteLaw",
        "BindingLaw",
        "JunctionLaw",
        "Citation",
        "CitedWork",
        "hosted_laws",
        "cycle_changes",
        "CHANNEL_LAW",
        "CYCLE_LAW",
        "ROUTE_LAW",
        "BINDING_LAW",
        "JUNCTION_LAW",
    ),
    "cells.registry.operators": ("FamilyOperator",),
    "cells.registry.kind_registry": (
        "Kind",
        "KindFields",
        "KindView",
        "KindRates",
        "LabelView",
        "Schedule",
        "EnergyRole",
        "PartitionRole",
        "AxisHost",
        "EntityBinding",
        "MOVES_END",
        "MOVES_ENDS",
        "FreeEnergyEntry",
        "TEMPERATURE_INDEPENDENT",
        "OneWayRecord",
        "parse_series",
        "series_to_dict",
        "qualified",
        "declared_schedule",
    ),
    "cells.definitions.specs": ("ConfigError", "require_fields", "finite_number", "bounded_integer"),  # noqa: E501
    "cells.laws.electrochemistry": ("R", "F", "CHARGE_PER_FMOL"),
    "cells.models.surface_pump": ("EXPLICIT_STEP_BOUND", "floating_nodes"),
    "cells.numerics.extracellular_field": ("scatter",),
    "cells.numerics.species_sums": ("species_sum", "entity_sum"),
    "cells.numerics.one_way_split": ("step_one_way_amounts", "close_one_way"),
    "cells.models.surface_tissue": ("physical_amounts",),
    "cells.models.surface_pump_v3": (
        "HOST_KINDS",
        "HostTable",
        "Host",
        "host_table",
        "host_ends",
        "host_voltage",
        "host_scatter",
        "host_node_conductance",
        "node_concentrations",
        "declared_hosts",
        "host_index",
        "moved_nodes",
        "crossing_junctions",
    ),
    "cells.kinds.proton_buffer": ("free_log_sensitivity",),
}
# What the kinds import today, from @3's module: the same objects as the surface's.
VIA_INNER_MODEL = ("KindRates", "EXPLICIT_STEP_BOUND", "physical_amounts")


def copies(module):
    """The names of `module` that are not their home's object (empty: every one is)."""
    return sorted(
        name
        for home, names in HOMES.items()
        for name in names
        if getattr(module, name, None) is not getattr(importlib.import_module(home), name)
    )


def test_the_surface_re_exports_the_internal_objects_never_copies():
    assert sorted(surface.__all__) == sorted(n for names in HOMES.values() for n in names)
    assert copies(surface) == []
    for name in VIA_INNER_MODEL:
        assert getattr(surface, name) is getattr(surface_pump_v3, name), name
    # The planted surface: one constant copied by value, one helper wrapped.
    planted = SimpleNamespace(**{n: getattr(surface, n) for n in surface.__all__})
    planted.R = float(repr(surface.R))  # A new float of the same value.
    planted.scatter = lambda *args, **kwargs: surface.scatter(*args, **kwargs)
    assert planted.R == surface.R  # Equal values hide a copy; identity does not.
    assert copies(planted) == ["R", "scatter"]
    for missing in ("Module", "Registry", "BUILTIN"):  # Module stage 1's, not yet built.
        assert not hasattr(surface, missing)


def test_the_surface_is_provisional_where_contributors_read_it():
    assert "PROVISIONAL (D195)" in surface.__doc__.splitlines()[0]
    assert "Nothing here is a stability promise yet" in " ".join(surface.__doc__.split())


def test_kind_rates_lives_in_the_kind_contract():
    assert kind_registry.KindRates.__module__ == "cells.registry.kind_registry"
    assert surface_pump_v3.KindRates is kind_registry.KindRates
    assert "KindRates" in kind_registry.__all__
    assert kind_registry.LabelView.__module__ == "cells.registry.kind_registry"  # FR-42's too.
    assert surface_pump_v3.LabelView is kind_registry.LabelView
    assert "LabelView" in kind_registry.__all__


SRC = Path(surface.__file__).resolve().parents[2]
HEAVY = ("cells.models", "cells.laws.", "cells.numerics", "cells.kinds", "cells.operators")


def loaded_after(statement):
    """The cells modules a fresh process holds after running `statement`."""
    script = f"import sys\n{statement}\nprint(__import__('json').dumps(sorted(sys.modules)))"
    env = dict(os.environ, PYTHONPATH=str(SRC), JAX_PLATFORMS="cpu", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=120
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return [m for m in json.loads(result.stdout) if m == "cells" or m.startswith("cells.")]


def heavy(modules):
    return [m for m in modules if m.startswith(HEAVY)]


def test_names_resolve_on_first_use_so_the_surface_loads_no_model():
    assert surface.HOMES.keys() == HOMES.keys()
    assert all(tuple(surface.HOMES[home]) == names for home, names in HOMES.items())
    bare = loaded_after("import cells.modules")
    assert heavy(bare) == [] and "cells.registry.laws" not in bare
    declared = loaded_after("from cells.modules import ChannelLaw, Citation, JunctionLaw")
    assert heavy(declared) == [] and "cells.registry.laws" in declared
    # Planted: the eager surface's first import loads the models, which import the law modules.
    assert heavy(loaded_after("from cells.models.surface_pump import EXPLICIT_STEP_BOUND"))
    assert sorted(dir(surface)) == sorted({*vars(surface), *surface.__all__})


# ------------------------------------------------------------------ the guard (§8.5)


def imports(tree, module):
    """(imported module, name, line) of every cells import in a module's syntax tree, at any depth
    (a function's own import included). A `from M import n` imports n from M; `from cells import
    n` and `import M` import the module itself (name None); a relative import resolves against
    the importing module's package."""
    package = module.rsplit(".", 1)[0]
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names if a.name.split(".")[0] == "cells"]
            out += [(name, None, node.lineno) for name in names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1] + ([base] if base else []))
            if base == "cells":
                out += [(f"cells.{a.name}", None, node.lineno) for a in node.names]
            elif base.split(".")[0] == "cells":
                out += [(base, a.name, node.lineno) for a in node.names]
    return out


def admitted(module, imported):
    """The guard's rule (CORE_SEAMS §8.5; STEP0 §2.2's reading, the lead's ruling of 18
    November): a module under laws/ imports from Cells only the surface and laws/, and one under
    kinds/ also kinds/."""
    allowed = ("cells.modules", "cells.laws")
    if module.startswith("cells.kinds"):
        allowed += ("cells.kinds",)
    return any(imported == a or imported.startswith(a + ".") for a in allowed)


def guard_violations(root):
    """{(path, imported module, name)} of each import the guard refuses under root's cells/laws/
    and cells/kinds/ (root holds the cells package)."""
    out = set()
    for folder in ("laws", "kinds"):
        for path in sorted((root / "cells" / folder).rglob("*.py")):
            parts = path.relative_to(root).with_suffix("").parts
            module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
            if parts[-1] == "__init__":
                module += ".__init__"  # So a relative import resolves inside the package.
            for imported, name, _ in imports(ast.parse(path.read_text()), module):
                if not admitted(module, imported):
                    out.add((path.relative_to(root).as_posix(), imported, name))
    return out


# The kinds' imports the surface does not carry yet, each (file, module, name). The kinds and
# binding owners rewrite them through the surface and delete their own lines here (a recorded
# exception, CORE_SEAMS §18): a new violation fails, and so does a line that no longer is one.
PENDING = frozenset(
    {
        ("cells/kinds/passive_routes.py", "cells.models.surface_pump_v3", "KindRates"),
        ("cells/kinds/passive_routes.py", "cells.models.surface_pump_v3", "moved_nodes"),
        ("cells/kinds/passive_routes.py", "cells.numerics.extracellular_field", "scatter"),
        ("cells/kinds/passive_routes.py", "cells.numerics.species_sums", "entity_sum"),
        ("cells/kinds/passive_routes.py", "cells.numerics.species_sums", "species_sum"),
        ("cells/kinds/passive_routes.py", "cells.registry", "laws"),
        ("cells/kinds/passive_routes.py", "cells.registry.kind_registry", "BUILTIN"),
        ("cells/kinds/passive_routes.py", "cells.registry.kind_registry", "ConfigError"),
        ("cells/kinds/passive_routes.py", "cells.registry.kind_registry", "Kind"),
        ("cells/kinds/passive_routes.py", "cells.registry.kind_registry", "KindFields"),
        ("cells/kinds/passive_routes.py", "cells.registry.kind_registry", "KindView"),
        ("cells/kinds/patch_damage.py", "cells.registry.kind_registry", "BUILTIN"),
        ("cells/kinds/ph_condition.py", "cells.registry.kind_registry", "BUILTIN"),
        ("cells/kinds/ph_condition.py", "cells.registry.kind_registry", "ConfigError"),
        ("cells/kinds/ph_condition.py", "cells.registry.kind_registry", "Kind"),
        ("cells/kinds/ph_condition.py", "cells.registry.kind_registry", "KindView"),
        ("cells/kinds/ph_condition.py", "cells.registry.kind_registry", "finite_number"),
        ("cells/kinds/ph_condition.py", "cells.registry.kind_registry", "qualified"),
        ("cells/kinds/ph_condition.py", "cells.registry.kind_registry", "require_fields"),
        ("cells/kinds/proton_buffer.py", "cells.models", "surface_pump_v3"),
        ("cells/kinds/proton_buffer.py", "cells.registry", "species_registry"),
        ("cells/kinds/proton_buffer.py", "cells.registry.kind_registry", "BUILTIN"),
        ("cells/kinds/proton_buffer.py", "cells.registry.kind_registry", "ConfigError"),
        ("cells/kinds/proton_buffer.py", "cells.registry.kind_registry", "Kind"),
        ("cells/kinds/proton_buffer.py", "cells.registry.kind_registry", "KindView"),
        ("cells/kinds/transporter.py", "cells.models.surface_pump_v3", "patch_node_conductance"),
        ("cells/kinds/transporter.py", "cells.registry", "species_registry"),
        ("cells/kinds/transporter.py", "cells.registry.kind_registry", "BUILTIN"),
    }
)


def test_built_ins_import_cells_only_through_the_surface(tmp_path):
    assert guard_violations(SRC) == PENDING  # laws/ holds none; kinds/ holds its recorded lines.
    assert not any(path.startswith("cells/laws/") for path, _, _ in PENDING)
    # Planted: a tree of one law and one kind module of each sort.
    root = tmp_path / "planted"
    for folder in ("laws/channels", "kinds"):
        (root / "cells" / folder).mkdir(parents=True)
    cases = {
        "laws/channels/registers.py": "from cells.registry import laws\n",
        "laws/channels/lazy.py": (
            "def f():\n    from cells.models.surface_pump_v3 import KindRates\n"
        ),
        "laws/channels/whole.py": "import cells.numerics.species_sums\n",
        "laws/channels/attribute.py": "from cells import registry\n",
        "laws/channels/clean.py": (
            "from cells.modules import ChannelLaw\nfrom cells.laws.electrochemistry import R\n"
            "from . import clean\nfrom cells import modules\nimport cells.laws.channels\n"
        ),
        "kinds/clean.py": "from cells.kinds import clean\nfrom cells.laws.routes import x\n",
        "kinds/core.py": "from cells.registry.kind_registry import BUILTIN\n",
    }
    for name, text in cases.items():
        (root / "cells" / name).write_text(text)
    assert guard_violations(root) == {
        ("cells/laws/channels/registers.py", "cells.registry", "laws"),
        ("cells/laws/channels/lazy.py", "cells.models.surface_pump_v3", "KindRates"),
        ("cells/laws/channels/whole.py", "cells.numerics.species_sums", None),
        ("cells/laws/channels/attribute.py", "cells.registry", None),
        ("cells/kinds/core.py", "cells.registry.kind_registry", "BUILTIN"),
    }
