"""CORE-004 acceptance: scalar parity, frozen source references and batch replay."""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.batch_io import load_batch_snapshot, write_batch_run, write_batch_snapshot  # noqa: E402
from cells.core.batch import branch_batch_checkpoints, load_batch, run_batch  # noqa: E402
from cells.core.runner import run  # noqa: E402
from cells.core.specs import load_spec  # noqa: E402
from cells.io import load_snapshot, runtime_identity, source_hashes  # noqa: E402
from scripts.verify_source_pair_build import audit_run, compare  # noqa: E402
from tests import reference_source_pair_numerics as ref  # noqa: E402
from tests.batch_fixtures import MODELS, assert_parity, definition, short_spec  # noqa: E402
from tests.source_pair_fixtures import reference_model, values  # noqa: E402

OLD = ROOT / "runs/model-005-2026-09-08/acceptance-01"
REFERENCE = ROOT / "runs/num-004-2026-09-08/qualification-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def audit_batch(path):
    manifest = json.loads((path / "manifest.json").read_text())
    assert manifest["source_hashes"] == source_hashes()
    assert manifest["runtime"] == runtime_identity()
    for name, checksum in manifest["files_sha256"].items():
        target = (path / name).resolve()
        assert target.is_relative_to(path.resolve()) and sha(target) == checksum
    snapshots = 0
    for name in manifest["snapshots"]:
        saved = load_batch_snapshot(path / name)
        snapshots += len(saved.checkpoints)
        for identity, checkpoint in saved.checkpoints.items():
            with np.load(path / f"worlds/world-{identity}/trajectory.npz") as arrays:
                index = np.flatnonzero(arrays["accepted_times"] == checkpoint.time)[0]
                for key, value in zip(checkpoint.state._fields, checkpoint.state, strict=True):
                    np.testing.assert_array_equal(value, arrays[key][index])
    for record in manifest["worlds"]:
        assert sha(path / record["path"] / "manifest.json") == record["manifest_sha256"]
        load_snapshot(path / record["path"] / "checkpoint_final")
        snapshots += 1
    return {
        "worlds": len(manifest["worlds"]),
        "complete_scalar_snapshots": snapshots,
        "payload_hashes": len(manifest["files_sha256"]),
        "manifest_sha256": sha(path / "manifest.json"),
    }


