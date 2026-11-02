"""Prepared blocked controls. Not executed by source-only development.

No genuine positive parent is synthesized. Source compilation, refusal paths
and observation/data-association helpers are checked independently; a future
positive continuity run requires Root's actual constants/handoff authority.
"""

import ast
import builtins
import json
import sys
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_load_remainder as stage
from tests.unit import test_betse_native_parameter_initializer_constants as inherited
from validation.betse import betse_native_parameter_load_remainder_software as runner
from validation.betse import betse_native_parameter_world_construction_software as world_runner
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
)

blocked = inherited.blocked
prevent_reference_execution = inherited.prevent_reference_execution


def test_exact_tail_profile_branches_and_helper_source_without_execution():
    plan = stage.source_plan()
    assert plan["statement_slice"] == (203, 218) and plan["source_lines"] == (1127, 1154)
    assert plan["load_cursor"] == 218 and plan["replaces"] == ("wsx", "wsy")
    assert len(plan["tail_stores"]) == 14 and len(plan["profile_union"]) == 24
    assert tuple(row[0] for row in plan["profiles"]) == stage.PROFILE_NAMES
    assert plan["profile_lines"] == (1265, 1496) and plan["balance_lines"] == (1569, 1605)
    assert (
        not plan["native_bodies_copied_or_rewritten"] and not plan["public_module_globals_patched"]
    )
    assert not plan["material_phase_world_science_admitted"]
    _, _, _, tail, _, _ = stage._source()
    assert [node.targets[0].attr for node in tail[:5]] == ["d_cell", "nx", "ny", "wsx", "wsy"]
    assert all("vol_env" not in ast.unparse(node) for node in tail)


def _compiled_shape():
    module = ModuleType("conditional-original-parameter-namespace")
    vars(module)["__builtins__"] = vars(builtins)

    def forbidden(self):
        raise AssertionError("Source compilation is not permission to run")

    original = FunctionType(forbidden.__code__, vars(module), "load")
    context = SimpleNamespace(
        parent=SimpleNamespace(function=original), api=SimpleNamespace(namespace=vars(module))
    )
    return module, context


def test_compile_transports_actual_iu_and_keeps_original_tail_ast():
    module, context = _compiled_shape()
    function = stage._compile(context)
    path, cls, _, selected, _, _ = stage._source()
    transport = ast.parse("iu = kwargs[" + repr(stage.LOCAL_KEY) + "]").body[0]
    stage.prefix.parameters.inherited._method(cls, "load").body = [transport, *selected]
    expected = stage.prefix.parameters._method_code(cls, "load", str(path))
    assert stage.prefix.parameters.inherited._code(
        function.__code__
    ) == stage.prefix.parameters.inherited._code(expected)
    assert function.__globals__ is vars(module)
    assert function.__builtins__ is context.parent.function.__builtins__
    assert (
        "_load_ion_profile" in function.__code__.co_names
        and stage.LOCAL_KEY in function.__code__.co_consts
    )


@pytest.mark.parametrize("mode", ["valid", "code", "namespace", "cached-builtins", "defaults"])
def test_original_helper_correspondence_rejects_static_drift_without_call(mode):
    module, _ = _compiled_shape()
    path, _, _, _, _, node = stage._source()
    code = stage.previous.previous.boundary._code(node, str(path), node.name)
    namespace = vars(module)
    function = FunctionType(code, namespace, node.name)
    if mode == "code":
        function.__code__ = (lambda a, b: None).__code__
    elif mode == "namespace":
        function = FunctionType(code, dict(namespace), node.name)
    elif mode == "cached-builtins":
        namespace["__builtins__"] = dict(vars(builtins))
        function = FunctionType(code, namespace, node.name)
        namespace["__builtins__"] = vars(builtins)
    elif mode == "defaults":
        function.__defaults__ = ()
    if mode == "valid":
        assert stage._canonical(function, code, namespace)
    else:
        with pytest.raises(ValueError):
            stage._canonical(function, code, namespace)


