"""cells.operator.size_threshold_division@1: division when a join brings the membrane to a size (OL6 S7).

The design is the OL6 design note's §6.8 (G2; tag ol6-design-note-2026-11-22, D304), and its
interface contract is Protocol G's §3 (tag ol6-protocol-g-registered-2026-11-23), fixed before this
was written. It is @1's cells.operator.size_threshold_fission@1 (assembly_lineages/fission.py) with the same
draw layout, partition, continuation and keys, in version 2's worlds. Its first users are Protocol
G's scope 2 (the GARD limit through 50 fissions), OL9's ladder from the GARD limit, and Syn3A's
F14 (a state-triggered division with a stochastic partition).

**The world** declares
`division = {law: cells.operator.size_threshold_division@1, size, partition: {rule: exact_fraction,
fraction}, continuation: first}`, in a single lineage.

**The trigger.** A committed event that moves one molecule into the membrane and brings the
membrane's count N to `size`. Every step of such a world changes N by at most one molecule (the
parse refuses others), so the boundary is exact: there is no overshoot and nothing is trimmed. A
daughter is never born at the size, since floor(f N) < N, so no division waits at a birth.

**The draw.** Domain 2 (partition), keyed by the parent's carrier key, at counter 0 (a parent
divides once). The occupied places are listed by type in declared order, the membrane's places in
place order: places 0 .. n_0 − 1 hold the first membrane place's species, the next n_1 the
second's, and so on. Place k takes the k-th uniform, and only the first N are read
(streams.block). Under JAX's partitionable threefry, which every run of the family requires, they
are the first N of any longer draw at the same address, @1's draw of molecule_capacity uniforms
among them.

**The partition** (`exact_fraction`, fraction f). Rank the places by u ascending, ties by place.
The first floor(f N), computed in float64 as @1's take is, go to the first daughter, and the second
daughter is the parent less the first. So no molecule is made or lost.

**Continuation and keys** (`first`; keys.py's rule). Both daughters take keys from the parent's
counter, `s:c` and `s:c+1`, with the first daughter the lower, and the counter moves to `s:c+2`. The
first daughter is followed: it continues the counter and becomes the slot's occupant. Its event
stream (domain 1, its key) starts at counter 0, its age. The division takes no time: the next
event's wait is drawn from the daughter's stream, from the trigger's time. The second daughter
leaves for the sink (sink:discard).

**The booking.** The work w = F_m(first) + F_m(second) − F_m(parent) is from an unmodelled agent
(signed; source:unmodelled_agent), with F_m(x) the membrane's own part of F: F less F with the
membrane emptied, so the pool's part cancels. The sink takes F_m(second). So
F(after) − F(before) = w − F_m(second), and the books close.

**The device** (`program`). The kernel's event runs unchanged. Each lane carries its division flag
beside it, as OL6 S4's device clock is carried, so kernel.Lane, Structure and Layout are untouched.
- A trigger raises the flag.
- A lane whose flag is up passes through the rest of its chunk unchanged, its events not
  committed.
- The host divides each flagged lane after the chunk (runner.py), then lowers the flag.

A trigger that is also the event guard's last event divides, and the lineage then ends
`event_limit`.

**Version 1 refuses:**
- a geometry (D2, cells.operator.shear_fission@1, is the physical division);
- finite lumen places;
- a step that changes N by more than one molecule;
- a founder at or above the size;
- floor(f size) < 1;
- a size above the molecule capacity;
- population mode, schedules and the diagnostic record;
- the deterministic representation (cells.assembly_representation.rate_equations@1).
"""

import functools
import math
from dataclasses import dataclass

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError, bounded_integer, finite_number
from cells.models.assembly_lineages_v2 import MODEL_ID, SIZE_THRESHOLD_DIVISION, kernel, streams
from cells.models.assembly_lineages_v2 import world as world_rules
from cells.models.assembly_lineages_v2.interfaces import AssemblyOperator
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import operators as operator_registry

RULES = {"exact_fraction": "fraction"}
CONTINUATIONS = ("first",)
KEYS = {"law", "size", "partition", "continuation"}
MAX_SIZE = 2**20  # @1's (fission.py)
DAUGHTERS = 2

