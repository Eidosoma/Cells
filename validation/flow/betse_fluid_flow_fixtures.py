"""Explicit small flow fields and manufactured refinements; no array imports."""

from copy import deepcopy
from math import cos, pi, sin

from validation.mechanics.betse_deformation_fixtures import layout


def base(name="cell-and-ecm"):
    mesh = deepcopy(layout())
    n, ny, nx, h = len(mesh["centers_m"]), 4, 5, 2e-5
    return dict(
        name=name,
        layout=mesh,
        cell_ids=["cell/" + str(i * 11 + 7) for i in range(n)],
        shape=[ny, nx],
        delta_m=h,
        bounds_m=[0, nx * h, 0, ny * h],
        environment_ids=["ecm/" + str(i * 13 + 3) for i in range(ny * nx)],
        viscosity_Pa_s=0.01,
        gj_fraction=5e-8,
        epsilon_F_m=8.8541878128e-12,
        relative_permittivity=80.0,
        cell_E_V_m=[[12 + 0.7 * sin(i) for i in range(n)], [-17 + 3 * cos(i) for i in range(n)]],
        cell_rho_C_m3=[0.8 - 0.3 * i for i in range(n)],
        environment_E_V_m=[
            [[25 * sin(i + j * 0.7) for j in range(nx)] for i in range(ny)],
            [[-15 * cos(0.6 * i + j) for j in range(nx)] for i in range(ny)],
        ],
        environment_potential_V=[
            [0.03 + 0.002 * i - 0.001 * j for j in range(nx)] for i in range(ny)
        ],
        diffusion_weight=[[0.3 + 0.02 * i + 0.06 * j for j in range(nx)] for i in range(ny)],
        is_ecm=True,
        # Deliberately external and unused by getFlow; changed cases demonstrate no pressure input.
        pressure_Pa=[1.0 + 0.5 * i for i in range(n)],
        osmotic_PP_native=[1e-11 * cos(i) for i in range(n)],
    )


def cases():
    rows = [base()]
    for name, changes in (
        ("cell-only", {"is_ecm": False}),
        ("viscosity-double", {"viscosity_Pa_s": 0.02}),
        ("gap-fraction-double", {"gj_fraction": 1e-7}),
        ("gap-fraction-zero", {"gj_fraction": 0.0}),
        ("permittivity-double", {"relative_permittivity": 160.0}),
    ):
        raw = base(name)
        raw.update(changes)
        rows.append(raw)
    for name in (
        "charge-reversed",
        "electric-reversed",
        "ecm-potential-offset",
        "ecm-weight-zero",
        "pressure-changed-unused",
        "zero-electric",
        "geometry-scaled-two",
    ):
        raw = base(name)
        if name == "charge-reversed":
            raw["cell_rho_C_m3"] = [-v for v in raw["cell_rho_C_m3"]]
        elif name in ("electric-reversed", "zero-electric"):
            scale = -1 if name == "electric-reversed" else 0
            raw["cell_E_V_m"] = [[scale * v for v in axis] for axis in raw["cell_E_V_m"]]
            raw["environment_E_V_m"] = [
                [[scale * v for v in row] for row in axis] for axis in raw["environment_E_V_m"]
            ]
        elif name == "ecm-potential-offset":
            raw["environment_potential_V"] = [
                [v + 0.02 for v in row] for row in raw["environment_potential_V"]
            ]
        elif name == "ecm-weight-zero":
            raw["diffusion_weight"] = [[0.0] * raw["shape"][1] for _ in range(raw["shape"][0])]
        elif name == "pressure-changed-unused":
            raw["pressure_Pa"] = [-1e6 * v for v in raw["pressure_Pa"]]
            raw["osmotic_PP_native"] = [1e6 * v for v in raw["osmotic_PP_native"]]
        elif name == "geometry-scaled-two":
            raw["delta_m"] *= 2
            raw["bounds_m"] = [2 * v for v in raw["bounds_m"]]
            for key in ("lengths_m", "dual_edge_m", "primal_edge_m"):
                raw["layout"][key] = [2 * v for v in raw["layout"][key]]
            raw["layout"]["dual_area_m2"] = [4 * v for v in raw["layout"]["dual_area_m2"]]
        rows.append(raw)
    raw = base("two-by-three-grid")
    raw.update(
        shape=[2, 3],
        environment_ids=["tiny/" + str(i) for i in range(6)],
        bounds_m=[0, 6e-5, 0, 4e-5],
    )
    for key in ("environment_E_V_m",):
        raw[key] = [[row[:3] for row in axis[:2]] for axis in raw[key]]
    for key in ("environment_potential_V", "diffusion_weight"):
        raw[key] = [row[:3] for row in raw[key][:2]]
    rows.append(raw)
    return rows


