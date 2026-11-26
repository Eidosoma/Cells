"""cells.population.shared_pool@1, the first cells.population_structure@1: K vesicle slots on one shared pool,
one world-level SSA (OL2 milestone 3; docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1.8; the design note's
§0.2c rules 13–15 and §0.2d items 5, 6 and 10).

**The world** declares `population = {structure: cells.population.shared_pool@1, slots: K, founders: [{place:
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

**Checkpoints** (FR-22, rung P; checkpoints.py): run(spec, stop=k) stops the world after its k-th
committed event and that event's own host action (a lysis), before the next draw, and ends
`stopped`, every life censored; its state is kept for a checkpoint (WorldRun.checkpoint).
run(spec, start=checkpoint) continues it: the device lane is restored verbatim (rates and sums
included, never recomputed) and the host's state with it, so the resumed run's trace, rows and
ledger are the uninterrupted run's after the cut, bitwise. Its rows count events from the world's
start (row_event), its periodic rows keep the world's cadence, its sums continue the checkpoint's,
and its ledger is referenced to the world's own initial F; its fission and transfer events keep
the world's numbering.
"""

import functools
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError, bounded_integer
from cells.models.assembly_lineages import folds
from cells.models.assembly_lineages_v2 import (
    MODEL_ID,
    PRESCRIBED_SHELL,
    SHARED_POOL,
    SHEAR_FISSION,
    division,
    kernel,
    pore_clock,
    pore_device,
    streams,
)
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
        "cells.population.shared_pool@1",
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

ROW_KINDS = ("start", "periodic", "end", "observed", "shear", "lysis", "transfer", "replacement")
START, PERIODIC, END, OBSERVED, SHEAR, LYSIS, TRANSFER, REPLACEMENT = range(8)
# FR-35: a withdrawal's row. Its legend entry is written only when a world declares a withdrawal
# (records.py), so every other population's run.json is unchanged.
WITHDRAWAL = len(ROW_KINDS)
WITHDRAWAL_KIND = "withdrawal"


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
        return ledger.state_free_energy(c, tables, world.terms, layout.terms)

    def world_f(state):
        base = full(state.pool)
        parts = [base] + [
            full(state.pool + state.slots[k]) - base + closure for k in np.flatnonzero(state.alive)
        ]
        return float(np.sum(parts))

    return world_f


# E_TRANSFER holds the pool work of every transfer and replacement (their schedule columns' sum).
E_HEAT, E_HEAT_MAG, E_WORK, E_WORK_MAG, E_SHEAR, E_MAG, E_TRANSFER, E_SINK = range(8)
EXTRA = 8  # the host's bookings, then one schedule-work column per declared schedule


class _Context:
    """The host's own records of a population run: keys, sub-lineages, lives, attempts, stops."""

    def __init__(self, spec, layout, state, founders):
        world = spec.model.world
        self.K = world.population["slots"]
        self.columns = [s.index for s in spec.experiment.schedules]
        # FR-31: one work column per hold, after the schedules' (none in a world without one)
        self.holds = [h.index for h in spec.experiment.tension_holds]
        self.extra = np.zeros(EXTRA + len(self.columns) + len(self.holds))
        self.pore_events = []  # FR-31: each rupture's record (pore_clock.event), in order
        self.stop_kinds = []  # FR-31: each applied stop's kind, "schedule" or "pore", in order
        self.clocks, self.pore_draws, self.pore_check = {}, [], None  # FR-31 (run sets them)
        self.device_clock = None  # OL6 S4: the slots' clocks on the device (pore_device.Clock)
        self.pore_vesicles = []  # OL6 S4: each clocked vesicle (pore_device.Vesicle), in order
        self.lineage = np.where(state.alive, np.arange(self.K), -1)  # each slot's sub-lineage
        self.count = {i: 0 for i in range(founders)}  # each sub-lineage's last key count
        self.next_sub = founders
        self.generation = np.zeros(self.K, dtype=np.int64)
        self.fission_counter = {}
        self.attempts, self.stops, self.lyses, self.lives = [], [], [], []
        self.by_index = {s.index: s for s in spec.experiment.schedules}
        self.transfers, self.transfer_counter, self.schedule_draws = [], {}, []
        self.replacements = []  # FR-20: each pool replacement's record (replacement.py)
        self.withdrawals = []  # FR-35: each pool withdrawal's record (withdrawal.py)
        # OL5's run rows: each shear or transfer event's (time, schedule, the state after it, the
        # slots living at its start), for the diagnostic record only (diagnostic.py).
        self.scheduled_after = []
        # FR-35: each withdrawal schedule's washes applied (its draw counter w) and the world's
        # withdrawals before a resumed run: both derived from the applied stops, never stored.
        self.washes, self.withdrawals_before = {}, 0
        self.life_of = {}  # slot -> index into lives
        self.attempts_before = self.transfers_before = 0  # a resumed run's numbering (rung P)
        self.replacements_before = 0
        for k in np.flatnonzero(state.alive):
            self._born(k, int(state.keys[k]), 0.0, "founder", "", int(k), "")

    def restore(self, host, time):
        """The host's state at a checkpoint (checkpoints.py): every counter and sum, and each
        living slot's life continued (birth_kind continued, at the run's start)."""
        arrays, doc = host["arrays"], host["doc"]
        self.lineage = arrays["lineage"].copy()
        self.generation = arrays["generation"].copy()
        self.extra = arrays["extra"].copy()
        self.count = {int(k): int(v) for k, v in doc["count"].items()}
        self.next_sub = int(doc["next_sub"])
        self.fission_counter = {int(k): int(v) for k, v in doc["fission_counter"].items()}
        self.transfer_counter = {int(k): int(v) for k, v in doc["transfer_counter"].items()}
        self.attempts_before = int(doc["attempts"])
        self.transfers_before = int(doc["transfers"])
        self.replacements_before = int(doc.get("replacements", 0))
        self.lives, self.life_of = [], {}
        for life in doc["lives"]:
            slot = int(life["slot"])
            self.life_of[slot] = len(self.lives)
            self.lives.append({
                "id": life["id"], "key": int(life["key"]), "lineage": int(life["lineage"]),
                "birth_time": time, "birth_kind": "continued",
                "generation": int(life["generation"]), "root": life["root"],
                "declared_by": MODEL_ID, "slot": f"slot:{slot}", "parent": "",
                "share": float("nan"), "donor": "", "predecessor": "", "birth_event": "",
                "end_time": None, "end_reason": None, "end_event": "",
            })  # fmt: skip

    def resume(self, state, applied, f_origin, splits):
        """What a checkpoint keeps of the host (checkpoints.py) at a stop: arrays and a doc."""
        living = [
            {"slot": int(s), **{k: self.lives[i][k] for k in ("id", "key", "lineage",
                                                              "generation", "root")}}
            for s, i in sorted(self.life_of.items())
        ]  # fmt: skip
        arrays = {"keys": state.keys.copy(), "lineage": self.lineage.copy(),
                  "generation": self.generation.copy(), "extra": self.extra.copy(),
                  "f_origin": np.float64(f_origin)}  # fmt: skip
        doc = {"count": {str(k): v for k, v in sorted(self.count.items())},
               "next_sub": self.next_sub,
               "fission_counter": {str(k): v for k, v in sorted(self.fission_counter.items())},
               "transfer_counter": {str(k): v for k, v in sorted(self.transfer_counter.items())},
               "attempts": self.attempts_before + len(self.attempts),
               "transfers": self.transfers_before + len(self.transfers),
               "replacements": self.replacements_before + len(self.replacements),
               "applied_stops": applied, "splits": splits, "lives": living}  # fmt: skip
        if self.holds:  # FR-31: each living vesicle's clock (pore_clock.clock_record)
            doc["pores"] = [pore_clock.clock_record(v) for _, v in sorted(self.clocks.items())]
        if self.device_clock is not None:  # OL6 S4: each slot's clock as the device left it
            h, e, k, t_c = (np.asarray(a, dtype=np.float64) for a in self.device_clock)
            doc["pore_clocks"] = [
                {"slot": int(s), "key": int(self.clock_keys[s]), "H": float(h[s]),
                 "threshold_E": float(e[s]), "rate_per_s": float(k[s]), "t_c": float(t_c[s])}
                for s in np.flatnonzero(np.isfinite(e))
            ]  # fmt: skip
        return {"arrays": arrays, "doc": doc}

    def _born(self, slot, key, time, kind, parent, lineage, event, root=None, share=float("nan")):
        from cells.models.assembly_lineages import keys as keys_rules

        life = keys_rules.carrier_id(key)
        self.life_of[slot] = len(self.lives)
        self.lives.append({
            "id": life, "key": key, "lineage": lineage, "birth_time": time, "birth_kind": kind,
            "generation": int(self.generation[slot]), "root": root or life,
            "declared_by": MODEL_ID if kind == "founder" else SHEAR_FISSION, "slot": f"slot:{slot}",
            "parent": parent, "share": share, "donor": "", "predecessor": "", "birth_event": event,
            "end_time": None, "end_reason": None, "end_event": "",
        })  # fmt: skip

    def end(self, slot, time, reason, event=""):
        life = self.lives[self.life_of.pop(slot)]
        life.update(end_time=time, end_reason=reason, end_event=event)

    def book(self, column, shear):
        self.extra[E_SHEAR] += shear
        self.extra[E_MAG] += abs(shear)
        self.extra[EXTRA + self.columns.index(column)] += shear


