"""fr10-dose-schedule-v1's tools on the host: the judge, the drafter and the guards (tier 1).

No engine run: synthetic records with known orders, budgets and comparisons exercise the judge's
derivation and every machine criterion, each with a planted error that must fail its own
criterion; records on the 10 ms grid are compared record by record, not second by second; the
generator's judged entry refuses before writing anything; the drafter's section is the checked-in
one, and it refuses a registered protocol; registration takes the record's status and changes
nothing else. The tests are status-agnostic: registration changes the status and adds the record
alone.
"""

import copy
import hashlib
import json
import math

import pytest

from validation.tissue import bath_schedule_judge as judge
from validation.tissue import bath_schedule_protocol as drafter
from validation.tissue import bath_schedule_qualification as generator

PROTOCOL = json.loads(generator.PROTOCOL.read_text())
D = drafter.derivation()
B1, B2 = D["W1"]["budget_fmol"], D["W2"]["budget_V"]


def times(end, every=0.01):
    return [round(k * every, 10) for k in range(int(round(end / every)) + 1)]


def w1_exact(t):
    """S at ecs_0 and ecs_1 (fmol): a smooth step response, the same shape as W1's."""
    def node(s, tau):
        up = 9e-3 * (1 - math.exp(-(s - 1.0) / tau)) if s >= 1.0 else 0.0
        down = 9e-3 * (1 - math.exp(-(s - 2.0) / tau)) if s >= 2.0 else 0.0
        return 1e-3 + up - down
    return dict(amount_S_ecs_0=[node(s, 0.1) for s in t], amount_S_ecs_1=[node(s, 0.3) for s in t])


def w2_exact(t):
    def v(s):
        return -0.089 + (0.0615 * (1 - math.exp(-(s - 0.5) / 0.1)) if s >= 0.5 else 0.0)
    def k(s):
        return 140.0 + (0.4 * (1 - math.exp(-(s - 0.5) / 0.1)) if s >= 0.5 else 0.0)
    return dict(V_wall_cell_0=[v(s) for s in t], amount_K_cell_0=[k(s) for s in t])


def ledgers(t, *, energy=0.01):
    return {f"ratio_{name}": [energy if name == "energy" else 0.0] * len(t)
            for name in drafter.LEDGERS}


VALENCES = {"Na": 1, "K": 1, "Cl": -1, "S": 0}


def engine(dt, end, series, *, steps=None, extra=None):
    t = times(end)
    quiet = {f"bath_dose_{sp}_fmol": [0.0] * len(t) for sp in VALENCES}
    quiet["bath_compensation_charge_C"] = [0.0] * len(t)
    return dict(kind="engine", admitted=True, completed=True, refusal=None, dt_s=dt, end_s=end,
                steps=steps or round(end / dt), record_s=t, valences=dict(VALENCES),
                series={**quiet, **series, **ledgers(t), **(extra or {})})


def after(s, te, *, right=False):
    """Past the event: the engine's record at t_e shows the bath before it (right=False)."""
    return s >= te - 1e-12 if right else s > te + 1e-12


def rung(world, dt, *, order=2, control=False, right=False, late=0.0, k_scale=1e-8):
    t = times(3.0 if world == "W1" else 2.0)
    exact = (w1_exact if world == "W1" else w2_exact)(t)
    e = (dt / 1e-3) ** order
    scale = dict(amount_S_ecs_0=1e-7, amount_S_ecs_1=1e-7, V_wall_cell_0=1e-6,
                 amount_K_cell_0=k_scale)  # Each about 1e-2 of its budget at 1 ms.
    if control:  # No step: the start held.
        series = {k: [v[0]] * len(v) for k, v in exact.items()}
    else:
        series = {k: [x + scale[k] * e * (1 - math.exp(-s)) for x, s in zip(v, t, strict=True)]
                  for k, v in exact.items()}
    flows = [0.1 * s for s in t]
    energy = dict(energy_residual_pJ=[1e-5 * e * f for f in flows], energy_flows_pJ=flows)
    records = {}
    if control:
        records = {}
    elif world == "W1":
        dose = [9e-3 if after(s, 1.0 + late, right=right) and not after(s, 2.0 + late, right=right)
                else 0.0 for s in t]
        records = dict(bath_dose_S_fmol=dose, bath_dose_free_energy_pJ=[d * 2.0 for d in dose])
    else:
        dose = {"Na": -45.0, "K": 45.0, "Cl": 0.0}
        records = {f"bath_dose_{sp}_fmol": [v if after(s, 0.5 + late, right=right) else 0.0
                                            for s in t] for sp, v in dose.items()}
        records["bath_dose_free_energy_pJ"] = [-5.0 if after(s, 0.5 + late, right=right) else 0.0
                                               for s in t]
    return engine(dt, t[-1], {**series, **energy, **records})


