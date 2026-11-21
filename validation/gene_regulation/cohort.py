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

**When the rate is known** (constant k >= 0), `known_rate` gives the closed form for completions
spread evenly over each output interval, through expm1 and with its zero-rate limit (everything
survives), so small and zero rates hold. On the engine's A1 export (revision f96a9606), minutes
60–90 and sampled at minute 90, both reproduce the reviewer's figures: 2.01673e-5 fmol completed
and 1.32977e-5 fmol surviving, while the pool grew by 2.70386e-6 fmol.

**Which chain completes the product** (`producing_chain`; the review's finding 2). An engine_run.py
record's own definition names the chain that makes each product row, so the completions are that
chain's: for the mRNA R in A1, transcription's (tx), not translation's (tl). A chain named that
does not make the product is refused, and so is a product that no chain or several chains make,
unless one of them is named. The A1 export's CSV holds tx (making R) and tl (making P).

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


def _spread(x):
    """(1 - e^(-x))/x, the mean of e^(-x s) over s in [0, 1], with its limit 1 at x = 0."""
    return 1.0 if x == 0 else -math.expm1(-x) / x


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
        S = S * decay + made * _spread(k * h)
    return Q[i2] - Q[i1], S, n[i2] - n[i1]


def known_rate(t, Q, k, t1, t2, ts=None):
    """The survivors at ts for a constant per-molecule rate k >= 0, completions spread evenly over
    each output interval: each interval's dQ e^(-k (ts - t_{i+1})) (1 - e^(-k h))/(k h), formed
    with expm1, so it holds at small k and reaches its limit dQ at k = 0."""
    if not (isinstance(k, (int, float)) and math.isfinite(k) and k >= 0):
        raise ValueError(f"a known rate is a finite number >= 0, not {k!r}")
    ts = t2 if ts is None else ts
    i1, i2 = t.index(t1), t.index(t2)
    out = 0.0
    for i in range(i1, i2):
        h = t[i + 1] - t[i]
        out += (Q[i + 1] - Q[i]) * math.exp(-k * (ts - t[i + 1])) * _spread(k * h)
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


POLYMERISATION = "templated_polymerisation@1"
CSV_CHAINS = {"tx": "R", "tl": "P"}  # The A1 export's chains and the product each makes.
CSV_COLUMNS = {"P": ("protein_P_fmol", "released_tl_fmol", "degraded_P_fmol"),
               "R": ("mRNA_R_fmol", "released_tx_fmol", "degraded_R_fmol")}  # fmt: skip


def producing_chain(makes, product, chain=None):
    """The chain whose completions are the product's (module docstring), from {chain: the row it
    makes}; ValueError for a named chain that makes another row, or none or several without one."""
    if chain is not None:
        if chain not in makes:
            raise ValueError(f"no chain {chain!r}: the chains are {sorted(makes)}")
        if makes[chain] != product:
            raise ValueError(
                f"chain {chain} completes {makes[chain]}, not {product}: its completions are not "
                f"{product}'s"
            )
        return chain
    found = sorted(c for c, made in makes.items() if made == product)
    if len(found) != 1:
        what = "no chain makes" if not found else f"chains {found} make"
        raise ValueError(f"{what} {product}: name the chain with --chain")
    return found[0]


def read(path, product="P", chain=None):
    """(t, n, Q, D) of an engine_run.py JSON or the A1 export's CSV, for one product, with Q the
    completions of the chain that makes it (producing_chain)."""
    path = Path(path)
    if path.suffix == ".json":
        r = json.loads(path.read_text())
        (block,) = [o for o in r["definition"]["model"]["operators"] if o["law"] == POLYMERISATION]
        chain = producing_chain({c["id"]: c["product"] for c in block["chains"]}, product, chain)
        x = r["readouts"]
        return r["t"], x[f"n_{product}"], x[f"int_Q_{chain}"], x[f"int_D_{product}"]
    producing_chain(CSV_CHAINS, product, chain)
    if product not in CSV_COLUMNS:
        raise ValueError(f"the A1 export holds the products {sorted(CSV_COLUMNS)}, not {product}")
    rows = list(csv.DictReader(path.open()))
    t = [float(row["t_s"]) for row in rows]
    return (t, *([float(row[c]) for row in rows] for c in CSV_COLUMNS[product]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file")
    parser.add_argument("--t1", type=float, required=True)
    parser.add_argument("--t2", type=float, required=True)
    parser.add_argument("--ts", type=float)
    parser.add_argument("--product", default="P")
    parser.add_argument("--chain", help="the chain that completes the product (else resolved)")
    parser.add_argument("--rate", type=float, help="a known constant per-molecule rate >= 0, 1/s")
    args = parser.parse_args(argv)
    if args.rate is not None and not (math.isfinite(args.rate) and args.rate >= 0):
        parser.error(f"--rate is a finite number >= 0, not {args.rate!r}")
    try:
        t, n, Q, D = read(args.file, args.product, args.chain)
    except ValueError as error:
        parser.error(str(error))
    completed, surviving, grew = survivors(t, n, Q, D, args.t1, args.t2, args.ts)
    out = dict(
        completed_fmol=completed,
        surviving_fmol=surviving,
        pool_change_fmol=grew,
        grid_error_fmol=grid_error(t, n, Q, D, args.t1, args.t2, args.ts),
    )
    if args.rate is not None:
        out["surviving_known_rate_fmol"] = known_rate(t, Q, args.rate, args.t1, args.t2, args.ts)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