CONTRACT = {  # Protocol G §3's interface contract, in the operator's words (a run record's).
    "trigger": "a committed event that moves one molecule into the membrane and brings its count "
    "N to `size` (exact: every step changes N by at most one molecule); a daughter is never born "
    "at the size (floor(f N) < N)",
    "places": "the occupied membrane places listed by type in declared order (the membrane's "
    "places in place order): places 0 .. n_0 - 1 hold the first membrane place's species, the next "
    "n_1 the second's, and so on; N places",
    "draw": "domain 2 (partition), keyed by the parent's carrier key, at counter 0; place k takes "
    "the k-th uniform; only the first N are read (under JAX's partitionable threefry, the first N "
    "of any longer draw at the same address, @1's draw of molecule_capacity uniforms among them)",
    "exact_fraction": "take = floor(f * N) in float64; rank the places by u ascending, ties by "
    "place; the first `take` go to the first daughter",
    "second_daughter": "the parent less the first daughter",
    "continuation": "first: the first daughter is followed; the second leaves for the sink",
    "keys": "the daughters take s:c and s:c+1 from the parent's counter, the first the lower; the "
    "followed one continues the counter and becomes the slot's occupant; its event stream (domain "
    "1, its key) starts at counter 0, its age (keys.py's rule, as @1's)",
    "clock": "the division takes no time: the next event's wait is drawn from the daughter's "
    "stream from the trigger's time; no draw is discarded",
    "booking": "work = F_m(first) + F_m(second) - F_m(parent), from an unmodelled agent, signed; "
    "the sink takes F_m(second); F_m(x) is F less F with the membrane emptied (the pool's part "
    "cancels)",
    "event_limit": "a trigger that is also the event guard's last event divides, and the lineage "
    "then ends event_limit",
}

OPERATOR = operator_registry.BUILTIN.register(
    AssemblyOperator(
        "cells.operator.size_threshold_division@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md §6.8 (G2); docs/OL6_PROTOCOL_G.md §3 "
            "(its interface contract); @1's cells.operator.size_threshold_fission@1 (Plastic Heredity "
            "preprint v5.0, Appendix F, contract T2-02; Zenodo 10.5281/zenodo.22143269)",
            "size-triggered division with an exact random partition, floor(f N) to the first "
            "daughter, in version 2's worlds",
            "no numbers taken",
            (
                "single-molecule membrane steps only (the trigger is exact)",
                "no geometry, no lumen and a single lineage in version 1",
            ),
        ),
        test="tests/unit/test_assembly_lineages_v2_size_division.py::"
        "test_each_division_keeps_protocol_g_s_contract",
        reads="the membrane's count N (current) and its counts",
        writes="the slot's composition: the followed (first) daughter replaces the parent",
        energy_role="work: the split's change in F, from an unmodelled agent (signed); the sink "
        "takes the second daughter's F_m",
        rules={"partition": sorted(RULES), "continuation": list(CONTINUATIONS)},
        stream="partition: domain 2 by the parent's carrier key, counter 0, one uniform per "
        "occupied membrane place (the first N)",
        contract=CONTRACT,
    )
)
DECLARATION = OPERATOR.record()  # As a run record states it (records.py).


# ------------------------------------------------------------------ the declaration (parse)


def membrane_changes(world):
    """{step id: the forward's change of the membrane's count}, from the declared sides."""
    phase = {p.name: p.phase for p in world.places}
    out = {}
    for step in world.steps:
        gained = sum(n for name, n in step.products if phase[name] == world_rules.MEMBRANE)
        lost = sum(n for name, n in step.reactants if phase[name] == world_rules.MEMBRANE)
        out[step.id] = gained - lost
    return out


