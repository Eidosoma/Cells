"""Software-only metadata/gate checks; synthetic receipts give no physics credit.

No Cells model, state constructor, RHS, SciPy solver or trajectory role executes.
The copied model files are AST declaration inputs with execution traps.
"""

import builtins
import importlib.util
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from validation.tissue import open_calcium_bath_trajectory_common as artifact

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
DECLARATIONS = (
    "surface_tissue",
    "surface_kinetic",
    "spatial_calcium",
    "surface_calcium",
    "surface_calcium_energy",
    "open_calcium_runtime",
    "surface_bath_events",
)


def raw_recipe(family="calcium", phase="SIM"):
    """Deliberately nonphysical JSON: only clock/cap/recipe metadata is tested."""
    return dict(
        synthetic=True,
        model=dict(id="synthetic_" + family, phase=phase, amplitude=0.25),
        experiment=dict(
            end_time=8e-6,
            observation_times=[0.0, 2e-6, 8e-6],
            channel_controls=[dict(controls=[dict(time=0.0, value=1), dict(time=2e-6, value=2)])],
        ),
        execution=dict(
            dt=6.25e-8,
            max_steps=512,
            max_trace_bytes=2**20,
            jit=False,
            backend="cpu",
        ),
    )


def receipt(path):
    return dict(path=str(path), sha256=artifact.sha(path))


def freeze(bundle):
    artifact.write_json(
        bundle / "manifest.json",
        dict(
            synthetic=True,
            file_sha256={
                str(path.relative_to(bundle)): artifact.sha(path)
                for path in bundle.rglob("*")
                if path.is_file() and path != bundle / "manifest.json"
            },
        ),
    )


@pytest.fixture
def forbid_execution(monkeypatch):
    """Fail on equation/solver imports or process launches during these checks."""
    original = builtins.__import__

    def checked_import(name, *args, **kwargs):
        if name.split(".")[0] in {"cells", "jax", "jaxlib"} or name.startswith("scipy.integrate"):
            raise AssertionError("Metadata test attempted model/solver import: " + name)
        return original(name, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("Metadata test attempted a subprocess launch")

    monkeypatch.setattr(builtins, "__import__", checked_import)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(sys, "path", sys.path[:])


@pytest.fixture
def preparation(tmp_path, monkeypatch, forbid_execution):
    module = importlib.util.spec_from_file_location(
        "synthetic_bath_preparer", WORK / "prepare_open_calcium_bath_trajectories.py"
    )
    preparer = importlib.util.module_from_spec(module)
    module.loader.exec_module(preparer)
    source = tmp_path / "synthetic-qualified-source"
    copied = {}
    for name in DECLARATIONS:
        path = "src/cells/models/" + name + ".py"
        target = source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "raise AssertionError('Synthetic AST input must never execute')\n"
            + (ROOT / path).read_text()
        )
        copied[path] = artifact.sha(target)
    inventory = tmp_path / "synthetic-source-inputs.json"
    artifact.write_json(inventory, dict(synthetic=True, source_hashes=copied))
    synthetic_work = tmp_path / "synthetic-work"
    synthetic_work.mkdir()
    shutil.copyfile(
        WORK / "open_calcium_bath_trajectory_protocol.json",
        synthetic_work / "open_calcium_bath_trajectory_protocol.json",
    )
    monkeypatch.setattr(preparer, "WORK", synthetic_work)
    qualification = dict(
        synthetic=True,
        qualified_source=dict(
            directory=str(source), inventory=receipt(inventory), expected_files=len(copied)
        ),
        receipts={},
        evidence={},
    )
    for name, counters in dict(
        ordinary_completion=dict(
            total_family_and_adjacent_checks=103, core_window_regression_checks=53
        ),
        ordinary_components=dict(distinct_component_cases=91),
        epoch_completion=dict(synthetic_cases=154),
    ).items():
        path = tmp_path / ("synthetic-" + name + ".json")
        artifact.write_json(path, dict(status="passed", synthetic=True, **counters))
        qualification["receipts"][name] = receipt(path) | dict(required_fields=counters)
    for family in ("calcium", "energy"):
        ordinary, init = raw_recipe(family), raw_recipe(family, "INIT")
        epoch = dict(
            ordinary,
            model=dict(
                id="synthetic_epoch",
                scheduled=ordinary["model"],
                handoff=dict(
                    source=dict(
                        definition=init,
                        checkpoint=dict(time_s=6.25e-8, state="short synthetic sentinel"),
                    )
                ),
            ),
        )
        for prefix, definition in (("ordinary", ordinary), ("epoch", epoch)):
            path = tmp_path / ("synthetic-" + prefix + "-" + family + ".json")
            artifact.write_json(path, dict(synthetic=True, definition=definition))
            qualification["evidence"][prefix + "-" + family] = receipt(path)
    input_path = tmp_path / "synthetic-qualification-inputs.json"
    output = tmp_path / "synthetic-prepared-bundle"

    def execute():
        artifact.write_json(input_path, qualification)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                str(preparer.__file__),
                "--qualification-inputs",
                str(input_path),
                "--output",
                str(output),
            ],
        )
        preparer.main()
        return output

    return dict(
        preparer=preparer,
        qualification=qualification,
        source=source,
        output=output,
        execute=execute,
    )


