"""FR-10's R-ion (Appendix A.3, item B2): a passive cell whose held bath is stepped.

Planted controls: a capacitor of the wrong sign, a capacitor missing its 1e-15, Appendix A's
rounded constants, a late event, and the Nernst potential of K alone in a world with Na and Cl
leaks.
"""

from __future__ import annotations

import copy
import warnings
from decimal import localcontext

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from validation.fr10.references import controls, ion
from validation.fr10.references.common import DIGITS, Constants, dec, exact, load_inputs

INPUTS = load_inputs()
CONST = Constants()


@pytest.fixture(scope="module")
def w2():
    world = ion.parse(INPUTS["R_ion"], INPUTS["constants"])
    return world, ion.solve(world)


def _nernst(T, co, ci, z=1):
    with localcontext() as ctx:
        ctx.prec = DIGITS
        return float(dec(CONST.thermal_voltage(T)) * (dec(co) / dec(ci)).ln() / z)


def test_the_start_is_at_rest_at_the_declared_E_K(w2):
    world, ref = w2
    assert ref["V0_V"] == float(exact(INPUTS["R_ion"]["cell"]["initial_charge_C"]) /
                                exact(INPUTS["R_ion"]["wall"]["capacitance_F"]))
    assert abs(ref["V0_V"] - _nernst(310, 5, 140)) < 1e-16
    assert abs(ref["rest_V_declared"] - _nernst(310, 5, 140)) < 1e-16
    assert abs(ref["V0_V"] + 0.0890156) < 1e-7


def test_flux_identities():
    world = ion.parse(INPUTS["R_ion"], INPUTS["constants"])
    fl = ion.Fluxes(world, world.epochs[0][1], ["K"])
    V = _nernst(310, 5, 140)
    assert abs(fl.J(V, [140.0])[0]) < 1e-15              # zero at the Nernst potential
    assert fl.J(0.0, [140.0])[0] > 0                      # outward positive: c_i > c_o at V = 0
    g = 1e15 * 5e-10 * 1e-10
    assert np.isclose(fl.J(0.0, [140.0])[0], g * (140 - 5), rtol=1e-15)   # u = 0: Fick
    for x in (1e-6, -1e-6, 1e-4):
        assert np.isclose(ion._bern(x), x / np.expm1(x), rtol=1e-12)
    assert ion._bern(0.0) == 1.0


def test_the_methods_agree_and_the_floor_is_small(w2):
    _world, ref = w2
    assert ref["scalar_reduction"]
    assert np.abs(ref["V_m_V"] - ref["V_m_radau_V"]).max() < 1e-12
    assert ref["floor"]["V_m_V"].max() < 1e-12
    assert max(v.max() for v in ref["floor"]["amount_fmol"].values()) < 1e-12
    for s in ("Na", "Cl", "S"):
        assert np.all(ref["amount_fmol"][s] == float(exact(INPUTS["R_ion"]["cell"]
                                                           ["amounts_fmol"][s])))


def test_charge_is_conserved_on_the_invariant(w2):
    world, ref = w2
    C = float(world.capacitance_F)
    lhs = C * (ref["V_m_V"] - ref["V0_V"])
    rhs = 1e-15 * float(CONST.faraday) * (ref["amount_fmol"]["K"] - 140.0)
    bound = 4 * np.spacing(140.0) * 1e-15 * float(CONST.faraday)   # 4 ulps of n_K, as charge
    assert np.abs(lhs - rhs).max() < bound          # coulombs
    assert np.allclose(ref["supply_fmol"]["K"], -(ref["amount_fmol"]["K"] - 140.0), rtol=0,
                       atol=0)


def test_the_two_readings_of_the_zero_current_potential(w2):
    world, ref = w2
    k = int(np.flatnonzero(ref["times_s"] == 0.5)[0])
    a = _nernst(310, 50, ref["amount_fmol"]["K"][k] / 1.0)
    assert abs(ref["zero_current_V"][0] - a) < 1e-16
    b = ref["limit_V"][0]
    fl = ion.Fluxes(world, world.epochs[1][1], ["K"])
    per = 1e-15 ** -1 * float(world.capacitance_F) / float(CONST.faraday)
    nb = 140.0 + per * (b - ref["V0_V"])
    assert abs(fl.J(b, [nb])[0]) < 1e-14
    assert 1.0e-7 < abs(a - b) < 1.5e-7
    assert abs(ref["V_m_V"][-1] - b) < 1e-10
    assert abs(b + 0.0275051) < 1e-7


