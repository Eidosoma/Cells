"""Blocked original-source definitions and synthetic retained-graph controls.

No original constructor, warm body, formatter, factory, model or RNG executes.
Positive graphs/profiles are explicitly synthetic and confer no parent credit.
"""

import ast
import copy
import json
import struct
import sys
from types import CellType, FunctionType, SimpleNamespace

import numpy as np
import pytest

from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_kinetic_reload_checkpoint import (
    graph as kinetic_graph,
)
from tests.unit.test_betse_normal_ecm_molecule_kinetic_reload_checkpoint import (
    no_warm_source_calls as no_warm_source_calls,
)
from validation.betse import betse_normal_ecm_molecule_kinetic_reload_reference as reference
from validation.betse import betse_normal_ecm_molecule_kinetic_reload_reference_native as native


@pytest.fixture(autouse=True)
def no_original_execution(tmp_path):
    previous, attempted = sys.getprofile(), []
    names = {"tex_val"} | set().union(*native.WARM.values())

    def guard(frame, event, arg):
        filename = frame.f_code.co_filename
        if (
            event == "call"
            and frame.f_code.co_name in names
            and (filename.startswith(native.PREFIX) or filename == "<authenticated native catalog>")
        ):
            attempted.append(dict(function=frame.f_code.co_name, file=filename))
            raise AssertionError("Actual original reference/helper body forbidden")
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(guard)
    yield attempted
    sys.setprofile(previous)
    (tmp_path / "reference-control.json").write_text(
        json.dumps(
            dict(
                actual_original_source_calls=attempted,
                synthetic_only=True,
                scientific_acceptance=False,
                parent_admission=False,
            )
        )
    )
    assert attempted == []


class SyntheticMolecule:
    pass


class SyntheticOriginal:
    pass


class SyntheticDynamic:
    pass


class SyntheticAliases:
    pass


def roots():
    sim = SimpleNamespace(cc_cells=np.array([[1.0, 2.0]]), extra_J_mem=np.array([0.0, 0.0]))
    cells = SimpleNamespace(cell_i=np.array([0, 1]), cell_ids=("cell-A", "cell-Z"))
    p = SimpleNamespace(_run_sim=True, network_config={"production rate": 0.1, "decay rate": 0.2})
    phase = SimpleNamespace(
        sim=sim,
        cells=cells,
        p=p,
        kind="SIM",
        dyna=SimpleNamespace(
            cell_target_inds={"tissue": np.array([0, 1])},
            tissue_target_inds={"tissue": np.array([1, 0, 1])},
        ),
    )
    sim.dyna = phase.dyna
    mol = SyntheticMolecule()
    mol.r_production, mol.r_decay = 0.1, 0.2
    mol.c_cells = np.array([3.0, 4.0])
    mol.gad_tex_vars = "original text, do not project away"
    sim.molecule = mol
    value = dict(
        sim=sim,
        cells=cells,
        p=p,
        phase=phase,
        raw={"source": "synthetic only"},
        ion_ids=("Na",),
        enabled={"molecules": True, "grn": False},
        definitions={"network": {"species": ["X", "Y"]}},
        catalogs={"ordered_targets": [1, 0, 1]},
    )
    return value


def contracts():
    return dict(
        types={SimpleNamespace: "record", SyntheticMolecule: "Molecule"}, aliases={}, functions={}
    )


def capture(value):
    return native.Graph(**contracts()).capture(value)[0]


def association():
    return dict(
        binding="synthetic-binding",
        complete_INIT="synthetic-complete",
        INIT_parent="synthetic-parent",
        kinetic_declaration="synthetic-request-digest",
    )


def leg(value=None, status="source_completed"):
    value = roots() if value is None else value
    graph = capture(value)
    return dict(
        association=association(),
        status=status,
        before=graph,
        after=copy.deepcopy(graph),
        capture_complete=True,
        capture_errors=[],
    )


def save_control(path, payload):
    reference.retention.archives.write_archive(
        path,
        dict(
            payload,
            synthetic_only=True,
            actual_original_source_entries=0,
            scientific_acceptance=False,
        ),
    )


def test_pinned_original_transitive_plan_keeps_formatter_difference_explicit(tmp_path):
    plan = reference.source_plan()
    assert plan["compiled_or_executed"] is False
    assert plan["formatter_correspondence"]["transitive_source_equal"] is False
    sites = plan["original"]["sites"]
    for name in (
        "MasterOfMolecules.reinitialize",
        "MasterOfGenes.reinitialize",
        "MasterOfNetworks.tissue_init",
        "MasterOfNetworks.write_growth_and_decay",
        "Molecule.init_growth",
        "tex_val",
    ):
        assert name in sites
    save_control(tmp_path / "source-plan", plan)


