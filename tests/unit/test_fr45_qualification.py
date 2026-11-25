"""FR-4's and FR-5's qualification tools on the host: the judge, the drafter, the guards.

No engine run and no reference run (tier 1): synthetic records with known orders, crossings,
rates and budgets exercise the judge's arithmetic and every machine criterion of both protocols;
the generator's and the judge's judged entries refuse unregistered protocols, sources other than a
clean snapshot, stand-ins, quick or incomplete runs and existing directories before writing
anything; registration takes the record's status and changes nothing else; the drafter's section
is the checked-in one. The tests are status-agnostic (MG0c's form): registration changes the status
and adds the record alone, so their outcomes do not change with it.
"""

import hashlib
import json
import math

import pytest

from validation import id_table
from validation.compartment_ph_engine import definitions as defs
from validation.compartment_ph_engine import dt_study
from validation.compartment_ph_engine.parameters import ARM_R, ARM_T, CHARGE_PER_FMOL
from validation.tissue import compartment_ph_judge as judge
from validation.tissue import compartment_ph_protocol as drafter
from validation.tissue import compartment_ph_qualification as generator

PROTOCOLS = {k: id_table.load(p) for k, p in generator.PROTOCOLS.items()}


# ------------------------------------------------------------------------ synthetic records


SPECIES = [s for s, _ in defs.SPECIES]


def amounts(series, n, cargo):
    """Every node's amounts for the allowance: H, K and X move between cell and lumen with their
    totals conserved; every other row is constant."""
    out = {node: {s: [1.0 + k] * n for k, s in enumerate(SPECIES + (["X"] if cargo else []))}
           for node in (defs.CELL, defs.LUMEN, defs.BATH)}
    moving = dict(H=("Heq_L", 108.0), K=("K_L", 149.16), X=("X_L", 0.4843288))
    for s, (name, total) in moving.items():
        if name in series:
            out[defs.LUMEN][s] = list(series[name])
            out[defs.CELL][s] = [total - v for v in series[name]]
    return out


def part(dt, end, series, *, stage=None, ledgers=None, start=None):
    out = dict(kind="engine", dt_s=dt, end_s=end, steps=round(end / dt), admitted=True,
               completed=True, refusal=None, record_s=[float(t) for t in range(round(end) + 1)],
               series=series, stage=stage or {}, ledgers=ledgers or {},
               amounts_fmol=amounts(series, round(end) + 1, "X_L" in series))
    if start is not None:
        out["start"] = start
    return out


def grow(t, tau):
    return 1.0 - math.exp(-t / tau)


def fr4_series(t, dt, order=2, k1=False, k2=False):
    e = (dt / 1e-3) ** order if dt else 0.0
    drop = 0.06 if k1 else (-0.5 if k2 else 2.1)
    ph = [7.2 - drop * grow(s, 100) + 1e-6 * e * grow(s, 50) for s in t]
    flows = [0.1 * s for s in t]
    return dict(
        pH_L=ph, pH_c=[7.2 + 0.018 * grow(s, 100) for s in t],
        V_b=[-7.3e-3 * grow(s, 5) + 1e-8 * e * grow(s, 50) for s in t],
        K_L=[9.16 - 2.17 * grow(s, 100) + 1e-6 * e * grow(s, 50) for s in t],
        Heq_L=[2.6 + 0.5 * grow(s, 100) + 1e-6 * e * grow(s, 50) for s in t],
        cycles=[2e-3 * s + 1e-6 * e * grow(s, 50) for s in t],
        energy_residual_pJ=[1e-4 * e * f for f in flows], energy_flows_pJ=flows)


def k3_refused(reason="envelope"):
    """K3 as the engine records it (the lead's ruling): refused at the definition, its reason
    attributed by the generator."""
    return dict(kind="engine", dt_s=1e-3, end_s=900.0, steps=0, admitted=False, completed=False,
                refusal="definition: Invalid resolved pump @3 definition: Initial resolved "
                        "channel/junction/pump domain invalid",
                refusal_reason=reason, record_s=[], series={}, stage={}, ledgers={},
                amounts_fmol={})


def fr4_parts(order=2):
    """A complete FR-4 run that passes every criterion at order 2 (its ladder's errors at
    `order`)."""
    stage = dict(envelope_max_lag_ph=1e-5, envelope_stages_beyond=0, cytosol_pH_min=7.2,
                 cytosol_pH_max=7.218)
    ledgers = dict(charge_residual_C=1e-21, charge_tolerance_C=1e-18)
    t = [float(s) for s in range(901)]
    parts = {}
    for name, dt in generator.FR4_RUNGS.items():
        parts[name] = part(dt, 900.0, fr4_series(t, dt, order), stage=stage, ledgers=ledgers)
    parts["control_k1"] = part(1e-3, 900.0, fr4_series(t, 1e-3, k1=True), stage=stage,
                               ledgers=ledgers)
    parts["control_k2"] = part(1e-3, 900.0, fr4_series(t, 1e-3, k2=True), stage=stage,
                               ledgers=ledgers)
    parts["control_k3"] = k3_refused()  # Refused at the definition through the envelope.
    exact = fr4_series(t, 0.0)
    kinetic = dict(exact, pH_L=[p + 2.0 * math.exp(-s) for p, s in zip(exact["pH_L"], t,
                                                                           strict=True)])
    parts["reference"] = dict(kind="reference", admitted=True, completed=True, record_s=t,
                              worlds=dict(declared=dict(record_s=t, series=exact),
                                          floor=dict(record_s=t, series=exact),
                                          control_k1=dict(record_s=t,
                                                          series=fr4_series(t, 0.0, k1=True)),
                                          kinetic_outside=dict(record_s=t, series=kinetic)))
    return parts


B = 1e-3 * 0.0654498  # X's budget (fmol) for X_L(0) = 0.0654498 fmol


