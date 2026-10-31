"""Synthetic orchestration controls; actual owners/native/RNG entry forbidden."""

import importlib.abc
import io
import json
import struct
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from validation.betse import betse_normal_ecm_molecule_handoff_run as runner
from validation.betse import betse_normal_ecm_molecule_handoff_run_plugin as plugin


@pytest.fixture(autouse=True)
def no_science(monkeypatch, tmp_path):
    attempted = []

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"cells", "betse", "numpy", "jax", "jaxlib"}:
                attempted.append(fullname)
                raise AssertionError("Actual scientific imports forbidden: " + fullname)
            return None

    guard = Guard()
    sys.meta_path.insert(0, guard)
    monkeypatch.delenv(runner.handoff.RELEASE_ENV, raising=False)
    yield
    sys.meta_path.remove(guard)
    (tmp_path / "software-control.json").write_text(
        json.dumps(
            dict(
                synthetic_only=True,
                actual_scientific_import_attempts=attempted,
                actual_setup_RNG_timestep_calls=0,
                parent_admission=False,
                scientific_acceptance=False,
            )
        )
    )
    assert attempted == []


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    runner.snapshot.write_json(path, value)


def raw_node(value):
    if type(value) is dict:
        return dict(mapping=[[key, raw_node(item)] for key, item in value.items()])
    if type(value) is list:
        return dict(sequence=[raw_node(item) for item in value])
    if type(value) is float:
        return dict(float64_bits=struct.pack("<d", value).hex())
    return value


def raw_archive(path, value, arrays=None):
    path.mkdir(parents=True)
    write(path / "data.json", raw_node(value))
    with zipfile.ZipFile(path / "arrays.npz", "x") as archive:
        for name, data in (arrays or {}).items():
            archive.writestr(name, data)
    write(
        path / "manifest.json",
        dict(
            kind="cells.betse_normal_current_raw_evidence@1",
            complete=True,
            files={
                name: runner.snapshot.digest(path / name) for name in ("data.json", "arrays.npz")
            },
        ),
    )


def basis(tmp_path, monkeypatch):
    """Tiny synthetic Git/evidence input; it represents no admitted owner."""
    repo = tmp_path / "repo"
    repo.mkdir()
    files = {
        *runner.OWNED,
        *runner.READERS,
        *(node.split("::")[0] for node in runner.TARGETS.values()),
        "src/cells/dummy.py",
        "validation/betse/original_fixtures.py",
    }
    for name in files:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Synthetic software source, no executable owner\n")
    for args in (
        ["init", "-q"],
        ["add", "."],
        [
            "-c",
            "user.name=Software Control",
            "-c",
            "user.email=software-control@example.invalid",
            "commit",
            "-q",
            "-m",
            "synthetic source",
        ],
    ):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, timeout=30)
    source = tmp_path / "baseline-source"
    runner.snapshot.freeze(repo, source, {name: name for name in files})
    grid = dict(
        geometry=dict(cell_volume_m3=[1.0]),
        world=dict(grid_size=1.0),
        current_definition=dict(geometry=dict(owner=[0]), ions=dict(ids=["Na"])),
    )
    text = json.dumps(grid, sort_keys=True, separators=(",", ":"))
    complete = dict(
        identity="synthetic-complete",
        binding=dict(
            identity="synthetic-INIT",
            inputs_raw=dict(field=dict(definition=dict(environment_geometry_definition=grid))),
            material_binding=dict(geometry_binding=dict(definition_json=text)),
        ),
        parent=dict(identity="synthetic-parent"),
    )
    component = dict(
        identity="synthetic-SIM",
        expected_init_identity="synthetic-INIT",
        inputs=dict(
            sim_phase=dict(field=dict(definition=dict(environment_geometry_definition=grid)))
        ),
        declaration=dict(
            base=dict(material_binding=dict(geometry_binding=dict(definition_json=text)))
        ),
    )
    transition = tmp_path / "failed-transition"
    raw_archive(
        transition / "actual-complete-INIT",
        dict(returned=dict(identity="synthetic-run", complete_init=complete)),
    )
    raw_archive(transition / "SIM-component-binding", dict(returned=component))
    raw_archive(transition / "actual-INIT-to-SIM", dict(failure="synthetic original refusal"))
    compare = tmp_path / "owner-comparison.json"
    write(compare, runner.handoff.compare_saved(transition))
    producer = tmp_path / "producer.json"
    write(
        producer,
        dict(
            source_hashes={"dummy.py": runner.snapshot.digest(repo / "src/cells/dummy.py")},
            runtime_code_sha256={},
            executable=runner.ref(sys.executable),
        ),
    )
    result = tmp_path / "reviewed-result.json"
    write(
        result,
        dict(
            validation=dict(passed=34),
            scientific_acceptance=False,
            source_snapshot=runner.ref(source / "SNAPSHOT.json"),
            saved_correspondence=dict(comparison=runner.ref(compare)),
            producer=runner.ref(producer),
        ),
    )
    review = tmp_path / "review.json"
    write(review, dict(scope="synthetic software control only", result=runner.ref(result)))
    monkeypatch.setattr(runner, "runtime_pins", lambda value: {})
    kwargs = dict(
        reviewed_result=result,
        reviewed_sha256=runner.snapshot.digest(result),
        review=review,
        review_sha256=runner.snapshot.digest(review),
    )
    return repo, kwargs


