"""Manufactured zero-state potassium populations on four resolved membrane patches."""

from copy import deepcopy

from validation.tissue import channel_catalog_v2_fixtures as prior

FAMILIES = prior.FAMILIES
ARMS = ("open", "blocked", "reordered", "empty", "instant_only")
LAW = "betse_cagpotassium_numeric_mM_scale@1"
MODEL_IDS = dict(
    ionic="resolved_tissue@10", calcium="resolved_calcium@9", energy="resolved_calcium_energy@3"
)


def definition(family="energy", arm="open", *, backend="cpu", padded=True):
    if family not in FAMILIES or arm not in ARMS:
        raise ValueError((family, arm))
    raw = prior.definition(family, "open", backend=backend, padded=False)
    raw["model"]["id"] = MODEL_IDS[family]
    m = raw["model"] if family == "ionic" else raw["model"]["ionic"]
    m["id"] = MODEL_IDS["ionic"]
    e = raw["experiment"]
    for i, patch in enumerate(m["membranes"]):
        channel = deepcopy(m["channels"][0])
        channel.update(
            id=f"calcium_sensitive_k_{i}",
            membrane_id=patch["id"],
            kinetic_law=LAW,
            max_permeability_m_per_s=2e-9,
            abundance=0.12 + 0.02 * i,
            initial_gate=[],
            permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
        )
        m["channels"].append(channel)
        e["channel_controls"].append(
            dict(
                channel_id=channel["id"],
                schedule=[dict(time=0.0, availability=0.75)],
            )
        )
    if arm == "blocked":
        for row in e["channel_controls"]:
            for c in row["schedule"]:
                c["availability"] = 0.0
    if arm == "reordered":
        m["species"].reverse()
        m["channels"].reverse()
        e["channel_controls"].reverse()
    if arm == "instant_only":
        m["channels"] = [c for c in m["channels"] if c["kinetic_law"] == LAW]
        ids = {c["id"] for c in m["channels"]}
        e["channel_controls"] = [c for c in e["channel_controls"] if c["channel_id"] in ids]
    if arm == "empty":
        m["channels"] = []
        e["channel_controls"] = []
    raw["execution"]["channel_capacity"] = len(m["channels"]) + int(padded)
    return raw


def compact_probe(family="energy"):
    """50 us of coupled wiring; no invented channel relaxation/recovery clock."""
    raw = definition(family, padded=False)
    e, dt = raw["experiment"], raw["execution"]["dt"]
    e.update(end_time=40 * dt, observation_times=[i * dt for i in (0, 10, 15, 20, 30, 40)])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [c for c in row[key] if c["time"] <= e["end_time"]]
    for row in e["channel_controls"]:
        if row["channel_id"] == "calcium_sensitive_k_0":
            row["schedule"].extend(
                [
                    dict(time=10 * dt, availability=0.0),
                    dict(time=30 * dt, availability=0.6),
                ]
            )
        if row["channel_id"] == "calcium_extra_1":
            row["schedule"].append(dict(time=20 * dt, availability=0.35))
    if family == "energy":
        e["regeneration_controls"][0]["schedule"].append(dict(time=15 * dt, availability=0.0))
    return raw


def assembly_definition(family="energy", *, backend="cpu"):
    raw = prior.assembly_definition(family, backend=backend)
    raw["ionic"] = definition(family, backend=backend)
    return raw
