"""FR-49's Parts B and C judge and driver, host only (validation/fr49/judge_bc.py, driver_bc.py).

- The judge's run table (RUNS) is the driver's (JOBS), field for field: the judge's literals against
  the jobs (D424), kept as a row.
- The reader takes a references file built in the results layout from the registered spec, and
  refuses each malformed form by its reason, never reading a value: D308's reader, before its tag.
  The invented format samples are read by `--check-reader` (its record is the tag's evidence).
- The order rule, the inconclusive rule and a part's verdict, on numbers given here.
- B6, the host row: the node-owned variant's site layout is the facing population's, bit for bit.
- The judge end to end on records fabricated here on each run's dt grid: honest records pass and
  each plant fails its registered criterion; a record off its registered rows is refused (reading
  3); B5 is gated on the wash's counts and scored for plant (d) only; C1-3 bounds the closure on
  every row (READING-2).
- The driver's first-run rule and fresh-process rule, and C1's plant against the engine's exchange.
Seconds and reason (D224): about 4 s, no compile; the judge is the registered instrument of Parts B
and C.
"""

import copy
import json
import shutil

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
        doc["method"]["well_second_route"] = dict(declared_accuracy="1e-20", within=True)
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
    well = [("method.well_second_route.within", True)] if world == "C1" else []
    assert found["cross_checks"] == [("method.second_route.within", True), *well]


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
    "C1 with no cross-check of the well": (
        "C1",
        lambda d: d["method"].pop("well_second_route"),
        "no cross-check of the well",
    ),
    "C1 whose well-like check is method.wellX": (
        "C1",
        lambda d: d["method"].update(wellX=d["method"].pop("well_second_route")),
        "no cross-check of the well",
    ),
}


@pytest.mark.parametrize(
    "path, matched",
    [
        ("method.well_second_route.within", True),
        ("method.well.second_route.within", True),
        ("method.wellX.within", False),
        ("method.wells.within", False),
        ("method.well_second_routeX.within", False),
        ("method.world_L.second_routes.ode_radau.within", False),
        ("method.within_declared_accuracy", False),
    ],
)
def test_c1_2s_cross_checks_are_the_wells_by_exact_name(path, matched):
    """READING-2: the well's checks are those named exactly `well` or `well_second_route` directly
    under `method`, never by a bare prefix."""
    assert judge_bc.well_checks([(path, True)]) == ([(path, True)] if matched else [])


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
WASH_B, WASH_C1 = 300.0, 900.0  # s: the spec's wash times.
EPS = float(np.finfo(float).eps)


def _grid(run_id):
    """A run's rows: its dt grid from 0 to its horizon (reading 3)."""
    _, dt, end, _, _, _ = judge_bc.RUNS[run_id]
    return np.arange(int(round(end / dt)) + 1, dtype=float) * dt


def _profile(times, end, late_from):
    """A rising profile that equals `end` exactly from `late_from` on."""
    t = np.asarray(times, dtype=float)
    return np.where(t >= late_from, end, end * (1 - np.exp(-t / 20.0)))


def _engine(profile, times, dt):
    """The profile with a third-order-sized departure early on: 8e-9 at 0.1 s, 1e-9 at 0.05 s."""
    delta = 8e-9 if dt == 0.1 else 1e-9
    return profile * (1 + np.where(np.asarray(times) < 100.0, delta, 0.0))


def _record(records, run_id, *, quantities=None, arrays=None, refused=False, **extra):
    job = driver_bc.job((run_id, *judge_bc.RUNS[run_id]))
    k = list(judge_bc.RUNS).index(run_id)
    process = dict(
        boot_id="fabricated", pid=2000 + k, start_ticks=100 + k, parent_pid=1, fresh=True
    )
    doc = dict(kind=judge_bc.RECORD_KIND, protocol=judge_bc.PROTOCOL, job=job, process=process,
               **extra)  # fmt: skip
    if refused:
        doc.update(outcome="refused", refusal=dict(cls="ConfigError", message="planted refusal"))
    else:
        doc.update(
            outcome="completed",
            times=[float(t).hex() for t in _grid(run_id)],
            quantities={k: [float(x).hex() for x in v] for k, v in quantities.items()},
        )
        np.savez(records / f"{run_id}.npz", **arrays)
    (records / f"{run_id}.json").write_text(json.dumps(doc))


