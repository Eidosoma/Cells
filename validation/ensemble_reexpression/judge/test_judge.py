"""The judge's own tests: the honest fabricated tables pass, each fault row does as CRITERIA section
5 says, and the order of the stages holds.

Seconds: about 30 in all on one core (the judge's plants are 10 of them). They read the captures and
compile nothing.
"""

from __future__ import annotations

import copy
import json
import math

import numpy as np
import pytest

from validation.ensemble_reexpression.judge import __main__ as cli
from validation.ensemble_reexpression.judge import (
    bands,
    fabricate,
    identities,
    plants,
    scoring,
    strictjson,
    structure,
)
from validation.ensemble_reexpression.judge import constants as c
from validation.ensemble_reexpression.judge.c0 import C0
from validation.ensemble_reexpression.judge.plants import Lazy, Query, refuse
from validation.ensemble_reexpression.judge.registration import (
    PART1,
    Registration,
    StringsNote,
    changes,
)
from validation.ensemble_reexpression.judge.table import (
    Echo,
    RunRows,
    TableSet,
    compare_block,
    hash_folder,
)

PASS, FAIL, OPEN, UNFORMED = c.PASS, c.FAIL, c.INCONCLUSIVE, c.NOT_FORMED
H = [f"jupiter_baseline h={h!r}" for h in (2.5e-05, 1.25e-05, 6.25e-06)]
J = [f"integrated h={h!r}" for h in (0.0001, 5e-05, 2.5e-05)]
B = [f"base s0 w2 h={h!r}" for h in (2.5e-05, 1.25e-05, 6.25e-06)]
RESTART, EP1, EP2, POOL, POOL_RESTART = (
    "jupiter_baseline h=2.5e-05 restart",
    "jupiter_baseline plant channel",
    "base plant swapped",
    "base s0 pool",
    "base s0 pool restart",
)
KEEP = {
    "jupiter": lambda run: run["consumer"] == "jupiter",
    "integrated": lambda run: run["consumer"] == "integrated",
    "base": lambda run: (
        run["consumer"] == "base" and run["seed_index"] == 0 and run["world_id"] in (None, 0, 2)
    ),
}


class Bench:
    """A small set of the registered runs, with its honest fabricated tables."""

    def __init__(self, only):
        self.reg = Registration(only=only)
        made = C0(self.reg)
        made.legacy_classes()
        self.captures, self.planted = made.captures, made.planted
        self.c0 = {
            "kind": c.C0_KIND,
            "status": "pass",
            "spec_sha256": self.reg.files,
            "legacy": made.legacy,
        }
        self.tables, self.note_data = fabricate.Fabricator(
            self.reg, self.captures, self.planted
        ).tables()
        self.note = StringsNote(self.note_data, "fabricated")

    def score(self, alter=lambda runs: None, consumer=None, missing=()):
        """The record of the altered tables, as a query."""
        consumer = consumer or self.reg.consumers[0]
        runs = Lazy(self.tables[consumer]["runs"])
        alter(runs)
        tables = dict(self.tables)
        tables[consumer] = dict(tables[consumer], runs=dict(runs), missing=list(missing))
        return Query(
            plants.judge(self.reg, self.note, tables, self.c0, self.captures, self.planted)
        )


@pytest.fixture(scope="module")
def benches():
    """The benches by name, each made when a test first asks for it."""
    held = {}

    def get(name):
        if name not in held:
            try:
                held[name] = Bench(KEEP[name])
            except OSError as error:
                pytest.skip(f"no captures here: {error}")
        return held[name]

    return get


# ----- honest tables -----


@pytest.mark.parametrize("name", ["jupiter", "integrated", "base"])
def test_honest_tables_pass(benches, name):
    q = benches(name).score()
    block = q.record["consumers"][name]
    assert block["verdict"] == PASS, [
        s["inconclusive"] + s["fails"] for s in block["sets"].values()
    ]
    assert {p["score"] for p in q.record["plants"]["plants"]} <= {"caught"}
    assert not q.record["ignored"] and not any(
        s["causes"] or s["flags"] for s in q.record["runs"].values()
    )
    assert {f["what"] for f in q.record["flags"]} <= {"restart to confirm"}
    assert q.record["retry_owed"]["runs"] == []
    for part in block["sets"].values():
        assert all(n["formed"] == n["expected"] for n in part["counts"].values())


def test_judge_plants_score_as_stated(benches):
    """JP1 to JP24 (JP14 at h2, Amendment 2), on a subset of the registered runs."""
    wanted = {"base s0 w0", "base s0 w1", "base s0 w2", "base s1 w0"}
    bench = Bench(
        lambda r: (
            r["consumer"] in ("jupiter", "integrated")
            or (
                r["consumer"] == "base"
                and (r["family"] in wanted or (r["family"] is None and r["seed_index"] in (0, 1)))
            )
        )
    )
    out = plants.run_plants(
        bench.reg, bench.note, bench.tables, bench.c0, bench.captures, bench.planted
    )
    assert len(out["plants"]) == 25
    assert [p["plant"] for p in out["plants"] if not p["scores_as_stated"]] == []


# ----- the fault rows of CRITERIA section 5 -----


def put(*path, value=None):
    """Set a leaf of a run's entry."""

    def alter(entry):
        for key in path[:-1]:
            entry = entry[key]
        entry[path[-1]] = value(entry[path[-1]]) if callable(value) else value

    return alter


def drop(*path):
    """Delete a leaf of a run's entry."""

    def alter(entry):
        for key in path[:-1]:
            entry = entry[key]
        del entry[path[-1]]

    return alter


