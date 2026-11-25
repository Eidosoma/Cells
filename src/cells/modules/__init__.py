"""cells.modules: the import surface for laws, kinds and modules. PROVISIONAL (D195).

**Provisional.** Nothing here is a stability promise yet. Names may change, move or go until a
first outside module arrives; then the promise goes back to the user (D195, item 3). Until then,
build against it knowing it may change.

**What it is** (docs/CORE_SEAMS_DESIGN.md §8.5; docs/MODULE_SYSTEM_DESIGN.md §2.6): one package
whose path does not move, re-exporting what a law, kind or module needs from Cells' internals.
- Every name is the internal object itself, taken from where it lives (HOMES), never copied.
- Each name resolves on first use (PEP 562's module `__getattr__`), so importing the surface
  imports nothing else. A law module that the core itself imports, such as a kernel module's
  per-law home, may then import the surface without an import cycle: `from cells.modules import
  ChannelLaw` loads only the law template's module.
- Internals may move freely; the surface follows them. Internals never import the surface.

**What it exports:**
- the declaration types of each interface: the law template's base, Law, on which a family's own
  law interfaces are built, and its ChannelLaw, CycleLaw, RouteLaw, BindingLaw and JunctionLaw,
  with Citation, the source a cited law gives, and CitedWork, a work it names (registry/laws.py);
  the operator template of a family's own operators, FamilyOperator (registry/operators.py); and
  the kind contract's Kind, KindFields, KindView, KindRates, LabelView and Schedule, with the
  roles its fields declare, EnergyRole and PartitionRole, the host of an own axis, AxisHost, and an
  entity's binding for §5.2's admission, EntityBinding, with MOVES_END and MOVES_ENDS, a
  moves-only law's inside and its two ends, and a reaction-level standard free energy,
  FreeEnergyEntry, with TEMPERATURE_INDEPENDENT, the basis of a dG° given in kJ/mol
  (registry/kind_registry.py);
- the law readers a kind uses: hosted_laws(interface, host), and cycle_changes(law), a cycle law's
  declared change rows, with the interfaces' IDs CHANNEL_LAW, CYCLE_LAW, ROUTE_LAW, BINDING_LAW and
  JUNCTION_LAW (registry/laws.py);
- the host table's readers (models/surface_pump_v3.py, the @3 owner's): HOST_KINDS, HostTable,
  Host, host_table, host_ends, host_voltage, host_scatter, host_node_conductance,
  node_concentrations, declared_hosts and host_index, with moved_nodes (each row's in-step movers)
  and crossing_junctions (the junctions that cross a floating capacitor component, fix (A)'s);
- floating_nodes (models/surface_pump.py), the outside nodes that no held bath, gauge or face
  holds, for a kind's definition-time charge bound (the charge rule's rows);
- the parsing helpers: ConfigError, require_fields, finite_number and bounded_integer
  (definitions/specs.py), and parse_series, series_to_dict, qualified and declared_schedule
  (registry/kind_registry.py);
- the constants: R, F and CHARGE_PER_FMOL (laws/electrochemistry.py), and
  EXPLICIT_STEP_BOUND (models/surface_pump.py);
- the array helpers kinds use: scatter (numerics/extracellular_field.py), species_sum and
  entity_sum (numerics/species_sums.py), and physical_amounts (models/surface_tissue.py);
- the one-way step rule FR-42's labels and FR-50's records share: step_one_way_amounts and
  close_one_way (numerics/one_way_split.py), with OneWayRecord, a kind's record pair
  (registry/kind_registry.py).
- the general closure's free_log_sensitivity, d ln c_free / d n_total at a stage, for a kind's
  material term (kinds/proton_buffer.py, the binding owner's).

**Not here yet**, with the work that brings them:
- Module, Registry and BUILTIN, and with them a registration entry, in module stage 1
  (MODULE_SYSTEM_DESIGN §2.3). Until then a built-in family's homes register through the
  registries' own call and are named in the static model table (registry/model_table.py).

**The guard** (tests/unit/test_modules_surface.py; §8.5): a built-in under laws/ imports from Cells
only this surface and laws/, and one under kinds/ also kinds/. The kinds' imports the surface does
not carry yet are recorded there line by line, until their owners rewrite them through the surface,
which gains the names they need as they ask (the lead's ruling, CORE_SEAMS §18).
"""

import importlib
from types import MappingProxyType

# Each exported name's home: the module that defines it.
HOMES = MappingProxyType(
    {
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
        "cells.definitions.specs": (
            "ConfigError",
            "require_fields",
            "finite_number",
            "bounded_integer",
        ),
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
)
_HOME = {name: home for home, names in HOMES.items() for name in names}

__all__ = (
    # The declaration types of each interface.
    "Law",
    "ChannelLaw",
    "CycleLaw",
    "RouteLaw",
    "BindingLaw",
    "JunctionLaw",
    "Citation",
    "CitedWork",
    "FamilyOperator",
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
    "OneWayRecord",  # FR-50: a kind's one-way record pair.
    # The law readers a kind uses.
    "hosted_laws",
    "cycle_changes",
    "CHANNEL_LAW",
    "CYCLE_LAW",
    "ROUTE_LAW",
    "BINDING_LAW",
    "JUNCTION_LAW",
    "ConfigError",
    "require_fields",
    "finite_number",
    "bounded_integer",
    "parse_series",
    "series_to_dict",
    "qualified",
    "declared_schedule",
    # The constants.
    "R",
    "F",
    "CHARGE_PER_FMOL",
    "EXPLICIT_STEP_BOUND",
    # The array helpers kinds use.
    "scatter",
    "species_sum",
    "entity_sum",
    "physical_amounts",
    "step_one_way_amounts",  # FR-42's and FR-50's step rule (numerics/one_way_split.py).
    "close_one_way",
    # The host table's readers.
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
    "floating_nodes",  # The outside nodes that nothing holds, for a kind's charge bound.
    "free_log_sensitivity",  # The general closure's derivative, for a kind's material term.
)


def __getattr__(name):
    """A surface name, from its home on first use (module docstring); kept here after that."""
    home = _HOME.get(name)
    if home is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(home), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *__all__})
