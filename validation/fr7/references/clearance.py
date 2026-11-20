"""R-clear: D217's five template-clearance clauses as registered definitions.

Written from D217 ("template clearance measured from the run's trajectory"), the design note's
section 9 and the brief's clauses; numpy and scipy only, nothing imports `cells`.

1. The criterion is declared before any engine output: these functions, the threshold epsilon,
   the drive's law and every world's saved rows are registered (interface/inputs.json).
2. The threshold is on the template's remaining drive D(t) = (F_T(c*) - b)/(1 - b), with
   c* = (cytosolic n_T + sum over releasing compartments of n_T)/V. For the Hill activation,
   D = c*^n/(K^n + c*^n). epsilon is chosen so that a constant drive of epsilon moves the
   steady-state response by less than a declared resolution (`epsilon_computation`).
3. The fall-back rule: t_clear is the earliest saved time at or after the drive's peak from which
   D <= epsilon holds at every later saved row. A re-crossing voids an earlier time. The peak is
   the first saved row with the largest D; if D never exceeds epsilon, t_clear is that row.
4. Every compartment that can still release template is included: a compartment counts at a row t
   when its declared release rate is positive on some interval starting at or after t.
5. "Not cleared" (None) is the outcome when no such time exists before the end.

Plants (wrong readings of the clauses), each a keyword of `t_clear` or `c_star`, so that their
power can be shown on the synthetic trajectories (`synthetic_trajectory`).
"""

import math

import numpy as np
from scipy.linalg import expm

NOT_CLEARED = None


def hill_drive(c, K, n):
    """D = c^n/(K^n + c^n), the activation law's remaining drive (F_T - b)/(1 - b)."""
    c = np.asarray(c, dtype=float)
    with np.errstate(divide="ignore", over="ignore"):
        r = np.where(c > 0.0, (K / np.where(c > 0.0, c, 1.0)) ** n, np.inf)
    return 1.0 / (1.0 + r)


def can_release(release, t):
    """Clause 4: True when the schedule ((t_start, rate), ...) has a positive rate on an interval
    starting at or after t."""
    starts = [a for a, _ in release]
    for j, (_start, rate) in enumerate(release):
        end = starts[j + 1] if j + 1 < len(release) else math.inf
        if rate > 0.0 and end > t:
            return True
    return False


def c_star(times, n_cytosol, compartments, volume_pL, *, left_out=False, count_sealed=False):
    """c* (mM) at each saved row. `compartments` is {name: (amounts at the rows, release
    schedule)}. Plants: `left_out` drops every compartment; `count_sealed` counts a compartment
    that can no longer release."""
    total = np.array(n_cytosol, dtype=float)
    if not left_out:
        for amounts, release in compartments.values():
            mask = np.array([count_sealed or can_release(release, t) for t in times])
            total = total + np.where(mask, np.asarray(amounts, dtype=float), 0.0)
    return total / volume_pL


def t_clear(times, D, epsilon, *, basal=None, rule="fall_back", strict=False,
            end_if_not_cleared=False):
    """Clause 3's clearance time over saved rows (None: not cleared, clause 5).

    Plants: `rule="first_crossing"` ignores later rows (no fall-back); `basal` given applies the
    threshold to the factor F = b + (1 - b) D instead of D; `strict` uses D < epsilon;
    `end_if_not_cleared` returns the last row instead of "not cleared"."""
    times = list(times)
    D = np.asarray(D, dtype=float)
    if len(times) != D.size or D.size == 0:
        raise ValueError("one drive value per saved row")
    if np.any(np.diff(times) <= 0):
        raise ValueError("saved rows strictly increase")
    x = D if basal is None else basal + (1.0 - basal) * D
    ok = (x < epsilon) if strict else (x <= epsilon)
    peak = int(np.argmax(D))
    if rule == "first_crossing":
        hits = np.nonzero(ok[peak:])[0]
        return times[peak + int(hits[0])] if hits.size else (times[-1] if end_if_not_cleared
                                                             else NOT_CLEARED)
    if rule != "fall_back":
        raise ValueError("rule is fall_back or first_crossing")
    tail_ok = np.flip(np.cumprod(np.flip(ok)).astype(bool))  # ok at j and every later row
    hits = np.nonzero(tail_ok[peak:])[0]
    if hits.size:
        return times[peak + int(hits[0])]
    return times[-1] if end_if_not_cleared else NOT_CLEARED


def bracket(times, D, epsilon, t):
    """D/epsilon at the clearance row and at the row before it: the margins that make the
    clearance row unambiguous against an engine's error in D."""
    if t is None:
        return dict(at=None, before=None)
    j = list(times).index(t)
    return dict(at=float(D[j] / epsilon), before=float(D[j - 1] / epsilon) if j > 0 else None)


# ---------------------------------------------------------------- epsilon and the trace level


