"""Independent saved Na/K source-contact audit. Standard library; no model calls."""

import argparse
import contextlib
import hashlib
import importlib.abc
import json
import math
import sys
import time
import traceback
import zipfile
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
CAPTURE = ROOT / "runs/ref-005a-pump-contact-2026-09-16/capture-01"
COMPLETION_SHA = "944d5183323650219cda4eae950e6ffd0fe8e2c2b8d35c2f125cfe727cd9f593"
REGISTRATION_SHA = "152b7ff43ff946450ef9c96f034d4a25ed09e2982ffa50a6ceaf451de0178fc4"
FORBIDDEN = (
    "cells",
    "betse",
    "numpy",
    "scipy",
    "jax",
    "jaxlib",
    "pump_reference",
    "pump_array",
    "pump_workers",
    "pump_job",
)
COLUMNS = (
    "na_in_fmol_s",
    "k_in_fmol_s",
    "third_out_na_fmol_s",
    "cycles_density_mol_m2_s",
    "inward_current_A",
)
ABSOLUTE = dict(zip(COLUMNS, (2e-12, 2e-12, 2e-12, 2e-18, 2e-22), strict=True))
ENGINES = ("native", "numpy", "jax_eager", "jax_jit")


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pairs(values):
    result = {}
    for name, value in values:
        require(name not in result, "Duplicate JSON key")
        result[name] = value
    return result


def read(path):
    return json.loads(
        Path(path).read_text(),
        object_pairs_hook=pairs,
        parse_constant=lambda _: require(False, "Nonfinite JSON constant"),
    )


