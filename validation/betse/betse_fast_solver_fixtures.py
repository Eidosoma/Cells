"""Small deterministic raw source definitions, no imports or numerical runs."""

CASES = (
    "no_ecm",
    "ecm",
    "temperature_split",
    "divalent",
    "cation_only",
    "anion_only",
    "zero_gap",
    "reordered",
)


def fixture(case="no_ecm", phase="SIM"):
    if case not in CASES or phase not in ("INIT", "SIM"):
        raise ValueError("Require a declared manufactured circuit case")
    owner = [0, 0, 0, 1, 1, 1, 1, 2, 2]
    neighbor = [1, 0, 2, 0, 2, 1, 1, 1, 0]
    area = [value * 1e-12 for value in (1, 3, 2, 1, 4, 3, 2, 4, 2)]
    normals = [
        [1.0, 0.0],
        [0.0, 1.0],
        [-1.0, 0.0],
        [-1.0, 0.0],
        [1.0, 0.0],
        [0.0, 1.0],
        [0.0, -1.0],
        [-1.0, 0.0],
        [1.0, 0.0],
    ]
    ids, z = (
        (["Na", "K", "Cl", "Ca"], [1.0, 1.0, -1.0, 2.0])
        if case == "divalent"
        else (["Na", "K", "Cl"], [1.0, 1.0, -1.0])
    )
    if case == "cation_only":
        ids, z = ["Na"], [1.0]
    if case == "anion_only":
        ids, z = ["Cl"], [-1.0]
    ecm = case in ("ecm", "temperature_split")
    ne = 5 if ecm else len(owner)
    ions = dict(
        ids=ids,
        valence=z,
        cell_mol_m3=[[11.0 + 19 * i + 3 * j for j in range(3)] for i in range(len(ids))],
        environment_mol_m3=[[40.0 + 17 * i + 2 * j for j in range(ne)] for i in range(len(ids))],
        free_diffusion_m2_s=[(1.0 + 0.2 * i) * 1e-9 for i in range(len(ids))],
        membrane_diffusion_m2_s=[
            [(1.0 + 0.1 * i + 0.03 * j) * 1e-18 for j in range(len(owner))] for i in range(len(ids))
        ],
    )
    g = dict(
        cell_ids=["cell-0", "cell-1", "cell-2"],
        membrane_ids=["mem-" + str(j) for j in range(len(owner))],
        owner=owner,
        neighbor=neighbor,
        membrane_area_m2=area,
        cell_area_m2=[6.1e-12, 10.2e-12, 6.3e-12],
        cell_volume_m3=[2e-15, 3e-15, 4e-15],
        normal_xy=normals,
        environment_index=[j % ne for j in range(len(owner))],
        junction_weights=[
            0.0 if a == b else 0.75 + 0.02 * (j % 3)
            for j, (a, b) in enumerate(zip(owner, neighbor, strict=True))
        ],
    )
    if case == "reordered":
        order = list(reversed(range(len(owner))))
        for key in (
            "membrane_ids",
            "owner",
            "neighbor",
            "membrane_area_m2",
            "normal_xy",
            "junction_weights",
        ):
            g[key] = [g[key][j] for j in order]
        for i in range(len(ids)):
            ions["membrane_diffusion_m2_s"][i] = [
                ions["membrane_diffusion_m2_s"][i][j] for j in order
            ]
            ions["environment_mol_m3"][i] = [ions["environment_mol_m3"][i][j] for j in order]
        g["environment_index"] = list(range(len(owner)))
    p = dict(
        R_J_mol_K=8.31446261815324,
        F_C_mol=96485.33212,
        q_C=1.602176634e-19,
        kb_J_K=1.380649e-23,
        configured_temperature_K=310.0 if case == "temperature_split" else 298.15,
        temperature_K=285.0 if case == "temperature_split" else 298.15,
        capacitance_F_m2=0.01,
        membrane_thickness_m=5e-9,
        gap_length_m=2.6e-8,
        junction_surface_fraction=0.0 if case == "zero_gap" else 1e-7,
        is_ecm=ecm,
    )
    raw = dict(
        kind="cells.betse_fast_solver_inputs@1",
        provenance=("Manufactured axes, asymmetric measures and explicit supplied voltage/current"),
        geometry=g,
        ions=ions,
        parameters=p,
    )
    calendar = dict(
        phase=phase,
        step_count=5,
        dt_s=1e-4,
        sample_stride=1.0,
        requested_duration_s=None,
        provenance="Complete original five-call equivalent-circuit comparison",
    )
    initial_drive = dict(
        extra_current_A_m2=[(j - 4) * 0.002 for j in range(len(owner))],
        junction_block=[0.8] * len(owner),
    )
    drives = [
        dict(
            extra_current_A_m2=[
                value * (1 + 0.03 * i) for value in initial_drive["extra_current_A_m2"]
            ],
            junction_block=[0.6 + 0.02 * i] * len(owner),
        )
        for i in range(5)
    ]
    return dict(
        definition=raw,
        calendar=calendar,
        initial_voltage_V=[-0.031, -0.046, -0.012],
        initial_drive=initial_drive,
        drives=drives,
    )
