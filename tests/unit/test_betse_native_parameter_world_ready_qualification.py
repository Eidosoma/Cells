"""Blocked software boundaries only; no synthetic successful Parameters/WorldReady."""

import builtins
import copy
import importlib.abc
import json
import os
import struct
import sys
from pathlib import Path
from types import FunctionType, ModuleType

import pytest

from cells.processes import betse_normal_ecm_molecule_checkpoint_codec as evidence_codec
from validation.betse import betse_native_parameter_world_ready_qualification as q
from validation.betse import betse_normal_ecm_molecule_handoff_run_plugin as recording


@pytest.fixture(scope="session", autouse=True)
def software_runtime_binding(tmp_path_factory):
    # Runtime imports above are library bootstrap, before each no-native/RNG
    # control. Keep the actual pytest child's inventory distinct from later
    # readers and from the still-unexecuted retained BETSE runtime composition.
    yield
    from validation.betse.betse_normal_channel_join_runtime import inventory

    q.snapshot.write_json(
        tmp_path_factory.getbasetemp() / "software-runtime.json",
        dict(
            child=recording.identity(),
            runtime=inventory(),
            producers=[q.ref(Path(q.__file__).resolve()), q.ref(Path(__file__).resolve())],
            scope="Actual blocked-software child; runtime bootstrap precedes per-case guards",
            retained_betse_runtime_executed=False,
        ),
    )


@pytest.fixture(autouse=True)
def native_blocked(monkeypatch, tmp_path, request):
    attempts = []
    previous_trace, previous_profile = sys.gettrace(), sys.getprofile()
    write = q.snapshot.write_json

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "betse" or fullname.startswith("betse."):
                attempts.append(fullname)
                raise AssertionError("Actual native import forbidden by software controls")

    finder = Block()
    sys.meta_path.insert(0, finder)

    def trace(frame, event, arg):
        module = frame.f_globals.get("__name__", "")
        if event == "call" and (
            frame.f_code.co_filename.startswith(str(q.NATIVE) + os.sep)
            or (module == "random" and frame.f_code.co_name != "<module>")
            or module.startswith("cells.numerics.")
        ):
            attempts.append((module, frame.f_code.co_name))
            raise AssertionError("Native/model/RNG body forbidden in software controls")
        if previous_trace is not None:
            return previous_trace(frame, event, arg)
        return None

    def forbidden(*args, **kwargs):
        attempts.append("actual-pipeline")
        raise AssertionError("Actual parameter pipeline forbidden by software controls")

    monkeypatch.setattr(q, "_execute", forbidden)
    monkeypatch.delenv(q.RELEASE, raising=False)
    numpy = sys.modules.get("numpy")
    if numpy is not None:
        for name in (
            "rand",
            "randn",
            "random",
            "random_sample",
            "randint",
            "uniform",
            "normal",
            "choice",
            "shuffle",
            "permutation",
            "seed",
            "default_rng",
        ):
            if hasattr(numpy.random, name):
                monkeypatch.setattr(numpy.random, name, forbidden)
    sys.settrace(trace)
    try:
        yield attempts
    finally:
        sys.meta_path.remove(finder)
        intact_trace = sys.gettrace() is trace
        intact_profile = sys.getprofile() is previous_profile
        sys.settrace(previous_trace)
        sys.setprofile(previous_profile)
        write(
            tmp_path / "parameter-blocked.json",
            dict(
                nodeid=request.node.nodeid,
                attempts=attempts,
                trace_intact=intact_trace,
                profile_intact=intact_profile,
                trace_restored=sys.gettrace() is previous_trace,
                profile_restored=sys.getprofile() is previous_profile,
                actual_parameter_native_dispatch_entries=0,
                guard_scope=(
                    "native imports/body, Cells numerical bodies, Python RNG and "
                    "public NumPy draw APIs; only metadata helpers exercised"
                ),
                body_and_final_teardown_required=True,
            ),
        )
        assert attempts == []
        assert intact_trace and intact_profile
        assert sys.gettrace() is previous_trace and sys.getprofile() is previous_profile


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "BASE", tmp_path)
    root = tmp_path / "original-inputs"
    (root / "extra_configs").mkdir(parents=True)
    files = {}
    for name in q.RAW_FILES:
        source = q.NATIVE / "betse/data/yaml" / name
        path = root / name
        path.write_bytes(source.read_bytes())
        path.chmod(0o444)
        files[name] = dict(input=q.ref(path))
    values = (
        ("init_pickle_dirname", str(root / "INITS")),
        ("sim_pickle_dirname", str(root / "SIMS")),
        ("init_pickle_filename", str(root / "INITS/init_1.betse.gz")),
        ("seed_pickle_filename", str(root / "INITS/world_1.betse.gz")),
        ("sim_pickle_filename", str(root / "SIMS/sim_1.betse.gz")),
        ("init_export_dirname", str(root / "RESULTS/init_1")),
        ("sim_export_dirname", str(root / "RESULTS/sim_1")),
        ("grn_config_filename", str(root / "extra_configs/grn_basic.yaml")),
        ("grn_pickle_dirname", str(root / "RESULTS/GRN")),
        ("grn_pickle_filename", str(root / "RESULTS/GRN/GRN_1.betse.gz")),
        ("grn_unpickle_filename", None),
    )
    value = dict(files=files, ordered_path_permission=values)
    path = tmp_path / "input-manifest.json"
    q.snapshot.write_json(path, value)
    return path, value


