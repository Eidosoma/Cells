"""FR-3's registered worlds and design: the inputs equal their generator, the worlds parse under
the declaration's rules, and the references hold on registered worlds with planted controls.

Planted controls:
- a trace above 1e-6 K_d, and internalisation on an inward population (both refused);
- a changed registered value;
- a rate 1% off against an honest third-order engine's error on the ladder;
- accessibility as a kinetic (K) or affinity (A) factor;
- a dropped site free energy in the ledger.
"""

from __future__ import annotations

import copy
import json
import re

import numpy as np
import pytest

from validation.fr3.references import api, design, schemes, worlds

INP = json.loads(worlds.INPUTS.read_text())
W = INP["worlds"]


def test_the_registered_inputs_equal_their_generator_and_parse():
    assert INP == json.loads(json.dumps(worlds.build()))
    for name, w in W.items():
        net = worlds.network(w)
        assert all(p.S > 0 for p in net.populations), name
    bad = copy.deepcopy(W["q3_association"])
    bad["trace_mM"] = 1e-8
    bad["nodes"]["cell_0"]["L_mM"] = 1e-8
    with pytest.raises(ValueError, match="trace above"):
        worlds.network(bad)
    bad = copy.deepcopy(W["q5_inward"])
    bad["populations"][1]["internalisation"] = {"rate_per_s": 0.1, "destination": "cell"}
    with pytest.raises(ValueError, match="outward populations only"):
        worlds.network(bad)
    assert not any("schedule" in json.dumps(w) for w in W.values())       # no bath schedule


def test_the_closed_node_against_its_riccati_form_and_the_registered_values():
    r = api.reference(W["q2_closed"])
    assert np.abs(r["riccati"]["B_fmol"] - r["B_fmol"][:, 0]).max() < 1e-16
    assert abs(r["equilibrium"]["B_fmol"][0] - r["riccati"]["B_eq_fmol"]) < 1e-20
    reg = json.loads(design.VALUES_FILE.read_text())["worlds"]["q2_closed"]
    got = design.thin(design.jsonable(r))
    assert not design._same(reg, got, "q2_closed", rtol=1e-9)
    changed = json.loads(json.dumps(reg))
    changed["heat_pJ"]["values"][10] *= 1 + 1e-6
    assert design._same(changed, got, "q2_closed", rtol=1e-9)
    # planted: the ledger without the site free energy is far from closing
    scale = abs(r["heat_pJ"][-1])
    assert np.abs(r["ledger_residual_pJ"]).max() < 1e-12 * scale
    from validation.fr3.references import energy as en
    net = worlds.network(W["q2_closed"])
    p = net.populations[0]
    Gs = np.array([en.site_free_energy(b, p.S, p.K_d, net.RT) for b in r["B_fmol"][:, 0]])
    assert np.abs(r["ledger_residual_pJ"] - (Gs - Gs[0])).max() > 1e-3 * scale


def test_q1_fast_shows_third_order_and_a_rate_error_stands_far_above_it():
    w = W["q1_fast"]
    net = worlds.network(w)
    ref = api.reference(w)
    exact_state = np.column_stack([ref["n_fmol"], ref["B_fmol"], ref["internalised_fmol"]])
    errs = []
    for dt in INP["dt_ladder_s"]:
        s = schemes.run(net, w["record_times_s"], dt)
        errs.append(np.abs(design._state(s) - exact_state).max())
    orders = np.log2(np.array(errs[:-1]) / np.array(errs[1:]))
    assert np.all(np.abs(orders - 3) < 0.15)
    assert errs[-1] > 100 * ref["n_fmol_floor"].max()
    bad = design._perturbed(w, "k_int_1pct")
    dev = design._dev(design._radau(worlds.network(bad), np.asarray(w["record_times_s"])),
                      {k: ref[k] for k in ("n_fmol", "B_fmol", "internalised_fmol")})
    assert dev > 1e4 * errs[0]


@pytest.mark.parametrize("ctag", ["low", "high"])
def test_accessibility_scales_occupancy_and_the_planted_factors_fail(ctag):
    by = {1.0: W[f"q4_alpha_1_{ctag}"], 0.5: W[f"q4_alpha_1_2_{ctag}"],
          0.25: W[f"q4_alpha_1_4_{ctag}"]}
    acc = api.accessibility(by)
    for a in (0.5, 0.25):
        assert abs(acc["theta_ratio"][a] / a - 1) < 1e-6
        assert abs(acc["relaxation_rate_per_s"][a] / acc["relaxation_rate_per_s"][1.0] - 1) < 1e-8
    d = json.loads(design.DESIGN_FILE.read_text())["power"]["accessibility"][ctag]
    ctrl = d["controls_on_theta_ratio"]
    assert min(v for k, v in ctrl.items() if k.startswith("K_")) > 0.4         # (K) always fails
    if ctag == "high":
        assert min(v for k, v in ctrl.items() if k.startswith("A_")) > 0.4     # (A) at saturation


def test_the_registered_design_is_powered_and_states_its_findings():
    d = json.loads(design.DESIGN_FILE.read_text())
    assert d["inputs"]["git_blob"] == design.git_blob_id(worlds.INPUTS)
    lad = d["power"]["ladder_stand_in"]["q1_fast"]
    assert all(abs(o - 3) < 0.15 for o in lad["observed_order"])
    for name, row in d["power"]["ceilings"].items():
        assert min(m for m in row["honest_margin_per_dt"] if m) >= design.MIN_MARGIN, name
    q = d["power"]["qss_order"]["observed_order"]
    assert all(0.9 < o < 1.1 for o in q)
    for name, e in d["power"]["energy"].items():
        assert e["min_heat_increment_pJ"] >= -e["heat_increment_allowance_pJ"], name
        assert e["max_ledger_residual_pJ"] <= 1e-13 * e["energy_scale_pJ"] + 1e-15, name
    assert any("background guard" in n for n in d["notes"])
    # planted: lower-order steppers fail the third-order claim on q1_fast
    low = lad["planted_lower_orders"]
    assert all(abs(o - 2) < 0.2 for o in low["ssprk22"]["observed_order"])
    assert all(abs(o - 1) < 0.2 for o in low["euler"]["observed_order"])
    ctrl = d["power"]["controls_fmol"]
    assert ctrl["q5_inward"]["cell_volume_dropped"] > 1e-9
    assert ctrl["q1_eps_1e-1"]["cell_volume_dropped_work_pJ"] > 1e-9
    assert min(ctrl["q3_binding_multiplier"].values()) > 1e-7
    assert {z["control"] for z in d["zero_power"]} >= {"the work's control in passive worlds"}


def test_nothing_imports_the_engine():
    for path in sorted(design.HERE.glob("*.py")):
        text = path.read_text()
        assert not re.search(r"^\s*(import cells|from cells)", text, re.M), path
        assert "validation.tissue" not in text, path
