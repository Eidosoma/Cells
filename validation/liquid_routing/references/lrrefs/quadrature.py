"""Two quadratures of different kinds.

- `TanhSinh`: the double-exponential rule with its nodes clustered at both ends, trapezoidal in u.
- `GradedGauss`: Gauss-Legendre on pieces graded geometrically toward the left end (and plain pieces
  elsewhere). It knows nothing of the first.
"""

import decimal
import math
from decimal import Decimal

from .arith import ONE, TWO, ZERO, pi, precision


class TanhSinh:
    """Nodes s in (0, 1) with s = 1/(1 + e^(-pi sinh u)), u = j/steps_per_unit."""

    def __init__(self, steps_per_unit, digits, cutoff_digits=62):
        with precision(digits):
            h = ONE / steps_per_unit
            big_pi = pi()
            limit = Decimal(cutoff_digits) * Decimal(10).ln()
            self.nodes = []      # (s, 1 - s, weight, index)
            j = 0
            while True:
                u = j * h
                e = u.exp()
                sinh = (e - 1 / e) / 2
                cosh = (e + 1 / e) / 2
                exponent = big_pi * sinh
                growth = exponent.exp()
                small = 1 / (1 + growth)                 # 1 - s for u >= 0, and s for -u
                large = growth / (1 + growth)
                weight = h * big_pi * cosh * small * large
                self.nodes.append((large, small, weight, j))
                if j > 0:
                    self.nodes.append((small, large, weight, -j))
                if exponent > limit:
                    break
                j += 1
            self.nodes.sort(key=lambda node: node[3])
            self.steps_per_unit = steps_per_unit

    def points(self, a, b):
        """[(position in (a, b), weight, on the coarse half-grid)]. Call it with a = 0 to keep positions accurate there."""
        length = b - a
        return [(a + length * s, length * w, index % 2 == 0) for s, _, w, index in self.nodes]


class GaussRule:
    """Nodes and weights of the n-point Gauss-Legendre rule on [0, 1]."""

    def __init__(self, n, digits):
        with precision(digits):
            self.rule = []
            for k in range(1, n + 1):
                x = Decimal(math.cos(math.pi * (k - 0.25) / (n + 0.5)))
                for _ in range(60):
                    p0, p1 = ONE, x
                    for j in range(2, n + 1):
                        p0, p1 = p1, ((2 * j - 1) * x * p1 - (j - 1) * p0) / j
                    slope = n * (x * p1 - p0) / (x * x - 1)
                    step = p1 / slope
                    x -= step
                    if abs(step) < Decimal(10) ** -(digits - 10):
                        break
                p0, p1 = ONE, x
                for j in range(2, n + 1):
                    p0, p1 = p1, ((2 * j - 1) * x * p1 - (j - 1) * p0) / j
                slope = n * (x * p1 - p0) / (x * x - 1)
                weight = 2 / ((1 - x * x) * slope * slope)
                self.rule.append(((1 - x) / 2, weight / 2))
            self.rule.sort()
            self.n = n

    def points(self, a, b):
        length = b - a
        return [(a + length * s, length * w) for s, w in self.rule]


def graded_pieces(a, b, depth):
    """[a, b] cut geometrically toward a: the first piece is (b - a) 2^-depth long, each next twice as far."""
    length = b - a
    edges = [a] + [a + length * TWO ** -k for k in range(depth, -1, -1)]
    return list(zip(edges, edges[1:]))


def gauss_points(rule, a, b, depth):
    """The graded Gauss points of [a, b]; depth 0 is one plain piece."""
    points = []
    for left, right in graded_pieces(a, b, depth):
        points.extend(rule.points(left, right))
    return points


__all__ = ["TanhSinh", "GaussRule", "gauss_points", "graded_pieces", "ZERO", "decimal"]
