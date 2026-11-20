"""The runner of version 2: one world per lane, event-driven (its own runner shape).

    run(spec)          one world, from its founder to the end of its lifecycle (kernel.py)
    run_lanes(specs)   several worlds of one structure, as lanes of one compiled program

The host loop of one batch of lanes: advance one chunk of events at a time until no lane is
RUNNING. A lane that is not RUNNING changes nothing and draws nothing, so the chunk size and the
lane batch change no value.

**Before a run,** the kernel's check runs on its generic probe (balance.verdict) and on the
world's own data (balance.world_report). Either refuses a world whose rates fail
ln a⁺ − ln a⁻ = −ΔF + w.

**Records** (records.py declares them):
- rows: the start, every `row_every_events` committed events, each observation time (the state
  after the last event at or before it), and the end, in time order;
- at each row, the counts of every place, the channels' cumulative counts, the held reservoirs'
  net supplies, and the cumulative heat Q and reservoir work W;
- the end row's time is the horizon when the state held to it (complete, inert), and the last
  event's otherwise. An observation time after the last event is filled from the final state when
  that state holds (complete, inert, extinct); a run stopped otherwise leaves it unobserved, and
  the run says how many (`observations_censored`).

The counts at a row are rebuilt on the host from the channels' cumulative counts, in exact
integers. At the end they must equal the lane's own counts: a run where they differ is a fault and
raises. Q and W are the device's own cumulative values at each row's event.

**The ledger** (ledger.py) is closed at every row: F(n_t) − F(n_0) = W − Q, to rounding. Every law
of this family is passive, so a run whose books do not close is refused: its status says so,
check() raises, and nothing is repaired.
"""

from dataclasses import dataclass, field
from time import perf_counter

import numpy as np

from cells.definitions.specs import ConfigError
from cells.models.assembly_lineages import keys
from cells.models.assembly_lineages_v2 import (
    MODE,
    balance,
    diagnostic,
    division,
    geometry,
    kernel,
    ledger,
    lumen,
    model,
    streams,
)
from cells.models.assembly_lineages_v2.spec import world_id

ROW_KINDS = ("start", "periodic", "end", "observed")
START, PERIODIC, END, OBSERVED = range(4)
# OL3: a row after a shear event's fission. Only a world that declares division writes it, and only
# its record's legend names it, so every other bundle's legend is unchanged.
DIVISION_ROW_KINDS = (*ROW_KINDS, "shear")
SHEAR = 4
_COMPILED = {}
HELD_TO_HORIZON = ("complete", "inert")
HOLDS = ("complete", "inert", "extinct")  # The final state holds after the last event.


class LedgerRefused(ConfigError):
    """A run whose ledger did not close at a saved row."""


@dataclass
class WorldRun:
    spec: object
    structure: object
    verdict: dict
    world_report: dict
    status: str
    rows: dict
    trace: dict
    diagnostics: dict
    closure: dict
    qualifier: str
    final: dict  # The last lane state (host arrays).
    timings: dict = field(default_factory=dict)
    osmotic: dict | None = None  # OL2 milestone 2: c_ext's drift report and any lysis (records)
    division: dict | None = None  # OL3: the fission table, the lives and the schedule's report
    diagnostic: dict | None = None  # OL2 milestone 3: §0.2d item 10.5's record (diagnostic.py)
    population: dict | None = None  # OL2 milestone 3: the shared pool's report (population.py)
    start: object = "fresh"  # FR-22 rung P: "fresh", or a run from a checkpoint's start record
    resume: dict | None = None  # the host's state a checkpoint keeps, when the run `stopped`

    def checkpoint(self):
        """The checkpoint of a population run stopped at an exact event count (checkpoints.py)."""
        from cells.models.assembly_lineages_v2 import checkpoints

        return checkpoints.make(self)

    def check(self):
        """Raise if the run was refused (a ledger that did not close)."""
        if self.closure["refused"]:
            raise LedgerRefused(self.closure["refused"])
        return self


def _compiled(structure, lanes, layout):
    """(initial, advance, compile seconds) of one structure for `lanes` lanes."""
    import jax

    key = (structure, lanes)
    if key not in _COMPILED:
        started = perf_counter()
        program = kernel.program(structure)
        founders = jax.ShapeDtypeStruct((lanes, structure.places), np.int64)
        initial = program.initial.lower(founders, layout).compile()
        shapes = jax.eval_shape(program.initial, founders, layout)
        advance = program.advance.lower(shapes, layout).compile()
        _COMPILED[key] = (initial, advance, perf_counter() - started)
    return _COMPILED[key]