@pytest.mark.parametrize("mode", ["default", "integer", "local", "constants", "law"])
def test_gate_refuses_before_hook_or_parameter_work(monkeypatch, mode):
    for name in (
        stage.RELEASE,
        stage.previous.RELEASE,
        stage.previous.previous.RELEASE,
        stage.previous.previous.mod.RELEASE,
    ):
        monkeypatch.setenv(name, "1")
    if mode in ("local", "constants"):
        monkeypatch.setenv(stage.RELEASE if mode == "local" else stage.previous.RELEASE, "0")
    enabled = False if mode == "default" else 1 if mode == "integer" else True

    def forbidden():
        raise AssertionError("Hook must not be reached")

    monkeypatch.setattr(stage, "_hook", forbidden)
    with pytest.raises(stage.LoadRejected) as caught:
        stage.complete_load(
            None, law_id="wrong" if mode == "law" else stage.LAW_ID, enabled=enabled
        )
    assert caught.value.stage == ("law" if mode == "law" else "release")


def test_missing_predecessor_hook_is_executable_prework_refusal(monkeypatch):
    for name in (
        stage.RELEASE,
        stage.previous.RELEASE,
        stage.previous.previous.RELEASE,
        stage.previous.previous.mod.RELEASE,
    ):
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(stage, "HANDOFF_PRODUCER_SHA256", None)
    before = len(stage._CONSUMED)
    with pytest.raises(stage.LoadRejected) as caught:
        stage.complete_load(None, law_id=stage.LAW_ID, enabled=True)
    assert caught.value.stage == "predecessor_handoff" and len(stage._CONSUMED) == before


def test_raw_helper_return_survives_observer_copy_failure(monkeypatch):
    context = SimpleNamespace(raw_return=None, raw_returns=[], returns={"balance": []}, locals={})
    frame, value = object(), (object(), object())
    primary = SyntheticCaptureFailure("metadata copy refused")

    def bad(frame):
        raise primary

    monkeypatch.setattr(stage, "_copy_locals", bad)
    with pytest.raises(SyntheticCaptureFailure) as caught:
        stage._returned(context, "balance", frame, value)
    assert caught.value is primary and context.raw_return == ("balance", frame, value)
    assert context.raw_returns[0][2] is value and context.returns["balance"][0] is value


@pytest.mark.parametrize("mode", ["valid", "helper-edge", "roster", "volume", "selector"])
def test_output_association_helper_requires_complete_original_data_graph(mode):
    # A data-check fixture, never an issued parameter/WorldReady owner.
    plan = stage.source_plan()
    members = tuple((name, object()) for name in stage.PROFILE_NAMES)
    fields = {"vol_env": object(), "wsx": object(), "wsy": object()}
    before = tuple(fields)
    volume = fields["vol_env"]
    profile_fields = plan["profiles"][0][1]
    for name in (*plan["tail_stores"], *profile_fields):
        if name not in fields:
            fields[name] = object()
    a, b, c, d = object(), object(), object(), object()
    fields.update(conc_env_m=a, z_M_env=b, cM_cell=c, z_M_cell=d)
    p = SimpleNamespace(**fields)
    base, internal = object(), {}
    context = SimpleNamespace(
        p=p,
        api=SimpleNamespace(members=members, base=base),
        plan=plan,
        before_names=before,
        original_volume=volume,
        internal=internal,
        entries=dict(tail=1, ion=1, balance=2, ion_alias=1),
        delegates=dict(tail=1, ion=1, balance=2, ion_alias=1),
        invocation_attempts=1,
        source_instructions=1,
        returns=dict(tail=[None], ion=[None], balance=[(a, b), (c, d)], ion_alias=[members[0][1]]),
        locals=dict(ion=dict(base=base), tail=dict(iu=internal)),
    )
    if mode == "helper-edge":
        p.cM_cell = object()
    elif mode == "roster":
        p.foreign = 1
    elif mode == "volume":
        p.vol_env = object()
    elif mode == "selector":
        context.returns["ion_alias"] = [object()]
    if mode == "valid":
        assert stage._outputs(context) == "BASIC"
    else:
        with pytest.raises(ValueError):
            stage._outputs(context)


def test_software_launch_is_held_before_packet_access(monkeypatch, tmp_path):
    monkeypatch.delenv(runner.SOFTWARE_RELEASE, raising=False)
    with pytest.raises(ValueError, match="remains held"):
        runner.software(tmp_path / "missing", tmp_path / "output")
    assert not (tmp_path / "output").exists()


