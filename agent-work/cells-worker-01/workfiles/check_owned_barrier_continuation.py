"""Exercise frozen continuation branches with zero new time/RHS integrations."""

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.bundle / "workspace"
    sys.path[:0] = [str(workspace / "src"), str(workspace)]
    spec = importlib.util.spec_from_file_location(
        "frozen_barrier_helpers", workspace / "tests/owned_barrier_transient_helpers.py"
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    assert helper.read(args.pilot / "result.json")["status"] == "passed"
    assert helper.read(args.pilot / "result.json")["bundle_manifest_sha256"] == helper.sha(
        args.bundle / "manifest.json"
    )
    args.output.mkdir(parents=True, exist_ok=False)
    for role in ("reference", "production"):
        for factor in (1, 2):
            source = helper.location(args.pilot, "energy-reseal", role, factor, 0, pilot=True)
            target = helper.location(args.output, "energy-reseal", role, factor, 0, pilot=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            for suffix in (".json", ".npz"):
                shutil.copyfile(source.with_suffix(suffix), target.with_suffix(suffix))
    end = 8 * helper.fixtures.DT_S
    # Explicitly synthetic zero-length windows test only the two checkpoint
    # branches. The complete 10us input and frozen equations stay untouched.
    helper.fixtures.window = lambda raw, chunk, pilot=False: (
        (0.0, end, [0.0, end]) if chunk == 0 else (end, end, [end])
    )
    proofs = []
    for role, runner in (
        ("reference", helper.run_reference),
        ("production", helper.run_production),
    ):
        for factor in (1, 2):
            original_meta, original = helper.load(
                helper.location(args.output, "energy-reseal", role, factor, 0, pilot=True)
            )
            for chunk in (0, 1):
                runner(args.bundle, args.output, "energy-reseal", factor, chunk)
                meta, actual = helper.load(
                    helper.location(args.output, "energy-reseal", role, factor, chunk)
                )
                if chunk == 0:
                    np.testing.assert_array_equal(actual["state_flat"], original["state_flat"])
                else:
                    np.testing.assert_array_equal(
                        actual["state_flat"][0], original["state_flat"][-1]
                    )
                if role == "reference":
                    assert meta["proof"]["rhs_evaluations"] == 0
                else:
                    for key in original["state_fields"].tolist():
                        np.testing.assert_array_equal(
                            actual["grid__" + key][-1], original["grid__" + key][-1]
                        )
                    for key, value in original.items():
                        if key.startswith("layout__"):
                            np.testing.assert_array_equal(actual[key], value)
                proofs.append(
                    dict(
                        role=role,
                        factor=factor,
                        chunk=chunk,
                        exact_complete_state=True,
                        exact_layout=role == "production",
                        new_time_s=0.0,
                        report=str(
                            helper.location(
                                args.output, "energy-reseal", role, factor, chunk
                            ).with_suffix(".json")
                        ),
                    )
                )
    helper.write(
        args.output / "result.json",
        dict(
            status="passed",
            checks=proofs,
            new_integration_time_s=0.0,
            reference_rhs_evaluations=0,
            scientific_scope="checkpoint preservation only; no new trajectory or refinement credit",
            bundle_manifest_sha256=helper.sha(args.bundle / "manifest.json"),
            pilot_result_sha256=helper.sha(args.pilot / "result.json"),
        ),
    )
    print(
        json.dumps(
            dict(
                status="passed",
                new_checkpoint_preservation_checks=len(proofs),
                result=str(args.output / "result.json"),
            )
        )
    )


if __name__ == "__main__":
    main()