def test_compile_definitions_only_in_fresh_original_namespace_with_exact_formatter(tmp_path):
    api, second = native.compile_original(), native.compile_original()
    assert api.namespace is not second.namespace
    assert api.classes["MasterOfNetworks"] is not second.classes["MasterOfNetworks"]
    assert api.namespace["tex_val"] is not str
    assert api.namespace["tex_val"].__code__.co_filename.startswith(native.PREFIX)
    assert api.namespace["tex_val"].__globals__ is api.namespace
    for tag in native.WARM:
        for name in native.WARM[tag]:
            method = vars(api.classes[tag])[name]
            assert method.__globals__ is api.namespace
            assert method.__code__.co_filename.startswith(native.PREFIX)
    assert api.plan["source_calls"] == api.plan["actual_constructor_calls"] == 0
    save_control(tmp_path / "compiled-definitions", api.plan)


@pytest.mark.parametrize("fault", ["decorator", "default"])
def test_executable_rejects_unapproved_class_definition_execution(fault):
    text = (
        "@foreign\ndef sample(x): return x"
        if fault == "decorator"
        else "def sample(x=foreign()): return x"
    )
    with pytest.raises(ValueError):
        native.Executable().visit(ast.parse(text).body[0])


def test_declared_annotation_cleaning_preserves_complete_method_body():
    original = ast.parse(
        "@type_check\ndef f(self, x: int = 1) -> None:\n 'doc'\n self.x = x\n return None"
    ).body[0]
    expected_body = ast.dump(
        ast.Module(body=original.body, type_ignores=[]), include_attributes=False
    )
    cleaned = native.Executable().visit(copy.deepcopy(original))
    assert (
        ast.dump(ast.Module(body=cleaned.body, type_ignores=[]), include_attributes=False)
        == expected_body
    )
    assert cleaned.decorator_list == [] and cleaned.returns is None


@pytest.mark.parametrize("fault", ["missing-file", "changed-byte"])
def test_original_file_pin_mismatch_refuses_before_compilation(tmp_path, fault):
    root = tmp_path / "original"
    root.mkdir()
    if fault == "changed-byte":
        (root / "exceptions.py").write_text("class BetseException(Exception): pass\n")
    with pytest.raises(ValueError, match="pinned original"):
        native.source_plan(root)


def test_complete_graph_copy_preserves_phase_aliases_values_layout_and_profiles(tmp_path):
    value = roots()
    graph = native.Graph(
        api=SimpleNamespace(classes={"Molecule": SyntheticOriginal}), **contracts()
    )
    before, copied = graph.capture(value)
    after, _ = native.Graph(
        types={SimpleNamespace: "record", SyntheticOriginal: "Molecule"}, aliases={}, functions={}
    ).capture(copied)
    assert native.compare_graphs(before, after)["aliases_values_layout_config_equal"]
    assert copied["phase"].sim is copied["sim"] and copied["phase"].p is copied["p"]
    assert copied["phase"].dyna is copied["sim"].dyna
    assert copied["sim"].molecule is not value["sim"].molecule
    copied["sim"].molecule.c_cells[0] = 99
    assert value["sim"].molecule.c_cells[0] == 3
    save_control(tmp_path / "complete-graph", dict(before=before, after=after))


@pytest.mark.parametrize("kind", ["C", "F", "readonly", "zero-dimensional", "numpy-scalar"])
def test_array_and_scalar_categories_and_layout_are_not_erased(kind):
    value = roots()
    a = np.arange(6.0).reshape(2, 3).copy()
    if kind == "F":
        a = np.asfortranarray(a)
    elif kind == "readonly":
        a.setflags(write=False)
    elif kind == "zero-dimensional":
        a = np.array(1.5)
    elif kind == "numpy-scalar":
        a = np.float64(1.5)
    value["raw"]["array"] = a
    before = capture(value)
    _, copied = native.Graph(
        api=SimpleNamespace(classes={"Molecule": SyntheticMolecule}), **contracts()
    ).capture(value)
    again = capture(copied)
    native.compare_graphs(before, again)
    nodes = [n for n in before["nodes"] if n.get("kind") in ("array", "numpy_scalar")]
    assert nodes


