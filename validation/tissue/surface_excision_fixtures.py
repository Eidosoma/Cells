"""Manufactured three-cell passive excision cases; no wound-healing claim."""

import math

F = 6.02214076e23 * 1.602176634e-19
ARMS = (
    "open",
    "clamped",
    "blocked",
    "no-op",
    "single-survivor",
    "sequential",
    "closed",
    "disconnected",
)
DT = 1e-5
CUT_TIME = 100 * DT


def definition(arm="open", *, backend="cpu", padded=False):
    if arm not in ARMS:
        raise ValueError(arm)
    species = ("Na", "K", "Cl")
    z = (1, 1, -1)
    cells = []
    for i in range(3):
        volume = 1.5 + 0.4 * i
        cells.append(
            dict(
                id=f"cell_{i}",
                volume_pL=volume,
                initial_amount_fmol=dict(
                    zip(
                        species,
                        [volume * v for v in (12 + 2 * i, 140 - 4 * i, 10 + i)],
                        strict=True,
                    )
                ),
                fixed_charge_equivalent_fmol=0.0,
                initial_charge_C=0.0,
            )
        )
    outside = [
        dict(
            id="shared",
            volume_pL=5.0,
            initial_amount_fmol=dict(Na=700.0, K=25.0, Cl=600.0),
            fixed_charge_equivalent_fmol=0.0,
            initial_charge_C=0.0,
            reservoir=arm == "clamped",
            boundary_potential_V=-0.003 if arm == "clamped" else 0.0,
        ),
        dict(
            id="bath",
            volume_pL=8.0,
            initial_amount_fmol=dict(Na=1160.0, K=32.0, Cl=960.0),
            fixed_charge_equivalent_fmol=0.0,
            initial_charge_C=0.0,
            reservoir=arm != "closed",
            boundary_potential_V=0.004 if arm == "clamped" else 0.0,
        ),
    ]
    membranes = []
    q = [0.0] * 5
    potentials = [-0.020, -0.025, -0.030, -0.003, outside[1]["boundary_potential_V"]]
    for i, cell in enumerate(cells):
        for j, external in enumerate(outside):
            if arm == "disconnected" and j == 0 and i != 0:
                continue
            cap = (1.5 + 0.2 * i if j == 0 else 2.0 + 0.3 * i) * 1e-12
            membranes.append(
                dict(
                    id=f"membrane_{i}_{external['id']}",
                    inside=cell["id"],
                    outside=external["id"],
                    area_m2=cap / 0.02,
                    capacitance_F=cap,
                    law="constant_field@1",
                    permeability_m_per_s=dict(Na=1e-9, K=2e-9, Cl=8e-10),
                )
            )
            charge = cap * (potentials[i] - potentials[3 + j])
            q[i] += charge
            q[3 + j] -= charge
    # Ionic plus fixed charge is conserved on retained owners. Reservoir
    # electrode charge is separate from this declared material charge.
    for i, row in enumerate([*cells, *outside]):
        row["initial_charge_C"] = q[i] if not row.get("reservoir", False) else 0.0
        row["fixed_charge_equivalent_fmol"] = row["initial_charge_C"] / (F * 1e-15) - math.fsum(
            valence * row["initial_amount_fmol"][s] for s, valence in zip(species, z, strict=True)
        )
    junctions = [
        dict(
            id=f"junction_{i}_{i + 1}",
            sender=f"cell_{i}",
            receiver=f"cell_{i + 1}",
            area_m2=4e-11,
            permeability_m_per_s=dict(Na=1e-9, K=2e-9, Cl=1e-9),
            law="constant_field@1",
        )
        for i in range(2)
    ]
    faces = [
        dict(
            id="face_shared_bath",
            sender="shared",
            receiver="bath",
            area_m2=1e-10,
            length_m=1e-5,
            diffusivity_m2_per_s={s: 0.0 if arm == "blocked" else 1e-10 for s in species},
            law="logmean_electrodiffusion@1",
        )
    ]
    level = 0.0 if arm == "blocked" else 1.0
    membrane_controls = [
        dict(membrane_id=p["id"], schedule=[dict(time=0.0, availability=level)]) for p in membranes
    ]
    removed_clock = next(
        row for row in membrane_controls if row["membrane_id"] == "membrane_1_bath"
    )
    removed_clock["schedule"].extend(
        [
            dict(time=0.000713, availability=0.0),
            dict(time=0.001237, availability=0.0 if arm == "blocked" else 0.6),
        ]
    )
    e = dict(
        end_time=250 * DT,
        observation_times=[
            0.0,
            40 * DT,
            0.000713,
            CUT_TIME,
            120 * DT,
            0.001237,
            150 * DT,
            200 * DT,
            250 * DT,
        ],
        membrane_controls=membrane_controls,
        junction_controls=[
            dict(junction_id=p["id"], schedule=[dict(time=0.0, availability=level)])
            for p in junctions
        ],
    )
    pad = int(padded)
    return dict(
        schema_version=1,
        model=dict(
            id="resolved_tissue@1",
            temperature_K=310.0,
            species=[dict(id=s, valence=v) for s, v in zip(species, z, strict=True)],
            cells=cells,
            extracellular=outside,
            membranes=membranes,
            junctions=junctions,
            faces=faces,
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1",
                gauge_reference="bath" if arm == "closed" else None,
            ),
        ),
        experiment=e,
        execution=dict(
            dt=DT,
            capacity=3 + pad,
            extracellular_capacity=2 + pad,
            membrane_capacity=len(membranes) + pad,
            edge_capacity=2 + pad,
            face_capacity=1 + pad,
            backend=backend,
            jit=True,
            precision="float64",
            solver="rk4",
            field_solver="capacitive_reduction_gauged_damped_newton@1",
            max_steps=512,
            max_trace_bytes=2**28,
            material_balance_atol_fmol={s: 2e-11 for s in species},
        ),
    )


def cut_plan(arm="open"):
    if arm not in ARMS:
        raise ValueError(arm)
    removed = (
        []
        if arm == "no-op"
        else ["cell_0", "cell_1"]
        if arm == "single-survivor"
        else ["cell_0" if arm == "disconnected" else "cell_1"]
    )
    result = [dict(time_s=CUT_TIME, removed_cell_ids=removed)]
    if arm == "sequential":
        result.append(dict(time_s=150 * DT, removed_cell_ids=["cell_0"]))
    return result
