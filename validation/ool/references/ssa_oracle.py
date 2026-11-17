"""Row OL1-4c: the SSA is the exact direct method on the law's propensities; and the host SSA
that writes the stand-in records.

Claim (§7.1, §7.2). The engine's stochastic simulation is Gillespie's direct method (Gillespie
1977, from memory) on the event-pair propensities: from state n with channel propensities a_j
(in the declared channel table's order) and total a0, the waiting time is tau = -ln(u1)/a0 and
the channel is the first j whose left-fold prefix sum exceeds u2 a0.

**The oracle.** Given a run's declared convention, its channel table and the uniforms it consumed
(diagnostic mode), the next event is fully determined. The oracle replays the run event by event
from its initial state with the reference's propensities:
- every channel must agree, except near-ties: u2 a0 within ``TIE_RTOL`` of a prefix boundary,
  where summation order can legitimately flip the choice. Near-ties are counted and reported,
  and the replay then follows the recorded channel;
- every event time must agree to ``TIME_RTOL`` (relative to the time);
- a run that declares no convention, or an unknown token, is refused (status 2).

Planted controls: a biased channel choice (reverse channels at 0.9 of their weight) and the
``power_propensity`` law. Under common variates each changes a channel at once.

**The float rates.** ``FloatRates`` evaluates the same propensities as ``laws.Law`` in float64,
the reverse by the products' rule, which equals the F path exactly (``laws`` docstring). It is
fast enough for long runs; the tests hold it to the exact law within 1e-13 relative on every
probe state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .common import CheckResult, RecordFormatError
from .laws import Law

TIE_RTOL = 1e-12
TIME_RTOL = 1e-12
PLANTED_REVERSE_WEIGHT = 0.9

TAU_NEG_LOG_U1 = "neg_log_u1_over_a0"
SELECT_FIRST_PREFIX_GT = "first_prefix_gt_u2_a0"
SSA_TOKENS = {"tau": (TAU_NEG_LOG_U1,), "select": (SELECT_FIRST_PREFIX_GT,)}


@dataclass(frozen=True)
class ChannelTable:
    """The declared channel table: row j fires step ``step[j]`` in direction ``sign[j]`` (+1
    forward, -1 reverse); the prefix sums fold in this order. Each channel appears once."""

    step: tuple
    sign: tuple
    code: tuple

    @staticmethod
    def default(law: Law) -> "ChannelTable":
        """Each step's forward channel, then its reverse, in the world's step order."""
        steps, signs, codes = [], [], []
        for r in range(len(law.world.steps)):
            for s in (1, -1):
                steps.append(r)
                signs.append(s)
                codes.append(len(codes))
        return ChannelTable(tuple(steps), tuple(signs), tuple(codes))

    @staticmethod
    def from_declared(rows, law: Law) -> "ChannelTable":
        if not isinstance(rows, list) or not rows:
            raise RecordFormatError("the run declares no channel table")
        names = [st.name for st in law.world.steps]
        steps, signs, codes, seen = [], [], [], set()
        for k, row in enumerate(rows):
            try:
                r, s, c = names.index(row["step"]), int(row["direction"]), int(row["code"])
            except (KeyError, ValueError, TypeError) as exc:
                raise RecordFormatError(f"channel row {k} needs step, direction and code") from exc
            if s not in (1, -1) or (r, s) in seen:
                raise RecordFormatError(f"channel row {k}: direction {s} of {names[r]} invalid or repeated")
            seen.add((r, s))
            steps.append(r)
            signs.append(s)
            codes.append(c)
        if len(seen) != 2 * len(names) or len(set(codes)) != len(codes):
            raise RecordFormatError("the channel table must list each step's two channels once, with unique codes")
        return ChannelTable(tuple(steps), tuple(signs), tuple(codes))


def check_convention(declared: dict | None) -> None:
    if not isinstance(declared, dict):
        raise RecordFormatError("the run declares no SSA convention; the oracle refuses it")
    for key, allowed in SSA_TOKENS.items():
        if declared.get(key) not in allowed:
            raise RecordFormatError(f"SSA convention {key}={declared.get(key)!r} is not in {allowed}")


class FloatRates:
    """The law's propensities in float64 (forward rule, and the products' rule for the reverse)."""

    def __init__(self, law: Law):
        self.law = law
        w = law.world
        self.steps = w.steps
        self.mem = np.array(law.mem)
        self.chi = np.array([[float(v) for v in row] for row in law.chi])
        self.k = np.array([float(st.rate.exact) for st in self.steps])
        self.k_minus = np.array([float(law.k_minus(st)) for st in self.steps])
        self.nu = np.array([law.nu[st.name] for st in self.steps], dtype=np.int64)
        self.alpha = np.array([law.alpha[st.name] for st in self.steps], dtype=np.int64)
        self.beta = np.array([law.beta[st.name] for st in self.steps], dtype=np.int64)
        self.X = {i: float(x) for i, x in law.Xp.items()}
        c0 = w.c0_mM.exact
        self.held_r = [math.prod(float(w.places[p].held_mM.exact / c0) ** a for p, a in st.reactants.items()
                                 if w.places[p].held) for st in self.steps]
        self.held_p = [math.prod(float(w.places[p].held_mM.exact / c0) ** a for p, a in st.products.items()
                                 if w.places[p].held) for st in self.steps]
        self.cats = [[(j, float(b)) for j, b in law.cat[st.name]] for st in self.steps]
        self.locus_X = [float(law.X(st.locus)) if st.locus != "membrane" else None for st in self.steps]
        self.c = law.c
        self.last = law.conv.last_molecule
        self.planted_bias = None

    def N(self, n) -> int:
        return int(np.sum(np.asarray(n)[self.mem]))

    def R(self, n) -> float:
        n = np.asarray(n, float)
        N = float(np.sum(n[self.mem]))
        if N == 0:
            return 0.0
        nm = np.where(self.mem, n, 0.0)
        return float(nm @ self.chi @ nm) / (2 * N)

    @staticmethod
    def ff(v: int, a: int) -> float:
        out = 1.0
        for j in range(a):
            out *= v - j
        return out if v >= a else 0.0

    def _extent(self, r, m) -> float:
        if self.locus_X[r] is not None:
            return self.locus_X[r]
        return float(self.N(m) - self.c + 1)

    def _draw(self, r, counts, coeff, m) -> float:
        """E(m) times one side's draw (the law's ``draw``): cancelled where 0/0, +inf where singular."""
        num, r_mem, dil = 1.0, 0, 1.0
        for i, a in enumerate(coeff):
            if not a:
                continue
            if counts[i] < a:
                return 0.0
            if self.mem[i]:
                num *= self.ff(int(counts[i]), int(a))
                r_mem += int(a)
            else:
                dil *= self.ff(int(counts[i]), int(a)) / self.X[i] ** a
        E = self._extent(r, m)
        if self.locus_X[r] is not None or r_mem == 0:
            return dil * num * E
        N = self.N(counts)
        den = self.ff(N - self.c, r_mem) if N - self.c >= 0 else 0.0
        if den:
            return dil * num * E / den
        if E == 0:
            return dil * num / self.ff(N - 1, r_mem - 1)
        return math.inf

    def _g(self, r, m) -> float:
        if not self.cats[r]:
            return 1.0
        N = self.N(m)
        if N == 0:
            return 1.0
        return 1.0 + sum(b * m[j] for j, b in self.cats[r]) / N

    def _kept_zero(self, r, n, p) -> bool:
        return self.last == "kept" and self.locus_X[r] is None and (self.N(n) == 0 or self.N(p) == 0)

    def forward(self, r, n) -> float:
        n = np.asarray(n)
        p = n + self.nu[r]
        if np.any(p < 0) or np.any(n < self.alpha[r]) or self._kept_zero(r, n, p):
            return 0.0
        m = np.minimum(n, p)
        d = self._draw(r, n, self.alpha[r], m)
        if d == 0.0 or math.isinf(d):
            return d
        return self.k[r] * self._g(r, m) * d * self.held_r[r]

    def reverse(self, r, p) -> float:
        p = np.asarray(p)
        n = p - self.nu[r]
        if np.any(n < 0) or np.any(n < self.alpha[r]) or self._kept_zero(r, n, p):
            return 0.0
        m = np.minimum(n, p)
        d = self._draw(r, p, self.beta[r], m)
        if d == 0.0 or math.isinf(d):
            return d
        return self.k_minus[r] * self._g(r, m) * d * self.held_p[r] * math.exp(self.R(p) - self.R(n))

    def channel_rates(self, n, table: ChannelTable) -> np.ndarray:
        out = np.empty(len(table.step))
        for j, (r, s) in enumerate(zip(table.step, table.sign)):
            out[j] = self.forward(r, n) if s > 0 else self.reverse(r, n)
        if self.planted_bias is not None:
            out = out * np.where(np.asarray(table.sign) < 0, self.planted_bias, 1.0)
        return out


def left_fold(a: np.ndarray) -> np.ndarray:
    out = np.empty_like(a)
    acc = 0.0
    for j, v in enumerate(a):
        acc = acc + v
        out[j] = acc
    return out


def select(prefix: np.ndarray, target: float) -> int:
    j = int(np.searchsorted(prefix, target, side="right"))
    return min(j, len(prefix) - 1)


def run_host_ssa(rates: FloatRates, table: ChannelTable, n0, t_end: float, rng: np.random.Generator,
                 max_events: int = 10 ** 7, true_total: bool = True) -> dict:
    """The host direct method, free running; records the trace and the uniforms it used.

    With ``rates.planted_bias`` set, channel selection uses the biased weights while the time
    is drawn from the true total (``true_total``), the planted control's definition."""
    n = np.array(n0, dtype=np.int64)
    t = 0.0
    times, codes, uniforms = [], [], []
    bias = rates.planted_bias
    end_reason = "max_events"
    for _ in range(max_events):
        rates.planted_bias = None
        a = rates.channel_rates(n, table)
        if np.any(np.isinf(a)):
            end_reason = "stalled"      # §0.2b rule 8: a singular rate is never fired
            break
        a0 = float(left_fold(a)[-1]) if a.size else 0.0
        if a0 <= 0:
            end_reason = "no_channel"
            break
        u1, u2 = rng.random(), rng.random()
        while u1 == 0.0:
            u1 = rng.random()
        tau = -math.log(u1) / a0
        if t + tau > t_end:
            end_reason = "t_end"
            break
        t += tau
        weights = a if bias is None else a * np.where(np.asarray(table.sign) < 0, bias, 1.0)
        prefix = left_fold(weights)
        j = select(prefix, u2 * prefix[-1])
        r, s = table.step[j], table.sign[j]
        n = n + s * rates.nu[r]
        times.append(t)
        codes.append(table.code[j])
        uniforms.append((u1, u2))
    rates.planted_bias = bias
    return dict(event_time=np.array(times), event_channel=np.array(codes, dtype=np.int64),
                event_uniforms=np.array(uniforms).reshape(-1, 2), final_state=n, end_reason=end_reason)


