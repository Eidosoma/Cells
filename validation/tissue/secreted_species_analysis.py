"""The D150 version 1 qualification's analysis: terms, tolerances, controls and predictions.

NumPy only, from the arms validation/tissue/secreted_species_qualification.py saved (OUT/ARM.json);
writes OUT/analysis.json. Every reference is independent of engine code: each arm's own declared
finite-volume system solved exactly (secreted_species_radial.solution), and the continuum closed
forms (secreted_species_closed_forms).

* **Q1, the exact discrete solution** (time integration), at each arm's records: an IMEX arm
  (ARS(2,2,2), 2.5 um, 1 ms) and an RK4 arm (2.5 um, 0.1 ms). Two step-term rules:
  * the dt study, S5's form, per shell and record: the step term |q(dt) - q(dt/2)| on the same
    grid; tolerance 3 x the step term, or the floor 64 eps x the scale (the largest concentration
    over the arm's records) where that is larger;
  * the splitting term (§12.1, the lead's milestone-3 instruction), per record in the max norm over
    shells, where the first shell carries the error: tolerance 3 x (|dt^2 k (g - k c_ss)| / 4 under
    ARS or / 12 under RK4 + the floor), with g the source face's kappa c0 / V0 and c_ss the declared
    system's steady state. The term is the leading order of the composite step's steady bias at
    the first shell; its sign is negative (the split scheme's first shell runs low).
  Reported beside them: the composite step's exact fixed point (the steady bias in full), and the
  step map iterated in NumPy (design §4.2: ARS's explicit stages or RK4's polynomial for the
  transport, the clearance's exact half-steps around it), which predicts the engine's error at every
  shell and record.
* **Q2, the continuum closed forms** (space and time), per element and record: the 24 coarse 5 um
  shells' averages, the amount M, the source's cumulative supply, the outer bath's and the
  clearance, for the judged IMEX arm; the spatial step |q(2.5 um) - q(1.25 um)| at 0.5 ms; the time
  step |q(1 ms) - q(0.5 ms)| at 2.5 um; the reference term 64 eps x the scale (the closed form is
  exact); tolerance 3 x (spatial + time + reference).
* **Controls** (development only). Q1's tolerances against references with k or D in error by a
  relative delta: the smallest delta each rule catches, and where; Q2's against the planar-face arm
  (the probes' faces).
* **Q3, the orders** (S5's Q5 form: reported, the stop rules judged): spatial at 5, 2.5 and
  1.25 um (0.5 ms), temporal at 1, 0.5 and 0.25 ms (2.5 um). The stop rule is on successive
  differences per quantity and record, in the max norm over the quantity's elements:
  max |q(h) - q(h/2)| > max |q(h/2) - q(h/4)| wherever both lie above 64 eps x the quantity's scale
  (the largest |value| over every element, record and arm). The per-element rule is reported beside
  it, and so are the errors' orders against R-continuum; an error can change sign between grids
  (the clearance's at 0.25 s does from 5 to 2.5 um).
"""

import json
import math
from pathlib import Path

import numpy as np

from validation.tissue import secreted_species_qualification as q
from validation.tissue import secreted_species_radial as radial

TIME_ARMS = ("dr2.5_dt1", "dr2.5_dt0.5", "dr2.5_dt0.25")
SPACE_ARMS = ("dr5_dt0.5", "dr2.5_dt0.5", "dr1.25_dt0.5")
Q1_ARMS = (
    ("Q1_imex", "dr2.5_dt1", "dr2.5_dt0.5"),
    ("Q1_rk4", "rk4_dr2.5_dt0.1", "rk4_dr2.5_dt0.05"),
)
DELTAS = tuple(m * 10.0**e for e in range(-14, 0) for m in (1, 2, 5))
SCALARS = ("amount_fmol", "source_supplied_fmol", "outer_supplied_fmol", "cleared_fmol")
QUANTITIES = ("coarse", *SCALARS)


def load(out):
    out = Path(out)
    return {
        p.stem: json.loads(p.read_text()) for p in sorted(out.glob("*.json")) if p.stem in q.ARMS
    }


def usable(arms, names):
    return all(n in arms and "refused" not in arms[n] for n in names)


