"""Synthetic mobile ATPase controls; diffusion/turnover are not biological fits."""

from validation.tissue import surface_dynamics_fixtures
from validation.tissue import surface_redistribution_fixtures as prior

ARMS = (
    "mobile",
    "immobile",
    "inhibited",
    "empty",
    "no_turnover",
    "reverse",
    "release",
    "pump_only",
    "uniform",
)


def definition(arm="mobile", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition(backend=backend, padded=padded)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = "resolved_redistribution@2"
    m["mobile_pumps"] = []
    if arm == "pump_only":
        m["mobile_populations"] = []
        x["population_capacity"] = 1
    for name, amounts, diffusion, turnover in (
        ("nak_alpha", [0.0015, 0.0005], 10000.0, 25.0),
        ("nak_beta", [0.0003, 0.0009], 6000.0, 9.0),
    ):
        if arm == "empty":
            amounts = [0.0, 0.0]
        if arm == "uniform":
            total = sum(amounts)
            amounts = [0.4 * total, 0.6 * total]
        m["mobile_pumps"].append(
            dict(
                id=name,
                law="nak_atp_mass_action_positive@1",
                roles=dict(sodium="Na", potassium="K"),
                stoichiometry=dict(Na=-3, K=2),
                turnover_per_s=0.0 if arm == "no_turnover" else turnover,
                km_na_mM=12.0,
                km_k_mM=0.2,
                km_atp_mM=0.5,
                metabolism=dict(
                    kind="maintained_chemical_reservoirs@1",
                    atp_mM=1.5,
                    adp_mM=0.1,
                    pi_mM=0.1,
                    delta_g0_J_per_mol=0.0 if arm == "reverse" else -37000.0,
                ),
                reference_density_fmol_per_um2=1e-5,
                initial_amount_fmol=dict(zip(("patch_0", "patch_1"), amounts, strict=True)),
                diffusivity_um2_per_s=0.0 if arm == "immobile" else diffusion,
            )
        )
    e["pump_controls"] = [
        dict(
            pump_id=p["id"],
            membrane_id=patch["id"],
            schedule=[dict(time=0.0, availability=0.0 if arm in ("inhibited", "release") else 1.0)],
        )
        for p in m["mobile_pumps"]
        for patch in m["membranes"]
    ]
    if arm == "release":
        for i, g in enumerate(e["pump_controls"]):
            g["schedule"].extend(
                [
                    dict(time=0.000137, availability=0.8 if i % 2 else 0.6),
                    dict(time=0.000237, availability=0.0),
                ]
            )
        e["observation_times"] = [0.0, 0.000137, 0.0002, 0.000237, 0.0004]
    x["pump_population_capacity"] = 2 + int(padded)
    return raw


def multicell(boundary):
    """Two cells, distinct capacitor components and open/closed return currents."""
    raw = surface_dynamics_fixtures.definition(boundary)
    source = definition()["model"]
    m = raw["model"]
    m["id"] = source["id"]
    for family, scale in (("mobile_populations", 1e-4), ("mobile_pumps", 1e-5)):
        m[family] = source[family]
        for k, pop in enumerate(m[family]):
            pop["initial_amount_fmol"] = {
                p["id"]: p["area_m2"] * 1e12 * scale * (1 + 0.2 * j + 0.05 * k)
                for j, p in enumerate(m["membranes"])
            }
    # One population is entirely absent on cell_1, while its other cell pumps.
    for p in m["membranes"]:
        if p["inside"] == "cell_1":
            m["mobile_pumps"][1]["initial_amount_fmol"][p["id"]] = 0.0
    m["surface_edges"] = []
    for cell in m["cells"]:
        patches = [p["id"] for p in m["membranes"] if p["inside"] == cell["id"]]
        m["surface_edges"].append(
            dict(
                id="along_" + cell["id"],
                sender=patches[0],
                receiver=patches[1],
                width_um=1.0,
                distance_um=2.0,
            )
        )
    raw["experiment"]["pump_controls"] = [
        dict(pump_id=pop["id"], membrane_id=p["id"], schedule=[dict(time=0.0, availability=0.7)])
        for pop in m["mobile_pumps"]
        for p in m["membranes"]
    ]
    raw["execution"].update(
        population_capacity=3,
        surface_edge_capacity=3,
        pump_population_capacity=3,
    )
    if boundary == "closed":
        # Roles are named, never inferred from species order.
        m["species"] = m["species"][::-1]
    return raw
