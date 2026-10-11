"""Independent saved-state review of NUM-011. No simulator or ODE solver imports."""

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
CAPTURE = ROOT / "runs/num-011-kinetic-pump-2026-09-16/candidate-01"
COMPLETION_SHA = "57df709995d155139e20f026dbdd40bd37b417e9cbc8c182586ae8ecf681cbcb"
REGISTRATION_SHA = "127ddcba432198f05a5705687293054bfc7cdcbc3e34eec5720ce776c4aba9f2"
FORBIDDEN = (
    "cells",
    "betse",
    "numpy",
    "scipy",
    "jax",
    "jaxlib",
    "coupled_plan",
    "coupled_candidate",
    "coupled_reference",
    "coupled_compare",
    "coupled_job",
    "pump_array",
    "pump_reference",
)
CASES = (
    "pump_leak",
    "pump_only",
    "leak_only",
    "all_blocked",
    "pump_block_release",
    "two_cells_shared_bath",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def read(path):
    return json.loads(
        Path(path).read_text(),
        object_pairs_hook=unique,
        parse_constant=lambda _: require(False, "Nonfinite JSON constant"),
    )


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


@contextlib.contextmanager
def model_fence():
    def forbidden(name):
        return any(name == prefix or name.startswith(prefix + ".") for prefix in FORBIDDEN)

    require(not any(forbidden(name) for name in sys.modules), "Model already imported")

    class Fence(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if forbidden(fullname):
                raise ImportError("Model import forbidden in saved-state review: " + fullname)
            return None

    fence = Fence()
    sys.meta_path.insert(0, fence)
    try:
        yield
        require(not any(forbidden(name) for name in sys.modules), "Review imported model")
    finally:
        sys.meta_path.remove(fence)


def files(path):
    return {str(p.relative_to(path)): sha(p) for p in path.rglob("*") if p.is_file()}


def authenticate():
    require(sha(CAPTURE / "completion.json") == COMPLETION_SHA, "Completion changed")
    require(sha(CAPTURE / "registration.json") == REGISTRATION_SHA, "Registration changed")
    done, registered = (read(CAPTURE / n) for n in ("completion.json", "registration.json"))
    require(done["status"] == "coupled_candidate_pass_pending_audit", "Capture did not pass")
    require(not (CAPTURE / "failure.json").exists(), "Capture has failure receipt")
    require(all(sha(CAPTURE / n) == h for n, h in done["files_sha256"].items()), "Payload changed")
    sources = registered["sources_sha256"]
    require(len(sources) == 14, "Source coverage")
    require(all(sha(ROOT / n) == h for n, h in sources.items()), "Candidate sources changed")
    with zipfile.ZipFile(CAPTURE / "sources.zip") as archive:
        require(len(archive.namelist()) == len(sources), "Source capsule count")
        require(set(archive.namelist()) == set(sources), "Source capsule members")
        require(
            all(hashlib.sha256(archive.read(n)).hexdigest() == h for n, h in sources.items()),
            "Source capsule bytes",
        )
    receipt = registered["software"]
    require(
        receipt["tests"] == 37 and sha(ROOT / receipt["path"]) == receipt["sha256"],
        "Candidate software receipt changed",
    )
    preserved_path = ROOT / "reports/ref-003a-preservation.json"
    require(sha(preserved_path) == registered["preservation_sha256"], "Preservation changed")
    preserved = read(preserved_path)
    require(
        all(sha(ROOT / n) == h for n, h in preserved["implementation_files_sha256"].items()),
        "Accepted implementation changed before review",
    )
    require(
        sha(ROOT / preserved["preserved_capsule"]) == preserved["preserved_capsule_sha256"],
        "Accepted archive changed",
    )
    prior = registered["prior_closeout"]
    directory = ROOT / prior["path"]
    require(sha(directory / "completion.json") == prior["completion_sha256"], "Prior closeout")
    require(
        all(
            sha(directory / n) == h
            for n, h in read(directory / "completion.json")["files_sha256"].items()
        ),
        "Prior payload changed",
    )
    return registered, preserved


def d(value):
    require(type(value) in (int, float) and math.isfinite(value), "Nonfinite numeric state")
    return Decimal(value)


def physical(case, state, constants):
    """60-digit extensive energy differences, not the old anchored-log1p code.

    Binary saved values are lifted exactly into Decimal. No rounded concentration
    differences or repeated floating subtraction of absolute energies are used.
    """
    n = len(case["volume_pL"])
    require(len(state) == 8 * n + 3, "State width")
    with localcontext() as ctx:
        ctx.prec = 60
        y, z, nu = list(map(d, state)), list(map(d, case["valence"])), case["pump_stoichiometry"]
        f, rt = d(constants["F"]), d(constants["R"]) * d(case["temperature_K"])
        scale = Decimal("0.001")
        cycles = y[6 * n + 3 : 7 * n + 3]
        ledgers = [
            [y[3 * n + 3 + 3 * i + s] + nu[s] * cycles[i] for s in range(3)] for i in range(n)
        ]
        material = [abs(y[3 * i + s] - ledgers[i][s]) for i in range(n) for s in range(3)]
        material += [abs(y[3 * n + s] + sum(ledgers[i][s] for i in range(n))) for s in range(3)]
        imbalance = sum(
            z[s] * (y[3 * n + s] + sum(y[3 * i + s] for i in range(n))) for s in range(3)
        )
        energy, work, voltages, concentrations = Decimal(0), Decimal(0), [], []
        for i in range(n + 1):
            volume = d(case["volume_pL"][i] if i < n else case["outside_volume_pL"])
            initial = case["initial_inside_mM"][i] if i < n else case["initial_outside_mM"]
            for s in range(3):
                c0, dn = d(initial[s]), y[3 * i + s]
                n0 = c0 * volume
                amount = n0 + dn
                require(amount > 0, "Depleted saved compartment")
                concentration = amount / volume
                concentrations.append(concentration)
                energy += scale * rt * (amount * concentration.ln() - n0 * c0.ln() - dn)
            if i == n:
                continue
            cap = d(case["area_m2"][i]) * d(case["specific_capacitance_F_m2"][i])
            q0 = cap * d(case["initial_voltage_V"][i])
            dq = f * Decimal("1e-15") * sum(z[s] * y[3 * i + s] for s in range(3))
            voltage = (q0 + dq) / cap
            voltages.append(float(voltage))
            require(all(abs(zs * f * voltage / rt) <= 50 for zs in z), "Saved voltage domain")
            energy += ((q0 + dq) ** 2 - q0**2) / (2 * cap) * Decimal("1e12")
            drive = (
                d(case["delta_g0_J_mol"][i])
                + rt
                * (d(case["adp_mM"][i]) * d(case["pi_mM"][i]) / (1000 * d(case["atp_mM"][i]))).ln()
            )
            work -= scale * drive * cycles[i]
        return {
            "material_residual_fmol": float(max(material)),
            "charge_residual_C": float(abs(f * Decimal("1e-15") * imbalance)),
            "energy_residual_pJ": float(abs(energy + sum(y[7 * n + 3 :]) - work)),
            "voltage_V": voltages,
            "min_concentration_mM": float(min(concentrations)),
        }


def audit(plan, reference, candidate, comparison):
    require(tuple(c["id"] for c in plan["cases"]) == CASES, "Case protocol changed")
    require(set(reference) == set(candidate) == set(CASES), "Case coverage")
    require(plan["rk4_steps_s"] == [0.0001, 0.00005], "Candidate steps changed")
    require(plan["reference_methods"] == ["DOP853", "Radau"], "Reference methods")
    require(comparison["status"] == "pass", "Saved comparison did not pass")
    groups = {(g["case"], g["method"]): g for g in comparison["groups"]}
    refinements = {(g["case"], g["engine"]): g for g in comparison["refinement"]}
    require(len(groups) == len(comparison["groups"]) == 30, "Comparison group coverage")
    require(len(refinements) == len(comparison["refinement"]) == 12, "Refinement coverage")
    limits = {
        name: plan[key]
        for name, key in (
            ("material_residual_fmol", "material_atol_fmol"),
            ("charge_residual_C", "charge_atol_C"),
            ("energy_residual_pJ", "energy_atol_pJ"),
        )
    }
    maxima = dict.fromkeys(limits, 0.0)
    rows, physical_count, restart_count, max_voltage = [], 0, 0, 0.0
    per_case, all_roundoff = [], True
    for case in plan["cases"]:
        name, n = case["id"], len(case["volume_pL"])
        require(case["end_time_s"] == 0.01, "Changed horizon")
        require(set(reference[name]) == {"DOP853", "Radau"}, "Method coverage")
        times = [k * plan["sample_dt_s"] for k in range(11)]
        targets = reference[name]["Radau"]["state"]
        cache = {}

        def inspect(state, *, cache=cache, case=case, n=n, name=name):
            nonlocal physical_count
            key = tuple(state)
            if key not in cache:
                cache[key] = physical(case, state, plan["constants"])
            found = cache[key]
            for quantity, limit in limits.items():
                require(found[quantity] <= limit, "Independent " + quantity)
                maxima[quantity] = max(maxima[quantity], found[quantity])
            require(min(state[7 * n + 3 :]) >= -1e-14, "Negative dissipation")
            if name == "all_blocked":
                require(all(v == 0 for v in state), "Blocked state changed")
            physical_count += 1
            return found

        for path in reference[name].values():
            require(len(path["state"]) == 11 and len(path["times_s"]) == 11, "Reference shape")
            require(
                all(abs(a - b) <= 1e-15 for a, b in zip(path["times_s"], times, strict=True)),
                "Reference times",
            )
            require(all(v == 0 for v in path["state"][0]), "Nonzero reference initial state")
            for state in path["state"]:
                inspect(state)
            segments = path["segments"]
            require(len(segments) == len(case["controls"]), "Reference segment coverage")
            for i, segment in enumerate(segments):
                end = case["controls"][i + 1]["time_s"] if i + 1 < len(segments) else 0.01
                require(
                    segment["start_s"] == case["controls"][i]["time_s"]
                    and segment["end_s"] == segment["last_solver_time_s"] == end
                    and type(segment["nfev"]) is int
                    and segment["nfev"] > 0,
                    "Reference segment metadata",
                )
                endpoint = path["state"][round(end / plan["sample_dt_s"])]
                require(len(segment["end_state"]) == len(endpoint), "Reference endpoint width")
                require(
                    all(
                        abs(a - b) <= plan["state_atol"] + plan["state_rtol"] * abs(b)
                        for a, b in zip(segment["end_state"], endpoint, strict=True)
                    ),
                    "Reference endpoint sample linkage",
                )
        trial = candidate[name]
        expected_keys = {
            f"{engine}/{dt}" for engine in ("numpy", "jax_jit") for dt in plan["rk4_steps_s"]
        }
        require(set(trial["trajectories"]) == expected_keys, "Candidate method coverage")
        paths = {"DOP853": reference[name]["DOP853"], **trial["trajectories"]}
        errors = {}
        for label, path in paths.items():
            require(len(path["state"]) == len(path["times_s"]) == 11, "Sample coverage")
            require(
                all(abs(a - b) <= 1e-15 for a, b in zip(path["times_s"], times, strict=True)),
                "Sample time linkage",
            )
            if label != "DOP853":
                dt = float(label.split("/")[1])
                full = path["full_state"]
                require(
                    path["step_s"] == dt and len(full) == round(0.01 / dt) + 1,
                    "Full endpoint coverage",
                )
                require(full[:: round(plan["sample_dt_s"] / dt)] == path["state"], "Sample linkage")
                require(all(v == 0 for v in full[0]), "Nonzero candidate initial state")
                for state in full:
                    inspect(state)
                for old, new in zip(full, full[1:], strict=False):
                    require(
                        all(
                            b >= a - 1e-14
                            for a, b in zip(old[7 * n + 3 :], new[7 * n + 3 :], strict=True)
                        ),
                        "Dissipation decreased",
                    )
                if name in ("leak_only", "all_blocked"):
                    require(
                        all(all(v == 0 for v in row[6 * n + 3 : 7 * n + 3]) for row in full),
                        "Absent pump acquired cycles",
                    )
                if name == "pump_only":
                    require(
                        all(all(v == 0 for v in row[3 * n + 3 : 6 * n + 3]) for row in full),
                        "Absent leak acquired history",
                    )
                if name == "pump_block_release":
                    section = full[round(0.004 / dt) : round(0.006 / dt) + 1]
                    require(
                        all(
                            row[6 * n + 3 : 7 * n + 3] == section[0][6 * n + 3 : 7 * n + 3]
                            for row in section
                        ),
                        "Pump history changed during block",
                    )
            scaled, voltage_error = 0.0, 0.0
            for index, (actual, expected) in enumerate(zip(path["state"], targets, strict=True)):
                require(len(actual) == len(expected) == 8 * n + 3, "Comparison width")
                for column, (value, target) in enumerate(zip(actual, expected, strict=True)):
                    d(value), d(target)
                    error = abs(value - target)
                    budget = plan["state_atol"] + plan["state_rtol"] * abs(target)
                    require(error <= budget, "Independent state comparison failed")
                    scaled = max(scaled, error / budget)
                    rows.append([name, label, index, column, value, target, error, budget])
                pa, pb = cache[tuple(actual)], cache[tuple(expected)]
                voltage_error = max(
                    voltage_error,
                    *(abs(a - b) for a, b in zip(pa["voltage_V"], pb["voltage_V"], strict=True)),
                )
            require(voltage_error <= plan["voltage_atol_V"], "Independent voltage comparison")
            saved = groups.pop((name, label))
            require(
                saved["max_scaled_state_error"] == scaled and saved["pass"] is True,
                "Saved state summary mismatch",
            )
            for quantity, limit in {
                **limits,
                "max_voltage_error_V": plan["voltage_atol_V"],
            }.items():
                require(
                    type(saved[quantity]) in (int, float)
                    and math.isfinite(saved[quantity])
                    and 0 <= saved[quantity] <= limit,
                    "Saved physical summary invalid",
                )
            errors[label] = scaled
            max_voltage = max(max_voltage, voltage_error)
        for engine in ("numpy", "jax_jit"):
            coarse, fine = [errors[f"{engine}/{dt}"] for dt in plan["rk4_steps_s"]]
            bound = max(
                plan["refinement_ratio_limit"] * coarse, plan["roundoff_scaled_error_floor"]
            )
            require(
                refinements.pop((name, engine))
                == {
                    "case": name,
                    "engine": engine,
                    "coarse": coarse,
                    "fine": fine,
                    "bound": bound,
                    "pass": fine <= bound,
                    "roundoff_limited": coarse <= plan["roundoff_scaled_error_floor"],
                }
                and fine <= bound,
                "Refinement reconstruction",
            )
            all_roundoff &= coarse <= plan["roundoff_scaled_error_floor"]
        require(
            trial["restart_exact"] is True and set(trial["checkpoints"]) == {"numpy", "jax_jit"},
            "Restart coverage",
        )
        for engine, checkpoint in trial["checkpoints"].items():
            full = trial["trajectories"][f"{engine}/5e-05"]["full_state"]
            require(
                checkpoint["time_s"] == 0.006
                and checkpoint["exact"] is True
                and checkpoint["complete_state"] == full[120]
                and checkpoint["suffix_state"] == full[120:],
                "Complete restart linkage",
            )
            restart_count += 1
        per_case.append({"case": name, "cached_physical_states": len(cache), "pass": True})
    require(
        not groups and not refinements and len(rows) == comparison["state_comparisons"] == 4070,
        "Numerical identity coverage",
    )
    return {
        "status": "coupled_candidate_independently_closed",
        "state_comparisons": len(rows),
        "groups": 30,
        "refinement_groups": 12,
        "physical_records": physical_count,
        "restarts": restart_count,
        "rows": rows,
        "cases": per_case,
        "independent_physical_maxima": maxima,
        "max_voltage_error_V": max_voltage,
        "all_refinement_roundoff_limited": all_roundoff,
        "observed_convergence_order_claimed": False,
        "model_imports": [],
        "solvers_rerun": False,
        "production_model_accepted": False,
        "native_betse_trajectory_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
    }


def run(output, tests):
    output, tests = output.resolve(), tests.resolve()
    require(
        output.is_relative_to(ROOT / "runs") and output != ROOT / "runs" and not output.exists(),
        "Use fresh audit output",
    )
    require(tests.is_relative_to(ROOT / "reports"), "Use reports software receipt")
    output.mkdir(parents=True)
    started = time.monotonic()
    try:
        with model_fence():
            registered, preserved = authenticate()
            before = files(CAPTURE)
            suites = ET.parse(tests).getroot().findall("testsuite")
            require(
                suites
                and sum(int(s.attrib["tests"]) for s in suites) >= 15
                and all(
                    int(s.attrib.get(k, 0)) == 0
                    for s in suites
                    for k in ("errors", "failures", "skipped")
                ),
                "Audit checks did not pass",
            )
            sources = {
                str(p.relative_to(ROOT)): sha(p)
                for p in (
                    Path(__file__).resolve(),
                    Path(__file__).with_name("test_coupled_audit.py").resolve(),
                )
            }
            with zipfile.ZipFile(output / "sources.zip", "x") as archive:
                for name in sources:
                    archive.write(ROOT / name, arcname=name)
            write(
                output / "registration.json",
                {
                    "capture": str(CAPTURE.relative_to(ROOT)),
                    "capture_sha256": before,
                    "capture_completion_sha256": COMPLETION_SHA,
                    "sources_sha256": sources,
                    "software": {"path": str(tests.relative_to(ROOT)), "sha256": sha(tests)},
                    "registered_utc": datetime.now(UTC).isoformat(),
                    "accepted_implementation_files_sha256": preserved[
                        "implementation_files_sha256"
                    ],
                    "accepted_source_hashes": preserved["source_hashes"],
                    "accepted_runtime": preserved["runtime"],
                    "accepted_capsule": preserved["preserved_capsule"],
                    "accepted_capsule_sha256": preserved["preserved_capsule_sha256"],
                },
            )
            worker = [read(CAPTURE / f"{engine}.json") for engine in ("reference", "candidate")]
            require(
                all(
                    w["registration_sha256"] == REGISTRATION_SHA and not w["warnings"]
                    for w in worker
                ),
                "Worker provenance/warnings",
            )
            result = audit(
                registered["protocol"],
                *(w["results"] for w in worker),
                read(CAPTURE / "comparison.json"),
            )
            require(files(CAPTURE) == before, "Original capture changed")
            authenticate()
            require(time.monotonic() - started < 30, "Short review exceeded 30 seconds")
            write(output / "audit.json", result)
            done = {k: v for k, v in result.items() if k != "rows"} | {
                "elapsed_seconds": time.monotonic() - started,
                "finished_utc": datetime.now(UTC).isoformat(),
                "capture_files_unchanged": len(before),
                "files_sha256": {
                    n: sha(output / n) for n in ("registration.json", "sources.zip", "audit.json")
                },
            }
            write(output / "completion.json", done)
            return done
    except BaseException:
        write(
            output / "failure.json",
            {"status": "failed_not_qualified", "traceback": traceback.format_exc()},
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.tests), sort_keys=True))
