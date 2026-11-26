"""The relationship tables' writer, cells.relations@1 (src/cells/records/relations.py).

D200 and D202; docs/RELATIONSHIPS_DESIGN.md §1.2, §1.3 and §5. Host only: no world runs here. Each
claim is tested once, with a planted error it must catch (D187):
1. The key rule gives the design's own worked tables: GARD's single lineage and population mode
   (§5.3) and the tissue world with a division and a replacement (§5.4). Planted: one world counter
   in event order, the rule §1.5 rejects.
2. One descent shape (§6's row): a malformed descent is refused, with nothing written. Planted: a
   key held twice, a missing end reason, a daughter born before its parent ends, and five more
   (an event id held twice among them: ids are unique within a world, event ids included).
3. The files: every array loads with allow_pickle=False, text is fixed-width '<U', the rows come
   back as written, and equal tables give equal bytes in any row order. Planted: unsorted rows.
4. Derived rows: the descent edges are the lives' own; a caller's descent edge is refused, and the
   reader refuses saved descent edges that disagree with the lives. Planted: a wrong parent.
5. Weights point at records: a position outside the record, an undeclared record and a record
   missing from its file are refused.
6. The reader refuses tables changed after writing. Planted: a key changed in the archive, an
   object column, another format.
7. The writer imports no model family, operator or law: the standard library and numpy only.
"""

import ast
import dataclasses
import hashlib
import json
import math
import time
import zipfile
from pathlib import Path

import numpy as np
import pytest

from cells.records import relations as rel

ROOT = Path(__file__).resolve().parents[2]
WORLD = rel.qualifier("0" * 64)
FISSION = "cells.operator.size_threshold_fission@1"
CONTINUATION = "cells.operator.daughter_continuation@1"
LINEAGES = "cells.model.assembly_lineages@1"
EXCHANGE = "cells.exchange.reservoir_exchange@1"
PARTITION = "cells.operator.isopotential_partition@1"
REPLACEMENT = "cells.operator.scheduled_cell_replacement@1"
TISSUE = "cells.model.resolved_pump_tissue@3"


def _replace(row, **changes):
    return dataclasses.replace(row, **changes)


# ------------------------------------------------------------------ the design's worked worlds


def gard_keys(keys):
    """§5.3: one founder, two fissions, the first daughter followed each time (single lineage)."""
    a0, s0 = keys.open()
    (a1, s1), (a2, s2) = keys.split(s0, [True, False], continues=0)
    (a3, s3), (a4, s4) = keys.split(s1, [True, False], continues=0)
    return {"a0": (a0, s0), "a1": (a1, s1), "a2": (a2, s2), "a3": (a3, s3), "a4": (a4, s4)}


def population_keys(keys):
    """§5.3's population mode: every daughter lives; generations split in turn, by parent key."""
    a0, s0 = keys.open()
    (a1, s1), (a2, s2) = keys.split(s0, [True, True], continues=0)
    (a3, s3), (a4, s4) = keys.split(s1, [True, True], continues=0)
    (b1, _), (b2, _) = keys.split(s2, [True, True], continues=0)
    (a5, _), (a6, _) = keys.split(s3, [True, True], continues=0)
    return {"a2": s2, "a4": s4, "a2's daughters": (b1, b2), "the followed path": (a5, a6)}


def tissue_keys(keys):
    """§5.4: founders cell_0 and cell_1; division `first` makes c1 and c2; then newcomer n1."""
    out = {"cell_0": keys.open(), "cell_1": keys.open()}
    (out["c1"], out["c2"]) = keys.split(out["cell_0"][1], [True, True], continues=0)
    out["n1"] = keys.open()
    return out


class OneWorldCounter(rel.Keys):
    """Planted: one counter for the world, in event order (the option §1.5 rejects)."""

    def __init__(self):
        super().__init__()
        self.count = 0

    def open(self):
        self.count += 1
        return rel.key(0, self.count - 1), 0

    def split(self, lineage, lives_on, continues=0):
        out = []
        for _ in lives_on:
            self.count += 1
            out.append((rel.key(0, self.count - 1), 0))
        return out


