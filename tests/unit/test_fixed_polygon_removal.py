"""Held polygon-removal panel; Chief coordinates scientific execution."""

import json
import os
import struct
import subprocess
import sys
import traceback
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from cells.processes import conservative_polygon_geometry as geometry
from cells.processes import fixed_polygon_removal as removal
from validation.geometry import fixed_polygon_removal_fixtures as fixtures
from validation.geometry import fixed_polygon_removal_reference as reference


@pytest.fixture(autouse=True)
def require_scientific_release(request):
    if request.node.originalname.startswith("test_software_"):
        return
    if os.environ.get("CELLS_FIXED_POLYGON_REMOVAL_SCIENTIFIC_RELEASE") != "1":
        pytest.skip(
            "Held polygon numerical checks; set "
            "CELLS_FIXED_POLYGON_REMOVAL_SCIENTIFIC_RELEASE=1 after scientific release"
        )


def save(name, value):
    root = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "fixed-polygon-removal"
    root.mkdir(parents=True, exist_ok=True)
    path = root / (name + ".json")
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return path


def failed(error):
    return dict(
        type=type(error).__module__ + "." + type(error).__qualname__,
        message=str(error),
        code=getattr(error, "code", None),
        stage=getattr(error, "stage", None),
        trial=removal.capture(getattr(error, "trial", None)),
        available_stdout=removal.capture(getattr(error, "stdout", None)),
        available_stderr=removal.capture(getattr(error, "stderr", None)),
        traceback="".join(traceback.format_exception(error)),
    )


@contextmanager
def evidence(name, inputs):
    state = dict(inputs=inputs)
    save(name + "-input", removal.capture(state))
    try:
        yield state
    except BaseException as error:
        save(name + "-failure", dict(available=removal.capture(state), failure=failed(error)))
        raise
    else:
        save(name + "-result", dict(status="passed", available=removal.capture(state)))


def bind_parent(raw, state):
    state["parent_request"] = geometry.from_polygons(raw, law_id=geometry.LAW_ID)
    state["parent_binding"] = geometry.prepare(state["parent_request"])
    return state["parent_request"], state["parent_binding"]


def fresh_reference(name, request):
    source = save(
        name + "-reference-input",
        dict(parent_declaration=request.parent_request.declaration, removal=request.declaration),
    )
    target = source.with_name(name + "-reference-result.json")
    completed = None
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(Path(reference.__file__).resolve()),
                str(source),
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=dict(os.environ),
        )
        save(
            name + "-reference-process",
            dict(
                command=completed.args,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                result_exists=target.exists(),
            ),
        )
        assert completed.returncode == 0, completed.stderr
        result = json.loads(target.read_text())
        assert result["status"] == "passed"
        return result["result"]
    except BaseException as error:
        save(
            name + "-reference-failure",
            dict(
                failure=failed(error),
                process_returned=completed is not None,
                result_exists=target.exists(),
            ),
        )
        raise