@pytest.mark.parametrize(
    "fault",
    [
        "dtype",
        "shape",
        "order",
        "writable",
        "scalar-category",
        "signed-zero",
        "profile-order",
        "profile-duplicate",
        "owner-axis",
        "config",
        "material",
        "GAD-text",
        "extra-field",
        "alias",
    ],
)
def test_full_comparison_detects_non_rate_graph_drift(fault, tmp_path):
    left = roots()
    left["raw"]["matrix"] = np.arange(6.0).reshape(2, 3).copy()
    left["raw"]["zero"] = 0.0
    right = copy.deepcopy(left)
    if fault == "dtype":
        right["sim"].molecule.c_cells = right["sim"].molecule.c_cells.astype(np.float32)
    elif fault == "shape":
        right["sim"].molecule.c_cells = right["sim"].molecule.c_cells.reshape(1, 2).copy()
    elif fault == "order":
        right["raw"]["matrix"] = np.asfortranarray(right["raw"]["matrix"])
    elif fault == "writable":
        right["raw"]["matrix"].setflags(write=False)
    elif fault == "scalar-category":
        right["raw"]["zero"] = np.array(0.0)
    elif fault == "signed-zero":
        right["raw"]["zero"] = -0.0
    elif fault == "profile-order":
        right["phase"].dyna.tissue_target_inds["tissue"] = np.array([0, 1, 1])
    elif fault == "profile-duplicate":
        right["phase"].dyna.tissue_target_inds["tissue"] = np.array([1, 0])
    elif fault == "owner-axis":
        right["cells"].cell_ids = ("cell-Z", "cell-A")
    elif fault == "config":
        right["p"].network_config["decay rate"] = 0.3
    elif fault == "material":
        right["sim"].cc_cells[0, 0] += 1
    elif fault == "GAD-text":
        right["sim"].molecule.gad_tex_vars = "str differs from the original formatter"
    elif fault == "extra-field":
        right["sim"].molecule.unrecorded_state = 0.0
    else:
        right["phase"].sim = copy.deepcopy(right["sim"])
    original, candidate = capture(left), capture(right)
    with pytest.raises(ValueError, match="graph differs"):
        native.compare_graphs(original, candidate)
    save_control(
        tmp_path / "drift",
        dict(
            fault=fault,
            original=original,
            candidate=candidate,
            rates_equal=True,
            complete_match=False,
        ),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "unknown-object",
        "callback",
        "unknown-base",
        "unknown-buffer",
        "logical-bound",
        "metadata-dtype",
        "object-array",
        "missing-root",
        "node-bound",
        "byte-bound",
    ],
)
def test_unowned_runtime_data_and_layout_refuse_with_partial_evidence(monkeypatch, fault):
    value = roots()
    if fault == "unknown-object":
        value["raw"]["unowned"] = object()
    elif fault == "callback":
        value["p"].foreign_callback = lambda: None
    elif fault == "unknown-base":
        value["raw"]["view"] = np.lib.stride_tricks.as_strided(
            np.arange(8.0), shape=(2,), strides=(8,)
        )
    elif fault == "unknown-buffer":
        value["raw"]["view"] = np.frombuffer(memoryview(bytearray(32)), dtype=np.float64)
    elif fault == "logical-bound":
        value["raw"]["view"] = np.ndarray(
            (native.MAX_ARRAY_BYTES // 8 + 1,), dtype=np.float64, buffer=np.zeros(1), strides=(0,)
        )
    elif fault == "object-array":
        value["raw"]["array"] = np.array([object()])
    elif fault == "metadata-dtype":
        value["raw"]["array"] = np.zeros(
            2, dtype=np.dtype("f8", metadata={"unowned_callback": lambda: None})
        )
    elif fault == "missing-root":
        value.pop("phase")
    elif fault == "node-bound":
        monkeypatch.setattr(native, "MAX_NODES", 2)
    else:
        monkeypatch.setattr(native, "MAX_ARRAY_BYTES", 1)
    with pytest.raises(ValueError) as caught:
        capture(value)
    intended = {
        "unknown-object": "class/callback authority",
        "callback": "class/callback authority",
        "unknown-base": "storage/base authority",
        "unknown-buffer": "storage/base authority",
        "logical-bound": "logical array exceeds byte bound",
        "metadata-dtype": "array dtype",
        "object-array": "array dtype",
        "missing-root": "Complete ordered runtime roots",
        "node-bound": "node bound",
        "byte-bound": "byte bound",
    }
    assert intended[fault] in str(caught.value)
    if fault != "missing-root":
        assert caught.value.partial["complete"] is False and caught.value.partial["nodes"]


def test_dynamic_alias_copy_preserves_mutation_association_without_getter_evaluation():
    value = roots()
    alias = SyntheticAliases()
    value["sim"].aliases = alias
    entries = [("Na", value["sim"], "cc_cells", 0), ("X", value["sim"].molecule, "c_cells", None)]
    spec = contracts()
    spec["aliases"][id(alias)] = ("DynamicValueDict", entries)
    api = SimpleNamespace(
        classes={
            "Molecule": SyntheticOriginal,
            "DynamicValue": SyntheticDynamic,
            "DynamicValueDict": SyntheticAliases,
        }
    )
    graph = native.Graph(api=api, **spec)
    before, copied = graph.capture(value)
    mapped = copied["sim"].aliases._key_to_dynamic_value
    mapped["X"].set_value(np.array([7.0, 8.0]))
    assert mapped["X"].get_value() is copied["sim"].molecule.c_cells
    assert copied["sim"].molecule.c_cells.tolist() == [7.0, 8.0]
    assert value["sim"].molecule.c_cells.tolist() == [3.0, 4.0]
    copied["sim"].cc_cells[0, 1] = 10.0
    assert mapped["Na"].get_value()[1] == 10.0
    assert before["capture_complete"] is True


@pytest.mark.parametrize("fault", ["input", "capture", "status", "failure", "parent"])
def test_retained_source_comparison_refuses_incomplete_foreign_or_failed_mismatch(fault):
    a, b = leg(status="source_failed"), leg(status="source_failed")
    a["failure"] = b["failure"] = dict(type="SyntheticFailure", stage="warm", message="retained")
    if fault == "input":
        b["before"]["nodes"][-1]["extra"] = 0
    elif fault == "capture":
        b["capture_errors"] = [dict(stage="reader", message="missing")]
    elif fault == "status":
        b["status"] = "source_completed"
    elif fault == "failure":
        b["failure"] = dict(type="TypeError", stage="warm", message="unexpected")
    else:
        b["association"] = dict(association(), INIT_parent="foreign")
    with pytest.raises(ValueError):
        reference.compare_retained(a, b, association=association())


def test_equal_retained_failure_remains_a_failed_prefix_not_completion(tmp_path):
    a, b = leg(status="source_failed"), leg(status="source_failed")
    a["failure"] = b["failure"] = dict(type="SyntheticFailure", stage="warm", message="retained")
    result = reference.compare_retained(a, b, association=association())
    assert result["status"] == "matching_failed_prefix" and result["full_native_admission"] is False
    save_control(tmp_path / "matching-failure", dict(original=a, candidate=b, result=result))


@pytest.mark.parametrize("gates", [("0", "0"), ("1", "0"), ("0", "1")])
def test_both_gates_precede_parent_output_and_compilation(monkeypatch, tmp_path, gates):
    for key, value in zip(reference.RELEASES, gates, strict=True):
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="both releases"):
        reference.actual_comparison(tmp_path / "held", changes=[], provenance="held")
    assert not (tmp_path / "held").exists()


