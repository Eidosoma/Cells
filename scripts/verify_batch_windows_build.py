"""CORE-005b: archived replay, accepted regressions and serialized cohort rounds.

Uses frozen accepted trajectories as test fixtures, never a new native source
solve or an implicit production checkpoint migration. Verification may retain
baseline arrays; the production runner and separate profile do not.
"""

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.batch_io import load_batch_snapshot  # noqa: E402
from cells.batch_window_io import write_windowed_batch  # noqa: E402
from cells.core.batch import branch_batch_checkpoints, load_batch  # noqa: E402
from cells.core.grid import EventGrid  # noqa: E402
from cells.core.schedule import event_index  # noqa: E402
from cells.core.specs import ConfigError  # noqa: E402
from cells.core.windows import WindowPolicy  # noqa: E402
from cells.io import _sha256 as sha  # noqa: E402
from cells.io import _write_json as write_json  # noqa: E402
from cells.io import load_snapshot, runtime_identity, source_hashes  # noqa: E402
from cells.models.registry import get_model  # noqa: E402
from scripts.verify_windows_build import audit_windows, baseline, payloads  # noqa: E402
from scripts.verify_windows_build import verify as verify_regression  # noqa: E402

BASE = ROOT / "runs/core-005a-2026-09-08"
RELEASE_SHA = "582f03e2495430968343828b923c3ab07350ac283c35115317755eaa7986d859"
ARCHIVE = ROOT / "reports/cells-0.9.0-source.tar.gz"
ARCHIVE_SHA = "08d9b5b2b3288055ca5d356d3b0cb2e3fa169b156a781677a43c09825e964874"


def audit_cohort(path, expected):
    manifest = payloads(path, current=True)
    assert manifest["kind"] == "cells_windowed_independent_world_run"
    assert manifest["status"] == "complete" and manifest["policy"]["recording"] == "full"
    spec = load_batch(path / "resolved_batch.json")
    assert spec.fingerprint == manifest["definition_sha256"]
    grids = {w.world_id: EventGrid(w.simulation) for w in spec.worlds}
    model = get_model(spec.worlds[0].simulation.model)
    counters = {
        i: {"accepted": 0, "observations": 0, "windows": 0, "diagnostics": {}} for i in expected
    }
    hashes, cohorts, snapshots, arrays = len(manifest["files_sha256"]), 0, 0, 0

    def check_snapshot(relative):
        nonlocal cohorts, snapshots
        saved = load_batch_snapshot(path / relative)
        assert saved.spec == spec and set(saved.checkpoints) == set(expected)
        for identity, cp in saved.checkpoints.items():
            values = expected[identity]
            at = np.flatnonzero(values["accepted_times"] == cp.time)
            assert len(at) == 1 and cp.step_index == grids[identity].exact_index(cp.time)
            for name, value in zip(cp.state._fields, cp.state, strict=True):
                np.testing.assert_array_equal(value, values[name][at[0]])
            for name, value in zip(cp.layout._fields, cp.layout, strict=True):
                np.testing.assert_array_equal(value, values["cell_ids" if name == "ids" else name])
            snapshots += 1
        cohorts += 1

    rounds = set()
    with (path / "windows.jsonl").open() as handle:
        for line in handle:
            record = json.loads(line)
            target = (path / record["path"]).resolve()
            assert target.is_relative_to(path.resolve())
            if record["kind"] == "cohort_checkpoint":
                assert sha(target / "manifest.json") == record["manifest_sha256"]
                assert record["completed_rounds"] % manifest["checkpoint_every_windows"] == 0
                assert record["completed_rounds"] < manifest["resources"]["rounds"]
                hashes += 1
                check_snapshot(record["path"])
                continue
            assert record["kind"] == "world_window"
            identity = record["world_id"]
            total, values = counters[identity], expected[identity]
            assert record["index"] == total["windows"]
            # A world participates in consecutive initial rounds, then stays finished.
            assert record["round"] == total["windows"]
            rounds.add(record["round"])
            previous = max(0, total["accepted"] - 1)
            assert record["start_time"] == values["accepted_times"][previous]
            assert record["start_step"] == grids[identity].exact_index(record["start_time"])
            assert record["end_step"] == grids[identity].exact_index(record["end_time"])
            assert (
                0 <= record["end_step"] - record["start_step"] <= manifest["policy"]["window_steps"]
            )
            assert sha(target) == record["sha256"]
            hashes += 1
            a, b = record["accepted_records"], record["observation_records"]
            assert b == record["validated_observations"]
            with np.load(target, allow_pickle=False) as data:
                keys = {"accepted_times", *model.STATE_TYPE._fields}
                if b:
                    keys |= {
                        k for k in values if k.startswith("observed_") or k == "observation_times"
                    }
                assert set(data.files) == keys
                for key in data.files:
                    observed = key.startswith("observed_") or key == "observation_times"
                    offset, length = (
                        (total["observations"], b) if observed else (total["accepted"], a)
                    )
                    np.testing.assert_array_equal(
                        data[key],
                        values[key][offset : offset + length],
                        err_msg=f"world {identity}: {key}",
                    )
                    arrays += 1
            total["accepted"] += a
            total["observations"] += b
            total["windows"] += 1
            for name, value in record["diagnostics"].items():
                total["diagnostics"][name] = max(total["diagnostics"].get(name, 0.0), value)
    assert rounds == set(range(manifest["resources"]["rounds"]))
    summary = json.loads((path / "summary.json").read_text())
    for record in manifest["worlds"]:
        identity, total = record["world_id"], counters[record["world_id"]]
        assert (
            total["accepted"]
            == record["saved_accepted_records"]
            == len(expected[identity]["accepted_times"])
        )
        assert (
            total["observations"]
            == record["saved_observation_records"]
            == len(expected[identity]["observation_times"])
        )
        assert total["windows"] == record["windows"]
        assert all(
            summary["world_summaries"][str(identity)][k] == v
            for k, v in total["diagnostics"].items()
        )
    check_snapshot("checkpoint_initial")
    check_snapshot("checkpoint_final")
    return {
        "manifest_sha256": sha(path / "manifest.json"),
        "worlds": len(expected),
        "rounds": len(rounds),
        "windows": sum(v["windows"] for v in counters.values()),
        "accepted_records": sum(v["accepted"] for v in counters.values()),
        "observation_records": sum(v["observations"] for v in counters.values()),
        "exact_payload_arrays": arrays,
        "payload_hashes": hashes,
        "cohort_snapshots": cohorts,
        "scalar_snapshots": snapshots,
    }