ECHO = {
    "a number": put("inputs", "cells", "cell_0", "volume_pL", value=lambda v: v * (1 + 1e-11)),
    "a declared zero": put(
        "inputs", "membranes", "membrane_2", "passive", "permeability_m_per_s", "K", value=1e-300
    ),
    "an integer": put("inputs", "species", "Na", value=1 + 1e-13),
    "a string": put("inputs", "closure", "gauge_reference", value="elsewhere"),
    "a region's charge": put(
        "inputs", "outside", "outside", "initial_charge_C", value=lambda v: v + 1e-24
    ),
    "a pump where there is none": put(
        "inputs", "membranes", "membrane_0", "pump", value={"law": "nak_pump_positive"}
    ),
    "a schedule's time": put(
        "inputs",
        "controls",
        "junction",
        "junction_2",
        value=[[0.0, 1.0], [0.005, 0.5], [0.0101, 0.0], [0.015, 1.0]],
    ),
    "a schedule left out that is no default": drop("inputs", "controls", "junction", "junction_2"),
    "a schedule that is no default for a membrane": put(
        "inputs", "controls", "pump", value={"membrane_0": [[0.0, 1.0], [0.01, 0.0]]}
    ),
    "an entity left out": drop("inputs", "junctions", "junction_10"),
    "an extra junction": put("inputs", "junctions", "junction_12", value=None)
    and (
        lambda e: e["inputs"]["junctions"].update(
            junction_12=copy.deepcopy(e["inputs"]["junctions"]["junction_0"])
        )
    ),
    "an extra species": lambda e: e["inputs"]["species"].update(Ca=2),
    "an extra region": lambda e: e["inputs"]["outside"].update(
        far=copy.deepcopy(e["inputs"]["outside"]["outside"])
    ),
    "a channel where there is none": put("inputs", "channels", value={"channel_0": {}}),
    "a schedule of no entity": lambda e: e["inputs"]["controls"]["junction"].update(
        junction_99=[[0.0, 1.0]]
    ),
    "world": put("world", value="jupiter_baseline"),
    "seed_index": put("seed_index", value=0),
    "world_id": put("world_id", value=0),
    "step_s": put("step_s", value=lambda v: v * (1 + 1e-11)),
    "a missing label": drop("strings", "rk4"),
    "an extra label": lambda e: e["strings"].update(kv15_mh="fabricated.kv15_mh"),
    "another string": put("strings", "rk4", value="fabricated.imex"),
    "a missing declared string": put("declared_strings", value=lambda v: v[1:]),
    "no inputs": put("inputs", value=None),
}


@pytest.mark.parametrize("case", ECHO)
def test_a_departing_echo_is_refused_and_nothing_of_it_is_judged(benches, case):
    q = benches("integrated").score(lambda runs: ECHO[case](runs[J[2]]))
    assert q.run(J[2])["refused"] and q.cause(J[2], "departing echo"), case
    assert q.nothing_judged(J[2], "integrated") and not q.fails()
    assert q.verdict("integrated") == OPEN


NO_FAULT = {
    "a number within 1e-12": put(
        "inputs", "cells", "cell_0", "volume_pL", value=lambda v: v * (1 + 5e-13)
    ),
    "an integer as a double": put("inputs", "species", "Na", value=1.0),
    "an empty map for an empty list": put("inputs", "faces", value={}),
    "no faces, no channels": lambda e: [e["inputs"].pop(k) for k in ("faces", "channels")],
    "controls that are empty left out": lambda e: [
        e["inputs"]["controls"].pop(k) for k in ("pump", "channel")
    ],
    "a default schedule left out": drop("inputs", "controls", "leak", "membrane_4"),
    "a default schedule written out": put(
        "inputs", "controls", "pump", value={"membrane_0": [[0.0, 1.0]]}
    ),
    "the initial entry left out": put(
        "inputs", "controls", "junction", "junction_2", value=lambda v: v[1:]
    ),
    "a pump left out that is null": drop("inputs", "membranes", "membrane_0", "pump"),
    "an extra key in an entity": put("inputs", "cells", "cell_0", "label", value="x"),
    "an extra key in the block": put("inputs", "note", value=1),
    "an extra key in the entry": put("extra", value=1),
    "an extra series": lambda e: e["rows"].update(leak_K={"membrane_0": [0.0] * 201}),
    "a negative zero": lambda e: e["rows"]["n_out_K"].update(outside=[-0.0] * 201),
    "off_grid false": put("off_grid", value=False),
    "variant": put("variant", value="x"),
    "no definition": put("definition", value=None),
    "a check that is not finite": put("checks", value={"a": math.nan}),
    "a missing record": drop("record"),
    "another machine": put("source", "cpu_model", value="another"),
    "extra rows": lambda e: extra_row(e),
}


def extra_row(entry):
    """One more accepted row between two compared times."""
    entry["t"].insert(1, 5e-05)
    for table in entry["rows"].values():
        for values in table.values():
            values.insert(1, values[0])


@pytest.mark.parametrize("case", NO_FAULT)
def test_what_refuses_nothing(benches, case):
    q = benches("integrated").score(lambda runs: NO_FAULT[case](runs[J[2]]))
    assert not q.run(J[2])["refused"], (case, q.run(J[2])["causes"])
    assert q.verdict("integrated") == PASS
    flagged = (
        "extra key",
        "extra series",
        "variant",
        "definition",
        "check",
        "record",
        "machine",
        "written out",
    )
    assert bool(q.run(J[2])["flags"]) == any(word in case for word in flagged), (
        case,
        q.run(J[2])["flags"],
    )


PROVENANCE = {
    "source incomplete": drop("source", "python"),
    "a missing snapshot": put("source", "snapshot", value=""),
    "checkout_dirty": put("source", "checkout_dirty", value=True),
    "engine_revision": put("source", "engine_revision", value="0" * 40),
    "snapshot_patch_sha256": put("source", "snapshot_patch_sha256", value="0" * 64),
    "host_patch": put("host_patch", value="x"),
    "a missing record_sha256": put("record_sha256", value=None),
    "t": lambda e: (
        [e["t"].insert(1, 0.0)]
        + [v.insert(1, v[0]) for table in e["rows"].values() for v in table.values()]
    ),
    "off_grid_change": put("steps", value=lambda v: v + 1),
    "steps": put("steps", value=lambda v: v - 1),
    "steps mistyped": put("steps", value="800"),
    "status": put("status", value="refused"),
    "status completed with a refusal": put(
        "refusal", value={"kind": "harness", "message": "x", "time_s": None}
    ),
}


@pytest.mark.parametrize("case", PROVENANCE)
def test_provenance_refuses_the_run_and_its_readouts_are_judged(benches, case):
    q = benches("integrated").score(lambda runs: PROVENANCE[case](runs[J[2]]))
    reason = {"steps mistyped": "steps", "status completed with a refusal": "status"}.get(
        case, case
    )
    assert q.run(J[2])["refused"] and reason in q.run(J[2])["reasons"], q.run(J[2])
    assert not q.fails() and q.verdict("integrated") == OPEN
    R = {e["outcome"] for e in q.R(J[2])}
    assert R == (
        {UNFORMED} if case == "t" else {PASS}
    )  # a doubled time leaves the entries that need it not formed


@pytest.mark.parametrize(
    "alter",
    [PROVENANCE["host_patch"], PROVENANCE["off_grid_change"], lambda e: refuse(e, "domain")],
)
def test_a_refusal_never_hides_a_fail(benches, alter):
    def both(runs):
        alter(runs[J[2]])
        runs[J[2]]["rows"]["n_cell_K"]["cell_3"][-1] *= 1 + 1e-3

    q = benches("integrated").score(both)
    assert q.run(J[2])["refused"] and q.verdict("integrated") == FAIL
    assert (J[2], "balance of cells, K") in q.fails()


