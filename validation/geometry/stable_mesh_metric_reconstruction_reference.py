"""Prospective production-denied Decimal metric reference on actual snapshots."""

import argparse
import importlib.abc
import json
import math
import os
import sys
import traceback
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

from validation.geometry import stable_geometry_primitives_reference as primitives
from validation.geometry import stable_initial_mesh_preparation_reference as geometry


def pairs(ring):
    return list(zip(ring, ring[1:] + ring[:1], strict=True))


def serial(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: serial(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [serial(child) for child in value]
    return value


def edge_metrics(points, edges, *, partial=None):
    rows, squares = [], []
    if partial is not None:
        partial.update(values=rows, squared_lengths=squares)
    for a, b in edges:
        delta = [points[b][i] - points[a][i] for i in (0, 1)]
        squared = sum((v * v for v in delta), Decimal(0))
        if squared <= 0:
            raise ValueError("Independent zero-length edge")
        length = squared.sqrt()
        tangent = [v / length for v in delta]
        rows.append(
            dict(
                length_m=length,
                midpoint_m=[(p + q) / 2 for p, q in zip(points[a], points[b], strict=True)],
                tangent_xy=tangent,
                normal_xy=[tangent[1], -tangent[0]],
            )
        )
        squares.append(squared)
    return rows, squares


def polygon_metrics(points, rings, refinement, *, partial=None):
    rows, exact = [], []
    if partial is not None:
        partial.update(values=rows, exact_targets=exact)
    for ring in rings:
        result = primitives.evaluate(
            "polygon", [[float(v).hex() for v in points[i]] for i in ring], refinement=refinement
        )
        values = {k: Decimal(v) for k, v in result["values_decimal"].items()}
        rows.append(
            dict(
                area_m2=values["signed_area_m2"],
                centroid_m=[values["centroid_x_m"], values["centroid_y_m"]],
            )
        )
        exact.append(result["exact_rational_targets"])
    return rows, exact


class ReferenceRejected(ValueError):
    def __init__(self, error, partial):
        super().__init__(str(error))
        self.partial = serial(partial)


def evaluate(payload, refinement):
    partial = dict(stage="input", refinement=refinement)
    try:
        return _evaluate(payload, refinement, partial)
    except Exception as error:
        raise ReferenceRejected(error, partial) from error


def _evaluate(payload, refinement, partial):
    cache, corrected = payload["source_cache"], payload["corrected"]
    if cache["use_centroids"] is not True:
        raise ValueError("Independent metric domain requires the declared centroid layout")
    if refinement not in (1, 2):
        raise ValueError("Require one of the two independent precision forms")
    raw_points, raw_vertices = cache["tri_verts"], cache["vor_verts"]
    faces, cells, edges = cache["tri_cells"], cache["vor_cells"], cache["tri_edges"]
    expected_geometry = {
        key: cache[key] for key in ("tri_verts", "tri_cells", "vor_verts", "vor_cells")
    }
    if corrected["geometry"] != expected_geometry or corrected["primal"]["edges"] != edges:
        raise ValueError("Independent original coordinates/axes differ")
    # The complete dual edge universe derives only from original polygon rows.
    # Coherently appended unused edges cannot enter this reference domain.
    full = []
    for ring in cells:
        for a, b in pairs(ring):
            if not any({a, b} == set(edge) for edge in full):
                full.append([a, b])
    if corrected["dual"]["full_edges"] != full:
        raise ValueError("Full dual edge table differs from the exact original ring union")
    selected = []
    for a, b in edges:
        common = [
            (x, y) for x, y in pairs(cells[a]) if any({x, y} == {u, v} for u, v in pairs(cells[b]))
        ]
        if len(common) != 1:
            raise ValueError("Independent selected owner pair is missing/ambiguous")
        x, y = common[0]
        selected.append([y, x])
    if corrected["dual"]["selected_edges"] != selected:
        raise ValueError("Selected edge orientation/owner pairing differs")
    precision = 4096 + (512 if refinement == 2 else 0)
    with localcontext() as context:
        context.prec = precision
        partial["stage"] = "polygon_metrics"
        points = [[Decimal.from_float(v) for v in point] for point in raw_points]
        vertices = [[Decimal.from_float(v) for v in point] for point in raw_vertices]
        partial["primal_polygons"] = {}
        face_metrics, face_exact = polygon_metrics(
            raw_points, faces, refinement, partial=partial["primal_polygons"]
        )
        partial["dual_polygons"] = {}
        cell_metrics, cell_exact = polygon_metrics(
            raw_vertices, cells, refinement, partial=partial["dual_polygons"]
        )
        partial["stage"] = "edge_metrics"
        partial["primal_edges"] = {}
        tri, tq = edge_metrics(points, edges, partial=partial["primal_edges"])
        partial["full_dual_edges"] = {}
        full_metrics, _ = edge_metrics(vertices, full, partial=partial["full_dual_edges"])
        partial["selected_dual_edges"] = {}
        dual, vq = edge_metrics(vertices, selected, partial=partial["selected_dual_edges"])
        partial["stage"] = "anchor_roles"
        roles, centre_indices = [[] for _ in raw_vertices], []
        layout_checks = []
        partial.update(
            anchor_roles=roles, centre_indices=centre_indices, layout_checks=layout_checks
        )
        for face, centre in enumerate(cache["tri_cents"]):
            hits = [i for i, vertex in enumerate(raw_vertices) if vertex == centre]
            if len(hits) != 1:
                raise ValueError("Independent source centre is not uniquely anchored")
            centre_indices.append(hits[0])
            roles[hits[0]].append(dict(kind="source_face_centroid", face=face))
            for axis in (0, 1):
                target = face_metrics[face]["centroid_m"][axis]
                error = abs(Decimal.from_float(centre[axis]) - target)
                budget = Decimal("1e-27") + Decimal("6e-12") * abs(target)
                layout_checks.append(
                    dict(
                        kind="face_centroid",
                        face=face,
                        axis=axis,
                        absolute_error_decimal=error,
                        budget_decimal=budget,
                        passed=error <= budget
                        and error <= 32 * Decimal.from_float(math.ulp(centre[axis])),
                    )
                )
        for edge_index, (a, b) in enumerate(edges):
            owners = [
                fi for fi, face in enumerate(faces) if any({a, b} == {x, y} for x, y in pairs(face))
            ]
            if len(owners) == 1:
                owner = owners[0]
                others = [i for i in selected[edge_index] if i != centre_indices[owner]]
                if len(others) != 1:
                    raise ValueError("Independent reflected endpoint is missing/ambiguous")
                roles[others[0]].append(
                    dict(kind="source_boundary_reflection", face=owner, primal_edge=edge_index)
                )
                for axis in (0, 1):
                    target = (
                        points[a][axis]
                        + points[b][axis]
                        - Decimal.from_float(cache["tri_cents"][owner][axis])
                    )
                    error = abs(vertices[others[0]][axis] - target)
                    budget = Decimal("1e-27") + Decimal("6e-12") * abs(target)
                    layout_checks.append(
                        dict(
                            kind="boundary_reflection",
                            face=owner,
                            axis=axis,
                            absolute_error_decimal=error,
                            budget_decimal=budget,
                            passed=error <= budget,
                        )
                    )
            elif len(owners) == 2:
                endpoints = {centre_indices[face] for face in owners}
                if len(endpoints) != 2 or set(selected[edge_index]) != endpoints:
                    raise ValueError("Independent interior edge lacks its actual face centres")
            else:
                raise ValueError("Independent unsupported primal face ownership")
        reference_areas = []
        partial["dual_vertex_reference_areas"] = reference_areas
        for row in roles:
            targets = {face_metrics[role["face"]]["area_m2"] for role in row}
            if len(targets) != 1:
                raise ValueError(
                    "Independent dual vertex reference area has unequal or missing owners"
                )
            reference_areas.append(next(iter(targets)))
        partial["stage"] = "native_store_coefficients"
        forward, inverse, geometric = [], [], []
        partial["coefficients"] = dict(
            native_forward=forward, native_inverse=inverse, coordinate_geometric=geometric
        )
        for i, (a, b) in enumerate(zip(tri, dual, strict=True)):
            stored_a = Decimal.from_float(float(a["length_m"]))
            stored_b = Decimal.from_float(float(b["length_m"]))
            forward.append(stored_b / stored_a)
            inverse.append(stored_a / stored_b)
            geometric.append((vq[i] / tq[i]).sqrt())
        inverse_area = [1 / Decimal.from_float(float(row["area_m2"])) for row in cell_metrics]
        grid, _ = geometry._grid([raw_points] + [[raw_vertices[i] for i in ring] for ring in cells])
        strict_seed_owners = [
            geometry._inside(grid[0][owner], ring) == 1 for owner, ring in enumerate(grid[1:])
        ]
        primal_convexity = [
            len(face) in (3, 4)
            and all(
                geometry._orient(
                    grid[0][face[i - 1]], grid[0][face[i]], grid[0][face[(i + 1) % len(face)]]
                )
                > 0
                for i in range(len(face))
            )
            for face in faces
        ]
        orientations = []
        for (a, b), (x, y) in zip(edges, selected, strict=True):
            t = [
                Fraction.from_float(raw_points[b][i]) - Fraction.from_float(raw_points[a][i])
                for i in (0, 1)
            ]
            v = [
                Fraction.from_float(raw_vertices[y][i]) - Fraction.from_float(raw_vertices[x][i])
                for i in (0, 1)
            ]
            determinant = t[0] * v[1] - t[1] * v[0]
            orientations.append(
                dict(
                    numerator=str(determinant.numerator),
                    denominator=str(determinant.denominator),
                    passed=determinant < 0,
                )
            )
        native = dict(
            tri_sa=[r["area_m2"] for r in face_metrics],
            tri_cents=[r["centroid_m"] for r in face_metrics],
            vor_sa=[r["area_m2"] for r in cell_metrics],
            vor_cents=[r["centroid_m"] for r in cell_metrics],
            tri_edge_len=[r["length_m"] for r in tri],
            tri_mids=[r["midpoint_m"] for r in tri],
            tri_tang=[r["tangent_xy"] for r in tri],
            vor_edge_len=[r["length_m"] for r in dual],
            vor_mids=[r["midpoint_m"] for r in dual],
            vor_tang=[r["tangent_xy"] for r in dual],
            tri_sa_o=reference_areas,
            inner_vvert_i=centre_indices,
            tri_ccents=None,
            tri_rcircs=None,
        )
        result = dict(
            kind="cells.stable_mesh_metric_independent_reference@1",
            refinement=refinement,
            precision_digits=precision,
            native_roles=native,
            full_dual_metrics=full_metrics,
            coefficients=dict(
                native_stored_dual_over_primal=forward,
                native_stored_primal_over_dual=inverse,
                coordinate_geometric_length_ratio=geometric,
                native_stored_inverse_dual_area=inverse_area,
            ),
            anchor_roles=roles,
            layout_checks=layout_checks,
            strict_seed_owner_checks=strict_seed_owners,
            primal_convexity_checks=primal_convexity,
            orientation_checks=orientations,
            exact_polygon_targets=dict(primal=face_exact, dual=cell_exact),
            primal_complex=geometry.complex_geometry(
                [[raw_points[i] for i in ring] for ring in faces], label="primal"
            ),
            dual_complex=geometry.complex_geometry(
                [[raw_vertices[i] for i in ring] for ring in cells], label="dual"
            ),
            source_axes_checked=True,
            full_edge_union_derived_from_original_rings=True,
            native_equivalence=False,
            physical_geometry_admitted=False,
        )
        # Save full Decimal strings, without projecting a rounded reference tree.
        return serial(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refinement", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()

    class DenyScience(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {
                "cells",
                "betse",
                "numpy",
                "scipy",
                "jax",
                "jaxlib",
                "PIL",
            }:
                raise ImportError("Metric reference denies production/science: " + fullname)

    sys.meta_path.insert(0, DenyScience())
    try:
        result = evaluate(json.loads(args.input.read_text()), args.refinement)
    except Exception as error:
        result = dict(
            status="reference_failed",
            type=type(error).__name__,
            reason=str(error),
            original_input=str(args.input),
            traceback=traceback.format_exc(),
            raw_partial=getattr(error, "partial", None),
        )
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        raise
    if any(
        n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "PIL"}
        for n in sys.modules
    ):
        raise RuntimeError("Production/scientific import reached independent worker")
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


if __name__ == "__main__":
    main()
