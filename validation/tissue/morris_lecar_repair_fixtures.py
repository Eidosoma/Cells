"""Synthetic 53-law prescribed injury; clocks are separate from coupled settling."""

from validation.tissue import morris_lecar_catalog_fixtures as base

MODEL_ID = "resolved_repair@4"
ARMS = ("uninjured", "sham", "held", "resealing")
CHANNEL_ARMS = base.ARMS


def definition(arm="resealing", *, channels="open", backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = base.definition("calcium", channels, backend=backend, padded=padded)
    m, e = raw["model"], raw["experiment"]
    m["id"] = MODEL_ID
    e.update(end_time=50e-6, observation_times=[0.0, 5.3e-6, 15.3e-6, 25e-6, 50e-6])
    raw["execution"]["dt"] = 0.625e-6
    # Keep the original controls through the explicitly short development horizon.
    for name, groups in e.items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [c for c in row[key] if c["time"] <= e["end_time"]]
    m["injury_patches"], e["injury_controls"] = [], []
    for i, patch in enumerate(m["ionic"]["membranes"]):
        m["injury_patches"].append(
            dict(
                membrane_id=patch["id"],
                law="prescribed_patch_injury_resealing@1",
                initial_damage=0.0,
                injury_rate_per_s=0.0 if arm == "uninjured" else 20000.0,
                resealing_rate_per_s=4000.0,
                permeability_m_per_s={
                    s["id"]: 1e-8 if s["id"] in ("Na", "K") else 0.0 for s in m["ionic"]["species"]
                },
            )
        )
        reseal = 0.0 if arm == "held" else 1.0
        e["injury_controls"].append(
            dict(
                membrane_id=patch["id"],
                schedule=[
                    dict(time=0.0, injury=0.0, resealing=reseal),
                    dict(
                        time=5.3e-6,
                        injury=float(i == 0 and arm in ("held", "resealing")),
                        resealing=reseal,
                    ),
                    dict(time=15.3e-6, injury=0.0, resealing=reseal),
                ],
            )
        )
    return raw


def compact_probe(arm="resealing"):
    """50 us with injury boundaries and dynamic/stateless channel interventions."""
    raw = definition(arm, padded=False)
    for row in raw["experiment"]["channel_controls"]:
        if row["channel_id"] in ("morris_lecar_0", "morris_lecar_5"):
            first = 12.5e-6 if row["channel_id"] == "morris_lecar_0" else 25e-6
            row["schedule"].extend(
                [dict(time=first, availability=0.0), dict(time=37.5e-6, availability=0.6)]
            )
    return raw


def assembly_definition(arm="resealing", *, backend="cpu"):
    raw = base.assembly_definition("calcium", backend=backend)
    raw["ionic"] = definition(arm, backend=backend)
    raw["ionic"]["experiment"]["observation_times"] = [0.0, 5e-6, 10e-6, 20e-6, 50e-6]
    raw["window_ticks"] = 8
    for row in raw["pools"]:
        row["pool"].update(end_time_s=50e-6, k_off_s_inv=40000.0)
    return raw
