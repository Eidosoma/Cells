# Synthetic test fixture for the visualizer's run adapter. Not Cells code.
def part_analyse(z):
    from validation.tissue.heredity_pilot import THRESHOLD_V

    return z["vm"] > THRESHOLD_V
