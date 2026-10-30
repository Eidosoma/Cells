"""Versioned host geometry primitives; no native or whole-mesh substitution."""

import hashlib
import json
import math
import struct
import sys
from dataclasses import dataclass, replace
from fractions import Fraction

LAW_ID = "cells_stable_binary64_geometry_primitives@1"
REQUEST_KIND = "cells.stable_geometry_primitive_request@1"
RESULT_KIND = "cells.stable_geometry_primitive_result@1"
MAX_VERTICES = 64
MAX_ULPS = 32
SQRT_BITS = (80, 160, 320, 640, 1280, 2560, 5120, 8192)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _ratio(value):
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


def _bits(value):
    return struct.pack(">d", value).hex()


class GeometryRejected(ValueError):
    def __init__(self, code, *, stage, detail=None, trial=None):
        super().__init__(code + " at " + stage)
        self.code, self.stage, self.detail, self.trial = code, stage, detail, trial


class _Uncertain(ArithmeticError):
    pass


@dataclass(frozen=True, slots=True)
class Request:
    primitive: str
    points: tuple
    identity: str


@dataclass(frozen=True, slots=True)
class Result:
    request_identity: str
    quantities: tuple
    method: str
    certificates_json: str
    provenance_json: str
    identity: str

    @property
    def values(self):
        return dict(self.quantities)

    @property
    def certificates(self):
        return json.loads(self.certificates_json)

    @property
    def provenance(self):
        return json.loads(self.provenance_json)


def request_record(request):
    return dict(
        kind=REQUEST_KIND,
        law=LAW_ID,
        primitive=request.primitive,
        points_binary64_hex=[[v.hex() for v in row] for row in request.points],
        maximum_certified_ulps=MAX_ULPS,
        native_equivalence=False,
        whole_mesh_credit=False,
        topology_qualified=False,
    )


def make_request(primitive, points):
    if type(primitive) is not str or primitive not in ("polygon", "triangle"):
        raise GeometryRejected("unknown_primitive", stage="input")
    if type(points) not in (tuple, list) or not 3 <= len(points) <= MAX_VERTICES:
        raise GeometryRejected("point_count", stage="input")
    if primitive == "triangle" and len(points) != 3:
        raise GeometryRejected("triangle_arity", stage="input")
    normalized = []
    for row in points:
        if type(row) not in (tuple, list) or len(row) != 2:
            raise GeometryRejected("point_axis", stage="input")
        values = []
        for value in row:
            if type(value) is int and abs(value) <= 2**53:
                value = float(value)
            if type(value) is not float or not math.isfinite(value):
                raise GeometryRejected("finite_binary64_scalar", stage="input")
            values.append(value)
        normalized.append(tuple(values))
    request = Request(primitive, tuple(normalized), "")
    return replace(request, identity=_digest(request_record(request)))


