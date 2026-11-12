"""Runner for the registered J1 diagnostic arms on R-full (j1_diagnostic_arms.json).

R-full only; numpy/scipy. J1 is a selection datum: nothing here is a prediction of record, and no
parameter is picked from Em (every curve is computed whole). Check C1 is held: no solution B or C
run anywhere. Every point recalibrates P_old on pulse Rm1 (852 kOhm) and the access (A/L or its
scale kappa) on pulse Rm2 (488 kOhm), except the declared end points (A/L = 0) and the uncalibrated
geometric-access check, then runs the registered 0-35 min protocol and reports Em and Rm at J1,
the time course, the descriptors D1-D7 (each arm's by-construction ones flagged) and the lumen.

Groups (python -m validation.division.j1_diagnostic_runner GROUP --output DIR):
  timing  a synthetic egg-scale cell (non-J1 compositions) with N = 1 and N = 10 rings, pulsed
  g1      A1 (f), A2 (zone), A4 (P_Cl), A7a (alpha), A7b (beta), with the null point first
  a3      the ring lumen: N = 1, 10, 20; w and bridge ranges; the geometric-access check
  a6      the new-membrane rules per exposed arm and the self-consistent fits
"""

import argparse
import json
import math
import time
import traceback
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, root

from validation.division import cleft_egg_reference as ref
from validation.division import cleft_rings_reference as rings

HERE = Path(__file__).parent
ARMS = HERE / "j1_diagnostic_arms.json"
PREDICTION = HERE / "j1_prediction_of_record.json"
METHOD = "LSODA"
R_EGG_M = 0.65e-3  # dL74 p5: 1.3 mm diameter
REFERENCE_TERM_V = 1.8475223435669708e-07  # the record's reference term (verdict)


