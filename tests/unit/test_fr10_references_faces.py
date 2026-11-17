"""FR-10's R-faces (Appendix A.2, item B1): the exact face chain with a stepped held bath.

Planted controls: a wrong conductance, a late (left-continuous) event, a supply sign error, an
n-for-c confusion on a world of unequal volumes, and a node cut off from the bath.
"""

from __future__ import annotations

import copy
import math

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from validation.fr10.references import controls, faces, schemes
from validation.fr10.references.common import exact, load_inputs

INPUTS = load_inputs()


@pytest.fixture(scope="module")
def w1():
    world = faces.parse(INPUTS["R_faces"])
    return world, faces.solve(world)


def _integrate(world, times, kappa_scale=1.0, unit_volumes=False, epochs=None):
    """The A.2 law integrated face by face with DOP853, epoch by epoch (independent of faces)."""
    epochs = world.epochs if epochs is None else epochs
    V = np.ones(world.n) if unit_volumes else np.array([float(v) for v in world.volume])
    n = np.array([float(v * c) for v, c in zip(world.volume, world.c0, strict=True)])

    def rhs(_t, n, cb):
        c = n / V
        dn = np.zeros_like(n)
        for i, j, k, _ in world.kappa:
            k = float(k) * kappa_scale
            if j is None:
                dn[i] += k * (cb - c[i])
            else:
                f = k * (c[j] - c[i])
                dn[i] += f
                dn[j] -= f
        return dn
    out = np.empty((len(times), world.n))
    texact = [exact(t) for t in times]
    for e, (t0, cb) in enumerate(epochs):
        t1 = epochs[e + 1][0] if e + 1 < len(epochs) else texact[-1]
        idx = [k for k, t in enumerate(texact) if t0 <= t and (t < t1 or e == len(epochs) - 1)]
        span = float(t1 - t0)
        taus = [float(texact[k] - t0) for k in idx]
        if span > 0:
            sol = solve_ivp(rhs, (0.0, span), n, args=(float(cb),), method="DOP853",
                            rtol=1e-13, atol=1e-20, t_eval=sorted(set(taus + [span])))
            at = {float(t): sol.y[:, i] for i, t in enumerate(sol.t)}
            for k, tau in zip(idx, taus, strict=True):
                out[k] = at[tau]
            n = at[span]
        else:
            for k in idx:
                out[k] = n
    return out


def test_conductances_and_relaxation_rates(w1):
    world, ref = w1
    k = faces.kappas(world)
    assert math.isclose(k["face_0"], 10.0, rel_tol=1e-15)
    assert math.isclose(k["face_1"], 5.0, rel_tol=1e-15)
    expected = sorted([-10 - math.sqrt(50), -10 + math.sqrt(50)])
    assert np.allclose(ref["rates_per_s"], expected, rtol=1e-14, atol=0)


def test_primary_meets_the_decimal_truth_within_its_floor(w1):
    world, ref = w1
    truth = faces.solve_decimal(world)
    err = np.abs(ref["amount_fmol"] - truth)
    assert err.max() < 1e-16
    assert np.all(err <= ref["floor_fmol"])
    assert np.abs(ref["amount_expm_fmol"] - truth).max() < 1e-15
    assert ref["floor_fmol"].max() < 1e-15


def test_solution_solves_the_law_and_a_wrong_conductance_is_caught(w1):
    world, ref = w1
    direct = _integrate(world, ref["times_s"])
    assert np.abs(direct - ref["amount_fmol"]).max() < 1e-13      # DOP853 at rtol 1e-13
    planted = _integrate(world, ref["times_s"], kappa_scale=1.01)
    assert np.abs(planted - ref["amount_fmol"]).max() > 1e-6


