"""Explicit no-ECM carried states and drives; no numerical imports."""

from validation.betse.betse_fast_solver_fixtures import fixture as geometry_fixture

CASES = (
    "closed",
    "open",
    "zero_voltage_neutral",
    "temperature_split",
    "moving_reversed",
    "stationary",
    "zero_gap",
    "membrane_lag",
    "clipping",
    "bath_depletion",
    "permuted",
    "asymmetric_gap",
)


def fixture(case="closed"):
    if case not in CASES:
        raise ValueError("Require a declared no-ECM ion/material join case")
    base = geometry_fixture()["definition"]["geometry"]
    g = {
        key: base[key]
        for key in (
            "cell_ids",
            "membrane_ids",
            "owner",
            "membrane_area_m2",
            "cell_volume_m3",
            "normal_xy",
        )
    }
    g.update(
        partner=[3, 1, 8, 0, 7, 5, 6, 4, 2],
        boundary=[False, True, False, False, False, True, True, False, False],
        gap_length_m=[2.6e-8 * (1 + 0.02 * j) for j in range(9)],
        gap_weights=[1.0, 0.0, 0.7, 1.0, 0.8, 0.0, 0.0, 0.8, 0.7],
    )
    ids, valence = ["Na", "K", "Cl", "P"], [1.0, 1.0, -1.0, -1.0]
    if case == "zero_voltage_neutral":
        ids, valence = ["Na", "neutral", "Cl", "P"], [1.0, 0.0, -1.0, -1.0]
    moving = ids[:3]
    if case == "moving_reversed":
        moving = list(reversed(moving))
    if case == "stationary":
        moving = []
    ions = dict(
        ids=ids,
        valence=valence,
        moving_ids=moving,
        membrane_diffusion_m2_s=[
            [(1 + 0.1 * i + 0.02 * j) * 1e-14 for j in range(9)] for i in range(4)
        ],
        gap_diffusion_m2_s=[[(1 + 0.15 * i) * 1e-9 for _ in range(9)] for i in range(4)],
    )
    p = dict(
        F_C_mol=96485.0,
        R_J_mol_K=8.314,
        configured_temperature_K=315.0 if case == "temperature_split" else 298.15,
        membrane_thickness_m=5e-9,
        junction_surface_fraction=0.0 if case == "zero_gap" else 1e-7,
        bath_volume_m3=1.7e-14,
        cluster_open=case == "open",
        is_ecm=False,
        v_sensitive_gj=False,
    )
    cell = [[11.0 + 19 * i + 3 * j for j in range(3)] for i in range(4)]
    membrane = [[cell[i][owner] for owner in g["owner"]] for i in range(4)]
    if case in ("membrane_lag", "clipping"):
        membrane = [
            [value * (1 + 0.05 * (j - 3)) for j, value in enumerate(row)] for row in membrane
        ]
    dt = 0.002
    if case == "clipping":
        ions["gap_diffusion_m2_s"] = [[2e-2] * 9 for _ in range(4)]
        p["junction_surface_fraction"] = 1e-4
        dt = 1e-4
    bath = [40.0 + 17 * i for i in range(4)]
    if case == "bath_depletion":
        p["bath_volume_m3"] = 1e-20
        dt = 0.02
    if case == "asymmetric_gap":
        g["gap_weights"][0] = 0.23
    initial = dict(
        cell_mol_m3=cell,
        membrane_mol_m3=membrane,
        bath_mol_m3=bath,
        voltage_V=[0.0] * 9
        if case == "zero_voltage_neutral"
        else [-0.031 + 0.002 * j for j in range(9)],
        membrane_flux_mol_m2_s=[[7e-9] * 9 for _ in range(4)],
        junction_flux_mol_m2_s=[[-4e-9] * 9 for _ in range(4)],
        junction_voltage_V=[0.007] * 9,
        junction_field_V_m=[-1e4] * 9,
        junction_field_xy_V_m=[[0.3e4, -0.7e4] for _ in range(9)],
        gap_open=[0.31] * 9,
    )
    steps = [
        dict(
            dt_s=dt,
            runtime_temperature_K=281.0 + 0.1 * j if case == "temperature_split" else 298.15,
            junction_block=[0.7 + 0.03 * j] * 9,
        )
        for j in range(4)
    ]
    if case == "permuted":
        order = list(reversed(range(9)))
        inverse = {old: new for new, old in enumerate(order)}
        for key in (
            "membrane_ids",
            "owner",
            "boundary",
            "membrane_area_m2",
            "gap_length_m",
            "normal_xy",
            "gap_weights",
        ):
            g[key] = [g[key][j] for j in order]
        g["partner"] = [inverse[g["partner"][j]] for j in order]
        for key in ("membrane_diffusion_m2_s", "gap_diffusion_m2_s"):
            ions[key] = [[row[j] for j in order] for row in ions[key]]
        for key in ("membrane_mol_m3", "membrane_flux_mol_m2_s", "junction_flux_mol_m2_s"):
            initial[key] = [[row[j] for j in order] for row in initial[key]]
        for key in (
            "voltage_V",
            "junction_voltage_V",
            "junction_field_V_m",
            "junction_field_xy_V_m",
            "gap_open",
        ):
            initial[key] = [initial[key][j] for j in order]
        for step in steps:
            step["junction_block"] = [step["junction_block"][j] for j in order]
    return dict(
        definition=dict(
            kind="cells.betse_normal_ion_join_inputs@1",
            provenance=(
                "Complete explicit no-ECM state and four carried source ion/material calls; "
                "no initializer"
            ),
            geometry=g,
            ions=ions,
            parameters=p,
        ),
        initial=initial,
        steps=steps,
    )
