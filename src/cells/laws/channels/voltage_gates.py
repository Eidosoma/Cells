"""Pure continuous m/h kinetics in volts/seconds; no implicit preparation.

SPEC-006 specifies the BETSE-v1.5.0 Kv1p5-derived engineering law. This is not
an external-reference execution or a temperature-calibrated channel catalog.

The law's own module is laws/channels/kv1p5_mh.py (docs/CORE_SEAMS_DESIGN.md §8.2), which
declares it; this module re-imports its names for their importers.
"""

from cells.laws.channels.kv1p5_mh import (  # noqa: F401
    LAW_ID,
    TEMPERATURE_K,
    VOLTAGE_DOMAIN_V,
    kinetics,
)
