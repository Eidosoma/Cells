"""Runner for the registered J1 combination round on R-full (j1_combination_round.json).

R-full only; numpy/scipy. In the arms containing A1, J1 calibrates f: this is the round's
declared calibration. No other value is picked from Em or from the time course. C1 and J2 stay
held: no solution B or C, and no DFS74 or J2 quantity.

Every point recalibrates P_old on pulse Rm1 and the access (A/L, or kappa under A7a's depth
shape) on pulse Rm2, as the diagnostic runner's evaluate() does. It then runs the registered
0-35 min protocol and reports Em and Rm at J1, the time course, D1-D7, Rm(17), Rm_low and F17,
and each registered criterion, with T-R17 and T-D7 in both forms. The arm's predicted Em at J1 is
reported beside the result.

The arms are built only from fields R-full already has, all null by default: bath_fraction,
access_shape, access_D and new_permeability. R-full's null path is therefore untouched.

Groups (python -m validation.division.j1_combination_runner GROUP --output DIR):
  a1     the null check, then A1 x A7a at alpha 0, 0.5, 1 and 2, with f calibrated on J1 at each
  pairs  seal x A7a (alpha 0, 1), A6c x A7a (central fit, alpha 1), seal x A6c (alpha 0, 1)
"""

import argparse
import json
import math
import time
import traceback
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

from validation.division import cleft_egg_reference as ref
from validation.division import cleft_rings_reference as rings
from validation.division import j1_diagnostic_runner as diag

HERE = Path(__file__).parent
ROUND = HERE / "j1_combination_round.json"
A6_FINAL = Path(
    "/mnt/workspaces/Cells/cell-division-s0b-20261111-01/j1-diagnostic-01/a6/a6_final.json"
)
METHOD = diag.METHOD  # LSODA, rtol 1e-10, as the band and the single arms
log_line = diag.log_line

# Registered values (j1_combination_round.json, calibration_per_unknown and pass_criteria).
F_BRACKET = (0.01, 0.03)
F_XTOL = 1e-8
ELIGIBLE_ALPHAS = (0.0, 1.0)
J1_MINUTES = 30.0
T_D2_MV = (-12.5, -7.5)
T_D3_MIN = 15.0
T_D4_MAX_MV = 3.0
T_D5_MAX = 0.66
T_R17_FIRST_MAX_OHM = 512e3
T_R17_F17_MIN = 0.935
T_D7_FIRST_MAX_KOHM = 91.0
T_D7_FRACTION = 0.25
FIG2_POST_RUN_VALUES = dict(  # pass_criteria.fig2: reported beside, never judged
    D2_mV=-10.0, D3_time_min=15.0, D4_mV=2.5, D5=0.46, F17=1.0, D7_kOhm=80.0
)

ARMS = {
    "A1_x_A7a": dict(alphas=(0.0, 0.5, 1.0, 2.0), calibrate_f=True, seal=False, a6c=False),
    "seal_x_A7a": dict(alphas=(0.0, 1.0), calibrate_f=False, seal=True, a6c=False),
    "A6c_x_A7a": dict(alphas=(1.0,), calibrate_f=False, seal=False, a6c=True),
    "seal_x_A6c": dict(alphas=(0.0, 1.0), calibrate_f=False, seal=True, a6c=True),
}
GROUP_ARMS = {"a1": ("A1_x_A7a",), "pairs": ("seal_x_A7a", "A6c_x_A7a", "seal_x_A6c")}


# ---------------------------------------------------------------- building an arm


def depth_shape(alpha, r_egg, r_bridge, r_mouth):
    """A7a's access shape (arm file); empty at alpha = 0, the registered constant access."""
    if alpha == 0.0:
        return ()
    return ("depth", alpha, r_egg, r_mouth, r_egg - r_bridge)


def j1_geometry(d):
    """(R_egg, r_bridge, r_mouth) of A3's slit at J1, as the single A7a arm used it."""
    values = ref.scalar_values(d)
    r_b, r_m = rings.ring_geometry(0.26e-6, values["new_membrane_area_at_j1_m2"] / 2.0)
    return diag.R_EGG_M, r_b, r_m


