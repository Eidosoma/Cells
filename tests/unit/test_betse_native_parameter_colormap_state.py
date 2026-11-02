"""Selected-entry data/source records; native imports/evaluators stay blocked."""

import functools
import pickle
import sys
from dataclasses import replace
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_parameter_colormap_state as stage
from tests.unit import test_betse_native_parameter_colormaps as earlier
from validation.betse.betse_native_single_cell_core_synthetic import save

blocked = earlier.blocked


def _module(monkeypatch, tmp_path, name, text):
    path = tmp_path / (name.rsplit(".", 1)[-1] + ".py")
    path.write_text(text)
    module = ModuleType(name)
    module.__file__ = str(path)
    # Conditional declarations only; all defined bodies raise if called.
    exec(compile(text, str(path), "exec", dont_inherit=True), vars(module))
    monkeypatch.setitem(sys.modules, name, module)
    return module


@pytest.fixture
def controlled(monkeypatch, tmp_path):
    h = earlier.controlled.__wrapped__(monkeypatch, tmp_path)
    colors = _module(
        monkeypatch,
        tmp_path,
        "matplotlib.colors",
        (
            "class Colormap:\n    def __init__(self):\n"
            '        raise AssertionError("constructor held")\n'
            "class LinearSegmentedColormap(Colormap):\n    pass\n"
            "class ListedColormap(Colormap):\n    pass\n"
        ),
    )
    curves = _module(
        monkeypatch,
        tmp_path,
        "matplotlib._conditional_curves",
        (
            "SCALE = 1.0\nCOEFFICIENTS = [1.0]\n"
            'def helper(value):\n    raise AssertionError("helper held")\n'
            "def curve(value):\n"
            "    if SCALE and COEFFICIENTS[0]:\n"
            '        raise AssertionError("callback held")\n'
            "    return helper(value)\n"
        ),
    )
    red = object.__new__(colors.LinearSegmentedColormap)
    blue = object.__new__(colors.ListedColormap)
    shared = np.array([[0.0, 0.5], [0.5, 1.0]], dtype=np.float64)
    red.name, red.N, red._isinit = h.names[0], 2, False
    red._segmentdata = dict(
        red=curves.curve,
        green=functools.partial(curves.curve),
        blue=[(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)],
    )
    red.data = shared
    blue.name, blue.N, blue._isinit, blue.colors = h.names[3], 2, False, [(0.0, 0.0, 1.0)]
    blue.data = shared
    h.api.mapping.update({h.names[0]: red, h.names[3]: blue})
    h.api.module.Colormap = colors.Colormap
    h.api.module.LinearSegmentedColormap = colors.LinearSegmentedColormap
    boundary = h.prepare()
    return SimpleNamespace(
        parent=h,
        boundary=boundary,
        colors=colors,
        curves=curves,
        red=red,
        blue=blue,
        shared=shared,
        capture=lambda: stage.capture_registry(boundary, law_id=stage.LAW_ID),
    )


def empty():
    assert not stage._ACTIVE
    earlier.empty()


def test_exact_input_source_and_no_lookup_or_initializer_admission():
    plan = stage.source_plan()
    assert plan["input_producer"] == stage.PREVIOUS_SHA256
    assert plan["selected_registry_only"] and plan["callback_evaluations"] == 0
    assert plan["lookups"] == 0 and not plan["parameter_advanced"]
    assert not plan["returned_objects_owned"] and not plan["native_pickle_or_decode"]
    assert not plan["INIT_admitted"]


def test_source_plan_encoder_producer_is_relocation_stable(monkeypatch, tmp_path):
    before = stage.source_plan()
    assert before["data_encoder"][0] == (
        "src/cells/processes/betse_normal_ecm_molecule_checkpoint_codec.py"
    )
    from pathlib import Path

    original = Path(stage.codec.__file__)
    relocated = tmp_path / "encoder-snapshot.py"
    relocated.write_bytes(original.read_bytes())
    monkeypatch.setattr(stage.codec, "__file__", str(relocated))
    assert stage.source_plan() == before


