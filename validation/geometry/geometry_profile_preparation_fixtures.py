"""Explicit profile declarations over already-qualified initial geometry artifacts."""

import json
import os
from copy import deepcopy
from pathlib import Path

from validation.geometry.geometry_profile_preparation_reference import derive_geometry

HANDOFF = Path("/mnt/workspaces/Cells/geometry-tissue-preparation-handoff-20261029-01")
CASES = (
    "overlap",
    "overlap-polygon",
    "percent-alias",
    "color",
    "image-centroids",
    "scaled",
    "disabled",
)


def artifact(name="irregular-native-radial"):
    root = (
        Path(os.environ.get("CELLS_GEOMETRY_PROFILE_REFERENCE", str(HANDOFF / "examples"))) / name
    )
    return {
        key: json.loads((root / (key + ".json")).read_text())
        for key in ("definition", "provenance")
    }


def selector(kind, value=None, *, identity=None, permutation=None):
    return dict(
        kind=kind, value=value, expected_layout_identity=identity, permutation_cell_ids=permutation
    )


def profile(name, picker, scale=1.0, insular=False):
    return dict(
        name=name,
        selector=picker,
        diffusivity_m2_s=[scale * (i + 1) * 1e-18 for i in range(6)],
        is_gj_insular=insular,
    )


def request(case="overlap"):
    source = artifact(
        "irregular-polygon"
        if case == "overlap-polygon"
        else "scaled-polygon"
        if case == "scaled"
        else "irregular-native-radial"
    )
    cells = source["provenance"]["request"]["geometry_source"]["mesh"]["cell_ids"]
    raw = dict(
        kind="cells.initial_geometry_profile_request@1",
        geometry_preparation=source,
        seed_fills=None,
        default=profile("Default", selector("ids", [cells[-1]])),
        profiles=[
            profile("Region", selector("ids", [cells[0], cells[1], cells[0]]), 2, True),
            profile("Later", selector("ids", [cells[1], cells[2]]), 3, False),
        ],
        ion_enabled=[True, True, True, False, False, False],
        enabled=case != "disabled",
        is_ecm=False,
    )
    if case == "percent-alias":
        raw["profiles"] = [
            profile("Before", selector("all"), 2),
            profile("Shuffle", selector("percent", 37, permutation=list(reversed(cells))), 4, True),
            profile("After", selector("all"), 3),
        ]
    if case == "color":
        raw["seed_fills"] = {cid: "#AbC" if i % 2 == 0 else "#abc" for i, cid in enumerate(cells)}
        raw["profiles"] = [profile("ExactColor", selector("color", "#AbC"), 5, True)]
    if case == "image-centroids":
        layout = derive_geometry(raw)["layout"]
        seeds = source["provenance"]["request"]["geometry_source"]["mesh"]["primal_points_m"]
        index = max(
            range(len(cells)),
            key=lambda i: sum((layout["cell_centres_m"][i][k] - seeds[i][k]) ** 2 for k in (0, 1)),
        )
        x, y = layout["cell_centres_m"][index]
        xmin, xmax, ymin, ymax = layout["bounds_m"]
        size = 64
        column = round((x - xmin) / (xmax - xmin) * (size - 1))
        row = size - 1 - round((y - ymin) / (ymax - ymin) * (size - 1))
        bitmap = [[255.0] * size for _ in range(size)]
        for y_pixel in range(max(0, min(row, size - 2)), max(0, min(row, size - 2)) + 2):
            for x_pixel in range(max(0, min(column, size - 2)), max(0, min(column, size - 2)) + 2):
                bitmap[y_pixel][x_pixel] = 0.0
        raw["profiles"] = [
            profile("CentroidPixel", selector("image", dict(grayscale_F=bitmap)), 6, True)
        ]
    return deepcopy(raw)
