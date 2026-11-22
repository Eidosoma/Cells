"""Reconstruct the pool across a shear event with rupture at birth (Cells record R10)."""

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import division, population, records, runner
from tests.assembly_lineage_v2_fixtures import definition
from tests.unit.test_assembly_lineages_v2_lumen import K_L, osmotic_world

BOOKS = (("event_heat_kT", "release_heat_kT"), ("reservoir_work_kT", "release_reservoir_work_kT"))


def birth_spec(mode, held, seed, daughters=2):
    world = osmotic_world(
        L_pool=20,
        L_mem=6 * daughters,
        S_pool=0,
        S_lumen=0,
        I_lumen=4 * daughters,
        floor=4 * K_L,
        sigma_max=1e-9,
    )
    world["division"] = {"law": division.SHEAR_FISSION}
    if held:
        inert = next(p for p in world["phases"]["pool"]["species"] if p["id"] == "I")
        inert.update(kind="held", held_mM=10.0)
        del world["founder"]["I@pool"]
    if mode == "population":
        founder = {name: n for name, n in world["founder"].items() if not name.endswith("@pool")}
        world["population"] = {
            "structure": population.SHARED_POOL,
            "slots": 3,
            "founders": [founder, dict(founder)] if daughters == 2 else [founder],
        }
        world["founder"].update(dict.fromkeys(founder, 0))
    else:
        world["division"]["continuation"] = "first"
    raw = definition(world, seed=seed, molecules=128, horizon=0.001, event_limit=64, row_every=1)
    raw["execution"]["mode"] = mode
    raw["experiment"].update(
        diagnostic=True,
        schedules=[{"index": 0, "kind": "shear", "k": daughters, "times_s": [0.001]}],
    )
    return parse_spec(raw)


def checked_pool_change(places, rows, field, before, after, returned):
    """Read a forward finite receipt and its inverse, or the debit to a held supply."""
    for p in places:
        if p["phase"] != "pool":
            continue
        k = p["index"]
        n = returned.get(p["name"], 0)
        start, end = int(rows[field][before, k]), int(rows[field][after, k])
        supplied = int(rows["reservoir_supplied"][after, k] - rows["reservoir_supplied"][before, k])
        if p["kind"] == "finite":
            assert n <= end and end - n == start and supplied == 0, p["name"]
        else:
            assert end == start and supplied == -n, p["name"]


def check_release(places, rows, field, before, after, release, daughter):
    pool = {p["species"]: p["name"] for p in places if p["phase"] == "pool"}
    cargo = Counter()
    for p, n in zip(vesicle_places(places), daughter["counts"], strict=True):
        if n:
            cargo[pool[p["species"]]] += n
    assert release["returned"] == dict(cargo)
    checked_pool_change(places, rows, field, before, after, cargo)
    assert release["time_s"] == rows["row_time"][after]
    for column, term in BOOKS:
        change = rows[column][after] - rows[column][before]
        assert math.isclose(change, release[term], rel_tol=1e-12, abs_tol=1e-12), term
    return {"key": daughter["key"], "slot": daughter["slot"], "returned": dict(cargo)}


def vesicle_places(places):
    return [
        p
        for phase in ("membrane", "lumen")
        for p in places
        if p["phase"] == phase and p["kind"] != "held"
    ]


