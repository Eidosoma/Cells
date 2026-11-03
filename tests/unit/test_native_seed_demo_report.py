"""Saved JSON/byte fixtures only; no BETSE source, owner or numerical execution."""

import json
import os
from contextlib import contextmanager
from types import FunctionType
from types import SimpleNamespace as NS

import pytest

from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import native_seed_demo_report as report
from validation.betse import native_seed_demo_report_software as software

_RAW_GUARDS = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit blocked saved-report software release required")
    adapter = NS(**dict(vars(software), reuse=software.base.reuse.reuse))
    namespace = dict(vars(guards), software=adapter, _BLOCKADE_FAILURES=())
    function = FunctionType(guards._blockade.__wrapped__.__code__, namespace)
    try:
        with contextmanager(function)(request, tmp_path):
            yield
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARDS.append(namespace["_BLOCKADE_FAILURES"])


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
    return pin(path)


def pin(path):
    return dict(path=str(path), sha256=report.snapshot.digest(path))


def read(path):
    return json.loads(path.read_text())


def fixture(tmp_path, mode="original", endpoint="seed", version=7):
    """A tiny explicitly synthetic snapshot passes the real byte verifier.

    Its files are inert text; these saved records grant no live source authority.
    No verifier, payload reader, runtime check or outcome check is substituted.
    """
    base = tmp_path / mode
    source = base / "prepared/source"
    source.mkdir(parents=True)
    files = {}
    for name in (report.DEMO, report.LAUNCH, report.PARAMETER):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# inert saved-report fixture; never imported\n")
        path.chmod(0o444)
        files[name] = dict(
            checkout_path=name,
            sha256=pin(path)["sha256"],
            observation=dict(size=path.stat().st_size),
            snapshot_mode=0o444,
        )
    (source / "checkout.patch").write_text("synthetic metadata fixture, no executable authority\n")
    manifest = dict(
        kind="cells.checkout_source_snapshot@1",
        status="complete",
        immutable=True,
        files=files,
        patch_sha256=pin(source / "checkout.patch")["sha256"],
    )
    manifest_pin = write(source / "SNAPSHOT.json", manifest)
    for path in reversed([source, *source.rglob("*")]):
        path.chmod(0o555 if path.is_dir() else 0o444)
    runtime_file = base / "runtime/interpreter"
    runtime_file.parent.mkdir()
    runtime_file.write_text("inert binary fixture, never executed\n")
    runtime = dict(executable=pin(runtime_file))
    input_file = base / "config/original.yaml"
    input_file.parent.mkdir()
    input_file.write_text("unchanged-original: true\n")
    program = write(base / "program.json", dict(fixture=True))
    external = [
        write(base / (name + ".json"), dict(fixture=name))
        for name in ("bootstrap", "writer-review")
    ]
    parameters = write(
        base / "prepared/inputs.json",
        dict(
            source_snapshot=manifest_pin,
            runtime=runtime,
            program=dict(root=str(input_file.parent), manifest=program),
        ),
    )
    demo = write(
        base / "prepared/demo-plan.json",
        dict(
            snapshot_sha256=manifest_pin["sha256"],
            parameter_packet=str(source.parent),
            parameter_sha256=parameters["sha256"],
            flux_operator=mode,
            endpoint=endpoint,
        ),
    )
    bundle = write(
        base / "input-bundle.json",
        dict(
            modes={mode: dict(config=str(input_file.parent), program=program)},
            source_inventory=dict(files={"original.yaml": dict(sha256=pin(input_file)["sha256"])}),
        ),
    )
    policy = dict(cpu=0, threads=1, wall_seconds=7200, max_rss_bytes=2**30, reserve_bytes=8 * 2**30)
    plan = dict(
        kind=report.LAUNCH_KINDS[version - 6],
        held=True,
        automatic_retry=False,
        source=str(source),
        source_snapshot=manifest_pin,
        producers={k: v["sha256"] for k, v in files.items()},
        demo_plan=demo,
        parameter_inputs=parameters,
        input_bundle=bundle,
        input_files=[pin(input_file)],
        runtime=runtime,
        runtime_roots=[str(runtime_file.parent)],
        external_files=external,
        flux_operator=mode,
        endpoint=endpoint,
        policy=policy,
    )
    plan_path = base / "launch-plan.json"
    plan_pin = write(plan_path, plan)
    output, worker = base / "actual", base / "actual/worker"
    loaded = {name.removesuffix(".py").replace("/", "."): pin(source / name) for name in files}
    inventory = dict(
        executable=pin(runtime_file),
        measured_cpu_affinity=[0],
        loaded_files=loaded,
        mapped_files=[],
    )
    write(worker / "runtime-before.json", inventory)
    write(worker / "runtime-after.json", inventory)
    write(
        worker / "source-after.json",
        dict(source_snapshot=manifest_pin, producers=plan["producers"]),
    )
    write(worker / "filesystem.json", dict(failures=[], first_error=None))
    limits = dict(
        max_wall_seconds=7200,
        max_process_tree_rss_bytes=2**30,
        min_available_host_memory_bytes=8 * 2**30,
    )
    process = dict(
        status="completed",
        returncode=0,
        limits=limits,
        process_tree_memory_metric="rss",
        elapsed_seconds=2.5,
        sampled_peak_process_tree_rss_bytes=8000000,
        minimum_available_host_memory_bytes=12 * 2**30,
        samples=10,
    )
    write(output / "process/result.json", process)
    write(
        output / "process/process-inputs.json",
        dict(
            command=[
                "inert-metadata-command",
                "--worker",
                str(plan_path),
                "--plan-sha256",
                plan_pin["sha256"],
                "--output",
                str(worker),
            ],
            cwd=str(source),
            limits=limits,
        ),
    )
    stages = ["geometry", "poisson", "core", "profiles", "junctions"]
    if endpoint != "seed":
        stages.append("init_setup")
    if endpoint == "init_prelude":
        stages.append("init_prelude")
    captures = []
    for i, stage in enumerate(stages[1:]):
        path = worker / f"demo/capture-{i:04d}.json"
        value = dict(source_completed=True, recorded_stage=stage, fixture=True)
        write(path, value)
        captures.append(
            dict(
                path=path.name, sha256=pin(path)["sha256"], label=stage + ".record", status="saved"
            )
        )
    raw_labels = ["poisson.cache", "core.cache", "profiles.after", "junctions.cache"]
    if endpoint != "seed":
        raw_labels.extend(("init_setup.before", "init_setup.after"))
    if endpoint == "init_prelude":
        raw_labels.extend(("init_prelude.before", "init_prelude.after", "init_prelude.raw_returns"))
    for label in raw_labels:
        path = worker / f"demo/capture-{len(captures):04d}.json"
        write(path, dict(fixture=True, raw_stage=label, identity=label))
        captures.append(
            dict(path=path.name, sha256=pin(path)["sha256"], label=label, status="saved")
        )
    operations = [
        dict(name=name, status="returned") for name in ("callback", "parameters", "geometry")
    ]
    for stage in stages[1:]:
        operations.extend(
            dict(name=name, status="returned") for name in (stage + "_request", stage)
        )
    outcome = dict(
        kind=report.DEMO_KINDS[version - 6],
        status="completed",
        flux_operator=mode,
        endpoint=endpoint,
        init_setup_completed=endpoint != "seed",
        init_prelude_completed=endpoint == "init_prelude",
        init_time_steps_completed=0,
        original_flux_defect_repaired=False,
        methods_completed=True,
        stage=stages[-1],
        completed_stage_trials=stages,
        operations=operations,
        primary=None,
        secondary=[],
        captures=captures,
        stage_work_is_non_additive=True,
        complete_seed_runner_or_INIT_SIM_restart_claim=False,
        scientific_or_physical_credit=0,
    )
    write(worker / "demo/outcome.json", outcome)
    diagnostics = dict(
        population=dict(cells=3),
        support=dict(maskM=dict(finite=True, nonzero=0)),
        domain_gate_passed=False,
        physical_admission=False,
    )
    geometry_captures = []

    def geometry_capture(label, value):
        path = worker / f"demo/geometry/capture-{len(geometry_captures):04d}.json"
        write(path, value)
        geometry_captures.append(
            dict(path=path.name, sha256=pin(path)["sha256"], label=label, status="saved")
        )

    geometry_capture("phase.record", dict(stages=["prefix", "caches", "dyna", "tail"]))
    for i in range(4):
        geometry_capture(f"phase.stage_trials.{i}.cache.cache", dict(identity=f"phase-cache-{i}"))
    geometry_steps = [
        "four_aliases",
        "cell_index",
        "cellVerts",
        "cellMatrices",
        "cell_vols",
        "mem_processing",
        "near_neigh",
        "makeECM",
        "environment",
        "grid_len",
        "make_maskM",
    ]
    for stage in ("lattice", "image", "mesh", "lifecycle", "geometry"):
        data = {key: f"{stage}-{key}" for key in ("before", "cache")}
        if stage == "geometry":
            data["stages"] = [[name, "step-" + name] for name in geometry_steps]
        geometry_capture(stage + ".record", data)
        for key in ("before", "cache"):
            geometry_capture(stage + "." + key + ".cache", dict(identity=data[key]))
    for stage in geometry_steps:
        geometry_capture("geometry.stage-" + stage, dict(identity="step-" + stage))
    geometry_capture("completed_geometry.cache", dict(identity="geometry-cache"))
    geometry_capture("diagnostics", diagnostics)
    write(
        worker / "demo/geometry/outcome.json",
        dict(
            status="source_completed",
            source_completed=True,
            source_error=None,
            metadata_error=None,
            capture_errors=[],
            captures=geometry_captures,
            diagnostics=diagnostics,
        ),
    )
    terminal = dict(
        kind=plan["kind"],
        status="source_completed_unqualified",
        scientific_credit=0,
        plan_sha256=plan_pin["sha256"],
        flux_operator=mode,
        endpoint=endpoint,
        public_entry_attempted=True,
        public_entry_returned=True,
        runtime_before_available=True,
        runtime_after_available=True,
        filesystem_audit_installed=True,
    )
    worker_pin = write(worker / "result.json", terminal)
    write(
        output / "result.json",
        dict(
            kind=plan["kind"],
            status="source_completed_unqualified",
            scientific_credit=0,
            plan_sha256=plan_pin["sha256"],
            process=process,
            worker=worker_pin,
        ),
    )
    return NS(
        base=base,
        source=source,
        plan=plan_path,
        digest=plan_pin["sha256"],
        output=output,
        worker=worker,
    )


