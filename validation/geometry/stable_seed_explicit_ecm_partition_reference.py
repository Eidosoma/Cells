"""Independent cumulative-width construction and complete finite-ECM geometry.

No production or scientific module is imported. New targets use integer ratios,
the extracted frozen integer-grid/ear lane and complete certificate inventories.
"""

import argparse
import hashlib
import importlib.abc
import json
import math
import os
import sys
import traceback
from decimal import localcontext
from pathlib import Path

DENIED = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "PIL", "torch"}


class NoScience(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in DENIED:
            raise ImportError("Independent explicit ECM constructor denies " + fullname)


sys.meta_path.insert(0, NoScience())
if DENIED & {name.split(".")[0] for name in sys.modules}:
    raise ImportError("Independent constructor requires a clean fresh process")

from validation.geometry import (  # noqa: E402
    stable_seed_explicit_ecm_partition_geometry_reference as geometry,  # noqa: E402
)

LAW = "cells_explicit_cleft_width_tensor_grid_cell_bath_partition@1"
INPUT_KIND = "cells.explicit_cleft_width_cell_bath_partition_declaration@1"
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
GEOMETRY_REFERENCE_SHA256 = "91e6d01931bb5856b2604c4b7348b3cf6d70e2737a75784b008495e6b025d251"
INVALIDATED = [
    "all_prior_full_domain_control_volumes_and_physical_geometry_bindings",
    "all_native_nearest_environment_membrane_gap_and_boundary_maps",
    "all_old_metrics_capacitances_operators_Hodge_stores_and_inverses",
    "all_old_physical_inventories_solver_initialization_and_loop_bindings",
]
polygon = geometry.polygon


def require(value, reason):
    if not value:
        raise ValueError(reason)


def same(actual, expected, label):
    require(type(actual) is type(expected), "Wrong complete field type: " + label)
    if type(expected) is dict:
        require(set(actual) == set(expected), "Incomplete/extra fields: " + label)
        for key, value in expected.items():
            same(actual[key], value, label + "/" + str(key))
    elif type(expected) is list:
        require(len(actual) == len(expected), "Incomplete/extra axis: " + label)
        for i, (a, b) in enumerate(zip(actual, expected, strict=True)):
            same(a, b, label + "/" + str(i))
    elif type(expected) is float:
        require(actual.hex() == expected.hex(), "Different binary64 bits: " + label)
    else:
        require(actual == expected, "Different field: " + label)


def keys(value, expected, label):
    require(
        type(value) is dict and set(value) == set(expected), "Incomplete/extra fields: " + label
    )


def record(value):
    if type(value) is float:
        return dict(binary64_hex=value.hex())
    if type(value) is dict:
        return {key: record(v) for key, v in value.items()}
    if type(value) in (list, tuple):
        return [record(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(
        json.dumps(record(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def json_record(text, limit):
    require(
        type(text) is str and len(text.encode("utf-8")) <= limit, "Bounded original JSON required"
    )

    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Nonfinite JSON constant: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def number(value, positive=False):
    require(
        type(value) is float and math.isfinite(value) and (not positive or value > 0),
        "Explicit finite binary64 metre value; positive widths",
    )
    require(value != 0 or math.copysign(1.0, value) > 0, "Signed-zero input unsupported")
    return geometry.ratio(value)


def identifier(value):
    require(
        type(value) is str and 1 <= len(value) <= 128 and all(33 <= ord(c) <= 126 for c in value),
        "Explicit stable owner ID",
    )


def authenticate(request):
    keys(request, {"declaration", "identity"}, "constructor request")
    d = request["declaration"]
    keys(
        d,
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
        "complete caller declaration",
    )
    expected = dict(
        kind=INPUT_KIND,
        opted_in_law=LAW,
        units=dict(coordinates="m", height="m", membrane_path="m", area="m2", volume="m3"),
        membrane_geometry_policy="zero_volume_interface_explicit_path@1",
        face_distance_policy="orthogonal_volume_centroids_shared_face@1",
        boundary_policy="sealed_no_transport@1",
        rounding_policy="all_grid_lines_exact_binary64_declared_widths_exact@1",
        old_cache_policy=dict(
            kind="invalidate_all_prior_geometry_and_operators@1", provided_cached_operators=None
        ),
        scope="new_manufactured_cell_and_bath_geometry_no_native_or_prior_cell_equivalence",
    )
    for key, value in expected.items():
        same(d[key], value, "explicit law/units/policy " + key)
    source = d["source"]
    keys(
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
    require(
        source["kind"] == "explicit_manufactured_seed_owners@1"
        and source["prior_full_domain_cells_reclassified"] is False
        and source["native_equivalence"] is False,
        "Fresh manufactured owners only",
    )
    require(
        all(type(source[k]) is str and bool(source[k]) for k in ("authority", "field")),
        "Explicit source authority/field",
    )
    pin = source["document_sha256"]
    require(
        type(pin) is str and len(pin) == 64 and all(c in "0123456789abcdef" for c in pin),
        "Source document hash",
    )
    domain = d["domain"]
    keys(domain, {"id", "vertices_m", "authority_field"}, "explicit domain")
    identifier(domain["id"])
    require(
        type(domain["authority_field"]) is str and bool(domain["authority_field"]),
        "Explicit domain authority field",
    )
    points = domain["vertices_m"]
    require(
        type(points) is list
        and len(points) == 4
        and all(type(p) is list and len(p) == 2 for p in points),
        "CCW rectangular domain",
    )
    for p in points:
        for v in p:
            number(v)
    left, bottom = points[0]
    right, top = points[2]
    require(left < right and bottom < top, "Positive domain extents")
    same(
        points,
        [[left, bottom], [right, bottom], [right, top], [left, top]],
        "axis-aligned CCW domain",
    )
    layout = d["layout"]
    keys(
        layout,
        {
            "x_centres_m",
            "y_centres_m",
            "cell_half_width_x_m",
            "cell_half_width_y_m",
            "cleft_width_x_m",
            "cleft_width_y_m",
        },
        "all explicit widths",
    )
    nx, ny = len(layout["x_centres_m"]), len(layout["y_centres_m"])
    require(
        1 <= nx <= 4 and 1 <= ny <= 4 and (2 * nx + 1) * (2 * ny + 1) <= 32,
        "Bounded manufactured tensor layout",
    )
    for axis, count in (("x", nx), ("y", ny)):
        for field, length, positive in (
            (axis + "_centres_m", count, False),
            ("cell_half_width_" + axis + "_m", count, True),
            ("cleft_width_" + axis + "_m", count + 1, True),
        ):
            require(
                type(layout[field]) is list and len(layout[field]) == length,
                "Complete per-axis width inventory",
            )
            for v in layout[field]:
                number(v, positive)
        require(
            all(
                a < b
                for a, b in zip(
                    layout[axis + "_centres_m"], layout[axis + "_centres_m"][1:], strict=False
                )
            ),
            "Increasing seed centers",
        )
    number(d["height_m"], True)
    number(d["membrane_thickness_m"], True)
    cellslots, bathslots, ids = set(), set(), []
    require(
        type(d["cell_owners"]) is list and len(d["cell_owners"]) == nx * ny,
        "Every original seed owner",
    )
    require(
        type(d["bath_owners"]) is list
        and len(d["bath_owners"]) == (2 * nx + 1) * (2 * ny + 1) - nx * ny,
        "Every positive bath slot owner",
    )
    for family, limits, slotset in (
        ("cell_owners", (nx, ny), cellslots),
        ("bath_owners", (2 * nx + 1, 2 * ny + 1), bathslots),
    ):
        for row in d[family]:
            keys(
                row,
                {"id", "slot"} | ({"seed_xy_m"} if family == "cell_owners" else set()),
                "complete owner row",
            )
            identifier(row["id"])
            ids.append(row["id"])
            slot = row["slot"]
            require(
                type(slot) is list
                and len(slot) == 2
                and all(
                    type(v) is int and 0 <= v < limit for v, limit in zip(slot, limits, strict=True)
                ),
                "Bounded integer slot",
            )
            require(tuple(slot) not in slotset, "Distinct owner slots")
            slotset.add(tuple(slot))
            if family == "cell_owners":
                same(
                    row["seed_xy_m"],
                    [layout["x_centres_m"][slot[0]], layout["y_centres_m"][slot[1]]],
                    "retained seed bits",
                )
            else:
                require(
                    not (slot[0] % 2 == slot[1] % 2 == 1), "Bath does not reclassify a cell slot"
                )
    require(len(ids) == len(set(ids)), "Distinct unchanged cell and bath IDs")
    same(request["identity"], digest([LAW, d]), "complete request seal")
    return d


def cumulative_axis(d, axis, lower, upper, events):
    layout = d["layout"]
    halves = [geometry.ratio(v) for v in layout["cell_half_width_" + axis + "_m"]]
    gaps = [geometry.ratio(v) for v in layout["cleft_width_" + axis + "_m"]]
    cuts = [geometry.ratio(lower)]
    for i, half in enumerate(halves):
        left = geometry.add(cuts[-1], gaps[i])
        center = geometry.add(left, half)
        same(
            center,
            geometry.ratio(layout[axis + "_centres_m"][i]),
            "cumulative widths retain seed center",
        )
        cuts.extend((left, geometry.add(center, half)))
    end = geometry.add(cuts[-1], gaps[-1])
    same(end, geometry.ratio(upper), "all explicit widths exhaust declared axis")
    cuts.append(end)
    stored = []
    for i, q in enumerate(cuts):
        value = geometry.number(q)
        same(geometry.ratio(value), q, "exact representability preserves width")
        events.append(
            dict(
                sequence=len(events),
                axis=axis,
                index=i,
                input_exact=q,
                returned=dict(value=value, binary64_hex=value.hex(), exact_target=q),
            )
        )
        stored.append(value)
    return (
        cuts,
        stored,
        dict(
            requested_cleft_widths=gaps,
            realized_cleft_widths=gaps,
            requested_half_widths=halves,
            realized_half_widths=halves,
        ),
    )


def vertex(i, j):
    return "explicit-ecm-v-" + str(i) + "-" + str(j)


def partition(request, d, xs, ys):
    nx, ny = len(xs) - 1, len(ys) - 1
    roles = {}
    for row in d["cell_owners"]:
        roles[(2 * row["slot"][0] + 1, 2 * row["slot"][1] + 1)] = (row["id"], "cell")
    for row in d["bath_owners"]:
        roles[tuple(row["slot"])] = (row["id"], "bath")
    regions = []
    for j in range(ny):
        for i in range(nx):
            name, kind = roles[(i, j)]
            regions.append(
                dict(
                    id=name,
                    kind=kind,
                    vertex_ids=[vertex(i + a, j + b) for a, b in ((0, 0), (1, 0), (1, 1), (0, 1))],
                )
            )
    incidence = {}
    for region in regions:
        for a, b in polygon._edges(region["vertex_ids"]):
            incidence.setdefault(tuple(sorted((a, b))), []).append((region["id"], a, b))
    exterior = [rows[0] for rows in incidence.values() if len(rows) == 1]
    forward = {a: b for _, a, b in exterior}
    cursor = vertex(0, 0)
    domain = []
    while cursor not in domain:
        domain.append(cursor)
        cursor = forward[cursor]
    require(cursor == domain[0] and len(domain) == len(exterior), "One complete ordered outer ring")
    boundary = [
        dict(region_id=name, vertex_ids=[a, b], condition=d["boundary_policy"])
        for name, a, b in exterior
    ]
    return dict(
        source=dict(
            kind="explicit_cell_bath_partition@1",
            generator=LAW,
            provenance=dict(
                constructor_request_identity=request["identity"],
                seed_source=d["source"],
                caller_domain=d["domain"],
                width_policy="explicit_cell_half_widths_and_every_outer_internal_cleft_width",
                new_physical_geometry=True,
                prior_full_domain_cells_reclassified=False,
                native_equivalence=False,
            ),
        ),
        vertices=[
            dict(id=vertex(i, j), xy_m=[x, y]) for j, y in enumerate(ys) for i, x in enumerate(xs)
        ],
        domain_vertex_ids=domain,
        regions=regions,
        boundary=boundary,
        height_m=d["height_m"],
        membrane_thickness_m=d["membrane_thickness_m"],
        membrane_geometry_policy=d["membrane_geometry_policy"],
        face_distance_policy=d["face_distance_policy"],
        axial_caps=d["boundary_policy"],
        units=d["units"],
    )


def total(values):
    answer = polygon._ratio(0)
    for value in values:
        answer = geometry.add(answer, value)
    return answer


def conservation(raw, primary):
    scale = int(primary["integer_scale"])
    points = {
        row["id"]: tuple(n * (scale // dd) for n, dd in (v.as_integer_ratio() for v in row["xy_m"]))
        for row in raw["vertices"]
    }
    rows = []
    for region in raw["regions"]:
        ring = [points[name] for name in region["vertex_ids"]]
        normals = [(b[1] - a[1], a[0] - b[0]) for a, b in polygon._edges(ring)]
        closure = [polygon._ratio(sum(n[k] for n in normals), scale) for k in (0, 1)]
        moments = [
            [
                polygon._ratio(
                    sum(
                        (a[i] + b[i]) * n[j]
                        for (a, b), n in zip(polygon._edges(ring), normals, strict=True)
                    ),
                    2 * scale * scale,
                )
                for j in (0, 1)
            ]
            for i in (0, 1)
        ]
        target = primary["regions"][region["id"]]
        same(closure, [polygon._ratio(0), polygon._ratio(0)], "independent constant flux closure")
        same(
            moments,
            [[target["area"], polygon._ratio(0)], [polygon._ratio(0), target["area"]]],
            "independent affine flux moments",
        )
        rows.append(
            dict(
                id=region["id"],
                kind=region["kind"],
                area_m2_exact=target["area"],
                volume_m3_exact=target["volume"],
                integrated_line_normals_m=[[polygon._ratio(v, scale) for v in n] for n in normals],
                constant_flux_closure_m=closure,
                affine_flux_moments_m2=moments,
            )
        )
    cells = total(row["area_m2_exact"] for row in rows if row["kind"] == "cell")
    baths = total(row["area_m2_exact"] for row in rows if row["kind"] == "bath")
    rounded_area = total(
        geometry.ratio(geometry.number(row["area"])) for row in primary["regions"].values()
    )
    rounded_volume = total(
        geometry.ratio(geometry.number(row["volume"])) for row in primary["regions"].values()
    )
    return dict(
        regions=rows,
        cell_area_m2_exact=cells,
        bath_area_m2_exact=baths,
        domain_area_m2_exact=primary["domain_area"],
        coverage_defect_m2_exact=polygon._ratio(0),
        domain_volume_m3_exact=primary["domain_volume"],
        region_volume_sum_m3_exact=primary["domain_volume"],
        membrane_incidence_column_sums=[0] * len(primary["membranes"]),
        face_incidence_column_sums=[0] * len(primary["faces"]),
        rounded_area_readout_sum_defect_m2=geometry.subtract(rounded_area, primary["domain_area"]),
        rounded_volume_readout_sum_defect_m3=geometry.subtract(
            rounded_volume, primary["domain_volume"]
        ),
        binary64_store_sums_exactly_claimed=False,
        trajectory_conservation_claimed=False,
    )


def derive(request, partial):
    require(
        hashlib.sha256(Path(geometry.__file__).read_bytes()).hexdigest()
        == GEOMETRY_REFERENCE_SHA256,
        "Changed frozen geometry-only reference lane",
    )
    partial["stage"] = "independent_complete_input"
    d = authenticate(request)
    ring = d["domain"]["vertices_m"]
    events = []
    partial["grid_line_events"] = events
    partial["stage"] = "independent_cumulative_x_grid"
    xe, xs, xc = cumulative_axis(d, "x", ring[0][0], ring[1][0], events)
    partial["x_axis"] = dict(grid_exact=xe, grid_stored=xs, width_checks=xc)
    partial["stage"] = "independent_cumulative_y_grid"
    ye, ys, yc = cumulative_axis(d, "y", ring[0][1], ring[2][1], events)
    partial["y_axis"] = dict(grid_exact=ye, grid_stored=ys, width_checks=yc)
    raw = partition(request, d, xs, ys)
    partial.update(stage="independent_complete_integer_grid_geometry", partition_input=raw)
    partial["stage"] = "independent_primary_geometry"
    primary = geometry.evaluate(raw, refinement=1)
    partial["primary"] = primary
    partial["stage"] = "independent_refined_geometry"
    refined = geometry.evaluate(raw, refinement=2)
    partial["refined"] = refined
    partial["stage"] = "independent_owner_maps"
    indices = {row["id"]: i for i, row in enumerate(raw["regions"])}
    maps = dict(
        seed_owners=[
            dict(
                source_index=i,
                owner_id=row["id"],
                slot=row["slot"],
                seed_binary64_hex=[v.hex() for v in row["seed_xy_m"]],
                geometry_cell_index=primary["cell_ids"].index(row["id"]),
                geometry_region_index=indices[row["id"]],
            )
            for i, row in enumerate(d["cell_owners"])
        ],
        bath_owners=[
            dict(
                source_index=i,
                owner_id=row["id"],
                slot=row["slot"],
                geometry_bath_index=primary["bath_ids"].index(row["id"]),
                geometry_region_index=indices[row["id"]],
            )
            for i, row in enumerate(d["bath_owners"])
        ],
        cell_or_bath_owner_reclassification_performed=False,
        nearest_midpoint_or_native_grid_maps_reused=False,
    )
    partial["owner_maps"] = maps
    construction = dict(
        x_grid_exact=xe,
        y_grid_exact=ye,
        width_checks=dict(x=xc, y=yc),
        grid_line_events=events,
        region_measure_targets=[
            dict(
                id=row["id"],
                area_m2_exact=primary["regions"][row["id"]]["area"],
                volume_m3_exact=primary["regions"][row["id"]]["volume"],
                centroid_m_exact=primary["regions"][row["id"]]["centroid"],
            )
            for row in raw["regions"]
        ],
        counts=dict(
            seed_owners=len(d["cell_owners"]),
            bath_owners=len(d["bath_owners"]),
            vertices=len(raw["vertices"]),
            regions=len(raw["regions"]),
            grid_lines=len(xs) + len(ys),
            membranes=len(primary["membranes"]),
            bath_faces=len(primary["faces"]),
            boundary_edges=len(primary["boundary"]),
        ),
    )
    partial["construction"] = construction
    provenance = dict(
        kind="cells.explicit_cleft_cell_bath_geometry_constructor@1",
        law=LAW,
        seed_source=d["source"],
        caller_domain=d["domain"],
        source_pins=SOURCE_PINS,
        finite_ECM_geometry_law="cells_finite_ecm_conforming_polygon_partition@1",
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
    partial["provenance"] = provenance
    partial["stage"] = "independent_conservation_and_complete_return"
    return dict(
        partition_input=raw,
        primary=primary,
        refined=refined,
        construction=construction,
        owner_maps=maps,
        conservation=conservation(raw, primary),
        provenance=provenance,
        production_functions_called=False,
        independent_width_construction=(
            "cumulative clefts and full cell widths from lower domain bounds"
        ),
    )


def vector2(value, label):
    require(
        type(value) is list
        and len(value) == 2
        and all(type(v) is float and math.isfinite(v) for v in value),
        "Exact two-component binary64 vector: " + label,
    )


def certificate(value, *, root=False, sign=False, zero=False):
    expected = (
        {"kind", "exact"}
        if not root or zero
        else {"kind", "lower", "upper", "precision_bits", "radicand"}
    )
    keys(value, expected | ({"sign"} if sign else set()), "complete metric certificate")
    if sign:
        require(
            type(value["sign"]) is int and value["sign"] in (-1, 1), "Exact integer tangent sign"
        )
    if root and not zero:
        require(
            type(value["precision_bits"]) is int
            and value["precision_bits"] in (80, 160, 320, 640, 1280, 2560, 5120, 8192),
            "Declared interval precision",
        )
    for field in ("exact", "lower", "upper", "radicand"):
        if field in value:
            keys(value[field], {"numerator", "denominator"}, "canonical ratio")
            same(
                value[field],
                polygon._ratio(*polygon._pair(value[field])),
                "canonical reduced ratio",
            )


def quantity(
    label, actual, target, cert, primary, refined, *, root=False, sign=1, unit=False, signed=False
):
    require(type(actual) is float and math.isfinite(actual), "Finite binary64 metric: " + label)
    certificate(cert, root=root, sign=signed, zero=int(target["numerator"]) == 0)
    values = []
    for reference in (primary, refined):
        with localcontext() as ctx:
            ctx.prec = reference["precision_digits"]
            value = polygon._decimal(target)
            values.append(str(sign * (value.sqrt() if root else value)))
    return polygon._quantity(
        label,
        actual,
        *values,
        exact=None if root else target,
        squared=target if root else None,
        sign=sign,
        certificate=cert,
        unit=unit,
    )


def compare_geometry(raw, g, primary, refined):
    keys(
        g,
        {
            "kind",
            "law",
            "request_identity",
            "source",
            "vertices",
            "domain_vertex_ids",
            "regions",
            "cell_ids",
            "bath_ids",
            "edges",
            "half_edges",
            "membranes",
            "faces",
            "boundary",
            "owner_axis",
            "membrane_incidence",
            "face_incidence",
            "height_m",
            "membrane_thickness_m",
            "domain_area_exact",
            "domain_volume_exact",
            "units",
            "face_distance_policy",
            "membrane_geometry_policy",
            "axial_caps",
            "native_equivalence",
            "qualification_inherited",
            "cell_cell_contacts_supported",
            "outer_transport_supported",
        },
        "all finite-ECM geometry fields",
    )
    expected_metadata = dict(
        kind="cells.finite_ecm_polygon_binding@1",
        law="cells_finite_ecm_conforming_polygon_partition@1",
        source=raw["source"],
        vertices=raw["vertices"],
        domain_vertex_ids=raw["domain_vertex_ids"],
        height_m=raw["height_m"],
        membrane_thickness_m=raw["membrane_thickness_m"],
        units=raw["units"],
        face_distance_policy=raw["face_distance_policy"],
        membrane_geometry_policy=raw["membrane_geometry_policy"],
        axial_caps=raw["axial_caps"],
        native_equivalence=False,
        qualification_inherited=False,
        cell_cell_contacts_supported=False,
        outer_transport_supported=False,
    )
    same(
        {key: g[key] for key in expected_metadata},
        expected_metadata,
        "all geometry provenance/units/gates",
    )
    for family in ("regions", "edges", "membranes", "faces", "boundary"):
        expected = (
            list(primary["regions"])
            if family == "regions"
            else [row["id"] for row in primary[family]]
        )
        same([row["id"] for row in g[family]], expected, "complete ordered " + family)
    base = geometry.compare_geometry(raw, g, primary, refined)
    quantities = []
    edge_targets = {row["id"]: row for row in primary["edges"]}
    edge_actual = {row["id"]: row for row in g["edges"]}
    for row in g["regions"]:
        keys(
            row,
            {"id", "kind", "vertex_ids", "area_m2", "volume_m3", "centroid_m", "certificates"},
            "region",
        )
        keys(row["certificates"], {"area", "volume", "centroid"}, "region certificates")
        vector2(row["centroid_m"], "region centroid")
        require(
            type(row["certificates"]["centroid"]) is list
            and len(row["certificates"]["centroid"]) == 2,
            "Centroid certificate axis",
        )
        target = primary["regions"][row["id"]]
        for field, key in (("area_m2", "area"), ("volume_m3", "volume")):
            quantities.append(
                quantity(
                    row["id"] + "/" + field,
                    row[field],
                    target[key],
                    row["certificates"][key],
                    primary,
                    refined,
                )
            )
        for i in (0, 1):
            quantities.append(
                quantity(
                    row["id"] + "/centroid/" + str(i),
                    row["centroid_m"][i],
                    target["centroid"][i],
                    row["certificates"]["centroid"][i],
                    primary,
                    refined,
                )
            )
    for row in g["edges"]:
        keys(
            row,
            {
                "id",
                "vertex_ids",
                "region_ids",
                "length_m",
                "area_m2",
                "midpoint_m",
                "tangent_xy",
                "normal_xy",
                "certificates",
                "interface_kind",
                "interface_id",
            },
            "edge",
        )
        keys(row["certificates"], {"length", "area", "midpoint", "tangent"}, "edge certificates")
        for field in ("midpoint_m", "tangent_xy", "normal_xy"):
            vector2(row[field], "edge " + field)
        for field in ("midpoint", "tangent"):
            require(
                type(row["certificates"][field]) is list and len(row["certificates"][field]) == 2,
                "Edge certificate axes",
            )
        target = edge_targets[row["id"]]
        for field, key in (("length_m", "length"), ("area_m2", "area")):
            quantities.append(
                quantity(
                    row["id"] + "/" + field,
                    row[field],
                    target[key + "_squared"],
                    row["certificates"][key],
                    primary,
                    refined,
                    root=True,
                )
            )
        tangent = []
        for i in (0, 1):
            quantities.append(
                quantity(
                    row["id"] + "/midpoint/" + str(i),
                    row["midpoint_m"][i],
                    target["midpoint"][i],
                    row["certificates"]["midpoint"][i],
                    primary,
                    refined,
                )
            )
            quantities.append(
                quantity(
                    row["id"] + "/tangent/" + str(i),
                    row["tangent_xy"][i],
                    target["tangent_squared"][i],
                    row["certificates"]["tangent"][i],
                    primary,
                    refined,
                    root=True,
                    sign=target["tangent_sign"][i],
                    unit=True,
                    signed=True,
                )
            )
            tangent.append(
                target["tangent_sign"][i] * geometry.number(target["tangent_squared"][i], root=True)
            )
        same(row["tangent_xy"], tangent, "independent tangent bits")
        same(row["normal_xy"], [tangent[1], -tangent[0]], "independent normal bits")
    for family in ("membranes", "faces", "boundary"):
        targets = {row["id"]: row for row in primary[family]}
        expected_fields = {"id", "edge_id", "vertex_ids", "area_m2", "normal_xy", "tangent_xy"} | (
            {"cell_id", "bath_id", "thickness_m"}
            if family == "membranes"
            else {
                "sender",
                "receiver",
                "length_m",
                "centroid_to_face_m",
                "common_projection_m",
                "certificates",
            }
            if family == "faces"
            else {"region_id", "condition"}
        )
        for row in g[family]:
            keys(row, expected_fields, family + " row")
            for field in ("normal_xy", "tangent_xy"):
                vector2(row[field], family + " " + field)
            require(
                type(row["area_m2"]) is float and math.isfinite(row["area_m2"]), "Finite route area"
            )
            edge = edge_actual[row["edge_id"]]
            direction = 1 if row["vertex_ids"] == edge["vertex_ids"] else -1
            for field in ("normal_xy", "tangent_xy"):
                same(
                    row[field],
                    [direction * v for v in edge[field]],
                    "complete directed route vector",
                )
            if family == "membranes":
                same(row["thickness_m"], raw["membrane_thickness_m"], "explicit membrane path")
            if family == "faces":
                target = targets[row["id"]]
                vector2(row["centroid_to_face_m"], "face side distances")
                vector2(row["common_projection_m"], "face projection")
                keys(
                    row["certificates"],
                    {"length", "centroid_to_face", "common_projection"},
                    "face certificates",
                )
                for key in ("centroid_to_face", "common_projection"):
                    require(
                        type(row["certificates"][key]) is list
                        and len(row["certificates"][key]) == 2,
                        "Complete face certificate axes",
                    )
                quantities.append(
                    quantity(
                        row["id"] + "/distance",
                        row["length_m"],
                        target["length_squared"],
                        row["certificates"]["length"],
                        primary,
                        refined,
                        root=True,
                    )
                )
                for i in (0, 1):
                    quantities.append(
                        quantity(
                            row["id"] + "/side/" + str(i),
                            row["centroid_to_face_m"][i],
                            target["centroid_to_face_squared"][i],
                            row["certificates"]["centroid_to_face"][i],
                            primary,
                            refined,
                            root=True,
                        )
                    )
                    quantities.append(
                        quantity(
                            row["id"] + "/projection/" + str(i),
                            row["common_projection_m"][i],
                            target["common_projection"][i],
                            row["certificates"]["common_projection"][i],
                            primary,
                            refined,
                        )
                    )
    for row in g["half_edges"]:
        keys(
            row,
            {
                "region_id",
                "vertex_ids",
                "edge_id",
                "interface_id",
                "interface_kind",
                "normal_xy",
                "neighbor_id",
            },
            "half edge",
        )
        vector2(row["normal_xy"], "half-edge normal")
        edge = edge_actual[row["edge_id"]]
        direction = 1 if row["vertex_ids"] == edge["vertex_ids"] else -1
        same(
            row["normal_xy"],
            [direction * v for v in edge["normal_xy"]],
            "complete half-edge normal bits",
        )
    owners = primary["cell_ids"] + primary["bath_ids"]
    for field, routes, ends in (
        ("membrane_incidence", primary["membranes"], ("cell_id", "bath_id")),
        ("face_incidence", primary["faces"], ("sender", "receiver")),
    ):
        expected = [
            [int(owner == row[ends[1]]) - int(owner == row[ends[0]]) for row in routes]
            for owner in owners
        ]
        same(g[field], expected, "complete typed integer incidence")
        require(
            all(sum(row[i] for row in expected) == 0 for i in range(len(routes))),
            "Exact incidence conservation",
        )
    return dict(
        base=base,
        full_precision_quantities=quantities,
        complete_field_axis_and_certificate_inventories=True,
        exact_constant_affine_and_volume_conservation=True,
        native_equivalence=False,
        physical_model_prepared=False,
    )


def verify(request, candidate, truth):
    try:
        keys(
            candidate,
            {
                "request_identity",
                "partition_request",
                "partition_binding",
                "construction",
                "owner_maps",
                "conservation",
                "provenance",
                "identity",
            },
            "complete constructor candidate",
        )
        same(candidate["request_identity"], request["identity"], "constructor request identity")
        raw = truth["partition_input"]
        expected_request = dict(
            declaration_json=json.dumps(
                raw, sort_keys=True, separators=(",", ":"), allow_nan=False
            ),
            identity=polygon._hash(
                dict(
                    kind="cells.finite_ecm_polygon_request@1",
                    law="cells_finite_ecm_conforming_polygon_partition@1",
                    declaration=raw,
                )
            ),
        )
        same(candidate["partition_request"], expected_request, "complete finite-ECM request")
        binding = candidate["partition_binding"]
        keys(binding, {"geometry_json", "identity"}, "finite-ECM binding")
        g = json_record(binding["geometry_json"], 16 * 2**20)
        same(binding["identity"], polygon._hash(g), "complete finite-ECM geometry seal")
        same(g["request_identity"], expected_request["identity"], "finite request binding")
        checked = compare_geometry(raw, g, truth["primary"], truth["refined"])
        for field in ("construction", "owner_maps", "conservation", "provenance"):
            same(candidate[field], truth[field], "complete independent " + field)
        same(
            candidate["identity"],
            digest(
                [LAW]
                + [
                    candidate[key]
                    for key in (
                        "request_identity",
                        "partition_request",
                        "partition_binding",
                        "construction",
                        "owner_maps",
                        "conservation",
                        "provenance",
                    )
                ]
            ),
            "complete candidate seal",
        )
        return dict(
            passed=True,
            geometry=checked,
            complete_constructor_and_geometry_arrays=True,
            physical_model_prepared=False,
            production_functions_called=False,
        )
    except Exception as error:
        return dict(
            passed=False,
            type=type(error).__name__,
            reason=str(error),
            traceback=traceback.format_exc(),
        )


def evaluate(payload):
    partial = dict(stage="input")
    try:
        keys(
            payload,
            {"request", "candidate"} | ({"controls"} if "controls" in payload else set()),
            "reference input",
        )
        controls = payload.get("controls", [])
        require(type(controls) is list and len(controls) <= 64, "Bounded explicit control panel")
        require(
            all(
                type(row) is dict
                and set(row) == {"name", "candidate"}
                and type(row["name"]) is str
                and bool(row["name"])
                for row in controls
            ),
            "Complete named controls",
        )
        require(len({row["name"] for row in controls}) == len(controls), "Distinct control IDs")
        truth = derive(payload["request"], partial)
        baseline = verify(payload["request"], payload["candidate"], truth)
        if not baseline["passed"]:
            return dict(
                status="baseline_failed",
                baseline_passed=False,
                candidate_passed=False,
                control_detected=False,
                baseline=baseline,
                controls=[],
                reference=truth,
                raw_partial=partial,
            )
        checked = [
            dict(name=row["name"], verification=verify(payload["request"], row["candidate"], truth))
            for row in controls
        ]
        return dict(
            status="complete",
            baseline_passed=True,
            candidate_passed=True,
            baseline=baseline,
            control_detected=bool(controls)
            and all(not row["verification"]["passed"] for row in checked),
            controls=checked,
            reference=truth,
            raw_partial=partial,
            physical_model_prepared=False,
            native_equivalence=False,
        )
    except Exception as error:
        return dict(
            status="reference_failed",
            baseline_passed=False,
            candidate_passed=False,
            control_detected=False,
            controls=[],
            type=type(error).__name__,
            reason=str(error),
            traceback=traceback.format_exc(),
            raw_partial=partial,
        )


def runtime_inventory(input_path):
    paths = {
        str(Path(sys.executable).resolve()),
        str(Path(__file__).resolve()),
        str(input_path.resolve()),
    }
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name and Path(name).is_file():
            paths.add(str(Path(name).resolve()))
    missing = []
    for line in Path("/proc/self/maps").read_text().splitlines():
        pieces = line.split(maxsplit=5)
        if len(pieces) == 6 and pieces[5].startswith("/"):
            path = Path(pieces[5])
            if path.is_file():
                paths.add(str(path.resolve()))
            else:
                missing.append(str(path))
    require(len(paths) <= 20000, "Bounded runtime file inventory")
    files, errors = {}, {}
    for path in sorted(paths):
        try:
            files[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError as error:
            errors[path] = str(error)
    return dict(
        pid=os.getpid(),
        parent_pid=os.getppid(),
        source=str(Path(__file__).resolve()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_sha256=hashlib.sha256(input_path.read_bytes()).hexdigest(),
        executable=sys.executable,
        python=sys.version,
        affinity=sorted(os.sched_getaffinity(0)),
        files=files,
        file_errors=errors,
        mapped_file_errors=missing,
        production_and_scientific_imports_denied=True,
        production_or_scientific_modules_loaded=sorted(
            n for n in sys.modules if n.split(".")[0] in DENIED
        ),
        threads={
            name: os.environ.get(name)
            for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = json_record(args.input.read_text(), 64 * 2**20)
    report = evaluate(payload)
    try:
        origin = runtime_inventory(args.input)
        report["runtime_origin"] = origin
        if (
            origin["file_errors"]
            or origin["mapped_file_errors"]
            or origin["production_or_scientific_modules_loaded"]
        ):
            report["runtime_capture_failed"] = True
    except Exception as error:
        report["runtime_capture_failed"] = True
        report["runtime_capture_failure"] = dict(
            type=type(error).__name__, reason=str(error), traceback=traceback.format_exc()
        )
    with args.output.open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not (
        report["baseline_passed"]
        and not report.get("runtime_capture_failed", False)
        and (report["control_detected"] if payload.get("controls") else report["candidate_passed"])
    ):
        raise SystemExit(2 if report["status"] == "baseline_failed" else 1)


if __name__ == "__main__":
    main()
