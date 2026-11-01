"""Pinned AST and synthetic observation controls; actual source stays blocked."""

import ast
import copy
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace as NS

import pytest

from validation.betse import native_multi_cell_environment_native as n

ROOT = Path("/mnt/workspaces/Cells/betse-v1.5.0")


def select(groups, file, name):
    return next(
        node
        for f, nodes in groups
        if f == file
        for node in nodes
        if getattr(node, "name", None) == name
    )


def test_original_ordinary_world_prefix_and_every_body_are_literal():
    groups, sites = n.source_nodes(ROOT)
    cells = select(groups, n.legacy_source.CELLS_FILE, "Cells")
    original = next(
        node
        for node in ast.parse((ROOT / n.legacy_source.CELLS_FILE).read_bytes()).body
        if isinstance(node, ast.ClassDef) and node.name == "Cells"
    )
    methods = {node.name: node for node in original.body if isinstance(node, ast.FunctionDef)}
    world = next(node for node in cells.body if node.name == "make_world")

    def dump(node):
        return ast.dump(node, include_attributes=False)

    assert [dump(node) for node in world.body] == [
        dump(node) for node in methods["make_world"].body[: len(world.body)]
    ]
    assert ast.unparse(world.body[-1]) == "self.make_maskM(phase.p)"
    assert "makeLaplacian" not in ast.unparse(world)
    for name in n.BODY_METHODS:
        assert dump(next(node for node in cells.body if node.name == name)) == dump(methods[name])
    assert sites[n.legacy_source.CELLS_FILE + ":make_world.grid_len"]["first_line"] == 494


def test_multi_twenty_stores_and_lazy_descriptor_remain_distinct_original_authorities():
    groups, _ = n.source_nodes(ROOT)
    stores = select(groups, n.legacy_source.PARAMETER_FILE, "store_parameters")
    assert [node.lineno for node in stores.body] == list(n.STORE_LINES)
    assert len(stores.body) == 20 and stores.body[0].lineno == 521
    descriptor = select(groups, n.legacy_source.PARAMETER_FILE, "parameter_type")
    assert n.DESCRIPTOR in ast.unparse(descriptor) and "grid_size" in ast.unparse(descriptor)
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "grid_size" for node in ast.walk(stores)
    )


def test_compile_only_private_namespace_extension_does_not_mutate_legacy_runtime():
    old = (
        n.legacy_runtime.MODULE_ORDER,
        copy.deepcopy(n.legacy_runtime.DIRECT),
        copy.deepcopy(n.legacy_runtime.EXPORTS),
    )
    scope = n.runtime_functions()
    groups, _ = n.source_nodes(ROOT)
    codes, _, metadata = scope["compile_groups"](groups, native_root=ROOT)
    assert "betse.science.math.finitediff" in codes
    assert metadata["constructors_methods_rng_decode_or_operators_executed"] is False
    assert (
        n.legacy_runtime.MODULE_ORDER == old[0]
        and n.legacy_runtime.DIRECT == old[1]
        and n.legacy_runtime.EXPORTS == old[2]
    )
    assert scope["DIRECT"]["betse.science.cells"]["fd"] == "betse.science.math.finitediff"


def test_source_ast_is_fresh_and_rechecks_original_pins(monkeypatch):
    groups, _ = n.source_nodes(ROOT)
    select(groups, n.legacy_source.CELLS_FILE, "Cells").body.clear()
    again, _ = n.source_nodes(ROOT)
    assert len(select(again, n.legacy_source.CELLS_FILE, "Cells").body) > 5
    original = n.shared.digest
    monkeypatch.setattr(
        n.shared, "digest", lambda p: "0" * 64 if str(p).endswith("finitediff.py") else original(p)
    )
    with pytest.raises(ValueError, match="source"):
        n.source_nodes(ROOT)


def observer(capture=copy.deepcopy):
    return n.Observation(
        capture,
        lambda e: dict(type=type(e).__name__, message=str(e)),
        lambda: {"synthetic_stream": True},
    )


