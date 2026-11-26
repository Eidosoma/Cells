"""cells.operator.pool_withdrawal@1: a fraction of a population's well-mixed pool drawn off at declared
times, the same volume of a declared buffer added (FR-35; D261; docs/ASSEMBLY_WITHDRAWAL_DESIGN.md).

The experiment declares `{index, kind: withdrawal, times_s, fraction, buffer}`. `fraction` f is in
(0, 1); `buffer` gives one integer count per finite pool place, in place order: the molecules in
the withdrawn volume fV (tracer-free is 0). At each time, a host stop:
- **the draw:** each molecule of each finite pool place leaves independently with probability q,
  f in the sampler's finite word: the uniforms are (m + 0.5)·2⁻⁵² with m a 52-bit integer, so
  q = #{m : (m + 0.5)·2⁻⁵² < f}·2⁻⁵², and q = f exactly at dyadic fractions such as ¼ and ½ (the
  Lean lane's finding of 21 November 2026). A place's withdrawn count is Binomial(n, q) exactly
  in distribution. Place j's molecules (j
  its ordinal among the P_f finite pool places, in place order) draw one block of n_j uniforms on
  the schedule's stream (domain 6, its declared index as the carrier word) at draw number
  w·P_f + j, w the schedule's washes before this one; molecule i leaves when u_i < f. A place's
  outcome depends only on its own count and its address; an empty place draws nothing and keeps
  its address. w is not stored: it is the count of this schedule's stops among the stops already
  applied (FR-22's applied-stops record), so a checkpoint carries it as one number;
- **kept:** every slot as it stands (its places, key, sub-lineage and life) and the held places;
- **the pool** after is the kept molecules plus the buffer's, in the pool's own volume.

**Capacity, before the draw** (D261 item 5): the wash is refused when a place's pre-wash count plus
its buffer count exceeds molecule_capacity (the k = 0 worst case), so no refusal depends on the
draw and the binomial is never truncated. The run's own F (ledger.state_free_energy) stays as the
backstop.

**Booking** (the design note's A, FR-27's booking with the discrete F). With F(c; gV) the pool's F
of counts c in volume gV, read through the guarded table at V and shifted by −(Σc)·ln g:
- the sink takes F(before; V) − F(kept; (1 − f)V), the free energy the pool loses as the sample
  leaves, given the outcome (`pool_loss_kT`). It is not the sample's own F(k; fV)
  (`sample_F_kT`): they differ by σ = −ln[C(n, k) f^k (1 − f)^(n−k)] summed over places, the
  outcome's binomial surprisal (`split_surprisal_kT`), booked against the physical f, not the
  sampler's q;
- the schedule's work column takes F(buffer; fV) (`buffer_F_kT`), paid by source:withdrawal/<index>;
- the heat ledger takes the mixing heat F(kept; (1 − f)V) + F(buffer; fV) − F(after; V)
  (`mixing_heat_kT`), which is −ln of a binomial probability, so never negative;
- F(after) − F(before) = work − sink − heat exactly, and F is additive over the pool and the
  vesicles, so the books close. Per-event booking is exact either way, since every term is a
  function of the realized k and the physical f. At f = 1 these are cells.operator.pool_replacement@1's
  bookings with zero heat; f = 1 itself is that operator's.
- **The mean heat:** for n tracers and a tracer-free buffer it is exactly −n(1 − q) ln(1 − f).
  This is FR-27's −n(1 − f) ln(1 − f) where q = f. The extreme fraction shows the largest
  relative gap: at f = 1 − 2⁻⁵³, 1 − q = 2⁻⁵² against 1 − f = 2⁻⁵³, so a surviving tracer's
  booked split score exceeds the sampler's by ln 2, and one tracer's mean heat is 8.1572e-15 kT
  against the ideal-volume 4.0786e-15 kT.

**Records.** Each withdrawal's time, schedule, fraction, the pre-wash, withdrawn, remaining and
supplied counts per finite place, its draws' addresses (index, draw number, size), and the five
energies above; a row of kind `withdrawal`, listed in run.json's legend only when a world declares
a withdrawal; in cells.relations@2, an event `event:withdrawal/<n>` paid by its source, the pool as
a node, and `removes_to` and `supplies` edges per species weighed by the withdrawn and supplied
counts.

**Refused:** a withdrawal without a population; f outside (0, 1); a buffer of the wrong length or
with a count above molecule_capacity; a buffer whose concentration in fV exceeds c_ext (§0.2c rule
6; the realized pool's drift is reported, as every run's); a held pool species the assemblies take
up (FR-20's Q3: the wash would be silently partial for it), and any held source that reaches a
finite place through the steps (D263: replacement.refuse_unlimited_sources, a held fuel or
precursor included); a withdrawal at another stop's declared
time (division.parse_schedules), or with a Poisson shear or a lysis at its time.
"""

