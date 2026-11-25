"""fr6-a5pp-v1's tools on the host: the judge, the drafter and the guards (tier 1, no run).

Synthetic records laid out as the references' world (two cells a and b; V, the amounts, s and
a_eff on the 50 ms records) exercise the judge's derivation and every machine criterion: rungs at
second order above 100 floors, controls departing by known multiples of the honest error, and the
basal rule's plateau that must put a resolved pair out of the band. Each planted error fails its
own criterion; the generator's judged entry refuses before writing anything (an unregistered
protocol, a protocol without its delta, a checkout, an existing directory); the drafter's section
is the checked-in one; registration takes the record's status and changes nothing else.
"""

import hashlib
import json
import math

import pytest

from validation import id_table
from validation.tissue import a5pp_acceptance_judge as judge
from validation.tissue import a5pp_acceptance_protocol as drafter
from validation.tissue import a5pp_acceptance_qualification as generator

PROTOCOL = id_table.load(generator.PROTOCOL)
D = drafter.derivation()
RECORD_MS = list(range(0, 2001, 50))
CELLS = ("a", "b")
SPECIES = ("Na", "K", "Cl")
FLOOR = dict(V=3.3e-14, amounts=1.4e-12, s=2.1e-14, a_eff=1.9e-14)
H1 = dict(V=3e-8, amounts=1e-8, s=1e-7, a_eff=1e-7)  # The honest error at 1 ms, second order.
DTS = (1e-3, 5e-4, 2.5e-4, 1.25e-4)


def names(x):
    return judge.names(x, CELLS)


def reference():
    series = {}
    for c in CELLS:
        series[f"V_{c}"] = [-0.06 + 0.005 * math.sin(t * 1e-3) for t in RECORD_MS]
        for k, s in enumerate(SPECIES):
            series[f"amount_{c}_{s}"] = [(24.0, 280.0, 60.0)[k] - 1e-3 * t * 1e-3
                                         for t in RECORD_MS]
        series[f"s_{c}"] = [0.1 + 0.3 * (1 - math.exp(-t * 1e-3)) for t in RECORD_MS]
        series[f"a_eff_{c}"] = [0.1 + 0.9 * v for v in series[f"s_{c}"]]
    return dict(kind="reference", admitted=True, completed=True, cells=list(CELLS),
                record_ms=list(RECORD_MS), series=series, floor=dict(FLOOR))


def engine(dt, *, order=2, offset=None, scale=1.0, ids=None):
    ref = reference()
    series = {}
    for x in ("V", "amounts", "s", "a_eff"):
        for n in names(x):
            error = scale * H1[x] * (dt / 1e-3) ** order
            plateau = (offset or {}).get(x, 0.0)
            series[n] = [v if t == 0 else v + error + plateau
                         for v, t in zip(ref["series"][n], RECORD_MS, strict=True)]
    for c in CELLS:
        series[f"U_{c}"] = [0.0] * len(RECORD_MS)
        series[f"F_{c}"] = [0.1] * len(RECORD_MS)
    return dict(kind="engine", admitted=True, completed=True, refusal=None, dt_s=dt,
                steps=round(2.0 / dt), record_ms=list(RECORD_MS), series=series,
                cells=list(CELLS), ids=ids or list(drafter.ENGINE_IDS[:6]))


def control(**kwargs):
    runs = {generator.dt_key(dt): engine(dt, **kwargs) for dt in DTS}
    return dict(kind="engine_set", admitted=True, completed=True, runs=runs)


def parts():
    out = {name: engine(dt) for name, dt in generator.RUNGS.items()}
    far = {x: 1e3 * H1[x] for x in ("V", "amounts")}
    for name in ("K_prior_swapped", "K_prior_shared_a", "K_prior_shared_b",
                 "K_prior_shared_mean", "K_prior_ignored", "K_state_bypassed", "K_k_on",
                 "K_k_off"):
        out[name] = control(offset=far)
    # The references' basal: the amounts 30 x the 1 ms honest error, V where it has power.
    out["K_basal_reference"] = control(offset=dict(V=30 * H1["V"] * (DTS[2] / 1e-3) ** 2,
                                                   amounts=30 * H1["amounts"]))
    # The rule's basal: a plateau at 12 x the finest honest V error and 160 x in the amounts.
    finest = (DTS[-1] / 1e-3) ** 2
    rule = control(offset=dict(V=12 * H1["V"] * finest, amounts=160 * H1["amounts"] * finest))
    rule["delta"] = 1e-4
    out["K_basal_rule"] = rule
    out["references"] = reference()
    return out


def failed(p):
    _, evaluated = judge.verdict(p, PROTOCOL)
    return sorted(c["id"] for c in evaluated["criteria"] if c["judged"] and not c["passed"])


def test_a_complete_run_passes_every_criterion():
    assert failed(parts()) == []


def test_the_orders_and_the_delta_rule():
    derived, _ = judge.verdict(parts(), PROTOCOL)
    for x in ("V", "amounts"):
        pairs = derived["orders"][x]["pairs"]
        assert [p["resolved"] for p in pairs] == [True, True, True]
        assert all(p["order"] == pytest.approx(2.0, abs=1e-3) for p in pairs)  # Rounding.
    assert derived["basal_rule_detection"]["caught"] == 1
    rule = derived["delta_rule"]
    assert rule["rule_delta"] == pytest.approx(10 * 1e-4 / 13, rel=1e-6)
    assert rule["registered_value"] == 1e-4  # 7.7e-5 rounded up on the 1-2-5 grid.