def arm_egg(base, *, alpha, geometry, f=0.0, seal=False, a6c_fit=None):
    """`base` with an arm's parts. f is A1's bath-facing fraction. The seal is the A8 rule
    (access D_Cl = 0, cation ratios free-solution, as build() does for 'cation_selective').
    a6c_fit is {'pk_m_s', 'rho'} for the new membrane (Na, K, Cl) = (rho P_K, P_K, 0)."""
    egg = replace(base, bath_fraction=f, access_shape=depth_shape(alpha, *geometry))
    if seal:
        egg = replace(egg, access_D=(egg.access_D[0], egg.access_D[1], 0.0))
    if a6c_fit is not None:
        pk = a6c_fit["pk_m_s"]
        egg = replace(egg, new_permeability=(a6c_fit["rho"] * pk, pk, 0.0))
    return egg


def a6c_central(path=A6_FINAL):
    """A6c's central -VM fit as recorded by the single-arm round (not refit)."""
    fit = json.loads(Path(path).read_text())["points"]["A6c_minus_VM_fit"]["central"]["fit"]
    return dict(pk_m_s=fit["pk_m_s"], rho=fit["rho"], source=str(path))


# ---------------------------------------------------------------- the f calibration


def recalibrated_em(egg, *, rm1_ohm, rm2_ohm, rm1_pair, j1_pair, em_pulse, guess, runner=None):
    """Em (V) at the front edge of pulse em_pulse after P_old on rm1 and the access on rm2,
    calibrated as evaluate() does, and the calibrated egg. A sealed egg (A/L = 0) keeps its
    access: there is none to calibrate."""
    p_old = ref.calibrate_old(egg, rm1_ohm, rm1_pair, method=METHOD, runner=runner)
    egg = replace(egg, p_old=p_old)
    if egg.a_over_l_m != 0.0:
        al, _ = ref.calibrate_access(
            egg, rm2_ohm, j1_pair, method=METHOD, guess=guess, step=0.02, runner=runner
        )
        egg = replace(egg, a_over_l_m=al)
    _, run = ref.rm_at(egg, j1_pair, method=METHOD, runner=runner)
    return run.onset_V[em_pulse], egg


def calibrate_fraction(em_at, target_V, *, bracket=F_BRACKET, f_end=None, xtol=F_XTOL):
    """The registered f search: f with em_at(f) = target_V.

    Brent's method, starting from `bracket` and widened to [0, f_end] if the bracket does not
    hold the target. f_end may be a number or a callable that computes it, so that it is computed
    only when needed. Returns (f, evaluations), where f is None if there is no crossing.
    Evaluations are cached, so each f costs one em_at call.
    """
    cache, log = {}, []

    def miss(f):
        if f not in cache:
            cache[f] = em_at(f)
            log.append(dict(f=f, em_V=cache[f]))
        return cache[f] - target_V

    lo, hi = bracket
    if miss(lo) * miss(hi) > 0.0:
        if f_end is None:
            return None, log
        lo, hi = 0.0, f_end() if callable(f_end) else f_end
        if miss(lo) * miss(hi) > 0.0:
            return None, log
    for end in (lo, hi):
        if miss(end) == 0.0:
            return end, log
    return brentq(miss, lo, hi, xtol=xtol), log


def j1_em(d, egg, record, *, runner=None):
    """Em at J1 (V) after the recalibration of evaluate(), for the f search."""
    rm = d["rm_definition"]
    targets = ref.scalar_values(d)
    guess = record["a_over_l_m"] if math.isnan(egg.a_over_l_m) else egg.a_over_l_m
    em, _ = recalibrated_em(
        egg,
        rm1_ohm=targets["rm1_target_ohm"],
        rm2_ohm=targets["rm2_target_ohm"],
        rm1_pair=tuple(rm["rm1_pulse_pair"]),
        j1_pair=tuple(rm["j1_pulse_pair"]),
        em_pulse=rm["j1_em_pulse"],
        guess=guess,
        runner=runner,
    )
    return em


# ---------------------------------------------------------------- judging a point


def radau_runner(egg, t_end, *, rtol=1e-10, method=None, record=()):
    """R-full with Radau whatever the caller asks: the failure rule's single rerun."""
    return ref.simulate(egg, t_end, rtol=rtol, method="Radau", record=record)


def j1_window(d):
    """T-J1: the registered window, the measured mean +/- 2 SE (V)."""
    o = d["observable"]
    mean, se = o["measured_mean_V"], o["measured_se_V"]
    return (mean - 2 * se, mean + 2 * se)


