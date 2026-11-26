"""The exact stochastic simulation of version 2: the direct method over general steps, in JAX.

One lane is one world: its assembly (the membrane and its lumen) and its pool. Lanes are vmapped,
so one compiled program advances any number of worlds that share a structure; a world's values
(its layout) are arguments, never closed over.

**Places and entries.** The state is the count of every place (a species in a phase: pool,
membrane, lumen), padded to the place capacity; a held pool place has no count (it stays 0) and
its net supply from the reservoir is booked instead. Each step is stored as K = 6 entries, its
distinct places with their reactant and product counts (α, β), padded with exact no-ops (place 0,
α = β = 0); so a step's arithmetic reads six places, whatever the world's size.

**Channels** (SSA_CONVENTION): 2R in declared order, the forward of each step 0 .. R−1, then the
reverse of each; padding steps have zero rates. A forward's rate is mass action's (mass_action.py)
at the state, times the rate factor on the pair's common state; a reverse's is the same law applied
to the products, with k⁻ = k_f exp(Σ ν μ°), the same factor, and exp(F_ex(n) − F_ex(n − ν)) for the
excess free-energy terms. So for every pair, ln a⁺ − ln a⁻ = −ΔF + w, which the kernel's check
verifies on random states (balance.py).

**The draw** is @1's convention exactly: the channels' partial totals by a serial left fold (D182);
two uniforms per event from the occupant's event stream (domain 1, @1's `exchange`) at counter = its
own event count; τ = −ln(u1)/a0; the first channel j with c_j > min(u2 a0, nextafter(a0, 0)). Rates
are recomputed in full at the new state after each event, and the event's heat is ln(the rate
drawn) − ln(its reverse's rate at the new state).

**The lifecycle.** A lane is RUNNING until:
- COMPLETE: the next event would fall after the time horizon (it is not committed; the state holds
  to the horizon);
- INERT: every rate is zero (nothing can happen: the state holds to the horizon);
- EXTINCT: under `last_molecule: extinct`, an event emptied the membrane (it has no reverse; its
  heat is −ΔF + w with F_mem(empty) = 0);
- EVENT_LIMIT: the event guard was reached;
- STALLED: the total rate was not finite (refused: nothing is repaired);
- CAPACITY: an event would take a count, or the membrane's size, past the molecule capacity (the
  log-factorial table): refused, the event not committed.
A lane that is not RUNNING changes nothing and draws nothing, so chunks and lane batches change no
value.
"""

import functools
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError
from cells.models.assembly_lineages import folds
from cells.models.assembly_lineages_v2 import PRESCRIBED_SHELL, mass_action, streams
from cells.models.assembly_lineages_v2 import world as world_rules
from cells.registry import laws as law_registry

RUNNING, COMPLETE, EXTINCT, EVENT_LIMIT, STALLED, INERT, CAPACITY, LYSED = range(8)
STATUS = ("running", "complete", "extinct", "event_limit", "stalled", "inert", "capacity",
          "lysed")  # fmt: skip
ENTRIES = 6  # K: distinct places per step (at most 3 reactant and 3 product molecules).
MEMBRANE = world_rules.PHASE_INDEX[world_rules.MEMBRANE]

