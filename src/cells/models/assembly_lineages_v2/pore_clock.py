"""FR-31 Phase A: the pore clock on the host, and a rupture through the release (the lead's rulings
of 22 November 2026; docs/VESICLE_PORES_LAWS.md §3, §5-§7, tagged
pores-laws-sheet-registered-2026-11-22).

**The clock** (the sheet's §5; Anderson 2007). A world that declares the pore law with a hold holds
its tension: the experiment's hold (tension_hold.py) sets σ, and no step changes a membrane place's
count, so each vesicle's area A = q·W/2 is fixed and its rate k_v(σ) is constant through the hold.
(A pore world with no hold takes σ from F, and its clock is on the device: pore_device.py, OL6 S4.)
- Each vesicle draws its threshold once, when the run first holds it (a founder, at the start):
  E = −ln u, u from the pore stream (domain 7, carrier word the vesicle's key, counter 0: its pore
  draws).
- Its internal time H(t) grows at k_v while the hold is in force, so it ruptures at
  t* = start_s + E/k_v, when t* ≤ end_s; otherwise not in the hold. A t* past the horizon is no
  event of the run.
- **Both endpoints are decided exactly** (`reaches`), from the binary values: t* ≤ end_s as
  E/k_v ≤ end_s − start_s, and t* ≤ the horizon as E/k_v ≤ horizon − start_s, in rationals of the
  float64 E, k_v (the rate its event records), start_s and cutoff. t* itself stays the float64
  start_s + E/k_v, which the host schedules and records. From one start (Phase A's one hold),
  rounding never carries a crossing across a cutoff, nor past another crossing; it can only round
  it onto one. So the exact comparison changes a decision only where t* equals the cutoff and the
  exact crossing lies beyond it: no rupture there. (The Lean lane's finding, 22 November 2026: a
  founder ruptured at a hold's end that its exact crossing passes by 2.4e-17 s.)
- The host treats t* as a stop. The chemistry draw that crosses it is discarded and counted, as
  at a schedule stop (the diagnostic fate `discarded_at_pore`). A device that ends `inert` before
  t* is advanced to it. The device kernel is the same program in every world.
- While a vesicle lives its clock runs, so a pore world whose chemistry is idle ends `complete`
  at the horizon, never `inert`; a population whose vesicles have all ruptured may end `inert`.
- Same-time stops are refused at the run's start: a t* equal to another vesicle's, or to a
  schedule stop's time (FR-20's rule: relations have no order between same-time events). Equal as
  recorded, in float64, not as exact crossings: relations read the recorded times, where two
  crossings that round to one t* are one time, and an exact tie rounds to one t*. Since rounding
  never reverses two crossings, the stops that are not refused run in their exact order. D283's
  same-instant band (4 ulps) is for declared times on a step's grid, and this clock has none.

**A rupture** (§6, §7). The opening is the forward of a pair, closed to a pore at r_c = Γ/σ:
- the hold does w = σ·πr_c² = σ_β/σ (k_BT), booked in its column, `tension_hold_work_kT`, paid by
  `source:tension_hold/<index>`;
- the vesicle's F rises by ΔF = 2πr_cΓ − k_BT·ln(A·n_s) = (2σ_β/σ − ln(A·n_s)) k_BT, n_s the site
  density of §7's closed form;
- so the opening books q_open = −ΔF + w = ln(A·n_s) − σ_β/σ, which is ln(k_v/P).
The open pore then ruptures at once (an exact-event world represents no pore's growth): the
existing release from the open state, every membrane and lumen molecule to its species' pool place
(a held place's reservoir takes them back, with its reservoir work w_r), the closure cost released.
It books q_release = −(F(after) − F(open)) + w_r, F(open) = F(n) + ΔF. The event's heat is
q_open + q_release = −(F(after) − F(n)) + w + w_r: ΔF cancels, so the books close for any η₂₉₈.
A rupture is a lysis: its life ends `lysed`, with the cause `pore` (a σ_max lysis's is
`threshold`; an osmotic lumen is refused with a hold, so Phase A has none).
"""

import math
from fractions import Fraction

import numpy as np

from cells.models.assembly_lineages_v2 import geometry, model, pore_nucleation, streams

