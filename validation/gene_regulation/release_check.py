"""FR-38's R1 checks (the sheet's §9.7-§9.10; D284): the requester's limit, the four fractions
beside their matched blanks, the zero-rate route's idleness, the fate rows at the trace floor, the
identities at every saved time with either machine option, and the release-window cohort by both
of §9.8's routes. Development, not judged: the registered comparison against code-blind
references comes after (D284).

It reads an engine_run.py directory of R1's runs (worlds.release_names(), at the test instance and
dt worlds.R1_DT) and writes release_check.json there. R1L is R1 at p = 0.75 with FR-42's labels on
its fate rows (erratum C); with --part R2, a directory of R2's runs
(worlds.r2_names() and r2_check_names() beside A1, at A1's step), writing release_check_r2.json.
It exits 1 when any check fails. R2's checks are its identities and energy, its route-2 cohort
(§9.12, reading 8), and the addendum's development check: its total RNA and protein approaching
A1's as tau shrinks.

The tolerances were written before the acceptance runs, after one development run (R1 p=0.75
returned) had been read. They come from §9.10's distance and the step's error, not from that run.
Two were revised after the first development set of R1 (all its 14 runs) had been read, each a
checker fault, not a loosening against a measured gap: G's identity bound gained the moving rows'
G terms (the blanks' rounding of those terms, about 2e-16 pJ, exceeded a bound scaled by their
tiny bookings alone), and the class-total check compares each run minus its own blank (a
labelled run carries two traces, an unlabelled one one). Neither revision changed a tolerance's
number:
- **Identities** (per producer, the hold's, each fate row's, the machines'): rounding alone,
  |residual| <= FLOOR_FMOL + ROUNDING x steps x the largest term, with ROUNDING = 8 eps. G's
  identity and the routes' heats against the booked heat: ROUNDING x steps x (the bookings'
  magnitude + the moving rows' G terms, whose amounts each step rounds).
- **The hold and the releases** against their closed forms: the release has no affinity factor,
  so only the step's error, (k h)^3 k T/24 < 1e-11 at R1_DT, and rounding: 1e-10 relative.
- **The survivors** (a run minus its matched blank) and route 1's cohort against the closed forms:
  each loss carries (1 - e^(y_f)), e^(y_f) ~ 9.4e-9 at R1's state (§9.10): 3e-8 relative.
- **The requester's six-decimal figures:** within half a unit of the last digit, 5e-7 copies.
- **The zero-rate route** at p = 0 and 1: its releases and H_rel exactly 0.0 at every output, and
  its fate row the blank's within 3e-8 relative, above zero (the trace floor).
- **Route 1 on shares** (§9.8 as erratum C amends it, D289): the labelled run's fate row times its
  window label's share, engine_run's label_<row>_cohort, with no blank, since a cohort starts at
  exactly zero as a share and the loss is computed once on the physical row.
  - **R1L is R1 with labels:** every readout but the label exports, and every check, is the
    unlabelled run's bit for bit, and each row's label amounts sum to the row within the shares'
    rounding (128 eps of the row).
  - **Against the closed forms:** SURVIVORS (the loss's (1 - e^(y_f)), as for the survivors) plus
    the share update's split, k_f h^2/(12 tau) relative (erratum C: numerics/label_shares.advance
    errs by (a k' - a' k) h^3/12 per half-step h, and in R1 the arrivals decay with the hold, a' =
    -a/tau, at a near-constant loss rate k_f). Both terms come from stated error terms, not from a
    run's gap.
  - **The cohort** (erratum F, §9.19) is the molecules released from their template in the
    window, marked on transcription's own label schedule (worlds.r1, labelled), so a molecule
    re-synthesised from monomers is not a member.
  - **Route 2** (erratum F) is cohort.py's known-rate form on the unlabelled run's releases into
    each fate, carried at the fate's declared first-order rate k, the gross one-way loss
    (gross_rate, from the run's own definition), not at the booked net loss int_D/n = k (1 -
    e^(y_f)).
  - **The two routes** (§9.8) agree within route 2's grid error (cohort.known_rate_error) plus
    that bound on route 1.
  - **The survival readout** (the requester's answer to (c) and (e)): the window's members alive
    at its end, the same molecules an hour later, and their ratio, None at a zero denominator, by
    route 1 (cohort.label_survival) against e^(-k_f 3600 s) within twice route 1's bound, and by
    route 2 (cohort.known_survival), whose ratio is e^(-k 3600 s) by construction at the declared
    k, against the sheet's k_f within the counts' grid errors. So that a record whose booked loss
    is not its declared k is still caught where no route 1 is run (R2), route 2's counts must
    also agree with the net reading (cohort.survival on the fate row's own n, int_Q and int_D)
    within both grid errors plus SURVIVORS: erratum F's item 4, the two agree only where e^(y_f)
    << 1, as at the sheet's state (about 9.4e-9; §9.10).
  - **That net agreement is scoped to e^(y_f) << 1** (FR-38's second comparison, protocol §5: it
    fails by design in its AN family, where e^(y_f) is about 0.13). The net reading departs from
    the gross one by about k_f (ts - t1) max e^(y_f), relative, since re-synthesis returns
    molecules at k_f e^(y_f) per molecule present. So the sub-check applies where that reach is
    within SURVIVORS, its own allowance (net_scope, from the record's own rows and potentials),
    and is reported as out of scope, neither pass nor fail, elsewhere. R1's runs stay in scope:
    their reach is at most 2.6e-8.

Run: python -m validation.gene_regulation.release_check DIR
"""

