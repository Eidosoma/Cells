"""Saved JSON/byte fixtures only; no BETSE source, owner or numerical execution."""

import copy
import hashlib
import json
import os
import struct
import zipfile
from contextlib import contextmanager
from types import FunctionType
from types import SimpleNamespace as NS
from typing import TYPE_CHECKING

import pytest

from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import native_seed_demo_report as report
from validation.betse import native_seed_demo_report_software as software

if TYPE_CHECKING:
    # Freeze the source-only AST fixture without importing its native dependencies.
    from validation.betse import betse_native_parameter_world_ready_qualification  # noqa: F401

_RAW_GUARDS = []


@pytest.mark.parametrize(
    "defect",
    [
        "original",
        "disabled",
        "late_failure",
        "sim_ambient",
        "mode",
        "source",
        "runtime",
        "program",
        "witness",
        "sim_reader_code",
        "sim_launch_code",
        "sim_observation_code",
        "reader_link",
        "legacy_original",
        "legacy_disabled",
    ],
)
def test_report_full_SIM_common_start_comparison_CPU4(tmp_path, monkeypatch, defect):
    from tests.unit import test_native_sim_reference_compare as direct

    direct.full_sim_common_control(tmp_path, monkeypatch, defect)


@pytest.mark.parametrize(
    "defect",
    [
        "original",
        "disabled",
        "ambient",
        "declaration",
        "mode",
        "release",
        "publication",
        "source",
        "order",
        "witness",
        "late_failure",
    ],
)
def test_report_common_start_full_SIM_saved_contract_CPU4(tmp_path, defect):
    from tests.unit import test_native_sim_demo_report as direct

    direct.common_start_control(tmp_path, defect)


def common_saved_fixture(tmp_path, monkeypatch, *, builtin=False):
    from tests.unit.test_native_seed_demo import common_fixture

    value = fixture(tmp_path, version=12)
    if builtin:
        from tests.unit.test_native_seed_rng_report import builtin_fixture

        builtin_fixture(value)
    monkeypatch.setattr(report, "COMMON_SHA256", "d" * 64)
    monkeypatch.setattr(report, "COMMON_REVIEW_SHA256", "e" * 64)
    plan = read(value.plan)
    selected = common_fixture()
    selected["program"]["input_identity"] = plan["initial_rng_inputs"]["inventory_sha256"]
    selected["program_identity"] = report._common_seal(selected["program"])
    selected["provider"].update(
        sha256=report.COMMON_SHA256, review_sha256=report.COMMON_REVIEW_SHA256
    )
    plan["_common_start"] = selected
    plan["_initial_rng_inputs"] = plan["initial_rng_inputs"]
    if builtin:
        plan["_initial_rng_kind"] = "cells.common_initial_rng_observation@2"
    root = value.worker / "demo"
    outcome = read(root / "outcome.json")
    witness_row = next(r for r in outcome["captures"] if r["label"] == "pre_seed_rng_witness")
    witness = read(root / witness_row["path"])
    state = witness["state"]
    record = dict(
        kind=report.COMMON_KIND,
        status="completed",
        program=selected["program"],
        program_identity=selected["program_identity"],
        role="cells",
        pid=123,
        epoch=report.COMMON_EPOCH,
        source=dict(
            helper=report.COMMON_FILE,
            helper_sha256=report.COMMON_SHA256,
            provenance="validation/betse/native_rng_runtime.py",
            provenance_sha256=plan["producers"].get(
                "validation/betse/native_rng_runtime.py", "f" * 64
            ),
        ),
        runtime=witness["common_binding"]["runtime"],
        generator_identities=dict(python=10, numpy=20),
        state={
            kind + "_" + stage: state["python_random" if kind == "python" else "numpy_random"]
            for kind in ("python", "numpy")
            for stage in ("before", "after", "readback")
        },
        operations=[[row[0], "returned"] for row in report.COMMON_STEPS],
        work=dict(
            program_API_calls=8,
            visible_RNG_observer_events=12,
            opaque_C_internals_not_independent_cases=True,
            inherited_observer_RNG_effects_require_reviewed_caller_contract=True,
        ),
        states_loaded=False,
        generators_replaced=False,
        biological_or_phase_admission=False,
    )
    plan["producers"].setdefault("validation/betse/native_rng_runtime.py", "f" * 64)
    completion = root / "common-start-rng/COMPLETED.json"
    completion.parent.mkdir()
    write(completion, record)
    row = dict(write(root / "common-start.json", record), label="common_start_rng", status="saved")
    row["path"] = "common-start.json"
    outcome["captures"].insert(0, row)
    outcome["common_start_program"] = row
    outcome["operations"].insert(3, dict(name="common_start_rng", status="returned"))
    witness["order"]["selected_boundaries"].insert(3, ["common_start_rng", "returned"])
    witness_row["sha256"] = write(root / witness_row["path"], witness)["sha256"]
    outcome["initial_rng_observation"] = dict(witness_row)
    return NS(value=value, plan=plan, outcome=outcome, root=root, record=record, selected=selected)


@pytest.mark.parametrize("builtin", [False, True])
def test_report_common_start_full_return_readback_then_observation_has_no_paired_credit(
    tmp_path, monkeypatch, builtin
):
    model = common_saved_fixture(tmp_path, monkeypatch, builtin=builtin)
    reader = report.Reader()
    captures = report._captures(reader, model.root, model.outcome["captures"])
    result = report._common_captures(reader, model.root, model.plan, model.outcome, captures)
    assert result["completed"] is True
    assert result["common_starting_authority_established"] is False
    assert result["scientific_credit"] == 0
    observation = report._initial_rng_captures(
        reader, model.root, model.plan, model.outcome, captures
    )
    assert observation["observed_states_equalized"] is False
    if builtin:
        from validation.betse import native_seed_rng_report as versioned

        second = versioned.initial_rng_captures(
            reader, model.root, model.plan, model.outcome, captures
        )
        assert second == observation


@pytest.mark.parametrize(
    "drift",
    [
        "publication",
        "readback",
        "draw",
        "role",
        "source",
        "order",
        "ambient",
        "mode",
    ],
)
def test_report_common_start_rejects_resealed_record_or_order_drift(tmp_path, monkeypatch, drift):
    model = common_saved_fixture(tmp_path, monkeypatch)
    if drift == "publication":
        write(model.root / "common-start-rng/COMPLETED.json", {})
    elif drift == "order":
        model.outcome["captures"].reverse()
    elif drift == "ambient":
        del model.plan["_common_start"]
    else:
        if drift == "readback":
            model.record["state"]["python_readback"] = copy.deepcopy(
                model.record["state"]["python_readback"]
            )
            model.record["state"]["python_readback"][1][0] += 1
        elif drift == "draw":
            model.record["program"] = dict(model.record["program"], draws=1)
        elif drift == "mode":
            model.record["program_identity"] = "7" * 64
        elif drift == "role":
            model.record["role"] = "original"
        else:
            model.record["source"]["helper_sha256"] = "7" * 64
        row = model.outcome["captures"][0]
        row["sha256"] = write(model.root / row["path"], model.record)["sha256"]
        write(model.root / "common-start-rng/COMPLETED.json", model.record)
    captures = report._captures(report.Reader(), model.root, model.outcome["captures"])
    with pytest.raises(ValueError):
        report._common_captures(report.Reader(), model.root, model.plan, model.outcome, captures)


def test_report_common_start_failed_program_cannot_gain_geometry_or_observation():
    plan = dict(_common_start={})
    outcome = dict(status="failed", common_start_program=None, captures=[], operations=[])
    result = report._common_captures(None, None, plan, outcome, [])
    assert result == dict(completed=False, common_starting_authority_established=False)
    outcome["operations"].append(dict(name="initial_rng", status="attempted"))
    with pytest.raises(ValueError):
        report._common_captures(None, None, plan, outcome, [])


@pytest.mark.parametrize("drift", ["none", "mode", "caller", "provider", "release", "held"])
def test_report_common_start_plan_requires_explicit_accepted_full_binding(monkeypatch, drift):
    from tests.unit.test_native_seed_demo_launch import common_launch_fixture

    plan, demo, manifest = common_launch_fixture()
    files = {name: row["sha256"] for name, row in manifest["files"].items()}
    monkeypatch.setattr(report, "COMMON_SHA256", "d" * 64)
    monkeypatch.setattr(report, "COMMON_REVIEW_SHA256", "e" * 64)
    files[report.COMMON_FILE] = plan["producers"][report.COMMON_FILE] = "d" * 64
    demo["common_start"]["provider"].update(sha256="d" * 64, review_sha256="e" * 64)
    plan.update(
        flux_operator="original",
        source="/inert/source",
        _initial_rng_inputs=demo["initial_rng_inputs"],
    )
    if drift == "mode":
        plan["flux_operator"] = "disabled"
    elif drift == "caller":
        files[report.COMMON_ORIGINAL] = "f" * 64
    elif drift == "provider":
        files[report.COMMON_FILE] = "f" * 64
    elif drift == "release":
        plan["release_environment"] = {}
    elif drift == "held":
        monkeypatch.setattr(report, "COMMON_REVIEW_SHA256", None)
    reader = NS(bind=lambda row: row)
    if drift == "none":
        assert report._common_declaration(reader, plan, demo, files) is demo["common_start"]
    else:
        with pytest.raises(ValueError):
            report._common_declaration(reader, plan, demo, files)


LEGACY_REPORTER = dict(
    path=(
        "/mnt/workspaces/Cells/native-seed-demo-paired-comparison-20261104-01/"
        "producer-label-repair-01/software-01-affected/source/"
        "validation/betse/native_seed_demo_report.py"
    ),
    sha256="3034f07f3633ce1301a843e1340a41e26b0a2453c7f5721e3b68989b5548a634",
)


def consumer_forbidden_frame(frame):
    return frame.f_globals.get("__name__") in (
        "cells.processes.betse_native_init_terminal",
        "cells.processes.betse_native_init_terminal_molecules",
    ) or software.is_forbidden_frame(frame)


@pytest.mark.parametrize(
    "module",
    (
        "cells.processes.betse_native_init_terminal",
        "cells.processes.betse_native_init_terminal_molecules",
    ),
)
def test_report_init_terminal_native_surface_is_blocked(module):
    for name in ("from_electrical", "prepare", "begin_iteration", "finish_runtime"):
        code = consumer_forbidden_frame.__code__.replace(co_name=name)
        assert consumer_forbidden_frame(NS(f_globals={"__name__": module}, f_code=code))


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit blocked saved-report software release required")
    adapter = NS(
        **dict(
            vars(software),
            reuse=software.base.reuse.reuse,
            is_forbidden_frame=consumer_forbidden_frame,
        )
    )
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


def terminal_calendar_cache(rows):
    """Actual wire schema with explicit synthetic calendar bytes; no NumPy."""
    raw = b"".join(bytes.fromhex(row[1])[::-1] for row in rows)
    layout = dict(
        dtype="<f8", shape=[len(rows)], strides_bytes=[8], C_contiguous=True, F_contiguous=True
    )
    descriptor = json.dumps(
        dict(
            kind="numeric_array",
            source_layout=layout,
            column="column_00000",
            sha256=hashlib.sha256(raw).hexdigest(),
        ),
        sort_keys=True,
        separators=(",", ":"),
    )
    return dict(
        descriptor_json=descriptor,
        identity=hashlib.sha256(descriptor.encode()).hexdigest(),
        all_finite=True,
        columns=[
            dict(
                name="column_00000",
                values=dict(
                    __ndarray__=True,
                    dtype="<f8",
                    shape=[len(rows)],
                    strides=[8],
                    raw_bytes_hex=raw.hex(),
                ),
            )
        ],
    )