def _world_b(records, refs):
    """The references' B, the engine's at both steps and its twin, and plants (b)-(d), whose lys
    rows differ from the twin's (their physics), (d) washed at lys too."""
    tb = np.asarray(judge_bc.sample_times("B"))
    doc = reference("B")
    doc["B"] = [repr(float(x)) for x in _profile(tb, B_STAR, judge_bc.B4_FROM)]
    doc["once"]["B*"] = repr(B_STAR)
    (refs / "B.json").write_text(json.dumps(doc))
    total = 1e-4
    for run_id, (world, dt, _, _, event, plant) in judge_bc.RUNS.items():
        if world != "B":
            continue
        t = _grid(run_id)
        profile = _profile(t, B_STAR, judge_bc.B4_FROM)
        washed = (t > WASH_B).astype(np.int64) * int(event)
        arrays = dict(
            lys_rows=np.zeros((t.size, 4)),
            site_free_increment_fmol=np.zeros((t.size, 1)),
            site_bound_increment_fmol=np.zeros((t.size, 1)),
            wash_applied_well=washed,
            wash_applied_lys=np.zeros(t.size, dtype=np.int64),
        )
        bound = _engine(profile, t, dt)
        n_l = total - bound
        if plant == "b":  # Binds from elsewhere: lys keeps its total and B stays at the trace.
            n_l, bound = np.full(t.size, total), np.full(t.size, 1e-12)
        elif plant == "c":  # B short of B*.
            n_l, bound = total - 0.99 * profile, 0.99 * profile
        elif plant == "d":  # lys loses material at the wash.
            n_l, bound = total - profile - np.where(t > WASH_B, 2e-6, 0.0), profile
            arrays["wash_applied_lys"] = washed.copy()
        if plant:
            arrays["lys_rows"] = arrays["lys_rows"] + 1e-9
        q = dict(n_L=n_l, B=bound, R=9.96e-5 - bound)
        _record(records, run_id, quantities=q, arrays=arrays)


def _world_c1(records, refs):
    """The well's values just before and after the wash, the engine's at 900 s and 902 s."""
    doc = reference("C1")
    well = dict(x_W_before=6e-4, b_W_before=4e-4, x_W_after=3e-4, b_W_after=2.000005e-4)
    doc["well"].update({k: repr(v) for k, v in well.items()})
    (refs / "C1.json").write_text(json.dumps(doc))
    for run_id, x_after in (("C1-dt2", 3e-4), ("C1-twin-dt2", 3e-4), ("C1-plant-dt2", 3.000005e-4)):
        t = _grid(run_id)
        n = np.where(t > WASH_C1, x_after + 2.000005e-4, 1e-3)
        x = np.where(t > WASH_C1, x_after, 6e-4)
        q = dict(n_O=n, n_C=n, n_W=n, share_x_O=x / n, share_x_C=x / n, share_x_W=x / n,
                 share_base_W=1 - x / n)  # fmt: skip
        rows = dict(O_rows=np.ones((t.size, 8)), C_rows=np.ones((t.size, 8)),
                    O_shares=np.zeros((t.size, 1, 2)), C_shares=np.zeros((t.size, 1, 2)),
                    label_closure_relative=np.full((t.size, 1), 1.4e-16))  # fmt: skip
        rows.update({name: np.zeros((t.size, 1)) for name in judge_bc.c1_physical_names()})
        _record(records, run_id, quantities=q, arrays=rows, label_closure_relative_max=1.4e-16)


