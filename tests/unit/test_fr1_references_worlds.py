"""FR-1's references on the FR lane's registered worlds (C3 to C11).

Each block is held against an independent integration or identity at the registered record
times, and a planted error must fail:
- a declared rate that disagrees with its parameters;
- a rate 1% off, and a schedule one step late;
- a Lie split, and the swapped palindrome;
- clearance, or the reaction, in the cytosol;
- a dropped volume in G.
"""

from __future__ import annotations

import copy
import json
from fractions import Fraction

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from validation.fr1.references import api, stepmap
from validation.fr1.references.design import INPUTS

INP = json.loads(INPUTS.read_text())
RC = INP["R_closed"]["worlds"]
RL = INP["R_linear"]["worlds"]


def _ode(f, y0, times, rtol=1e-13):
    sol = solve_ivp(f, (0.0, float(times[-1])), y0, method="DOP853", rtol=rtol, atol=1e-22,
                    t_eval=times)
    assert sol.success
    return sol.y.T


def _S(w, node):
    return float(w["nodes"][node]["initial_fmol"]["S"])


def test_declared_rates_are_checked_against_their_parameters():
    api.closed(RC["C4_two_way"])
    bad = copy.deepcopy(RC["C4_two_way"])
    bad["routes"][1]["schedule"][0]["kappa_per_s"] = 20.0 * (1 + 1e-12)
    with pytest.raises(ValueError, match="differs from its parameters"):
        api.closed(bad)
    bad = copy.deepcopy(RC["C5_saturable"])
    bad["routes"][0]["schedule"][0]["b_fmol"] = 5e-3
    with pytest.raises(ValueError, match="differs from its parameters"):
        api.closed(bad)


def test_C3_loading_closed_forms_and_their_controls():
    w = RC["C3_flux"]
    r = api.closed(w)
    t = r["times_s"]
    J = Fraction(w["routes"][0]["schedule"][0]["J_fmol_per_s"])
    for k in (0, 137, 500):
        assert r["amount_fmol"]["ecs_0"][k] == float(Fraction(_S(w, "ecs_0")) +
                                                     J * Fraction(t[k]))
    w = RC["C3_first_order"]
    r = api.closed(w)
    t = r["times_s"][::25]
    y = _ode(lambda _t, y: [-0.5 * y[0], 0.5 * y[0]], [_S(w, "cell_0"), _S(w, "ecs_0")], t)
    assert np.abs(r["amount_fmol"]["cell_0"][::25] - y[:, 0]).max() < 1e-16
    # planted: a rate 1% off departs far beyond the rounding allowance of the design
    w2 = copy.deepcopy(w)
    w2["routes"][0]["schedule"][0]["k_e_per_s"] = 0.505
    dev = np.abs(api.closed(w2)["amount_fmol"]["cell_0"] - r["amount_fmol"]["cell_0"]).max()
    assert dev > 1e6 * 4.5e-15


def test_C4_two_way_and_C5_saturable_against_their_ODEs():
    w = RC["C4_two_way"]
    r = api.closed(w)
    assert r["x_eq"] == 2 / 3 and r["a_per_s"] == 10.0
    a, b = r["a_per_s"], r["b_per_s"]
    y = _ode(lambda _t, y: [-a * y[0] + b * y[1], a * y[0] - b * y[1]],
             [_S(w, "cell_0"), _S(w, "ecs_0")], r["times_s"])
    assert np.abs(r["amount_fmol"]["cell_0"] - y[:, 0]).max() < 1e-16
    w = RC["C5_saturable"]
    r = api.closed(w)
    s = w["routes"][0]["schedule"][0]
    A, B = s["a_fmol_per_s"], s["b_fmol"]
    t = r["times_s"][::50]
    y = _ode(lambda _t, y: [-A * y[0] / (B + y[0])], [_S(w, "ecs_0")], t)
    assert np.abs(r["amount_fmol"]["ecs_0"][::50] - y[:, 0]).max() < 1e-15
    total = r["amount_fmol"]["cell_0"] + r["amount_fmol"]["ecs_0"]
    assert np.allclose(total, _S(w, "cell_0") + _S(w, "ecs_0"), rtol=1e-15, atol=0)


@pytest.fixture(scope="module")
def rungs():
    return {k: api.step_map(w) for k, w in INP["R_step_map"]["worlds"].items()}


