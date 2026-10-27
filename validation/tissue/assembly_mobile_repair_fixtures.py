"""One-way assembly control of fixed and mobile conductance on owned calcium tissue."""

from validation.tissue import surface_mobile_repair_fixtures as mobile
from validation.tissue import surface_repair_fixtures as prior

ARMS = ("mobile", "release", "uncoupled")
STEPS = (0.625e-6, 0.3125e-6, 0.15625e-6)


def definition(arm="mobile", *, backend="cpu", dt=STEPS[0], padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.assembly_definition(backend=backend)
    raw["ionic"] = mobile.definition(
        "mobile" if arm == "uncoupled" else arm, backend=backend, padded=padded
    )
    raw["ionic"]["execution"]["dt"] = dt
    # Complete coupled snapshots stay on accepted nominal ticks. Every external
    # change and every cell's stochastic event still splits the internal RK4 step.
    raw["ionic"]["experiment"]["observation_times"] = [
        i * STEPS[0] for i in (0, 8, 9, 16, 24, 25, 30, 31, 40, 46, 47, 64, 80)
    ]
    if arm == "uncoupled":
        for binding in raw["pools"]:
            binding["coupling"].update(inactive_availability=1.0, active_availability=1.0)
    return raw


def normalized(raw):
    from copy import deepcopy

    result = deepcopy(raw)
    result["ionic"]["execution"]["backend"] = "cpu"
    return result
