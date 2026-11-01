"""Source-blocked multi-cell driver controls; no original source is evaluated."""

import copy
import hashlib
import importlib.abc
import sys
from enum import Enum
from types import SimpleNamespace

import pytest

from validation.betse import native_multi_cell_caller_native as native


@pytest.fixture(autouse=True)
def no_actual_science(monkeypatch):
    attempts = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {
                "cells",
                "betse",
                "numpy",
                "scipy",
                "PIL",
                "jax",
                "jaxlib",
            }:
                attempts.append(fullname)
                raise AssertionError("Actual scientific import forbidden: " + fullname)

    def forbidden(*args, **kwargs):
        raise AssertionError("Actual original-source runtime forbidden")

    blocker = Block()
    sys.meta_path.insert(0, blocker)
    monkeypatch.setattr(native.runtime, "build", forbidden)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
    assert not attempts


@pytest.fixture
def declaration(tmp_path):
    image = tmp_path / "input.bin"
    image.write_bytes(b"image file bytes; decoding stays forbidden")
    raw = dict(
        seed_recipe=dict(
            kind="cells.betse_lattice_seed_recipe@1",
            provenance="synthetic software input",
            lattice_type="SQUARE",
            world_len_m=4e-5,
            cell_radius_m=5e-6,
            lattice_disorder=0.1,
        ),
        seed_stream_before=["MT19937", list(range(624)), 624, 0, 0.0],
        controls=dict(native.CONTROLS),
        image_recipe=dict(
            kind="cells.betse_image_mask_source@1",
            filename=str(image),
            conf_dirname=str(tmp_path),
            image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        ),
    )
    configuration = {
        "world options": {
            "cell height": 1e-5,
            "cell spacing": 2.6e-8,
            "simulate single cell": False,
            "import from svg": None,
            "alpha shape": 0.05,
            "use centers": True,
            "mesh refinement": {
                "refine mesh": False,
                "maximum steps": 2,
                "convergence threshold": 1e-30,
            },
        }
    }
    return raw, configuration, image


@pytest.mark.parametrize("lattice", ["SQUARE", "HEX"])
def test_input_declarations_keep_exact_controls_and_original_file(declaration, lattice):
    raw, conf, image = declaration
    raw["seed_recipe"]["lattice_type"] = lattice
    before = copy.deepcopy((raw, conf))
    declared, copied, path = native.inputs(raw, conf)
    assert (raw, conf) == before and (declared, copied) == before
    assert path == image and declared is not raw and copied is not conf


@pytest.mark.parametrize(
    "field,value",
    [
        ("single_cell", True),
        ("svg_override", True),
        ("refine_mesh", True),
        ("maximum_voronoi_steps", True),
        ("maximum_voronoi_steps", 3),
        ("voronoi_convergence", 1e-20),
        ("use_centroids", False),
        ("alpha_shape", 0.1),
    ],
)
def test_unreleased_native_branch_refuses_before_science(declaration, field, value):
    raw, conf, _ = declaration
    raw["controls"][field] = value
    with pytest.raises(ValueError, match="controls"):
        native.evaluate(raw, conf, "/never/read", record_exception=repr)


@pytest.mark.parametrize(
    "field,value",
    [
        ("world_len_m", 0),
        ("world_len_m", True),
        ("world_len_m", float("nan")),
        ("world_len_m", 1.0),
        ("cell_radius_m", 0),
        ("cell_radius_m", float("inf")),
        ("lattice_disorder", -0.1),
        ("lattice_disorder", 1.1),
        ("lattice_type", "UNKNOWN"),
    ],
)
def test_invalid_lattice_inputs_refuse(declaration, field, value):
    raw, conf, _ = declaration
    raw["seed_recipe"][field] = value
    with pytest.raises(ValueError):
        native.inputs(raw, conf)


@pytest.mark.parametrize("mutation", ["missing", "additional", "branch", "height", "steps_bool"])
def test_configuration_is_closed_and_source_consistent(declaration, mutation):
    raw, conf, _ = declaration
    world = conf["world options"]
    if mutation == "missing":
        del world["cell spacing"]
    elif mutation == "additional":
        conf["general options"] = {"comp grid size": 25}
    elif mutation == "branch":
        world["simulate single cell"] = True
    elif mutation == "height":
        world["cell height"] = False
    else:
        world["mesh refinement"]["maximum steps"] = True
    with pytest.raises(ValueError):
        native.inputs(raw, conf)


