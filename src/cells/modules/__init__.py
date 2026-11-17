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
- the declaration types of each interface: the law template's ChannelLaw, CycleLaw, RouteLaw and
  BindingLaw, with Citation, the source a cited law gives (registry/laws.py); and the kind
  contract's Kind, KindFields, KindView, KindRates and Schedule (core/kind_registry.py);
- the parsing helpers: ConfigError, require_fields, finite_number and bounded_integer
  (core/specs.py), and parse_series, series_to_dict, qualified and declared_schedule
  (core/kind_registry.py);
- the constants: R, F and CHARGE_PER_FMOL (processes/electrochemistry.py), and
  EXPLICIT_STEP_BOUND (models/surface_pump.py);
- the array helpers kinds use: scatter (numerics/extracellular_field.py), species_sum and
  entity_sum (numerics/species_sums.py), and physical_amounts (models/surface_tissue.py).

**Not here yet**, with the work that brings them:
- the host table's end readers, with the host table (§2);
- Module, Registry and BUILTIN, in module stage 1 (MODULE_SYSTEM_DESIGN §2.3).

Built-ins do not yet import only this surface. The AST guard that makes them do so is a later
step.
"""

from cells.core.kind_registry import (
    Kind,
    KindFields,
    KindRates,
    KindView,
    Schedule,
    declared_schedule,
    parse_series,
    qualified,
    series_to_dict,
)
from cells.core.specs import ConfigError, bounded_integer, finite_number, require_fields
from cells.models.surface_pump import EXPLICIT_STEP_BOUND
from cells.models.surface_tissue import physical_amounts
from cells.numerics.extracellular_field import scatter
from cells.numerics.species_sums import entity_sum, species_sum
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.registry.laws import BindingLaw, ChannelLaw, Citation, CycleLaw, RouteLaw

__all__ = (
    # The declaration types of each interface.
    "ChannelLaw",
    "CycleLaw",
    "RouteLaw",
    "BindingLaw",
    "Citation",
    "Kind",
    "KindFields",
    "KindView",
    "KindRates",
    "Schedule",
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