def fr5_arm_series(arm, t, dt, *, control=False, exact_d=False):
    w0 = 60.0 if arm == "T" else 100.0
    w1 = w0 + 60.0
    e = (dt / 5e-4) ** 2 if dt else 0.0

    def bump(s):
        if s < w0:
            return 0.0
        if s < w1:
            return grow(s - w0, 20)
        return grow(60.0, 20) * math.exp(-(s - w1) / 100)

    ph = [5.0946 + (0.0 if control and arm == "R" else 0.8) * bump(s) for s in t]
    rate = [0.0] + [(8.0 if (control and arm == "T") or p < 5.5 else 0.4) * B for p in ph[1:]]
    m_cond = []
    for r in rate:
        m_cond.append((m_cond[-1] if m_cond else 0.0) - r)
    # The step error moves X through the route, booked as transferred.
    m_cond = [m + 1e-3 * B * e * grow(s, 50) for m, s in zip(m_cond, t, strict=True)]
    pore_on = arm == "R" and not control
    m_pore = [-0.87 * 0.0654498 * grow(max(s - w0, 0.0), 5) if pore_on else 0.0 for s in t]
    x_l = [0.0654498 + a + b for a, b in zip(m_cond, m_pore, strict=True)]
    x_c = [0.418879 - a - b for a, b in zip(m_cond, m_pore, strict=True)]
    d = [bump(s) + (0.0 if exact_d else 1e-7 * e * grow(s, 50)) for s in t]
    pump = [4e-3 * s for s in t]
    leak = [-1e-3 * s for s in t]
    pore_h = [-1e-4 * bump(s) * s for s in t]
    out = dict(
        pH_L=[p + 1e-7 * e * grow(s, 50) for p, s in zip(ph, t, strict=True)],
        pH_c=[7.218] * len(t), V_b=[-7.33e-3 + 1e-8 * bump(s) + 1e-9 * e * grow(s, 50)
                                    for s in t],
        X_L=x_l, X_c=x_c, d=d, f=[1.0 / (1.0 + 10 ** (4 * (p - 5.5))) for p in ph],
        moved_X_transfer=m_cond, moved_H_pump=pump, moved_H_leak=leak, moved_H_pore=pore_h,
        Heq_L=[2.6 + a + b + c for a, b, c in zip(pump, leak, pore_h, strict=True)],
        Heq_c=[105.0 - a - b - c for a, b, c in zip(pump, leak, pore_h, strict=True)],
        # The energy residual's step error: 2e-5 of the flows at the declared 0.5 ms, second order.
        energy_residual_pJ=[1e-5 * e * s for s in t], energy_flows_pJ=[0.5 * s for s in t],
        **{f"heat_{r}_pJ": [0.01 * s for s in t] for r in (
            "proton_leak_0", "proton_pore_0", "bounding_0_K", "cargo_transfer_0",
            "cargo_pore_0")})
    if arm == "R":
        out["moved_X_pore"] = m_pore
        out["X_L"] = x_l
    return out


def fr5_parts(*, exact_d=True, extract_sha="a" * 64):
    t = [float(s) for s in range(401)]
    stage = dict(envelope_max_lag_ph=1e-4, envelope_stages_beyond=0, cytosol_pH_min=7.21,
                 cytosol_pH_max=7.22)
    ledgers = dict(charge_residual_C=1e-21, charge_tolerance_C=1e-18)
    start = dict(extract_sha256=extract_sha, producer="engine", time_s=1800.0)
    parts = dict(start=dict(kind="engine", admitted=True, completed=True,
                            extract_sha256=extract_sha))
    worlds = {}
    for arm in ("T", "R"):
        for name, (a, dt) in generator.FR5_RUNGS.items():
            if a == arm:
                parts[name] = part(dt, 400.0, fr5_arm_series(arm, t, dt, exact_d=exact_d),
                                   stage=stage, ledgers=ledgers, start=start)
        parts[f"{arm}_control"] = part(5e-4, 400.0, fr5_arm_series(arm, t, 5e-4, control=True),
                                       stage=stage, ledgers=ledgers, start=start)
        exact = fr5_arm_series(arm, t, 0.0)
        worlds[arm] = dict(record_s=t, series=exact)
        worlds[f"{arm}_floor"] = dict(record_s=t, series=exact)
        worlds[f"{arm}_control"] = dict(record_s=t, series=fr5_arm_series(arm, t, 0.0,
                                                                          control=True))
    parts["reference"] = dict(kind="reference", admitted=True, completed=True, worlds=worlds,
                              record_s=t, start=start)
    return parts


def failed(parts, protocol):
    _, evaluated = judge.verdict(parts, protocol)
    return sorted(c["id"] for c in evaluated["criteria"] if c["judged"] and not c["passed"])


# ------------------------------------------------------------------------ the arithmetic


def test_a_second_order_ladder_is_resolved_in_band_and_a_first_order_one_fails():
    parts = fr4_parts()
    rungs = list(generator.FR4_RUNGS)
    good = judge.ladder(parts, rungs, "pH_L", (1.8, 2.2))
    assert [c["cls"] for c in good["classes"]] == ["resolved", "resolved"]
    assert [c["order"] for c in good["classes"]] == pytest.approx([2.0, 2.0], abs=1e-6)
    assert good["passes"] == 1 and good["judged_class"] == "resolved"
    bad = judge.ladder(fr4_parts(order=1), rungs, "pH_L", (1.8, 2.2))
    assert bad["order_finest"] == pytest.approx(1.0, abs=1e-6) and bad["passes"] == 0


def test_differences_under_their_floors_are_at_rounding_and_pass():
    parts = fr4_parts()
    for name in generator.FR4_RUNGS:  # errors of 1e-13 pH: under N eps max|pH| at every rung
        dt = generator.FR4_RUNGS[name]
        parts[name]["series"]["pH_L"] = [7.2 + 1e-13 * (dt / 1e-3) ** 2 * grow(s, 50)
                                         for s in range(901)]
    got = judge.ladder(parts, list(generator.FR4_RUNGS), "pH_L", (1.8, 2.2))
    assert got["judged_class"] == "at_rounding" and got["passes"] == 1
    assert got["at_rounding_every_pair"] == 1 and got["order_finest"] is None


def test_the_four_classes_of_two_differences_each_with_its_floor():
    """The lead's ruling (15 November 2026): resolved in band; at rounding passes; mixed passes
    unless its lower bound log2(D1/F2) exceeds the band's upper edge; reversed fails."""

    def pair(d, floor):
        return dict(difference=d, floor=floor, above=d > 0 and d >= floor)

    band = (1.8, 2.2)
    assert judge.classify(pair(4e-6, 1e-9), pair(1e-6, 1e-9), band)["passes"] == 1
    assert judge.classify(pair(8e-6, 1e-9), pair(1e-6, 1e-9), band)["passes"] == 0  # order 3
    rounding = judge.classify(pair(5e-10, 1e-9), pair(9e-10, 2e-9), band)
    assert rounding["cls"] == "at_rounding" and rounding["passes"] == 1
    mixed = judge.classify(pair(3e-9, 1e-9), pair(1e-9, 2e-9), band)
    assert mixed["cls"] == "mixed" and mixed["lower_bound"] == pytest.approx(math.log2(1.5))
    assert mixed["passes"] == 1
    above = judge.classify(pair(1e-7, 1e-9), pair(1e-9, 2e-9), band)  # bound log2(50) > 2.2
    assert above["cls"] == "mixed" and above["passes"] == 0
    assert judge.classify(pair(1e-7, 1e-9), pair(1e-9, 2e-9), (1.8, None))["passes"] == 1
    reversed_ = judge.classify(pair(5e-10, 1e-9), pair(3e-9, 2e-9), band)
    assert reversed_["cls"] == "reversed" and reversed_["passes"] == 0


