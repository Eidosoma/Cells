"""Native-blocked launch metadata controls; private fixtures issue no owners."""

import copy
import json
import os
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType
from types import SimpleNamespace as NS

import pytest

from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import native_seed_demo_launch as launch
from validation.betse import native_seed_demo_launch_software as software

_RAW_GUARDS = []


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
    adapter = NS(**dict(vars(software), reuse=software.base.reuse.reuse))
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
    for name in launch.PRODUCERS:
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


@pytest.mark.parametrize("endpoint", ["seed", "init_setup", "init_prelude"])
def test_launch_endpoint_is_bound_to_exact_demo_declaration(bundle, endpoint):
    b = bundle
    declaration = launch.read(b.plan["demo_plan"])
    declaration["endpoint"] = endpoint
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
    assert b.calls == ["initial-directory-epoch"]


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