def w3_times():
    return [round(k * 1e-4, 10) for k in range(61)]


def w3_k():
    return [0.0 if s <= 0.002 + 1e-12 else 2e4 for s in w3_times()]


def w3_supply():
    return [1e-7 * s for s in w3_times()]


def w3_part():
    t = w3_times()
    own = [1e-3 if s <= 0.002 + 1e-12 else 2e4 for s in t]
    part = engine(1e-4, 0.006, {}, steps=60)
    part["record_s"] = t
    part["series"] = {k: [v[0]] * len(t) for k, v in part["series"].items()}
    part["series"].update(
        reservoir_work_own_pJ=own, reservoir_work_bound_pJ=[1.0] * len(t),
        bath_reconciliation_pJ=w3_k(), supplied_S_fmol=w3_supply(),
        bath_dose_S_fmol=[5e-4 if after(s, 0.002) else 0.0 for s in t],
        bath_dose_free_energy_pJ=[1e-3 if after(s, 0.002) else 0.0 for s in t])
    return part


def references():
    t1, t2 = times(3.0), times(2.0)
    return dict(kind="reference", admitted=True, completed=True, worlds=dict(
        W1=dict(record_s=t1, series=w1_exact(t1)), W1_floor=dict(record_s=t1, series=w1_exact(t1)),
        W2=dict(record_s=t2, series=w2_exact(t2)), W2_floor=dict(record_s=t2, series=w2_exact(t2))),
        records=dict(
            W1=[dict(time_s=1.0, dose_fmol={"S": 9e-3}, free_energy_pJ=1.8e-2),
                dict(time_s=2.0, dose_fmol={"S": -9e-3}, free_energy_pJ=-1.8e-2)],
            W2=[dict(time_s=0.5, dose_fmol={"Na": -45.0, "K": 45.0, "Cl": 0.0},
                     free_energy_pJ=-5.0)],
            W3=[dict(time_s=0.002, dose_fmol={"S": 5e-4}, free_energy_pJ=1e-3)]),
        K_W3=dict(record_s=w3_times(), series=dict(K_pJ=w3_k()),
                  supply_fmol=dict(S=w3_supply())))


def comparison(**fields):
    return dict(kind="comparison", admitted=True, completed=True, **fields)


def refusals():
    classes = {}
    for cls, check in drafter.REFUSAL_CHECKS.items():
        classes[cls] = dict(refused=[dict(refused=True, message="m", check=check)],
                            admitted=[dict(admitted=True, ran=True, message=None)])
    classes["R12_beyond_the_explicit_bound"]["declared_alone_at_1ms"] = dict(admitted=True)
    return dict(kind="refusals", admitted=True, completed=True, classes=classes)


def parts():
    out = {name: rung("W1", dt) for name, dt in generator.W1_RUNGS.items()}
    out |= {name: rung("W2", dt) for name, dt in generator.W2_RUNGS.items()}
    out["W1_control"] = rung("W1", 1e-3, control=True)
    out["W2_control"] = rung("W2", 1e-3, control=True)
    out["W3_rk4"] = w3_part()
    out["W4_idle"] = comparison(idle=dict(equal=True), planted=dict(equal=False))
    out["W5_restart"] = comparison(restarts={f"{t:g}": dict(equal=True)
                                             for t in generator.RESTART_TIMES_S},
                                   planted=dict(equal=False))
    out["W5_batch"] = comparison(worlds={f"world_{i}": dict(equal=True) for i in (1, 2, 3)})
    for name in ("W6_water", "W7_staircase_ars", "W7_staircase_rk4"):
        out[name] = engine(1e-3, 0.1, {})
    out["refusals"] = refusals()
    out["references"] = references()
    return out


