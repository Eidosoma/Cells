"""Conduction observables as a host analysis (Track E, EXCITABLE_TISSUE_DESIGN.md section 5; M1).

One owner for each observable's definition, as pure functions on saved series (numpy arrays of
rows; columns are cells, membranes or junctions). Drivers, judges and references read the same
definitions, and none of them executes the engine. The definitions follow the design note's
section 5 and the equations appendix's section 8, with M1's revisions:

- **Activation time.** Every upward crossing of a declared level after a declared arming time,
  interpolated linearly between the two rows that bracket it; the first is the activation time.
- **Conduction velocity.** The inverse least-squares slope of activation time against path
  distance over a declared span; None when a cell in the span did not activate.
- **The cell's own upstroke.** Its largest dVm/dt after a declared time and, over its rise from a
  declared start level to its peak, the inward part of its net ionic membrane current
  integrated (its inward charge) and its most inward value. The source fraction is the inward
  charge over C (V_peak - V_rest). A passive cell is a pure sink: zero inward charge. Net ionic
  current is outward positive (the engine's membrane_current_A).
- **Launched front (capture).** Every cell activates; every source (stimulated) cell activates
  within its stimulus; the mean activation per graph-distance ring from the sources rises
  strictly with distance; and every ring at distance >= 2 activates after the stimulus ends.
- **Action-potential duration.** From a declared reference time: the stimulus end in a stimulus
  run (appendix section 8.3: the largest dV/dt there is the stimulus onset's), the largest
  dV/dt in a kicked run. APDx is the first time after the peak at which V falls below
  V_peak - x (V_peak - V_rest), less the reference time.
- **Brackets.** For an outcome that flips once along a parameter: the largest value with the
  first outcome and the smallest with the second, and whether they are ordered.
"""

from collections import deque

import numpy as np

ACTIVATION_LEVEL_V = -0.030
RISE_START_V = -0.050


def crossings(t, v, level, *, after=None):
    """Every upward crossing of level by v(t), linearly interpolated, at or after `after`.

    A crossing lies between rows i-1 and i with v[i-1] < level <= v[i]; it is kept when its
    interpolated time is at or after `after` (None keeps all).
    """
    t, v = np.asarray(t, dtype=float), np.asarray(v, dtype=float)
    out = []
    for i in range(1, len(v)):
        a, b = v[i - 1], v[i]
        if a < level <= b:
            when = float(t[i - 1] + (level - a) * (t[i] - t[i - 1]) / (b - a))
            if after is None or when >= after:
                out.append(when)
    return out


def activation_times(t, vm, *, level=ACTIVATION_LEVEL_V, after=None):
    """Per column: (first crossing or None, every crossing)."""
    vm = np.asarray(vm, dtype=float)
    every = [crossings(t, vm[:, i], level, after=after) for i in range(vm.shape[1])]
    return [c[0] if c else None for c in every], every


