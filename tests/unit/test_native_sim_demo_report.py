"""Complete direct SIM saved packets made from inert stdlib metadata only."""

import hashlib
import os
import struct
from pathlib import Path

import pytest

from tests.unit import test_native_seed_demo_report as old
from tests.unit import test_native_sim_demo_observation as observed
from validation.betse import native_sim_demo_report as report
from validation.betse import native_sim_demo_report_software as software

write, read, pin = old.write, old.read, old.pin


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit frozen blocked SIM report release required")
    with software.blocked(tmp_path):
        yield


def identity(name):
    return hashlib.sha256(name.encode()).hexdigest()


def fixture(tmp_path, *, count=3, mode="original"):
    value = old.fixture(
        tmp_path,
        endpoint="init_terminal",
        version=12,
        numpy_origin=True,
        parameter_prefix=True,
        mode=mode,
    )
    native = tmp_path / "native/betse"
    native.mkdir(parents=True)
    (native / "metadata_fixture.py").write_text("# inert original-source inventory fixture\n")
    plan = read(value.plan)
    manifest = read(value.source / "SNAPSHOT.json")
    for p in [value.source, *[p for p in value.source.rglob("*") if p.is_dir()]]:
        p.chmod(0o755)
    stages = {}
    for name in report.launch._producers({"kind": report.DEMO_KIND}):
        p = value.source / name
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# inert saved producer; no source is executed\n")
            p.chmod(0o444)
    for alias, name in zip(report.launch.SIM_MODULES, report.launch.SIM_FILES, strict=True):
        stages[alias] = pin(value.source / name)["sha256"]
    helper = value.source / report.launch.SIM_FILE
    helper.chmod(0o644)
    helper.write_text(
        "MODULES = "
        + repr(report.launch.SIM_MODULES)
        + "\nSOURCE_PINS = "
        + repr(stages)
        + "\nREVIEW_PINS = "
        + repr(dict.fromkeys(stages, "b" * 64))
        + "\n"
    )
    helper.chmod(0o444)
    observation_policy = observed.saved_policy(
        value.source, tmp_path / "observation-reviews", stages["run"]
    )
    for p in value.source.rglob("*.py"):
        name = str(p.relative_to(value.source))
        manifest["files"][name] = dict(
            checkout_path=name,
            sha256=pin(p)["sha256"],
            observation=dict(size=p.stat().st_size),
            snapshot_mode=0o444,
        )
    (value.source / "SNAPSHOT.json").chmod(0o644)
    snapshot = write(value.source / "SNAPSHOT.json", manifest)
    (value.source / "SNAPSHOT.json").chmod(0o444)
    for p in reversed([value.source, *[p for p in value.source.rglob("*") if p.is_dir()]]):
        p.chmod(0o555)
    parameters = read(Path(plan["parameter_inputs"]["path"]))
    program_path = Path(parameters["program"]["manifest"]["path"])
    parameters["program"]["manifest"] = write(
        program_path, dict(fixture=True, ordered_path_permission=[])
    )
    bundle = read(Path(plan["input_bundle"]["path"]))
    bundle["modes"][mode]["program"] = parameters["program"]["manifest"]
    plan["input_bundle"] = write(Path(plan["input_bundle"]["path"]), bundle)
    parameters.update(
        source_snapshot=snapshot, acquisition_sequence=list(report.launch.ACQUISITION_SEQUENCE)
    )
    plan["parameter_inputs"] = write(Path(plan["parameter_inputs"]["path"]), parameters)
    declaration = read(Path(plan["demo_plan"]["path"]))
    declaration.update(
        kind=report.DEMO_KIND,
        endpoint=report.ENDPOINT,
        held=True,
        policy=report.launch.POLICY,
        init_iterations=None,
        parameter_sha256=plan["parameter_inputs"]["sha256"],
        snapshot_sha256=snapshot["sha256"],
    )
    declaration["source_plan"]["optional_sim_terminal"] = dict(
        module="validation.betse.native_sim_demo",
        source_sha256=pin(helper)["sha256"],
        review_sha256="b" * 64,
        acquisition_sequence=list(report.launch.ACQUISITION_SEQUENCE),
        maximum_iterations=512,
        complete_configured_calendar=True,
        selected_stop=False,
        same_retained_simulator_and_cells=True,
        distinct_fresh_loaded_parameters_and_SIM_phase=True,
        before_native_pickle=True,
        imports_before_callback=True,
        completed_observation=observation_policy,
        physical_checkpoint_or_scientific_admission=False,
    )
    plan.update(
        kind=report.LAUNCH_KIND,
        endpoint=report.ENDPOINT,
        init_iterations=None,
        source_snapshot=snapshot,
        acquisition_sequence=list(report.launch.ACQUISITION_SEQUENCE),
        stack_diagnostic=False,
        sim_original_sources=report.observation.original_sources(native.parent),
        runtime_roots=[*plan["runtime_roots"], str(native.parent)],
        limitations=report.launch.source_plan(endpoint=report.ENDPOINT),
        release_environment=dict.fromkeys(
            (
                report.launch.RELEASE,
                report.launch.DEMO_RELEASE,
                *report.launch.SIM_GATES,
                report.observation.RELEASE,
            ),
            "1",
        ),
    )
    plan["demo_plan"] = write(Path(plan["demo_plan"]["path"]), declaration)
    plan["producers"] = {
        name: manifest["files"][name]["sha256"] for name in report.launch._producers(declaration)
    }
    value.digest = write(value.plan, plan)["sha256"]
    for name in ("runtime-before.json", "runtime-after.json"):
        runtime = read(value.worker / name)
        for relative in plan["producers"]:
            runtime["loaded_files"][relative.removesuffix(".py").replace("/", ".")] = pin(
                value.source / relative
            )
        write(value.worker / name, runtime)
    write(
        value.worker / "source-after.json",
        dict(source_snapshot=snapshot, producers=plan["producers"]),
    )
    process = read(value.output / "process/process-inputs.json")
    process["command"][process["command"].index("--plan-sha256") + 1] = value.digest
    write(value.output / "process/process-inputs.json", process)
    outcome = read(value.worker / "demo/outcome.json")
    bootstrap = [
        f"sim_imports.{role}.{event}"
        for role in report.launch.SIM_MODULES
        for event in ("factory", "enter")
    ]
    outcome["operations"][:0] = [dict(name=name, status="returned") for name in bootstrap]
    for row in outcome["captures"]:
        if row["label"] == "pre_seed_rng_witness":
            path = value.worker / "demo" / row["path"]
            witness = read(path)
            witness["source"]["snapshot_sha256"] = snapshot["sha256"]
            witness["source"]["parameter_packet_sha256"] = plan["parameter_inputs"]["sha256"]
            witness["order"]["selected_boundaries"][:0] = [[name, "returned"] for name in bootstrap]
            row["sha256"] = write(path, witness)["sha256"]
            outcome["initial_rng_observation"] = dict(row)
    initial_id = next(
        read(value.worker / "demo" / row["path"])["identity"]
        for row in outcome["captures"]
        if row["label"] == "init_terminal.record"
    )
    current, prep, assembly, trial, request = [
        identity(x) for x in ("current", "prep", "assembly", "trial", "request")
    ]
    streams = [
        [identity("ready-numpy"), identity("ready-python")],
        [identity("after-numpy"), identity("after-python")],
    ]
    dt = struct.pack("!d", 0.125).hex()
    iterations = [
        [
            i,
            struct.pack("!d", i * 0.125).hex(),
            bool(i % 2),
            identity("state" + str(i)),
            [identity("n" + str(i)), identity("p" + str(i))],
            i + 1,
            identity("graph" + str(i)),
            [],
            [],
        ]
        for i in range(count)
    ]
    calendar = old.terminal_calendar_cache(iterations)
    record = dict(
        identity=trial,
        request=request,
        assembly=assembly,
        INIT=initial_id,
        parameters=current,
        operator_mode="original_value_and_flux"
        if mode == "original"
        else "original_value_only_flux_omitted",
        before=identity("before"),
        ready=identity("ready"),
        after=identity("after"),
        calendar=calendar["identity"],
        sampled=identity("sampled"),
        dt=dt,
        iterations=iterations,
        streams=streams,
        calls=list(range(count)),
        report=True,
        loop=True,
        context=True,
        before_native_pickle=True,
    )
    linkage = dict(
        trial_identity=trial,
        request_identity=request,
        completed_INIT_identity=initial_id,
        constructor_identity=assembly,
        current_parameters_identity=current,
        configured_iterations=count,
        maximum_iterations=512,
        configured_dt_bits=dt,
        operator_mode=record["operator_mode"],
        complete_configured_calendar=True,
        selected_stop=False,
        report_returned=True,
        loop_returned=True,
        context_returned=True,
        before_native_pickle=True,
        same_retained_simulator_and_cells=True,
        distinct_current_parameters=True,
        source_library_metadata_work_is_non_additive=True,
        native_pickle_checkpoint_or_physical_admission=False,
    )

    def capture(label, data):
        p = value.worker / "demo" / (label + ".json")
        row = dict(path=p.name, sha256=write(p, data)["sha256"], label=label, status="saved")
        outcome["captures"].append(row)

    capture(
        "sim_imports",
        [
            dict(
                role=role,
                proof_identity=11 + i,
                record_identity=21 + i,
                entered=True,
                exited=True,
                published=True,
                actual_import_not_replayed=True,
            )
            for i, role in enumerate(report.launch.SIM_MODULES)
        ],
    )
    capture(
        "sim_preparation.record",
        dict(
            identity=prep,
            init=initial_id,
            parameters=current,
            source_completed=True,
            phase_or_SIM_execution_admitted=False,
        ),
    )
    capture(
        "sim_assembly.record",
        dict(
            identity=assembly,
            preparation=prep,
            INIT=initial_id,
            current_parameters=current,
            constructor_completed=True,
            SIM_iterations=0,
            rng_after=streams[0],
        ),
    )
    capture("sim_run.record", record)
    for row in iterations:
        capture(f"sim_run.iteration.{row[0]:04d}.after", dict(identity=row[3]))
        capture(f"sim_run.iteration.{row[0]:04d}.rng", [dict(identity=x) for x in row[4]])
    for key in ("before", "ready", "after", "sampled"):
        capture("sim_run." + key, dict(identity=record[key]))
    capture("sim_run.calendar", calendar)
    capture("sim_run.configured_dt", dict(float64_bits=bytes.fromhex(dt)[::-1].hex()))
    for name, stream in zip(("stream_before", "stream_after"), streams, strict=True):
        capture("sim_run." + name, [dict(identity=x) for x in stream])
    capture("sim_run.linkage", linkage)
    outcome.update(
        kind=report.DEMO_KIND,
        endpoint=report.ENDPOINT,
        init_iterations=None,
        sim_completed=True,
        sim_time_steps_completed=count,
        init_short_history_completed=False,
        sim_imports_complete=True,
        sim_cleanup_complete=True,
        sim_secondary=[],
        sim_linkage=linkage,
    )
    outcome["completed_stage_trials"].extend(report.SIM_STAGES)
    outcome["operations"].append(dict(name="current_parameters", status="returned"))
    for stage in report.SIM_STAGES:
        outcome["operations"].extend(
            dict(name=n, status="returned") for n in (stage + "_request", stage, stage + ".record")
        )
    outcome["operations"].append(dict(name="sim_completed", status="returned"))
    outcome["operations"].append(dict(name="sim_final_check", status="returned"))
    outcome["operations"].extend(
        dict(name=name, status="returned")
        for name in ("sim_observation", "sim_observation_final_check")
    )
    outcome["sim_observation"] = observed.saved_observation(
        value.worker / "demo/sim_observation",
        observation_policy,
        stages["run"],
        trial,
        count=count,
        mode=mode,
    )
    write(value.worker / "demo/outcome.json", outcome)
    for index, name in enumerate(("parameters", "current_parameters")):
        rows = []
        directory = value.worker / "demo" / name
        for i, operation in enumerate(old.PARAMETER_OPERATIONS):
            target = directory / "evidence" / f"{i:02d}-{operation}"
            row = dict(
                name=operation,
                attempted=True,
                returned=True,
                returned_identity=1000 + index * 100 + i,
                evidence_complete=True,
                errors=[],
                graphs={},
                captures={},
            )
            write(target / "attempt.json", dict(name=operation, attempt=i + 1))
            row["payload"] = old.parameter_archive(target / "payload", numeric=True)
            write(target / "outcome.json", row)
            rows.append(row)
        acquisition = dict(
            packet=plan["parameter_inputs"],
            operations=rows,
            actual_world_ready_identity=rows[-3]["returned_identity"],
            actual_p_identity=rows[-1]["returned_identity"],
            acquisition_sequence=list(report.launch.ACQUISITION_SEQUENCE),
        )
        if index == 0:
            acquisition.update(
                construction_claim_opened=False, phase_or_persisted_owner_admission=False
            )
        else:
            acquisition.update(
                initial_owner_identity=1026,
                initial_p_identity=1028,
                distinct_fresh_native_load=True,
                INIT_SIM_or_persisted_owner_admission=False,
            )
        write(directory / "acquisition.json", acquisition)
    worker = read(value.worker / "result.json")
    worker.update(
        kind=report.LAUNCH_KIND,
        endpoint=report.ENDPOINT,
        init_iterations=None,
        plan_sha256=value.digest,
        sim_observation=outcome["sim_observation"],
    )
    terminal = read(value.output / "result.json")
    terminal.update(
        kind=report.LAUNCH_KIND,
        plan_sha256=value.digest,
        worker=write(value.worker / "result.json", worker),
    )
    write(value.output / "result.json", terminal)
    return value


