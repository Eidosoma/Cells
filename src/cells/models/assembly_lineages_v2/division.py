"""cells.operator.shear_fission@1: division at shear events in a single lineage (OL3 milestone 1).

The lead's rulings are §0.2c rules 9–13 and §0.2d items 6, 7, 9 and 10
(docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §2).

**The world** declares `division = {law: cells.operator.shear_fission@1, continuation: first | uniform}`,
with an optional `critical_stress_Pa = {value, provenance}`. Division needs a geometry and an
osmotic lumen: a daughter's own volume, the v test, the lumen's terms in the shear work and lysis at
birth all follow from them. The experiment declares the shear schedules,
`[{index, kind: shear, k, times_s, stress_Pa?}]`: k is declared per schedule (rule 11), and a stress
is given exactly when the world declares a critical stress. Declared times only in this milestone.

**An attempt** (item 10.2), at a schedule time, on the assembly alive at its start (item 10.1):
1. the stress test (when declared), then v ≤ k^(−1/2), that is 36πkV² ≤ A³ (V in m³, A in m²);
   an assembly that fails either draws nothing;
2. the draw: one block of N + k + N_L uniforms from the parent's fission stream (domain 2, its
   carrier key, the counter at its attempts that drew, from 0);
3. the split: rule 9's C3x for the membrane, then rule 10's multinomial for the lumen;
4. the floor test: every daughter at or above W_floor, else refused and recorded, the parent kept;
5. the fission: the daughters take the parent's next keys in daughter order, one is followed by the
   continuation rule (`first`, or `uniform` from the parent's continuation stream, domain 3,
   counter 0), and the others leave the world for the sink.

**The booking** (item 7): the shear work is w = Σ_j F_v(d_j) − F_v(parent), with F_v a vesicle's
own part of F (its membrane, lumen and closure cost), so it holds (k − 1)·C_close; the sink takes
the unfollowed daughters' F_v. A daughter beyond σ_max lyses at birth (item 10.3): if it is the
followed one the lineage ends lysed, booked as a lysis. An unfollowed daughter leaves for the sink
whether or not it would lyse; its flag is recorded (a case the rulings do not state: asked).

`split` is one vectorised host function, used by the run and by the partition probe alike.
"""

import math
from dataclasses import dataclass

import numpy as np

from cells.definitions.specs import ConfigError, bounded_integer, finite_number
from cells.models.assembly_lineages_v2 import MODEL_ID, SHEAR_FISSION, geometry, lumen, streams
from cells.models.assembly_lineages_v2.interfaces import AssemblyOperator
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import operators as operator_registry

CONTINUATIONS = ("first", "uniform")
OUTCOMES = ("split", "refused_stress", "refused_volume", "refused_floor")
MAX_K = 16


def parse_data(raw, world):
    """The world's division block (spec.py calls it after the geometry is attached)."""
    if not isinstance(raw, dict) or raw.get("law") != SHEAR_FISSION:
        raise ConfigError(f"world: division names its law, {SHEAR_FISSION}")
    allowed, required = {"law", "continuation", "critical_stress_Pa"}, {"law"}
    if not required <= set(raw) <= allowed:
        raise ConfigError(
            f"world: division: missing={sorted(required - set(raw))}, "
            f"unknown={sorted(set(raw) - allowed)}"
        )
    if world.geometry is None or world.conventions.lumen_volume != "osmotic":
        raise ConfigError(
            "world: division needs a geometry and an osmotic lumen: a daughter's own volume, the "
            "v test and lysis at birth follow from them (OL3; §0.2e rule 2)"
        )
    if raw.get("continuation", CONTINUATIONS[0]) not in CONTINUATIONS:
        raise ConfigError(f"world: division: continuation is one of {', '.join(CONTINUATIONS)}")
    critical = None
    if "critical_stress_Pa" in raw:
        entry = raw["critical_stress_Pa"]
        if not isinstance(entry, dict) or set(entry) != {"value", "provenance"}:
            raise ConfigError("world: division: critical_stress_Pa is {value, provenance}")
        value = finite_number(entry["value"], "world: division: critical_stress_Pa", positive=True)
        if not isinstance(entry["provenance"], str) or not entry["provenance"]:
            raise ConfigError("world: division: critical_stress_Pa states its provenance")
        critical = (value, entry["provenance"])
    # A single lineage declares its continuation; a population, where every daughter lives,
    # declares none (checked against the mode with the definition: spec.py).
    return {"continuation": raw.get("continuation"), "critical_stress_Pa": critical}