def failed(p):
    _, evaluated = judge.verdict(p, PROTOCOL)
    return sorted(c["id"] for c in evaluated["criteria"] if c["judged"] and not c["passed"])


# ------------------------------------------------------------------ the judge


def test_a_complete_run_passes_every_criterion():
    assert failed(parts()) == []


@pytest.mark.parametrize("plant, expected", [
    ("first_order", {"J2_order_W1_amount_S_ecs_0", "J2_order_W1_amount_S_ecs_1",
                     "J5_energy_falls"}),
    ("off_reference", {"J4_reference", "J3_state_error"}),
    ("energy", {"J5_energy"}),
    ("w3_energy", {"J5_W3_energy"}),
    ("k3_weak", {"J12_K3_after"}),
    ("records", {"J6_records"}),
    ("free_energy", {"J6_free_energy_reference"}),
    ("idle", {"J7_idle"}),
    ("k4", {"J12_K4"}),
    ("restart", {"J8_restart"}),
    ("refusal_check", {"J9_refusals"}),
    ("neighbour", {"J9_refusals"}),
    # An incomplete run part has no records: its own criteria and the ledger maxima fail too.
    ("not_admitted", {"J1_admission", "J10_staircase", "J6_records", "J6_charge",
                      "J6_compensation"}),
    ("compensation", {"J6_compensation"}),
    ("charge_from_nothing", {"J6_compensation"}),
    ("k_reference", {"J5_K_reference"}),
    ("k_supply", {"J5_K_reference"}),  # K computed from a supply that is not W3's.
    ("late_dose", {"J6_records_reference", "J6_free_energy_reference"}),
    # The cytosol K 1.4 x its budget C B2 / F at 1 ms (and off R-ion by as much).
    ("k_budget", {"J3_state_error", "J4_reference"}),
])
def test_each_planted_error_fails_its_own_criterion(plant, expected):
    p = parts()
    if plant == "first_order":
        for name, dt in generator.W1_RUNGS.items():
            p[name] = rung("W1", dt, order=1)
    elif plant == "off_reference":
        s = p["W1_rung_1ms"]["series"]["amount_S_ecs_0"]
        s[150] += 2 * B1
    elif plant == "energy":
        s = p["W2_rung_1ms"]["series"]
        s["energy_residual_pJ"] = [3e-3 * f for f in s["energy_flows_pJ"]]
    elif plant == "w3_energy":
        p["W3_rk4"]["series"]["ratio_energy"][40] = 1.5
    elif plant == "k3_weak":
        p["W3_rk4"]["series"]["reservoir_work_own_pJ"][-1] = 5.0
    elif plant == "records":
        p["W1_rung_0p5ms"]["series"]["ratio_bath_dose"][7] = 2.0
    elif plant == "free_energy":
        p["references"]["records"]["W2"][0]["free_energy_pJ"] = -5.0 * (1 + 1e-9)
    elif plant == "idle":
        p["W4_idle"]["idle"] = dict(equal=False)
    elif plant == "k4":
        p["W4_idle"]["planted"] = dict(equal=True)
    elif plant == "restart":
        p["W5_restart"]["restarts"]["1"] = dict(equal=False)
    elif plant == "refusal_check":
        p["refusals"]["classes"]["R7_a_faster_face"]["refused"][0]["check"] = "the species cap"
    elif plant == "neighbour":
        p["refusals"]["classes"]["R8_outside_the_measured_steps"]["admitted"][0]["ran"] = False
    elif plant == "not_admitted":
        p["W7_staircase_rk4"].update(completed=False, refusal="refused at run time")
    elif plant == "compensation":  # 870 x the rounding of W2's 90 fmol of charged dose.
        p["W2_rung_0p5ms"]["series"]["bath_compensation_charge_C"][100] = 1e-20
    elif plant == "charge_from_nothing":
        p["W1_control"]["series"]["bath_compensation_charge_C"][5] = 1e-30
    elif plant == "k_reference":
        p["references"]["K_W3"]["series"]["K_pJ"][40] += 2.0
    elif plant == "k_supply":
        p["references"]["K_W3"]["supply_fmol"]["S"][30] *= 1 + 1e-12
    elif plant == "k_budget":
        for name, dt in generator.W2_RUNGS.items():
            p[name] = rung("W2", dt, k_scale=1e-6)
    elif plant == "late_dose":  # The dose one record late: the bracket sees nothing move.
        p["W1_rung_1ms"] = rung("W1", 1e-3, late=0.01)
    found = set(failed(p))
    assert expected <= found and found <= expected | {"J1_admission"}, found