def conduction_velocity(activation, distance, span):
    """The inverse least-squares slope of activation time against distance over span (indices).

    Returns dict(per_unit=velocity in distance units per second, slope_s, intercept_s,
    rms_residual_s), or None when a cell in the span did not activate or the slope is not
    positive.
    """
    idx = list(span)
    if len(idx) < 2 or any(activation[i] is None for i in idx):
        return None
    x = np.asarray([distance[i] for i in idx], dtype=float)
    y = np.asarray([activation[i] for i in idx], dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    if slope <= 0:
        return None
    rms = float(np.sqrt(np.mean((y - (slope * x + intercept)) ** 2)))
    return dict(
        per_unit=float(1.0 / slope),
        slope_s=float(slope),
        intercept_s=float(intercept),
        rms_residual_s=rms,
    )


def upstroke(t, vm, im, dvdt, capacitance, *, after, rest_index, rise_start=RISE_START_V):
    """Each column's own upstroke (see the module docstring).

    after: per-column times (or one time) from which the column is read, for example the
    stimulus end for a stimulated cell and the stimulus onset for the others. rest_index: the
    row whose voltage is V_rest. Returns lists per column: max_dvdt_V_s, inward_charge_C,
    peak_inward_A, rise_charge_C, source_fraction and rise_start_s (None when the column never
    reaches the start level before its peak).
    """
    t = np.asarray(t, dtype=float)
    vm, im, dvdt = (np.asarray(a, dtype=float) for a in (vm, im, dvdt))
    n = vm.shape[1]
    after = np.broadcast_to(np.asarray(after, dtype=float), (n,))
    dts = np.diff(t, prepend=t[0])
    out = {
        k: []
        for k in (
            "max_dvdt_V_s",
            "inward_charge_C",
            "peak_inward_A",
            "rise_charge_C",
            "source_fraction",
            "rise_start_s",
        )
    }
    for i in range(n):
        s0 = int(np.searchsorted(t, after[i]))
        if s0 >= len(t):
            for k in out:
                out[k].append(None)
            continue
        out["max_dvdt_V_s"].append(float(dvdt[s0:, i].max()))
        k_peak = s0 + int(np.argmax(vm[s0:, i]))
        above = np.flatnonzero(vm[s0 : k_peak + 1, i] >= rise_start)
        rise = float(capacitance[i] * (vm[k_peak, i] - vm[rest_index, i]))
        if above.size == 0:
            q_in, peak_in, start = 0.0, 0.0, None
        else:
            k0 = s0 + int(above[0])
            seg = im[k0 : k_peak + 1, i]
            q_in = float(np.sum(np.maximum(-seg, 0.0) * dts[k0 : k_peak + 1]))
            peak_in = float(max(-seg.min(), 0.0))
            start = float(t[k0])
        out["inward_charge_C"].append(q_in)
        out["peak_inward_A"].append(peak_in)
        out["rise_charge_C"].append(rise)
        out["source_fraction"].append(q_in / rise if rise > 0 else 0.0)
        out["rise_start_s"].append(start)
    return out


def graph_distances(n, edges, sources):
    """Breadth-first graph distance of every node from the source set (None if unreachable)."""
    nbrs = [[] for _ in range(n)]
    for a, b in edges:
        nbrs[a].append(b)
        nbrs[b].append(a)
    dist = [None] * n
    queue = deque()
    for s in sources:
        dist[s] = 0
        queue.append(s)
    while queue:
        i = queue.popleft()
        for j in nbrs[i]:
            if dist[j] is None:
                dist[j] = dist[i] + 1
                queue.append(j)
    return dist


def launched_front(activation, sources, edges, *, on_s, off_s):
    """The launched-front rule (see the module docstring), with its parts and ring means."""
    n = len(activation)
    dist = graph_distances(n, edges, sources)
    reached = [d for d in dist if d is not None]
    top = max(reached) if reached else 0
    means = []
    for d in range(top + 1):
        ts = [activation[i] for i in range(n) if dist[i] == d and activation[i] is not None]
        means.append(float(np.mean(ts)) if ts else None)
    all_cross = all(x is not None for x in activation)
    within = all(activation[i] is not None and on_s <= activation[i] <= off_s for i in sources)
    rising = all(
        x is not None and y is not None and y > x for x, y in zip(means, means[1:], strict=False)
    )
    outruns = all(m is not None and m > off_s for m in means[2:])
    return dict(
        ring_mean_activation_s=means,
        all_cross=all_cross,
        sources_within_stimulus=within,
        rings_rise=rising,
        outruns_stimulus=outruns,
        launched=bool(all_cross and within and rising and outruns),
    )


def falling(t, v, level, start):
    """The first downward crossing of level at or after row start, linearly interpolated."""
    t, v = np.asarray(t, dtype=float), np.asarray(v, dtype=float)
    for i in range(max(start, 1), len(v)):
        a, b = v[i - 1], v[i]
        if a >= level > b:
            return float(t[i - 1] + (a - level) * (t[i] - t[i - 1]) / (a - b))
    return None


def action_potential(t, v, *, reference_s, rest_V, fractions=(0.5, 0.9)):
    """Peak after the reference time and APDx from it (see the module docstring)."""
    t, v = np.asarray(t, dtype=float), np.asarray(v, dtype=float)
    first = int(np.searchsorted(t, reference_s))
    if first >= len(t):
        return None
    k = first + int(np.argmax(v[first:]))
    peak = float(v[k])
    out = dict(peak_V=peak, time_to_peak_s=float(t[k] - reference_s), reference_s=reference_s)
    amplitude = peak - rest_V
    for x in fractions:
        cross = falling(t, v, peak - x * amplitude, k)
        out[f"apd{int(round(100 * x))}_s"] = None if cross is None else cross - reference_s
    return out


def largest_dvdt_time(t, v, *, after=None):
    """The kicked run's reference: the midpoint of the rows with the largest dV/dt after `after`."""
    t, v = np.asarray(t, dtype=float), np.asarray(v, dtype=float)
    first = 0 if after is None else int(np.searchsorted(t, after))
    dv = np.diff(v[first:]) / np.diff(t[first:])
    k = first + int(np.argmax(dv))
    return float(0.5 * (t[k] + t[k + 1]))


def bracket(rows):
    """rows [(value, flipped)]: the largest value that flips and the smallest that does not."""
    flipped = [r for r, f in rows if f]
    kept = [r for r, f in rows if not f]
    hi = max(flipped) if flipped else None
    lo = min(kept) if kept else None
    return dict(
        largest_flipping=hi,
        smallest_not_flipping=lo,
        ordered=hi is None or lo is None or hi < lo,
    )
