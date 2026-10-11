"""Run the maintained NUM-009 v2 matrix with explicit historical test routing.

The original production driver and v1 source-bound files are not edited.
The v1 complete-session suite is prospective and has no complete evidence.
Its maintained v2 counterpart runs; v1 preflight/stopped-evidence tests also run.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import test_cells_build as previous  # noqa: E402

DRIVER_SHA256 = "4102a34c4d31e2599ee40b684e31af4f5598a5b6f61b13fc8b39189169d15b99"
V1_PROSPECTIVE = "tests/unit/test_finite_extracellular_artifact_audit.py"
V2_COMPLETE = "tests/unit/test_finite_extracellular_artifact_audit_v2.py"


def run_tests(output):
    if previous.sha(ROOT / "scripts/test_cells_build.py") != DRIVER_SHA256:
        raise ValueError("Accepted production test driver changed")
    if os.environ.get("PYTEST_ADDOPTS") or os.environ.get("PYTEST_PLUGINS"):
        raise ValueError("Require explicit test routing without inherited pytest overrides")
    failure = ROOT / "runs/num-009-2026-09-10/reference-01/failure.json"
    if previous.sha(failure) != "7dd501991ab3c61144d3f8862f91a8b76c146619e5c554b2b9fd46a5c87f3e67":
        raise ValueError("Historical v1 stopped attempt changed")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    print("Historical v1 complete-session tests: unexecuted (no complete v1 evidence).", flush=True)
    print("Maintained v2 complete-session and v1 stopped-evidence tests: included.", flush=True)
    old_options = os.environ.get("PYTEST_ADDOPTS")
    try:
        os.environ["PYTEST_ADDOPTS"] = f"--ignore={V1_PROSPECTIVE}"
        current = previous.run_tests(output / "current", only="current")
    finally:
        if old_options is None:
            os.environ.pop("PYTEST_ADDOPTS", None)
        else:
            os.environ["PYTEST_ADDOPTS"] = old_options
    historical = previous.run_tests(output / "historical", only="reference")
    contexts = current["contexts"] | historical["contexts"]
    result = {
        "schema": "cells.finite_extracellular_build_matrix@1",
        "status": "pass" if current["status"] == historical["status"] == "pass" else "failed",
        "contexts": contexts,
        "total_tests": current["total_tests"] + historical["total_tests"],
        "unexecuted_prospective_suite": {
            "file": V1_PROSPECTIVE,
            "sha256": previous.sha(ROOT / V1_PROSPECTIVE),
            "tests": 13,
            "reason": "V1 stopped unqualified and has no complete session; not passing coverage.",
            "maintained_replacement": V2_COMPLETE,
        },
        "current_pytest_addopts": f"--ignore={V1_PROSPECTIVE}",
        "historical_pytest_addopts": None,
        "underlying_driver_sha256": DRIVER_SHA256,
        "driver_sha256": previous.sha(__file__),
        "child_receipts_sha256": {
            name: previous.sha(output / name / "verification.json")
            for name in ("current", "historical")
        },
    }
    with (output / "verification.json").open("x") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_tests(args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    raise SystemExit(0 if receipt["status"] == "pass" else 1)
