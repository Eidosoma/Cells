"""Preserve the failed cluster's missing scalar endpoints without altering its evidence.

Executed with the parent's frozen Cells package. Only the two missing scalar
trajectories are recomputed; the original two-world endpoint is authenticated
and reused. This diagnostic expects the original exact replay failure and is
not numerical acceptance of that implementation.
"""

import argparse
import json
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from cells.assembly.io import digest, runtime, write_json

FILES = (
    "registration.json",
    "failure.json",
    "cpu.xml",
    "cpu.runtime.json",
    "cluster-evidence/cpu/baseline.json",
    "cluster-evidence/cpu/baseline.npz",
)


def parent_binding(parent):
    parent = Path(parent).resolve()
    registration = json.loads((parent / "registration.json").read_text())
    failure = json.loads((parent / "failure.json").read_text())
    if failure["status"] != "failed" or (parent / "completion.json").exists():
        raise ValueError("Partition replay requires the failed cluster qualification")
    cases = ET.parse(parent / "cpu.xml").getroot().iter("testcase")
    failures = [
        case
        for case in cases
        if case.attrib["name"]
        == "test_complete_restart_windows_world_partition_and_pool_independence"
        and case.find("failure") is not None
    ]
    if (
        len(failures) != 1
        or "ionic_face_dissipated_energy_pJ" not in failures[0].find("failure").text
    ):
        raise ValueError("Parent does not contain the expected energy-ledger replay failure")
    for name, expected in registration["sources_sha256"].items():
        if digest(parent / "source" / name) != expected:
            raise ValueError("Frozen parent source changed: " + name)
    return {
        "path": str(parent),
        "files_sha256": {name: digest(parent / name) for name in FILES},
        "frozen_source_files": len(registration["sources_sha256"]),
    }


def differences(a, b):
    """Compare all raw bits, then quantify finite float differences separately."""
    if set(a) != set(b):
        raise ValueError("Partition endpoints contain different state fields")
    report, compared = {}, 0
    for key, left in a.items():
        right = b[key]
        if left.shape != right.shape or left.dtype != right.dtype:
            raise ValueError("Partition endpoint shape/dtype mismatch: " + key)
        left_bytes = np.ascontiguousarray(left).view(np.uint8).reshape(-1, left.dtype.itemsize)
        right_bytes = np.ascontiguousarray(right).view(np.uint8).reshape(-1, right.dtype.itemsize)
        changed = np.any(left_bytes != right_bytes, axis=1).reshape(left.shape)
        compared += left.size
        if not changed.any():
            continue
        row = {"different_scalars": int(changed.sum()), "shape": list(left.shape)}
        if left.dtype == np.float64:
            finite = np.isfinite(left) & np.isfinite(right)
            if np.any(changed & ~finite):
                raise ValueError("Nonfinite endpoint mismatch: " + key)
            x, y = left[changed], right[changed]

            def ordered(values):
                bits = values.view(np.uint64)
                sign = np.uint64(1 << 63)
                return np.where((bits & sign) != 0, ~bits, bits ^ sign)

            u, v = ordered(x), ordered(y)
            delta = np.abs(x - y)
            row.update(
                max_absolute_difference=float(delta.max()),
                max_ulp_difference=int((np.maximum(u, v) - np.minimum(u, v)).max()),
                first_indices=np.argwhere(changed)[:8].tolist(),
                first_left=x[:8].tolist(),
                first_right=y[:8].tolist(),
            )
        report[key] = row
    return {"compared_scalars": compared, "different_fields": report}


def replay(root):
    from cells.assembly_cell.io import flatten, source_identity
    from cells.assembly_cluster import engine
    from cells.assembly_cluster.spec import parse_spec
    from cells.ensemble.families import bind_definition

    started = time.monotonic()
    output = root / "partition-parent-replay"
    output.mkdir()
    try:
        registered = json.loads((root / "registration.json").read_text())["partition_parent"]
        parent = Path(registered["path"])
        if parent_binding(parent) != registered:
            raise ValueError("Registered parent evidence changed")
        if runtime() != json.loads((parent / "cpu.runtime.json").read_text()):
            raise ValueError("Parent replay CPU runtime changed")
        old_registration = json.loads((parent / "registration.json").read_text())
        expected_sources = {
            name.removeprefix("src/cells/"): value
            for name, value in old_registration["sources_sha256"].items()
            if name.startswith("src/cells/") and name.endswith(".py")
        }
        if source_identity() != expected_sources:
            raise ValueError("Replay did not load the registered parent's frozen package")
        baseline = json.loads((parent / "cluster-evidence/cpu/baseline.json").read_text())
        spec = parse_spec(baseline["definition"])
        if spec.fingerprint != baseline["definition_sha256"] or spec.pool.worlds != 2:
            raise ValueError("Unexpected parent baseline definition")
        with np.load(parent / "cluster-evidence/cpu/baseline.npz", allow_pickle=False) as arrays:
            saved = {k: arrays[k].copy() for k in arrays.files}
        np.savez_compressed(output / "parent-batch.npz", **saved)
        parts = []
        for index in range(spec.pool.worlds):
            definition = bind_definition(
                spec.to_dict(),
                worlds=1,
                world_id_start=spec.pool.world_id_start + index,
                seed=(spec.pool.seed - spec.pools[0].stream_id) % 2**32,
            )
            state, result = engine.run(parse_spec(definition), backend="cpu")
            arrays = flatten(state)
            np.savez_compressed(output / f"world-{index}.npz", **arrays)
            write_json(output / f"world-{index}.json", result | {"definition": definition})
            parts.append(arrays)
        scalar = {key: np.concatenate([p[key] for p in parts]) for key in saved}
        np.savez_compressed(output / "partition-combined.npz", **scalar)
        compared = differences(saved, scalar)
        # The failure must be reproduced, not retrospectively accepted under a
        # numerical tolerance. Record any additional differences before refusal.
        write_json(output / "comparison.json", compared)
        if "ionic_face_dissipated_energy_pJ" not in compared["different_fields"]:
            raise ValueError("Expected parent's exact energy-ledger mismatch was not reproduced")
        result = {
            "status": "original_partition_failure_reproduced",
            "elapsed_seconds": time.monotonic() - started,
            "parent": registered,
            **compared,
            "scientific_acceptance": False,
            "outputs_sha256": {p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()},
        }
        write_json(output / "result.json", result)
        return result
    except BaseException as exc:
        write_json(
            output / "failure.json",
            {
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "elapsed_seconds": time.monotonic() - started,
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    print(json.dumps(replay(parser.parse_args().root.resolve()), indent=2))