def _stack(trees):
    import jax

    return jax.tree_util.tree_map(lambda *xs: np.stack([np.asarray(x) for x in xs]), *trees)


def _lane(tree, i):
    """Lane i of a stacked lane tree, as {field: host value} (empty states kept as ())."""
    import jax

    out = {}
    for name in kernel.Lane._fields:
        value = getattr(tree, name)
        if isinstance(value, tuple) and not value:
            out[name] = ()
        else:
            out[name] = jax.tree_util.tree_map(lambda a: np.asarray(a)[i].copy(), value)
    return out


def changes(layout, structure):
    """(count change [2R, P], supply change [2R, P]) of each channel, in exact integers: a forward
    moves +ν over the finite places, a reverse −ν; a held place's supply moves −ν."""
    R, P = structure.steps, structure.places
    count = np.zeros((2 * R, P), dtype=np.int64)
    supply = np.zeros((2 * R, P), dtype=np.int64)
    for r in range(R):
        for k in range(kernel.ENTRIES):
            a, b = layout.entry_alpha[r, k], layout.entry_beta[r, k]
            if a + b == 0:
                continue
            place = layout.entry_place[r, k]
            if layout.entry_held[r, k]:
                supply[r, place] -= b - a
                supply[R + r, place] -= a - b
            else:
                count[r, place] += b - a
                count[R + r, place] += a - b
    return count, supply


class _World:
    """One lane's records (host side)."""

    def __init__(self, lane, row_every, observations, divides=False, diagnose=False):
        self.start = lane
        self.row_every = row_every
        self.rows = []  # (kind, event index, time, fired [2R], Q, |Q|, W, |W|)
        self.fired = np.zeros_like(lane["fired"])
        self.events = 0
        self.channels, self.times, self.draws = [], [], []
        self.observations = list(observations)
        self.booked = (0.0, 0.0, 0.0, 0.0)  # Q, |Q|, W, |W| after the last event taken.
        # OL3: each row's fission terms, (jump [P], shear work, sink, their magnitude), cumulative;
        # None for a world without division (its rows are OL2's).
        self.extras = [] if divides else None
        self.jump = np.zeros_like(lane["counts"])
        self.shear = self.sink = self.magnitude = 0.0
        self.attempts = []  # (division.Attempt, the parent's generation), in order
        self.counters = {}  # each parent's fission counter: its attempts that drew
        self.diagnostic = None  # §0.2d item 10.5: the draws' addresses and fates, when declared
        if diagnose:
            self.diagnostic = {"draws": [], "heat": [], "work": [], "jumps": [],
                               "schedule_draws": [], "key": 0, "counter": 0,
                               "lysed_at_stop": False, "ended_by_stop": False}  # fmt: skip

    def extra(self):
        return (self.jump.copy(), self.shear, self.sink, self.magnitude)

    def row(self, *row):
        self.rows.append(row)
        if self.extras is not None:
            self.extras.append(self.extra())

    def observe(self, until):
        """Observation rows for every pending time before `until` (the next event's time)."""
        while self.observations and self.observations[0] < until:
            t = self.observations.pop(0)
            self.row(OBSERVED, self.events, t, self.fired.copy(), *self.booked)

    def take(self, channel, time, heat, heat_mag, work, work_mag, draws, R):
        """The committed events of one chunk, in order (channel: the kernel's signed code)."""
        index = np.where(channel > 0, channel - 1, R + (-channel - 1)).astype(np.int64)
        for k in range(len(index)):
            self.observe(time[k])
            self.booked = (heat[k], heat_mag[k], work[k], work_mag[k])
            self.events += 1
            self.fired[index[k]] += 1
            if self.events % self.row_every == 0:
                self.row(PERIODIC, self.events, time[k], self.fired.copy(), heat[k], heat_mag[k],
                         work[k], work_mag[k])  # fmt: skip
        self.channels.append(channel)
        self.times.append(time)
        if draws is not None:
            self.draws.append(draws)
        d = self.diagnostic
        if d is not None:
            for _ in range(len(index)):
                d["draws"].append((d["key"], d["counter"], diagnostic.COMMITTED))
                d["counter"] += 1
            d["heat"].append(np.asarray(heat))
            d["work"].append(np.asarray(work))


