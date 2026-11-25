"""Arm 6's published splits, in decimal (LAWS section 10 and P19): Strang P(h/2) E(h) P(h/2), and Lie P(h) then E(h).

P is the exact propagator of G_Q, and E(h) = I + h G_P + (h G_P)^2 / 2, the explicit stages of a linear system.
"""

from decimal import Decimal

from . import propagator as pr
from .arith import HALF, ZERO


def explicit_matrix(g, h):
    """I + hB + (hB)^2 / 2."""
    n = len(g)
    b = pr.scaled(g, h)
    square = pr.matmul(b, b)
    return pr.add(pr.add(pr.identity(n), b), pr.scaled(square, HALF))


def split_run(world, species, step, outputs, kind):
    """{time: {name: amount}} of the split run at the outputs that `step` divides (and t = 0)."""
    layout = pr.Layout(world)
    g_flow = pr.generator(world, species, ZERO, layout, with_faces=False)
    g_face = pr.generator(world, species, ZERO, layout, with_flow=False)
    face_step = explicit_matrix(g_face, step)
    if kind == "strang":
        half = pr.expm(g_flow, step / 2)
        one = pr.matmul(half, pr.matmul(face_step, half))
    elif kind == "lie":
        one = pr.matmul(face_step, pr.expm(g_flow, step))
    else:
        raise ValueError(kind)
    y = pr.with_inlets(world, species, ZERO, pr.start_vector(world, species, layout), layout)
    rows = {}
    wanted = set(outputs)
    count = int(max(outputs) / step)
    names = layout.nodes + layout.collectors
    if ZERO in wanted:
        rows[ZERO] = {name: y[layout.index[name]] for name in names}
    for k in range(1, count + 1):
        y = pr.matvec(one, y)
        t = step * k
        if t in wanted:
            rows[t] = {name: y[layout.index[name]] for name in names}
    return rows


def halving_estimate(series, p):
    """CRITERIA section 3.5 from three series (coarse, middle, fine): (d2, d1, est)."""
    coarse, middle, fine = series
    d2 = max(abs(b - a) for a, b in zip(coarse, middle))
    d1 = max(abs(b - a) for a, b in zip(middle, fine))
    factor = Decimal(2) ** p
    return d2, d1, max(d1 / (factor - 1), d2 / (factor * (factor - 1)))


def order(d2, d1):
    """q = log2(d2 / d1)."""
    return (d2 / d1).ln() / Decimal(2).ln()
