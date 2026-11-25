"""Stage 1 (power) and stage 2 (scores and verdicts), in the spec's order (CRITERIA sections 4 to
8).

Stage 1 reads the tables' own rows, the inputs' scales and C0's numbers of the captures. It opens no
capture and forms no difference between a candidate and a capture. Stage 2 forms those, and it needs
`power.json` and its recorded sha256.
"""

from __future__ import annotations

import numpy as np

from . import bands, identities, strictjson
from . import constants as c
from .legacy import STEPS, Captures, Planted
from .registration import Registration, StringsNote, changes
from .settlements import Settlements
from .table import NotFormed, RunRows, TableSet, assess, column, parse_schedule

OUTSIDE = "resolved outside its window"
CUT = "a refused run: the refusal cut what it holds (Amendment 2, reading 14)"
ANOTHER_PATH = (
    "a support run that a check stopped: its rows are another path's (Amendment 2, reading 13)"
)


def begins(a: list, b: list) -> bool:
    """True where one list is a beginning of the other."""
    short = min(len(a), len(b))
    return a[:short] == b[:short]


class OrderFault(Exception):
    """A step of the judgement that is out of the spec's order, or whose inputs are not the recorded
    ones.
    """


# ----- counts (READOUTS sections 3 and 4) -----


def expected_counts(registration: Registration, consumer: str, families=None) -> dict:
    """The entries of a consumer by class. `families` restricts the families; the pool and support
    runs stay (CRITERIA section 8).
    """
    chosen = registration.by_consumer[consumer] if families is None else families
    names = {family.name for family in chosen}
    out = {"S": 0, "energy": 0, "R": 0, "E": 0, "D": 0}
    for family in chosen:
        out["S"] += len(family.world.entries)
        out["energy"] += int(family.world.identities_judged)
    for run in registration.runs.values():
        if run["consumer"] != consumer or (
            run["family"] is not None and run["family"] not in names
        ):
            continue
        world = registration.worlds[run["world"]]
        pool = registration.is_pool(run)
        if run["role"] == "judged":
            out["D"] += 1
            if pool:
                out["R"] += len(world.pools)
                out["E"] += len(world.pools) * (len(c.POOL_ARRAYS) + 2)
            else:
                out["R"] += ionic_R(world)
                out["E"] += ionic_E(world)
        if run["role"] == "support" and registration.restart_time(run) is not None:
            if supported_family(registration, run) in names | {None}:
                per_pool = len(c.POOL_ARRAYS) + 1
                out["E"] += len(world.pools) * per_pool if pool else len(world.entries)
    return out


def supported_family(registration: Registration, run: dict):
    """The family of the run that a restart is compared with, None where it has none (a pool run).
    Its entries, and the support run, are of the set of `base` that holds that family.
    """
    owner = registration.restarted(run)
    return registration.runs[owner]["family"] if owner is not None else None


def ionic_R(world) -> int:
    """The class R entries of an ionic judged run: three balances of each species, and the
    capacitor.
    """
    return 3 * len(world.species) + 1 if world.identities_judged else 0


def ionic_E(world) -> int:
    """The class E entries of an ionic judged run: its structural zeros and, in an assembly world,
    the switch list, the schedule and the seeds.
    """
    return len(world.zeros) + (3 if world.assembly else 0)


# ----- what both stages read -----


class Tables:
    """The tables with every registered run's state, its rows on demand, and the copy guard's first
    comparison.
    """

    def __init__(
        self,
        registration: Registration,
        note: StringsNote,
        tables: TableSet,
        retry: TableSet | None = None,
        owed=(),
        settlements: Settlements | None = None,
    ):
        faults = note.faults(registration)
        if faults:
            raise OrderFault(f"the strings note: {'; '.join(faults[:5])}")
        self.reg, self.note, self.tables, self.retry = registration, note, tables, retry
        self.states, self.ignored = assess(registration, note, tables, retry, owed)
        self.owed = tuple(owed)
        self.settlements = settlements
        self._rows, self._arrays = {}, {}
        self.guard_hits = []  # every refusal by the copy guard, with its settlement
        self.guard_a = self._guard_a()

    def rows(self, name: str) -> RunRows:
        """A judged run's rows. Raises `NotFormed` where nothing of the run is judged."""
        state = self.states[name]
        if not state.judgable:
            raise NotFormed(f"{name}: {'; '.join(state.causes()) or 'not judged'}")
        if name not in self._rows:
            self._rows[name] = RunRows(self.reg.worlds[state.run["world"]], state.entry)
        return self._rows[name]

    def entry(self, name: str, entry) -> np.ndarray:
        """An entry's array of a run."""
        key = (name, entry.name)
        if key not in self._arrays:
            try:
                self._arrays[key] = self.rows(name).entry(entry)
            except NotFormed as error:
                self._arrays[key] = NotFormed(
                    str(error) if str(error).startswith(name) else f"{name}: {error}"
                )
        if isinstance(self._arrays[key], NotFormed):
            raise NotFormed(str(self._arrays[key]))
        return self._arrays[key]

    def rungs(self, family) -> tuple:
        """The family's runs, and its retry run where that is owed."""
        retry = (family.retry_name,) if family.retry_name in self.states else ()
        return family.runs + retry

    def guard_rows(self, name: str):
        """Every class S row of a run at every compared time, or None where one of them is not
        there.
        """
        world = self.reg.worlds[self.states[name].run["world"]]
        try:
            return [self.entry(name, entry) for entry in world.guard_entries()]
        except NotFormed:
            return None

    def _guard_a(self) -> list:
        """Comparison (a): two rungs of one family whose class S rows are all exactly equal. Both
        are refused (CRITERIA section 5).
        """
        out = []
        for family in self.reg.families.values():
            names = [n for n in self.rungs(family) if self.states[n].judgable]
            held = {name: self.guard_rows(name) for name in names}
            for i, first in enumerate(names):
                for second in names[i + 1 :]:
                    if held[first] is None or held[second] is None:
                        continue
                    if all(
                        np.array_equal(a, b) for a, b in zip(held[first], held[second], strict=True)
                    ):
                        out.append([family.name, first, second])
                        self.refuse_copy(first, "a", f"its class S rows equal {second}'s")
                        self.refuse_copy(second, "a", f"its class S rows equal {first}'s")
        return out

    def refuse_copy(self, name: str, comparison: str, detail: str):
        """Refuse a run by the copy guard, for the checker to settle. A refusal that the lead's
        dated note has lifted is no refusal (Amendment 2, reading 28).
        """
        state = self.states[name]
        settled = self.settlements.guard.get((name, comparison)) if self.settlements else None
        self.guard_hits.append(
            {
                "run": name,
                "consumer": state.consumer,
                "comparison": comparison,
                "detail": detail,
                "settled": settled,
            }
        )
        if settled is not None and settled["outcome"] == c.LIFTED:
            state.lifted.append([comparison, settled["lead_note"]])
        else:
            state.guard.append([comparison, detail])


def estimates(tables: Tables, family, names, steps_s, c0: dict) -> dict:
    """Every S entry and the energy identity of a triple: the run's own differences, U_c, the
    order's class, beta and power.
    """
    registration, world = tables.reg, family.world
    steps_c = world.steps(steps_s[2])
    legacy = c0["legacy"][family.name]
    out = {}
    for entry in [*world.entries, world.energy]:
        record = {"runs": list(names), "S_c": steps_c, "p": world.p, "home": False, "tested": None}
        identity = entry.where == "identity"
        if not identity:
            record.update(S_l=legacy["S_l"], home=registration.is_home(world.name, entry.name))
        try:
            arrays = [tables.entry(name, entry) for name in names]
        except NotFormed as error:
            out[entry.name] = {**record, "formed": False, "why": str(error)}
            continue
        d2, d1, U_c = bands.estimate(*arrays, world.p)
        U_l = 0.0 if identity else legacy["entries"][entry.name]["U_l"]
        parts = bands.band(entry, U_c, U_l, steps_c, None if identity else legacy["S_l"])
        record.update(formed=True, why=None, d2=d2, d1=d1, q=bands.observed_order(d2, d1), **parts)
        record["class"] = bands.classify(d2, d1, parts["theta"], world.p)
        if not identity:
            size = legacy["entries"][entry.name]["largest"]
            ratio = registration.ratio(world.name, entry.name)
            distance = ratio * size
            record.update(ratio=ratio, largest_L3=size, planted_distance=distance)
            record["tested"] = parts["beta"] <= distance / c.POWER_FACTOR
            record["truncation_is_larger"] = 2 * U_c > parts["beta"] - 2 * U_c
        out[entry.name] = record
    return out