@pytest.mark.parametrize(
    "slot,value", [(0, "PCG64"), (1, [0] * 623), (2, True), (2, 625), (3, 2), (4, float("nan"))]
)
def test_complete_mt_state_required(declaration, slot, value):
    raw, conf, _ = declaration
    raw["seed_stream_before"][slot] = value
    with pytest.raises(ValueError, match="MT"):
        native.inputs(raw, conf)


@pytest.mark.parametrize("mutation", ["bytes", "missing", "symlink", "oversize", "field"])
def test_image_identity_refuses_before_decoder(declaration, mutation):
    raw, conf, path = declaration
    if mutation == "bytes":
        path.write_bytes(b"changed")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "symlink":
        linked = path.with_name("link.bin")
        linked.symlink_to(path)
        raw["image_recipe"]["filename"] = str(linked)
    elif mutation == "oversize":
        path.write_bytes(b"x" * (2**20 + 1))
    else:
        raw["image_recipe"]["new_field"] = "unknown"
    with pytest.raises(ValueError):
        native.inputs(raw, conf)


def error_record(error):
    return dict(
        type=type(error).__name__,
        message=str(error),
        cause=None if error.__cause__ is None else str(error.__cause__),
    )


def synthetic_namespace(*, fail=None, observation_failure=None):
    calls = []
    shared = SimpleNamespace(mask=None, caller=None, mesh=None)
    lattice = Enum("CellLatticeType", ("HEX", "SQUARE"))

    class TissuePickerImageMask:
        def __init__(self):
            xpts, ypts = [0.0, 1.0], [0.0, 1.0]
            self.clipping_matrix = [[1.0, 0.0], [0.0, 1.0]]
            self.clipcurve = [[0.0, 0.0], [1.0, 1.0]]
            shared.mask = self
            assert xpts == ypts

    class DECMesh:
        def __init__(self):
            shared.mesh = self
            self.image_mask = None
            self.vcell_verts = [[0.0, 1.0]]
            self.vor_verts = [[0.0, 0.0]]
            self.vor_cents = [[0.5, 0.5]]
            if fail == "constructor":
                raise ValueError("original constructor failure") from RuntimeError(
                    "constructor cause"
                )

        def clip_and_refine(self, mask):
            self.image_mask = mask
            if fail == "clip":
                self.partial = [9, 8]
                raise ValueError("original clip failure") from RuntimeError("clip cause")

    class Cells:
        def __init__(self, p):
            shared.caller = self
            calls.append("constructor")

        def _make_cell_lattice(self, p):
            calls.append("lattice")
            self.clust_xy = [[0.0, 1.0]]

        def make_voronoi(self, phase):
            calls.append("voronoi")
            mask = TissuePickerImageMask()
            self.mesh = DECMesh()
            self.mesh.clip_and_refine(mask)
            self.ecm_verts = self.mesh.vcell_verts
            self.cluster_mask = mask.clipping_matrix
            self.ecm_verts_unique = self.mesh.vor_verts

        def cell_index(self, p):
            calls.append("index")
            self.cell_centres = self.mesh.vor_cents

        def make_world(self, phase):
            phase.die_unless_kind_seed()
            self._make_cell_lattice(phase.p)
            self.make_voronoi(phase)
            self.cell_index(phase.p)

    def stores(p):
        calls.append("stores")
        for key in native.CONTROL_FIELDS:
            setattr(p, key, native.CONTROLS[key])
        p.cell_height = float(p._conf["world options"]["cell height"])

    def capture(value):
        if observation_failure is not None and observation_failure(value):
            raise OSError("synthetic capture failure")
        return copy.deepcopy(value)

    return (
        dict(
            Cells=Cells,
            DECMesh=DECMesh,
            TissuePickerImageMask=TissuePickerImageMask,
            CellLatticeType=lattice,
            store_parameters=stores,
            metadata={},
        ),
        shared,
        calls,
        capture,
    )


