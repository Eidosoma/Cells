"""Native-blocked launch metadata controls; private fixtures issue no owners."""

import ast
import copy
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType
from types import SimpleNamespace as NS
from typing import TYPE_CHECKING

import pytest

from tests.unit import test_betse_native_world_phase_construction as guards
from tests.unit import test_native_sim_demo_observation as observed
from validation.betse import native_seed_demo_launch as launch
from validation.betse import native_seed_demo_launch_software as software

if TYPE_CHECKING:
    # Read-only AST inputs in the immutable software image; never runtime imports.
    from cells.processes import (  # noqa: F401
        betse_native_init_sim_assembly,
        betse_native_init_sim_preparation,
        betse_native_init_terminal,
        betse_native_sim_run,
    )

_RAW_GUARDS = []


def consumer_forbidden_frame(frame):
    return frame.f_globals.get("__name__") in (
        "cells.processes.betse_native_init_terminal",
        "cells.processes.betse_native_init_terminal_molecules",
        "cells.processes.betse_native_init_sim_preparation",
        "cells.processes.betse_native_init_sim_assembly",
        "cells.processes.betse_native_sim_run",
        "validation.betse.native_sim_demo",
    ) or software.is_forbidden_frame(frame)


@pytest.mark.parametrize(
    "module",
    (
        "cells.processes.betse_native_init_terminal",
        "cells.processes.betse_native_init_terminal_molecules",
    ),
)
def test_launch_init_terminal_native_surface_is_blocked(module):
    for name in ("from_electrical", "prepare", "begin_iteration", "finish_runtime"):
        code = consumer_forbidden_frame.__code__.replace(co_name=name)
        assert consumer_forbidden_frame(NS(f_globals={"__name__": module}, f_code=code))


def terminal_bundle(b):
    declaration = launch.read(b.plan["demo_plan"])
    declaration.update(
        kind="cells.genuine_seed_core_profiles_junctions_demo@7",
        endpoint="init_terminal",
        init_iterations=None,
    )
    declaration["source_plan"] = dict(
        optional_init_terminal=dict(
            maximum_iterations=512,
            init_iterations=None,
            full_original_calendar=True,
            normal_loop_context_and_caller_return=True,
            selected_stop=False,
            before_native_pickle=True,
        )
    )
    declaration_pin = write(b.packet / "demo-plan.json", declaration)
    made = launch.prepare(
        b.packet,
        b.root / "terminal-plan",
        demo_plan_sha256=declaration_pin["sha256"],
        release_environment=b.env,
        input_bundle=b.plan["input_bundle"],
    )
    b.path, b.sha = Path(made["plan"]["path"]), made["plan"]["sha256"]
    b.plan = launch.read(made["plan"])
    release = write(
        b.root / "terminal-release.json",
        dict(
            kind=launch.RELEASE_KIND,
            authorized=True,
            launch_plan_sha256=b.sha,
            demo_plan_sha256=b.plan["demo_plan"]["sha256"],
            snapshot_sha256=b.plan["source_snapshot"]["sha256"],
            release_environment=b.env,
            endpoint="init_terminal",
            init_iterations=None,
        ),
    )
    b.release, b.release_sha = Path(release["path"]), release["sha256"]
    return b


@pytest.mark.parametrize("count", (1, 500, 512))
def test_launch_init_terminal_keeps_none_selection_and_whole_count(bundle, monkeypatch, count):
    b = terminal_bundle(bundle)
    assert launch.verify(b.path, b.sha)["init_iterations"] is None
    assert launch.verify_release(b.plan, b.sha, b.release, b.release_sha)["init_iterations"] is None
    calls = []

    def public(path, output, **kwargs):
        assert launch.read(b.plan["demo_plan"])["init_iterations"] is None
        calls.append(kwargs)
        output.mkdir()
        return NS(
            methods_completed=True,
            evidence_completed=True,
            primary=None,
            secondary=[],
            endpoint="init_terminal",
            init_iterations=None,
            init_terminal_completed=True,
            init_first_step_completed=False,
            init_short_history_completed=False,
            init_time_steps_completed=count,
        )

    worker_setup(b, monkeypatch, public)
    result = launch.worker(b.path, b.root / "worker", **kwargs(b))
    assert (
        result["status"] == "source_completed_unqualified" and result["endpoint"] == "init_terminal"
    )
    assert result["init_iterations"] is None and result["scientific_credit"] == 0
    assert len(calls) == 1


@pytest.mark.parametrize("bad", (0, 64, 500, True, "all"))
def test_launch_init_terminal_rejects_any_selected_count(bundle, bad):
    b = terminal_bundle(bundle)
    b.plan["init_iterations"] = bad
    with pytest.raises(ValueError, match="iteration count"):
        launch._immutable(b.plan)


@pytest.mark.parametrize(
    "field,bad",
    (
        ("init_time_steps_completed", 0),
        ("init_time_steps_completed", 513),
        ("init_time_steps_completed", True),
        ("init_iterations", 500),
        ("init_terminal_completed", False),
        ("init_short_history_completed", True),
    ),
)
def test_launch_init_terminal_partial_or_selected_worker_return_stays_failed(
    bundle, monkeypatch, field, bad
):
    b = terminal_bundle(bundle)

    def public(path, output, **kwargs):
        output.mkdir()
        fields = dict(
            methods_completed=True,
            evidence_completed=True,
            primary=None,
            secondary=[],
            endpoint="init_terminal",
            init_iterations=None,
            init_terminal_completed=True,
            init_first_step_completed=False,
            init_short_history_completed=False,
            init_time_steps_completed=500,
        )
        fields[field] = bad
        return NS(**fields)

    worker_setup(b, monkeypatch, public)
    with pytest.raises(ValueError):
        launch.worker(b.path, b.root / "worker", **kwargs(b))
    assert (b.root / "worker/failure.json").is_file()


def short_history_bundle(b, count=3):
    declaration = launch.read(b.plan["demo_plan"])
    declaration.update(
        kind="cells.genuine_seed_core_profiles_junctions_demo@6",
        endpoint="init_short_history",
        init_iterations=count,
    )
    pin = write(b.packet / "demo-plan.json", declaration)
    made = launch.prepare(
        b.packet,
        b.root / "short-history-plan",
        demo_plan_sha256=pin["sha256"],
        release_environment=b.env,
        input_bundle=b.plan["input_bundle"],
    )
    b.path, b.sha = Path(made["plan"]["path"]), made["plan"]["sha256"]
    b.plan = launch.read(made["plan"])
    pin = write(
        b.root / "short-history-release.json",
        dict(
            kind=launch.RELEASE_KIND,
            authorized=True,
            launch_plan_sha256=b.sha,
            demo_plan_sha256=b.plan["demo_plan"]["sha256"],
            snapshot_sha256=b.plan["source_snapshot"]["sha256"],
            release_environment=b.env,
            endpoint="init_short_history",
            init_iterations=count,
        ),
    )
    b.release, b.release_sha = Path(pin["path"]), pin["sha256"]
    return b


@pytest.mark.parametrize("count", [1, 3, 64])
def test_launch_init_short_history_count_bound_through_preparation_release_and_worker(
    bundle, monkeypatch, count
):
    b = short_history_bundle(bundle, count)
    assert launch.verify(b.path, b.sha)["init_iterations"] == count
    assert (
        launch.verify_release(b.plan, b.sha, b.release, b.release_sha)["init_iterations"] == count
    )
    calls = []

    def public(path, output, **kwargs):
        declared = launch.read(b.plan["demo_plan"])
        assert declared["init_iterations"] == count and path == b.plan["demo_plan"]["path"]
        calls.append((path, kwargs))
        output.mkdir()
        return NS(
            methods_completed=True,
            evidence_completed=True,
            primary=None,
            secondary=[],
            endpoint="init_short_history",
            init_iterations=count,
            init_short_history_completed=True,
            init_first_step_completed=False,
            init_time_steps_completed=count,
        )

    worker_setup(b, monkeypatch, public)
    result = launch.worker(b.path, b.root / "worker", **kwargs(b))
    assert result["init_iterations"] == count and result["endpoint"] == "init_short_history"
    assert result["scientific_credit"] == 0 and len(calls) == 1


@pytest.mark.parametrize("count", [None, True, False, 0, 65, 2.0, "2"])
def test_launch_init_short_history_rejects_invalid_selection_before_output(bundle, count):
    with pytest.raises(ValueError, match="iteration count"):
        short_history_bundle(bundle, count)
    assert not (bundle.root / "short-history-plan").exists()


@pytest.mark.parametrize(
    "mutation", ["plan", "bool_plan", "release", "bool_release", "release_endpoint", "old_schema"]
)
def test_launch_init_short_history_refuses_changed_count_or_endpoint(bundle, mutation):
    b = short_history_bundle(bundle, 1)
    if mutation in ("plan", "bool_plan"):
        b.plan["init_iterations"] = True if mutation == "bool_plan" else 2
        with pytest.raises(ValueError, match="iteration count"):
            launch._immutable(b.plan)
    elif mutation == "old_schema":
        declaration = launch.read(b.plan["demo_plan"])
        declaration["kind"] = "cells.genuine_seed_core_profiles_junctions_demo@5"
        b.plan["demo_plan"] = write(b.packet / "demo-plan.json", declaration)
        with pytest.raises(ValueError, match="explicit demo schema"):
            launch._immutable(b.plan)
    else:
        release = launch.read(dict(path=str(b.release), sha256=b.release_sha))
        if mutation == "release_endpoint":
            release["endpoint"] = "init_first_step"
        else:
            release["init_iterations"] = True if mutation == "bool_release" else 2
        pin = write(b.release, release)
        with pytest.raises(ValueError, match="explicit release"):
            launch.verify_release(b.plan, b.sha, b.release, pin["sha256"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("init_iterations", True),
        ("init_iterations", 2),
        ("init_time_steps_completed", True),
        ("init_time_steps_completed", 2),
        ("init_short_history_completed", False),
        ("init_first_step_completed", True),
    ],
)
def test_launch_init_short_history_incomplete_public_return_never_succeeds(
    bundle, monkeypatch, field, value
):
    b = short_history_bundle(bundle, 1)
    result = NS(
        methods_completed=True,
        evidence_completed=True,
        primary=None,
        secondary=[],
        endpoint="init_short_history",
        init_iterations=1,
        init_time_steps_completed=1,
        init_short_history_completed=True,
        init_first_step_completed=False,
    )
    setattr(result, field, value)
    worker_setup(b, monkeypatch, lambda *args, **kwargs: result)
    with pytest.raises(ValueError, match="complete short-history"):
        launch.worker(b.path, b.root / "worker", **kwargs(b))
    failure = json.loads((b.root / "worker/failure.json").read_text())
    assert failure["scientific_credit"] == 0
    assert not (b.root / "worker/result.json").exists()


def test_launch_init_short_history_guard_still_blocks_public_owner_entry():
    namespace = {"__name__": "cells.processes.betse_native_init_short_history"}
    container = compile("def prepare():\n return None\n", "synthetic.py", "exec")
    code = next(value for value in container.co_consts if hasattr(value, "co_name"))
    assert software.is_forbidden_frame(NS(f_globals=namespace, f_code=code))


@pytest.fixture
def write_policy(tmp_path):
    output, native, home = tmp_path / "output", tmp_path / "native", tmp_path / "home"
    for folder in (output, native, home):
        folder.mkdir()
    link = home / ".betse"
    link.symlink_to(native, target_is_directory=True)
    parameter_directory = tmp_path / "inputs/RESULTS/GRN"
    policy = launch.WritePolicy(
        output,
        native_home=link,
        native_target=native,
        native_link=launch._link_record(link),
        directories=(parameter_directory,),
    )
    return NS(
        policy=policy,
        output=output,
        native=native,
        home=home,
        link=link,
        parameter_directory=parameter_directory,
    )


@pytest.mark.parametrize("role", ["evidence", "cache", "native_link", "native_target", "mkdir"])
def test_launch_filesystem_exact_declared_writes(write_policy, role):
    b = write_policy
    targets = {
        "evidence": b.output / "result.json",
        "cache": b.output / "runtime-cache/matplotlib/fontlist.json",
        "native_link": b.link / "betse.log",
        "native_target": b.native / "betse.log",
        "mkdir": b.parameter_directory,
    }
    if role == "mkdir":
        b.policy.audit("os.mkdir", (str(targets[role]), 0o755, -1))
    else:
        b.policy.audit("open", (str(targets[role]), "w", os.O_CREAT | os.O_WRONLY))
    b.policy.check()
    assert len(b.policy.events) == 1 and b.policy.record()["failures"] == []


