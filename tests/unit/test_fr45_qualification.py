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

from validation.compartment_ph import definitions as defs
from validation.compartment_ph import dt_study
from validation.compartment_ph.parameters import ARM_R, ARM_T, CHARGE_PER_FMOL
from validation.tissue import compartment_ph_judge as judge
from validation.tissue import compartment_ph_protocol as drafter
from validation.tissue import compartment_ph_qualification as generator

PROTOCOLS = {k: json.loads(p.read_text()) for k, p in generator.PROTOCOLS.items()}


# ------------------------------------------------------------------------ synthetic records


def part(dt, end, series, *, stage=None, ledgers=None, start=None):
    out = dict(kind="engine", dt_s=dt, end_s=end, steps=round(end / dt), admitted=True,
               completed=True, refusal=None, record_s=[float(t) for t in range(round(end) + 1)],
               series=series, stage=stage or {}, ledgers=ledgers or {})
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
        cycles=[2e-3 * s + 1e-6 * e * grow(s, 50) for s in t],
        energy_residual_pJ=[1e-4 * e * f for f in flows], energy_flows_pJ=flows)


def fr4_parts(order=2):
    """A complete FR-4 run that passes every criterion at order 2 (its ladder's errors at
    `order`)."""
    stage = dict(envelope_max_lag_ph=1e-5, envelope_stages_beyond=0, cytosol_pH_min=7.2,
                 cytosol_pH_max=7.218)
    ledgers = dict(material_residual_fmol={"H": 1e-15, "K": 1e-12},
                   material_tolerance_fmol={"H": 1e-14, "K": 1e-10},
                   charge_residual_C=1e-21, charge_tolerance_C=1e-18)
    t = [float(s) for s in range(901)]
    parts = {}
    for name, dt in generator.FR4_RUNGS.items():
        parts[name] = part(dt, 900.0, fr4_series(t, dt, order), stage=stage, ledgers=ledgers)
    parts["control_k1"] = part(1e-3, 900.0, fr4_series(t, 1e-3, k1=True), stage=stage,
                               ledgers=ledgers)
    parts["control_k2"] = part(1e-3, 900.0, fr4_series(t, 1e-3, k2=True), stage=stage,
                               ledgers=ledgers)
    parts["control_k3"] = part(1e-3, 900.0, fr4_series(t, 1e-3), ledgers=ledgers,
                               stage=dict(stage, envelope_max_lag_ph=2.0,
                                          envelope_stages_beyond=1200))
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
        energy_residual_pJ=[1e-5 * s for s in t], energy_flows_pJ=[0.5 * s for s in t],
        **{f"heat_{r}_pJ": [0.01 * s for s in t] for r in (
            "proton_leak_0", "proton_pore_0", "bounding_0_K", "cargo_transfer_0",
            "cargo_pore_0")})
    if arm == "R":
        out["moved_X_pore"] = m_pore
        out["X_L"] = x_l
    return out


def fr5_parts(*, exact_d=False, extract_sha="a" * 64):
    t = [float(s) for s in range(401)]
    stage = dict(envelope_max_lag_ph=1e-4, envelope_stages_beyond=0, cytosol_pH_min=7.21,
                 cytosol_pH_max=7.22)
    ledgers = dict(material_residual_fmol={"H": 1e-15, "X": 1e-16},
                   material_tolerance_fmol={"H": 1e-12, "X": 1e-12},
                   charge_residual_C=1e-21, charge_tolerance_C=1e-18)
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


def test_a_second_order_ladder_has_order_two_and_a_first_order_rung_leaves_the_band():
    parts = fr4_parts()
    rungs = list(generator.FR4_RUNGS)
    good = judge.ladder(parts, rungs, "pH_L")
    assert good["resolved"] == [True, True, True]
    assert good["orders"] == pytest.approx([2.0, 2.0], abs=1e-6)  # rounding of the sums
    bad = judge.ladder(fr4_parts(order=1), rungs, "pH_L")
    assert bad["order_finest"] == pytest.approx(1.0, abs=1e-6)


def test_a_difference_under_accumulated_rounding_is_unresolved_and_gives_no_order():
    parts = fr4_parts()
    for name in generator.FR4_RUNGS:  # errors of 1e-13 pH: under N eps max|pH| at every rung
        dt = generator.FR4_RUNGS[name]
        parts[name]["series"]["pH_L"] = [7.2 + 1e-13 * (dt / 1e-3) ** 2 * grow(s, 50)
                                         for s in range(901)]
    got = judge.ladder(parts, list(generator.FR4_RUNGS), "pH_L")
    assert got["resolved"] == [False, False, False] and got["order_finest"] is None


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
    assert {"J4_reference_pH_L", "J4_start"} <= set(failed(parts, protocol))
    parts = fr4_parts()
    parts["control_k2"]["series"] = fr4_series([float(s) for s in range(901)], 1e-3)
    assert failed(parts, protocol) == ["J7_K2_planted_sign"]  # a control that is not caught
    parts = fr4_parts()
    parts["rung_0p5ms"]["stage"]["envelope_stages_beyond"] = 3
    assert failed(parts, protocol) == ["J5_envelope_count"]


def test_a_missing_or_refused_part_fails_its_criteria_through_none():
    protocol = PROTOCOLS["fr4"]
    parts = fr4_parts()
    del parts["rung_0p25ms"]
    got = failed(parts, protocol)
    assert "J1_admission" in got and "J2_order_pH_L" in got
    parts = fr4_parts()
    parts["rung_1ms"].update(completed=False, refusal="refused at run time")
    assert {"J1_admission", "J3_state_error_pH_L", "J4_reference_pH_L"} <= set(
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


def test_an_exact_damage_state_gives_no_order_so_j2_fails_on_d():
    """Question 3 to the lead: d's step is exact, so its rung differences are rounding."""
    assert failed(fr5_parts(exact_d=True), PROTOCOLS["fr5"]) == ["J2_R_order_d", "J2_T_order_d"]


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
        assert protocol["questions_for_the_lead"] == drafter.QUESTIONS[which]


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
    if generator.STAND_INS:
        assert "stand-ins remain" in refusal
    else:
        assert refusal is None
    assert not out.exists()


def test_the_development_entry_refuses_engine_parts_while_the_engine_is_a_stand_in(tmp_path):
    out = tmp_path / "dev"
    if generator.STAND_INS:
        with pytest.raises(SystemExit, match="stand-in"):
            generator.main(["dev", "fr4", str(out), "rung_1ms"])
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
    assert d["start"]["extract_sha256"] == defs.start_sha256(extract)
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
