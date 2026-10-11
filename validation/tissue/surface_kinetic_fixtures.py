"""Synthetic resolved kinetic worlds; parameters are not biological measurements."""

from validation.tissue import surface_dynamics_fixtures as passive

ARMS = passive.ARMS


def definition(arm="open", *, backend="cpu", padded=True):
    raw = passive.definition(arm, backend=backend, padded=padded)
    m, e = raw["model"], raw["experiment"]
    m["id"], m["temperature_K"] = "resolved_tissue@2", 298.15
    for i, p in enumerate(m["membranes"]):
        p["pump"] = dict(
            id=f"pump_{i}",
            law="nak_atp_mass_action_positive@1",
            roles=dict(sodium="Na", potassium="K"),
            stoichiometry=dict(Na=-3, K=2),
            capacity_fmol_per_s=0.02 + 0.005 * i,
            km_na_mM=12.0,
            km_k_mM=0.2,
            km_atp_mM=0.5,
            metabolism=dict(
                kind="maintained_chemical_reservoirs@1",
                atp_mM=1.5,
                adp_mM=0.1,
                pi_mM=0.1,
                delta_g0_J_per_mol=-37000.0,
            ),
        )
    for p in m["junctions"]:
        p["gate"] = dict(
            law="betse_rate_junction_relaxation@1",
            threshold_voltage_V=0.015,
            minimum_open_fraction=0.1,
            initial_gate=0.6,
        )
    m["channels"] = [
        dict(
            id=f"channel_{i}",
            membrane_id=f"membrane_{i}",
            species_id="K",
            kinetic_law="betse_kv1p5_mh@1",
            max_permeability_m_per_s=3e-10,
            abundance=0.5 + 0.1 * i,
            initial_gate=[0.2 + 0.05 * i, 0.7],
        )
        for i in range(4)
    ]
    for kind in ("channel", "pump"):
        e[kind + "_controls"] = [
            dict(
                **{kind + "_id": f"{kind}_{i}"},
                schedule=(
                    [dict(time=0.0, availability=0.0), dict(time=0.00073, availability=0.8)]
                    if arm == "release"
                    else [dict(time=0.0, availability=0.8)]
                ),
            )
            for i in range(4)
        ]
    raw["execution"]["channel_capacity"] = 4 + int(padded)
    return raw