@pytest.mark.parametrize(
    "role", ["input", "sibling", "parameter_file", "nested_mkdir", "fd", "new_link"]
)
def test_launch_filesystem_refuses_unowned_writes_and_keeps_first_failure(write_policy, role):
    b = write_policy
    target = {
        "input": b.output.parent / "inputs/sim_config.yaml",
        "sibling": b.output.parent / "different/output.json",
        "parameter_file": b.parameter_directory / "model.dat",
        "nested_mkdir": b.parameter_directory / "unrequested",
        "fd": 88,
        "new_link": b.output / "link",
    }[role]
    event = "os.mkdir" if role == "nested_mkdir" else "open"
    args = (target if type(target) is int else str(target), "w", os.O_WRONLY)
    if role == "new_link":
        event, args = "os.symlink", (str(b.native), str(target), -1)
    with pytest.raises(ValueError) as caught:
        b.policy.audit(event, args)
    with pytest.raises(ValueError) as check:
        b.policy.check()
    assert check.value is caught.value is b.policy.first_error
    # Retaining a refusal is still possible; this does not clear the failed epoch.
    b.policy.audit("open", (str(b.output / "failure.json"), "w", os.O_WRONLY))
    assert b.policy.record()["first_error"] is not None


@pytest.mark.parametrize("mutation", ["remove", "retarget", "same_target_new_link", "nested_link"])
def test_launch_filesystem_native_link_drift_never_authorizes_a_write(write_policy, mutation):
    b = write_policy
    target = b.link / "betse.log"
    if mutation == "nested_link":
        (b.native / "nested").symlink_to(b.output.parent, target_is_directory=True)
        target = b.link / "nested/escaped"
    else:
        b.link.unlink()
        if mutation != "remove":
            b.link.symlink_to(b.output if mutation == "retarget" else b.native)
    with pytest.raises(ValueError):
        b.policy.audit("open", (str(target), "w", os.O_WRONLY))
    assert b.policy.first_error is not None
    assert not target.exists()


def test_launch_filesystem_native_canonical_path_does_not_bypass_link_epoch(write_policy):
    b = write_policy
    b.link.unlink()
    with pytest.raises(ValueError, match="Native log link"):
        b.policy.audit("open", (str(b.native / "betse.log"), "w", os.O_WRONLY))
    assert b.policy.record()["failures"]


def test_launch_filesystem_readonly_access_is_not_write_permission(write_policy):
    b = write_policy
    b.policy.audit("open", ("/unowned/source.py", "r", os.O_RDONLY))
    assert b.policy.events == []
    with pytest.raises(ValueError):
        b.policy.audit("os.rename", (str(b.output / "x"), "/unowned/y", -1, -1))


@pytest.mark.parametrize(
    "mode,flags", [("r+", os.O_RDWR), ("w", os.O_WRONLY | os.O_CREAT | os.O_TRUNC)]
)
def test_launch_filesystem_null_device_supports_library_type_probes(write_policy, mode, flags):
    policy = write_policy.policy
    policy.audit("open", ("/dev/null", mode, flags))
    with open("/dev/null", "r+b" if mode == "r+" else "wb") as stream:
        assert stream.write(b"metadata probe") == 14
        if mode == "r+":
            assert stream.read() == b""
    policy.check()
    assert policy.record()["null_device"] == launch._null_device()
    assert policy.record()["failures"] == []


@pytest.mark.parametrize("event", ["os.remove", "os.truncate", "os.chmod", "os.rename"])
def test_launch_filesystem_null_device_is_not_mutable_path_authority(write_policy, event):
    policy = write_policy.policy
    args = (
        ("/dev/null", str(write_policy.output / "renamed"), -1, -1)
        if event == "os.rename"
        else ("/dev/null", 0)
    )
    with pytest.raises(ValueError, match="Only null-device opens") as caught:
        policy.audit(event, args)
    assert policy.first_error is caught.value


@pytest.mark.parametrize("change", ["inode", "rdev", "ordinary_file"])
def test_launch_filesystem_null_device_identity_drift_is_sticky(write_policy, monkeypatch, change):
    policy = write_policy.policy
    if change == "ordinary_file":
        original = Path.lstat

        def changed(path):
            if path == Path("/dev/null"):
                return NS(st_mode=0o100666, st_rdev=os.makedev(1, 3))
            return original(path)

        monkeypatch.setattr(Path, "lstat", changed)
    else:
        observed = dict(policy.null_device)
        observed[change] += 1
        monkeypatch.setattr(launch, "_null_device", lambda: observed)
    with pytest.raises(ValueError) as caught:
        policy.audit("open", ("/dev/null", "w", os.O_WRONLY))
    assert policy.first_error is caught.value
    assert policy.record()["failures"]


@pytest.mark.parametrize("target", ["/dev/zero", "/dev/random", "/tmp/null"])
def test_launch_filesystem_null_device_exception_does_not_admit_other_paths(write_policy, target):
    with pytest.raises(ValueError, match="Undeclared demonstration write"):
        write_policy.policy.audit("open", (target, "w", os.O_WRONLY))


def test_launch_filesystem_null_device_alias_is_not_authorized(write_policy):
    alias = write_policy.output / "null-alias"
    alias.symlink_to("/dev/null")
    with pytest.raises(ValueError):
        write_policy.policy.audit("open", (str(alias), "w", os.O_WRONLY))


@pytest.mark.parametrize("cached", [False, True])
def test_launch_filesystem_temporary_probe_and_default_files_stay_in_output(
    write_policy, monkeypatch, cached
):
    b = write_policy
    directory = b.output / "runtime-cache/tmp"
    for key in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(key, str(directory))
    monkeypatch.setattr(launch.tempfile, "tempdir", str(directory) if cached else None)
    record = launch._temporary_directory(b.output, b.policy)
    assert record == launch._temporary_binding(directory)
    assert record is b.policy.temporary_directory
    assert list(directory.iterdir()) == []  # Both startup probes were removed.
    with launch.tempfile.NamedTemporaryFile() as stream:
        assert Path(stream.name).parent == directory
        stream.write(b"library bootstrap bytes")
        stream.seek(0)
        assert stream.read() == b"library bootstrap bytes"
    b.policy.check()
    assert b.policy.record()["temporary_directory"] == record
    assert not (b.output / "runtime-cache/matplotlib").exists()


@pytest.mark.parametrize("cached", ["/tmp", b"/tmp", Path("/tmp")])
def test_launch_filesystem_foreign_cached_temporary_path_refuses_without_reset(
    write_policy, monkeypatch, cached
):
    b = write_policy
    directory = b.output / "runtime-cache/tmp"
    for key in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(key, str(directory))
    monkeypatch.setattr(launch.tempfile, "tempdir", cached)
    with pytest.raises(ValueError, match="Foreign cached temporary"):
        launch._temporary_directory(b.output, b.policy)
    assert launch.tempfile.tempdir is cached
    assert not directory.exists() and b.policy.temporary_directory is None


@pytest.mark.parametrize("key", ["TMPDIR", "TEMP", "TMP"])
def test_launch_filesystem_temporary_environment_drift_refuses_before_probe(
    write_policy, monkeypatch, key
):
    b = write_policy
    directory = b.output / "runtime-cache/tmp"
    for name in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(name, str(directory))
    monkeypatch.setenv(key, "/tmp")
    monkeypatch.setattr(launch.tempfile, "tempdir", None)
    with pytest.raises(ValueError, match="Exact worker temporary environment"):
        launch._temporary_directory(b.output, b.policy)
    assert not directory.exists() and launch.tempfile.tempdir is None


@pytest.mark.parametrize("change", ["directory", "link", "cache", "environment"])
def test_launch_filesystem_temporary_binding_drift_is_sticky(write_policy, monkeypatch, change):
    b = write_policy
    directory = b.output / "runtime-cache/tmp"
    for key in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(key, str(directory))
    monkeypatch.setattr(launch.tempfile, "tempdir", None)
    launch._temporary_directory(b.output, b.policy)
    if change in ("directory", "link"):
        directory.rename(directory.with_name("original-tmp"))
        if change == "directory":
            directory.mkdir(mode=0o700)
        else:
            directory.symlink_to(directory.with_name("original-tmp"), target_is_directory=True)
    elif change == "cache":
        monkeypatch.setattr(launch.tempfile, "tempdir", "/tmp")
    else:
        monkeypatch.setenv("TEMP", "/tmp")
    with pytest.raises(ValueError) as caught:
        b.policy.check()
    assert b.policy.first_error is caught.value
    assert b.policy.record()["failures"]


@pytest.mark.parametrize("root", ["link", "native"])
@pytest.mark.parametrize("event", ["os.remove", "os.rename"])
def test_launch_filesystem_root_replacement_refuses_before_mutation(write_policy, root, event):
    b = write_policy
    target = getattr(b, root)
    args = (str(target), -1) if event == "os.remove" else (str(b.output / "x"), str(target), -1, -1)
    with pytest.raises(ValueError, match="cannot be replaced or removed"):
        b.policy.audit(event, args)
    assert b.link.is_symlink() and b.native.is_dir()


@pytest.mark.parametrize("installed", [True, False])
def test_launch_filesystem_installation_is_observed_before_entry(
    write_policy, tmp_path, monkeypatch, installed
):
    b = write_policy
    bootstrap = write(
        tmp_path / "bootstrap.json",
        dict(
            environment=dict(
                HOME=str(b.home),
                MPLCONFIGDIR=str(b.output / "runtime-cache/matplotlib"),
                PYTHONDONTWRITEBYTECODE="1",
            ),
            native_links={str(b.link): launch._link_record(b.link)},
            native_write_roots=[
                str(b.link),
                str(b.native),
                str(b.output / "runtime-cache/matplotlib"),
            ],
        ),
    )
    demo = write(
        tmp_path / "demo.json",
        dict(callback_bootstrap=bootstrap["path"], callback_bootstrap_sha256=bootstrap["sha256"]),
    )
    inputs = write(
        tmp_path / "parameters.json", dict(program=dict(directories=[str(b.parameter_directory)]))
    )
    callbacks = []
    with monkeypatch.context() as patch:
        patch.setattr(launch.Path, "home", classmethod(lambda cls: b.home))
        patch.setattr(
            launch.sys, "addaudithook", lambda fn: callbacks.append(fn) if installed else None
        )
        patch.setattr(
            launch.sys, "audit", lambda event, *args: [fn(event, args) for fn in callbacks]
        )
        if installed:
            policy = launch._filesystem(dict(demo_plan=demo, parameter_inputs=inputs), b.output)
            assert policy.installed is True and callbacks[0].__self__ is policy
        else:
            with pytest.raises(ValueError, match="Actual demonstration filesystem audit"):
                launch._filesystem(dict(demo_plan=demo, parameter_inputs=inputs), b.output)


def test_launch_filesystem_caught_violation_prevents_worker_success(
    bundle, write_policy, monkeypatch
):
    b, policy = bundle, write_policy.policy

    def public(*_args, **_kwargs):
        try:
            policy.audit("open", ("/unowned/path", "w", os.O_WRONLY))
        except ValueError:
            pass
        return NS(methods_completed=True, evidence_completed=True, primary=None, secondary=[])

    worker_setup(b, monkeypatch, public)
    monkeypatch.setattr(launch, "_filesystem", lambda *_a: policy)
    with pytest.raises(ValueError) as caught:
        launch.worker(b.path, b.root / "worker", **kwargs(b))
    assert caught.value is policy.first_error
    assert not (b.root / "worker/result.json").exists()
    assert (b.root / "worker/filesystem.json").is_file()


def test_launch_filesystem_final_record_failure_preserves_original_falsey_source(
    bundle, monkeypatch
):
    b, primary = bundle, primary_error()

    def public(*_args, **_kwargs):
        raise primary

    def bad_record():
        raise OSError("filesystem record")

    worker_setup(b, monkeypatch, public)
    monkeypatch.setattr(
        launch, "_filesystem", lambda *_a: NS(check=lambda: None, record=bad_record)
    )
    with pytest.raises(FalseyError) as caught:
        launch.worker(b.path, b.root / "worker", **kwargs(b))
    assert caught.value is primary and caught.value.__cause__ is primary.__cause__
    data = launch.read(launch.pin(b.root / "worker/failure.json"))
    assert any(row["stage"] == "filesystem-record" for row in data["secondary"])


