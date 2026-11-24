"""FR-50 code-blind reference (protocol fr50-one-way-records-v1): the generator and writer.

For each case of a spec file it evaluates route A (fr50_route_a: LAWS.md's forms in decimal
arithmetic at 120 digits) and route B (fr50_route_b: exact rationals with their own exp and ln, by
Ussing's ratio and the net), and for K2 also Radau (fr50_ode). It compares them, and writes
<case id>.json holding route A's values at 30 significant digits, the method with the largest
differences, and the provenance.

Usage:
    python fr50_reference.py                     the registered cases -> results/
    python fr50_reference.py --format-sample     format-sample/invented_cases.json -> format-sample/
    python fr50_reference.py --spec FILE --out DIR [--cases ID ...]   any spec file -> DIR

Writing results/ or format-sample/ is refused while the checkout has dirty paths, other than the
files this writer produces, unless --allow-dirty is given. Any other --out must lie outside the
repository. A spec file with "invented": true marks every output invented in its "inputs" block.
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

import fr50_ode as ode  # noqa: E402
import fr50_route_a as route_a  # noqa: E402
import fr50_route_b as route_b  # noqa: E402
import fr50_spec  # noqa: E402
import numpy  # noqa: E402
import scipy  # noqa: E402

HERE = Path(__file__).resolve().parent
PACKAGE = "validation/fr50/references"
RESULTS_DIR = HERE / "results"
SAMPLE_DIR = HERE / "format-sample"
SAMPLE_SPEC = SAMPLE_DIR / "invented_cases.json"
OUTPUT_PREFIXES = (f"{PACKAGE}/results/", f"{PACKAGE}/format-sample/INVENTED_")
OUT_DIGITS = 30
SPEC_TAG = "fr50-one-way-records-v1-registered-2026-11-23"
ACCURACY = {"closed_form": Fraction(1, 10**20), "ode": Fraction(1, 10**10)}

FORWARD = {
    "K1": "inward: the outside node to the cell (a neutral route on a patch)",
    "K2": "inward: the outside node to the cell (a neutral route on a patch)",
    "K3": "inward: the outside node to the cell (a constant-field route on a patch)",
    "K4": "forward cycles (the transporter)",
    "K4h": "forward cycles (the transporter)",
    "E1": "outward: the cell to the outside node (@3's membrane route)",
    "E2": "sender to receiver (a junction route)",
    "E3": "sender to receiver (an uncharged face)",
    "E4": "outward: the cell to the outside node (a channel population)",
    "E6": "outward: the cell to the outside node (a channel population)",
}
STEADY_ROUTES = ("K1", "E1", "E2", "E3", "E4")


def fmt(x, digits: int = OUT_DIGITS) -> str:
    """x as d.ddd...e+N with `digits` significant digits, half-even; an exact zero is "0"."""
    if not isinstance(x, Decimal):
        q = Fraction(x)
        x = route_a.context(digits + 10).divide(Decimal(q.numerator), Decimal(q.denominator))
    if x == 0:
        return "0"
    y = route_a.context(digits).plus(x)
    sign, ds, _ = y.as_tuple()
    ds = tuple(ds) + (0,) * (digits - len(ds))
    mantissa = f"{ds[0]}." + "".join(str(d) for d in ds[1:]) if digits > 1 else f"{ds[0]}"
    return f"{'-' if sign else ''}{mantissa}e{y.adjusted():+d}"


def fmt_q(q: Fraction, digits: int = 3) -> str:
    return fmt(q, digits)


def rel(a, b) -> Fraction:
    """|a - b| / max(|a|, |b|) in exact rationals; 0 when a == b (so exact zeros count 0)."""
    a, b = Fraction(a), Fraction(b)
    if a == b:
        return Fraction(0)
    return abs(a - b) / max(abs(a), abs(b))


def scaled(a, b, scale) -> Fraction:
    """|a - b| / |scale|: for a quantity near 0 by construction (a net), against its flux."""
    return abs(Fraction(a) - Fraction(b)) / abs(Fraction(scale))


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
        "generator": f"{PACKAGE}/fr50_reference.py",
    }


def inputs_block(spec: fr50_spec.Spec) -> dict:
    try:
        spec_file = f"{PACKAGE}/{spec.path.resolve().relative_to(HERE).as_posix()}"
    except ValueError:
        spec_file = spec.path.resolve().as_posix()
    if spec.invented:
        statement = ("INVENTED inputs, for a format sample only: this file shows the results "
                     "layout. No value in it is a reference value of any registered case.")
    else:
        statement = (f"The registered cases: {PACKAGE}/spec/cases.json, in a byte-identical "
                     f"copy of the tag {SPEC_TAG}.")
    return {"invented": spec.invented, "spec_file": spec_file, "statement": statement}


class Table:
    """The largest difference per quantity between route A and a second route."""

    def __init__(self):
        self.rows: dict = {}
        self.reported = Fraction(0)

    def add(self, name: str, a_values, b_values, measure=rel, scale=None) -> None:
        worst, where = Fraction(-1), None
        for i, (a, b) in enumerate(zip(a_values, b_values, strict=True)):
            d = measure(a, b) if scale is None else measure(a, b, scale)
            if d > worst:
                worst, where = d, i
            reported = rel(Decimal(fmt(a)), b) if scale is None else scaled(
                Decimal(fmt(a)), b, scale)
            self.reported = max(self.reported, reported)
        self.rows[name] = {"max": worst, "index": where}

    def worst(self) -> Fraction:
        return max((row["max"] for row in self.rows.values()), default=Fraction(0))

    def as_json(self) -> dict:
        return {name: {"max": fmt_q(row["max"]), "index": row["index"]}
                for name, row in self.rows.items()}


ROUTE_A_TEXT = ("LAWS.md's forms in Python's decimal arithmetic (libmpdec) at 120 significant "
                "digits, rounding half-even: the one-way fluxes of section 2's table with "
                "B(x) = x/(e^x - 1); the transporter of section 3 with dG_cyc/(R T) as the sum "
                "the law writes; u by section 4; K2 by section 5's closed form; each steady "
                "record as its flux times t. The reported values are route A's.")
ROUTE_B_TEXT = ("Exact rationals (fractions.Fraction) with the package's own binary exp and ln, "
                "intermediate results rounded to 640 significant bits; no decimal module. Each "
                "one-way flux from Ussing's ratio and the net: the net from the one-exponential "
                "GHK form, rho = backward/forward from Ussing's ratio, forward = net/(1 - rho). "
                "Exactly at zero net (rho = 1) that is 0/0, and the one-way fluxes come from their "
                "direct forms in exact rationals. The transporter's dG_cyc/(R T) from one "
                "logarithm of the exact product of its concentration ratios; u from "
                "K = exp(ln K(0) + a V_ref); E_K from its own ln, rounded to 50 digits by integer "
                "arithmetic; K2 by the Taylor series of its linear system's matrix exponential.")


def build(spec: fr50_spec.Spec, case: fr50_spec.Case) -> dict:
    kind = case.kind
    A = route_a.CaseA(spec, case)
    B = route_b.CaseB(spec, case)
    a, b = A.values, B.values
    doc: dict = {"kind": "cells.fr50_reference_result@1", "protocol": "fr50-one-way-records-v1",
                 "case_id": case.id, "case_kind": kind, "inputs": inputs_block(spec),
                 "declared": case.raw, "forward_direction": FORWARD[kind]}
    table = Table()
    extra_routes: dict = {}
    checks: dict = {}
    if kind in ("E1", "E4", "E6"):
        if Fraction(A.E_K) != B.E_K:
            raise AssertionError(f"{case.id}: the routes' 50-digit E_K differ")
        doc["E_K_V"] = str(A.E_K)
        checks["E_K_50_digit_strings_equal"] = True
        checks["E_K_unrounded_relative_difference"] = fmt_q(rel(A.E_full, B.E_full))
    if kind in STEADY_ROUTES:
        ts = route_a.times(case.record_times)
        if kind in ("E1", "E4"):
            doc["V_V"] = str(A.E_K)
        if kind == "E4":
            doc["u"] = fmt(a["u"])
            table.add("u", [a["u"]], [b["u"]])
        doc["prefactor_pL_per_s"] = fmt(a["g"])
        doc["forward_fmol_per_s"] = fmt(a["forward"])
        doc["backward_fmol_per_s"] = fmt(a["backward"])
        doc["net_fmol_per_s"] = fmt(a["net"])
        doc["record_times_s"] = [str(t) for t in ts]
        doc["F_fmol"] = [fmt(v) for v in a["F"]]
        doc["B_fmol"] = [fmt(v) for v in a["B"]]
        table.add("prefactor_pL_per_s", [a["g"]], [b["g"]])
        table.add("forward_fmol_per_s", [a["forward"]], [b["forward"]])
        table.add("backward_fmol_per_s", [a["backward"]], [b["backward"]])
        table.add("net_fmol_per_s, against the forward flux", [a["net"]], [b["net"]],
                  scaled, a["forward"])
        table.add("F_fmol", a["F"], b["F"])
        table.add("B_fmol", a["B"], b["B"])
        checks["ussing_ratio_backward_over_forward"] = fmt(b["rho"])
        checks["ussing_ratio_minus_1"] = fmt(b["rho"] - 1)
        checks["second_route"] = _second_route_text(b["route"])
    elif kind in ("K4", "K4h"):
        doc["dG_cyc_over_RT"] = fmt(a["dG_cyc_over_RT"])
        doc["S"] = fmt(a["S"])
        doc["J_plus_fmol_cycles_per_s"] = fmt(a["J_plus"])
        doc["J_minus_fmol_cycles_per_s"] = fmt(a["J_minus"])
        table.add("dG_cyc_over_RT, absolute", [a["dG_cyc_over_RT"]], [b["dG_cyc_over_RT"]],
                  scaled, 1)
        table.add("S", [a["S"]], [b["S"]])
        table.add("J_plus_fmol_cycles_per_s", [a["J_plus"]], [b["J_plus"]])
        table.add("J_minus_fmol_cycles_per_s", [a["J_minus"]], [b["J_minus"]])
        if kind == "K4":
            ts = route_a.times(case.record_times)
            doc["net_fmol_cycles_per_s"] = fmt(a["net"])
            doc["record_times_s"] = [str(t) for t in ts]
            doc["F_fmol_cycles"] = [fmt(v) for v in a["F"]]
            doc["B_fmol_cycles"] = [fmt(v) for v in a["B"]]
            table.add("net_fmol_cycles_per_s, against J_plus", [a["net"]], [b["net"]], scaled,
                      a["J_plus"])
            table.add("F_fmol_cycles", a["F"], b["F"])
            table.add("B_fmol_cycles", a["B"], b["B"])
        else:
            doc["J_minus_over_J_plus"] = fmt(a["J_minus_over_J_plus"])
            table.add("J_minus_over_J_plus", [a["J_minus_over_J_plus"]],
                      [b["J_minus_over_J_plus"]])
        checks["dG_cyc_over_RT_by_second_route"] = fmt(b["dG_cyc_over_RT"])
        checks["ussing_ratio_J_minus_over_J_plus"] = fmt(b["rho"])
        checks["second_route"] = _second_route_text(b["route"])
    elif kind == "K2":
        ts = route_a.times(case.record_times)
        doc["a_pL_per_s"] = fmt(a["a"])
        doc["k_per_s"] = fmt(a["k"])
        doc["c_bar_mM"] = fmt(a["c_bar"])
        doc["record_times_s"] = [str(t) for t in ts]
        names = (("c_cell", "c_cell_mM"), ("c_node", "c_node_mM"), ("F", "F_fmol"),
                 ("B", "B_fmol"))
        for key, name in names:
            doc[name] = [fmt(v) for v in a[key]]
            table.add(name, a[key], b[key])
        radau = ode.relaxation_radau(case)
        radau_table = Table()
        for key, name in names:
            radau_table.add(name, a[key], radau[key])
        extra_routes["ode_radau"] = {
            "description": ("scipy.integrate.solve_ivp, Radau, rtol 1e-12, atol 1e-30, on "
                            "(n_O, n_N, F, B), binary64"),
            "largest_relative_difference": radau_table.as_json(),
            "max": fmt_q(radau_table.worst()),
            "declared_accuracy": fmt_q(ACCURACY["ode"], 1),
            "within": radau_table.worst() <= ACCURACY["ode"]}
    elif kind in ("K3", "E6"):
        evaluations = []
        fields = ["forward", "backward", "ratio_inward_over_outward",
                  "ratio_backward_over_forward"]
        if kind == "E6":
            fields = ["u", *fields, "difference"]
        names = {"forward": "forward_fmol_per_s", "backward": "backward_fmol_per_s",
                 "difference": "difference_forward_minus_backward_fmol_per_s"}
        for ea, eb in zip(A.evaluations, B.evaluations, strict=True):
            if Fraction(ea["V"]) != eb["V"]:
                raise AssertionError(f"{case.id}: the routes' voltages differ")
            row = {"V_V": str(ea["V"])}
            if kind == "E6":
                row["availability"] = ea["availability"]
                row["V_ref_V"] = str(ea["V_ref"])
            for field in fields:
                row[names.get(field, field)] = fmt(ea[field])
            evaluations.append(row)
        for field in fields:
            table.add(names.get(field, field), [e[field] for e in A.evaluations],
                      [e[field] for e in B.evaluations])
        doc["evaluations"] = evaluations
    if checks:
        doc["checks"] = checks
    worst = table.worst()
    within = worst <= ACCURACY["closed_form"] and table.reported <= ACCURACY["closed_form"]
    for route in extra_routes.values():
        within = within and route["within"]
    doc["method"] = {
        "route_A": ROUTE_A_TEXT,
        "route_A_working_precision_digits": route_a.PREC,
        "reported_significant_digits": OUT_DIGITS,
        "route_B": ROUTE_B_TEXT,
        "largest_relative_difference": table.as_json(),
        "max": fmt_q(worst),
        "declared_accuracy": fmt_q(ACCURACY["closed_form"], 1),
        "reported_strings_against_route_B": fmt_q(table.reported),
        "difference_measure": ("|A - B| / max(|A|, |B|), in exact rationals; 0 when both are "
                               "equal. A net, which is 0 at these states by construction, is "
                               "measured against its forward flux, and dG_cyc/(R T) absolutely."),
        "other_routes": extra_routes,
        "within_declared_accuracy": within,
    }
    return doc


def _second_route_text(route: str) -> str:
    if route == "ussing_and_net":
        return "Ussing's ratio and the net: forward = net/(1 - rho), backward = rho forward"
    return ("direct one-way forms in exact rationals: the state is exactly at zero net "
            "(rho = 1), where Ussing's recomputation from the net is 0/0")


def write(spec: fr50_spec.Spec, out_dir: Path, case_ids: list[str] | None = None) -> list[Path]:
    cases = [c for c in spec.cases if case_ids is None or c.id in case_ids]
    if case_ids is not None and len(cases) != len(case_ids):
        raise ValueError("unknown case id among " + ", ".join(case_ids))
    prov = provenance()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"revision {prov['git_revision']}, dirty {prov['dirty_paths']}", flush=True)
    written = []
    for case in cases:
        doc = build(spec, case)
        doc["provenance"] = prov
        path = out_dir / f"{case.id}.json"
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
        written.append(path)
        print(f"{case.id}: max {doc['method']['max']}, within "
              f"{doc['method']['within_declared_accuracy']}", flush=True)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--spec", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--format-sample", action="store_true")
    parser.add_argument("--cases", nargs="*", default=None)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)
    if args.format_sample:
        if args.spec is not None or args.out is not None:
            parser.error("--format-sample takes neither --spec nor --out")
        spec_path, out_dir = SAMPLE_SPEC, SAMPLE_DIR
    else:
        spec_path = fr50_spec.CASES_JSON if args.spec is None else args.spec
        out_dir = RESULTS_DIR if args.out is None else args.out.resolve()
    spec = fr50_spec.load(spec_path)
    if args.format_sample and not spec.invented:
        parser.error("the format sample's spec must be marked invented")
    if out_dir == RESULTS_DIR and spec.invented:
        parser.error("results/ holds the registered cases only")
    if out_dir in (RESULTS_DIR, SAMPLE_DIR):
        dirty = provenance()["dirty_paths"]
        if dirty and not args.allow_dirty:
            parser.error("dirty paths: " + ", ".join(dirty))
    else:
        root = repository_root()
        if root is not None and out_dir.is_relative_to(root):
            parser.error("--out must lie outside the repository")
    try:
        write(spec, out_dir, args.cases)
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