def test_the_material_allowance_is_computed_by_the_judge_from_the_records():
    """Floor plus N eps max over records of the species' total (the lead's ruling); a leak of H
    beyond it fails J6, and the engine's tolerance is never read."""
    protocol = PROTOCOLS["fr4"]
    derived = judge.derive(fr4_parts(), protocol)
    h = derived["ledgers"]["material"]["parts"]["rung_1ms"]["H"]
    total = 108.0 + 1.0 + 3.0 * 1.0  # the lumen's and cell's H, and the bath's constant row
    assert h["allowance_fmol"] == pytest.approx(1e-16 + 900000 * judge.EPS * total, rel=1e-6)
    parts = fr4_parts()
    lumen = parts["rung_1ms"]["amounts_fmol"][defs.LUMEN]["H"]
    lumen[-1] += 1e-6  # material appears from nothing
    assert failed(parts, protocol) == ["J6_material"]


def test_the_richardson_error_is_the_true_error_of_a_second_order_rung():
    parts = fr4_parts()
    exact = parts["reference"]["worlds"]["declared"]
    true = judge.max_abs_difference(parts["rung_1ms"], exact, "pH_L")
    assert judge.richardson(parts, "rung_1ms", "rung_0p5ms", "pH_L") == pytest.approx(true,
                                                                                   rel=1e-9)


def test_crossings_and_mean_rates_interpolate_between_records():
    t = [0.0, 1.0, 2.0, 3.0, 4.0]
    up, down = judge.crossings(t, [5.0, 5.4, 5.8, 5.6, 5.2], 5.5)
    assert up == pytest.approx(1.25) and down == pytest.approx(3.25)
    assert judge.crossings(t, [5.0] * 5, 5.5) == (None, None)
    assert judge.crossings(t, [5.0, 5.6, 5.7, 5.8, 5.9], 5.5)[1] is None
    m = [0.0, -2.0, -4.0, -4.5, -5.0]
    assert judge.mean_rate(t, m, 0.0, 2.0) == pytest.approx(2.0)
    assert judge.mean_rate(t, m, 1.5, 3.5) == pytest.approx((4.75 - 3.0) / 2.0)
    assert judge.mean_rate(t, m, None, 3.0) is None and judge.at_time(t, m, 9.0) is None


def test_undefined_values_are_none_never_nan():
    assert dt_study.observed_order(1.0, 1.0, 1.0) is None
    assert judge.log2_ratio(0.0, 1.0) is None and judge.ratio(1.0, 0.0) is None
    assert judge.max_or_none([1.0, None]) is None and judge.max_or_none([]) is None


# ------------------------------------------------------------------------ whole verdicts


def test_a_complete_fr4_run_passes_every_criterion_and_each_planted_error_fails_its_own():
    protocol = PROTOCOLS["fr4"]
    assert failed(fr4_parts(), protocol) == []
    assert failed(fr4_parts(order=1), protocol) == [  # the energy residual falls at order 1
        "J2_order_K_L", "J2_order_V_b", "J2_order_cycles", "J2_order_pH_L", "J6_energy_falls"]
    parts = fr4_parts()
    parts["rung_1ms"]["series"]["pH_L"] = [p + 2e-3 for p in parts["rung_1ms"]["series"]["pH_L"]]
    assert {"J4_reference_pH", "J4_start"} <= set(failed(parts, protocol))
    parts = fr4_parts()
    parts["control_k2"]["series"] = fr4_series([float(s) for s in range(901)], 1e-3)
    assert failed(parts, protocol) == ["J7_K2_planted_sign"]  # a control that is not caught
    parts = fr4_parts()
    parts["rung_0p5ms"]["stage"]["envelope_stages_beyond"] = 3
    assert failed(parts, protocol) == ["J5_envelope_count"]


def test_j4_and_k2s_catch_judge_every_buffered_node():
    """The lead's ruling (15 November 2026): J4, and so K2's catch, judges the pH of the lumen and
    the cytosol, the maximum over both nodes and every record; FR-5's pH budget the same."""
    protocol, t = PROTOCOLS["fr4"], [float(s) for s in range(901)]
    parts = fr4_parts()
    for rung in ("rung_1ms", "rung_0p5ms"):  # The same at the half rung: J3 sees no step error.
        s = parts[rung]["series"]
        s["pH_c"] = [p + 1.5e-3 * grow(r, 10) for p, r in zip(s["pH_c"], t, strict=True)]
    assert failed(parts, protocol) == ["J4_reference_pH"]  # the cytosol alone, the lumen exact
    derived = judge.derive(parts, protocol)["reference"]
    assert derived["pH_max_abs"] == derived["pH_c_max_abs"] > derived["pH_L_max_abs"]
    parts = fr4_parts()
    uncaught = fr4_series(t, 1e-3)  # K2's lumen as the declared world's: caught by the cytosol
    for shift, expected in ((3e-3, []), (1e-3, ["J7_K2_planted_sign"])):
        k2 = dict(uncaught, pH_c=[p - shift * grow(r, 10) for p, r in zip(uncaught["pH_c"], t,
                                                                         strict=True)])
        parts["control_k2"]["series"] = k2
        assert failed(parts, protocol) == expected
    del parts["control_k2"]["series"]["pH_c"]  # a node missing fails through None
    assert failed(parts, protocol) == ["J7_K2_planted_sign"]
    protocol, t = PROTOCOLS["fr5"], [float(s) for s in range(401)]
    for arm in ("T", "R"):
        parts = fr5_parts()
        for rung in (f"{arm}_rung_0p5ms", f"{arm}_rung_0p25ms"):  # J3 sees no step error.
            s = parts[rung]["series"]
            s["pH_c"] = [p + 1.5e-3 * grow(r, 10) for p, r in zip(s["pH_c"], t, strict=True)]
        assert failed(parts, protocol) == [f"J4_{arm}_pH"]


def test_j3_and_j4_start_judge_every_buffered_node():
    """The lead's later ruling (15 November 2026): J3's pH state error and J4_start judge every
    buffered node too, the maximum over the lumen and the cytosol (V_b as written): a cytosol-only
    step error at the half rung fails J3, and a cytosol-only row-0 offset fails J4_start, the
    lumen's in budget; FR-5's arms the same."""
    protocol, t = PROTOCOLS["fr4"], [float(s) for s in range(901)]
    parts = fr4_parts()
    s = parts["rung_0p5ms"]["series"]
    s["pH_c"] = [p + 1e-3 * grow(r, 10) for p, r in zip(s["pH_c"], t, strict=True)]
    assert failed(parts, protocol) == ["J3_state_error_pH"]
    derived = judge.derive(parts, protocol)["state_error"]
    assert derived["pH"] == derived["pH_c"] > derived["pH_L"]
    parts = fr4_parts()
    s = parts["rung_1ms"]["series"]
    s["pH_c"] = [s["pH_c"][0] + 1e-9, *s["pH_c"][1:]]
    assert failed(parts, protocol) == ["J4_start"]
    protocol, t = PROTOCOLS["fr5"], [float(s) for s in range(401)]
    for arm in ("T", "R"):
        parts = fr5_parts()
        s = parts[f"{arm}_rung_0p25ms"]["series"]
        s["pH_c"] = [p + 1e-3 * grow(r, 10) for p, r in zip(s["pH_c"], t, strict=True)]
        assert failed(parts, protocol) == [f"J3_{arm}_pH"]
        parts = fr5_parts()
        s = parts[f"{arm}_rung_1ms"]["series"]
        s["pH_c"] = [s["pH_c"][0] + 1e-9, *s["pH_c"][1:]]
        assert failed(parts, protocol) == [f"J4_{arm}_start"]


