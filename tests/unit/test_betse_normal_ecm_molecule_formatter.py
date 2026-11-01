"""Native/warm/RNG-blocked formatter source and private binding controls.

Only the new Cells text helper runs, on small explicitly synthetic inputs.
Its calls are reported as helper work, never reference or biological cases.
"""

import ast
import builtins
import copy
import json
import sys
from dataclasses import replace
from types import FunctionType, MappingProxyType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_formatter as formatter
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_kinetic_reload_checkpoint import (
    no_warm_source_calls as no_warm_source_calls,
)
from tests.unit.test_betse_normal_ecm_molecule_kinetic_reload_reference import (
    no_original_execution as no_original_execution,
)
from validation.betse import betse_normal_ecm_molecule_formatter as validation
from validation.betse import betse_normal_ecm_molecule_kinetic_reload_reference as reference
from validation.betse.betse_normal_current_native import write_archive


@pytest.fixture(autouse=True)
def formatter_work(tmp_path):
    previous, entries, attempts = sys.getprofile(), [], []

    def guard(frame, event, arg):
        if event == "call" and frame.f_code in formatter._CODES:
            attempts.append(frame.f_code.co_name)
            raise AssertionError("Actual inherited/private warm consumer forbidden")
        if event == "call" and frame.f_code is formatter._FORMATTER_CODE:
            entries.append(dict(helper="Cells literal tex_val", status="entered"))
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(guard)
    yield entries
    sys.setprofile(previous)
    (tmp_path / "formatter-control.json").write_text(
        json.dumps(
            dict(
                actual_consumer_entry_attempts=attempts,
                Cells_text_helper_calls=entries,
                actual_original_formatter_or_warm_calls=0,
                synthetic_only=True,
                scientific_acceptance=False,
                independent_biological_cases=0,
                helper_work_is_not_reference_execution=True,
            )
        )
    )
    assert attempts == []


def retain(path, value):
    write_archive(
        path,
        dict(
            value,
            synthetic_only=True,
            scientific_acceptance=False,
            original_warm_INIT_RNG_execution=0,
            independent_biological_cases=0,
        ),
    )


def dummy(*args, **kwargs):
    raise AssertionError("Synthetic replacement must not execute")


def test_entire_original_formatter_AST_and_closure_are_bound_without_evaluation(
    tmp_path, formatter_work
):
    plan = validation.source_plan()
    assert plan["entire_executable_function_AST_equal"] is True
    assert plan["original_function_compiled_or_called"] is False
    assert plan["private_preparation"]["prepared_function_objects"] == 5
    assert plan["live_bindings_installed"]
    assert len(plan["source_declarations"]) == 3
    assert plan["actual_method_association"]["INIT_or_native_owner_admission"] is False
    assert formatter_work == []
    retain(tmp_path / "source-plan", plan)


def test_private_methods_preserve_complete_code_defaults_globals_without_installing(tmp_path):
    originals = formatter.originals()
    before = [dict(f.__globals__) for f in originals]
    candidate = formatter.prepare()
    assert formatter.check_prepared(candidate) is candidate
    for (module, cls, name), original, copied, namespace in zip(
        formatter.SPECS, originals, candidate.methods.values(), before, strict=True
    ):
        assert vars(cls)[name] is original and original.__globals__ is vars(module)
        assert original.__globals__ == namespace
        assert copied.__code__ is original.__code__
        assert copied.__defaults__ is original.__defaults__
        assert copied.__globals__ is not original.__globals__
        assert set(copied.__globals__) == set(namespace)
        assert all(
            v is (formatter.source.tex_val if k == "tex_val" else namespace[k])
            for k, v in copied.__globals__.items()
        )
        assert original.__globals__["tex_val"] is formatter.source.tex_val
    retain(tmp_path / "private-methods", formatter.describe(candidate))


@pytest.mark.parametrize(
    "value,expected",
    [
        (0.0, "0.00"),
        (-0.0, "-0.00"),
        (1.2345, "1.23"),
        (-1.2345, "-1.23"),
        (999.0, "999.00"),
        (1000.0, "1.00e+03"),
        (-1000.0, "-1.00e+03"),
        (0.011, "0.01"),
        (0.01, "1.00e-02"),
        (0.001, "1.00e-03"),
        (1, "1.0"),
        (1000, "1000.0"),
        (True, "1.0"),
        (np.float64(1000), "1000.0"),
        (np.float32(1.25), "1.25"),
        (np.array([1.0, 3.0]), "2.0"),
        (np.array(1.25), "1.25"),
        (np.float64("nan"), "nan"),
        (np.float64("inf"), "inf"),
    ],
)
def test_synthetic_text_keeps_native_type_threshold_mean_and_sign_semantics(
    value, expected, tmp_path, formatter_work
):
    helper = formatter.check_helper()
    result = helper(value)
    assert type(result) is str and result == expected
    assert len(formatter_work) == 1
    retain(
        tmp_path / "text",
        dict(
            input=value,
            input_type=type(value).__name__,
            expected_text=expected,
            complete_text=result,
            Cells_helper_calls=1,
            original_reference_calls=0,
        ),
    )


