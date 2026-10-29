"""Complete-owner, two-step inputs for public interfaces, not physical calibration.

The scientific fixtures keep their own horizons. These inputs retain every
channel law and material owner while placing control changes on a tiny clock
to check routing, persisted state and restart through the public interfaces.
"""

import importlib
from copy import deepcopy

from validation.tissue import calcium_energy_water_fixtures as water
from validation.tissue import calcium_energy_water_repair_fixtures as repair
from validation.tissue import hcn_extra_catalog_fixtures as hcn
from validation.topology.owned_calcium_profile_interventions_fixtures import _scaled

FAMILIES = ("water", "repair")
FIELDS = {"water": 43, "repair": 48}
DT = 1e-9


def stem(family):
    if family not in FAMILIES:
        raise ValueError(family)
    return "surface_calcium_energy_water" + ("_repair" if family == "repair" else "")


def components(family, *, version=2):
    name = stem(family) + ("_hcn_extra" if version == 2 else "")
    return (
        importlib.import_module("cells.core." + name + "_spec"),
        importlib.import_module("cells.models." + name),
    )


def definition(family, *, backend="cpu", jit=False, version=2):
    if version not in (1, 2):
        raise ValueError(version)
    raw = (
        repair.definition("preinjured", backend=backend, padded=True)
        if family == "repair"
        else water.definition(backend=backend, padded=True)
    )
    raw["model"]["id"] = stem(family).replace("surface_", "resolved_") + f"@{version}"
    ionic = raw["model"]["ionic"]
    if version == 2:
        ionic["id"] = "resolved_tissue@12"
        extension = hcn.definition("energy", padded=False)
        controls = {row["channel_id"]: row for row in extension["experiment"]["channel_controls"]}
        for channel in extension["model"]["ionic"]["channels"]:
            if channel["kinetic_law"] in {law for law, _, _ in hcn.ADDED_LAWS}:
                ionic["channels"].append(deepcopy(channel))
                raw["experiment"]["channel_controls"].append(deepcopy(controls[channel["id"]]))
    raw["execution"].update(jit=jit, dt=DT, channel_capacity=len(ionic["channels"]) + 1)
    experiment = raw["experiment"]
    experiment.update(end_time=2 * DT, observation_times=[0.0, DT, 2 * DT])
    for name, rows in experiment.items():
        if name.endswith("_controls"):
            for row in rows:
                key = "controls" if "controls" in row else "schedule"
                first = deepcopy(row[key][0])
                first["time"] = 0.0
                second = _scaled(first, 0.7)
                second["time"] = DT
                if name == "injury_controls":
                    first.update(injury=0.8, resealing=0.4)
                    second.update(injury=0.2, resealing=0.7)
                row[key] = [first, second]
    return raw


def assembly_definition(family):
    raw = (
        repair.assembly_definition("preinjured")
        if family == "repair"
        else water.assembly_definition()
    )
    raw["ionic"] = definition(family, jit=True)
    raw["window_ticks"] = 2
    for row in raw["pools"]:
        row["pool"].update(end_time_s=2 * DT, worlds=1)
    return raw
