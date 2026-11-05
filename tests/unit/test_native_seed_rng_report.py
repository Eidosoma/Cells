"""Versioned saved-reader controls; no RNG state, owner or source execution."""

import os
import sys
from pathlib import Path

import pytest

from tests.unit import test_native_seed_demo_report as old
from validation.betse import native_rng_runtime as runtime
from validation.betse import native_seed_rng_report as report
from validation.betse import native_seed_rng_runtime_software as software

write, read, pin = old.write, old.read, old.pin


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit frozen saved RNG controls required")
    with software.blocked(tmp_path):
        yield


def builtin_fixture(value, *, file_backed=False):
    """Declare a new inert packet explicitly; do not relabel any actual record."""
    plan = read(value.plan)
    manifest = read(value.source / "SNAPSHOT.json")
    directories = [value.source, *[p for p in value.source.rglob("*") if p.is_dir()]]
    for path in directories:
        path.chmod(0o755)
    helper = value.source / runtime.FILE
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text("# inert saved provenance producer; never imported\n")
    helper.chmod(0o444)
    manifest["files"][runtime.FILE] = dict(
        checkout_path=runtime.FILE,
        sha256=pin(helper)["sha256"],
        observation=dict(size=helper.stat().st_size),
        snapshot_mode=0o444,
    )
    snapshot_path = value.source / "SNAPSHOT.json"
    snapshot_path.chmod(0o644)
    selected = write(snapshot_path, manifest)
    snapshot_path.chmod(0o444)
    for path in reversed(directories):
        path.chmod(0o555)
    plan["source_snapshot"] = selected
    plan["producers"][runtime.FILE] = pin(helper)["sha256"]
    parameters = read(Path(plan["parameter_inputs"]["path"]))
    parameters["source_snapshot"] = selected
    plan["parameter_inputs"] = write(Path(plan["parameter_inputs"]["path"]), parameters)
    for name in ("parameters", "current_parameters"):
        acquisition_path = value.worker / "demo" / name / "acquisition.json"
        if acquisition_path.exists():
            acquisition = read(acquisition_path)
            acquisition["packet"] = plan["parameter_inputs"]
            write(acquisition_path, acquisition)
    declaration = read(Path(plan["demo_plan"]["path"]))
    declaration.update(
        snapshot_sha256=selected["sha256"], parameter_sha256=plan["parameter_inputs"]["sha256"]
    )
    declaration["source_plan"]["initial_rng_observation"].update(
        kind=report.WITNESS_KIND,
        runtime_producer="validation.betse.native_rng_runtime",
        runtime_producer_sha256=pin(helper)["sha256"],
    )
    plan["demo_plan"] = write(Path(plan["demo_plan"]["path"]), declaration)
    value.digest = write(value.plan, plan)["sha256"]
    version = ".".join(str(v) for v in sys.version_info[:3])
    for name in ("runtime-before.json", "runtime-after.json"):
        inventory = read(value.worker / name)
        inventory["python"] = version
        inventory["loaded_files"]["validation.betse.native_rng_runtime"] = pin(helper)
        if not file_backed:
            del inventory["loaded_files"]["_random"]
            inventory.setdefault("modules_without_files", []).append("_random")
        write(value.worker / name, inventory)
    write(
        value.worker / "source-after.json",
        dict(source_snapshot=selected, producers=plan["producers"]),
    )
    outcome = read(value.worker / "demo/outcome.json")
    row = next(r for r in outcome["captures"] if r["label"] == "pre_seed_rng_witness")
    path = value.worker / "demo" / row["path"]
    witness = read(path)
    witness["kind"] = report.WITNESS_KIND
    witness["source"]["files"][runtime.FILE] = pin(helper)["sha256"]
    witness["source"].update(
        snapshot_sha256=selected["sha256"],
        parameter_packet_sha256=plan["parameter_inputs"]["sha256"],
    )
    origin = witness["common_binding"]["runtime"]
    origin["python"] = version
    if not file_backed:
        del origin["files"]["_random"]
        origin.update(
            kind=runtime.KIND,
            interpreter=dict(
                implementation="cpython",
                cache_tag=sys.implementation.cache_tag,
                hexversion=sys.hexversion,
                builtin_module_names=list(sys.builtin_module_names),
            ),
            builtins={
                "_random": dict(
                    kind=runtime.BUILTIN_KIND,
                    name="_random",
                    origin="built-in",
                    loader="_frozen_importlib.BuiltinImporter",
                    has_location=False,
                    cached=None,
                    submodule_search_locations=None,
                    export="_random.Random",
                    methods=list(runtime.METHODS),
                    executable_sha256=origin["executable"]["sha256"],
                )
            },
        )
    row["sha256"] = write(path, witness)["sha256"]
    outcome["initial_rng_observation"] = dict(row)
    write(value.worker / "demo/outcome.json", outcome)
    process = read(value.output / "process/process-inputs.json")
    process["command"][process["command"].index("--plan-sha256") + 1] = value.digest
    write(value.output / "process/process-inputs.json", process)
    worker = read(value.worker / "result.json")
    worker["plan_sha256"] = value.digest
    worker_pin = write(value.worker / "result.json", worker)
    terminal = read(value.output / "result.json")
    terminal.update(plan_sha256=value.digest, worker=worker_pin)
    write(value.output / "result.json", terminal)
    return value