def _world_c2(records, refs):
    """Two ligands' B against their references, each conserved; the plant misses B1*."""
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
    for run_id, miss in (("C2-dt0.1", 1.0), ("C2-dt0.05", 1.0), ("C2-plant-dt0.1", 0.999)):
        t, dt = _grid(run_id), judge_bc.RUNS[run_id][1]
        b1 = _engine(_profile(t, B1_STAR, judge_bc.C2_3_FROM), t, dt) * miss
        b2 = _engine(_profile(t, B2_STAR, judge_bc.C2_3_FROM), t, dt)
        q = dict(n_L1=6e-5 - b1, B1=b1, n_L2=6e-5 - b2, B2=b2, R=9.96e-5 - b1 - b2)
        _record(records, run_id, quantities=q, arrays=dict(lys_rows=np.zeros((t.size, 4))))


@pytest.fixture(scope="module")
def fabricated(tmp_path_factory):
    """The twelve runs' honest records on their dt grids, and the three references, written once."""
    root = tmp_path_factory.mktemp("fabricated")
    records, refs = root / "records", root / "refs"
    records.mkdir()
    refs.mkdir()
    for world in (_world_b, _world_c1, _world_c2):
        world(records, refs)
    return records, refs


def _copy(fabricated, tmp_path):
    records, refs = tmp_path / "records", tmp_path / "refs"
    shutil.copytree(fabricated[0], records)
    shutil.copytree(fabricated[1], refs)
    return records, refs


def _rewrite(records, run_id, change):
    """One record rewritten through change(doc, arrays)."""
    path = records / f"{run_id}.json"
    doc = json.loads(path.read_text())
    arrays = dict(np.load(records / f"{run_id}.npz"))
    change(doc, arrays)
    path.write_text(json.dumps(doc))
    np.savez(records / f"{run_id}.npz", **arrays)


def test_the_judge_end_to_end_passes_honest_records_and_catches_every_plant(fabricated):
    """The criteria's code on numbers given here, under the driver's record names: honest runs pass
    every criterion of the three parts, and each plant fails its registered criterion. B5 is
    reported for (b) and (c), whose lys rows differ from the twin's, and scored for (d) only."""
    verdict = judge_bc.judge(*fabricated)
    assert verdict["verdict"] == "passed", json.dumps(verdict, default=str)[:2000]
    plants = {
        w: {k: p["fails"] for k, p in v["plants"].items()} for w, v in verdict["parts"].items()
    }
    assert plants == {"B": {"a": ["B4"], "b": ["B2", "B4"], "c": ["B4"], "d": ["B2", "B5"]},
                      "C1": {"c1": ["C1-2"]}, "C2": {"c2": ["C2-3"]}}  # fmt: skip
    b = verdict["parts"]["B"]
    assert [(b["plants"][k]["B5"]["passed"], b["plants"][k]["B5"]["scored"]) for k in "bcd"] == [
        (False, False),
        (False, False),
        (False, True),
    ]
    once, none = dict(well=1, lys=0), dict(well=0, lys=0)
    assert b["criteria"]["B5"]["washes"] == {
        "B-dt0.1": once,
        "B-dt0.05": once,
        "B-twin-dt0.1": none,
    }
    assert b["criteria"]["B3"]["ratio"] == pytest.approx(8.0)
    json.dumps(verdict, default=float)  # The verdict file's write.


def test_a_refused_plant_run_is_not_the_registrations_catch(fabricated, tmp_path):
    records, refs = _copy(fabricated, tmp_path)
    _record(records, "B-plant-c-dt0.1", refused=True)
    verdict = judge_bc.judge(records, refs)
    assert verdict["parts"]["B"]["verdict"] == "failed"
    assert verdict["parts"]["B"]["plants"]["c"]["refused"]["message"] == "planted refusal"
    assert verdict["parts"]["C1"]["verdict"] == verdict["parts"]["C2"]["verdict"] == "passed"


def _sample_grid(doc, arrays, every):
    doc["times"] = doc["times"][::every]
    doc["quantities"] = {k: v[::every] for k, v in doc["quantities"].items()}
    arrays.update({k: v[::every] for k, v in arrays.items()})


