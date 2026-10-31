"""Small stdlib failure/sampling contracts; no scientific imports or evaluation."""

import struct
import traceback


def record_failure(error, *, stage, readers, retain):
    payload = dict(
        status="unexpected_source_failure",
        failure=dict(
            type=type(error).__name__,
            message=str(error),
            stage=stage,
            traceback="".join(traceback.format_exception(error)),
        ),
        available={},
        capture_errors=[],
    )
    for name, reader in readers.items():
        try:
            payload["available"][name] = reader()
        except Exception as capture_error:
            payload["capture_errors"].append(
                dict(section=name, type=type(capture_error).__name__, message=str(capture_error))
            )
    if retain is not None:
        try:
            retain(payload)
        except Exception as archive_error:
            error.add_note(
                "Failure evidence writer also failed: "
                + type(archive_error).__name__
                + ": "
                + str(archive_error)
            )
    return payload


def sampling_contract(
    *,
    source_labels,
    native_flags,
    reference_indices,
    native_rows,
    owned_rows,
    observation_indices,
    completed_calls,
):
    def require(condition, reason):
        if not condition:
            raise ValueError(reason)

    def bits(value):
        return struct.pack("<d", float(value))

    require(
        type(completed_calls) is int and 0 <= completed_calls <= len(source_labels),
        "Completed prefix outside original calendar",
    )
    require(
        len(native_flags) == len(source_labels) and all(type(v) is bool for v in native_flags),
        "Full native sample flag axis differs from source calendar",
    )
    expected = [i for i, flag in enumerate(native_flags) if flag]
    require(len(reference_indices) == 2, "Require both independent sampling forms")
    for indices in reference_indices:
        require(
            all(type(i) is int for i in indices) and indices == expected,
            "Independent sample indices differ from native source recurrence",
        )
    require(
        len(native_rows) == len(owned_rows) == completed_calls,
        "Complete native/owned per-call sampling records required",
    )
    selected = []
    for i, (native, owned) in enumerate(zip(native_rows, owned_rows, strict=True)):
        eligible = i in expected
        require(
            native["source_call"] == owned["call_index"] == i, "Sample record source call differs"
        )
        require(
            bits(native["source_time_s"])
            == bits(owned["source_label_s"])
            == bits(source_labels[i]),
            "Sample record original source label differs",
        )
        require(
            type(native["native_calendar_eligible"]) is bool
            and native["native_calendar_eligible"] is eligible,
            "Native per-call eligibility differs from independent indices",
        )
        require(
            type(owned["sample_eligible"]) is bool and owned["sample_eligible"] is eligible,
            "Owned per-call eligibility differs from native/independent indices",
        )
        require(
            native["display_attempted"] is False and native["display_completed"] is False,
            "Headless INIT cannot acquire display credit",
        )
        if eligible:
            selected.append(i)
    require(
        observation_indices == selected,
        "Emitted selected observations differ from native/independent prefix",
    )
    return dict(
        original_sample_indices=expected,
        selected_prefix_indices=selected,
        completed_calls=completed_calls,
    )