def test_a_missing_or_refused_part_fails_its_criteria_through_none():
    protocol = PROTOCOLS["fr4"]
    parts = fr4_parts()
    del parts["rung_0p25ms"]
    got = failed(parts, protocol)
    assert "J1_admission" in got and "J2_order_pH_L" in got
    parts = fr4_parts()
    parts["rung_1ms"].update(completed=False, refusal="refused at run time")
    assert {"J1_admission", "J3_state_error_pH", "J4_reference_pH"} <= set(
        failed(parts, protocol))


def test_a_complete_fr5_run_passes_every_criterion_and_its_claims_and_controls_can_fail():
    protocol = PROTOCOLS["fr5"]
    assert failed(fr5_parts(), protocol) == []
    derived = judge.derive(fr5_parts(), protocol)
    claims = derived["T"]["claims"]["engine"]
    up, down = claims["up_s"], claims["down_s"]
    j = math.ceil(down)  # the step (j - 1, j] holding the down-crossing carries the 8 B/s rate
    above = (0.4 * (j - 1 - up) + 8.0 * (down - (j - 1))) / (down - up)
    assert claims["above_over_pre"] == pytest.approx(above / 8.0, rel=1e-4)
    assert claims["pre_damage_rate_per_budget"] == pytest.approx(8.0, rel=1e-4)
    assert derived["R"]["claims"]["engine"]["released_in_window"] == pytest.approx(
        0.87 * grow(60.0, 5), rel=1e-12)
    parts = fr5_parts()
    parts["T_control"]["series"] = fr5_arm_series("T", [float(s) for s in range(401)], 5e-4)
    assert {"J10_T_control_X_L", "J10_T_control_transfer"} <= set(failed(parts, protocol))
    parts = fr5_parts()
    s = parts["R_rung_0p5ms"]["series"]
    s["moved_X_pore"] = [0.5 * v for v in s["moved_X_pore"]]
    assert "J11_R_release" in failed(parts, protocol)


def test_records_that_end_inside_the_injury_window_leave_the_release_undefined_not_a_crash():
    """A completed part whose records end inside arm R's window (100 to 160 s), as a 20 s quick
    pass's do (found by FR-5's dry run, 16 November 2026): the release through the pore is
    undefined (None), so J11_R_release fails, and the judge still writes its verdict."""
    parts = fr5_parts()
    rung = parts["R_rung_0p5ms"]
    rung["record_s"] = rung["record_s"][:121]
    rung["series"] = {k: v[:121] for k, v in rung["series"].items()}
    derived = judge.derive(parts, PROTOCOLS["fr5"])
    assert derived["R"]["claims"]["engine"]["released_in_window"] is None
    assert derived["R"]["claims"]["reference"]["released_in_window"] is not None
    assert "J11_R_release" in failed(parts, PROTOCOLS["fr5"])


def test_an_exact_damage_state_passes_and_a_resolved_one_fails_its_exactness():
    """FR-5's Q3, ruled: d exact at rounding on every rung pair, fixed before the run."""
    assert failed(fr5_parts(exact_d=True), PROTOCOLS["fr5"]) == []
    assert failed(fr5_parts(exact_d=False), PROTOCOLS["fr5"]) == ["J2_R_d_exact", "J2_T_d_exact"]


def test_route_heat_is_judged_on_the_routes_the_engine_does_not_refuse_per_step():
    """FR-5's Q6, ruled: a fall in an exactly booked cargo route's heat is the engine's refusal
    to make, not the judge's; a fall in the proton leak's fails J7."""
    protocol = PROTOCOLS["fr5"]
    parts = fr5_parts()
    heat = parts["T_rung_0p5ms"]["series"]["heat_cargo_transfer_0_pJ"]
    heat[200] -= 0.02  # the route's heat rises 0.01 pJ per record: this one falls
    assert failed(parts, protocol) == []
    derived = judge.derive(parts, protocol)
    assert derived["T"]["energy"]["route_heat_increments_pJ"]["cargo_transfer_0"] < -1e-3
    heat = parts["T_rung_0p5ms"]["series"]["heat_proton_leak_0_pJ"]
    heat[200] -= 0.02
    assert failed(parts, protocol) == ["J7_T_route_heat"]


def test_the_energy_line_judges_f4_on_the_coarsest_rung_and_its_fall_beside_the_declared_one():
    """FR-5's energy criterion as settled before registration (17 November 2026): the dt study's F4
    as written first, the residual over flows <= 2e-3 at 1 ms (the coarsest rung) and falling at
    second order, with the declared 0.5 ms kept. A residual over 2e-3 at 1 ms alone, which a reading
    of the declared rung passes, fails J7_T_energy; a first-order fall fails J7_T_energy_falls."""
    protocol = PROTOCOLS["fr5"]
    parts = fr5_parts()
    coarse = parts["T_rung_1ms"]["series"]
    coarse["energy_residual_pJ"] = [3e-3 * f for f in coarse["energy_flows_pJ"]]
    assert judge.derive(parts, protocol)["T"]["energy"]["over_flows_at_declared"] < 2e-3
    assert failed(parts, protocol) == ["J7_T_energy"]
    parts = fr5_parts()
    for name, (arm, dt) in generator.FR5_RUNGS.items():
        if arm == "T":
            s = parts[name]["series"]
            s["energy_residual_pJ"] = [2e-5 * (dt / 5e-4) * f for f in s["energy_flows_pJ"]]
    assert failed(parts, protocol) == ["J7_T_energy_falls"]


def test_every_prose_criterion_has_a_judged_machine_criterion():
    for protocol in PROTOCOLS.values():
        machine = [c["id"] for c in protocol["judge"]["criteria"] if c["judged"]]
        for prose in protocol["criteria"]:
            j = prose.split("_")[0]
            assert any(m.split("_")[0] == j for m in machine), (protocol["id"], prose)


