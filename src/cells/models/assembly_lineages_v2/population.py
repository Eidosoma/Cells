"""cells.shared_pool@1, the first cells.population_structure@1: K vesicle slots on one shared pool,
one world-level SSA (OL2 milestone 3; docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1.8; the design note's
§0.2c rules 13–15 and §0.2d items 5, 6 and 10).

**The world** declares `population = {structure: cells.shared_pool@1, slots: K, founders: [{place:
count} of every finite membrane and lumen place, ...]}`, with a geometry (so a vesicle never
empties: §0.2c rule 5's floor). Its `founder` holds the pool, with every vesicle place 0. Founder i
takes slot i and key i:0 (cells.relations' §1.3); the other slots start empty.

**F is additive** over the pool and the vesicles: F = F(pool) + Σ_alive F_v(slot), with F_v a
vesicle's own F and its closure cost.

**The selection map** (§0.2d item 5): groups in order, the pool, then slots 0 to K − 1; a step
with a membrane or lumen place is every slot's, the others the pool's. Each group's channels are
its steps forward, then reverse; every total is a serial fold in those orders. Three uniforms per
draw from the world's stream (domain 5, carrier word 0) at the world's draw count: τ = −ln u1/a0,
the group the first whose running total exceeds min(u2·a0, nextafter(a0, 0)), the channel the
first in it whose running total exceeds min(u3·a_g, nextafter(a_g, 0)). Every slot's rates are the
single assembly's at the slot's vesicle with the pool (kernel.rates), so a world of one slot has
OL1's rate table.

**A vesicle's lysis** (an event whose end state has σ > σ_max) stops the world for the host: the
vesicle's molecules go to their pool places (a held place's reservoir takes them back), its closure
cost is released, its slot frees, and one row books q = −(F(after) − F(before)) + w (§0.2d item 7).
The world then goes on.
"""

import functools
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError, bounded_integer
from cells.models.assembly_lineages import folds
from cells.models.assembly_lineages_v2 import MODEL_ID, SHARED_POOL, kernel, streams
from cells.models.assembly_lineages_v2.interfaces import PopulationStructure
from cells.modules import Citation
from cells.registry import laws as law_registry

MAX_SLOTS = 1024
SLOT_LYSED = len(kernel.STATUS)  # a host stop: one slot's vesicle lysed (the run goes on)
STATUS = (*kernel.STATUS, "slot_lysed")


def parse_data(raw, world):
    if not isinstance(raw, dict) or raw.get("structure") != SHARED_POOL:
        raise ConfigError(f"world: population names its structure, {SHARED_POOL}")
    if set(raw) != {"structure", "slots", "founders"}:
        raise ConfigError("world: population is {structure, slots, founders}")
    if world.geometry is None:
        raise ConfigError(
            "world: a population needs a geometry: its floor keeps every vesicle from emptying "
            "(§0.2c rule 5)"
        )
    slots = bounded_integer(raw["slots"], "world: population slots", maximum=MAX_SLOTS)
    vesicle = [p.name for p in world.places if p.phase in ("membrane", "lumen") and not p.held]
    if any(world.founder[world.place_index(name)] for name in vesicle):
        raise ConfigError("world: a population's founder is the pool's: every vesicle place 0")
    founders = raw["founders"]
    if type(founders) is not list or not 1 <= len(founders) <= slots:
        raise ConfigError("world: population founders is a list of 1 to `slots` vesicles")
    out = []
    for i, entry in enumerate(founders):
        if not isinstance(entry, dict) or set(entry) != set(vesicle):
            raise ConfigError(
                f"world: population founder {i} gives every membrane and lumen place: {vesicle}"
            )
        counts = [0] * len(world.places)
        for name in vesicle:
            counts[world.place_index(name)] = bounded_integer(
                entry[name], f"world: population founder {i} {name}", minimum=0
            )
        out.append(tuple(counts))
    declared = [{name: int(entry[name]) for name in vesicle} for entry in founders]
    return {"slots": slots, "founders": tuple(out), "declared": declared}


