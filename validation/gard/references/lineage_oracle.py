"""The host lineage oracle: a single-lineage direct-method run that writes records in the
engine's declared layout.

This is an independent reference runner: the direct method (``ssa_oracle``) on the
kernels in ``kernels``, a size-threshold fission, and a daughter continuation. It
follows the preprint's T2-02 contract (Appendix F) by default. Each event is one
molecule. The lineage grows to mass 80, then a multivariate-hypergeometric split puts
floor(N/2) molecules in the first daughter, and the first daughter is followed. A
40,000-event guard fissions the current state. The stochastic ledger books each event's
heat as ln(forward/reverse propensity) and each fission's work as
ln pi(P) - ln pi(D1) - ln pi(D2). The sink receives -ln pi(U) of the unfollowed
daughter. ``log_weight`` is ln pi~ with no constant.

The tests use its bundles as stand-ins for engine runs, with planted errors injected.
Its uniforms come from counter-based streams with domain separation: a SeedSequence over
(seed, domain, branch key, counter). So a restart is exact by construction, and a reused
branch key is a reproducible planted error.
"""

from __future__ import annotations

import math

import numpy as np

from .kernels import ExchangeLaw, HeldReservoir, PAIR_CONSISTENT, SINGLE_EVENT, event_heat, log_weight, propensities
from .records import canonical_digest
from .ssa_oracle import DECLARED_BY_ENGINE, ChannelTable, bias_weights, select_channel, uniforms_from_words

DOMAIN_EVENTS = 1
DOMAIN_PARTITION = 2
DOMAIN_CONTINUATION = 3


def stream_words(seed: int, domain: int, branch: int, counter: int, n: int) -> np.ndarray:
    """n 64-bit words for (seed, domain, branch, counter): a pure function of its key."""
    ss = np.random.SeedSequence([int(seed), int(domain), int(branch), int(counter) >> 32,
                                 int(counter) & 0xFFFFFFFF])
    return ss.generate_state(n, dtype=np.uint64)


def stream_uniforms(seed: int, domain: int, branch: int, counter: int, n: int) -> np.ndarray:
    return uniforms_from_words(stream_words(seed, domain, branch, counter, n))


EVENT_BLOCK = 256


class EventStream:
    """Event k's pair (u1, u2): words 2(k mod B), 2(k mod B) + 1 of block floor(k / B).

    A pure function of (seed, branch, k), so a run can be resumed at any event; blocks of
    B = 256 events keep the cost per event small.
    """

    def __init__(self, seed: int, branch: int):
        self.seed, self.branch = int(seed), int(branch)
        self._block = -1
        self._u = None

    def pair(self, k: int) -> tuple[float, float]:
        b, o = divmod(int(k), EVENT_BLOCK)
        if b != self._block:
            self._u = stream_uniforms(self.seed, DOMAIN_EVENTS, self.branch, b, 2 * EVENT_BLOCK)
            self._block = b
        return float(self._u[2 * o]), float(self._u[2 * o + 1])


def world_record(law: ExchangeLaw, founder: np.ndarray, *, fission_mass: int, partition: str = "exact_fraction",
                 fraction: float = 0.5, p: float = 0.5, continuation: str = "first",
                 event_guard: int | None = 40000, guard_rule: str = "stop") -> dict:
    """A world record in the canonical layout of ``records.WORLD_FIELDS``."""
    if not isinstance(law.reservoir, HeldReservoir):
        raise ValueError("lineage worlds use a held supply")
    G = law.n_types
    fission = {"operator": "cells.operator.size_threshold_fission@1", "mass": int(fission_mass),
               "partition": partition}
    if partition == "exact_fraction":
        fission["fraction"] = float(fraction)
    else:
        fission["p"] = float(p)
    if event_guard is not None:
        fission["event_guard"] = int(event_guard)
        fission["guard_rule"] = guard_rule
    body = {
        "schema": "cells.assembly_lineages.world@1",
        "types": [f"type{i:03d}" for i in range(G)],
        "supply": {"kind": "held", "rho": [float(v) for v in law.reservoir.rho]},
        "constants": {"k_join": [float(v) for v in law.k_join], "k_leave": [float(v) for v in law.k_leave]},
        "beta": [[float(v) for v in row] for row in law.beta],
        "founder": [int(v) for v in founder],
        "rules": {"fission": fission,
                  "continuation": {"operator": "cells.operator.daughter_continuation@1", "rule": continuation,
                                   "empty_daughter": "fallback_nonempty"},
                  "sink": {"kind": "declared_sink"},
                  "boundary": law.boundary},
        "units": {"time": "nominal", "temperature_K": None},
    }
    body["id"] = canonical_digest(body)
    return body