def test_original_raw_inputs_are_permissions_not_parsed_owners(inputs):
    path, _ = inputs
    program = q.input_program(path, q.ref(path)["sha256"])
    assert program["files"]["sim_config.yaml"]["sha256"] == q.RAW_FILES["sim_config.yaml"]
    assert len(program["path_permission"]) == 11
    assert len(program["directories"]) == 5
    assert all(not Path(p).exists() for p in program["directories"])
    assert not hasattr(program, "parameters")


def test_saved_raw_program_round_trip_revalidates_without_parsing(inputs, tmp_path):
    path, _ = inputs
    program = q.input_program(path, q.ref(path)["sha256"])
    saved = tmp_path / "program.json"
    q.snapshot.write_json(saved, program)
    assert q.read(saved) == program
    assert q.input_program(path, q.ref(path)["sha256"]) == q.read(saved)


def test_runtime_declaration_reads_real_providers_without_import_or_path_mutation():
    before = tuple(sys.path)
    modules = {n: sys.modules.get(n) for n, _, _ in q.RUNTIME_PROVIDERS}
    plan = q.runtime_plan()
    assert plan["entry"] == str(q.DEFAULT_PYTHON)
    assert plan["primary_site"] == str(q.RETAINED_SITE)
    assert plan["appended_site"] == str(q.CPU_SITE)
    assert plan["providers"]["numpy"]["site"] == str(q.RETAINED_SITE)
    assert plan["providers"]["matplotlib"]["site"] == str(q.RETAINED_SITE)
    assert plan["providers"]["jax"]["site"] == str(q.CPU_SITE)
    assert not plan["actual_library_import"] and plan["unchanged_shared_runtime"]
    assert tuple(sys.path) == before
    assert all(sys.modules.get(name) is module for name, module in modules.items())
    with pytest.raises(ValueError, match="Retained BETSE"):
        q.runtime_plan(q.BASE / "venv-cpu/bin/python")


@pytest.mark.parametrize(
    "drift", ["none", "shadow", "duplicate", "provider", "plan", "prefix", "executable"]
)
def test_runtime_entry_preserves_origins_and_explicit_dependency_precedence(
    tmp_path, monkeypatch, drift
):
    primary, extra = str(tmp_path / "retained"), str(tmp_path / "cpu")
    name = "closed_software_runtime_probe"
    module = ModuleType(name)
    module.__file__ = str(tmp_path / "retained/probe/__init__.py")
    declared = dict(
        entry="/software/runtime/metadata-only",
        prefix=sys.prefix,
        executable=q.ref(Path(sys.executable).resolve()),
        primary_site=primary,
        appended_site=extra,
        providers={name: dict(files=[dict(path=module.__file__)])},
    )
    expected = copy.deepcopy(declared)
    monkeypatch.setattr(q, "runtime_plan", lambda entry: copy.deepcopy(expected))
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys, "path", [primary])
    if drift == "shadow":
        sys.path.insert(0, extra)
    elif drift == "duplicate":
        sys.path.extend((extra, extra))
    elif drift == "provider":
        module.__file__ = str(tmp_path / "foreign/probe/__init__.py")
    elif drift == "plan":
        declared["appended_site"] = str(tmp_path / "undeclared")
    elif drift == "prefix":
        monkeypatch.setattr(sys, "prefix", "/wrong/prefix")
    elif drift == "executable":
        monkeypatch.setattr(sys, "executable", str(Path(q.__file__).resolve()))
    before = tuple(sys.path)
    if drift == "none":
        assert q._runtime_entry(declared) is declared
        assert sys.path == [primary, extra]
        assert q._runtime_entry(declared) is declared  # No duplicate activation.
        assert sys.path == [primary, extra]
    else:
        with pytest.raises(ValueError):
            q._runtime_entry(declared)
        assert tuple(sys.path) == before


