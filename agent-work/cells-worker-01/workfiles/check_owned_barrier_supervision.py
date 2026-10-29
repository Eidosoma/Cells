"""Check fail-closed completion and startup ownership without numerical work."""

import argparse
import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument(
    "--runner", type=Path, default=Path(__file__).with_name("run_owned_barrier_transients.py")
)
args = parser.parse_args()
runner = args.runner.resolve()
digest = hashlib.sha256(runner.read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location("guarded_barrier_runner", runner)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
out = args.output.resolve()
out.mkdir(exist_ok=False)
counts = dict(tests=6, errors=0, failures=0, skipped=0)
base = dict(error=None, changed=[], counts=counts, completed=102, expected=102, pilot=False)
cases = [
    ("complete_full_suite", {}, True),
    ("missing_comparison", {"counts": counts | {"tests": 5}}, False),
    ("skipped_comparison", {"counts": counts | {"skipped": 1}}, False),
    ("failed_comparison", {"counts": counts | {"failures": 1}}, False),
    ("comparison_error", {"counts": counts | {"errors": 1}}, False),
    ("post_test_resource_failure", {"error": {"type": "ResourceLimit"}}, False),
    ("source_drift", {"changed": ["workspace/src/example.py"]}, False),
    ("unfinished_units", {"completed": 101}, False),
    ("pilot_success", {"pilot": True, "counts": {}}, True),
    ("pilot_failure", {"pilot": True, "error": {"type": "ResourceLimit"}}, False),
]
records = []
for name, changes, expected in cases:
    actual = module.completed_successfully(**(base | changes))
    assert actual is expected, (name, actual, expected)
    records.append(dict(name=name, passed=True))


def run_failure(name, claimed_digest, existing=False, *, mode="--execute"):
    target = out / name
    sentinel = b"existing result must remain byte-exact\n"
    if existing:
        target.mkdir()
        (target / "result.json").write_bytes(sentinel)
    command = [
        sys.executable,
        "-B",
        str(runner),
        mode,
        "--bundle",
        str(out / "deliberately-missing-bundle"),
        "--output",
        str(target),
    ] + ([] if claimed_digest is None else ["--runner-sha256", claimed_digest])
    result = subprocess.run(command, capture_output=True, timeout=20)
    (out / (name + ".stdout")).write_bytes(result.stdout)
    (out / (name + ".stderr")).write_bytes(result.stderr)
    assert result.returncode != 0
    if existing:
        assert sorted(p.name for p in target.iterdir()) == ["result.json"]
        assert (target / "result.json").read_bytes() == sentinel
    else:
        for file in ("failure.json", "result.json", "job-status.json"):
            data = json.loads((target / file).read_text())
            assert data["status"] == "failed"
            if file != "job-status.json":
                assert data["full_trajectory_credit"] is False
    records.append(dict(name=name, passed=True, returncode=result.returncode))


run_failure("startup_bundle_failure", digest)
run_failure("supervisor_hash_refusal", "0" * 64)
run_failure("existing_output_preserved", digest, existing=True)
run_failure("pilot_startup_bundle_failure", digest, mode="--pilot")
run_failure("pilot_supervisor_hash_refusal", "0" * 64, mode="--pilot")
run_failure("pilot_missing_supervisor_hash", None, mode="--pilot")
reviewed = Path("/mnt/workspaces/Cells/owned-barrier-refinement-supervision-20261029-01/runner.py")
assert ast.dump(ast.parse(runner.read_text()), include_attributes=False) == ast.dump(
    ast.parse(reviewed.read_text()), include_attributes=False
)
records.append(dict(name="reviewed_supervisor_AST_exact", passed=True))
receipt = dict(
    status="passed",
    runner_sha256=digest,
    checks=records,
    numerical_work_run=False,
    full_trajectory_credit=False,
    reviewed_supervisor_sha256=hashlib.sha256(reviewed.read_bytes()).hexdigest(),
)
(out / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(dict(status="passed", checks=len(records), runner_sha256=digest)))