@pytest.mark.parametrize("mode", ("original", "disabled"))
def test_sim_report_rng_origin_version2_preserves_direct_SIM_schema(tmp_path, mode):
    from tests.unit.test_native_seed_rng_report import builtin_fixture

    value = builtin_fixture(fixture(tmp_path, count=2, mode=mode))
    result = report.inspect_attempt(value.plan, plan_sha256=value.digest, output=value.output)
    write(value.base / "builtin-report.json", result)
    assert result["status"] == "completed_unqualified", result.get("verification_issues")
    assert result["kind"] == report.KIND and result["endpoint"] == "sim_terminal"
    assert result["demonstration"]["initial_rng"]["observed"] is True
    assert result["scientific_credit"] == 0


def inspect(value):
    return report.inspect_attempt(value.plan, plan_sha256=value.digest, output=value.output)


@pytest.mark.parametrize("mode", ("original", "disabled"))
@pytest.mark.parametrize("count", (1, 3, 512))
def test_sim_report_complete_direct_schema_preserves_whole_calendar(tmp_path, mode, count):
    value = fixture(tmp_path, count=count, mode=mode)
    result = inspect(value)
    assert result["verification_issues"] == []
    assert (
        result["status"] == "completed_unqualified" and result["sim_iterations_completed"] == count
    )
    assert result["init_iterations_completed"] == 3 and result["scientific_credit"] == 0
    assert result["parameter_load_prefix"]["acquisition_returned"] is True
    assert result["current_parameter_prefix"]["acquisition_returned"] is True
    assert result["initial_rng_inputs"] and result["common_starting_authority_established"] is False
    with pytest.raises(ValueError, match="schema"):
        old.report.inspect_attempt(value.plan, plan_sha256=value.digest)