def test_preparation_freezes_only_metadata_and_matching_full_INIT_graph(preparation):
    output = preparation["execute"]()
    artifact.verify_bundle(output)
    prepared = artifact.read_json(output / "preparation.json")
    plan = artifact.read_json(output / "plan.json")
    assert prepared["numerical_launches"] == prepared["active_job_polls"] == 0
    assert prepared["preparation_imported_cells_or_jax"] is False
    assert prepared["qualified_product_files_changed"] == []
    assert len(plan["jobs"]) == 40
    assert plan["automatic_dependency_execution"] is False
    for family in ("calcium", "energy"):
        for suffix in (
            "oracle_standard",
            "oracle_tight",
            "production_dt1",
            "production_dt2",
            "production_dt4",
        ):
            job = plan["jobs"]["epoch-" + family + "-" + suffix]
            parent = "init-" + family + "-" + suffix
            assert job["parent"] == parent and job["requires"] == [parent]
            assert plan["jobs"][parent]["phase"] == "INIT"
        for lane in ("ordinary", "init", "epoch"):
            dataset = plan["datasets"][lane + "-" + family]
            assert [len(dataset["accepted_times_by_divisor"][str(i)]) for i in (1, 2, 4)] == [
                129,
                257,
                513,
            ]
            for divisor in (1, 2, 4):
                raw = artifact.read_json(
                    output / plan["jobs"][dataset["production"][str(divisor)]]["definition"]
                )
                expected = raw_recipe(family, "INIT" if lane == "init" else "SIM")
                expected["execution"]["dt"] /= divisor
                assert raw == expected  # Entire original recipe, clocks and all caps.
        assert len(plan["jobs"]["ordinary-" + family + "-compare"]["requires"]) == 6
        assert len(plan["jobs"]["epoch-" + family + "-compare"]["requires"]) == 12
        retained = artifact.read_json(output / "retained" / ("epoch-" + family + "-evidence.json"))
        assert (
            retained["definition"]["model"]["handoff"]["source"]["checkpoint"]["time_s"] == 6.25e-8
        )
        full_init = artifact.read_json(output / "inputs" / ("init-" + family + "-original.json"))
        assert full_init["experiment"]["end_time"] == 8e-6


@pytest.mark.parametrize("defect", ["source", "inventory", "pending_epoch", "receipt_scope"])
def test_preparation_refuses_unqualified_or_changed_source_before_copy(preparation, defect):
    q = preparation["qualification"]
    if defect == "source":
        path = next(preparation["source"].rglob("*.py"))
        path.write_text(path.read_text() + "\n# post-inventory source drift\n")
    elif defect == "inventory":
        path = Path(q["qualified_source"]["inventory"]["path"])
        value = artifact.read_json(path)
        value["source_hashes"].pop(next(iter(value["source_hashes"])))
        artifact.write_json(path, value)
    else:
        entry = q["receipts"]["epoch_completion"]
        path = Path(entry["path"])
        value = artifact.read_json(path)
        value.update(status="pending") if defect == "pending_epoch" else value.update(
            synthetic_cases=153
        )
        artifact.write_json(path, value)
        entry["sha256"] = artifact.sha(path)  # Exercise semantic gates beyond outer hashing.
    with pytest.raises(ValueError):
        preparation["execute"]()
    assert not preparation["output"].exists()


