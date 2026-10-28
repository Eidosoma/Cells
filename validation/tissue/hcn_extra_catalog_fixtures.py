"""Three HCN variants in the complete 56-law catalog; independent raw inputs."""

from copy import deepcopy

from validation.channels import hcn_extra_reference as source
from validation.tissue import morris_lecar_catalog_fixtures as prior

FAMILIES = prior.FAMILIES
ARMS = ("open", "blocked", "reordered", "empty", "leak_only", "camp_only")
MODEL_IDS = dict(
    ionic="resolved_tissue@12", calcium="resolved_calcium@11", energy="resolved_calcium_energy@5"
)
ADDED_LAWS = (
    ("betse_hcn_leak_open@1", "HCNLeak", 0.33),
    ("betse_hcn2_camp_m@1", "HCN2_cAMP", 0.2),
    ("betse_hcn4_camp_m@1", "HCN4_cAMP", 0.2),
)


def definition(family="energy", arm="open", *, backend="cpu", padded=True):
    if family not in FAMILIES or arm not in ARMS:
        raise ValueError((family, arm))
    raw = prior.definition(family, "open", backend=backend, padded=False)
    raw["model"]["id"] = MODEL_IDS[family]
    m = raw["model"] if family == "ionic" else raw["model"]["ionic"]
    m["id"] = MODEL_IDS["ionic"]
    e = raw["experiment"]
    for i, (law, name, sodium) in enumerate(ADDED_LAWS):
        channel = deepcopy(m["channels"][0])
        channel.update(
            id=f"hcn_extra_{i}",
            membrane_id=m["membranes"][i % len(m["membranes"])]["id"],
            kinetic_law=law,
            max_permeability_m_per_s=1.5e-9,
            abundance=0.1,
            initial_gate=[] if i == 0 else [float(v) for v in source.initial_gates(-0.080, name)],
            permeant_ions=[
                dict(species_id=s, relative_permeability=w)
                for s, w in (("Na", sodium), ("K", 1.0), ("Ca", 0.05))
            ],
        )
        m["channels"].append(channel)
        e["channel_controls"].append(
            dict(channel_id=channel["id"], schedule=[dict(time=0.0, availability=0.8)])
        )
    if arm == "blocked":
        for row in e["channel_controls"]:
            for change in row["schedule"]:
                change["availability"] = 0.0
    if arm == "reordered":
        m["species"].reverse()
        m["channels"].reverse()
        e["channel_controls"].reverse()
    if arm in ("leak_only", "camp_only", "empty"):
        wanted = (
            {"hcn_extra_0"}
            if arm == "leak_only"
            else {"hcn_extra_1", "hcn_extra_2"}
            if arm == "camp_only"
            else set()
        )
        m["channels"] = [c for c in m["channels"] if c["id"] in wanted]
        e["channel_controls"] = [c for c in e["channel_controls"] if c["channel_id"] in wanted]
    raw["execution"]["channel_capacity"] = len(m["channels"]) + int(padded)
    return raw


def compact_probe(family="energy"):
    """50 us of live coupling and separate controls, not HCN steady-state evidence."""
    raw = definition(family, padded=False)
    e, dt = raw["experiment"], raw["execution"]["dt"]
    e.update(end_time=40 * dt, observation_times=[i * dt for i in (0, 10, 15, 20, 30, 40)])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [c for c in row[key] if c["time"] <= e["end_time"]]
    for row in e["channel_controls"]:
        if row["channel_id"] in ("hcn_extra_0", "hcn_extra_2"):
            first = 10 if row["channel_id"] == "hcn_extra_0" else 20
            row["schedule"].extend(
                [dict(time=first * dt, availability=0.0), dict(time=30 * dt, availability=0.6)]
            )
    if family == "energy":
        e["regeneration_controls"][0]["schedule"].append(dict(time=15 * dt, availability=0.0))
    return raw


def assembly_definition(family="energy", *, backend="cpu"):
    raw = prior.assembly_definition(family, backend=backend)
    raw["ionic"] = definition(family, backend=backend)
    return raw