LEAF = {
    "missing": lambda e: e["rows"]["junction_K"].pop("junction_5"),
    "mistyped": lambda e: e["rows"]["junction_K"]["junction_5"].__setitem__(100, "0.0"),
    "a boolean": lambda e: e["rows"]["junction_K"]["junction_5"].__setitem__(100, True),
    "not finite": lambda e: e["rows"]["junction_K"]["junction_5"].__setitem__(100, math.nan),
    "another length": lambda e: e["rows"]["junction_K"]["junction_5"].pop(),
}


@pytest.mark.parametrize("case", LEAF)
def test_a_judged_leaf_leaves_its_entries_not_formed(benches, case):
    q = benches("integrated").score(lambda runs: LEAF[case](runs[J[1]]))
    assert not q.run(J[1])["refused"] and not q.fails() and q.verdict("integrated") == OPEN
    unformed = {e["readout"] for e in q.entries if e["judged"] and e["outcome"] == UNFORMED}
    assert unformed == {"junction_K", "balance of cells, K"}


def test_a_missing_and_a_doubled_row(benches):
    def missing(runs):
        entry = runs[J[1]]
        entry["t"].pop(7)
        [v.pop(7) for table in entry["rows"].values() for v in table.values()]

    def doubled(runs):
        entry = runs[J[1]]
        entry["t"].insert(8, entry["t"][7] + 1e-13)
        [v.insert(8, v[7]) for table in entry["rows"].values() for v in table.values()]

    for alter in (missing, doubled):
        q = benches("integrated").score(alter)
        assert not q.run(J[1])["refused"] and not q.fails()
        assert {e["outcome"] for e in q.S("integrated") if e["readout"] != "voltage"} == {UNFORMED}
        assert q.outcome(family="integrated", readout="voltage", **{"class": "S"}) == PASS
        assert q.verdict("integrated") == OPEN


@pytest.mark.parametrize("kind", ["definition", "domain", "harness"])
def test_a_refused_run_is_judged_on_the_rows_it_holds(benches, kind):
    def early(runs, wrong):
        entry = runs[J[0]]
        refuse(entry, kind)
        entry["t"] = entry["t"][:50]
        for table in entry["rows"].values():
            for entity in table:
                table[entity] = table[entity][:50]
        if wrong:
            entry["rows"]["n_cell_K"]["cell_0"][40] += 1e-6

    q = benches("integrated").score(lambda runs: early(runs, False))
    assert q.run(J[0])["refused"] and not q.fails() and q.verdict("integrated") == OPEN
    assert {e["outcome"] for e in q.R(J[0])} == {UNFORMED}  # no time is dropped from a pass
    assert q.outcome(run=J[0], readout="completes") == UNFORMED  # D is not judged
    q = benches("integrated").score(lambda runs: early(runs, True))
    assert (J[0], "balance of cells, K") in q.fails() and q.verdict("integrated") == FAIL


def test_a_refused_run_that_has_no_declaration(benches):
    """Amendment 2, item 7: where no declaration exists, `inputs`, `strings` and `declared_strings`
    are empty.
    """

    def alter(runs):
        refuse(runs[J[0]], "harness", rows=False)
        runs[J[0]].update(inputs={}, strings={}, declared_strings=[], steps=None)
        out = structure.Faults()
        assert (
            structure.entry_faults(runs[J[0]], "x", out) == "ionic run, refused (harness)"
            and out.items == []
        )

    q = benches("integrated").score(alter)
    assert (
        q.run(J[0])["refused"]
        and q.nothing_judged(J[0], "integrated")
        and q.verdict("integrated") == OPEN
        and not q.fails()
    )


def test_a_run_in_missing_or_in_neither_list(benches):
    bench = benches("integrated")
    for missing in ([J[1]], []):
        q = bench.score(lambda runs: runs.pop(J[1]), missing=missing)
        assert (
            q.run(J[1])["refused"] and q.cause(J[1], "missing") and q.verdict("integrated") == OPEN
        )
        assert q.nothing_judged(J[1], "integrated")


def test_runs_that_are_not_registered_are_ignored(benches):
    def alter(runs):
        runs["integrated h=1.25e-05 retry"] = copy.deepcopy(runs[J[2]])
        runs["integrated h=1.25e-05 retry"]["record_sha256"] = "1" * 64
        runs["another run"] = dict(copy.deepcopy(runs[J[2]]), record_sha256="2" * 64)

    q = benches("integrated").score(alter)
    assert q.verdict("integrated") == PASS and {item["run"] for item in q.record["ignored"]} == {
        "integrated h=1.25e-05 retry",
        "another run",
    }


def test_the_off_grid_switch_refuses_a_registered_run(benches):
    q = benches("integrated").score(lambda runs: runs[J[0]].update(off_grid=True))
    assert (
        q.run(J[0])["refused"] and q.cause(J[0], "kind harness") and q.verdict("integrated") == OPEN
    )


def test_structural_zeros(benches):
    q = benches("integrated").score(
        lambda runs: runs[J[0]]["rows"]["n_out_Cl"]["outside"].__setitem__(3, 5e-324)
    )
    assert (J[0], "n_out_Cl is zero") in q.fails()


# ----- restarts, pools and schedules (class E) -----


def test_a_restart_equals_the_uninterrupted_run(benches):
    bench = benches("jupiter")
    ulp = lambda v: math.nextafter(v, math.inf)  # noqa: E731
    q = bench.score(
        lambda runs: runs[RESTART]["rows"]["pump"]["membrane_1"].__setitem__(
            5, ulp(runs[RESTART]["rows"]["pump"]["membrane_1"][5])
        )
    )
    assert q.fails() == [(H[0], "restart pump")] and q.verdict("jupiter") == FAIL
    q = bench.score(lambda runs: put("restart", "time_s", value=0.005)(runs[RESTART]))
    assert {e["outcome"] for e in q.entries if str(e["readout"]).startswith("restart ")} == {
        UNFORMED
    }
    q = bench.score(lambda runs: refuse(runs[RESTART], "harness", rows=False))
    assert not q.run(H[0])["refused"] and q.verdict("jupiter") == OPEN and not q.fails()

    def without_the_optional_row(runs):
        entry = runs[RESTART]
        entry["t"].pop(0)
        for table in entry["rows"].values():
            for values in table.values():
                values.pop(0)

    assert bench.score(without_the_optional_row).verdict("jupiter") == PASS


