"""Self-tests of FR-5's references (validation/compartment_ph/transfer_reference.py): damage, leak
and reseal, and pH-conditioned transfer of a neutral cargo X on FR-4's compartment state.

They check the exact damage law against an integration of its equation, the condition f, that the
model without FR-5's routes is FR-4's R-closure, X's closed form at fixed pH and damage (every
factor of §8's `multiply`), and, on §13.2's world, the energy identity, charge and material, the
per-route heats and the steady start. Independence is checked by
tests/unit/test_compartment_ph_references.py, which covers every module of the folder.
"""

import math
import random
from dataclasses import replace

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from validation.compartment_ph import ph_reference as ph
from validation.compartment_ph import transfer_reference as tr

SCHEDULE = tr.Damage(k_inj_per_s=1.0, k_res_per_s=0.05, injure=(tr.Window(100.0, 110.0),),
                     reseal=(tr.Window(110.0, math.inf),))


def test_the_damage_law_is_exact_on_constant_pieces():
    ds = tr.DamageSolution(SCHEDULE)
    assert ds.at(0.0) == 0.0 and ds.at(99.999) == 0.0
    d110 = -math.expm1(-10.0)
    assert ds.at(110.0) == pytest.approx(d110, rel=1e-15)
    assert ds.at(150.0) == pytest.approx(d110 * math.exp(-2.0), rel=1e-14)
    assert ds.at(1e4) == pytest.approx(d110 * math.exp(-0.05 * (1e4 - 110.0)), rel=1e-12)
    # Random overlapping windows with partial values (three never sum above 1), against an
    # integration of dd/dt.
    rng = random.Random(7)
    for _ in range(4):
        inj = tuple(tr.Window(s, s + rng.uniform(0.5, 4.0), rng.uniform(0.0, 1.0 / 3.0))
                    for s in sorted(rng.uniform(0.0, 20.0) for _ in range(3)))
        res = tuple(tr.Window(s, s + rng.uniform(0.5, 8.0), rng.uniform(0.0, 1.0 / 3.0))
                    for s in sorted(rng.uniform(0.0, 20.0) for _ in range(3)))
        dm = tr.Damage(k_inj_per_s=rng.uniform(0.1, 3.0), k_res_per_s=rng.uniform(0.01, 1.0),
                       injure=inj, reseal=res, d0=rng.uniform(0.0, 1.0))
        ds = tr.DamageSolution(dm)
        edges = [*ds.breaks, 30.0]
        d = dm.d0
        for t0, t1 in zip(edges, edges[1:], strict=False):
            if t1 <= t0:
                continue
            a, b = ds.rates(t0)
            sol = solve_ivp(lambda t, y, a=a, b=b: [a * (1 - y[0]) - b * y[0]], (t0, t1), [d],
                            method="DOP853", rtol=1e-12, atol=1e-15)
            d = sol.y[0, -1]
            assert ds.at(t1) == pytest.approx(d, abs=1e-11)
            assert 0.0 <= ds.at(0.5 * (t0 + t1)) <= 1.0
    with pytest.raises(ValueError):
        tr.DamageSolution(tr.Damage(d0=1.5))
    with pytest.raises(ValueError):
        tr.DamageSolution(tr.Damage(injure=(tr.Window(0.0, 1.0, 0.7), tr.Window(0.5, 2.0, 0.7))))


def test_the_condition_opens_below_pH50():
    c = tr.Condition(pH50=5.5, hill=4.0)
    assert c.f(5.5) == 0.5
    assert c.f(-1e3) == 1.0 and c.f(1e3) == 0.0  # no overflow at either end
    assert c.f(5.0) > 0.99 > 0.01 > c.f(6.0)
    slope = (c.f(5.5 + 1e-6) - c.f(5.5 - 1e-6)) / 2e-6
    assert slope == pytest.approx(-4.0 * math.log(10.0) / 4.0, rel=1e-6)


def test_without_fr5_routes_the_model_is_fr4s_closure():
    base = ph.acceptance_world()
    m = ph._Model(base, kinetic=False)
    start = tr.Start(Heq_fmol=tuple(m.Heq0), ions_fmol=tuple(m.ions0), X_fmol=(1e-3, 2e-3))
    rec = (0.5, 2.0, 8.0)
    a = tr.integrate(tr.TransferWorld(base=base, start=start), 8.0, record=rec)
    b = ph.integrate(base, 8.0, record=rec)
    for t in rec:
        for key in ("pH_L", "pH_c", "Vb", "cycles", "work_pJ", "heat_pJ"):
            assert a.at[t][key] == pytest.approx(b.at[t][key], rel=1e-9, abs=1e-15), key
        assert (a.at[t]["X_c"], a.at[t]["X_L"]) == (1e-3, 2e-3)


