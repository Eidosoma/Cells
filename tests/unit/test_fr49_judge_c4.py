"""FR-49's C4 judge and driver, host only (validation/fr49/judge_c4.py, driver_c4.py; amendments 2
and 3).

- The judge's run table (RUNS) is the driver's (JOBS), field for field.
- The judge end to end on records fabricated here on the 0.5 s grid, with each run's definition as
  the driver builds it: honest records pass C4-1 to C4-8, and each plant fails its registered
  criteria, C4-1 scored for (d) only and C4-7 for (e) only; a refused plant run is not the catch.
- The reader refuses a record off its registered layout: off the dt grid, its observations off
  theirs, an array missing or extra, other entity slots, no process, a missing file, another job, a
  definition not its hash, or one that fails amendment 2's gates (that run is not judged); and a set
  in which two runs share one process.
- C4-1's wash gate, C4-3's closure bound, C4-4's extra fields (LABELS_ONLY's and no more), and
  C4-7's minus (binding's own fields only).
- Plant (e) at its own 1800 s (amendment 3): its record on its own rows, its definition's end time
  its registered change, C4-1 and C4-7 on the twins' rows to its horizon only (the times bit for
  bit, the observations cut at its horizon), and C4-8 at L's 31 times with the scale over L's 61.
- The driver's first-run rule (amendment 2, A2.7; A3.7 for plant (e)) and its fresh-process rule;
  the reader check on invented samples made here.
Seconds and reason (D224): about 11 s on one core (41 rows; amendment 3's eight added about 4 s), no
compile; the judge is the registered instrument of C4.
"""

import copy
import hashlib
import json
import shutil
from decimal import Decimal

import numpy as np
import pytest

from validation.fr49 import driver_c4, judge_bc, judge_c4, judge_l

CASES = json.loads(judge_bc.SPEC.read_text())
ROWS = 7201
T = np.arange(ROWS, dtype=float) * 0.5
B_STAR = 9.7e-5  # Invented: the judge's own arithmetic is tested.
WELL = dict(x_W_before=6e-4, b_W_before=4e-4, x_W_after=3e-4, b_W_after=2.000005e-4)
EPS = float(np.finfo(float).eps)


def test_the_judges_run_table_is_the_drivers_jobs():
    assert {row[0]: tuple(row[1:]) for row in driver_c4.JOBS} == judge_c4.RUNS
    assert driver_c4.FIELDS[1:] == judge_c4.JOB_FIELDS


# -------------------------------------------------- references and records, fabricated


def _bc_reference(world):
    """A references file in judge_bc's layout, with the registered spec's declared values."""
    v = CASES["worlds"][world]
    times = judge_bc.sample_times(world)
    doc = dict(kind=judge_bc.KIND, protocol=judge_bc.PROTOCOL, world=world,
               inputs=dict(invented=False), sample_times_s=[f"{t:g}" for t in times],
               method=dict(second_route=dict(declared_accuracy="1e-20", within=True)))  # fmt: skip
    declared = {k: copy.deepcopy(v[k]) for k in judge_bc.DECLARED[world]}
    if world == "B":
        declared.update(sample_times_rule=v["sample_times_s"]["rule"], sites_per_fmol="602214076")
        declared["wash_elsewhere"] = {
            k: v["wash_elsewhere"][k] for k in ("node", "time_s", "fraction")
        }
        doc["once"] = dict.fromkeys(judge_bc.ONCE["B"], "1e-4")
        doc["once"]["B*"] = repr(B_STAR)
    else:
        declared["wash"] = copy.deepcopy(v["wash"])
        doc["well"] = dict.fromkeys(judge_bc.WELL_KEYS, "1e-4") | {
            k: repr(x) for k, x in WELL.items()
        }
        doc["method"]["well_second_route"] = dict(declared_accuracy="1e-20", within=True)
    doc["declared"] = declared
    for q in judge_bc.QUANTITIES[world]:
        doc[q] = ["1e-4"] * len(times)
    return doc