def test_the_checked_in_judge_sections_are_the_drafters():
    for which, protocol in PROTOCOLS.items():
        assert protocol["judge"] == json.loads(json.dumps(drafter.judge_section(which)))
        assert protocol["judged_parts"] == list(generator.PARTS[which])
        assert protocol["questions_for_the_lead"] == []
        for asked, ruling in zip(drafter.ASKED[which], drafter.RULINGS[which], strict=True):
            assert any(a.startswith(asked) and ruling in a
                       for a in protocol["questions_answered"])
            assert f"{drafter.RULED} {which.upper()}'s {ruling}" in protocol["disclosures"]
        assert prose_mismatches(protocol, which) == []


def registered(protocol):
    """Registered in register's form: the status begins 'registered' and the registration record's
    status equals it."""
    status, record = protocol.get("status"), protocol.get("registration")
    return (isinstance(status, str) and status.startswith("registered")
            and isinstance(record, dict) and record.get("status") == status)


def prose_mismatches(protocol, which):
    """The drafter's PROSE leaves that the protocol does not hold. Once registered, the status leaf
    is the record's (register replaces it), so it alone is exempt, and only then."""
    out = []
    for path, text in drafter.PROSE[which].items():
        if path == ("status",) and registered(protocol):
            continue
        leaf = protocol
        for key in path:
            leaf = leaf[key]
        if leaf != text:
            out.append(path)
    return out


@pytest.mark.parametrize("which", ["fr4", "fr5"])
def test_the_status_leaf_is_the_drafters_while_proposed_and_the_records_once_registered(
        tmp_path, which):
    """The checked-in protocol in either state: PROPOSED, every PROSE leaf the drafter's; registered
    by register, its status the record's and every other leaf the drafter's. Planted: a changed
    status while PROPOSED, a 'registered' status without its matching record, and a changed scope
    once registered each fail."""
    proposed = {k: v for k, v in PROTOCOLS[which].items() if k != "registration"}
    proposed["status"] = drafter.PROSE[which][("status",)]
    assert prose_mismatches(proposed, which) == []
    assert prose_mismatches(dict(proposed, status="PROPOSED (another text)"), which) == [
        ("status",)]
    path, record = tmp_path / "protocol.json", tmp_path / "record.json"
    path.write_text(json.dumps(proposed))
    record.write_text(json.dumps(dict(status="registered by the lead (a test)")))
    done = drafter.register(path, record)
    assert registered(done) and prose_mismatches(done, which) == []
    unmatched = dict(done, registration=dict(status="registered otherwise"))
    assert not registered(unmatched)
    assert prose_mismatches(unmatched, which) == [("status",)]
    assert prose_mismatches(dict(done, scope="another scope"), which) == [("scope",)]


@pytest.mark.parametrize("which", ["fr4", "fr5"])
def test_draft_refuses_a_registered_protocol_and_leaves_it_as_registered(tmp_path, which):
    """draft never overwrites a registered protocol's status or registration: it refuses before
    writing, both for register's form and for a PROPOSED status carrying a registration record."""
    proposed = {k: v for k, v in PROTOCOLS[which].items() if k != "registration"}
    proposed["status"] = drafter.PROSE[which][("status",)]
    path, record = tmp_path / "protocol.json", tmp_path / "record.json"
    path.write_text(json.dumps(proposed))
    record.write_text(json.dumps(dict(status="registered by the lead (a test)")))
    drafter.register(path, record)
    before = path.read_bytes()
    with pytest.raises(SystemExit, match="only a PROPOSED protocol"):
        drafter.draft(which, path)
    assert path.read_bytes() == before
    path.write_text(json.dumps(dict(proposed, registration=dict(status="registered (a test)"))))
    before = path.read_bytes()
    with pytest.raises(SystemExit, match="carries a registration record"):
        drafter.draft(which, path)
    assert path.read_bytes() == before


# ------------------------------------------------------------------------ refusals


def copy(tmp_path, which, status):
    """The checked-in protocol with another status: a registered one carries its matching
    registration record, any other none."""
    data = dict(PROTOCOLS[which])
    data.pop("registration", None)
    if status.startswith("registered"):
        data["registration"] = dict(status=status)
    path = tmp_path / f"{which}-{status.split()[0]}.json"
    path.write_text(json.dumps(dict(data, status=status)))
    return path


def clean_snapshot(root):
    root.mkdir(parents=True, exist_ok=True)
    manifest = dict(status="complete", patch_sha256=hashlib.sha256(b"").hexdigest(),
                    git_revision="1" * 40)
    (root / "SNAPSHOT.json").write_text(json.dumps(manifest))


@pytest.mark.parametrize("which", ["fr4", "fr5"])
def test_the_checked_in_protocol_is_refused_outside_a_clean_snapshot(tmp_path, which):
    data = PROTOCOLS[which]
    refusal = generator.judged_run_refusal(data, tmp_path)
    if data["status"].lower().startswith("registered"):
        assert data["registration"]["status"] == data["status"]
        assert "clean execution snapshot" in refusal
    else:
        assert "not registered" in refusal and "registration" not in data


@pytest.mark.parametrize("which", ["fr4", "fr5"])
def test_the_judged_entry_refuses_before_writing_anything(tmp_path, which):
    out = tmp_path / "out"
    proposed = copy(tmp_path, which, "PROPOSED (a test copy)")
    with pytest.raises(SystemExit, match="not registered"):
        generator.main(["judged", str(proposed), str(out), generator.PARTS[which][0]])
    registered = json.loads(copy(tmp_path, which, "registered (a test copy)").read_text())
    assert "registration record" in generator.judged_run_refusal(
        {k: v for k, v in registered.items() if k != "registration"}, tmp_path)
    assert "clean execution snapshot" in generator.judged_run_refusal(registered, tmp_path)
    clean_snapshot(tmp_path / "snap")
    refusal = generator.judged_run_refusal(registered, tmp_path / "snap")
    if generator.blocking_stand_ins(which):
        assert "stand-ins remain" in refusal
    else:
        assert refusal is None
    assert not out.exists()


PLANTED_STAND_IN = "a planted stand-in (this test's): FR-5's rungs and controls are not wired"


def plant_stand_in(monkeypatch):
    """Every part is wired, so STAND_INS is empty (the last, fr5_kinds, went with the core's
    raw-sum bound, 16 November 2026). The guard is shown with a planted stand-in that blocks what
    fr5_kinds blocked: FR-5's rungs and controls."""
    assert generator.STAND_INS == {} and generator.STAND_IN_PARTS == {}
    monkeypatch.setattr(generator, "STAND_INS", {"planted": PLANTED_STAND_IN})
    monkeypatch.setattr(generator, "STAND_IN_PARTS",
                        {"planted": {*generator.FR5_RUNGS, *generator.FR5_CONTROL_PARTS}})