ARCHIVE_WORKER = r"""
import json, sys
from pathlib import Path
import numpy as np
from cells.io import load_snapshot, source_hashes
from cells.batch_io import load_batch_snapshot
from cells.core.windows import WindowPolicy, iter_windows
from cells.window_io import write_windowed_run
data = json.loads(sys.stdin.read())
assert source_hashes() == data['source_hashes']
for name in data['snapshots']:
    load_snapshot(name)
for name in data['cohorts']:
    load_batch_snapshot(name)
root = Path(data['base']) / 'acceptance-01/scalar/source-scalar-regression-01/S01'
parent = load_snapshot(next((root / 'snapshots').iterdir()))
old = Path(data['old']) / 'source-scalar-regression-01/S01/trajectory.npz'
with np.load(old, allow_pickle=False) as values:
    accepted = int(np.searchsorted(values['accepted_times'], parent.checkpoint.time))
    observed = int(np.searchsorted(values['observation_times'], parent.checkpoint.time))
    for index, part in enumerate(iter_windows(parent.spec, WindowPolicy(129), parent.checkpoint)):
        skip = int(index > 0)
        size = len(part.times) - skip
        np.testing.assert_array_equal(
            part.times[skip:], values['accepted_times'][accepted:accepted+size])
        for name, value in zip(part.history._fields, part.history, strict=True):
            np.testing.assert_array_equal(value[skip:], values[name][accepted:accepted+size])
        accepted += size
        for name, value in vars(part.observations).items():
            key = 'observation_times' if name == 'times' else 'observed_'+name
            np.testing.assert_array_equal(value, values[key][observed:observed+len(value)])
        observed += len(part.observations.times)
    assert accepted == len(values['accepted_times'])
    assert observed == len(values['observation_times'])
write_windowed_run(data['output'], parent.spec, WindowPolicy(129), parent.checkpoint)
print(json.dumps({'status':'pass', 'scalar_snapshots':len(data['snapshots']),
                  'cohort_snapshots':len(data['cohorts']), 'exact_window_replay':True,
                  'source_files':len(source_hashes())}))
"""