@pytest.mark.parametrize("field", ["recipe", "duration", "step_cap", "trace_cap"])
def test_preparation_refuses_changed_qualified_raw_evidence_and_retains_failure(preparation, field):
    entry = preparation["qualification"]["evidence"]["ordinary-calcium"]
    path = Path(entry["path"])
    value = artifact.read_json(path)
    change_recipe(value["definition"], field)
    artifact.write_json(path, value)  # Retained qualification checksum remains fixed.
    with pytest.raises(ValueError, match="Qualification input changed"):
        preparation["execute"]()
    failure = artifact.read_json(preparation["output"] / "failure.json")
    assert failure["status"] == "failed"
    assert not (preparation["output"] / "manifest.json").exists()


@pytest.mark.parametrize("location", ["ordinary", "init", "epoch"])
def test_fixed_full8us_horizon_refuses_short_raw_phase_even_if_rehashed(preparation, location):
    entry = preparation["qualification"]["evidence"][
        ("ordinary" if location == "ordinary" else "epoch") + "-calcium"
    ]
    path = Path(entry["path"])
    value = artifact.read_json(path)
    raw = value["definition"]
    if location == "init":
        raw = raw["model"]["handoff"]["source"]["definition"]
    raw["experiment"]["end_time"] = 2e-6
    artifact.write_json(path, value)
    entry["sha256"] = artifact.sha(path)
    with pytest.raises(ValueError, match="Wrong original full8us CPU phase recipe"):
        preparation["execute"]()
    assert not (preparation["output"] / "manifest.json").exists()


def change_recipe(raw, field):
    if field == "recipe":
        raw["model"]["amplitude"] *= 2
    elif field == "duration":
        raw["experiment"]["end_time"] *= 0.5
    elif field == "step_cap":
        raw["execution"]["max_steps"] *= 2
    elif field == "trace_cap":
        raw["execution"]["max_trace_bytes"] *= 2
    elif field == "control":
        raw["experiment"]["channel_controls"][0]["controls"][1]["time"] *= 0.5
    else:
        raise AssertionError(field)


def dependency_bundle(tmp_path):
    bundle = tmp_path / "synthetic-dependency-bundle"
    bundle.mkdir()
    raw = raw_recipe(phase="INIT")
    artifact.write_json(bundle / "definition.json", raw)
    artifact.write_json(bundle / "protocol.json", dict(synthetic=True, duration_s=8e-6))
    parent = "init-calcium-production_dt1"
    job = dict(
        role="production",
        family="calcium",
        dataset="init-calcium",
        phase="INIT",
        dt_divisor=1,
        definition="definition.json",
        definition_sha256=artifact.digest(raw),
        physics_sha256=artifact.digest(artifact.physical_definition(raw)),
        requires=[],
    )
    artifact.write_json(bundle / "plan.json", dict(synthetic=True, jobs={parent: job}))
    freeze(bundle)
    return bundle, parent, job, raw


@pytest.mark.parametrize("field", ["recipe", "duration", "step_cap", "trace_cap", "control"])
def test_physical_definition_gate_refuses_drift_after_resealing_raw_hash(
    tmp_path, field, forbid_execution
):
    bundle, parent, _, raw = dependency_bundle(tmp_path)
    change_recipe(raw, field)
    artifact.write_json(bundle / "definition.json", raw)
    plan = artifact.read_json(bundle / "plan.json")
    plan["jobs"][parent]["definition_sha256"] = artifact.digest(raw)
    artifact.write_json(bundle / "plan.json", plan)
    freeze(bundle)  # Both raw and manifest hashes now match; physics identity stays fixed.
    with pytest.raises(ValueError, match="physical recipe, controls or caps changed"):
        artifact.load_job(bundle, parent, "production")


def test_dt_only_change_retains_physics_and_caps(tmp_path, forbid_execution):
    bundle, parent, _, raw = dependency_bundle(tmp_path)
    raw["execution"]["dt"] /= 2
    artifact.write_json(bundle / "definition.json", raw)
    plan = artifact.read_json(bundle / "plan.json")
    plan["jobs"][parent]["definition_sha256"] = artifact.digest(raw)
    artifact.write_json(bundle / "plan.json", plan)
    freeze(bundle)
    _, _, restored = artifact.load_job(bundle, parent, "production")
    assert restored == raw