def run(spec, *, start=None, stop=None):
    """One population world, from its founders to the end of its lifecycle (module docstring).

    start: a checkpoint (checkpoints.Checkpoint) to continue from, or None for a fresh run.
    stop: an event count at which the run stops `stopped`, after that event and its own host
    action, before the next draw; its state is kept for a checkpoint (WorldRun.checkpoint)."""
    from time import perf_counter

    from cells.models.assembly_lineages_v2 import balance, diagnostic, model
    from cells.models.assembly_lineages_v2 import runner as single

    if not diagnostic.partitionable():
        raise ConfigError(
            "This family's block draws need JAX's partitionable threefry: "
            "jax_threefry_partitionable is off, so the run is refused (§0.2d item 9)"
        )
    if stop is not None and (type(stop) is not int or not 1 <= stop < spec.experiment.event_limit):
        raise ConfigError(
            "A stop is an event count from 1 to below experiment.event_limit "
            f"({spec.experiment.event_limit}), not {stop!r}"
        )
    admitted = None
    if start is not None:
        from cells.models.assembly_lineages_v2 import checkpoints

        admitted = checkpoints.admit(spec, start)
        if stop is not None and stop <= start.clock["events"]:
            raise ConfigError(
                f"A stop at {stop} events is not after the checkpoint's {start.clock['events']}"
            )
    world = spec.model.world
    K = world.population["slots"]
    structure, layout = model.structure(spec), model.layout(spec)
    kernel.refuse_unknown(structure)
    osmotic = world.conventions.lumen_volume == "osmotic"
    shell = world.geometry[0] == PRESCRIBED_SHELL  # FR-21: its own probe, as runner.py takes it
    verdict = (
        balance.shell_verdict()
        if shell
        else balance.osmotic_verdict()
        if osmotic
        else balance.geometry_verdict()
    )
    world_report = balance.world_report(spec)  # each slot's rates are the single assembly's
    P, R = structure.places, structure.steps
    m = masks(world, P, R)
    founders = world.population["founders"]
    horizon = spec.experiment.time_horizon_s
    plan, schedule_draws = single._plan(spec, layout.base_key)
    _refuse_shared_replacements(spec, plan)
    world_f = _energy(spec, layout)
    if admitted is None:
        slots = np.zeros((K, P), dtype=np.int64)
        for i, f in enumerate(founders):
            slots[i, : len(f)] = f
        alive = np.arange(K) < len(founders)
        keys = np.where(alive, np.arange(K, dtype=np.int64) << 32, -1)  # founder i holds i:0
        state = _State(model.founder(spec), slots, alive, keys, np.zeros(P, dtype=np.int64))
        ctx = _Context(spec, layout, state, len(founders))
        stream = streams.stream_key_data(layout.base_key, streams.WORLD_CARRIER, "world")
        zero = np.float64(0.0)
        lane = Lane(state.pool, state.slots, state.alive, zero, np.int64(0), np.int64(0),
                    state.supplied, zero, zero, zero, zero, np.zeros((K + 1, 2 * R)),
                    np.asarray(stream), np.int32(kernel.RUNNING), np.int32(-1))  # fmt: skip
        applied, origin = 0, {"start": "fresh", "f": world_f(state), "events": 0}
    else:
        record, saved, host = admitted
        lane = Lane(**{name: saved[name] for name in Lane._fields})
        state = _State(lane.pool, lane.slots, lane.alive, host["arrays"]["keys"], lane.supplied)
        ctx = _Context(spec, layout, _State(state.pool, state.slots, np.zeros(K, dtype=bool),
                                            state.keys, state.supplied), 0)  # fmt: skip
        ctx.restore(host, float(lane.time))
        applied = int(host["doc"]["applied_stops"])
        _count_washes(spec, ctx, plan[:applied])  # FR-35: w is the applied stops', one number
        plan = plan[applied:]  # the stops the checkpoint's run applied are its own
        origin = {"start": record, "f": float(host["arrays"]["f_origin"]),
                  "events": int(lane.events), "counter": int(lane.counter),
                  "splits": int(host["doc"]["splits"]), "extra": ctx.extra.copy(),
                  "sums": np.asarray([lane.heat, lane.heat_magnitude, lane.work,
                                      lane.work_magnitude], dtype=np.float64)}  # fmt: skip
    start_state = state.copy()
    ctx.world_report = world_report
    ctx.schedule_draws = list(schedule_draws)
    # FR-31: each living vesicle's pore clock, by slot, and its rupture a stop (pore_clock.py)
    clocks, pending = {}, []
    on_device = pore_device.clocked(spec)  # OL6 S4: σ from F, the clocks on the device
    if world.hazard is not None and not on_device:
        clocks = {
            int(k): pore_clock.Vesicle(spec, layout.base_key, state.keys[k], state.slots[k], slot=k)
            for k in np.flatnonzero(state.alive)
        }
        if admitted is not None:  # the checkpoint's clocks, each its definition's, or refused
            pore_clock.refuse_other_clocks(clocks, admitted[2]["doc"]["pores"])
        pending = sorted((v.time, k) for k, v in clocks.items() if v.due)  # decided exactly
        pore_clock.refuse_same_time([clocks[k] for _, k in pending], [t for t, _ in plan])
        # the threshold draws are made when the run first holds a vesicle: a resumed run's
        # vesicles drew in the run that wrote its checkpoint (checkpoints.py)
        ctx.pore_draws = [clocks[k].draw() for k in sorted(clocks)] if admitted is None else []
        # the pair's check at the definition's founders' areas, the same in every segment (a
        # resumed run may hold no vesicle)
        areas = [pore_clock.area_m2(world, f) for f in founders]
        ctx.pore_check = {"probe": balance.pore_verdict(),
                          "world": balance.pore_world_report(spec, areas)}  # fmt: skip
    stack = functools.partial(jax.tree_util.tree_map, lambda x: np.asarray(x)[None])
    vesicles, pores = {}, None
    if on_device:  # OL6 S4: each living slot's clock beside the lane (pore_device.py)
        pores = pore_device.constants(world)[None]
        advance_c, rates_c = pore_device.population_program(structure)
        k_slots = np.asarray(rates_c(state.slots[None], stack(layout), pores), dtype=np.float64)[0]
        k_slots = np.where(state.alive, k_slots, 0.0)
        empty = pore_device.Clock(*(np.zeros(len(state.alive)),) * 4)
        if admitted is None:
            ctx.device_clock, born = pore_device.carry_over(
                empty, k_slots, np.full(len(state.alive), -2), state.keys, state.alive, 0.0, 0.0,
                layout.base_key, [pore_clock.area_m2(world, c) for c in state.slots], vesicles)
            ctx.pore_vesicles = born
        else:  # the checkpoint's clocks, as the device left them; each threshold its key's draw
            ctx.device_clock, vesicles = _restore_clocks(world, layout, state, admitted, k_slots)
        ctx.clock_keys = state.keys.copy()
        areas = [pore_clock.area_m2(world, f) for f in founders]
        ctx.pore_check = {"probe": balance.pore_verdict(), "world": balance.pore_world_report(
            spec, areas, sigmas=single._tensions(spec))}  # fmt: skip
    first = _next_stop(plan, pending, horizon)
    limit = layout.event_limit if stop is None else np.int64(min(int(layout.event_limit), stop))
    layouts = stack(layout._replace(horizon=np.float64(first), event_limit=limit))
    ms = stack(m)
    advance, refresh = program(structure)
    started = perf_counter()
    # A restored lane keeps its rates as the device left them: never recomputed (checkpoints.py).
    lanes = stack(lane) if admitted is not None else refresh(stack(lane), layouts, ms)
    vesicle_f = single._vesicle_energy(spec, layout)
    events, draws = [], []
    end_status = None
    while True:
        status = int(np.asarray(lanes.status)[0])
        if status == kernel.RUNNING:
            if on_device:
                device = stack(pore_device.Clock(*ctx.device_clock))
                lanes, device, out = advance_c(lanes, device, layouts, pores, ms)
                ctx.device_clock = pore_device.Clock(*(np.asarray(a)[0] for a in device))
            else:
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
        host = jax.tree_util.tree_map(lambda a: np.array(a)[0], lanes)
        if status == kernel.EVENT_LIMIT and stop is not None and int(host.events) >= stop:
            end_status = "stopped"  # the run's own stop, not the experiment's guard
            break
        fired = None
        if on_device and status in (kernel.COMPLETE, kernel.INERT):  # OL6 S4: an own t_c
            fired = _fired_slot(ctx.device_clock, host.alive, layouts, plan)
        if status == SLOT_LYSED:
            state = _State(host.pool, host.slots, host.alive, state.keys, host.supplied)
            keys_before = state.keys.copy()
            _lyse(world, layout, state, ctx, world_f, int(host.lysed_slot), float(host.time),
                  int(host.events))  # fmt: skip
            if on_device:  # the lysed slot's clock ends with it
                _carry_clocks(world, layout, state, ctx, vesicles, rates_c, keys_before,
                              float(host.time), float(host.time))  # fmt: skip
        elif fired is not None:  # OL6 S4: the earliest slot's pore at its own t_c
            slot, stop_time = fired
            state = _State(host.pool, host.slots, host.alive, state.keys, host.supplied)
            keys_before = state.keys.copy()
            last = float(host.time)
            _rupture_device(spec, layout, state, ctx, world_f, vesicles[slot], stop_time, last,
                            int(host.events))  # fmt: skip
            _carry_clocks(world, layout, state, ctx, vesicles, rates_c, keys_before, last,
                          stop_time)  # fmt: skip
            ctx.stop_kinds.append("pore")
            nxt = _next_stop(plan, pending, horizon)
            layouts = layouts._replace(horizon=np.asarray([nxt]))
            going = kernel.RUNNING if stop_time < horizon else status  # a stop at t_end holds
            host = host._replace(time=np.float64(stop_time), status=np.int32(going))
        elif (
            status in (kernel.COMPLETE, kernel.INERT)
            and pending
            and (not plan or pending[0][0] < plan[0][0])
        ):  # FR-31: a vesicle's rupture at its t*; the draw that crossed it is discarded, counted
            stop_time, k = pending.pop(0)
            state = _State(host.pool, host.slots, host.alive, state.keys, host.supplied)
            _rupture(spec, layout, state, ctx, world_f, clocks.pop(k), int(host.events))
            ctx.stop_kinds.append("pore")
            nxt = _next_stop(plan, pending, horizon)
            layouts = layouts._replace(horizon=np.asarray([nxt]))
            going = kernel.RUNNING if stop_time < horizon else status  # a stop at t_end holds
            host = host._replace(time=np.float64(stop_time), status=np.int32(going))
        elif status in (kernel.COMPLETE, kernel.INERT) and plan:
            stop_time, stop_events = plan.pop(0)  # the draw that crossed it is discarded, counted
            applied += 1
            state = _State(host.pool, host.slots, host.alive, state.keys, host.supplied)
            keys_before, last = state.keys.copy(), float(host.time)
            full = _shear_stop(spec, layout, state, ctx, world_f, vesicle_f, stop_time,
                               stop_events, int(host.events))  # fmt: skip
            if on_device:  # OL6 S4: the clocks to the stop; the newborn draw their own
                ctx.stop_kinds.append("schedule")
                _carry_clocks(world, layout, state, ctx, vesicles, rates_c, keys_before, last,
                              stop_time)  # fmt: skip
            if clocks:  # FR-31: a transfer's removed vesicles take their clocks with them
                ctx.stop_kinds.append("schedule")
                clocks = {k: v for k, v in clocks.items()
                          if state.alive[k] and int(state.keys[k]) == v.key}  # fmt: skip
                pending = [(t, k) for t, k in pending if k in clocks]
            if full:
                end_status = "slots_full"
                host = host._replace(time=np.float64(stop_time))
                break
            nxt = _next_stop(plan, pending, horizon)
            layouts = layouts._replace(horizon=np.asarray([nxt]))
            going = kernel.RUNNING if stop_time < horizon else status  # a stop at t_end holds
            host = host._replace(time=np.float64(stop_time), status=np.int32(going))
        else:
            break
        host = host._replace(pool=state.pool, slots=state.slots, alive=state.alive,
                             supplied=state.supplied, lysed_slot=np.int32(-1),
                             status=np.int32(kernel.RUNNING) if int(host.status) == SLOT_LYSED
                             else host.status)  # fmt: skip
        lanes = refresh(stack(host), layouts, ms)
        if stop is not None and int(host.events) >= stop:  # a lysis at the stop's own event
            end_status = "stopped"
            host = jax.tree_util.tree_map(lambda a: np.array(a)[0], lanes)
            break
    run_seconds = perf_counter() - started
    ctx.clocks = clocks  # FR-31: the living vesicles' clocks, for a checkpoint's host document
    final = jax.tree_util.tree_map(lambda a: np.array(a)[0], lanes)
    if end_status is not None:
        final = host
    state = _State(final.pool, final.slots, final.alive, state.keys, final.supplied)
    return _assemble(spec, structure, layout, m, verdict, start_state, state, ctx, events, draws,
                     ctx.schedule_draws, final, end_status, world_f, run_seconds, origin,
                     applied, stop)  # fmt: skip