def _plan(spec, base_key):
    """(stops, schedule draws): a division world's schedule stops, [(time, [its events, in
    schedule-index order])], at or before the horizon (§0.2d item 10.1), and its schedules' draws
    (Poisson gaps); ([], []) for any other world."""
    if not spec.experiment.schedules:
        return [], []
    events, draws = division.timeline(
        spec.experiment.schedules, spec.experiment.time_horizon_s, base_key
    )
    out = []
    for event in events:
        if out and out[-1][0] == event[0]:
            out[-1][1].append(event)
        else:
            out.append((event[0], [event]))
    return out, draws


def _vesicle_energy(spec, layout):
    """F_v(counts): the vesicle's own part of F in a [P] state, with its closure cost, as F less F
    with the vesicle's places emptied (the pool's part cancels; §0.2d item 7)."""
    world = spec.model.world
    tables = model.tables(spec)
    vesicle = np.concatenate(division.vesicle_places(world))
    capacity = layout.place_held.shape[0]
    closure = geometry.closure_kT(world)

    def energy(counts):
        full = np.zeros(capacity, dtype=np.int64)
        full[: len(counts)] = counts
        empty = full.copy()
        empty[vesicle] = 0
        value = ledger.free_energy(full, tables, world.terms, layout.terms) - ledger.free_energy(
            empty, tables, world.terms, layout.terms
        )
        if not np.isfinite(value):
            raise AssertionError("A vesicle's own free energy is not finite: a fault")
        return value + closure

    return energy


def _shear(specs, host_layouts, holders, plans, lanes, layout, due, initial, device):
    """Apply each due lane's schedule stop on the host (division.py): the draw that crossed the
    stop is discarded and counted, then the stop's events act in index order on the assembly alive
    at each one's start. Returns the lanes and the layout with each lane's next stop."""
    import jax

    host = jax.tree_util.tree_map(np.array, lanes)
    horizons = np.array(layout.horizon)
    changed = np.zeros(len(specs), dtype=bool)
    for i in due:
        spec, holder = specs[i], holders[i]
        world = spec.model.world
        places = len(world.places)
        stop, events = plans[i].pop(0)
        holder.observe(stop)  # Observations before the stop see the state before its events.
        held = int(host.status[i])
        age = int(host.age[i]) + 1  # The draw that crossed the stop: discarded, and counted.
        key, generation = int(host.occupant[i]), int(host.generation[i])
        d = holder.diagnostic
        if d is not None:
            d["draws"].append((key, age - 1, diagnostic.DISCARDED))
            before = host.counts[i].copy()
        next_key = int(host.next_carrier[i])
        counts = host.counts[i].copy()
        lysed = False
        for event in events:
            counter = holder.counters.get(key, 0)
            attempt = division.attempt(
                world, counts[:places], key, counter, event, host_layouts[i].base_key,
                holder.energy, next_key,
            )  # fmt: skip
            holder.attempts.append((attempt, generation))
            if attempt.counter >= 0:
                holder.counters[key] = counter + 1
            if attempt.outcome != "split":
                continue
            after = counts.copy()
            after[:places] = attempt.daughters[attempt.followed]
            holder.jump += after - counts
            holder.shear += attempt.shear_work
            holder.sink += attempt.sink
            holder.magnitude += abs(attempt.shear_work) + abs(attempt.sink)
            counts = after
            next_key += attempt.k
            key, generation, age = attempt.keys[attempt.followed], generation + 1, 0
            changed[i] = True
            holder.row(SHEAR, holder.events, stop, holder.fired.copy(), *holder.booked)
            if attempt.lysed[attempt.followed]:  # §0.2d item 10.3: born beyond sigma_max.
                lysed = True
                break
        if changed[i]:
            host.counts[i] = counts
            host.event_stream[i] = np.asarray(
                streams.stream_key_data(host_layouts[i].base_key, key, "events")
            )
        host.occupant[i], host.generation[i], host.next_carrier[i] = key, generation, next_key
        host.age[i], host.time[i] = age, stop
        horizons[i] = plans[i][0][0] if plans[i] else spec.experiment.time_horizon_s
        if lysed:
            host.status[i] = kernel.LYSED
        elif stop < spec.experiment.time_horizon_s:
            host.status[i] = kernel.RUNNING
        else:
            host.status[i] = held  # The last stop is the horizon: the state holds to it.
        if d is not None:
            d["key"], d["counter"] = key, age
            if changed[i]:
                d["jumps"].append((holder.events, counts - before))
            d["lysed_at_stop"] |= lysed
            d["ended_by_stop"] = not lysed and stop >= spec.experiment.time_horizon_s
    if changed.any():  # The new occupants' totals, rates and term states, from their counts.
        fresh = jax.tree_util.tree_map(np.asarray, initial(host.counts, layout))

        def pick(new, old):
            return np.where(changed.reshape((-1,) + (1,) * (old.ndim - 1)), new, old)

        host = host._replace(
            totals=pick(fresh.totals, host.totals),
            rates=pick(fresh.rates, host.rates),
            factor_state=jax.tree_util.tree_map(pick, fresh.factor_state, host.factor_state),
            term_states=jax.tree_util.tree_map(pick, fresh.term_states, host.term_states),
        )
    layout = layout._replace(horizon=jax.device_put(horizons, device))
    return jax.device_put(host, device), layout


