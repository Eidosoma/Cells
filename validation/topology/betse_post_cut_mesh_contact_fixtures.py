"""Literal bounded source inputs, constructed only in focused/future CPU checks."""

import numpy as np

CASES = (
    "corner_cut",
    "centre_cut",
    "no_cut",
    "all_cut",
    "ordered_two_cut",
    "uniform_polygon_raw",
    "nonfinite_mesh_raw",
)


def object_rows(rows):
    result = np.empty(len(rows), dtype=object)
    for index, row in enumerate(rows):
        result[index] = np.asarray(row)
    return result


def fixture(case="corner_cut", *, mode="cut_through_contacts"):
    if case not in CASES:
        raise ValueError("Unknown literal post-cut input")
    points = np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.5, 0.5]]) * 1e-6
    faces = np.asarray([[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]], dtype=np.int64)
    edges = np.asarray(
        [[0, 1], [1, 4], [4, 0], [1, 2], [2, 4], [2, 3], [3, 4], [3, 0]], dtype=np.int64
    )
    vfaces = [[] for _ in points]
    vedges = [[] for _ in points]
    for index, row in enumerate(faces):
        for vertex in row:
            vfaces[int(vertex)].append(index)
    for index, row in enumerate(edges):
        for vertex in row:
            vedges[int(vertex)].append(index)
    selected = {
        "corner_cut": [0],
        "centre_cut": [4],
        "no_cut": [],
        "all_cut": [0, 1, 2, 3, 4],
        "ordered_two_cut": [3, 0],
        "uniform_polygon_raw": [0],
        "nonfinite_mesh_raw": [0],
    }[case]
    polygons = []
    for index, centre in enumerate(points):
        count = 4 if case == "uniform_polygon_raw" else [3, 4, 5, 3, 4][index]
        angle = np.arange(count) * 2 * np.pi / count
        polygons.append(centre + 0.12e-6 * np.column_stack((np.cos(angle), np.sin(angle))))
    groups = []
    membrane_ids = []
    offset = 0
    cell_to_mems = []
    for index, row in enumerate(polygons):
        names = ["cell-" + str(index) + "/segment-" + str(j) for j in range(len(row))]
        groups.append(names)
        membrane_ids.extend(names)
        cell_to_mems.append(list(range(offset, offset + len(row))))
        offset += len(row)
    target_membranes = [value for index in selected for value in cell_to_mems[index]]
    face_coords = points[faces]
    face_centre = face_coords.mean(axis=1)
    vector = points[edges[:, 1]] - points[edges[:, 0]]
    length = np.linalg.norm(vector, axis=1)
    mesh = dict(
        tri_verts=points.copy(),
        tri_edges=edges.copy(),
        tri_cells=faces.copy(),
        tcell_verts=face_coords.copy(),
        tri_ccents=face_centre.copy(),
        tri_rcircs=np.full(4, 0.5e-6),
        tri_cents=face_centre.copy(),
        tri_sa=np.full(4, 0.25e-12),
        tri_mids=points[edges].mean(axis=1),
        tri_edge_i=np.arange(len(edges), dtype=np.int64),
        tri_edge_len=length,
        tri_tang=vector / length[:, None],
        vor_sa=np.full(len(points), 1e-12),
        vor_edge_len=np.full(len(edges), 0.5e-6),
        _tverts_to_tcell=object_rows(vfaces),
        tverts_to_tedges=object_rows(vedges),
        n_tverts=len(points),
        n_tedges=len(edges),
        n_tcell=len(faces),
        bflags_tverts=np.asarray([0, 1, 2, 3]),
        bflags_tedges=np.asarray([0, 3, 5, 7]),
        inner_tvert_i=np.asarray([4]),
        make_all_operators=False,
        stale_auxiliary_witness=np.arange(7, dtype=float),
    )
    if case == "nonfinite_mesh_raw":
        mesh["tri_verts"][2, 0] = np.nan
    cells = dict(
        cell_i=np.arange(len(points)),
        mem_i=np.arange(offset),
        cell_to_mems=object_rows(cell_to_mems),
        cell_to_nn_full=object_rows(vedges),
        map_cell2ecm=np.arange(len(points)),
        map_mem2ecm=np.arange(offset) % 31,
        cell_centres=points.copy(),
        ecm_verts=object_rows(polygons),
    )
    sim = dict(
        cdl=len(points),
        mdl=offset,
        edl=31,
        cc_cells=np.arange(10, dtype=float).reshape(2, 5) + 1,
        cc_at_mem=np.ones((2, offset)),
        cc_env=np.ones((2, 31)),
        endo_retic=None,
    )
    return dict(
        kind="cells.supplied_post_cut_source_request@1",
        mode=mode,
        classification="manufactured_supplied_source_state",
        provenance=(
            "Literal five-vertex supplied source snapshot; "
            "no cold mesh provenance or physical Voronoi claim."
        ),
        sim=sim,
        cells=cells,
        mesh=mesh,
        selection=dict(
            cells=np.asarray(selected, dtype=np.int64),
            membranes=np.asarray(target_membranes, dtype=np.int64),
            provenance="Explicit supplied picker occurrences",
        ),
        parameters=dict(
            is_ecm=True,
            Ca_dyn=False,
            cell_space=0.05e-6,
            scale_cell=0.9,
            cell_radius=0.05e-6,
            cell_height=1e-6,
            tm=5e-9,
        ),
        handler={},
        owners=dict(
            cell_ids=["cell-" + str(i) for i in range(5)],
            membrane_ids=membrane_ids,
            mesh_edge_ids=["mesh-edge-" + str(i) for i in range(len(edges))],
            mesh_face_ids=["mesh-face-" + str(i) for i in range(len(faces))],
            cell_membrane_ids=groups,
        ),
    )


