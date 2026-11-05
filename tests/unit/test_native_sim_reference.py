"""AST and blocked metadata controls; no original SIM body is executed."""

import ast
import dis
import gc
import inspect
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace

import pytest

from validation.betse import native_sim_reference as reference
from validation.betse import native_sim_reference_software as software
from validation.betse import native_sim_reference_source as source

initial = reference.initial


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit immutable blocked original-SIM reference software required")
    with software.blocked(tmp_path):
        yield


def _frame(name="_plot_loop", module="betse.science.sim", locals_=None):
    return SimpleNamespace(
        f_code=SimpleNamespace(
            co_name=name,
            co_firstlineno=1,
            co_filename=str(initial.NATIVE_ROOT / "betse/science/sim.py"),
        ),
        f_globals={"__name__": module},
        f_locals={} if locals_ is None else locals_,
        f_lineno=10,
    )


def _observer(tmp_path, archive=None):
    return reference.SimObserve(
        initial.State(stage="SIM"),
        initial.NATIVE_ROOT,
        archive or SimpleNamespace(save=lambda *args: None),
        None,
        10,
    )


def _prepared(tmp_path):
    path = tmp_path / "prepared.json"
    initial.snapshot.write_json(
        path, dict(kind=reference.KIND, held=True, source_plan=reference.source_plan())
    )
    return path, initial.snapshot.digest(path)


def test_sim_reference_source_plan_is_selected_and_held():
    plan = reference.source_plan()
    assert plan["external_owner_cache_phase_or_pickle_inputs"] is False
    assert plan["actual_source_native_reference_execution_released"] is False
    assert all(value is None for value in plan["reviews"].values())
    assert plan["full_original_calendar_or_explicit_capacity_refusal"] is True
    assert plan["max_SIM_iterations"] == initial.MAX_ITERATIONS
    assert plan["resource_policy"] == initial.NATIVE_POLICY
    assert plan["original"]["numerical_solver_or_flux_repair"] is False
    assert not {"phase", "sim", "cells", "p", "state", "owner", "cache"} & set(
        inspect.signature(reference.evaluate).parameters
    )


def _terminal_metadata(tmp_path, monkeypatch):
    """Real pinned code objects and inert frame data; no body is invoked."""
    observer = _observer(tmp_path)
    attempt = reference.Attempt(sim=observer.state, observer=observer)
    package = object()
    attempt.raw["original_package"] = package
    observer.enable_terminal(attempt, "original")
    t = observer.terminal
    for role, (relative, qualified) in {
        "caller": (source.RUNNER, source.ENTRY),
        **source.TERMINAL_METHODS,
    }.items():
        name = relative[:-3].replace("/", ".")
        module = sys.modules.get(name)
        if module is None:
            module = ModuleType(name)
            module.__loader__ = package
            monkeypatch.setitem(sys.modules, name, module)
        code = source.selected()[0] if role == "caller" else source.terminal_code(role, "original")
        fn = FunctionType(code, vars(module))
        if "." in qualified:
            class_name, method = qualified.split(".")
            if class_name not in vars(module):
                setattr(module, class_name, type(class_name, (), {}))
            setattr(vars(module)[class_name], method, fn)
        else:
            setattr(module, qualified, fn)
        if role == "caller":
            observer.state.raw["selected_SIM_caller"] = fn
        frame = SimpleNamespace(f_code=code, f_globals=vars(module), f_back=None, f_locals={})
        t.frames[role] = frame
        observer._terminal_function(frame, role)
    old_p, current = object(), SimpleNamespace(sim_tsteps=2, dt=0.125)
    sim, cells, old_phase = object(), object(), object()
    t.phase = SimpleNamespace(p=current, sim=sim, cells=cells)
    t.calendar = (0.0, 0.125)
    t.sampled = {0.0}
    t.iteration_times = ["0000000000000000", "3fc0000000000000"]
    t.returns = set(t.frames)
    t.context_entries, t.context_yield, t.context_return = 2, True, True
    t.events = [
        (i + 1, *event) for i, event in enumerate(source.terminal_plan()["required_events"])
    ]
    observer.state.raw.update(
        SIM_phase=t.phase,
        lineage_before=dict(INIT_phase=old_phase, old_parameters=old_p, simulator=sim, cells=cells),
    )
    observer.state.iterations = ["saved-1", "saved-2"]
    observer.state.source_returned = observer.state.hooks_restored = True
    return attempt


@pytest.mark.parametrize("mode", ["original", "disabled"])
def test_sim_reference_terminal_compiler_only_reads_pinned_original_bodies(mode):
    from types import CodeType

    plan = source.terminal_plan()
    assert len(plan["required_events"]) == 16 and plan["native_pickle_entered"] is False
    for role, (relative, qualified) in source.TERMINAL_METHODS.items():
        code = source.terminal_code(role, mode)
        assert type(code) is CodeType and code.co_qualname == qualified
        assert code.co_filename == str(initial.NATIVE_ROOT / relative)
        assert (
            type(
                source._terminal_compiled(
                    (initial.NATIVE_ROOT / relative).read_bytes(), relative, mode
                )
            )
            is tuple
        )
    assert "_pickle_phase" not in source.terminal_code("core", mode).co_names


