"""Independent stdlib 80-digit matrix/owner mechanics and display reference."""

from decimal import Decimal, localcontext


def d(value):
    return Decimal(str(value))


def matvec(matrix, vector):
    return [sum((a * b for a, b in zip(row, vector, strict=True)), d(0)) for row in matrix]


def matmul(a, b):
    return [
        [sum((a[i][k] * b[k][j] for k in range(len(b))), d(0)) for j in range(len(b[0]))]
        for i in range(len(a))
    ]


def transpose(a):
    return [list(row) for row in zip(*a, strict=True)]


def arrays(layout):
    sm = [[d(v) for v in row] for row in layout["sum_membranes"]]
    n = len(sm)
    counts = [sum(row) for row in sm]
    fg, cg = [], []
    for kind, direction_key in ((fg, "force_directions"), (cg, "curl_directions")):
        for axis in range(2):
            matrix = [[d(0)] * n for _ in range(n)]
            for i in range(n):
                for m, (left, right) in enumerate(layout["neighbors"]):
                    coefficient = (
                        sm[i][m]
                        * d(layout[direction_key][m][axis])
                        / (counts[i] * d(layout["lengths_m"][m]))
                    )
                    coefficient *= -1 if kind is fg else 1
                    matrix[i][right] += coefficient
                    matrix[i][left] -= coefficient
            kind.append(matrix)
    inc = [[d(v) for v in row] for row in layout["incidence"]]
    pinv = [[d(v) for v in row] for row in layout["incidence_inverse"]]
    weights = [
        d(a) / d(b) for a, b in zip(layout["dual_edge_m"], layout["primal_edge_m"], strict=True)
    ]
    area = [d(v) for v in layout["dual_area_m2"]]
    lap = [
        [
            -sum(inc[e][i] * weights[e] * inc[e][j] for e in range(len(inc))) / area[i]
            for j in range(n)
        ]
        for i in range(n)
    ]
    inv = [
        [
            -sum(pinv[i][e] * pinv[j][e] / weights[e] for e in range(len(inc))) * area[j]
            for j in range(n)
        ]
        for i in range(n)
    ]
    return dict(
        pressure_gradient_x=fg[0],
        pressure_gradient_y=fg[1],
        curl_gradient_x=cg[0],
        curl_gradient_y=cg[1],
        laplacian=lap,
        laplacian_inverse=inv,
    )


def gradient(value, operators):
    return [matvec(operators[k], value) for k in ("pressure_gradient_x", "pressure_gradient_y")]


def rotation(vector, operators):
    gx, gy = operators["curl_gradient_x"], operators["curl_gradient_y"]
    curl = [x - y for x, y in zip(matvec(gx, vector[1]), matvec(gy, vector[0]), strict=True)]
    potential = matvec(operators["laplacian_inverse"], [-v for v in curl])
    return potential, [matvec(gy, potential), [-v for v in matvec(gx, potential)]]


def osmotic(raw, operators):
    mesh = raw["layout"]
    n, e = len(mesh["centers_m"]), len(raw["primary_env_mM"][0])
    rt = d(raw["gas_constant_J_mol_K"]) * d(raw["temperature_K"])
    cell = [
        rt
        * sum(
            (
                d(row[i])
                for key in ("primary_cell_mM", "molecule_cell_mM", "grn_cell_mM")
                for row in raw[key]
            ),
            d(0),
        )
        for i in range(n)
    ]
    env = [
        rt
        * sum(
            (
                d(row[i])
                for key in ("primary_env_mM", "molecule_env_mM", "grn_env_mM")
                for row in raw[key]
            ),
            d(0),
        )
        for i in range(e)
    ]
    if raw["is_ecm"]:
        average = [env[i] for i in raw["cell_to_environment"]]
    else:
        per_mem = [env[raw["cell_to_environment"][owner]] for owner, _ in mesh["neighbors"]]
        average = [
            sum(d(w) * v for w, v in zip(row, per_mem, strict=True)) / sum(row)
            for row in mesh["sum_membranes"]
        ]
    delta = [a - b for a, b in zip(average, cell, strict=True)]
    scale = (
        d(raw["aquaporin_fraction"])
        / d(raw["water_viscosity_Pa_s"])
        * d("9e-20")
        / d(raw["membrane_thickness_m"])
    )
    velocity = [
        (value - d(pressure)) * scale
        for value, pressure in zip(delta, raw["pressure_Pa"], strict=True)
    ]
    div = [
        u * d(a) / d(v)
        for u, a, v in zip(velocity, mesh["cell_area_m2"], mesh["cell_volume_m3"], strict=True)
    ]
    pp = matvec(
        operators["laplacian_inverse"], [-v * d(raw["density_kg_m3"]) * d(raw["dt_s"]) for v in div]
    )
    return dict(
        cell_osmotic_pressure_Pa=cell,
        environment_osmotic_pressure_Pa=env,
        delta_pressure_Pa=delta,
        water_velocity_m_s=velocity,
        divergence_per_s=div,
        PP_native=pp,
    )


