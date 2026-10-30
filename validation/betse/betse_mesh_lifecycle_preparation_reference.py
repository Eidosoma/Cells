"""Independent bounded Decimal/Fraction lifecycle algebra on supplied topology."""

from decimal import Decimal, localcontext
from fractions import Fraction

MAX_NODES = 32
DEFAULT_RCOND = Decimal("1e-15")
RANK_MARGIN = Decimal(1000)


class ReferenceFailure(ValueError):
    def __init__(self, error, trial):
        super().__init__("Lifecycle reference failed: " + str(error))
        self.trial = trial


def d(value):
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, Fraction):
        result = Decimal(value.numerator) / Decimal(value.denominator)
    else:
        result = Decimal.from_float(float(value))
    if not result.is_finite():
        raise ValueError("Independent algebra requires finite input coefficients")
    return result


def serial(value):
    if isinstance(value, Decimal):
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return dict(kind="retained_decimal_outside_float64", value=str(value))
        return number
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {key: serial(v) for key, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


def matrix(values):
    if not values or not values[0] or any(len(row) != len(values[0]) for row in values):
        raise ValueError("Independent matrix domain requires nonempty rectangular arrays")
    return [[d(v) for v in row] for row in values]


def transpose(a):
    return [list(row) for row in zip(*a, strict=True)]


def zeros(m, n):
    return [[Decimal(0) for _ in range(n)] for _ in range(m)]


def eye(n):
    return [[Decimal(i == j) for j in range(n)] for i in range(n)]


def mul(a, b):
    if len(a[0]) != len(b):
        raise ValueError("Independent matrix dimensions differ")
    bt = transpose(b)
    return [
        [sum((x * y for x, y in zip(row, col, strict=True)), Decimal(0)) for col in bt] for row in a
    ]


def sub(a, b):
    return [[x - y for x, y in zip(row, col, strict=True)] for row, col in zip(a, b, strict=True)]


def add(a, b):
    return [[x + y for x, y in zip(row, col, strict=True)] for row, col in zip(a, b, strict=True)]


def scaled(a, value):
    return [[value * x for x in row] for row in a]


def inverse(a):
    n = len(a)
    if n > MAX_NODES or len(a[0]) != n:
        raise ValueError("Independent inverse requires a bounded square matrix")
    rows = [list(row) + e for row, e in zip(a, eye(n), strict=True)]
    for j in range(n):
        pivot = max(range(j, n), key=lambda i: abs(rows[i][j]))
        if rows[pivot][j] == 0:
            raise ValueError("Singular independent inverse")
        rows[j], rows[pivot] = rows[pivot], rows[j]
        scale = rows[j][j]
        rows[j] = [v / scale for v in rows[j]]
        for i in range(n):
            if i != j:
                factor = rows[i][j]
                rows[i] = [v - factor * w for v, w in zip(rows[i], rows[j], strict=True)]
    return [row[n:] for row in rows]


def exact_rank(a):
    rows = [[Fraction(v) for v in row] for row in a]
    rank = 0
    for j in range(len(rows[0])):
        pivot = next((i for i in range(rank, len(rows)) if rows[i][j]), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        p = rows[rank][j]
        rows[rank] = [v / p for v in rows[rank]]
        for i in range(rank + 1, len(rows)):
            factor = rows[i][j]
            rows[i] = [v - factor * w for v, w in zip(rows[i], rows[rank], strict=True)]
        rank += 1
        if rank == len(rows):
            break
    return rank


def norm_one(a):
    return max(sum(abs(v) for v in col) for col in transpose(a))


def norm_inf(a):
    return max(sum(abs(v) for v in row) for row in a)


def graph_pinv(a):
    """Gauge-fixed graph Laplacian solve, independent of SVD implementation."""
    n = len(a[0])
    if n > MAX_NODES:
        return None
    groups = [{i} for i in range(n)]
    anchors = set()
    degrees = [0] * n
    for row in a:
        indices = [i for i, v in enumerate(row) if v]
        if any(v not in (-1, 0, 1) for v in row) or len(indices) > 2:
            return None
        if len(indices) == 2:
            i, j = indices
            if row[i] + row[j] != 0:
                return None
            first = next(g for g in groups if i in g)
            second = next(g for g in groups if j in g)
            if first is not second:
                groups.remove(second)
                first.update(second)
        elif len(indices) == 1:
            anchors.add(indices[0])
        for i in indices:
            degrees[i] += 1
    p = zeros(n, n)
    unanchored = 0
    for group in groups:
        if not group & anchors:
            unanchored += 1
            for i in group:
                for j in group:
                    p[i][j] = Decimal(1) / len(group)
    at = transpose(a)
    laplacian = mul(at, a)
    expected = mul(inverse(add(laplacian, p)), at)
    # A conservative unweighted grounded-incidence separation. Nonzero
    # singular values are bounded away from NumPy's declared1e-15 cutoff.
    gap = Decimal(1) / (Decimal(n + 1) * Decimal(max(1, 2 * max(degrees))).sqrt())
    return dict(
        supported=True,
        method="gauge_fixed_grounded_incidence",
        expected=expected,
        exact_rank=n - unanchored,
        components=[sorted(g) for g in groups],
        anchored_components=sum(bool(g & anchors) for g in groups),
        conservative_nonzero_relative_gap=gap,
        default_rcond=DEFAULT_RCOND,
        rank_gap_resolved=gap > RANK_MARGIN * DEFAULT_RCOND,
    )


def pinv_reference(a):
    m, n = len(a), len(a[0])
    if max(m, n) > 4 * MAX_NODES:
        raise ValueError("Independent pseudoinverse exceeds declared dimension bound")
    if all(v == a[0][0] for row in a for v in row):
        c = a[0][0]
        return dict(
            supported=True,
            method="exact_constant_rank_one_or_zero",
            expected=[
                [Decimal(0) if c == 0 else Decimal(1) / (c * m * n) for _ in range(m)]
                for _ in range(n)
            ],
            exact_rank=0 if c == 0 else 1,
            rank_gap_resolved=True,
        )
    result = graph_pinv(a)
    if result is not None:
        return result
    result = graph_pinv(transpose(a))
    if result is not None:
        return dict(
            result, method="transposed_" + result["method"], expected=transpose(result["expected"])
        )
    rank = exact_rank(a)
    if m == n and n <= MAX_NODES and rank == n:
        inv = inverse(a)
        gap = Decimal(1) / (norm_one(a) * norm_inf(a) * norm_one(inv) * norm_inf(inv)).sqrt()
        return dict(
            supported=True,
            method="independent_full_rank_inverse",
            expected=inv,
            exact_rank=rank,
            conservative_nonzero_relative_gap=gap,
            default_rcond=DEFAULT_RCOND,
            rank_gap_resolved=gap > RANK_MARGIN * DEFAULT_RCOND,
        )
    return dict(
        supported=False,
        exact_rank=rank,
        method="retained_unsupported_rank_domain",
        rank_gap_resolved=False,
        reason="No independent truncated-SVD target claimed",
    )


def mp_identities(a, ap):
    aap, apa = mul(a, ap), mul(ap, a)
    return dict(
        A_Aplus_A=dict(actual=mul(a, apa), expected=a),
        Aplus_A_Aplus=dict(actual=mul(ap, aap), expected=ap),
        A_Aplus_symmetric=dict(actual=aap, expected=transpose(aap)),
        Aplus_A_symmetric=dict(actual=apa, expected=transpose(apa)),
    )


def incidence(edges, n):
    result = zeros(len(edges), n)
    for i, (u, v) in enumerate(edges):
        result[i][v] = Decimal(1)
        result[i][u] = Decimal(-1)
    return result


def face_incidence(cells, edges, *, reverse=False):
    result = zeros(len(cells), len(edges))
    ambiguous = []
    for i, cell in enumerate(cells):
        for j, u in enumerate(cell):
            v = cell[(j - 1 if reverse else j + 1) % len(cell)]
            forward = [k for k, edge in enumerate(edges) if list(edge) == [u, v]]
            backward = [k for k, edge in enumerate(edges) if list(edge) == [v, u]]
            chosen = (
                forward
                if forward and not backward
                else backward
                if backward and not forward
                else []
            )
            if len(chosen) > 1:
                ambiguous.append(dict(row=i, pair=[u, v], candidate_indices=chosen))
            elif chosen:
                result[i][chosen[0]] = Decimal(1 if forward else -1)
    return dict(
        expected=result,
        unique_matches=not ambiguous,
        ambiguities=ambiguous,
        topology_is_input=True,
        canonical_tie_index_claim=False,
    )


def smoothing(cache, params, frame):
    areas = [Fraction.from_float(float(v)) for v in cache["vor_sa"]]
    dual = [Fraction.from_float(float(v)) for v in cache["vor_edge_len"]]
    primal = [Fraction.from_float(float(v)) for v in cache["tri_edge_len"]]
    delta = [[Fraction.from_float(float(v)) for v in row] for row in cache["delta_tri_0"]]
    n = len(areas)
    h = Fraction.from_float(float(params["stepsize"]))
    # Exact rational assembly avoids a second floating reduction while keeping
    # every captured geometric metric an explicitly supplied input.
    ll = [
        [
            sum(
                (
                    -delta[k][i] * (dual[k] / primal[k]) * delta[k][j] / areas[i]
                    for k in range(len(delta))
                ),
                Fraction(0),
            )
            for j in range(n)
        ]
        for i in range(n)
    ]
    expected_mm = [[d(Fraction(int(i == j)) - h * ll[i][j]) for j in range(n)] for i in range(n)]
    target = pinv_reference(expected_mm)
    report = dict(
        expected_MM=expected_mm,
        source_MM=frame["MM"],
        semantic_inverse=target,
        source_metric_geometry_qualified=False,
    )
    if target["supported"] and target["rank_gap_resolved"]:
        expected_points = mul(target["expected"], matrix(cache["tri_verts"]))
        report["expected_full_step_points_m"] = expected_points
    return report


def evaluate(events, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require independent Decimal100/160 refinement")
    report = dict(
        pinv=[],
        dots=[],
        operators=[],
        quality=[],
        energy=[],
        smoothing=[],
        moves=[],
        source_topology_is_input=True,
        independent_topology_generation=False,
        topology_qualified=False,
        physical_geometry_admitted=False,
        upstream_initial_qualification="19/22 accuracy qualification open",
    )
    try:
        with localcontext() as context:
            context.prec = 100 if refinement == 1 else 160
            report["precision"] = context.prec
            stack = []
            active = not any(e["kind"] == "lifecycle_continuation_start" for e in events)
            pending_move = None
            for event in events:
                report["last_event_sequence"] = event["sequence"]
                kind, name, payload = event["kind"], event["method"], event["payload"]
                if kind == "lifecycle_continuation_start":
                    active = True
                    stack = []
                    continue
                if not active:
                    continue
                if kind == "method_enter":
                    stack.append(
                        dict(
                            name=name, params=payload["call_parameters"], cache=payload.get("cache")
                        )
                    )
                elif kind in ("method_return", "method_failure"):
                    entry = stack.pop()
                    if entry["name"] != name:
                        raise ValueError("Unbalanced lifecycle method trace")
                    if kind == "method_return" and name == "mesh_quality_calc":
                        c = entry["cache"]
                        expected = [
                            sum(((d(x) - d(y)) ** 2 for x, y in zip(a, b, strict=True)), Decimal(0))
                            for a, b in zip(c["tri_ccents"], c["tri_cents"], strict=True)
                        ]
                        report["quality"].append(
                            dict(
                                sequence=event["sequence"],
                                actual=payload["result"],
                                expected=expected,
                                units="m2",
                            )
                        )
                    elif kind == "method_return" and name == "create_core_operators":
                        c = entry["cache"]
                        report["operators"].append(
                            dict(
                                sequence=event["sequence"],
                                field="delta_tri_0",
                                actual=payload["cache"]["delta_tri_0"],
                                expected=incidence(c["tri_edges"], c["n_tverts"]),
                                exact_topological_entries=True,
                            )
                        )
                    elif kind == "method_return" and name == "create_aux_operators":
                        c = entry["cache"]
                        tri = face_incidence(c["tri_cells"], c["tri_edges"])
                        vor = face_incidence(
                            [c["vor_cells"][i] for i in c["inner_tvert_i"]],
                            c["vor_edges"],
                            reverse=True,
                        )
                        for field, target in (
                            ("delta_tri_1", tri),
                            (
                                "delta_vor_0",
                                dict(
                                    expected=incidence(c["vor_edges"], c["n_vverts"]),
                                    unique_matches=True,
                                ),
                            ),
                            ("delta_vor_1", vor),
                        ):
                            report["operators"].append(
                                dict(
                                    sequence=event["sequence"],
                                    field=field,
                                    actual=payload["cache"][field],
                                    expected=target["expected"],
                                    exact_topological_entries=target["unique_matches"],
                                    ambiguities=target.get("ambiguities", []),
                                )
                            )
                elif kind == "pinv_output":
                    a, ap = matrix(payload["matrix"]), matrix(payload["result"])
                    report["pinv"].append(
                        dict(
                            sequence=event["sequence"],
                            label=payload["label"],
                            actual=payload["result"],
                            target=pinv_reference(a),
                            identities=mp_identities(a, ap),
                        )
                    )
                elif kind == "dot_output":
                    vector = not isinstance(payload["right"][0], list)
                    b = [[d(v)] for v in payload["right"]] if vector else matrix(payload["right"])
                    expected = mul(matrix(payload["left"]), b)
                    if vector:
                        expected = [row[0] for row in expected]
                    report["dots"].append(
                        dict(
                            sequence=event["sequence"],
                            label=payload["label"],
                            actual=payload["result"],
                            expected=expected,
                            units="m"
                            if vector
                            else "dimensionless"
                            if payload["label"] == "term2"
                            else "m-2",
                            independent_accuracy_claim=vector or payload["label"] == "term2",
                        )
                    )
                elif (
                    kind == "lifecycle_return_locals"
                    and name == "laplacian_smoothing"
                    and payload["locals"]["stepsize"] is not None
                ):
                    entry = next(e for e in reversed(stack) if e["name"] == name)
                    value = smoothing(entry["cache"], entry["params"], payload["locals"])
                    value.update(
                        sequence=event["sequence"],
                        source_points_after_m=payload["cache"]["tri_verts"],
                    )
                    report["smoothing"].append(value)
                elif (
                    kind
                    in (
                        "refinement_iteration_start",
                        "refinement_iteration_end",
                        "lifecycle_return_locals",
                    )
                    and name == "refine_mesh"
                ):
                    frame = payload["locals"]
                    if "ui" in frame:
                        radius = d(payload["cache"]["cell_radius"])
                        expected = sum((d(v) for v in frame["ui"]), Decimal(0)) / radius**2
                        report["energy"].append(
                            dict(
                                sequence=event["sequence"],
                                actual=frame["UU"],
                                expected=expected,
                                source_would_update=d(frame["UU"]) > d(frame["convergence"]),
                                independent_would_update=expected > d(frame["convergence"]),
                                independent_branch_decision_claim=False,
                            )
                        )
                elif kind == "coordinate_update_before":
                    pending_move = payload
                elif kind == "coordinate_update_after":
                    if pending_move is None:
                        raise ValueError("Missing coordinate-update input")
                    if payload["policy"] in ("inner", "all"):
                        expected = [list(row) for row in pending_move["points"]]
                        indices = (
                            range(len(expected))
                            if payload["policy"] == "all"
                            else pending_move["indices"]
                        )
                        for i in indices:
                            expected[i] = list(pending_move["vor_cents"][i])
                        report["moves"].append(
                            dict(
                                sequence=event["sequence"],
                                policy=payload["policy"],
                                actual=payload["points"],
                                expected=expected,
                                exact_coordinate_copy=True,
                                point_ids_before=pending_move["point_ids"],
                                point_ids_after=payload["point_ids"],
                            )
                        )
                    pending_move = None
            if stack:
                raise ValueError("Unclosed lifecycle method trace")
            report["status"] = "independent_algebra_complete"
            return serial(report)
    except Exception as error:
        report.update(
            status="retained_reference_failure",
            failure=dict(type=type(error).__name__, message=str(error)),
        )
        raise ReferenceFailure(error, serial(report)) from error