def test_events_are_right_continuous_and_a_late_event_is_first_order(w1):
    world, ref = w1
    t = ref["times_s"]
    k1 = int(np.flatnonzero(t == 1.0)[0])
    assert np.all(ref["amount_fmol"][: k1 + 1] == 0.001)    # nothing moves before or at 1 s
    assert np.all(ref["amount_fmol"][k1 + 1] > 0.001)
    ladder = INPUTS["R_faces"]["dt_ladder_s"]
    late = [np.abs(faces.solve(world, epochs=controls.shifted_epochs(world.epochs, "late", dt))
                   ["amount_fmol"] - ref["amount_fmol"]).max() for dt in ladder]
    honest = [np.abs(schemes.run_faces(world, dt, "ars_implicit") - ref["amount_fmol"]).max()
              for dt in ladder]
    late_orders = np.log2(np.array(late[:-1]) / np.array(late[1:]))
    honest_orders = np.log2(np.array(honest[:-1]) / np.array(honest[1:]))
    assert np.all(np.abs(late_orders - 1.0) < 0.05)
    assert np.all(np.abs(honest_orders - 2.0) < 0.05)
    # the late event departs far beyond the honest error at every dt
    assert all(a > 100 * b for a, b in zip(late, honest, strict=True))


def test_supply_is_the_nodes_gain_and_a_sign_error_is_caught(w1):
    _world, ref = w1
    gain = ref["amount_fmol"].sum(axis=1) - 0.002
    assert np.abs(ref["supply_fmol"] - gain).max() < 1e-17
    assert np.abs(-ref["supply_fmol"] - gain).max() > 1e-2
    assert np.all(ref["supply_floor_fmol"] < 1e-16)


def test_long_after_a_step_the_nodes_reach_the_bath():
    block = copy.deepcopy(INPUTS["R_faces"])
    block["bath"]["events"] = block["bath"]["events"][:1]
    block["record_times_s"] = [0.0, 1.0, 21.0]
    out = faces.solve(faces.parse(block))
    cb = block["bath"]["events"][0]["concentration_mM"]["S"]
    assert np.allclose(out["amount_fmol"][-1], cb, rtol=1e-15, atol=0)


def test_unequal_volumes_are_solved_and_n_for_c_has_power_only_there():
    block = copy.deepcopy(INPUTS["R_faces"])
    block["finite_nodes"]["ecs_0"]["volume_pL"] = 0.5
    block["finite_nodes"]["ecs_1"]["volume_pL"] = 2.0
    world = faces.parse(block)
    ref = faces.solve(world)
    direct = _integrate(world, ref["times_s"])
    assert np.abs(direct - ref["amount_fmol"]).max() < 1e-13
    confused = _integrate(world, ref["times_s"], unit_volumes=True)
    assert np.abs(confused - ref["amount_fmol"]).max() > 1e-4
    # On W1, whose nodes are 1 pL, the same confusion is invisible: the registered zero power.
    w1 = faces.parse(INPUTS["R_faces"])
    r1 = faces.solve(w1)
    assert np.abs(_integrate(w1, r1["times_s"], unit_volumes=True) - r1["amount_fmol"]).max() \
        < 1e-13


def test_refusals():
    cut = copy.deepcopy(INPUTS["R_faces"])
    cut["finite_nodes"]["ecs_2"] = {"volume_pL": 1.0, "S_mM": 0.001}
    with pytest.raises(ValueError, match="no path to the bath"):
        faces.parse(cut)
    at_zero = copy.deepcopy(INPUTS["R_faces"])
    at_zero["bath"]["events"][0]["time_s"] = 0.0
    with pytest.raises(ValueError, match="does not follow"):
        faces.parse(at_zero)
    back = copy.deepcopy(INPUTS["R_faces"])
    back["bath"]["events"][1]["time_s"] = 0.5
    with pytest.raises(ValueError, match="does not follow"):
        faces.parse(back)
    trace = copy.deepcopy(INPUTS["R_faces"])
    trace["bath"]["events"][1]["concentration_mM"]["S"] = 0.0
    with pytest.raises(ValueError, match="not positive"):
        faces.parse(trace)