def fixture(
    tmp_path,
    mode="original",
    endpoint="seed",
    version=None,
    numpy_origin=False,
    iterations=3,
    import_observation=False,
    parameter_prefix=False,
):
    """A tiny explicitly synthetic snapshot passes the real byte verifier.

    Its files are inert text; these saved records grant no live source authority.
    No verifier, payload reader, runtime check or outcome check is substituted.
    """
    natural = endpoint == "init_terminal"
    if natural:
        import_observation = True
    multiple = endpoint in ("init_short_history", "init_terminal")
    prefix = "init_terminal" if natural else "init_short_history"
    if version is None:
        version = (
            11
            if natural
            else 10
            if endpoint == "init_short_history"
            else 9
            if endpoint == "init_first_step"
            else (8 if endpoint == "init_electrical" or numpy_origin else 7)
        )
    base = tmp_path / mode
    source = base / "prepared/source"
    source.mkdir(parents=True)
    files = {}
    sources = (report.DEMO, report.LAUNCH, report.PARAMETER)
    if version == 12:
        sources += (report.INITIAL_RNG,)
    if numpy_origin:
        sources += (report.NUMPY_ORIGIN,)
    if import_observation:
        sources += (report.MOLECULE_WRAPPER,)
    for name in sources:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            (report.Path(report.__file__).resolve().parents[2] / report.PARAMETER).read_bytes()
            if parameter_prefix and name == report.PARAMETER
            else b"# inert saved-report fixture; never imported\n"
        )
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
            kind=report.DEMO_KINDS[version - 6],
            snapshot_sha256=manifest_pin["sha256"],
            parameter_packet=str(source.parent),
            parameter_sha256=parameters["sha256"],
            flux_operator=mode,
            endpoint=endpoint,
            **({"init_iterations": iterations} if endpoint == "init_short_history" else {}),
            **(
                {
                    "source_plan": {
                        "optional_molecule_import_authority": dict(
                            protocol=report.IMPORT_PROTOCOL,
                            modules={
                                "molecule_wrappers": (
                                    "cells.processes.betse_native_init_molecule_wrapper_authority"
                                )
                            },
                            source_pins={
                                "molecule_wrappers": files[report.MOLECULE_WRAPPER]["sha256"]
                            },
                            review_pins={"molecule_wrappers": "a" * 64},
                        ),
                        **(
                            {
                                "optional_init_terminal": dict(
                                    maximum_iterations=512,
                                    init_iterations=None,
                                    full_original_calendar=True,
                                    normal_loop_context_and_caller_return=True,
                                    selected_stop=False,
                                    before_native_pickle=True,
                                )
                            }
                            if natural
                            else {}
                        ),
                    }
                }
                if import_observation
                else {}
            ),
        ),
    )
    bundle = write(
        base / "input-bundle.json",
        dict(
            modes={mode: dict(config=str(input_file.parent), program=program)},
            source_inventory=dict(files={"original.yaml": dict(sha256=pin(input_file)["sha256"])}),
        ),
    )
    if version == 12:
        bundle_value = read(report.Path(bundle["path"]))
        bundle_value["source_inventory"] = dict(
            directories=[],
            files={
                "original.yaml": dict(
                    size_bytes=input_file.stat().st_size, sha256=pin(input_file)["sha256"]
                )
            },
        )
        bundle = write(report.Path(bundle["path"]), bundle_value)
        declaration = read(report.Path(demo["path"]))
        inventory = bundle_value["source_inventory"]
        declaration["initial_rng_inputs"] = dict(
            profile="original",
            inventory=inventory,
            inventory_sha256=hashlib.sha256(
                json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )
        declaration.setdefault("source_plan", {})["initial_rng_observation"] = dict(
            kind=report.INITIAL_RNG_KIND,
            epoch=report.INITIAL_RNG_EPOCH,
            boundary=report.INITIAL_RNG_BOUNDARY,
            full_numpy_MT_and_python_state=True,
            complete_input_inventory_bound=True,
            reset_draw_or_replacement=False,
            common_starting_authority_established=False,
            producer="validation.betse.native_seed_initial_rng",
            producer_sha256=files[report.INITIAL_RNG]["sha256"],
        )
        demo = write(report.Path(demo["path"]), declaration)
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
        **({"init_iterations": iterations} if endpoint == "init_short_history" else {}),
        **({"initial_rng_inputs": declaration["initial_rng_inputs"]} if version == 12 else {}),
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
    if numpy_origin:
        write(
            worker / "numpy-copy-origin.json",
            dict(
                kind=report.NUMPY_ORIGIN_KIND,
                completed=True,
                hooks_restored=True,
                source_error=None,
                capture_errors=[],
                cleanup_errors=[],
                source_files={
                    str(source / report.NUMPY_ORIGIN): files[report.NUMPY_ORIGIN]["sha256"]
                },
                synthetic_protocol_fixture=True,
            ),
        )
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
    if endpoint in (
        "init_prelude",
        "init_dynamics",
        "init_electrical",
        "init_first_step",
        "init_short_history",
        "init_terminal",
    ):
        stages.append("init_prelude")
    if endpoint in (
        "init_dynamics",
        "init_electrical",
        "init_first_step",
        "init_short_history",
        "init_terminal",
    ):
        stages.append("init_dynamics")
    if endpoint in ("init_electrical", "init_first_step", "init_short_history", "init_terminal"):
        stages.extend(("init_storage", "init_electrical"))
    if endpoint == "init_first_step":
        stages.append("init_first_step")
    if multiple:
        stages.append(prefix)
    first_step_ids = {
        key: str(index) * 64
        for index, key in enumerate(("before", "after", "calendar", "sampled", "t", "dt"), 1)
    }
    first_step_streams = dict(rng_before=["a" * 64, "b" * 64], rng_after=["c" * 64, "d" * 64])
    short_ids = {k: v for k, v in first_step_ids.items() if k != "t"}
    short_rows, short_links = [], []
    for i in range(iterations if multiple else 0):
        after = (
            short_ids["after"]
            if i == iterations - 1
            else hashlib.sha256(str(i).encode()).hexdigest()
        )
        bits = struct.pack("!d", i * 0.00123456789).hex()
        short_rows.append(
            [
                i,
                bits,
                i % 2 == 0,
                after,
                10 + i * 7,
                i + 1,
                1000 + i,
                {"fixture": True, "conservation_assessed": False},
            ]
        )
        short_links.append(
            dict(
                ordinal=i,
                source_time_bits=bits,
                sampled=i % 2 == 0,
                after_identity=after,
                work_end=10 + i * 7,
                callbacks_end=i + 1,
                molecular_record_identity=1000 + i,
            )
        )
    short_record = dict(
        short_ids,
        identity="9" * 64,
        request="e" * 64,
        parent="f" * 64,
        iterations=short_rows,
        work=10 + iterations * 7,
        helpers=iterations * 2,
        callbacks=iterations,
        source_completed=True,
        loop_returned=False,
        selected_stop=True,
        initial_diagnostics={"fixture": True, "conservation_assessed": False},
        **first_step_streams,
    )
    short_linkage = dict(
        request_identity="e" * 64,
        parent_identity="f" * 64,
        trial_identity="9" * 64,
        requested_iterations=iterations,
        operator_mode="original_value_and_flux"
        if mode == "original"
        else "original_value_only_flux_omitted",
        iterations=short_links,
        **first_step_streams,
    )
    if natural:
        short_ids["calendar"] = terminal_calendar_cache(short_rows)["identity"]
        short_record["calendar"] = short_ids["calendar"]
        short_record.update(loop_returned=True, context_returned=True, selected_stop=False)
        short_linkage.pop("requested_iterations")
        short_linkage.update(
            configured_iterations=iterations,
            maximum_iterations=512,
            source_completed=True,
            loop_returned=True,
            context_returned=True,
            selected_stop=False,
            full_original_calendar=True,
            before_native_pickle=True,
        )
    captures = []
    for i, stage in enumerate(stages[1:]):
        path = worker / f"demo/capture-{i:04d}.json"
        value = dict(source_completed=True, recorded_stage=stage, fixture=True)
        if endpoint in ("init_first_step", "init_short_history", "init_terminal"):
            if stage == "init_electrical":
                value["rng_after"] = first_step_streams["rng_before"]
            elif stage == "init_first_step":
                value = dict(
                    first_step_ids,
                    **first_step_streams,
                    complete=True,
                    index=0,
                    loop_returned=False,
                    selected_stop=True,
                )
            elif stage == prefix:
                value = short_record
        write(path, value)
        captures.append(
            dict(
                path=path.name, sha256=pin(path)["sha256"], label=stage + ".record", status="saved"
            )
        )
    raw_labels = ["poisson.cache", "core.cache", "profiles.after", "junctions.cache"]
    if endpoint != "seed":
        raw_labels.extend(("init_setup.before", "init_setup.after"))
    if endpoint in (
        "init_prelude",
        "init_dynamics",
        "init_electrical",
        "init_first_step",
        "init_short_history",
        "init_terminal",
    ):
        raw_labels.extend(("init_prelude.before", "init_prelude.after", "init_prelude.raw_returns"))
    if endpoint in (
        "init_dynamics",
        "init_electrical",
        "init_first_step",
        "init_short_history",
        "init_terminal",
    ):
        raw_labels.extend(
            "init_dynamics." + name
            for name in (
                "before",
                "after",
                "stream_before",
                "stream_after",
                "rng_calls",
                "tissue_record",
                "raw_returns",
            )
        )
    if endpoint in ("init_electrical", "init_first_step", "init_short_history", "init_terminal"):
        for name, streams in (
            ("init_storage", ("stream_before", "stream_after")),
            ("init_electrical", ("rng_before", "rng_after")),
        ):
            raw_labels.extend(
                name + "." + field
                for field in ("before", "after", *streams, "stores", "raw_returns")
            )
    if endpoint == "init_first_step":
        raw_labels.extend(
            "init_first_step." + name
            for name in (
                "before",
                "after",
                "calendar",
                "sampled",
                "source_time_label",
                "configured_dt",
                "stream_before",
                "stream_after",
                "stores",
                "raw_returns",
            )
        )
    if multiple:
        raw_labels.extend(
            prefix + "." + name
            for name in (
                "linkage",
                "before",
                "after",
                "calendar",
                "sampled",
                "configured_dt",
                "stream_before",
                "stream_after",
                "work",
                "helpers",
                "callbacks",
                "raw_returns",
                "initial_diagnostics",
            )
        )
        raw_labels.extend(f"{prefix}.iteration.{i:04d}.after" for i in range(iterations))
    for label in raw_labels:
        path = worker / f"demo/capture-{len(captures):04d}.json"
        value = dict(fixture=True, raw_stage=label, identity=label)
        if label.startswith("init_first_step."):
            name = label.split(".")[1]
            key = {"source_time_label": "t", "configured_dt": "dt"}.get(name, name)
            if key in first_step_ids:
                value["identity"] = first_step_ids[key]
                if key == "t":
                    value["float64_bits"] = "0000000000000000"
                elif key == "dt":
                    value["float64_bits"] = "fca9f1d24d62503f"
            if name in ("stream_before", "stream_after"):
                value = first_step_streams[name.replace("stream_", "rng_")]
        if label.startswith(prefix + "."):
            name = label.removeprefix(prefix + ".")
            key = "dt" if name == "configured_dt" else name
            if key in short_ids:
                value["identity"] = short_ids[key]
            elif name == "linkage":
                value = short_linkage
            elif name in ("stream_before", "stream_after"):
                value = first_step_streams[name.replace("stream_", "rng_")]
            elif name.startswith("iteration."):
                value["identity"] = short_rows[int(name.split(".")[1])][3]
            elif name == "work":
                value = [
                    ["inert-synthetic-body.py", 10, True, True] for _ in range(short_record[name])
                ]
            elif name == "helpers":
                value = [["inert-helper", True, True] for _ in range(short_record[name])]
            elif name == "callbacks":
                value = [["progressed", 1, [0], True, None] for _ in range(short_record[name])]
            if natural and name == "calendar":
                value = terminal_calendar_cache(short_rows)
        write(path, value)
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
        init_prelude_completed=endpoint
        in (
            "init_prelude",
            "init_dynamics",
            "init_electrical",
            "init_first_step",
            "init_short_history",
            "init_terminal",
        ),
        init_dynamics_completed=endpoint
        in (
            "init_dynamics",
            "init_electrical",
            "init_first_step",
            "init_short_history",
            "init_terminal",
        ),
        init_storage_completed=endpoint
        in ("init_electrical", "init_first_step", "init_short_history", "init_terminal"),
        init_electrical_completed=endpoint
        in ("init_electrical", "init_first_step", "init_short_history", "init_terminal"),
        init_first_step_completed=endpoint == "init_first_step",
        init_time_steps_completed=iterations if multiple else int(endpoint == "init_first_step"),
        **(
            {"init_short_history_completed": True, "init_iterations": iterations}
            if endpoint == "init_short_history"
            else {"init_terminal_completed": True, "init_iterations": None}
            if natural
            else {}
        ),
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
        **(
            {"init_iterations": iterations if endpoint == "init_short_history" else None}
            if version == 10
            else {}
        ),
    )
    if numpy_origin:
        terminal.update(numpy_copy_origin_available=True, numpy_copy_origin_completed=True)
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
    value = NS(
        base=base,
        source=source,
        plan=plan_path,
        digest=plan_pin["sha256"],
        output=output,
        worker=worker,
    )
    if version == 12:
        attach_initial_rng(value)
    return attach_molecular_records(value) if natural else value


def inspect(value):
    return report.inspect_attempt(value.plan, plan_sha256=value.digest, output=value.output)


def change(value, relative, function):
    path = value.output / relative
    data = read(path)
    function(data)
    write(path, data)


def change_capture(value, label, function):
    """Retain exact new sidecar hashes for a deliberate saved-evidence mutation."""
    path = value.worker / "demo/outcome.json"
    outcome = read(path)
    row = next(row for row in outcome["captures"] if row["label"] == label)
    capture = value.worker / "demo" / row["path"]
    data = read(capture)
    replacement = function(data)
    write(capture, data if replacement is None else replacement)
    row["sha256"] = pin(capture)["sha256"]
    write(path, outcome)


@pytest.mark.parametrize(
    "endpoint", ("seed", "init_electrical", "init_first_step", "init_short_history")
)
def test_report_init_terminal_preserves_exact_preextension_saved_report(tmp_path, endpoint):
    """Run the pinned historical JSON verifier; preserve its saved report verbatim."""
    value = fixture(tmp_path, endpoint=endpoint)
    path = report.Path(LEGACY_REPORTER["path"])
    assert not path.is_symlink() and report.snapshot.digest(path) == LEGACY_REPORTER["sha256"]
    write(tmp_path / "legacy-reporter-input.json", LEGACY_REPORTER)
    namespace = dict(__name__="tests.private_legacy_seed_report", __file__=str(path))
    # This historical validation module only reads saved evidence. It imports no
    # model and issues no owner; shared evidence/stdlib machinery is deliberate.
    FunctionType(compile(path.read_bytes(), str(path), "exec", dont_inherit=True), namespace)()
    before = namespace["inspect_attempt"](value.plan, plan_sha256=value.digest, output=value.output)
    saved_path = tmp_path / "unchanged-preextension-report.json"
    saved_pin = write(saved_path, before)
    after = inspect(value)
    assert after == before == read(saved_path)
    assert pin(saved_path) == saved_pin
    assert "natural_terminal" not in after["demonstration"]
    write(
        tmp_path / "legacy-report-continuity.json",
        dict(
            endpoint=endpoint,
            historical_source=LEGACY_REPORTER,
            saved_report=saved_pin,
            exact_saved_and_fresh_equality=True,
            old_report_unchanged=True,
            source_native_or_scientific_credit=0,
        ),
    )


@pytest.mark.parametrize("mode", ("original", "disabled"))
@pytest.mark.parametrize("iterations", (1, 3, 500, 512))
def test_report_init_terminal_verifies_complete_calendar_and_normal_context(
    tmp_path, mode, iterations
):
    value = fixture(tmp_path, mode=mode, endpoint="init_terminal", iterations=iterations)
    result = inspect(value)
    assert result["status"] == "completed_unqualified" and not result["verification_issues"]
    assert result["init_iterations_requested"] is None
    assert result["init_iterations_completed"] == iterations and result["time_steps_qualified"] == 0
    terminal = result["demonstration"]["natural_terminal"]
    assert terminal["configured_iterations"] == terminal["recorded_iterations"] == iterations
    assert terminal["maximum_iterations"] == 512
    assert terminal["loop_returned"] is terminal["context_returned"] is True
    assert terminal["selected_stop"] is False
    assert terminal["original_time_bits"] == [
        struct.pack("!d", index * 0.00123456789).hex() for index in range(iterations)
    ]
    assert result["scientific_credit"] == 0 and not result["restart_qualified"]