import argparse
import json
import math
import sys
from pathlib import Path

from cells.definitions.specs import parse_spec
from cells.operators.templated_polymerisation import COPY_FMOL, FLOOR_FMOL
from validation.gene_regulation import cohort, engine_run, worlds
from validation.gene_regulation import sheet_check as sheet

ROUNDING = 8 * 2.0**-52
RELEASES = 1e-10  # Relative: the hold and the releases against their closed forms.
SURVIVORS = 3e-8  # Relative: the survivors, the cohort and the label rows' sum (§9.10).
FIGURES = 5e-7  # Copies: half a unit of the requester's sixth decimal.
LIMIT = dict(
    p=0.75,
    t=3600.0,
    held=40.0,
    released=40.0,
    durable=30.0,
    short_lived=10.0,
    surviving_durable=24.852814,
    surviving_short_lived=5.000000,
)
SET = "test instance"
RID = worlds.RELEASE
FATE_ROWS = dict(durable="R", short_lived="R_s")
SHARES = 128 * 2.0**-52  # A row's label amounts against the row: the shares' domain allows 64 ulps.


def _path(directory, name):
    return Path(directory) / engine_run.slug(SET) / f"{engine_run.slug(name)}.json"


def _load(directory, name):
    run = json.loads(_path(directory, name).read_text())
    run["path"] = str(_path(directory, name))
    return run


def closed_forms(p, t):
    """The limit's closed forms (§9.10) in copies at time t: (hold, released into each fate,
    surviving in each fate), with k_e = 1/tau."""
    r = sheet.RELEASE
    H0, ke = float(r["H0"]), 1.0 / float(r["tau"])
    k = dict(durable=float(r["k_durable"]), short_lived=float(r["k_short"]))
    split = dict(durable=p, short_lived=1.0 - p)
    hold = H0 * math.exp(-ke * t)
    released = {f: split[f] * H0 * -math.expm1(-ke * t) for f in k}
    surviving = {
        f: split[f] * H0 * ke * math.exp(-ke * t) * -math.expm1(-(k[f] - ke) * t) / (k[f] - ke)
        for f in k
    }
    return hold, released, surviving


def window_cohort(p, fate, t1, t2, ts):
    """The closed form (copies) of the releases into `fate` in [t1, t2] still present at ts."""
    r = sheet.RELEASE
    H0, ke = float(r["H0"]), 1.0 / float(r["tau"])
    kf = float(r["k_durable" if fate == "durable" else "k_short"])
    share = p if fate == "durable" else 1.0 - p
    d = kf - ke
    return share * H0 * ke * math.exp(-kf * ts) * (math.exp(d * t2) - math.exp(d * t1)) / d


class Checks:
    def __init__(self):
        self.rows, self.failed = [], []

    def add(self, name, ok, **detail):
        self.rows.append(dict(check=name, ok=bool(ok), **detail))
        if not ok:
            self.failed.append(name)


def _relative(value, expected):
    return abs(value - expected) / abs(expected) if expected else abs(value)


