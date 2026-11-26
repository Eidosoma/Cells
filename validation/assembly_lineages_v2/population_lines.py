"""F12 and generation inheritance along the lines of a cells.model.assembly_lineages@2 population (R4;
analysis, not engine physics; the lead's rulings of 20 November 2026).

In a population every daughter lives, so descent branches, while F12 is defined along one line.
This module reads a saved population bundle (run.json, records.npz, relations@2 and the manifest's
provenance) and never runs the engine. It reads lines three ways, as the lead ruled (R4a):
- **(a) survivors' lines of descent:** the line of every life alive at a declared time, traced back
  to its founder. These are the only long lines under transfers, so they are conditioned on
  survival, and the output says so: transfers sample uniformly and add no bias of composition,
  but lines that divide more are over-represented, so selection is part of this reading;
- **(b) uniform descent, exactly:** from each state, every path of its descendants weighted by the
  product of 1/k over its splits (each daughter of a split with probability 1/k), summed into the
  weights of a certified, a negative and a censored line. No random draw is made. It is the
  unconditioned reading, and it measures how much a transfer's removal censors;
- **(d) the pooled rates:** every boundary's mark, counted over the population, as the baseline.
(c), population futures, waits for OL9 to register a per-state population readout.

**Marks.** F12's reading (f12.py): at each split on a line, the parent just before it against
that line's daughter just after it. The generation reading (generation_inheritance.py, D245, never
called F12): each parent on the line against the next parent on it. Both decide H in exact integers
over the experiment's declared amphiphiles (D245; f12.amphiphile_places): an undeclared set is
refused. A daughter's counts in the fission table repeat the pool, which H never reads.

**Ends** (R4b, R4c): lysis is extinction (absorbing; a daughter lysed at birth leaves no mark of
its own); a transfer's removal censors a line and never extinguishes it; so does the run's end, a
`slots_full` end included, which censors every live line.

**The window** starts at a declared start generation or a declared time (R4d), never a default:
from a start generation g, a line's window opens with the split of its life of generation g; from
a start time t, with the first split of its life alive at t. A line that ends inside the window,
uncertified and not extinct, is censored. Both are recorded in the output.

**Shared prefixes** (R4e): each survivor's line reports, for every other, the last generation the
two share, and the output gives the generation where all of them merge. Independence is counted
by runs, never by lines.

**Checks** against relations@2, each a refusal when it fails: each split's parent ends `divided`
at `event:fission/<row>`; each daughter is a life born by division of it, in the slot the table
records; and the daughters' membrane and lumen counts sum to the parent's. A run resumed from a
checkpoint (rung P) is refused: joining its segments is not built.
"""

import json
from pathlib import Path

import numpy as np

from validation.assembly_lineages import inheritance
from validation.assembly_lineages_v2 import f12, generation_inheritance

FORMAT = "cells.assembly_lineages_v2.population_lines@1"
SPLIT = 0  # division.POPULATION_OUTCOMES' index of "split", checked against the legend
CONDITIONING = (
    "lines of the lives alive at the declared time: conditioned on survival. Transfers sample "
    "uniformly and add no bias of composition, but lines that divide more are over-represented, "
    "so selection is part of this reading. Lines share their past: independence is counted by "
    "runs, never by lines"
)
ENDS = {"lysed": "extinct", "removed": "censored", "censored": "censored", "divided": None}


def read(directory):
    """(run.json, arrays, lives by id, provenance) of a saved population bundle."""
    from cells.models.assembly_lineages_v2 import records
    from cells.records import relations

    _, record, arrays = records.read(directory)
    _, tables = relations.read(directory)
    provenance = json.loads((Path(directory) / "manifest.json").read_text())["provenance"]
    if record.get("mode") != "population":
        raise f12.BundleMismatch("Population lines read population bundles; f12.py reads lines")
    if record["run"]["start"] != "fresh":
        raise f12.BundleMismatch("A run resumed from a checkpoint: joining segments is not built")
    return record, arrays, {life.id: life for life in tables["lives"]}, provenance