def test_the_controls_fail_when_they_do_not_differ_from_the_arm():
    p = parts()
    p["W1_control"] = rung("W1", 1e-3)  # A control that is its arm.
    p["W2_control"] = rung("W2", 1e-3)
    assert {"J12_K1", "J12_K2"} <= set(failed(p))


def test_records_on_the_10_ms_grid_are_compared_record_by_record():
    """FR-4's and FR-5's arithmetic keys records by round(t); FR-10's parts reach it on a 10 ms
    grid (on_record_grid), so a difference at 0.37 s alone is seen, where integer seconds would
    have kept only one record per second."""
    p = parts()
    t = p["W1_rung_1ms"]["record_s"]
    p["W1_rung_1ms"]["series"]["amount_S_ecs_1"][t.index(0.37)] += 5 * B1
    assert "J4_reference" in failed(p)
    derived = judge.derive(p, PROTOCOL)
    assert derived["reference"]["W1_amount_S_ecs_1"] == pytest.approx(5.0, abs=0.01)


def test_the_records_are_read_across_the_event_whichever_side_a_record_at_it_shows():
    p = parts()
    p["W1_rung_1ms"] = rung("W1", 1e-3, right=True)
    p["W2_rung_1ms"] = rung("W2", 1e-3, right=True)
    assert failed(p) == []
    p["W3_rk4"]["record_s"] = p["W3_rk4"]["record_s"][:-1] + [0.0061]
    assert failed(p) == ["J5_K_reference"]  # K's record times must be W3's own.


def test_undefined_values_fail_through_none():
    p = parts()
    del p["references"]
    assert {"J4_reference", "J4_row0", "J6_records_reference", "J12_K1"} <= set(failed(p))


# ------------------------------------------------------------------ the drafter and registration


def test_the_checked_in_judge_section_is_the_drafters():
    assert PROTOCOL["judge"] == json.loads(json.dumps(drafter.judge_section()))
    assert PROTOCOL["judged_parts"] == list(generator.PARTS)
    assert set(drafter.REFUSAL_CHECKS) == {k for k in PROTOCOL["refusal_classes"]
                                           if k.startswith("R")}


def proposed():
    data = {k: v for k, v in PROTOCOL.items() if k != "registration"}
    if not data["status"].startswith("PROPOSED"):
        data["status"] = "PROPOSED (a test copy)"
    return data


def test_registration_takes_the_records_status_and_keeps_every_other_leaf(tmp_path):
    path, record = tmp_path / "p.json", tmp_path / "r.json"
    path.write_text(json.dumps(proposed()))
    before = json.loads(path.read_text())
    record.write_text(json.dumps(dict(status="PROPOSED again")))
    with pytest.raises(SystemExit, match="must begin 'registered'"):
        drafter.register(path, record)
    record.write_text(json.dumps(dict(status="registered by the lead (a test)", by="the lead")))
    after = drafter.register(path, record)
    assert after["registration"] == dict(status=after["status"], by="the lead")
    assert list(after)[list(after).index("status") + 1] == "registration"
    assert {k: v for k, v in after.items() if k not in ("status", "registration")} == {
        k: v for k, v in before.items() if k != "status"}


