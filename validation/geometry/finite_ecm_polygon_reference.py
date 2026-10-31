"""Independent integer-grid/Green geometry, unit and full-node field checks.

No Fraction or production imports. Scientific dependencies are imported only
by the initial-field lane, after its fresh-process guard is installed.
"""

import hashlib
import json
import math
from collections import defaultdict
from decimal import localcontext
from pathlib import Path
from types import SimpleNamespace

from validation.geometry import conservative_polygon_geometry_reference as polygon
from validation.geometry import stable_geometry_primitives_reference as rounding


class ReferenceRejected(ValueError):
    pass


def ratio(value):
    return polygon._ratio(*float(value).as_integer_ratio())


def add(a, b):
    an, ad = polygon._pair(a)
    bn, bd = polygon._pair(b)
    return polygon._ratio(an * bd + bn * ad, ad * bd)


def subtract(a, b):
    an, ad = polygon._pair(a)
    bn, bd = polygon._pair(b)
    return polygon._ratio(an * bd - bn * ad, ad * bd)


def multiply(a, b):
    return polygon._mul(a, b)


def divide(a, b):
    an, ad = polygon._pair(a)
    bn, bd = polygon._pair(b)
    return polygon._ratio(an * bd, ad * bn)


def dot(a, b):
    total = ratio(0)
    for x, y in zip(a, b, strict=True):
        total = add(total, multiply(x, y))
    return total


def number(exact, *, root=False, precision=4096):
    with localcontext() as ctx:
        ctx.prec = precision
        target = polygon._decimal(exact)
        if root:
            value = float(target.sqrt())
            if not math.isfinite(value) or not polygon._sqrt_rounding_cell(value, exact):
                raise ReferenceRejected("unresolved_or_unrepresentable_radical")
        else:
            exact_hex = rounding._rounded_ratio(exact, target)
            if exact_hex is None:
                raise ReferenceRejected("unrepresentable_rational")
            value = float.fromhex(exact_hex)
    return value