@pytest.mark.parametrize("mode", ("original", "disabled"))
@pytest.mark.parametrize("file_backed", (False, True))
def test_rng_report_version2_actual_reader_keeps_origins_explicit(tmp_path, mode, file_backed):
    value = builtin_fixture(old.fixture(tmp_path, version=12, mode=mode), file_backed=file_backed)
    result = report.inspect_attempt(value.plan, plan_sha256=value.digest, output=value.output)
    assert result["status"] == "completed_unqualified", result.get("issues")
    assert result["kind"] == report.KIND
    assert result["demonstration"]["initial_rng"]["observed"] is True
    assert result["common_starting_authority_established"] is False
    assert result["scientific_credit"] == 0
    with pytest.raises(ValueError):
        old.report.inspect_attempt(value.plan, plan_sha256=value.digest, output=value.output)


def test_rng_report_legacy_reader_output_is_preserved(tmp_path):
    value = old.fixture(tmp_path, version=12)
    actual = report.inspect_attempt(value.plan, plan_sha256=value.digest, output=value.output)
    expected = old.inspect(value)
    assert actual == expected


@pytest.mark.parametrize("version", (1, 2))
@pytest.mark.parametrize("mode", ("original", "disabled"))
def test_rng_report_public_starting_prefix_api_uses_actual_saved_protocol(tmp_path, version, mode):
    value = old.fixture(tmp_path, version=12, mode=mode)
    if version == 2:
        value = builtin_fixture(value)
    reader = old.report.Reader()
    plan, files, originals = report.read_plan(reader, value.plan, value.digest)
    outcome = read(value.worker / "demo/outcome.json")
    rows = [
        row
        for row in outcome["captures"]
        if row["label"] in ("before_seed_random_states", "pre_seed_rng_witness")
    ]
    captures = old.report._captures(reader, value.worker / "demo", rows)
    observed = report.initial_rng_captures(reader, value.worker / "demo", plan, outcome, captures)
    recorded = report.runtime_evidence(reader, value.worker, plan, files)
    assert originals and reader.issues == []
    assert observed["observed"] is True
    assert observed["common_starting_authority_established"] is False
    assert plan["_initial_rng_kind"] == (report.LEGACY_KIND, report.WITNESS_KIND)[version - 1]
    if version == 2:
        assert recorded["snapshot_producers"][runtime.FILE] == plan["producers"][runtime.FILE]


@pytest.mark.parametrize(
    "mutation",
    (
        "runtime_file",
        "missing_builtin",
        "duplicate_builtin",
        "wrong_interpreter",
        "origin",
        "helper",
        "partial",
        "version",
    ),
)
def test_rng_report_refuses_resealed_or_incomplete_builtin_evidence(tmp_path, mutation):
    value = builtin_fixture(old.fixture(tmp_path, version=12))
    if mutation in ("runtime_file", "missing_builtin", "duplicate_builtin", "helper"):
        path = value.worker / "runtime-after.json"
        row = read(path)
        if mutation == "runtime_file":
            row["loaded_files"]["_random"] = row["executable"]
        elif mutation == "missing_builtin":
            row["modules_without_files"].remove("_random")
        elif mutation == "duplicate_builtin":
            row["modules_without_files"].append("_random")
        else:
            del row["loaded_files"]["validation.betse.native_rng_runtime"]
        write(path, row)
    else:

        def mutate(witness):
            if mutation == "wrong_interpreter":
                witness["common_binding"]["runtime"]["builtins"]["_random"]["executable_sha256"] = (
                    "0" * 64
                )
            elif mutation == "origin":
                witness["common_binding"]["runtime"]["builtins"]["_random"]["origin"] = "frozen"
            elif mutation == "version":
                witness["kind"] = "unknown"

        old.initial_rng_capture_change(value, "pre_seed_rng_witness", mutate)
        if mutation == "partial":
            outcome = read(value.worker / "demo/outcome.json")
            row = next(r for r in outcome["captures"] if r["label"] == "pre_seed_rng_witness")
            (value.worker / "demo" / row["path"]).write_text("{partial")
    result = report.inspect_attempt(value.plan, plan_sha256=value.digest, output=value.output)
    assert result["status"] != "completed_unqualified"
    assert result["scientific_credit"] == 0 and result["verification_issues"]
