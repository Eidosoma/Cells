"""Execute frozen NUM-007 coupled-channel trials, retaining candidate rejections."""

import argparse
import hashlib
import io
import json
import os
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests import reference_voltage_gated_dynamics as ref  # noqa: E402
from tests import voltage_gated_numerical_checks as checks  # noqa: E402

SOURCE_FILES = (
    "configs/reference/multispecies_membrane_v1.json",
    "configs/reference/voltage_gated_channel_v1.json",
    "configs/reference/voltage_gated_trajectories_v1.json",
    "docs/VOLTAGE_GATED_CHANNEL_SPEC.md",
    "docs/VOLTAGE_GATED_NUMERICS.md",
    "tests/reference_multispecies.py",
    "tests/reference_multispecies_dynamics.py",
    "tests/multispecies_numerical_checks.py",
    "tests/reference_voltage_gated_channel.py",
    "tests/reference_voltage_gated_dynamics.py",
    "tests/voltage_gated_numerical_checks.py",
    "tests/unit/test_voltage_gated_dynamics.py",
    "tests/unit/test_voltage_gated_artifact_audit.py",
    "scripts/qualify_voltage_gated_reference.py",
    "scripts/audit_voltage_gated_reference.py",
    "scripts/audit_multispecies_reference.py",
    "pyproject.toml",
    "requirements-lock.txt",
    "requirements-reference.txt",
)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


class Artifacts:
    def __init__(self, path, quota):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=False)
        self.quota = quota
        self.used = 0
        self.hashes = {}

    def write(self, name, payload, *, closing=False):
        reserve = 0 if closing else 65536
        if self.used + len(payload) > self.quota - reserve:
            raise ref.ResourceLimit("Scientific artifact budget exhausted")
        target = self.path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(payload)
        self.used += len(payload)
        self.hashes[name] = sha(payload)

    def json(self, name, value, *, closing=False):
        self.write(name, json_bytes(value), closing=closing)

    def arrays(self, name, arrays):
        buffer = io.BytesIO()
        np.savez_compressed(buffer, **arrays)
        self.write(name, buffer.getvalue())


def capture_sources():
    buffer = io.BytesIO()
    hashes = {}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            payload = (ROOT / name).read_bytes()
            hashes[name] = sha(payload)
            archive.writestr(name, payload)
    return buffer.getvalue(), hashes


