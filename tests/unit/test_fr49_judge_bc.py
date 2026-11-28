"""FR-49's Parts B and C judge and driver, host only (validation/fr49/judge_bc.py, driver_bc.py).

- The judge's run table (RUNS) is the driver's (JOBS), field for field: the judge's literals against
  the jobs (D424), kept as a row.
- The reader takes a references file built in the results layout from the registered spec, and
  refuses each malformed form by its reason, never reading a value: D308's reader, before its tag.
  The invented format samples are read by `--check-reader` (its record is the tag's evidence).
- The order rule, the inconclusive rule and a part's verdict, on numbers given here.
- B6, the host row: the node-owned variant's site layout is the facing population's, bit for bit.
Seconds and reason (D224): about 2 s, no compile; the judge is the registered instrument of Parts B
and C.
"""

import copy
import json

import numpy as np
import pytest

from validation.fr49 import driver_bc, judge_bc

CASES = json.loads(judge_bc.SPEC.read_text())


def test_the_judges_run_table_is_the_drivers_jobs():
    assert {row[0]: tuple(row[1:]) for row in driver_bc.JOBS} == judge_bc.RUNS
    assert driver_bc.FIELDS[1:] == judge_bc.JOB_FIELDS


def reference(world):
    """A references file in the results layout, the registered spec's declared values, and numbers
    that are placeholders: the reader reads structure and declared inputs only."""
    v = CASES["worlds"][world]
    times = judge_bc.sample_times(world)
    doc = dict(kind=judge_bc.KIND, protocol=judge_bc.PROTOCOL, world=world,
               inputs=dict(invented=False), sample_times_s=[f"{t:g}" for t in times],
               method=dict(second_route=dict(declared_accuracy="1e-20", within=True)))  # fmt: skip
    declared = {k: copy.deepcopy(v[k]) for k in judge_bc.DECLARED[world]}
    if world in ("B", "C2"):
        declared.update(sample_times_rule=v["sample_times_s"]["rule"], sites_per_fmol="602214076")
    if world == "B":
        declared["wash_elsewhere"] = {
            k: v["wash_elsewhere"][k] for k in ("node", "time_s", "fraction")
        }
    if world == "C1":
        declared["wash"] = copy.deepcopy(v["wash"])
        doc["well"] = dict.fromkeys(judge_bc.WELL_KEYS, "1e-4")
    doc["declared"] = declared
    for q in judge_bc.QUANTITIES[world]:
        doc[q] = ["1e-4"] * len(times)
    if world in judge_bc.ONCE:
        doc["once"] = dict.fromkeys(judge_bc.ONCE[world], "1e-4")
    return doc


def written(tmp_path, doc):
    path = tmp_path / f"{doc['world']}.json"
    path.write_text(json.dumps(doc))
    return path


@pytest.mark.parametrize("world", ["B", "C1", "C2"])
def test_the_reader_takes_the_layout(tmp_path, world):
    found = judge_bc.read_reference(written(tmp_path, reference(world)), world)
    assert all(
        len(found[q]) == len(judge_bc.sample_times(world)) for q in judge_bc.QUANTITIES[world]
    )
    assert found["cross_checks"] == [("method.second_route.within", True)]


def _edit(world, change):
    doc = reference(world)
    change(doc)
    return doc


REFUSED = {
    "another kind": ("B", lambda d: d.update(kind="other@1"), "kind is"),
    "another world": ("B", lambda d: d.update(world="C2"), "world is"),
    "an invented sample read as the references": (
        "C2",
        lambda d: d["inputs"].update(invented=True),
        "inputs.invented is true",
    ),
    "a declared value not the spec's": (
        "B",
        lambda d: d["declared"].update(k_off_per_s="2e-3"),
        "declared k_off_per_s",
    ),
    "the wash elsewhere at another time": (
        "B",
        lambda d: d["declared"]["wash_elsewhere"].update(time_s="200"),
        "declared wash_elsewhere.time_s",
    ),
    "another sample-time rule": (
        "C2",
        lambda d: d["declared"].update(sample_times_rule="t_i = 10 i"),
        "sample_times_rule",
    ),
    "C1's buffer at another concentration": (
        "C1",
        lambda d: d["declared"]["wash"].update(buffer_mM={"S": "2e-9"}),
        "declared wash.buffer_mM",
    ),
    "a missing sample time": ("B", lambda d: d["sample_times_s"].pop(), "is not among the file's"),
    "a quantity of another length": ("C2", lambda d: d["B2"].pop(), "B2 has 100 entries"),
    "a quantity that is not finite": ("B", lambda d: d["n_L"].__setitem__(3, "nan"), "not finite"),
    "a missing once value": ("C2", lambda d: d["once"].pop("B2*"), "once.B2*"),
    "a missing well value": ("C1", lambda d: d["well"].pop("x_W_after"), "well.x_W_after"),
    "no cross-check": ("B", lambda d: d.update(method={}), "no cross-check"),
}


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_the_reader_refuses_by_reason(tmp_path, name):
    world, change, words = REFUSED[name]
    with pytest.raises(judge_bc.ReaderError, match=words):
        judge_bc.read_reference(written(tmp_path, _edit(world, change)), world)