def splits(record, arrays, lives):
    """{parent life id: {row, time, parent_counts, daughters: [{life, counts, lysed_at_birth}]}}
    for every split, checked against the relations (module docstring)."""
    if "fission_outcome" not in arrays:
        return {}
    legend = record["records"]["fission_outcome"]["legend"]
    if legend.get(str(SPLIT)) != "split":
        raise f12.BundleMismatch(f"The bundle's outcome legend is not division's: {legend}")
    vesicle = [p["index"] for p in record["places"] if p["phase"] in ("membrane", "lumen")]
    out = {}
    for r in np.flatnonzero(arrays["fission_outcome"] == SPLIT).tolist():
        k = int(arrays["fission_k"][r])
        parent = lives.get(f12._carrier(int(arrays["fission_parent"][r])))
        if (
            parent is None
            or parent.end_reason != "divided"
            or (parent.end_event != f"event:fission/{r}")
        ):
            raise f12.BundleMismatch(f"Split {r}: the parent's life does not end divided at it")
        counts = arrays["fission_parent_counts"][r]
        daughters = arrays["fission_daughter_counts"][r][:k]
        if not np.array_equal(daughters[:, vesicle].sum(axis=0), counts[vesicle]):
            raise f12.BundleMismatch(
                f"Split {r}: the daughters' vesicles do not sum to the parent's"
            )
        rows = []
        for j in range(k):
            life = lives.get(f12._carrier(int(arrays["fission_daughters"][r][j])))
            slot = f"slot:{int(arrays['fission_daughter_slots'][r][j])}"
            if (
                life is None
                or life.birth_kind != "division"
                or life.parent != parent.id
                or (life.slot != slot)
            ):
                raise f12.BundleMismatch(
                    f"Split {r}: daughter {j} is not a life of the parent in {slot}"
                )
            rows.append(
                {
                    "life": life.id,
                    "counts": daughters[j],
                    "lysed_at_birth": bool(arrays["fission_lysed_at_birth"][r][j]),
                }
            )
        out[parent.id] = {
            "row": r,
            "time": float(arrays["fission_time"][r]),
            "parent_counts": counts,
            "daughters": rows,
        }
    return out


def _split_mark(parent_counts, daughter, chosen):
    """F12's mark of one boundary, or None where it leaves none (lysed at birth; empty)."""
    if daughter["lysed_at_birth"]:
        return None
    mark = inheritance.inherited(parent_counts[chosen], daughter["counts"][chosen])
    return None if mark is None else int(mark)


def _generation_mark(parent_split, child_split, chosen, threshold):
    """The generation reading's mark from a parent's split to its daughter's own split."""
    mark = inheritance.inherited(
        parent_split["parent_counts"][chosen], child_split["parent_counts"][chosen], threshold
    )
    return None if mark is None else int(mark)


def _end(life):
    """'extinct' or 'censored' for the end of a life that did not divide."""
    if life.end_reason not in ENDS or ENDS[life.end_reason] is None:
        raise f12.BundleMismatch(f"{life.id}: a line cannot end with {life.end_reason!r}")
    return ENDS[life.end_reason]


def _starts(lives, start_generation, start_time):
    """The states the window opens at: lives of the start generation, or lives alive at the start
    time (R4d). Exactly one of the two is declared."""
    if (start_generation is None) == (start_time is None):
        raise ValueError("Declare a start generation or a start time (R4d), exactly one")
    if start_generation is not None:
        return sorted(
            life.id for life in lives.values() if life.generation == int(start_generation)
        )
    t = float(start_time)
    return sorted(
        life.id
        for life in lives.values()
        if life.birth_time <= t
        and (t < life.end_time or (life.end_reason == "censored" and t <= life.end_time))
    )


def _alive_at(lives, time):
    return sorted(
        life.id
        for life in lives.values()
        if life.birth_time <= time
        and (time < life.end_time or (life.end_reason == "censored" and time <= life.end_time))
    )


def _line(lives, life_id):
    """[founder, ..., life]: the life's line of descent."""
    out = [life_id]
    while lives[out[-1]].parent:
        out.append(lives[out[-1]].parent)
    return out[::-1]