def text(keyed):
    return {name: (rel.key_text(k), s) for name, (k, s) in keyed.items()}


def test_the_key_rule_gives_the_designs_tables():
    gard = {"a0": ("0:0", 0), "a1": ("0:1", 0), "a2": ("0:2", -1), "a3": ("0:3", 0)}
    gard["a4"] = ("0:4", -1)
    assert text(gard_keys(rel.Keys())) == gard
    population = population_keys(rel.Keys())
    assert (population["a2"], population["a4"]) == (1, 2)
    assert [rel.key_text(k) for k in population["a2's daughters"]] == ["1:1", "1:2"]
    assert [rel.key_text(k) for k in population["the followed path"]] == ["0:5", "0:6"]
    tissue = {"cell_0": ("0:0", 0), "cell_1": ("1:0", 1), "c1": ("0:1", 0), "c2": ("0:2", 2)}
    tissue["n1"] = ("3:0", 3)
    assert text(tissue_keys(rel.Keys())) == tissue
    # Planted: one world counter keeps GARD's single lineage, but not the population's followed
    # path (§1.5) nor the tissue's newcomer.
    assert text(gard_keys(OneWorldCounter()))["a3"] == ("0:3", 0)
    planted = population_keys(OneWorldCounter())
    assert [rel.key_text(k) for k in planted["the followed path"]] != ["0:5", "0:6"]
    assert text(tissue_keys(OneWorldCounter()))["n1"] != ("3:0", 3)


# ------------------------------------------------------------------ worlds as rows


def gard_world():
    """§5.3's GARD lineage as rows: keys from the kernel's rule, two fissions at t1 and t2."""
    k = gard_keys(rel.Keys())
    t1, t2 = 3.0, 7.5
    life = dict(declared_by=CONTINUATION, root="carrier:a0")
    f1, f2 = "event:fission/1", "event:fission/2"
    lives = [
        rel.Life("carrier:a0", *k["a0"], 0.0, "founder", t1, "divided", 0, "carrier:a0", LINEAGES,
                 slot="slot:0", end_event=f1),
        rel.Life("carrier:a1", *k["a1"], t1, "division", t2, "divided", 1, **life, slot="slot:0",
                 parent="carrier:a0", share=0.625, birth_event=f1, end_event=f2),
        rel.Life("carrier:a2", *k["a2"], t1, "division", t1, "not_followed", 1, **life,
                 parent="carrier:a0", share=0.375, birth_event=f1, end_event=f1),
        rel.Life("carrier:a3", *k["a3"], t2, "division", t2, "censored", 2, **life, slot="slot:0",
                 parent="carrier:a1", share=0.5, birth_event=f2),
        rel.Life("carrier:a4", *k["a4"], t2, "division", t2, "not_followed", 2, **life,
                 parent="carrier:a1", share=0.5, birth_event=f2, end_event=f2),
    ]  # fmt: skip
    agent = "source:unmodelled_agent"
    events = [
        rel.Event(f1, t1, "fission", FISSION, False, at="carrier:a0", source=agent),
        rel.Event(f2, t2, "fission", FISSION, False, at="carrier:a1", source=agent),
    ]
    nodes = [rel.Node("slot:0", "slot", LINEAGES), rel.Node("sink:discard", "sink", CONTINUATION)]
    sources = [
        rel.Source("source:reservoir", "reservoir", "substrate", EXCHANGE, carries="t0,t1",
                   record="joined_total"),
        rel.Source(agent, "unmodelled", "energy", FISSION, payer_of="fission_work_kT"),
    ]  # fmt: skip
    edges = [
        rel.Edge("supplies", "source:reservoir", "slot:0", EXCHANGE, species="t1",
                 weight_record="joined_total", weight_index="1,0", mode="one_way"),
        rel.Edge("removes_to", "carrier:a2", "sink:discard", CONTINUATION, event=f1,
                 species="t1", weight_record="discarded_total", weight_index="1,0", mode="event"),
    ]  # fmt: skip
    shapes = {"joined_total": (5, 2, 1), "discarded_total": (5, 2, 1), "fission_work_kT": (5, 1)}
    records = one_file(shapes, times="row_time", file="records.npz")
    return dict(
        world=WORLD,
        lives=lives,
        events=events,
        nodes=nodes,
        sources=sources,
        edges=edges,
        records=records,
    )


