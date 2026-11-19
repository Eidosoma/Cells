"""The harness's reference adequacy (REGISTRATION_20261118.md §5.3), judged from kept rows.

The comparison functions are pure (arrays in, verdicts out), so the planted controls test them
on synthetic rows; load_arm derives each class from an arm's kept rows with the engine's own
readouts. Stage 0 makes no qualification claim (amendment 1, Q1).

Classes, at every observation row, cumulative from t = 0:
* voltage: every active patch's membrane voltage (V), |dVm| against a budget in V;
* concentration: every species in every active cell (mM), |dc| / c_ref;
* gate: every active channel gate and junction gate, |dg|;
* histories: every state field outside the dynamical four, elementwise
  |d| <= budget x max(|ref|, floor), with the floor by the field's unit (_pJ energy, _C charge,
  otherwise amounts and cycles in fmol).

Usage: python -m validation.long_duration.harness_judge OUTPUT.json R1_DIR R2_DIR [R3_DIR]
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

CLASSES = ("voltage", "concentration", "gate")
# §5.3: each crossing is "located by linear interpolation between 1 ms rows" before its 0.5 ms
# budget applies; one located between sparser rows (outside the 1 ms window) takes no timing pass.
CROSSING_ROW_SPACING_S = 1e-3


def class_error(test, ref, kind):
    """Per row: the largest error of one class over its entries (relative for concentration)."""
    test, ref = np.asarray(test, dtype=float), np.asarray(ref, dtype=float)
    diff = np.abs(test - ref)
    if kind == "concentration":
        diff = diff / np.abs(ref)
    return diff.reshape(len(diff), -1).max(axis=1, initial=0.0)


def judge_class(test, ref, kind, budget, times=None, after=None):
    """The class's verdict: its largest per-row error over every row (or rows after `after`),
    its ratio to the budget and the row where it is largest."""
    errors = class_error(test, ref, kind)
    if after is not None:
        mask = np.asarray(times) > after
        errors = np.where(mask, errors, 0.0)
    worst = int(np.argmax(errors)) if len(errors) else 0
    largest = float(errors[worst]) if len(errors) else 0.0
    out = dict(largest=largest, budget=budget, ratio=largest / budget, passed=largest <= budget)
    if times is not None and len(errors):
        out["row_time_s"] = float(np.asarray(times)[worst])
    return out


def floor_of(name, floors):
    if name.endswith("_pJ"):
        return floors["energy_pJ"]
    if name.endswith("_C"):
        return floors["charge_C"]
    return floors["amount_fmol"]


def judge_histories(test, ref, budget, floors, times=None):
    """Per history field: the largest |d| / (budget max(|ref|, floor)) over rows and entries,
    with where it is largest (row, entry, the two values and the entry's largest |ref| over the
    rows), so a failure near an accumulator's zero can be told from one at its magnitude."""
    out, passed = {}, True
    for name in ref:
        a, b = np.asarray(test[name], dtype=float), np.asarray(ref[name], dtype=float)
        scale = budget * np.maximum(np.abs(b), floor_of(name, floors))
        ratios = np.abs(a - b) / scale
        ratio = float(np.max(ratios, initial=0.0))
        entry = dict(ratio=ratio, passed=ratio <= 1.0)
        if ratios.size and ratio > 0:
            where = np.unravel_index(int(np.argmax(ratios)), ratios.shape)
            column = (slice(None), *where[1:])
            entry.update(
                row=int(where[0]),
                entry=[int(i) for i in where[1:]],
                test=float(a[where]),
                ref=float(b[where]),
                entry_largest_ref=float(np.max(np.abs(b[column]), initial=0.0)),
            )
            if times is not None:
                entry["row_time_s"] = float(np.asarray(times)[where[0]])
        out[name] = entry
        passed &= ratio <= 1.0
    return dict(fields=out, passed=bool(passed))