def parse_data(raw, world):
    """The world's division block naming this law (spec.py dispatches on the law)."""
    where = f"world: division ({SIZE_THRESHOLD_DIVISION})"
    if set(raw) != KEYS:
        raise ConfigError(
            f"{where}: missing={sorted(KEYS - set(raw))}, unknown={sorted(set(raw) - KEYS)}"
        )
    size = bounded_integer(raw["size"], f"{where}: size", minimum=2, maximum=MAX_SIZE)
    partition = raw["partition"]
    if not isinstance(partition, dict) or partition.get("rule") not in RULES:
        raise ConfigError(f"{where}: the partition rule is one of {sorted(RULES)}")
    if set(partition) != {"rule", "fraction"}:
        raise ConfigError(f"{where}: the exact_fraction partition is {{rule, fraction}}")
    fraction = finite_number(partition["fraction"], f"{where}: fraction", positive=True)
    if not fraction < 1:
        raise ConfigError(f"{where}: fraction lies strictly between 0 and 1")
    if raw["continuation"] not in CONTINUATIONS:
        raise ConfigError(f"{where}: continuation is {', '.join(CONTINUATIONS)} in version 1")
    if world.geometry is not None:
        raise ConfigError(
            f"{where}: refused with a geometry ({world.geometry[0]}) in version 1: a vesicle's "
            "physical division is cells.operator.shear_fission@1's (D2; the OL6 design note's §6.8)"
        )
    lumen = [p.name for p in world.places if p.phase == world_rules.LUMEN and not p.held]
    if lumen:
        raise ConfigError(
            f"{where}: refused with lumen places ({', '.join(lumen)}) in version 1: the partition "
            "splits the membrane's molecules"
        )
    for step_id, moved in membrane_changes(world).items():
        if abs(moved) > 1:
            raise ConfigError(
                f"{where}: step {step_id} changes the membrane's count by {moved}: the trigger is "
                "exact only when every step moves at most one molecule into or out of the membrane"
            )
    membrane = sum(
        c for p, c in zip(world.places, world.founder, strict=True)
        if p.phase == world_rules.MEMBRANE
    )  # fmt: skip
    if membrane >= size:
        raise ConfigError(
            f"{where}: the founder's membrane holds {membrane}, at or above the size {size}: the "
            "trigger is a join that brings N to the size"
        )
    if math.floor(fraction * float(size)) < 1:
        raise ConfigError(
            f"{where}: floor(fraction * size) = 0: the first daughter, the followed one, holds no "
            "molecule"
        )
    return {"size": size, "rule": "exact_fraction", "fraction": fraction, "continuation": "first"}


def data_to_dict(data):
    return {
        "law": SIZE_THRESHOLD_DIVISION,
        "size": data["size"],
        "partition": {"rule": data["rule"], RULES[data["rule"]]: data["fraction"]},
        "continuation": data["continuation"],
    }


def cross_checks(world, experiment, execution):
    """The experiment's and the execution's refusals (spec.py, after both parse)."""
    where = f"world: division ({SIZE_THRESHOLD_DIVISION})"
    size = world.size_division["size"]
    if size > execution.molecule_capacity:
        raise ConfigError(
            f"{where}: the size {size} is above molecule_capacity {execution.molecule_capacity}: "
            "every count is at most the capacity, the log-factorial table's last index"
        )
    if experiment.schedules:
        raise ConfigError(
            f"{where}: schedules are refused beside it in version 1 (a stop's operators and a "
            "division's are not ordered yet)"
        )
    if experiment.diagnostic:
        raise ConfigError(
            f"{where}: the diagnostic record is refused beside it in version 1 (trace and "
            "uniforms record its events and draws)"
        )
    if experiment.tension_holds:
        raise ConfigError(f"{where}: tension holds are refused beside it in version 1")


# ------------------------------------------------------------------ the split (host)


def take(fraction, n):
    """floor(f N) in float64, @1's expression (fission.split)."""
    return int(np.floor(np.float64(fraction) * np.float64(n)))


def split(counts, uniforms, fraction):
    """The first daughter's counts [G] (int64): counts [G], the parent's membrane places in place
    order; uniforms, the N = sum(counts) uniforms, place k's the k-th."""
    counts = np.asarray(counts, dtype=np.int64)
    n = int(counts.sum())
    u = np.asarray(uniforms, dtype=np.float64)
    if u.shape != (n,):
        raise ValueError(f"A split reads one uniform per occupied place: {n}, not {u.shape}")
    kind = np.repeat(np.arange(counts.size), counts)  # place k's type
    order = np.argsort(u, kind="stable")  # ascending, ties by place
    return np.bincount(kind[order[: take(fraction, n)]], minlength=counts.size).astype(np.int64)


