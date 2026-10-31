"""Held fixed-polygon removal cases; existing qualified coordinate recipes."""

from validation.geometry import conservative_polygon_geometry_fixtures as parent

POSITIVE_CASES = (
    "triangle-contact",
    "grid-corner",
    "merged-cell",
    "disconnected-island",
    "two-bath-exposed",
    "all-cells",
    "empty-selection",
    "merged-all-cells",
)


def case(name):
    recipe, selected = {
        "triangle-contact": ("two-triangles", ["cell1"]),
        "grid-corner": ("quad-grid", ["physical-s-1-1"]),
        "merged-cell": ("quad-grid-merged", ["left"]),
        "disconnected-island": ("disconnected-cells", ["cell0"]),
        "two-bath-exposed": ("two-baths", ["cell0"]),
        "all-cells": ("two-triangles", ["cell0", "cell1"]),
        "empty-selection": ("two-triangles", []),
        "merged-all-cells": ("concave-merged", ["concave"]),
    }[name]
    return parent.fixture(recipe), selected


def removal(before, selected, *, bath_override=None):
    """Choose faces by explicit opposite-cell ownership, not array lengths."""
    chosen = set(selected)
    membranes = {r["id"]: r for r in before["membranes"]}
    rows = []
    for face in before["contacts"]:
        if sum(c in chosen for c in (face["sender"], face["receiver"])) != 1:
            continue
        survivor = next(
            membranes[n] for n in face["membrane_ids"] if membranes[n]["cell_id"] not in chosen
        )
        rows.append(
            dict(
                membrane_id=survivor["id"],
                bath_id=(survivor["bath_id"] if bath_override is None else bath_override),
            )
        )
    return dict(removed_cell_ids=list(selected), exposed_baths=rows)