def inspect(value):
    return report.inspect_attempt(value.plan, plan_sha256=value.digest, output=value.output)


def change(value, relative, function):
    path = value.output / relative
    data = read(path)
    function(data)
    write(path, data)


@pytest.mark.parametrize("endpoint", report.ENDPOINTS)
def test_report_completed_pair_preserves_zero_masks_and_no_physical_credit(tmp_path, endpoint):
    first, second = (
        fixture(tmp_path, endpoint=endpoint),
        fixture(tmp_path, mode="disabled", endpoint=endpoint),
    )
    paired = report.compare_modes(inspect(first), inspect(second))
    assert paired["paired_execution_complete"] is True
    assert all(paired["matching"].values())
    assert paired["original"]["geometry"]["diagnostics"]["domain_gate_passed"] is False
    assert paired["numerical_equality_checked"] is paired["physical_parity"] is False
    assert paired["restart_qualified"] is paired["original_flux_defect_repaired"] is False


def test_report_historical_saved_schema_uses_its_own_producer_bytes(tmp_path):
    value = fixture(tmp_path, version=6)
    result = inspect(value)
    assert result["status"] == "completed_unqualified"
    assert result["verification_issues"] == []


def test_report_prepared_and_missing_terminal_never_imply_a_running_or_completed_job(tmp_path):
    value = fixture(tmp_path)
    assert report.inspect_attempt(value.plan, plan_sha256=value.digest)["status"] == "prepared_only"
    (value.output / "result.json").unlink()
    (value.worker / "demo/outcome.json").unlink()
    result = inspect(value)
    assert result["status"] == "no_terminal_observed"
    assert "demonstration" not in result  # Do not inspect partially written workers.
    assert result["source_execution_complete"] is False


