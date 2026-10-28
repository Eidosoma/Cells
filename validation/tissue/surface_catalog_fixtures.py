"""Manufactured shared Na/K/Ca/Cl catalog on multiple tissue membrane owners.

No fitted physiology. The calcium/ER parent is projected to its ordinary ionic
model: calcium here is a mobile ion, without the parent's dedicated stores.
"""

from copy import deepcopy

from validation.tissue import surface_calcium_cav_fixtures as prior

ADDED = (
    ("betse_nav1p3_m3h_regularized@1", (("Na", 1.0),)),
    ("betse_navrat2_m3h_regularized@1", (("Na", 1.0),)),
    ("betse_navrat1_m3h_regularized@1", (("Na", 1.0),)),
    ("betse_navrat3_m3h_regularized@1", (("Na", 1.0),)),
    ("betse_naleak_always_open@1", (("Na", 1.0),)),
    ("betse_nav1p6_persistent_m@1", (("Na", 1.0),)),
    ("betse_kv2p1_mh@1", (("K", 1.0),)),
    ("betse_kv2p2_mh@1", (("K", 1.0),)),
    ("betse_kv3p1_m@1", (("K", 1.0),)),
    ("betse_kv3p2_m2@1", (("K", 1.0),)),
    ("betse_kv3p3_m2h_source_tau@1", (("K", 1.0),)),
    ("betse_kv3p4_mh@1", (("K", 1.0),)),
    ("betse_k_fast_mh@1", (("K", 1.0),)),
    ("betse_kleak_always_open@1", (("K", 1.0),)),
    ("betse_clleak_always_open@1", (("Cl", 1.0),)),
    ("betse_catleak_na_k@1", (("Na", 1.0), ("K", 1.0), ("Ca", 0.0))),
    ("betse_catleak2_na_k_ca@1", (("Na", 1.0), ("K", 1.0), ("Ca", 1.0))),
)
ARMS = ("open", "blocked", "release", "reordered")


def legacy_definition(*, backend="cpu", padded=True):
    raw = prior.definition("baseline", backend=backend, padded=padded)
    raw["model"] = raw["model"]["ionic"]
    for key in ("store_controls", "plasma_controls", "calcium_channel_controls"):
        raw["experiment"].pop(key)
    for key in ("chemical_capacity", "reaction_capacity"):
        raw["execution"].pop(key)
    return raw


def definition(arm="open", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = legacy_definition(backend=backend, padded=padded)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = "resolved_tissue@8"
    for i, (law, ions) in enumerate(ADDED):
        channel = deepcopy(m["channels"][i % 4])
        channel.update(
            id=f"catalog_population_{i}",
            kinetic_law=law,
            permeant_ions=[dict(species_id=s, relative_permeability=w) for s, w in ions],
            initial_gate=[0.15 + 0.03 * (i % 7), 0.8 - 0.04 * (i % 6)],
            max_permeability_m_per_s=1e-9,
            abundance=0.05 + 0.01 * (i % 4),
        )
        m["channels"].append(channel)
        e["channel_controls"].append(dict(channel_id=channel["id"], schedule=[]))
    # Intrinsic gates evolve independently of availability, including leak gates.
    for i, row in enumerate(e["channel_controls"]):
        row["schedule"] = [dict(time=0.0, availability=0.0 if arm == "blocked" else 0.8)]
        if arm == "release":
            row["schedule"] += [
                dict(time=0.0005 + 0.000025 * (i % 2), availability=0.0),
                dict(time=0.001 + 0.000025 * (i % 2), availability=0.7),
            ]
    events = {c["time"] for g in e["channel_controls"] for c in g["schedule"]}
    e["observation_times"] = sorted(set(e["observation_times"]) | events)
    if arm == "reordered":
        m["species"].reverse()
        m["channels"].reverse()
        e["channel_controls"].reverse()
    x["channel_capacity"] = len(m["channels"]) + int(padded)
    return raw


def compact_probe():
    """Same laws/owners, early trajectory only; no slow-relaxation claim."""
    raw = definition("release", padded=False)
    e = raw["experiment"]
    dt = raw["execution"]["dt"]
    e.update(end_time=40 * dt, observation_times=[i * dt for i in (0, 10, 20, 30, 40)])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                group["schedule"] = [v for v in group["schedule"] if v["time"] <= e["end_time"]]
    return raw