def test_missing_true_INIT_retains_failure_without_compiling_original_or_creating_owner(
    monkeypatch, tmp_path
):
    for key in reference.RELEASES:
        monkeypatch.setenv(key, "1")

    def forbidden(*a, **kw):
        raise AssertionError("No original compiler/owner before genuine INIT")

    monkeypatch.setattr(native, "compile_original", forbidden)
    path = tmp_path / "missing-parent"
    with pytest.raises(ValueError, match="actual retained INIT"):
        reference.actual_comparison(path, changes=[], provenance="held")
    assert (path / "failure/manifest.json").is_file()
    data = json.loads((path / "attempts.json").read_text())
    assert len(data["attempts"]) == 1 and data["invocations"] == {}


def test_old_conditioning_dictionary_and_scalar_receipt_cannot_finish_runtime_capture():
    binding, completed, _ = kinetic_graph()
    cap = reference.RuntimeCapture(binding, completed, None)
    cap.before = {"incoming_owners": {}, "parameter_fields": {}}
    cap.after = {"rates_equal": True}
    cap.entries = cap.exits = 1
    cap.normal_exit = cap.restored = True
    with pytest.raises(ValueError, match="owner graph/profile/layout"):
        cap.finish()


def test_original_python_work_category_includes_helpers_constructors_and_nested_calls():
    for module in ("original_betse_kinetic_reload", "pinned_catalog_Na", "pinned_catalog_common"):
        for name in ("reinitialize", "__init__", "tex_val", "init_growth"):
            assert reference.ReferenceCalls.category(module, name) == "original_source_boundary"


