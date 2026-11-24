"""FR-49 code-blind reference (protocol fr49-compartment-compositions-v1): the generator and writer.

For each world of a spec file (L, B, C1, C2) it evaluates the high-precision routes of fr49_exact
and the ODE integrations of fr49_ode, compares them, and writes <world>.json. Each file holds the
primary route's values at 30 significant digits, the method with the largest differences, and the
provenance.

Usage:
    python fr49_reference.py                     the registered worlds -> results/
    python fr49_reference.py --format-sample     format-sample/invented_cases.json -> format-sample/
    python fr49_reference.py --spec FILE --out DIR [--worlds L B ...]   any spec file -> DIR

Writing results/ or format-sample/ is refused while the checkout has dirty paths, other than the
files this writer produces, unless --allow-dirty is given. Any other --out must lie outside the
repository. A spec file with "invented": true marks every output invented, in its "inputs" block,
and names it INVENTED_<world>.json.
"""

from __future__ import annotations

import os

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse  # noqa: E402
import decimal  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from decimal import Decimal  # noqa: E402
from fractions import Fraction  # noqa: E402
from pathlib import Path  # noqa: E402

import fr49_exact as exact  # noqa: E402
import fr49_ode as ode  # noqa: E402
import fr49_spec  # noqa: E402
import numpy  # noqa: E402
import scipy  # noqa: E402

HERE = Path(__file__).resolve().parent
PACKAGE = "validation/fr49/references"
RESULTS_DIR = HERE / "results"
SAMPLE_DIR = HERE / "format-sample"
SAMPLE_SPEC = SAMPLE_DIR / "invented_cases.json"
OUTPUT_PREFIXES = (f"{PACKAGE}/results/", f"{PACKAGE}/format-sample/INVENTED_")
OUT_DIGITS = 30
SPEC_TAG = "fr49-compartment-compositions-v1-registered-2026-11-23"
TAYLOR_STEP = {"B": "0.05", "C2": "0.1"}  # s
TAYLOR_CHECK_STEP = "0.05"  # s: C2's step check
ACCURACY = {"thirty_digit": Fraction(1, 10**20), "ode": Fraction(1, 10**10),
            "matrix_exponential": Fraction(1, 10**13)}

L_QUANTITIES = {
    "n_O": "fmol: S in the owner O",
    "n_C": "fmol: S in the compartment C",
    "x_O": "fmol: S carrying label x in O",
    "x_C": "fmol: S carrying label x in C",
    "base_O": "fmol: S at the base label in O, n_O - x_O",
    "base_C": "fmol: S at the base label in C, n_C - x_C",
    "share_x_O": "dimensionless: O's share of label x, x_O/n_O",
    "share_x_C": "dimensionless: C's share of label x, x_C/n_C",
}
B_QUANTITIES = {"B": "fmol: bound ligand", "n_L": "fmol: free ligand in C",
                "c": "mM: free ligand concentration n_L/V_C"}
B_ONCE = {"S": "fmol", "K_d": "mM", "b": "fmol", "c*": "mM", "B*": "fmol", "B1": "fmol",
          "B2": "fmol", "lambda": "1/s", "L_T": "fmol", "d": "fmol"}
C2_QUANTITIES = {"B1": "fmol: L1 bound", "B2": "fmol: L2 bound",
                 "c1": "mM: free L1, (L_T1 - B1)/V_C", "c2": "mM: free L2, (L_T2 - B2)/V_C",
                 "R": "fmol: free sites, S - B1 - B2"}
C2_ONCE = {"c1*": "mM", "c2*": "mM", "B1*": "fmol", "B2*": "fmol", "R*": "fmol", "S": "fmol",
           "K_1": "mM", "K_2": "mM"}
WELL = {"x_W_before": "fmol", "b_W_before": "fmol", "n_W_before": "fmol",
        "share_x_W_before": "dimensionless", "share_b_W_before": "dimensionless",
        "x_W_after": "fmol", "b_W_after": "fmol", "n_W_after": "fmol",
        "share_x_W_after": "dimensionless", "share_b_W_after": "dimensionless"}