def test_self_only_grid_len_observation_precedes_mask_and_preserves_actual_aliases():
    obs = observer()
    marker = []

    class Cells:
        def environment(self, p):
            self.xypts = marker

        def make_maskM(self, p):
            self.maskM = marker

    obs.caller = Cells()
    obs.mesh = NS(image_mask=None)
    obs.parameter = NS(plot_grid_size=50)
    obs.parameter_names = ("plot_grid_size",)
    obs.ordinary_wrap(Cells, "environment")
    obs.ordinary_wrap(Cells, "make_maskM")
    obs.caller.environment(obs.parameter)
    obs.caller.grid_len = len(obs.caller.xypts)  # stand-in for the original inline statement
    obs.caller.make_maskM(obs.parameter)
    assert [name for name, _ in obs.ordinary] == ["environment", "assign_grid_len", "make_maskM"]
    assert obs.caller.xypts is marker and obs.caller.maskM is marker


@pytest.mark.parametrize("boundary", ["enter", "return", "unwind"])
def test_observer_failure_stops_next_body_and_keeps_primary_exception(boundary):
    calls = []
    obs = observer()

    class Cells:
        def environment(self, p):
            calls.append("environment")
            self.partial = [1]
            if boundary == "unwind":
                obs.remember(OSError("capture"), "synthetic_unwind")
                raise ValueError("primary") from RuntimeError("cause")

        def make_maskM(self, p):
            calls.append("mask")

    obs.caller = Cells()
    obs.mesh = NS()
    obs.parameter = NS()
    if boundary == "enter":
        obs.remember(OSError("capture"), "synthetic_enter")
    if boundary == "return":
        obs.capture = lambda value: (_ for _ in ()).throw(OSError("capture"))
    obs.ordinary_wrap(Cells, "environment")
    obs.ordinary_wrap(Cells, "make_maskM")
    with pytest.raises((n.legacy.CaptureFailure, ValueError)) as caught:
        obs.caller.environment(obs.parameter)
        obs.caller.make_maskM(obs.parameter)
    assert calls == ([] if boundary == "enter" else ["environment"])
    assert obs.capture_error is not None
    if boundary == "unwind":
        assert str(caught.value) == "primary" and str(caught.value.__cause__) == "cause"
        assert obs.caller.partial == [1]


def test_parameter_snapshot_excludes_only_normalized_phase_adapter_fields():
    obs = observer()

    class Cells:
        def cell_index(self, p):
            self.cell_i = []

    obs.caller = Cells()
    obs.mesh = NS()
    obs.parameter = NS(plot_grid_size=50, tissue_default=object(), conf_dirname="synthetic")
    obs.wrap(Cells, "cell_index")
    obs.caller.cell_index(obs.parameter)
    assert obs.parameter_names == ("plot_grid_size",)
    assert obs.before["parameters"] == {"plot_grid_size": 50}


def test_descriptor_construction_is_before_any_reference_parameter_or_caller_birth():
    tree = ast.parse(Path(n.__file__).read_text())
    evaluate = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "evaluate"
    )
    text = ast.unparse(evaluate)
    assert text.index("descriptor_before_birth(") < text.index("clone(legacy._execute")
    assert "parameter_type(**kwargs) if '_conf' in kwargs" in text
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)


@pytest.mark.parametrize("fail", [False, True])
def test_descriptor_work_is_attempts_not_cases_and_before_any_parameter_birth(monkeypatch, fail):
    obs = observer()
    calls = []

    def selected(factory, root):
        calls.append((obs.parameter, obs.caller))
        if fail:
            raise ValueError("original descriptor") from RuntimeError("descriptor cause")
        return (object(), {"synthetic": True})

    monkeypatch.setattr(n.shared, "grid_parameter_type", selected)
    if fail:
        with pytest.raises(ValueError, match="original descriptor") as caught:
            n.descriptor_before_birth(obs, object(), "/synthetic_original")
        assert str(caught.value.__cause__) == "descriptor cause"
    else:
        assert n.descriptor_before_birth(obs, object(), "/synthetic_original")[1] == {
            "synthetic": True
        }
    assert calls == [(None, None)]
    assert [row["event"] for row in obs.work] == ["attempt", "failed" if fail else "returned"]
    assert not any(row["is_case"] for row in obs.work)
    obs.parameter = NS()
    with pytest.raises(ValueError, match="retrofitted"):
        n.descriptor_before_birth(obs, object(), "/synthetic_original")
    assert len(calls) == 1