@pytest.mark.parametrize(
    "boundary,has_source_error",
    [("runtime-after", False), ("runtime-after", True), ("result-write", False)],
)
def test_launch_filesystem_late_caught_violation_never_promotes_success(
    bundle, write_policy, monkeypatch, boundary, has_source_error
):
    b, policy, primary = bundle, write_policy.policy, primary_error()
    observed = []

    def prohibited():
        try:
            policy.audit("open", ("/unowned/postrun", "w", os.O_WRONLY))
        except ValueError:
            pass

    def public(*_args, **_kwargs):
        if has_source_error:
            raise primary
        return NS(methods_completed=True, evidence_completed=True, primary=None, secondary=[])

    worker_setup(b, monkeypatch, public)
    monkeypatch.setattr(launch, "_filesystem", lambda *_a: policy)
    original_write = launch.snapshot.write_json

    def observe():
        observed.append("runtime")
        if len(observed) == 2 and boundary == "runtime-after":
            prohibited()
        return runtime(b)

    def writer(path, value):
        if Path(path).name == "result.json" and boundary == "result-write":
            prohibited()
        return original_write(path, value)

    with monkeypatch.context() as patch:
        patch.setattr(launch, "observe_runtime", observe)
        patch.setattr(launch.snapshot, "write_json", writer)
        with pytest.raises((ValueError, FalseyError)) as caught:
            launch.worker(b.path, b.root / "worker", **kwargs(b))
    assert caught.value is (primary if has_source_error else policy.first_error)
    assert policy.first_error is not None and (b.root / "worker/failure.json").is_file()


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit native-blocked launch software release required")
    request.config.option.maxfail = 1
    adapter = NS(
        **dict(
            vars(software),
            reuse=software.base.reuse.reuse,
            is_forbidden_frame=consumer_forbidden_frame,
        )
    )
    namespace = dict(vars(guards), software=adapter, _BLOCKADE_FAILURES=())
    fn = FunctionType(guards._blockade.__wrapped__.__code__, namespace)
    try:
        with contextmanager(fn)(request, tmp_path):
            yield
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARDS.append(namespace["_BLOCKADE_FAILURES"])


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False))
    return launch.pin(path)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    """Real immutable metadata image; all native issuers remain absent/blocked."""
    monkeypatch.setattr(launch, "BASE", tmp_path)
    monkeypatch.setattr(launch, "PILLOW", tmp_path / "pillow")
    for name in ("pillow", "betse-v1.5.0", "site", "tail"):
        (tmp_path / name).mkdir()
    packet, source = tmp_path / "packet", tmp_path / "packet/source"
    source.mkdir(parents=True)
    files = {}
    for name in (*launch.PRODUCERS, launch.initial_rng.FILE, launch.initial_rng.rng_runtime.FILE):
        p = source / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Synthetic metadata producer, no executable native code\n")
        p.chmod(0o444)
        files[name] = dict(
            checkout_path=name,
            sha256=launch.pin(p)["sha256"],
            observation=dict(size=p.stat().st_size),
            snapshot_mode=0o444,
        )
    patch = source / "checkout.patch"
    patch.write_bytes(b"")
    patch.chmod(0o444)
    write(
        source / "SNAPSHOT.json",
        dict(
            kind="cells.checkout_source_snapshot@1",
            status="complete",
            immutable=True,
            files=files,
            patch_sha256=launch.pin(patch)["sha256"],
        ),
    )
    (source / "SNAPSHOT.json").chmod(0o444)
    for p in source.rglob("*"):
        if p.is_dir():
            p.chmod(0o555)
    source.chmod(0o555)
    pair = tmp_path / "raw"
    config_root = pair / "original/config"
    config = write(config_root / "config.json", dict(unchanged="private metadata"))
    image = config_root / "geo/image.png"
    image.parent.mkdir()
    image.write_bytes(b"synthetic image bytes, never decoded")
    program = dict(
        root=str(config_root),
        files=dict(config=config),
        manifest=write(pair / "original/program.json", dict(input=config)),
    )
    disabled = pair / "disabled/config"
    disabled.mkdir(parents=True)
    bundle_value = dict(
        source_inventory=dict(
            files={
                "config.json": dict(sha256=config["sha256"]),
                "geo/image.png": dict(sha256=launch.pin(image)["sha256"]),
            }
        ),
        modes=dict(
            original=dict(config=str(config_root), program=program["manifest"]),
            disabled=dict(config=str(disabled), program=dict(path="unused", sha256="0" * 64)),
        ),
    )
    pair_pin = write(pair / "inputs.json", bundle_value)
    runtime = dict(
        entry=str(Path(launch.sys.executable).absolute()),
        executable=launch.pin(Path(launch.sys.executable).resolve()),
        venv_configuration=write(tmp_path / "pyvenv.cfg", dict(synthetic=True)),
        primary_site=str(tmp_path / "site"),
        appended_site=str(tmp_path / "tail"),
    )
    inputs = dict(
        source_snapshot=launch.pin(source / "SNAPSHOT.json"),
        runtime=runtime,
        source_review=write(tmp_path / "review.json", dict(scope="private")),
        program=program,
    )
    inputs_pin = write(packet / "inputs.json", inputs)
    bootstrap = write(tmp_path / "bootstrap.json", dict(native=False))
    declaration = dict(
        parameter_packet=str(packet),
        parameter_sha256=inputs_pin["sha256"],
        snapshot_sha256=inputs["source_snapshot"]["sha256"],
        held=True,
        policy=launch.POLICY,
        flux_operator="original",
        callback_bootstrap=bootstrap["path"],
        callback_bootstrap_sha256=bootstrap["sha256"],
        shared_writer_review=str(tmp_path / "writer.json"),
    )
    write(tmp_path / "writer.json", dict(native=False))
    demo_pin = write(packet / "demo-plan.json", declaration)
    calls = []

    def output_path(p, _packet, actual_program):
        base = Path(actual_program["root"])
        launch.require(
            p != base and not p.is_relative_to(base) and not base.is_relative_to(p),
            "Output intersects raw input",
        )
        return p

    def packet_inputs(actual_packet, actual_sha):
        assert Path(actual_packet) == packet and actual_sha == inputs_pin["sha256"]
        calls.append("initial-directory-epoch")
        return inputs

    parameter = NS(
        runtime_plan=lambda _python: runtime,
        packet_inputs=packet_inputs,
        output_path=output_path,
        _runtime_entry=lambda _runtime: None,
    )
    monkeypatch.setattr(launch, "_parameter", lambda: parameter)
    input_checks = []

    def verify_inputs(actual_pair, actual_sha, *, mode):
        assert actual_pair == pair and actual_sha == pair_pin["sha256"] and mode == "original"
        input_checks.append(mode)
        launch.require(not (config_root / "RESULTS").exists(), "Fresh input epoch required")
        return launch.read(pair_pin)

    input_metadata = NS(verify=verify_inputs)
    monkeypatch.setattr(launch, "_input_metadata", lambda _plan: input_metadata)
    release_environment = {
        launch.RELEASE: "1",
        launch.DEMO_RELEASE: "1",
        "CELLS_EXPLICIT_COMPONENT_RELEASED": "1",
    }
    result = launch.prepare(
        packet,
        tmp_path / "held",
        demo_plan_sha256=demo_pin["sha256"],
        release_environment=release_environment,
        input_bundle=pair_pin,
    )
    plan_path = Path(result["plan"]["path"])
    sha = result["plan"]["sha256"]
    plan = launch.read(result["plan"])
    release_path = tmp_path / "release/release.json"
    release_pin = write(
        release_path,
        dict(
            kind=launch.RELEASE_KIND,
            authorized=True,
            launch_plan_sha256=sha,
            demo_plan_sha256=demo_pin["sha256"],
            snapshot_sha256=inputs["source_snapshot"]["sha256"],
            release_environment=release_environment,
            endpoint=plan["endpoint"],
            init_iterations=plan["init_iterations"],
        ),
    )
    return NS(
        root=tmp_path,
        packet=packet,
        source=source,
        plan=plan,
        path=plan_path,
        sha=sha,
        release=release_path,
        release_sha=release_pin["sha256"],
        calls=calls,
        parameter=parameter,
        inputs=inputs,
        env=release_environment,
        pair=pair,
        pair_pin=pair_pin,
        input_checks=input_checks,
        input_metadata=input_metadata,
        image=image,
    )


def kwargs(b):
    return dict(
        plan_sha256=b.sha, release_path=b.release, release_sha256=b.release_sha, enabled=True
    )


def authorize_metadata(monkeypatch, b):
    monkeypatch.setenv(launch.RELEASE, "1")
    monkeypatch.setattr(launch, "_frozen", lambda plan: None)


def test_launch_prepare_preserves_held_gates_and_explicit_environment(bundle):
    b = bundle
    assert launch.verify(b.path, b.sha) == b.plan
    assert b.calls == ["initial-directory-epoch"]
    assert launch.verify_release(b.plan, b.sha, b.release, b.release_sha)["authorized"] is True
    assert b.plan["held"] is True and b.plan["limitations"]["owner_hydration"] is False
    assert b.plan["policy"] == dict(
        cpu=0, threads=1, max_rss_bytes=2**30, wall_seconds=7200, reserve_bytes=8 * 2**30
    )
    assert not (b.root / "worker").exists()


@pytest.mark.parametrize(
    "endpoint",
    ["seed", "init_setup", "init_prelude", "init_dynamics", "init_electrical", "init_first_step"],
)
def test_launch_endpoint_is_bound_to_exact_demo_declaration(bundle, endpoint):
    b = bundle
    declaration = launch.read(b.plan["demo_plan"])
    declaration["endpoint"] = endpoint
    if endpoint == "init_first_step":
        declaration["kind"] = "cells.genuine_seed_core_profiles_junctions_demo@5"
    changed = write(b.packet / "demo-plan.json", declaration)
    made = launch.prepare(
        b.packet,
        b.root / "endpoint-plan",
        demo_plan_sha256=changed["sha256"],
        release_environment=b.env,
        input_bundle=b.plan["input_bundle"],
    )
    plan = launch.read(made["plan"])
    assert launch.verify(Path(made["plan"]["path"]), made["plan"]["sha256"])["endpoint"] == endpoint
    plan["endpoint"] = "init_setup" if endpoint == "seed" else "seed"
    with pytest.raises(ValueError, match="endpoint binding"):
        launch._immutable(plan)


@pytest.mark.parametrize("kind", [None, "cells.genuine_seed_core_profiles_junctions_demo@4"])
def test_launch_first_step_refuses_pre_iteration_demo_schema(bundle, kind):
    b = bundle
    declaration = launch.read(b.plan["demo_plan"])
    declaration.update(endpoint="init_first_step", kind=kind)
    changed = write(b.packet / "demo-plan.json", declaration)
    with pytest.raises(ValueError, match="explicit demo schema"):
        launch.prepare(
            b.packet,
            b.root / "first-step-plan",
            demo_plan_sha256=changed["sha256"],
            release_environment=b.env,
            input_bundle=b.plan["input_bundle"],
        )


@pytest.mark.parametrize("endpoint", [None, True, "sim", "INIT"])
def test_launch_endpoint_refuses_unknown_or_untyped_value(bundle, endpoint):
    plan = copy.deepcopy(bundle.plan)
    plan["endpoint"] = endpoint
    with pytest.raises(ValueError, match="endpoint binding"):
        launch._immutable(plan)


@pytest.mark.parametrize("mutation", ["enable", "environment", "snapshot", "demo", "plan", "extra"])
def test_launch_release_refuses_unbound_authority(bundle, mutation):
    b = bundle
    value = launch.read(launch.pin(b.release))
    if mutation == "enable":
        value["authorized"] = False
    elif mutation == "environment":
        value["release_environment"]["CELLS_UNDECLARED_RELEASED"] = "1"
    elif mutation == "extra":
        value["discovered_gates"] = True
    else:
        key = {
            "snapshot": "snapshot_sha256",
            "demo": "demo_plan_sha256",
            "plan": "launch_plan_sha256",
        }[mutation]
        value[key] = "0" * 64
    ref = write(b.root / "bad-release.json", value)
    with pytest.raises(ValueError, match="Exact explicit release"):
        launch.verify_release(b.plan, b.sha, Path(ref["path"]), ref["sha256"])


@pytest.mark.parametrize("count", [None, 1, 64])
def test_launch_prepared_release_retains_verified_endpoint_and_count(bundle, monkeypatch, count):
    b = bundle if count is None else short_history_bundle(bundle, count)

    def forbidden(*args, **kwargs):
        pytest.fail("Release metadata must not launch or execute a worker")

    for name in ("launch", "controller", "worker"):
        monkeypatch.setattr(launch, name, forbidden)
    output = b.path.parent / "prepared-release.json"
    bound = launch.prepare_release(b.path, output, plan_sha256=b.sha)
    value = launch.verify_release(b.plan, b.sha, output, bound["sha256"])
    assert value["endpoint"] == ("seed" if count is None else "init_short_history")
    assert value["init_iterations"] is None if count is None else value["init_iterations"] == count
    assert value["release_environment"] == b.env
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        launch.prepare_release(b.path, output, plan_sha256=b.sha)
    assert output.read_bytes() == before


@pytest.mark.parametrize("change", ["plan", "source", "input", "destination"])
def test_launch_prepared_release_refuses_unverified_inputs_before_write(bundle, change):
    b = bundle
    output = b.path.parent / "prepared-release.json"
    sha = b.sha
    if change == "plan":
        sha = "0" * 64
    elif change == "source":
        declaration = copy.deepcopy(b.plan)
        declaration["producers"][launch.DEMO] = "0" * 64
        changed = write(b.path.parent / "changed-plan.json", declaration)
        b.path, sha = Path(changed["path"]), changed["sha256"]
    elif change == "input":
        (Path(b.inputs["program"]["root"]) / "RESULTS").mkdir()
    else:
        output = b.root / "outside-release.json"
    with pytest.raises((ValueError, RuntimeError)):
        launch.prepare_release(b.path, output, plan_sha256=sha)
    assert not output.exists()


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        {launch.RELEASE: "1"},
        {launch.RELEASE: "1", launch.DEMO_RELEASE: True},
        {launch.RELEASE: "1", launch.DEMO_RELEASE: "1", "PYTHONPATH": "1"},
    ],
)
def test_launch_release_environment_is_closed(bad):
    with pytest.raises(ValueError):
        launch._environment_map(bad)


