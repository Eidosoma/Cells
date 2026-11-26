"""FR-51's judge: the engine against the code-blind references, by fr51-channel-block-v1's criteria.

This file is the registration's addendum (D308): its reader exists and is tagged before it reads any
reference. The criteria are REGISTRATION.md §3's, as written there. The reader takes the references'
results layout (`cells.fr51_reference_result@1`, one file per case in results/) and checks its
structure: the case's ID, its voltages and their index, and every array, numeric and of the right
length.

The engine's values are not computed here. They come from a function named at run time
(`--engine MODULE:FUNCTION`), written with the engine's build. It is called as
engine(case_id, voltages_V) and returns a mapping of arrays over those voltages (§2 of the
registration):
- I_free and I_blocked (A), and u;
- slope_part [mode, voltage]: theta (1 - theta), for criterion S;
- T_V (S), the per-stage channel term;
- T_co and T_ci (fmol/s per mM), the per-stage concentration terms, for the reversal reference.

Usage:
  python -m validation.fr51.judge --check-reader DIR --cases CASES_JSON --out OUT
      the reader on DIR's files (a format sample, or results/), structure only, values unread;
  python -m validation.fr51.judge --references DIR --engine MODULE:FUNCTION --out OUT
      the judged comparison against the tagged references, after the reader's tag.
"""

import argparse
import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

KIND = "cells.fr51_reference_result@1"
PROTOCOL = "fr51-channel-block-v1"
SPEC = Path(__file__).resolve().parent / "references" / "spec" / "cases.json"
FREE = ("J_free_fmol_s", "I_free_A", "dI_free_dV_S", "u")
BLOCKED = (
    "V_ref_V",
    "J_blocked_fmol_s",
    "I_blocked_A",
    "dI_blocked_dV_S",
    "dJ_blocked_dc_o_fmol_s_per_mM",
    "dJ_blocked_dc_i_fmol_s_per_mM",
)
PER_MODE = ("theta_k", "one_minus_theta_k")
EXTRAS = ("E_ion", "E_ion_minus_0.0005_V", "E_ion_plus_0.0005_V")
GRID_COUNT = 361
# The bands of REGISTRATION.md §3, fixed before any reference value was seen.
REL = 1e-12  # P, B, R, S, G, E.
FLOOR = 1e-15  # P: times the case's largest |I_r|.
AWAY = 1e-3  # V: B-ratio only where |V - E_ion| is at least this.


class ReaderError(ValueError):
    """A references file whose structure the reader refuses, naming what is wrong."""


@dataclass(frozen=True)
class ReferenceCase:
    case_id: str
    declared: dict
    blocked: bool
    modes: int
    voltages: np.ndarray  # [N], V, read from the reference's decimal strings.
    grid: slice  # The declared grid's voltages.
    extras: dict  # {extra name: index}.
    E_ion: float
    u_at_reversal: float
    q: dict = field(default_factory=dict)  # {name: [N] or [mode, N]}, float64.
    within_declared_accuracy: bool = False


def _floats(values, what):
    try:
        return np.asarray([float(x) for x in values], dtype=float)
    except (TypeError, ValueError) as error:
        raise ReaderError(f"{what} is not a list of numbers: {error}") from None