@pytest.mark.parametrize(
    "field,bad",
    (
        ("loop_returned", False),
        ("context_returned", False),
        ("selected_stop", True),
        ("source_completed", False),
    ),
)
@pytest.mark.parametrize("target", ("record", "linkage"))
def test_report_init_terminal_cannot_promote_selected_or_partial_return(
    tmp_path, field, bad, target
):
    value = fixture(tmp_path, endpoint="init_terminal")
    change_capture(value, "init_terminal." + target, lambda row: row.update({field: bad}))
    result = inspect(value)
    assert result["verification_issues"] and result["init_iterations_completed"] == 0
    assert result["status"] != "completed_unqualified"


@pytest.mark.parametrize("bad", (0, 513, True))
def test_report_init_terminal_configured_count_is_bounded_without_truncation(tmp_path, bad):
    value = fixture(tmp_path, endpoint="init_terminal")
    change(value, "worker/demo/outcome.json", lambda row: row.update(init_time_steps_completed=bad))
    result = inspect(value)
    assert result["verification_issues"] and result["init_iterations_completed"] == 0


@pytest.mark.parametrize(
    "field",
    (
        "record",
        "linkage",
        "calendar",
        "stream_after",
        "initial_diagnostics",
        "iteration.0001.after",
    ),
)
def test_report_init_terminal_requires_each_original_observation(tmp_path, field):
    value = fixture(tmp_path, endpoint="init_terminal")
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row.update(
            captures=[item for item in row["captures"] if item["label"] != "init_terminal." + field]
        ),
    )
    result = inspect(value)
    assert result["verification_issues"] and result["init_iterations_completed"] == 0


def test_report_init_terminal_resealed_iteration_time_still_must_match_actual_calendar(tmp_path):
    value = fixture(tmp_path, endpoint="init_terminal")
    changed = struct.pack("!d", -0.0).hex()

    def record(row):
        row["iterations"][1][1] = changed

    def linkage(row):
        row["iterations"][1]["source_time_bits"] = changed

    change_capture(value, "init_terminal.record", record)
    change_capture(value, "init_terminal.linkage", linkage)
    result = inspect(value)
    assert result["verification_issues"] and result["init_iterations_completed"] == 0
    assert "calendar" in str(result["verification_issues"])


@pytest.mark.parametrize("bad", (64, 513, True))
def test_report_init_terminal_guard_in_linkage_must_be_exact_512(tmp_path, bad):
    value = fixture(tmp_path, endpoint="init_terminal")
    change_capture(value, "init_terminal.linkage", lambda row: row.update(maximum_iterations=bad))
    result = inspect(value)
    assert result["verification_issues"] and result["init_iterations_completed"] == 0


def test_report_init_terminal_invalid_domain_observation_is_retained_without_admission(tmp_path):
    value = fixture(tmp_path, endpoint="init_terminal")

    def invalid(row):
        row["initial_diagnostics"] = dict(
            finite_concentrations=False,
            nonnegative_concentrations=False,
            finite_positive_volumes=False,
            finite_voltage=False,
            physical_or_conservation_admission=False,
        )

    change_capture(value, "init_terminal.record", invalid)
    result = inspect(value)
    assert result["status"] == "completed_unqualified"
    domain = result["demonstration"]["natural_terminal"]["initial_diagnostics"]
    assert domain["finite_positive_volumes"] is False
    assert result["scientific_credit"] == result["time_steps_qualified"] == 0


@pytest.mark.parametrize("mode", ["original", "disabled"])
@pytest.mark.parametrize("natural_return", [False, True])
def test_report_first_step_keeps_original_time_labels_and_separate_execution_credit(
    tmp_path, mode, natural_return
):
    value = fixture(tmp_path, mode=mode, endpoint="init_first_step")
    if natural_return:
        change_capture(
            value,
            "init_first_step.record",
            lambda row: row.update(loop_returned=True, selected_stop=False),
        )
    result = inspect(value)
    assert result["status"] == "completed_unqualified" and result["verification_issues"] == []
    assert result["init_iterations_completed"] == 1 and result["time_steps_qualified"] == 0
    assert result["scientific_credit"] == 0 and result["restart_qualified"] is False
    captures = result["demonstration"]["captures"]
    for name, bits in (
        ("source_time_label", "0000000000000000"),
        ("configured_dt", "fca9f1d24d62503f"),
    ):
        row = next(row for row in captures if row["label"] == "init_first_step." + name)
        assert read(value.worker / "demo" / row["path"])["float64_bits"] == bits
    record = next(row for row in captures if row["label"] == "init_first_step.record")["references"]
    assert record["rng_before"] != record["rng_after"]  # Record actual changes; never reset/rebase.


@pytest.mark.parametrize("version", [8, 9])
def test_report_first_step_extension_preserves_electrical_schema_history(tmp_path, version):
    value = fixture(tmp_path, endpoint="init_electrical", version=version, numpy_origin=True)
    result = inspect(value)
    assert result["status"] == "completed_unqualified" and result["verification_issues"] == []
    assert result["init_iterations_completed"] == result["time_steps_qualified"] == 0


@pytest.mark.parametrize("version", [6, 7, 8])
def test_report_first_step_cannot_relabel_a_prior_plan(tmp_path, version):
    value = fixture(tmp_path, endpoint="init_first_step", version=version)
    with pytest.raises(ValueError, match="plan schemas"):
        inspect(value)


@pytest.mark.parametrize(
    "field",
    [
        "record",
        "before",
        "after",
        "calendar",
        "sampled",
        "source_time_label",
        "configured_dt",
        "stream_before",
        "stream_after",
        "stores",
        "raw_returns",
    ],
)
def test_report_first_step_requires_each_original_capture(tmp_path, field):
    value = fixture(tmp_path, endpoint="init_first_step")
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row.update(
            captures=[c for c in row["captures"] if c["label"] != "init_first_step." + field]
        ),
    )
    result = inspect(value)
    assert result["status"] == "incomplete_evidence" and result["verification_issues"]
    assert result["init_iterations_completed"] == 0 and result["source_execution_complete"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "count_zero",
        "count_two",
        "count_bool",
        "flag",
        "old_schema",
        "incomplete",
        "index_one",
        "index_bool",
        "both_stops",
        "no_stop",
        "stage_order",
        "operation",
    ],
)
def test_report_first_step_refuses_incomplete_or_extra_iteration_claims(tmp_path, mutation):
    value = fixture(tmp_path, endpoint="init_first_step")
    changes = {
        "incomplete": {"complete": False},
        "index_one": {"index": 1},
        "index_bool": {"index": False},
        "both_stops": {"loop_returned": True},
        "no_stop": {"selected_stop": False},
    }
    if mutation in changes:
        change_capture(value, "init_first_step.record", lambda row: row.update(changes[mutation]))
    else:

        def alter(row):
            if mutation.startswith("count_"):
                row["init_time_steps_completed"] = {
                    "count_zero": 0,
                    "count_two": 2,
                    "count_bool": True,
                }[mutation]
            elif mutation == "flag":
                row["init_first_step_completed"] = False
            elif mutation == "old_schema":
                row["kind"] = report.DEMO_KINDS[2]
            elif mutation == "stage_order":
                row["completed_stage_trials"][-2:] = reversed(row["completed_stage_trials"][-2:])
            else:
                row["operations"][-1]["status"] = "attempted"

        change(value, "worker/demo/outcome.json", alter)
    result = inspect(value)
    assert result["status"] == "incomplete_evidence" and result["verification_issues"]
    assert result["init_iterations_completed"] == 0


@pytest.mark.parametrize("field", ["before", "after", "calendar", "sampled", "t", "dt"])
def test_report_first_step_refuses_retargeted_calendar_time_or_state(tmp_path, field):
    value = fixture(tmp_path, endpoint="init_first_step")
    change_capture(value, "init_first_step.record", lambda row: row.update({field: "e" * 64}))
    result = inspect(value)
    assert result["status"] == "incomplete_evidence" and result["verification_issues"]
    assert result["init_iterations_completed"] == 0


@pytest.mark.parametrize("mutation", ["before", "after", "short", "parent"])
def test_report_first_step_preserves_two_streams_and_the_electrical_handoff(tmp_path, mutation):
    value = fixture(tmp_path, endpoint="init_first_step")
    if mutation == "parent":
        change_capture(
            value, "init_electrical.record", lambda row: row.update(rng_after=["e" * 64, "f" * 64])
        )
    elif mutation == "short":
        change_capture(
            value, "init_first_step.record", lambda row: row.update(rng_before=["a" * 64])
        )
    else:
        change_capture(
            value, "init_first_step.stream_" + mutation, lambda row: ["e" * 64, "f" * 64]
        )
    result = inspect(value)
    assert result["status"] == "incomplete_evidence" and result["verification_issues"]
    assert result["init_iterations_completed"] == 0


@pytest.mark.parametrize("promote", [False, True])
def test_report_first_step_failure_retains_partial_trial_without_execution_promotion(
    tmp_path, promote
):
    value = fixture(tmp_path, endpoint="init_first_step")
    primary = dict(type="OriginalSourceError", message="retained", cause="original cause")
    (value.output / "result.json").unlink()
    write(value.output / "failure.json", dict(error=primary))
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row.update(
            status="failed",
            primary=primary,
            methods_completed=False,
            init_first_step_completed=promote,
            init_time_steps_completed=int(promote),
        ),
    )
    result = inspect(value)
    assert result["status"] == "failed" and result["init_iterations_completed"] == 0
    assert result["failures"][-1]["failure"]["primary"] == primary
    assert bool(result["verification_issues"]) is promote
    if not promote:
        record = next(
            row
            for row in result["demonstration"]["captures"]
            if row["label"] == "init_first_step.record"
        )
        assert (
            record["references"]["complete"] is True
        )  # Raw body evidence is not a successful endpoint.


@pytest.mark.parametrize("mode", ["original", "disabled"])
def test_report_numpy_origin_preserves_declared_bootstrap_and_historical_scope(tmp_path, mode):
    value = fixture(tmp_path, mode=mode, numpy_origin=True)
    result = inspect(value)
    assert result["status"] == "completed_unqualified" and result["verification_issues"] == []
    assert result["numpy_copy_origin"]["completed"] is True
    assert result["scientific_credit"] == 0 and result["original_flux_defect_repaired"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "kind",
        "completed",
        "hooks",
        "source",
        "capture",
        "cleanup",
        "files",
        "hash",
        "relative",
        "available_flag",
        "completed_flag",
    ],
)
def test_report_numpy_origin_refuses_incomplete_or_inconsistent_completion(tmp_path, mutation):
    value = fixture(tmp_path, numpy_origin=True)
    relative = "worker/numpy-copy-origin.json"
    if mutation == "missing":
        (value.output / relative).unlink()
    elif mutation.endswith("_flag"):
        key = "numpy_copy_origin_" + mutation.removesuffix("_flag")
        change(value, "worker/result.json", lambda row: row.update({key: False}))
        change(
            value, "result.json", lambda row: row.update(worker=pin(value.worker / "result.json"))
        )
    else:

        def alter(row):
            key, replacement = {
                "kind": ("kind", "foreign"),
                "completed": ("completed", False),
                "hooks": ("hooks_restored", False),
                "source": ("source_error", False),
                "capture": ("capture_errors", ["capture failed"]),
                "cleanup": ("cleanup_errors", ["cleanup failed"]),
                "files": ("source_files", {}),
                "hash": ("source_files", {str(value.source / report.NUMPY_ORIGIN): "0" * 64}),
                "relative": ("source_files", {"relative.py": "0" * 64}),
            }[mutation]
            row[key] = replacement

        change(value, relative, alter)
    result = inspect(value)
    assert result["status"] != "completed_unqualified" and result["verification_issues"]
    assert result["source_execution_complete"] is False


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


@pytest.mark.parametrize("name", ["init_storage", "init_electrical"])
@pytest.mark.parametrize(
    "field",
    ["record", "before", "after", "streams_before", "streams_after", "stores", "raw_returns"],
)
def test_report_init_electrical_requires_each_stage_capture(tmp_path, name, field):
    value = fixture(tmp_path, endpoint="init_electrical")
    if field.startswith("streams_"):
        field = ("stream_" if name == "init_storage" else "rng_") + field.removeprefix("streams_")
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row.update(
            captures=[
                capture for capture in row["captures"] if capture["label"] != name + "." + field
            ]
        ),
    )
    result = inspect(value)
    assert result["status"] != "completed_unqualified" and result["verification_issues"]


@pytest.mark.parametrize(
    "mutation",
    [
        "storage_flag",
        "electrical_flag",
        "stage_order",
        "operations",
        "old_outcome",
        "time_step",
        "flux_repair",
    ],
)
def test_report_init_electrical_refuses_incomplete_or_promoted_success(tmp_path, mutation):
    value = fixture(tmp_path, endpoint="init_electrical")

    def alter(row):
        if mutation == "storage_flag":
            row["init_storage_completed"] = False
        elif mutation == "electrical_flag":
            row["init_electrical_completed"] = False
        elif mutation == "stage_order":
            row["completed_stage_trials"][-2:] = reversed(row["completed_stage_trials"][-2:])
        elif mutation == "operations":
            row["operations"][-1]["status"] = "attempted"
        elif mutation == "old_outcome":
            row["kind"] = report.DEMO_KINDS[1]
        elif mutation == "time_step":
            row["init_time_steps_completed"] = 1
        else:
            row["original_flux_defect_repaired"] = True

    change(value, "worker/demo/outcome.json", alter)
    result = inspect(value)
    assert result["status"] != "completed_unqualified" and result["verification_issues"]


def test_report_init_electrical_does_not_relabel_old_plan_schema(tmp_path):
    value = fixture(tmp_path, endpoint="init_electrical", version=7)
    with pytest.raises(ValueError, match="plan schemas"):
        inspect(value)