def _marks_on(line, by_parent, chosen, threshold, until):
    """(split marks, generation marks, extinct) along a line of life ids, from its first life's
    split to its last life's birth; a generation mark needs the next life's own split, at or
    before `until`."""
    split_marks, generation_marks, extinct = [], [], False
    for i in range(len(line) - 1):
        s = by_parent[line[i]]
        daughter = next(d for d in s["daughters"] if d["life"] == line[i + 1])
        mark = _split_mark(s["parent_counts"], daughter, chosen)
        if mark is None:
            extinct = daughter["lysed_at_birth"]
            break
        split_marks.append(mark)
    for i in range(len(line) - 1):
        if line[i + 1] not in by_parent or by_parent[line[i + 1]]["time"] > until:
            break
        mark = _generation_mark(by_parent[line[i]], by_parent[line[i + 1]], chosen, threshold)
        if mark is None:
            break
        generation_marks.append(mark)
    return split_marks, generation_marks, extinct


def _verdicts(split_marks, generation_marks, extinct, parameters):
    w, r, g = inheritance.WINDOW, inheritance.RUN, inheritance.MIN_GAP
    return {
        "f12": f12.verdict(split_marks, extinct, window=w, run=r, min_gap=g),
        "generation_inheritance": f12.verdict(
            generation_marks,
            extinct,
            window=parameters["window"],
            run=parameters["run"],
            min_gap=parameters["min_gap"],
        ),
    }


def survivors_lines(
    lives, by_parent, chosen, *, at_time, start_generation=None, start_time=None, parameters=None
):
    """(a): the lines of the lives alive at `at_time`, each read from its window's start."""
    p = {**generation_inheritance.PARAMETERS, **(parameters or {})}
    survivors = _alive_at(lives, at_time)
    starts = set(_starts(lives, start_generation, start_time))
    lines = {s: _line(lives, s) for s in survivors}
    out = []
    for s, line in lines.items():
        opened = next((i for i, life in enumerate(line) if life in starts), None)
        row = {"survivor": s, "line": line, "opens_at": None if opened is None else line[opened]}
        if opened is None:  # the window's state is not on this line (it was born after it)
            row.update(
                {"f12": None, "generation_inheritance": None, "marks": [], "generation_marks": []}
            )
        else:
            sm, gm, extinct = _marks_on(
                line[opened:], by_parent, chosen, tuple(p["threshold"]), at_time
            )
            row.update({"marks": sm, "generation_marks": gm, **_verdicts(sm, gm, extinct, p)})
        row["shared"] = {
            other: _last_shared(line, lines[other], lives) for other in lines if other != s
        }
        out.append(row)
    merged = None
    if lines:
        first = min(len(line) for line in lines.values())
        shared = [i for i in range(first) if len({line[i] for line in lines.values()}) == 1]
        merged = lives[next(iter(lines.values()))[shared[-1]]].generation if shared else None
    return out, merged


def _last_shared(a, b, lives):
    """The generation of the last life two lines share, or None (different founders)."""
    last = None
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        last = lives[x].generation
    return last