def convert(value):
    if isinstance(value, dict):
        return {k: convert(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [convert(v) for v in value]
    return float(value)


def evaluate(raw):
    with localcontext() as context:
        context.prec = 80
        operators = arrays(raw["layout"])
        pressure, pp = ([d(v) for v in raw[k]] for k in ("pressure_Pa", "PP_native"))
        osm = osmotic(raw, operators) if raw["compute_osmotic"] else None
        if osm is not None:
            pp = osm["PP_native"]
        mu = d(raw["young_modulus_Pa"]) / (2 * (1 + d(".49")))
        g, dt = d(raw["galvanotropism_m2_V"]), d(raw["dt_s"])
        if raw["mode"] == "steady":
            grad = gradient(pressure, operators)
            unprojected = [
                matvec(operators["laplacian_inverse"], [-v / mu for v in axis]) for axis in grad
            ]
            potential, rotated = rotation(unprojected, operators)
            osmo = (
                gradient(pp, operators)
                if raw["include_osmotic"]
                else [[d(0)] * len(pressure) for _ in range(2)]
            )
            electric = [[d(v) * g for v in axis] for axis in raw["electric_field_V_m"]]
            result = [
                [a + b + c for a, b, c in zip(rot, os, el, strict=True)]
                for rot, os, el in zip(rotated, osmo, electric, strict=True)
            ]
            data = dict(
                displacement_m=result,
                pressure_gradient_Pa_m=grad,
                unprojected_elastic_m=unprojected,
                rotational_m=rotated,
                rotation_potential=potential,
                osmotic_addition_native=osmo,
                electric_addition_m=electric,
            )
        else:
            assert raw["clock_s"] > 0
            combined = [
                a + b if raw["include_osmotic"] else a for a, b in zip(pressure, pp, strict=True)
            ]
            grad = gradient(combined, operators)
            body = [
                [
                    (v + d(j) / d(sigma) * d(rho) * g) / mu
                    for v, j, sigma, rho in zip(
                        axis,
                        currents,
                        raw["conductivity_S_m"],
                        raw["charge_density_C_m3"],
                        strict=True,
                    )
                ]
                for axis, currents in zip(grad, raw["current_density_A_m2"], strict=True)
            ]
            k = dt * dt * mu / 1000
            gamma = (
                dt
                * dt
                * d(raw["viscous_damping_native"])
                * mu
                / (1000 * 2 * d(raw["cell_radius_m"]))
            )
            current, previous = (
                [[d(v) for v in axis] for axis in raw[key]]
                for key in ("displacement_m", "previous_displacement_m")
            )
            candidate = [
                [
                    k * lap_value - gamma * (now - old) / dt + k / mu * f + 2 * now - old
                    for lap_value, now, old, f in zip(
                        matvec(operators["laplacian"], cur), cur, prev, forces, strict=True
                    )
                ]
                for cur, prev, forces in zip(current, previous, body, strict=True)
            ]
            potential, result = rotation(candidate, operators)
            data = dict(
                displacement_m=result,
                previous_displacement_m=current,
                pressure_gradient_native=grad,
                divided_body_force_native=body,
                unprojected_candidate_m=candidate,
                rotation_potential=potential,
                source_k_m2=[k],
                source_gamma_native=[gamma],
            )
        gx, gy = operators["curl_gradient_x"], operators["curl_gradient_y"]
        data["divergence_numeric"] = [
            a + b for a, b in zip(matvec(gx, result[0]), matvec(gy, result[1]), strict=True)
        ]
        return (
            convert(dict(operators=operators, result=data, osmotic=osm))
            if osm is not None
            else convert(dict(operators=operators, result=data))
        )


def solve_many(matrix, rhs):
    """Independent Decimal partial-pivot elimination, no array algebra."""
    n = len(matrix)
    rows = [list(a) + list(b) for a, b in zip(matrix, rhs, strict=True)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(rows[i][col]))
        if rows[pivot][col] == 0:
            raise ValueError("Rank-deficient independent display fit")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [v / divisor for v in rows[col]]
        for i in range(n):
            if i != col:
                multiplier = rows[i][col]
                rows[i] = [a - multiplier * b for a, b in zip(rows[i], rows[col], strict=True)]
    return [row[n:] for row in rows]


def display_expected(raw):
    """80-digit normal-equation polynomial fit with native rectangle clamping.

    Repeated samples refit the fixed displacement values against the new display
    centres. FITPACK/adaptive knots are not reimplemented outside this regime.
    """
    with localcontext() as context:
        context.prec = 80
        mesh = raw["layout"]
        original = [[d(v) for v in row] for row in mesh["vertices_m"]]
        centers = [[d(v) for v in row] for row in mesh["centers_m"]]
        data = transpose([[d(v) for v in row] for row in raw["displacement_m"]])
        records = []
        for _ in range(raw["calls"]):
            low = [min(c[a] for c in centers) for a in range(2)]
            high = [max(c[a] for c in centers) for a in range(2)]
            offset = [sum(c[a] for c in centers) / len(centers) for a in range(2)]
            scale = [hi - lo for hi, lo in zip(high, low, strict=True)]

            def basis(point, offset=offset, scale=scale):
                x, y = [(point[a] - offset[a]) / scale[a] for a in range(2)]
                return [
                    (x**i if i else d(1)) * (y**j if j else d(1))
                    for i in range(5)
                    for j in range(5)
                ]

            design = [basis(c) for c in centers]
            normal = matmul(transpose(design), design)
            rhs = matmul(transpose(design), data)
            solution = solve_many(normal, rhs)
            displacement = []
            for point in original:
                clamped = [max(low[a], min(high[a], point[a])) for a in range(2)]
                displacement.append(matmul([basis(clamped)], solution)[0])
            vertices = [
                [a + b for a, b in zip(v, dv, strict=True)]
                for v, dv in zip(original, displacement, strict=True)
            ]
            centers = [
                [sum(vertices[4 * i + j][a] for j in range(4)) / 4 for a in range(2)]
                for i in range(len(mesh["centers_m"]))
            ]
            records.append(convert(dict(vertices_m=vertices, cell_centres_m=centers)))
        return records
