"""Read retained typed arrays and reduce integer incidence; no geometry solve.

No scientific packages, source kernels, candidate adapter or reference routines
are imported or evaluated. Existing geometric verdicts are quoted separately
from new integer-owner observations. Original files are opened read-only.
"""

import ast
import hashlib
import itertools
import json
import math
import os
import struct
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

RUN = Path("/mnt/workspaces/Cells/stable-initial-mesh-preparation-20261030-01")
REVIEW_SHA256 = "b88ae9a987a03481c1e95c3e320dc004ceb2eef64213f131aef38c9236d75539"
MAX_BYTES = 128 * 2**20
MAX_ELEMENTS = 262144


class SavedSourceRejected(ValueError):
    def __init__(self, reason, evidence):
        super().__init__(reason)
        self.saved_evidence = evidence


def evidence_run():
    return Path(os.environ.get("CELLS_STABLE_MESH_PHYSICAL_SAVED_RUN", str(RUN)))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Require bounded regular saved evidence")
    return json.loads(path.read_text())


def array(archive, name):
    info = archive.getinfo(name + ".npy")
    if info.file_size > MAX_BYTES:
        raise ValueError("Saved array exceeds bounded evidence reader")
    with archive.open(info) as stream:
        magic = stream.read(8)
        if magic[:6] != b"\x93NUMPY" or magic[6] not in (1, 2, 3):
            raise ValueError("Require a saved NPY numeric column")
        width = 2 if magic[6] == 1 else 4
        count = struct.unpack("<H" if width == 2 else "<I", stream.read(width))[0]
        if count > 65536:
            raise ValueError("Unexpected saved NPY header size")
        header = ast.literal_eval(stream.read(count).decode())
        raw = stream.read()
    dtype, shape = header["descr"], tuple(header["shape"])
    if type(dtype) is not str or dtype[1:2] not in "biuf" or math.prod(shape) > MAX_ELEMENTS:
        raise ValueError("Require bounded real saved columns; pickle/object data is refused")
    width = int(dtype[2:])
    if len(raw) != math.prod(shape) * width:
        raise ValueError("Saved array byte count differs from shape")
    if header["fortran_order"] and len(shape) > 1:
        strides = [math.prod(shape[:i]) for i in range(len(shape))]
        raw = b"".join(
            raw[sum(i * s for i, s in zip(ix, strides, strict=True)) * width :][:width]
            for ix in itertools.product(*(range(n) for n in shape))
        )
    return dtype, shape, raw


def reshape(values, shape):
    if not shape:
        return values[0]
    width = math.prod(shape[1:])
    return [reshape(values[i * width : (i + 1) * width], shape[1:]) for i in range(shape[0])]