def _profiles():
    """S's honest values (the same at every labelled run), and their L.json at the sample times."""
    n_o = 1e-3 * (1 + 0.1 * np.sin(T / 300.0))
    n_c = 2e-4 * (1 + 0.05 * np.cos(T / 200.0))
    share_o, share_c = np.where(T >= 600.0, 0.3, 0.0), np.where(T >= 600.0, 0.2, 0.0)
    return n_o, n_c, share_o, share_c


def _l_reference():
    v = CASES["worlds"]["L"]
    n_o, n_c, share_o, share_c = _profiles()
    index = [int(t / 0.5) for t in judge_c4.L_TIMES]
    doc = dict(
        kind=judge_l.KIND,
        protocol=judge_l.PROTOCOL,
        world="L",
        inputs=dict(invented=False),
        sample_times_s=[f"{t:g}" for t in judge_c4.L_TIMES],
        method=dict(eigen_closed_form=dict(declared_accuracy="1e-13", within=True)),
    )
    doc["declared"] = {k: copy.deepcopy(v[k]) for k in judge_l.DECLARED}
    doc["declared"]["sample_times_rule"] = v["sample_times_s"]["rule"]
    values = dict(n_O=n_o, n_C=n_c, x_O=n_o * share_o, x_C=n_c * share_c)
    for q in judge_l.QUANTITIES:
        doc[q] = [repr(float(x)) for x in values[q][index]]
    return doc


def _quantities(run_id):
    _, _, _, _, event, labelled, bound, plant = judge_c4.RUNS[run_id]
    v = CASES["worlds"]["B"]
    total = float(Decimal(v["initial_fmol"]["n_L"]) + Decimal(v["initial_fmol"]["B"]))
    profile = np.where(T >= 550.0, B_STAR, B_STAR * (1 - np.exp(-T / 20.0)))
    b = np.zeros(ROWS) if not bound else (0.99 * profile if plant == "c" else profile)
    n_g = total - b
    if plant == "d":  # The wash at C takes G away.
        n_g = n_g - np.where(T > 900.0, 2e-6, 0.0)
    if plant == "e":  # The sites bind S, not G.
        n_g = np.full(ROWS, total)
    n_o, n_c, share_o, share_c = _profiles()
    if plant == "e":
        n_c = n_c * np.where(T >= 60.0, 1.5, 1.0)
    x_after = 3.000005e-4 if plant == "c1" else WELL["x_W_after"]
    n_w = np.where(T > 900.0, x_after + WELL["b_W_after"], 1e-3)
    x_w = np.where(T > 900.0, x_after, WELL["x_W_before"])
    q = dict(n_O=n_o, n_C=n_c, n_W=n_w, n_G=n_g, B=b, R=9.96e-5 - b)
    if labelled:
        q.update(share_x_O=share_o, share_x_C=share_c, share_x_W=x_w / n_w,
                 share_base_W=1 - x_w / n_w)  # fmt: skip
    return q


def _arrays(run_id):
    _, _, _, _, event, labelled, bound, plant = judge_c4.RUNS[run_id]
    w = judge_c4.world()
    out = {name: np.zeros((ROWS, 1)) for name in judge_c4.c4_physical_names()}
    rows = np.zeros((ROWS, w["species"]))
    if plant == "d":
        rows[T > 900.0, w["s"]] = 1e-9
    if plant == "e":
        rows[:, w["s"]] = 1e-9
    out["C.extracellular_amount_increment"] = rows
    out["wash_applied_W"] = ((T > 900.0) & event).astype(np.int64)
    out["wash_applied_C"] = ((T > 900.0) & (plant == "d")).astype(np.int64)
    if labelled:
        out.update(
            label_share=np.zeros((ROWS, 1, 2, 1)),
            label_outside_share=np.zeros((ROWS, 1, 2, 3)),
            label_closure_relative=np.full((ROWS, 1), 1.4e-16),
        )
    if driver_c4.full(dict(event=event, bound=bound, plant=plant)):
        out.update({"H.amount_increment": np.zeros((ROWS, w["species"], 1)),
                    "H.site_bound_increment_fmol": np.zeros((ROWS, 1)),
                    "OBS.times": np.arange(61, dtype=float) * 60.0,
                    "OBS.amount_increment": np.zeros((61, w["species"], 1))})  # fmt: skip
        if labelled:
            labels = ("label_share", "label_outside_share", "label_closure_relative")
            out.update({f"H.{f}": np.zeros((ROWS, 1)) for f in labels})
    return out


