"""cells.modules, the provisional import surface (docs/CORE_SEAMS_DESIGN.md §8.5; D195; seam F).

- It re-exports exactly §8.5's names that exist today (with Citation, the lead's addition, and
  the templates a family builds its own interfaces on, Law and FamilyOperator: §15), each the
  internal object itself, imported from where it lives and never copied (planted: a surface
  holding one copied constant and one wrapped helper, which the same check must catch). A
  registration entry stays module stage 1's, fenced.
- It says "provisional" where contributors read it.
- KindRates lives in the kind contract, and @3's module re-exports the same object.
"""

import importlib
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
        "Citation",
        "CitedWork",
    ),
    "cells.registry.operators": ("FamilyOperator",),
    "cells.registry.kind_registry": (
        "Kind",
        "KindFields",
        "KindView",
        "KindRates",
        "Schedule",
        "EnergyRole",
        "PartitionRole",
        "parse_series",
        "series_to_dict",
        "qualified",
        "declared_schedule",
    ),
    "cells.definitions.specs": ("ConfigError", "require_fields", "finite_number", "bounded_integer"),  # noqa: E501
    "cells.laws.electrochemistry": ("R", "F", "CHARGE_PER_FMOL"),
    "cells.models.surface_pump": ("EXPLICIT_STEP_BOUND",),
    "cells.numerics.extracellular_field": ("scatter",),
    "cells.numerics.species_sums": ("species_sum", "entity_sum"),
    "cells.models.surface_tissue": ("physical_amounts",),
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