POOLS = {
    "path, an event's time": (
        lambda r: r[POOL]["path"]["cell_1"]["3"][0].__setitem__(
            0, math.nextafter(r[POOL]["path"]["cell_1"]["3"][0][0], 0)
        ),
        {(POOL, "cell_1 path")},
    ),
    "path, an availability": (
        lambda r: r[POOL]["path"]["cell_1"]["2"][1].__setitem__(1, 0),
        {(POOL, "cell_1 path"), (POOL, "cell_1 exposure")},
    ),
    "a seed": (
        lambda r: [
            r[POOL]["inputs"]["cell_0"].update(seed=1),
            r[POOL]["pool"]["cell_0"].update(seed=1),
        ],
        {(POOL, "cell_0 seed")},
    ),
    "the restart's array": (
        lambda r: r[POOL_RESTART]["pool"]["cell_0"]["arrays"]["free"].__setitem__(2, 0),
        {(POOL, "restart cell_0 free")},
    ),
    "the restart's path": (
        lambda r: r[POOL_RESTART]["path"]["cell_0"].update({"2": [[0.0150, 1]]}),
        {(POOL, "restart cell_0 path")},
    ),
    "a schedule's time": (
        lambda r: r[B[0]]["inputs"]["controls"]["channel"]["channel_0"][1].__setitem__(0, 0.002),
        {(B[0], "channel schedule")},
    ),
    "a recorded seed": (
        lambda r: r[B[0]]["inputs"]["assembly"]["pool_seeds"].update(cell_1=3),
        {(B[0], "pool seeds")},
    ),
    "a schedule left out": (
        lambda r: r[B[0]]["inputs"]["controls"].pop("channel"),
        {(B[0], "channel schedule")},
    ),
}


@pytest.mark.parametrize("case", POOLS)
def test_class_E_of_the_pools_and_the_schedules(benches, case):
    alter, wanted = POOLS[case]
    q = benches("base").score(alter)
    assert set(q.fails()) == wanted and q.verdict("base") == FAIL


POOL_FORM = {
    "an array of another shape": lambda r: r[POOL]["pool"]["cell_0"]["arrays"]["free"].pop(),
    "an array that is not finite": lambda r: r[POOL]["pool"]["cell_0"]["arrays"][
        "time_s"
    ].__setitem__(0, math.inf),
    "a path's world left out": lambda r: r[POOL]["path"]["cell_0"].pop("7"),
    "a switch list's channel left out": lambda r: r[B[0]]["inputs"]["assembly"]["switch_list"].pop(
        "channel_1"
    ),
    "no pool seeds": lambda r: r[B[0]]["inputs"]["assembly"].pop("pool_seeds"),
}


@pytest.mark.parametrize("case", POOL_FORM)
def test_class_E_leaves_that_are_missing_or_mistyped(benches, case):
    q = benches("base").score(POOL_FORM[case])
    assert (
        not q.fails()
        and q.verdict("base") == OPEN
        and any(e["outcome"] == UNFORMED for e in q.entries)
    )


def test_schedules_may_hold_the_initial_entry_and_repeats(benches):
    def alter(runs):
        block = runs[B[1]]["inputs"]
        for channel, listed in block["assembly"]["switch_list"].items():
            block["assembly"]["switch_list"][channel] = [[0.0, 1], *listed, [0.0199, listed[-1][1]]]
            block["controls"]["channel"][channel] = block["controls"]["channel"][channel][1:]

    assert benches("base").score(alter).verdict("base") == PASS


def test_pool_runs_echo_and_seed_provenance(benches):
    bench = benches("base")
    q = bench.score(lambda r: r[POOL]["pool"]["cell_0"].update(seed=5))
    assert "pool seed" in q.run(POOL)["reasons"] and not q.fails() and q.verdict("base") == OPEN
    q = bench.score(lambda r: r[POOL]["inputs"]["cell_0"]["pool"].update(k_off_s_inv=301.0))
    assert q.cause(POOL, "departing echo") and q.verdict("base") == OPEN
    q = bench.score(
        lambda r: r[POOL]["inputs"].update(cell_2=copy.deepcopy(r[POOL]["inputs"]["cell_1"]))
    )
    assert q.cause(POOL, "departing echo", "cell_2")
    q = bench.score(
        lambda r: [
            r[POOL]["inputs"]["cell_0"]["pool"].pop(k)
            for k in ("root_node", "world_id_start", "initial_bond_indices")
        ]
    )
    assert not q.run(POOL)["refused"] and q.verdict("base") == PASS


def test_the_steps_of_a_split_run(benches):
    bench = benches("base")
    least, events = (
        3200,
        sum(len(p) for p in bench.reg.expected_paths(bench.reg.runs[B[2]]).values()),
    )
    for steps, good in (
        (least, True),
        (least + events, True),
        (least - 1, False),
        (least + events + 1, False),
    ):
        q = bench.score(lambda r, count=steps: r[B[2]].update(steps=count))
        assert q.run(B[2])["refused"] is not good and (good or q.run(B[2])["reasons"] == ["steps"])


# ----- plants -----

PLANT = {
    "EP1 missing": ("jupiter", lambda r: r.pop(EP1), "EP1", "unscorable", OPEN),
    "EP1 without its change": (
        "jupiter",
        lambda r: r[EP1]["inputs"]["channels"]["channel_0"].update(max_permeability_m_per_s=3e-10),
        "EP1",
        "unscorable",
        OPEN,
    ),
    "EP1 refused and caught": (
        "jupiter",
        lambda r: r[EP1].update(host_patch="x"),
        "EP1",
        "unscorable",
        OPEN,
    ),
    "EP1 refused and equal": (
        "jupiter",
        lambda r: r[EP1].update(host_patch="x", rows=r[H[2]]["rows"]),
        "EP1",
        "not caught",
        FAIL,
    ),
    "EP1 on a refused family": (
        "jupiter",
        lambda r: r[H[0]].update(host_patch="x"),
        "EP1",
        "unscorable",
        OPEN,
    ),
    "EP2 not swapped": (
        "base",
        lambda r: [
            x.update(channel_0=x["channel_1"], channel_1=x["channel_0"])
            for x in [r[EP2]["inputs"]["controls"]["channel"]]
        ],
        "EP2",
        "unscorable",
        OPEN,
    ),
    "EP2 with other seeds": (
        "base",
        lambda r: r[EP2]["inputs"]["assembly"]["pool_seeds"].update(cell_0=1),
        "EP2",
        "unscorable",
        OPEN,
    ),
    "EP2 equal": ("base", lambda r: r[EP2].update(rows=r[B[2]]["rows"]), "EP2", "not caught", FAIL),
}


@pytest.mark.parametrize("case", PLANT)
def test_engine_plants(benches, case):
    name, alter, plant, score, verdict = PLANT[case]
    q = benches(name).score(alter)
    assert q.plant(plant) == score and q.verdict(name) == verdict


def test_a_structural_plant_that_the_candidate_resembles_is_not_caught(benches):
    bench = benches("integrated")
    run = bench.planted.run(
        "ST9 the schedule is not applied", bench.reg.families["integrated"], 2.5e-05
    )
    world = bench.reg.worlds["integrated"]

    def alter(runs):
        for name in J:
            for series in ("junction_Na", "junction_K", "junction_Cl"):
                values = run.series(series, world.row_times)
                runs[name]["rows"][series] = {
                    j: values[:, i].tolist() for i, j in enumerate(world.junctions)
                }

    q = bench.score(alter)
    assert [p["score"] for p in q.record["plants"]["plants"]] == ["not caught"] and q.verdict(
        "integrated"
    ) == FAIL


