"""Self-tests of item 4's finite-fuel reference (validation/compartment_ph/fuel_reference.py).

They check the pump's rational form against §6's, its static head and reversal; the regeneration's
detailed balance and its sign; the leak against its closed form; and, on the calibrated first case,
depletion with reduced pump activity and recovery, held fuel unaffected, the negative control, the
energy identity, the moieties and every heat. Independence is checked by
tests/unit/test_compartment_ph_references.py, which covers every module of the folder.
"""

import math
import random
from dataclasses import replace

import pytest

from validation.compartment_ph import fuel_reference as fr

REC = (50.0, 99.0, 150.0, 299.0, 310.0, 350.0, 400.0, 600.0)


def test_the_pump_law_is_sections_6_form_with_its_static_head():
    w = fr.acceptance_world()
    m = fr._FuelModel(w)
    rt, c0 = w.rt, w.standard_mM
    rng = random.Random(3)
    for _ in range(200):
        c = {r: 10 ** rng.uniform(-4, 2) for r in ("ATP", "ADP", "Pi", "D", "P", "Y_c", "Y_s")}
        y = m.y0.copy()
        for r in fr.ROWS:
            y[m.i[r]] = c[r] * m.V[0]
        y[m.i["Y_c"]], y[m.i["Y_s"]] = c["Y_c"] * m.V[0], c["Y_s"] * m.V[1]
        _, J, _, _, _ = m.rates(0.0, y)
        _, dG_cyc, _ = m.free_energies(m.conc(y))
        S = 1.0 / (1.0 + w.K_Y_mM / c["Y_c"]) / (1.0 + w.K_ATP_mM / c["ATP"])
        assert J == pytest.approx(w.pump_capacity_fmol_per_s * S * -math.expm1(dG_cyc / rt),
                                  rel=1e-9, abs=1e-300)
        assert -dG_cyc * J >= 0.0  # the pump's heat is never negative
    # Static head: c_Ys/c_Yc = exp(-dG_ATP/(n RT)) makes dG_cyc = 0 and J = 0.
    c = m.conc(m.y0)
    dG_atp = w.dG0_hyd() + rt * math.log(c["ADP"] * c["Pi"] / (c["ATP"] * c0))
    assert dG_atp == pytest.approx(-51.4e3, rel=2e-3)  # held fuel's phosphorylation potential
    y = m.y0.copy()
    y[m.i["Y_s"]] = c["Y_c"] * math.exp(-dG_atp / rt) * m.V[1]
    assert abs(m.rates(0.0, y)[1]) <= 1e-12 * w.pump_capacity_fmol_per_s
    y[m.i["Y_s"]] *= 1.01
    assert m.rates(0.0, y)[1] < 0  # beyond static head the pump reverses


def test_the_regeneration_is_detailed_balanced():
    w = fr.acceptance_world()
    m = fr._FuelModel(w)
    rt = w.rt
    assert w.dG0_reg() == pytest.approx(-29.5e3, rel=1e-12)
    assert w.dG0_hyd() == pytest.approx(-30.5e3, rel=1e-12)
    rng = random.Random(5)
    for _ in range(200):
        y = m.y0.copy()
        for r in fr.ROWS:
            y[m.i[r]] = 10 ** rng.uniform(-3, 2) * m.V[0]
        c, _, _, v, _ = m.rates(0.0, y)
        _, _, dG_reg = m.free_energies(c)
        assert v * dG_reg <= 0.0  # it runs down its own free energy
        assert v == pytest.approx(m.V[0] * w.standard_mM * w.k_f_per_s * (c["D"] / 1e3)
                                  * (c["ADP"] / 1e3) * (c["Pi"] / 1e3) * -math.expm1(dG_reg / rt),
                                  rel=1e-9, abs=1e-300)
    # At equilibrium it vanishes: set P from a_P a_ATP / (a_D a_ADP a_Pi) = exp(-dG0_reg/RT).
    y = m.y0.copy()
    c = m.conc(y)
    P_eq = c["D"] * c["ADP"] * c["Pi"] / (c["ATP"] * w.standard_mM) * math.exp(-w.dG0_reg() / rt)
    y[m.i["P"]] = P_eq * m.V[0]
    assert abs(m.rates(0.0, y)[3]) <= 1e-12 * m.V[0] * w.k_f_per_s


