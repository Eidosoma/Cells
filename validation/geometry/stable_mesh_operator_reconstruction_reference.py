"""Independent integer-bordered solve and exact graph/cache checks.

Targets use only the declared original edge axes and incoming metric stores.
Production operator values never select targets, ranks or rounding budgets.
"""

import argparse
import hashlib
import importlib.abc
import json
import math
import os
import sys
import traceback
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

from validation.geometry import stable_geometry_primitives_reference as primitive_reference

LAW = "cells_stable_primal_graph_exact_mp_source_factorization@1"
BASELINE_BINDING = {
    "case": "caller-square-zero",
    "kind": "cells.operator_reviewed_square_metric_parent@1",
    "metric03_companion_manifest_sha256": (
        "9b6bc90a7ff788e8ee8615a755128c2f71014c0fc916233037caebb1a7e944df"
    ),
    "metric03_manifest_sha256": "39c7dae39a44409cd83cf352d60f98ae5a96133537b51549296d611ff66522f9",
    "metric_payload_sha256": "d0d5bc61fa436ab7a5c8059c9fd86c143748523f01102781a535e2cab60326fe",
    "original_cache_sha256": "fd15567d2440bb582a04d1994f4503d7857bbb6b8786fbf3fca50ea47d00c8f9",
    "probe_result_sha256": "8837bad80325d5c4290124f3bec0a06064905f88ad617c8ece75a19d79eedf0f",
    "probe_review_sha256": "4bff37c48e8701b07f7fb7bac773e1afb2d4c8fbd134a3d96dea0a942d47e185",
    "retained_point_ids_sha256": "59bba66a9495936e1807d631256a2308869df9b37fcdc446a38e8eb02eb32e1f",
    "source_evidence_sha256": "56ffadac715d8555a6a055975fbdf782d17f33b7d5b467f8b1f268dd3399fee3",
    "topology_payload_sha256": "f6ed747505c33d26a885508d38f386e3ce6a04e69ac198f5a3a3842240f74229",
}
METRIC_LAW = "cells_stable_corrected_topology_centroid_mesh_metrics@1"
GATES = dict.fromkeys(
    (
        "parent_qualification_inherited",
        "native_core_pseudoinverse_qualified",
        "native_cache_admitted",
        "weighted_laplacian_inverse_admitted",
        "physical_geometry_admitted",
        "ordinary_ECM_loop_ready",
    ),
    False,
)
INVALIDATED = [
    "all_original_native_incidence_inverse_and_graph_caches",
    "dual_and_auxiliary_incidence_inverse_caches",
    "curl_and_Cartesian_interpolation",
    "Dirichlet_injection_and_boundary_profiles",
    "actual_weighted_Laplacian_inverse",
    "physical_geom_weight_membrane_measures_and_volumes",
    "environment_operators_and_inverses",
    "native_seed_init_load_and_ordinary_loop_bindings",
]


def fraction(value):
    if type(value) is not dict or set(value) != {"numerator", "denominator"}:
        raise ValueError("Require a complete rational scalar")
    if any(type(value[key]) is not str for key in value):
        raise ValueError("Require literal rational numerator/denominator strings")
    result = Fraction(int(value["numerator"]), int(value["denominator"]))
    if (
        str(result.numerator) != value["numerator"]
        or str(result.denominator) != value["denominator"]
    ):
        raise ValueError("Noncanonical rational proof scalar")
    return result