def _next_stop(plan, pending, horizon):
    """The device's horizon: the next schedule stop's time, or (FR-31) an earlier vesicle's
    rupture time, or the experiment's horizon."""
    nxt = plan[0][0] if plan else horizon
    if pending and pending[0][0] < nxt:
        return pending[0][0]
    return nxt


def _rupture(spec, layout, state, ctx, world_f, clock, n_events):
    """FR-31: a vesicle's rupture at its t* on the host (pore_clock.py): the opening, then the
    release from the open state, booked as one pore row; its slot frees and the world goes on."""
    world = spec.model.world
    s, time = clock.slot, clock.time
    before = world_f(state)
    work, heat_open, delta_f = pore_clock.opening(world, clock.area, clock.hold.sigma)
    added, took, returned, work_return = pore_clock.release(world, layout, state.slots[s])
    state.pool = state.pool + added
    state.supplied = state.supplied + took
    state.slots[s] = 0
    state.alive[s] = False
    q_release = -(world_f(state) - (before + delta_f)) + work_return
    heat = heat_open + q_release
    ctx.extra[[E_HEAT, E_HEAT_MAG, E_WORK, E_WORK_MAG]] += [
        heat, abs(heat_open) + abs(q_release), work_return, abs(work_return)
    ]  # fmt: skip
    ctx.extra[E_MAG] += abs(work)
    ctx.extra[EXTRA + len(ctx.columns) + ctx.holds.index(clock.hold.index)] += work
    ctx.pore_events.append(
        pore_clock.event(world, clock, heat_open, work, q_release, returned, work_return)
    )
    ctx.end(s, time, "lysed", f"event:lysis/{clock.key}")
    state.keys[s] = -1
    ctx.lineage[s] = -1
    ctx.stops.append((n_events, pore_clock.PORE_ROW, time, state.copy(), ctx.extra.copy()))