def mechanisms(registration: Registration, families, table: dict) -> dict:
    """Mechanism to whether a home entry of one of the families tests it, and which do (CRITERIA
    section 4.5).
    """
    out = {}
    for family in families:
        for mechanism, homes in registration.mechanisms(family.world.name).items():
            found = out.setdefault(mechanism, {"tested": False, "by": 0, "first": None})
            for home in homes:
                record = table.get(family.name, {}).get(home, {})
                if record.get("tested"):
                    found["tested"] = True
                    found["by"] += 1
                    found["first"] = found["first"] or [family.name, home]
    return out


def sets_of(registration: Registration, consumer: str) -> dict:
    """The sets in which a consumer is reported: one, or `base`'s two (CRITERIA section 8)."""
    families = registration.by_consumer[consumer]
    seen = registration.profile.get("not_blind", {}).get(consumer)
    if not seen:
        return {"all": families}
    return {
        "blind": [f for f in families if f.name not in seen],
        "not blind": [f for f in families if f.name in seen],
    }


def stage1(tables: Tables, c0: dict, hashes: dict, first: dict | None = None) -> dict:
    """Stage 1: power. With `first` (the first pass's record), only what it owes the retry, on the
    new triples.
    """
    registration = tables.reg
    if c0.get("kind") != c.C0_KIND or c0.get("status") != "pass":
        raise OrderFault("C0 did not pass, so no table is judged")
    if c0["spec_sha256"] != registration.files:
        raise OrderFault("C0 read other spec files")
    table = {}
    for family in registration.families.values():
        if first is None:
            table[family.name] = estimates(tables, family, family.runs, family.steps_s, c0)
        elif family.retry_name in tables.states:
            names = (*family.runs[1:], family.retry_name)
            steps = (*family.steps_s[1:], family.retry_step)
            owed = first["retry_owed"]["why"][family.name]
            wanted = {reason.split(":")[0] for reason in owed}
            full = estimates(tables, family, names, steps, c0)
            table[family.name] = {name: record for name, record in full.items() if name in wanted}
    out = {
        "kind": c.POWER_KIND,
        "protocol": c.PROTOCOL,
        "part": c.PART,
        "pass": 1 if first is None else 2,
        "hashes": hashes,
        "guard_a": tables.guard_a,
        "runs": {
            name: {"judged": s.judgable, "refused": s.refused, "stopped": s.stopped}
            for name, s in tables.states.items()
        },
        "families": table,
    }
    if first is None:
        out["mechanisms"] = {
            consumer: {
                which: mechanisms(registration, families, table)
                for which, families in sets_of(registration, consumer).items()
            }
            for consumer in registration.consumers
        }
    return strictjson.plain(out)


# ----- stage 2 -----


