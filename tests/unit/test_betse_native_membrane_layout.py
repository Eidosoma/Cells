"""Proposed lossless layout/schema controls; static preparation never collects."""

import json
import os
import subprocess
import sys
import traceback
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from cells.processes import betse_native_membrane_layout as layout
from validation.betse import betse_native_membrane_layout_fixtures as fixtures


def serial(value):
    if type(value).__module__ == "numpy" and type(value).__name__ == "ndarray":
        return dict(
            dtype=value.dtype.str,
            shape=list(value.shape),
            strides=list(value.strides),
            object_values=serial(value.tolist()) if value.dtype.kind == "O" else None,
            raw_bytes_hex=None if value.dtype.kind == "O" else value.tobytes(order="C").hex(),
        )
    if isinstance(value, dict):
        return {key: serial(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(child) for child in value]
    return layout.plain(value)


def persist(root, name, value):
    root.mkdir(parents=True, exist_ok=True)
    with (root / (name + ".json")).open("x") as stream:
        json.dump(serial(value), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def begin(root, case, purpose):
    spec = fixtures.specification(case)
    persist(
        root,
        "declared-input",
        dict(specification=spec, purpose=purpose, launch_owner="Chief/Root; static proposal only"),
    )
    return dict(
        specification=spec,
        stage="declared",
        owners=None,
        declaration=None,
        snapshot=None,
        bound=None,
        views=[],
        reference=None,
    )


def failure(root, state, error):
    persist(
        root,
        "failure",
        dict(
            type=type(error).__name__,
            reason=str(error),
            traceback=traceback.format_exc(),
            state=state,
            original=getattr(error, "original", None),
            partial=getattr(error, "partial", None),
        ),
    )


def capture(root, state, mutation=None):
    state["stage"] = "supplied_store_construction"
    owners, declared = fixtures.build(state["specification"], mutation)
    state.update(owners=owners, declaration=declared)
    persist(root, "original-native-shaped-stores", dict(owners=owners, declaration=declared))
    state["stage"] = "capture"
    snapshot = layout.capture_supplied(owners, declared)
    state["snapshot"] = snapshot
    persist(root, "captured-six-column-parent", snapshot)
    return snapshot


def construct(root, state):
    snapshot = capture(root, state)
    state["stage"] = "bind_layout"
    bound = layout.bind_layout(snapshot)
    state["bound"] = bound
    persist(root, "bound-layout", bound)
    for name, conversion, operation in (
        ("midpoint-normal", layout.MIDPOINT_NORMAL_LAW, layout.midpoint_normal_view),
        ("normal-tangent", layout.NORMAL_TANGENT_LAW, layout.normal_tangent_view),
    ):
        state["stage"] = name
        persist(
            root, name + "-conversion-request", dict(parent=bound, opted_in_conversion=conversion)
        )
        view = operation(bound, opted_in_conversion=conversion)
        state["views"].append(view)
        persist(root, name + "-view", view)
    return snapshot, bound, state["views"]


def independent(root, state, payload):
    state["stage"] = "independent_byte_schema_owner_check"
    persist(root, "independent-input", payload)
    path = root / "independent-output.json"
    with (root / "independent.stdout.log").open("x") as stream:
        try:
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_native_membrane_layout_reference",
                    "--input",
                    str(root / "independent-input.json"),
                    "--output",
                    str(path),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=480,
                check=False,
            )
        except Exception as error:
            persist(
                root,
                "independent-process-failure",
                dict(type=type(error).__name__, reason=str(error)),
            )
            raise
        finally:
            stream.flush()
            os.fsync(stream.fileno())
    persist(root, "independent-process", dict(returncode=process.returncode))
    report = json.loads(path.read_text()) if path.is_file() else None
    state["reference"] = report
    if report is None:
        raise RuntimeError("Missing checker output; full input and process log are retained")
    assert process.returncode == (0 if report["passed"] else 1)
    return report


@pytest.mark.parametrize("case", fixtures.CASES)
def test_lossless_native_six_column_schema_and_views(case, tmp_path):
    state = begin(tmp_path, case, "supplied schema values; no native mesh/seed/init claim")
    try:
        original, bound, views = construct(tmp_path, state)
        report = independent(tmp_path, state, dict(original=original, layout=bound, views=views))
        assert report["passed"]
        assert all(value is False for value in bound.gates.values())
        assert all(layout.validate_view(view) is view for view in views)
        assert bound.snapshot is original
        if case == "nonunit-schema-only":
            assert bound.gates["vector_geometry_qualified"] is False
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", fixtures.REFUSALS)
def test_incomplete_changed_or_ambiguous_native_schema_is_refused(name, tmp_path):
    state = begin(tmp_path, fixtures.CASES[0], "declared schema refusal: " + name)
    try:
        original = capture(tmp_path, state, name)
        with pytest.raises(layout.LayoutRejected) as caught:
            layout.bind_layout(original)
        persist(
            tmp_path,
            "expected-refusal",
            dict(
                reason=str(caught.value),
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", fixtures.CORRUPTIONS)
def test_independent_checks_reject_changed_parent_owner_and_views(name, tmp_path):
    state = begin(tmp_path, fixtures.CASES[0], "declared outgoing corruption: " + name)
    try:
        original, bound, views = construct(tmp_path, state)
        payload = layout.plain(dict(original=original, layout=bound, views=views))
        if name == "native-parent-bytes":
            raw = payload["layout"]["snapshot"]["entries"]["mem_vects_flat"]["value"]["raw"]
            raw["bytes_hex"] = raw["bytes_hex"][:-2] + "ff"
        elif name == "owner-cells":
            payload["layout"]["owner_cells"][0] = 1
        elif name == "owner-local":
            payload["layout"]["owner_local_indices"][0] = 2
        elif name == "view-law":
            payload["views"][0]["conversion_law"] = layout.NORMAL_TANGENT_LAW
        elif name == "view-column-map":
            payload["views"][0]["selected_columns"] = [2, 3, 4, 5]
        elif name == "view-bytes":
            raw = payload["views"][0]["values"]["raw"]
            raw["bytes_hex"] = raw["bytes_hex"][:-2] + "ff"
        elif name == "view-units":
            payload["views"][0]["column_units"] = ["1"] * 4
        elif name == "physical-gate":
            payload["layout"]["gates"]["physical_geometry_admitted"] = True
        assert independent(tmp_path, state, payload)["passed"] is False
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", fixtures.RESEALED)
def test_resealed_schema_and_view_requests_are_revalidated(name, tmp_path):
    state = begin(tmp_path, fixtures.CASES[0], "declared resealed control: " + name)
    try:
        original, bound, views = construct(tmp_path, state)
        kwargs = {}
        if name == "snapshot-units":
            declaration = layout.plain(original.declaration)
            declaration["column_units"][0] = "cm"
            changed = replace(original, declaration=layout.freeze(declaration), identity="")
            changed = replace(changed, identity=layout.digest(layout.snapshot_record(changed)))
            operation = layout.bind_layout
        elif name in ("layout-owner", "layout-gates"):
            if name == "layout-owner":
                changed = replace(bound, owner_cells=(1,) + bound.owner_cells[1:], identity="")
            else:
                changed = replace(
                    bound,
                    gates=layout.freeze(dict(bound.gates, physical_geometry_admitted=True)),
                    identity="",
                )
            changed = replace(changed, identity=layout.digest(layout.layout_record(changed)))
            operation = layout.midpoint_normal_view
            kwargs = dict(opted_in_conversion=layout.MIDPOINT_NORMAL_LAW)
        else:
            changed = replace(views[0], selected_columns=(2, 3, 4, 5), identity="")
            changed = replace(changed, identity=layout.digest(layout.view_record(changed)))
            operation = layout.validate_view
        persist(tmp_path, "declared-resealed-input", changed)
        with pytest.raises(layout.LayoutRejected) as caught:
            operation(changed, **kwargs)
        persist(
            tmp_path,
            "expected-refusal",
            dict(
                reason=str(caught.value),
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def test_snapshot_owns_all_six_column_bytes_and_owner_rows(tmp_path):
    state = begin(tmp_path, fixtures.CASES[0], "original caller buffers may change after capture")
    try:
        original = capture(tmp_path, state)
        before = deepcopy(layout.plain(original))
        state["owners"]["mem_vects_flat"][:] = 17.0
        state["owners"]["mem_mids_flat"][:] = 18.0
        state["owners"]["mem_to_cells"][:] = 9
        state["owners"]["cell_to_mems"][0][:] = 19
        persist(tmp_path, "changed-caller-owned-buffers", state["owners"])
        assert layout.plain(original) == before
        bound = layout.bind_layout(original)
        persist(tmp_path, "bound-independent-snapshot", bound)
    except Exception as error:
        failure(tmp_path, state, error)
        raise


def test_native_capture_refuses_unpinned_class_and_retains_snapshot(tmp_path):
    state = begin(tmp_path, fixtures.CASES[0], "supplied lookalike cannot become a native instance")
    try:
        capture(tmp_path, state)
        with pytest.raises(layout.LayoutRejected) as caught:
            layout.capture_native(SimpleNamespace(**state["owners"]), state["declaration"])
        persist(
            tmp_path,
            "expected-native-source-refusal",
            dict(
                reason=str(caught.value),
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
        assert caught.value.original.entries["mem_vects_flat"]["captured"] is True
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", ("midpoint-normal", "normal-tangent"))
def test_conversion_requires_explicit_matching_law(name, tmp_path):
    state = begin(tmp_path, fixtures.CASES[0], "conversion opt-in refusal: " + name)
    try:
        _, bound, _ = construct(tmp_path, state)
        operation = (
            layout.midpoint_normal_view if name == "midpoint-normal" else layout.normal_tangent_view
        )
        persist(
            tmp_path, "wrong-conversion-request", dict(name=name, opted_in_conversion="automatic")
        )
        with pytest.raises(layout.LayoutRejected) as caught:
            operation(bound, opted_in_conversion="automatic")
        persist(
            tmp_path,
            "expected-conversion-refusal",
            dict(
                reason=str(caught.value),
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise


@pytest.mark.parametrize("name", ("layout", "midpoint-normal", "normal-tangent"))
def test_schema_does_not_admit_initialization_or_physical_geometry(name, tmp_path):
    state = begin(tmp_path, fixtures.CASES[0], "continued initialization refusal: " + name)
    try:
        _, bound, views = construct(tmp_path, state)
        value = {"layout": bound, "midpoint-normal": views[0], "normal-tangent": views[1]}[name]
        with pytest.raises(layout.LayoutRejected) as caught:
            layout.require_initialization_handoff(value)
        persist(
            tmp_path,
            "expected-initialization-refusal",
            dict(
                reason=str(caught.value),
                original=caught.value.original,
                partial=caught.value.partial,
            ),
        )
    except Exception as error:
        failure(tmp_path, state, error)
        raise