def lineage_birth(meta, diag, stop, rows, at_shear):
    (attempt,) = stop["attempts"]
    assert attempt["outcome"] == "split"
    (before,), (after,) = at_shear["shear"], at_shear["end"]
    assert before < after
    places = meta["places"]
    finite = [p["index"] for p in places if p["phase"] == "pool" and p["kind"] == "finite"]
    assert [places[k]["name"] for k in finite] == diag["pool_places"]
    counts = rows["place_count"]
    assert stop["pool_after"] == attempt["pool_after"] == counts[before, finite].tolist()
    assert diag["states"]["final"]["pool"] == counts[after, finite].tolist()
    daughters = attempt["daughters"]
    chosen = daughters[attempt["followed"]]
    assert chosen["slot"] == 0 and all(
        d["slot"] is None for j, d in enumerate(daughters) if j != attempt["followed"]
    )
    vesicle = [p["index"] for p in vesicle_places(places)]
    assert diag["vesicle_places"] == [places[k]["name"] for k in vesicle]
    assert counts[before, vesicle].tolist() == chosen["counts"]
    assert attempt["heat_kT"] == attempt["reservoir_work_kT"] == 0
    discarded = (
        rows["discarded_free_energy_kT"][before] - rows["discarded_free_energy_kT"][before - 1]
    )
    assert math.isclose(discarded, attempt["sink_kT"], rel_tol=1e-12, abs_tol=1e-12)
    release = meta["osmotic"]["lysis"]
    observed = []
    if chosen["lysed_at_birth"]:
        assert meta["end"]["status"] == "lysed" and stop["slots_after"] == []
        assert not counts[after, vesicle].any()
        observed.append(check_release(places, rows, "place_count", before, after, release, chosen))
    else:
        assert release is None
        assert stop["slots_after"] == [
            {"slot": 0, "key": chosen["key"], "counts": chosen["counts"]}
        ]
        assert counts[after, vesicle].tolist() == chosen["counts"]
        checked_pool_change(places, rows, "place_count", before, after, {})
    (final_slot,) = diag["states"]["final"]["slots"]
    assert final_slot == {
        "slot": 0,
        "key": chosen["key"],
        "counts": counts[after, vesicle].tolist(),
    }
    outside = [d["key"] for d in daughters if d["slot"] is None and d["lysed_at_birth"]]
    return before, after, observed, outside


def population_birth(meta, diag, stop, rows, at_shear, by_key):
    places = meta["places"]
    assert diag["places"] == [p["name"] for p in places]
    vesicle = [p["index"] for p in vesicle_places(places)]
    # A parent changes key exactly once, even if several schedules share a timestamp or a
    # later daughter occupies a slot a previous release freed.
    splits = []
    for a in stop["attempts"]:
        if a["outcome"] == "split":
            s = a["slot"]
            (j,) = [
                j
                for j in at_shear["shear"]
                if j > 0
                and rows["slot_key"][j - 1, s] == a["key"]
                and rows["slot_key"][j, s] == a["daughters"][0]["key"]
            ]
            splits.append((a, j))
    before = last = splits[0][1]
    observed = []
    for attempt, split in splits:
        assert last <= split
        checked_pool_change(places, rows, "pool_count", last, split, {})
        last = split
        releases = []
        for d in attempt["daughters"]:
            slot, key = d["slot"], d["key"]
            assert rows["slot_key"][split, slot] == key
            assert rows["slot_count"][split, slot, vesicle].tolist() == d["counts"]
            if d["lysed_at_birth"]:
                release = by_key.pop(key)
                releases.append(release)
                j = last + 1
                assert j in at_shear["lysis"] and release["event"] == rows["row_event"][j]
                assert release["slot"] == slot and rows["slot_key"][last, slot] == key
                assert rows["slot_key"][j, slot] == -1 and not rows["slot_count"][j, slot].any()
                observed.append(check_release(places, rows, "pool_count", last, j, release, d))
                last = j
        for field, term in (
            ("heat_kT", "release_heat_kT"),
            ("reservoir_work_kT", "release_reservoir_work_kT"),
        ):
            assert math.isclose(
                attempt[field], sum(r[term] for r in releases), rel_tol=1e-12, abs_tol=1e-12
            )
    assert stop["pool_after"] == rows["pool_count"][last].tolist()
    live = [
        {"slot": i, "key": int(key), "counts": rows["slot_count"][last, i].tolist()}
        for i, key in enumerate(rows["slot_key"][last])
        if key >= 0
    ]
    assert stop["slots_after"] == live
    assert {s["key"] for s in live}.isdisjoint(r["key"] for r in observed)
    return before, last, observed, []


