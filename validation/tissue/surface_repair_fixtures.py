"""Synthetic injury controls, not fitted repair kinetics or biological cases."""

from validation.tissue import surface_calcium_cav_fixtures as base

ARMS = ("uninjured", "sham", "held", "resealing")


def definition(arm="resealing", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = base.definition(backend=backend, padded=padded)
    m, e = raw["model"], raw["experiment"]
    m["id"] = "resolved_repair@1"
    e.update(end_time=50e-6, observation_times=[0.0, 5.3e-6, 15.3e-6, 25e-6, 50e-6])
    # Closure-integral refinement requires a finer grid than CaV alone.
    raw["execution"]["dt"] = 0.625e-6
    m["injury_patches"], e["injury_controls"] = [], []
    for i, patch in enumerate(m["ionic"]["membranes"]):
        m["injury_patches"].append(
            dict(
                membrane_id=patch["id"],
                law="prescribed_patch_injury_resealing@1",
                initial_damage=0.0,
                injury_rate_per_s=20000.0,
                resealing_rate_per_s=4000.0,
                permeability_m_per_s={
                    s["id"]: (1e-8 if s["id"] in ("Na", "K") else 0.0)
                    for s in m["ionic"]["species"]
                },
            )
        )
        reseal = 0.0 if arm == "held" else 1.0
        schedule = [dict(time=0.0, injury=0.0, resealing=reseal)]
        # Keep the same event grid even for sham/no-injury controls.
        schedule += [
            dict(
                time=5.3e-6, injury=float(i == 0 and arm in ("held", "resealing")), resealing=reseal
            ),
            dict(time=15.3e-6, injury=0.0, resealing=reseal),
        ]
        e["injury_controls"].append(dict(membrane_id=patch["id"], schedule=schedule))
    if arm == "uninjured":
        for p in m["injury_patches"]:
            p["injury_rate_per_s"] = 0.0
    return raw
