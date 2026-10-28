"""Prescribed Na/K lesion on the finite-fuel/chemical/water owner graph.

Damage/resealing rates are synthetic controls. Interfaces and ER volume stay
fixed, and no structural ATP cost or biological repair law is introduced.
"""

from validation.tissue import calcium_energy_water_fixtures as base

MODEL_ID = "resolved_calcium_energy_water_repair@1"
REPAIR_ARMS = ("uninjured", "sham", "held", "resealing", "preinjured")
STRESS_ARMS = (
    "open",
    "blocked",
    "reordered",
    "empty",
    "instant_only",
    "dynamic_only",
    "sealed",
    "supply_off",
    "reverse",
    "absent",
)
ARMS = (*REPAIR_ARMS, *STRESS_ARMS)


def definition(arm="resealing", *, parent="open", backend="cpu", padded=True):
    if arm not in ARMS or parent not in base.ARMS:
        raise ValueError((arm, parent))
    prior = arm if arm in STRESS_ARMS else parent
    repair = arm if arm in REPAIR_ARMS else "preinjured"
    raw = base.definition(prior, backend=backend, padded=padded)
    m, e = raw["model"], raw["experiment"]
    m["id"] = MODEL_ID
    raw["execution"]["dt"] = 0.625e-6
    e.update(end_time=50e-6, observation_times=[0.0, 5.3e-6, 15.3e-6, 25e-6, 50e-6])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [value for value in row[key] if value["time"] <= e["end_time"]]
    m["injury_patches"], e["injury_controls"] = [], []
    for i, patch in enumerate(m["ionic"]["membranes"]):
        m["injury_patches"].append(
            dict(
                membrane_id=patch["id"],
                law="prescribed_patch_injury_resealing@1",
                initial_damage=0.25 if i == 0 and repair == "preinjured" else 0.0,
                injury_rate_per_s=0.0 if repair == "uninjured" else 20000.0,
                resealing_rate_per_s=4000.0,
                permeability_m_per_s={
                    ion["id"]: 1e-8 if ion["id"] in ("Na", "K") else 0.0
                    for ion in m["ionic"]["species"]
                },
            )
        )
        resealing = 0.0 if repair == "held" else 1.0
        e["injury_controls"].append(
            dict(
                membrane_id=patch["id"],
                schedule=[
                    dict(time=0.0, injury=0.0, resealing=resealing),
                    dict(
                        time=5.3e-6,
                        injury=float(i == 0 and repair in ("held", "resealing")),
                        resealing=resealing,
                    ),
                    dict(time=15.3e-6, injury=0.0, resealing=resealing),
                ],
            )
        )
    if arm == "reordered":
        m["injury_patches"].reverse()
        e["injury_controls"].reverse()
    return raw


def compact_probe(arm="resealing", *, backend="cpu", padded=False):
    """50-us coupled development with off-grid injury and parent control events."""
    return definition(arm, parent="release", backend=backend, padded=padded)


def assembly_definition(arm="resealing", *, parent="open", backend="cpu"):
    raw = base.assembly_definition(backend=backend)
    raw["ionic"] = definition(arm, parent=parent, backend=backend)
    raw["ionic"]["experiment"]["observation_times"] = [0.0, 5e-6, 10e-6, 20e-6, 50e-6]
    raw["window_ticks"] = 8
    for row in raw["pools"]:
        row["pool"].update(end_time_s=50e-6, k_off_s_inv=40000.0)
    return raw
