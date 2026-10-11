"""Read-only diagnosis of a sealed failed pilot; no ODE/model/producer imports."""

import argparse
import hashlib
import math
import signal
import struct
import sys
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import native_energy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pump_loop_audit"))
sys.path.insert(0, str(HERE.parent / "kinetic_family_audit"))
import artifacts as a  # noqa: E402
import evidence as e  # noqa: E402

CAPTURE = e.ROOT / "runs/ref-005c-matched-pump-2026-09-16/pilot-01"
REGISTRATION = "2dc09a3d112b1f0efc3a03d0a43f9cc2a395078553881ba7a7cc33497dff269b"
FAILURE = "b6e2624a2dc39dd5204bc7a660d608944079d615ac7c564c9c5ea56581d72500"
FIELDS = (
    "amount_increment",
    "leak_transferred",
    "pump_cycles",
    "dissipated_energy_pJ",
    "gate",
    "channel_transferred",
    "junction_gate",
    "junction_transferred",
    "junction_dissipated_energy_pJ",
    "extracellular_amount_increment",
)
e.FORBIDDEN += (
    "pilot_context",
    "pilot_compare",
    "pilot_math",
    "pilot_mapping",
    "pilot_reference",
    "pilot_cells",
    "pilot_native",
    "pilot_job",
)


def inventory(directory):
    paths = list(directory.rglob("*"))
    e.require(not any(p.is_symlink() for p in paths), "Symlink in evidence")
    e.require(all(p.is_file() or p.is_dir() for p in paths), "Nonregular evidence")
    return {str(p.relative_to(directory)): e.sha(p) for p in sorted(paths) if p.is_file()}


def authenticate():
    e.require(
        e.sha(CAPTURE / "registration.json") == REGISTRATION
        and e.sha(CAPTURE / "failure.json") == FAILURE,
        "Failed pilot identity changed",
    )
    e.require(not (CAPTURE / "completion.json").exists(), "Rejected pilot claims completion")
    r = e.read(CAPTURE / "registration.json")
    e.require(
        len(r["sources_sha256"]) == 629
        and all(e.sha(e.ROOT / n) == h for n, h in r["sources_sha256"].items()),
        "Frozen inputs changed",
    )
    sources = {
        n.removeprefix("src/cells/"): h
        for n, h in r["sources_sha256"].items()
        if n.startswith("src/cells/")
    }
    e.require(
        len(sources) == 55
        and set(sources)
        == {str(p.relative_to(e.ROOT / "src/cells")) for p in (e.ROOT / "src/cells").rglob("*.py")},
        "Production inventory changed",
    )
    with zipfile.ZipFile(CAPTURE / "sources.zip") as archive:
        e.require(
            len(archive.namelist()) == 629 and set(archive.namelist()) == set(r["sources_sha256"]),
            "Source capsule membership",
        )
        e.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Source capsule bytes",
        )
    e.require(
        e.software(e.ROOT / r["software"]["path"], 37) == r["software"], "Pilot software receipt"
    )
    e.require(
        e.read(CAPTURE / "failure.json")["status"] == "pilot_failed_not_qualified",
        "Unexpected terminal state",
    )
    for phase in ("mapping", "reference", "betse", "cells"):
        e.require(
            e.read(CAPTURE / (phase + "-complete.json"))["status"] == "phase_pass",
            "Missing capture phase",
        )
    return r, sources


def discrepancy(actual, expected, atol, rtol=0.0):
    x, y = list(e.flat(actual)), list(e.flat(expected))
    e.require(len(x) == len(y) and x, "Comparison extent")
    results = []
    for i, (v, w) in enumerate(zip(x, y, strict=True)):
        e.require(math.isfinite(v) and math.isfinite(w), "Nonfinite comparison")
        error, budget = abs(v - w), atol + rtol * abs(w)
        e.require(budget > 0, "Positive budget required")
        results.append(
            dict(index=i, actual=v, reference=w, error=error, budget=budget, ratio=error / budget)
        )
    return dict(
        comparisons=len(results),
        max_error=max(v["error"] for v in results),
        worst=max(results, key=lambda v: v["ratio"]),
        failures=[v for v in results if v["ratio"] > 1],
    )


def sample(record, times):
    indices = []
    for t in times:
        matches = [i for i, v in enumerate(record["times_s"]) if abs(v - t) < 1e-15]
        e.require(len(matches) == 1, "Ambiguous/off-grid observation")
        indices.append(matches[0])
    return {k: [record[k][i] for i in indices] for k in ("states", "voltage_V")}


