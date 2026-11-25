"""The judge's plants JP1 to JP24 (PLANTS section 6, and Amendment 2 for JP14): altered copies of honest tables, and what each must score.

A plant alters rows only, or the one leaf that it names. Each is scored by the code that scores the registered tables. What a plant names
(a family, a run) comes from the profile, so the rehearsal's worlds can stand in for the registered ones.
"""

from __future__ import annotations

import copy
import math

from . import constants as c
from . import scoring
from .legacy import Captures
from .registration import Registration, StringsNote
from .table import TableSet

HEATS = ("heat_leak", "heat_pump", "heat_channel")


class Query:
    """What a plant's checks ask of a record."""

    def __init__(self, record: dict, baseline: dict | None = None):
        self.record = record
        self.entries = record["entries"]
        self.before = None if baseline is None else {k: v["verdict"] for k, v in baseline["consumers"].items()}
        self.failed_before = set() if baseline is None else set(Query(baseline).fails())

    def find(self, **wanted) -> list:
        """The judged entries that have these values."""
        return [e for e in self.entries if e["judged"] and all(e.get(k) == v for k, v in wanted.items())]

    def S(self, family, readout=None) -> list:
        """The judged class S entries of a family, or the one of a readout."""
        return [e for e in self.find(family=family, **{"class": "S"}) if readout in (None, e["readout"])]

    def R(self, run) -> list:
        """The judged class R entries of a run."""
        return self.find(run=run, **{"class": "R"})

    def outcome(self, **wanted):
        """The outcome of the one judged entry that has these values."""
        found = self.find(**wanted)
        return found[0]["outcome"] if len(found) == 1 else f"{len(found)} entries"

    def fails(self) -> list:
        """Every failing entry that did not fail in the baseline, as (run, readout)."""
        found = [(e["run"], e["readout"]) for e in self.entries if e["judged"] and e["outcome"] == c.FAIL]
        return [item for item in found if item not in self.failed_before]

    def run(self, name) -> dict:
        """A run's state."""
        return self.record["runs"][name]

    def cause(self, name, *words) -> bool:
        """True where one cause of a run's refusal holds all the words."""
        return any(all(word in cause for word in words) for cause in self.run(name)["causes"])

    def verdict(self, consumer) -> str:
        """A consumer's verdict."""
        return self.record["consumers"][consumer]["verdict"]

    def reads(self, consumer, wanted):
        """True or False: a consumer's verdict is the wanted one. None where the baseline does not pass, so that it cannot be read."""
        if self.before is not None and self.before[consumer] != c.PASS:
            return None
        return self.verdict(consumer) == wanted

    def plant(self, name) -> str:
        """An engine plant's score."""
        return next(p["score"] for p in self.record["plants"]["plants"] if p["plant"] == name)

    def balances_fail(self, runs, species, cells=(), regions=()) -> bool:
        """True where the balances of these cells and regions fail in each of the runs."""
        good = True
        for run in runs:
            for kind, entities in (("cells", cells), ("regions", regions)):
                if entities:
                    found = self.find(run=run, readout=f"balance of {kind}, {species}")
                    good &= len(found) == 1 and found[0]["outcome"] == c.FAIL and all(found[0]["by_entity"][k] > 1 for k in entities)
        return good

    def readouts_judged(self, run, family) -> bool:
        """True where a refused run's readouts are judged: its R entries and its family's S entries are formed."""
        found = self.R(run) + self.S(family)
        return bool(found) and all(e["outcome"] != c.NOT_FORMED for e in found)

    def nothing_judged(self, run, family) -> bool:
        """True where nothing of a run is judged, and its family's S entries are not formed."""
        own = [e for e in self.entries if e["run"] == run and e["judged"] and e["class"] != "S"] + self.S(family)
        return bool(own) and all(e["outcome"] == c.NOT_FORMED for e in own)


class Lazy(dict):
    """A table's runs, each copied when a plant first takes it."""

    def __init__(self, base):
        super().__init__(base)
        self._own = set()

    def __getitem__(self, key):
        if key not in self._own:
            super().__setitem__(key, copy.deepcopy(super().__getitem__(key)))
            self._own.add(key)
        return super().__getitem__(key)


def scaled(table: dict, factor: float) -> dict:
    """A series times a factor."""
    return {entity: [v * factor for v in values] for entity, values in table.items()}


def largest(table: dict) -> float:
    """The largest magnitude of a series, over its entities."""
    return max(abs(v) for values in table.values() for v in values)


