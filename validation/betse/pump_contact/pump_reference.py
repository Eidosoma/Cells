"""D107 positive-domain Na/K thermodynamics, independent of both model runtimes."""

import math
import sys
from decimal import Decimal, localcontext
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contact as c  # noqa: E402

FIELDS = (
    "na_in_mM",
    "na_out_mM",
    "k_in_mM",
    "k_out_mM",
    "atp_mM",
    "adp_mM",
    "pi_mM",
    "km_na_mM",
    "km_k_mM",
    "km_atp_mM",
    "temperature_K",
    "area_m2",
    "alpha_mol_m2_s",
    "availability",
    "voltage_V",
    "delta_g0_J_mol",
)
BASE = dict(
    zip(
        FIELDS,
        (
            12.0,
            140.0,
            140.0,
            4.0,
            1.5,
            0.1,
            0.1,
            12.0,
            0.2,
            0.5,
            298.15,
            1e-9,
            1e-7,
            1.0,
            -0.08,
            -37000.0,
        ),
        strict=True,
    )
)
CONSTANTS = {
    "source_constants": {"F": 96485.0, "R": 8.314},
    "matched_constants": {"F": 6.02214076e23 * 1.602176634e-19, "R": 6.02214076e23 * 1.380649e-23},
}
OUTPUTS = (
    "na_in_fmol_s",
    "k_in_fmol_s",
    "third_out_na_fmol_s",
    "cycles_density_mol_m2_s",
    "inward_current_A",
)
ABSOLUTE = dict(zip(OUTPUTS, (2e-12, 2e-12, 2e-12, 2e-18, 2e-22), strict=True))
RELATIVE = 2e-11
ENGINES = ("native", "numpy", "jax_eager", "jax_jit")


def validate_case(case, constants):
    c.require(set(case) == {"id", *FIELDS}, "Wrong pump case fields")
    c.require(isinstance(case["id"], str) and bool(case["id"]), "Wrong pump case id")
    c.require(set(constants) == {"F", "R"}, "Wrong constants")
    for name, value in {**{k: case[k] for k in FIELDS}, **constants}.items():
        c.require(type(value) in (int, float) and math.isfinite(value), f"Nonfinite {name}")
    for name in (*FIELDS[:12], "F", "R"):
        value = constants[name] if name in constants else case[name]
        c.require(value > 0, f"Nonpositive {name}")
    c.require(case["alpha_mol_m2_s"] >= 0, "Negative pump capacity")
    c.require(0 <= case["availability"] <= 1, "Invalid availability")
    c.require(200 <= case["temperature_K"] <= 400, "Temperature outside contact domain")


def thermodynamics(case, constants):
    """Decimal values; caller owns precision context. Positive concentrations only."""
    d = lambda key: Decimal(str(case[key]))  # noqa: E731
    f, r = (Decimal(str(constants[k])) for k in ("F", "R"))
    rt = r * d("temperature_K")
    chemical = d("delta_g0_J_mol") + rt * (d("adp_mM") * d("pi_mM") / (1000 * d("atp_mM"))).ln()
    mu_na = rt * (d("na_in_mM") / d("na_out_mM")).ln() + f * d("voltage_V")
    mu_k = rt * (d("k_in_mM") / d("k_out_mM")).ln() + f * d("voltage_V")
    affinity = chemical - 3 * mu_na + 2 * mu_k
    saturation = (
        d("na_in_mM") ** 3
        / (d("km_na_mM") ** 3 + d("na_in_mM") ** 3)
        * d("k_out_mM") ** 2
        / (d("km_k_mM") ** 2 + d("k_out_mM") ** 2)
        * d("atp_mM")
        / (d("km_atp_mM") + d("atp_mM"))
    )
    return affinity, chemical, saturation, rt


def oracle(case, constants):
    validate_case(case, constants)
    with localcontext() as context:
        context.prec = 80
        affinity, chemical, saturation, rt = thermodynamics(case, constants)
        c.require(abs(affinity / rt) <= 80, "Exponential drive outside contact domain")
        j = (
            Decimal(str(case["alpha_mol_m2_s"]))
            * Decimal(str(case["availability"]))
            * saturation
            * (1 - (affinity / rt).exp())
        )
        cycles = Decimal(str(case["area_m2"])) * j * Decimal("1e15")
        return {
            "na_in_fmol_s": float(-3 * cycles),
            "k_in_fmol_s": float(2 * cycles),
            "third_out_na_fmol_s": float(3 * cycles),
            "cycles_density_mol_m2_s": float(j),
            "inward_current_A": float(-Decimal(str(constants["F"])) * cycles * Decimal("1e-15")),
            "cycle_free_energy_J_mol": float(affinity),
            "chemical_free_energy_J_mol": float(chemical),
            "dissipation_pJ_s": float(-Decimal("0.001") * cycles * affinity),
            "chemical_input_power_pJ_s": float(-Decimal("0.001") * cycles * chemical),
        }