def compare_reference(request, binding, expected):
    report = binding.report
    assert report["axes"]["cell"]["after_ids"] == expected["surviving_cell_ids"]
    assert [r["id"] for r in report["axes"]["cell"]["removed_records"]] == expected[
        "removed_cell_ids"
    ]
    assert {r["membrane_id"] for r in report["exposed_faces"]} == {
        r["membrane_id"] for r in expected["exposed_faces"]
    }
    before = request.parent_binding.geometry
    assert expected["area_balance"]["residual"] == dict(numerator="0", denominator="1")
    assert not report["physical_model_prepared"]
    assert not report["ordinary_continuation_admitted"]
    assert report["native_invalidated_owners"] == list(removal.NATIVE_INVALIDATED_OWNERS)
    for axis in report["axes"].values():
        for new_index, old_index in enumerate(axis["new_to_old"]):
            assert axis["before_ids"][old_index] == axis["after_ids"][new_index]
            assert axis["old_to_new"][old_index] == new_index
    for row in before["cells"]:
        assert row["certificates"]["area"]["exact"] == expected["cell_area_m2"][row["id"]]
        assert row["certificates"]["volume"]["exact"] == expected["cell_volume_m3"][row["id"]]
    if binding.child_binding is None:
        assert not expected["surviving_cell_ids"]
        assert binding.child_request is None
        assert report["axes"]["bath"]["after_ids"] == [r["id"] for r in before["baths"]]
        return
    after = binding.child_binding.geometry
    parent_vertices = {r["id"]: r for r in before["vertices"]}
    parent_membranes = {r["id"]: r for r in before["membranes"]}
    for row in after["vertices"]:
        assert removal.capture(row) == removal.capture(parent_vertices[row["id"]])
    for row in after["cells"]:
        assert row["certificates"]["area"]["exact"] == expected["cell_area_m2"][row["id"]]
        assert row["certificates"]["volume"]["exact"] == expected["cell_volume_m3"][row["id"]]
    for row in after["membranes"]:
        for key in ("area_m2", "thickness_m", "normal_xy", "tangent_xy", "vertex_ids"):
            assert removal.capture(row[key]) == removal.capture(parent_membranes[row["id"]][key])
    assert not expected["unused_bath_ids"]
    assert {r["id"] for r in after["membranes"]} == {r["id"] for r in expected["membranes"]}
    assert {r["id"] for r in after["contacts"]} == set(expected["contact_ids"])
    membranes = {r["id"]: r for r in after["membranes"]}
    for row in expected["membranes"]:
        actual = membranes[row["id"]]
        for key in ("cell_id", "edge_id", "bath_id", "vertex_ids"):
            assert actual[key] == row[key]
        if row["exposed"]:
            assert actual["partner_id"] == actual["id"]
    edges = {r["id"]: r for r in after["edges"]}
    for row in expected["edges"]:
        actual = edges[row["id"]]
        assert actual["vertex_ids"] == row["vertex_ids"]
        assert set(actual["cell_ids"]) == set(row["cell_ids"])
        assert actual["certificates"]["length"]["radicand"] == row["squared_length_m2"]
    for contact in after["contacts"]:
        a, b = (membranes[name] for name in contact["membrane_ids"])
        assert (a["partner_id"], b["partner_id"]) == (b["id"], a["id"])
        assert a["normal_xy"] == [-v for v in b["normal_xy"]]
        assert a["area_m2"] == b["area_m2"] == contact["area_m2"]
    assert after["baths"] == before["baths"]
    assert not report["physical_model_prepared"]
    assert not report["ordinary_continuation_admitted"]
    assert report["native_invalidated_owners"] == list(removal.NATIVE_INVALIDATED_OWNERS)


@pytest.mark.parametrize(
    "case",
    [
        "triangle-contact",
        "grid-corner",
        "merged-cell",
        "disconnected-island",
        "two-bath-exposed",
        "all-cells",
        "empty-selection",
        "merged-all-cells",
    ],
)
def test_positive_owned_geometry(case):
    raw, selected = fixtures.case(case)
    with evidence(case, dict(parent=raw, removed_cell_ids=selected)) as state:
        parent_request, parent_binding = bind_parent(raw, state)
        state["declaration"] = fixtures.removal(parent_binding.geometry, selected)
        state["request"] = removal.from_parent(
            parent_request, parent_binding, state["declaration"], law_id=removal.LAW_ID
        )
        state["binding"] = removal.prepare(state["request"])
        state["reference"] = fresh_reference(case, state["request"])
        compare_reference(state["request"], state["binding"], state["reference"])
        removal.validate_binding(state["request"], state["binding"])
        if not selected:
            assert state["binding"].child_request is parent_request
            assert state["binding"].child_binding is parent_binding
        assert state["parent_binding"].geometry == parent_binding.geometry


def test_sequential_removal():
    raw, _ = fixtures.case("grid-corner")
    with evidence("sequential", dict(parent=raw)) as state:
        parent_request, parent_binding = bind_parent(raw, state)
        for index, selected in enumerate((["physical-s-1-1"], ["physical-s-0-1"])):
            declaration = fixtures.removal(parent_binding.geometry, selected)
            request = removal.from_parent(
                parent_request, parent_binding, declaration, law_id=removal.LAW_ID
            )
            binding = removal.prepare(request)
            state[str(index)] = dict(request=request, binding=binding)
            expected = fresh_reference("sequential-" + str(index), request)
            compare_reference(request, binding, expected)
            parent_request, parent_binding = binding.child_request, binding.child_binding
        assert len(parent_binding.geometry["cells"]) == 2