def _fired_slot(clock, alive, layouts, plan):
    """OL6 S4: (slot, t_c) of the living slot whose own t_c comes first, when it lies within the
    device's horizon, else None. Two slots' t_c at one time, or a t_c at a schedule stop's, are
    refused (FR-20's rule, in pore_clock.refuse_same_time's words)."""
    t_c = np.where(alive, np.asarray(clock.crossing, dtype=np.float64), np.inf)
    slot = int(np.argmin(t_c))
    time = float(t_c[slot])
    if not time <= float(np.asarray(layouts.horizon)[0]):
        return None
    if int(np.sum(t_c == time)) > 1:
        raise ConfigError(
            f"Two vesicles' pores open at the same time, {time} s: relations have no order "
            "between same-time events, so the run is refused"
        )
    if plan and time == plan[0][0]:
        raise ConfigError(
            f"A pore opens at {time} s, the time of a schedule stop: relations have no order "
            "between same-time events, so the run is refused (FR-20's rule)"
        )
    return slot, time


def _rupture_device(spec, layout, state, ctx, world_f, vesicle, time, last, n_events):
    """OL6 S4: a slot's pore at its own t_c (pore_device.py), booked as _rupture books Phase A's,
    with pore_clock.opening_from_f (no hold, no work); its slot frees and the world goes on."""
    from cells.models.assembly_lineages_v2 import lumen

    world = spec.model.world
    s = vesicle.slot
    h, _, k, _ = ctx.device_clock
    vesicle.time, vesicle.due, vesicle.rate = time, True, float(k[s])
    vesicle.area = pore_clock.area_m2(world, state.slots[s])
    vesicle.sigma = lumen.host_tension(world, state.slots[s][: len(world.places)])
    clock_h = float(h[s]) + vesicle.rate * (time - last)
    before = world_f(state)
    _, heat_open, delta_f = pore_clock.opening_from_f(world, vesicle.area, vesicle.sigma)
    added, took, returned, work_return = pore_clock.release(world, layout, state.slots[s])
    state.pool = state.pool + added
    state.supplied = state.supplied + took
    state.slots[s] = 0
    state.alive[s] = False
    q_release = -(world_f(state) - (before + delta_f)) + work_return
    heat = heat_open + q_release
    ctx.extra[[E_HEAT, E_HEAT_MAG, E_WORK, E_WORK_MAG]] += [
        heat, abs(heat_open) + abs(q_release), work_return, abs(work_return)
    ]  # fmt: skip
    ctx.pore_events.append(pore_device.event_record(vesicle, heat_open, delta_f, q_release,
                                                    returned, work_return, clock_h))  # fmt: skip
    ctx.end(s, time, "lysed", f"event:lysis/{vesicle.key}")
    state.keys[s] = -1
    ctx.lineage[s] = -1
    ctx.stops.append((n_events, pore_clock.PORE_ROW, time, state.copy(), ctx.extra.copy()))