def log_line(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def inputs():
    d = ref.load_declared()
    arms = json.loads(ARMS.read_text())
    record = json.loads(PREDICTION.read_text())
    return d, arms, record


# ---------------------------------------------------------------- one point


def descriptors(times, em, rm, j1):
    """D1-D7 of the registered time_course.descriptors (times s, Em V, Rm ohm per pulse)."""
    t = np.asarray(times)
    em = np.asarray(em)
    rm = np.asarray(rm)

    def at(x, s):
        return float(x[int(np.flatnonzero(np.isclose(t, s))[0])])

    moved = np.flatnonzero(np.abs(em - em[0]) > 0.5e-3)
    before = t < j1
    i_min = int(np.argmin(np.where(before, em, np.inf)))
    rm_min = float(np.min(rm[before & (t >= 420.0)])) if np.any(before & (t >= 420.0)) else math.nan
    return {
        "D1_onset_min": float(t[moved[0]] / 60.0) if len(moved) else None,
        "D2_em_change_7_to_17_min_mV": (at(em, 1020.0) - at(em, 420.0)) * 1e3,
        "D3_em_minimum": {"time_min": float(t[i_min] / 60.0), "value_mV": float(em[i_min] * 1e3)},
        "D4_late_change_mV": (at(em, j1) - float(em[i_min])) * 1e3,
        "D5_rm_fraction_of_fall_by_10_min": (at(rm, 420.0) - at(rm, 600.0))
        / (at(rm, 420.0) - at(rm, 1020.0)),
        "D6_rm_ratio_17_over_7": at(rm, 1020.0) / at(rm, 420.0),
        "D7_late_rm_rise_kOhm": (at(rm, j1) - rm_min) / 1e3,
    }


def lumen_of(at_j1):
    if at_j1.get("lumen_mean_mM") is not None:  # ring model
        return dict(
            mean_mM=at_j1["lumen_mean_mM"],
            mouth_ring_mM=at_j1["ring_mM"][0],
            deepest_ring_mM=at_j1["ring_mM"][-1],
            ring_mM=at_j1["ring_mM"],
            ring_potential_V=at_j1["ring_potential_V"],
        )
    return dict(mean_mM=at_j1.get("lumen_mM"), potential_V=at_j1.get("phi_lumen"))


def evaluate(d, egg, record, *, runner=None, calibrate_access=True, label=""):
    """Calibrate (P_old on Rm1, A/L on Rm2 unless told not to), then the 0-35 min time course."""
    started = time.perf_counter()
    rm = d["rm_definition"]
    targets = ref.scalar_values(d)
    j1 = float(d["time"]["j1_s"])
    p_old = ref.calibrate_old(
        egg, targets["rm1_target_ohm"], tuple(rm["rm1_pulse_pair"]), method=METHOD, runner=runner
    )
    egg = replace(egg, p_old=p_old)
    evaluations = []
    if calibrate_access:
        al, evaluations = ref.calibrate_access(
            egg,
            targets["rm2_target_ohm"],
            tuple(rm["j1_pulse_pair"]),
            method=METHOD,
            guess=record["a_over_l_m"] if egg.a_over_l_m != egg.a_over_l_m else egg.a_over_l_m,
            step=0.02,
            runner=runner,
        )
        egg = replace(egg, a_over_l_m=al)
    run = (runner or ref.simulate)(egg, float(d["time"]["horizon_s"]), method=METHOD, record=(j1,))
    k = rm["j1_em_pulse"]
    ks = sorted(i for i in run.onset_V if i >= 1 and i in run.sample_V and i - 1 in run.sample_V)
    p = egg.pulses
    times = [p.onset(i) for i in ks]
    em = [run.onset_V[i] for i in ks]
    rms = [run.rm(i)[0] for i in ks]
    rm_j1, dv_prev, dv = run.rm(k)
    out = dict(
        label=label,
        em_j1_V=run.onset_V[k],
        rm_j1_ohm=rm_j1,
        chords_ohm=[
            dv_prev / (p.sign(k - 1) * p.amplitude_A),
            dv / (p.sign(k) * p.amplitude_A),
        ],
        p_old_m_s=p_old,
        a_over_l_m=egg.a_over_l_m,
        calibration_evaluations=len(evaluations),
        cytosol_na_j1_mM=run.at[j1]["cytosol_mM"][0],
        lumen_j1=lumen_of(run.at[j1]),
        descriptors=descriptors(times, em, rms, j1),
        time_course=dict(times_s=times, em_V=em, rm_ohm=rms),
        wall_s=time.perf_counter() - started,
    )
    log_line(
        label,
        f"Em {out['em_j1_V'] * 1e3:.3f} mV",
        f"Rm {rm_j1 / 1e3:.2f} kOhm",
        f"{out['wall_s']:.0f} s",
    )
    return out


def default_egg(d, **overrides):
    return ref.build(d, ref.scalar_values(d, overrides))


def writer(path):
    def write(result):
        path.write_text(json.dumps(result, indent=1, default=float) + "\n")

    return write


def by_construction(arms, arm_id, variant=None):
    for a in arms["arms"]:
        if a["id"] == arm_id:
            s = a.get("descriptors_set_by_construction", {})
            return s.get(variant, s) if variant else s
    raise KeyError(arm_id)


def end_point(d, egg, record, field, lo, hi, *, label):
    """The value of `field` at which a sealed lumen (A/L = 0) alone gives pulse Rm2 = 488 kOhm."""
    rm = d["rm_definition"]
    targets = ref.scalar_values(d)
    p_old = ref.calibrate_old(
        egg, targets["rm1_target_ohm"], tuple(rm["rm1_pulse_pair"]), method=METHOD
    )
    sealed = replace(egg, p_old=p_old, a_over_l_m=0.0)

    def miss(x):
        value, _ = ref.rm_at(
            replace(sealed, **{field: x}), tuple(rm["j1_pulse_pair"]), method=METHOD
        )
        return math.log(value / targets["rm2_target_ohm"])

    x = brentq(miss, lo, hi, xtol=1e-9, rtol=1e-10)
    log_line(label, "end", field, x)
    return x


# ---------------------------------------------------------------- groups


def group_g1(args):
    d, arms, record = inputs()
    out = dict(group="g1", arms={})
    write = writer(Path(args.output) / "g1.json")
    base = default_egg(d)
    out["null"] = evaluate(d, base, record, label="null (registered)")
    out["null"]["record_minus_null_V"] = record["prediction_of_record_V"] - out["null"]["em_j1_V"]
    write(out)
    # A1: bath-facing fraction f.
    a1 = dict(by_construction=by_construction(arms, "A1_bath_facing_fraction"), points=[])
    f_end = end_point(d, base, record, "bath_fraction", 0.01, 0.6, label="A1")
    for f in [0.01, 0.02, 0.03, 0.05, 0.07]:
        if f < f_end:
            a1["points"].append(
                dict(f=f, **evaluate(d, replace(base, bath_fraction=f), record, label=f"A1 f={f}"))
            )
            write(out | {"arms": out["arms"] | {"A1": a1}})
    end = evaluate(
        d,
        replace(base, bath_fraction=f_end, a_over_l_m=0.0),
        record,
        calibrate_access=False,
        label="A1 end",
    )
    a1["points"].append(dict(f=f_end, end=True, **end))
    out["arms"]["A1"] = a1
    write(out)
    # A2: furrow zone, as fractions of its end value.
    a2 = dict(by_construction=by_construction(arms, "A2_peri_furrow_old_membrane_zone"), points=[])
    zone = replace(base, zone_reference_area_m2=ref.scalar_values(d)["new_membrane_area_at_j1_m2"])
    z_end = end_point(d, zone, record, "zone_ratio", 0.05, 10.0, label="A2")
    a2["zone_ratio_end"] = z_end
    for frac in [0.1, 0.25, 0.5, 0.75, 0.9]:
        a2["points"].append(
            dict(
                fraction=frac,
                zone_ratio=frac * z_end,
                **evaluate(d, replace(zone, zone_ratio=frac * z_end), record, label=f"A2 {frac}"),
            )
        )
        out["arms"]["A2"] = a2
        write(out)
    end = evaluate(
        d,
        replace(zone, zone_ratio=z_end, a_over_l_m=0.0),
        record,
        calibrate_access=False,
        label="A2 end",
    )
    a2["points"].append(dict(fraction=1.0, zone_ratio=z_end, end=True, **end))
    out["arms"]["A2"] = a2
    write(out)
    # A4: old-membrane P_Cl / P_K.
    a4 = dict(
        by_construction=by_construction(arms, "A4_old_membrane_chloride"), marked_x=0.06, points=[]
    )
    for x in [0.03, 0.06, 0.12]:
        a4["points"].append(
            dict(
                x=x,
                **evaluate(d, replace(base, old_relative=(1.0, 1.0, x)), record, label=f"A4 x={x}"),
            )
        )
        out["arms"]["A4"] = a4
        write(out)
    # A7a: depth scaling; A7b: late apposition.
    values = ref.scalar_values(d)
    r_b, r_m = rings.ring_geometry(0.26e-6, values["new_membrane_area_at_j1_m2"] / 2.0)
    d_ref = R_EGG_M - r_b
    a7a = dict(
        by_construction=by_construction(arms, "A7_depth_dependent_access", "A7a_depth_scaling"),
        points=[],
    )
    for alpha in [0.5, 1.0, 2.0]:
        egg = replace(base, access_shape=("depth", alpha, R_EGG_M, r_m, d_ref))
        a7a["points"].append(
            dict(alpha=alpha, **evaluate(d, egg, record, label=f"A7a alpha={alpha}"))
        )
        out["arms"]["A7a"] = a7a
        write(out)
    a7b = dict(
        by_construction=by_construction(arms, "A7_depth_dependent_access", "A7b_late_apposition"),
        points=[],
    )
    for beta in [0.8, 0.6, 0.4]:
        egg = replace(base, access_shape=("ramp", beta, 900.0, 1680.0))
        a7b["points"].append(dict(beta=beta, **evaluate(d, egg, record, label=f"A7b beta={beta}")))
        out["arms"]["A7b"] = a7b
        write(out)
    return out


def group_a3(args):
    d, arms, record = inputs()
    out = dict(group="a3", by_construction=by_construction(arms, "A3_distributed_lumen"), points=[])
    write = writer(Path(args.output) / "a3.json")
    values = ref.scalar_values(d)
    face = values["new_membrane_area_at_j1_m2"] / 2.0
    cases = [
        dict(n=1, w=2.0e-6, bridge=0.26e-6, rim="calibrated"),
        dict(n=10, w=2.0e-6, bridge=0.26e-6, rim="calibrated"),
        dict(n=20, w=2.0e-6, bridge=0.26e-6, rim="calibrated"),
        dict(n=10, w=1.5e-6, bridge=0.26e-6, rim="calibrated"),
        dict(n=10, w=2.5e-6, bridge=0.26e-6, rim="calibrated"),
        dict(n=10, w=2.0e-6, bridge=0.206e-6, rim="calibrated"),
        dict(n=10, w=2.0e-6, bridge=0.314e-6, rim="calibrated"),
        dict(n=10, w=1.5e-6, bridge=0.26e-6, rim="geometric"),
        dict(n=10, w=2.0e-6, bridge=0.26e-6, rim="geometric"),
        dict(n=10, w=2.5e-6, bridge=0.26e-6, rim="geometric"),
        dict(n=20, w=2.0e-6, bridge=0.26e-6, rim="geometric"),
    ]
    for c in cases:
        r_b, r_m = rings.ring_geometry(c["bridge"], face)
        geom = rings.Rings(c["n"], r_b, r_m, rim=c["rim"])
        egg = default_egg(d, gap_width_m=c["w"])
        label = f"A3 N={c['n']} w={c['w'] * 1e6:g}um bridge={c['bridge'] * 1e6:g}mm2 rim={c['rim']}"
        try:
            point = evaluate(
                d,
                egg,
                record,
                runner=rings.runner(geom),
                calibrate_access=c["rim"] == "calibrated",
                label=label,
            )
        except Exception as error:  # Kept: a failed point is a result.
            point = dict(label=label, error=repr(error), tb=traceback.format_exc())
            log_line(label, "FAILED", repr(error))
        out["points"].append(dict(case=c, r_bridge_m=r_b, r_mouth_m=r_m, **point))
        write(out)
    return out


def exposed_arm(d, values, *, rm1, area, new_permeability):
    """The exposed arm: new membrane facing the bath, 0.04 mm2/min from onset to `area`."""
    rate = 0.04e-6 / 60.0
    egg = ref.build(d, values)
    duration = (area - egg.activation_area_m2) / rate
    egg = replace(
        egg,
        new_faces="bath",
        schedule=((egg.onset_s, rate), (egg.onset_s + duration, 0.0)),
        new_permeability=new_permeability,
    )
    p_old = ref.calibrate_old(egg, rm1, tuple(d["rm_definition"]["rm1_pulse_pair"]), method=METHOD)
    return replace(egg, p_old=p_old)


def fit_arm(d, values, arm, *, em2, rm2, area, x0):
    """P_K,new and P_Na/P_K with the exposed arm's pulse Em2 and Rm2 equal to the data."""
    template = exposed_arm(d, values, rm1=arm["rm1"], area=area, new_permeability=(0.0, 1e-7, 0.0))
    calls = []

    def residual(x):
        pk, rho = math.exp(x[0]), math.exp(x[1])
        egg = replace(template, new_permeability=(rho * pk, pk, 0.0))
        j1, _ = ref.j1_readout(d, egg, method=METHOD)
        r = [(j1["em_V"] - em2) * 1e3, math.log(j1["rm_ohm"] / rm2)]
        calls.append(dict(pk=pk, rho=rho, em_V=j1["em_V"], rm_ohm=j1["rm_ohm"]))
        return r

    sol = root(residual, x0, method="hybr", options=dict(xtol=1e-8))
    pk, rho = math.exp(sol.x[0]), math.exp(sol.x[1])
    return dict(
        success=bool(sol.success),
        message=str(sol.message),
        pk_m_s=pk,
        rho=rho,
        residual=list(map(float, sol.fun)),
        evaluations=len(calls),
        last=calls[-1] if calls else None,
    )


def group_a6(args):
    d, arms, record = inputs()
    out = dict(
        group="a6",
        by_construction=by_construction(arms, "A6_new_membrane_rules_per_exposed_arm"),
        points={},
    )
    write = writer(Path(args.output) / "a6.json")
    rules = {
        "A6a_minus_VM_rules": dict(
            new_membrane_specific_resistance_ohm_m2=0.182, new_membrane_PNa_over_PK=0.019266
        ),
        "A6b_plus_VM_plus_CCB_rules": dict(
            new_membrane_specific_resistance_ohm_m2=0.136, new_membrane_PNa_over_PK=0.047778
        ),
    }
    for label, override in rules.items():
        out["points"][label] = dict(
            override=override, **evaluate(d, default_egg(d, **override), record, label=label)
        )
        write(out)
    arms_data = {
        "A6c_minus_VM_fit": dict(
            rm1=901e3,
            em2=-0.0600,
            em2_se=0.0025,
            rm2=336e3,
            rm2_se=31e3,
            area=0.33e-6,
            area_se=0.018e-6,
            rule="A6a_minus_VM_rules",
        ),
        "A6d_plus_VM_plus_CCB_fit": dict(
            rm1=779e3,
            em2=-0.0609,
            em2_se=0.0034,
            rm2=165e3,
            rm2_se=10e3,
            area=0.65e-6,
            area_se=0.039e-6,
            rule="A6b_plus_VM_plus_CCB_rules",
        ),
    }
    for label, arm in arms_data.items():
        values = ref.scalar_values(d, rules[arm["rule"]])
        start = ref.build(d, values).new_permeability
        x0 = [math.log(start[1]), math.log(start[0] / start[1])]
        cases = [("central", {})]
        for key in ("em2", "rm2", "area"):
            for sign, end in ((-1, "low"), (1, "high")):
                cases.append((f"{key}:{end}", {key: arm[key] + sign * arm[key + "_se"]}))
        results = {}
        for case, change in cases:
            data = dict(arm, **change)
            try:
                fit = fit_arm(
                    d, values, arm, em2=data["em2"], rm2=data["rm2"], area=data["area"], x0=x0
                )
                egg = replace(
                    default_egg(d),
                    new_permeability=(fit["rho"] * fit["pk_m_s"], fit["pk_m_s"], 0.0),
                )
                point = evaluate(d, egg, record, label=f"{label} {case}")
                results[case] = dict(fit=fit, **point)
            except Exception as error:  # Kept: a failed fit is a result.
                results[case] = dict(error=repr(error), tb=traceback.format_exc())
                log_line(label, case, "FAILED", repr(error))
            out["points"][label] = results
            write(out)
    return out


def group_timing(args):
    """Cost of one J1-length pulsed run of the ring model (N = 1 and 10) on an egg-scale synthetic
    cell: the registered schedule and ring geometry, non-J1 compositions and permeabilities."""
    d = ref.load_declared()
    values = ref.scalar_values(d)
    j1 = ref.build(d, values)
    egg = ref.Egg(
        temperature_K=300.0,
        cytosol_volume_m3=7.8e-10,
        cytosol_mM=(12.0, 140.0, 30.0),
        bath_mM=(100.0, 3.0, 103.0),
        old_area_m2=8.7e-6,
        old_capacitance_F=3.2e-8,
        old_relative=(1.0, 1.0, 0.0),
        p_old=2e-10,
        new_permeability=(4e-9, 1e-7, 0.0),
        new_specific_capacitance_F_m2=6.2e-3,
        onset_s=j1.onset_s,
        activation_area_m2=j1.activation_area_m2,
        schedule=j1.schedule,
        gap_width_m=2e-6,
        access_law="logmean",
        access_D=(1.33e-9, 1.96e-9, 2.03e-9),
        a_over_l_m=1e-6,
    )
    r_b, r_m = rings.ring_geometry(0.26e-6, values["new_membrane_area_at_j1_m2"] / 2.0)
    t_end = 1801.0
    out = dict(group="timing", horizon_s=t_end, results={})
    base = ref.simulate(egg, t_end, method=METHOD)
    out["results"]["R-full"] = dict(wall_s=base.wall_s, steps=base.steps)
    log_line("timing R-full", base.wall_s, base.steps)
    for n in (1, 10):
        run = rings.simulate(egg, t_end, rings=rings.Rings(n, r_b, r_m), method=METHOD)
        out["results"][f"N={n}"] = dict(wall_s=run.wall_s, steps=run.steps)
        log_line("timing", n, run.wall_s, run.steps)
    return out


GROUPS = dict(timing=group_timing, g1=group_g1, a3=group_a3, a6=group_a6)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("group", choices=sorted(GROUPS))
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        result = GROUPS[args.group](args)
        result["verdict"] = "done"
    except Exception as error:  # Kept as the group's result.
        result = dict(
            group=args.group, verdict="error", error=repr(error), tb=traceback.format_exc()
        )
    result["provenance"] = ref.provenance()
    result["wall_s"] = time.perf_counter() - started
    name = args.group if args.group == "timing" else f"{args.group}_final"
    (output / f"{name}.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
    log_line(args.group, result.get("verdict"), f"{result['wall_s']:.0f} s")


if __name__ == "__main__":
    main()