@pytest.mark.parametrize("drift", ["hash", "mode", "relative", "order", "extra"])
def test_input_program_refuses_changed_or_foreign_authority(inputs, drift):
    path, original = inputs
    value = copy.deepcopy(original)
    main = Path(value["files"]["sim_config.yaml"]["input"]["path"])
    if drift == "hash":
        main.chmod(0o644)
        main.write_bytes(main.read_bytes() + b"\n# changed\n")
        main.chmod(0o444)
        value["files"]["sim_config.yaml"]["input"] = q.ref(main)
    elif drift == "mode":
        main.chmod(0o644)
    elif drift == "relative":
        value["ordered_path_permission"] = (
            ("init_pickle_dirname", "INITS"),
            *value["ordered_path_permission"][1:],
        )
    elif drift == "order":
        value["ordered_path_permission"] = tuple(reversed(value["ordered_path_permission"]))
    else:
        value["files"]["extra.yaml"] = value["files"]["sim_config.yaml"]
    changed = path.with_name("changed.json")
    q.snapshot.write_json(changed, value)
    with pytest.raises(ValueError):
        q.input_program(changed, q.ref(changed)["sha256"])


@pytest.mark.parametrize("entry", [q.start, q.worker, q.acquire_world_ready])
@pytest.mark.parametrize("enabled", [False, True, 1])
def test_unreleased_entry_never_creates_output_or_reads_packet(
    tmp_path, monkeypatch, entry, enabled
):
    called = []
    monkeypatch.setattr(q, "packet_inputs", lambda *args: called.append(True))
    output = tmp_path / "untouched"
    with pytest.raises(ValueError, match="held"):
        entry(tmp_path / "packet", output, packet_sha256="0" * 64, enabled=enabled)
    assert not output.exists() and called == []


@pytest.mark.parametrize("route", ["direct", "symlink", "ancestor"])
def test_released_output_containment_refuses_before_any_process(tmp_path, monkeypatch, route):
    monkeypatch.setattr(q, "BASE", tmp_path)
    monkeypatch.setenv(q.RELEASE, "1")
    packet = tmp_path / "packet"
    packet.mkdir()
    output = packet / "bad"
    if route == "symlink":
        link = tmp_path / "linked"
        link.symlink_to(packet, target_is_directory=True)
        output = link / "bad"
    elif route == "ancestor":
        output = tmp_path
    monkeypatch.setattr(
        q, "packet_inputs", lambda *args: dict(program=dict(root=str(tmp_path / "inputs")))
    )
    calls = []
    monkeypatch.setattr(q.resources, "run_bounded", lambda *a, **k: calls.append(True))
    with pytest.raises(ValueError):
        q.start(packet, output, packet_sha256="0" * 64, enabled=True)
    assert not (packet / "bad").exists() and calls == []


def test_safe_sibling_launch_contract_is_bounded_and_does_not_spawn(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "BASE", tmp_path)
    monkeypatch.setenv(q.RELEASE, "1")
    packet = tmp_path / "packet"
    packet.mkdir()
    declared = dict(
        program=dict(root=str(tmp_path / "inputs")), runtime=dict(entry="/explicit/python")
    )
    monkeypatch.setattr(q, "packet_inputs", lambda *args: declared)
    calls = []

    def record(command, **kwargs):
        calls.append((command, kwargs))
        return dict(status="not-executed-software-spy")

    monkeypatch.setattr(q.resources, "run_bounded", record)
    output = tmp_path / "sibling"
    result = q.start(packet, output, packet_sha256="a" * 64, enabled=True)
    command, options = calls[0]
    assert result["status"] == "not-executed-software-spy" and len(calls) == 1
    assert command[:3] == ["taskset", "-c", "0"]
    assert "--worker" in command and "--enabled" in command
    assert options["timeout"] == 480 and options["max_rss_bytes"] == 2**30
    assert options["min_available_bytes"] == 8 * 2**30
    assert options["env"][q.RELEASE] == "1"
    assert all(options["env"][name] == "1" for name in q.GATES)
    assert options["env"]["OMP_NUM_THREADS"] == "1"
    assert options["env"]["MPLCONFIGDIR"].startswith(str(output / "worker"))
    assert not (output / "worker").exists()