def tissue_world():
    """§5.4's tissue world as rows: a division at 2 ms and a template newcomer at 3 ms, in one
    world (the format's shape; the engine admits them as two worlds today)."""
    k = tissue_keys(rel.Keys())
    first, r1 = "event:division/first", "event:replacement/n1"
    end = 0.004
    lives = [
        rel.Life("carrier:cell_0", *k["cell_0"], 0.0, "founder", 0.002, "divided", 0,
                 "carrier:cell_0", PARTITION, slot="slot:cell_0", end_event=first),
        rel.Life("carrier:cell_1", *k["cell_1"], 0.0, "founder", 0.003, "replaced", 0,
                 "carrier:cell_1", REPLACEMENT, slot="slot:cell_1", end_event=r1),
        rel.Life("carrier:c1", *k["c1"], 0.002, "division", end, "censored", 1, "carrier:cell_0",
                 PARTITION, slot="slot:d1", parent="carrier:cell_0", share=0.5, birth_event=first),
        rel.Life("carrier:c2", *k["c2"], 0.002, "division", end, "censored", 1, "carrier:cell_0",
                 PARTITION, slot="slot:d2", parent="carrier:cell_0", share=0.5, birth_event=first),
        rel.Life("carrier:n1", *k["n1"], 0.003, "template", end, "censored", 0, "carrier:n1",
                 REPLACEMENT, slot="slot:cell_1", predecessor="carrier:cell_1", birth_event=r1),
    ]  # fmt: skip
    events = [
        rel.Event(first, 0.002, "division", PARTITION, True, step=2, at="carrier:cell_0"),
        rel.Event(r1, 0.003, "replacement", REPLACEMENT, True, step=3, at="slot:cell_1",
                  source="source:template/T1"),
    ]  # fmt: skip
    nodes = [rel.Node(f"slot:{c}", "slot", TISSUE) for c in ("cell_0", "cell_1", "d1", "d2")]
    nodes.append(rel.Node("sink:waste", "sink", REPLACEMENT))
    sources = [
        rel.Source("source:template/T1", "template", "intervention", REPLACEMENT, carries="K",
                   record="replacement_supplied_fmol"),
    ]  # fmt: skip
    edges = [
        rel.Edge("supplies", "source:template/T1", "slot:cell_1", REPLACEMENT, event=r1,
                 species="K", weight_record="replacement_supplied_fmol", weight_index="0,1",
                 mode="event"),
    ]  # fmt: skip
    records = one_file(
        {"replacement_supplied_fmol": (5, 1, 4)}, times="accepted_times", file="trajectory.npz"
    )
    return dict(world=WORLD, lives=lives, events=events, nodes=nodes, sources=sources,
                edges=edges, records=records)  # fmt: skip


# Each record file's rows' times: GARD's bundle saves its start, then each fission's parent and
# daughter rows at the fission's time (fissions at 3 and 7.5); the tissue run saves every 1 ms step.
TIMES = {
    "row_time": np.array([0.0, 3.0, 3.0, 7.5, 7.5]),
    "accepted_times": np.array([0.0, 0.001, 0.002, 0.003, 0.004]),
}


def one_file(shapes, *, times, file):
    """Cumulative records saved in one file, {name: record}."""
    return {
        name: {
            "array": name,
            "times": times,
            "kind": "cumulative",
            "shape": list(shape),
            "files": [{"file": file, "rows": [0, shape[0]]}],
        }
        for name, shape in shapes.items()
    }