# ----- the order rule, the bands and power -----


@pytest.mark.parametrize(
    "d2, d1, expected",
    [
        (1.0, 1.0, "unresolved"),
        (0.0, 0.0, "unresolved"),
        (3.0, 1.0, "mixed"),
        (1.0, 3.0, "mixed"),
        (64.0, 4.0, "resolved"),
    ]
    + [
        (2.0**4.5 * 4, 4.0, "resolved"),
        (2.0**3.5 * 4, 4.0, "resolved"),
        (2.0**4.6 * 4, 4.0, "resolved outside its window"),
    ]
    + [(2.0**3.4 * 4, 4.0, "resolved outside its window")],
)
def test_the_order_rule(d2, d1, expected):
    assert bands.classify(d2, d1, 2.0, 4) == expected
    inside, outside = bands.score(1.0, 1.0, expected), bands.score(1.5, 1.0, expected)
    table = {
        "unresolved": (PASS, FAIL),
        "resolved": (PASS, FAIL),
        "mixed": (OPEN, FAIL),
        "resolved outside its window": (OPEN, OPEN),
    }
    assert (inside, outside) == table[expected]
    assert (
        bands.classify(math.inf, d1, 2.0, 4) == "not finite"
        and bands.score(0.0, 1.0, "not finite") == FAIL
    )


def test_estimates_and_bands_are_the_formulas():
    world = Registration(only=KEEP["jupiter"]).worlds["jupiter_baseline"]
    e = world.by_name["n_cell_K"]
    s, ref, eps = e.scale, e.amount_ref, 2.0**-52
    Y = [np.array([[0.0]]), np.array([[32.0]]), np.array([[33.0]])]
    d2, d1, U = bands.estimate(*Y, 4)
    assert (d2, d1, U) == (32.0, 1.0, max(1 / 15, 32 / 240)) and bands.estimate(*Y, 2)[2] == max(
        1 / 3, 32 / 12
    )
    b = bands.band(e, U, 0.5, 3200, 800)
    beta = (
        2 * (0.5 + U) + 8 * eps * 3201 * s + 8 * eps * 801 * s + 4e-12 * s + 2.5 * eps * 3201 * ref
    )
    assert b["beta"] == pytest.approx(beta, rel=1e-15) and b["theta"] == pytest.approx(
        10 * (8 * eps * 3201 * s + 2.5 * eps * 3201 * ref), rel=1e-15
    )
    phi = world.by_name["phi_out"]
    assert (
        phi.e_close() == 4.3e-12 * 0.12
        and phi.e_store(3200) == 0.0
        and world.by_name["pump"].e_close() == 4e-12 * 0.002
    )
    assert float(bands.extrapolate(Y[1], Y[2], 4)[0, 0]) == 33.0 + 1 / 15


def test_exposure_and_changes():
    assert changes([[0.0, 1], [0.2, 0], [0.3, 0], [0.4, 1]]) == [
        [0.2, 0],
        [0.4, 1],
    ]  # SPEC section 3.2's own example
    assert identities.exposure([[0.25, 0], [0.5, 0], [0.75, 1]], 1.0) == 0.5
    assert identities.exposure([], 0.02) == 0.02 and identities.exposure([[0.01, 0]], 0.02) == 0.01


def test_the_state_form_is_flagged_and_decides_nothing(benches):
    """A statistic inside the band with e_store and outside the one without."""
    bench = benches("integrated")
    world = bench.reg.worlds["integrated"]
    shift = 0.5 * world.by_name["n_cell_K"].e_store(800)

    def alter(runs):
        for name in J:
            runs[name]["rows"]["n_cell_K"]["cell_2"] = [
                v + shift for v in runs[name]["rows"]["n_cell_K"]["cell_2"]
            ]

    q = bench.score(alter)
    item = q.S("integrated", "n_cell_K")[0]
    assert (
        item["state_form"] and item["outcome"] == PASS and q.verdict("integrated") in (PASS, FAIL)
    )
    assert any(f["what"] == "state form" for f in q.record["flags"])


def test_an_order_two_world_reports_its_identities(benches):
    bench = benches("integrated")
    world = bench.reg.worlds["integrated"]
    world.p = 2
    try:
        counts = scoring.expected_counts(bench.reg, "integrated")
        assert (counts["R"], counts["energy"]) == (0, 0)
        q = bench.score(
            lambda runs: [
                v.__setitem__(-1, 1.0) for v in runs[J[2]]["rows"]["heat_junction"].values()
            ]
        )
        item = next(e for e in q.entries if e["readout"] == "energy_identity")
        assert item["outcome"] == c.REPORTED and item["reported"] == FAIL and not item["judged"]
        assert all(not e["judged"] for e in q.entries if e["class"] == "R")
    finally:
        world.p = 4


def with_margins(bench, alter):
    """A bench that reads other margins, and its own otherwise."""
    other = copy.copy(bench)
    other.reg = copy.copy(bench.reg)
    other.reg.margins = copy.deepcopy(bench.reg.margins)
    alter(other.reg.margins["worlds"]["integrated"])
    return other


def test_power_is_read_from_the_margins(benches):
    """An untested entry counts for neither side. An untested mechanism leaves its consumer open."""
    bench = benches("integrated")
    q = with_margins(bench, lambda m: m["entries"]["heat_junction"].update(ratio=1e-12)).score()
    block = q.record["consumers"]["integrated"]["sets"]["all"]
    assert q.S("integrated", "heat_junction")[0]["outcome"] == c.NOT_TESTED
    assert q.verdict("integrated") == PASS
    assert block["not_tested"] == [["integrated", "heat_junction"]]
    q = with_margins(bench, lambda m: m["entries"]["junction_gate"].update(ratio=1e-12)).score()
    assert q.verdict("integrated") == OPEN and q.record["retry_owed"]["runs"] == []
    assert not q.record["consumers"]["integrated"]["sets"]["all"]["mechanisms"]["junction gate"][
        "tested"
    ]
    q = with_margins(bench, lambda m: m["entries"]["junction_K"].update(ratio=1e-12)).score()
    assert q.verdict("integrated") == PASS  # its mechanism has two other homes

    def wrong(runs):
        for name in J:
            values = runs[name]["rows"]["heat_junction"]
            runs[name]["rows"]["heat_junction"] = plants.scaled(values, 1.01)

    q = with_margins(bench, lambda m: m["entries"]["heat_junction"].update(ratio=1e-12)).score(
        wrong
    )
    assert q.S("integrated", "heat_junction")[0]["outcome"] == FAIL  # untested, and above beta


