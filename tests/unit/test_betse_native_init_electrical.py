"""Blocked metadata controls; no field equation or native owner is executed."""

import ast
import builtins
import copy
import os
import sys
from contextlib import contextmanager
from types import CodeType, FunctionType, ModuleType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_init_electrical as stage
from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import betse_native_init_electrical_software as software

_RAW_GUARDS = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit electrical native-blocked software release required")
    adapter = NS(**dict(vars(software), reuse=software.base.reuse.reuse))
    namespace = dict(vars(guards), stage=stage, software=adapter, _BLOCKADE_FAILURES=())
    function = FunctionType(guards._blockade.__wrapped__.__code__, namespace)
    try:
        with contextmanager(function)(request, tmp_path):
            yield
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARDS.append(namespace["_BLOCKADE_FAILURES"])


def context(**extra):
    values = dict(
        invalid=False,
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        primary=None,
        request=None,
        stage="metadata",
        stores=[],
        pending_stores={},
        sim=NS(),
        helper_calls=[],
        frames={},
        work=[],
        methods={},
        external={},
        operation=None,
        body_names={},
        current_attempted=False,
    )
    values.update(extra)
    return NS(**values)


def test_electrical_full_literal_closure_and_flux_independence():
    plan = stage.source_plan()
    assert len(plan["source"]) == 4 and len(plan["roster"]) == 7
    assert plan["native_helpers"] == ("get_current", "HH_Decomp", "gradient", "diff", "divergence")
    assert plan["flux_inverse_read"] is False and plan["flux_defect_repair"] is False
    assert "lapENV_P_inv" not in plan["reads"]["cells"]
    assert "lapENVinv" in plan["reads"]["cells"]
    assert len({field for _, _, field in plan["stores"]}) == 27
    assert plan["actual_source_native_operator_reference_or_scientific_release"] is False
    assert plan["timestep_credit"] == 0


@pytest.mark.parametrize(
    "name",
    ("update_V", "get_current", "HH_Decomp", "gradient", "diff", "divergence", "smooth_flux"),
)
def test_electrical_original_code_is_whole_module_compiled_without_execution(name):
    node, code = stage._definitions()[name]
    assert type(code) is CodeType and code.co_firstlineno == node.lineno
    assert code.co_name == name and code.co_filename.startswith(str(stage.NATIVE) + "/")


def test_electrical_original_numeric_branches_and_boundary_order_retained():
    definitions = stage._definitions()
    current = definitions["get_current"][0]
    branch = next(n for n in current.body if isinstance(n, ast.If))
    assert ast.unparse(branch.test) == "p.is_ecm is True"
    values = [ast.unparse(n) for n in branch.body if isinstance(n, ast.Assign)]
    boundaries = [line for line in values if line.startswith("div_Jb[")]
    assert [line.split("sim.bound_V[")[1].split("]")[0] for line in boundaries] == [
        "'R'",
        "'L'",
        "'T'",
        "'B'",
    ]
    body = definitions["update_V"][0]
    assert (
        ast.unparse(next(n for n in body.body if isinstance(n, ast.If)).test)
        == "p.cell_polarizability == 0.0"
    )
    assert ast.unparse(body.body[-1]) == "self.dvm = (self.vm - vmo) / p.dt"
    assert "0.1" in ast.unparse(body) and ".mean(axis=0)" in ast.unparse(body)


def test_electrical_no_operator_rebuild_new_rng_or_timestep_loop():
    text = "\n".join(ast.unparse(node) for node, _ in stage._definitions().values())
    assert not {
        "pinv",
        "makeLaplacian",
        "RandomState",
        "set_state",
        "run_sim_core",
        "update_all_concs",
    } & {
        n.id
        for node, _ in stage._definitions().values()
        for n in ast.walk(node)
        if isinstance(n, ast.Name)
    }
    assert "random" not in text and "lapENV_P_inv" not in text


@pytest.mark.parametrize("entry", ("ready", "request", "prepare"))
def test_electrical_unbound_parent_refuses_before_foreign_inspection(entry, monkeypatch):
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("No supplied parent inspection before producer binding")

    with pytest.raises(stage.ElectricalRejected) as caught:
        if entry == "ready":
            stage._ready()
        elif entry == "request":
            stage.from_storage(Foreign(), law_id=stage.LAW_ID)
        else:
            monkeypatch.setenv(stage.RELEASE, "1")
            stage.prepare(Foreign(), enabled=True)
    assert caught.value.stage == "held" and caught.value.trial is None


