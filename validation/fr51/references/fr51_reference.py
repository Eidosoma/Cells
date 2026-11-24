"""FR-51 code-blind reference (protocol fr51-channel-block-v1): the generator and writer.

For every case of a spec file it evaluates route A (fr51_route_a: the closed forms of
spec/LAWS.md in decimal arithmetic at 120 digits) and route B (fr51_route_b: exact rationals with
their own exp and ln, the alternative algebra, and central differences for every slope). It
compares the two in exact rational arithmetic, and writes <case id>.json holding route A's values
at 30 significant digits, the method with the largest differences, and the provenance.

Usage:
    python fr51_reference.py                     the registered cases -> results/
    python fr51_reference.py --format-sample     format-sample/invented_cases.json -> format-sample/
    python fr51_reference.py --spec FILE --out DIR [--cases ID ...]   any spec file -> DIR

Writing results/ or format-sample/ is refused while the checkout has dirty paths, other than the
files this writer produces, unless --allow-dirty is given. Any other --out must lie outside the
repository. A spec file with "invented": true (such as format-sample/invented_cases.json) marks
every output it produces as invented, in the output's own "inputs" block. No BLAS or NumPy is
used; the thread variables are pinned anyway.
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

import fr51_route_a as route_a  # noqa: E402
import fr51_route_b as route_b  # noqa: E402
import fr51_spec  # noqa: E402

HERE = Path(__file__).resolve().parent
PACKAGE = "validation/fr51/references"
RESULTS_DIR = HERE / "results"
SAMPLE_DIR = HERE / "format-sample"
SAMPLE_SPEC = SAMPLE_DIR / "invented_cases.json"
# Files this writer produces, left out of the dirty-path listing (repository-relative prefixes)
OUTPUT_PREFIXES = (f"{PACKAGE}/results/", f"{PACKAGE}/format-sample/INVENTED_")
OUT_DIGITS = 30
SPEC_TAG = "fr51-channel-block-v1-registered-2026-11-23"

# internal name -> output name (cases.json requested_outputs)
NAMES = {
    "V_ref": "V_ref_V",
    "J_free": "J_free_fmol_s",
    "I_free": "I_free_A",
    "dI_free_dV": "dI_free_dV_S",
    "theta": "theta_k",
    "one_minus_theta": "one_minus_theta_k",
    "u": "u",
    "J_blocked": "J_blocked_fmol_s",
    "I_blocked": "I_blocked_A",
    "dI_blocked_dV": "dI_blocked_dV_S",
    "dJ_blocked_dc_o": "dJ_blocked_dc_o_fmol_s_per_mM",
    "dJ_blocked_dc_i": "dJ_blocked_dc_i_fmol_s_per_mM",
}
FREE_KEYS = ["J_free", "I_free", "dI_free_dV"]
BLOCK_KEYS = ["V_ref", "theta", "one_minus_theta", "u", "J_blocked", "I_blocked",
              "dI_blocked_dV", "dJ_blocked_dc_o", "dJ_blocked_dc_i"]
U_AND_CURRENTS = ["u", "theta", "one_minus_theta", "J_free", "I_free", "J_blocked", "I_blocked"]
SLOPES = ["dI_free_dV", "dI_blocked_dV", "dJ_blocked_dc_o", "dJ_blocked_dc_i"]
PER_MODE = ("theta", "one_minus_theta")
DECLARED_ACCURACY = {"u_and_currents": Fraction(1, 10**20), "slopes": Fraction(1, 10**15)}


def fmt(x: Decimal, digits: int = OUT_DIGITS) -> str:
    """x as d.ddd...e+N with `digits` significant digits, half-even; an exact zero is "0"."""
    if x == 0:
        return "0"
    y = route_a.context(digits).plus(x)
    sign, ds, _ = y.as_tuple()
    ds = tuple(ds) + (0,) * (digits - len(ds))
    mantissa = f"{ds[0]}." + "".join(str(d) for d in ds[1:]) if digits > 1 else f"{ds[0]}"
    return f"{'-' if sign else ''}{mantissa}e{y.adjusted():+d}"


def fmt_q(q: Fraction, digits: int = 3) -> str:
    """A rational (a difference or a ratio) at `digits` significant digits."""
    if q == 0:
        return "0"
    return fmt(route_a.context(digits).divide(Decimal(q.numerator), Decimal(q.denominator)),
               digits)


def exact(x: Decimal) -> str:
    """An exact decimal written exactly and briefly (a declared or derived exact value)."""
    return "0" if x == 0 else str(x.normalize(route_a.context()))


def rel(a: Fraction, b: Fraction) -> Fraction:
    """|a - b| / max(|a|, |b|); 0 when a == b, so an exact zero in both routes counts 0."""
    if a == b:
        return Fraction(0)
    return abs(a - b) / max(abs(a), abs(b))


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
    """The git revision, the dirty paths (other than this writer's outputs), and the Python
    version."""
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
                n += 1  # the rename's source path follows
            if not path.startswith(OUTPUT_PREFIXES):
                dirty.append(path)
    return {
        "git_revision": revision.strip() if revision else None,
        "dirty_paths": sorted(dirty),
        "dirty_paths_exclude": [f"{prefix}*" for prefix in OUTPUT_PREFIXES],
        "python": sys.version,
        "libmpdec": decimal.__libmpdec_version__,
        "generator": f"{PACKAGE}/fr51_reference.py",
    }


def inputs_block(spec: fr51_spec.Spec) -> dict:
    """The same fields for every output; an invented spec marks the output invented."""
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


def _pairs(key: str, a_out: dict, b_out: dict):
    """(mode or None, voltage index, route A value, route B value) for one quantity."""
    if key in PER_MODE:
        for k, (la, lb) in enumerate(zip(a_out[key], b_out[key], strict=True)):
            for j, (va, vb) in enumerate(zip(la, lb, strict=True)):
                yield k, j, va, vb
    else:
        for j, (va, vb) in enumerate(zip(a_out[key], b_out[key], strict=True)):
            yield None, j, va, vb


def _compare(keys: list[str], a_out: dict, b_out: dict, reported: bool) -> dict:
    """The largest relative difference per quantity, with where it occurs (the first maximum)."""
    table = {}
    for key in keys:
        worst, where = Fraction(-1), None
        for k, j, va, vb in _pairs(key, a_out, b_out):
            a = Fraction(Decimal(fmt(va))) if reported else Fraction(va)
            d = rel(a, vb)
            if d > worst:
                worst, where = d, (k, j)
        table[key] = (worst, where)
    return table


def _group_max(table: dict, group: list[str]) -> tuple[Fraction, str | None]:
    best, name = Fraction(-1), None
    for key in group:
        if key in table and table[key][0] > best:
            best, name = table[key][0], key
    return best, name


def _sign(x: Decimal) -> int:
    return (x > 0) - (x < 0)


def value_arrays(A: route_a.CaseA, a_out: dict) -> dict:
    """Route A's values as the requested output arrays, under their output names."""
    keys = FREE_KEYS + (BLOCK_KEYS if A.block is not None else [])
    arrays = {}
    for key in keys:
        if key == "V_ref":
            arrays[NAMES[key]] = [str(v) if v != 0 else "0" for v in a_out[key]]
        elif key in PER_MODE:
            arrays[NAMES[key]] = [[fmt(v) for v in mode] for mode in a_out[key]]
        else:
            arrays[NAMES[key]] = [fmt(v) for v in a_out[key]]
    if A.block is None:
        arrays["u"] = [fmt(route_a.ONE)] * len(A.voltages)
    return arrays


def build_case(spec: fr51_spec.Spec, case: fr51_spec.Case, prov: dict) -> dict:
    A = route_a.CaseA(spec, case)
    a_out = A.evaluate()
    B = route_b.CaseB(spec, case)
    b_out = B.evaluate()

    # The two routes form the same voltages, the same E_ion string, and the same V_ref.
    if [Fraction(v) for v in A.voltages] != B.voltages:
        raise AssertionError(f"{case.id}: the routes' voltage lists differ")
    if Fraction(A.E_ion) != B.E_ion:
        raise AssertionError(f"{case.id}: the routes' 50-digit E_ion differ")
    keys = FREE_KEYS + (BLOCK_KEYS if case.block is not None else [])
    compared = [k for k in keys if k != "V_ref"]
    route_table = _compare(compared, a_out, b_out, reported=False)
    reported_table = _compare(compared, a_out, b_out, reported=True)
    v_ref_abs = Fraction(0)
    if case.block is not None:
        for va, vb in zip(a_out["V_ref"], b_out["V_ref"], strict=True):
            v_ref_abs = max(v_ref_abs, abs(Fraction(va) - vb))

    n_grid = spec.grid_count
    i_E = n_grid
    doc: dict = {
        "kind": "cells.fr51_reference_result@1",
        "protocol": "fr51-channel-block-v1",
        "case_id": case.id,
        "inputs": inputs_block(spec),
        "declared": {
            "population": case.population,
            "ion": case.ion,
            "valence": case.z,
            "c_i_mM": case.c_i_mM,
            "c_o_mM": case.c_o_mM,
            "T_K": spec.T_K,
            "area_m2": case.area_m2,
            "permeability_m_per_s": case.permeability_m_per_s,
            "relative_permeability": case.relative_permeability,
            "open_fraction": case.open_fraction,
            "availability": case.availability,
            "abundance": exact(A.abundance),
            "abundance_from": ("units: N/(A rho_ref)" if case.abundance_from == "units"
                               else case.abundance_from),
            "units": (None if case.units_count is None else
                      {"count": case.units_count,
                       "reference_density_per_m2": case.reference_density_per_m2}),
            "block": None if case.block is None else case.block.name,
        },
        "E_ion_V": str(A.E_ion),
        "u_at_reversal": (fmt(a_out["u"][i_E]) if case.block is not None
                          else fmt(route_a.ONE)),
        "voltage_count": len(A.voltages),
        "voltage_index": {"grid": [0, n_grid - 1], "E_ion": i_E,
                          "E_ion_minus_0.0005_V": i_E + 1, "E_ion_plus_0.0005_V": i_E + 2},
        "voltages_V": [str(v) for v in A.voltages],
    }
    if case.block is not None:
        doc["per_mode_layout"] = ("theta_k[k][j] and one_minus_theta_k[k][j]: mode k in the "
                                  "block's declared order (from 0), voltage j")
    doc.update(value_arrays(A, a_out))

    # LAWS.md 2: the two properties the criteria use
    J = a_out["J_free"]
    largest = max(abs(v) for v in J)
    props: dict = {"reversal": {
        "E_ion_V": str(A.E_ion),
        "J_free_at_E_ion_fmol_s": fmt(J[i_E]),
        "abs_J_free_at_E_ion_over_max_abs_J_free": fmt_q(Fraction(abs(J[i_E])) / Fraction(largest)),
        "sign_of_J_free_at_E_ion_minus_0.0005_V": _sign(J[i_E + 1]),
        "sign_of_J_free_at_E_ion_plus_0.0005_V": _sign(J[i_E + 2]),
    }}
    if Decimal(case.c_i_mM) == Decimal(case.c_o_mM):
        with decimal.localcontext(route_a.context()):
            G = route_a.FMOL_TO_MOL * A.F * A.z * A.z * A.q * A.pref * A.c_i
            deviation = Fraction(0)
            zero_at_zero = True
            for V, current in zip(A.voltages, a_out["I_free"], strict=True):
                if V == 0:
                    zero_at_zero = zero_at_zero and current == 0
                    continue
                deviation = max(deviation, rel(Fraction(current), Fraction(G * V)))
        props["linear_through_zero"] = {
            "G_lin_S": fmt(G),
            "law": "I = A P r a o v c z^2 F^2 V/(R T)",
            "max_relative_deviation_of_I_free_from_G_lin_V": fmt_q(deviation),
            "I_free_is_exactly_0_at_V_0": zero_at_zero,
        }
    doc["properties"] = props

    by_quantity = {}
    for key in compared:
        worst, (k, j) = route_table[key]
        entry = {"max": fmt_q(worst), "voltage_index": j}
        if k is not None:
            entry["mode"] = k
        by_quantity[NAMES[key]] = entry
    groups = {}
    within = True
    for group_name, group in (("u_and_currents", U_AND_CURRENTS), ("slopes", SLOPES)):
        worst, name = _group_max(route_table, group)
        rep_worst, rep_name = _group_max(reported_table, group)
        groups[group_name] = {
            "route_difference": fmt_q(worst), "route_difference_quantity": NAMES[name],
            "reported_strings_against_route_B": fmt_q(rep_worst),
            "reported_strings_quantity": NAMES[rep_name],
            "declared_accuracy": fmt_q(DECLARED_ACCURACY[group_name], 1),
        }
        within = within and rep_worst <= DECLARED_ACCURACY[group_name]
    doc["method"] = {
        "route_A": (
            "The closed forms of spec/LAWS.md sections 2-6 in Python's decimal arithmetic "
            "(libmpdec), rounding half-even: B(x) = x/(e^x - 1) with e^x - 1 at raised "
            "precision; each 1 - theta_k = K_k/(c_B + K_k) formed directly and "
            "u = sum_k w_k (1 - theta_k) / sum_k w_k, left to right in mode order; the slopes "
            "by the analytic forms of sections 2, 4 and 5. The reported values are route A's."),
        "route_A_working_precision_digits": route_a.PREC,
        "reported_significant_digits": OUT_DIGITS,
        "E_ion": (
            "The Nernst potential at 120 digits, rounded half-even to 50 significant digits. "
            "This 50-digit value is E_ion throughout: in the voltage list and in "
            "V_ref = V - E_ion, so V_ref is exactly 0 at V = E_ion. Route B recomputes it with "
            "its own ln and rounds it by integer arithmetic; the two agree exactly."),
        "route_B": (
            "Exact rational arithmetic (fractions.Fraction) with the package's own binary exp "
            "and ln, intermediate results rounded to 640 significant bits; no decimal module. "
            "The GHK flux in its classical form 1e15 A P r a o v x (c_i - c_o e^-x)/(1 - e^-x), "
            "with its own x = 0 limit; K_k = exp(ln K_k(0) + a_k V_ref); "
            "theta_k = 1/(1 + K_k/c_B), 1 - theta_k = 1/(1 + c_B/K_k); u by the literal "
            "1 - sum_k w_k theta_k / sum_k w_k; every slope by a central difference of route B's "
            "own values, step 1e-50 V, or 1e-50 times the concentration, with E recomputed "
            "unrounded from a perturbed concentration under the reversal reference."),
        "difference_measure": (
            "|A - B| / max(|A|, |B|), in exact rational arithmetic. A quantity that is exactly 0 "
            "in both routes counts 0 (the free flux and current at V = 0 when c_i = c_o; "
            "theta_k when c_B = 0). route_difference uses route A's 120-digit working values; "
            "reported_strings_against_route_B uses the 30-digit strings in this file."),
        "largest_relative_difference": groups,
        "by_quantity": by_quantity,
        "V_ref_largest_absolute_difference_V": fmt_q(v_ref_abs) if case.block else None,
        "E_ion_unrounded_relative_difference": fmt_q(rel(Fraction(A.E_full), B.E_full)),
        "E_ion_50_digit_strings_equal": True,
        "within_declared_accuracy": within,
    }
    doc["provenance"] = prov
    return doc


def write(spec: fr51_spec.Spec, out_dir: Path, case_ids: list[str] | None = None) -> list[Path]:
    """Evaluate and write every (or each named) case of `spec` into out_dir."""
    cases = [c for c in spec.cases if case_ids is None or c.id in case_ids]
    if case_ids is not None and len(cases) != len(case_ids):
        raise ValueError("unknown case id among " + ", ".join(case_ids))
    prov = provenance()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"revision {prov['git_revision']}, dirty {prov['dirty_paths']}", flush=True)
    written = []
    for case in cases:
        doc = build_case(spec, case, prov)
        path = out_dir / f"{case.id}.json"
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
        written.append(path)
        groups = doc["method"]["largest_relative_difference"]
        print(f"{case.id}: u/I route {groups['u_and_currents']['route_difference']}, "
              f"slopes route {groups['slopes']['route_difference']}, "
              f"within {doc['method']['within_declared_accuracy']}", flush=True)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--spec", type=Path, default=None,
                        help="spec file (default: spec/cases.json)")
    parser.add_argument("--out", type=Path, default=None,
                        help="output directory outside the repository (default: results/)")
    parser.add_argument("--format-sample", action="store_true",
                        help="write format-sample/ from format-sample/invented_cases.json")
    parser.add_argument("--cases", nargs="*", default=None, help="case ids (default: all)")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="write results/ or format-sample/ although the checkout is dirty")
    args = parser.parse_args(argv)
    if args.format_sample:
        if args.spec is not None or args.out is not None:
            parser.error("--format-sample takes neither --spec nor --out")
        spec_path, out_dir = SAMPLE_SPEC, SAMPLE_DIR
    else:
        spec_path = fr51_spec.CASES_JSON if args.spec is None else args.spec
        out_dir = RESULTS_DIR if args.out is None else args.out.resolve()
    spec = fr51_spec.load(spec_path)
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
