"""Independent stdlib topology/contact controls from archived actual inputs.

No Cells, NumPy, SciPy, native or JAX imports. Incidence pseudoinverses use exact
rational graph algebra; nearest and contact predicates use Decimal80/140.
"""

import json
import math
import os
import struct
import sys
from decimal import Decimal, localcontext
from fractions import Fraction


def decode_graph(text):
    raw = json.loads(text)
    nodes = raw["nodes"]
    cache = {}

    def shape_values(flat, shape):
        if not shape:
            return flat[0]
        if len(shape) == 1:
            return list(flat)
        stride = math.prod(shape[1:])
        return [
            shape_values(flat[i * stride : (i + 1) * stride], shape[1:]) for i in range(shape[0])
        ]

    def numeric(dtype, data):
        widths = {
            "f8": "d",
            "f4": "f",
            "i8": "q",
            "i4": "i",
            "u8": "Q",
            "u4": "I",
            "b1": "?",
            "u1": "B",
            "i1": "b",
        }
        endian = dtype[0]
        kind = dtype[1:]
        order = "<" if endian in "<|=" else ">"
        return [item[0] for item in struct.iter_unpack(order + widths[kind], bytes.fromhex(data))]

    def value(item):
        if not isinstance(item, dict):
            return item
        if "float64" in item:
            return float.fromhex(item["float64"])
        if "numpy_scalar" in item:
            return numeric(item["numpy_scalar"], item["data"])[0]
        index = item["ref"]
        if index in cache:
            return cache[index]
        node = nodes[index]
        kind = node["kind"]
        if kind in ("dict", "namespace", "dataclass"):
            out = {}
            cache[index] = out
            for key, child in node["items"]:
                out[key] = value(child)
        elif kind == "ndarray":
            if "items" in node:
                leaves = [value(child) for child in node["items"]]
            else:
                leaves = numeric(node["dtype"], node["data"])
            out = shape_values(leaves, node["shape"])
            cache[index] = out
        elif kind in ("list", "tuple", "set"):
            out = []
            cache[index] = out
            out.extend(value(child) for child in node["items"])
        else:
            raise ValueError("Unknown explicit typed graph node")
        return out

    return value(raw["root"])


def inverse(matrix):
    n = len(matrix)
    a = [
        [Fraction(value) for value in row] + [Fraction(i == j) for j in range(n)]
        for i, row in enumerate(matrix)
    ]
    for col in range(n):
        pivot = next((row for row in range(col, n) if a[row][col]), None)
        if pivot is None:
            raise ValueError("Exact rational graph system singular")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [value / scale for value in a[col]]
        for row in range(n):
            if row == col:
                continue
            scale = a[row][col]
            a[row] = [one - scale * two for one, two in zip(a[row], a[col], strict=True)]
    return [row[n:] for row in a]


def incidence_inverse(B):
    e = len(B)
    n = len(B[0]) if e else 0
    # Connected components are determined independently from nonzero incidence.
    adjacency = [set() for _ in range(n)]
    for row in B:
        verts = [i for i, value in enumerate(row) if value]
        for i in verts:
            adjacency[i].update(verts)
    remaining = set(range(n))
    components = []
    while remaining:
        pending = [min(remaining)]
        found = set()
        while pending:
            vertex = pending.pop()
            if vertex in found:
                continue
            found.add(vertex)
            pending.extend(adjacency[vertex] - found)
        remaining -= found
        components.append(sorted(found))
    result = [[Fraction(0) for _ in range(e)] for _ in range(n)]
    for group in components:
        size = len(group)
        L = [
            [sum(Fraction(B[edge][i]) * B[edge][j] for edge in range(e)) for j in group]
            for i in group
        ]
        shift = Fraction(1, size)
        A = inverse([[value + shift for value in row] for row in L])
        plus = [[value - shift for value in row] for row in A]
        for row, vertex in enumerate(group):
            for edge in range(e):
                result[vertex][edge] = sum(
                    plus[row][col] * B[edge][other] for col, other in enumerate(group)
                )
    return result, components


def decimal(value):
    return Decimal.from_float(float(value))


def exact_squared_distances(point, candidates):
    """Exact dyadic distances of the incoming binary64 coordinates."""
    return [
        sum(
            (Fraction.from_float(float(a)) - Fraction.from_float(float(b))) ** 2
            for a, b in zip(point, candidate, strict=True)
        )
        for candidate in candidates
    ]


def fraction_rows(values):
    return [[value.numerator, value.denominator] for value in values]


