"""Operators of the composite pump-tissue model, the operator section's built-in package.

Each operator implements the contract of models/operators/contract.py for one law
(docs/CELL_DIVISION_DESIGN.md §3.3). New combinations are definitions
(core/pump_composite_spec.py), not model families (D142, D143). The package registers its
operators on the operator section's BUILTIN (registry/operators.py; docs/CORE_SEAMS_DESIGN.md
§8.4) through the call an outside package uses, which runs check_declarations. OPERATORS is the
active section as a mapping.
"""

from cells.models.operators.bath_schedule import ScheduledBathComposition
from cells.models.operators.bridge_closure import CytoplasmicBridgeClosure
from cells.models.operators.cell_replacement import ScheduledReplacement
from cells.models.operators.cell_replacement_v2 import ScheduledReplacementOverWater
from cells.models.operators.compartments import CellOwnedCompartments
from cells.models.operators.current_injection import ElectrodeCurrentInjection
from cells.models.operators.k_anion_symport import KAnionSymport
from cells.models.operators.membrane_insertion import ScheduledMembraneInsertion
from cells.models.operators.membrane_insertion_v2 import ScheduledMembraneInsertionV2
from cells.models.operators.membrane_state import MembraneEntityState
from cells.models.operators.osmotic_water import OsmoticWater
from cells.models.operators.partition import IsopotentialPartition
from cells.models.operators.restricted_lumen import RestrictedCleftLumen
from cells.models.operators.restricted_lumen_v2 import RestrictedCleftLumenV2
from cells.models.operators.site_occupancy import SiteOccupancy
from cells.models.operators.species_exchange import ScheduledSpeciesExchange
from cells.models.operators.species_reactions import LocalSpeciesReactions
from cells.models.operators.species_regulated_availability import SpeciesRegulatedAvailability
from cells.models.operators.species_turnover import ScheduledSpeciesTurnover
from cells.registry.operators import BUILTIN, OPERATORS  # noqa: F401  (the active section)

for _operator in (  # Today's order: the section's registration order.
    OsmoticWater,
    KAnionSymport,
    ScheduledReplacement,
    ScheduledReplacementOverWater,
    ElectrodeCurrentInjection,
    MembraneEntityState,
    ScheduledMembraneInsertion,
    RestrictedCleftLumen,
    IsopotentialPartition,
    CytoplasmicBridgeClosure,
    ScheduledMembraneInsertionV2,
    RestrictedCleftLumenV2,
    ScheduledSpeciesTurnover,
    ScheduledSpeciesExchange,
    LocalSpeciesReactions,
    SpeciesRegulatedAvailability,
    ScheduledBathComposition,
    CellOwnedCompartments,
    SiteOccupancy,
):
    BUILTIN.register(_operator)
del _operator