def test_a_plant_whose_distance_is_at_most_two_bands_is_unscorable(benches):
    def alter(margins):
        margins["structural"]["ST9 the schedule is not applied"]["junction_Cl"]["distance"] = 1e-20

    q = with_margins(benches("integrated"), alter).score()
    (plant,) = q.record["plants"]["plants"]
    assert plant["score"] == "unscorable" and q.verdict("integrated") == OPEN
    assert [e["score"] for e in plant["entries"]] == ["caught", "caught", "unscorable"]


def test_the_band_decides(benches):
    """An entry just inside its band passes, and just outside it fails."""
    bench = benches("integrated")
    entry = bench.reg.worlds["integrated"].by_name["junction_gate"]
    beta = bench.score().S("integrated", "junction_gate")[0]["band"]
    for share, outcome in ((0.98, PASS), (1.02, FAIL)):

        def alter(runs, shift=share * beta):
            for name in J:
                runs[name]["rows"]["junction_gate"]["junction_7"][33] += shift

        q = bench.score(alter)
        item = q.S("integrated", "junction_gate")[0]
        assert item["outcome"] == outcome and item["at"] == [entry.times[33], "junction_7"]
        assert item["ratio"] == pytest.approx(share, rel=1e-3)


# ----- the retry -----


def perturbed(bench, mixed: bool):
    """Tables of `integrated` in which one home entry is owed the retry: by order (mixed) or by
    power (resolved and untested).
    """
    runs = Lazy(bench.tables["integrated"]["runs"])
    entry = bench.reg.worlds["integrated"].by_name["junction_gate"]
    size = 3 * c.THRESHOLD * entry.e_round(800) if mixed else 1e-2
    values = {name: runs[name]["rows"]["junction_gate"]["junction_0"] for name in J}
    values[J[0]][60] += size if mixed else 17 * size
    if not mixed:
        values[J[1]][60] += size
    tables = dict(bench.tables)
    tables["integrated"] = dict(tables["integrated"], runs=dict(runs))
    return tables


@pytest.mark.parametrize("mixed", [True, False])
def test_the_retry(benches, mixed):
    bench = benches("integrated")
    tables = perturbed(bench, mixed)
    state = scoring.Tables(bench.reg, bench.note, TableSet.from_data(tables))
    power = scoring.stage1(state, bench.c0, {"a": 1})
    first = scoring.Stage2(state, bench.c0, power, bench.captures, bench.planted).run()
    name = "integrated h=1.25e-05 retry"
    reason = "junction_gate: order" if mixed else "junction_gate: power"
    assert first["retry_owed"] == {
        "kind": c.RETRY_KIND,
        "part": 1,
        "runs": [name],
        "why": {"integrated": [reason]},
    }
    block = first["consumers"]["integrated"]
    assert (
        block["verdict"] == OPEN and not block["final"] and block["retry_owed"] == [name]
    )  # untested: its mechanism has no other home

    def second(alter=lambda runs: None):
        made = fabricate.Fabricator(bench.reg, bench.captures, bench.planted).retry_tables([name])
        alter(made["integrated"]["runs"])
        again = scoring.Tables(
            bench.reg,
            bench.note,
            TableSet.from_data(tables),
            TableSet.from_data(made, retry=True),
            [name],
        )
        power2 = scoring.stage1(again, bench.c0, {"a": 2}, first)
        assert set(power2["families"]["integrated"]) == {"junction_gate"}
        return Query(
            scoring.Stage2(
                again, bench.c0, power, bench.captures, bench.planted, power2, first
            ).run()
        )

    q = second()
    item = q.S("integrated", "junction_gate")[0]
    assert item["runs"] == [*J[1:], name] and item["pass_of_the_judgement"] == 2
    if mixed:
        assert (
            q.verdict("integrated") == PASS
            and item["outcome"] == PASS
            and q.record["consumers"]["integrated"]["final"]
        )
        covered = q.record["consumers"]["integrated"]["steps_covered"]
        assert covered == {
            "steps_s": [[0.0001, 5e-05, 2.5e-05]],
            "judged_again": {
                "integrated": {"steps_s": [5e-05, 2.5e-05, 1.25e-05], "entries": ["junction_gate"]}
            },
        }
        q = second(lambda runs: runs.clear())
        assert (
            q.run(name)["refused"] and q.verdict("integrated") == OPEN
        )  # an owed retry run that is missing is a missing run
        q = second(lambda runs: runs[name]["rows"]["n_cell_K"]["cell_0"].__setitem__(-1, 1.0))
        assert (name, "balance of cells, K") in q.fails() and q.verdict(
            "integrated"
        ) == FAIL  # its own R entries are judged
        q = second(lambda runs: runs[name]["rows"]["n_out_K"]["outside"].__setitem__(-1, 1e-30))
        assert (name, "n_out_K is zero") in q.fails() and q.verdict(
            "integrated"
        ) == FAIL  # and its class E (Amendment 2)
    else:
        assert (
            item["outcome"] == OPEN and q.verdict("integrated") == OPEN
        )  # h2 stays coarse: mixed, and it stays so


def test_a_refused_run_takes_no_retry(benches):
    bench = benches("integrated")
    tables = perturbed(bench, True)
    entry = copy.deepcopy(tables["integrated"]["runs"][J[1]])
    entry["host_patch"] = "x"
    tables["integrated"]["runs"][J[1]] = entry
    record = plants.judge(bench.reg, bench.note, tables, bench.c0, bench.captures, bench.planted)
    assert record["retry_owed"]["runs"] == []


# ----- C0 -----

C0_FAULT = {
    "a scale": (
        "scales",
        lambda reg: reg.inputs["worlds"]["cell"]["scales"].update(pump=0.0020000001),
    ),
    "an amount reference": (
        "scales",
        lambda reg: reg.inputs["worlds"]["base"]["amount_refs"].update(voltage=2900.0),
    ),
    "a volume of the block": (
        "definitions",
        lambda reg: reg.inputs["worlds"]["integrated"]["ionic"]["cells"]["cell_0"].update(
            volume_pL=0.46
        ),
    ),
    "a seed": (
        "definitions",
        lambda reg: reg.inputs["worlds"]["base"]["pools"]["cell_1"]["seeds"].__setitem__(2, 1),
    ),
    "a literal block": (
        "literal_blocks",
        lambda reg: reg.inputs["worlds"]["cell"]["ionic"].update(end_s=0.03),
    ),
    "a run": ("run_list", lambda reg: reg.runs["integrated h=5e-05"].update(step_s=4e-05)),
    "a path": ("paths", lambda reg: reg.paths["worlds"]["cell"]["s1"]["cell_0"]["0"].pop()),
    "an exposure": (
        "exposures",
        lambda reg: reg.paths["worlds"]["base"]["s0"]["cell_1"]["2"][0].__setitem__(0, 0.0003),
    ),
    "a pinned manifest": (
        "pins",
        lambda reg: reg.legacy["captures"].update(science_manifest_sha256="0" * 64),
    ),
    "a snapshot's record": (
        "pins",
        lambda reg: reg.legacy["integrated_capture"].update(snapshot_manifest_sha256="0" * 64),
    ),
    "a planted file": (
        "plant_files",
        lambda reg: reg.manifest["runs"][3]["outputs_sha256"].update({"run/run.json": "0" * 64}),
    ),
    "a declared change": (
        "plant_files",
        lambda reg: reg.manifest["runs"][3]["modify"][0].update(mul=1.02),
    ),
    "a mechanism's home": (
        "mechanisms",
        lambda reg: reg.margins["worlds"]["cell"]["mechanisms"]["channel kinetics"].pop("gate_h"),
    ),
    "a key": ("spec_keys", lambda reg: reg.margins.update(extra=1)),
    "a printed class": (
        "legacy_classes",
        lambda reg: reg.legacy["worlds"]["integrated"]["entries"]["voltage"].update(
            {"class": "resolved"}
        ),
    ),
    "a registered distance": (
        "engine_plants",
        lambda reg: reg.margins["worlds"]["base"]["structural"][
            "ST6 availability on the other cell's channel"
        ]["channel_K"].update(distance=2.9e-07),
    ),
    "a published count": ("counts", lambda reg: reg.worlds["integrated"].entries.pop()),
}


