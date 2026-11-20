"""F12, generation inheritance and restored futures on cells.assembly_lineages@2's saved bundles
(validation/assembly_lineages_v2: f12.py, generation_inheritance.py, futures.py and worlds.py;
the lead's rulings of 20 November 2026 and D245).

Each claim with a planted error it must catch (D187):
- F1: F12's marks are each split's parent against its followed daughter, by @1's exact predicate;
  a daughter lysed at birth ends the sequence with no mark; the verdicts are certified, negative
  (the window complete, or extinct first) and censored (planted: the other daughter's marks);
- F2: generation inheritance is its own reading, each parent against the next parent, with its
  own format, and a switch of composition between fissions is a break there and not in F12
  (planted: the daughter compared in place of the next parent gives F12's marks);
- F3: H's species set is the declared amphiphiles: an undeclared set, a species outside the
  membrane and a set that disagrees with the bundle's are refused (planted: a block species in
  the membrane is not read);
- F4: a future's definition changes only its founder, schedules, horizon, observations and branch
  word; its word is unique per (landmark, future); a landmark with no shear time after it is
  refused; the rate tables agree at the landmark (planted: a changed potential is refused; a
  dropped pool changes the rate table);
- F5: on saved bundles, a natural lineage of a held-amphiphile world with catalysed joins reads
  under both readings, its post-fission landmarks match its fission table, and its futures run,
  pass their checks and are counted, while its last landmark, with no shear time after it, is
  recorded as refused (planted: a parent whose counts no longer sum is refused).

World-compiling cost: one program (a natural lineage and two futures of one structure, one lane),
61-69 s for the whole file, local and unmeasured: on CPU 23 at a machine load near 34, not on the
timed lane. Most of it is the osmotic verdict that every osmotic world pays once per process.
Reason: the reader's contract is the saved bundle's format, and the futures' checks are the runs'
own.
"""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from validation.assembly_lineages import inheritance
from validation.assembly_lineages_v2 import f12, futures, generation_inheritance, worlds

ENTRIES, _ = worlds.catalysis(2, law="uniform", seed=20261120, p=1.0, low=0.0, high=2.0)


def split(parent, daughter, *, lysed=False):
    return {"parent_counts": np.asarray(parent), "daughter_counts": np.asarray(daughter),
            "lysed_at_birth": lysed}  # fmt: skip


def test_f12_marks_are_the_split_s_and_its_verdicts():
    chosen = [0, 1]
    # 100 (P.D)^2 > 81 (P.P)(D.D): (10, 10) against (5, 5) is inherited, against (9, 1) is not.
    same, broken = split([10, 10, 3], [5, 5, 3]), split([10, 10, 3], [9, 1, 3])
    sequence, at_birth = f12.marks([broken, same, same, same], chosen)
    assert sequence == [0, 1, 1, 1] and not at_birth
    assert f12.verdict(sequence, False, window=12, run=3, min_gap=0) == {
        "verdict": "certified",
        "certified_at": 4,
    }
    lysed = split([4, 4, 0], [2, 2, 0], lysed=True)
    sequence, at_birth = f12.marks([broken, same, lysed, same], chosen)
    assert sequence == [0, 1] and at_birth  # a daughter lysed at birth: no mark, and the end
    assert f12.verdict(sequence, True, window=12, run=3, min_gap=0)["verdict"] == "negative"
    assert f12.verdict([1] * 12, False, window=12, run=3, min_gap=0)["verdict"] == "negative"
    assert f12.verdict([0, 1], False, window=12, run=3, min_gap=0)["verdict"] == "censored"
    # Planted: the unfollowed daughter (the parent less the followed one) gives another mark:
    # (12, 4) against (8, 0) is inherited, against (4, 4) it is not.
    uneven = split([12, 4, 0], [8, 0, 0])
    other = split([12, 4, 0], [4, 4, 0])
    assert f12.marks([uneven], chosen)[0] == [1] and f12.marks([other], chosen)[0] == [0]


def test_generation_inheritance_is_its_own_reading():
    chosen = [0, 1]
    # The lineage switches between fissions: each daughter is like its parent, but the next
    # parent, grown from it, is not.
    splits = [split([10, 10, 0], [5, 5, 0]), split([20, 2, 0], [10, 1, 0]),
              split([21, 3, 0], [10, 2, 0])]  # fmt: skip
    assert f12.marks(splits, chosen)[0] == [1, 1, 1]
    sequence, _ = generation_inheritance.marks(splits, chosen)
    assert sequence == [0, 1]  # (10, 10) against (20, 2); (20, 2) against (21, 3)
    assert generation_inheritance.marks(splits, chosen, before=[2, 20, 0])[0] == [0, 0, 1]
    # Planted: the daughter in place of the next parent is F12's reading, not this one.
    planted = [int(inheritance.inherited(s["parent_counts"][chosen], s["daughter_counts"][chosen]))
               for s in splits]  # fmt: skip
    assert planted != sequence
    assert "f12" not in generation_inheritance.FORMAT
    lysed = [splits[0], split([20, 2, 0], [10, 1, 0], lysed=True)]
    assert generation_inheritance.marks(lysed, chosen) == ([0], True)