PORE_ROW = 9  # the row kind `pore` (records.py writes its legend entry only in pore worlds)
PORE_ROW_KIND = "pore"
DISCARDED_PORE = "discarded_at_pore"  # the diagnostic fate of a draw that crosses a pore stop
CAUSES = ("pore", "threshold")


def area_m2(world, counts):
    """A = q·W/2 (m²) of a vesicle's counts (a state over at least the world's places)."""
    quanta = geometry.place_quanta(world, len(world.places))
    footprint = int(np.asarray(counts, dtype=np.int64)[: len(world.places)] @ quanta)
    return float(geometry.area_m2(world, footprint))


def threshold(base_key, key, counter=0):
    """(u, E = −ln u) of a vesicle's pore draw: domain 7, its key, the counter."""
    stream = streams.stream_key_data(base_key, int(key), "pore")
    u = float(np.asarray(streams.uniforms(stream, int(counter), 1))[0])
    return u, -math.log(u)


def log_rate(world, area, sigma):
    """ln k_v (k_v in 1/s) of a vesicle of area A (m²) at a held σ (N/m), at the world's T."""
    log_nu, gamma, e_a, _ = pore_nucleation.parameters(world)
    return pore_nucleation.log_rate(area, sigma, world.units.temperature_K, log_nu, gamma, e_a)


def reaches(energy, rate, start, cutoff):
    """Whether H, growing at `rate` k_v (1/s) from `start` (s), reaches `energy` (E, or what is
    left of it at the hold's start) by `cutoff` (s): E/k_v ≤ cutoff − start, decided exactly in
    rationals of the binary values, never on t* as it rounds (the module docstring)."""
    return Fraction(energy) / Fraction(rate) <= Fraction(cutoff) - Fraction(start)


def crossing(world, holds, area, energy):
    """(t*, the hold, ln k_v, E′) where H(t), growing at k_v while each hold is in force (in time
    order), reaches the threshold E; (inf, None, None, None) when it never does. E′ is E less H at
    the hold's start, exact (E itself in Phase A's one hold): whether H reaches E within a hold, or
    within the horizon (Vesicle.due), is decided on it (reaches). t* = start_s + E′/k_v in float64,
    the time the host schedules and records."""
    reached = Fraction(0)  # H at the next hold's start, exact
    for hold in sorted(holds, key=lambda h: h.start):
        log_k = log_rate(world, area, hold.sigma)
        rate = math.exp(log_k)
        if rate > 0:
            left = Fraction(energy) - reached
            if reaches(left, rate, hold.start, hold.end):
                return hold.start + float(left) / rate, hold, log_k, left
            reached += Fraction(rate) * (Fraction(hold.end) - Fraction(hold.start))
    return math.inf, None, None, None


def rupture_time(world, holds, area, energy):
    """(t*, the hold, ln k_v) of `crossing`: (inf, None, None) when no hold brings H to E."""
    return crossing(world, holds, area, energy)[:3]


def opening(world, area, sigma):
    """(w, q_open, ΔF) of a pore's opening to r_c, each in k_BT: w = σ_β/σ, the hold's work;
    ΔF = 2σ_β/σ − ln(A·n_s), the vesicle's; q_open = −ΔF + w (module docstring)."""
    log_nu, gamma, e_a, eta = pore_nucleation.parameters(world)
    beta = pore_nucleation.sigma_beta(gamma, world.units.temperature_K)
    work = beta / sigma
    log_sites = math.log(area) + pore_nucleation.log_site_density(log_nu, gamma, e_a, eta)
    delta_f = 2.0 * beta / sigma - log_sites
    return work, -delta_f + work, delta_f


def opening_from_f(world, area, sigma):
    """(w, q_open, ΔF) of a pore's opening where σ comes from F, each in k_BT (OL6 S3; the sheet's
    §7): no hold does work, w = 0, and the pore's area relief is inside ΔF to leading order in
    r_c/R_v, ΔF = 2σ_β/σ − σ_β/σ − ln(A·n_s) = σ_β/σ − ln(A·n_s); so q_open = −ΔF = ln(k_v/P), as
    under a hold."""
    log_nu, gamma, e_a, eta = pore_nucleation.parameters(world)
    beta = pore_nucleation.sigma_beta(gamma, world.units.temperature_K)
    log_sites = math.log(area) + pore_nucleation.log_site_density(log_nu, gamma, e_a, eta)
    delta_f = beta / sigma - log_sites
    return 0.0, -delta_f, delta_f