def _scalar_run(world, sign=1.0, q_scale=1.0, t_max=None):
    """V_m from a hand-built scalar equation (planted capacitor errors), per epoch, to t_max."""
    V0 = world.V0()
    out = []
    times = world.times if t_max is None else world.times[world.times <= t_max]
    V = V0
    for e, (t0, bath) in enumerate(world.epochs):
        fl = ion.Fluxes(world, bath, ["K"])
        q = fl.q * q_scale
        per = 1.0 / fl.q

        def rhs(_t, y, fl=fl, q=q, per=per):
            return [-sign * q * fl.J_list(y[0], [140.0 + per * (y[0] - V0)])[0]]
        last = e + 1 == len(world.epochs)
        t1 = float(times[-1]) if last else float(world.epochs[e + 1][0])
        sel = [float(t) for t in times if float(t0) <= t < t1 or (last and t == t1)]
        sol = solve_ivp(rhs, (float(t0), t1), [V], method="LSODA", rtol=1e-10, atol=1e-14,
                        t_eval=sel if last else sel + [t1])
        if not sol.success:            # a planted run that diverges: no value is a match
            return np.concatenate([out, np.full(len(times) - len(out), np.inf)])
        out += list(sol.y[0][: len(sel)])
        V = sol.y[0][-1]
    return np.array(out)


def test_planted_capacitor_errors_and_rounded_constants_are_caught(w2):
    world, ref = w2
    honest = _scalar_run(world)
    assert np.abs(honest - ref["V_m_V"]).max() < 1e-8
    early = ref["V_m_V"][world.times <= 0.6]       # the planted runs diverge or jump: stop early
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")        # LSODA reports the divergence and the stiffness
        wrong_sign = _scalar_run(world, sign=-1.0, t_max=0.6)
        no_1e15 = _scalar_run(world, q_scale=1e15, t_max=0.6)
    assert np.abs(wrong_sign - early).max() > 1e-2
    assert np.abs(no_1e15 - early).max() > 1e-2
    rounded = controls.ion_rounded_constants(INPUTS["R_ion"], ref)
    assert 1.0e-5 < rounded["V_m_V"] < 2.0e-5


def test_timing_controls_are_first_order_in_dt(w2):
    world, ref = w2
    ladder = INPUTS["R_ion"]["dt_ladder_s"]
    devs = controls.ion_controls(world, ladder, ref)
    late = [devs[f"late@{dt:g}"]["V_m_V"] for dt in ladder]
    orders = np.log2(np.array(late[:-1]) / np.array(late[1:]))
    assert np.all(np.abs(orders - 1.0) < 0.05)
    assert devs["null"]["V_m_V"] > 0.06
    assert devs["accumulate"]["V_m_V"] == 0.0          # one event: the registered zero power


def test_a_world_with_sodium_and_chloride_leaks():
    block = copy.deepcopy(INPUTS["R_ion"])
    block["wall"]["permeability_m_per_s"].update({"Na": 2e-11, "Cl": 2.25e-10})
    block["record_times_s"] = block["record_times_s"][::10]
    world = ion.parse(block, INPUTS["constants"])
    ref = ion.solve(world)
    assert not ref["scalar_reduction"]
    assert np.abs(ref["V_m_V"] - ref["V_m_radau_V"]).max() < 1e-11
    assert ref["zero_current_floor_V"][0] < 1e-15
    # charge conservation over all three ions
    q = sum(world.z[s] * (ref["amount_fmol"][s] - float(world.amounts0[s]))
            for s in ("Na", "K", "Cl"))
    C = float(world.capacitance_F)
    bound = 8 * np.spacing(150.0) * 1e-15 * float(CONST.faraday)
    assert np.abs(C * (ref["V_m_V"] - ref["V0_V"]) - 1e-15 * float(CONST.faraday) * q).max() \
        < bound
    # planted: K's Nernst potential alone is not the zero-current potential here
    k = int(np.flatnonzero(ref["times_s"] == 0.5)[0])
    nernst_k = _nernst(310, 50, ref["amount_fmol"]["K"][k])
    assert abs(nernst_k - ref["zero_current_V"][0]) > 1e-3
    assert ref["limit_V"] == [None]