def test_x_at_fixed_pH_and_damage_follows_the_closed_form():
    """No pump, leak or ions, so h and f are constant; d is held at d0. Three routes carry every
    factor of §8: f, d and f d. X relaxes as one closed pair, and its heat is -dG_X."""
    base = replace(ph.acceptance_world(), pump=None, proton_permeability_m_s=0.0,
                   permeability_m_s={})
    m = ph._Model(base, kinetic=False)
    V = m.V
    start = tr.Start(Heq_fmol=tuple(m.Heq0), ions_fmol=tuple(m.ions0),
                     X_fmol=(1e-4 * V[0], 1.0 * V[1]))
    cond = tr.Condition(pH50=7.0, hill=2.0)
    f = cond.f(7.2)
    routes = (tr.CargoRoute("t", 1e-8, conditioned=True), tr.CargoRoute("p", 1e-7, damaged=True),
              tr.CargoRoute("tp", 3e-8, conditioned=True, damaged=True))
    d0 = 0.3
    world = tr.TransferWorld(base=base, start=start, cargo_routes=routes, condition=cond,
                             damage=tr.Damage(d0=d0))
    rec = (0.1, 1.0, 5.0)
    run = tr.integrate(world, 5.0, record=rec)
    PA = base.patch_area_m2 * (f * 1e-8 + d0 * 1e-7 + f * d0 * 3e-8)
    k = 1e15 * PA * (1.0 / V[0] + 1.0 / V[1])
    n0 = (start.X_fmol[0], start.X_fmol[1])
    c_eq = sum(n0) / (V[0] + V[1])
    rt = base.constants.rt

    def g(nc, nL):
        return 1e-3 * rt * sum(n * (math.log(n / v / 1000.0) - 1.0)
                               for n, v in ((nc, V[0]), (nL, V[1])))

    for t in rec:
        r = run.at[t]
        cL = c_eq + (n0[1] / V[1] - c_eq) * math.exp(-k * t)
        assert r["cX_L"] == pytest.approx(cL, rel=1e-9)
        assert r["X_c"] + r["X_L"] == pytest.approx(sum(n0), rel=1e-14)
        assert r["d"] == d0 and r["f"] == pytest.approx(f, rel=1e-12)
        heat_X = sum(r["heat_by_route_pJ"][f"X_{name}"] for name in ("t", "p", "tp"))
        assert heat_X == pytest.approx(g(*n0) - g(r["X_c"], r["X_L"]), rel=1e-8)
        assert abs(r["energy_residual_pJ"]) <= 1e-10 * heat_X
        assert r["J_X"]["tp"] == pytest.approx(r["J_X"]["t"] * d0 * 3.0, rel=1e-12)


@pytest.fixture(scope="module")
def declared():
    """§13.2's world from FR-4's steady state, 0 to 125 s: before, during and after the damage.
    At rtol 1e-9 and from FR-4 at 1800 s, for speed; the driver starts from 3600 s and records
    the floor at 1e-11 and 1e-12."""
    start, steady = tr.steady_start(t_steady=1800.0, rtol=1e-9)
    rec = (1.0, 50.0, 99.0, 100.0, 105.0, 110.0, 115.0, 125.0)
    return dict(start=start, steady=steady, rec=rec,
                run=tr.integrate(tr.acceptance_world(start=start), 125.0, record=rec, rtol=1e-9))


def test_the_start_is_fr4s_steady_state(declared):
    s = declared["steady"]
    n = ph.acceptance_world().pump.n
    assert abs(n * s["J_cyc"] + s["J_H"]) < 1e-10 and abs(s["J_ions"]["K"]) < 1e-10
    assert s["pH_L"] == pytest.approx(5.0946, abs=1e-3)


def test_the_energy_identity_charge_material_and_route_heats(declared):
    run, rec = declared["run"], declared["rec"]
    start = declared["start"]
    for t in rec:
        r = run.at[t]
        assert abs(r["energy_residual_pJ"]) <= 1e-8 * r["work_pJ"]
        assert sum(r["heat_by_route_pJ"].values()) == pytest.approx(r["heat_pJ"], rel=1e-12)
        assert r["Heq_c"] + r["Heq_L"] == pytest.approx(sum(start.Heq_fmol), rel=1e-13)
        assert r["X_c"] + r["X_L"] == pytest.approx(sum(start.X_fmol), rel=1e-13)
        K0 = start.ions_fmol[0]["K"] + start.ions_fmol[1]["K"]
        assert r["ions_c"]["K"] + r["ions_L"]["K"] == pytest.approx(K0, rel=1e-13)
        assert abs(r["phi_c"]) <= 1e-9
        moved = r["moved_fmol"]  # c to L, since the start
        assert moved["X_transfer"] + moved["X_pore"] == pytest.approx(
            r["X_L"] - start.X_fmol[1], rel=1e-9)
    # Every route's heat accumulates without decreasing: each is passive or the pump's -dG_cyc.
    for name in run.model.route_names:
        series = [run.at[t]["heat_by_route_pJ"][name] for t in rec]
        assert all(b >= a - 1e-12 for a, b in zip(series, series[1:], strict=False)), name
    # The pores open only with damage.
    assert run.at[99.0]["J_H_pore"] == 0.0 and run.at[99.0]["J_X"]["pore"] == 0.0
    assert run.at[105.0]["d"] > 0.99 and run.at[105.0]["J_H_pore"] < 0  # protons leave the lumen
    assert np.isfinite([run.at[t]["pH_L"] for t in rec]).all()
