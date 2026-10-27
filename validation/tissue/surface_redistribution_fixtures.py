"""Synthetic mobile pores; accelerated diffusion is not a biological calibration."""

ARMS = ("mobile", "immobile", "uniform", "blocked", "empty")


def definition(arm="mobile", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    ions, z = ("Na", "K", "Cl"), (1, 1, -1)
    charge = 6.02214076e23 * 1.602176634e-19 * 1e-15

    def mapped(values):
        return dict(zip(ions, values, strict=True))

    def owner(identity, volume, concentration, q, *, outside=False, reservoir=False):
        amounts = [volume * v for v in concentration]
        result = dict(
            id=identity,
            volume_pL=volume,
            initial_amount_fmol=mapped(amounts),
            initial_charge_C=q,
            fixed_charge_equivalent_fmol=q / charge
            - sum(a * v for a, v in zip(amounts, z, strict=True)),
        )
        if outside:
            result.update(reservoir=reservoir, boundary_potential_V=0.005 if reservoir else 0.0)
        return result

    model = dict(
        id="resolved_redistribution@1",
        temperature_K=298.15,
        species=[dict(id=s, valence=v) for s, v in zip(ions, z, strict=True)],
        cells=[owner("cell", 2.0, [15, 130, 145], -8.5e-14)],
        extracellular=[
            owner("finite", 4.0, [130, 8, 138], 4e-14, outside=True),
            owner("bath", 5.0, [145, 4, 149], 4.5e-14, outside=True, reservoir=True),
        ],
        membranes=[
            dict(
                id=f"patch_{i}",
                inside="cell",
                outside=outside,
                area_m2=area * 1e-12,
                capacitance_F=area * 1e-14,
                permeability_m_per_s=mapped([0, 0, 1e-9]),
                law="constant_field@1",
            )
            for i, (outside, area) in enumerate((("finite", 100), ("bath", 150)))
        ],
        junctions=[],
        faces=[],
        closure=dict(
            law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
        ),
        mobile_populations=[],
        surface_edges=[
            dict(
                id="along_cell", sender="patch_0", receiver="patch_1", width_um=2.0, distance_um=1.0
            )
        ],
    )
    for name, permeability, amounts, diffusion in (
        ("sodium_pore", [1e-8, 0, 0], [0.020, 0.005], 10000.0),
        ("potassium_pore", [0, 2e-8, 0], [0.004, 0.016], 6000.0),
    ):
        if arm == "uniform":
            total = sum(amounts)
            amounts = [total * 0.4, total * 0.6]
        if arm == "empty":
            amounts = [0.0, 0.0]
        model["mobile_populations"].append(
            dict(
                id=name,
                law="neutral_mobile_leak@1",
                reference_density_fmol_per_um2=1e-4,
                permeability_at_reference_density_m_per_s=mapped(permeability),
                initial_amount_fmol=dict(zip(("patch_0", "patch_1"), amounts, strict=True)),
                diffusivity_um2_per_s=0.0 if arm == "immobile" else diffusion,
            )
        )
    pad = int(padded)
    return dict(
        schema_version=1,
        model=model,
        experiment=dict(
            end_time=0.0004,
            observation_times=[0.0, 0.0002, 0.0004],
            membrane_controls=[
                dict(
                    membrane_id=f"patch_{i}",
                    schedule=[dict(time=0.0, availability=0.0 if arm == "blocked" else 1.0)],
                )
                for i in range(2)
            ],
            junction_controls=[],
        ),
        execution=dict(
            dt=0.0000125,
            capacity=1 + pad,
            extracellular_capacity=2 + pad,
            membrane_capacity=2 + pad,
            edge_capacity=pad,
            face_capacity=pad,
            population_capacity=2 + pad,
            surface_edge_capacity=1 + pad,
            backend=backend,
            jit=True,
            precision="float64",
            solver="rk4",
            field_solver="capacitive_reduction_gauged_damped_newton@1",
            max_steps=256,
            max_trace_bytes=2**27,
            material_balance_atol_fmol=mapped([2e-11] * 3),
        ),
    )