def test_the_order_and_inconclusive_rules_and_a_parts_verdict():
    assert judge_bc._order(8e-9, 1e-9)[1:] == (True, True)  # A ratio of 8.
    assert judge_bc._order(4e-9, 1e-9)[2] is False  # Second order, outside the window.
    assert judge_bc._order(5e-13, 4e-13)[1:] == (False, True)  # Under the floor: e(0.05) < 1e-12.
    assert judge_bc._order(5e-13, 2e-12)[1:] == (False, False)
    within, outside = [("m.within", True)], [("m.within", True), ("n.within", False)]
    assert judge_bc._criterion(True, True, within) == dict(passed=True, inconclusive=False)
    assert judge_bc._criterion(True, True, outside) == dict(passed=False, inconclusive=True)
    assert judge_bc._criterion(True, False, outside)["passed"] is True  # Engine-only.
    ok, open_ = dict(passed=True, inconclusive=False), dict(passed=False, inconclusive=True)
    caught, missed = dict(caught=True), dict(caught=False)
    assert judge_bc.part_verdict({"x": ok}, {"a": caught}) == "passed"
    assert judge_bc.part_verdict({"x": ok, "y": open_}, {"a": caught}) == "inconclusive"
    assert judge_bc.part_verdict({"x": ok}, {"a": missed}) == "failed"
    assert judge_bc.part_verdict({"x": dict(passed=False)}, {"a": caught}) == "failed"


def test_b6_the_node_owned_variants_layout_is_the_facing_ones():
    found = judge_bc.b_six()
    assert found["passed"] and found["differing"] == [], found


# -------------------------------------------------- the judge end to end, on numbers given here

B_STAR, B1_STAR, B2_STAR = 9.7e-5, 5.7e-5, 4.0e-5  # Invented: the judge's own arithmetic is tested.


def _profile(times, end, late_from):
    """A rising profile that equals `end` exactly from `late_from` on."""
    t = np.asarray(times, dtype=float)
    return np.where(t >= late_from, end, end * (1 - np.exp(-t / 20.0)))


def _engine(profile, times, dt):
    """The profile with a third-order-sized departure early on: 8e-9 at 0.1 s, 1e-9 at 0.05 s."""
    delta = 8e-9 if dt == 0.1 else 1e-9
    return profile * (1 + np.where(np.asarray(times) < 100.0, delta, 0.0))


def _record(records, run_id, *, times=None, quantities=None, arrays=None, refused=False, **extra):
    job = driver_bc.job((run_id, *judge_bc.RUNS[run_id]))
    doc = dict(kind=judge_bc.RECORD_KIND, protocol=judge_bc.PROTOCOL, job=job, **extra)
    if refused:
        doc.update(outcome="refused", refusal=dict(cls="ConfigError", message="planted refusal"))
    else:
        doc.update(
            outcome="completed",
            times=[float(t).hex() for t in times],
            quantities={k: [float(x).hex() for x in v] for k, v in quantities.items()},
        )
        np.savez(records / f"{run_id}.npz", **arrays)
    (records / f"{run_id}.json").write_text(json.dumps(doc))


