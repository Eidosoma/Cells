"""mechanical_equilibrium_analysis@1 on periodic honeycombs (apical_vertex_mechanics@1).

FIRE plus Newton reaches the case-I ground state; box relaxation recovers a*; the
relaxed moduli equal Staddon et al. (2023) G = r (p - p0) p / (4a) and
B = a + r p p0 / (4a), with relaxed G two thirds of affine G; a quasi-static
contraction of one junction to zero length has a positive barrier below the
pentagon threshold and none in the compatible regime.
"""

import jax
import numpy as np
import pytest

from cells.analysis import mechanical_equilibrium as me
from cells.core.specs import ConfigError, parse_spec
from tests.apical_vertex_fixtures import A_STAR, E_STAR, GAMMA, LAMBDA, honeycomb
from validation.morphogenesis import mg1_theory as theory

jax.config.update("jax_enable_x64", True)


def test_minimum_box_relaxation_and_moduli_of_case_one():
    pb = me.problem(parse_spec(honeycomb(displacement=0.05, seed=1)))
    eq = me.minimize(pb)
    assert abs(eq.energy / 16 - E_STAR) <= 1e-13 and eq.max_force < 1e-13
    pb = me.problem(parse_spec(honeycomb(area=A_STAR * 1.05**2, displacement=0.02, seed=1)))
    eq = me.minimize(pb, box=True)
    assert abs(np.linalg.det(eq.box) / 16 - A_STAR) <= 1e-12
    assert np.max(np.abs(eq.stress)) <= 1e-11 and eq.box_iterations >= 1
    mod = me.moduli(pb, eq.position, eq.box)
    shear, bulk = theory.moduli(*theory.staddon_parameters(LAMBDA, GAMMA))
    assert abs(mod.shear - shear) <= 1e-9 * shear and abs(mod.bulk - bulk) <= 1e-9 * bulk
    assert abs(mod.shear / mod.shear_affine - 2 / 3) <= 1e-9
    assert mod.zero_modes == 2 and mod.negative_modes == 0


def ordered(p0, r=1.0, seed=3):
    area = theory.hexagon_state(r, p0)[0] if p0 < theory.P_STAR else 1.0
    d = honeycomb(area=area, displacement=0.02, seed=seed)
    for j in d["model"]["junctions"]:
        j["line_tension"] = -2.0 * r * p0
    for c in d["model"]["cells"]:
        c["contractility"] = r
    return me.problem(parse_spec(d))


def test_contraction_barrier_below_and_above_the_pentagon_threshold():
    fractions = np.linspace(1.0, 0.0, 6)
    pb = ordered(3.7)
    path = me.contraction(pb, me.minimize(pb).position, 0, fractions)
    assert path.barrier > 1e-3 and np.all(path.max_forces < 1e-9)
    pb = ordered(3.85)
    eq = me.minimize(pb)
    assert abs(eq.energy + 16 * 3.85**2 / 2) <= 1e-10  # compatible: Staddon energy zero
    path = me.contraction(pb, eq.position, 0, fractions)
    assert abs(path.barrier) <= 1e-10


def test_analysis_refusals():
    pb = me.problem(parse_spec(honeycomb()))
    with pytest.raises(ConfigError, match="decrease"):
        me.contraction(pb, pb.position, 0, [0.5, 1.0])
    d = honeycomb()
    d["model"]["periods"][0][1] = 0.01  # A sheared, non-upper-triangular box.
    sheared = parse_spec(d)
    with pytest.raises(ConfigError, match="upper-triangular"):
        me.minimize(me.problem(sheared), box=True)
