"""Conditional primal graph caches from corrected topology and stored metrics.

The incidence pseudoinverse is exact and unweighted. Native lapGJinv remains
the source factorized map; no weighted inverse, regularization or physical
admission is inferred. Binary64 cache readouts are certified separately.
"""

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from fractions import Fraction
from pathlib import Path

from cells.processes import stable_geometry_primitives as arithmetic
from cells.processes import stable_mesh_metric_reconstruction as metrics
from cells.processes import stable_mesh_operator_reconstruction_algebra as algebra
from cells.processes import stable_mesh_physical_reconstruction as topology

LAW_ID = "cells_stable_primal_graph_exact_mp_source_factorization@1"
INPUT_KIND = "cells.stable_mesh_operator_reconstruction_declaration@1"
SOURCE_PINS = (
    (
        "stable_geometry_primitives",
        "c9fab4f34aa9166711431844f2af72eb6b8fe4873154bfe01dfce3f656326958",
    ),
    (
        "stable_mesh_metric_reconstruction",
        "81a93cc8cf93e0885712e4df8d09e82c0db37a564c14f0ca4af44fa51e08fe0f",
    ),
    (
        "stable_mesh_operator_reconstruction_algebra",
        "d2912bc06cf0459ceaa0149ef5f71c9b35c7339892d3293f49182ce4e2a2c49d",
    ),
    (
        "stable_mesh_physical_reconstruction",
        "b0633f93978dba2db684e23ee1e3e348c0f3edde624b3069c57b115e3d7ab582",
    ),
)
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
MAX_VERTICES = 32
MAX_EDGES = 96
MAX_SCALAR_OUTPUTS = 24576
UNITS = dict(
    incidence="1",
    incidence_pseudoinverse="1",
    edge_hodge="1",
    inverse_area="1/m2",
    area="m2",
    forward_laplacian="1/m2",
    source_factorized_map="m2",
)
GATE_NAMES = (
    "parent_qualification_inherited",
    "native_core_pseudoinverse_qualified",
    "native_cache_admitted",
    "weighted_laplacian_inverse_admitted",
    "physical_geometry_admitted",
    "ordinary_ECM_loop_ready",
)
INVALIDATED = (
    "all_original_native_incidence_inverse_and_graph_caches",
    "dual_and_auxiliary_incidence_inverse_caches",
    "curl_and_Cartesian_interpolation",
    "Dirichlet_injection_and_boundary_profiles",
    "actual_weighted_Laplacian_inverse",
    "physical_geom_weight_membrane_measures_and_volumes",
    "environment_operators_and_inverses",
    "native_seed_init_load_and_ordinary_loop_bindings",
)


@dataclass(frozen=True)
class Request:
    metric_request: metrics.Request
    metric_candidate: metrics.Candidate
    declaration: object
    identity: str


@dataclass(frozen=True)
class Candidate:
    request_identity: str
    owner_axes: object
    source_diagonals: object
    exact_matrices: object
    rounded_matrices: object
    algebra: object
    certificates: object
    diagnostics: object
    prerequisites: object
    identity: str


class OperatorRejected(ValueError):
    def __init__(self, reason, *, stage, original=None, partial=None):
        super().__init__("Primal graph operator candidate refused at " + stage + ": " + str(reason))
        self.stage, self.original, self.partial = stage, original, partial


def plain(value):
    if isinstance(value, Fraction):
        return dict(numerator=str(value.numerator), denominator=str(value.denominator))
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: plain(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(child) for child in value]
    return value


def digest(value):
    return topology.digest(plain(value))