@pytest.mark.parametrize("operation", ("construct", "hydrate", "phase", "trial"))
def test_electrical_foreign_handle_never_issues_authority(operation):
    owner = object.__new__(stage.ElectricalOwner)
    with pytest.raises((TypeError, stage.ElectricalRejected)):
        if operation == "construct":
            stage.ElectricalOwner()
        elif operation == "hydrate":
            owner.__reduce_ex__(4)
        else:
            getattr(owner, operation)


def test_electrical_bad_law_and_disabled_release_precede_dependencies(monkeypatch):
    monkeypatch.setattr(stage, "_ready", lambda: pytest.fail("No dependency entry"))
    with pytest.raises(stage.ElectricalRejected, match="law"):
        stage.from_storage(object(), law_id="supplied_voltage")
    with pytest.raises(stage.ElectricalRejected, match="held"):
        stage.prepare(object())


def test_electrical_nested_store_completion_waits_for_its_actual_frame():
    root, child = object(), object()
    old, new = object(), object()
    c = context(sim=NS(vm=old, rho_cells=new))
    c.pending_stores[id(root)] = (root, 5, "vm", old, True, 0)
    c.pending_stores[id(child)] = (child, 6, "rho_cells", None, False, 0)
    stage._finish_store(c, child)
    assert c.stores == [(6, "rho_cells", None, new, False, True)]
    assert id(root) in c.pending_stores
    c.sim.vm = new
    stage._finish_store(c, root)
    assert c.stores[-1] == (5, "vm", old, new, True, True)


def test_electrical_failed_store_archive_keeps_raw_assignment_and_primary():
    original, changed, frame = object(), object(), object()
    primary = ValueError("source")
    capture = OSError("store journal")

    class Failed:
        def append(self, row):
            raise capture

    c = context(sim=NS(vm=changed), primary=primary, stores=Failed())
    c.pending_stores[id(frame)] = (frame, 8, "vm", original, True, 0)
    stage._finish_store(c, frame, normal=False)
    assert c.last_store == (8, "vm", original, changed, True, False)
    assert c.capture_error is capture and c.primary is primary
    assert c.last_store_attempt[0] is frame


def test_electrical_falsey_source_and_capture_errors_stay_distinct():
    class Falsey(ValueError):
        def __bool__(self):
            return False

    primary, cause, capture = Falsey("source"), RuntimeError("cause"), OSError("capture")
    primary.__cause__ = cause
    c = context(primary=primary)
    stage._capture(c, "return", capture, primary)
    assert c.primary is primary and c.primary.__cause__ is cause
    assert c.capture_error is capture and c.last_capture[2] is primary


def _operation_fixture(monkeypatch, *, caller="get_current"):
    # Metadata-only invocation frame; no native owner or numerical delegate.
    frame = NS(f_code=object())
    c = context(body_names={frame.f_code: caller})
    c.frames[id(frame)] = dict(frame=frame, returned=False)
    monkeypatch.setattr(stage, "_check", lambda value: None)
    # These existing journal tests isolate before/after-delegate behavior.
    # Separate real-frame controls below exercise the actual admission gate.
    monkeypatch.setattr(stage, "_operation_source", lambda *args: None)

    def guard(value):
        if value.entry_error is not None:
            raise value.entry_error
        if value.capture_error is not None:
            raise value.capture_error

    monkeypatch.setattr(stage, "_guard", guard)
    return c, frame


def test_electrical_helper_nested_call_retains_parent_and_raw_return(monkeypatch):
    c, frame = _operation_fixture(monkeypatch)
    parent = dict(operation="get_current")
    c.operation = parent
    returned = object()
    c.external["dot"] = lambda *args: returned
    assert stage._operation_call(c, "dot", (object(),), {}, frame) is returned
    assert c.operation is parent and c.last_helper_return[1] is returned
    assert c.helper_calls[0]["entered"] and c.helper_calls[0]["returned"]


