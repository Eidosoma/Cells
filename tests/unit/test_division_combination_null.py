"""J1 combination round: each combined arm reduces to its single parts when one part is null.

The combinations of j1_combination_round.json have never run together, and the existing tests
cover each extension's null only separately. Two reductions are checked. With f = 0, A1 x A7a
reproduces A7a alone. With alpha = 0, each arm reproduces its level-shifters alone (A1; the seal;
A6c; the seal with A6c). Simulations use synthetic cells (tests/division_fixtures.py). The
checks on the declared egg compare constructions only and simulate nothing.
"""

import math
from dataclasses import fields, replace

import numpy as np
import pytest

from tests.division_fixtures import growing
from validation.division import cleft_egg_reference as ref
from validation.division import cleft_rings_reference as rings
from validation.division import j1_combination_runner as comb
from validation.division import j1_diagnostic_runner as diag

GEOMETRY = (3e-5, 1e-5, 2e-5)  # synthetic r_egg, r_bridge, r_mouth (m) for areas near 1e-9 m2
FIT = dict(pk_m_s=2e-7, rho=0.02)  # a synthetic A6c-like new membrane


def same_egg(a, b):
    """Field-by-field equality, with NaN equal to NaN (unset Egg fields are NaN)."""

    def same(x, y):
        nan = isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y)
        return x == y or nan

    return all(same(getattr(a, f.name), getattr(b, f.name)) for f in fields(a))


def trace(egg, t_end=2.1):
    """Em at every pulse front edge and sample on the synthetic cell's pulse train (V)."""
    run = ref.simulate(egg, t_end, method="LSODA")
    ks = sorted(k for k in run.onset_V if k in run.sample_V)
    return np.array([run.onset_V[k] for k in ks] + [run.sample_V[k] for k in ks])


def alone(base, *, f=0.0, seal=False, a6c_fit=None):
    """A level-shifter (or several) on `base` with the registered constant access, built
    directly from the arm file's definitions rather than through the round's builder."""
    egg = replace(base, bath_fraction=f)
    if seal:
        egg = replace(egg, access_D=(egg.access_D[0], egg.access_D[1], 0.0))
    if a6c_fit is not None:
        pk = a6c_fit["pk_m_s"]
        egg = replace(egg, new_permeability=(a6c_fit["rho"] * pk, pk, 0.0))
    return egg


def test_f_zero_builds_the_single_A7a_arm_on_the_declared_egg():
    d = ref.load_declared()
    base = diag.default_egg(d)
    values = ref.scalar_values(d)
    r_b, r_m = rings.ring_geometry(0.26e-6, values["new_membrane_area_at_j1_m2"] / 2.0)
    for alpha in (0.5, 1.0, 2.0):  # as j1_diagnostic_runner.group_g1 built A7a
        single = replace(base, access_shape=("depth", alpha, diag.R_EGG_M, r_m, diag.R_EGG_M - r_b))
        combined = comb.arm_egg(base, alpha=alpha, geometry=comb.j1_geometry(d), f=0.0)
        assert same_egg(combined, single)


def test_the_seal_is_the_declared_cation_selective_access():
    d = ref.load_declared()
    declared = ref.build(d, ref.scalar_values(d, {"access_selectivity": "cation_selective"}))
    built = comb.arm_egg(diag.default_egg(d), alpha=0.0, geometry=comb.j1_geometry(d), seal=True)
    assert same_egg(built, declared)


def test_f_zero_and_a_vanishing_f_reproduce_A7a_alone():
    base = growing()
    single = replace(base, access_shape=comb.depth_shape(1.0, *GEOMETRY))
    assert same_egg(comb.arm_egg(base, alpha=1.0, geometry=GEOMETRY, f=0.0), single)
    vanishing = comb.arm_egg(base, alpha=1.0, geometry=GEOMETRY, f=1e-12)
    assert vanishing.bath_fraction > 0.0
    reference = trace(single)
    assert np.max(np.abs(reference - trace(base))) > 1e-6  # the shape acts: not vacuous
    assert np.max(np.abs(trace(vanishing) - reference)) < 1e-9


@pytest.mark.parametrize(
    "parts",
    [dict(f=0.02), dict(seal=True), dict(a6c_fit=FIT), dict(seal=True, a6c_fit=FIT)],
    ids=["A1", "seal", "A6c", "seal+A6c"],
)
def test_alpha_zero_reproduces_the_level_shifters_alone(parts):
    base = growing()
    shifter = alone(base, **parts)
    assert same_egg(comb.arm_egg(base, alpha=0.0, geometry=GEOMETRY, **parts), shifter)
    # The combined code path with A7a's shape at alpha = 0 (access scale exactly 1).
    r_egg, r_bridge, r_mouth = GEOMETRY
    flat = replace(shifter, access_shape=("depth", 0.0, r_egg, r_mouth, r_egg - r_bridge))
    assert flat.extended
    assert np.max(np.abs(trace(flat) - trace(shifter))) < 1e-9
