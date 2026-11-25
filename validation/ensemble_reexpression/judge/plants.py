"""The judge's plants JP1 to JP24 (PLANTS section 6): altered copies of honest tables, and what each must score.

A plant alters rows only, or the one leaf that it names. Each is scored by the code that scores the registered tables.
"""

from __future__ import annotations

import copy
import math

import numpy as np

from . import constants as c
from . import scoring
from .legacy import Captures
from .registration import Registration, StringsNote
from .table import TableSet

H1, H2, H3 = (f"jupiter_baseline h={h!r}" for h in (2.5e-05, 1.25e-05, 6.25e-06))
R1, R2, R3 = (f"jupiter_pump_release h={h!r}" for h in (2.5e-05, 1.25e-05, 6.25e-06))
I1, I2, I3 = (f"integrated h={h!r}" for h in (0.0001, 5e-05, 2.5e-05))
CLASS_S_SERIES = (
    "n_cell_Na n_cell_K n_cell_Cl n_out_Na n_out_K n_out_Cl leak_Na leak_K leak_Cl channel_K junction_Na junction_K junction_Cl "
    "face_Na face_K face_Cl pump gate_m gate_h junction_gate heat_junction heat_face"
).split()
HEATS = ("heat_leak", "heat_pump", "heat_channel")


class Query:
    """What a plant's checks ask of a record."""

    def __init__(self, record: dict):
        self.record = record
        self.entries = record["entries"]

    def find(self, **wanted) -> list:
        """The judged entries that have these values."""
        return [e for e in self.entries if e["judged"] and all(e.get(k) == v for k, v in wanted.items())]

    def outcome(self, **wanted):
        """The outcome of the one judged entry that has these values."""
        found = self.find(**wanted)
        return found[0]["outcome"] if len(found) == 1 else f"{len(found)} entries"

    def fails(self) -> list:
        """Every failing entry, as (run, readout)."""
        return [(e["run"], e["readout"]) for e in self.entries if e["judged"] and e["outcome"] == c.FAIL]

    def run(self, name) -> dict:
        """A run's state."""
        return self.record["runs"][name]

    def verdict(self, consumer) -> str:
        """A consumer's verdict."""
        return self.record["consumers"][consumer]["verdict"]

    def blind(self) -> dict:
        """`base`'s blind set."""
        return self.record["consumers"]["base"]["sets"]["blind"]

    def plant(self, name) -> str:
        """An engine plant's score."""
        return next(p["score"] for p in self.record["plants"]["plants"] if p["plant"] == name)


def scaled(values, factor):
    """A row times a factor."""
    return [v * factor for v in values]


def largest(table) -> float:
    """The largest magnitude of a series, over its entities."""
    return max(abs(v) for values in table.values() for v in values)


def refuse(entry, kind, message, rows=True):
    """Make an entry a refused one of a kind. Without rows, as a refusal before any accepted row."""
    entry["status"] = "refused"
    entry["refusal"] = {"kind": kind, "message": message, "time_s": 0.01 if kind == "check" else None}
    if not rows:
        entry.update(t=[], rows={}, potential_t=[], potentials={})


class Plant:
    """One judge's plant: the consumer whose table it alters, the alteration, and its checks."""

    def __init__(self, name, consumer, what, must, alter, check):
        self.name, self.consumer, self.what, self.must, self.alter, self.check = name, consumer, what, must, alter, check


def all_balances(q: Query, runs, species, cells=(), regions=()):
    """True where the balances of these cells and regions fail in each of the runs."""
    good = True
    for run in runs:
        if cells:
            found = q.find(run=run, readout=f"balance of cells, {species}")
            good &= len(found) == 1 and found[0]["outcome"] == c.FAIL and all(found[0]["by_entity"][k] > 1 for k in cells)
        if regions:
            found = q.find(run=run, readout=f"balance of regions, {species}")
            good &= len(found) == 1 and found[0]["outcome"] == c.FAIL and all(found[0]["by_entity"][k] > 1 for k in regions)
    return good


