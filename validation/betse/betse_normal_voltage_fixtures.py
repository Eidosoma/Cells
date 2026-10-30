"""Manufactured explicit operators and three carried no-ECM voltage calls."""

from validation.betse.betse_normal_ion_join_fixtures import fixture as ion_fixture

CASES = (
    "simple",
    "polarized",
    "pol_flag_magnitude",
    "boundary_corners",
    "zero_bounds",
    "alias_map",
    "temperature_split",
    "cancellation",
    "moving_reversed",
    "area_mismatch",
    "membrane_lag",
    "zero_sigma_polarized",
)


def fixture(case="simple"):
    if case not in CASES:
        raise ValueError("Require declared normal-voltage case")
    base = ion_fixture(
        case if case in ("temperature_split", "moving_reversed", "membrane_lag") else "closed"
    )
    raw, initial = base["definition"], base["initial"]
    for j in range(3):
        initial["cell_mol_m3"][2][j] = (
            initial["cell_mol_m3"][0][j] + initial["cell_mol_m3"][1][j] - 4.0
        )
        initial["cell_mol_m3"][3][j] = 4.0
    initial["membrane_mol_m3"] = [
        [
            row[a] * (1 + 0.01 * (j - 3) if case == "membrane_lag" else 1)
            for j, a in enumerate(raw["geometry"]["owner"])
        ]
        for row in initial["cell_mol_m3"]
    ]
    g = raw["geometry"]
    surface = [
        sum(g["membrane_area_m2"][j] for j, a in enumerate(g["owner"]) if a == i) for i in range(3)
    ]
    if case == "area_mismatch":
        surface = [a * b for a, b in zip(surface, (0.8, 1.1, 1.4), strict=True)]
    current = dict(
        kind="cells.betse_normal_current_inputs@1",
        provenance="Explicit B24-to-B23 post-flux source join",
        geometry={
            key: g[key]
            for key in ("cell_ids", "membrane_ids", "owner", "membrane_area_m2", "normal_xy")
        },
        ions={key: raw["ions"][key] for key in ("ids", "valence")},
        parameters=dict(F_C_mol=raw["parameters"]["F_C_mol"], sharpness_cell=0.5),
    )
    current["geometry"]["cell_area_m2"] = surface
    delta, size = 1e-6, 12
    voltage = dict(
        kind="cells.betse_normal_voltage_inputs@1",
        provenance="Caller-owned inverse and explicit source coefficients; no initialization",
        grid=dict(
            shape=[3, 4],
            delta_m=delta,
            membrane_to_grid=[0, 0, 4, 7, 7, 11, 3, 0, 11]
            if case == "alias_map"
            else list(range(9)),
            inverse_m2=[
                [-(delta**2) * (0.2 if i == j else 0.005 / (1 + abs(i - j))) for j in range(size)]
                for i in range(size)
            ],
            operator_provenance=(
                "Manufactured raw dense lapENVinv on original ravel axes; "
                "inverse/gauge preparation not qualified"
            ),
        ),
        geometry=dict(
            diviterm_m=[1e-7, 1.1e-7, 0.9e-7], radius_m=[5e-6 * (1 + 0.03 * j) for j in range(9)]
        ),
        ions=dict(
            free_diffusion_m2_s=[0.0] * 4
            if case == "zero_sigma_polarized"
            else [1e-9, 1.1e-9, 1.3e-9, 0.0]
        ),
        parameters=dict(
            capacitance_F_m2=0.01,
            R_J_mol_K=raw["parameters"]["R_J_mol_K"],
            configured_temperature_K=raw["parameters"]["configured_temperature_K"],
            polarizability=17.0
            if case == "pol_flag_magnitude"
            else 0.4
            if case in ("polarized", "zero_sigma_polarized")
            else 0.0,
            true_cell_size_m=9e-6,
            cell_radius_m=5e-6,
        ),
    )
    drives = []
    for j, step in enumerate(base["steps"][:3]):
        if case == "zero_sigma_polarized":
            step["dt_s"] = 1e-6
        bounds = dict(R=2e-4, L=-1e-4, T=3e-4, B=-4e-4)
        if case == "zero_bounds":
            bounds = {key: 0.0 for key in bounds}
        if case == "boundary_corners":
            bounds = dict(R=7e-4, L=-9e-4, T=3e-4, B=-1e-4)
        drives.append(
            dict(
                material=step,
                boundary_V={key: value * (1 + 0.1 * j) for key, value in bounds.items()},
                extra_charge_C_m3=[-0.01 * (1 + j), 0.0, 0.02],
                extra_current_A_m2=[
                    (a - 4) * (1e-15 if case == "cancellation" else 1e-5) for a in range(9)
                ],
            )
        )
    return dict(
        ion_definition=raw,
        current_definition=current,
        voltage_definition=voltage,
        initial=initial,
        drives=drives,
        elapsed_start_s=0.07,
    )
