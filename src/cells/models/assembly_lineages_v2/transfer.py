"""cells.operator.serial_transfer@1: a population's serial transfer at declared times (OL2 milestone 3;
docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §2.6; the design note's §0.2d item 6).

The experiment declares `{index, kind: transfer, times_s, K_keep, fresh_pool}`: fresh_pool gives one
count per finite pool place, in place order. At each time the transfer draws one uniform per living
assembly, in slot order, each its own draw on the schedule's stream (domain 6, its index), and keeps
the K_keep smallest, ties by slot (a uniform sample without replacement; all of them if fewer
live). It draws even when every assembly is kept. Kept assemblies keep their slots; the rest end
`removed` and their slots free. The pool's finite places are replaced by the fresh composition (the
held places and c_ext are unchanged); the fresh pool's solutes may not exceed c_ext (§0.2c rule 6).

Booking: before, F = F_kept + F_removed + F(old pool); after, F = F_kept + F(fresh pool). The sink
takes F_removed + F(old pool), and the schedule's work column takes F(fresh pool), paid by
source:transfer/<index>; so the books close.
"""

import numpy as np

from cells.definitions.specs import ConfigError, bounded_integer, finite_number
from cells.models.assembly_lineages_v2 import MODEL_ID, streams
from cells.models.assembly_lineages_v2.interfaces import AssemblyOperator
from cells.modules import Citation
from cells.registry import operators as operator_registry

SERIAL_TRANSFER = "cells.operator.serial_transfer@1"
KEYS = {"index", "kind", "times_s", "K_keep", "fresh_pool"}


def parse(entry, world):
    from cells.models.assembly_lineages_v2 import division

    if world.population is None:
        raise ConfigError("experiment: a transfer needs a population (execution mode population)")
    if set(entry) != KEYS:
        raise ConfigError(f"experiment: a transfer's keys are {sorted(KEYS)}")
    index = bounded_integer(entry["index"], "experiment: schedule index", minimum=0)
    times = entry["times_s"]
    if type(times) is not list or not times:
        raise ConfigError("experiment: a transfer's times_s is a non-empty list")
    times = tuple(finite_number(t, "experiment: a transfer time", positive=True) for t in times)
    if any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError("experiment: a transfer's times_s are strictly increasing")
    keep = bounded_integer(entry["K_keep"], "experiment: K_keep", minimum=1)
    finite = [i for i, p in enumerate(world.places) if p.phase == "pool" and not p.held]
    fresh = entry["fresh_pool"]
    if type(fresh) is not list or len(fresh) != len(finite):
        raise ConfigError(
            f"experiment: fresh_pool gives one count per finite pool place, in place order: "
            f"{[world.places[i].name for i in finite]}"
        )
    fresh = tuple(bounded_integer(c, "experiment: fresh_pool", minimum=0) for c in fresh)
    _refuse_above_c_ext(world, finite, fresh)
    return division.Schedule(index, "transfer", None, times, None, None, keep, fresh)


def _refuse_above_c_ext(world, finite, fresh):
    """§0.2c rule 6: the fresh pool's solutes may not exceed c_ext."""
    from cells.models.assembly_lineages_v2 import lumen

    if world.conventions.lumen_volume != "osmotic":
        return
    volume = world.volume("pool")
    held = sum(p.held_mM for p in world.places if p.phase == "pool" and p.held)
    solutes = sum(fresh) / (lumen.AVOGADRO * volume) * 1e3 + held  # mM
    c_ext = lumen.outside_mM(world)
    if solutes > c_ext:
        raise ConfigError(
            f"experiment: the fresh pool's solutes, {solutes:.6g} mM, exceed c_ext, {c_ext:.6g} mM "
            "(§0.2c rule 6)"
        )


def fresh_vector(world, schedule, capacity):
    """The fresh pool as a [capacity] state of the pool's finite places."""
    finite = [i for i, p in enumerate(world.places) if p.phase == "pool" and not p.held]
    out = np.zeros(capacity, dtype=np.int64)
    out[finite] = schedule.fresh
    return out


def replaced_pool(world, schedule, pool):
    """The pool after a transfer or a replacement (replacement.py): its finite places take the
    schedule's composition, its held places stay."""
    finite = np.zeros(pool.size, dtype=bool)
    finite[[i for i, p in enumerate(world.places) if p.phase == "pool" and not p.held]] = True
    return np.where(finite, fresh_vector(world, schedule, pool.size), pool)


def sample(base_key, schedule, counter, living, keep):
    """(kept slots, draws [(index, counter, u, "transfer", nan)], the next counter): one uniform
    per living slot, in slot order, each its own draw; the `keep` smallest, ties by slot."""
    key = streams.stream_key_data(base_key, schedule.index, "schedule")
    draws, values = [], []
    for slot in living:
        u = float(np.asarray(streams.uniforms(key, counter, 1))[0])
        draws.append((schedule.index, counter, u, "transfer", float("nan")))
        values.append((u, slot))
        counter += 1
    kept = sorted(slot for _, slot in sorted(values)[:keep])
    return kept, draws, counter


CONTRACT = {
    "trigger": "a declared transfer time; same-time events in schedule-index order",
    "draw": "one uniform per living assembly, in slot order, each its own draw on the schedule's "
    "stream (domain 6, its declared index) at its counter; it draws even when every assembly is "
    "kept",
    "keep": "the K_keep smallest uniforms, ties by slot: a uniform sample without replacement; all "
    "of them if fewer live",
    "slots": "kept assemblies keep their slots; the removed end `removed` and their slots free",
    "pool": "the finite pool places take the declared fresh composition; held places and c_ext are "
    "unchanged; the fresh pool's solutes may not exceed c_ext",
    "booking": "the sink takes F of the removed vesicles and of the old pool; the schedule's work "
    "column takes F of the fresh pool (source:transfer/<index>)",
}

OPERATOR = operator_registry.BUILTIN.register(
    AssemblyOperator(
        "cells.operator.serial_transfer@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §2.6; docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.2d "
            "item 6 (serial transfer, the shared pool's bottleneck)",
            "a uniform sample of K_keep living assemblies and a fresh pool, booked as schedule "
            "work",
            "no numbers taken",
            ("the transfer's own dissipation is not modelled",),
        ),
        test="tests/unit/test_assembly_lineages_v2_population.py::"
        "test_a_transfer_keeps_a_uniform_sample_and_refreshes_the_pool",
        reads="the living slots, in slot order",
        writes="the slots kept and removed; the pool's finite places",
        energy_role="work: the fresh pool's F (its schedule); sink: the removed vesicles' and the "
        "old pool's F",
        rules={"keep": ["the K_keep smallest uniforms, ties by slot"]},
        stream="schedule: domain 6 by the schedule's declared index, one draw per living assembly",
        contract=CONTRACT,
    )
)
DECLARATION = OPERATOR.record()
