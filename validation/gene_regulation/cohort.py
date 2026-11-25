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
term after it. The integral of n over each interval is the trapezoid, h (n_i + n_{i+1})/2, which
is exact as the grid refines. The calculation's error on a grid is stated by running it on every
second output as well and differencing (`grid_error`).

**When the rate is known** (constant k >= 0), `known_rate` gives the closed form for completions
spread evenly over each output interval, through expm1 and with its zero-rate limit (everything
survives), so small and zero rates hold. On the engine's A1 export (revision f96a9606), minutes
60–90 and sampled at minute 90, both reproduce the reviewer's figures: 2.01673e-5 fmol completed
and 1.32977e-5 fmol surviving, while the pool grew by 2.70386e-6 fmol. Its grid error is stated as
grid_error's is (`known_rate_error`). FR-38's cohort is this form at each fate's gross one-way loss
(the sheet's erratum F, §9.19): its members leave at the declared k, while the booked net loss,
k (1 - e^y), also counts re-synthesis, which returns molecules that are not members. The two agree
only where e^y << 1. `known_survival` is FR-38's survival readout in this form.

**Which chain completes the product** (`producing_chain`; the review's finding 2). An engine_run.py
record's own definition names the chain that makes each product row, so the completions are that
chain's: for the mRNA R in A1, transcription's (tx), not translation's (tl). A chain named that
does not make the product is refused, and so is a product that no chain or several chains make,
unless one of them is named. The A1 export's CSV holds tx (making R) and tl (making P). With a
release (the sheet's §9, FR-38), a fate row's inflow is the release's into it, not the chain's
completions, which join the hold (`producers`): this is §9.8's route 2, per fate pool. A row its
cell exports (amendment T, §9.17) is refused: it leaves by export as well as by its loss, so one
pool's reading does not apply, and `series` reads the cohort through the export.

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

import numpy as np

# D283: the window edges' predicate is the clock's one same-instant predicate (it was a seam here,
# equal times, until D283 landed), as templated_polymerisation.grid_time reads on_grid.
from cells.numerics.clock_instants import same_instant
from validation import id_table


def _integral(t, n, i, j):
    """The integral of n over [t_i, t_j] on the output grid, by Simpson's rule on uniform pairs of
    intervals, the trapezoid on what remains. survivors calls it on one interval at a time
    (j = i + 1), where it is the trapezoid."""
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


BOUND_ROUNDING = 1e-12  # Relative: the survivors' allowance above the pool from rounding alone.


def _window(t, t1, t2, ts):
    """(i1, i2, i3) of t1 <= t2 <= ts, each an output time (D264, finding 6; same_instant)."""
    if not t1 <= t2 <= ts:
        raise ValueError(f"the window needs t1 <= t2 <= ts, not {t1}, {t2} and {ts}")
    found = [next((i for i, v in enumerate(t) if same_instant(v, x)), None) for x in (t1, t2, ts)]
    missing = [x for x, i in zip((t1, t2, ts), found, strict=True) if i is None]
    if missing:
        raise ValueError(f"{missing[0]} s is not an output time")
    return tuple(found)


def check_counters(t, n=None, Q=None, D=None):
    """Refuse invalid inputs (D264, finding 6), naming the first fault:
    - every series finite, with one value per output time;
    - the output times strictly increasing, and the pool n non-negative;
    - the completion Q and loss D counters non-decreasing, as cumulative counters always are."""
    if any(not math.isfinite(v) for v in t) or any(b <= a for a, b in zip(t, t[1:], strict=False)):
        raise ValueError("the output times are not finite and strictly increasing")
    for name, seq in (("pool", n), ("completion counter", Q), ("loss counter", D)):
        if seq is None:
            continue
        if len(seq) != len(t):
            raise ValueError(f"the {name} holds {len(seq)} values for {len(t)} output times")
        bad = next((i for i, v in enumerate(seq) if not math.isfinite(v)), None)
        if bad is not None:
            raise ValueError(f"the {name} is {seq[bad]!r} at t = {t[bad]} s")
        if name == "pool":
            low = next((i for i, v in enumerate(seq) if v < 0), None)
            if low is not None:
                raise ValueError(f"the pool is negative at t = {t[low]} s")
            continue
        down = next((i for i in range(len(seq) - 1) if seq[i + 1] < seq[i]), None)
        if down is not None:
            raise ValueError(
                f"the {name} decreases between t = {t[down]} and {t[down + 1]} s: a cumulative "
                "counter never does"
            )


def _cohort(t, n, Q, D, i1, i2, i3):
    """(the cohort at ts, [(t, cohort, pool), ...] at each output after t1): the calculation of the
    module docstring, on outputs i1 to i3, completions counted up to i2."""
    S, path = 0.0, []
    for i in range(i1, i3):
        h = t[i + 1] - t[i]
        lost = D[i + 1] - D[i]
        k = 0.0
        if lost > 0:
            held = _integral(t, n, i, i + 1)
            if held <= 0:
                raise ValueError(f"material is lost from an empty pool at t = {t[i]} s")
            k = lost / held
        made = Q[i + 1] - Q[i] if i < i2 else 0.0
        S = S * math.exp(-k * h) + made * _spread(k * h)
        path.append((t[i + 1], S, n[i + 1]))
    return S, path


def survivors(t, n, Q, D, t1, t2, ts=None):
    """(completed in [t1, t2], surviving at ts, the pool's change over [t1, t2]) from the counters
    on an output grid holding t1, t2 and ts (module docstring). Refused on invalid counters or
    window (check_counters, _window), and where the cohort exceeds the pool at any output from t1
    to ts beyond rounding (D264, finding 5). Labelled material is at most the total, so such a
    result shows outputs too far apart for the calculation. Where all present material is labelled
    the calculation stays below the pool, so the bound refuses no resolved run."""
    ts = t2 if ts is None else ts
    check_counters(t, n, Q, D)
    i1, i2, i3 = _window(t, t1, t2, ts)
    S, path = _cohort(t, n, Q, D, i1, i2, i3)
    for when, cohort, pool in path:
        if cohort > pool * (1 + BOUND_ROUNDING):
            error = grid_error(t, n, Q, D, t1, t2, ts)
            resolution = "its grid error cannot be estimated" if error is None else (
                f"its grid error estimated at {error:.6g} fmol")  # fmt: skip
            raise ValueError(
                f"the cohort, {cohort:.6g} fmol, exceeds the pool, {pool:.6g} fmol, at t = {when} "
                f"s, {resolution}: the outputs are too far apart for this calculation"
            )
    return Q[i2] - Q[i1], S, n[i2] - n[i1]


def known_rate(t, Q, k, t1, t2, ts=None):
    """The survivors at ts for a constant per-molecule rate k >= 0, completions spread evenly over
    each output interval: each interval's dQ e^(-k (ts - t_{i+1})) (1 - e^(-k h))/(k h), formed
    with expm1, so it holds at small k and reaches its limit dQ at k = 0. Refused on an invalid
    completion counter or window."""
    if not (isinstance(k, (int, float)) and math.isfinite(k) and k >= 0):
        raise ValueError(f"a known rate is a finite number >= 0, not {k!r}")
    ts = t2 if ts is None else ts
    check_counters(t, Q=Q)
    i1, i2, _ = _window(t, t1, t2, ts)
    out = 0.0
    for i in range(i1, i2):
        h = t[i + 1] - t[i]
        out += (Q[i + 1] - Q[i]) * math.exp(-k * (ts - t[i + 1])) * _spread(k * h)
    return out


def known_rate_error(t, Q, k, t1, t2, ts=None):
    """|known_rate on every output - known_rate on every second output|: the known-rate form's
    error on the coarser grid, an upper estimate of its error on the given one, as grid_error's.
    None where the window [t1, t2] holds no output to drop: the time resolution is then
    insufficient to estimate it, which is never reported as a zero error. At a constant rate the
    form reads only the window's outputs (outputs after t2 change nothing), so an output dropped
    between t2 and ts alone would give a false zero; the window's own outputs decide."""
    ts = t2 if ts is None else ts
    check_counters(t, Q=Q)
    i1, i2, i3 = _window(t, t1, t2, ts)
    keep = [i for i in range(len(t)) if i % 2 == 0 or i in (i1, i2, i3)]
    if all(i in keep for i in range(i1, i2 + 1)):
        return None
    fine = known_rate(t, Q, k, t1, t2, ts)
    return abs(fine - known_rate([t[i] for i in keep], [Q[i] for i in keep], k, t1, t2, ts))


def known_survival(t, Q, k, t1, t2, ts):
    """FR-38's survival readout at a known constant per-molecule rate k >= 0 (erratum F, §9.19: a
    member leaves its fate row at the loss's gross one-way rate, whatever re-synthesis returns to
    the row): of the releases during [t1, t2), the members alive at t2, the same molecules alive at
    ts >= t2, and their ratio, None at a zero denominator; each count with its grid error
    (known_rate_error, None where it cannot be estimated). The ratio is e^(-k (ts - t2)) by
    construction, so the counts are the readout, not the ratio."""
    alive, later = known_rate(t, Q, k, t1, t2, t2), known_rate(t, Q, k, t1, t2, ts)
    return dict(
        alive_at_window_end=alive,
        alive_at_sample=later,
        ratio=None if alive == 0 else later / alive,
        grid_error_at_window_end=known_rate_error(t, Q, k, t1, t2, t2),
        grid_error_at_sample=known_rate_error(t, Q, k, t1, t2, ts),
    )


def series(t, Q, k_f, forward, n_c, backward, n_o, k_o, t1, t2, ts):
    """FR-38's release-marked cohort through an export (the sheet's §9.17.5, second readout, as
    erratum H, §9.21, item 2, reads it): (in the fate row, at the node) at ts, two pools in series
    on the output grid. The window's releases (Q, released during [t1, t2), spread evenly over
    each interval) join the row; its members leave the row at the fate's gross k_f and by the
    export's forward part, and return by its backward part; at the node they leave at the outside
    loss's gross k_o and by the backward part. Each interval's per-molecule export rates are its
    forward and backward counters' increments over the integral of the row and of the node (the
    trapezoid), held constant over it, and each interval's linear system is solved exactly (the
    matrix exponential of its augmented form). Exact for constant rates in well-mixed pools, up to
    its grid error (series_error). Refused on a negative or non-finite rate, invalid counters or
    pools (check_counters), and an export from an empty pool. Unlike survivors, the result is not
    bounded by the pools to rounding: where a pool starts empty its interval-held rates overshoot
    by the form's O(h^2) error, which series_error estimates, so no pool ceiling is imposed."""
    from scipy.linalg import expm

    for name, rate in (("k_f", k_f), ("k_o", k_o)):
        if not (isinstance(rate, (int, float)) and math.isfinite(rate) and rate >= 0):
            raise ValueError(f"a known rate is a finite number >= 0, not {name} = {rate!r}")
    check_counters(t, n=n_c, Q=Q, D=forward)
    check_counters(t, n=n_o, D=backward)
    i1, i2, i3 = _window(t, t1, t2, ts)
    state = np.zeros(2)
    for i in range(i1, i3):
        h = t[i + 1] - t[i]
        held_c = _integral(t, n_c, i, i + 1)
        held_o = _integral(t, n_o, i, i + 1)
        moved_e, moved_b = forward[i + 1] - forward[i], backward[i + 1] - backward[i]
        for moved, held, where in ((moved_e, held_c, "the fate row"), (moved_b, held_o, "the node")):
            if moved > 0 and held <= 0:
                raise ValueError(
                    f"material is exported from an empty pool ({where}) over [{t[i]}, {t[i + 1]}] s"
                )
        r_e = moved_e / held_c if held_c > 0 else 0.0
        r_b = moved_b / held_o if held_o > 0 else 0.0
        made = (Q[i + 1] - Q[i]) / h if i < i2 else 0.0
        system = np.array([
            [-(k_f + r_e), r_b, made],
            [r_e, -(k_o + r_b), 0.0],
            [0.0, 0.0, 0.0],
        ])  # fmt: skip
        state = (expm(system * h) @ np.array([state[0], state[1], 1.0]))[:2]
    return float(state[0]), float(state[1])


def series_error(t, Q, k_f, forward, n_c, backward, n_o, k_o, t1, t2, ts):
    """|series on every output - series on every second output|, the larger of the fate row's and
    the node's: the series form's error on the coarser grid, an upper estimate on the given one
    for either part (grid_error's form); None where the window holds no output to drop."""
    i1, i2, i3 = _window(t, t1, t2, ts)
    keep = [i for i in range(len(t)) if i % 2 == 0 or i in (i1, i2, i3)]
    if all(i in keep for i in range(i1, i3 + 1)):
        return None
    fine = series(t, Q, k_f, forward, n_c, backward, n_o, k_o, t1, t2, ts)
    pick = [[seq[i] for i in keep] for seq in (t, Q, forward, n_c, backward, n_o)]
    coarse = series(pick[0], pick[1], k_f, pick[2], pick[3], pick[4], pick[5], k_o, t1, t2, ts)
    return max(abs(fine[0] - coarse[0]), abs(fine[1] - coarse[1]))


def grid_error(t, n, Q, D, t1, t2, ts=None):
    """|survivors on every output - survivors on every second output|: the calculation's error on
    the coarser grid, an upper estimate of its error on the given one. None where the window holds
    no output to drop (D264, finding 5): the time resolution is then insufficient to estimate it,
    which is never reported as a zero error."""
    ts = t2 if ts is None else ts
    check_counters(t, n, Q, D)
    i1, i2, i3 = _window(t, t1, t2, ts)
    keep = [i for i in range(len(t)) if i % 2 == 0 or i in (i1, i2, i3)]
    if all(i in keep for i in range(i1, i3 + 1)):
        return None
    fine = _cohort(t, n, Q, D, i1, i2, i3)[0]
    pick = [[seq[i] for i in keep] for seq in (t, n, Q, D)]
    c1, c2, c3 = (keep.index(i) for i in (i1, i2, i3))
    coarse = _cohort(*pick, c1, c2, c3)[0]
    return abs(fine - coarse)


def survival(t, n, Q, D, t1, t2, ts):
    """FR-38's survival readout (the requester's answer to (c) and (e), 22 November 2026): of the
    material completed or released during [t1, t2), the members alive at t2, those same molecules
    alive at ts >= t2, and their ratio, None at a zero denominator; each count with its grid error
    (None where it cannot be estimated). The window's edges are output times, so a release in the
    step that starts at t2 belongs to the next window."""
    _, alive, _ = survivors(t, n, Q, D, t1, t2, t2)
    _, later, _ = survivors(t, n, Q, D, t1, t2, ts)
    return dict(
        alive_at_window_end=alive,
        alive_at_sample=later,
        ratio=None if alive == 0 else later / alive,
        grid_error_at_window_end=grid_error(t, n, Q, D, t1, t2, t2),
        grid_error_at_sample=grid_error(t, n, Q, D, t1, t2, ts),
    )


def label_survival(t, labelled, t2, ts):
    """FR-38's survival readout by route 1 (erratum C, D289): from an engine series of the amount
    one label marks on the output grid (engine_run's label_<row>_<label>, the window's label,
    whose window closes at t2), the members alive at t2, the same molecules alive at ts >= t2, and
    their ratio, None at a zero denominator. The label must receive no arrivals in [t2, ts], as a
    window's label used once does not: the engine's labels follow the molecules, so no grid error
    enters. Refused on an invalid series or window."""
    check_counters(t, n=labelled)
    _, i2, i3 = _window(t, t2, t2, ts)
    alive, later = labelled[i2], labelled[i3]
    return dict(
        alive_at_window_end=alive,
        alive_at_sample=later,
        ratio=None if alive == 0 else later / alive,
    )


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


def producers(chains):
    """({producer: the row it fills}, {producer: its inflow's readout}) of a record's chains at the
    exported cell: a chain fills its product through its completions, int_Q_<chain>. A chain with
    a release (the sheet's §9, FR-38) fills no row at completion, which joins its hold: each of its
    fate rows is filled by the release, named <release>_<fate> (with _<class> where it has several
    classes), through int_Q_<release>_<fate> (_<class>), the class's own counter."""
    makes, counters = {}, {}
    for c in chains:
        release = c.get("release")
        if release is None:
            makes[c["id"]], counters[c["id"]] = c["product"], f"int_Q_{c['id']}"
            continue
        classes = release["fates"]
        for k, pair in enumerate(classes):
            for fate, row in pair.items():
                name = f"{release['id']}_{fate}" + (f"_{k + 1}" if len(classes) > 1 else "")
                makes[name], counters[name] = row, f"int_Q_{name}"
    return makes, counters


def exported_cell(record, block):
    """The cell an engine_run.py record exports (D264's record names it), or for a record without
    one the single cell of its routes, the single-cell format (D265, finding 8)."""
    if record.get("cell"):
        return record["cell"]
    cells = {q["cell"] for q in block["pools"]} | {d["cell"] for d in block["degradations"]}
    cells |= {x["cell"] for x in block["transfers"]}
    if len(cells) != 1:
        raise ValueError(
            f"the record names no exported cell, and its routes are in {sorted(cells)}"
        )
    return next(iter(cells))


def read(path, product="P", chain=None):
    """(t, n, Q, D) of an engine_run.py JSON or the A1 export's CSV, for one product, with Q the
    completions of the chain that makes it (producing_chain)."""
    path = Path(path)
    if path.suffix == ".json":
        r = id_table.load(path)
        (block,) = [o for o in r["definition"]["model"]["operators"] if o["law"] == POLYMERISATION]
        cell = exported_cell(r, block)
        inside = {m["id"]: m["inside"] for m in r["definition"]["model"].get("membranes", ())}
        exports = [e["id"] for e in block.get("exports", ())
                   if e["row"] == product and inside.get(e["patch"]) == cell]  # fmt: skip
        if exports:
            raise ValueError(
                f"{product} at {cell} leaves by export {exports[0]} as well as by its loss "
                "(amendment T, §9.17), so one pool's reading does not apply; the cohort through "
                "an export is series'"
            )
        pool_cell = {q["id"]: q["cell"] for q in block["pools"]}
        here = [c for c in block["chains"] if pool_cell[c["pool"]] == cell]
        local, counters = producers(here)
        elsewhere = {c["id"]: pool_cell[c["pool"]] for c in block["chains"] if c not in here}
        if chain in elsewhere:
            raise ValueError(
                f"chain {chain} is in {elsewhere[chain]}; the record exports {cell} (D265)"
            )
        chain = producing_chain(local, product, chain)
        x = r["readouts"]
        loss = x.get(f"int_D_{product}")
        if loss is None:
            routes = [d["id"] for d in block["degradations"]
                      if d["polymer"] == product and d["cell"] == cell]  # fmt: skip
            if routes:
                raise ValueError(
                    f"the record lacks int_D_{product}, which the loss routes {routes} at {cell} "
                    "supply"
                )
            raise ValueError(
                f"the record lacks int_D_{product}: no loss route of {product} at {cell} is "
                "declared, but the record does not establish zero loss (re-export it)"
            )
        return r["t"], x[f"n_{product}"], x[counters[chain]], loss
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
    try:
        completed, surviving, grew = survivors(t, n, Q, D, args.t1, args.t2, args.ts)
        error = grid_error(t, n, Q, D, args.t1, args.t2, args.ts)
        counted = survival(t, n, Q, D, args.t1, args.t2, args.t2 if args.ts is None else args.ts)
        known = None
        if args.rate is not None:
            known = known_rate(t, Q, args.rate, args.t1, args.t2, args.ts)
    except ValueError as refusal:
        parser.error(str(refusal))
    out = dict(
        completed_fmol=completed,
        surviving_fmol=surviving,
        pool_change_fmol=grew,
        grid_error_fmol=error,
        alive_at_window_end_fmol=counted["alive_at_window_end"],
        alive_at_sample_fmol=counted["alive_at_sample"],
        survival_ratio=counted["ratio"],
    )
    if error is None:
        out["time_resolution"] = (
            "insufficient: the window holds no output to drop, so the grid error cannot be "
            "estimated; sample more often"
        )
    if known is not None:
        out["surviving_known_rate_fmol"] = known
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