class _FalseySourceFailure(SyntheticSourceFailure):
    def __bool__(self):
        return False


@pytest.fixture
def observed(monkeypatch):
    """Actual Python observer events on toy code, never original source/laws."""
    bodies, control = [], dict(fail=False)
    member = object()
    primary, cause = _FalseySourceFailure("toy original primary"), SyntheticSourceCause("toy cause")

    def nested():
        return "toy witness"

    def getter(self_descriptor, self, cls):
        bodies.append("alias")
        return member

    alias = type("ConditionalAlias", (), {"__get__": getter})()

    def balance(concentrations, zs):
        bodies.append("balance")
        nested()
        if control["fail"]:
            raise primary from cause
        return ("toy compensation", "toy charge")

    def ion(self):
        bodies.append("ion")
        selected = self.ion_profile
        conc_env, zs = ["a", "b", "c"], ["z", "z", "z"]
        self.env, self.ze = balance(conc_env, zs)
        self.after_first = selected
        conc_cell = ["d", "e", "f"]
        self.cell, self.zc = balance(conc_cell, zs)
        self.after_second = True

    def tail(self, **kwargs):
        bodies.append("tail")
        try:
            self._load_ion_profile()
            self.after_ion = True
        finally:
            self.tail_finalized = True

    cls = type("ConditionalParameters", (), {"ion_profile": alias, "_load_ion_profile": ion})
    p = cls()
    tree = ast.parse(Path(__file__).read_text())

    def node(fn):
        return next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == fn.__name__
            and n.lineno == fn.__code__.co_firstlineno
        )

    ion_node, tail_node = node(ion), node(tail)
    calls = sorted(
        (
            n
            for n in ast.walk(ion_node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "balance"
        ),
        key=lambda n: n.lineno,
    )
    attr = next(
        n for n in ast.walk(ion_node) if isinstance(n, ast.Attribute) and n.attr == "ion_profile"
    )
    invoke = next(
        n
        for n in ast.walk(tail_node)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "_load_ion_profile"
    )
    sites = dict(
        ion=stage._spans(tail.__code__, [invoke], "CALL"),
        balance=stage._spans(ion.__code__, calls, "CALL"),
        balance_arguments=(("conc_env", "zs"), ("conc_cell", "zs")),
        ion_alias=stage._spans(ion.__code__, [attr], "LOAD_ATTR"),
    )
    context = SimpleNamespace(
        function=tail,
        p=p,
        internal=object(),
        active=True,
        invalid=False,
        thread=stage.get_ident(),
        source_error=None,
        capture_errors=(),
        work=[],
        raw_return=None,
        raw_returns=[],
        raw_entry=None,
        returns=dict(tail=[], ion=[], balance=[], ion_alias=[]),
        entries=dict(tail=0, ion=0, balance=0, ion_alias=0),
        balance_inputs=[],
        locals={},
        api=SimpleNamespace(
            ion=ion,
            balance=balance,
            getter=getter,
            alias=alias,
            cls=cls,
            members=(("BASIC", member),),
        ),
    )
    monkeypatch.setattr(stage, "_call_sites", lambda actual: sites if actual is context else None)
    return SimpleNamespace(
        context=context,
        bodies=bodies,
        control=control,
        primary=primary,
        cause=cause,
        nested=nested,
        tail=tail,
        ion=ion,
        balance=balance,
    )


def test_real_observer_toy_nested_frames_and_attempts_are_not_cases(observed):
    h = observed
    with stage._observe(h.context):
        stage._invoke(h.context)
    assert h.context.entries == h.context.delegates == dict(tail=1, ion=1, balance=2, ion_alias=1)
    assert h.bodies == ["tail", "ion", "alias", "balance", "balance"]
    assert h.context.p.after_ion and h.context.p.tail_finalized
    assert h.context.observer_recovery["clean"] and not h.context.capture_errors


@pytest.mark.parametrize("kind", ["locals", "inherited-return", "inherited-nested"])
@pytest.mark.parametrize("source_error", [False, True])
def test_real_observer_stops_first_safe_boundary_and_preserves_falsey_unwind(
    observed, monkeypatch, kind, source_error
):
    h = observed
    h.control["fail"] = source_error
    prior = sys.getprofile()
    selected = h.nested.__code__ if kind == "inherited-nested" else h.balance.__code__
    original_copy = stage._copy_locals

    def copy(frame):
        if frame.f_code is h.balance.__code__:
            raise SyntheticCaptureFailure("toy return locals failure")
        return original_copy(frame)

    def hook(frame, event, arg):
        if frame.f_code is selected and event == "return":
            raise SyntheticCaptureFailure("toy inherited return failure")
        if prior is not None:
            prior(frame, event, arg)

    if kind == "locals":
        monkeypatch.setattr(stage, "_copy_locals", copy)
    else:
        sys.setprofile(hook)
    try:
        expected = (
            _FalseySourceFailure
            if source_error and kind != "inherited-nested"
            else stage._ObservationStop
        )
        with pytest.raises(expected) as caught:
            with stage._observe(h.context):
                stage._invoke(h.context)
    finally:
        sys.setprofile(prior)
    if expected is _FalseySourceFailure:
        assert caught.value is h.primary and h.primary.__cause__ is h.cause
        assert h.context.observer_state.primary is h.primary
    assert h.bodies.count("balance") == 1 and h.context.delegates["balance"] == 1
    assert not hasattr(h.context.p, "env") and not hasattr(h.context.p, "after_first")
    assert not hasattr(h.context.p, "after_ion")
    assert h.context.raw_returns and h.context.invalid and h.context.capture_errors


@pytest.mark.parametrize("kind", ["same", "next", "raw-ion", "raw-tail"])
def test_real_inherited_callback_raw_entry_is_counted_poisoned_and_cannot_be_caught(observed, kind):
    h = observed
    prior, refused = sys.getprofile(), []
    selected = h.ion if kind == "raw-ion" else h.tail if kind == "raw-tail" else h.balance
    event = "return" if kind == "next" else "call"
    fired = False

    def hook(frame, what, arg):
        nonlocal fired
        if not fired and frame.f_code is selected.__code__ and what == event:
            fired = True
            try:
                if kind == "raw-ion":
                    h.ion(h.context.p)
                elif kind == "raw-tail":
                    h.tail(h.context.p)
                else:
                    h.balance(["x", "y", "z"], ["q", "q", "q"])
            except ValueError as error:
                refused.append(error)
        if prior is not None:
            prior(frame, what, arg)

    sys.setprofile(hook)
    try:
        with pytest.raises(stage._ObservationStop):
            with stage._observe(h.context):
                stage._invoke(h.context)
    finally:
        sys.setprofile(prior)
    role = "ion" if kind == "raw-ion" else "tail" if kind == "raw-tail" else "balance"
    assert fired and len(refused) == 1 and h.context.entries[role] == 2
    assert h.context.invalid and h.context.observer_state.rejections[0] is refused[0]
    assert h.context.delegates[role] == (1 if kind == "next" else 0)
    assert not hasattr(h.context.p, "after_first")


@pytest.mark.parametrize("failure", ["before", "after", "clear-other", "persistent"])
def test_dual_hook_recovery_samples_after_both_actions_and_never_erases_failure(failure):
    expected_profile, expected_trace = object(), object()
    current = dict(profile=object(), trace=object())
    calls = []

    def profile(value):
        calls.append("profile")
        if failure in ("before", "persistent") and (
            calls.count("profile") == 1 or failure == "persistent"
        ):
            raise SyntheticCaptureFailure("profile before setter")
        current["profile"] = value
        if failure == "after" and calls.count("profile") == 1:
            raise SyntheticCaptureFailure("profile after setter")

    def trace(value):
        calls.append("trace")
        current["trace"] = value
        if failure == "clear-other" and calls.count("trace") == 1:
            current["profile"] = None

    result = stage._recover_hooks(
        expected_profile,
        expected_trace,
        set_profile=profile,
        set_trace=trace,
        get_profile=lambda: current["profile"],
        get_trace=lambda: current["trace"],
    )
    assert calls.count("profile") <= 3 and "trace" in calls
    assert result["errors"] and not result["clean"]
    assert result["identities_match"] is (failure != "persistent")
    assert (
        result["final_profile"] is current["profile"] and result["final_trace"] is current["trace"]
    )


def test_observer_bookkeeping_failure_preserves_falsey_primary_and_both_hooks(
    observed, monkeypatch
):
    h = observed
    h.control["fail"] = True
    prior, trace = sys.getprofile(), sys.gettrace()

    def refused(*args):
        raise SyntheticCaptureFailure("observer bookkeeping refused")

    monkeypatch.setattr(stage, "_observer_bookkeeping", refused)
    with pytest.raises(_FalseySourceFailure) as caught:
        with stage._observe(h.context):
            stage._invoke(h.context)
    assert caught.value is h.primary and h.primary.__cause__ is h.cause
    assert sys.getprofile() is prior and sys.gettrace() is trace
    assert h.context.observer_recovery["identities_match"]
    assert any(name == "observer_bookkeeping" for name, _ in h.context.capture_errors)


@pytest.mark.parametrize("entry", [runner, world_runner])
@pytest.mark.parametrize("cli", [False, True])
def test_direct_child_and_cli_refuse_before_pytest_or_output(monkeypatch, tmp_path, entry, cli):
    output = tmp_path / "unreleased-child"
    entries = []

    def forbidden(*args):
        entries.append("pytest")
        raise AssertionError("No pytest driver admission")

    monkeypatch.setattr(runner, "_pytest_driver", forbidden)
    if cli:
        monkeypatch.setattr(sys, "argv", [entry.__file__, "--child", str(output)])
    with pytest.raises(ValueError, match="Direct software child entry is unreleased"):
        entry.main() if cli else entry.child(output)
    assert entries == [] and not output.exists()


@pytest.fixture
def worker_image(monkeypatch, tmp_path):
    """Conditional image metadata, never a worker/source/INIT admission."""
    packet, output = tmp_path / "conditional-packet", tmp_path / "conditional-output"
    source = packet / "source"
    source.mkdir(parents=True)
    output.mkdir()
    file = runner.FILE
    test, production, release = runner.ENTRY_CONFIG[file]
    files = {}
    for name in (file, test, production, runner.CM_GUARD_TEST):
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(__file__).parents[2].joinpath(name).read_bytes())
        files[name] = dict(sha256=runner.snapshot.digest(target))
    manifest = dict(repository=str(Path(__file__).parents[2]), files=files)
    manifest_file = source / "SNAPSHOT.json"
    runner.snapshot.write_json(manifest_file, manifest)
    plan = packet / "source-plan.json"
    runner.snapshot.write_json(plan, dict(conditional_metadata_only=True))
    inputs = dict(
        snapshot=runner.inherited.ref(manifest_file),
        source_plan=runner.inherited.ref(plan),
        owned_files={n: files[n]["sha256"] for n in (file, test, production)},
        external_runtime_paths=[],
        resources=runner.RESOURCES,
        software_entry=dict(file=file, test=test, release=release, native_release=False),
        fixture_producer=dict(path=runner.CM_GUARD_TEST, sha256=runner.CM_GUARD_SHA256),
        actual_source_native_parser_RNG_phase_or_science_release=False,
    )
    runner.snapshot.write_json(packet / "inputs.json", inputs)

    def verify(root, *, manifest_sha256):
        assert root == source and manifest_sha256 == runner.snapshot.digest(manifest_file)
        for name, row in files.items():
            if runner.snapshot.digest(source / name) != row["sha256"]:
                raise ValueError("Conditional frozen payload changed")
        return manifest

    monkeypatch.setattr(runner.snapshot, "verify", verify)
    monkeypatch.setattr(runner.inherited, "separate", lambda path, *parents: Path(path).resolve())
    monkeypatch.setattr(runner.os, "sched_getaffinity", lambda pid: {0})
    for name in tuple(runner.os.environ):
        if name.startswith("CELLS_"):
            monkeypatch.delenv(name)
    parent_pid = 873201
    monkeypatch.setattr(runner.os, "getppid", lambda: parent_pid)
    grant = dict(
        kind="cells.world_ready_software_worker_authorization@1",
        file=file,
        packet=str(packet),
        output=str(output),
        inputs_sha256=runner.snapshot.digest(packet / "inputs.json"),
        snapshot_sha256=inputs["snapshot"]["sha256"],
        parent_pid=parent_pid,
        nonce="a" * 64,
        native_release=False,
    )
    authorization = output / runner.AUTH_FILE
    runner.snapshot.write_json(authorization, grant)
    return SimpleNamespace(
        packet=packet,
        output=output,
        source=source,
        manifest=manifest,
        inputs=inputs,
        file=file,
        release=release,
        grant=grant,
        authorization=authorization,
        entry=source / file,
    )