def gross_rate(record, row):
    """The declared first-order rate k (1/s) of fate row `row`'s loss at the record's exported
    cell, the gross one-way loss of erratum F (§9.19): the sum over the row's degradations there of
    each one's scheduled rate, from the record's own definition. Refused where a rate changes
    during the run, since the known-rate form needs a constant k."""
    raw = record["definition"]
    (block,) = [o for o in raw["model"]["operators"] if o["law"] == worlds.POLYMERISATION]
    cell = cohort.exported_cell(record, block)
    routes = {d["id"] for d in block["degradations"] if d["polymer"] == row and d["cell"] == cell}
    total = 0.0
    for control in raw["experiment"]["polymerisation_controls"]:
        if control["route_id"] not in routes:
            continue
        values = {float(change["value"]) for change in control["schedule"]}
        if len(values) != 1:
            raise ValueError(
                f"{control['route_id']}'s rate changes during the run: the known-rate form needs "
                "a constant k"
            )
        total += values.pop()
    return total


def _bound(steps, *terms):
    return FLOOR_FMOL + ROUNDING * steps * max(abs(x) for x in terms)


def identities(checks, name, run, machine):
    """The hold's, each fate row's and the producer's identities, and the machines', at every
    saved time (§9.7)."""
    x = run["readouts"]
    steps = run["steps"]
    H0 = x[f"H_{RID}"][0]
    fates = [FATE_ROWS]
    worst = dict(hold=0.0, fate=0.0, producer=0.0, machines=0.0)
    for i, _ in enumerate(run["t"]):
        A, H = x["int_Q_tx"][i], x[f"H_{RID}"][i]
        out = sum(x[f"int_Q_{RID}_{f}"][i] for f in FATE_ROWS)
        residual = H0 + A - H - out
        worst["hold"] = max(worst["hold"], abs(residual) / _bound(steps, H0, A, H, out))
        kept = lost = 0.0
        for k, rows in enumerate(fates):
            for f, row in rows.items():
                gained = x[f"n_{row}"][i] - x[f"n_{row}"][0]
                into = (x[f"int_Q_{RID}_{f}_{k + 1}"] if len(fates) > 1 else x[f"int_Q_{RID}_{f}"])[
                    i
                ]
                gone = x[f"int_D_{row}"][i]
                fate = gained - into + gone
                bound = _bound(steps, x[f"n_{row}"][i], into, gone)
                worst["fate"] = max(worst["fate"], abs(fate) / bound)
                kept, lost = kept + gained, lost + gone
        producer = H0 + A - H - kept - lost
        worst["producer"] = max(
            worst["producer"], abs(producer) / _bound(steps, H0, A, H, kept, lost)
        )
        M = float(sheet.A1["M_pol"]) * COPY_FMOL
        F, E = x["F_pol"][i], x["E_tx"][i]  # E: sum C, plus H where held (§9.12, reading 6).
        machines = F + E - M
        worst["machines"] = max(worst["machines"], abs(machines) / _bound(steps, F, E, M))
    for key, value in worst.items():
        checks.add(
            f"{name}: the {key} identity at every saved time",
            value <= 1.0,
            largest_over_bound=value,
        )


def limits(checks, name, run, blank, p):
    """The hold, the releases and the survivors (minus the matched blank) at every output against
    the closed forms, and at the requester's case its six-decimal figures."""
    x, xb = run["readouts"], blank["readouts"]
    worst = dict(hold=0.0, released=0.0, surviving=0.0)
    for i, t in enumerate(run["t"]):
        hold, released, surviving = closed_forms(p, t)
        worst["hold"] = max(worst["hold"], _relative(x[f"H_{RID}"][i] / COPY_FMOL, hold))
        for f, row in FATE_ROWS.items():
            got = x[f"int_Q_{RID}_{f}"][i] / COPY_FMOL
            worst["released"] = max(
                worst["released"], _relative(got, released[f]) if released[f] else abs(got)
            )
            alive = (x[f"n_{row}"][i] - xb[f"n_{row}"][i]) / COPY_FMOL
            worst["surviving"] = max(
                worst["surviving"], _relative(alive, surviving[f]) if surviving[f] else abs(alive)
            )
    checks.add(
        f"{name}: the hold against its closed form",
        worst["hold"] <= RELEASES,
        largest_relative=worst["hold"],
    )
    checks.add(
        f"{name}: the releases against their closed forms",
        worst["released"] <= RELEASES,
        largest_relative=worst["released"],
    )
    checks.add(
        f"{name}: the survivors, minus the blank, against their closed forms",
        worst["surviving"] <= SURVIVORS,
        largest_relative=worst["surviving"],
    )
    if p != LIMIT["p"]:
        return
    i = run["t"].index(LIMIT["t"])
    copies = dict(
        held=x[f"H_{RID}"][i],
        released=x[f"int_Q_{RID}_durable"][i] + x[f"int_Q_{RID}_short_lived"][i],
        durable=x[f"int_Q_{RID}_durable"][i],
        short_lived=x[f"int_Q_{RID}_short_lived"][i],
        surviving_durable=x["n_R"][i] - xb["n_R"][i],
        surviving_short_lived=x["n_R_s"][i] - xb["n_R_s"][i],
    )
    copies = {k: v / COPY_FMOL for k, v in copies.items()}
    for key, value in copies.items():
        checks.add(
            f"{name}: the requester's {key} at 1 h",
            abs(value - LIMIT[key]) <= FIGURES,
            copies=value,
            requester=LIMIT[key],
        )


