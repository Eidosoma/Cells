"""Unrun lifecycle cases and explicit manufactured algebra witnesses."""

import numpy as np

from cells.processes import betse_image_mask_prelude as images
from cells.processes import betse_initial_mesh_preparation as initial
from cells.processes import betse_mesh_clip_preparation as clipped
from cells.processes import betse_mesh_lifecycle_preparation as lifecycle
from validation.betse import betse_mesh_clip_preparation_fixtures as previous

CALLER_CASES = (
    "caller-square-core",
    "caller-hex-core",
    "caller-square-zero-steps",
    "caller-hex-zero-steps",
    "caller-square-early",
    "caller-hex-early",
    "caller-square-two-steps",
    "caller-hex-two-steps",
)
OPTION_CASES = (
    "native-square-zero-smoothing",
    "native-hex-zero-smoothing",
    "native-square-positive-smoothing",
    "native-hex-positive-smoothing",
    "native-square-smooth-refine-inner",
    "native-hex-smooth-refine-inner",
    "native-square-smooth-refine-all",
    "native-hex-smooth-refine-all",
)
CASES = (*CALLER_CASES, *OPTION_CASES)
HELPER_CASES = (
    "core-path",
    "core-disconnected",
    "aux-square",
    "smoothing-zero",
    "smoothing-positive",
    "smoothing-singular-constant",
    "refine-zero-steps",
    "refine-converged",
)
RAW_HELPER_CASES = ("smoothing-zero-area", "core-out-of-range-edge")


def declaration(name, directory):
    if name not in CASES:
        raise ValueError("Require a declared lifecycle input case")
    lattice = "hex" if "-hex-" in name else "square"
    base, inputs = previous.case("dense4-" + lattice + "-centroid", directory)
    binding, seeds, prelude = base.upstream
    controls = dict(inputs["controls"])
    if name in CALLER_CASES:
        controls["refine_mesh"] = not name.endswith("-core")
        controls["maximum_voronoi_steps"] = 0 if name.endswith("-zero-steps") else 2
        controls["voronoi_convergence"] = 1e9 if name.endswith("-early") else 1e-30
        prelude = images.prepare(binding, seeds, prelude.image, controls)
        base = initial.from_image_prelude(binding, seeds, prelude)
        options = None
    else:
        radius = base.constructor_kwargs["cell_radius"]
        refine = "smooth-refine-" in name
        options = dict(
            kind=lifecycle.OPTION_KIND,
            classification="manufactured_native_api_options",
            provenance=(
                "Native API option trial. The caller fixes smoothing=None and fix_bounds=True."
            ),
            parameters=dict(
                smoothing=0.0 if name.endswith("zero-smoothing") else 0.001 * radius**2,
                refinement=refine,
                max_steps=1,
                convergence=1e-30,
                fix_bounds=not name.endswith("-all"),
            ),
        )
    return base, dict(inputs, controls=controls, lifecycle_case=name, native_option_recipe=options)


def bind(base, initial_state, clip_state, inputs):
    clip_request = clipped.from_initial_mesh(base, initial_state)
    if inputs["native_option_recipe"] is None:
        return lifecycle.from_clipped(clip_request, clip_state)
    return lifecycle.from_native_option_trial(
        clip_request, clip_state, inputs["native_option_recipe"]
    )


def helper(name):
    if name not in (*HELPER_CASES, *RAW_HELPER_CASES):
        raise ValueError("Require declared isolated source algebra inputs")

    def a(value):
        return np.asarray(value, dtype=float)

    if name.startswith("core-"):
        n = 4 if name == "core-disconnected" else 3
        edges = (
            [[0, 1], [2, 3]]
            if n == 4
            else [[0, 3]]
            if name == "core-out-of-range-edge"
            else [[0, 1], [1, 2]]
        )
        return (
            "create_core_operators",
            dict(
                n_tverts=n,
                n_tedges=len(edges),
                tri_edges=np.asarray(edges, dtype=int),
                tri_verts=a([[i, 0] for i in range(n)]),
            ),
            {},
        )
    if name == "aux-square":
        edges = np.asarray([[0, 1], [1, 2], [2, 3], [3, 0]], dtype=int)
        cells = np.empty(1, dtype=object)
        cells[0] = np.asarray([0, 1, 2, 3], dtype=int)
        return (
            "create_aux_operators",
            dict(
                n_tverts=4,
                n_tedges=4,
                n_tcell=1,
                tri_edges=edges,
                tri_cells=cells,
                n_vedges=4,
                n_vverts=4,
                vor_edges=edges.copy(),
                vor_cells=cells.copy(),
                inner_tvert_i=np.asarray([0], dtype=int),
                tri_verts=a([[0, 0], [1, 0], [1, 1], [0, 1]]),
            ),
            {},
        )
    if name.startswith("refine-"):
        return (
            "refine_mesh",
            dict(
                cell_radius=1.0,
                tri_cents=a([[0, 0], [1, 0]]),
                tri_ccents=a([[0, 1], [2, 0]]),
                tri_verts=a([[0, 0], [1, 0], [0, 1]]),
                removed_bad_verts=True,
                mesh_qual=123.0,
            ),
            dict(
                max_steps=0 if name == "refine-zero-steps" else 3, convergence=1e9, fix_bounds=True
            ),
        )
    singular = name == "smoothing-singular-constant"
    n = 2 if singular else 3
    points = [[0, 0], [1, 2]] if singular else [[0, 0], [1, 0], [2, 1]]
    delta = [[-1, 1]] if singular else [[-1, 1, 0], [0, -1, 1]]
    area = [0, 1, 1] if name == "smoothing-zero-area" else [1] * n
    prototype = dict(
        n_tverts=n,
        tri_verts=a(points),
        vor_cents=a(points),
        vor_sa=a(area),
        vor_edge_len=a([1] * len(delta)),
        tri_edge_len=a([1] * len(delta)),
        delta_tri_0=a(delta),
        removed_bad_verts=True,
    )
    step = -0.5 if singular else 0.0 if name == "smoothing-zero" else 0.1
    return "laplacian_smoothing", prototype, dict(stepsize=step)