def test_report_explicit_failure_keeps_primary_cause_and_capture_gap(tmp_path):
    value = fixture(tmp_path)
    (value.output / "result.json").unlink()
    primary = dict(
        type="OriginalError", message="", cause=dict(type="ValueError", message="native cause")
    )
    write(value.output / "failure.json", dict(status="failed", primary=primary))
    process = read(value.output / "process/result.json")
    process.update(status="failed", returncode=1)
    write(value.output / "process/failure.json", process)
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row.update(
            status="failed",
            methods_completed=False,
            primary="OriginalError",
            captures=[
                dict(
                    path="capture-9999.json",
                    label="raw.partial",
                    status="capture_failed",
                    error=dict(type="CaptureError"),
                )
            ],
        ),
    )
    result = inspect(value)
    assert result["status"] == "failed" and result["source_execution_complete"] is False
    assert result["failures"][0]["failure"]["primary"] == primary
    assert result["demonstration"]["captures"][0]["status"] == "capture_failed"
    assert result["resources"]["sampled_limits_met"] is True


@pytest.mark.parametrize("field", ["source_files", "original_input_files", "policy", "endpoint"])
def test_report_pair_requires_same_sources_inputs_policy_and_endpoint(tmp_path, field):
    a, b = inspect(fixture(tmp_path)), inspect(fixture(tmp_path, mode="disabled"))
    b[field] = "different saved declaration"
    paired = report.compare_modes(a, b)
    assert paired["matching"][field] is False
    assert paired["paired_execution_complete"] is False