@pytest.mark.parametrize(
    "mutation", ("legacy_kind", "one_load", "missing_gate", "helper_pin", "missing_stage")
)
def test_sim_report_resealed_plan_contract_refuses_before_completion(tmp_path, mutation):
    value = fixture(tmp_path)
    plan = read(value.plan)
    if mutation == "legacy_kind":
        plan["kind"] = old.report.LAUNCH_KINDS[-1]
    elif mutation == "one_load":
        plan["acquisition_sequence"] = ["initial_world_ready"]
    elif mutation == "missing_gate":
        del plan["release_environment"][report.launch.SIM_GATES[0]]
    elif mutation == "missing_stage":
        del plan["producers"][report.launch.SIM_FILES[-1]]
    else:
        plan["producers"][report.launch.SIM_FILE] = "0" * 64
    digest = write(value.plan, plan)["sha256"]
    with pytest.raises((ValueError, KeyError)):
        report.inspect_attempt(value.plan, plan_sha256=digest)


@pytest.mark.parametrize(
    "label,mutation",
    (
        ("sim_run.record", "time"),
        ("sim_run.record", "ordinal"),
        ("sim_run.record", "stream"),
        ("sim_run.record", "context"),
        ("sim_run.record", "count"),
        ("sim_run.linkage", "maximum"),
        ("sim_assembly.record", "parent"),
        ("sim_preparation.record", "current"),
        ("sim_run.iteration.0001.rng", "rng"),
        ("sim_run.configured_dt", "dt"),
        ("sim_imports", "proof"),
    ),
)
def test_sim_report_resealed_saved_raw_linkage_or_calendar_tamper_refuses(
    tmp_path, label, mutation
):
    value = fixture(tmp_path)

    def mutate(row):
        if mutation == "time":
            row["iterations"][1][1] = "0" * 16
        elif mutation == "ordinal":
            row["iterations"][1][0] = True
        elif mutation == "stream":
            row["streams"][0][0] = "0" * 64
        elif mutation == "context":
            row["context"] = False
        elif mutation == "count":
            row["iterations"].pop()
        elif mutation == "maximum":
            row["maximum_iterations"] = 64
        elif mutation == "parent":
            row["INIT"] = "0" * 64
        elif mutation == "current":
            row["parameters"] = "0" * 64
        elif mutation == "rng":
            row[0]["identity"] = "0" * 64
        elif mutation == "dt":
            row["float64_bits"] = "0" * 16
        else:
            row[1]["published"] = False

    old.change_capture(value, label, mutate)
    result = inspect(value)
    assert result["verification_issues"] and not result["source_execution_complete"]
    assert result["sim_iterations_completed"] == 0