def crossings(times, values, level, after):
    """Times (s) at which values cross `level` after `after`, by linear interpolation between
    the bracketing rows, with each crossing's direction and the spacing of the two rows that
    locate it. A run of rows exactly at the level is a crossing at its first row if the sign
    differs on either side of it, located by that row and the one before it, and a tangency (no
    crossing) if it does not."""
    t, v = np.asarray(times, dtype=float), np.asarray(values, dtype=float) - level
    out = []
    i = 0
    while i < len(t) - 1:
        j = i + 1
        if v[j] == 0.0 and v[i] != 0.0:
            k = j
            while k < len(v) and v[k] == 0.0:
                k += 1
            if k < len(v) and v[i] * v[k] < 0 and t[j] > after:
                out.append(
                    dict(
                        time_s=float(t[j]),
                        direction="up" if v[k] > v[i] else "down",
                        spacing_s=float(t[j] - t[i]),
                    )
                )
            i = max(k - 1, j)
            continue
        if v[i] * v[j] < 0:
            at = t[i] + (0.0 - v[i]) * (t[j] - t[i]) / (v[j] - v[i])
            if at > after:
                out.append(
                    dict(
                        time_s=float(at),
                        direction="up" if v[j] > v[i] else "down",
                        spacing_s=float(t[j] - t[i]),
                    )
                )
        i = j
    return out


def located(crossing, spacing):
    """Whether a crossing was located between rows at most `spacing` apart, to the rounding of
    the rows' time labels: two ulps of its time (a 1 ms bracket of float labels near 1800 s reads
    up to 2e-13 s over 1 ms)."""
    return crossing["spacing_s"] <= spacing + 2 * float(np.spacing(abs(crossing["time_s"])))


def timing_verdict(test, ref, budget, spacing, count=2):
    """The first `count` crossings of each run, paired in order: each |dt| within the budget,
    with both crossings located between rows at most `spacing` apart (§5.3's 1 ms rows: a pair
    located between sparser rows fails, since its interpolation cannot resolve the budget); a
    crossing present in one run only fails."""
    a, b = test[:count], ref[:count]
    pairs = [
        dict(
            test_s=x["time_s"],
            ref_s=y["time_s"],
            difference_s=x["time_s"] - y["time_s"],
            test_spacing_s=x["spacing_s"],
            ref_spacing_s=y["spacing_s"],
            passed=abs(x["time_s"] - y["time_s"]) <= budget
            and x["direction"] == y["direction"]
            and located(x, spacing)
            and located(y, spacing),
        )
        for x, y in zip(a, b, strict=False)
    ]
    same_count = len(a) == len(b)
    return dict(
        pairs=pairs,
        crossings_test=len(a),
        crossings_ref=len(b),
        passed=bool(same_count and all(p["passed"] for p in pairs)),
    )


def recovery_time(times, values, reference, delta, after, through):
    """The first row after `after` from which |values - reference| <= delta at every row through
    `through`, or None."""
    t, v = np.asarray(times, dtype=float), np.asarray(values, dtype=float)
    inside = np.abs(v - reference) <= delta
    window = (t > after) & (t <= through)
    candidates = np.flatnonzero(window)
    if not len(candidates):
        return None
    ok = inside[candidates]
    # The last row of the window that is outside: recovery starts at the next row.
    outside = np.flatnonzero(~ok)
    if not len(outside):
        return float(t[candidates[0]])
    if outside[-1] == len(candidates) - 1:
        return None
    return float(t[candidates[outside[-1] + 1]])


def peak_response(times, values, reference, after):
    t, v = np.asarray(times, dtype=float), np.asarray(values, dtype=float)
    mask = t > after
    return float(np.max(np.abs(v[mask] - reference), initial=0.0))


def observed_order(e_coarse, e_fine):
    """p = log2(e_coarse / e_fine), or None where either is zero or not finite."""
    if not (e_coarse > 0 and e_fine > 0 and math.isfinite(e_coarse) and math.isfinite(e_fine)):
        return None
    return math.log2(e_coarse / e_fine)


# ------------------------------------------------------------------ the engine side


