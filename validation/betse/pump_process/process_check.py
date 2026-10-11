"""Production process versus saved, independently closed matched-constant contact.

No native rerun and no coupled trajectory: this qualifies the process boundary.
"""

import json
import math
import sys
import warnings
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import F, R

ROOT = Path(__file__).resolve().parents[3]
CAPTURE = ROOT / "runs/ref-005a-pump-contact-2026-09-16/capture-01"
COLUMNS = (
    "na_in_fmol_s",
    "k_in_fmol_s",
    "third_out_na_fmol_s",
    "cycles_density_mol_m2_s",
    "inward_current_A",
)


def inputs(cases, xp):
    for case in cases:
        if not all(
            math.isfinite(case[name]) and case[name] > 0
            for name in ("na_in_mM", "na_out_mM", "k_in_mM", "k_out_mM", "temperature_K")
        ):
            raise ValueError("Invalid physical probe before potential evaluation")

    def values(name):
        return xp.asarray([case[name] for case in cases], dtype=xp.float64)

    temperature, voltage = values("temperature_K"), values("voltage_V")
    p = pump.Parameters(
        values("alpha_mol_m2_s") * values("area_m2") * 1e15,
        *(
            values(name)
            for name in (
                "atp_mM",
                "adp_mM",
                "pi_mM",
                "km_na_mM",
                "km_k_mM",
                "km_atp_mM",
                "delta_g0_J_mol",
            )
        ),
    )
    mu_na = (
        R * temperature * (xp.log(values("na_in_mM")) - xp.log(values("na_out_mM"))) + F * voltage
    )
    mu_k = R * temperature * (xp.log(values("k_in_mM")) - xp.log(values("k_out_mM"))) + F * voltage
    return (
        values("na_in_mM"),
        values("k_out_mM"),
        mu_na,
        mu_k,
        temperature,
        p,
        values("availability"),
    )


def evaluate(cases, saved, protocol):
    if not jax.config.x64_enabled or jax.default_backend() != "cpu" or jax.config.jax_disable_jit:
        raise ValueError("Process qualification requires JIT enabled / CPU float64")
    expected = {
        (row["case"], row["column"]): row
        for row in saved["rows"]
        if row["profile"] == "matched_constants" and row["engine"] == "native"
    }
    if len(expected) != 31 * len(COLUMNS):
        raise ValueError("Saved matched-constant contact coverage changed")
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Duplicate production probe")
    result, thermodynamics = [], []
    for engine in ("numpy", "jax_eager", "jax_jit"):
        xp = np if engine == "numpy" else jnp
        args = inputs(cases, xp)
        if not np.asarray(pump.domain_valid(*args, xp=xp)).all():
            raise ValueError("Production probe outside kinetic domain")
        outputs = (
            jax.jit(pump.kinetics)(*args) if engine == "jax_jit" else pump.kinetics(*args, xp=xp)
        )
        rate, affinity, drive = (np.asarray(v) for v in outputs)
        if any(v.dtype != np.float64 or not np.isfinite(v).all() for v in (rate, affinity, drive)):
            raise ValueError("Production dtype/finite result")
        for index, case in enumerate(cases):
            cycle = float(rate[index])
            actual = (
                -3 * cycle,
                2 * cycle,
                3 * cycle,
                cycle * 1e-15 / case["area_m2"],
                -F * cycle * 1e-15,
            )
            blocked = case["alpha_mol_m2_s"] == 0 or case["availability"] == 0
            if blocked and cycle != 0:
                raise ValueError("Disabled pump did not give exact zero")
            dissipated = -0.001 * cycle * float(affinity[index])
            if dissipated < 0:
                raise ValueError("Negative production pump dissipation")
            thermodynamics.append(
                {
                    "engine": engine,
                    "case": case["id"],
                    "cycles_fmol_s": cycle,
                    "cycle_free_energy_J_mol": float(affinity[index]),
                    "chemical_drive_J_mol": float(drive[index]),
                    "dissipation_pJ_s": dissipated,
                }
            )
            for column, value in zip(COLUMNS, actual, strict=True):
                record = expected[case["id"], column]
                for kind, key in (("independent_oracle", "expected"), ("saved_native", "actual")):
                    target = record[key]
                    budget = protocol["absolute_tolerances"][column] + protocol[
                        "relative_tolerance"
                    ] * abs(target)
                    error = abs(value - target)
                    result.append(
                        {
                            "engine": engine,
                            "case": case["id"],
                            "column": column,
                            "reference": kind,
                            "actual": value,
                            "expected": target,
                            "budget": budget,
                            "absolute_error": error,
                            "pass": error <= budget and (not blocked or value == 0),
                        }
                    )
    return {
        "status": "pass" if all(r["pass"] for r in result) else "failed",
        "cases": len(cases),
        "comparisons": len(result),
        "rows": result,
        "thermodynamics": thermodynamics,
        "law_id": pump.LAW_ID,
        "profile": "matched_constants",
        "native_rerun": False,
        "coupled_production_model_accepted": False,
        "gpu_tested": False,
        "biology_validated": False,
    }


def run(output):
    import process_job as job

    job.authenticate(output)
    protocol = job.c.read(CAPTURE / "registration.json")["protocol"]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = evaluate(
            protocol["profiles"]["matched_constants"]["cases"],
            job.c.read(CAPTURE / "comparison.json"),
            protocol,
        )
    result["warnings"] = [str(w.message) for w in caught]
    job.c.write(output / "process-contact.json", result)
    job.c.require(
        result["status"] == "pass" and not caught, "Process contact failed; data retained"
    )
    job.authenticate(output)


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve())
    print(json.dumps({"status": "process_contact_pass"}))