def test_step_map_fixed_point_splitting_term_and_order(rungs):
    devs = []
    for key, r in rungs.items():
        dt = r["dt_s"]
        assert abs(r["x"][-1] - r["x_star"]) < 1e-12
        sp = r["splitting"]
        assert abs(sp["relative_over_leading"] - 1) < 10 * dt          # 1 - O(dt)
        assert np.isclose(sp["absolute_displacement"], r["x_eq"] * sp["relative_displacement"],
                          rtol=1e-9)
        closed = api.closed(INP["R_step_map"]["worlds"][key])
        devs.append(np.abs(r["amount_fmol"]["cell_0"] - closed["amount_fmol"]["cell_0"]).max())
        assert np.all(r["floor_fmol"]["cell_0"] <= r["rounding_allowance_fmol"])
    orders = np.log2(np.array(devs[:-1]) / np.array(devs[1:]))
    assert np.all(np.abs(orders - 2) < 0.01)


def test_planted_maps_fail_the_comparison_to_rounding(rungs):
    r = rungs["0.000125"]
    w = INP["R_step_map"]["worlds"]["0.000125"]
    every, steps = int(r["steps"][1]), int(r["steps"][-1])
    for plan in ("lie", "swapped"):
        it = stepmap.iterate(_S(w, "cell_0"), _S(w, "ecs_0"), r["a_per_s"], r["b_per_s"],
                             r["dt_s"], steps, plan=plan, every=every)
        dev = np.abs(it["n_c_fmol"] - r["amount_fmol"]["cell_0"]).max()
        assert dev > 1e3 * r["rounding_allowance_fmol"], plan


def test_linear_worlds_against_their_ODEs_and_planted_sites():
    w = RL["C6_load_and_degrade"]
    r = api.linear(w)
    t = r["times_s"][::30]
    y = _ode(lambda _t, y: [-y[0], y[0] - 2 * y[1], 2 * y[1]],
             [_S(w, "cell_0"), _S(w, "ecs_0"), 0.0], t)
    got = np.column_stack([r["amount_fmol"]["cell_0"]["S"][::30],
                           r["amount_fmol"]["ecs_0"]["S"][::30], r["cleared_fmol"][::30]])
    assert np.abs(got - y).max() < 1e-16
    bad = copy.deepcopy(w)
    bad["clearance_node"] = "cell_0"
    assert np.abs(api.linear(bad)["amount_fmol"]["ecs_0"]["S"] -
                  r["amount_fmol"]["ecs_0"]["S"]).max() > 1e-5
    w = RL["C7_load_and_react"]
    r = api.linear(w)
    assert np.all(r["amount_fmol"]["cell_0"]["P"] == 1e-09)
    assert np.ptp(r["moiety_fmol"]) <= 4 * np.spacing(r["moiety_fmol"][0])
    bad = copy.deepcopy(w)
    bad["reactions"]["convert"]["sites"] = {"outside": [], "cells": ["cell_0"]}
    assert np.abs(api.linear(bad)["amount_fmol"]["ecs_0"]["P"] -
                  r["amount_fmol"]["ecs_0"]["P"]).max() > 1e-5
    w = RL["C8_uptake_path"]
    sub = copy.deepcopy(w)
    sub["record_times_s"] = w["record_times_s"][::50]
    r = api.linear(sub)
    y = _ode(lambda _t, y: [-2 * y[0], 2 * y[0] - y[1], y[1]],
             [_S(w, "ecs_e"), _S(w, "cell_0"), _S(w, "ecs_0")], r["times_s"])
    got = np.column_stack([r["amount_fmol"][n]["S"] for n in ("ecs_e", "cell_0", "ecs_0")])
    assert np.abs(got - y).max() < 1e-15


def test_capacitor_and_energy():
    net = INP["R_capacitor"]["network"]
    v = api.capacitor(net, [-6e-14, -6e-14], [0.0, 1e-17])
    assert v["V_b_V"][0] == 0.0 and v["V_pm_V"][0] == float(Fraction(-6e-14) / Fraction(1e-12))
    assert v["V_b_V"][1] == float(-Fraction(1e-17) / Fraction(1e-13))
    w = INP["R_energy"]["worlds"]["flux_export RK4"]
    e = api.energy(w, INP["constants"])
    end = {n: e["amount_fmol"][n][-1] for n in ("cell_0", "ecs_0")}
    start = {n: _S(w, n) for n in ("cell_0", "ecs_0")}
    vols = {n: w["nodes"][n]["volume_pL"] for n in ("cell_0", "ecs_0")}
    dG = api.free_energy(end, vols, 310.0) - api.free_energy(start, vols, 310.0)
    assert abs(e["dG_pJ"][-1] - dG) <= 1e-15 * abs(api.free_energy(end, vols, 310.0))
    assert e["dG_floor_pJ"].max() < 1e-16
    # planted: G without the volume (ln n for ln(n/V)) changes dG well beyond its floor
    unit = {n: 1.0 for n in vols}
    dG_bad = api.free_energy(end, unit, 310.0) - api.free_energy(start, unit, 310.0)
    assert abs(dG_bad - dG) > 1e-5
