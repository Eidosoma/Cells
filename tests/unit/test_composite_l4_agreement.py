"""The L4 agreement driver's CPU-only parts (validation/tissue/composite_l4_agreement.py).

Terms, the variant rule, the stop rule and the variant protocols, on synthetic saved runs
against the registered W1, W2 and G2-Q1 protocols (no engine run).
"""

import copy
import json

import pytest

from validation.tissue import composite_l4_agreement as agreement

W7 = "W7/literature"


def w1_run(volume=1.0, converged=True):
    return dict(
        trajectories={"P1": {"0.0": {"cell_volume_pL": [volume]}}},
        stationary={"H": dict(converged=converged, volume_pL=0.7, membrane_voltage_V=-0.05)},
    )


def w2_run(classification="stable", voltage=-0.08):
    return {
        "red_cell_15-kaji_s0.12": {
            "0": dict(
                converged=True,
                classification=classification,
                volume_pL=0.7,
                membrane_voltage_V=voltage,
                route_cycles_fmol_s=3e-5,
            )
        }
    }


def g2_run(voltage=-0.05):
    record = dict(
        time_s=0.0, membrane_voltage_V=[voltage, -0.06], slot_amount_fmol={"1": [1.0, 2.0]}
    )
    return {W7: [record]}


def test_up1_is_the_methods_rounding():
    assert agreement.up1(2.543043109426435e-09) == 3e-09
    assert agreement.up1(1e-06) == 1e-06
    assert agreement.up1(9.35552637706949e-07) == 1e-06
    assert agreement.up1(0.0) == 0.0


def test_widening_never_tightens_and_keeps_the_registered_value_when_nothing_is_added():
    assert agreement.widen(2.5e-9, 0.0, 0.0, summed=True) == (2.5e-9, False)
    new, stop = agreement.widen(3e-6, 2e-6, 0.0, summed=True)  # Above the sum 1e-6: stop.
    assert new == agreement.up1(3 * (1e-6 + 2e-6)) and stop
    new, stop = agreement.widen(1e-6, 1e-7, 1e-7, summed=False)
    assert new == 1e-6 and not stop  # 3 x 2e-7 = 6e-7 stays below the fixed bound.


@pytest.mark.parametrize(("part", "run"), [("w1", w1_run()), ("w2", w2_run()), ("g2", g2_run())])
def test_cpu_against_cpu_gives_the_registered_protocol(part, run):
    protocol = agreement.registered(part)[1]
    out = agreement.variant(part, protocol, agreement.measured(part, run, run, run))
    report = out.pop("backend_variant")
    assert report["status"] == agreement.STATUS
    assert out == protocol  # Zero terms: every field and tolerance exactly as registered.
    assert not report["stop"] and report["rows"]
    assert all(row["widening"] == 1.0 for row in report["rows"])


def test_the_stop_rule():
    protocol = agreement.registered("w1")[1]
    tolerance = protocol["tolerances"]["P1"]["cell_volume_pL"]
    a = w1_run(volume=1.0 + tolerance)  # A backend term above the registered sum.
    out = agreement.variant("w1", protocol, agreement.measured("w1", w1_run(), a, a))
    assert out["backend_variant"]["stop_items"] == ["P1/cell_volume_pL"]
    assert out["tolerances"]["P1"]["cell_volume_pL"] >= tolerance
    changed = w1_run(converged=False)
    out = agreement.variant("w1", protocol, agreement.measured("w1", w1_run(), changed, changed))
    assert out["backend_variant"]["stop_items"] == ["H"]
    protocol = agreement.registered("w2")[1]
    flipped = w2_run(classification="unstable")
    out = agreement.variant("w2", protocol, agreement.measured("w2", w2_run(), flipped, flipped))
    assert out["backend_variant"]["stop"]
    shifted = g2_run(voltage=-0.05 + 1e-3)
    protocol = agreement.registered("g2")[1]
    out = agreement.variant("g2", protocol, agreement.measured("g2", g2_run(), shifted, shifted))
    assert f"{W7}/q3_membrane_voltage_V" in out["backend_variant"]["stop_items"]