def data_to_dict(data):
    return {"structure": SHARED_POOL, "slots": data["slots"], "founders": data["declared"]}


def founder_vectors(world):
    """Each founder vesicle with the pool, as a whole-world state of one assembly."""
    pool = np.asarray(world.founder, dtype=np.int64)
    return tuple(tuple((pool + np.asarray(v)).tolist()) for v in world.population["founders"])


FORMULAS = {
    "free_energy": "F = F(pool) + sum over living slots of F_v(slot), F_v the vesicle's own F with "
    "its closure cost",
    "groups": "the pool, then slots 0 to K - 1, in slot order; a step with a membrane or lumen "
    "place is every slot's, the others the pool's; a group's channels are its steps forward, then "
    "reverse",
    "selection": "u1, u2, u3 from domain 5 (carrier word 0) at the world's draw count: tau = "
    "-ln u1 / a0; the group the first whose running total exceeds min(u2 a0, nextafter(a0, 0)); "
    "the channel the first in it whose running total exceeds min(u3 a_g, nextafter(a_g, 0)); "
    "serial folds throughout",
    "lysis": "a slot's event whose end state has sigma > sigma_max: its molecules to their pool "
    "places, its closure cost released, its slot freed; one row books q = -(F(after) - F(before)) "
    "+ w",
}
TEST = "tests/unit/test_assembly_lineages_v2_population.py::test_one_slot_has_the_single_rate_table"

LAW = law_registry.BUILTIN.register(
    PopulationStructure(
        "cells.shared_pool@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1.8; docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.2c "
            "rules 13-15 and §0.2d items 5-7 (the shared pool, R5); docs/RELATIONSHIPS_DESIGN.md "
            "§1.3-§1.4 (P-b, keys)",
            "one world-level SSA over K vesicle slots on one pool",
            "no numbers taken",
            ("c_ext is held: for a finite pool a declared approximation, its drift reported",),
        ),
        test=TEST,
        data=("slots", "founders"),
        parse_data=parse_data,
        data_to_dict=data_to_dict,
        formulas=FORMULAS,
    )
)
assert LAW.law_id == SHARED_POOL


# ------------------------------------------------------------------ the device program


class Lane(NamedTuple):
    pool: object  # [P] int64: the pool's places (every vesicle place 0)
    slots: object  # [K, P] int64: each slot's vesicle places (every pool place 0)
    alive: object  # [K] bool
    time: object
    events: object  # committed events
    counter: object  # the world stream's draws (domain 5): committed, discarded or ending
    supplied: object  # [P]: molecules taken from each held place's reservoir, net
    heat: object
    heat_magnitude: object
    work: object
    work_magnitude: object
    rates: object  # [K + 1, 2R]: the pool group's, then each slot's (0 off the group)
    world_stream: object
    status: object
    lysed_slot: object  # the slot whose event lysed it (status SLOT_LYSED), else -1


class Event(NamedTuple):
    committed: object
    group: object  # 0 the pool, 1 + k slot k; -1 uncommitted
    channel: object  # the kernel's signed code; 0 uncommitted
    time: object
    heat: object
    heat_magnitude: object
    work: object
    work_magnitude: object
    uniforms: object  # (u1, u2, u3) of the draw, committed or not


class Masks(NamedTuple):
    vesicle: object  # [2R] bool: the slots' channels
    pool: object  # [2R] bool: the pool's channels
    place_vesicle: object  # [P] bool: membrane and lumen places


def masks(world, capacity_places, capacity_steps):
    R = capacity_steps
    vesicle = np.zeros(R, dtype=bool)
    for r, step in enumerate(world.steps):
        names = [name for name, _ in (*step.reactants, *step.products)]
        vesicle[r] = any(world.places[world.place_index(n)].phase != "pool" for n in names)
    both = np.concatenate((vesicle, vesicle))
    place = np.zeros(capacity_places, dtype=bool)
    place[: len(world.places)] = [p.phase != "pool" for p in world.places]
    return Masks(both, ~both, place)