def test_the_leak_alone_follows_its_closed_form():
    w = replace(fr.acceptance_world(), pump_capacity_fmol_per_s=0.0, k_f_per_s=0.0,
                start_mM={**fr.acceptance_world().start_mM, "Y_s": 40.0})
    run = fr.integrate(w, 100.0, record=(1.0, 10.0, 100.0))
    Vc, Vs = w.cell_volume_pL, w.store_volume_pL
    k = 1e15 * w.leak_m_s * w.patch_area_m2 * (1 / Vc + 1 / Vs)
    c_eq = (10.0 * Vc + 40.0 * Vs) / (Vc + Vs)
    for t, r in run.at.items():
        assert r["c"]["Y_s"] == pytest.approx(c_eq + (40.0 - c_eq) * math.exp(-k * t), rel=1e-9)
        assert abs(r["energy_residual_pJ"]) <= 1e-10 * r["Q_pJ"]


@pytest.fixture(scope="module")
def runs():
    """The calibrated first case, held fuel and the negative control, to 600 s at rtol 1e-9 for
    speed; the driver runs them at 1e-11 and records the floor."""
    T, rtol = 600.0, 1e-9
    return dict(finite=fr.integrate(fr.acceptance_world(), T, record=REC, rtol=rtol),
                held=fr.integrate(fr.acceptance_world(held=True), T, record=REC, rtol=rtol),
                control=fr.integrate(fr.acceptance_world(off_windows=()), T, record=REC,
                                     rtol=rtol))


def test_depletion_reduces_the_pump_and_recovery_restores_it(runs):
    f, h, ctl = runs["finite"].at, runs["held"].at, runs["control"].at
    assert f[99.0]["J_cyc"] == pytest.approx(h[99.0]["J_cyc"], rel=1e-2)  # fed, it matches held
    assert f[299.0]["c"]["ATP"] < 1e-2 and f[299.0]["J_cyc"] < 1e-2 * f[99.0]["J_cyc"]
    assert f[299.0]["v"] == 0.0 and f[299.0]["m"] == 0.0
    assert h[299.0]["J_cyc"] == pytest.approx(h[99.0]["J_cyc"], rel=1e-2)  # held: no depletion
    assert f[400.0]["J_cyc"] == pytest.approx(f[99.0]["J_cyc"], rel=1e-2)  # recovered
    assert f[400.0]["c"]["ATP"] == pytest.approx(f[99.0]["c"]["ATP"], rel=1e-2)
    for t in REC:  # the negative control never depletes
        assert ctl[t]["J_cyc"] > 0.9 * ctl[99.0]["J_cyc"]
        assert abs(f[t]["dG_cyc"] / runs["finite"].model.w.rt) <= 80.0  # §6's domain


def test_the_energy_identity_the_moieties_and_the_heats(runs):
    for name, run in runs.items():
        first = run.at[REC[0]]
        scale = max(abs(r["Q_pJ"]) for r in run.at.values())
        for t in REC:
            r = run.at[t]
            assert abs(r["energy_residual_pJ"]) <= 1e-7 * scale, (name, t)
            for key, value in r["moieties"].items():
                assert value == pytest.approx(first["moieties"][key], rel=1e-12), (name, key)
        for key in ("pump", "leak", "reg"):
            series = [run.at[t]["heat_pJ"][key] for t in REC]
            assert all(b >= a - 1e-12 * scale for a, b in zip(series, series[1:], strict=False))
        if name == "held":
            assert run.at[REC[-1]]["W_pJ"] > 0 and run.at[REC[-1]]["heat_pJ"]["reg"] == 0.0
        else:
            assert run.at[REC[-1]]["W_pJ"] == 0.0  # finite fuel: no maintenance
