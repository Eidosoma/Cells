"""Operators of the composite pump-tissue model: an explicit registry, no plugins.

Each operator implements the contract of models/operators/contract.py for one law
(docs/CELL_DIVISION_DESIGN.md §3.3). New combinations are definitions
(core/pump_composite_spec.py), not model families (D142, D143).
"""

from cells.models.operators.bridge_closure import CytoplasmicBridgeClosure
from cells.models.operators.cell_replacement import ScheduledReplacement
from cells.models.operators.cell_replacement_v2 import ScheduledReplacementOverWater
from cells.models.operators.contract import check_declarations
from cells.models.operators.current_injection import ElectrodeCurrentInjection
from cells.models.operators.k_anion_symport import KAnionSymport
from cells.models.operators.membrane_insertion import ScheduledMembraneInsertion
from cells.models.operators.membrane_insertion_v2 import ScheduledMembraneInsertionV2
from cells.models.operators.membrane_state import MembraneEntityState
from cells.models.operators.osmotic_water import OsmoticWater
from cells.models.operators.partition import IsopotentialPartition
from cells.models.operators.restricted_lumen import RestrictedCleftLumen
from cells.models.operators.restricted_lumen_v2 import RestrictedCleftLumenV2
from cells.models.operators.species_exchange import ScheduledSpeciesExchange
from cells.models.operators.species_reactions import LocalSpeciesReactions
from cells.models.operators.species_turnover import ScheduledSpeciesTurnover

OPERATORS = {
    op.LAW_ID: op
    for op in (
        check_declarations(OsmoticWater)(),
        check_declarations(KAnionSymport)(),
        check_declarations(ScheduledReplacement)(),
        check_declarations(ScheduledReplacementOverWater)(),
        check_declarations(ElectrodeCurrentInjection)(),
        check_declarations(MembraneEntityState)(),
        check_declarations(ScheduledMembraneInsertion)(),
        check_declarations(RestrictedCleftLumen)(),
        check_declarations(IsopotentialPartition)(),
        check_declarations(CytoplasmicBridgeClosure)(),
        check_declarations(ScheduledMembraneInsertionV2)(),
        check_declarations(RestrictedCleftLumenV2)(),
        check_declarations(ScheduledSpeciesTurnover)(),
        check_declarations(ScheduledSpeciesExchange)(),
        check_declarations(LocalSpeciesReactions)(),
    )
}