def judge(point, *, rm1_ohm, window=None):
    """Every registered criterion at one point; T-R17 and T-D7 in both forms.

    window: T-J1's window (V), or None where Em at J1 is set by construction (A1 x A7a).
    """
    tc, dd = point["time_course"], point["descriptors"]
    t = np.asarray(tc["times_s"])
    rm = np.asarray(tc["rm_ohm"])
    rm17 = float(rm[int(np.flatnonzero(np.isclose(t, 17 * 60.0))[0])])
    rm_low = float(np.min(rm[t <= J1_MINUTES * 60.0 + 1e-9]))
    f17 = (rm1_ohm - rm17) / (rm1_ohm - rm_low)
    d7 = dd["D7_late_rm_rise_kOhm"]
    d7_restated_max = T_D7_FRACTION * (rm1_ohm - rm_low) / 1e3
    shared = {
        "T-D2": dict(
            value=dd["D2_em_change_7_to_17_min_mV"],
            passes=T_D2_MV[0] <= dd["D2_em_change_7_to_17_min_mV"] <= T_D2_MV[1],
        ),
        "T-D3": dict(
            value=dd["D3_em_minimum"]["time_min"],
            passes=dd["D3_em_minimum"]["time_min"] >= T_D3_MIN,
        ),
        "T-D4": dict(value=dd["D4_late_change_mV"], passes=dd["D4_late_change_mV"] <= T_D4_MAX_MV),
        "T-D5": dict(
            value=dd["D5_rm_fraction_of_fall_by_10_min"],
            passes=dd["D5_rm_fraction_of_fall_by_10_min"] <= T_D5_MAX,
        ),
    }
    if window is not None:
        em = point["em_j1_V"]
        shared["T-J1"] = dict(value=em, passes=window[0] <= em <= window[1])
    forms = {
        "T-R17": dict(
            first=dict(value=rm17, passes=rm17 <= T_R17_FIRST_MAX_OHM),
            restated=dict(value=f17, passes=f17 >= T_R17_F17_MIN),
        ),
        "T-D7": dict(
            first=dict(value=d7, passes=d7 <= T_D7_FIRST_MAX_KOHM),
            restated=dict(value=d7, limit=d7_restated_max, passes=d7 <= d7_restated_max),
        ),
    }
    base_pass = all(c["passes"] for c in shared.values())
    under = {
        form: base_pass and all(c[form]["passes"] for c in forms.values())
        for form in ("first", "restated")
    }
    if under["first"] and under["restated"]:
        verdict = "passes"
    elif under["first"] or under["restated"]:
        verdict = "form-dependent"  # lead_decisions_taken: blocks freezing of this point only
    else:
        verdict = "fails"
    return dict(
        rm17_ohm=rm17,
        rm_low_ohm=rm_low,
        f17=f17,
        criteria=shared | forms,
        passes_under=under,
        verdict=verdict,
    )


# ---------------------------------------------------------------- one point


def evaluate_arm_point(ctx, arm, alpha, runner=None):
    """One point of one arm: f search if the arm has A1, then evaluate() and judge()."""
    spec = ARMS[arm]
    d, record = ctx["d"], ctx["record"]
    parts = dict(seal=spec["seal"], a6c_fit=ctx["a6c"] if spec["a6c"] else None)
    label = f"{arm} alpha={alpha:g}"
    extra = {}
    f = 0.0
    if spec["calibrate_f"]:

        def em_at(x):
            egg = arm_egg(ctx["base"], alpha=alpha, geometry=ctx["geometry"], f=x, **parts)
            if ctx["f_end"] is not None and x >= ctx["f_end"]:
                egg = replace(egg, a_over_l_m=0.0)  # the end point: the lumen is sealed
            return j1_em(d, egg, record, runner=runner)

        f, search = calibrate_fraction(
            em_at, ctx["j1_target_V"], f_end=lambda: ctx["compute_f_end"]()
        )
        extra = dict(f_search=search, f_end=ctx["f_end"])
        if f is None:  # registered: an alpha with no J1 crossing yields no candidate
            log_line(label, "no J1 crossing in [0, f_end]")
            return dict(
                label=label,
                arm=arm,
                alpha=alpha,
                eligible=alpha in ELIGIBLE_ALPHAS,
                verdict="no crossing",
                **extra,
            )
        label += f" f={f:.8f}"
    egg = arm_egg(ctx["base"], alpha=alpha, geometry=ctx["geometry"], f=f, **parts)
    point = diag.evaluate(d, egg, record, runner=runner, label=label)
    verdicts = judge(
        point, rm1_ohm=ctx["rm1_ohm"], window=None if spec["calibrate_f"] else ctx["window"]
    )
    return dict(
        arm=arm,
        alpha=alpha,
        eligible=alpha in ELIGIBLE_ALPHAS,
        f=f if spec["calibrate_f"] else None,
        seal=spec["seal"],
        a6c_fit=parts["a6c_fit"],
        predicted_T_J1=ctx["predictions"][arm],
        em_start_V=point["time_course"]["em_V"][0],
        **extra,
        **point,
        **verdicts,
    )


