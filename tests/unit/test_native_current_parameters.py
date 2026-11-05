"""Metadata acquisition controls; no real Parameters, INIT or SIM is constructed."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from validation.betse import betse_native_parameter_world_ready_qualification as q
from validation.betse import native_current_parameters_software as software


@pytest.fixture(autouse=True)
def blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "_ACQUISITIONS", {})
    monkeypatch.setattr(q, "_ACQUISITION_PACKETS", {})
    monkeypatch.setattr(q, "_ACQUISITION_ACTIVE", [])
    monkeypatch.setattr(q, "_ACQUISITION_ENTRY", None)
    monkeypatch.setattr(q, "_ACQUISITION_FAILURES", [])
    monkeypatch.delenv(q.RELEASE, raising=False)
    with software.blocked(tmp_path):
        yield


class Retired:
    @property
    def parameters(self):
        raise AssertionError("A consumed original owner must never be revalidated")


@pytest.fixture
def model(tmp_path, monkeypatch):
    """Only metadata pair tokens stand in for pipeline returns, never owners."""
    packet, root = tmp_path / "packet", tmp_path / "original-inputs"
    packet.mkdir()
    root.mkdir()
    (packet / "inputs.json").write_text('{"metadata_fixture": true}')
    old, old_p = Retired(), object()
    fresh, fresh_p = Retired(), object()
    program = dict(
        root=str(root),
        directories=[
            str(root / name)
            for name in ("INITS", "SIMS", "RESULTS/init", "RESULTS/sim", "RESULTS/GRN")
        ],
    )
    inputs = dict(program=program, acquisition_sequence=q.CURRENT_LOADS, runtime={})
    state = NS(
        packet=packet,
        root=root,
        inputs=inputs,
        first=(old, old_p),
        second=(fresh, fresh_p),
        calls=[],
        packet_reads=[],
        runtime_reads=[],
        pin=q.snapshot.digest(packet / "inputs.json"),
        output=tmp_path / "first",
        current=tmp_path / "current",
    )

    def pipeline(modules, actual_program, evidence, journal):
        assert actual_program is program
        state.calls.append("pipeline")
        for path in program["directories"]:
            Path(path).mkdir(parents=True, exist_ok=True)
        journal.append(dict(metadata_only=True, operation="synthetic-controller-return"))
        return state.first if len(state.calls) == 1 else state.second

    def packet_inputs(packet, pin, *, directory_epoch=None):
        state.packet_reads.append((packet, pin, directory_epoch))
        assert Path(packet) == state.packet and pin == state.pin
        assert directory_epoch is not None
        q.require(q._directory_epoch(program) == directory_epoch, "Native directory epoch changed")
        return inputs

    monkeypatch.setattr(q, "BASE", tmp_path)
    monkeypatch.setattr(q, "__file__", str(packet / "source" / q.FILE))
    monkeypatch.setattr(q, "_entry", lambda *args: (packet, inputs))
    monkeypatch.setattr(q, "_packet_inputs", packet_inputs)
    monkeypatch.setattr(q, "_modules", lambda *args: {})
    monkeypatch.setattr(q, "_execute", pipeline)
    monkeypatch.setattr(q, "_runtime_entry", lambda value: state.runtime_reads.append(value))
    monkeypatch.setattr(q.os, "sched_getaffinity", lambda pid: {0})
    monkeypatch.setenv(q.RELEASE, "1")
    return state


def first(model):
    result = q.acquire_world_ready(
        model.packet, model.output, packet_sha256=model.pin, enabled=True
    )
    assert result[0] is model.first[0] and result[1] is model.first[1]
    return result


def current(model, **changes):
    arguments = dict(
        packet_sha256=model.pin,
        previous_owner=model.first[0],
        previous_parameters=model.first[1],
        enabled=True,
    )
    arguments.update(changes)
    return q.acquire_current_world_ready(model.packet, model.current, **arguments)


def test_current_parameters_distinct_return_preserves_old_identity_and_real_directory_epoch(model):
    first(model)
    record = q._ACQUISITIONS[id(model.first[0])]
    epoch = record.directory_epoch
    assert {row[0] for row in epoch} == {
        str(model.root),
        str(model.root / "RESULTS"),
        *model.inputs["program"]["directories"],
    }
    # Normal output content/mtime changes are not directory replacement.
    (model.root / "INITS/ordinary-output").write_bytes(b"retained output")
    result = current(model)
    assert result[0] is model.second[0] and result[1] is model.second[1]
    assert record.owner is model.first[0] and record.p is model.first[1]
    assert record.current_owner is result[0] and record.current_p is result[1]
    assert record.attempted and record.published and not record.invalid
    assert q._directory_epoch(model.inputs["program"]) == epoch
    assert model.packet_reads == [(model.packet, model.pin, epoch)]
    assert len(record.initial_journal) == len(record.journal) == 1
    assert len(model.calls) == 2 and q._ACQUISITION_ACTIVE == []
    saved = json.loads((model.current / "acquisition.json").read_text())
    assert saved["actual_p_identity"] == id(model.second[1])
    assert saved["INIT_SIM_or_persisted_owner_admission"] is False
    with pytest.raises(ValueError, match="consumed"):
        current(model)
    assert len(model.calls) == 2


@pytest.mark.parametrize("preexisting", [False, True])
def test_current_parameters_two_load_first_slot_is_exclusive_even_with_existing_directories(
    model, preexisting
):
    if preexisting:
        for path in model.inputs["program"]["directories"]:
            Path(path).mkdir(parents=True, exist_ok=True)
    first(model)
    with pytest.raises(ValueError, match="already consumed"):
        q.acquire_world_ready(model.packet, model.current, packet_sha256=model.pin, enabled=True)
    assert model.calls == ["pipeline"] and not model.current.exists()


@pytest.mark.parametrize("mode", ["absent", "explicit"])
def test_current_parameters_default_one_load_never_grants_reload(model, mode):
    if mode == "absent":
        del model.inputs["acquisition_sequence"]
    else:
        model.inputs["acquisition_sequence"] = q.ONE_LOAD
    first(model)
    assert q._ACQUISITIONS == q._ACQUISITION_PACKETS == {}
    with pytest.raises(ValueError, match="Exact in-process"):
        current(model)
    assert model.calls == ["pipeline"]


@pytest.mark.parametrize("foreign", ["owner", "p", "thread", "process"])
def test_current_parameters_foreign_pair_or_execution_refuses_before_packet_load(
    model, monkeypatch, foreign
):
    first(model)
    record = q._ACQUISITIONS[id(model.first[0])]
    changes = {}
    if foreign == "owner":
        changes["previous_owner"] = Retired()
    elif foreign == "p":
        changes["previous_parameters"] = object()
    elif foreign == "thread":
        monkeypatch.setattr(q, "get_ident", lambda: record.thread + 1)
    else:
        monkeypatch.setattr(q.os, "getpid", lambda: record.process + 1)
    with pytest.raises(ValueError):
        current(model, **changes)
    assert not record.attempted and not model.packet_reads and not model.current.exists()


@pytest.mark.parametrize("place", ["leaf", "parent", "root"])
@pytest.mark.parametrize("change", ["replace", "symlink", "file"])
def test_current_parameters_directory_or_ancestor_replacement_refuses_and_consumes(
    model, place, change
):
    first(model)
    target = {"leaf": model.root / "INITS", "parent": model.root / "RESULTS", "root": model.root}[
        place
    ]
    saved = target.with_name(target.name + "-original")
    target.rename(saved)
    if change == "replace":
        if saved.is_dir():
            import shutil

            shutil.copytree(saved, target)
    elif change == "symlink":
        target.symlink_to(saved, target_is_directory=True)
    else:
        target.write_bytes(b"not a directory")
    with pytest.raises((ValueError, FileNotFoundError, NotADirectoryError)):
        current(model)
    record = q._ACQUISITIONS[id(model.first[0])]
    assert record.attempted and not record.published and model.calls == ["pipeline"]
    with pytest.raises(ValueError, match="consumed"):
        current(model)


@pytest.mark.parametrize("drift", ["packet", "runtime", "module", "source_path", "cpu"])
def test_current_parameters_preflight_failures_remain_consumed_without_delegate(
    model, monkeypatch, drift
):
    first(model)
    primary = ValueError("original preflight failure")
    if drift in ("packet", "runtime", "module"):
        slot = {"packet": "_packet_inputs", "runtime": "_runtime_entry", "module": "_modules"}[
            drift
        ]

        def refuse(*args, **kwargs):
            raise primary

        monkeypatch.setattr(q, slot, refuse)
    elif drift == "source_path":
        monkeypatch.setattr(q, "__file__", str(model.packet / "other.py"))
    else:
        monkeypatch.setattr(q.os, "sched_getaffinity", lambda pid: {4})
    with pytest.raises(ValueError) as error:
        current(model)
    record = q._ACQUISITIONS[id(model.first[0])]
    assert record.attempted and not record.published and model.calls == ["pipeline"]
    assert error.value.parameter_acquisition is record and q._ACQUISITION_ACTIVE == []
    with pytest.raises(ValueError, match="consumed"):
        current(model)


@pytest.mark.parametrize("first_failure", ["pipeline", "epoch", "writer"])
def test_current_parameters_failed_first_load_never_issues_second_slot(
    model, monkeypatch, first_failure
):
    primary = OSError("first load failed")
    primary.__cause__ = LookupError("original cause")
    write = q.snapshot.write_json

    def refuse(*args, **kwargs):
        raise primary

    if first_failure == "pipeline":
        monkeypatch.setattr(q, "_execute", refuse)
    elif first_failure == "epoch":
        monkeypatch.setattr(q, "_directory_epoch", refuse)
    else:

        def writer(path, value):
            if path.name == "acquisition.json":
                raise primary
            return write(path, value)

        monkeypatch.setattr(q.snapshot, "write_json", writer)
    with pytest.raises(OSError) as error:
        first(model)
    assert error.value is primary and isinstance(error.value.__cause__, LookupError)
    assert not q._ACQUISITIONS and q._ACQUISITION_ACTIVE == []
    assert len(q._ACQUISITION_PACKETS) == 1
    with pytest.raises(ValueError, match="already consumed"):
        first(model)
    with pytest.raises(ValueError, match="Exact in-process"):
        current(model)


@pytest.mark.parametrize(
    "failure", ["pipeline", "post_epoch", "writer", "writer_and_failure_writer"]
)
@pytest.mark.parametrize("falsey", [False, True])
def test_current_parameters_failed_second_load_retains_raw_pairs_primary_cause_and_consumption(
    model, monkeypatch, failure, falsey
):
    class Failure(OSError):
        def __bool__(self):
            return not falsey

    first(model)
    primary, cause = Failure("real source or observation primary"), LookupError("original cause")
    primary.__cause__ = cause
    execute, write = q._execute, q.snapshot.write_json

    def pipeline(*args):
        if failure == "pipeline":
            raise primary
        result = execute(*args)
        if failure == "post_epoch":
            (model.root / "INITS").rename(model.root / "INITS-old")
            (model.root / "INITS").mkdir()
        return result

    def writer(path, value):
        if path.name == "acquisition.json" and failure.startswith("writer"):
            raise primary
        if path.name == "failure.json" and failure == "writer_and_failure_writer":
            raise RuntimeError("secondary writer failure")
        return write(path, value)

    monkeypatch.setattr(q, "_execute", pipeline)
    monkeypatch.setattr(q.snapshot, "write_json", writer)
    with pytest.raises((Failure, ValueError)) as error:
        current(model)
    record = q._ACQUISITIONS[id(model.first[0])]
    if failure != "post_epoch":
        assert error.value is primary and error.value.__cause__ is cause
    assert record.source_error is error.value and error.value.parameter_acquisition is record
    assert record.owner is model.first[0] and record.p is model.first[1]
    if failure != "pipeline":
        assert record.current_owner is model.second[0] and record.current_p is model.second[1]
    assert record.attempted and not record.published and q._ACQUISITION_ACTIVE == []
    assert bool(record.capture_errors) is (failure == "writer_and_failure_writer")
    with pytest.raises(ValueError, match="consumed"):
        current(model)


@pytest.mark.parametrize("same", ["owner", "p", "both", "list"])
def test_current_parameters_requires_distinct_exact_actual_return_pair(model, same):
    first(model)
    if same == "owner":
        model.second = (model.first[0], model.second[1])
    elif same == "p":
        model.second = (model.second[0], model.first[1])
    elif same == "both":
        model.second = model.first
    else:
        model.second = list(model.second)
    with pytest.raises(ValueError, match="distinct|Exact fresh"):
        current(model)
    assert not q._ACQUISITIONS[id(model.first[0])].published


@pytest.mark.parametrize("boundary", ["runtime", "module", "pipeline", "writer"])
@pytest.mark.parametrize("route", ["initial", "current"])
def test_current_parameters_caught_reentry_poison_stops_publication(
    model, monkeypatch, boundary, route
):
    first(model)
    target = {"runtime": "_runtime_entry", "module": "_modules", "pipeline": "_execute"}.get(
        boundary
    )
    original = getattr(q, target) if target else q.snapshot.write_json
    entered = []

    def enter():
        entered.append(True)
        with pytest.raises(ValueError, match="Reentrant"):
            if route == "initial":
                q.acquire_world_ready(
                    model.packet, model.output, packet_sha256=model.pin, enabled=True
                )
            else:
                current(model)

    def delegate(*args, **kwargs):
        if boundary != "writer" or args[0].name == "acquisition.json":
            enter()
        return original(*args, **kwargs)

    if target:
        monkeypatch.setattr(q, target, delegate)
    else:
        monkeypatch.setattr(q.snapshot, "write_json", delegate)
    with pytest.raises(ValueError, match="poisons"):
        current(model)
    record = q._ACQUISITIONS[id(model.first[0])]
    assert entered and record.invalid and not record.published and not q._ACQUISITION_ACTIVE
    assert len(model.calls) == (1 if boundary in ("runtime", "module") else 2)


@pytest.mark.parametrize(
    "sequence",
    [
        None,
        True,
        "initial_world_ready",
        ("initial_world_ready", "fresh_current_world_ready", "again"),
        ("fresh_current_world_ready",),
        (True,),
    ],
)
def test_current_parameters_sequence_roster_is_exact(sequence):
    with pytest.raises(ValueError):
        q._acquisition_sequence(dict(acquisition_sequence=sequence))


def test_current_parameters_unreleased_or_unissued_is_not_input_authority(tmp_path, monkeypatch):
    reads = []
    monkeypatch.setattr(q, "_packet_inputs", lambda *args, **kwargs: reads.append(True))
    for enabled in (False, True):
        with pytest.raises(ValueError, match="held"):
            q.acquire_current_world_ready(
                tmp_path,
                tmp_path / "out",
                packet_sha256="0" * 64,
                previous_owner=Retired(),
                previous_parameters=object(),
                enabled=enabled,
            )
    assert not reads and not (tmp_path / "out").exists()


def test_current_parameters_take_refuses_poison_before_next_public_operation(tmp_path, monkeypatch):
    record = NS(invalid=True)
    monkeypatch.setattr(q, "_ACQUISITION_ACTIVE", [record])
    reached = []
    with pytest.raises(ValueError, match="poisons"):
        q.take(tmp_path, "must-not-run", lambda: reached.append(True), lambda *args: None, [])
    assert reached == [] and not (tmp_path / "00-must-not-run").exists()


@pytest.mark.parametrize(
    "boundary", ["initial_preflight", "current_preflight", "initial_return", "current_return"]
)
def test_current_parameters_return_observer_reentry_is_reserved_before_helpers(
    model, monkeypatch, boundary
):
    if boundary.startswith("current"):
        first(model)
    target = {
        "initial_preflight": q._entry,
        "current_preflight": q._packet_inputs,
        "initial_return": q._acquire_world_ready,
        "current_return": q._acquire_current_world_ready,
    }[boundary]
    previous = sys.getprofile()
    errors = []

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if frame.f_code is target.__code__ and event == "return":
            try:
                if boundary.startswith("initial"):
                    first(model)
                else:
                    current(model)
            except ValueError as error:
                errors.append(error)

    sys.setprofile(profile)
    try:
        with pytest.raises(ValueError, match="poisons"):
            current(model) if boundary.startswith("current") else first(model)
    finally:
        sys.setprofile(previous)
    assert len(errors) == 1 and "Reentrant" in str(errors[0])
    assert q._ACQUISITION_ENTRY is None and q._ACQUISITION_ACTIVE == []
    assert (
        len(model.calls)
        == {
            "initial_preflight": 0,
            "current_preflight": 1,
            "initial_return": 1,
            "current_return": 2,
        }[boundary]
    )
    for record in q._ACQUISITIONS.values():
        assert record.invalid and not record.published


@pytest.fixture
def packet_metadata(tmp_path, monkeypatch):
    """Real immutable input bytes; snapshot/runtime readers are declared metadata adapters."""
    root, packet = tmp_path / "raw", tmp_path / "packet"
    (root / "extra_configs").mkdir(parents=True)
    (packet / "source").mkdir(parents=True)
    monkeypatch.setattr(q, "BASE", tmp_path)
    files = {}
    for name in q.RAW_FILES:
        path = root / name
        path.write_bytes((q.NATIVE / "betse/data/yaml" / name).read_bytes())
        path.chmod(0o444)
        files[name] = dict(input=q.ref(path))
    names = (
        ("init_pickle_dirname", "INITS"),
        ("sim_pickle_dirname", "SIMS"),
        ("init_pickle_filename", "INITS/init_1.betse.gz"),
        ("seed_pickle_filename", "INITS/world_1.betse.gz"),
        ("sim_pickle_filename", "SIMS/sim_1.betse.gz"),
        ("init_export_dirname", "RESULTS/init_1"),
        ("sim_export_dirname", "RESULTS/sim_1"),
        ("grn_config_filename", "extra_configs/grn_basic.yaml"),
        ("grn_pickle_dirname", "RESULTS/GRN"),
        ("grn_pickle_filename", "RESULTS/GRN/GRN_1.betse.gz"),
        ("grn_unpickle_filename", None),
    )
    program_path = tmp_path / "program.json"
    q.snapshot.write_json(
        program_path,
        dict(
            files=files,
            ordered_path_permission=[
                (name, None if value is None else str(root / value)) for name, value in names
            ],
        ),
    )
    program = q.input_program(program_path, q.snapshot.digest(program_path))
    review = tmp_path / "review.json"
    review.write_text('{"metadata_fixture": true}')
    monkeypatch.setattr(q, "SOURCE_REVIEW_SHA256", q.snapshot.digest(review))
    runtime = dict(entry="metadata-only-runtime")
    rows = {
        alias: dict(
            module="cells.processes." + name,
            file="src/cells/processes/" + name + ".py",
            sha256="1" * 64,
        )
        for alias, name in q.MODULES.items()
    }
    manifest = dict(files={row["file"]: dict(sha256=row["sha256"]) for row in rows.values()})
    monkeypatch.setattr(q.snapshot, "verify", lambda *args, **kwargs: manifest)
    monkeypatch.setattr(q, "runtime_plan", lambda *args: dict(runtime))
    inputs = dict(
        kind=q.KIND,
        held=True,
        resources=q.POLICY,
        source_modules=rows,
        source_snapshot=dict(sha256="2" * 64),
        source_review=q.ref(review),
        program=program,
        initial_directory_state=q.directory_state(program),
        runtime=dict(runtime),
        acquisition_sequence=q.CURRENT_LOADS,
    )
    q.snapshot.write_json(packet / "inputs.json", inputs)
    return NS(
        packet=packet,
        inputs=inputs,
        root=root,
        program=program,
        pin=q.snapshot.digest(packet / "inputs.json"),
        manifest=manifest,
        runtime=runtime,
    )


def test_current_parameters_initial_packet_never_accepts_post_load_epoch_implicitly(
    packet_metadata,
):
    model = packet_metadata
    assert q.packet_inputs(model.packet, model.pin)["program"] == model.program
    for path in model.program["directories"]:
        Path(path).mkdir(parents=True, exist_ok=True)
    epoch = q._directory_epoch(model.program)
    with pytest.raises(ValueError, match="Initial native directory epoch changed"):
        q.packet_inputs(model.packet, model.pin)
    loaded = q._packet_inputs(model.packet, model.pin, directory_epoch=epoch)
    assert loaded["program"] == model.program
    assert loaded["initial_directory_state"] == [
        list(row) for row in model.inputs["initial_directory_state"]
    ]
    assert q.snapshot.digest(model.packet / "inputs.json") == model.pin


@pytest.mark.parametrize(
    "drift", ["input_bits", "input_writable", "review", "runtime", "module_pin", "packet"]
)
def test_current_parameters_retained_epoch_does_not_relax_other_packet_checks(
    packet_metadata, drift
):
    model = packet_metadata
    for path in model.program["directories"]:
        Path(path).mkdir(parents=True, exist_ok=True)
    epoch = q._directory_epoch(model.program)
    if drift.startswith("input"):
        path = model.root / "sim_config.yaml"
        path.chmod(0o644)
        if drift == "input_bits":
            path.write_bytes(path.read_bytes() + b"\n# changed\n")
            path.chmod(0o444)
    elif drift == "review":
        Path(model.inputs["source_review"]["path"]).write_text("changed")
    elif drift == "runtime":
        model.runtime["entry"] = "other-runtime"
    elif drift == "module_pin":
        next(iter(model.manifest["files"].values()))["sha256"] = "3" * 64
    else:
        (model.packet / "inputs.json").write_text("{}")
    with pytest.raises(ValueError):
        q._packet_inputs(model.packet, model.pin, directory_epoch=epoch)


@pytest.mark.parametrize("load", ["first", "current"])
@pytest.mark.parametrize("falsey", [False, True])
@pytest.mark.parametrize("boundary", ["pop_call", "pop_return", "failure_append"])
def test_current_parameters_cleanup_hook_failure_preserves_original_unwind(
    model, monkeypatch, load, falsey, boundary
):
    class Failure(ValueError):
        def __bool__(self):
            return not falsey

    if load == "current":
        first(model)
    primary, cause = Failure("original source error"), LookupError("original cause")
    primary.__cause__ = cause
    cleanup = OSError("inherited observer rejected metadata cleanup")

    def fail(*args, **kwargs):
        raise primary

    monkeypatch.setattr(q, "_execute", fail)
    previous = sys.getprofile()
    reached = []

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        method = getattr(arg, "__name__", None)
        receiver = getattr(arg, "__self__", None)
        selected = (
            boundary == "failure_append"
            and event == "c_call"
            and method == "append"
            and receiver is q._ACQUISITION_FAILURES
        ) or (
            boundary.startswith("pop")
            and event == ("c_call" if boundary == "pop_call" else "c_return")
            and method == "pop"
            and receiver is q._ACQUISITION_ACTIVE
        )
        if selected:
            reached.append(True)
            raise cleanup

    sys.setprofile(profile)
    try:
        with pytest.raises(Failure) as error:
            first(model) if load == "first" else current(model)
    finally:
        sys.setprofile(previous)
    assert reached == [True]
    assert error.value is primary and error.value.__cause__ is cause
    record = q._ACQUISITION_PACKETS[(str(model.packet), model.pin)]
    assert record.source_error is primary and record.invalid and not record.published
    assert not q._ACQUISITION_ACTIVE and q._ACQUISITION_ENTRY is None
    if boundary == "failure_append":
        assert primary.parameter_acquisition_entry[3] == (cleanup,)
    else:
        assert record.cleanup_errors == (cleanup,)


@pytest.mark.parametrize("load", ["first", "current"])
@pytest.mark.parametrize("event", ["c_call", "c_return"])
def test_current_parameters_cleanup_rejection_prevents_successful_publication(model, load, event):
    if load == "current":
        first(model)
    previous = sys.getprofile()
    cleanup = OSError("successful load cleanup rejected")
    reached = []

    def profile(frame, kind, arg):
        if previous is not None:
            previous(frame, kind, arg)
        if (
            kind == event
            and getattr(arg, "__name__", None) == "pop"
            and getattr(arg, "__self__", None) is q._ACQUISITION_ACTIVE
        ):
            reached.append(True)
            raise cleanup

    sys.setprofile(profile)
    try:
        with pytest.raises(OSError) as error:
            first(model) if load == "first" else current(model)
    finally:
        sys.setprofile(previous)
    assert reached == [True] and error.value is cleanup
    record = q._ACQUISITION_PACKETS[(str(model.packet), model.pin)]
    assert record.cleanup_errors == (cleanup,) and record.invalid and not record.published
    assert record.owner is model.first[0] and record.p is model.first[1]
    if load == "current":
        assert record.current_owner is model.second[0] and record.current_p is model.second[1]
    assert q._ACQUISITION_ENTRY is None and q._ACQUISITION_ACTIVE == []