@pytest.mark.parametrize(
    "case",
    [
        "wrong-law",
        "duplicate-cell",
        "unknown-cell",
        "source-id-instead-physical",
        "missing-bath",
        "extra-bath",
        "unknown-bath",
        "unused-bath",
        "duplicate-bath",
        "point-touch-survivors",
        "all-removed-extra-bath",
    ],
)
def test_invalid_request(case):
    raw, selected = fixtures.case(
        "two-bath-exposed" if case == "unused-bath" else "triangle-contact"
    )
    if case == "point-touch-survivors":
        raw, _ = fixtures.case("grid-corner")
        selected = ["physical-s-0-0", "physical-s-1-1"]
    if case == "all-removed-extra-bath":
        raw, selected = fixtures.case("all-cells")
    with evidence("refusal-" + case, dict(parent=raw)) as state:
        parent_request, parent_binding = bind_parent(raw, state)
        declaration = fixtures.removal(
            parent_binding.geometry,
            selected,
            bath_override="outer" if case == "unused-bath" else None,
        )
        law = removal.LAW_ID
        if case == "wrong-law":
            law = "native_DEC_cut@1"
        elif case == "duplicate-cell":
            declaration["removed_cell_ids"] *= 2
        elif case == "unknown-cell":
            declaration["removed_cell_ids"] = ["absent-cell"]
        elif case == "source-id-instead-physical":
            declaration["removed_cell_ids"] = ["s1"]
        elif case == "missing-bath":
            declaration["exposed_baths"] = []
        elif case in ("extra-bath", "all-removed-extra-bath"):
            existing = {r["membrane_id"] for r in declaration["exposed_baths"]}
            mid = next(
                r["id"] for r in parent_binding.geometry["membranes"] if r["id"] not in existing
            )
            declaration["exposed_baths"].append(dict(membrane_id=mid, bath_id="bath"))
        elif case == "unknown-bath":
            declaration["exposed_baths"][0]["bath_id"] = "invented-bath"
        elif case == "duplicate-bath":
            declaration["exposed_baths"] *= 2
        state["declaration"] = declaration
        with pytest.raises(removal.RemovalRejected) as caught:
            state["request"] = removal.from_parent(
                parent_request, parent_binding, declaration, law_id=law
            )
            state["binding"] = removal.prepare(state["request"])
        state["expected_refusal"] = failed(caught.value)
        assert caught.value.trial
        if case == "point-touch-survivors":
            assert "nonmanifold_boundary_vertex" in json.dumps(caught.value.trial)
        if case == "unused-bath":
            assert caught.value.trial["child_declaration"] is not None
            assert caught.value.trial["returned_child_request"] is not None
            assert "unused_or_unknown_bath" in json.dumps(caught.value.trial)


@pytest.mark.parametrize(
    "case",
    [
        "parent-request",
        "parent-binding",
        "removal-identity",
        "result-report",
        "child-pair",
        "child-request-owner",
        "generated-parent",
    ],
)
def test_parent_and_result_corruption(case):
    raw, selected = fixtures.case("triangle-contact")
    with evidence("corruption-" + case, dict(parent=raw)) as state:
        parent_request, parent_binding = bind_parent(raw, state)
        declaration = fixtures.removal(parent_binding.geometry, selected)
        request = removal.from_parent(
            parent_request, parent_binding, declaration, law_id=removal.LAW_ID
        )
        state["request"] = request
        binding = removal.prepare(request)
        state["binding"] = binding
        with pytest.raises(removal.RemovalRejected) as caught:
            if case == "parent-request":
                removal.from_parent(
                    replace(parent_request, identity="0" * 64),
                    parent_binding,
                    declaration,
                    law_id=removal.LAW_ID,
                )
            elif case == "parent-binding":
                removal.from_parent(
                    parent_request,
                    replace(parent_binding, request_identity="0" * 64),
                    declaration,
                    law_id=removal.LAW_ID,
                )
            elif case == "generated-parent":
                generated = parent_request.declaration
                generated["source"]["kind"] = "owned_stable_initial_dual_mesh@1"
                removal.from_parent(
                    replace(parent_request, declaration_json=json.dumps(generated)),
                    parent_binding,
                    declaration,
                    law_id=removal.LAW_ID,
                )
            elif case == "removal-identity":
                removal.prepare(replace(request, identity="0" * 64))
            elif case == "result-report":
                changed = binding.report
                changed["physical_model_prepared"] = True
                removal.validate_binding(request, replace(binding, report_json=json.dumps(changed)))
            elif case == "child-pair":
                removal.validate_binding(request, replace(binding, child_request=None))
            else:
                child = replace(binding.child_binding, request_identity="0" * 64)
                removal.validate_binding(request, replace(binding, child_binding=child))
        state["expected_refusal"] = failed(caught.value)
        assert caught.value.trial