def release(world, layout, counts):
    """A rupture's release of the vesicle in `counts` (its places; any pool places are not read):
    (added [P] to the pool's finite places, took [P] from each held reservoir's net supply,
    {pool place: count} returned, the reservoir work w_r = −Σ μ_held × the molecules a held place
    took back), in place order, as the lysis's release does (runner._release)."""
    held_mu = model.place_arrays(world, layout.place_held.shape[0])[5]
    pool_index = {p.species: i for i, p in enumerate(world.places) if p.phase == "pool"}
    added = np.zeros(layout.place_held.shape[0], dtype=np.int64)
    took = np.zeros_like(added)
    returned, work = {}, 0.0
    for i, place in enumerate(world.places):
        amount = int(counts[i])
        if place.phase not in ("membrane", "lumen") or amount == 0:
            continue
        j = pool_index[place.species]  # every one has a pool place (pore_nucleation.parse_data)
        returned[world.places[j].name] = returned.get(world.places[j].name, 0) + amount
        if world.places[j].held:
            took[j] -= amount
            work -= amount * float(held_mu[j])
        else:
            added[j] += amount
    return added, took, returned, work


class Vesicle:
    """One vesicle's clock: its key, area, threshold draw and rupture time (t* may be inf), and
    whether its rupture is an event of the run (`due`: t* within the horizon, decided exactly)."""

    def __init__(self, spec, base_key, key, counts, slot=0):
        world = spec.model.world
        self.slot, self.key, self.counter = int(slot), int(key), 0
        self.area = area_m2(world, counts)
        self.u, self.energy = threshold(base_key, key, self.counter)
        self.time, self.hold, self.log_rate, left = crossing(
            world, spec.experiment.tension_holds, self.area, self.energy
        )
        self.due = self.hold is not None and reaches(
            left, math.exp(self.log_rate), self.hold.start, spec.experiment.time_horizon_s
        )

    def draw(self):
        """The diagnostic record's row of its draw: (key, counter, u, E, t*)."""
        return (self.key, self.counter, self.u, self.energy, self.time)


def clock_record(vesicle):
    """A living vesicle's clock as a checkpoint's host document keeps it (t* null when inf)."""
    return {"slot": vesicle.slot, "key": vesicle.key, "threshold_E": vesicle.energy,
            "counter": vesicle.counter,
            "t_star": vesicle.time if math.isfinite(vesicle.time) else None}  # fmt: skip


def refuse_other_clocks(clocks, saved):
    """A restart's clocks, rebuilt from each living vesicle's key and counts, are the checkpoint's
    (checkpoints.py), or the run is refused."""
    from cells.definitions.specs import ConfigError

    rebuilt = [clock_record(v) for _, v in sorted(clocks.items())]
    if rebuilt != saved:
        raise ConfigError(
            "The checkpoint's pore clocks are not its definition's: the living vesicles' keys, "
            "thresholds or rupture times differ"
        )


def event(world, vesicle, heat_open, work, q_release, returned, work_return):
    """A rupture's record (run.json's pores.events, the lead's ruling 3; the release records σ_hold
    and no σ_max)."""
    return {
        "time_s": vesicle.time,
        "slot": vesicle.slot,
        "key": vesicle.key,
        "hold": vesicle.hold.index,
        "sigma_N_per_m": vesicle.hold.sigma,
        "area_m2": vesicle.area,
        "rate_per_s": math.exp(vesicle.log_rate),
        "threshold_E": vesicle.energy,
        "counter": vesicle.counter,
        "work_kT": work,
        "opening_heat_kT": heat_open,
        "cause": "pore",
        "release": {
            "returned": returned,
            "release_heat_kT": q_release,
            "release_reservoir_work_kT": work_return,
        },
    }


