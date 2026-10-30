"""Stable manufactured ECM material histories and explicit external seams."""

from copy import deepcopy

from validation.betse.betse_environment_field_fixtures import fixture as field_fixture

CASES = (
    "slow",
    "fast_duplicate",
    "fast_equal_flux",
    "open",
    "flow",
    "smoothed",
    "temperature_split",
    "moving_reversed",
    "stationary",
    "stationary_pump_role",
    "neutral_nonce",
    "zero_transport",
    "signed_environment",
    "bulk_clipping",
    "membrane_lag",
    "rectangular",
    "permuted",
)
LOW_INVENTORY_CASE = "low_inventory_signed_environment"


def fixture(case="slow"):
    if case not in (*CASES, LOW_INVENTORY_CASE):
        raise ValueError("Require a declared bounded ECM material case")
    base_case = (
        "duplicate"
        if case == "fast_duplicate"
        else "rectangular"
        if case == "rectangular"
        else "standard"
    )
    original = field_fixture(base_case)
    geometry = original["definition"]
    cg = geometry["current_definition"]["geometry"]
    ids = ["Na", "neutral" if case == "neutral_nonce" else "K", "Cl", "P"]
    valence = [1.0, 0.0 if case == "neutral_nonce" else 1.0, -1.0, -1.0]
    geometry["current_definition"]["ions"] = dict(ids=ids, valence=valence)
    n, m, e = 3, 9, 12 if case == "rectangular" else 9
    ny, nx = (4, 3) if case == "rectangular" else (3, 3)
    cell = [[11.0 + 7 * i + 2 * j for j in range(n)] for i in range(4)]
    env = [[20.0 + 3 * i + (k % 5) for k in range(e)] for i in range(4)]
    geometry["cache_initial_state"] = dict(
        cell_mol_m3=deepcopy(cell), environment_mol_m3=deepcopy(env), free_diffusion_m2_s=[1e-9] * 4
    )
    geometry["parameters"]["configured_temperature_K"] = (
        315.0 if case == "temperature_split" else 298.15
    )
    jg = dict(
        partner=[3, 1, 8, 0, 7, 5, 6, 4, 2],
        boundary=[False, True, False, False, False, True, True, False, False],
        gap_length_m=[0.8 + 0.02 * j for j in range(m)],
        gap_weights=[1.0, 0.0, 0.7, 1.0, 0.8, 0.0, 0.0, 0.8, 0.7],
    )
    moving = ids[:3]
    if case == "stationary":
        moving = []
    elif case == "stationary_pump_role":
        moving = ids[1:3]
    elif case == "moving_reversed":
        moving = list(reversed(moving))
    ions = dict(
        moving_ids=moving,
        membrane_diffusion_m2_s=[
            [(1 + 0.1 * i + 0.02 * j) * 1e-5 for j in range(m)] for i in range(4)
        ],
        gap_diffusion_m2_s=[[(1 + 0.15 * i) * 1e-4] * m for i in range(4)],
        environment_diffusion_m2_s=[
            [(1 + 0.1 * i + 0.03 * k) * 1e-3 for k in range(e)] for i in range(4)
        ],
        tight_junction_modulator=[[0.5 + 0.05 * ((i + k) % 5) for k in range(e)] for i in range(4)],
    )
    p = dict(
        R_J_mol_K=8.314,
        membrane_thickness_m=1.0,
        gap_surface_fraction=0.1,
        cluster_open=case in ("open", "fast_equal_flux"),
        fast_update_ecm=case.startswith("fast"),
        sharpness=0.4 if case == "smoothed" else 1.0,
        fluid_flow=case == "flow",
        v_sensitive_gj=False,
    )
    membrane = [[row[owner] for owner in cg["owner"]] for row in cell]
    if case == "membrane_lag":
        membrane = [[v * (1 + 0.03 * (j - 4)) for j, v in enumerate(row)] for row in membrane]
    if case in ("fast_equal_flux", "zero_transport"):
        ions["membrane_diffusion_m2_s"] = [[0.0] * m for _ in range(4)]
        ions["gap_diffusion_m2_s"] = [[0.0] * m for _ in range(4)]
    if case == "zero_transport":
        ions["environment_diffusion_m2_s"] = [[0.0] * e for _ in range(4)]
        env = [[23.0 + 3 * i] * e for i in range(4)]
    if case == LOW_INVENTORY_CASE:
        env = [[1e-4] * e for _ in range(4)]
    initial = dict(
        cell_mol_m3=cell,
        membrane_mol_m3=membrane,
        environment_mol_m3=env,
        voltage_V=[0.0] * m if case == "neutral_nonce" else [-0.03 + 0.004 * j for j in range(m)],
        membrane_flux_mol_m2_s=[[7e-7] * m for _ in range(4)],
        junction_flux_mol_m2_s=[[-4e-7] * m for _ in range(4)],
        environment_flux_x_mol_m2_s=[[3e-6] * e for _ in range(4)],
        environment_flux_y_mol_m2_s=[[-2e-6] * e for _ in range(4)],
        junction_voltage_V=[0.007] * m,
        junction_field_source=[-0.02] * m,
        junction_field_xy_source=[[0.01, -0.02] for _ in range(m)],
        gap_open=[0.31] * m,
    )
    steps = []
    for tick in range(
        1 if case in ("signed_environment", "bulk_clipping", LOW_INVENTORY_CASE) else 3
    ):
        pump = [[(i + 1) * (j - 3) * 2e-7 for j in range(m)] for i in range(4)]
        late = [[(i - 2) * (4 - j) * 3e-8 for j in range(m)] for i in range(4)]
        if case == "fast_equal_flux":
            pump, late = [[(i + 1) * 1e-3] * m for i in range(4)], [[0.0] * m for _ in range(4)]
        if case == "zero_transport":
            pump = late = [[0.0] * m for _ in range(4)]
        if case == LOW_INVENTORY_CASE:
            pump = [[10.0] * m for _ in range(4)]
        if case == "signed_environment":
            pump = [[5e5] * m for _ in range(4)]
        if case == "bulk_clipping":
            pump = [[-1e4] * m for _ in range(4)]
        if not p["cluster_open"]:
            for row in pump + late:
                for face, boundary in enumerate(jg["boundary"]):
                    if boundary:
                        row[face] = 0.0
        steps.append(
            dict(
                dt_s=0.001,
                runtime_temperature_K=281.0 + tick if case == "temperature_split" else 298.15,
                junction_block=[0.7 + 0.03 * tick] * m,
                channel_multiplier=[0.8 + 0.02 * j for j in range(m)],
                supplied_pump_membrane_flux_mol_m2_s=pump,
                supplied_late_membrane_flux_mol_m2_s=late,
                electric_x_source=[[(j - 1) * 0.001 for j in range(nx)] for _ in range(ny)],
                electric_y_source=[[(i - 1) * -0.001] * nx for i in range(ny)],
                velocity_x_m_s=[[(j - 1) * 1e-4 for j in range(nx)] for _ in range(ny)],
                velocity_y_m_s=[[(i - 1) * 2e-4] * nx for i in range(ny)],
                boundary_mol_m3=[1e-4] * 4
                if case == LOW_INVENTORY_CASE
                else [23.0 + 3 * i + 0.05 * tick for i in range(4)],
            )
        )
    if case == "permuted":
        order = list(reversed(range(m)))
        inv = {old: new for new, old in enumerate(order)}
        for key in ("membrane_ids", "owner", "membrane_area_m2", "normal_xy"):
            cg[key] = [cg[key][j] for j in order]
        geometry["geometry"]["membrane_midpoints_m"] = [
            geometry["geometry"]["membrane_midpoints_m"][j] for j in order
        ]
        for key in ("boundary", "gap_length_m", "gap_weights"):
            jg[key] = [jg[key][j] for j in order]
        jg["partner"] = [inv[jg["partner"][j]] for j in order]
        for key in ("membrane_diffusion_m2_s", "gap_diffusion_m2_s"):
            ions[key] = [[row[j] for j in order] for row in ions[key]]
        for key in ("membrane_mol_m3", "membrane_flux_mol_m2_s", "junction_flux_mol_m2_s"):
            initial[key] = [[row[j] for j in order] for row in initial[key]]
        for key in (
            "voltage_V",
            "junction_voltage_V",
            "junction_field_source",
            "junction_field_xy_source",
            "gap_open",
        ):
            initial[key] = [initial[key][j] for j in order]
        for packet in steps:
            for key in ("junction_block", "channel_multiplier"):
                packet[key] = [packet[key][j] for j in order]
            for key in (
                "supplied_pump_membrane_flux_mol_m2_s",
                "supplied_late_membrane_flux_mol_m2_s",
            ):
                packet[key] = [[row[j] for j in order] for row in packet[key]]
    return dict(
        definition=dict(
            kind="cells.betse_ecm_transport_inputs@1",
            provenance=(
                "Stable manufactured ECM source chronology, explicit post-mask pump/late "
                "flux and held fields; no handlers or Voronoi initialization"
            ),
            environment_geometry_definition=geometry,
            junction_geometry=jg,
            ions=ions,
            parameters=p,
        ),
        initial=initial,
        steps=steps,
    )
