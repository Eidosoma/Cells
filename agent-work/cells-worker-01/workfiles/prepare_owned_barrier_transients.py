"""Prepare six full-10us refinements from accepted immutable stage inputs."""

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
SEED = Path("/mnt/workspaces/Cells/owned-barrier-development-20261029-05")
STAGES = Path("/mnt/workspaces/Cells/owned-barrier-stage-handoff-20261029-01")
STAGE_SHA = "b9743a520c71871d98b0f61f12f165cae03d0c565875df9a5f2f911acd69f303"
PUBLIC = Path("/mnt/workspaces/Cells/owned-barrier-public-integration-20261029-01/contracts-01")
NEW = (
    "validation/transport/owned_barrier_transient_fixtures.py",
    "validation/transport/owned_barrier_transient_reference.py",
    "tests/owned_barrier_transient_helpers.py",
    "tests/unit/test_owned_barrier_transients.py",
)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.parent == Path("/mnt/workspaces/Cells") and not output.exists()
    assert sha(STAGES / "result.json") == STAGE_SHA
    stage = read(STAGES / "result.json")
    assert stage["distinct_checks"] == 62 and stage["full_independent_stage_comparisons"] == 90
    assert read(SEED / "result.json")["status"] == "passed"
    seed = read(SEED / "source-manifest.json")
    for name, expected in stage["executed_owned_runtime_sha256"].items():
        assert sha(ROOT / name) == sha(SEED / "workspace" / name) == expected
    for name in (*NEW, "agent-work/cells-worker-01/workfiles/run_owned_barrier_transients.py"):
        ast.parse((ROOT / name).read_text())
    output.mkdir()
    workspace = output / "workspace"
    workspace.mkdir()
    for relative, expected in seed["source_sha256"].items():
        source, target = SEED / "workspace" / relative, workspace / relative
        assert sha(source) == expected, relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for name in NEW:
        target = workspace / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(WORK / "run_owned_barrier_transients.py", output / "runner.py")
    shutil.copyfile(Path(__file__), output / "prepare.py")
    for source, name in (
        (STAGES / "result.json", "stage-result.json"),
        (STAGES / "component-tests.xml", "stage-tests.xml"),
        (PUBLIC / "result.json", "public-result.json"),
        (PUBLIC / "tests.xml", "public-tests.xml"),
        (PUBLIC / "verification.json", "public-verification.json"),
    ):
        target = output / "retained" / name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, target)
    for name, expected in stage["evidence_sha256"].items():
        assert sha(Path(name)) == expected
    spec = importlib.util.spec_from_file_location("barrier_fixture", workspace / NEW[0])
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    inputs = {}
    for dataset in fixture.DATASETS:
        family, case = dataset.split("-", 1)
        source = next(
            Path(row["report"]["path"])
            for row in stage["stages"]
            if Path(row["report"]["path"]).name == f"stages-{family}-{case}-False.json"
        )
        original = read(source)["definition"]
        raw = fixture.definition(original)
        assert raw["model"] == original["model"] and raw["experiment"] == original["experiment"]
        write(output / "inputs" / (dataset + ".json"), raw)
        inputs[dataset] = dict(
            source=str(source),
            source_sha256=sha(source),
            samples_s=fixture.samples(raw),
            chunk_ends_s=fixture.CHUNK_ENDS_S,
        )
    protocol = dict(
        status="prepared_full_suite_held_for_root_launch",
        datasets=list(fixture.DATASETS),
        original_horizon_s=fixture.END_S,
        production_dt_s=[fixture.DT_S, fixture.DT_S / 2],
        continuous_chunk_ends_s=fixture.CHUNK_ENDS_S,
        physical_scope=(
            "exact full56 owners, fixed geometry, all20/35/39 state fields and actual history"
        ),
        reference=dict(
            method="independent segmented DOP853",
            relative_tolerances=[2e-11, 1e-11],
            bulk_atols=[2e-14, 1e-14],
            face_history_atols_fmol=[1e-24, 5e-25],
            charge_atols_C=[1e-29, 5e-30],
            clock_atols_s=[1e-22, 5e-23],
            maximum_steps_s=[62.5e-9, 31.25e-9],
            uncertainty_budget_fraction_max=0.1,
        ),
        budgets=dict(
            state_rtol=3e-9,
            state_atol=2e-11,
            charge_atol_C=3e-25,
            clock_atol_s=1e-17,
            independent_energy_atol_pJ=1e-9,
            independent_material_atol_fmol=2e-11,
            unchanged_parent_checks=True,
        ),
        refinement=dict(
            full_state_fine_factor=0.35,
            full_state_precision_floor=3e-13,
            face_resolution_floor_fmol=1e-20,
            face_reference_uncertainty_multiplier=8,
            resolved_face_fine_factor=0.35,
            resolved_face_additive_floor_fmol=1e-22,
            resolved_face_reference_allowance_multiplier=2,
            no_convergence_order_claim=True,
        ),
        arrays=(
            "All accepted production-grid states, every sample/control boundary, "
            "all observables/layouts, reference fields and durable failures"
        ),
        continuation=(
            "Each role/resolution carries its own actual endpoint, all anchors, "
            "histories and absolute phase clock; no rebasing. The full run reuses "
            "the four completed pilot prefixes and continues from 0.5 us."
        ),
        pilot=dict(
            dataset="energy-reseal",
            duration_s=8 * fixture.DT_S,
            full_trajectory_credit=False,
            required_worker_sha256=sha(output / "runner.py"),
            required_worker_arguments=["--runner-sha256", sha(output / "runner.py")],
            exact_pilot_coverage=(
                "two independent tolerances/steps and two production dt on the original prefix"
            ),
        ),
        launch=dict(
            full_suite_held=True,
            cpu=3,
            threads=1,
            child_tree_rss_bytes=2**30,
            minimum_host_reserve_bytes=8 * 2**30,
            max_full_unit_seconds=480,
            maximum_pilot_unit_seconds=120,
            initial_full_eta_minutes=[90, 180],
        ),
        retained_stage_checks=62,
        retained_public_integration_checks=17,
        expected_new_full_comparisons=6,
        stages_and_smokes_distinct_from_trajectories=True,
        stage_handoff_sha256=STAGE_SHA,
        automatic_followup=False,
        inputs=inputs,
    )
    write(output / "protocol.json", protocol)
    environment = os.environ | dict(
        PYTHONPATH=str(workspace / "src") + ":" + str(workspace),
        PYTHONDONTWRITEBYTECODE="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="true",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        MALLOC_ARENA_MAX="2",
        CELLS_BARRIER_BUNDLE=str(output),
        CELLS_BARRIER_OUTPUT=str(output / "not-run"),
    )
    os.sched_setaffinity(0, {3})
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
        "tests/unit/test_owned_barrier_transients.py",
    ]
    resource = run_bounded(
        command,
        directory=directory,
        cwd=workspace,
        env=environment,
        timeout=60,
        max_rss_bytes=2**30,
        min_available_bytes=8 * 2**30,
    )
    counts = []
    for name in ("stage-tests.xml", "public-tests.xml"):
        cases = list(ET.parse(output / "retained" / name).getroot().iter("testcase"))
        assert all(
            not any(c.find(tag) is not None for tag in ("failure", "error", "skipped"))
            for c in cases
        )
        counts.append(len(cases))
    assert counts == [62, 17]
    files = {
        p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
    }
    write(
        output / "manifest.json",
        dict(
            status="prepared_not_launched",
            file_sha256=files,
            supervisor=dict(path="runner.py", sha256=sha(output / "runner.py")),
            runtime_sha256={k: v for k, v in seed["source_sha256"].items() if k.startswith("src/")},
            stage_handoff=dict(path=str(STAGES / "result.json"), sha256=STAGE_SHA),
            retained_checks=dict(stages=62, public=17),
            new_comparisons=6,
            collection=resource,
            live_shared_files_written=False,
            automatic_followup=False,
        ),
    )
    print(
        json.dumps(
            dict(
                status="prepared_not_launched",
                manifest=str(output / "manifest.json"),
                sha256=sha(output / "manifest.json"),
                numerical_work_run=False,
            )
        )
    )


if __name__ == "__main__":
    main()
