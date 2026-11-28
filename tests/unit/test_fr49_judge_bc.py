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
