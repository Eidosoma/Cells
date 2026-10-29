"""Explicit manufactured layouts and clocks; no production or array imports."""

from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
from math import cos, pi, sin


def inverse(matrix):
    n = len(matrix)
    rows = [
        [Fraction(v) for v in row] + [Fraction(i == j) for j in range(n)]
        for i, row in enumerate(matrix)
    ]
    for col in range(n):
        pivot = next(i for i in range(col, n) if rows[i][col])
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [v / divisor for v in rows[col]]
        for i in range(n):
            if i != col:
                multiplier = rows[i][col]
                rows[i] = [a - multiplier * b for a, b in zip(rows[i], rows[col], strict=True)]
    return [row[n:] for row in rows]


@lru_cache
def layout(nx=3, ny=2, periodic=False):
    n, h, height = nx * ny, 1e-3 / nx if periodic else 2e-5, 1e-5
    centers = [[(i % nx) * h, (i // nx) * h] for i in range(n)]
    neighbors, directions, owners, edges = [], [], [], []
    for i in range(n):
        x, y = i % nx, i // nx
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, yy = x + dx, y + dy
            j = (
                y * nx + (xx % nx)
                if periodic and dy == 0
                else (yy * nx + xx if 0 <= xx < nx and 0 <= yy < ny else i)
            )
            neighbors.append([i, j])
            directions.append([float(dx), float(dy)])
            owners.append(i)
        if periodic:
            edges.append((i, y * nx + (x + 1) % nx))
        else:
            if x + 1 < nx:
                edges.append((i, i + 1))
            if y + 1 < ny:
                edges.append((i, i + nx))
    incidence = [[int(j == b) - int(j == a) for j in range(n)] for a, b in edges]
    gram = [
        [sum(row[i] * row[j] for row in incidence) + Fraction(1, n) for j in range(n)]
        for i in range(n)
    ]
    gram_inv = inverse(gram)
    pinv = [
        [sum((gram_inv[i][j] - Fraction(1, n)) * row[j] for j in range(n)) for row in incidence]
        for i in range(n)
    ]
    sm = [[int(owner == i) for owner in owners] for i in range(n)]
    vertices = [
        [c[0] + dx * h / 4, c[1] + dy * h / 4]
        for c in centers
        for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
    return dict(
        neighbors=neighbors,
        lengths_m=[h] * (4 * n),
        force_directions=directions,
        curl_directions=deepcopy(directions),
        sum_membranes=sm,
        incidence=incidence,
        incidence_inverse=[[float(v) for v in row] for row in pinv],
        dual_edge_m=[h] * len(edges),
        primal_edge_m=[h] * len(edges),
        dual_area_m2=[h * h] * n,
        centers_m=centers,
        vertices_m=vertices,
        membrane_area_m2=[h * height] * (4 * n),
        cell_area_m2=[4 * h * height] * n,
        cell_volume_m3=[h * h * height] * n,
        membrane_volume_m3=[h * height * 7.5e-9] * (4 * n),
        cell_height_m=height,
        spacing_m=h,
    )


def base(name="steady-pressure"):
    mesh = deepcopy(layout())
    n = len(mesh["centers_m"])
    return dict(
        name=name,
        layout=mesh,
        mode="steady",
        young_modulus_Pa=1000.0,
        galvanotropism_m2_V=1e-9,
        include_osmotic=False,
        fixed_boundary=True,
        dt_s=1e-6,
        viscous_damping_native=0.01,
        cell_radius_m=1e-5,
        clock_s=0.001,
        pressure_Pa=[1.0 + 0.2 * i + 0.3 * sin(i) for i in range(n)],
        PP_native=[2e-11 * cos(i) for i in range(n)],
        electric_field_V_m=[[10.0 + i for i in range(n)], [-20.0 + 2 * i for i in range(n)]],
        current_density_A_m2=[
            [0.02 * (i + 1) for i in range(n)],
            [-0.01 * (i + 1) for i in range(n)],
        ],
        charge_density_C_m3=[0.3 + 0.1 * i for i in range(n)],
        conductivity_S_m=[0.8] * n,
        displacement_m=[[1e-8 * sin(i) for i in range(n)], [2e-8 * cos(i) for i in range(n)]],
        previous_displacement_m=[
            [0.9e-8 * sin(i) for i in range(n)],
            [1.8e-8 * cos(i) for i in range(n)],
        ],
        compute_osmotic=False,
        is_ecm=True,
        gas_constant_J_mol_K=8.314,
        temperature_K=310.0,
        aquaporin_fraction=0.01,
        water_viscosity_Pa_s=1e-3,
        membrane_thickness_m=7.5e-9,
        density_kg_m3=1050.0,
        cell_to_environment=[i % 5 for i in range(n)],
        primary_cell_mM=[[100.0 + i for i in range(n)], [20.0 - 0.2 * i for i in range(n)]],
        primary_env_mM=[[120.0 + i for i in range(5)], [25.0 - 0.1 * i for i in range(5)]],
        molecule_cell_mM=[[0.3 + 0.02 * i for i in range(n)]],
        molecule_env_mM=[[0.5 + 0.03 * i for i in range(5)]],
        grn_cell_mM=[[0.4 + 0.01 * i for i in range(n)]],
        grn_env_mM=[[0.2 + 0.03 * i for i in range(5)]],
    )


def cases():
    result = [base()]
    for name, changes in (
        ("steady-free-flag", {"fixed_boundary": False}),
        ("steady-osmotic-addition", {"include_osmotic": True}),
        ("steady-negative-galvanotropism", {"galvanotropism_m2_V": -2e-9}),
        ("steady-no-electric", {"galvanotropism_m2_V": 0.0}),
        ("steady-soft", {"young_modulus_Pa": 100.0}),
        ("time-positive", {"mode": "time"}),
        ("time-positive-free", {"mode": "time", "fixed_boundary": False}),
        ("time-positive-osmotic", {"mode": "time", "include_osmotic": True}),
        ("time-positive-no-damping", {"mode": "time", "viscous_damping_native": 0.0}),
        ("time-positive-double-dt", {"mode": "time", "dt_s": 2e-6}),
        ("osmotic-ecm", {"compute_osmotic": True, "include_osmotic": True}),
        (
            "osmotic-membrane-average",
            {"compute_osmotic": True, "include_osmotic": True, "is_ecm": False},
        ),
        (
            "osmotic-no-aquaporin",
            {"compute_osmotic": True, "include_osmotic": True, "aquaporin_fraction": 0.0},
        ),
        ("osmotic-double-clock", {"compute_osmotic": True, "include_osmotic": True, "dt_s": 2e-6}),
    ):
        row = base(name)
        row.update(changes)
        result.append(row)
    for mode in ("steady", "time"):
        row = base(mode + "-different-force-curl-directions")
        row["mode"] = mode
        row["layout"]["force_directions"] = [
            [x + 0.1 * sin(i), y - 0.07 * cos(i)]
            for i, (x, y) in enumerate(row["layout"]["force_directions"])
        ]
        result.append(row)
    for n in (8, 16, 32):
        row = base("periodic-strip-" + str(n))
        row["layout"] = deepcopy(layout(n, 1, True))
        row.update(
            pressure_Pa=[sin(2 * pi * i / n) for i in range(n)],
            PP_native=[0.0] * n,
            electric_field_V_m=[[0.0] * n, [cos(2 * pi * i / n) for i in range(n)]],
            current_density_A_m2=[[0.0] * n, [0.0] * n],
            charge_density_C_m3=[0.0] * n,
            conductivity_S_m=[1.0] * n,
            displacement_m=[[0.0] * n, [0.0] * n],
            previous_displacement_m=[[0.0] * n, [0.0] * n],
        )
        result.append(row)
    return result


def display_cases():
    result = []
    mesh = deepcopy(layout(6, 6))
    for name, matrix, offset, calls in (
        ("display-affine-repeat", [[0.002, -0.001], [0.0007, 0.0015]], [1e-8, -2e-8], 2),
        ("display-zero", [[0.0, 0.0], [0.0, 0.0]], [0.0, 0.0], 1),
        ("display-quartic", None, None, 1),
    ):
        row = dict(
            name=name,
            layout=deepcopy(mesh),
            affine_matrix=matrix,
            affine_offset_m=offset,
            calls=calls,
        )
        if matrix is not None:
            d = [
                [sum(matrix[a][j] * c[j] for j in range(2)) + offset[a] for c in mesh["centers_m"]]
                for a in range(2)
            ]
        else:
            d = [
                [1e-8 * (c[0] / 1e-4) ** 4 * (c[1] / 1e-4) ** 3 for c in mesh["centers_m"]],
                [-2e-8 * (c[0] / 1e-4) ** 2 * (c[1] / 1e-4) ** 4 for c in mesh["centers_m"]],
            ]
        row["displacement_m"] = d
        result.append(row)
    row = deepcopy(result[1])
    row.update(
        name="display-minimum-25-centres",
        layout=deepcopy(layout(5, 5)),
        displacement_m=[[0.0] * 25, [0.0] * 25],
    )
    result.append(row)
    return result


def limitations():
    result = []
    for name, changes, failure in (
        ("disabled-time-zero-np-float", {"mode": "time", "clock_s": 0.0}, True),
        ("time-positive-missing-history", {"mode": "time", "empty_history": True}, True),
        ("time-negative-clock", {"mode": "time", "clock_s": -0.01}, False),
        ("time-zero-conductivity", {"mode": "time", "conductivity_S_m": [0.0] * 6}, True),
        ("time-negative-dt", {"mode": "time", "dt_s": -1e-6}, False),
        ("steady-missing-PP", {"include_osmotic": True, "missing_PP": True}, True),
        ("steady-unbounded-displacement", {"electric_field_V_m": [[1e12] * 6, [0.0] * 6]}, False),
        (
            "steady-nonfinite-no-check",
            {"electric_field_V_m": [[float("inf")] * 6, [0.0] * 6]},
            False,
        ),
    ):
        row = base(name)
        row.update(changes)
        row["expected_failure"] = failure
        result.append(row)
    for n, name in ((4, "display-too-few-centres"), (6, "display-collinear-centres")):
        row = display_cases()[0]
        row["name"] = name
        row["layout"] = deepcopy(layout(n, n))
        if n == 6:
            row["layout"]["centers_m"] = [[c[0] + c[1], 0.0] for c in row["layout"]["centers_m"]]
        row["displacement_m"] = [[0.0] * (n * n), [0.0] * (n * n)]
        row["display_only"] = True
        row["expected_failure"] = n == 4
        if n == 6:
            row["expected_outcomes"] = ["captured_failure", "captured_limitation"]
        result.append(row)
    return result


def compatible_modal_operators(n=8, length_m=1e-3):
    """Independent manufactured derivative mode, not a native geometry builder."""
    k = 2 * pi / length_m
    s, c = [sin(2 * pi * i / n) for i in range(n)], [cos(2 * pi * i / n) for i in range(n)]
    projector = [[2 / n * (s[i] * s[j] + c[i] * c[j]) for j in range(n)] for i in range(n)]
    derivative = [[2 * k / n * (c[i] * s[j] - s[i] * c[j]) for j in range(n)] for i in range(n)]
    zero = [[0.0] * n for _ in range(n)]
    return dict(
        gradient=derivative,
        zero=zero,
        laplacian=[[-k * k * v for v in row] for row in projector],
        inverse=[[-v / (k * k) for v in row] for row in projector],
        mode=s,
        k_per_m=k,
    )