def test_raw_fields_keep_available_data_when_adjacent_actual_references_are_opaque():
    opaque = object()
    value = [1, -2, 3]

    def capture(item):
        if item is opaque:
            raise ValueError("opaque actual owner")
        return copy.deepcopy(item)

    obs = observer(capture)
    obs.caller = NS(mesh=opaque, cell_i=value)
    obs.raw_locals = {"standin.py:makeECM": dict(self=opaque, completed_buffer=value)}
    rows = n.retain_raw(obs)
    saved = {row["label"]: row for row in rows}
    assert (
        saved["caller.mesh"]["status"]
        == saved["locals.standin.py:makeECM.self"]["status"]
        == "capture_failed"
    )
    assert (
        saved["caller.cell_i"]["value"]
        == saved["locals.standin.py:makeECM.completed_buffer"]["value"]
        == value
    )
    assert (
        obs.caller.cell_i is value
        and obs.raw_locals["standin.py:makeECM"]["completed_buffer"] is value
    )


@pytest.mark.parametrize("fail", [False, True])
def test_profile_preserves_raw_return_or_unwind_locals_and_previous_guard(fail):
    obs = observer()
    visits = []
    previous = sys.getprofile()

    def guard(frame, event, arg):
        if frame.f_code.co_name == "standin":
            visits.append(event)
        if previous is not None:
            previous(frame, event, arg)

    namespace = {}
    exec(
        compile(
            "def standin(fail):\n"
            "    completed=[1,2]\n"
            "    if fail:\n"
            "        raise ValueError('primary') from RuntimeError('cause')\n"
            "    return completed\n",
            "/synthetic_original/standin.py",
            "exec",
        ),
        namespace,
    )
    try:
        sys.setprofile(guard)
        with n.source_observation(obs, "/synthetic_original", "ordinary_reference"):
            if fail:
                with pytest.raises(ValueError, match="primary") as caught:
                    namespace["standin"](True)
                assert str(caught.value.__cause__) == "cause"
            else:
                assert namespace["standin"](False) == [1, 2]
        assert sys.getprofile() is guard
    finally:
        sys.setprofile(previous)
    assert "call" in visits and "return" in visits
    assert obs.raw_locals["standin.py:standin"]["completed"] == [1, 2]


def numpy_helper_fixture(monkeypatch):
    scope = n.runtime_functions()
    numpy, core, methods = (
        ModuleType(name) for name in ("numpy", "numpy._core", "numpy._core._methods")
    )
    numpy._core = core
    core._methods = methods
    numpy.random = object()
    for value in (numpy, core, methods):
        monkeypatch.setitem(sys.modules, value.__name__, value)
    rng = object()
    proxy = scope["_Numpy"](numpy, rng)
    binding = scope["_cached_numpy_helpers"](numpy)
    importer = scope["_importer"]("betse.science.cells", set(), {}, proxy, binding)
    return scope, numpy, core, methods, proxy, rng, importer


def test_numpy_helper_uses_exact_reviewed_root_code_and_private_namespace():
    scope = n.runtime_functions()
    for name in ("_cached_numpy_helpers", "_check_numpy_helpers", "_importer", "build"):
        assert scope[name].__code__ is getattr(n.legacy_runtime, name).__code__
        assert scope[name].__globals__ is scope
    assert scope["NUMPY_C_API_IMPORT"] == ("numpy._core._methods", (), 0)
    assert "betse.science.math.finitediff" not in n.legacy_runtime.MODULE_ORDER


def test_numpy_helper_exact_cached_request_keeps_actual_links_and_private_rng(monkeypatch):
    _, numpy, core, methods, proxy, rng, importer = numpy_helper_fixture(monkeypatch)
    before = {name: sys.modules[name] for name in ("numpy", "numpy._core", "numpy._core._methods")}
    assert importer("numpy._core._methods", {}, {}, (), 0) is proxy
    assert proxy._module is numpy and proxy.random is rng and proxy.random is not numpy.random
    assert numpy._core is core and core._methods is methods
    assert all(sys.modules[name] is value for name, value in before.items())


