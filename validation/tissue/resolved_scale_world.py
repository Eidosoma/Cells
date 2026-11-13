"""Synthetic BETSE-sized resolved_pump_tissue@1 world for scale and step studies.

Geometry is synthetic: a jittered hexagonal cluster of 225 cells in a 24 x 25
extracellular grid whose outer ring is held as reservoirs. Patches map to the
grid square under their midpoint, which leaves about 180 isolated far-field
squares as separate floating components. Coefficients follow BETSE v1.5.0's
default configuration values (temperature, Dm/tm, Do, cm, gap-junction surface
fraction and length, gate threshold/minimum, alpha_NaK and pump constants) to
give realistic stiffness; they are not fitted, and this is not BETSE's
geometry. P is carried as a zero-transport species, as in BETSE's basic
profile. Every compartment starts electroneutral, so all charges are zero.
"""

import math

import numpy as np

SPECIES = (("Na", 1), ("K", 1), ("P", -1), ("M", -1))
CELL_mM = (12.0, 139.0, 135.0, 16.0)
ENV_mM = (145.0, 5.0, 10.0, 140.0)
FREE_D_m2_s = (1.33e-9, 1.96e-9, 0.0, 1.0e-9)
MEMBRANE_D_m2_s = (2.0e-18, 1.0e-18, 0.0, 1.0e-18)
MEMBRANE_THICKNESS_m = 7.5e-9
CAPACITANCE_F_m2 = 0.05
GJ_SURFACE_FRACTION = 5.0e-8
GJ_LENGTH_m = 26.0e-9
GJ_THRESHOLD_V = 0.015
GJ_MINIMUM = 0.10
ALPHA_NAK_mol_m2_s = 1.0e-7
TEMPERATURE_K = 310.0


