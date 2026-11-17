"""The exact stochastic simulation of assembly lineages: the direct method in JAX, over lanes.

One lane is one world's lineage: one continuing assembly (single-lineage mode). Lanes are vmapped,
so one compiled program advances any number of worlds that share a structure; a world's values
(its layout) are arguments, never closed over, so one program serves every matrix and supply.

The direct method (Gillespie 1977), one molecule per event. The convention a run declares
(SSA_CONVENTION):
- Channels, 2C in declared order: the joins of types 0 .. C-1, then their leaves (C is the type
  capacity; padding types have zero rates). Join i: (kf_i rho_i N) g_join_i; leave i:
  (kb_i n_i) g_leave_i, with g = 1 without a rate-factor law (exchange.py, factors.py).
- Their total a0 and partial totals c_j: a serial left fold in channel order (folds.py, D182).
- Two uniforms per event from the occupant's exchange stream at counter = its own event count
  (streams.py): u1 sets the waiting time tau = -ln(u1) / a0; u2 picks the first channel j with
  c_j > min(u2 a0, nextafter(a0, 0)).
- The rates are recomputed in full after each event, at the new state; the selected channel's
  rate and the reverse channel's new rate give the event's heat (ledger.py).

The lifecycle. A join that brings the size to the fission size marks the lane FISSION_DUE; the
lane then waits, drawing nothing, until the fission pass (fission.py, continuation.py) replaces
its occupant with the followed daughter. A lineage ends COMPLETE after its last fission, EXTINCT
when its assembly empties (its last molecule leaves, or an empty daughter is followed under the
`extinct` rule), EVENT_LIMIT when one growth reaches the event guard, or STALLED if its total
rate is not a finite positive number (a refusal: nothing is repaired). A lane that is not
RUNNING changes nothing and draws nothing, so chunk boundaries and lane batches change no value.

The rate-factor law's incremental state (GARD: x = beta n) is updated by one column per event
and recomputed exactly whenever the composition is replaced (the founder, each daughter).
"""

import functools
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.models.assembly_lineages import (
    continuation,
    exchange,
    factors,
    fission,
    folds,
    ledger,
    streams,
)

RUNNING, FISSION_DUE, COMPLETE, EXTINCT, EVENT_LIMIT, STALLED = range(6)
STATUS = ("running", "fission_due", "complete", "extinct", "event_limit", "stalled")

SSA_CONVENTION = {
    "method": "direct method (Gillespie 1977), one molecule per event",
    "channels": "joins of types 0..C-1, then leaves of types 0..C-1 (C the type capacity; "
    "padding types have zero rates, so the declared table, channel_table, lists the declared "
    "types' channels in the same order and every partial total at them is the same)",
    "join_rate": "(kf_i * rho_i * N) * g_join_i",
    "leave_rate": "(kb_i * n_i) * g_leave_i",
    "prefix": "serial left fold in channel order: c_0 = a_0, c_j = c_(j-1) + a_j; a0 = c_(2C-1)",
    "draw": "two uniforms per event, (u1, u2), from the occupant's exchange stream at counter = "
    "the occupant's event count since its birth",
    "tau": "tau = -ln(u1) / a0",
    "channel": "the first j with c_j > min(u2 * a0, nextafter(a0, 0))",
    "after_event": "all rates recomputed at the new state; heat = ln(rate drawn) - ln(the "
    "reverse channel's rate at the new state)",
}


LIFECYCLE = {
    "statuses": {
        "running": "drawing events",
        "fission_due": "a join reached the fission size, or a daughter was born at it (a "
        "binomial partition can give one daughter every molecule); the fission pass replaces the "
        "occupant",
        "complete": "the lineage made its last fission (experiment.fissions)",
        "extinct": "the assembly emptied: its last molecule left, or an empty daughter was "
        "followed under the continuation's `extinct` rule",
        "event_limit": "one growth reached experiment.growth_event_limit events without a "
        "fission: the lineage stops (no forced fission)",
        "stalled": "the total rate was not a finite positive number: refused, nothing repaired",
    },
    "order": "after each committed event: fission_due if a join reached the fission size, else "
    "extinct if the assembly is empty, else event_limit if the occupant's events since its birth "
    "reached the guard, else running",
}


