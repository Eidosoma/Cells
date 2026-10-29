"""Retain full arrays for the original 31.25 ns transient accuracy failure."""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(path, name):
    tree = ast.parse(path.read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.dump(node, include_attributes=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    original = Path("/mnt/workspaces/Cells/owned-calcium-phase-development-20261029-02")
    report = json.loads((original / "result.json").read_text())
    assert report["tests"] == dict(tests=1, errors=0, failures=1, skipped=0)
    runtime = (
        "src/cells/core/owned_calcium_profile_phase_handoff.py",
        "src/cells/core/surface_calcium_profile_epoch_spec.py",
        "src/cells/core/surface_calcium_energy_profile_epoch_spec.py",
        "src/cells/models/surface_calcium_profile_epoch.py",
        "src/cells/models/surface_calcium_energy_profile_epoch.py",
    )
    for name in runtime:
        assert sha(root / name) == report["source_sha256"][name]
    test = "tests/unit/test_owned_calcium_profile_phase_handoff.py"
    oracle = "validation/topology/owned_calcium_profile_phase_handoff_reference.py"
    for path, names in (
        (test, ("integrate_host", "source_run", "source_checkpoint", "prepared", "compare")),
        (oracle, ("initial", "integrate")),
    ):
        for name in names:
            assert function(root / path, name) == function(original / "sources" / path, name)
    os.environ["CELLS_COMPONENT_EVIDENCE"] = str(output / "evidence")
    from tests.unit import test_owned_calcium_profile_phase_handoff as check

    assert check.source_run.cache_info().currsize == check.prepared.cache_info().currsize == 0
    # This is a local fixture override in this fresh process. Canonical files,
    # accepted fine-step evidence and every constitutive equation stay unchanged.
    check.fixtures.DT = 0.03125e-6
    failure = None
    try:
        check.test_carried_SIM_every_observation_refines_and_preserves_accounting(
            "fuel5", "changed-controls"
        )
    except AssertionError as error:
        failure = str(error)
    assert failure is not None, "Expected original coarse accuracy failure did not recur"
    name = "owned-calcium-epoch-SIM-refinement-fuel5-changed-controls-failure"
    record_path = output / "evidence" / (name + ".json")
    record = json.loads(record_path.read_text())
    assert record["status"] == "failed" and record["reason"] == "full-state accuracy budget"
    ratio = float(record["error"])
    assert abs(ratio - 4.1302162705663) < 1e-6 and record["dt_s"] == 0.03125e-6
    arrays = output / "evidence" / record["arrays_file"]
    with check.np.load(arrays, allow_pickle=False) as data:
        assert data["production_flat_1"].shape == data["reference_flat"].shape == (21, 897)
        assert "1__chemical_amount_increment" in data and "1__energy_amount_increment_fmol" in data
    result = dict(
        status="expected_accuracy_failure_reproduced",
        original_failed_receipt=str(original / "result.json"),
        original_failed_receipt_sha256=sha(original / "result.json"),
        original_runtime_unchanged=True,
        original_integration_and_oracle_functions_unchanged=True,
        local_fixture_dt_s=0.03125e-6,
        physical_tolerances_changed=False,
        error_over_unchanged_budget=ratio,
        failure_record=dict(path=str(record_path), sha256=sha(record_path)),
        arrays=dict(path=str(arrays), sha256=sha(arrays)),
        counted_as_passing_scientific_case=False,
    )
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(status=result["status"], error_over_budget=ratio, arrays=str(arrays))))


if __name__ == "__main__":
    main()