def identity(prefix, value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return prefix + hashlib.sha256(encoded).hexdigest()


def evaluate(raw, *, refinement=1):
    if set(raw) != {
        "source",
        "vertices",
        "domain_vertex_ids",
        "regions",
        "boundary",
        "height_m",
        "membrane_thickness_m",
        "membrane_geometry_policy",
        "face_distance_policy",
        "axial_caps",
        "units",
    }:
        raise ReferenceRejected("explicit_input_fields")
    if (
        set(raw["source"]) != {"kind", "generator", "provenance"}
        or any(set(row) != {"id", "xy_m"} for row in raw["vertices"])
        or any(set(row) != {"id", "kind", "vertex_ids"} for row in raw["regions"])
        or any(set(row) != {"region_id", "vertex_ids", "condition"} for row in raw["boundary"])
    ):
        raise ReferenceRejected("explicit_source_region_vertex_boundary_fields")
    if refinement not in (1, 2):
        raise ReferenceRejected("refinement")
    if (
        raw["source"]["kind"] != "explicit_cell_bath_partition@1"
        or not raw["source"]["provenance"]
        or raw["units"]
        != dict(coordinates="m", height="m", membrane_path="m", area="m2", volume="m3")
    ):
        raise ReferenceRejected("explicit_source_units")
    if (
        raw["membrane_geometry_policy"] != "zero_volume_interface_explicit_path@1"
        or raw["face_distance_policy"] != "orthogonal_volume_centroids_shared_face@1"
        or raw["axial_caps"] != "sealed_no_transport@1"
    ):
        raise ReferenceRejected("unsupported_geometry_or_boundary_policy")
    coordinates = [v for row in raw["vertices"] for v in row["xy_m"]]
    for value in coordinates + [raw["height_m"], raw["membrane_thickness_m"]]:
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or (type(value) is int and abs(value) > 2**53)
        ):
            raise ReferenceRejected("binary64_inputs")
    if raw["height_m"] <= 0 or raw["membrane_thickness_m"] <= 0:
        raise ReferenceRejected("positive_height_membrane_path")
    if not 3 <= len(raw["vertices"]) <= 256 or not 2 <= len(raw["regions"]) <= 32:
        raise ReferenceRejected("partition_bounds")
    scale = max(float(v).as_integer_ratio()[1] for v in coordinates)
    vertices = {
        row["id"]: tuple(
            int(float(v).as_integer_ratio()[0]) * (scale // float(v).as_integer_ratio()[1])
            for v in row["xy_m"]
        )
        for row in raw["vertices"]
    }
    if len(vertices) != len(raw["vertices"]) or len(set(vertices.values())) != len(vertices):
        raise ReferenceRejected("distinct_vertices")
    rows = raw["regions"]
    cells = [row["id"] for row in rows if row["kind"] == "cell"]
    baths = [row["id"] for row in rows if row["kind"] == "bath"]
    if (
        not 1 <= len(cells) <= 16
        or not baths
        or len(cells) + len(baths) != len(rows)
        or any(not 3 <= len(row["vertex_ids"]) <= 64 for row in rows)
        or sum(len(row["vertex_ids"]) for row in rows) > 512
    ):
        raise ReferenceRejected("region_roles_or_bounds")
    if {v for row in rows for v in row["vertex_ids"]} != set(vertices):
        raise ReferenceRejected("unused_or_unknown_vertex")
    incidence, measures = polygon._complex(vertices, rows, scale)
    outer = {
        tuple(owners[0][1:]): owners[0][0] for owners in incidence.values() if len(owners) == 1
    }
    if set(outer) != set(polygon._edges(raw["domain_vertex_ids"])):
        raise ReferenceRejected("incomplete_single_outer_domain")
    boundary = {tuple(row["vertex_ids"]): row["region_id"] for row in raw["boundary"]}
    if (
        len(boundary) != len(raw["boundary"])
        or boundary != outer
        or any(row["condition"] != "sealed_no_transport@1" for row in raw["boundary"])
    ):
        raise ReferenceRejected("explicit_sealed_boundary_owners")
    domain = polygon._polygon([vertices[v] for v in raw["domain_vertex_ids"]], scale)
    total = ratio(0)
    for row in rows:
        pts = [vertices[v] for v in row["vertex_ids"]]
        if any(polygon._orient(a, b, p) < 0 for a, b in polygon._edges(pts) for p in pts):
            raise ReferenceRejected("convex_regions_required")
        total = add(total, measures[row["id"]]["area"])
    if not polygon._same_ratio(total, domain["area"]):
        raise ReferenceRejected("domain_area_exhaustion")
    adjacency = defaultdict(set)
    for owners in incidence.values():
        if len(owners) == 2:
            a, b = owners[0][0], owners[1][0]
            adjacency[a].add(b)
            adjacency[b].add(a)
    reached = {rows[0]["id"]}
    queue = list(reached)
    while queue:
        for neighbor in adjacency[queue.pop()] - reached:
            reached.add(neighbor)
            queue.append(neighbor)
    if reached != {row["id"] for row in rows}:
        raise ReferenceRejected("connected_partition")
    height = ratio(raw["height_m"])
    targets = {
        row["id"]: dict(
            kind=row["kind"],
            vertex_ids=row["vertex_ids"],
            area=measures[row["id"]]["area"],
            volume=multiply(measures[row["id"]]["area"], height),
            centroid=measures[row["id"]]["centroid"],
        )
        for row in rows
    }
    roles = {row["id"]: row["kind"] for row in rows}
    edges = []
    membranes = []
    faces = []
    boundary_rows = []
    half = []
    for owners in incidence.values():
        edge = tuple(sorted(owners[0][1:]))
        a, b = edge
        pa, pb = vertices[a], vertices[b]
        dx, dy = pb[0] - pa[0], pb[1] - pa[1]
        length_squared = polygon._ratio(dx * dx + dy * dy, scale * scale)
        area_squared = multiply(length_squared, multiply(height, height))
        edge_id = identity("ecm-edge-", list(edge))
        names = [owner[0] for owner in owners]
        if len(owners) == 1:
            owner, u, v = owners[0]
            if roles[owner] != "bath":
                raise ReferenceRejected("cell_at_outer_boundary")
            kind = "boundary"
            route = dict(
                id=identity("ecm-boundary-", list(edge)),
                edge_id=edge_id,
                region_id=owner,
                vertex_ids=[u, v],
                condition="sealed_no_transport@1",
            )
            boundary_rows.append(route)
        elif roles[names[0]] == roles[names[1]] == "cell":
            raise ReferenceRejected("direct_cell_cell_has_no_cleft")
        elif "cell" in (roles[name] for name in names):
            owner, u, v = next(row for row in owners if roles[row[0]] == "cell")
            bath = next(name for name in names if roles[name] == "bath")
            kind = "membrane"
            route = dict(
                id=identity("ecm-membrane-", list(edge)),
                edge_id=edge_id,
                cell_id=owner,
                bath_id=bath,
                vertex_ids=[u, v],
            )
            membranes.append(route)
        else:
            sender, u, v = owners[0]
            receiver = owners[1][0]
            cs, cr = targets[sender]["centroid"], targets[receiver]["centroid"]
            start = [polygon._ratio(x, scale) for x in vertices[u]]
            tangent = [
                polygon._ratio(y - x, scale) for x, y in zip(vertices[u], vertices[v], strict=True)
            ]
            delta = [subtract(y, x) for x, y in zip(cs, cr, strict=True)]
            if int(dot(delta, tangent)["numerator"]) != 0:
                raise ReferenceRejected("nonorthogonal_centroid_link")
            projection = divide(
                dot([subtract(x, y) for x, y in zip(cs, start, strict=True)], tangent),
                dot(tangent, tangent),
            )
            pn, pd = polygon._pair(projection)
            if not 0 < pn < pd:
                raise ReferenceRejected("projection_not_inside_shared_face")
            foot = [add(x, multiply(projection, t)) for x, t in zip(start, tangent, strict=True)]
            sign = []
            for center in (cs, cr):
                offset = [subtract(x, y) for x, y in zip(center, start, strict=True)]
                signed = subtract(multiply(tangent[0], offset[1]), multiply(tangent[1], offset[0]))
                sign.append(int(signed["numerator"]))
            if sign[0] <= 0 or sign[1] >= 0:
                raise ReferenceRejected("centroid_side_ownership")
            kind = "face"
            side_squared = []
            for center in (cs, cr):
                offset = [subtract(x, y) for x, y in zip(center, foot, strict=True)]
                side_squared.append(dot(offset, offset))
            route = dict(
                id=identity("ecm-face-", list(edge)),
                edge_id=edge_id,
                sender=sender,
                receiver=receiver,
                vertex_ids=[u, v],
                length_squared=dot(delta, delta),
                centroid_to_face_squared=side_squared,
                common_projection=foot,
            )
            faces.append(route)
        edges.append(
            dict(
                id=edge_id,
                vertex_ids=list(edge),
                region_ids=names,
                interface_kind=kind,
                interface_id=route["id"],
                length_squared=length_squared,
                area_squared=area_squared,
                midpoint=[polygon._ratio(x + y, 2 * scale) for x, y in zip(pa, pb, strict=True)],
                tangent_squared=[polygon._ratio(d * d, dx * dx + dy * dy) for d in (dx, dy)],
                tangent_sign=[-1 if d < 0 else 1 for d in (dx, dy)],
            )
        )
        for owner, u, v in owners:
            half.append(
                dict(
                    region_id=owner,
                    vertex_ids=[u, v],
                    edge_id=edge_id,
                    interface_id=route["id"],
                    interface_kind=kind,
                    neighbor_id=next((name for name in names if name != owner), None),
                )
            )
    if not faces or {row["cell_id"] for row in membranes} != set(cells):
        raise ReferenceRejected("owned_membranes_and_ECM_faces_required")
    precision = 4096 + (512 if refinement == 2 else 0)
    # Resolve every required output now, including pL conversions, so extreme
    # underflow/overflow is a refusal rather than an admitted zero volume.
    for row in targets.values():
        for q in [row["area"], row["volume"], *row["centroid"]]:
            number(q, precision=precision)
    for row in edges:
        number(row["area_squared"], root=True, precision=precision)
        number(row["length_squared"], root=True, precision=precision)
    for row in faces:
        number(row["length_squared"], root=True, precision=precision)
    return dict(
        kind="cells.finite_ecm_polygon_independent_geometry@1",
        refinement=refinement,
        precision_digits=precision,
        integer_scale=str(scale),
        regions=targets,
        cell_ids=cells,
        bath_ids=baths,
        edges=edges,
        membranes=membranes,
        faces=faces,
        boundary=boundary_rows,
        half_edges=half,
        domain_area=total,
        domain_volume=multiply(total, height),
        production_functions_called=False,
        native_equivalence=False,
        qualification_inherited=False,
    )


def _metric(actual, exact, certificate, *, root=False, precision=4096):
    target = number(exact, root=root, precision=precision)
    assert float(actual).hex() == target.hex()
    assert certificate["radicand" if root else "exact"] == exact


def compare_geometry(raw, actual, primary=None, refined=None):
    primary = evaluate(raw) if primary is None else primary
    refined = evaluate(raw, refinement=2) if refined is None else refined
    assert {k: v for k, v in primary.items() if k not in ("refinement", "precision_digits")} == {
        k: v for k, v in refined.items() if k not in ("refinement", "precision_digits")
    }
    assert actual["cell_ids"] == primary["cell_ids"] and actual["bath_ids"] == primary["bath_ids"]
    assert (
        actual["domain_area_exact"] == primary["domain_area"]
        and actual["domain_volume_exact"] == primary["domain_volume"]
    )
    assert actual["owner_axis"] == primary["cell_ids"] + primary["bath_ids"]
    regions = {row["id"]: row for row in actual["regions"]}
    assert set(regions) == set(primary["regions"])
    for name, row in regions.items():
        target = primary["regions"][name]
        assert row["kind"] == target["kind"] and row["vertex_ids"] == target["vertex_ids"]
        _metric(row["area_m2"], target["area"], row["certificates"]["area"])
        _metric(row["volume_m3"], target["volume"], row["certificates"]["volume"])
        for value, cert, q in zip(
            row["centroid_m"], row["certificates"]["centroid"], target["centroid"], strict=True
        ):
            _metric(value, q, cert)
    edge_targets = {row["id"]: row for row in primary["edges"]}
    edges = {row["id"]: row for row in actual["edges"]}
    assert set(edges) == set(edge_targets)
    normals = {}
    tangents = {}
    for name, row in edges.items():
        target = edge_targets[name]
        for key in ("vertex_ids", "region_ids", "interface_kind", "interface_id"):
            assert row[key] == target[key]
        _metric(row["area_m2"], target["area_squared"], row["certificates"]["area"], root=True)
        _metric(row["length_m"], target["length_squared"], row["certificates"]["length"], root=True)
        for value, cert, q in zip(
            row["midpoint_m"], row["certificates"]["midpoint"], target["midpoint"], strict=True
        ):
            _metric(value, q, cert)
        tangent = [
            sign * number(q, root=True)
            for q, sign in zip(target["tangent_squared"], target["tangent_sign"], strict=True)
        ]
        normal = [tangent[1], -tangent[0]]
        assert row["tangent_xy"] == tangent and row["normal_xy"] == normal
        normals[name] = normal
        tangents[name] = tangent
    for kind in ("membranes", "faces", "boundary"):
        expected = {row["id"]: row for row in primary[kind]}
        found = {row["id"]: row for row in actual[kind]}
        assert set(found) == set(expected)
        for name, row in found.items():
            target = expected[name]
            for key in ("edge_id", "vertex_ids") + (
                {
                    "membranes": ("cell_id", "bath_id"),
                    "faces": ("sender", "receiver"),
                    "boundary": ("region_id", "condition"),
                }[kind]
            ):
                assert row[key] == target[key]
            edge = edge_targets[row["edge_id"]]
            assert row["area_m2"] == number(edge["area_squared"], root=True)
            direction = 1 if row["vertex_ids"] == edge["vertex_ids"] else -1
            assert row["normal_xy"] == [direction * v for v in normals[row["edge_id"]]]
            assert row["tangent_xy"] == [direction * v for v in tangents[row["edge_id"]]]
            if kind == "membranes":
                assert row["thickness_m"] == raw["membrane_thickness_m"]
            if kind == "faces":
                _metric(
                    row["length_m"],
                    target["length_squared"],
                    row["certificates"]["length"],
                    root=True,
                )
                for value, cert, q in zip(
                    row["centroid_to_face_m"],
                    row["certificates"]["centroid_to_face"],
                    target["centroid_to_face_squared"],
                    strict=True,
                ):
                    _metric(value, q, cert, root=True)
                for value, cert, q in zip(
                    row["common_projection_m"],
                    row["certificates"]["common_projection"],
                    target["common_projection"],
                    strict=True,
                ):
                    _metric(value, q, cert)
    actual_half = []
    for row in actual["half_edges"]:
        projected = {key: value for key, value in row.items() if key != "normal_xy"}
        actual_half.append(projected)
        edge = edge_targets[row["edge_id"]]
        direction = 1 if row["vertex_ids"] == edge["vertex_ids"] else -1
        assert row["normal_xy"] == [direction * v for v in normals[row["edge_id"]]]
    assert actual_half == primary["half_edges"]
    for name, routes, ends in (
        ("membrane_incidence", primary["membranes"], ("cell_id", "bath_id")),
        ("face_incidence", primary["faces"], ("sender", "receiver")),
    ):
        expected = [
            [int(owner == route[ends[1]]) - int(owner == route[ends[0]]) for route in routes]
            for owner in actual["owner_axis"]
        ]
        assert actual[name] == expected
    return dict(
        status="passed",
        regions=len(regions),
        cell_bath_membranes=len(primary["membranes"]),
        bath_bath_faces=len(primary["faces"]),
        sealed_boundary_sides=len(primary["boundary"]),
        exact_partition_volume_and_orthogonal_distance_targets=True,
        production_functions_called=False,
        qualification_inherited=False,
    )


def semantic(value, name=None):
    if isinstance(value, dict):
        return {key: semantic(item, key) for key, item in value.items()}
    if not isinstance(value, list):
        return value
    rows = [semantic(item) for item in value]
    key = {
        "cells": "id",
        "extracellular": "id",
        "membranes": "id",
        "junctions": "id",
        "faces": "id",
        "membrane_controls": "membrane_id",
        "junction_controls": "junction_id",
    }.get(name)
    if key is not None:
        assert len({row[key] for row in rows}) == len(rows)
        return sorted(rows, key=lambda row: row[key])
    return rows


def materialize(raw, g, request, *, refinement=1):
    target = evaluate(raw, refinement=refinement)
    edges = {row["id"]: row for row in target["edges"]}
    membranes = {row["id"]: row for row in target["membranes"]}
    faces = {row["id"]: row for row in target["faces"]}
    conversions = []

    def visit(value, path=()):
        if isinstance(value, dict) and "$geometry" in value:
            quantity = value["$geometry"]
            root = False
            if quantity == "region_volume_pL":
                exact = multiply(target["regions"][value["region_id"]]["volume"], ratio(1e15))
                units = "pL"
            elif quantity in ("membrane_area_m2", "membrane_capacitance_F", "face_area_m2"):
                owner = (
                    faces[value["face_id"]]
                    if quantity == "face_area_m2"
                    else membranes[value["membrane_id"]]
                )
                exact = edges[owner["edge_id"]]["area_squared"]
                root = True
                units = "m2"
                if quantity == "membrane_capacitance_F":
                    c = ratio(value["specific_capacitance_F_per_m2"])
                    exact = multiply(exact, multiply(c, c))
                    units = "F"
            elif quantity == "face_length_m":
                exact = faces[value["face_id"]]["length_squared"]
                root = True
                units = "m"
            elif quantity == "membrane_permeability_m_per_s":
                exact = divide(
                    ratio(value["diffusivity_m2_per_s"]), ratio(raw["membrane_thickness_m"])
                )
                units = "m/s"
            else:
                raise ReferenceRejected("unknown_quantity_reference")
            result = number(exact, root=root, precision=target["precision_digits"])
            conversions.append(
                dict(
                    path=list(path),
                    reference=value,
                    exact_target=exact,
                    root=root,
                    units=units,
                    value_binary64_hex=result.hex(),
                )
            )
            return result
        if isinstance(value, dict):
            return {key: visit(item, (*path, key)) for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item, (*path, index)) for index, item in enumerate(value)]
        return value

    return dict(
        definition=visit(request["definition_template"]),
        conversions=conversions,
        geometry_targets=target,
    )