class Structure(NamedTuple):
    """Everything that selects a program: value-free and hashable (the compile key)."""

    capacity: int
    molecule_capacity: int
    factor: str | None
    partition: str
    daughter: str
    empty: str
    chunk: int
    unroll: int
    uniforms: bool  # Diagnostic: the draws are outputs too (the events are the same).


class Layout(NamedTuple):
    """One world's values, bound as arguments (one lane's; the runner stacks lanes)."""

    kf_rho: object  # [C] kf_i rho_i, 0 for padding.
    kb: object  # [C] kb_i, 0 for padding.
    log_theta: object  # [C] ln(K_i rho_i), 0 for padding (no molecule of it ever exists).
    log_factorial: object  # [M + 1] ln k!.
    split_size: object  # int64: the fission size.
    split_value: object  # float64: the partition's fraction or probability.
    fission_limit: object  # int64: fissions to run.
    growth_limit: object  # int64: the event guard of one growth.
    base_key: object  # uint32[2]: the world's base key (streams.py).
    factor: object  # The rate-factor law's layout, or ().


class Lane(NamedTuple):
    counts: object  # [C] int64
    size: object  # int64
    time: object  # float64, nominal
    events: object  # int64: the lineage's events
    age: object  # int64: the occupant's events since its birth (its exchange counter)
    occupant: object  # int64: carrier key
    generation: object  # int64
    next_carrier: object  # int64
    fissions: object  # int64
    joined: object  # [C] int64, cumulative
    left: object  # [C] int64, cumulative
    discarded: object  # [C] int64, cumulative
    heat: object  # float64, k_BT, cumulative, non-monotone
    heat_magnitude: object  # float64: sum of |q|, for the closure's tolerance
    work: object  # float64, k_BT, cumulative, signed
    work_magnitude: object
    sink: object  # float64, k_BT, cumulative
    sink_magnitude: object
    rates: object  # [2C] float64 at the current state
    factor_state: object  # The rate-factor law's state, or ()
    exchange_stream: object  # uint32[2]: the occupant's exchange stream
    status: object  # int32


class Row(NamedTuple):
    """A saved row of the lineage: the lane's state, without its working arrays."""

    time: object
    events: object
    age: object
    counts: object
    size: object
    joined: object
    left: object
    discarded: object
    heat: object
    heat_magnitude: object
    work: object
    work_magnitude: object
    sink: object
    sink_magnitude: object
    occupant: object
    generation: object
    fissions: object
    status: object


class Step(NamedTuple):
    """One event step's outputs, per lane (committed or not)."""

    committed: object  # bool
    channel: object  # int32: +(i+1) a join of type i, -(i+1) a leave
    time: object  # float64: the event's time
    uniforms: object  # [2] float64, or () when not recorded


class Split(NamedTuple):
    """One fission pass's outputs, per lane (fired or not)."""

    fired: object
    parent: object  # carrier key
    daughters: object  # [2] carrier keys
    followed: object  # 0 or 1
    first: object  # [C] the first daughter's counts
    similarity: object  # [2] cosine of the parent with each daughter (NaN for an empty one)
    before: object  # Row: the parent, at the fission's time
    after: object  # Row: the followed daughter
    places: object  # [M] the partition's uniforms, or ()
    choice: object  # the continuation's uniform, or ()


def channel_table(type_ids, held="held phase"):
    """The declared channels in the kernel's order (R1, the lead's ruling of 17 November 2026):
    row i joins type i, row N + i takes it out, for the N declared types. The trace's
    event_channel is signed: +(i+1) is row i and -(i+1) is row N + i."""
    count = len(type_ids)
    rows = []
    for kind, sign in (("join", 1), ("leave", -1)):
        for i, name in enumerate(type_ids):
            rows.append(
                {
                    "row": len(rows),
                    "kind": kind,
                    "type": name,
                    "type_index": i,
                    "event_channel": sign * (i + 1),
                    "stoichiometry": {"assembly": {name: sign}, held: {name: -sign}},
                    "rate": SSA_CONVENTION[f"{kind}_rate"].replace("_i", f"_{i}"),
                }
            )
    return {
        "order": "joins of the declared types in order, then their leaves; the kernel folds its "
        "partial totals in this order (padding channels of the capacity add exact zeros)",
        "event_channel": f"+(i+1) is row i, the join of type i; -(i+1) is row {count} + i, its "
        "leave",
        "rows": rows,
    }