def test_the_amphiphile_set_is_declared():
    record = {"places": [
        {"index": 0, "name": "B@pool", "species": "B", "phase": "pool"},
        {"index": 1, "name": "A0@membrane", "species": "A0", "phase": "membrane"},
        {"index": 2, "name": "B@membrane", "species": "B", "phase": "membrane"},
        {"index": 3, "name": "A1@membrane", "species": "A1", "phase": "membrane"},
        {"index": 4, "name": "I@lumen", "species": "I", "phase": "lumen"},
    ]}  # fmt: skip
    stated = {"amphiphiles": ["A1", "A0"]}
    assert f12.amphiphile_places(record, stated) == ([1, 3], ["A0@membrane", "A1@membrane"])
    assert f12.amphiphile_places(record, {}, ["A0"]) == ([1], ["A0@membrane"])
    with pytest.raises(f12.BundleMismatch, match="declares no amphiphile set"):
        f12.amphiphile_places(record, {})
    with pytest.raises(f12.BundleMismatch, match="not the bundle's"):
        f12.amphiphile_places(record, stated, ["A0"])
    with pytest.raises(f12.BundleMismatch, match="unknown"):
        f12.amphiphile_places(record, {}, ["A0", "I"])
    # Planted: the block B, which sits in the membrane, is never read unless declared.
    assert 2 not in f12.amphiphile_places(record, stated)[0]


def definition(pool, times, horizon):
    w = worlds.world(types=2, pool=pool, held_mM=100.0, pool_counts=20, membrane=8,
                     entries=ENTRIES)  # fmt: skip
    return worlds.definition(w, schedules=[worlds.shear(0, times=list(times))], horizon=horizon,
                             molecules=2048, row_every=200, chunk=64)  # fmt: skip


def test_a_future_changes_only_what_the_rule_allows():
    natural = definition("finite", (1.0, 2.0, 3.0, 4.0), 4.5)
    spec = parse_spec(natural)
    world = spec.model.world
    counts = np.asarray(world.founder)
    counts[world.place_index("A0@membrane")] += 3
    landmark = {"time": 2.0, "counts": counts.tolist()}
    future = futures.definition(natural, landmark, futures.word(5, 1, 4))
    assert future["experiment"]["schedules"][0]["times_s"] == [1.0, 2.0]
    assert future["experiment"]["time_horizon_s"] == 2.5
    assert future["execution"]["stream"]["branch"] == 1 + 5 * 4 + 1
    assert (
        future["model"]["world"]["founder"]["A0@membrane"]
        == counts[world.place_index("A0@membrane")]
    )
    assert len({futures.word(s, f, 4) for s in range(6) for f in range(4)}) == 24
    with pytest.raises(ValueError, match="natural run"):
        futures.word(0, 0, 4, natural_branch=1)
    with pytest.raises(futures.LandmarkRefused, match="no time after the landmark"):
        futures.definition(natural, {"time": 4.0, "counts": counts.tolist()}, 1)
    planted = copy.deepcopy(future)  # Planted: a changed potential is refused.
    planted["model"]["world"]["species"][0]["standard_mu_RT"]["bilayer"] = -2.5
    with pytest.raises(ValueError, match="changes only"):
        futures.check_definition(natural, planted)
    fspec = parse_spec(future)
    start = np.asarray(fspec.model.world.founder)
    assert futures.rates_agree(spec, counts, fspec, start) == (True, 0.0)
    dropped = start.copy()  # Planted: the pool dropped from the founder.
    for name in ("A0@pool", "A1@pool"):
        dropped[world.place_index(name)] = 0
    assert not futures.rates_agree(spec, counts, fspec, dropped)[0]


def test_a_lineage_its_readers_and_its_futures_on_saved_bundles(tmp_path):
    from cells.models.assembly_lineages_v2 import records, runner

    natural = definition("held", (1.0, 2.0, 3.0), 3.5)
    run = runner.run(parse_spec(natural)).check()
    declared = {"amphiphiles": worlds.amphiphiles(natural["model"]["world"])}
    records.write_run(tmp_path / "natural", run, provenance={"operation": "test", **declared})
    first = f12.lineage(tmp_path / "natural")
    second = generation_inheritance.lineage(tmp_path / "natural")
    assert first["splits"] == second["splits"] >= 2
    assert first["places"] == ["A0@membrane", "A1@membrane"]
    assert len(second["marks"]) == first["splits"] - 1
    record, arrays, lives, _ = f12.read(tmp_path / "natural")
    marks = futures.landmarks(tmp_path / "natural")
    assert [m["split"] for m in marks] == [s["row"] for s in f12.boundaries(record, arrays, lives)]
    last = marks[-1]
    splits = [marks[0]["split"]] + ([last["split"]] if last["time"] >= 3.0 else [])
    index = futures.run(tmp_path / "natural", tmp_path / "futures", splits=splits,
                        per_landmark=2, lanes=1)  # fmt: skip
    assert len(index["landmarks"]) == 1 and len(index["landmarks"][0]["futures"]) == 2
    refused = [r["split"] for r in index["refused"] if "no time after" in r["reason"]]
    assert refused == splits[1:]  # the last landmark has no shear time after it
    for f in index["landmarks"][0]["futures"]:
        assert f["rates_largest_relative_difference"] <= futures.RTOL
        provenance = json.loads((Path(f["bundle"]) / "manifest.json").read_text())["provenance"]
        assert provenance["amphiphiles"] == declared["amphiphiles"]
        assert provenance["landmark"]["split"] == marks[0]["split"]
    for reader in (f12, generation_inheritance):
        counted = reader.futures(tmp_path / "futures" / "futures.json")["landmarks"][0]["counts"]
        assert counted["certified"] + counted["negative"] + counted["censored"] == 2
    # Planted: a parent whose counts no longer sum to its daughters' is refused.
    arrays = dict(arrays)
    arrays["fission_parent_counts"] = arrays["fission_parent_counts"].copy()
    arrays["fission_parent_counts"][marks[0]["split"], world_place(record, "A0@membrane")] += 1
    with pytest.raises(f12.BundleMismatch, match="do not sum"):
        f12.boundaries(record, arrays, lives)


def world_place(record, name):
    return next(p["index"] for p in record["places"] if p["name"] == name)
