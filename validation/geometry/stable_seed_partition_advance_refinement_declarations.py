"""Explicit clock-control caller successor; no physical fixture is evaluated."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from validation.geometry import stable_seed_partition_physiology_bridge_declarations as original

PARENT_MANIFEST_SHA256 = "92caecd20cba1973336f14a005492a144393740fae3d6cd3be32a2636a8fcf26"
PARENT_CALLERS_SHA256 = "4be058c5f6211a9a489c709ee95f371d3dd7bf0ba03c8834e789c0be3554c09f"
CLOCK_ARM_IDS = ("base", "dt-half", "dt-quarter")
ARM_IDS = (
    "base",
    "dt-half",
    "dt-quarter",
    "base-trace-4MiB",
    "dt-half-trace-4MiB",
    "dt-quarter-trace-4MiB",
)


def document_path():
    return Path(__file__).with_name("stable_seed_partition_advance_refinement_callers.json")


def document():
    value = json.loads(document_path().read_text())
    parent = Path(__file__).with_name("stable_seed_partition_physiology_bridge_callers.json")
    if hashlib.sha256(parent.read_bytes()).hexdigest() != PARENT_CALLERS_SHA256:
        raise ValueError("Changed immutable original physical caller document")
    embedded = json.dumps(value["original_callers_document"], sort_keys=True, allow_nan=False)
    original_text = json.dumps(json.loads(parent.read_text()), sort_keys=True, allow_nan=False)
    if embedded != original_text:
        raise ValueError("Original four callers, shared dt/end or physics changed")
    if value["parent_initial_manifest_sha256"] != PARENT_MANIFEST_SHA256:
        raise ValueError("Changed parent initial packet")
    return value


def arm(control_id):
    value = document()
    rows = [
        value["original_arm"],
        *value["numerical_controls"],
        *value["resource_numerical_controls"],
    ]
    return next(row for row in rows if row["id"] == control_id)


def geometry_declaration(case):
    return original.geometry_declaration(case)


def declaration(case_id, geometry, *, document_sha256, numerical_control_id):
    if document_sha256 != PARENT_CALLERS_SHA256 or numerical_control_id not in ARM_IDS:
        raise ValueError("Complete original caller and explicit clock control required")
    value = document()
    if case_id not in value["scope"]["case_ids"]:
        raise ValueError("Clock controls cannot add physical cases")
    base = original.declaration(case_id, geometry, document_sha256=PARENT_CALLERS_SHA256)
    if numerical_control_id == "base":
        return base
    selected = arm(numerical_control_id)
    if "applies_to_case_ids" in selected and case_id not in selected["applies_to_case_ids"]:
        raise ValueError("The storage envelope is only an explicitly declared resource control")
    changed = deepcopy(base)
    changed["execution"]["dt"] = float(selected["dt_s"])
    changed["execution"]["max_steps"] = selected["max_steps"]
    if "max_trace_bytes" in selected:
        changed["execution"]["max_trace_bytes"] = selected["max_trace_bytes"]
    if changed["experiment"]["end_time"] != selected["end_time_s"]:
        raise ValueError("All numerical controls require the original common endpoint")
    changed["provenance"].update(
        kind="explicit_manufactured_initial_clock_control@1",
        document_sha256=hashlib.sha256(document_path().read_bytes()).hexdigest(),
        parent_document_sha256=PARENT_CALLERS_SHA256,
        parent_initial_manifest_sha256=PARENT_MANIFEST_SHA256,
        numerical_control_id=numerical_control_id,
        clock_control=dict(
            dt_s=float(selected["dt_s"]),
            max_steps=selected["max_steps"],
            unchanged_end_time_s=float(selected["end_time_s"]),
        ),
    )
    if "max_trace_bytes" in selected:
        changed["provenance"]["resource_control"] = dict(
            id="trace-4MiB",
            max_trace_bytes=selected["max_trace_bytes"],
            original_max_trace_bytes=base["execution"]["max_trace_bytes"],
            old_budget_refusal_reclassified=False,
        )
    return changed


def clock_labels(control_id):
    """Independent bounded clock labels; no model or geometry is evaluated."""
    selected = arm(control_id)
    dt, end, count = float(selected["dt_s"]), float(selected["end_time_s"]), selected["max_steps"]
    if count not in (1, 2, 4) or end != 1e-6:
        raise ValueError(
            "Only the three explicitly declared original-endpoint clocks are supported"
        )
    values = [i * dt for i in range(count)] + [end]
    if values[0] != 0.0 or any(b <= a for a, b in zip(values, values[1:], strict=False)):
        raise ValueError("Explicit original-grid clock labels must strictly increase")
    return values


def comparison_ids(case_id):
    return tuple(document()["comparison_arm_ids"][case_id])


def same_physical_definition(definitions, arm_ids):
    """Reject changed physics/controls; only declared clock resources differ."""
    targets = []
    caps = []
    for control_id in arm_ids:
        selected = arm(control_id)
        raw = definitions[control_id]
        if (
            raw["execution"]["dt"] != selected["dt_s"]
            or raw["execution"]["max_steps"] != selected["max_steps"]
        ):
            raise ValueError("Each arm must carry its explicitly declared dt and max_steps")
        if raw["experiment"]["end_time"] != selected["end_time_s"]:
            raise ValueError("All three arms must reach the unchanged common endpoint")
        expected_cap = selected.get("max_trace_bytes", 1048576)
        if raw["execution"]["max_trace_bytes"] != expected_cap:
            raise ValueError("Explicit original or 4MiB storage control must be retained")
        caps.append(expected_cap)
        normalized = deepcopy(raw)
        normalized["execution"].pop("dt")
        normalized["execution"].pop("max_steps")
        targets.append(normalized)
    encoded = [
        json.dumps(target, sort_keys=True, separators=(",", ":"), allow_nan=False)
        for target in targets
    ]
    if len(set(caps)) != 1 or any(target != encoded[0] for target in encoded[1:]):
        raise ValueError(
            "Clock controls cannot change physical model, controls or other execution fields"
        )
    return targets[0]
