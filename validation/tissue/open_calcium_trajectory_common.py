"""Artifact and comparison primitives for prepared full8us qualification roles.

No production equations or process launcher are imported here. Preparation and
future execution remain distinct; failed numerical states are preserved as-is.
"""

import hashlib
import json
import math
import os
import traceback
from pathlib import Path


def read_json(path):
    def reject(value):
        raise ValueError("Nonfinite JSON constant: " + value)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field: " + key)
            result[key] = value
        return result

    return json.loads(Path(path).read_text(), parse_constant=reject, object_pairs_hook=unique)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_bundle(bundle):
    """Check the entire frozen inventory without importing any model code."""
    bundle = Path(bundle).resolve()
    manifest = read_json(bundle / "manifest.json")
    expected = manifest["file_sha256"]
    actual = {
        str(p.relative_to(bundle))
        for p in bundle.rglob("*")
        if p.is_file() and p != bundle / "manifest.json"
    }
    if actual != set(expected):
        raise ValueError("Frozen bundle inventory changed")
    for name, checksum in expected.items():
        path = (bundle / name).resolve()
        if not path.is_relative_to(bundle) or sha(path) != checksum:
            raise ValueError("Frozen source/input hash changed: " + name)
    return manifest


def load_job(bundle, job_id, role):
    bundle = Path(bundle).resolve()
    verify_bundle(bundle)
    plan = read_json(bundle / "plan.json")
    protocol = read_json(bundle / "protocol.json")
    job = plan["jobs"][job_id]
    if job["role"] != role:
        raise ValueError("Wrong qualification role")
    raw = read_json(bundle / job["definition"])
    if digest(raw) != job["definition_sha256"]:
        raise ValueError("Role definition changed")
    if digest(physical_definition(raw)) != job["physics_sha256"]:
        raise ValueError("Role physics changed")
    return protocol, job, raw


def verify_result(directory):
    directory = Path(directory)
    record = read_json(directory / "result.json")
    if record["status"] != "passed" or (directory / "failure.json").exists():
        raise ValueError("Dependency role did not pass: " + str(directory))
    for name, checksum in record["artifacts"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or sha(path) != checksum:
            raise ValueError("Dependency artifact changed: " + str(path))
    return record


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def save_arrays(path, **arrays):
    import numpy as np

    path = Path(path)
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def physical_definition(raw):
    return {
        **raw,
        "execution": {k: v for k, v in raw["execution"].items() if k not in ("dt", "max_steps")},
    }


def control_times(raw):
    end = raw["experiment"]["end_time"]
    times = {0.0, end}
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                times.update(
                    row["time"] for row in group.get("controls", group.get("schedule", []))
                )
    if any(not math.isfinite(t) or not 0 <= t <= end for t in times):
        raise ValueError("Control clock outside the original horizon")
    return sorted(times)


def held_controls(raw, time):
    return {
        name: [
            next(
                row
                for row in reversed(group.get("controls", group.get("schedule", [])))
                if row["time"] <= time
            )
            for group in groups
        ]
        for name, groups in raw["experiment"].items()
        if name.endswith("_controls")
    }


def accepted_times(raw, dt):
    import numpy as np

    end = raw["experiment"]["end_time"]
    if not math.isfinite(dt) or dt <= 0 or end / dt > raw["execution"]["max_steps"]:
        raise ValueError("Invalid or excessive prepared step count")
    count = max(0, math.ceil(end / dt) - 1)
    while count > 0 and count * dt >= end:
        count -= 1
    values = sorted({i * dt for i in range(count + 1)} | set(control_times(raw)))
    if len(values) - 1 > raw["execution"]["max_steps"]:
        raise ValueError("Exact event-split grid exceeds prepared numerical quota")
    return np.asarray(values, dtype=float)


def error_budget(context, target, protocol):
    import numpy as np

    tolerance = protocol["tolerances"]
    absolute = np.concatenate(
        [
            np.full(
                math.prod(shape),
                tolerance["trajectory_charge_atol"]
                if name.endswith("_C")
                else tolerance["trajectory_state_atol"],
            )
            for name, shape in context["shapes"].items()
        ]
    )
    return absolute + tolerance["trajectory_rtol"] * np.abs(target)


def check_proof(proof, protocol):
    import numpy as np

    tolerance = protocol["tolerances"]
    groups = (
        (
            (
                "local_material_fmol",
                "outside_material_fmol",
                "chemical_ledger_fmol",
                "ionic_ownership_fmol",
                "nonionic_moiety_fmol",
                "ionic_global_fmol",
            ),
            tolerance["material_atol_fmol"],
        ),
        (
            ("pool_material_fmol", "adenylate_fmol", "phosphorus_fmol"),
            tolerance["pool_material_atol_fmol"],
        ),
        (
            ("capacitor_charge_C", "electrode_charge_C", "global_charge_C"),
            tolerance["charge_atol_C"],
        ),
        (
            ("reservoir_work_pJ", "electrode_work_pJ", "energy_residual_pJ", "pool_energy_pJ"),
            tolerance["energy_atol_pJ"],
        ),
    )
    metrics = {}
    for names, limit in groups:
        for name in names:
            value = np.asarray(proof[name])
            if not np.isfinite(value).all():
                raise ValueError("Nonfinite independent invariant: " + name)
            maximum = float(np.max(np.abs(value), initial=0.0))
            metrics[name] = maximum
            if maximum > limit:
                raise ValueError(f"Independent invariant {name}: {maximum!r} > {limit!r}")
    return metrics


def write_progress(stream, record):
    stream.write(json.dumps(record, allow_nan=False) + "\n")
    stream.flush()


def failure(directory, error, *, context=None, arrays=None):
    directory = Path(directory)
    if arrays:
        save_arrays(directory / "failed-trial.npz", **arrays)
    write_json(
        directory / "failure.json",
        dict(
            status="failed",
            type=type(error).__name__,
            message=str(error),
            traceback=traceback.format_exc(),
            context=context or {},
            raw_trial_archive="failed-trial.npz" if arrays else None,
            policy="no clipping, rebasing, partial acceptance or automatic retry",
        ),
    )


def success(directory, record):
    directory = Path(directory)
    artifacts = {
        str(path.relative_to(directory)): sha(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
        and path != directory / "result.json"
        and not path.name.endswith(".pending")
    }
    write_json(directory / "result.json", dict(status="passed", artifacts=artifacts, **record))