def rate_factor(structure):
    return None if structure.factor is None else factors.resolve(structure.factor)


def rates(counts, size, layout, factor_state, law, xp=jnp):
    """All 2C rates at a state (exchange times the rate factor), in channel order."""
    n = counts.astype(np.float64)
    total = size.astype(np.float64) if hasattr(size, "astype") else np.float64(size)
    join, leave = exchange.base_rates(n, total, layout.kf_rho, layout.kb)
    if law is not None:
        g_join, g_leave = law.factors(n, total, factor_state, layout.factor, xp)
        join, leave = join * g_join, leave * g_leave
    return xp.concatenate((join, leave))


def factor_state(counts, layout, law, unroll):
    if law is None:
        return ()
    return law.state(counts.astype(jnp.float64), layout.factor, jnp, unroll)


def row(lane):
    return Row(
        lane.time,
        lane.events,
        lane.age,
        lane.counts,
        lane.size,
        lane.joined,
        lane.left,
        lane.discarded,
        lane.heat,
        lane.heat_magnitude,
        lane.work,
        lane.work_magnitude,
        lane.sink,
        lane.sink_magnitude,
        lane.occupant,
        lane.generation,
        lane.fissions,
        lane.status,
    )


def _select(flag, new, old):
    return jax.tree_util.tree_map(lambda a, b: jnp.where(flag, a, b), new, old)


def initial(founder, layout, structure):
    """A lane at its founder: carrier 0, generation 0, nothing booked."""
    law = rate_factor(structure)
    counts = founder.astype(jnp.int64)
    size = jnp.sum(counts)
    state = factor_state(counts, layout, law, structure.unroll)
    zero_c = jnp.zeros_like(counts)
    zero = jnp.float64(0.0)
    status = jnp.where(size > 0, RUNNING, EXTINCT).astype(jnp.int32)
    return Lane(
        counts=counts,
        size=size,
        time=zero,
        events=jnp.int64(0),
        age=jnp.int64(0),
        occupant=jnp.int64(0),
        generation=jnp.int64(0),
        next_carrier=jnp.int64(1),
        fissions=jnp.int64(0),
        joined=zero_c,
        left=zero_c,
        discarded=zero_c,
        heat=zero,
        heat_magnitude=zero,
        work=zero,
        work_magnitude=zero,
        sink=zero,
        sink_magnitude=zero,
        rates=rates(counts, size, layout, state, law),
        factor_state=state,
        exchange_stream=streams.stream_key_data(layout.base_key, jnp.int64(0), "exchange"),
        status=status,
    )


def event(lane, layout, structure):
    """One event of one lane (the direct method; module docstring)."""
    law = rate_factor(structure)
    capacity = structure.capacity
    running = lane.status == RUNNING
    prefix = folds.prefix(lane.rates, jnp, structure.unroll)
    total = prefix[-1]
    draw = streams.uniforms(lane.exchange_stream, lane.age, 2)
    wait = -jnp.log(draw[0]) / jnp.where(total > 0, total, 1.0)
    threshold = jnp.minimum(draw[1] * total, jnp.nextafter(total, 0.0))
    channel = jnp.argmax(prefix > threshold)
    usable = (total > 0) & jnp.isfinite(total) & jnp.isfinite(wait) & (wait > 0)
    commit = running & usable
    kind = channel % capacity
    join = channel < capacity
    sign = jnp.where(join, 1, -1).astype(jnp.int64)
    counts = lane.counts.at[kind].add(sign)
    size = lane.size + sign
    state = lane.factor_state
    if law is not None:
        state = law.update(state, layout.factor, kind, sign.astype(jnp.float64), jnp)
    new_rates = rates(counts, size, layout, state, law)
    reverse = jnp.where(join, capacity + kind, kind)
    heat = jnp.where(
        size > 0,
        jnp.log(lane.rates[channel]) - jnp.log(jnp.where(size > 0, new_rates[reverse], 1.0)),
        -layout.log_theta[kind],  # The last molecule's leave: Phi(empty) = 0 (ledger.py).
    )
    age = lane.age + 1
    status = jnp.where(
        join & (size == layout.split_size),
        FISSION_DUE,
        jnp.where(size == 0, EXTINCT, jnp.where(age >= layout.growth_limit, EVENT_LIMIT, RUNNING)),
    ).astype(jnp.int32)
    one = jnp.zeros_like(lane.counts).at[kind].set(1)
    moved = lane._replace(
        counts=counts,
        size=size,
        time=lane.time + wait,
        events=lane.events + 1,
        age=age,
        joined=lane.joined + jnp.where(join, one, 0),
        left=lane.left + jnp.where(join, 0, one),
        heat=lane.heat + heat,
        heat_magnitude=lane.heat_magnitude + jnp.abs(heat),
        rates=new_rates,
        factor_state=state,
        status=status,
    )
    stalled = lane._replace(status=jnp.int32(STALLED))
    lane = _select(commit, moved, _select(running, stalled, lane))
    signed = jnp.where(join, kind + 1, -(kind + 1)).astype(jnp.int32)
    recorded = draw if structure.uniforms else ()
    return lane, Step(commit, jnp.where(commit, signed, 0), lane.time, recorded)


