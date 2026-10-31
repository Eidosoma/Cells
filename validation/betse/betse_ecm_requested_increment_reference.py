"""Independent requested-junction increment with complete Decimal retention.

The existing source-equation reference runs at its declared100/160-digit
contexts. A mandatory observer saves every raw Decimal coefficient/state before
projection. No production, native or scientific package is imported here.
"""

import math
import struct
from collections.abc import Mapping
from decimal import Decimal

from validation.betse import betse_ecm_transport_reference as source

KEY = "junction_requested_outward_increment_mol_m3"
RAW_KIND = "cells.betse_ecm_complete_raw_decimal_reference@1"


def encode(value):
    if isinstance(value, Decimal):
        return dict(type="decimal", text=str(value))
    if type(value) is float:
        return dict(type="binary64", bits_be=struct.pack(">d", value).hex())
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError("Raw reference mappings require string keys")
        return dict(type="mapping", items=[[key, encode(item)] for key, item in value.items()])
    if type(value) in (tuple, list):
        return dict(
            type="tuple" if type(value) is tuple else "list", items=[encode(item) for item in value]
        )
    if value is None or type(value) in (str, int, bool):
        return value
    raise TypeError("Unsupported complete reference payload: " + type(value).__name__)


def decode(value):
    if not isinstance(value, dict):
        if value is None or type(value) in (str, int, bool):
            return value
        raise ValueError("Untagged raw numeric or container value")
    kind = value.get("type")
    if kind == "decimal" and set(value) == {"type", "text"}:
        return Decimal(value["text"])
    if kind == "binary64" and set(value) == {"type", "bits_be"}:
        bits = bytes.fromhex(value["bits_be"])
        if len(bits) != 8:
            raise ValueError("Require complete binary64 bits")
        return struct.unpack(">d", bits)[0]
    if kind in ("tuple", "list") and set(value) == {"type", "items"}:
        rows = [decode(item) for item in value["items"]]
        return tuple(rows) if kind == "tuple" else rows
    if kind == "mapping" and set(value) == {"type", "items"}:
        rows = value["items"]
        if any(
            type(row) is not list or len(row) != 2 or type(row[0]) is not str for row in rows
        ) or len({row[0] for row in rows}) != len(rows):
            raise ValueError("Require distinct complete ordered mapping entries")
        return {key: decode(item) for key, item in rows}
    raise ValueError("Invalid typed raw reference node")


def project(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {key: project(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [project(item) for item in value]
    return value


def counts(value):
    result = dict(
        decimal_values=0, binary64_values=0, containers=0, maximum_decimal_coefficient_digits=0
    )

    def visit(item):
        if isinstance(item, Decimal):
            result["decimal_values"] += 1
            result["maximum_decimal_coefficient_digits"] = max(
                result["maximum_decimal_coefficient_digits"], len(item.as_tuple().digits)
            )
        elif type(item) is float:
            result["binary64_values"] += 1
        elif isinstance(item, Mapping):
            result["containers"] += 1
            for child in item.values():
                visit(child)
        elif isinstance(item, (tuple, list)):
            result["containers"] += 1
            for child in item:
                visit(child)

    visit(value)
    return result


def evaluate(inputs, *, refinement=1, retain):
    if not callable(retain):
        raise ValueError("Complete raw Decimal retention is required in this validation scope")
    precision = {1: 100, 2: 160}.get(refinement)
    if precision is None:
        raise ValueError("Require declared reference precision")
    captured = []

    def capture(raw):
        payload = dict(
            kind=RAW_KIND,
            precision_digits=precision,
            counts=counts(raw),
            payload=encode(raw),
            binary64_projection_is_separate=True,
            source_nonce_binary64_rounding_retained=True,
        )
        retain("raw-decimal-" + str(precision), payload)
        captured.append(payload["counts"])

    projected = source.evaluate(inputs, refinement=refinement, retain_decimal=capture)
    retain("projected-reference-" + str(precision), projected)
    if (
        len(captured) != 1
        or captured[0]["decimal_values"] == 0
        or projected["precision"] != precision
    ):
        raise ValueError("Incomplete raw Decimal reference observation")
    return projected


def validate_payload(payload, projection):
    if payload["kind"] != RAW_KIND or payload["precision_digits"] not in (100, 160):
        raise ValueError("Incorrect raw reference identity")
    raw = decode(payload["payload"])
    if (
        raw["precision"] != payload["precision_digits"]
        or counts(raw) != payload["counts"]
        or encode(raw) != payload["payload"]
    ):
        raise ValueError("Changed complete raw Decimal payload or precision")
    if encode(project(raw)) != encode(projection):
        raise ValueError("Raw Decimal payload does not produce its complete binary64 projection")
    return raw


def finite_matrix(value):
    if (
        type(value) not in (list, tuple)
        or not value
        or any(type(row) not in (list, tuple) for row in value)
    ):
        raise ValueError("Require a rectangular requested-increment matrix")
    width = len(value[0])
    if not width or any(
        len(row) != width or any(type(v) not in (int, float) or not math.isfinite(v) for v in row)
        for row in value
    ):
        raise ValueError("Require finite requested increments with exact ion/cell axes")
    return len(value), width


def compare_increment(actual, expected):
    shape = finite_matrix(actual)
    if shape != finite_matrix(expected):
        raise ValueError("Requested-increment axes disagree")
    rows = []
    for i in range(shape[0]):
        for c in range(shape[1]):
            observed, target = float(actual[i][c]), float(expected[i][c])
            budget = 3e-13 + 6e-12 * abs(target)
            rows.append(
                dict(
                    ion_index=i,
                    cell_index=c,
                    actual=observed,
                    reference=target,
                    budget=budget,
                    error_over_budget=abs(observed - target) / budget,
                )
            )
    return dict(
        shape=list(shape),
        elements=rows,
        maximum_error_over_budget=max(row["error_over_budget"] for row in rows),
        fixed_absolute_floor=3e-13,
        fixed_relative=6e-12,
    )
