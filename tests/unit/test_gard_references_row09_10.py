"""GARD references, rows 9 and 10: streams and observers.

Planted controls: a reused key (and a reseeding restart), and H = 0.9 counted as
inherited (and off-by-one F12 detectors).
"""

from __future__ import annotations

import numpy as np
import pytest

from validation.gard.references import observers as ob
from validation.gard.references import streams as st
from validation.gard.references.harness import probe_input_arrays
from validation.gard.references.kernels import PAIR_CONSISTENT
from validation.gard.references.lineage_oracle import simulate_lineage
from validation.gard.references.standin import preprint_law


@pytest.fixture(scope="module")
def world():
    return preprint_law(21, PAIR_CONSISTENT)


def _run(world, **kw):
    law, founder = world
    kw.setdefault("n_fissions", 6)
    kw.setdefault("seed", 51)
    return simulate_lineage(law, founder, **kw)


def test_replay_is_bitwise_and_a_changed_seed_is_not(world):
    _, r1, a1 = _run(world)
    _, r2, a2 = _run(world)
    assert st.check_bitwise_replay(a1, a2, r1, r2).passed
    _, r3, a3 = _run(world, seed=52)
    assert not st.check_bitwise_replay(a1, a3, r1, r3).passed


def test_restart_matches_and_a_reseeding_restart_is_caught(world):
    _, run, a = _run(world)
    row, fis = 5, 2
    ev = int(a["row_event"][row])
    good = st.check_restart(a, a, row, ev, fis)
    assert good.passed
    tail = {k: v for k, v in a.items()}
    for name in st.ROW_AXIS_ARRAYS:
        tail[name] = a[name][row:]
    for name in st.EVENT_AXIS_ARRAYS:
        tail[name] = a[name][ev:]
    for name in st.FISSION_AXIS_ARRAYS:
        if name in a:
            tail[name] = a[name][fis:]
    assert st.check_restart(a, tail, row, ev, fis).passed
    # planted: the restart draws a fresh stream after the checkpoint
    _, _, other = _run(world, seed=999)
    spliced = dict(tail)
    spliced["event_channel"] = other["event_channel"][: tail["event_channel"].size]
    assert not st.check_restart(a, spliced, row, ev, fis).passed


def test_branches_are_independent_and_a_reused_key_is_caught(world):
    law, founder = world
    branches, ids = [], []
    for k in range(3):
        _, run, a = simulate_lineage(law, founder, n_fissions=2, seed=51, branch=200 + k)
        branches.append(a)
        ids.append(run["stream"])
    assert st.check_branch_independence(branches, ids).passed
    # planted: branch 2 reuses branch 0's key while declaring its own identity
    _, run_r, a_r = simulate_lineage(law, founder, n_fissions=2, seed=51, branch=200)
    reused = st.check_branch_independence(branches[:2] + [a_r], ids[:2] + [dict(run_r["stream"], branch=202)])
    assert not reused.passed and reused.detail["repeated_pairs"]


def test_f12_reference_predicates_agree_on_all_4096_sequences():
    res = ob.check_f12_table(ob.f12_reference_table())
    assert res.passed and res.detail["reference_positives"] == ob.F12_POSITIVES == 2065
    msb = ob.check_f12_table(ob.f12_reference_table("msb_first"), "msb_first")
    assert msb.passed


def test_f12_definition_on_hand_cases():
    T, F = True, False
    assert ob.f12_scan([F, T, T, T] + [T] * 8)
    assert not ob.f12_scan([T, T, T, F] + [F] * 8)  # a run before the break does not count
    assert not ob.f12_scan([F, T, T, F, T, T, F, T, T, F, T, T])  # never three in a row
    assert not ob.f12_scan([T] * 9 + [F, T, T])  # renewal unfinished within twelve
    assert ob.f12_scan([F, T, T, T])  # certified before a later extinction stays positive
    assert ob.f12_scan([F] * 9 + [T, T, T])  # the third success is the twelfth boundary
    assert not ob.f12_scan([F] * 10 + [T, T, T])  # the third success lies beyond the window


@pytest.mark.parametrize("bad", ["run_of_two", "break_may_follow", "window_13"])
def test_off_by_one_f12_detectors_are_caught(bad):
    def detector(marks):
        s = "".join("1" if m else "0" for m in marks)
        if bad == "run_of_two":
            return "0" in s and any("11" in s[i + 1:] for i, c in enumerate(s) if c == "0")
        if bad == "break_may_follow":
            return "0" in s and "111" in s
        return ob.f12_scan(list(marks) + [True], horizon=13)
    table = np.array([detector(ob.sequence(k)) for k in range(4096)])
    assert not ob.check_f12_table(table).passed


def test_h_threshold_probes_catch_h_equal_point_nine_as_inherited():
    probes = probe_input_arrays()["observer_probe_inputs"]
    P, Dd = probes["probe_parent"], probes["probe_daughter"]
    H = np.array([ob.similarity(p, d) for p, d in zip(P, Dd)])
    exact = np.array([ob.inherited_exact(p, d) for p, d in zip(P, Dd)])
    assert ob.check_observer_probes(P, Dd, H, exact).passed
    ge = H >= 0.9 - 1e-12  # planted: H = 0.9 counted as inherited
    bad = ob.check_observer_probes(P, Dd, H, ge)
    assert not bad.passed and bad.detail["mismatches_at_exact_point_nine"] > 0
    # a plain float comparison is also caught: rounding pushes some exact-0.9 pairs above 0.9
    float_gt = ob.check_observer_probes(P, Dd, H, H > 0.9)
    assert not float_gt.passed and float_gt.detail["mismatches_at_exact_point_nine"] > 0


def test_exact_point_nine_by_hand():
    P = np.array([45, 15, 15, 5])
    D = np.array([40, 0, 0, 0])
    assert ob.similarity(P, D) == 0.9 and not ob.inherited_exact(P, D)
    assert ob.inherited_exact(np.array([45, 15, 15, 4]), D)
    assert not ob.inherited_exact(np.array([45, 15, 15, 6]), D)


def test_fission_similarity_records_and_a_perturbed_h(world):
    _, _, a = _run(world)
    count = a["assembly_count"][:, :, 0]
    F = a["fission_split"].shape[0]
    parents, daughters = count[1:1 + 2 * F:2], count[2:2 + 2 * F:2]
    res = ob.check_fission_similarity(parents, a["fission_split"], a["fission_followed"], daughters,
                                      a["fission_similarity"])
    assert res.passed, res.detail
    sim = a["fission_similarity"].copy()
    sim[3, 0] += 1e-12
    assert not ob.check_fission_similarity(parents, a["fission_split"], a["fission_followed"], daughters, sim).passed
