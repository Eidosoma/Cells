"""Four extra calcium laws sharing existing ionic, calcium and fuel inventories."""

from copy import deepcopy

from validation.tissue import surface_calcium_catalog_fixtures as calcium
from validation.tissue import surface_calcium_energy_fixtures as energy
from validation.tissue import surface_catalog_fixtures as ionic

FAMILIES = ("ionic", "calcium", "energy")
ARMS = ("open", "blocked", "reordered", "empty")
ADDED_LAWS = (
    "betse_ca_l2_m2h@1",
    "betse_ca_l3_shift15_m2h@1",
    "betse_cav_g_m2h_regularized@1",
    "betse_caleak_always_open@1",
)
MODEL_IDS = dict(
    ionic="resolved_tissue@9", calcium="resolved_calcium@8", energy="resolved_calcium_energy@2"
)


def definition(family="ionic", arm="open", *, backend="cpu", padded=True):
    if family not in FAMILIES or arm not in ARMS:
        raise ValueError((family, arm))
    previous = dict(ionic=ionic, calcium=calcium, energy=energy)[family]
    raw = previous.definition(
        "reordered" if arm == "reordered" else "open", backend=backend, padded=padded
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = MODEL_IDS[family]
    ion = m if family == "ionic" else m["ionic"]
    ion["id"] = MODEL_IDS["ionic"]
    for i, law in enumerate(ADDED_LAWS):
        channel = deepcopy(ion["channels"][0])
        channel.update(
            id=f"calcium_extra_{i}",
            membrane_id=ion["membranes"][i]["id"],
            kinetic_law=law,
            max_permeability_m_per_s=1e-9,
            abundance=0.08,
            initial_gate=[0.27 + 0.03 * i, 0.65 - 0.04 * i],
            permeant_ions=[dict(species_id="Ca", relative_permeability=1.0)],
        )
        ion["channels"].append(channel)
        e["channel_controls"].append(
            dict(channel_id=channel["id"], schedule=[dict(time=0.0, availability=0.8)])
        )
    if arm == "blocked":
        for group in e["channel_controls"]:
            for c in group["schedule"]:
                c["availability"] = 0.0
    if arm == "empty":
        ion["channels"] = []
        e["channel_controls"] = []
    if arm == "reordered":
        ion["channels"].reverse()
        e["channel_controls"].reverse()
    x["channel_capacity"] = len(ion["channels"]) + int(padded)
    return raw


def compact_probe(family="energy"):
    """50 us of coupled wiring/control changes; no depletion or gate-settling claim."""
    raw = definition(family, padded=False)
    dt, e = raw["execution"]["dt"], raw["experiment"]
    e.update(end_time=40 * dt, observation_times=[i * dt for i in (0, 10, 15, 20, 30, 40)])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                key = "controls" if "controls" in group else "schedule"
                group[key] = [c for c in group[key] if c["time"] <= e["end_time"]]
    for row in e["channel_controls"]:
        if row["channel_id"] == "calcium_extra_1":
            row["schedule"].append(dict(time=10 * dt, availability=0.35))
        elif row["channel_id"] == "calcium_extra_3":
            row["schedule"].extend(
                [dict(time=20 * dt, availability=0.0), dict(time=30 * dt, availability=0.7)]
            )
    if family == "energy":
        e["regeneration_controls"][0]["schedule"].append(dict(time=15 * dt, availability=0.0))
    return raw


def assembly_definition(family="energy", *, backend="cpu"):
    if family not in ("calcium", "energy"):
        raise ValueError("Assembly requires the owned calcium family")
    raw = (calcium if family == "calcium" else energy).assembly_definition(backend=backend)
    raw["ionic"] = definition(family, backend=backend)
    return raw