@pytest.mark.parametrize("role", ["packet", "raw", "source", "overlay", "parent"])
def test_launch_output_cannot_replace_any_input(bundle, role):
    b = bundle
    output = {
        "packet": b.packet / "new",
        "raw": b.root / "raw/new",
        "source": b.source / "new",
        "overlay": b.root / "pillow/new",
        "parent": b.root,
    }[role]
    with pytest.raises(ValueError):
        launch._safe_output(output, b.plan)


def test_launch_environment_does_not_inherit_or_invent_release_flags(bundle, monkeypatch):
    monkeypatch.setenv("CELLS_UNREVIEWED_RELEASED", "1")
    monkeypatch.setenv("PYTHONHOME", "/wrong")
    for key in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(key, "/inherited/temporary")
    value = launch.environment(bundle.plan, bundle.root / "run")
    assert {k: v for k, v in value.items() if k.startswith("CELLS_")} == bundle.env
    assert "PYTHONHOME" not in value
    assert all(value[k] == "1" for k in launch.THREADS)
    assert value["PYTHONPYCACHEPREFIX"] == str(bundle.source / ".unused-bytecode-cache")
    assert all(
        value[key] == str(bundle.root / "run/worker/runtime-cache/tmp")
        for key in ("TMPDIR", "TEMP", "TMP")
    )


def test_launch_immutable_checks_do_not_reopen_consumed_directory_epoch(bundle):
    launch.verify(bundle.path, bundle.sha)
    bundle.parameter.packet_inputs = lambda *_args: pytest.fail("Consumed directory epoch reopened")
    assert launch.verify(bundle.path, bundle.sha, initial=False) == bundle.plan


def test_launch_changed_frozen_source_is_refused(bundle):
    p = bundle.source / launch.FILE
    p.chmod(0o644)
    p.write_text("changed\n")
    p.chmod(0o444)
    with pytest.raises(ValueError, match="Changed snapshot"):
        launch.verify(bundle.path, bundle.sha)


def test_launch_reads_same_hashed_bytes_and_rejects_duplicates(bundle):
    p = bundle.root / "duplicate.json"
    p.write_text('{"a": 1, "a": 2}')
    with pytest.raises(ValueError, match="Duplicate"):
        launch.read(launch.pin(p))
    with pytest.raises(ValueError, match="Changed bound file"):
        launch.read(dict(path=str(p), sha256="0" * 64))


def test_launch_starts_one_detached_controller_without_poll_or_retry(bundle, monkeypatch):
    b = bundle
    authorize_metadata(monkeypatch, b)
    seen = []

    class Child:
        pid = 4321

        def poll(self):
            pytest.fail("Forbidden polling")

        def wait(self, **_kwargs):
            pytest.fail("Forbidden waiting")

    def popen(command, **options):
        seen.append((command, options))
        return Child()

    monkeypatch.setattr(launch.subprocess, "Popen", popen)
    output = b.root / "run"
    result = launch.launch(b.path, output, **kwargs(b))
    assert result["status"] == "launched_unobserved" and result["terminal_outcome"] is None
    assert len(seen) == 1 and seen[0][1]["start_new_session"] is True
    assert seen[0][0][:5] == [str(launch.TASKSET), "-c", "0", b.plan["runtime"]["entry"], "-B"]
    assert seen[0][1]["env"][launch.DEMO_RELEASE] == "1"
    assert launch.read(launch.pin(output / "LAUNCH.json")) == result
    with pytest.raises(ValueError, match="Fresh output"):
        launch.launch(b.path, output, **kwargs(b))
    assert len(seen) == 1


class FalseyError(RuntimeError):
    def __bool__(self):
        return False


def primary_error():
    error = FalseyError("original")
    error.__cause__ = LookupError("cause")
    return error


def test_launch_spawn_failure_retained_without_worker(bundle, monkeypatch):
    authorize_metadata(monkeypatch, bundle)
    primary = primary_error()

    def fail(*_args, **_kwargs):
        raise primary

    monkeypatch.setattr(launch.subprocess, "Popen", fail)
    output = bundle.root / "run"
    with pytest.raises(FalseyError) as got:
        launch.launch(bundle.path, output, **kwargs(bundle))
    assert got.value is primary and got.value.__cause__ is primary.__cause__
    result = launch.read(launch.pin(output / "failure.json"))
    assert result["state"] == dict(child_pid=None, child_may_be_running=False)
    assert result["primary"]["cause"]["message"] == "cause"


def test_launch_receipt_failure_keeps_started_pid_and_never_kills(bundle, monkeypatch):
    authorize_metadata(monkeypatch, bundle)
    monkeypatch.setattr(launch.subprocess, "Popen", lambda *_args, **_kwargs: NS(pid=123))
    original = launch.snapshot.write_json
    primary = primary_error()

    def writer(p, value):
        if p.name == "LAUNCH.json":
            raise primary
        return original(p, value)

    monkeypatch.setattr(launch.snapshot, "write_json", writer)
    output = bundle.root / "run"
    with pytest.raises(FalseyError) as got:
        launch.launch(bundle.path, output, **kwargs(bundle))
    assert got.value is primary
    assert launch.read(launch.pin(output / "failure.json"))["state"] == dict(
        child_pid=123, child_may_be_running=True
    )


def controller_output(b):
    output = b.root / "run"
    output.mkdir()
    write(
        output / "launch-request.json",
        dict(
            plan=launch.pin(b.path),
            release=launch.pin(b.release),
            policy=launch.POLICY,
            worker_wall_seconds=launch._wall_seconds(b.plan),
            release_environment=b.env,
        ),
    )
    return output


def test_launch_controller_uses_exact_existing_guard_and_worker_completion(bundle, monkeypatch):
    b = bundle
    authorize_metadata(monkeypatch, b)
    output = controller_output(b)
    observed = []

    def bounded(command, **options):
        observed.append((command, options))
        write(
            output / "worker/result.json",
            dict(status="source_completed_unqualified", plan_sha256=b.sha),
        )
        return dict(status="completed", returncode=0)

    monkeypatch.setattr(launch.resources, "run_bounded", bounded)
    value = launch.controller(b.path, output, **kwargs(b))
    assert value["scientific_credit"] == 0
    assert len(observed) == 1
    command, options = observed[0]
    assert "--worker" in command and options["timeout"] == 7200
    assert options["max_rss_bytes"] == 2**30 and options["min_available_bytes"] == 8 * 2**30
    assert options["process_tree_memory_metric"] == "rss"


def test_launch_duplicate_controller_cannot_write_into_active_attempt(bundle, monkeypatch):
    b = bundle
    authorize_metadata(monkeypatch, b)
    output = controller_output(b)
    claim = write(output / "controller-started.json", dict(pid=987, already_owned=True))
    monkeypatch.setattr(
        launch.resources, "run_bounded", lambda *_a, **_k: pytest.fail("Duplicate worker")
    )
    with pytest.raises(FileExistsError):
        launch.controller(b.path, output, **kwargs(b))
    assert launch.pin(output / "controller-started.json") == claim
    assert not (output / "failure.json").exists()


@pytest.mark.parametrize("where", ["preflight", "guard", "terminal"])
def test_launch_controller_retains_each_failure_without_retry(bundle, monkeypatch, where):
    b = bundle
    authorize_metadata(monkeypatch, b)
    output = controller_output(b)
    primary = primary_error()
    calls = []

    def failed(*_args, **_kwargs):
        calls.append(where)
        raise primary

    if where == "preflight":
        monkeypatch.setattr(launch, "_entry", failed)
    elif where == "guard":
        monkeypatch.setattr(launch.resources, "run_bounded", failed)
    else:
        monkeypatch.setattr(
            launch.resources,
            "run_bounded",
            lambda *_args, **_kwargs: dict(status="completed", returncode=0),
        )
        original = launch.read

        def read(row):
            if row["path"].endswith("worker/result.json"):
                return dict(status="failed", plan_sha256=b.sha)
            return original(row)

        write(output / "worker/result.json", {})
        monkeypatch.setattr(launch, "read", read)
    with pytest.raises(FalseyError if where != "terminal" else ValueError) as got:
        launch.controller(b.path, output, **kwargs(b))
    if where != "terminal":
        assert got.value is primary and calls == [where]
    assert (output / "failure.json").is_file() and not (output / "result.json").exists()


def runtime(b):
    return dict(
        executable=b.plan["runtime"]["executable"],
        measured_cpu_affinity=[0],
        loaded_files={
            "validation.betse.native_seed_demo_launch": launch.pin(b.source / launch.FILE),
            "validation.betse.betse_native_parameter_world_ready_qualification": launch.pin(
                b.source / launch.PARAMETER
            ),
        },
        mapped_files=[],
        modules_without_files=[],
    )


@pytest.mark.parametrize(
    "mutation", ["cpu", "executable", "mutable", "missing", "changed", "removed"]
)
def test_launch_runtime_refuses_real_metadata_mismatch(bundle, mutation):
    b = bundle
    before = runtime(b)
    assert set(launch.check_runtime(before, b.plan)) == {launch.FILE, launch.PARAMETER}
    value = copy.deepcopy(before)
    if mutation == "cpu":
        value["measured_cpu_affinity"] = [4]
    elif mutation == "executable":
        value["executable"]["sha256"] = "0" * 64
    elif mutation == "mutable":
        value["loaded_files"]["cells.actual"] = write(b.root / "live.py", dict(source="not frozen"))
    elif mutation == "missing":
        value["loaded_files"]["unavailable"] = dict(path=str(b.root / "absent"), unavailable=True)
    elif mutation == "changed":
        next(iter(value["loaded_files"].values()))["sha256"] = "0" * 64
    else:
        value["loaded_files"].pop("validation.betse.native_seed_demo_launch")
    with pytest.raises(ValueError):
        launch.check_runtime(value, b.plan, before=before)


def worker_setup(b, monkeypatch, action):
    if b.plan.get("endpoint") == launch.SIM_ENDPOINT:
        # Worker protocol fixture has no live provider context; actual typed
        # consumer finalization is exercised independently under the same guard.
        def metadata_finish(returned, trial, mode, *, inherited_hooks):
            assert returned.sim_trial is trial and mode == returned.flux_operator
            assert inherited_hooks is False
            launch.sim_observation.bound(returned.sim_observation.record_pin)

        monkeypatch.setattr(launch.sim_observation, "finish", metadata_finish)
    authorize_metadata(monkeypatch, b)
    monkeypatch.setattr(launch, "_worker_environment", lambda *_a: None)
    monkeypatch.setattr(launch, "_temporary_directory", lambda *_a: None)
    monkeypatch.setattr(launch, "observe_runtime", lambda: runtime(b))
    monkeypatch.setattr(
        launch, "_filesystem", lambda *_a: NS(check=lambda: None, record=lambda: {})
    )
    monkeypatch.setattr(
        launch, "_demo", lambda: NS(__file__=str(b.source / launch.DEMO), run_demo=action)
    )
    b.origin_events = []
    b.origin_record = dict(
        kind=launch.NUMPY_ORIGIN_KIND,
        completed=True,
        hooks_restored=True,
        source_error=None,
        capture_errors=[],
        cleanup_errors=[],
        source_files={
            str(b.source / launch.NUMPY_ORIGIN): b.plan["producers"][launch.NUMPY_ORIGIN]
        },
        synthetic_protocol_fixture=True,
    )

    @contextmanager
    def capture():
        b.origin_events.append("enter")
        try:
            yield
        finally:
            b.origin_events.append("exit")

    def record():
        b.origin_events.append("record")
        return b.origin_record

    b.origin = NS(capture=capture, record=record)
    monkeypatch.setattr(launch, "_numpy_origin", lambda _plan: b.origin)


def test_launch_worker_calls_only_public_demo_in_fresh_directory(bundle, monkeypatch):
    b = bundle
    calls = []

    def public(plan_path, output, **options):
        calls.append((plan_path, output, options))
        assert not output.exists()
        output.mkdir()
        return NS(methods_completed=True, evidence_completed=True, primary=None, secondary=[])

    worker_setup(b, monkeypatch, public)
    output = b.root / "worker"
    value = launch.worker(b.path, output, **kwargs(b))
    assert value["public_entry_returned"] is True and value["scientific_credit"] == 0
    assert calls == [
        (
            b.plan["demo_plan"]["path"],
            output / "demo",
            dict(plan_sha256=b.plan["demo_plan"]["sha256"], enabled=True),
        )
    ]
    assert (output / "runtime-before.json").is_file() and (output / "runtime-after.json").is_file()
    assert b.origin_events == ["enter", "exit", "record"]
    assert value["numpy_copy_origin_available"] is value["numpy_copy_origin_completed"] is True
    assert json.loads((output / "numpy-copy-origin.json").read_text()) == b.origin_record
    assert b.calls == ["initial-directory-epoch"]