import math

import numpy as np

from cells.definitions.specs import ConfigError, bounded_integer, finite_number
from cells.models.assembly_lineages_v2 import MODEL_ID, streams
from cells.models.assembly_lineages_v2.interfaces import AssemblyOperator
from cells.modules import Citation
from cells.registry import operators as operator_registry

POOL_WITHDRAWAL = "cells.operator.pool_withdrawal@1"
KEYS = {"index", "kind", "times_s", "fraction", "buffer"}


def finite_places(world):
    """The finite pool places' indices, in place order (their ordinals j are the draw's)."""
    return [i for i, p in enumerate(world.places) if p.phase == "pool" and not p.held]


def parse(entry, world):
    from cells.models.assembly_lineages_v2 import division, lumen

    if world.population is None:
        raise ConfigError("experiment: a withdrawal needs a population (execution mode population)")
    if set(entry) != KEYS:
        raise ConfigError(f"experiment: a withdrawal's keys are {sorted(KEYS)}")
    index = bounded_integer(entry["index"], "experiment: schedule index", minimum=0,
                            maximum=2**31 - 1)  # fmt: skip
    times = entry["times_s"]
    if type(times) is not list or not times:
        raise ConfigError("experiment: a withdrawal's times_s is a non-empty list")
    times = tuple(finite_number(t, "experiment: a withdrawal time", positive=True) for t in times)
    if any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError("experiment: a withdrawal's times_s are strictly increasing")
    fraction = finite_number(entry["fraction"], "experiment: a withdrawal's fraction")
    if not 0.0 < fraction < 1.0:
        raise ConfigError(
            f"experiment: a withdrawal's fraction is in (0, 1), not {fraction!r}: 0 withdraws "
            "nothing, and a whole exchange (1) is cells.operator.pool_replacement@1's"
        )
    finite = finite_places(world)
    buffer = entry["buffer"]
    if type(buffer) is not list or len(buffer) != len(finite):
        raise ConfigError(
            "experiment: a withdrawal's buffer gives one count per finite pool place, in place "
            "order, the molecules in the withdrawn volume: "
            f"{[world.places[i].name for i in finite]}"
        )
    buffer = tuple(bounded_integer(c, "experiment: a withdrawal's buffer", minimum=0)
                   for c in buffer)  # fmt: skip
    taken = {p.species for p in world.places if p.phase in ("membrane", "lumen")}
    held = sorted(
        p.name for p in world.places if p.phase == "pool" and p.held and p.species in taken
    )
    if held:
        raise ConfigError(
            f"experiment: a withdrawal leaves held places as they are, so {held}, which the "
            "assemblies take up, would be washed out only in part: declare it finite (FR-20's Q3)"
        )
    from cells.models.assembly_lineages_v2 import replacement

    replacement.refuse_unlimited_sources(world, "a withdrawal", "buffer")  # D263, as a replacement
    if world.conventions.lumen_volume == "osmotic":  # §0.2c rule 6, on the buffer itself
        volume = fraction * world.volume("pool")
        held_mM = sum(p.held_mM for p in world.places if p.phase == "pool" and p.held)
        solutes = sum(buffer) / (lumen.AVOGADRO * volume) * 1e3 + held_mM  # mM
        c_ext = lumen.outside_mM(world)
        if solutes > c_ext:
            raise ConfigError(
                f"experiment: the withdrawal's buffer is {solutes:.6g} mM in its volume, above "
                f"c_ext, {c_ext:.6g} mM (§0.2c rule 6)"
            )
    return division.Schedule(index, "withdrawal", None, times, None, None, None, buffer,
                             fraction=fraction)  # fmt: skip


def refuse_beyond_capacity(world, schedule, pool, capacity):
    """D261 item 5: before the draw, each place's pre-wash count plus its buffer count is at most
    the capacity (the k = 0 worst case), so no refusal depends on the draw."""
    for i, b in zip(finite_places(world), schedule.fresh, strict=True):
        if int(pool[i]) + b > capacity:
            raise ConfigError(
                f"Withdrawal {schedule.index}: {world.places[i].name} holds {int(pool[i])} before "
                f"the wash and its buffer {b}, so the pool could reach {int(pool[i]) + b}, above "
                f"molecule_capacity {capacity}; refused before the draw (declare a larger capacity)"
            )


