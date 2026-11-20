"""cells.pool_replacement@1: a population's exterior replaced at declared times, a pulse or a
washout (FR-20; D237, D240; docs/ASSEMBLY_WASHOUT_DESIGN.md).

The experiment declares `{index, kind: replacement, times_s, pool}`: pool gives one count per finite
pool place, in place order (as a transfer's fresh_pool). At each time, a host stop:
- it draws nothing (the schedule's stream, domain 6 by its index, is never drawn) and keeps every
  slot as it stands: its places, key, sub-lineage and life, so a gate's state and a bound tracer
  stay where they are;
- the pool's finite places take `pool`. The held places, c_ext and the pool's volume are unchanged
  (the user's Q1: the wash bath has the pool's own volume). The bath stays finite, so molecules the
  assemblies release accumulate in it and can re-enter;
- a pulse is a replacement whose pool holds tracer, and a washout one whose pool holds none (Q2).
Same-time stops act in schedule-index order with every other schedule (§0.2d item 10.1).

**Booking.** F is additive over the pool and the vesicles, so F(after) − F(before) = F(fresh pool) −
F(old pool): the sink takes F(old pool), and the schedule's work column takes F(fresh pool), paid
by source:replacement/<index>; the books close. The pool step (the finite places replaced, and F
of the pool before and after) is the transfer's (transfer.replaced_pool), so every transfer world
is unchanged bitwise.

**Records.** Each replacement's time, schedule, the old pool's count per finite place (removed to
the sink), the fresh pool's (supplied by its source), the sink's F and its work; a row of kind
`replacement`; in cells.relations@2, an event `event:replacement/<n>` paid by its source, the pool
as a node (`node:pool`), and `removes_to` and `supplies` edges per species weighed by those counts.

**Refused** (the design note's W6): a replacement without a population; a pool of the wrong length;
fresh solutes above c_ext (the transfer's refusal, §0.2c rule 6; Q4); and a world with a held pool
species that the assemblies take up (it has a membrane or lumen place). A replacement leaves held
places as they are, so such a species, a tracer held at a concentration, could never be washed out;
it is declared finite instead (Q3).
"""

from cells.definitions.specs import ConfigError, bounded_integer, finite_number
from cells.models.assembly_lineages_v2 import MODEL_ID
from cells.models.assembly_lineages_v2.interfaces import AssemblyOperator
from cells.modules import Citation
from cells.registry import operators as operator_registry

POOL_REPLACEMENT = "cells.pool_replacement@1"
KEYS = {"index", "kind", "times_s", "pool"}


def parse(entry, world):
    from cells.models.assembly_lineages_v2 import division, transfer

    if world.population is None:
        raise ConfigError(
            "experiment: a replacement needs a population (execution mode population)"
        )
    if set(entry) != KEYS:
        raise ConfigError(f"experiment: a replacement's keys are {sorted(KEYS)}")
    index = bounded_integer(entry["index"], "experiment: schedule index", minimum=0,
                            maximum=2**31 - 1)  # fmt: skip
    times = entry["times_s"]
    if type(times) is not list or not times:
        raise ConfigError("experiment: a replacement's times_s is a non-empty list")
    times = tuple(finite_number(t, "experiment: a replacement time", positive=True) for t in times)
    if any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError("experiment: a replacement's times_s are strictly increasing")
    finite = [i for i, p in enumerate(world.places) if p.phase == "pool" and not p.held]
    pool = entry["pool"]
    if type(pool) is not list or len(pool) != len(finite):
        raise ConfigError(
            f"experiment: a replacement's pool gives one count per finite pool place, in place "
            f"order: {[world.places[i].name for i in finite]}"
        )
    pool = tuple(bounded_integer(c, "experiment: a replacement's pool", minimum=0) for c in pool)
    taken = {p.species for p in world.places if p.phase in ("membrane", "lumen")}
    held = sorted(
        p.name for p in world.places if p.phase == "pool" and p.held and p.species in taken
    )
    if held:
        raise ConfigError(
            f"experiment: a replacement leaves held places as they are, so {held}, which the "
            "assemblies take up, could never be washed out: declare it finite (FR-20's Q3)"
        )
    transfer._refuse_above_c_ext(world, finite, pool)
    return division.Schedule(index, "replacement", None, times, None, None, None, pool)


def removed_and_supplied(world, old, new):
    """({place: count} of the old pool's finite places, the same of the fresh pool's)."""
    names = [(i, p.name) for i, p in enumerate(world.places) if p.phase == "pool" and not p.held]
    return ({name: int(old[i]) for i, name in names}, {name: int(new[i]) for i, name in names})


CONTRACT = {
    "trigger": "a declared replacement time; same-time events in schedule-index order",
    "draw": "none: the schedule's stream (domain 6, its declared index) is never drawn",
    "keep": "every living assembly, as it stands: its places, key, sub-lineage and life",
    "pool": "the finite pool places take the declared composition; held places, c_ext and the "
    "pool's volume are unchanged; the fresh pool's solutes may not exceed c_ext",
    "booking": "the sink takes F of the old pool; the schedule's work column takes F of the fresh "
    "pool (source:replacement/<index>)",
}

OPERATOR = operator_registry.BUILTIN.register(
    AssemblyOperator(
        POOL_REPLACEMENT,
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ASSEMBLY_WASHOUT_DESIGN.md (FR-20, approved by the user in D240); "
            "docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.2d item 6 (the transfer's pool step)",
            "the exterior of an assembly population replaced at a declared time, every assembly "
            "kept, the exchange booked as schedule work and a sink",
            "no numbers taken",
            ("the replacement's own dissipation is not modelled",),
        ),
        test="tests/unit/test_assembly_lineages_v2_replacement.py::"
        "test_a_replacement_keeps_every_slot_and_replaces_the_pool",
        reads="the pool's finite places",
        writes="the pool's finite places",
        energy_role="work: the fresh pool's F (its schedule); sink: the old pool's F",
        rules={"keep": ["every living assembly, as it stands"]},
        stream="none: the schedule's stream is reserved by its index and never drawn",
        contract=CONTRACT,
    )
)
DECLARATION = OPERATOR.record()
assert OPERATOR.operator_id == POOL_REPLACEMENT
