"""F12 on cells.model.assembly_lineages@2's saved bundles: a lineage's inheritance marks from its fission
table and its relations, and the break-and-renewal event (analysis, not engine physics).

It reads a single-lineage division bundle (records.write_run's: records.npz, run.json and
manifest.json, with relations.json and relations.npz) and never runs the engine. F12 is exactly
@1's, imported unchanged from validation/assembly_lineages/inheritance.py: at each split, the
parent just before it against the followed daughter just after it, inherited when H > 9/10
strictly (decided in exact integers), and the event a break followed strictly later by three
consecutive inherited boundaries within twelve (`certified_at`). @1's `lineage_marks` reads @1's
two-daughter `fission_split`, which @2's k-daughter table does not have, hence this reader. A
second reading, each parent against the next parent, has its own name and parameters and is never
F12 (D245): generation_inheritance.py.

**Boundaries.** Every split of the lineage, in order: a row of the fission table whose outcome is
`split`. A refused attempt (the stress, volume or floor test) is not a boundary.

**H's species set is the experiment's declared amphiphiles** (D245): the membrane's amphiphiles
only, never a building block or a spent form that also sits in the membrane, since counting them
would raise similarity. A world's builder declares the set, and its runs carry it in their
provenance (manifest.json's `amphiphiles`); a caller may pass it instead, and the two must agree.
A bundle with no declared set is refused, as is a set naming a species outside the membrane. The
lumen's solutes are split by volume and are not an inherited identity, and the pool is shared.

**Ends** (the plan's R2 and R3, as the lead ruled on 20 November 2026):
- lysis is extinction: absorbing, and negative unless the event was certified before it. A
  followed daughter that lyses at birth leaves no counted boundary, as the preprint's empty
  daughter is "neither a fission nor an inheritance break";
- a lineage that ends otherwise (its horizon, its event guard, the capacity) with fewer marks than
  the window and no certification is censored, not negative: @2 has no fission-count horizon.

**Verdicts:** `certified` (at a boundary, 1-based), `negative` (the window complete without it, or
extinct first) or `censored`. They are counted and reported; how censored futures and refused
landmarks enter an estimate is OL9's registration's to decide (the lead's ruling), so nothing here
folds them into a probability.

**Checks** against relations@2, each a refusal when it fails: the parent of every split ends
`divided` at `event:fission/<row>`; the followed daughter is a life born by division of that
parent, under its key; the daughters' membrane and lumen counts sum to the parent's (the pool is
repeated in every daughter, so it is left out); and each split's parent is the previous split's
followed daughter. Population bundles are refused: which paths F12 follows there waits for a
ruling (the plan's R4).
"""

import json
from pathlib import Path

import numpy as np

from validation.assembly_lineages import inheritance

FORMAT = "cells.assembly_lineages_v2.f12@1"
SPLIT = 0  # division.OUTCOMES' index of "split", checked against the bundle's legend
WHY = (
    "H is taken over the experiment's declared amphiphiles in the membrane (D245): the assembly's "
    "own composition, never a building block or spent form that also sits there; the lumen's "
    "solutes are split by volume and are not an inherited identity, and the pool is shared"
)


class BundleMismatch(ValueError):
    """A bundle whose fission table and relations disagree, or that this reader cannot read."""


def _carrier(key):
    return f"carrier:a{int(key)}"


def read(directory):
    """(run.json, arrays, lives by id, the run's provenance) of a saved bundle, checked by
    records.read's manifest and by relations.read."""
    from cells.models.assembly_lineages_v2 import records
    from cells.records import relations

    _, record, arrays = records.read(directory)
    _, tables = relations.read(directory)
    manifest = json.loads((Path(directory) / "manifest.json").read_text())
    return record, arrays, {life.id: life for life in tables["lives"]}, manifest["provenance"]


def amphiphile_places(record, provenance, amphiphiles=None):
    """(indices, names) of the membrane places of the declared amphiphiles (module docstring)."""
    stated = provenance.get("amphiphiles")
    if amphiphiles is None and stated is None:
        raise BundleMismatch(
            "The bundle declares no amphiphile set and none is given: H's species set is declared "
            "per experiment (D245)"
        )
    if amphiphiles is not None and stated is not None and sorted(amphiphiles) != sorted(stated):
        raise BundleMismatch(
            f"The amphiphiles given, {amphiphiles}, are not the bundle's, {stated}"
        )
    declared = list(amphiphiles if amphiphiles is not None else stated)
    membrane = {p["species"]: p for p in record["places"] if p["phase"] == "membrane"}
    unknown = sorted(set(declared) - set(membrane))
    if not declared or unknown:
        raise BundleMismatch(f"Not a set of the membrane's species: {declared} (unknown {unknown})")
    chosen = sorted((membrane[s] for s in set(declared)), key=lambda p: p["index"])
    return [p["index"] for p in chosen], [p["name"] for p in chosen]