def draw(base_key, world, schedule, wash, pool):
    """(withdrawn [P] int64, [(index, draw number, size)]): wash `wash` of this schedule on the
    pre-wash pool, per place one block of its count at draw number wash·P_f + j (module
    docstring)."""
    finite = finite_places(world)
    key = streams.stream_key_data(base_key, schedule.index, "schedule")
    taken = np.zeros_like(pool)
    addresses = []
    for j, i in enumerate(finite):
        n, number = int(pool[i]), wash * len(finite) + j
        if n:
            u = np.asarray(streams.block(key, number, n), dtype=np.float64)
            taken[i] = int(np.count_nonzero(u < schedule.fraction))
        addresses.append((schedule.index, number, n))
    return taken, addresses


def buffer_vector(world, schedule, size):
    out = np.zeros(size, dtype=np.int64)
    out[finite_places(world)] = schedule.fresh
    return out


def booking(pool_f, before, taken, buffer, fraction, world):
    """The five energies of a withdrawal (module docstring), from pool_f(c): F of the pool vector c
    at the pool's volume through the guarded table read. F(c; gV) = pool_f(c) − pool_f(0) −
    (Σc)·ln g, the empty pool's F subtracted so that only the pool's own counts enter."""
    finite = np.zeros(before.size, dtype=bool)
    finite[finite_places(world)] = True
    zero = pool_f(np.zeros_like(before))
    ln_f = math.log(fraction)
    ln_rest = math.log1p(-fraction) if fraction < 1.0 else -math.inf  # the small-ratio form

    def F(c, ln_g):
        """F(c; gV): an empty c has F 0 at any volume (0·ln g is 0, even for g = 0)."""
        total = int(np.sum(np.where(finite, c, 0)))
        return pool_f(c) - zero - (total * ln_g if total else 0.0)

    kept = before - taken
    after = kept + buffer
    f_before, f_kept, f_after = F(before, 0.0), F(kept, ln_rest), F(after, 0.0)
    sample, work = F(taken, ln_f), F(buffer, ln_f)
    return {
        "pool_loss_kT": f_before - f_kept,
        "sample_F_kT": sample,
        "split_surprisal_kT": f_kept + sample - f_before,
        "buffer_F_kT": work,
        "mixing_heat_kT": f_kept + work - f_after,
    }


def by_place(world, vector):
    return {world.places[i].name: int(vector[i]) for i in finite_places(world)}


CONTRACT = {
    "trigger": "a declared withdrawal time, which no other stop shares: a shear, a transfer, a "
    "replacement or another withdrawal at the same declared time is refused at parse, and a "
    "Poisson shear drawn at it is refused at the run's start",
    "draw": "each molecule of each finite pool place leaves independently with probability f: "
    "place j's block of n_j uniforms on the schedule's stream (domain 6, its declared index) at "
    "draw number w P_f + j, w the schedule's washes already applied; molecule i leaves when "
    "u_i < f",
    "keep": "every living assembly, as it stands: its places, key, sub-lineage and life",
    "pool": "the kept molecules plus the buffer's declared counts, in the pool's own volume; held "
    "places, c_ext and the volume are unchanged; refused before the draw when a place's pre-wash "
    "count plus its buffer count exceeds molecule_capacity",
    "booking": "the sink takes F(before; V) - F(kept; (1-f)V); the schedule's work column takes "
    "F(buffer; fV) (source:withdrawal/<index>); the heat ledger takes the mixing heat "
    "F(kept; (1-f)V) + F(buffer; fV) - F(after; V), never negative",
}

OPERATOR = operator_registry.BUILTIN.register(
    AssemblyOperator(
        POOL_WITHDRAWAL,
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ASSEMBLY_WITHDRAWAL_DESIGN.md (FR-35, decided by the lead in D261); "
            "docs/COMPARTMENT_WASH_DESIGN.md §2 (FR-27's liquid exchange, one mechanism)",
            "a fraction of a population's well-mixed pool drawn off molecule by molecule, the same "
            "volume of buffer added, the exchange booked as a sink, schedule work and mixing heat",
            "no numbers taken",
            ("the pool's volume is a world constant; the withdrawn volume is fV",),
        ),
        test="tests/unit/test_assembly_lineages_v2_replacement.py::"
        "test_a_withdrawal_keeps_every_slot_draws_each_molecule_and_closes_its_books",
        reads="the pool's finite places, the schedule's stream",
        writes="the pool's finite places",
        energy_role="sink: F(before) - F(kept at (1-f)V); work: the buffer's F at fV (its "
        "schedule); heat: the mixing heat",
        rules={"draw": ["each molecule independently with probability f, per-place blocks"]},
        stream="schedule: domain 6 by the schedule's declared index, one block per finite pool "
        "place per wash at draw number w P_f + j",
        contract=CONTRACT,
    )
)
DECLARATION = OPERATOR.record()
assert OPERATOR.operator_id == POOL_WITHDRAWAL
