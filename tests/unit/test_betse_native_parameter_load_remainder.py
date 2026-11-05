"""Prepared blocked controls. Not executed by source-only development.

No genuine positive parent is synthesized. Source compilation, refusal paths
and observation/data-association helpers are checked independently; a future
positive continuity run requires Root's actual constants/handoff authority.
"""

import ast
import builtins
import copy
import dis
import json
import struct
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path
from types import CodeType, FunctionType, ModuleType, SimpleNamespace

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
conditional_grant_contract = inherited.conditional_grant_contract


def _scalar_capture_context(**fields):
    """Only a graph-reader adapter; never an issued parameter or source owner."""
    runtime = SimpleNamespace(runtime_types=frozenset())
    birth = SimpleNamespace(source=SimpleNamespace(yaml=SimpleNamespace))
    ancestor = SimpleNamespace(runtime=runtime, birth=birth)
    return SimpleNamespace(
        p=SimpleNamespace(**fields),
        parent=SimpleNamespace(parent=SimpleNamespace(parent=ancestor)),
    )


@pytest.mark.parametrize(
    "case",
    [
        "repeat",
        "history",
        "falsey_history",
        "graph",
        "colormap",
        "output",
        "audit",
        "consumed",
        "run_sim",
    ],
)
def test_completed_parameter_read_reserves_real_ancestry_and_releases_on_failure(monkeypatch, case):
    """Registry adapter only; history/outputs are synthetic, never native authority.

    Exercise the public getter and actual inherited registry/audit/graph machinery
    with the closed source context shape that the real load leaves behind.
    """

    class FalseyError(ValueError):
        def __bool__(self):
            return False

    context = _scalar_capture_context(value=1.25, fields={"label": "unchanged"})
    owner = object.__new__(stage.WorldReadyParametersOwner)
    context.owner = owner
    context.loaded = SimpleNamespace(owner=object())
    context.active = context.validating = context.invalid = False
    context.capture_errors = ()
    context.after_graph = stage._capture(context)
    context.after_cm = object()
    monkeypatch.setitem(stage._ISSUED, owner, context)
    paths = stage.previous.previous.mod.subconfigs.paths
    actual_install = paths._install_audit
    reservations, checkpoints = [], []
    cause = OSError("synthetic validation cause")
    primary = (FalseyError if case == "falsey_history" else ValueError)("synthetic read refusal")

    def check_rows(name):
        validation = stage._ACTIVE[-1]
        rows = stage._stacks(validation)
        assert len(rows) > 5 and len({id(stack) for stack, _ in rows}) == len(rows)
        assert not hasattr(context, "guard") and validation is not context
        assert all(len(stack) == 1 and stack[-1] is value for stack, value in rows)
        assert all(value is validation for stack, value in rows if stack is not paths._ACTIVE)
        assert paths._ACTIVE[-1] is validation.guard
        assert validation.guard.active and validation.guard.audit_ready
        checkpoints.append(name)
        return validation

    def refuse():
        raise primary from cause

    def install(guard):
        actual_install(guard)
        validation = check_rows("audit")
        assert validation.guard is guard
        reservations.append(validation)
        if case == "audit":
            refuse()

    def history(actual_owner):
        assert actual_owner is owner
        check_rows("history")
        if case in ("history", "falsey_history"):
            refuse()
        return object()

    def colormaps(actual_context):
        assert actual_context is context
        check_rows("colormaps")
        if case == "colormap":
            refuse()
        return context.after_cm

    def same_colormaps(current, baseline):
        assert current is baseline is context.after_cm

    def outputs(actual_context):
        assert actual_context is context
        check_rows("outputs")
        if case == "output":
            refuse()

    monkeypatch.setattr(paths, "_install_audit", install)
    monkeypatch.setattr(stage, "validate_completed_history", history)
    monkeypatch.setattr(stage, "_colormaps", colormaps)
    monkeypatch.setattr(stage.previous, "_same_cm", same_colormaps)
    monkeypatch.setattr(stage, "_outputs", outputs)
    if case == "graph":
        context.p.value = 2.5
    elif case == "consumed":
        monkeypatch.setitem(stage._CONSTRUCTED, owner, object())
    elif case == "run_sim":
        context.p._run_sim = False
    original_fields = dict(vars(context.p))

    if case == "repeat":
        assert owner.parameters is context.p
        assert owner.parameters is context.p
        assert len(reservations) == 2 and reservations[0] is not reservations[1]
        assert checkpoints == ["audit", "history", "colormaps", "outputs"] * 2
        assert context.invalid is False
    else:
        with pytest.raises(ValueError) as caught:
            _ = owner.parameters
        if case in ("audit", "history", "falsey_history", "colormap", "output"):
            assert caught.value is primary and caught.value.__cause__ is cause
        elif case in ("consumed", "run_sim"):
            assert type(caught.value) is stage.LoadRejected
            assert caught.value.stage == "constructed" and caught.value.partial is context
            assert checkpoints == ["audit", "history"]
        elif case == "graph":
            assert checkpoints == ["audit", "history"]
        assert context.invalid is True and len(reservations) == 1
    for validation in reservations:
        assert validation.guard.active is False
        assert all(not stack for stack, _ in stage._stacks(validation))
    assert context.validating is False and not hasattr(context, "guard")
    assert context.capture_errors == () and vars(context.p) == original_fields
    assert stage._ISSUED[owner] is context and context.owner is owner


@pytest.mark.parametrize(
    "bits",
    [
        "bff0000000000000",
        "3ff0000000000000",
        "0000000000000000",
        "8000000000000000",
        "7ff0000000000000",
        "fff0000000000000",
        "7ff8000000000001",
        "fff8000000001234",
    ],
)
def test_remainder_scalar_capture_preserves_exact_type_bits_and_aliases(bits):
    import numpy as np

    scalar = np.frombuffer(bytes.fromhex(bits), dtype=">f8")[0]
    assert type(scalar) is np.float64
    context = _scalar_capture_context(z_M_env=scalar, z_M_cell=scalar, values={"M": scalar})
    objects, graph = stage._capture(context)
    node = next(row for row in graph["nodes"] if row["type"] == "numpy.float64")
    assert node["float64_value"] == bits
    assert any(value is scalar for value in objects) and any(
        value is np.float64 for value in objects
    )
    roots = dict(graph["roots"])
    assert roots["z_M_env"] == roots["z_M_cell"] == ("ref", node["token"])
    nested = graph["nodes"][roots["values"][1]]["dict_storage"]
    assert nested[0][1] == ("ref", node["token"])
    assert context.p.z_M_env is context.p.z_M_cell is context.p.values["M"] is scalar
    assert struct.pack(">d", float.__float__(scalar)).hex() == bits
    assert context.parent.parent.parent.runtime.runtime_types == frozenset()


def test_remainder_scalar_capture_keeps_ordinary_graph_and_default_refusal_unchanged():
    import numpy as np

    context = _scalar_capture_context(number=1.25, fields={"label": "untouched"})
    before = stage.prefix.graphs.capture(
        vars(context.p), yaml_base=SimpleNamespace, runtime_types=frozenset()
    )
    after = stage._capture(context)
    stage.prefix.parameters.inherited._same_graph(before, after)
    with pytest.raises(stage.prefix.graphs.UnsupportedYamlGraph, match="numpy.float64"):
        stage.prefix.graphs.capture(
            {"valence": np.float64(-1)}, yaml_base=SimpleNamespace, runtime_types=frozenset()
        )
    assert (
        stage.prefix.graphs.MAX_NODES,
        stage.prefix.graphs.MAX_BYTES,
        stage.prefix.graphs.MAX_DEPTH,
    ) == (100000, 16 * 2**20, 96)


@pytest.mark.parametrize("kind", ["float32", "int64", "array", "scalar_subclass"])
def test_remainder_scalar_capture_rejects_unselected_scalar_and_array_types(kind):
    import numpy as np

    class Subclass(np.float64):
        def __float__(self):
            raise AssertionError("Unknown scalar conversion must never run")

    value = {
        "float32": lambda: np.float32(-1),
        "int64": lambda: np.int64(-1),
        "array": lambda: np.array([-1.0]),
        "scalar_subclass": lambda: Subclass(-1),
    }[kind]()
    with pytest.raises(stage.prefix.graphs.UnsupportedYamlGraph):
        stage._capture(_scalar_capture_context(value=value))