def read_birth(directory, *, archived_population=False):
    """Read every successful population shear, or the lineage fixture's final shear."""
    meta = json.loads((directory / "run.json").read_text())
    diag = json.loads((directory / "diagnostic.json").read_text())
    pop = meta["mode"] == "population"
    if archived_population and not pop:
        raise ValueError("--population-record requires a population run")
    if not archived_population:
        with np.load(directory / "diagnostic.npz") as events:
            assert not events["event_lysed"].any()
        (sole_stop,) = diag["shear_events"]
        assert sole_stop["time"] == meta["end"]["time"]
        if pop:
            assert diag["states"]["final"] == {
                "slots": sole_stop["slots_after"],
                "pool": sole_stop["pool_after"],
            }
    births = [r for r in diag.get("lyses", []) if r["at_birth"]]
    by_key = {r["key"]: r for r in births}
    assert len(by_key) == len(births)
    field = "pool_count" if pop else "place_count"
    columns = [
        "row_time",
        "row_kind",
        "row_event",
        "reservoir_supplied",
        "event_heat_kT",
        "reservoir_work_kT",
        field,
    ]
    columns += ["slot_count", "slot_key"] if pop else ["discarded_free_energy_kT"]
    with np.load(directory / "records.npz") as bundle:
        rows = {name: bundle[name] for name in columns}
    by_time = defaultdict(lambda: defaultdict(list))
    legend = meta["records"]["row_kind"]["legend"]
    for j, (time, kind) in enumerate(zip(rows["row_time"], rows["row_kind"], strict=True)):
        by_time[time][legend[str(kind)]].append(j)
    places = meta["places"]
    finite = [p for p in places if p["phase"] == "pool" and p["kind"] == "finite"]

    def pool(j):
        return {p["name"]: int(rows[field][j, p["index"]]) for p in finite}

    reports = []
    for stop in diag["shear_events"]:
        if not any(a["outcome"] == "split" for a in stop["attempts"]):
            continue
        at_shear = by_time[stop["time"]]
        if pop:
            before, after, receipts, outside = population_birth(
                meta, diag, stop, rows, at_shear, by_key
            )
        else:
            before, after, receipts, outside = lineage_birth(meta, diag, stop, rows, at_shear)
        total = Counter()
        for r in receipts:
            total.update(r["returned"])
        checked_pool_change(places, rows, field, before, after, total)
        reports.append(
            {
                "time_s": stop["time"],
                "schedule": stop["schedule"],
                "finite_before": pool(before),
                "finite_after": pool(after),
                "diagnostic_pool": "after returns" if pop else "before returns",
                "released_daughters": receipts,
                "unfollowed_ruptures": outside,
                "held_supply_change": {
                    p["name"]: int(
                        rows["reservoir_supplied"][after, p["index"]]
                        - rows["reservoir_supplied"][before, p["index"]]
                    )
                    for p in places
                    if p["phase"] == "pool" and p["kind"] == "held"
                },
            }
        )
    assert not by_key
    return reports


def compare(directory):
    cases = {}
    for mode, seed, held, daughters in (
        ("single_lineage", 9, False, 2),
        ("single_lineage", 9, True, 2),
        ("single_lineage", 1, False, 2),
        ("population", 1, False, 2),
        ("population", 1, True, 2),
        ("population", 2, True, 3),
    ):
        name = f"{mode}_{seed}_{'held' if held else 'finite'}"
        result = runner.run(birth_spec(mode, held, seed, daughters)).check()
        assert result.closure["holds"]
        records.write_run(directory / name, result)
        (cases[name],) = read_birth(directory / name)
        releases = cases[name]["released_daughters"]
        if daughters == 3:
            assert len(releases) == 2 and releases[0]["slot"] != releases[1]["slot"]
        elif mode == "population":
            assert len(releases) == 2 and releases[0]["slot"] == releases[1]["slot"]
            assert (
                releases[0]["key"] != releases[1]["key"]
                and releases[0]["returned"] != releases[1]["returned"]
            )
        elif seed == 9:
            assert len(releases) == 1
        else:
            assert not releases and cases[name]["unfollowed_ruptures"]
    return cases


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--population-record", type=Path, help="read an existing population bundle")
    group.add_argument("--output", type=Path, help="keep the six CPU run bundles here")
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    if args.population_record:
        results = read_birth(args.population_record, archived_population=True)
    elif args.output:
        results = compare(args.output)
    else:
        with TemporaryDirectory() as tmp:
            results = compare(Path(tmp))
    print(json.dumps(results, indent=2, allow_nan=False))