def state_checks(actual, expected, limits):
    amount, energy, voltage, relative = limits
    return {
        "amount": discrepancy(
            [v[:52] for v in actual["states"]],
            [v[:52] for v in expected["states"]],
            amount,
            relative,
        ),
        "energy": discrepancy(
            [v[52:] for v in actual["states"]],
            [v[52:] for v in expected["states"]],
            energy,
            relative,
        ),
        "voltage": discrepancy(actual["voltage_V"], expected["voltage_V"], voltage, relative),
    }


def refinement(errors, floor, ratio):
    e.require(
        len(errors) == 3 and all(math.isfinite(v) and v >= 0 for v in errors), "Refinement inputs"
    )
    return dict(
        errors=errors,
        floor=floor,
        passed=all(
            a <= floor or b <= ratio * a for a, b in zip(errors[:-1], errors[1:], strict=True)
        ),
        observed_orders=[
            math.log2(a / b) if min(a, b) > floor else None
            for a, b in zip(errors[:-1], errors[1:], strict=True)
        ],
    )


def bitwise_equal(left, right):
    return b"".join(struct.pack("<d", v) for v in e.flat(left)) == b"".join(
        struct.pack("<d", v) for v in e.flat(right)
    )


def canonical(arrays, index):
    def val(name):
        return arrays["observed_" + name]["values"][index]

    return (
        [val("amount_increment")[s][i] for i in range(7) for s in range(3)]
        + [val("extracellular_amount_increment")[s][0] for s in range(3)]
        + [val("leak_transferred")[s][i] for i in range(7) for s in range(3)]
        + val("pump_cycles")[:7]
        + val("dissipated_energy_pJ")[:7]
    )


def run_arrays(directory, sources):
    manifest = e.read(directory / "manifest.json")
    e.require(manifest["source_hashes"] == sources, "Run source identity")
    e.require(
        all(e.sha(directory / n) == h for n, h in manifest["files_sha256"].items()),
        "Run payload checksum",
    )
    return a.decode_npz(directory / "trajectory.npz")


def cells_records(packet, sources):
    e.require(
        len(packet["records"]) == 24 and len(packet["resumes"]) == 6, "Cells capture coverage"
    )
    for key, record in packet["records"].items():
        directory = CAPTURE / record["directory"]
        arrays = run_arrays(directory, sources)
        e.require(arrays["observation_times"]["values"] == record["times_s"], "Cells times link")
        e.require(
            [canonical(arrays, i) for i in range(len(record["times_s"]))] == record["states"],
            "Cells state summary link",
        )
        e.require(
            [v[:7] for v in arrays["observed_voltage_V"]["values"]] == record["voltage_V"],
            "Cells voltage summary link",
        )
        if key in packet["resumes"]:
            resume = packet["resumes"][key]
            restarted = run_arrays(CAPTURE / resume["directory"], sources)
            start = resume["start_step"]
            e.require(
                bitwise_equal(
                    arrays["accepted_times"]["values"][start:],
                    restarted["accepted_times"]["values"],
                ),
                "Restart time suffix",
            )
            for name in FIELDS:
                e.require(
                    arrays[name]["shape"][1:] == restarted[name]["shape"][1:]
                    and arrays[name]["dtype"] == restarted[name]["dtype"],
                    "Restart state axes/type",
                )
                e.require(
                    bitwise_equal(arrays[name]["values"][start:], restarted[name]["values"]),
                    "Restart state suffix",
                )
            layout = {
                name: v
                for name, v in arrays.items()
                if not name.startswith("observed_")
                and name not in FIELDS + ("accepted_times", "observation_times")
            }
            e.require(
                all(restarted[name] == value for name, value in layout.items()), "Restart layout"
            )
            snapshot = directory / f"snapshots/step-{start:06d}"
            manifest = e.read(snapshot / "manifest.json")
            e.require(
                manifest["source_hashes"] == sources
                and manifest["state_sha256"] == e.sha(snapshot / "state.npz"),
                "Checkpoint identity/bytes",
            )
            checkpoint = a.decode_npz(snapshot / "state.npz")
            # Trajectory exports name the ID axis "cell_ids"; complete-state
            # archives retain the layout field's canonical name "ids".
            checkpoint_layout = {
                "ids" if name == "cell_ids" else name: value for name, value in layout.items()
            }
            e.require(
                set(checkpoint) == set(checkpoint_layout) | set(FIELDS),
                "Checkpoint membership",
            )
            e.require(
                all(checkpoint[name] == value for name, value in checkpoint_layout.items()),
                "Checkpoint layout",
            )
            for name in FIELDS:
                e.require(
                    checkpoint[name]["shape"] == arrays[name]["shape"][1:]
                    and checkpoint[name]["dtype"] == arrays[name]["dtype"],
                    "Checkpoint state axes/type",
                )
                e.require(
                    bitwise_equal(checkpoint[name]["values"], arrays[name]["values"][start]),
                    "Checkpoint full state",
                )
    return packet["records"]