def test_a_stand_in_blocks_only_the_judged_runs_of_the_protocol_whose_parts_it_blocks(
        tmp_path, monkeypatch):
    """FR-4's judged run does not wait for FR-5's stand-ins: a stand-in blocks a protocol's judged
    run only when it blocks one of that protocol's parts, and every run records the stand-ins that
    block its own protocol (the judge refuses any). Nothing blocks either protocol today; a
    planted stand-in on FR-5's rungs and controls blocks FR-5's judged run alone."""
    clean_snapshot(tmp_path / "snap")
    registered = {which: json.loads(copy(tmp_path, which, "registered (a test copy)").read_text())
                  for which in ("fr4", "fr5")}
    for which in ("fr4", "fr5"):
        assert generator.blocking_stand_ins(which) == []
        assert generator.judged_run_refusal(registered[which], tmp_path / "snap") is None
    plant_stand_in(monkeypatch)
    assert generator.blocking_stand_ins("fr5") == ["planted"]
    assert generator.blocking_stand_ins("fr4") == []
    refusal = generator.judged_run_refusal(registered["fr5"], tmp_path / "snap")
    assert "stand-ins remain" in refusal and "this protocol's parts" in refusal
    assert generator.judged_run_refusal(registered["fr4"], tmp_path / "snap") is None
    # Each run's record, without an engine or a reference run: the reference parts stubbed.
    for which in ("fr4", "fr5"):
        monkeypatch.setitem(generator.FUNCTIONS[which], "reference",
                            lambda name, context: dict(kind="reference"))
    for which, recorded in (("fr4", []), ("fr5", ["planted"])):
        out = tmp_path / f"dev-{which}"
        record = generator.run(which, ["reference"], out, status="Development run",
                               extract={"producer": "engine"})
        assert record["stand_ins"] == recorded
        assert json.loads((out / "results.json").read_text())["stand_ins"] == recorded


def test_compare_checks_records_bit_for_bit_with_run_times_apart(tmp_path):
    parts = fr4_parts()
    a = results(parts, "fr4")
    b = json.loads(json.dumps(a))
    for value in b["parts"].values():  # Every run-time leaf differs, at any depth.
        value.update(wall_s=1.5, seconds=2.5, timings=dict(compile_seconds=3.5))
        for world in value.get("worlds", {}).values():
            world["seconds"] = 4.5
    paths = [tmp_path / "a.json", tmp_path / "b.json"]
    for path, data in zip(paths, (a, b), strict=True):
        path.write_text(json.dumps(data))
    report = judge.compare(*paths, tmp_path / "same.json")
    assert all(p["identical"] for p in report["parts"].values())
    b["parts"]["rung_1ms"]["series"]["pH_L"][3] += 1e-15
    paths[1].write_text(json.dumps(b))
    report = judge.compare(*paths, tmp_path / "differ.json")
    assert not report["parts"]["rung_1ms"]["identical"]
    assert report["parts"]["rung_1ms"]["differences"] == [".series.pH_L[3]"]
    assert all(p["identical"] for n, p in report["parts"].items() if n != "rung_1ms")


def test_world_agreement_compares_two_saved_worlds_bit_for_bit(tmp_path):
    """FR-5's world agreement with one world per unit (world_agreement --world, then --compare):
    the two records files are compared leaf by leaf, run times and the world's name apart; a
    planted one-ulp difference is found at its path; files that are not one arm's two worlds of one
    definition are refused."""
    from validation.compartment_ph_engine import world_agreement as wa

    meta = dict(arm="T", path="vector", horizon_s=2.0, window_s=[0.5, 1.5], dt_s=None,
                start=dict(producer="engine", time_s=1800.0, extract_sha256="start-a"),
                definition_sha256="definition-a")
    dev = dict(admitted=True, completed=True, refusal=None, steps=4000, record_s=[0, 1, 2],
               series=dict(X_L=[1.0, 0.5, 0.25], pH_L=[5.1, 5.2, 5.3]), world="development",
               timings=dict(compile_seconds=1.0))
    dec = dict(json.loads(json.dumps(dev)), world="declared", timings=dict(compile_seconds=2.0))

    def write(name, world, records, **changes):
        path = tmp_path / name
        path.write_text(json.dumps(dict(kind=wa.RECORDS_KIND, world=world, **{**meta, **changes},
                                        records=records)))
        return path

    a, b, out = write("dev.json", "development", dev), write("dec.json", "declared", dec), \
        tmp_path / "out.json"
    assert wa.main(["--compare", str(a), str(b), str(out)]) == 0
    report = json.loads(out.read_text())
    assert report["bitwise"] and report["differences"] == []
    assert report["runs"]["declared"] == dict(admitted=True, completed=True, refusal=None,
                                              steps=4000, records=3)
    planted = json.loads(json.dumps(dec))
    planted["series"]["X_L"][2] = math.nextafter(0.25, 1.0)
    wa.main(["--compare", str(a), str(write("planted.json", "declared", planted)), str(out)])
    report = json.loads(out.read_text())
    assert not report["bitwise"] and report["differences"] == [".series.X_L[2]"]
    for name, changes in (("arm.json", dict(arm="R")),
                          ("definition.json", dict(definition_sha256="definition-b"))):
        with pytest.raises(SystemExit, match="not one arm's two worlds"):
            wa.compare_files(a, write(name, "declared", dec, **changes))
    with pytest.raises(SystemExit, match="declared records expected"):
        wa.compare_files(a, a)


def test_judged_runs_take_the_vector_path_and_development_runs_either(tmp_path):
    """The lead's ruling (15 November 2026, a dated pre-run correction in both protocols): a
    judged run takes the vector-window path, every accepted row checked on the device, and refuses
    the host path; a development run takes the host path unless --path names the vector one."""
    out = tmp_path / "out"
    assert generator.JUDGED_PATH == "vector" and set(generator.PATHS) == {"host", "vector"}
    assert generator.default_path(judged=True) == "vector"
    assert generator.default_path(judged=False) == "host"
    why = generator.refusal_before_writing("fr4", ["rung_1ms"], out, None, judged=True,
                                           quick=False, path="host", world="declared")
    assert "execution path (vector" in why
    assert generator.refusal_before_writing("fr4", ["rung_1ms"], out, None, judged=True,
                                            quick=False, path="vector", world="declared") is None
    for path in generator.PATHS:
        assert generator.refusal_before_writing("fr4", ["rung_1ms"], out, None, judged=False,
                                                quick=True, path=path) is None
    for which in ("fr4", "fr5"):
        disclosures = PROTOCOLS[which]["disclosures"]
        assert drafter.EXECUTION_PATH in disclosures
        assert any("the lead's ruling on the cost and the rehearsal" in d for d in disclosures)
    assert not out.exists()


