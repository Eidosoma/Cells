"""Contraction paths through the compatibility crossing (judged-01's barrier failure).

A compatible start at r = 10 loses compatibility at a critical contraction fraction,
where the constrained network is critically flat (judged-01's failure, on 8 x 8). On
4 x 4 the same crossing converges through the trust-region and force-residual stages
(failure handling: test_mechanical_equilibrium_failures.py).
"""

import jax
import numpy as np

from cells.analysis import mechanical_equilibrium as me
from validation.morphogenesis import mg1_vertex as d

jax.config.update("jax_enable_x64", True)


def test_path_through_the_compatibility_crossing_converges():
    r, p0 = 10.0, 3.75
    pb, model = d._staddon_problem(4, r, p0, seed=3)
    eq = me.minimize(pb)
    # Compatibility is lost at fraction 0.5 on this path (critically flat there).
    fractions = np.array([1.0, 0.6, 0.5, 0.45])
    path = me.contraction(pb, eq.position, d.orientation_junctions(model)[1], fractions)
    assert np.all(path.max_forces <= 1e-11)
    staddon = np.asarray(path.energies) + 16 * r * p0**2 / 2
    assert abs(staddon[0]) < 1e-10 and staddon[-1] > 1e-9  # compatible start, then incompatible
    crossing = [s for s in path.diagnostics if s.get("cycles")]
    assert crossing and all(s["spectrum"]["negative"] == 0 for s in path.diagnostics)