def run(spec, *, start=None, stop=None):
    """One world, fresh or (a population, FR-22 rung P) from a checkpoint `start`, to its end or to
    an exact stop at `stop` events (population.run)."""
    if spec.execution.mode == "population":  # OL2 milestone 3 (population.py)
        from cells.models.assembly_lineages_v2 import population

        return population.run(spec, start=start, stop=stop)
    if start is not None or stop is not None:
        raise ConfigError(
            "Checkpoints, a start or a stop, are built for population runs (FR-22 rung P); a "
            "single-lineage run's (rung S) waits for a consumer"
        )
    return _run_single(spec)


def _run_single(spec):
    """One world, from its founder to the end of its lifecycle."""
    return run_lanes([spec])[0]


def run_lanes(specs):
    """Several worlds of one structure, as lanes of one program; one WorldRun each."""
    import jax

    from cells.execution.devices import execution_device

    if not diagnostic.partitionable():
        raise ConfigError(
            "This family's block draws (a partition's uniforms, an event's two) give the same "
            "values at any block size only with JAX's partitionable threefry: "
            "jax_threefry_partitionable is off, so the run is refused (§0.2d item 9)"
        )
    if any(s.execution.mode != MODE for s in specs):
        raise ConfigError(f"run_lanes runs {MODE} worlds")
    structures = {model.structure(s) for s in specs}
    if len(structures) != 1:
        raise ConfigError("Lanes share one structure (capacities, laws, conventions, recording)")
    (structure,) = structures
    if len({s.execution.backend for s in specs}) != 1:
        raise ConfigError("Lanes share one backend")
    kernel.refuse_unknown(structure)
    # Refuses a kernel that fails the identity on its probe; a world with a geometry (OL2) takes
    # the geometric probe's verdict, and OL1's worlds the probe they always had.
    osmotic = any(s.model.world.conventions.lumen_volume == "osmotic" for s in specs)
    if osmotic:
        verdict = balance.osmotic_verdict()
    else:
        verdict = (
            balance.geometry_verdict() if structure.geometry is not None else balance.verdict()
        )
    by_world = {}  # The world's own report, once per distinct world (lanes often share one).
    for s in specs:
        key = world_id(s.model.world)
        if key not in by_world:
            by_world[key] = balance.world_report(s)
    reports = [by_world[world_id(s.model.world)] for s in specs]
    device = execution_device(specs[0].execution.backend)
    host_layouts = [model.layout(s) for s in specs]
    planned = [_plan(s, h.base_key) for s, h in zip(specs, host_layouts, strict=True)]
    plans = [p for p, _ in planned]  # OL3: each lane's schedule stops (division.py)
    stops = [
        layout_i._replace(horizon=np.float64(plan[0][0])) if plan else layout_i
        for layout_i, plan in zip(host_layouts, plans, strict=True)
    ]
    layout = jax.device_put(_stack(stops), device)
    founders = jax.device_put(np.stack([model.founder(s) for s in specs]), device)
    L, R = len(specs), structure.steps
    with jax.default_device(device):
        initial, advance, compile_seconds = _compiled(structure, L, layout)
        started = perf_counter()
        lanes = initial(founders, layout)
        holders = [
            _World(_lane(lanes, i), s.experiment.row_every_events, s.experiment.observation_times_s,
                   s.model.world.division is not None, s.experiment.diagnostic)
            for i, s in enumerate(specs)
        ]  # fmt: skip
        for holder, (_, draws) in zip(holders, planned, strict=True):
            if holder.diagnostic is not None:
                holder.diagnostic["schedule_draws"] = draws
        for holder, spec, layout_i in zip(holders, specs, host_layouts, strict=True):
            if spec.model.world.division is not None:
                holder.energy = _vesicle_energy(spec, layout_i)
        chunks = 0
        while True:
            status = np.asarray(lanes.status)
            if not (status == kernel.RUNNING).any():
                held = (kernel.COMPLETE, kernel.INERT)  # A lane at a schedule stop holds to it.
                due = [i for i in range(L) if plans[i] and int(status[i]) in held]
                if not due:
                    break
                lanes, layout = _shear(specs, host_layouts, holders, plans, lanes, layout, due,
                                       initial, device)  # fmt: skip
                continue
            lanes, out = advance(lanes, layout)
            chunks += 1
            committed = np.asarray(out.committed)
            if not committed.any():
                continue
            host = jax.tree_util.tree_map(np.asarray, out)
            for i in range(L):
                mask = committed[:, i]
                if mask.any():
                    holders[i].take(
                        host.channel[mask, i],
                        host.time[mask, i],
                        host.heat[mask, i],
                        host.heat_magnitude[mask, i],
                        host.work[mask, i],
                        host.work_magnitude[mask, i],
                        host.uniforms[mask, i] if structure.uniforms else None,
                        R,
                    )
        jax.block_until_ready(lanes)
        run_seconds = perf_counter() - started
    results = []
    for i, spec in enumerate(specs):
        final = _lane(lanes, i)
        events = holders[i].events
        timings = {
            "compile_seconds": compile_seconds,
            "run_seconds": run_seconds,
            "lanes": L,
            "chunks": chunks,
            "events": events,
            "events_per_second": events / run_seconds if run_seconds > 0 else None,
            "scope": "wall time of the whole lane batch on its device; compile apart (cached per "
            "structure and lane count)",
        }
        results.append(
            _assemble(
                spec, structure, host_layouts[i], verdict, reports[i], holders[i], final, timings
            )
        )
    return results