@pytest.mark.parametrize(
    "label",
    [
        "record",
        "before",
        "after",
        "stream_before",
        "stream_after",
        "rng_calls",
        "tissue_record",
        "raw_returns",
    ],
)
def test_report_init_dynamics_requires_every_completed_capture(tmp_path, label):
    value = fixture(tmp_path, endpoint="init_dynamics")

    def remove(row):
        row["captures"] = [c for c in row["captures"] if c["label"] != "init_dynamics." + label]

    change(value, "worker/demo/outcome.json", remove)
    result = inspect(value)
    assert result["status"] == "incomplete_evidence" and not result["source_execution_complete"]
    assert any(row["section"] == "outcome" for row in result["verification_issues"])


@pytest.mark.parametrize(
    "mutation",
    ["completion_flag", "prelude_flag", "tissue_bytes", "rng_bytes", "operation", "steps"],
)
def test_report_init_dynamics_cannot_claim_completion_with_damaged_evidence(tmp_path, mutation):
    value = fixture(tmp_path, endpoint="init_dynamics")
    if mutation in ("tissue_bytes", "rng_bytes"):
        label = "tissue_record" if mutation == "tissue_bytes" else "rng_calls"
        outcome = read(value.worker / "demo/outcome.json")
        captured = next(c for c in outcome["captures"] if c["label"] == "init_dynamics." + label)
        (value.worker / "demo" / captured["path"]).write_text("changed exact capture")
    else:

        def mutate(row):
            if mutation == "completion_flag":
                row["init_dynamics_completed"] = False
            elif mutation == "prelude_flag":
                row["init_prelude_completed"] = False
            elif mutation == "operation":
                row["operations"][-1]["status"] = "failed"
            else:
                row["init_time_steps_completed"] = 1

        change(value, "worker/demo/outcome.json", mutate)
    result = inspect(value)
    assert result["status"] == "incomplete_evidence" and not result["source_execution_complete"]


@pytest.mark.parametrize("placement", ["correct", "early", "late", "seed"])
def test_report_init_dynamics_file_work_requires_correct_endpoint_and_order(tmp_path, placement):
    value = fixture(tmp_path, endpoint="seed" if placement == "seed" else "init_dynamics")

    def mutate(row):
        entries = row["operations"]
        index = (
            len(entries) - 2
            if placement == "correct"
            else (0 if placement == "early" else len(entries))
        )
        entries.insert(index, dict(name="init_dynamics_file", status="returned"))

    change(value, "worker/demo/outcome.json", mutate)
    result = inspect(value)
    assert result["source_execution_complete"] is (placement == "correct")
    assert result["status"] == (
        "completed_unqualified" if placement == "correct" else "incomplete_evidence"
    )


def test_report_init_dynamics_failure_keeps_completed_prelude_and_original_cause(tmp_path):
    value = fixture(tmp_path, endpoint="init_dynamics")
    (value.output / "result.json").unlink()
    primary = dict(
        type="DynamicsRejected", message="", cause=dict(type="NativeError", message="source")
    )
    write(value.output / "failure.json", dict(status="failed", primary=primary))
    process = read(value.output / "process/result.json")
    process.update(status="failed", returncode=1)
    write(value.output / "process/failure.json", process)

    def fail(row):
        row.update(
            status="failed",
            methods_completed=False,
            primary="DynamicsRejected",
            init_dynamics_completed=False,
        )
        row["completed_stage_trials"].pop()
        row["operations"][-1]["status"] = "failed"
        row["captures"] = [
            c for c in row["captures"] if not c["label"].startswith("init_dynamics.")
        ]

    change(value, "worker/demo/outcome.json", fail)
    result = inspect(value)
    assert result["status"] == "failed" and result["failures"][0]["failure"]["primary"] == primary
    retained = result["demonstration"]["outcome"]
    assert (
        retained["init_prelude_completed"] is True and retained["init_dynamics_completed"] is False
    )
    assert retained["completed_stage_trials"][-1] == "init_prelude"
    assert not result["source_execution_complete"] and result["time_steps_qualified"] == 0


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
    "field", ["configuration_profile", "selected_input_files", "configuration_changes"]
)
def test_report_headless_pair_requires_same_explicit_configuration_and_selected_bytes(
    tmp_path, field
):
    from validation.betse import native_seed_demo_input_profiles as profiles

    a, b = inspect(fixture(tmp_path)), inspect(fixture(tmp_path, mode="disabled"))
    for result in (a, b):
        result.update(
            configuration_profile="headless",
            configuration_changes=profiles.changes(),
            selected_input_files={profiles.MAIN: profiles.HEADLESS_SHA256},
        )
    assert report.compare_modes(a, b)["paired_execution_complete"] is True
    b[field] = "different saved input variant"
    paired = report.compare_modes(a, b)
    assert paired["matching"][field] is False
    assert paired["paired_execution_complete"] is False


def test_report_headless_saved_plan_retains_original_provenance_and_selected_main(tmp_path):
    from pathlib import Path

    from validation.betse import native_seed_demo_input_profiles as profiles

    value = fixture(tmp_path)
    plan = read(value.plan)
    bundle = read(Path(plan["input_bundle"]["path"]))
    selected = bundle["modes"]["original"]
    config = Path(selected["config"])
    raw = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse/data/yaml/sim_config.yaml").read_bytes()
    (config / profiles.MAIN).write_bytes(profiles.transform(raw))
    bundle["source_inventory"]["files"][profiles.MAIN] = dict(
        sha256=profiles.ORIGINAL_SHA256, size_bytes=len(raw)
    )
    bundle.update(
        input_inventory=profiles.inventory(bundle["source_inventory"], "headless"),
        configuration_profile="headless",
        configuration_changes=profiles.changes(),
        raw_configuration_and_images_unchanged=False,
    )
    selected["program"] = write(
        value.base / "headless-program.json", dict(input_profile="headless")
    )
    parameters = read(Path(plan["parameter_inputs"]["path"]))
    parameters["program"].update(input_profile="headless", manifest=selected["program"])
    plan["parameter_inputs"] = write(Path(plan["parameter_inputs"]["path"]), parameters)
    demo = read(Path(plan["demo_plan"]["path"]))
    demo["parameter_sha256"] = plan["parameter_inputs"]["sha256"]
    plan["demo_plan"] = write(Path(plan["demo_plan"]["path"]), demo)
    plan["input_bundle"] = write(Path(plan["input_bundle"]["path"]), bundle)
    plan["input_files"] = [
        dict(path=str(config / name), sha256=row["sha256"])
        for name, row in sorted(bundle["input_inventory"]["files"].items())
    ]
    value.digest = write(value.plan, plan)["sha256"]
    result = report.inspect_attempt(value.plan, plan_sha256=value.digest)
    assert result["status"] == "prepared_only"
    assert result["configuration_profile"] == "headless"
    assert result["original_input_files"][profiles.MAIN] == profiles.ORIGINAL_SHA256
    assert result["selected_input_files"][profiles.MAIN] == profiles.HEADLESS_SHA256
    assert result["configuration_changes"] == profiles.changes()
    assert result["scientific_credit"] == 0


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


def molecule_fixture(tmp_path, *, mode="original", endpoint="init_dynamics"):
    """Inert saved records exercise the reader, without issuing molecular authority."""
    value = fixture(tmp_path, mode=mode, endpoint=endpoint, import_observation=True)
    return value if endpoint == "init_terminal" else attach_molecular_records(value)


def attach_molecular_records(value):
    """Shared inert saved records, never an actual session/claim or source callback."""
    change_capture(
        value,
        "init_dynamics.record",
        lambda row: row.update(
            molecule_record=101,
            tissue_record=201,
            tail_source_completed=True,
            timesteps_completed=0,
            completed_INIT_or_independent_case=False,
        ),
    )
    change_capture(
        value,
        "init_dynamics.tissue_record",
        lambda row: dict(
            record_identity=201,
            completion_claim_identity=301,
            init_trial_identity="d" * 64,
            calls=["init_profiles", "init_events"],
            source_completed=True,
            work_views_are_non_additive=True,
            live_claim_or_frame_serialization=False,
        ),
    )
    metadata = dict(
        identity="e" * 64,
        record_identity=101,
        completion_claim_identity=301,
        molecules_identity=401,
        core_identity=501,
        source_completed=True,
        constructors=[["Molecules", 401, 601], ["MasterOfMolecules", 501, 602]],
        source_work=[["inert/original.py", 10, 603, True]],
        dynamic_callbacks=[[701, 702, 703, 604]],
        work_views_are_non_additive=True,
        live_claim_or_frame_serialization=False,
        import_record_identity=801,
    )
    outcome = read(value.worker / "demo/outcome.json")
    for name, raw in (
        ("molecule_record", metadata),
        ("molecule_raw_returns", [None, {"retained": [0, 1, 2]}]),
    ):
        path = value.worker / "demo" / (name + ".json")
        write(path, raw)
        outcome["captures"].append(
            dict(
                label="init_dynamics." + name,
                path=path.name,
                sha256=pin(path)["sha256"],
                status="saved",
            )
        )
    outcome.update(init_native_molecules=True, init_molecule_network_completed=True)
    write(value.worker / "demo/outcome.json", outcome)
    attach_import_capture(value)
    return value


def attach_import_capture(value):
    outcome = read(value.worker / "demo/outcome.json")
    plan = read(value.plan)
    source = report.Path(plan["source"])
    record = dict(
        protocol=report.IMPORT_PROTOCOL,
        law="fresh_original_molecule_channel_imported_beartype_factory@1",
        context_identity=800,
        record_identity=801,
        producer_sha256=pin(source / report.MOLECULE_WRAPPER)["sha256"],
        source_completed=True,
        published=True,
        active=False,
        hooks_restored=True,
        monitor_restored=True,
        factories=1,
        generated=1,
        raw_returns=1,
        source_errors=0,
        work_views_are_non_additive=True,
        live_claim_or_frame_serialization=False,
    )
    for name, raw in (("record", record), ("raw_returns", [{"synthetic_raw_identity": 802}])):
        path = value.worker / "demo" / ("imports-" + name + ".json")
        write(path, raw)
        outcome["captures"].append(
            dict(
                label="molecule_imports." + name,
                path=path.name,
                sha256=pin(path)["sha256"],
                status="saved",
            )
        )
    outcome.update(
        molecule_import_protocol=report.IMPORT_PROTOCOL,
        molecule_import_completed=True,
        molecule_import_record_identity=801,
        molecule_import_operations=[
            dict(name="enter", status="returned"),
            dict(name="exit", status="returned"),
        ],
    )
    write(value.worker / "demo/outcome.json", outcome)


def test_report_import_closed_record_is_required_and_linked_to_enabled_network(tmp_path):
    value = molecule_fixture(tmp_path)
    result = inspect(value)
    assert result["status"] == "completed_unqualified"
    imported = result["demonstration"]["molecule_imports"]
    assert imported["declared"] and imported["completed"]
    assert imported["record"]["record_identity"] == 801
    assert result["scientific_credit"] == 0


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "active", "unpublished", "record_link", "producer", "work", "flag"],
)
def test_report_import_incomplete_or_resealed_wrong_link_never_promotes(mutation, tmp_path):
    value = molecule_fixture(tmp_path)
    if mutation in ("missing", "duplicate", "flag"):

        def mutate(row):
            if mutation == "flag":
                row["molecule_import_completed"] = 1
            elif mutation == "missing":
                row["captures"] = [
                    x for x in row["captures"] if x["label"] != "molecule_imports.record"
                ]
            else:
                row["captures"].append(
                    next(x for x in row["captures"] if x["label"] == "molecule_imports.record")
                )

        change(value, "worker/demo/outcome.json", mutate)
    elif mutation == "record_link":
        change_capture(
            value,
            "init_dynamics.molecule_record",
            lambda row: row.update(import_record_identity=999),
        )
    else:
        key, changed = {
            "active": ("active", True),
            "unpublished": ("published", False),
            "producer": ("producer_sha256", "f" * 64),
            "work": ("raw_returns", 2),
        }[mutation]
        change_capture(value, "molecule_imports.record", lambda row: row.update({key: changed}))
    result = inspect(value)
    assert result["status"] == "incomplete_evidence"
    assert result["source_execution_complete"] is False
    assert result["verification_issues"]


def test_report_import_legacy_enabled_claim_without_record_is_not_promoted(tmp_path):
    value = molecule_fixture(tmp_path)
    assert inspect(value)["status"] == "completed_unqualified"
    plan = read(value.plan)
    declaration = read(report.Path(plan["demo_plan"]["path"]))
    declaration.pop("source_plan")
    plan["demo_plan"] = write(report.Path(plan["demo_plan"]["path"]), declaration)
    value.digest = write(value.plan, plan)["sha256"]
    worker = read(value.worker / "result.json")
    worker["plan_sha256"] = value.digest
    worker_pin = write(value.worker / "result.json", worker)
    terminal = read(value.output / "result.json")
    terminal.update(plan_sha256=value.digest, worker=worker_pin)
    write(value.output / "result.json", terminal)

    def old(row):
        for name in (
            "molecule_import_protocol",
            "molecule_import_completed",
            "molecule_import_record_identity",
            "molecule_import_operations",
        ):
            row.pop(name)
        row["captures"] = [
            x for x in row["captures"] if not x["label"].startswith("molecule_imports.")
        ]

    change(value, "worker/demo/outcome.json", old)
    result = inspect(value)
    assert result["status"] == "incomplete_evidence"
    assert any(
        "required import evidence" in row["message"] for row in result["verification_issues"]
    )


def test_report_import_successful_prefix_does_not_promote_later_source_failure(tmp_path):
    value = molecule_fixture(tmp_path)

    def failed(row):
        row.update(status="failed", primary="OriginalSourceError", methods_completed=False)

    change(value, "worker/demo/outcome.json", failed)
    result = inspect(value)
    assert result["status"] == "failed"
    assert result["demonstration"]["molecule_imports"]["completed"] is True
    assert result["source_execution_complete"] is False and result["scientific_credit"] == 0


def molecule_refusal(value, message):
    result = inspect(value)
    assert result["status"] == "incomplete_evidence"
    assert result["source_execution_complete"] is False
    assert result["source_evidence_complete"] is False
    assert result["init_molecule_network_completed"] is False
    assert any(
        issue["section"] == "outcome" and message in issue["message"]
        for issue in result["verification_issues"]
    )


