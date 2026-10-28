"""Shared finite ATP, owned calcium/ER and compliant water; synthetic inputs."""

from copy import deepcopy

from validation.tissue import calcium_water_fixtures as water
from validation.tissue import morris_lecar_catalog_fixtures as calcium

MODEL_ID = "resolved_calcium_energy_water@1"
ARMS = (*water.ARMS, "supply_off", "reverse", "absent")


def definition(arm="open", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = calcium.definition(
        "energy", arm if arm in calcium.ARMS else "open", backend=backend, padded=padded
    )
    w = water.definition(arm if arm in water.ARMS else "open", backend=backend, padded=padded)
    m, e = raw["model"], raw["experiment"]
    m.update(
        id=MODEL_ID,
        chemical_osmotic_coupling="ideal_all_cytosol_species_fixed_er@1",
        energy_osmotic_coupling="neutral_ideal_atp_adp_pi@1",
        water_compartments=deepcopy(w["model"]["water_compartments"]),
        water_membranes=deepcopy(w["model"]["water_membranes"]),
    )
    raw["execution"].update(w["execution"])
    raw["execution"]["regeneration_capacity"] = len(m["regeneration_ports"]) + int(padded)
    supply = e["regeneration_controls"]
    e.update(deepcopy(w["experiment"]))
    e["regeneration_controls"] = supply
    # Keep the finite pump controls from the energy definition; all non-fuel
    # controls have the same physical route IDs in the calcium-water fixture.
    if arm == "supply_off":
        for row in supply:
            row["schedule"] = [dict(time=0.0, availability=0.0)]
    if arm == "reverse":
        for pool in m["energy_pools"]:
            pool["delta_g0_J_per_mol"] = 17000.0
    if arm == "absent":
        for patch in m["ionic"]["membranes"]:
            patch["pump"] = None
        for route in m["plasma_transport"]["membranes"]:
            route["pump"] = None
        for store in m["stores"]:
            store["model"]["membrane"]["pump"] = None
        e["pump_controls"] = []
        for row in e["plasma_controls"]:
            for change in row["schedule"]:
                change["pump"] = 0.0
        for row in e["store_controls"]:
            for change in row["controls"]:
                change["pump"] = 0.0
    if arm == "release":
        dt = raw["execution"]["dt"]
        supply[0]["schedule"] = [
            dict(time=0.0, availability=0.8),
            dict(time=25 * dt, availability=0.0),
            dict(time=35 * dt, availability=0.6),
        ]
    return raw


def compact_probe(*, backend="cpu", padded=False):
    return definition("release", backend=backend, padded=padded)


def assembly_definition(*, backend="cpu"):
    raw = calcium.assembly_definition("energy", backend=backend)
    raw["ionic"] = definition(backend=backend)
    raw["window_ticks"] = 8
    for row in raw["pools"]:
        row["pool"].update(end_time_s=raw["ionic"]["experiment"]["end_time"], k_off_s_inv=40000.0)
    return raw
