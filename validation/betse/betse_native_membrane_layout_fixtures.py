"""Unexecuted supplied schema specimens; no native producer or geometry engine."""

import hashlib
from pathlib import Path

CASES = (
    "little-endian-fortran",
    "big-endian",
    "strided",
    "object-owner-rows",
    "rectangular-object-owners",
    "nonunit-schema-only",
)
REFUSALS = (
    "missing-vectors",
    "four-columns",
    "float32",
    "nonfinite",
    "midpoint-bits",
    "midpoint-dtype",
    "owner-out-of-range",
    "owner-order",
    "duplicate-owner-index",
    "missing-owner-row",
    "cell-axis",
    "membrane-axis",
    "units",
    "columns",
    "law",
    "geometry-claim",
    "evidence",
    "owner-order-declaration",
)
CORRUPTIONS = (
    "native-parent-bytes",
    "owner-cells",
    "owner-local",
    "view-law",
    "view-column-map",
    "view-bytes",
    "view-units",
    "physical-gate",
)
RESEALED = ("snapshot-units", "layout-owner", "layout-gates", "view-columns")


def declaration():
    return dict(
        kind="cells.betse_native_membrane_layout_declaration@1",
        opted_in_law="betse_native_six_column_membrane_layout_v1_5_0@1",
        columns=["mid_x", "mid_y", "nx", "ny", "tx", "ty"],
        column_units=["m", "m", "1", "1", "1", "1"],
        owner_order="native_cell_major_then_membrane_local_i",
        geometry_classification="unqualified_native_layout",
        evidence=[
            dict(
                path=str(Path(__file__)),
                sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            )
        ],
    )


def specification(case):
    if case not in CASES:
        raise ValueError("Unknown supplied schema specimen")
    return dict(
        case=case,
        declaration=declaration(),
        source_kind="supplied_schema_values_no_native_run",
        vectors=[
            [-0.0, 0.0, 0.0, -1.0, 1.0, 0.0],
            [2.0, 3.0, 1.0, 0.0, 0.0, 1.0],
            [4.0, 5.0, 0.0, 1.0, -1.0, 0.0],
            [6.0, 7.0, -1.0, 0.0, 0.0, -1.0],
            [8.0, 9.0, 0.0, -1.0, 1.0, 0.0],
            [10.0, 11.0, 1.0, 0.0, 0.0, 1.0],
            [12.0, 13.0, 0.0, 1.0, -1.0, 0.0],
        ],
        dtype=">f8" if case == "big-endian" else "<f8",
        index_dtype=">i4" if case == "big-endian" else "<i8",
        cell_to_mems=[[0, 1, 2], [3, 4, 5, 6]],
        physical_geometry_claim=False,
        native_seed_init_history_claim=False,
    )


def build(spec, mutation=None):
    # NumPy is used only for prospective native-store construction, never by
    # static preparation or by the independent byte/schema checker.
    import numpy as np

    case = spec["case"]
    rows = spec["vectors"][:6] if case == "rectangular-object-owners" else spec["vectors"]
    dtype = np.dtype(spec["dtype"])
    vectors = np.array(rows, dtype=dtype, order="F" if case == "little-endian-fortran" else "C")
    if case == "strided":
        backing = np.zeros((len(rows), 12), dtype=dtype)
        backing[:, ::2] = vectors
        vectors = backing[:, ::2]
    if case == "nonunit-schema-only":
        vectors[:, 2:6] = [3.0, 4.0, 7.0, 8.0]
    index_dtype = np.dtype(spec["index_dtype"])
    local = [list(row) for row in spec["cell_to_mems"]]
    if case == "rectangular-object-owners":
        local[1] = [3, 4, 5]
    groups = [np.array(row, dtype=index_dtype) for row in local]
    if case == "object-owner-rows":
        groups = [np.array(row, dtype=object) for row in local]
    owner_rows = np.asarray(groups, dtype=object)
    owners = dict(
        cell_i=[0, 1],
        mem_i=list(range(len(rows))),
        mem_to_cells=np.array([0, 0, 0] + [1] * (len(rows) - 3), dtype=index_dtype),
        cell_to_mems=owner_rows,
        mem_mids_flat=vectors[:, :2].copy(order="C"),
        mem_vects_flat=vectors,
    )
    declared = {
        key: [dict(row) for row in value]
        if key == "evidence"
        else list(value)
        if isinstance(value, list)
        else value
        for key, value in spec["declaration"].items()
    }
    if mutation == "missing-vectors":
        del owners["mem_vects_flat"]
    elif mutation == "four-columns":
        owners["mem_vects_flat"] = vectors[:, :4].copy()
    elif mutation == "float32":
        owners["mem_vects_flat"] = vectors.astype("<f4")
    elif mutation == "nonfinite":
        owners["mem_vects_flat"][0, 5] = np.inf
    elif mutation == "midpoint-bits":
        owners["mem_mids_flat"][0, 0] = 0.0
    elif mutation == "midpoint-dtype":
        owners["mem_mids_flat"] = owners["mem_mids_flat"].astype(">f8")
    elif mutation == "owner-out-of-range":
        owners["mem_to_cells"][0] = 2
    elif mutation == "owner-order":
        owners["mem_to_cells"][[0, 3]] = owners["mem_to_cells"][[3, 0]]
    elif mutation == "duplicate-owner-index":
        owners["cell_to_mems"][0][1] = 0
    elif mutation == "missing-owner-row":
        owners["cell_to_mems"] = owners["cell_to_mems"][:1]
    elif mutation == "cell-axis":
        owners["cell_i"] = [1, 0]
    elif mutation == "membrane-axis":
        owners["mem_i"] = list(reversed(owners["mem_i"]))
    elif mutation == "units":
        declared["column_units"][0] = "um"
    elif mutation == "columns":
        declared["columns"][2:6] = ["tx", "ty", "nx", "ny"]
    elif mutation == "law":
        declared["opted_in_law"] = "inferred-native"
    elif mutation == "geometry-claim":
        declared["geometry_classification"] = "physical_mesh_qualified"
    elif mutation == "evidence":
        declared["evidence"] = []
    elif mutation == "owner-order-declaration":
        declared["owner_order"] = "sort_by_midpoints"
    elif mutation is not None:
        raise ValueError("Unknown input control")
    return owners, declared
