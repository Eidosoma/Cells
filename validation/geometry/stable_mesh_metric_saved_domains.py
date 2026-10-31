"""Exact owner-containment diagnostics on saved coordinates, without rebuilding.

The even/odd horizontal-ray test is independent of the production winding test.
Simple rings and their topology are prerequisites, not qualified by this tool.
No metric constructor, reference solver, tolerance or coordinate is changed.
"""

import argparse
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Require a two-coordinate point")
    if any(
        type(v) not in (float, int) or (type(v) is float and not math.isfinite(v)) for v in value
    ):
        raise ValueError("Require finite coordinates; booleans are not coordinates")
    return tuple(Fraction(v) for v in value)


def _ratio(value):
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


def classify_point(point, polygon):
    """Return an exact relation and every ray/edge witness for a simple ring."""
    p = _point(point)
    vertices = [_point(v) for v in polygon]
    if len(vertices) < 3 or len(set(vertices)) != len(vertices):
        raise ValueError("Require at least three distinct vertices in an open ring")
    crossings, boundary_edges, witnesses = [], [], []
    for edge, a in enumerate(vertices):
        b = vertices[(edge + 1) % len(vertices)]
        cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        on_segment = cross == 0 and all(min(a[k], b[k]) <= p[k] <= max(a[k], b[k]) for k in (0, 1))
        if on_segment:
            boundary_edges.append(edge)
        # A half-open vertical interval counts a ray through a vertex once.
        straddles = (a[1] > p[1]) != (b[1] > p[1])
        x_intersection = None
        crosses = False
        if straddles:
            x_intersection = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            crosses = x_intersection > p[0]
            if crosses:
                crossings.append(edge)
        witnesses.append(
            dict(
                edge=edge,
                cross_exact=_ratio(cross),
                on_segment=on_segment,
                straddles=straddles,
                ray_crossing=crosses,
                intersection_x_exact=None if x_intersection is None else _ratio(x_intersection),
            )
        )
    relation = "boundary" if boundary_edges else "inside" if len(crossings) % 2 else "outside"
    return dict(
        relation=relation,
        boundary_edges=boundary_edges,
        crossing_edges=crossings,
        edge_witnesses=witnesses,
    )


def audit_geometry(geometry):
    """Check only the original seed-to-dual-ring pairing, preserving its axis."""
    if set(geometry) != {"tri_verts", "tri_cells", "vor_verts", "vor_cells"}:
        raise ValueError("Require the complete saved topology geometry schema")
    points, vertices, rings = (geometry[key] for key in ("tri_verts", "vor_verts", "vor_cells"))
    if not points or len(points) != len(rings):
        raise ValueError("Require a nonempty exact seed/ring owner axis")
    for p in [*points, *vertices]:
        _point(p)
    rows = []
    for owner, ring in enumerate(rings):
        if (
            not isinstance(ring, (list, tuple))
            or len(ring) < 3
            or any(type(i) is not int or not 0 <= i < len(vertices) for i in ring)
            or len(ring) != len(set(ring))
        ):
            raise ValueError("Require distinct valid vertex IDs for each owned ring")
        rows.append(
            dict(
                owner=owner,
                point=points[owner],
                polygon_vertex_ids=list(ring),
                **classify_point(points[owner], [vertices[i] for i in ring]),
            )
        )
    noninterior = [row["owner"] for row in rows if row["relation"] != "inside"]
    return dict(
        owners=rows,
        owner_count=len(rows),
        noninterior_owners=noninterior,
        all_seeds_strictly_inside=not noninterior,
        simple_rings_and_topology_assumed=True,
        topology_revalidated=False,
        metrics_qualified=False,
        physical_geometry_admitted=False,
    )


def _sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_candidate(path):
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError("Use the original artifact, not a filesystem alias")
    if not path.is_file() or path.stat().st_size > 16 * 2**20:
        raise ValueError("Require a bounded saved candidate file")

    def pairs(items):
        value = {}
        for key, child in items:
            if key in value:
                raise ValueError("Duplicate JSON key: " + key)
            value[key] = child
        return value

    def nonfinite(value):
        raise ValueError("Nonstandard JSON constant: " + value)

    return json.loads(path.read_text(), object_pairs_hook=pairs, parse_constant=nonfinite)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", nargs=2, action="append", metavar=("NAME", "CANDIDATE"), required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError("Preserve the existing diagnostic result")
    names = [name for name, _ in args.case]
    paths = [Path(name).absolute() for _, name in args.case]
    if len(names) != len(set(names)) or len(paths) != len(set(paths)):
        raise ValueError("Do not count a saved case or artifact twice")
    results = []
    for (name, _), path in zip(args.case, paths, strict=True):
        before = _sha(path)
        candidate = read_candidate(path)
        report = audit_geometry(candidate["geometry"])
        if _sha(path) != before:
            raise ValueError("Saved input changed during diagnosis")
        results.append(
            dict(
                case=name,
                input_path=str(path),
                input_sha256=before,
                candidate_identity=candidate["identity"],
                **report,
            )
        )
    result = dict(
        kind="cells.saved_seed_owner_domain_diagnostic@1",
        status="diagnostic_completed",
        source_sha256=_sha(Path(__file__)),
        cases=results,
        cases_checked=len(results),
        cases_with_noninterior_seeds=sum(not r["all_seeds_strictly_inside"] for r in results),
        geometry_reconstruction_runs=0,
        metric_constructor_runs=0,
        metric_qualification_credit=0,
        biological_case_credit=0,
        original_coordinates_unchanged=True,
        tolerance_used=None,
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps({key: value for key, value in result.items() if key != "cases"}, sort_keys=True)
    )


if __name__ == "__main__":
    main()