def compare_conversion(packet, primary, refined):
    geometry_checks = compare_geometry(
        packet["geometry_declaration"],
        packet["geometry"],
        primary["geometry_targets"],
        refined["geometry_targets"],
    )
    assert primary["definition"] == refined["definition"]
    assert semantic(primary["definition"]) == semantic(packet["definition"])
    actual = {tuple(row["path"]): row for row in packet["provenance"]["conversions"]}
    expected = {tuple(row["path"]): row for row in primary["conversions"]}
    assert set(actual) == set(expected)
    for path, row in expected.items():
        found = actual[path]
        assert (
            found["reference"] == row["reference"]
            and found["units"] == row["units"]
            and found["value_binary64_hex"] == row["value_binary64_hex"]
        )
        assert found["certificate"]["radicand" if row["root"] else "exact"] == row["exact_target"]
    return dict(
        status="passed",
        geometry=geometry_checks,
        conversions=len(expected),
        complete_nongeometric_physics_inventory_controls_preserved=True,
        production_functions_called=False,
        trajectory_executed=False,
    )


def compare_initial_field(packet, *, retain):
    import numpy as np

    from validation.tissue import surface_dynamics_reference as dynamics
    from validation.tissue import surface_field_reference as electrical
    from validation.tissue import surface_reference as transport

    raw = packet["definition"]
    context = dynamics.bind(raw)
    initial = dynamics.initial(context)
    tol = json.loads(
        (Path(__file__).resolve().parents[1] / "tissue/surface_field_protocol.json").read_text()
    )["tolerances"]
    n, o = len(context["vi"]), len(context["vo"])
    nm, nf = len(raw["model"]["membranes"]), len(raw["model"]["faces"])
    node_indices = list(range(n)) + list(
        range(raw["execution"]["capacity"], raw["execution"]["capacity"] + o)
    )

    def physical_field(record):
        values = {key: np.asarray(value) for key, value in record.items() if key != "rates"}
        for key in ("potential_V", "capacitor_node_charge_C", "charge_residual_C"):
            values[key] = values[key][node_indices]
        for key in ("membrane_charge_C", "membrane_voltage_rate_V_s"):
            values[key] = values[key][:nm]
        for key in ("electrode_charge_C", "electrode_current_A", "reservoir_supply_charge_A"):
            values[key] = values[key][:o]
        rates = {}
        for key, value in record["rates"].items():
            value = np.asarray(value)
            if key == "cell_rate_fmol_s":
                value = value[:, :n]
            elif key in ("outside_rate_fmol_s", "reservoir_supply_fmol_s"):
                value = value[:, :o]
            elif key != "valid":
                count = nm if key.startswith("membrane_") else nf if key.startswith("face_") else 0
                value = value[..., :count]
            rates[key] = value
        return SimpleNamespace(**values, rates=SimpleNamespace(**rates))

    def field_atol(name):
        for suffix, key in (
            ("_V_s", "voltage_rate_atol_V_s"),
            ("_V", "voltage_atol_V"),
            ("_C", "charge_atol_C"),
            ("_J_mol", "chemical_potential_atol_J_mol"),
            ("_A", "current_comparison_atol_A"),
            ("_pJ_s", "power_atol_pJ_s"),
            ("_pJ", "energy_atol_pJ"),
        ):
            if name.endswith(suffix):
                return tol[key]
        return tol["flux_atol_fmol_s"]

    retain(
        "reference-initial",
        dict(
            state=initial.tolist(),
            shapes={key: list(shape) for key, shape in context["shapes"].items()},
        ),
    )

    def compact(values):
        assert set(values) == set(context["shapes"])
        for key, shape in context["shapes"].items():
            array = np.asarray(values[key])
            assert array.ndim == len(shape)
            assert all(a >= b for a, b in zip(array.shape, shape, strict=True))
            mask = np.ones(array.shape, dtype=bool)
            mask[tuple(slice(0, n) for n in shape)] = False
            assert np.isfinite(array).all() and not np.any(array[mask])
        return dynamics.flatten(context, values)

    np.testing.assert_array_equal(compact(packet["state"]), initial)
    for name in ("membrane_cell", "membrane_outside", "face_sender", "face_receiver"):
        count = nm if name.startswith("membrane_") else nf
        np.testing.assert_array_equal(
            np.asarray(packet["layout"][name])[:count], context["layout"][name]
        )
    np.testing.assert_array_equal(
        np.asarray(packet["layout"]["face_factor"])[:, :nf], context["layout"]["face_factor"]
    )
    atol = dynamics.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    )
    reports = []
    for index, trial in enumerate(packet["initial_control_probes"]):
        expected, phi, proof = dynamics.evaluate(context, initial, trial["time_s"])
        actual = compact(trial["derivative"])
        budget = atol + 3e-10 * np.abs(expected)
        phi_actual = np.asarray(trial["potential_V"])
        phi_budget = 3e-13 + 3e-10 * np.abs(phi)
        intended_cell_phi = np.asarray(
            [
                packet["request"]["provenance"]["declared_cell_potential_V"][row["id"]]
                for row in raw["model"]["cells"]
            ]
        )
        fields = dynamics.unpack(context, expected)
        ion = raw["model"]
        chemical = (
            1e-3
            * dynamics.R
            * ion["temperature_K"]
            * np.sum(
                np.log(np.c_[context["ai"] / context["vi"], context["ao"] / context["vo"]])
                * np.c_[fields["amount_increment"], fields["extracellular_amount_increment"]]
            )
        )
        material = np.c_[fields["amount_increment"], fields["extracellular_amount_increment"]]
        charge_rate = (
            dynamics.F * 1e-15 * (np.asarray(context["layout"]["valence"]).T @ material)[0]
        )
        electric = 1e12 * np.dot(phi, charge_rate)
        dissipation = sum(
            np.sum(fields[k + "_dissipated_energy_pJ"]) for k in ("membrane", "junction", "face")
        )
        energy = float(chemical + electric + dissipation)
        stage_raw = dynamics.stage(context, initial, trial["time_s"])
        matrix, active, reservoir, _, floating, _ = electrical.topology(stage_raw)
        pins = ~active | reservoir
        for members in floating:
            pins[members[0]] = True
        free = np.flatnonzero(~pins)
        voltage_rate = np.zeros_like(phi)
        voltage_rate[free] = np.linalg.solve(matrix[np.ix_(free, free)], charge_rate[free])
        p = context["layout"]
        mi, mo = np.asarray(p["membrane_cell"]), np.asarray(p["membrane_outside"])
        vm = phi[mi] - phi[n + mo]
        dvm = voltage_rate[mi] - voltage_rate[n + mo]
        caps = np.asarray(p["membrane_capacitance"])
        cap_power = float(1e12 * np.sum(caps * vm * dvm))
        expected_rates = transport.transport(stage_raw, phi[:n], phi[n:])
        field_target = dict(
            potential_V=phi,
            membrane_charge_C=caps * vm,
            capacitor_node_charge_C=matrix @ phi,
            electrode_charge_C=np.zeros(o),
            electrode_current_A=np.zeros(o),
            reservoir_supply_charge_A=np.zeros(o),
            membrane_voltage_rate_V_s=dvm,
            capacitor_energy_pJ=0.5e12 * np.sum(caps * vm * vm),
            capacitor_energy_rate_pJ_s=cap_power,
            chemical_energy_rate_pJ_s=chemical,
            reservoir_power_pJ_s=0.0,
            electrode_power_pJ_s=0.0,
            dissipation_pJ_s=dissipation,
        )
        observed_field = physical_field(trial["field"])
        field_actual = {key: getattr(observed_field, key) for key in field_target}
        field_target.update({"rates__" + key: value for key, value in expected_rates.items()})
        field_actual.update(
            {"rates__" + key: getattr(observed_field.rates, key) for key in expected_rates}
        )
        physical_fields = []
        for key, target_value in field_target.items():
            target_value = np.asarray(target_value)
            observed = np.asarray(field_actual[key])
            field_bounds = field_atol(key) + tol["physical_rtol"] * np.abs(target_value)
            score = float(np.max(np.abs(observed - target_value) / field_bounds, initial=0))
            physical_fields.append(
                dict(
                    name=key,
                    actual=observed.tolist(),
                    independent=target_value.tolist(),
                    budget=field_bounds.tolist(),
                    error_over_budget=score,
                )
            )
        record = dict(
            time_s=trial["time_s"],
            reference_state=initial.tolist(),
            actual_derivative=actual.tolist(),
            reference_derivative=expected.tolist(),
            derivative_budget=budget.tolist(),
            actual_potential_V=phi_actual.tolist(),
            reference_potential_V=phi.tolist(),
            potential_budget_V=phi_budget.tolist(),
            derivative_error_over_budget=float(
                np.max(np.abs(actual - expected) / budget, initial=0)
            ),
            potential_error_over_budget=float(
                np.max(np.abs(phi_actual - phi) / phi_budget, initial=0)
            ),
            intended_cell_potential_V=intended_cell_phi.tolist(),
            intended_cell_potential_error_over_budget=float(
                np.max(np.abs(phi[:n] - intended_cell_phi) / phi_budget[:n], initial=0)
            ),
            reference_energy_balance_pJ_s=energy,
            actual_energy_balance_pJ_s=trial["energy_balance_pJ_s"],
            reference_full_node_root=proof,
            capacitive_components=len(floating),
            reference_face_flux_fmol_s=fields["face_transferred"].tolist(),
            production_stage_valid=trial["valid"],
            physical_field_comparisons=physical_fields,
            transport_valid=bool(observed_field.rates.valid),
        )
        retain("reference-stage-" + str(index) + "-pre-accounting", record)
        try:
            _, accounting = electrical.check(stage_raw, observed_field)
        except AssertionError as error:
            record.update(complete_field_accounting_passed=False, accounting_failure=str(error))
        else:
            record.update(
                complete_field_accounting_passed=True, complete_field_accounting=accounting
            )
        retain("reference-stage-" + str(index), record)
        reports.append(record)
    return dict(
        status="compared",
        stages=reports,
        complete_state_field_count=len(context["shapes"]),
        time_advanced=False,
        trajectory_executed=False,
        native_equivalence=False,
        production_functions_called=False,
    )


def assert_initial_field(report):
    for trial in report["stages"]:
        assert (
            trial["derivative_error_over_budget"] <= 1 and trial["potential_error_over_budget"] <= 1
        )
        assert trial["production_stage_valid"]
        assert trial["transport_valid"] and trial["complete_field_accounting_passed"]
        assert trial["intended_cell_potential_error_over_budget"] <= 1
        assert all(row["error_over_budget"] <= 1 for row in trial["physical_field_comparisons"])
        assert max(abs(v) for v in trial["reference_potential_V"]) > 1e-3
        assert any(value != 0 for row in trial["reference_face_flux_fmol_s"] for value in row)
        assert abs(trial["reference_energy_balance_pJ_s"]) <= 1e-10
        assert abs(trial["actual_energy_balance_pJ_s"]) <= 1e-10
