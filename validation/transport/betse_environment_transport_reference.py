"""Independent stdlib/Decimal owner, stencil, barrier and face transport math."""

from decimal import Decimal, localcontext
from math import exp, fsum


def gaussian(matrix, sigma):
    ny, nx = len(matrix), len(matrix[0])
    radius = int(4 * sigma + 0.5)
    weights = [exp(-j * j / (2 * sigma * sigma)) for j in range(-radius, radius + 1)]
    total = fsum(weights)
    weights = [v / total for v in weights]

    def reflected(at, size):
        at %= 2 * size
        return at if at < size else 2 * size - at - 1

    vertical = [
        [
            fsum(w * matrix[reflected(i + k - radius, ny)][j] for k, w in enumerate(weights))
            for j in range(nx)
        ]
        for i in range(ny)
    ]
    return [
        [
            fsum(w * vertical[i][reflected(j + k - radius, nx)] for k, w in enumerate(weights))
            for j in range(nx)
        ]
        for i in range(ny)
    ]


def coefficients(raw):
    ny, nx = raw["shape"]
    size = ny * nx
    regions = raw["regions"]
    targets = [
        v
        for key in ("boundary_membrane", "neighbor_membrane", "boundary_cell")
        for v in regions[key]
    ]
    if raw["is_ecm"]:
        rows = []
        for free, relative in zip(raw["D_free_m2_s"], raw["relative_TJ"], strict=True):
            row = [free] * size
            for at in regions["cluster"]:
                row[at] = free * raw["adherens_factor"]
            for at in targets:
                row[at] = free * raw["tight_factor"] * relative
            rows.append(row)
        maximum = max(rows[raw["species_ids"].index("Na")])
        weight = [v / maximum for v in rows[raw["species_ids"].index("Na")]]
    else:
        row = [1.0] * size
        for at in targets:
            row[at] = raw["tight_factor"]
        weight = [
            v for row in gaussian([row[i * nx : (i + 1) * nx] for i in range(ny)], 1.0) for v in row
        ]
        rows = list(raw["D_free_m2_s"])
    return dict(D_env=rows, weight=weight, TJ_targets=targets)


def gradient(matrix, h, *, divergence=False):
    ny, nx = len(matrix), len(matrix[0])
    gx = []
    gy = []
    for i in range(ny):
        rx = []
        ry = []
        for j in range(nx):
            x = (
                (matrix[i][j + 1] - matrix[i][j - 1]) / (2 * h)
                if 0 < j < nx - 1
                else (matrix[i][1] - matrix[i][0]) / h
                if j == 0
                else (matrix[i][-1] - matrix[i][-2]) / h
            )
            y = (
                (matrix[i + 1][j] - matrix[i - 1][j]) / (2 * h)
                if 0 < i < ny - 1
                else (matrix[1][j] - matrix[0][j]) / h
                if i == 0
                else (matrix[-1][j] - matrix[-2][j]) / h
            )
            rx.append(-x if divergence and j in (0, nx - 1) else x)
            ry.append(-y if divergence and i in (0, ny - 1) else y)
        gx.append(rx)
        gy.append(ry)
    return gx, gy


def smooth(matrix, sharp):
    ny, nx = len(matrix), len(matrix[0])
    out = [row[:] for row in matrix]
    for i in range(1, ny - 1):
        for j in range(1, nx - 1):
            out[i][j] = sharp * matrix[i][j] + (1 - sharp) / 4 * (
                matrix[i - 1][j] + matrix[i + 1][j] + matrix[i][j - 1] + matrix[i][j + 1]
            )
    return out


def source_step(raw, values, diffusion, bath, *, valence, mobility=0.0, dilation=1.0):
    ny, nx = raw["shape"]
    h = raw["delta_m"]
    matrix = [list(values[i * nx : (i + 1) * nx]) for i in range(ny)]
    for i in range(ny):
        matrix[i][0] = matrix[i][-1] = bath
    matrix[0] = [bath] * nx
    matrix[-1] = [bath] * nx
    gx, gy = gradient(matrix, h)
    fx = []
    fy = []
    for i in range(ny):
        rx = []
        ry = []
        for j in range(nx):
            at = i * nx + j
            d = diffusion[at]
            c = matrix[i][j]
            drift = d * valence * raw["q_C"] / (raw["kb_J_K"] * raw["temperature_K"]) + mobility
            ux = raw["velocity_m_s"][0][at] if raw["fluid_flow"] else 0
            uy = raw["velocity_m_s"][1][at] if raw["fluid_flow"] else 0
            rx.append(-d * gx[i][j] + drift * c * raw["electric_V_m"][0][at] + ux * c)
            ry.append(-d * gy[i][j] + drift * c * raw["electric_V_m"][1][at] + uy * c)
        fx.append(rx)
        fy.append(ry)
    dx, _ = gradient([[-v for v in row] for row in fx], h, divergence=True)
    _, dy = gradient([[-v for v in row] for row in fy], h, divergence=True)
    div = [[dx[i][j] + dy[i][j] for j in range(nx)] for i in range(ny)]
    after = [
        [matrix[i][j] + raw["dt_s"] * dilation * div[i][j] for j in range(nx)] for i in range(ny)
    ]
    if raw["sharpness"] < 1:
        after = smooth(after, raw["sharpness"])
    return dict(
        concentration=[v for row in after for v in row],
        clamped=matrix,
        flux_x=fx,
        flux_y=fy,
        divergence=div,
    )