class Stage2:
    """The scores: every entry, every plant, every verdict."""

    def __init__(
        self,
        tables: Tables,
        c0: dict,
        power: dict,
        captures: Captures,
        planted: Planted,
        power2: dict | None = None,
        first: dict | None = None,
    ):
        self.tables, self.c0, self.power = tables, c0, power
        self.captures, self.planted = captures, planted
        self.reg = tables.reg
        self.power2 = power2
        self.first = first
        self.settled = tables.settlements.flags if tables.settlements else {}
        self.entries = []
        self.flags = []
        self.to_settle = []  # the flags that leave an entry at best inconclusive
        self.for_the_lead = []
        self._capture = {}
        self._reads = {}

    # ----- small helpers -----

    def flag(self, run, what, detail):
        """Tell the checker."""
        self.flags.append({"run": run, "what": what, "detail": detail})

    def tell(self, run, what, detail):
        """Tell the lead."""
        self.for_the_lead.append({"run": run, "what": what, "detail": detail})

    def open_flag(self, kind, where, owner, subject, detail, entries):
        """A flag to the checker that leaves `entries` at best inconclusive until it is settled
        (Amendment 2, item 5 (a) and readings 12 and 24). `where` is the consumer and the run.
        """
        consumer, run = where
        self.to_settle.append(
            {
                "id": f"{kind}; {owner}; {subject}",
                "kind": kind,
                "consumer": consumer,
                "run": run,
                "detail": detail,
                "entries": entries,
            }
        )

    def add(self, **record):
        """Record one judged or reported entry."""
        self.entries.append(record)
        return record

    def capture(self, family, step, entry):
        """A captured entry's array."""
        key = (family.name, step, entry.name)
        if key not in self._capture:
            self._capture[key] = self.captures.run(family, step).entry(entry)
        return self._capture[key]

    def star(self, family, entry):
        """L*."""
        return bands.extrapolate(
            self.capture(family, "h2", entry), self.capture(family, "h4", entry), c.LEGACY_ORDER
        )

    @staticmethod
    def place(array, entry):
        """Where an array's largest magnitude lies: [time, entity]."""
        t, e = np.unravel_index(int(np.argmax(np.abs(array))), array.shape)
        return [entry.times[t], entry.entities[e]]

    # ----- the run -----

    def run(self) -> dict:
        """Every score, then the plants, the retry and the verdicts."""
        self.guard_b()
        for family in self.reg.families.values():
            self.class_S(family)
        for name, state in self.tables.states.items():
            run = state.run
            if self.reg.is_pool(run):
                if run["role"] == "judged":
                    self.pool_run(name, state)
                else:
                    self.pool_restart(name, state)
                continue
            self.class_R(name, state)
            self.class_E(name, state)
            if run["role"] == "support":
                self.restart(name, state)
        for name, state in self.tables.states.items():
            self.class_D(name, state)
            if state.second_pass:  # Amendment 2, item 8 (a)
                self.tell(
                    name,
                    "the second pass of a stop completed",
                    f"the run was refused by the engine's check ({state.refusal_message}), and "
                    f"stays refused. The second pass completed where it was refused",
                )
        self.settle()
        plants = self.plants()
        owed = self.retry_owed()
        verdicts = self.verdicts(plants, owed)
        waits = self.guard_waits()
        pending = {}
        for item in self.entries:
            for flag in item.get("pending", ()):
                pending.setdefault(item["run"], []).append(flag)
        return strictjson.plain(
            {
                "kind": c.RECORD_KIND,
                "protocol": c.PROTOCOL,
                "part": c.PART,
                "pass": 1 if self.power2 is None else 2,
                "hashes": {
                    **self.power["hashes"],
                    **({} if self.power2 is None else {"retry": self.power2["hashes"]}),
                },
                "runs": {
                    name: dict(
                        state.record(),
                        verdict=verdicts["runs"].get(name),
                        **({"pending": sorted(set(pending[name]))} if name in pending else {}),
                    )
                    for name, state in self.tables.states.items()
                },
                "ignored": self.tables.ignored,
                "files": {
                    consumer: {
                        "sha256": f.sha256,
                        "refused": f.refusals,
                        "flags": f.flags,
                        "absent": f.absent,
                    }
                    for consumer, f in self.tables.tables.files.items()
                },
                "file_flags": self.tables.tables.flags
                + (self.tables.retry.flags if self.tables.retry else []),
                "entries": self.entries,
                "plants": plants,
                "flags": self.flags,
                "flags_to_settle": self.to_settle,
                "runs_pending_on_a_flag": sorted(pending),
                "copy_guard": self.tables.guard_hits,
                "for_the_lead": self.for_the_lead,
                "retry_owed": owed,
                "retry_owed_waits_on": waits,
                "where_nothing_is_judged": self.unseen(),
                "consumers": verdicts["consumers"],
                "part_1": verdicts["part"],
                "reference_files_opened": {**self.captures.opened, **self.planted.opened},
            }
        )

    def unseen(self) -> dict:
        """The four places where a fail can go unseen, by name (CRITERIA section 5)."""
        states = self.tables.states
        lost = {n for n, s in states.items() if not s.judgable}
        return {
            "a departing echo": [n for n, s in states.items() if s.echo],
            "in `missing` or in neither list": [n for n, s in states.items() if s.missing],
            "a file refused whole": {
                k: f.refusals for k, f in self.tables.tables.files.items() if f.refusals
            },
            "a missing or doubled row or leaf": [
                [e["run"], e["readout"], e.get("why")]
                for e in self.entries
                if e["judged"] and e["outcome"] == c.NOT_FORMED and e["run"] not in lost
            ],
        }

    def guard_b(self):
        """Comparison (b): a run whose class S rows all equal the captured rows of its own world at
        a captured step.
        """
        for name, state in self.tables.states.items():
            run = state.run
            if (
                not state.judgable
                or self.reg.is_pool(run)
                or run["role"] == "support"
                or run["family"] not in self.reg.families
            ):
                continue
            rows = self.tables.guard_rows(name)
            if rows is None:
                continue
            family = self.reg.families[run["family"]]
            for step in STEPS:
                entries = family.world.guard_entries()
                if all(
                    np.array_equal(mine, self.capture(family, step, entry))
                    for mine, entry in zip(rows, entries, strict=True)
                ):
                    self.tables.refuse_copy(
                        name, "b", f"its class S rows equal the captured rows at {step}"
                    )

    def guard_waits(self) -> list:
        """The copy guard's refusals that are not settled. `retry_owed.json` is written once, and
        after them (Amendment 2, reading 28).
        """
        return [
            [hit["run"], hit["comparison"]]
            for hit in self.tables.guard_hits
            if hit["settled"] is None
        ]

    # ----- class S -----

    def class_S(self, family):
        """The S entries and the energy identity of a family, on the triple that each is
        judged on.
        """
        world = family.world
        first = self.power["families"][family.name]
        second = (self.power2 or {}).get("families", {}).get(family.name, {})
        for entry in [*world.entries, world.energy]:
            est = second.get(entry.name, first[entry.name])
            self._class_S(family, entry, est, entry.name in second)

    def _class_S(self, family, entry, est, again):
        identity = entry.where == "identity"
        judged = (
            not identity or family.world.identities_judged
        )  # an order-2 world's identities are reported (SPEC section 8)
        record = {
            "consumer": family.consumer,
            "family": family.name,
            "run": family.retry_name if again else family.finest,
            "readout": entry.name,
            "class": "S",
            "judged": judged,
            "pass_of_the_judgement": 2 if again else 1,
        }
        if not est["formed"]:
            self.add(
                **record,
                outcome=c.NOT_FORMED if judged else c.REPORTED,
                why=est["why"],
                home=est["home"],
            )
            return
        names = est["runs"]
        Y2, Y3 = (self.tables.entry(name, entry) for name in names[1:])
        star = bands.extrapolate(Y2, Y3, family.world.p)
        gap = star if identity else star - self.star(family, entry)
        statistic = bands.largest(gap)
        outcome = bands.score(statistic, est["beta"], est["class"])
        why = None
        if outcome == c.INCONCLUSIVE:
            why = f"by order ({est['class']})"
        if outcome == c.PASS and est["tested"] is False:
            outcome, why = c.NOT_TESTED, "beta is above a tenth of the planted distance"
        state_form = est["e_store"] > 0 and est["beta_without_store"] < statistic <= est["beta"]
        if state_form:
            self.flag(
                record["run"],
                "state form",
                f"{family.name} {entry.name}: inside the band with e_store and outside the one "
                f"without",
            )
        stopped = [n for n in names if self.tables.states[n].stopped]
        item = self.add(
            **record,
            **({"on_a_stopped_runs_rows": stopped} if stopped else {}),
            outcome=outcome if judged else c.REPORTED,
            reported=None if judged else outcome,
            why=why,
            statistic=statistic,
            band=est["beta"],
            ratio=statistic / est["beta"] if est["beta"] else None,
            at=self.place(gap, entry),
            d1=est["d1"],
            d2=est["d2"],
            q=est["q"],
            order_class=est["class"],
            U_c=est["U_c"],
            U_l=est["U_l"],
            band_without_store=est["beta_without_store"],
            state_form=state_form,
            planted_distance=est.get("planted_distance"),
            tested=est["tested"],
            home=est["home"],
            runs=names,
            S_c=est["S_c"],
        )
        if (
            judged
            and est["tested"] is False
            and est["class"] == OUTSIDE
            and statistic > est["beta"]
        ):
            self._corner(family, item, est)

    def _corner(self, family, item, est):
        """An untested entry that is resolved outside its window and above beta: inconclusive by
        order, flagged with its error (Amendment 2, item 5 (a)). What the retry's triple gives is at
        best inconclusive until the flag is settled.
        """
        self.open_flag(
            c.CORNER,
            (family.consumer, item["run"]),
            family.name,
            item["readout"],
            {
                "pass_of_the_judgement": item["pass_of_the_judgement"],
                "statistic": item["statistic"],
                "band": item["band"],
                "d1": est["d1"],
                "d2": est["d2"],
                "q": est["q"],
            },
            [],
        )

    # ----- class R -----

    def class_R(self, name, state):
        """The balances and the capacitor of an ionic run, against its own grid's steps (CRITERIA
        section 4.2).
        """
        run = state.run
        world = self.reg.worlds[run["world"]]
        judged = run["role"] in ("judged", "retry") and world.identities_judged
        steps = world.steps(run["step_s"])
        times = world.identity_times
        items = []
        for species in world.species:
            for kind, residual, entities in (
                ("cells", identities.cell_residual, world.cells),
                ("regions", identities.region_residual, world.regions),
                ("closed world", identities.closed_residual, ("world",)),
            ):
                bound = identities.balance_bound(world, kind, species, steps)
                items.append(
                    (
                        f"balance of {kind}, {species}",
                        lambda rows, at, r=residual, x=species: r(world, rows, x, at),
                        times,
                        bound,
                        entities,
                    )
                )
        bound = identities.capacitor_bound(world, steps)
        items.append(
            (
                "capacitor",
                lambda rows, at: identities.capacitor_residual(world, rows, at),
                world.potential_times,
                bound,
                world.membranes,
            )
        )
        start = self.reg.restart_time(run)
        for readout, residual, at, (limit, without), entities in items:
            if start is not None:
                at = tuple(t for t in at if t > start + c.TIME_TOL_S)
            record = {
                "consumer": run["consumer"],
                "family": run["family"],
                "run": name,
                "readout": readout,
                "class": "R",
                "judged": judged,
            }
            try:
                rows = self.tables.rows(name)
                if not at:
                    raise NotFormed("no compared time")
                value = residual(rows, at)
                partial = None
            except NotFormed as error:
                value, partial = self._partial(state, residual, at), str(error)
            if value is None:
                self.add(**record, outcome=c.NOT_FORMED if judged else c.REPORTED, why=partial)
                continue
            with np.errstate(all="ignore"):
                over = np.abs(value) if limit == 0 else np.abs(value) / limit
            statistic = bands.largest(value)
            good = statistic <= limit
            entity_max = {entity: float(np.max(over[:, i])) for i, entity in enumerate(entities)}
            outcome = c.PASS if good else c.FAIL
            if good and partial is not None:
                outcome = c.NOT_FORMED
            if good and limit > without and statistic > without:
                self.flag(
                    name,
                    "state form",
                    f"{readout}: inside the band with e_store and outside the one without",
                )
            if not judged and outcome == c.FAIL:
                self.flag(
                    name,
                    "a miss of an identity that is reported and not judged",
                    f"{readout}: {statistic!r} against {limit!r}",
                )
            self.add(
                **record,
                outcome=outcome if judged else c.REPORTED,
                reported=None if judged else outcome,
                why=partial,
                statistic=statistic,
                band=limit,
                ratio=statistic / limit if limit else None,
                band_without_store=without,
                by_entity=entity_max,
                zero_scale=limit == 0.0,
            )

    def _partial(self, state, residual, times):
        """A residual on the rows that a refused or stopped run holds, or None (CRITERIA section 5:
        a refusal never hides a fail).
        """
        if not state.partial:
            return None
        rows = self.tables.rows(state.name)
        held = rows.held(times)
        try:
            return residual(rows, held) if held else None
        except NotFormed:
            held = tuple(t for t in held if t in rows.held(times, "potential_t"))
            try:
                return residual(rows, held) if held else None
            except NotFormed:
                return None

    # ----- class E -----

    def class_E(self, name, state):
        """The structural zeros, the switch list, the channel schedule and the recorded seeds of an
        ionic run.
        """
        run = state.run
        world = self.reg.worlds[run["world"]]
        judged = run["role"] in (
            "judged",
            "retry",
        )  # a retry run's class E entries are judged (Amendment 2, item 3)
        for entry in world.zeros:
            record = {
                "consumer": run["consumer"],
                "family": run["family"],
                "run": name,
                "readout": f"{entry.name} is zero",
                "class": "E",
                "judged": judged,
            }
            if run["role"] == "support":
                continue
            self._zero(record, name, state, entry)
        if not world.assembly or run["role"] == "support":
            return
        paths = self.reg.expected_paths(run)
        record = {
            "consumer": run["consumer"],
            "family": run["family"],
            "run": name,
            "class": "E",
            "judged": judged,
        }
        inputs = state.entry.get("inputs") if state.judgable else None
        assembly = inputs.get("assembly") if isinstance(inputs, dict) else None
        controls = inputs.get("controls") if isinstance(inputs, dict) else None

        def switches():
            listed = assembly.get("switch_list") if isinstance(assembly, dict) else None
            if not isinstance(listed, dict):
                raise NotFormed("inputs.assembly.switch_list is missing or mistyped")
            return {
                channel: self._schedule(listed.get(channel), f"switch_list.{channel}")
                for channel in paths
            }

        def schedules():
            declared = controls.get("channel", {}) if isinstance(controls, dict) else {}
            declared = {} if declared == [] else declared
            if not isinstance(declared, dict):
                raise NotFormed("inputs.controls.channel is mistyped")
            return {
                channel: self._schedule(
                    declared.get(channel, [[0.0, 1.0]]), f"controls.channel.{channel}"
                )
                for channel in paths
            }

        def seeds():
            held = assembly.get("pool_seeds") if isinstance(assembly, dict) else None
            if not isinstance(held, dict):
                raise NotFormed("inputs.assembly.pool_seeds is missing or mistyped")
            out = {}
            for cell in world.pools:
                if not strictjson.is_integer(held.get(cell)):
                    raise NotFormed(f"inputs.assembly.pool_seeds.{cell} is missing or mistyped")
                out[cell] = held[cell]
            return out

        wanted = {channel: changes(path) for channel, path in paths.items()}
        wanted_seeds = {
            cell: pool["seeds"][run["seed_index"]] for cell, pool in world.pools.items()
        }
        for readout, read, expected in (
            ("switch list", switches, wanted),
            ("channel schedule", schedules, wanted),
            ("pool seeds", seeds, wanted_seeds),
        ):
            self._equal(record, readout, state, read, expected)

    @staticmethod
    def _schedule(value, what):
        parsed = parse_schedule(value)
        if parsed is None:
            raise NotFormed(f"inputs.{what} is missing or mistyped")
        return changes(parsed)

    def _equal(self, record, readout, state, read, expected):
        """One class E entry of leaves: equal as numbers, or not formed."""
        judged = record["judged"]
        if not state.judgable:
            self.add(
                **record,
                readout=readout,
                outcome=c.NOT_FORMED if judged else c.REPORTED,
                why="; ".join(state.causes()),
            )
            return
        try:
            held = read()
        except NotFormed as error:
            self.add(
                **record,
                readout=readout,
                outcome=c.NOT_FORMED if judged else c.REPORTED,
                reported=None if judged else c.NOT_FORMED,
                why=str(error),
            )
            return
        good = held == expected
        outcome = c.PASS if good else c.FAIL
        why = None if good else f"held {held!r}, expected {expected!r}"[:400]
        if not judged and not good:
            self.flag(record["run"], "a class E entry of a run that owns none", readout)
        self.add(
            **record,
            readout=readout,
            outcome=outcome if judged else c.REPORTED,
            reported=None if judged else outcome,
            why=why,
        )

    def _zero(self, record, name, state, entry):
        """A structural zero, every row of the run."""
        judged = record["judged"]
        try:
            rows = self.tables.rows(name)
            rows.index(entry.times)
            every = rows._table(
                rows.rows, "rows", entry.series, entry.entities, range(len(rows._times("t"))), "t"
            )
        except NotFormed as error:
            every = None
            if state.partial:
                try:
                    rows = self.tables.rows(name)
                    every = rows._table(
                        rows.rows,
                        "rows",
                        entry.series,
                        entry.entities,
                        range(len(rows._times("t"))),
                        "t",
                    )
                except NotFormed:
                    every = None
            if every is None or not np.any(every):
                self.add(**record, outcome=c.NOT_FORMED if judged else c.REPORTED, why=str(error))
                return
        good = not np.any(every)
        outcome = c.PASS if good else c.FAIL
        self.add(
            **record,
            outcome=outcome if judged else c.REPORTED,
            reported=None if judged else outcome,
            statistic=bands.largest(every),
            band=0.0,
        )

    def restart(self, name, state):
        """A restart's E entries: equal to the uninterrupted run of the same step, after its time
        (CRITERIA section 4.1).
        """
        run = state.run
        start = self.reg.restart_time(run)
        if start is None:
            return
        world = self.reg.worlds[run["world"]]
        owner = self.reg.restarted(run)
        if owner is None:
            self.flag(name, "restart", "no registered run is the one that it resumes")
            return
        at_fault = None
        if state.judgable:
            held = state.entry.get("restart")
            good = (
                isinstance(held, dict)
                and strictjson.is_finite(held.get("time_s"))
                and abs(held["time_s"] - start) <= c.TIME_TOL_S
            )
            at_fault = None if good else "its `restart` does not hold the registered time"
            if good and not isinstance(held.get("through"), str):
                self.flag(name, "restart", "`through` is missing or mistyped")
            if good and not strictjson.is_integer(held.get("step_index")):
                self.flag(name, "restart", "`step_index` is missing or mistyped")
        differs = []
        for entry in world.entries:
            record = {
                "consumer": run["consumer"],
                "family": self.reg.runs[owner]["family"],
                "run": owner,
                "support": name,
                "readout": f"restart {entry.name}",
                "class": "E",
                "judged": True,
            }
            key = "potential_t" if entry.where == "potentials" else "t"
            after = [t for t in entry.times if t > start + c.TIME_TOL_S]
            if state.stopped:
                if not at_fault:
                    differs.append(self._differences(name, owner, entry, after, key))
                self.add(**record, outcome=c.NOT_FORMED, why=at_fault or ANOTHER_PATH)
                continue
            try:
                if at_fault:
                    raise NotFormed(at_fault)
                rows = self.tables.rows(name)
                optional = [t for t in entry.times if abs(t - start) <= c.TIME_TOL_S]
                times = [t for t in optional if rows.held((t,), key)] + after
                if not times:
                    raise NotFormed("no compared time after the restart's time")
                mine = self._at(name, entry, times)
                whole = self._at(owner, entry, times)
            except NotFormed as error:
                missed = at_fault is None and self._partial_restart(state, owner, entry, after, key)
                self.add(**record, outcome=c.FAIL if missed else c.NOT_FORMED, why=str(error))
                continue
            good = np.array_equal(mine, whole)
            self.add(
                **record,
                outcome=c.PASS if good else c.FAIL,
                why=None,
                statistic=bands.largest(mine - whole),
                band=0.0,
            )
        if state.stopped:
            self._tell_differences(name, owner, [d for d in differs if d])
        self._reload(name, state, owner)

    def _reload(self, name, state, owner):
        """A restart's entries are the checker's to confirm: the run's own record shows that it
        reloaded a written checkpoint, and without that they are inconclusive (CRITERIA section 4.1,
        Amendment 2, reading 25). A passing one waits.
        """
        mine = [e for e in self.entries if e.get("support") == name]
        if any(e["outcome"] == c.PASS for e in mine):
            held = state.entry.get("restart")
            self.open_flag(
                c.RELOAD,
                (state.consumer, name),
                name,
                owner,
                {"restart": held, "to_confirm": "its record shows the reload of a checkpoint"},
                mine,
            )

    def _tell_differences(self, name, owner, differs):
        """What a support run that a check stopped shows beside the run that it resumes: for the
        checker and for the lead (Amendment 2, reading 13).
        """
        what = "a support run that a check stopped: its rows are another path's"
        detail = {"resumes": owner, "differences_on_the_rows_that_it_holds": differs}
        self.flag(name, what, detail)
        self.tell(name, what, detail)

    def _differences(self, name, owner, entry, times, key):
        """How the rows that two runs both hold differ, or None where nothing is held."""
        mine, whole = self.tables.states[name], self.tables.states[owner]
        if not (mine.judgable and whole.judgable):
            return None
        both = self.tables.rows(owner).held(times, key)
        held = [t for t in self.tables.rows(name).held(times, key) if t in both]
        try:
            gap = self._at(name, entry, held) - self._at(owner, entry, held) if held else None
        except NotFormed:
            return None
        if gap is None:
            return None
        return {
            "readout": entry.name,
            "compared_times": len(held),
            "unequal_values": int(np.count_nonzero(gap)),
            "largest": bands.largest(gap),
        }

    def _at(self, name, entry, times):
        rows = self.tables.rows(name)
        if entry.where == "potentials":
            return rows.potential(entry.series, times)
        return rows.get(entry.series, times)

    def _partial_restart(self, state, owner, entry, times, key) -> bool:
        """True where one of the two runs is refused or stopped, and the rows that both hold already
        differ.
        """
        whole = self.tables.states[owner]
        if not (state.judgable and whole.judgable and (state.partial or whole.partial)):
            return False
        mine = self.tables.rows(state.name)
        held = [t for t in mine.held(times, key) if t in self.tables.rows(owner).held(times, key)]
        try:
            return bool(held) and not np.array_equal(
                self._at(state.name, entry, held), self._at(owner, entry, held)
            )
        except NotFormed:
            return False

    # ----- the pools -----

    @staticmethod
    def _array(entry, cell, name, shape):
        pool = entry.get("pool")
        arrays = (
            pool.get(cell, {}).get("arrays")
            if isinstance(pool, dict) and isinstance(pool.get(cell), dict)
            else None
        )
        value = arrays.get(name) if isinstance(arrays, dict) else None
        out = []

        def walk(item, depth):
            if depth == len(shape):
                # One array is of booleans, and no other (Amendment 2, item 7 (d)).
                if isinstance(item, bool) and name == c.BOOLEAN_ARRAY:
                    out.append(int(item))
                elif strictjson.is_finite(item) and name != c.BOOLEAN_ARRAY:
                    out.append(item)
                else:
                    raise NotFormed(f"pool.{cell}.arrays.{name} holds {item!r}")
                return
            if not isinstance(item, list) or len(item) != shape[depth]:
                raise NotFormed(
                    f"pool.{cell}.arrays.{name} is missing, or not of shape {list(shape)}"
                )
            for part in item:
                walk(part, depth + 1)

        walk(value, 0)
        return out

    @staticmethod
    def _path(entry, cell, world_ids):
        path = entry.get("path")
        table = path.get(cell) if isinstance(path, dict) else None
        if not isinstance(table, dict):
            raise NotFormed(f"path.{cell} is missing or mistyped")
        out = {}
        for wid in world_ids:
            events = parse_schedule(table.get(wid))
            if events is None:
                raise NotFormed(f"path.{cell}.{wid} is missing or mistyped")
            out[wid] = events
        return out

    def pool_run(self, name, state):
        """A pool run's arrays, its own path and seed (class E), and its exposures (class R)."""
        run = state.run
        world = self.reg.worlds[run["world"]]
        seed = run["seed_index"]
        marked = name in self.reg.profile.get("not_blind_pool_runs", [])
        for cell, pool in world.pools.items():
            base = {
                "consumer": run["consumer"],
                "family": None,
                "run": name,
                "judged": True,
                "cell": cell,
            }
            if marked:
                base["holds_worlds_that_are_not_blind"] = True
            ids = [str(pool["pool"]["world_id_start"] + i) for i in range(pool["pool"]["worlds"])]
            captured = self.captures.pool_arrays(run["world"], seed, cell)
            for array in c.POOL_ARRAYS:
                record = {**base, "readout": f"{cell} {array}", "class": "E"}
                try:
                    self.tables.rows(name)
                    if state.cut:
                        raise NotFormed(CUT)
                    mine = self._array(state.entry, cell, array, captured[array].shape)
                except NotFormed as error:
                    self.add(**record, outcome=c.NOT_FORMED, why=str(error))
                    continue
                theirs = captured[array].ravel().tolist()
                wrong = [i for i, (a, b) in enumerate(zip(mine, theirs, strict=True)) if a != b]
                self.add(
                    **record,
                    outcome=c.FAIL if wrong else c.PASS,
                    why=None,
                    unequal=len(wrong),
                    of=len(theirs),
                    at=wrong[:1] or None,
                )
            record = {**base, "readout": f"{cell} path", "class": "E"}
            path = None
            try:
                self.tables.rows(name)
                path = self._path(state.entry, cell, ids)
                reference = {
                    wid: self.reg.reference_path(run["world"], seed, cell, wid) for wid in ids
                }
                wrong = [wid for wid in ids if path[wid] != reference[wid]]
                if state.cut:
                    # What a refusal cut is not formed. Any other difference is a fail.
                    wrong = [w for w in ids if path[w] != reference[w][: len(path[w])]]
                    path = None
                    if not wrong:
                        raise NotFormed(CUT)
                self.add(
                    **record,
                    outcome=c.FAIL if wrong else c.PASS,
                    why=f"worlds {wrong}" if wrong else None,
                )
            except NotFormed as error:
                self.add(**record, outcome=c.NOT_FORMED, why=str(error))
            record = {**base, "readout": f"{cell} seed", "class": "E"}
            try:
                self.tables.rows(name)
                held = state.entry["inputs"][cell].get("seed")
                if not strictjson.is_integer(held):
                    raise NotFormed(f"inputs.{cell}.seed is missing or mistyped")
                self.add(
                    **record, outcome=c.PASS if held == pool["seeds"][seed] else c.FAIL, why=None
                )
            except NotFormed as error:
                self.add(**record, outcome=c.NOT_FORMED, why=str(error))
            record = {**base, "readout": f"{cell} exposure", "class": "R"}
            if path is None:
                why = CUT if state.cut else "its path is not formed"
                self.add(**record, outcome=c.NOT_FORMED, why=why)
                continue
            exposure, segments = self.captures.exposure(run["world"], seed, cell)
            worst, missed, ratio = None, [], 0.0
            for i, wid in enumerate(ids):
                value = identities.exposure(path[wid], world.end_s)
                bound = identities.exposure_bound(world.end_s, segments[i])
                gap = abs(value - float(exposure[i]))
                if not gap <= bound:
                    missed.append(wid)
                if worst is None or gap / bound > ratio:
                    worst, ratio = [gap, bound, wid], gap / bound
            self.add(
                **record,
                outcome=c.FAIL if missed else c.PASS,
                why=f"worlds {missed}" if missed else None,
                statistic=worst[0],
                band=worst[1],
                ratio=ratio,
                at=worst[2],
            )

    def pool_restart(self, name, state):
        """A pool restart's arrays, and its path after the restart's time, equal to the
        uninterrupted run's (class E).
        """
        run = state.run
        start = self.reg.restart_time(run)
        if start is None:
            return
        world = self.reg.worlds[run["world"]]
        owner = self.reg.restarted(run)
        if owner is None:
            self.flag(name, "restart", "no registered run is the one that it resumes")
            return
        whole = self.tables.states[owner]
        fault = None
        if state.judgable:
            held = state.entry.get("restart")
            good = (
                isinstance(held, dict)
                and strictjson.is_finite(held.get("time_s"))
                and abs(held["time_s"] - start) <= c.TIME_TOL_S
            )
            fault = None if good else "its `restart` does not hold the registered time"
            if good and not isinstance(held.get("through"), str):
                self.flag(name, "restart", "`through` is missing or mistyped")
            if good and held.get("step_index") is not None:
                self.flag(
                    name,
                    "restart",
                    "`step_index` is not null in a pool restart (Amendment 1, item 2)",
                )
            for cell, pool in world.pools.items():
                if state.entry["inputs"][cell].get("seed") != pool["seeds"][run["seed_index"]]:
                    self.flag(name, "seed", f"inputs.{cell}.seed is not the registered seed")
        cut = state.cut or whole.cut
        differs = []
        for cell, pool in world.pools.items():
            ids = [str(pool["pool"]["world_id_start"] + i) for i in range(pool["pool"]["worlds"])]
            base = {
                "consumer": run["consumer"],
                "family": None,
                "run": owner,
                "support": name,
                "judged": True,
                "class": "E",
                "cell": cell,
            }
            if owner in self.reg.profile.get("not_blind_pool_runs", []):
                base["holds_worlds_that_are_not_blind"] = True
            shapes = {
                array: self.captures.pool_arrays(run["world"], run["seed_index"], cell)[array].shape
                for array in c.POOL_ARRAYS
            }
            for array in c.POOL_ARRAYS:
                record = {**base, "readout": f"restart {cell} {array}"}
                try:
                    if fault:
                        raise NotFormed(fault)
                    self.tables.rows(name)
                    self.tables.rows(owner)
                    if state.stopped:
                        raise NotFormed(ANOTHER_PATH)
                    if cut:
                        raise NotFormed(CUT)
                    mine = self._array(state.entry, cell, array, shapes[array])
                    theirs = self._array(whole.entry, cell, array, shapes[array])
                    self.add(**record, outcome=c.PASS if mine == theirs else c.FAIL, why=None)
                except NotFormed as error:
                    self.add(**record, outcome=c.NOT_FORMED, why=str(error))
            record = {**base, "readout": f"restart {cell} path"}
            try:
                if fault:
                    raise NotFormed(fault)
                self.tables.rows(name)
                self.tables.rows(owner)
                mine, theirs = (
                    self._path(state.entry, cell, ids),
                    self._path(whole.entry, cell, ids),
                )
                after = {
                    w: tuple([e for e in path[w] if e[0] > start] for path in (mine, theirs))
                    for w in ids
                }
                wrong = [w for w, (a, b) in after.items() if a != b]
                if state.stopped or cut:
                    # What a refusal cut is not formed. Any other difference of a path is a fail,
                    # but in a run that a check stopped, whose path is another execution's.
                    wrong = [w for w, (a, b) in after.items() if not begins(a, b)]
                    if state.stopped:
                        differs.append({"cell": cell, "worlds_that_differ": wrong})
                        raise NotFormed(ANOTHER_PATH)
                    if not wrong:
                        raise NotFormed(CUT)
                self.add(
                    **record,
                    outcome=c.FAIL if wrong else c.PASS,
                    why=f"worlds {wrong}" if wrong else None,
                )
            except NotFormed as error:
                self.add(**record, outcome=c.NOT_FORMED, why=str(error))
        if state.stopped:
            self._tell_differences(name, owner, differs)
        self._reload(name, state, owner)

    # ----- class D -----

    def class_D(self, name, state):
        """Completion (CRITERIA section 4.4). A stop fails. D is not formed for a refusal of kind
        `definition`, `domain` or `harness`. It is for a run that is refused for its provenance, by
        the copy guard or for two lists (Amendment 2, reading 16): it passes if the run completed.
        """
        run = state.run
        if run["role"] not in ("judged", "retry"):
            return
        record = {
            "consumer": run["consumer"],
            "family": run["family"],
            "run": name,
            "readout": "completes",
            "class": "D",
            "judged": True,
        }
        if not state.judgable:
            self.add(**record, outcome=c.NOT_FORMED, why="; ".join(state.causes()))
        elif state.stopped:
            self.add(**record, outcome=c.FAIL, why=state.refusal_message)
        elif state.completed and state.refusal_kind is None:
            self.add(**record, outcome=c.PASS, why=None)
        else:
            self.add(**record, outcome=c.NOT_FORMED, why="refused: D is not judged")

    # ----- the flags that the checker settles -----

    def settle(self):
        """The flags that leave an entry at best inconclusive until the checker settles them
        (Amendment 2, item 5 (a) and readings 12, 24 and 25). A settled one counts as the checker
        says.
        """
        for name, state in self.tables.states.items():
            run = state.run
            if not state.judgable or self.reg.is_pool(run) or run["role"] == "plant":
                continue
            if run["role"] in ("judged", "retry"):
                self._rows_at_time_0(name, state)
            self._values_not_finite(name, state)
        if self.first is not None:
            self._corners_again()
        unknown = set(self.settled) - {item["id"] for item in self.to_settle}
        if unknown:
            raise OrderFault(f"a settlement of a flag that is not there: {sorted(unknown)[:3]}")
        touched = {}
        for item in self.to_settle:
            item["settled"] = self.settled.get(item["id"])
            for entry in item["entries"]:
                touched.setdefault(id(entry), (entry, []))[1].append(item)
            item["entries"] = [[e["run"], e["readout"], e["class"]] for e in item["entries"]]
        for entry, items in touched.values():
            self._settle(entry, items)

    @staticmethod
    def _settle(entry, items):
        """What an entry counts as, with its flags. A fail by the rule stays a fail, and what is not
        formed or inconclusive stays so but for a flag that the checker settles as a fail.
        """
        entry["by_rule"] = entry["outcome"]
        entry["flags"] = [item["id"] for item in items]
        waiting = [item["id"] for item in items if item["settled"] is None]
        said = {item["settled"]["counts_as"] for item in items if item["settled"]}
        if entry["outcome"] == c.FAIL:
            return
        if c.FAIL in said:
            entry.update(outcome=c.FAIL, why="the checker settled a flag on it as a fail")
        elif entry["outcome"] in (c.PASS, c.NOT_TESTED) and c.INCONCLUSIVE in said:
            entry.update(
                outcome=c.INCONCLUSIVE, why="the checker settled a flag on it as inconclusive"
            )
        elif entry["outcome"] in (c.PASS, c.NOT_TESTED) and waiting:
            entry.update(
                outcome=c.INCONCLUSIVE,
                why=f"pending on {len(waiting)} flag(s) to the checker: {'; '.join(waiting)}",
                pending=waiting,
            )

    def _rows_at_time_0(self, name, state):
        """Reading 12: in a world whose capacitor is not read at time 0, a row of `n_cell_x` at time
        0 that is not zero.
        """
        world = self.reg.worlds[state.run["world"]]
        if any(abs(t) <= c.TIME_TOL_S for t in world.potential_times):
            return
        rows, times = state.entry.get("rows"), state.entry.get("t")
        if not isinstance(rows, dict) or not isinstance(times, list):
            return
        at_zero = np.flatnonzero(np.abs(column(times)) <= c.TIME_TOL_S)
        capacitor = [e for e in self.entries if e["run"] == name and e["readout"] == "capacitor"]
        for x in world.species:
            table, found = rows.get(f"n_cell_{x}"), {}
            for cell in world.cells:
                listed = table.get(cell) if isinstance(table, dict) else None
                if not isinstance(listed, list) or len(listed) != len(times):
                    continue
                values = column(listed)[at_zero]
                if np.any(np.isfinite(values) & (values != 0)):
                    found[cell] = values.tolist()
            if found:
                self.open_flag(
                    c.AT_ZERO,
                    (state.consumer, name),
                    name,
                    f"n_cell_{x}",
                    found,
                    [e for e in capacitor if e["judged"]],
                )

    def _reads_of(self, world) -> dict:
        """Readout to the series that it reads of a run, as (where, series) to its times."""
        if world.name not in self._reads:
            table = {}

            def reads(readout, where, names, times):
                for name in names:
                    held = table.setdefault(readout, {}).setdefault((where, name), set())
                    held.update(times)

            heats = identities.heat_series(world)
            amounts = [f"n_{side}_{x}" for side in ("cell", "out") for x in world.species]
            for entry in [*world.entries, *world.zeros]:
                names = [entry.series]
                if entry.where == "formed":
                    names = [h for h in heats if h in ("heat_leak", "heat_pump", "heat_channel")]
                where = "potentials" if entry.where == "potentials" else "rows"
                label = f"{entry.name} is zero" if entry in world.zeros else entry.name
                reads(label, where, names, entry.times)
            work = ["work_pump"] if world.pumps else []
            times = world.identity_times
            reads("energy_identity", "rows", [*amounts, *heats, *work], times)
            reads("energy_identity", "potentials", ["voltage"], (0.0,))
            for x in world.species:
                routes = [] if world.zero_routes else [f"leak_{x}"]
                if any(world.block["channels"][k]["species_id"] == x for k in world.channels):
                    routes.append(f"channel_{x}")
                routes += ["pump"] if world.pumps else []
                inner = [f"junction_{x}"] if world.junctions else []
                outer = [f"face_{x}"] if world.faces else []
                reads(f"balance of cells, {x}", "rows", [f"n_cell_{x}", *routes, *inner], times)
                reads(f"balance of regions, {x}", "rows", [f"n_out_{x}", *routes, *outer], times)
                both = [f"n_cell_{x}", f"n_out_{x}"]
                reads(f"balance of closed world, {x}", "rows", both, times)
            cells = [f"n_cell_{x}" for x in world.species]
            reads("capacitor", "rows", cells, world.potential_times)
            reads("capacitor", "potentials", ["voltage"], (0.0, *world.potential_times))
            self._reads[world.name] = table
        return self._reads[world.name]

    def _entries_of(self, name, state) -> list:
        """(entry, the readout that it reads, the times after which) of every judged entry that
        reads a run's rows: its family's S entries, its own R and E entries, and the E entries of a
        restart of it or by it.
        """
        out = []
        for entry in self.entries:
            if not entry["judged"]:
                continue
            readout, after = entry["readout"], -np.inf
            if entry.get("support"):
                if name not in (entry["support"], entry["run"]):
                    continue
                readout = readout.removeprefix("restart ")
                after = self.reg.restart_time(self.reg.runs[entry["support"]])
            elif entry["class"] == "S":
                if name not in entry.get("runs", ()):
                    continue
            elif entry["run"] != name or entry["class"] not in ("R", "E"):
                continue
            out.append((entry, readout, after))
        return out

    def _values_not_finite(self, name, state):
        """Reading 24: a value of a judged series that is no finite number at a time that no
        compared time is, and the entries that read the series of that run.
        """
        if not state.nonfinite:
            return
        world = self.reg.worlds[state.run["world"]]
        reads, read_by = self._reads_of(world), self._entries_of(name, state)
        for (where, series), table in state.nonfinite.items():
            times_key = "potential_t" if where == "potentials" else "t"
            times = column(state.entry[times_key])
            if not np.all(np.isfinite(times)):
                continue  # no compared time has a row
            entries, compared = [], set()
            for entry, readout, after in read_by:
                needs = reads.get(readout, {}).get((where, series))
                if needs is not None:
                    entries.append(entry)
                    compared |= {t for t in needs if t >= after - c.TIME_TOL_S}
            if not entries:
                continue
            found = {}
            for entity, rows in table.items():
                if entity not in world.entities(series):
                    continue
                others = [
                    i for i in rows if not any(abs(times[i] - t) <= c.TIME_TOL_S for t in compared)
                ]
                if others:
                    held = state.entry[where][series][entity]
                    found[entity] = [[float(times[i]), repr(held[i])] for i in others[:3]]
            if found:
                self.open_flag(
                    c.NOT_FINITE, (state.consumer, name), name, f"{where}.{series}", found, entries
                )

    def _corners_again(self):
        """The corner of item 5 (a) on the retry's triple: an entry that the first pass flagged and
        that is judged again is at best inconclusive until its flag is settled.
        """
        held = {item["id"]: item for item in self.to_settle if item["kind"] == c.CORNER}
        for item in self.first["flags_to_settle"]:
            if item["kind"] != c.CORNER:
                continue
            again = [
                e
                for e in self.entries
                if e["class"] == "S"
                and f"{c.CORNER}; {e['family']}; {e['readout']}" == item["id"]
                and e["pass_of_the_judgement"] == 2
            ]
            if item["id"] in held:  # it is there again, on the triple of the retry
                held[item["id"]]["detail"]["first"] = item["detail"]
                held[item["id"]]["entries"] = again
            else:
                self.to_settle.append(dict(item, entries=again))

    # ----- plants -----

    def _honest(self, family, entry_name):
        """What a plant needs of its honest family: its estimates, or why it is unscorable."""
        est = (self.power2 or {}).get("families", {}).get(family.name, {}).get(
            entry_name
        ) or self.power["families"][family.name][entry_name]
        bad = [
            n for n in est["runs"] if self.tables.states[n].refused or self.tables.states[n].stopped
        ]
        if bad:
            return None, f"the honest run {bad[0]} is refused or stopped"
        if not est["formed"]:
            return None, f"the named entry is not formed: {est['why']}"
        return est, None

    def plants(self) -> dict:
        """The structural and the engine plants (CRITERIA section 6)."""
        out = []
        for consumer, world, family, name, plant in self.reg.structural():
            step_s = self.captures.step_s(world.name, "h4")
            named = []
            for key in plant["named"]:
                entry = world.by_name[key]
                item = {"entry": key, "distance": plant[key]["distance"]}
                est, why = self._honest(family, key)
                if est is None:
                    named.append({**item, "score": "unscorable", "why": why})
                    continue
                star = bands.extrapolate(
                    *(self.tables.entry(n, entry) for n in est["runs"][1:]), world.p
                )
                statistic = bands.largest(
                    star - self.planted.run(plant["run"], family, step_s).entry(entry)
                )
                named.append(
                    {**item, **self._plant_score(item["distance"], est["beta"], statistic)}
                )
            out.append(
                {
                    "plant": name,
                    "kind": "structural",
                    "consumer": consumer,
                    "family": family.name,
                    "entries": named,
                    "score": overall(named),
                }
            )
        for consumer, run, name, plant, distances in self.reg.engine():
            out.append(self._engine(consumer, run, name, plant, distances))
        return {"plants": out}

    @staticmethod
    def _plant_score(distance, beta, statistic):
        out = {"band": beta, "statistic": statistic, "margin": distance / beta}
        if distance <= 2 * beta:
            return {
                **out,
                "score": "unscorable",
                "why": "its registered distance is at most 2 beta",
            }
        return {**out, "score": "caught" if statistic > beta else "not caught", "why": None}

    def _engine(self, consumer, run, name, plant, distances):
        family = self.reg.families[run["family"]]
        world, state = family.world, self.tables.states[run["name"]]
        out = {
            "plant": name,
            "kind": "engine",
            "consumer": consumer,
            "family": family.name,
            "run": run["name"],
            "causes": state.causes(),
        }

        def unscorable(why):
            return {
                **out,
                "entries": [
                    {"entry": k, "score": "unscorable", "why": why} for k in plant["named"]
                ],
                "score": "unscorable",
            }

        if not state.judgable:
            return unscorable("; ".join(state.causes()))
        if world.assembly:
            held = {
                e["readout"]: e
                for e in self.entries
                if e["run"] == run["name"] and e["class"] == "E"
            }
            for readout in ("switch list", "channel schedule", "pool seeds"):
                if held[readout].get("reported") != c.PASS:
                    return unscorable(f"its {readout} departs from what the plant declares")
        rows, honest = self.tables.guard_rows(run["name"]), None
        if self.tables.states[family.finest].judgable:
            honest = self.tables.guard_rows(family.finest)
        equal = (
            rows is not None
            and honest is not None
            and all(np.array_equal(a, b) for a, b in zip(rows, honest, strict=True))
        )
        if equal:
            why = "its class S rows equal the run it was planted in"
            return {
                **out,
                "entries": [
                    {"entry": k, "score": "not caught", "why": why} for k in plant["named"]
                ],
                "score": "not caught",
            }
        named = []
        for key in plant["named"]:
            entry = world.by_name[key]
            item = {"entry": key, "distance": distances[key]}
            est, why = self._honest(family, key)
            if est is None:
                named.append({**item, "score": "unscorable", "why": why})
                continue
            try:
                mine = self.tables.entry(run["name"], entry)
            except NotFormed as error:
                named.append(
                    {
                        **item,
                        "score": "unscorable",
                        "why": f"the named entry is not formed: {error}",
                    }
                )
                continue
            statistic = bands.largest(mine - self.star(family, entry))
            named.append({**item, **self._plant_score(distances[key], est["beta"], statistic)})
        score = overall(named)
        if score == "caught" and (state.refused or state.stopped):
            return {
                **out,
                "entries": named,
                "score": "unscorable",
                "why": "the plant's own run is refused",
            }
        return {**out, "entries": named, "score": score}

    # ----- the retry -----

    def retry_owed(self) -> dict:
        """What the retry is owed (CRITERIA section 7): the runs, and why, by family."""
        runs, why = [], {}
        if self.power2 is None:
            for family in self.reg.families.values():
                if any(
                    self.tables.states[n].refused or self.tables.states[n].stopped
                    for n in family.runs
                ):
                    continue
                reasons = []
                for item in self.entries:
                    if item["class"] != "S" or item["family"] != family.name or not item["judged"]:
                        continue
                    est = self.power["families"][family.name][item["readout"]]
                    outcome = item.get("by_rule", item["outcome"])  # a flag owes no retry
                    if outcome == c.INCONCLUSIVE:
                        reasons.append(f"{item['readout']}: order")
                    elif (
                        est.get("formed")
                        and est["home"]
                        and est["tested"] is False
                        and outcome != c.FAIL
                        and est["truncation_is_larger"]
                    ):
                        reasons.append(f"{item['readout']}: power")
                if reasons:
                    why[family.name] = sorted(reasons)
                    runs.append(family.retry_name)
        return {
            "kind": c.RETRY_KIND,
            "part": c.PART,
            "runs": sorted(runs),
            "why": dict(sorted(why.items())),
        }

    # ----- verdicts -----

    def _run_verdict(self, name, owned):
        state = self.tables.states[name]
        outcomes = [e["outcome"] for e in owned]
        if c.FAIL in outcomes:
            return c.FAIL
        if state.refused or any(o in (c.INCONCLUSIVE, c.NOT_FORMED) for o in outcomes):
            return c.INCONCLUSIVE
        return c.PASS

    def verdicts(self, plants, owed) -> dict:
        """Every run's verdict, every consumer's (in its sets), and the part's (CRITERIA
        section 8).
        """
        owned = {}
        for item in self.entries:
            if item["judged"]:
                owned.setdefault(item["run"], []).append(item)
        runs = {}
        for name, state in self.tables.states.items():
            if state.run["role"] in ("judged", "retry"):
                runs[name] = self._run_verdict(name, owned.get(name, []))
        consumers = {}
        for consumer in self.reg.consumers:
            sets = sets_of(self.reg, consumer)
            table = {
                which: self._set_verdict(consumer, families, runs, plants)
                for which, families in sets.items()
            }
            order = (c.FAIL, c.INCONCLUSIVE, c.PENDING, c.PASS)
            verdict = min((t["verdict"] for t in table.values()), key=order.index)
            state = min((t["state"] for t in table.values()), key=order.index)
            pending = sorted({flag for t in table.values() for flag in t["pending"]})
            judged = [e for e in self.entries if e["consumer"] == consumer and e["judged"]]
            counts = self._counts(consumer, self.reg.by_consumer[consumer], judged)
            published = self.reg.profile.get("counts", {}).get(consumer, {})
            for key, numbers in counts.items():
                numbers["published"] = published.get(key)
            families = self.reg.by_consumer[consumer]
            waiting = [f.retry_name for f in families if f.retry_name in owed["runs"]]
            copies = [
                hit["run"]
                for hit in self.tables.guard_hits
                if hit["consumer"] == consumer and hit["settled"] is None
            ]
            consumers[consumer] = {
                "verdict": verdict,
                "state": state,  # pending: nothing but unsettled flags keeps it from a pass
                "pending": pending,
                # An owed retry, an unsettled flag and an unsettled refusal by the copy guard leave
                # the verdict open.
                "final": not (waiting or pending or copies),
                "retry_owed": waiting,
                "steps_covered": self._steps_covered(families),
                "sets": table,
                "counts": counts,
            }
            note = self.reg.profile.get("notes", {}).get(consumer)
            if note:
                consumers[consumer]["note"] = note
        whole = {"consumers": {k: v["verdict"] for k, v in consumers.items()}}
        whole["passes"] = all(v == c.PASS for v in whole["consumers"].values())
        whole["pending"] = {k: v["pending"] for k, v in consumers.items() if v["pending"]}
        return {"runs": runs, "consumers": consumers, "part": whole}

    def _steps_covered(self, families) -> dict:
        """The steps that a pass covers (CRITERIA section 7): the families' three, and the triple of
        every entry judged again.
        """
        again = {}
        for item in self.entries:
            if (
                item["class"] == "S"
                and item.get("pass_of_the_judgement") == 2
                and item["family"] in {f.name for f in families}
            ):
                family = self.reg.families[item["family"]]
                again.setdefault(
                    family.name,
                    {"steps_s": [*family.steps_s[1:], family.retry_step], "entries": []},
                )["entries"].append(item["readout"])
        return {
            "steps_s": sorted({f.steps_s for f in families}, reverse=True),
            "judged_again": again,
        }

    def _set_verdict(self, consumer, families, runs, plants):
        names = {f.name for f in families}
        shared = [
            r for r in self.reg.runs.values() if r["consumer"] == consumer and r["family"] is None
        ]
        members = [n for f in families for n in self.tables.rungs(f)] + [
            r["name"] for r in shared if r["role"] == "judged"
        ]
        support = [
            r["name"]
            for r in shared
            if r["role"] == "support" and supported_family(self.reg, r) in names | {None}
        ]
        entries = [
            e
            for e in self.entries
            if e["consumer"] == consumer
            and e["judged"]
            and (e["family"] in names or e["family"] is None)
        ]
        its_plants = [p for p in plants["plants"] if p["consumer"] == consumer]
        reasons, fails, others = [], [], 0
        for name in members:
            if runs[name] == c.FAIL:
                fails.append(f"the run {name} fails")
        for plant in its_plants:
            if plant["score"] == "not caught":
                fails.append(f"the plant {plant['plant']} is not caught")
        for name in members + support:
            state = self.tables.states[name]
            if state.refused or state.stopped:
                reasons.append(
                    f"the run {name} is refused, missing or stopped: {'; '.join(state.causes())}"
                )
        others += len(reasons)
        waiting = [e for e in entries if e["outcome"] in (c.INCONCLUSIVE, c.NOT_FORMED)]
        pending = sorted({flag for e in waiting for flag in e.get("pending", ())})
        others += sum(1 for e in waiting if not e.get("pending"))
        for item in waiting[:20]:
            reasons.append(
                f"{item['run']}, {item['readout']}: {item['outcome']} ({item.get('why')})"
            )
        if len(waiting) > 20:
            reasons.append(
                f"and {len(waiting) - 20} more entries that are inconclusive or not formed"
            )
        found = self._mechanisms(families)
        before = len(reasons)
        for mechanism, record in found.items():
            if not record["tested"]:
                reasons.append(f"the mechanism {mechanism} is untested")
        for plant in its_plants:
            if plant["score"] == "unscorable":
                reasons.append(f"the plant {plant['plant']} is unscorable")
        counts = self._counts(consumer, families, entries)
        for name, numbers in counts.items():
            if numbers["formed"] < numbers["expected"]:
                reasons.append(
                    f"{numbers['formed']} entries of class {name} were formed, and "
                    f"{numbers['expected']} are listed"
                )
        others += len(reasons) - before
        verdict = c.FAIL if fails else c.INCONCLUSIVE if reasons else c.PASS
        only_pending = verdict == c.INCONCLUSIVE and pending and not others
        return {
            "verdict": verdict,
            "state": c.PENDING if only_pending else verdict,
            "pending": pending,
            "fails": fails,
            "inconclusive": reasons,
            "families": {f.name: self._family_summary(f, entries) for f in families},
            "members": {
                "families": len(families),
                "judged_runs": len(members),
                "pool_runs": [
                    r["name"] for r in shared if r["role"] == "judged" and self.reg.is_pool(r)
                ],
                "runs_of_no_family": [
                    r["name"] for r in shared if r["role"] == "judged" and not self.reg.is_pool(r)
                ],
                "support_runs": support,
                "plants": [p["plant"] for p in its_plants],
            },
            "counts": counts,
            "outcomes": self._outcomes(entries),
            "by_class": by_class(entries),
            "mechanisms": found,
            "not_tested": [
                [e["family"], e["readout"]] for e in entries if e["outcome"] == c.NOT_TESTED
            ],
            "failing_entries": [
                [e["run"], e["readout"], e["class"]] for e in entries if e["outcome"] == c.FAIL
            ],
        }

    def _mechanisms(self, families):
        table = {}
        for family in families:
            table[family.name] = dict(self.power["families"][family.name])
            table[family.name].update((self.power2 or {}).get("families", {}).get(family.name, {}))
        return mechanisms(self.reg, families, table)

    def _counts(self, consumer, families, entries):
        expected = expected_counts(self.reg, consumer, families)
        retried = [f for f in families if f.retry_name in self.tables.states]
        for family in retried:
            expected["D"] += 1
            expected["E"] += ionic_E(family.world)
            expected["R"] += ionic_R(family.world)
        formed = dict.fromkeys(expected, 0)
        for item in entries:
            if item["outcome"] in (c.NOT_FORMED, c.REPORTED):
                continue
            key = "energy" if item["readout"] == "energy_identity" else item["class"]
            formed[key] += 1
        return {name: {"formed": formed[name], "expected": expected[name]} for name in expected}

    @staticmethod
    def _outcomes(entries):
        out = {}
        for item in entries:
            table = out.setdefault(item["class"], {})
            table[item["outcome"]] = table.get(item["outcome"], 0) + 1
        return out

    @staticmethod
    def _family_summary(family, entries):
        mine = [e for e in entries if e["family"] == family.name]
        worst = max(
            (e for e in mine if e["class"] == "S" and e.get("ratio") is not None),
            key=lambda e: e["ratio"],
            default=None,
        )
        return {
            "verdict_of_its_entries": worst_of(mine),
            "by_class": by_class(mine),
            "outcomes": Stage2._outcomes(mine),
            "largest_S_ratio": None if worst is None else [worst["readout"], worst["ratio"]],
        }


