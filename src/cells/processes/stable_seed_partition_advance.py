"""Draft first original-grid RK4 interval after qualified initial physiology.

All scientific imports and execution follow the pending numerical-qualification
gate. Existing Cells checked RK4, controls, layout and accounting are reused.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path
from types import MappingProxyType

LAW_ID = "cells_explicit_seed_partition_first_original_rk4_interval@1"
INPUT_KIND = "cells.explicit_seed_partition_first_interval_request@1"
INITIAL_MANIFEST_SHA256 = "92caecd20cba1973336f14a005492a144393740fae3d6cd3be32a2636a8fcf26"
INITIAL_REFERENCE_SHA256 = "554dd4db948070a9c3328e5a2af7ad8b457085b229e9ada260e4e2e26f289ed0"
INITIAL_SOURCE_REVIEW_SHA256 = None
INITIAL_NUMERICAL_QUALIFICATION_SHA256 = None
DRAFT_ONLY = True
SOURCE_PINS = {
    "src/cells/processes/stable_seed_partition_physiology_bridge.py": (
        "31959e49ec266092556dc67c755d28105e24bdf6789079fd766c7c5e4f3566ca"
    ),
    "src/cells/numerics/fixed_step.py": (
        "a9821afc713c07b18c4d586ba7e991379eb011be54494a177aab13b8a39dd3b6"
    ),
    "src/cells/core/runner.py": "b58db4c695141ad04c32a4b1f49091fbc0a57c8820a5321002403fe01c544a95",
    "src/cells/core/grid.py": "3a34c0307205069ccd05d199a374e2d5fc01e65311e9bb7e5f3066f4c1a28139",
    "src/cells/core/state.py": "367d3bdcb4093203280a96697a9d7eaf25b11f8a3799c0e5582ce57fb0c12dd1",
    "src/cells/core/devices.py": "3ec3d787e0c554382ff2eea1612db667412b9ad529930fd69dbc68d8a9b65d9d",
    "src/cells/core/schedule.py": (  # Original held-control clock.
        "889eba6db8fcec06a290bc367eb1ddaaabbccec4a5b591ee35b5bc8a4e6082be"
    ),
    "src/cells/core/surface_tissue_spec.py": (
        "ca325e50b59a29ae25eaebc846cd126366e44c94ce0a931b833f26bb693db3aa"
    ),
    "src/cells/models/surface_tissue.py": (
        "a0c9993799b752913deaae7ccdab6780397e05d4e2ac30f66bd60de928eafe29"
    ),
    "src/cells/numerics/surface_field.py": (
        "6ae86409650223e5e81214ee2f57a5d6a0637c7d8ab2d3613e7dbc0d3dc26378"
    ),
    "src/cells/numerics/surface_transport.py": (
        "f64cb3c0201be098793ce916ad65a19fd607b292c143c1b91950d03758f593d9"
    ),
    "src/cells/numerics/extracellular_field.py": (
        "bb0702893a0605616fa84e7864d1e8b4409dbf3404a0b8c8195a538c2488fbbf"
    ),
    "src/cells/processes/electrochemistry.py": (
        "e52dc29e3514268d538b7ceff293d32fd24d36ed3e9ef6242dc2906592c112f2"
    ),
}


@dataclass(frozen=True)
class InitialQualification:
    source_review_json: str
    numerical_qualification_json: str
    prepared_manifest_json: str
    input_json: str
    report_json: str
    caller_acceptance: object


@dataclass(frozen=True)
class Request:
    initial_request: object
    initial_preparation: object
    qualification: InitialQualification
    declaration: object
    identity: str


@dataclass(frozen=True)
class Result:
    request_identity: str
    checkpoint: object
    checkpoint_record: object
    evidence: object
    provenance: object
    identity: str


class AdvanceRejected(ValueError):
    def __init__(self, code, *, stage, original=None, partial=None):
        super().__init__(code)
        self.code, self.stage, self.original, self.partial = code, stage, original, partial


def plain(value):
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(item) for item in value)
    return value


def digest(value):
    def record(item):
        if type(item) is float:
            return dict(binary64_hex=item.hex())
        if type(item) is dict:
            return {k: record(v) for k, v in item.items()}
        if type(item) is list:
            return [record(v) for v in item]
        return item

    return hashlib.sha256(
        json.dumps(
            record(plain(value)), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _require(value, code, *, stage):
    if not value:
        raise AdvanceRejected(code, stage=stage)


def _json(text):
    _require(
        type(text) is str and len(text.encode()) <= 128 * 2**20,
        "complete_bounded_original_JSON_required",
        stage="initial_qualification",
    )

    def pairs(rows):
        result = {}
        for key, value in rows:
            _require(key not in result, "duplicate_JSON_key", stage="initial_qualification")
            result[key] = value
        return result

    def nonfinite(value):
        raise AdvanceRejected(
            "nonfinite_JSON_constant", stage="initial_qualification", original=value
        )

    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def _qualification_gate(proof):
    if (
        DRAFT_ONLY
        or INITIAL_SOURCE_REVIEW_SHA256 is None
        or INITIAL_NUMERICAL_QUALIFICATION_SHA256 is None
    ):
        raise AdvanceRejected(
            "upstream_initial_numerical_qualification_pending",
            stage="initial_qualification",
            original=plain(proof),
            partial=dict(
                source_candidate_only=True,
                numerical_execution_permitted=False,
                automatic_retry=False,
            ),
        )
    _require(
        type(proof) is InitialQualification,
        "complete_initial_qualification_required",
        stage="initial_qualification",
    )
    for text, pin in (
        (proof.source_review_json, INITIAL_SOURCE_REVIEW_SHA256),
        (proof.numerical_qualification_json, INITIAL_NUMERICAL_QUALIFICATION_SHA256),
        (proof.prepared_manifest_json, INITIAL_MANIFEST_SHA256),
    ):
        _require(
            type(text) is str and hashlib.sha256(text.encode()).hexdigest() == pin,
            "changed_initial_authority_bytes",
            stage="initial_qualification",
        )
        _json(text)
    # Exact receipt bytes must be explicitly pinned by Chief after qualification.
    # Their future schema/scope is not inferred from a positive worker report.


def _pins():
    root = Path(__file__).resolve().parents[3]
    for rel, pin in SOURCE_PINS.items():
        _require(
            hashlib.sha256((root / rel).read_bytes()).hexdigest() == pin,
            "changed_first_interval_source:" + rel,
            stage="source_pins",
        )


def _declaration(value):
    expected = {
        "kind",
        "opted_in_law",
        "initial_preparation_identity",
        "step_policy",
        "requested_end_time_s",
        "provided_checkpoint_state_or_operators",
        "caller",
    }
    _require(
        isinstance(value, Mapping) and set(value) == expected,
        "complete_first_interval_declaration_required",
        stage="declaration",
    )
    _require(
        value["kind"] == INPUT_KIND
        and value["opted_in_law"] == LAW_ID
        and value["step_policy"] == "first_original_EventGrid_interval_no_subdivision@1",
        "existing_first_interval_policy_required",
        stage="declaration",
    )
    _require(
        value["provided_checkpoint_state_or_operators"] is None,
        "first_interval_cannot_adopt_state_or_operators",
        stage="declaration",
    )
    _require(
        type(value["caller"]) is str and bool(value["caller"]),
        "explicit_first_interval_caller_required",
        stage="declaration",
    )
    _require(
        type(value["initial_preparation_identity"]) is str
        and len(value["initial_preparation_identity"]) == 64
        and all(c in "0123456789abcdef" for c in value["initial_preparation_identity"]),
        "complete_initial_preparation_identity_required",
        stage="declaration",
    )
    end = value["requested_end_time_s"]
    _require(
        end is None or (type(end) is float and math.isfinite(end) and end > 0),
        "explicit_finite_positive_endpoint_or_original_grid_required",
        stage="declaration",
    )
    return freeze(plain(value))


def _qualified_initial(initial_request, preparation, proof, declaration):
    _qualification_gate(proof)
    _pins()
    from cells.processes import stable_seed_partition_physiology_bridge as initial

    _require(
        type(initial_request) is initial.Request and type(preparation) is initial.Preparation,
        "exact_initial_request_and_preparation_types_required",
        stage="initial_binding",
    )
    rebuilt = initial.bind(
        initial_request.constructor_request,
        initial_request.constructor_candidate,
        initial_request.geometry_evidence,
        initial_request.declaration,
    )
    _require(
        digest(rebuilt) == digest(initial_request)
        and preparation.request_identity == initial_request.identity
        and preparation.identity == initial.digest(initial.preparation_record(preparation)),
        "complete_initial_preparation_binding_required",
        stage="initial_binding",
    )
    _require(
        declaration["initial_preparation_identity"] == preparation.identity,
        "declared_initial_preparation_changed",
        stage="initial_binding",
    )
    incoming, report = _json(proof.input_json), _json(proof.report_json)
    _require(
        set(incoming) == {"case_id", "request", "preparation"}
        and digest(incoming["request"]) == digest(initial_request)
        and digest(incoming["preparation"]) == digest(preparation),
        "complete_original_positive_initial_worker_input_required",
        stage="initial_binding",
    )
    _require(
        report["status"] == "complete"
        and report["baseline_passed"] is True
        and report["candidate_passed"] is True
        and report["control_detected"] is False
        and report["controls"] == []
        and not report.get("runtime_capture_failed", False)
        and not report.get("failure_capture_failed", False)
        and report["baseline"]["full_node_physics_and_RHS_verified"] is True
        and report["baseline"]["represented_concentration_defects_verified"] is True
        and report["baseline"]["accounting_passed"] is True,
        "qualified_complete_initial_physics_not_control_credit_required",
        stage="initial_binding",
    )
    runtime = report["runtime_origin"]
    _require(
        runtime["source_sha256"] == INITIAL_REFERENCE_SHA256
        and runtime["input_sha256"] == hashlib.sha256(proof.input_json.encode()).hexdigest()
        and runtime["production_imports_denied"] is True
        and runtime["production_modules_loaded"] == []
        and runtime["file_errors"] == {}
        and runtime["mapped_file_errors"] == []
        and type(runtime["pid"]) is int
        and type(runtime["parent_pid"]) is int
        and runtime["pid"] > 0
        and runtime["parent_pid"] > 0
        and runtime["pid"] != runtime["parent_pid"],
        "complete_actual_independent_initial_worker_origin_required",
        stage="initial_binding",
    )
    manifest = _json(proof.prepared_manifest_json)
    worker_root = Path(runtime["source"]).parents[2]
    for rel in (
        "validation/geometry/stable_seed_partition_physiology_bridge_reference.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_initial_reference.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_field_reference.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_scalar_reference.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_declarations.py",
        "validation/geometry/stable_seed_explicit_ecm_partition_geometry_reference.py",
        "validation/geometry/conservative_polygon_geometry_reference.py",
        "validation/geometry/stable_geometry_primitives_reference.py",
    ):
        _require(
            runtime["files"].get(str(worker_root / rel))
            == manifest["file_sha256"]["source/" + rel],
            "changed_initial_reference_runtime_source:" + rel,
            stage="initial_binding",
        )
    expected_acceptance = dict(
        kind="caller_accepts_qualified_initial_partition_for_first_original_interval@1",
        caller=declaration["caller"],
        initial_request_identity=initial_request.identity,
        initial_preparation_identity=preparation.identity,
        source_review_sha256=INITIAL_SOURCE_REVIEW_SHA256,
        numerical_qualification_sha256=INITIAL_NUMERICAL_QUALIFICATION_SHA256,
        original_input_sha256=hashlib.sha256(proof.input_json.encode()).hexdigest(),
        original_report_sha256=hashlib.sha256(proof.report_json.encode()).hexdigest(),
        scope="one_original_interval_no_subdivision_continuation_or_native_equivalence",
    )
    _require(
        digest(proof.caller_acceptance) == digest(expected_acceptance),
        "complete_explicit_first_interval_acceptance_required",
        stage="initial_binding",
    )
    return dict(
        case_id=incoming["case_id"],
        initial_preparation_identity=preparation.identity,
        source_review_sha256=INITIAL_SOURCE_REVIEW_SHA256,
        numerical_qualification_sha256=INITIAL_NUMERICAL_QUALIFICATION_SHA256,
    )


def request_record(request):
    return [
        LAW_ID,
        request.initial_request,
        request.initial_preparation,
        request.qualification,
        request.declaration,
    ]


def bind(initial_request, initial_preparation, proof, declaration):
    _qualification_gate(proof)
    declared = _declaration(declaration)
    _qualified_initial(initial_request, initial_preparation, proof, declared)
    authority = InitialQualification(
        proof.source_review_json,
        proof.numerical_qualification_json,
        proof.prepared_manifest_json,
        proof.input_json,
        proof.report_json,
        freeze(plain(proof.caller_acceptance)),
    )
    request = Request(initial_request, initial_preparation, authority, declared, "")
    return replace(request, identity=digest(request_record(request)))


def array_record(value, np):
    """Capture complete names/dtypes/bytes, preserving nonfinite failure bits."""
    if hasattr(value, "_asdict"):
        return {name: array_record(item, np) for name, item in value._asdict().items()}
    if isinstance(value, Mapping):
        return {name: array_record(item, np) for name, item in value.items()}
    array = np.asarray(value)
    _require(
        array.dtype.kind in "bif" and (array.dtype.kind != "f" or array.dtype.itemsize == 8),
        "complete_real_float64_trial_array_required",
        stage="typed_capture",
    )
    return dict(
        kind="typed_C_order_array_bytes@1",
        dtype=array.dtype.str,
        shape=list(array.shape),
        data_hex=array.tobytes(order="C").hex(),
    )


def checkpoint_record(checkpoint, np):
    return dict(
        kind="first_original_numeric_checkpoint@1",
        state=array_record(checkpoint.state, np),
        layout=array_record(checkpoint.layout, np),
        time_s=checkpoint.time,
        step_index=checkpoint.step_index,
        event_index=checkpoint.event_index,
    )


def _cells_trial(state, held, layout, step, model, jax, np, retain):
    from cells.numerics.fixed_step import rk4_checked_step

    trials = []
    retain("cells_trial_roster", trials)

    def contextual(trial, control, parameters, active):
        index = len(trials)
        row = dict(
            index=index,
            role=("k1", "k2", "k3", "k4", "unmasked_endpoint")[index],
            state=array_record(trial, np),
            control=array_record(control, np),
            control_domain_return=None,
            rhs_evaluated=False,
        )
        trials.append(row)
        retain("cells_trial_roster", trials)
        retain("trial-" + str(index) + "-input", row)
        # Preserve the ordinary control-aware guard and its own field recomputation.
        ok = model.control_domain_valid(trial, control, parameters, active)
        row["control_domain_return"] = array_record(ok, np)
        retain("cells_trial_roster", trials)
        retain("trial-" + str(index) + "-domain-return", row)
        return ok

    def guard(trial, parameters, active):
        return model.domain_valid(trial, parameters, active)

    guard.with_control = contextual

    def rhs(trial, control, parameters, active):
        row = trials[-1]
        values = model.field_values(trial, control, parameters)
        row["field"] = array_record(values, np)
        retain("cells_trial_roster", trials)
        retain("trial-" + str(row["index"]) + "-field-return", row["field"])
        derivative = model.derivative_from_field(values, parameters)
        row["rhs"] = array_record(derivative, np)
        row["rhs_evaluated"] = True
        retain("cells_trial_roster", trials)
        retain("trial-" + str(row["index"]) + "-rhs-return", row["rhs"])
        return derivative

    # Same eager checked kernel and JAX equations as the ordinary CPU runner.
    with jax.disable_jit():
        proposed, ok = rk4_checked_step(rhs, guard, state, step, held, layout, layout.active)
    jax.block_until_ready((proposed, ok))
    retain(
        "cells_checked_kernel_return",
        dict(
            returned_state=array_record(proposed, np),
            accepted_domain=array_record(ok, np),
            original_kernel_returns_old_state_if_invalid=True,
            trials=trials,
        ),
    )
    _require(len(trials) == 5, "complete_cells_trial_roster_required", stage="cells_stage_domain")
    _require(
        bool(ok), "existing_cells_rk4_trial_or_endpoint_domain_failed", stage="cells_stage_domain"
    )
    return proposed, trials


def result_record(result):
    return [
        LAW_ID,
        result.request_identity,
        result.checkpoint_record,
        result.evidence,
        result.provenance,
    ]


def advance(request, *, observer=None):
    partial = dict(stage="initial_qualification", request=plain(request), accepted=False)

    def retain(name, value):
        partial[name] = plain(value)
        if observer is not None:
            observer(name, plain(value))

    try:
        _require(
            type(request) is Request,
            "exact_first_interval_request_required",
            stage="initial_qualification",
        )
        _qualification_gate(request.qualification)
        rebuilt = bind(
            request.initial_request,
            request.initial_preparation,
            request.qualification,
            request.declaration,
        )
        _require(
            digest(rebuilt) == digest(request),
            "changed_first_interval_request",
            stage="initial_binding",
        )
        partial["stage"] = "exact_initial_quantity_unit_layout_carry"
        import jax
        import numpy as np

        from cells.core import surface_tissue_spec as schema
        from cells.core.devices import execution_device
        from cells.core.grid import EventGrid, require_refinement_model
        from cells.core.runner import validate_checkpoint
        from cells.core.schedule import control_values, event_index
        from cells.core.state import Checkpoint
        from cells.models import surface_tissue as model
        from cells.processes import stable_seed_partition_physiology_bridge as initial

        initial.physical._pins()
        definition = request.initial_preparation.physical_preparation.definition
        retain("unchanged_initial_definition", definition)
        spec = schema.parse(definition)
        _require(
            spec.execution.backend == "cpu" and spec.execution.jit is False,
            "existing_cpu_eager_scope_required",
            stage=partial["stage"],
        )
        require_refinement_model(spec)
        grid = EventGrid(spec)
        _require(
            len(grid) >= 2 and grid[0] == 0.0,
            "first_original_interval_required",
            stage=partial["stage"],
        )
        end = float(grid[1])
        selected = request.declaration["requested_end_time_s"]
        _require(
            selected is None or selected == end,
            "endpoint_must_equal_first_original_boundary",
            stage="original_grid",
        )
        step = end - float(grid[0])
        retain(
            "original_interval",
            dict(
                start_s=0.0, end_s=end, step_s=step, original_grid_length=len(grid), subdivisions=1
            ),
        )
        table = control_values(spec, [0.0, end])
        held = type(table)(*(v[0] for v in table))
        at_end = type(table)(*(v[1] for v in table))
        _require(
            all(np.array_equal(a, b) for a, b in zip(held, at_end, strict=True)),
            "initial_bridge_only_declares_held_time_zero_controls",
            stage="original_grid",
        )
        model.check_steps(spec, np.asarray([step]), type(table)(*(v[:1] for v in table)))
        state, layout = model.initial_values(spec)
        encoded_state, encoded_layout = array_record(state, np), array_record(layout, np)
        retain("fresh_initial_state", encoded_state)
        retain("fresh_initial_layout", encoded_layout)
        _require(
            digest(encoded_state) == digest(request.initial_preparation.initial_snapshot["state"])
            and digest(encoded_layout)
            == digest(request.initial_preparation.initial_snapshot["layout"]),
            "complete_initial_state_and_layout_bytes_must_carry_exactly",
            stage=partial["stage"],
        )
        _require(
            digest(array_record(held, np))
            == digest(request.initial_preparation.initial_snapshot["control"]),
            "complete_initial_control_bytes_must_carry_exactly",
            stage=partial["stage"],
        )
        device = execution_device("cpu")
        state, layout, held, at_end = jax.device_put((state, layout, held, at_end), device)
        source = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
        retain("source_checkpoint", checkpoint_record(source, np))
        validate_checkpoint(spec, source, times=grid)
        partial["stage"] = "existing_cells_checked_rk4_trial"
        device_step = jax.device_put(np.asarray(step, dtype=np.float64), device)
        proposed, trials = _cells_trial(state, held, layout, device_step, model, jax, np, retain)
        partial["stage"] = "existing_integrated_ledger_accounting"
        history = model.STATE_TYPE(
            *(
                np.stack((np.asarray(a), np.asarray(b)))
                for a, b in zip(state, proposed, strict=True)
            )
        )
        retain("complete_two_boundary_history", array_record(history, np))
        ledger_values = model.balances(
            model.STATE_TYPE(*(np.asarray(v) for v in proposed)),
            model.LAYOUT_TYPE(*(np.asarray(v) for v in layout)),
        )
        retain("raw_existing_endpoint_balances", array_record(ledger_values, np))
        diagnostics = model.check_values(history, spec)
        retain("existing_history_diagnostics", diagnostics)
        partial["stage"] = "right_continuous_endpoint_field"
        endpoint_field = model.field_values(proposed, at_end, layout)
        retain("complete_endpoint_field", array_record(endpoint_field, np))
        endpoint_rhs = model.derivative_from_field(endpoint_field, layout)
        retain("complete_endpoint_diagnostic_RHS", array_record(endpoint_rhs, np))
        _require(
            bool(endpoint_field.converged) and bool(endpoint_field.rates.valid),
            "right_continuous_endpoint_field_failed",
            stage=partial["stage"],
        )
        result_checkpoint = Checkpoint(proposed, source.layout, end, 1, event_index(spec, end))
        partial["stage"] = "ordinary_checkpoint_acceptance"
        validate_checkpoint(spec, result_checkpoint, times=grid)
        _require(
            digest(array_record(result_checkpoint.layout, np)) == digest(encoded_layout),
            "original_layout_cannot_be_rebased",
            stage=partial["stage"],
        )
        partial["accepted"] = True
        partial["first_interval_numerically_qualified"] = False
        provenance = dict(
            kind="cells.explicit_partition_first_original_interval_candidate@1",
            law=LAW_ID,
            initial_request_identity=request.initial_request.identity,
            initial_preparation_identity=request.initial_preparation.identity,
            initial_source_manifest_sha256=INITIAL_MANIFEST_SHA256,
            initial_source_review_sha256=INITIAL_SOURCE_REVIEW_SHA256,
            initial_numerical_qualification_sha256=INITIAL_NUMERICAL_QUALIFICATION_SHA256,
            source_pins=SOURCE_PINS,
            step_s=step,
            start_s=0.0,
            end_s=end,
            cells_checked_kernel="cells.numerics.fixed_step.rk4_checked_step",
            stepping_laws="existing Cells checked RK4 and resolved_tissue@1",
            new_physical_law=False,
            ordinary_layout_preserved=True,
            parameters_or_units_changed=False,
            automatic_retry=False,
            automatic_refinement=False,
            continuation_admitted=False,
            advancing_qualification_inherited=False,
            native_equivalence=False,
            scientific_first_interval_qualification_required=True,
        )
        record = checkpoint_record(result_checkpoint, np)
        evidence = dict(
            trials=trials,
            endpoint_field=partial["complete_endpoint_field"],
            endpoint_RHS=partial["complete_endpoint_diagnostic_RHS"],
            integrated_balances=partial["raw_existing_endpoint_balances"],
            ordinary_history_diagnostics=diagnostics,
            partial=partial,
        )
        result = Result(
            request.identity,
            result_checkpoint,
            freeze(record),
            freeze(evidence),
            freeze(provenance),
            "",
        )
        return replace(result, identity=digest(result_record(result)))
    except Exception as error:
        partial["existing_cells_checks_completed_before_failure"] = partial["accepted"]
        partial["accepted"] = False
        raise AdvanceRejected(
            getattr(error, "code", "first_original_interval_failed"),
            stage=getattr(error, "stage", partial["stage"]),
            original=dict(
                type=type(error).__name__,
                reason=str(error),
                partial=plain(getattr(error, "partial", None)),
            ),
            partial=freeze(plain(partial)),
        ) from error


def require_continuation(_result):
    raise AdvanceRejected("first_interval_candidate_does_not_admit_continuation", stage="scope")