@pytest.mark.parametrize("retarget", ["same_bits_object", "python_float", "different_bits"])
def test_remainder_scalar_capture_unchanged_bits_do_not_replace_original_object(retarget):
    import numpy as np

    value = np.float64(-1)
    context = _scalar_capture_context(value=value, alias=value)
    before = stage._capture(context)
    context.p.value = {
        "same_bits_object": lambda: np.float64(-1),
        "python_float": lambda: -1.0,
        "different_bits": lambda: np.float64(1),
    }[retarget]()
    assert context.p.value is not value and context.p.alias is value
    with pytest.raises(ValueError):
        stage.prefix.parameters.inherited._same_graph(before, stage._capture(context))


@pytest.mark.parametrize("drift", ["float32", "python_float", "fake_class", "registry", "module"])
def test_remainder_scalar_capture_requires_original_class_and_namespace(monkeypatch, drift):
    import numpy as np

    registry = stage.previous.previous.state
    original = np.float64
    context = _scalar_capture_context(value=original(-1))
    stage._capture(context)
    if drift == "registry":
        monkeypatch.setattr(
            registry, "NUMPY_SCALARS", tuple(k for k in registry.NUMPY_SCALARS if k is not original)
        )
    elif drift == "module":
        copied = ModuleType("numpy")
        vars(copied).update(vars(np))
        monkeypatch.setattr(registry, "np", copied)
    else:
        replacement = {
            "float32": np.float32,
            "python_float": float,
            "fake_class": type("float64", (float,), {"__module__": "numpy"}),
        }[drift]
        monkeypatch.setattr(np, "float64", replacement)
    with pytest.raises(ValueError, match="retained NumPy"):
        stage._capture(context)


def _package_wrapper_metadata(monkeypatch):
    """Real library decoration of compiled metadata; never run native bodies."""
    import numpy as np
    from beartype import beartype
    from beartype.claw._clawstate import claw_state

    path, node, _, _, _, balance_ast = stage._source()
    compiled = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    class_code = next(
        c for c in compiled.co_consts if type(c) is CodeType and c.co_name == "Parameters"
    )
    ion_code = next(
        c for c in class_code.co_consts if type(c) is CodeType and c.co_name == "_load_ion_profile"
    )
    balance_code = next(
        c for c in compiled.co_consts if type(c) is CodeType and c.co_name == "_balance_charge"
    )
    module = ModuleType("metadata_only_remainder")
    namespace = vars(module)
    namespace.update(__builtins__=vars(builtins), np=np, SequenceTypes=(Sequence, np.ndarray))
    ion = FunctionType(ion_code, namespace)
    ion.__annotations__ = {"return": None}
    cls = type("Parameters", (), {"__module__": module.__name__, "_load_ion_profile": ion})
    assert beartype(cls) is cls
    balance = FunctionType(balance_code, namespace)
    balance.__annotations__ = dict(
        concentrations=namespace["SequenceTypes"], zs=namespace["SequenceTypes"], return_=tuple
    )
    balance.__annotations__["return"] = balance.__annotations__.pop("return_")
    namespace["_balance_charge"] = beartype(balance)
    # Opaque bindings complete the compile-only module's lookup surface. The
    # native entry guard remains active; none of these bodies may execute.
    for code in (ion_code, balance_code):
        for instruction in dis.get_instructions(code):
            if instruction.opname == "LOAD_GLOBAL" and instruction.argval not in vars(builtins):
                namespace.setdefault(instruction.argval, object())
    namespace["__claw_state_beartype__"] = claw_state
    monkeypatch.setitem(
        claw_state.module_name_to_beartype_conf,
        module.__name__,
        cls._load_ion_profile.__kwdefaults__["__beartype_conf"],
    )
    types_module = ModuleType("betse.util.type.types")
    types_module.SequenceTypes = namespace["SequenceTypes"]
    monkeypatch.setitem(sys.modules, types_module.__name__, types_module)
    return SimpleNamespace(
        cls=cls,
        namespace=namespace,
        ion=ion,
        balance=balance,
        node=node,
        balance_ast=balance_ast,
        path=path,
    )


def _wrapped_observation(observed, monkeypatch):
    """Real type wrappers and real trace/profile calls around toy bodies only."""
    import numpy as np
    from beartype import beartype

    h, context = observed, observed.context
    union = (Sequence, np.ndarray)
    context.api.balance.__annotations__ = {"concentrations": union, "zs": union, "return": tuple}
    balance_wrapper = beartype(context.api.balance)
    context.api.ion.__annotations__ = {"return": None}
    assert beartype(context.api.cls) is context.api.cls
    # Toy closure dispatch is changed before the observer starts. Production
    # retains native module globals and its actual installed class slots.
    cells = dict(
        zip(context.api.ion.__code__.co_freevars, context.api.ion.__closure__, strict=True)
    )
    cells["balance"].cell_contents = balance_wrapper
    context.api.ion_wrapper = vars(context.api.cls)["_load_ion_profile"]
    context.api.balance_wrapper = balance_wrapper
    context.api.namespace = {"_balance_charge": balance_wrapper}
    return h