def contact_fixture(*, ambiguous=False):
    # Separately named supplied contact-helper seam, never a completed full cut.
    raw = fixture(mode="contact_only")
    mids = np.asarray([[0.0, 0.0], [0.01e-6, 0.0], [2e-6, 0.0]])
    normals = np.asarray([[1.0, 0.0], [-1.0, 0.0], [1.0, 0.0]])
    if ambiguous:
        mids = np.asarray([[0.0, 0.0], [0.01e-6, 0.0], [0.02e-6, 0.0]])
    raw["cells"] = dict(
        cell_i=np.arange(3),
        mem_i=np.arange(3),
        mem_mids_flat=mids,
        mem_vects_flat=np.column_stack(
            (mids, normals, np.column_stack((-normals[:, 1], normals[:, 0])))
        ),
        mem_to_cells=np.arange(3),
        cell_to_mems=object_rows([[0], [1], [2]]),
        mem_sa=np.full(3, 1e-12),
        cell_centres=np.asarray([[-1e-6, 0.0], [1e-6, 0.0], [3e-6, 0.0]]),
        ecm_verts=object_rows(
            [
                np.asarray([[i * 2e-6, 0.0], [i * 2e-6 + 1e-6, 0.0], [i * 2e-6, 1e-6]])
                for i in range(3)
            ]
        ),
    )
    raw["owners"] = dict(
        cell_ids=["a", "b", "c"],
        membrane_ids=["a/s", "b/s", "c/s"],
        mesh_edge_ids=[],
        mesh_face_ids=[],
        cell_membrane_ids=[["a/s"], ["b/s"], ["c/s"]],
    )
    raw["selection"] = dict(
        cells=np.asarray([], dtype=np.int64),
        membranes=np.asarray([], dtype=np.int64),
        provenance="Empty supplied helper selection",
    )
    raw["provenance"] = "Manufactured supplied mem_processing/near_neigh/calc_gj_vects input only."
    raw["mesh"] = {}
    raw["parameters"]["cell_radius"] = 1e-6
    return raw
