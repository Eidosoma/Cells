"""CORE-006: frozen-reference production acceptance and exact old-model regressions.

One bounded CPU acceptance session; no new implicit reference solve, fitting,
optimization or migration. New outputs only; failed attempts remain on disk.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import asdict, replace
from pathlib import Path
from time import monotonic

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.batch_io import load_batch_snapshot  # noqa: E402
from cells.batch_window_io import write_windowed_batch  # noqa: E402
from cells.core.batch import BatchSpec, WorldSpec, load_batch, run_batch  # noqa: E402
from cells.core.runner import branch_checkpoint, run  # noqa: E402
from cells.core.specs import ConfigError, PumpChange  # noqa: E402
from cells.core.windows import WindowPolicy, iter_windows  # noqa: E402
from cells.io import (  # noqa: E402
    _sha256 as sha,
)
from cells.io import (  # noqa: E402
    _write_json as write_json,
)
from cells.io import (  # noqa: E402
    load_snapshot,
    runtime_identity,
    source_hashes,
    write_run,
    write_snapshot,
)
from cells.models import multispecies_membrane as model  # noqa: E402
from scripts.audit_multispecies_build import audit, audit_run  # noqa: E402
from scripts.audit_preserved_multispecies_reference import (  # noqa: E402
    ARCHIVE_SHA,
    extract_sources,
)
from scripts.audit_preserved_multispecies_reference import (  # noqa: E402
    audit as audit_reference,
)
from scripts.verify_batch_windows_build import audit_cohort, suffix  # noqa: E402
from scripts.verify_windows_build import assert_full, baseline, payloads  # noqa: E402
from tests import multispecies_numerical_checks as checks  # noqa: E402
from tests.multispecies_fixtures import canonical_values, spec_for  # noqa: E402
from tests.reference_multispecies_dynamics import load_panel  # noqa: E402

REFERENCE = ROOT / "runs/num-006-2026-09-09/reference-01"
RELEASE = ROOT / "runs/core-005b-2026-09-08/release-audit.json"
RELEASE_SHA = "94d8ee4500f91fb6fb5506085c515944ad235e7d42318430d11d85e41b74da4e"
OLD = ROOT / "runs/core-004-2026-09-08"
PREVIOUS = ROOT / "runs/core-005b-2026-09-08/acceptance-01/regression/verification.json"
PREVIOUS_SHA = "128e3950890063353fb13cf542b4c3b7c59018ec6377aea664903338ca5fa36b"
MAX_SECONDS = 1800
MAX_BYTES = 512 * 2**20


def guard(output, started):
    if monotonic() - started > MAX_SECONDS:
        raise ValueError("Acceptance session wall budget reached; no automatic retry")
    if sum(p.stat().st_size for p in output.rglob("*") if p.is_file()) > MAX_BYTES:
        raise ValueError("Acceptance artifact budget reached; no automatic retry")


ARCHIVED_WORKER = r"""
import json, sys
from pathlib import Path
import numpy as np
from cells.io import load_snapshot, source_hashes, runtime_identity
from cells.batch_io import load_batch_snapshot
from cells.core.runner import run
data = json.loads(sys.stdin.read())
assert source_hashes() == data['source_hashes']
assert runtime_identity() == data['runtime']
for name in data['snapshots']:
    load_snapshot(name)
for name in data['cohorts']:
    load_batch_snapshot(name)
saved = load_snapshot(data['replay_snapshot'])
result = run(saved.spec, saved.checkpoint)
with np.load(data['replay_baseline'], allow_pickle=False) as expected:
    start = np.searchsorted(expected['accepted_times'], saved.checkpoint.time)
    observed = np.searchsorted(expected['observation_times'], saved.checkpoint.time)
    np.testing.assert_array_equal(result.times, expected['accepted_times'][start:])
    for field, values in zip(result.history._fields, result.history, strict=True):
        np.testing.assert_array_equal(values, expected[field][start:])
    for field, values in vars(result.observations).items():
        key = 'observation_times' if field == 'times' else 'observed_'+field
        np.testing.assert_array_equal(values, expected[key][observed:])
print(json.dumps({'status':'pass', 'scalar_snapshots':len(data['snapshots']),
                  'cohort_snapshots':len(data['cohorts']), 'exact_source_pair_replay':True}))
