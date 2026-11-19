"""FR-2 DEVELOPMENT SHIM: for development only (the lead's ruling 12, 19 November 2026).

The compartments admission is the operators owner's (FR-2's design statement 1, §7.1). Until it
is on main, this admits membrane_entity_state@1 and scheduled_membrane_trafficking@1 beside
cell_owned_compartments@1, in memory and in the requested form:
- ADMITTED gains both laws;
- CONFLICTS_VIEW no longer holds membrane_area and membrane_capacitance.
It clears the composite's cache on both sides, so no composition built under it outlives it.

It is never in a commit that gates or lands, and it is removed before the first gate.
tests/unit/test_membrane_trafficking.py::test_the_development_shim_is_gone fails while this file
exists.
"""

import contextlib

from cells.models import pump_composite
from cells.operators import compartments, membrane_state, membrane_trafficking

LAWS = (membrane_state.LAW_ID, membrane_trafficking.LAW_ID)
REFERENCE_READS = ("membrane_area", "membrane_capacitance")


@contextlib.contextmanager
def admission():
    """The requested admission, in memory, for the block's duration."""
    admitted, conflicts = compartments.ADMITTED, compartments.CellOwnedCompartments.CONFLICTS_VIEW
    pump_composite._implementation.cache_clear()
    compartments.ADMITTED = (*admitted, *(law for law in LAWS if law not in admitted))
    compartments.CellOwnedCompartments.CONFLICTS_VIEW = tuple(
        k for k in conflicts if k not in REFERENCE_READS
    )
    try:
        yield
    finally:
        compartments.ADMITTED = admitted
        compartments.CellOwnedCompartments.CONFLICTS_VIEW = conflicts
        pump_composite._implementation.cache_clear()