@pytest.mark.parametrize("mode", ["original", "disabled"])
@pytest.mark.parametrize("endpoint", ["init_dynamics", "init_electrical", "init_first_step"])
def test_report_molecule_completed_linkage_preserves_endpoint_scope(tmp_path, mode, endpoint):
    value = molecule_fixture(tmp_path, mode=mode, endpoint=endpoint)
    result = inspect(value)
    assert result["status"] == "completed_unqualified"
    assert result["verification_issues"] == []
    assert result["init_native_molecules"] is True
    assert result["init_molecule_network_completed"] is True
    assert result["demonstration"]["molecule_network"] == dict(
        selected=True, completed=True, identity="e" * 64
    )
    assert result["init_iterations_completed"] == int(endpoint == "init_first_step")
    assert result["scientific_credit"] == result["time_steps_qualified"] == 0
    assert result["restart_qualified"] is False
    rows = {row["label"]: row for row in result["demonstration"]["captures"]}
    for label in ("molecule_record", "molecule_raw_returns"):
        path = value.worker / "demo" / (label + ".json")
        assert pin(path) in result["observed_file_pins"]
    # The full work and return data stay in their authenticated capture files.
    metadata = rows["init_dynamics.molecule_record"]["references"]
    assert metadata["completion_claim_identity"] == 301
    assert "source_work" not in metadata and "constructors" not in metadata
    assert "dynamic_callbacks" not in metadata


@pytest.mark.parametrize(
    "version,endpoint",
    [(6, "seed"), (7, "init_dynamics"), (8, "init_electrical"), (9, "init_first_step")],
)
def test_report_molecule_missing_optional_fields_preserves_all_historical_schemas(
    tmp_path, version, endpoint
):
    value = fixture(tmp_path, version=version, endpoint=endpoint)
    result = inspect(value)
    assert result["status"] == "completed_unqualified"
    assert result["verification_issues"] == []
    assert result["init_native_molecules"] is None
    assert result["init_molecule_network_completed"] is False
    assert result["init_iterations_completed"] == int(endpoint == "init_first_step")


@pytest.mark.parametrize(
    "endpoint,selected", [("seed", None), ("init_dynamics", False), ("init_first_step", False)]
)
def test_report_molecule_explicit_unselected_or_disabled_has_no_network_credit(
    tmp_path, endpoint, selected
):
    value = fixture(tmp_path, endpoint=endpoint)
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row.update(
            init_native_molecules=selected, init_molecule_network_completed=False
        ),
    )
    result = inspect(value)
    assert result["status"] == "completed_unqualified"
    assert result["init_native_molecules"] is selected
    assert result["demonstration"]["molecule_network"] == dict(
        selected=selected, completed=False, identity=None
    )


@pytest.mark.parametrize("label", ["molecule_record", "molecule_raw_returns"])
@pytest.mark.parametrize("mutation", ["missing", "failed", "duplicate", "changed_bytes"])
def test_report_molecule_completion_requires_both_exact_saved_captures(tmp_path, label, mutation):
    value = molecule_fixture(tmp_path)
    assert inspect(value)["source_evidence_complete"] is True
    path = value.worker / "demo/outcome.json"
    outcome = read(path)
    row = next(r for r in outcome["captures"] if r["label"] == "init_dynamics." + label)
    if mutation == "missing":
        outcome["captures"].remove(row)
    elif mutation == "failed":
        row.update(status="capture_failed", error=dict(type="ObservationFailure"))
    elif mutation == "duplicate":
        duplicate = value.worker / "demo" / (label + "-duplicate.json")
        duplicate.write_bytes((value.worker / "demo" / row["path"]).read_bytes())
        outcome["captures"].append(dict(row, path=duplicate.name, sha256=pin(duplicate)["sha256"]))
    else:
        (value.worker / "demo" / row["path"]).write_text("changed retained bytes")
    write(path, outcome)
    molecule_refusal(value, "" if mutation == "changed_bytes" else "required raw capture")


@pytest.mark.parametrize(
    "label,key,replacement,message",
    [
        ("molecule_record", "identity", "g" * 64, "hash identity"),
        ("molecule_record", "identity", "e" * 63, "hash identity"),
        ("molecule_record", "identity", 1, "hash identity"),
        ("molecule_record", "source_completed", False, "non-additive metadata"),
        ("molecule_record", "work_views_are_non_additive", False, "non-additive metadata"),
        ("molecule_record", "live_claim_or_frame_serialization", True, "non-additive metadata"),
        ("tissue_record", "source_completed", False, "non-additive metadata"),
        ("tissue_record", "work_views_are_non_additive", 1, "non-additive metadata"),
        ("tissue_record", "live_claim_or_frame_serialization", None, "non-additive metadata"),
        ("molecule_record", "completion_claim_identity", 302, "completion claims differ"),
        ("molecule_record", "record_identity", 102, "trial molecular/tissue linkage"),
        ("tissue_record", "record_identity", 202, "trial molecular/tissue linkage"),
        ("molecule_record", "molecules_identity", True, "original molecular object identity"),
        ("molecule_record", "core_identity", 0, "original molecular object identity"),
        ("record", "molecule_record", 102, "trial molecular/tissue linkage"),
        ("record", "tissue_record", 202, "trial molecular/tissue linkage"),
        ("record", "tail_source_completed", 1, "trial molecular/tissue linkage"),
        ("record", "timesteps_completed", False, "trial molecular/tissue linkage"),
        ("record", "completed_INIT_or_independent_case", True, "trial molecular/tissue linkage"),
    ],
)
def test_report_molecule_resealed_metadata_cannot_change_original_linkage_or_scope(
    tmp_path, label, key, replacement, message
):
    value = molecule_fixture(tmp_path)
    change_capture(value, "init_dynamics." + label, lambda row: row.update({key: replacement}))
    molecule_refusal(value, message)


@pytest.mark.parametrize("key", ["record_identity", "completion_claim_identity"])
def test_report_molecule_boolean_identity_cannot_alias_exact_integer_identity(tmp_path, key):
    value = molecule_fixture(tmp_path)
    change_capture(value, "init_dynamics.molecule_record", lambda row: row.update({key: True}))
    if key == "record_identity":
        change_capture(value, "init_dynamics.record", lambda row: row.update(molecule_record=1))
    else:
        change_capture(value, "init_dynamics.tissue_record", lambda row: row.update({key: 1}))
    molecule_refusal(value, "Exact saved object identity")


@pytest.mark.parametrize("selection", ["missing", None, False])
def test_report_molecule_captures_require_explicit_enabled_selection(tmp_path, selection):
    value = molecule_fixture(tmp_path)

    def mutate(row):
        if selection == "missing":
            row.pop("init_native_molecules")
            row.pop("init_molecule_network_completed")
        else:
            row.update(init_native_molecules=selection, init_molecule_network_completed=False)

    change(value, "worker/demo/outcome.json", mutate)
    molecule_refusal(value, "without explicit enabled selection")


@pytest.mark.parametrize(
    "mutation,message",
    [
        ("selection_integer", "Exact optional molecular"),
        ("completion_integer", "Exact optional molecular"),
        ("missing_selection", "Both optional molecular"),
        ("missing_completion", "Both optional molecular"),
        ("not_completed", "flags disagree"),
        ("not_dynamics", "completed INIT dynamics"),
        ("missing_stage", "completed INIT dynamics"),
    ],
)
def test_report_molecule_flags_and_completed_stage_are_exact(tmp_path, mutation, message):
    value = molecule_fixture(tmp_path)

    def mutate(row):
        if mutation == "selection_integer":
            row["init_native_molecules"] = 1
        elif mutation == "completion_integer":
            row["init_molecule_network_completed"] = 1
        elif mutation.startswith("missing_") and mutation != "missing_stage":
            row.pop(
                "init_native_molecules"
                if mutation == "missing_selection"
                else "init_molecule_network_completed"
            )
        elif mutation == "not_completed":
            row["init_molecule_network_completed"] = False
        elif mutation == "not_dynamics":
            row["init_dynamics_completed"] = False
        else:
            row["completed_stage_trials"].remove("init_dynamics")

    change(value, "worker/demo/outcome.json", mutate)
    molecule_refusal(value, message)


@pytest.mark.parametrize("endpoint,selected", [("seed", True), ("init_dynamics", None)])
def test_report_molecule_selection_respects_reached_endpoint(tmp_path, endpoint, selected):
    value = fixture(tmp_path, endpoint=endpoint)
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row.update(
            init_native_molecules=selected, init_molecule_network_completed=False
        ),
    )
    molecule_refusal(
        value, "before its endpoint" if endpoint == "seed" else "requires its molecular selection"
    )


def test_report_molecule_completed_stage_survives_later_failure_without_endpoint_credit(tmp_path):
    value = molecule_fixture(tmp_path, endpoint="init_electrical")
    (value.output / "result.json").unlink()
    primary = dict(type="OriginalElectricalError", message="", cause=dict(type="Cause", message=""))
    write(value.output / "failure.json", dict(status="failed", primary=primary))

    def fail(row):
        row.update(
            status="failed",
            methods_completed=False,
            primary=primary,
            init_electrical_completed=False,
        )
        row["completed_stage_trials"].remove("init_electrical")
        row["operations"][-1]["status"] = "failed"
        row["captures"] = [
            c for c in row["captures"] if not c["label"].startswith("init_electrical.")
        ]

    change(value, "worker/demo/outcome.json", fail)
    result = inspect(value)
    assert result["status"] == "failed"
    assert result["demonstration"]["molecule_network"] == dict(
        selected=True, completed=True, identity="e" * 64
    )
    assert result["init_molecule_network_completed"] is True
    assert result["failures"][0]["failure"]["primary"] == primary
    assert result["source_execution_complete"] is False
    assert result["source_evidence_complete"] is False
    assert result["init_iterations_completed"] == result["time_steps_qualified"] == 0
    assert result["scientific_credit"] == 0 and result["restart_qualified"] is False


def test_report_molecule_failed_raw_observation_does_not_promote_completed_record(tmp_path):
    value = molecule_fixture(tmp_path)
    (value.output / "result.json").unlink()

    def fail(row):
        row.update(
            status="failed",
            methods_completed=False,
            primary="RawObservationError",
            init_dynamics_completed=False,
            init_molecule_network_completed=False,
        )
        row["completed_stage_trials"].remove("init_dynamics")
        capture = next(
            c for c in row["captures"] if c["label"] == "init_dynamics.molecule_raw_returns"
        )
        capture.update(status="capture_failed", error=dict(type="RawObservationError"))

    change(value, "worker/demo/outcome.json", fail)
    result = inspect(value)
    assert result["status"] == "failed" and result["verification_issues"] == []
    assert result["demonstration"]["molecule_network"] == dict(
        selected=True, completed=False, identity=None
    )
    assert result["init_molecule_network_completed"] is False
    assert result["source_execution_complete"] is False
    assert any(c["status"] == "capture_failed" for c in result["demonstration"]["captures"])


def test_report_molecule_failure_only_capture_does_not_promote_unselected_route(tmp_path):
    value = fixture(tmp_path, endpoint="init_dynamics")
    (value.output / "result.json").unlink()
    raw = value.worker / "demo/failed-molecular.json"
    write(raw, dict(identity="e" * 64, source_completed=True))

    def fail(row):
        row.update(
            status="failed",
            methods_completed=False,
            primary="SelectionError",
            init_native_molecules=None,
            init_molecule_network_completed=False,
            init_dynamics_completed=False,
        )
        row["completed_stage_trials"].remove("init_dynamics")
        row["captures"].append(
            dict(
                label="init_dynamics.failure.molecule_record",
                path=raw.name,
                sha256=pin(raw)["sha256"],
                status="saved",
            )
        )

    change(value, "worker/demo/outcome.json", fail)
    result = inspect(value)
    assert result["status"] == "failed"
    assert result["demonstration"]["molecule_network"] == dict(
        selected=None, completed=False, identity=None
    )
    assert result["init_molecule_network_completed"] is False
    assert result["source_execution_complete"] is False


def test_report_molecule_raw_return_sidecar_bits_remain_authenticated(tmp_path):
    value = molecule_fixture(tmp_path)
    path = value.worker / "demo/molecule_raw_returns.json"
    path.unlink()
    raw = bytes.fromhex("0000000000000080010000000000f87f") * 4096
    report.evidence.write(
        path,
        dict(
            __ndarray__=True,
            dtype="<f8",
            shape=[8192],
            strides=[8],
            raw_bytes_hex=raw.hex(),
        ),
    )

    def update(row):
        capture = next(
            c for c in row["captures"] if c["label"] == "init_dynamics.molecule_raw_returns"
        )
        capture["sha256"] = pin(path)["sha256"]

    change(value, "worker/demo/outcome.json", update)
    assert inspect(value)["source_evidence_complete"] is True
    sidecar = next(path.with_name(path.name + ".arrays").glob("*.bin"))
    sidecar.write_bytes(b"x" + raw[1:])
    molecule_refusal(value, "")


@pytest.mark.parametrize("same_selection", [False, True])
def test_report_molecule_paired_flux_modes_require_same_molecular_route(tmp_path, same_selection):
    original = inspect(molecule_fixture(tmp_path, mode="original"))
    if same_selection:
        disabled_value = molecule_fixture(tmp_path, mode="disabled")
    else:
        disabled_value = fixture(tmp_path, mode="disabled", endpoint="init_dynamics")
        change(
            disabled_value,
            "worker/demo/outcome.json",
            lambda row: row.update(
                init_native_molecules=False,
                init_molecule_network_completed=False,
            ),
        )
    disabled = inspect(disabled_value)
    assert original["source_evidence_complete"] is disabled["source_evidence_complete"] is True
    paired = report.compare_modes(original, disabled)
    assert paired["matching"]["init_native_molecules"] is same_selection
    assert paired["paired_execution_complete"] is same_selection
    assert paired["physical_parity"] is paired["restart_qualified"] is False