SSA_CONVENTION = {
    "method": "direct method (Gillespie 1977), one step per event",
    "channels": "the forward of steps 0..R-1, then their reverses (R the step capacity; padding "
    "steps have zero rates, so the declared channel table lists the declared steps' channels in "
    "the same order and every partial total at them is the same)",
    "forward_rate": "mass action (cells.reaction.stochastic_mass_action@1) at the firing state n, times the "
    "rate factor on the pair's common state m = min(n, n + nu)",
    "reverse_rate": "the same law applied to the products, with k- = k_f exp(sum nu mu°), the same "
    "factor on m, and exp(F_ex(n) - F_ex(n - nu)) for the excess terms",
    "prefix": "serial left fold in channel order: c_0 = a_0, c_j = c_(j-1) + a_j; a0 = c_(2R-1)",
    "draw": "two uniforms per event, (u1, u2), from the occupant's event stream (domain 1) at "
    "counter = the occupant's event count since its birth",
    "uniform": streams.UNIFORM,
    "tau": "tau = -ln(u1) / a0",
    "channel": "the first j with c_j > min(u2 * a0, nextafter(a0, 0))",
    "after_event": "all rates recomputed at the new state; heat = ln(rate drawn) - ln(its "
    "reverse's rate at the new state); an event with no reverse (an extinction) books "
    "heat = -dF + w with F_mem(empty) = 0",
    "horizon": "an event whose time would pass the horizon is not committed: the state holds to "
    "the horizon",
    "tokens": {
        "tau": "neg_log_u1_over_a0",
        "select": "first_prefix_gt_u2_a0",
        "fold": "serial_left_fold_in_channel_order",
        "uniform": "open_interval_midpoints_of_2^52_bins_from_the_low_52_bits_of_a_threefry_word",
        "draws_per_event": 2,
    },
}

LIFECYCLE = {
    "statuses": {
        "running": "drawing events",
        "complete": "the next event would pass the time horizon: the state holds to it",
        "inert": "every rate is zero: the state holds to the horizon",
        "extinct": "last_molecule extinct: an event emptied the membrane (no reverse)",
        "event_limit": "the event guard (experiment.event_limit) was reached",
        "stalled": "the total rate was not finite: refused, nothing repaired",
        "capacity": "an event would pass the molecule capacity: refused, not committed",
    },
    "order": "before an event: stalled if the total is not finite, inert if it is zero, complete "
    "if the event would pass the horizon, capacity if it would pass the molecule capacity; after a "
    "committed event: extinct if it emptied the membrane under last_molecule extinct, else "
    "event_limit at the guard, else running",
}

# OL2 milestone 2's lifecycle, for a world with an osmotic lumen (OL1's text above is unchanged).
LIFECYCLE_OSMOTIC = {
    "statuses": {
        **LIFECYCLE["statuses"],
        "lysed": "an event's end state took the vesicle beyond sigma_max: the life ends lysed, "
        "its molecules return to their pool places and its closure cost is released",
    },
    "order": LIFECYCLE["order"] + "; after a committed event: lysed if its end state's tension "
    "is beyond sigma_max",
}


class Structure(NamedTuple):
    """Everything that selects a program: value-free and hashable (the compile key)."""

    places: int  # P, the place capacity.
    steps: int  # R, the step capacity.
    molecules: int  # The molecule capacity: the log-factorial table's last index.
    offset: int  # c, the condensed measure's offset.
    last_molecule: str
    reactions: tuple  # The steps' reaction laws' IDs, sorted (each step's index: step_law).
    factor: str | None  # The rate factor's law ID, or None.
    terms: tuple  # The excess free-energy terms' law IDs, in declared order.
    chunk: int
    unroll: int
    uniforms: bool  # Diagnostic: the draws are outputs too (the events are the same).
    geometry: str | None = None  # OL2: the geometry law's ID, or None (OL1's programs, unchanged).


class Layout(NamedTuple):
    """One world's values, bound as arguments (one lane's; the runner stacks lanes)."""

    entry_place: object  # [R, K] int32
    entry_alpha: object  # [R, K] int64: reactant counts
    entry_beta: object  # [R, K] int64: product counts
    entry_phase: object  # [R, K] int32
    entry_held: object  # [R, K] bool
    entry_log_X: object  # [R, K] float64: ln X of a dilute entry's phase, 0 elsewhere
    entry_log_activity: object  # [R, K] float64: ln(c/c0) of a held entry, 0 elsewhere
    entry_mu0: object  # [R, K] float64: μ°/RT of the entry's place (its phase kind)
    step_active: object  # [R] bool
    step_law: object  # [R] int32: the step's reaction law, an index into Structure.reactions
    kf: object  # [R] float64: k_f, multiplied after the exponential (an exact scale stays exact)
    log_ratio: object  # [R] float64: ln(k⁻/k_f) = Σ ν μ° (held places at their μ°_sol)
    locus_membrane: object  # [R] bool
    log_extent: object  # [R] float64: ln X of a dilute locus, 0 for the membrane
    step_work: object  # [R] float64: the forward's reservoir work, −Σ_held ν μ_held
    step_moves: object  # [R] int64: the forward's change of the membrane's count
    place_held: object  # [P] bool
    place_phase: object  # [P] int32
    log_factorial: object  # [M + 1] float64: ln k!
    factor: object  # The rate factor's layout, or ().
    terms: object  # The excess terms' layouts, in order.
    base_key: object  # uint32[2]
    horizon: object  # float64: the time horizon (s)
    event_limit: object  # int64: the event guard
    # OL2: () without a geometry (no leaf, so OL1's programs are unchanged), else GEOMETRY_FIELDS.
    geometry: object = ()