@pytest.mark.parametrize("plant, expected", [
    # First order also raises the honest error at the fine rungs, which the basal controls
    # are judged against.
    ("first_order", {"A5pp_V_order", "A5pp_amounts_order", "K_basal_reference",
                     "K_basal_rule"}),
    ("start", {"A5pp_start"}),
    ("ids", {"C0_ids"}),
    ("prior_close", {"K_prior_swapped"}),
    ("bypass_close", {"K_state_bypassed"}),
    ("rate_close", {"K_k_on"}),
    ("basal_reference_coarse", {"K_basal_reference"}),
    ("basal_rule_no_plateau", {"K_basal_rule_detected", "K_basal_rule"}),
    ("unresolved", {"A5pp_amounts_resolved"}),
])
def test_each_planted_error_fails_its_own_criterion(plant, expected):
    p = parts()
    if plant == "first_order":
        for name, dt in generator.RUNGS.items():
            p[name] = engine(dt, order=1)
    elif plant == "start":
        p["a5pp_rung_0p5ms"]["series"]["V_a"][0] *= 1 + 1e-12
    elif plant == "ids":
        p["a5pp_rung_1ms"]["ids"] = [*p["a5pp_rung_1ms"]["ids"], "rk4"]
    elif plant == "prior_close":
        p["K_prior_swapped"] = control(offset=dict(V=2 * H1["V"], amounts=2 * H1["amounts"]))
    elif plant == "bypass_close":
        p["K_state_bypassed"] = control()
    elif plant == "rate_close":
        p["K_k_on"]["runs"]["1ms"] = engine(1e-3, offset=dict(V=0.0, amounts=1e3 * H1["amounts"]))
    elif plant == "basal_reference_coarse":
        p["K_basal_reference"]["runs"]["1ms"] = engine(1e-3, offset=dict(amounts=2 * H1["amounts"]))
    elif plant == "basal_rule_no_plateau":
        p["K_basal_rule"] = dict(control(), delta=1e-4)
    elif plant == "unresolved":  # Every amounts error under 100 floors: no resolved pair.
        for name, dt in generator.RUNGS.items():
            p[name] = engine(dt, scale=1e-6)
        p["K_basal_rule"] = dict(control(scale=1e-6), delta=1e-4)
    found = set(failed(p))
    assert expected <= found, found
    if plant != "unresolved":
        assert found <= expected | {"C0_admission"}, found


def test_undefined_values_fail_through_none():
    p = parts()
    del p["references"]
    assert {"A5pp_start", "A5pp_V_order", "K_prior_swapped", "K_basal_rule_detected",
            "C0_admission"} <= set(failed(p))


def test_every_criterion_metric_resolves_on_a_complete_run():
    _, evaluated = judge.verdict(parts(), PROTOCOL)
    assert [c["id"] for c in evaluated["criteria"] if any(v is None for v in c["values"])] == []


@pytest.mark.parametrize("x, want", [(7.7e-5, 1e-4), (1e-4, 1e-4), (1.1e-4, 2e-4),
                                     (3e-6, 5e-6), (6e-6, 1e-5)])
def test_the_1_2_5_grid(x, want):
    assert judge.round_up_125(x) == pytest.approx(want)


# ------------------------------------------------------------------ the drafter and registration


def test_the_checked_in_judge_section_is_the_drafters():
    assert PROTOCOL["judge"] == json.loads(json.dumps(drafter.judge_section(PROTOCOL)))
    assert PROTOCOL["judged_parts"] == list(generator.PARTS)


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
    assert {k: v for k, v in after.items() if k not in ("status", "registration")} == {
        k: v for k, v in before.items() if k != "status"}


def test_the_judged_entry_refuses_before_writing_anything(tmp_path, monkeypatch):
    out = tmp_path / "out"
    unregistered = tmp_path / "proposed.json"
    unregistered.write_text(json.dumps(proposed()))
    with pytest.raises(SystemExit, match="not registered"):
        generator.main(["judged", str(unregistered), str(out), "a5pp_rung_1ms"])
    data = proposed()
    data.pop("registered_delta", None)
    data["status"] = "registered (a test)"
    data["registration"] = dict(status=data["status"])
    no_delta = tmp_path / "no_delta.json"
    no_delta.write_text(json.dumps(data))
    with pytest.raises(SystemExit, match="registers no delta"):
        generator.main(["judged", str(no_delta), str(out), "a5pp_rung_1ms"])
    data["registered_delta"] = dict(basal=1e-4)
    registered = tmp_path / "registered.json"
    registered.write_text(json.dumps(data))
    monkeypatch.setattr(generator, "ROOT", tmp_path / "checkout")
    with pytest.raises(SystemExit, match="clean execution snapshot"):
        generator.main(["judged", str(registered), str(out), "a5pp_rung_1ms"])
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "SNAPSHOT.json").write_text(json.dumps(dict(
        status="complete", patch_sha256=hashlib.sha256(b"").hexdigest())))
    monkeypatch.setattr(generator, "judged_run_refusal", lambda protocol, root=snapshot: None)
    out.mkdir()
    with pytest.raises(SystemExit, match="exists"):
        generator.main(["judged", str(registered), str(out), "a5pp_rung_1ms"])
    assert not any(out.iterdir())


def test_every_judged_part_has_its_function_and_unit():
    assert set(generator.PARTS) <= set(generator.FUNCTIONS)
    assert set(PROTOCOL["judge"]["units"]) == set(generator.PARTS)
    assert set(drafter.control_checks()) == {p for p in generator.PARTS if p.startswith("K_")}
