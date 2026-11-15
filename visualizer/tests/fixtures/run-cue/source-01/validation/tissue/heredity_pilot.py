# Synthetic test fixture for the visualizer's run adapter. Not Cells code.
"""Synthetic wording: the cells lie on a jittered hexagonal
lattice."""

from validation.tissue import surface_pump_v3_fixtures as fixtures

THRESHOLD_V = fixtures.HEREDITY_STATES["U"][0]


def count(vm):
    return vm > THRESHOLD_V