class Lane(NamedTuple):
    counts: object  # [P] int64
    totals: object  # [3] int64: each phase's count (finite places)
    time: object  # float64 (s): the last event's time
    events: object  # int64
    age: object  # int64: the occupant's events since its birth (its stream counter)
    occupant: object  # int64: carrier key (keys.py's rule)
    generation: object  # int64
    next_carrier: object  # int64
    fired: object  # [2R] int64, cumulative per channel
    supplied: object  # [P] int64: molecules taken from each held place's reservoir, net
    heat: object  # float64, k_BT, cumulative, non-monotone
    heat_magnitude: object  # float64: Σ |q|
    work: object  # float64, k_BT: reservoir work, cumulative, signed
    work_magnitude: object
    rates: object  # [2R] float64 at the current state
    factor_state: object  # The rate factor's state, or ()
    term_states: object  # The excess terms' states, in order
    event_stream: object  # uint32[2]
    status: object  # int32


class Event(NamedTuple):
    """One event step's outputs, per lane (committed or not)."""

    committed: object  # bool
    channel: object  # int32: +(r+1) the forward of step r, -(r+1) its reverse; 0 uncommitted
    time: object  # float64
    heat: object  # float64, cumulative after the event
    heat_magnitude: object
    work: object
    work_magnitude: object
    uniforms: object  # [2] float64, or () when not recorded


class View(NamedTuple):
    """What a law reads of one direction of every step at a state ([R, K] per entry)."""

    places: object  # [R, K] int32
    counts: object  # [R, K] int64: the entries' counts at the firing state
    coeff: object  # [R, K] int64: the direction's reactant counts
    other: object  # [R, K] int64: the direction's product counts
    membrane: object  # [R, K] bool: a finite membrane entry
    dilute: object  # [R, K] bool: a finite dilute entry
    held: object  # [R, K] bool
    log_X: object
    log_activity: object
    mu0: object
    consumed: object  # [R, K] int64: n − m, the direction's net consumption at finite entries
    membrane_total: object  # int64: N at the firing state
    log_factorial: object
    offset: int  # c (static)
    log_encounter: object = None  # OL2: [R] ln(E(m)·ρ0) of the geometric laws, or None.


class Tables(NamedTuple):
    """A world's host tables, per place, for the exact free energy (ledger.py, balance.py)."""

    mu0: object  # [P] float64
    log_X: object  # [P] float64: ln X of a dilute place, 0 elsewhere
    finite: object  # [P] bool: a declared place that holds a count
    membrane: object  # [P] bool: a finite membrane place
    log_factorial: object
    offset: int


def laws(structure):
    """(the rate factor law or None, the excess term laws), from the active law registry (a scoped
    registry included, so a planted law registered in a test's scope is the one used)."""
    registry = law_registry.active()
    factor = None if structure.factor is None else registry.lookup(structure.factor)
    return factor, tuple(registry.lookup(term) for term in structure.terms)


def reactions(structure):
    """The steps' reaction laws, in Structure.reactions' order (from the active registry)."""
    registry = law_registry.active()
    return tuple(registry.lookup(law_id) for law_id in structure.reactions)


