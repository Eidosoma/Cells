"""The S5 judge entries' verdicts, pure functions of a report and the protocol (tier 1).

Synthetic reports shaped as each judge entry builds them, after the JSON round trip the entry
makes before its verdict (record times become the protocol's string keys). Nothing here draws a
set or runs a judge entry.
"""

import json

from validation.division import egg_division_world as egg
from validation.division import q2_rops_comparison as q2
from validation.division import q3_tissue_comparison as q3
from validation.division import q5_order as q5


def round_trip(report):
    return json.loads(json.dumps(report))


def test_q3s_verdict_reads_the_protocols_record_keys():
    t = 0.0025
    report = round_trip(
        {"worlds": {"w": {"per_record": {t: {"engine_minus_reference": {"V": 1e-7}}}}}}
    )
    item = {
        "tolerances": {
            "worlds": {"w": {"quantities": {"V": {"records": {str(t): {"tolerance": 2e-7}}}}}}
        }
    }
    assert q3.verdict(report, item)["verdict"] == "pass"
    item["tolerances"]["worlds"]["w"]["quantities"]["V"]["records"][str(t)]["tolerance"] = 5e-8
    assert q3.verdict(report, item)["verdict"] == "fail"


def test_q5s_verdict_judges_the_stop_rules_only():
    report = round_trip(
        {
            "worlds": {
                "w": {
                    "V": {"measurable": 3, "every_step_term_decreases": True, "order_min": 1.5},
                    "lumen": {"measurable": 0, "every_step_term_decreases": False},
                }
            }
        }
    )
    assert q5.verdict(report)["verdict"] == "pass"  # Orders are reported, not banded.
    report["worlds"]["w"]["V"]["every_step_term_decreases"] = False
    assert q5.verdict(report)["verdict"] == "stop"


def test_the_egg_verdict():
    diagnostics = {"max_balance_error_fmol": 2.0e-10}
    report = round_trip(
        dict(
            diagnostics=diagnostics,
            replay_diagnostics=dict(diagnostics),
            negative_control="Resolved pump accounting failed: local",
        )
    )
    assert egg.verdict(report)["verdict"] == "pass"
    assert egg.verdict(dict(report, negative_control="passed (...)"))["verdict"] == "fail"
    assert egg.verdict(dict(report, replay_diagnostics={}))["verdict"] == "fail"


FIXED = "asymmetric neighbour world, bound state"
NEAR = "asymmetric neighbour world, seen spread 1 draw 35"


def q2_report(worst, caught, baseline, faithful=True, misses=()):
    """A Q2 report; misses: (case, control) pairs whose targets miss the threshold."""
    controls = {}
    for label in (FIXED, NEAR):
        entry = {"baseline": {"any key": baseline}, "construction": {"faithful": faithful}}
        for control, targets in q2.CONTROL_TARGETS.items():
            hit = caught and (label, control) not in misses
            entry[control] = {"targets_caught_at_threshold": {g: hit for g in targets}}
        controls[label] = entry
    new = {
        "cases": {"c": {"worst": worst}},
        "simultaneous": {"s": {"one then two": {"worst": worst}}},
        "random": {"w": {"spread 1": {"worst": worst}}},
        "negative_controls": controls,
    }
    return round_trip({"scales": {"new": new}})


def test_q2s_verdict():
    item = {"negative_controls": {"threshold": q2.THRESHOLD}}
    assert q2.verdict(q2_report(10.0, True, 1.0), item)["verdict"] == "pass"
    assert q2.verdict(q2_report(65.0, True, 1.0), item)["verdict"] == "fail"
    assert q2.verdict(q2_report(10.0, False, 1.0), item)["verdict"] == "fail"
    # A near-zero case must pass undefected at the new scale.
    assert q2.verdict(q2_report(10.0, True, 65.0), item)["verdict"] == "fail"
    # An engine-side control's construction must reproduce the engine's own event.
    assert q2.verdict(q2_report(10.0, True, 1.0, faithful=False), item)["verdict"] == "fail"
    # The third amendment: on a near-zero case a_k, the mismatch scale and transference are
    # reported, not judged; the frozen rule (reported=()) judged them there too.
    near_miss = q2_report(10.0, True, 1.0, misses={(NEAR, "mismatch scale")})
    assert q2.verdict(near_miss, item)["verdict"] == "pass"
    assert q2.verdict(near_miss, item, reported=())["verdict"] == "fail"
    for control in q2.NEAR_ZERO_REPORTED:  # Judged on the fixed cases.
        fixed_miss = q2_report(10.0, True, 1.0, misses={(FIXED, control)})
        assert q2.verdict(fixed_miss, item)["verdict"] == "fail"
    for control in set(q2.CONTROL_TARGETS) - set(q2.NEAR_ZERO_REPORTED):  # Judged everywhere.
        assert (
            q2.verdict(q2_report(10.0, True, 1.0, misses={(NEAR, control)}), item)["verdict"]
            == "fail"
        )