def idle(checks, name, run, blank, p):
    """At p = 0 or 1, the zero-rate route's releases and H_rel exactly 0.0 at every output, and
    its fate row the blank's, above zero: the trace floor."""
    if p not in (0.0, 1.0):
        return
    fate = "durable" if p == 0.0 else "short_lived"
    x, xb = run["readouts"], blank["readouts"]
    zero = all(v == 0.0 for v in x[f"int_Q_{RID}_{fate}"] + x[f"H_rel_{RID}_{fate}"])
    checks.add(f"{name}: the {fate} route idle, bit for bit", zero)
    row = FATE_ROWS[fate]
    worst = max(_relative(a, b) for a, b in zip(x[f"n_{row}"], xb[f"n_{row}"], strict=True))
    floor = min(x[f"n_{row}"]) > 0
    checks.add(
        f"{name}: the {fate} row at the trace floor, the blank's",
        worst <= SURVIVORS and floor,
        largest_relative=worst,
        smallest_fmol=min(x[f"n_{row}"]),
    )


def _moved_terms(run):
    """The G terms of the rows that move, sum |n| RT (|mu°/RT| + |ln(n/(V c0))| + 1) in pJ at
    their largest: what each step's rounding of their amounts carries into G's identity."""
    spec = parse_spec(run["definition"])
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    mu = dict(zip([s.id for s in block.species], block.mu_RT, strict=True))
    scale = spec.model.cells[0].volume_pL * block.c0_mM
    rt = float(sheet.R_GAS * sheet.T_K) / 1000  # pJ per fmol per unit of mu/RT.
    total = 0.0
    for row, m in mu.items():
        series = run["readouts"][f"n_{row}"]
        if len(set(series)) > 1:
            total += max(abs(n) * rt * (abs(m) + abs(math.log(n / scale)) + 1) for n in series)
    return total


def energy(checks, name, run):
    """G(t) - G(0) + sum H = 0 and the routes' heats summing to the booked heat, both at rounding
    (ROUNDING x steps x the bookings' magnitude and the moving rows' G terms), and every heat
    class, H_rel among them, non-decreasing (no driven work: §9.5)."""
    c = run["checks"]
    scale = c["energy_magnitude_at_end_pJ"] + _moved_terms(run)
    bound = ROUNDING * run["steps"] * scale
    checks.add(
        f"{name}: G's identity",
        c["G_identity_largest_pJ"] <= bound,
        largest_pJ=c["G_identity_largest_pJ"],
        bound_pJ=bound,
    )
    split = c["routes_minus_total_largest_pJ"]
    checks.add(
        f"{name}: the routes' heats sum to the booked heat",
        split <= bound,
        largest_pJ=split,
        bound_pJ=bound,
    )
    least = min(c["smallest_class_increment"].values())
    checks.add(f"{name}: every heat class non-decreasing", least >= 0.0, smallest=least)


def split_bound(fate, dt):
    """Route 1's relative error from the share update's split (erratum C): k_f h^2/(12 tau) at the
    half-step h = dt/2, the arrivals into the fate decaying with the hold (a' = -a/tau) at a
    near-constant loss rate k_f (numerics/label_shares.advance's (a k' - a' k) h^3/12)."""
    r = sheet.RELEASE
    k = float(r["k_durable" if fate == "durable" else "k_short"])
    h = dt / 2
    return k * h * h / (12.0 * float(r["tau"]))


