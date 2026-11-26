"""A host oracle for the lineage kernel: scalar arithmetic replaying supplied uniforms.

No JAX and no kernel code: the oracle evaluates the declared convention (kernel.SSA_CONVENTION;
fission.py; continuation.py) with plain Python floats and NumPy integers, from the uniforms a
diagnostic run saves (event_uniforms, partition_uniforms, continuation_uniform), so the kernel's
events can be compared with common random variates (the capsid pattern, cells/assembly).

Its own choices, apart from the kernel's:
- the rate factor's state is recomputed from the counts at every event (beta n, a serial fold
  over the types; for cells.rate_factor.gard_catalysis_pair_consistent@2, in rationals, rounded once, which
  is what the kernel's exact cache gives), never updated incrementally;
- only the declared types are evaluated (no capacity padding);
- the channel is found by a scalar running total, and the split by a stable argsort.
The products are formed in the kernel's declared order ((kf rho) N g; (kb n) g) and the folds are
serial, so the oracle's rates agree with the kernel's to rounding: event sequences are compared
exactly, times to a relative 1e-12.
"""

import math
from fractions import Fraction

import numpy as np

from cells.models.assembly_lineages import (
    GARD_PAIR_CONSISTENT,
    GARD_PAIR_CONSISTENT_V2,
    GARD_SINGLE_EVENT,
)


def _factors(form, counts, size, beta):
    """(join, leave) factors per type, from a fresh beta n."""
    count = len(counts)
    if form is None:
        return [1.0] * count, [1.0] * count
    if form == GARD_PAIR_CONSISTENT_V2:
        return _factors_exact(counts, size, beta)
    x = []
    for i in range(count):
        total = beta[i][0] * float(counts[0])
        for j in range(1, count):
            total = total + beta[i][j] * float(counts[j])
        x.append(total)
    join = [1.0 + x[i] / size if size > 0 else 1.0 for i in range(count)]
    if form == GARD_SINGLE_EVENT:
        return join, join
    leave = [
        1.0 + (x[i] - beta[i][i]) / (size - 1.0) if size > 1 and counts[i] > 0 else 1.0
        for i in range(count)
    ]
    return join, leave


def _factors_exact(counts, size, beta):
    """@2's pair-consistent factors: beta n in rationals, rounded once (float of a Fraction is
    correctly rounded), and the leave's (beta n)_i - beta_ii likewise."""
    count = len(counts)
    x = [
        sum((Fraction(beta[i][j]) * int(counts[j]) for j in range(count)), Fraction(0))
        for i in range(count)
    ]
    join = [1.0 + float(x[i]) / size if size > 0 else 1.0 for i in range(count)]
    leave = [
        1.0 + float(x[i] - Fraction(beta[i][i])) / (size - 1.0)
        if size > 1 and counts[i] > 0
        else 1.0
        for i in range(count)
    ]
    return join, leave


def replay(spec, event_uniforms, partition_uniforms, continuation_uniform):
    """The lineage the declared convention gives from these uniforms.

    Returns {"time": [...], "channel": [...], "splits": [first daughter counts per fission],
    "followed": [...], "similarity": [(h1, h2), ...], "status": str}."""
    world = spec.model.world
    form = spec.model.rate_factor
    if form not in (None, GARD_SINGLE_EVENT, GARD_PAIR_CONSISTENT, GARD_PAIR_CONSISTENT_V2):
        raise ValueError(f"The oracle knows no rate factor {form}")
    count = world.types.count
    beta = [list(row) for row in world.data["catalysis_matrix"]] if form else None
    kf_rho = [
        (k * b) * r
        for k, b, r in zip(
            world.types.transfer_constant, world.leave_rate, world.supply, strict=True
        )
    ]
    kb = list(world.leave_rate)
    counts = np.asarray(world.founder, dtype=np.int64)
    partition, chooser = world.fission.partition, world.continuation
    out = {
        "time": [],
        "channel": [],
        "splits": [],
        "followed": [],
        "similarity": [],
        "status": None,
    }
    clock, age, draw = 0.0, 0, 0
    limit = spec.experiment.growth_event_limit
    while True:
        size = int(counts.sum())
        gj, gl = _factors(form, counts, float(size), beta)
        rates = [(kf_rho[i] * float(size)) * gj[i] for i in range(count)]
        rates += [(kb[i] * float(counts[i])) * gl[i] for i in range(count)]
        running, partial = 0.0, []
        for value in rates:
            running = running + value
            partial.append(running)
        if draw >= len(event_uniforms):
            out["status"] = "uniforms_exhausted"
            return out
        u1, u2 = (float(u) for u in event_uniforms[draw])
        draw += 1
        clock = clock + (-math.log(u1) / running)
        threshold = min(u2 * running, math.nextafter(running, 0.0))
        channel = next(j for j, value in enumerate(partial) if value > threshold)
        kind, join = channel % count, channel < count
        counts[kind] += 1 if join else -1
        size += 1 if join else -1
        age += 1
        out["time"].append(clock)
        out["channel"].append(kind + 1 if join else -(kind + 1))
        if size == 0:
            out["status"] = "extinct"
            return out
        if join and size == world.fission.size:
            while True:  # A daughter born at the fission size splits at once.
                k = len(out["splits"])
                first = _split(counts, size, partition_uniforms[k], partition)
                second = counts - first
                sizes = (int(first.sum()), int(second.sum()))
                pick = _choose(chooser, continuation_uniform[k], sizes)
                out["splits"].append(first)
                out["followed"].append(pick)
                out["similarity"].append((_cosine(counts, first), _cosine(counts, second)))
                counts = (first if pick == 0 else second).copy()
                size = sizes[pick]
                age = 0
                if size == 0:
                    out["status"] = "extinct"
                    return out
                if len(out["splits"]) >= spec.experiment.fissions:
                    out["status"] = "complete"
                    return out
                if size < world.fission.size:
                    break
        elif age >= limit:
            out["status"] = "event_limit"
            return out


def _split(counts, size, places, partition):
    kinds = np.repeat(np.arange(len(counts)), counts)  # Molecule places, by type in order.
    places = np.asarray(places[:size], dtype=np.float64)
    if partition.rule == "exact_fraction":
        take = math.floor(partition.value * size)
        chosen = np.argsort(places, kind="stable")[:take]
    else:
        chosen = np.flatnonzero(places < partition.value)
    return np.bincount(kinds[chosen], minlength=len(counts)).astype(np.int64)


def _choose(rules, uniform, sizes):
    pick = {"first": 0, "second": 1}.get(rules.daughter)
    if pick is None:
        pick = 0 if uniform < 0.5 else 1
    if rules.empty == "other" and sizes[pick] == 0 and sizes[1 - pick] > 0:
        pick = 1 - pick
    return pick


def _cosine(a, b):
    dot, aa, bb = int(np.dot(a, b)), int(np.dot(a, a)), int(np.dot(b, b))
    return dot / math.sqrt(float(aa) * float(bb)) if aa and bb else math.nan