def _carry_clocks(world, layout, state, ctx, vesicles, rates_c, keys_before, time_from, time_to):
    """OL6 S4: the slots' clocks across a host operator (pore_device.carry_over), each new
    vesicle at its new counts' rate."""
    one = jax.tree_util.tree_map(lambda x: np.asarray(x)[None], layout)
    pores = pore_device.constants(world)[None]
    rates = np.asarray(rates_c(state.slots[None], one, pores), dtype=np.float64)[0]
    rates = np.where(state.alive, rates, 0.0)
    areas = [pore_clock.area_m2(world, c) for c in state.slots]
    ctx.device_clock, born = pore_device.carry_over(
        ctx.device_clock, rates, keys_before, state.keys, state.alive, time_from, time_to,
        layout.base_key, areas, vesicles)  # fmt: skip
    ctx.pore_vesicles += born
    ctx.clock_keys = state.keys.copy()


def _restore_clocks(world, layout, state, admitted, rates):
    """OL6 S4: a resumed run's clocks, as its checkpoint's host document holds them (each slot's H,
    threshold, rate and t_c as the device left them, never recomputed), with each living vesicle's
    key and threshold its definition's draw, or the run is refused."""
    saved = {int(c["slot"]): c for c in admitted[2]["doc"].get("pore_clocks", [])}
    K = len(state.alive)
    h, e, k, t_c = np.zeros(K), np.full(K, np.inf), np.zeros(K), np.full(K, np.inf)
    vesicles = {}
    for s in np.flatnonzero(state.alive):
        entry = saved.get(int(s))
        vesicle = pore_device.Vesicle(layout.base_key, int(state.keys[s]),
                                      pore_clock.area_m2(world, state.slots[s]))  # fmt: skip
        if entry is None or entry["key"] != vesicle.key or entry["threshold_E"] != vesicle.energy:
            raise ConfigError(
                "The checkpoint's pore clocks are not its definition's: a living vesicle's key or "
                "threshold differs, or its clock is missing"
            )
        vesicle.slot = int(s)
        vesicles[int(s)] = vesicle
        h[s], e[s] = entry["H"], entry["threshold_E"]
        k[s], t_c[s] = entry["rate_per_s"], entry["t_c"]
    if len(saved) != len(vesicles):
        raise ConfigError("The checkpoint's pore clocks are not its definition's: an empty slot "
                          "holds a clock")  # fmt: skip
    del rates
    return pore_device.Clock(h, e, k, t_c), vesicles


def _lyse(world, layout, state, ctx, world_f, s, time, n_events, at_birth=False):
    """A slot's lysis on the host, booked as one lysis row (module docstring)."""
    before = world_f(state)
    key = int(state.keys[s])
    record = _release(world, layout, state, s)
    w = record["release_reservoir_work_kT"]
    q = -(world_f(state) - before) + w
    record |= {"time_s": time, "slot": s, "key": key, "event": n_events, "release_heat_kT": q,
               "at_birth": at_birth}  # fmt: skip
    if world.hazard is not None:  # FR-31: a pore world labels each lysis by its cause
        record["cause"] = "threshold"
    ctx.extra[[E_HEAT, E_HEAT_MAG, E_WORK, E_WORK_MAG]] += [q, abs(q), w, abs(w)]
    ctx.lyses.append(record)
    ctx.end(s, time, "lysed", f"event:lysis/{key}")
    state.keys[s] = -1
    ctx.lineage[s] = -1
    ctx.stops.append((n_events, LYSIS, time, state.copy(), ctx.extra.copy()))


def _shear_stop(spec, layout, state, ctx, world_f, vesicle_f, time, stop_events, n_events):
    """A stop's shear events, in schedule-index order, each on the assemblies alive at its start,
    in slot order (§0.2d item 10.1). Every daughter lives: daughter 0 takes its parent's slot, the
    others free slots in slot order. Returns True when the run stops `slots_full`."""
    from cells.models.assembly_lineages import keys as keys_rules

    world = spec.model.world
    places = len(world.places)
    for event in stop_events:
        living = [int(x) for x in np.flatnonzero(state.alive)]
        if ctx.by_index[event[1]].kind == "transfer":
            _transfer(spec, layout, state, ctx, world_f, time, ctx.by_index[event[1]], n_events)
            ctx.scheduled_after.append((time, event[1], state.copy(), living))
            continue
        if ctx.by_index[event[1]].kind == "replacement":
            _replace(spec, state, ctx, world_f, time, ctx.by_index[event[1]], n_events)
            continue
        if ctx.by_index[event[1]].kind == "withdrawal":
            _withdraw(spec, layout, state, ctx, world_f, time, ctx.by_index[event[1]], n_events)
            continue
        k = event[2]
        for s in [int(x) for x in np.flatnonzero(state.alive)]:
            parent = int(state.keys[s])
            sub = int(ctx.lineage[s])
            counter = ctx.fission_counter.get(parent, 0)
            free = [int(x) for x in np.flatnonzero(~state.alive)]
            counts = (state.pool + state.slots[s])[:places]
            next_key = keys_rules.key(sub, ctx.count[sub] + 1)
            a = division.attempt(world, counts, parent, counter, event, layout.base_key,
                                 vesicle_f, next_key, free_slots=len(free))  # fmt: skip
            row = ctx.attempts_before + len(ctx.attempts)
            homes = [s, *free[: k - 1]] if a.outcome == "split" else []
            ctx.attempts.append((a, int(ctx.generation[s]), s, homes))
            if a.counter >= 0:
                ctx.fission_counter[parent] = counter + 1
            if a.outcome == "slots_full":
                ctx.scheduled_after.append((time, event[1], state.copy(), living))
                return True
            if a.outcome != "split":
                continue
            ctx.count[sub] += k
            fission = f"event:fission/{row}"
            parent_life = ctx.lives[ctx.life_of[s]]
            ctx.end(s, time, "divided", fission)
            generation = ctx.generation[s] + 1
            sizes = (
                a.daughters[:, :places].sum(axis=1)
                - counts[[i for i, p in enumerate(world.places) if p.phase == "pool"]].sum()
            )
            for j, slot in enumerate(homes):
                state.slots[slot] = 0
                vesicle = a.daughters[j].copy()
                vesicle[[i for i, p in enumerate(world.places) if p.phase == "pool"]] = 0
                state.slots[slot, :places] = vesicle
                state.alive[slot], state.keys[slot] = True, a.keys[j]
                ctx.generation[slot] = generation
                if j == 0:
                    ctx.lineage[slot] = sub  # the first continues its parent's counter
                else:
                    ctx.lineage[slot] = ctx.next_sub  # a new sub-lineage, in world event order
                    ctx.count[ctx.next_sub] = 0
                    ctx.next_sub += 1
                ctx._born(slot, int(a.keys[j]), time, "division", parent_life["id"],
                          int(ctx.lineage[slot]), fission, root=parent_life["root"],
                          share=float(sizes[j] / sizes.sum()))  # fmt: skip
            ctx.book(event[1], a.shear_work)
            ctx.stops.append((n_events, SHEAR, time, state.copy(), ctx.extra.copy()))
            for j, slot in enumerate(homes):  # §0.2d item 10.3: born beyond sigma_max
                if a.lysed[j]:
                    _lyse(world, layout, state, ctx, world_f, slot, time, n_events, at_birth=True)
        ctx.scheduled_after.append((time, event[1], state.copy(), living))
    return False


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