def record_files(directory, world):
    """The run's record files that a world's records name: each record zero-filled over each of
    its files' rows, beside the rows' times."""
    by_file = {}
    for entry in world["records"].values():
        for part in entry["files"]:
            start, stop = part["rows"]
            arrays = by_file.setdefault(part["file"], {})
            arrays[entry["array"]] = np.zeros((stop - start, *entry["shape"][1:]))
            arrays[entry["times"]] = TIMES[entry["times"]][start:stop]
    for name, arrays in by_file.items():
        (directory / name).parent.mkdir(parents=True, exist_ok=True)
        np.savez(directory / name, **arrays)


def written(tmp_path, world, name="run"):
    directory = tmp_path / name
    directory.mkdir()
    record_files(directory, world)
    rel.write(directory, **world)
    return directory


def refused(world, *words):
    """The writer refuses `world`, and the refusal names each of `words`."""
    with pytest.raises(rel.RelationsRefused) as caught:
        rel.tables(**world)
    for word in words:
        assert word in str(caught.value), str(caught.value)
    return str(caught.value)


# ------------------------------------------------------------------ 2. one descent shape


def _life(world, name):
    return next(i for i, x in enumerate(world["lives"]) if x.id == f"carrier:{name}")


def _with_life(world, name, **changes):
    world = dict(world, lives=list(world["lives"]))
    i = _life(world, name)
    world["lives"][i] = _replace(world["lives"][i], **changes)
    return world


PLANTED_DESCENT = {
    # §6's three: a key duplicated across two mechanisms, a missing end reason, a daughter born
    # before its parent ends.
    "a key held twice": (lambda w: _with_life(w, "n1", key=rel.key(0, 1)), "is unique"),
    "a missing end reason": (lambda w: _with_life(w, "c1", end_reason=""), "end_reason"),
    "a daughter born before its parent ends": (
        lambda w: _with_life(w, "cell_0", end_time=0.0025),
        "born where its parent ended",
    ),
    "a daughter drawing another sub-lineage": (
        lambda w: _with_life(w, "c2", key=rel.key(1, 1)),
        "draws a count of its parent's sub-lineage",
    ),
    "a gap in a sub-lineage's counts": (
        lambda w: _with_life(w, "c2", key=rel.key(0, 3)),
        "with no gap",
    ),
    "a sub-lineage opened twice": (lambda w: _with_life(w, "c2", lineage=3), "opened once"),
    "a replaced life without its successor": (
        lambda w: _with_life(w, "n1", predecessor="", birth_kind="template"),
        "replaced by exactly one newcomer",
    ),
    "an event id held twice": (
        lambda w: dict(w, events=[*w["events"], w["events"][0]]),
        "events event:division/first: its id is unique",
    ),
}


def test_the_design_worlds_are_accepted_as_they_stand():
    for world in (gard_world(), tissue_world()):
        descriptor, arrays = rel.tables(**world)
        assert descriptor["format"] == rel.FORMAT and "status" not in descriptor
        assert descriptor["tables"]["lives"]["rows"] == 5


@pytest.mark.parametrize("plant", sorted(PLANTED_DESCENT))
def test_a_malformed_descent_is_refused(plant, tmp_path):
    change, rule = PLANTED_DESCENT[plant]
    world = change(tissue_world())
    refused(world, rule)
    directory = tmp_path / "run"
    directory.mkdir()
    record_files(directory, world)
    with pytest.raises(rel.RelationsRefused):
        rel.write(directory, **world)
    assert sorted(p.name for p in directory.iterdir()) == ["trajectory.npz"]  # Nothing written.


def test_an_unfollowed_daughter_has_no_slot_and_ends_at_its_birth():
    world = gard_world()
    rel.tables(**world)
    refused(_with_life(world, "a2", slot="slot:0"), "unfollowed daughter")
    refused(_with_life(world, "a4", end_time=9.0), "unfollowed daughter")


def test_nothing_is_overwritten(tmp_path):
    directory = written(tmp_path, tissue_world())
    before = (directory / rel.ARRAYS).read_bytes()
    with pytest.raises(rel.RelationsRefused, match="exists"):
        rel.write(directory, **tissue_world())
    assert (directory / rel.ARRAYS).read_bytes() == before


# ------------------------------------------------------------------ 3. the files


