"""FR-31's pore clock on the device, for a tension that comes from F (OL6 S4, L1; the design note's
§3.6 and §6.3, D304).

A world that declares cells.assembly_hazard.pore_nucleation@1 with no hold takes its tension from F: the osmotic
lumen's σ(N_L, W) at the exact counts, as kernel.lysis_at reads it. Its vesicles' rates then change
at events, so Phase A's host clock (pore_clock.Vesicle: t* = start_s + E/k_v at a held σ and a fixed
area) does not apply, and the clock moves onto the device:
- each vesicle draws E = −ln u from domain 7 (its key, counter 0) when the run first holds it (a
  founder at the start, a daughter at its birth), with H = 0 then (pore_clock.threshold);
- between events the state holds, so k_v is constant and H grows linearly: each committed event adds
  k_v·τ, the rate at the state before it times its wait;
- the candidate opening t_c = t + max(0, E − H)/k_v (inf where k_v = 0, a floppy vesicle) bounds the
  device's horizon, so the chemistry draw that would land past it is not committed; the lane halts
  and the host fires the pore at t_c, exactly (H is piecewise linear), discarding the crossing draw
  and counting it (discarded_at_pore) as at Phase A's host stop; a lane that halted inert is
  advanced to its t_c;
- the opening books pore_clock.opening_from_f (w = 0, ΔF = σ_β/σ − ln(A·n_s)), then the release
  from the open state, so ΔF cancels in the event's total.

**Static dispatch** (`clocked`). Phase A's worlds (a hold, a fixed area) keep the host clock, so
their programs, layouts and bits are unchanged: kernel.event runs as it is, with only its layout's
horizon replaced by min(horizon, t_c). The clock rides beside the lanes (`Clock`), never as a field
of kernel.Lane or population.Lane, whose fields checkpoints and records name.

**The rate** (`rate`) is the law's closed form, ln k_v = ln A + c0 + ½ ln σ − σ_β/σ with
c0 = ln ν_A − (3/2) ln T − E_A/(R·T) (`constants`, per lane), at A = q·W/2 and σ from the lumen's
exact (N_L, W); it is 0 where σ = 0 or A = 0, its logarithms guarded.
"""

import functools
import math
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.models.assembly_lineages_v2 import (
    PORE_NUCLEATION,
    kernel,
    lumen,
    pore_clock,
    pore_nucleation,
)

CLOCK = (
    "each vesicle's threshold E = -ln u, u from domain 7 (its key, counter 0), drawn when the run "
    "first holds it (a founder at the start, a daughter at its birth), H = 0 then; with sigma from "
    "F (an osmotic lumen, no hold) k_v changes at events, so the device carries H: each committed "
    "event adds k_v(n) tau, and the candidate opening t_c = t + max(0, E - H)/k_v bounds the "
    "device's horizon; the draw that crosses t_c is discarded and counted (discarded_at_pore), the "
    "pore fires at t_c, and an inert device is advanced to it"
)


class Clock(NamedTuple):
    """One lane's clock (single lineage: scalars; a population: one entry per slot)."""

    H: object  # float64: ∫ k_v dt since the vesicle's birth
    E: object  # float64: its threshold (inf with no vesicle)
    rate: object  # float64: k_v at the lane's current state
    crossing: object  # float64: the candidate opening t_c (inf where k_v = 0)


def clocked(spec):
    """Whether a definition's pore clock is on the device: the pore law with no hold (σ from F)."""
    world = spec.model.world
    return (world.hazard is not None and world.hazard[0] == PORE_NUCLEATION
            and not spec.experiment.tension_holds)  # fmt: skip


def constants(world):
    """[c0, σ_β] of a world that declares the pore law (module docstring), float64."""
    log_nu, gamma, e_a, _ = pore_nucleation.parameters(world)
    t = world.units.temperature_K
    c0 = log_nu - 1.5 * math.log(t) - e_a / (pore_nucleation.R * t)
    return np.asarray([c0, pore_nucleation.sigma_beta(gamma, t)], dtype=np.float64)