def test_late_refusal_retains_returned_trial(monkeypatch):
    raw, selected = fixtures.case("triangle-contact")
    with evidence("late-refusal", dict(parent=raw)) as state:
        parent_request, parent_binding = bind_parent(raw, state)
        declaration = fixtures.removal(parent_binding.geometry, selected)
        request = removal.from_parent(
            parent_request, parent_binding, declaration, law_id=removal.LAW_ID
        )
        state["request"] = request

        def injected(*args):
            raise ArithmeticError("injected post-return owner-check failure")

        monkeypatch.setattr(removal, "_unchanged_survivors", injected)
        with pytest.raises(removal.RemovalRejected) as caught:
            removal.prepare(request)
        state["expected_refusal"] = failed(caught.value)
        trial = caught.value.trial
        assert trial["child_declaration"] and trial["returned_child_request"]
        assert trial["returned_child_binding"] and trial["lineage"]
        assert "injected post-return" in json.dumps(trial)
        assert isinstance(caught.value.__cause__, ArithmeticError)


def test_returned_record_copy():
    raw, selected = fixtures.case("triangle-contact")
    with evidence("returned-copy", dict(parent=raw)) as state:
        parent_request, parent_binding = bind_parent(raw, state)
        request = removal.from_parent(
            parent_request,
            parent_binding,
            fixtures.removal(parent_binding.geometry, selected),
            law_id=removal.LAW_ID,
        )
        binding = removal.prepare(request)
        state["binding"] = binding
        copied = binding.report
        copied["axes"]["cell"]["after_ids"].clear()
        assert binding.report["axes"]["cell"]["after_ids"] == ["cell0"]
        assert len(parent_binding.geometry["cells"]) == 2
        removal.validate_binding(request, binding)


@pytest.fixture
def software_no_geometry(monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("unexpected_geometry_or_reference_execution")
        raise AssertionError("Software refusal checks must not execute geometry or references")

    for name in ("from_polygons", "prepare", "validate_request", "validate_binding"):
        monkeypatch.setattr(geometry, name, forbidden)
    monkeypatch.setattr(reference, "solve", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    yield attempts
    assert attempts == []


def test_software_nonfinite_opt_in_preserved(software_no_geometry):
    with evidence("software-nonfinite", dict(parent="unparsed parent strings")) as state:
        request = geometry.Request("full invalid parent declaration", (), "id")
        binding = geometry.Binding("id", "full invalid parent geometry", "geometry-id")
        with pytest.raises(removal.RemovalRejected) as caught:
            removal.from_parent(
                request,
                binding,
                dict(removed_cell_ids=[], exposed_baths=[]),
                law_id=struct.unpack(">d", bytes.fromhex("7ff8000000000017"))[0],
            )
        state["expected_refusal"] = failed(caught.value)
        assert caught.value.code == "explicit_opt_in"
        assert caught.value.trial["opted_in_law"] == dict(
            kind="binary64", bits_be="7ff8000000000017"
        )
        assert "full invalid parent declaration" in json.dumps(caught.value.trial)


def test_software_metadata_cannot_resume(software_no_geometry):
    with evidence("software-resume", dict(attempted_admission=True)) as state:
        binding = removal.Binding("id", '{"ordinary_continuation_admitted":true}', None, None, "id")
        with pytest.raises(removal.RemovalRejected) as caught:
            removal.require_ordinary_resume(None, binding)
        state["expected_refusal"] = failed(caught.value)
        assert caught.value.code == "ordinary_checkpoint_owner_unavailable"
        assert caught.value.trial["native_invalidated_owners"] == list(
            removal.NATIVE_INVALIDATED_OWNERS
        )