def refuse(entry: dict, kind: str, rows: bool = True):
    """Make an entry a refused one of a kind. Without rows, as a refusal before any accepted row."""
    entry["status"] = "refused"
    entry["refusal"] = {"kind": kind, "message": "planted", "time_s": 0.01 if kind == "check" else None}
    if not rows:
        entry.update(t=[], rows={}, potential_t=[], potentials={})


def reversed_maps(value):
    """The same JSON value with every map in the opposite order."""
    if isinstance(value, dict):
        return {k: reversed_maps(v) for k, v in reversed(list(value.items()))}
    return [reversed_maps(v) for v in value] if isinstance(value, list) else value


class Plant:
    """One judge's plant: the consumer whose table it alters, the alteration, and its checks."""

    def __init__(self, name, consumer, what, must, alter, check):
        self.name, self.consumer, self.what, self.must, self.alter, self.check = name, consumer, what, must, alter, check


def plants(registration: Registration, captures: Captures) -> list:
    """The plants. JP4 has two forms: an integer by 1, and a time by one unit in the last place."""
    target = registration.profile["plant_targets"]
    A, B, junctions = (registration.families[target[k]] for k in ("ionic", "other_schedule", "junctions"))
    seen, assembly = registration.families[target["not_blind"]], registration.families[target["assembly"]]
    H1, H2, H3 = A.runs
    I1, I2, I3 = junctions.runs
    pool_run, (path_run, path_cell, path_world) = target["pool"], target["pool_path"]
    ionic, J, pools = A.consumer, junctions.consumer, seen.consumer
    world = A.world
    facing = tuple(dict.fromkeys(m["outside"] for m in world.block["membranes"].values()))
    W3 = assembly.finest
    out = []

    def add(name, consumer, what, must, alter, check):
        out.append(Plant(name, consumer, what, must, alter, check))

    known = registration.profile.get("not_blind", {}).get(pools, [seen.name])
    others = [f.name for f in registration.by_consumer[pools] if f.name not in known]

    def blind_passes(q):
        sets = q.record["consumers"][pools]["sets"]
        families = {name: f for block in sets.values() for name, f in block["families"].items()}
        good = all(families[name]["verdict_of_its_entries"] == c.PASS for name in others) and bool(others)
        return good and ("blind" not in sets or (sets["blind"]["verdict"] == c.PASS and set(sets["blind"]["families"]) == set(others)))

    def jp1(runs):
        for name in A.runs:
            runs[name]["rows"]["leak_K"] = scaled(runs[name]["rows"]["leak_K"], -1.0)

    add(
        "JP1", ionic, f"{A.name}, all three rungs: the rows leak_K negated",
        "a fail of leak_K (S), and of the balances of both cells and of the region they face (R)", jp1,
        lambda q: [
            ("leak_K fails (S)", q.outcome(family=A.name, readout="leak_K", **{"class": "S"}) == c.FAIL),
            ("the balances of both cells and of the region they face fail (R), in each rung", q.balances_fail(A.runs, "K", world.cells, facing)),
            ("no run is refused", not any(q.run(n)["refused"] for n in A.runs)),
            ("the consumer fails", q.reads(ionic, c.FAIL)),
        ],
    )

    def jp2(runs):
        for name in A.runs:
            runs[name]["rows"]["heat_pump"] = scaled(runs[name]["rows"]["heat_pump"], 0.0)

    add(
        "JP2", ionic, f"{A.name}, all three rungs: the rows heat_pump set to zero", "a fail of heat_membrane (S), and of energy_identity", jp2,
        lambda q: [
            ("heat_membrane fails (S)", q.outcome(family=A.name, readout="heat_membrane", **{"class": "S"}) == c.FAIL),
            ("energy_identity fails", q.outcome(family=A.name, readout="energy_identity") == c.FAIL),
            ("no run is refused", not any(q.run(n)["refused"] for n in A.runs)),
        ],
    )

    def jp3(runs):
        for mine, theirs in zip(B.runs, A.runs):
            for key in ("rows", "potentials"):
                runs[mine][key] = copy.deepcopy(runs[theirs][key])

    add(
        "JP3", ionic, f"{B.name}, all three rungs: the rows and potentials replaced by {A.name}'s of the same step", "a fail of pump (S), and not refused", jp3,
        lambda q: [
            ("pump fails (S)", q.outcome(family=B.name, readout="pump", **{"class": "S"}) == c.FAIL),
            ("not refused", not any(q.run(n)["refused"] for n in B.runs)),
        ],
    )

    def jp4_integer(runs):
        runs[pool_run]["pool"]["cell_0"]["arrays"]["event_count"][0] += 1

    def jp4_time(runs):
        times = runs[pool_run]["pool"]["cell_0"]["arrays"]["last_event_time_s"]
        times[-1] = math.nextafter(times[-1], math.inf)

    def check4(readout):
        return lambda q: [
            ("class E of that array fails, for that run", q.outcome(run=pool_run, readout=readout) == c.FAIL),
            ("no other entry fails", q.fails() == [(pool_run, readout)]),
            ("the run is not refused", not q.run(pool_run)["refused"]),
            ("the consumer fails", q.reads(pools, c.FAIL)),
        ]

    must4 = "a fail of class E of that array, for that run"
    add("JP4 (integer)", pools, f"{pool_run}: one value of event_count by 1", must4, jp4_integer, check4("cell_0 event_count"))
    add("JP4 (time)", pools, f"{pool_run}: one value of last_event_time_s by one unit in the last place", must4, jp4_time, check4("cell_0 last_event_time_s"))

    def jp5(runs):
        for series in (*dict.fromkeys(e.series for e in world.guard_entries()), *HEATS):
            runs[H3]["rows"][series] = copy.deepcopy(runs[H2]["rows"][series])

    add(
        "JP5", ionic, f"{A.name}, h3: its class S rows, and the three heats, replaced by h2's",
        "both runs refused by the copy guard (a), their readouts judged, for the checker to settle", jp5,
        lambda q: [
            ("both runs are refused by the copy guard (a)", all(q.cause(n, "copy guard (a)") for n in (H2, H3))),
            ("the third run is not refused", not q.run(H1)["refused"]),
            ("their readouts are judged", q.readouts_judged(H2, A.name) and q.readouts_judged(H3, A.name)),
            ("no entry fails", not q.fails()),
            ("the consumer is inconclusive", q.reads(ionic, c.INCONCLUSIVE)),
        ],
    )

    def jp6(runs):
        refuse(runs[H1], "harness", rows=False)
        table = runs[H3]["rows"]["n_cell_K"]
        table[world.cells[0]][-1] += 1e-6 * largest(table)

    add(
        "JP6", ionic, f"{A.name}: h1 refused (kind harness, no row), and one n_cell_K of h3 raised by 1e-6 of its largest value",
        "the fail of h3's balances stands, and the consumer fails", jp6,
        lambda q: [
            ("h1 is refused and not stopped", q.run(H1)["refused"] and not q.run(H1)["stopped"]),
            ("h3's balance of that cell fails (R)", q.balances_fail((H3,), "K", world.cells[:1])),
            ("the family's S entries are not formed", {e["outcome"] for e in q.S(A.name)} == {c.NOT_FORMED}),
            ("the consumer fails", q.reads(ionic, c.FAIL)),
        ],
    )

    def jp7(runs):
        for name in A.runs:
            runs[name]["rows"]["heat_junction"] = scaled(runs[name]["rows"]["heat_junction"], 0.0)

    add(
        "JP7", ionic, f"{A.name}, all three rungs: the rows heat_junction set to zero", "a fail of heat_junction (S) and of energy_identity", jp7,
        lambda q: [
            ("heat_junction fails (S)", q.outcome(family=A.name, readout="heat_junction", **{"class": "S"}) == c.FAIL),
            ("energy_identity fails", q.outcome(family=A.name, readout="energy_identity") == c.FAIL),
        ],
    )

    def jp8(runs):
        runs[path_run]["path"][path_cell][path_world].pop()

    add(
        "JP8", pools, f"{path_run}: the last event deleted from the run's own path of world {path_world}, {path_cell}",
        "a fail of class E of the run's own path for that run. The exposure is unchanged and passes (R). The schedule entries of the ionic runs are not touched", jp8,
        lambda q: [
            ("class E of the run's own path fails", q.outcome(run=path_run, readout=f"{path_cell} path") == c.FAIL),
            ("the exposure passes (R)", q.outcome(run=path_run, readout=f"{path_cell} exposure") == c.PASS),
            ("the schedule entries of the ionic runs pass", {e["outcome"] for e in q.entries if e["judged"] and e["readout"] in ("switch list", "channel schedule")} == {c.PASS}),
            ("no other entry fails", q.fails() == [(path_run, f"{path_cell} path")]),
            ("the consumer fails", q.reads(pools, c.FAIL)),
        ],
    )

    def jp9(runs):
        runs[H1]["inputs"]["temperature_K"] *= 1 + 1e-9

    add(
        "JP9", ionic, f"{A.name}, h1: one number of inputs moved by 1e-9 of itself", "refused, and nothing of the run judged. Not a fail plant", jp9,
        lambda q: [
            ("refused by its echo", q.cause(H1, "departing echo", "temperature_K")),
            ("nothing of the run is judged", q.nothing_judged(H1, A.name)),
            ("no entry fails", not q.fails()),
            ("the consumer is inconclusive", q.reads(ionic, c.INCONCLUSIVE)),
        ],
    )

    def jp10(runs):
        block = runs[I1]["inputs"]
        amounts = next(r["initial_amount_fmol"] for r in block["outside"].values())
        whole = next(x for x, value in amounts.items() if x == "K" and float(value).is_integer())
        amounts[whole] = int(amounts[whole])
        bare = next(m for m, v in block["membranes"].items() if v["pump"] is None)
        del block["membranes"][bare]["pump"]
        del block["controls"]["pump"]
        schedule = next(s for s in block["controls"]["junction"].values() if len(s) > 1)
        schedule.insert(2, [(schedule[1][0] + schedule[2][0]) / 2, schedule[1][1]])
        runs[I1]["inputs"] = reversed_maps(block)
        runs[I1]["strings"] = reversed_maps(runs[I1]["strings"])

    add(
        "JP10", J, f"{junctions.name}, h1: an echo with its maps in another order, a whole number without its point, a default omitted, and a schedule with a repeated value",
        "not refused", jp10,
        lambda q: [
            ("not refused", not q.run(I1)["refused"]),
            ("no entry fails", not q.fails()),
            ("the consumer passes", q.reads(J, c.PASS)),
        ],
    )

    def jp11(runs):
        refuse(runs[H1], "check")

    add(
        "JP11", ionic, f"{A.name}, h1: status refused, kind check", "a stop, and a fail (D). The rows it holds are judged", jp11,
        lambda q: [
            ("a stop", q.run(H1)["stopped"]),
            ("D fails", q.outcome(run=H1, readout="completes") == c.FAIL),
            ("the rows it holds are judged", {e["outcome"] for e in q.R(H1)} == {c.PASS}),
            ("no other entry fails", q.fails() == [(H1, "completes")]),
            ("the consumer fails", q.reads(ionic, c.FAIL)),
        ],
    )

    def jp12(runs):
        del runs[target["restart"]]

    add(
        "JP12", ionic, f"the support run {target['restart']} missing", "the consumer at best inconclusive", jp12,
        lambda q: [
            ("the support run is missing", q.cause(target["restart"], "missing")),
            ("the run it supports is not refused", not q.run(registration.restarted(registration.runs[target["restart"]]))["refused"]),
            ("no entry fails", not q.fails()),
            ("the consumer is inconclusive", q.reads(ionic, c.INCONCLUSIVE)),
        ],
    )

    def jp13(runs):
        runs[I2]["record_sha256"] = runs[I1]["record_sha256"]

    add(
        "JP13", J, f"{junctions.name}, h1 and h2: the same record_sha256", "both refused, readouts judged", jp13,
        lambda q: [
            ("both are refused, for the shared record_sha256", all("a shared record_sha256" in q.run(n)["reasons"] for n in (I1, I2))),
            ("h3 is not refused", not q.run(I3)["refused"]),
            ("their readouts are judged", q.readouts_judged(I1, junctions.name) and q.readouts_judged(I2, junctions.name)),
            ("no entry fails", not q.fails()),
            ("the consumer is inconclusive", q.reads(J, c.INCONCLUSIVE)),
        ],
    )

    def jp14(runs):
        table = runs[H2]["rows"]["leak_K"]
        shift = 2.0**-52 * largest(table)
        runs[H2]["rows"]["leak_K"] = {entity: [v + shift for v in values] for entity, values in table.items()}

    def check14(q):
        found = q.S(A.name, "leak_K")
        item = found[0] if len(found) == 1 else {}
        theta = c.THRESHOLD * world.by_name["leak_K"].e_round(world.steps(A.steps_s[2]))
        below = item.get("d1", math.inf) <= theta and item.get("d2", math.inf) <= theta
        return [
            ("the entry's class is by the rule", below and item.get("order_class") == "unresolved"),
            ("no fail is invented", item.get("outcome") == c.PASS and not q.fails()),
        ]

    add(
        "JP14", ionic, f"{A.name}, h2: one series leak_K shifted by 2^-52 of its largest value, the other two rungs honest (Amendment 2)",
        "the entry's class is by the rule, and no fail is invented", jp14, check14,
    )

    def jp15(runs):
        for name in seen.runs:
            runs[name]["rows"]["channel_K"] = scaled(runs[name]["rows"]["channel_K"], 1.01)

    add(
        "JP15", pools, f"{seen.name}, all three rungs: the rows channel_K multiplied by 1.01, every blind family honest",
        "the consumer fails, and the record shows that its blind families pass", jp15,
        lambda q: [
            ("channel_K of that family fails (S)", q.outcome(family=seen.name, readout="channel_K", **{"class": "S"}) == c.FAIL),
            ("the consumer fails", q.reads(pools, c.FAIL)),
            ("its blind families pass", blind_passes(q)),
        ],
    )

    def jp16(runs):
        refuse(runs[seen.runs[0]], "domain")

    add(
        "JP16", pools, f"{seen.name}, h1, refused (kind domain), every blind family honest",
        "the consumer inconclusive, and the record shows that its blind families pass", jp16,
        lambda q: [
            ("the run is refused, and not stopped", q.run(seen.runs[0])["refused"] and not q.run(seen.runs[0])["stopped"]),
            ("the consumer is inconclusive", q.reads(pools, c.INCONCLUSIVE)),
            ("its blind families pass", blind_passes(q)),
        ],
    )

    def jp17(runs):
        listed = runs[W3]["inputs"]["assembly"]["switch_list"]
        next(changes for changes in listed.values() if changes).pop()

    add(
        "JP17", pools, f"{assembly.name}, h3: one change deleted from switch_list alone",
        "a fail of class E of the switch list. The channel schedule's entry passes", jp17,
        lambda q: [
            ("the switch list fails (E)", q.outcome(run=W3, readout="switch list") == c.FAIL),
            ("the channel schedule passes", q.outcome(run=W3, readout="channel schedule") == c.PASS),
            ("no other entry fails", q.fails() == [(W3, "switch list")]),
            ("the run is not refused", not q.run(W3)["refused"]),
        ],
    )

    def jp18(runs):
        strings = runs[W3]["strings"]
        text = strings["assembly_observable"]
        strings["assembly_observable"] = text[:-1] + ("x" if text[-1] != "x" else "y")

    add(
        "JP18", pools, f"{assembly.name}, h3: one character of the assembly_observable string changed, and the label kept",
        "refused, and nothing of the run judged. Not a fail plant", jp18,
        lambda q: [
            ("refused by its echo", q.cause(W3, "departing echo", "assembly_observable")),
            ("nothing of the run is judged", q.nothing_judged(W3, assembly.name)),
            ("no entry fails", not q.fails()),
        ],
    )

    joined = world.junctions[0]
    ends = (world.block["junctions"][joined]["from_cell"], world.block["junctions"][joined]["to_cell"])

    def jp19(runs):
        for name in A.runs:
            table = runs[name]["rows"]["junction_K"]
            table[joined][-1] += 1e-4 * largest(table)

    add(
        "JP19", ionic, f"{A.name}, all three rungs: one junction_K (the last time) raised by 1e-4 of its largest value",
        "a fail of junction_K (S), and of the balances of the two cells (R)", jp19,
        lambda q: [
            ("junction_K fails (S)", q.outcome(family=A.name, readout="junction_K", **{"class": "S"}) == c.FAIL),
            ("the balances of the two cells fail (R), in each rung", q.balances_fail(A.runs, "K", ends)),
        ],
    )

    def jp20(runs):
        for name in A.runs:
            runs[name]["rows"]["work_pump"] = scaled(runs[name]["rows"]["work_pump"], 1.01)

    add(
        "JP20", ionic, f"{A.name}, all three rungs: the rows work_pump multiplied by 1.01", "a fail of energy_identity, and of no S entry against a capture", jp20,
        lambda q: [
            ("energy_identity fails", q.outcome(family=A.name, readout="energy_identity") == c.FAIL),
            ("no S entry against a capture fails", [e["readout"] for e in q.S(A.name) if e["outcome"] == c.FAIL] == ["energy_identity"]),
            ("no other entry fails", [readout for _, readout in q.fails()] == ["energy_identity"]),
        ],
    )

    def jp21(runs):
        legacy = captures.run(A, "h2")
        rows = runs[H2]["rows"]
        for series in dict.fromkeys(e.series for e in world.guard_entries()):
            values = legacy.series(series, world.row_times)
            rows[series] = {k: values[:, i].tolist() for i, k in enumerate(world.entities(series))}
        heat = legacy.series("heat_membrane", world.row_times)
        for i, membrane in enumerate(world.membranes):
            rows["heat_leak"][membrane] = (0.25 * heat[:, i]).tolist()
            rows["heat_pump"][membrane] = (0.25 * heat[:, i]).tolist()
            for channel in world.channels_of(membrane):
                rows["heat_channel"][channel] = (0.5 * heat[:, i]).tolist()

    add(
        "JP21", ionic, f"{A.name}, h2: its class S rows replaced by the captured rows at h/2, and the three heats by a split of the captured sum",
        "refused by the copy guard (b), its readouts judged", jp21,
        lambda q: [
            ("refused by the copy guard (b)", q.cause(H2, "copy guard (b)")),
            ("the other two rungs are not refused", not q.run(H1)["refused"] and not q.run(H3)["refused"]),
            ("its readouts are judged", q.readouts_judged(H2, A.name)),
            ("no entry fails", not q.fails()),
            ("the consumer is inconclusive", q.reads(ionic, c.INCONCLUSIVE)),
        ],
    )

    def jp22(runs):
        for key in ("rows", "potentials"):
            runs[target["engine_plant"]][key] = copy.deepcopy(runs[H3][key])

    variant = registration.runs[target["engine_plant"]]["variant"]
    add(
        "JP22", ionic, f"the rows of {target['engine_plant']} made equal to its honest run's ({A.name}, h3)", "the plant is not caught, and the consumer fails", jp22,
        lambda q: [
            ("the plant is not caught", q.plant(variant) == "not caught"),
            ("the consumer fails", q.reads(ionic, c.FAIL)),
        ],
    )

    def jp23(runs):
        runs[I3]["declared_strings"] = sorted([*runs[I3]["declared_strings"], "an.extra.string"])

    add(
        "JP23", J, f"{junctions.name}, h3: an extra string in declared_strings", "refused, and nothing of the run judged. Not a fail plant", jp23,
        lambda q: [
            ("refused by its echo", q.cause(I3, "departing echo", "declared_strings")),
            ("nothing of the run is judged", q.nothing_judged(I3, junctions.name)),
            ("no entry fails", not q.fails()),
            ("the consumer is inconclusive", q.reads(J, c.INCONCLUSIVE)),
        ],
    )

    def jp24(runs):
        runs[H3]["steps"] += 1

    add(
        "JP24", ionic, f"{A.name}, h3: steps one more than end_s/step_s", "refused (the reason off_grid_change), its readouts judged", jp24,
        lambda q: [
            ("refused, with the reason off_grid_change", q.run(H3)["refused"] and "off_grid_change" in q.run(H3)["reasons"]),
            ("its readouts are judged", q.readouts_judged(H3, A.name)),
            ("no entry fails", not q.fails()),
            ("the consumer is inconclusive", q.reads(ionic, c.INCONCLUSIVE)),
        ],
    )
    return out