def view(counts, totals, layout, offset, forward, xp):
    a, b = layout.entry_alpha, layout.entry_beta
    coeff, other = (a, b) if forward else (b, a)
    real = (a + b) > 0
    held = layout.entry_held & real
    membrane = (layout.entry_phase == MEMBRANE) & ~layout.entry_held & real
    dilute = (layout.entry_phase != MEMBRANE) & ~layout.entry_held & real
    consumed = xp.where(membrane | dilute, xp.maximum(coeff - other, 0), 0)
    return View(
        places=layout.entry_place,
        counts=counts[layout.entry_place],
        coeff=coeff,
        other=other,
        membrane=membrane,
        dilute=dilute,
        held=held,
        log_X=layout.entry_log_X,
        log_activity=layout.entry_log_activity,
        mu0=layout.entry_mu0,
        consumed=consumed,
        membrane_total=totals[MEMBRANE],
        log_factorial=layout.log_factorial,
        offset=offset,
    )


def log_parts(counts, totals, factor_state, term_states, layout, structure, xp=jnp):
    """ln (a / k_f) of all 2R channels at a state, in channel order (−inf: it cannot fire): the
    rate without its rate constant, which rates() multiplies after the exponential."""
    factor, terms = laws(structure)
    kinetics = reactions(structure)
    shell = structure.geometry == PRESCRIBED_SHELL  # FR-21: static, so other programs are as were
    bilayer = structure.geometry is not None and not shell
    footprint = footprint_of(counts, layout, xp) if bilayer else None
    out = []
    for forward in (True, False):
        v = view(counts, totals, layout, structure.offset, forward, xp)
        if shell:
            v = v._replace(log_encounter=shell_extent(layout, xp))
        elif structure.geometry is not None:
            v = v._replace(log_encounter=encounter_extent(footprint, layout, v, xp))
        log_a = xp.full(layout.step_law.shape, -xp.inf)
        for k, law in enumerate(kinetics):  # Each step's own law: one pass per law, selected.
            log_k = law.log_direction(
                v, layout.locus_membrane, layout.log_extent, structure.offset, xp
            )
            log_a = xp.where(layout.step_law == k, log_k, log_a)
        if not forward:  # k⁻ = k_f exp(Σ ν μ°).
            log_a = log_a + layout.log_ratio
        if factor is not None:
            log_a = log_a + factor.log_factor(factor_state, layout.factor, v, xp)
        if not forward:  # The reverse fires n -> n + (α − β).
            change = layout.entry_alpha - layout.entry_beta
            for term, state, term_layout in zip(terms, term_states, layout.terms, strict=True):
                log_a = log_a - term.delta(state, term_layout, v, change, xp)
        if bilayer:  # §0.2c rule 5: the vesicle floor, in quanta (a shell has none).
            moved = layout.geometry[2] if forward else -layout.geometry[2]
            log_a = xp.where(floor_zero(footprint, moved, layout.geometry[6]), -xp.inf, log_a)
        if structure.last_molecule == "kept":
            moves = layout.step_moves if forward else -layout.step_moves
            log_a = xp.where(kept_zero(totals[MEMBRANE], moves), -xp.inf, log_a)
        out.append(xp.where(layout.step_active, log_a, -xp.inf))
    return xp.concatenate(out)


# OL2's geometry layout (model.layout; geometry.py): the order of Layout.geometry's arrays.
GEOMETRY_FIELDS = (
    "place_quanta",  # [P] int64: k_i at a finite membrane place, 0 elsewhere
    "entry_quanta",  # [R, K] int64: the entry's place's k
    "step_quanta",  # [R] int64: the forward's change of W
    "step_encounter",  # [R] int32: 0 none (OL1's extent), 1 an area, 2 a radius
    "log_area",  # float64: c_area, ln(A ρ0) = c_area + ln W
    "log_radius",  # float64: c_radius, ln(4πR ρ0) = c_radius + ½ ln W
    "floor_quanta",  # int64: W_floor
    "lumen_mask",  # [P] int64: 1 at a finite lumen place (OL2 milestone 2)
    "lumen_constants",  # [4] float64: lumen.constants (zeros without an osmotic lumen)
    "sigma_max",  # float64: the lysis tension (N/m); +inf without an osmotic lumen
    "kT_J",  # float64: k_BT in joules
    "area_quantum_m2",  # float64: q
)