def read_case(path, spec_case=None, spec_blocks=None):
    """One case's results file. With its spec case (cases.json's entry) and the spec's blocks, the
    case's ID, its block and its mode count are checked against them as well."""
    try:
        doc = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ReaderError(f"{path}: not readable JSON: {error}") from None
    if not isinstance(doc, dict):
        raise ReaderError(f"{path}: not a JSON object")
    for key, expected in (("kind", KIND), ("protocol", PROTOCOL)):
        if doc.get(key) != expected:
            raise ReaderError(f"{path}: {key} is {doc.get(key)!r}, not {expected!r}")
    case_id = doc.get("case_id")
    if spec_case is not None and case_id != spec_case["id"]:
        raise ReaderError(f"{path}: case_id {case_id!r}, not the spec's {spec_case['id']!r}")
    declared = doc.get("declared")
    if not isinstance(declared, dict):
        raise ReaderError(f"{path}: no declared object")
    block = declared.get("block")
    if spec_case is not None and block != spec_case["block"]:
        raise ReaderError(
            f"{path}: declared block {block!r}, not the spec's {spec_case['block']!r}"
        )
    voltages = _floats(doc.get("voltages_V", ()), f"{path}: voltages_V")
    n = voltages.size
    if doc.get("voltage_count") != n or n != GRID_COUNT + len(EXTRAS):
        raise ReaderError(
            f"{path}: {n} voltages, voltage_count {doc.get('voltage_count')!r}; the spec asks for "
            f"{GRID_COUNT} grid voltages and {len(EXTRAS)} extras"
        )
    index = doc.get("voltage_index")
    if not isinstance(index, dict) or index.get("grid") != [0, GRID_COUNT - 1]:
        raise ReaderError(f"{path}: voltage_index.grid is not [0, {GRID_COUNT - 1}]")
    extras = {}
    for name in EXTRAS:
        at = index.get(name)
        if type(at) is not int or not GRID_COUNT <= at < n:
            raise ReaderError(f"{path}: voltage_index has no extra {name!r} past the grid")
        extras[name] = at
    q = {}
    for name in FREE:
        if name not in doc:
            raise ReaderError(f"{path}: {name} is missing")
        q[name] = _floats(doc[name], f"{path}: {name}")
    blocked = block is not None
    modes = 0
    if blocked:
        for name in BLOCKED:
            if name not in doc:
                raise ReaderError(f"{path}: {name} is missing for a blocked case")
            q[name] = _floats(doc[name], f"{path}: {name}")
        for name in PER_MODE:
            rows = doc.get(name)
            if not isinstance(rows, list) or not rows:
                raise ReaderError(f"{path}: {name} is not a list of modes")
            q[name] = np.stack([_floats(r, f"{path}: {name}[{k}]") for k, r in enumerate(rows)])
        modes = q["theta_k"].shape[0]
        if q["one_minus_theta_k"].shape != q["theta_k"].shape:
            raise ReaderError(f"{path}: theta_k and one_minus_theta_k differ in shape")
        if spec_blocks is not None and modes != len(spec_blocks[block]["modes"]):
            raise ReaderError(f"{path}: {modes} modes; the spec's block has "
                              f"{len(spec_blocks[block]['modes'])}")  # fmt: skip
    for name, values in q.items():
        if values.shape[-1] != n:
            raise ReaderError(f"{path}: {name} has {values.shape[-1]} values for {n} voltages")
    method = doc.get("method")
    if not isinstance(method, dict) or not isinstance(method.get("within_declared_accuracy"), bool):
        raise ReaderError(f"{path}: method.within_declared_accuracy is not a boolean")
    return ReferenceCase(
        case_id=case_id,
        declared=declared,
        blocked=blocked,
        modes=modes,
        voltages=voltages,
        grid=slice(0, GRID_COUNT),
        extras=extras,
        E_ion=float(doc["E_ion_V"]),
        u_at_reversal=float(doc["u_at_reversal"]),
        q=q,
        within_declared_accuracy=method["within_declared_accuracy"],
    )


def read_results(directory, cases_json=SPEC):
    """{case ID: ReferenceCase} for every case of the spec, each from DIRECTORY/<case ID>.json."""
    spec = json.loads(Path(cases_json).read_text())
    out = {}
    for case in spec["cases"]:
        out[case["id"]] = read_case(
            Path(directory) / f"{case['id']}.json", spec_case=case, spec_blocks=spec["blocks"]
        )
    return out


# ------------------------------------------------------------------ the comparisons (§3)


def within(engine, reference, rel=REL, floor=0.0):
    """|engine - reference| <= rel |reference| + floor, elementwise: (all, largest excess ratio)."""
    engine, reference = np.asarray(engine, float), np.asarray(reference, float)
    bound = rel * np.abs(reference) + floor
    excess = np.abs(engine - reference) / np.where(bound > 0, bound, np.inf)
    exact = (bound == 0) & (engine == reference)
    ok = (np.abs(engine - reference) <= bound) | exact
    return bool(np.all(ok)), float(np.max(np.where(exact, 0.0, excess), initial=0.0))


def at_least(term, magnitude, rel=REL):
    """term >= |magnitude| (1 - rel), elementwise: (all, the smallest term / |magnitude|)."""
    term, magnitude = np.asarray(term, float), np.abs(np.asarray(magnitude, float))
    ratio = np.where(magnitude > 0, term / np.where(magnitude > 0, magnitude, 1.0), np.inf)
    return bool(np.all(term >= magnitude * (1 - rel))), float(np.min(ratio, initial=np.inf))


def check_p(e, ref):
    """P1–P4: I_free against GHK, with the floor for cancellation at reversal."""
    r = ref.q["I_free_A"]
    return within(e["I_free"], r, floor=FLOOR * float(np.max(np.abs(r))))


def check_b_u(e, ref):
    """B-u: u at every voltage, the extras included."""
    return within(e["u"], ref.q["u"])


def check_b_ratio(e, ref):
    """B-ratio: the blocked-to-free current ratio, only where |V - E_ion| >= 1 mV."""
    away = np.abs(ref.voltages - ref.E_ion) >= AWAY
    ratio = np.asarray(e["I_blocked"], float)[away] / np.asarray(e["I_free"], float)[away]
    return within(ratio, ref.q["u"][away])


def check_r(e, ref):
    """R: the fraction read directly at V = E_ion, against u_at_reversal."""
    at = ref.extras["E_ion"]
    return within(np.asarray(e["u"], float)[at], ref.u_at_reversal)


def check_s(e, ref):
    """S: u and each mode's theta (1 - theta), relatively, on the compiled program."""
    ok_u, worst_u = within(e["u"], ref.q["u"])
    part = ref.q["theta_k"] * ref.q["one_minus_theta_k"]
    ok_p, worst_p = within(e["slope_part"], part)
    return ok_u and ok_p, max(worst_u, worst_p)