@pytest.mark.parametrize(
    "drift", ["valid", "parent", "image", "entry", "authorization", "native-release"]
)
def test_worker_authorization_binds_parent_image_entry_and_consumes_once(
    worker_image, monkeypatch, drift
):
    h = worker_image
    pin = runner.snapshot.digest(h.authorization)
    entry = h.entry
    if drift == "parent":
        monkeypatch.setattr(runner.os, "getppid", lambda: -1)
    elif drift == "image":
        h.entry.write_text("changed conditional source")
    elif drift == "entry":
        entry = Path(runner.__file__)
    elif drift == "authorization":
        h.authorization.write_text("{}")
    elif drift == "native-release":
        monkeypatch.setenv("CELLS_NATIVE_PARAMETER_LOAD_REMAINDER_RELEASED", "1")

    def authorize():
        return runner._authorization(h.output, h.authorization, pin, file=h.file, entry_path=entry)

    if drift == "valid":
        result = authorize()
        assert result["source"] == h.source
        assert (h.output / "worker-authorization.claim.json").is_file()
        with pytest.raises(FileExistsError):
            authorize()
    else:
        with pytest.raises((ValueError, AssertionError)):
            authorize()
        assert not (h.output / "worker-authorization.claim.json").exists()


def test_parent_authorization_survives_inherited_release_environment_stripping(
    worker_image, monkeypatch
):
    h = worker_image
    output = h.output / "fresh-parent-output"
    captured = []
    monkeypatch.setenv(h.release, "1")

    def bounded(command, **kwargs):
        captured.append((command, kwargs))
        environment = kwargs["env"]
        assert h.release not in environment
        assert environment["CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED"] == "0"
        assert kwargs["timeout"] == 480 and kwargs["max_rss_bytes"] == 2**30
        assert kwargs["min_available_bytes"] == 8 * 2**30
        authorization = Path(command[command.index("--authorization") + 1])
        pin = command[command.index("--authorization-sha256") + 1]
        with monkeypatch.context() as child:
            child.delenv(h.release)
            child.setattr(runner.os, "getppid", runner.os.getpid)
            result = runner._authorization(
                output, authorization, pin, file=h.file, entry_path=h.entry
            )
        assert result["source"] == h.source
        return dict(returncode=0, conditional_launch_only=True)

    monkeypatch.setattr(runner.inherited.guard, "run_bounded", bounded)
    result = runner.software(h.packet, output)
    assert result["returncode"] == 0 and len(captured) == 1
    assert json.loads((output / "worker-authorization.claim.json").read_text())["nonce"]