@pytest.mark.parametrize(
    "mutation",
    ("missing", "duplicate", "failed", "file_bits", "current_pair", "missing_current", "runtime"),
)
def test_sim_report_missing_partial_or_unbound_evidence_never_promotes(tmp_path, mutation):
    value = fixture(tmp_path)
    outcome = read(value.worker / "demo/outcome.json")
    row = next(r for r in outcome["captures"] if r["label"] == "sim_run.iteration.0001.after")
    if mutation == "missing":
        outcome["captures"].remove(row)
    elif mutation == "duplicate":
        outcome["captures"].append(dict(row))
    elif mutation == "failed":
        row.update(status="capture_failed", error="saved failure")
    elif mutation == "file_bits":
        (value.worker / "demo" / row["path"]).write_text("{}")
    elif mutation == "missing_current":
        (value.worker / "demo/current_parameters/acquisition.json").unlink()
    elif mutation == "current_pair":
        p = value.worker / "demo/current_parameters/acquisition.json"
        r = read(p)
        r["initial_p_identity"] = 111
        write(p, r)
    else:
        p = value.worker / "runtime-after.json"
        r = read(p)
        r["loaded_files"].pop(report.launch.SIM_FILES[-1].removesuffix(".py").replace("/", "."))
        write(p, r)
    write(value.worker / "demo/outcome.json", outcome)
    result = inspect(value)
    assert result["verification_issues"] and result["sim_iterations_completed"] == 0


