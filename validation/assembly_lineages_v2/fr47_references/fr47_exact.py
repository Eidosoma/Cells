"""FR-47's code-blind references, method 1: exact closed forms in decimal arithmetic.

Written from the spec folder ``validation/assembly_lineages_v2/fr47_spec/`` (SPEC.md, CRITERIA.md
and AMENDMENT-2026-11-23.md, as of fr47-protocol 59cb1a12) and from
``docs/FR47_SHELL_EXCHANGE_PROTOCOL.md``, and from nothing else. Nothing here imports, reads or runs
the engine.

Method 1 gives the values the writer writes. Every quantity is a closed form evaluated in decimal
arithmetic at ``prec`` significant digits (60 by default). The writer rounds each value once, to
the nearest float. The generator re-evaluates everything at a higher precision and requires the
same floats, and ``fr47_numeric.py`` (float64 linear algebra and ODE solvers) checks every quantity
by an independent route.

Why the closed forms are exact
------------------------------
Shell worlds (W1, W1D; SPEC.md section 1). Every tracer molecule moves independently:
  - it enters the lumen at kappa_in and leaves it at kappa_out;
  - at a withdrawal it is removed with probability exactly f when in the pool, and at the
    replacement every pool molecule is removed.

  So a molecule's law is a two-state relaxation between stops and a linear map at each stop. A
  count is a sum of independent indicators, one per founder molecule: a sum of binomials, one per
  founder place. Its cumulants are the sums of the indicators' cumulants: mean = sum n p,
  var = sum n p q, kappa4 = sum n p q (1 - 6 p q), and mu4 = kappa4 + 3 var^2.

Gated worlds (W2; SPEC.md sections 1 and 3.3). Given the gate's path K(s), each molecule moves
independently with rates g(K) kappa_in and g(K) kappa_out. So its lumen probability depends on the
path only through Phi(t) = int_0^t g(K(s)) ds:
  - born in the pool: p = pi1 (1 - Y);
  - born in the lumen: p = pi1 + pi0 Y;
  - here Y = exp(-lambda Phi), lambda = kappa_in + kappa_out, pi1 = kappa_in/lambda and
    pi0 = kappa_out/lambda.

  Given the path, each count is a sum of binomials, whose raw moments are polynomials in Y of
  degree <= 4. So the exact moments need E[Y^m], m <= 4. Since g(K) = e^b + c1 K, with
  c1 = (e^a - e^b)/N_g, and the copies switch independently of each other and of the tracer:
      E[Y^m] = exp(-m lambda e^b t) * prod over copies of f_x(theta_m, t),   theta_m = m lambda c1,
      f_x(theta, t) = [exp(t (Q - theta diag(1, 0))) 1]_x            (Feynman-Kac),
  with Q the copy's generator over (G, H) and x the copy's founder form. This is SPEC.md section
  3.3's closed linear system for E[n^j 1{K = k}], j <= 4, solved in closed form.
"""

from __future__ import annotations

from decimal import Decimal, getcontext, localcontext
from fractions import Fraction

DEFAULT_PREC = 60

N_A_PER_MOL = "6.02214076e23"  # SPEC.md section 0, exact (SI 2019)
C0_MOL_PER_L = "1"  # the standard concentration
L_TO_M3 = "1e-3"
M_REPLICAS = 128  # replicas per world (protocol section 5)
FAIL_BAND = 6  # statistical plants: distance in 6 SD/sqrt(M) (CRITERIA)
C1_RELATIVE = "1e-5"  # C1's bound, 1e-5 s_y
C5_STEP_CAP = 10**4  # C5's bound at the step guard's cap, A = 1e4 (CRITERIA)
C5_TRACER_PLACES = 2  # P_t: S@pool and S@lumen (AMENDMENT section 7)

SHELL_OBSERVABLES = ("S@pool", "S@lumen", "B@wall")
GATE_OBSERVABLES = ("S@pool", "S@lumen", "G@wall", "H@wall", "B@wall")
GAP_OBSERVABLES = ("S@pool", "S@lumen", "G@wall", "H@wall")  # the gap list (SPEC.md section 3.3)
C8_OBSERVABLES = ("S@pool", "S@lumen")  # C8: the tracer only (AMENDMENT-2026-11-24 section 1)
# the spec's order of compared quantities, for the plants' tie rule (AMENDMENT-2026-11-24 section 2)
SPEC_ORDER = (
    "S@pool",
    "S@lumen",
    "G@wall",
    "H@wall",
    "B@wall",
    "removed",
    "mixing_heat",
    "heat",
    "tracer_moiety",
)
# distances equal to 40 digits are ties: exact ties of exact arithmetic that rounding at 60 (or 100)
# digits can split, far below any real difference between two compared quantities
TIE_RELATIVE = "1e-40"

STIRLING2 = {  # S(j, i): n^j = sum_i S(j, i) n(n - 1)...(n - i + 1)
    0: {0: 1},
    1: {1: 1},
    2: {1: 1, 2: 1},
    3: {1: 1, 2: 3, 3: 1},
    4: {1: 1, 2: 7, 3: 6, 4: 1},
}


# --------------------------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------------------------