@pytest.mark.parametrize(
    "value,exception", [(float("nan"), ValueError), (float("inf"), OverflowError)]
)
def test_original_python_float_failure_is_not_changed_to_a_success_receipt(
    value, exception, tmp_path, formatter_work
):
    with pytest.raises(exception) as caught:
        formatter.source.tex_val(value)
    assert len(formatter_work) == 1
    retain(
        tmp_path / "raw-failure",
        dict(
            input=value,
            primary_type=type(caught.value).__name__,
            primary_message=str(caught.value),
            primary_cause=None if caught.value.__cause__ is None else repr(caught.value.__cause__),
            primary_context=None
            if caught.value.__context__ is None
            else repr(caught.value.__context__),
            successful_text=False,
            Cells_helper_calls=1,
        ),
    )


@pytest.mark.parametrize(
    "fault",
    ["formatter", "code", "math", "numpy", "log10", "mean", "builtin", "source-file"],
)
def test_runtime_helper_identity_dependencies_and_source_drift_refuse(monkeypatch, fault, tmp_path):
    if fault == "formatter":
        monkeypatch.setattr(formatter.source, "tex_val", str)
    elif fault == "code":
        monkeypatch.setattr(formatter.source.tex_val, "__code__", dummy.__code__)
    elif fault == "math":
        monkeypatch.setattr(formatter.source, "math", SimpleNamespace(log10=formatter._LOG10))
    elif fault == "numpy":
        monkeypatch.setattr(formatter.source, "np", SimpleNamespace(mean=formatter._MEAN))
    elif fault == "log10":
        monkeypatch.setattr(formatter.math, "log10", dummy)
    elif fault == "mean":
        monkeypatch.setattr(formatter.np, "mean", dummy)
    elif fault == "builtin":
        monkeypatch.setattr(formatter.source, "type", dummy, raising=False)
    else:
        path = tmp_path / "foreign-same-bytes.py"
        path.write_bytes(formatter._FORMATTER_FILE.read_bytes())
        monkeypatch.setattr(formatter.source, "__file__", str(path))
    with pytest.raises(ValueError, match="Changed formatter"):
        formatter.check_helper()


@pytest.mark.parametrize(
    "fault", ["formatter", "globals", "defaults", "code", "method-set", "record", "annotation"]
)
def test_private_consumer_drift_or_supplied_record_never_activates(monkeypatch, fault):
    value = formatter.prepare()
    first = next(iter(value.methods.values()))
    if fault == "formatter":
        monkeypatch.setitem(first.__globals__, "tex_val", str)
    elif fault == "globals":
        monkeypatch.setitem(first.__globals__, "np", SimpleNamespace())
    elif fault == "defaults":
        monkeypatch.setattr(first, "__defaults__", ("unexpected",))
    elif fault == "code":
        monkeypatch.setattr(first, "__code__", dummy.__code__)
    elif fault == "method-set":
        value = replace(value, methods=MappingProxyType({}))
    elif fault == "record":
        value = {"methods": value.methods}
    else:
        monkeypatch.setattr(first, "__annotations__", {"return": str})
    with pytest.raises(ValueError, match="formatter|Formatter"):
        formatter.check_prepared(value)


@pytest.mark.parametrize(
    "fault", ["function", "code", "defaults", "annotations", "attributes", "legacy-formatter"]
)
def test_existing_method_authority_drift_refuses_before_any_copy(monkeypatch, fault):
    _, cls, name = formatter.SPECS[0]
    function = vars(cls)[name]
    if fault == "function":
        monkeypatch.setattr(cls, name, FunctionType(function.__code__, function.__globals__))
    elif fault == "code":
        monkeypatch.setattr(function, "__code__", dummy.__code__)
    elif fault == "defaults":
        monkeypatch.setattr(function, "__defaults__", ("unexpected",))
    elif fault == "annotations":
        monkeypatch.setitem(function.__annotations__, "return", str)
    elif fault == "legacy-formatter":
        monkeypatch.setitem(function.__globals__, "tex_val", str)
    else:
        monkeypatch.setattr(function, "unowned_callback", dummy, raising=False)
    with pytest.raises(ValueError, match="Foreign formatter consumer"):
        formatter.prepare()


