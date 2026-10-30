"""Unrun primitive recipes; original failed inputs retain their saved bits."""

import json
import math
import struct
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

REGRESSIONS = Path(__file__).with_name("stable_geometry_primitives_regressions.json")
BASE_CASES = (
    "retained-centroid",
    "retained-thin",
    "box-offset",
    "box-zero",
    "concave",
    "collinear-edge",
    "dynamic-range",
    "right",
    "thin-dyadic",
    "large-representable",
    "tiny-representable",
    "regular64-offset",
)
SCALE_CASES = (
    "scale-retained-centroid--80",
    "scale-retained-centroid--20",
    "scale-retained-centroid-20",
    "scale-retained-centroid-80",
    "scale-retained-thin--80",
    "scale-retained-thin--20",
    "scale-retained-thin-20",
    "scale-retained-thin-80",
    "scale-box-offset--80",
    "scale-box-offset--20",
    "scale-box-offset-20",
    "scale-box-offset-80",
    "scale-right--80",
    "scale-right--20",
    "scale-right-20",
    "scale-right-80",
)
POLYGON_ORDER_CASES = (
    "polygon-order-0",
    "polygon-order-1",
    "polygon-order-2",
    "polygon-order-3",
    "polygon-reverse-0",
    "polygon-reverse-1",
    "polygon-reverse-2",
    "polygon-reverse-3",
)
TRIANGLE_ORDER_CASES = (
    "triangle-order-012",
    "triangle-order-021",
    "triangle-order-102",
    "triangle-order-120",
    "triangle-order-201",
    "triangle-order-210",
)
TRANSLATION_CASES = (
    "translate-retained-centroid-large",
    "translate-retained-centroid-small",
    "translate-retained-thin-large",
    "translate-retained-thin-small",
    "translate-box-offset-large",
    "translate-box-offset-small",
    "translate-right-large",
    "translate-right-small",
)
COMBINED_CASES = (
    "combined-retained-centroid--40",
    "combined-retained-centroid-40",
    "combined-retained-thin--40",
    "combined-retained-thin-40",
)
CASES = (
    *BASE_CASES,
    *SCALE_CASES,
    *POLYGON_ORDER_CASES,
    *TRIANGLE_ORDER_CASES,
    *TRANSLATION_CASES,
    *COMBINED_CASES,
)
DOMAIN_CASES = (
    "triangle-collinear",
    "triangle-repeated",
    "polygon-collinear",
    "polygon-bowtie",
    "polygon-touching",
    "polygon-backtrack",
    "polygon-repeated",
    "too-few",
    "too-many",
    "wrong-axis",
    "nan",
    "infinity",
    "boolean",
    "large-integer",
    "unsupported-scalar",
    "unknown-primitive",
    "triangle-arity",
    "polygon-area-overflow",
    "polygon-area-underflow",
    "triangle-radius-overflow",
    "triangle-output-underflow",
)


def _decode(record):
    if record["dtype"] != "<f8":
        raise ValueError("Retained regression dtype changed")
    values = [value[0] for value in struct.iter_unpack("<d", bytes.fromhex(record["bits_C"]))]
    if record["shape"] == [2]:
        return values
    assert record["shape"][1] == 2 and len(values) == 2 * record["shape"][0]
    return [values[2 * i : 2 * i + 2] for i in range(record["shape"][0])]


def regression(name):
    with REGRESSIONS.open() as handle:
        rows = json.load(handle)["rows"]
    row = next(row for row in rows if row["name"] == name)
    points = (
        _decode(row["input"])
        if row["primitive"] == "polygon"
        else [_decode(row["input"][key]) for key in ("A", "B", "C")]
    )
    return row["primitive"], points, row


def _base(name):
    if name.startswith("retained-"):
        return regression(name)
    if name == "box-offset":
        points = [[1, 1], [3, 1], [3, 3], [1, 3]]
    elif name == "box-zero":
        points = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
    elif name == "concave":
        points = [[0, 0], [3, 0], [3, 1], [1, 1], [1, 3], [0, 3]]
    elif name == "collinear-edge":
        points = [[0, 0], [1, 0], [2, 0], [2, 1], [0, 1]]
    elif name == "dynamic-range":
        w, h = math.ldexp(1.0, 700), math.ldexp(1.0, -700)
        points = [[0, 0], [w, 0], [w, h], [0, h]]
    elif name == "regular64-offset":
        points = [
            [3 + math.cos(2 * math.pi * i / 64), 4 + math.sin(2 * math.pi * i / 64)]
            for i in range(64)
        ]
    else:
        if name == "right":
            points = [[1, 2], [4, 2], [1, 6]]
        elif name == "thin-dyadic":
            points = [[0, 0], [1, math.ldexp(1.0, -100)], [2, 0]]
        elif name in ("large-representable", "tiny-representable"):
            length = math.ldexp(1.0, 400 if name.startswith("large") else -400)
            points = [[0, 0], [length, 0], [0, length]]
        else:
            raise ValueError("Unknown manufactured base")
        return (
            "triangle",
            [[float(v) for v in p] for p in points],
            dict(classification="manufactured_binary64_input"),
        )
    return (
        "polygon",
        [[float(v) for v in p] for p in points],
        dict(classification="manufactured_binary64_input"),
    )


def _ratio(value):
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


def hex_points(points):
    return [[float(v).hex() for v in p] for p in points]