def test_the_files_load_without_pickle_and_repeat_byte_for_byte(tmp_path, monkeypatch):
    world = gard_world()
    a = written(tmp_path, world, "a")
    with np.load(a / rel.ARRAYS, allow_pickle=False) as saved:
        arrays = {name: saved[name] for name in saved.files}
    descriptor = json.loads((a / rel.DESCRIPTOR).read_text())
    for entry in descriptor["tables"].values():
        for column in entry["columns"]:
            array = arrays[column["array"]]
            assert array.shape == (entry["rows"],)
            kind = {"text": "U", "int64": "i", "float64": "f", "bool": "b"}[column["type"]]
            assert array.dtype.kind == kind and array.dtype.kind != "O"
            if kind == "U":
                assert array.dtype.str.startswith("<U")
    _, rows = rel.read(a)
    by_key = sorted(world["lives"], key=lambda x: x.key)
    assert [rel._row_key(x) for x in rows["lives"]] == [rel._row_key(x) for x in by_key]
    assert [r.id for r in rows["events"]] == ["event:fission/1", "event:fission/2"]
    # The same tables in reversed row order, written later: the same bytes.
    time.sleep(2.1)  # Past a zip timestamp's 2 s resolution.
    reverse = {k: v[::-1] if isinstance(v, list) else v for k, v in world.items()}
    b = written(tmp_path, reverse, "b")
    for name in (rel.ARRAYS, rel.DESCRIPTOR):
        assert (a / name).read_bytes() == (b / name).read_bytes(), name
    # Planted: rows kept in the order given.
    monkeypatch.setattr(rel, "_sort_key", lambda table, row: 0)
    c = written(tmp_path, reverse, "c")
    assert (a / rel.ARRAYS).read_bytes() != (c / rel.ARRAYS).read_bytes()


# ------------------------------------------------------------------ 4. derived rows


def test_the_descent_edges_are_the_lives_own(tmp_path):
    world = tissue_world()
    _, arrays = rel.tables(**world)
    edges = {
        (str(r), str(f), str(t), str(e))
        for r, f, t, e in zip(
            arrays["edges.relation"],
            arrays["edges.from"],
            arrays["edges.to"],
            arrays["edges.event"],
            strict=True,
        )
        if str(r) in rel.DESCENT
    }
    first, r1 = "event:division/first", "event:replacement/n1"
    assert edges == {
        ("parent_of", "carrier:cell_0", "carrier:c1", first),
        ("parent_of", "carrier:cell_0", "carrier:c2", first),
        ("precedes_in_slot", "carrier:cell_1", "carrier:n1", r1),
        ("occupies", "carrier:cell_0", "slot:cell_0", ""),
        ("occupies", "carrier:cell_1", "slot:cell_1", ""),
        ("occupies", "carrier:c1", "slot:d1", first),
        ("occupies", "carrier:c2", "slot:d2", first),
        ("occupies", "carrier:n1", "slot:cell_1", r1),
    }
    own = rel.Edge("parent_of", "carrier:cell_0", "carrier:c1", PARTITION, mode="event")
    refused(dict(world, edges=[*world["edges"], own]), "descent edges are derived")
    carrier = rel.Node("carrier:x", "carrier", PARTITION)
    refused(dict(world, nodes=[*world["nodes"], carrier]), "are derived")
    # Planted: a saved parent_of edge that names the wrong parent.
    directory = written(tmp_path, world)
    with np.load(directory / rel.ARRAYS, allow_pickle=False) as saved:
        arrays = {name: saved[name] for name in saved.files}
    descriptor = json.loads((directory / rel.DESCRIPTOR).read_text())
    rel.validate(descriptor, arrays, directory)
    froms = arrays["edges.from"].tolist()
    i = next(
        i
        for i, (r, t) in enumerate(zip(arrays["edges.relation"], arrays["edges.to"], strict=True))
        if str(r) == "parent_of" and str(t) == "carrier:c2"
    )
    froms[i] = "carrier:cell_1"
    arrays["edges.from"] = np.asarray(froms, dtype=arrays["edges.from"].dtype)
    with pytest.raises(rel.RelationsInvalid, match="descent edges are those the lives give"):
        rel.validate(descriptor, arrays, directory)


