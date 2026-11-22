"""FR-38's R1 checks (the sheet's §9.7-§9.10; D284): the requester's limit, the four fractions
beside their matched blanks, the zero-rate route's idleness, the fate rows at the trace floor, the
identities at every saved time with either machine option, and the release-window cohort by both
of §9.8's routes. Development, not judged: the registered comparison against code-blind
references comes after (D284).

It reads an engine_run.py directory of R1's runs (worlds.release_names(), at the test instance and
dt worlds.R1_DT) and writes release_check.json there; with --part R2, a directory of R2's runs
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
- **The two cohort routes** (§9.8) agree within route 2's grid error (cohort.grid_error) plus the
  label rows' departure. Each label row's loss reads its own potential, so the class rows are not
  neutral labels (erratum B, §9.13): their sum departs from the unlabelled row by at most about
  1e-8 relative at R1, the size of the e^(y_f) term, and route 1 is provisional until FR-42's
  share labels (D289) replace the class rows. It is checked here: each fate's class total minus
  the labelled blank's against the unlabelled row minus its blank's, within 3e-8 relative.

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
LABEL_ROWS = dict(zip(("durable", "short_lived"), worlds.R1_LABEL_ROWS, strict=True))


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


def _bound(steps, *terms):
    return FLOOR_FMOL + ROUNDING * steps * max(abs(x) for x in terms)


def identities(checks, name, run, machine):
    """The hold's, each fate row's and the producer's identities, and the machines', at every
    saved time (§9.7)."""
    x = run["readouts"]
    steps = run["steps"]
    H0 = x[f"H_{RID}"][0]
    fates = [FATE_ROWS] + ([LABEL_ROWS] if f"n_{LABEL_ROWS['durable']}" in x else [])
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


def cohorts(checks, runs, machine):
    """§9.8's two routes for the releases in R1's window at p = 0.75: route 1, the label rows
    minus the labelled blank's; route 2, cohort.py on the unlabelled run's counters. Each fate's
    class total, minus the labelled blank's, is the unlabelled row minus its blank's, within the
    label rows' departure (at most about 1e-8, §9.8)."""
    t1, t2 = worlds.R1_WINDOW
    plain, plain_blank = runs[f"R1 p=0.75 {machine}"], runs[f"R1 blank {machine}"]
    labelled, blank = runs[f"R1L p=0.75 {machine}"], runs[f"R1L blank {machine}"]
    x, xl, xb = plain["readouts"], labelled["readouts"], blank["readouts"]
    xpb = plain_blank["readouts"]
    worst = max(
        _relative(
            xl[f"n_{RID}_{f}"][i] - xb[f"n_{RID}_{f}"][i], x[f"n_{row}"][i] - xpb[f"n_{row}"][i]
        )
        for f, row in FATE_ROWS.items()
        for i in range(1, len(plain["t"]))
    )
    checks.add(
        f"R1L p=0.75 {machine}: each fate's class total, the unlabelled row",
        worst <= SURVIVORS,
        largest_relative=worst,
    )
    for f, row in FATE_ROWS.items():
        for ts in (t2, 2 * t2):
            i = plain["t"].index(ts)
            route1 = (xl[f"n_{LABEL_ROWS[f]}"][i] - xb[f"n_{LABEL_ROWS[f]}"][i]) / COPY_FMOL
            t, n, Q, D = cohort.read(plain["path"], row)  # Its own pool's counters.
            _, route2, _ = cohort.survivors(t, n, Q, D, t1, t2, ts)
            error = cohort.grid_error(t, n, Q, D, t1, t2, ts)
            route2, error = route2 / COPY_FMOL, (math.inf if error is None else error / COPY_FMOL)
            exact = window_cohort(0.75, f, t1, t2, ts)
            checks.add(
                f"R1L p=0.75 {machine}: route 1's {f} cohort at {ts:g} s, the closed form",
                _relative(route1, exact) <= SURVIVORS,
                copies=route1,
                closed_form=exact,
            )
            checks.add(
                f"R1 p=0.75 {machine}: the two routes' {f} cohort at {ts:g} s",
                abs(route1 - route2) <= error + SURVIVORS * abs(route1),
                route1=route1,
                route2=route2,
                grid_error=error,
            )