def membrane_places(world):
    """The finite membrane places, in place order (the partition's list)."""
    return np.asarray(
        [i for i, p in enumerate(world.places) if p.phase == world_rules.MEMBRANE and not p.held],
        dtype=np.int64,
    )


def uniforms(base_key, parent, n):
    """The partition's N uniforms: domain 2, the parent's key, counter 0 (streams.block, the
    plain draw bit for bit)."""
    key = streams.stream_key_data(base_key, int(parent), "partition")
    return np.asarray(streams.block(key, 0, int(n)), dtype=np.float64)


@dataclass(frozen=True)
class Division:
    """One division of the single lineage (a row of its fission table)."""

    time: float
    event: int  # the trigger's index among the lineage's committed events, from 1
    parent: int  # carrier key
    generation: int  # the parent's
    size: int  # N
    parent_counts: np.ndarray  # [P]
    daughters: np.ndarray  # [2, P]: each daughter's membrane with the pool as it is
    keys: tuple  # (first, second)
    work: float  # k_BT
    sink: float  # k_BT, F_m(second)
    uniforms: np.ndarray  # [N]


def divide(world, base_key, counts, parent, generation, next_key, time, event, energy):
    """The division of the assembly with `counts` ([P]) at its trigger; energy(counts): F_m of the
    membrane in a [P] state (k_BT). Returns a Division; the followed daughter is the first."""
    data = world.size_division
    counts = np.array(counts, dtype=np.int64)  # a copy: the caller's lane row is overwritten next
    membrane = membrane_places(world)
    n = int(counts[membrane].sum())
    if n != data["size"]:
        raise AssertionError(f"A division at N = {n}, not the size {data['size']}: a fault")
    drawn = uniforms(base_key, parent, n)
    first = split(counts[membrane], drawn, data["fraction"])
    daughters = np.repeat(counts[None, :], DAUGHTERS, axis=0)
    daughters[0, membrane] = first
    daughters[1, membrane] = counts[membrane] - first
    f_first, f_second = energy(daughters[0]), energy(daughters[1])
    work = math.fsum((f_first, f_second, -energy(counts)))
    return Division(time=time, event=event, parent=parent, generation=generation, size=n,
                    parent_counts=counts, daughters=daughters,
                    keys=(next_key, next_key + 1), work=work, sink=f_second,
                    uniforms=drawn)  # fmt: skip


# ------------------------------------------------------------------ the device's flag


def _select(flag, new, old):
    return jax.tree_util.tree_map(lambda a, b: jnp.where(flag, a, b), new, old)


def event(lane, due, layout, size, structure):
    """One event of one single-lineage lane with its division flag: kernel.event, unchanged. A lane
    whose flag is up passes through as it is (its event not committed); a committed event that
    moves a molecule into the membrane and brings N to `size` raises the flag."""
    after, out = kernel.event(lane, layout, structure)
    code = out.channel
    step = jnp.clip(jnp.abs(code) - 1, 0, structure.steps - 1)
    moved = jnp.where(code > 0, layout.step_moves[step], -layout.step_moves[step])
    reached = after.totals[kernel.MEMBRANE] == size
    trigger = out.committed & (moved > 0) & reached & ~due
    lane_after = _select(due, lane, after)
    committed = out.committed & ~due
    out = out._replace(
        committed=committed,
        channel=jnp.where(committed, code, 0),
        time=lane_after.time,
        heat=lane_after.heat,
        heat_magnitude=lane_after.heat_magnitude,
        work=lane_after.work,
        work_magnitude=lane_after.work_magnitude,
    )
    return lane_after, due | trigger, out