@pytest.mark.parametrize("mode", ["original", "disabled"])
@pytest.mark.parametrize("iterations", [1, 3, 64])
def test_report_short_history_keeps_contiguous_states_and_original_time_bits(
    tmp_path, mode, iterations
):
    value = fixture(tmp_path, mode=mode, endpoint="init_short_history", iterations=iterations)
    result = inspect(value)
    assert result["status"] == "completed_unqualified" and result["verification_issues"] == []
    assert result["init_iterations_requested"] == result["init_iterations_completed"] == iterations
    history = result["demonstration"]["short_history"]
    assert history["recorded_iterations"] == iterations
    assert history["original_time_bits"] == [
        struct.pack("!d", i * 0.00123456789).hex() for i in range(iterations)
    ]
    assert history["initial_diagnostics"]["conservation_assessed"] is False
    assert history["numerical_or_conservation_qualification"] is False
    assert result["time_steps_qualified"] == result["scientific_credit"] == 0
    assert result["original_flux_defect_repaired"] is result["restart_qualified"] is False


@pytest.mark.parametrize("bad", [None, True, False, 0, -1, 65, 3.0, "3"])
def test_report_short_history_requires_exact_count_before_reading_outcome(tmp_path, bad):
    value = fixture(tmp_path, endpoint="init_short_history")
    plan = read(value.plan)
    plan["init_iterations"] = bad
    value.digest = write(value.plan, plan)["sha256"]
    with pytest.raises(ValueError, match="count"):
        inspect(value)


@pytest.mark.parametrize("version", [6, 7, 8, 9])
def test_report_short_history_cannot_relabel_historical_schemas(tmp_path, version):
    value = fixture(tmp_path, endpoint="init_short_history", version=version)
    with pytest.raises(ValueError, match="plan schemas"):
        inspect(value)


@pytest.mark.parametrize("bad", [True, 2, 4, None])
def test_report_short_history_prepared_demo_and_plan_count_must_agree(tmp_path, bad):
    value = fixture(tmp_path, endpoint="init_short_history")
    plan = read(value.plan)
    path = value.source.parent / "demo-plan.json"
    demo = read(path)
    demo["init_iterations"] = bad
    plan["demo_plan"] = write(path, demo)
    value.digest = write(value.plan, plan)["sha256"]
    with pytest.raises(ValueError, match="Prepared iteration count"):
        inspect(value)


@pytest.mark.parametrize(
    "mutation",
    [
        "count",
        "bool_count",
        "operator",
        "request",
        "parent",
        "trial",
        "row_count",
        "ordinal",
        "bool_ordinal",
        "time_bits",
        "sample_type",
        "snapshot",
        "work_backwards",
        "work_overflow",
        "callback_overflow",
        "molecular",
        "stream_before",
        "stream_after",
    ],
)
def test_report_short_history_refuses_count_state_epoch_or_work_retarget(tmp_path, mutation):
    value = fixture(tmp_path, endpoint="init_short_history")

    def mutate(row):
        if mutation in ("count", "bool_count"):
            row["requested_iterations"] = 2 if mutation == "count" else True
        elif mutation == "operator":
            row["operator_mode"] = "original_value_only_flux_omitted"
        elif mutation in ("request", "parent", "trial"):
            row[mutation + "_identity"] = "7" * 64
        elif mutation == "row_count":
            row["iterations"].pop()
        elif mutation in ("stream_before", "stream_after"):
            row[mutation.replace("stream_", "rng_")][0] = "7" * 64
        else:
            part = row["iterations"][1]
            key, replacement = {
                "ordinal": ("ordinal", 0),
                "bool_ordinal": ("ordinal", True),
                "time_bits": ("source_time_bits", "0000000000000000"),
                "sample_type": ("sampled", 1),
                "snapshot": ("after_identity", "7" * 64),
                "work_backwards": ("work_end", 0),
                "work_overflow": ("work_end", 9999),
                "callback_overflow": ("callbacks_end", 9999),
                "molecular": ("molecular_record_identity", True),
            }[mutation]
            part[key] = replacement

    change_capture(value, "init_short_history.linkage", mutate)
    result = inspect(value)
    assert result["verification_issues"] and result["status"] != "completed_unqualified"
    assert result["init_iterations_completed"] == result["scientific_credit"] == 0


# Independent, named public-call sequence from the frozen qualifier. Its source is
# read as AST only; neither the qualifier nor its codec/owners are imported here.
PARAMETER_OPERATIONS = (
    "birth-request",
    "actual-birth",
    "main-file",
    "yaml-request",
    "actual-yaml",
    "path-permission",
    "path-request",
    "actual-paths",
    "seven-request",
    "actual-seven",
    "numeric-request",
    "actual-numeric",
    "events-request",
    "actual-events",
    "expression-file",
    "network-input",
    "network-request",
    "actual-network",
    "grn-request",
    "actual-grn",
    "modulator-request",
    "actual-modulators",
    "colormap-input",
    "registry-capture",
    "actual-colormaps",
    "actual-constants",
    "actual-world-ready",
    "final-history",
    "final-live-parameters",
)