def data_to_dict(data):
    out = {"law": SHEAR_FISSION}
    if data["continuation"] is not None:
        out["continuation"] = data["continuation"]
    if data["critical_stress_Pa"] is not None:
        value, provenance = data["critical_stress_Pa"]
        out["critical_stress_Pa"] = {"value": value, "provenance": provenance}
    return out


@dataclass(frozen=True)
class Schedule:
    """A declared schedule: its index (the carrier word of its stream, domain 6), its kind, k, and
    its times: declared (times), or a Poisson process of rate `rate` (1/s) drawn per run."""

    index: int
    kind: str  # "shear", "transfer", "replacement" (FR-20) or "withdrawal" (FR-35)
    k: int | None
    times: tuple | None
    rate: float | None
    stress: float | None
    keep: int | None = None  # a transfer's K_keep
    fresh: tuple | None = None  # a transfer's fresh pool, a replacement's pool or a withdrawal's
    # buffer (its counts in the withdrawn volume): one count per finite pool place
    fraction: float | None = None  # a withdrawal's fraction f, in (0, 1) (FR-35)


def parse_schedules(raw, world):
    """The experiment's shear schedules (Schedule), by index."""
    if type(raw) is not list or not raw:
        raise ConfigError("experiment: schedules is a non-empty list")
    critical = None if world.division is None else world.division["critical_stress_Pa"]
    out, seen = [], set()
    for entry in raw:
        if isinstance(entry, dict) and entry.get("kind") in ("transfer", "replacement",
                                                             "withdrawal"):  # fmt: skip
            from cells.models.assembly_lineages_v2 import replacement, transfer, withdrawal

            module = {"transfer": transfer, "replacement": replacement,
                      "withdrawal": withdrawal}[entry["kind"]]  # fmt: skip
            schedule = module.parse(entry, world)
            if schedule.index in seen:
                raise ConfigError("experiment: schedule indices are unique")
            seen.add(schedule.index)
            out.append(schedule)
            continue
        if not isinstance(entry, dict) or entry.get("kind") != "shear":
            raise ConfigError(
                "experiment: a schedule is {index, kind: shear, k, times_s, ...}, "
                "{index, kind: transfer, times_s, K_keep, fresh_pool}, "
                "{index, kind: replacement, times_s, pool} or "
                "{index, kind: withdrawal, times_s, fraction, buffer}"
            )
        if world.division is None:
            raise ConfigError("experiment: a shear schedule needs the world's division block")
        timing = {"poisson_rate_per_s"} if "poisson_rate_per_s" in entry else {"times_s"}
        keys = {"index", "kind", "k"} | timing | ({"stress_Pa"} if critical else set())
        if set(entry) != keys:
            raise ConfigError(
                f"experiment: schedule keys are {sorted(keys)} (times_s or poisson_rate_per_s; a "
                "stress exactly when the world declares a critical stress)"
            )
        index = bounded_integer(entry["index"], "experiment: schedule index", minimum=0,
                                maximum=2**31 - 1)  # fmt: skip
        if index in seen:
            raise ConfigError("experiment: schedule indices are unique")
        seen.add(index)
        k = bounded_integer(entry["k"], "experiment: schedule k", minimum=2, maximum=MAX_K)
        times = rate = None
        if "times_s" in entry:
            times = entry["times_s"]
            if type(times) is not list or not times:
                raise ConfigError("experiment: a schedule's times_s is a non-empty list")
            times = tuple(
                finite_number(t, "experiment: a schedule time", positive=True) for t in times
            )
            if any(b <= a for a, b in zip(times, times[1:], strict=False)):
                raise ConfigError("experiment: a schedule's times_s are strictly increasing")
        else:
            rate = finite_number(
                entry["poisson_rate_per_s"], "experiment: poisson_rate_per_s", positive=True
            )
        stress = None
        if critical:
            stress = finite_number(entry["stress_Pa"], "experiment: schedule stress_Pa")
        out.append(Schedule(index, "shear", k, times, rate, stress))
    out.sort(key=lambda s: s.index)
    # FR-20: a replacement never shares a declared time with another stop, since cells.relations
    # has no order between same-time events (the lead's condition of 20 November).
    for s in out:
        if s.kind not in ("replacement", "withdrawal"):  # FR-35: a withdrawal stands alone too
            continue
        for other in out:
            shared = set(s.times) & set(other.times or ()) if other is not s else set()
            if shared:
                raise ConfigError(
                    f"experiment: {s.kind} {s.index} shares the time {min(shared)} s with "
                    f"schedule {other.index} ({other.kind}); relations have no order between "
                    f"same-time events, so a {s.kind} stands alone in time"
                )
    first = {}  # Two shear schedules never share a time: each attempt has one payer (19 November).
    for s in out:
        index = s.index
        for t in (s.times or ()) if s.kind == "shear" else ():
            if t in first:
                raise ConfigError(
                    f"experiment: shear schedules {first[t]} and {index} share the time {t} s; "
                    "each attempt has one payer"
                )
            first[t] = index
    return tuple(out)