def _transfer(spec, layout, state, ctx, world_f, time, schedule, n_events):
    """A serial transfer on the host (transfer.py): the kept sample, the removed lives, the fresh
    pool, and their booking (the sink, the schedule's work column)."""
    from cells.models.assembly_lineages_v2 import transfer

    world = spec.model.world
    living = [int(x) for x in np.flatnonzero(state.alive)]
    counter = ctx.transfer_counter.get(schedule.index, 0)
    kept, drawn, ctx.transfer_counter[schedule.index] = transfer.sample(
        layout.base_key, schedule, counter, living, schedule.keep
    )
    ctx.schedule_draws += drawn
    empty = state.copy()
    empty.alive[:] = False
    pool_f = world_f(empty)
    removed = [s for s in living if s not in kept]
    vesicles = []
    for s in removed:
        alone = empty.copy()
        alone.alive[s] = True
        vesicles.append(world_f(alone) - pool_f)
    sink = float(np.sum(vesicles)) + pool_f
    event = f"event:transfer/{ctx.transfers_before + len(ctx.transfers)}"
    for s in removed:
        ctx.end(s, time, "removed", event)
        state.slots[s], state.alive[s], state.keys[s], ctx.lineage[s] = 0, False, -1, -1
    state.pool = transfer.replaced_pool(world, schedule, state.pool)
    empty = state.copy()
    empty.alive[:] = False
    work = world_f(empty)
    ctx.extra[E_SINK] += sink
    ctx.extra[E_TRANSFER] += work
    ctx.extra[EXTRA + ctx.columns.index(schedule.index)] += work
    ctx.extra[E_MAG] += abs(sink) + abs(work)
    ctx.transfers.append({"id": event, "time_s": time, "schedule": schedule.index,
                          "draws": [list(d[:3]) for d in drawn], "kept": kept,
                          "removed": removed, "sink_kT": sink, "work_kT": work})  # fmt: skip
    ctx.stops.append((n_events, TRANSFER, time, state.copy(), ctx.extra.copy()))


def _refuse_shared_replacements(spec, plan):
    """FR-20: a replacement stands alone in time. Declared times are refused at parse
    (division.parse_schedules); a Poisson shear drawn at a replacement's time is refused here, on
    the grouped plan, before the first event."""
    kinds = {s.index: s.kind for s in spec.experiment.schedules}
    for time, events in plan:
        alone = [kinds[e[1]] for e in events if kinds[e[1]] in ("replacement", "withdrawal")]
        if len(events) > 1 and alone:
            raise ConfigError(
                f"A {alone[0]} shares the time {time} s with another stop (a Poisson shear); "
                "relations have no order between same-time events"
            )


def _count_washes(spec, ctx, applied_plan):
    """FR-35: a withdrawal schedule's draw counter w is the number of its stops among the applied
    ones, so a resumed run reads it from FR-22's applied-stops record, one number."""
    kinds = {s.index: s.kind for s in spec.experiment.schedules}
    for _, events in applied_plan:
        for event in events:
            if kinds[event[1]] == "withdrawal":
                ctx.washes[event[1]] = ctx.washes.get(event[1], 0) + 1
                ctx.withdrawals_before += 1


def _withdraw(spec, layout, state, ctx, world_f, time, schedule, n_events):
    """A pool withdrawal on the host (withdrawal.py): every slot kept; each molecule of each finite
    pool place withdrawn with probability f on the schedule's stream; the buffer added; the sink,
    the schedule's work column and the mixing heat booked."""
    from cells.models.assembly_lineages_v2 import withdrawal

    world = spec.model.world
    if any(record["time_s"] == time for record in ctx.lyses):
        raise ConfigError(
            f"A lysis at {time} s, the time of withdrawal {schedule.index}: relations have no "
            "order between same-time events"
        )
    before = state.pool.copy()
    withdrawal.refuse_beyond_capacity(world, schedule, before, spec.execution.molecule_capacity)
    wash = ctx.washes.get(schedule.index, 0)
    taken, addresses = withdrawal.draw(layout.base_key, world, schedule, wash, before)
    ctx.washes[schedule.index] = wash + 1
    buffer = withdrawal.buffer_vector(world, schedule, before.size)
    empty = state.copy()
    empty.alive[:] = False

    def pool_f(c):  # F of a pool vector at the pool's volume: the run's own guarded read
        empty.pool = np.asarray(c, dtype=np.int64)
        return world_f(empty)

    energy = withdrawal.booking(pool_f, before, taken, buffer, schedule.fraction, world)
    state.pool = before - taken + buffer
    sink, work, heat = energy["pool_loss_kT"], energy["buffer_F_kT"], energy["mixing_heat_kT"]
    ctx.extra[E_SINK] += sink
    ctx.extra[E_TRANSFER] += work
    ctx.extra[EXTRA + ctx.columns.index(schedule.index)] += work
    ctx.extra[[E_HEAT, E_HEAT_MAG]] += [heat, abs(heat)]
    ctx.extra[E_MAG] += abs(sink) + abs(work)
    ctx.withdrawals.append({
        "id": f"event:withdrawal/{ctx.withdrawals_before + len(ctx.withdrawals)}",
        "time_s": time, "schedule": schedule.index, "fraction": schedule.fraction,
        "before": withdrawal.by_place(world, before),
        "withdrawn": withdrawal.by_place(world, taken),
        "remaining": withdrawal.by_place(world, before - taken),
        "supplied": withdrawal.by_place(world, buffer),
        "draws": [list(a) for a in addresses], **energy,
    })  # fmt: skip
    ctx.stops.append((n_events, WITHDRAWAL, time, state.copy(), ctx.extra.copy()))