def mesh_oracle(raw, precision):
    mesh = raw["mesh"]
    n = len(mesh["tri_verts"])
    selected = set(raw["selection"]["cells"])
    surviving = [i for i in range(n) if i not in selected]
    removed_faces = sorted(
        {face for vertex in selected for face in mesh["_tverts_to_tcell"][vertex]}
    )
    removed_edges = sorted(
        {edge for vertex in selected for edge in mesh["tverts_to_tedges"][vertex]}
    )
    edge_survivors = [i for i in range(len(mesh["tri_edges"])) if i not in removed_edges]
    face_survivors = [i for i in range(len(mesh["tri_cells"])) if i not in removed_faces]
    points = [mesh["tri_verts"][i] for i in surviving]
    query_audit = []

    def nearest(point):
        if not points:
            raise ValueError("No surviving vertex for source KDTree lookup")
        distances = [
            sum((decimal(a) - decimal(b)) ** 2 for a, b in zip(point, candidate, strict=True))
            for candidate in points
        ]
        minimum = min(distances)
        ids = [i for i, value in enumerate(distances) if value == minimum]
        exact_distances = exact_squared_distances(point, points)
        exact_minimum = min(exact_distances)
        exact_minimizers = [i for i, value in enumerate(exact_distances) if value == exact_minimum]
        if ids != exact_minimizers:
            raise ValueError(
                "Decimal nearest minimizers differ from exact binary64-coordinate distances"
            )
        query_audit.append(
            dict(
                point_binary64_hex=[float(value).hex() for value in point],
                rounded_squared_distances=[str(value) for value in distances],
                exact_squared_distances=fraction_rows(exact_distances),
                minimizers=ids,
                exact_minimizers=exact_minimizers,
            )
        )
        if len(ids) != 1:
            raise ValueError("Source-conditional nearest tie has no unique independent index")
        return ids[0]

    faces = [[nearest(point) for point in mesh["tcell_verts"][i]] for i in face_survivors]
    edges = [[nearest(mesh["tri_verts"][v]) for v in mesh["tri_edges"][i]] for i in edge_survivors]
    # Source create_mappings matches the exact directed edge only, preserving
    # missing reverse-oriented face edges rather than silently repairing them.
    face_to_edges = []
    vert_edges = [[] for _ in points]
    for face in faces:
        found = []
        for left, right in zip(face, face[1:] + face[:1], strict=True):
            exact = [i for i, edge in enumerate(edges) if edge == [left, right]]
            if exact:
                index = exact[0]
                found.append(index)
                vert_edges[left].append(index)
                vert_edges[right].append(index)
        face_to_edges.append(found)
    edge_faces = [[] for _ in edges]
    for face, row in enumerate(face_to_edges):
        for edge in row:
            edge_faces[edge].append(face)
    B = [[0 for _ in points] for _ in edges]
    for index, (left, right) in enumerate(edges):
        B[index][right] = 1
        B[index][left] = -1
    pinv, components = incidence_inverse(B)
    return dict(
        survivor_vertex_indices=surviving,
        removed_face_indices=removed_faces,
        removed_edge_indices=removed_edges,
        source_return_is_removed_edges=True,
        tri_cells=faces,
        tri_edges=edges,
        tcell_to_tedges=face_to_edges,
        tverts_to_tedges=vert_edges,
        tedges_to_tcell=edge_faces,
        delta_tri_0=B,
        exact_pseudoinverse=[
            [[value.numerator, value.denominator] for value in row] for row in pinv
        ],
        pseudoinverse_binary64=[[float(value) for value in row] for row in pinv],
        components=components,
        nearest_audit=query_audit,
        hanging_vertex_indices=[
            i for i in range(len(points)) if not any(i in face for face in faces)
        ],
        empty_native_target_dtype_risk=not bool(removed_faces),
        stale_auxiliary_not_rebuilt=True,
        physical_mesh_admitted=False,
    )


