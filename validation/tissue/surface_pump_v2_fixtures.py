"""Synthetic resolved pump worlds with calcium for resolved_pump_tissue@2.

Parameters are synthetic, not biological measurements. definition(calcium=False)
is the resolved_pump_tissue@1 fixture declared as @2 with no calcium pump (the
equivalence world). With calcium=True every owner also holds Ca (charge anchors
unchanged: the fixed background absorbs the added Ca charge), membranes,
junctions and faces carry Ca permeabilities, and every membrane has a
ca_atp_mass_action_positive@1 pump whose schedule follows its Na/K pump.
"""

from validation.tissue import surface_pump_fixtures as first

CELL_CA_mM = 1e-4
OUTSIDE_CA_mM = 2.0


def calcium_pump(i):
    return dict(
        id=f"calcium_pump_{i}",
        law="ca_atp_mass_action_positive@1",
        roles=dict(calcium="Ca"),
        stoichiometry=dict(Ca=-1),
        capacity_fmol_per_s=0.01 + 0.002 * i,
        km_ca_mM=1e-3,
        km_atp_mM=0.5,
        metabolism=dict(
            kind="maintained_chemical_reservoirs@1",
            atp_mM=1.5,
            adp_mM=0.1,
            pi_mM=0.1,
            delta_g0_J_per_mol=-30500.0,
        ),
    )


def definition(
    arm="open", *, backend="cpu", padded=True, solver="rk4", temperature_K=298.15, calcium=True
):
    raw = first.definition(
        arm, backend=backend, padded=padded, solver=solver, temperature_K=temperature_K
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = "resolved_pump_tissue@2"
    if not calcium:
        for p in m["membranes"]:
            p["calcium_pump"] = None
        e["calcium_pump_controls"] = []
        return raw
    m["species"].append(dict(id="Ca", valence=2))
    for key, concentration in (("cells", CELL_CA_mM), ("extracellular", OUTSIDE_CA_mM)):
        for owner in m[key]:
            amount = concentration * owner["volume_pL"]
            owner["initial_amount_fmol"]["Ca"] = amount
            owner["fixed_charge_equivalent_fmol"] -= 2 * amount
    for i, p in enumerate(m["membranes"]):
        p["permeability_m_per_s"]["Ca"] = 1e-10 * (1 + 0.25 * i)
        p["calcium_pump"] = calcium_pump(i)
    for p in m["junctions"]:
        p["permeability_m_per_s"]["Ca"] = 2e-10
    for p in m["faces"]:
        p["diffusivity_m2_per_s"]["Ca"] = 5e-15
    e["calcium_pump_controls"] = [
        dict(pump_id=f"calcium_pump_{i}", schedule=[dict(c) for c in group["schedule"]])
        for i, group in enumerate(e["pump_controls"])
    ]
    x["material_balance_atol_fmol"]["Ca"] = 2e-11
    return raw
