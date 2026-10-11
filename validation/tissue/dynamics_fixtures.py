"""Synthetic kinetic tissue, with every outside capacitor countercharge explicit."""

import math

from validation.betse.spatial_cluster.fixtures import IDS, F
from validation.betse.spatial_cluster.fixtures import definition as local_definition


def definition(*, end=0.002, dt=0.0001, backend="cpu", arm="baseline", padded=True):
    if arm not in ("baseline", "blocked", "release", "same_region"):
        raise ValueError("Unknown tissue trajectory arm")
    raw = local_definition(end=end, dt=dt, backend=backend, padded=padded)
    m = raw["model"]
    m["id"] = "spatial_extracellular@3"
    m["closure"]["law"] = "capacitive_regions_ghk_return_current@1"
    raw["execution"]["field_solver"] = "gauged_damped_newton@1"
    if arm != "same_region":
        m["cells"][1]["membrane"]["outside"] = "near"
    # This is fixture construction, not simulator repair: fixed backgrounds are
    # declared once in the reproducible input and are never changed during a run.
    for outside in (m["extracellular"], *m["surroundings"]):
        cap_charge = math.fsum(
            c["membrane"]["area_m2"]
            * c["membrane"]["specific_capacitance_F_per_m2"]
            * c["cell"]["initial_voltage_V"]
            for c in m["cells"]
            if c["membrane"]["outside"] == outside["id"]
        )
        outside["fixed_charge_equivalent_fmol"] = -cap_charge / (F * 1e-15) - math.fsum(
            z * outside["initial_amount_fmol"][s] for z, s in zip((1, 1, -1), IDS, strict=True)
        )
    # A resistive outside path makes cross-region return currents observable.
    for face in m["faces"]:
        face["area_m2"] *= 1e-4
    schedule = raw["experiment"]["junction_controls"][0]["schedule"]
    if arm in ("blocked", "release"):
        schedule[0]["open_fraction"] = 0.0
    if arm == "release":
        schedule.append({"time": 0.001, "open_fraction": 1.0})
    raw["experiment"]["observation_times"] = sorted(
        {0.0, end, *(v for v in (0.0005, 0.001, 0.0015) if v < end)}
    )
    return raw
