"""Regenerate six preceding model suites and audit their unchanged numeric artifacts.

Normal production APIs and existing independent acceptance drivers are used.
Old snapshots remain source-strict; only the preserved archive may load them.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.core.runner import branch_checkpoint, run  # noqa: E402
from cells.core.specs import ConfigError, load_spec  # noqa: E402
from cells.io import load_snapshot, runtime_identity, source_hashes, write_run  # noqa: E402
from scripts import verify_first_build, verify_pair_build  # noqa: E402

OLD = ROOT / "runs/model-004-2026-09-08"
ARCHIVE = ROOT / "reports/cells-0.6.0-source.tar.gz"
ARCHIVE_SHA = "ba8b0621186b39b4b745ba2539b1fb363c22d808632a3652f9227baf211c4899"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def require(value, message):
    if not value:
        raise ValueError(message)


def small_examples(output, *, pair=False):
    output.mkdir()
    fresh = (
        {
            "active": "pair_exchange_active",
            "blocked": "pair_exchange_blocked",
            "pulse": "pair_exchange_pulse",
        }
        if pair
        else {"pulse": "single_cell_pulse"}
    )
    parent_name = "active" if pair else "pulse"
    results = {}
    for name, config in fresh.items():
        result = run(load_spec(ROOT / f"configs/{config}.json"))
        write_run(output / name, result, checkpoint_times=(6.0,) if name == parent_name else ())
        results[name] = result
    parent = results[parent_name]
    snapshot = load_snapshot(
        output / parent_name / f"snapshots/step-{parent.checkpoint_at(6.0).step_index:06d}"
    )
    provenance = {"parent_snapshot_sha256": snapshot.fingerprint, "branch_time": 6.0}
    write_run(
        output / "resumed",
        run(snapshot.spec, snapshot.checkpoint),
        provenance=provenance | {"operation": "resume"},
    )
    config = "pair_exchange_release" if pair else "single_cell_rechallenge"
    changed = load_spec(ROOT / f"configs/{config}.json")
    branch = run(changed, branch_checkpoint(snapshot.spec, snapshot.checkpoint, changed))
    write_run(
        output / ("released" if pair else "rechallenged"),
        branch,
        provenance=provenance | {"operation": "branch"},
    )
    receipt = (verify_pair_build if pair else verify_first_build).verify(output)
    write_json(output / "verification.json", receipt)


def archived_check(output):
    require(sha(ARCHIVE) == ARCHIVE_SHA, "Preserved 0.6.0 archive changed")
    with tempfile.TemporaryDirectory(prefix="cells-06-audit-") as directory:
        with tarfile.open(ARCHIVE) as archive:
            expected = json.loads((OLD / "acceptance/verification.json").read_text())[
                "source_hashes"
            ]
            actual = {
                m.name.removeprefix("src/cells/"): hashlib.sha256(
                    archive.extractfile(m).read()
                ).hexdigest()
                for m in archive.getmembers()
                if m.isfile() and m.name.startswith("src/cells/")
            }
            require(actual == expected, "Archived source identity differs from accepted 0.6.0")
            archive.extractall(directory, filter="data")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(directory) / "src")
        script = """
import json
from pathlib import Path
import numpy as np
from cells.core.runner import run
from cells.io import load_snapshot, write_run
import cells
root=Path("runs/model-004-2026-09-08")
count=0
suites=("acceptance","synthetic-regression","pair-regression","composition-regression",
        "regulatory-regression","physical-cell-regression")
for suite in suites:
    for manifest in sorted((root/suite).rglob("manifest.json")):
        data=json.loads(manifest.read_text())
        if "files_sha256" in data:
            for relative in data["snapshots"]:
                load_snapshot(manifest.parent/relative); count+=1
assert count==159, count
parent=load_snapshot(root/"acceptance/Q00/snapshots/step-006000")
replay=run(parent.spec,parent.checkpoint)
with np.load(root/"acceptance/Q00/trajectory.npz") as old:
    for name,value in zip(replay.history._fields,replay.history,strict=True):
        np.testing.assert_array_equal(old[name][6000:],value)
