"""Prescribed repair on the complete 56-law moving-volume/fuel owner."""

from validation.tissue import calcium_energy_water_hcn_extra_fixtures as base

MODEL_ID = "resolved_calcium_energy_water_repair@2"
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
    "leak_only",
    "camp_only",
    "legacy53",
)
ARMS = (*REPAIR_ARMS, *STRESS_ARMS)


def definition(arm="resealing", *, parent="open", backend="cpu", padded=True):
    if arm not in ARMS or parent not in base.ARMS:
        raise ValueError((arm, parent))
    prior = arm if arm in STRESS_ARMS else parent
    repair = arm if arm in REPAIR_ARMS else "preinjured"
    raw = base.definition(prior, backend=backend, padded=padded)
    model, experiment = raw["model"], raw["experiment"]
    model["id"] = MODEL_ID
    raw["execution"]["dt"] = 0.625e-6
    experiment.update(end_time=50e-6, observation_times=[0.0, 5.3e-6, 15.3e-6, 25e-6, 50e-6])
    for name, groups in experiment.items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [c for c in row[key] if c["time"] <= experiment["end_time"]]
    model["injury_patches"], experiment["injury_controls"] = [], []
    for i, patch in enumerate(model["ionic"]["membranes"]):
        model["injury_patches"].append(
            dict(
                membrane_id=patch["id"],
                law="prescribed_patch_injury_resealing@1",
                initial_damage=0.25 if i == 0 and repair == "preinjured" else 0.0,
                injury_rate_per_s=0.0 if repair == "uninjured" else 20000.0,
                resealing_rate_per_s=4000.0,
                permeability_m_per_s={
                    s["id"]: 1e-8 if s["id"] in ("Na", "K") else 0.0
                    for s in model["ionic"]["species"]
                },
            )
        )
        reseal = 0.0 if repair == "held" else 1.0
        experiment["injury_controls"].append(
            dict(
                membrane_id=patch["id"],
                schedule=[
                    dict(time=0.0, injury=0.0, resealing=reseal),
                    dict(
                        time=5.3e-6,
                        injury=float(i == 0 and repair in ("held", "resealing")),
                        resealing=reseal,
                    ),
                    dict(time=15.3e-6, injury=0.0, resealing=reseal),
                ],
            )
        )
    if arm == "reordered":
        model["injury_patches"].reverse()
        experiment["injury_controls"].reverse()
    return raw


def compact_probe(arm="resealing", *, backend="cpu", padded=False):
    raw = definition(arm, parent="release", backend=backend, padded=padded)
    for row in raw["experiment"]["channel_controls"]:
        if row["channel_id"] in ("hcn_extra_0", "hcn_extra_2"):
            row["schedule"] = [
                dict(time=time, availability=value)
                for time, value in ((0.0, 0.8), (12.5e-6, 0.0), (37.5e-6, 0.6))
            ]
    return base.all_observation_boundaries(raw)