def synthetic_parent(tmp_path):
    bundle, name, job, raw = dependency_bundle(tmp_path)
    folder = tmp_path / "synthetic-parent-receipt"
    (folder / "data").mkdir(parents=True)
    (folder / "guard").mkdir()
    (folder / "data/synthetic.txt").write_text("No state or numerical trajectory exists here.\n")
    protocol = artifact.read_json(bundle / "protocol.json")
    child = artifact.identity(bundle, protocol, job, raw, name) | dict(synthetic=True, dt_divisor=1)
    guard = dict(
        status="completed",
        returncode=0,
        elapsed_seconds=0.01,
        samples=1,
        process_tree_memory_metric="rss",
        limits=dict(
            max_wall_seconds=480,
            max_process_tree_rss_bytes=2**30,
            min_available_host_memory_bytes=8 * 2**30,
        ),
        sampled_peak_process_tree_rss_bytes=1024,
        observed_process_high_water_bytes=1024,
        minimum_available_host_memory_bytes=16 * 2**30,
        synthetic=True,
    )
    inputs = dict(cpu=0, cpu_affinity=[0], synthetic=True)
    target = dict(requires=[name], parent=name, dataset="epoch-calcium")
    mapping = tmp_path / "synthetic-dependency-runs.json"
    artifact.write_json(mapping, {name: str(folder)})

    def seal(stale_guard=False):
        artifact.success(folder / "data", child)
        previous = deepcopy(guard)
        if stale_guard:
            previous["returncode"] = 7
        artifact.write_json(folder / "guard/result.json", guard)
        artifact.write_json(folder / "inputs.json", inputs)
        artifact.success(
            folder,
            dict(
                job_id=name,
                synthetic=True,
                bundle_manifest_sha256=artifact.sha(bundle / "manifest.json"),
                resource_result=previous,
                qualifier_result_sha256=artifact.sha(folder / "data/result.json"),
            ),
        )

    seal()
    return dict(
        bundle=bundle,
        name=name,
        folder=folder,
        child=child,
        guard=guard,
        inputs=inputs,
        target=target,
        mapping=mapping,
        seal=seal,
    )


def test_matching_synthetic_INIT_receipt_is_returned_without_execution(tmp_path, forbid_execution):
    data = synthetic_parent(tmp_path)
    result = artifact.dependencies(data["bundle"], data["target"], data["mapping"])
    assert result[data["name"]]["record"]["synthetic"] is True
    assert result[data["name"]]["record"]["phase"] == "INIT"
    assert result[data["name"]]["child_result_sha256"] == artifact.sha(
        data["folder"] / "data/result.json"
    )


@pytest.mark.parametrize("defect", ["absent", "wrong_name", "extra_parent"])
def test_missing_or_mismatched_INIT_mapping_refuses_before_receipt_use(
    tmp_path, defect, forbid_execution
):
    data = synthetic_parent(tmp_path)
    paths = {} if defect == "absent" else {"init-energy-production_dt1": str(data["folder"])}
    if defect == "extra_parent":
        paths[data["name"]] = str(data["folder"])
    artifact.write_json(data["mapping"], paths)
    with pytest.raises(ValueError, match="exactly the explicitly completed dependencies"):
        artifact.dependencies(data["bundle"], data["target"], data["mapping"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("job_id", "init-energy-production_dt1"),
        ("family", "energy"),
        ("phase", "SIM"),
        ("duration_s", 6.25e-8),
        ("definition_sha256", "foreign_recipe"),
        ("bundle_manifest_sha256", "foreign_source"),
    ],
)
def test_wrong_INIT_identity_refuses_even_with_resealed_receipt_hashes(
    tmp_path, field, value, forbid_execution
):
    data = synthetic_parent(tmp_path)
    data["child"][field] = value
    data["seal"]()
    with pytest.raises(ValueError, match="Dependency job/source/resource receipt disagrees"):
        artifact.dependencies(data["bundle"], data["target"], data["mapping"])


