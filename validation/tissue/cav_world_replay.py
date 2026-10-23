"""Capture CaV replay variability or verify a narrowly frozen numerical fix.

This is a bounded diagnostic, not a replacement qualification or a tolerance
change. Repeated runs distinguish run-to-run variability from a reproducible
scalar/batch difference. Every complete history is saved before comparison.
"""

import argparse
import hashlib
import json
import time
import traceback
from pathlib import Path

import numpy as np


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def parent_binding(parent):
    parent = Path(parent)
    registration = json.loads((parent / "registration.json").read_text())
    failure = json.loads((parent / "failure.json").read_text())
    if failure.get("status") != "failed" or failure.get("group") != "calcium-worlds":
        raise ValueError("Require the failed CaV independent-world qualification")
    if failure.get("phase") != "gpu" or (parent / "completion.json").exists():
        raise ValueError("Require incomplete GPU qualification evidence")
    for name, expected in registration["sources_sha256"].items():
        if digest(parent / "source" / name) != expected:
            raise ValueError("Frozen parent source changed: " + name)
    baseline = parent / "groups/gpu/calcium-worlds/tmp/resolved-calcium-cav-trajectories0/baseline"
    manifest = json.loads((baseline / "manifest.json").read_text())
    for name, expected in manifest["files_sha256"].items():
        if digest(baseline / name) != expected:
            raise ValueError("Parent baseline artifact changed: " + name)
    files = (
        "registration.json",
        "failure.json",
        "component-protocol.json",
        "gpu.runtime.json",
        "groups/gpu/calcium-worlds/tests.xml",
        "groups/gpu/calcium-worlds/stdout.log",
        "groups/cpu/calcium-worlds/qualified.json",
    )
    return dict(
        path=str(parent.resolve()),
        frozen_files=len(registration["sources_sha256"]),
        files_sha256={name: digest(parent / name) for name in files},
        baseline=str(baseline),
        baseline_manifest_sha256=digest(baseline / "manifest.json"),
        baseline_trajectory_sha256=digest(baseline / "trajectory.npz"),
    )


def comparisons(left, right, times):
    from validation.assembly.cluster_partition_replay import differences

    report = differences(left, right)
    earliest = None
    numerical_mismatches = 0
    for name, a in left.items():
        b = right[name]
        numerical_mismatches += int(np.count_nonzero(a != b))
        raw_a = np.ascontiguousarray(a).view(np.uint8).reshape(*a.shape, a.dtype.itemsize)
        raw_b = np.ascontiguousarray(b).view(np.uint8).reshape(*b.shape, b.dtype.itemsize)
        changed = np.argwhere(np.any(raw_a != raw_b, axis=-1))
        if len(changed):
            index = changed[0].tolist()
            if earliest is None or index[0] < earliest["step"]:
                earliest = dict(
                    field=name, indices=index, step=index[0], time_s=float(times[index[0]])
                )
    return report | dict(first_difference=earliest, unequal_values=numerical_mismatches)


def execution_source(record, parent):
    """An optional candidate may change only the two diagnosed source files."""
    candidate = record.get("candidate_source")
    if candidate is None:
        return parent / "source"
    from validation.assembly.qualify_cell import files

    source = Path(candidate["path"]).resolve()
    if source.is_relative_to(parent):
        raise ValueError("A candidate must not modify the failed parent's evidence")
    actual = files(source)
    expected = json.loads((parent / "registration.json").read_text())["sources_sha256"]
    if actual != candidate["sources_sha256"] or set(actual) != set(expected):
        raise ValueError("Candidate source manifest changed")
    changed = {name for name in expected if expected[name] != actual[name]}
    if changed != {
        "src/cells/numerics/extracellular_field.py",
        "src/cells/models/surface_kinetic.py",
    }:
        raise ValueError("Candidate differs outside the diagnosed channel accumulation")
    return source