def _split(parent: np.ndarray, partition: str, fraction: float, p: float, words_u: np.ndarray) -> np.ndarray:
    G = parent.size
    N = int(parent.sum())
    d1 = np.zeros(G, dtype=np.int64)
    if partition == "exact_fraction":
        n1 = int(math.floor(fraction * N))
        remaining = parent.astype(np.int64).copy()
        R = N
        for k in range(n1):
            target = int(words_u[k] * R)  # 0 <= target < R
            i = int(np.searchsorted(np.cumsum(remaining), target, side="right"))
            remaining[i] -= 1
            d1[i] += 1
            R -= 1
        return d1
    types = np.repeat(np.arange(G), parent)
    np.add.at(d1, types[words_u[:N] < p], 1)
    return d1


def _cosine(x: np.ndarray, y: np.ndarray) -> float:
    nx, ny = np.linalg.norm(x), np.linalg.norm(y)
    if nx == 0 or ny == 0:
        return float("nan")
    return float(np.dot(x, y) / (nx * ny))


def simulate_lineage(law: ExchangeLaw, founder, *, fission_mass: int = 80, n_fissions: int = 10,
                     seed: int = 0, branch: int = 0, partition: str = "exact_fraction", fraction: float = 0.5,
                     p: float = 0.5, continuation: str = "first", event_guard: int | None = 40000,
                     diagnostics: bool = True, leave_weight: float = 1.0, join_factor: float = 1.0,
                     max_events: int | None = None, t_max: float | None = None,
                     world: dict | None = None, table: ChannelTable | None = None,
                     guard_rule: str = "stop", partition_branch: int | None = None) -> tuple[dict, dict, dict]:
    """Run one lineage; return (world, run, arrays) in the canonical bundle layout.

    ``leave_weight`` and ``join_factor`` exist only to plant errors for the controls:
    a biased channel choice, and a catalytic factor applied to joins only.
    """
    G = law.n_types
    x = np.array(founder, dtype=np.int64)
    if world is None:
        world = world_record(law, x, fission_mass=fission_mass, partition=partition, fraction=fraction,
                             p=p, continuation=continuation, event_guard=event_guard, guard_rule=guard_rule)
    rows = {k: [] for k in ("row_time", "row_event", "assembly_count", "joined_total", "left_total",
                            "discarded_total", "exchange_heat_kT", "fission_work_kT",
                            "discarded_free_energy_kT", "log_weight", "ledger_residual_kT",
                            "occupant", "generation")}
    fis = {k: [] for k in ("fission_time", "fission_slot", "fission_parent", "fission_daughters",
                           "fission_followed", "fission_split", "fission_similarity",
                           "fission_partition_counter", "continuation_uniform")}
    ev_time, ev_chan, ev_u, per_growth, part_u = [], [], [], [], []
    joined = np.zeros(G, dtype=np.int64)
    left = np.zeros(G, dtype=np.int64)
    discarded = np.zeros(G, dtype=np.int64)
    heat = work = sink = 0.0
    lw0 = log_weight(law, x)
    t = 0.0
    k = 0
    occupant, generation, next_key = 0, 0, 1
    status = "complete"

    def save_row():
        lw = log_weight(law, x)
        rows["row_time"].append(t)
        rows["row_event"].append(k)
        rows["assembly_count"].append(x.copy()[:, None])
        rows["joined_total"].append(joined.copy()[:, None])
        rows["left_total"].append(left.copy()[:, None])
        rows["discarded_total"].append(discarded.copy()[:, None])
        rows["exchange_heat_kT"].append([heat])
        rows["fission_work_kT"].append([work])
        rows["discarded_free_energy_kT"].append([sink])
        rows["log_weight"].append([lw])
        rows["ledger_residual_kT"].append([heat - ((lw - lw0) + work - sink)])
        rows["occupant"].append([occupant])
        rows["generation"].append([generation])

    save_row()
    events = EventStream(seed, branch)
    table = ChannelTable.default(G) if table is None else table
    weights = bias_weights(table, leave_weight)
    a_plus, a_minus = propensities(law, x)
    f = 0
    in_growth = 0
    while f < n_fissions:
        if max_events is not None and k >= max_events:
            status = "max_events"
            break
        a = table.vector(a_plus * join_factor, a_minus)
        a0 = float(np.cumsum(a)[-1])
        if not a0 > 0:
            status = "stuck"
            break
        u1, u2 = events.pair(k)
        j, _ = select_channel(a, u2, weights)
        i, sign = table.event(j)
        tau = -math.log(u1) / a0
        if t_max is not None and t + tau > t_max:
            status = "t_max"
            break
        y = x.copy()
        y[i] += sign
        b_plus, b_minus = propensities(law, y)
        heat += event_heat(law, x, i, sign, (a_plus, a_minus), (b_plus, b_minus))
        x = y
        a_plus, a_minus = b_plus, b_minus
        if sign > 0:
            joined[i] += 1
        else:
            left[i] += 1
        t += tau
        ev_time.append(t)
        ev_chan.append(int(table.code[j]))
        ev_u.append((u1, u2))
        k += 1
        in_growth += 1
        if int(x.sum()) == 0:
            status = "extinct"  # neither a fission nor a break (preprint, Appendix F)
            break
        guard = event_guard is not None and in_growth >= event_guard
        if guard and guard_rule == "stop" and int(x.sum()) != fission_mass:
            status = "event_guard"  # the engine stops the lineage; T2-02 would force a fission
            break
        if int(x.sum()) == fission_mass or (guard and x.sum() >= 2):
            per_growth.append(in_growth)
            in_growth = 0
            save_row()  # the parent before the split
            P = x.copy()
            N = int(P.sum())
            n_u = int(math.floor(fraction * N)) if partition == "exact_fraction" else N
            pb = branch if partition_branch is None else partition_branch  # a shared key is a planted error
            pu = stream_uniforms(seed, DOMAIN_PARTITION, pb, occupant, max(n_u, 1))  # keyed by the parent
            part_u.append(pu)
            d1 = _split(P, partition, fraction, p, pu)
            d2 = P - d1
            cu = float(stream_uniforms(seed, DOMAIN_CONTINUATION, branch, occupant, 1)[0])
            if continuation == "first":
                fol = 0
            elif continuation == "second":
                fol = 1
            else:
                fol = 0 if cu < 0.5 else 1
            if (d1 if fol == 0 else d2).sum() == 0:
                fol = 1 - fol  # the declared empty-daughter rule: fall back to the nonempty daughter
            D, U = (d1, d2) if fol == 0 else (d2, d1)
            lp, ld1, ld2 = log_weight(law, P), log_weight(law, d1), log_weight(law, d2)
            work += lp - ld1 - ld2
            sink += -log_weight(law, U)
            discarded += U
            keys = (next_key, next_key + 1)
            next_key += 2
            fis["fission_time"].append(t)
            fis["fission_slot"].append(0)
            fis["fission_parent"].append(occupant)
            fis["fission_daughters"].append(keys)
            fis["fission_followed"].append(fol)
            fis["fission_split"].append(d1.copy())
            fis["fission_similarity"].append((_cosine(P, d1), _cosine(P, d2)))
            fis["fission_partition_counter"].append(0)
            fis["continuation_uniform"].append(cu)
            occupant = keys[fol]
            generation += 1
            x = D.copy()
            a_plus, a_minus = propensities(law, x)
            f += 1
            save_row()  # the followed daughter
    if in_growth:
        per_growth.append(in_growth)
    arrays = {
        "row_time": np.asarray(rows["row_time"], dtype=np.float64),
        "row_event": np.asarray(rows["row_event"], dtype=np.int64),
        "assembly_count": np.asarray(rows["assembly_count"], dtype=np.int64),
        "joined_total": np.asarray(rows["joined_total"], dtype=np.int64),
        "left_total": np.asarray(rows["left_total"], dtype=np.int64),
        "discarded_total": np.asarray(rows["discarded_total"], dtype=np.int64),
        "exchange_heat_kT": np.asarray(rows["exchange_heat_kT"], dtype=np.float64),
        "fission_work_kT": np.asarray(rows["fission_work_kT"], dtype=np.float64),
        "discarded_free_energy_kT": np.asarray(rows["discarded_free_energy_kT"], dtype=np.float64),
        "log_weight": np.asarray(rows["log_weight"], dtype=np.float64),
        "ledger_residual_kT": np.asarray(rows["ledger_residual_kT"], dtype=np.float64),
        "occupant": np.asarray(rows["occupant"], dtype=np.int64),
        "generation": np.asarray(rows["generation"], dtype=np.int64),
        "fission_time": np.asarray(fis["fission_time"], dtype=np.float64),
        "fission_slot": np.asarray(fis["fission_slot"], dtype=np.int64),
        "fission_parent": np.asarray(fis["fission_parent"], dtype=np.int64),
        "fission_daughters": np.asarray(fis["fission_daughters"], dtype=np.int64).reshape(-1, 2),
        "fission_followed": np.asarray(fis["fission_followed"], dtype=np.int64),
        "fission_split": np.asarray(fis["fission_split"], dtype=np.int64).reshape(-1, G),
        "fission_similarity": np.asarray(fis["fission_similarity"], dtype=np.float64).reshape(-1, 2),
        "fission_partition_counter": np.asarray(fis["fission_partition_counter"], dtype=np.int64),
        "event_time": np.asarray(ev_time, dtype=np.float64),
        "event_channel": np.asarray(ev_chan, dtype=np.int64),
        "events_per_growth": np.asarray(per_growth, dtype=np.int64),
    }
    if diagnostics:
        arrays["event_uniforms"] = np.asarray(ev_u, dtype=np.float64).reshape(-1, 2)
        arrays["continuation_uniform"] = np.asarray(fis["continuation_uniform"], dtype=np.float64)
        arrays["partition_uniforms"] = (np.concatenate(part_u) if part_u else np.zeros(0)).astype(np.float64)
    run = {
        "schema": "cells.assembly_lineages.run@1",
        "world_id": world["id"],
        "founder": "world",
        "law": {
            "id": (
                "cells.rate_factor.gard_catalysis_pair_consistent@1"
                if law.form == PAIR_CONSISTENT
                else "cells.rate_factor.gard_catalysis_single_event@1"
            ),
            "form": law.form,
            "energy_role": "passive" if law.form == PAIR_CONSISTENT else "driven",
            "check_verdict": "passive" if law.form == PAIR_CONSISTENT else "refused_as_passive",
        },
        "revision": "host-oracle",
        "mode": "single_lineage",
        "stream": {
            "seed": int(seed),
            "branch": int(branch),
            "domains": {
                "events": DOMAIN_EVENTS,
                "partition": DOMAIN_PARTITION,
                "continuation": DOMAIN_CONTINUATION,
            },
        },
        "ssa_convention": dict(DECLARED_BY_ENGINE),
        "ledger_conventions": {
            "event_heat": "ln_forward_over_reverse_propensity",
            "fission_work": "ln_pi_parent_minus_ln_pi_daughters",
            "sink": "minus_ln_pi_unfollowed",
            "log_weight_constant": 0.0,
        },
        "end_status": status,
        "channels": table.to_declared(world["types"]),
        "time": {
            "unit": world["units"]["time"],
            "temperature_K": world["units"]["temperature_K"],
            "rates": "per " + world["units"]["time"] + " time unit",
            "bases": ["fission"],
        },
    }
    if t_max is not None:
        run["t_end"] = float(t_max) if status == "t_max" else float(t)
    return world, run, arrays
