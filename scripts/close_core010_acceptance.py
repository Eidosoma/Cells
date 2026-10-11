"""Seal recorded development acceptance; stable release promotion remains separate."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.core.specs import read_json  # noqa: E402
from cells.io import _sha256 as sha  # noqa: E402
from cells.io import _write_json as write_json  # noqa: E402
from cells.io import runtime_identity, source_hashes  # noqa: E402
from scripts.audit_spatial_extracellular_build import implementation  # noqa: E402
from scripts.spatial_extracellular_acceptance_resources import from_registration  # noqa: E402
from scripts.spatial_extracellular_production_audit import authenticate, require  # noqa: E402
from scripts.test_spatial_extracellular_build import implementation_hashes  # noqa: E402


def close(session, audit_path, matrix_path, output):
    resources = from_registration(read_json(session / "registration.json"))
    baseline_path = resources.baseline
    baseline = read_json(baseline_path)["files_sha256"]
    require(all((ROOT / p).is_file() for p in baseline), "Pre-existing worktree files are missing")
    changed = {
        p: {"before": v, "after": sha(ROOT / p)} for p, v in baseline.items() if sha(ROOT / p) != v
    }
    require(
        set(changed) <= resources.allowed_edits,
        "Unexpected change to existing implementation/evidence",
    )
    receipt, audited, matrix = (
        read_json(session / "verification.json"),
        read_json(audit_path),
        read_json(matrix_path),
    )
    require(
        receipt["status"] == audited["status"] == matrix["status"] == "pass",
        "Acceptance/audit/matrix did not pass",
    )
    authenticate(session, receipt["files_sha256"], extra=("verification.json",))
    require(
        audited["verification_sha256"] == sha(session / "verification.json"),
        "Independent audit identity differs",
    )
    require(
        receipt["implementation_files_sha256"] == implementation(resources)
        and matrix["implementation_sha256"] == implementation_hashes(),
        "Acceptance/matrix source contexts differ",
    )
    require(
        receipt["source_hashes"] == source_hashes() and receipt["runtime"] == runtime_identity(),
        "Production context differs",
    )
    previous = read_json(ROOT / "reports/core-010-implementation-closeout.json")
    require(
        previous["source_hashes"] == source_hashes(), "Production bytes changed in acceptance slice"
    )
    quality = {}
    for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
        worker = subprocess.run(
            [str(ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        quality[name] = worker.stdout.strip()
    paths = (
        subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .split("\0")
    )
    new = {
        p: sha(ROOT / p) for p in sorted(set(paths) - set(baseline) - {""}) if (ROOT / p).is_file()
    }
    result = {
        "schema": "cells.core010_recorded_development_closeout@1",
        "status": "pass",
        "scope": (
            "Recorded passive spatial CPU/JAX development acceptance; "
            "stable release promotion is separate"
        ),
        "stable_release_accepted": False,
        "resource_plan": resources.name,
        "accepted_stable_version": "0.14.0",
        "development_version": runtime_identity()["cells_version"],
        "production_modules_unchanged": len(source_hashes()),
        "source_hashes": source_hashes(),
        "runtime": runtime_identity(),
        "baseline_sha256": sha(baseline_path),
        "baseline_files": len(baseline),
        "unchanged_baseline_files": len(baseline) - len(changed),
        "changed_baseline_files": changed,
        "new_workspace_files_sha256_before_receipt": new,
        "acceptance": audited,
        "independent_audit_sha256": sha(audit_path),
        "regression": {
            "verification_sha256": sha(matrix_path),
            "total_tests": matrix["total_tests"],
            "contexts": matrix["contexts"],
        },
        "quality": quality,
        "biological_validation": False,
        "gpu_tested": False,
        "next_gate": (
            "Preserve accepted development source/artifacts; promote a stable version "
            "with explicit source/replay closeout"
        ),
    }
    write_json(output, result)
    return {
        k: result[k]
        for k in (
            "status",
            "production_modules_unchanged",
            "baseline_files",
            "unchanged_baseline_files",
            "stable_release_accepted",
        )
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(close(args.session, args.audit, args.matrix, args.output), sort_keys=True))
