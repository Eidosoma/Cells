"""E07-v1's schedules, donor rules and paired-null reading (registered protocol E07-v1-B).

validation/tissue/e07_v1_turnover.py builds every arm's schedule and the copy-only null;
validation/tissue/e07_v1_run.py reads an engine run against that null. These tests use
labels only: no engine step runs.
"""

import math

import numpy as np
import pytest

from validation.tissue import e07_v1_run as run
from validation.tissue import e07_v1_turnover as e7

FAST = dict(residence_s=1020.0, end_s=2340.0)


def sheet_plan(seed, size=37, rule="neighbour", **kw):
    return e7.plan(scope="sheet", rule=rule, size=size, seed=seed, **(FAST | kw))


def test_sheet_schedule_replaces_every_cell_once_per_turnover():
    p = sheet_plan(101)
    steps = [k for k, _, _ in p["events"]]
    assert steps == sorted(steps) and len(set(steps)) == len(steps)
    assert steps[0] == round(0.5 * 1020.0 / 127 / e7.DT)
    assert all(k * e7.DT < 2340.0 - e7.DT for k in steps)
    n = 127
    slots = [slot for _, slot, _ in p["events"]]
    assert slots == [p["permutation"][j % n] for j in range(len(slots))]
    for block in range(len(slots) // n):  # Oldest first: each cell once per turnover.
        assert sorted(slots[block * n : (block + 1) * n]) == list(range(n))
    assert p["turnover_complete_s"] == pytest.approx([126.5 * 1020 / 127, 253.5 * 1020 / 127])


def test_schedule_is_seeded_and_shared_across_discs():
    a, b = sheet_plan(101), sheet_plan(101, size=19)
    assert a["events"] == b["events"]  # Replicate r: one schedule on every disc and s.
    assert sheet_plan(101) == a
    assert sheet_plan(102)["permutation"] != a["permutation"]


def test_event_grid_keeps_the_default_schedule():
    assert sheet_plan(101, grid_dt=e7.DT) == sheet_plan(101)
    fine = sheet_plan(101, dt=0.001, grid_dt=0.005)
    coarse = sheet_plan(101)
    assert [k for k, *_ in fine["events"]] == [5 * k for k, *_ in coarse["events"]]
    assert [e[1:] for e in fine["events"]] == [e[1:] for e in coarse["events"]]


def test_donor_rules():
    _, _, neighbours = e7.sheet()
    counts = np.zeros(6)
    for seed in range(101, 121):
        for _, slot, donor in sheet_plan(seed)["events"]:
            assert donor in neighbours[slot]
            if len(neighbours[slot]) == 6:
                counts[neighbours[slot].index(donor)] += 1
    # Blind to state: uniform over a slot's six neighbours (chi-square, 5 dof, p 0.001).
    expected = counts.sum() / 6
    assert counts.sum() > 3000 and ((counts - expected) ** 2 / expected).sum() < 20.5
    inside = e7.disc(37)
    control = e7.plan(scope="disc", rule="disc_neighbour", size=37, seed=101, **FAST)
    assert len(control["events"]) == 85
    for _, slot, donor in control["events"]:
        assert slot in inside and donor in inside and donor in neighbours[slot]
    assert all(d is None for _, _, d in sheet_plan(101, rule="isolated")["events"])


def test_arm_set_is_the_registered_one():
    arms = {a["id"]: a for a in e7.arm_set()}
    assert sum(len(a["seeds"]) for a in arms.values()) == 38
    assert arms["a-donor-fast-k1-d37-s1.0"]["seeds"] == list(range(1, 9))
    assert arms["a-donor-central-k1-d37-s0.6"]["end_s"] == e7.CONTROL_END_S
    assert arms["a-donor-fast-k3-d37-s1.0"]["judged_at"] == "first turnover"
    assert all(a["end_s"] <= e7.CONTROL_END_S for a in arms.values())


def test_null_reads_donors_before_events_at_one_step():
    centre, outside = 63, 0  # The disc's centre (D) and a sheet corner (H).
    events = [(400, centre, outside), (400, outside, centre)]
    series = e7.null_series(events, 37, 20.0)
    assert series["d_inside"].tolist() == [37, 36, 36]
    assert series["d_outside"].tolist() == [0, 1, 1]
    assert series["J"][-1] == pytest.approx(36 / 38)


# ------------------------------------------------------------------ the paired reading


def record(scope="sheet", rule="neighbour", end_s=600.0, judged="second turnover"):
    p = e7.plan(scope=scope, rule=rule, size=37, residence_s=300.0, end_s=end_s, seed=101)
    return dict(
        size=37, dt=e7.DT, kind="donor" if rule != "isolated" else "iso", rule=rule,
        planned_end_s=end_s, judged_at=judged, turnover_complete_s=p["turnover_complete_s"],
        formation=e7.BRACKETS["fast"],
        events=[(k, slot, donor, f"n{j}") for j, (k, slot, donor) in enumerate(p["events"])],
    )  # fmt: skip


def synthetic(rec, flips=(), stop_after=None):
    """Records of a run whose labels follow copying, except that each (cell, time) in flips
    turns that cell H then. Records every 10 s and at each event (before the event)."""
    _, _, neighbours = e7.sheet()
    inside = np.zeros(127, dtype=bool)
    inside[sorted(e7.disc(rec["size"]))] = True
    label = inside.copy()
    events = sorted(rec["events"], key=lambda e: e[0])
    regular = set(np.round(np.arange(0.0, rec["planned_end_s"] + 1e-9, 10.0), 9).tolist())
    times = sorted(regular | {round(k * rec["dt"], 9) for k, *_ in events})
    if stop_after is not None:
        times = [x for x in times if x <= stop_after + 1e-9]
    t_all, d_all, k = [], [], 0
    pending = sorted(flips, key=lambda f: f[1])
    for t in times:
        while k < len(events) and events[k][0] * rec["dt"] < t - 1e-9:
            step = events[k][0]
            batch = []
            while k < len(events) and events[k][0] == step:
                batch.append(events[k])
                k += 1
            new = [(slot, False if d is None else bool(label[d])) for _, slot, d, _ in batch]
            for slot, value in new:
                label[slot] = value
        while pending and pending[0][1] <= t + 1e-9:
            label[pending.pop(0)[0]] = False
        t_all.append(t)
        d_all.append(label.copy())
    t_all, d_all = np.array(t_all), np.array(d_all)
    is_regular = np.array([x in regular for x in t_all])
    osm = np.full(d_all.shape, sum(run.e7_h_state()))
    return t_all, d_all, osm, is_regular


def test_copying_engine_reads_as_neutral():
    rec = record()
    t_all, d_all, osm, regular = synthetic(rec)
    out = run.reading(rec, dict(stop="planned end"), t_all, d_all, osm, regular)
    assert out["basis"] == "record" and out["delta_J"] == 0.0
    assert out["D_copies_lost"] == 0 and out["H_copies_converted"] == 0
    assert out["founders_lost"] == 0 and out["run_class"] == "neutral"
    assert out["J_series"]["engine"] == out["J_series"]["null"]
    assert out["d_outside_max"] == out["d_outside_max_null"]  # Copying spreads D: no failure.


def test_a_lost_D_copy_is_counted_and_lowers_J():
    rec = record()
    t_all, d_all, osm, regular = synthetic(rec)
    # The first D copy inside the disc (donor D at its event record) falls to H 5 s later.
    inside = e7.disc(37)
    index = {round(float(x), 9): i for i, x in enumerate(t_all)}
    k, slot = next(
        (k, slot)
        for k, slot, d, _ in rec["events"]
        if d is not None and slot in inside and d_all[index[round(k * e7.DT, 9)], d]
    )
    flip = k * e7.DT + 5.0
    t_all, d_all, osm, regular = synthetic(rec, flips=[(slot, flip)])
    out = run.reading(rec, dict(stop="planned end"), t_all, d_all, osm, regular)
    assert out["D_copies_lost"] == 1
    assert out["D_loss_fraction"] == pytest.approx(1 / out["D_copies"])
    series = out["J_series"]
    after = next(i for i, x in enumerate(series["t_s"]) if x > flip)
    assert series["engine"][after] < series["null"][after]  # One D cell fewer in the disc.


def test_censored_run_is_judged_at_its_last_valid_record():
    rec = record()
    t_all, d_all, osm, regular = synthetic(rec, stop_after=400.0)
    osm[t_all >= 400.0 - 1e-9, 63] *= 1.2  # Above the censor from 400 s on.
    out = run.reading(rec, dict(stop="censor"), t_all, d_all, osm, regular)
    assert out["basis"].startswith("censored") and out["judged_s"] == 390.0
    assert out["delta_J"] == 0.0


def test_an_all_H_run_is_absorbed_at_its_judged_time():
    rec = record(end_s=600.0)
    t_all, d_all, osm, regular = synthetic(rec, stop_after=200.0)
    d_all[t_all >= 150.0 - 1e-9] = False  # The engine loses every D cell at 150 s.
    out = run.reading(rec, dict(stop="all_h"), t_all, d_all, osm, regular)
    assert out["basis"].startswith("absorbed") and out["J_engine"] == 0.0
    assert out["delta_J"] == pytest.approx(-out["J_null"]) and out["run_class"] == "erosion"


def test_run_classes_and_the_group_rule():
    delta = 2 / 37
    assert run.run_class(0.0, 0.0, 0.0, delta) == "neutral"
    assert run.run_class(-0.1, 0.0, 0.0, delta) == "erosion"
    assert run.run_class(0.0, 0.06, 0.0, delta) == "erosion"
    assert run.run_class(0.1, 0.0, 0.0, delta) == "recruitment"
    assert run.run_class(0.1, 0.06, 0.0, delta) == "mixed"
    assert run.run_class(0.0, 0.03, 0.0, delta) == "small bias"
    assert run.run_class(0.0, None, None, delta) == "neutral"
    assert run.group_class(["erosion"] * 6 + ["neutral"] * 2) == "erosion"
    assert run.group_class(["erosion"] * 5 + ["neutral"] * 3) == "split"
    assert run.group_class(["neutral", "neutral"]) == "neutral"
    assert run.group_class(["neutral", "erosion"]) == "split"
    assert run.group_class(["erosion"] * 2 + ["neutral"]) == "erosion"
    assert math.ceil(2 * 4 / 3) == 3  # Four runs need three.


def test_e1_segments_keep_their_step_in_the_file_name(tmp_path):
    fine = run.e1_paths(tmp_path, "b-tau40-d37-s1.0", 101, 0.001)
    coarse = run.e1_paths(tmp_path, "b-tau40-d37-s1.0", 101, 0.005)
    assert fine[0] != coarse[0] and fine[1] != coarse[1]
    assert fine[0].name == "b-tau40-d37-s1.0-seed101-dt0.001.npz"


def test_deviation_over_records_is_reported_beside_the_judged_record():
    rec = record()
    t_all, d_all, osm, regular = synthetic(rec)
    out = run.reading(rec, dict(stop="planned end"), t_all, d_all, osm, regular)
    over = out["delta_J_over_records"]
    assert over["status"] == run.SUPPLEMENTARY and over["status"].startswith("supplementary")
    assert over["mean"] == 0.0 and over["min"] == 0.0 and over["nonzero_records"] == 0
    assert over["records"] == int(
        np.sum((t_all[regular] > 0) & (t_all[regular] <= out["judged_s"]))
    )