def _verify_sources():
    for (name, expected), module in zip(
        SOURCE_PINS, (arithmetic, metrics, algebra, topology), strict=True
    ):
        if (
            module.__name__.rsplit(".", 1)[-1] != name
            or hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Changed frozen primal graph dependency: " + name)


def _declaration(value):
    if (
        not isinstance(value, Mapping)
        or set(value)
        != {
            "kind",
            "opted_in_law",
            "units",
            "boundary_policy",
            "rank_policy",
            "regularization",
            "parent_status",
            "parent_baseline",
        }
        or value["kind"] != INPUT_KIND
        or value["opted_in_law"] != LAW_ID
        or value["units"] != UNITS
        or value["boundary_policy"] != "primal_closed_graph_no_Dirichlet_injection"
        or value["rank_policy"] != "exact_unweighted_Moore_Penrose_no_cutoff"
        or value["regularization"] is not None
        or value["parent_status"]
        != "explicit_reviewed_square_metric03_baseline_no_physical_qualification"
        or value["parent_baseline"] != BASELINE_BINDING
    ):
        raise ValueError(
            "Declare the complete bounded graph law; no physical qualification or regularization"
        )
    return topology.freeze(plain(value))


def request_record(value):
    return (LAW_ID, value.metric_request, value.metric_candidate, value.declaration)


def parent_payloads(metric_request, metric_candidate):
    """Keep capture-context identities separate from complete reviewed source payloads."""
    parent = metric_request.topology_request
    corrected = plain(metric_request.topology_candidate)
    supplied = plain(metric_candidate)
    evidence = plain(parent.evidence)
    return dict(
        topology_payload={
            key: child
            for key, child in corrected.items()
            if key not in {"identity", "request_identity"}
        },
        metric_payload={
            key: child
            for key, child in supplied.items()
            if key not in {"identity", "request_identity", "topology_identity"}
        },
        original_cache=plain(parent.original_cache),
        retained_point_ids=plain(parent.retained_point_ids),
        source_evidence={key: child for key, child in evidence.items() if key != "original_record"},
    )


def _verify_parent_baseline(metric_request, metric_candidate):
    payloads = parent_payloads(metric_request, metric_candidate)
    if payloads["source_evidence"].get("case") != BASELINE_BINDING["case"] or any(
        digest(value) != BASELINE_BINDING[name + "_sha256"] for name, value in payloads.items()
    ):
        raise ValueError(
            "Original complete parent payload is outside the explicitly reviewed metric baseline"
        )


def bind(metric_request, metric_candidate, declaration):
    _verify_sources()
    declared = _declaration(declaration)
    if (
        type(metric_request) is not metrics.Request
        or type(metric_candidate) is not metrics.Candidate
    ):
        raise ValueError(
            "Require complete original metric request/candidate and corrected topology"
        )
    rebuilt = metrics.prepare(metric_request)
    if digest(rebuilt) != digest(metric_candidate):
        raise ValueError("Changed or resealed metric stores, owners or certificates")
    _verify_parent_baseline(metric_request, metric_candidate)
    corrected = metric_request.topology_candidate
    n, e = len(corrected.geometry["tri_verts"]), len(corrected.primal["edges"])
    if not 1 <= n <= MAX_VERTICES or not 1 <= e <= MAX_EDGES:
        raise ValueError("Outside the bounded32-vertex/96-edge exact graph layer")
    if any(
        metric_candidate.prerequisites[key] is not False
        for key in (
            "physical_geometry_admitted",
            "native_mesh_cache_admitted",
            "ordinary_ECM_loop_ready",
        )
    ):
        raise ValueError("The metric parent may not silently promote physical or native admission")
    result = Request(metric_request, metric_candidate, declared, "")
    return replace(result, identity=digest(request_record(result)))


def components(vertices, edges):
    unseen, result = set(range(vertices)), []
    while unseen:
        first = min(unseen)
        frontier, row = [first], []
        unseen.remove(first)
        while frontier:
            vertex = frontier.pop()
            row.append(vertex)
            for a, b in edges:
                other = b if a == vertex else a if b == vertex else None
                if other in unseen:
                    unseen.remove(other)
                    frontier.append(other)
        result.append(tuple(sorted(row)))
    return tuple(result)


def _weights(values, count, name):
    if len(values) != count or any(
        type(value) is not float or not math.isfinite(value) or value <= 0 for value in values
    ):
        raise ValueError("Incomplete/nonpositive native metric stores: " + name)
    return tuple(Fraction.from_float(value) for value in values)


class _Work:
    def __init__(self):
        self.pivots, self.scalars, self.partial = [], [], {}

    def round(self, target, name, row, column):
        event = dict(
            sequence=len(self.scalars),
            matrix=name,
            row=row,
            column=column,
            input_exact=plain(target),
        )
        self.scalars.append(event)
        try:
            value = arithmetic._round(target, "primal_graph_" + name)
        except Exception as error:
            event["failure"] = dict(
                type=type(error).__name__,
                reason=str(error),
                detail=plain(getattr(error, "detail", None)),
            )
            raise
        event["returned"] = dict(
            value=value,
            binary64_hex=value.hex(),
            certificate=dict(
                kind="correctly_rounded_binary_rational",
                exact=plain(target),
                event_index=event["sequence"],
            ),
        )
        return value, event["sequence"]


def candidate_record(value):
    return (
        LAW_ID,
        value.request_identity,
        value.owner_axes,
        value.source_diagonals,
        value.exact_matrices,
        value.rounded_matrices,
        value.algebra,
        value.certificates,
        value.diagnostics,
        value.prerequisites,
    )


def source_factors(d, pinv, w, r, alpha, area):
    """Exact targets for the stored native graph factorization, with no solve claim."""
    a = algebra
    l1 = a.scale_rows(d, w)
    l2 = a.negative(a.scale_rows(a.transpose(d), alpha))
    l1_inv = a.scale_columns(pinv, r)
    l2_inv = a.negative(a.scale_columns(a.transpose(pinv), area))
    return dict(
        delta_tri_0=d,
        delta_tri_0_inv=pinv,
        L1=l1,
        L2=l2,
        L1_inv=l1_inv,
        L2_inv=l2_inv,
        lapGJ=a.multiply(l2, l1),
        lapGJinv=a.multiply(l1_inv, l2_inv),
        stiffness=a.multiply(a.transpose(d), l1),
    )


def prepare(request, *, observer=None):
    work, stage = _Work(), "request"
    try:
        if type(request) is not Request or request.identity != digest(request_record(request)):
            raise ValueError("Changed or unsealed primal graph request")
        checked = bind(request.metric_request, request.metric_candidate, request.declaration)
        if digest(request_record(checked)) != digest(request_record(request)):
            raise ValueError("Changed full graph declaration or parents")
        corrected = request.metric_request.topology_candidate
        native, coefficients = (
            request.metric_candidate.native_roles,
            request.metric_candidate.coefficients,
        )
        edges = corrected.primal["edges"]
        n, e = len(corrected.geometry["tri_verts"]), len(edges)
        a = algebra
        stage = "exact_incidence_pseudoinverse"
        d = a.matrix(corrected.primal["delta_0"])
        work.partial["delta_tri_0"] = d
        connected = components(n, edges)
        q = a.matrix([[int(i in component) for component in connected] for i in range(n)])
        pinv, factors = a.pseudoinverse(d, journal=work.pivots)
        work.partial.update(delta_tri_0_inv=pinv, factors=factors)
        rank = factors["rank"]
        if rank != n - len(connected):
            raise ValueError("Incidence rank and complete connected-component kernel disagree")
        cycles = a.nullspace(a.transpose(d), journal=work.pivots, label="cycle_nullspace_rref")
        work.partial["edge_cycle_nullspace"] = cycles
        if observer is not None:
            observer(stage, plain(work.partial))
        stage = "source_stored_hodge_factors"
        w = _weights(coefficients["native_stored_dual_over_primal"], e, "dual/primal")
        r = _weights(coefficients["native_stored_primal_over_dual"], e, "primal/dual")
        alpha = _weights(coefficients["native_stored_inverse_dual_area"], n, "inverse_area")
        area = _weights(native["vor_sa"], n, "unscaled_dual_area")
        work.partial["source_hodge_inputs"] = dict(w=w, r=r, alpha=alpha, area=area)
        matrices = source_factors(d, pinv, w, r, alpha, area)
        work.partial["exact_matrices"] = matrices
        count = sum(value.rows * value.cols for value in matrices.values())
        if count > MAX_SCALAR_OUTPUTS:
            raise ValueError("The complete scalar cache panel exceeds the declared bound")
        effective_mass = tuple(1 / value for value in alpha)
        right_inverse_kernel = a.scale_rows(q, tuple(1 / value for value in area))
        left_forward_kernel = a.scale_rows(q, effective_mass)
        lap, inverse = matrices["lapGJ"], matrices["lapGJinv"]
        source_area_defect = a.multiply(a.transpose(q), a.scale_rows(lap, area))
        diagnostics = dict(
            input_ratio_reciprocal_seam=[w0 * r0 - 1 for w0, r0 in zip(w, r, strict=True)],
            input_area_reciprocal_seam=[x * y - 1 for x, y in zip(area, alpha, strict=True)],
            primal_boundary_of_boundary=a.multiply(a.matrix(corrected.primal["delta_1"]), d),
            source_area_forward_conservation_defect=source_area_defect,
            source_area_forward_adjoint_defect=a.subtract(
                a.scale_rows(lap, area), a.transpose(a.scale_rows(lap, area))
            ),
            forward_factorized_forward_defect=a.subtract(
                a.multiply(a.multiply(lap, inverse), lap), lap
            ),
            inverse_forward_inverse_defect=a.subtract(
                a.multiply(a.multiply(inverse, lap), inverse), inverse
            ),
            factorized_map_is_general_weighted_pseudoinverse_claimed=False,
            exact_forward_selfadjoint_mass="reciprocal_of_stored_inverse_area",
            exact_factorized_map_selfadjoint_mass="source_unscaled_area",
            rounded_cache_exact_nullspace_or_energy_claimed=False,
            native_BLAS_SVD_bytes_claimed=False,
        )
        work.partial["diagnostics"] = diagnostics
        if observer is not None:
            observer(stage, plain(work.partial))
        stage = "correctly_rounded_cache_readouts"
        rounded, indices, storage_errors = {}, {}, {}
        work.partial.update(rounded_matrices=rounded, matrix_event_indices=indices)
        for name, value in matrices.items():
            output, slots = [], []
            rounded[name], indices[name] = output, slots
            for i, row in enumerate(value.data):
                output_row, slot_row = [], []
                output.append(output_row)
                slots.append(slot_row)
                for j, target in enumerate(row):
                    stored, slot = work.round(target, name, i, j)
                    output_row.append(stored)
                    slot_row.append(slot)
            stored_exact = a.matrix([[Fraction.from_float(x) for x in row] for row in output])
            storage_errors[name] = a.subtract(stored_exact, value)
        diagnostics["storage_errors"] = storage_errors
        stored_lap = a.matrix([[Fraction.from_float(x) for x in row] for row in rounded["lapGJ"]])
        stored_inv = a.matrix(
            [[Fraction.from_float(x) for x in row] for row in rounded["lapGJinv"]]
        )
        diagnostics.update(
            rounded_forward_constant_defect=a.multiply(stored_lap, q),
            rounded_effective_mass_left_defect=a.multiply(
                a.transpose(left_forward_kernel), stored_lap
            ),
            rounded_source_area_forward_defect=a.multiply(
                a.transpose(q), a.scale_rows(stored_lap, area)
            ),
            rounded_inverse_right_kernel_defect=a.multiply(stored_inv, right_inverse_kernel),
            rounded_inverse_output_mean_defect=a.multiply(a.transpose(q), stored_inv),
        )
        if observer is not None:
            observer(stage, plain(work.partial))
        result = Candidate(
            request.identity,
            topology.freeze(
                dict(
                    primal_vertex_ids=request.metric_request.topology_request.retained_point_ids,
                    primal_edges=edges,
                    selected_dual_edges=corrected.dual["selected_edges"],
                    metric_identity=request.metric_candidate.identity,
                    topology_identity=corrected.identity,
                )
            ),
            topology.freeze(
                dict(
                    star_eij=dict(
                        kind="diagonal",
                        units="1",
                        values=list(coefficients["native_stored_dual_over_primal"]),
                    ),
                    star_eij_inv=dict(
                        kind="diagonal",
                        units="1",
                        values=list(coefficients["native_stored_primal_over_dual"]),
                    ),
                    star_a=dict(
                        kind="diagonal",
                        units="1/m2",
                        values=list(coefficients["native_stored_inverse_dual_area"]),
                    ),
                    star_a_inv=dict(kind="diagonal", units="m2", values=list(native["vor_sa"])),
                )
            ),
            topology.freeze(plain(matrices)),
            topology.freeze(rounded),
            topology.freeze(
                plain(
                    dict(
                        factors,
                        components=connected,
                        vertex_nullspace=q,
                        edge_cycle_nullspace=cycles,
                        forward_left_nullspace=left_forward_kernel,
                        factorized_inverse_right_nullspace=right_inverse_kernel,
                        effective_mass=effective_mass,
                        source_area=area,
                    )
                )
            ),
            topology.freeze(
                plain(
                    dict(
                        matrix_event_indices=indices,
                        arithmetic_events=work.scalars,
                        algebra_pivots=work.pivots,
                    )
                )
            ),
            topology.freeze(plain(diagnostics)),
            topology.freeze(
                dict(
                    **dict.fromkeys(GATE_NAMES, False),
                    invalidated=INVALIDATED,
                    independent_algebra_and_storage_checks_required=True,
                    reconstructed_cache_fields=(
                        "delta_tri_0",
                        "delta_tri_0_inv",
                        "lapGJ",
                        "lapGJinv",
                    ),
                    physical_geom_weight=None,
                    auxiliary_operators=None,
                    Dirichlet_injection=None,
                )
            ),
            "",
        )
        return replace(result, identity=digest(candidate_record(result)))
    except Exception as error:
        raise OperatorRejected(
            error,
            stage=stage,
            original=request,
            partial=topology.freeze(
                plain(
                    dict(
                        completed=work.partial,
                        algebra_pivots=work.pivots,
                        arithmetic_events=work.scalars,
                        source_error=dict(
                            type=type(error).__name__,
                            reason=str(error),
                            original=getattr(error, "original", None),
                            partial=getattr(error, "partial", None),
                            detail=getattr(error, "detail", None),
                        ),
                    )
                )
            ),
        ) from error


def require_native_cache(candidate):
    raise OperatorRejected(
        "Conditional graph caches do not qualify native inverse operators, "
        "physical geometry, auxiliary/boundary caches or the full loop",
        stage="native_cache_admission",
        original=candidate,
    )