def r2_cohorts(checks, name, run):
    """R2's release-window cohort by route 2 alone (§9.12, reading 8): cohort.py on each fate's
    counters for R1's window, sampled at its end and an hour later, reported with its grid error,
    which must be estimable at R2's outputs."""
    t1, t2 = worlds.R1_WINDOW
    for f, row in FATE_ROWS.items():
        for ts in (t2, 2 * t2):
            t, n, Q, D = cohort.read(run["path"], row)  # Its own pool's counters.
            completed, surviving, _ = cohort.survivors(t, n, Q, D, t1, t2, ts)
            error = cohort.grid_error(t, n, Q, D, t1, t2, ts)
            checks.add(
                f"{name}: route 2's {f} cohort at {ts:g} s",
                error is not None and 0.0 <= surviving <= completed,
                released_copies=completed / COPY_FMOL,
                surviving_copies=surviving / COPY_FMOL,
                grid_error_copies=None if error is None else error / COPY_FMOL,
            )


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


def switches(checks, name, run):
    """R1S (worlds.r1s): psi switched at completion and p changed mid-run, compiled. While psi = 2
    every arrival joins hold class 2, and after the switch none does, so class 2's hold and
    releases are int_Q_tx up to the switch; class 1's are its 80 copies and the arrivals after
    it; and each fate's share of every interval's releases is that interval's p, 0.75 and then
    0.25. Each at rounding."""
    x, steps = run["readouts"], run["steps"]
    switch, change, _ = worlds.R1S_TIMES
    t, A = run["t"], x["int_Q_tx"]
    at = t.index(switch)
    worst = dict(class_2=0.0, class_1=0.0, share=0.0)
    H0 = x[f"H_{RID}_1"][0]
    for i, now in enumerate(t):
        kept = {
            k: x[f"H_{RID}_{k}"][i] + sum(x[f"int_Q_{RID}_{f}_{k}"][i] for f in FATE_ROWS)
            for k in (1, 2)
        }
        joined = A[min(i, at)]
        later = A[i] - A[min(i, at)]
        worst["class_2"] = max(worst["class_2"], abs(kept[2] - joined) / _bound(steps, A[i]))
        worst["class_1"] = max(
            worst["class_1"], abs(kept[1] - H0 - later) / _bound(steps, H0, A[i], kept[1])
        )
        if i == 0:
            continue
        out = {
            f: sum(x[f"int_Q_{RID}_{f}_{k}"][i] - x[f"int_Q_{RID}_{f}_{k}"][i - 1] for k in (1, 2))
            for f in FATE_ROWS
        }
        p = 0.75 if now <= change else 0.25
        share = out["durable"] / (out["durable"] + out["short_lived"])
        worst["share"] = max(worst["share"], abs(share - p))
    checks.add(
        f"{name}: class 2 holds the arrivals before the switch, and only those",
        worst["class_2"] <= 1.0,
        largest_over_bound=worst["class_2"],
    )
    checks.add(
        f"{name}: class 1 holds its 80 copies and the arrivals after the switch",
        worst["class_1"] <= 1.0,
        largest_over_bound=worst["class_1"],
    )
    checks.add(
        f"{name}: each interval's releases split by its p",
        worst["share"] <= 1e-12,
        largest=worst["share"],
    )


def check_switch(directory):
    """R1S at each machine option: its identities, energy and switches."""
    directory = Path(directory)
    checks = Checks()
    for machine in ("returned", "held"):
        name = f"R1S {machine}"
        run = _load(directory, name)
        identities(checks, name, run, machine)
        energy(checks, name, run)
        switches(checks, name, run)
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
        for name in (f"R1 blank {machine}", f"R1L p=0.75 {machine}", f"R1L blank {machine}"):
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