def parameter_archive(directory, *, numeric=False):
    """Build literal codec/NPY bytes with stdlib, without a serializer or NumPy."""
    directory.mkdir(parents=True)
    tree = dict(
        kind="cells.ordinary_ecm_molecule_checkpoint_graph@1",
        root=["ref", 0],
        nodes=[dict(tag="mapping", proxy=False, items=[[["str", "saved"], ["bool", True]]])],
    )
    raw = bytes.fromhex(
        "0000000000000080000000000000f07f"
    )  # -0.0 and +inf retained, not evaluated.
    arrays = {}
    if numeric:
        tree["nodes"][0]["items"].append([["str", "raw"], ["ref", 1]])
        tree["nodes"].append(
            dict(
                tag="array", key="a00000000", dtype="<f8", shape=[2], fortran=False, writable=False
            )
        )
        arrays["a00000000"] = dict(dtype="<f8", shape=[2], sha256=hashlib.sha256(raw).hexdigest())
    write(directory / "state.json", tree)
    with zipfile.ZipFile(directory / "arrays.npz", "w", compression=zipfile.ZIP_STORED) as archive:
        if numeric:
            header = b"{'descr': '<f8', 'fortran_order': False, 'shape': (2,), }"
            header += b" " * ((-10 - len(header) - 1) % 64) + b"\n"
            archive.writestr(
                "a00000000.npy",
                b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + raw,
            )
    fingerprint = hashlib.sha256(
        json.dumps(
            dict(tree=tree, arrays=arrays), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    return write(
        directory / "manifest.json",
        dict(
            kind="parameter_observation@1",
            files={n: pin(directory / n) for n in ("state.json", "arrays.npz")},
            fingerprint=fingerprint,
            complete=True,
            owner_admission=False,
            reconstruct_live_owners=False,
        ),
    )


def parameter_fixture(tmp_path, *, mode="original", count=29, acquired=False):
    value = fixture(tmp_path, mode=mode, parameter_prefix=True)
    directory = value.worker / "demo/parameters"
    rows = []
    primary = dict(
        type="builtins.AttributeError",
        identity=901,
        argument_summary=["missing public guard"],
        argument_summary_is_not_full_graph=True,
        cause_identity=900,
        context_identity=None,
        frames=[dict(file="frozen/remainder.py", function="parameters", line=73)],
        frames_truncated=False,
    )
    for index, name in enumerate(PARAMETER_OPERATIONS[:count]):
        target = directory / "evidence" / f"{index:02d}-{name}"
        row = dict(
            name=name,
            attempted=True,
            returned=acquired or index + 1 < count,
            evidence_complete=True,
            errors=[],
            graphs={},
            captures={},
        )
        if row["returned"]:
            row["returned_identity"] = 1000 + index
        else:
            row["primary"] = primary
            write(target / "primary.json", primary)
        write(target / "attempt.json", dict(name=name, attempt=index + 1))
        row["payload"] = parameter_archive(target / "payload", numeric=True)
        if name == "actual-world-ready":
            row["graphs"]["actual_p"] = parameter_archive(target / "graph-actual_p", numeric=True)
            row["captures"]["after"] = parameter_archive(target / "capture-after", numeric=True)
        write(target / "outcome.json", row)
        rows.append(row)
    if acquired:
        assert count == 29
        journal = dict(
            packet=read(value.plan)["parameter_inputs"],
            operations=rows,
            actual_world_ready_identity=rows[-3]["returned_identity"],
            actual_p_identity=rows[-1]["returned_identity"],
            construction_claim_opened=False,
            phase_or_persisted_owner_admission=False,
        )
        journal_name = "acquisition.json"
    else:
        journal = dict(primary=primary, operations=rows, source_or_evidence_incomplete=True)
        journal_name = "failure.json"
        # This is one failed saved acquisition, not a completed worker with an invented owner.
        (value.output / "result.json").unlink()
        (value.worker / "result.json").unlink()
        write(value.output / "failure.json", dict(status="failed", primary=primary))
        process = read(value.output / "process/result.json")
        process.update(status="failed", returncode=1)
        (value.output / "process/result.json").unlink()
        write(value.output / "process/failure.json", process)
        change(
            value,
            "worker/demo/outcome.json",
            lambda row: row.update(
                status="failed",
                methods_completed=False,
                primary=primary,
                completed_stage_trials=[],
                captures=[],
                operations=[
                    dict(name="callback", status="returned"),
                    dict(name="parameters", status="failed"),
                ],
            ),
        )
    write(directory / journal_name, journal)
    value.parameter_dir, value.parameter_journal = directory, journal_name
    return value


def parameter_row(value, index, mutate):
    path = value.parameter_dir / value.parameter_journal
    journal = read(path)
    row = journal["operations"][index]
    mutate(row)
    write(value.parameter_dir / "evidence" / f"{index:02d}-{row['name']}" / "outcome.json", row)
    write(path, journal)


@pytest.mark.parametrize("mode", ["original", "disabled"])
def test_report_parameter_prefix_returns_survive_failed_public_access(tmp_path, mode):
    value = parameter_fixture(tmp_path, mode=mode)
    result = inspect(value)
    prefix = result["parameter_load_prefix"]
    assert not result["verification_issues"], result["verification_issues"]
    assert result["status"] == "failed" and not result["source_execution_complete"]
    assert result["time_steps_qualified"] == result["init_iterations_completed"] == 0
    assert prefix["status"] == "failed_after_recorded_prefix" and prefix["evidence_complete"]
    assert prefix["actual_world_ready_returned"] and prefix["completed_history_returned"]
    assert not prefix["acquisition_returned"] and not prefix["usable_owner"]
    assert not prefix["init_or_sim_credit"] and prefix["scientific_credit"] == 0
    failed = prefix["final_live_parameters"]
    assert failed["status"] == "failed" and failed["primary"]["cause_identity"] == 900
    assert failed["primary"]["argument_summary"] == ["missing public guard"]
    assert [row["name"] for row in prefix["operations"]] == list(PARAMETER_OPERATIONS)
    assert prefix["archive_count"] == 31 and prefix["authenticated_payload_bytes"] > 31 * 16
    assert all(
        archive["verified"]["numeric_bytes"] == 16
        for row in prefix["operations"]
        for archive in row["archives"]
    )
    assert all(
        archive["verified"]["graph_reconstructed"] is False
        for row in prefix["operations"]
        for archive in row["archives"]
    )


def test_report_parameter_prefix_uses_exact_frozen_operation_ast_without_import(tmp_path):
    value = parameter_fixture(tmp_path, count=1)
    assert report._parameter_roster(report.Reader(), read(value.plan)) == list(PARAMETER_OPERATIONS)
    source = value.source / report.PARAMETER
    source.chmod(0o644)
    source.write_bytes(source.read_bytes() + b"\n# altered frozen source\n")
    source.chmod(0o444)
    with pytest.raises(ValueError):
        inspect(value)


@pytest.mark.parametrize("version", [6, 7, 8, 9, 10])
@pytest.mark.parametrize("mode", ["original", "disabled"])
def test_report_parameter_prefix_absent_historical_journal_is_explicit(tmp_path, version, mode):
    result = inspect(fixture(tmp_path, version=version, mode=mode))
    assert result["status"] == "completed_unqualified" and not result["verification_issues"]
    prefix = result["parameter_load_prefix"]
    assert prefix["status"] == "not_recorded" and prefix["journal_files"] == []
    assert not prefix["actual_world_ready_returned"] and not prefix["acquisition_returned"]
    assert not prefix["usable_owner"] and not prefix["evidence_complete"]


def test_report_parameter_prefix_present_but_unpublished_is_incomplete(tmp_path):
    value = fixture(tmp_path)
    (value.worker / "demo/parameters/evidence").mkdir(parents=True)
    result = inspect(value)
    assert result["status"] == "incomplete_evidence"
    assert result["parameter_load_prefix"]["status"] == "incomplete_evidence"
    assert any(i["type"] == "MissingEvidence" for i in result["verification_issues"])


@pytest.mark.parametrize("role", ["payload", "graph-actual_p", "capture-after"])
def test_report_parameter_prefix_authenticates_all_archive_roles(tmp_path, role):
    value = parameter_fixture(tmp_path)
    target = value.parameter_dir / "evidence/26-actual-world-ready" / role / "arrays.npz"
    target.write_bytes(target.read_bytes() + b"changed")
    result = inspect(value)
    prefix = result["parameter_load_prefix"]
    assert result["status"] == "failed" and result["verification_issues"]
    assert not prefix["actual_world_ready_returned"] and not prefix["evidence_complete"]
    assert prefix["operations"][26]["journal_returned"] is True
    assert prefix["final_live_parameters"]["primary"]["type"] == "builtins.AttributeError"
    assert prefix["reader_charged_file_bytes"] > prefix["authenticated_payload_bytes"]
    assert any(role in row["section"] for row in result["verification_issues"])


@pytest.mark.parametrize("mutation", ["missing", "truncated", "fingerprint", "dtype", "duplicate"])
def test_report_parameter_prefix_resealed_bad_archive_never_becomes_complete(tmp_path, mutation):
    value = parameter_fixture(tmp_path, count=1)
    directory = value.parameter_dir / "evidence/00-birth-request/payload"
    manifest = read(directory / "manifest.json")
    if mutation == "missing":
        (directory / "arrays.npz").unlink()
    elif mutation == "truncated":
        target = directory / "arrays.npz"
        target.write_bytes(target.read_bytes()[:-9])
        manifest["files"]["arrays.npz"] = pin(target)
    elif mutation == "fingerprint":
        manifest["fingerprint"] = "f" * 64
    else:
        target = directory / "arrays.npz"
        with zipfile.ZipFile(target) as archive:
            raw = archive.read("a00000000.npy")
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr(
                "a00000000.npy", raw.replace(b"<f8", b"<i8") if mutation == "dtype" else raw
            )
            if mutation == "duplicate":
                with pytest.warns(UserWarning, match="Duplicate name"):
                    archive.writestr("a00000000.npy", raw)
        manifest["files"]["arrays.npz"] = pin(target)
    newpin = write(directory / "manifest.json", manifest)
    parameter_row(value, 0, lambda row: row.update(payload=newpin))
    result = inspect(value)
    assert result["status"] == "failed" and result["verification_issues"]
    assert not result["parameter_load_prefix"]["evidence_complete"]
    assert result["parameter_load_prefix"]["operations"][0]["status"] == "failed"


@pytest.mark.parametrize("mutation", ["outcome", "attempt", "journal_order", "identity", "graphs"])
def test_report_parameter_prefix_independent_outcome_and_journal_checks(tmp_path, mutation):
    value = parameter_fixture(tmp_path, count=2)
    operation = value.parameter_dir / "evidence/00-birth-request"
    if mutation in ("outcome", "attempt"):
        path = operation / (mutation + ".json")
        row = read(path)
        row["name"] = "wrong"
        write(path, row)
    elif mutation == "journal_order":
        path = value.parameter_dir / "failure.json"
        row = read(path)
        row["operations"].reverse()
        write(path, row)
    elif mutation == "identity":
        parameter_row(value, 0, lambda row: row.update(returned_identity=True))
    else:
        parameter_row(value, 0, lambda row: row.pop("graphs"))
    result = inspect(value)
    assert result["status"] == "failed" and result["verification_issues"]
    assert not result["parameter_load_prefix"]["evidence_complete"]
    assert not result["parameter_load_prefix"]["acquisition_returned"]


def test_report_parameter_prefix_late_capture_gap_keeps_authenticated_returns(tmp_path):
    value = parameter_fixture(tmp_path)
    parameter_row(
        value,
        28,
        lambda row: row.update(
            evidence_complete=False,
            errors=[dict(stage="observe-or-archive", type="CaptureError", identity=902)],
        ),
    )
    result = inspect(value)
    prefix = result["parameter_load_prefix"]
    assert result["status"] == "failed" and not prefix["evidence_complete"]
    assert prefix["actual_world_ready_returned"] and prefix["completed_history_returned"]
    assert prefix["final_live_parameters"]["status"] == "failed"
    assert prefix["final_live_parameters"]["capture_errors"][0]["identity"] == 902
    assert prefix["primary"]["identity"] == 901 and prefix["primary"]["cause_identity"] == 900


def test_report_parameter_prefix_early_failure_with_no_operation_retains_primary(tmp_path):
    value = parameter_fixture(tmp_path, count=0)
    result = inspect(value)
    prefix = result["parameter_load_prefix"]
    assert result["status"] == "failed" and not result["verification_issues"]
    assert prefix["operations"] == [] and prefix["archive_count"] == 0
    assert prefix["primary"]["identity"] == 901 and prefix["primary"]["cause_identity"] == 900
    assert not prefix["actual_world_ready_returned"] and not prefix["acquisition_returned"]
    assert not prefix["usable_owner"]


def test_report_parameter_prefix_failure_archive_gap_does_not_erase_earlier_returns(tmp_path):
    value = parameter_fixture(tmp_path)
    path = value.parameter_dir / "evidence/28-final-live-parameters/payload/manifest.json"
    path.write_text('{"kind":')
    result = inspect(value)
    prefix = result["parameter_load_prefix"]
    assert result["status"] == "failed" and result["verification_issues"]
    assert prefix["actual_world_ready_returned"] and prefix["completed_history_returned"]
    assert not prefix["evidence_complete"] and prefix["final_live_parameters"]["status"] == "failed"
    assert prefix["final_live_parameters"]["primary"]["cause_identity"] == 900


def test_report_parameter_prefix_full_saved_acquisition_is_never_live_owner_authority(tmp_path):
    result = inspect(parameter_fixture(tmp_path, acquired=True))
    prefix = result["parameter_load_prefix"]
    assert result["status"] == "completed_unqualified", result["verification_issues"]
    assert prefix["status"] == "returned_acquisition" and prefix["acquisition_returned"]
    assert prefix["actual_world_ready_returned"] and prefix["completed_history_returned"]
    assert prefix["final_live_parameters"]["status"] == "returned"
    assert not prefix["usable_owner"] and not prefix["init_or_sim_credit"]


@pytest.mark.parametrize("field", ["actual_world_ready_identity", "actual_p_identity", "packet"])
def test_report_parameter_prefix_acquisition_linkage_is_authenticated(tmp_path, field):
    value = parameter_fixture(tmp_path, acquired=True)
    path = value.parameter_dir / "acquisition.json"
    row = read(path)
    row[field] = 999 if field != "packet" else dict(path="/absent-inputs.json", sha256="f" * 64)
    write(path, row)
    result = inspect(value)
    assert result["verification_issues"] and result["status"] == "incomplete_evidence"
    assert not result["parameter_load_prefix"]["acquisition_returned"]


@pytest.mark.parametrize(
    "field",
    [
        "linkage",
        "record",
        "before",
        "after",
        "calendar",
        "sampled",
        "configured_dt",
        "stream_before",
        "stream_after",
        "work",
        "helpers",
        "callbacks",
        "raw_returns",
        "initial_diagnostics",
        "iteration.0001.after",
    ],
)
def test_report_short_history_needs_every_original_capture(tmp_path, field):
    value = fixture(tmp_path, endpoint="init_short_history")
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row.update(
            captures=[c for c in row["captures"] if c["label"] != "init_short_history." + field]
        ),
    )
    result = inspect(value)
    assert result["verification_issues"] and result["status"] != "completed_unqualified"


@pytest.mark.parametrize(
    "mutation", ["after", "time", "work", "callbacks", "rows", "completion", "flags"]
)
def test_report_short_history_original_record_cannot_drift_behind_linkage(tmp_path, mutation):
    value = fixture(tmp_path, endpoint="init_short_history")

    def mutate(row):
        if mutation == "after":
            row["after"] = "7" * 64
        elif mutation == "time":
            row["iterations"][1][1] = "0000000000000000"
        elif mutation in ("work", "callbacks"):
            row[mutation] = 0
        elif mutation == "rows":
            row["iterations"].reverse()
        elif mutation == "completion":
            row["source_completed"] = False
        elif mutation == "flags":
            row["loop_returned"] = row["selected_stop"] = True

    change_capture(value, "init_short_history.record", mutate)
    result = inspect(value)
    assert result["verification_issues"] and result["status"] != "completed_unqualified"


@pytest.mark.parametrize("mutation", ["request", "count", "flag", "first_step"])
def test_report_short_history_outcome_cannot_overstate_or_relabel_work(tmp_path, mutation):
    value = fixture(tmp_path, endpoint="init_short_history")
    key, changed = {
        "request": ("init_iterations", 2),
        "count": ("init_time_steps_completed", 4),
        "flag": ("init_short_history_completed", False),
        "first_step": ("init_first_step_completed", True),
    }[mutation]
    change(value, "worker/demo/outcome.json", lambda row: row.update({key: changed}))
    result = inspect(value)
    assert result["verification_issues"] and result["init_iterations_completed"] == 0


@pytest.mark.parametrize("promote", [False, True])
def test_report_short_history_failure_retains_completed_rows_without_promotion(tmp_path, promote):
    value = fixture(tmp_path, endpoint="init_short_history")
    primary = dict(type="OriginalSourceError", message="retained", cause="original cause")
    (value.output / "result.json").unlink()
    write(value.output / "failure.json", dict(error=primary))
    change(
        value,
        "worker/demo/outcome.json",
        lambda row: row.update(
            status="failed",
            primary=primary,
            methods_completed=False,
            init_short_history_completed=promote,
            init_time_steps_completed=3 if promote else 0,
        ),
    )
    result = inspect(value)
    assert result["status"] == "failed" and result["init_iterations_completed"] == 0
    assert result["failures"][-1]["failure"]["primary"] == primary
    assert bool(result["verification_issues"]) is promote
    if not promote:
        record = next(
            r
            for r in result["demonstration"]["captures"]
            if r["label"] == "init_short_history.record"
        )
        assert len(record["references"]["iterations"]) == 3
        assert result["demonstration"]["short_history"] is None


def test_report_short_history_pair_requires_same_declared_count(tmp_path):
    original = inspect(fixture(tmp_path, endpoint="init_short_history", iterations=3))
    disabled = inspect(
        fixture(tmp_path, mode="disabled", endpoint="init_short_history", iterations=2)
    )
    paired = report.compare_modes(original, disabled)
    assert original["status"] == disabled["status"] == "completed_unqualified"
    assert paired["matching"]["init_iterations_requested"] is False
    assert paired["paired_execution_complete"] is paired["numerical_equality_checked"] is False


@pytest.mark.parametrize("count", [None, True, 2])
def test_report_short_history_worker_count_must_match_completed_plan(tmp_path, count):
    value = fixture(tmp_path, endpoint="init_short_history")
    worker = read(value.worker / "result.json")
    worker["init_iterations"] = count
    worker_pin = write(value.worker / "result.json", worker)
    change(value, "result.json", lambda row: row.update(worker=worker_pin))
    result = inspect(value)
    assert result["verification_issues"] and result["status"] != "completed_unqualified"
    assert result["init_iterations_completed"] == 0


def test_report_short_history_cannot_promote_natural_loop_return(tmp_path):
    value = fixture(tmp_path, endpoint="init_short_history")
    change_capture(
        value,
        "init_short_history.record",
        lambda row: row.update(loop_returned=True, selected_stop=False),
    )
    result = inspect(value)
    assert result["verification_issues"] and result["init_iterations_completed"] == 0


@pytest.mark.parametrize("field", ["work", "helpers", "callbacks"])
@pytest.mark.parametrize("mutation", ["empty", "short", "long", "wrong_type"])
def test_report_short_history_actual_work_capture_lengths_match_original_totals(
    tmp_path, field, mutation
):
    value = fixture(tmp_path, endpoint="init_short_history")

    def mutate(rows):
        assert type(rows) is list and len(rows) > 1
        if mutation == "empty":
            return []
        if mutation == "short":
            return rows[:-1]
        if mutation == "long":
            return [*rows, rows[-1]]
        return {"declared_length": len(rows)}

    change_capture(value, "init_short_history." + field, mutate)
    result = inspect(value)
    assert result["verification_issues"] and result["status"] != "completed_unqualified"
    assert result["init_iterations_completed"] == 0


@pytest.mark.parametrize(
    "mutation",
    ["legacy_seven", "sampled_false", "sampled_int", "rng_before", "rng_after", "rng_missing"],
)
def test_report_short_history_requires_original_sample_and_stream_witnesses(tmp_path, mutation):
    value = fixture(tmp_path, endpoint="init_short_history")

    def mutate(row):
        if mutation == "legacy_seven":
            for iteration in row["iterations"]:
                iteration.pop(2)
        elif mutation == "sampled_false":
            row["iterations"][0][2] = False
        elif mutation == "sampled_int":
            row["iterations"][0][2] = 1
        elif mutation == "rng_missing":
            del row["rng_before"]
        else:
            row[mutation][0] = "7" * 64

    change_capture(value, "init_short_history.record", mutate)
    result = inspect(value)
    assert result["verification_issues"] and result["status"] != "completed_unqualified"
    assert result["init_iterations_completed"] == result["scientific_credit"] == 0


def attach_initial_rng(value):
    """Canonical archive.snapshot wire, not a cache; explicitly inert saved evidence."""
    plan = read(value.plan)
    state = dict(
        numpy_random=[
            "MT19937",
            dict(
                __ndarray__=True,
                dtype="<u4",
                shape=[624],
                strides=[4],
                raw_bytes_hex=struct.pack("<624I", *range(1, 625)).hex(),
            ),
            624,
            0,
            dict(float64_bits="0000000000000080"),
        ],
        python_random=[3, [*range(1, 625), 624], dict(float64_bits="010000000000f87f")],
        initial_random_reset_or_replacement=False,
    )
    rng_files = {}
    for name in report.RNG_MODULES:
        path = value.base / "runtime" / (name + ".inert")
        path.write_text("metadata-only runtime fixture: " + name + "\n")
        rng_files[name] = pin(path)
    for name in ("runtime-before.json", "runtime-after.json"):
        path = value.worker / name
        runtime = read(path)
        runtime.update(python="3.13.synthetic")
        runtime["loaded_files"].update(rng_files)
        write(path, runtime)
    witness = dict(
        kind=report.INITIAL_RNG_KIND,
        epoch=report.INITIAL_RNG_EPOCH,
        common_binding=dict(
            input_inventory_sha256=plan["initial_rng_inputs"]["inventory_sha256"],
            mode=plan["flux_operator"],
            profile="original",
            runtime=dict(
                python="3.13.synthetic",
                executable=plan["runtime"]["executable"],
                numpy_version="synthetic-wire-only",
                files=rng_files,
            ),
        ),
        state=state,
        source=dict(
            files={name: plan["producers"][name] for name in (report.INITIAL_RNG, report.DEMO)},
            snapshot_sha256=plan["source_snapshot"]["sha256"],
            parameter_packet_sha256=plan["parameter_inputs"]["sha256"],
        ),
        order=dict(
            boundary=report.INITIAL_RNG_BOUNDARY,
            parameter_identity=101,
            world_ready_identity=102,
            callback_identity=103,
            same_parameter=True,
            seed_entered=False,
            selected_boundaries=[
                ["callback", "returned"],
                ["constructor_preflight", "returned"],
                ["parameters", "returned"],
                ["initial_rng", "attempted"],
            ],
        ),
        observed_states_equalized=False,
        common_starting_authority_established=False,
        scientific_physical_checkpoint_credit=0,
    )
    rows = []
    for label, data in (("before_seed_random_states", state), ("pre_seed_rng_witness", witness)):
        path = value.worker / "demo" / (label + ".json")
        write(path, data)
        rows.append(dict(path=path.name, sha256=pin(path)["sha256"], label=label, status="saved"))
    path = value.worker / "demo/outcome.json"
    outcome = read(path)
    outcome.update(initial_rng_observation=rows[1], common_starting_authority_established=False)
    outcome["captures"] = rows + outcome["captures"]
    outcome["operations"][1:1] = [dict(name="constructor_preflight", status="returned")]
    outcome["operations"][3:3] = [dict(name="initial_rng", status="returned")]
    write(path, outcome)
    # New launch schemas bind the worker's explicit None selection too.
    worker = read(value.worker / "result.json")
    worker["init_iterations"] = plan.get("init_iterations")
    worker_pin = write(value.worker / "result.json", worker)
    controller = read(value.output / "result.json")
    controller["worker"] = worker_pin
    write(value.output / "result.json", controller)


def initial_rng_capture_change(value, label, action):
    change_capture(value, label, action)
    path = value.worker / "demo/outcome.json"
    outcome = read(path)
    outcome["initial_rng_observation"] = next(
        row for row in outcome["captures"] if row["label"] == "pre_seed_rng_witness"
    )
    write(path, outcome)


@pytest.mark.parametrize("mode", ("original", "disabled"))
def test_report_initial_rng_complete_canonical_wire_is_observation_only(tmp_path, mode):
    value = fixture(tmp_path, mode=mode, version=12)
    result = inspect(value)
    write(tmp_path / "initial-rng-report.json", result)
    assert result["verification_issues"] == [] and result["status"] == "completed_unqualified"
    observed = result["demonstration"]["initial_rng"]
    assert observed["observed"] is True and observed["state_bytes_preserved"] is True
    assert observed["common_starting_authority_established"] is False
    assert result["common_starting_authority_established"] is False
    assert result["scientific_credit"] == 0 and result["numerical_comparison"] is False
    wire = next(
        row["initial_rng_wire"]
        for row in result["demonstration"]["captures"]
        if row["label"] == "before_seed_random_states"
    )
    assert wire["numpy_random"][4] == dict(float64_bits="0000000000000080")
    assert wire["python_random"][2] == dict(float64_bits="010000000000f87f")
    assert result["initial_rng_inputs"]["inventory"]["directories"] == []


@pytest.mark.parametrize("present", (False, True))
def test_report_initial_rng_legacy_seven_constructor_preflight_is_optional_exactly_once(
    tmp_path, present
):
    value = fixture(tmp_path, version=11)
    if present:
        change(
            value,
            "worker/demo/outcome.json",
            lambda data: data["operations"].insert(
                1, dict(name="constructor_preflight", status="returned")
            ),
        )
    result = inspect(value)
    assert result["status"] == "completed_unqualified" and result["verification_issues"] == []
    assert "initial_rng_inputs" not in result and "initial_rng" not in result["demonstration"]


@pytest.mark.parametrize("version", (11, 12))
@pytest.mark.parametrize("mutation", ("duplicate", "late", "failed"))
def test_report_initial_rng_constructor_operation_is_not_ignored(tmp_path, version, mutation):
    value = fixture(tmp_path, version=version)
    if version == 11:
        change(
            value,
            "worker/demo/outcome.json",
            lambda data: data["operations"].insert(
                1, dict(name="constructor_preflight", status="returned")
            ),
        )
    assert inspect(value)["status"] == "completed_unqualified"

    def change_ops(data):
        row = data["operations"][1]
        if mutation == "duplicate":
            data["operations"].insert(1, dict(row))
        elif mutation == "late":
            data["operations"].insert(3, data["operations"].pop(1))
        else:
            row["status"] = "failed"

    change(value, "worker/demo/outcome.json", change_ops)
    result = inspect(value)
    assert result["verification_issues"] and not result["source_evidence_complete"]


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_witness",
        "missing_state",
        "failed_witness",
        "duplicate_witness",
        "wrong_observation_row",
        "absent_observation",
        "missing_preflight",
        "missing_rng",
        "late_rng",
        "failed_rng",
        "authority_flag",
        "old_outcome_schema",
    ),
)
def test_report_initial_rng_success_requires_complete_bound_capture_and_order(tmp_path, mutation):
    value = fixture(tmp_path, version=12)
    assert inspect(value)["status"] == "completed_unqualified"

    def mutate(data):
        if mutation in ("missing_witness", "missing_state"):
            label = (
                "pre_seed_rng_witness"
                if mutation == "missing_witness"
                else "before_seed_random_states"
            )
            data["captures"] = [row for row in data["captures"] if row["label"] != label]
        elif mutation == "failed_witness":
            data["captures"][1].update(status="capture_failed", error=dict(type="CaptureError"))
            data["initial_rng_observation"] = dict(data["captures"][1])
        elif mutation == "duplicate_witness":
            data["captures"].append(dict(data["captures"][1]))
        elif mutation == "wrong_observation_row":
            data["initial_rng_observation"] = dict(data["captures"][0])
        elif mutation == "absent_observation":
            data["initial_rng_observation"] = None
        elif mutation in ("missing_preflight", "missing_rng"):
            name = "constructor_preflight" if mutation == "missing_preflight" else "initial_rng"
            data["operations"] = [row for row in data["operations"] if row["name"] != name]
        elif mutation == "late_rng":
            data["operations"].insert(5, data["operations"].pop(3))
        elif mutation == "failed_rng":
            data["operations"][3]["status"] = "failed"
        elif mutation == "authority_flag":
            data["common_starting_authority_established"] = True
        else:
            data["kind"] = report.DEMO_KINDS[5]

    change(value, "worker/demo/outcome.json", mutate)
    result = inspect(value)
    write(tmp_path / "initial-rng-refusal.json", result)
    assert result["verification_issues"] and not result["source_evidence_complete"]


