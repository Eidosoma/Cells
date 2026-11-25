"""Stage 1 (power) and stage 2 (scores and verdicts), in the spec's order (CRITERIA sections 4 to 8).

Stage 1 reads the tables' own rows, the inputs' scales and C0's numbers of the captures. It opens no capture and forms no difference
between a candidate and a capture. Stage 2 forms those, and it needs `power.json` and its recorded sha256.
"""

from __future__ import annotations

import numpy as np

from . import bands, identities, strictjson
from . import constants as c
from .legacy import STEPS, Captures, Planted
from .registration import Registration, StringsNote, changes
from .table import NotFormed, RunRows, TableSet, assess, parse_schedule


class OrderFault(Exception):
    """A step of the judgement that is out of the spec's order, or whose inputs are not the recorded ones."""


# ----- counts (READOUTS sections 3 and 4) -----


def expected_counts(registration: Registration, consumer: str, families=None) -> dict:
    """The entries of a consumer by class. `families` restricts the families; the pool and support runs stay (CRITERIA section 8)."""
    chosen = registration.by_consumer[consumer] if families is None else families
    out = {"S": 0, "energy": 0, "R": 0, "E": 0, "D": 0}
    for family in chosen:
        world = family.world
        out["S"] += len(world.entries)
        out["D"] += 3
        if world.identities_judged:
            out["energy"] += 1
            out["R"] += 3 * (3 * len(world.species) + 1)
        out["E"] += 3 * len(world.zeros)
        if world.assembly:
            out["E"] += 3 * 3
    for run in registration.runs.values():
        if run["consumer"] != consumer:
            continue
        world = registration.worlds[run["world"]]
        pool = registration.is_pool(run)
        if run["role"] == "judged" and pool:
            out["D"] += 1
            out["R"] += len(world.pools)
            out["E"] += len(world.pools) * (len(c.POOL_ARRAYS) + 2)
        if run["role"] == "support" and registration.restart_time(run) is not None:
            out["E"] += len(world.pools) * (len(c.POOL_ARRAYS) + 1) if pool else len(world.entries)
    return out


# ----- what both stages read -----


class Tables:
    """The tables with every registered run's state, its rows on demand, and the copy guard's first comparison."""

    def __init__(self, registration: Registration, note: StringsNote, tables: TableSet, retry: TableSet | None = None, owed=()):
        faults = note.faults(registration)
        if faults:
            raise OrderFault(f"the strings note: {'; '.join(faults[:5])}")
        self.reg, self.note, self.tables, self.retry = registration, note, tables, retry
        self.states, self.ignored = assess(registration, note, tables, retry, owed)
        self.owed = tuple(owed)
        self._rows, self._arrays = {}, {}
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
                self._arrays[key] = NotFormed(str(error) if str(error).startswith(name) else f"{name}: {error}")
        if isinstance(self._arrays[key], NotFormed):
            raise NotFormed(str(self._arrays[key]))
        return self._arrays[key]

    def rungs(self, family) -> tuple:
        """The family's runs, and its retry run where that is owed."""
        retry = (family.retry_name,) if family.retry_name in self.states else ()
        return family.runs + retry

    def guard_rows(self, name: str):
        """Every class S row of a run at every compared time, or None where one of them is not there."""
        world = self.reg.worlds[self.states[name].run["world"]]
        try:
            return [self.entry(name, entry) for entry in world.guard_entries()]
        except NotFormed:
            return None

    def _guard_a(self) -> list:
        """Comparison (a): two rungs of one family whose class S rows are all exactly equal. Both are refused (CRITERIA section 5)."""
        out = []
        for family in self.reg.families.values():
            names = [n for n in self.rungs(family) if self.states[n].judgable]
            held = {name: self.guard_rows(name) for name in names}
            for i, first in enumerate(names):
                for second in names[i + 1 :]:
                    if held[first] is None or held[second] is None:
                        continue
                    if all(np.array_equal(a, b) for a, b in zip(held[first], held[second])):
                        out.append([family.name, first, second])
                        self.states[first].guard.append(["a", f"its class S rows equal {second}'s"])
                        self.states[second].guard.append(["a", f"its class S rows equal {first}'s"])
        return out