def diagnostic_bundle(b):
    made = launch.prepare(
        b.packet,
        b.root / "diagnostic-plan",
        demo_plan_sha256=b.plan["demo_plan"]["sha256"],
        release_environment=b.env,
        input_bundle=b.plan["input_bundle"],
        stack_diagnostic=True,
    )
    b.path, b.sha = Path(made["plan"]["path"]), made["plan"]["sha256"]
    b.plan = launch.read(made["plan"])
    b.release = b.path.parent / "release.json"
    b.release_sha = launch.prepare_release(b.path, b.release, plan_sha256=b.sha)["sha256"]
    return b


def test_launch_stack_diagnostic_has_explicit_shorter_budget_and_release(bundle):
    assert launch._wall_seconds(bundle.plan) == 7200
    b = diagnostic_bundle(bundle)
    assert launch.verify(b.path, b.sha)["stack_diagnostic"] is True
    assert b.plan["policy"] == launch.POLICY
    assert launch._wall_seconds(b.plan) == 1800
    assert b.plan["policy"]["max_rss_bytes"] == 2**30
    assert b.plan["policy"]["reserve_bytes"] == 8 * 2**30
    tampered = dict(b.plan, stack_diagnostic=False)
    changed = write(b.path.parent / "changed.json", tampered)
    with pytest.raises(ValueError, match="Exact explicit release"):
        launch.verify_release(tampered, changed["sha256"], b.release, b.release_sha)


def test_launch_stack_diagnostic_missing_mode_preserves_original_schema_refusal(
    bundle, monkeypatch
):
    b = bundle
    worker_setup(b, monkeypatch, lambda *_a, **_k: pytest.fail("Malformed plan entered source"))
    legacy = dict(b.plan)
    legacy.pop("stack_diagnostic")
    changed = write(b.root / "legacy-plan.json", legacy)
    release = launch.read(launch.pin(b.release))
    release["launch_plan_sha256"] = changed["sha256"]
    changed_release = write(b.root / "legacy-release.json", release)
    with pytest.raises(ValueError, match="Exact launch-plan schema") as caught:
        launch.worker(
            changed["path"],
            b.root / "worker",
            plan_sha256=changed["sha256"],
            release_path=changed_release["path"],
            release_sha256=changed_release["sha256"],
            enabled=True,
        )
    failed = launch.read(launch.pin(b.root / "worker/failure.json"))
    assert failed["primary"]["message"] == str(caught.value)
    assert failed["state"]["stack_diagnostic"] is None
    assert failed["state"]["public_entry_attempted"] is False
    assert not b.origin_events and not (b.root / "worker/stack-sampling-start.json").exists()


@pytest.mark.parametrize("bad", (None, 1, "true", []))
def test_launch_stack_diagnostic_rejects_untyped_mode_before_output(bundle, bad):
    with pytest.raises(ValueError, match="Explicit stack diagnostic"):
        launch.prepare(
            bundle.packet,
            bundle.root / "invalid-plan",
            demo_plan_sha256=bundle.plan["demo_plan"]["sha256"],
            release_environment=bundle.env,
            input_bundle=bundle.plan["input_bundle"],
            stack_diagnostic=bad,
        )
    assert not (bundle.root / "invalid-plan").exists()


def test_launch_stack_diagnostic_controller_keeps_other_resource_limits(bundle, monkeypatch):
    b = diagnostic_bundle(bundle)
    authorize_metadata(monkeypatch, b)
    output = controller_output(b)
    calls = []

    def bounded(command, **options):
        calls.append((command, options))
        write(
            output / "worker/result.json",
            dict(status="source_completed_unqualified", plan_sha256=b.sha),
        )
        return dict(status="completed", returncode=0)

    monkeypatch.setattr(launch.resources, "run_bounded", bounded)
    launch.controller(b.path, output, **kwargs(b))
    assert len(calls) == 1
    assert calls[0][1]["timeout"] == 1800
    assert calls[0][1]["max_rss_bytes"] == 2**30
    assert calls[0][1]["min_available_bytes"] == 8 * 2**30
    assert calls[0][1]["process_tree_memory_metric"] == "rss"
    assert (
        launch.read(launch.pin(output / "controller-started.json"))["worker_wall_seconds"] == 1800
    )


def test_launch_stack_diagnostic_timer_keeps_hooks_and_cancels_before_close(tmp_path, monkeypatch):
    hooks = launch.sys.getprofile(), launch.sys.gettrace()
    sampler = launch.StackSampler(tmp_path)
    events = []

    def arm(seconds, **options):
        assert seconds == 30 and options == dict(repeat=True, file=sampler.stream, exit=False)
        assert not sampler.stream.closed
        assert (tmp_path / "stack-sampling-start.json").is_file()
        events.append("arm")

    def cancel():
        assert not sampler.stream.closed
        events.append("cancel")

    monkeypatch.setattr(launch.faulthandler, "dump_traceback_later", arm)
    monkeypatch.setattr(launch.faulthandler, "cancel_dump_traceback_later", cancel)
    sampler.start()
    assert (tmp_path / "stack-sampling-armed.json").is_file()
    sampler.stop()
    assert events == ["arm", "cancel"] and sampler.stream.closed
    assert sampler.record()["cancellation_confirmed"] is True
    assert (launch.sys.getprofile(), launch.sys.gettrace()) == hooks
    with pytest.raises(ValueError, match="already"):
        sampler.stop()


def test_launch_stack_diagnostic_real_c_timer_writes_without_python_hook_changes(
    tmp_path, monkeypatch
):
    # A short stdlib-only timer establishes that real C sampling observes this
    # metadata frame; no model, owner or scientific delegate is called.
    monkeypatch.setattr(launch, "STACK_INTERVAL_SECONDS", 0.02)
    hooks = launch.sys.getprofile(), launch.sys.gettrace()
    sampler = launch.StackSampler(tmp_path)
    try:
        sampler.start()
        time.sleep(0.12)
    finally:
        sampler.stop()
    observed = (tmp_path / "stacks.log").read_text()
    assert "test_launch_stack_diagnostic_real_c_timer" in observed
    assert sampler.cancelled and sampler.stream.closed
    assert (launch.sys.getprofile(), launch.sys.gettrace()) == hooks


@pytest.mark.parametrize("stage", ("open", "start-record", "arm", "armed-record"))
def test_launch_stack_diagnostic_setup_failure_refuses_source_and_closes_file(
    bundle, monkeypatch, stage
):
    b = diagnostic_bundle(bundle)
    worker_setup(b, monkeypatch, lambda *_a, **_k: pytest.fail("Source after failed sampler"))
    primary = primary_error()
    events = []
    original_open, original_write = Path.open, launch.snapshot.write_json

    def opening(path, *args, **options):
        if stage == "open" and path.name == "stacks.log":
            raise primary
        return original_open(path, *args, **options)

    def writer(path, value):
        target = {
            "start-record": "stack-sampling-start.json",
            "armed-record": "stack-sampling-armed.json",
        }.get(stage)
        if path.name == target:
            raise primary
        return original_write(path, value)

    def arm(*args, **options):
        events.append("arm")
        if stage == "arm":
            raise primary

    monkeypatch.setattr(Path, "open", opening)
    monkeypatch.setattr(launch.snapshot, "write_json", writer)
    monkeypatch.setattr(launch.faulthandler, "dump_traceback_later", arm)
    monkeypatch.setattr(
        launch.faulthandler, "cancel_dump_traceback_later", lambda: events.append("cancel")
    )
    with pytest.raises(FalseyError) as caught:
        launch.worker(b.path, b.root / "worker", **kwargs(b))
    assert caught.value is primary and caught.value.__cause__ is primary.__cause__
    sampler = launch._STACK_SAMPLERS[-1]
    assert sampler.stream is None or sampler.stream.closed
    assert events == (["arm", "cancel"] if stage in ("arm", "armed-record") else [])
    assert not b.origin_events
    failed = launch.read(launch.pin(b.root / "worker/failure.json"))
    assert failed["state"]["public_entry_attempted"] is False


@pytest.mark.parametrize("has_source", (False, True))
@pytest.mark.parametrize("failure", ("cancel", "final-record"))
def test_launch_stack_diagnostic_cleanup_preserves_primary_and_live_timer_fd(
    bundle, monkeypatch, has_source, failure
):
    b = diagnostic_bundle(bundle)
    primary, cleanup = primary_error(), OSError("sampler cleanup")

    def public(_plan, output, **options):
        assert (b.root / "worker/stack-sampling-armed.json").is_file()
        if has_source:
            raise primary
        output.mkdir()
        return NS(methods_completed=True, evidence_completed=True, primary=None, secondary=[])

    worker_setup(b, monkeypatch, public)
    monkeypatch.setattr(launch.faulthandler, "dump_traceback_later", lambda *args, **options: None)
    original_write = launch.snapshot.write_json

    def cancel():
        if failure == "cancel":
            raise cleanup

    def writer(path, value):
        if failure == "final-record" and path.name == "stack-sampling-final.json":
            raise cleanup
        return original_write(path, value)

    monkeypatch.setattr(launch.faulthandler, "cancel_dump_traceback_later", cancel)
    monkeypatch.setattr(launch.snapshot, "write_json", writer)
    try:
        with pytest.raises(BaseException) as caught:
            launch.worker(b.path, b.root / "worker", **kwargs(b))
        assert caught.value is (primary if has_source else cleanup)
        assert primary.__cause__.args == ("cause",)
        sampler = launch._STACK_SAMPLERS[-1]
        assert sampler.stream.closed is (failure != "cancel")
        assert sampler.cancelled is (failure != "cancel")
        failed = launch.read(launch.pin(b.root / "worker/failure.json"))
        assert failed["secondary"][-1]["error"]["message"] == "sampler cleanup"
        assert not (b.root / "worker/result.json").exists()
        assert (b.root / "worker/runtime-after.json").is_file()
    finally:
        # No real C timer was armed by this failure injection.
        launch._STACK_SAMPLERS[-1].stream.close()


def test_launch_stack_diagnostic_worker_samples_public_call_and_runtime_inventory(
    bundle, monkeypatch
):
    b = diagnostic_bundle(bundle)
    events = []

    def public(_plan, output, **options):
        assert events == ["arm"]
        output.mkdir()
        return NS(methods_completed=True, evidence_completed=True, primary=None, secondary=[])

    worker_setup(b, monkeypatch, public)
    monkeypatch.setattr(
        launch.faulthandler, "dump_traceback_later", lambda *a, **k: events.append("arm")
    )

    def cancel():
        assert (b.root / "worker/runtime-after.json").is_file()
        assert (b.root / "worker/source-after.json").is_file()
        events.append("cancel")

    monkeypatch.setattr(launch.faulthandler, "cancel_dump_traceback_later", cancel)
    result = launch.worker(b.path, b.root / "worker", **kwargs(b))
    assert events == ["arm", "cancel"]
    assert result["stack_diagnostic"] is True and result["scientific_credit"] == 0
    assert launch.read(launch.pin(b.root / "worker/stack-sampling-final.json"))[
        "cancellation_confirmed"
    ]


@pytest.mark.parametrize(
    "mutation", ["kind", "completed", "hooks", "source", "capture", "cleanup", "files"]
)
def test_launch_numpy_origin_incomplete_evidence_prevents_success(bundle, monkeypatch, mutation):
    b = bundle
    worker_setup(
        b,
        monkeypatch,
        lambda *_a, **_k: NS(
            methods_completed=True, evidence_completed=True, primary=None, secondary=[]
        ),
    )
    key, value = {
        "kind": ("kind", "foreign"),
        "completed": ("completed", False),
        "hooks": ("hooks_restored", False),
        "source": ("source_error", {"type": "SourceError"}),
        "capture": ("capture_errors", [{"type": "OSError"}]),
        "cleanup": ("cleanup_errors", [{"type": "OSError"}]),
        "files": ("source_files", {}),
    }[mutation]
    b.origin_record[key] = value
    output = b.root / "worker"
    with pytest.raises(ValueError, match="construction proof incomplete"):
        launch.worker(b.path, output, **kwargs(b))
    assert json.loads((output / "numpy-copy-origin.json").read_text()) == b.origin_record
    assert (output / "runtime-after.json").is_file() and not (output / "result.json").exists()