def boundaries(record, arrays, lives):
    """The lineage's splits in order, checked against its relations: [{row, time, parent,
    daughter, followed, parent_counts, daughter_counts, lysed_at_birth}] (counts over every
    place)."""
    if record.get("mode") != "single_lineage" or "division" not in record:
        raise BundleMismatch(
            "This reader reads single-lineage division bundles; a population's paths wait for a "
            "ruling"
        )
    legend = record["records"]["fission_outcome"]["legend"]
    if legend.get(str(SPLIT)) != "split":
        raise BundleMismatch(f"The bundle's outcome legend is not division's: {legend}")
    vesicle = [p["index"] for p in record["places"] if p["phase"] in ("membrane", "lumen")]
    out = []
    for r in np.flatnonzero(arrays["fission_outcome"] == SPLIT).tolist():
        followed = int(arrays["fission_followed"][r])
        parent = int(arrays["fission_parent"][r])
        daughter = int(arrays["fission_daughters"][r][followed])
        parent_counts = arrays["fission_parent_counts"][r]
        daughters = arrays["fission_daughter_counts"][r][: int(arrays["fission_k"][r])]
        if not np.array_equal(daughters[:, vesicle].sum(axis=0), parent_counts[vesicle]):
            raise BundleMismatch(f"Split {r}: the daughters' vesicles do not sum to the parent's")
        life = lives.get(_carrier(parent))
        if life is None or life.end_reason != "divided" or life.end_event != f"event:fission/{r}":
            raise BundleMismatch(f"Split {r}: the parent's life does not end divided at it")
        child = lives.get(_carrier(daughter))
        if child is None or child.birth_kind != "division" or child.parent != life.id:
            raise BundleMismatch(f"Split {r}: the followed daughter is not a life of the parent")
        if out and out[-1]["daughter"] != parent:
            raise BundleMismatch(f"Split {r}: its parent is not the previous followed daughter")
        out.append({
            "row": r, "time": float(arrays["fission_time"][r]), "parent": parent,
            "daughter": daughter, "followed": followed, "parent_counts": parent_counts,
            "daughter_counts": daughters[followed],
            "lysed_at_birth": bool(arrays["fission_lysed_at_birth"][r][followed]),
        })  # fmt: skip
    return out


def marks(splits, chosen):
    """(marks, extinct_at_birth): F12's marks over the places `chosen` (indices). A followed
    daughter lysed at birth ends the sequence with no mark of its own."""
    out = []
    for s in splits:
        if s["lysed_at_birth"]:
            return out, True
        mark = inheritance.inherited(s["parent_counts"][chosen], s["daughter_counts"][chosen])
        if mark is None:  # no declared amphiphile on one side: not a boundary
            return out, False
        out.append(int(mark))
    return out, False


def verdict(sequence, extinct, *, window, run, min_gap):
    """{verdict, certified_at}: certified (at a 1-based boundary), negative (the window complete,
    or extinct before certification) or censored (fewer marks, not extinct)."""
    at = inheritance.certified_at(sequence, window, run, min_gap)
    if at:
        return {"verdict": "certified", "certified_at": at}
    if extinct or len(sequence) >= window:
        return {"verdict": "negative", "certified_at": 0}
    return {"verdict": "censored", "certified_at": 0}


def lineage(directory, *, amphiphiles=None, start=0):
    """F12 on one saved single-lineage bundle, from its `start`-th split on (0: the whole lineage;
    k: the state just after split k − 1), as JSON data."""
    record, arrays, lives, provenance = read(directory)
    chosen, chosen_names = amphiphile_places(record, provenance, amphiphiles)
    later = boundaries(record, arrays, lives)[start:]
    sequence, at_birth = marks(later, chosen)
    status = record["end"]["status"]
    extinct = at_birth or status == "lysed"
    return {
        "format": FORMAT,
        "bundle": str(directory),
        "qualifier": record["run"]["qualifier"],
        "places": chosen_names,
        "why": WHY,
        "parameters": inheritance.parameters(),
        "start": start,
        "splits": len(later),
        "marks": sequence,
        "breaks": sequence.count(0),
        "end": {"status": status, "extinct": extinct, "lysed_at_birth": at_birth},
        **verdict(sequence, extinct, window=inheritance.WINDOW, run=inheritance.RUN,
                  min_gap=inheritance.MIN_GAP),
    }  # fmt: skip


def futures(index_path, *, amphiphiles=None):
    """F12 for each landmark's futures (futures.py's index), counted: certified, negative (of which
    extinct), censored, and the same counts for each half of its words (the branch halves), with
    the refused landmarks listed. No estimate is formed (OL9's registration decides)."""
    return tally(index_path, lambda bundle, landmark: lineage(bundle, amphiphiles=amphiphiles),
                 FORMAT)  # fmt: skip


def tally(index_path, read_future, fmt):
    """Each landmark's futures read by `read_future(bundle, landmark)`, counted (futures())."""
    index = json.loads(Path(index_path).read_text())
    out = {"format": fmt, "index": str(index_path), "landmarks": [],
           "refused": index.get("refused", [])}  # fmt: skip
    for landmark in index["landmarks"]:
        rows = []
        for future in landmark["futures"]:
            got = read_future(future["bundle"], landmark)
            rows.append({"word": future["word"], "verdict": got["verdict"],
                         "certified_at": got["certified_at"], "extinct": got["end"]["extinct"],
                         "marks": got["marks"]})  # fmt: skip
        rows.sort(key=lambda row: row["word"])
        half = len(rows) // 2
        out["landmarks"].append({
            "split": landmark["split"], "time": landmark["time"], "futures": len(rows),
            "counts": counts(rows), "halves": [counts(rows[:half]), counts(rows[half:])],
            "rows": rows,
        })  # fmt: skip
    return out


def counts(rows):
    verdicts = [row["verdict"] for row in rows]
    return {
        "certified": verdicts.count("certified"),
        "negative": verdicts.count("negative"),
        "extinct_negative": sum(
            1 for row in rows if row["verdict"] == "negative" and row["extinct"]
        ),  # fmt: skip
        "censored": verdicts.count("censored"),
    }