def pulse(time, on, off, change):
    with localcontext() as ctx:
        ctx.prec = 80
        t, a, b, d = (Decimal(str(v)) for v in (time, on, off, change))
        g = 10 / d
        return float(1 / (1 + (-g * (t - a)).exp()) - 1 / (1 + (-g * (t - b)).exp()))


def bath_updates(raw, time, boundary, concentration):
    boundary = list(boundary)
    state = [row[:] for row in concentration]
    baseline = dict(zip(raw["species_ids"], raw["base_bath_mol_m3"], strict=True))
    for kind in ("K_env", "Cl_env", "Na_env"):
        event = next((v for v in raw["events"] if v["kind"] == kind), None)
        if event is None or kind == "Cl_env" and not raw["enabled_Cl"]:
            continue
        ion = kind.split("_")[0]
        delta = (
            event["amplitude"]
            * pulse(time, event["on_s"], event["off_s"], event["change_s"])
            * baseline[ion]
        )
        at = raw["species_ids"].index(ion)
        if raw["is_ecm"]:
            boundary[at] = baseline[ion] + delta
            other = "Na" if ion == "Cl" else "M"
            boundary[raw["species_ids"].index(other)] = baseline[other] + delta
        else:
            state[at] = [baseline[ion] + delta] * len(state[at])
    return boundary, state


def bernoulli(value):
    if value == 0:
        return Decimal(1)
    return value / (value.exp() - 1)


def face_step(
    spec,
    concentration,
    diffusion,
    electric,
    velocity,
    bath,
    opened,
    dt,
    temperature,
    q,
    kb,
    *,
    mobility=None,
):
    """Independent high-precision Bernoulli-fitted conservative face operator."""
    with localcontext() as ctx:
        ctx.prec = 80

        def number(value):
            return Decimal(str(value))

        ids = spec["site_ids"]
        ny, nx = spec["shape"]
        h = number(spec["delta_m"])
        height = number(spec["height_m"])
        volume = h * h * height
        area = h * height
        dt = number(dt)
        z = spec["valence"]
        s = len(concentration)
        total = [[number(v) * volume for v in row] for row in concentration]
        change = [[Decimal(0)] * len(ids) for _ in range(s)]
        internal = []
        boundary = []
        outgoing = [[Decimal(0)] * len(ids) for _ in range(s)]
        mobility = [0.0] * s if mobility is None else mobility
        for (left, right), (nxv, nyv) in zip(
            spec["internal_indices"], spec["internal_normals"], strict=True
        ):
            row = []
            for ion in range(s):
                a, b = number(diffusion[ion][left]), number(diffusion[ion][right])
                d = 2 * a * b / (a + b) if a + b else Decimal(0)
                e = sum(
                    (number(electric[k][left]) + number(electric[k][right])) / 2 * number(v)
                    for k, v in enumerate((nxv, nyv))
                )
                u = sum(
                    (number(velocity[k][left]) + number(velocity[k][right])) / 2 * number(v)
                    for k, v in enumerate((nxv, nyv))
                )
                w = (
                    d * number(z[ion]) * number(q) / (number(kb) * number(temperature))
                    + number(mobility[ion])
                ) * e + u
                if d:
                    pe = w * h / d
                    alpha = d / h * bernoulli(-pe)
                    beta = d / h * bernoulli(pe)
                else:
                    alpha = max(w, Decimal(0))
                    beta = max(-w, Decimal(0))
                flux = alpha * number(concentration[ion][left]) - beta * number(
                    concentration[ion][right]
                )
                row.append(float(flux))
                delta = flux * area * dt
                change[ion][left] -= delta
                change[ion][right] += delta
                outgoing[ion][left] += alpha * area / volume
                outgoing[ion][right] += beta * area / volume
            internal.append(row)
        for at, (owner, (nxv, nyv)) in enumerate(
            zip(spec["boundary_indices"], spec["boundary_normals"], strict=True)
        ):
            row = []
            for ion in range(s):
                if not opened[at]:
                    row.append(0.0)
                    continue
                d = number(diffusion[ion][owner])
                length = h / 2
                e = sum(number(electric[k][owner]) * number(v) for k, v in enumerate((nxv, nyv)))
                u = sum(number(velocity[k][owner]) * number(v) for k, v in enumerate((nxv, nyv)))
                w = (
                    d * number(z[ion]) * number(q) / (number(kb) * number(temperature))
                    + number(mobility[ion])
                ) * e + u
                if d:
                    pe = w * length / d
                    alpha = d / length * bernoulli(-pe)
                    beta = d / length * bernoulli(pe)
                else:
                    alpha = max(w, Decimal(0))
                    beta = max(-w, Decimal(0))
                flux = alpha * number(concentration[ion][owner]) - beta * number(bath[ion][at])
                row.append(float(flux))
                change[ion][owner] -= flux * area * dt
                outgoing[ion][owner] += alpha * area / volume
            boundary.append(row)
        result = [
            [float((total[i][j] + change[i][j]) / volume) for j in range(len(ids))]
            for i in range(s)
        ]
        return dict(
            concentration=result,
            amount_change=[[float(v) for v in row] for row in change],
            internal_flux=[list(row) for row in zip(*internal, strict=True)],
            boundary_flux=[list(row) for row in zip(*boundary, strict=True)],
            maximum_courant=float(max(v for row in outgoing for v in row) * dt),
        )