@pytest.mark.parametrize(
    "failure",
    [
        "identity",
        "inventory",
        "producers",
        "identity_write",
        "inventory_write",
        "runtime_write",
        "final_write",
    ],
)
@pytest.mark.parametrize("source_error", [False, True])
def test_worker_evidence_probes_and_writes_are_independent_of_primary(
    monkeypatch, tmp_path, failure, source_error
):
    output = tmp_path / "conditional-worker"
    output.mkdir()
    primary, cause = _FalseySourceFailure("toy pytest failure"), SyntheticSourceCause("cause")
    primary.__cause__ = cause
    values, calls, binding = {}, [], object()
    image = dict(source=tmp_path, manifest={})
    monkeypatch.setattr(runner, "_authorization", lambda *a, **kw: image)
    count = 0

    def producers(*args, **kwargs):
        nonlocal count
        count += 1
        if failure == "producers" and count > 1:
            raise SyntheticCaptureFailure("producer evidence")
        return {"conditional": {}}, (binding,)

    monkeypatch.setattr(runner, "_producers", producers)

    def driver(directory):
        if source_error:
            raise primary
        return 0

    monkeypatch.setattr(runner, "_pytest_driver", lambda target: driver)

    def probe(name):
        calls.append(name)
        if failure == name:
            raise SyntheticCaptureFailure(name + " probe")
        return dict(conditional_metadata_only=name)

    monkeypatch.setattr(runner, "_identity", lambda: probe("identity"))
    monkeypatch.setattr(runner, "_inventory", lambda: probe("inventory"))
    original_write = runner.snapshot.write_json

    def write(path, value):
        calls.append(path.name)
        rejected = {
            "identity_write": "identity.json",
            "inventory_write": "inventory.json",
            "runtime_write": "runtime.json",
            "final_write": "worker-evidence.json",
        }.get(failure)
        if path.name == rejected:
            raise OSError("conditional evidence persistence")
        values[path.name] = value
        return original_write(path, value)

    monkeypatch.setattr(runner.snapshot, "write_json", write)
    expected = _FalseySourceFailure if source_error else runner.WorkerEvidenceRejected
    with pytest.raises(expected) as caught:
        runner._child(output, "conditional", "hash", file=runner.FILE, entry_path=runner.__file__)
    context = caught.value.world_ready_worker
    if source_error:
        assert caught.value is primary and primary.__cause__ is cause
    assert "identity" in calls and "inventory" in calls
    assert "runtime.json" in calls and "worker-evidence.json" in calls
    assert context.errors and context.primary is (primary if source_error else None)
    assert any(
        name.startswith(failure.split("_")[0]) or name.endswith("_write")
        for name, _ in context.errors
    )
    assert "hooks.json" in values