def cohorts(checks, runs, machine):
    """§9.8's two routes for the releases in R1's window at p = 0.75 (errata C and F): route 1 on
    shares, the labelled run's label_<row>_cohort, marked on transcription's own schedule, with no
    blank; route 2, cohort.py's known-rate form on the unlabelled run's releases at each fate's
    gross k (gross_rate). R1L is R1 with labels: every other readout and every check bit for
    bit."""
    t1, t2 = worlds.R1_WINDOW
    base, window = worlds.R1_LABELS
    plain, labelled = runs[f"R1 p=0.75 {machine}"], runs[f"R1L p=0.75 {machine}"]
    x, xl = plain["readouts"], labelled["readouts"]
    physical = {k: v for k, v in xl.items() if not k.startswith("label_")}
    differ = sorted(k for k in set(x) | set(physical) if x.get(k) != physical.get(k))
    same = not differ and labelled["checks"] == plain["checks"]
    checks.add(
        f"R1L p=0.75 {machine}: every readout and check the unlabelled run's, bit for bit",
        same,
        differing=differ[:5],
    )
    worst = max(
        abs(xl[f"label_{row}_{base}"][i] + xl[f"label_{row}_{window}"][i] - x[f"n_{row}"][i])
        / x[f"n_{row}"][i]
        for row in FATE_ROWS.values()
        for i in range(len(plain["t"]))
    )
    checks.add(
        f"R1L p=0.75 {machine}: each fate row's label amounts sum to the row",
        worst <= SHARES,
        largest_relative=worst,
    )
    starts = [xl[f"label_{row}_{window}"][plain["t"].index(t1)] for row in FATE_ROWS.values()]
    checks.add(f"R1L p=0.75 {machine}: the cohort starts at exactly zero", starts == [0.0, 0.0])
    for f, row in FATE_ROWS.items():
        bound = SURVIVORS + split_bound(f, labelled["dt_s"])
        cohort1 = [v / COPY_FMOL for v in xl[f"label_{row}_{window}"]]
        t, _, Q, _ = cohort.read(plain["path"], row)  # Its own releases into the fate.
        k = gross_rate(plain, row)
        for ts in (t2, 2 * t2):
            i = plain["t"].index(ts)
            route1 = cohort1[i]
            route2 = cohort.known_rate(t, Q, k, t1, t2, ts)
            error = cohort.known_rate_error(t, Q, k, t1, t2, ts)
            # An unavailable grid error is insufficient resolution and fails the check (fail-closed,
            # as replace_restart.agreement); it is never read as an infinite bound.
            route2, error = route2 / COPY_FMOL, (None if error is None else error / COPY_FMOL)
            exact = window_cohort(0.75, f, t1, t2, ts)
            checks.add(
                f"R1L p=0.75 {machine}: route 1's {f} cohort at {ts:g} s, the closed form",
                _relative(route1, exact) <= bound,
                copies=route1,
                closed_form=exact,
                bound=bound,
            )
            checks.add(
                f"R1 p=0.75 {machine}: the two routes' {f} cohort at {ts:g} s",
                error is not None and abs(route1 - route2) <= error + bound * abs(route1),
                route1=route1,
                route2=route2,
                grid_error=error,
            )
        counted = cohort.label_survival(plain["t"], cohort1, t2, 2 * t2)
        k = float(sheet.RELEASE["k_durable" if f == "durable" else "k_short"])
        expected = math.exp(-k * t2)
        checks.add(
            f"R1L p=0.75 {machine}: route 1's {f} survival, alive at {t2:g} s and at {2 * t2:g} s",
            counted["ratio"] is not None and _relative(counted["ratio"], expected) <= 2 * bound,
            alive_copies=counted["alive_at_window_end"],
            later_copies=counted["alive_at_sample"],
            ratio=counted["ratio"],
            closed_form_ratio=expected,
            bound=2 * bound,
        )
        survival(checks, f"R1 p=0.75 {machine}", plain["path"], row, f)


def net_scope(record, row, k, t1, ts):
    """Whether the net agreement applies (the module docstring): {exp_y_largest, reach, in_scope}.
    e^(y_f), y_f = sum_m nu_m (mu°_m + ln(c_m/c0)) - (mu°_f + ln(c_f/c0))/L per residue (the sheet's
    §4.4), is formed at each output from the record's own rows (n/V, V its exported V where water
    moves it, else the cell's declared volume) and its definition's potentials and degradation."""
    raw = record["definition"]
    (block,) = [o for o in raw["model"]["operators"] if o["law"] == worlds.POLYMERISATION]
    cell = cohort.exported_cell(record, block)
    route = next(d for d in block["degradations"] if d["polymer"] == row and d["cell"] == cell)
    mu = {s["id"]: float(s["standard_mu_RT"]) for s in block["species"]}
    c0 = float(block["standard_concentration_mM"])
    x = record["readouts"]
    missing = sorted(({f"n_{m}" for m in route["monomers"]} | {f"n_{row}"}) - set(x))
    if missing:  # A record that cannot show e^(y_f): the sub-check applies, as before its scope.
        return dict(exp_y_largest=None, reach=None, in_scope=True,
                    why=f"the record lacks {missing}, so e^(y_f) is not formed")  # fmt: skip
    declared = next(c["volume_pL"] for c in raw["model"]["cells"] if c["id"] == cell)
    volume = x.get("V", [float(declared)] * len(record["t"]))
    largest = 0.0
    for i, v in enumerate(volume):
        y = math.fsum(nu * (mu[m] + math.log(x[f"n_{m}"][i] / (v * c0)))
                      for m, nu in route["monomers"].items())  # fmt: skip
        y -= (mu[row] + math.log(x[f"n_{row}"][i] / (v * c0))) / route["residues"]
        largest = max(largest, math.exp(y))
    reach = k * (ts - t1) * largest
    return dict(exp_y_largest=largest, reach=reach, in_scope=reach <= SURVIVORS)


