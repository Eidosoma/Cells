"""Analytical and representability controls for the saved-owner diagnostic."""

import json
import math

import pytest

from validation.geometry import stable_mesh_metric_saved_domains as diagnostic


@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize(
    "point,relation",
    (
        ((0.5, 0.5), "inside"),
        ((0.0, 0.5), "boundary"),
        ((0.0, 0.0), "boundary"),
        ((2.0, 0.0), "outside"),
        ((-math.ulp(0.0), 0.5), "outside"),
        ((math.ulp(0.0), 0.5), "inside"),
    ),
)
def test_exact_square_with_subnormal_boundary_neighbors(reverse, point, relation):
    ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    if reverse:
        ring.reverse()
    assert diagnostic.classify_point(point, ring)["relation"] == relation


@pytest.mark.parametrize(
    "point,relation",
    (
        ((0.5, 1.5), "inside"),
        ((1.5, 1.5), "outside"),
        ((1.0, 1.5), "boundary"),
    ),
)
def test_concave_notch_and_edge(point, relation):
    ring = [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0), (1.0, 2.0), (0.0, 2.0)]
    assert diagnostic.classify_point(point, ring)["relation"] == relation


def test_triangle_products_below_binary64_range_remain_exact():
    side = 2.0**-1000
    assert side * side == 0.0
    row = diagnostic.classify_point((side / 4, side / 4), [(0.0, 0.0), (side, 0.0), (0.0, side)])
    assert row["relation"] == "inside"
    assert all(w["cross_exact"]["numerator"] != "0" for w in row["edge_witnesses"])


def test_owner_axis_is_not_repaired_or_reordered():
    geometry = dict(
        tri_verts=[[1.5, 0.5], [0.5, 0.5]],
        tri_cells=[],
        vor_verts=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [2.0, 0.0], [2.0, 1.0]],
        vor_cells=[[0, 1, 2, 3], [1, 4, 5, 2]],
    )
    row = diagnostic.audit_geometry(geometry)
    assert row["noninterior_owners"] == [0, 1]
    assert not row["metrics_qualified"] and not row["physical_geometry_admitted"]
    geometry["tri_verts"].reverse()
    assert diagnostic.audit_geometry(geometry)["all_seeds_strictly_inside"]
    geometry["tri_verts"].pop()
    with pytest.raises(ValueError, match="owner axis"):
        diagnostic.audit_geometry(geometry)


@pytest.mark.parametrize("point", ((float("nan"), 0.0), (float("inf"), 0.0), (True, 0.0), (0.0,)))
def test_nonfinite_and_malformed_points_refused(point):
    with pytest.raises(ValueError):
        diagnostic.classify_point(point, [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)])


def test_saved_inputs_refuse_duplicate_keys_and_filesystem_aliases(tmp_path):
    path = tmp_path / "candidate.json"
    path.write_text('{"geometry":{},"geometry":{}}')
    with pytest.raises(ValueError, match="Duplicate"):
        diagnostic.read_candidate(path)
    path.write_text(json.dumps({"geometry": {}}))
    alias = tmp_path / "alias.json"
    alias.symlink_to(path)
    with pytest.raises(ValueError, match="alias"):
        diagnostic.read_candidate(alias)