def _fabricate(tmp_path, refused=()):
    records, refs = tmp_path / "records", tmp_path / "refs"
    records.mkdir()
    refs.mkdir()
    # World B: the references' B, and the engine's at both steps, its twin, and plants (b)-(d).
    tb = np.asarray(judge_bc.sample_times("B"))
    b_ref = _profile(tb, B_STAR, judge_bc.B4_FROM)
    doc = reference("B")
    doc["B"] = [repr(float(x)) for x in b_ref]
    doc["once"]["B*"] = repr(B_STAR)
    (refs / "B.json").write_text(json.dumps(doc))
    total = 1e-4
    lys = np.zeros((tb.size, 4))
    shared = dict(
        lys_rows=lys,
        site_free_increment_fmol=np.zeros((tb.size, 1)),
        site_bound_increment_fmol=np.zeros((tb.size, 1)),
        wash_applied_well=(tb > 300).astype(int),
        wash_applied_lys=np.zeros(tb.size),
    )
    for run_id, dt in (("B-dt0.1", 0.1), ("B-dt0.05", 0.05), ("B-twin-dt0.1", 0.1)):
        bound = _engine(b_ref, tb, dt)
        q = dict(n_L=total - bound, B=bound, R=9.96e-5 - bound)
        _record(records, run_id, times=tb, quantities=q, arrays=shared, refused=run_id in refused)
    planted = {
        "B-plant-b-dt0.1": dict(n_L=np.full(tb.size, total), B=np.full(tb.size, 1e-12)),
        "B-plant-c-dt0.1": dict(n_L=total - 0.99 * b_ref, B=0.99 * b_ref),
        "B-plant-d-dt0.1": dict(n_L=total - b_ref - np.where(tb > 300, 2e-6, 0.0), B=b_ref),
    }
    for run_id, q in planted.items():
        arrays = dict(shared, lys_rows=lys + (1e-9 if run_id.endswith("d-dt0.1") else 0.0))
        _record(records, run_id, times=tb, quantities=dict(q, R=9.96e-5 - q["B"]), arrays=arrays,
                refused=run_id in refused)  # fmt: skip
    # C1: the well's values just before and after the wash, the engine's at 900 s and 902 s.
    doc = reference("C1")
    well = dict(x_W_before=6e-4, b_W_before=4e-4, x_W_after=3e-4, b_W_after=2.000005e-4)
    doc["well"].update({k: repr(v) for k, v in well.items()})
    (refs / "C1.json").write_text(json.dumps(doc))
    tc = np.asarray([0.0, 900.0, 902.0, 3600.0])
    rows = dict(O_rows=np.ones((4, 8)), C_rows=np.ones((4, 8)), O_shares=np.zeros((4, 1, 2)),
                C_shares=np.zeros((4, 1, 2)))  # fmt: skip
    for run_id, x_after in (("C1-dt2", 3e-4), ("C1-twin-dt2", 3e-4), ("C1-plant-dt2", 3.000005e-4)):
        n = np.asarray([1e-3, 1e-3, x_after + 2.000005e-4, x_after + 2.000005e-4])
        x = np.asarray([6e-4, 6e-4, x_after, x_after])
        q = dict(n_O=n, n_C=n, n_W=n, share_x_O=x / n, share_x_C=x / n, share_x_W=x / n,
                 share_base_W=1 - x / n)  # fmt: skip
        _record(records, run_id, times=tc, quantities=q, arrays=rows, refused=run_id in refused,
                label_closure_relative_max=0.0)  # fmt: skip
    # C2: two ligands' B against their references, each conserved; the plant misses B1*.
    t2 = np.asarray(judge_bc.sample_times("C2"))
    refs_c2 = {
        "B1": _profile(t2, B1_STAR, judge_bc.C2_3_FROM),
        "B2": _profile(t2, B2_STAR, judge_bc.C2_3_FROM),
    }
    doc = reference("C2")
    for q_name, values in refs_c2.items():
        doc[q_name] = [repr(float(x)) for x in values]
    doc["once"].update({"B1*": repr(B1_STAR), "B2*": repr(B2_STAR)})
    (refs / "C2.json").write_text(json.dumps(doc))
    for run_id, dt, miss in (
        ("C2-dt0.1", 0.1, 1.0),
        ("C2-dt0.05", 0.05, 1.0),
        ("C2-plant-dt0.1", 0.1, 0.999),
    ):
        b1 = _engine(refs_c2["B1"], t2, dt) * miss
        b2 = _engine(refs_c2["B2"], t2, dt)
        q = dict(n_L1=6e-5 - b1, B1=b1, n_L2=6e-5 - b2, B2=b2, R=9.96e-5 - b1 - b2)
        arrays = dict(lys_rows=np.zeros((t2.size, 4)))
        _record(records, run_id, times=t2, quantities=q, arrays=arrays, refused=run_id in refused)
    return records, refs