def fmt(x, digits: int = OUT_DIGITS) -> str:
    """x as d.ddd...e+N with `digits` significant digits, half-even; an exact zero is "0"."""
    if not isinstance(x, Decimal):
        x = exact.context(80).divide(Decimal(Fraction(x).numerator),
                                     Decimal(Fraction(x).denominator))
    if x == 0:
        return "0"
    y = exact.context(digits).plus(x)
    sign, ds, _ = y.as_tuple()
    ds = tuple(ds) + (0,) * (digits - len(ds))
    mantissa = f"{ds[0]}." + "".join(str(d) for d in ds[1:]) if digits > 1 else f"{ds[0]}"
    return f"{'-' if sign else ''}{mantissa}e{y.adjusted():+d}"


def rel(a, b) -> Fraction:
    """|a - b| / max(|a|, |b|) in exact rationals; 0 when a == b (so exact zeros count 0)."""
    a, b = Fraction(a), Fraction(b)
    if a == b:
        return Fraction(0)
    return abs(a - b) / max(abs(a), abs(b))


def fmt_q(q: Fraction, digits: int = 3) -> str:
    return fmt(q, digits)


def _git(*args: str) -> str | None:
    try:
        done = subprocess.run(["git", *args], cwd=HERE, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return done.stdout.decode("utf-8", "surrogateescape")


def repository_root() -> Path | None:
    top = _git("rev-parse", "--show-toplevel")
    return Path(top.strip()) if top else None


def provenance() -> dict:
    """The git revision, the dirty paths (other than this writer's outputs), and the Python,
    NumPy and SciPy versions."""
    revision = _git("rev-parse", "HEAD")
    dirty = []
    status = _git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    if status is not None:
        entries = status.split("\0")
        n = 0
        while n < len(entries):
            entry = entries[n]
            n += 1
            if not entry:
                continue
            code, path = entry[:2], entry[3:]
            if code[0] in "RC":
                n += 1
            if not path.startswith(OUTPUT_PREFIXES):
                dirty.append(path)
    return {
        "git_revision": revision.strip() if revision else None,
        "dirty_paths": sorted(dirty),
        "dirty_paths_exclude": [f"{prefix}*" for prefix in OUTPUT_PREFIXES],
        "python": sys.version,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "libmpdec": decimal.__libmpdec_version__,
        "generator": f"{PACKAGE}/fr49_reference.py",
    }


def inputs_block(spec: fr49_spec.Spec) -> dict:
    try:
        spec_file = f"{PACKAGE}/{spec.path.resolve().relative_to(HERE).as_posix()}"
    except ValueError:
        spec_file = spec.path.resolve().as_posix()
    if spec.invented:
        statement = ("INVENTED inputs, for a format sample only: this file shows the results "
                     "layout. No value in it is a reference value of any registered world.")
    else:
        statement = (f"The registered worlds: {PACKAGE}/spec/cases.json, in a byte-identical "
                     f"copy of the tag {SPEC_TAG}.")
    return {"invented": spec.invented, "spec_file": spec_file, "statement": statement}


def _header(spec: fr49_spec.Spec, world: str, declared: dict) -> dict:
    return {"kind": "cells.fr49_reference_result@1",
            "protocol": "fr49-compartment-compositions-v1",
            "world": world, "inputs": inputs_block(spec), "declared": declared}


def _diffs(primary: dict, other: dict, names) -> tuple[dict, Fraction]:
    """Per quantity, the largest relative difference over the samples and its sample index."""
    table, worst = {}, Fraction(0)
    for name in names:
        best, where = Fraction(-1), None
        for i, (a, b) in enumerate(zip(primary[name], other[name], strict=True)):
            d = rel(a, b)
            if d > best:
                best, where = d, i
        table[name] = {"max": fmt_q(best), "sample_index": where}
        worst = max(worst, best)
    return table, worst


def _normalised(primary: dict, other: dict, names) -> dict:
    """max_i |a - b| / max_i |a|, the measure the registration's errors use."""
    out = {}
    for name in names:
        top = max(abs(Fraction(a)) for a in primary[name])
        gap = max(abs(Fraction(a) - Fraction(b))
                  for a, b in zip(primary[name], other[name], strict=True))
        out[name] = fmt_q(gap / top if top else Fraction(0))
    return out


def _reported_error(primary: dict, other: dict, names) -> Fraction:
    worst = Fraction(0)
    for name in names:
        for a, b in zip(primary[name], other[name], strict=True):
            worst = max(worst, rel(Decimal(fmt(a)), b))
    return worst


def _within(value: Fraction, bound: Fraction) -> bool:
    return value <= bound


# ---- World L -------------------------------------------------------------------------------------

def world_L_parts(spec: fr49_spec.Spec) -> tuple[list, dict, dict, dict]:
    W = spec.L
    times = exact.sample_times(W.samples)
    primary = exact.world_L_expm(W)
    eigen = exact.world_L_sylvester(W)
    radau_raw = ode.world_L_radau(W)
    radau = {"n_O": list(radau_raw[0]), "n_C": list(radau_raw[1]), "x_O": list(radau_raw[2]),
             "x_C": list(radau_raw[3])}
    radau["base_O"] = [a - b for a, b in zip(radau["n_O"], radau["x_O"], strict=True)]
    radau["base_C"] = [a - b for a, b in zip(radau["n_C"], radau["x_C"], strict=True)]
    radau["share_x_O"] = [a / b for a, b in zip(radau["x_O"], radau["n_O"], strict=True)]
    radau["share_x_C"] = [a / b for a, b in zip(radau["x_C"], radau["n_C"], strict=True)]
    return times, primary, eigen, radau


def world_L_body(spec: fr49_spec.Spec, parts) -> tuple[dict, dict]:
    times, primary, eigen, radau = parts
    names = list(L_QUANTITIES)
    eigen_table, eigen_worst = _diffs(primary, eigen, names)
    radau_table, radau_worst = _diffs(primary, radau, names)
    reported = _reported_error(primary, eigen, names)
    method = {
        "primary": ("The matrix exponential of the augmented linear system "
                    "(n_O, n_C, x_O, x_C, 1) on each interval between t = 0, t1, t2 and the "
                    "sample times, by its Taylor series with scaling and squaring, in decimal "
                    "arithmetic. The reported values are the primary's."),
        "working_precision_digits": exact.PREC + 10,
        "reported_significant_digits": OUT_DIGITS,
        "second_routes": {
            "eigen_closed_form": {
                "description": ("e^(A dt) by Sylvester's formula from A's two eigenvalues, about "
                                "each interval's steady state -A^-1 s, in decimal arithmetic at "
                                "70 digits; it demonstrates the matrix exponentials' accuracy"),
                "largest_relative_difference": eigen_table,
                "max": fmt_q(eigen_worst),
                "declared_accuracy": fmt_q(ACCURACY["matrix_exponential"], 1),
                "within": _within(eigen_worst, ACCURACY["matrix_exponential"]),
            },
            "ode_radau": {
                "description": ("scipy.integrate.solve_ivp, Radau, rtol 1e-13, atol 1e-30, its "
                                "steps stopped at t1 and t2 (one solve per piece), binary64. It "
                                "is held to World L's declared 1e-13, the stricter of that and "
                                "the ODE integrations' 1e-10"),
                "largest_relative_difference": radau_table,
                "max": fmt_q(radau_worst),
                "max_normalised_difference": _normalised(primary, radau, names),
                "declared_accuracy": fmt_q(ACCURACY["matrix_exponential"], 1),
                "within": _within(radau_worst, ACCURACY["matrix_exponential"]),
            },
        },
        "reported_strings_against_eigen_closed_form": fmt_q(reported),
        "difference_measure": ("|A - B| / max(|A|, |B|) per sample, in exact rational arithmetic; "
                               "0 when both are equal, as x_O and x_C are (exactly 0) before t1; "
                               "max_normalised_difference is max_i |A - B| / max_i |A|"),
    }
    method["within_declared_accuracy"] = (method["second_routes"]["eigen_closed_form"]["within"]
                                          and method["second_routes"]["ode_radau"]["within"]
                                          and reported <= ACCURACY["thirty_digit"])
    body = {"quantities": L_QUANTITIES, "sample_times_s": [str(t) for t in times]}
    body.update({name: [fmt(v) for v in primary[name]] for name in names})
    return body, method


def build_L(spec: fr49_spec.Spec, parts) -> dict:
    W = spec.L
    doc = _header(spec, "L", {
        "V_O_pL": W.V_O, "V_C_pL": W.V_C, "a_pL_per_s": W.a, "k_d_per_s": W.k_d,
        "P_fmol_per_s": W.P, "initial_fmol": {"n_O": W.n_O0, "n_C": W.n_C0, "x_O": W.x_O0,
                                               "x_C": W.x_C0},
        "pulse_s": {"t1": W.t1, "t2": W.t2}, "horizon_s": W.horizon,
        "sample_times_rule": f"t_i = {W.samples.step} i, i = 0 ... {W.samples.last}"})
    body, method = world_L_body(spec, parts)
    doc.update(body)
    doc["method"] = method
    return doc


# ---- World B -------------------------------------------------------------------------------------

def build_B(spec: fr49_spec.Spec) -> dict:
    W = spec.B
    times = exact.sample_times(W.samples)
    primary = exact.world_B_exact(spec)
    once = primary["once"]
    check = exact.world_B_once_check(spec)  # S and L_T of its own, in exact rationals
    with decimal.localcontext(exact.context()):
        S_check, L_T_check = exact.to_decimal(check["S"]), exact.to_decimal(check["L_T"])
    taylor_states = exact.binding_taylor(W.V_C, S_check, [(W.k_on, W.k_off, str(L_T_check))],
                                         [W.B0], times, TAYLOR_STEP["B"])
    with decimal.localcontext(exact.context()):
        taylor = {"B": [s[0] for s in taylor_states]}
        taylor["n_L"] = [L_T_check - b for b in taylor["B"]]
        taylor["c"] = [n / Decimal(W.V_C) for n in taylor["n_L"]]
    radau_raw = ode.world_B_radau(spec)
    radau = {"B": list(radau_raw[0]), "n_L": list(radau_raw[1]),
             "c": [n / float(W.V_C) for n in radau_raw[1]]}
    names = list(B_QUANTITIES)
    taylor_table, taylor_worst = _diffs(primary, taylor, names)
    radau_table, radau_worst = _diffs(primary, radau, names)
    once_table = {k: fmt_q(rel(once[k], check[k])) for k in B_ONCE}
    once_worst = max(rel(once[k], check[k]) for k in B_ONCE)
    reported = max(_reported_error(primary, taylor, names),
                   max(rel(Decimal(fmt(once[k])), check[k]) for k in B_ONCE))
    equilibrium_gap = rel(once["B*"], once["B1"])
    end_gap_closed = rel(primary["B"][-1], once["B*"])
    end_gap_radau = rel(radau["B"][-1], once["B*"])
    doc = _header(spec, "B", {
        "V_C_pL": W.V_C, "sites": {"copies": W.sites.copies,
                                    "sites_per_copy": W.sites.sites_per_copy,
                                    "accessible_fraction": W.sites.accessible_fraction},
        "sites_per_fmol": spec.sites_per_fmol, "k_on_per_mM_per_s": W.k_on,
        "k_off_per_s": W.k_off, "initial_fmol": {"n_L": W.n_L0, "B": W.B0},
        "horizon_s": W.horizon,
        "sample_times_rule": f"t_i = {W.samples.step} i, i = 0 ... {W.samples.last}",
        "wash_elsewhere": {"node": W.wash_node, "time_s": W.wash_time,
                           "fraction": W.wash_fraction}})
    doc["quantities"] = B_QUANTITIES
    doc["sample_times_s"] = [str(t) for t in times]
    doc.update({name: [fmt(v) for v in primary[name]] for name in names})
    doc["once_units"] = B_ONCE
    doc["once"] = {k: fmt(once[k]) for k in B_ONCE}
    doc["root_branch"] = (f"{primary['branch']}: "
                          + ("c* = 2 L_T K_d/(b + d)" if primary["branch"] == "b >= 0"
                             else "c* = (d - b)/(2 V_C)"))
    doc["checks"] = {
        "B*_against_B1_relative_difference": fmt_q(equilibrium_gap),
        "B_at_horizon_against_B*_relative_gap": fmt_q(end_gap_closed),
        "radau_B_at_horizon_against_B*_relative_gap": fmt_q(end_gap_radau),
        "wash_elsewhere": "no effect on C (LAWS.md 3): C's equations are integrated through it",
    }
    within = (taylor_worst <= ACCURACY["thirty_digit"] and radau_worst <= ACCURACY["ode"]
              and equilibrium_gap <= ACCURACY["thirty_digit"]
              and once_worst <= ACCURACY["thirty_digit"]
              and reported <= ACCURACY["thirty_digit"])
    doc["method"] = {
        "primary": ("LAWS.md 3's closed forms in decimal arithmetic: the equilibrium root c* on "
                    "its branch, B1 < B2 from the quadratic (B1 = L_T S/B2), lambda, and the "
                    "Riccati transient B = B1 - r (B2 - B1)/(1 - r), r = r0 e^(-lambda t). The "
                    "reported values are the primary's."),
        "working_precision_digits": exact.PREC,
        "reported_significant_digits": OUT_DIGITS,
        "second_routes": {
            "taylor_integration": {
                "description": (f"the binding equation integrated by its Taylor series in decimal "
                                f"arithmetic at {exact.TAYLOR_PREC} digits, fixed step "
                                f"{TAYLOR_STEP['B']} s"),
                "largest_relative_difference": taylor_table, "max": fmt_q(taylor_worst),
                "declared_accuracy": fmt_q(ACCURACY["thirty_digit"], 1),
                "within": taylor_worst <= ACCURACY["thirty_digit"]},
            "ode_radau": {
                "description": "scipy.integrate.solve_ivp, Radau, rtol 1e-12, atol 1e-30, on "
                               "(B, n_L), binary64, with its own S from the declared values",
                "largest_relative_difference": radau_table, "max": fmt_q(radau_worst),
                "max_normalised_difference": _normalised(primary, radau, names),
                "declared_accuracy": fmt_q(ACCURACY["ode"], 1),
                "within": radau_worst <= ACCURACY["ode"]},
            "once_values": {
                "description": ("each once value by a second route: S, K_d, L_T and b in exact "
                                "rationals; d from b^2 + 4 V_C L_T K_d; B1 = (s - d)/2 and "
                                "B2 = (s + d)/2, since B2 - B1 = d; lambda = k_on d/V_C; "
                                "c* = (L_T - B1)/V_C; B* = B1. The Taylor and Radau routes use "
                                "their own S and L_T"),
                "relative_difference": once_table, "max": fmt_q(once_worst),
                "declared_accuracy": fmt_q(ACCURACY["thirty_digit"], 1),
                "within": once_worst <= ACCURACY["thirty_digit"]},
            "equilibrium": {
                "description": "B* = L_T - V_C c* from the root's formula, against B1 from the "
                               "quadratic in B",
                "relative_difference": fmt_q(equilibrium_gap),
                "declared_accuracy": fmt_q(ACCURACY["thirty_digit"], 1),
                "within": equilibrium_gap <= ACCURACY["thirty_digit"]},
        },
        "reported_strings_against_second_route": fmt_q(reported),
        "difference_measure": "|A - B| / max(|A|, |B|) per sample, in exact rational arithmetic",
        "within_declared_accuracy": within,
    }
    return doc


# ---- C1 ------------------------------------------------------------------------------------------

def build_C1(spec: fr49_spec.Spec, parts) -> dict:
    W = spec.C1
    well = exact.c1_wash(W)
    check = exact.c1_wash_rational(W)
    gaps = {k: rel(well[k], check[k]) for k in WELL}
    worst = max(gaps.values())
    reported = max(rel(Decimal(fmt(well[k])), check[k]) for k in WELL)
    doc = _header(spec, "C1", {
        "world_L": "as world L, unchanged", "V_W_pL": W.V_W,
        "initial_fmol": {"x_W": W.x_W0, "b_W": W.b_W0},
        "wash": {"time_s": W.wash_time, "fraction": W.wash_fraction,
                 "buffer_mM": {"S": W.buffer_mM}, "buffer_label": "base"}})
    doc["well_units"] = WELL
    doc["well"] = {k: fmt(well[k]) for k in WELL}
    doc["well_note"] = ("just before (t_w-) and just after (t_w+) the wash at t_w; the well's "
                        "amounts are constant between washes")
    body, L_method = world_L_body(spec, parts)
    doc["world_L"] = "World L's quantities, as in L.json: the wash leaves them unchanged"
    doc.update(body)
    doc["method"] = {
        "well_primary": "LAWS.md 4's arithmetic in decimal arithmetic at 60 digits",
        "well_second_route": {"description": "the same arithmetic in exact rationals",
                              "largest_relative_difference": fmt_q(worst),
                              "declared_accuracy": fmt_q(ACCURACY["thirty_digit"], 1),
                              "within": worst <= ACCURACY["thirty_digit"]},
        "well_reported_strings_against_exact": fmt_q(reported),
        "world_L": L_method,
        "reported_significant_digits": OUT_DIGITS,
        "within_declared_accuracy": (worst <= ACCURACY["thirty_digit"]
                                     and reported <= ACCURACY["thirty_digit"]
                                     and L_method["within_declared_accuracy"]),
    }
    return doc


# ---- C2 ------------------------------------------------------------------------------------------

def build_C2(spec: fr49_spec.Spec) -> dict:
    W = spec.C2
    times = exact.sample_times(W.samples)
    if times[-1] != Decimal(W.horizon):
        raise ValueError("C2: the last sample time is not the horizon")
    root = exact.c2_root(spec)
    S = root["S"]
    ligands = [(g.k_on, g.k_off, g.total) for g in W.ligands]

    def arrays(states) -> dict:
        with decimal.localcontext(exact.context()):
            V_C = Decimal(W.V_C)
            L_T = [Decimal(g.total) for g in W.ligands]
            return {"B1": [s[0] for s in states], "B2": [s[1] for s in states],
                    "c1": [(L_T[0] - s[0]) / V_C for s in states],
                    "c2": [(L_T[1] - s[1]) / V_C for s in states],
                    "R": [S - s[0] - s[1] for s in states]}

    primary = arrays(exact.binding_taylor(W.V_C, S, ligands, list(W.B0), times,
                                          TAYLOR_STEP["C2"]))
    with decimal.localcontext(exact.context()):
        S_check = exact.to_decimal(exact.capacity_rational(W.sites, spec.sites_per_fmol))
    step_check = arrays(exact.binding_taylor(W.V_C, S_check, ligands, list(W.B0), times,
                                             TAYLOR_CHECK_STEP))
    radau_raw = ode.c2_integrate(spec, "Radau")
    dop_raw = ode.c2_integrate(spec, "DOP853")

    def from_ode(y) -> dict:
        V_C = float(W.V_C)
        return {"B1": list(y[0]), "B2": list(y[1]), "c1": [n / V_C for n in y[2]],
                "c2": [n / V_C for n in y[3]], "R": list(y[4])}

    radau, dop = from_ode(radau_raw), from_ode(dop_raw)
    names = list(C2_QUANTITIES)
    step_table, step_worst = _diffs(primary, step_check, names)
    radau_table, radau_worst = _diffs(primary, radau, names)
    dop_table, dop_worst = _diffs(primary, dop, names)
    newton = exact.c2_root_newton2(spec, [radau["c1"][-1], radau["c2"][-1]])
    once = {"c1*": root["c"][0], "c2*": root["c"][1], "B1*": root["B"][0],
            "B2*": root["B"][1], "R*": root["R"], "S": S, "K_1": root["K"][0],
            "K_2": root["K"][1]}
    once_check = {"c1*": newton["c"][0], "c2*": newton["c"][1], "B1*": newton["B"][0],
                  "B2*": newton["B"][1], "R*": newton["R"], "S": newton["S"],
                  "K_1": newton["K"][0], "K_2": newton["K"][1]}
    root_table = {k: fmt_q(rel(once[k], once_check[k])) for k in C2_ONCE}
    root_worst = max(rel(once[k], once_check[k]) for k in C2_ONCE)
    reported = max(_reported_error(primary, step_check, names),
                   max(rel(Decimal(fmt(once[k])), once_check[k]) for k in C2_ONCE))
    end = {f"{route}_B{j + 1}": fmt_q(rel(values[f"B{j + 1}"][-1], root["B"][j]))
           for route, values in (("taylor", primary), ("radau", radau), ("dop853", dop))
           for j in range(2)}
    doc = _header(spec, "C2", {
        "V_C_pL": W.V_C, "sites": {"copies": W.sites.copies,
                                    "sites_per_copy": W.sites.sites_per_copy,
                                    "accessible_fraction": W.sites.accessible_fraction},
        "sites_per_fmol": spec.sites_per_fmol,
        "ligands": [{"id": g.id, "k_on_per_mM_per_s": g.k_on, "k_off_per_s": g.k_off,
                     "total_fmol": g.total} for g in W.ligands],
        "initial_bound_fmol": {f"B{j + 1}": b for j, b in enumerate(W.B0)},
        "horizon_s": W.horizon,
        "sample_times_rule": f"t_i = {W.samples.step} i, i = 0 ... {W.samples.last}"})
    doc["quantities"] = C2_QUANTITIES
    doc["sample_times_s"] = [str(t) for t in times]
    doc.update({name: [fmt(v) for v in primary[name]] for name in names})
    doc["once_units"] = C2_ONCE
    doc["once"] = {k: fmt(v) for k, v in once.items()}
    doc["checks"] = {"end_approaches_root": {
        "description": "|B_j(horizon) - B_j*| / B_j*, for each route's transient",
        "relative_gap": end}}
    within = (radau_worst <= ACCURACY["ode"] and dop_worst <= ACCURACY["ode"]
              and root_worst <= ACCURACY["thirty_digit"]
              and step_worst <= ACCURACY["thirty_digit"]
              and reported <= ACCURACY["thirty_digit"])
    doc["method"] = {
        "transient_primary": (f"LAWS.md 5's two binding equations integrated by their Taylor "
                              f"series in decimal arithmetic at {exact.TAYLOR_PREC} digits, "
                              f"fixed step {TAYLOR_STEP['C2']} s, each step's series summed "
                              f"until two terms fall below 1e-{exact.TAYLOR_PREC - 4} L_T. The "
                              f"same integrator matches World B's exact transient (B.json). "
                              f"The reported values are the primary's."),
        "root_primary": ("one equation in the free sites R: f(R) = R + R sum_j "
                         "L_T_j/(K_j V_C + R) - S = 0, solved by Newton from R = 0 at 70 digits; "
                         "then c_j* = L_T_j/(V_C + R*/K_j) and B_j* = L_T_j - V_C c_j*"),
        "reported_significant_digits": OUT_DIGITS,
        "second_routes": {
            "ode_radau": {
                "description": "scipy.integrate.solve_ivp, Radau, rtol 1e-12, atol 1e-30, on "
                               "(B1, B2, n1, n2, R), binary64, with its own S",
                "largest_relative_difference": radau_table, "max": fmt_q(radau_worst),
                "max_normalised_difference": _normalised(primary, radau, names),
                "declared_accuracy": fmt_q(ACCURACY["ode"], 1),
                "within": radau_worst <= ACCURACY["ode"]},
            "ode_dop853": {
                "description": "scipy.integrate.solve_ivp, DOP853, rtol 1e-13, atol 1e-30, on "
                               "(B1, B2, n1, n2, R), binary64, with its own S",
                "largest_relative_difference": dop_table, "max": fmt_q(dop_worst),
                "max_normalised_difference": _normalised(primary, dop, names),
                "declared_accuracy": fmt_q(ACCURACY["ode"], 1),
                "within": dop_worst <= ACCURACY["ode"]},
            "taylor_step_check": {
                "description": (f"the primary integrator again at step {TAYLOR_CHECK_STEP} s "
                                f"(the same method; a convergence check, not an independent "
                                f"route)"),
                "largest_relative_difference": step_table, "max": fmt_q(step_worst),
                "within": step_worst <= ACCURACY["thirty_digit"]},
            "root_two_equation_newton": {
                "description": ("Newton on LAWS.md 5's two equations in (c1, c2) as written, at "
                                "70 digits, from Radau's state at the horizon, with S in exact "
                                "rationals; R* = S/(1 + c1/K1 + c2/K2)"),
                "relative_difference": root_table,
                "largest_relative_difference": fmt_q(root_worst),
                "declared_accuracy": fmt_q(ACCURACY["thirty_digit"], 1),
                "within": root_worst <= ACCURACY["thirty_digit"]},
        },
        "reported_strings_against_second_route": fmt_q(reported),
        "difference_measure": "|A - B| / max(|A|, |B|) per sample, in exact rational arithmetic",
        "within_declared_accuracy": within,
    }
    return doc


# ---- Writing -------------------------------------------------------------------------------------

def write(spec: fr49_spec.Spec, out_dir: Path, worlds: list[str] | None = None) -> list[Path]:
    chosen = list(fr49_spec.WORLDS) if worlds is None else worlds
    unknown = [w for w in chosen if w not in fr49_spec.WORLDS]
    if unknown:
        raise ValueError("unknown world among " + ", ".join(unknown))
    prov = provenance()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"revision {prov['git_revision']}, dirty {prov['dirty_paths']}", flush=True)
    parts = world_L_parts(spec) if ("L" in chosen or "C1" in chosen) else None
    builders = {"L": lambda: build_L(spec, parts), "B": lambda: build_B(spec),
                "C1": lambda: build_C1(spec, parts), "C2": lambda: build_C2(spec)}
    written = []
    for world in fr49_spec.WORLDS:
        if world not in chosen:
            continue
        doc = builders[world]()
        doc["provenance"] = prov
        name = ("INVENTED_" if spec.invented else "") + f"{world}.json"
        path = out_dir / name
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
        written.append(path)
        print(f"{name}: within declared accuracy {doc['method']['within_declared_accuracy']}",
              flush=True)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--spec", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--format-sample", action="store_true")
    parser.add_argument("--worlds", nargs="*", default=None)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)
    if args.format_sample:
        if args.spec is not None or args.out is not None:
            parser.error("--format-sample takes neither --spec nor --out")
        spec_path, out_dir = SAMPLE_SPEC, SAMPLE_DIR
    else:
        spec_path = fr49_spec.CASES_JSON if args.spec is None else args.spec
        out_dir = RESULTS_DIR if args.out is None else args.out.resolve()
    spec = fr49_spec.load(spec_path)
    if args.format_sample and not spec.invented:
        parser.error("the format sample's spec must be marked invented")
    if out_dir == RESULTS_DIR and spec.invented:
        parser.error("results/ holds the registered worlds only")
    if out_dir in (RESULTS_DIR, SAMPLE_DIR):
        dirty = provenance()["dirty_paths"]
        if dirty and not args.allow_dirty:
            parser.error("dirty paths: " + ", ".join(dirty))
    else:
        root = repository_root()
        if root is not None and out_dir.is_relative_to(root):
            parser.error("--out must lie outside the repository")
    try:
        write(spec, out_dir, args.worlds)
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