def test_take_forwards_exact_live_metadata_object_and_refuses_collision(tmp_path):
    value = object()  # Metadata identity probe, never a native owner.
    calls, journal = [], []

    def operation():
        calls.append(True)
        return value

    def observe(returned, primary):
        assert returned is value and primary is None
        return dict(returned_identity=id(value), metadata_only=True), {}, {}

    returned = q.take(tmp_path, "metadata", operation, observe, journal)
    assert returned is value and journal[0]["evidence_complete"] and calls == [True]
    with pytest.raises(FileExistsError):
        q.take(tmp_path, "metadata", operation, observe, [])
    assert calls == [True]


@pytest.mark.parametrize("failure", ["observer", "archive", "outcome", "primary-and-outcome"])
def test_primary_and_cause_survive_secondary_evidence_failures(tmp_path, monkeypatch, failure):
    primary = RuntimeError("primary source-shaped refusal")
    cause = LookupError("retained cause")
    primary.__cause__ = cause
    original_write = q.snapshot.write_json

    def operation():
        raise primary

    def observe(returned, error):
        assert returned is None and error is primary
        if failure == "observer":
            raise TypeError("secondary observation")
        return dict(error=q.error_record(error)), {}, {}

    def write(path, value):
        if path.name == "outcome.json" or (
            failure == "primary-and-outcome" and path.name == "primary.json"
        ):
            raise OSError("secondary I/O")
        return original_write(path, value)

    if failure in ("outcome", "primary-and-outcome"):
        monkeypatch.setattr(q.snapshot, "write_json", write)
    if failure == "archive":
        monkeypatch.setattr(
            q, "archive", lambda *a, **k: (_ for _ in ()).throw(OSError("archive I/O"))
        )
    journal = []
    with pytest.raises(RuntimeError) as caught:
        q.take(tmp_path, "failure", operation, observe, journal)
    assert caught.value is primary and caught.value.__cause__ is cause
    assert primary.parameter_diagnostic is journal[0]
    assert journal[0]["primary"]["identity"] == id(primary) and journal[0]["errors"]
    assert journal[0]["evidence_complete"] is False


def test_successful_return_with_incomplete_evidence_is_refused(tmp_path):
    value, journal = object(), []

    def incomplete(value, primary):
        raise TypeError("unsupported evidence")

    with pytest.raises(q.ObservationRejected) as caught:
        q.take(tmp_path, "returned", lambda: value, incomplete, journal)
    assert caught.value.parameter_diagnostic["returned_identity"] == id(value)
    assert journal[0]["returned"] and not journal[0]["evidence_complete"]


def test_closed_observation_keeps_aliases_and_scalar_bits(tmp_path):
    shared = [1, -0.0]
    payload = dict(first=shared, second=shared)
    row = q.archive(tmp_path / "graph", payload)
    assert q.bound(row).is_file()
    codec = q._codec()
    assert codec is evidence_codec
    value = codec.decode(
        json.loads((tmp_path / "graph/state.json").read_text()),
        (tmp_path / "graph/arrays.npz").read_bytes(),
    )
    assert value["first"] is value["second"]
    assert struct.pack(">d", value["first"][1]) == struct.pack(">d", -0.0)


@pytest.fixture
def metadata_module(tmp_path):
    path = tmp_path / "metadata.py"
    path.write_text("def probe(x):\n    return ((3, -0.0), x)\n")
    module = ModuleType("declared_metadata")
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), vars(module))
    return module


@pytest.mark.parametrize(
    "drift", ["none", "typed-constant", "signed-bit", "cached-builtins", "globals"]
)
def test_public_code_guard_is_typed_and_uses_cached_builtins(metadata_module, drift):
    module = metadata_module
    original = module.probe
    if drift in ("typed-constant", "signed-bit"):
        values = list(original.__code__.co_consts)
        pair = next(i for i, value in enumerate(values) if type(value) is tuple)
        values[pair] = (complex(3, 0), -0.0) if drift == "typed-constant" else (3, 0.0)
        original.__code__ = original.__code__.replace(co_consts=tuple(values))
    elif drift == "cached-builtins":
        foreign = dict(vars(builtins))
        vars(module)["__builtins__"] = foreign
        module.probe = FunctionType(original.__code__, vars(module))
        vars(module)["__builtins__"] = vars(builtins)
    elif drift == "globals":
        module.probe = FunctionType(original.__code__, dict(vars(module)))
    if drift == "none":
        assert q._function(module, "probe") is original
    else:
        with pytest.raises(ValueError):
            q._function(module, "probe")