def all_rates(pool, slots, alive, layout, structure, m):
    def one(vesicle):
        c = pool + vesicle
        totals = kernel.totals_of(c, layout)
        factor_state, term_states = kernel.states(c, totals, layout, structure)
        return kernel.rates(c, totals, factor_state, term_states, layout, structure)

    per_slot = jnp.where(m.vesicle[None, :] & alive[:, None], jax.vmap(one)(slots), 0.0)
    pool_rates = jnp.where(m.pool, one(jnp.zeros_like(pool)), 0.0)
    return jnp.concatenate((pool_rates[None, :], per_slot), axis=0)


def event(lane, layout, structure, m):
    R = structure.steps
    running = lane.status == kernel.RUNNING
    prefixes = jax.vmap(lambda a: folds.prefix(a, jnp, structure.unroll))(lane.rates)
    totals = prefixes[:, -1]
    running_totals = folds.prefix(totals, jnp, structure.unroll)
    a0 = running_totals[-1]
    u = streams.uniforms(lane.world_stream, lane.counter, 3)
    wait = -jnp.log(u[0]) / jnp.where(a0 > 0, a0, 1.0)
    group = jnp.argmax(running_totals > jnp.minimum(u[1] * a0, jnp.nextafter(a0, 0.0)))
    a_g = totals[group]
    channel = jnp.argmax(prefixes[group] > jnp.minimum(u[2] * a_g, jnp.nextafter(a_g, 0.0)))
    finite = jnp.isfinite(a0) & jnp.isfinite(wait)
    usable = finite & (a0 > 0) & (wait > 0)
    in_time = lane.time + wait <= layout.horizon
    step = channel % R
    forward = channel < R
    places = layout.entry_place[step]
    alpha, beta = layout.entry_alpha[step], layout.entry_beta[step]
    change = jnp.where(forward, beta - alpha, alpha - beta)
    held = layout.entry_held[step]
    delta = jnp.zeros_like(lane.pool).at[places].add(jnp.where(held, 0, change))
    pool_delta = jnp.where(m.place_vesicle, 0, delta)
    slot = jnp.maximum(group - 1, 0)
    in_slot = group > 0
    pool = lane.pool + pool_delta
    slots = lane.slots.at[slot].add(jnp.where(in_slot, delta - pool_delta, 0))
    supplied = lane.supplied.at[places].add(jnp.where(held, -change, 0))
    rates = all_rates(pool, slots, lane.alive, layout, structure, m)
    reverse = jnp.where(forward, channel + R, channel - R)
    back = rates[group, reverse]
    heat = jnp.where(
        back > 0,
        jnp.log(lane.rates[group, channel]) - jnp.log(jnp.where(back > 0, back, 1.0)),
        jnp.nan,  # A committed event always has a reverse (the floor keeps every vesicle).
    )
    work = jnp.where(forward, layout.step_work[step], -layout.step_work[step])
    membrane = jnp.sum(jnp.where(layout.place_phase == kernel.MEMBRANE, slots, 0), axis=1)
    fits = (jnp.max(slots) <= structure.molecules) & (jnp.max(pool) <= structure.molecules)
    fits = fits & (jnp.max(membrane) <= structure.molecules)
    lysed = in_slot & kernel.lysis_at(pool + slots[slot], layout)
    events = lane.events + 1
    status = jnp.where(
        lysed,
        SLOT_LYSED,
        jnp.where(events >= layout.event_limit, kernel.EVENT_LIMIT, kernel.RUNNING),
    ).astype(jnp.int32)
    after = lane._replace(
        pool=pool,
        slots=slots,
        time=lane.time + wait,
        events=events,
        counter=lane.counter + 1,
        supplied=supplied,
        heat=lane.heat + heat,
        heat_magnitude=lane.heat_magnitude + jnp.abs(heat),
        work=lane.work + work,
        work_magnitude=lane.work_magnitude + jnp.abs(work),
        rates=rates,
        status=status,
        lysed_slot=jnp.where(lysed, slot, -1).astype(jnp.int32),
    )
    commit = running & usable & in_time & fits
    halted = jnp.where(
        ~finite,
        kernel.STALLED,
        jnp.where(a0 == 0, kernel.INERT, jnp.where(~in_time, kernel.COMPLETE, kernel.CAPACITY)),
    ).astype(jnp.int32)
    stopped = lane._replace(status=halted, counter=lane.counter + 1)  # the draw is spent
    lane = kernel._select(commit, after, kernel._select(running, stopped, lane))
    signed = jnp.where(forward, step + 1, -(step + 1)).astype(jnp.int32)
    return lane, Event(
        commit,
        jnp.where(commit, group, -1).astype(jnp.int32),
        jnp.where(commit, signed, 0),
        lane.time,
        lane.heat,
        lane.heat_magnitude,
        lane.work,
        lane.work_magnitude,
        jnp.where(running, u, jnp.nan),
    )