def _rows(run_id):
    """A run's saved rows: its dt grid to its registered horizon (plant (e)'s 1800 s: 3,601)."""
    return int(round(judge_c4.RUNS[run_id][2] / 0.5)) + 1


def _on_rows(arrays, n):
    """The fabricated arrays on a run's first n rows, its observations to that row's time."""
    keep = arrays["OBS.times"] <= T[n - 1] if "OBS.times" in arrays else None
    return {k: (v[keep] if k.startswith("OBS.") else v[:n]) for k, v in arrays.items()}


def _write(records, run_id, *, refused=False, quantities=None, arrays=None, process=None):
    job = driver_c4.job((run_id, *judge_c4.RUNS[run_id]))
    definition = records / f"{run_id}.definition.json"
    definition.write_text(json.dumps(driver_c4.raw_world(job), indent=1) + "\n")
    k = list(judge_c4.RUNS).index(run_id)
    doc = dict(kind=judge_c4.RECORD_KIND, protocol=judge_c4.PROTOCOL, job=job,
               process=process or dict(boot_id="fabricated", pid=3000 + k, start_ticks=10 + k,
                                       parent_pid=1, fresh=True),
               c4_entity_slots=judge_c4.world()["slots"],
               definition_sha256=hashlib.sha256(definition.read_bytes()).hexdigest())  # fmt: skip
    if refused:
        doc.update(outcome="refused", refusal=dict(cls="ConfigError", message="planted refusal"))
    else:
        n = _rows(run_id)
        q = _quantities(run_id) if quantities is None else quantities
        hexed = {k: [float(x).hex() for x in v[:n]] for k, v in q.items()}
        doc.update(outcome="completed", times=[float(t).hex() for t in T[:n]], quantities=hexed)
        if driver_c4.full(job):
            doc["diagnostics"] = {"max_balance_error_fmol": 1e-18}
        a = _arrays(run_id) if arrays is None else arrays
        np.savez(records / f"{run_id}.npz", **_on_rows(a, n))
    (records / f"{run_id}.json").write_text(json.dumps(doc))


@pytest.fixture(scope="module")
def fabricated(tmp_path_factory):
    """The eight runs' honest records and the three references, written once."""
    root = tmp_path_factory.mktemp("c4")
    records, refs = root / "records", root / "refs"
    records.mkdir()
    refs.mkdir()
    (refs / "L.json").write_text(json.dumps(_l_reference()))
    for world in ("B", "C1"):
        (refs / f"{world}.json").write_text(json.dumps(_bc_reference(world)))
    for run_id in judge_c4.RUNS:
        _write(records, run_id)
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
    arrays = (
        dict(np.load(records / f"{run_id}.npz")) if (records / f"{run_id}.npz").exists() else {}
    )
    change(doc, arrays)
    path.write_text(json.dumps(doc))
    if arrays:
        np.savez(records / f"{run_id}.npz", **arrays)


# -------------------------------------------------- the judge end to end


def test_the_judge_end_to_end_passes_honest_records_and_catches_every_plant(fabricated):
    """Honest records pass C4-1 to C4-8; each plant fails its registered criteria, C4-1 scored for
    (d) only and C4-7 for (e) only, and every criterion each plant fails is reported."""
    verdict = judge_c4.judge(*fabricated)
    part = verdict["parts"]["C4"]
    assert verdict["verdict"] == "passed", json.dumps(part, default=str)[:3000]
    assert all(c["passed"] for c in part["criteria"].values())
    scored = {name: p.get("scored", p["fails"]) for name, p in part["plants"].items()}
    assert scored == {"a": ["C4-6"], "c": ["C4-6"], "d": ["C4-1", "C4-5"], "c1": ["C4-2"],
                      "e": ["C4-7", "C4-8"]}, scored  # fmt: skip
    assert "C4-5" in part["plants"]["e"]["fails"]  # Reported, not scored.
    assert part["criteria"]["C4-4"]["extra_fields"] == [
        "label_closure_relative",
        "label_outside_share",
        "label_share",
    ]
    json.dumps(verdict, default=float)