def cell_refinement():
    rows = []
    for n in (8, 16, 32):
        raw = base("periodic-cells-" + str(n))
        raw.update(
            is_ecm=False,
            layout=deepcopy(layout(n, 1, True)),
            cell_ids=["periodic/" + str(i) for i in range(n)],
            cell_E_V_m=[[0.0] * n, [cos(2 * pi * i / n) for i in range(n)]],
            cell_rho_C_m3=[1.0] * n,
            viscosity_Pa_s=1.0,
            gj_fraction=1.0,
            pressure_Pa=[0.0] * n,
            osmotic_PP_native=[0.0] * n,
        )
        rows.append(raw)
    return rows


def environment_refinement():
    """Fixed boundary-centre domain, prescribed discrete first-solve field.

    Slip RHS is explicitly manufactured so the *first* native solve gives
    raw=(0,cos(kx)sin(ky)). The second native HH solve and derivatives are
    tested against (-sin(kx)cos(ky)/2,cos(kx)sin(ky)/2). Its native m3/s
    output is a numerical field, not a physical unit-velocity experiment.
    """
    rows = []
    for n in (5, 9, 17):
        raw, length = base("manufactured-ecm-" + str(n)), 1e-3
        h, theta = length / (n - 1), pi / (n - 1)
        u = [[cos(theta * j) * sin(theta * i) for j in range(n)] for i in range(n)]
        slip = []
        for i in range(n):
            row = []
            for j in range(n):
                lap = (
                    u[i][j] / h**2
                    if i in (0, n - 1) or j in (0, n - 1)
                    else (u[i - 1][j] + u[i + 1][j] + u[i][j - 1] + u[i][j + 1] - 4 * u[i][j])
                    / h**2
                )
                row.append(-lap)
            slip.append(row)
        raw.update(
            shape=[n, n],
            delta_m=h,
            bounds_m=[-h / 2, length + h / 2, -h / 2, length + h / 2],
            environment_ids=["manufactured/" + str(i) for i in range(n * n)],
            viscosity_Pa_s=1.0,
            epsilon_F_m=1.0,
            relative_permittivity=1.0,
            environment_potential_V=[[1.0] * n for _ in range(n)],
            diffusion_weight=[[1.0] * n for _ in range(n)],
            environment_E_V_m=[[[0.0] * n for _ in range(n)], [[-v for v in row] for row in slip]],
            manufactured_raw=[[[0.0] * n for _ in range(n)], u],
            manufactured_output=[
                [[-0.5 * sin(theta * j) * cos(theta * i) for j in range(n)] for i in range(n)],
                [[0.5 * cos(theta * j) * sin(theta * i) for j in range(n)] for i in range(n)],
            ],
        )
        rows.append(raw)
    return rows


def limitations():
    rows = []
    for name in (
        "missing-cell-inverse",
        "missing-environment-inverse",
        "zero-viscosity",
        "negative-viscosity",
        "negative-gap-fraction",
        "negative-weight",
        "bad-cell-field-axis",
        "bad-ecm-voltage-axis",
        "nan-cell-field",
        "nan-ecm-field",
        "missing-charge-owner",
    ):
        raw = base(name)
        raw["defect"] = name
        if name == "zero-viscosity":
            raw["viscosity_Pa_s"] = 0.0
        if name == "negative-viscosity":
            raw["viscosity_Pa_s"] = -0.01
        if name == "negative-gap-fraction":
            raw["gj_fraction"] = -5e-8
        if name == "negative-weight":
            raw["diffusion_weight"][1][2] = -1.0
        if name == "bad-cell-field-axis":
            raw["cell_E_V_m"] = [[0.0] * 24, [0.0] * 24]
        if name == "bad-ecm-voltage-axis":
            raw["environment_potential_V"] = [[0.0] * 3]
        rows.append(raw)
    return rows
