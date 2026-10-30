"""Prepared byte-owned PGM fixtures; writing occurs only in an explicit panel."""

import hashlib

CASES = ("asymmetric4", "near_white5", "centre_hole6", "dense4")


def raster(case):
    if case == "asymmetric4":
        # Its flipped mask must remain asymmetric to expose transposed queries.
        return [[0, 0, 255, 255], [0, 0, 255, 255], [0, 255, 0, 255], [0, 0, 0, 0]]
    if case == "near_white5":
        return [[254 if (i + 2 * j) % 3 == 0 else 255 for j in range(5)] for i in range(5)]
    if case == "centre_hole6":
        return [[255 if 2 <= i <= 3 and 2 <= j <= 3 else 0 for j in range(6)] for i in range(6)]
    if case == "dense4":
        return [[0] * 4 for _ in range(4)]
    if case == "white4":
        return [[255] * 4 for _ in range(4)]
    if case == "small3":
        return [[0] * 3 for _ in range(3)]
    if case == "collinear4":
        return [[0 if i == 1 else 255 for _ in range(4)] for i in range(4)]
    if case == "nonsquare":
        return [[0] * 5 for _ in range(4)]
    raise ValueError("Require a declared image-prelude fixture")


def write_image(directory, case, *, absolute=False):
    rows = raster(case)
    data = f"P5\n{len(rows[0])} {len(rows)}\n255\n".encode() + bytes(v for row in rows for v in row)
    path = directory / (case + ".pgm")
    path.write_bytes(data)
    return dict(
        kind="cells.betse_image_mask_source@1",
        filename=str(path) if absolute else path.name,
        conf_dirname=str(directory),
        image_sha256=hashlib.sha256(data).hexdigest(),
    )


def controls(*, single_cell=False):
    return dict(
        kind="cells.betse_make_voronoi_controls@1",
        single_cell=single_cell,
        svg_override=False,
        alpha_shape=0.4,
        use_centroids=True,
        refine_mesh=False,
        maximum_voronoi_steps=8,
        voronoi_convergence=7.5,
    )