@pytest.mark.parametrize(
    "event,inside", [("open", True), ("open", False), ("os.mkdir", True), ("os.mkdir", False)]
)
def test_write_permission_has_no_native_pickle_or_shared_filesystem_escape(tmp_path, event, inside):
    output = tmp_path / "output"
    output.mkdir()
    native = tmp_path / "original-directory"
    policy = q.WritePolicy(output, (str(native),))
    path = output / "evidence" if inside else tmp_path / "outside"
    args = (str(path), "w", 65) if event == "open" else (str(path), 0o777, -1)
    if inside:
        policy.audit(event, args)
    else:
        with pytest.raises(ValueError, match="permission"):
            policy.audit(event, args)
    policy.audit("os.mkdir", (str(native), 0o777, -1))
    with pytest.raises(ValueError):
        policy.audit("open", (str(native / "not-a-pickle"), "w", 65))
    assert not path.exists() and not native.exists()


def test_no_callback_or_phase_call_is_part_of_parameter_dispatch():
    assert set(q.MODULES) == {
        "parameters",
        "yaml",
        "paths",
        "seven",
        "numeric",
        "events",
        "boundary",
        "network",
        "grn",
        "modulators",
        "colormaps",
        "state",
        "colormap_load",
        "constants",
        "remainder",
    }
    assert q.MAX_STEPS >= 29
    assert all("WPC" not in name and "WORLD_CONSTRUCTION" not in name for name in q.GATES)


def test_observer_accepts_only_the_actual_issued_file_declaration(tmp_path, monkeypatch):
    from cells.processes import betse_native_parameter_yaml_prefix as files

    monkeypatch.setattr(files, "BASE", tmp_path)
    path = tmp_path / "file-only.yaml"
    path.write_bytes(b"# unparsed software-only file\n")
    path.chmod(0o444)
    value = files.input_file(path, sha256=q.ref(path)["sha256"], origin="software file observation")
    journal = []
    observe = q._observer({"yaml": files}, "yaml", "FileInput", dict(p=None))
    returned = q.take(tmp_path, "actual-file-declaration", lambda: value, observe, journal)
    assert returned is value and journal[0]["evidence_complete"]
    with pytest.raises(ValueError, match="return type"):
        observe({"filename": str(path)}, None)


def test_import_primary_survives_inventory_failure(tmp_path, monkeypatch):
    from validation.betse import betse_normal_channel_join_runtime as runtime

    packet, output = tmp_path / "packet", tmp_path / "output"
    packet.mkdir()
    (packet / "inputs.json").write_text("{}")
    output.mkdir()
    (output / "evidence").mkdir()
    primary, cause = ImportError("synthetic source import"), LookupError("original cause")
    primary.__cause__ = cause
    assert recording.Calls is not None

    def refused(*args, **kwargs):
        raise primary

    monkeypatch.setattr(q, "acquire_world_ready", refused)
    monkeypatch.setattr(
        runtime, "inventory", lambda: (_ for _ in ()).throw(OSError("inventory I/O"))
    )
    with pytest.raises(ImportError) as caught:
        q._worker_body(packet, output, {}, q.WritePolicy(output, ()))
    assert caught.value is primary and caught.value.__cause__ is cause
    failure = json.loads((output / "failure.json").read_text())
    assert failure["primary"]["identity"] == id(primary)
    assert failure["recovery_errors"] and failure["actual_world_ready_returned"] is False
    assert not (output / "result.json").exists()


def test_in_process_acquisition_retains_import_failure_without_downstream_work(
    tmp_path, monkeypatch
):
    packet, directory = tmp_path / "packet", tmp_path / "entry"
    packet.mkdir()
    primary, cause = ImportError("source-shaped module refusal"), LookupError("original cause")
    primary.__cause__ = cause
    monkeypatch.setattr(q, "BASE", tmp_path)
    monkeypatch.setattr(
        q, "_entry", lambda *args: (packet, dict(program=dict(root=str(tmp_path / "inputs"))))
    )
    calls = []

    def import_failure(*args):
        calls.append("module-import")
        raise primary

    monkeypatch.setattr(q, "_modules", import_failure)
    with pytest.raises(ImportError) as caught:
        q.acquire_world_ready(packet, directory, packet_sha256="0" * 64, enabled=True)
    assert caught.value is primary and caught.value.__cause__ is cause
    assert calls == ["module-import"] and primary.parameter_acquisition["operations"] == []
    failure = json.loads((directory / "failure.json").read_text())
    assert failure["primary"]["identity"] == id(primary)
    assert failure["operations"] == [] and failure["source_or_evidence_incomplete"]
    assert not (directory / "acquisition.json").exists()