@dataclass(frozen=True, slots=True)
class _I:
    value: float
    lo: float
    hi: float

    @classmethod
    def point(cls, value):
        return cls(value, value, value)

    @classmethod
    def outward(cls, value, lo, hi):
        if not all(math.isfinite(v) for v in (value, lo, hi)):
            raise _Uncertain("float_range")
        low, high = math.nextafter(lo, -math.inf), math.nextafter(hi, math.inf)
        if not math.isfinite(low) or not math.isfinite(high):
            raise _Uncertain("outward_range")
        return cls(value, low, high)

    def __add__(self, other):
        return self.outward(self.value + other.value, self.lo + other.lo, self.hi + other.hi)

    def __sub__(self, other):
        if self.lo == self.hi == other.lo == other.hi:
            return self.point(0.0)
        return self.outward(self.value - other.value, self.lo - other.hi, self.hi - other.lo)

    def __mul__(self, other):
        if self.lo == self.hi == 0 or other.lo == other.hi == 0:
            return self.point(0.0)
        terms = (self.lo * other.lo, self.lo * other.hi, self.hi * other.lo, self.hi * other.hi)
        return self.outward(self.value * other.value, min(terms), max(terms))

    def __truediv__(self, other):
        if other.lo <= 0 <= other.hi:
            raise _Uncertain("denominator_sign_unresolved")
        terms = (self.lo / other.lo, self.lo / other.hi, self.hi / other.lo, self.hi / other.hi)
        return self.outward(self.value / other.value, min(terms), max(terms))

    def square(self):
        lower = 0.0 if self.lo <= 0 <= self.hi else min(self.lo * self.lo, self.hi * self.hi)
        upper = max(self.lo * self.lo, self.hi * self.hi)
        value = self.outward(self.value * self.value, lower, upper)
        return replace(value, lo=max(0.0, value.lo))

    def sqrt(self):
        if self.lo < 0:
            raise _Uncertain("sqrt_sign_unresolved")
        low, _ = _sqrt_float_bounds(self.lo)
        _, high = _sqrt_float_bounds(self.hi)
        return _I(math.sqrt(self.value), low, high)

    def absolute(self):
        if self.lo >= 0:
            return self
        if self.hi <= 0:
            return self.point(-1.0) * self
        raise _Uncertain("absolute_sign_unresolved")


def _sum(values):
    values = tuple(values)
    try:
        interval = _I.point(0.0)
        for value in values:
            interval = interval + value
        return replace(interval, value=math.fsum(v.value for v in values))
    except (OverflowError, ValueError) as error:
        raise _Uncertain("sum_range") from error


def _sqrt_float_bounds(value):
    approximate = math.sqrt(value)
    low = max(0.0, math.nextafter(approximate, -math.inf))
    high = math.nextafter(approximate, math.inf)
    if not math.isfinite(high):
        raise _Uncertain("sqrt_range")
    numerator, denominator = value.as_integer_ratio()
    ln, ld = low.as_integer_ratio()
    hn, hd = high.as_integer_ratio()
    if ln * ln * denominator > numerator * ld * ld or hn * hn * denominator < numerator * hd * hd:
        raise _Uncertain("libm_sqrt_not_bracketed")
    return low, high


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b, strict=True))


def _fraction_points(points):
    return tuple(tuple(Fraction.from_float(v) for v in row) for row in points)


def _orient(a, b, c, counters):
    counters["orientation_filters"] += 1
    try:
        aa, bb, cc = (tuple(_I.point(v) for v in p) for p in (a, b, c))
        value = _cross(_sub(bb, aa), _sub(cc, aa))
        if value.lo > 0:
            return 1
        if value.hi < 0:
            return -1
    except (ArithmeticError, ValueError):
        pass
    counters["exact_orientation_fallbacks"] += 1
    aa, bb, cc = _fraction_points((a, b, c))
    value = _cross(_sub(bb, aa), _sub(cc, aa))
    return (value > 0) - (value < 0)


def _between(a, b, point):
    return all(min(x, y) <= z <= max(x, y) for x, y, z in zip(a, b, point, strict=True))


def _domain(request, counters):
    points = request.points
    if len(set(points)) != len(points):
        raise GeometryRejected("repeated_vertex", stage="domain")
    if request.primitive == "triangle":
        if not _orient(*points, counters):
            raise GeometryRejected("degenerate_triangle", stage="domain")
        return
    n = len(points)
    turns = [_orient(points[i - 1], points[i], points[(i + 1) % n], counters) for i in range(n)]
    if not any(turns):
        raise GeometryRejected("degenerate_polygon", stage="domain")
    for i, turn in enumerate(turns):
        if turn == 0 and not _between(points[i - 1], points[(i + 1) % n], points[i]):
            raise GeometryRejected("overlapping_adjacent_edges", stage="domain")
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            c, d = points[j], points[(j + 1) % n]
            o1, o2 = _orient(a, b, c, counters), _orient(a, b, d, counters)
            o3, o4 = _orient(c, d, a, counters), _orient(c, d, b, counters)
            crossing = o1 * o2 < 0 and o3 * o4 < 0
            touching = (
                (o1 == 0 and _between(a, b, c))
                or (o2 == 0 and _between(a, b, d))
                or (o3 == 0 and _between(c, d, a))
                or (o4 == 0 and _between(c, d, b))
            )
            if crossing or touching:
                raise GeometryRejected("non_simple_polygon", stage="domain")