def footprint_of(counts, layout, xp=jnp):
    """W(n) = Σ_p n_p k_p quanta, an exact integer (§0.2c rule 4)."""
    return xp.sum(counts * layout.geometry[0])


def encounter_extent(footprint, layout, view, xp=jnp):
    """ln(E(m)·ρ0) of each step's geometric encounter on its common state m (§0.2d item 2), from
    the exact integer W(m) = W(n) − Σ_e k_e (n_e − m_e), so both directions of a pair compute the
    same value; −inf where W(m) = 0, and 0 for a step without a geometric encounter."""
    consumed = xp.where(view.membrane, view.consumed, 0)
    w_m = footprint - mass_action.entry_sum(layout.geometry[1] * consumed, xp)
    log_w = mass_action.safe_log(w_m.astype(np.float64), xp)
    code = layout.geometry[3]
    area = layout.geometry[4] + log_w
    radius = layout.geometry[5] + 0.5 * log_w
    return xp.where(code == 1, area, xp.where(code == 2, radius, 0.0))


def shell_extent(layout, xp=jnp):
    """FR-21: ln(A_sh·ρ0) for each cells.reaction.shell_permeation@1 step (code 3), 0 for any other: a
    constant of the world, the same on every state and in both directions."""
    return xp.where(layout.geometry[3] == 3, layout.geometry[4], 0.0)


def lysis_at(counts, layout, xp=jnp):
    """Whether a state's tension is beyond sigma_max (§0.2b rule 3): never without an osmotic
    lumen, whose sigma_max is +inf."""
    from cells.models.assembly_lineages_v2 import lumen as lumen_rules

    g = layout.geometry
    n_lumen = xp.sum(counts * g[7])
    sigma = lumen_rules.tension(n_lumen, footprint_of(counts, layout, xp), g[10], g[11], g[8], xp)
    return sigma > g[9]


def floor_zero(footprint, moved, floor):
    """The pairs §0.2c rule 5 gives rate zero: the step changes W (moved ≠ 0, the direction's
    change) and the firing state or the result is below the floor. A step that keeps W fires."""
    return (moved != 0) & ((footprint < floor) | (footprint + moved < floor))


def kept_zero(total, moves):
    """The channels `last_molecule: kept` gives rate zero (§0.2a, as worded 18 November 2026):
    those of a pair whose step changes the membrane's count (moves ≠ 0, the direction's change)
    and one of whose end states, the firing state (total) or the result (total + moves), has an
    empty membrane. So the membrane never empties, and a step that leaves the membrane's count
    alone fires at its own rate: a pool step at a state with an empty membrane fires at the pool's
    mass action."""
    return (moves != 0) & ((total == 0) | (total + moves == 0))


def rates(counts, totals, factor_state, term_states, layout, structure, xp=jnp):
    """All 2R rates at a state, in channel order (1/s): k_f exp(ln(a / k_f)), so a rate constant
    scaled by a power of two scales every rate exactly (the rescale pair's bitwise claim)."""
    parts = log_parts(counts, totals, factor_state, term_states, layout, structure, xp)
    return xp.concatenate((layout.kf, layout.kf)) * xp.exp(parts)


def log_rates(counts, totals, factor_state, term_states, layout, structure, xp=jnp):
    """ln a of all 2R channels at a state (−inf: the channel cannot fire)."""
    parts = log_parts(counts, totals, factor_state, term_states, layout, structure, xp)
    return mass_action.safe_log(xp.concatenate((layout.kf, layout.kf)), xp) + parts


def totals_of(counts, layout, xp=jnp):
    """Each phase's count over its finite places."""
    finite = xp.where(layout.place_held, 0, counts)
    return (
        xp.zeros(3, dtype=counts.dtype).at[layout.place_phase].add(finite)
        if xp is jnp
        else (
            np.bincount(
                np.asarray(layout.place_phase), weights=np.asarray(finite), minlength=3
            ).astype(np.int64)
        )
    )