def test_sim_report_original_failure_and_partial_sim_arrays_remain_visible(tmp_path):
    value = fixture(tmp_path)
    primary = dict(type="OriginalError", cause="original cause")
    (value.output / "result.json").unlink()
    write(value.output / "failure.json", dict(primary=primary))
    old.change(
        value,
        "worker/demo/outcome.json",
        lambda r: r.update(
            status="failed",
            primary=primary,
            methods_completed=False,
            sim_completed=False,
            sim_time_steps_completed=0,
        ),
    )
    result = inspect(value)
    assert result["status"] == "failed" and result["sim_iterations_completed"] == 0
    assert result["failures"][0]["failure"]["primary"] == primary
    assert any(r["label"] == "sim_run.record" for r in result["demonstration"]["captures"])


def test_sim_report_later_failure_preserves_returned_sim_without_whole_run_credit(tmp_path):
    value = fixture(tmp_path)
    primary = dict(type="FinalWriterError", cause="original reporting cause")
    (value.output / "result.json").unlink()
    write(value.output / "failure.json", dict(primary=primary))
    old.change(
        value,
        "worker/demo/outcome.json",
        lambda row: row.update(status="failed", primary=primary),
    )
    result = inspect(value)
    assert result["status"] == "failed" and result["sim_iterations_completed"] == 0
    assert result["source_execution_complete"] is False
    saved = result["demonstration"]
    assert saved["outcome"]["sim_completed"] is True
    assert saved["outcome"]["sim_time_steps_completed"] == 3
    assert saved["complete_sim"] is None
    assert any(row["label"] == "sim_run.record" for row in saved["captures"])
    assert result["failures"][0]["failure"]["primary"] == primary