def _replace(spec, state, ctx, world_f, time, schedule, n_events):
    """A pool replacement on the host (replacement.py): every slot kept as it stands; the pool's
    finite places take the declared composition; the sink takes F of the old pool, the schedule's
    work column F of the fresh pool."""
    from cells.models.assembly_lineages_v2 import replacement, transfer

    world = spec.model.world
    if any(record["time_s"] == time for record in ctx.lyses):
        raise ConfigError(
            f"A lysis at {time} s, the time of replacement {schedule.index}: relations have no "
            "order between same-time events"
        )
    empty = state.copy()
    empty.alive[:] = False
    old_f, old = world_f(empty), state.pool.copy()
    state.pool = transfer.replaced_pool(world, schedule, state.pool)
    empty = state.copy()
    empty.alive[:] = False
    work = world_f(empty)
    ctx.extra[E_SINK] += old_f
    ctx.extra[E_TRANSFER] += work
    ctx.extra[EXTRA + ctx.columns.index(schedule.index)] += work
    ctx.extra[E_MAG] += abs(old_f) + abs(work)
    removed, supplied = replacement.removed_and_supplied(world, old, state.pool)
    ctx.replacements.append({
        "id": f"event:replacement/{ctx.replacements_before + len(ctx.replacements)}",
        "time_s": time, "schedule": schedule.index, "removed": removed, "supplied": supplied,
        "sink_kT": old_f, "work_kT": work,
    })  # fmt: skip
    ctx.stops.append((n_events, REPLACEMENT, time, state.copy(), ctx.extra.copy()))