def _polygon(points):
    origin = points[0]
    local = [_sub(p, origin) for p in points]
    terms = [_cross(local[i], local[i + 1]) for i in range(1, len(points) - 1)]
    twice = _sum(terms)
    denominator = _I.point(3.0) * twice
    centre = tuple(
        origin[axis]
        + _sum((local[i][axis] + local[i + 1][axis]) * term for i, term in enumerate(terms, 1))
        / denominator
        for axis in range(2)
    )
    return dict(
        centroid_x_m=centre[0], centroid_y_m=centre[1], signed_area_m2=twice / _I.point(2.0)
    )


def _triangle(points):
    a, b, c = points
    u, v = _sub(b, a), _sub(c, a)
    determinant = _cross(u, v)
    u2, v2 = _sum(x.square() for x in u), _sum(x.square() for x in v)
    denominator = _I.point(2.0) * determinant
    offset = ((u2 * v[1] - v2 * u[1]) / denominator, (u[0] * v2 - v[0] * u2) / denominator)
    radius = _sum(x.square() for x in offset).sqrt()
    sides = [_sum(x.square() for x in edge).sqrt() for edge in (u, v, _sub(v, u))]
    area2 = determinant.absolute()
    return dict(
        circumcenter_x_m=a[0] + offset[0],
        circumcenter_y_m=a[1] + offset[1],
        circumradius_m=radius,
        inradius_m=area2 / _sum(sides),
        area_m2=area2 / _I.point(2.0),
    )


def _certify(values):
    certificates = {}
    for name, value in values.items():
        if value.value == 0 and (value.lo != 0 or value.hi != 0):
            raise _Uncertain("zero_coordinate_unresolved:" + name)
        error = math.nextafter(
            max(abs(value.value - value.lo), abs(value.hi - value.value)), math.inf
        )
        if not math.isfinite(error) or error > MAX_ULPS * math.ulp(value.value):
            raise _Uncertain("output_enclosure_too_wide:" + name)
        certificates[name] = dict(
            kind="outward_binary64_interval",
            lower_hex=value.lo.hex(),
            upper_hex=value.hi.hex(),
            maximum_ulps=MAX_ULPS,
        )
    return {k: v.value for k, v in values.items()}, certificates


def _round(value, name):
    try:
        rounded = float(value)
    except OverflowError as error:
        raise GeometryRejected(
            "unrepresentable_output", stage=name, detail=_ratio(value)
        ) from error
    if not math.isfinite(rounded) or (rounded == 0 and value != 0):
        raise GeometryRejected("unrepresentable_output", stage=name, detail=_ratio(value))
    return 0.0 if value == 0 else rounded