def schedule_to_dict(schedules):
    out = []
    for s in schedules:
        if s.kind == "transfer":
            out.append({"index": s.index, "kind": s.kind, "times_s": list(s.times),
                        "K_keep": s.keep, "fresh_pool": list(s.fresh)})  # fmt: skip
            continue
        if s.kind == "replacement":
            out.append({"index": s.index, "kind": s.kind, "times_s": list(s.times),
                        "pool": list(s.fresh)})  # fmt: skip
            continue
        if s.kind == "withdrawal":  # FR-35
            out.append({"index": s.index, "kind": s.kind, "times_s": list(s.times),
                        "fraction": s.fraction, "buffer": list(s.fresh)})  # fmt: skip
            continue
        entry = {"index": s.index, "kind": s.kind, "k": s.k}
        if s.times is not None:
            entry["times_s"] = list(s.times)
        else:
            entry["poisson_rate_per_s"] = s.rate
        if s.stress is not None:
            entry["stress_Pa"] = s.stress
        out.append(entry)
    return out


def poisson_times(schedule, horizon, base_key):
    """A Poisson schedule's times at or before the horizon, and its draws [(index, counter, u,
    "gap", time)]: t_1 = -ln(u_0)/rate from t = 0, then t_(i+1) = t_i - ln(u_i)/rate, each gap its
    own draw on the schedule's stream (domain 6, its index), the gap past the horizon included
    (§0.2d items 6 and 10.4)."""
    key = streams.stream_key_data(base_key, schedule.index, "schedule")
    t, counter, times, draws = 0.0, 0, [], []
    while True:
        u = float(np.asarray(streams.uniforms(key, counter, 1))[0])
        t = t - math.log(u) / schedule.rate
        draws.append((schedule.index, counter, u, "gap", t))
        counter += 1
        if t > horizon:
            return tuple(times), draws
        times.append(t)


def timeline(schedules, horizon, base_key=None):
    """([(time, index, k, stress)] of every scheduled event at or before the horizon, in time
    order, same-time events in schedule-index order (§0.2d item 10.1); the schedules' draws)."""
    events, draws = [], []
    for s in schedules:
        times = s.times
        if times is None:
            times, drawn = poisson_times(s, horizon, base_key)
            draws += drawn
        events += [(t, s.index, s.k, s.stress) for t in times if t <= horizon]
    return sorted(events, key=lambda e: (e[0], e[1])), draws


# ------------------------------------------------------------------ the split (host, vectorised)