@pytest.mark.parametrize("case", C0_FAULT)
def test_C0_names_a_fault(benches, case):
    """Every clause is able to fail: one changed datum, and its clause names it."""
    benches("integrated")
    clause, alter = C0_FAULT[case]
    made = C0(Registration(profile=copy.deepcopy(PART1)))
    alter(made.reg)
    if clause == "engine_plants":
        made.reg.only = lambda run: run["family"] in ("base s0 w2", "jupiter_baseline")
        made.reg.families = {
            k: v for k, v in made.reg.families.items() if k in ("base s0 w2", "jupiter_baseline")
        }
        made.legacy_classes()
    try:
        getattr(made, clause)()
    except Exception as error:  # C0.run turns what cannot go on into a fault
        assert "0" * 64 in str(error), (case, error)
    else:
        assert made.clauses[-1].faults, case


# ----- files -----


def written(tmp_path, bench, consumer="integrated"):
    """The fabricated table of a consumer, its SHA256SUMS and a strings note, on disk."""
    cli.write_tables(tmp_path / "table", {consumer: bench.tables[consumer]})
    strictjson.dump(tmp_path / "strings.json", bench.note_data)
    strictjson.dump(tmp_path / "c0.json", bench.c0)
    return tmp_path / "table"


def test_files_that_are_refused_whole(benches, tmp_path):
    bench = benches("integrated")
    folder = written(tmp_path, bench)
    path = folder / "table_integrated.json"
    text, sums = path.read_text(), (folder / "SHA256SUMS").read_text()

    def reasons(content=text, sums_text=sums):
        path.write_text(content)
        (folder / "SHA256SUMS").unlink(missing_ok=True)
        if sums_text is not None:
            (folder / "SHA256SUMS").write_text(sums_text)
        tables = TableSet.read(folder, ["integrated"])
        return tables, tables.files["integrated"].refusals

    assert reasons()[1] == []
    doubled = text.replace('"kind":', '"kind": "x",\n "kind":', 1)
    assert "duplicate key" in reasons(doubled, sums)[1][-1]
    assert "departs" in reasons(text + " ", sums)[1][0]
    assert "missing from SHA256SUMS" in reasons(text, "0" * 64 + "  table_other.json\n")[1][0]
    tables, found = reasons(text, None)
    assert found == [] and tables.flags[0][0] == "SHA256SUMS"
    for old, new in (
        ('"part": 1', '"part": 2'),
        ('"fmol"', '"mol"'),
        ('"consumer": "integrated"', '"consumer": "cell"'),
        (c.TABLE_KIND, "x"),
        ('"missing": []', '"absent": []'),
    ):
        assert reasons(text.replace(old, new, 1), None)[1], new
    assert reasons("{", None)[1]
    tables, _ = reasons(text + " ", sums)
    state = scoring.Tables(bench.reg, bench.note, tables)
    record = scoring.Stage2(
        state, bench.c0, scoring.stage1(state, bench.c0, {}), bench.captures, bench.planted
    ).run()
    block = record["consumers"]["integrated"]
    assert (
        block["verdict"] == OPEN
        and "its file is refused" in block["sets"]["all"]["inconclusive"][0]
    )
    assert {e["outcome"] for e in record["entries"] if e["judged"]} == {UNFORMED}


def test_nan_and_infinity_are_read():
    assert math.isnan(strictjson.loads(b'{"a": NaN}')["a"]) and strictjson.loads(b"[Infinity]") == [
        math.inf
    ]
    with pytest.raises(strictjson.DuplicateKey):
        strictjson.loads(b'{"a": {"b": 1, "b": 1}}')


# ----- the order of the stages -----


def test_the_order_of_the_stages(benches, tmp_path, monkeypatch, capsys):
    """power.json comes from the tables and C0 alone, and stage 2 starts only from its recorded
    sha256 and the recorded tables.
    """
    bench = benches("integrated")
    folder = written(tmp_path, bench)
    monkeypatch.setattr(cli, "registration", lambda args: bench.reg)
    first = [
        "--tables",
        str(folder),
        "--tables-record",
        str(tmp_path / "hashes.json"),
        "--strings",
        str(tmp_path / "strings.json"),
        "--c0",
        str(tmp_path / "c0.json"),
    ]
    power, out = tmp_path / "power.json", tmp_path / "judged"

    def stage2(digest, where=out):
        return cli.main(
            ["stage2", *first, "--power", str(power), "--power-sha256", digest, "--out", str(where)]
        )

    assert cli.main(["hash", "--tables", str(folder), "--out", str(tmp_path / "hashes.json")]) == 0

    def closed(*args, **kwargs):
        raise AssertionError("stage 1 opened the reference side")

    with monkeypatch.context() as patch:
        for name in ("Captures", "Planted"):
            patch.setattr(cli, name, closed)
        assert cli.main(["stage1", *first, "--out", str(power)]) == 0
        assert stage2("0" * 64) == 2  # refused before it opens the reference side
    digest = strictjson.sha256(power.read_bytes())
    with pytest.raises(FileExistsError):
        cli.main(["stage1", *first, "--out", str(power)])  # nothing is overwritten

    table = folder / "table_integrated.json"
    honest = table.read_bytes()
    table.write_bytes(honest.replace(b"0.02", b"0.020", 1))
    assert stage2(digest) == 2  # the tables are not the recorded ones
    table.write_bytes(honest)
    changed = json.loads(power.read_text())
    changed["families"]["integrated"]["junction_K"]["beta"] *= 2
    power.write_text(json.dumps(changed))
    assert (
        stage2(strictjson.sha256(power.read_bytes())) == 2
    )  # not what stage 1 makes of these tables
    power.unlink()
    assert (
        cli.main(["stage1", *first, "--out", str(power)]) == 0
        and strictjson.sha256(power.read_bytes()) == digest
    )
    assert stage2(digest) == 0
    record = json.loads((out / "record.json").read_text())
    assert (
        record["hashes"]["power_sha256"] == digest
        and record["consumers"]["integrated"]["verdict"] == PASS
    )
    assert json.loads((out / "retry_owed.json").read_text())["runs"] == []
    capsys.readouterr()