def profiled_capture(monkeypatch, *, fail_source=False, fail_capture=False):
    binding, completed, _ = kinetic_graph()
    value = roots()
    ctx = SimpleNamespace(
        **{k: value[k] for k in ("sim", "cells", "p", "phase", "raw", "ion_ids", "enabled")}
    )
    ctx.views = {
        "molecules": SimpleNamespace(
            definition={"species": ["X", "Y"]}, catalog={"targets": [1, 0, 1]}
        ),
        "grn": SimpleNamespace(definition={}, catalog={}),
    }
    api = SimpleNamespace(classes={"Molecule": SyntheticOriginal})
    cap = reference.RuntimeCapture(binding, completed, api)
    primary, cause = OSError("synthetic warm error"), LookupError("original synthetic cause")

    def dispatch(self, t, phase, cells, p):
        self.molecule.r_production = 0.3
        if fail_source:
            raise primary from cause

    def initialize(ctx):
        dispatch(ctx.sim, 0.0, ctx.phase, ctx.cells, ctx.p)

    def outer(ctx, source_binding, completed):
        initialize(ctx)

    cap.code, cap.caller = dispatch.__code__, initialize.__code__
    monkeypatch.setattr(reference.lifecycle.setup, "reinitialize_owners", outer)
    if fail_capture:

        def broken_contracts(actual):
            raise TypeError("synthetic profile capture failure")

        monkeypatch.setattr(reference, "runtime_contracts", broken_contracts)
    else:
        monkeypatch.setattr(reference, "runtime_contracts", lambda actual: contracts())
    return cap, lambda: outer(ctx, binding, completed), primary, cause


def marker(cap):
    cap.stage(
        "kinetic_reload_complete",
        dict(
            source_binding_identity=cap.binding.identity,
            source_complete_INIT_identity=cap.completed.identity,
            capture_complete=True,
            normal_exit=True,
            identity="synthetic-closed-marker-no-admission",
        ),
    )


def test_actual_profiled_synthetic_boundary_preserves_graph_and_profiler_without_parent_credit(
    monkeypatch, tmp_path
):
    cap, invoke, _, _ = profiled_capture(monkeypatch)
    prior = sys.getprofile()
    with cap:
        invoke()
        marker(cap)
    assert sys.getprofile() is prior
    data = cap.finish()
    assert data["entries"] == data["return_or_unwind_events"] == 1
    assert data["before"] != data["after"] and data["capture_errors"] == []
    save_control(tmp_path / "profiled-boundary", data)


@pytest.mark.parametrize("capture_failure", [False, True])
def test_profiled_unwind_keeps_original_exception_cause_and_incomplete_capture(
    monkeypatch, tmp_path, capture_failure
):
    cap, invoke, primary, cause = profiled_capture(
        monkeypatch, fail_source=True, fail_capture=capture_failure
    )
    prior = sys.getprofile()
    with pytest.raises(OSError) as caught, cap:
        invoke()
    assert caught.value is primary and primary.__cause__ is cause
    assert sys.getprofile() is prior and cap.restored and cap.normal_exit is False
    assert bool(cap.errors) is capture_failure
    with pytest.raises(ValueError, match="incomplete actual"):
        cap.finish()
    save_control(
        tmp_path / "profiled-failure",
        dict(
            capture=cap.data(),
            primary=dict(type=type(primary).__name__, message=str(primary), cause=str(cause)),
        ),
    )


def test_source_success_with_profile_capture_error_never_becomes_positive_comparison(
    monkeypatch, tmp_path
):
    cap, invoke, _, _ = profiled_capture(monkeypatch, fail_capture=True)
    with cap:
        invoke()
        marker(cap)
    assert cap.normal_exit and cap.errors
    with pytest.raises(ValueError, match="incomplete actual"):
        cap.finish()
    save_control(tmp_path / "returned-incomplete", cap.data())


@pytest.mark.parametrize(
    "fault", ["duplicate", "no-marker", "foreign-marker", "duplicate-marker", "profiler"]
)
def test_profiled_capture_rejects_missing_duplicate_foreign_or_restoration_conditions(
    monkeypatch, fault
):
    cap, invoke, _, _ = profiled_capture(monkeypatch)
    prior = sys.getprofile()
    with cap:
        invoke()
        if fault == "duplicate":
            invoke()
        elif fault == "foreign-marker":
            with pytest.raises(ValueError, match="Foreign"):
                cap.stage("kinetic_reload_complete", dict(source_binding_identity="foreign"))
        elif fault == "duplicate-marker":
            marker(cap)
            with pytest.raises(ValueError, match="duplicate"):
                marker(cap)
        elif fault == "profiler":
            marker(cap)
            sys.setprofile(prior)
    assert sys.getprofile() is prior
    with pytest.raises(ValueError, match="incomplete actual"):
        cap.finish()


