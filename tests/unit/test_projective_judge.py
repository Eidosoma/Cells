"""validation/tissue/projective_judge.py on synthetic saved results.

Each criterion of projective-c-qualification-v1 is evaluated from saved parts
only: accuracy with E(t) = sum of max(estimate, a posteriori) and the floor,
absolute caps judged or (Q1L) reported, energy, the fallback criterion with
amendment 1's readings (reference rows, transient end), the near-fold switch
criteria, pairing by the fine definition's digest, failures, and the
burst-growth check.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from validation.tissue import projective_judge as judge

PROTOCOL = json.loads(judge.PROTOCOL.read_text())
TOL = dict(concentration_mM=1e-3, membrane_voltage_V=1e-5, gate=1e-4)


def definition(changes=()):
    schedule = [dict(time=0.0, availability=0.0)] + [
        dict(time=t, availability=1.0) for t in changes
    ]
    return dict(
        model=dict(id="resolved_pump_tissue@3"),
        experiment=dict(channel_controls=[dict(channel_id="cue_0", schedule=schedule)]),
        execution=dict(dt=1e-3, projective=dict(tolerance=dict(TOL))),
    )


def observation(t, vm=(-0.08,), c=(10.0, 140.0), g=(0.5,)):
    return dict(time_s=t, membrane_voltage_V=list(vm), concentration_mM=list(c), gate=list(g))


def jump(start, stop, estimate=0.5, posterior=0.4, defect=1.0, bound=10.0):
    return dict(
        from_time_s=start,
        to_time_s=stop,
        steps=round((stop - start) / 1e-3),
        estimate_normalized=estimate,
        a_posteriori_normalized=posterior,
        energy_defect_pJ=defect,
        energy_bound_pJ=bound,
        ledgers=dict(electrode=dict(after=1e-26, carried_fine_drift=1e-27, affine_excess=1e-28)),
    )


def report(jumps, fallbacks=(), rejections=()):
    return dict(
        jump_log=list(jumps),
        fallback_log=list(fallbacks),
        rejection_log=list(rejections),
        fine_steps=1000,
        discarded_fine_steps=0,
        traversed_steps=5000,
        step_speedup=5.0,
    )


def projective(observations, jumps, *, digest="abc", changes=(), caps=True, **extra):
    return dict(
        part="projective",
        status="completed",
        definition=definition(changes),
        fine_definition_sha256=digest,
        caps_judged=caps,
        observations=observations,
        report=report(jumps, **extra),
        diagnostics={},
        wall_s=10.0,
        switch_below_m50mV_s=[None],
    )


def reference(observations, *, digest="abc"):
    return dict(
        part="reference",
        status="completed",
        fine_definition_sha256=digest,
        observations=observations,
        diagnostics={},
        wall_s=40.0,
        switch_below_m50mV_s=[None],
    )


def write(directory, name, value):
    (Path(directory) / f"{name}.json").write_text(json.dumps(value))


def test_accuracy_uses_the_larger_estimate_and_the_floor():
    fine = [observation(0.0), observation(20.0)]
    ok = [observation(0.0), observation(20.0, vm=(-0.08 + 0.9e-5,))]  # 2 * 1e-5 * 0.5 = 1e-5
    bad = [observation(0.0), observation(20.0, vm=(-0.08 + 1.1e-5,))]
    early = [observation(0.0, vm=(-0.08 + 2e-9,)), observation(20.0)]  # before any jump
    jumps = [jump(10.0, 12.0, estimate=0.5, posterior=0.3)]
    for mine, outcome in ((ok, "pass"), (bad, "fail"), (early, "fail")):
        result = judge.judge_accuracy(PROTOCOL, projective(mine, jumps), reference(fine))
        assert result["outcome"] == outcome, mine
    posterior = [jump(10.0, 12.0, estimate=0.3, posterior=0.5)]  # max() takes 0.5
    result = judge.judge_accuracy(PROTOCOL, projective(ok, posterior), reference(fine))
    assert result["outcome"] == "pass"
    assert result["table"][1]["effort"] == 0.5


def test_caps_are_judged_or_reported():
    fine = [observation(0.0, c=(10.0, 140.0))]
    mine = [observation(0.0, vm=(-0.08 + 3e-5,), c=(10.0, 140.0))]  # 30 uV over 20 uV
    judged = judge.judge_caps(PROTOCOL, projective(mine, []), reference(fine), judged=True)
    reported = judge.judge_caps(PROTOCOL, projective(mine, []), reference(fine), judged=False)
    assert judged["outcome"] == "fail" and not judged["within"]
    assert reported["outcome"] == "reported" and reported["judged"] is False
    relative = [observation(0.0, c=(10.0 * (1 + 3e-4), 140.0))]
    assert (
        judge.judge_caps(PROTOCOL, projective(relative, []), reference(fine), judged=True)[
            "outcome"
        ]
        == "fail"
    )


def test_energy_fails_a_jump_over_its_bound():
    good = projective([], [jump(10.0, 12.0, defect=1.0, bound=10.0)])
    bad = projective([], [jump(10.0, 12.0, defect=11.0, bound=10.0)])
    assert judge.judge_energy(PROTOCOL, good)["outcome"] == "pass"
    assert judge.judge_energy(PROTOCOL, bad)["outcome"] == "fail"


def rates(fast=()):
    times = np.round(np.arange(0, 1200001) * 1e-3, 6)
    rate = np.zeros_like(times)
    for t in fast:
        rate[int(round(t / 1e-3))] = 1.0  # Above the 1e-3 V/s threshold.
    return dict(times_s=times, max_abs_dvm_dt_V_per_s=rate)


def fallback(jumps, *, fast=(), fallbacks=(), rejections=()):
    mine = projective([], jumps, changes=(900.0,), fallbacks=fallbacks, rejections=rejections)
    return judge.judge_fallback(PROTOCOL, mine, reference([]), rates(fast), onset=900.0)


def test_fallback_criterion_with_amendment_1_readings():
    reacted = [dict(time_s=901.0, reason="voltage_rate")]
    resumed = [jump(500.0, 600.0), jump(950.0, 960.0)]
    ok = fallback(resumed, fast=(900.1, 900.4), fallbacks=reacted)
    assert ok["outcome"] == "pass" and ok["transient_end_s"] == pytest.approx(900.4)
    # A jump over a fast reference row (amendment 1) fails it.
    assert fallback(resumed, fast=(550.0,), fallbacks=reacted)["outcome"] == "fail"
    # A jump containing the scheduled change fails it (the verifying burst is 3 s).
    over = [jump(850.0, 898.0), jump(950.0, 960.0)]
    assert fallback(over, fallbacks=reacted)["outcome"] == "fail"
    # No listed reason within 10 s after the cue fails it.
    late = [dict(time_s=911.0, reason="voltage_rate"), dict(time_s=901.0, reason="cooldown")]
    assert fallback(resumed, fallbacks=late)["outcome"] == "fail"
    # A rejection with a listed reason counts.
    rejected = [dict(from_time_s=905.0, to_time_s=907.0, steps=2000, reason="correction")]
    assert fallback(resumed, rejections=rejected)["outcome"] == "pass"
    # Jumps must resume within 120 s of the transient end.
    assert (
        fallback([jump(500.0, 600.0), jump(1100.0, 1110.0)], fallbacks=reacted)["outcome"] == "fail"
    )


def test_near_fold_switch_branch_and_accuracy():
    fine = [observation(t, vm=(-0.03,) if t < 600 else (-0.08,)) for t in (0.0, 300.0, 900.0)]
    mine = [dict(o) for o in fine]
    p, r = projective(mine, [jump(700.0, 800.0)]), reference(fine)
    r["switch_below_m50mV_s"], p["switch_below_m50mV_s"] = [600.0], [620.0]  # 20 s <= 30 s
    assert judge.judge_near_fold(PROTOCOL, p, r)["outcome"] == "pass"
    p["switch_below_m50mV_s"] = [640.0]  # 40 s > 5 % of 600 s
    assert judge.judge_near_fold(PROTOCOL, p, r)["outcome"] == "fail"
    p["switch_below_m50mV_s"] = [None]
    assert judge.judge_near_fold(PROTOCOL, p, r)["outcome"] == "fail"


def test_cases_pair_by_digest_share_a_reference_and_keep_failures(tmp_path):
    fine = [observation(0.0), observation(20.0)]
    write(tmp_path, "Q1-relax-pair-projective", projective(fine, [jump(10.0, 12.0)]))
    write(tmp_path, "Q1L-relax-pair-loose-projective", projective(fine, [jump(10.0, 15.0)]))
    write(tmp_path, "Q1-relax-pair-reference", reference(fine))
    write(
        tmp_path,
        "A1-pump-pair-projective-failure",
        dict(status="failed", error="NumericalError('refused')", fine_definition_sha256="x"),
    )
    cases = {c["id"]: c for c in PROTOCOL["cases"]}
    q1l = judge.judge_case(PROTOCOL, tmp_path, cases["Q1L-relax-pair-loose"])
    assert q1l["files"]["reference"]["path"].endswith("Q1-relax-pair-reference.json")
    assert q1l["outcome"] == "pass"
    a1 = judge.judge_case(PROTOCOL, tmp_path, cases["A1-pump-pair"])
    assert a1["outcome"] == "fail" and a1["criteria"][0]["id"] == "conservation"
    q2 = judge.judge_case(PROTOCOL, tmp_path, cases["Q2-relax-world"])
    assert q2["outcome"] == "not evaluable"
    other = projective(fine, [], digest="different")
    write(tmp_path, "F1-cue-in-window-projective", other)
    f1 = judge.judge_case(PROTOCOL, tmp_path, cases["F1-cue-in-window"])
    assert f1["outcome"] == "not evaluable"  # No reference with that fine definition.


def test_burst_growth_check_and_overall_verdict(tmp_path):
    states = {
        name: dict(
            cycles=[dict(jump_s=s, fast_max_growth=g) for s, g in ((2.0, 0.001), (120.0, g))]
        )
        for name, g in (("H", 0.007), ("D", 0.024))
    }
    spectrum = dict(burst_steps=3000, slope_steps=250, states=states)
    assert judge.burst_growth(PROTOCOL, spectrum)["outcome"] == "pass"
    states["D"]["cycles"][1]["fast_max_growth"] = 0.2
    assert judge.burst_growth(PROTOCOL, spectrum)["outcome"] == "fail"
    assert judge.burst_growth(PROTOCOL, dict(spectrum, burst_steps=2000))["outcome"] == "fail"
    assert judge.burst_growth(PROTOCOL, None)["outcome"] == "not evaluable"
    result = judge.judge(tmp_path)  # Nothing saved: incomplete, never pass.
    assert result["verdict"] == "incomplete"
    assert result["protocol"]["amendments"] == ["amendment-1", "amendment-2"]
    judge.main([str(tmp_path)])
    with pytest.raises(FileExistsError):  # The judgement is never overwritten.
        judge.main([str(tmp_path)])


def test_f2_switch_onset_is_amendment_2s_first_fast_reference_row():
    data = rates(fast=(5.0, 300.0, 300.5))  # 5 s is before the 10 s window start.
    assert judge.f2_onset(data, 10.0, 1e-3) == pytest.approx(300.0)
    assert judge.f2_onset(rates(fast=(5.0,)), 10.0, 1e-3) is None


def f2_files(directory, fast):
    fine = [observation(t, vm=(-0.03,) if t < 600 else (-0.08,)) for t in (0.0, 300.0, 900.0)]
    mine = projective([dict(o) for o in fine], [jump(650.0, 660.0), jump(950.0, 960.0)], fallbacks=[
        dict(time_s=601.0, reason="voltage_rate")
    ])  # fmt: skip
    ref = reference(fine)
    mine["switch_below_m50mV_s"], ref["switch_below_m50mV_s"] = [610.0], [600.0]
    write(directory, "F2-near-fold-projective", mine)
    write(directory, "F2-near-fold-reference", ref)
    np.savez(directory / "F2-near-fold-reference-rates.npz", **rates(fast=fast))


def test_f2_fallback_uses_the_onset_and_fails_without_one(tmp_path):
    case = next(c for c in PROTOCOL["cases"] if c["id"] == "F2-near-fold")
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    f2_files(tmp_path / "a", fast=(600.0, 600.5))
    f2_files(tmp_path / "b", fast=(5.0,))
    passed = judge.judge_case(PROTOCOL, tmp_path / "a", case)
    fallback = next(c for c in passed["criteria"] if c["id"] == "fallback")
    assert fallback["outcome"] == "pass" and fallback["onset_s"] == pytest.approx(600.0)
    missing = judge.judge_case(PROTOCOL, tmp_path / "b", case)
    fallback = next(c for c in missing["criteria"] if c["id"] == "fallback")
    assert fallback["outcome"] == "fail" and "amendment 2" in fallback["reason"]


def test_q2_is_judged_on_its_five_cell_run_after_a_global_charge_refusal(tmp_path):
    fine = [observation(0.0), observation(20.0)]
    refusal = "NumericalError('Resolved pump accounting failed: global_charge')"
    write(tmp_path, "Q2-relax-world-projective-failure", dict(status="failed", error=refusal))
    write(tmp_path, "Q2-relax-world-5cell-projective", projective(fine, [jump(10.0, 12.0)]))
    write(tmp_path, "Q2-relax-world-5cell-reference", reference(fine))
    entry = next(c for c in judge.judge(tmp_path)["cases"] if c["id"] == "Q2-relax-world")
    assert entry["run"] == "Q2-relax-world-5cell" and entry["outcome"] == "pass"
    assert entry["seven_cell_refusal_reported"]["outcome"] == "fail"
    other = tmp_path / "other"
    other.mkdir()
    electrode = "NumericalError('Resolved pump accounting failed: electrode')"
    write(other, "Q2-relax-world-projective-failure", dict(status="failed", error=electrode))
    write(other, "Q2-relax-world-5cell-projective", projective(fine, []))
    entry = next(c for c in judge.judge(other)["cases"] if c["id"] == "Q2-relax-world")
    assert entry["run"] == "Q2-relax-world" and entry["outcome"] == "fail"  # Not a fallback.
