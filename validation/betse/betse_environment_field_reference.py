"""Independent small-grid Decimal operators, Gaussian kernels and source fields.

No NumPy/SciPy/Cells/BETSE imports. Neumann gauge uses an explicit constant-mode
projection; neither inverse nor prepared geometry is accepted from production.
"""

from decimal import Decimal, localcontext
from fractions import Fraction
from functools import lru_cache

from validation.betse.betse_normal_current_reference import evaluate as current_reference


def d(value):
    return Decimal.from_float(float(value))


def serial(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: serial(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [serial(item) for item in value]
    return value


def _zeros(ny, nx):
    return [[Decimal(0) for _ in range(nx)] for _ in range(ny)]


def _flatten(a):
    return [value for row in a for value in row]


def _reshape(a, shape):
    return [list(a[i * shape[1] : (i + 1) * shape[1]]) for i in range(shape[0])]


def _mv(matrix, vector):
    return [sum(a * b for a, b in zip(row, vector, strict=True)) for row in matrix]


def _inverse(matrix):
    n = len(matrix)
    a = [row[:] + [Decimal(i == j) for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        if a[pivot][col] == 0:
            raise ValueError("Independent operator is singular")
        a[col], a[pivot] = a[pivot], a[col]
        denominator = a[col][col]
        a[col] = [value / denominator for value in a[col]]
        for row in range(n):
            if row != col and a[row][col] != 0:
                factor = a[row][col]
                a[row] = [x - factor * y for x, y in zip(a[row], a[col], strict=True)]
    return [row[n:] for row in a]


@lru_cache(maxsize=32)
def _operators(ny, nx, delta_float, precision):
    with localcontext() as context:
        context.prec = precision
        n, delta = ny * nx, d(delta_float)
        value, flux = _zeros(n, n), _zeros(n, n)
        for i in range(ny):
            for j in range(nx):
                k = i * nx + j
                adjacent = [
                    r * nx + c
                    for r, c in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1))
                    if 0 <= r < ny and 0 <= c < nx
                ]
                flux[k][k] = Decimal(-len(adjacent))
                for other in adjacent:
                    flux[k][other] = Decimal(1)
                if i in (0, ny - 1) or j in (0, nx - 1):
                    value[k][k] = Decimal(1)
                else:
                    value[k] = flux[k][:]
        inverse_value = _inverse(value)
        constant = Decimal(1) / n
        shifted = [[entry + constant for entry in row] for row in flux]
        inverse_shifted = _inverse(shifted)
        inverse_flux = [[entry - constant for entry in row] for row in inverse_shifted]
        return tuple(
            [[entry / delta**2 for entry in row] for row in matrix]
            if index < 2
            else [[entry * delta**2 for entry in row] for row in matrix]
            for index, matrix in enumerate((value, flux, inverse_value, inverse_flux))
        )


def geometry(raw, *, precision):
    world, supplied = raw["world"], raw["geometry"]
    g = raw["current_definition"]["geometry"]
    # Independent rational arithmetic with explicit binary64 source store seams
    # before int(span/delta), retaining native coordinate-count truncation.
    sx = float(Fraction(world["xmax_m"]) - Fraction(world["xmin_m"]))
    sy = float(Fraction(world["ymax_m"]) - Fraction(world["ymin_m"]))
    step = float(Fraction(sx) / world["grid_size"])
    nx, ny = int(float(Fraction(sx) / Fraction(step))), int(float(Fraction(sy) / Fraction(step)))
    delta = d(step)
    if min(nx, ny) < 2 or nx * ny > 49:
        raise ValueError("Independent source grid is outside the bounded domain")
    xv = [d(world["xmin_m"]) + Decimal(j) * d(sx) / nx for j in range(nx + 1)]
    yv = [d(world["ymin_m"]) + Decimal(i) * d(sy) / ny for i in range(ny + 1)]
    x = [[(xv[j] + xv[j + 1]) / 2 for j in range(nx)] for _ in range(ny)]
    y = [[(yv[i] + yv[i + 1]) / 2 for _ in range(nx)] for i in range(ny)]
    points = [[x[i][j], y[i][j]] for i in range(ny) for j in range(nx)]

    def nearest(queries):
        answer = []
        for query in queries:
            distances = [
                sum((d(a) - b) ** 2 for a, b in zip(query, point, strict=True)) for point in points
            ]
            order = sorted(range(len(points)), key=lambda k: distances[k])
            first, second = distances[order[0]].sqrt(), distances[order[1]].sqrt()
            if second - first <= Decimal(64) * d(2**-52) * max(second, delta):
                raise ValueError("Independent nearest map is ambiguous under declared admission")
            answer.append(order[0])
        return answer

    cell_map, membrane_map = (
        nearest(supplied["cell_centres_m"]),
        nearest(supplied["membrane_midpoints_m"]),
    )
    n, m = nx * ny, len(membrane_map)
    area, counts = [Decimal(0)] * n, [Decimal(0)] * n
    divmap = _zeros(n, m)
    for face, site in enumerate(membrane_map):
        area[site] += d(g["membrane_area_m2"][face])
        counts[site] += 1
        divmap[site][face] += d(g["membrane_area_m2"][face])
    p = raw["parameters"]
    volume = [
        value * d(p["cell_space_m"]) / 2 if count else d(p["cell_height_m"]) * delta**2
        for value, count in zip(area, counts, strict=True)
    ]
    correction = [
        (d(supplied["cell_volume_m3"][i]) / volume[k])
        * (4 * delta * d(p["cell_height_m"]) / d(g["cell_area_m2"][i]))
        for i, k in enumerate(cell_map)
    ]
    ad, an, invd, invn = _operators(ny, nx, step, precision)
    return dict(
        shape=(ny, nx),
        delta_m=delta,
        X_m=x,
        Y_m=y,
        grid_points_m=points,
        index_ij=[[i, j] for i in range(ny) for j in range(nx)],
        cell_to_grid=cell_map,
        membrane_to_grid=membrane_map,
        membrane_area_per_site_m2=area,
        membranes_per_site=counts,
        true_environment_volume_m3=volume,
        membrane_divergence_map_m2=divmap,
        cell_to_environment_correction=correction,
        dirichlet_laplacian_per_m2=ad,
        dirichlet_inverse_m2=invd,
        neumann_laplacian_per_m2=an,
        neumann_inverse_m2=invn,
    )


def _cache(raw):
    p, initial = raw["parameters"], raw["cache_initial_state"]
    z = [d(value) for value in raw["current_definition"]["ions"]["valence"]]
    f = d(raw["current_definition"]["parameters"]["F_C_mol"])
    ci, co = initial["cell_mol_m3"], initial["environment_mol_m3"]
    sigma = sum(
        sum(
            zz**2
            * d(p["q_C"])
            * f
            * d(ci[i][j])
            * d(initial["free_diffusion_m2_s"][i])
            / (d(p["kb_J_K"]) * d(p["configured_temperature_K"]))
            for i, zz in enumerate(z)
        )
        for j in range(len(ci[0]))
    ) / len(ci[0])
    ko = sum(
        sum(
            d(p["NAv_per_mol"])
            * d(p["q_C"]) ** 2
            * zz**2
            * d(co[i][k])
            / (
                d(p["relative_permittivity"])
                * d(p["vacuum_permittivity_F_m"])
                * d(p["kb_J_K"])
                * d(p["configured_temperature_K"])
            )
            for i, zz in enumerate(z)
        ).sqrt()
        for k in range(len(co[0]))
    ) / len(co[0])
    return dict(sigma_S_m=sigma, ko_environment_per_m=ko)


def _derivative(field, delta, *, source_boundary):
    ny, nx = len(field), len(field[0])
    dx, dy = _zeros(ny, nx), _zeros(ny, nx)
    for i in range(ny):
        for j in range(nx):
            dx[i][j] = (
                (field[i][j + 1] - field[i][j - 1]) / (2 * delta)
                if 0 < j < nx - 1
                else (field[i][1] - field[i][0]) / delta
                if j == 0
                else (field[i][-1] - field[i][-2]) / delta
            )
            dy[i][j] = (
                (field[i + 1][j] - field[i - 1][j]) / (2 * delta)
                if 0 < i < ny - 1
                else (field[1][j] - field[0][j]) / delta
                if i == 0
                else (field[-1][j] - field[-2][j]) / delta
            )
            if source_boundary:
                if j in (0, nx - 1):
                    dx[i][j] = -dx[i][j]
                if i in (0, ny - 1):
                    dy[i][j] = -dy[i][j]
    return dx, dy


def _combine(a, b, first=1, second=1):
    return [
        [first * x + second * y for x, y in zip(row, other, strict=True)]
        for row, other in zip(a, b, strict=True)
    ]


def _hodge(x, y, g, boundary=None):
    shape, delta, inverse = g["shape"], g["delta_m"], g["dirichlet_inverse_m2"]
    ny, nx = shape
    rotated_x, rotated_y = [[-v for v in row] for row in y], [row[:] for row in x]
    dx, _ = _derivative(rotated_x, delta, source_boundary=True)
    _, dy = _derivative(rotated_y, delta, source_boundary=True)
    dr = _combine(dx, dy)
    for i in range(ny):
        for j in range(nx):
            if i in (0, ny - 1) or j in (0, nx - 1):
                dr[i][j] = Decimal(0)
    aa = _mv(inverse, [-value for value in _flatten(dr)])
    ax, ay = _derivative(_reshape(aa, shape), delta, source_boundary=False)
    dx, _ = _derivative(x, delta, source_boundary=True)
    _, dy = _derivative(y, delta, source_boundary=True)
    divergence = _combine(dx, dy)
    b = dict.fromkeys(("L", "R", "B", "T"), Decimal(0)) if boundary is None else boundary
    for i in range(ny):
        divergence[i][0], divergence[i][-1] = -b["L"] / delta**2, -b["R"] / delta**2
    for j in range(nx):
        divergence[0][j], divergence[-1][j] = -b["B"] / delta**2, -b["T"] / delta**2
    bb = _mv(inverse, _flatten(divergence))
    gx, gy = _derivative(_reshape(bb, shape), delta, source_boundary=False)
    return dict(
        input_x=x,
        input_y=y,
        rotated_x=rotated_x,
        rotated_y=rotated_y,
        rotated_divergence=dr,
        AA=aa,
        solenoidal_x=[[-v for v in row] for row in ay],
        solenoidal_y=ax,
        divergence=divergence,
        BB=bb,
        gradient_x=gx,
        gradient_y=gy,
    )


def _gaussian(field, *, constant):
    ny, nx = len(field), len(field[0])
    weights = [(-Decimal(offset**2) / 2).exp() for offset in range(-4, 5)]
    total = sum(weights)
    weights = [value / total for value in weights]
    result = [row[:] for row in field]
    for axis, size in ((0, ny), (1, nx)):
        output = _zeros(ny, nx)
        for i in range(ny):
            for j in range(nx):
                for offset, weight in zip(range(-4, 5), weights, strict=True):
                    position = (i if axis == 0 else j) + offset
                    if not 0 <= position < size:
                        if constant:
                            continue
                        position %= 2 * size
                        position = position if position < size else 2 * size - position - 1
                    output[i][j] += (
                        weight * result[position if axis == 0 else i][position if axis == 1 else j]
                    )
        result = output
    return result


def _fields(raw, packet, g, cache):
    shape, delta = g["shape"], g["delta_m"]
    ny, nx = shape
    n = ny * nx
    mapping = g["membrane_to_grid"]
    current_geometry = raw["current_definition"]["geometry"]
    p = raw["parameters"]
    boundary = {key: d(value) for key, value in packet["boundary_V"].items()}
    rhs = _zeros(ny, nx)
    for i in range(ny):
        rhs[i][-1], rhs[i][0] = -boundary["R"] / delta**2, -boundary["L"] / delta**2
    for j in range(nx):
        rhs[-1][j], rhs[0][j] = -boundary["T"] / delta**2, -boundary["B"] / delta**2
    phi = _mv(g["dirichlet_inverse_m2"], [-v for v in _flatten(rhs)])
    local = local_smoothed = surface = surface_voltage = charge = screened = screen = None
    smoothing = None
    if raw["is_ecm"]:
        z = raw["current_definition"]["ions"]["valence"]
        f = d(raw["current_definition"]["parameters"]["F_C_mol"])
        jx = _reshape(
            [
                sum(d(zz) * f * d(packet["environment_flux_x"][i][k]) for i, zz in enumerate(z))
                + d(packet["extra_environment_current_xy"][k][0])
                for k in range(n)
            ],
            shape,
        )
        jy = _reshape(
            [
                sum(d(zz) * f * d(packet["environment_flux_y"][i][k]) for i, zz in enumerate(z))
                + d(packet["extra_environment_current_xy"][k][1])
                for k in range(n)
            ],
            shape,
        )
        hodge = _hodge(jx, jy, g, boundary)
        charge = [
            sum(d(zz) * f * d(packet["environment_mol_m3"][i][k]) for i, zz in enumerate(z))
            + d(packet["extra_environment_charge_C_m3"][k])
            for k in range(n)
        ]
        mean_area = sum(g["membrane_area_per_site_m2"][k] for k in mapping) / len(mapping)
        surface = [Decimal(0)] * n
        for k in mapping:
            surface[k] = charge[k] * d(p["cell_height_m"]) * delta**2 / mean_area
        if cache["ko_environment_per_m"] == 0:
            return dict(refused_zero_screening=True), None, hodge
        surface_voltage = [
            v
            / (
                cache["ko_environment_per_m"]
                * d(p["vacuum_permittivity_F_m"])
                * d(p["relative_permittivity"])
            )
            for v in surface
        ]
        screen = (
            2
            / (cache["ko_environment_per_m"] * delta)
            * (d(p["cell_radius_m"]) / d(p["true_cell_size_m"]))
        )
        smoothed = _flatten(_gaussian(_reshape(surface_voltage, shape), constant=True))
        voltage = [a + b for a, b in zip(smoothed, phi, strict=True)]
        screened = _reshape([screen * v for v in voltage], shape)
        gx, gy = _derivative(screened, delta, source_boundary=False)
    else:
        local = [Decimal(0)] * n
        for face, site in enumerate(mapping):
            local[site] = d(packet["old_voltage_V"][current_geometry["owner"][face]]) / 2
        local_smoothed = _gaussian(_reshape([-v for v in local], shape), constant=False)
        gx, gy = _derivative(
            [[delta * v for v in row] for row in local_smoothed], delta, source_boundary=False
        )
        smoothing = _hodge(gx, gy, g)
        gx = _combine(smoothing["solenoidal_x"], smoothing["gradient_x"])
        gy = _combine(smoothing["solenoidal_y"], smoothing["gradient_y"])
        jx = [
            [
                -cache["sigma_S_m"] * v * d(packet["environment_weight"][i][j])
                for j, v in enumerate(row)
            ]
            for i, row in enumerate(gx)
        ]
        jy = [
            [
                -cache["sigma_S_m"] * v * d(packet["environment_weight"][i][j])
                for j, v in enumerate(row)
            ]
            for i, row in enumerate(gy)
        ]
        hodge = _hodge(jx, jy, g)
        voltage = _flatten(local_smoothed)
    ex, ey = [[-v for v in row] for row in gx], [[-v for v in row] for row in gy]
    fx, fy = _flatten(ex), _flatten(ey)
    normal = [
        fx[site] * d(current_geometry["normal_xy"][face][0])
        + fy[site] * d(current_geometry["normal_xy"][face][1])
        for face, site in enumerate(mapping)
    ]
    values = dict(
        raw_environment_current_x=jx,
        raw_environment_current_y=jy,
        local_voltage_assignment=local,
        local_voltage_smoothed=local_smoothed,
        surface_charge_C_m2=surface,
        surface_voltage_V=surface_voltage,
        environment_charge_C_m3=charge,
        screened_voltage_source=screened,
        screen=screen,
        boundary_rhs=rhs,
        boundary_potential_V=phi,
        environment_voltage_V=voltage,
        electric_x_source=ex,
        electric_y_source=ey,
        normal_electric_source=normal,
        environment_current_x=hodge["solenoidal_x"],
        environment_current_y=hodge["solenoidal_y"],
        total_current_x_source=_combine(hodge["solenoidal_x"], hodge["gradient_x"]),
        total_current_y_source=_combine(hodge["solenoidal_y"], hodge["gradient_y"]),
        magnetic_field_source=[v * d(p["magnetic_permeability_H_m"]) for v in hodge["AA"]],
    )
    return values, smoothing, hodge


def evaluate(inputs, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require the two declared independent precision settings")
    precision = 100 if refinement == 1 else 160
    raw = inputs["definition"]
    with localcontext() as context:
        context.prec = precision
        g, cache = geometry(raw, precision=precision), _cache(raw)
        frames = []
        for row in inputs["frames"]:
            values, smoothing, hodge = _fields(raw, row["environment"], g, cache)
            frames.append(
                dict(
                    values=values,
                    smoothing_hodge=smoothing,
                    current_hodge=hodge,
                    current=current_reference(
                        raw["current_definition"], row["current"], refinement=refinement
                    ),
                )
            )
        return serial(
            dict(
                geometry=g,
                cache=cache,
                frames=frames,
                precision=precision,
                native_source_only=True,
                physical_field_energy_parity=False,
                inverse_supplied=False,
                gauge="Dirichlet value rows and Neumann constant-mode complement",
            )
        )