def survival(checks, name, path, row, fate, *, window=None, ts=None, k_expected=None):
    """The requester's survival readout (FR-38's (c) and (e), 22 November 2026) by route 2 at the
    fate's gross k (erratum F; cohort.known_survival): the window's members alive at its end, the
    same alive at ts (an hour later in R1), and their ratio, against the closed forms' ratio,
    e^(-k_f (ts - t2)), within the counts' grid errors. Its counts must also agree with the net
    reading on the row's own counters (cohort.survival) within both grid errors plus SURVIVORS
    (the module docstring), so that a record whose booked loss is not its declared k fails, where
    e^(y_f) << 1 (net_scope); elsewhere that agreement is reported out of scope. It fails closed
    (the Lean lane's finding at a6acbc27): an empty cohort (none alive at the window's end, an
    undefined ratio) is reported as such, and counts whose grid error cannot be estimated (outputs
    too far apart) as insufficient resolution; neither passes. window, ts and k_expected default
    to R1's window, 2 t2 and the sheet's k_f; another world (FR-38's second comparison) gives its
    own."""
    t1, t2 = worlds.R1_WINDOW if window is None else window
    ts = 2 * t2 if ts is None else ts
    record = json.loads(Path(path).read_text())
    t, n, Q, D = cohort.read(path, row)
    gross = gross_rate(record, row)
    counted = cohort.known_survival(t, Q, gross, t1, t2, ts)
    net = cohort.survival(t, n, Q, D, t1, t2, ts)
    k = (float(sheet.RELEASE["k_durable" if fate == "durable" else "k_short"])
         if k_expected is None else float(k_expected))  # fmt: skip
    expected = math.exp(-k * (ts - t2))
    alive, later = counted["alive_at_window_end"], counted["alive_at_sample"]
    ends = ("window_end", "sample")
    errors = [counted[f"grid_error_at_{e}"] for e in ends]
    net_errors = [net[f"grid_error_at_{e}"] for e in ends]
    what = f"{name}: route 2's {fate} survival, alive at {t2:g} s and at {ts:g} s"
    detail = dict(
        alive_copies=alive / COPY_FMOL,
        later_copies=later / COPY_FMOL,
        ratio=counted["ratio"],
        closed_form_ratio=expected,
        gross_rate_per_s=gross,
        net_alive_copies=net["alive_at_window_end"] / COPY_FMOL,
        net_later_copies=net["alive_at_sample"] / COPY_FMOL,
    )
    if counted["ratio"] is None:
        checks.add(what, False, status="empty cohort", **detail)
        return
    if None in errors or None in net_errors:
        checks.add(what, False, status="insufficient resolution", **detail)
        return
    # The ratio's own rounding, beside the counts' grid errors (the Lean lane's turnover_roundoff
    # control: at constant turnover the known-rate form is exact on any grid, its grid error exactly
    # zero, and the ratio one ulp above 1/4 failed a zero bound). Each count sums the window's m
    # non-negative terms, each within 4 eps (its exp, its spread and two products), the sum adding at
    # most (m - 1) eps; the division adds eps and the closed form's exp eps: (2 m + 8) eps relative.
    m = sum(1 for x in t if t1 <= x < t2)
    rounding = (2 * m + 8) * sys.float_info.epsilon * expected
    bound = (errors[1] + expected * errors[0]) / alive + rounding
    ok = abs(counted["ratio"] - expected) <= bound
    gaps = [
        abs(counted[f"alive_at_{e}"] - net[f"alive_at_{e}"])
        - (a + b + SURVIVORS * counted[f"alive_at_{e}"])
        for e, a, b in zip(ends, errors, net_errors, strict=True)
    ]
    scope = net_scope(record, row, gross, t1, ts)
    agree = max(gaps) <= 0.0 if scope["in_scope"] else None  # None: out of scope, not judged.
    checks.add(what, ok and agree is not False, status="compared", bound=bound,
               net_agrees=agree, net_scope=scope, **detail)  # fmt: skip