def c3x(species_counts, quanta, k, uniforms):
    """§0.2c rule 9. species_counts [G] and quanta [G] of the parent's membrane (declared order);
    uniforms: the block's first N + k values. Returns (blocks [k, G], pi [k], w_blocks [k]):
    block t goes to daughter pi[t]."""
    counts = np.asarray(species_counts, dtype=np.int64)
    weights = np.asarray(quanta, dtype=np.int64)
    n = int(counts.sum())
    species = np.repeat(np.arange(counts.size), counts)  # the list, by species in declared order
    u = np.asarray(uniforms[:n], dtype=np.float64)
    rank = np.argsort(u, kind="stable")  # ascending, ties by list position
    ranked = species[rank]
    prefix = np.concatenate(([0], np.cumsum(weights[ranked])))  # S_c, c = 0..N
    total = int(prefix[-1])
    cuts = [0]
    for t in range(1, k):
        gap = np.abs(k * prefix - t * total)
        gap[: cuts[-1]] = np.iinfo(np.int64).max  # c ≥ c_(t−1)
        cuts.append(int(np.argmin(gap)))  # the smallest such c (argmin's first)
    cuts.append(n)
    blocks = np.zeros((k, counts.size), dtype=np.int64)
    for t in range(k):
        blocks[t] = np.bincount(ranked[cuts[t] : cuts[t + 1]], minlength=counts.size)
    order = np.asarray(uniforms[n : n + k], dtype=np.float64)
    pi = np.argsort(order, kind="stable")  # ascending, ties by index
    return blocks, pi, blocks @ weights


def lumen_split(lumen_counts, pi, areas_m2, uniforms):
    """§0.2c rule 10: each lumen molecule (by species in declared order) goes to daughter pi[t] for
    the smallest t with u < Σ_(s ≤ t) p_pi(s), p_j = V_sph(A_j)/Σ V_sph, the last weight 1.
    Returns [k, G_L] counts by daughter."""
    counts = np.asarray(lumen_counts, dtype=np.int64)
    k = pi.size
    volumes = np.asarray(areas_m2, dtype=np.float64) ** 1.5
    p = volumes / volumes.sum()
    cumulative = np.cumsum(p[pi])
    cumulative[-1] = 1.0
    species = np.repeat(np.arange(counts.size), counts)
    u = np.asarray(uniforms, dtype=np.float64)
    t = np.searchsorted(cumulative, u, side="right")  # smallest t with u < cumulative[t]
    out = np.zeros((k, counts.size), dtype=np.int64)
    np.add.at(out, (pi[np.minimum(t, k - 1)], species), 1)
    return out


def split(membrane, quanta, lumen, k, q, uniforms):
    """The daughters of one attempt: ([k, G] membrane by daughter, [k, G_L] lumen by daughter),
    from its block of N + k + N_L uniforms (§0.2c rules 9 and 10)."""
    n = int(np.sum(membrane))
    blocks, pi, w_blocks = c3x(membrane, quanta, k, uniforms[: n + k])
    by_daughter = np.zeros_like(blocks)
    by_daughter[pi] = blocks
    areas = np.zeros(k, dtype=np.float64)
    areas[pi] = q * w_blocks.astype(np.float64) / 2.0
    return by_daughter, lumen_split(lumen, pi, areas, uniforms[n + k :])


def admitted_volume(volume_L, footprint, q, k):
    """v ≤ k^(−1/2), as 36πkV² ≤ A³ (V in m³, A in m²)."""
    volume = volume_L * 1e-3
    area = q * footprint / 2.0
    return 36.0 * math.pi * k * volume * volume <= area**3