def engine(arm):
    """The arm's quantities at its records (t > 0): concentrations [t, shell], coarse averages
    [t, 24] and the four scalars [t]."""
    g = q.geometry(arm["width_m"])
    amounts = np.asarray(arm["shell_amounts_fmol"])[1:]
    ratio = g.shells // q.COARSE.shells
    coarse = amounts.reshape(len(amounts), q.COARSE.shells, ratio).sum(axis=2)
    out = dict(
        times=np.asarray(arm["times_s"])[1:],
        concentration=amounts / g.volumes_pL,
        coarse=coarse / q.COARSE.volumes_pL,
        amount_fmol=amounts.sum(axis=1),
    )
    for key in ("source_supplied_fmol", "outer_supplied_fmol", "cleared_fmol"):
        out[key] = np.asarray(arm[key])[1:]
    return out


def system(arm, *, diffusivity=q.D, clearance=q.K):
    g = q.geometry(arm["width_m"])
    m, b = radial.operator(
        g,
        diffusivity=diffusivity,
        clearance=clearance,
        c0_mM=q.C0,
        outer_mM=q.TRACE,
        faces=arm["faces"],
    )
    return g, m, b


def discrete(arm, *, diffusivity=q.D, clearance=q.K):
    """The exact solution of the arm's declared system at its records [t, shell] (mM)."""
    g, m, b = system(arm, diffusivity=diffusivity, clearance=clearance)
    start = q.problem().shell_averages(g.edges, 0.0)
    return radial.solution(m, b, start, np.asarray(arm["times_s"])[1:])


def continuum(times):
    p = q.problem()
    return dict(
        coarse=np.stack([p.shell_averages(q.COARSE.edges, t) for t in times]),
        amount_fmol=np.array([p.amount_fmol(t) for t in times]),
        source_supplied_fmol=np.array([p.source_supplied_fmol(t) for t in times]),
        outer_supplied_fmol=np.array([p.outer_supplied_fmol(t) for t in times]),
        cleared_fmol=np.array([p.cleared_fmol(t) for t in times]),
    )


def step_map(arm):
    """The composite step as a linear map c -> d (A (d c) + B b): the clearance's exact half-steps
    d = exp(-k h / 2) around the transport's ARS(2,2,2) explicit stages (A = I - hT + h^2 T^2 / 2,
    B = h (I - h T / 2)) or RK4's polynomial, with T the transport without clearance."""
    g, m, b = system(arm)
    h, n = arm["dt_s"], g.shells
    t = m - q.K * np.eye(n)
    eye = np.eye(n)
    if arm["solver"] == "rk4":
        z = -h * t
        z2 = z @ z
        z3 = z2 @ z
        a = eye + z + z2 / 2 + z3 / 6 + z3 @ z / 24
        bb = h * (eye + z / 2 + z2 / 6 + z3 / 24)
    else:
        a = eye - h * t + 0.5 * h * h * t @ t
        bb = h * (eye - 0.5 * h * t)
    return g, m, b, a, bb, math.exp(-q.K * h / 2)


def scheme_map(arm):
    """The step map iterated in NumPy from the start, at the records [t, shell] (mM)."""
    g, _, b, a, bb, d = step_map(arm)
    c = q.problem().shell_averages(g.edges, 0.0)
    h = arm["dt_s"]
    wanted = {int(round(time / h)): k for k, time in enumerate(arm["times_s"][1:])}
    out = np.zeros((len(wanted), g.shells))
    for step in range(1, max(wanted) + 1):
        c = d * (a @ (d * c) + bb @ b)
        if step in wanted:
            out[wanted[step]] = c
    return out


def splitting_term(arm):
    """(the leading-order formula -dt^2 k (g - k c_ss) / 4 or / 12 at the first shell, the step
    map's exact fixed point minus c_ss at the first shell), both mM and signed."""
    g, m, b, a, bb, d = step_map(arm)
    c_ss = np.linalg.solve(m, b)
    fixed = np.linalg.solve(np.eye(g.shells) - d * d * a, d * bb @ b)
    factor = 12.0 if arm["solver"] == "rk4" else 4.0
    formula = -(arm["dt_s"] ** 2) * q.K * (b[0] - q.K * c_ss[0]) / factor
    return float(formula), float(fixed[0] - c_ss[0])


def floor(scale):
    return q.FLOOR_K * q.EPS * scale


def norm(x):
    """[record] the largest |element| at each record."""
    x = np.abs(np.asarray(x, dtype=float))
    return np.max(x.reshape(len(x), -1), axis=1)