def contact_oracle(raw, precision):
    # Raw is the archived actual incoming cells and parameter state at the
    # mem_processing call, not an outgoing contact or a complete trajectory.
    cells, p = raw["cells"], raw["parameters"]
    mids = cells["mem_mids_flat"]
    normals = [row[2:4] for row in cells["mem_vects_flat"]]
    # Include actual source binary64 scalar operation order for threshold input;
    # all distances/dot products remain independently evaluated in Decimal.
    threshold = decimal(3.0 * (1.0 - p["scale_cell"]) * p["cell_radius"])
    neighbors = []
    nearest = []
    boundary = []
    audit = []
    for i, point in enumerate(mids):
        d2 = [
            sum((decimal(a) - decimal(b)) ** 2 for a, b in zip(point, other, strict=True))
            for other in mids
        ]
        candidates = [j for j, value in enumerate(d2) if value <= threshold**2]
        exact_distances = exact_squared_distances(point, mids)
        exact_threshold = Fraction(threshold) ** 2
        exact_candidates = [
            j for j, value in enumerate(exact_distances) if value <= exact_threshold
        ]
        if candidates != exact_candidates:
            raise ValueError("Decimal candidates differ from exact binary64-coordinate threshold")
        neighbors.append(candidates)
        if len(candidates) == 1:
            pair = [i, i]
            boundary.append(i)
        elif len(candidates) == 2:
            pair = list(candidates)
        else:
            pair = []
            for j in candidates:
                dot = sum(
                    decimal(a) * decimal(b) for a, b in zip(normals[i], normals[j], strict=True)
                )
                # Only fixtures separated from round-half boundaries receive
                # exact discrete credit. Preserve source overwrite-on-each-j.
                pair = [i, j] if round(dot, 1) == Decimal("-1.0") else [i, i]
        nearest.append(pair)
        audit.append(
            dict(
                membrane=i,
                rounded_squared_distances=[str(value) for value in d2],
                exact_squared_distances=fraction_rows(exact_distances),
                candidates=candidates,
                exact_candidates=exact_candidates,
                exact_threshold_squared=[exact_threshold.numerator, exact_threshold.denominator],
            )
        )
    partners = []
    owner_pairs = []
    for i, pair in enumerate(nearest):
        if len(pair) != 2:
            raise ValueError("Source empty nearest pair; partial oracle retained by caller")
        left, right = pair
        if left == right:
            partner = i
        elif i == left:
            partner = right
        elif i == right:
            partner = left
        else:
            continue
        partners.append(partner)
        owner_pairs.append([cells["mem_to_cells"][i], cells["mem_to_cells"][partner]])
    return dict(
        mem_nn=nearest,
        nn_i=partners,
        cell_nn_i=owner_pairs,
        bflags_mems=boundary,
        incoming_query_audit=audit,
        actual_source_threshold_binary64_hex=float(threshold).hex(),
        source_last_candidate_overwrite_preserved=True,
        independent_carried_trajectory=False,
        physical_mesh_admitted=False,
    )


def evaluate(request):
    precision = request["precision"]
    if precision not in (80, 140):
        raise ValueError("Only declared precision pair")
    raw = decode_graph(request["input_graph"])
    with localcontext() as context:
        context.prec = precision
        if request["mode"] == "mesh":
            result = mesh_oracle(raw, precision)
        elif request["mode"] == "contact":
            result = contact_oracle(raw, precision)
        else:
            raise ValueError("Unknown independent conditional oracle")
    return dict(
        kind="cells.post_cut_independent_conditional_form@1",
        precision=precision,
        result=result,
        runtime=dict(
            pid=os.getpid(),
            ppid=os.getppid(),
            executable=sys.executable,
            isolated=sys.flags.isolated,
            no_site=sys.flags.no_site,
        ),
        scientific_modules_loaded=[
            name
            for name in sys.modules
            if name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "pytest"}
        ],
    )


def failed_reference(error):
    def exact(value):
        if isinstance(value, Decimal):
            return dict(decimal=str(value))
        if isinstance(value, Fraction):
            return dict(numerator=value.numerator, denominator=value.denominator)
        if type(value) is float:
            return dict(binary64_hex=value.hex())
        if isinstance(value, dict):
            return {str(key): exact(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [exact(item) for item in value]
        if value is None or type(value) in (str, bool, int):
            return value
        return dict(available_python_type=type(value).__name__)

    frames = []
    frame = error.__traceback__
    while frame is not None:
        name = frame.tb_frame.f_code.co_name
        if name in {
            "evaluate",
            "mesh_oracle",
            "contact_oracle",
            "nearest",
            "inverse",
            "incidence_inverse",
            "exact_squared_distances",
        }:
            frames.append(dict(function=name, available_locals=exact(frame.tb_frame.f_locals)))
        frame = frame.tb_next
    return dict(
        kind="cells.failed_independent_post_cut_form@1",
        error_type=type(error).__name__,
        reason=str(error),
        available_frames=frames,
    )


if __name__ == "__main__":
    text = sys.stdin.read(16 * 2**20 + 1)
    if len(text.encode()) > 16 * 2**20:
        raise ValueError("Bounded input exceeded")
    try:
        result = evaluate(json.loads(text))
    except Exception as error:
        json.dump(failed_reference(error), sys.stdout, sort_keys=True, allow_nan=False)
        raise
    json.dump(result, sys.stdout, sort_keys=True, allow_nan=False)
