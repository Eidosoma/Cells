"""Positive-domain 3 Na out / 2 K in ATPase with maintained metabolic pools.

SPEC-010 / D111: a named process, not a selectable simulation family yet.
Species roles, geometry, inventories, masks and ledgers belong to the composing
model. Supply neutral inactive padding BEFORE this law and reject invalid trials
using domain_valid. There is no concentration floor, clipping or state repair.
See docs/KINETIC_PUMP_PROCESS.md for units, evidence and remaining integration.

The law's own module is laws/pumps/nak_atp_mass_action_positive.py (docs/CORE_SEAMS_DESIGN.md
§8.2), which declares it; this module re-imports its names for their importers.
"""

from cells.laws.pumps.nak_atp_mass_action_positive import (  # noqa: F401
    LAW_ID,
    MAX_ABS_AFFINITY_OVER_RT,
    MAX_ABS_ION_POTENTIAL_OVER_RT,
    POTASSIUM_PER_CYCLE,
    SODIUM_PER_CYCLE,
    TEMPERATURE_DOMAIN_K,
    Parameters,
    Rates,
    STANDARD_STATE_mM,
    chemical_drive,
    domain_valid,
    kinetics,
)