def test_the_retry_by_command(benches, tmp_path, monkeypatch, capsys):
    """The retry's two stages read the first pass's files by their recorded sha256, and refuse
    others.
    """
    bench = benches("integrated")
    written(tmp_path, bench)
    monkeypatch.setattr(cli, "registration", lambda args: bench.reg)
    cli.write_tables(tmp_path / "owed", {"integrated": perturbed(bench, True)["integrated"]})
    T, R = tmp_path / "owed", tmp_path / "table-retry"
    first = [
        "--tables",
        str(T),
        "--tables-record",
        str(tmp_path / "h.json"),
        "--strings",
        str(tmp_path / "strings.json"),
        "--c0",
        str(tmp_path / "c0.json"),
    ]
    digest = lambda name: strictjson.sha256((tmp_path / name).read_bytes())  # noqa: E731
    assert cli.main(["hash", "--tables", str(T), "--out", str(tmp_path / "h.json")]) == 0
    assert cli.main(["stage1", *first, "--out", str(tmp_path / "power.json")]) == 0
    power = ["--power", str(tmp_path / "power.json"), "--power-sha256", digest("power.json")]
    assert cli.main(["stage2", *first, *power, "--out", str(tmp_path / "judged")]) == 0
    owed = json.loads((tmp_path / "judged/retry_owed.json").read_text())
    assert owed["runs"] == ["integrated h=1.25e-05 retry"]
    cli.write_tables(
        R, fabricate.Fabricator(bench.reg, bench.captures, bench.planted).retry_tables(owed["runs"])
    )
    assert cli.main(["hash", "--tables", str(R), "--out", str(tmp_path / "hr.json")]) == 0

    recorded = digest("judged/retry_owed.json")

    def again(command, *more, owed_digest=recorded):
        return cli.main(
            [
                command,
                *first,
                *power,
                "--record",
                str(tmp_path / "judged/record.json"),
                "--owed",
                str(tmp_path / "judged/retry_owed.json"),
                "--owed-sha256",
                owed_digest,
            ]
            + ["--retry-tables", str(R), "--retry-record", str(tmp_path / "hr.json"), *more]
        )

    assert again("retry-stage1", "--out", str(tmp_path / "p2.json"), owed_digest="0" * 64) == 2
    assert again("retry-stage1", "--out", str(tmp_path / "p2.json")) == 0
    assert (
        again(
            "retry-stage2",
            "--power-retry",
            str(tmp_path / "p2.json"),
            "--power-retry-sha256",
            "0" * 64,
            "--out",
            str(tmp_path / "final"),
        )
        == 2
    )
    assert (
        again(
            "retry-stage2",
            "--power-retry",
            str(tmp_path / "p2.json"),
            "--power-retry-sha256",
            digest("p2.json"),
            "--out",
            str(tmp_path / "final"),
        )
        == 0
    )
    verdict = json.loads((tmp_path / "final/verdict.json").read_text())
    assert (
        verdict["consumers"]["integrated"]["verdict"] == PASS
        and verdict["pass_of_the_judgement"] == 2
        and verdict["retry_owed"] == []
    )
    capsys.readouterr()


def test_stage_1_needs_a_passing_C0(benches):
    bench = benches("integrated")
    state = scoring.Tables(bench.reg, bench.note, TableSet.from_data(bench.tables))
    for change in ({"status": "fail"}, {"spec_sha256": {}}):
        with pytest.raises(scoring.OrderFault):
            scoring.stage1(state, {**bench.c0, **change}, {})
    for alter in (
        lambda note: note["runs"].pop(J[0]),
        lambda note: note["labels"].update(rk4=""),
        lambda note: note["runs"][J[0]]["laws"].append("x"),
    ):
        note = copy.deepcopy(bench.note_data)
        alter(note)
        with pytest.raises(scoring.OrderFault, match="strings note"):
            scoring.Tables(bench.reg, StringsNote(note, "x"), TableSet.from_data(bench.tables))


# ----- the structure-only mode and the rehearsal's mode -----


def test_structure_only(benches, tmp_path):
    bench = benches("integrated")
    folder = written(tmp_path, bench)
    found = structure.table_faults(folder)
    assert found["faults"] == [] and found["kinds_of_run"] == {"ionic run": 3}
    entry = copy.deepcopy(bench.tables["integrated"]["runs"][J[0]])
    for alter in (
        drop("checks"),
        put("rows", "pump_x", value={"m": [True]}),
        put("source", "blas_threads", value="1"),
        put("restart", value={}),
        put("inputs", "cells", "cell_0", value={}),
    ):
        broken, out = copy.deepcopy(entry), structure.Faults()
        alter(broken)
        structure.entry_faults(broken, "x", out)
        assert out.items


def test_a_profile_reads_a_rehearsal(tmp_path, benches):
    """The rehearsal's path, on the registered files under a profile: C0's general clauses pass, and
    the tables pass.
    """
    benches("integrated")
    (tmp_path / "profile.json").write_text(json.dumps({**PART1, "not_blind": {}, "counts": {}}))
    args = cli.parser().parse_args(
        ["c0", "--profile", str(tmp_path / "profile.json"), "--out", "x"]
    )
    reg = cli.registration(args)
    assert reg.rehearsal and reg.profile["not_blind"] == {}
    made = C0(Registration(profile=reg.profile, rehearsal=True, only=KEEP["integrated"]))
    made.scales()
    made.reference_identities()
    assert [clause.faults for clause in made.clauses] == [[], []]


# ----- the echo alone -----


def test_an_echo_of_the_inputs_departs_nowhere():
    reg = Registration(only=KEEP["jupiter"])
    for world in reg.worlds.values():
        out = Echo()
        compare_block(world.block, plants.reversed_maps(copy.deepcopy(world.block)), world, out)
        assert out.departures == [] and out.extras == []


def test_rows_are_matched_by_time_and_not_by_bits(benches):
    bench = benches("integrated")
    entry = copy.deepcopy(bench.tables["integrated"]["runs"][J[0]])
    entry["t"] = [t + (1e-13 if t else 0.0) for t in entry["t"]]
    rows = RunRows(bench.reg.worlds["integrated"], entry)
    assert rows.get("junction_K", (0.0, 0.015)).shape == (2, 12)
    assert hash_folder.__doc__