def geometry(seed=0, rows=24, cols=25, delta=7.351931307678047e-6, height=1.0e-5, cells=225):
    """Index arrays and sizes; deterministic for a seed."""
    rng = np.random.default_rng(seed)
    spacing = 9.25e-6
    centre = np.array([cols * delta / 2, rows * delta / 2])
    points = np.array(
        [
            ((i + 0.5 * (j % 2)) * spacing, j * spacing * math.sqrt(3) / 2)
            for j in range(-14, 15)
            for i in range(-14, 15)
        ]
    )
    points = points[np.argsort(np.hypot(*points.T), kind="stable")[:cells]] + centre
    points += rng.normal(scale=0.03 * spacing, size=points.shape)
    distance = np.hypot(*(points[:, None] - points[None]).transpose(2, 0, 1))
    near = (distance < 1.3 * spacing) & ~np.eye(cells, dtype=bool)
    pairs = np.argwhere(np.triu(near))
    owner, midpoint = [], []
    for i in range(cells):
        for j in np.flatnonzero(near[i]):
            owner.append(i)
            midpoint.append(0.5 * (points[i] + points[j]))
        if near[i].sum() < 6:  # One outward boundary patch per edge cell.
            out = points[i] - centre
            owner.append(i)
            midpoint.append(points[i] + 0.5 * spacing * out / np.hypot(*out))
    midpoint = np.asarray(midpoint)
    row = np.clip((midpoint[:, 1] // delta).astype(int), 0, rows - 1)
    col = np.clip((midpoint[:, 0] // delta).astype(int), 0, cols - 1)
    grid = np.arange(rows * cols).reshape(rows, cols)
    ring = np.zeros((rows, cols), dtype=bool)
    ring[[0, -1], :] = ring[:, [0, -1]] = True
    return dict(
        cells=cells,
        squares=rows * cols,
        pairs=pairs,
        owner=np.asarray(owner),
        square=grid[row, col],
        face_sender=np.r_[grid[:, :-1].ravel(), grid[:-1, :].ravel()],
        face_receiver=np.r_[grid[:, 1:].ravel(), grid[1:, :].ravel()],
        ring=ring.ravel(),
        delta=delta,
        height=height,
        patch_area=spacing / math.sqrt(3) * height,
        cell_volume_pL=math.sqrt(3) / 2 * spacing**2 * height * 1e15,
        square_volume_pL=delta**2 * height * 1e15,
    )


def definition(
    *,
    dt=1e-3,
    end_time=0.01,
    observation_times=None,
    solver="imex_ars222_face_electromigration@1",
    backend="cpu",
    seed=0,
    max_trace_bytes=2**34,
    field_solver="capacitive_reduction_gauged_damped_newton@2",
):
    """The scale world's definition. field_solver: the declared field solver; the default
    is the version every definition made before D147 declares (drivers choose by D147 with
    validation/tissue/field_solver_choice.py)."""
    g = geometry(seed)
    ids = [s for s, _ in SPECIES]

    def mapped(values):
        return dict(zip(ids, values, strict=True))

    def owner(prefix, i, volume, mM, **extra):
        return dict(
            id=f"{prefix}_{i}",
            volume_pL=volume,
            initial_amount_fmol=mapped([c * volume for c in mM]),
            fixed_charge_equivalent_fmol=0.0,
            initial_charge_C=0.0,
            **extra,
        )

    area = g["patch_area"]
    membranes = []
    for k, (i, square) in enumerate(zip(g["owner"], g["square"], strict=True)):
        membranes.append(
            dict(
                id=f"membrane_{k}",
                inside=f"cell_{i}",
                outside=f"ecm_{square}",
                area_m2=area,
                capacitance_F=CAPACITANCE_F_m2 * area,
                permeability_m_per_s=mapped([d / MEMBRANE_THICKNESS_m for d in MEMBRANE_D_m2_s]),
                law="constant_field@1",
                pump=dict(
                    id=f"pump_{k}",
                    law="nak_atp_mass_action_positive@1",
                    roles=dict(sodium="Na", potassium="K"),
                    stoichiometry=dict(Na=-3, K=2),
                    capacity_fmol_per_s=ALPHA_NAK_mol_m2_s * area * 1e15,
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
                ),
            )
        )
    junctions = [
        dict(
            id=f"junction_{k}",
            sender=f"cell_{a}",
            receiver=f"cell_{b}",
            area_m2=area,
            permeability_m_per_s=mapped(
                [d * GJ_SURFACE_FRACTION / GJ_LENGTH_m for d in FREE_D_m2_s]
            ),
            law="constant_field@1",
            gate=dict(
                law="junction_voltage_relaxation@1",
                threshold_voltage_V=GJ_THRESHOLD_V,
                minimum_open_fraction=GJ_MINIMUM,
                initial_gate=1.0,
            ),
        )
        for k, (a, b) in enumerate(g["pairs"])
    ]
    face_area = g["height"] * g["delta"]
    faces = [
        dict(
            id=f"face_{k}",
            sender=f"ecm_{a}",
            receiver=f"ecm_{b}",
            area_m2=face_area,
            length_m=g["delta"],
            diffusivity_m2_per_s=mapped(FREE_D_m2_s),
            law="logmean_electrodiffusion@1",
        )
        for k, (a, b) in enumerate(zip(g["face_sender"], g["face_receiver"], strict=True))
    ]
    model = dict(
        id="resolved_pump_tissue@1",
        temperature_K=TEMPERATURE_K,
        species=[dict(id=s, valence=z) for s, z in SPECIES],
        cells=[owner("cell", i, g["cell_volume_pL"], CELL_mM) for i in range(g["cells"])],
        extracellular=[
            owner(
                "ecm",
                k,
                g["square_volume_pL"],
                ENV_mM,
                reservoir=bool(g["ring"][k]),
                boundary_potential_V=0.0,
            )
            for k in range(g["squares"])
        ],
        membranes=membranes,
        junctions=junctions,
        faces=faces,
        closure=dict(
            law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
        ),
    )
    times = [0.0, end_time] if observation_times is None else list(observation_times)
    experiment = dict(
        end_time=end_time,
        observation_times=times,
        membrane_controls=[
            dict(membrane_id=p["id"], schedule=[dict(time=0.0, availability=1.0)])
            for p in membranes
        ],
        junction_controls=[
            dict(junction_id=p["id"], schedule=[dict(time=0.0, availability=1.0)])
            for p in junctions
        ],
        pump_controls=[
            dict(pump_id=p["pump"]["id"], schedule=[dict(time=0.0, availability=1.0)])
            for p in membranes
        ],
    )
    execution = dict(
        dt=dt,
        capacity=g["cells"],
        extracellular_capacity=g["squares"],
        membrane_capacity=len(membranes),
        edge_capacity=len(junctions),
        face_capacity=len(faces),
        backend=backend,
        jit=True,
        precision="float64",
        solver=solver,
        field_solver=field_solver,
        max_steps=int(math.ceil(end_time / dt)) + 8,
        max_trace_bytes=max_trace_bytes,
        material_balance_atol_fmol=mapped([1e-10] * len(ids)),
    )
    return dict(schema_version=1, model=model, experiment=experiment, execution=execution)