RECORD_REFUSED = {
    "rows on the sample grid": (
        "B-dt0.1",
        lambda d, a: _sample_grid(d, a, 50),
        "121 rows, not the dt grid's 6001",
    ),
    "a row off the grid": (
        "B-dt0.05",
        lambda d, a: d["times"].__setitem__(7, float(np.nextafter(7 * 0.05, 1.0)).hex()),
        "row 7 is at",
    ),
    "a quantity short of a row": (
        "C2-dt0.1",
        lambda d, a: d["quantities"]["B2"].pop(),
        "quantity B2 has 20000 entries for 20001 rows",
    ),
    "an array short of a row": (
        "C1-dt2",
        lambda d, a: a.update(O_rows=a["O_rows"][:-1]),
        "array O_rows has",
    ),
    "another job": (
        "C2-dt0.05",
        lambda d, a: d["job"].update(dt=0.025),
        "not the registered run C2-dt0.05",
    ),
    "a missing record file": ("C2-dt0.1", "missing", "record of the registered run C2-dt0.1 is"),
    "no process field": ("B-dt0.1", lambda d, a: d.pop("process"), "no fresh process"),
    "a refused record with no process field": (
        "B-plant-c-dt0.1",
        lambda d, a: (d.update(outcome="refused", refusal={}), d.pop("process")),
        "no fresh process",
    ),
}


def test_two_runs_sharing_one_process_are_refused(fabricated, tmp_path):
    """READING-2: the judge refuses a set of records in which two runs share one process, before
    any part reads a value."""
    records, refs = _copy(fabricated, tmp_path)
    shared = json.loads((records / "C1-dt2.json").read_text())["process"]
    _rewrite(records, "C1-twin-dt2", lambda d, a: d.update(process=shared))
    with pytest.raises(judge_bc.ReaderError, match="C1-twin-dt2 and C1-dt2 share one process"):
        judge_bc.judge(records, refs)


@pytest.mark.parametrize("name", sorted(RECORD_REFUSED))
def test_a_record_off_its_registered_rows_is_refused(fabricated, tmp_path, name):
    """Reading 3, enforced (READING-2): a record's rows are exactly its run's dt grid, every
    quantity and array one entry per row, and its job the registered row."""
    run_id, change, words = RECORD_REFUSED[name]
    if change != "missing":
        for suffix in (".json", ".npz"):
            shutil.copy(fabricated[0] / f"{run_id}{suffix}", tmp_path / f"{run_id}{suffix}")
        _rewrite(tmp_path, run_id, change)
    with pytest.raises(judge_bc.ReaderError, match=words):
        judge_bc.read_record(tmp_path, run_id)


B5_UNCOUNTED = {
    "the well's event never applied": (
        "B-dt0.05",
        lambda d, a: a.update(wash_applied_well=0 * a["wash_applied_well"]),
    ),
    "an event applied in the twin": (
        "B-twin-dt0.1",
        lambda d, a: a.update(wash_applied_well=(_grid("B-twin-dt0.1") > WASH_B).astype(np.int64)),
    ),
    "an event applied at lys": (
        "B-dt0.1",
        lambda d, a: a.update(wash_applied_lys=a["wash_applied_well"].copy()),
    ),
    "the event applied twice": (
        "B-dt0.1",
        lambda d, a: a.update(wash_applied_well=2 * a["wash_applied_well"]),
    ),
}


@pytest.mark.parametrize("name", sorted(B5_UNCOUNTED))
def test_b5_is_gated_on_the_washs_counts(fabricated, tmp_path, name):
    """B5 fails, its arrays bit for bit the twin's, unless the well's event applied exactly once in
    each honest run, none in the twin, and none at lys (READING-2)."""
    run_id, change = B5_UNCOUNTED[name]
    records, refs = _copy(fabricated, tmp_path)
    _rewrite(records, run_id, change)
    criteria, _ = judge_bc.judge_b(records, judge_bc.read_reference(refs / "B.json", "B"))
    assert criteria["B5"]["passed"] is False and criteria["B5"]["differing"] == []