def epsilon_computation(basal, resolution, supplied=None):
    """Clause 2's threshold, shown.

    At any precursor level n_P held fixed, the units' steady state is N* = c_u k_a F n_P/k_r
    (every stage carries c_u k_a F n_P/kappa), so a constant drive D moves it by the relative
    amount (1 - b) D/b from the basal F = b. With a supply S_P and a clearance k_P the steady
    state is N* = c_u S_P k_a F/(k_r (k_P + k_a F)), whose relative move,
    (F_eps - b) k_P/(b (k_P + k_a F_eps)), is smaller. So epsilon <= resolution b/(1 - b) holds
    the steady-state response (units, and so the conductance P N/rho_ref) within the resolution
    in every precursor regime. `supplied` = (k_a, k_P) evaluates the supplied form too."""
    eps_max = resolution * basal / (1.0 - basal)
    exponent = math.floor(math.log10(eps_max))
    mantissa = math.floor(eps_max / 10.0 ** exponent)
    eps = mantissa * 10.0 ** exponent  # one significant digit, rounded down
    out = dict(resolution_relative=resolution, basal=basal, epsilon_max=eps_max, epsilon=eps,
               held_precursor_move=(1.0 - basal) * eps / basal)
    if supplied is not None:
        ka, kP = supplied
        F_eps = basal + (1.0 - basal) * eps
        out["supplied_move"] = (F_eps - basal) * kP / (basal * (kP + ka * F_eps))
    return out


def trace_level(epsilon, K, n):
    """The template concentration at which D = epsilon: K (epsilon/(1 - epsilon))^(1/n)."""
    return K * (epsilon / (1.0 - epsilon)) ** (1.0 / n)


# ---------------------------------------------------------------- synthetic trajectories


def synthetic_trajectory(case, common, times):
    """Amounts at the rows for a synthetic case: a cytosolic template with D150's turnover
    (production schedule, clearance k_T) and compartments that release into the cytosol at
    piecewise-constant rates and degrade at their own rate. Exact per segment by the matrix
    exponential of the linear system. Returns (n_cytosol, {name: amounts}, {name: release})."""
    comps = case["compartments"]
    names = list(comps)
    k_T = common["clearance_per_s"]
    edges = {0.0, *map(float, times)}
    edges |= {float(a) for a, _ in case["production"]}
    for c in comps.values():
        edges |= {float(a) for a, _ in c["release"]}
    edges = sorted(e for e in edges if 0.0 <= e <= max(times))

    def value(schedule, t0, t1):
        mid, v = 0.5 * (t0 + t1), schedule[0][1]
        for a, x in schedule:
            if a > mid:
                break
            v = x
        return v

    size = 2 + len(names)
    y = np.zeros(size)
    y[0] = case["n0_fmol"]
    for i, name in enumerate(names):
        y[1 + i] = comps[name]["n0_fmol"]
    y[-1] = 1.0
    out = {edges[0]: y.copy()}
    for t0, t1 in zip(edges, edges[1:], strict=False):
        A = np.zeros((size, size))
        A[0, 0] = -k_T
        A[0, -1] = value(case["production"], t0, t1)
        for i, name in enumerate(names):
            r = value(comps[name]["release"], t0, t1)
            A[0, 1 + i] = r
            A[1 + i, 1 + i] = -(r + comps[name]["degradation_per_s"])
        y = expm(A * (t1 - t0)) @ y
        out[t1] = y.copy()
    rows = np.array([out[float(t)] for t in times])
    return (rows[:, 0], {name: rows[:, 1 + i] for i, name in enumerate(names)},
            {name: [tuple(x) for x in comps[name]["release"]] for name in names})


PLANTS = {
    "compartment_left_out": dict(c_star=dict(left_out=True)),
    "sealed_compartment_counted": dict(c_star=dict(count_sealed=True)),
    "first_crossing_no_fall_back": dict(t_clear=dict(rule="first_crossing")),
    "threshold_on_the_factor": dict(t_clear=dict(basal=True)),
    "strict_inequality": dict(t_clear=dict(strict=True)),
    "end_time_if_not_cleared": dict(t_clear=dict(end_if_not_cleared=True)),
}


def evaluate_case(case, common, times, plant=None):
    """(t_clear, D at the rows, c* at the rows) for one synthetic case, under a plant or none."""
    spec = PLANTS[plant] if plant else {}
    n_cyt, amounts, release = synthetic_trajectory(case, common, times)
    comps = {name: (amounts[name], release[name]) for name in amounts}
    cs = c_star(times, n_cyt, comps, common["volume_pL"], **spec.get("c_star", {}))
    D = hill_drive(cs, common["K_mM"], common["n"])
    kw = dict(spec.get("t_clear", {}))
    if kw.get("basal") is True:
        kw["basal"] = common["basal"]
    return t_clear(times, D, common["epsilon"], **kw), D, cs