@pytest.mark.parametrize(
    "case",
    [
        "metadata-valid",
        "metadata-ion-unwrapped",
        "metadata-balance-unwrapped",
        "metadata-ion-code",
        "metadata-balance-code",
        "metadata-ion-delegate",
        "metadata-balance-delegate",
        "metadata-balance-default-copy",
        "metadata-balance-annotations",
        "metadata-balance-meta",
        "metadata-balance-config",
        "metadata-balance-class-stack",
        "metadata-original-globals",
        "metadata-original-body",
        "metadata-sequence-member",
        "metadata-balance-argument-cache",
        "observe-valid",
        "observe-body-failure",
        "observe-direct-ion",
        "observe-direct-balance",
        "observe-ion-delegate",
        "observe-balance-delegate",
        "observe-wrapper-code",
        "observe-caught-reentry",
        "observe-wrapper-return-capture",
        "observe-falsey-primary",
        "observe-trace-entry-rejection",
        "observe-profile-entry-rejection",
        "observe-trace-exception-rejection",
    ],
)
def test_installed_package_wrapper_repair(case, monkeypatch, observed):
    if case.startswith("metadata-"):
        h = _package_wrapper_metadata(monkeypatch)
        before = stage._native_helpers(h.cls, h.namespace, h.node, h.balance_ast, h.path)
        wrapper = h.cls._load_ion_profile if "ion" in case else h.namespace["_balance_charge"]
        if case == "metadata-ion-unwrapped":
            h.cls._load_ion_profile = h.ion
        elif case == "metadata-balance-unwrapped":
            h.namespace["_balance_charge"] = h.balance
        elif case in ("metadata-ion-code", "metadata-balance-code"):
            wrapper.__code__ = (lambda *args, **kwargs: None).__code__
        elif case in ("metadata-ion-delegate", "metadata-balance-delegate"):
            original = wrapper.__wrapped__
            wrapper.__kwdefaults__["__beartype_func"] = FunctionType(
                original.__code__, original.__globals__
            )
        elif case == "metadata-balance-default-copy":
            value = next(iter(wrapper.__kwdefaults__))
            wrapper.__kwdefaults__[value] = tuple(list(wrapper.__kwdefaults__[value]))
        elif case == "metadata-balance-annotations":
            h.balance.__annotations__["zs"] = tuple
        elif case == "metadata-balance-meta":
            wrapper.__kwdefaults__["__beartype_check_meta"] = (
                h.cls._load_ion_profile.__kwdefaults__["__beartype_check_meta"]
            )
        elif case == "metadata-balance-config":
            wrapper.__kwdefaults__["__beartype_conf"] = object()
        elif case == "metadata-balance-class-stack":
            meta = wrapper.__kwdefaults__["__beartype_check_meta"]
            object.__setattr__(meta, "cls_stack", (h.cls,))
        elif case == "metadata-original-globals":
            foreign = FunctionType(h.balance.__code__, dict(h.namespace))
            foreign.__annotations__ = h.balance.__annotations__
            wrapper.__wrapped__ = foreign
        elif case == "metadata-original-body":
            h.balance.__code__ = (lambda a, b: None).__code__
        elif case == "metadata-sequence-member":
            h.namespace["SequenceTypes"] = (Sequence, list)
        elif case == "metadata-balance-argument-cache":
            wrapper.__beartype_args_lens = (2, False, False, False)
        if case == "metadata-valid":
            after = stage._native_helpers(h.cls, h.namespace, h.node, h.balance_ast, h.path)
            assert before.ion is after.ion is h.ion and before.balance is after.balance is h.balance
            assert len(before.atoms) == len(after.atoms)
            assert all(a is b for a, b in zip(before.atoms, after.atoms, strict=True))
        else:
            with pytest.raises(ValueError):
                stage._native_helpers(h.cls, h.namespace, h.node, h.balance_ast, h.path)
        assert not observed.bodies  # Native metadata and toy bodies were never called.
        return

    h = _wrapped_observation(observed, monkeypatch)
    context = h.context
    prior, trace = sys.getprofile(), sys.gettrace()
    callbacks, nested = [], []
    capture = SyntheticCaptureFailure("wrapper return observation failed")
    if case in (
        "observe-body-failure",
        "observe-falsey-primary",
        "observe-trace-exception-rejection",
    ):
        h.control["fail"] = True
    if case == "observe-direct-ion":
        h.context.api.cls._load_ion_profile = h.context.api.ion
    elif case == "observe-direct-balance":
        cells = dict(zip(h.ion.__code__.co_freevars, h.ion.__closure__, strict=True))
        cells["balance"].cell_contents = context.api.balance

    def inherited_profile(frame, event, value):
        if prior is not None:
            prior(frame, event, value)
        if event == "call" and frame.f_code is context.api.ion_wrapper.__code__ and not callbacks:
            callbacks.append("ion")
            if case == "observe-profile-entry-rejection":
                raise capture
            elif case in ("observe-ion-delegate", "observe-balance-delegate"):
                role = "ion" if case == "observe-ion-delegate" else "balance"
                original = getattr(context.api, role)
                getattr(context.api, role + "_wrapper").__kwdefaults__["__beartype_func"] = (
                    FunctionType(
                        original.__code__, original.__globals__, closure=original.__closure__
                    )
                )
            elif case == "observe-wrapper-code":
                context.api.balance_wrapper.__code__ = (lambda *args, **kwargs: None).__code__
            elif case == "observe-caught-reentry":
                try:
                    context.api.ion(context.p)
                except BaseException as error:
                    nested.append(error)
        if (
            event == "return"
            and frame.f_code is context.api.balance_wrapper.__code__
            and case in ("observe-wrapper-return-capture", "observe-falsey-primary")
        ):
            raise capture

    def inherited_trace(frame, event, value):
        if trace is not None:
            trace(frame, event, value)
        if (
            case == "observe-trace-entry-rejection"
            and event == "call"
            and frame.f_code is context.api.ion_wrapper.__code__
        ) or (
            case == "observe-trace-exception-rejection"
            and event == "exception"
            and frame.f_code is context.api.balance.__code__
            and value[1] is h.primary
        ):
            raise capture
        return inherited_trace

    sys.setprofile(inherited_profile)
    selected_trace = inherited_trace if case.startswith("observe-trace-") else trace
    sys.settrace(selected_trace)
    try:
        if case == "observe-valid":
            with stage._observe(context):
                stage._invoke(context)
            assert context.entries == context.delegates
            assert context.entries["ion_wrapper"] == context.entries["ion"] == 1
            assert context.entries["balance_wrapper"] == context.entries["balance"] == 2
            assert all(
                a is b
                for a, b in zip(
                    context.returns["balance"], context.returns["balance_wrapper"], strict=True
                )
            )
            assert h.bodies == ["tail", "ion", "alias", "balance", "balance"]
        else:
            with pytest.raises(BaseException) as caught:
                with stage._observe(context):
                    stage._invoke(context)
            assert not hasattr(context.p, "after_second")
            if case in (
                "observe-body-failure",
                "observe-falsey-primary",
                "observe-trace-exception-rejection",
            ):
                assert caught.value is h.primary and caught.value.__cause__ is h.cause
                assert context.source_error is h.primary
                if case != "observe-body-failure":
                    assert any(error is capture for _, error in context.capture_errors)
            if case in ("observe-trace-entry-rejection", "observe-profile-entry-rejection"):
                assert caught.value is capture and context.source_error is None
                assert context.delegates["ion_wrapper"] == context.delegates["ion"] == 0
                assert any(error is capture for _, error in context.capture_errors)
            if case == "observe-wrapper-return-capture":
                assert context.returns["balance"][0] is context.returns["balance_wrapper"][0]
                assert any(error is capture for _, error in context.capture_errors)
            if case == "observe-caught-reentry":
                assert nested and "ion" not in h.bodies
                assert nested[0] is context.observer_state.rejections[0]
        assert sys.getprofile() is inherited_profile and sys.gettrace() is selected_trace
    finally:
        sys.setprofile(prior)
        sys.settrace(trace)


def test_candidate_grant_api_keeps_actual_hook_refusing_before_retirement(monkeypatch):
    assert stage._hook() is stage.previous
    assert stage.HANDOFF_PRODUCER_SHA256 == stage.SOURCE_CANDIDATE_PREDECESSOR_SHA256
    # Retain the missing-connection control explicitly in the fresh source regime.
    monkeypatch.setattr(stage, "HANDOFF_PRODUCER_SHA256", None)
    for gate in (
        stage.RELEASE,
        stage.previous.RELEASE,
        stage.previous.previous.RELEASE,
        stage.previous.previous.mod.RELEASE,
    ):
        monkeypatch.setenv(gate, "1")
    before = len(stage._CONSUMED)
    with pytest.raises(stage.LoadRejected) as caught:
        stage.complete_load(None, law_id=stage.LAW_ID, enabled=True)
    assert caught.value.stage == "predecessor_handoff" and len(stage._CONSUMED) == before
    assert stage.source_plan()["candidate_source_grants_runtime_admission"] is False
    assert stage.source_plan()["runtime_hook_available"] is False


def test_actual_grant_object_survives_failed_enter_without_source_or_fake_owner(
    conditional_grant_contract,
    monkeypatch,
):
    h = conditional_grant_contract
    primary = SyntheticSourceFailure("conditional authority refusal before tail")
    h.flags["primary"] = primary
    calls = []

    def forbidden(self, **kwargs):
        calls.append(True)
        raise AssertionError("Tail/native work must not be entered")

    # Use the actual source-bound hook; only initial authority is conditional.
    # The refused parent never enters the original tail or issues a WorldReady owner.
    assert stage._hook() is stage.previous
    monkeypatch.setattr(stage, "_native", lambda context: SimpleNamespace(bindings=()))
    monkeypatch.setattr(stage, "_compile", lambda context: forbidden)
    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(stage.LoadRejected) as caught:
        stage.complete_load(h.owner, law_id=stage.LAW_ID, enabled=True)
    context = caught.value.partial
    assert caught.value.__cause__ is primary and context.operation_error is primary
    assert type(context.grant) is stage.previous.RemainderGrant
    assert context.grant.record.succeeded is False and primary.remainder_grant is context.grant
    assert context.parent_owner is h.owner and context.p is h.p and context.work == []
    assert calls == [] and context.owner is None and not stage._ACTIVE
    assert stage._hook() is stage.previous


def test_load_record_retains_separate_closed_grant_identity_and_metadata_work():
    metadata = ((0, "graph_capture", "attempted_metadata_only"),)
    value = stage.LoadRecord(
        "parent",
        "source",
        218,
        "BASIC",
        "before",
        "after",
        (),
        (),
        True,
        "",
        handoff_identity="actual-grant",
        handoff_work=metadata,
    )
    document = stage.record_document(value)
    assert document["handoff_identity"] == "actual-grant" and document["handoff_work"] is metadata
    assert document["work"] == () and document["biological_cases"] == 0
    with pytest.raises(stage.LoadRejected):
        stage._context(value)  # An immutable declaration never issues a live owner.


def _reviewed_cleanup_reference():
    path, pin = runner.REVIEWED_CLEANUP_REFS["current"]
    return dict(path=path, sha256=pin)