@pytest.mark.parametrize(
    "defect",
    [
        None,
        "source",
        "capture",
        "hooks",
        "short_calendar",
        "context",
        "loop",
        "order",
        "returned_phase",
    ],
)
def test_sim_reference_terminal_record_requires_complete_actual_metadata(
    tmp_path, monkeypatch, defect
):
    attempt = _terminal_metadata(tmp_path, monkeypatch)
    state, t = attempt.sim, attempt.observer.terminal
    if defect == "source":
        state.primary = FalseySourceError("source")
    elif defect == "capture":
        state.capture_error = OSError("capture")
    elif defect == "hooks":
        state.hooks_restored = False
    elif defect == "short_calendar":
        t.iteration_times.pop()
    elif defect == "context":
        t.context_return = False
    elif defect == "loop":
        t.returns.remove("loop")
    elif defect == "order":
        t.events[1], t.events[2] = t.events[2], t.events[1]
    elif defect == "returned_phase":
        state.raw["SIM_phase"] = object()
    if defect is not None:
        with pytest.raises(initial.ReferenceRejected):
            reference._terminal_record(attempt)
        assert "terminal_observation" not in state.raw
    else:
        value = reference._terminal_record(attempt)
        assert value["configured_iterations"] == value["completed_iterations"] == 2
        assert value["normal_full_loop_return"] and value["before_native_pickle"]
        assert value["lineage_identities"]["SIM_phase"] == id(t.phase)
        assert value["physical_checkpoint_or_common_starting_authority"] is False


@pytest.mark.parametrize("defect", ["export", "code", "hidden_delegate", "closure", "namespace"])
def test_sim_reference_terminal_rechecks_live_export_delegate_bindings(
    tmp_path, monkeypatch, defect
):
    attempt = _terminal_metadata(tmp_path, monkeypatch)
    t = attempt.observer.terminal
    fn = t.functions["loop"][0]
    module = sys.modules["betse.science.sim"]
    if defect == "export":
        module.Simulator._run_sim_core_loop = FunctionType(fn.__code__, fn.__globals__)
    elif defect == "code":
        fn.__code__ = fn.__code__.replace()
    elif defect == "hidden_delegate":
        fn.__kwdefaults__ = {"__body": object()}
    elif defect == "closure":
        fn.__wrapped__ = lambda: None
    else:
        t.frames["loop"].f_globals = dict(t.frames["loop"].f_globals)
    with pytest.raises(initial.ReferenceRejected):
        reference._terminal_record(attempt)
    assert "terminal_observation" not in attempt.sim.raw


def test_sim_reference_terminal_hidden_instability_retains_original_before_observation(
    tmp_path, monkeypatch
):
    attempt = _terminal_metadata(tmp_path, monkeypatch)
    t = attempt.observer.terminal
    primary = FalseySourceError("caught native instability")
    cause = OSError("original cause")
    primary.__cause__ = cause
    frame = t.frames["core"]
    frame.f_locals["exception_instability"] = primary
    t.returns.remove("core")
    attempt.observer._terminal_return(frame, None, None)
    assert attempt.sim.primary is primary and primary.__cause__ is cause
    assert t.raw_returns[-1] == (frame, None, None) and "core" not in t.returns


@pytest.mark.parametrize("source_kind", ["normal", "ordinary", "falsey"])
@pytest.mark.parametrize("fault", ["append", "profile", "trace", "capture_entry"])
def test_sim_reference_terminal_repair_return_capture_keeps_hidden_primary(
    tmp_path, monkeypatch, source_kind, fault
):
    attempt = _terminal_metadata(tmp_path, monkeypatch)
    state, observer = attempt.sim, attempt.observer
    t = observer.terminal
    primary = (
        None
        if source_kind == "normal"
        else FalseySourceError("native instability")
        if source_kind == "falsey"
        else ValueError("native instability")
    )
    cause, capture, reporting = (
        OSError("source cause"),
        OSError("return capture"),
        OSError("capture entry"),
    )
    if primary is not None:
        primary.__cause__ = cause
    frame = t.frames["core"]
    frame.f_locals["exception_instability"] = primary
    t.returns.remove("core")
    calls = []

    class Sink:
        def append(self, value):
            calls.append(value)
            raise capture

    t.raw_returns = Sink()
    prior, local = (sys.getprofile(), sys.gettrace()), {}

    def reject(current, event):
        if (
            event == "call"
            and current.f_code is Sink.append.__code__
            and fault in ("profile", "trace")
        ):
            raise capture
        if (
            event == "call"
            and current.f_code is initial.Observe._capture.__code__
            and fault == "capture_entry"
        ):
            raise reporting

    def profile(current, event, value):
        if prior[0] is not None:
            prior[0](current, event, value)
        reject(current, event)

    def trace(current, event, value):
        inherited = prior[1] if event == "call" else local.get(id(current))
        if inherited is not None:
            delegate = inherited(current, event, value)
            if delegate is not None:
                local[id(current)] = delegate
        reject(current, event)
        if event == "return":
            local.pop(id(current), None)
        return trace

    try:
        if fault in ("profile", "capture_entry"):
            sys.setprofile(profile)
        elif fault == "trace":
            sys.settrace(trace)
        observer._terminal_return(frame, None, None)
    finally:
        sys.setprofile(prior[0])
        sys.settrace(prior[1])
    assert state.primary is primary and state.capture_error is capture
    assert state.raw["last_terminal_return"] == (frame, None, None)
    assert state.raw["terminal_return_capture_error"] is capture and "core" not in t.returns
    if primary is not None:
        assert primary.__cause__ is cause
    if fault == "capture_entry":
        assert state.raw["terminal_return_capture_reporting_error"] is reporting
    if fault in ("profile", "trace"):
        assert calls == []
    with pytest.raises(type(primary) if primary is not None else initial.ReferenceRejected):
        initial._stop(state)