def archive_check(output, release):
    assert sha(ARCHIVE) == ARCHIVE_SHA
    roots = [BASE / "acceptance-01/scalar", BASE / "acceptance-01/batch", BASE / "profile-02"]
    manifests = [
        (p, json.loads(p.read_text())) for root in roots for p in root.rglob("manifest.json")
    ]
    snapshots = sorted(
        str(p.parent)
        for p, m in manifests
        if m.get("kind") == "cells_complete_numerical_checkpoint"
    )
    cohorts = sorted(
        str(p.parent) for p, m in manifests if m.get("kind") == "cells_independent_world_checkpoint"
    )
    assert len(snapshots) == release["total_accepted_current_scalar_snapshots"] == 342
    for loader, path in ((load_snapshot, snapshots[0]), (load_batch_snapshot, cohorts[0])):
        try:
            loader(path)
        except ConfigError as exc:
            assert "source differs" in str(exc)
        else:
            raise AssertionError("Implicit old checkpoint migration")
    with tempfile.TemporaryDirectory(prefix="cells-archived-09-") as temporary:
        with tarfile.open(ARCHIVE) as tar:
            tar.extractall(temporary, filter="data")
        request = {
            "source_hashes": release["source_hashes"],
            "snapshots": snapshots,
            "cohorts": cohorts,
            "base": str(BASE),
            "old": str(ROOT / "runs/core-004-2026-09-08"),
            "output": str(output / "archived-09-replay"),
        }
        worker = subprocess.run(
            [sys.executable, "-c", ARCHIVE_WORKER],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=120,
            cwd=temporary,
            env=os.environ | {"PYTHONPATH": str(Path(temporary) / "src")},
        )
        (output / "archived-09.log").write_text(worker.stdout + worker.stderr)
        assert worker.returncode == 0, worker.stderr
        return json.loads(worker.stdout) | {
            "archive_sha256": ARCHIVE_SHA,
            "current_refuses_old_snapshots": True,
        }


def suffix(values, checkpoint, model):
    start = int(np.searchsorted(values["accepted_times"], checkpoint.time))
    observed = int(np.searchsorted(values["observation_times"], checkpoint.time))
    return {
        key: value[start:]
        if key == "accepted_times" or key in model.STATE_TYPE._fields
        else value[observed:]
        if key == "observation_times" or key.startswith("observed_")
        else value
        for key, value in values.items()
    }


def reuse_regression(path, checksum):
    """Re-audit a completed, hash-pinned regression without re-running solvers."""
    assert sha(path / "verification.json") == checksum
    receipt = json.loads((path / "verification.json").read_text())
    assert receipt["status"] == "pass"
    assert receipt["source_hashes"] == source_hashes()
    assert receipt["runtime"] == runtime_identity()
    for name, value in receipt["implementation_files_sha256"].items():
        assert sha(ROOT / name) == value
    assert sha(path / "implementation_sources.zip") == receipt["implementation_capsule_sha256"]
    for name, record in receipt["scalar"].items():
        current = path / "scalar" / name
        assert sha(current / "manifest.json") == record["manifest_sha256"]
        old = ROOT / "runs/core-004-2026-09-08" / name
        assert sha(old / "manifest.json") == record["baseline_manifest_sha256"]
        payloads(old, current=False)
        _, _, expected = baseline(old)
        audited = audit_windows(current, expected)
        assert all(record[k] == value for k, value in audited.items())
    for name, record in receipt["batches"].items():
        current = path / "batch" / name
        assert sha(current / "manifest.json") == record["manifest_sha256"]
        payloads(current, current=True)
        load_batch_snapshot(current / "checkpoint_final")
    return {
        "status": "pass",
        "reused_and_reaudited": True,
        "scalar_runs": len(receipt["scalar"]),
        "batch_runs": len(receipt["batches"]),
        "ordinary_exact_arrays": receipt["ordinary_exact_arrays"],
        "batch_exact_arrays": receipt["batch_exact_arrays"],
        "sha256": checksum,
    }


