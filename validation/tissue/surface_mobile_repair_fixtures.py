"""Synthetic mobile-channel/calcium/injury composition; no fitted recovery law."""

from validation.tissue import surface_mobile_channel_fixtures as mobile
from validation.tissue import surface_repair_fixtures as prior

ARMS = ("mobile", "immobile", "blocked", "empty", "sham", "held", "release", "channel_only")


def definition(arm="mobile", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition(
        "sham" if arm == "sham" else "held" if arm == "held" else "resealing",
        backend=backend,
        padded=padded,
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = "resolved_repair@2"
    ion = m["ionic"]
    # Representative immobile shared HCN/CaV populations; the dedicated CaV,
    # PMCA/NCX, ER, buffer and IP3 processes remain present on both cell owners.
    ion["channels"] = [
        c for c in ion["channels"] if c["kinetic_law"] in ("betse_hcn2_m@1", "betse_cav2p1_m@1")
    ]
    names = {c["id"] for c in ion["channels"]}
    e["channel_controls"] = [c for c in e["channel_controls"] if c["channel_id"] in names]
    x["channel_capacity"] = len(names) + int(padded)
    patches = ion["membranes"]
    m["surface_edges"] = []
    for cell in ion["cells"]:
        own = [p for p in patches if p["inside"] == cell["id"]]
        for a, b in zip(own, own[1:], strict=False):
            m["surface_edges"].append(
                dict(
                    id="surface_" + a["id"],
                    sender=a["id"],
                    receiver=b["id"],
                    width_um=2.0,
                    distance_um=1.0,
                )
            )
    m["mobile_channels"] = []
    for k in range(2):
        amounts = {s: {} for s in mobile.STATES}
        for j, patch in enumerate(patches):
            total = patch["area_m2"] * 1e12 * 1e-4 * (2.0 if j % 2 == 0 else 0.4)
            if arm == "empty" or (k == 1 and patch["inside"] == ion["cells"][-1]["id"]):
                total = 0.0
            gate = (0.8, 0.7) if j % 2 == 0 else (0.2, 0.3)
            for s, value in zip(mobile.STATES, mobile.factorized(*gate), strict=True):
                amounts[s][patch["id"]] = total * value
        m["mobile_channels"].append(
            dict(
                id=f"mobile_kv_{k}",
                kinetic_law="betse_kv1p5_mh@1",
                species_id="K",
                reference_density_fmol_per_um2=1e-4,
                permeability_at_reference_density_m_per_s=2e-8,
                initial_state_amount_fmol=amounts,
                diffusivity_um2_per_s=0.0 if arm == "immobile" else 10000.0 / (1 + k),
                gate_mode="dynamic",
            )
        )
    e["mobile_channel_controls"] = []
    for pop in m["mobile_channels"]:
        for patch in patches:
            schedule = [dict(time=0.0, availability=0.0 if arm in ("blocked", "release") else 1.0)]
            if arm == "release":
                schedule += [
                    dict(time=19.1e-6, availability=0.7),
                    dict(time=29.1e-6, availability=0.0),
                ]
            e["mobile_channel_controls"].append(
                dict(channel_id=pop["id"], membrane_id=patch["id"], schedule=schedule)
            )
    if arm == "release":
        e["observation_times"] = sorted({*e["observation_times"], 19.1e-6, 29.1e-6})
    if arm == "channel_only":
        for patch in ion["membranes"]:
            patch["permeability_m_per_s"] = {s: 0.0 for s in patch["permeability_m_per_s"]}
        for family in ("channel_controls", "pump_controls", "calcium_channel_controls"):
            for row in e[family]:
                for c in row["schedule"]:
                    c["availability"] = 0.0
        for row in e["plasma_controls"]:
            for c in row["schedule"]:
                c.update(pump=0.0, exchanger=0.0)
        for p in m["injury_patches"]:
            p["permeability_m_per_s"] = {s: 0.0 for s in p["permeability_m_per_s"]}
    x.update(
        channel_population_capacity=2 + int(padded),
        surface_edge_capacity=len(m["surface_edges"]) + int(padded),
    )
    return raw