CONTRACT = {
    "trigger": "a declared shear schedule time: the assembly alive at its start is tested; "
    "same-time events in schedule-index order (§0.2d item 10.1)",
    "order": "the stress test (when declared), then 36 pi k V^2 <= A^3; then one draw; the split; "
    "the floor test; the fission applied, or refused and recorded with the parent kept (§0.2d item "
    "10.2). An assembly failing the stress or v test neither draws nor advances its counter",
    "draw": "domain 2, the parent's carrier key, counter = its attempts that drew (from 0): a "
    "block of N + k + N_L uniforms, rule 9's N + k then rule 10's N_L",
    "c3x": "rank the membrane molecules (by species in declared order) by their uniforms, ties by "
    "list position; c_t the smallest c >= c_(t-1) minimising |k S_c - t W|; block t is ranked "
    "molecules c_(t-1)+1..c_t; the k further uniforms' argsort (ties by index) is pi, and block t "
    "goes to daughter pi(t) (§0.2c rule 9)",
    "lumen": "p_j = V_sph(A_j) / sum_l V_sph(A_l); a lumen molecule with uniform u goes to "
    "daughter pi(t) for the smallest t with u < sum_(s<=t) p_pi(s), the last cumulative weight 1 "
    "(§0.2c rule 10)",
    "keys": "the daughters take the lineage counter's next k keys in daughter order (keys.py's "
    "rule; single lineage: sub-lineage 0); the followed daughter becomes the slot's occupant and "
    "draws its own event stream (its key, domain 1) from counter 0 (§0.2d item 10.6)",
    "clock": "the draw that crosses a schedule time is discarded and counted: the occupant's next "
    "draw is at the next counter, its wait measured from the schedule time (§0.2d item 6)",
    "continuation": "first, or uniform: floor(u k) with u the continuation stream's draw at "
    "counter 0 (domain 3); the others leave for the sink",
    "booking": "shear work = sum_j F_v(d_j) - F_v(parent), F_v a vesicle's own F with its "
    "closure cost; the sink takes the unfollowed daughters' F_v; a followed daughter beyond "
    "sigma_max lyses at birth, booked as a lysis (§0.2d items 7 and 10.3)",
}

OPERATOR = operator_registry.BUILTIN.register(
    AssemblyOperator(
        "cells.operator.shear_fission@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §4, §0.2c rules 9-13, §0.2d items 6, 7 and 10; "
            "docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §2.1-§2.5 (division under shear, D2)",
            "geometric admission at shear events, a split at equal target areas, booked as work",
            "no numbers taken",
            (
                "equal target areas (k equal spheres) in the first worlds",
                "declared shear times in this version; Poisson times come with the shared pool",
            ),
        ),
        test="tests/unit/test_assembly_lineages_v2_division.py::"
        "test_c3x_and_the_lumen_split_are_rule_9_and_10_s_laws",
        reads="the assembly's counts, its footprint and its lumen volume (current)",
        writes="the slot's composition: the followed daughter replaces the parent",
        energy_role="work: the split's change in F, from the shear (its schedule)",
        rules={"continuation": list(CONTINUATIONS), "outcomes": list(OUTCOMES)},
        stream="fission: domain 2 by the parent's key; continuation: domain 3, counter 0",
        contract=CONTRACT,
    )
)
DECLARATION = OPERATOR.record()  # As a run record states it (records.py).


# ------------------------------------------------------------------ one attempt (host)


@dataclass(frozen=True)
class Attempt:
    """One shear event's attempt on one assembly (a row of the fission table)."""

    time: float
    schedule: int
    k: int
    parent: int  # carrier key
    counter: int  # its fission counter's draw, or -1 (not admitted: no draw)
    outcome: str  # OUTCOMES
    parent_counts: np.ndarray  # [P] the world's places
    daughters: np.ndarray  # [k, P]: each daughter's vesicle with the pool as it is (split only)
    keys: tuple  # the daughters' carrier keys, in daughter order (split only)
    followed: int  # the followed daughter, or -1
    lysed: tuple  # each daughter beyond sigma_max at birth (split only)
    shear_work: float  # k_BT, sum_j F_v(d_j) - F_v(parent) (split only)
    sink: float  # k_BT, the unfollowed daughters' F_v (split only)


def vesicle_places(world):
    """(membrane places, lumen places), each in place order (by species, in declared order)."""
    membrane = [i for i, p in enumerate(world.places) if p.phase == "membrane" and not p.held]
    inside = [i for i, p in enumerate(world.places) if p.phase == "lumen" and not p.held]
    return np.asarray(membrane, dtype=np.int64), np.asarray(inside, dtype=np.int64)


