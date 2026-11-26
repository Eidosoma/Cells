"""Generation inheritance on cells.model.assembly_lineages@2's saved bundles: each parent against the
next parent on the same path (analysis; D245's second reading, never called F12).

F12 compares a split's parent with its followed daughter just after it, so it sees only the split's
sampling: at a vesicle's real size a half split breaks only near four or fewer molecules a species
(the fuel note's §2.4), and a lineage that switches composition between fissions leaves no mark.
This reading compares the parent of each split with the parent of the lineage's next split, one
generation later, after the daughter's growth: a switch between fissions is a break here. It has
its own name, its own parameters and its own registration (D245); F12 stays as
validation/assembly_lineages/inheritance.py defines it (f12.py).

**What it shares with f12.py:** the bundle's reading and checks (f12.read, f12.boundaries), H's
species set (the experiment's declared amphiphiles, f12.amphiphile_places), the exact integer
decision of H > threshold (inheritance.inherited), the event's predicate (inheritance.certified_at,
here over generation marks) and the ends: extinction (lysis) is absorbing and negative unless
certified first, and a lineage that ends otherwise short of the window is censored.

**Marks.** For a lineage's splits s_1, s_2, ... with parents P_1, P_2, ..., the marks are
H(P_j, P_(j+1)) > threshold. The last split has no next parent. A future (futures.py) starts just
after a landmark split: its first mark compares the landmark's parent, which the future's index
carries, with its own first parent (`before`). A followed daughter that lyses at birth never
becomes a parent, so its split's parent is the sequence's last.

**PARAMETERS are provisional,** set equal to F12's numbers only as a starting point: the reading's
registration sets them (D245).
"""

import numpy as np

from validation.assembly_lineages import inheritance
from validation.assembly_lineages_v2 import f12

FORMAT = "cells.assembly_lineages_v2.generation_inheritance@1"
PARAMETERS = {"threshold": (9, 10), "window": 12, "run": 3, "min_gap": 0}


def marks(splits, chosen, *, before=None, threshold=PARAMETERS["threshold"]):
    """(marks, extinct_at_birth): each parent against the next parent, over the places `chosen`;
    before: the parent of the split just before the first (a future's landmark)."""
    parents = ([np.asarray(before)] if before is not None else []) + [
        s["parent_counts"] for s in splits
    ]
    at_birth = any(s["lysed_at_birth"] for s in splits)
    out = []
    for a, b in zip(parents, parents[1:], strict=False):
        mark = inheritance.inherited(np.asarray(a)[chosen], np.asarray(b)[chosen], threshold)
        if mark is None:
            break
        out.append(int(mark))
    return out, at_birth


def lineage(directory, *, amphiphiles=None, start=0, before=None, parameters=None):
    """Generation inheritance on one saved single-lineage bundle, from its `start`-th split on, as
    JSON data. At start k > 0 the first mark compares split k − 1's parent with split k's."""
    p = {**PARAMETERS, **(parameters or {})}
    record, arrays, lives, provenance = f12.read(directory)
    chosen, chosen_names = f12.amphiphile_places(record, provenance, amphiphiles)
    splits = f12.boundaries(record, arrays, lives)
    if before is None and start > 0:
        before = splits[start - 1]["parent_counts"]
    later = splits[start:]
    sequence, at_birth = marks(later, chosen, before=before, threshold=tuple(p["threshold"]))
    status = record["end"]["status"]
    extinct = at_birth or status == "lysed"
    return {
        "format": FORMAT,
        "bundle": str(directory),
        "qualifier": record["run"]["qualifier"],
        "places": chosen_names,
        "why": f12.WHY,
        "parameters": {**p, "threshold": {"strictly_above": f"{p['threshold'][0]}/"
                                          f"{p['threshold'][1]}"},
                       "marks": "each split's parent against the next split's parent on the "
                       "followed path; the last split has none",
                       "provisional": "set by the reading's own registration (D245)"},
        "start": start,
        "splits": len(later),
        "marks": sequence,
        "breaks": sequence.count(0),
        "end": {"status": status, "extinct": extinct, "lysed_at_birth": at_birth},
        **f12.verdict(sequence, extinct, window=p["window"], run=p["run"],
                      min_gap=p["min_gap"]),
    }  # fmt: skip


def futures(index_path, *, amphiphiles=None, parameters=None):
    """Generation inheritance for each landmark's futures, counted as f12.futures() counts F12."""
    return f12.tally(
        index_path,
        lambda bundle, landmark: lineage(bundle, amphiphiles=amphiphiles,
                                         before=landmark["parent_counts"], parameters=parameters),
        FORMAT,
    )  # fmt: skip