def smallest_caught(arm, measure, tolerance):
    """{k, D: [delta, index]}: the smallest relative error in the reference's clearance or
    diffusivity whose |engine - wrong reference| (measure) exceeds the tolerance somewhere."""
    found = {}
    for name, value in (("clearance", q.K), ("diffusivity", q.D)):
        found[name] = None
        for delta in DELTAS:
            fraction = measure(discrete(arm, **{name: value * (1.0 + delta)})) / tolerance
            if np.max(fraction) > 1.0:
                where = np.unravel_index(int(np.argmax(fraction)), fraction.shape)
                found[name] = [delta, [int(i) for i in where]]
                break
    return found


def q1_errors(arm):
    """[record, shell] |engine - R-discrete| (mM): Q1's judged quantity."""
    return np.abs(engine(arm)["concentration"] - discrete(arm))


def q1(arms, judged, half):
    arm = arms[judged]
    c = engine(arm)["concentration"]
    ref = discrete(arm)
    error = np.abs(c - ref)
    step = np.abs(c - engine(arms[half])["concentration"])
    scale = float(np.max(np.abs(c)))
    tolerance = np.maximum(3.0 * step, floor(scale))
    formula, fixed = splitting_term(arm)
    split_tolerance = np.full(len(c), 3.0 * (abs(formula) + floor(scale)))
    predicted = scheme_map(arm)
    return dict(
        judged=judged,
        step_arm=half,
        records_s=arm["times_s"][1:],
        scale_mM=scale,
        floor_mM=floor(scale),
        dt_study=dict(
            tolerance_mM=tolerance.tolist(),
            error_mM=error.tolist(),
            step_term_mM=step.tolist(),
            elements_at_floor=int(np.sum(3.0 * step < floor(scale))),
            fraction_by_record=np.max(error / tolerance, axis=1).tolist(),
            fraction_max=float(np.max(error / tolerance)),
            worst_shell=int(np.argmax(np.max(error / tolerance, axis=0))),
            control_smallest_relative_error_caught=smallest_caught(
                arm, lambda wrong: np.abs(c - wrong), tolerance
            ),
        ),
        splitting_term=dict(
            formula_first_shell_mM=formula,
            tolerance_mM=split_tolerance.tolist(),
            error_max_norm_mM=norm(c - ref).tolist(),
            fraction_by_record=(norm(c - ref) / split_tolerance).tolist(),
            fraction_max=float(np.max(norm(c - ref) / split_tolerance)),
            control_smallest_relative_error_caught=smallest_caught(
                arm, lambda wrong: norm(c - wrong), split_tolerance
            ),
        ),
        predictions=dict(
            formula_first_shell_of_c0=formula / q.C0,
            fixed_point_first_shell_of_c0=fixed / q.C0,
            first_shell_error_of_c0_by_record=((c[:, 0] - ref[:, 0]) / q.C0).tolist(),
            first_shell_step_term_of_c0_by_record=(step[:, 0] / q.C0).tolist(),
            error_max_norm_of_c0_by_record=(norm(c - ref) / q.C0).tolist(),
            scheme_map_error_max_norm_of_c0_by_record=(norm(predicted - ref) / q.C0).tolist(),
            engine_minus_scheme_map_max_of_c0=float(np.max(np.abs(c - predicted))) / q.C0,
        ),
    )


def q2_errors(arm):
    """{quantity: [record, element]} |engine - R-continuum|: Q2's judged quantities."""
    e = engine(arm)
    ref = continuum(e["times"])
    return {key: np.abs(e[key] - ref[key]) for key in QUANTITIES}


def q2(arms):
    judged, half, fine = (engine(arms[n]) for n in ("dr2.5_dt1", "dr2.5_dt0.5", "dr1.25_dt0.5"))
    ref = continuum(judged["times"])
    planar = engine(arms["planar_dr2.5_dt1"]) if usable(arms, ["planar_dr2.5_dt1"]) else None
    out = dict(judged="dr2.5_dt1", records_s=judged["times"].tolist(), quantities={})
    for key in QUANTITIES:
        scale = float(np.max(np.abs(judged[key])))
        error = np.abs(judged[key] - ref[key])
        space = np.abs(half[key] - fine[key])
        step = np.abs(judged[key] - half[key])
        tolerance = 3.0 * (space + step + floor(scale))
        entry = dict(
            scale=scale,
            reference_term=floor(scale),
            tolerance=tolerance.tolist(),
            error=error.tolist(),
            spatial_step_term=space.tolist(),
            time_step_term=step.tolist(),
            largest_time_over_largest_spatial=float(np.max(step) / np.max(space)),
            fraction_by_record=norm(error / tolerance).tolist(),
            fraction_max=float(np.max(error / tolerance)),
        )
        if planar is not None:
            entry["planar_control_fraction_max"] = float(
                np.max(np.abs(planar[key] - ref[key]) / tolerance)
            )
        out["quantities"][key] = entry
    return out


