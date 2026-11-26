"""The CaV1.2-type gate law's names, in volts and seconds, for the calcium catalogue.

The law's own module is laws/channels/cav1p2_m2h.py (docs/CORE_SEAMS_DESIGN.md §8.2), which
declares it; this one re-imports its names for laws/channels/cav_channels.py. Continuous relaxation:
the gates are integrated by their host's solver.
"""

from cells.laws.channels.cav1p2_m2h import (  # noqa: F401
    LAW_ID,
    VOLTAGE_DOMAIN_V,
    kinetics,
)
from cells.laws.channels.cav1p2_m2h import opening as open_probability  # noqa: F401