@pytest.mark.parametrize(
    "defect",
    [
        "status",
        "exit",
        "wall",
        "rss_limit",
        "reserve_limit",
        "metric",
        "peak",
        "high_water",
        "reserve",
        "affinity",
        "stale_guard",
        "resource_stop",
    ],
)
def test_corrupt_resource_receipt_refuses_even_with_valid_artifact_envelopes(
    tmp_path, defect, forbid_execution
):
    data = synthetic_parent(tmp_path)
    guard = data["guard"]
    if defect == "status":
        guard["status"] = "failed"
    elif defect == "exit":
        guard["returncode"] = 1
    elif defect == "wall":
        guard["limits"]["max_wall_seconds"] = 481
    elif defect == "rss_limit":
        guard["limits"]["max_process_tree_rss_bytes"] *= 2
    elif defect == "reserve_limit":
        guard["limits"]["min_available_host_memory_bytes"] //= 2
    elif defect == "metric":
        guard["process_tree_memory_metric"] = "pss"
    elif defect == "peak":
        guard["sampled_peak_process_tree_rss_bytes"] = 2**30 + 1
    elif defect == "high_water":
        guard["observed_process_high_water_bytes"] = 2**30 + 1
    elif defect == "reserve":
        guard["minimum_available_host_memory_bytes"] = 8 * 2**30 - 1
    elif defect == "affinity":
        data["inputs"]["cpu_affinity"] = [0, 1]
    elif defect == "resource_stop":
        artifact.write_json(data["folder"] / "guard/resource-stop.json", dict(synthetic=True))
    data["seal"](stale_guard=defect == "stale_guard")
    with pytest.raises(ValueError, match="Dependency job/source/resource receipt disagrees"):
        artifact.dependencies(data["bundle"], data["target"], data["mapping"])


def test_child_artifact_corruption_is_refused_without_reexecution(tmp_path, forbid_execution):
    data = synthetic_parent(tmp_path)
    (data["folder"] / "data/synthetic.txt").write_text("Corrupted after receipt sealing\n")
    with pytest.raises(ValueError, match="Dependency artifact changed"):
        artifact.dependencies(data["bundle"], data["target"], data["mapping"])


@pytest.mark.parametrize(
    "elapsed,samples",
    [
        (481.0, 1),
        (0.01, 0),
        (-0.01, 1),
        (None, 1),
        ("nan", 1),
        (True, 1),
        (0.01, 1.5),
        (0.01, True),
    ],
)
def test_actual_wall_and_sample_witness_refuse_resealed_receipts(
    tmp_path, elapsed, samples, forbid_execution
):
    data = synthetic_parent(tmp_path)
    data["guard"].update(elapsed_seconds=elapsed, samples=samples)
    data["seal"]()
    with pytest.raises(ValueError, match="Dependency job/source/resource receipt disagrees"):
        artifact.dependencies(data["bundle"], data["target"], data["mapping"])


@pytest.mark.parametrize("field", ["elapsed_seconds", "samples"])
def test_missing_actual_resource_witness_refuses_resealed_receipt(
    tmp_path, field, forbid_execution
):
    data = synthetic_parent(tmp_path)
    del data["guard"][field]
    data["seal"]()
    with pytest.raises(ValueError, match="Dependency job/source/resource receipt disagrees"):
        artifact.dependencies(data["bundle"], data["target"], data["mapping"])


@pytest.mark.parametrize("elapsed", [0.0, 480.0])
def test_actual_wall_boundaries_with_positive_samples_are_accepted(
    tmp_path, elapsed, forbid_execution
):
    data = synthetic_parent(tmp_path)
    data["guard"].update(elapsed_seconds=elapsed, samples=1)
    data["seal"]()
    assert data["name"] in artifact.dependencies(data["bundle"], data["target"], data["mapping"])


def test_overflowing_JSON_elapsed_refuses_despite_matching_artifact_hashes(
    tmp_path, forbid_execution
):
    data = synthetic_parent(tmp_path)
    data["guard"]["elapsed_seconds"] = "1e400"
    data["seal"]()
    # 1e400 is a JSON number, not the rejected nonstandard Infinity token.
    # Preserve fully matching child, guard and supervisor artifact envelopes.
    guard = data["folder"] / "guard/result.json"
    guard.write_text(guard.read_text().replace('"1e400"', "1e400"))
    supervisor_path = data["folder"] / "result.json"
    supervisor = artifact.read_json(supervisor_path)
    supervisor["artifacts"]["guard/result.json"] = artifact.sha(guard)
    artifact.write_json(supervisor_path, supervisor)
    supervisor_path.write_text(supervisor_path.read_text().replace('"1e400"', "1e400"))
    artifact.verify_result(data["folder"])
    with pytest.raises(ValueError, match="Dependency job/source/resource receipt disagrees"):
        artifact.dependencies(data["bundle"], data["target"], data["mapping"])