def test_original_source_digest_and_symlink_drift_refuse_without_source_execution(tmp_path):
    wrong = tmp_path / "networks.py"
    wrong.write_bytes(validation.NATIVE.read_bytes() + b"\n# changed\n")
    with pytest.raises(ValueError, match="pinned original"):
        validation.source_plan(wrong)
    alias = tmp_path / "alias.py"
    alias.symlink_to(validation.NATIVE)
    with pytest.raises(ValueError, match="pinned original"):
        validation.source_plan(alias)


def test_current_live_consumers_require_the_native_helper_without_admitting_an_INIT():
    candidate = formatter.prepare()
    assert formatter.describe(candidate)["installed"] is False
    assert formatter.describe(candidate)["actual_source_formatter_aliases_installed"] is True
    result = validation.require_adopted_binding()
    assert result["formatter_bound"] is True
    assert result["INIT_or_native_owner_admission"] is False


def test_provenance_JSON_roundtrip_has_no_callable_constructor_or_native_admission(formatter_work):
    data = formatter.describe(formatter.prepare())
    saved = json.dumps(data, allow_nan=False)
    assert json.loads(saved) == data
    assert data["native_owner_or_INIT_admission"] is False
    assert data["warm_calls"] == 0 and formatter_work == []


@pytest.mark.parametrize("module", [formatter.network, formatter.environment, formatter.lifecycle])
def test_only_declared_import_and_alias_change_the_complete_consumer_AST(module):
    from pathlib import Path

    result = validation.check_declaration_delta(
        module.__name__, ast.parse(Path(module.__file__).read_bytes())
    )
    assert result["complete_remaining_module_AST_equal"] is True
    assert module.tex_val is formatter.check_helper()


@pytest.mark.parametrize(
    "fault", ["missing-import", "duplicate-import", "str-fallback", "wrong-helper", "body-drift"]
)
def test_extra_source_changes_or_missing_alias_authority_are_rejected(fault):
    from pathlib import Path

    module = formatter.network
    tree = ast.parse(Path(module.__file__).read_bytes())
    imported = next(
        n
        for n in tree.body
        if isinstance(n, ast.ImportFrom) and any(a.asname == "formatter_source" for a in n.names)
    )
    alias = next(
        n
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "tex_val" for t in n.targets)
    )
    if fault == "missing-import":
        tree.body.remove(imported)
    elif fault == "duplicate-import":
        tree.body.append(copy.deepcopy(imported))
    elif fault == "str-fallback":
        alias.value = ast.Name("str", ast.Load())
    elif fault == "wrong-helper":
        alias.value.attr = "unknown_formatter"
    else:
        tree.body.append(ast.Pass())
    with pytest.raises(ValueError, match="formatter|Source changed beyond"):
        validation.check_declaration_delta(module.__name__, tree)


@pytest.mark.parametrize("role,count", [("molecules", 5), ("grn", 4)])
def test_actual_source_owner_class_and_inherited_methods_are_retained(role, count):
    row = validation.require_adopted_binding()["roles"][role]
    assert len(row["formatter_methods"]) == count
    assert row["class_name"].startswith("cells.processes.")
    assert formatter.lifecycle.MasterOfGenes is formatter.lifecycle.qualified.MasterOfGenes


def test_current_reference_binds_native_formatter_without_rebinding_frozen_str_evidence(
    tmp_path, no_formatter_calls
):
    plan = reference.source_plan()
    correspondence = plan["formatter_correspondence"]
    assert correspondence["whole_executable_function_AST_equal"] is True
    assert correspondence["actual_helper_identity_and_cached_builtins_checked"] is True
    assert correspondence["evaluated"] is False and plan["scientific_admission"] is False
    assert no_formatter_calls == []
    retain(
        tmp_path / "current-reference-prerequisite",
        dict(
            current_source_plan=plan,
            reference_comparator_relaxed=False,
            frozen_str_evidence_rebound=False,
            original_reference_calls=0,
        ),
    )


def test_current_reference_still_refuses_old_str_without_formatter_calls(
    monkeypatch, tmp_path, no_formatter_calls
):
    monkeypatch.setitem(formatter._ORIGINALS[0].__globals__, "tex_val", str)
    with pytest.raises(ValueError) as caught:
        reference.source_plan()
    assert no_formatter_calls == []
    retain(
        tmp_path / "old-str-reference-refusal",
        dict(primary=str(caught.value), accepted=False, frozen_evidence_rebound=False),
    )