def with_failure_rule(ctx, arm, alpha):
    """The registered failure rule: a point that fails to integrate is recorded as failed and
    rerun once with Radau at rtol 1e-10, reported as such; a failed point never passes."""
    try:
        return evaluate_arm_point(ctx, arm, alpha)
    except Exception as error:  # Kept: a failed point is a result.
        failed = dict(error=repr(error), tb=traceback.format_exc())
        log_line(arm, alpha, "FAILED", repr(error), "- rerunning once with Radau")
    try:
        return dict(evaluate_arm_point(ctx, arm, alpha, runner=radau_runner), first_failure=failed)
    except Exception as error:
        log_line(arm, alpha, "FAILED again with Radau", repr(error))
        return dict(
            arm=arm,
            alpha=alpha,
            eligible=alpha in ELIGIBLE_ALPHAS,
            verdict="failed",
            first_failure=failed,
            radau_failure=dict(error=repr(error), tb=traceback.format_exc()),
        )


# ---------------------------------------------------------------- groups


def context(args):
    d, _, record = diag.inputs()
    registered = json.loads(ROUND.read_text())
    ctx = dict(
        d=d,
        record=record,
        base=diag.default_egg(d),
        geometry=j1_geometry(d),
        rm1_ohm=ref.scalar_values(d)["rm1_target_ohm"],
        window=j1_window(d),
        j1_target_V=d["observable"]["measured_mean_V"],
        predictions={a["id"]: a["predicted_T_J1"] for a in registered["arms"]},
        a6c=a6c_central(args.a6_final),
        f_end=None,
    )

    def compute_f_end():
        if ctx["f_end"] is None:
            ctx["f_end"] = diag.end_point(
                d, ctx["base"], record, "bath_fraction", 0.01, 0.6, label="A1 f_end"
            )
        return ctx["f_end"]

    ctx["compute_f_end"] = compute_f_end
    return ctx


def run_group(args):
    ctx = context(args)
    out = dict(
        group=args.group,
        round_file=str(ROUND),
        a6c_fit=ctx["a6c"],
        j1_target_V=ctx["j1_target_V"],
        j1_window_V=list(ctx["window"]),
        fig2_post_run_values=FIG2_POST_RUN_VALUES,
        points=[],
    )
    write = diag.writer(Path(args.output) / f"{args.group}.json")
    if args.group == "a1":
        null = diag.evaluate(ctx["d"], ctx["base"], ctx["record"], label="null (registered)")
        miss = null["em_j1_V"] - ctx["record"]["prediction_of_record_V"]
        out["null_check"] = dict(
            em_j1_V=null["em_j1_V"],
            record_minus_null_V=-miss,
            within_reference_term=abs(miss) <= diag.REFERENCE_TERM_V,
        )
        write(out)
        if not out["null_check"]["within_reference_term"]:
            raise RuntimeError(f"null check failed: record - null = {-miss!r} V")
    for arm in GROUP_ARMS[args.group]:
        for alpha in ARMS[arm]["alphas"]:
            out["points"].append(with_failure_rule(ctx, arm, alpha))
            out["f_end"] = ctx["f_end"]
            write(out)
    out["eligible_passing"] = [
        p.get("label", f"{p['arm']} alpha={p['alpha']:g}")
        for p in out["points"]
        if p.get("eligible") and p.get("verdict") == "passes"
    ]
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("group", choices=sorted(GROUP_ARMS))
    parser.add_argument("--output", required=True)
    parser.add_argument("--a6-final", default=str(A6_FINAL), help="A6c's recorded fits")
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        result = run_group(args)
        result["verdict"] = "done"
    except Exception as error:  # Kept as the group's result.
        result = dict(
            group=args.group, verdict="error", error=repr(error), tb=traceback.format_exc()
        )
    result["provenance"] = ref.provenance()
    result["wall_s"] = time.perf_counter() - started
    (output / f"{args.group}_final.json").write_text(
        json.dumps(result, indent=1, default=float) + "\n"
    )
    log_line(args.group, result.get("verdict"), f"{result['wall_s']:.0f} s")


if __name__ == "__main__":
    main()