def replay(root):
    import jax

    import cells
    from cells.assembly.io import runtime
    from cells.core.batch import BatchSpec, WorldSpec, run_batch
    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from cells.io import write_run
    from cells.models import surface_calcium_cav as model
    from tests.unit import test_surface_calcium_cav_full as adapter
    from tests.unit import test_surface_calcium_hcn_full as inherited
    from validation.tissue import surface_calcium_cav_fixtures as fixtures

    began = time.monotonic()
    record = json.loads((root / "registration.json").read_text())
    parent = Path(record["parent"]["path"])
    try:
        if parent_binding(parent) != record["parent"]:
            raise ValueError("Registered parent evidence changed")
        source = execution_source(record, parent)
        if not Path(cells.__file__).resolve().is_relative_to(source):
            raise ValueError("Replay must execute its registered frozen package")
        jax.config.update("jax_enable_x64", True)
        if runtime() != json.loads((parent / "gpu.runtime.json").read_text()):
            raise ValueError("GPU runtime differs from the failed parent")
        # Use the same adapter and fixture binding as the failed pytest node.
        inherited.fixtures = fixtures
        baseline = parse_spec(fixtures.definition(backend="gpu"))
        alternate = parse_spec(adapter.heterogeneous_definition(backend="gpu"))
        cases = {23: baseline, 41: alternate}
        write(root / "definitions.json", {str(k): s.to_dict() for k, s in cases.items()})
        results, timings = {}, {}

        def save(name, result):
            write_run(root / name, result)
            results[name] = {k: np.asarray(v) for k, v in result.history._asdict().items()}
            timings[name] = result.timings
            write(
                root / (name + "-finished.json"),
                dict(
                    status="captured",
                    elapsed_seconds=time.monotonic() - began,
                    checks=result.diagnostics,
                    timing=result.timings,
                ),
            )

        scalar = {}
        for identity, spec in cases.items():
            result = run(spec)
            scalar[identity] = result
            save(f"scalar-{identity}", result)
        # Identical parameters and executable shapes, fresh initial state.
        save("scalar-repeat-41", run(alternate))
        for name, order in (
            ("batch", (23, 41)),
            ("batch-repeat", (23, 41)),
            ("batch-reverse", (41, 23)),
        ):
            batch = run_batch(
                BatchSpec(tuple(WorldSpec(k, cases[k]) for k in order), 2, 4096, 2**32)
            )
            write(root / (name + "-resources.json"), batch.resources)
            for identity in order:
                save(f"{name}-{identity}", batch.worlds[identity])
        times = scalar[23].times
        with np.load(
            Path(record["parent"]["baseline"]) / "trajectory.npz", allow_pickle=False
        ) as archive:
            if not np.array_equal(times, archive["accepted_times"]):
                raise ValueError("Replay changed the parent integration grid")
            original = {k: archive[k] for k in model.STATE_TYPE._fields}
        reports = {"parent_baseline_to_repeat": comparisons(original, results["scalar-23"], times)}
        pairs = [("scalar-41", "scalar-repeat-41")]
        for identity in cases:
            pairs += [
                (f"scalar-{identity}", f"batch-{identity}"),
                (f"batch-{identity}", f"batch-repeat-{identity}"),
                (f"batch-{identity}", f"batch-reverse-{identity}"),
            ]
        for left, right in pairs:
            reports[left + "_to_" + right] = comparisons(results[left], results[right], times)
        if parent_binding(parent) != record["parent"]:
            raise ValueError("Parent evidence changed during diagnostic")
        execution_source(record, parent)
        reproduced = bool(reports["scalar-41_to_batch-41"]["different_fields"])
        varied = any(
            reports[k]["different_fields"]
            for k in (
                "scalar-41_to_scalar-repeat-41",
                "batch-23_to_batch-repeat-23",
                "batch-41_to_batch-repeat-41",
            )
        )
        candidate = "candidate_source" in record
        replay_pass = all(
            not v["different_fields"]
            for k, v in reports.items()
            if k != "parent_baseline_to_repeat"
        )
        finding = (
            ("replay_passed" if replay_pass else "replay_failed")
            if candidate
            else ("reproduced" if reproduced else "not_reproduced")
        )
        write(
            root / "diagnostic-result.json",
            dict(
                status="completed",
                finding=finding,
                identical_input_variability_observed=bool(varied),
                same_source_replay_pass=replay_pass,
                parent_baseline_comparison_scope="Cross-version information only for a candidate",
                comparisons=reports,
                timings=timings,
                elapsed_seconds=time.monotonic() - began,
                production_sources_changed=candidate,
                numerical_tolerances_changed=False,
                scope="Numerical replay diagnostic; no qualification or biological claim",
                automatic_followup=False,
            ),
        )
        if candidate and not replay_pass:
            raise ValueError("Candidate failed complete bitwise same-source replay")
    except BaseException:
        write(
            root / "diagnostic-failure.json",
            dict(
                status="failed",
                traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic() - began,
                automatic_followup=False,
            ),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    replay(parser.parse_args().output.resolve())