def write(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


@contextlib.contextmanager
def model_fence():
    def forbidden(name):
        return any(name == item or name.startswith(item + ".") for item in FORBIDDEN)

    require(not any(forbidden(name) for name in sys.modules), "Model already imported")

    class Fence(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if forbidden(fullname):
                raise ImportError("Model import forbidden in independent pump audit: " + fullname)
            return None

    fence = Fence()
    sys.meta_path.insert(0, fence)
    try:
        yield
        require(not any(forbidden(name) for name in sys.modules), "Audit imported model")
    finally:
        sys.meta_path.remove(fence)


def packet_hashes():
    return {str(p.relative_to(CAPTURE)): sha(p) for p in CAPTURE.rglob("*") if p.is_file()}


def authenticate():
    require(sha(CAPTURE / "completion.json") == COMPLETION_SHA, "Capture completion changed")
    require(sha(CAPTURE / "registration.json") == REGISTRATION_SHA, "Registration changed")
    completion, registration = (read(CAPTURE / n) for n in ("completion.json", "registration.json"))
    require(
        completion["status"] == "contact_pass_pending_audit"
        and completion["comparisons"] == 1240
        and completion["failures"] == 0,
        "Unexpected capture scope",
    )
    require(not (CAPTURE / "failure.json").exists(), "Capture has failure receipt")
    require(
        all(sha(CAPTURE / n) == h for n, h in completion["files_sha256"].items()),
        "Captured payload changed",
    )
    source = registration["sources_sha256"]
    require(
        len(source) == 11 and all(sha(ROOT / n) == h for n, h in source.items()),
        "Captured source changed",
    )
    with zipfile.ZipFile(CAPTURE / "sources.zip") as archive:
        require(
            set(archive.namelist()) == set(source) and len(archive.namelist()) == len(source),
            "Capsule members changed",
        )
        require(
            all(hashlib.sha256(archive.read(n)).hexdigest() == h for n, h in source.items()),
            "Capsule bytes changed",
        )
    software = registration["software"]
    require(
        software["tests"] == 70 and sha(ROOT / software["path"]) == software["sha256"],
        "Software receipt changed",
    )
    preserve = ROOT / "reports/ref-003a-preservation.json"
    require(sha(preserve) == registration["preservation_sha256"], "Preservation changed")
    accepted = read(preserve)
    require(
        all(sha(ROOT / n) == h for n, h in accepted["implementation_files_sha256"].items()),
        "Accepted implementation changed before closeout",
    )
    require(
        sha(ROOT / accepted["preserved_capsule"]) == accepted["preserved_capsule_sha256"],
        "Accepted source capsule changed",
    )
    prior = registration["prior_closeout"]
    prior_path = ROOT / prior["path"]
    require(
        sha(prior_path / "completion.json") == prior["completion_sha256"], "Prior closeout changed"
    )
    require(
        all(
            sha(prior_path / n) == h
            for n, h in read(prior_path / "completion.json")["files_sha256"].items()
        ),
        "Prior audit payload changed",
    )
    return registration


def reference(case, constants):
    """Direct mass-action quotient / equilibrium constant; no old oracle import."""
    with localcontext() as context:
        context.prec = 90
        d = {k: Decimal(str(v)) for k, v in case.items() if k != "id"}
        f, r = Decimal(str(constants["F"])), Decimal(str(constants["R"]))
        rt = r * d["temperature_K"]
        q = (
            d["adp_mM"]
            / 1000
            * d["pi_mM"]
            / 1000
            * (d["na_out_mM"] / 1000) ** 3
            * (d["k_in_mM"] / 1000) ** 2
            / (d["atp_mM"] / 1000 * (d["na_in_mM"] / 1000) ** 3 * (d["k_out_mM"] / 1000) ** 2)
        )
        keq = ((f * d["voltage_V"] - d["delta_g0_J_mol"]) / rt).exp()
        na, k, atp = (
            d["na_in_mM"] / d["km_na_mM"],
            d["k_out_mM"] / d["km_k_mM"],
            d["atp_mM"] / d["km_atp_mM"],
        )
        saturation = na**3 * k**2 * atp / ((1 + na**3) * (1 + k**2) * (1 + atp))
        j = d["availability"] * d["alpha_mol_m2_s"] * saturation * (1 - q / keq)
        cycles = j * d["area_m2"] * Decimal("1e15")
        affinity = rt * (q / keq).ln()
        return dict(
            zip(
                COLUMNS,
                map(
                    float, (-3 * cycles, 2 * cycles, 3 * cycles, j, -f * cycles * Decimal("1e-15"))
                ),
                strict=True,
            )
        ), {
            "affinity_J_mol": float(affinity),
            "dissipation_pJ_s": float(-cycles * affinity * Decimal("0.001")),
        }


def derived(raw, case, constants):
    require(type(raw) is list and len(raw) == 3, "Bad density shape")
    require(all(type(v) in (int, float) and math.isfinite(v) for v in raw), "Invalid density")
    # Reconstruct the exact reported binary64 conversion order separately from
    # the independent decimal physical values. Neither modifies captured data.
    na, k, third = raw
    area, faraday = case["area_m2"], constants["F"]
    return dict(
        zip(
            COLUMNS,
            (
                na * area * 1e15,
                k * area * 1e15,
                third * area * 1e15,
                -na / 3,
                faraday * area * (na + k),
            ),
            strict=True,
        )
    )


def audit_saved(registration, native, prototype, comparison):
    require(
        native["engine"] == "unmodified_betse_pumpNaKATP"
        and prototype["engine"] == "validation_only_nak_array_law",
        "Wrong engines",
    )
    require(
        set(native["results"]) == {"native"}
        and set(prototype["results"]) == {"numpy", "jax_eager", "jax_jit"},
        "Engine coverage",
    )
    for result in (native, prototype):
        require(
            result["registration_sha256"] == REGISTRATION_SHA
            and not result["warnings"]
            and result["input_unchanged"] is True,
            "Worker provenance/input mismatch",
        )
    require(
        native["met_ignored"] is True and native["third_is_outward_na"] is True,
        "Native semantics changed",
    )
    require(prototype["backend"] == "cpu" and prototype["dtype"] == "float64", "Execution mode")
    expected_files = {
        n: h
        for n, h in registration["upstream"]["files_sha256"].items()
        if n.startswith("betse/") and n.endswith(".py")
    }
    require(
        native["installed_python_sha256"] == expected_files and len(expected_files) == 332,
        "Native source provenance mismatch",
    )
    plan = registration["protocol"]
    require(
        plan["absolute_tolerances"] == ABSOLUTE and plan["relative_tolerance"] == 2e-11,
        "Changed numerical budgets",
    )
    require(set(plan["profiles"]) == {"source_constants", "matched_constants"}, "Profile coverage")
    results = {**native["results"], **prototype["results"]}
    raw = {"native": native["raw_density_mol_m2_s"], **prototype["raw_density_mol_m2_s"]}
    require(set(raw) == set(ENGINES), "Raw engine coverage")
    rows = comparison["rows"]
    require(
        len(rows) == comparison["comparisons"] == 1240 and comparison["failures"] == 0,
        "Wrong comparison count",
    )
    indexed = {(x["engine"], x["profile"], x["case"], x["column"]): x for x in rows}
    require(len(indexed) == len(rows), "Duplicate comparison")
    rebuilt, thermodynamics, max_scaled = [], [], 0.0
    for engine in ENGINES:
        require(set(results[engine]) == set(raw[engine]) == set(plan["profiles"]), "Profile rows")
        for name, profile in plan["profiles"].items():
            cases, constants = profile["cases"], profile["constants"]
            require(len(cases) == len(raw[engine][name]) == 31, "Case count")
            require(set(results[engine][name]) == {x["id"] for x in cases}, "Case coverage")
            for case, densities in zip(cases, raw[engine][name], strict=True):
                expected, energy = reference(case, constants)
                actual = derived(densities, case, constants)
                require(actual == results[engine][name][case["id"]], "Raw/derived linkage mismatch")
                require(densities[2] == -densities[0], "Third return is not outward Na")
                require(
                    abs(2 * densities[0] + 3 * densities[1])
                    <= 8 * math.ulp(max(map(abs, densities))),
                    "Na/K stoichiometry mismatch",
                )
                require(energy["dissipation_pJ_s"] >= 0, "Negative reference dissipation")
                thermodynamics.append(
                    {"engine": engine, "profile": name, "case": case["id"], **energy}
                )
                zero = case["availability"] == 0 or case["alpha_mol_m2_s"] == 0
                for column in COLUMNS:
                    value, target = actual[column], expected[column]
                    error, budget = abs(value - target), ABSOLUTE[column] + 2e-11 * abs(target)
                    row = {
                        "engine": engine,
                        "profile": name,
                        "case": case["id"],
                        "column": column,
                        "actual": value,
                        "expected": target,
                        "absolute_error": error,
                        "budget": budget,
                        "pass": error <= budget and (not zero or value == 0),
                        "exact_zero_required": zero,
                    }
                    require(
                        row == indexed[(engine, name, case["id"], column)],
                        "Independent comparison column mismatch",
                    )
                    require(row["pass"], "Independent physical check failed")
                    max_scaled = max(max_scaled, error / budget)
                    rebuilt.append(row)
    return {
        "status": "pump_contact_independently_closed",
        "comparisons": len(rebuilt),
        "independent_column_mismatches": 0,
        "raw_triplets_checked": len(thermodynamics),
        "max_error_fraction_of_budget": max_scaled,
        "rows": rebuilt,
        "thermodynamics": thermodynamics,
        "model_imports": [],
        "simulators_rerun": False,
        "production_pump_implemented": False,
        "coupled_trajectory_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
    }


def run(output, tests=None):
    output = output.resolve()
    require(
        output.is_relative_to(ROOT / "runs") and output != ROOT / "runs" and not output.exists(),
        "Use fresh audit output",
    )
    output.mkdir(parents=True)
    began = time.monotonic()
    try:
        with model_fence():
            registration = authenticate()
            before = packet_hashes()
            require(
                tests is not None and tests.resolve().is_relative_to(ROOT / "reports"),
                "Need focused software receipt",
            )
            suites = ET.parse(tests).getroot().findall("testsuite")
            require(
                bool(suites)
                and sum(int(s.attrib["tests"]) for s in suites) == 17
                and all(
                    all(int(s.attrib.get(k, 0)) == 0 for k in ("failures", "errors", "skipped"))
                    for s in suites
                ),
                "Software checks did not pass",
            )
            audit_sources = {
                str(p.relative_to(ROOT)): sha(p)
                for p in (
                    Path(__file__).resolve(),
                    Path(__file__).with_name("test_pump_audit.py").resolve(),
                )
            }
            with zipfile.ZipFile(output / "sources.zip", "x") as capsule:
                for name in audit_sources:
                    capsule.write(ROOT / name, arcname=name)
            write(
                output / "registration.json",
                {
                    "capture": str(CAPTURE.relative_to(ROOT)),
                    "completion_sha256": COMPLETION_SHA,
                    "capture_sha256": before,
                    "auditor_sha256": sha(Path(__file__)),
                    "sources_sha256": audit_sources,
                    "software": {
                        "path": str(tests.resolve().relative_to(ROOT)),
                        "sha256": sha(tests),
                        "tests": 17,
                    },
                    "registered_utc": datetime.now(UTC).isoformat(),
                },
            )
            result = audit_saved(
                registration,
                *(read(CAPTURE / f"{n}.json") for n in ("native", "prototype", "comparison")),
            )
            require(before == packet_hashes(), "Audit modified the original capture")
            require(time.monotonic() - began <= 30, "Short audit exceeded its 30-second bound")
            write(output / "audit.json", result)
            write(
                output / "completion.json",
                {k: v for k, v in result.items() if k not in ("rows", "thermodynamics")}
                | {
                    "elapsed_seconds": time.monotonic() - began,
                    "finished_utc": datetime.now(UTC).isoformat(),
                    "capture_files_unchanged": len(before),
                    "capture_completion_sha256": COMPLETION_SHA,
                    "files_sha256": {
                        n: sha(output / n)
                        for n in ("registration.json", "audit.json", "sources.zip")
                    },
                },
            )
            return read(output / "completion.json")
    except BaseException:
        write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "traceback": traceback.format_exc(),
                "elapsed_seconds": time.monotonic() - began,
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.tests), sort_keys=True))
