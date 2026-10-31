"""Bounded manufactured cell/bath rectangles with explicit cleft widths.

Fresh caller seed owners, widths, bath slots and domain define a new physical
geometry law. No prior full-domain cells, native maps or operators are adopted.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType

from cells.processes import finite_ecm_polygon_geometry as finite

LAW_ID = "cells_explicit_cleft_width_tensor_grid_cell_bath_partition@1"
INPUT_KIND = "cells.explicit_cleft_width_cell_bath_partition_declaration@1"
MAX_CELLS_PER_AXIS = 4
MAX_REGIONS = 32
SOURCE_PINS = {
    "finite_ecm_polygon_geometry.py": (
        "9769a8ec6e2816fa3b4d939c6b0f4d0518b01a7ec6679e9090442d984534c925"
    ),
    "conservative_polygon_geometry.py": (
        "5d267b20cdb3a05f4f036bbc3fa6978b40780ca4394f67ac6c33a8b605af4b0d"
    ),
    "stable_geometry_primitives.py": (
        "c9fab4f34aa9166711431844f2af72eb6b8fe4873154bfe01dfce3f656326958"
    ),
}
INVALIDATED = (
    "all_prior_full_domain_control_volumes_and_physical_geometry_bindings",
    "all_native_nearest_environment_membrane_gap_and_boundary_maps",
    "all_old_metrics_capacitances_operators_Hodge_stores_and_inverses",
    "all_old_physical_inventories_solver_initialization_and_loop_bindings",
)


def plain(value):
    if isinstance(value, Fraction):
        return dict(numerator=str(value.numerator), denominator=str(value.denominator))
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: plain(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(child) for child in value]
    return value


def freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(child) for key, child in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(child) for child in value)
    return value


def record(value):
    if type(value) is float:
        return dict(binary64_hex=value.hex())
    if isinstance(value, Mapping):
        return {key: record(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [record(child) for child in value]
    return value


def digest(value):
    return hashlib.sha256(
        json.dumps(
            record(plain(value)), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Request:
    declaration: object
    identity: str


@dataclass(frozen=True)
class Candidate:
    request_identity: str
    partition_request: finite.Request
    partition_binding: finite.Binding
    construction: object
    owner_maps: object
    conservation: object
    provenance: object
    identity: str


class ConstructionRejected(ValueError):
    def __init__(self, reason, *, stage, original=None, partial=None):
        super().__init__("Explicit cell/bath construction refused at " + stage + ": " + str(reason))
        self.stage, self.original, self.partial = stage, original, partial


def _keys(value, expected, label):
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise ValueError("Complete exact fields required: " + label)


def _number(value, *, positive=False):
    if type(value) is not float or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError("Explicit finite binary64 metre values required; widths must be positive")
    if value == 0 and math.copysign(1.0, value) < 0:
        raise ValueError("Signed-zero geometry input is outside this declared manufactured law")
    return value


def _slot(value, nx, ny):
    if (
        not isinstance(value, (tuple, list))
        or len(value) != 2
        or any(type(v) is not int for v in value)
        or not 0 <= value[0] < nx
        or not 0 <= value[1] < ny
    ):
        raise ValueError("Complete bounded integer owner slot required")
    return tuple(value)


def _declaration(value):
    _keys(
        value,
        {
            "kind",
            "opted_in_law",
            "source",
            "domain",
            "layout",
            "cell_owners",
            "bath_owners",
            "height_m",
            "membrane_thickness_m",
            "units",
            "membrane_geometry_policy",
            "face_distance_policy",
            "boundary_policy",
            "rounding_policy",
            "old_cache_policy",
            "scope",
        },
        "declaration",
    )
    if (
        value["kind"] != INPUT_KIND
        or value["opted_in_law"] != LAW_ID
        or value["units"] != finite.UNITS
        or value["scope"]
        != "new_manufactured_cell_and_bath_geometry_no_native_or_prior_cell_equivalence"
        or value["rounding_policy"] != "all_grid_lines_exact_binary64_declared_widths_exact@1"
        or value["membrane_geometry_policy"] != "zero_volume_interface_explicit_path@1"
        or value["face_distance_policy"] != "orthogonal_volume_centroids_shared_face@1"
        or value["boundary_policy"] != "sealed_no_transport@1"
    ):
        raise ValueError(
            "Explicit new manufactured geometry, SI, width, face and boundary laws required"
        )
    _keys(value["old_cache_policy"], {"kind", "provided_cached_operators"}, "old cache policy")
    if (
        value["old_cache_policy"]["kind"] != "invalidate_all_prior_geometry_and_operators@1"
        or value["old_cache_policy"]["provided_cached_operators"] is not None
    ):
        raise ValueError("Prior geometry/caches/operators cannot be reused or reclassified")
    source = value["source"]
    _keys(
        source,
        {
            "kind",
            "authority",
            "document_sha256",
            "field",
            "prior_full_domain_cells_reclassified",
            "native_equivalence",
        },
        "seed provenance",
    )
    if (
        source["kind"] != "explicit_manufactured_seed_owners@1"
        or source["native_equivalence"] is not False
        or source["prior_full_domain_cells_reclassified"] is not False
        or any(type(source[key]) is not str or not source[key] for key in ("authority", "field"))
        or type(source["document_sha256"]) is not str
        or len(source["document_sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in source["document_sha256"])
    ):
        raise ValueError(
            "Fresh explicit manufactured seed provenance required; "
            "no prior-cell or native promotion"
        )
    domain = value["domain"]
    _keys(domain, {"id", "vertices_m", "authority_field"}, "caller domain")
    finite.exact._id(domain["id"])
    if type(domain["authority_field"]) is not str or not domain["authority_field"]:
        raise ValueError("Caller domain document field required")
    ring = domain["vertices_m"]
    if not isinstance(ring, (tuple, list)) or len(ring) != 4:
        raise ValueError("This bounded law requires one explicit axis-aligned rectangular domain")
    if any(not isinstance(row, (tuple, list)) or len(row) != 2 for row in ring):
        raise ValueError("Complete rectangular domain coordinate pairs required")
    for point in ring:
        for v in point:
            _number(v)
    (left, bottom), (right, bottom2), (right2, top), (left2, top2) = ring
    if not (left == left2 < right == right2 and bottom == bottom2 < top == top2):
        raise ValueError("Only a CCW axis-aligned rectangle starting at lower-left is supported")
    layout = value["layout"]
    _keys(
        layout,
        {
            "x_centres_m",
            "y_centres_m",
            "cell_half_width_x_m",
            "cell_half_width_y_m",
            "cleft_width_x_m",
            "cleft_width_y_m",
        },
        "explicit offsets and clefts",
    )
    nx, ny = len(layout["x_centres_m"]), len(layout["y_centres_m"])
    if (
        not 1 <= nx <= MAX_CELLS_PER_AXIS
        or not 1 <= ny <= MAX_CELLS_PER_AXIS
        or (2 * nx + 1) * (2 * ny + 1) > MAX_REGIONS
    ):
        raise ValueError(
            "Bounded tensor layout requires 1..4 cells per axis and at most32 total regions"
        )
    for axis, count in (("x", nx), ("y", ny)):
        for field, length, positive in (
            (axis + "_centres_m", count, False),
            ("cell_half_width_" + axis + "_m", count, True),
            ("cleft_width_" + axis + "_m", count + 1, True),
        ):
            rows = layout[field]
            if not isinstance(rows, (tuple, list)) or len(rows) != length:
                raise ValueError(
                    "Every cell offset and outer/interior cleft width is explicitly required"
                )
            for v in rows:
                _number(v, positive=positive)
        if any(
            a >= b
            for a, b in zip(
                layout[axis + "_centres_m"], layout[axis + "_centres_m"][1:], strict=False
            )
        ):
            raise ValueError("Seed coordinate axes must be strictly increasing")
    cells, baths = value["cell_owners"], value["bath_owners"]
    if (
        not isinstance(cells, (tuple, list))
        or len(cells) != nx * ny
        or not isinstance(baths, (tuple, list))
        or len(baths) != (2 * nx + 1) * (2 * ny + 1) - nx * ny
    ):
        raise ValueError("Complete separate cell-seed and positive bath-slot owner axes required")
    cell_slots, bath_slots, ids = set(), set(), []
    for row in cells:
        _keys(row, {"id", "seed_xy_m", "slot"}, "retained manufactured seed")
        ids.append(finite.exact._id(row["id"]))
        i, j = _slot(row["slot"], nx, ny)
        if (i, j) in cell_slots:
            raise ValueError("Duplicate cell seed slot")
        cell_slots.add((i, j))
        if digest(row["seed_xy_m"]) != digest([layout["x_centres_m"][i], layout["y_centres_m"][j]]):
            raise ValueError(
                "Complete retained seed coordinate bits must match its declared tensor slot"
            )
    for row in baths:
        _keys(row, {"id", "slot"}, "explicit bath slot")
        ids.append(finite.exact._id(row["id"]))
        slot = _slot(row["slot"], 2 * nx + 1, 2 * ny + 1)
        if slot in bath_slots or (slot[0] % 2 == slot[1] % 2 == 1):
            raise ValueError("Duplicate bath slot or reclassification of a cell slot")
        bath_slots.add(slot)
    if len(set(ids)) != len(ids):
        raise ValueError("Distinct unchanged cell and new bath owner IDs required")
    _number(value["height_m"], positive=True)
    _number(value["membrane_thickness_m"], positive=True)
    return freeze(plain(value))


def bind(declaration):
    declared = _declaration(declaration)
    return Request(declared, digest((LAW_ID, declared)))


class _Work:
    def __init__(self, observer):
        self.observer, self.events, self.partial = observer, [], {}

    def emit(self, stage, value):
        if self.observer is not None:
            self.observer(stage, plain(value))

    def grid(self, axis, index, exact):
        trial = dict(sequence=len(self.events), axis=axis, index=index, input_exact=plain(exact))
        self.events.append(trial)
        self.emit("grid_line_input", trial)
        value = finite.exact.arithmetic._round(exact, "explicit_ECM_grid_line")
        trial["returned"] = dict(value=value, binary64_hex=value.hex(), exact_target=plain(exact))
        self.emit("grid_line_return", trial)
        if Fraction.from_float(value) != exact:
            raise ValueError(
                "A declared width would change after binary64 projection; exact grid lines required"
            )
        return value


def _axis(layout, axis, lower, upper, work):
    centers = list(map(Fraction.from_float, layout[axis + "_centres_m"]))
    halves = list(map(Fraction.from_float, layout["cell_half_width_" + axis + "_m"]))
    gaps = list(map(Fraction.from_float, layout["cleft_width_" + axis + "_m"]))
    exact = [Fraction.from_float(lower)]
    for center, half in zip(centers, halves, strict=True):
        exact.extend((center - half, center + half))
    exact.append(Fraction.from_float(upper))
    if any(a >= b for a, b in zip(exact, exact[1:], strict=False)):
        raise ValueError("Cell offsets collapse, overlap or meet the selected outer domain")
    actual_gaps = [exact[2 * i + 1] - exact[2 * i] for i in range(len(gaps))]
    if actual_gaps != gaps:
        raise ValueError(
            "Explicit outer/intercellular cleft widths must exactly match seed offsets and domain"
        )
    stored = [work.grid(axis, i, value) for i, value in enumerate(exact)]
    return (
        exact,
        stored,
        dict(
            requested_cleft_widths=plain(gaps),
            realized_cleft_widths=plain(actual_gaps),
            requested_half_widths=plain(halves),
            realized_half_widths=plain(
                [(exact[2 * i + 2] - exact[2 * i + 1]) / 2 for i in range(len(halves))]
            ),
        ),
    )


def _vertex(i, j):
    return "explicit-ecm-v-" + str(i) + "-" + str(j)


def _raw(request, xs, ys):
    d = request.declaration
    nx, ny = len(xs) - 1, len(ys) - 1
    cells = {
        (2 * row["slot"][0] + 1, 2 * row["slot"][1] + 1): row["id"] for row in d["cell_owners"]
    }
    baths = {tuple(row["slot"]): row["id"] for row in d["bath_owners"]}
    regions = [
        dict(
            id=cells.get((i, j), baths.get((i, j))),
            kind="cell" if (i, j) in cells else "bath",
            vertex_ids=[_vertex(i, j), _vertex(i + 1, j), _vertex(i + 1, j + 1), _vertex(i, j + 1)],
        )
        for j in range(ny)
        for i in range(nx)
    ]
    domain = (
        [_vertex(i, 0) for i in range(nx)]
        + [_vertex(nx, j) for j in range(ny)]
        + [_vertex(i, ny) for i in range(nx, 0, -1)]
        + [_vertex(0, j) for j in range(ny, 0, -1)]
    )
    boundary = []
    for row in regions:
        ring = row["vertex_ids"]
        for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
            if any((a, b) == (u, v) for u, v in zip(domain, domain[1:] + domain[:1], strict=True)):
                boundary.append(
                    dict(region_id=row["id"], vertex_ids=[a, b], condition=d["boundary_policy"])
                )
    return dict(
        source=dict(
            kind="explicit_cell_bath_partition@1",
            generator=LAW_ID,
            provenance=dict(
                constructor_request_identity=request.identity,
                seed_source=plain(d["source"]),
                caller_domain=plain(d["domain"]),
                width_policy="explicit_cell_half_widths_and_every_outer_internal_cleft_width",
                new_physical_geometry=True,
                prior_full_domain_cells_reclassified=False,
                native_equivalence=False,
            ),
        ),
        vertices=[
            dict(id=_vertex(i, j), xy_m=[x, y]) for j, y in enumerate(ys) for i, x in enumerate(xs)
        ],
        domain_vertex_ids=domain,
        regions=regions,
        boundary=boundary,
        height_m=d["height_m"],
        membrane_thickness_m=d["membrane_thickness_m"],
        membrane_geometry_policy=d["membrane_geometry_policy"],
        face_distance_policy=d["face_distance_policy"],
        axial_caps=d["boundary_policy"],
        units=plain(d["units"]),
    )


def _measure_targets(raw):
    points = {row["id"]: tuple(map(Fraction.from_float, row["xy_m"])) for row in raw["vertices"]}
    height = Fraction.from_float(raw["height_m"])
    rows = []
    for region in raw["regions"]:
        a, _, c, _ = (points[name] for name in region["vertex_ids"])
        area = (c[0] - a[0]) * (c[1] - a[1])
        rows.append(
            dict(
                id=region["id"],
                area_m2_exact=plain(area),
                volume_m3_exact=plain(area * height),
                centroid_m_exact=plain([(a[k] + c[k]) / 2 for k in (0, 1)]),
            )
        )
    return rows


def _conservation(raw, geometry):
    points = {row["id"]: tuple(map(Fraction.from_float, row["xy_m"])) for row in raw["vertices"]}
    height = Fraction.from_float(raw["height_m"])
    rows = []
    for region in raw["regions"]:
        ring = [points[name] for name in region["vertex_ids"]]
        area = finite.exact._moments(ring)[0]
        normals = [
            (b[1] - a[1], a[0] - b[0]) for a, b in zip(ring, ring[1:] + ring[:1], strict=True)
        ]
        closure = [sum((normal[k] for normal in normals), Fraction(0)) for k in (0, 1)]
        moments = [
            [
                sum(
                    (
                        ((a[i] + b[i]) / 2) * normal[j]
                        for a, b, normal in zip(ring, ring[1:] + ring[:1], normals, strict=True)
                    ),
                    Fraction(0),
                )
                for j in (0, 1)
            ]
            for i in (0, 1)
        ]
        if closure != [0, 0] or moments != [[area, 0], [0, area]]:
            raise ValueError("Exact constant/affine flux conservation failed")
        rows.append(
            dict(
                id=region["id"],
                kind=region["kind"],
                area_m2_exact=plain(area),
                volume_m3_exact=plain(area * height),
                integrated_line_normals_m=plain(normals),
                constant_flux_closure_m=plain(closure),
                affine_flux_moments_m2=plain(moments),
            )
        )

    def ratio(row):
        return Fraction(int(row["numerator"]), int(row["denominator"]))

    cell_area = sum(
        (ratio(row["area_m2_exact"]) for row in rows if row["kind"] == "cell"), Fraction(0)
    )
    bath_area = sum(
        (ratio(row["area_m2_exact"]) for row in rows if row["kind"] == "bath"), Fraction(0)
    )
    domain_area = finite.exact._moments([points[name] for name in raw["domain_vertex_ids"]])[0]
    if cell_area + bath_area != domain_area or min(cell_area, bath_area) <= 0:
        raise ValueError("Positive cell/bath coverage and exact area exhaustion required")
    return dict(
        regions=rows,
        cell_area_m2_exact=plain(cell_area),
        bath_area_m2_exact=plain(bath_area),
        domain_area_m2_exact=plain(domain_area),
        coverage_defect_m2_exact=plain(cell_area + bath_area - domain_area),
        domain_volume_m3_exact=plain(domain_area * height),
        region_volume_sum_m3_exact=plain((cell_area + bath_area) * height),
        membrane_incidence_column_sums=[
            sum(row[i] for row in geometry["membrane_incidence"])
            for i in range(len(geometry["membranes"]))
        ],
        face_incidence_column_sums=[
            sum(row[i] for row in geometry["face_incidence"]) for i in range(len(geometry["faces"]))
        ],
        rounded_area_readout_sum_defect_m2=plain(
            sum((Fraction.from_float(row["area_m2"]) for row in geometry["regions"]), Fraction(0))
            - domain_area
        ),
        rounded_volume_readout_sum_defect_m3=plain(
            sum((Fraction.from_float(row["volume_m3"]) for row in geometry["regions"]), Fraction(0))
            - domain_area * height
        ),
        binary64_store_sums_exactly_claimed=False,
        trajectory_conservation_claimed=False,
    )


def candidate_record(value):
    return (
        LAW_ID,
        value.request_identity,
        value.partition_request,
        value.partition_binding,
        value.construction,
        value.owner_maps,
        value.conservation,
        value.provenance,
    )


def prepare(request, *, observer=None):
    work = _Work(observer)
    stage = "complete_explicit_input"
    try:
        if type(request) is not Request or digest(bind(request.declaration)) != digest(request):
            raise ValueError("Complete owned unaltered constructor request required")
        for name, module in (
            ("finite_ecm_polygon_geometry.py", finite),
            ("conservative_polygon_geometry.py", finite.exact),
            ("stable_geometry_primitives.py", finite.exact.arithmetic),
        ):
            if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != SOURCE_PINS[name]:
                raise ValueError("Changed frozen cell/bath construction dependency: " + name)
        work.emit(stage, request)
        d = request.declaration
        ring = d["domain"]["vertices_m"]
        stage = "exact_widths_and_shared_grid_lines"
        xe, xs, xc = _axis(d["layout"], "x", ring[0][0], ring[1][0], work)
        ye, ys, yc = _axis(d["layout"], "y", ring[0][1], ring[2][1], work)
        raw = _raw(request, xs, ys)
        work.partial["partition_input"] = raw
        work.emit("partition_input", raw)
        targets = _measure_targets(raw)
        work.partial["region_measure_targets"] = targets
        work.emit("region_measure_targets", targets)
        stage = "existing_finite_ECM_geometry_admission"
        bound = finite.from_partition(raw, law_id=finite.LAW_ID)
        work.partial["partition_request"] = plain(bound)
        work.emit("partition_request", bound)
        geometry = finite.prepare(bound)
        work.partial["partition_binding"] = plain(geometry)
        work.emit("partition_binding", geometry)
        g = geometry.geometry
        region_index = {row["id"]: i for i, row in enumerate(g["regions"])}
        maps = dict(
            seed_owners=[
                dict(
                    source_index=i,
                    owner_id=row["id"],
                    slot=list(row["slot"]),
                    seed_binary64_hex=[v.hex() for v in row["seed_xy_m"]],
                    geometry_cell_index=g["cell_ids"].index(row["id"]),
                    geometry_region_index=region_index[row["id"]],
                )
                for i, row in enumerate(d["cell_owners"])
            ],
            bath_owners=[
                dict(
                    source_index=i,
                    owner_id=row["id"],
                    slot=list(row["slot"]),
                    geometry_bath_index=g["bath_ids"].index(row["id"]),
                    geometry_region_index=region_index[row["id"]],
                )
                for i, row in enumerate(d["bath_owners"])
            ],
            cell_or_bath_owner_reclassification_performed=False,
            nearest_midpoint_or_native_grid_maps_reused=False,
        )
        construction = dict(
            x_grid_exact=plain(xe),
            y_grid_exact=plain(ye),
            width_checks=dict(x=xc, y=yc),
            grid_line_events=work.events,
            region_measure_targets=targets,
            counts=dict(
                seed_owners=len(d["cell_owners"]),
                bath_owners=len(d["bath_owners"]),
                vertices=len(raw["vertices"]),
                regions=len(raw["regions"]),
                grid_lines=len(xs) + len(ys),
                membranes=len(g["membranes"]),
                bath_faces=len(g["faces"]),
                boundary_edges=len(g["boundary"]),
            ),
        )
        provenance = dict(
            kind="cells.explicit_cleft_cell_bath_geometry_constructor@1",
            law=LAW_ID,
            seed_source=plain(d["source"]),
            caller_domain=plain(d["domain"]),
            source_pins=SOURCE_PINS,
            finite_ECM_geometry_law=finite.LAW_ID,
            positive_cell_bath_geometry_prepared=True,
            independent_construction_and_geometry_checks_required=True,
            physical_model_prepared=False,
            native_equivalence=False,
            prior_full_domain_cells_reclassified=False,
            old_caches_or_operators_admitted=False,
            ordinary_ECM_loop_ready=False,
            scientific_qualification_inherited=False,
            biological_calibration=False,
            solver_trajectory_executed=False,
            invalidated=INVALIDATED,
        )
        stage = "exact_coverage_and_conservation"
        conservation = _conservation(raw, g)
        value = Candidate(
            request.identity,
            bound,
            geometry,
            freeze(plain(construction)),
            freeze(plain(maps)),
            freeze(plain(conservation)),
            freeze(plain(provenance)),
            "",
        )
        result = replace(value, identity=digest(candidate_record(value)))
        work.emit("candidate", result)
        return result
    except Exception as error:
        raise ConstructionRejected(
            str(error),
            stage=stage,
            original=plain(request),
            partial=plain(
                dict(
                    completed=work.partial,
                    grid_line_events=work.events,
                    source_error=dict(
                        type=type(error).__name__,
                        reason=str(error),
                        trial=getattr(error, "trial", None),
                        detail=getattr(error, "detail", None),
                    ),
                )
            ),
        ) from error


def validate(request, candidate):
    if type(candidate) is not Candidate or digest(prepare(request)) != digest(candidate):
        raise ValueError(
            "Changed complete constructor input, partition geometry, owners, evidence or seal"
        )
    return candidate


def require_physical_admission(_candidate):
    raise ValueError(
        "New positive cell/bath geometry still requires independent qualification "
        "and caller physical admission"
    )


def require_cached_operators(_candidate):
    raise ValueError(
        "All prior geometry, operators and native environment bindings are invalidated"
    )