@pytest.mark.parametrize(
    "boundary,source_failed",
    [
        ("enter", False),
        ("exit", False),
        ("exit", True),
        ("record", False),
        ("record", True),
        ("writer", False),
        ("writer", True),
        ("suppressed", True),
    ],
)
def test_launch_numpy_origin_boundary_failure_keeps_original_primary_and_other_evidence(
    bundle, monkeypatch, boundary, source_failed
):
    b = bundle
    primary, secondary = primary_error(), OSError("origin observation failed")
    calls = []

    def public(*_args, **_kwargs):
        calls.append("public")
        if source_failed:
            raise primary
        return NS(methods_completed=True, evidence_completed=True, primary=None, secondary=[])

    worker_setup(b, monkeypatch, public)

    @contextmanager
    def capture():
        if boundary == "enter":
            raise secondary
        try:
            yield
        except BaseException:
            if boundary != "suppressed":
                raise
        finally:
            if boundary == "exit":
                raise secondary

    def record():
        if boundary == "record":
            raise secondary
        return b.origin_record

    b.origin.capture, b.origin.record = capture, record
    writer = launch.snapshot.write_json

    def write_origin(path, value):
        if boundary == "writer" and path.name == "numpy-copy-origin.json":
            raise secondary
        return writer(path, value)

    monkeypatch.setattr(launch.snapshot, "write_json", write_origin)
    output = b.root / "worker"
    expected = primary if source_failed else secondary
    with pytest.raises(type(expected)) as caught:
        launch.worker(b.path, output, **kwargs(b))
    assert caught.value is expected
    if source_failed:
        assert caught.value.__cause__ is primary.__cause__
    assert calls == ([] if boundary == "enter" else ["public"])
    assert (output / "runtime-after.json").is_file() and (output / "source-after.json").is_file()
    assert not (output / "result.json").exists()
    if boundary in ("exit", "record", "writer") and source_failed:
        failure = launch.read(launch.pin(output / "failure.json"))
        assert any(row["error"]["type"] == "builtins.OSError" for row in failure["secondary"])


def test_launch_worker_primary_cause_survive_all_postsource_reporting_failures(bundle, monkeypatch):
    b = bundle
    primary = primary_error()

    def public(*_args, **_kwargs):
        raise primary

    worker_setup(b, monkeypatch, public)
    original = launch.snapshot.write_json

    def writer(p, value):
        if p.name in ("runtime-after.json", "source-after.json", "failure.json"):
            raise OSError("injected writer")
        return original(p, value)

    monkeypatch.setattr(launch.snapshot, "write_json", writer)
    output = b.root / "worker"
    with pytest.raises(FalseyError) as got:
        launch.worker(b.path, output, **kwargs(b))
    assert got.value is primary and got.value.__cause__ is primary.__cause__
    retained = [r for r in launch._RAW_FAILURES if r[0] is primary]
    assert any(
        isinstance(row[1], (tuple, list))
        and {p[0] for p in row[1]} == {"runtime-after", "source-after"}
        for row in retained
    )
    assert isinstance(primary.seed_launch_capture_error, OSError)
    assert not (output / "result.json").exists()


def test_launch_worker_refuses_incomplete_return_and_keeps_raw_demo_artifacts(bundle, monkeypatch):
    b = bundle

    def public(_plan, output, **_options):
        output.mkdir()
        (output / "partial.bin").write_bytes(b"exact available raw evidence")
        return NS(methods_completed=True, evidence_completed=False, primary=None, secondary=[])

    worker_setup(b, monkeypatch, public)
    output = b.root / "worker"
    with pytest.raises(ValueError, match="Incomplete demonstration"):
        launch.worker(b.path, output, **kwargs(b))
    assert (output / "demo/partial.bin").read_bytes() == b"exact available raw evidence"
    assert (
        launch.read(launch.pin(output / "failure.json"))["state"]["public_entry_returned"] is True
    )


def test_launch_worker_preentry_failure_never_calls_public_api(bundle, monkeypatch):
    b = bundle
    worker_setup(b, monkeypatch, lambda *_a, **_k: pytest.fail("Unexpected public entry"))

    def fail(_plan, _output):
        raise ValueError("actual environment mismatch")

    monkeypatch.setattr(launch, "_worker_environment", fail)
    output = b.root / "worker"
    with pytest.raises(ValueError, match="environment mismatch"):
        launch.worker(b.path, output, **kwargs(b))
    row = launch.read(launch.pin(output / "failure.json"))
    assert row["state"]["public_entry_attempted"] is False


def test_launch_worker_temporary_probe_failure_retains_primary_before_library_entry(
    bundle, monkeypatch
):
    b = bundle
    worker_setup(b, monkeypatch, lambda *_a, **_k: pytest.fail("Unexpected public entry"))
    primary = primary_error()

    def probe(_output, _policy):
        raise primary

    monkeypatch.setattr(launch, "_temporary_directory", probe)
    with pytest.raises(FalseyError) as caught:
        launch.worker(b.path, b.root / "worker", **kwargs(b))
    assert caught.value is primary and caught.value.__cause__ is primary.__cause__
    row = launch.read(launch.pin(b.root / "worker/failure.json"))
    assert row["state"]["public_entry_attempted"] is False
    assert row["state"]["runtime_before_available"] is False


def test_launch_error_formatter_failure_keeps_primary_and_cause(tmp_path, monkeypatch):
    class Unprintable(FalseyError):
        def __str__(self):
            raise OSError("formatter")

    primary = Unprintable()
    primary.__cause__ = KeyError("original cause")
    value = launch.error_record(primary)
    assert (
        value["message_error_type"] == "OSError" and value["cause"]["message"] == "'original cause'"
    )
    launch._failure(tmp_path, primary, [], "metadata")
    assert launch.read(launch.pin(tmp_path / "failure.json"))["primary"]["cause"] == value["cause"]


def test_launch_held_entry_never_dispatches_or_creates_output(bundle, monkeypatch):
    monkeypatch.delenv(launch.RELEASE, raising=False)
    monkeypatch.setattr(
        launch.subprocess, "Popen", lambda *_a, **_k: pytest.fail("Unexpected process")
    )
    with pytest.raises(ValueError, match="remains held"):
        launch.launch(bundle.path, bundle.root / "run", **kwargs(bundle))
    assert not (bundle.root / "run").exists()


def test_launch_body_has_no_gate_discovery_or_wait_api():
    import ast

    tree = ast.parse(Path(launch.__file__).read_text())
    body = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "launch")
    names = {n.attr for n in ast.walk(body) if isinstance(n, ast.Attribute)}
    assert not names.intersection({"wait", "poll", "sleep", "kill", "terminate", "GATES"})
    assert "Popen" in names


def test_launch_frozen_gate_checks_actual_path_cpu_and_interpreter(bundle, monkeypatch):
    b = bundle
    with pytest.raises(ValueError, match="immutable launch"):
        launch._frozen(b.plan)
    monkeypatch.setattr(launch, "ROOT", b.source)
    monkeypatch.setattr(launch, "__file__", str(b.source / launch.FILE))
    monkeypatch.setattr(launch.os, "sched_getaffinity", lambda _pid: {0})
    launch._frozen(b.plan)
    wrong = copy.deepcopy(b.plan)
    wrong["runtime"]["entry"] = str(b.root / "different-interpreter")
    with pytest.raises(ValueError, match="interpreter"):
        launch._frozen(wrong)
    monkeypatch.setattr(launch.os, "sched_getaffinity", lambda _pid: {4})
    with pytest.raises(ValueError, match="CPU0"):
        launch._frozen(b.plan)


def test_launch_worker_environment_requires_exact_release_limits_threads(bundle, monkeypatch):
    b = bundle
    for name in list(os.environ):
        if name.startswith("CELLS_"):
            monkeypatch.delenv(name)
    for name, value in launch.environment(b.plan, b.root / "run").items():
        if name.startswith(("PYTHON", "CELLS_")) or name in (
            *launch.THREADS,
            "CUDA_VISIBLE_DEVICES",
            "JAX_PLATFORMS",
            "MPLCONFIGDIR",
            "XDG_CACHE_HOME",
            "TMPDIR",
            "TEMP",
            "TMP",
        ):
            monkeypatch.setenv(name, value)
    monkeypatch.setattr(launch.resource, "getrlimit", lambda _kind: (2**30, 2**30))
    monkeypatch.setattr(launch.resources, "memory_available", lambda: 9 * 2**30)
    launch._worker_environment(b.plan, b.root / "run/worker")
    monkeypatch.setenv("CELLS_UNDECLARED_RELEASED", "1")
    with pytest.raises(ValueError, match="release environment"):
        launch._worker_environment(b.plan, b.root / "run/worker")
    monkeypatch.delenv("CELLS_UNDECLARED_RELEASED")
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    with pytest.raises(ValueError, match="environment mismatch"):
        launch._worker_environment(b.plan, b.root / "run/worker")


def test_launch_worker_startup_verification_failure_has_terminal(bundle, monkeypatch):
    b = bundle
    authorize_metadata(monkeypatch, b)
    primary = primary_error()

    def fail(*_args, **_kwargs):
        raise primary

    monkeypatch.setattr(launch, "_entry", fail)
    monkeypatch.setattr(launch, "observe_runtime", lambda: runtime(b))
    output = b.root / "worker"
    with pytest.raises(FalseyError) as got:
        launch.worker(b.path, output, **kwargs(b))
    assert got.value is primary
    row = launch.read(launch.pin(output / "failure.json"))
    assert row["state"]["public_entry_attempted"] is False
    assert row["primary"]["cause"]["message"] == "cause"


def test_launch_failure_exhausted_recorder_does_not_replace_primary(tmp_path, monkeypatch):
    class RefusingList:
        def append(self, _value):
            raise MemoryError("emergency recorder")

    primary = primary_error()
    monkeypatch.setattr(launch, "_RAW_FAILURES", RefusingList())
    original = launch.snapshot.write_json

    def writer(path, value):
        if path == tmp_path / "failure.json":
            raise OSError("writer failure")
        return original(path, value)

    monkeypatch.setattr(launch.snapshot, "write_json", writer)
    launch._failure(tmp_path, primary, [], "metadata")
    assert isinstance(primary.seed_launch_capture_error, OSError)
    assert isinstance(primary.__cause__, LookupError)


def test_launch_inputs_complete_selected_bundle_is_checked_before_consumption(bundle):
    b = bundle
    assert b.input_checks == ["original"]
    assert b.plan["input_bundle"] == b.pair_pin
    assert len(b.plan["input_files"]) == 2
    assert launch.INPUTS in b.plan["producers"]
    launch.verify(b.path, b.sha)
    assert b.input_checks == ["original", "original"]


def test_launch_inputs_headless_roster_uses_selected_bytes_without_source_or_owner(tmp_path):
    from validation.betse import native_seed_demo_input_profiles as profiles

    source = dict(files={profiles.MAIN: dict(sha256=profiles.ORIGINAL_SHA256, size_bytes=63375)})
    value = dict(
        source_inventory=source,
        input_inventory=profiles.inventory(source, "headless"),
        configuration_profile="headless",
        configuration_changes=profiles.changes(),
        raw_configuration_and_images_unchanged=False,
        modes={mode: dict(config=str(tmp_path / mode)) for mode in ("original", "disabled")},
    )
    bundle = write(tmp_path / "headless-bundle.json", value)
    for mode in ("original", "disabled"):
        (tmp_path / mode).mkdir()
        assert launch._input_files(bundle, mode) == [
            dict(path=str(tmp_path / mode / profiles.MAIN), sha256=profiles.HEADLESS_SHA256)
        ]
    assert value["source_inventory"] == source


@pytest.mark.parametrize("where", ["bundle", "parameters", "raw_program"])
def test_launch_inputs_headless_profile_disagreement_refuses_before_callback(bundle, where):
    b = bundle
    plan, inputs = copy.deepcopy(b.plan), copy.deepcopy(b.inputs)
    if where == "bundle":
        value = launch.read(b.pair_pin)
        value["configuration_profile"] = "headless"
        plan["input_bundle"] = write(b.root / "other-bundle.json", value)
    elif where == "parameters":
        inputs["program"]["input_profile"] = "headless"
    else:
        value = launch.read(b.pair_pin)
        row = write(b.root / "other-program.json", dict(input_profile="headless"))
        value["modes"]["original"]["program"] = row
        inputs["program"]["manifest"] = row
        plan["input_bundle"] = write(b.root / "other-bundle.json", value)
    with pytest.raises(ValueError, match="profile"):
        launch._inputs(plan, inputs, initial=False)
    assert b.input_checks == ["original"]


@pytest.mark.parametrize("role", ["image", "core"])
def test_launch_inputs_changed_original_file_refuses_before_public_demo(bundle, monkeypatch, role):
    b = bundle
    authorize_metadata(monkeypatch, b)
    target = b.image if role == "image" else Path(b.inputs["program"]["files"]["config"]["path"])
    target.write_bytes(b"changed original bytes")
    monkeypatch.setattr(launch, "_demo", lambda: pytest.fail("Public native entry reached"))
    monkeypatch.setattr(launch, "observe_runtime", lambda: runtime(b))
    with pytest.raises(ValueError):
        launch.worker(b.path, b.root / "worker", **kwargs(b))
    failure = launch.read(launch.pin(b.root / "worker/failure.json"))
    assert failure["state"]["public_entry_attempted"] is False
    assert not (b.root / "worker/demo").exists()