def test_prepare_copies_only_current_git_and_keeps_exact_targets(tmp_path, monkeypatch):
    repo, kwargs = basis(tmp_path, monkeypatch)
    # A reviewed path is a selection, never a historical source overlay.
    (repo / runner.OWNED[0]).write_text("# Fresh current Git implementation\n")
    output = tmp_path / "packet"
    inputs = runner.prepare(repo, output, **kwargs)
    assert (output / "source" / runner.OWNED[0]).read_bytes() == (
        repo / runner.OWNED[0]
    ).read_bytes()
    assert inputs["targets"] == runner.TARGETS and len(inputs["targets"]) == 3
    assert inputs["scenarios"]["SIM_associations"]["INIT_setup_entries"] == 2
    assert inputs["independent_biological_cases"] == 0 and inputs["scientific_acceptance"] is False
    assert runner.verify_packet(output, runner.snapshot.digest(output / "inputs.json")) == inputs
    request = runner.read_json(output / "root-request-template.json")
    assert request["cpu"] is request["timeout_seconds"] is request["max_rss_bytes"] is None
    assert not (output / "result.json").exists()
    with pytest.raises(FileExistsError):
        runner.prepare(repo, output, **kwargs)


def test_prepare_refuses_changed_original_fixture(tmp_path, monkeypatch):
    repo, kwargs = basis(tmp_path, monkeypatch)
    (repo / "validation/betse/original_fixtures.py").write_text("# Changed fixture\n")
    with pytest.raises(ValueError, match="Changed original fixture/target"):
        runner.prepare(repo, tmp_path / "packet", **kwargs)


def test_packet_refuses_corruption_and_changed_failed_parent(tmp_path, monkeypatch):
    repo, kwargs = basis(tmp_path, monkeypatch)
    packet = tmp_path / "packet"
    inputs = runner.prepare(repo, packet, **kwargs)
    pin = runner.snapshot.digest(packet / "inputs.json")
    with pytest.raises(ValueError, match="Changed held run inputs"):
        runner.verify_packet(packet, "0" * 64)
    archive = Path(inputs["original_failed_archives"]["actual-INIT-to-SIM"]["path"]) / "data.json"
    with archive.open("ab") as stream:
        stream.write(b" original failure stays corrupted")
    with pytest.raises(ValueError, match="Changed saved handoff evidence"):
        runner.verify_packet(packet, pin)


def test_runtime_pins_include_the_actual_startup_package(tmp_path, monkeypatch):
    startup = tmp_path / "startup.py"
    startup.write_text("# Synthetic startup software, no owner state\n")
    stdlib = tmp_path / "stdlib"
    stdlib.mkdir()
    packages = []

    def distribution(package):
        packages.append(package)
        return SimpleNamespace(
            files=[Path("startup.py")] if package == "setuptools" else [],
            locate_file=lambda member: tmp_path / member,
        )

    monkeypatch.setattr(runner.metadata, "distribution", distribution)
    monkeypatch.setattr(runner.sysconfig, "get_path", lambda name: str(stdlib))
    pins = runner.runtime_pins(dict(runtime_code_sha256={}))
    assert "setuptools" in packages
    assert pins == {str(startup): runner.snapshot.digest(startup)}