def verify(output):
    if output.exists():
        raise ValueError("Output must be new")
    assert (
        sha(OLD / "verification.json")
        == "8f8ef8a3897e26c0ed2b2c49c3b44748f23b3fdb16ff2d64a5aba86f3b8c83b8"
    )
    assert (
        sha(REFERENCE / "verification.json")
        == "fa8f7332bccf033f04236c1ff81dc7e838533d00828db63b17847e4613294190"
    )
    # Audit the frozen inputs before using them, without a new reference solve.
    for base in (OLD, REFERENCE):
        receipt = json.loads((base / "verification.json").read_text())
        payloads = receipt["files_sha256"] if base == OLD else receipt["payload_hashes"]
        for name, checksum in payloads.items():
            assert sha(base / name) == checksum
    output.mkdir(parents=True)
    initial, runtime = source_hashes(), runtime_identity()
    files = [ROOT / "src/cells" / name for name in initial] + [
        Path(__file__),
        ROOT / "tests/batch_fixtures.py",
        ROOT / "tests/unit/test_batch.py",
        ROOT / "tests/integration/test_batch_cli.py",
        ROOT / "configs/batch_source_pair.json",
        ROOT / "configs/batch_source_pair_branch.json",
        ROOT / "pyproject.toml",
        ROOT / "requirements-lock.txt",
        ROOT / "scripts/verify_source_pair_build.py",
        ROOT / "tests/source_pair_fixtures.py",
        ROOT / "tests/reference_source_pair_numerics.py",
        ROOT / "tests/reference_source_pair.py",
        ROOT / "tests/reference_emt.py",
        ROOT / "scripts/audit_source_pair_numerics.py",
        ref.eq.PANEL,
        ref.PROTOCOL,
    ]
    identity = {str(p.relative_to(ROOT)): sha(p) for p in files}
    records = {}
    for name in MODELS[:-1]:
        print(f"Scalar parity: {name}", flush=True)
        result = run_batch(definition([short_spec(name, 0.3), short_spec(name, 0.5)]))
        for world in result.spec.worlds:
            assert_parity(result.worlds[world.world_id], run(world.simulation))
        write_batch_run(output / name, result)
        records[name] = audit_batch(output / name) | {"scalar_parity": True}
    print("All 14 frozen source cases in one independent-clock batch", flush=True)
    panel = ref.eq.load_panel()
    specs = [load_spec(OLD / f"{case['id']}/resolved_config.json") for case in panel["cases"]]
    source_batch = definition(specs, ids=list(range(100, 114)))
    result = run_batch(source_batch)
    path = output / "source-reference-panel"
    write_batch_run(path, result)
    scores = {}
    for i, case in enumerate(panel["cases"]):
        world = result.worlds[100 + i]
        audit = audit_run(path / f"worlds/world-{100 + i}")
        with np.load(REFERENCE / case["id"] / "rk4-0.01/trajectory.npz") as arrays:
            oracle = ref.Model(panel, case)
            np.testing.assert_array_equal(world.times, arrays["accepted_times"])
            scores[case["id"]] = {
                "accepted": compare(
                    oracle,
                    world.times,
                    values(world.history),
                    arrays["refined"][np.searchsorted(arrays["sample_times"], world.times)],
                ),
                "observed": compare(
                    oracle, world.observations.times, values(world.observations), arrays["refined"]
                ),
                "audit": audit,
            }
    records["source-reference-panel"] = audit_batch(path) | {"frozen_scores": scores}
    checkpoints = result.checkpoint_at(
        {key: float(w.times[13]) for key, w in result.worlds.items()}
    )
    write_batch_snapshot(output / "source-replay-checkpoint", source_batch, checkpoints)
    saved = load_batch_snapshot(output / "source-replay-checkpoint")
    resumed = run_batch(saved.spec, saved.checkpoints)
    for key, world in resumed.worlds.items():
        original = result.worlds[key]
        for a, b in zip(world.history, original.history, strict=True):
            np.testing.assert_array_equal(a, b[13:])
        for name, array in vars(world.observations).items():
            selected = original.observations.times >= world.times[0]
            np.testing.assert_array_equal(array, vars(original.observations)[name][selected])
    write_batch_run(output / "source-replayed", resumed)
    records["source-replayed"] = audit_batch(output / "source-replayed") | {"exact_replay": True}
    spec = load_batch(ROOT / "configs/batch_source_pair.json")
    original = run_batch(spec)
    write_batch_run(output / "source-example", original, checkpoint_times=(0.5,))
    records["source-example"] = audit_batch(output / "source-example")
    changed = load_batch(ROOT / "configs/batch_source_pair_branch.json")
    checkpoints = branch_batch_checkpoints(spec, original.checkpoint_at(0.5), changed)
    future = run_batch(changed, checkpoints)
    branch_scores = {}
    for world in changed.worlds:
        branch = future.worlds[world.world_id]
        assert_parity(branch, run(world.simulation, checkpoints[world.world_id]))
        independent = reference_model(world.simulation)
        oracle = ref.integrate_reference(independent, refinement=0.1)
        accepted, observed = oracle.sample(branch.times), oracle.sample(branch.observations.times)
        branch_scores[str(world.world_id)] = {
            "accepted": compare(independent, branch.times, values(branch.history), accepted),
            "observed": compare(
                independent, branch.observations.times, values(branch.observations), observed
            ),
        }
        write_json(
            output / f"branch-reference-{world.world_id}.json",
            {"panel": independent.panel, "case": independent.case, "solver": oracle.stats},
        )
        np.savez_compressed(
            output / f"branch-reference-{world.world_id}.npz",
            accepted_times=branch.times,
            observed_times=branch.observations.times,
            accepted_reference=accepted,
            observed_reference=observed,
            **{
                f"segment_{i}_{key}": value
                for i, s in enumerate(oracle.segments)
                for key, value in (("times", s.t), ("increment_state", s.y.T))
            },
        )
    write_batch_run(output / "source-branched", future)
    records["source-branched"] = audit_batch(output / "source-branched") | {
        "independent_branch_scores": branch_scores
    }
    with zipfile.ZipFile(
        output / "implementation_sources.zip", "x", zipfile.ZIP_DEFLATED
    ) as archive:
        for p in files:
            assert sha(p) == identity[str(p.relative_to(ROOT))]
            archive.write(p, p.relative_to(ROOT))
    assert source_hashes() == initial and runtime_identity() == runtime
    report = {
        "status": "pass",
        "source_hashes": initial,
        "runtime": runtime,
        "implementation_source_hashes": identity,
        "batches": records,
        "files_sha256": {
            str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
        },
    }
    write_json(output / "verification.json", report)
    print(
        json.dumps(
            {
                "status": "pass",
                "batch_runs": len(records),
                "world_runs": sum(r["worlds"] for r in records.values()),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    verify(parser.parse_args().output)