def cosine(parent, daughter):
    """H(P, D): integer dot products (exact in any order), then a correctly rounded square root
    and division. The barrier keeps XLA from rewriting x / sqrt(y) as x * rsqrt(y), which is not
    correctly rounded, so H is the host's value bit for bit."""
    dot = jnp.sum(parent * daughter)
    norms = jnp.sum(parent * parent).astype(jnp.float64) * jnp.sum(daughter * daughter)
    root = jax.lax.optimization_barrier(jnp.sqrt(norms))
    return jnp.where(norms > 0, dot.astype(jnp.float64) / root, jnp.nan)


def split(lane, layout, structure):
    """The fission pass of one lane: a no-op unless the lane is FISSION_DUE."""
    law = rate_factor(structure)
    due = lane.status == FISSION_DUE
    parent, size = lane.counts, lane.size
    partition_stream = streams.stream_key_data(layout.base_key, lane.occupant, "partition")
    places = streams.uniforms(partition_stream, jnp.int64(0), structure.molecule_capacity)
    first = fission.split(parent, size, places, structure.partition, layout.split_value)
    second = parent - first
    sizes = (jnp.sum(first), jnp.sum(second))
    choice_stream = streams.stream_key_data(layout.base_key, lane.occupant, "continuation")
    choice = streams.uniforms(choice_stream, jnp.int64(0), 1)[0]
    followed = continuation.choose(structure.daughter, structure.empty, choice, sizes)
    keep = jnp.where(followed == 0, first, second)
    drop = parent - keep
    keep_size = jnp.where(followed == 0, sizes[0], sizes[1])

    def phi(counts, n):
        return ledger.log_weight(counts, n, layout.log_theta, layout.log_factorial, jnp)

    phi_parent, phi_first, phi_second = (
        phi(parent, size),
        phi(first, sizes[0]),
        phi(second, sizes[1]),
    )
    work = phi_parent - phi_first - phi_second
    sink = -jnp.where(followed == 0, phi_second, phi_first)
    daughters = jnp.stack((lane.next_carrier, lane.next_carrier + 1))
    occupant = daughters[followed]
    fissions = lane.fissions + 1
    state = factor_state(keep, layout, law, structure.unroll)
    after = lane._replace(
        counts=keep,
        size=keep_size,
        age=jnp.int64(0),
        occupant=occupant,
        generation=lane.generation + 1,
        next_carrier=lane.next_carrier + 2,
        fissions=fissions,
        discarded=lane.discarded + drop,
        work=lane.work + work,
        work_magnitude=lane.work_magnitude + jnp.abs(work),
        sink=lane.sink + sink,
        sink_magnitude=lane.sink_magnitude + jnp.abs(sink),
        rates=rates(keep, keep_size, layout, state, law),
        factor_state=state,
        exchange_stream=streams.stream_key_data(layout.base_key, occupant, "exchange"),
        status=jnp.where(
            keep_size == 0,
            EXTINCT,
            jnp.where(
                fissions >= layout.fission_limit,
                COMPLETE,
                jnp.where(keep_size >= layout.split_size, FISSION_DUE, RUNNING),
            ),
        ).astype(jnp.int32),
    )
    result = _select(due, after, lane)
    record = Split(
        fired=due,
        parent=lane.occupant,
        daughters=daughters,
        followed=followed,
        first=first,
        similarity=jnp.stack((cosine(parent, first), cosine(parent, second))),
        before=row(lane),
        after=row(result),
        places=places if structure.uniforms else (),
        choice=choice if structure.uniforms else (),
    )
    return result, record