def rate(counts, layout, pore, xp=jnp):
    """k_v (1/s) of a vesicle's counts [..., P] (its membrane and lumen places; any pool places
    carry no quanta and no lumen weight), from the layout's geometry and `pore` = constants()."""
    g = layout.geometry
    footprint = xp.sum(counts * g[0], axis=-1)
    n_lumen = xp.sum(counts * g[7], axis=-1)
    sigma = lumen.tension(n_lumen, footprint, g[10], g[11], g[8], xp)
    area = g[11] * footprint.astype(np.float64) / 2.0
    live = (sigma > 0) & (area > 0)
    safe_sigma = xp.where(live, sigma, 1.0)
    log_k = xp.log(xp.where(live, area, 1.0)) + (pore[0] + 0.5 * xp.log(safe_sigma)
                                                  - pore[1] / safe_sigma)  # fmt: skip
    return xp.where(live, xp.exp(log_k), 0.0)


def crossing(time, h, e, k, xp=jnp):
    """t_c = time + max(0, E − H)/k_v, and inf where k_v = 0."""
    positive = k > 0
    return xp.where(positive, time + xp.maximum(e - h, 0.0) / xp.where(positive, k, 1.0), xp.inf)


def _select(flag, new, old):
    return jax.tree_util.tree_map(lambda a, b: jnp.where(flag, a, b), new, old)


def event(lane, clock, layout, pore, structure):
    """One event of one single-lineage lane with its clock: kernel.event, unchanged, with the
    horizon bounded by t_c; a committed event adds k_v·τ to H and re-rates the clock."""
    bounded = layout._replace(horizon=jnp.minimum(layout.horizon, clock.crossing))
    after, out = kernel.event(lane, bounded, structure)
    h = clock.H + clock.rate * (after.time - lane.time)
    k = rate(after.counts, layout, pore)
    new = Clock(h, clock.E, k, crossing(after.time, h, clock.E, k))
    return after, _select(out.committed, new, clock), out


@functools.cache
def program(structure):
    """(advance, rates) of one structure with the device clock: `advance(lanes, clocks, layout,
    pores)` runs a chunk of events, as kernel.program's, carrying the clocks beside the lanes;
    `rates(counts, layout, pores)` is the clock's rate at each lane's counts (the host's re-rating
    after its own operators)."""

    def advance(lanes, clocks, layout, pores):
        def body(carry, _):
            la, cl = carry

            def one(a, c, lo, po):
                return event(a, c, lo, po, structure)

            la, cl, out = jax.vmap(one)(la, cl, layout, pores)
            return (la, cl), out

        (lanes, clocks), out = jax.lax.scan(body, (lanes, clocks), None, length=structure.chunk)
        return lanes, clocks, out

    return jax.jit(advance), jax.jit(jax.vmap(lambda c, lo, po: rate(c, lo, po)))


class Vesicle:
    """A clocked vesicle's host record (the single lineage's holder.pores): its key, its draw, and
    once it fires, its rupture's time, area, tension and rate; `due` once it has fired."""

    hold = None  # σ comes from F: no hold

    def __init__(self, base_key, key, area, time=0.0):
        self.slot, self.key, self.counter = 0, int(key), 0
        self.area = float(area)
        self.u, self.energy = pore_clock.threshold(base_key, key, self.counter)
        self.born = float(time)
        self.time, self.rate, self.sigma, self.due = math.inf, None, None, False

    def draw(self):
        """The diagnostic record's row of its draw: (key, counter, u, E, t*), t* inf if unfired."""
        return (self.key, self.counter, self.u, self.energy, self.time)


def event_record(vesicle, heat_open, delta_f, q_release, returned, work_return, clock_h):
    """A rupture's record with σ from F (run.json's pores.events; pore_clock.event's fields, with
    no hold and no hold work, the opening's ΔF and H at the crossing)."""
    return {
        "time_s": vesicle.time,
        "slot": vesicle.slot,
        "key": vesicle.key,
        "hold": None,
        "sigma_N_per_m": vesicle.sigma,
        "area_m2": vesicle.area,
        "rate_per_s": vesicle.rate,
        "threshold_E": vesicle.energy,
        "counter": vesicle.counter,
        "clock_H": clock_h,
        "work_kT": 0.0,
        "opening_heat_kT": heat_open,
        "delta_F_kT": delta_f,
        "cause": "pore",
        "release": {
            "returned": returned,
            "release_heat_kT": q_release,
            "release_reservoir_work_kT": work_return,
        },
    }