@pytest.mark.parametrize("case", ["a node's electrode charge differs", "an array is missing"])
def test_c1_1_compares_every_physical_state_field_at_o_and_c(fabricated, tmp_path, case):
    """READING-3: C1-1's physical rows are every physical state field at O and C, here C's
    electrode charge, compared bit for bit; a record without one of them is refused."""
    records, refs = _copy(fabricated, tmp_path)
    name, names = "C.electrode_charge_transferred_C", judge_bc.c1_physical_names()
    assert {name, "O.amount_increment", "O.poly_complexes_fmol", "P.membrane_transferred",
            "P.passive_transferred"} <= set(names)  # fmt: skip

    def change(doc, arrays):
        if case == "an array is missing":
            arrays.pop(name)
        else:
            arrays[name] = arrays[name].copy()
            arrays[name][700, 0] = 1e-30

    _rewrite(records, "C1-twin-dt2", change)
    reference = judge_bc.read_reference(refs / "C1.json", "C1")
    if case == "an array is missing":
        with pytest.raises(judge_bc.ReaderError, match="C1-1's arrays missing"):
            judge_bc.judge_c1(records, reference)
    else:
        criteria, _ = judge_bc.judge_c1(records, reference)
        assert criteria["C1-1"]["passed"] is False and criteria["C1-1"]["differing"] == [name]


@pytest.mark.parametrize("value, passed", [(64 * EPS, True), (65 * EPS, False), (np.nan, False)])
def test_c1_3_bounds_the_label_owners_closure_on_every_row(fabricated, tmp_path, value, passed):
    """C1-3: the closure diagnostic at most 64 ε on every row of C1 and its twin (reading 5, the
    bound of the label owner's own run tests), here one row of the twin's set to `value`."""
    records, refs = _copy(fabricated, tmp_path)

    def one_row(doc, arrays):
        arrays["label_closure_relative"] = arrays["label_closure_relative"].copy()
        arrays["label_closure_relative"][700, 0] = value

    _rewrite(records, "C1-twin-dt2", one_row)
    criteria, _ = judge_bc.judge_c1(records, judge_bc.read_reference(refs / "C1.json", "C1"))
    assert criteria["C1-3"]["passed"] is passed


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
        (("dev-B", "B", 0.1, 900.0, 5.0, True, None), False, "not strictly short"),
        (("dev-B", "B", 0.1, float("nan"), 5.0, True, None), False, "not strictly short"),
        (("dev-C1", "C1", 2.0, 60.0, 60.0, True, "b"), False, "is World B's, not world C1's"),
        (("C1-dt1", "C1", 1.0, 3600.0, 60.0, True, None), True, "not a registered run"),
        (("dev-B", "B", 0.1, 60.0, 5.0, True, "e"), False, "not a registered plant"),
        (("dev-D", "D", 0.1, 60.0, 5.0, True, None), False, "not a registered world"),
    ],
    ids=[
        "registered, not judged",
        "registered, judged",
        "dev at full length",
        "dev at full length, judged",
        "dev, shortened",
        "dev beyond full length",
        "dev at a NaN horizon",
        "plant b on C1",
        "a registered ID's world at another step",
        "an unknown plant",
        "a dev job naming an unknown world",
    ],
)
def test_the_first_run_rule(row, judged, refused):
    """The driver's first-run rule (the lead, 28 November 2026): a registered world first runs at
    its registered length only in a judged run, so a dev- job at or beyond that horizon is
    refused."""
    found = driver_bc.first_run_refusal(driver_bc.job(row), judged)
    assert (found is None) if refused is None else (refused in found)


@pytest.mark.parametrize(
    "case, refused",
    [
        ("fresh", None),
        ("not started by run", "the one `run` starts"),
        ("another job's mark", "the one `run` starts"),
        ("a job run before", "ran B-dt0.1 already"),
        ("the engine loaded", "loaded cells.execution.runner"),
        ("jax loaded", "loaded jax"),
    ],
)
def test_a_run_gets_a_fresh_process_of_its_own(tmp_path, case, refused):
    """READING-2: `run` starts a fresh process for each job, and that process refuses unless it is
    one: started by `run` for its job and driver, no job run before, no JAX or engine module."""
    job = tmp_path / "dev-B.json"
    environ, modules, ran = {driver_bc.CHILD: driver_bc.mark(job)}, ["numpy", "json"], []
    if case == "not started by run":
        environ = {}
    elif case == "another job's mark":
        environ = {driver_bc.CHILD: driver_bc.mark(tmp_path / "dev-C1.json")}
    elif case == "a job run before":
        ran = ["B-dt0.1"]
    elif case == "the engine loaded":
        modules = [*modules, "cells.execution.runner"]
    elif case == "jax loaded":
        modules = [*modules, "jax"]
    found = driver_bc.fresh_process_refusal(job, environ=environ, modules=modules, ran=ran)
    assert (found is None) if refused is None else (refused in found)


