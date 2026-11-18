"""OL5's OL2/OL3 run references: the shared pool's two-level map, the clock rule, shear fission,
birth lysis, serial transfer and their bookings, the partition probe, and the harness end to end
on the stand-in (code-blind; no engine)."""

from __future__ import annotations

import math

import pytest

from validation.ool.references import harness2 as H2
from validation.ool.references import ol3_checks as O3
from validation.ool.references import population as P
from validation.ool.references import registered2 as R2
from validation.ool.references import standin2 as S2
from validation.ool.references.ol2 import Law2, Vesicle2

RUNS = R2.runs()
_TRACES = {}


def honest(run: str) -> dict:
    if run not in _TRACES:
        spec = RUNS[run]
        _TRACES[run] = P.simulate(spec, P.HostStreams(spec.seed))
    return _TRACES[run]


def test_two_level_map_with_its_guard_and_empty_groups():
    groups = [[0.0, 0.0], [1.0, 2.0], [], [3.0]]
    assert P.two_level(groups, 0.0, 0.0)[:2] == (1, 0)
    assert P.two_level(groups, 0.4, 0.5)[:2] == (1, 1)             # 0.4 * 6 = 2.4 < 3: slot group 1; 0.5 * 3 > 1
    assert P.two_level(groups, 0.6, 0.9)[:2] == (3, 0)             # the empty group is never chosen
    assert P.two_level(groups, math.nextafter(1.0, 0.0), math.nextafter(1.0, 0.0))[:2] == (3, 0)
    assert P.flat(groups, 0.4)[:2] == (1, 1)


@pytest.mark.parametrize("run", sorted(RUNS))
def test_honest_runs_replay_close_and_keep_their_counters(run):
    tr = honest(run)
    spec = RUNS[run]
    assert tr["end_reason"] == H2.END_REASON[run]
    assert P.replay(spec, tr)["passed"]
    assert P.closure_check(spec, tr)["passed"]
    assert P.stream_check(tr)["passed"]
    assert P.environment_check(tr)["passed"]
    cov = H2._coverage(tr)
    assert all(cov[k] >= v for k, v in H2.COVERAGE.get(run, {}).items()), cov


def test_the_clock_rule_discards_each_crossing_draw():
    tr = honest("ol3_lineage_run")
    times = RUNS["ol3_lineage_run"].schedules[0].times
    discarded = [i for i, d in enumerate(tr["draws"]) if d["fate"] == "discarded"]
    assert len(discarded) == len(times)
    shears = [e["t"] for e in tr["events"] if e["kind"] == "shear"]
    assert shears == list(times)
    for i in discarded:                                           # the next draw takes the next counter
        d, nxt = tr["draws"][i], tr["draws"][i + 1]
        assert nxt["counter"] == d["counter"] + 1 or nxt["key"] != d["key"]
    assert not any(d["fate"] == "discarded" for d in honest("ol2_shared_run")["draws"])     # no schedule


def test_poisson_gaps_and_the_transfer_sample():
    spec = RUNS["ol3_population_run"]
    tr = honest("ol3_population_run")
    lam = spec.schedules[0].rate
    gaps = [d for d in tr["schedule_draws"] if d["schedule"] == 0]
    t, expect = 0.0, []
    for d in gaps:
        t += -math.log(d["u"]) / lam
        expect.append(t)
    shears = [e["t"] for e in tr["events"] if e["kind"] == "shear"]
    assert shears == [x for x in expect if x <= spec.t_end]
    for e in (e for e in tr["events"] if e["kind"] == "transfer"):
        order = sorted(e["draws"], key=lambda d: (d["u"], d["slot"]))
        assert e["kept"] == sorted(d["slot"] for d in order[: spec.schedules[1].K_keep])
    first = next(e for e in tr["events"] if e["kind"] == "transfer")
    assert not first["removed"] and len(first["draws"]) == 4      # it draws although every assembly is kept


def test_bookings_shear_work_birth_lysis_and_transfer():
    spec = RUNS["ol3_shear_probe_run"]
    law = Law2(spec.world)
    tr = honest("ol3_shear_probe_run")
    births = 0
    before = {j: s for j, s in enumerate(tr["initial"]["slots"])}
    for e in (e for e in tr["events"] if e["kind"] == "shear"):
        for a in e["attempts"]:
            parent = Vesicle2(tuple(before[a["slot"]]["n"]), tuple(before[a["slot"]]["l"]))
            if a["outcome"] != "split":
                continue
            ds = [Vesicle2(tuple(d["n"]), tuple(d["l"])) for d in a["daughters"]]
            w_shear = sum(law.F_vesicle(d) for d in ds) - law.F_vesicle(parent)
            assert math.isclose(a["shear_work"], w_shear, rel_tol=1e-12)
            assert sum(map(sum, (d.n for d in ds))) == sum(parent.n)                  # conserved
            births += sum(d["lysed_at_birth"] for d in a["daughters"])
        before = {j: s for j, s in enumerate(e["slots_after"]) if s is not None}
    assert births >= 1
    spec = RUNS["ol3_population_run"]
    law = Law2(spec.world)
    tr = honest("ol3_population_run")
    pool, slots = tuple(tr["initial"]["pool"]), list(tr["initial"]["slots"])
    for e in tr["events"]:
        if e["kind"] == "transfer":
            removed = sum(law.F_vesicle(Vesicle2(tuple(slots[j]["n"]), tuple(slots[j]["l"]))) for j in e["removed"])
            assert math.isclose(e["sink"], removed + law.F_pool(pool), rel_tol=1e-12, abs_tol=1e-9)
            assert math.isclose(e["schedule_work"], law.F_pool(tuple(spec.schedules[1].fresh_pool)), rel_tol=1e-12)
        if e["kind"] == "step":
            pool = tuple(e["pool"])
            slots[e["group"]] = e["after"] if e["group"] >= 0 else None
        else:
            pool, slots = tuple(e["pool"]), list(e["slots_after"])


