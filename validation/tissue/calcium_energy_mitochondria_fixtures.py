"""Explicit disjoint mitochondrial inventories on the 42-field parent fixture.

Synthetic fixed geometry, unchanged native-default diffusivity. This declares
new organelle inventories without withdrawing material from the cytosol.
"""

from validation.tissue import calcium_energy_network_transport_fixtures as prior

MODEL_ID = "resolved_calcium_energy_mitochondria@1"
ARMS = ("active", "blocked", "zero-diffusion", "reordered", "reverse")
F, R = prior.F, prior.R


def definition(arm="active", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition("active", backend=backend, padded=padded)
    m, e = raw["model"], raw["experiment"]
    m["id"] = MODEL_ID
    ion = m["ionic"]
    rows = []
    for i, cell in enumerate(ion["cells"]):
        volume = 0.5 * cell["volume_pL"]
        area = 0.5 * sum(p["area_m2"] for p in ion["membranes"] if p["inside"] == cell["id"])
        concentrations = dict(Na=20.0 + 2 * i, K=100.0 - 5 * i, Cl=30.0 + i, Ca=0.01 + 0.002 * i)
        rows.append(
            dict(
                id="mitochondrion_" + cell["id"],
                cell_id=cell["id"],
                volume_pL=volume,
                area_m2=area,
                specific_capacitance_F_per_m2=0.05,
                membrane_thickness_m=7.5e-9,
                initial_voltage_V=0.08 if arm == "reverse" else -0.08 + 0.02 * i,
                initial_amount_fmol={
                    s["id"]: volume * concentrations[s["id"]] for s in ion["species"]
                },
                diffusivity_m2_per_s={
                    s["id"]: 0.0 if arm == "zero-diffusion" else 1e-19 for s in ion["species"]
                },
            )
        )
    m["mitochondria"] = dict(
        law="betse_mitochondrial_passive_continuous_si@1",
        source_law="betse_mitochondrial_ion_voltage_source_v1_5_0@1",
        initialization="explicit_disjoint_inventory@1",
        voltage="charge_consistent_mito_minus_cytosol@1",
        cytosol_volume_role="solvent_volume_excludes_er_and_mitochondria@1",
        constants=dict(faraday_C_mol=F, gas_constant_J_mol_K=R),
        compartments=rows,
    )
    e["mitochondria_controls"] = [
        dict(
            mitochondrion_id=row["id"],
            schedule=[dict(time=0.0, availability=0.0 if arm == "blocked" else 0.8)],
        )
        for row in rows
    ]
    if arm == "reordered":
        rows.reverse()
        ion["species"].reverse()
        e["mitochondria_controls"].reverse()
    return raw


def compact_probe(arm="active", *, backend="cpu", padded=False):
    """50 us, with organelle-only edges and inherited maintained transport/fuel."""
    raw = definition(arm, backend=backend, padded=padded)
    e, dt = raw["experiment"], raw["execution"]["dt"]
    e.update(
        end_time=40 * dt,
        observation_times=[0.0, 8 * dt, 12.7e-6, 15 * dt, 20 * dt, 31.7e-6, 30 * dt, 40 * dt],
    )
    for kind, groups in e.items():
        if kind.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [change for change in row[key] if change["time"] <= e["end_time"]]
    by_id = {row["mitochondrion_id"]: row for row in e["mitochondria_controls"]}
    first = "mitochondrion_" + raw["model"]["ionic"]["cells"][0]["id"]
    by_id[first]["schedule"].extend(
        [
            dict(time=12.7e-6, availability=0.0),
            dict(time=31.7e-6, availability=0.0 if arm == "blocked" else 0.6),
        ]
    )
    e["regeneration_controls"][0]["schedule"].append(dict(time=15 * dt, availability=0.0))
    return raw