"""


def archive_check(output):
    assert sha(RELEASE) == RELEASE_SHA
    release = json.loads(RELEASE.read_text())
    base = RELEASE.parent
    roots = [
        base / "acceptance-01/regression",
        base / "acceptance-02/cohorts",
        base / "acceptance-02/resumed",
        base / "profile-01",
    ]
    snapshots, cohorts = [], []
    for root in roots:
        for path in sorted(root.rglob("manifest.json")):
            manifest = json.loads(path.read_text())
            if manifest.get("runtime", {}).get("cells_version") != "0.10.0":
                continue  # Explicitly exclude retained old-source replay artifacts.
            if manifest.get("kind") == "cells_complete_numerical_checkpoint":
                snapshots.append(str(path.parent))
            if manifest.get("kind") == "cells_independent_world_checkpoint":
                cohorts.append(str(path.parent))
    assert len(snapshots) == release["accepted_current_scalar_snapshots"] == 948
    assert len(cohorts) == release["accepted_current_cohort_snapshots"] == 99
    for loader, path in ((load_snapshot, snapshots[0]), (load_batch_snapshot, cohorts[0])):
        try:
            loader(path)
        except ConfigError as error:
            assert "source differs" in str(error)
        else:
            raise AssertionError("Old checkpoint was silently migrated")
    replay_root = base / "acceptance-01/regression/scalar/source-scalar-regression-01/S01"
    request = {
        "source_hashes": release["source_hashes"],
        "runtime": release["runtime"],
        "snapshots": snapshots,
        "cohorts": cohorts,
        "replay_snapshot": str(next((replay_root / "snapshots").iterdir())),
        "replay_baseline": str(OLD / "source-scalar-regression-01/S01/trajectory.npz"),
    }
    with tempfile.TemporaryDirectory(prefix="cells-core006-old-") as directory:
        extract_sources(directory)
        worker = subprocess.run(
            [sys.executable, "-c", ARCHIVED_WORKER],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=360,
            cwd=directory,
            env=os.environ | {"PYTHONPATH": str(Path(directory) / "src")},
        )
    with (output / "archived-010.log").open("x") as handle:
        handle.write(worker.stdout + worker.stderr)
    assert worker.returncode == 0, worker.stderr
    return json.loads(worker.stdout) | {
        "archive_sha256": ARCHIVE_SHA,
        "current_refuses_migration": True,
    }


def old_regressions(output, started):
    assert sha(PREVIOUS) == PREVIOUS_SHA
    previous = json.loads(PREVIOUS.read_text())
    release = json.loads(RELEASE.read_text())
    # Registry dispatch necessarily grows. Every older law, assembly, numerical
    # method and observer remains byte-for-byte unchanged.
    current = source_hashes()
    for name, digest in release["source_hashes"].items():
        if name != "models/registry.py" and (
            name.startswith(("models/", "processes/", "coupling/", "numerics/"))
            or name == "observers.py"
        ):
            assert current[name] == digest
    scalar, batches = {}, {}
    for index, (name, record) in enumerate(previous["scalar"].items()):
        print(f"Old scalar/window regression {index + 1}/78: {name}", flush=True)
        path = OLD / name
        assert sha(path / "manifest.json") == record["baseline_manifest_sha256"]
        payloads(path, current=False)
        spec, checkpoint, expected = baseline(path)
        ordinary = run(spec, checkpoint)
        exact = assert_full(ordinary, expected)
        accepted = observed = windows = arrays = 0
        for i, part in enumerate(iter_windows(spec, WindowPolicy(257), checkpoint)):
            skip = int(i > 0)
            length = len(part.times) - skip
            np.testing.assert_array_equal(
                part.times[skip:], expected["accepted_times"][accepted : accepted + length]
            )
            for field, values in zip(part.history._fields, part.history, strict=True):
                np.testing.assert_array_equal(
                    values[skip:], expected[field][accepted : accepted + length]
                )
                arrays += 1
            accepted += length
            length = len(part.observations.times)
            for field, values in vars(part.observations).items():
                key = "observation_times" if field == "times" else f"observed_{field}"
                np.testing.assert_array_equal(values, expected[key][observed : observed + length])
                arrays += 1
            observed += length
            windows += 1
        assert accepted == len(expected["accepted_times"]) and observed == len(
            expected["observation_times"]
        )
        scalar[name] = {
            "baseline_manifest_sha256": record["baseline_manifest_sha256"],
            "ordinary_exact_arrays": exact,
            "window_arrays": arrays,
            "windows": windows,
            "accepted_records": accepted,
            "observations": observed,
        }
        guard(output, started)
    for name, record in previous["batches"].items():
        print(f"Old independent batch regression: {name}", flush=True)
        path = OLD / "acceptance-01" / name
        assert sha(path / "manifest.json") == record["baseline_manifest_sha256"]
        manifest = payloads(path, current=False)
        spec = load_batch(path / "resolved_batch.json")
        checkpoints, expected = {}, {}
        for entry in manifest["worlds"]:
            world = path / entry["path"]
            payloads(world, current=False)
            _, checkpoints[entry["world_id"]], expected[entry["world_id"]] = baseline(world)
        result = run_batch(spec, checkpoints)
        exact = sum(
            assert_full(world, expected[identity]) for identity, world in result.worlds.items()
        )
        batches[name] = {
            "baseline_manifest_sha256": record["baseline_manifest_sha256"],
            "worlds": len(result.worlds),
            "exact_arrays": exact,
        }
        guard(output, started)
    return {
        "status": "pass",
        "prior_acceptance_sha256": PREVIOUS_SHA,
        "scalar": scalar,
        "batches": batches,
        "ordinary_exact_arrays": sum(v["ordinary_exact_arrays"] for v in scalar.values()),
        "batch_exact_arrays": sum(v["exact_arrays"] for v in batches.values()),
        "note": (
            "Old arrays are authenticated test fixtures, not implicitly migrated snapshots; "
            "no duplicate old trajectories written"
        ),
    }


REPLAY_WORKER = r"""
import json, sys
from pathlib import Path
import numpy as np
from cells.io import load_snapshot, write_run, source_hashes, runtime_identity
from cells.core.runner import run
data=json.loads(sys.stdin.read())
assert source_hashes() == data['source_hashes'] and runtime_identity() == data['runtime']
for record in data['runs']:
    parent=Path(record['path'])
    saved=load_snapshot(next((parent/'snapshots').iterdir()))
    result=run(saved.spec, saved.checkpoint)
    with np.load(parent/'trajectory.npz', allow_pickle=False) as values:
        a=np.searchsorted(values['accepted_times'],saved.checkpoint.time)
        b=np.searchsorted(values['observation_times'],saved.checkpoint.time)
        np.testing.assert_array_equal(result.times,values['accepted_times'][a:])
        for field,v in zip(result.history._fields,result.history,strict=True):
            np.testing.assert_array_equal(v,values[field][a:])
        for field,v in vars(result.observations).items():
            key='observation_times' if field=='times' else 'observed_'+field
            np.testing.assert_array_equal(v,values[key][b:])
    write_run(record['output'],result,provenance={'operation':'fresh_process_complete_restart','parent_snapshot_sha256':saved.fingerprint})