def states(counts, totals, layout, structure, xp=jnp):
    """(the rate factor's state, the excess terms' states), exactly at a state."""
    factor, terms = laws(structure)
    factor_state = () if factor is None else factor.state(counts, layout.factor, xp)
    term_states = tuple(
        term.state(counts, totals, term_layout, xp)
        for term, term_layout in zip(terms, layout.terms, strict=True)
    )
    return factor_state, term_states


def boundary_heat(lane, layout, structure, step, change, work):
    """−ΔF + w of an event that has no reverse (an extinction): F_mem(empty) = 0."""
    from cells.models.assembly_lineages_v2 import ideal_mixing

    factor, terms = laws(structure)
    del factor
    one = jax.tree_util.tree_map(lambda a: a[step][None], _per_step(layout))
    v = view(lane.counts, lane.totals, layout._replace(**one), structure.offset, True, jnp)
    d = change[None, :]
    delta = ideal_mixing.delta((), (), v, d, jnp)[0]
    for term, state, term_layout in zip(terms, lane.term_states, layout.terms, strict=True):
        delta = delta + term.delta(state, term_layout, v, d, jnp)[0]
    return -delta + work


def _per_step(layout):
    names = (
        "entry_place",
        "entry_alpha",
        "entry_beta",
        "entry_phase",
        "entry_held",
        "entry_log_X",
        "entry_log_activity",
        "entry_mu0",
    )
    return {name: getattr(layout, name) for name in names}


def _select(flag, new, old):
    return jax.tree_util.tree_map(lambda a, b: jnp.where(flag, a, b), new, old)


def initial(founder, layout, structure):
    """A lane at its founder: carrier 0, generation 0, nothing booked."""
    counts = founder.astype(jnp.int64)
    totals = totals_of(counts, layout)
    factor_state, term_states = states(counts, totals, layout, structure)
    zero = jnp.float64(0.0)
    return Lane(
        counts=counts,
        totals=totals,
        time=zero,
        events=jnp.int64(0),
        age=jnp.int64(0),
        occupant=jnp.int64(0),
        generation=jnp.int64(0),
        next_carrier=jnp.int64(1),
        fired=jnp.zeros(2 * structure.steps, dtype=jnp.int64),
        supplied=jnp.zeros_like(counts),
        heat=zero,
        heat_magnitude=zero,
        work=zero,
        work_magnitude=zero,
        rates=rates(counts, totals, factor_state, term_states, layout, structure),
        factor_state=factor_state,
        term_states=term_states,
        event_stream=streams.stream_key_data(layout.base_key, jnp.int64(0), "events"),
        status=jnp.int32(RUNNING),
    )