@functools.lru_cache(maxsize=16)
def program(structure):
    def advance(lanes, layouts, m):
        def body(current, _):
            return jax.vmap(lambda la, lo, ma: event(la, lo, structure, ma))(current, layouts, m)

        return jax.lax.scan(body, lanes, None, length=structure.chunk)

    def refresh(lanes, layouts, m):
        def one(la, lo, ma):
            return la._replace(rates=all_rates(la.pool, la.slots, la.alive, lo, structure, ma))

        return jax.vmap(one)(lanes, layouts, m)

    return jax.jit(advance), jax.jit(refresh)


# ------------------------------------------------------------------ the host run

ROW_KINDS = ("start", "periodic", "end", "observed", "shear", "lysis", "transfer")
START, PERIODIC, END, OBSERVED, SHEAR, LYSIS, TRANSFER = range(7)


class _State:
    """The world on the host: the pool, the slots, who lives there, and the reservoirs."""

    def __init__(self, pool, slots, alive, keys, supplied):
        self.pool, self.slots, self.alive = pool.copy(), slots.copy(), alive.copy()
        self.keys, self.supplied = keys.copy(), supplied.copy()

    def copy(self):
        return _State(self.pool, self.slots, self.alive, self.keys, self.supplied)


def _energy(spec, layout):
    """F of a world state: F(pool) + sum over living slots of [F(pool + slot) - F(pool) + C]."""
    from cells.models.assembly_lineages_v2 import geometry, ledger, model

    world = spec.model.world
    tables = model.tables(spec)
    closure = geometry.closure_kT(world)

    def full(c):
        return ledger.free_energy(c, tables, world.terms, layout.terms)

    def world_f(state):
        base = full(state.pool)
        parts = [base] + [
            full(state.pool + state.slots[k]) - base + closure for k in np.flatnonzero(state.alive)
        ]
        return float(np.sum(parts))

    return world_f


