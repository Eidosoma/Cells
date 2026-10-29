"""Freeze qualified full8us bath recipes and 40 explicit future role commands.

Preparation reads JSON/source ASTs only. It never imports a model, initializes
state, evaluates equations, launches a child or queries an active computation.
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
    "validation/tissue/open_calcium_bath_trajectory_" + name + ".py"
    for name in ("common", "oracle", "production", "observers", "compare")
)
RUNNER = WORK / "run_open_calcium_bath_trajectory_role.py"


def helper():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    module = importlib.util.spec_from_file_location("bath_trajectory_artifact", ROOT / ADDITIONS[0])
    result = importlib.util.module_from_spec(module)
    module.loader.exec_module(result)
    return result


def checked_json(artifact, entry):
    path = Path(entry["path"]).resolve()
    if artifact.sha(path) != entry["sha256"]:
        raise ValueError("Qualification input changed: " + str(path))
    return artifact.read_json(path)


def declared_fields(source, family, epoch=False):
    """Read only literal field declarations; future workers check exact equality.

    HCN/catalog change channel axes without adding saved field names. Calcium
    replaces the kinetic observer map and explicitly uses passive diagnostics.
    """
    evidence = {}

    def expression(module, name):
        path = source / "src/cells/models" / (module + ".py")
        tree = ast.parse(path.read_text())
        evidence[str(path.relative_to(source))] = name
        values = [
            row.value
            for row in tree.body
            if isinstance(row, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in row.targets)
        ]
        if len(values) != 1:
            raise ValueError("Expected one frozen field declaration: " + module + "." + name)
        return values[0]

    def keys(node):
        if isinstance(node, ast.Dict):
            return [ast.literal_eval(key) for key in node.keys]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return keys(node.left) + keys(node.right)
        return []

    def literals(module, name):
        value = expression(module, name)
        if not isinstance(value, (ast.Tuple, ast.List)):
            raise ValueError("Expected frozen tuple field declaration")
        return [item.value for item in value.elts if isinstance(item, ast.Constant)]

    passive = keys(expression("surface_tissue", "STATE_AXES"))
    kinetic = passive + keys(expression("surface_kinetic", "STATE_AXES"))
    calcium = (
        kinetic
        + literals("spatial_calcium", "ER_FIELDS")
        + keys(expression("surface_calcium", "STATE_AXES"))
    )
    if len(calcium) != 34 or len(set(calcium)) != 34:
        raise ValueError("Complete frozen calcium saved-field declaration changed")
    observed = [
        "times",
        *calcium,
        *(key for key in literals("surface_tissue", "OBSERVATION_FIELDS") if key != "times"),
        *(key for key in literals("surface_calcium", "OBSERVATION_FIELDS") if key != "times"),
    ]
    states = calcium[:]
    if family == "energy":
        extra = keys(expression("surface_calcium_energy", "EXTRA_AXES"))
        states += extra
        observed += extra + literals("surface_calcium_energy", "READOUTS")
    observed += literals("open_calcium_runtime", "EXTRA_OBSERVATIONS")
    extra = keys(expression("surface_bath_events", "EXTRA_AXES"))
    states += extra
    observed += extra + literals("surface_bath_events", "EXTRA_OBSERVATIONS")
    if epoch:
        observed += ["init_phase_clock_s", "elapsed_time_s"]
    if (
        len(set(states)) != len(states)
        or len(set(observed)) != len(observed)
        or not set(states).issubset(observed)
        or len(states) != (36 if family == "calcium" else 40)
    ):
        raise ValueError("Static complete state/observer field composition failed")
    return states, observed, evidence


def add_dataset(artifact, output, dataset, raw, family, phase, epoch, protocol, jobs, datasets):
    if (
        raw["experiment"]["end_time"] != protocol["duration_s"]
        or raw["execution"]["dt"] != protocol["base_dt_s"]
        or raw["execution"]["jit"] is not False
        or raw["execution"]["backend"] != "cpu"
        or raw["model"]["phase"] != phase
    ):
        raise ValueError("Wrong original full8us CPU phase recipe: " + dataset)
    states, observers, declarations = declared_fields(output / "source", family, epoch)
    events = artifact.control_times(raw)
    if not set(raw["experiment"]["observation_times"]).issubset(events):
        raise ValueError("Original observer clocks changed")
    physics = artifact.digest(artifact.physical_definition(raw))
    production, oracles, grids = {}, {}, {}
    common = dict(
        family=family,
        dataset=dataset,
        phase=phase,
        is_epoch=epoch,
        state_fields=states,
        observer_fields=observers,
        physics_sha256=physics,
    )
    artifact.write_json(output / "inputs" / (dataset + "-original.json"), raw)
    for divisor in protocol["dt_divisors"]:
        refined = deepcopy(raw)
        refined["execution"]["dt"] = protocol["base_dt_s"] / divisor
        if artifact.physical_definition(refined) != artifact.physical_definition(raw):
            raise ValueError("Refinement changed original physics/controls/resource caps")
        path = "inputs/" + dataset + "-dt" + str(divisor) + ".json"
        artifact.write_json(output / path, refined)
        grid = artifact.accepted_times(refined, refined["execution"]["dt"])
        grids[str(divisor)] = grid.tolist()
        name = dataset + "-production_dt" + str(divisor)
        parent = "init-" + family + "-production_dt" + str(divisor) if epoch else None
        jobs[name] = common | dict(
            role="production",
            dt_divisor=divisor,
            definition=path,
            definition_sha256=artifact.digest(refined),
            expected_samples=len(grid),
            requires=[parent] if parent else [],
            parent=parent,
        )
        production[str(divisor)] = name
    finest = set(grids[str(max(protocol["dt_divisors"]))])
    if any(not set(grid).issubset(finest) for grid in grids.values()):
        raise ValueError("Original event-split refinement grids are not exactly nested")
    base = jobs[production["1"]]
    for variant in ("standard", "tight"):
        name = dataset + "-oracle_" + variant
        parent = "init-" + family + "-oracle_" + variant if epoch else None
        jobs[name] = common | dict(
            role="oracle",
            oracle_variant=variant,
            definition=base["definition"],
            definition_sha256=base["definition_sha256"],
            expected_samples=len(finest),
            requires=[parent] if parent else [],
            parent=parent,
        )
        oracles[variant] = name
    projection = dataset + "-projection"
    jobs[projection] = common | dict(
        role="projection",
        definition=base["definition"],
        definition_sha256=base["definition_sha256"],
        requires=list(oracles.values()),
        oracles=oracles,
    )
    integrations = [*oracles.values(), *production.values()]
    datasets[dataset] = dict(
        definition=base["definition"],
        integrations=integrations,
        oracles=oracles,
        production=production,
        projection=projection,
        complete_fields=len(states),
        observer_fields=observers,
        full_duration_s=raw["experiment"]["end_time"],
        exact_original_controls_s=events,
        accepted_times_by_divisor=grids,
        original_max_steps=raw["execution"]["max_steps"],
        original_max_trace_bytes=raw["execution"]["max_trace_bytes"],
        physics_sha256=physics,
        physical_recipe_controls_and_all_caps_unchanged=True,
        only_execution_changes=["dt"],
        static_observer_declarations=declarations,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    artifact = helper()
    qualification = artifact.read_json(args.qualification_inputs)
    protocol = artifact.read_json(WORK / "open_calcium_bath_trajectory_protocol.json")
    source_entry = qualification["qualified_source"]
    source = Path(source_entry["directory"]).resolve()
    capture = checked_json(artifact, source_entry["inventory"])
    original_hashes = capture["source_hashes"]
    if len(original_hashes) != source_entry["expected_files"]:
        raise ValueError("Accepted source inventory count changed")
    for key in ("ordinary_completion", "ordinary_components", "epoch_completion"):
        entry = qualification["receipts"][key]
        receipt = checked_json(artifact, entry)
        if receipt["status"] != "passed" or not entry["required_fields"]:
            raise ValueError("Require completed scoped qualification: " + key)
        if any(receipt.get(name) != value for name, value in entry["required_fields"].items()):
            raise ValueError("Qualification scope/counters changed: " + key)
    if qualification["receipts"]["ordinary_completion"]["required_fields"] != dict(
        total_family_and_adjacent_checks=103, core_window_regression_checks=53
    ):
        raise ValueError("Require the accepted ordinary103 and core53 receipt")
    output = args.output.resolve()
    if (
        output.exists()
        or output == ROOT
        or output.is_relative_to(source)
        or source.is_relative_to(output)
        or ROOT.is_relative_to(output)
    ):
        raise ValueError("Need a new separate bundle directory")
    for name, expected in original_hashes.items():
        path = (source / name).resolve()
        if not path.is_relative_to(source) or artifact.sha(path) != expected:
            raise ValueError("Qualified frozen source drift: " + name)
    for name in ADDITIONS:
        ast.parse((ROOT / name).read_text())
    for path in (Path(__file__), RUNNER):
        ast.parse(path.read_text())
    output.mkdir(parents=True, exist_ok=False)
    try:
        for name in original_hashes:
            target = output / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
        overlays = {}
        for name in ADDITIONS:
            target = output / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
            overlays[name] = dict(
                qualified_capture_sha256=original_hashes.get(name),
                prepared_sha256=artifact.sha(target),
                new_validation_only=True,
            )
        retained = output / "retained"
        retained.mkdir()
        (output / "inputs").mkdir()
        for original, target in (
            (Path(__file__), output / "prepare.py"),
            (RUNNER, output / "runner.py"),
            (args.qualification_inputs, retained / "qualification-inputs.json"),
            (Path(source_entry["inventory"]["path"]), retained / "qualified-source-inputs.json"),
        ):
            shutil.copyfile(original, target)
        for key, entry in qualification["receipts"].items():
            checked_json(artifact, entry)
            shutil.copyfile(entry["path"], retained / (key + ".json"))
        if qualification.get("source_correspondence"):
            checked_json(artifact, qualification["source_correspondence"])
            shutil.copyfile(
                qualification["source_correspondence"]["path"],
                retained / "source-correspondence.json",
            )
        protocol.update(
            status="prepared_for_root_review_no_launch",
            accepted_source=str(source),
            qualification_receipts=qualification["receipts"],
            qualification_inputs_sha256=artifact.sha(args.qualification_inputs),
        )
        artifact.write_json(output / "protocol.json", protocol)
        jobs, datasets, input_evidence = {}, {}, {}
        for family in protocol["families"]:
            evidence = qualification["evidence"]["ordinary-" + family]
            record = checked_json(artifact, evidence)
            shutil.copyfile(evidence["path"], retained / ("ordinary-" + family + "-evidence.json"))
            ordinary = record["definition"]
            add_dataset(
                artifact,
                output,
                "ordinary-" + family,
                ordinary,
                family,
                "SIM",
                False,
                protocol,
                jobs,
                datasets,
            )
            evidence = qualification["evidence"]["epoch-" + family]
            record = checked_json(artifact, evidence)
            shutil.copyfile(evidence["path"], retained / ("epoch-" + family + "-evidence.json"))
            epoch = record["definition"]
            init = epoch["model"]["handoff"]["source"]["definition"]
            sim = deepcopy(epoch)
            sim["model"] = deepcopy(epoch["model"]["scheduled"])
            add_dataset(
                artifact,
                output,
                "init-" + family,
                init,
                family,
                "INIT",
                False,
                protocol,
                jobs,
                datasets,
            )
            add_dataset(
                artifact,
                output,
                "epoch-" + family,
                sim,
                family,
                "SIM",
                True,
                protocol,
                jobs,
                datasets,
            )
            input_evidence[family] = dict(
                ordinary=qualification["evidence"]["ordinary-" + family],
                epoch=evidence,
                epoch_source_policy=(
                    "raw full8us INIT recipe only; discard short component checkpoint"
                ),
                numerical_trajectory_credit_from_component_evidence=False,
            )
        for family in protocol["families"]:
            for lane in ("ordinary", "epoch"):
                dataset = lane + "-" + family
                phases = (["init-" + family] if lane == "epoch" else []) + [dataset]
                requires = [
                    name
                    for phase in phases
                    for name in (*datasets[phase]["integrations"], datasets[phase]["projection"])
                ]
                base = jobs[datasets[dataset]["production"]["1"]]
                jobs[dataset + "-compare"] = {
                    key: base[key]
                    for key in (
                        "family",
                        "dataset",
                        "phase",
                        "is_epoch",
                        "definition",
                        "definition_sha256",
                        "physics_sha256",
                    )
                }
                jobs[dataset + "-compare"].update(
                    role="compare", requires=requires, compare_datasets=phases
                )
        if len(jobs) != protocol["planned_roles"] or len(jobs) != 40:
            raise ValueError("Prepared role count changed")
        if any(name not in jobs for job in jobs.values() for name in job["requires"]):
            raise ValueError("Unknown prepared role dependency")
        artifact.write_json(
            output / "plan.json",
            dict(
                jobs=jobs,
                datasets=datasets,
                input_evidence=input_evidence,
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
            if job["requires"]:
                template = name + "-dependency-runs.template.json"
                artifact.write_json(
                    output / template,
                    {
                        key: "<ABSOLUTE_COMPLETED_" + key + "_RUN_DIRECTORY>"
                        for key in job["requires"]
                    },
                )
                command += ["--dependency-runs", "<FILLED_" + template + ">"]
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
                validation_overlays=overlays,
                qualified_product_files_changed=[],
                jobs=len(jobs),
                datasets=list(datasets),
                preparation_imported_cells_or_jax=any(
                    name.split(".")[0] in {"cells", "jax", "jaxlib"} for name in sys.modules
                ),
                limitation="No parser/state/RHS/integrator or numerical role ran",
            ),
        )
        if any(name.split(".")[0] in {"cells", "jax", "jaxlib"} for name in sys.modules):
            raise ValueError("Preparation imported production or JAX")
        for name, expected in original_hashes.items():
            if name not in ADDITIONS and artifact.sha(output / "source" / name) != expected:
                raise ValueError("Copy changed qualified source: " + name)
        files = {
            str(path.relative_to(output)): artifact.sha(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        artifact.write_json(
            output / "manifest.json",
            dict(
                kind="cells.open_calcium_bath_full8us_prepared_bundle@1",
                file_sha256=files,
                accepted_source=str(source),
                qualification_inputs_sha256=artifact.sha(args.qualification_inputs),
                numerical_work_launched=False,
            ),
        )
        artifact.verify_bundle(output)
        print("Prepared only: " + str(output))
        print("Manifest SHA256: " + artifact.sha(output / "manifest.json"))
    except BaseException as error:
        artifact.failure(output, error, context=dict(stage="preparation_only_no_launch"))
        raise


if __name__ == "__main__":
    main()