def run(output):
    plan, cases = ref.load_panel()
    archive, source_hashes = capture_sources()
    artifacts = Artifacts(output, plan["resources"]["artifact_bytes"])
    artifacts.write("sources.zip", archive)
    artifacts.write("protocol.json", ref.PANEL.read_bytes())
    artifacts.json("cases.json", [case.definition() for case in cases])
    started, analyses, summaries = monotonic(), {}, {}
    deadline = started + plan["resources"]["session_wall_seconds"]
    artifacts.json(
        "session.json",
        {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "protocol_sha256": ref.PANEL_SHA256,
            "source_sha256": source_hashes,
            "resources": plan["resources"],
            "runtime": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "cpu_affinity": sorted(os.sched_getaffinity(0)),
                "thread_environment": {
                    name: os.environ.get(name)
                    for name in (
                        "OMP_NUM_THREADS",
                        "OPENBLAS_NUM_THREADS",
                        "MKL_NUM_THREADS",
                        "NUMEXPR_NUM_THREADS",
                    )
                },
            },
            "state_layout": (
                "sample_state: [amount increments S, baseline ledgers S, cycles, "
                "dissipation pJ, m, h, channel ledger]"
            ),
            "native_coordinates": {
                "Radau": "increments",
                "BDF": "increments",
                "RK4": "absolute_amounts",
            },
            "dense_basis": (
                "Radau/RK4 normalized-time power coefficients; BDF Newton coefficients and factors"
            ),
        },
    )
    current_case, current_attempt = None, None
    try:
        for case in cases:
            current_case, records, stats = case.id, {}, {}
            samples = ref.comparison_grid(case, plan["candidate"])
            attempts = [(s["id"], s) for s in plan["references"]]
            attempts.extend((f"rk4_{dt:g}", dt) for dt in plan["candidate"]["steps_s"])
            for name, setting in attempts:
                current_attempt = name
                print(f"{case.id}: {name}", flush=True)
                budget = ref.Budget(
                    deadline=deadline, max_calls=plan["resources"]["max_rhs_calls_per_attempt"]
                )
                if isinstance(setting, dict):
                    arrays, stats[name] = ref.integrate_reference(case, setting, budget=budget)
                    kind = setting["method"]
                else:
                    arrays, stats[name] = ref.integrate_candidate(case, setting, budget=budget)
                    kind = "RK4"
                budget.check()
                if stats[name]["status"] == "complete":
                    sampled_times = samples
                    observed = ref.sample_record(case, arrays, kind, samples)
                else:
                    sampled_times = np.empty(0)
                    observed = np.empty((0, case.size))
                records[name] = {
                    **arrays,
                    "sample_times_s": sampled_times,
                    "sample_state": observed,
                }
                artifacts.arrays(f"{case.id}/{name}.npz", records[name])
                artifacts.json(f"{case.id}/{name}.json", stats[name])
            analyses[case.id] = checks.analyze_case(case.definition(), records, stats, plan)
            artifacts.json(f"{case.id}/analysis.json", analyses[case.id])
            p, count = case.parameters, case.species_count
            final = records["refined"]["sample_state"][-1]
            summaries[case.id] = {
                "samples": len(samples),
                "final_amount_fmol": (np.asarray(p.initial_amount_fmol) + final[:count]).tolist(),
                "final_voltage_V": float(checks.voltage(case.definition(), final[:count])),
                "final_pump_cycles_fmol": float(final[2 * count]),
                "final_dissipation_pJ": float(final[2 * count + 1]),
                "final_gate": final[case.gate_start : case.gate_start + 2].tolist(),
                "final_channel_fmol": float(final[-1]),
                "attempts": stats,
            }
            print(f"{case.id}: references_pass={analyses[case.id]['references_pass']}", flush=True)
        checks.require(monotonic() < deadline, "Scientific session wall-time budget exhausted")
        checks.require(
            all(
                sha((ROOT / name).read_bytes()) == digest for name, digest in source_hashes.items()
            ),
            "Captured source changed during the scientific session",
        )
        selection = checks.select_candidate(analyses, plan)
        receipt = {
            **selection,
            "scope": plan["scope"],
            "seconds": monotonic() - started,
            "completed_cases": list(analyses),
            "cases": summaries,
            "protocol_sha256": ref.PANEL_SHA256,
            "source_sha256": source_hashes,
            "files_sha256": dict(artifacts.hashes),
            "artifact_bytes_before_receipt": artifacts.used,
            "production_change": False,
            "rejected_candidates": sum(
                s["status"] == "rejected"
                for item in summaries.values()
                for s in item["attempts"].values()
            ),
            "gpu_qualification": "not_performed",
            "biological_acceptance": "not_assessable",
        }
        artifacts.json("verification.json", receipt, closing=True)
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "selected_dt_s": receipt["selected_dt_s"],
                    "cases": len(analyses),
                    "seconds": receipt["seconds"],
                    "artifact_bytes": artifacts.used,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return receipt
    except Exception as error:
        artifacts.json(
            "failure.json",
            {
                "status": "stopped",
                "case": current_case,
                "attempt": current_attempt,
                "error_type": type(error).__name__,
                "reason": str(error),
                "completed_cases": list(analyses),
                "files_sha256": dict(artifacts.hashes),
                "seconds": monotonic() - started,
                "production_change": False,
            },
            closing=True,
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="A new session directory")
    args = parser.parse_args()
    return 0 if run(args.output)["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