def cases(constants):
    rows = [{"id": "baseline", **BASE}]
    variants = {
        "voltage_V": [-0.12, -0.04, 0.0, 0.06],
        "temperature_K": [310.0],
        "na_in_mM": [6.0, 24.0],
        "na_out_mM": [70.0],
        "k_in_mM": [70.0],
        "k_out_mM": [0.02, 0.2, 2.0],
        "atp_mM": [0.15, 0.5, 15.0],
        "adp_mM": [0.01],
        "pi_mM": [1.0],
        "km_na_mM": [6.0],
        "km_k_mM": [0.4],
        "km_atp_mM": [1.0],
        "availability": [0.0, 0.5],
        "alpha_mol_m2_s": [0.0, 2e-7],
        "area_m2": [2e-9],
    }
    for name, values in variants.items():
        for value in values:
            rows.append({"id": f"{name}={value}", **BASE, name: value})
    at_zero = {"id": "stall_basis", **BASE, "voltage_V": 0.0}
    with localcontext() as context:
        context.prec = 80
        stall = float(thermodynamics(at_zero, constants)[0] / Decimal(str(constants["F"])))
    for name, offset in (
        ("reverse", -0.02),
        ("near_reverse", -1e-9),
        ("stall", 0.0),
        ("near_forward", 1e-9),
        ("forward", 0.02),
    ):
        rows.append({"id": f"mathematical_{name}", **BASE, "voltage_V": stall + offset})
    return rows


def protocol():
    return {
        "schema": "cells.betse_nak_contact_protocol@1",
        "decision": "D107",
        "upstream_revision": c.REVISION,
        "law": "betse_1_5_0_nak_positive_domain_validation_prototype",
        "profiles": {
            name: {"constants": values, "cases": cases(values)}
            for name, values in CONSTANTS.items()
        },
        "absolute_tolerances": ABSOLUTE,
        "relative_tolerance": RELATIVE,
        "cpu_affinity": [0, 1, 2, 3],
        "worker_timeout_seconds": 45,
        "total_timeout_seconds": 150,
        "artifact_limit_bytes": 32 * 1024**2,
        "per_file_limit_bytes": 8 * 1024**2,
        "production_changed": False,
        "coupled_trajectory": False,
        "biology_validated": False,
        "gpu_tested": False,
        "automatic_retry": False,
        "automatic_followup": False,
    }


def validate_protocol(plan):
    c.require(plan == protocol(), "Unregistered pump contact protocol")
    for profile in plan["profiles"].values():
        ids = [case["id"] for case in profile["cases"]]
        c.require(len(ids) == len(set(ids)), "Duplicate pump case")
        for case in profile["cases"]:
            oracle(case, profile["constants"])


def evaluate(plan, results):
    """Saved-column comparison only; never calls a runtime or numerical prototype."""
    validate_protocol(plan)
    c.require(set(results) == set(ENGINES), "Wrong engine coverage")
    rows = []
    for engine, result in results.items():
        c.require(set(result) == set(plan["profiles"]), "Wrong profile coverage")
        for profile_name, profile in plan["profiles"].items():
            saved = result[profile_name]
            c.require(
                set(saved) == {case["id"] for case in profile["cases"]}, "Wrong case coverage"
            )
            for case in profile["cases"]:
                expected = oracle(case, profile["constants"])
                actual = saved[case["id"]]
                c.require(set(actual) == set(OUTPUTS), "Wrong measured columns")
                for name in OUTPUTS:
                    value, target = actual[name], expected[name]
                    c.require(
                        type(value) in (int, float) and math.isfinite(value), "Nonfinite result"
                    )
                    budget = ABSOLUTE[name] + RELATIVE * abs(target)
                    exact_zero = case["availability"] == 0 or case["alpha_mol_m2_s"] == 0
                    error = abs(value - target)
                    rows.append(
                        {
                            "engine": engine,
                            "profile": profile_name,
                            "case": case["id"],
                            "column": name,
                            "actual": value,
                            "expected": target,
                            "absolute_error": error,
                            "budget": budget,
                            "pass": error <= budget and (not exact_zero or value == 0),
                            "exact_zero_required": exact_zero,
                        }
                    )
    return {
        "rows": rows,
        "comparisons": len(rows),
        "failures": sum(not row["pass"] for row in rows),
        "independent_saved_data_audit_complete": False,
    }
