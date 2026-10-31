"""Fresh conditional references with read-only pre-projection retention."""

import struct
import sys
from decimal import Decimal

from validation.betse import betse_mechanics_join_reference as mechanics
from validation.betse import betse_normal_ecm_field_join_reference as field


def encode(value):
    if isinstance(value, Decimal):
        return dict(decimal=str(value))
    if type(value) is float:
        return dict(binary64_bits_be=struct.pack(">d", value).hex())
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    if value is None or type(value) in (str, bool, int):
        return value
    raise TypeError("Unexpected raw reference type: " + type(value).__name__)


def evaluate(kind, inputs, *, refinement=1, retain):
    if kind == "mechanics":
        return mechanics.evaluate(inputs, refinement=refinement, retain=retain)
    precision = 100 if refinement == 1 else 160
    captured = []

    def trace(frame, event, arg):
        if (
            event == "call"
            and frame.f_code.co_name in ("serial", "plain")
            and (frame.f_back is None or frame.f_back.f_code.co_name not in ("serial", "plain"))
            and frame.f_globals.get("__name__", "").startswith("validation.")
        ):
            value = frame.f_locals["value"]
            name = "raw-preprojection-" + str(precision) + "-" + str(len(captured)).zfill(4)
            payload = dict(
                precision=precision,
                module=frame.f_globals["__name__"],
                converter=frame.f_code.co_name,
                source_function=frame.f_back.f_code.co_name if frame.f_back is not None else None,
                payload=encode(value),
                read_only_trace=True,
            )
            retain(name, payload)
            captured.append(name)
        return trace

    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        result = field.evaluate(inputs, refinement=refinement)
    finally:
        sys.settrace(previous)
    if not captured:
        raise ValueError("Reference returned without complete pre-projection observation")
    retain(
        "raw-preprojection-index-" + str(precision),
        dict(records=captured, semantics_modified=False),
    )
    retain("projected-reference-" + str(100 if refinement == 1 else 160), result)
    return result