def load_arm(directory):
    """(record, times, classes, histories, cell_0 voltage) of one arm's kept rows."""
    from cells.definitions.specs import parse_spec
    from cells.models import surface_pump_projective as projective
    from cells.registry.models import get_model
    from validation.long_duration import worlds

    directory = Path(directory)
    record = json.loads((directory / "run.json").read_text())
    with np.load(directory / "rows.npz") as archive:  # Each array once: an indexed npz
        data = {k: archive[k] for k in archive.files}  # decompresses per access.
    times = data["times"]
    spec = parse_spec(worlds.h2(record["dt_s"], development_end=record["development_end_s"]))
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    fields = model.STATE_TYPE._fields
    cells = np.asarray(p.active, dtype=bool)
    gate_mask = np.asarray(p.channel_gate_active, dtype=bool)
    junctions = np.asarray(p.junction_active, dtype=bool)
    voltage, concentration, gate = [], [], []
    for i in range(len(times)):
        row = model.STATE_TYPE(*(data[f][i] for f in fields))
        voltage.append(projective.membrane_voltage(row, p))
        ci, _ = model.physical_amounts(row, p)
        concentration.append(ci[:, cells] / p.volume[cells])
        gate.append(np.concatenate((row.channel_gate[gate_mask], row.junction_gate[junctions])))
    classes = dict(
        voltage=np.asarray(voltage), concentration=np.asarray(concentration), gate=np.asarray(gate)
    )
    histories = {k: data[k] for k in record["history_fields"]}
    return record, times, classes, histories, np.asarray(voltage)[:, 0]


def compare(test, ref, reg):
    """§5.3's verdicts of one arm against its reference (both from load_arm)."""
    budgets = reg["budgets"]
    t_rec, t, c, h, v0 = test
    r_rec, rt, rc, rh, rv0 = ref
    if not np.array_equal(t, rt):
        raise ValueError("The arms' observation rows differ")
    if t_rec["run_of_record"] != r_rec["run_of_record"] or t_rec["cue_s"] != r_rec["cue_s"]:
        raise ValueError("A development arm is compared only with a development arm")
    cue_start, cue_end = t_rec["cue_s"]
    if t_rec["run_of_record"] and [cue_start, cue_end] != list(reg["cue_s"]):
        raise ValueError("The run of record's cue differs from the registered cue")
    per_budget = dict(voltage=budgets["voltage_V"], concentration=budgets["relative_concentration"],
                      gate=budgets["gate"])  # fmt: skip
    trajectory = {k: judge_class(c[k], rc[k], k, per_budget[k], t) for k in CLASSES}
    response = {k: judge_class(c[k], rc[k], k, per_budget[k], t, after=cue_start) for k in CLASSES}
    pre = float(v0[np.flatnonzero(t == cue_start)[0]])
    pre_ref = float(rv0[np.flatnonzero(rt == cue_start)[0]])
    peak, peak_ref = (
        peak_response(t, v0, pre, cue_start),
        peak_response(rt, rv0, pre_ref, cue_start),
    )
    peak_error = abs(peak - peak_ref) / peak_ref if peak_ref else math.inf
    response["peak"] = dict(
        test_V=peak,
        ref_V=peak_ref,
        relative=peak_error,
        budget=budgets["peak_response_relative"],
        passed=peak_error <= budgets["peak_response_relative"],
    )
    level = budgets["crossing_level_V"]
    timing = timing_verdict(
        crossings(t, v0, level, cue_start), crossings(rt, rv0, level, cue_start),
        budgets["crossing_time_s"], CROSSING_ROW_SPACING_S,
    )  # fmt: skip
    through = budgets["recovery_through_s"] if t_rec["run_of_record"] else float(t[-1])
    timing["recovery"] = {
        f"{delta * 1e3:g}_mV": dict(
            test_s=recovery_time(t, v0, pre, delta, cue_end, through),
            ref_s=recovery_time(rt, rv0, pre_ref, delta, cue_end, through),
        )
        for delta in budgets["recovery_deltas_V"]
    }
    histories = judge_histories(h, rh, budgets["history_relative"], budgets["history_floors"], t)
    caps = dict(
        voltage=trajectory["voltage"]["largest"] / 20e-6,
        relative_concentration=trajectory["concentration"]["largest"] / 2e-4,
    )
    conservation = dict(test=t_rec["status"], ref=r_rec["status"],
                        passed=t_rec["status"] == r_rec["status"] == "complete")  # fmt: skip
    adequate = (
        all(trajectory[k]["passed"] for k in CLASSES)
        and all(response[k]["passed"] for k in CLASSES)
        and response["peak"]["passed"]
        and timing["passed"]
        and histories["passed"]
        and conservation["passed"]
    )
    return dict(
        test=t_rec["arm"],
        ref=r_rec["arm"],
        trajectory=trajectory,
        intervention_response=response,
        threshold_timing=timing,
        histories=histories,
        conservation=conservation,
        caps_benchmark_ratios=caps,
        adequate=bool(adequate),
    )