write_run(Path(__import__("sys").argv[1]),replay,provenance={"operation":"archived_0.6.0_replay"})
print(json.dumps({"status":"pass","version":cells.__version__,"snapshots":count,"exact_archived_replay":True}))
"""
        result = subprocess.run(
            [sys.executable, "-c", script, str(output / "archived-06-replay")],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        if result.returncode:
            write_json(
                output / "archived-audit-failure.json",
                {"status": "failed", "stdout": result.stdout, "stderr": result.stderr},
            )
            raise ValueError(f"Archived audit failed: {result.stderr}")
        receipt = json.loads(result.stdout)
    try:
        load_snapshot(OLD / "acceptance/Q00/checkpoint_final")
    except ConfigError as error:
        require("source differs" in str(error), "Old snapshot failed for an unexpected reason")
    else:
        raise ValueError("Current source must not silently migrate 0.6.0 snapshots")
    return receipt | {"archive_sha256": ARCHIVE_SHA, "current_version_refuses_old_source": True}


def audit_suites(output, initial):
    suites = {
        "synthetic-regression": "synthetic-regression",
        "pair-regression": "pair-regression",
        "composition-regression": "composition-regression",
        "regulatory-regression": "regulatory-regression",
        "physical-cell-regression": "physical-cell-regression",
        "physical-pair-regression": "acceptance",
    }
    records = {}
    payloads = snapshots = arrays = 0
    for new, old in suites.items():
        for path in sorted((output / new).rglob("manifest.json")):
            manifest = json.loads(path.read_text())
            if "files_sha256" not in manifest:
                continue
            relative = path.parent.relative_to(output / new)
            prior = OLD / old / relative
            require(
                manifest["source_hashes"] == initial,
                "Source changed during previous-model regression",
            )
            require(manifest["runtime"] == runtime_identity(), "Runtime changed")
            for name, digest in manifest["files_sha256"].items():
                p = (path.parent / name).resolve()
                require(
                    p.is_relative_to(path.parent.resolve()) and sha(p) == digest,
                    "Invalid regression payload",
                )
                payloads += 1
            with (
                np.load(path.parent / "trajectory.npz", allow_pickle=False) as a,
                np.load(prior / "trajectory.npz", allow_pickle=False) as b,
            ):
                require(set(a.files) == set(b.files), "Previous-model array inventory differs")
                for name in a.files:
                    require(
                        a[name].dtype == b[name].dtype and a[name].shape == b[name].shape,
                        "Shape/dtype changed",
                    )
                    np.testing.assert_array_equal(a[name], b[name])
                    arrays += 1
                for snapshot in manifest["snapshots"]:
                    saved = load_snapshot(path.parent / snapshot)
                    snapshots += 1
                    at = np.flatnonzero(a["accepted_times"] == saved.checkpoint.time)[0]
                    for name, value in zip(
                        saved.checkpoint.state._fields, saved.checkpoint.state, strict=True
                    ):
                        np.testing.assert_array_equal(a[name][at], value)
            records[str(path.parent.relative_to(output))] = {
                "manifest_sha256": sha(path),
                "exact_previous_trajectory": True,
            }
    require(len(records) == 62, "Expected all 62 previously accepted production runs")
    return {
        "runs": records,
        "payload_hashes": payloads,
        "snapshots": snapshots,
        "exact_arrays": arrays,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    require(not output.exists(), "Output must be new")
    output.mkdir(parents=True)
    sources, runtime = source_hashes(), runtime_identity()
    archive_result = archived_check(output)
    print("Archived 0.6.0 replay and snapshot audit pass", flush=True)
    small_examples(output / "synthetic-regression")
    small_examples(output / "pair-regression", pair=True)
    jobs = [
        ("composition-regression", "verify_composition_build.py", []),
        (
            "regulatory-regression",
            "verify_emt_build.py",
            [str(ROOT / "runs/m1b-2026-09-08/source-reference/reference.json")],
        ),
        ("physical-cell-regression", "verify_bioelectric_build.py", []),
        ("physical-pair-regression", "verify_bioelectric_pair_build.py", []),
    ]
    for name, driver, arguments in jobs:
        print(name, flush=True)
        with (output / f"{name}.log").open("x") as log:
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / driver),
                    *arguments,
                    "--output",
                    str((output / name).resolve()),
                ],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                check=True,
                timeout=600,
            )
    audit = audit_suites(output, sources)
    require(source_hashes() == sources and runtime_identity() == runtime, "Source/runtime changed")
    receipt = {
        "status": "pass",
        "source_hashes": sources,
        "runtime": runtime,
        "archived_source": archive_result,
        "driver_sha256": sha(Path(__file__)),
        **audit,
        "suite_receipts": {
            str(p.relative_to(output)): sha(p) for p in output.rglob("verification.json")
        },
    }
    write_json(output / "verification.json", receipt)
    print(
        json.dumps(
            {"status": "pass", "runs": len(audit["runs"]), "exact_arrays": audit["exact_arrays"]}
        )
    )


if __name__ == "__main__":
    main()
