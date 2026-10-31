"""Unrun explicit-width constructor, independent coverage and corruption plans."""

import ast
import hashlib
import json
import math
import os
import subprocess
import sys
import traceback
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from cells.processes import stable_seed_explicit_ecm_partition as constructor
from validation.geometry import stable_seed_explicit_ecm_partition_fixtures as fixtures

REFUSALS = (
    "wrong-law",
    "missing-clefts",
    "zero-cleft",
    "negative-offset",
    "cell-collapse",
    "domain-gap",
    "oblique-domain",
    "clockwise-domain",
    "changed-seed",
    "missing-seed",
    "duplicate-owner",
    "missing-bath",
    "bath-in-cell-slot",
    "unsupported-grid",
    "wrong-units",
    "native-claim",
    "prior-cell-reclassification",
    "old-operator",
    "empty-operator",
    "zero-membrane-path",
    "signed-zero",
    "unrepresentable-offset",
    "area-underflow",
)
REFUSAL_EXPECTATIONS = {
    "wrong-law": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Explicit new manufactured geometry, SI, width, face and boundary laws required",
        "source_error": None,
        "cause_chain": [],
    },
    "missing-clefts": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Complete exact fields required: explicit offsets and clefts",
        "source_error": None,
        "cause_chain": [],
    },
    "zero-cleft": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Explicit finite binary64 metre values required; widths must be positive",
        "source_error": None,
        "cause_chain": [],
    },
    "negative-offset": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Explicit finite binary64 metre values required; widths must be positive",
        "source_error": None,
        "cause_chain": [],
    },
    "cell-collapse": {
        "phase": "prepare",
        "exception_type": "ConstructionRejected",
        "stage": "exact_widths_and_shared_grid_lines",
        "reason": (
            "Explicit cell/bath construction refused at "
            "exact_widths_and_shared_grid_lines: Cell offsets collapse, overlap "
            "or meet the selected outer domain"
        ),
        "source_error": {
            "type": "ValueError",
            "reason": "Cell offsets collapse, overlap or meet the selected outer domain",
        },
        "cause_chain": [
            {
                "exception_type": "ValueError",
                "stage": None,
                "code": None,
                "reason": "Cell offsets collapse, overlap or meet the selected outer domain",
            }
        ],
    },
    "domain-gap": {
        "phase": "prepare",
        "exception_type": "ConstructionRejected",
        "stage": "exact_widths_and_shared_grid_lines",
        "reason": (
            "Explicit cell/bath construction refused at "
            "exact_widths_and_shared_grid_lines: Explicit outer/intercellular "
            "cleft widths must exactly match seed offsets and domain"
        ),
        "source_error": {
            "type": "ValueError",
            "reason": (
                "Explicit outer/intercellular cleft widths must exactly match seed "
                "offsets and domain"
            ),
        },
        "cause_chain": [
            {
                "exception_type": "ValueError",
                "stage": None,
                "code": None,
                "reason": (
                    "Explicit outer/intercellular cleft widths must exactly match seed "
                    "offsets and domain"
                ),
            }
        ],
    },
    "oblique-domain": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Only a CCW axis-aligned rectangle starting at lower-left is supported",
        "source_error": None,
        "cause_chain": [],
    },
    "clockwise-domain": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Only a CCW axis-aligned rectangle starting at lower-left is supported",
        "source_error": None,
        "cause_chain": [],
    },
    "changed-seed": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Complete retained seed coordinate bits must match its declared tensor slot",
        "source_error": None,
        "cause_chain": [],
    },
    "missing-seed": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Complete separate cell-seed and positive bath-slot owner axes required",
        "source_error": None,
        "cause_chain": [],
    },
    "duplicate-owner": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Distinct unchanged cell and new bath owner IDs required",
        "source_error": None,
        "cause_chain": [],
    },
    "missing-bath": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Complete separate cell-seed and positive bath-slot owner axes required",
        "source_error": None,
        "cause_chain": [],
    },
    "bath-in-cell-slot": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Duplicate bath slot or reclassification of a cell slot",
        "source_error": None,
        "cause_chain": [],
    },
    "unsupported-grid": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Bounded tensor layout requires 1..4 cells per axis and at most32 total regions",
        "source_error": None,
        "cause_chain": [],
    },
    "wrong-units": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Explicit new manufactured geometry, SI, width, face and boundary laws required",
        "source_error": None,
        "cause_chain": [],
    },
    "native-claim": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": (
            "Fresh explicit manufactured seed provenance required; no prior-cell "
            "or native promotion"
        ),
        "source_error": None,
        "cause_chain": [],
    },
    "prior-cell-reclassification": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": (
            "Fresh explicit manufactured seed provenance required; no prior-cell "
            "or native promotion"
        ),
        "source_error": None,
        "cause_chain": [],
    },
    "old-operator": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Prior geometry/caches/operators cannot be reused or reclassified",
        "source_error": None,
        "cause_chain": [],
    },
    "empty-operator": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Prior geometry/caches/operators cannot be reused or reclassified",
        "source_error": None,
        "cause_chain": [],
    },
    "zero-membrane-path": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Explicit finite binary64 metre values required; widths must be positive",
        "source_error": None,
        "cause_chain": [],
    },
    "signed-zero": {
        "phase": "bind",
        "exception_type": "ValueError",
        "stage": None,
        "reason": "Signed-zero geometry input is outside this declared manufactured law",
        "source_error": None,
        "cause_chain": [],
    },
    "unrepresentable-offset": {
        "phase": "prepare",
        "exception_type": "ConstructionRejected",
        "stage": "exact_widths_and_shared_grid_lines",
        "reason": (
            "Explicit cell/bath construction refused at "
            "exact_widths_and_shared_grid_lines: A declared width would change "
            "after binary64 projection; exact grid lines required"
        ),
        "source_error": {
            "type": "ValueError",
            "reason": (
                "A declared width would change after binary64 projection; exact grid lines required"
            ),
        },
        "cause_chain": [
            {
                "exception_type": "ValueError",
                "stage": None,
                "code": None,
                "reason": (
                    "A declared width would change after binary64 projection; exact grid "
                    "lines required"
                ),
            }
        ],
    },
    "area-underflow": {
        "phase": "prepare",
        "exception_type": "ConstructionRejected",
        "stage": "existing_finite_ECM_geometry_admission",
        "reason": (
            "Explicit cell/bath construction refused at "
            "existing_finite_ECM_geometry_admission: unrepresentable_output at "
            "region_area_m2"
        ),
        "source_error": {
            "type": "PartitionRejected",
            "reason": "unrepresentable_output at region_area_m2",
        },
        "cause_chain": [
            {
                "exception_type": "PartitionRejected",
                "stage": "partition_and_physical_faces",
                "code": None,
                "reason": "unrepresentable_output at region_area_m2",
            },
            {
                "exception_type": "GeometryRejected",
                "stage": "region_area_m2",
                "code": "unrepresentable_output",
                "reason": "unrepresentable_output at region_area_m2",
            },
        ],
    },
}
CORRUPTIONS = (
    "stored-vertex",
    "bath-reclassified",
    "missing-bath",
    "missing-membrane",
    "face-distance",
    "double-face-area",
    "face-owner",
    "boundary-owner",
    "seed-owner-map",
    "extra-centroid-axis",
    "extra-tangent-axis",
    "tangent-certificate",
    "face-interval-certificate",
    "boolean-incidence",
    "empty-grid-ledger",
    "extra-grid-event",
    "coherent-wrong-grid-target",
    "wrong-width-target",
    "empty-region-targets",
    "wrong-conservation",
    "native-promotion",
    "physical-promotion",
    "extra-field",
)


