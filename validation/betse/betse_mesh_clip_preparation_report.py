"""Count observed clipping branches from saved typed actual traces only."""

import hashlib
import json
import struct
from pathlib import Path

import numpy as np

from validation.betse import betse_initial_mesh_preparation_wire as wire


def _payload(record, archive):
    prefix = record["column_prefix"] + "__"
    columns = {
        name[len(prefix) :]: archive[name] for name in archive.files if name.startswith(prefix)
    }
    # Validate every numeric column against the typed saved descriptor.
    wire.owned_signature(record["descriptor"], columns)
    raw = json.dumps(record["descriptor"], sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(raw.encode()).hexdigest() != record["identity"]:
        raise ValueError("Changed branch-report input descriptor")

    def decode(node):
        kind = node["kind"]
        if kind == "numeric_array":
            return columns[node["column"]].tolist()
        if kind == "numpy_scalar":
            return np.frombuffer(bytes.fromhex(node["bits"]), dtype=np.dtype(node["dtype"]))[
                0
            ].item()
        if kind == "float":
            return struct.unpack("<d", bytes.fromhex(node["bits"]))[0]
        if kind == "dict":
            return {decode(k): decode(v) for k, v in node["items"]}
        if kind == "object_array":
            values = [decode(v) for v in node["items"]]
            shape = node["source_layout"]["shape"]

            def reshape(start, axes):
                if not axes:
                    return values[start]
                width = int(np.prod(axes[1:], dtype=int))
                return [reshape(start + i * width, axes[1:]) for i in range(axes[0])]

            return reshape(0, shape)
        if "items" in node:
            return [decode(v) for v in node["items"]]
        return node["value"]

    return decode(record["descriptor"])


def branch_counts(path):
    path = Path(path)
    actual = json.loads(path.read_text())
    if actual.get("mode") != "actual_before_native":
        raise ValueError("Whole clipping branch counts require an actual mesh trace")
    counts = dict(
        cells_visited=0,
        completed_cell_traces=0,
        incomplete_cell_traces=0,
        all_vertices_nonzero_emitted=0,
        partial_clip_attempts=0,
        partial_clip_emitted=0,
        all_vertices_zero_discarded=0,
        partial_centre_zero_discarded=0,
        partial_no_centroid_discarded=0,
        short_polygon_discarded=0,
        all_centroids_discarded_cases=0,
        centroid_seed_replacements=0,
    )
    emitted = False
    with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
        for event in actual["events"]:
            if event["kind"] == "clip_cell_enter":
                counts["cells_visited"] += 1
                emitted = False
            elif event["kind"] == "method_enter" and event["method"] == "clip_counterclockwise":
                counts["partial_clip_attempts"] += 1
            elif event["kind"] == "clip_centroid_emitted":
                payload = _payload(event["payload"], archive)
                key = (
                    "all_vertices_nonzero_emitted"
                    if payload["branch"] == "all_vertices_nonzero"
                    else "partial_clip_emitted"
                )
                counts[key] += 1
                emitted = True
            elif event["kind"] == "clip_cell_exit":
                counts["completed_cell_traces"] += 1
                frame = _payload(event["payload"], archive)["locals"]
                if len(frame["poly_ind"]) < 3:
                    counts["short_polygon_discarded"] += 1
                    continue
                inside = sum(v == 1 for v in frame["point_check"])
                if inside == 0:
                    counts["all_vertices_zero_discarded"] += 1
                elif inside < len(frame["cell_poly"]) and np.asarray(frame["cent_val"]).item() != 1:
                    counts["partial_centre_zero_discarded"] += 1
                elif inside < len(frame["cell_poly"]) and not emitted:
                    counts["partial_no_centroid_discarded"] += 1
            elif event["kind"] == "clip_seed_replacement":
                payload = _payload(event["payload"], archive)
                counts["centroid_seed_replacements"] += 1
                counts["all_centroids_discarded_cases"] += int(
                    len(payload["derived_point_ids"]) == 0
                )
    counts["incomplete_cell_traces"] = counts["cells_visited"] - counts["completed_cell_traces"]
    return dict(
        case=path.stem.removesuffix("-actual"),
        source_state_status=actual["state"]["status"],
        counts=counts,
        whole_partial_clipping_observed=counts["partial_clip_attempts"] > 0,
        whole_partial_centroid_emission_observed=counts["partial_clip_emitted"] > 0,
        all_discarded_whole_case_observed=counts["all_centroids_discarded_cases"] > 0,
        topology_qualified=False,
        isolated_keeper_witness_is_whole_partial_case=False,
    )


def summarize(directory):
    cases = []
    for path in sorted(Path(directory).glob("*-actual.json")):
        if json.loads(path.read_text()).get("mode") == "actual_before_native":
            cases.append(branch_counts(path))
    keys = cases[0]["counts"] if cases else ()
    totals = {key: sum(row["counts"][key] for row in cases) for key in keys}
    return dict(
        scope="Observed branches in retained actual mesh traces only",
        cases=cases,
        totals=totals,
        partial_clip_whole_cases=sum(r["whole_partial_clipping_observed"] for r in cases),
        partial_emission_whole_cases=sum(
            r["whole_partial_centroid_emission_observed"] for r in cases
        ),
        all_discarded_whole_cases=sum(r["all_discarded_whole_case_observed"] for r in cases),
        only_observed_branches_receive_source_scope_credit=True,
        isolated_keeper_witness_is_whole_partial_case=False,
        declared_cases_do_not_guarantee_branch_coverage=True,
        topology_qualified=False,
        downstream_geometry_admitted=False,
    )