@pytest.mark.parametrize("mutation", ["program", "config", "missing_file", "extra_file"])
def test_launch_inputs_exact_program_and_full_roster_cannot_be_retargeted(bundle, mutation):
    b = bundle
    plan = copy.deepcopy(b.plan)
    if mutation in ("program", "config"):
        value = launch.read(b.pair_pin)
        row = value["modes"]["original"]
        if mutation == "program":
            row["program"] = b.plan["demo_plan"]
        else:
            row["config"] = str(b.pair / "disabled/config")
        plan["input_bundle"] = write(b.root / "retargeted-pair.json", value)
    elif mutation == "missing_file":
        plan["input_files"].pop()
    else:
        plan["input_files"].append(plan["input_files"][0])
    with pytest.raises(ValueError):
        launch._inputs(plan, b.inputs, initial=True)
    assert b.input_checks == ["original"]


@pytest.mark.parametrize("where", ["sibling", "pair_parent"])
def test_launch_inputs_outputs_cannot_overlap_any_part_of_the_pair(bundle, where):
    b = bundle
    target = b.pair / ("disabled/new-output" if where == "sibling" else "new-output")
    with pytest.raises(ValueError, match="overlaps"):
        launch._safe_output(target, b.plan)
    assert not target.exists()


def test_launch_inputs_consumed_epoch_and_used_sibling_are_not_reopened(bundle, monkeypatch):
    b = bundle
    (b.image.parent.parent / "RESULTS").mkdir()
    (b.pair / "disabled/config/outputs").mkdir()
    monkeypatch.setattr(
        b.input_metadata, "verify", lambda *_a, **_k: pytest.fail("Consumed input epoch reopened")
    )
    monkeypatch.setattr(
        b.parameter, "packet_inputs", lambda *_a, **_k: pytest.fail("Consumed Key epoch reopened")
    )
    assert launch.verify(b.path, b.sha, initial=False) == b.plan
    b.image.write_bytes(b"changed after native execution")
    with pytest.raises(ValueError, match="Changed bound file"):
        launch.verify(b.path, b.sha, initial=False)


@pytest.mark.parametrize("mutation", ["unchanged", "file_bytes", "module_origin"])
def test_launch_inputs_metadata_producer_is_bound_to_frozen_bytes_and_origin(
    bundle, monkeypatch, mutation
):
    b = bundle
    # Exercise the real checker rather than the fixture's metadata-only verifier.
    # The fixture replaces _input_metadata; retrieve the original code from this module's source.
    tree = compile(Path(launch.__file__).read_bytes(), launch.__file__, "exec")
    code = next(
        c for c in tree.co_consts if hasattr(c, "co_name") and c.co_name == "_input_metadata"
    )
    check = FunctionType(code, dict(vars(launch), ROOT=b.source))
    module = NS(__file__=str(b.source / launch.INPUTS))
    monkeypatch.setattr(launch.importlib, "import_module", lambda _name: module)
    if mutation == "file_bytes":
        p = b.source / launch.INPUTS
        p.chmod(0o644)
        p.write_text("# drift\n")
        p.chmod(0o444)
    elif mutation == "module_origin":
        module.__file__ = str(b.source / launch.DEMO)
    if mutation == "unchanged":
        assert check(b.plan) is module
    else:
        with pytest.raises(ValueError):
            check(b.plan)


def initial_rng_bundle(b, *, witness_version=1):
    """Upgrade only inert metadata to @8; no RNG getter, owner or native call."""
    inventory = launch.initial_rng.inputs.inventory(Path(b.inputs["program"]["root"]))
    bundle_value = launch.read(b.pair_pin)
    bundle_value["source_inventory"] = inventory
    b.pair_pin.update(write(Path(b.pair_pin["path"]), bundle_value))
    declaration = launch.read(b.plan["demo_plan"])
    declaration.update(
        kind=launch.RNG_DEMO_KIND,
        initial_rng_inputs=dict(
            profile="original",
            inventory=inventory,
            inventory_sha256=launch.initial_rng.seal(inventory),
        ),
    )
    manifest = launch.read(b.plan["source_snapshot"])
    declaration.setdefault("source_plan", {})["initial_rng_observation"] = dict(
        kind=launch.initial_rng.LEGACY_KIND if witness_version == 1 else launch.initial_rng.KIND,
        epoch=launch.initial_rng.EPOCH,
        boundary="after_issued_WorldReady_before_geometry_phase_construction",
        full_numpy_MT_and_python_state=True,
        complete_input_inventory_bound=True,
        reset_draw_or_replacement=False,
        common_starting_authority_established=False,
        producer="validation.betse.native_seed_initial_rng",
        producer_sha256=manifest["files"][launch.initial_rng.FILE]["sha256"],
        **(
            dict(
                runtime_producer="validation.betse.native_rng_runtime",
                runtime_producer_sha256=manifest["files"][launch.initial_rng.rng_runtime.FILE][
                    "sha256"
                ],
            )
            if witness_version == 2
            else {}
        ),
    )
    declaration_pin = write(b.packet / "demo-plan.json", declaration)
    made = launch.prepare(
        b.packet,
        b.root / "rng-plan",
        demo_plan_sha256=declaration_pin["sha256"],
        release_environment=b.env,
        input_bundle=b.pair_pin,
    )
    b.path, b.sha = Path(made["plan"]["path"]), made["plan"]["sha256"]
    b.plan = launch.read(made["plan"])
    return b


@pytest.mark.parametrize("mutation", (None, "helper", "source", "version", "producer"))
def test_launch_rng_origin_version2_binds_helper_before_source(bundle, mutation):
    b = initial_rng_bundle(bundle, witness_version=2)
    declared = launch.read(b.plan["demo_plan"])
    assert declared["source_plan"]["initial_rng_observation"]["kind"] == launch.initial_rng.KIND
    assert launch.initial_rng.rng_runtime.FILE in b.plan["producers"]
    assert launch.verify(b.path, b.sha) == b.plan
    if mutation is None:
        return
    plan = dict(b.plan)
    if mutation == "helper":
        del plan["producers"][launch.initial_rng.rng_runtime.FILE]
    else:
        policy = declared["source_plan"]["initial_rng_observation"]
        if mutation == "source":
            policy["runtime_producer_sha256"] = "0" * 64
        elif mutation == "version":
            policy["kind"] = "unknown"
        else:
            policy["runtime_producer"] = "foreign.runtime"
        plan["demo_plan"] = write(Path(plan["demo_plan"]["path"]), declared)
    selected = write(b.path, plan)
    with pytest.raises(ValueError):
        launch.verify(b.path, selected["sha256"])


def test_launch_initial_rng_full_bundle_and_source_bound_without_getters(bundle, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Metadata launch must not observe or manipulate RNG state")

    monkeypatch.setattr(launch.initial_rng, "observe", forbidden)
    monkeypatch.setattr(launch.initial_rng, "read_states", forbidden)
    b = initial_rng_bundle(bundle)
    result = launch.verify(b.path, b.sha)
    assert result["initial_rng_inputs"]["inventory"]["directories"] == ["geo"]
    assert set(result["initial_rng_inputs"]["inventory"]["files"]) == {
        "config.json",
        "geo/image.png",
    }
    assert launch.initial_rng.FILE in result["producers"]
    assert result["kind"] == "cells.genuine_seed_demo_detached_launch@12"
    assert (
        launch.read(result["demo_plan"])["source_plan"]["initial_rng_observation"][
            "common_starting_authority_established"
        ]
        is False
    )
    release = launch.prepare_release(b.path, b.path.parent / "release.json", plan_sha256=b.sha)
    assert (
        launch.verify_release(result, b.sha, Path(release["path"]), release["sha256"])[
            "demo_plan_sha256"
        ]
        == result["demo_plan"]["sha256"]
    )
    write(
        b.root / "rng-metadata-proof.json",
        dict(plan=result, release=release, native_or_rng_getter_calls=0),
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_launch_inputs",
        "different_profile",
        "missing_directory",
        "missing_file",
        "wrong_size",
        "boolean_size",
        "wrong_digest",
        "missing_producer",
        "wrong_producer",
        "authority_claim",
        "reset_claim",
        "wrong_epoch",
        "wrong_source",
        "legacy_relabel",
    ),
)
def test_launch_initial_rng_rejects_resealed_input_source_or_authority_drift(bundle, mutation):
    b = initial_rng_bundle(bundle)
    assert launch.verify(b.path, b.sha)["initial_rng_inputs"]
    plan = copy.deepcopy(b.plan)
    declaration = launch.read(plan["demo_plan"])
    selected = declaration["initial_rng_inputs"]
    policy = declaration["source_plan"]["initial_rng_observation"]
    if mutation == "missing_launch_inputs":
        del plan["initial_rng_inputs"]
    elif mutation == "different_profile":
        selected["profile"] = "headless"
    elif mutation == "missing_directory":
        selected["inventory"]["directories"] = []
    elif mutation == "missing_file":
        del selected["inventory"]["files"]["geo/image.png"]
    elif mutation in ("wrong_size", "boolean_size"):
        selected["inventory"]["files"]["geo/image.png"]["size_bytes"] = (
            True if mutation == "boolean_size" else 1
        )
    elif mutation == "wrong_digest":
        selected["inventory_sha256"] = "0" * 64
    elif mutation == "missing_producer":
        del plan["producers"][launch.initial_rng.FILE]
    elif mutation == "wrong_producer":
        plan["producers"][launch.initial_rng.FILE] = "0" * 64
    elif mutation == "authority_claim":
        policy["common_starting_authority_established"] = True
    elif mutation == "reset_claim":
        policy["reset_draw_or_replacement"] = True
    elif mutation == "wrong_epoch":
        policy["epoch"] = "after_geometry"
    elif mutation == "wrong_source":
        policy["producer_sha256"] = "0" * 64
    else:
        declaration["kind"] = "cells.genuine_seed_core_profiles_junctions_demo@7"
    plan["demo_plan"] = write(b.packet / "demo-plan.json", declaration)
    with pytest.raises((ValueError, KeyError)):
        launch._immutable(plan)
    write(
        b.root / "rng-declared-refusal.json",
        dict(mutation=mutation, plan=plan, declaration=declaration),
    )


def test_launch_initial_rng_old_demo_has_no_implicit_observation(bundle):
    value = launch.verify(bundle.path, bundle.sha)
    assert "initial_rng_inputs" not in value and launch.initial_rng.FILE not in value["producers"]
    assert launch.read(value["demo_plan"]).get("kind") != launch.RNG_DEMO_KIND