@pytest.fixture
def no_formatter_calls(tmp_path, no_actual_execution, no_warm_source_calls, no_original_execution):
    """F1 controls inspect function objects; no formatter/consumer may run."""
    previous, attempted = sys.getprofile(), []
    forbidden = {formatter._FORMATTER_CODE, *formatter._CODES}

    def guard(frame, event, arg):
        if event == "call" and frame.f_code in forbidden:
            attempted.append(frame.f_code.co_name)
            raise AssertionError("F1 no-call source control attempted formatter execution")
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(guard)
    yield attempted
    sys.setprofile(previous)
    (tmp_path / "F1-no-call-control.json").write_text(
        json.dumps(
            dict(
                source_entry_attempts=attempted,
                formatter_calls=0,
                scientific_acceptance=False,
                source_object_inspection_only=True,
            )
        )
    )
    assert attempted == []


@pytest.mark.parametrize("representation", ["dictionary", "module"])
def test_F1_construction_binds_actual_cached_builtin_dictionary(
    representation, monkeypatch, no_formatter_calls, tmp_path
):
    if representation == "module":
        for original in formatter._ORIGINALS:
            assert original.__builtins__ is vars(builtins)
            monkeypatch.setitem(original.__globals__, "__builtins__", builtins)
    value = formatter.prepare()
    for name, original in zip(value.methods, formatter._ORIGINALS, strict=True):
        copied = value.methods[name]
        assert copied.__builtins__ is original.__builtins__
        assert formatter._builtin_dictionary(copied.__globals__) is original.__builtins__
    formatter.check_prepared(value)
    assert no_formatter_calls == []
    retain(
        tmp_path / "F1-construction",
        dict(
            representation=representation,
            actual_cached_builtin_identity_bound=True,
            methods=len(value.methods),
            formatter_evaluations=0,
        ),
    )


@pytest.mark.parametrize("drift", ["foreign-dictionary", "missing-slot", "none-slot"])
def test_F1_original_construction_namespace_drift_refuses_without_calls(
    drift, monkeypatch, no_formatter_calls, tmp_path
):
    original = formatter._ORIGINALS[0]
    expected = original.__builtins__
    if drift == "foreign-dictionary":
        monkeypatch.setitem(original.__globals__, "__builtins__", dict(expected))
    elif drift == "missing-slot":
        monkeypatch.delitem(original.__globals__, "__builtins__")
    else:
        monkeypatch.setitem(original.__globals__, "__builtins__", None)
    assert original.__builtins__ is expected
    with pytest.raises(ValueError, match="cached builtins|builtins namespace") as caught:
        formatter.prepare()
    assert no_formatter_calls == []
    retain(
        tmp_path / "F1-original-drift",
        dict(
            drift=drift,
            primary=str(caught.value),
            actual_original_cached_dictionary_unchanged=True,
            formatter_evaluations=0,
            accepted=False,
        ),
    )


@pytest.mark.parametrize("drift", ["foreign-cached-restored-globals", "changed-current-slot"])
def test_F1_private_cached_and_current_builtins_mismatch_refuses_without_calls(
    drift, no_formatter_calls, tmp_path
):
    value = formatter.prepare()
    name = next(iter(value.methods))
    method = value.methods[name]
    expected = method.__builtins__
    namespace = method.__globals__
    foreign = dict(expected)
    namespace["__builtins__"] = foreign
    if drift == "foreign-cached-restored-globals":
        forged = FunctionType(
            method.__code__, namespace, method.__name__, method.__defaults__, method.__closure__
        )
        namespace["__builtins__"] = expected
        forged.__kwdefaults__ = method.__kwdefaults__
        forged.__annotations__ = method.__annotations__
        forged.__qualname__, forged.__doc__ = method.__qualname__, method.__doc__
        assert forged.__builtins__ is foreign
        assert forged.__globals__["__builtins__"] is expected
        assert forged.__code__ is method.__code__ and forged.__globals__ is method.__globals__
        methods = dict(value.methods)
        methods[name] = forged
        value = replace(value, methods=MappingProxyType(methods))
    else:
        assert method.__builtins__ is expected
        assert method.__globals__["__builtins__"] is foreign
    with pytest.raises(ValueError, match="Private formatter cached builtins/namespace") as caught:
        formatter.check_prepared(value)
    assert no_formatter_calls == []
    retain(
        tmp_path / "F1-private-drift",
        dict(
            drift=drift,
            primary=str(caught.value),
            formatter_evaluations=0,
            accepted=False,
            code_defaults_and_nonbuiltin_globals_preserved=True,
            cached_dictionary_identity_is_distinct_from_current_slot=True,
        ),
    )