@pytest.mark.parametrize(
    "mutation",
    (
        "sim_preparation.record",
        "sim_assembly.record",
        "sim_run.record",
        "sim_final_check",
        "early_final",
        "failed_final",
        "duplicate_record",
    ),
)
def test_sim_report_requires_actual_public_record_calls_and_final_validation(tmp_path, mutation):
    value = fixture(tmp_path)

    def change(row):
        operations = row["operations"]
        if mutation in (*[name + ".record" for name in report.SIM_STAGES], "sim_final_check"):
            operations[:] = [entry for entry in operations if entry["name"] != mutation]
        elif mutation == "early_final":
            entry = operations.pop()
            operations.insert(
                next(i for i, op in enumerate(operations) if op["name"] == "sim_run"), entry
            )
        elif mutation == "failed_final":
            operations[-1]["status"] = "failed"
        else:
            entry = next(op for op in operations if op["name"] == "sim_run.record")
            operations.append(dict(entry))

    old.change(value, "worker/demo/outcome.json", change)
    result = inspect(value)
    assert result["verification_issues"] and result["sim_iterations_completed"] == 0
    assert result["source_execution_complete"] is False


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "partial",
        "wrong_record",
        "wrong_capture",
        "missing_blob",
        "duplicate",
        "failure",
        "late_failure",
    ),
)
def test_sim_report_observation_rejects_missing_corrupt_or_failed_evidence(tmp_path, mutation):
    value = fixture(tmp_path, count=1)
    target = value.worker / "demo/outcome.json"
    outcome = read(target)
    observed = outcome["sim_observation"]
    if mutation == "missing":
        del outcome["sim_observation"]
    elif mutation == "partial":
        observed["completed"] = False
    elif mutation == "wrong_record":
        Path(observed["record"]["path"]).write_text("{partial")
    elif mutation == "wrong_capture":
        Path(observed["captures"][0]["pin"]["path"]).write_text("{}")
    elif mutation == "missing_blob":
        artifacts = report.evidence.files(observed["captures"][0]["pin"]["path"])
        next(Path(row["path"]) for row in artifacts if row["path"].endswith(".bin")).unlink()
    elif mutation == "duplicate":
        observed["captures"][1] = dict(observed["captures"][0])
    elif mutation == "failure":
        observed["primary_present"] = True
    else:
        write(value.output / "failure.json", {"primary": "postsource failure"})
    write(target, outcome)
    result = inspect(value)
    assert not result["source_execution_complete"] and result["saved_comparison_request"] is None
    if mutation != "late_failure":
        assert result["verification_issues"]
    assert result["scientific_credit"] == 0


def test_sim_report_observation_postprocess_binds_actual_artifacts_and_independent_hash(tmp_path):
    value = fixture(tmp_path, count=1)
    before = inspect(value)
    assert before["status"] == "completed_unqualified", before["verification_issues"]
    assert before["saved_comparison_request"] is None
    selected = report.finalize_observation(
        value.plan,
        plan_sha256=value.digest,
        output=value.output,
        destination=tmp_path / "finalization",
    )
    result = report.inspect_attempt(
        value.plan,
        plan_sha256=value.digest,
        output=value.output,
        observation_request=selected["request_file"],
    )
    assert result["verification_issues"] == []
    assert result["saved_comparison_request"]["request"] == selected["request"]
    assert selected["accepted_observer_sha256"] == before["accepted_observer_sha256"]
    binding = read(Path(selected["request"]["binding"]["path"]))
    assert set(binding) == {
        "kind",
        "execution_source",
        "reviews",
        "runtime",
        "process",
        "terminal",
        "inputs",
        "original_sources",
        "observation_record",
    }
    assert binding["process"] == pin(value.output / "process/result.json")
    assert binding["runtime"] == pin(value.worker / "runtime-after.json")
    assert (
        not selected["comparison_accepted"]
        and not selected["common_starting_authority_established"]
    )