def sim_bundle(b):
    """A complete byte-bound synthetic SIM plan; none of these files is imported."""
    b = initial_rng_bundle(b)
    native = launch.BASE / "betse-v1.5.0/betse"
    native.mkdir(parents=True, exist_ok=True)
    (native / "metadata_fixture.py").write_text("# inert original-source inventory fixture\n")
    source, manifest = b.source, launch.read(b.plan["source_snapshot"])
    for directory in [source, *[p for p in source.rglob("*") if p.is_dir()]]:
        directory.chmod(0o755)
    pins = {}
    for name, relative in zip(launch.SIM_MODULES, launch.SIM_FILES, strict=True):
        p = source / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# inert stage for byte-binding controls\n")
        p.chmod(0o444)
        pins[name] = launch.pin(p)["sha256"]
    helper = source / launch.SIM_FILE
    helper.write_text(
        "MODULES = "
        + repr(launch.SIM_MODULES)
        + "\nSOURCE_PINS = "
        + repr(pins)
        + "\nREVIEW_PINS = "
        + repr(dict.fromkeys(pins, "b" * 64))
        + "\n"
    )
    helper.chmod(0o444)
    observation_policy = observed.saved_policy(source, b.root / "observation-reviews", pins["run"])
    for relative in (
        launch.SIM_FILE,
        *launch.SIM_FILES,
        launch.sim_observation.FILE,
        launch.sim_observation.OBSERVER,
        launch.sim_observation.WRITER,
        launch.sim_observation.HISTORY,
    ):
        p = source / relative
        manifest["files"][relative] = dict(
            checkout_path=relative,
            sha256=launch.pin(p)["sha256"],
            observation=dict(size=p.stat().st_size),
            snapshot_mode=0o444,
        )
    (source / "SNAPSHOT.json").chmod(0o644)
    snapshot_pin = write(source / "SNAPSHOT.json", manifest)
    (source / "SNAPSHOT.json").chmod(0o444)
    for directory in reversed([source, *[p for p in source.rglob("*") if p.is_dir()]]):
        directory.chmod(0o555)
    b.inputs.update(
        source_snapshot=snapshot_pin, acquisition_sequence=list(launch.ACQUISITION_SEQUENCE)
    )
    inputs_pin = write(b.packet / "inputs.json", b.inputs)
    declaration = launch.read(b.plan["demo_plan"])
    declaration.update(
        kind=launch.SIM_DEMO_KIND,
        endpoint=launch.SIM_ENDPOINT,
        init_iterations=None,
        parameter_sha256=inputs_pin["sha256"],
        snapshot_sha256=snapshot_pin["sha256"],
    )
    declaration["source_plan"]["optional_init_terminal"] = dict(
        maximum_iterations=512,
        init_iterations=None,
        full_original_calendar=True,
        normal_loop_context_and_caller_return=True,
        selected_stop=False,
        before_native_pickle=True,
    )
    declaration["source_plan"]["optional_sim_terminal"] = dict(
        module="validation.betse.native_sim_demo",
        source_sha256=launch.pin(helper)["sha256"],
        review_sha256="b" * 64,
        acquisition_sequence=list(launch.ACQUISITION_SEQUENCE),
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
    declaration_pin = write(b.packet / "demo-plan.json", declaration)
    b.env.update(
        dict.fromkeys(
            (
                *launch.SIM_GATES,
                launch.sim_observation.RELEASE,
                launch.sim_observation.HISTORY_RELEASE,
            ),
            "1",
        )
    )
    b.parameter.packet_inputs = lambda packet, digest: (
        b.inputs
        if Path(packet) == b.packet and digest == inputs_pin["sha256"]
        else pytest.fail("Wrong parameter packet")
    )
    made = launch.prepare(
        b.packet,
        b.root / "sim-plan",
        demo_plan_sha256=declaration_pin["sha256"],
        release_environment=b.env,
        input_bundle=b.pair_pin,
    )
    b.path, b.sha = Path(made["plan"]["path"]), made["plan"]["sha256"]
    b.plan = launch.read(made["plan"])
    release = launch.prepare_release(b.path, b.path.parent / "sim-release.json", plan_sha256=b.sha)
    b.release, b.release_sha = Path(release["path"]), release["sha256"]
    return b


def sim_return(count=3, *, record=None):
    trial = NS(
        identity="a" * 64,
        iterations=tuple(range(count)),
        report_returned=True,
        loop_returned=True,
        context_returned=True,
        before_native_pickle=True,
    )
    return NS(
        methods_completed=True,
        evidence_completed=True,
        primary=None,
        secondary=[],
        endpoint="sim_terminal",
        flux_operator="original",
        init_iterations=None,
        init_terminal_completed=True,
        init_first_step_completed=False,
        init_short_history_completed=False,
        init_time_steps_completed=500,
        sim_time_steps_completed=count,
        sim_trial=trial,
        sim_completed=True,
        sim_observation=NS(
            completed=True,
            cleanup_complete=True,
            primary=None,
            secondary=[],
            record_pin=record,
            started=True,
            rows=[],
            raw_return={},
            partial=None,
        ),
        sim_imports_complete=True,
        sim_cleanup_complete=True,
        sim_metadata_stopped=False,
        sim_secondary=[],
        sim_linkage=dict(
            trial_identity=trial.identity,
            configured_iterations=count,
            maximum_iterations=512,
            selected_stop=False,
            complete_configured_calendar=True,
            report_returned=True,
            loop_returned=True,
            context_returned=True,
            before_native_pickle=True,
            same_retained_simulator_and_cells=True,
            distinct_current_parameters=True,
        ),
    )


@pytest.mark.parametrize("count", (1, 500, 512))
def test_launch_sim_complete_worker_retains_direct_schema_and_whole_counts(
    bundle, monkeypatch, count
):
    b = sim_bundle(bundle)
    assert launch.verify(b.path, b.sha)["kind"] == launch.SIM_KIND
    assert b.plan["acquisition_sequence"] == list(launch.ACQUISITION_SEQUENCE)
    calls = []

    def public(path, output, **kwargs):
        calls.append(path)
        output.mkdir()
        return sim_return(count, record=write(output / "record.json", {"synthetic": True}))

    worker_setup(b, monkeypatch, public)
    result = launch.worker(b.path, b.root / "worker", **kwargs(b))
    assert result["kind"] == launch.SIM_KIND and result["endpoint"] == "sim_terminal"
    assert len(calls) == 1 and result["scientific_credit"] == 0


@pytest.mark.parametrize(
    "mutation",
    (
        "old_launch",
        "old_demo",
        "missing_sequence",
        "one_load",
        "gate",
        "helper_pin",
        "review_pin",
        "selected_stop",
    ),
)
def test_launch_sim_preflight_rejects_resealed_contract_changes(bundle, mutation):
    b = sim_bundle(bundle)
    if mutation == "old_launch":
        b.plan["kind"] = launch.KIND
    elif mutation == "missing_sequence":
        del b.plan["acquisition_sequence"]
    elif mutation == "gate":
        del b.plan["release_environment"][launch.SIM_GATES[0]]
    else:
        declaration = launch.read(b.plan["demo_plan"])
        if mutation == "old_demo":
            declaration["kind"] = launch.RNG_DEMO_KIND
        elif mutation == "one_load":
            b.inputs["acquisition_sequence"] = ["initial_world_ready"]
            pin = write(b.packet / "inputs.json", b.inputs)
            b.plan["parameter_inputs"] = pin
            declaration["parameter_sha256"] = pin["sha256"]
        else:
            key = {
                "helper_pin": "source_sha256",
                "review_pin": "review_sha256",
                "selected_stop": "selected_stop",
            }[mutation]
            declaration["source_plan"]["optional_sim_terminal"][key] = (
                True if mutation == "selected_stop" else None
            )
        b.plan["demo_plan"] = write(b.packet / "demo-plan.json", declaration)
    with pytest.raises((ValueError, KeyError)):
        launch._immutable(b.plan)


@pytest.mark.parametrize(
    "field,value",
    (
        ("sim_completed", False),
        ("sim_time_steps_completed", True),
        ("sim_time_steps_completed", 513),
        ("sim_imports_complete", False),
        ("sim_cleanup_complete", False),
        ("sim_metadata_stopped", True),
        ("sim_secondary", [("capture", "failed")]),
        ("context_returned", False),
        ("loop_returned", False),
        ("before_native_pickle", False),
    ),
)
def test_launch_sim_incomplete_return_retains_failure_without_terminal(
    bundle, monkeypatch, field, value
):
    b = sim_bundle(bundle)
    returned = sim_return(record=write(b.root / "record.json", {"synthetic": True}))
    setattr(
        returned.sim_trial
        if field in ("context_returned", "loop_returned", "before_native_pickle")
        else returned,
        field,
        value,
    )

    def public(path, output, **kwargs):
        output.mkdir()
        return returned

    worker_setup(b, monkeypatch, public)
    with pytest.raises(ValueError):
        launch.worker(b.path, b.root / "worker", **kwargs(b))
    failure = launch.read(launch.pin(b.root / "worker/failure.json"))
    assert failure["state"]["public_entry_returned"] is True
    assert failure["kind"] == launch.SIM_KIND
    assert not (b.root / "worker/result.json").exists()


def test_launch_sim_explicit_gate_roster_matches_actual_selected_entries(bundle, tmp_path):
    """Read selected public-entry declarations without importing any owner."""
    source_root = Path(__file__).resolve().parents[2]
    selected = (
        ("betse_native_init_sim_preparation", "prepare", "RELEASE"),
        ("betse_native_init_terminal", "reserve_for_sim", "SIM_RESERVATION_RELEASE"),
        ("betse_native_init_sim_assembly", "prepare", "RELEASE"),
        ("betse_native_init_sim_assembly", "reserve_for_run", "RUN_RESERVATION_RELEASE"),
        ("betse_native_sim_run", "prepare", "RELEASE"),
    )
    required, declarations = [], []
    for module, name, constant in selected:
        path = source_root / "src/cells/processes" / (module + ".py")
        tree = ast.parse(path.read_bytes())
        assignments = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == constant
        ]
        assert len(assignments) == 1
        gate = ast.literal_eval(assignments[0].value)
        function = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
        )
        lookups = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and ast.unparse(node.func) == "os.environ.get"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == constant
        ]
        assert len(lookups) == 1
        required.append(gate)
        declarations.append(
            dict(
                source=launch.pin(path),
                function=name,
                line=function.lineno,
                constant=constant,
                gate=gate,
            )
        )
    assert tuple(required) == launch.SIM_GATES and len(set(required)) == 5
    before = {name: os.environ.get(name) for name in required}
    b = sim_bundle(bundle)
    assert all(b.plan["release_environment"][name] == "1" for name in required)
    assert launch.verify(b.path, b.sha)["kind"] == launch.SIM_KIND
    assert b.plan["limitations"]["sim_terminal"]["explicit_release_flags"] == required
    assert {name: os.environ.get(name) for name in required} == before
    write(
        tmp_path / "actual-selected-gates.json",
        dict(declarations=declarations, declared_only=True, native_source_or_owner_executed=False),
    )


@pytest.mark.parametrize("gate", launch.SIM_GATES)
@pytest.mark.parametrize("value", (None, "0", 1), ids=("absent", "disabled", "wrong_type"))
def test_launch_sim_explicit_gate_refusal_before_entry(bundle, gate, value):
    b = sim_bundle(bundle)
    if value is None:
        del b.plan["release_environment"][gate]
    else:
        b.plan["release_environment"][gate] = value
    with pytest.raises(ValueError, match="Explicit actual SIM release flags required"):
        launch._immutable(b.plan)
    assert not (b.root / "worker").exists()


@pytest.mark.parametrize(
    "mutation", ("gate_missing", "gate_wrong", "pin", "review", "writer", "policy", "originals")
)
def test_launch_sim_observation_contract_is_explicit_before_entry(bundle, mutation):
    b = sim_bundle(bundle)
    declaration = launch.read(b.plan["demo_plan"])
    policy = declaration["source_plan"]["optional_sim_terminal"]["completed_observation"]
    if mutation.startswith("gate"):
        b.plan["release_environment"][launch.sim_observation.RELEASE] = (
            None if mutation == "gate_missing" else "0"
        )
    elif mutation == "pin":
        policy["observer_sha256"] = "0" * 64
    elif mutation == "review":
        policy["observer_review"]["sha256"] = "0" * 64
    elif mutation == "writer":
        policy["writer_sha256"] = "0" * 64
    elif mutation == "policy":
        policy["already_typed_transport"] = False
    else:
        b.plan["sim_original_sources"]["sha256"] = "0" * 64
    b.plan["demo_plan"] = write(b.packet / "demo-plan.json", declaration)
    with pytest.raises(ValueError):
        launch._immutable(b.plan)


@pytest.mark.parametrize("value", (None, "0", True))
def test_launch_sim_history_release_is_separate_and_required_before_source(bundle, value):
    b = sim_bundle(bundle)
    assert len(launch.SIM_GATES) == 5
    assert launch.sim_observation.HISTORY_RELEASE not in launch.SIM_GATES
    if value is None:
        del b.plan["release_environment"][launch.sim_observation.HISTORY_RELEASE]
    else:
        b.plan["release_environment"][launch.sim_observation.HISTORY_RELEASE] = value
    with pytest.raises(ValueError, match="completed-history observation release"):
        launch._immutable(b.plan)
    assert not (b.root / "worker").exists()


def test_launch_sim_history_source_and_release_are_explicit_in_prepared_plan(bundle):
    b = sim_bundle(bundle)
    launch._immutable(b.plan)
    declaration = launch.read(b.plan["demo_plan"])
    assert launch.sim_observation.HISTORY in launch._producers(declaration)
    assert (
        b.plan["producers"][launch.sim_observation.HISTORY]
        == launch.pin(Path(b.plan["source"]) / launch.sim_observation.HISTORY)["sha256"]
    )
    assert b.plan["release_environment"][launch.sim_observation.HISTORY_RELEASE] == "1"
    assert b.plan["limitations"]["sim_terminal"]["history_release"] == (
        launch.sim_observation.HISTORY_RELEASE
    )


@pytest.mark.parametrize("fault", ("source_missing", "source_changed", "policy_module"))
def test_launch_sim_history_binding_refuses_before_worker_creation(bundle, fault):
    b = sim_bundle(bundle)
    if fault == "source_missing":
        del b.plan["producers"][launch.sim_observation.HISTORY]
    elif fault == "source_changed":
        target = Path(b.plan["source"]) / launch.sim_observation.HISTORY
        target.chmod(0o644)
        target.write_text(target.read_text() + "# changed declaration\n")
    else:
        declaration = launch.read(b.plan["demo_plan"])
        declaration["source_plan"]["optional_sim_terminal"]["completed_observation"][
            "history_module"
        ] = "cells.processes.foreign"
        b.plan["demo_plan"] = write(b.packet / "demo-plan.json", declaration)
    with pytest.raises(ValueError):
        launch._immutable(b.plan)
    assert not (b.root / "worker").exists()


@pytest.mark.parametrize(
    "field,value",
    (
        ("completed", False),
        ("cleanup_complete", False),
        ("primary", OSError("capture")),
        ("secondary", [("writer", OSError("secondary"))]),
        ("record_pin", None),
    ),
)
def test_launch_sim_missing_observation_cannot_be_success(tmp_path, field, value):
    returned = sim_return(record=write(tmp_path / "record.json", {"scope": "synthetic"}))
    setattr(returned.sim_observation, field, value)
    with pytest.raises(ValueError, match="observation"):
        launch._sim_return(returned)