def test_sim_reference_terminal_context_yield_then_normal_return_is_distinct(tmp_path, monkeypatch):
    attempt = _terminal_metadata(tmp_path, monkeypatch)
    t = attempt.observer.terminal
    frame = t.frames["context"]
    t.context_entries, t.context_yield, t.context_return = 1, False, False
    t.returns.remove("context")
    frame.f_lasti = next(
        i.offset for i in dis.get_instructions(frame.f_code) if i.opname == "YIELD_VALUE"
    )
    attempt.observer._terminal_return(frame, None, None)
    assert t.context_yield and not t.context_return and "context" not in t.returns
    t.context_entries = 2
    frame.f_lasti = next(
        i.offset
        for i in dis.get_instructions(frame.f_code)
        if i.opname in ("RETURN_VALUE", "RETURN_CONST")
    )
    attempt.observer._terminal_return(frame, None, None)
    assert t.context_return and "context" in t.returns


def test_sim_reference_retained_caller_statements_are_literal():
    code, plan = source.selected()
    raw = (initial.NATIVE_ROOT / source.RUNNER).read_bytes()
    original = initial._method(ast.parse(raw), "SimRunner", "sim")
    expected = ast.Module(body=[original.body[i] for i in (1, 2, 5, 6, 7, 8, 9)], type_ignores=[])
    assert (
        initial._sha(ast.dump(expected, include_attributes=False).encode())
        == plan["retained_statement_sha256"]
    )
    assert code.co_name == source.ENTRY and code.co_argcount == 4
    assert code.co_varnames[:4] == ("self", "sim", "cells", "p_old")
    assert code.co_filename == str(initial.NATIVE_ROOT / source.RUNNER)
    assert [row["index"] for row in plan["omitted_statements"]] == [0, 3, 4]
    assert plan["full_loadSim_autoInit_pickle_or_checkpoint_history"] is False


@pytest.mark.parametrize("module", [None, {}, dict(__name__="betse.science.simrunner")])
def test_sim_reference_source_rejects_inspection_namespace(module):
    with pytest.raises(initial.ReferenceRejected, match="Actual original"):
        source.bind(module)


def test_sim_reference_phase_and_core_order_remain_original():
    runner = initial._method(
        ast.parse((initial.NATIVE_ROOT / source.RUNNER).read_bytes()), "SimRunner", "sim"
    )
    phase = runner.body[6].value
    assert [arg.arg for arg in phase.keywords] == ["kind", "cells", "p", "sim", "callbacks"]
    assert (
        ast.unparse(phase)
        == "SimPhase(kind=phase_kind, cells=cells, p=self._p, sim=sim, callbacks=self._callbacks)"
    )
    sim = initial._method(
        ast.parse((initial.NATIVE_ROOT / "betse/science/sim.py").read_bytes()),
        "Simulator",
        "run_sim_core",
    )
    calls = [
        ast.unparse(node.func)
        for statement in sim.body
        for node in ast.walk(statement)
        if isinstance(node, ast.Call)
    ]
    assert calls[:5] == [
        "phase.die_unless_kind_init_or_sim",
        "self.init_dynamics",
        "self.clear_storage",
        "self.update_V",
        "self._plot_loop",
    ]
    assert source.EPOCH.startswith("original_full_SIM_")


@pytest.mark.parametrize(
    "name", ["betse", "betse.science.sim", "betse.unavailable_native_dependency"]
)
def test_sim_reference_closed_import_authority_refuses_new_native_modules(name):
    guard = reference.ExistingOriginalImports()
    with pytest.raises(initial.ReferenceRejected, match="authority unavailable"):
        guard.find_spec(name)
    assert guard.find_spec("json") is None


@pytest.mark.parametrize("name", ["loadWorld", "loadSim", "saveSim"])
def test_sim_reference_pickle_entry_refuses_before_admission(tmp_path, name):
    observer = _observer(tmp_path)
    with pytest.raises(initial.ReferenceRejected, match="Saved-source substitution"):
        observer._entry(_frame(name, "betse.science.filehandling"))
    assert observer.admitted == {} and observer.state.work == []


@pytest.mark.parametrize("count", [1, 512, 513])
def test_sim_reference_complete_calendar_is_recorded_or_refused(tmp_path, count):
    captured = []
    observer = _observer(tmp_path, SimpleNamespace(save=lambda *args: captured.append(args)))
    frame = _frame()
    observer._entry(frame)
    if count <= 512:
        observer._return(frame, ([0] * count, set()))
    else:
        with pytest.raises(initial.ReferenceRejected, match="capacity"):
            observer._return(frame, ([0] * count, set()))
    assert captured[0][0] == "original_calendar" and len(captured[0][1][0]) == count
    assert observer.state.source_returned is False


def test_sim_reference_archive_scopes_SIM_epochs_and_preserves_raw_failure(tmp_path, monkeypatch):
    state = initial.State(stage="SIM")
    archive = reference.SimArchive(tmp_path / "captures", state)
    pin = archive.save("iteration_0001", dict(ordinal=1, source_time=0.0))
    assert state.captures[0]["label"] == "SIM.iteration_0001"
    assert Path(pin["path"]).is_file()
    raw = {"retained": "original raw partial"}
    error = OSError("capture publication failure")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(initial.evidence, "write", fail)
    with pytest.raises(OSError) as caught:
        archive.save("iteration_0002", raw)
    assert caught.value is error
    assert state.raw["failed_archive"]["value"] is raw
    assert (
        state.captures[-1]["label"] == "SIM.iteration_0002"
        and state.captures[-1]["status"] == "capture_failed"
    )