def case(name):
    if name not in CASES:
        raise ValueError("Require a declared primitive case")
    base, exponent, translation, permutation, orientation = name, 0, (0.0, 0.0), None, 1
    if name in SCALE_CASES or name in COMBINED_CASES:
        prefix = "scale-" if name in SCALE_CASES else "combined-"
        body = name.removeprefix(prefix)
        base = next(v for v in BASE_CASES if body.startswith(v + "-"))
        exponent = int(body.removeprefix(base + "-"))
        if name in COMBINED_CASES:
            translation = (math.ldexp(1.0, -20), -math.ldexp(1.0, -20))
    elif name in TRANSLATION_CASES:
        body = name.removeprefix("translate-")
        base = next(v for v in BASE_CASES if body.startswith(v + "-"))
        translation = (
            (math.ldexp(1.0, 20), -math.ldexp(1.0, 20))
            if name.endswith("large")
            else (-0.125, 0.25)
        )
    elif name in POLYGON_ORDER_CASES:
        base = "retained-centroid"
        offset = int(name.rsplit("-", 1)[1])
        order = list(range(4))
        if name.startswith("polygon-reverse-"):
            order.reverse()
            orientation = -1
        permutation = order[offset:] + order[:offset]
    elif name in TRIANGLE_ORDER_CASES:
        base = "retained-thin"
        permutation = [int(v) for v in name.rsplit("-", 1)[1]]
    kind, points, source = _base(base)
    original = [list(p) for p in points]
    if permutation is not None:
        points = [points[i] for i in permutation]
    quantization = []
    if exponent or any(translation):
        scale = Fraction(1 << exponent) if exponent >= 0 else Fraction(1, 1 << -exponent)
        moved = []
        for point in points:
            row = []
            for value, shift in zip(point, translation, strict=True):
                exact = Fraction.from_float(value) * scale + Fraction.from_float(shift)
                rounded = float(exact)
                quantization.append(_ratio(Fraction.from_float(rounded) - exact))
                row.append(rounded)
            moved.append(row)
        points = moved
    exact_transform = all(row["numerator"] == "0" for row in quantization)
    return (
        kind,
        points,
        dict(
            case=name,
            base=base,
            source=source,
            base_points_hex=hex_points(original),
            input_points_hex=hex_points(points),
            transform=dict(
                scale_exponent=exponent,
                translation_hex=[v.hex() for v in translation],
                permutation=permutation,
                polygon_orientation_factor=orientation,
                exact_binary64_input_transform=exact_transform,
                coordinate_quantization=quantization,
            ),
            rounded_transforms_are_new_inputs=not exact_transform,
            mathematical_native_equivalence=False,
            whole_mesh_credit=False,
        ),
    )


def domain(name):
    if name not in DOMAIN_CASES:
        raise ValueError("Require a declared refusal")
    kind, points, comparable = "polygon", [[0, 0], [1, 0], [0, 1]], True
    expected = None
    if name == "triangle-collinear":
        kind, points, expected = "triangle", [[0, 0], [1, 0], [2, 0]], "degenerate_triangle"
    elif name == "triangle-repeated":
        kind, points, expected = "triangle", [[0, 0], [1, 0], [0, 0]], "repeated_vertex"
    elif name == "polygon-collinear":
        points, expected = [[0, 0], [1, 0], [2, 0], [3, 0]], "degenerate_polygon"
    elif name == "polygon-bowtie":
        points, expected = [[0, 0], [2, 2], [0, 2], [2, 0]], "non_simple_polygon"
    elif name == "polygon-touching":
        points, expected = [[0, 0], [2, 0], [2, 2], [1, 0], [0, 2]], "non_simple_polygon"
    elif name == "polygon-backtrack":
        points, expected = [[0, 0], [2, 0], [1, 0], [2, 1], [0, 1]], "overlapping_adjacent_edges"
    elif name == "polygon-repeated":
        points, expected = [[0, 0], [1, 0], [1, 1], [0, 0]], "repeated_vertex"
    elif name in ("polygon-area-overflow", "polygon-area-underflow"):
        length = math.ldexp(1.0, 600 if name.endswith("overflow") else -600)
        points = [[0, 0], [length, 0], [length, length], [0, length]]
        expected = "unrepresentable_output"
    elif name == "triangle-radius-overflow":
        kind, points, expected = (
            "triangle",
            [[0, 0], [math.ldexp(1.0, 700), 0], [math.ldexp(1.0, 699), math.ldexp(1.0, -700)]],
            "unrepresentable_output",
        )
    elif name == "triangle-output-underflow":
        length = float.fromhex("0x0.0000000000001p-1022")
        kind, points, expected = (
            "triangle",
            [[0, 0], [length, 0], [0, length]],
            "unrepresentable_output",
        )
    else:
        comparable = False
        if name == "too-few":
            points, expected = [[0, 0], [1, 0]], "point_count"
        elif name == "too-many":
            points, expected = [[0, 0]] * 65, "point_count"
        elif name == "wrong-axis":
            points, expected = [[0, 0, 0]] * 3, "point_axis"
        elif name in ("nan", "infinity", "boolean", "large-integer", "unsupported-scalar"):
            value = {
                "nan": float("nan"),
                "infinity": float("inf"),
                "boolean": True,
                "large-integer": 2**54,
                "unsupported-scalar": Decimal("1.25"),
            }[name]
            points[0][0], expected = value, "finite_binary64_scalar"
        elif name == "unknown-primitive":
            kind, expected = "quadrilateral_circle", "unknown_primitive"
        elif name == "triangle-arity":
            kind, points, expected = "triangle", [[0, 0], [1, 0], [1, 1], [0, 1]], "triangle_arity"
    return kind, points, dict(case=name, expected=expected, independent_geometric_domain=comparable)