# ------------------------------------------------------------------ a population, a clock per slot


def population_event(lane, clock, layout, pore, structure, m):
    """One event of a population lane with its slots' clocks: population.event, unchanged, with the
    horizon bounded by the earliest living slot's t_c; a committed event adds each slot's k_v·τ to
    its H and re-rates every slot (0 in an empty one)."""
    from cells.models.assembly_lineages_v2 import population

    first = jnp.min(jnp.where(lane.alive, clock.crossing, jnp.inf))
    bounded = layout._replace(horizon=jnp.minimum(layout.horizon, first))
    after, out = population.event(lane, bounded, structure, m)
    h = clock.H + clock.rate * (after.time - lane.time)
    k = jnp.where(after.alive, rate(after.slots, layout, pore), 0.0)
    new = Clock(h, clock.E, k, crossing(after.time, h, clock.E, k))
    return after, _select(out.committed, new, clock), out


@functools.cache
def population_program(structure):
    """(advance, rates) for a population with the device clock, as population.program's advance
    with the slots' clocks beside the lane; `rates(slots [L, K, P], layouts, pores)`."""

    def advance(lanes, clocks, layouts, pores, m):
        def body(carry, _):
            la, cl = carry

            def one(a, c, lo, po, ma):
                return population_event(a, c, lo, po, structure, ma)

            la, cl, out = jax.vmap(one)(la, cl, layouts, pores, m)
            return (la, cl), out

        (lanes, clocks), out = jax.lax.scan(body, (lanes, clocks), None, length=structure.chunk)
        return lanes, clocks, out

    return jax.jit(advance), jax.jit(jax.vmap(lambda s, lo, po: rate(s, lo, po)))


def carry_over(clock, rates, keys_before, keys_after, alive, time_from, time_to, base_key,
               areas, vesicles):
    """A population's clocks across the host's own operators at time_to (a stop, a rupture, a
    lysis), on the host (numpy, [K] each): a slot whose vesicle stays runs H to time_to at its
    rate and keeps its t_c; a slot with a new vesicle (a daughter, or one placed there) draws its
    own threshold at its birth, H = 0, at `rates` (its new counts'); an empty slot has no clock.
    `vesicles` (slot: Vesicle) is updated in place; returns the new clock and the new vesicles in
    slot order (their draws, for the record)."""
    h, e, k, t_c = (np.array(a, dtype=np.float64) for a in clock)
    born = []
    for s in range(h.shape[0]):
        if alive[s] and keys_after[s] == keys_before[s] and s in vesicles:
            h[s] += k[s] * (time_to - time_from)
            continue
        vesicles.pop(s, None)
        if not alive[s]:
            h[s], e[s], k[s], t_c[s] = 0.0, np.inf, 0.0, np.inf
            continue
        vesicle = Vesicle(base_key, int(keys_after[s]), areas[s], time=time_to)
        vesicle.slot = s
        vesicles[s] = vesicle
        born.append(vesicle)
        h[s], e[s], k[s] = 0.0, vesicle.energy, float(rates[s])
        t_c[s] = crossing(time_to, 0.0, vesicle.energy, k[s], np)
    return Clock(h, e, k, t_c), born


def lifecycle(base, population=False):
    """A device-clocked pore world's lifecycle: pore_clock.lifecycle's statuses, with the device's
    order (records._lifecycle)."""
    out = pore_clock.lifecycle(base, population=population)
    order = base["order"] + (
        "; the device bounds its horizon by each living vesicle's candidate opening t_c = t + "
        "max(0, E - H)/k_v, the draw that crosses it is discarded and counted, and the pore fires "
        "at t_c"
    )
    return {**out, "order": order}