def test_same_selected_entries_arrays_aliases_and_source_callbacks_without_evaluation(
    controlled, tmp_path
):
    h = controlled
    owner = h.capture()
    record = owner.record
    assert record.array_copies == 1 and record.callback_inspections == 2
    assert record.boundary_identity == h.boundary.binding.identity
    assert [row[-1] for row in record.role_entries] == [True, True, False, True]
    ctx = stage._ISSUED[owner]
    assert sum(value is h.red for value in ctx.capture.objects) == 1
    assert sum(value is h.shared for value in ctx.capture.objects) == 1
    assert len(ctx.capture.encoder.original_arrays) == 1
    assert ctx.capture.encoder.original_arrays[0] is h.shared
    assert h.parent.p is h.parent.owner.parameters and not h.parent.parent.invalid
    assert not any(store in vars(h.parent.p) for store, _, _ in stage.previous.ROLES)
    with pytest.raises(stage.ColormapStateRejected) as caught:
        stage.require_lookup_result(owner)
    assert caught.value.stage == "lookup_return_prerequisite"
    assert owner.record is record
    empty()
    save(
        tmp_path,
        "selected-colormap-registry-state",
        dict(
            record=stage.record_document(record),
            tree=ctx.capture.tree,
            arrays=ctx.capture.arrays,
            source_files=ctx.capture.files,
            actual_native_lookup_constructor_callback_entries=0,
            conditional_module_declarations=True,
            no_parameter_write=True,
            returned_objects_owned=False,
            validation_metadata_work=ctx.validations,
        ),
    )


@pytest.mark.parametrize(
    "drift",
    [
        "data",
        "dtype",
        "alias",
        "field-order",
        "callback-attrs",
        "partial",
        "global",
        "global-shadow",
        "helper-code",
        "code",
        "class-method",
        "source-file",
        "record",
        "saved-array",
        "saved-tree",
    ],
)
def test_current_data_callback_source_alias_and_evidence_drift_refuses(controlled, drift):
    h = controlled
    owner = h.capture()
    assert owner.record.graph_identity
    ctx = stage._ISSUED[owner]
    if drift == "data":
        h.shared[0, 0] = 2.0
    elif drift == "dtype":
        h.red.data = h.shared.astype(np.float32)
    elif drift == "alias":
        h.blue.data = h.shared.copy()
    elif drift == "field-order":
        value = vars(h.red).pop("name")
        h.red.name = value
    elif drift == "callback-attrs":
        h.curves.curve.extra = True
    elif drift == "partial":
        h.red._segmentdata["green"].keywords["foreign"] = 1
    elif drift == "global":
        h.curves.SCALE = 2.0
    elif drift == "global-shadow":
        h.curves.AssertionError = RuntimeError
    elif drift == "code":
        h.curves.curve.__code__ = (lambda x: x).__code__
    elif drift == "helper-code":
        h.curves.helper.__code__ = (lambda x: x).__code__
    elif drift == "class-method":
        h.colors.Colormap.__init__ = lambda self: None
    elif drift == "source-file":
        with open(h.curves.__file__, "a") as stream:
            stream.write("\n# drift\n")
    elif drift == "record":
        ctx.record = replace(ctx.record)
    elif drift == "saved-array":
        ctx.capture.arrays["a00000000"][0, 0] = 3.0
    else:
        ctx.capture.tree["kind"] = "foreign"
    with pytest.raises(stage.ColormapStateRejected) as caught:
        _ = owner.record
    assert caught.value.stage == "drift" and ctx.invalid and not ctx.validating
    assert caught.value.partial is ctx and caught.value.source_error is not None
    empty()