def judged_readouts(q: Query, run, family=None):
    """True where a refused run's readouts are judged: its R entries and, in its family, the S entries are formed."""
    R = [e for e in q.find(run=run, **{"class": "R"})]
    S = [e for e in q.find(family=family, **{"class": "S"})] if family else []
    formed = [e for e in R + S if e["outcome"] != c.NOT_FORMED]
    return bool(formed) and len(formed) == len(R + S)


def nothing_judged(q: Query, run, family):
    """True where nothing of a run is judged, and its family's S entries are not formed."""
    own = [e for e in q.entries if e["run"] == run and e["judged"] and e["class"] != "S"]
    S = [e for e in q.find(family=family, **{"class": "S"})]
    return all(e["outcome"] == c.NOT_FORMED for e in own + S) and bool(own + S)


def plants(registration: Registration, captures: Captures) -> list:
    """The 24 plants (JP4 has two forms: an integer by 1, and a time by one unit in the last place)."""
    out = []

    def add(name, consumer, what, must, alter, check):
        out.append(Plant(name, consumer, what, must, alter, check))

    # ----- JP1 to JP3 -----

    def jp1(runs):
        for name in (H1, H2, H3):
            rows = runs[name]["rows"]
            rows["leak_K"] = {k: scaled(v, -1.0) for k, v in rows["leak_K"].items()}

    add(
        "JP1", "jupiter", "jupiter_baseline, all three rungs: the rows leak_K negated",
        "a fail of leak_K (S), and of the balances of both cells and of the region they face (R)", jp1,
        lambda q: [
            ("leak_K fails (S)", q.outcome(family="jupiter_baseline", readout="leak_K", **{"class": "S"}) == c.FAIL),
            ("the balances of both cells and of `local` fail (R), in each rung", all_balances(q, (H1, H2, H3), "K", ("cell_0", "cell_1"), ("local",))),
            ("no run is refused", not any(q.run(n)["refused"] for n in (H1, H2, H3))),
            ("jupiter fails", q.verdict("jupiter") == c.FAIL),
        ],
    )

    def jp2(runs):
        for name in (H1, H2, H3):
            rows = runs[name]["rows"]
            rows["heat_pump"] = {k: scaled(v, 0.0) for k, v in rows["heat_pump"].items()}

    add(
        "JP2", "jupiter", "jupiter_baseline, all three rungs: the rows heat_pump set to zero",
        "a fail of heat_membrane (S), and of energy_identity", jp2,
        lambda q: [
            ("heat_membrane fails (S)", q.outcome(family="jupiter_baseline", readout="heat_membrane", **{"class": "S"}) == c.FAIL),
            ("energy_identity fails", q.outcome(family="jupiter_baseline", readout="energy_identity") == c.FAIL),
            ("no run is refused", not any(q.run(n)["refused"] for n in (H1, H2, H3))),
        ],
    )

    def jp3(runs):
        for mine, theirs in zip((R1, R2, R3), (H1, H2, H3)):
            for key in ("rows", "potentials", "t", "potential_t"):
                runs[mine][key] = copy.deepcopy(runs[theirs][key])

    add(
        "JP3", "jupiter", "jupiter_pump_release, all three rungs: the rows and potentials replaced by jupiter_baseline's of the same step",
        "a fail of pump (S), and not refused", jp3,
        lambda q: [
            ("pump fails (S)", q.outcome(family="jupiter_pump_release", readout="pump", **{"class": "S"}) == c.FAIL),
            ("not refused", not any(q.run(n)["refused"] for n in (R1, R2, R3))),
        ],
    )

    # ----- JP4 -----

    def jp4_integer(runs):
        runs["base s1 pool"]["pool"]["cell_0"]["arrays"]["event_count"][0] += 1

    def jp4_time(runs):
        times = runs["base s1 pool"]["pool"]["cell_1"]["arrays"]["last_event_time_s"]
        times[3] = math.nextafter(times[3], math.inf)

    def check4(cell, array):
        def check(q):
            E = q.find(run="base s1 pool", **{"class": "E"})
            wrong = [e["readout"] for e in E if e["outcome"] == c.FAIL]
            return [
                (f"class E of {cell} {array} fails for that run", f"{cell} {array}" in wrong),
                ("no other entry fails", q.fails() == [("base s1 pool", f"{cell} {array}")]),
                ("the run is not refused", not q.run("base s1 pool")["refused"]),
                ("base fails", q.verdict("base") == c.FAIL),
            ]

        return check

    must4 = "a fail of class E of that array, for that run"
    add("JP4 (integer)", "base", "base s1 pool: one value of event_count by 1", must4, jp4_integer, check4("cell_0", "event_count"))
    add("JP4 (time)", "base", "base s1 pool: one value of last_event_time_s by one unit in the last place", must4, jp4_time, check4("cell_1", "last_event_time_s"))

    # ----- JP5 to JP7 -----

    def jp5(runs):
        for series in (*CLASS_S_SERIES, *HEATS):
            runs[H3]["rows"][series] = copy.deepcopy(runs[H2]["rows"][series])

    add(
        "JP5", "jupiter", "jupiter_baseline, h3: its class S rows, and the three heats, replaced by h2's",
        "both runs refused by the copy guard (a), their readouts judged, for the checker to settle", jp5,
        lambda q: [
            ("both runs are refused by the copy guard (a)", all(any("copy guard (a)" in x for x in q.run(n)["causes"]) for n in (H2, H3))),
            ("the third run is not refused", not q.run(H1)["refused"]),
            ("their readouts are judged", judged_readouts(q, H2, "jupiter_baseline") and judged_readouts(q, H3, "jupiter_baseline")),
            ("no entry fails", not q.fails()),
            ("jupiter is at best inconclusive", q.verdict("jupiter") == c.INCONCLUSIVE),
        ],
    )

    def jp6(runs):
        refuse(runs[H1], "harness", "planted", rows=False)
        table = runs[H3]["rows"]["n_cell_K"]
        table["cell_0"][-1] += 1e-6 * largest(table)

    add(
        "JP6", "jupiter", "jupiter_baseline: h1 refused (kind harness, no row), and one n_cell_K of h3 raised by 1e-6 of its largest value",
        "the fail of h3's balances stands, and jupiter fails", jp6,
        lambda q: [
            ("h1 is refused and not stopped", q.run(H1)["refused"] and not q.run(H1)["stopped"]),
            ("h3's balance of cells fails (R)", all_balances(q, (H3,), "K", ("cell_0",))),
            ("the family's S entries are not formed", {e["outcome"] for e in q.find(family="jupiter_baseline", **{"class": "S"})} == {c.NOT_FORMED}),
            ("jupiter fails", q.verdict("jupiter") == c.FAIL),
        ],
    )

    def jp7(runs):
        for name in (H1, H2, H3):
            rows = runs[name]["rows"]
            rows["heat_junction"] = {k: scaled(v, 0.0) for k, v in rows["heat_junction"].items()}

    add(
        "JP7", "jupiter", "jupiter_baseline, all three rungs: the rows heat_junction set to zero",
        "a fail of heat_junction (S) and of energy_identity", jp7,
        lambda q: [
            ("heat_junction fails (S)", q.outcome(family="jupiter_baseline", readout="heat_junction", **{"class": "S"}) == c.FAIL),
            ("energy_identity fails", q.outcome(family="jupiter_baseline", readout="energy_identity") == c.FAIL),
        ],
    )

    # ----- JP8 -----

    def jp8(runs):
        runs["base s0 pool"]["path"]["cell_0"]["2"].pop()

    add(
        "JP8", "base", "base s0 pool: the last event deleted from the run's own path of world 2, cell_0",
        "a fail of class E of the run's own path for that run. The exposure is unchanged and passes (R). The ionic runs' schedule entries are not touched", jp8,
        lambda q: [
            ("class E of the run's own path fails", q.outcome(run="base s0 pool", readout="cell_0 path") == c.FAIL),
            ("the exposure passes (R)", q.outcome(run="base s0 pool", readout="cell_0 exposure") == c.PASS),
            ("the schedule entries of the ionic runs pass", {e["outcome"] for e in q.entries if e["judged"] and e["readout"] in ("switch list", "channel schedule")} == {c.PASS}),
            ("no other entry but the restart's path fails", set(q.fails()) == {("base s0 pool", "cell_0 path")}),
            ("base fails", q.verdict("base") == c.FAIL),
        ],
    )

    # ----- JP9, JP10 -----

    def jp9(runs):
        runs[H1]["inputs"]["temperature_K"] *= 1 + 1e-9

    add(
        "JP9", "jupiter", "jupiter_baseline, h1: one number of inputs moved by 1e-9 of itself",
        "refused, and nothing of the run judged. Not a fail plant", jp9,
        lambda q: [
            ("refused by its echo", any("departing echo" in x for x in q.run(H1)["causes"])),
            ("nothing of the run is judged", nothing_judged(q, H1, "jupiter_baseline")),
            ("no entry fails", not q.fails()),
            ("jupiter is at best inconclusive", q.verdict("jupiter") == c.INCONCLUSIVE),
        ],
    )

    def jp10(runs):
        entry = runs[I1]
        block = entry["inputs"]
        block["outside"]["outside"]["initial_amount_fmol"]["K"] = int(block["outside"]["outside"]["initial_amount_fmol"]["K"])
        del block["membranes"]["membrane_3"]["pump"]
        del block["controls"]["pump"]
        schedule = block["controls"]["junction"]["junction_4"]
        schedule.insert(2, [0.0075, schedule[1][1]])
        entry["inputs"] = reversed_maps(block)
        entry["strings"] = reversed_maps(entry["strings"])

    add(
        "JP10", "integrated", "integrated, h1: the echo's maps in another order, a 27 for a 27.0, a default omitted, a schedule with a repeated value",
        "not refused", jp10,
        lambda q: [
            ("not refused", not q.run(I1)["refused"]),
            ("no entry fails", not q.fails()),
            ("integrated passes", q.verdict("integrated") == c.PASS),
        ],
    )

    # ----- JP11 to JP14 -----

    def jp11(runs):
        refuse(runs[H1], "check", "planted")

    add(
        "JP11", "jupiter", "jupiter_baseline, h1: status refused, kind check",
        "a stop, and a fail (D). The rows it holds are judged", jp11,
        lambda q: [
            ("a stop", q.run(H1)["stopped"]),
            ("D fails", q.outcome(run=H1, readout="completes") == c.FAIL),
            ("the rows it holds are judged", {e["outcome"] for e in q.find(run=H1, **{"class": "R"})} == {c.PASS}),
            ("no other entry fails", q.fails() == [(H1, "completes")]),
            ("jupiter fails", q.verdict("jupiter") == c.FAIL),
        ],
    )

    def jp12(runs):
        del runs[f"{H1} restart"]

    add(
        "JP12", "jupiter", "the support run jupiter_baseline h=2.5e-05 restart missing",
        "the consumer at best inconclusive", jp12,
        lambda q: [
            ("the support run is missing", any("missing" in x for x in q.run(f"{H1} restart")["causes"])),
            ("the run it supports is not refused", not q.run(H1)["refused"]),
            ("no entry fails", not q.fails()),
            ("jupiter is at best inconclusive", q.verdict("jupiter") == c.INCONCLUSIVE),
        ],
    )

    def jp13(runs):
        runs[I2]["record_sha256"] = runs[I1]["record_sha256"]

    add(
        "JP13", "integrated", "integrated, h1 and h2: the same record_sha256", "both refused, readouts judged", jp13,
        lambda q: [
            ("both are refused, for the shared record_sha256", all("a shared record_sha256" in q.run(n)["reasons"] for n in (I1, I2))),
            ("h3 is not refused", not q.run(I3)["refused"]),
            ("their readouts are judged", judged_readouts(q, I1, "integrated") and judged_readouts(q, I2, "integrated")),
            ("no entry fails", not q.fails()),
            ("integrated is at best inconclusive", q.verdict("integrated") == c.INCONCLUSIVE),
        ],
    )

    def jp14(runs):
        table = runs[H1]["rows"]["leak_K"]
        shift = 2.0**-52 * largest(table)
        runs[H1]["rows"]["leak_K"] = {k: [v + shift for v in values] for k, values in table.items()}

    def check14(q):
        found = q.find(family="jupiter_baseline", readout="leak_K", **{"class": "S"})
        item = found[0] if len(found) == 1 else {}
        theta = c.THRESHOLD * registration.worlds["jupiter_baseline"].by_name["leak_K"].e_round(3200)
        by_rule = "unresolved" if item.get("d1", 1) <= theta and item.get("d2", 1) <= theta else "another"
        return [
            ("the entry's class is by the rule", item.get("order_class") == by_rule == "unresolved"),
            ("no fail is invented", item.get("outcome") == c.PASS and not q.fails()),
        ]

    add(
        "JP14", "jupiter", "jupiter_baseline, h1: leak_K shifted by 2^-52 of its largest value, the other two rungs honest",
        "the entry's class is by the rule, and no fail is invented", jp14, check14,
    )

    # ----- JP15 to JP18 -----

    W0 = [f"base s0 w0 h={h!r}" for h in (2.5e-05, 1.25e-05, 6.25e-06)]

    def jp15(runs):
        for name in W0:
            rows = runs[name]["rows"]
            rows["channel_K"] = {k: scaled(v, 1.01) for k, v in rows["channel_K"].items()}

    def blind_passes(q):
        blind = q.blind()
        return blind["verdict"] == c.PASS and len(blind["families"]) == 30 and {f["verdict_of_its_entries"] for f in blind["families"].values()} == {c.PASS}

    add(
        "JP15", "base", "base s0 w0, all three rungs: the rows channel_K multiplied by 1.01",
        "base fails, and the record shows that its 30 blind families pass", jp15,
        lambda q: [
            ("channel_K of base s0 w0 fails", q.outcome(family="base s0 w0", readout="channel_K", **{"class": "S"}) == c.FAIL),
            ("base fails", q.verdict("base") == c.FAIL),
            ("its 30 blind families pass", blind_passes(q)),
        ],
    )

    def jp16(runs):
        refuse(runs[W0[0]], "domain", "planted")

    add(
        "JP16", "base", "base s0 w0, h1, refused (kind domain)",
        "base inconclusive, and the record shows that its 30 blind families pass", jp16,
        lambda q: [
            ("the run is refused", q.run(W0[0])["refused"] and not q.run(W0[0])["stopped"]),
            ("base is inconclusive", q.verdict("base") == c.INCONCLUSIVE),
            ("its 30 blind families pass", blind_passes(q)),
        ],
    )

    W1 = "base s1 w0 h=6.25e-06"

    def jp17(runs):
        listed = runs[W1]["inputs"]["assembly"]["switch_list"]
        channel = max(listed, key=lambda k: len(listed[k]))
        listed[channel].pop()

    add(
        "JP17", "base", "base s1 w0, h3: one change deleted from switch_list alone",
        "a fail of class E of the switch list. The channel schedule's entry passes", jp17,
        lambda q: [
            ("the switch list fails (E)", q.outcome(run=W1, readout="switch list") == c.FAIL),
            ("the channel schedule passes", q.outcome(run=W1, readout="channel schedule") == c.PASS),
            ("no other entry fails", q.fails() == [(W1, "switch list")]),
            ("the run is not refused", not q.run(W1)["refused"]),
        ],
    )

    def jp18(runs):
        strings = runs[W1]["strings"]
        text = strings["assembly_observable"]
        strings["assembly_observable"] = text[:-1] + ("x" if text[-1] != "x" else "y")

    add(
        "JP18", "base", "base s1 w0, h3: one character of the assembly_observable string changed, and the label kept",
        "refused, and nothing of the run judged. Not a fail plant", jp18,
        lambda q: [
            ("refused by its echo", any("departing echo" in x and "assembly_observable" in x for x in q.run(W1)["causes"])),
            ("nothing of the run is judged", nothing_judged(q, W1, "base s1 w0")),
            ("no entry fails", not q.fails()),
        ],
    )

    # ----- JP19 to JP24 -----

    def jp19(runs):
        for name in (H1, H2, H3):
            table = runs[name]["rows"]["junction_K"]
            table["junction"][-1] += 1e-4 * largest(table)

    add(
        "JP19", "jupiter", "jupiter_baseline, all three rungs: one junction_K (the last time) raised by 1e-4 of its largest value",
        "a fail of junction_K (S), and of the balances of the two cells (R)", jp19,
        lambda q: [
            ("junction_K fails (S)", q.outcome(family="jupiter_baseline", readout="junction_K", **{"class": "S"}) == c.FAIL),
            ("the balances of the two cells fail (R), in each rung", all_balances(q, (H1, H2, H3), "K", ("cell_0", "cell_1"))),
        ],
    )

    def jp20(runs):
        for name in (H1, H2, H3):
            rows = runs[name]["rows"]
            rows["work_pump"] = {k: scaled(v, 1.01) for k, v in rows["work_pump"].items()}

    add(
        "JP20", "jupiter", "jupiter_baseline, all three rungs: the rows work_pump multiplied by 1.01",
        "a fail of energy_identity, and of no S entry against a capture", jp20,
        lambda q: [
            ("energy_identity fails", q.outcome(family="jupiter_baseline", readout="energy_identity") == c.FAIL),
            ("no S entry against a capture fails", [r for _, r in q.fails()] == ["energy_identity"]),
        ],
    )

    def jp21(runs):
        world = registration.worlds["jupiter_baseline"]
        legacy = captures.ionic("jupiter_baseline", "h2")
        rows = runs[H2]["rows"]
        for series in CLASS_S_SERIES:
            values = legacy.series(series, world.row_times)
            rows[series] = {k: values[:, i].tolist() for i, k in enumerate(world.entities(series))}
        heat = legacy.series("heat_membrane", world.row_times)
        for i, membrane in enumerate(world.membranes):
            rows["heat_leak"][membrane] = (0.25 * heat[:, i]).tolist()
            rows["heat_pump"][membrane] = (0.25 * heat[:, i]).tolist()
            for channel in world.channels_of(membrane):
                rows["heat_channel"][channel] = (0.5 * heat[:, i]).tolist()

    add(
        "JP21", "jupiter", "jupiter_baseline, h2: its class S rows replaced by the captured rows of jupiter_baseline-h2, and the heats by a split of the captured sum",
        "refused by the copy guard (b), its readouts judged", jp21,
        lambda q: [
            ("refused by the copy guard (b)", any("copy guard (b)" in x for x in q.run(H2)["causes"])),
            ("the other two rungs are not refused", not q.run(H1)["refused"] and not q.run(H3)["refused"]),
            ("its readouts are judged", judged_readouts(q, H2, "jupiter_baseline")),
            ("no entry fails", not q.fails()),
            ("jupiter is at best inconclusive", q.verdict("jupiter") == c.INCONCLUSIVE),
        ],
    )

    def jp22(runs):
        for key in ("rows", "potentials", "t", "potential_t"):
            runs["jupiter_baseline plant channel"][key] = copy.deepcopy(runs[H3][key])

    add(
        "JP22", "jupiter", "EP1's rows made equal to its honest run's (jupiter_baseline, h3)", "EP1 is not caught, and jupiter fails", jp22,
        lambda q: [
            ("EP1 is not caught", q.plant("EP1") == "not caught"),
            ("jupiter fails", q.verdict("jupiter") == c.FAIL),
        ],
    )

    def jp23(runs):
        runs[I3]["declared_strings"] = sorted([*runs[I3]["declared_strings"], "an.extra.string@1"])

    add(
        "JP23", "integrated", "integrated, h3: an extra string in declared_strings",
        "refused, and nothing of the run judged. Not a fail plant", jp23,
        lambda q: [
            ("refused by its echo", any("departing echo" in x and "declared_strings" in x for x in q.run(I3)["causes"])),
            ("nothing of the run is judged", nothing_judged(q, I3, "integrated")),
            ("no entry fails", not q.fails()),
            ("integrated is at best inconclusive", q.verdict("integrated") == c.INCONCLUSIVE),
        ],
    )

    def jp24(runs):
        runs[H3]["steps"] += 1

    add(
        "JP24", "jupiter", "jupiter_baseline, h3: steps one more than end_s/step_s",
        "refused (the reason off_grid_change), its readouts judged", jp24,
        lambda q: [
            ("refused, with the reason off_grid_change", q.run(H3)["refused"] and "off_grid_change" in q.run(H3)["reasons"]),
            ("its readouts are judged", judged_readouts(q, H3, "jupiter_baseline")),
            ("no entry fails", not q.fails()),
            ("jupiter is at best inconclusive", q.verdict("jupiter") == c.INCONCLUSIVE),
        ],
    )
    return out