def test_reader_failure_is_incomplete_even_with_written_archive_and_original_primary(
    monkeypatch, tmp_path
):
    primary, cause = OSError("synthetic source"), KeyError("synthetic source cause")
    attempts = []

    def operation():
        raise primary from cause

    def broken_reader():
        raise TypeError("synthetic reader")

    with pytest.raises(OSError) as caught:
        reference.retention._take(
            tmp_path,
            "retained",
            operation,
            attempts=attempts,
            work="synthetic only",
            readers=dict(owner=broken_reader),
        )
    assert caught.value is primary and primary.__cause__ is cause
    row = attempts[0]
    assert row["archive_written"] is True and row["capture_complete"] is False
    assert row["evidence_complete"] is False and row["capture_errors"]


@pytest.mark.parametrize("change", ["type", "value"])
def test_graph_metadata_boolean_or_header_tamper_is_not_equal(change):
    graph = capture(roots())
    other = copy.deepcopy(graph)
    if change == "type":
        next(n for n in other["nodes"] if n.get("kind") == "array")["layout"]["writable"] = 1
    else:
        next(n for n in other["nodes"] if n.get("kind") == "array")["layout"]["dtype"] = "<f4"
    with pytest.raises(native.GraphRejected) as caught:
        native.compare_graphs(graph, other)
    assert caught.value.partial["complete_match"] is False
    assert "layout" in caught.value.partial["difference"]["path"]


def test_copied_lookup_retains_the_same_mutable_axis_backing():
    value = roots()
    axes = ["Na", "K"]
    value["ion_ids"] = axes

    def uncalled_source(name):
        raise AssertionError("Source callback must not execute during graph copy")

    value["sim"].get_ion = uncalled_source
    spec = contracts()
    spec["functions"][id(uncalled_source)] = dict(kind="get_ion", ion_ids=axes)
    graph = native.Graph(api=SimpleNamespace(classes={"Molecule": SyntheticOriginal}), **spec)
    _, copied = graph.capture(value)
    copied["ion_ids"].reverse()
    assert copied["sim"].get_ion("Na") == 1
    assert value["ion_ids"] == ["Na", "K"]


def inspection_context():
    """Unowned source-code/closure metadata only; no callback invocation."""
    module = reference.lifecycle.catalog.base
    code = next(
        c
        for c in reference._nested(module.augment)
        if c.co_name == "<lambda>" and c.co_freevars == ("ion_ids",)
    )
    axes = ["Na", "K"]
    lookup = FunctionType(code, vars(module), closure=(CellType(axes),))
    sim = SimpleNamespace(get_ion=lookup, molecules=None, grn=None)
    p, cells = SimpleNamespace(), SimpleNamespace()
    phase = SimpleNamespace(sim=sim, p=p, cells=cells)
    views = {
        r: SimpleNamespace(sim=sim, p=p, cells=cells, phase=phase) for r in reference.kinetics.ROLES
    }
    return SimpleNamespace(
        sim=sim,
        p=p,
        cells=cells,
        phase=phase,
        views=views,
        ion_ids=axes,
        enabled={r: False for r in reference.kinetics.ROLES},
    )


def test_inspection_binds_lookup_axis_owner_without_calling_or_admitting_it():
    ctx = inspection_context()
    data = reference.runtime_contracts(ctx)
    assert data["functions"][id(ctx.sim.get_ion)]["ion_ids"] is ctx.ion_ids
    assert data["aliases"] == {}


@pytest.mark.parametrize(
    "fault",
    [
        "equal-axis-copy",
        "getter-default",
        "foreign-code",
        "view-sim",
        "view-p",
        "view-cells",
        "view-phase",
    ],
)
def test_missing_lookup_or_view_authority_refuses_before_reconstruction(fault):
    ctx = inspection_context()
    if fault == "equal-axis-copy":
        ctx.ion_ids = list(ctx.ion_ids)
    elif fault == "getter-default":
        ctx.sim.get_ion.__defaults__ = ("Na",)
    elif fault == "foreign-code":
        ctx.sim.get_ion = lambda name: 0
    else:
        setattr(ctx.views["molecules"], fault.removeprefix("view-"), SimpleNamespace())
    with pytest.raises(ValueError, match="authority|association"):
        reference.runtime_contracts(ctx)


