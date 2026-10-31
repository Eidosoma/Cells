"""Live-mask authority flow with original decoders/constructors/operators blocked."""

import hashlib
import inspect
import json
import os
import pickle
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_single_cell_image_mask as masks
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_IMAGE_MASK_EVIDENCE", str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def harness(monkeypatch, tmp_path, *, fail=False):
    """Counterfactual ownership/FD controls; no real image is decoded or fitted."""
    monkeypatch.setattr(
        masks.core.initial.streams,
        "native_stream_manifest",
        lambda value: dict(synthetic_stream_metadata=True),
    )
    calls = dict(construct=0, native=[])
    errors = {}
    filename = tmp_path / "synthetic-image-bytes.dat"
    data = b"synthetic input provenance, not a decoded image"
    filename.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    raw = dict(
        bitmap=np.asarray([[0.0, 0.0, 0.0, 0.0]] * 4, dtype=np.float32),
        matrix=np.asarray([[1.0, 1.0, 1.0, 1.0]] * 4),
        x=np.asarray([-1.0, 0.0, 1.0, 2.0]),
        y=np.asarray([-1.0, 0.0, 1.0, 2.0]),
        row=np.asarray([0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3]),
        col=np.asarray([0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3]),
        points=np.asarray(
            [
                [-1.0, -1.0],
                [0.0, -1.0],
                [1.0, -1.0],
                [2.0, -1.0],
                [-1.0, 0.0],
                [0.0, 0.0],
                [1.0, 0.0],
                [2.0, 0.0],
                [-1.0, 1.0],
                [0.0, 1.0],
                [1.0, 1.0],
                [2.0, 1.0],
                [-1.0, 2.0],
                [0.0, 2.0],
                [1.0, 2.0],
                [2.0, 2.0],
            ]
        ),
        vertices=np.asarray([0, 3, 15, 12]),
        curve=np.asarray([[-1.0, -1.0], [2.0, -1.0], [2.0, 2.0], [-1.0, 2.0]]),
        linear_knots=np.asarray([-1.0, -1.0, 0.0, 1.0, 2.0, 2.0]),
        fast_knots=np.asarray([-1.0, -1.0, -1.0, -1.0, 2.0, 2.0, 2.0, 2.0]),
        coefficients=np.asarray([1.0] * 16),
    )
    frozen = masks.images.arrays.frozen
    image = masks.images.ImageSource(
        json.dumps(
            dict(
                kind=masks.images.IMAGE_KIND,
                filename=str(filename),
                conf_dirname=str(tmp_path),
                image_sha256=digest,
            ),
            sort_keys=True,
        ),
        str(filename),
        str(filename.resolve()),
        data,
        digest,
        "F",
        frozen(raw["bitmap"]),
        masks.images.metadata.version("pillow"),
        "",
    )
    image = replace(image, identity=masks.core.records._digest(masks.images.image_record(image)))
    values = masks.images.MaskValues(
        *[
            frozen(value)
            for value in (
                raw["bitmap"],
                raw["matrix"],
                raw["x"],
                raw["y"],
                np.column_stack((raw["row"], raw["col"])),
                raw["points"],
                raw["vertices"],
                raw["curve"],
                raw["linear_knots"],
                raw["linear_knots"],
                raw["coefficients"],
                raw["fast_knots"],
                raw["fast_knots"],
                raw["coefficients"],
            )
        ]
    )
    prelude = masks.images.Prelude(
        "synthetic-binding",
        "synthetic-seed",
        image,
        json.dumps(dict(single_cell=True)),
        None,
        values,
        (),
        {},
        "init_mesh",
        {},
        "",
    )
    prelude = replace(
        prelude, identity=masks.core.records._digest(masks.images.prelude_record(prelude))
    )
    cells = SimpleNamespace(xmin=-1.0, xmax=2.0, ymin=-1.0, ymax=2.0)
    rng = SimpleNamespace(identity="synthetic-same-live-RNG")
    caller_owner = object.__new__(masks.callers.CallerOwner)
    context = dict(
        caller=cells,
        tape=SimpleNamespace(rng=rng),
        trial=SimpleNamespace(identity="synthetic-caller"),
        request=SimpleNamespace(
            core_request=SimpleNamespace(
                initial_request=SimpleNamespace(upstream=(None, None, prelude))
            )
        ),
    )

    def validate_caller(owner):
        if owner is not caller_owner:
            raise masks.callers.CallerRejected(
                "Synthetic caller unavailable", stage="caller_authority_unavailable"
            )
        return context

    class Spline:
        def __init__(self, knots):
            self.tck = (knots.copy(), knots.copy(), raw["coefficients"].copy())

        def get_knots(self):
            return self.tck[:2]

        def get_coeffs(self):
            return self.tck[2]

        def __call__(self, *args):
            calls["native"].append("unexpected spline evaluation")
            raise AssertionError("No spline evaluation is allowed")

    class Mask:
        __reduce_ex__ = masks._serialize_refused

    class Picker:
        __reduce_ex__ = masks._serialize_refused

    def construct(tape, expected, actual_caller):
        calls["construct"] += 1
        calls["received_caller"] = actual_caller
        assert actual_caller is cells
        tape.picker = Picker()
        tape.picker.filename = str(filename)
        tape.mask = Mask()
        tape.mask.msize, tape.mask.clipping_matrix = 4, raw["matrix"]
        fd = os.open(filename, os.O_RDONLY)
        tape.descriptors.append(fd)
        info = os.fstat(fd)
        tape.receipts.append(
            dict(
                filename=str(filename),
                before_sha256=digest,
                device=info.st_dev,
                inode=info.st_ino,
                byte_count=len(data),
                input_mode="F",
            )
        )
        if fail:
            try:
                raise SyntheticSourceCause("retained synthetic image cause")
            except SyntheticSourceCause as cause:
                error = SyntheticSourceFailure("retained synthetic image failure")
                errors["source"], errors["source_cause"] = error, cause
                raise error from cause
        linear, fast = Spline(raw["linear_knots"]), Spline(raw["fast_knots"])

        def function(x, y):
            return linear(x, y).T

        tape.mask.clipping_function = function
        tape.mask.clipping_function_fast = fast
        tape.mask.clipcurve = raw["curve"]
        tape.splines = [linear, fast]
        tape.hull = SimpleNamespace(points=raw["points"], vertices=raw["vertices"])
        tape.locals["TissuePickerImageMask.__init__"] = dict(
            bitmap=raw["bitmap"],
            xpts=raw["x"],
            ypts=raw["y"],
            indsN=(raw["row"], raw["col"]),
            ppts=raw["points"],
            bverts=raw["vertices"],
            bclip=tape.hull,
        )
        tape.events.append(
            dict(method="synthetic-native-mask", kind="return", attributes=vars(tape.mask))
        )
        return tape.picker, tape.mask

    monkeypatch.setattr(masks.callers, "_validate_owner", validate_caller)
    monkeypatch.setattr(masks.core.initial, "_rng_stream", lambda value: value)
    monkeypatch.setattr(masks, "_construct", construct)

    def forbidden(*a, **k):
        calls["native"].append("cache hydration or actual source")
        raise AssertionError("Unexpected native decoder/operator/cache hydration")

    monkeypatch.setattr(masks.core.caches, "plain", forbidden)
    for module, name in (
        (masks.images, "prepare"),
        (masks.callers, "prepare"),
        (masks.core, "prepare"),
        (masks.images.lattice, "generate"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    request = masks.from_caller(caller_owner, law_id=masks.LAW_ID)
    return SimpleNamespace(
        request=request,
        context=context,
        raw=raw,
        filename=filename,
        calls=calls,
        errors=errors,
        Spline=Spline,
        caller_owner=caller_owner,
    )


def execute(h, evidence):
    save(evidence, "request", h.request)
    try:
        owner = masks.prepare(h.request)
    except masks.ImageOwnerRejected as error:
        save(
            evidence,
            "failed",
            dict(
                error=error,
                trial=error.trial,
                partial=error.partial,
                source_error=error.source_error,
                capture_error=error.capture_error,
                calls=h.calls,
            ),
        )
        raise
    save(evidence, "result", dict(trial=owner.trial, calls=h.calls))
    return owner


def test_software_literal_source_and_original_picker_base(evidence):
    pins = masks._verify_sources()
    namespace = masks._namespace(masks._Tape(None))
    assert inspect.isabstract(namespace["TissuePickerABC"])
    assert issubclass(namespace["TissuePickerImage"], namespace["TissuePickerABC"])
    assert not inspect.isabstract(namespace["TissuePickerImage"])
    save(evidence, "literal-source", pins)


@pytest.mark.parametrize("value", [None, {}, {"mask": True}, SimpleNamespace()])
def test_software_absent_or_inspection_caller_refuses(value, evidence):
    with pytest.raises(masks.callers.CallerRejected) as caught:
        masks.from_caller(value, law_id=masks.LAW_ID)
    assert caught.value.stage == "caller_authority_unavailable"
    save(evidence, "refused", caught.value)


def test_software_live_objects_aliases_and_descriptor_provenance(monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    owner = execute(h, evidence)
    mask = owner.mask
    value = masks._authority(owner)
    assert h.calls["received_caller"] is value["caller"] is h.context["caller"]
    assert value["rng"] is h.context["tape"].rng
    assert mask.clipping_matrix is h.raw["matrix"]
    assert mask.clipcurve is h.raw["curve"]
    assert masks._linear(mask) is value["tape"].splines[0]
    assert mask.clipping_function_fast is value["tape"].splines[1]
    assert owner.trial.source_completed and len(owner.trial.input_receipts) == 1
    assert (
        owner.trial.input_receipts[0]["before_sha256"]
        == owner.trial.input_receipts[0]["after_sha256"]
    )
    assert not masks.trial_record(owner.trial)["full_caller_continuation_admitted"]
    assert len(masks.INVALIDATED_OWNERS) == 11
    for target in (owner, mask, value["tape"].picker):
        with pytest.raises(TypeError, match="serialized"):
            pickle.dumps(target)
    assert h.calls["construct"] == 1 and h.calls["native"] == []


@pytest.mark.parametrize(
    "change",
    [
        "matrix",
        "equal-matrix",
        "curve",
        "fast",
        "linear",
        "knots",
        "hull",
        "caller",
        "RNG",
        "RNG-epoch",
        "filename",
        "file-bytes",
        "event",
        "producer",
        "trial",
    ],
)
def test_software_stale_image_authority_refuses(change, monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    owner = execute(h, evidence)
    mask = owner.mask
    value = masks._authority(owner)
    tape = value["tape"]
    if change == "matrix":
        mask.clipping_matrix[0, 0] = 9.0
    elif change == "equal-matrix":
        mask.clipping_matrix = mask.clipping_matrix.copy()
    elif change == "curve":
        mask.clipcurve = mask.clipcurve.copy()
    elif change == "fast":
        mask.clipping_function_fast = h.Spline(h.raw["fast_knots"])
        tape.splines[1] = mask.clipping_function_fast
    elif change == "linear":
        replacement = h.Spline(h.raw["linear_knots"])
        mask.clipping_function.__closure__[0].cell_contents = replacement
        tape.splines[0] = replacement
    elif change == "knots":
        tape.splines[0].tck[0][0] = 7.0
    elif change == "hull":
        tape.hull.vertices = tape.hull.vertices.copy()
    elif change == "caller":
        h.context["caller"] = SimpleNamespace(**vars(h.context["caller"]))
    elif change == "RNG":
        h.context["tape"].rng = SimpleNamespace(identity=value["rng"].identity)
    elif change == "RNG-epoch":
        value["rng"].identity = "changed"
    elif change == "filename":
        tape.picker.filename = "changed"
    elif change == "file-bytes":
        h.filename.write_bytes(b"changed source input")
    elif change == "event":
        tape.events[0]["kind"] = "changed"
    elif change == "producer":
        monkeypatch.setattr(masks, "_verify_sources", lambda: {"changed": "source"})
    else:
        object.__setattr__(owner.trial, "source_completed", False)
    with pytest.raises(masks.ImageOwnerRejected) as caught:
        _ = owner.mask
    assert caught.value.stage == "image_authority_drift"
    assert h.calls["construct"] == 1 and h.calls["native"] == []
    save(evidence, "drift", dict(error=caught.value, calls=h.calls))


def test_software_raw_failure_keeps_original_cause_and_partial_mask(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path, fail=True)
    existing = frozenset(masks._ISSUED)
    with pytest.raises(masks.ImageOwnerRejected) as caught:
        execute(h, evidence)
    error = caught.value
    assert error.source_error is h.errors["source"] and error.__cause__ is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["source_cause"]
    assert error.trial is not None and not error.trial.source_completed
    assert error.partial["tape"].mask.clipping_matrix is h.raw["matrix"]
    assert not error.partial["usable_live_owner_available"]
    assert frozenset(masks._ISSUED) == existing and h.calls["native"] == []


@pytest.mark.parametrize("point", ["audit", "Trial", "identity", "issuance"])
def test_software_sealing_failure_keeps_raw_source(point, monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path)
    error = SyntheticCaptureFailure("injected mask capture failure")

    def fail(*a, **k):
        raise error

    if point == "audit":
        monkeypatch.setattr(masks, "_audit", fail)
    elif point == "Trial":
        monkeypatch.setattr(masks, "Trial", fail)
    elif point == "identity":
        monkeypatch.setattr(masks, "trial_record", fail)
    else:
        monkeypatch.setattr(masks, "_graph", fail)
    with pytest.raises(masks.ImageOwnerRejected) as caught:
        execute(h, evidence)
    value = caught.value
    assert value.capture_error is error and value.source_error is None and value.__cause__ is error
    assert value.partial["tape"].mask.clipping_matrix is h.raw["matrix"]
    assert not value.partial["usable_live_owner_available"] and h.calls["native"] == []


def test_software_secondary_capture_error_keeps_primary_failure(monkeypatch, tmp_path, evidence):
    h = harness(monkeypatch, tmp_path, fail=True)
    original = masks._Tape.finish_inputs
    secondary = SyntheticCaptureFailure("descriptor capture failure")

    def finish(self):
        original(self)
        raise secondary

    monkeypatch.setattr(masks._Tape, "finish_inputs", finish)
    with pytest.raises(masks.ImageOwnerRejected) as caught:
        execute(h, evidence)
    value = caught.value
    assert value.source_error is h.errors["source"] and value.capture_error is secondary
    assert value.__cause__ is value.source_error
    assert value.source_error.__cause__ is h.errors["source_cause"]
    assert not value.partial["usable_live_owner_available"] and h.calls["native"] == []


def test_software_caller_tail_requires_real_mesh_order_RNG_and_height(
    monkeypatch, tmp_path, evidence
):
    h = harness(monkeypatch, tmp_path)
    owner = execute(h, evidence)
    for mesh in (None, {"same_epoch": True}):
        with pytest.raises(masks.ImageOwnerRejected) as caught:
            masks.require_caller_continuation(
                owner, mesh_owner=mesh, parameter_owner={"cell_height": 1.0}
            )
        assert caught.value.stage == "caller_mesh_parameter_authority_unavailable"
        assert caught.value.partial["equal_epochs_are_not_shared_RNG_identity"]
        assert caught.value.partial["complete_mesh_is_not_in_caller_init_order"]
    assert h.calls["construct"] == 1 and h.calls["native"] == []


def test_software_forged_mask_owner_refuses(evidence):
    owner = object.__new__(masks.ImageOwner)
    with pytest.raises(masks.ImageOwnerRejected) as caught:
        _ = owner.mask
    assert caught.value.stage == "image_authority_unavailable"
    save(evidence, "forged", caught.value)