def run(spec):
    """One population world, from its founders to the end of its lifecycle (module docstring)."""
    from time import perf_counter

    from cells.models.assembly_lineages import keys as keys_rules
    from cells.models.assembly_lineages_v2 import balance, diagnostic, ledger, lumen, model
    from cells.models.assembly_lineages_v2 import runner as single

    if not diagnostic.partitionable():
        raise ConfigError(
            "This family's block draws need JAX's partitionable threefry: "
            "jax_threefry_partitionable is off, so the run is refused (§0.2d item 9)"
        )
    world = spec.model.world
    K = world.population["slots"]
    structure, layout = model.structure(spec), model.layout(spec)
    kernel.refuse_unknown(structure)
    osmotic = world.conventions.lumen_volume == "osmotic"
    verdict = balance.osmotic_verdict() if osmotic else balance.geometry_verdict()
    P, R = structure.places, structure.steps
    m = masks(world, P, R)
    founders = world.population["founders"]
    slots = np.zeros((K, P), dtype=np.int64)
    for i, f in enumerate(founders):
        slots[i, : len(f)] = f
    alive = np.arange(K) < len(founders)
    keys = np.where(alive, np.arange(K, dtype=np.int64) << 32, -1)  # founder i holds i:0
    state = _State(model.founder(spec), slots, alive, keys, np.zeros(P, dtype=np.int64))
    start = state.copy()
    stream = streams.stream_key_data(layout.base_key, streams.WORLD_CARRIER, "world")
    zero = np.float64(0.0)
    lane = Lane(state.pool, state.slots, state.alive, zero, np.int64(0), np.int64(0),
                state.supplied, zero, zero, zero, zero, np.zeros((K + 1, 2 * R)),
                np.asarray(stream), np.int32(kernel.RUNNING), np.int32(-1))  # fmt: skip
    stack = functools.partial(jax.tree_util.tree_map, lambda x: np.asarray(x)[None])
    layouts, ms = stack(layout), stack(m)
    advance, refresh = program(structure)
    started = perf_counter()
    lanes = refresh(stack(lane), layouts, ms)
    world_f = _energy(spec, layout)
    events, draws, stops, lyses = [], [], [], []
    extra = np.zeros(4)  # the host's bookings: heat, |heat|, work, |work|
    while True:
        status = int(np.asarray(lanes.status)[0])
        if status == kernel.RUNNING:
            lanes, out = advance(lanes, layouts, ms)
            host = jax.tree_util.tree_map(lambda a: np.asarray(a)[:, 0], out)
            ran = ~np.isnan(host.uniforms[:, 0])
            draws.append((host.uniforms[ran], host.committed[ran]))
            c = host.committed
            if c.any():
                events.append(np.stack([host.group[c], host.channel[c]], axis=1))
                events.append(np.stack([host.time[c], host.heat[c], host.heat_magnitude[c],
                                        host.work[c], host.work_magnitude[c]], axis=1))  # fmt: skip
            continue
        if status != SLOT_LYSED:
            break
        host = jax.tree_util.tree_map(lambda a: np.array(a)[0], lanes)
        state = _State(host.pool, host.slots, host.alive, state.keys, host.supplied)
        before = world_f(state)
        s = int(host.lysed_slot)
        record = _release(world, layout, state, s)
        q = -(world_f(state) - before) + record["release_reservoir_work_kT"]
        record |= {"time_s": float(host.time), "slot": s, "key": int(state.keys[s]),
                   "event": int(host.events), "release_heat_kT": q}  # fmt: skip
        extra += [q, abs(q), record["release_reservoir_work_kT"],
                  abs(record["release_reservoir_work_kT"])]  # fmt: skip
        lyses.append(record)
        stops.append((int(host.events), LYSIS, float(host.time), state.copy(), extra.copy()))
        host = host._replace(pool=state.pool, slots=state.slots, alive=state.alive,
                             supplied=state.supplied, status=np.int32(kernel.RUNNING),
                             lysed_slot=np.int32(-1))  # fmt: skip
        lanes = refresh(stack(host), layouts, ms)
    run_seconds = perf_counter() - started
    final = jax.tree_util.tree_map(lambda a: np.array(a)[0], lanes)
    return _assemble(spec, structure, layout, m, verdict, start, state.keys, events, draws,
                     stops, lyses, final, world_f, run_seconds, keys_rules, ledger, lumen,
                     single)  # fmt: skip


def _release(world, layout, state, s):
    """A lysed slot's molecules to their pool places (a held place's reservoir takes them back,
    with its reservoir work), its slot freed. Returns the record (without its heat)."""
    from cells.models.assembly_lineages_v2 import model

    held_mu = model.place_arrays(world, layout.place_held.shape[0])[5]
    pool_index = {p.species: i for i, p in enumerate(world.places) if p.phase == "pool"}
    returned, work = {}, 0.0
    for i, place in enumerate(world.places):
        amount = int(state.slots[s, i])
        if place.phase == "pool" or amount == 0:
            continue
        j = pool_index[place.species]
        returned[world.places[j].name] = returned.get(world.places[j].name, 0) + amount
        if world.places[j].held:
            state.supplied[j] -= amount
            work -= amount * float(held_mu[j])
        else:
            state.pool[j] += amount
    from cells.models.assembly_lineages_v2 import lumen

    sigma = lumen.host_tension(world, (state.pool + state.slots[s])[: len(world.places)])
    state.slots[s] = 0
    state.alive[s] = False
    return {"returned": returned, "release_reservoir_work_kT": work, "sigma_N_per_m": sigma}