@pytest.mark.parametrize("fault", ("request", "terminal", "process", "result", "runtime"))
def test_sim_report_observation_postprocess_rejects_altered_partial_and_stale_binding(
    tmp_path, fault
):
    value = fixture(tmp_path, count=1)
    destination = tmp_path / "finalization"
    selected = report.finalize_observation(
        value.plan, plan_sha256=value.digest, output=value.output, destination=destination
    )
    target = {
        "request": destination / "request.json",
        "terminal": destination / "terminal.json",
        "result": destination / "result.json",
        "process": value.output / "process/result.json",
        "runtime": value.worker / "runtime-after.json",
    }[fault]
    target.write_text("{}")
    try:
        result = report.inspect_attempt(
            value.plan,
            plan_sha256=value.digest,
            output=value.output,
            observation_request=selected["request_file"],
        )
    except ValueError:
        return
    assert result["saved_comparison_request"] is None and result["verification_issues"]


def test_sim_report_observation_final_publication_failure_retains_partial_and_primary(
    tmp_path, monkeypatch
):
    value = fixture(tmp_path, count=1)
    destination = tmp_path / "finalization"
    primary = OSError("final publication failed")
    primary.__cause__ = ValueError("cause")
    original = report.snapshot.write_json

    def fail(path, data):
        if path.parent == destination and path.name in ("result.json", "failure.json"):
            path.write_text("{partial")
            raise primary
        return original(path, data)

    monkeypatch.setattr(report.snapshot, "write_json", fail)
    with pytest.raises(OSError) as raised:
        report.finalize_observation(
            value.plan, plan_sha256=value.digest, output=value.output, destination=destination
        )
    assert raised.value is primary and primary.__cause__.args == ("cause",)
    assert (destination / "request.json").is_file() and (destination / "binding.json").is_file()
    assert (destination / "failure.json").read_text() == "{partial"
    result = report.inspect_attempt(
        value.plan,
        plan_sha256=value.digest,
        output=value.output,
        observation_request=pin(destination / "request.json"),
    )
    assert result["saved_comparison_request"] is None and result["verification_issues"]


@pytest.mark.parametrize("created", (False, True))
def test_sim_report_observation_declared_directory_is_permission_not_required_creation(
    tmp_path, created
):
    value = fixture(tmp_path, count=1)
    plan = read(value.plan)
    parameters = read(Path(plan["parameter_inputs"]["path"]))
    root = Path(parameters["program"]["root"])
    program_path = Path(parameters["program"]["manifest"]["path"])
    selected = write(
        program_path,
        dict(
            fixture=True,
            ordered_path_permission=[
                ["unused_dirname", str(root / "unused")],
            ],
        ),
    )
    parameters["program"]["manifest"] = selected
    plan["parameter_inputs"] = write(Path(plan["parameter_inputs"]["path"]), parameters)
    bundle = read(Path(plan["input_bundle"]["path"]))
    bundle["modes"][plan["flux_operator"]]["program"] = selected
    plan["input_bundle"] = write(Path(plan["input_bundle"]["path"]), bundle)
    # Exercise the real bounded tree projection without manufacturing execution.
    if created:
        (root / "unused").mkdir()
    declaration = read(Path(plan["demo_plan"]["path"]))
    plan["_observation_policy"] = declaration["source_plan"]["optional_sim_terminal"][
        "completed_observation"
    ]
    report_value = dict(
        status="completed_unqualified",
        configuration_profile="original",
        demonstration=dict(
            completed_observation=dict(
                completed=True,
                record=read(value.worker / "demo/outcome.json")["sim_observation"]["record"],
            )
        ),
    )
    result = report._binding(
        report.Reader(), plan, value.output, report_value, pin(value.output / "result.json")
    )
    assert ("unused" in result["inputs"]["inventory"]["directories"]) is created
    (root / "unauthorized").mkdir()
    with pytest.raises(ValueError, match="declared native directories"):
        report._binding(
            report.Reader(), plan, value.output, report_value, pin(value.output / "result.json")
        )