@pytest.mark.parametrize(
    "drift",
    [
        "numpy_cache",
        "core_cache",
        "methods_cache",
        "core_link",
        "methods_link",
        "name",
        "proxy",
        "missing",
    ],
)
def test_numpy_helper_changed_cached_authority_refuses_before_any_loader(monkeypatch, drift):
    scope, numpy, core, methods, proxy, _, importer = numpy_helper_fixture(monkeypatch)
    if drift.endswith("_cache"):
        name = {
            "numpy_cache": "numpy",
            "core_cache": "numpy._core",
            "methods_cache": "numpy._core._methods",
        }[drift]
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    elif drift == "core_link":
        numpy._core = ModuleType("numpy._core")
    elif drift == "methods_link":
        core._methods = ModuleType("numpy._core._methods")
    elif drift == "name":
        methods.__name__ = "numpy._core.supplied"
    elif drift == "proxy":
        proxy._module = ModuleType("numpy")
    else:
        importer = scope["_importer"]("betse.science.cells", set(), {}, proxy, None)
    with pytest.raises(ImportError, match="cached NumPy"):
        importer("numpy._core._methods")


@pytest.mark.parametrize(
    "name,fromlist,level",
    [
        ("numpy._core._methods", ("_mean",), 0),
        ("numpy._core._methods", ("*",), 0),
        ("numpy._core._methods", (), 1),
        ("numpy._core._exceptions", (), 0),
        ("numpy.core._methods", (), 0),
        ("betse.science.cells", (), 0),
    ],
)
def test_numpy_helper_exception_does_not_widen_package_or_source_imports(
    monkeypatch, name, fromlist, level
):
    *_, importer = numpy_helper_fixture(monkeypatch)
    with pytest.raises(ImportError, match="Undeclared"):
        importer(name, fromlist=fromlist, level=level)


@pytest.mark.parametrize("failure", ["factory", "observer", "both"])
def test_repair_c1_descriptor_failure_has_failed_envelope_and_no_parent(monkeypatch, failure):
    primary = ValueError("original descriptor factory")
    primary.__cause__ = RuntimeError("original descriptor cause")
    captured = []

    def record(error):
        captured.append(error)
        return dict(
            type=type(error).__name__,
            message=str(error),
            cause=None if error.__cause__ is None else str(error.__cause__),
        )

    obs = n.Observation(copy.deepcopy, record, lambda: {"retained_actual_rng_marker": True})
    attempt = NS(execution=None, descriptor_metadata=None, source_body_attempted=False)
    calls = []

    def factory(*a):
        obs.raw_locals["descriptor.py:factory"] = {"partial_bits": [1, -2, 3]}
        if failure in {"observer", "both"}:
            obs.remember(OSError("descriptor observation"), "descriptor_locals")
        if failure in {"factory", "both"}:
            raise primary
        return object(), {"actual_factory_returned": True}

    monkeypatch.setattr(n.shared, "grid_parameter_type", factory)
    with n._source_attempt(obs, attempt):
        obs.stage = "descriptor_construction"
        _, attempt.descriptor_metadata = n.descriptor_before_birth(
            obs, object(), "/synthetic_original"
        )
        calls.append("forbidden caller construction")
    result = n._finalize_reference(
        obs,
        attempt.execution,
        attempt.descriptor_metadata,
        sites={"synthetic": "site"},
        image_sha256="a" * 64,
        source_attempted=attempt.source_body_attempted,
    )
    assert calls == [] and obs.parameter is None and obs.caller is None
    assert result["status"] == "source_failed" and result["source_body_completed"] is False
    assert (
        result["before"] is None
        and result["cache"] is None
        and result["descriptor_metadata"] is None
    )
    assert (
        result["actual_source_executions"] == 0
        and result["descriptor_constructions_attempted"] == 1
    )
    assert [row["event"] for row in result["work"]] == ["attempt", "failed"]
    assert result["failed_stage"] == "descriptor_construction"
    raw = {row["label"]: row for row in result["raw_captures"]}
    assert raw["locals.descriptor.py:factory.partial_bits"]["value"] == [1, -2, 3]
    if failure in {"factory", "both"}:
        assert primary in captured
        assert result["source_error"]["cause"] == "original descriptor cause"
    else:
        assert result["source_error"] is None
    if failure in {"observer", "both"}:
        assert result["capture_error"]["message"] == "descriptor observation"
        assert result["capture_errors"]


