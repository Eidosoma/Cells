"""Closed, metadata-only prerequisite gates for the unfrozen trajectory proposal.

The None pins are deliberate: only Chief's accepted receipts can supply them in
a reviewed successor. This draft is not a prepared or executable science capsule.
"""

import hashlib
import json

DRAFT_ONLY = True
GEOMETRY_ACCEPTANCE_SHA256 = "f2f1eab5db26bdc5e4b6dc9a8a9e3c54f5b894b2fbcdee344f5307900603a8c9"
INITIAL18_MANIFEST_SHA256 = "61679336deda03709b6425f6dc571222a1ffdb6a3e92af01b2378bd3270c115f"
INITIAL18_SOURCE_REVIEW_SHA256 = "84440f74eff19c7a96a275afb81f99ccc0eecc241d484c4cb3c9a13735f1f614"
INITIAL18_NUMERICAL_QUALIFICATION_SHA256 = None
FIRST_ADVANCE_SOURCE_REVIEW_SHA256 = None
FIRST_ADVANCE_NUMERICAL_QUALIFICATION_SHA256 = None
TRAJECTORY_INITIAL_MANIFEST_SHA256 = None
TRAJECTORY_INITIAL_SOURCE_REVIEW_SHA256 = None
TRAJECTORY_INITIAL_NUMERICAL_QUALIFICATION_SHA256 = None
TRAJECTORY_SOURCE_REVIEW_SHA256 = None


class PrerequisitePending(ValueError):
    code = "trajectory_prerequisite_pending"
    stage = "metadata_prerequisites_before_scientific_imports"


def parse(text):
    if type(text) is not str or len(text.encode()) > 128 * 2**20:
        raise ValueError("Bounded exact authority JSON required")

    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("Duplicate authority JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Nonfinite authority JSON: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def required_pins(phase):
    if phase not in {"initial", "trajectory"}:
        raise ValueError("Explicit initial or trajectory authority phase required")
    pins = dict(
        geometry_acceptance_json=GEOMETRY_ACCEPTANCE_SHA256,
        initial18_manifest_json=INITIAL18_MANIFEST_SHA256,
        initial18_source_review_json=INITIAL18_SOURCE_REVIEW_SHA256,
        initial18_qualification_json=INITIAL18_NUMERICAL_QUALIFICATION_SHA256,
        first_advance_source_review_json=FIRST_ADVANCE_SOURCE_REVIEW_SHA256,
        first_advance_qualification_json=FIRST_ADVANCE_NUMERICAL_QUALIFICATION_SHA256,
        trajectory_initial_manifest_json=TRAJECTORY_INITIAL_MANIFEST_SHA256,
        trajectory_initial_source_review_json=TRAJECTORY_INITIAL_SOURCE_REVIEW_SHA256,
    )
    if phase == "trajectory":
        pins.update(
            trajectory_initial_qualification_json=TRAJECTORY_INITIAL_NUMERICAL_QUALIFICATION_SHA256,
            trajectory_source_review_json=TRAJECTORY_SOURCE_REVIEW_SHA256,
        )
    return pins


def require(authority, *, phase):
    pins = required_pins(phase)
    if DRAFT_ONLY or any(pin is None for pin in pins.values()):
        error = PrerequisitePending(
            "Initial18, first advance and fresh trajectory bindings require accepted receipts"
        )
        error.detail = dict(
            phase=phase,
            numerical_execution_permitted=False,
            freeze_permitted=False,
            pending=[name for name, pin in pins.items() if pin is None],
            automatic_retry=False,
        )
        raise error
    if type(authority) is not dict or set(authority) != set(pins):
        raise ValueError("Complete exact authority roster required")
    for name, pin in pins.items():
        text = authority[name]
        if type(text) is not str or hashlib.sha256(text.encode()).hexdigest() != pin:
            raise ValueError("Changed accepted authority: " + name)
        if type(parse(text)) is not dict:
            raise ValueError("Authority receipts must be complete objects")
    return {name: parse(text) for name, text in authority.items()}


def initial_phase(authority):
    """The trajectory has two more receipts than its prerequisite initial worker."""
    return {name: authority[name] for name in required_pins("initial")}