def test_variant_rows_follow_the_rule():
    protocol = agreement.registered("w2")[1]
    a = w2_run(voltage=-0.08 + 2e-7)
    out = agreement.variant("w2", protocol, agreement.measured("w2", w2_run(), a, w2_run()))
    (row,) = [r for r in out["backend_variant"]["rows"] if r["item"] == "voltage_V"]
    expected = max(protocol["stationary"]["voltage_V"], agreement.up1(3 * (2e-7 + 2e-7)))
    assert row["backend"] == pytest.approx(2e-7) and row["tolerance"] == expected
    assert out["stationary"]["voltage_V"] == expected


RUNS = dict(w1=w1_run(), w2=w2_run(), g2=g2_run())


def registered_variant(part):
    protocol = agreement.registered(part)[1]
    run = RUNS[part]
    out = agreement.variant(part, protocol, agreement.measured(part, run, run, run))
    out["backend_variant"]["status"] = "registered at a lead's commit (test)"
    return protocol, out


def judged(part, protocol, tmp_path):
    path = tmp_path / f"{part}.json"
    path.write_text(json.dumps(protocol))
    return agreement.judged_protocol(part, path)[1:]


@pytest.mark.parametrize("part", ["w1", "w2", "g2"])
def test_judged_runs_take_the_registered_protocol_or_a_registered_variant(part, tmp_path):
    protocol, out = registered_variant(part)
    assert out["backend_variant"]["base"] == agreement.BASES[part]
    assert judged(part, protocol, tmp_path) == (True, "the registered protocol")
    assert judged(part, out, tmp_path)[0]
    (site, *_) = agreement.tolerance_sites(part, protocol)
    widened = copy.deepcopy(out)
    parent = agreement._at(widened, site[:-1])
    parent[site[-1]] = 2 * parent[site[-1]]  # A wider tolerance stays a registered variant.
    assert judged(part, widened, tmp_path)[0]


@pytest.mark.parametrize("part", ["w1", "w2", "g2"])
def test_judged_runs_refuse_other_files(part, tmp_path):
    protocol, out = registered_variant(part)
    site = agreement.tolerance_sites(part, protocol)[0]
    proposed = copy.deepcopy(out)
    proposed["backend_variant"]["status"] = agreement.STATUS
    ok, reason = judged(part, proposed, tmp_path)
    assert not ok and "does not say registered" in reason
    edited = copy.deepcopy(out)
    edited["edited_field"] = "not in the registered protocol"
    ok, reason = judged(part, edited, tmp_path)
    assert not ok and "a field other than the widened tolerances differs" in reason
    plain = copy.deepcopy(protocol)  # An edited protocol, not a variant.
    parent = agreement._at(plain, site[:-1])
    parent[site[-1]] = 2 * parent[site[-1]]
    ok, reason = judged(part, plain, tmp_path)
    assert not ok and "no backend_variant block" in reason
    tighter = copy.deepcopy(out)
    parent = agreement._at(tighter, site[:-1])
    parent[site[-1]] = 0.5 * parent[site[-1]]
    ok, reason = judged(part, tighter, tmp_path)
    assert not ok and "at least as registered" in reason
    elsewhere = copy.deepcopy(out)
    elsewhere["backend_variant"]["base"] = "validation/tissue/another_protocol.json"
    ok, reason = judged(part, elsewhere, tmp_path)
    assert not ok and "does not name the base protocol" in reason


def test_the_g2_judge_marks_other_protocols_dry(tmp_path):
    from validation.tissue import cell_replacement_judge as judge

    protocol, out = registered_variant("g2")
    path = tmp_path / "variant.json"
    path.write_text(json.dumps(out))
    dry, acceptance = judge.run_kind(path)
    assert not dry and acceptance.startswith("a registered backend variant")
    assert judge.run_kind() == (False, None)  # The default is unchanged.
    out["backend_variant"]["status"] = agreement.STATUS
    path.write_text(json.dumps(out))
    dry, acceptance = judge.run_kind(path)
    assert dry and acceptance.startswith("dry run only")
    path.write_text(json.dumps(protocol))
    assert judge.run_kind(path) == (False, "the registered protocol")
    assert judge.run_kind(path, parameters=tmp_path / "p.json")[0]  # Still a dry run.


def test_w2_reads_the_qualifications_own_judge_output(tmp_path):
    item = dict(arm="red_cell_15-kaji_s0.12", branch=0, **w2_run()["red_cell_15-kaji_s0.12"]["0"])
    path = tmp_path / "w2-judge.json"
    path.write_text(json.dumps(dict(verdict="pass", items=[copy.deepcopy(item)])))
    assert agreement.load_run("w2", path) == w2_run()
