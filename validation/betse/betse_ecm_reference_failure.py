"""PROPOSAL: exact scalar/Decimal partial evidence for an ECM reference refusal.

This serializes already available values; it evaluates no equations. Arrays and
arbitrary Python objects are outside the JSON-input reference's capture domain.
"""

import hashlib
import json
import os
import struct
from decimal import Decimal
from pathlib import Path


def typed(value):
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if type(value) is float:
        return {"float64_bits": struct.pack("<d", value).hex()}
    if isinstance(value, dict):
        if not all(type(key) is str for key in value):
            raise ValueError("Reference evidence requires string mapping owners")
        return {"mapping": [[key, typed(item)] for key, item in value.items()]}
    if isinstance(value, (tuple, list)):
        return {"sequence": [typed(item) for item in value], "sequence_type": type(value).__name__}
    if value is None or type(value) in (str, int, bool):
        return value
    raise TypeError("Unsupported reference-failure value: " + type(value).__name__)


def write(output, *, input_bytes, mode, refinement, error, runtime, available_result):
    output = Path(output)
    value = dict(
        kind="cells.ecm_reference_failure_evidence@1",
        status="failed",
        input_sha256=hashlib.sha256(input_bytes).hexdigest(),
        mode=mode,
        refinement=refinement,
        error_type=type(error).__name__,
        error_message=str(error),
        partial=typed(getattr(error, "reference_partial", None)),
        available_result=typed(available_result),
        runtime=runtime,
        partial_values_recomputed=False,
        new_reference_forms=0,
        primary_result_is_not_accepted=True,
    )
    path = output.with_name("failure-" + output.name)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return path