@pytest.mark.parametrize(
    "failure",
    ("missing_frame", "completed_frame", "foreign_frame", "wrong_parent", "wrong_body", "non_ecm"),
)
def test_electrical_rejects_detached_wrong_or_non_ecm_helper_before_delegate(failure, monkeypatch):
    c, frame = _operation_fixture(monkeypatch)
    calls = []
    c.methods["gradient"] = lambda *args: calls.append("delegate")
    name = "gradient"
    if failure == "missing_frame":
        c.frames.clear()
    elif failure == "completed_frame":
        c.frames[id(frame)]["returned"] = True
    elif failure == "foreign_frame":
        c.frames[id(frame)]["frame"] = object()
    elif failure == "wrong_parent":
        c.operation = dict(operation="unrelated")
    elif failure == "wrong_body":
        c.body_names[frame.f_code] = "diff"
    else:
        name = "smooth_flux"
    with pytest.raises(stage.ElectricalRejected):
        stage._operation_call(c, name, (), {}, frame)
    assert c.invalid and c.last_helper["entered"] is False and calls == []


def test_electrical_second_get_current_attempt_is_sticky(monkeypatch):
    c, frame = _operation_fixture(monkeypatch, caller="update_V")
    calls = []
    c.methods["get_current"] = lambda *args: calls.append("first")
    stage._operation_call(c, "get_current", (), {}, frame)
    with pytest.raises(stage.ElectricalRejected) as caught:
        stage._operation_call(c, "get_current", (), {}, frame)
    assert c.entry_error is caught.value and calls == ["first"]


def test_electrical_helper_entry_capture_stops_delegate(monkeypatch):
    c, frame = _operation_fixture(monkeypatch)
    failure = OSError("enter append")
    calls = []

    class Fails:
        def append(self, row):
            raise failure

    c.helper_calls = Fails()
    c.external["dot"] = lambda: calls.append("called")
    with pytest.raises(OSError) as caught:
        stage._operation_call(c, "dot", (), {}, frame)
    assert caught.value is failure and calls == [] and c.last_helper["entered"] is False


def test_electrical_native_helper_error_keeps_cause_parent_and_no_return(monkeypatch):
    c, frame = _operation_fixture(monkeypatch)
    failure, cause = ValueError("synthetic source failure"), OSError("cause")
    failure.__cause__ = cause
    parent = dict(operation="get_current")
    c.operation = parent

    def fail():
        raise failure

    c.external["dot"] = fail
    with pytest.raises(ValueError) as caught:
        stage._operation_call(c, "dot", (), {}, frame)
    assert caught.value is failure and failure.__cause__ is cause
    assert c.primary is failure and c.operation is parent
    assert c.last_helper_error[1] is failure and c.last_helper["returned"] is False


def test_electrical_post_return_failure_does_not_lose_actual_helper_result(monkeypatch):
    c, frame = _operation_fixture(monkeypatch)
    returned, failure = object(), OSError("post-return observation")
    c.external["dot"] = lambda: returned
    count = []

    def check(value):
        count.append(None)
        if len(count) == 2:
            raise failure

    monkeypatch.setattr(stage, "_check", check)
    with pytest.raises(OSError) as caught:
        stage._operation_call(c, "dot", (), {}, frame)
    assert caught.value is failure and c.last_helper_return[1] is returned
    assert c.last_helper["raw"] is returned and c.last_helper["returned"]


@pytest.mark.parametrize("broken", (None, 0, 1))
def test_electrical_final_cleanup_attempts_both_hooks_and_samples_both_orders(broken):
    required, state, calls = (object(), object()), [None, None], []

    def setter(index):
        def set_value(value):
            calls.append(("set", index))
            if index == broken:
                raise OSError("restore failed")
            state[index] = value

        return set_value

    def getter(index):
        def get_value():
            calls.append(("get", index))
            return state[index]

        return get_value

    c = context(
        required_hooks=required,
        setters=(setter(0), setter(1)),
        getters=(getter(0), getter(1)),
        cleanup_errors=(),
    )
    stage._restore(c)
    assert calls == [("set", 1), ("set", 0), ("get", 0), ("get", 1), ("get", 1), ("get", 0)]
    assert c.hooks_safe is (broken is None)
    assert bool(c.cleanup_errors) is (broken is not None)


