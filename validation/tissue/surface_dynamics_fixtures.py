"""Synthetic resolved tissue trajectories; no fitted or measured biological parameters."""

import math

import numpy as np

from validation.tissue import surface_field_fixtures

ARMS = ("open", "closed", "clamped", "release")


def definition(arm="open", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    row = surface_field_fixtures.definition("anchored" if arm in ("clamped", "release") else arm)
    p = row["layout"]
    ids, valence = ("Na", "K", "Cl"), (1, 1, -1)
    f = 6.02214076e23 * 1.602176634e-19 * 1e-15

    def mapped(v):
        return dict(zip(ids, v, strict=True))

    model = dict(
        id="resolved_tissue@1",
        temperature_K=p["temperature"],
        species=[dict(id=s, valence=z) for s, z in zip(ids, valence, strict=True)],
    )
    for key, concentration, charges, volumes, prefix in (
        ("cells", row["ci"], row["cell_charge_C"], [2.0, 3.0], "cell"),
        ("extracellular", row["co"], row["outside_charge_C"], [4.0, 4.5, 5.0, 5.5, 7.0], "outside"),
    ):
        owners = []
        for i, (q, volume) in enumerate(zip(charges, volumes, strict=True)):
            amounts = [c[i] * volume for c in concentration]
            c = dict(
                id=f"{prefix}_{i}",
                volume_pL=volume,
                initial_amount_fmol=mapped(amounts),
                fixed_charge_equivalent_fmol=q / f
                - math.fsum(z * a for z, a in zip(valence, amounts, strict=True)),
                initial_charge_C=q,
            )
            if key == "extracellular":
                c.update(reservoir=p["reservoir"][i], boundary_potential_V=row["boundary_V"][i])
            owners.append(c)
        model[key] = owners
    model["membranes"] = [
        dict(
            id=f"membrane_{k}",
            inside=f"cell_{p['membrane_cell'][k]}",
            outside=f"outside_{p['membrane_outside'][k]}",
            area_m2=p["membrane_area"][k],
            capacitance_F=p["membrane_capacitance"][k],
            permeability_m_per_s=mapped([r[k] for r in p["membrane_permeability"]]),
            law="constant_field@1",
        )
        for k in range(4)
    ]
    model["junctions"] = [
        dict(
            id="junction_0",
            sender="cell_0",
            receiver="cell_1",
            area_m2=p["junction_area"][0],
            permeability_m_per_s=mapped([r[0] for r in p["junction_permeability"]]),
            law="constant_field@1",
        )
    ]
    model["faces"] = [
        dict(
            id=f"face_{k}",
            sender=f"outside_{i}",
            receiver=f"outside_{j}",
            area_m2=1e-10,
            length_m=1e-5,
            diffusivity_m2_per_s=mapped([r[k] * 1e-5 / 1e-10 for r in p["face_factor"]]),
            law="logmean_electrodiffusion@1",
        )
        for k, (i, j) in enumerate(zip(p["face_sender"], p["face_receiver"], strict=True))
    ]
    model["closure"] = dict(
        law="resolved_capacitor_components_current_continuity@1",
        gauge_reference="outside_4" if arm == "closed" else None,
    )
    experiment = dict(
        end_time=0.002,
        observation_times=[0.0, 0.001, 0.002],
        membrane_controls=[
            dict(membrane_id=f"membrane_{k}", schedule=[dict(time=0.0, availability=a)])
            for k, a in enumerate(row["membrane_open"])
        ],
        junction_controls=[
            dict(
                junction_id="junction_0",
                schedule=[dict(time=0.0, availability=row["junction_open"][0])],
            )
        ],
    )
    if arm == "release":
        experiment["junction_controls"][0]["schedule"] = [
            dict(time=0.0, availability=0.0),
            dict(time=0.00073, availability=0.6),
        ]
        experiment["membrane_controls"][1]["schedule"].append(dict(time=0.001, availability=0.0))
        experiment["observation_times"].insert(1, 0.00073)
    pad = int(padded)
    return dict(
        schema_version=1,
        model=model,
        experiment=experiment,
        execution=dict(
            dt=0.0001,
            capacity=2 + pad,
            extracellular_capacity=5 + pad,
            membrane_capacity=4 + pad,
            edge_capacity=1 + pad,
            face_capacity=5 + pad,
            backend=backend,
            jit=True,
            precision="float64",
            solver="rk4",
            field_solver="capacitive_reduction_gauged_damped_newton@1",
            max_steps=256,
            max_trace_bytes=2**29,
            material_balance_atol_fmol=mapped([2e-11] * 3),
        ),
    )


def component_input(raw, state=None, time=0.0):
    """Independent serialized conversion is implemented by the reference module."""
    from validation.tissue.surface_dynamics_reference import bind, initial, stage

    c = bind(raw)
    return stage(c, initial(c) if state is None else np.asarray(state), time)
