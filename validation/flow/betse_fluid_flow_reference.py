"""Independent stdlib/80-digit cell algebra and pivoted ECM boundary solves.

Frozen mechanics reference supplies its already qualified owner/DEC operators;
frozen geometry reference supplies its independent stencil and elimination.
No production, NumPy, SciPy or JAX imports occur here.
"""

from decimal import localcontext

from validation.geometry.betse_geometry_reference import grid_laplacian, solve_dense
from validation.mechanics.betse_deformation_reference import arrays, convert, d, matvec, rotation


def derivatives(values, h, negative_boundary=False):
    ny, nx = len(values), len(values[0])
    result = [[[0.0] * nx for _ in range(ny)] for _ in range(2)]
    for axis in (0, 1):
        for i in range(ny):
            for j in range(nx):
                pos, size = (j, nx) if axis == 0 else (i, ny)
                lo, hi = max(0, pos - 1), min(size - 1, pos + 1)
                a, b = (
                    (values[i][lo], values[i][hi]) if axis == 0 else (values[lo][j], values[hi][j])
                )
                sign = -1 if negative_boundary and pos in (0, size - 1) else 1
                result[axis][i][j] = sign * (b - a) / ((hi - lo) * h)
    return result


def environment(raw):
    ny, nx = raw["shape"]
    h = raw["delta_m"]
    lap = grid_laplacian((ny, nx), h, dict.fromkeys("NSEW", "value"))

    def solve(values):
        solution = solve_dense(lap, [v for row in values for v in row])
        return [solution[i * nx : (i + 1) * nx] for i in range(ny)]

    scale = -raw["epsilon_F_m"] * raw["relative_permittivity"] / raw["viscosity_Pa_s"]
    slip = [
        [
            [scale * e * phi * w for e, phi, w in zip(erow, prow, wrow, strict=True)]
            for erow, prow, wrow in zip(
                axis, raw["environment_potential_V"], raw["diffusion_weight"], strict=True
            )
        ]
        for axis in raw["environment_E_V_m"]
    ]
    unprojected = [solve([[-v for v in row] for row in axis]) for axis in slip]
    dx = derivatives([[-v for v in row] for row in unprojected[1]], h, True)[0]
    dy = derivatives(unprojected[0], h, True)[1]
    stream = solve(
        [
            [-dx[i][j] - dy[i][j] if 0 < i < ny - 1 and 0 < j < nx - 1 else 0.0 for j in range(nx)]
            for i in range(ny)
        ]
    )
    gx, gy = derivatives(stream, h)
    output = [[[-v for v in row] for row in gy], gx]
    dx, dy = derivatives(unprojected[0], h, True)[0], derivatives(unprojected[1], h, True)[1]
    scalar = solve(
        [
            [dx[i][j] + dy[i][j] if 0 < i < ny - 1 and 0 < j < nx - 1 else 0.0 for j in range(nx)]
            for i in range(ny)
        ]
    )
    dx, dy = derivatives(output[0], h, True)[0], derivatives(output[1], h, True)[1]
    return dict(
        slip_velocity_m_s=slip,
        unprojected_native_m3_s=unprojected,
        stream_potential_native_m4_s=stream,
        output_native_m3_s=output,
        discarded_scalar_native_m4_s=scalar,
        discarded_gradient_native_m3_s=derivatives(scalar, h),
        divergence_numeric_m2_s=[
            [a + b for a, b in zip(x, y, strict=True)] for x, y in zip(dx, dy, strict=True)
        ],
    )


def evaluate(raw):
    with localcontext() as context:
        context.prec = 80
        op = arrays(raw["layout"])
        scale = d(raw["gj_fraction"]) / d(raw["viscosity_Pa_s"])
        body = [
            [d(e) * d(rho) * scale for e, rho in zip(axis, raw["cell_rho_C_m3"], strict=True)]
            for axis in raw["cell_E_V_m"]
        ]
        unprojected = [matvec(op["laplacian_inverse"], [-v for v in axis]) for axis in body]
        stream, velocity = rotation(unprojected, op)
        div = [
            a + b
            for a, b in zip(
                matvec(op["curl_gradient_x"], velocity[0]),
                matvec(op["curl_gradient_y"], velocity[1]),
                strict=True,
            )
        ]
        cell = convert(
            dict(
                divided_body_force_per_m_s=body,
                unprojected_velocity_m_s=unprojected,
                stream_potential_m2_s=stream,
                velocity_m_s=velocity,
                divergence_numeric_per_s=div,
            )
        )
    return dict(cells=cell, environment=environment(raw) if raw["is_ecm"] else None)
