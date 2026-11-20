"""The window-survivor calculation (FR-25's backlog, D248 and D251): of the product completed in a
window [t1, t2], how much is still present at a sampling time ts >= t2, as a pulse label measures
it, from the engine's existing outputs alone. Development, not judged.

**What it assumes.** One well-mixed pool whose loss does not depend on a molecule's age: every
molecule present at time s is lost at the same per-molecule rate k(s). templated_polymerisation@1's
degradation is such a loss, J_D = k n (1 - e^y), so k(s) = k (1 - e^(y(s))). Under age- or
region-selective loss no output identifies which molecules were lost, and this calculation does
not apply (FR-33).

**The calculation.** The cohort's amount S obeys dS = dQ - (S/n) dD over [t1, t2] and dS = -(S/n) dD
after t2, from S(t1) = 0, where the outputs give:
- Q(t), the cumulative completions (the chain's int_Q, poly_released_fmol);
- D(t), the cumulative losses (int_D, poly_degraded_fmol);
- n(t), the pool (n_P or n_R).

It needs neither k nor y: (S/n) dD is the cohort's share of each loss. On the output grid each
interval is integrated with the pool's per-molecule loss rate held at its interval mean,
k_i = (D_{i+1} - D_i)/(integral of n over the interval), and completions spread evenly over the
interval:
  S_{i+1} = S_i e^(-k_i h) + (dQ_i / (k_i h)) (1 - e^(-k_i h)) inside the window, without the dQ
term after it. The integral of n uses Simpson's rule where the grid allows, else the trapezoid.
Both are exact as the grid refines. The calculation's error on a grid is stated by running it on
every second output as well and differencing (`grid_error`).

**When the rate is known** (constant k), `known_rate` gives the closed form for completions spread
evenly over each output interval. On the engine's A1 export (revision f96a9606), minutes 60–90 and
sampled at minute 90, both reproduce the reviewer's figures: 2.01673e-5 fmol completed and
1.32977e-5 fmol surviving, while the pool grew by 2.70386e-6 fmol.

**The check.** FR-25's turnover control: 100 copies at steady state, a one-hour half-life and
production of 100 ln 2 copies per hour. Of the 69.31 copies completed in the first hour, 50 remain
at its end and 25 an hour later. `turnover_control` builds those counters and checks both.

Run: python -m validation.gene_regulation.cohort FILE --t1 S --t2 S [--ts S] [--product ROW]
[--chain ID], with FILE an engine_run.py run (JSON) or the A1 export's CSV.
"""

import argparse
import csv
import json
import math
from pathlib import Path


def _integral(t, n, i, j):
    """The integral of n over [t_i, t_j] on the output grid, by Simpson's rule on uniform pairs of
    intervals, the trapezoid on what remains."""
    total, k = 0.0, i
    while k + 2 <= j and abs((t[k + 1] - t[k]) - (t[k + 2] - t[k + 1])) < 1e-9:
        total += (t[k + 2] - t[k]) * (n[k] + 4 * n[k + 1] + n[k + 2]) / 6
        k += 2
    while k < j:
        total += (t[k + 1] - t[k]) * (n[k] + n[k + 1]) / 2
        k += 1
    return total


def survivors(t, n, Q, D, t1, t2, ts=None):
    """(completed in [t1, t2], surviving at ts, the pool's change over [t1, t2]) from the counters
    on an output grid holding t1, t2 and ts (module docstring)."""
    ts = t2 if ts is None else ts
    i1, i2, i3 = (t.index(x) for x in (t1, t2, ts))
    S = 0.0
    for i in range(i1, i3):
        h = t[i + 1] - t[i]
        lost = D[i + 1] - D[i]
        k = lost / _integral(t, n, i, i + 1) if lost > 0 else 0.0
        decay = math.exp(-k * h)
        made = Q[i + 1] - Q[i] if i < i2 else 0.0
        spread = -math.expm1(-k * h) / (k * h) if k > 0 else 1.0
        S = S * decay + made * spread
    return Q[i2] - Q[i1], S, n[i2] - n[i1]


def known_rate(t, Q, k, t1, t2, ts=None):
    """The survivors at ts for a constant per-molecule rate k, completions spread evenly over each
    output interval."""
    ts = t2 if ts is None else ts
    i1, i2 = t.index(t1), t.index(t2)
    out = 0.0
    for i in range(i1, i2):
        h = t[i + 1] - t[i]
        early, late = ts - t[i], ts - t[i + 1]
        out += (Q[i + 1] - Q[i]) * (math.exp(-k * late) - math.exp(-k * early)) / (k * h)
    return out


def grid_error(t, n, Q, D, t1, t2, ts=None):
    """|survivors on every output - survivors on every second output|: the calculation's error on
    the coarser grid, an upper estimate of its error on the given one."""
    fine = survivors(t, n, Q, D, t1, t2, ts)[1]
    keep = [i for i in range(len(t)) if i % 2 == 0 or t[i] in (t1, t2, ts)]
    pick = [[seq[i] for i in keep] for seq in (t, n, Q, D)]
    coarse = survivors(*pick, t1, t2, ts)[1]
    return abs(fine - coarse)


def turnover_control(points_per_hour=60):
    """FR-25's turnover control on exact counters: (completed in hour 1, surviving at 1 h, at 2 h).
    Expected 100 ln 2 = 69.31, 50 and 25 copies."""
    hour = 3600.0
    k = math.log(2) / hour
    production = 100 * k  # copies/s, so n stays at 100.
    t = [i * hour / points_per_hour for i in range(2 * points_per_hour + 1)]
    n = [100.0] * len(t)
    Q = [production * s for s in t]
    D = [k * 100.0 * s for s in t]
    completed, at_1h, _ = survivors(t, n, Q, D, 0.0, hour)
    _, at_2h, _ = survivors(t, n, Q, D, 0.0, hour, 2 * hour)
    return completed, at_1h, at_2h


def read(path, product="P", chain="tl"):
    """(t, n, Q, D) of an engine_run.py JSON or the A1 export's CSV, for one product."""
    path = Path(path)
    if path.suffix == ".json":
        r = json.loads(path.read_text())
        x = r["readouts"]
        return r["t"], x[f"n_{product}"], x[f"int_Q_{chain}"], x[f"int_D_{product}"]
    rows = list(csv.DictReader(path.open()))
    name = {"P": ("protein_P_fmol", "released_tl_fmol", "degraded_P_fmol"),
            "R": ("mRNA_R_fmol", "released_tx_fmol", "degraded_R_fmol")}[product]  # fmt: skip
    t = [float(row["t_s"]) for row in rows]
    return (t, *([float(row[c]) for row in rows] for c in name))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file")
    parser.add_argument("--t1", type=float, required=True)
    parser.add_argument("--t2", type=float, required=True)
    parser.add_argument("--ts", type=float)
    parser.add_argument("--product", default="P")
    parser.add_argument("--chain", default="tl")
    parser.add_argument("--rate", type=float, help="a known constant per-molecule rate, 1/s")
    args = parser.parse_args(argv)
    t, n, Q, D = read(args.file, args.product, args.chain)
    completed, surviving, grew = survivors(t, n, Q, D, args.t1, args.t2, args.ts)
    out = dict(
        completed_fmol=completed,
        surviving_fmol=surviving,
        pool_change_fmol=grew,
        grid_error_fmol=grid_error(t, n, Q, D, args.t1, args.t2, args.ts),
    )
    if args.rate:
        out["surviving_known_rate_fmol"] = known_rate(t, Q, args.rate, args.t1, args.t2, args.ts)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