def number(text):
    """The exact value of an input: an integer, or a string holding a decimal literal, p/q, ln(x),
    or a sum of these (``"0.7 + ln(2)"``). Evaluated in the current decimal context."""
    if isinstance(text, bool):
        raise TypeError("a boolean is not an input number")
    if isinstance(text, int):
        return Decimal(text)
    if not isinstance(text, str):
        raise TypeError(f"inputs are strings or integers, got {text!r}")
    if "e+" in text.lower():
        raise ValueError(f"write exponents without '+': {text!r}")
    total = Decimal(0)
    for raw in text.split("+"):
        term = raw.strip()
        sign = Decimal(1)
        if term.startswith("-ln("):
            sign, term = Decimal(-1), term[1:]
        if term.startswith("ln(") and term.endswith(")"):
            value = Decimal(term[3:-1].strip()).ln()
        elif "/" in term:
            p, q = term.split("/")
            value = Decimal(p.strip()) / Decimal(q.strip())
        else:
            value = Decimal(term)
        total += sign * value
    return total


def dyadic_fraction(text):
    """A withdrawal's f, as an exact fraction whose denominator is a power of two."""
    p, q = (int(x) for x in text.split("/"))
    frac = Fraction(p, q)
    if not 0 < frac < 1 or frac.denominator & (frac.denominator - 1):
        raise ValueError(f"f must be a dyadic number in (0, 1): {text!r}")
    return frac


def parse_world(raw):
    """The world's inputs as exact decimals (current context). Checks the timeline's shape."""
    w = {"name": raw["name"], "type": raw["type"]}
    if w["type"] not in ("shell_washes", "gated_shell"):
        raise ValueError(f"unknown world type {w['type']!r}")
    for key in ("V_out_L", "V_in_L", "A_sh_m2", "P_s_m_per_s"):
        w[key] = number(raw[key])
        if w[key] <= 0:
            raise ValueError(f"{key} must be positive")
    pots = raw["tracer_potentials_kBT"]
    w["mu_solution"] = number(pots["solution"])
    # "no lumen potential": the lumen place takes the solution's, so Delta = 0 (SPEC.md section 2)
    w["mu_lumen"] = w["mu_solution"] if pots["lumen"] is None else number(pots["lumen"])
    founder = raw["founder_molecules"]
    for key, value in founder.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"founder count {key} must be a non-negative integer")
    w["founder"] = dict(founder)
    w["obs"] = [number(t) for t in raw["observation_times_s"]]
    w["horizon"] = number(raw["horizon_s"])
    if any(b <= a for a, b in zip(w["obs"], w["obs"][1:], strict=False)) or not w["obs"]:
        raise ValueError("observation times must be strictly increasing")
    if w["obs"][0] <= 0 or w["obs"][-1] > w["horizon"]:
        raise ValueError("observation times must lie in (0, horizon]")
    w["stops"] = []
    if w["type"] == "shell_washes":
        if set(founder) != {"S@pool", "S@lumen", "B@wall"}:
            raise ValueError("a shell world's founder has S@pool, S@lumen and B@wall")
        for stop in raw["stops"]:
            t = number(stop["time_s"])
            if stop["kind"] == "withdrawal":
                frac = dyadic_fraction(stop["f"])
                f = Decimal(frac.numerator) / Decimal(frac.denominator)
            elif stop["kind"] == "replacement":
                f = Decimal(1)
            else:
                raise ValueError(f"unknown stop kind {stop['kind']!r}")
            w["stops"].append((t, stop["kind"], f))
        times = [s[0] for s in w["stops"]]
        if any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ValueError("stops must be strictly increasing in time")
        if times and (times[0] <= 0 or times[-1] >= w["horizon"]):
            raise ValueError("stops must lie in (0, horizon)")
        if set(times) & set(w["obs"]):
            raise ValueError("no observation time may fall at a stop (SPEC.md section 2)")
    else:
        if raw.get("stops"):
            raise ValueError("a gated world has no washes (SPEC.md section 2)")
        if set(founder) != {"S@pool", "S@lumen", "B@wall", "G@wall", "H@wall"}:
            raise ValueError("a gated world's founder has S@pool, S@lumen, B@wall, G@wall, H@wall")
        gate = raw["gate"]
        w["a"] = number(gate["a_open_kBT"])
        w["b"] = number(gate["b_closed_kBT"])
        w["mu_G"] = number(gate["mu0_G_kBT"])
        w["mu_H"] = number(gate["mu0_H_kBT"])
        w["k_GH"] = number(gate["k_GH_per_s"])
        if w["k_GH"] <= 0:
            raise ValueError("k_GH must be positive")
        if founder["G@wall"] + founder["H@wall"] <= 0:
            raise ValueError("a gated world needs at least one gate copy")
    w["plants"] = list(raw.get("plants", []))
    return w


def shell_rates(w, *, exit_potential=True):
    """kappa_in = P_s A_sh / V_out and kappa_out = P_s A_sh e^Delta / V_in, V in m^3 (SPEC.md
    section 1). ``exit_potential=False`` drops e^Delta from the exit (plants P1 and P7)."""
    to_m3 = Decimal(L_TO_M3)
    pa = w["P_s_m_per_s"] * w["A_sh_m2"]
    k_in = pa / (w["V_out_L"] * to_m3)
    delta = w["mu_lumen"] - w["mu_solution"]
    factor = delta.exp() if exit_potential else Decimal(1)
    k_out = pa * factor / (w["V_in_L"] * to_m3)
    return k_in, k_out


def ln_capacity(volume_l):
    """ln X_place, X_place = N_A V_place c0 with V in L and c0 in mol/L (SPEC.md section 3.2)."""
    return (Decimal(N_A_PER_MOL) * volume_l * Decimal(C0_MOL_PER_L)).ln()


