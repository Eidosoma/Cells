"""Freeze an unlaunched full8us qualification bundle from accepted raw evidence.

Only JSON, source inventories and event clocks are evaluated. No model parser,
state constructor, field/RHS, integrator, pytest or subprocess is called.
"""

import argparse
import ast
import importlib.util
import shutil
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
ADDITIONS = tuple(
    "validation/tissue/open_calcium_trajectory_" + name + ".py"
    for name in ("common", "oracle", "production", "compare")
)
RUNNER = WORK / "run_open_owned_trajectory_role.py"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    helper = importlib.util.spec_from_file_location("trajectory_artifact", ROOT / ADDITIONS[0])
    artifact = importlib.util.module_from_spec(helper)
    helper.loader.exec_module(artifact)
    protocol = artifact.read_json(WORK / "open_owned_trajectory_protocol.json")
    source = Path(protocol["accepted_source"]).resolve()
    receipt_path = Path(protocol["component_receipt"])
    if artifact.sha(receipt_path) != protocol["component_receipt_sha256"]:
        raise ValueError("Accepted component/public receipt changed")
    receipt = artifact.read_json(receipt_path)
    if receipt["total_distinct_checks"] != 96:
        raise ValueError("Wrong accepted qualification capture")
    capture = Path(receipt["component_inputs"]["path"])
    if artifact.sha(capture) != receipt["component_inputs"]["sha256"]:
        raise ValueError("Accepted source inventory changed")
    original_hashes = artifact.read_json(capture)["source_hashes"]
    if (
        output.exists()
        or output.is_relative_to(source)
        or source.is_relative_to(output)
        or output == ROOT
    ):
        raise ValueError("Need a new separate bundle directory")
    for name, expected in original_hashes.items():
        path = (source / name).resolve()
        if not path.is_relative_to(source) or artifact.sha(path) != expected:
            raise ValueError("Accepted frozen source drift: " + name)
    for name in ADDITIONS:
        if name in original_hashes:
            raise ValueError("New trajectory file would overwrite handed-off source")
        ast.parse((ROOT / name).read_text())
    for path in (Path(__file__), RUNNER):
        ast.parse(path.read_text())
    output.mkdir(parents=True, exist_ok=False)
    try:
        for name in original_hashes:
            target = output / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
        for name in ADDITIONS:
            target = output / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        for original, name in (
            (Path(__file__), "prepare.py"),
            (RUNNER, "runner.py"),
            (receipt_path, "retained/completion-verification.json"),
            (capture, "retained/component-inputs.json"),
        ):
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
        protocol["status"] = "prepared_for_root_review_no_launch"
        protocol["input_evidence"] = "exact raw definitions from accepted mixed stage artifacts"
        artifact.write_json(output / "protocol.json", protocol)
        inputs = output / "inputs"
        inputs.mkdir()
        jobs, input_checks = {}, {}
        for family in protocol["families"]:
            evidence = next(
                row
                for row in receipt["manufactured_configurations"]
                if Path(row["path"]).name == "stages-" + family + "-mixed.json"
            )
            evidence_path = Path(evidence["path"])
            if artifact.sha(evidence_path) != evidence["sha256"]:
                raise ValueError("Original mixed definition evidence changed")
            shutil.copyfile(evidence_path, output / "retained" / evidence_path.name)
            raw = artifact.read_json(evidence_path)["definition"]
            if (
                raw["experiment"]["end_time"] != protocol["duration_s"]
                or raw["execution"]["dt"] != protocol["base_dt_s"]
                or raw["execution"]["jit"] is not False
                or raw["execution"]["backend"] != "cpu"
            ):
                raise ValueError("Wrong original full8us CPU fixture")
            artifact.write_json(inputs / (family + "-original.json"), raw)
            events = artifact.control_times(raw)
            if raw["experiment"]["observation_times"] != events:
                raise ValueError("Original observations must be exact original control boundaries")
            grids = {}
            for divisor in protocol["dt_divisors"]:
                value = deepcopy(raw)
                value["execution"].update(dt=protocol["base_dt_s"] / divisor)
                restored = deepcopy(value)
                restored["execution"].update(
                    dt=raw["execution"]["dt"], max_steps=raw["execution"]["max_steps"]
                )
                if restored != raw or artifact.physical_definition(
                    value
                ) != artifact.physical_definition(raw):
                    raise ValueError("Refinement changed original physics/controls/resources")
                name = family + "-dt" + str(divisor) + ".json"
                artifact.write_json(inputs / name, value)
                times = artifact.accepted_times(value, value["execution"]["dt"])
                grids[str(divisor)] = times.tolist()
                jobs[family + "-production_dt" + str(divisor)] = dict(
                    role="production",
                    family=family,
                    dt_divisor=divisor,
                    definition="inputs/" + name,
                    definition_sha256=artifact.digest(value),
                    physics_sha256=artifact.digest(artifact.physical_definition(value)),
                    expected_samples=len(times),
                    requires=[],
                )
            fine = set(grids[str(max(protocol["dt_divisors"]))])
            if any(not set(times).issubset(fine) for times in grids.values()):
                raise ValueError("Prepared refinement grids are not exactly nested")
            coarse = jobs[family + "-production_dt1"]
            for variant in ("standard", "tight"):
                jobs[family + "-oracle_" + variant] = dict(
                    role="oracle",
                    family=family,
                    oracle_variant=variant,
                    definition=coarse["definition"],
                    definition_sha256=coarse["definition_sha256"],
                    physics_sha256=coarse["physics_sha256"],
                    expected_samples=len(fine),
                    requires=[],
                )
            dependencies = [family + "-" + name for name in protocol["roles_per_family"][:-1]]
            jobs[family + "-compare"] = dict(
                role="compare",
                family=family,
                definition=coarse["definition"],
                definition_sha256=coarse["definition_sha256"],
                physics_sha256=coarse["physics_sha256"],
                requires=dependencies,
            )
            input_checks[family] = dict(
                source_evidence=evidence,
                original_definition_sha256=artifact.digest(raw),
                physics_sha256=coarse["physics_sha256"],
                full_duration_s=raw["experiment"]["end_time"],
                exact_original_controls_s=events,
                accepted_times_by_divisor=grids,
                physics_and_all_controls_preserved=True,
                only_execution_changes=["dt"],
                numerical_max_steps=raw["execution"]["max_steps"],
            )
            artifact.write_json(
                output / (family + "-dependency-runs.template.json"),
                {name: "<ABSOLUTE_COMPLETED_" + name + "_RUN_DIRECTORY>" for name in dependencies},
            )
        artifact.write_json(
            output / "plan.json",
            dict(
                jobs=jobs,
                input_checks=input_checks,
                automatic_dependency_execution=False,
                numerical_work_launched=False,
            ),
        )
        commands = {}
        for name, job in jobs.items():
            command = [
                sys.executable,
                "-B",
                str(output / "runner.py"),
                "--bundle",
                str(output),
                "--execute",
                "--job",
                name,
                "--cpu",
                "<ROOT_SELECTED_CPU>",
                "--output",
                "<NEW_ABSOLUTE_RUN_DIRECTORY>",
            ]
            if job["role"] == "compare":
                command += ["--dependency-runs", "<FILLED_FAMILY_DEPENDENCY_RUNS_JSON>"]
            commands[name] = command
        artifact.write_json(
            output / "commands.json",
            dict(
                metadata_only_check=[
                    sys.executable,
                    "-B",
                    str(output / "runner.py"),
                    "--bundle",
                    str(output),
                    "--check",
                ],
                one_explicit_role_at_a_time=commands,
                automatic_launch=False,
            ),
        )
        artifact.write_json(
            output / "preparation.json",
            dict(
                status="prepared_not_executed",
                numerical_launches=0,
                active_job_polls=0,
                accepted_original_source_files=len(original_hashes),
                new_trajectory_modules=list(ADDITIONS),
                qualified_original_files_changed=[],
                jobs=len(jobs),
                families=protocol["families"],
                preparation_imported_cells_or_jax=any(
                    name.split(".")[0] in {"cells", "jax", "jaxlib"} for name in sys.modules
                ),
                checks=(
                    "AST/hash inventories; JSON physics/control preservation; nested event grids"
                ),
                limitation="No numerical role, parser admission or accuracy test has run",
            ),
        )
        for name, expected in original_hashes.items():
            if artifact.sha(output / "source" / name) != expected:
                raise ValueError("Copy changed qualified source: " + name)
        files = {
            str(path.relative_to(output)): artifact.sha(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        artifact.write_json(
            output / "manifest.json",
            dict(
                kind="cells.open_owned_full8us_prepared_bundle@1",
                file_sha256=files,
                accepted_source=str(source),
                component_receipt_sha256=protocol["component_receipt_sha256"],
                numerical_work_launched=False,
            ),
        )
        artifact.verify_bundle(output)
        print("Prepared only: " + str(output))
        print("Manifest SHA256: " + artifact.sha(output / "manifest.json"))
    except BaseException as error:
        artifact.failure(output, error, context={"stage": "preparation_only_no_launch"})
        raise


if __name__ == "__main__":
    main()