def test_remaining_split_source_selection_binds_actual_eight_and_held118(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Metadata reader may not prepare or launch work")

    monkeypatch.setattr(runner, "prepare_cleanup_batch", forbidden)
    monkeypatch.setattr(runner.inherited.guard, "run_bounded", forbidden)
    selection = runner._remaining_selection(_reviewed_cleanup_reference())
    split = selection["split_affected"]
    assert (split["earlier_source_cases"], split["current_source_cases"]) == (5, 3)
    assert split["single_current_source_run"] is False and split["cases"] == 8
    assert [(r["original_index"], r["execution_index"], r["bank"]) for r in split["groups"]] == [
        (8, 0, "earlier"),
        (9, 1, "earlier"),
        (10, 2, "current"),
    ]
    assert split["banks"]["earlier"]["test_sha256"] != split["banks"]["current"]["test_sha256"]
    assert split["banks"]["current"]["test_sha256"] == runner.CM_GUARD_SHA256
    assert selection["indices"] == list(range(11, 42))
    assert selection["functions"] == 31 and selection["cases"] == 118
    assert selection["cases_by_family"] == dict(CM=29, WR=89)
    assert sum(selection["case_counts"].values()) == 118
    assert len(selection["current68"]["nodeids"]) == 68
    held_nodes = [n for row in selection["selectors"].values() for n in row["expected_nodeids"]]
    assert len(held_nodes) == len(set(held_nodes)) == 118
    assert set(held_nodes).isdisjoint(selection["current68"]["nodeids"])
    assert selection["overlap_with_current68"] == []
    assert selection["held_for_Root_disposition"] is True
    assert len(selection["preserved_failures"]) == 3
    assert len(selection["preserved_failed_processes"]) == 4
    assert len(selection["producers"]) == 3
    assert runner._selected_cleanup_groups(
        dict(groups=[list(runner.CLEANUP_GROUPS[i]) for i in range(11, 42)], selection=selection)
    ) == tuple((i, runner.CLEANUP_GROUPS[i]) for i in range(11, 42))


@pytest.mark.parametrize("drift", ["old-eight-receipt", "wrong-pin", "foreign-review"])
def test_remaining_refuses_unreviewed_affected_receipts_before_read(monkeypatch, drift):
    reference = _reviewed_cleanup_reference()
    if drift == "old-eight-receipt":
        reference = dict(path="/tmp/synthetic-current-eight.json", sha256="0" * 64)
    elif drift == "wrong-pin":
        reference["sha256"] = "0" * 64
    else:
        reference["path"] += ".foreign"

    def forbidden(reference):
        raise AssertionError("Unreviewed reference reached evidence read")

    monkeypatch.setattr(runner, "_bound_cleanup_record", forbidden)
    with pytest.raises(ValueError, match="Exact Root-reviewed split-source"):
        runner._remaining_selection(reference)


@pytest.mark.parametrize(
    "drift,message",
    [
        ("current-review", "Exact reviewed68"),
        ("prior-association", "bind original source bank"),
        ("prior-resources", "plan/resources"),
        ("controller-success", "controllers must remain failed"),
        ("group-success", "failed group must remain failed"),
        ("execution-index", "actual execution indices"),
        ("foreign-bank", "current fixture successor"),
        ("wrong-current-item", "ordered unique JUnit"),
        ("duplicate-current-function", "unique current68"),
    ],
)
def test_remaining_reader_refuses_changed_review_banks_and_failed_parents(
    monkeypatch, drift, message
):
    original = runner._bound_cleanup_record
    current = original(_reviewed_cleanup_reference())
    prior_path, prior_pin = runner.REVIEWED_CLEANUP_REFS["prior"]
    prior = original(dict(path=prior_path, sha256=prior_pin))

    def changed(reference):
        record = copy.deepcopy(original(reference))
        if reference == _reviewed_cleanup_reference():
            if drift == "current-review":
                record["fresh_software"]["passed"] = 8
            elif drift == "prior-association":
                record["historical_scope"]["prior_root_review"]["sha256"] = "0" * 64
        if (
            reference["path"] == runner.PRIOR_CLEANUP_REFS["inputs"][0]
            and drift == "prior-resources"
        ):
            record["resources"]["cpu"] = 3
        if (
            reference == prior["preserved_failures"][0]["artifact"]
            and drift == "controller-success"
        ):
            record["status"] = "completed"
        if reference == prior["groups"][2]["software"] and drift == "group-success":
            record["status"] = "completed"
        if (
            reference["path"] == runner.REVIEWED_CLEANUP_REFS["prior"][0]
            and drift == "execution-index"
        ):
            record["groups"][0]["index"] = 8
        if reference == current["bound_evidence"]["batch_inputs"] and drift == "foreign-bank":
            record["packet"] = next(
                ref
                for ref in prior["bound_evidence"]
                if ref["path"].endswith("/packet/inputs.json")
            )
        if reference == current["bound_evidence"]["selection"]:
            if drift == "wrong-current-item":
                name = record["selectors"][0]["runner_target"] + "[foreign]"
                record["selectors"][0]["expected_nodeids"][0] = runner.CM_GUARD_TEST + "::" + name
                record["selectors"][0]["expected_item_names"][0] = name
            elif drift == "duplicate-current-function":
                record["selectors"][1] = copy.deepcopy(record["selectors"][0])
        if (
            reference == current["bound_evidence"]["batch_result"]
            and drift == "duplicate-current-function"
        ):
            record["groups"][1] = copy.deepcopy(record["groups"][0])
        return record

    monkeypatch.setattr(runner, "_bound_cleanup_record", changed)
    with pytest.raises(ValueError, match=message):
        runner._remaining_selection(_reviewed_cleanup_reference())


def test_remaining_counts_derive_from_exact_selectors_and_junit_not_stale_summary(monkeypatch):
    original = runner._bound_cleanup_record
    review = original(_reviewed_cleanup_reference())

    def changed(reference):
        record = original(reference)
        if reference == review["bound_evidence"]["selection"]:
            record = copy.deepcopy(record)
            record["counts"] = {"stale": 7300}
            record["cases_by_module"] = {"stale": 7300}
            record["expected_existing_case_guards"] = {"stale": 7300}
        return record

    monkeypatch.setattr(runner, "_bound_cleanup_record", changed)
    selection = runner._remaining_selection(_reviewed_cleanup_reference())
    assert selection["cases"] == 118 and selection["cases_by_family"] == dict(CM=29, WR=89)
    assert len(selection["current68"]["nodeids"]) == 68 and selection["functions"] == 31


def test_remaining_overlap_with_completed68_refuses_before_preparation(monkeypatch):
    original = runner._bound_cleanup_record
    changed_groups = list(runner.CLEANUP_GROUPS)
    changed_groups[11] = changed_groups[10]
    monkeypatch.setattr(runner, "CLEANUP_GROUPS", tuple(changed_groups))

    def changed(reference):
        record = original(reference)
        if reference["path"] == runner.PRIOR_CLEANUP_REFS["inputs"][0]:
            record["groups"] = [list(row) for row in changed_groups]
        return record

    monkeypatch.setattr(runner, "_bound_cleanup_record", changed)
    with pytest.raises(ValueError, match="overlap completed68"):
        runner._remaining_selection(_reviewed_cleanup_reference())


def test_remaining_literal_selector_preserves_parameter_order_without_evaluation(tmp_path):
    test = runner.TEST
    path = tmp_path / test
    path.parent.mkdir(parents=True)
    path.write_text(
        "@pytest.mark.parametrize('a', ['x', 'y'])\n"
        "@pytest.mark.parametrize('b', [False, True])\n"
        "def test_roster(a,b): raise AssertionError('must not run')\n"
    )
    exact = runner._literal_selector(tmp_path, test, "test_roster")
    assert exact["expected_item_names"] == [
        "test_roster[False-x]",
        "test_roster[False-y]",
        "test_roster[True-x]",
        "test_roster[True-y]",
    ]
    assert exact["expected_cases"] == 4
    source = Path(runner.__file__).resolve().parents[2]
    opaque = runner._literal_selector(
        source, runner.TEST, "test_direct_child_and_cli_refuse_before_pytest_or_output"
    )
    modules = (
        "validation.betse.betse_native_parameter_load_remainder_software",
        "validation.betse.betse_native_parameter_world_construction_software",
    )
    assert opaque["expected_item_names"] == [
        "test_direct_child_and_cli_refuse_before_pytest_or_output[" + str(flag) + "-" + module + "]"
        for flag in (False, True)
        for module in modules
    ]


def test_named_module_selector_agrees_with_actual_pinned_pytest_policy_without_importing_targets(
    tmp_path,
):
    from _pytest.python import IdMaker

    policy_path = Path(IdMaker._idval_from_value.__code__.co_filename).resolve()
    assert (
        runner.snapshot.digest(policy_path)
        == "b04488f5e46bf1ffe2e8344f81756e10b970dbfaf2f7f2f4d312becd6404df76"
    )
    modules = (
        "validation.betse.betse_native_parameter_load_remainder_software",
        "validation.betse.betse_native_parameter_world_construction_software",
    )
    target = "test_direct_child_and_cli_refuse_before_pytest_or_output"
    path = tmp_path / runner.TEST
    path.parent.mkdir(parents=True)
    path.write_text(
        "from validation.betse import betse_native_parameter_load_remainder_software as runner\n"
        "from validation.betse import betse_native_parameter_world_construction_software"
        " as world_runner\n"
        "@pytest.mark.parametrize('entry', [runner, world_runner])\n"
        "@pytest.mark.parametrize('cli', [False, True])\n"
        "def " + target + "(entry, cli): raise AssertionError('must not run')\n"
    )
    named_ids = [IdMaker._idval_from_value(None, ModuleType(name)) for name in modules]
    assert named_ids == list(modules) and named_ids != ["entry0", "entry1"]
    expected = [
        target + "[" + str(flag) + "-" + name + "]" for flag in (False, True) for name in named_ids
    ]
    selector = runner._literal_selector(tmp_path, runner.TEST, target)
    assert selector["expected_item_names"] == expected and selector["expected_cases"] == 4


@pytest.mark.parametrize(
    "drift",
    ["foreign-import", "relative-import", "unknown-alias", "shadowed", "duplicate", "reordered"],
)
def test_named_module_selector_refuses_foreign_or_ambiguous_import_authority(tmp_path, drift):
    target = "test_direct_child_and_cli_refuse_before_pytest_or_output"
    first = (
        "from validation.betse import betse_native_parameter_load_remainder_software as runner\n"
    )
    second = (
        "from validation.betse import betse_native_parameter_world_construction_software"
        " as world_runner\n"
    )
    values = "runner, world_runner"
    extra = ""
    if drift == "foreign-import":
        first = "from foreign import betse_native_parameter_load_remainder_software as runner\n"
    elif drift == "relative-import":
        first = (
            "from .validation.betse import betse_native_parameter_load_remainder_software"
            " as runner\n"
        )
    elif drift == "unknown-alias":
        values = "unknown, world_runner"
    elif drift == "shadowed":
        extra = "runner = supplied_namespace\n"
    elif drift == "duplicate":
        first += first
    elif drift == "reordered":
        values = "world_runner, runner"
    path = tmp_path / runner.TEST
    path.parent.mkdir(parents=True)
    path.write_text(
        first + second + extra + "@pytest.mark.parametrize('entry', [" + values + "])\n"
        "def " + target + "(entry): raise AssertionError('must not run')\n"
    )
    with pytest.raises(ValueError):
        runner._literal_selector(tmp_path, runner.TEST, target)


def test_remaining_legacy_none_selector_keeps_original_builtin_id_without_collection():
    source = Path(runner.__file__).resolve().parents[2]
    target = runner.CLEANUP_GROUPS[6][1]
    exact = runner._literal_selector(source, runner.CM_GUARD_TEST, target)
    assert exact["expected_cases"] == 4
    assert exact["expected_item_names"] == [
        target + "[None]",
        target + "[]",
        target + "[foreign]",
        target + "[1]",
    ]


def _copied_reader_group(tmp_path):
    # Deliberate metadata corruption stays outside pytest's real guard-receipt tree.
    # These copies test a reader, and are never execution receipts or owner authority.
    directory = tmp_path.parent.parent / ("reader-evidence-copy-" + tmp_path.name)
    directory.mkdir()
    review = runner._bound_cleanup_record(_reviewed_cleanup_reference())
    batch = runner._bound_cleanup_record(review["bound_evidence"]["batch_result"])
    actual = batch["groups"][0]
    row = {}
    for key, filename in (
        ("software", "result.json"),
        ("runtime", "runtime.json"),
        ("junit", "junit.xml"),
    ):
        path = directory / filename
        path.write_bytes(Path(actual[key]["path"]).read_bytes())
        row[key] = runner.inherited.ref(path)
    for index, path in enumerate(
        sorted((Path(actual["junit"]["path"]).parent / "pytest").rglob("native-blocked.json"))
    ):
        case = directory / "pytest" / str(index)
        case.mkdir(parents=True)
        for name in ("native-blocked.json", "matplotlib-blocked.json"):
            (case / name).write_bytes(path.with_name(name).read_bytes())
    fixture_source = Path(review["source_and_runtime_integrity"]["worker_snapshot"]["path"]).parent
    selector = runner._literal_selector(fixture_source, runner.CM_GUARD_TEST, actual["target"])
    return row, selector, fixture_source, directory


@pytest.mark.parametrize(
    "drift",
    [
        "valid",
        "missing",
        "corrupt",
        "attempt",
        "hook",
        "primary",
        "after-callback",
        "foreign-fixture",
        "extra-diagnostic",
    ],
)
def test_remaining_group_requires_actual_paired_reference_evidence_not_receipt_counts(
    tmp_path, drift
):
    row, selector, fixture_source, directory = _copied_reader_group(tmp_path)
    valid = runner._group_evidence(row, selector, fixture_source=fixture_source)
    assert len(valid["nodeids"]) == 3 and len(valid["matplotlib_references"]) == 3
    assert valid["additional_matplotlib_diagnostics"] == []
    assert all(
        r["fixture_sha256"] == runner.CM_GUARD_SHA256
        and r["persisted_record_is_final_certificate"] is False
        for r in valid["matplotlib_references"]
    )
    if drift == "valid":
        return
    reference = directory / "pytest/0/matplotlib-blocked.json"
    if drift == "extra-diagnostic":
        nested = directory / "pytest/0/nested-control/matplotlib-blocked.json"
        nested.parent.mkdir()
        nested.write_text(json.dumps(dict(attempts=["declared nested blocked probe"])))
        result = runner._group_evidence(row, selector, fixture_source=fixture_source)
        assert len(result["nodeids"]) == 3 and len(result["matplotlib_references"]) == 3
        assert result["additional_matplotlib_diagnostics"] == [runner.inherited.ref(nested)]
        return
    if drift == "missing":
        reference.unlink()
    elif drift == "corrupt":
        reference.write_text("{truncated")
    elif drift == "foreign-fixture":
        fixture_source = directory / "foreign-source"
        fixture = fixture_source / runner.CM_GUARD_TEST
        fixture.parent.mkdir(parents=True)
        fixture.write_text("# foreign unexecuted fixture declaration\n")
    else:
        record = json.loads(reference.read_text())
        if drift == "attempt":
            record["attempts"] = ["blocked import"]
        elif drift == "hook":
            record["final_profile_identity"] += 1
        elif drift == "primary":
            record["primary_identity"] = 1
        elif drift == "after-callback":
            record["clean_guard"] = True
        reference.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        runner._group_evidence(row, selector, fixture_source=fixture_source)


@pytest.mark.parametrize(
    "declaration",
    [
        "@pytest.mark.parametrize('a', ['same', 'same'])",
        "@pytest.mark.parametrize('a', arbitrary())",
        "@pytest.mark.parametrize('a', [object()])",
        "@pytest.mark.parametrize('a', ['x'], ids=['hidden'])",
        "@foreign",
        "@pytest.mark.parametrize('a,b', [('x','y')])",
        "@pytest.mark.parametrize('a', [])",
    ],
)
def test_remaining_literal_selector_refuses_ambiguous_or_executable_rosters(tmp_path, declaration):
    path = tmp_path / "tests/unit/probe.py"
    path.parent.mkdir(parents=True)
    path.write_text(declaration + "\ndef test_probe(a): raise AssertionError('must not run')\n")
    with pytest.raises(ValueError):
        runner._literal_selector(tmp_path, "tests/unit/probe.py", "test_probe")


@pytest.mark.parametrize(
    "drift",
    [
        "valid",
        "duplicate-item",
        "wrong-parameter",
        "wrong-module",
        "reordered-items",
        "duplicate-guard",
        "foreign-guard",
        "missing-guard",
        "missing-cleanup",
        "attempt",
        "boolean-count",
        "failed-item",
        "duplicate-expected",
    ],
)
def test_remaining_exact_item_guard_association_refuses_equal_count_substitutions(drift):
    review = runner._bound_cleanup_record(_reviewed_cleanup_reference())
    batch = runner._bound_cleanup_record(review["bound_evidence"]["batch_result"])
    row = batch["groups"][0]
    source = Path(review["source_and_runtime_integrity"]["worker_snapshot"]["path"]).parent
    selector = runner._literal_selector(source, runner.CM_GUARD_TEST, row["target"])
    cases = list(ET.parse(row["junit"]["path"]).iter("testcase"))
    guards = [
        json.loads(p.read_text())
        for p in sorted((Path(row["junit"]["path"]).parent / "pytest").rglob("native-blocked.json"))
    ]
    assert runner._case_roster(selector, cases, guards) == selector["expected_nodeids"]
    if drift == "valid":
        return
    if drift == "duplicate-item":
        cases[1].set("name", cases[0].get("name"))
    elif drift == "wrong-parameter":
        cases[0].set("name", row["target"] + "[unlisted]")
    elif drift == "wrong-module":
        cases[0].set("classname", "tests.unit.foreign")
    elif drift == "reordered-items":
        cases.reverse()
    elif drift == "duplicate-guard":
        guards[1] = copy.deepcopy(guards[0])
    elif drift == "foreign-guard":
        guards[0]["nodeid"] = runner.CM_GUARD_TEST + "::foreign"
    elif drift == "missing-guard":
        guards.pop()
    elif drift == "missing-cleanup":
        guards[0]["inherited_generator_closed"] = False
    elif drift == "attempt":
        guards[0]["flattened_attempted"] = ["forbidden"]
    elif drift == "boolean-count":
        guards[0]["final_blocked_attempt_count"] = False
    elif drift == "failed-item":
        ET.SubElement(cases[0], "failure")
    elif drift == "duplicate-expected":
        selector["expected_nodeids"][1] = selector["expected_nodeids"][0]
    with pytest.raises(ValueError):
        runner._case_roster(selector, cases, guards)


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


def test_remaining_reviewed_context_group_has_native_guard_without_invented_matplotlib_receipt(
    monkeypatch,
):
    review = runner._bound_cleanup_record(_reviewed_cleanup_reference())
    batch = runner._bound_cleanup_record(review["bound_evidence"]["batch_result"])
    selected = runner._bound_cleanup_record(review["bound_evidence"]["selection"])
    index = next(
        i
        for i, row in enumerate(selected["selectors"])
        if row["function_nodeid"].startswith(runner.CM_CONTEXT_TEST + "::")
    )
    selector = selected["selectors"][index]
    fixture_source = Path(review["source_and_runtime_integrity"]["worker_snapshot"]["path"]).parent
    evidence = runner._group_evidence(
        batch["groups"][index], selector, fixture_source=fixture_source
    )
    assert evidence["reference_fixture_installed"] is False
    assert len(evidence["native_guards"]) == selector["expected_cases"]
    assert evidence["matplotlib_references"] == []
    assert evidence["fixture_source"]["sha256"] == runner.CM_CONTEXT_SHA256
    original = runner.snapshot.digest

    def changed(path):
        return "0" * 64 if Path(path) == fixture_source / runner.CM_CONTEXT_TEST else original(path)

    monkeypatch.setattr(runner.snapshot, "digest", changed)
    with pytest.raises(ValueError, match="Exact reviewed bank fixture"):
        runner._group_evidence(batch["groups"][index], selector, fixture_source=fixture_source)


def _compiled_shape():
    module = ModuleType("conditional-original-parameter-namespace")
    vars(module)["__builtins__"] = vars(builtins)
    module.np = object()  # Lookup metadata only; original helper execution stays blocked.

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


@pytest.mark.parametrize("which", ["profile", "trace"])
@pytest.mark.parametrize("source_error", [False, True])
def test_final_recovery_helper_entry_refusal_preserves_primary_and_retires_guard(
    observed, monkeypatch, which, source_error
):
    h = observed
    h.control["fail"] = source_error
    prior, trace = sys.getprofile(), sys.gettrace()
    original_guards = tuple(stage._HOOK_GUARDS)
    secondary = SyntheticCaptureFailure("inherited hook rejected final recovery entry")
    refused = []
    bookkeeping = []
    monkeypatch.setattr(stage, "_observer_bookkeeping", lambda *args: bookkeeping.append(args))

    def inherited_hook(frame, event, arg):
        if (
            event == "call"
            and frame.f_code is stage._recover_hooks.__code__
            and frame.f_locals["expected_profile"] is expected_profile
            and frame.f_locals["expected_trace"] is expected_trace
        ):
            # The actual profiled/traced call is rejected before the helper body.
            refused.append((frame, dict(frame.f_locals)))
            raise secondary
        previous = prior if which == "profile" else trace
        if previous is not None:
            previous(frame, event, arg)
        return inherited_hook if which == "trace" else None

    expected_profile = inherited_hook if which == "profile" else prior
    expected_trace = inherited_hook if which == "trace" else trace
    (sys.setprofile if which == "profile" else sys.settrace)(inherited_hook)
    try:
        expected = _FalseySourceFailure if source_error else stage._ObservationStop
        with pytest.raises(expected) as caught:
            with stage._observe(h.context):
                stage._invoke(h.context)
        final_profile, final_trace = sys.getprofile(), sys.gettrace()
    finally:
        sys.setprofile(prior)
        sys.settrace(trace)
    assert len(refused) == 1 and "errors" not in refused[0][1]
    if source_error:
        assert caught.value is h.primary and h.primary.__cause__ is h.cause
        assert h.context.raw_returns and h.context.observer_state.primary is h.primary
    else:
        assert h.context.p.after_ion and h.context.p.tail_finalized
    assert final_profile is expected_profile and final_trace is expected_trace
    assert len(stage._HOOK_GUARDS) == len(original_guards)
    assert all(a is b for a, b in zip(stage._HOOK_GUARDS, original_guards, strict=True))
    recovery = h.context.observer_recovery
    assert recovery["helper"] is None and recovery["identities_match"] and not recovery["clean"]
    assert recovery["metadata_stopped"] and not recovery["bookkeeping_called"] and bookkeeping == []
    assert any(
        name == "final_hook_recovery" and error is secondary for name, error in recovery["errors"]
    )
    assert h.context.invalid and any(error is secondary for _, error in h.context.capture_errors)
    assert {name for _, name, _ in recovery["samples"]} == {"profile", "trace"}


@pytest.mark.parametrize("source_error", [False, True])
def test_observer_final_samples_follow_mutating_bookkeeping(observed, monkeypatch, source_error):
    h = observed
    h.control["fail"] = source_error
    prior, trace = sys.getprofile(), sys.gettrace()
    calls = []

    def inherited_hook(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)

    def bookkeeping(*args):
        calls.append(args)
        sys.setprofile(None)
        sys.settrace(None)

    monkeypatch.setattr(stage, "_observer_bookkeeping", bookkeeping)
    sys.setprofile(inherited_hook)
    try:
        expected = _FalseySourceFailure if source_error else stage._ObservationStop
        with pytest.raises(expected) as caught:
            with stage._observe(h.context):
                stage._invoke(h.context)
        final_profile, final_trace = sys.getprofile(), sys.gettrace()
    finally:
        sys.setprofile(prior)
        sys.settrace(trace)
    assert len(calls) == 1
    assert final_profile is inherited_hook and final_trace is trace
    assert h.context.observer_recovery["identities_match"]
    assert not h.context.observer_recovery["clean"] and h.context.invalid
    assert any(name == "final_hook_identity_0" for name, _ in h.context.capture_errors)
    if source_error:
        assert caught.value is h.primary and h.primary.__cause__ is h.cause


@pytest.fixture
def worker_probes(monkeypatch, tmp_path):
    """Real worker evidence control flow with source/pytest/native bodies blocked."""
    output = tmp_path / "conditional-worker-final-hooks"
    output.mkdir()
    primary, cause = _FalseySourceFailure("toy pytest primary"), SyntheticSourceCause("cause")
    primary.__cause__ = cause
    prior, trace = sys.getprofile(), sys.gettrace()
    h = SimpleNamespace(
        output=output, primary=primary, cause=cause, fail=False, calls=[], probes=[]
    )
    binding = object()
    monkeypatch.setattr(
        runner, "_authorization", lambda *a, **kw: dict(source=tmp_path, manifest={})
    )

    def probe(name):
        assert sys.getprofile() is prior and sys.gettrace() is trace
        h.probes.append(name)
        return ({"conditional": {}}, (binding,)) if name == "producers" else dict(conditional=name)

    monkeypatch.setattr(runner, "_producers", lambda *a, **kw: probe("producers"))
    monkeypatch.setattr(runner, "_identity", lambda: probe("identity"))
    monkeypatch.setattr(runner, "_inventory", lambda: probe("inventory"))

    def driver(directory):
        h.calls.append("blocked-pytest-body")
        if h.fail:
            raise h.primary
        return 0

    monkeypatch.setattr(runner, "_pytest_driver", lambda target: driver)
    h.run = lambda: runner._child(
        output, "conditional", "hash", file=runner.FILE, entry_path=runner.__file__
    )
    return h


def test_worker_final_cleanup_accepts_unchanged_conditional_evidence(worker_probes):
    h = worker_probes
    prior, trace = sys.getprofile(), sys.gettrace()
    assert h.run() == 0
    assert h.calls == ["blocked-pytest-body"]
    assert sys.getprofile() is prior and sys.gettrace() is trace
    saved = json.loads((h.output / "worker-evidence.json").read_text())
    assert saved["pytest_returned_zero"] and saved["final_worker_success_requires_terminal"]
    assert saved["final_hook_sample_after_all_writers_pending"]
    assert saved["available"]["hooks"]["sample_scope"] == "before_later_worker_writers_not_final"


@pytest.mark.parametrize(
    "filename",
    [
        "identity.json",
        "inventory.json",
        "producers.json",
        "hooks.json",
        "runtime.json",
        "worker-evidence.json",
    ],
)
@pytest.mark.parametrize("source_error", [False, True])
def test_worker_samples_after_every_writer_and_refuses_recovered_hook_drift(
    worker_probes, monkeypatch, filename, source_error
):
    h = worker_probes
    h.fail = source_error
    prior, trace = sys.getprofile(), sys.gettrace()
    original_write, payloads, writes = runner.snapshot.write_json, {}, []

    def foreign_profile(frame, event, arg):
        return None

    def foreign_trace(frame, event, arg):
        return foreign_trace

    def write(path, value):
        assert sys.getprofile() is prior and sys.gettrace() is trace
        writes.append(path.name)
        payloads[path.name] = json.loads(json.dumps(value))
        result = original_write(path, value)
        if path.name == filename:
            sys.setprofile(foreign_profile)
            sys.settrace(foreign_trace)
        return result

    monkeypatch.setattr(runner.snapshot, "write_json", write)
    try:
        expected = _FalseySourceFailure if source_error else runner.WorkerEvidenceRejected
        with pytest.raises(expected) as caught:
            h.run()
        final_profile, final_trace = sys.getprofile(), sys.gettrace()
    finally:
        sys.setprofile(prior)
        sys.settrace(trace)
    context = caught.value.world_ready_worker
    assert h.calls == ["blocked-pytest-body"] and writes.count(filename) == 1
    assert writes[-1] == filename and context.metadata_stopped
    assert final_profile is prior and final_trace is trace
    assert context.hook_recovery["identities_match"] and not context.hook_recovery["clean"]
    assert any(name == "final_hook_identity_0" for name, _ in context.errors)
    final = context.values["final_hook_identities"]
    assert final["restored"] and not final["clean"]
    assert final["sample_scope"] == "after_all_worker_writers_and_primary_attachment"
    if "hooks.json" in payloads:
        assert payloads["hooks.json"]["sample_scope"] == "before_later_worker_writers_not_final"
    if "worker-evidence.json" in payloads:
        assert payloads["worker-evidence.json"]["final_hook_sample_after_all_writers_pending"]
        assert payloads["worker-evidence.json"]["final_worker_success_requires_terminal"]
    if source_error:
        assert caught.value is h.primary and h.primary.__cause__ is h.cause


@pytest.mark.parametrize("failure", ["profile", "trace", "clear-other", "persistent-profile"])
@pytest.mark.parametrize("source_error", [False, True])
def test_worker_final_hook_cleanup_is_bounded_independent_and_keeps_primary(
    worker_probes, monkeypatch, failure, source_error
):
    h = worker_probes
    h.fail = source_error
    prior, trace = sys.getprofile(), sys.gettrace()
    set_profile, set_trace, write = sys.setprofile, sys.settrace, runner.snapshot.write_json
    attempts = dict(profile=0, trace=0)
    secondary = SyntheticCaptureFailure("conditional final setter refusal")

    def foreign_profile(frame, event, arg):
        return None

    def foreign_trace(frame, event, arg):
        return foreign_trace

    def profile(value):
        if value is prior:
            attempts["profile"] += 1
            if failure == "persistent-profile" or (
                failure == "profile" and attempts["profile"] == 1
            ):
                raise secondary
        set_profile(value)

    def traced(value):
        if value is trace:
            attempts["trace"] += 1
            if failure == "trace" and attempts["trace"] == 1:
                raise secondary
        set_trace(value)
        if failure == "clear-other" and attempts["trace"] == 1:
            set_profile(None)

    def writer(path, value):
        result = write(path, value)
        if path.name == "worker-evidence.json":
            set_profile(foreign_profile)
            set_trace(foreign_trace)
        return result

    monkeypatch.setattr(sys, "setprofile", profile)
    monkeypatch.setattr(sys, "settrace", traced)
    monkeypatch.setattr(runner.snapshot, "write_json", writer)
    try:
        expected = _FalseySourceFailure if source_error else runner.WorkerEvidenceRejected
        with pytest.raises(expected) as caught:
            h.run()
        final_profile, final_trace = sys.getprofile(), sys.gettrace()
    finally:
        set_profile(prior)
        set_trace(trace)
    context = caught.value.world_ready_worker
    assert 1 <= attempts["profile"] <= 3 and 1 <= attempts["trace"] <= 3
    assert final_trace is trace
    assert (final_profile is prior) is (failure != "persistent-profile")
    assert context.hook_recovery["identities_match"] is (failure != "persistent-profile")
    assert not context.hook_recovery["clean"] and context.errors
    if failure != "clear-other":
        assert any(error is secondary for _, error in context.hook_recovery["errors"])
    assert {name for _, name, _ in context.hook_recovery["samples"]} == {"profile", "trace"}
    if source_error:
        assert caught.value is h.primary and h.primary.__cause__ is h.cause


@pytest.mark.parametrize("which", ["profile", "trace"])
@pytest.mark.parametrize("source_error", [False, True])
def test_failed_observer_restore_stops_bookkeeping_even_after_recovery(
    observed, monkeypatch, which, source_error
):
    h = observed
    h.control["fail"] = source_error
    prior, trace = sys.getprofile(), sys.gettrace()
    real_profile, real_trace = sys.setprofile, sys.settrace
    calls, refused = [], []
    secondary = SyntheticCaptureFailure("first restore failed")

    def setter(value):
        expected = prior if which == "profile" else trace
        if value is expected and not refused:
            refused.append(value)
            (real_profile if which == "profile" else real_trace)(None)
            raise secondary
        return (real_profile if which == "profile" else real_trace)(value)

    monkeypatch.setattr(sys, "set" + which, setter)

    def bookkeeping(*args):
        calls.append(args)
        assert sys.getprofile() is prior and sys.gettrace() is trace

    monkeypatch.setattr(stage, "_observer_bookkeeping", bookkeeping)
    try:
        with pytest.raises(
            _FalseySourceFailure if source_error else stage._ObservationStop
        ) as caught:
            with stage._observe(h.context):
                stage._invoke(h.context)
        final_profile, final_trace = sys.getprofile(), sys.gettrace()
    finally:
        real_profile(prior)
        real_trace(trace)
    recovery = h.context.observer_recovery
    assert refused and calls == [] and recovery["metadata_stopped"]
    assert not recovery["bookkeeping_called"] and recovery["identities_match"]
    assert any(error is secondary for _, error in recovery["errors"])
    assert final_profile is prior and final_trace is trace
    if source_error:
        assert caught.value is h.primary and h.primary.__cause__ is h.cause


def _worker_context(error):
    trace = error.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code is runner._child.__code__:
            return trace.tb_frame.f_locals["context"]
        trace = trace.tb_next
    raise AssertionError("Actual worker traceback/context missing")


@pytest.mark.parametrize("source_error", [False, True])
def test_worker_hook_loss_stops_all_later_metadata_even_after_final_recovery(
    worker_probes, monkeypatch, source_error
):
    h = worker_probes
    prior, trace = sys.getprofile(), sys.gettrace()

    def foreign(frame, event, arg):
        return foreign

    def driver(output):
        h.calls.append("blocked-pytest-body")
        sys.setprofile(foreign)
        sys.settrace(foreign)
        if source_error:
            raise h.primary
        return 0

    monkeypatch.setattr(runner, "_pytest_driver", lambda target: driver)
    try:
        with pytest.raises(
            _FalseySourceFailure if source_error else runner.WorkerEvidenceRejected
        ) as caught:
            h.run()
        final_profile, final_trace = sys.getprofile(), sys.gettrace()
    finally:
        sys.setprofile(prior)
        sys.settrace(trace)
    context = _worker_context(caught.value)
    assert h.probes == ["producers"] and h.calls == ["blocked-pytest-body"]
    assert context.callback_calls == ["initial_producers", "pytest_driver", "pytest"]
    assert context.metadata_stopped and context.values.keys() == {"final_hook_identities"}
    assert list(h.output.iterdir()) == []
    assert context.hook_recovery["identities_match"] and not context.hook_recovery["clean"]
    assert final_profile is prior and final_trace is trace
    if source_error:
        assert caught.value is h.primary and h.primary.__cause__ is h.cause


def test_worker_formatter_hook_loss_stops_later_formatters_attachment_and_writers(worker_probes):
    h = worker_probes
    h.fail = True
    prior, trace = sys.getprofile(), sys.gettrace()
    calls = []

    def foreign(frame, event, arg):
        return foreign

    class Primary(_FalseySourceFailure):
        def __str__(self):
            assert sys.getprofile() is prior and sys.gettrace() is trace
            calls.append("str")
            sys.setprofile(foreign)
            sys.settrace(foreign)
            return "original primary"

    h.primary = Primary("primary")
    h.primary.__cause__ = h.cause
    try:
        with pytest.raises(Primary) as caught:
            h.run()
        final_profile, final_trace = sys.getprofile(), sys.gettrace()
    finally:
        sys.setprofile(prior)
        sys.settrace(trace)
    context = _worker_context(caught.value)
    assert caught.value is h.primary and h.primary.__cause__ is h.cause and calls == ["str"]
    assert context.callback_calls[-1] == "format_primary" and context.metadata_stopped
    assert (
        not (h.output / "runtime.json").exists()
        and not (h.output / "worker-evidence.json").exists()
    )
    assert final_profile is prior and final_trace is trace


@pytest.mark.parametrize("target", ["unknown", "-k", "test_missing", "test_x[1]"])
def test_exact_function_selection_refuses_foreign_targets_before_packet(
    monkeypatch, tmp_path, target
):
    monkeypatch.setenv(runner.SOFTWARE_RELEASE, "1")
    with pytest.raises(ValueError, match="owned software test function"):
        runner.software(tmp_path / "missing", tmp_path / "output", target=target)
    assert not (tmp_path / "output").exists()


def test_cleanup_batch_launch_stays_held_before_snapshot(monkeypatch, tmp_path):
    monkeypatch.delenv(runner.SOFTWARE_RELEASE, raising=False)
    with pytest.raises(ValueError, match="launch remains held"):
        runner.launch_cleanup_batch(tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_first_group_creates_launcher_before_guard_without_starting_worker(monkeypatch, tmp_path):
    batch = tmp_path / "conditional-batch"
    packet = batch / "CM-packet"
    packet.mkdir(parents=True)
    target = "test_matplotlib_guard_unchanged_valid_cleanup_requires_evidence_return"
    groups = (("CM", target),)
    monkeypatch.setattr(runner, "CLEANUP_GROUPS", groups)
    runner.snapshot.write_json(packet / "inputs.json", dict(conditional_metadata_only=True))
    inputs = dict(
        groups=groups,
        resources=runner.RESOURCES,
        controller_manifest=dict(sha256="conditional-source"),
        packets=dict(CM=runner.inherited.ref(packet / "inputs.json")),
    )
    runner.snapshot.write_json(batch / "batch-inputs.json", inputs)
    source = Path(runner.__file__).resolve().parents[2]
    verify_calls, calls = [], []

    def verify(actual, *, manifest_sha256):
        verify_calls.append(actual)
        assert actual == source and manifest_sha256 == "conditional-source"

    monkeypatch.setattr(runner.snapshot, "verify", verify)
    secondary = SyntheticCaptureFailure("conditional guard entry stop; no process")

    def guarded(command, **kwargs):
        calls.append((command, kwargs))
        launcher = batch / "00-CM/launcher"
        assert kwargs["directory"] == launcher and launcher.is_dir()
        assert command[-2:] == ["--target", target] and "-k" not in command
        assert command[command.index("--output") + 1] == str(batch / "00-CM/software")
        assert kwargs["cwd"] == packet / "source" and kwargs["timeout"] == 480
        assert kwargs["max_rss_bytes"] == 2**30 and kwargs["min_available_bytes"] == 8 * 2**30
        runner.snapshot.write_json(
            launcher / "process-inputs.json", dict(conditional_metadata_only=True)
        )
        raise secondary

    monkeypatch.setattr(runner.inherited.guard, "run_bounded", guarded)
    assert (
        runner.cleanup_batch_child(batch, runner.snapshot.digest(batch / "batch-inputs.json")) == 1
    )
    failure = json.loads((batch / "BATCH-FAILURE.json").read_text())
    assert len(calls) == 1 and verify_calls == [source]
    assert failure["error_type"] == "SyntheticCaptureFailure" and failure["outcomes"] == []
    assert failure["active"] == dict(index=0, family="CM", target=target)
    assert not (batch / "00-CM/software").exists() and not (batch / "BATCH-RESULT.json").exists()


def test_worker_formatter_bypasses_custom_cause_and_type_access_before_hook_loss(
    worker_probes, monkeypatch
):
    h = worker_probes
    h.fail = True
    prior, trace = sys.getprofile(), sys.gettrace()
    cause_accesses, type_accesses, strings = [], [], []
    formatting = []

    def foreign(frame, event, arg):
        return foreign

    class Meta(type):
        def __getattribute__(cls, name):
            if name == "__qualname__" and formatting:
                type_accesses.append(name)
                assert sys.getprofile() is prior and sys.gettrace() is trace
            return super().__getattribute__(name)

    class Primary(_FalseySourceFailure, metaclass=Meta):
        def __getattribute__(self, name):
            if name == "__cause__" and formatting:
                cause_accesses.append(name)
                assert sys.getprofile() is prior and sys.gettrace() is trace
                raise AssertionError("Custom cause dispatch is forbidden")
            return super().__getattribute__(name)

        def __str__(self):
            assert sys.getprofile() is prior and sys.gettrace() is trace
            strings.append(True)
            sys.setprofile(foreign)
            sys.settrace(foreign)
            return "original primary"

    primary = Primary("primary")
    BaseException.__cause__.__set__(primary, h.cause)
    h.primary = primary
    actual_formatter = runner._exception

    def measured_formatter(error):
        formatting.append(True)
        try:
            return actual_formatter(error)
        finally:
            formatting.pop()

    monkeypatch.setattr(runner, "_exception", measured_formatter)
    try:
        with pytest.raises(Primary) as caught:
            h.run()
        final_profile, final_trace = sys.getprofile(), sys.gettrace()
    finally:
        sys.setprofile(prior)
        sys.settrace(trace)
    context = _worker_context(caught.value)
    assert (
        caught.value is primary
        and BaseException.__cause__.__get__(primary, BaseException) is h.cause
    )
    assert cause_accesses == [] and type_accesses == [] and strings == [True]
    retained = context.raw_results["format_primary"]
    assert retained["identity"] == id(primary) and retained["cause_identity"] == id(h.cause)
    assert retained["type"] == type.__getattribute__(Primary, "__qualname__")
    assert context.callback_calls[-1] == "format_primary" and context.metadata_stopped
    assert final_profile is prior and final_trace is trace
    assert (
        not (h.output / "runtime.json").exists()
        and not (h.output / "worker-evidence.json").exists()
    )