print(json.dumps({'status':'pass','exact_restarts':len(data['runs'])}))
"""


def verify(output):
    output.mkdir(parents=True, exist_ok=False)
    started = monotonic()
    sources, runtime = source_hashes(), runtime_identity()
    extras = [
        Path(__file__),
        ROOT / "scripts/audit_multispecies_build.py",
        ROOT / "scripts/audit_preserved_multispecies_reference.py",
        ROOT / "scripts/verify_windows_build.py",
        ROOT / "scripts/verify_batch_windows_build.py",
        ROOT / "scripts/audit_multispecies_reference.py",
        ROOT / "tests/multispecies_fixtures.py",
        ROOT / "tests/unit/test_multispecies_membrane.py",
        ROOT / "tests/unit/test_multispecies_artifact_audit.py",
        ROOT / "tests/unit/test_multispecies_build_audit.py",
        ROOT / "scripts/test_cells_build.py",
        ROOT / "configs/multispecies_baseline.json",
        ROOT / "configs/multispecies_controls.json",
        ROOT / "configs/multispecies_nakcl.json",
        ROOT / "tests/reference_multispecies_dynamics.py",
        ROOT / "tests/reference_multispecies.py",
        ROOT / "tests/multispecies_numerical_checks.py",
        ROOT / "pyproject.toml",
        ROOT / "requirements-lock.txt",
    ]
    files = [ROOT / "src/cells" / name for name in sources] + extras
    identity = {str(p.relative_to(ROOT)): sha(p) for p in files}
    with zipfile.ZipFile(
        output / "implementation_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as capsule:
        for path in files:
            capsule.write(path, path.relative_to(ROOT))
    write_json(
        output / "registration.json",
        {
            "source_hashes": sources,
            "runtime": runtime,
            "files_sha256": identity,
            "max_seconds": MAX_SECONDS,
            "max_artifact_bytes": MAX_BYTES,
        },
    )
    try:
        print("Auditing preserved NUM-006 evidence and 0.10.0 checkpoints", flush=True)
        reference_audit = audit_reference(REFERENCE)
        write_json(output / "reference-audit.json", reference_audit)
        archive = archive_check(output)
        write_json(output / "archived-010-audit.json", archive)
        plan, cases = load_panel()
        records, replay, expected, definitions = {}, [], {}, {}
        for case in cases:
            print(f"Production reference qualification, JIT and eager: {case.id}", flush=True)
            with np.load(REFERENCE / case.id / "refined.npz", allow_pickle=False) as values:
                samples = values["sample_times_s"]
            outputs = {}
            for mode, jit in (("jit", True), ("eager", False)):
                spec = spec_for(case, jit=jit, samples=samples)
                assert json.loads(json.dumps(asdict(spec.model))) == json.loads(
                    json.dumps(asdict(case.parameters))
                )
                result = run(spec)
                path = output / mode / case.id
                middle = float(result.times[len(result.times) // 2])
                write_run(
                    path,
                    result,
                    checkpoint_times=(middle,),
                    provenance={"operation": "CORE-006", "reference_case": case.id},
                )
                _, records[f"{mode}/{case.id}"] = audit_run(
                    path, case.definition(), plan, REFERENCE / case.id
                )
                outputs[mode] = (
                    canonical_values(case, result.history),
                    canonical_values(case, result.observations),
                )
                if jit:
                    _, _, expected[case.id] = baseline(path)
                    definitions[case.id] = result.spec
                    replay.append({"path": str(path), "output": str(output / "resumed" / case.id)})
                guard(output, started)
            for a, b in zip(outputs["jit"], outputs["eager"], strict=True):
                assert checks.errors(
                    case.definition(), a, b, plan["trajectory_limits"], factor=0.001
                )["pass"]
        print("Fresh-process complete restart for all fourteen production cases", flush=True)
        worker = subprocess.run(
            [sys.executable, "-c", REPLAY_WORKER],
            input=json.dumps({"source_hashes": sources, "runtime": runtime, "runs": replay}),
            capture_output=True,
            text=True,
            timeout=180,
            cwd=ROOT,
        )
        with (output / "restart.log").open("x") as handle:
            handle.write(worker.stdout + worker.stderr)
        assert worker.returncode == 0, worker.stderr
        for case in cases:
            _, records[f"resumed/{case.id}"] = audit_run(
                output / "resumed" / case.id, case.definition(), plan, REFERENCE / case.id
            )
        # The pulse-off future branch reduces to the independently qualified
        # passive control, preserving the original anchors and cumulative state.
        parent = run(definitions["divalent_short_pulse"])
        checkpoint = parent.checkpoint_at(0.203)
        write_snapshot(output / "branch-parent", parent.spec, checkpoint)
        branch_spec = replace(
            parent.spec,
            experiment=replace(
                parent.spec.experiment, pump=(PumpChange(0.0, 0.0), PumpChange(0.203, 0.0))
            ),
        )
        branch = run(branch_spec, branch_checkpoint(parent.spec, checkpoint, branch_spec))
        branch_path = output / "branch/divalent_pulse_omitted"
        write_run(
            branch_path,
            branch,
            provenance={
                "operation": "future_branch",
                "parent_definition_sha256": parent.spec.fingerprint,
            },
        )
        passive = next(c for c in cases if c.id == "divalent_passive_10s")
        _, records["branch/divalent_pulse_omitted"] = audit_run(
            branch_path, passive.definition(), plan, REFERENCE / passive.id, branch=True
        )
        print("Variable-clock cohort recording and restart, both species extents", flush=True)
        cohorts = {}
        for prefix in ("mono", "divalent"):
            selected = [c for c in cases if c.id.startswith(prefix)]
            batch = BatchSpec(
                tuple(WorldSpec(i + 1, definitions[c.id]) for i, c in enumerate(selected)),
                7,
                20000,
                2**28,
            )
            wanted = {i + 1: expected[c.id] for i, c in enumerate(selected)}
            path = output / "cohorts" / prefix
            write_windowed_batch(path, batch, WindowPolicy(129, "full"), checkpoint_every_windows=1)
            cohorts[prefix] = audit_cohort(path, wanted)
            saved = load_batch_snapshot(path / "snapshots/round-0000000001")
            resumed = output / "cohort-resumed" / prefix
            write_windowed_batch(resumed, saved.spec, WindowPolicy(73, "full"), saved.checkpoints)
            cohorts[f"resumed/{prefix}"] = audit_cohort(
                resumed, {i: suffix(v, saved.checkpoints[i], model) for i, v in wanted.items()}
            )
            guard(output, started)
        regression = old_regressions(output, started)
        write_json(output / "old-model-regression.json", regression)
        assert source_hashes() == sources and runtime_identity() == runtime
        assert all(sha(ROOT / name) == value for name, value in identity.items())
        guard(output, started)
        receipt = {
            "status": "pass",
            "source_hashes": sources,
            "runtime": runtime,
            "reference": reference_audit,
            "archive": archive,
            "runs": records,
            "cohorts": cohorts,
            "old_model_regression": regression,
            "fresh_process_restart": json.loads(worker.stdout),
            "jit_eager_comparison_factor": 0.001,
            "seconds": monotonic() - started,
            "files_sha256": {
                str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
            },
            "implementation_files_sha256": identity,
        }
        write_json(output / "verification.json", receipt)
        return audit(output)
    except BaseException as error:
        write_json(
            output / "failure.json",
            {
                "status": "failed",
                "type": type(error).__name__,
                "error": str(error),
                "seconds": monotonic() - started,
                "source_hashes": source_hashes(),
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output.resolve()), indent=2, sort_keys=True, allow_nan=False))