# --------------------------------------------------------------------------------------------
# Sums of independent indicators
# --------------------------------------------------------------------------------------------


def _guard_probability(p):
    """A probability strictly inside (0, 1) must be far from the ends at this precision, so that
    an exact 0 or 1 is always structural, never rounding."""
    if p < 0 or p > 1:
        raise ArithmeticError(f"probability outside [0, 1]: {p}")
    if p not in (0, 1):
        floor = Decimal(10) ** (-(getcontext().prec // 2))
        if min(p, 1 - p) < floor:
            raise ArithmeticError("a probability is too near 0 or 1 for a structural class")


def indicator_sum(groups):
    """Moments of a sum of independent binomials, ``groups`` = [(n, p), ...].

    Returns {"constant": bool, "mean", "var", "mu4"}. The class is structural: constant exactly
    when every group with molecules has p exactly 0 or 1 (SPEC.md section 3.1)."""
    k1 = k2 = k4 = Decimal(0)
    constant = True
    for n, p in groups:
        if n == 0:
            continue
        _guard_probability(p)
        if p not in (0, 1):
            constant = False
        pq = p * (1 - p)
        k1 += n * p
        k2 += n * pq
        k4 += n * pq * (1 - 6 * pq)
    mu4 = k4 + 3 * k2 * k2
    if constant != (k2 == 0):
        raise ArithmeticError("the class and the variance disagree")
    return {"constant": constant, "mean": k1, "var": k2, "mu4": mu4}


def scaled(moments, c):
    """Moments of c X from those of X (the mixing heat is c times the kept count)."""
    return {
        "constant": moments["constant"],
        "mean": c * moments["mean"],
        "var": c * c * moments["var"],
        "mu4": c**4 * moments["mu4"],
    }


def entry(moments, *, count):
    """A pair's (or a stop quantity's) entry from its moments: a ``constant`` holds ``value`` (an
    integer for a count), a ``spread`` holds mean, var and mu4 (SPEC.md section 5)."""
    if moments["constant"]:
        value = moments["mean"]
        if count:
            if value != value.to_integral_value():
                raise ArithmeticError("a constant count that is not an integer")
            value = int(value)
        return {"constant": True, "value": value}
    if moments["var"] <= 0:
        raise ArithmeticError("a spread entry without a positive variance")
    return {
        "constant": False,
        "mean": moments["mean"],
        "var": moments["var"],
        "mu4": moments["mu4"],
    }


def entry_mean(e):
    return Decimal(e["value"]) if e["constant"] else e["mean"]


# --------------------------------------------------------------------------------------------
# Shell worlds: the single-molecule law through the timeline
# --------------------------------------------------------------------------------------------


def timeline(w):
    """Observation times, stops and the horizon in time order: (t, kind, f)."""
    events = [(t, "obs", None) for t in w["obs"]]
    events += [(t, kind, f) for t, kind, f in w["stops"]]
    events.sort(key=lambda e: e[0])
    if w["obs"][-1] == w["horizon"]:
        return events  # the horizon is also the last observation time
    return events + [(w["horizon"], "horizon", None)]


def _relax(p_pool, p_lumen, k_in, k_out, tau):
    """Two-state relaxation over tau: the mass in the system is kept, and the deviation from the
    equilibrium split decays at lambda = k_in + k_out."""
    lam = k_in + k_out
    if tau == 0 or lam == 0:
        return p_pool, p_lumen
    s = p_pool + p_lumen
    pi0, pi1 = k_out / lam, k_in / lam
    e = (-lam * tau).exp()
    return pi0 * s + (p_pool - pi0 * s) * e, pi1 * s + (p_lumen - pi1 * s) * e


def shell_law(w, k_in, k_out, *, removal=None, lumen_mapped=None, freeze_after_replacement=False):
    """The law of one pool-born and one lumen-born molecule through the timeline.

    Options (the plants; CRITERIA.md and AMENDMENT sections 2-4):
      removal(f): the pool fraction a withdrawal removes (honest: f; P2: 1 - (1 - f)^2; P8: f^2);
      lumen_mapped: "every_stop" maps the lumen at each stop as the pool and books its loss as
        removed (P3, registered); "replacement_only" does so at the replacement alone (P3's
        unregistered variant, information only);
      freeze_after_replacement: nothing moves after the full wash (P4's factored flux).
    """
    if lumen_mapped not in (None, "every_stop", "replacement_only"):
        raise ValueError(f"unknown lumen mapping {lumen_mapped!r}")
    out = {}
    for origin, start in (("pool", (1, 0)), ("lumen", (0, 1))):
        p_pool, p_lumen = Decimal(start[0]), Decimal(start[1])
        t_prev, frozen = Decimal(0), False
        rec = {"start": (p_pool, p_lumen), "obs": {}, "stops": {}}
        for t, kind, f in timeline(w):
            if not frozen:
                p_pool, p_lumen = _relax(p_pool, p_lumen, k_in, k_out, t - t_prev)
            t_prev = t
            if kind == "obs":
                rec["obs"][t] = (p_pool, p_lumen)
                continue
            if kind == "horizon":
                continue
            pre = (p_pool, p_lumen)
            if kind == "withdrawal":
                rho = f if removal is None else removal(f)
                removed, kept = rho * p_pool, (1 - rho) * p_pool
                p_pool = kept
                if lumen_mapped == "every_stop":
                    removed += f * p_lumen
                    p_lumen = (1 - f) * p_lumen
            else:
                removed, kept = p_pool, Decimal(0)
                p_pool = Decimal(0)
                if lumen_mapped is not None:
                    removed += p_lumen
                    p_lumen = Decimal(0)
                if freeze_after_replacement:
                    frozen = True
            rec["stops"][t] = {
                "pre": pre,
                "removed": removed,
                "kept": kept,
                "post": (p_pool, p_lumen),
            }
        rec["end"] = (p_pool, p_lumen)
        out[origin] = rec
    return out


def _groups(w, law, pick):
    """[(founder count, probability)] for the pool-born and lumen-born molecules."""
    return [
        (w["founder"]["S@pool"], pick(law["pool"])),
        (w["founder"]["S@lumen"], pick(law["lumen"])),
    ]


def _mean(w, law, pick):
    return sum((n * p for n, p in _groups(w, law, pick)), Decimal(0))


def mixing_coefficient(f):
    """The withdrawal's booked mixing heat per kept molecule, -ln(1 - f) (SPEC.md section 1)."""
    return -(1 - f).ln()


def f_cont(n_pool, n_lumen, w, *, zero_as_one=False):
    """F_cont of the tracer's places (SPEC.md section 3.2); the wall's places cancel in Q_c.

    ``zero_as_one`` is plant P9: a place at zero takes one molecule's term."""
    total = Decimal(0)
    for n, mu, volume in (
        (n_pool, w["mu_solution"], w["V_out_L"]),
        (n_lumen, w["mu_lumen"], w["V_in_L"]),
    ):
        lnx = ln_capacity(volume)
        if n == 0:
            if zero_as_one:
                total += mu - lnx - 1
            continue
        if n < 0:
            raise ArithmeticError("a mean count below zero")
        total += n * (mu - lnx) + n * n.ln() - n
    return total


def shell_d(w, law):
    """The deterministic representation's mean trajectory from a molecule law: the counts at the
    observation times, each stop's removed amount and mixing heat, and the interval boundaries."""
    founder = w["founder"]
    d = {"pairs": {}, "stops": {}, "bounds": []}
    for t in w["obs"]:
        d["pairs"][("S@pool", t)] = _mean(w, law, lambda r, t=t: r["obs"][t][0])
        d["pairs"][("S@lumen", t)] = _mean(w, law, lambda r, t=t: r["obs"][t][1])
        d["pairs"][("B@wall", t)] = Decimal(founder["B@wall"])
    for t, kind, f in w["stops"]:
        removed = _mean(w, law, lambda r, t=t: r["stops"][t]["removed"])
        heat = None
        if kind == "withdrawal":
            heat = mixing_coefficient(f) * _mean(w, law, lambda r, t=t: r["stops"][t]["kept"])
        d["stops"][t] = (removed, heat)
    # interval boundaries: (start time, start counts, end time, end counts)
    start_t = Decimal(0)
    start_n = (Decimal(founder["S@pool"]), Decimal(founder["S@lumen"]))
    for t, _kind, _f in w["stops"]:
        pre = tuple(_mean(w, law, lambda r, i=i, t=t: r["stops"][t]["pre"][i]) for i in (0, 1))
        d["bounds"].append((start_t, start_n, t, pre))
        start_t = t
        start_n = tuple(_mean(w, law, lambda r, i=i, t=t: r["stops"][t]["post"][i]) for i in (0, 1))
    end_n = tuple(_mean(w, law, lambda r, i=i: r["end"][i]) for i in (0, 1))
    d["bounds"].append((start_t, start_n, w["horizon"], end_n))
    return d


def interval_heats(w, d, *, zero_as_one=False):
    """Q_c = -[F_cont(end) - F_cont(start)] of the mean counts, per interval (SPEC.md 3.2)."""
    out = []
    for t0, n0, t1, n1 in d["bounds"]:
        heat = -(f_cont(*n1, w, zero_as_one=zero_as_one) - f_cont(*n0, w, zero_as_one=zero_as_one))
        out.append((t0, t1, heat))
    return out


def shell_exact_pairs(w, law):
    """The exact law's moments per place and observation time, in SHELL_OBSERVABLES order."""
    pairs = []
    for obs, index in (("S@pool", 0), ("S@lumen", 1)):
        for t in w["obs"]:
            m = indicator_sum(_groups(w, law, lambda r, t=t, index=index: r["obs"][t][index]))
            pairs.append((obs, t, entry(m, count=True)))
    for t in w["obs"]:
        # the wall's subunit B: no step moves it (SPEC.md section 1)
        pairs.append(("B@wall", t, {"constant": True, "value": w["founder"]["B@wall"]}))
    return pairs


def shell_exact_stops(w, law):
    """Each stop's removed count and each withdrawal's mixing heat, exact moments."""
    stops = []
    for t, kind, f in w["stops"]:
        removed = indicator_sum(_groups(w, law, lambda r, t=t: r["stops"][t]["removed"]))
        heat = None
        if kind == "withdrawal":
            kept = indicator_sum(_groups(w, law, lambda r, t=t: r["stops"][t]["kept"]))
            heat = entry(scaled(kept, mixing_coefficient(f)), count=False)
        stops.append((t, kind, f, entry(removed, count=True), heat))
    return stops


# --------------------------------------------------------------------------------------------
# Shell worlds: the plants' predicted effects (SPEC.md 3.4; CRITERIA.md; AMENDMENT 2-7)
# --------------------------------------------------------------------------------------------


def _largest(candidates):
    """The candidate of largest distance (AMENDMENT-2026-11-24 section 2): a tie in distance goes
    to the earliest time or stop (an interval by its start), then to the first observable in the
    spec's order."""
    top = max(c["distance"] for c in candidates)
    floor = top - Decimal(TIE_RELATIVE) * top
    tied = [c for c in candidates if c["distance"] >= floor]

    def when(c):
        return c["time_s"] if "time_s" in c else c["start_s"]

    return min(tied, key=lambda c: (when(c), SPEC_ORDER.index(c["observable"])))


def _c1_scale_pairs(w, d):
    scale = {}
    for obs in SHELL_OBSERVABLES:
        values = [abs(Decimal(w["founder"][obs]))] + [abs(d["pairs"][(obs, t)]) for t in w["obs"]]
        scale[obs] = max(values)
    return scale


def _stop_scales(w, d):
    removed = max((abs(d["stops"][t][0]) for t, _k, _f in w["stops"]), default=Decimal(0))
    heats = [abs(d["stops"][t][1]) for t, kind, _f in w["stops"] if kind == "withdrawal"]
    return removed, max(heats, default=Decimal(0))


def _det_candidates_c1(w, honest, planted):
    """C1's compared quantities: (d)'s counts at every observation time and removed per stop."""
    rel = Decimal(C1_RELATIVE)
    scale = _c1_scale_pairs(w, honest)
    removed_scale, _heat_scale = _stop_scales(w, honest)
    out = []
    for obs in SHELL_OBSERVABLES:
        for t in w["obs"]:
            h, p = honest["pairs"][(obs, t)], planted["pairs"][(obs, t)]
            out.append(
                {
                    "observable": obs,
                    "time_s": t,
                    "honest": h,
                    "planted": p,
                    "distance": abs(p - h) / (rel * scale[obs]),
                }
            )
    for t, _kind, _f in w["stops"]:
        h, p = honest["stops"][t][0], planted["stops"][t][0]
        out.append(
            {
                "observable": "removed",
                "time_s": t,
                "honest": h,
                "planted": p,
                "distance": abs(p - h) / (rel * removed_scale),
            }
        )
    return out


def _det_candidates_c4(w, honest, planted, only_time=None):
    """C4 for (d): each stop's removed amount and each withdrawal's mixing heat, C1's bound."""
    rel = Decimal(C1_RELATIVE)
    removed_scale, heat_scale = _stop_scales(w, honest)
    out = []
    for t, kind, _f in w["stops"]:
        if only_time is not None and t != only_time:
            continue
        h, p = honest["stops"][t][0], planted["stops"][t][0]
        out.append(
            {
                "observable": "removed",
                "time_s": t,
                "honest": h,
                "planted": p,
                "distance": abs(p - h) / (rel * removed_scale),
            }
        )
        if kind == "withdrawal":
            h, p = honest["stops"][t][1], planted["stops"][t][1]
            out.append(
                {
                    "observable": "mixing_heat",
                    "time_s": t,
                    "honest": h,
                    "planted": p,
                    "distance": abs(p - h) / (rel * heat_scale),
                }
            )
    return out


def _stat_distance(planted_mean, honest):
    """|planted - honest| in the fail band's unit, 6 SD_ref/sqrt(M) (AMENDMENT section 7)."""
    if honest["constant"]:
        if planted_mean != Decimal(honest["value"]):
            raise ArithmeticError("a plant moves a constant pair: its distance is unbounded")
        return Decimal(0)
    unit = FAIL_BAND * honest["var"].sqrt() / Decimal(M_REPLICAS).sqrt()
    return abs(planted_mean - honest["mean"]) / unit


def first_withdrawal_after_replacement(w):
    seen = False
    for t, kind, _f in w["stops"]:
        if kind == "replacement":
            seen = True
        elif seen:
            return t
    raise ValueError("no withdrawal after a full wash")


def shell_plants(
    w, k_in, k_out, honest_law, honest_d, honest_pairs, honest_stops, *, p3_variant="every_stop"
):
    """One entry per (plant, criterion): the compared quantity of largest distance, named."""
    entries = []
    rel = Decimal(C1_RELATIVE)
    for plant in w["plants"]:
        if plant == "P1":
            _k, k_out_bare = shell_rates(w, exit_potential=False)
            law = shell_law(w, k_in, k_out_bare)
            entries.append(("P1", "C1", _largest(_det_candidates_c1(w, honest_d, shell_d(w, law)))))
        elif plant == "P2":
            law = shell_law(w, k_in, k_out, removal=lambda f: 1 - (1 - f) ** 2)
            planted = shell_d(w, law)
            entries.append(("P2", "C1", _largest(_det_candidates_c1(w, honest_d, planted))))
            entries.append(("P2", "C4", _largest(_det_candidates_c4(w, honest_d, planted))))
        elif plant == "P3":
            law = shell_law(w, k_in, k_out, lumen_mapped=p3_variant)
            entries.append(("P3", "C1", _largest(_det_candidates_c1(w, honest_d, shell_d(w, law)))))
        elif plant == "P4":
            law = shell_law(w, k_in, k_out, freeze_after_replacement=True)
            planted = shell_d(w, law)
            entries.append(("P4", "C1", _largest(_det_candidates_c1(w, honest_d, planted))))
            t4 = first_withdrawal_after_replacement(w)
            entries.append(("P4", "C4", _largest(_det_candidates_c4(w, honest_d, planted, t4))))
        elif plant == "P6":
            total = sum((Decimal(w["founder"][k]) for k in ("S@pool", "S@lumen")), Decimal(0))
            eps = Decimal(2) ** -52
            bound = 16 * eps * (C5_STEP_CAP + len(w["stops"])) * C5_TRACER_PLACES * total
            cands = []
            for t in list(w["obs"]) + ([w["horizon"]] if w["horizon"] != w["obs"][-1] else []):
                if t in w["obs"]:
                    present = honest_d["pairs"][("S@pool", t)] + honest_d["pairs"][("S@lumen", t)]
                else:
                    present = sum(_mean(w, honest_law, lambda r, i=i: r["end"][i]) for i in (0, 1))
                # the removed tracer is left unbooked: present + 0 against the founder's
                cands.append(
                    {
                        "observable": "tracer_moiety",
                        "time_s": t,
                        "honest": total,
                        "planted": present,
                        "distance": abs(present - total) / bound,
                    }
                )
            entries.append(("P6", "C5", _largest(cands)))
        elif plant == "P7":
            _k, k_out_bare = shell_rates(w, exit_potential=False)
            law = shell_law(w, k_in, k_out_bare)
            planted_pairs = shell_exact_pairs(w, law)
            cands = []
            for (obs, t, hm), (_o, _t, pm) in zip(honest_pairs, planted_pairs, strict=True):
                pmean = entry_mean(pm)
                cands.append(
                    {
                        "observable": obs,
                        "time_s": t,
                        "honest": entry_mean(hm),
                        "planted": pmean,
                        "distance": _stat_distance(pmean, hm),
                    }
                )
            entries.append(("P7", "C2", _largest(cands)))
        elif plant == "P8":
            law = shell_law(w, k_in, k_out, removal=lambda f: f * f)
            planted_stops = shell_exact_stops(w, law)
            cands = []
            pairs_of_stops = zip(honest_stops, planted_stops, strict=True)
            for (t, kind, _f, hr, hh), (_t, _k, _f2, pr, ph) in pairs_of_stops:
                cands.append(
                    {
                        "observable": "removed",
                        "time_s": t,
                        "honest": entry_mean(hr),
                        "planted": entry_mean(pr),
                        "distance": _stat_distance(entry_mean(pr), hr),
                    }
                )
                if kind == "withdrawal":
                    cands.append(
                        {
                            "observable": "mixing_heat",
                            "time_s": t,
                            "honest": entry_mean(hh),
                            "planted": entry_mean(ph),
                            "distance": _stat_distance(entry_mean(ph), hh),
                        }
                    )
            entries.append(("P8", "C4", _largest(cands)))
        elif plant == "P9":
            honest_heats = interval_heats(w, honest_d)
            planted_heats = interval_heats(w, honest_d, zero_as_one=True)
            scale = max(abs(q) for _a, _b, q in honest_heats)
            cands = []
            for (t0, t1, h), (_a, _b, p) in zip(honest_heats, planted_heats, strict=True):
                cands.append(
                    {
                        "observable": "heat",
                        "start_s": t0,
                        "end_s": t1,
                        "honest": h,
                        "planted": p,
                        "distance": abs(p - h) / (rel * scale),
                    }
                )
            entries.append(("P9", "C9", _largest(cands)))
        else:
            raise ValueError(f"plant {plant} is not a shell-world plant")
    return entries


def shell_reference(w, *, p3_variant="every_stop"):
    """Method 1 for a shell world (current decimal context)."""
    k_in, k_out = shell_rates(w)
    law = shell_law(w, k_in, k_out)
    pairs = shell_exact_pairs(w, law)
    stops = shell_exact_stops(w, law)
    d = shell_d(w, law)
    heats = interval_heats(w, d)
    plants = shell_plants(w, k_in, k_out, law, d, pairs, stops, p3_variant=p3_variant)
    return {
        "rates": (k_in, k_out),
        "pairs": pairs,
        "stops": stops,
        "d": d,
        "intervals": heats,
        "plants": plants,
    }


# --------------------------------------------------------------------------------------------
# Gated worlds
# --------------------------------------------------------------------------------------------


def _poly_mul(a, b):
    out = [Decimal(0)] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] += x * y
    return out


def _poly_add(a, b):
    n = max(len(a), len(b))
    return [(a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) for i in range(n)]


def _binomial(n, k):
    out = 1
    for i in range(k):
        out = out * (n - i) // (i + 1)
    return out


def _binomial_raw_moment_polys(n, u, v, jmax=4):
    """E[X^j | Y] for X ~ Bin(n, u + v Y), j = 0..jmax, as polynomials in Y."""
    p_powers = [[Decimal(1)]]
    for _ in range(jmax):
        p_powers.append(_poly_mul(p_powers[-1], [u, v]))
    polys = []
    for j in range(jmax + 1):
        poly = [Decimal(0)]
        for i, s in STIRLING2[j].items():
            falling = 1
            for r in range(i):
                falling *= n - r
            if falling == 0:
                continue
            poly = _poly_add(poly, [Decimal(s * falling) * c for c in p_powers[i]])
        polys.append(poly)
    return polys


def _sum_raw_moment_polys(parts, jmax=4):
    """Raw moments of a sum of variables independent given Y, from each part's raw moments."""
    total = parts[0]
    for part in parts[1:]:
        new = []
        for j in range(jmax + 1):
            poly = [Decimal(0)]
            for ell in range(j + 1):
                term = _poly_mul(total[ell], part[j - ell])
                poly = _poly_add(poly, [Decimal(_binomial(j, ell)) * c for c in term])
            new.append(poly)
        total = new
    return total


def _central_from_raw(raw):
    e1, e2, e3, e4 = raw[1], raw[2], raw[3], raw[4]
    var = e2 - e1 * e1
    mu4 = e4 - 4 * e1 * e3 + 6 * e1 * e1 * e2 - 3 * e1**4
    return e1, var, mu4


def copy_factors(alpha, beta, theta, t):
    """f_G and f_H: E[exp(-theta int_0^t sigma ds)] for one copy founded open (G) or closed (H),
    sigma = 1 when open; the copy leaves G at alpha and H at beta (Feynman-Kac, a 2x2 exponent)."""
    if theta == 0:
        return Decimal(1), Decimal(1)
    tr = -(alpha + beta + theta)
    det = theta * beta
    disc = (alpha + theta - beta) ** 2 + 4 * alpha * beta
    r2 = (tr - disc.sqrt()) / 2
    r1 = det / r2
    e1, e2 = (r1 * t).exp(), (r2 * t).exp()
    f_g = (e1 * (-theta - r2) - e2 * (-theta - r1)) / (r1 - r2)
    f_h = (e1 * (-r2) - e2 * (-r1)) / (r1 - r2)
    return f_g, f_h


def gate_parameters(w):
    k_in, k_out = shell_rates(w)
    f = w["founder"]
    p = {"k_in": k_in, "k_out": k_out, "lam": k_in + k_out}
    p["pi1"], p["pi0"] = k_in / p["lam"], k_out / p["lam"]
    p["ea"], p["eb"] = w["a"].exp(), w["b"].exp()
    p["alpha"] = w["k_GH"]  # G -> H per copy
    p["beta"] = w["k_GH"] * (w["mu_H"] - w["mu_G"]).exp()  # H -> G per copy
    p["G0"], p["H0"], p["B0"] = f["G@wall"], f["H@wall"], f["B@wall"]
    p["Ng"] = p["G0"] + p["H0"]
    p["Nw"] = p["B0"] + p["Ng"]
    p["NP"], p["NL"] = f["S@pool"], f["S@lumen"]
    p["N"] = p["NP"] + p["NL"]
    p["c1"] = (p["ea"] - p["eb"]) / p["Ng"]
    p["gam"] = p["alpha"] + p["beta"]
    p["piG"], p["piH"] = p["beta"] / p["gam"], p["alpha"] / p["gam"]
    return p


def y_moments(p, t):
    """E[Y^m], m = 0..4, Y = exp(-lambda Phi(t))."""
    out = []
    for m in range(5):
        theta = m * p["lam"] * p["c1"]
        f_g, f_h = copy_factors(p["alpha"], p["beta"], theta, t)
        out.append((-m * p["lam"] * p["eb"] * t).exp() * f_g ** p["G0"] * f_h ** p["H0"])
    return out


def _tracer_moments(p, ey, pool):
    """Exact mean, var and mu4 of S@pool (pool=True) or S@lumen given E[Y^m]."""
    if pool:
        parts = [(p["NP"], p["pi0"], p["pi1"]), (p["NL"], p["pi0"], -p["pi0"])]
    else:
        parts = [(p["NP"], p["pi1"], -p["pi1"]), (p["NL"], p["pi1"], p["pi0"])]
    polys = _sum_raw_moment_polys([_binomial_raw_moment_polys(n, u, v) for n, u, v in parts])
    raw = [sum((c * ey[m] for m, c in enumerate(poly)), Decimal(0)) for poly in polys]
    if abs(raw[0] - 1) > Decimal(10) ** (-(getcontext().prec - 5)):
        raise ArithmeticError("the zeroth moment is not one")
    mean, var, mu4 = _central_from_raw(raw)
    return mean, var, mu4


def gate_exact_pairs(w, p):
    """Exact moments of S@pool, S@lumen, G@wall, H@wall and B@wall (GATE_OBSERVABLES order)."""
    by_obs = {obs: [] for obs in GATE_OBSERVABLES}
    crossing = p["k_in"] + p["k_out"] > 0 and p["N"] > 0
    switching = p["gam"] > 0
    for t in w["obs"]:
        ey = y_moments(p, t)
        for obs, pool in (("S@pool", True), ("S@lumen", False)):
            mean, var, mu4 = _tracer_moments(p, ey, pool)
            if not crossing:
                by_obs[obs].append(
                    (obs, t, {"constant": True, "value": p["NP"] if pool else p["NL"]})
                )
                continue
            if var <= 0:
                raise ArithmeticError("a spread pair without a positive variance")
            by_obs[obs].append((obs, t, {"constant": False, "mean": mean, "var": var, "mu4": mu4}))
        e = (-p["gam"] * t).exp()
        p_gg, p_hg = p["piG"] + p["piH"] * e, p["piG"] * (1 - e)  # open at t | G or H at 0
        q_gg, q_hg = p["piH"] * (1 - e), p["piH"] + p["piG"] * e  # closed at t | G or H at 0
        g_m = indicator_sum([(p["G0"], p_gg), (p["H0"], p_hg)])
        h_m = indicator_sum([(p["G0"], q_gg), (p["H0"], q_hg)])
        if not switching and not (g_m["constant"] and h_m["constant"]):
            raise ArithmeticError("a gate that does not switch must have constant forms")
        by_obs["G@wall"].append(("G@wall", t, entry(g_m, count=True)))
        by_obs["H@wall"].append(("H@wall", t, entry(h_m, count=True)))
        by_obs["B@wall"].append(("B@wall", t, {"constant": True, "value": p["B0"]}))
    return [pair for obs in GATE_OBSERVABLES for pair in by_obs[obs]]


def gate_mean_field(w, p, *, entry_only=False):
    """The deterministic representation's registered limit (SPEC.md section 3.3): the rate
    equations of the means, g at the mean open count, and the switching at k (N_w + 1)/N_w.

    ``entry_only`` is plant P5: g multiplies kappa_in alone (AMENDMENT section 5)."""
    fac = Decimal(p["Nw"] + 1) / Decimal(p["Nw"])
    gam_w = p["gam"] * fac
    g_eq, h_eq = p["Ng"] * p["piG"], p["Ng"] * p["piH"]
    a0 = p["eb"] + p["c1"] * g_eq  # g(t) = a0 + a1 exp(-gam_w t)
    a1 = p["c1"] * (p["G0"] - g_eq)
    out = {}
    for t in w["obs"]:
        e = (-gam_w * t).exp()
        out[("G@wall", t)] = g_eq + (p["G0"] - g_eq) * e
        out[("H@wall", t)] = h_eq + (p["H0"] - h_eq) * e
        out[("B@wall", t)] = Decimal(p["B0"])
        if not entry_only:
            phi = a0 * t + a1 * (1 - e) / gam_w
            y = (-p["lam"] * phi).exp()
            out[("S@lumen", t)] = p["N"] * p["pi1"] + (p["NL"] - p["N"] * p["pi1"]) * y
            out[("S@pool", t)] = p["N"] * p["pi0"] + (p["NP"] - p["N"] * p["pi0"]) * y
        else:
            lumen = _entry_only_lumen(p, a0, a1, gam_w, t)
            out[("S@lumen", t)] = lumen
            out[("S@pool", t)] = p["N"] - lumen
    return out


def _expint(sigma, t):
    """int_0^t exp(sigma s) ds."""
    if sigma == 0:
        return t
    return ((sigma * t).exp() - 1) / sigma


def _entry_only_lumen(p, a0, a1, gam_w, t):
    """P5's planted mean field: dn/dt = kappa_in g(t) (N - n) - kappa_out n with
    g(t) = a0 + a1 exp(-gam_w t), solved as a convergent series (no ODE solver):
    n(t) = exp(-I(t)) [n0 + kappa_in N int_0^t g(s) exp(I(s)) ds],
    I(t) = b0 t + (b1/gam_w)(1 - exp(-gam_w t)), b0 = kappa_in a0 + kappa_out, b1 = kappa_in a1,
    and exp(I(s)) expanded in powers of exp(-gam_w s)."""
    k_in, k_out = p["k_in"], p["k_out"]
    b0, b1 = k_in * a0 + k_out, k_in * a1
    r = -b1 / gam_w
    total, term_coef, m = Decimal(0), Decimal(1), 0
    tiny = Decimal(10) ** (-(getcontext().prec + 5))
    while True:
        piece = term_coef * (
            a0 * _expint(b0 - m * gam_w, t) + a1 * _expint(b0 - (m + 1) * gam_w, t)
        )
        total += piece
        m += 1
        term_coef = term_coef * r / m
        if m > 8 and abs(piece) <= tiny * abs(total):
            break
        if m > 10000:
            raise ArithmeticError("P5's series did not converge")
    integral = (b1 / gam_w).exp() * total
    i_t = b0 * t + (b1 / gam_w) * (1 - (-gam_w * t).exp())
    return (-i_t).exp() * (p["NL"] + k_in * p["N"] * integral)


def gate_reference(w):
    """Method 1 for a gated world (current decimal context)."""
    p = gate_parameters(w)
    pairs = gate_exact_pairs(w, p)
    mf = gate_mean_field(w, p)
    exact = {(obs, t): m for obs, t, m in pairs}
    root_m = Decimal(M_REPLICAS).sqrt()
    gap = []
    for obs in GAP_OBSERVABLES:
        for t in w["obs"]:
            m = exact[(obs, t)]
            if m["constant"]:
                raise ArithmeticError("a constant gap pair")
            g = mf[(obs, t)] - m["mean"]
            gap.append((obs, t, g, abs(g) * root_m / m["var"].sqrt()))
    plants = []
    for plant in w["plants"]:
        if plant != "P5":
            raise ValueError(f"plant {plant} is not a gated-world plant")
        planted = gate_mean_field(w, p, entry_only=True)
        rel = Decimal(C1_RELATIVE)
        cands = []
        for obs in GATE_OBSERVABLES:
            scale = max([abs(Decimal(w["founder"][obs]))] + [abs(mf[(obs, t)]) for t in w["obs"]])
            for t in w["obs"]:
                h, q = mf[(obs, t)], planted[(obs, t)]
                cands.append(
                    {
                        "observable": obs,
                        "time_s": t,
                        "honest": h,
                        "planted": q,
                        "distance": abs(q - h) / (rel * scale),
                    }
                )
        plants.append(("P5", "C7", _largest(cands)))
    return {"params": p, "pairs": pairs, "d": mf, "gap": gap, "plants": plants}


def reference(raw_world, prec=DEFAULT_PREC, **options):
    """Method 1's results for a world given as its input dictionary, at ``prec`` digits."""
    with localcontext() as ctx:
        ctx.prec = prec
        w = parse_world(raw_world)
        if w["type"] == "shell_washes":
            out = shell_reference(w, **options)
        else:
            out = gate_reference(w)
        out["world"] = w
        return out