def replay(rates: FloatRates, table: ChannelTable, n0, event_time, event_channel, event_uniforms) -> CheckResult:
    """Row OL1-4c: replay a diagnostic run under common variates."""
    n = np.array(n0, dtype=np.int64)
    t = 0.0
    code_to_row = {c: j for j, c in enumerate(table.code)}
    E = len(event_channel)
    if event_uniforms.shape != (E, 2):
        return CheckResult("ssa_replay", False, dict(problem=f"event_uniforms shape {event_uniforms.shape}, ({E}, 2) expected"))
    mismatch, ties, worst_time = [], 0, 0.0
    for e in range(E):
        a = rates.channel_rates(n, table)
        if np.any(np.isinf(a)):
            mismatch.append(dict(event=e, problem="a singular rate at this state: the run should have stopped "
                                                  "stalled (§0.2b rule 8)", state=n.tolist()))
            break
        prefix = left_fold(a)
        a0 = float(prefix[-1])
        u1, u2 = float(event_uniforms[e, 0]), float(event_uniforms[e, 1])
        if a0 <= 0 or not (0 < u1 < 1) or not (0 <= u2 < 1):
            mismatch.append(dict(event=e, problem="no positive total or a uniform outside (0, 1)"))
            break
        t += -math.log(u1) / a0
        rel = abs(t - float(event_time[e])) / max(abs(t), 1e-300)
        worst_time = max(worst_time, rel)
        target = u2 * a0
        j = select(prefix, target)
        recorded = code_to_row.get(int(event_channel[e]))
        if recorded is None:
            mismatch.append(dict(event=e, problem=f"unknown channel code {int(event_channel[e])}"))
            break
        if j != recorded:
            near = np.min(np.abs(prefix - target)) <= TIE_RTOL * a0
            if near:
                ties += 1
            else:
                mismatch.append(dict(event=e, oracle=table.code[j], engine=int(event_channel[e]), state=n.tolist()))
                if len(mismatch) >= 5:
                    break
            j = recorded
        if rel > TIME_RTOL and len(mismatch) < 5:
            mismatch.append(dict(event=e, problem="time", oracle=t, engine=float(event_time[e])))
        r, s = table.step[j], table.sign[j]
        n = n + s * rates.nu[r]
        t = float(event_time[e])
    return CheckResult("ssa_replay", not mismatch, dict(events=E, near_ties=ties, max_rel_time_error=worst_time,
                                                        mismatches=mismatch[:5]))