def check_g(e, ref):
    """G: the per-stage channel term at least |dI_blocked/dV|."""
    return at_least(e["T_V"], ref.q["dI_blocked_dV_S"])


def check_e(e, ref):
    """E: the per-stage concentration terms at least |dJ_blocked/dc| at each end."""
    ok_o, worst_o = at_least(e["T_co"], ref.q["dJ_blocked_dc_o_fmol_s_per_mM"])
    ok_i, worst_i = at_least(e["T_ci"], ref.q["dJ_blocked_dc_i_fmol_s_per_mM"])
    return ok_o and ok_i, min(worst_o, worst_i)


# The registered cases of each criterion (REGISTRATION.md §3).
CHECKS = {
    "P": (check_p, ("P1_K_equal", "P2_K_unequal", "P3_Na_unequal", "P4_Cl_unequal")),
    "B-u": (check_b_u, ("B1_two_modes_E1", "B1_two_modes_E2", "B2_woodhull_inside",
                        "B3_divalent_outside_E1", "B3_divalent_outside_E2", "B4_anion_effective",
                        "B5_effective_valence_5", "G1_steep_K_inside_reversal",
                        "G2_steep_K_outside_voltage", "G3_steep_Na_outside_voltage",
                        "G4_steep_Na_inside_reversal", "G5_steep_Cl_anion_outside",
                        "S1_strong_one_mode", "S2_strong_two_modes", "Z1_zero_blocker",
                        "C1_abundance_doubled", "C2_units_declared", "C2_units_doubled")),
    "B-ratio": (check_b_ratio, ("B1_two_modes_E1", "B1_two_modes_E2", "B2_woodhull_inside",
                                "B3_divalent_outside_E1", "B3_divalent_outside_E2",
                                "B4_anion_effective", "B5_effective_valence_5")),
    "R": (check_r, ("B1_two_modes_E1", "B1_two_modes_E2", "B2_woodhull_inside",
                    "B3_divalent_outside_E1", "B3_divalent_outside_E2", "B4_anion_effective",
                    "B5_effective_valence_5", "Z1_zero_blocker")),
    "S": (check_s, ("S1_strong_one_mode", "S2_strong_two_modes")),
    "G": (check_g, ("B1_two_modes_E1", "B1_two_modes_E2", "B2_woodhull_inside",
                    "B3_divalent_outside_E1", "B3_divalent_outside_E2", "B4_anion_effective",
                    "B5_effective_valence_5", "G1_steep_K_inside_reversal",
                    "G2_steep_K_outside_voltage", "G3_steep_Na_outside_voltage",
                    "G4_steep_Na_inside_reversal", "G5_steep_Cl_anion_outside")),
    "E": (check_e, ("B1_two_modes_E1", "B1_two_modes_E2", "B5_effective_valence_5",
                    "G1_steep_K_inside_reversal", "G4_steep_Na_inside_reversal",
                    "Z1_zero_blocker", "C1_abundance_doubled", "C2_units_declared")),
}  # fmt: skip


def judge(references, engine):
    """{criterion: {case: {passed, worst, inconclusive}}}. A case whose reference reports a
    cross-check outside its declared accuracy is inconclusive, not a pass (§0)."""
    out = {}
    for name, (check, cases) in CHECKS.items():
        out[name] = {}
        for case_id in cases:
            ref = references[case_id]
            values = engine(case_id, ref.voltages)
            passed, worst = check(values, ref)
            out[name][case_id] = dict(
                passed=passed, worst=worst, inconclusive=not ref.within_declared_accuracy
            )
    return out


def _engine(spec):
    module, _, name = spec.partition(":")
    return getattr(importlib.import_module(module), name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--check-reader", type=Path, default=None)
    parser.add_argument("--cases", type=Path, default=SPEC)
    parser.add_argument("--references", type=Path, default=None)
    parser.add_argument("--engine", default=None, help="MODULE:FUNCTION")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.check_reader is not None:  # D308: the reader on a format sample, values unread.
        spec = json.loads(args.cases.read_text())
        report = {}
        for case in spec["cases"]:
            path = args.check_reader / f"{case['id']}.json"
            try:
                ref = read_case(path, spec_case=case, spec_blocks=spec["blocks"])
                report[case["id"]] = dict(parsed=True, voltages=int(ref.voltages.size),
                                          blocked=ref.blocked, modes=ref.modes,
                                          arrays=sorted(ref.q))  # fmt: skip
            except ReaderError as error:
                report[case["id"]] = dict(parsed=False, why=str(error))
        (args.out / "reader_check.json").write_text(json.dumps(report, indent=1))
        print(json.dumps({k: v["parsed"] for k, v in report.items()}))
        return 0 if all(v["parsed"] for v in report.values()) else 1
    if args.references is None or args.engine is None:
        parser.error("--references and --engine, or --check-reader")
    verdict = judge(read_results(args.references, args.cases), _engine(args.engine))
    (args.out / "verdict.json").write_text(json.dumps(verdict, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