def test_electrical_metadata_bindings_reject_equal_code_replacement(monkeypatch):
    def atoms(function):
        return function, function.__code__

    original = stage._stores
    c = context(atoms=atoms, checker=(atoms, atoms.__code__, atoms.__globals__))
    c.metadata = (("_stores", original, stage._callable_atoms(c, original)),)
    stage._bootstrap(c)
    replacement = FunctionType(original.__code__, original.__globals__)
    monkeypatch.setattr(stage, "_stores", replacement)
    with pytest.raises(ValueError, match="replaced"):
        stage._bootstrap(c)


def test_electrical_run_keeps_original_same_simulator_method_boundary():
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_run")
    assert ast.unparse(node.body[-1]) == "return context.sim.update_V(context.cells, context.p)"


def test_electrical_literal_and_numerical_dispatch_are_blocked_by_runner():
    for module, name in (
        ("cells.processes.betse_native_init_electrical_source", "update_V"),
        ("cells.processes.betse_native_init_electrical", "_namespace"),
        ("cells.processes.betse_native_init_electrical", "_run"),
    ):
        assert software.is_forbidden_frame(
            NS(f_globals={"__name__": module}, f_code=NS(co_name=name, co_filename=__file__))
        )
    assert sys.getprofile() is not None


@pytest.mark.parametrize(
    "drift",
    (None, "code", "globals", "defaults", "after_proof", "after_ready_code", "after_ready_slot"),
)
def test_electrical_parent_hook_authentication_precedes_any_parent_delegate(
    drift, tmp_path, monkeypatch
):
    payload = (
        "def _claim_for_electrical(owner, *, expected, transition, entries):\n"
        "    raise AssertionError('never executed')\n"
        "def _check_electrical_authority(transition, *, flag=False):\n"
        "    raise AssertionError('never executed')\n"
    )
    path = tmp_path / "metadata_parent.py"
    path.write_text(payload)
    module = ModuleType("metadata_parent")
    module.__file__ = str(path)
    exec(compile(payload, str(path), "exec"), vars(module))
    calls = []
    module.previous = NS(_pin=lambda value: type(value) is str and len(value) == 64)
    module._ready = lambda: calls.append("metadata_ready")
    monkeypatch.setattr(stage, "storage", module)
    monkeypatch.setattr(
        stage, "PARENT_SOURCE_SHA256", stage.hashlib.sha256(path.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(stage, "PARENT_REVIEW_SHA256", "0" * 64)
    monkeypatch.setattr(stage, "PARENT_CLAIM", "_claim_for_electrical")
    monkeypatch.setattr(stage, "PARENT_CHECK", "_check_electrical_authority")
    fn = module._check_electrical_authority
    if drift == "code":
        fn.__code__ = (lambda transition, flag=False: None).__code__
    elif drift == "globals":
        module._check_electrical_authority = FunctionType(fn.__code__, dict(vars(module)))
    elif drift == "defaults":
        fn.__kwdefaults__["flag"] = True
    elif drift == "after_proof":

        def after_proof():
            calls.append("metadata_ready")
            module._check_electrical_authority = lambda value: None

        module._ready = after_proof
    if drift is None:
        assert stage._ready().module is module and calls == ["metadata_ready"]
    elif drift.startswith("after_ready"):
        binding = stage._ready()
        if drift == "after_ready_code":
            fn.__code__ = (lambda value: None).__code__
        else:
            module._check_electrical_authority = lambda value: None
        with pytest.raises(ValueError, match="Authenticated"):
            stage._call_parent(context(parent_binding=binding), "check", object())
        assert calls == ["metadata_ready"]
    else:
        with pytest.raises(ValueError):
            stage._ready()
        assert calls == (["metadata_ready"] if drift == "after_proof" else [])


@pytest.mark.parametrize("drift", (None, "global_shadow", "provider_copy", "provider_zip"))
def test_electrical_clone_builtin_provider_and_global_resolution(drift):
    code = compile(
        "def selected(left, right):\n    return zip(left, right)\n", "<builtin-metadata>", "exec"
    )
    namespace = {"__builtins__": vars(builtins)}
    exec(code, namespace)
    function = namespace["selected"]
    if drift == "global_shadow":
        namespace["zip"] = lambda *args: None
    elif drift in ("provider_copy", "provider_zip"):
        namespace["__builtins__"] = dict(vars(builtins))
        if drift == "provider_zip":
            namespace["__builtins__"]["zip"] = lambda *args: None
        assert function.__builtins__ is vars(builtins)  # old cached mapping has not changed
    if drift is None:
        rows = stage._builtin_bindings(function)
        assert any(key == "zip" and value is builtins.zip for _, key, value in rows)
    else:
        with pytest.raises(ValueError, match="builtin"):
            stage._builtin_bindings(function)


@pytest.mark.parametrize("drift", ("global_shadow", "provider_copy"))
def test_electrical_live_binding_rechecks_clone_builtins_after_acquisition(drift, monkeypatch):
    namespace = {"__builtins__": vars(builtins)}
    exec(
        compile(
            "def selected(left, right):\n    return zip(left, right)\n",
            "<builtin-metadata>",
            "exec",
        ),
        namespace,
    )
    function = namespace["selected"]

    class MetadataSim:
        def update_V(self):
            raise AssertionError("No source delegate")

    # This isolates the real namespace binding checker; no owner is issued and
    # none of its numerical-state/parent-authority checks is asserted here.
    c = context(
        parent_binding=object(),
        storage_parent=NS(trial=object()),
        phase=object(),
        p=object(),
        cells=object(),
        sim=MetadataSim(),
        handler=object(),
        cache=object(),
        entries=object(),
        parent_claim=lambda: None,
        parent_check=lambda: None,
        originals={},
        methods={"selected": function},
        wrappers={},
        external={},
        reuse_functions=(),
        namespaces=(),
        facades=(),
        external_members=(),
        atoms=lambda value: (value,),
    )
    monkeypatch.setattr(stage, "_bootstrap", lambda value: None)
    monkeypatch.setattr(stage.storage, "_observer_bindings", lambda value: ())
    stage._binding(c)
    if drift == "global_shadow":
        namespace["zip"] = lambda *args: None
    else:
        namespace["__builtins__"] = dict(vars(builtins))
    with pytest.raises(ValueError, match="builtin"):
        stage._binding(c)


@pytest.mark.parametrize(
    "name,changed",
    (
        ("HH_Decomp", (None, 2.0)),
        ("HH_Decomp", (None, 1)),
        ("gradient", (False,)),
        ("diff", (False,)),
    ),
)
def test_electrical_native_default_drift_refuses_before_body(name, changed):
    node, code = stage._definitions()[name]
    expected = tuple(ast.literal_eval(v) for v in node.args.defaults)
    function = FunctionType(code, {"__builtins__": __builtins__}, name, expected)
    stage._native_defaults(function, node)
    function.__defaults__ = changed
    with pytest.raises(ValueError, match="defaults"):
        stage._native_defaults(function, node)


@pytest.mark.parametrize("drift", ("keyword", "wrapped", "implementation"))
def test_electrical_live_callable_binding_includes_keyword_and_delegate_code(drift):
    def child(*, selected=None):
        return selected

    def helper():
        return None

    helper.__wrapped__ = child
    helper._implementation = child
    c = context(atoms=stage.storage.previous.previous.previous._atoms)
    original_code = helper.__code__
    before = stage._callable_atoms(c, helper)
    if drift == "keyword":
        child.__kwdefaults__["selected"] = object()
    elif drift == "wrapped":
        helper.__wrapped__ = lambda: None
    else:
        child.__code__ = (lambda: None).__code__
    after = stage._callable_atoms(c, helper)
    assert helper.__code__ is original_code
    assert len(before) != len(after) or any(a is not b for a, b in zip(before, after, strict=True))


@pytest.mark.parametrize("drift", (None, "direct", "replacement"))
def test_electrical_real_wrapper_and_source_frame_chain(drift, monkeypatch):
    c = context(wrappers={})
    returned, input_value = object(), object()
    calls = []
    monkeypatch.setattr(stage, "_check", lambda value: None)
    monkeypatch.setattr(stage, "_guard", lambda value: None)

    def delegate(value, *, selected):
        calls.append((value, selected))
        return returned

    c.external["dot"] = delegate
    wrapper = stage._operation_wrapper(c, "dot")
    c.wrappers["dot"] = wrapper

    def body():
        frame = sys._getframe()
        c.frames[id(frame)] = dict(frame=frame, returned=False)
        c.body_names[frame.f_code] = "get_current"
        if drift == "direct":
            return stage._operation_call(c, "dot", (input_value,), {"selected": input_value}, frame)
        actual = stage._operation_wrapper(c, "dot") if drift == "replacement" else wrapper
        return actual(input_value, selected=input_value)

    if drift is None:
        assert body() is returned and calls == [(input_value, input_value)]
    else:
        with pytest.raises(stage.ElectricalRejected):
            body()
        assert calls == [] and c.invalid


@pytest.mark.parametrize("fail", (False, True))
def test_electrical_opcode_journal_retains_tuple_targets_after_actual_multiline_rhs(fail):
    c = context(store_fields=frozenset(("left", "right", "later")))
    old_left, old_right, old_later = object(), object(), object()
    c.sim = NS(left=old_left, right=old_right, later=old_later)
    calls = []
    failure = ValueError("multiline RHS failed before STORE_ATTR")

    def rhs():
        assert c.stores == []  # no store has happened while the RHS is evaluated
        calls.append("rhs")
        return 3, 4

    def later_term():
        assert [row[1] for row in c.stores] == ["left", "right"]
        if fail:
            raise failure
        return c.sim.right

    def body():
        # fmt: off
        c.sim.left, c.sim.right = rhs()
        c.sim.later = (
            c.sim.left
            + later_term()
        )
        # fmt: on

    c.store_instructions = {body.__code__: stage._store_instructions(body.__code__)}
    previous_trace = sys.gettrace()

    def trace(frame, event, arg):
        if frame.f_code is body.__code__:
            frame.f_trace_opcodes = True
            stage._observe_stores(c, frame, event)
        return trace

    try:
        sys.settrace(trace)
        if fail:
            with pytest.raises(ValueError) as caught:
                body()
            assert caught.value is failure
        else:
            body()
    finally:
        sys.settrace(previous_trace)
    assert calls == ["rhs"]
    expected = [
        ("left", old_left, 3, True, True),
        ("right", old_right, 4, True, True),
    ]
    if not fail:
        expected.append(("later", old_later, 7, True, True))
    else:
        assert c.sim.later is old_later
    assert [
        (name, before, after, existed, complete)
        for _, name, before, after, existed, complete in c.stores
    ] == expected
    assert not c.pending_stores
    code = stage._definitions()["get_current"][1]
    assert [name for line, name in stage._store_instructions(code).values() if line == 64] == [
        "J_env_x",
        "J_env_y",
    ]


@pytest.mark.parametrize("falsey", (False, True))
def test_electrical_caller_cleanup_boundary_survives_restore_entry_failure(falsey):
    class Falsey(ValueError):
        def __bool__(self):
            return False

    primary = Falsey("source") if falsey else ValueError("source")
    cause, capture = OSError("cause"), RuntimeError("restore entry")
    primary.__cause__ = cause
    required, state, calls = (object(), object()), [None, None], []

    def setter(index):
        def assign(value):
            state[index] = value
            calls.append(index)

        return assign

    c = context(
        cleanup_errors=(),
        required_hooks=required,
        setters=(setter(0), setter(1)),
        getters=(lambda: state[0], lambda: state[1]),
    )
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    prepare = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "prepare")
    boundary = next(
        n
        for n in ast.walk(prepare)
        if isinstance(n, ast.Try)
        and n.finalbody
        and any(
            isinstance(child, ast.Try)
            and any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "_restore"
                for call in ast.walk(child)
            )
            for child in n.finalbody
        )
    )
    cleanup = next(child for child in boundary.finalbody if isinstance(child, ast.Try))
    # Execute the exact protected caller-boundary AST as metadata, with no
    # parent/phase/native fixture and with the production _restore call failing.
    node = ast.parse(
        "def boundary(context):\n    try:\n        raise primary\n    finally:\n        pass\n"
    ).body[0]
    node.body[0].finalbody = [copy.deepcopy(cleanup)]
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))

    def failed_restore(value):
        raise capture

    namespace = dict(primary=primary, _restore=failed_restore)
    exec(compile(module, "<electrical-cleanup-metadata>", "exec"), namespace)
    with pytest.raises(ValueError) as caught:
        namespace["boundary"](c)
    assert caught.value is primary and primary.__cause__ is cause
    assert c.cleanup_entry_error is capture and c.invalid and c.hooks_safe
    assert calls == [1, 0] and all(a is required[0] and b is required[1] for a, b in c.final_hooks)