def test_judged_runs_take_the_declared_world_and_development_runs_either(tmp_path):
    """The lead's ruling (16 November 2026, a dated pre-run correction in both protocols): a
    judged run takes the declared world, FR-1's compartment operator included (the composite,
    shown bitwise the development world's over 900 s), and refuses the development world; a
    development run takes the development world unless --world names the declared one."""
    out = tmp_path / "out"
    assert generator.JUDGED_WORLD == "declared"
    assert set(generator.WORLDS) == {"development", "declared"}
    assert generator.default_world(judged=True) == "declared"
    assert generator.default_world(judged=False) == "development"
    why = generator.refusal_before_writing("fr4", ["rung_1ms"], out, None, judged=True,
                                           quick=False, path="vector", world="development")
    assert "the protocols' world (declared" in why
    assert generator.refusal_before_writing("fr4", ["rung_1ms"], out, None, judged=True,
                                            quick=False, path="vector", world="declared") is None
    for world in generator.WORLDS:
        assert generator.refusal_before_writing("fr4", ["rung_1ms"], out, None, judged=False,
                                                quick=True, path="vector", world=world) is None
    assert drafter.DECLARED_WORLD_FR4 in PROTOCOLS["fr4"]["disclosures"]
    assert drafter.DECLARED_WORLD_FR5 in PROTOCOLS["fr5"]["disclosures"]
    assert not out.exists()


def test_the_development_entry_refuses_the_parts_a_stand_in_blocks(tmp_path, monkeypatch):
    """With nothing stood in, FR-5's rungs and controls pass the development entry's refusals; a
    planted stand-in refuses exactly its own parts, by its text, before anything is written."""
    out = tmp_path / "dev"
    engine_start = {"producer": "engine"}
    fr5_parts = sorted({*generator.FR5_RUNGS, *generator.FR5_CONTROL_PARTS})
    for part in fr5_parts:
        assert generator.refusal_before_writing("fr5", [part], out, engine_start, judged=False,
                                                quick=False) is None
    plant_stand_in(monkeypatch)
    for part in fr5_parts:
        why = generator.refusal_before_writing("fr5", [part], out, engine_start, judged=False,
                                               quick=False)
        assert "stand-in" in why and PLANTED_STAND_IN in why
    for which, part in (("fr5", "start"), ("fr5", "reference"), ("fr4", "rung_1ms")):
        assert generator.refusal_before_writing(which, [part], out, engine_start, judged=False,
                                                quick=False) is None  # Not its parts.
    with pytest.raises(SystemExit, match="stand-in"):  # Before the start is asked for.
        generator.main(["dev", "fr5", str(out), fr5_parts[0]])
    assert not out.exists()
    with pytest.raises(SystemExit, match="--start"):
        generator.main(["dev", "fr5", str(out), "reference"])
    with pytest.raises(SystemExit, match="unknown"):
        generator.main(["dev", "fr4", str(out), "rung_3ms"])
    assert not out.exists()


def results(parts, which, *, status=None, source=None, **extra):
    pid = generator.IDS[which]
    out = dict(status=status or "Judged run of " + pid, protocol_id=pid,
               source=source or dict(kind="snapshot", status="complete",
                                     patch_sha256=hashlib.sha256(b"").hexdigest(),
                                     git_revision="1" * 40),
               requested_parts=sorted(parts), complete=True, quick=False, stand_ins=[],
               parts=parts)
    out.update(extra)
    return out


def test_the_judge_refuses_runs_it_cannot_judge(tmp_path):
    which, protocol = "fr4", dict(PROTOCOLS["fr4"])
    registered = dict(protocol, status="registered (a test copy)")
    registered["registration"] = dict(status=registered["status"])
    parts = fr4_parts()
    whole = [("all", results(parts, which))]
    assert "not registered" in judge.refusal(dict(protocol, status="PROPOSED"), whole,
                                             tmp_path / "v")
    assert judge.refusal(registered, whole, tmp_path / "v") is None
    dirty = [("all", results(parts, which, source=dict(kind="checkout")))]
    assert "clean, complete execution snapshot" in judge.refusal(registered, dirty,
                                                                 tmp_path / "v")
    some = [("some", results({"reference": parts["reference"]}, which))]
    assert "judged parts" in judge.refusal(registered, some, tmp_path / "v")
    (tmp_path / "v").mkdir()
    assert "output directory exists" in judge.refusal(registered, whole, tmp_path / "v")
    with pytest.raises(SystemExit, match="quick"):
        judge.merge([("q", results(parts, which, quick=True))], protocol, judged=True)
    with pytest.raises(SystemExit, match="incomplete"):
        judge.merge([("i", dict(results(parts, which), complete=False))], protocol, judged=True)
    split = [("a", results({"rung_1ms": parts["rung_1ms"]}, which)),
             ("b", results({"rung_1ms": parts["rung_1ms"]}, which))]
    with pytest.raises(SystemExit, match="more than one run"):
        judge.merge(split, protocol, judged=True)
    other = [("o", results(parts, "fr5"))]
    with pytest.raises(SystemExit, match="not a run of"):
        judge.merge(other, protocol, judged=True)
    fr5 = fr5_parts()
    fr5["T_rung_1ms"]["start"] = dict(fr5["T_rung_1ms"]["start"], extract_sha256="b" * 64)
    with pytest.raises(SystemExit, match="extract"):
        judge.merge([("s", results(fr5, "fr5"))], PROTOCOLS["fr5"], judged=True)


def test_the_development_verdict_is_written_once_and_says_it_is_not_a_judgement(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps(results(fr4_parts(), "fr4", status="Development run")))
    out = tmp_path / "verdict"
    record = judge.main(["dev", str(generator.PROTOCOLS["fr4"]), str(out), str(path)])
    assert record["passed"] and record["kind"].startswith("Development verdict")
    assert json.loads((out / "verdict.json").read_text())["passed"]
    with pytest.raises(SystemExit, match="exists"):
        judge.main(["dev", str(generator.PROTOCOLS["fr4"]), str(out), str(path)])


def test_registration_takes_the_records_status_and_keeps_every_other_leaf(tmp_path):
    path = copy(tmp_path, "fr5", "PROPOSED (a test copy)")
    before = json.loads(path.read_text())
    record = tmp_path / "record.json"
    record.write_text(json.dumps(dict(status="PROPOSED again")))
    with pytest.raises(SystemExit, match="must begin 'registered'"):
        drafter.register(path, record)
    record.write_text(json.dumps(dict(status="registered by the lead (a test)", by="the lead")))
    after = drafter.register(path, record)
    assert after["status"] == "registered by the lead (a test)"
    assert after["registration"] == dict(status=after["status"], by="the lead")
    assert list(after)[list(after).index("status") + 1] == "registration"
    assert {k: v for k, v in after.items() if k not in ("status", "registration")} == {
        k: v for k, v in before.items() if k != "status"}
    with pytest.raises(SystemExit, match="only a PROPOSED protocol"):
        drafter.register(path, record)


