"""The self-test's rows of the three flag paths (Amendment 2, item 5 (a) and readings 12 and 24). No
judge's plant covers them.

Each row alters an honest table so that a flag stands, and scores it four times: with the flag open,
and settled in each of the three ways. The tables are the fabricated ones, the settlements are
invented, and so is the margin that leaves an entry untested in the corner's row.
"""

from __future__ import annotations

import copy
import math

from . import constants as c
from . import plants, scoring
from .plants import Lazy
from .settlements import fabricated

ENDS = {None: c.INCONCLUSIVE, c.BY_THE_RULE: c.PASS, "fail": c.FAIL, "inconclusive": c.INCONCLUSIVE}


def part(registration, family):
    """The registration with one family alone, and the pool runs of its seed."""
    view = registration.part(family.consumer)
    view.runs = {
        name: run
        for name, run in view.runs.items()
        if run["family"] == family.name
        or (registration.is_pool(run) and run["seed_index"] == family.seed_index)
    }
    view.families = {family.name: family}
    view.by_consumer = {family.consumer: [family]}
    return view


def checks_of(records: dict, consumer: str, flag: str, entries: set, rule: str) -> list:
    """What a row must show, with its flag open (None) and settled in each way."""
    out = []
    for said, record in records.items():
        block = record["consumers"][consumer]
        held = {(e["run"], e["readout"]): e for e in record["entries"] if "by_rule" in e}
        wanted = rule if said == c.BY_THE_RULE else ENDS[said]
        how = "open" if said is None else f"settled, {said}"
        (item,) = record["flags_to_settle"] or (None,)
        out += [
            (
                f"{how}: the flag stands in the record",
                item is not None
                and item["id"] == flag
                and (item["settled"] or {}).get("counts_as") == said,
            ),
            (
                f"{how}: its entries, and no other, count so",
                set(held) == entries
                and all((e["outcome"], e["by_rule"]) == (wanted, rule) for e in held.values())
                and all(bool(e.get("pending")) is (said is None) for e in held.values()),
            ),
            (f"{how}: the consumer is {ENDS[said]}", block["verdict"] == ENDS[said]),
            (
                f"{how}: {'pending, and no pass' if said is None else 'nothing is pending'}",
                (block["state"] == c.PENDING) is (said is None)
                and bool(block["pending"]) is (said is None)
                and block["final"] is (said is not None),
            ),
        ]
    return out


def rows(registration, note, tables, c0, captures, planted, retry) -> list:
    """The three rows, each with its checks and whether all hold."""
    target = registration.profile["plant_targets"]
    assembly = registration.families[target["assembly"]]
    junctions = registration.families[target["junctions"]]
    out = []

    def run(name, where, consumer, what, must, view, alter, flag, entries, rule, again=None):
        held = tables[consumer]["runs"]
        made = Lazy({k: v for k, v in held.items() if k in view.runs})
        alter(made)
        table = {consumer: dict(tables[consumer], runs=dict(made))}

        def judged(settlements=None):
            found = plants.judge(
                view, note, table, c0, captures, planted, again, settlements=settlements
            )
            return found if again is None else found[1]

        records = {None: judged()}
        for said in c.COUNTS_AS:
            records[said] = judged(fabricated(records[None], counts_as=said))
        checks = checks_of(records, consumer, flag, entries, rule)
        out.append(
            {
                "row": name,
                "where": where,
                "consumer": consumer,
                "what": what,
                "must_be": must,
                "scores_as_stated": all(good for _, good in checks),
                "checks": [[what_, bool(good)] for what_, good in checks],
            }
        )

    middle, finest = assembly.runs[1], junctions.finest
    cell, gap = assembly.world.cells[0], "junction_K"

    def at_zero(runs):
        runs[middle]["rows"]["n_cell_K"][cell][0] = 5e-324

    run(
        "F1",
        "reading 12",
        assembly.consumer,
        f"{middle}: the row of n_cell_K at time 0, {cell}, set to 5e-324",
        "flagged, and the run's capacitor at best inconclusive until the flag is settled",
        part(registration, assembly),
        at_zero,
        f"{scoring.AT_ZERO}; {middle}; n_cell_K",
        {(middle, "capacitor")},
        c.PASS,
    )

    def between(runs):
        entry = runs[finest]
        entry["t"].insert(1, (entry["t"][0] + entry["t"][1]) / 2)
        for table in entry["rows"].values():
            for values in table.values():
                values.insert(1, values[0])
        entry["rows"][gap][junctions.world.junctions[0]][1] = math.nan

    run(
        "F2",
        "reading 24",
        junctions.consumer,
        f"{finest}: one more row between two compared times, whose {gap} is not a number",
        "flagged, and every entry that reads the series of the run at best inconclusive until the "
        "flag is settled",
        part(registration, junctions),
        between,
        f"{scoring.NOT_FINITE}; {finest}; rows.{gap}",
        {(finest, gap), (finest, "balance of cells, K")},
        c.PASS,
    )

    view = part(registration, junctions)
    view.margins = copy.deepcopy(registration.margins)
    view.margins["worlds"][junctions.world.name]["entries"]["heat_junction"]["ratio"] = 1e-12
    heat = "heat_junction"

    def corner(runs):
        for name, shift in zip(junctions.runs, (1, -11, 1), strict=True):
            runs[name]["rows"][heat][junctions.world.junctions[0]][60] += 2e-12 * shift

    run(
        "F3",
        "item 5 (a)",
        junctions.consumer,
        f"{junctions.name}: {heat} untested (an invented ratio), and errors of 1, -11 and 1 times "
        f"2e-12 in its three rungs: outside its window and above beta on the first triple",
        "inconclusive by order and flagged with its error, owed the retry, and what the retry's "
        "triple gives at best inconclusive until the flag is settled",
        view,
        corner,
        f"{scoring.CORNER}; {junctions.name}; {heat}",
        {(junctions.retry_name, heat)},
        c.NOT_TESTED,
        again=retry,
    )
    return out
