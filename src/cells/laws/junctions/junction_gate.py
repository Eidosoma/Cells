"""Continuous physical-time junction conductance from the BETSE v1.5.0 rate equations.

The rate equations are cited from BETSE v1.5.0 (no BETSE code is used).

The finite_extracellular@3 composition evaluates the rates at common solver
stages. State g is relative intrinsic conductance in [minimum, 1]. Availability
multiplies conductance without
changing g. Native per-ion updates, stored-state blocking and class initialization
belong to the separate validation compatibility adapter, not this physical law.
No temperature scaling, connexin catalog or biological fit is implied.

The law's own module is laws/junctions/junction_voltage_relaxation.py (docs/CORE_SEAMS_DESIGN.md
§8.2), which declares it; this module re-imports its names for their importers.
"""

from cells.laws.junctions.junction_voltage_relaxation import (  # noqa: F401
    LAW_ID,
    MAX_ABS_VOLTAGE_V,
    RELAXATION_LAW_ID,
    Parameters,
    Rates,
    advance_clamped,
    domain_valid,
    kinetics,
    open_fraction,
    rhs,
)