def run_synthetic(declaration, *, fail=None, observation_failure=None, **options):
    raw, conf, _ = declaration
    namespace, shared, calls, capture = synthetic_namespace(
        fail=fail, observation_failure=observation_failure
    )
    values = dict(
        capture=capture,
        record_exception=error_record,
        stream=lambda: {"synthetic": True},
        image_unchanged=lambda: True,
        global_unchanged=lambda: True,
        source_unchanged=lambda: True,
        native_root="/not/original/source",
        sites={},
        pins={},
        log_events=[],
    )
    values.update(options)
    return native._execute(namespace, raw, conf, **values), shared, calls


def test_synthetic_full_boundary_preserves_real_objects_and_mask_layout_projection(declaration):
    record, objects, calls = run_synthetic(declaration)
    assert record["status"] == "source_completed" and record["source_error"] is None
    assert record["capture_error"] is None and all(record["aliases"].values())
    assert calls == ["stores", "constructor", "lattice", "voronoi", "index"]
    token = record["mesh_cache"]["image_mask"]
    assert list(token) == [
        "kind",
        "identity",
        "image_identity",
        "xpts_m",
        "ypts_m",
        "clipping_matrix",
        "clipcurve_m",
    ]
    assert token["identity"] is token["image_identity"] is None
    assert token["clipping_matrix"] == objects.mask.clipping_matrix
    assert objects.mesh.image_mask is objects.mask
    assert objects.caller.cluster_mask is objects.mask.clipping_matrix
    assert (
        "mesh" not in record["caller_cache"] and "tissue_default" not in record["parameter_cache"]
    )
    assert [name for name, _ in record["stages"]] == [
        "__init__",
        "_make_cell_lattice",
        "make_voronoi",
        "cell_index",
    ]


@pytest.mark.parametrize("stage", ["constructor", "clip"])
def test_original_partial_constructor_or_clip_failure_and_cause_survive(declaration, stage):
    record, objects, calls = run_synthetic(declaration, fail=stage)
    assert record["status"] == "source_failed"
    assert record["source_error"]["message"] == "original " + stage + " failure"
    assert record["source_error"]["cause"] == stage + " cause"
    assert "index" not in calls and record["mesh_cache"] is not None
    if stage == "constructor":
        assert not hasattr(objects.caller, "mesh")
    else:
        assert objects.mesh.partial == record["mesh_cache"]["partial"] == [9, 8]


def test_capture_failure_stops_at_source_boundary_without_claiming_source_exception(declaration):
    record, objects, calls = run_synthetic(
        declaration, observation_failure=lambda value: type(value) is dict and "clust_xy" in value
    )
    assert record["status"] == "source_failed" and record["source_error"] is None
    assert record["capture_error"]["type"] == "OSError"
    assert calls == ["stores", "constructor", "lattice"]
    assert objects.mesh is None and record["capture_errors"]


@pytest.mark.parametrize("probe", ["image_unchanged", "global_unchanged", "source_unchanged"])
def test_post_source_identity_drift_denies_completed_comparison(declaration, probe):
    record, _, calls = run_synthetic(declaration, **{probe: lambda: False})
    assert calls[-1] == "index" and record["source_body_completed"] is True
    assert record["status"] == "source_failed" and record["failed_stage"] == "final_metadata"


def test_secondary_exception_recorder_failure_retains_original_primary(declaration):
    def record(error):
        raise OSError("recorder failed")

    result, _, _ = run_synthetic(declaration, fail="clip", record_exception=record)
    assert result["status"] == "source_failed"
    saved = result["source_error"]
    assert saved["type"] == "ValueError" and saved["message"] == "original clip failure"
    assert saved["recorder_failed"] is True
    assert saved["chain"][saved["chain"][0]["cause"]]["message"] == "clip cause"
    assert result["capture_error"] is not None


