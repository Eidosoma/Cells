"""E07-v1's scorer (validation/tissue/e07_v1_score.py): its record readers on synthetic
records. No engine step runs."""

import json

import numpy as np
import pytest

from validation.tissue import e07_v1_score as sc
from validation.tissue import e07_v1_turnover as e7
from validation.tissue.heredity_pilot import THRESHOLD_V

D, H = THRESHOLD_V + 0.01, THRESHOLD_V - 0.01


def write(folder, vm, events):
    n_rec = vm.shape[0]
    np.savez(folder / "records.npz", t=np.arange(n_rec) * 10.0, vm=vm,
             regular=np.ones(n_rec, dtype=bool), osm=np.ones_like(vm),
             abundance=np.ones((n_rec, 1)), gate=np.ones((n_rec, 1)))  # fmt: skip
    (folder / "plan.json").write_text(json.dumps(dict(dt=0.005, events=events)))
    sc.series.cache_clear()
    return folder


def test_all_h_is_the_first_of_two_consecutive_records_without_d(tmp_path):
    vm = np.full((6, 127), H)
    vm[[0, 2], 5] = D  # One all-H record at 10 s with D again at 20 s: not the stop.
    assert sc.all_h_time(write(tmp_path, vm, [])) == 30.0


def test_collective_fall_leaves_out_slots_replaced_in_the_interval(tmp_path):
    vm = np.full((3, 127), H)
    vm[0, :6] = D  # Six D cells at 0 s, all H at 10 s; slot 0 was replaced at 5 s.
    folder = write(tmp_path, vm, [[1000, 0, 1]])
    assert sc.largest_fall(folder, 20.0) == dict(cells=5, at_s=10.0)
    assert sc.largest_fall(folder, 5.0) == dict(cells=0, at_s=None)


def test_templates_read_interior_and_conversion_to_the_judged_record(tmp_path):
    _, _, neighbours = e7.sheet()
    inside = e7.disc(37)
    interior = next(c for c in sorted(inside) if all(x in inside for x in neighbours[c]))
    outside = next(c for c in range(127) if c not in inside)
    vm = np.full((4, 127), H)
    vm[2:, interior] = D  # The interior template is D from 20 s.
    events = [[1000, interior, None], [1000, outside, None], [7000, interior, None]]
    rows = sc.templates(write(tmp_path, vm, events), dict(judged_s=30.0, size=37))
    assert [(r["slot"], r["interior"], r["converted"]) for r in rows] == [
        (interior, True, True),
        (outside, False, False),
    ]  # The template at 35 s comes after the judged record.
    assert all(r["birth_s"] == pytest.approx(5.0) for r in rows)