def cauchy(values):
    """S5's Q5 stop rule for three refinements' values [3, record, element...], per record in the
    max norm over the quantity's elements (a scalar is its own). The per-element rule is reported
    beside it: at an element where a field's error changes sign, the leading term of the difference
    vanishes and the next need not fall, so a per-element monotonicity test is ill-posed there."""
    values = np.asarray(values, dtype=float)
    scale = float(np.max(np.abs(values)))
    first, second = norm(values[0] - values[1]), norm(values[1] - values[2])
    measurable = (first > floor(scale)) & (second > floor(scale))
    order = np.log2(first[measurable] / second[measurable])
    e1, e2 = np.abs(values[0] - values[1]), np.abs(values[1] - values[2])
    each = (e1 > floor(scale)) & (e2 > floor(scale))
    rising = each & (e2 >= e1)
    return dict(
        scale=scale,
        records_measurable=int(np.sum(measurable)),
        records_below_floor=int(np.sum(~measurable)),
        every_difference_decreases=bool(np.all(second[measurable] < first[measurable])),
        largest_differences=[first.tolist(), second.tolist()],
        orders_by_record=np.log2(first / second).tolist(),
        order_min=float(np.min(order)) if order.size else None,
        order_max=float(np.max(order)) if order.size else None,
        per_element_reported=dict(
            measurable=int(np.sum(each)),
            not_decreasing=int(np.sum(rising)),
            where_record_element=[[int(i) for i in w] for w in np.argwhere(rising)],
            their_first_difference_over_the_records_largest=[
                float(e1[tuple(w)] / first[w[0]]) for w in np.argwhere(rising)
            ],
        ),
    )


def orders(arms):
    space, time_ = {}, {}
    if usable(arms, SPACE_ARMS):
        x = [engine(arms[a]) for a in SPACE_ARMS]
        ref = continuum(x[0]["times"])
        for key in QUANTITIES:
            errors = [norm(v[key] - ref[key]) for v in x]
            space[key] = dict(
                cauchy([v[key] for v in x]),
                error_max_norm_against_continuum=[e.tolist() for e in errors],
                error_orders=[np.log2(errors[i] / errors[i + 1]).tolist() for i in range(2)],
            )
    if usable(arms, TIME_ARMS):
        x = [engine(arms[a]) for a in TIME_ARMS]
        for key in ("concentration", *SCALARS):
            time_[key] = cauchy([v[key] for v in x])
    return dict(space=space, time=time_)


def analyse(out):
    arms = load(out)
    refused = {k: v["refused"] for k, v in arms.items() if "refused" in v}
    report = dict(
        analysis_source=q.source_identity(),
        arms_source=json.loads((Path(out) / "source.json").read_text()),
        arms={
            k: dict(
                seconds=v.get("seconds"),
                max_dt_K_ii=v.get("max_dt_K_ii"),
                diagnostics=v.get("diagnostics"),
                refused=v.get("refused"),
            )
            for k, v in arms.items()
        },
        refused=refused,
        mass_balance_fmol={},
    )
    for name, arm in arms.items():  # The engine's own amounts against its own bookings.
        if name in refused:
            continue
        e = engine(arm)
        change = e["amount_fmol"] - float(np.sum(arm["shell_amounts_fmol"][0]))
        booked = e["source_supplied_fmol"] + e["outer_supplied_fmol"] - e["cleared_fmol"]
        report["mass_balance_fmol"][name] = float(np.max(np.abs(change - booked)))
    for key, judged, half in Q1_ARMS:
        if usable(arms, [judged, half]):
            report[key] = q1(arms, judged, half)
    if usable(arms, ["dr2.5_dt1", "dr2.5_dt0.5", "dr1.25_dt0.5"]):
        report["Q2"] = q2(arms)
    report["Q3"] = orders(arms)
    path = Path(out) / "analysis.json"
    path.write_text(json.dumps(report, indent=1, default=float) + "\n")
    print(path)
    return report