@pytest.mark.parametrize(
    "kind",
    [
        "callable-object",
        "local-closure",
        "foreign-function",
        "writable-view",
        "noncontiguous",
        "object-array",
        "unknown-value",
        "unknown-global",
        "metaclass-equality",
        "class-property",
    ],
)
def test_unsupported_callbacks_arrays_and_objects_refuse_with_partial_evidence(
    controlled, kind, tmp_path
):
    h = controlled
    if kind == "callable-object":

        class Callback:
            def __call__(self, *args):
                raise AssertionError("Arbitrary callback invoked")

        h.red.extra = Callback()
    elif kind == "local-closure":

        def factory():
            original = h.curves.curve
            return lambda value: original(value)

        h.red.extra = factory()
    elif kind == "foreign-function":
        h.red.extra = lambda value: value
    elif kind == "writable-view":
        h.red.data = h.shared[0, :]
    elif kind == "noncontiguous":
        h.red.data = np.arange(12.0).reshape(3, 4)[:, ::2]
    elif kind == "object-array":
        h.red.data = np.array([object()], dtype=object)
    elif kind == "unknown-global":
        h.curves.COEFFICIENTS = object()
    elif kind == "metaclass-equality":

        class Meta(type):
            def __eq__(self, other):
                raise AssertionError("Unknown type equality invoked")

        unknown = Meta("Unknown", (), {})
        h.red.extra = object.__new__(unknown)
    elif kind == "class-property":

        class Unknown:
            @property
            def __class__(self):
                raise AssertionError("Unknown __class__ getter invoked")

        h.red.extra = Unknown()
    else:
        h.red.extra = object()
    with pytest.raises(stage.ColormapStateRejected) as caught:
        h.capture()
    ctx = caught.value.partial
    expected = {
        "callable-object": "Unowned selected colormap state",
        "local-closure": "Unowned callback or factory-local closure",
        "foreign-function": "Callback lacks actual Matplotlib module authority",
        "writable-view": "Writable runtime views have unowned aliasing",
        "noncontiguous": "Noncontiguous runtime views",
        "object-array": "Unowned/object/extended numeric dtype",
        "unknown-value": "Unowned selected colormap state",
        "unknown-global": "Unowned selected colormap state",
        "metaclass-equality": "Unowned selected colormap state",
        "class-property": "Unowned selected colormap state",
    }[kind]
    assert expected in str(caught.value.source_error)
    assert caught.value.source_error is caught.value.__cause__ and ctx.invalid
    assert ctx.partial_capture is not None and ctx.source_error is caught.value.source_error
    assert len(ctx.partial_capture.objects) > 0 and not ctx.active
    empty()
    save(
        tmp_path,
        "selected-colormap-incomplete-diagnostic",
        dict(
            supported_boundary=False,
            case=kind,
            primary=caught.value.source_error,
            work=ctx.work,
            partial_nodes=ctx.partial_capture.encoder.nodes,
            partial_arrays=ctx.partial_capture.encoder.arrays,
            object_count=len(ctx.partial_capture.objects),
            callback_evaluations=0,
            actual_native_entries=0,
            incomplete=True,
            no_success_record=not hasattr(ctx, "record"),
        ),
    )


@pytest.mark.parametrize("storage", ["list", "array"])
def test_mutable_callback_coefficient_payload_is_owned_not_only_its_identity(controlled, storage):
    h = controlled
    if storage == "array":
        h.curves.COEFFICIENTS = np.array([1.0], dtype=np.float64)
    owner = h.capture()
    assert owner.record.callback_inspections == 2
    original = h.curves.COEFFICIENTS
    original[0] = 4.0
    assert h.curves.COEFFICIENTS is original
    with pytest.raises(stage.ColormapStateRejected) as caught:
        _ = owner.record
    assert caught.value.stage == "drift" and stage._ISSUED[owner].invalid
    empty()


@pytest.mark.parametrize("gate", ["law", "none", "dictionary", "record", "unissued", "pickle"])
def test_exact_issued_input_and_no_state_record_promotion(controlled, gate):
    h = controlled
    if gate == "law":
        with pytest.raises(stage.ColormapStateRejected) as caught:
            stage.capture_registry(h.boundary, law_id="foreign")
        assert caught.value.stage == "law"
    elif gate == "pickle":
        owner = h.capture()
        with pytest.raises(TypeError, match="not native persistence"):
            pickle.dumps(owner)
    else:
        value = {
            "none": None,
            "dictionary": {},
            "record": h.boundary.binding,
            "unissued": object.__new__(stage.previous.ColormapBoundary),
        }[gate]
        with pytest.raises(stage.previous.ColormapBoundaryRejected):
            stage.capture_registry(value, law_id=stage.LAW_ID)
    empty()