def uniform_descent(lives, by_parent, chosen, state, *, parameters=None):
    """(b): from a state (a life), the exact weights of a uniformly chosen line of its descendants
    being certified, negative (and of that, extinct) or censored (and of that, by a transfer's
    removal), under F12's and the generation reading's marks."""
    p = {**generation_inheritance.PARAMETERS, **(parameters or {})}
    window = {"f12": inheritance.WINDOW, "generation_inheritance": p["window"]}
    totals = {
        name: {"certified": 0.0, "negative": 0.0, "extinct": 0.0, "censored": 0.0, "removed": 0.0}
        for name in window
    }

    def settle(name, marks, extinct, end_reason, weight):
        got = f12.verdict(
            marks,
            extinct,
            window=window[name],
            run=inheritance.RUN if name == "f12" else p["run"],
            min_gap=inheritance.MIN_GAP if name == "f12" else p["min_gap"],
        )
        t = totals[name]
        t[got["verdict"]] += weight
        if got["verdict"] == "negative" and extinct:
            t["extinct"] += weight
        if got["verdict"] == "censored" and end_reason == "removed":
            t["removed"] += weight

    def walk(life_id, split_marks, generation_marks, weight, previous_split, done):
        """done: the readings already settled on this path."""
        life = lives[life_id]
        s = by_parent.get(life_id)
        if previous_split is not None and s is not None and "generation_inheritance" not in done:
            mark = _generation_mark(previous_split, s, chosen, tuple(p["threshold"]))
            if mark is not None:
                generation_marks = generation_marks + [mark]
        for name, marks in (("f12", split_marks), ("generation_inheritance", generation_marks)):
            if name in done:
                continue
            certified = (
                inheritance.certified_at(
                    marks,
                    window[name],
                    inheritance.RUN if name == "f12" else p["run"],
                    inheritance.MIN_GAP if name == "f12" else p["min_gap"],
                )
                > 0
            )
            if certified or len(marks) >= window[name]:
                settle(name, marks, False, None, weight)
                done = done | {name}
        if len(done) == 2:
            return
        if s is None:  # the line ends with this life: extinct, or censored
            end = _end(life)
            for name, marks in (("f12", split_marks), ("generation_inheritance", generation_marks)):
                if name not in done:
                    settle(name, marks, end == "extinct", life.end_reason, weight)
            return
        share = weight / len(s["daughters"])
        for daughter in s["daughters"]:
            mark = _split_mark(s["parent_counts"], daughter, chosen)
            if mark is None:  # lysed at birth: extinct here, with no mark
                for name, marks in (
                    ("f12", split_marks),
                    ("generation_inheritance", generation_marks),
                ):
                    if name not in done:
                        settle(name, marks, True, "lysed", share)
                continue
            walk(
                daughter["life"],
                split_marks + [mark] if "f12" not in done else split_marks,
                generation_marks,
                share,
                s,
                done,
            )

    walk(state, [], [], 1.0, None, frozenset())
    return totals


def pooled(by_parent, chosen, *, parameters=None):
    """(d): every boundary's mark over the population, counted, under both readings."""
    p = {**generation_inheritance.PARAMETERS, **(parameters or {})}
    split_marks, generation_marks = [], []
    for s in by_parent.values():
        for daughter in s["daughters"]:
            mark = _split_mark(s["parent_counts"], daughter, chosen)
            if mark is not None:
                split_marks.append(mark)
            child = by_parent.get(daughter["life"])
            if child is not None:
                g = _generation_mark(s, child, chosen, tuple(p["threshold"]))
                if g is not None:
                    generation_marks.append(g)
    return {
        "f12_boundaries": len(split_marks),
        "f12_inherited": int(sum(split_marks)),
        "generation_boundaries": len(generation_marks),
        "generation_inherited": int(sum(generation_marks)),
    }


def population(
    directory, *, at_time, start_generation=None, start_time=None, amphiphiles=None, parameters=None
):
    """R4 on one saved population bundle, as JSON data: (a) survivors' lines at `at_time` (a time,
    or "end": the run's end, declared), (b) uniform descent from each start state, and (d) the
    pooled rates."""
    record, arrays, lives, provenance = read(directory)
    chosen, chosen_names = f12.amphiphile_places(record, provenance, amphiphiles)
    by_parent = splits(record, arrays, lives)
    when = float(record["end"]["time"]) if at_time == "end" else float(at_time)
    lines, merged = survivors_lines(
        lives,
        by_parent,
        chosen,
        at_time=when,
        start_generation=start_generation,
        start_time=start_time,
        parameters=parameters,
    )
    states = _starts(lives, start_generation, start_time)
    descent = {
        s: uniform_descent(lives, by_parent, chosen, s, parameters=parameters) for s in states
    }
    return {
        "format": FORMAT,
        "bundle": str(directory),
        "qualifier": record["run"]["qualifier"],
        "places": chosen_names,
        "why": f12.WHY,
        "status": record["end"]["status"],
        "window": {
            "start_generation": start_generation,
            "start_time": start_time,
            "f12": inheritance.parameters(),
            "generation_inheritance": {**generation_inheritance.PARAMETERS, **(parameters or {})},
        },
        "survivors": {
            "at_time": when,
            "conditioning": CONDITIONING,
            "lines": lines,
            "all_merge_at_generation": merged,
            "independent_runs": 1,
        },
        "uniform_descent": descent,
        "pooled": pooled(by_parent, chosen, parameters=parameters),
        "ends": {
            "lysed": "extinct",
            "removed": "censored (never extinct)",
            "censored": "censored (the run's end, slots_full included)",
        },
    }
