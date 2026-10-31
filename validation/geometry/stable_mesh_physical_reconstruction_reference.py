"""Prospective independent geometry checks; never evaluated in preparation.

Uses the established exact integer polygon checks on the supplied coordinates,
and exhaustive edge scans rather than the candidate's lookup construction.
No native/production/scientific package is imported. No metric or inverse is
invented, and a passing topology report would not admit physical geometry.
"""

import argparse
import importlib.abc
import json
import sys
from fractions import Fraction
from pathlib import Path

from validation.geometry import stable_initial_mesh_preparation_reference as geometry


def pairs(ring):
    return list(zip(ring, ring[1:] + ring[:1], strict=True))


def _det(a, b):
    return a[0] * b[1] - a[1] * b[0]


def evaluate(original, candidate):
    """Check a supplied candidate in a later authorized isolated worker."""
    vertices, faces, edges = (original[k] for k in ("tri_verts", "tri_cells", "tri_edges"))
    vvertices, vcells = original["vor_verts"], original["vor_cells"]
    p, d = candidate["primal"], candidate["dual"]
    rows = []

    def check(name, actual, expected):
        rows.append(dict(check=name, passed=actual == expected, actual=actual, expected=expected))

    check(
        "coordinates_and_original_owner_order",
        candidate["geometry"],
        {k: original[k] for k in ("tri_verts", "tri_cells", "vor_verts", "vor_cells")},
    )
    expected_faces, expected_signs = [], []
    for face in faces:
        face_edges, face_signs = [], []
        for a, b in pairs(face):
            hits = [
                (i, 1 if edge == [a, b] else -1)
                for i, edge in enumerate(edges)
                if edge == [a, b] or edge == [b, a]
            ]
            if len(hits) != 1:
                raise ValueError("Independent scan finds incomplete/nonunique original edge")
            face_edges.append(hits[0][0])
            face_signs.append(hits[0][1])
        expected_faces.append(face_edges)
        expected_signs.append(face_signs)
    inverse = [
        [fi for fi, row in enumerate(expected_faces) if ei in row] for ei in range(len(edges))
    ]
    endpoints = [[ei for ei, edge in enumerate(edges) if vi in edge] for vi in range(len(vertices))]
    check("face_edge_incidence", p["face_to_edges"], expected_faces)
    check("face_edge_orientation", p["face_edge_signs"], expected_signs)
    primal_d1 = [
        [
            next((sign for ei, sign in zip(ids, signs, strict=True) if ei == edge), 0)
            for edge in range(len(edges))
        ]
        for ids, signs in zip(expected_faces, expected_signs, strict=True)
    ]
    check("primal_signed_face_operator", p["delta_1"], primal_d1)
    check("inverse_face_incidence", p["edge_to_faces"], inverse)
    check("unique_vertex_edge_incidence", p["vertex_to_edges"], endpoints)
    check("original_primal_edge_axis", p["edges"], edges)
    boundary = [i for i, row in enumerate(inverse) if len(row) == 1]
    check("primal_boundary_axis", p["boundary_edges"], boundary)
    check(
        "primal_boundary_vertices",
        p["boundary_vertices"],
        sorted({v for i in boundary for v in edges[i]}),
    )
    check(
        "primal_boundary_face_owners",
        p["boundary_faces_per_boundary_edge"],
        [inverse[i][0] for i in boundary],
    )
    # Establish the complete directed axis from original rings before reading
    # any candidate incidence. Exhaustive scans preserve first occurrence
    # order independently of the production undirected-key lookup.
    full_edges = []
    for ring in vcells:
        for a, b in pairs(ring):
            if not any(edge == [a, b] or edge == [b, a] for edge in full_edges):
                full_edges.append([a, b])
    check("full_dual_edge_inventory", d["full_edges"], full_edges)
    occurrences = []
    for edge in full_edges:
        occurrences.append(
            [
                (owner, local, 1 if (a, b) == tuple(edge) else -1)
                for owner, ring in enumerate(vcells)
                for local, (a, b) in enumerate(pairs(ring))
                if set((a, b)) == set(edge)
            ]
        )
    check(
        "full_dual_incidence",
        d["full_edge_owner_occurrences"],
        [[list(v) for v in row] for row in occurrences],
    )
    expected_boundary = [i for i, row in enumerate(occurrences) if len(row) == 1]
    check("full_dual_boundary_axis", d["full_boundary_edges"], expected_boundary)
    check(
        "full_dual_boundary_vertices",
        d["full_boundary_vertices"],
        sorted({v for i in expected_boundary for v in full_edges[i]}),
    )
    full_d1 = [
        [next((sign for own, _, sign in row if own == owner), 0) for row in occurrences]
        for owner in range(len(vcells))
    ]
    check("full_dual_signed_polygon_operator", d["full_polygon_delta_1"], full_d1)
    check(
        "selected_dual_endpoint_operator",
        d["selected_delta_0"],
        [
            [int(v == b) - int(v == a) for v in range(len(vvertices))]
            for a, b in d["selected_edges"]
        ],
    )
    check(
        "selected_dual_reverse_boundary",
        d["selected_reverse_polygon_delta_1"],
        [[int(owner == a) - int(owner == b) for a, b in edges] for owner in range(len(vcells))],
    )
    for pi, (a, b) in enumerate(edges):
        hits = [
            i
            for i, row in enumerate(occurrences)
            if sorted(owner for owner, _, _ in row) == sorted((a, b))
        ]
        check("dual_owner_pair_" + str(pi), len(hits), 1)
        if len(hits) == 1:
            check("selected_to_full_" + str(pi), d["selected_to_full"][pi], hits[0])
            check(
                "selected_endpoints_" + str(pi),
                sorted(d["selected_edges"][pi]),
                sorted(full_edges[hits[0]]),
            )
        delta_t = [
            Fraction.from_float(vertices[b][i]) - Fraction.from_float(vertices[a][i])
            for i in (0, 1)
        ]
        x, y = d["selected_edges"][pi]
        delta_v = [
            Fraction.from_float(vvertices[y][i]) - Fraction.from_float(vvertices[x][i])
            for i in (0, 1)
        ]
        determinant = _det(delta_t, delta_v)
        rows.append(
            dict(
                check="selected_clockwise_" + str(pi),
                passed=determinant <= 0,
                determinant_exact=dict(
                    numerator=str(determinant.numerator), denominator=str(determinant.denominator)
                ),
            )
        )
    check(
        "selected_interfaces_unique",
        len(set(map(tuple, map(sorted, d["selected_edges"])))),
        len(edges),
    )
    check(
        "inverse_selected_axis_map",
        d["full_to_selected"],
        [
            [j for j, i in enumerate(d["selected_to_full"]) if i == full]
            for full in range(len(full_edges))
        ],
    )
    owner_plan = candidate["physical_owner_plan"]
    expected_occurrences = [
        dict(cell=owner, local_edge=local, dual_endpoints=[ring[local - 1], b])
        for owner, ring in enumerate(vcells)
        for local, b in enumerate(ring)
    ]
    check("physical_occurrence_plan", owner_plan["membrane_occurrences"], expected_occurrences)
    expected_owners = [row["cell"] for row in expected_occurrences]
    check("physical_membrane_owner_axis", owner_plan["membrane_to_cells"], expected_owners)
    check(
        "physical_inverse_owner_map",
        owner_plan["cell_to_membranes"],
        [
            [i for i, owner in enumerate(expected_owners) if owner == cell]
            for cell in range(len(vcells))
        ],
    )
    expected_partners, boundary_occurrences = [], []
    for i, row in enumerate(expected_occurrences):
        others = [
            j
            for j, other in enumerate(expected_occurrences)
            if j != i and sorted(row["dual_endpoints"]) == sorted(other["dual_endpoints"])
        ]
        if len(others) > 1:
            raise ValueError("Independent scan finds ambiguous membrane owners")
        expected_partners.append(others[0] if others else None)
        if not others:
            boundary_occurrences.append(i)
    check(
        "physical_interior_partner_occurrences",
        owner_plan["interior_partner_occurrences"],
        expected_partners,
    )
    check(
        "physical_boundary_occurrences",
        owner_plan["boundary_membrane_occurrences"],
        boundary_occurrences,
    )
    check("boundary_partner_policy_remains_unresolved", owner_plan["boundary_partner_policy"], None)
    for label, d0, d1 in (
        ("primal", p["delta_0"], p["delta_1"]),
        ("dual_full", d["full_delta_0"], d["full_polygon_delta_1"]),
    ):
        if not d0 or not d1:
            raise ValueError("Missing explicitly declared integer operators")
        expected_d0_edges = edges if label == "primal" else full_edges
        expected_width = len(vertices) if label == "primal" else len(vvertices)
        expected_d0 = [
            [int(v == b) - int(v == a) for v in range(expected_width)] for a, b in expected_d0_edges
        ]
        check(label + "_signed_endpoint_operator", d0, expected_d0)
        chain = [
            [sum(row[e] * d0[e][v] for e in range(len(d0))) for v in range(len(d0[0]))]
            for row in d1
        ]
        check(label + "_boundary_of_boundary", chain, [[0] * len(d0[0]) for _ in d1])
    source_polygons = [[vertices[i] for i in row] for row in faces]
    dual_polygons = [[vvertices[i] for i in row] for row in vcells]
    primal_geometry = geometry.complex_geometry(source_polygons, label="retained_primal")
    dual_geometry = geometry.complex_geometry(dual_polygons, label="retained_dual")
    return dict(
        kind="cells.stable_mesh_physical_reconstruction_independent_check@1",
        exact_topology_checks=rows,
        primal_geometry=primal_geometry,
        dual_geometry=dual_geometry,
        candidate_topology_and_complex_geometry_passed=all(row["passed"] for row in rows)
        and primal_geometry["passed"]
        and dual_geometry["passed"],
        actual_coordinates_retriangulated=False,
        original_geometry_tolerances_changed=False,
        native_equivalence=False,
        physical_geometry_admitted=False,
        inverse_operators_checked=False,
        ordinary_ECM_loop_ready=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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
                raise ImportError(
                    "Independent geometry worker denies production/science: " + fullname
                )

    sys.meta_path.insert(0, DenyScience())
    payload = json.loads(args.input.read_text())
    report = evaluate(payload["original"], payload["candidate"])
    if any(
        n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "PIL"}
        for n in sys.modules
    ):
        raise RuntimeError("Independent geometry worker imported production/science")
    # Save full checks before the caller decides whether they pass.
    with args.output.open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