def estimates(tables: Tables, family, names, steps_s, c0: dict) -> dict:
    """Every S entry and the energy identity of a triple: the run's own differences, U_c, the order's class, beta and power."""
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
    """Mechanism to whether a home entry of one of the families tests it, and which do (CRITERIA section 4.5)."""
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
    """Stage 1: power. With `first` (the first pass's record), only what it owes the retry, on the new triples."""
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
        "runs": {name: {"judged": s.judgable, "refused": s.refused, "stopped": s.stopped} for name, s in tables.states.items()},
        "families": table,
    }
    if first is None:
        out["mechanisms"] = {
            consumer: {which: mechanisms(registration, families, table) for which, families in sets_of(registration, consumer).items()}
            for consumer in registration.consumers
        }
    return strictjson.plain(out)


# ----- stage 2 -----


class Stage2:
    """The scores: every entry, every plant, every verdict."""

    def __init__(self, tables: Tables, c0: dict, power: dict, captures: Captures, planted: Planted, power2: dict | None = None, first: dict | None = None):
        self.tables, self.c0, self.power = tables, c0, power
        self.captures, self.planted = captures, planted
        self.reg = tables.reg
        self.power2 = power2
        self.first = first
        self.entries = []
        self.flags = []
        self._capture = {}

    # ----- small helpers -----

    def flag(self, run, what, detail):
        """Tell the checker."""
        self.flags.append({"run": run, "what": what, "detail": detail})

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
        return bands.extrapolate(self.capture(family, "h2", entry), self.capture(family, "h4", entry), c.LEGACY_ORDER)

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
        plants = self.plants()
        owed = self.retry_owed()
        verdicts = self.verdicts(plants)
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
                "runs": {name: dict(state.record(), verdict=verdicts["runs"].get(name)) for name, state in self.tables.states.items()},
                "ignored": self.tables.ignored,
                "files": {
                    consumer: {"sha256": f.sha256, "refused": f.refusals, "flags": f.flags, "absent": f.absent}
                    for consumer, f in self.tables.tables.files.items()
                },
                "file_flags": self.tables.tables.flags + (self.tables.retry.flags if self.tables.retry else []),
                "entries": self.entries,
                "plants": plants,
                "flags": self.flags,
                "retry_owed": owed,
                "consumers": verdicts["consumers"],
                "part_1": verdicts["part"],
            }
        )

    def guard_b(self):
        """Comparison (b): a run whose class S rows all equal the captured rows of its own world at a captured step."""
        for name, state in self.tables.states.items():
            run = state.run
            if not state.judgable or self.reg.is_pool(run) or run["role"] == "support":
                continue
            rows = self.tables.guard_rows(name)
            if rows is None:
                continue
            family = self.reg.families[run["family"]]
            for step in STEPS:
                entries = family.world.guard_entries()
                if all(np.array_equal(mine, self.capture(family, step, entry)) for mine, entry in zip(rows, entries)):
                    state.guard.append(["b", f"its class S rows equal the captured rows at {step}"])

    # ----- class S -----

    def class_S(self, family):
        """The S entries and the energy identity of a family, on the triple that each is judged on."""
        world = family.world
        first = self.power["families"][family.name]
        second = (self.power2 or {}).get("families", {}).get(family.name, {})
        for entry in [*world.entries, world.energy]:
            est = second.get(entry.name, first[entry.name])
            self._class_S(family, entry, est, entry.name in second)

    def _class_S(self, family, entry, est, again):
        identity = entry.where == "identity"
        judged = not identity or family.world.identities_judged  # an order-2 world's identities are reported (SPEC section 8)
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
            self.add(**record, outcome=c.NOT_FORMED if judged else c.REPORTED, why=est["why"], home=est["home"])
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
            self.flag(record["run"], "state form", f"{family.name} {entry.name}: inside the band with e_store and outside the one without")
        self.add(
            **record,
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

    # ----- class R -----

    def class_R(self, name, state):
        """The balances and the capacitor of an ionic run, against its own grid's steps (CRITERIA section 4.2)."""
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
                items.append((f"balance of {kind}, {species}", lambda rows, at, r=residual, x=species: r(world, rows, x, at), times, bound, entities))
        bound = identities.capacitor_bound(world, steps)
        items.append(("capacitor", lambda rows, at: identities.capacitor_residual(world, rows, at), world.potential_times, bound, world.membranes))
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
                value = residual(rows, at)
                partial = None
            except NotFormed as error:
                value, partial = self._partial(state, residual, at), str(error)
            if value is None:
                self.add(**record, outcome=c.NOT_FORMED if judged else c.REPORTED, why=partial)
                continue
            over = np.abs(value) if limit == 0 else np.abs(value) / limit
            statistic = bands.largest(value)
            good = statistic <= limit
            entity_max = {entity: float(np.max(over[:, i])) for i, entity in enumerate(entities)}
            outcome = c.PASS if good else c.FAIL
            if good and partial is not None:
                outcome = c.NOT_FORMED
            if good and limit > without and statistic > without:
                self.flag(name, "state form", f"{readout}: inside the band with e_store and outside the one without")
            if not judged and outcome == c.FAIL:
                self.flag(name, "a miss of an identity that is reported and not judged", f"{readout}: {statistic!r} against {limit!r}")
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
        """A residual on the rows that a refused or stopped run holds, or None (CRITERIA section 5: a refusal never hides a fail)."""
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
        """The structural zeros, the switch list, the channel schedule and the recorded seeds of an ionic run."""
        run = state.run
        world = self.reg.worlds[run["world"]]
        judged = run["role"] in ("judged", "retry")  # a retry's class E entries are judged (the lead's ruling, Amendment 2)
        for entry in world.zeros:
            record = {"consumer": run["consumer"], "family": run["family"], "run": name, "readout": f"{entry.name} is zero", "class": "E", "judged": judged}
            if run["role"] == "support":
                continue
            self._zero(record, name, state, entry)
        if not world.assembly or run["role"] == "support":
            return
        paths = self.reg.expected_paths(run)
        record = {"consumer": run["consumer"], "family": run["family"], "run": name, "class": "E", "judged": judged}
        inputs = state.entry.get("inputs") if state.judgable else None
        assembly = inputs.get("assembly") if isinstance(inputs, dict) else None
        controls = inputs.get("controls") if isinstance(inputs, dict) else None

        def switches():
            listed = assembly.get("switch_list") if isinstance(assembly, dict) else None
            if not isinstance(listed, dict):
                raise NotFormed("inputs.assembly.switch_list is missing or mistyped")
            return {channel: self._schedule(listed.get(channel), f"switch_list.{channel}") for channel in paths}

        def schedules():
            declared = controls.get("channel", {}) if isinstance(controls, dict) else {}
            declared = {} if declared == [] else declared
            if not isinstance(declared, dict):
                raise NotFormed("inputs.controls.channel is mistyped")
            return {channel: self._schedule(declared.get(channel, [[0.0, 1.0]]), f"controls.channel.{channel}") for channel in paths}

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
        wanted_seeds = {cell: pool["seeds"][run["seed_index"]] for cell, pool in world.pools.items()}
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
            self.add(**record, readout=readout, outcome=c.NOT_FORMED if judged else c.REPORTED, why="; ".join(state.causes()))
            return
        try:
            held = read()
        except NotFormed as error:
            self.add(**record, readout=readout, outcome=c.NOT_FORMED if judged else c.REPORTED, reported=None if judged else c.NOT_FORMED, why=str(error))
            return
        good = held == expected
        outcome = c.PASS if good else c.FAIL
        why = None if good else f"held {held!r}, expected {expected!r}"[:400]
        if not judged and not good:
            self.flag(record["run"], "a class E entry of a run that owns none", readout)
        self.add(**record, readout=readout, outcome=outcome if judged else c.REPORTED, reported=None if judged else outcome, why=why)

    def _zero(self, record, name, state, entry):
        """A structural zero, every row of the run."""
        judged = record["judged"]
        try:
            rows = self.tables.rows(name)
            rows.index(entry.times)
            every = rows._table(rows.rows, "rows", entry.series, entry.entities, range(len(rows._times("t"))), "t")
        except NotFormed as error:
            every = None
            if state.partial:
                try:
                    rows = self.tables.rows(name)
                    every = rows._table(rows.rows, "rows", entry.series, entry.entities, range(len(rows._times("t"))), "t")
                except NotFormed:
                    every = None
            if every is None or not np.any(every):
                self.add(**record, outcome=c.NOT_FORMED if judged else c.REPORTED, why=str(error))
                return
        good = not np.any(every)
        outcome = c.PASS if good else c.FAIL
        self.add(**record, outcome=outcome if judged else c.REPORTED, reported=None if judged else outcome, statistic=bands.largest(every), band=0.0)

    def restart(self, name, state):
        """A restart's E entries: equal to the uninterrupted run of the same step, after its time (CRITERIA section 4.1)."""
        run = state.run
        start = self.reg.restart_time(run)
        if start is None:
            return
        world = self.reg.worlds[run["world"]]
        owner = self.reg.restarted(run)
        at_fault = None
        if state.judgable:
            held = state.entry.get("restart")
            good = isinstance(held, dict) and strictjson.is_finite(held.get("time_s")) and abs(held["time_s"] - start) <= c.TIME_TOL_S
            at_fault = None if good else "its `restart` does not hold the registered time"
            if good and not isinstance(held.get("through"), str):
                self.flag(name, "restart", "`through` is missing or mistyped")
            if good and not strictjson.is_integer(held.get("step_index")):
                self.flag(name, "restart", "`step_index` is missing or mistyped")
            self.flag(name, "restart to confirm", "the checker confirms from the run's own record that it reloaded a written checkpoint")
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
            try:
                if at_fault:
                    raise NotFormed(at_fault)
                rows = self.tables.rows(name)
                optional = [t for t in entry.times if abs(t - start) <= c.TIME_TOL_S]
                times = [t for t in optional if rows.held((t,), key)] + after
                mine = self._at(name, entry, times)
                whole = self._at(owner, entry, times)
            except NotFormed as error:
                why, missed = str(error), self._partial_restart(state, owner, entry, after, key) if at_fault is None else False
                self.add(**record, outcome=c.FAIL if missed else c.NOT_FORMED, why=why)
                continue
            good = np.array_equal(mine, whole)
            self.add(**record, outcome=c.PASS if good else c.FAIL, why=None, statistic=bands.largest(mine - whole), band=0.0)

    def _at(self, name, entry, times):
        rows = self.tables.rows(name)
        if entry.where == "potentials":
            return rows.potential(entry.series, times)
        return rows.get(entry.series, times)

    def _partial_restart(self, state, owner, entry, times, key) -> bool:
        """True where a partial restart's held rows already differ from the uninterrupted run's."""
        if not state.partial or not self.tables.states[owner].judgable:
            return False
        mine = self.tables.rows(state.name)
        held = [t for t in mine.held(times, key) if t in self.tables.rows(owner).held(times, key)]
        try:
            return bool(held) and not np.array_equal(self._at(state.name, entry, held), self._at(owner, entry, held))
        except NotFormed:
            return False

    # ----- the pools -----

    @staticmethod
    def _array(entry, cell, name, shape):
        pool = entry.get("pool")
        arrays = pool.get(cell, {}).get("arrays") if isinstance(pool, dict) and isinstance(pool.get(cell), dict) else None
        value = arrays.get(name) if isinstance(arrays, dict) else None
        out = []

        def walk(item, depth):
            if depth == len(shape):
                if isinstance(item, bool):
                    out.append(int(item))
                elif strictjson.is_finite(item):
                    out.append(item)
                else:
                    raise NotFormed(f"pool.{cell}.arrays.{name} holds {item!r}")
                return
            if not isinstance(item, list) or len(item) != shape[depth]:
                raise NotFormed(f"pool.{cell}.arrays.{name} is missing, or not of shape {list(shape)}")
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
            base = {"consumer": run["consumer"], "family": None, "run": name, "judged": True, "cell": cell}
            if marked:
                base["holds_worlds_that_are_not_blind"] = True
            ids = [str(pool["pool"]["world_id_start"] + i) for i in range(pool["pool"]["worlds"])]
            captured = self.captures.pool_arrays(run["world"], seed, cell)
            for array in c.POOL_ARRAYS:
                record = {**base, "readout": f"{cell} {array}", "class": "E"}
                try:
                    self.tables.rows(name)
                    mine = self._array(state.entry, cell, array, captured[array].shape)
                except NotFormed as error:
                    self.add(**record, outcome=c.NOT_FORMED, why=str(error))
                    continue
                theirs = captured[array].ravel().tolist()
                wrong = [i for i, (a, b) in enumerate(zip(mine, theirs)) if a != b]
                self.add(**record, outcome=c.FAIL if wrong else c.PASS, why=None, unequal=len(wrong), of=len(theirs), at=wrong[:1] or None)
            record = {**base, "readout": f"{cell} path", "class": "E"}
            path = None
            try:
                self.tables.rows(name)
                path = self._path(state.entry, cell, ids)
                reference = {wid: self.reg.reference_path(run["world"], seed, cell, wid) for wid in ids}
                wrong = [wid for wid in ids if path[wid] != reference[wid]]
                self.add(**record, outcome=c.FAIL if wrong else c.PASS, why=f"worlds {wrong}" if wrong else None)
            except NotFormed as error:
                self.add(**record, outcome=c.NOT_FORMED, why=str(error))
            record = {**base, "readout": f"{cell} seed", "class": "E"}
            try:
                self.tables.rows(name)
                held = state.entry["inputs"][cell].get("seed")
                if not strictjson.is_integer(held):
                    raise NotFormed(f"inputs.{cell}.seed is missing or mistyped")
                self.add(**record, outcome=c.PASS if held == pool["seeds"][seed] else c.FAIL, why=None)
            except NotFormed as error:
                self.add(**record, outcome=c.NOT_FORMED, why=str(error))
            record = {**base, "readout": f"{cell} exposure", "class": "R"}
            if path is None:
                self.add(**record, outcome=c.NOT_FORMED, why="its path is not formed")
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
                **record, outcome=c.FAIL if missed else c.PASS, why=f"worlds {missed}" if missed else None,
                statistic=worst[0], band=worst[1], ratio=ratio, at=worst[2],
            )

    def pool_restart(self, name, state):
        """A pool restart's arrays, and its path after the restart's time, equal to the uninterrupted run's (class E)."""
        run = state.run
        start = self.reg.restart_time(run)
        if start is None:
            return
        world = self.reg.worlds[run["world"]]
        owner = self.reg.restarted(run)
        whole = self.tables.states[owner]
        fault = None
        if state.judgable:
            held = state.entry.get("restart")
            good = isinstance(held, dict) and strictjson.is_finite(held.get("time_s")) and abs(held["time_s"] - start) <= c.TIME_TOL_S
            fault = None if good else "its `restart` does not hold the registered time"
            if good and not isinstance(held.get("through"), str):
                self.flag(name, "restart", "`through` is missing or mistyped")
            if good and held.get("step_index") is not None:
                self.flag(name, "restart", "`step_index` is not null in a pool restart (Amendment 1, item 2)")
            self.flag(name, "restart to confirm", "the checker confirms from the run's own record that it reloaded a written checkpoint")
            for cell, pool in world.pools.items():
                if state.entry["inputs"][cell].get("seed") != pool["seeds"][run["seed_index"]]:
                    self.flag(name, "seed", f"inputs.{cell}.seed is not the registered seed")
        for cell, pool in world.pools.items():
            ids = [str(pool["pool"]["world_id_start"] + i) for i in range(pool["pool"]["worlds"])]
            base = {"consumer": run["consumer"], "family": None, "run": owner, "support": name, "judged": True, "class": "E", "cell": cell}
            shapes = {array: self.captures.pool_arrays(run["world"], run["seed_index"], cell)[array].shape for array in c.POOL_ARRAYS}
            for array in c.POOL_ARRAYS:
                record = {**base, "readout": f"restart {cell} {array}"}
                try:
                    if fault:
                        raise NotFormed(fault)
                    self.tables.rows(name)
                    self.tables.rows(owner)
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
                mine, theirs = self._path(state.entry, cell, ids), self._path(whole.entry, cell, ids)
                wrong = [w for w in ids if [e for e in mine[w] if e[0] > start] != [e for e in theirs[w] if e[0] > start]]
                self.add(**record, outcome=c.FAIL if wrong else c.PASS, why=f"worlds {wrong}" if wrong else None)
            except NotFormed as error:
                self.add(**record, outcome=c.NOT_FORMED, why=str(error))

    # ----- class D -----

    def class_D(self, name, state):
        """Completion (CRITERIA section 4.4). A stop fails; a refusal is not a stop, and D is not judged there."""
        run = state.run
        if run["role"] not in ("judged", "retry"):
            return
        record = {"consumer": run["consumer"], "family": run["family"], "run": name, "readout": "completes", "class": "D", "judged": True}
        if not state.judgable:
            self.add(**record, outcome=c.NOT_FORMED, why="; ".join(state.causes()))
        elif state.stopped:
            self.add(**record, outcome=c.FAIL, why=state.refusal_message)
        elif state.completed:
            self.add(**record, outcome=c.PASS, why=None)
        else:
            self.add(**record, outcome=c.NOT_FORMED, why="refused: D is not judged")

    # ----- plants -----

    def _honest(self, family, entry_name):
        """What a plant needs of its honest family: its estimates, or why it is unscorable."""
        est = (self.power2 or {}).get("families", {}).get(family.name, {}).get(entry_name) or self.power["families"][family.name][entry_name]
        bad = [n for n in est["runs"] if self.tables.states[n].refused or self.tables.states[n].stopped]
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
                star = bands.extrapolate(*(self.tables.entry(n, entry) for n in est["runs"][1:]), world.p)
                statistic = bands.largest(star - self.planted.run(plant["run"], family, step_s).entry(entry))
                named.append({**item, **self._plant_score(item["distance"], est["beta"], statistic)})
            out.append({"plant": name, "kind": "structural", "consumer": consumer, "family": family.name, "entries": named, "score": overall(named)})
        for consumer, run, name, plant, distances in self.reg.engine():
            out.append(self._engine(consumer, run, name, plant, distances))
        return {"plants": out}

    @staticmethod
    def _plant_score(distance, beta, statistic):
        out = {"band": beta, "statistic": statistic, "margin": distance / beta}
        if distance <= 2 * beta:
            return {**out, "score": "unscorable", "why": "its registered distance is at most 2 beta"}
        return {**out, "score": "caught" if statistic > beta else "not caught", "why": None}

    def _engine(self, consumer, run, name, plant, distances):
        family = self.reg.families[run["family"]]
        world, state = family.world, self.tables.states[run["name"]]
        out = {"plant": name, "kind": "engine", "consumer": consumer, "family": family.name, "run": run["name"], "causes": state.causes()}

        def unscorable(why):
            return {**out, "entries": [{"entry": k, "score": "unscorable", "why": why} for k in plant["named"]], "score": "unscorable"}

        if not state.judgable:
            return unscorable("; ".join(state.causes()))
        if world.assembly:
            held = {e["readout"]: e for e in self.entries if e["run"] == run["name"] and e["class"] == "E"}
            for readout in ("switch list", "channel schedule", "pool seeds"):
                if held[readout].get("reported") != c.PASS:
                    return unscorable(f"its {readout} departs from what the plant declares")
        rows, honest = self.tables.guard_rows(run["name"]), None
        if self.tables.states[family.finest].judgable:
            honest = self.tables.guard_rows(family.finest)
        equal = rows is not None and honest is not None and all(np.array_equal(a, b) for a, b in zip(rows, honest))
        if equal:
            why = "its class S rows equal the run it was planted in"
            return {**out, "entries": [{"entry": k, "score": "not caught", "why": why} for k in plant["named"]], "score": "not caught"}
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
                named.append({**item, "score": "unscorable", "why": f"the named entry is not formed: {error}"})
                continue
            statistic = bands.largest(mine - self.star(family, entry))
            named.append({**item, **self._plant_score(distances[key], est["beta"], statistic)})
        score = overall(named)
        if score == "caught" and (state.refused or state.stopped):
            return {**out, "entries": named, "score": "unscorable", "why": "the plant's own run is refused"}
        return {**out, "entries": named, "score": score}

    # ----- the retry -----

    def retry_owed(self) -> dict:
        """What the retry is owed (CRITERIA section 7): the runs, and why, by family."""
        runs, why = [], {}
        if self.power2 is None:
            for family in self.reg.families.values():
                if any(self.tables.states[n].refused or self.tables.states[n].stopped for n in family.runs):
                    continue
                reasons = []
                for item in self.entries:
                    if item["class"] != "S" or item["family"] != family.name or not item["judged"]:
                        continue
                    est = self.power["families"][family.name][item["readout"]]
                    if item["outcome"] == c.INCONCLUSIVE:
                        reasons.append(f"{item['readout']}: order")
                    elif est.get("formed") and est["home"] and est["tested"] is False and item["outcome"] != c.FAIL and est["truncation_is_larger"]:
                        reasons.append(f"{item['readout']}: power")
                if reasons:
                    why[family.name] = sorted(reasons)
                    runs.append(family.retry_name)
        return {"kind": c.RETRY_KIND, "part": c.PART, "runs": sorted(runs), "why": dict(sorted(why.items()))}

    # ----- verdicts -----

    def _run_verdict(self, name, owned):
        state = self.tables.states[name]
        outcomes = [e["outcome"] for e in owned]
        if c.FAIL in outcomes:
            return c.FAIL
        if state.refused or any(o in (c.INCONCLUSIVE, c.NOT_FORMED) for o in outcomes):
            return c.INCONCLUSIVE
        return c.PASS

    def verdicts(self, plants) -> dict:
        """Every run's verdict, every consumer's (in its sets), and the part's (CRITERIA section 8)."""
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
            table = {which: self._set_verdict(consumer, families, runs, plants) for which, families in sets.items()}
            order = (c.FAIL, c.INCONCLUSIVE, c.PASS)
            verdict = min((t["verdict"] for t in table.values()), key=order.index)
            consumers[consumer] = {"verdict": verdict, "sets": table}
            note = self.reg.profile.get("notes", {}).get(consumer)
            if note:
                consumers[consumer]["note"] = note
        whole = {"consumers": {k: v["verdict"] for k, v in consumers.items()}}
        whole["passes"] = all(v == c.PASS for v in whole["consumers"].values())
        return {"runs": runs, "consumers": consumers, "part": whole}

    def _set_verdict(self, consumer, families, runs, plants):
        names = {f.name for f in families}
        shared = [r for r in self.reg.runs.values() if r["consumer"] == consumer and r["family"] is None]
        members = [n for f in families for n in self.tables.rungs(f)] + [r["name"] for r in shared if r["role"] == "judged"]
        support = [r["name"] for r in shared if r["role"] == "support"]
        entries = [e for e in self.entries if e["consumer"] == consumer and e["judged"] and (e["family"] in names or e["family"] is None)]
        its_plants = [p for p in plants["plants"] if p["consumer"] == consumer]
        reasons, fails = [], []
        for name in members:
            if runs[name] == c.FAIL:
                fails.append(f"the run {name} fails")
        for plant in its_plants:
            if plant["score"] == "not caught":
                fails.append(f"the plant {plant['plant']} is not caught")
        for name in members + support:
            state = self.tables.states[name]
            if state.refused or state.stopped:
                reasons.append(f"the run {name} is refused, missing or stopped: {'; '.join(state.causes())}")
        waiting = [e for e in entries if e["outcome"] in (c.INCONCLUSIVE, c.NOT_FORMED)]
        for item in waiting[:20]:
            reasons.append(f"{item['run']}, {item['readout']}: {item['outcome']} ({item.get('why')})")
        if len(waiting) > 20:
            reasons.append(f"and {len(waiting) - 20} more entries that are inconclusive or not formed")
        found = self._mechanisms(families)
        for mechanism, record in found.items():
            if not record["tested"]:
                reasons.append(f"the mechanism {mechanism} is untested")
        for plant in its_plants:
            if plant["score"] == "unscorable":
                reasons.append(f"the plant {plant['plant']} is unscorable")
        counts = self._counts(consumer, families, entries)
        for name, numbers in counts.items():
            if numbers["formed"] < numbers["expected"]:
                reasons.append(f"{numbers['formed']} entries of class {name} were formed, and {numbers['expected']} are listed")
        verdict = c.FAIL if fails else c.INCONCLUSIVE if reasons else c.PASS
        return {
            "verdict": verdict,
            "fails": fails,
            "inconclusive": reasons,
            "families": {f.name: self._family_summary(f, entries) for f in families},
            "members": {
                "families": len(families),
                "judged_runs": len(members),
                "pool_runs": [r["name"] for r in shared if r["role"] == "judged"],
                "support_runs": support,
                "plants": [p["plant"] for p in its_plants],
            },
            "counts": counts,
            "outcomes": self._outcomes(entries),
            "mechanisms": found,
            "not_tested": [[e["family"], e["readout"]] for e in entries if e["outcome"] == c.NOT_TESTED],
            "failing_entries": [[e["run"], e["readout"], e["class"]] for e in entries if e["outcome"] == c.FAIL],
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
            expected["E"] += len(family.world.zeros) + (3 if family.world.assembly else 0)
            if family.world.identities_judged:
                expected["R"] += 3 * len(family.world.species) + 1
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
        outcomes = {}
        for item in mine:
            table = outcomes.setdefault(item["class"], {})
            table[item["outcome"]] = table.get(item["outcome"], 0) + 1
        flat = {e["outcome"] for e in mine}
        verdict = c.FAIL if c.FAIL in flat else c.INCONCLUSIVE if flat & {c.INCONCLUSIVE, c.NOT_FORMED} else c.PASS
        worst = max((e for e in mine if e["class"] == "S" and e.get("ratio") is not None), key=lambda e: e["ratio"], default=None)
        return {
            "verdict_of_its_entries": verdict,
            "outcomes": outcomes,
            "largest_S_ratio": None if worst is None else [worst["readout"], worst["ratio"]],
        }


def overall(named) -> str:
    """A plant's score from its named entries: any not caught, then any unscorable, then caught (CRITERIA section 6)."""
    scores = {item["score"] for item in named}
    if "not caught" in scores:
        return "not caught"
    return "unscorable" if "unscorable" in scores or not scores else "caught"


def check_power(tables: Tables, c0: dict, power: dict, hashes: dict, first: dict | None = None):
    """Stage 2 begins only where `power.json` is what stage 1 makes of these tables, and of the recorded hashes."""
    if power.get("kind") != c.POWER_KIND:
        raise OrderFault("power.json is not a power record")
    if power["hashes"] != hashes:
        raise OrderFault("power.json was made from other files")
    again = stage1(tables, c0, hashes, first)
    if again != power:
        raise OrderFault("power.json is not what stage 1 makes of these tables")