@pytest.mark.parametrize("result_kind", ["object", "none", "unwind", "entry"])
def test_installed_profiler_failure_stops_before_following_public_operation(
    tmp_path, monkeypatch, result_kind
):
    """Actual installed profiler around synthetic functions, never a native body."""
    from validation.betse import betse_normal_channel_join_runtime as runtime

    packet, output = tmp_path / "packet", tmp_path / "output"
    packet.mkdir()
    (packet / "inputs.json").write_text("{}")
    output.mkdir()
    evidence = output / "synthetic-operations"
    evidence.mkdir()
    primary, cause = RuntimeError("original operation refusal"), LookupError("original cause")
    primary.__cause__ = cause
    secondary = OSError("synthetic recorder I/O failure")
    value, operations, journal, target = object(), [], [], []
    old_emit = recording.Calls.emit

    def prepare():
        operations.append("first")
        if result_kind == "unwind":
            raise primary
        return None if result_kind == "none" else value

    # A metadata-only function name/module reaches the existing accounting
    # classification. It has no original/Cells numerical code or owner state.
    operation = FunctionType(
        prepare.__code__,
        dict(prepare.__globals__, __name__="cells.software_only_work_probe"),
        prepare.__name__,
        prepare.__defaults__,
        prepare.__closure__,
    )

    def emit(observer, row):
        if row.get("function") == "cells.software_only_work_probe.prepare":
            target.append(row["invocation"])
            if result_kind == "entry":
                raise secondary
        if row.get("event") == "exit" and row.get("invocation") in target:
            raise secondary
        return old_emit(observer, row)

    def observe(returned, error):
        return (
            dict(
                returned_identity=id(returned),
                primary_identity=id(error) if error is not None else None,
                synthetic_observer_control=True,
            ),
            {},
            {},
        )

    def acquire(*args, **kwargs):
        try:
            q.take(evidence, "first", operation, observe, journal)
            # This second delegate must never run after a failed first record.
            q.take(evidence, "second", lambda: operations.append("second"), observe, journal)
            raise AssertionError("Unexpected successful synthetic acquisition")
        except BaseException as error:
            if result_kind != "entry":
                with pytest.raises(q.ObservationRejected, match="before another operation"):
                    q.take(
                        evidence,
                        "after-caught-failure",
                        lambda: operations.append("later"),
                        observe,
                        journal,
                    )
            error.parameter_acquisition = dict(operations=journal, capture_errors=[])
            raise

    monkeypatch.setattr(recording.Calls, "emit", emit)
    monkeypatch.setattr(q, "acquire_world_ready", acquire)
    monkeypatch.setattr(runtime, "inventory", lambda: dict(scope="synthetic local failure control"))
    expected = (
        RuntimeError
        if result_kind == "unwind"
        else (OSError if result_kind == "entry" else q.ObservationRejected)
    )
    with pytest.raises(expected) as caught:
        q._worker_body(packet, output, {}, q.WritePolicy(output, ()))
    assert target and operations == ([] if result_kind == "entry" else ["first"])
    assert len(journal) == 1
    # Entry rejection is an exactly captured primary with no returned value.
    # Deferred return loss is separately incomplete work evidence.
    assert journal[0]["evidence_complete"] is (result_kind == "entry")
    assert not (evidence / "01-second").exists()
    assert not (evidence / "01-after-caught-failure").exists()
    if result_kind == "unwind":
        assert caught.value is primary and caught.value.__cause__ is cause
        witness = primary.parameter_work_observation[3][0]
        assert witness[1] == "return" and witness[2] is None and witness[3] is secondary
    elif result_kind == "entry":
        assert caught.value is secondary
    else:
        assert caught.value.parameter_live_return is (None if result_kind == "none" else value)
        witness = caught.value.parameter_work_observation[3][0]
        assert witness[2] is (None if result_kind == "none" else value)
    failure = json.loads((output / "failure.json").read_text())
    assert failure["succeeded"] is False and failure["primary"]["identity"] == id(caught.value)
    assert not (output / "result.json").exists()
    assert q._WORK_OBSERVER.get() is None