def reversed_maps(value):
    """The same JSON value with every map in the opposite order."""
    if isinstance(value, dict):
        return {k: reversed_maps(v) for k, v in reversed(list(value.items()))}
    return [reversed_maps(v) for v in value] if isinstance(value, list) else value


def judge(registration: Registration, note: StringsNote, tables: dict, c0: dict, captures, planted) -> dict:
    """Both stages on parsed tables, in memory: the code that the registered tables go through."""
    state = scoring.Tables(registration, note, TableSet.from_data(tables))
    hashes = {"tables": "in memory"}
    power = scoring.stage1(state, c0, hashes)
    scoring.check_power(scoring.Tables(registration, note, TableSet.from_data(tables)), c0, power, hashes)
    return scoring.Stage2(state, c0, power, captures, planted).run()


def run_plants(registration: Registration, note: StringsNote, tables: dict, c0: dict, captures, planted, only=None) -> dict:
    """Score every plant on altered copies of the tables. A plant whose checks do not all hold is named, and nothing is bent."""
    baseline = judge(registration, note, tables, c0, captures, planted)
    out = {
        "baseline": {k: v["verdict"] for k, v in baseline["consumers"].items()},
        "baseline_plants": [[p["plant"], p["consumer"], p["score"]] for p in baseline["plants"]["plants"]],
        "plants": [],
    }
    for plant in plants(registration, captures):
        if only and plant.name.split()[0] not in only:
            continue
        altered = dict(tables)
        altered[plant.consumer] = dict(tables[plant.consumer], runs=dict(tables[plant.consumer]["runs"]))
        runs = altered[plant.consumer]["runs"]
        runs.update(copy.deepcopy(runs))
        plant.alter(runs)
        record = judge(registration, note, altered, c0, captures, planted)
        checks = [[what, bool(good)] for what, good in plant.check(Query(record))]
        out["plants"].append(
            {
                "plant": plant.name,
                "consumer": plant.consumer,
                "what": plant.what,
                "must_be": plant.must,
                "scores_as_stated": all(good for _, good in checks),
                "checks": checks,
                "verdicts": {k: v["verdict"] for k, v in record["consumers"].items()},
            }
        )
    out["all_as_stated"] = all(p["scores_as_stated"] for p in out["plants"])
    return out


__all__ = ["Plant", "Query", "judge", "plants", "run_plants", "np"]
