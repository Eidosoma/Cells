"""The judges' harness check before scoring (the external review's finding 4, the lead's ruling
of 18 November 2026): incomplete evidence is a harness failure, refused before any score.

- validation/tissue/judge_harness.py: a part's record times against its registered grid, a refusal
  class's examples on both sides, and a criterion's metric that resolves to an empty list.
- FR-6's A5'' judge refuses a judged run whose rung lacks one voltage sample. Before the harness it
  scored the 40 records it still shared with the references. A development verdict over the same
  records is written, with the gap recorded (quick and partial development runs stay admitted).
- FR-10's judge refuses a registered refusal class without examples, and a W2 rung that lacks one
  record. Before the harness, all() passed the empty class.
- FR-1, FR-3, FR-4 and FR-5 catch a dropped record, and FR-1 and FR-3 an empty class.
The registered criteria and the shared evaluator are unchanged: each judge's verdict() still scores
as it did. The judges read the registered inputs directly, as their fixtures do.
"""

import copy
import json

import pytest

from validation.tissue import a5pp_acceptance_judge as a5pp
from validation.tissue import bath_schedule_judge as fr10


def harness():
    from validation.tissue import judge_harness  # Imported here, so the entries' tests run at main.

    return judge_harness

# ------------------------------------------------------------------------------------- harness


def test_grid_refuses_a_missing_or_an_extra_record():
    assert harness().grid("p", [0, 50, 100], [0, 50, 100]) == []
    (missing,) = harness().grid("p", [0, 100], [0, 50, 100])
    assert "2 record times against the registered grid's 3" in missing and "[50]" in missing
    assert harness().grid("p", [0, 50, 100, 150], [0, 50, 100])
    assert harness().grid("p", None, [0, 50])
    assert harness().grid("p", [50, 0], [0, 50])  # The registered order too.


def test_classes_refuse_a_class_without_an_example_on_either_side():
    full = {"R1": {"refused": [{}], "admitted": [{}]}}
    assert harness().classes(full, ["R1"]) == []
    assert harness().classes({"R1": {"refused": [], "admitted": []}}, ["R1"])
    assert harness().classes({"R1": {"refused": [{}], "admitted": []}}, ["R1"])
    assert harness().classes(full, ["R1", "R2"])  # A registered class with no row at all.


def test_metrics_refuse_an_empty_list_and_leave_none_to_the_evaluator():
    criteria = [dict(id="c", metrics=["derived.values"]), dict(id="d", metrics=["derived.gone"])]
    assert harness().metrics(criteria, dict(derived=dict(values=[1.0]))) == []
    (empty,) = harness().metrics(criteria, dict(derived=dict(values=[])))
    assert "criterion c" in empty


def test_refuse_is_a_harness_failure():
    harness().refuse([])
    with pytest.raises(SystemExit, match="incomplete evidence"):
        harness().refuse(["a gap"])


# ----------------------------------------------------------------------------- FR-6's A5''


def a5pp_parts():
    from tests.unit import test_fr6_a5pp_qualification as a5t

    return a5t.parts(), a5t.PROTOCOL


def run_main(module, protocol, parts, tmp_path):
    results = tmp_path / "results.json"
    results.write_text(json.dumps(dict(protocol_id=protocol["id"], parts=parts)))
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    return module.main(["dev", str(path), str(tmp_path / "verdict"), str(results)])


def test_a5pp_scores_complete_evidence(tmp_path):
    parts, protocol = a5pp_parts()
    assert a5pp.incomplete(parts, protocol) == []
    record = run_main(a5pp, protocol, parts, tmp_path)
    assert record["passed"] and record["harness"]["gaps"] == []


def test_a5pp_refuses_a_dropped_voltage_sample(tmp_path):
    parts, protocol = a5pp_parts()
    rung = parts["a5pp_rung_0p5ms"]
    at = rung["record_ms"].index(1000)
    del rung["record_ms"][at]
    for values in rung["series"].values():
        del values[at]
    assert a5pp.verdict(parts, protocol)[1]["passed"]  # Scoring alone passes on 40 records.
    with pytest.raises(SystemExit, match="incomplete evidence.*a5pp_rung_0p5ms"):
        a5pp.harnessed(parts, protocol)  # A judged run's entry.
    record = run_main(a5pp, protocol, parts, tmp_path)  # A development verdict records the gap.
    (gap,) = record["harness"]["gaps"]
    assert gap.startswith("a5pp_rung_0p5ms: 40 record times")