def orders(arms, window):
    """§5.3's observed order per class, at the row of largest |z1 - z2| and at the end."""
    (_, t, c1, _, _), (_, _, c2, _, _), (_, _, c3, _, _) = arms
    out = {}
    for k in CLASSES:
        e12, e23 = class_error(c1[k], c2[k], k), class_error(c2[k], c3[k], k)
        worst = int(np.argmax(e12))
        at = dict(worst_row=worst, end_row=len(t) - 1)
        out[k] = {}
        for label, row in at.items():
            p = observed_order(float(e12[row]), float(e23[row]))
            inside = p is not None and window[0] <= p <= window[1]
            estimates = error_estimates(float(e23[row]), p) if inside else (None, None)
            out[k][label] = dict(
                time_s=float(t[row]),
                p=p,
                inside_window=inside,
                r2_error_estimate=estimates[0],
                r3_error_estimate=estimates[1],
            )
    return out


def error_estimates(e23, p):
    """(R2's, R3's) error from |z2 - z3| and the order p, with z_h = z* + C h^p and the steps
    halving: R3's is |z2 - z3| / (2^p - 1) and R2's |z2 - z3| / (1 - 2^-p), 2^p times larger
    (amendment 3: the registration's text had named R3's estimate as R2's)."""
    return e23 / (1.0 - 2.0**-p), e23 / (2.0**p - 1.0)


ARM_NAMES = ("R1", "R2", "R3")


def check_arms(directories, records, reg):
    """Amendment 3: refuse to score unless arm i is R1, R2, R3 in turn with its registered step,
    the directories are distinct, the steps strictly decrease, and every arm shares one snapshot
    revision and one registration (two arms, R1 and R2, when R3 did not run)."""
    if len(records) not in (2, 3) or len(directories) != len(records):
        raise ValueError("The judge takes R1 and R2, or R1, R2 and R3")
    resolved = [str(Path(d).resolve()) for d in directories]
    if len(set(resolved)) != len(resolved):
        raise ValueError("The judge's arms must come from distinct directories")
    for i, record in enumerate(records):
        name = ARM_NAMES[i]
        if record.get("arm") != name:
            raise ValueError(f"Arm {i + 1} must be {name}, not {record.get('arm')}")
        if record.get("dt_s") != reg["arms_dt_s"][name]:
            raise ValueError(f"{name}'s step {record.get('dt_s')} is not its registered step")
    steps = [r["dt_s"] for r in records]
    if any(b >= a for a, b in zip(steps[:-1], steps[1:], strict=True)):
        raise ValueError("The arms' steps must strictly decrease")
    for key in ("snapshot_revision", "registration"):
        if len({r.get(key) for r in records}) != 1:
            raise ValueError(f"The arms differ in {key}")


def run(output, directories):
    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.long_duration import worlds

    reg = worlds.registration()["harness"]
    records = [json.loads((Path(d) / "run.json").read_text()) for d in directories]
    check_arms(directories, records, reg)  # Before any scoring (amendment 3).
    arms = [load_arm(d) for d in directories]
    out = dict(
        measurement="harness reference adequacy",
        run_of_record=all(a[0]["run_of_record"] for a in arms),
        registration=worlds.registration()["registration"],
        qualification_claim="none (stage 0; amendment 1, Q1)",
        arms={a[0]["arm"]: str(d) for a, d in zip(arms, directories, strict=True)},
    )
    reference = arms[-1]
    out["R1_against_reference"] = compare(arms[0], reference, reg)
    if len(arms) == 3:
        out["R2_against_R3"] = compare(arms[1], arms[2], reg)
        out["orders"] = orders(arms, reg["order_window"])
    if out["R1_against_reference"]["adequate"]:
        out["stage1_reference"] = arms[0][0]["arm"]
    elif len(arms) == 3 and out["R2_against_R3"]["adequate"]:
        out["stage1_reference"] = arms[1][0]["arm"]
    else:
        out["stage1_reference"] = arms[-1][0]["arm"] + " (its error unestimated)"
    with open(output, "x") as stream:
        json.dump(out, stream, indent=1)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1], sys.argv[2:]))
