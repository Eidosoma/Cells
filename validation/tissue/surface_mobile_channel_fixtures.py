"""Synthetic joint-state channel controls; no biological diffusion-rate fit."""

from validation.tissue import surface_mobile_pump_fixtures as prior

STATES = ("m0h0", "m0h1", "m1h0", "m1h1")
ARMS = (
    "mobile",
    "immobile",
    "blocked",
    "frozen",
    "empty",
    "zero_permeability",
    "release",
    "counterflow",
    "channel_only",
)


def factorized(m, h):
    return ((1 - m) * (1 - h), (1 - m) * h, m * (1 - h), m * h)


def definition(arm="mobile", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition(backend=backend, padded=padded)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    # Conformation mixing dissipation needs this resolution at these synthetic
    # rates. Keep the coarser 12.5-us step in the independent refinement test.
    x["dt"] = 6.25e-6
    m["id"] = "resolved_redistribution@3"
    m["mobile_channels"] = []
    for i, (total, gate, diffusion) in enumerate(
        (
            ([0.02, 0.005], [(0.8, 0.7), (0.2, 0.3)], 10000.0),
            ([0.004, 0.016], [(0.35, 0.85), (0.75, 0.45)], 6000.0),
        )
    ):
        probabilities = [factorized(*v) for v in gate]
        if arm == "empty":
            total = [0.0, 0.0]
        if arm == "counterflow":
            total = [0.01, 0.015]
            probabilities = [(0.4, 0.1, 0.1, 0.4), (0.1, 0.4, 0.4, 0.1)]
        m["mobile_channels"].append(
            dict(
                id="mobile_kv_" + str(i),
                kinetic_law="betse_kv1p5_mh@1",
                species_id="K",
                reference_density_fmol_per_um2=1e-4,
                permeability_at_reference_density_m_per_s=0.0
                if arm == "zero_permeability"
                else 2e-8,
                initial_state_amount_fmol={
                    state: {
                        p["id"]: total[j] * probabilities[j][q]
                        for j, p in enumerate(m["membranes"])
                    }
                    for q, state in enumerate(STATES)
                },
                diffusivity_um2_per_s=0.0 if arm == "immobile" else diffusion,
                gate_mode="frozen" if arm in ("frozen", "counterflow") else "dynamic",
            )
        )
    e["channel_controls"] = [
        dict(
            channel_id=p["id"],
            membrane_id=patch["id"],
            schedule=[dict(time=0.0, availability=0.0 if arm in ("blocked", "release") else 1.0)],
        )
        for p in m["mobile_channels"]
        for patch in m["membranes"]
    ]
    if arm == "release":
        for i, g in enumerate(e["channel_controls"]):
            g["schedule"].extend(
                [
                    dict(time=0.000137, availability=0.6 + 0.2 * (i % 2)),
                    dict(time=0.000237, availability=0.0),
                ]
            )
        e["observation_times"] = [0.0, 0.000137, 0.0002, 0.000237, 0.0004]
    if arm == "channel_only":
        m["mobile_populations"] = []
        x["population_capacity"] = 1
        for p in m["mobile_pumps"]:
            p["initial_amount_fmol"] = {k: 0.0 for k in p["initial_amount_fmol"]}
        for patch in m["membranes"]:
            patch["permeability_m_per_s"] = {k: 0.0 for k in patch["permeability_m_per_s"]}
    x["channel_population_capacity"] = 2 + int(padded)
    return raw


def multicell(boundary):
    raw = prior.multicell(boundary)
    source = definition()["model"]["mobile_channels"]
    m = raw["model"]
    m["temperature_K"] = 298.15
    m["id"] = "resolved_redistribution@3"
    m["mobile_channels"] = source
    for k, pop in enumerate(source):
        pop["initial_state_amount_fmol"] = {
            s: {
                p["id"]: (
                    0.0
                    if k == 1 and p["inside"] == "cell_1"
                    else p["area_m2"]
                    * 1e12
                    * 1e-4
                    * (1 + 0.2 * j)
                    * factorized(0.3 + 0.1 * j, 0.8 - 0.1 * j)[q]
                )
                for j, p in enumerate(m["membranes"])
            }
            for q, s in enumerate(STATES)
        }
    raw["experiment"]["channel_controls"] = [
        dict(
            channel_id=p["id"], membrane_id=patch["id"], schedule=[dict(time=0.0, availability=0.7)]
        )
        for p in source
        for patch in m["membranes"]
    ]
    raw["execution"]["channel_population_capacity"] = 3
    return raw
