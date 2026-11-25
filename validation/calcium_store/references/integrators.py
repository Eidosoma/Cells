"""Two integrators of y' = f(y) in decimal arithmetic, of two kinds.

- `extrapolated_midpoint`: explicit. The midpoint rule at 2, 4, ..., 2k substeps, extrapolated in the square of the substep
  (Gragg, Bulirsch and Stoer). Order 2k. Decimal operations only, so it gives the same digits on every machine. The published
  values come from this one.
- `RadauIIA`: implicit and stiffly accurate. s collocation stages at the right Radau nodes, order 2s - 1, solved by a
  simplified Newton iteration. Its linear algebra is in doubles and only steers the iteration; the residual is in decimal
  and is driven to rounding.

`f` takes and returns a list of Decimals. The independent variable does not appear in f.
"""

from decimal import Decimal, localcontext

import numpy

TWO = Decimal(2)


def extrapolated_midpoint_step(f, y, H, columns):
    """One step of length H. Returns the value of the last diagonal entry of the extrapolation table."""
    f0 = f(y)
    previous_row = None
    for j in range(1, columns + 1):
        n = 2 * j
        h = H / n
        twice = 2 * h
        z0 = y
        z1 = [a + h * b for a, b in zip(y, f0)]
        for _ in range(1, n):
            fz = f(z1)
            z0, z1 = z1, [a + twice * b for a, b in zip(z0, fz)]
        row = [z1]
        for i in range(1, j):
            # columns i and i - 1 use the substep counts 2j and 2(j - i)
            ratio = Decimal(j) / Decimal(j - i)
            denominator = ratio * ratio - 1
            row.append([a + (a - b) / denominator for a, b in zip(row[i - 1], previous_row[i - 1])])
        previous_row = row
    return previous_row[-1]


def extrapolated_midpoint(f, y0, times, steps_per_interval, columns):
    """The values at each of `times` (the first is the initial time), by equal steps within each interval."""
    y = list(y0)
    values = [list(y)]
    for start, end in zip(times, times[1:]):
        H = (end - start) / steps_per_interval
        for _ in range(steps_per_interval):
            y = extrapolated_midpoint_step(f, y, H, columns)
        values.append(list(y))
    return values


# Radau IIA


def _polynomial_value(coefficients, x):
    total = Decimal(0)
    for coefficient in reversed(coefficients):
        total = total * x + coefficient
    return total


def _radau_polynomial(s):
    """Integer coefficients, lowest first, of d^(s-1)/dx^(s-1) [x^(s-1) (x - 1)^s]: its roots are the right Radau nodes."""
    from math import comb

    coefficients = [0] * (s - 1) + [comb(s, k) * (-1) ** (s - k) for k in range(s + 1)]
    for _ in range(s - 1):
        coefficients = [k * coefficients[k] for k in range(1, len(coefficients))]
    return coefficients


def radau_nodes(s):
    """The s right Radau nodes on (0, 1], the last exactly 1, in the context's precision."""
    integers = _radau_polynomial(s)
    coefficients = [Decimal(k) for k in integers]
    grid = 40 * s * s
    points = [Decimal(i) / grid for i in range(grid)]  # 1 itself is a root and is added below
    signs = [_polynomial_value(coefficients, x) > 0 for x in points]
    roots = []
    for left, right, a, b in zip(points, points[1:], signs, signs[1:]):
        if a == b:
            continue
        for _ in range(12 * 34):
            middle = (left + right) / 2
            if (_polynomial_value(coefficients, middle) > 0) == a:
                left = middle
            else:
                right = middle
        roots.append((left + right) / 2)
    if len(roots) != s - 1:
        raise ValueError(f"found {len(roots)} of {s - 1} inner Radau nodes")
    return roots + [Decimal(1)]


def radau_matrix(nodes):
    """a_ij = the integral of the j-th Lagrange polynomial of the nodes from 0 to node i."""
    s = len(nodes)
    matrix = [[None] * s for _ in range(s)]
    for j in range(s):
        coefficients = [Decimal(1)]
        denominator = Decimal(1)
        for m in range(s):
            if m == j:
                continue
            shifted = [Decimal(0)] + coefficients
            coefficients = [a - nodes[m] * b for a, b in zip(shifted, coefficients + [Decimal(0)])]
            denominator *= nodes[j] - nodes[m]
        integral = [Decimal(0)] + [c / (k + 1) / denominator for k, c in enumerate(coefficients)]
        for i in range(s):
            matrix[i][j] = _polynomial_value(integral, nodes[i])
    return matrix


class RadauIIA:
    """The s-stage Radau IIA collocation method, order 2s - 1."""

    def __init__(self, stages):
        self.stages = stages
        with localcontext() as context:
            context.prec = 120
            nodes = radau_nodes(stages)
            matrix = radau_matrix(nodes)
        self.nodes = [+c for c in nodes]
        self.matrix = [[+a for a in row] for row in matrix]
        self.weights = self.matrix[-1]
        self._double = numpy.array([[float(a) for a in row] for row in self.matrix])

    def step(self, f, jacobian, y, H, tolerance, limit=60):
        """One step of length H: (the new value, the stage values, iterations used)."""
        s, N = self.stages, len(y)
        system = numpy.eye(s * N) - float(H) * numpy.kron(self._double, jacobian)
        inverse = numpy.linalg.inv(system)
        stage_values = [list(y) for _ in range(s)]
        for iteration in range(1, limit + 1):
            slopes = [f(z) for z in stage_values]
            residual = []
            for i in range(s):
                row = self.matrix[i]
                for n in range(N):
                    total = sum((row[j] * slopes[j][n] for j in range(s)), Decimal(0))
                    residual.append(stage_values[i][n] - y[n] - H * total)
            largest = max(abs(r) for r in residual)
            if largest == 0:
                return stage_values[-1], stage_values, iteration
            # the correction is found in doubles on a residual scaled to 1, so it has about 15 digits of its own size
            scaled = numpy.array([float(r / largest) for r in residual])
            correction = inverse @ scaled
            for i in range(s):
                for n in range(N):
                    stage_values[i][n] -= largest * Decimal(float(correction[i * N + n]))
            if largest < tolerance:
                return stage_values[-1], stage_values, iteration
        raise ArithmeticError(f"no convergence: residual {largest}")


def finite_difference_jacobian(f, y, relative=Decimal("1e-14")):
    """df/dy as doubles by central differences in decimal, each step `relative` times a typical size of the component."""
    columns = []
    for n in range(len(y)):
        delta = relative * max(abs(y[n]), Decimal("1e-6"))
        up, down = list(y), list(y)
        up[n] += delta
        down[n] -= delta
        columns.append([float((a - b) / (TWO * delta)) for a, b in zip(f(up), f(down))])
    return numpy.array(columns).T


def radau(f, quadrature, y0, times, steps_per_interval, method, tolerance=Decimal("1e-36")):
    """The values and the integrals of `quadrature(y)` at each of `times`: a list of (y, Q)."""
    y = list(y0)
    Q = [Decimal(0)] * len(quadrature(y))
    values = [(list(y), list(Q))]
    for start, end in zip(times, times[1:]):
        H = (end - start) / steps_per_interval
        for _ in range(steps_per_interval):
            jacobian = finite_difference_jacobian(f, y)
            new, stage_values, _iterations = method.step(f, jacobian, y, H, tolerance)
            rates = [quadrature(z) for z in stage_values]
            for n in range(len(Q)):
                Q[n] += H * sum((method.weights[j] * rates[j][n] for j in range(method.stages)), Decimal(0))
            y = list(new)
        values.append((list(y), list(Q)))
    return values
