"""CORE-005a: exact accepted-0.8.0 regressions and independently audited chunks.

This verification driver reads saved baseline traces in memory. That is not
part of the production window runner or its separate memory profile.
"""

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.batch_io import load_batch_snapshot, write_batch_run  # noqa: E402
from cells.core.batch import load_batch, run_batch  # noqa: E402
from cells.core.grid import EventGrid  # noqa: E402
from cells.core.runner import run, validate_checkpoint  # noqa: E402
from cells.core.schedule import event_index  # noqa: E402
from cells.core.specs import ConfigError, load_spec  # noqa: E402
from cells.core.state import Checkpoint  # noqa: E402
from cells.core.windows import WindowPolicy  # noqa: E402
from cells.io import _sha256 as sha  # noqa: E402
from cells.io import _write_json as write_json  # noqa: E402
from cells.io import load_snapshot, runtime_identity, source_hashes  # noqa: E402
from cells.models.registry import get_model  # noqa: E402
from cells.window_io import write_windowed_run  # noqa: E402

BASE = ROOT / "runs/core-004-2026-09-08"
RELEASE_SHA = "6a166ea315a33fbb24e85b93b4f548b08c1dabf7ac13766a0f4a82ce74201b96"
ARCHIVE = ROOT / "reports/cells-0.8.0-source.tar.gz"
ARCHIVE_SHA = "5f49ac0fde1af95b47977d6310f9e4eeddc048456006d21a9ba7c30d4449bdad"


def payloads(path, *, current):
    manifest = json.loads((path / "manifest.json").read_text())
    if current:
        assert manifest["source_hashes"] == source_hashes()
        assert manifest["runtime"] == runtime_identity()
    for name, checksum in manifest["files_sha256"].items():
        target = (path / name).resolve()
        assert target.is_relative_to(path.resolve()) and sha(target) == checksum
    return manifest


