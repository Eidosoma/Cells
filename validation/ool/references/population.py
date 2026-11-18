"""OL2's shared pool and OL3's schedules: the reference world, its direct method and its replay.

Written from docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.2c rules 5 and 8-14, §0.2d items 5-7 (at
7fb8816f, with item 6 confirmed at 95c98b5a), §3.1-§3.3, §4.3-§4.4 and §5.2; code-blind.

**Draws.** Every uniform is addressed by (domain, key, counter):
- the world's selection (population mode): domain 5, the world's carrier word, three uniforms per
  draw (u1 the time, u2 the group, u3 the channel; §0.2d 5);
- the followed assembly's events (single-lineage mode): domain 1, its carrier key, OL1's two
  uniforms per draw, the counter being OL1's ``age`` (§0.2d 6, 95c98b5a);
- a fission attempt: domain 2, the parent's carrier key, the counter counting the parent's
  attempts (§0.2c rule 12), one block of N + k + N_L uniforms in rules 9-10's order;
- a schedule: domain 6, its declared index as the key, a block of one per draw, the counter at the
  schedule's own draw count: one per Poisson gap, one per living assembly at a transfer.
A draw's counter counts draws, not events.

**The clock** (§0.2d 6, ruled). A draw whose time crosses the next declared schedule time is
discarded; the clock moves to that time, the scheduled event applies, and the next draw takes the
next counter. A draw crossing t_end ends the run (``t_end``), as in OL1.

**Selection** (population; §0.2d 5). a0 is the serial fold of the groups' totals (the pool, then
slots 0..K-1), each group's total the serial fold of its channels (the vesicle's declared steps
forward, then the same steps reverse; the pool's steps likewise). tau = -ln(u1)/a0; the group is
the first whose running total exceeds min(u2 a0, nextafter(a0, 0)); the channel the first in the
group whose running total exceeds min(u3 a_g, nextafter(a_g, 0)). Single-lineage: the channel is
the first whose prefix exceeds u2 a0 (OL1's map).

**Events** (§0.2d item 10, at c8b22371: the replay conventions, binding the engine and the
references alike). A step's end state beyond sigma_max lyses the vesicle (one ledger row, ``ol2``).
A shear event (declared times, or a Poisson process of rate lambda with gaps -ln(u)/lambda, the
first t_1 = -ln(u_0)/lambda from t = 0) acts on the assemblies alive at its start, in slot order;
daughters born in it are not tested again. Two scheduled events at the same time apply in order of
schedule index, each to the assemblies alive at its own start, with no draw between them; a
declared time equal to t_end applies, a later one never does. An attempt runs: the stress test
(none is declared in the registered worlds), v <= k^(-1/2) (§4.3, D2); in population mode k - 1
free slots, or the run stops ``slots_full``; the draw (rule 9's uniforms, then rule 10's); the split
and the floor test; the fission applied, or refused and recorded with the parent kept. The fission
counter counts draws. Every daughter counts as born (the shear work Sum F(daughters) - F(parent),
and keys) and takes its slot (the first daughter the parent's, the others the lowest free, or the
lowest of the free and the parent's: either set is accepted, the assignment within it not claimed);
a daughter born beyond sigma_max then lyses at birth, freeing its slot, booked as a lysis. In
single-lineage mode the recorded followed daughter (G1's ``fission_followed``, required) continues
and the others go to the sink. A transfer (declared times) draws one uniform per living assembly in slot order
and keeps the K_keep smallest, ties by slot; the removed assemblies' F and the old pool's F go to
the sink, and the fresh pool's F is schedule work (§3.1-§3.3).

**Ledger closure** (§3.3): F(now) - F(0) = reservoir work + shear work + schedule work - heat -
sink, at every event.

``simulate`` runs the model from a draw source: ``HostStreams`` (the stand-in) or ``Recorded``
(the replay, which serves a trace's own uniforms and follows its recorded choice only at a
near-tie). ``replay`` compares a trace with the reference event by event.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field

import numpy as np

from . import partition as PT
from .common import RecordFormatError
from .ol2 import Law2, Vesicle2, World2

DOMAIN_LINEAGE, DOMAIN_FISSION, DOMAIN_WORLD, DOMAIN_SCHEDULE = 1, 2, 5, 6
TIE_RTOL = 1e-12
TIME_RTOL = 1e-12
TRACE_FORMAT = "ool_references.population_trace@1"
PLANTED_POPULATION = ("flat_select", "counter_not_advanced", "transfer_largest", "transfer_skip_when_all_kept",
                      "gap_one_minus", "admission_one_over_k", "floor_on_parent", "birth_lysis_kept",
                      "transfer_fresh_to_sink", "old_pool_not_sunk", "slots_highest", "no_discard")


@dataclass(frozen=True)
class Schedule:
    index: int                      # the declared index: the key in domain 6
    kind: str                       # "shear" or "transfer"
    times: tuple = ()               # declared times (s)
    rate: float | None = None       # a Poisson shear's rate (1/s)
    k: int = 2                      # shear: daughters per fission
    K_keep: int = 0                 # transfer: assemblies kept
    fresh_pool: tuple = ()          # transfer: the fresh pool's finite counts

    def document(self) -> dict:
        out = {"index": self.index, "kind": self.kind}
        if self.kind == "shear":
            out.update({"k": self.k, **({"times_s": list(self.times)} if self.times else {"poisson_rate_per_s": self.rate})})
        else:
            out.update({"times_s": list(self.times), "K_keep": self.K_keep, "fresh_pool": list(self.fresh_pool)})
        return out


@dataclass
class RunSpec:
    world: World2
    mode: str                       # "population" or "single_lineage"
    slots: int
    t_end: float
    max_events: int
    schedules: tuple
    world_key: int
    founders: list                  # [(Vesicle2, carrier key)] into slots 0, 1, ...
    pool: tuple                     # the initial finite pool
    seed: int = 0                   # the stand-in's streams only
    name: str = ""


def daughter_key(parent: int, j: int) -> int:
    """The stand-in's carrier key for daughter j (the engine's own derivation is recorded)."""
    return (parent * 1_000_003 + 7919 * (j + 1)) % (2 ** 61 - 1)


class HostStreams:
    """The stand-in's uniforms: a NumPy generator seeded by (seed, domain, key, counter)."""

    def __init__(self, seed: int):
        self.seed = seed

    def get(self, domain: int, key: int, counter: int, n: int) -> list:
        g = np.random.Generator(np.random.PCG64(np.random.SeedSequence([self.seed, domain, key % 2 ** 32,
                                                                         key // 2 ** 32, counter])))
        u = g.random(n)
        while n and u[0] == 0.0:        # the time uniform is in (0, 1)
            u[0] = g.random()
        return [float(x) for x in u]

    def follow(self, what: str, index, mine):
        return mine

    def followed_daughter(self, attempt_index: int, k: int) -> int:
        return 0

    def daughter_slots(self, attempt_index: int, parent_slot: int, free: list, mine: dict) -> dict:
        return mine

    def daughter_keys(self, attempt_index: int, parent_key: int, k: int) -> list:
        return [daughter_key(parent_key, j) for j in range(k)]


class Recorded:
    """A trace's own draws, served by address; a missing draw is a mismatch."""

    def __init__(self, trace: dict):
        self.trace = trace
        self.index = {}
        for d in trace.get("draws", []):
            self.index[(d["domain"], d["key"], d["counter"])] = d["u"]
        for d in trace.get("schedule_draws", []):
            self.index[(DOMAIN_SCHEDULE, d["schedule"], d["counter"])] = [d["u"]]
        stopped = [a for e in trace.get("events", []) if e["kind"] == "shear" for a in e["attempts"]
                   if a.get("outcome") == "slots_full"]
        self.attempts = [a for e in trace.get("events", []) if e["kind"] == "shear" for a in e["attempts"]
                         if a.get("outcome") != "slots_full"]
        for a in self.attempts + [a for a in stopped if a.get("u")]:
            self.index[(DOMAIN_FISSION, a["key"], a["counter"])] = a["u"]
        self.used = set()
        self.missing = []
        self.ties = 0

    def get(self, domain: int, key: int, counter: int, n: int) -> list:
        addr = (domain, key, counter)
        u = self.index.get(addr)
        if u is None or len(u) != n:
            self.missing.append(dict(address=list(addr), needed=n, recorded=None if u is None else len(u)))
            hint = " (every draw is recorded, discarded draws, the draw that ends the run and a Poisson gap past t_end " \
                   "included)" if u is None else ""
            raise _Mismatch(f"draw {addr} needed ({n} uniforms), recorded {None if u is None else len(u)}{hint}")
        self.used.add(addr)
        return list(u)

    def follow(self, what: str, index, mine):
        """At a near-tie the replay follows the trace's recorded choice."""
        self.ties += 1
        return self.recorded_choice(what, index, mine)

    def recorded_choice(self, what, index, mine):
        if what == "step":
            ev = self.trace["events"][index]
            return (ev["group"], ev["channel"]) if ev["kind"] == "step" else mine
        if what == "lumen":
            return self.attempts[index]["daughters"]
        return mine

    def followed_daughter(self, attempt_index: int, k: int) -> int:
        """G1's ``fission_followed``, generalised to k: required on every single-lineage split; a
        missing or out-of-range field is a record error, never daughter 0 (§0.2d 10)."""
        a = self.attempts[attempt_index]
        f = a.get("followed")
        if not isinstance(f, int) or isinstance(f, bool) or not 0 <= f < k:
            raise RecordFormatError(f"the single-lineage attempt (key {a.get('key')}, counter {a.get('counter')}) "
                                    f"records no followed daughter in 0..{k - 1} (fission_followed): {f!r}")
        return f

    def daughter_slots(self, attempt_index: int, parent_slot: int, free: list, mine: dict) -> dict:
        """The recorded daughter-to-slot map (every daughter, a birth-lysed one included, takes its
        slot first; §0.2d 10.3), when its slot set is one of the two readings of 'later daughters
        take free slots in slot order' (§0.2d 6): the parent's slot and the lowest free ones, or the
        lowest of the free slots and the parent's. Which daughter takes which slot is not claimed
        (the daughters are exchangeable under pi)."""
        if attempt_index >= len(self.attempts):
            return mine
        rec = {d: int(x.get("slot", -1)) for d, x in enumerate(self.attempts[attempt_index].get("daughters", []))}
        n = len(mine)
        reading_b = {parent_slot, *free[: max(n - 1, 0)]}
        reading_a = set(sorted(free + [parent_slot])[:n])
        if set(rec) == set(mine) and len(set(rec.values())) == n and set(rec.values()) in (reading_a, reading_b):
            return rec
        return mine

    def daughter_keys(self, attempt_index: int, parent_key: int, k: int) -> list:
        return [int(d["key"]) for d in self.attempts[attempt_index]["daughters"]]


class _Mismatch(Exception):
    pass


@dataclass
class _State:
    slots: list
    keys: list
    pool: tuple
    t: float = 0.0
    attempts: dict = field(default_factory=dict)     # carrier key -> attempts so far
    draws: dict = field(default_factory=dict)        # (domain, key) -> draws so far


def ruled_order(channels) -> list:
    """§0.2d 5: a group's channels in declared step order, forwards, then reverses."""
    return [(i, 1) for i in range(len(channels))] + [(i, -1) for i in range(len(channels))]


def channel_document(model) -> dict:
    def doc(chs, order):
        return [[chs[i].id, "forward" if s > 0 else "reverse"] for i, s in order]

    return {"pool": doc(model.pch, model.porder), "vesicle": doc(model.vch, model.vorder)}


def _fold(xs) -> float:
    acc = 0.0
    for x in xs:
        acc += x
    return acc


def two_level(group_rates: list, u2: float, u3: float) -> tuple:
    """§0.2d 5; returns (group, channel, near_tie)."""
    totals = [_fold(r) for r in group_rates]
    run, a0 = [], 0.0
    for t in totals:
        a0 += t
        run.append(a0)
    target = min(u2 * a0, math.nextafter(a0, 0.0))
    g = next(i for i, x in enumerate(run) if x > target)
    tie = min(abs(x - target) for x in run) <= TIE_RTOL * a0
    ag = totals[g]
    target = min(u3 * ag, math.nextafter(ag, 0.0))
    acc, c = 0.0, len(group_rates[g]) - 1
    for i, r in enumerate(group_rates[g]):
        acc += r
        if acc > target:
            c = i
            break
    prefix = np.cumsum(group_rates[g])
    tie = tie or bool(np.min(np.abs(prefix - target)) <= TIE_RTOL * ag)
    return g, c, tie


def flat(group_rates: list, u2: float) -> tuple:
    """The planted one-level map over every channel of every group."""
    items = [(g, c, r) for g, rates in enumerate(group_rates) for c, r in enumerate(rates)]
    a0 = _fold(r for _, _, r in items)
    target = min(u2 * a0, math.nextafter(a0, 0.0))
    acc = 0.0
    for g, c, r in items:
        acc += r
        if acc > target:
            return g, c, False
    raise RuntimeError("no channel")


class Model:
    """The reference world for one run specification (``planted`` names one wrong behaviour)."""

    def __init__(self, spec: RunSpec, planted: str | None = None, law_planted: str | None = None,
                 lineage_order: list | None = None):
        self.spec = spec
        self.planted = planted
        self.law = Law2(spec.world, law_planted)
        self.vch = spec.world.vesicle_channels()
        self.pch = spec.world.pool_channels()
        self.vorder = lineage_order or ruled_order(self.vch)
        self.porder = ruled_order(self.pch)
        if spec.mode == "single_lineage" and self.pch:
            raise ValueError("a single-lineage world with pool steps is not registered in the references")

    # ---------------------------------------------------------------- rates
    def group_rates(self, st: _State) -> list:
        law, p = self.law, st.pool
        out = [[law.pool_rate(p, self.pch[i], s) for i, s in self.porder]]
        for v in st.slots:
            out.append([] if v is None else [law.rate(v, p, self.vch[i], s) for i, s in self.vorder])
        return out

    def lineage_rates(self, st: _State) -> list:
        v = st.slots[0]
        return [self.law.rate(v, st.pool, self.vch[i], s) for i, s in self.vorder]

    # ---------------------------------------------------------------- draws
    def draw(self, src, st: _State, domain: int, key: int, n: int) -> tuple:
        c = st.draws.get((domain, key), 0)          # every counter starts at 0 (§0.2d 10.6)
        u = src.get(domain, key, c, n)
        st.draws[(domain, key)] = c + 1
        return c, u

    # ---------------------------------------------------------------- events
    def apply_step(self, st: _State, g: int, c: int) -> dict:
        """Group g (0 the pool, 1 + j slot j), channel c of the group's order."""
        law = self.law
        if g == 0:
            i, sign = self.porder[c]
            ch = self.pch[i]
            p2 = law.pool_after(st.pool, ch, sign)
            dF = law._dF_pool(st.pool, p2)
            st.pool = p2
            return dict(group=-1, channel=c, lysed=False, heat=-dF, reservoir_work=0.0)
        j = g - 1
        v = st.slots[j]
        i, sign = self.vorder[c]
        ch = self.vch[i]
        v2, p2 = law.after(v, st.pool, ch, sign)
        w = law.work(ch, sign)
        if law.lyses(v2):
            b = law.lysis_booking(v, st.pool, v2, p2, w)
            st.pool = b["pool_after"]
            st.slots[j] = None
            st.keys[j] = None
            return dict(group=j, channel=c, lysed=True, heat=b["heat"], reservoir_work=b["work"])
        dF = law.dF(v, st.pool, v2, p2)
        st.slots[j], st.pool = v2, p2
        return dict(group=j, channel=c, lysed=False, heat=-dF + w, reservoir_work=w)

    def admissible(self, v: Vesicle2, k: int) -> bool:
        thr = 1.0 / k if self.planted == "admission_one_over_k" else k ** -0.5
        return self.law.reduced_volume(v) <= thr

    def free_slots(self, st: _State) -> list:
        free = [j for j, v in enumerate(st.slots) if v is None]
        return free[::-1] if self.planted == "slots_highest" else free

    def shear(self, st: _State, sch: Schedule, src, attempt_base: int) -> tuple:
        """Every assembly living at the event's start, in slot order. Returns (event, end)."""
        law, w = self.law, self.spec.world
        k = sch.k
        attempts, not_admitted, end = [], [], None
        living = [j for j, v in enumerate(st.slots) if v is not None]
        for j in living:
            v = st.slots[j]
            if v is None:
                continue
            if not self.admissible(v, k):
                not_admitted.append(j)
                continue
            if self.spec.mode == "population" and len(self.free_slots(st)) < k - 1:
                end = "slots_full"
                break
            key = st.keys[j]
            counter = st.attempts.get(key, 0)
            N, NL = sum(v.n), sum(v.l)
            u = src.get(DOMAIN_FISSION, key, counter, N + k + NL)
            st.attempts[key] = counter + 1
            ai = attempt_base + len(attempts)
            sp = PT.split_from_uniforms(list(v.n), self.law.k, list(v.l), k, u)
            att = dict(slot=j, key=key, counter=counter, u=u)
            Wd = [sum(a * b for a, b in zip(row, self.law.k)) for row in sp["membrane"]]
            floor_fail = (law.W(v) < w.W_floor) if self.planted == "floor_on_parent" else min(Wd) < w.W_floor
            if floor_fail:
                att.update(outcome="refused_floor", daughters=[], shear_work=0.0, heat=0.0, reservoir_work=0.0, sink=0.0)
                attempts.append(att)
                continue
            lum = sp["lumen"]
            if _lumen_near_tie(sp, u, N, k):
                lum = [d["l"] for d in src.follow("lumen", ai, [dict(n=m, l=x) for m, x in zip(sp["membrane"], lum)])]
            daughters = [Vesicle2(tuple(m), tuple(x)) for m, x in zip(sp["membrane"], lum)]
            w_shear = law.shear_work(v, daughters)
            keys = src.daughter_keys(ai, key, k)
            free = self.free_slots(st)
            st.slots[j], st.keys[j] = None, None
            heat = res = sink = 0.0
            drec = []
            followed = src.followed_daughter(ai, k) if self.spec.mode == "single_lineage" else None
            lysed = [law.lyses(dv) and self.planted != "birth_lysis_kept" for dv in daughters]
            mine = dict(zip(range(k), [j] + free[: k - 1]))
            slot_of = src.daughter_slots(ai, j, free, mine) if self.spec.mode == "population" else mine
            if self.spec.mode == "population":
                for d, dv in enumerate(daughters):          # each takes its slot before any birth lysis
                    st.slots[slot_of[d]], st.keys[slot_of[d]] = dv, keys[d]
            for d, dv in enumerate(daughters):
                rec = dict(key=keys[d], n=list(dv.n), l=list(dv.l), lysed_at_birth=bool(lysed[d]))
                if self.spec.mode == "single_lineage":
                    rec["slot"] = 0 if d == followed else -1
                    if d != followed:
                        sink += law.F_vesicle(dv)
                    elif lysed[d]:
                        end = "lysed"
                    else:
                        st.slots[0], st.keys[0] = dv, keys[d]
                else:
                    rec["slot"] = slot_of[d]
                    if lysed[d]:                              # the birth lysis frees the slot
                        b = law.lysis_booking(dv, st.pool, dv, st.pool, 0.0)
                        heat += b["heat"]
                        res += b["work"]
                        st.pool = b["pool_after"]
                        st.slots[slot_of[d]], st.keys[slot_of[d]] = None, None
                drec.append(rec)
            att.update(outcome="split", daughters=drec, shear_work=w_shear, heat=heat, reservoir_work=res, sink=sink)
            if followed is not None:
                att["followed"] = followed
            attempts.append(att)
            if end:
                break
        return dict(kind="shear", schedule=sch.index, attempts=attempts, not_admitted=not_admitted), end

    def transfer(self, st: _State, sch: Schedule, src) -> dict:
        law = self.law
        living = [j for j, v in enumerate(st.slots) if v is not None]
        draws = []
        if not (self.planted == "transfer_skip_when_all_kept" and len(living) <= sch.K_keep):
            for j in living:
                c, (u,) = self.draw(src, st, DOMAIN_SCHEDULE, sch.index, 1)
                draws.append(dict(slot=j, counter=c, u=u))
        if draws:
            order = sorted(draws, key=lambda d: (d["u"], d["slot"]))
            if self.planted == "transfer_largest":
                order = sorted(draws, key=lambda d: (-d["u"], d["slot"]))
            kept = sorted(d["slot"] for d in order[: sch.K_keep])
        else:
            kept = living[: sch.K_keep]
        removed = [j for j in living if j not in kept]
        sink = sum(law.F_vesicle(st.slots[j]) for j in removed)
        old = law.F_pool(st.pool)
        fresh = law.F_pool(tuple(sch.fresh_pool))
        sched_work = fresh
        if self.planted != "old_pool_not_sunk":
            sink += old
        if self.planted == "transfer_fresh_to_sink":
            sink -= fresh
            sched_work = 0.0
        for j in removed:
            st.slots[j], st.keys[j] = None, None
        st.pool = tuple(sch.fresh_pool)
        return dict(kind="transfer", schedule=sch.index, draws=draws, kept=kept, removed=removed, sink=sink,
                    schedule_work=sched_work)

    # ---------------------------------------------------------------- schedule times
    def next_times(self, st: _State, src, pending: dict, sch: Schedule):
        """The schedule's next time after the current one (Poisson: draw a gap)."""
        if sch.times:
            i = pending.get(sch.index, (None, -1))[1] + 1
            return (sch.times[i], i) if i < len(sch.times) else (math.inf, i)
        prev = pending.get(sch.index, (0.0, -1))[0]
        c, (u,) = self.draw(src, st, DOMAIN_SCHEDULE, sch.index, 1)
        gap = -math.log1p(-u) / sch.rate if self.planted == "gap_one_minus" else -math.log(u) / sch.rate
        self._gaps.append(dict(schedule=sch.index, counter=c, u=u, use="gap", time=prev + gap))
        return prev + gap, c


def _lumen_near_tie(sp: dict, u: list, N: int, k: int) -> bool:
    cum, acc = [], 0.0
    for b in range(k):
        acc += sp["weights"][sp["pi"][b]]
        cum.append(acc)
    lu = np.asarray(u[N + k:])
    if lu.size == 0:
        return False
    return bool(np.min(np.abs(lu[:, None] - np.asarray(cum[:-1])[None, :]), initial=1.0) <= TIE_RTOL)


def simulate(spec: RunSpec, src, planted: str | None = None, law_planted: str | None = None,
             lineage_order: list | None = None) -> dict:
    """Run the reference from a draw source; returns a trace in the canonical layout."""
    m = Model(spec, planted, law_planted, lineage_order)
    m._gaps = []
    K = spec.slots
    slots = [None] * K
    keys = [None] * K
    for j, (v, key) in enumerate(spec.founders):
        slots[j], keys[j] = v, key
    st = _State(slots=slots, keys=keys, pool=tuple(spec.pool))
    F0 = m.law.F(st.slots, st.pool)
    trace = dict(format=TRACE_FORMAT, run=spec.name, world=spec.world.name, mode=spec.mode, slots=K, t_end=spec.t_end,
                 max_events=spec.max_events, schedules=[s.document() for s in spec.schedules],
                 world_key=spec.world_key, environment={"threefry_partitionable": True},
                 initial=dict(slots=[None if v is None else dict(n=list(v.n), l=list(v.l), key=keys[j])
                                     for j, v in enumerate(st.slots)], pool=list(st.pool)),
                 channels=channel_document(m), draws=[], schedule_draws=[], events=[], F_initial=F0)
    pending = {}
    for s in spec.schedules:
        pending[s.index] = m.next_times(st, src, pending, s)
    attempt_base = 0
    end = None
    try:
        while end is None:
            if len(trace["events"]) >= spec.max_events:
                end = "max_events"
                break
            t_next, s_next = min(((pending[s.index][0], s.index) for s in spec.schedules), default=(math.inf, None))
            if t_next <= st.t and t_next <= spec.t_end:
                # a scheduled event due now (a simultaneous one, or one at t = 0): it applies before any
                # draw, in order of schedule index (§0.2d 10.1)
                end = _apply_schedule(m, st, spec, s_next, src, trace, pending, attempt_base)
                attempt_base = _count_attempts(trace)
                continue
            if spec.mode == "population":
                rates = m.group_rates(st)
                a0 = _fold(_fold(r) for r in rates)
                domain, key, n_u = DOMAIN_WORLD, spec.world_key, 3
            else:
                if st.slots[0] is None:
                    end = "lysed"
                    break
                rates = m.lineage_rates(st)
                a0 = _fold(rates)
                domain, key, n_u = DOMAIN_LINEAGE, st.keys[0], 2
            if a0 <= 0:
                if t_next <= spec.t_end:
                    st.t = t_next
                    end = _apply_schedule(m, st, spec, s_next, src, trace, pending, attempt_base)
                    attempt_base = _count_attempts(trace)
                    continue
                end = "no_channel"
                break
            c, u = m.draw(src, st, domain, key, n_u)
            tau = -math.log(u[0]) / a0
            rec = dict(domain=domain, key=key, counter=c, u=u)
            trace["draws"].append(rec)
            t_fire = st.t + tau
            if t_fire > t_next and t_next <= spec.t_end:
                if m.planted == "counter_not_advanced":
                    st.draws[(domain, key)] = c
                st.t = t_next
                end = _apply_schedule(m, st, spec, s_next, src, trace, pending, attempt_base)
                attempt_base = _count_attempts(trace)
                if m.planted != "no_discard" or end is not None:
                    rec["fate"] = "discarded"
                    continue
                # the planted clock: the crossing draw fires after the scheduled event, at its own time
                if spec.mode == "population":
                    rates = m.group_rates(st)
                    a0 = _fold(_fold(r) for r in rates)
                else:
                    rates = m.lineage_rates(st)
                    a0 = _fold(rates)
                if a0 <= 0:
                    rec["fate"] = "discarded"
                    continue
            if t_fire > spec.t_end:
                rec["fate"] = "end"
                end = "t_end"
                break
            st.t = t_fire
            ei = len(trace["events"])
            if spec.mode == "population":
                if m.planted == "flat_select":
                    g, ch, tie = flat(rates, u[1])
                else:
                    g, ch, tie = two_level(rates, u[1], u[2])
                if tie:
                    g, ch = src.follow("step", ei, (g - 1, ch))
                    g += 1
            else:
                prefix = np.cumsum(rates)
                target = u[1] * a0
                ch = min(int(np.searchsorted(prefix, target, side="right")), len(rates) - 1)
                if np.min(np.abs(prefix - target)) <= TIE_RTOL * a0:
                    _, ch = src.follow("step", ei, (0, ch))
                g = 1
            rec["fate"] = "event"
            out = m.apply_step(st, g, ch)
            trace["events"].append(dict(kind="step", t=st.t, draw=len(trace["draws"]) - 1, **out,
                                        **_state_of(st, out["group"])))
            if spec.mode == "single_lineage" and out["lysed"]:
                end = "lysed"
    except _Mismatch as exc:
        end = "replay_mismatch"
        trace["replay_problem"] = str(exc)
    trace["schedule_draws"] = sorted(m._gaps + [dict(schedule=e["schedule"], counter=d["counter"], u=d["u"],
                                                     use="transfer")
                                                for e in trace["events"] if e["kind"] == "transfer" for d in e["draws"]],
                                     key=lambda d: (d["schedule"], d["counter"]))
    trace["end_reason"] = end
    trace["t_final"] = st.t
    trace["final"] = dict(slots=[None if v is None else dict(n=list(v.n), l=list(v.l), key=st.keys[j])
                                 for j, v in enumerate(st.slots)], pool=list(st.pool))
    trace["F_final"] = m.law.F(st.slots, st.pool)
    return trace


def _count_attempts(trace: dict) -> int:
    return sum(len(e["attempts"]) for e in trace["events"] if e["kind"] == "shear")


def _state_of(st: _State, j: int) -> dict:
    v = st.slots[j] if j >= 0 else None
    return dict(after=None if v is None else dict(n=list(v.n), l=list(v.l)), pool=list(st.pool))


def _apply_schedule(m: Model, st: _State, spec: RunSpec, s_index: int, src, trace: dict, pending: dict,
                    attempt_base: int):
    sch = next(s for s in spec.schedules if s.index == s_index)
    if sch.kind == "shear":
        ev, end = m.shear(st, sch, src, attempt_base)
    else:
        ev, end = m.transfer(st, sch, src), None
    ev["t"] = st.t
    ev["pool"] = list(st.pool)
    ev["slots_after"] = [None if v is None else dict(n=list(v.n), l=list(v.l), key=st.keys[j])
                         for j, v in enumerate(st.slots)]
    trace["events"].append(ev)
    pending[sch.index] = m.next_times(st, src, pending, sch)
    return end


# ==================================================================== checks on a trace

def _close(a: float, b: float, scale: float, rtol: float = 1e-9) -> bool:
    return abs(a - b) <= rtol * max(1.0, abs(scale))


def compare(mine: dict, theirs: dict, scale: float, limit: int = 5) -> list:
    """Event-by-event differences between the reference's trace and a recorded one."""
    out = []

    def bad(**kw):
        out.append(kw)
        return len(out) >= limit

    em, et = mine["events"], theirs.get("events", [])
    for i in range(min(len(em), len(et))):
        a, b = em[i], et[i]
        if a["kind"] != b["kind"]:
            bad(where="event", index=i, reference=a["kind"], recorded=b["kind"])
            return out
        if abs(a["t"] - b["t"]) > TIME_RTOL * max(abs(a["t"]), 1e-300):
            if bad(where="time", index=i, reference=a["t"], recorded=b["t"]):
                return out
        if a["kind"] == "step":
            if (a["group"], a["channel"], a["lysed"]) != (b["group"], b["channel"], b["lysed"]):
                if bad(where="step", index=i, reference=[a["group"], a["channel"], a["lysed"]],
                       recorded=[b["group"], b["channel"], b["lysed"]]):
                    return out
                continue
            for f in ("heat", "reservoir_work"):
                if not _close(a[f], b[f], scale):
                    if bad(where=f, index=i, reference=a[f], recorded=b[f]):
                        return out
            if a["after"] != b["after"] or a["pool"] != b["pool"]:
                if bad(where="state", index=i, reference=[a["after"], a["pool"]], recorded=[b["after"], b["pool"]]):
                    return out
        elif a["kind"] == "shear":
            if a["not_admitted"] != b.get("not_admitted"):
                if bad(where="not_admitted", index=i, reference=a["not_admitted"], recorded=b.get("not_admitted")):
                    return out
            b_att = [y for y in b["attempts"] if y.get("outcome") != "slots_full"]
            if len(a["attempts"]) != len(b_att):
                bad(where="attempts", index=i, reference=len(a["attempts"]), recorded=len(b_att))
                return out
            for x, y in zip(a["attempts"], b_att):
                keys = ("slot", "key", "counter", "outcome")
                if [x[q] for q in keys] != [y.get(q) for q in keys]:
                    if bad(where="attempt", index=i, reference=[x[q] for q in keys], recorded=[y.get(q) for q in keys]):
                        return out
                    continue
                dx = [(d["n"], d["l"], d["slot"], d["lysed_at_birth"]) for d in x["daughters"]]
                dy = [(d.get("n"), d.get("l"), d.get("slot"), d.get("lysed_at_birth")) for d in y.get("daughters", [])]
                if dx != dy:
                    if bad(where="daughters", index=i, slot=x["slot"], reference=dx, recorded=dy):
                        return out
                for f in ("shear_work", "heat", "reservoir_work", "sink"):
                    if not _close(x[f], y.get(f, math.nan), scale):
                        if bad(where=f, index=i, slot=x["slot"], reference=x[f], recorded=y.get(f)):
                            return out
        elif a["kind"] == "transfer":
            if [(d["slot"], d["counter"], d["u"]) for d in a["draws"]] != \
                    [(d.get("slot"), d.get("counter"), d.get("u")) for d in b.get("draws", [])]:
                if bad(where="transfer_draws", index=i, reference=len(a["draws"]), recorded=len(b.get("draws", []))):
                    return out
            if (a["kept"], a["removed"]) != (b.get("kept"), b.get("removed")):
                if bad(where="transfer_kept", index=i, reference=a["kept"], recorded=b.get("kept")):
                    return out
            for f in ("sink", "schedule_work"):
                if not _close(a[f], b.get(f, math.nan), scale):
                    if bad(where=f, index=i, reference=a[f], recorded=b.get(f)):
                        return out
    if len(em) != len(et):
        bad(where="events", reference=len(em), recorded=len(et))
    dm, dt = mine["draws"], theirs.get("draws", [])
    for i in range(min(len(dm), len(dt))):
        a, b = dm[i], dt[i]
        if (a["domain"], a["key"], a["counter"], a.get("fate")) != (b["domain"], b["key"], b["counter"], b.get("fate")):
            bad(where="draw", index=i, reference=[a["domain"], a["key"], a["counter"], a.get("fate")],
                recorded=[b["domain"], b["key"], b["counter"], b.get("fate")])
            break
    if len(dm) != len(dt):
        bad(where="draws", reference=len(dm), recorded=len(dt))
    if mine.get("end_reason") == "replay_mismatch":
        bad(problem=mine.get("replay_problem"))
    sm = [(d["schedule"], d["counter"], d["u"], d["use"]) for d in mine["schedule_draws"]]
    st_ = [(d.get("schedule"), d.get("counter"), d.get("u"), d.get("use")) for d in theirs.get("schedule_draws", [])]
    if sm != st_:
        bad(where="schedule_draws", reference=len(sm), recorded=len(st_))
    if mine["end_reason"] != theirs.get("end_reason"):
        bad(where="end_reason", reference=mine["end_reason"], recorded=theirs.get("end_reason"))
    return out


def spec_for_trace(spec: RunSpec, trace: dict) -> RunSpec:
    """The registered run with the trace's own carrier keys, after checking that the trace is
    that run (mode, slots, t_end, schedules, the initial counts and pool); RecordFormatError if not."""
    want = dict(mode=spec.mode, slots=spec.slots, t_end=spec.t_end, schedules=[s.document() for s in spec.schedules],
                pool=list(spec.pool))
    got = dict(mode=trace.get("mode"), slots=trace.get("slots"), t_end=trace.get("t_end"),
               schedules=trace.get("schedules"), pool=trace.get("initial", {}).get("pool"))
    for k in want:
        if want[k] != got[k]:
            raise RecordFormatError(f"the trace's {k} {got[k]!r} is not the registered run's {want[k]!r}")
    slots = trace["initial"].get("slots", [])
    if len(slots) != spec.slots:
        raise RecordFormatError(f"the trace's initial slots: {len(slots)}, {spec.slots} registered")
    founders = []
    for j, s in enumerate(slots):
        reg = spec.founders[j][0] if j < len(spec.founders) else None
        if (s is None) != (reg is None) or (s is not None and (tuple(s["n"]), tuple(s["l"])) != (reg.n, reg.l)):
            raise RecordFormatError(f"the trace's founder in slot {j} is not the registered one")
        if s is not None:
            founders.append((reg, int(s["key"])))
    if "world_key" not in trace:
        raise RecordFormatError("the trace has no world_key")
    return dataclasses.replace(spec, world_key=int(trace["world_key"]), founders=founders)


def declared_order(spec: RunSpec, trace: dict):
    """The trace's channel table must be §0.2d 10.7's in both modes: a group's declared steps
    forward, then the same steps reverse (the pool's steps in the pool group, every step with a
    membrane or lumen place in every slot's group, and a single lineage's likewise)."""
    table = trace.get("channels")
    if not isinstance(table, dict) or "vesicle" not in table or "pool" not in table:
        raise RecordFormatError("the trace declares no channel table (pool and vesicle fold orders)")
    m = Model(spec)
    ruled = channel_document(m)
    if table["pool"] != ruled["pool"]:
        return None, "the pool group's order is not §0.2d 5's (declared steps forwards, then reverses)"
    if table["vesicle"] != ruled["vesicle"]:
        return None, "a slot group's (or the lineage's) order is not §0.2d 10.7's (declared steps forward, then reverse)"
    if spec.mode == "population":
        return None, None
    ids = {c.id: i for i, c in enumerate(m.vch)}
    try:
        order = [(ids[a], 1 if b == "forward" else -1) for a, b in table["vesicle"]]
    except KeyError as exc:
        raise RecordFormatError(f"the channel table names an undeclared step {exc}") from exc
    if sorted(order) != sorted(ruled_order(m.vch)) or any(b not in ("forward", "reverse") for _, b in table["vesicle"]):
        raise RecordFormatError("the lineage's channel table is not one entry per step and direction")
    return order, None


def replay(spec: RunSpec, trace: dict) -> dict:
    """Rows OL2-3, OL2-4 and OL3-2 to OL3-5: rerun the reference on the trace's own uniforms,
    with the trace's own carrier keys and declared channel table."""
    spec = spec_for_trace(spec, trace)
    order, problem = declared_order(spec, trace)
    if problem:
        return dict(passed=False, events=len(trace.get("events", [])), draws=len(trace.get("draws", [])),
                    near_ties=0, differences=[dict(where="channels", problem=problem)])
    src = Recorded(trace)
    mine = simulate(spec, src, lineage_order=order)
    law = Law2(spec.world)
    scale = law.F_scale([None if s is None else Vesicle2(tuple(s["n"]), tuple(s["l"])) for s in trace["initial"]["slots"]],
                        tuple(trace["initial"]["pool"]))
    diffs = compare(mine, trace, scale)
    unused = sorted(set(src.index) - src.used)        # every recorded draw is the reference's (§0.2d 10.5)
    if unused:
        diffs.append(dict(where="unused_draws", count=len(unused), first=[list(x) for x in unused[:3]]))
    return dict(passed=not diffs, events=len(trace.get("events", [])), draws=len(trace.get("draws", [])),
                near_ties=src.ties, differences=diffs[:6])


def stream_check(trace: dict) -> dict:
    """The counters count draws (§0.2d 6, §0.2c rule 12): consecutive per address, one block per
    fission attempt of N + k + N_L, one draw per Poisson gap and per living assembly at a transfer,
    each schedule under its own declared index."""
    problems = []
    per = {}
    for d in trace.get("draws", []):
        per.setdefault((d["domain"], d["key"]), []).append(d["counter"])
        if d["domain"] not in (DOMAIN_WORLD, DOMAIN_LINEAGE):
            problems.append(dict(problem="selection draw outside domains 5 and 1", draw=[d["domain"], d["key"]]))
    for addr, cs in per.items():
        if cs != list(range(len(cs))):
            problems.append(dict(problem="selection counters not 0, 1, 2, ... (§0.2d 10.6)", address=list(addr)))
    sch = {s["index"]: s for s in trace.get("schedules", [])}
    per = {}
    for d in trace.get("schedule_draws", []):
        per.setdefault(d["schedule"], []).append(d)
        s = sch.get(d["schedule"])
        if s is None:
            problems.append(dict(problem="a domain-6 draw under an undeclared key", key=d["schedule"]))
        elif s["kind"] == "shear" and ("times_s" in s or d["use"] != "gap"):
            problems.append(dict(problem="a declared-time shear schedule drew, or a shear draw not a gap", key=d["schedule"]))
        elif s["kind"] == "transfer" and d["use"] != "transfer":
            problems.append(dict(problem="a transfer schedule's draw not a transfer draw", key=d["schedule"]))
    for key, ds in per.items():
        cs = [d["counter"] for d in sorted(ds, key=lambda d: d["counter"])]
        if cs != list(range(len(cs))):
            problems.append(dict(problem="schedule counters not 0, 1, 2, ...", key=key))
    living_before = [s for s in trace["initial"]["slots"] if s is not None]
    n_living = len(living_before)
    att = {}
    for e in trace.get("events", []):
        if e["kind"] == "transfer" and len(e.get("draws", [])) != n_living:
            problems.append(dict(problem="a transfer drew other than one uniform per living assembly", t=e["t"],
                                 living=n_living, draws=len(e.get("draws", []))))
        if e["kind"] == "shear":
            for a in e["attempts"]:
                att.setdefault(a["key"], []).append(a["counter"])
        if "slots_after" in e:
            n_living = sum(s is not None for s in e["slots_after"])
        elif e["kind"] == "step" and e.get("lysed"):
            n_living -= 1
    for key, cs in att.items():
        if cs != list(range(len(cs))):
            problems.append(dict(problem="fission counters not counting the parent's attempts", key=key))
    return dict(passed=not problems, problems=problems[:6])


def closure_check(spec: RunSpec, trace: dict) -> dict:
    """§3.3: F(final) - F(initial) = reservoir + shear + schedule work - heat - sink, from the
    trace's own states and ledger, with the reference's F."""
    law = Law2(spec.world)

    def F_of(snapshot):
        ves = [None if s is None else Vesicle2(tuple(s["n"]), tuple(s["l"])) for s in snapshot["slots"]]
        return law.F(ves, tuple(snapshot["pool"])), law.F_scale(ves, tuple(snapshot["pool"]))

    F0, s0 = F_of(trace["initial"])
    F1, s1 = F_of(trace["final"])
    tot = dict(heat=0.0, reservoir_work=0.0, shear_work=0.0, schedule_work=0.0, sink=0.0)
    for e in trace.get("events", []):
        if e["kind"] == "step":
            tot["heat"] += e["heat"]
            tot["reservoir_work"] += e["reservoir_work"]
        elif e["kind"] == "shear":
            for a in e["attempts"]:
                for f in ("heat", "reservoir_work", "shear_work", "sink"):
                    tot[f] += a.get(f, 0.0)
        else:
            tot["sink"] += e["sink"]
            tot["schedule_work"] += e["schedule_work"]
    lhs = F1 - F0
    rhs = tot["reservoir_work"] + tot["shear_work"] + tot["schedule_work"] - tot["heat"] - tot["sink"]
    tol = 1e-9 * max(s0, s1, 1.0)
    return dict(passed=abs(lhs - rhs) <= tol, dF=lhs, booked=rhs, residual=lhs - rhs, tolerance=tol, totals=tot)


def environment_check(trace: dict) -> dict:
    """§0.2d 9: the run's environment record states JAX's threefry as partitionable."""
    flag = trace.get("environment", {}).get("threefry_partitionable")
    return dict(passed=flag is True, threefry_partitionable=flag)