def _assemble(spec, structure, layout, m, verdict, start, keys, events, draws, stops, lyses,
              final, world_f, run_seconds, keys_rules, ledger, lumen, single):  # fmt: skip
    from cells.models.assembly_lineages_v2 import geometry

    world = spec.model.world
    places = len(world.places)
    status = STATUS[int(final.status)]
    pairs = events[0::2]
    numbers = events[1::2]
    codes = np.concatenate(pairs) if pairs else np.zeros((0, 2), dtype=np.int64)
    values = np.concatenate(numbers) if numbers else np.zeros((0, 5))
    count_change, supply_change = single.changes(layout, structure)
    R = structure.steps
    index = np.where(codes[:, 1] > 0, codes[:, 1] - 1, R + (-codes[:, 1] - 1)).astype(np.int64)
    horizon = spec.experiment.time_horizon_s
    end_time = horizon if status in ("complete", "inert") else float(final.time)
    # The rows: the start, every row_every events, each observation, each stop, the end.
    marks = [(0, START, 0.0)]
    every = spec.experiment.row_every_events
    marks += [(e, PERIODIC, float(values[e - 1, 0])) for e in range(every, len(codes) + 1, every)]
    times = values[:, 0]
    for t in spec.experiment.observation_times_s:
        if t <= end_time:
            marks.append((int(np.searchsorted(times, t, side="right")), OBSERVED, t))
    marks += [(n, kind, t) for n, kind, t, *_ in stops]
    marks.append((len(codes), END, end_time))
    order = {START: 0, PERIODIC: 1, OBSERVED: 1, SHEAR: 2, LYSIS: 2, TRANSFER: 2, END: 3}
    marks.sort(key=lambda x: (x[0], order[x[1]], x[2]))
    state, stop_i, e = start.copy(), 0, 0
    extra = np.zeros(4)
    rows = []
    for n, kind, t in marks:
        while e < n:  # replay the events up to this row, in exact integers
            change = count_change[index[e]]
            state.pool += np.where(m.place_vesicle, 0, change)
            if codes[e, 0] > 0:
                state.slots[codes[e, 0] - 1] += np.where(m.place_vesicle, change, 0)
            state.supplied += supply_change[index[e]]
            e += 1
            while stop_i < len(stops) and stops[stop_i][0] == e and stops[stop_i][1] != END:
                state, extra = stops[stop_i][3].copy(), stops[stop_i][4]
                stop_i += 1
        device = values[n - 1, 1:] if n > 0 else np.zeros(4)
        rows.append((kind, n, t, state.copy(), device + extra))
    if not (np.array_equal(state.pool, final.pool) and np.array_equal(state.slots, final.slots)
            and np.array_equal(state.supplied, final.supplied)):  # fmt: skip
        raise AssertionError(
            "The rows rebuilt from the events differ from the world's state: a fault"
        )
    f = np.asarray([world_f(r[3]) for r in rows])
    booked = np.stack([r[4] for r in rows])
    heat, heat_mag, work, work_mag = booked.T
    residual = ledger.residual(heat, work, f, f[0])
    tolerance = ledger.closure_tolerance(heat_mag, work_mag, f, f[0])
    closes = bool(np.all(np.abs(residual) <= tolerance))
    worst = int(np.argmax(np.abs(residual) - tolerance))
    refused = None
    if not closes:
        refused = (f"the ledger does not close: residual {residual[worst]:.3g} k_BT at row {worst} "
                   f"exceeds its rounding bound {tolerance[worst]:.3g}")  # fmt: skip
        status = "refused"
    quanta = geometry.place_quanta(world, structure.places)
    slot_counts = np.stack([r[3].slots[:, :places] for r in rows])
    alive = np.stack([r[3].alive for r in rows])
    key_rows = np.where(alive, keys[None, :], -1)
    V = np.zeros(alive.shape)
    sigma = np.zeros(alive.shape)
    for r, row in enumerate(rows):
        for k in np.flatnonzero(row[3].alive):
            c = (row[3].pool + row[3].slots[k])[:places]
            V[r, k], sigma[r, k] = lumen.host_volume_L(world, c), lumen.host_tension(world, c)
    row_arrays = {
        "row_time": np.asarray([r[2] for r in rows]),
        "row_event": np.asarray([r[1] for r in rows], dtype=np.int64),
        "row_kind": np.asarray([r[0] for r in rows], dtype=np.int8),
        "pool_count": np.stack([r[3].pool[:places] for r in rows]),
        "slot_count": slot_counts,
        "slot_key": key_rows,
        "reservoir_supplied": np.stack([r[3].supplied[:places] for r in rows]),
        "event_heat_kT": heat,
        "reservoir_work_kT": work,
        "free_energy_kT": f,
        "ledger_residual_kT": residual,
        "membrane_footprint_quanta": np.where(alive, slot_counts @ quanta[:places], 0),
        "lumen_volume_L": V,
        "tension_N_per_m": sigma,
    }
    closure = {"checked": True, "holds": closes,
               "max_abs_residual_kT": float(np.max(np.abs(residual))),
               "tolerance_rtol": ledger.RTOL, "refused": refused,
               "reads": "every law of this family is passive: the residual is rounding, and a run "
               "whose books do not close is refused", "observations_censored": 0}  # fmt: skip
    trace = {}
    if spec.experiment.trace:
        trace = {"event_time": times.copy(), "event_group": codes[:, 0].astype(np.int32),
                 "event_channel": codes[:, 1].astype(np.int32)}  # fmt: skip
    all_draws = np.concatenate([d for d, _ in draws]) if draws else np.zeros((0, 3))
    committed = np.concatenate([c for _, c in draws]) if draws else np.zeros(0, dtype=bool)
    diagnostics = {}
    if structure.uniforms:
        diagnostics["event_uniforms"] = all_draws[committed]
    report = {
        "slots": int(world.population["slots"]),
        "founders": len(world.population["founders"]),
        "lyses": lyses,
        "draws": int(len(all_draws)),
        "reads": "one world-level SSA (cells.shared_pool@1); each lysis frees its slot, and the "
        "world goes on",
    }
    timings = {"run_seconds": run_seconds, "events": int(len(codes)), "lanes": 1}
    return single.WorldRun(
        spec=spec, structure=structure, verdict=verdict,
        world_report={"population": "the kernel's check on its probe; each slot's rates are the "
                      "single assembly's (kernel.rates)"},
        status=status, rows=row_arrays, trace=trace, diagnostics=diagnostics, closure=closure,
        qualifier=keys_rules.qualifier(spec.fingerprint, "fresh", None), final=final._asdict(),
        timings=timings, osmotic=None, division=None, diagnostic=None, population=report,
    )  # fmt: skip


def lives(run):
    """The lives as cells.relations' Life fields: founder i holds i:0 in slot i (sub-lineage i);
    a life ends lysed at its lysis, or is censored at the run's end."""
    from cells.models.assembly_lineages import keys as keys_rules

    rows = run.rows
    end_time = float(rows["row_time"][-1])
    lysed = {record["key"]: record for record in run.population["lyses"]}
    out = []
    for k, key in enumerate(rows["slot_key"][0].tolist()):
        if key < 0:
            continue
        life = keys_rules.carrier_id(key)
        ended = lysed.get(key)
        out.append({
            "id": life, "key": int(key), "lineage": int(key >> 32), "birth_time": 0.0,
            "birth_kind": "founder", "generation": 0, "root": life, "declared_by": MODEL_ID,
            "slot": f"slot:{k}", "parent": "", "share": float("nan"), "donor": "",
            "predecessor": "", "birth_event": "",
            "end_time": ended["time_s"] if ended else end_time,
            "end_reason": "lysed" if ended else "censored",
            "end_event": f"event:lysis/{key}" if ended else "",
        })  # fmt: skip
    return out