def _sqrt_bounds(value, bits):
    if value <= 0:
        raise GeometryRejected("nonpositive_radicand", stage="exact_sqrt")
    numerator, denominator = value.numerator, value.denominator
    exponent = numerator.bit_length() - denominator.bit_length()
    if (
        (numerator < denominator << exponent)
        if exponent >= 0
        else (numerator << -exponent < denominator)
    ):
        exponent -= 1
    shift = bits - exponent // 2
    nn = numerator << (2 * shift) if shift >= 0 else numerator
    dd = denominator if shift >= 0 else denominator << (-2 * shift)
    root = math.isqrt(nn // dd)
    unit = Fraction(1, 1 << shift) if shift >= 0 else Fraction(1 << -shift)
    lower = root * unit
    upper = lower if root * root * dd == nn else lower + unit
    return lower, upper


def _irrational(bounds, name):
    last = None
    for bits in SQRT_BITS:
        lower, upper = bounds(bits)
        last = dict(lower=_ratio(lower), upper=_ratio(upper), precision_bits=bits)
        try:
            lo = float(lower)
        except OverflowError as error:
            raise GeometryRejected("unrepresentable_output", stage=name, detail=last) from error
        try:
            hi = float(upper)
        except OverflowError:
            continue
        if _bits(lo) == _bits(hi):
            if not math.isfinite(lo) or lo == 0:
                raise GeometryRejected("unrepresentable_output", stage=name, detail=last)
            return lo, dict(kind="resolved_dyadic_sqrt_interval", **last)
    raise GeometryRejected("rounding_not_resolved", stage=name, detail=last)


def _exact(request):
    points = _fraction_points(request.points)
    certificates = {}
    if request.primitive == "polygon":
        origin = points[0]
        local = [_sub(p, origin) for p in points]
        terms = [_cross(local[i], local[i + 1]) for i in range(1, len(points) - 1)]
        twice = sum(terms, Fraction(0))
        if not twice:
            raise GeometryRejected("degenerate_polygon", stage="exact_area")
        centre = [
            origin[axis]
            + sum(
                ((local[i][axis] + local[i + 1][axis]) * term for i, term in enumerate(terms, 1)),
                Fraction(0),
            )
            / (3 * twice)
            for axis in range(2)
        ]
        exact = dict(centroid_x_m=centre[0], centroid_y_m=centre[1], signed_area_m2=twice / 2)
    else:
        a, b, c = points
        u, v = _sub(b, a), _sub(c, a)
        determinant = _cross(u, v)
        if not determinant:
            raise GeometryRejected("degenerate_triangle", stage="exact_area")
        u2, v2 = sum((x * x for x in u), Fraction(0)), sum((x * x for x in v), Fraction(0))
        offset = (
            (u2 * v[1] - v2 * u[1]) / (2 * determinant),
            (u[0] * v2 - v[0] * u2) / (2 * determinant),
        )
        exact = dict(
            circumcenter_x_m=a[0] + offset[0],
            circumcenter_y_m=a[1] + offset[1],
            area_m2=abs(determinant) / 2,
        )
        squared_radius = sum((x * x for x in offset), Fraction(0))
        radius, radius_certificate = _irrational(
            lambda bits: _sqrt_bounds(squared_radius, bits), "circumradius_m"
        )
        squared_sides = [sum((x * x for x in edge), Fraction(0)) for edge in (u, v, _sub(v, u))]

        def inradius_bounds(bits):
            intervals = [_sqrt_bounds(q, bits) for q in squared_sides]
            return abs(determinant) / sum(hi for _, hi in intervals), abs(determinant) / sum(
                lo for lo, _ in intervals
            )

        inradius, inradius_certificate = _irrational(inradius_bounds, "inradius_m")
        certificates.update(circumradius_m=radius_certificate, inradius_m=inradius_certificate)
    values = {name: _round(value, name) for name, value in exact.items()}
    certificates.update(
        {
            name: dict(kind="correctly_rounded_binary_rational", exact=_ratio(value))
            for name, value in exact.items()
        }
    )
    if request.primitive == "triangle":
        values.update(circumradius_m=radius, inradius_m=inradius)
    return values, certificates


def result_record(result):
    return dict(
        kind=RESULT_KIND,
        law=LAW_ID,
        request_identity=result.request_identity,
        quantities_binary64_hex={name: value.hex() for name, value in result.quantities},
        method=result.method,
        certificates=result.certificates,
        provenance=result.provenance,
        native_equivalence=False,
        whole_mesh_credit=False,
        topology_qualified=False,
        physical_geometry_admitted=False,
    )


def prepare(request):
    if type(request) is not Request:
        raise GeometryRejected("request_type", stage="input")
    if type(request.points) is not tuple or any(type(row) is not tuple for row in request.points):
        raise GeometryRejected("mutable_request_points", stage="identity")
    if any(type(v) is not float or not math.isfinite(v) for row in request.points for v in row):
        raise GeometryRejected("noncanonical_request_scalar", stage="identity")
    expected = make_request(request.primitive, request.points)
    if request.identity != expected.identity or request_record(request) != request_record(expected):
        raise GeometryRejected("changed_request", stage="identity")
    counters = dict(orientation_filters=0, exact_orientation_fallbacks=0)
    fallback = None
    try:
        if (
            sys.float_info.radix,
            sys.float_info.mant_dig,
            sys.float_info.max_exp,
            sys.float_info.min_exp,
        ) != (2, 53, 1024, -1021):
            raise GeometryRejected("unsupported_float_platform", stage="platform")
        tiny = float.fromhex("0x0.0000000000001p-1022")
        one, half = 1.0, math.ldexp(1.0, -53)
        if (
            tiny + tiny != float.fromhex("0x0.0000000000002p-1022")
            or one + half != one
            or one + 1.5 * half != math.nextafter(one, math.inf)
        ):
            raise GeometryRejected("unsupported_float_environment", stage="platform")
        _domain(request, counters)
        try:
            points = [tuple(_I.point(v) for v in p) for p in request.points]
            candidates = (_polygon if request.primitive == "polygon" else _triangle)(points)
            values, certificates = _certify(candidates)
            if (request.primitive == "polygon" and values["signed_area_m2"] == 0) or (
                request.primitive == "triangle"
                and any(values[k] <= 0 for k in ("area_m2", "inradius_m", "circumradius_m"))
            ):
                raise _Uncertain("positive_measure_unresolved")
            method = "filtered_float64_outward_intervals"
        except (ArithmeticError, ValueError) as error:
            fallback = str(error)
            values, certificates = _exact(request)
            method = (
                "exact_binary_rational"
                if request.primitive == "polygon"
                else "exact_binary_rational_and_dyadic_sqrt"
            )
    except GeometryRejected as error:
        error.trial = dict(
            request=request_record(request),
            status="retained_primitive_refusal",
            code=error.code,
            stage=error.stage,
            detail=error.detail,
            fallback_reason=fallback,
            predicates=counters,
            native_equivalence=False,
            topology_qualified=False,
        )
        raise
    provenance = dict(
        policy=LAW_ID,
        floating_environment="binary64_nearest_even_with_gradual_underflow",
        fallback_reason=fallback,
        predicates=counters,
        maximum_fast_path_ulps=MAX_ULPS,
        exact_sqrt_precision_cap_bits=SQRT_BITS[-1],
        primitive_only=True,
        acceleration_qualified=False,
        native_primitives_changed=False,
        original_failed_campaign_reclassified=False,
    )
    result = Result(
        request.identity,
        tuple(sorted(values.items())),
        method,
        _json(certificates),
        _json(provenance),
        "",
    )
    return replace(result, identity=_digest(result_record(result)))


def validate(request, result):
    if type(result) is not Result:
        raise GeometryRejected("result_type", stage="identity")
    if type(result.quantities) is not tuple or any(
        type(row) is not tuple
        or len(row) != 2
        or type(row[0]) is not str
        or type(row[1]) is not float
        or not math.isfinite(row[1])
        for row in result.quantities
    ):
        raise GeometryRejected("mutable_or_untyped_result", stage="identity")
    expected = prepare(request)
    try:
        if result.identity != expected.identity or result_record(result) != result_record(expected):
            raise GeometryRejected("changed_result", stage="identity")
    except (TypeError, AttributeError, ValueError, OverflowError) as error:
        raise GeometryRejected("changed_result", stage="identity") from error
    return result