def test_comparison_view_retains_exact_header_and_does_not_modify_forensics(declaration):
    result, _, _ = run_synthetic(declaration)
    before = copy.deepcopy(result)
    selected = native.comparison_record(result)
    assert tuple(selected) == native.NATIVE_FIELDS and result == before
    assert selected["mesh_cache"] is result["mesh_cache"]
    assert "stages" in result and "stages" not in selected


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_body_completed", False),
        ("original_source_unchanged", False),
        ("capture_errors", [{"error": "recording failed"}]),
        ("capture_error", {"type": "OSError"}),
        ("source_error", {"type": "ValueError"}),
        ("image_unchanged", False),
        ("global_random_stream_unchanged", False),
    ],
)
def test_comparison_view_rejects_contradictory_completed_result(declaration, field, value):
    result, _, _ = run_synthetic(declaration)
    result[field] = value
    with pytest.raises(ValueError, match="contradicts"):
        native.comparison_record(result)


def test_failed_comparison_view_does_not_upgrade_partial_result(declaration):
    result, _, _ = run_synthetic(declaration, fail="clip")
    selected = native.comparison_record(result)
    assert selected["status"] == "source_failed"
    assert selected["source_error"] is result["source_error"]


def test_final_source_pin_check_refuses_changed_and_linked_file(tmp_path):
    original = tmp_path / "original.py"
    original.write_bytes(b"original source bytes")
    pins = {"original.py": hashlib.sha256(original.read_bytes()).hexdigest()}
    assert native._source_unchanged(tmp_path, pins)
    original.write_bytes(b"changed source bytes")
    assert not native._source_unchanged(tmp_path, pins)
    original.rename(tmp_path / "linked.py")
    original.symlink_to(tmp_path / "linked.py")
    assert not native._source_unchanged(tmp_path, pins)


def test_outer_trace_and_profile_remain_chained_and_restored(declaration):
    old_trace, old_profile = sys.gettrace(), sys.getprofile()
    events = []

    def tracer(frame, event, arg):
        if frame.f_code.co_name == "cell_index":
            events.append(("trace", event))
        return tracer

    def profiler(frame, event, arg):
        if frame.f_code.co_name == "cell_index":
            events.append(("profile", event))

    try:
        sys.settrace(tracer)
        sys.setprofile(profiler)
        result, _, _ = run_synthetic(declaration)
        assert result["status"] == "source_completed"
        assert sys.gettrace() is tracer and sys.getprofile() is profiler
    finally:
        sys.settrace(old_trace)
        sys.setprofile(old_profile)
    assert ("trace", "call") in events and ("profile", "call") in events


def test_outer_native_guard_rejection_is_not_swallowed(declaration):
    prior = sys.getprofile()

    def guard(frame, event, arg):
        if event == "call" and frame.f_code.co_name == "cell_index":
            raise RuntimeError("outer guard denied entry")

    try:
        sys.setprofile(guard)
        result, _, calls = run_synthetic(declaration)
        assert result["status"] == "source_failed"
        assert result["source_error"]["message"] == "outer guard denied entry"
        assert sys.getprofile() is guard
    finally:
        sys.setprofile(prior)
    assert "index" not in calls


@pytest.mark.parametrize("hook", ["profile", "trace"])
def test_late_capture_guard_rejection_restores_hook_before_later_probe(declaration, hook):
    previous_profile, previous_trace = sys.getprofile(), sys.gettrace()
    seen = []

    def final_stream():
        return {"synthetic": True}

    def guard(frame, event, arg):
        if event == "call":
            if frame.f_code.co_name == "capture" and frame.f_back.f_code.co_name == "<lambda>":
                seen.append("late_capture_refused")
                raise RuntimeError("outer guard denied final capture")
            if frame.f_code is final_stream.__code__:
                seen.append("guarded_stream_probe")
        return guard

    try:
        (sys.setprofile if hook == "profile" else sys.settrace)(guard)
        result, _, calls = run_synthetic(declaration, stream=final_stream)
        assert calls[-1] == "index" and result["source_body_completed"] is True
        assert result["status"] == "source_failed" and result["source_error"] is None
        assert result["capture_error"]["message"] == "outer guard denied final capture"
        assert result["caller_cache"] is None and result["mesh_cache"] is None
        assert seen == [
            "guarded_stream_probe",
            "late_capture_refused",
            "late_capture_refused",
            "guarded_stream_probe",
        ]
        assert (sys.getprofile() if hook == "profile" else sys.gettrace()) is guard
    finally:
        sys.setprofile(previous_profile)
        sys.settrace(previous_trace)