def test_worker_hold_precedes_io_launch_and_output(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Worker must refuse before preflight/process work")

    monkeypatch.setattr(runner, "verify_packet", forbidden)
    monkeypatch.setattr(runner, "run_bounded", forbidden)
    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    with pytest.raises(ValueError, match="Held: existing Root release"):
        runner.worker(tmp_path / "absent", tmp_path / "output", {})
    assert not (tmp_path / "output").exists()


def packet_tree(packet):
    return {
        str(path.relative_to(packet)): (
            path.is_dir(),
            path.stat().st_mtime_ns,
            None if path.is_dir() else path.read_bytes(),
        )
        for path in [packet, *packet.rglob("*")]
    }


@pytest.mark.parametrize(
    "route", ["direct", "packet-itself", "symlink-parent", "symlink-leaf", "symlink-packet"]
)
def test_worker_refuses_inside_packet_before_any_mutation(tmp_path, monkeypatch, route):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "marker").write_bytes(b"held packet bytes")
    output = packet / "new-output" / "nested"
    if route == "packet-itself":
        output = packet
    elif route == "symlink-parent":
        alias = tmp_path / "parent-alias"
        alias.symlink_to(packet, target_is_directory=True)
        output = alias / "new-output" / "nested"
    elif route == "symlink-leaf":
        output = tmp_path / "leaf-alias"
        output.symlink_to(packet / "new-output", target_is_directory=True)
    elif route == "symlink-packet":
        alias = tmp_path / "packet-alias"
        alias.symlink_to(packet, target_is_directory=True)
        packet = alias
    actual_packet = packet.resolve(strict=True)
    before = packet_tree(actual_packet)
    attempted = []

    def forbidden(*args, **kwargs):
        attempted.append("mutation/preflight/process")
        raise AssertionError("Inside-packet output must refuse before any mutation or launch")

    monkeypatch.setenv(runner.handoff.RELEASE_ENV, "1")
    for module, name in (
        (Path, "mkdir"),
        (runner, "verify_packet"),
        (runner, "run_bounded"),
        (runner, "retain_failure"),
        (runner.snapshot, "write_json"),
        (subprocess, "Popen"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    with pytest.raises(ValueError, match="Output must be separate from the held packet"):
        runner.worker(packet, output, {})
    assert attempted == [] and packet_tree(actual_packet) == before
    (tmp_path / "containment-control.json").write_text(
        json.dumps(
            dict(
                route=route,
                packet_unchanged=True,
                mutation_preflight_process_attempts=attempted,
                actual_setup_native_RNG_timestep_calls=0,
                scientific_acceptance=False,
            )
        )
    )


@pytest.mark.parametrize("secondary_failure", [False, True])
def test_worker_safe_sibling_retains_primary_preflight_error(
    tmp_path, monkeypatch, secondary_failure
):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "marker").write_bytes(b"held packet bytes")
    output = tmp_path / "safe-sibling"
    before = packet_tree(packet)
    primary = OSError("synthetic primary preflight refusal")
    cause = ValueError("original primary cause")
    primary.__cause__ = cause
    observed = []

    def preflight(*args):
        observed.append("safe sibling preflight")
        raise primary

    def forbidden(*args, **kwargs):
        raise AssertionError("No actual owner/native/process/resource entry in this control")

    def secondary(*args, **kwargs):
        raise OSError("synthetic secondary evidence refusal")

    monkeypatch.setenv(runner.handoff.RELEASE_ENV, "1")
    monkeypatch.setattr(runner, "verify_packet", preflight)
    monkeypatch.setattr(runner, "run_bounded", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(runner.os, "sched_setaffinity", forbidden)
    if secondary_failure:
        monkeypatch.setattr(runner.snapshot, "write_json", secondary)
    with pytest.raises(OSError, match="synthetic primary preflight refusal") as caught:
        runner.worker(packet, output, {"packet_sha256": "0" * 64})
    assert caught.value is primary and caught.value.__cause__ is cause
    assert output.is_dir() and observed == ["safe sibling preflight"]
    assert packet_tree(packet) == before
    if secondary_failure:
        assert not (output / "failure.json").exists()
        assert "synthetic secondary evidence refusal" in primary.__notes__[0]
    else:
        failure = runner.read_json(output / "failure.json")
        assert failure["stage"] == "preflight" and failure["message"] == str(primary)
        assert str(cause) in failure["traceback"]
    (tmp_path / "containment-control.json").write_text(
        json.dumps(
            dict(
                route="safe-sibling",
                packet_unchanged=True,
                primary_exception_and_cause_preserved=True,
                secondary_failure=secondary_failure,
                actual_setup_native_RNG_timestep_calls=0,
                scientific_acceptance=False,
            )
        )
    )


def test_worker_packet_resolution_failure_creates_no_output(tmp_path, monkeypatch):
    monkeypatch.setenv(runner.handoff.RELEASE_ENV, "1")

    def forbidden(*args, **kwargs):
        raise AssertionError("Resolve the packet before any mutation/preflight/process work")

    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(runner, "verify_packet", forbidden)
    monkeypatch.setattr(runner, "run_bounded", forbidden)
    monkeypatch.setattr(runner, "retain_failure", forbidden)
    with pytest.raises(FileNotFoundError):
        runner.worker(tmp_path / "missing-packet", tmp_path / "output", {})
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize(
    "fault",
    [
        "cpu-bool",
        "cpu-missing",
        "cpu-negative",
        "time-missing",
        "time-zero",
        "memory-bool",
        "reserve-low",
        "extra",
    ],
)
def test_root_resource_plan_is_explicit_and_strict(fault, monkeypatch):
    # Metadata guard only, never a worker launch.
    monkeypatch.setenv(runner.handoff.RELEASE_ENV, "1")
    request = dict(
        packet_sha256="0" * 64,
        cpu=0,
        timeout_seconds=480,
        max_rss_bytes=2**30,
        min_available_bytes=8 * 2**30,
    )
    if fault == "cpu-bool":
        request["cpu"] = False
    elif fault == "cpu-missing":
        request["cpu"] = None
    elif fault == "cpu-negative":
        request["cpu"] = -1
    elif fault == "time-missing":
        request["timeout_seconds"] = None
    elif fault == "time-zero":
        request["timeout_seconds"] = 0
    elif fault == "memory-bool":
        request["max_rss_bytes"] = True
    elif fault == "reserve-low":
        request["min_available_bytes"] = 1
    else:
        request["unexpected"] = 1
    with pytest.raises(ValueError):
        runner.released_request(dict(release_env=runner.handoff.RELEASE_ENV), request)


def test_command_and_environment_cannot_expand_roster_or_inherit_extra_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTEST_ADDOPTS", "--ignore=tests")
    monkeypatch.setenv("CELLS_COMPONENT_EVIDENCE", "old-output")
    monkeypatch.setenv("XLA_FLAGS", "unreviewed-flags")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    env = runner.child_environment(tmp_path / "source", tmp_path / "target")
    assert not {"PYTEST_ADDOPTS", "CELLS_COMPONENT_EVIDENCE", "XLA_FLAGS"}.intersection(env)
    assert env["CUDA_VISIBLE_DEVICES"] == "" and env["OMP_NUM_THREADS"] == "1"
    assert env[runner.handoff.RELEASE_ENV] == "1" and env["PYTHONOPTIMIZE"] == "0"
    for node in runner.TARGETS.values():
        args = runner.command(tmp_path / "source", tmp_path / "target", node)
        assert (
            args.count(node) == 1 and "--noconftest" in args and "--import-mode=importlib" in args
        )
    with pytest.raises(ValueError, match="Exactly one"):
        runner.command(tmp_path, tmp_path, "tests/unit")


def test_profile_counts_nested_synthetic_work_without_model_or_RNG(tmp_path):
    namespace = {"__name__": "cells.processes.betse_normal_ecm_molecule_checkpoint"}
    exec(
        compile(
            "def verify(): return 1\n"
            "def advance(): return verify()\n"
            "def save_checkpoint(): return advance()\n",
            "<synthetic-software-control>",
            "exec",
        ),
        namespace,
    )
    path = tmp_path / "calls.jsonl"
    with path.open("x") as stream:
        calls = plugin.Calls(stream)
        calls.start()
        try:
            assert namespace["save_checkpoint"]() == 1
        finally:
            result = calls.stop()
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    entries = [row for row in rows if row["event"] == "entry"]
    assert [row["category"] for row in entries] == [
        "checkpoint_save_checkpoint",
        "timestep_boundary",
        "verification_boundary",
    ]
    assert [row["parent_invocation"] for row in entries] == [None, 1, 2]
    assert len(rows) == 6 and result["active_invocations"] == 0 and result["profile_intact"]
    assert all(count == 1 for count in result["counts"].values())


def test_profile_unwind_is_counted_but_not_invented_success(tmp_path):
    namespace = {"__name__": "cells.synthetic_control"}
    exec(
        compile(
            'def verify(): raise ValueError("synthetic refusal")\n', "<synthetic-control>", "exec"
        ),
        namespace,
    )
    with (tmp_path / "calls.jsonl").open("x") as stream:
        calls = plugin.Calls(stream)
        calls.start()
        try:
            with pytest.raises(ValueError, match="synthetic refusal"):
                namespace["verify"]()
        finally:
            result = calls.stop()
    assert result["active_invocations"] == 0 and "status" not in result
    assert "exception unwind" in result["scope"]


def test_phase_accounting_reads_plain_slots_without_setup(tmp_path):
    @dataclass(frozen=True, slots=True)
    class Calendar:
        phase: str

    namespace = {"__name__": "cells.synthetic_control"}
    exec(compile("def advance(binding): return 1\n", "<synthetic-control>", "exec"), namespace)
    with (tmp_path / "calls.jsonl").open("x") as stream:
        calls = plugin.Calls(stream)
        calls.start()
        try:
            namespace["advance"](SimpleNamespace(calendar=Calendar("SIM")))
        finally:
            result = calls.stop()
    assert result["phase_counts"] == {"cells.synthetic_control.advance:SIM": 1}


def test_RNG_C_observation_is_synthetic_not_a_draw():
    calls = plugin.Calls(io.StringIO())
    rows = []
    calls.emit = rows.append
    frame = sys._getframe()
    callable_metadata = SimpleNamespace(__module__="numpy.random.mtrand", __name__="set_state")
    calls.observe(frame, "c_call", callable_metadata)
    calls.observe(frame, "c_return", callable_metadata)
    assert calls.counts == {"numpy.random.mtrand.set_state": 1}
    assert [row["event"] for row in rows] == ["entry", "exit"] and not calls.active


def test_counter_io_failure_closes_profile(tmp_path):
    namespace = {"__name__": "cells.synthetic_control"}
    exec(compile("def verify(): return 1\n", "<synthetic-control>", "exec"), namespace)
    with (tmp_path / "calls.jsonl").open("x") as stream:
        calls = plugin.Calls(stream)

        def refused(row):
            raise OSError("synthetic accounting I/O failure")

        calls.emit = refused
        calls.start()
        try:
            with pytest.raises(OSError, match="accounting I/O"):
                namespace["verify"]()
        finally:
            result = calls.stop()
    assert result["profile_intact"] is False and calls.failure is not None


@pytest.mark.parametrize("fault", [None, "pid", "start-time", "child", "terminal", "empty"])
def test_actual_child_binding_uses_saved_supervisor_not_live_queries(tmp_path, fault):
    process = tmp_path / "process"
    process.mkdir()
    identity = dict(pid=10, start_ticks=20)
    start = dict(pid=11 if fault == "pid" else 10)
    done = dict(status="completed", returncode=1 if fault == "terminal" else 0)
    rows = [dict(pid=10, start_ticks=21 if fault == "start-time" else 20)]
    if fault == "child":
        rows.append(dict(pid=12, start_ticks=30))
    if fault == "empty":
        rows = []
    write(process / "process-started.json", start)
    write(process / "result.json", done)
    (process / "host-resources.jsonl").write_text(json.dumps(dict(processes=rows)) + "\n")
    if fault is None:
        assert runner.bind_process(tmp_path, identity)["terminal"] == runner.ref(
            process / "result.json"
        )
    else:
        with pytest.raises(ValueError):
            runner.bind_process(tmp_path, identity)


def test_native_and_child_guards_refuse_before_execution(tmp_path):
    session = plugin.Session(tmp_path)
    with pytest.raises(ImportError, match="Native BETSE"):
        session.guard.find_spec("betse.science")
    with pytest.raises(RuntimeError, match="No native/reference"):
        session.block_child(["never-executed"])
    assert len(session.forbidden) == 2


def test_secondary_failure_writer_does_not_mask_primary(tmp_path, monkeypatch):
    primary = ValueError("primary source refusal")

    def secondary(*args, **kwargs):
        raise OSError("secondary evidence refusal")

    monkeypatch.setattr(runner.snapshot, "write_json", secondary)
    runner.retain_failure(tmp_path, primary, stage="synthetic-software")
    assert (
        str(primary) == "primary source refusal"
        and "secondary evidence refusal" in primary.__notes__[0]
    )


@pytest.mark.parametrize(
    "fault", [None, "truncated", "orphan-exit", "aggregate", "phase", "parent", "duplicate"]
)
def test_invocation_journal_must_match_nested_actual_records(tmp_path, fault):
    function = "cells.synthetic_control.verify"
    rows = [
        dict(event="entry", invocation=1, function=function, phase="INIT", parent_invocation=None),
        dict(event="exit", invocation=1, exit_event="return"),
    ]
    accounting = dict(
        counts={function: 1}, phase_counts={function + ":INIT": 1}, durable_major_entries=1
    )
    if fault == "truncated":
        rows.pop()
    elif fault == "orphan-exit":
        rows[1]["invocation"] = 2
    elif fault == "aggregate":
        accounting["counts"][function] = 2
    elif fault == "phase":
        accounting["phase_counts"][function + ":INIT"] = 2
    elif fault == "parent":
        rows[0]["parent_invocation"] = 7
    elif fault == "duplicate":
        rows.insert(1, dict(rows[0]))
    path = tmp_path / "invocations.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    if fault is None:
        assert runner.bind_calls(path, accounting)["durable_major_entries"] == 1
    else:
        with pytest.raises(ValueError):
            runner.bind_calls(path, accounting)


def npy_bytes(shape=(2,), dtype="<f8"):
    text = repr(dict(descr=dtype, fortran_order=False, shape=shape)).encode("ascii")
    length = ((10 + len(text) + 1 + 63) // 64) * 64 - 10
    header = text + b" " * (length - len(text) - 1) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", length) + header + b"\x00" * 16


@pytest.mark.parametrize("fault", [None, "descriptor", "orphan", "truncated", "collision"])
def test_saved_raw_array_binding_is_complete_bounded_and_exact(tmp_path, fault):
    folder = tmp_path / "archive"
    raw_archive(folder, {}, arrays={"a0.npy": npy_bytes()})
    value = dict(array="a0", dtype="<f8", shape=[2])
    if fault == "descriptor":
        value["shape"] = [1, 2]
    if fault == "orphan":
        value = None
    if fault == "truncated":
        (folder / "arrays.npz").write_bytes(b"truncated")
    elif fault == "collision":
        value = dict(sequence=[value, value])
    (folder / "data.json").write_text(json.dumps(value))
    manifest = runner.read_json(folder / "manifest.json")
    manifest["files"] = {
        name: runner.snapshot.digest(folder / name) for name in ("data.json", "arrays.npz")
    }
    (folder / "manifest.json").write_text(json.dumps(manifest))
    if fault is None:
        bound = runner.bind_archive(folder)
        assert bound["arrays"] == 1 and bound["scalar_0D_identity_claim"] is False
    else:
        with pytest.raises((ValueError, zipfile.BadZipFile)):
            runner.bind_archive(folder)


@pytest.mark.parametrize(
    "fault", ["xfail", "skip", "failed", "duplicate", "identity", "wrong-node"]
)
def test_reader_cannot_promote_nonpassing_or_wrong_target(tmp_path, fault):
    node = runner.TARGETS["zero_INIT_calls"]
    start = dict(pid=10, start_ticks=20)
    finish = dict(
        start,
        exitstatus=0,
        collected=[node],
        reports=[
            dict(nodeid=node, when=when, outcome="passed", wasxfail=False)
            for when in ("setup", "call", "teardown")
        ],
    )
    if fault == "xfail":
        finish["reports"][1]["wasxfail"] = True
    elif fault == "skip":
        finish["reports"][1]["outcome"] = "skipped"
    elif fault == "failed":
        finish["reports"][1]["outcome"] = "failed"
    elif fault == "duplicate":
        finish["collected"].append(node)
    elif fault == "identity":
        finish["pid"] = 11
    else:
        finish["collected"] = ["unbound target"]
    write(tmp_path / "pytest-start.json", start)
    write(tmp_path / "pytest-finish.json", finish)
    with pytest.raises(ValueError):
        runner.read_target(tmp_path, {}, label="zero_INIT_calls", cpu=0)