def test_the_judges_read_their_fixtures_registered_inputs():
    from validation.tissue import a5pp_acceptance_fixtures as af
    from validation.tissue import site_occupancy_acceptance_fixtures as so
    from validation.tissue import site_occupancy_acceptance_judge as fr3

    assert (a5pp.INPUTS, a5pp.WORLD) == (af.INPUTS, af.WORLD_ID)
    assert fr3.INPUTS == so.INPUTS


# ------------------------------------------------------------------------------------- FR-10


def fr10_complete():
    """FR-10's evidence on the registered grids, as far as the harness reads it."""
    protocol = json.loads(fr10.Path(fr10.__file__).with_name("bath_schedule_protocol.json")
                          .read_text())
    inputs = json.loads(fr10.INPUTS.read_text())
    d = protocol["judge"]["derivation"]
    parts, worlds = {}, {}
    for world, key in fr10.GRIDS.items():
        grid = inputs[key]["record_times_s"]
        w = d[world]
        for name in (*w["ladder_parts"], w["declared_part"], w["half_part"], f"{world}_control"):
            parts[name] = dict(kind="engine", completed=True, record_s=list(grid), series={})
        worlds[world] = worlds[f"{world}_floor"] = dict(record_s=list(grid), series={})
    parts["references"] = dict(kind="references", worlds=worlds)
    parts["refusals"] = dict(classes={c: {"refused": [{}], "admitted": [{}]}
                                      for c in d["refusal_checks"]})
    return protocol, parts


def test_fr10_complete_evidence_holds_no_gap():
    protocol, parts = fr10_complete()
    assert fr10.incomplete(parts, protocol) == []


@pytest.mark.parametrize("plant", ["empty_class", "missing_record"])
def test_fr10_refuses_incomplete_evidence(plant):
    protocol, parts = fr10_complete()
    if plant == "empty_class":
        first = next(iter(parts["refusals"]["classes"]))
        parts["refusals"]["classes"][first] = {"refused": [], "admitted": []}
        assert fr10.refusal_class(parts["refusals"]["classes"][first], "x") == 1  # all([]).
    else:
        rung = copy.deepcopy(parts["W2_rung_0p5ms"])
        del rung["record_s"][100]
        parts["W2_rung_0p5ms"] = rung
    with pytest.raises(SystemExit, match="incomplete evidence"):
        fr10.harnessed(parts, protocol)  # A judged run's entry: refused before any derivation.


# ------------------------------------------------------- the sibling judges: FR-1, FR-3, FR-4/5


def fr1_complete():
    from validation.tissue import compartment_acceptance_judge as fr1

    protocol = json.loads(fr1.Path(fr1.__file__).with_name("compartment_acceptance_protocol.json")
                          .read_text())
    inputs = json.loads(fr1.INPUTS.read_text())
    d = protocol["judge"]["derivation"]
    compared = {"C3_flux": ["C3_flux"], "C3_first_order": ["C3_first_order"],
                "C5": [d["C5"]["part"]], "C4": [*d["C4"]["ladder_parts"], "K1_one_way"],
                "C6": [*d["C6"]["ladder_parts"], "K2_no_clearance"],
                "C7": list(d["C7"]["ladder_parts"]), "C8": list(d["C8"]["ladder_parts"])}
    parts, worlds = {}, {}
    for world, names in compared.items():
        form, key = fr1.REGISTERED[world]
        grid = list(inputs[form]["worlds"][key]["record_times_s"])
        worlds[world] = worlds[f"{world}_floor"] = dict(record_s=grid)
        for name in names:
            parts[name] = dict(kind="engine", completed=True, record_s=list(grid))
    parts["references"] = dict(worlds=worlds)
    parts["C1_refusals"] = dict(classes={c: {"refused": [{}], "admitted": [{}]}
                                         for c in d["C1"]["checks"]})
    return fr1, protocol, parts