def test_actual_wrong_parent_helper_frame_refuses_before_body_and_stays_poisoned(observed):
    h = observed
    with pytest.raises(stage._ObservationStop):
        with stage._observe(h.context):
            with pytest.raises(ValueError, match="parent/frame/order"):
                h.balance(["a", "b", "c"], ["z", "z", "z"])
            with pytest.raises(stage._ObservationStop):
                stage._invoke(h.context)
    assert h.context.entries["balance"] == 1 and h.context.entries["tail"] == 0
    assert h.context.delegates["balance"] == 0 and h.bodies == []
    assert h.context.entry_witnesses and h.context.invalid


@pytest.mark.parametrize("when", ["setup", "restore"])
@pytest.mark.parametrize("failure", ["before", "after"])
def test_actual_hook_setter_failures_recover_both_without_replacing_source_unwind(
    observed, monkeypatch, when, failure
):
    h = observed
    h.control["fail"] = when == "restore"
    prior, trace, real_set, fired = sys.getprofile(), sys.gettrace(), sys.setprofile, []

    def setter(value):
        selected = value is prior if when == "restore" else value is not prior
        if selected and not fired:
            fired.append(value)
            if failure == "after":
                real_set(value)
            raise SyntheticCaptureFailure("actual setter " + failure)
        return real_set(value)

    monkeypatch.setattr(sys, "setprofile", setter)
    expected = _FalseySourceFailure if when == "restore" else stage._ObservationStop
    with pytest.raises(expected) as caught:
        with stage._observe(h.context):
            stage._invoke(h.context)
    assert len(fired) == 1 and h.context.invalid and h.context.capture_errors
    assert sys.getprofile() is prior and sys.gettrace() is trace
    assert h.context.observer_recovery["identities_match"]
    if when == "restore":
        assert caught.value is h.primary and h.primary.__cause__ is h.cause
        assert not h.context.observer_recovery["clean"]
    else:
        assert not h.context.observer_setup["clean"] and h.bodies == []


@pytest.mark.parametrize("change", ["clear-local", "disable-opcodes"])
def test_inherited_callback_cannot_disable_parent_safe_boundaries(observed, change):
    h = observed
    prior = sys.getprofile()

    def hook(frame, event, arg):
        if frame.f_code is h.nested.__code__ and event == "return":
            if change == "clear-local":
                frame.f_back.f_trace = None
            else:
                frame.f_back.f_trace_opcodes = False
        if prior is not None:
            prior(frame, event, arg)

    sys.setprofile(hook)
    try:
        with pytest.raises(stage._ObservationStop):
            with stage._observe(h.context):
                stage._invoke(h.context)
    finally:
        sys.setprofile(prior)
    assert h.bodies.count("balance") == 1 and not hasattr(h.context.p, "env")
    assert h.context.invalid
    assert any(name == "active_frame_trace_change" for name, _ in h.context.capture_errors)