def test_c1s_plant_is_the_engines_exchange_but_for_its_one_line(monkeypatch):
    """READING-2: C1's plant is a copy of label_shares.exchange; any change of the engine's beyond
    the planted line stops the plant before it patches."""
    import jax.numpy as jnp

    from cells.numerics import label_shares
    from cells.numerics.species_sums import entity_sum
    from validation.fr49 import plants_bc

    assert plants_bc.c1_drift() == []

    def exchange(shares, n0, removed, supplied, present, *, xp=jnp):
        declared = present if present.ndim == 3 else present[:, :, None]
        base = (xp.arange(shares.shape[1]) == 0)[None, :, None]
        kept = (n0 - removed)[:, None, :] * shares
        x = xp.where(declared, kept + xp.where(base, supplied[:, None, :], 0.0), 0.0)
        total = entity_sum(x, axis=1, xp=xp)
        moved = ((removed > 0) | (supplied >= 0)) & (total > 0)  # Another line changed.
        out = x / xp.where(moved, total, 1.0)[:, None, :]
        return xp.where(moved[:, None, :], out, shares)

    monkeypatch.setattr(label_shares, "exchange", exchange)
    with pytest.raises(RuntimeError, match="supplied >= 0"):
        with plants_bc.plant_c1():
            pass
    assert label_shares.exchange is exchange


@pytest.mark.parametrize(
    "case",
    ["this tree", "neither git nor a snapshot", "another engine tree", "an enclosing repository"],
)
def test_the_identity_names_a_revision_and_the_drivers_own_engine(tmp_path, case):
    """The driver's identity: a revision from git or SNAPSHOT.json, never none, and the engine
    loaded from the driver's own tree, or the run is refused."""
    if case == "this tree":
        found = driver_bc.identity()
        assert found["revision"] and found["engine_tree"] == str(driver_bc.Path(
            driver_bc.__file__).resolve().parents[2])  # fmt: skip
        return
    here, engine = tmp_path, tmp_path / "elsewhere"
    words = "not the driver's tree"
    if case == "neither git nor a snapshot":
        engine, words = tmp_path, "gives a revision"
    elif case == "an enclosing repository":
        import subprocess

        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        here = engine = tmp_path / "tree"
        here.mkdir()
        words = "an enclosing repository"
    with pytest.raises(SystemExit, match=words):
        driver_bc.identity(here=here, engine=engine)


@pytest.mark.parametrize(
    "axes, shape, words",
    [
        (("species", "membrane_slot"), (2, 8, 3), None),
        (("species", "electrode_slot"), (2, 8, 3), "does not class"),
        (("species",), (2, 8), "does not class"),
        (("channel_slot",), (2, 1), "holds a slot"),
    ],
)
def test_c1_1s_entity_rule_classes_every_axis_or_refuses(axes, shape, words):
    """READING-3: worlds_bc's entity rule cuts each entity axis to O's, C's or what lies between
    them, keeps sub-axes whole, and refuses an axis it does not class, or an empty one with a
    slot."""
    from validation.fr49 import worlds_bc as wb

    slots = wb.c1_entity_slots(wb.world_c1())
    values = np.zeros(shape)
    if words is None:
        cls, part = wb.c1_part(axes, values, slots)
        assert cls == "P" and part.shape == (2, 8, len(slots["membrane_slot"])) == (2, 8, 2)
    else:
        with pytest.raises(ValueError, match=words):
            wb.c1_part(axes, values, slots)
