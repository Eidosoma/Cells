"""cells.modules: the import surface for laws, kinds and modules. PROVISIONAL (D195).

**Provisional.** Nothing here is a stability promise yet. Names may change, move or go until a
first outside module arrives; then the promise goes back to the user (D195, item 3). Until then,
build against it knowing it may change.

**What it is** (docs/CORE_SEAMS_DESIGN.md §8.5; docs/MODULE_SYSTEM_DESIGN.md §2.6): one package
whose path does not move, re-exporting what a law, kind or module needs from Cells' internals.
- Every name is imported from where it lives, never copied, so each is the internal object
  itself.
- Internals may move freely; the surface follows them.
- Internals never import the surface, so it adds no import cycle.

**What it exports:**
- the declaration types of each interface: the law template's base, Law, on which a family's own
  law interfaces are built, and its ChannelLaw, CycleLaw, RouteLaw and BindingLaw, with Citation,
  the source a cited law gives, and CitedWork, a work it names (registry/laws.py); the operator
  template of a family's own operators, FamilyOperator (registry/operators.py); and the kind
  contract's Kind, KindFields, KindView, KindRates and Schedule, with the roles its fields declare,
  EnergyRole and PartitionRole (registry/kind_registry.py);
- the parsing helpers: ConfigError, require_fields, finite_number and bounded_integer
  (definitions/specs.py), and parse_series, series_to_dict, qualified and declared_schedule
  (registry/kind_registry.py);
- the constants: R, F and CHARGE_PER_FMOL (laws/electrochemistry.py), and
  EXPLICIT_STEP_BOUND (models/surface_pump.py);
- the array helpers kinds use: scatter (numerics/extracellular_field.py), species_sum and
  entity_sum (numerics/species_sums.py), and physical_amounts (models/surface_tissue.py).

**Not here yet**, with the work that brings them:
- the host table's end readers, with the host table (§2);
- Module, Registry and BUILTIN, and with them a registration entry, in module stage 1
  (MODULE_SYSTEM_DESIGN §2.3). Until then a built-in family's homes register through the
  registries' own call and are named in the static model table (registry/model_table.py).

Built-ins do not yet import only this surface. The AST guard that makes them do so is a later
step.
"""

from cells.definitions.specs import ConfigError, bounded_integer, finite_number, require_fields
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.models.surface_pump import EXPLICIT_STEP_BOUND
from cells.models.surface_tissue import physical_amounts
from cells.numerics.extracellular_field import scatter
from cells.numerics.species_sums import entity_sum, species_sum
from cells.registry.kind_registry import (
    EnergyRole,
    Kind,
    KindFields,
    KindRates,
    KindView,
    PartitionRole,
    Schedule,
    declared_schedule,
    parse_series,
    qualified,
    series_to_dict,
)
from cells.registry.laws import (
    BindingLaw,
    ChannelLaw,
    Citation,
    CitedWork,
    CycleLaw,
    Law,
    RouteLaw,
)
from cells.registry.operators import FamilyOperator

__all__ = (
    # The declaration types of each interface.
    "Law",
    "ChannelLaw",
    "CycleLaw",
    "RouteLaw",
    "BindingLaw",
    "Citation",
    "CitedWork",
    "FamilyOperator",
    "Kind",
    "KindFields",
    "KindView",
    "KindRates",
    "Schedule",
    "EnergyRole",
    "PartitionRole",
    # The parsing helpers.
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
)