def verdict_of(record) -> dict:
    """The verdicts alone, with the causes that they name."""
    return {
        "kind": "ensemble-reexpression verdicts, version 1",
        "protocol": record["protocol"],
        "part": record["part"],
        "pass_of_the_judgement": record["pass"],
        "hashes": record["hashes"],
        "consumers": record["consumers"],
        "part_1": record["part_1"],
        "plants": [
            {
                k: p.get(k)
                for k in ("plant", "kind", "consumer", "family", "score", "why", "entries")
            }
            for p in record["plants"]["plants"]
        ],
        "refusals": {n: s["causes"] for n, s in record["runs"].items() if s["causes"]},
        "refused_files": {k: f["refused"] for k, f in record["files"].items() if f["refused"]},
        "ignored_runs": record["ignored"],
        "where_nothing_is_judged": record["where_nothing_is_judged"],
        "flags_to_the_checker": len(record["flags"])
        + sum(len(s["flags"]) for s in record["runs"].values()),
        "flags_to_settle": record["flags_to_settle"],
        "runs_pending_on_a_flag": record["runs_pending_on_a_flag"],
        "copy_guard": record["copy_guard"],
        "for_the_lead": record["for_the_lead"],
        "retry_owed": record["retry_owed"]["runs"],
        "retry_owed_waits_on": record["retry_owed_waits_on"],
    }


