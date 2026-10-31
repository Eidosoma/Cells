"""Independent stdlib byte/schema/owner verification; no production imports."""

import argparse
import hashlib
import json
import math
import os
import struct
import traceback
from pathlib import Path

LAW = "betse_native_six_column_membrane_layout_v1_5_0@1"
ROLES = ["mid_x", "mid_y", "nx", "ny", "tx", "ty"]
UNITS = ["m", "m", "1", "1", "1", "1"]
GATES = dict(
    physical_geometry_admitted=False,
    vector_geometry_qualified=False,
    native_seed_init_history_proven=False,
    initialization_handoff_integrated=False,
    ordinary_ECM_loop_ready=False,
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _buffer(value, *, geometry, rank):
    if set(value) != {"dtype", "shape", "raw", "original_strides"}:
        raise ValueError("Independent typed-buffer field inventory differs")
    forms = (
        {"<f8": "<d", ">f8": ">d"}
        if geometry
        else {
            "<i4": "<i",
            ">i4": ">i",
            "<i8": "<q",
            ">i8": ">q",
            "<u4": "<I",
            ">u4": ">I",
            "<u8": "<Q",
            ">u8": ">Q",
        }
    )
    shape, strides = value["shape"], value["original_strides"]
    if (
        value["dtype"] not in forms
        or len(shape) != rank
        or len(strides) != rank
        or any(type(v) is not int or not 1 <= v <= 128 for v in shape)
        or any(type(v) is not int for v in strides)
        or set(value["raw"]) != {"bytes_hex"}
    ):
        raise ValueError("Independent dtype/shape/stride declaration is unsupported")
    raw = bytes.fromhex(value["raw"]["bytes_hex"])
    form = forms[value["dtype"]]
    if len(raw) != math.prod(shape) * struct.calcsize(form) or len(raw) > 65536:
        raise ValueError("Independent typed payload size differs")
    values = [row[0] for row in struct.iter_unpack(form, raw)]
    if geometry and any(not math.isfinite(v) for v in values):
        raise ValueError("Independent finite-binary64 schema failed")
    return values, raw


def _indices(value):
    kind = value["kind"]
    if kind == "array_indices" and set(value) == {"kind", "buffer"}:
        return _buffer(value["buffer"], geometry=False, rank=1)[0]
    if kind == "python_indices" and set(value) == {"kind", "container", "values"}:
        if value["container"] not in ("list", "tuple"):
            raise ValueError("Independent original sequence type differs")
    elif kind == "object_indices" and set(value) == {"kind", "header", "values"}:
        header = value["header"]
        if (
            set(header) != {"dtype", "shape", "strides"}
            or header["dtype"] != "|O"
            or header["shape"] != [len(value["values"])]
            or len(header["strides"]) != 1
            or any(type(stride) is not int for stride in header["strides"])
        ):
            raise ValueError("Independent original object row metadata differs")
    else:
        raise ValueError("Independent integer index representation is incomplete")
    if any(type(index) is not int for index in value["values"]):
        raise ValueError("Independent owner index scalar types changed")
    return value["values"]


def verify(original, layout, views):
    rows = []

    def require(condition, label):
        rows.append(dict(label=label, passed=bool(condition)))
        if not condition:
            raise ValueError("Independent source/schema/owner refusal: " + label)

    try:
        declaration = original["declaration"]
        require(
            set(declaration)
            == {
                "kind",
                "opted_in_law",
                "columns",
                "column_units",
                "owner_order",
                "geometry_classification",
                "evidence",
            },
            "complete_declaration",
        )
        require(
            declaration["kind"] == "cells.betse_native_membrane_layout_declaration@1"
            and declaration["opted_in_law"] == LAW
            and declaration["columns"] == ROLES
            and declaration["column_units"] == UNITS
            and declaration["owner_order"] == "native_cell_major_then_membrane_local_i"
            and declaration["geometry_classification"] == "unqualified_native_layout",
            "six_roles_mixed_units_and_no_geometry_claim",
        )
        require(bool(declaration["evidence"]), "original_evidence_link_present")
        for link in declaration["evidence"]:
            require(
                set(link) == {"path", "sha256"}
                and type(link["path"]) is str
                and bool(link["path"])
                and type(link["sha256"]) is str
                and len(link["sha256"]) == 64
                and all(c in "0123456789abcdef" for c in link["sha256"]),
                "evidence_identity",
            )
        observation, source = original["observation"], original["source"]
        require(
            observation == "supplied_owner_stores"
            and source is None
            or (
                observation == "pinned_native_Cells_stores"
                and source is not None
                and set(source) == {"qualified_type", "source", "sha256"}
                and source["qualified_type"] == "betse.science.cells.Cells"
                and type(source["source"]) is str
                and bool(source["source"])
                and source["sha256"]
                == "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"
            ),
            "explicit_source_observation_without_history_inference",
        )
        require(
            original["identity"]
            == digest([LAW, declaration, observation, original["entries"], source]),
            "original_snapshot_seal",
        )
        require(layout["snapshot"] == original, "complete_original_snapshot_retained")
        entries = original["entries"]
        require(
            set(entries)
            == {
                "cell_i",
                "mem_i",
                "mem_to_cells",
                "cell_to_mems",
                "mem_mids_flat",
                "mem_vects_flat",
            },
            "complete_owner_inventory",
        )
        for key, entry in entries.items():
            require(
                set(entry) == {"present", "captured", "value"}
                and entry["present"] is True
                and entry["captured"] is True,
                "actual_store/" + key,
            )
        cell_axis, membrane_axis = (_indices(entries[key]["value"]) for key in ("cell_i", "mem_i"))
        n, m = len(cell_axis), len(membrane_axis)
        require(
            1 <= n <= 16
            and 1 <= m <= 128
            and cell_axis == list(range(n))
            and membrane_axis == list(range(m)),
            "unchanged_source_row_axes",
        )
        owner, _ = _buffer(entries["mem_to_cells"]["value"], geometry=False, rank=1)
        groups = entries["cell_to_mems"]["value"]
        require(
            set(groups) == {"kind", "header", "rows"}
            and groups["kind"] == "native_cell_to_mems_rows"
            and len(groups["rows"]) == n,
            "complete_local_owner_rows",
        )
        header = groups["header"]
        require(set(header) == {"container", "dtype", "shape", "strides"}, "owner_container_header")
        if header["container"] == "ndarray":
            require(
                header["dtype"] == "|O"
                and len(header["shape"]) in (1, 2)
                and header["shape"][0] == n
                and len(header["strides"]) == len(header["shape"])
                and all(type(v) is int and 1 <= v <= 128 for v in header["shape"])
                and all(type(v) is int for v in header["strides"]),
                "original_object_owner_container",
            )
        else:
            require(
                header["container"] in ("list", "tuple")
                and header["dtype"] is None
                and header["shape"] == [n]
                and header["strides"] is None,
                "original_sequence_owner_container",
            )
        expected_owner, expected_local, flat = [], [], []
        for cell, row in enumerate(groups["rows"]):
            indices = _indices(row)
            require(bool(indices), "nonempty_local_owner_axis")
            if len(header["shape"]) == 2:
                require(len(indices) == header["shape"][1], "original_local_owner_shape")
            for local, index in enumerate(indices):
                flat.append(index)
                expected_owner.append(cell)
                expected_local.append(local)
        require(flat == membrane_axis and owner == expected_owner, "source_inverse_owner_maps")
        require(
            layout["owner_cells"] == expected_owner
            and layout["owner_local_indices"] == expected_local,
            "layout_owner_and_local_order",
        )
        vectors, mids = (entries[key]["value"] for key in ("mem_vects_flat", "mem_mids_flat"))
        _, raw = _buffer(vectors, geometry=True, rank=2)
        _, midpoint_raw = _buffer(mids, geometry=True, rank=2)
        require(
            vectors["shape"] == [m, 6]
            and mids["shape"] == [m, 2]
            and vectors["dtype"] == mids["dtype"],
            "full_six_column_binary64_schema",
        )
        require(
            b"".join(raw[48 * i : 48 * i + 16] for i in range(m)) == midpoint_raw,
            "bitwise_duplicate_midpoint_roles",
        )
        require(
            layout["columns"] == ROLES
            and layout["column_units"] == UNITS
            and layout["gates"] == GATES,
            "schema_only_layout_roles_and_gates",
        )
        require(
            layout["identity"]
            == digest([LAW, original, expected_owner, expected_local, ROLES, UNITS, GATES]),
            "layout_seal",
        )
        for view in views:
            choices = {
                "cells.native_six_to_midpoint_normal_xy@1": [0, 1, 2, 3],
                "cells.native_six_to_normal_tangent_xy@1": [2, 3, 4, 5],
            }
            require(view["conversion_law"] in choices, "explicit_conversion_name")
            selected = choices[view["conversion_law"]]
            require(
                view["parent"] == layout and view["selected_columns"] == selected,
                "view_retains_full_parent_and_column_map",
            )
            roles = [ROLES[i] for i in selected]
            units = [UNITS[i] for i in selected]
            require(
                view["columns"] == roles
                and view["column_units"] == units
                and view["gates"] == GATES,
                "view_roles_units_and_closed_gates",
            )
            _, actual_bytes = _buffer(view["values"], geometry=True, rank=2)
            expected_bytes = b"".join(
                raw[i * 48 + c * 8 : i * 48 + (c + 1) * 8] for i in range(m) for c in selected
            )
            require(
                view["values"]["dtype"] == vectors["dtype"]
                and view["values"]["shape"] == [m, 4]
                and view["values"]["original_strides"] == [32, 8]
                and actual_bytes == expected_bytes,
                "exact_view_bytes_without_coercion",
            )
            require(
                view["identity"]
                == digest(
                    [layout, view["conversion_law"], selected, roles, units, view["values"], GATES]
                ),
                "explicit_view_seal",
            )
        return dict(
            kind="cells.native_membrane_layout_independent_check@1",
            passed=True,
            rows=rows,
            checked_views=len(views),
            numeric_tolerances_used=False,
            physical_geometry_admitted=False,
            native_seed_init_history_proven=False,
        )
    except Exception as error:
        return dict(
            kind="cells.native_membrane_layout_independent_check@1",
            passed=False,
            rows=rows,
            reason=str(error),
            type=type(error).__name__,
            traceback=traceback.format_exc(),
            numeric_tolerances_used=False,
            physical_geometry_admitted=False,
            native_seed_init_history_proven=False,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text())
    report = verify(payload["original"], payload["layout"], payload["views"])
    report["original_input_path"] = str(args.input)
    with args.output.open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