def verify(output, regression_path=None, regression_sha=None):
    if (regression_path is None) != (regression_sha is None):
        raise ValueError("Existing regression path and expected checksum must be supplied together")
    assert sha(BASE / "release-audit.json") == RELEASE_SHA
    release = json.loads((BASE / "release-audit.json").read_text())
    for name, checksum in release["evidence_sha256"].items():
        assert sha(ROOT / name) == checksum
    previous = json.loads((BASE / "acceptance-01/verification.json").read_text())
    sources, runtime = source_hashes(), runtime_identity()
    for name, checksum in release["source_hashes"].items():
        if (
            name.startswith(("models/", "processes/", "coupling/", "numerics/"))
            or name == "observers.py"
        ):
            assert sources[name] == checksum
    output.mkdir(parents=True, exist_ok=False)
    archive = archive_check(output, release)
    write_json(output / "archived-09-audit.json", archive)
    # Reuse the accepted verification driver unchanged for all 78 scalar/window
    # trajectories, 10 ordinary batches and archived-0.8 strict replay.
    if regression_path is None:
        regression_path = output / "regression"
        regression = verify_regression(regression_path)
    else:
        regression = reuse_regression(regression_path, regression_sha)
    regression["path"] = str(regression_path)
    records = {}
    for name, prior in previous["batches"].items():
        print(f"Cohort windows + complete round restart: {name}", flush=True)
        old = BASE / "acceptance-01/batch" / name
        assert sha(old / "manifest.json") == prior["manifest_sha256"]
        manifest = payloads(old, current=False)
        spec = load_batch(old / "resolved_batch.json")
        checkpoints, expected = {}, {}
        for world in manifest["worlds"]:
            definition, cp, values = baseline(old / world["path"])
            identity = world["world_id"]
            assert definition == next(w.simulation for w in spec.worlds if w.world_id == identity)
            checkpoints[identity], expected[identity] = cp, values
        if name == "source-branched":
            original_path = BASE / "acceptance-01/batch/source-example"
            original_spec = load_batch(original_path / "resolved_batch.json")
            parents = {}
            for identity, cp in checkpoints.items():
                parent_spec, _, values = baseline(original_path / f"worlds/world-{identity}")
                row = int(np.flatnonzero(values["accepted_times"] == cp.time)[0])
                for field, value in zip(cp.state._fields, cp.state, strict=True):
                    np.testing.assert_array_equal(value, values[field][row])
                # A future change exactly at the checkpoint changes the branch's
                # event cursor. The original-protocol fixture needs its own clock.
                parents[identity] = replace(
                    cp,
                    step_index=EventGrid(parent_spec).exact_index(cp.time),
                    event_index=event_index(parent_spec, cp.time),
                )
            # Exercise ordinary future-branch validation, not just the numerical
            # suffix. Frozen preceding acceptance already independently solved it.
            checkpoints = branch_batch_checkpoints(original_spec, parents, spec)
        width = min(257, max(1, max(len(v["accepted_times"]) - 1 for v in expected.values()) // 3))
        path = output / "cohorts" / name
        write_windowed_batch(
            path,
            spec,
            WindowPolicy(width, "full"),
            checkpoints,
            checkpoint_every_windows=1,
            provenance={
                "operation": "accepted_09_regression_fixture",
                "baseline_manifest_sha256": prior["manifest_sha256"],
            },
        )
        records[name] = audit_cohort(path, expected) | {
            "baseline_manifest_sha256": prior["manifest_sha256"],
            "future_branch_api_exercised": name == "source-branched",
        }
        saved = load_batch_snapshot(path / "snapshots/round-0000000001")
        replay = output / "resumed" / name
        write_windowed_batch(
            replay, saved.spec, WindowPolicy(max(1, width // 2), "full"), saved.checkpoints
        )
        model = get_model(spec.worlds[0].simulation.model)
        wanted = {i: suffix(values, saved.checkpoints[i], model) for i, values in expected.items()}
        records[f"resumed/{name}"] = audit_cohort(replay, wanted)
    assert sources == source_hashes() and runtime == runtime_identity()
    files = [ROOT / "src/cells" / name for name in sources] + [
        Path(__file__),
        ROOT / "scripts/verify_windows_build.py",
        ROOT / "scripts/profile_batch_windows.py",
        ROOT / "scripts/profile_windows.py",
        ROOT / "scripts/profile_worlds.py",
        ROOT / "tests/unit/test_batch_windows.py",
        ROOT / "tests/integration/test_batch_window_cli.py",
        ROOT / "tests/batch_fixtures.py",
        ROOT / "pyproject.toml",
        ROOT / "requirements-lock.txt",
    ]
    identity = {str(p.relative_to(ROOT)): sha(p) for p in files}
    with zipfile.ZipFile(
        output / "implementation_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as capsule:
        for file in files:
            capsule.write(file, file.relative_to(ROOT))
    receipt = {
        "status": "pass",
        "scope": "Engineering parity/replay; no new biology, native source solve or GPU claim",
        "runtime": runtime,
        "source_hashes": sources,
        "baseline_release_sha256": RELEASE_SHA,
        "archive": archive,
        "regression": regression,
        "cohorts": records,
        "implementation_files_sha256": identity,
        "implementation_capsule_sha256": sha(output / "implementation_sources.zip"),
    }
    write_json(output / "verification.json", receipt)
    return {
        "status": "pass",
        "cohort_runs": len(records),
        "sha256": sha(output / "verification.json"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regression", type=Path)
    parser.add_argument("--regression-sha256")
    args = parser.parse_args()
    print(
        json.dumps(
            verify(
                args.output.resolve(),
                None if args.regression is None else args.regression.resolve(),
                args.regression_sha256,
            ),
            indent=2,
        )
    )