def test_draft_refuses_a_registered_protocol_and_changes_no_byte(tmp_path):
    path, record = tmp_path / "p.json", tmp_path / "r.json"
    path.write_text(json.dumps(proposed()))
    record.write_text(json.dumps(dict(status="registered by the lead (a test)")))
    drafter.register(path, record)
    before = path.read_bytes()
    with pytest.raises(SystemExit, match="only a PROPOSED protocol"):
        drafter.draft(path)
    assert path.read_bytes() == before


def test_draft_changes_only_the_judge_section_and_the_judged_parts(tmp_path):
    path = tmp_path / "p.json"
    data = proposed()
    data["judge"] = {"stale": True}
    data["judged_parts"] = []
    path.write_text(json.dumps(data))
    after = drafter.draft(path)
    assert {k: v for k, v in after.items() if k not in ("judge", "judged_parts")} == {
        k: v for k, v in data.items() if k not in ("judge", "judged_parts")}
    assert after["judge"] == json.loads(json.dumps(drafter.judge_section()))


# ------------------------------------------------------------------ the generator's guards


def registered_copy(tmp_path):
    data = proposed()
    data["status"] = "registered (a test)"
    data["registration"] = dict(status=data["status"])
    path = tmp_path / "registered.json"
    path.write_text(json.dumps(data))
    return path


def test_the_judged_entry_refuses_before_writing_anything(tmp_path, monkeypatch):
    out = tmp_path / "out"
    unregistered = tmp_path / "proposed.json"
    unregistered.write_text(json.dumps(proposed()))
    with pytest.raises(SystemExit, match="not registered"):
        generator.main(["judged", str(unregistered), str(out), "W6_water"])
    # A source tree without SNAPSHOT.json (the test may itself run from a snapshot, as a gate's).
    monkeypatch.setattr(generator, "ROOT", tmp_path / "checkout")
    with pytest.raises(SystemExit, match="clean execution snapshot"):
        generator.main(["judged", str(registered_copy(tmp_path)), str(out), "W6_water"])
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "SNAPSHOT.json").write_text(json.dumps(dict(
        status="complete", patch_sha256=hashlib.sha256(b"").hexdigest())))
    monkeypatch.setattr(generator, "ROOT", snapshot)
    monkeypatch.setattr(generator, "judged_run_refusal",
                        lambda protocol, root=snapshot: None)
    with pytest.raises(SystemExit, match="pass --w3"):
        generator.main(["judged", str(registered_copy(tmp_path)), str(out), "references"])
    with pytest.raises(SystemExit, match="no quick horizon"):
        generator.main(["judged", str(registered_copy(tmp_path)), str(out), "W6_water",
                        "--quick"])
    out.mkdir()
    with pytest.raises(SystemExit, match="exists"):
        generator.main(["judged", str(registered_copy(tmp_path)), str(out), "W6_water"])
    assert not any(out.iterdir())


def test_the_refusal_classifier_names_every_check_once():
    labels = [check for check, _ in generator.CHECKS]
    assert len(labels) == len(set(labels))
    assert set(drafter.REFUSAL_CHECKS.values()) <= set(labels)
    assert generator.classify("an unrelated message") is None
    for check, phrase in generator.CHECKS:
        assert generator.classify(f"... {phrase} ...") == check


def test_a_quick_horizon_keeps_only_the_events_inside_it():
    from validation.tissue import bath_schedule_fixtures as bfx

    raw = generator.quick(bfx.chain_world())
    end = raw["experiment"]["end_time"]
    assert end == pytest.approx(generator.QUICK_FRACTION * bfx.CHAIN_END_S)
    assert all(e["time"] < end for e in raw["experiment"]["bath_composition_events"])
    assert raw["experiment"]["observation_times"][-1] == end
    assert copy.deepcopy(raw) == raw