def _assemble(spec, structure, layout, m, verdict, start, state, ctx, events, draws,
              schedule_draws, final, end_status, world_f, run_seconds, origin, applied,
              stop):  # fmt: skip
    from cells.models.assembly_lineages import keys as keys_rules
    from cells.models.assembly_lineages_v2 import geometry, ledger, lumen
    from cells.models.assembly_lineages_v2 import runner as single

    world = spec.model.world
    places = len(world.places)
    status = end_status or STATUS[int(final.status)]
    if world.hazard is not None and status == "inert" and state.alive.any():
        status = "complete"  # FR-31: a living vesicle's clock runs (pore_clock.py)
    codes = np.concatenate(events[0::2]) if events else np.zeros((0, 2), dtype=np.int64)
    values = np.concatenate(events[1::2]) if events else np.zeros((0, 5))
    count_change, supply_change = single.changes(layout, structure)
    R = structure.steps
    index = np.where(codes[:, 1] > 0, codes[:, 1] - 1, R + (-codes[:, 1] - 1)).astype(np.int64)
    horizon = spec.experiment.time_horizon_s
    end_time = horizon if status in ("complete", "inert") else float(final.time)
    # A resumed run (rung P) counts events from the world's start: k0 events came before it.
    resumed = origin["start"] != "fresh"
    k0 = origin["events"]
    t0 = float(origin["start"]["time"]) if resumed else 0.0
    marks = [(0, START, t0, -1)]
    every = spec.experiment.row_every_events
    marks += [
        (g - k0, PERIODIC, float(values[g - k0 - 1, 0]), -1)
        for g in range((k0 // every + 1) * every, k0 + len(codes) + 1, every)
    ]
    times = values[:, 0]
    for t in spec.experiment.observation_times_s:
        if t <= end_time and (t > t0 or not resumed):
            marks.append((int(np.searchsorted(times, t, side="right")), OBSERVED, t, -1))
    marks += [(n - k0, kind, t, i) for i, (n, kind, t, *_) in enumerate(ctx.stops)]
    marks.append((len(codes), END, end_time, len(ctx.stops)))
    # In event order, then time order: an observation at or after a stop with no event between
    # sees the stop's state; at one time, a stop before an observation (as the single lineage).
    order = {START: 0, PERIODIC: 1, SHEAR: 2, LYSIS: 2, TRANSFER: 2, REPLACEMENT: 2, WITHDRAWAL: 2,
             pore_clock.PORE_ROW: 2, OBSERVED: 3, END: 4}  # fmt: skip
    marks.sort(key=lambda x: (x[0], x[2], order[x[1]], x[3]))
    replay, e = start.copy(), 0
    extra = origin["extra"].copy() if resumed else np.zeros_like(ctx.extra)
    sums = origin["sums"] if resumed else np.zeros(4)  # the device's sums before any event
    rows = []
    diagnose = spec.experiment.diagnostic
    after_events = []  # (the changed vesicle's places, the pool's) after each event, when declared
    for n, kind, t, at in marks:
        while e < n:  # replay the events up to this row, in exact integers
            change = count_change[index[e]]
            replay.pool += np.where(m.place_vesicle, 0, change)
            if codes[e, 0] > 0:
                replay.slots[codes[e, 0] - 1] += np.where(m.place_vesicle, change, 0)
            replay.supplied += supply_change[index[e]]
            if diagnose:
                g = codes[e, 0]
                vesicle = replay.slots[g - 1] if g > 0 else np.zeros_like(replay.pool)
                after_events.append((vesicle[:places].copy(), replay.pool[:places].copy()))
            e += 1
        if kind in (SHEAR, LYSIS, TRANSFER, REPLACEMENT, WITHDRAWAL, pore_clock.PORE_ROW):
            replay, extra = ctx.stops[at][3].copy(), ctx.stops[at][4]
        device = values[n - 1, 1:] if n > 0 else sums
        rows.append((kind, n + k0, t, replay.copy(), device, extra.copy()))
    if not (np.array_equal(replay.pool, final.pool) and np.array_equal(replay.slots, final.slots)
            and np.array_equal(replay.supplied, final.supplied)):  # fmt: skip
        raise AssertionError(
            "The rows rebuilt from the events differ from the world's state: a fault"
        )
    f = np.asarray([world_f(r[3]) for r in rows])
    device = np.stack([r[4] for r in rows])
    extra = np.stack([r[5] for r in rows])
    columns = extra[:, EXTRA : EXTRA + len(ctx.columns)]
    heat = device[:, 0] + extra[:, E_HEAT]
    heat_mag = device[:, 1] + extra[:, E_HEAT_MAG]
    work = device[:, 2] + extra[:, E_WORK]
    booked = work + columns.sum(axis=1) - extra[:, E_SINK]
    booked_mag = device[:, 3] + extra[:, E_WORK_MAG] + extra[:, E_MAG]
    holds = extra[:, EXTRA + len(ctx.columns) :]  # FR-31: each hold's work column
    if ctx.holds:  # the holds' work is done on the vesicles (their payers')
        booked = booked + holds.sum(axis=1)
    if not np.allclose(columns.sum(axis=1), extra[:, E_SHEAR] + extra[:, E_TRANSFER],
                       rtol=1e-12, atol=1e-9):  # fmt: skip
        raise AssertionError(
            "The schedule columns differ from the shear, transfer, replacement and withdrawal "
            "totals"
        )
    f_0 = origin["f"] if resumed else f[0]  # the world's own initial F, before any cut
    residual = ledger.residual(heat, booked, f, f_0)
    tolerance = ledger.closure_tolerance(heat_mag, booked_mag, f, f_0)
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
    osmotic = world.conventions.lumen_volume == "osmotic"
    if osmotic:  # the lumen's volume and tension rows, as the single lineage records them
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
        "slot_key": np.stack([np.where(r[3].alive, r[3].keys, -1) for r in rows]),
        "reservoir_supplied": np.stack([r[3].supplied[:places] for r in rows]),
        "event_heat_kT": heat,
        "reservoir_work_kT": work,
        "free_energy_kT": f,
        "ledger_residual_kT": residual,
    }
    if world.geometry[0] != PRESCRIBED_SHELL:  # FR-21: a shell's wall has no quanta, so no W
        row_arrays["membrane_footprint_quanta"] = np.where(alive, slot_counts @ quanta[:places], 0)
    if osmotic:  # a declared lumen's volume is the world's constant, and it has no tension
        row_arrays |= {"lumen_volume_L": V, "tension_N_per_m": sigma}
    if ctx.columns:
        row_arrays |= {"schedule_work_kT": columns, "shear_work_kT": extra[:, E_SHEAR],
                       "discarded_free_energy_kT": extra[:, E_SINK]}  # fmt: skip
    if ctx.holds:  # FR-31
        row_arrays["tension_hold_work_kT"] = holds
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
    resume = None
    if status == "stopped":  # what a checkpoint keeps of the host (checkpoints.py)
        splits = int(sum(a.outcome == "split" for a, *_ in ctx.attempts))
        if resumed:
            splits += origin["splits"]
        resume = ctx.resume(state, applied, origin["f"], splits)
    for k in list(ctx.life_of):  # alive at the end: censored where observation stopped
        ctx.end(k, end_time, "censored")
    fissions = None
    if ctx.attempts:
        fissions = division.fission_arrays([(a, g) for a, g, _, _ in ctx.attempts], places,
                                           division.POPULATION_OUTCOMES)  # fmt: skip
        width = fissions["fission_daughters"].shape[1]
        fissions["fission_slot"] = np.asarray([s for _, _, s, _ in ctx.attempts], dtype=np.int64)
        fissions["fission_daughter_slots"] = np.asarray(
            [list(h) + [-1] * (width - len(h)) for _, _, _, h in ctx.attempts], dtype=np.int64
        ).reshape(len(ctx.attempts), width)
    report = {
        "slots": int(world.population["slots"]),
        "founders": len(world.population["founders"]),
        "lyses": ctx.lyses,
        "draws": int(len(all_draws)),
        "schedule_columns": ctx.columns,
        "lives": sorted(ctx.lives, key=lambda x: (x["birth_time"], x["key"])),
        "fissions": fissions,
        "schedule_draws": schedule_draws,
        "transfers": ctx.transfers,
        "reads": "one world-level SSA (cells.population.shared_pool@1); each lysis frees its slot, and the "
        "world goes on; every daughter lives",
    }
    if any(s.kind == "replacement" for s in spec.experiment.schedules):  # FR-20, when declared
        report["replacements"] = ctx.replacements
    withdraws = any(s.kind == "withdrawal" for s in spec.experiment.schedules)
    if withdraws:  # FR-35, when declared
        report["withdrawals"] = ctx.withdrawals
    if resumed:  # a run from a checkpoint: its start, and the world's numbering before it
        report["start"] = origin["start"]
        report["numbering"] = {"events": k0, "attempts": ctx.attempts_before,
                               "transfers": ctx.transfers_before,
                               "replacements": ctx.replacements_before}  # fmt: skip
        if withdraws:
            report["numbering"]["withdrawals"] = ctx.withdrawals_before
    timings = {"run_seconds": run_seconds, "events": int(len(codes)), "lanes": 1}
    pores = None
    if world.hazard is not None:  # FR-31: the clock's report (records.py's pores block)
        draws = (ctx.pore_draws if ctx.device_clock is None
                 else [v.draw() for v in ctx.pore_vesicles])  # OL6 S4: in draw order  # fmt: skip
        pores = {"events": ctx.pore_events, "draws": draws, "check": ctx.pore_check,
                 "causes": {"pore": len(ctx.pore_events), "threshold": len(ctx.lyses)}}  # fmt: skip
    record = None
    if diagnose:  # §0.2d item 10.5 (diagnostic.py)
        from cells.models.assembly_lineages_v2 import diagnostic
        from cells.models.assembly_lineages_v2.spec import world_id

        body, arrays = diagnostic.build_population(
            spec, layout, ctx, all_draws, committed, codes, values, after_events, status, start,
            replay, world_id(world), ended=status in ("complete", "inert", "stalled", "capacity")
            and not any(n - k0 == len(codes) and t >= horizon for n, k, t, *_ in ctx.stops),
            offsets=None if not resumed else {"events": k0, "counter": int(origin["counter"]),
                                              "heat": float(sums[0]), "work": float(sums[2])},
        )  # fmt: skip
        if pores is not None:  # FR-31: each draw that crossed a pore stop, the events, the draws
            fates = arrays["draw_fate"]
            spent = np.flatnonzero(~committed)  # one per applied stop, in order, then the end's
            for j, kind in enumerate(ctx.stop_kinds):
                if kind == "pore":
                    fates[spent[j]] = diagnostic.DISCARDED_AT_PORE
            body |= {"fates": list(diagnostic.PORE_FATES), "pore_events": pores["events"]}
            arrays |= pore_clock.draw_arrays(pores["draws"])
        record = {"body": body, "arrays": arrays}
    begun = {"checkpoint": origin["start"]["checkpoint"], "time": t0} if resumed else "fresh"
    halted = None if resume is None else {"events": stop, "fissions": resume["doc"]["splits"]}
    return single.WorldRun(
        spec=spec, structure=structure, verdict=verdict,
        world_report=ctx.world_report,
        status=status, rows=row_arrays, trace=trace, diagnostics=diagnostics, closure=closure,
        qualifier=keys_rules.qualifier(spec.fingerprint, begun, halted), final=final._asdict(),
        timings=timings, division=None, diagnostic=record, population=report,
        osmotic=single._osmotic_report(world, row_arrays["pool_count"], None)
        if world.conventions.lumen_volume == "osmotic" else None,
        start=origin["start"], resume=resume, pores=pores,
    )  # fmt: skip


def lives(run):
    """The lives as cells.relations' Life fields, in birth order (the run's own records)."""
    return run.population["lives"]