def r2_cohorts(checks, name, run):
    """R2's release-window cohort by route 2 alone (§9.12, reading 8): cohort.py's known-rate form
    on each fate's releases for R1's window at the fate's gross k (erratum F; gross_rate), sampled
    at its end and an hour later, reported with its grid error, which must be estimable at R2's
    outputs."""
    t1, t2 = worlds.R1_WINDOW
    for f, row in FATE_ROWS.items():
        t, _, Q, _ = cohort.read(run["path"], row)  # Its own releases into the fate.
        k = gross_rate(run, row)
        completed = Q[t.index(t2)] - Q[t.index(t1)]
        for ts in (t2, 2 * t2):
            surviving = cohort.known_rate(t, Q, k, t1, t2, ts)
            error = cohort.known_rate_error(t, Q, k, t1, t2, ts)
            checks.add(
                f"{name}: route 2's {f} cohort at {ts:g} s",
                error is not None and 0.0 <= surviving <= completed,
                released_copies=completed / COPY_FMOL,
                surviving_copies=surviving / COPY_FMOL,
                grid_error_copies=None if error is None else error / COPY_FMOL,
            )
        survival(checks, name, run["path"], row, f)


def approach(checks, runs, machine):
    """The addendum's development check (§9.9): with both fates at A1's k_R, R2's total RNA (R +
    R_s) and protein follow A1's, delayed by the hold, so their largest distance from A1's,
    relative to A1's largest, falls as tau is divided by 10 and by 100."""
    a1 = runs["A1"]["readouts"]
    out = {}
    for k in (1, 10, 100):
        x = runs[f"R2A tau/{k} {machine}"]["readouts"]
        rna = [r + s for r, s in zip(x["n_R"], x["n_R_s"], strict=True)]
        out[k] = {
            what: max(abs(a - b) for a, b in zip(mine, a1[row], strict=True)) / max(a1[row])
            for what, mine, row in (("RNA", rna, "n_R"), ("protein", x["n_P"], "n_P"))
        }
    for what in ("RNA", "protein"):
        d = [out[k][what] for k in (1, 10, 100)]
        checks.add(
            f"R2A {machine}: its {what} approaches A1's as tau shrinks",
            d[0] > d[1] > d[2],
            distances=dict(zip(("tau", "tau/10", "tau/100"), d, strict=True)),
        )


def check_r2(directory):
    """R2 (§9.9, its addendum and §9.12) at A1's step: each machine option's identities, energy and
    route-2 cohort, and the development check beside A1."""
    directory = Path(directory)
    names = [*worlds.r2_names(), *worlds.r2_check_names(), "A1"]
    runs = {name: _load(directory, name) for name in names}
    checks = Checks()
    for machine in ("returned", "held"):
        name = f"R2 {machine}"
        identities(checks, name, runs[name], machine)
        energy(checks, name, runs[name])
        r2_cohorts(checks, name, runs[name])
        approach(checks, runs, machine)
    return _write(directory, "release_check_r2.json", checks)