def test_the_judge_end_to_end_passes_honest_records_and_catches_every_plant(tmp_path):
    """The criteria's code on numbers given here, under the driver's record names: honest runs pass
    every criterion of the three parts, and each plant fails its registered criterion."""
    verdict = judge_bc.judge(*_fabricate(tmp_path))
    assert verdict["verdict"] == "passed", json.dumps(verdict, default=str)[:2000]
    plants = {
        w: {k: p["fails"] for k, p in v["plants"].items()} for w, v in verdict["parts"].items()
    }
    assert plants == {"B": {"a": ["B4"], "b": ["B2", "B4"], "c": ["B4"], "d": ["B2", "B5"]},
                      "C1": {"c1": ["C1-2"]}, "C2": {"c2": ["C2-3"]}}  # fmt: skip
    assert verdict["parts"]["B"]["criteria"]["B3"]["ratio"] == pytest.approx(8.0)
    json.dumps(verdict, default=float)  # The verdict file's write.


def test_a_refused_plant_run_is_not_the_registrations_catch(tmp_path):
    verdict = judge_bc.judge(*_fabricate(tmp_path, refused=("B-plant-c-dt0.1",)))
    assert verdict["parts"]["B"]["verdict"] == "failed"
    assert verdict["parts"]["B"]["plants"]["c"]["refused"]["message"] == "planted refusal"
    assert verdict["parts"]["C1"]["verdict"] == verdict["parts"]["C2"]["verdict"] == "passed"


def test_a_record_of_another_job_is_refused(tmp_path):
    records, refs = _fabricate(tmp_path)
    doc = json.loads((records / "C2-dt0.05.json").read_text())
    doc["job"]["dt"] = 0.025
    (records / "C2-dt0.05.json").write_text(json.dumps(doc))
    with pytest.raises(judge_bc.ReaderError, match="not the registered run C2-dt0.05"):
        judge_bc.judge(records, refs)


def test_every_registered_job_builds_and_parses_and_each_definition_plant_changes_one_rate():
    """The twelve jobs through the driver's own builder, each engine plant entered: they parse (no
    step), and the two definition plants change exactly one declared rate each."""
    from cells.definitions.specs import parse_spec
    from validation.fr49 import plants_bc

    changed = {}
    for row in driver_bc.JOBS:
        entry = driver_bc.job(row)
        with plants_bc.engine(entry["plant"]):
            raw = driver_bc.raw_world(entry)
            parse_spec(raw)
        if entry["plant"] in ("c", "c2"):
            honest = driver_bc.raw_world(dict(entry, plant=None))
            pairs = zip(honest["model"]["operators"], raw["model"]["operators"], strict=True)
            blocks = [(a, b) for a, b in pairs if a != b]
            ((before, after),) = blocks
            changed[entry["plant"]] = [
                (p["id"], k, before["populations"][i][k], v)
                for i, p in enumerate(after["populations"])
                for k, v in p.items()
                if before["populations"][i][k] != v
            ]
    assert changed == {
        "c": [("lumen_sites", "dissociation_rate_per_s", 1e-3, 2e-3)],
        "c2": [("m_L2", "association_rate_per_mM_per_s", 500.0, 1000.0)],
    }


@pytest.mark.parametrize(
    "row, judged, refused",
    [
        (("B-dt0.1", "B", 0.1, 600.0, 5.0, True, None), False, "runs only with --judged"),
        (("B-dt0.1", "B", 0.1, 600.0, 5.0, True, None), True, None),
        (("dev-C2", "C2", 0.05, 2000.0, 20.0, None, None), False, "registered horizon"),
        (("dev-C1", "C1", 2.0, 3600.0, 60.0, True, None), True, "registered horizon"),
        (("dev-C2", "C2", 0.05, 200.0, 20.0, None, None), False, None),
    ],
    ids=[
        "registered, not judged",
        "registered, judged",
        "dev at full length",
        "dev at full length, judged",
        "dev, shortened",
    ],
)
def test_the_first_run_rule(row, judged, refused):
    """The driver's first-run rule (the lead, 28 November 2026): a registered world first runs at
    its registered length only in a judged run, so a dev- job at that horizon is refused."""
    found = driver_bc.first_run_refusal(driver_bc.job(row), judged)
    assert (found is None) if refused is None else (refused in found)