def refuse_same_time(vesicles, stop_times):
    """FR-20's rule at the run's start: a rupture time shared with another vesicle's, or with a
    schedule stop's, is refused (relations have no order between same-time events). The times are
    compared as recorded, in float64, which refuses every exact tie too (the module docstring)."""
    from cells.definitions.specs import ConfigError

    times = sorted(v.time for v in vesicles if math.isfinite(v.time))
    for a, b in zip(times, times[1:], strict=False):
        if a == b:
            raise ConfigError(
                f"Two vesicles' pores open at the same time, {a} s: relations have no order "
                "between same-time events, so the run is refused"
            )
    shared = sorted(set(times) & set(stop_times))
    if shared:
        raise ConfigError(
            f"A pore opens at {shared[0]} s, the time of a schedule stop: relations have no "
            "order between same-time events, so the run is refused (FR-20's rule)"
        )


def block(spec, events, causes):
    """run.json's `pores`: the law, its declared parameters and derived constants, the events and
    the counts by cause."""
    world = spec.model.world
    law_id, data = world.hazard
    log_nu, gamma, e_a, eta = pore_nucleation.parameters(world)
    temperature = world.units.temperature_K
    return {
        "law": law_id,
        "parameters": {k: {"value": data[k][0], "provenance": data[k][1]} for k in data},
        "units": dict(pore_nucleation.UNITS),
        "derived": {
            "temperature_K": temperature,
            "sigma_beta_N_per_m": pore_nucleation.sigma_beta(gamma, temperature),
            "log_site_density_per_m2": pore_nucleation.log_site_density(log_nu, gamma, e_a, eta),
        },
        "events": events,
        "causes": {cause: int(causes.get(cause, 0)) for cause in CAUSES},
        "reads": "each event's heat is opening_heat_kT + release.release_heat_kT, its work "
        "work_kT (the hold's column) + release.release_reservoir_work_kT; the opening's dF "
        "cancels across the two",
    }


def holds_block(spec):
    """run.json's `tension_hold`: one entry per hold, with its payer."""
    from cells.models.assembly_lineages_v2 import tension_hold

    return [{"index": h.index, "sigma_N_per_m": h.sigma, "start_s": h.start, "end_s": h.end,
             "payer": tension_hold.payer(h)} for h in spec.experiment.tension_holds]  # fmt: skip


def draw_arrays(draws):
    """The diagnostic record's domain-7 draws: one row per vesicle's threshold draw."""
    return {
        "pore_draw_key": np.asarray([d[0] for d in draws], dtype=np.int64),
        "pore_draw_counter": np.asarray([d[1] for d in draws], dtype=np.int64),
        "pore_draw_uniform": np.asarray([d[2] for d in draws], dtype=np.float64),
        "pore_draw_threshold": np.asarray([d[3] for d in draws], dtype=np.float64),
        "pore_draw_time": np.asarray([d[4] for d in draws], dtype=np.float64),
    }


CLOCK = (
    "each vesicle's threshold E = -ln u, u from domain 7 (its key, counter 0), drawn when the run "
    "first holds it; t* = start_s + E/k_v(sigma) while the hold is in force; the host stops at "
    "t*: the chemistry draw that crosses it is discarded and counted (discarded_at_pore), and an "
    "inert device is advanced to it; a living vesicle's clock runs, so idle chemistry ends "
    "complete at the horizon"
)


def lifecycle(base, population=False):
    """A pore world's lifecycle, from the one its mode would have (records._lifecycle)."""
    statuses = dict(base["statuses"])
    statuses["complete"] = (
        "the next event, a step or a vesicle's rupture, would pass the time horizon: the state "
        "holds to it; a living vesicle's clock runs, so a world whose chemistry is idle ends here"
    )
    statuses["inert"] = (
        "every rate is zero and no vesicle lives: a living vesicle's clock runs, so such a world "
        "ends complete"
    )
    if population:
        statuses["lysed"] += (
            "; a vesicle's rupture at its t* (cells.assembly_hazard.pore_nucleation@1, cause pore) is a lysis: it "
            "frees its slot"
        )
    else:
        statuses["lysed"] = (
            "the vesicle ruptured at its t* (cells.assembly_hazard.pore_nucleation@1, cause pore): its molecules "
            "return to their pool places and its closure cost is released"
        )
    order = base["order"] + (
        "; the host stops at each vesicle's rupture time t*, the device's horizon until then, "
        "and the draw that crosses it is discarded and counted"
    )
    return {**base, "statuses": statuses, "order": order}