def switches(checks, name, run, plain):
    """R1S (worlds.r1s): labels marked at completion (the hold's own shares, D296) and p changed
    mid-run, compiled, against R1SU, the same world unlabelled.
    - Every readout but the label exports, and every check, R1SU's bit for bit.
    - The hold's and each fate row's label amounts sum to them, and the cohort starts at exactly
      zero.
    - The hold's cohort, the completions of [0, R1S_TIMES[0]) still held, against route 2's
      known-rate calculation on the run's own completions (cohort.known_rate at the hold's exact
      per-molecule exit rate 1/tau), within its grid error (the same on every second output) plus
      the survivors' bound.
    - Each fate's share of every interval's releases is that interval's p, 0.75 and then 0.25."""
    x, xu = run["readouts"], plain["readouts"]
    switch, change, _ = worlds.R1S_TIMES
    base, window = worlds.R1_LABELS
    t, A = run["t"], x["int_Q_tx"]
    physical = {k: v for k, v in x.items() if not k.startswith("label_")}
    differ = sorted(k for k in set(xu) | set(physical) if xu.get(k) != physical.get(k))
    checks.add(
        f"{name}: every readout and check the unlabelled run's, bit for bit",
        not differ and run["checks"] == plain["checks"],
        differing=differ[:5],
    )
    pairs = [(f"n_{row}", f"label_{row}") for row in FATE_ROWS.values()]
    pairs.append((f"H_{RID}", f"label_H_{RID}"))
    worst = max(
        abs(x[f"{label}_{base}"][i] + x[f"{label}_{window}"][i] - x[total][i])
        / max(x[total][i], FLOOR_FMOL)
        for total, label in pairs
        for i in range(len(t))
    )
    checks.add(f"{name}: each hold's and row's label amounts sum to it", worst <= SHARES,
               largest_relative=worst)  # fmt: skip
    starts = [x[f"{label}_{window}"][0] for _, label in pairs]
    checks.add(f"{name}: the cohort starts at exactly zero", starts == [0.0] * len(pairs))
    rate = 1.0 / float(sheet.RELEASE["tau"])
    keep = [i for i in range(len(t)) if i % 2 == 0 or t[i] in (0.0, switch, t[-1])]
    worst = 0.0
    for i, now in enumerate(t):
        if now < switch:
            continue
        held = x[f"label_H_{RID}_{window}"][i]
        fine = cohort.known_rate(t, A, rate, 0.0, switch, now)
        if now in [t[k] for k in keep]:
            coarse = cohort.known_rate([t[k] for k in keep], [A[k] for k in keep], rate, 0.0,
                                       switch, now)  # fmt: skip
            bound = abs(fine - coarse) + SURVIVORS * abs(fine)
            worst = max(worst, abs(held - fine) / bound)
    checks.add(
        f"{name}: the hold's cohort, route 2's known-rate calculation, within its grid error",
        worst <= 1.0,
        largest_over_bound=worst,
    )
    worst = 0.0
    for i, now in enumerate(t):
        if i == 0:
            continue
        out = {f: x[f"int_Q_{RID}_{f}"][i] - x[f"int_Q_{RID}_{f}"][i - 1] for f in FATE_ROWS}
        p = 0.75 if now <= change else 0.25
        share = out["durable"] / (out["durable"] + out["short_lived"])
        worst = max(worst, abs(share - p))
    checks.add(
        f"{name}: each interval's releases split by its p",
        worst <= 1e-12,
        largest=worst,
    )


def check_switch(directory):
    """R1S at each machine option, beside R1SU: its identities, energy, labels and p's switch."""
    directory = Path(directory)
    checks = Checks()
    for machine in ("returned", "held"):
        name = f"R1S {machine}"
        run, plain = _load(directory, name), _load(directory, f"R1SU {machine}")
        identities(checks, name, run, machine)
        energy(checks, name, run)
        switches(checks, name, run, plain)
    return _write(directory, "release_check_switch.json", checks)


def _write(directory, file, checks):
    record = dict(
        kind="cells.gene_regulation.release_check@1",
        what=__doc__.splitlines()[0],
        tolerances=dict(
            rounding=ROUNDING, releases=RELEASES, survivors=SURVIVORS, figures_copies=FIGURES
        ),
        passed=not checks.failed,
        failed=checks.failed,
        checks=checks.rows,
    )
    (Path(directory) / file).write_text(json.dumps(record, indent=1) + "\n")
    return record


def check(directory):
    """R1 (§9.9): its runs of worlds.release_names()."""
    directory = Path(directory)
    runs = {name: _load(directory, name) for name in worlds.release_names()}
    checks = Checks()
    for machine in ("returned", "held"):
        blank = runs[f"R1 blank {machine}"]
        for value in sheet.RELEASE["p_cases"]:
            p = float(value)
            name = f"R1 p={format(p, 'g')} {machine}"
            run = runs[name]
            identities(checks, name, run, machine)
            limits(checks, name, run, blank, p)
            idle(checks, name, run, blank, p)
            energy(checks, name, run)
        for name in (f"R1 blank {machine}", f"R1L p=0.75 {machine}"):
            identities(checks, name, runs[name], machine)
            energy(checks, name, runs[name])
        cohorts(checks, runs, machine)
    return _write(directory, "release_check.json", checks)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("directory")
    parser.add_argument("--part", choices=("R1", "R2", "switch"), default="R1")
    args = parser.parse_args(argv)
    record = dict(R1=check, R2=check_r2, switch=check_switch)[args.part](args.directory)
    print(f"{len(record['checks'])} checks, {len(record['failed'])} failed")
    for name in record["failed"]:
        print("FAILED", name)
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