def sibling(lane, layout, structure, first, followed):
    """Every-descendant mode: the other daughter of the fission that the pass has just made, as a
    lane at its birth (a no-op unless `lane` is FISSION_DUE).

    `lane` is the parent before the split; `first` and `followed` are the fission pass's record
    (split). The followed daughter's lane is the fission pass's own, so the followed path is the
    single lineage's, bitwise. This lane exchanges the daughters' roles: it keeps the other
    daughter, books the followed daughter's material and free energy as leaving its path (the
    same ledger terms, with the roles exchanged), and takes the other key. Its sub-lineage counter
    (next_carrier) is the host's to assign once its generation has ended (keys.py); it is -1 here.
    The program is separate from the fission pass, which it leaves untouched."""
    law = rate_factor(structure)
    due = lane.status == FISSION_DUE
    parent, size = lane.counts, lane.size
    second = parent - first
    sizes = (jnp.sum(first), jnp.sum(second))
    other = 1 - followed
    keep = jnp.where(other == 0, first, second)
    drop = parent - keep
    keep_size = jnp.where(other == 0, sizes[0], sizes[1])

    def phi(counts, n):
        return ledger.log_weight(counts, n, layout.log_theta, layout.log_factorial, jnp)

    phi_parent, phi_first, phi_second = (
        phi(parent, size),
        phi(first, sizes[0]),
        phi(second, sizes[1]),
    )
    work = phi_parent - phi_first - phi_second
    sink = -jnp.where(other == 0, phi_second, phi_first)
    daughters = jnp.stack((lane.next_carrier, lane.next_carrier + 1))
    occupant = daughters[other]
    fissions = lane.fissions + 1
    state = factor_state(keep, layout, law, structure.unroll)
    born = lane._replace(
        counts=keep,
        size=keep_size,
        age=jnp.int64(0),
        occupant=occupant,
        generation=lane.generation + 1,
        next_carrier=jnp.int64(-1),
        fissions=fissions,
        discarded=lane.discarded + drop,
        work=lane.work + work,
        work_magnitude=lane.work_magnitude + jnp.abs(work),
        sink=lane.sink + sink,
        sink_magnitude=lane.sink_magnitude + jnp.abs(sink),
        rates=rates(keep, keep_size, layout, state, law),
        factor_state=state,
        exchange_stream=streams.stream_key_data(layout.base_key, occupant, "exchange"),
        status=jnp.where(
            keep_size == 0,
            EXTINCT,
            jnp.where(
                fissions >= layout.fission_limit,
                COMPLETE,
                jnp.where(keep_size >= layout.split_size, FISSION_DUE, RUNNING),
            ),
        ).astype(jnp.int32),
    )
    return _select(due, born, lane)


@functools.cache
def sibling_program(structure):
    """The compiled sibling pass of one structure (every-descendant mode), cached per structure."""
    return jax.jit(jax.vmap(lambda la, lo, f, k: sibling(la, lo, structure, f, k)))


class Program(NamedTuple):
    initial: object
    advance: object
    split: object


@functools.cache
def program(structure):
    """The compiled program of one structure, for any number of lanes (cached per structure)."""

    def advance(lanes, layout):
        def body(current, _):
            return jax.vmap(lambda la, lo: event(la, lo, structure))(current, layout)

        return jax.lax.scan(body, lanes, None, length=structure.chunk)

    return Program(
        initial=jax.jit(jax.vmap(lambda f, lo: initial(f, lo, structure))),
        advance=jax.jit(advance),
        split=jax.jit(jax.vmap(lambda la, lo: split(la, lo, structure))),
    )