# ------------------------------------------------------------------ 5. weights point at records


def test_weights_point_at_declared_records_in_their_files(tmp_path):
    world = gard_world()
    edge, other = world["edges"]
    refused(dict(world, edges=[_replace(edge, weight_index="2,0"), other]), "gives one position")
    refused(dict(world, edges=[_replace(edge, weight_index="1"), other]), "gives one position")
    undeclared = _replace(edge, weight_record="left_total")
    refused(dict(world, edges=[undeclared, other]), "left_total is declared")
    refused(dict(world, edges=[_replace(edge, weight=1.0), other]), "not both")
    amount = dict(world["records"], fission_work_kT=dict(world["records"]["fission_work_kT"]))
    amount["fission_work_kT"]["kind"] = "amount"
    refused(dict(world, records=amount), "fission_work_kT is a declared cumulative record")
    gap = {k: dict(v) for k, v in world["records"].items()}
    gap["joined_total"]["files"] = [{"file": "records.npz", "rows": [1, 5]}]
    refused(dict(world, records=gap), "each from where the last stopped")
    directory = tmp_path / "run"
    directory.mkdir()
    np.savez(
        directory / "records.npz", joined_total=np.zeros((5, 2, 1)), row_time=TIMES["row_time"]
    )
    with pytest.raises(rel.RelationsRefused, match="holds discarded_total"):
        rel.write(directory, **world)  # Two records are not in the file.
    assert sorted(p.name for p in directory.iterdir()) == ["records.npz"]


def test_a_record_names_its_times_and_files_in_row_order(tmp_path):
    """A windowed run's records lie in chunks: records_in reads them, the writer checks every
    chunk, and an event's weight needs the record's rows on both sides of it (EVENT_ROWS)."""
    world = gard_world()
    chunks = ["chunks/window-0.npz", "chunks/window-1.npz"]
    for entry in world["records"].values():
        entry["files"] = [{"file": chunks[0], "rows": [0, 3]}, {"file": chunks[1], "rows": [3, 5]}]
    directory = written(tmp_path, world)
    kinds = dict.fromkeys(world["records"], "cumulative")
    assert rel.records_in(directory, chunks, kinds, times="row_time") == world["records"]
    _, rows = rel.read(directory)
    assert len(rows["edges"]) == len(rel.tables(**world)[1]["edges.relation"])
    # Planted: rows whose times fall.
    falling = tmp_path / "falling"
    falling.mkdir()
    record_files(falling, world)
    with np.load(falling / chunks[1]) as saved:
        arrays = dict(saved)
    arrays["row_time"] = np.array([7.5, 2.0])
    np.savez(falling / chunks[1], **arrays)
    with pytest.raises(rel.RelationsRefused, match="its times are finite and never fall"):
        rel.write(falling, **world)
    # Planted: an event after the record's last row.
    late = tmp_path / "late"
    late.mkdir()
    record_files(late, world)
    events = [
        _replace(e, time=e.time + 10.0) if e.id == "event:fission/2" else e for e in world["events"]
    ]
    moved = dict(world, events=events)
    moved["lives"] = [
        _replace(x, **{f: getattr(x, f) + 10.0 for f in ("birth_time", "end_time")
                       if getattr(x, f) == 7.5})
        for x in world["lives"]
    ]  # fmt: skip
    removes = _replace(world["edges"][1], from_="carrier:a4", event="event:fission/2")
    moved["edges"] = [world["edges"][0], removes]
    rel.tables(**moved)
    with pytest.raises(rel.RelationsRefused, match="has a row at or after its event's time"):
        rel.write(late, **moved)


# ------------------------------------------------------------------ 6. the reader's check


def _saved(directory):
    with np.load(directory / rel.ARRAYS, allow_pickle=False) as saved:
        arrays = {name: saved[name] for name in saved.files}
    return json.loads((directory / rel.DESCRIPTOR).read_text()), arrays


