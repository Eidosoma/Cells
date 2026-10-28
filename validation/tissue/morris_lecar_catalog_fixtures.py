"""Thirteen ML populations with distinct zero/one-state channel declarations."""

from copy import deepcopy

from validation.tissue import calcium_activated_catalog_fixtures as prior

FAMILIES = prior.FAMILIES
ARMS = ("open", "blocked", "reordered", "empty", "instant_only", "dynamic_only")
MODEL_IDS = dict(
    ionic="resolved_tissue@11", calcium="resolved_calcium@10", energy="resolved_calcium_energy@4"
)
ADDED_LAWS = (
    ("betse_kv_ml1_dynamic_m@1", (("K", 1.0),)),
    ("betse_kv2p1_ml_dynamic_m@1", (("K", 1.0),)),
    ("betse_kv1p3_ml_dynamic_m@1", (("K", 1.0),)),
    ("betse_kv1p5_ml_dynamic_m@1", (("K", 1.0),)),
    ("betse_kv1p5s_ml_slow_dynamic_m@1", (("K", 1.0),)),
    ("betse_nav_ml_instantaneous@1", (("Na", 1.0),)),
    ("betse_cav_l_ml_instantaneous@1", (("Ca", 1.0),)),
    ("betse_cav_l_ml2_instantaneous@1", (("Ca", 1.0),)),
    ("betse_cav_n_ml_instantaneous@1", (("Ca", 1.0),)),
    ("betse_cav_t_ml_instantaneous@1", (("Ca", 1.0),)),
    ("betse_kir_ml_instantaneous@1", (("K", 1.0),)),
    ("betse_hcn2_ml_source_sign_instantaneous@1", (("K", 1.0), ("Na", 0.2))),
    ("betse_hcn4_ml_source_sign_instantaneous@1", (("K", 1.0), ("Na", 0.2))),
)


def definition(family="energy", arm="open", *, backend="cpu", padded=True):
    if family not in FAMILIES or arm not in ARMS:
        raise ValueError((family, arm))
    raw = prior.definition(family, "open", backend=backend, padded=False)
    raw["model"]["id"] = MODEL_IDS[family]
    m = raw["model"] if family == "ionic" else raw["model"]["ionic"]
    m["id"] = MODEL_IDS["ionic"]
    e = raw["experiment"]
    for i, (law, routes) in enumerate(ADDED_LAWS):
        channel = deepcopy(m["channels"][0])
        channel.update(
            id=f"morris_lecar_{i}",
            membrane_id=m["membranes"][i % len(m["membranes"])]["id"],
            kinetic_law=law,
            max_permeability_m_per_s=1.5e-9,
            abundance=0.1,
            initial_gate=[0.2 + 0.06 * i] if i < 5 else [],
            permeant_ions=[dict(species_id=s, relative_permeability=w) for s, w in routes],
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
    if arm in ("instant_only", "dynamic_only", "empty"):
        count = dict(instant_only=0, dynamic_only=1, empty=-1)[arm]
        m["channels"] = [c for c in m["channels"] if len(c["initial_gate"]) == count]
        ids = {c["id"] for c in m["channels"]}
        e["channel_controls"] = [c for c in e["channel_controls"] if c["channel_id"] in ids]
    raw["execution"]["channel_capacity"] = len(m["channels"]) + int(padded)
    return raw


def compact_probe(family="energy"):
    """50 us of state/control coupling; component relaxations are separate evidence."""
    raw = definition(family, padded=False)
    e, dt = raw["experiment"], raw["execution"]["dt"]
    e.update(end_time=40 * dt, observation_times=[i * dt for i in (0, 10, 15, 20, 30, 40)])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [c for c in row[key] if c["time"] <= e["end_time"]]
    for row in e["channel_controls"]:
        if row["channel_id"] in ("morris_lecar_0", "morris_lecar_5"):
            first = 10 if row["channel_id"] == "morris_lecar_0" else 20
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