CAUGHT_BY = {"flat_select": "ol2_shared_run", "counter_not_advanced": "ol3_lineage_run",
             "no_discard": "ol3_lineage_run", "transfer_largest": "ol3_population_run",
             "transfer_skip_when_all_kept": "ol3_population_run", "gap_one_minus": "ol3_population_run",
             "admission_one_over_k": "ol3_slots_full_run", "floor_on_parent": "ol3_shear_probe_run",
             "birth_lysis_kept": "ol3_shear_probe_run", "slots_highest": "ol3_shear_probe_run",
             "transfer_fresh_to_sink": "ol3_population_run", "old_pool_not_sunk": "ol3_population_run"}
CAUGHT_BY_LAW = {"closure_added_again": "ol3_shear_probe_run", "closure_not_released": "ol2_lysis_run",
                 "release_work_omitted": "ol2_lysis_run", "no_lumen_term": "ol2_lysis_run"}


@pytest.mark.parametrize("form", sorted(CAUGHT_BY) + sorted(CAUGHT_BY_LAW))
def test_each_planted_behaviour_fails_its_row(form):
    run = CAUGHT_BY.get(form) or CAUGHT_BY_LAW[form]
    spec = RUNS[run]
    tr = P.simulate(spec, P.HostStreams(spec.seed), form if form in CAUGHT_BY else None,
                    form if form in CAUGHT_BY_LAW else None)
    verdicts = (P.replay(spec, tr)["passed"], P.closure_check(spec, tr)["passed"], P.stream_check(tr)["passed"])
    assert not all(verdicts), form
    if form in ("old_pool_not_sunk", "closure_added_again", "closure_not_released"):
        assert not verdicts[1]                                    # the ledger does not close
    if form in ("transfer_fresh_to_sink", "release_work_omitted"):
        assert verdicts[1] and not verdicts[0]                    # closure holds; the term-wise replay does not


def test_partition_probe_replays_and_meets_its_laws():
    att = {p["id"]: O3.standin_attempts(p, R2.PARTITION_ATTEMPTS, 7, 100 + i) for i, p in enumerate(R2.OL3_PARENTS)}
    assert O3.check(R2.OL3_PARENTS, att, R2.PARTITION_ATTEMPTS)["passed"]
    short = {k: v[: R2.PARTITION_ATTEMPTS - 1] for k, v in att.items()}
    assert not O3.check(R2.OL3_PARENTS, short, R2.PARTITION_ATTEMPTS)["passed"]        # below the registered M


@pytest.mark.parametrize("form", ["g1_sizes", "no_pi", "largest_c", "lumen_by_area", "lumen_equal", "ties_last"])
def test_partition_planted_forms(form):
    alpha = 1e-3 / (2 * len(R2.OL3_PARENTS))
    caught = False
    for i, p in enumerate(R2.OL3_PARENTS):
        att = O3.standin_attempts(p, 400, 7, 100 + i, form)
        r = (O3.replay(p, att)["passed"], O3.membrane_law(p, att, alpha)["passed"], O3.lumen_weights_test(p, att, alpha)["passed"])
        caught = caught or not all(r)
    assert caught == (form != "ties_last"), form                  # ties_last: zero power (ties have probability 0)


def test_harness_end_to_end_on_the_stand_in(tmp_path):
    root = S2.build(tmp_path / "honest")
    status, verdict = H2.run_rows(root)
    assert status == 0, {r: v.get("problem") or [c["check"] for c in v["checks"] if not c["passed"]]
                         for r, v in verdict.items() if not v["passed"]}
    S2.write_run(root, "ol3_shear_probe_run", planted="birth_lysis_kept")
    status, verdict = H2.run_rows(root, ["OL3-3"])
    assert status == 1 and verdict["OL3-3"]["passed"] is False
    S2.write_refusals(root, accept="refuse_floor_without_kept")
    status, _ = H2.run_rows(root, ["OL2-5"])
    assert status == 1
    (root / "kernel" / "ol2_wa" / "manifest.json").unlink()
    status, verdict = H2.run_rows(root, ["OL2-1"])
    assert status == 2 and "manifest" in verdict["OL2-1"]["problem"]
