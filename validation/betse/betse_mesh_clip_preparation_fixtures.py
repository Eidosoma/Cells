"""Unrun clipping cases; source topology stays an owned, unqualified input."""

import numpy as np

from cells.processes import betse_image_mask_prelude as images
from cells.processes import betse_initial_mesh_preparation as initial
from validation.betse import betse_image_mask_prelude_fixtures as masks
from validation.betse import betse_initial_mesh_preparation_fixtures as upstream

CASES = (
    "dense4-square-centroid",
    "dense4-square-circumcentre",
    "dense4-hex-centroid",
    "dense4-hex-circumcentre",
    "asymmetric4-square-centroid",
    "asymmetric4-square-circumcentre",
    "asymmetric4-hex-centroid",
    "asymmetric4-hex-circumcentre",
    "centre_hole6-square-centroid",
    "centre_hole6-square-circumcentre",
    "centre_hole6-hex-centroid",
    "centre_hole6-hex-circumcentre",
)
HELPER_CASES = (
    "left-inside",
    "left-boundary",
    "line-crossing",
    "convex-polygon",
    "duplicate-cloud",
    "keeper-complement",
    "empty-cloud",
)
RAW_HELPER_CASES = ("parallel-lines", "short-polygon")


def case(name, directory):
    if name not in CASES:
        raise ValueError("Use the declared clipping source panel")
    image, lattice, centre = name.split("-")
    base, inputs = upstream.caller("caller-" + lattice + "-disordered", directory)
    binding, seeds, _ = base.upstream
    controls = dict(inputs["controls"], use_centroids=centre == "centroid")
    recipe = masks.write_image(directory, image)
    image_source = images.capture_image(recipe)
    prelude = images.prepare(binding, seeds, image_source, controls)
    request = initial.from_image_prelude(binding, seeds, prelude)
    return request, dict(
        inputs,
        controls=controls,
        image_recipe=recipe,
        classification="native_lattice_and_owned_image_source_inputs",
        upstream_accuracy_qualification="open",
        image_bytes_hex=image_source.file_bytes.hex(),
    )


def helper(name):
    if name not in (*HELPER_CASES, *RAW_HELPER_CASES):
        raise ValueError("Use declared manufactured isolated-helper witnesses")

    def a(value):
        return np.asarray(value, dtype=float)

    if name.startswith("left-"):
        return "is_left_of_vector", dict(
            subject_point=a([0.5e-6, 1e-6 if name == "left-inside" else 0]),
            vector_head_point=a([1e-6, 0]),
            vector_tail_point=a([0, 0]),
        )
    if name in ("line-crossing", "parallel-lines"):
        return "intersect_lines", dict(
            line1_point1=a([0, 0]),
            line1_point2=a([2e-6, 0]),
            line2_point1=a([1e-6, -1e-6] if name == "line-crossing" else [0, 1e-6]),
            line2_point2=a([1e-6, 1e-6] if name == "line-crossing" else [2e-6, 1e-6]),
        )
    if name in ("convex-polygon", "short-polygon"):
        return "clip_counterclockwise", dict(
            subject_polygon=a(
                [[0, 0], [2e-6, 0]]
                if name == "short-polygon"
                else [[0, 0], [2e-6, 0], [2e-6, 2e-6], [0, 2e-6]]
            ),
            clip_polygon=a([[0, 0], [3e-6, 0], [0, 3e-6]]),
        )
    if name == "keeper-complement":
        return "search_point_cloud", dict(
            pts=a([[0, 0], [0.5e-6, 0.5e-6], [1e-6, 1e-6]]),
            pt_cloud=a([[0, 0], [1e-6, 1e-6], [2e-6, 0]]),
        )
    return "search_point_cloud", dict(
        pts=a([[0, 0], [1e-6, 0]]),
        pt_cloud=a([[0, 0], [0, 0]]) if name == "duplicate-cloud" else np.empty((0, 2)),
    )