def test_array_subclass_refuses_before_custom_copy_or_lost_private_state():
    class ForeignArray(np.ndarray):
        def copy(self, *a, **kw):
            raise AssertionError("Unowned array method must not execute")

    value = roots()
    value["raw"]["array"] = np.arange(2.0).view(ForeignArray)
    with pytest.raises(native.GraphRejected, match="array category"):
        capture(value)


@pytest.mark.parametrize("kind", ["array", "scalar"])
def test_structured_dtype_cannot_collapse_to_an_opaque_void_width(kind):
    value = roots()
    structured = np.array([(1, 2)], dtype=[("first", "i4"), ("second", "i4")])
    value["raw"]["structured"] = structured if kind == "array" else structured[0]
    with pytest.raises(native.GraphRejected, match="array dtype|scalar category/dtype"):
        capture(value)


def graph_copy(value):
    graph = native.Graph(
        api=SimpleNamespace(classes={"Molecule": SyntheticMolecule}), **contracts()
    )
    before, copied = graph.capture(value)
    after = capture(copied)
    native.compare_graphs(before, after)
    return graph, before, copied, after


@pytest.mark.parametrize(
    "mode",
    [
        "owned",
        "flat-base",
        "Fortran",
        "immutable-bytes",
        "bytearray",
        "readonly-parent",
        "readonly-view",
    ],
)
def test_real_shaped_GJ_columns_keep_storage_base_offset_stride_and_mutations(mode, tmp_path):
    flat = np.arange(12.0)
    if mode == "flat-base":
        matrix = flat.reshape(6, 2)
    elif mode == "Fortran":
        matrix = np.asfortranarray(flat.reshape(6, 2))
    elif mode == "immutable-bytes":
        matrix = np.frombuffer(flat.tobytes(), dtype=np.float64).reshape(6, 2)
    elif mode == "bytearray":
        matrix = np.ndarray((6, 2), dtype=np.float64, buffer=bytearray(flat.tobytes()))
    else:
        matrix = flat.reshape(6, 2).copy()
    x, y = matrix[:, 0], matrix[:, 1]
    if mode == "readonly-parent":
        matrix.setflags(write=False)
    elif mode == "readonly-view":
        x.setflags(write=False)
    value = roots()
    value["sim"].E_gj_x, value["sim"].E_gj_y = x, y
    value["sim"].same_x = x
    value["raw"]["arrays_10"] = matrix
    graph, before, copied, after = graph_copy(value)
    cx, cy, cm = copied["sim"].E_gj_x, copied["sim"].E_gj_y, copied["raw"]["arrays_10"]
    for source, actual in ((x, cx), (y, cy), (matrix, cm)):
        assert native._array_layout(source) == native._array_layout(actual)
        assert (
            actual.base is graph.copies[id(source.base)]
            if source.base is not None
            else actual.base is None
        )
        assert source.tobytes() == actual.tobytes()
    assert cx is copied["sim"].same_x
    assert np.shares_memory(cx, cm) and np.shares_memory(cy, cm)
    assert cx.base is cy.base
    original_bytes = matrix.tobytes()
    if cx.flags.writeable:
        cx[2] = 123.0
        assert cm[2, 0] == 123.0
    if cy.flags.writeable:
        cy[1] = 456.0
        assert cm[1, 1] == 456.0
    assert matrix.tobytes() == original_bytes
    save_control(
        tmp_path / "GJ-shared-storage",
        dict(
            mode=mode,
            before=before,
            after=after,
            unique_storage_bytes=graph.array_bytes,
            storage_nodes=graph.storage_nodes,
        ),
    )


@pytest.mark.parametrize(
    "mode", ["reverse", "zero-stride", "unaligned", "zero-dimensional", "empty"]
)
def test_supported_bounded_views_preserve_exact_layout_and_base(mode):
    owner = np.arange(32, dtype=np.uint8)
    if mode == "reverse":
        view = owner[::-2]
    elif mode == "zero-stride":
        view = np.ndarray((5,), dtype=np.uint8, buffer=owner, strides=(0,))
    elif mode == "unaligned":
        view = np.ndarray((3,), dtype=">f8", buffer=owner, offset=1, strides=(9,))
    elif mode == "zero-dimensional":
        view = np.ndarray((), dtype=np.uint32, buffer=owner, offset=4)
    else:
        view = owner[:0]
    value = roots()
    value["raw"].update(view=view, owner=owner)
    graph, _, copied, _ = graph_copy(value)
    assert copied["raw"]["view"].base is graph.copies[id(view.base)]
    assert native._array_layout(copied["raw"]["view"]) == native._array_layout(view)