def _unpack(dtype, raw):
    codes = {
        ("i", 4): "i",
        ("i", 8): "q",
        ("u", 4): "I",
        ("u", 8): "Q",
        ("f", 4): "f",
        ("f", 8): "d",
        ("b", 1): "?",
    }
    width = int(dtype[2:])
    code = codes[dtype[1], width]
    return list(
        struct.unpack((">" if dtype[0] == ">" else "<") + str(len(raw) // width) + code, raw)
    )


def decode(record, archive):
    descriptor = record["descriptor"]
    canonical = json.dumps(descriptor, sort_keys=True, separators=(",", ":"))
    if hashlib.sha256(canonical.encode()).hexdigest() != record["identity"]:
        raise ValueError("Saved typed descriptor identity differs")
    prefix, seen = record["column_prefix"] + "__", set()

    def visit(node):
        kind = node["kind"]
        if kind == "numeric_array":
            name = node["column"]
            if name in seen:
                raise ValueError("Repeated saved column identifier")
            seen.add(name)
            dtype, shape, raw = array(archive, prefix + name)
            if (
                dtype != node["source_layout"]["dtype"]
                or list(shape) != node["source_layout"]["shape"]
                or hashlib.sha256(raw).hexdigest() != node["sha256"]
            ):
                raise ValueError("Saved column hash/axis/dtype differs")
            return reshape(_unpack(dtype, raw), shape)
        if kind == "object_array":
            return reshape([visit(n) for n in node["items"]], node["source_layout"]["shape"])
        if kind == "dict":
            return {visit(k): visit(v) for k, v in node["items"]}
        if kind == "float":
            return struct.unpack("<d", bytes.fromhex(node["bits"]))[0]
        if kind == "numpy_scalar":
            return _unpack(node["dtype"], bytes.fromhex(node["bits"]))[0]
        if "items" in node:
            return [visit(n) for n in node["items"]]
        return node["value"]

    result = visit(descriptor)
    expected = {
        name[:-4][len(prefix) :]
        for name in archive.namelist()
        if name.endswith(".npy") and name.startswith(prefix)
    }
    if seen != expected:
        raise ValueError("Incomplete saved numeric columns")
    return result


def pairs(ring):
    return zip(ring, ring[1:] + ring[:1], strict=True)


def incidence_observations(cache):
    """Integer relationships of saved rings, never corrected output geometry."""
    faces, edges = cache["tri_cells"], cache["tri_edges"]
    lookup = {tuple(sorted(edge)): i for i, edge in enumerate(edges)}
    if len(lookup) != len(edges):
        raise ValueError("Saved primal edge IDs are not unique")
    expected, owners, directed = [], [[] for _ in edges], []
    for fi, face in enumerate(faces):
        row, signs = [], []
        for a, b in pairs(face):
            ei = lookup[tuple(sorted((a, b)))]
            row.append(ei)
            owners[ei].append(fi)
            signs.append(1 if edges[ei] == [a, b] else -1)
        expected.append(row)
        directed.append(signs)
    actual = cache["tcell_to_tedges"]
    directed_only = [
        [ei for ei, sign in zip(row, signs, strict=True) if sign == 1]
        for row, signs in zip(expected, directed, strict=True)
    ]
    omitted = [
        dict(face=i, missing_edge_ids=[ei for ei in row if ei not in actual[i]])
        for i, row in enumerate(expected)
        if set(row) != set(actual[i])
    ]
    actual_inverse = cache["tedges_to_tcell"]
    inverse_mismatches = [
        dict(edge=i, original=actual_inverse[i], incident_faces=row)
        for i, row in enumerate(owners)
        if sorted(row) != sorted(actual_inverse[i])
    ]
    dual = defaultdict(list)
    for owner, face in enumerate(cache["vor_cells"]):
        for a, b in pairs(face):
            dual[tuple(sorted((a, b)))].append(owner)
    by_owner = defaultdict(list)
    for edge, row in dual.items():
        if len(row) == 2 and row[0] != row[1]:
            by_owner[tuple(sorted(row))].append(list(edge))
    candidate_counts = [len(by_owner[tuple(sorted(edge))]) for edge in edges]
    pairing_mismatches = []
    for i, edge in enumerate(edges):
        candidates = by_owner[tuple(sorted(edge))]
        selected = cache["vor_edges"][i]
        if len(candidates) != 1 or tuple(sorted(selected)) != tuple(candidates[0]):
            pairing_mismatches.append(
                dict(
                    primal_edge=i,
                    primal_owners=edge,
                    native_selected_dual_edge=selected,
                    dual_complex_owner_candidates=candidates,
                )
            )
    selected_counts = Counter(tuple(sorted(edge)) for edge in cache["vor_edges"])
    return dict(
        vertices=len(cache["tri_verts"]),
        faces=len(faces),
        primal_edges=len(edges),
        expected_face_edge_occurrences=sum(map(len, faces)),
        original_face_edge_occurrences=sum(map(len, actual)),
        omitted_reverse_occurrences=sum(len(row["missing_edge_ids"]) for row in omitted),
        directed_only_source_rule_matches=actual == directed_only,
        all_primal_edges_have_one_or_two_face_owners=all(len(row) in (1, 2) for row in owners),
        inverse_mismatches=inverse_mismatches,
        omitted=omitted,
        unique_endpoint_incidence_matches_original=all(
            sorted(row) == [i for i, edge in enumerate(edges) if vi in edge]
            for vi, row in enumerate(cache["tverts_to_tedges"])
        ),
        dual_polygon_edges=len(dual),
        selected_dual_edges=len(cache["vor_edges"]),
        dual_polygon_outer_boundary_edges=sum(len(row) == 1 for row in dual.values()),
        dual_owner_candidate_count_histogram=dict(sorted(Counter(candidate_counts).items())),
        owner_pairing_mismatches=pairing_mismatches,
        repeated_selected_dual_edges=[
            dict(edge=list(edge), occurrences=count)
            for edge, count in selected_counts.items()
            if count > 1
        ],
        original_dual_boundary_flags=cache["bflags_vedges"],
        boundary_flag_indices_outside_selected_axis=[
            i for i in cache["bflags_vedges"] if not 0 <= i < len(cache["vor_edges"])
        ],
        physical_coordinates_recomputed=False,
        new_candidate_adapter_evaluated=False,
    )


def diagnose(run=RUN):
    run = Path(run)
    result, review = read(run / "result.json"), read(run / "root-review-01/REVIEW.json")
    if sha(run / "result.json") != review["bindings"]["result_sha256"]:
        raise ValueError("Changed retained failed result")
    if REVIEW_SHA256 and sha(run / "root-review-01/REVIEW.json") != REVIEW_SHA256:
        raise ValueError("Changed retained independent review")
    cases, bindings = [], {}
    for reviewed in review["cases"]:
        unit = reviewed["check"]
        paths = sorted((run / "evidence" / unit / "stable-initial-mesh").glob("*-actual.json"))
        if len(paths) != 1:
            raise ValueError("Require one complete original actual record per declared unit")
        path = paths[0]
        for source_path in (path, path.with_suffix(".npz")):
            relative = str(source_path.relative_to(run))
            actual_sha = sha(source_path)
            if actual_sha != result["artifacts"][relative]:
                raise ValueError("Changed original mesh evidence: " + relative)
            bindings[relative] = actual_sha
        original = read(path)
        status = original["state"]["status"]
        entry = dict(
            case=original["case"],
            unit=unit,
            original_status=status,
            original_record=str(path),
            json_sha256=sha(path),
            npz_sha256=sha(path.with_suffix(".npz")),
        )
        if reviewed["role"] == "raw":
            entry.update(
                raw_failure_preserved=True,
                failure_stage=original["state"]["failure_stage"],
                failure_type=original["state"]["failure_type"],
                physical_candidate=False,
            )
        else:
            with zipfile.ZipFile(path.with_suffix(".npz")) as archive:
                saved = decode(original["final"], archive)
            entry["saved_integer_observations"] = incidence_observations(saved)
            entry["previous_geometry_verdict"] = reviewed["whole_mesh"]
            entry["retained_point_ids"] = original["state"]["retained_point_ids"]
        cases.append(entry)
    return dict(
        kind="cells.stable_mesh_physical_reconstruction_saved_diagnosis@1",
        original_run=str(run),
        original_result_sha256=sha(run / "result.json"),
        original_review_sha256=sha(run / "root-review-01/REVIEW.json"),
        saved_artifact_sha256=bindings,
        cases=cases,
        original_complete_geometry_passes=0,
        original_complete_meshes=9,
        original_raw_failures=2,
        original_failure_reclassified=False,
        scope=dict(
            saved_integer_topology_only=True,
            geometric_verdicts="quoted original independent review",
            source_or_reference_routines_evaluated=False,
            candidate_adapter_evaluated=False,
            coordinates_areas_lengths_operators_recomputed=False,
            scientific_imports=False,
            fixtures_constructed=False,
            jobs_launched=False,
            jobs_polled=False,
        ),
    )


def retained_request(case, run=RUN):
    """Future request loading from original evidence, never invoked by diagnosis.

    This creates a candidate input only when explicitly called by a later
    authorized check. It evaluates no native/source/reference geometry body.
    """
    run = Path(run)
    result = read(run / "result.json")
    review = read(run / "root-review-01/REVIEW.json")
    if sha(run / "root-review-01/REVIEW.json") != REVIEW_SHA256:
        raise ValueError("Changed original review binding")
    if sha(run / "result.json") != review["bindings"]["result_sha256"]:
        raise ValueError("Changed original failed result binding")
    for row in review["cases"]:
        directory = run / "evidence" / row["check"] / "stable-initial-mesh"
        for path in directory.glob("*-actual.json"):
            actual = read(path)
            if actual["case"] != case:
                continue
            retained = dict(
                original_record=str(path),
                original_json=actual,
                archive=str(path.with_suffix(".npz")),
            )
            for source in (path, path.with_suffix(".npz")):
                expected = result["artifacts"][str(source.relative_to(run))]
                retained[str(source)] = dict(expected_sha256=expected, actual_sha256=sha(source))
                if retained[str(source)]["actual_sha256"] != expected:
                    raise SavedSourceRejected("Changed original saved case", retained)
            if actual["state"]["status"] != "stable_mesh_completed_unqualified":
                raise SavedSourceRejected(
                    "Raw source failure cannot become a completed candidate", retained
                )
            try:
                with zipfile.ZipFile(path.with_suffix(".npz")) as archive:
                    cache = decode(actual["final"], archive)
            except Exception as error:
                raise SavedSourceRejected(
                    "Retained typed cache decoding failed: " + str(error), retained
                ) from error
            return dict(
                kind="cells.stable_mesh_physical_reconstruction_request@1",
                opted_in_law="cells_stable_mesh_incidence_physical_reconstruction_candidate@1",
                evidence=dict(
                    case=case,
                    original_record=str(path),
                    record_sha256=sha(path),
                    archive_sha256=sha(path.with_suffix(".npz")),
                    cache_identity=actual["final"]["identity"],
                    original_status=actual["state"]["status"],
                    source_revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
                    saved_decode_scope="original_typed_saved_cache",
                ),
                cache=cache,
                retained_point_ids=actual["state"]["retained_point_ids"],
            )
    raise ValueError("Case is not an authenticated original saved mesh")


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=RUN)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = diagnose(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