@pytest.mark.parametrize(
    "relative",
    [
        "result.json",
        "worker/result.json",
        "process/result.json",
        "worker/runtime-after.json",
        "worker/source-after.json",
        "worker/filesystem.json",
        "worker/demo/outcome.json",
        "worker/demo/geometry/outcome.json",
        "worker/demo/capture-0000.json",
    ],
)
def test_report_missing_terminal_evidence_never_promotes_success(tmp_path, relative):
    value = fixture(tmp_path)
    (value.output / relative).unlink()
    result = inspect(value)
    assert result["source_execution_complete"] is False
    assert result["status"] != "completed_unqualified"


@pytest.mark.parametrize(
    "mutation",
    [
        "endpoint",
        "stages",
        "operations",
        "capture",
        "primary",
        "steps",
        "flux_repaired",
        "scientific_credit",
        "init_flag",
    ],
)
def test_report_outcome_inconsistencies_refuse_complete_credit(tmp_path, mutation):
    value = fixture(tmp_path)

    def mutate(row):
        if mutation == "endpoint":
            row["endpoint"] = "init_prelude"
        elif mutation == "stages":
            row["completed_stage_trials"].reverse()
        elif mutation == "operations":
            row["operations"].pop()
        elif mutation == "capture":
            row["captures"].pop()
        elif mutation == "primary":
            row["primary"] = "OriginalError"
        elif mutation == "steps":
            row["init_time_steps_completed"] = True
        elif mutation == "flux_repaired":
            row["original_flux_defect_repaired"] = True
        elif mutation == "scientific_credit":
            row["scientific_or_physical_credit"] = 1
        else:
            row["init_setup_completed"] = True

    change(value, "worker/demo/outcome.json", mutate)
    result = inspect(value)
    assert result["status"] == "incomplete_evidence"
    assert any(row["section"] == "outcome" for row in result["verification_issues"])