def test_the_launch_template_runs_the_entries_through_the_detached_launcher():
    for which, protocol in PROTOCOLS.items():
        r = protocol["judge"]["resources"]
        assert r["unit"].startswith("scripts/run_detached.sh ") and "--oom-first" in r["unit"]
        assert "--wait-headroom" not in r["unit"] and "--runtime-max RUNTIME_MAX_S" in r["unit"]
        assert f"compartment_ph_qualification judged SNAPSHOT/validation/compartment_ph/" \
               f"protocols/{drafter.FILES[which]}" in r["unit"]
        assert set(protocol["judge"]["units"]) == set(generator.PARTS[which])


# ------------------------------------------------------------------------ the worlds


def test_every_rung_of_both_ladders_records_every_second_on_shared_times():
    for rung in dt_study.build_rungs():
        times = rung["definition"]["experiment"]["observation_times"]
        assert len(times) == 901 and [round(t) for t in times] == list(range(901))
    for arm in ("T", "R"):
        for rung in dt_study.build_fr5_rungs(arm):
            times = rung["definition"]["experiment"]["observation_times"]
            assert len(times) == 401 and [round(t) for t in times] == list(range(401))
            assert abs(times[-1] - 400.0) < 1e-9
    with pytest.raises(ValueError, match="grid"):
        defs.record_stride(400.0, 3e-4)


def synthetic_extract(producer="reference_self_check"):
    declared = defs.fr4_world()
    nodes = {n["id"]: dict(amounts_fmol=dict(n["initial_amount_fmol"]), charge_C=0.0)
             for n in declared["model"]["cells"] + declared["model"]["extracellular"]}
    nodes[defs.LUMEN]["amounts_fmol"]["H"] *= 1.5
    nodes[defs.LUMEN]["amounts_fmol"]["K"] -= 2.0
    nodes[defs.LUMEN]["charge_C"] = 5.7e-14
    nodes[defs.CELL]["charge_C"] = -4.1e-14
    return defs.start_extract(producer=producer, nodes=nodes,
                              readouts=dict(pH_c=7.21, pH_L=5.09, V_b_V=-7.3e-3), time_s=1800.0,
                              dt_s=1e-3, source=dict(kind="test"))


def test_fr5_takes_the_extracts_amounts_and_charges_and_its_controls():
    extract = synthetic_extract()
    z = dict(defs.SPECIES)
    d = defs.fr5_world(ARM_R, start=extract)
    for node in d["model"]["cells"] + d["model"]["extracellular"]:
        taken = extract["nodes"][node["id"]]
        assert all(node["initial_amount_fmol"][s] == v for s, v in taken["amounts_fmol"].items())
        assert node["initial_charge_C"] == taken["charge_C"]
        net = node["fixed_charge_equivalent_fmol"] + math.fsum(
            z.get(s, 0) * n for s, n in node["initial_amount_fmol"].items())
        assert net * CHARGE_PER_FMOL == pytest.approx(taken["charge_C"], rel=1e-9, abs=1e-24)
    assert "start" not in d  # The part's record carries the extract's identity instead.
    recorded = generator._with_start({}, dict(start=extract))["start"]
    assert recorded == dict(extract_sha256=defs.start_sha256(extract),
                            producer="reference_self_check", time_s=1800.0)
    routes = {r["id"]: r for r in defs.fr5_world(ARM_T, start=extract,
                                                 control="f_equals_1")["model"]["passive_routes"]}
    assert routes["cargo_transfer_0"]["factors"] == [] and "cargo_pore_0" not in routes
    injury = defs.fr5_world(ARM_R, start=extract, control="d_equals_0")["experiment"][
        "damage_controls"][0]["injury"]
    assert all(step["value"] == 0.0 for step in injury)
    with pytest.raises(ValueError, match="checkpoint time"):
        defs.fr5_world(ARM_R, start=dict(extract, time_s=900.0))
    with pytest.raises(ValueError, match="nine rows"):
        defs.check_start(dict(extract, nodes={defs.CELL: extract["nodes"][defs.CELL]}))


def test_a_judged_fr5_part_takes_only_the_engines_extract_from_its_own_snapshot(tmp_path):
    clean_snapshot(tmp_path)
    engine = dict(synthetic_extract("engine"), source=generator.snapshot_identity(tmp_path))
    assert generator.start_refusal(engine, judged=True, root=tmp_path) is None
    assert "engine's extract" in generator.start_refusal(synthetic_extract(), judged=True,
                                                         root=tmp_path)
    assert generator.start_refusal(synthetic_extract(), judged=False, root=tmp_path) is None
    assert "--start" in generator.start_refusal(None, judged=False, root=tmp_path)


@pytest.mark.parametrize("which", ["fr4", "fr5"])
def test_the_judged_path_registers_guards_merges_and_passes(tmp_path, which):
    """register on a PROPOSED copy, then the judge's judged entry on judged-form unit results from
    a clean snapshot: the guard, the merge (one part per unit) and the verdict, in sequence."""
    path = copy(tmp_path, which, "PROPOSED (a test copy)")
    record = tmp_path / "record.json"
    record.write_text(json.dumps(dict(status="registered by the lead (a test copy)")))
    drafter.register(path, record)
    parts = fr4_parts() if which == "fr4" else fr5_parts()
    files = []
    for name, value in parts.items():  # one results file per unit, as the launch template runs
        files.append(tmp_path / f"{name}.json")
        files[-1].write_text(json.dumps(results({name: value}, which)))
    out = tmp_path / "verdict"
    record = judge.main(["judged", str(path), str(out), *map(str, files)])
    assert record["kind"] == "Judged verdict" and record["passed"]
    assert set(record["part_sources"]) == set(generator.PARTS[which])
    with pytest.raises(SystemExit, match="exists"):
        judge.main(["judged", str(path), str(out), *map(str, files)])


def test_k3_is_caught_by_its_envelope_refusal_and_leaves_j1():
    """The lead's rulings (15 November 2026): K3's catch is the engine's refusal through the
    envelope at the definition; a refusal for another reason, or a K3 that runs, is not; J1's
    admission leaves K3 out, and J5 reads zero envelope refusals and the reported maximum."""
    protocol = json.loads(generator.PROTOCOLS["fr4"].read_text())
    derivation = protocol["judge"]["derivation"]
    parts = fr4_parts()
    derived = judge.derive_fr4(parts, derivation)
    assert derived["admission"]["all_admitted"] == 1 and "control_k3" not in derived[
        "admission"]["parts"]
    assert derived["controls"]["k3"]["engine_stages_beyond"] == 1
    assert derived["envelope"] == dict(max_lag_ph=1e-5, stages_beyond=0)
    ran = dict(k3_refused(None), admitted=True, completed=True, refusal=None)
    for k3, expected in ((k3_refused("other"), None), (ran, 0)):
        derived = judge.derive_fr4(dict(parts, control_k3=k3), derivation)
        assert derived["controls"]["k3"]["engine_stages_beyond"] == expected
