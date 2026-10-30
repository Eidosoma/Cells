"""Data-only synthetic None-energy routes on the qualified owned56 fuel recipe."""

from copy import deepcopy

from validation.tissue import calcium_energy_network_transport_fixtures as original

MODEL_ID = "resolved_calcium_energy_irreversible_transport@1"
ACCOUNTING = "irreversible_species_transport_explicit_physical_work@1"
ARMS = (
    "active",
    "blocked",
    "empty",
    "reordered",
    "downhill",
    "signed-regulation",
    "work-extraction",
)


def definition(arm="active", *, padded=True, native_none=None):
    if arm not in ARMS or native_none not in (None, "None"):
        raise ValueError((arm, native_none))
    raw = original.definition(arm if arm in original.ARMS else "active", padded=padded)
    raw["model"]["id"] = MODEL_ID
    group = raw["model"]["network_transport"]
    group["accounting"] = ACCOUNTING
    for row in group["routes"]:
        row["configuration"]["standard free energy"] = native_none
        row["drive"]["supplied_energy_J_per_mol"] = 60000.0
    if arm in ("downhill", "signed-regulation", "work-extraction"):
        route = deepcopy(next(row for row in group["routes"] if row["id"] == "na_drive"))
        route["drive"]["supplied_energy_J_per_mol"] = (
            -60000.0 if arm == "signed-regulation" else -1000.0 if arm == "work-extraction" else 0.0
        )
        if arm == "signed-regulation":
            route["configuration"].update(
                {"transporter inhibitors": ["Na&"], "inhibitor Km": [1.0], "inhibitor n": [1.0]}
            )
        group["routes"] = [route]
        raw["experiment"]["network_transport_controls"] = [
            row
            for row in raw["experiment"]["network_transport_controls"]
            if row["transporter_id"] == route["id"]
        ]
    raw["execution"]["network_transport_capacity"] = len(group["routes"]) + int(padded)
    return raw


def probe(arm="active", *, padded=False, native_none=None):
    """Two original nominal steps, with a distinct actual route-only boundary."""
    raw = definition(arm, padded=padded, native_none=native_none)
    end, dt = 2 * raw["execution"]["dt"], raw["execution"]["dt"]
    raw["experiment"]["end_time"] = end
    for key, groups in raw["experiment"].items():
        if key.endswith("_controls"):
            for group in groups:
                name = "controls" if "controls" in group else "schedule"
                group[name] = [row for row in group[name] if row["time"] <= end]
    times = [0.0, dt, end]
    routes = raw["experiment"]["network_transport_controls"]
    if routes:
        time = 0.75 * dt
        times.append(time)
        routes[0]["schedule"].append(
            dict(time=time, availability=0.0 if arm == "blocked" else 0.35)
        )
    raw["experiment"]["observation_times"] = sorted(times)
    return raw


parent_definition = original.parent_definition