@pytest.mark.parametrize(
    "mutation",
    ["hash", "mutable_project", "lost_before_module", "cpu", "executable", "source_after"],
)
def test_report_runtime_and_loaded_producers_are_bound(tmp_path, mutation):
    value = fixture(tmp_path)
    path = "worker/runtime-after.json"

    def mutate(row):
        if mutation == "hash":
            next(iter(row["loaded_files"].values()))["sha256"] = "0" * 64
        elif mutation == "mutable_project":
            p = value.base / "runtime/copied.py"
            p.write_text("unchanged-looking project producer")
            row["loaded_files"]["cells.changed"] = pin(p)
        elif mutation == "lost_before_module":
            row["loaded_files"].pop(next(iter(row["loaded_files"])))
        elif mutation == "cpu":
            row["measured_cpu_affinity"] = [1]
        elif mutation == "executable":
            row["executable"]["sha256"] = "0" * 64
        else:
            row["producers"] = {}

    if mutation == "source_after":
        path = "worker/source-after.json"
    change(value, path, mutate)
    result = inspect(value)
    assert result["status"] == "incomplete_evidence"
    assert any(row["section"] == "runtime" for row in result["verification_issues"])


@pytest.mark.parametrize(
    "mutation", ["wall", "rss", "reserve", "process_plan", "filesystem", "conflicting_terminal"]
)
def test_report_resource_and_failure_records_cannot_be_overruled(tmp_path, mutation):
    value = fixture(tmp_path)
    if mutation in ("wall", "rss", "reserve"):
        field, number = {
            "wall": ("elapsed_seconds", 7201),
            "rss": ("sampled_peak_process_tree_rss_bytes", 2**31),
            "reserve": ("minimum_available_host_memory_bytes", 1),
        }[mutation]
        change(value, "process/result.json", lambda row: row.update({field: number}))
        process = read(value.output / "process/result.json")
        change(value, "result.json", lambda row: row.update(process=process))
    elif mutation == "process_plan":
        change(
            value,
            "process/process-inputs.json",
            lambda row: row["command"].__setitem__(
                row["command"].index("--plan-sha256") + 1, "0" * 64
            ),
        )
    elif mutation == "filesystem":
        change(value, "worker/filesystem.json", lambda row: row.update(first_error="write refused"))
    else:
        write(
            value.output / "worker/failure.json",
            dict(status="failed", primary=dict(type="SealFailure")),
        )
    result = inspect(value)
    assert result["status"] != "completed_unqualified"
    assert result["source_evidence_complete"] is False


@pytest.mark.parametrize("mutation", ["plan_digest", "source", "input", "duplicate_json", "schema"])
def test_report_unbound_plan_or_changed_bytes_refuse_before_outcomes(tmp_path, mutation):
    value = fixture(tmp_path)
    if mutation == "plan_digest":
        value.digest = "0" * 64
    elif mutation == "source":
        path = value.source / report.DEMO
        path.chmod(0o644)
        path.write_text("changed snapshot")
    elif mutation == "input":
        (value.base / "config/original.yaml").write_text("changed input")
    elif mutation == "duplicate_json":
        value.plan.write_text('{"kind":1,"kind":2}')
        value.digest = pin(value.plan)["sha256"]
    else:
        row = read(value.plan)
        row["kind"] = "unknown future schema"
        value.digest = write(value.plan, row)["sha256"]
    with pytest.raises(ValueError):
        inspect(value)


def test_report_full_typed_sidecar_bits_checked_without_array_construction(tmp_path):
    value = fixture(tmp_path)
    path = value.worker / "demo/capture-0000.json"
    path.unlink()
    raw = bytes.fromhex("0000000000000080010000000000f87f") * 4096
    report.evidence.write(
        path,
        dict(__ndarray__=True, dtype="<f8", shape=[8192], strides=[8], raw_bytes_hex=raw.hex()),
    )
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row["captures"][0].update(sha256=pin(path)["sha256"]),
    )
    assert inspect(value)["status"] == "completed_unqualified"
    sidecar = next(path.with_name(path.name + ".arrays").glob("*.bin"))
    sidecar.write_bytes(b"x" + raw[1:])
    result = inspect(value)
    assert result["source_evidence_complete"] is False
    assert any(row["section"] == "outcome" for row in result["verification_issues"])