def test_repair_c1_evaluate_descriptor_is_inside_the_same_protected_source_attempt():
    tree = ast.parse(Path(n.__file__).read_text())
    evaluate = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "evaluate"
    )
    block = next(
        node
        for node in evaluate.body
        if isinstance(node, ast.With)
        and any(
            isinstance(item.context_expr, ast.Call)
            and getattr(item.context_expr.func, "id", None) == "_source_attempt"
            for item in node.items
        )
    )
    text = ast.unparse(block)
    assert text.index("descriptor_before_birth(") < text.index("clone(legacy._execute")
    assert isinstance(evaluate.body[-1], ast.Return)
    assert evaluate.body[-1].value.func.id == "_finalize_reference"


def rejected_capture_guards(target, *, mode, reject_value=None):
    prior = n._guards()
    visits = []

    def match(frame, event):
        return (
            event == "call"
            and frame.f_code is target.__code__
            and (reject_value is None or frame.f_locals.get("value") is reject_value)
        )

    def trace(frame, event, arg):
        if match(frame, event):
            visits.append("trace_reject")
            raise OSError("outer trace capture refusal")
        return trace

    def profile(frame, event, arg):
        if prior[0] is not None:
            prior[0](frame, event, arg)
        if mode == "profile" and match(frame, event):
            visits.append("profile_reject")
            raise OSError("outer profile capture refusal")

    expected = (profile, trace if mode == "trace" else prior[1])
    sys.setprofile(expected[0])
    sys.settrace(expected[1])
    return prior, expected, visits


@pytest.mark.parametrize("mode", ["trace", "profile"])
def test_repair_c2_final_probes_restore_both_guards_after_actual_rejection(mode):
    obs = observer()
    original = dict(type="ValueError", message="retained primary", cause="retained cause")
    execution = dict(
        status="source_failed",
        source_body_completed=False,
        source_error=original,
        capture_error=None,
        failed_stage="synthetic_source",
        warnings=[],
    )
    calls = []

    def rejected():
        calls.append("must not execute")

    prior, expected, visits = rejected_capture_guards(rejected, mode=mode)

    def later():
        assert n._guards() == expected
        calls.append("later guarded probe")
        return "saved"

    try:
        result = n._finalize_reference(
            obs,
            execution,
            None,
            sites={},
            image_sha256="a" * 64,
            source_attempted=True,
            probes={"first": rejected, "second": later},
        )
        assert n._guards() == expected
    finally:
        n._restore_guards(prior)
    assert visits == [mode + "_reject"] and calls == ["later guarded probe"]
    assert result["source_error"] is original and result["capture_error"] is not None
    assert result["second"] == "saved" and result["status"] == "source_failed"


@pytest.mark.parametrize("mode", ["trace", "profile"])
def test_repair_c2_raw_field_rejection_does_not_leave_later_fields_unguarded(mode):
    first = [1]
    second = [2]
    expected = None

    def capture(value):
        assert n._guards() == expected
        return copy.deepcopy(value)

    obs = observer(capture)
    obs.caller = NS(first=first, second=second)
    prior, expected, visits = rejected_capture_guards(capture, mode=mode, reject_value=first)
    try:
        rows = n.retain_raw(obs)
        assert n._guards() == expected
    finally:
        n._restore_guards(prior)
    records = {row["label"]: row for row in rows}
    assert visits == [mode + "_reject"]
    assert records["caller.first"]["status"] == "capture_failed"
    assert records["caller.second"]["value"] == second
    assert obs.caller.first is first and obs.caller.second is second


def test_repair_c2_source_context_restores_prior_trace_and_profile_after_trace_refusal():
    obs = observer()

    def rejected():
        raise AssertionError("must not enter synthetic delegate")

    prior, expected, visits = rejected_capture_guards(rejected, mode="trace")
    try:
        with pytest.raises(OSError, match="outer trace"):
            with n.source_observation(obs, "/synthetic_original", "descriptor_construction"):
                rejected()
        assert n._guards() == expected
    finally:
        n._restore_guards(prior)
    assert visits == ["trace_reject"]