@functools.cache
def program(structure):
    """`advance(lanes, due, layout, sizes)`: a chunk of events, as kernel.program's, carrying each
    lane's division flag beside it (sizes: each lane's declared size)."""

    def advance(lanes, due, layout, sizes):
        def body(carry, _):
            la, du = carry

            def one(a, d, lo, s):
                return event(a, d, lo, s, structure)

            la, du, out = jax.vmap(one)(la, du, layout, sizes)
            return (la, du), out

        (lanes, due), out = jax.lax.scan(body, (lanes, due), None, length=structure.chunk)
        return lanes, due, out

    return jax.jit(advance)


# ------------------------------------------------------------------ records (host)


def fission_arrays(divisions, places, size, with_uniforms):
    """The fission table: one row per division, in order (records.py declares the arrays)."""
    count = len(divisions)
    out = {
        "fission_time": np.asarray([d.time for d in divisions], dtype=np.float64),
        "fission_event": np.asarray([d.event for d in divisions], dtype=np.int64),
        "fission_parent": np.asarray([d.parent for d in divisions], dtype=np.int64),
        "fission_parent_generation": np.asarray([d.generation for d in divisions],
                                                dtype=np.int64),  # fmt: skip
        "fission_size": np.asarray([d.size for d in divisions], dtype=np.int64),
        "fission_parent_counts": np.asarray(
            [d.parent_counts[:places] for d in divisions], dtype=np.int64
        ).reshape(count, places),
        "fission_daughters": np.asarray([d.keys for d in divisions], dtype=np.int64).reshape(
            count, DAUGHTERS
        ),
        "fission_daughter_counts": np.asarray(
            [d.daughters[:, :places] for d in divisions], dtype=np.int64
        ).reshape(count, DAUGHTERS, places),
        "fission_followed": np.zeros(count, dtype=np.int64),
        "fission_work_kT": np.asarray([d.work for d in divisions], dtype=np.float64),
        "fission_discarded_kT": np.asarray([d.sink for d in divisions], dtype=np.float64),
    }
    if with_uniforms:
        out["partition_uniforms"] = np.asarray(
            [d.uniforms for d in divisions], dtype=np.float64
        ).reshape(count, size)
    return out


def lives(divisions, world, status, end_time):
    """The lives, as cells.relations@2's Life fields (one dict each, in birth order): the founder
    0:0, and at each division its parent's end (divided) and its two daughters (the first followed
    in the slot, the second not followed). The last occupant ends extinct, or censored at the run's
    end. share: a daughter's membrane molecules over its parent's."""
    from cells.models.assembly_lineages import keys

    membrane = membrane_places(world)
    founder = keys.carrier_id(0)
    current = {"id": founder, "key": 0, "lineage": 0, "birth_time": 0.0,
               "birth_kind": "founder", "generation": 0, "root": founder, "declared_by": MODEL_ID,
               "slot": "slot:0", "parent": "", "share": float("nan"), "donor": "",
               "predecessor": "", "birth_event": ""}  # fmt: skip
    out = []
    for r, d in enumerate(divisions):
        event = f"event:fission/{r}"
        out.append(current | {"end_time": d.time, "end_reason": "divided", "end_event": event})
        sizes = d.daughters[:, membrane].sum(axis=1)
        followed = None
        for j, key in enumerate(d.keys):
            life = {"id": keys.carrier_id(key), "key": int(key), "birth_time": d.time,
                    "birth_kind": "division", "generation": current["generation"] + 1,
                    "root": founder, "declared_by": SIZE_THRESHOLD_DIVISION,
                    "parent": current["id"], "share": float(sizes[j] / sizes.sum()), "donor": "",
                    "predecessor": "", "birth_event": event}  # fmt: skip
            if j == 0:
                followed = life | {"lineage": 0, "slot": "slot:0"}
            else:
                out.append(life | {"lineage": -1, "slot": "", "end_time": d.time,
                                   "end_reason": "not_followed", "end_event": event})  # fmt: skip
        current = followed
    reason = "extinct" if status == "extinct" else "censored"
    out.append(current | {"end_time": end_time, "end_reason": reason, "end_event": ""})
    return sorted(out, key=lambda life: (life["birth_time"], life["key"]))