def test_report_cli_exclusively_writes_and_never_overwrites_evidence(tmp_path, monkeypatch):
    value = fixture(tmp_path)
    path = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "report",
            "--plan",
            str(value.plan),
            "--plan-sha256",
            value.digest,
            "--attempt",
            str(value.output),
            "--output",
            str(path),
        ],
    )
    assert report.main() == 0
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        report.main()
    assert path.read_bytes() == original
    assert read(path)["status"] == "completed_unqualified"


def test_report_captured_path_escape_is_refused(tmp_path):
    value = fixture(tmp_path)
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row["captures"][0].update(path="../outside.json"),
    )
    assert inspect(value)["status"] == "incomplete_evidence"


def test_report_two_identical_failures_are_never_a_completed_pair(tmp_path):
    a, b = inspect(fixture(tmp_path)), inspect(fixture(tmp_path, mode="disabled"))
    for value in (a, b):
        value.update(
            status="failed", source_execution_complete=False, source_evidence_complete=False
        )
    assert report.compare_modes(a, b)["paired_execution_complete"] is False


@pytest.mark.parametrize(
    "label",
    [
        "poisson.cache",
        "core.cache",
        "profiles.after",
        "junctions.cache",
        "init_setup.before",
        "init_setup.after",
        "init_prelude.before",
        "init_prelude.after",
        "init_prelude.raw_returns",
    ],
)
def test_report_missing_raw_endpoint_capture_refuses_even_with_all_stage_records(tmp_path, label):
    value = fixture(tmp_path, endpoint="init_prelude")
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row.update(captures=[r for r in row["captures"] if r["label"] != label]),
    )
    result = inspect(value)
    assert result["source_evidence_complete"] is False
    assert any(r["section"] == "outcome" for r in result["verification_issues"])


@pytest.mark.parametrize(
    "label",
    [
        "lattice.record",
        "lattice.before.cache",
        "phase.stage_trials.2.cache.cache",
        "geometry.stage-makeECM",
        "completed_geometry.cache",
        "diagnostics",
    ],
)
def test_report_missing_geometry_record_cache_or_intermediate_refuses(tmp_path, label):
    value = fixture(tmp_path)
    change(
        value,
        "worker/demo/geometry/outcome.json",
        lambda row: row.update(captures=[r for r in row["captures"] if r["label"] != label]),
    )
    result = inspect(value)
    assert result["source_evidence_complete"] is False
    assert any(r["section"] == "geometry" for r in result["verification_issues"])


@pytest.mark.parametrize("name", ["program.json", "bootstrap.json", "writer-review.json"])
@pytest.mark.parametrize("mutation", ["missing", "drift"])
def test_report_all_declared_external_and_program_files_are_authenticated(tmp_path, name, mutation):
    value = fixture(tmp_path)
    path = value.base / name
    if mutation == "missing":
        path.unlink()
    else:
        path.write_text("different bytes")
    with pytest.raises(ValueError):
        inspect(value)


@pytest.mark.parametrize("available", ["process", "demo", "demo_with_damaged_capture"])
def test_report_known_failure_survives_missing_final_publication(tmp_path, available):
    value = fixture(tmp_path)
    (value.output / "result.json").unlink()
    if available == "process":
        (value.worker / "demo/outcome.json").unlink()
        process = read(value.output / "process/result.json")
        process.update(status="failed", returncode=-9)
        write(value.output / "process/failure.json", process)
    else:
        change(
            value,
            "worker/demo/outcome.json",
            lambda row: row.update(
                status="failed", methods_completed=False, primary="OriginalError"
            ),
        )
        if available == "demo_with_damaged_capture":
            (value.worker / "demo/capture-0000.json").write_text("damaged capture")
    result = inspect(value)
    assert result["status"] == "failed"
    assert result["failures"] and result["source_execution_complete"] is False
    assert result["source_evidence_complete"] is False
    if available != "process":
        assert result["failures"][-1]["failure"]["primary"] == "OriginalError"