def test_sim_reference_actual_iteration_stream_uses_retained_fields_and_SIM_dt(
    tmp_path, monkeypatch
):
    import numpy as np

    state = initial.State(stage="SIM")
    archive = reference.SimArchive(tmp_path / "captures", state)
    observer = _observer(tmp_path, archive)
    observer.state = state
    sim = SimpleNamespace(vm=np.array([-0.0, 1.0]), lapENVinv=object(), gj_funk=None)
    frame = _frame(
        locals_={
            "self": sim,
            "phase": SimpleNamespace(
                p=SimpleNamespace(
                    dt=0.25,
                    molecules_enabled=False,
                    grn_enabled=False,
                    global_options={},
                    scheduled_options={},
                ),
                dyna=SimpleNamespace(event_cut=None, _event_voltage=None),
            ),
            "time_steps_sampled": {0.0},
        }
    )
    frame.f_globals["np"] = SimpleNamespace(
        random=SimpleNamespace(get_state=lambda: ("synthetic-full-state-provider",))
    )
    monkeypatch.setattr(
        initial, "random", SimpleNamespace(getstate=lambda: ("synthetic-Python-state",))
    )
    for ordinal in range(3):
        frame.f_locals["t"] = ordinal * 0.25
        observer._iteration(frame)
    assert len(state.iterations) == 3 and set(state.raw) == {"last_iteration"}
    assert state.raw["last_iteration"]["configured_dt"] == 0.25
    assert set(state.raw["last_iteration"]["fields"]) == {"vm"}
    assert [row["label"] for row in state.captures] == [
        f"SIM.iteration_{i:04d}" for i in range(1, 4)
    ]


@pytest.mark.parametrize(
    "result",
    [
        None,
        {},
        dict(kind=initial.KIND, status="failed"),
        dict(kind=initial.KIND, status="completed"),
    ],
)
def test_sim_reference_no_supplied_or_failed_parent_becomes_authority(result, monkeypatch):
    monkeypatch.setattr(initial, "_ATTEMPT", None)
    with pytest.raises((initial.ReferenceRejected, AttributeError)):
        reference._parent_state(result, None)