def baseline(path):
    """Explicit test fixture conversion, NOT a production snapshot migration."""
    spec = load_spec(path / "resolved_config.json")
    model = get_model(spec.model)
    with np.load(path / "trajectory.npz", allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    time = float(arrays["accepted_times"][0])
    state = model.STATE_TYPE(*(arrays[k][0].copy() for k in model.STATE_TYPE._fields))
    layout = model.LAYOUT_TYPE(
        *(arrays["cell_ids" if k == "ids" else k].copy() for k in model.LAYOUT_TYPE._fields)
    )
    checkpoint = Checkpoint(
        state, layout, time, EventGrid(spec).exact_index(time), event_index(spec, time)
    )
    validate_checkpoint(spec, checkpoint)
    return spec, checkpoint, arrays


def assert_full(result, arrays):
    actual = {"accepted_times": result.times} | dict(
        zip(result.history._fields, result.history, strict=True)
    )
    actual.update(
        {
            "cell_ids" if k == "ids" else k: v
            for k, v in zip(result.final.layout._fields, result.final.layout, strict=True)
        }
    )
    actual.update(
        {
            "observation_times" if k == "times" else f"observed_{k}": v
            for k, v in vars(result.observations).items()
        }
    )
    assert actual.keys() == arrays.keys()
    for name, value in actual.items():
        np.testing.assert_array_equal(value, arrays[name], err_msg=name)
    return len(actual)


def audit_windows(path, expected):
    """Check serialized indices, all payload values, snapshots and field coverage."""
    manifest = payloads(path, current=True)
    assert manifest["kind"] == "cells_windowed_run" and manifest["status"] == "complete"
    spec = load_spec(path / "resolved_config.json")
    model = get_model(spec.model)
    grid = EventGrid(spec)
    accepted = observations = count = hashes = snapshots = 0
    start = grid.exact_index(float(expected["accepted_times"][0]))
    diagnostic_maxima = {}
    with (path / "windows.jsonl").open() as handle:
        for line in handle:
            record = json.loads(line)
            if record["kind"] == "checkpoint":
                for name, file in (("manifest", "manifest.json"), ("state", "state.npz")):
                    assert sha(path / record["path"] / file) == record[f"{name}_sha256"]
                    hashes += 1
                saved = load_snapshot(path / record["path"])
                assert saved.checkpoint.time == record["time"]
                assert saved.checkpoint.step_index == record["step_index"]
                at = int(np.searchsorted(expected["accepted_times"], saved.checkpoint.time))
                for name, value in zip(
                    saved.checkpoint.state._fields, saved.checkpoint.state, strict=True
                ):
                    np.testing.assert_array_equal(value, expected[name][at])
                snapshots += 1
                continue
            assert record["kind"] == "window" and record["index"] == count
            assert record["start_step"] == start
            assert record["start_time"] == grid[start]
            assert record["end_time"] == grid[record["end_step"]]
            assert record["end_step"] - start <= manifest["policy"]["window_steps"]
            start = record["end_step"]
            for k, v in record["diagnostics"].items():
                diagnostic_maxima[k] = max(diagnostic_maxima.get(k, 0.0), v)
            target = (path / record["path"]).resolve()
            assert target.is_relative_to(path.resolve()) and sha(target) == record["sha256"]
            hashes += 1
            with np.load(target, allow_pickle=False) as data:
                a, b = record["accepted_records"], record["observation_records"]
                keys = {"accepted_times", *model.STATE_TYPE._fields}
                if b:
                    keys |= {
                        k for k in expected if k.startswith("observed_") or k == "observation_times"
                    }
                assert set(data.files) == keys
                for key in data.files:
                    obs = key.startswith("observed_") or key == "observation_times"
                    offset, length = (observations, b) if obs else (accepted, a)
                    np.testing.assert_array_equal(
                        data[key], expected[key][offset : offset + length], err_msg=key
                    )
                accepted += a
                observations += b
            count += 1
    assert accepted == len(expected["accepted_times"])
    assert observations == len(expected["observation_times"])
    assert start == len(grid) - 1
    for name, row in (("checkpoint_initial", 0), ("checkpoint_final", -1)):
        saved = load_snapshot(path / name)
        for key, value in zip(saved.checkpoint.state._fields, saved.checkpoint.state, strict=True):
            np.testing.assert_array_equal(value, expected[key][row])
        for key, value in zip(
            saved.checkpoint.layout._fields, saved.checkpoint.layout, strict=True
        ):
            np.testing.assert_array_equal(value, expected["cell_ids" if key == "ids" else key])
        snapshots += 1
    summary = json.loads((path / "summary.json").read_text())
    assert all(summary[k] == v for k, v in diagnostic_maxima.items())
    resources = manifest["resources"]
    assert resources["windows"] == count
    assert resources["saved_accepted_records"] == accepted
    assert (
        resources["saved_observation_records"]
        == resources["validated_observations"]
        == observations
    )
    return {
        "windows": count,
        "accepted_records": accepted,
        "observation_records": observations,
        "payload_hashes": hashes + len(manifest["files_sha256"]),
        "snapshots": snapshots,
        "manifest_sha256": sha(path / "manifest.json"),
    }


ARCHIVE_WORKER = r"""
import json, sys
from pathlib import Path
import numpy as np
from cells.io import load_snapshot, source_hashes, write_run
from cells.core.runner import run
data = json.loads(sys.stdin.read())
assert source_hashes() == data['source_hashes']
for name in data['snapshots']:
    load_snapshot(name)
base = Path(data['base']) / 'source-scalar-regression-01/S01'
parent = load_snapshot(base / 'snapshots/step-000500')
result = run(parent.spec, parent.checkpoint)
with np.load(base / 'trajectory.npz', allow_pickle=False) as old:
    step = np.searchsorted(old['accepted_times'], parent.checkpoint.time)
    for name, value in zip(result.history._fields, result.history, strict=True):
        np.testing.assert_array_equal(value, old[name][step:])
    mask = old['observation_times'] >= parent.checkpoint.time
    for name, value in vars(result.observations).items():
        key = 'observation_times' if name == 'times' else 'observed_'+name
        np.testing.assert_array_equal(value, old[key][mask])
write_run(data['output'], result)
print(json.dumps({'status': 'pass', 'snapshots': len(data['snapshots']),
                  'source_files': len(source_hashes()), 'exact_replay': True}))
"""


def archive_check(output, release, scalar, batches):
    assert sha(ARCHIVE) == ARCHIVE_SHA
    roots = [BASE / name for name in scalar["run_manifest_sha256"]]
    roots += [BASE / "acceptance-01" / name for name in batches["batches"]]
    roots += [BASE / "acceptance-01/source-replay-checkpoint", BASE / "profile-01"]
    snapshots = sorted(
        {
            str(p.parent)
            for root in roots
            for p in root.rglob("manifest.json")
            if json.loads(p.read_text()).get("kind") == "cells_complete_numerical_checkpoint"
        }
    )
    assert len(snapshots) == release["total_current_version_scalar_snapshots"] == 434
    try:
        load_snapshot(snapshots[0])
    except ConfigError as exc:
        assert "source differs" in str(exc)
    else:
        raise AssertionError("Current version silently loaded an old checkpoint")
    with tempfile.TemporaryDirectory(prefix="cells-archived-08-") as temporary:
        with tarfile.open(ARCHIVE) as tar:
            tar.extractall(temporary, filter="data")
        request = {
            "snapshots": snapshots,
            "source_hashes": release["source_hashes"],
            "base": str(BASE),
            "output": str(output / "archived-08-replay"),
        }
        worker = subprocess.run(
            [sys.executable, "-c", ARCHIVE_WORKER],
            input=json.dumps(request),
            text=True,
            capture_output=True,
            timeout=120,
            cwd=temporary,
            env=os.environ | {"PYTHONPATH": str(Path(temporary) / "src")},
        )
        (output / "archived-08.log").write_text(worker.stdout + worker.stderr)
        assert worker.returncode == 0, worker.stderr
        return json.loads(worker.stdout) | {
            "archive_sha256": ARCHIVE_SHA,
            "current_refuses_old_snapshot": True,
        }


def verify(output):
    assert sha(BASE / "release-audit.json") == RELEASE_SHA
    release = json.loads((BASE / "release-audit.json").read_text())
    for name, checksum in release["evidence_sha256"].items():
        assert sha(ROOT / name) == checksum
    scalar = json.loads((BASE / "scalar-regression-audit.json").read_text())
    batches = json.loads((BASE / "acceptance-01/verification.json").read_text())
    sources, runtime = source_hashes(), runtime_identity()
    for name, checksum in release["source_hashes"].items():
        if (
            name.startswith(("models/", "processes/", "coupling/", "numerics/"))
            or name == "observers.py"
        ):
            assert sources[name] == checksum
    output.mkdir(parents=True, exist_ok=False)
    archive = archive_check(output, release, scalar, batches)
    write_json(output / "archived-08-audit.json", archive)
    records, scalar_arrays = {}, 0
    for i, (name, checksum) in enumerate(scalar["run_manifest_sha256"].items()):
        old = BASE / name
        print(f"Scalar + window regression {i + 1}/78: {name}", flush=True)
        assert sha(old / "manifest.json") == checksum
        payloads(old, current=False)
        spec, cp, arrays = baseline(old)
        ordinary = run(spec, cp)
        exact = assert_full(ordinary, arrays)
        scalar_arrays += exact
        path = output / "scalar" / name
        midpoint = float(arrays["accepted_times"][len(arrays["accepted_times"]) // 2])
        summary = write_windowed_run(
            path,
            spec,
            WindowPolicy(257, "full"),
            cp,
            checkpoint_times=[midpoint],
            provenance={
                "operation": "accepted_08_regression_fixture",
                "baseline_manifest_sha256": checksum,
            },
        )
        assert all(summary[k] == v for k, v in ordinary.diagnostics.items())
        records[name] = audit_windows(path, arrays) | {
            "ordinary_exact_arrays": exact,
            "baseline_manifest_sha256": checksum,
        }
    batch_records, batch_arrays = {}, 0
    for name, record in batches["batches"].items():
        print(f"Unchanged independent-world batch: {name}", flush=True)
        old = BASE / "acceptance-01" / name
        assert sha(old / "manifest.json") == record["manifest_sha256"]
        manifest = payloads(old, current=False)
        spec = load_batch(old / "resolved_batch.json")
        checkpoints, expected = {}, {}
        for world in manifest["worlds"]:
            definition, cp, values = baseline(old / world["path"])
            checkpoints[world["world_id"]], expected[world["world_id"]] = cp, values
            assert definition == next(
                w.simulation for w in spec.worlds if w.world_id == world["world_id"]
            )
        result = run_batch(spec, checkpoints)
        for world_id, actual in result.worlds.items():
            batch_arrays += assert_full(actual, expected[world_id])
        path = output / "batch" / name
        write_batch_run(path, result)
        current = payloads(path, current=True)
        restored = load_batch_snapshot(path / "checkpoint_final")
        assert set(restored.checkpoints) == set(expected)
        batch_records[name] = {
            "manifest_sha256": sha(path / "manifest.json"),
            "baseline_manifest_sha256": record["manifest_sha256"],
            "payload_hashes": len(current["files_sha256"]),
            "worlds": len(result.worlds),
        }
    assert sources == source_hashes() and runtime == runtime_identity()
    files = [ROOT / "src/cells" / name for name in sources] + [
        Path(__file__),
        ROOT / "tests/unit/test_windows.py",
        ROOT / "tests/integration/test_window_cli.py",
        ROOT / "tests/batch_fixtures.py",
        ROOT / "pyproject.toml",
        ROOT / "requirements-lock.txt",
    ]
    identity = {str(p.relative_to(ROOT)): sha(p) for p in files}
    with zipfile.ZipFile(
        output / "implementation_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as archive_file:
        for path in files:
            archive_file.write(path, path.relative_to(ROOT))
    receipt = {
        "status": "pass",
        "scope": (
            "Exact engineering regressions; no new native source solve, assay, organ or GPU result"
        ),
        "runtime": runtime,
        "source_hashes": sources,
        "archive": archive,
        "baseline_release_sha256": RELEASE_SHA,
        "scalar": records,
        "batches": batch_records,
        "ordinary_exact_arrays": scalar_arrays,
        "batch_exact_arrays": batch_arrays,
        "implementation_files_sha256": identity,
        "implementation_capsule_sha256": sha(output / "implementation_sources.zip"),
    }
    write_json(output / "verification.json", receipt)
    return {
        "status": "pass",
        "scalar_runs": len(records),
        "batch_runs": len(batch_records),
        "ordinary_exact_arrays": scalar_arrays,
        "batch_exact_arrays": batch_arrays,
        "sha256": sha(output / "verification.json"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(verify(parser.parse_args().output.resolve()), indent=2))