def diagnose(r, sources):
    plan, traj = r["protocol"], r["protocol"]["trajectory"]
    reference = e.read(CAPTURE / "reference.json")["records"]
    native = e.read(CAPTURE / "betse.json")["records"]
    cells = cells_records(e.read(CAPTURE / "cells.json"), sources)
    e.require(len(reference) == 18 and len(native) == 36, "Native/reference coverage")
    constraints, grids, energy, refinements = {}, {}, {}, {}
    for name, record in reference.items():
        e.require(
            record == e.read(CAPTURE / "reference" / name / "result.json"),
            "Independent-reference aggregate/individual link",
        )
        ident = name.split("/")[0]
        primary = reference[ident + "/" + plan["reference"]["primary"]]
        e.require(record["times_s"] == primary["times_s"], "Reference grid")
        limits = plan["reference"]
        checks = state_checks(
            record,
            primary,
            (
                limits["agreement_amount_fmol"],
                limits["agreement_energy_pJ"],
                limits["agreement_voltage_V"],
                0.0,
            ),
        )
        constraints.update({"reference/" + name + "/" + k: v for k, v in checks.items()})
    ledger = e.Ledger()
    native_steps = 0
    for variant in r["native_preparation"]["protocol"]["variants"]:
        ident = variant["id"]
        ref = sample(reference[ident + "/" + plan["reference"]["primary"]], plan["common_times_s"])
        ladders = {"native": [], "cells": []}
        finest = None
        for dt in plan["native_steps_s"]:
            key = ident + "/dt_" + format(dt, ".8g")
            row, quiet = (
                e.read(CAPTURE / native[key + "/" + mode]) for mode in ("observed", "unobserved")
            )
            e.require(
                set(row) == set(quiet)
                and all(row[k] == quiet[k] for k in row if k not in ("mode", "trace")),
                "Observer pair mismatch",
            )
            e.require(
                row["geometry"] == r["native_geometry"]
                and row["trace"]["initial"]["physical"] == r["native_initial"][ident]
                and row["dt_s"] == dt
                and row["steps"] == round(plan["duration_s"] / dt)
                and row["id"] == ident,
                "Initial geometry/state changed",
            )
            for array in (*row["histories"].values(), *row["final_arrays"].values()):
                e.array(array)
            points = native_energy.reconstruct(row, variant, plan["common_times_s"], ledger)
            native_steps += points["steps"]
            checks = state_checks(
                points,
                ref,
                (
                    traj["native_amount_fmol"],
                    traj["native_energy_pJ"],
                    traj["native_voltage_V"],
                    traj["relative"],
                ),
            )
            grids["native/" + key] = checks
            energy[key] = points["energy"]
            ladders["native"].append(checks)
            if dt == plan["native_steps_s"][-1]:
                finest = points
                constraints.update({ident + "/native_finest/" + k: v for k, v in checks.items()})
                constraints[ident + "/native_energy_balance"] = discrepancy(
                    points["energy"]["max_defect_pJ"],
                    0.0,
                    plan["accounting"]["native_finest_energy_pJ"],
                )
        for dt in plan["cells_steps_s"]:
            key = ident + "/dt_" + format(dt, ".8g") + "/jax_jit"
            row = cells[key]
            # State budget is unchanged; voltage has no relative allowance.
            checks = state_checks(
                row,
                ref,
                (
                    traj["cells_state_atol"],
                    traj["cells_state_atol"],
                    traj["cells_voltage_V"],
                    traj["cells_state_rtol"],
                ),
            )
            checks["voltage"] = discrepancy(
                row["voltage_V"], ref["voltage_V"], traj["cells_voltage_V"]
            )
            grids["cells/" + key] = checks
            ladders["cells"].append(checks)
            constraints.update({key + "/reference/" + k: v for k, v in checks.items()})
            if dt == plan["cells_steps_s"][-1]:
                factor = traj["cross_engine_budget_multiplier"]
                constraints.update(
                    {
                        ident + "/cross_engine/" + k: v
                        for k, v in state_checks(
                            finest,
                            row,
                            (
                                factor * traj["native_amount_fmol"],
                                factor * traj["native_energy_pJ"],
                                factor * traj["native_voltage_V"],
                                traj["relative"],
                            ),
                        ).items()
                    }
                )
        for engine, rows in ladders.items():
            for name, suffix in (("amount", "fmol"), ("energy", "pJ"), ("voltage", "V")):
                refinements[ident + "/" + engine + "/" + name] = refinement(
                    [v[name]["max_error"] for v in rows],
                    plan["refinement"][f"floor_{name}_{suffix}"],
                    plan["refinement"]["contraction_max"],
                )
        key = ident + "/dt_" + format(plan["cells_eager_step_s"], ".8g")
        eager, jit = cells[key + "/jax_eager"], cells[key + "/jax_jit"]
        constraints[ident + "/backends/state"] = discrepancy(
            eager["states"], jit["states"], 2e-12, 2e-11
        )
        constraints[ident + "/backends/voltage"] = discrepancy(
            eager["voltage_V"], jit["voltage_V"], 2e-10, 2e-11
        )
    for key, record in cells.items():
        diag = record["diagnostics"]
        for names, budget in (
            (
                (
                    "max_balance_error_fmol",
                    "max_extracellular_balance_error_fmol",
                    "max_global_balance_error_fmol",
                ),
                "cells_material_fmol",
            ),
            (("max_countercharge_error_C",), "cells_charge_C"),
            (("max_energy_balance_error_pJ",), "cells_energy_pJ"),
        ):
            constraints[key + "/reported/" + budget] = discrepancy(
                [diag[k] for k in names], [0.0] * len(names), plan["accounting"][budget]
            )
    e.require(native_steps == 1680, "Native update coverage")
    e.require(
        constraints["pump_leak/native_finest/energy"]["failures"],
        "Original first rejection not independently reproduced",
    )
    return dict(
        status="failed_pilot_diagnosed_not_qualified",
        constraints=constraints,
        failed_groups={k: v for k, v in constraints.items() if v["failures"]},
        failed_comparisons=sum(len(v["failures"]) for v in constraints.values()),
        comparisons=sum(v["comparisons"] for v in constraints.values()),
        native_flux_transfer_comparisons=ledger.count,
        native_flux_transfer_maxima=ledger.maxima,
        reference_error_ladders=grids,
        refinements=refinements,
        native_energy=energy,
        native_observed_steps=native_steps,
        observer_pairs=18,
        decoded_cells_trajectories=24,
        full_state_restart_suffixes=6,
        complete_checkpoint_links=6,
        energy_accounting_independently_reconstructed_for=(
            "native only; Cells diagnostics are source-bound saved reports"
        ),
        model_or_reference_rerun=False,
        qualified=False,
        tolerance_changed=False,
    )


