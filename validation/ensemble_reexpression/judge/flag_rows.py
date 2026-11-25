"""The self-test's rows of the four flag paths (Amendment 2: item 5 (a) and readings 12, 24 and 25).
No judge's plant covers them.

Each row makes a flag stand on honest tables, and scores them with the flag open and settled in each
way that its kind may count as. The tables are the fabricated ones, the settlements are invented,
and so is the margin that leaves an entry untested in the corner's row. Every other restart's
reload is confirmed by an invented settlement, so that the row's own flag decides.
"""

from __future__ import annotations

import copy
import math

from . import constants as c
from . import plants
from .plants import Lazy
from .settlements import ReloadsConfirmed, SettlementFault, Settlements, allowed, fabricated_data

ENDS = {None: c.INCONCLUSIVE, c.BY_THE_RULE: c.PASS, "fail": c.FAIL, "inconclusive": c.INCONCLUSIVE}


def part(registration, family, support=None):
    """The registration with one family alone, the pool runs of its seed, and a support run."""
    view = registration.part(family.consumer)
    view.runs = {
        name: run
        for name, run in view.runs.items()
        if run["family"] == family.name
        or name == support
        or (registration.is_pool(run) and run["role"] == "judged")
        and run["seed_index"] == family.seed_index
    }
    view.families = {family.name: family}
    view.by_consumer = {family.consumer: [family]}
    return view


def settled(record: dict, flag: str, said: str) -> Settlements:
    """Invented settlements of a record: the row's flag counts as said, and every other flag, a
    reload, is confirmed.
    """
    data, records = fabricated_data(record, c.BY_THE_RULE)
    for item in data["flags"]:
        if item["flag"] == flag:
            item["counts_as"] = said
    return Settlements(data, "fabricated", records)


def checks_of(records: dict, consumer: str, flag: str, entries: set, rule: str) -> list:
    """What a row must show, with its flag open (None) and settled in each way."""
    out = []
    for said, record in records.items():
        block = record["consumers"][consumer]
        held = {
            (e["run"], e["readout"]): e for e in record["entries"] if flag in e.get("flags", ())
        }
        wanted = rule if said == c.BY_THE_RULE else ENDS[said]
        how = "open" if said is None else f"settled, {said}"
        mine = [f for f in record["flags_to_settle"] if f["id"] == flag]
        others = [f for f in record["flags_to_settle"] if f["id"] != flag]
        out += [
            (
                f"{how}: the flag stands in the record, once, and every other one is settled",
                len(mine) == 1
                and (mine[0]["settled"] or {}).get("counts_as") == said
                and all(f["settled"] is not None for f in others),
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
    """The four rows, each with its checks and whether all hold."""
    target = registration.profile["plant_targets"]
    assembly = registration.families[target["assembly"]]
    junctions = registration.families[target["junctions"]]
    out = []

    def run(name, where, consumer, what, must, view, alter, flag, entries, rule, again=None):
        held = tables[consumer]["runs"]
        made = Lazy({k: v for k, v in held.items() if k in view.runs})
        alter(made)
        table = {consumer: dict(tables[consumer], runs=dict(made))}

        def judged(settlements):
            found = plants.judge(
                view, note, table, c0, captures, planted, again, settlements=settlements
            )
            return found if again is None else found[1]

        kind = flag.split("; ")[0]
        records = {None: judged(None if kind == c.RELOAD else ReloadsConfirmed())}
        for said in allowed(kind):
            records[said] = judged(settled(records[None], flag, said))
        checks = checks_of(records, consumer, flag, entries, rule)
        if kind == c.RELOAD:  # a reload is shown or not: it is no fail
            try:
                settled(records[None], flag, "fail")
                refused = False
            except SettlementFault:
                refused = True
            checks.append(("a settlement of it as a fail is refused", refused))
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
        f"{c.AT_ZERO}; {middle}; n_cell_K",
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
        f"{c.NOT_FINITE}; {finest}; rows.{gap}",
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
        f"{c.CORNER}; {junctions.name}; {heat}",
        {(junctions.retry_name, heat)},
        c.NOT_TESTED,
        again=retry,
    )

    support = target["restart"]
    owner = registration.restarted(registration.runs[support])
    family = registration.families[registration.runs[owner]["family"]]
    readouts = [f"restart {entry.name}" for entry in family.world.entries]
    run(
        "F4",
        "reading 25",
        family.consumer,
        f"{support}: honest, and its reload of a checkpoint not yet confirmed",
        "every passing entry of the restart at best inconclusive until the checker confirms the "
        "reload (by the rule) or says that the record does not show it (inconclusive)",
        part(registration, family, support),
        lambda runs: None,
        f"{c.RELOAD}; {support}; {owner}",
        {(owner, readout) for readout in readouts},
        c.PASS,
    )
    return out