def _release(world, layout, tables, counts, supplied, f, heat, heat_mag, work, work_mag, time):
    """A lysis's release n′ → n_after on the end row: the membrane's and the lumen's molecules go to
    their pool places as monomers, the closure cost is released, and the row books
    q = −(F(n_after) − F(n′)) + w_return on top of the triggering step's own
    q = −(F(n′) − F(n)) + w, so the event's one row holds q = −(F(n_after) − F(n)) + w (§0.2d
    item 7). A held place that
    receives molecules books their reservoir work, w = −Σ μ_held × the molecules received."""
    n_prime = counts[-1].copy()
    after = n_prime.copy()
    took = supplied[-1].copy()
    work_return = 0.0
    pool_index = {p.species: i for i, p in enumerate(world.places) if p.phase == "pool"}
    returned = {}
    held_mu = model.place_arrays(world, layout.place_held.shape[0])[5]
    for i, place in enumerate(world.places):
        if place.phase not in ("membrane", "lumen") or n_prime[i] == 0:
            continue
        j = pool_index[place.species]  # every membrane and lumen species has one (spec.py)
        amount = int(n_prime[i])
        after[i] = 0
        returned[world.places[j].name] = returned.get(world.places[j].name, 0) + amount
        if world.places[j].held:
            took[j] -= amount  # the reservoir takes them back
            work_return -= amount * float(held_mu[j])
        else:
            after[j] += amount
    f_after = ledger.free_energy(after, tables, world.terms, layout.terms)  # no C_close
    q_release = -(f_after - f[-1]) + work_return
    counts, supplied, f = counts.copy(), supplied.copy(), f.copy()
    heat, heat_mag, work, work_mag = heat.copy(), heat_mag.copy(), work.copy(), work_mag.copy()
    counts[-1], supplied[-1], f[-1] = after, took, f_after
    heat[-1] += q_release
    heat_mag[-1] += abs(q_release)
    work[-1] += work_return
    work_mag[-1] += abs(work_return)
    record = {
        "time_s": time,
        "sigma_N_per_m": lumen.host_tension(world, n_prime[: len(world.places)]),
        "sigma_max_N_per_m": world.geometry[1]["sigma_max_N_per_m"][0],
        "returned": returned,
        "release_heat_kT": q_release,
        "release_reservoir_work_kT": work_return,
        "reads": "the end row holds the released state; observations after the lysis are censored",
    }
    return counts, supplied, f, heat, heat_mag, work, work_mag, record