def worst_of(entries) -> str:
    """Fail where one fails, inconclusive where one is inconclusive or not formed, else pass."""
    found = {e["outcome"] for e in entries}
    if c.FAIL in found:
        return c.FAIL
    return c.INCONCLUSIVE if found & {c.INCONCLUSIVE, c.NOT_FORMED} else c.PASS


def by_class(entries) -> dict:
    """The worst outcome of the entries of each class."""
    names = sorted({e["class"] for e in entries})
    return {name: worst_of([e for e in entries if e["class"] == name]) for name in names}


def overall(named) -> str:
    """A plant's score from its named entries: any not caught, then any unscorable, then caught
    (CRITERIA section 6).
    """
    scores = {item["score"] for item in named}
    if "not caught" in scores:
        return "not caught"
    return "unscorable" if "unscorable" in scores or not scores else "caught"


def check_power(tables: Tables, c0: dict, power: dict, hashes: dict, first: dict | None = None):
    """Stage 2 begins only where `power.json` is what stage 1 makes of these tables, and of the
    recorded hashes.
    """
    if power.get("kind") != c.POWER_KIND:
        raise OrderFault("power.json is not a power record")
    if power["hashes"] != hashes:
        raise OrderFault("power.json was made from other files")
    again = stage1(tables, c0, hashes, first)
    if again != power:
        raise OrderFault("power.json is not what stage 1 makes of these tables")
