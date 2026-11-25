"""The CaV1.2-type gate law's names, in volts and seconds, for their older importers.

The law's own module is laws/channels/cav1p2_m2h.py (docs/CORE_SEAMS_DESIGN.md §8.2), which
declares it; this one re-imports its names for the calcium catalogue (laws/channels/
cav_channels.py) and the older families. Continuous relaxation: the gates are integrated by their
host's solver. TEMPERATURE_K, the temperature those families declare, and MIN_TAU_S, tau_m's least
value, which bounds their steps, are the older families' own.
"""

from cells.laws.channels.cav1p2_m2h import (  # noqa: F401
    LAW_ID,
    VOLTAGE_DOMAIN_V,
    kinetics,
)
from cells.laws.channels.cav1p2_m2h import opening as open_probability  # noqa: F401

TEMPERATURE_K = 298.15
MIN_TAU_S = 0.005