def _osmotic_report(world, counts, lysis):
    """c_ext's drift report (§0.2c rule 6) and any lysis: the pool's solute osmolarity at every
    row, against the held c_ext. It is exact for held species; for finite ones c_ext is held while
    the pool's count moves, a declared approximation whose largest relative drift is reported."""
    c_ext = lumen.outside_mM(world)
    volume = world.volume("pool")
    osm = []
    for row in counts:
        total = 0.0
        for place, count in zip(world.places, row, strict=True):
            if place.phase != "pool":
                continue
            total += place.held_mM if place.held else count / (lumen.AVOGADRO * volume) * 1e3
        osm.append(total)
    osm = np.asarray(osm, dtype=np.float64)
    return {
        "outside_osmolarity_mM": c_ext,
        "pool_solutes_mM_at_start": float(osm[0]),
        "largest_relative_drift": float(np.max(np.abs(osm - osm[0])) / c_ext),
        "reads": "c_ext is held (the outside's total osmolarity); the drift is the pool's solute "
        "osmolarity's largest change over the run, relative to c_ext",
        "lysis": lysis,
    }


def _assemble(spec, structure, layout, verdict, report, holder, final, timings):
    world = spec.model.world
    status = kernel.STATUS[int(final["status"])]
    count_change, supply_change = changes(layout, structure)
    start = holder.start
    places = len(world.places)
    end_time = spec.experiment.time_horizon_s if status in HELD_TO_HORIZON else float(final["time"])
    if status in HOLDS:
        holder.observe(np.inf)  # The final state holds: every remaining time sees it.
    censored = len(holder.observations)
    zero_fired = np.zeros_like(holder.fired)
    rows = [(START, 0, 0.0, zero_fired, 0.0, 0.0, 0.0, 0.0)]
    rows += holder.rows
    rows.append(
        (END, holder.events, end_time, holder.fired.copy(), float(final["heat"]),
         float(final["heat_magnitude"]), float(final["work"]), float(final["work_magnitude"]))
    )  # fmt: skip
    fired = np.stack([r[3] for r in rows]).astype(np.int64)
    counts = start["counts"][None, :] + fired @ count_change
    divides = world.division is not None
    if divides:  # OL3: each row's fission jump, shear work, sink and their magnitude, cumulative.
        extras = [(np.zeros_like(holder.jump), 0.0, 0.0, 0.0), *holder.extras, holder.extra()]
        counts = counts + np.stack([e[0] for e in extras])
        shear, sink, fission_mag = (
            np.asarray([e[k] for e in extras], dtype=np.float64) for k in (1, 2, 3)
        )
    supplied = fired @ supply_change
    if not np.array_equal(counts[-1], final["counts"]) or not np.array_equal(
        supplied[-1], final["supplied"]
    ):
        raise AssertionError(
            "The rows rebuilt from the channels' counts differ from the lane's own state: a fault"
        )
    tables = model.tables(spec)
    f = np.asarray(
        [ledger.free_energy(c, tables, world.terms, layout.terms) for c in counts], dtype=np.float64
    )
    if world.geometry is not None:  # C_close, once for the one living vesicle (§0.2c rule 8).
        f = f + geometry.closure_kT(world)
    heat = np.asarray([r[4] for r in rows], dtype=np.float64)
    heat_mag = np.asarray([r[5] for r in rows], dtype=np.float64)
    work = np.asarray([r[6] for r in rows], dtype=np.float64)
    work_mag = np.asarray([r[7] for r in rows], dtype=np.float64)
    lysis = None
    if status == "lysed":  # OL2 milestone 2: the release, booked on the end row (§0.2d item 7).
        counts, supplied, f, heat, heat_mag, work, work_mag, lysis = _release(
            world, layout, tables, counts, supplied, f, heat, heat_mag, work, work_mag,
            float(final["time"]),
        )  # fmt: skip
    booked, booked_mag = work, work_mag
    if divides:  # The shear work is done on the lineage; the sink takes F_v (§0.2d item 7).
        booked, booked_mag = work + shear - sink, work_mag + fission_mag
    residual = ledger.residual(heat, booked, f, f[0])
    tolerance = ledger.closure_tolerance(heat_mag, booked_mag, f, f[0])
    closes = bool(np.all(np.abs(residual) <= tolerance))
    worst = int(np.argmax(np.abs(residual) - tolerance))
    refused = None
    if not closes:
        refused = (
            f"the ledger does not close: residual {residual[worst]:.3g} k_BT at row {worst} "
            f"exceeds its rounding bound {tolerance[worst]:.3g}"
        )
        status = "refused"
    closure = {
        "checked": True,
        "holds": closes,
        "max_abs_residual_kT": float(np.max(np.abs(residual))),
        "tolerance_rtol": ledger.RTOL,
        "refused": refused,
        "reads": "every law of this family is passive: the residual is rounding, and a run whose "
        "books do not close is refused",
        "observations_censored": censored,
    }
    R_declared = len(world.steps)
    declared = np.r_[np.arange(R_declared), structure.steps + np.arange(R_declared)]
    row_arrays = {
        "row_time": np.asarray([r[2] for r in rows], dtype=np.float64),
        "row_event": np.asarray([r[1] for r in rows], dtype=np.int64),
        "row_kind": np.asarray([r[0] for r in rows], dtype=np.int8),
        "place_count": counts[:, :places],
        "reservoir_supplied": supplied[:, :places],
        "channel_fired": fired[:, declared],
        "event_heat_kT": heat,
        "reservoir_work_kT": work,
        "free_energy_kT": f,
        "ledger_residual_kT": residual,
    }
    if world.geometry is not None:  # OL2: the membrane's footprint W at each row (quanta).
        row_arrays["membrane_footprint_quanta"] = counts[:, :places] @ geometry.place_quanta(
            world, places
        )
    division_report = None
    if divides:
        row_arrays["shear_work_kT"] = shear
        row_arrays["discarded_free_energy_kT"] = sink
        lysis_time = float(final["time"])
        division_report = {
            "fissions": division.fission_arrays(holder.attempts, places),
            "lives": division.lives(
                holder.attempts, world, status, lysis_time if status == "lysed" else end_time
            ),
        }
    osmotic_report = None
    if world.conventions.lumen_volume == "osmotic":  # OL2 milestone 2's rows and report.
        rows_v = [lumen.host_volume_L(world, c[:places]) for c in counts]
        rows_sigma = [lumen.host_tension(world, c[:places]) for c in counts]
        row_arrays["lumen_volume_L"] = np.asarray(rows_v, dtype=np.float64)
        row_arrays["tension_N_per_m"] = np.asarray(rows_sigma, dtype=np.float64)
        osmotic_report = _osmotic_report(world, counts[:, :places], lysis)
    trace = {}
    if spec.experiment.trace:
        trace = {
            "event_time": np.concatenate(holder.times) if holder.times else np.zeros(0),
            "event_channel": np.concatenate(holder.channels).astype(np.int32)
            if holder.channels
            else np.zeros(0, dtype=np.int32),
        }
    diagnostics = {}
    if structure.uniforms:
        diagnostics["event_uniforms"] = (
            np.concatenate(holder.draws) if holder.draws else np.zeros((0, 2))
        )
    qualifier = keys.qualifier(spec.fingerprint, "fresh", None)
    record = None
    if holder.diagnostic is not None:  # §0.2d item 10.5 (diagnostic.py)
        d = holder.diagnostic
        device = kernel.STATUS[int(final["status"])]
        if device in ("complete", "inert", "stalled", "capacity") and not d["ended_by_stop"]:
            d["draws"].append((d["key"], d["counter"], diagnostic.ENDED))
        body, arrays = diagnostic.build(
            spec, layout, holder, status, start["counts"], counts[-1], world_id(world),
            np.concatenate(holder.draws) if holder.draws else None,
        )  # fmt: skip
        record = {"body": body, "arrays": arrays}
    return WorldRun(
        spec=spec,
        structure=structure,
        verdict=verdict,
        world_report=report,
        status=status,
        rows=row_arrays,
        trace=trace,
        diagnostics=diagnostics,
        closure=closure,
        qualifier=qualifier,
        final=final,
        timings=timings,
        osmotic=osmotic_report,
        division=division_report,
        diagnostic=record,
    )