@pytest.mark.parametrize(
    "fault", ["alias", "offset", "stride", "writeability", "unused-storage-byte"]
)
def test_equal_logical_view_values_do_not_hide_storage_or_layout_drift(fault, tmp_path):
    def example():
        owner = np.ones((5, 2))
        value = roots()
        value["sim"].E_gj_x = np.ndarray((3,), dtype=np.float64, buffer=owner, strides=(16,))
        value["sim"].E_gj_y = np.ndarray(
            (3,), dtype=np.float64, buffer=owner, offset=8, strides=(16,)
        )
        value["raw"]["owner"] = owner
        return value

    left, right = example(), example()
    owner = right["raw"]["owner"]
    if fault == "alias":
        right["sim"].E_gj_x = np.ndarray((3,), dtype=np.float64, buffer=owner.copy(), strides=(16,))
    elif fault == "offset":
        right["sim"].E_gj_x = np.ndarray(
            (3,), dtype=np.float64, buffer=owner, offset=16, strides=(16,)
        )
    elif fault == "stride":
        right["sim"].E_gj_x = np.ndarray((3,), dtype=np.float64, buffer=owner, strides=(8,))
    elif fault == "writeability":
        right["sim"].E_gj_x.setflags(write=False)
    else:
        owner[-1, -1] = 2.0
    assert np.array_equal(left["sim"].E_gj_x, right["sim"].E_gj_x)
    assert np.array_equal(left["sim"].E_gj_y, right["sim"].E_gj_y)
    before, after = capture(left), capture(right)
    with pytest.raises(native.GraphRejected, match="graph differs") as caught:
        native.compare_graphs(before, after)
    save_control(
        tmp_path / "storage-drift",
        dict(
            fault=fault,
            original=before,
            candidate=after,
            difference=caught.value.partial,
            logical_GJ_values_equal=True,
        ),
    )


def test_shared_storage_is_bounded_and_counted_once(monkeypatch):
    owner = np.arange(16.0)
    value = {name: None for name in native.ROOTS}
    value["sim"] = SimpleNamespace(views=[owner[i % 8 : i % 8 + 8] for i in range(20)])
    value["raw"] = {"owner": owner}
    monkeypatch.setattr(native, "MAX_ARRAY_BYTES", owner.nbytes)
    graph = native.Graph(**contracts())
    _, copied = graph.capture(value)
    assert graph.array_bytes == owner.nbytes and graph.storage_nodes == 1
    assert all(v.base is copied["raw"]["owner"] for v in copied["sim"].views)


@pytest.mark.parametrize(
    "bits",
    [
        "0000000000000000",
        "8000000000000000",
        "3ff8000000000000",
        "0000000000000001",
        "7ff0000000000000",
        "fff0000000000000",
        "7ff8000000000001",
        "7ff8000000000002",
        "fff8000000000001",
        "7ff0000000000001",
    ],
)
def test_python_float_binary64_bits_survive_capture_and_copy(bits, tmp_path):
    number = struct.unpack(">d", bytes.fromhex(bits))[0]
    value = roots()
    value["raw"]["number"] = number
    _, before, copied, after = graph_copy(value)
    assert struct.pack(">d", copied["raw"]["number"]).hex() == bits
    raw_node = next(
        n
        for n in before["nodes"]
        if n.get("kind") == "mapping" and any(k == "number" for k, _ in n["items"])
    )
    token = next(v for k, v in raw_node["items"] if k == "number")
    assert token == dict(scalar="float", encoding="ieee754-binary64-big-endian", value=bits)
    save_control(tmp_path / "binary64", dict(bits=bits, original=before, copied=after))


@pytest.mark.parametrize(
    "left,right",
    [
        ("7ff8000000000001", "7ff8000000000002"),
        ("7ff8000000000001", "fff8000000000001"),
        ("7ff0000000000001", "7ff8000000000001"),
        ("0000000000000000", "8000000000000000"),
    ],
)
def test_nan_payload_sign_and_signed_zero_differences_refuse(left, right):
    a, b = roots(), roots()
    a["raw"]["number"] = struct.unpack(">d", bytes.fromhex(left))[0]
    b["raw"]["number"] = struct.unpack(">d", bytes.fromhex(right))[0]
    with pytest.raises(native.GraphRejected, match="graph differs"):
        native.compare_graphs(capture(a), capture(b))


def test_old_lossy_graph_version_gets_no_repair_credit():
    a = capture(roots())
    b = copy.deepcopy(a)
    a["kind"] = b["kind"] = "cells.kinetic_reference_complete_data_graph@1"
    with pytest.raises(ValueError, match="version required"):
        native.compare_graphs(a, b)