def pack(value):
    if isinstance(value, Fraction):
        return dict(numerator=str(value.numerator), denominator=str(value.denominator))
    if isinstance(value, dict):
        return {key: pack(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [pack(child) for child in value]
    return value


def hex_record(value):
    if type(value) is float:
        return dict(binary64_hex=value.hex())
    if isinstance(value, dict):
        return {str(key): hex_record(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [hex_record(child) for child in value]
    return value


def digest(value):
    return hashlib.sha256(
        json.dumps(
            hex_record(pack(value)), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def grid(rows, cols=None):
    width = len(rows[0]) if rows else cols
    if width is None or any(len(row) != width for row in rows):
        raise ValueError("Independent complete matrix dimensions are required")
    return dict(rows=len(rows), cols=width, data=[[Fraction(x) for x in row] for row in rows])


def read_grid(value, rows, cols):
    if type(value) is not dict or set(value) != {"rows", "cols", "data"}:
        raise ValueError("Incomplete/extra exact matrix fields")
    if (
        type(value["rows"]) is not int
        or type(value["cols"]) is not int
        or (value["rows"], value["cols"]) != (rows, cols)
        or type(value["data"]) is not list
        or len(value["data"]) != rows
        or any(type(row) is not list or len(row) != cols for row in value["data"])
    ):
        raise ValueError("Exact matrix source-owner shape changed")
    return grid([[fraction(x) for x in row] for row in value["data"]], cols)


def zero(rows, cols):
    return grid([[0] * cols for _ in range(rows)], cols)


def trans(value):
    return grid(
        [[value["data"][i][j] for i in range(value["rows"])] for j in range(value["cols"])],
        value["rows"],
    )


def product(left, right):
    if left["cols"] != right["rows"]:
        raise ValueError("Independent matrix axes disagree")
    result = zero(left["rows"], right["cols"])
    for i, row in enumerate(left["data"]):
        for k, x in enumerate(row):
            if x:
                for j, y in enumerate(right["data"][k]):
                    result["data"][i][j] += x * y
    return result


def difference(left, right):
    if (left["rows"], left["cols"]) != (right["rows"], right["cols"]):
        raise ValueError("Independent residual axes disagree")
    return grid(
        [
            [x - y for x, y in zip(a, b, strict=True)]
            for a, b in zip(left["data"], right["data"], strict=True)
        ],
        left["cols"],
    )


def rowscale(value, scale):
    if len(scale) != value["rows"]:
        raise ValueError("Independent row-metric owner axis differs")
    return grid([[x * scale[i] for x in row] for i, row in enumerate(value["data"])], value["cols"])


def identity(size):
    return grid([[int(i == j) for j in range(size)] for i in range(size)], size)


def iszero(value):
    return all(x == 0 for row in value["data"] for x in row)


def rounded_hex(value):
    with localcontext() as context:
        context.prec = 4096
        approximation = Decimal(value.numerator) / Decimal(value.denominator)
        result = primitive_reference._rounded_ratio(pack(value), approximation)
    if result is None:
        raise ValueError("Independent rational cache target is unrepresentable in binary64")
    return result


def graph_axes(vertices, edges):
    parent = list(range(vertices))

    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i

    forest = []
    for index, (a, b) in enumerate(edges):
        x, y = root(a), root(b)
        if x != y:
            parent[y] = x
            forest.append(index)
    groups = {}
    for vertex in range(vertices):
        groups.setdefault(root(vertex), []).append(vertex)
    components = sorted(groups.values(), key=lambda row: row[0])
    omitted = {max(row) for row in components}
    pivots = [i for i in range(vertices) if i not in omitted]
    free = [i for i in range(len(edges)) if i not in forest]
    cycles = zero(len(edges), len(free))
    adjacency = [[] for _ in range(vertices)]
    for index in forest:
        a, b = edges[index]
        adjacency[a].append((b, index, 1))
        adjacency[b].append((a, index, -1))
    for column, edge in enumerate(free):
        a, b = edges[edge]
        frontier, predecessor = [b], {b: None}
        while frontier and a not in predecessor:
            node = frontier.pop(0)
            for other, index, sign in adjacency[node]:
                if other not in predecessor:
                    predecessor[other] = (node, index, sign)
                    frontier.append(other)
        if a not in predecessor:
            raise ValueError("Independent forest does not span an edge's owner component")
        cycles["data"][edge][column] = Fraction(1)
        node = a
        while node != b:
            previous, index, sign = predecessor[node]
            cycles["data"][index][column] = Fraction(sign)
            node = previous
    return components, pivots, forest, cycles


def bareiss_solve(integer_matrix, integer_rhs, partial, label):
    size = len(integer_matrix)
    if (
        size == 0
        or any(len(row) != size for row in integer_matrix)
        or len(integer_rhs) != size
        or any(type(x) is not int for row in integer_matrix + integer_rhs for x in row)
    ):
        raise ValueError("Independent bordered solve requires complete integer matrices")
    width = len(integer_rhs[0])
    if any(len(row) != width for row in integer_rhs):
        raise ValueError("Independent solve RHS owner axis differs")
    rows = [list(row) + list(rhs) for row, rhs in zip(integer_matrix, integer_rhs, strict=True)]
    state = dict(
        label=label, input_matrix=integer_matrix, input_rhs=integer_rhs, pivots=[], active=rows
    )
    partial.setdefault("bareiss_solves", []).append(state)
    previous = 1
    for column in range(size - 1):
        chosen = next((i for i in range(column, size) if rows[i][column]), None)
        if chosen is None:
            raise ValueError(
                "Singular bordered reference system; no damping or substituted inverse"
            )
        event = dict(
            column=column, chosen_row=chosen, previous_denominator=previous, before=deepcopy(rows)
        )
        state["pivots"].append(event)
        rows[column], rows[chosen] = rows[chosen], rows[column]
        pivot = rows[column][column]
        for i in range(column + 1, size):
            old = rows[i][column]
            for j in range(column + 1, size + width):
                numerator = rows[i][j] * pivot - old * rows[column][j]
                quotient, remainder = divmod(numerator, previous)
                if remainder:
                    raise ValueError("Independent fraction-free exact division failed")
                rows[i][j] = quotient
            rows[i][column] = 0
        previous = pivot
        event["after"] = deepcopy(rows)
    if rows[-1][size - 1] == 0:
        raise ValueError("Singular final bordered pivot")
    answer = [[Fraction(0)] * width for _ in range(size)]
    for i in range(size - 1, -1, -1):
        for column in range(width):
            rhs = Fraction(rows[i][size + column]) - sum(
                (Fraction(rows[i][j]) * answer[j][column] for j in range(i + 1, size)), Fraction(0)
            )
            answer[i][column] = rhs / rows[i][i]
    result = grid(answer, width)
    state["answer"] = result
    return result


def integer_inverse(value, partial, label):
    if any(x.denominator != 1 for row in value["data"] for x in row):
        raise ValueError("Independent source rank factors must be integer graph matrices")
    data = [[int(x) for x in row] for row in value["data"]]
    return bareiss_solve(
        data,
        [[int(i == j) for j in range(value["rows"])] for i in range(value["rows"])],
        partial,
        label,
    )


def verify_parent_baseline(request):
    """Authenticate reviewed input roles before independently deriving graph targets."""
    mreq, supplied = request["metric_request"], request["metric_candidate"]
    parent, corrected = mreq["topology_request"], mreq["topology_candidate"]
    payloads = dict(
        topology_payload={
            key: value
            for key, value in corrected.items()
            if key not in {"identity", "request_identity"}
        },
        metric_payload={
            key: value
            for key, value in supplied.items()
            if key not in {"identity", "request_identity", "topology_identity"}
        },
        original_cache=parent["original_cache"],
        retained_point_ids=parent["retained_point_ids"],
        source_evidence={
            key: value for key, value in parent["evidence"].items() if key != "original_record"
        },
    )
    if payloads["source_evidence"].get("case") != BASELINE_BINDING["case"] or any(
        digest(value) != BASELINE_BINDING[name + "_sha256"] for name, value in payloads.items()
    ):
        raise ValueError(
            "Independent original parent payload is outside the reviewed square baseline"
        )


def derive(request, partial):
    declaration = request["declaration"]
    expected_declaration = dict(
        kind="cells.stable_mesh_operator_reconstruction_declaration@1",
        opted_in_law=LAW,
        units=dict(
            incidence="1",
            incidence_pseudoinverse="1",
            edge_hodge="1",
            inverse_area="1/m2",
            area="m2",
            forward_laplacian="1/m2",
            source_factorized_map="m2",
        ),
        boundary_policy="primal_closed_graph_no_Dirichlet_injection",
        rank_policy="exact_unweighted_Moore_Penrose_no_cutoff",
        regularization=None,
        parent_status="explicit_reviewed_square_metric03_baseline_no_physical_qualification",
        parent_baseline=BASELINE_BINDING,
    )
    if declaration != expected_declaration:
        raise ValueError("Independent graph declaration/units/status is unsupported")
    if request["identity"] != digest(
        [LAW, request["metric_request"], request["metric_candidate"], declaration]
    ):
        raise ValueError("Changed original operator request")
    verify_parent_baseline(request)
    mreq, metric = request["metric_request"], request["metric_candidate"]
    if any(
        metric["prerequisites"][name] is not False
        for name in (
            "physical_geometry_admitted",
            "native_mesh_cache_admitted",
            "ordinary_ECM_loop_ready",
        )
    ):
        raise ValueError("Independent metric input may not promote parent qualification")
    corrected, cache = mreq["topology_candidate"], mreq["topology_request"]["original_cache"]
    edges, n = cache["tri_edges"], len(cache["tri_verts"])
    e = len(edges)
    if not 1 <= n <= 32 or not 1 <= e <= 96 or corrected["primal"]["edges"] != edges:
        raise ValueError("Independent complete bounded graph owner axes differ")
    d = zero(e, n)
    seen = set()
    for row, pair in enumerate(edges):
        if (
            len(pair) != 2
            or any(type(i) is not int or not 0 <= i < n for i in pair)
            or pair[0] == pair[1]
            or tuple(sorted(pair)) in seen
        ):
            raise ValueError("Ambiguous or invalid independent original primal edge")
        a, b = pair
        seen.add(tuple(sorted(pair)))
        d["data"][row][a], d["data"][row][b] = Fraction(-1), Fraction(1)
    if corrected["primal"]["delta_0"] != d["data"]:
        raise ValueError("Corrected D0 differs from actual original edge endpoints")
    d1 = zero(len(cache["tri_cells"]), e)
    face_keys, occurrences = set(), [[] for _ in edges]
    if not cache["tri_cells"]:
        raise ValueError("Missing original face owners")
    for face, ring in enumerate(cache["tri_cells"]):
        if (
            type(ring) is not list
            or len(ring) not in (3, 4)
            or len(set(ring)) != len(ring)
            or any(type(i) is not int or not 0 <= i < n for i in ring)
            or tuple(sorted(ring)) in face_keys
        ):
            raise ValueError("Ambiguous original face owner/vertex cycle")
        face_keys.add(tuple(sorted(ring)))
        for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
            hits = [
                (i, 1 if edge == [a, b] else -1)
                for i, edge in enumerate(edges)
                if set(edge) == {a, b}
            ]
            if len(hits) != 1:
                raise ValueError("Missing/ambiguous independent source face-edge owner")
            index, sign = hits[0]
            d1["data"][face][index] = Fraction(sign)
            occurrences[index].append((face, sign))
    if any(
        len(row) not in (1, 2) or len(row) == 2 and row[0][1] == row[1][1] for row in occurrences
    ) or any(not any(i in edge for edge in edges) for i in range(n)):
        raise ValueError("Unused or nonmanifold original graph owner")
    if corrected["primal"]["delta_1"] != d1["data"] or not iszero(product(d1, d)):
        raise ValueError("Independent exact primal chain/face owners disagree")
    connected, pivots, forest, cycles = graph_axes(n, edges)
    rank = n - len(connected)
    if rank != len(forest) or rank == 0:
        raise ValueError("Unresolved/nonpositive original graph rank")
    q = grid([[int(i in component) for component in connected] for i in range(n)])
    h = [[0] * n for _ in range(n)]
    for a, b in edges:
        h[a][a] += 1
        h[b][b] += 1
        h[a][b] -= 1
        h[b][a] -= 1
    count = len(connected)
    bordered = [row + [int(i in component) for component in connected] for i, row in enumerate(h)]
    bordered.extend(
        [[int(i in component) for i in range(n)] + [0] * count for component in connected]
    )
    rhs = [[int(d["data"][j][i]) for j in range(e)] for i in range(n)] + [
        [0] * e for _ in connected
    ]
    partial["stage"] = "independent_component_gauged_bordered_solve"
    solved = bareiss_solve(bordered, rhs, partial, "unweighted_incidence_pseudoinverse")
    pinv = grid(solved["data"][:n], e)
    partial["incidence_pseudoinverse"] = pinv
    native, coef = metric["native_roles"], metric["coefficients"]

    def positive_store(values, size, label):
        if (
            type(values) is not list
            or len(values) != size
            or any(type(x) is not float or not math.isfinite(x) or x <= 0 for x in values)
        ):
            raise ValueError("Invalid original metric input store: " + label)
        return [Fraction.from_float(x) for x in values]

    lp = positive_store(native["tri_edge_len"], e, "primal lengths")
    ld = positive_store(native["vor_edge_len"], e, "selected dual lengths")
    area = positive_store(native["vor_sa"], n, "unscaled dual area")
    w = positive_store(coef["native_stored_dual_over_primal"], e, "forward edge Hodge")
    r = positive_store(coef["native_stored_primal_over_dual"], e, "separate inverse edge Hodge")
    alpha = positive_store(coef["native_stored_inverse_dual_area"], n, "stored inverse area")
    for a, b, x, y in zip(lp, ld, w, r, strict=True):
        if rounded_hex(b / a) != float(x).hex() or rounded_hex(a / b) != float(y).hex():
            raise ValueError("Incoming metric ratios do not preserve source store division seams")
    if any(rounded_hex(1 / a) != float(b).hex() for a, b in zip(area, alpha, strict=True)):
        raise ValueError("Incoming metric inverse areas differ from the original source stores")
    partial["stage"] = "independent_source_graph_factors"
    l1 = grid([[w[i] * x for x in row] for i, row in enumerate(d["data"])])
    l2 = grid([[-alpha[i] * d["data"][j][i] for j in range(e)] for i in range(n)])
    i1 = grid([[pinv["data"][i][j] * r[j] for j in range(e)] for i in range(n)])
    i2 = grid([[-pinv["data"][j][i] * area[j] for j in range(n)] for i in range(e)])
    lap, stiffness = zero(n, n), zero(n, n)
    for index, (a, b) in enumerate(edges):
        weight = w[index]
        for owner, other in ((a, b), (b, a)):
            lap["data"][owner][owner] -= alpha[owner] * weight
            lap["data"][owner][other] += alpha[owner] * weight
            stiffness["data"][owner][owner] += weight
            stiffness["data"][owner][other] -= weight
    inverse = grid(
        [
            [
                -area[j]
                * sum(
                    (pinv["data"][i][k] * r[k] * pinv["data"][j][k] for k in range(e)), Fraction(0)
                )
                for j in range(n)
            ]
            for i in range(n)
        ]
    )
    matrices = dict(
        delta_tri_0=d,
        delta_tri_0_inv=pinv,
        L1=l1,
        L2=l2,
        L1_inv=i1,
        L2_inv=i2,
        lapGJ=lap,
        lapGJinv=inverse,
        stiffness=stiffness,
    )
    c = grid([[row[j] for j in pivots] for row in d["data"]])
    component_of = {i: component for component in connected for i in component}
    rr = grid(
        [
            [int(j == pivot) - int(j == max(component_of[pivot])) for j in range(n)]
            for pivot in pivots
        ]
    )
    gc, gr = product(trans(c), c), product(rr, trans(rr))
    gci = integer_inverse(gc, partial, "independent_column_gram_inverse")
    gri = integer_inverse(gr, partial, "independent_row_gram_inverse")
    effective = [1 / x for x in alpha]
    algebra = dict(
        rank=rank,
        pivot_columns=pivots,
        components=connected,
        column_factor=c,
        row_factor=rr,
        column_gram=gc,
        row_gram=gr,
        column_gram_inverse=gci,
        row_gram_inverse=gri,
        vertex_nullspace=q,
        edge_cycle_nullspace=cycles,
        forward_left_nullspace=rowscale(q, effective),
        factorized_inverse_right_nullspace=rowscale(q, [1 / x for x in area]),
        effective_mass=effective,
        source_area=area,
    )
    diagonals = dict(
        star_eij=dict(kind="diagonal", units="1", values=coef["native_stored_dual_over_primal"]),
        star_eij_inv=dict(
            kind="diagonal", units="1", values=coef["native_stored_primal_over_dual"]
        ),
        star_a=dict(kind="diagonal", units="1/m2", values=coef["native_stored_inverse_dual_area"]),
        star_a_inv=dict(kind="diagonal", units="m2", values=native["vor_sa"]),
    )
    partial["exact_targets"] = matrices
    return dict(
        n=n,
        e=e,
        rank=rank,
        components=connected,
        pivots=pivots,
        forest=forest,
        matrices=matrices,
        algebra=algebra,
        diagonals=diagonals,
        d1=d1,
        q=q,
        area=area,
        effective=effective,
        w=w,
        r=r,
        alpha=alpha,
    )


def typed_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            typed_equal(actual[key], child) for key, child in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            typed_equal(a, b) for a, b in zip(actual, expected, strict=True)
        )
    return actual == expected


def candidate_record(candidate):
    return [LAW] + [
        candidate[name]
        for name in (
            "request_identity",
            "owner_axes",
            "source_diagonals",
            "exact_matrices",
            "rounded_matrices",
            "algebra",
            "certificates",
            "diagnostics",
            "prerequisites",
        )
    ]


def expected_diagnostics(truth, stored):
    exact = truth["matrices"]
    lap, inverse, q = exact["lapGJ"], exact["lapGJinv"], truth["q"]
    area, effective = truth["area"], truth["effective"]
    left = rowscale(q, effective)
    right = rowscale(q, [1 / x for x in area])
    return dict(
        input_ratio_reciprocal_seam=[
            x * y - 1 for x, y in zip(truth["w"], truth["r"], strict=True)
        ],
        input_area_reciprocal_seam=[x * y - 1 for x, y in zip(area, truth["alpha"], strict=True)],
        primal_boundary_of_boundary=product(truth["d1"], exact["delta_tri_0"]),
        source_area_forward_conservation_defect=product(trans(q), rowscale(lap, area)),
        source_area_forward_adjoint_defect=difference(
            rowscale(lap, area), trans(rowscale(lap, area))
        ),
        forward_factorized_forward_defect=difference(product(product(lap, inverse), lap), lap),
        inverse_forward_inverse_defect=difference(product(product(inverse, lap), inverse), inverse),
        factorized_map_is_general_weighted_pseudoinverse_claimed=False,
        exact_forward_selfadjoint_mass="reciprocal_of_stored_inverse_area",
        exact_factorized_map_selfadjoint_mass="source_unscaled_area",
        rounded_cache_exact_nullspace_or_energy_claimed=False,
        native_BLAS_SVD_bytes_claimed=False,
        storage_errors={name: difference(stored[name], value) for name, value in exact.items()},
        rounded_forward_constant_defect=product(stored["lapGJ"], q),
        rounded_effective_mass_left_defect=product(trans(left), stored["lapGJ"]),
        rounded_source_area_forward_defect=product(trans(q), rowscale(stored["lapGJ"], area)),
        rounded_inverse_right_kernel_defect=product(stored["lapGJinv"], right),
        rounded_inverse_output_mean_defect=product(trans(q), stored["lapGJinv"]),
    )


def verify_pivots(events, truth):
    n, e, rank = truth["n"], truth["e"], truth["rank"]
    d, factors = truth["matrices"]["delta_tri_0"], truth["algebra"]

    def augmented(value):
        return grid([row + identity(rank)["data"][i] for i, row in enumerate(value["data"])])

    blocks = [
        ("D0_rref", d, truth["pivots"]),
        ("gramC_inverse", augmented(factors["column_gram"]), list(range(rank))),
        ("gramR_inverse", augmented(factors["row_gram"]), list(range(rank))),
        ("cycle_nullspace_rref", trans(d), truth["forest"]),
    ]
    if type(events) is not list or len(events) != 4 * rank:
        raise ValueError("Complete exact pivot journal must contain4*source-rank entries")
    offset = 0
    for label, initial, columns in blocks:
        state = deepcopy(initial)
        for step, column in enumerate(columns):
            event = events[offset]
            offset += 1
            if set(event) != {"label", "step", "column", "chosen_row", "before", "after"}:
                raise ValueError("Incomplete or extra exact pivot slots")
            before = read_grid(event["before"], state["rows"], state["cols"])
            chosen = next((i for i in range(step, state["rows"]) if state["data"][i][column]), None)
            if (
                event["label"] != label
                or type(event["step"]) is not int
                or event["step"] != step
                or type(event["column"]) is not int
                or event["column"] != column
                or type(event["chosen_row"]) is not int
                or event["chosen_row"] != chosen
                or before != state
                or chosen is None
            ):
                raise ValueError("Exact pivot input/order differs from source rank-factor axes")
            data = deepcopy(state["data"])
            data[step], data[chosen] = data[chosen], data[step]
            pivot = data[step][column]
            normalized = [x / pivot for x in data[step]]
            after = []
            for i, row in enumerate(data):
                after.append(
                    normalized
                    if i == step
                    else [x - row[column] * y for x, y in zip(row, normalized, strict=True)]
                )
            state = grid(after, state["cols"])
            if read_grid(event["after"], state["rows"], state["cols"]) != state:
                raise ValueError(
                    "Exact pivot returned values do not follow from its retained input"
                )
    if offset != 4 * rank or (n, e) != (d["cols"], d["rows"]):
        raise ValueError("Incomplete pivot event coverage")


def absolute(value):
    return grid([[abs(x) for x in row] for row in value["data"]], value["cols"])


def plus(left, right):
    return difference(left, rowscale(right, [-1] * right["rows"]))


def verify_candidate(request, candidate, truth, projections):
    checks, residuals, bounds_report = [], {}, {}

    def require(condition, label, detail=None):
        checks.append(dict(label=label, passed=bool(condition)))
        if not condition:
            if detail is not None:
                residuals[label] = detail
            raise ValueError("Independent graph candidate rejected: " + label)

    def zero_check(value, label):
        residuals[label] = (
            value
            if not iszero(value)
            else dict(rows=value["rows"], cols=value["cols"], all_zero=True)
        )
        require(iszero(value), label)

    def bounded(value, target, budget, label):
        delta = difference(value, target)
        valid = all(
            abs(x) <= b
            for row, brow in zip(delta["data"], budget["data"], strict=True)
            for x, b in zip(row, brow, strict=True)
        )
        bounds_report[label] = dict(
            actual=value,
            exact_target=target,
            error=delta,
            budget=budget,
            budget_basis="independent exact target rounding cells",
        )
        require(valid, label)

    try:
        require(
            type(candidate) is dict
            and set(candidate)
            == {
                "request_identity",
                "owner_axes",
                "source_diagonals",
                "exact_matrices",
                "rounded_matrices",
                "algebra",
                "certificates",
                "diagnostics",
                "prerequisites",
                "identity",
            },
            "complete_candidate_fields",
        )
        require(
            candidate["request_identity"] == request["identity"],
            "unchanged_original_request_identity",
        )
        require(
            candidate["identity"] == digest(candidate_record(candidate)), "complete_candidate_seal"
        )
        mreq = request["metric_request"]
        corrected = mreq["topology_candidate"]
        expected_axes = dict(
            primal_vertex_ids=mreq["topology_request"]["retained_point_ids"],
            primal_edges=corrected["primal"]["edges"],
            selected_dual_edges=corrected["dual"]["selected_edges"],
            metric_identity=request["metric_candidate"]["identity"],
            topology_identity=corrected["identity"],
        )
        require(
            typed_equal(candidate["owner_axes"], expected_axes), "immutable_original_owner_axes"
        )
        require(
            typed_equal(candidate["source_diagonals"], truth["diagonals"]),
            "exact_source_hodge_store_roles_and_units",
        )
        require(
            typed_equal(candidate["algebra"], pack(truth["algebra"])),
            "complete_exact_rank_factors_and_nullspaces",
        )
        expected_prerequisites = dict(
            **GATES,
            invalidated=INVALIDATED,
            independent_algebra_and_storage_checks_required=True,
            reconstructed_cache_fields=["delta_tri_0", "delta_tri_0_inv", "lapGJ", "lapGJinv"],
            physical_geom_weight=None,
            auxiliary_operators=None,
            Dirichlet_injection=None,
        )
        require(
            typed_equal(candidate["prerequisites"], expected_prerequisites),
            "closed_native_physical_and_auxiliary_gates",
        )
        matrices = truth["matrices"]
        require(
            set(candidate["exact_matrices"]) == set(matrices)
            and set(candidate["rounded_matrices"]) == set(matrices),
            "complete_matrix_role_inventory",
        )
        stored, budgets = {}, {}
        for name, expected in matrices.items():
            actual_exact = read_grid(
                candidate["exact_matrices"][name], expected["rows"], expected["cols"]
            )
            require(
                actual_exact == expected,
                "independent_exact_target/" + name,
                difference(actual_exact, expected),
            )
            actual = candidate["rounded_matrices"][name]
            require(
                type(actual) is list
                and len(actual) == expected["rows"]
                and all(type(row) is list and len(row) == expected["cols"] for row in actual),
                "complete_binary64_owner_axis/" + name,
            )
            values, cells = [], []
            for i, row in enumerate(actual):
                output, error_cells = [], []
                for j, value in enumerate(row):
                    require(
                        type(value) is float
                        and math.isfinite(value)
                        and value.hex() == projections[name][i][j],
                        "correct_rounding/" + name + "/" + str(i) + "/" + str(j),
                    )
                    expected_float = float.fromhex(projections[name][i][j])
                    budget = Fraction.from_float(math.ulp(expected_float)) / 2
                    output.append(Fraction.from_float(value))
                    error_cells.append(
                        abs(Fraction.from_float(expected_float) - expected["data"][i][j])
                    )
                    require(
                        abs(output[-1] - expected["data"][i][j]) <= budget,
                        "independent_rounding_cell/" + name + "/" + str(i) + "/" + str(j),
                    )
                values.append(output)
                cells.append(error_cells)
            stored[name], budgets[name] = (
                grid(values, expected["cols"]),
                grid(cells, expected["cols"]),
            )
        certs = candidate["certificates"]
        require(
            type(certs) is dict
            and set(certs) == {"matrix_event_indices", "arithmetic_events", "algebra_pivots"},
            "complete_certificate_group_inventory",
        )
        require(
            type(certs["matrix_event_indices"]) is dict
            and set(certs["matrix_event_indices"]) == set(matrices),
            "complete_scalar_slot_role_inventory",
        )
        expected_events = sum(value["rows"] * value["cols"] for value in matrices.values())
        events = certs["arithmetic_events"]
        require(
            type(events) is list and len(events) == expected_events,
            "source_owner_scalar_event_cardinality",
        )
        index = 0
        for name, target in matrices.items():
            slots = certs["matrix_event_indices"][name]
            require(
                type(slots) is list
                and len(slots) == target["rows"]
                and all(type(row) is list and len(row) == target["cols"] for row in slots),
                "complete_scalar_slots/" + name,
            )
            for i in range(target["rows"]):
                for j in range(target["cols"]):
                    event = events[index]
                    require(
                        type(slots[i][j]) is int
                        and slots[i][j] == index
                        and type(event) is dict
                        and set(event)
                        == {"sequence", "matrix", "row", "column", "input_exact", "returned"}
                        and type(event["sequence"]) is int
                        and event["sequence"] == index
                        and event["matrix"] == name
                        and type(event["row"]) is int
                        and event["row"] == i
                        and type(event["column"]) is int
                        and event["column"] == j,
                        "unique_source_scalar_slot/" + str(index),
                    )
                    require(
                        fraction(event["input_exact"]) == target["data"][i][j],
                        "scalar_input_is_independent_target/" + str(index),
                    )
                    returned = event["returned"]
                    require(
                        type(returned) is dict
                        and set(returned) == {"value", "binary64_hex", "certificate"}
                        and type(returned["value"]) is float
                        and returned["value"].hex()
                        == returned["binary64_hex"]
                        == projections[name][i][j]
                        and returned["value"].hex()
                        == candidate["rounded_matrices"][name][i][j].hex(),
                        "scalar_return_readout_binding/" + str(index),
                    )
                    certificate = returned["certificate"]
                    require(
                        type(certificate) is dict
                        and set(certificate) == {"kind", "exact", "event_index"}
                        and certificate["kind"] == "correctly_rounded_binary_rational"
                        and type(certificate["event_index"]) is int
                        and certificate["event_index"] == index
                        and fraction(certificate["exact"]) == target["data"][i][j],
                        "scalar_certificate_independent_target/" + str(index),
                    )
                    index += 1
        require(index == expected_events, "complete_unique_scalar_event_coverage")
        verify_pivots(certs["algebra_pivots"], truth)
        require(True, "complete_input_and_return_exact_pivot_journal")
        d, x = matrices["delta_tri_0"], matrices["delta_tri_0_inv"]
        dx, xd = product(d, x), product(x, d)
        zero_check(difference(product(dx, d), d), "Penrose_DXD_equals_D")
        zero_check(difference(product(xd, x), x), "Penrose_XDX_equals_X")
        zero_check(difference(dx, trans(dx)), "Penrose_DX_selfadjoint")
        zero_check(difference(xd, trans(xd)), "Penrose_XD_selfadjoint")
        q, alg = truth["q"], truth["algebra"]
        zero_check(product(d, q), "complete_vertex_component_kernel")
        zero_check(product(trans(d), alg["edge_cycle_nullspace"]), "complete_edge_cycle_kernel")
        zero_check(product(trans(q), x), "incidence_pseudoinverse_component_mean_gauge")
        zero_check(product(truth["d1"], d), "primal_boundary_of_boundary")
        lap, inverse = matrices["lapGJ"], matrices["lapGJinv"]
        zero_check(
            difference(product(matrices["L2"], matrices["L1"]), lap), "source_forward_factorization"
        )
        zero_check(
            difference(product(matrices["L1_inv"], matrices["L2_inv"]), inverse),
            "source_factorized_map_preserved",
        )
        zero_check(product(lap, q), "forward_constant_kernel")
        zero_check(
            product(trans(alg["forward_left_nullspace"]), lap), "effective_mass_conservation"
        )
        zero_check(
            difference(rowscale(lap, truth["effective"]), trans(rowscale(lap, truth["effective"]))),
            "effective_mass_forward_adjoint",
        )
        gram_forward = product(trans(d), rowscale(d, truth["w"]))
        zero_check(
            plus(rowscale(lap, truth["effective"]), gram_forward),
            "forward_negative_energy_gram_factor",
        )
        zero_check(
            product(inverse, alg["factorized_inverse_right_nullspace"]),
            "source_factorized_right_kernel",
        )
        zero_check(product(trans(q), inverse), "source_factorized_output_component_mean")
        zero_check(
            difference(rowscale(inverse, truth["area"]), trans(rowscale(inverse, truth["area"]))),
            "source_area_factorized_map_adjoint",
        )
        z = trans(rowscale(x, truth["area"]))
        gram_inverse = product(trans(z), rowscale(z, truth["r"]))
        zero_check(
            plus(rowscale(inverse, truth["area"]), gram_inverse),
            "factorized_map_negative_energy_gram_factor",
        )
        require(
            all(v > 0 for v in truth["w"] + truth["r"] + truth["area"] + truth["effective"]),
            "strict_metric_positivity_for_all_vector_energy_signs",
        )
        diagnostics = expected_diagnostics(truth, stored)
        require(
            typed_equal(candidate["diagnostics"], pack(diagnostics)),
            "complete_reported_defects_and_storage_errors",
        )
        rounded_l, rounded_k = stored["lapGJ"], stored["lapGJinv"]
        bl, bk = budgets["lapGJ"], budgets["lapGJinv"]
        zero_lq = zero(truth["n"], len(truth["components"]))
        zero_left = zero(len(truth["components"]), truth["n"])
        bounded(product(rounded_l, q), zero_lq, product(bl, q), "rounded_forward_constant_bound")
        left = alg["forward_left_nullspace"]
        bounded(
            product(trans(left), rounded_l),
            zero_left,
            product(trans(left), bl),
            "rounded_effective_mass_conservation_bound",
        )
        source_area_left = rowscale(q, truth["area"])
        bounded(
            product(trans(source_area_left), rounded_l),
            diagnostics["source_area_forward_conservation_defect"],
            product(trans(source_area_left), bl),
            "source_area_defect_preserved_with_independent_storage_bound",
        )
        right = alg["factorized_inverse_right_nullspace"]
        bounded(
            product(rounded_k, right),
            zero_lq,
            product(bk, right),
            "rounded_source_inverse_kernel_bound",
        )
        bounded(
            product(trans(q), rounded_k),
            zero_left,
            product(trans(q), bk),
            "rounded_source_inverse_mean_bound",
        )
        for actual, budget, mass, label in (
            (rounded_l, bl, truth["effective"], "rounded_forward_adjoint_bound"),
            (rounded_k, bk, truth["area"], "rounded_factorized_map_adjoint_bound"),
        ):
            weighted, cell = rowscale(actual, mass), rowscale(budget, mass)
            bounded(
                difference(weighted, trans(weighted)),
                zero(truth["n"], truth["n"]),
                plus(cell, trans(cell)),
                label,
            )
        xs, bx = stored["delta_tri_0_inv"], budgets["delta_tri_0_inv"]
        ad, ax = absolute(d), absolute(x)
        bounded(
            difference(product(product(d, xs), d), d),
            zero(d["rows"], d["cols"]),
            product(product(ad, bx), ad),
            "rounded_Penrose_DXD_bound",
        )
        triple_budget = plus(
            plus(product(product(bx, ad), ax), product(product(ax, ad), bx)),
            plus(product(product(bx, ad), bx), bx),
        )
        bounded(
            difference(product(product(xs, d), xs), xs),
            zero(x["rows"], x["cols"]),
            triple_budget,
            "rounded_Penrose_XDX_bound",
        )
        for value, cell, label in (
            (product(d, xs), product(ad, bx), "rounded_Penrose_DX_adjoint_bound"),
            (product(xs, d), product(bx, ad), "rounded_Penrose_XD_adjoint_bound"),
        ):
            bounded(
                difference(value, trans(value)),
                zero(value["rows"], value["cols"]),
                plus(cell, trans(cell)),
                label,
            )
        return dict(
            passed=True,
            checks=checks,
            exact_algebra_residuals=residuals,
            storage_error_bounds=bounds_report,
            numerical_tolerance_added=False,
            weighted_Laplacian_inverse_claimed=False,
            physical_geometry_admitted=False,
        )
    except Exception as error:
        return dict(
            passed=False,
            checks=checks,
            exact_algebra_residuals=residuals,
            storage_error_bounds=bounds_report,
            reason=str(error),
            type=type(error).__name__,
            traceback=traceback.format_exc(),
            numerical_tolerance_added=False,
            weighted_Laplacian_inverse_claimed=False,
            physical_geometry_admitted=False,
        )


def evaluate(payload):
    partial = dict(stage="input")
    try:
        truth = derive(payload["request"], partial)
        partial["stage"] = "independent_binary64_projections"
        projections = {
            name: [[rounded_hex(x) for x in row] for row in value["data"]]
            for name, value in truth["matrices"].items()
        }
        baseline = payload.get("baseline", payload["candidate"])
        baseline_report = verify_candidate(payload["request"], baseline, truth, projections)
        if not baseline_report["passed"]:
            return dict(
                status="baseline_failed",
                baseline_passed=False,
                candidate_passed=False,
                control_detected=False,
                baseline=baseline_report,
                reference=truth,
                reference_binary64_hex=projections,
                raw_partial=partial,
            )
        if "baseline" in payload:
            checked = verify_candidate(payload["request"], payload["candidate"], truth, projections)
            detected = checked["passed"] is False
        else:
            checked, detected = baseline_report, False
        return dict(
            status="complete",
            baseline_passed=True,
            candidate_passed=checked["passed"],
            control_detected=detected,
            baseline=baseline_report,
            candidate=checked,
            reference=truth,
            reference_binary64_hex=projections,
            reference_solve_journal=partial,
            physical_geometry_admitted=False,
            native_cache_admitted=False,
        )
    except Exception as error:
        return dict(
            status="reference_failed",
            baseline_passed=False,
            candidate_passed=False,
            control_detected=False,
            reason=str(error),
            traceback=traceback.format_exc(),
            raw_partial=partial,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    denied = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "PIL", "torch"}

    class DenyScience(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in denied:
                raise ImportError("Exact graph reference denies production/science: " + fullname)

    sys.meta_path.insert(0, DenyScience())
    if denied & {name.split(".")[0] for name in sys.modules}:
        raise RuntimeError("Scientific import reached independent graph reference")
    payload = json.loads(args.input.read_text())
    report = pack(evaluate(payload))
    report["runtime_origin"] = dict(
        pid=os.getpid(),
        parent_pid=os.getppid(),
        executable=sys.executable,
        source=str(Path(__file__).resolve()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
    )
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    passed = report["baseline_passed"] and (
        report["control_detected"] if "baseline" in payload else report["candidate_passed"]
    )
    if not passed:
        raise SystemExit(2 if report["status"] == "baseline_failed" else 1)


if __name__ == "__main__":
    main()
