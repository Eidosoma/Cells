"""A host oracle of version 2: the kernel's events replayed from supplied uniforms, in NumPy.

At every state the oracle recomputes the rate factor's and the excess terms' states exactly from
the counts (the kernel keeps them incrementally), takes the kernel's own rate function on the host,
and draws with the run's saved uniforms by the same convention (kernel.SSA_CONVENTION): a cumulative
sum in channel order, τ = −ln(u1)/a0, and the first channel whose partial total exceeds
min(u2 a0, nextafter(a0, 0)). A run's trace must agree with it: channels exactly (but for a
threshold coincidence at rounding) and times to a relative 1e-12, since the two keep the factor's
and terms' states by different arithmetic.

`reverse_weight` (diagnostic, a planted error): every reverse channel's rate scaled before the draw,
which a replay must disagree with.
"""

import numpy as np

from cells.models.assembly_lineages_v2 import kernel, model, runner


def replay(spec, uniforms, *, reverse_weight=1.0):
    """(channel codes, times) of the events drawn with `uniforms` [events, 2] from the founder."""
    structure, layout = model.structure(spec), model.layout(spec)
    counts = model.founder(spec).copy()
    count_change, _ = runner.changes(layout, structure)
    R = structure.steps
    horizon = spec.experiment.time_horizon_s
    time, channels, times = 0.0, [], []
    for u1, u2 in np.asarray(uniforms, dtype=np.float64):
        totals = kernel.totals_of(counts, layout, np)
        factor_state, term_states = kernel.states(counts, totals, layout, structure, np)
        rates = kernel.rates(counts, totals, factor_state, term_states, layout, structure, np)
        rates = np.concatenate((rates[:R], rates[R:] * reverse_weight))
        prefix = np.cumsum(rates)
        total = prefix[-1]
        if not (np.isfinite(total) and total > 0):
            break
        wait = -np.log(u1) / total
        if time + wait > horizon:
            break
        threshold = min(u2 * total, np.nextafter(total, 0.0))
        j = int(np.argmax(prefix > threshold))
        time = time + wait
        counts = counts + count_change[j]
        channels.append(j + 1 if j < R else -(j - R + 1))
        times.append(time)
    return np.asarray(channels, dtype=np.int32), np.asarray(times, dtype=np.float64)