def test_fr1_harness_catches_a_dropped_record_and_an_empty_class():
    fr1, protocol, parts = fr1_complete()
    assert fr1.incomplete(parts, protocol) == []
    rung = parts["C6_rung_0p5ms"]
    rung["record_s"] = rung["record_s"][:150] + rung["record_s"][151:]
    first = next(iter(parts["C1_refusals"]["classes"]))
    parts["C1_refusals"]["classes"][first]["admitted"] = []
    gaps = fr1.incomplete(parts, protocol)
    assert len(gaps) == 2 and gaps[0].startswith("C6_rung_0p5ms") and first in gaps[1]


def fr3_complete():
    from validation.tissue import site_occupancy_acceptance_fixtures as fx
    from validation.tissue import site_occupancy_acceptance_judge as fr3

    protocol = json.loads(fr3.Path(fr3.__file__).with_name(
        "site_occupancy_acceptance_protocol.json").read_text())
    d = protocol["judge"]["derivation"]
    unit = d["record_unit_s"]
    parts, refs = {}, {}
    for name in d["engine_parts"]:
        world = d["world_of"][name]
        grid = [int(round(t / unit)) for t in fx.registered(world)["record_times_s"]]
        refs[world] = dict(record_ms=grid)
        parts[name] = dict(kind="engine", completed=True, record_ms=list(grid))
    arm = d["world_of"][d["engine_parts"][0]]
    for name, spec in d["controls"].items():
        parts[name] = dict(runs={v: dict(arm=arm, record_ms=list(refs[arm]["record_ms"]))
                                 for v in spec})
    parts["references"] = dict(worlds=refs)
    parts["Q6_refusals"] = dict(classes={c: {"refused": [{}], "admitted": [{}]}
                                         for c in d["Q6"]["refusal_checks"]})
    return fr3, protocol, parts


def test_fr3_harness_catches_a_dropped_record_a_short_control_and_an_empty_class():
    fr3, protocol, parts = fr3_complete()
    assert fr3.incomplete(parts, protocol) == []
    del parts["q1_fast_rung_0p25ms"]["record_ms"][5]
    run = next(iter(parts["K_rates"]["runs"].values()))
    run["record_ms"] = run["record_ms"][:-1]
    first = next(iter(parts["Q6_refusals"]["classes"]))
    parts["Q6_refusals"]["classes"][first]["refused"] = []
    gaps = fr3.incomplete(parts, protocol)
    assert [g.split(":")[0] for g in gaps] == ["q1_fast_rung_0p25ms", "K_rates/k_on",
                                                f"refusal class {first}"]


@pytest.mark.parametrize("which", ["fr4-acidification-v1", "fr5-transfer-v1"])
def test_fr45_harness_catches_a_dropped_record(which):
    from validation.tissue import compartment_ph_judge as base

    path = {"fr4-acidification-v1": "fr4_acidification_v1.json",
            "fr5-transfer-v1": "fr5_transfer_v1.json"}[which]
    root = base.Path(base.__file__).resolve().parents[2]
    protocol = json.loads((root / "validation" / "compartment_ph" / "protocols" / path).read_text())
    d = protocol["judge"]["derivation"]
    grid = [float(t) for t in range(0, 61)]
    if which == "fr4-acidification-v1":
        worlds = {w: dict(record_s=list(grid)) for w in ("declared", "floor", "kinetic_outside")}
        names = [*d["ladder_parts"], d["declared_part"], d["half_part"], d["control_parts"][1]]
    else:
        worlds = {w: dict(record_s=list(grid)) for arm in d["arms"] for w in (arm, f"{arm}_floor")}
        names = [n for a in d["arms"].values()
                 for n in (*a["ladder_parts"], a["declared_part"], a["half_part"],
                           a["control_part"])]
    parts = {n: dict(kind="engine", record_s=list(grid)) for n in names}
    parts["reference"] = dict(worlds=worlds)
    assert base.incomplete(parts, protocol) == []
    victim = names[-1]
    parts[victim] = dict(parts[victim], record_s=grid[:30] + grid[31:])
    (gap,) = base.incomplete(parts, protocol)
    assert gap.startswith(victim)