def block(base_key, parent, counter, size):
    """The attempt's uniforms: the parent's fission stream (domain 2) at its counter. They are
    drawn at the next power of two and cut (streams.block), the plain draw bit for bit, so a host
    draw compiles once per power of two rather than once per size."""
    key = streams.stream_key_data(base_key, int(parent), "partition")
    return np.asarray(streams.block(key, int(counter), int(size)), dtype=np.float64)


def attempt(world, counts, parent, counter, event, base_key, vesicle_f, next_key,
            free_slots=None):  # fmt: skip
    """Item 10.2's attempt on the assembly with `counts` ([P]) at a shear `event`
    (time, index, k, stress). counter: the parent's fission counter; vesicle_f(counts): F_v of the
    vesicle in a [P] state (k_BT, with its closure cost); next_key: the lineage counter's next key.
    Returns an Attempt."""
    time, index, k, stress = event
    counts = np.asarray(counts, dtype=np.int64)
    empty = np.zeros((0, counts.size), dtype=np.int64)
    refused = dict(time=time, schedule=index, k=k, parent=parent, parent_counts=counts,
                   daughters=empty, keys=(), followed=-1, lysed=(), shear_work=0.0,
                   sink=0.0)  # fmt: skip
    q = world.geometry[1]["area_quantum_m2"]
    quanta = geometry.place_quanta(world, counts.size)
    critical = world.division["critical_stress_Pa"]
    if critical is not None and not stress >= critical[0]:
        return Attempt(counter=-1, outcome="refused_stress", **refused)
    footprint = int(counts @ quanta)
    if not admitted_volume(lumen.host_volume_L(world, counts), footprint, q, k):
        return Attempt(counter=-1, outcome="refused_volume", **refused)
    if free_slots is not None and free_slots < k - 1:  # population: before the draw (item 10.2)
        return Attempt(counter=-1, outcome="slots_full", **refused)
    membrane, inside = vesicle_places(world)
    n, n_lumen = int(counts[membrane].sum()), int(counts[inside].sum())
    uniforms = block(base_key, parent, counter, n + k + n_lumen)
    by_membrane, by_lumen = split(
        counts[membrane], quanta[membrane], counts[inside], k, q, uniforms
    )
    daughters = np.repeat(counts[None, :], k, axis=0)
    daughters[:, membrane] = by_membrane
    daughters[:, inside] = by_lumen
    if np.any(daughters @ quanta < geometry.floor_quanta(world)):
        return Attempt(**{**refused, "counter": counter, "outcome": "refused_floor"})
    followed = 0 if free_slots is None else -1  # a population follows none: every daughter lives
    if world.division["continuation"] == "uniform":
        key = streams.stream_key_data(base_key, int(parent), "continuation")
        followed = int(np.floor(float(streams.uniforms(key, 0, 1)[0]) * k))
    sigma_max = world.geometry[1]["sigma_max_N_per_m"][0]
    lysed = tuple(bool(lumen.host_tension(world, d) > sigma_max) for d in daughters)
    energies = [vesicle_f(d) for d in daughters]
    work = math.fsum(energies) - vesicle_f(counts)
    sink = 0.0 if followed < 0 else math.fsum(e for j, e in enumerate(energies) if j != followed)
    keys = tuple(next_key + j for j in range(k))
    return Attempt(time=time, schedule=index, k=k, parent=parent, counter=counter,
                   outcome="split", parent_counts=counts, daughters=daughters, keys=keys,
                   followed=followed, lysed=lysed, shear_work=work, sink=sink)  # fmt: skip


# ------------------------------------------------------------------ records (host)


POPULATION_OUTCOMES = (*OUTCOMES, "slots_full")  # a population's attempts (population.py)