def test_a_refused_plant_run_is_not_the_registrations_catch(fabricated, tmp_path):
    records, refs = _copy(fabricated, tmp_path)
    (records / "C4-plant-e-dt0.5.npz").unlink()
    _write(records, "C4-plant-e-dt0.5", refused=True)
    part = judge_c4.judge(records, refs)["parts"]["C4"]
    assert (
        part["verdict"] == "failed"
        and part["plants"]["e"]["refused"]["message"] == "planted refusal"
    )


def _grid_off(doc, arrays):
    doc["times"] = doc["times"][::2]
    doc["quantities"] = {k: v[::2] for k, v in doc["quantities"].items()}
    arrays.update({k: v[::2] for k, v in arrays.items() if not k.startswith("OBS.")})


def _definition_changed(records):
    def change(doc, arrays):
        path = records / "C4-dt0.5.definition.json"
        raw = json.loads(path.read_text())
        block = next(
            b for b in raw["model"]["operators"] if b["law"] == "cells.operator.site_occupancy@1"
        )
        block["populations"][0]["dissociation_rate_per_s"] *= 2.0
        path.write_text(json.dumps(raw))
        doc["definition_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    return change


def _plant_e_at_world_ls_horizon(records):
    def change(doc, arrays):
        path = records / "C4-plant-e-dt0.5.definition.json"
        raw = json.loads(path.read_text())
        raw["experiment"]["end_time"] = 3600.0
        path.write_text(json.dumps(raw))
        doc["definition_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    return change


RECORD_REFUSED = {
    "rows off the dt grid": ("C4-twin-dt0.5", lambda r: _grid_off, "rows, not the dt grid's 7201"),
    "observations off their grid": (
        "C4-dt0.5",
        lambda r: lambda d, a: a.update({"OBS.times": a["OBS.times"] + 1.0}),
        "observations are not on the 60 s grid",
    ),
    "a C4-1 array missing": (
        "C4-unbound-dt0.5",
        lambda r: lambda d, a: a.pop("C.wash_applied"),
        "not exactly C4-1's set: extra [], missing ['C.wash_applied']",
    ),
    "an extra P array": (
        "C4-dt0.5",
        lambda r: lambda d, a: a.update({"P.an_uncompared_field": np.zeros((ROWS, 1))}),
        "extra ['P.an_uncompared_field']",
    ),
    "other entity slots": (
        "C4-twin-dt0.5",
        lambda r: (
            lambda d, a: d.update(c4_entity_slots=dict(d["c4_entity_slots"], membrane_slot=[1]))
        ),
        "other entity slots",
    ),
    "no process field": ("C4-dt0.5", lambda r: lambda d, a: d.pop("process"), "no fresh process"),
    "another job": (
        "C4-plant-c-dt0.5",
        lambda r: lambda d, a: d["job"].update(dt=0.25),
        "not the registered run C4-plant-c-dt0.5",
    ),
    "a definition not its hash": (
        "C4-dt0.5",
        lambda r: lambda d, a: d.update(definition_sha256="0" * 64),
        "its hash is not its record's",
    ),
    "a definition that fails the values gate": (
        "C4-dt0.5",
        _definition_changed,
        "C4-dt0.5 is not judged: its definition fails amendment 2's gates: k_off = B.k_off: "
        "DIFFERS",
    ),
    "plant (e)'s definition at world L's horizon, not its own": (
        "C4-plant-e-dt0.5",
        _plant_e_at_world_ls_horizon,
        "C4-plant-e-dt0.5 is not judged: its definition fails amendment 2's gates: end time = "
        "L.horizon_s: DIFFERS",
    ),
}


@pytest.mark.parametrize("name", sorted(RECORD_REFUSED))
def test_a_record_off_its_registered_layout_is_refused(fabricated, tmp_path, name):
    run_id, change, words = RECORD_REFUSED[name]
    for suffix in (".json", ".npz", ".definition.json"):
        shutil.copy(fabricated[0] / f"{run_id}{suffix}", tmp_path / f"{run_id}{suffix}")
    _rewrite(tmp_path, run_id, change(tmp_path))
    with pytest.raises(judge_bc.ReaderError, match=__import__("re").escape(words)):
        judge_c4.read_record(tmp_path, run_id)


def test_a_missing_record_and_two_runs_sharing_one_process_are_refused(fabricated, tmp_path):
    with pytest.raises(
        judge_bc.ReaderError, match="record of the registered run C4-dt0.5 is missing"
    ):
        judge_c4.read_record(tmp_path, "C4-dt0.5")
    records, refs = _copy(fabricated, tmp_path)
    shared = json.loads((records / "C4-dt0.5.json").read_text())["process"]
    _rewrite(records, "C4-unbound-dt0.5", lambda d, a: d.update(process=shared))
    with pytest.raises(
        judge_bc.ReaderError, match="C4-unbound-dt0.5 and C4-dt0.5 share one process"
    ):
        judge_c4.judge(records, refs)


# -------------------------------------------------- the criteria's own rules


def _criteria(records, refs):
    return judge_c4.judge_c4(records, judge_c4.read_references(refs))["criteria"]


@pytest.mark.parametrize(
    "case",
    [
        "C4-1: the well's event applied twice",
        "C4-1: an event applied at C in the unlabelled twin",
        "C4-3: one row's closure at 65 eps",
        "C4-4: an extra field beyond the labels'",
        "C4-7: a field beside binding's own differs",
        "C4-7: binding's own field differs (allowed)",
    ],
)
def test_each_criterions_own_rule(fabricated, tmp_path, case):
    records, refs = _copy(fabricated, tmp_path)
    if case == "C4-1: the well's event applied twice":
        _rewrite(records, "C4-dt0.5", lambda d, a: a.update(wash_applied_W=2 * a["wash_applied_W"]))
        criterion, passes = "C4-1", False
    elif case == "C4-1: an event applied at C in the unlabelled twin":
        _rewrite(records, "C4-unlabelled-dt0.5",
                 lambda d, a: a.update(wash_applied_C=a["wash_applied_W"].copy()))  # fmt: skip
        criterion, passes = "C4-1", False
    elif case == "C4-3: one row's closure at 65 eps":

        def change(d, a):
            a["label_closure_relative"] = a["label_closure_relative"].copy()
            a["label_closure_relative"][700, 0] = 65 * EPS

        _rewrite(records, "C4-unbound-dt0.5", change)
        criterion, passes = "C4-3", False
    elif case == "C4-4: an extra field beyond the labels'":
        _rewrite(
            records, "C4-dt0.5", lambda d, a: a.update({"H.another_field": np.zeros((ROWS, 1))})
        )
        criterion, passes = "C4-4", False
    elif case == "C4-7: a field beside binding's own differs":

        def change(d, a):
            a["O.turnover_work_pJ"] = a["O.turnover_work_pJ"] + 1e-30

        _rewrite(records, "C4-unbound-dt0.5", change)
        criterion, passes = "C4-7", False
    else:

        def change(d, a):
            a["P.site_bound_increment_fmol"] = a["P.site_bound_increment_fmol"] + 1e-9

        _rewrite(records, "C4-unbound-dt0.5", change)
        criterion, passes = "C4-7", True
    assert _criteria(records, refs)[criterion]["passed"] is passes


# -------------------------------------------------- plant (e)'s own horizon (amendment 3)

E, UNBOUND, TWIN = "C4-plant-e-dt0.5", "C4-unbound-dt0.5", "C4-twin-dt0.5"


@pytest.mark.parametrize("case", [
    "the twins' rows past (e)'s horizon are not compared with (e)",
    "C4-8 reads (e) at L's 31 times, its scale over L's 61",
    "a twin's times off (e)'s rows are refused",
    "a twin's rows and observations are cut at (e)'s horizon",
])  # fmt: skip
def test_plant_e_is_judged_on_its_own_rows(fabricated, tmp_path, case):
    rows = _rows(E)  # 3,601: 0 to 1800 s.
    if case == "the twins' rows past (e)'s horizon are not compared with (e)":
        records, refs = _copy(fabricated, tmp_path)

        def change(d, a):  # One field differs past 1800 s, another at 1800 s, (e)'s last row.
            a["O.turnover_work_pJ"] = a["O.turnover_work_pJ"].copy()
            a["O.turnover_work_pJ"][rows:] += 1e-30
            a["C.wash_applied"] = a["C.wash_applied"].copy()
            a["C.wash_applied"][rows - 1] += 1e-30

        _rewrite(records, UNBOUND, change)
        _rewrite(records, TWIN, change)
        result = judge_c4.judge_c4(records, judge_c4.read_references(refs))
        report = result["plants"]["e"]["report"]
        assert "O.turnover_work_pJ" in result["criteria"]["C4-7"]["differing"]  # At full length.
        for differing in (report["C4-7"], report["C4-1"]["differing"]):
            assert "O.turnover_work_pJ" not in differing and "C.wash_applied" in differing
    elif case == "C4-8 reads (e) at L's 31 times, its scale over L's 61":
        records, refs = _copy(fabricated, tmp_path)
        doc = json.loads((refs / "L.json").read_text())
        ref = np.array([float(x) for x in doc["n_C"]])
        ref[31:] *= 10.0  # Past 1800 s the reference is larger, so the two scales differ.
        doc["n_C"] = [repr(float(x)) for x in ref]
        (refs / "L.json").write_text(json.dumps(doc))
        result = judge_c4.judge_c4(records, judge_c4.read_references(refs))
        eight = result["plants"]["e"]["report"]["C4-8"]
        engine = _quantities(E)["n_C"][[int(t / 0.5) for t in judge_c4.L_TIMES[:31]]]
        error = np.max(np.abs(engine - ref[:31]))
        assert eight["samples"] == 31 and eight["e"]["n_C"] == float(error / np.max(np.abs(ref)))
        assert eight["e"]["n_C"] < float(error / np.max(np.abs(ref[:31])))
        assert result["criteria"]["C4-8"]["samples"] == 61
    else:
        arrays = {
            "C.x": np.arange(ROWS, dtype=float)[:, None],
            "OBS.times": np.arange(61, dtype=float) * 60.0,
            "OBS.x": np.arange(61.0),
        }
        runs = {E: (None, None, T[:rows], {}), UNBOUND: (None, None, T.copy(), arrays)}
        if case == "a twin's times off (e)'s rows are refused":
            off = np.arange(31, dtype=float) * 60.0
            off[5] = np.nextafter(off[5], np.inf)
            runs[E] = (None, None, T[:rows], {"OBS.times": off})
            with pytest.raises(judge_bc.ReaderError, match="observation instants to C4-plant-e"):
                judge_c4.on_rows(runs, E, UNBOUND)
            runs[UNBOUND][2][10] = np.nextafter(T[10], np.inf)
            with pytest.raises(judge_bc.ReaderError, match="times on C4-plant-e-dt0.5's rows"):
                judge_c4.on_rows(runs, E, UNBOUND)
        else:
            cut = judge_c4.on_rows(runs, E, UNBOUND)
            assert np.array_equal(cut["C.x"], arrays["C.x"][:rows])
            assert np.array_equal(cut["OBS.times"], np.arange(31) * 60.0)
            assert np.array_equal(cut["OBS.x"], np.arange(31.0))


# -------------------------------------------------- the driver's rules (A2.7)


@pytest.mark.parametrize(
    "row, judged, refused",
    [
        (
            ("C4-dt0.5", "C4", 0.5, 3600.0, 60.0, True, True, True, None),
            False,
            "only with --judged",
        ),
        (("C4-dt0.5", "C4", 0.5, 3600.0, 60.0, True, True, True, None), True, None),
        (("C4-dt1", "C4", 1.0, 3600.0, 60.0, True, True, True, None), True, "not a registered run"),
        (("dev-C4", "C4", 0.5, 3600.0, 60.0, True, True, True, None), False, "not strictly short"),
        (("dev-C4", "C4", 0.5, 7200.0, 60.0, True, True, True, None), True, "not strictly short"),
        (("dev-C4", "C4", 0.5, float("nan"), 60.0, True, True, True, None), False, "not strictly"),
        (
            ("dev-C4", "C4", 0.5, 1260.0, 60.0, True, True, True, "b"),
            False,
            "not a registered plant",
        ),
        (("dev-C4", "B", 0.5, 1260.0, 60.0, True, True, True, None), False, "is not C4's"),
        (("dev-C4", "C4", 0.5, 1260.0, 60.0, True, True, True, "e"), False, None),
        (("C4-plant-e-dt0.5", "C4", 0.5, 1800.0, 60.0, True, True, True, "e"), True, None),
        (
            ("C4-plant-e-dt0.5", "C4", 0.5, 3600.0, 60.0, True, True, True, "e"),
            True,
            "not a registered run",
        ),
        (
            ("dev-C4", "C4", 0.5, 1800.0, 60.0, True, True, True, "e"),
            False,
            "not strictly short of its registered run's (1800 s",
        ),
    ],
    ids=[
        "registered, not judged",
        "registered, judged",
        "a registered ID's world at another step",
        "dev at full length",
        "dev beyond it, judged",
        "dev at a NaN horizon",
        "an unknown plant",
        "a dev job of another world",
        "dev, shortened",
        "plant (e) at its own horizon, judged",
        "plant (e) at world L's horizon",
        "a dev job of plant (e) at its own horizon (A3.7)",
    ],  # fmt: skip
)
def test_the_first_run_rule_binds_every_run(row, judged, refused):
    found = driver_c4.first_run_refusal(driver_c4.job(row), judged)
    assert (found is None) if refused is None else (refused in found), found


@pytest.mark.parametrize("case, refused", [
    ("fresh", None),
    ("not started by run", "the one `run` starts"),
    ("a job run before", "ran C4-dt0.5 already"),
    ("the engine loaded", "loaded cells.execution.runner"),
])  # fmt: skip
def test_a_run_gets_a_fresh_process_of_its_own(tmp_path, case, refused):
    job = tmp_path / "dev-C4.json"
    environ, modules, ran = {driver_c4.CHILD: driver_c4.mark(job)}, ["numpy", "json"], []
    if case == "not started by run":
        environ = {driver_c4.CHILD: driver_c4.mark(tmp_path / "other.json")}
    elif case == "a job run before":
        ran = ["C4-dt0.5"]
    elif case == "the engine loaded":
        modules = [*modules, "cells.execution.runner"]
    found = driver_c4.fresh_process_refusal(job, environ=environ, modules=modules, ran=ran)
    assert (found is None) if refused is None else (refused in found)


def test_the_reader_check_reads_invented_samples_and_refuses_them_as_the_references(tmp_path):
    """D308: the tagged readers on invented samples made here, by structure: each parses as a sample
    and is refused when read as the references."""
    for name, doc in (
        ("L", _l_reference()),
        ("B", _bc_reference("B")),
        ("C1", _bc_reference("C1")),
    ):
        doc["inputs"]["invented"] = True
        (tmp_path / f"INVENTED_{name}.json").write_text(json.dumps(doc))
    report = judge_c4.check_reader(tmp_path, judge_bc.SPEC)
    assert all(
        report[w]["parsed"] and report[w]["refused_as_the_references"] for w in ("L", "B", "C1")
    )