def event(lane, layout, structure):
    """One event of one lane (the direct method; module docstring)."""
    factor, terms = laws(structure)
    R = structure.steps
    running = lane.status == RUNNING
    prefix = folds.prefix(lane.rates, jnp, structure.unroll)
    total = prefix[-1]
    draw = streams.uniforms(lane.event_stream, lane.age, 2)
    wait = -jnp.log(draw[0]) / jnp.where(total > 0, total, 1.0)
    threshold = jnp.minimum(draw[1] * total, jnp.nextafter(total, 0.0))
    channel = jnp.argmax(prefix > threshold)
    finite = jnp.isfinite(total) & jnp.isfinite(wait)
    usable = finite & (total > 0) & (wait > 0)
    in_time = lane.time + wait <= layout.horizon
    step = channel % R
    forward = channel < R
    places = layout.entry_place[step]
    alpha, beta = layout.entry_alpha[step], layout.entry_beta[step]
    change = jnp.where(forward, beta - alpha, alpha - beta)
    held = layout.entry_held[step]
    moved = jnp.where(held, 0, change)
    counts = lane.counts.at[places].add(moved)
    totals = lane.totals.at[layout.entry_phase[step]].add(moved)
    supplied = lane.supplied.at[places].add(jnp.where(held, -change, 0))
    fits = (jnp.max(counts) <= structure.molecules) & (totals[MEMBRANE] <= structure.molecules)
    factor_state = lane.factor_state
    if factor is not None:
        factor_state = factor.update(factor_state, layout.factor, places, moved, jnp)
    term_states = tuple(
        term.update(state, term_layout, places, moved, jnp)
        for term, state, term_layout in zip(terms, lane.term_states, layout.terms, strict=True)
    )
    new_rates = rates(counts, totals, factor_state, term_states, layout, structure)
    reverse = jnp.where(forward, channel + R, channel - R)
    work = jnp.where(forward, layout.step_work[step], -layout.step_work[step])
    back = new_rates[reverse]
    emptied = (totals[MEMBRANE] == 0) & (lane.totals[MEMBRANE] > 0)
    extinction = emptied & (structure.last_molecule == "extinct")
    heat = jnp.where(
        back > 0,
        jnp.log(lane.rates[channel]) - jnp.log(jnp.where(back > 0, back, 1.0)),
        boundary_heat(lane, layout, structure, step, change, work)
        if structure.last_molecule == "extinct"
        else jnp.nan,  # Otherwise a committed event always has a reverse: nan would be a fault.
    )
    events = lane.events + 1
    status = jnp.where(
        extinction, EXTINCT, jnp.where(events >= layout.event_limit, EVENT_LIMIT, RUNNING)
    ).astype(jnp.int32)
    if structure.geometry not in (None, PRESCRIBED_SHELL):  # lysis at the end state (§0.2b rule 3)
        status = jnp.where(lysis_at(counts, layout), LYSED, status).astype(jnp.int32)
    after = lane._replace(
        counts=counts,
        totals=totals,
        time=lane.time + wait,
        events=events,
        age=lane.age + 1,
        fired=lane.fired.at[channel].add(1),
        supplied=supplied,
        heat=lane.heat + heat,
        heat_magnitude=lane.heat_magnitude + jnp.abs(heat),
        work=lane.work + work,
        work_magnitude=lane.work_magnitude + jnp.abs(work),
        rates=new_rates,
        factor_state=factor_state,
        term_states=term_states,
        status=status,
    )
    commit = running & usable & in_time & fits
    halted = jnp.where(
        ~finite,
        STALLED,
        jnp.where(total == 0, INERT, jnp.where(~in_time, COMPLETE, CAPACITY)),
    ).astype(jnp.int32)
    stopped = lane._replace(status=halted)
    lane = _select(commit, after, _select(running, stopped, lane))
    signed = jnp.where(forward, step + 1, -(step + 1)).astype(jnp.int32)
    recorded = draw if structure.uniforms else ()
    return lane, Event(
        commit,
        jnp.where(commit, signed, 0),
        lane.time,
        lane.heat,
        lane.heat_magnitude,
        lane.work,
        lane.work_magnitude,
        recorded,
    )


class Program(NamedTuple):
    initial: object
    advance: object


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
    )


def channel_table(world):
    """The declared channels in the kernel's order, with their codes (the trace's event_channel):
    row r is the forward of step r (code +(r+1)), row R + r its reverse (code −(r+1))."""
    rows = []
    count = len(world.steps)
    for direction, sign in (("forward", 1), ("reverse", -1)):
        for r, step in enumerate(world.steps):
            reactants, products = (
                (step.reactants, step.products) if sign > 0 else (step.products, step.reactants)
            )
            rows.append(
                {
                    "row": len(rows),
                    "step": step.id,
                    "step_index": r,
                    "direction": direction,
                    "event_channel": sign * (r + 1),
                    "reactants": dict(reactants),
                    "products": dict(products),
                    "locus": step.locus,
                    "law": step.law,
                }
            )
    return {
        "order": "the forward of each declared step in order, then their reverses; the kernel "
        "folds its partial totals in this order (padding channels of the capacity add exact "
        "zeros)",
        "event_channel": f"+(r+1) is row r, the forward of step r; -(r+1) is row {count} + r, its "
        "reverse",
        "rows": rows,
    }


def refuse_unknown(structure):
    """Every law a structure names resolves in the active registry (ConfigError otherwise)."""
    try:
        laws(structure)
        reactions(structure)
    except KeyError as error:
        raise ConfigError(str(error)) from error