def judge(registration: Registration, note: StringsNote, tables: dict, c0: dict, captures, planted) -> dict:
    """Both stages on parsed tables, in memory: the code that the registered tables go through."""
    state = scoring.Tables(registration, note, TableSet.from_data(tables))
    hashes = {"tables": "in memory"}
    power = scoring.stage1(state, c0, hashes)
    scoring.check_power(state, c0, power, hashes)
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
        item = {"plant": plant.name, "consumer": plant.consumer, "what": plant.what, "must_be": plant.must}
        runs = Lazy(tables[plant.consumer]["runs"])
        try:
            plant.alter(runs)
        except (KeyError, IndexError, StopIteration, TypeError) as error:
            item.update(scores_as_stated=False, cannot_be_formed=f"{type(error).__name__}: {error}")
            out["plants"].append(item)
            continue
        altered = dict(tables)
        altered[plant.consumer] = dict(tables[plant.consumer], runs=dict(runs))
        record = judge(registration, note, altered, c0, captures, planted)
        checks = [[what, good if good is None else bool(good)] for what, good in plant.check(Query(record, baseline))]
        item.update(scores_as_stated=all(good is not False for _, good in checks), checks=checks)
        item["verdicts"] = {k: v["verdict"] for k, v in record["consumers"].items()}
        out["plants"].append(item)
    out["all_as_stated"] = all(p["scores_as_stated"] for p in out["plants"])
    return out
