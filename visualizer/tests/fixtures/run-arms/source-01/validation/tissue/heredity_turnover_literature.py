# Synthetic test fixture for the visualizer's run adapter. Not Cells code.
from validation.tissue import heredity_pilot as pilot

THRESHOLD_V = pilot.THRESHOLD_V
RECORD_S = 10.0


def analyse(vm):
    return vm > THRESHOLD_V