def fission_arrays(attempts, places, outcomes=OUTCOMES):
    """The fission table: one row per attempt, in order (records.py declares the arrays).
    attempts: [(Attempt, the parent's generation)]."""
    rows = [a for a, _ in attempts]
    width = max([a.k for a in rows], default=1)
    count = len(rows)
    daughters = np.zeros((count, width, places), dtype=np.int64)
    keys_ = np.full((count, width), -1, dtype=np.int64)
    lysed = np.zeros((count, width), dtype=bool)
    for r, a in enumerate(rows):
        if a.outcome == "split":
            daughters[r, : a.k] = a.daughters[:, :places]
            keys_[r, : a.k] = a.keys
            lysed[r, : a.k] = a.lysed
    return {
        "fission_time": np.asarray([a.time for a in rows], dtype=np.float64),
        "fission_schedule": np.asarray([a.schedule for a in rows], dtype=np.int64),
        "fission_k": np.asarray([a.k for a in rows], dtype=np.int64),
        "fission_parent": np.asarray([a.parent for a in rows], dtype=np.int64),
        "fission_parent_generation": np.asarray([g for _, g in attempts], dtype=np.int64),
        "fission_counter": np.asarray([a.counter for a in rows], dtype=np.int64),
        "fission_outcome": np.asarray([outcomes.index(a.outcome) for a in rows], dtype=np.int8),
        "fission_followed": np.asarray([a.followed for a in rows], dtype=np.int64),
        "fission_parent_counts": np.asarray(
            [a.parent_counts[:places] for a in rows], dtype=np.int64
        ).reshape(count, places),
        "fission_daughters": keys_,
        "fission_daughter_counts": daughters,
        "fission_lysed_at_birth": lysed,
        "fission_shear_work_kT": np.asarray([a.shear_work for a in rows], dtype=np.float64),
        "fission_discarded_kT": np.asarray([a.sink for a in rows], dtype=np.float64),
    }


def lives(attempts, world, status, end_time):
    """The lives, as cells.relations@2's Life fields (one dict each, in birth order): the founder
    0:0, and at each split its parent's end (divided) and its k daughters (the followed one in the
    slot, the others not followed). The last occupant ends lysed at its lysis, extinct, or censored
    at the run's end. share: a daughter's molecules (membrane and lumen) over its brood's."""
    from cells.models.assembly_lineages import keys

    membrane, inside = vesicle_places(world)
    vesicle = np.concatenate((membrane, inside))
    founder = keys.carrier_id(0)
    current = {"id": founder, "key": 0, "lineage": 0, "birth_time": 0.0,
               "birth_kind": "founder", "generation": 0, "root": founder, "declared_by": MODEL_ID,
               "slot": "slot:0", "parent": "", "share": float("nan"), "donor": "",
               "predecessor": "", "birth_event": ""}  # fmt: skip
    out = []
    for r, (a, _) in enumerate(attempts):
        if a.outcome != "split":
            continue
        event = f"event:fission/{r}"
        out.append(current | {"end_time": a.time, "end_reason": "divided", "end_event": event})
        sizes = a.daughters[:, vesicle].sum(axis=1)
        for j, key in enumerate(a.keys):
            life = {"id": keys.carrier_id(key), "key": int(key), "birth_time": a.time,
                    "birth_kind": "division", "generation": current["generation"] + 1,
                    "root": founder, "declared_by": SHEAR_FISSION, "parent": current["id"],
                    "share": float(sizes[j] / sizes.sum()), "donor": "", "predecessor": "",
                    "birth_event": event}  # fmt: skip
            if j == a.followed:
                followed = life | {"lineage": 0, "slot": "slot:0"}
            else:
                out.append(life | {"lineage": -1, "slot": "", "end_time": a.time,
                                   "end_reason": "not_followed", "end_event": event})  # fmt: skip
        current = followed
    if status == "lysed":
        end = {"end_time": end_time, "end_reason": "lysed",
               "end_event": f"event:lysis/{current['key']}"}  # fmt: skip
    elif status == "extinct":
        end = {"end_time": end_time, "end_reason": "extinct", "end_event": ""}
    else:
        end = {"end_time": end_time, "end_reason": "censored", "end_event": ""}
    out.append(current | end)
    return sorted(out, key=lambda life: (life["birth_time"], life["key"]))
