"""Independent byte-PGM mask, Decimal grid/hull and bilinear query reference.

No production/native/Pillow/NumPy/SciPy imports. Cubic fast-spline coefficients
are outside this independent reference; original native arrays cover that seam.
"""

from decimal import Decimal, localcontext


def d(value):
    return Decimal.from_float(float(value))


def _serial(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_serial(v) for v in value]
    if isinstance(value, dict):
        return {key: _serial(v) for key, v in value.items()}
    return value


def decode_pgm(data):
    """Exact declared P5 byte fixtures; no claim for other Pillow conversions."""
    magic, dimensions, maximum, raster = data.split(b"\n", 3)
    width, height = (int(value) for value in dimensions.split())
    if magic != b"P5" or maximum != b"255" or width != height or len(raster) != width * height:
        raise ValueError("Require the declared square P5/255 byte fixture")
    return [list(raster[i * width : (i + 1) * width]) for i in range(height)]


def _hull(points):
    """Monotone chain, CCW from lexicographic minimum; retain input indices."""
    order = sorted(range(len(points)), key=lambda index: tuple(points[index]))
    if len(order) < 3:
        raise ValueError("Raw independent hull lacks three image points")

    def cross(i, j, k):
        a, b, c = points[i], points[j], points[k]
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    lower, upper = [], []
    for index in order:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], index) <= 0:
            lower.pop()
        lower.append(index)
    for index in reversed(order):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], index) <= 0:
            upper.pop()
        upper.append(index)
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:
        raise ValueError("Raw independent hull is collinear")
    return hull


def _linear(x, y, mask, qx, qy):
    if not x[0] <= qx <= x[-1] or not y[0] <= qy <= y[-1]:
        raise ValueError("Independent query currently covers the closed image window only")

    def interval(axis, query):
        index = next((i for i in range(len(axis) - 1) if query <= axis[i + 1]), len(axis) - 2)
        return index, (query - axis[index]) / (axis[index + 1] - axis[index])

    i, u = interval(x, qx)
    j, v = interval(y, qy)
    return (
        (1 - u) * (1 - v) * mask[j][i]
        + u * (1 - v) * mask[j][i + 1]
        + (1 - u) * v * mask[j + 1][i]
        + u * v * mask[j + 1][i + 1]
    )


def evaluate(data, bounds_m, points_x=(), points_y=(), *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require the two declared independent precisions")
    with localcontext() as context:
        context.prec = 100 if refinement == 1 else 160
        bitmap = decode_pgm(data)
        m = len(bitmap)
        if not 4 <= m <= 32:
            raise ValueError("Reference complete masks require the native cubic size boundary")
        mask = [[int(value != 255) for value in row] for row in reversed(bitmap)]
        xmin, xmax, ymin, ymax = (d(v) for v in bounds_m)
        x = [xmin + i * (xmax - xmin) / (m - 1) for i in range(m)]
        y = [ymin + i * (ymax - ymin) / (m - 1) for i in range(m)]
        indices = [[i, j] for i, row in enumerate(mask) for j, value in enumerate(row) if value]
        points = [[x[j], y[i]] for i, j in indices]
        hull = _hull(points)
        values = [
            _linear(x, y, mask, d(qx), d(qy)) for qx, qy in zip(points_x, points_y, strict=False)
        ]
        return _serial(
            dict(
                bitmap=bitmap,
                clipping_matrix=mask,
                xpts_m=x,
                ypts_m=y,
                active_grid_indices=indices,
                active_points_m=points,
                canonical_hull_indices=hull,
                canonical_clipcurve_m=[points[i] for i in hull],
                paired_linear_values=values,
                selected_indices=[i for i, value in enumerate(values) if value != 0],
                precision=context.prec,
                fast_cubic_independent_claim=False,
            )
        )