@pytest.mark.parametrize(
    "mutation",
    (
        "epoch",
        "inventory",
        "profile",
        "mode",
        "producer",
        "snapshot",
        "parameter_packet",
        "equalized",
        "authority",
        "credit",
        "seed_entered",
        "parameter_identity",
        "order",
        "runtime_roster",
        "runtime_python",
        "runtime_executable",
        "runtime_loaded_origin",
    ),
)
def test_report_initial_rng_resealed_witness_retains_exact_provenance_and_no_authority(
    tmp_path, mutation
):
    value = fixture(tmp_path, version=12)
    assert inspect(value)["status"] == "completed_unqualified"

    def mutate(data):
        if mutation == "epoch":
            data["epoch"] = "after_SEED"
        elif mutation in ("inventory", "profile", "mode"):
            key = "input_inventory_sha256" if mutation == "inventory" else mutation
            data["common_binding"][key] = {
                "inventory": "0" * 64,
                "profile": "headless",
                "mode": "disabled",
            }[mutation]
        elif mutation in ("producer", "snapshot", "parameter_packet"):
            if mutation == "producer":
                data["source"]["files"][report.INITIAL_RNG] = "0" * 64
            else:
                data["source"][mutation + "_sha256"] = "0" * 64
        elif mutation in ("equalized", "authority", "credit"):
            key = {
                "equalized": "observed_states_equalized",
                "authority": "common_starting_authority_established",
                "credit": "scientific_physical_checkpoint_credit",
            }[mutation]
            data[key] = True
        elif mutation == "seed_entered":
            data["order"]["seed_entered"] = True
        elif mutation == "parameter_identity":
            data["order"]["parameter_identity"] = True
        elif mutation == "order":
            data["order"]["selected_boundaries"].pop(1)
        elif mutation == "runtime_roster":
            del data["common_binding"]["runtime"]["files"]["_random"]
        elif mutation == "runtime_python":
            data["common_binding"]["runtime"]["python"] = "foreign"
        elif mutation == "runtime_executable":
            data["common_binding"]["runtime"]["executable"] = data["common_binding"]["runtime"][
                "files"
            ]["_random"]
        else:
            data["common_binding"]["runtime"]["files"]["numpy"] = data["common_binding"]["runtime"][
                "files"
            ]["random"]

    initial_rng_capture_change(value, "pre_seed_rng_witness", mutate)
    result = inspect(value)
    assert result["verification_issues"] and not result["source_evidence_complete"]


@pytest.mark.parametrize(
    "mutation",
    (
        "reset",
        "dtype",
        "shape",
        "strides",
        "truncated_bytes",
        "zero_state",
        "mt_position_bool",
        "has_gauss",
        "float_value",
        "python_version",
        "python_words",
        "python_word_bool",
        "python_position",
        "python_gauss",
        "cache_descriptor",
        "state_mismatch",
    ),
)
def test_report_initial_rng_canonical_full_states_are_checked_before_credit(tmp_path, mutation):
    value = fixture(tmp_path, version=12)
    assert inspect(value)["status"] == "completed_unqualified"

    def state_change(data):
        mt, py = data["numpy_random"], data["python_random"]
        if mutation == "reset":
            data["initial_random_reset_or_replacement"] = True
        elif mutation in ("dtype", "shape", "strides"):
            mt[1][mutation] = {"dtype": "<i4", "shape": [623], "strides": [8]}[mutation]
        elif mutation == "truncated_bytes":
            mt[1]["raw_bytes_hex"] = mt[1]["raw_bytes_hex"][:-2]
        elif mutation == "zero_state":
            mt[1]["raw_bytes_hex"] = "0" * (624 * 8)
        elif mutation == "mt_position_bool":
            mt[2] = True
        elif mutation == "has_gauss":
            mt[3] = 2
        elif mutation == "float_value":
            mt[4] = 0.0
        elif mutation == "python_version":
            py[0] = 2
        elif mutation == "python_words":
            py[1].pop()
        elif mutation == "python_word_bool":
            py[1][0] = True
        elif mutation == "python_position":
            py[1][-1] = 625
        elif mutation == "python_gauss":
            py[2] = dict(float64_bits="00")
        elif mutation == "cache_descriptor":
            mt[1] = terminal_calendar_cache([[0, "0000000000000000"]])
        else:
            mt[2] = 623

    initial_rng_capture_change(value, "before_seed_random_states", state_change)
    if mutation != "state_mismatch":
        initial_rng_capture_change(
            value, "pre_seed_rng_witness", lambda data: state_change(data["state"])
        )
    result = inspect(value)
    assert result["verification_issues"] and not result["source_evidence_complete"]


@pytest.mark.parametrize(
    "mutation", ("missing", "profile", "directory", "size", "digest", "source_pin", "authority")
)
def test_report_initial_rng_prepared_plan_requires_whole_selected_inventory(tmp_path, mutation):
    value = fixture(tmp_path, version=12)
    assert inspect(value)["status"] == "completed_unqualified"
    plan = read(value.plan)
    demo = read(report.Path(plan["demo_plan"]["path"]))
    selected = demo["initial_rng_inputs"]
    if mutation == "missing":
        del plan["initial_rng_inputs"]
    elif mutation == "profile":
        selected["profile"] = "headless"
    elif mutation == "directory":
        selected["inventory"]["directories"] = ["undeclared"]
    elif mutation == "size":
        selected["inventory"]["files"]["original.yaml"]["size_bytes"] = 0
    elif mutation == "digest":
        selected["inventory_sha256"] = "0" * 64
    elif mutation == "source_pin":
        demo["source_plan"]["initial_rng_observation"]["producer_sha256"] = "0" * 64
    else:
        demo["source_plan"]["initial_rng_observation"]["common_starting_authority_established"] = (
            True
        )
    plan["demo_plan"] = write(report.Path(plan["demo_plan"]["path"]), demo)
    value.digest = write(value.plan, plan)["sha256"]
    with pytest.raises((ValueError, KeyError)):
        report.inspect_attempt(value.plan, plan_sha256=value.digest)


def test_report_initial_rng_later_failure_retains_observation_without_completion(tmp_path):
    value = fixture(tmp_path, version=12)
    assert inspect(value)["status"] == "completed_unqualified"

    def fail(data):
        data.update(
            status="failed",
            methods_completed=False,
            primary=dict(type="SourceError", identity=901),
            completed_stage_trials=[],
        )
        data["operations"] = data["operations"][:5]
        data["operations"][-1]["status"] = "failed"

    change(value, "worker/demo/outcome.json", fail)
    (value.output / "result.json").unlink()
    result = inspect(value)
    assert result["status"] == "failed" and not result["source_execution_complete"]
    assert result["demonstration"]["initial_rng"]["observed"] is True
    assert result["common_starting_authority_established"] is False


def test_report_initial_rng_failed_capture_does_not_issue_saved_observation(tmp_path):
    value = fixture(tmp_path, version=12)

    def fail(data):
        data.update(
            status="failed",
            methods_completed=False,
            initial_rng_observation=None,
            primary=dict(type="CaptureError", identity=902),
            completed_stage_trials=[],
        )
        data["operations"] = data["operations"][:4]
        data["operations"][-1]["status"] = "failed"
        data["captures"] = data["captures"][:2]
        data["captures"][-1].update(status="capture_failed", error=dict(type="CaptureError"))

    change(value, "worker/demo/outcome.json", fail)
    (value.output / "result.json").unlink()
    result = inspect(value)
    assert (
        result["status"] == "failed" and result["demonstration"]["initial_rng"]["observed"] is False
    )
    assert not result["source_evidence_complete"]


def test_report_initial_rng_pair_checks_complete_inventory_not_state_equality(tmp_path):
    first, second = fixture(tmp_path, version=12), fixture(tmp_path, mode="disabled", version=12)
    initial_rng_capture_change(
        second, "before_seed_random_states", lambda data: data["numpy_random"].__setitem__(2, 623)
    )
    initial_rng_capture_change(
        second,
        "pre_seed_rng_witness",
        lambda data: data["state"]["numpy_random"].__setitem__(2, 623),
    )
    a, b = inspect(first), inspect(second)
    assert a["status"] == b["status"] == "completed_unqualified"
    result = report.compare_modes(a, b)
    assert (
        result["paired_execution_complete"] is True
        and result["matching"]["initial_rng_inputs"] is True
    )
    assert result["numerical_equality_checked"] is False and result["physical_parity"] is False
    changed = copy.deepcopy(b)
    changed["initial_rng_inputs"]["inventory"]["directories"] = ["different"]
    assert report.compare_modes(a, changed)["paired_execution_complete"] is False