def test_sim_reference_held_evaluate_never_calls_INIT_producer(tmp_path, monkeypatch):
    path, pin = _prepared(tmp_path)
    calls = []
    monkeypatch.setattr(initial, "evaluate", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(reference, "_ATTEMPT", None)
    result = reference.evaluate(path, pin, tmp_path / "out")
    assert result["status"] == "failed" and calls == []
    assert result["INIT_parent_consumed"] is False
    assert result["SIM_iterations"] == [] and result["SIM_captures"] == []
    assert (tmp_path / "out/SIM-reference-result.json").is_file()
    assert reference._ATTEMPT is not None
    second = reference.evaluate(path, pin, tmp_path / "second")
    assert second["status"] == "failed" and calls == []


def test_sim_reference_missing_preparation_retains_early_failure(tmp_path):
    result = reference.evaluate(tmp_path / "missing", "0" * 64, tmp_path / "out")
    assert result["status"] == "failed" and result["primary"]
    assert result["INIT_result"] is None and result["SIM_captures"] == []


def test_sim_reference_supervisor_is_held_before_launch(tmp_path, monkeypatch):
    from validation.betse import betse_mesh_lifecycle_preparation_guard as guard

    path, pin = _prepared(tmp_path)
    calls = []
    monkeypatch.setattr(guard, "run_bounded", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(initial.ReferenceRejected, match="remains held"):
        reference.supervise(path, pin, None, None, tmp_path / "out")
    assert calls == [] and not (tmp_path / "out").exists()


def test_sim_reference_preserves_literal_constructor_then_core_source_order():
    tree = ast.parse(Path(reference.__file__).read_bytes())
    function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_continue"
    )
    calls = [ast.unparse(node.func) for node in ast.walk(function) if isinstance(node, ast.Call)]
    assert calls.index("module.Parameters.make") < calls.index("caller")
    assert "_sim_execution" in calls and "package.verify" in calls
    text = ast.unparse(function)
    assert "parent_consumed = True" in text
    assert "phase.p" in text and "phase.sim" in text and "phase.cells" in text
    assert "__enter__" not in text and ".used =" not in text


def test_sim_reference_prepare_refuses_manifest_file_before_freezing(tmp_path, monkeypatch):
    path = tmp_path / "inputs.json"
    path.write_text("{}\n")
    calls = []
    monkeypatch.setattr(reference.snapshot, "freeze", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(initial.ReferenceRejected, match="paired-input directory"):
        reference.prepare(
            tmp_path / "out",
            input_pair=path,
            input_sha256=reference.snapshot.digest(path),
            mode="original",
        )
    assert calls == [] and not (tmp_path / "out").exists()


def test_sim_reference_preparation_roster_includes_complete_parent_triple():
    starts = reference.preparation_starts()
    assert set(reference.OWNED) <= set(starts)
    assert {initial.FILE, initial.TEST, initial.RUNNER} <= set(starts)
    assert len(starts) == len(set(starts))


class FalseySourceError(ValueError):
    def __bool__(self):
        return False


def _failure_path(tmp_path, monkeypatch, primary, *, raised=False, uncovered=False):
    path, pin = _prepared(tmp_path)
    plan = initial._json_record(path, pin)
    plan.update(
        execution_source=dict(root=str(reference.ROOT), snapshot_sha256="a" * 64, owned_files={}),
        INIT_prepared=dict(path="unused", sha256="b" * 64),
    )
    path.unlink()
    initial.snapshot.write_json(path, plan)
    state = initial.State(primary=primary, observer_used=True, hooks_restored=not uncovered)
    state.raw["required_inherited_hooks"] = sys.getprofile(), sys.gettrace()
    nested = dict(kind=initial.KIND, status="failed", primary=initial._error(primary))
    calls = []

    def parent(*args, **kwargs):
        initial._ATTEMPT = state
        if raised:
            raise primary
        return nested

    monkeypatch.setattr(reference, "_ATTEMPT", None)
    monkeypatch.setattr(initial, "_ATTEMPT", None)
    monkeypatch.setattr(initial, "evaluate", parent)
    monkeypatch.setattr(initial, "_resources", lambda: None)
    monkeypatch.setattr(reference.snapshot, "verify", lambda *a, **k: dict(files={}))
    monkeypatch.setattr(
        reference,
        "_release",
        lambda *a, **k: dict(init_release=dict(path="unused", sha256="b" * 64)),
    )
    monkeypatch.setattr(reference, "_continue", lambda *a, **k: calls.append("SIM"))
    return path, initial.snapshot.digest(path), state, nested, calls


def test_sim_reference_repair_actual_original_loader_verifier_interface(monkeypatch):
    loader = initial.OriginalPackage(initial.NATIVE_ROOT, {}, "original")
    loader.used = True
    assert not hasattr(loader, "check")
    loader.verify()
    module = ModuleType("betse.science.simrunner")
    module.__loader__ = loader
    monkeypatch.setitem(sys.modules, module.__name__, module)
    compiled = source.bind(module)
    assert compiled.__globals__ is vars(module)
    assert compiled.__code__.co_name == source.ENTRY
    assert loader.used and loader not in sys.meta_path
    tree = ast.parse(Path(reference.__file__).read_bytes())
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "check"
        and ast.unparse(node.func.value) == "package"
        for node in ast.walk(tree)
    )


@pytest.mark.parametrize("falsey", [False, True])
@pytest.mark.parametrize("raised,uncovered", [(False, False), (True, True)])
def test_sim_reference_repair_failed_INIT_primary_and_raw_state(
    tmp_path, monkeypatch, falsey, raised, uncovered
):
    primary = (FalseySourceError if falsey else ValueError)("original INIT failure")
    primary.__cause__ = OSError("original cause")
    path, pin, state, nested, calls = _failure_path(
        tmp_path, monkeypatch, primary, raised=raised, uncovered=uncovered
    )
    result = reference.evaluate(path, pin, tmp_path / "out")
    attempt = reference._ATTEMPT
    assert attempt.parent is state and attempt.primary is primary
    assert attempt.primary.__cause__ is primary.__cause__
    assert calls == [] and not attempt.parent_consumed and attempt.sim is None
    assert result["primary"][0]["identity"] == id(primary) and result["status"] == "failed"
    assert result["INIT_result"] == (None if raised else nested)
    assert attempt.hooks_restored


@pytest.mark.parametrize("falsey", [False, True])
@pytest.mark.parametrize("where", ["mkdir", "render", "write"])
def test_sim_reference_repair_terminal_boundary_keeps_primary(tmp_path, monkeypatch, falsey, where):
    primary = (FalseySourceError if falsey else ValueError)("original source")
    primary.__cause__ = OSError("source cause")
    path, pin, state, _, calls = _failure_path(tmp_path, monkeypatch, primary)
    output = tmp_path / "out"
    secondary = OSError("secondary terminal failure")
    if where == "mkdir":
        original = Path.mkdir

        def mkdir(self, *args, **kwargs):
            if self == output:
                raise secondary
            return original(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", mkdir)
    elif where == "render":
        monkeypatch.setattr(initial, "_error", lambda error: (_ for _ in ()).throw(secondary))
    else:
        original = reference.snapshot.write_json

        def write(path, value):
            if path == output / "SIM-reference-result.json":
                raise secondary
            return original(path, value)

        monkeypatch.setattr(reference.snapshot, "write_json", write)
    with pytest.raises(type(primary)) as caught:
        reference.evaluate(path, pin, output)
    assert caught.value is primary and primary.__cause__.args == ("source cause",)
    attempt = reference._RAW_FAILURES[-1]
    assert attempt.parent is state and attempt.primary is primary and calls == []
    assert any(error is secondary for _, error in attempt.secondary)


@pytest.mark.parametrize("hook", ["profile", "trace"])
@pytest.mark.parametrize("falsey", [False, True])
def test_sim_reference_repair_observed_exit_rejection_restores_both(tmp_path, hook, falsey):
    observer = _observer(tmp_path)
    primary = (FalseySourceError if falsey else ValueError)("body primary")
    primary.__cause__ = KeyError("body cause")
    secondary = RuntimeError("inherited context exit rejection")
    old_profile, old_trace = sys.getprofile(), sys.gettrace()
    enabled = [False]

    def inherited(frame, event, arg):
        previous = old_profile if hook == "profile" else old_trace
        child = previous(frame, event, arg) if previous is not None else None
        if (
            enabled[0]
            and event == "call"
            and frame.f_code.co_name == "__exit__"
            and frame.f_globals.get("__name__") == "contextlib"
        ):
            enabled[0] = False
            raise secondary
        return child if hook == "profile" else inherited

    def execute():
        enabled[0] = True
        raise primary

    try:
        (sys.setprofile if hook == "profile" else sys.settrace)(inherited)
        required = sys.getprofile(), sys.gettrace()
        with pytest.raises(type(primary)) as caught:
            reference._sim_execution(observer, execute)
        assert caught.value is primary and primary.__cause__.args == ("body cause",)
        assert observer.state.primary is primary and observer.state.hooks_restored
        assert sys.getprofile() is required[0] and sys.gettrace() is required[1]
        assert any(error is secondary for _, error in observer.state.secondary)
        assert observer.state.raw["observed_manager"].gen.gi_frame is None
        unraisable = []
        old_unraisable = sys.unraisablehook

        def fresh_profile(frame, event, arg):
            if old_profile is not None:
                old_profile(frame, event, arg)

        def fresh_trace(frame, event, arg):
            if old_trace is not None:
                old_trace(frame, event, arg)
            return fresh_trace

        try:
            sys.unraisablehook = unraisable.append
            sys.setprofile(fresh_profile)
            sys.settrace(fresh_trace)
            gc.collect()
            assert sys.getprofile() is fresh_profile and sys.gettrace() is fresh_trace
            assert unraisable == []
        finally:
            sys.unraisablehook = old_unraisable
    finally:
        enabled[0] = False
        sys.setprofile(old_profile)
        sys.settrace(old_trace)


def test_sim_reference_repair_independent_setters_after_failure(tmp_path, monkeypatch):
    observer = _observer(tmp_path)
    tokens = [object(), object()]
    actual, restored = list(tokens), []
    primary = FalseySourceError("source")
    secondary = OSError("profile restoration")

    def profile(value):
        restored.append("profile")
        raise secondary

    def trace(value):
        restored.append("trace")
        actual[1] = value

    facade = SimpleNamespace(
        setprofile=profile, settrace=trace, getprofile=lambda: actual[0], gettrace=lambda: actual[1]
    )

    @contextmanager
    def observing(value):
        value.state.observer_used = True
        actual[:] = [object(), object()]
        yield

    monkeypatch.setattr(reference, "sys", facade)
    monkeypatch.setattr(initial, "observed", observing)
    with pytest.raises(FalseySourceError) as caught:
        reference._sim_execution(observer, lambda: (_ for _ in ()).throw(primary))
    assert caught.value is primary and restored == ["profile", "trace"]
    assert not observer.state.hooks_restored and observer.state.coverage_failed
    assert any(error is secondary for _, error in observer.state.secondary)


def _finisher(tmp_path, monkeypatch, primary=None, sticky=None):
    from validation.betse import betse_normal_channel_join_runtime as runtime

    output = tmp_path / "out"
    output.mkdir()
    (output / "runtime.json").write_bytes(b"original INIT runtime")
    (output / "filesystem.json").write_bytes(b"original INIT audit")
    selected = dict(root=str(tmp_path), inventory=dict(files={}, directories=[]))
    parent_plan = dict(inputs=selected)
    parent_pin = tmp_path / "INIT-prepared.json"
    initial.snapshot.write_json(parent_pin, parent_plan)
    initial.snapshot.write_json(
        output / "execution-inputs.json",
        dict(source_root=selected["root"], inventory=selected["inventory"], files=[]),
    )
    calls = []

    def audit():
        calls.append("audit")
        if sticky is not None:
            raise sticky

    parent = initial.State()
    old_p, current = SimpleNamespace(_run_sim=False), SimpleNamespace(_run_sim=True)
    sim, cells = object(), object()
    old_phase = SimpleNamespace(p=old_p, sim=sim, cells=cells, kind=SimpleNamespace(name="INIT"))
    phase = SimpleNamespace(p=current, sim=sim, cells=cells, kind=SimpleNamespace(name="SIM"))
    parent.raw.update(init_phase=old_phase, parameters=old_p)
    parent.raw.update(
        shared_writer_session=SimpleNamespace(check=lambda: calls.append("lease")),
        filesystem_audit=SimpleNamespace(
            check=audit, record=lambda: dict(sticky=sticky is not None)
        ),
    )
    state = initial.State(
        primary=primary, source_returned=True, hooks_restored=True, observer_used=True
    )
    state.raw.update(
        lineage_before=dict(INIT_phase=old_phase, old_parameters=old_p, simulator=sim, cells=cells),
        SIM_phase=phase,
        current_parameters=current,
    )
    attempt = reference.Attempt(
        parent=parent,
        sim=state,
        hooks_restored=True,
        parent_consumed=True,
        required_hooks=(sys.getprofile(), sys.gettrace()),
        controls=((sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)),
    )
    (output / "SIM-reference").mkdir()
    archive = reference.SimArchive(output / "SIM-reference/captures", state)
    attempt.raw.update(
        original_package=SimpleNamespace(verify=lambda: calls.append("verify"), loaded={}),
        SIM_archive=archive,
    )
    plan = dict(
        execution_source=dict(snapshot_sha256="a" * 64, owned_files={}),
        INIT_prepared=dict(path=str(parent_pin), sha256=initial.snapshot.digest(parent_pin)),
    )
    monkeypatch.setattr(reference.snapshot, "verify", lambda *a, **k: dict(files={}))
    monkeypatch.setattr(initial.inputs, "inventory", lambda *a: selected["inventory"])
    monkeypatch.setattr(initial, "_retain_native", lambda *a: calls.append("partials"))
    monkeypatch.setattr(runtime, "inventory", lambda: dict(loaded_files={}, actual_post_SIM=True))
    monkeypatch.setattr(reference, "_ATTEMPT", attempt)
    monkeypatch.setattr(initial, "_ATTEMPT", parent)
    # These controls isolate final audit/coverage behavior, not native terminal
    # witnessing. Dedicated terminal controls exercise the genuine checker.
    monkeypatch.setattr(
        reference, "_terminal_record", lambda actual: {"synthetic_audit_control": actual is attempt}
    )
    return attempt, plan, output, calls


@pytest.mark.parametrize("source_failed", [False, True])
@pytest.mark.parametrize("sticky_failed", [False, True])
def test_sim_reference_repair_post_SIM_audit_runtime_and_live_lease(
    tmp_path, monkeypatch, source_failed, sticky_failed
):
    primary = FalseySourceError("original SIM source") if source_failed else None
    sticky = OSError("caught sticky audit rejection") if sticky_failed else None
    attempt, plan, output, calls = _finisher(tmp_path, monkeypatch, primary, sticky)
    reference._finish_sim(attempt, plan, output)
    expected = 3 if not source_failed and not sticky_failed else 2
    assert calls.count("verify") == calls.count("lease") == calls.count("audit") == expected
    assert "partials" in calls
    assert (output / "runtime.json").read_bytes() == b"original INIT runtime"
    assert (output / "filesystem.json").read_bytes() == b"original INIT audit"
    record = initial._json_record(
        output / "SIM-reference/runtime.json",
        initial.snapshot.digest(output / "SIM-reference/runtime.json"),
    )
    assert record["actual_post_SIM"] is True
    assert (output / "SIM-reference/source-input-binding.json").is_file()
    assert attempt.sim.primary is (primary if primary is not None else sticky)
    assert attempt.finalization_complete is (not source_failed and not sticky_failed)
    if source_failed and sticky_failed:
        assert any(error is sticky for _, error in attempt.sim.secondary)


def test_sim_reference_repair_post_SIM_runtime_failure_retains_original(tmp_path, monkeypatch):
    from validation.betse import betse_normal_channel_join_runtime as runtime

    primary, secondary = ValueError("original source"), OSError("inventory failure")
    attempt, plan, output, _ = _finisher(tmp_path, monkeypatch, primary)
    monkeypatch.setattr(runtime, "inventory", lambda: (_ for _ in ()).throw(secondary))
    reference._finish_sim(attempt, plan, output)
    assert attempt.sim.primary is primary and attempt.sim.capture_error is secondary
    assert not attempt.finalization_complete


def _rich_iteration(tmp_path, monkeypatch):
    import numpy as np

    sim = SimpleNamespace(
        vm=np.array([-0.0, 1.0]),
        gj_funk=None,
        gjopen=np.array([0.125, 0.75]),
        gj_block=np.array([1.0, 0.0]),
    )
    p = SimpleNamespace(
        dt=0.125,
        molecules_enabled=False,
        grn_enabled=False,
        global_options={"gj_block": 0},
        scheduled_options={"Na_mem": 0},
    )
    dyna = SimpleNamespace(event_cut=None, _event_voltage=None)
    phase = SimpleNamespace(p=p, dyna=dyna)
    state = initial.State(stage="SIM")
    archive = reference.SimArchive(tmp_path / "rich-captures", state)
    observer = _observer(tmp_path, archive)
    observer.state = state
    frame = _frame(locals_={"self": sim, "phase": phase, "t": 0.0, "time_steps_sampled": {0.0}})
    frame.f_globals["np"] = SimpleNamespace(
        random=SimpleNamespace(get_state=lambda: ("synthetic MT",))
    )
    monkeypatch.setattr(initial, "random", SimpleNamespace(getstate=lambda: ("synthetic Python",)))
    return observer, frame, sim, p, dyna


def test_sim_reference_observations_contract_is_pinned_and_literal():
    plan = source.observation_plan()
    assert plan["epoch"] == source.EPOCH and plan["kind"] == source.OBSERVATION_KIND
    assert plan["actual_body_or_RNG_execution"] is False
    assert "gjopen" in plan["gap_junction_fields"] and "E_env_y" in plan["electric_fields"]
    assert "_fire_events_tissue" in plan["event_methods"]["betse.science.tissue.tishandler"]
    for name, digest in plan["native_sources"].items():
        assert initial.snapshot.digest(initial.NATIVE_ROOT / name) == digest


def test_sim_reference_observations_actual_fields_absence_and_disabled_channels(
    tmp_path, monkeypatch
):
    observer, frame, sim, p, dyna = _rich_iteration(tmp_path, monkeypatch)
    observer._iteration(frame)
    row = observer.state.raw["last_iteration"]
    assert row["observation_contract"] == source.OBSERVATION_KIND
    assert row["gates"]["gap_junction"]["gjopen"]["value"] is sim.gjopen
    assert row["gates"]["gap_junction_core"]["alpha"] == dict(present=False)
    assert row["electric_fields"]["E_env_x"] == dict(present=False)
    assert row["gates"]["molecules"]["enabled"] is False
    assert row["events"]["global_options"] is p.global_options
    assert row["events"]["event_cut"] == dict(present=False)
    assert len(observer.state.iterations) == 1


def test_sim_reference_observations_enabled_channels_keep_original_core_data(tmp_path, monkeypatch):
    observer, frame, sim, p, _ = _rich_iteration(tmp_path, monkeypatch)
    p.molecules_enabled = True
    core = SimpleNamespace(m=sim.gjopen, h=sim.gj_block, modulator=-0.0)
    sim.molecules = SimpleNamespace(
        core=SimpleNamespace(channels={"actual_roster": SimpleNamespace(channel_core=core)})
    )
    observer._iteration(frame)
    channels = observer.state.raw["last_iteration"]["gates"]["molecules"]["channels"]
    assert channels[0]["name"] == "actual_roster"
    assert channels[0]["fields"]["m"] is core.m
    assert channels[0]["fields"]["h"] is core.h
    assert not {"phase", "owner", "cache"} & channels[0].keys()


@pytest.mark.parametrize("boundary", ["return", "unwind"])
def test_sim_reference_observations_event_edges_and_raw_primary(tmp_path, monkeypatch, boundary):
    observer, frame, _, _, dyna = _rich_iteration(tmp_path, monkeypatch)
    event = _frame(
        "fire_events",
        "betse.science.tissue.tishandler",
        dict(self=dyna, phase=frame.f_locals["phase"], t=0.0),
    )
    observer._entry(event)
    observer._entry(event)
    primary = ValueError("original event failure")
    primary.__cause__ = OSError("original event cause")
    if boundary == "unwind":
        observer.pending[id(event)] = primary
    observer._return(event, None)
    observer._return(event, None)
    assert [row["boundary"] for row in observer.step_events] == ["enter", boundary]
    assert observer.state.raw["last_event_observation"]["error"] is (
        primary if boundary == "unwind" else None
    )
    observer._iteration(frame)
    row = observer.state.raw["last_iteration"]
    assert len(row["events"]["calls"]) == 2 and observer.step_events == []
    assert row["events"]["calls"][-1]["cause_type"] == (
        "builtins.OSError" if boundary == "unwind" else None
    )


def test_sim_reference_observations_failed_capture_retains_row_events_arrays(tmp_path, monkeypatch):
    observer, frame, sim, _, _ = _rich_iteration(tmp_path, monkeypatch)
    observer.step_events.append(dict(ordinal=1, boundary="enter"))
    primary = OSError("actual writer failure")

    def fail(*args, **kwargs):
        raise primary

    monkeypatch.setattr(initial.evidence, "write", fail)
    with pytest.raises(OSError) as caught:
        observer._iteration(frame)
    assert caught.value is primary and observer.state.iterations == []
    raw = observer.state.raw["failed_archive"]["value"]
    assert raw["gates"]["gap_junction"]["gjopen"]["value"] is sim.gjopen
    assert raw["events"]["calls"] == observer.step_events


@pytest.mark.parametrize("change", ["old_p", "new_p", "sim", "cells", "phase", "claim"])
def test_sim_reference_observations_closed_lineage_refuses_retarget(tmp_path, monkeypatch, change):
    attempt, _, _, _ = _finisher(tmp_path, monkeypatch)
    before = attempt.sim.raw["lineage_before"]
    phase = attempt.sim.raw["SIM_phase"]
    if change == "old_p":
        before["INIT_phase"].p = object()
    elif change == "new_p":
        phase.p = object()
    elif change == "sim":
        phase.sim = object()
    elif change == "cells":
        phase.cells = object()
    elif change == "phase":
        phase.kind.name = "INIT"
    else:
        monkeypatch.setattr(initial, "_ATTEMPT", initial.State())
    with pytest.raises(initial.ReferenceRejected, match="ancestry"):
        reference._closed_lineage(attempt)
    assert attempt.closed_lineage is None
    assert (
        attempt.sim.raw["closed_lineage_observation"]["live_owner_or_checkpoint_hydration"] is False
    )


@pytest.mark.parametrize("boundary", ["call", "return"])
@pytest.mark.parametrize("reject", [False, True])
def test_sim_reference_metadata_recovery_covers_later_callbacks(
    tmp_path, monkeypatch, boundary, reject
):
    from validation.betse import betse_normal_channel_join_runtime as runtime

    primary = FalseySourceError("original source")
    primary.__cause__ = KeyError("original cause")
    attempt, plan, output, calls = _finisher(tmp_path, monkeypatch, primary)
    old_profile, old_trace = sys.getprofile(), sys.gettrace()
    triggered = [False]
    delegates = []
    seen = []
    secondary = RuntimeError("inherited metadata observer")

    def inventory_probe():
        delegates.append("inventory")
        return dict(loaded_files={})

    def inherited(frame, event, arg):
        if old_profile is not None:
            old_profile(frame, event, arg)
        if not triggered[0] and event == boundary and frame.f_code is inventory_probe.__code__:
            triggered[0] = True
            sys.setprofile(None)
            sys.settrace(None)
            if reject:
                raise secondary

    def audit_record():
        seen.append((sys.getprofile(), sys.gettrace()))
        return dict(retained=True)

    monkeypatch.setattr(runtime, "inventory", inventory_probe)
    attempt.parent.raw["filesystem_audit"].record = audit_record
    try:
        sys.setprofile(inherited)
        attempt.required_hooks = (inherited, old_trace)
        reference._finish_sim(attempt, plan, output)
        assert triggered[0] and seen == [(inherited, old_trace)]
        assert delegates == ([] if boundary == "call" and reject else ["inventory"])
        assert attempt.sim.primary is primary and primary.__cause__.args == ("original cause",)
        assert attempt.sim.capture_error is not None and not attempt.finalization_complete
        assert (
            attempt.hooks_restored and sys.getprofile() is inherited and sys.gettrace() is old_trace
        )
        if reject:
            assert any(error is secondary for _, error in attempt.sim.secondary)
    finally:
        sys.setprofile(old_profile)
        sys.settrace(old_trace)


@pytest.mark.parametrize("failed", ["profile", "trace", "both"])
def test_sim_reference_metadata_failed_recovery_stops_later_delegate(tmp_path, monkeypatch, failed):
    primary = FalseySourceError("original source")
    attempt, _, _, _ = _finisher(tmp_path, monkeypatch, primary)
    attempt.primary = primary
    old_profile, old_trace = sys.getprofile(), sys.gettrace()
    setter_calls = []
    later = []
    fault = [False]

    def set_profile(value):
        setter_calls.append("profile")
        if fault[0] and failed in ("profile", "both"):
            raise OSError("profile restore")
        sys.setprofile(value)

    def set_trace(value):
        setter_calls.append("trace")
        if fault[0] and failed in ("trace", "both"):
            raise OSError("trace restore")
        sys.settrace(value)

    def clears():
        sys.setprofile(None)
        sys.settrace(None)
        fault[0] = True

    attempt.controls = ((set_profile, set_trace), (sys.getprofile, sys.gettrace))
    try:
        with pytest.raises(FalseySourceError) as caught:
            reference._metadata(attempt, "cleared", clears)
        assert caught.value is primary and not attempt.hooks_restored
        assert setter_calls == ["profile", "trace", "profile", "trace"]
        assert "metadata_coverage_unavailable" in attempt.raw
        with pytest.raises(FalseySourceError):
            reference._metadata(attempt, "later", lambda: later.append("unsafe"))
        assert later == []
    finally:
        sys.setprofile(old_profile)
        sys.settrace(old_trace)