def persist(root, name, value):
    root.mkdir(parents=True, exist_ok=True)
    with (root / (name + ".json")).open("x") as stream:
        json.dump(constructor.plain(value), stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def evidence(root, case, purpose):
    state = dict(case=case, purpose=purpose, stage="declared", request=None, candidate=None)
    persist(
        root,
        "explicit-declared-input",
        dict(
            case=case,
            purpose=purpose,
            declaration=fixtures.declaration(case),
            source_scope="new_manufactured_cell_bath_geometry",
            native_equivalence=False,
            prior_full_domain_cells_reclassified=False,
        ),
    )
    try:
        yield state
    except BaseException as error:
        try:
            persist(
                root,
                "constructor-failure",
                dict(
                    state=state,
                    type=type(error).__name__,
                    reason=str(error),
                    traceback=traceback.format_exc(),
                    stage=getattr(error, "stage", None),
                    original=getattr(error, "original", None),
                    partial=getattr(error, "partial", None),
                ),
            )
        except BaseException as capture:
            error.add_note("Failure capture also failed: " + repr(capture))
            try:
                persist(
                    root,
                    "constructor-failure-capture-error",
                    dict(
                        original_type=type(error).__name__,
                        original_reason=str(error),
                        capture_type=type(capture).__name__,
                        capture_reason=str(capture),
                    ),
                )
            except BaseException as fallback:
                error.add_note("Failure fallback also failed: " + repr(fallback))
        raise


def observer(root, prefix):
    sequence = [0]

    def observe(stage, value):
        persist(root, prefix + "-" + str(sequence[0]) + "-" + stage, value)
        sequence[0] += 1

    return observe


def build(root, state):
    raw = fixtures.declaration(state["case"])
    state["stage"] = "complete_explicit_bind"
    request = constructor.bind(raw)
    state["request"] = request
    persist(root, "constructor-request", request)
    state["stage"] = "positive_cell_and_bath_construction"
    value = constructor.prepare(request, observer=observer(root, "construction-event"))
    state["candidate"] = value
    persist(root, "constructor-candidate", value)
    return request, value


def independent(root, request, value, *, controls=None, failed_baseline=False):
    payload = dict(request=request, candidate=value)
    if controls is not None:
        payload["controls"] = controls
    persist(root, "reference-input", payload)
    source, target = root / "reference-input.json", root / "reference-output.json"
    process = None
    with (root / "reference.stdout.log").open("x") as stream:
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.geometry.stable_seed_explicit_ecm_partition_reference",
                    "--input",
                    str(source),
                    "--output",
                    str(target),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
            persist(
                root,
                "reference-started",
                dict(
                    pid=process.pid,
                    parent_pid=os.getpid(),
                    input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    timeout_seconds=480,
                    execution_mode="actual_nested_child_only_never_replay",
                ),
            )
            process.wait(timeout=480)
        except BaseException as error:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            persist(
                root,
                "reference-process-failure",
                dict(
                    type=type(error).__name__,
                    reason=str(error),
                    pid=None if process is None else process.pid,
                    traceback=traceback.format_exc(),
                ),
            )
            raise
        finally:
            stream.flush()
            os.fsync(stream.fileno())
    persist(
        root,
        "reference-process",
        dict(pid=process.pid, parent_pid=os.getpid(), returncode=process.returncode),
    )
    report = json.loads(target.read_text()) if target.is_file() else None
    assert report is not None, (
        "Original input/start/log/process artifacts retained; no complete reference report"
    )
    runtime = report["runtime_origin"]
    assert runtime["pid"] == process.pid and runtime["parent_pid"] == os.getpid()
    assert runtime["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert runtime["production_and_scientific_imports_denied"] is True
    assert (
        runtime["production_or_scientific_modules_loaded"] == []
        and runtime["file_errors"] == {}
        and runtime["mapped_file_errors"] == []
    )
    assert report.get("runtime_capture_failed", False) is False
    if failed_baseline:
        assert process.returncode == 2 and report["status"] == "baseline_failed"
        assert (
            report["baseline_passed"] is False
            and report["control_detected"] is False
            and report["controls"] == []
        )
    else:
        assert (
            process.returncode == 0
            and report["baseline_passed"] is True
            and report["candidate_passed"] is True
        )
        if controls:
            assert report["control_detected"] is True
            assert [row["name"] for row in report["controls"]] == [row["name"] for row in controls]
            assert all(row["verification"]["passed"] is False for row in report["controls"])
        else:
            assert report["control_detected"] is False
    return report


def reseal(value):
    g = json.loads(value["partition_binding"]["geometry_json"])
    encoded = json.dumps(g, sort_keys=True, separators=(",", ":"), allow_nan=False)
    value["partition_binding"]["geometry_json"] = encoded
    value["partition_binding"]["identity"] = hashlib.sha256(encoded.encode()).hexdigest()
    value["identity"] = constructor.digest(
        [constructor.LAW_ID]
        + [
            value[key]
            for key in (
                "request_identity",
                "partition_request",
                "partition_binding",
                "construction",
                "owner_maps",
                "conservation",
                "provenance",
            )
        ]
    )
    return value


def corrupt(name, value):
    changed = constructor.plain(value)
    g = json.loads(changed["partition_binding"]["geometry_json"])
    if name == "stored-vertex":
        g["vertices"][0]["xy_m"][0] = math.nextafter(g["vertices"][0]["xy_m"][0], math.inf)
    elif name == "bath-reclassified":
        next(row for row in g["regions"] if row["kind"] == "bath")["kind"] = "cell"
    elif name == "missing-bath":
        g["regions"].pop()
    elif name == "missing-membrane":
        g["membranes"].pop()
    elif name == "face-distance":
        g["faces"][0]["length_m"] *= 2
    elif name == "double-face-area":
        g["faces"][0]["area_m2"] *= 2
    elif name == "face-owner":
        g["faces"][0]["sender"], g["faces"][0]["receiver"] = (
            g["faces"][0]["receiver"],
            g["faces"][0]["sender"],
        )
    elif name == "boundary-owner":
        g["boundary"][0]["region_id"] = g["cell_ids"][0]
    elif name == "seed-owner-map":
        changed["owner_maps"]["seed_owners"][0]["geometry_region_index"] += 1
    elif name == "extra-centroid-axis":
        g["regions"][0]["centroid_m"].append(0.0)
    elif name == "extra-tangent-axis":
        for edge in g["edges"]:
            edge["tangent_xy"].append(0.0)
        edges = {row["id"]: row for row in g["edges"]}
        for family in ("membranes", "faces", "boundary"):
            for row in g[family]:
                row["tangent_xy"].append(
                    0.0 if row["vertex_ids"] == edges[row["edge_id"]]["vertex_ids"] else -0.0
                )
    elif name == "tangent-certificate":
        value = g["edges"][0]["certificates"]["tangent"][0]
        value["caller_tolerance"] = 1.0
    elif name == "face-interval-certificate":
        cert = g["faces"][0]["certificates"]["length"]
        cert["lower"] = dict(numerator="0", denominator="1")
    elif name == "boolean-incidence":
        row = next(row for row in g["membrane_incidence"] if any(v == 1 for v in row))
        row[row.index(1)] = True
    elif name == "empty-grid-ledger":
        changed["construction"]["grid_line_events"] = []
    elif name == "extra-grid-event":
        changed["construction"]["grid_line_events"].append(
            deepcopy(changed["construction"]["grid_line_events"][-1])
        )
    elif name == "coherent-wrong-grid-target":
        event = changed["construction"]["grid_line_events"][1]
        event["input_exact"]["numerator"] = str(int(event["input_exact"]["numerator"]) + 1)
        event["returned"]["exact_target"] = deepcopy(event["input_exact"])
    elif name == "wrong-width-target":
        changed["construction"]["width_checks"]["x"]["realized_cleft_widths"][0]["numerator"] = (
            "999"
        )
    elif name == "empty-region-targets":
        changed["construction"]["region_measure_targets"] = []
    elif name == "wrong-conservation":
        changed["conservation"]["bath_area_m2_exact"]["numerator"] = "999"
    elif name == "native-promotion":
        changed["provenance"]["native_equivalence"] = g["native_equivalence"] = True
    elif name == "physical-promotion":
        changed["provenance"]["physical_model_prepared"] = True
    elif name == "extra-field":
        changed["ordinary_loop_cache"] = {}
    else:
        raise ValueError(name)
    changed["partition_binding"]["geometry_json"] = json.dumps(
        g, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return reseal(changed)


@pytest.mark.parametrize("case", fixtures.CASES)
def test_positive_explicit_cell_bath_construction_and_full_independent_geometry(case, tmp_path):
    with evidence(tmp_path, case, "positive_new_manufactured_geometry_only") as state:
        request, value = build(tmp_path, state)
        independent(tmp_path, request, value)
        assert value.conservation["coverage_defect_m2_exact"]["numerator"] == "0"
        assert int(value.conservation["bath_area_m2_exact"]["numerator"]) > 0
        assert value.provenance["physical_model_prepared"] is False
        assert len(value.partition_binding.geometry["membranes"]) == 4 * len(
            request.declaration["cell_owners"]
        )
        assert [row["owner_id"] for row in value.owner_maps["seed_owners"]] == [
            row["id"] for row in request.declaration["cell_owners"]
        ]
        persist(
            tmp_path,
            "positive-verdict",
            dict(
                passed=True,
                case=case,
                new_manufactured_geometry=True,
                native_equivalence=False,
                physical_model_prepared=False,
                actual_reference_children=1,
            ),
        )


def test_complete_caller_width_domain_owner_and_cache_refusals(tmp_path):
    with evidence(
        tmp_path, fixtures.BASE, "batched_refusals_after_positive_independent_constructor"
    ) as state:
        request, value = build(tmp_path, state)
        independent(tmp_path, request, value)
        assert tuple(REFUSAL_EXPECTATIONS) == REFUSALS
        refusal_metadata_controls(tmp_path)
        for name in REFUSALS:
            raw = fixtures.declaration(fixtures.BASE)
            if name == "wrong-law":
                raw["opted_in_law"] = "native_cell_space"
            elif name == "missing-clefts":
                raw["layout"].pop("cleft_width_x_m")
            elif name == "zero-cleft":
                raw["layout"]["cleft_width_x_m"][0] = 0.0
            elif name == "negative-offset":
                raw["layout"]["cell_half_width_x_m"][0] *= -1
            elif name == "cell-collapse":
                raw["layout"]["cell_half_width_x_m"][0] *= 2
            elif name == "domain-gap":
                raw["layout"]["cleft_width_x_m"][0] *= 2
            elif name == "oblique-domain":
                raw["domain"]["vertices_m"][1][1] = 1e-9
            elif name == "clockwise-domain":
                raw["domain"]["vertices_m"].reverse()
            elif name == "changed-seed":
                raw["cell_owners"][0]["seed_xy_m"][0] *= 2
            elif name == "missing-seed":
                raw["cell_owners"].pop()
            elif name == "duplicate-owner":
                raw["bath_owners"][0]["id"] = raw["cell_owners"][0]["id"]
            elif name == "missing-bath":
                raw["bath_owners"].pop()
            elif name == "bath-in-cell-slot":
                raw["bath_owners"][0]["slot"] = [1, 1]
            elif name == "unsupported-grid":
                raw["layout"]["x_centres_m"] = [1.0, 2.0, 3.0]
                raw["layout"]["y_centres_m"] = [1.0, 2.0]
            elif name == "wrong-units":
                raw["units"]["membrane_path"] = "nm"
            elif name == "native-claim":
                raw["source"]["native_equivalence"] = True
            elif name == "prior-cell-reclassification":
                raw["source"]["prior_full_domain_cells_reclassified"] = True
            elif name == "old-operator":
                raw["old_cache_policy"]["provided_cached_operators"] = dict(lapGJinv=[[1.0]])
            elif name == "empty-operator":
                raw["old_cache_policy"]["provided_cached_operators"] = {}
            elif name == "zero-membrane-path":
                raw["membrane_thickness_m"] = 0.0
            elif name == "signed-zero":
                raw["domain"]["vertices_m"][0][0] = -0.0
            elif name == "unrepresentable-offset":
                raw["layout"]["x_centres_m"] = [1.0]
                raw["cell_owners"][0]["seed_xy_m"][0] = 1.0
                raw["layout"]["cell_half_width_x_m"] = [2.0**-53]
                raw["layout"]["cleft_width_x_m"] = [float.fromhex("0x1.fffffffffffffp-1")] * 2
                raw["domain"]["vertices_m"][1][0] = raw["domain"]["vertices_m"][2][0] = 2.0
            elif name == "area-underflow":
                unit = 2.0**-600
                for axis in ("x", "y"):
                    raw["layout"][axis + "_centres_m"] = [2 * unit]
                    raw["layout"]["cell_half_width_" + axis + "_m"] = [unit]
                    raw["layout"]["cleft_width_" + axis + "_m"] = [unit, unit]
                raw["cell_owners"][0]["seed_xy_m"] = [2 * unit, 2 * unit]
                raw["domain"]["vertices_m"] = [
                    [0.0, 0.0],
                    [4 * unit, 0.0],
                    [4 * unit, 4 * unit],
                    [0.0, 4 * unit],
                ]
            persist(tmp_path, "refusal-" + name + "-input", raw)
            phase = "bind"
            with pytest.raises(ValueError) as caught:
                changed = constructor.bind(raw)
                phase = "prepare"
                constructor.prepare(
                    changed, observer=observer(tmp_path, "refusal-" + name + "-event")
                )
            expected = REFUSAL_EXPECTATIONS[name]
            observed = refusal_contract(caught.value, phase)
            persist(
                tmp_path,
                "refusal-" + name + "-verdict",
                dict(
                    refused=observed == expected,
                    expected=expected,
                    observed=observed,
                    original=getattr(caught.value, "original", None),
                    partial=getattr(caught.value, "partial", None),
                ),
            )
            assert (
                type(caught.value)
                is {
                    "ValueError": ValueError,
                    "ConstructionRejected": constructor.ConstructionRejected,
                }[expected["exception_type"]]
            )
            assert observed == expected
            if name == "unrepresentable-offset":
                assert isinstance(caught.value, constructor.ConstructionRejected)
                assert caught.value.partial["grid_line_events"][-1]["returned"][
                    "exact_target"
                ] != constructor.plain(
                    ratio_from_float(
                        caught.value.partial["grid_line_events"][-1]["returned"]["value"]
                    )
                )
            if name == "area-underflow":
                assert isinstance(caught.value, constructor.ConstructionRejected)
                assert len(caught.value.partial["completed"]["region_measure_targets"]) == 9
        persist(
            tmp_path,
            "input-refusal-panel",
            dict(
                passed=True, ids=REFUSALS, positive_baseline_first=True, actual_reference_children=1
            ),
        )


def refusal_contract(error, phase):
    causes = []
    cause = error.__cause__
    while cause is not None:
        causes.append(
            dict(
                exception_type=type(cause).__name__,
                stage=getattr(cause, "stage", None),
                code=getattr(cause, "code", None),
                reason=str(cause),
            )
        )
        cause = cause.__cause__
    partial = getattr(error, "partial", None)
    source = None if partial is None else partial["source_error"]
    return dict(
        phase=phase,
        exception_type=type(error).__name__,
        stage=getattr(error, "stage", None),
        reason=str(error),
        source_error=None if source is None else dict(type=source["type"], reason=source["reason"]),
        cause_chain=causes,
    )


def refusal_metadata_controls(root):
    expected = REFUSAL_EXPECTATIONS["cell-collapse"]
    rows = []
    for field, replacement in (
        ("phase", "bind"),
        ("exception_type", "ValueError"),
        ("stage", "existing_finite_ECM_geometry_admission"),
        ("reason", "unrelated late ValueError"),
        ("source_error", dict(type="ValueError", reason="unrelated late ValueError")),
        ("cause_chain", []),
    ):
        changed = deepcopy(expected)
        changed[field] = replacement
        rows.append(dict(changed_field=field, expected=expected, observed=changed, credited=False))
        assert changed != expected
    unrelated = refusal_contract(ValueError("unrelated late ValueError"), "prepare")
    wrong_stage = refusal_contract(
        constructor.ConstructionRejected("unrelated late ValueError", stage="wrong_stage"),
        "prepare",
    )
    assert unrelated != expected and wrong_stage != expected
    persist(
        root,
        "refusal-metadata-controls",
        dict(
            rows=rows,
            unrelated_exception=unrelated,
            wrong_stage_exception=wrong_stage,
            metadata_only=True,
            scientific_case_credit=0,
            additional_children=0,
        ),
    )


def reference_retention_metadata_controls(root):
    """Future metadata faults in exact extracted ASTs; no geometry call or child."""
    project = Path(__file__).resolve().parents[2]
    source = project / "validation/geometry/stable_seed_explicit_ecm_partition_reference.py"
    lane = project / "validation/geometry/stable_seed_explicit_ecm_partition_geometry_reference.py"
    tree = ast.parse(source.read_bytes())
    names = {"require", "keys", "derive", "evaluate"}
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in functions} == names
    extracted = ast.Module(body=functions, type_ignores=[])
    rows = []
    for fault in ("after_primary", "after_refined"):
        calls = []
        primary, refined = dict(marker="completed_primary"), dict(marker="completed_refined")

        class MetadataFault(RuntimeError):
            pass

        class MetadataPartition(dict):
            def __getitem__(self, key):
                if key == "regions":
                    raise MetadataFault("injected after_refined")
                return super().__getitem__(key)

        def geometry_stub(
            raw, *, refinement, calls=calls, fault=fault, primary=primary, refined=refined
        ):
            calls.append(refinement)
            if refinement == 2 and fault == "after_primary":
                raise MetadataFault("injected after_primary")
            return primary if refinement == 1 else refined

        def cumulative_stub(declaration, axis, lower, upper, events):
            events.append(dict(marker="metadata_grid_event", axis=axis))
            return [axis + "_exact"], [axis + "_stored"], dict(marker=axis + "_widths")

        def unreachable(*args):
            raise AssertionError("Metadata failure cannot reach baseline or control verification")

        namespace = dict(
            hashlib=hashlib,
            Path=Path,
            traceback=traceback,
            GEOMETRY_REFERENCE_SHA256=hashlib.sha256(lane.read_bytes()).hexdigest(),
            geometry=SimpleNamespace(__file__=str(lane), evaluate=geometry_stub),
            authenticate=lambda request: dict(domain=dict(vertices_m=[[0, 0], [1, 0], [1, 1]])),
            cumulative_axis=cumulative_stub,
            partition=lambda *args: MetadataPartition(),
            verify=unreachable,
        )
        exec(compile(extracted, str(source) + ":metadata_stubs", "exec"), namespace)
        report = namespace["evaluate"](
            dict(
                request=dict(marker="metadata_request"),
                candidate=dict(marker="metadata_candidate"),
                controls=[dict(name="must_not_receive_credit", candidate={})],
            )
        )
        persist(
            root,
            "reference-retention-" + fault,
            dict(
                report=report,
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                exact_extracted_AST_members=sorted(names),
                dependency_calls_stubbed=True,
                geometry_evaluations=0,
                additional_children=0,
                scientific_case_credit=0,
            ),
        )
        assert report["status"] == "reference_failed" and report["type"] == "MetadataFault"
        assert report["reason"] == "injected " + fault
        assert report["baseline_passed"] is False and report["candidate_passed"] is False
        assert report["control_detected"] is False and report["controls"] == []
        partial = report["raw_partial"]
        assert partial["primary"] == primary and len(partial["grid_line_events"]) == 2
        assert set(partial) >= {"x_axis", "y_axis", "partition_input"}
        if fault == "after_primary":
            assert "refined" not in partial and partial["stage"] == "independent_refined_geometry"
        else:
            assert partial["refined"] == refined and partial["stage"] == "independent_owner_maps"
        assert calls == [1, 2]
        rows.append(
            dict(fault=fault, retained_completed_precisions=1 if fault == "after_primary" else 2)
        )
    persist(root, "reference-retention-metadata-panel", dict(rows=rows, scientific_case_credit=0))


def ratio_from_float(value):
    numerator, denominator = value.as_integer_ratio()
    return dict(numerator=str(numerator), denominator=str(denominator))


def test_resealed_constructor_and_geometry_controls_need_same_worker_baseline(tmp_path):
    with evidence(
        tmp_path, fixtures.BASE, "one_derived_truth_for_all_resealed_output_controls"
    ) as state:
        request, value = build(tmp_path, state)
        controls = [dict(name=name, candidate=corrupt(name, value)) for name in CORRUPTIONS]
        assert all(
            constructor.digest(row["candidate"]) != constructor.digest(value) for row in controls
        )
        independent(tmp_path, request, value, controls=controls)
        persist(
            tmp_path,
            "output-control-panel",
            dict(
                passed=True,
                ids=CORRUPTIONS,
                positive_baseline_same_worker_first=True,
                actual_reference_children=1,
            ),
        )


def test_failed_constructor_baseline_cannot_credit_output_controls(tmp_path):
    with evidence(
        tmp_path, fixtures.BASE, "failed_baseline_blocks_negative_control_credit"
    ) as state:
        request, value = build(tmp_path, state)
        independent(
            tmp_path,
            request,
            corrupt("face-distance", value),
            controls=[
                dict(name="physical-promotion", candidate=corrupt("physical-promotion", value))
            ],
            failed_baseline=True,
        )
        reference_retention_metadata_controls(tmp_path)
        persist(
            tmp_path,
            "baseline-failure-guard",
            dict(passed=True, control_credit=False, actual_reference_children=1),
        )


def test_geometry_does_not_admit_old_operators_or_physical_model(tmp_path):
    with evidence(
        tmp_path, fixtures.BASE, "new_geometry_keeps_physical_native_and_old_operator_gates_closed"
    ) as state:
        request, value = build(tmp_path, state)
        independent(tmp_path, request, value)
        constructor.validate(request, value)
        with pytest.raises(ValueError, match="physical admission"):
            constructor.require_physical_admission(value)
        with pytest.raises(ValueError, match="invalidated"):
            constructor.require_cached_operators(value)
        persist(
            tmp_path,
            "closed-gates-verdict",
            dict(
                passed=True,
                physical_model_prepared=False,
                native_equivalence=False,
                actual_reference_children=1,
            ),
        )
