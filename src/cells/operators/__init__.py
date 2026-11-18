"""Operators of the composite pump-tissue model, the operator section's built-in package.

Each operator implements the contract of operators/contract.py for one law
(docs/CELL_DIVISION_DESIGN.md §3.3). New combinations are definitions
(definitions/pump_composite_spec.py), not model families (D142, D143). The package registers its
operators on the operator section's BUILTIN (registry/operators.py; docs/CORE_SEAMS_DESIGN.md
§8.4) through the call an outside package uses, which runs check_declarations. OPERATORS is the
active section as a mapping.
"""

from cells.operators.bath_schedule import ScheduledBathComposition
from cells.operators.bridge_closure import CytoplasmicBridgeClosure
from cells.operators.cell_replacement import ScheduledReplacement
from cells.operators.cell_replacement_v2 import ScheduledReplacementOverWater
from cells.operators.compartments import CellOwnedCompartments
from cells.operators.current_injection import ElectrodeCurrentInjection
from cells.operators.k_anion_symport import KAnionSymport
from cells.operators.membrane_insertion import ScheduledMembraneInsertion
from cells.operators.membrane_insertion_v2 import ScheduledMembraneInsertionV2
from cells.operators.membrane_state import MembraneEntityState
from cells.operators.osmotic_water import OsmoticWater
from cells.operators.partition import IsopotentialPartition
from cells.operators.restricted_lumen import RestrictedCleftLumen
from cells.operators.restricted_lumen_v2 import RestrictedCleftLumenV2
from cells.operators.site_occupancy import SiteOccupancy
from cells.operators.species_exchange import ScheduledSpeciesExchange
from cells.operators.species_reactions import LocalSpeciesReactions
from cells.operators.species_regulated_availability import SpeciesRegulatedAvailability
from cells.operators.species_turnover import ScheduledSpeciesTurnover
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