def execute(output, tests):
    e.require(
        output.is_relative_to(e.ROOT / "runs")
        and output != e.ROOT / "runs"
        and not output.exists(),
        "Fresh diagnostic directory required",
    )
    receipt = e.software(tests, 15)
    start = time.monotonic()
    output.mkdir(parents=True)

    def deadline(_sig, _frame):
        raise TimeoutError("Bounded saved-data diagnosis exceeded 55 seconds")

    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, 55)
    try:
        with e.model_fence():
            r, sources = authenticate()
            files = inventory(CAPTURE)
            code = {
                str(p.relative_to(e.ROOT)): e.sha(p)
                for p in (
                    *HERE.glob("*.py"),
                    HERE.parent / "pump_loop_audit/evidence.py",
                    HERE.parent / "kinetic_family_audit/artifacts.py",
                )
            }
            e.write(
                output / "registration.json",
                dict(
                    schema="cells.failed_pump_pilot_diagnosis@1",
                    decision="D118",
                    created_utc=datetime.now(UTC).isoformat(),
                    original_registration_sha256=REGISTRATION,
                    original_failure_sha256=FAILURE,
                    failed_payload_sha256=files,
                    failure_payload_sealed_at_review_not_original_completion=True,
                    sources_sha256=code,
                    software=receipt,
                    timeout_seconds=55,
                    decimal_digits=70,
                    forbidden_imports=list(e.FORBIDDEN),
                ),
            )
            with zipfile.ZipFile(
                output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for name in code:
                    archive.write(e.ROOT / name, arcname=name)
            result = diagnose(r, sources)
            e.write(output / "diagnosis.json", result)
            authenticate()
            e.require(
                inventory(CAPTURE) == files
                and all(e.sha(e.ROOT / n) == h for n, h in code.items()),
                "Evidence/source changed during review",
            )
            e.write(
                output / "completion.json",
                dict(
                    status=result["status"],
                    elapsed_seconds=time.monotonic() - start,
                    finished_utc=datetime.now(UTC).isoformat(),
                    files_sha256=inventory(output),
                    failed_comparisons=result["failed_comparisons"],
                    failed_groups=list(result["failed_groups"]),
                    comparisons=result["comparisons"],
                    original_payload_files=len(files),
                    qualified=False,
                    automatic_followup=False,
                ),
            )
            return e.read(output / "completion.json")
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        e.write(
            output / "failure.json",
            dict(status="diagnosis_failed", traceback=traceback.format_exc()),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(execute(args.output.resolve(), args.tests.resolve()), sort_keys=True))