def test_the_reader_refuses_tables_changed_after_writing(tmp_path):
    directory = written(tmp_path, gard_world())
    descriptor, arrays = _saved(directory)
    rel.validate(descriptor, arrays, directory)
    keys = arrays["lives.key"].copy()
    keys[-1] = keys[0]  # Planted: a key held twice.
    with pytest.raises(rel.RelationsInvalid, match="is unique"):
        rel.validate(descriptor, dict(arrays, **{"lives.key": keys}))
    ids = arrays["lives.id"].astype(object)  # Planted: an object column.
    with pytest.raises(rel.RelationsInvalid, match="little-endian text"):
        rel.validate(descriptor, dict(arrays, **{"lives.id": ids}))
    with pytest.raises(rel.RelationsInvalid, match="its format"):
        rel.validate(dict(descriptor, format="cells.relations@0"), arrays)
    # The prose may be reworded within a version (and a file from before the label was lifted
    # carries a status); a machine field may not change. Planted: a column's type.
    rel.validate(dict(descriptor, status="provisional", ids="reworded", sorted="reworded"), arrays)
    retyped = json.loads(json.dumps(descriptor))
    (column,) = [c for c in retyped["tables"]["lives"]["columns"] if c["name"] == "share"]
    column["type"] = "int64"
    with pytest.raises(rel.RelationsInvalid, match="machine fields"):
        rel.validate(retyped, arrays)
    tampered = tmp_path / "tampered"
    tampered.mkdir()
    record_files(tampered, gard_world())
    (tampered / rel.DESCRIPTOR).write_text((directory / rel.DESCRIPTOR).read_text())
    with zipfile.ZipFile(tampered / rel.ARRAYS, "w") as archive:  # An object array, pickled.
        for name, array in dict(arrays, **{"lives.id": ids}).items():
            with archive.open(name + ".npy", "w") as stream:
                np.lib.format.write_array(stream, array, allow_pickle=True)
    with pytest.raises(ValueError, match="allow_pickle"):
        rel.read(tampered)


def test_the_world_is_a_run_qualifier():
    """The qualifier of {fingerprint, start}, and of a stop when a run stopped early: the same
    canonical JSON every family digests (GARD's records name it), and an unstopped run's stays the
    qualifier of {fingerprint, start} alone."""

    def digest(body):
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()

    branch = {"checkpoint": "cd", "time": 1.5}
    stop = {"events": 12, "fissions": 3}
    assert rel.qualifier("ab") == rel.qualifier("ab", stop=None)
    assert rel.qualifier("ab") == digest({"definition": "ab", "start": "fresh"})
    assert rel.qualifier("ab", branch, stop) == digest(
        {"definition": "ab", "start": branch, "stop": stop}
    )
    named = {rel.qualifier("ab"), rel.qualifier("ac"), rel.qualifier("ab", branch)}
    named |= {rel.qualifier("ab", stop=stop), rel.qualifier("ab", stop=dict(stop, events=13))}
    assert len(named) == 5
    refused(dict(tissue_world(), world="w"), "run qualifier")
    for start, stopped in (
        ({"checkpoint": "cd"}, None),
        ("fresh", {}),
        ("fresh", {"events": "12"}),
    ):
        with pytest.raises(rel.RelationsRefused):
            rel.qualifier("ab", start, stopped)


# ------------------------------------------------------------------ 7. no engine imports

ALLOWED = {"hashlib", "json", "math", "re", "zipfile", "dataclasses", "pathlib", "numpy"}


def imported(source):
    """The top-level packages a module's text imports."""
    out = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            out.add("." if node.level else node.module.split(".")[0])
    return out


def test_the_writer_imports_no_engine_code():
    source = (ROOT / "src" / "cells" / "records" / "relations.py").read_text()
    assert imported(source) <= ALLOWED, imported(source) - ALLOWED
    assert imported(source + "\nfrom cells.models import pump_composite\n") - ALLOWED == {"cells"}
    assert math.isnan(rel.Life.__dataclass_fields__["share"].default)
