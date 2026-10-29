"""Freeze the full transient package without inspecting or launching contract jobs."""

import argparse
import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
SEED = Path("/mnt/workspaces/Cells/joint-water-phase-development-20261029-04")
PARENT = Path("/mnt/workspaces/Cells/joint-water-profiles-development-20261029-03")
PARENT_REVIEW = PARENT / "root-review-01/REVIEW.json"
PARENT_REVIEW_SHA = "ef1385547c76fcae7f06c64f9494b014bf75d2b1422d205f7429a17f3e9d3a2b"
NEW = (
    "validation/topology/joint_water_epoch_transient_fixtures.py",
    "validation/topology/joint_water_epoch_transient_reference.py",
    "tests/owned_joint_water_epoch_transient_helpers.py",
    "tests/unit/test_joint_water_epoch_transients.py",
)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("joint-water-epoch-refinement-preparation-")
    assert not output.exists()
    seed = read(SEED / "result.json")
    parent = read(PARENT / "result.json")
    assert seed["status"] == "passed" and seed["tests"] == dict(
        tests=4, failures=0, errors=0, skipped=0
    )
    assert parent["status"] == "passed" and parent["tests"] == dict(
        tests=53, failures=0, errors=0, skipped=0
    )
    assert sha(PARENT_REVIEW) == PARENT_REVIEW_SHA
    base = read(SEED / "workspace-manifest.json")
    assert base["qualified_base_source_sha256"] == parent["executed_runtime_source_sha256"]
    for name, expected in seed["output_sha256"].items():
        assert sha(SEED / name) == expected, name
    for relative in NEW:
        ast.parse((ROOT / relative).read_text())
    for name in (
        "run_joint_water_epoch_refinements.py",
        "prepare_joint_water_epoch_refinements.py",
    ):
        ast.parse((WORK / name).read_text())
    output.mkdir()
    workspace = output / "workspace"
    shutil.copytree(
        SEED / "workspace", workspace, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    for name, expected in (
        seed["executed_runtime_source_sha256"] | seed["executed_validation_source_sha256"]
    ).items():
        assert sha(workspace / name) == expected, name
    for relative in NEW:
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    shutil.copyfile(WORK / "run_joint_water_epoch_refinements.py", output / "runner.py")
    shutil.copyfile(Path(__file__), output / "prepare.py")
    for source, name in (
        (SEED / "result.json", "seed-result.json"),
        (PARENT / "result.json", "accepted-parent-result.json"),
        (PARENT_REVIEW, "accepted-parent-review.json"),
    ):
        target = output / "provenance" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    spec = importlib.util.spec_from_file_location("frozen_epoch_fixture", workspace / NEW[0])
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    parent_inputs = {}
    for family in fixture.FAMILIES:
        qualified = []
        for case in ("SIM", "close-reopen"):
            relative = "evidence/joint-water-profiles-trajectory-" + family + "-" + case + ".json"
            assert sha(PARENT / relative) == parent["output_sha256"][relative]
            value = read(PARENT / relative)
            assert value["status"] == "passed"
            qualified.append(value["inputs"])
            parent_inputs[relative] = sha(PARENT / relative)
        definitions = fixture.definitions(*qualified)
        for case, raw in definitions.items():
            dataset = "INIT-" + family if case == "INIT" else "SIM-" + family + "-" + case
            write(output / "inputs" / (dataset + ".json"), raw)
            times = set(raw["experiment"]["observation_times"])
            for name, rows in raw["experiment"].items():
                if name.endswith("_controls"):
                    for row in rows:
                        entries = row["controls" if "controls" in row else "schedule"]
                        clocks = [c["time"] for c in entries]
                        assert clocks[0] == 0.0 and clocks == sorted(set(clocks))
                        assert all(0 <= t <= 4e-6 and t in times for t in clocks)
    shared = (
        "src/cells/core/specs.py",
        "src/cells/core/schedule.py",
        "src/cells/models/registry.py",
        "src/cells/ensemble/ionic.py",
        "src/cells/core/tissue_profile_composition_preparation.py",
    )
    live = {}
    for relative in shared:
        target = output / "live-shared-at-preparation" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
        live[relative] = sha(target)
    protocol = dict(
        status="prepared_not_launched",
        purpose="Complete independent INIT and actual carried SIM refinement without rebasing",
        datasets=list(fixture.DATASETS),
        phase_duration_s=4e-6,
        production_dt_s=[0.03125e-6, 0.015625e-6],
        independent=dict(
            method="segmented DOP853",
            rtol=2e-11,
            atol=2e-14,
            charge_atol_C=1e-29,
            background_transfer_atol_fmol=1e-24,
            clock_atol_s=1e-22,
            max_step_s=0.0625e-6,
        ),
        acceptance=dict(
            state_rtol=3e-9,
            state_atol=2e-11,
            charge_atol_C=3e-25,
            energy_atol_pJ=1e-9,
            water_atol_pL=2e-12,
            adenylate_and_phosphorus_atol_fmol=2e-12,
            damage_atol=4096 * sys.float_info.epsilon,
            SIM_background_increment_error_coarse_min=1e-20,
            SIM_background_increment_fine_factor=0.35,
            SIM_background_increment_fine_floor=1e-22,
            INIT_precision_label_floor=3e-13,
        ),
        sequence=(
            "Reference SIM starts from independent INIT endpoint; each production SIM "
            "starts from its own dt INIT checkpoint. Original physical references and "
            "every ledger remain continuous."
        ),
        reuse=(
            "Compute two INIT datasets once; reuse their reference/coarse/fine endpoints "
            "for four SIM cases. No repeated accepted contracts."
        ),
        padding=(
            "Physical capacities compact in trajectories; fixed gate/store/native slots "
            "retained. Padded carried-stage coverage retained separately with accepted71 "
            "contracts."
        ),
        arrays=(
            "Every declared observation/control boundary, all44/49 state fields, every "
            "accepted production grid point, all observables/layout fields, independent "
            "flats and actual source checkpoints. Failed evidence retained."
        ),
        endpoint_only_claim=False,
        convergence_order_claim=False,
        long_launch=(
            "Explicitly held until Chief accepts the exact71-contract receipt. Runner "
            "launch requires the accepted review and Chief-supplied SHA256; preparation "
            "never checks that job."
        ),
        runtime_seed=dict(path=str(SEED / "result.json"), sha256=sha(SEED / "result.json")),
        accepted_parent=dict(
            receipt=str(PARENT / "result.json"),
            sha256=sha(PARENT / "result.json"),
            review=str(PARENT_REVIEW),
            review_sha256=PARENT_REVIEW_SHA,
            canonical_input_sha256=parent_inputs,
        ),
    )
    write(output / "protocol.json", protocol)
    env = os.environ.copy()
    env.update(
        {
            n: "1"
            for n in (
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        }
    )
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="true",
        CUDA_VISIBLE_DEVICES="",
        JAX_ENABLE_COMPILATION_CACHE="false",
        PYTHONPATH=str(workspace / "src") + os.pathsep + str(workspace),
        CELLS_COMPONENT_SOURCE_ROOT=str(workspace),
    )
    assert sorted(os.sched_getaffinity(0)) == [4]
    sys.path[:0] = [str(workspace / "src"), str(workspace)]
    from validation.assembly.component_process import run_bounded

    directory = output / "collection-guard"
    directory.mkdir()
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
        str(workspace / "tests/unit/test_joint_water_epoch_transients.py"),
    ]
    run_bounded(
        command,
        directory=directory,
        cwd=workspace,
        env=env,
        timeout=60,
        max_rss_bytes=2**30,
        min_available_bytes=8 * 2**30,
    )
    stdout = (directory / "stdout.log").read_text()
    nodes = [
        line
        for line in stdout.splitlines()
        if "::test_complete_epoch_transient_refinement[" in line
    ]
    assert len(nodes) == 6 and all(
        sum("[" + d + "]" in n for n in nodes) == 1 for d in fixture.DATASETS
    )
    write(
        output / "collection.json",
        dict(status="collected_only_no_scientific_run", nodes=nodes, command=command),
    )
    for name, expected in (
        seed["executed_runtime_source_sha256"] | seed["executed_validation_source_sha256"]
    ).items():
        assert sha(workspace / name) == expected, name
    manifest = dict(
        status="prepared_not_launched",
        prepared_utc=datetime.now(UTC).isoformat(),
        datasets=list(fixture.DATASETS),
        runtime_source_sha256=seed["executed_runtime_source_sha256"],
        retained_validation_source_sha256=seed["executed_validation_source_sha256"],
        required_contract_receipt="/mnt/workspaces/Cells/joint-water-phase-development-20261029-05/result.json",
        required_contract_checks=71,
        expected_new_refinements=6,
        expected_total_checks=77,
        resources=dict(
            cpu_affinity=[4],
            max_child_tree_rss_bytes=2**30,
            min_available_host_bytes=8 * 2**30,
            max_unit_seconds=480,
            gpu=False,
            jit=False,
        ),
        live_shared_source_sha256=live,
        versions={
            n: importlib.metadata.version(n) for n in ("numpy", "scipy", "jax", "jaxlib", "pytest")
        },
        source_seed=protocol["runtime_seed"],
        accepted_parent=protocol["accepted_parent"],
        executing_import_paths=dict(
            cells=str(workspace / "src/cells"),
            tests=str(workspace / "tests"),
            validation=str(workspace / "validation"),
        ),
        automatic_polling=False,
        automatic_followup=False,
        scientific_runs_launched=0,
    )
    manifest["file_sha256"] = {
        str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
    }
    write(output / "manifest.json", manifest)
    print(
        json.dumps(
            dict(
                status="prepared_not_launched",
                manifest=str(output / "manifest.json"),
                sha256=sha(output / "manifest.json"),
                frozen_files=len(manifest["file_sha256"]),
                datasets=manifest["datasets"],
                contracts_job_queried=False,
                scientific_runs_launched=0,
            )
        )
    )


if __name__ == "__main__":
    main()
