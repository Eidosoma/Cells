"""Static correspondence for native metric roles and the new candidate law."""

import ast
import hashlib
import json
from pathlib import Path

CORE = "src/cells/processes/stable_mesh_metric_reconstruction.py"
REFERENCE = "validation/geometry/stable_mesh_metric_reconstruction_reference.py"
CHECKS = "validation/geometry/stable_mesh_metric_reconstruction_checks.py"
TEST = "tests/unit/test_stable_mesh_metric_reconstruction.py"
PARENT = Path("/mnt/workspaces/Cells/stable-mesh-physical-reconstruction-prepared-20261031-02")
PARENT_SHA256 = "86867136cb973d47bb2765039090254eb403e7ac2037789177aea5879fcb0b39"
PARENT_RECEIPT = Path(
    "/mnt/workspaces/Cells/stable-mesh-physical-reconstruction-preparation-20261031-02.json"
)
PARENT_RECEIPT_SHA256 = "66efd4333eff97162a46432547bb7b50a49e5fb64049286dc3fce2f8bc3a2116"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def function(tree, name, cls=None):
    body = tree.body
    if cls:
        body = next(
            node.body for node in body if isinstance(node, ast.ClassDef) and node.name == cls
        )
    return next(node for node in body if isinstance(node, ast.FunctionDef) and node.name == name)


def site(path, node):
    return dict(
        source=path,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def assigned(node, target):
    return [
        n
        for n in ast.walk(node)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == target for t in n.targets)
    ]


def literal(tree, name):
    return ast.literal_eval(
        next(
            n.value
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
        )
    )


def audit(checkout, project):
    checkout, project = Path(checkout), Path(project)
    if (
        sha(PARENT / "manifest.json") != PARENT_SHA256
        or sha(PARENT_RECEIPT) != PARENT_RECEIPT_SHA256
    ):
        raise ValueError("Require the explicit topology02 successor")
    core = ast.parse((project / CORE).read_bytes())
    pins = literal(core, "SOURCE_PINS")
    for name, expected in pins:
        if sha(project / ("src/cells/processes/" + name + ".py")) != expected:
            raise ValueError("Changed pinned metric dependency: " + name)
    native_pins = {
        "betse/science/math/mesh.py": (
            "fd0dc21e1f82aa71e19a487f3b91c4b5258f02aec4c69f22c2bf3c419e425c38"
        ),
        "betse/science/cells.py": (
            "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"
        ),
    }
    for path, expected in native_pins.items():
        if sha(checkout / path) != expected:
            raise ValueError("Changed pinned native metric source")
    mesh_path, cells_path = native_pins
    mesh, cells = (ast.parse((checkout / path).read_bytes()) for path in native_pins)
    define = function(mesh, "define_vorverts", "DECMesh")
    reference_area = assigned(define, "self.tri_sa_o")
    assert len(reference_area) == 1 and ast.unparse(reference_area[0].value) == "tri_sa_o[vi]"
    graph = function(cells, "graphLaplacian", "Cells")
    reads = sorted(
        {
            n.attr
            for n in ast.walk(graph)
            if isinstance(n, ast.Attribute) and ast.unparse(n.value) == "self.mesh"
        }
    )
    assert reads == ["delta_tri_0", "delta_tri_0_inv", "tri_edge_len", "vor_edge_len", "vor_sa"]
    coefficient_sites = {
        name: site(cells_path, assigned(graph, name)[0])
        for name in ("star_eij", "star_a", "star_eij_inv", "star_a_inv")
    }
    native_methods = {}
    for name in (
        "process_primary_edges",
        "define_vorverts",
        "process_voredges",
        "create_core_operators",
        "create_aux_operators",
    ):
        node = function(mesh, name, "DECMesh")
        native_methods[name] = site(mesh_path, node) | dict(body=ast.unparse(node))
    helper_path = "src/cells/processes/conservative_polygon_geometry.py"
    helper = ast.parse((project / helper_path).read_bytes())
    helpers = {
        name: site(helper_path, function(helper, name))
        for name in ("_complex", "_moments", "_rounded", "_root", "_platform", "_inside")
    }
    reference = ast.parse((project / REFERENCE).read_bytes())
    payload_reads = {
        n.slice.value
        for n in ast.walk(reference)
        if isinstance(n, ast.Subscript)
        and isinstance(n.value, ast.Name)
        and n.value.id == "payload"
        and isinstance(n.slice, ast.Constant)
    }
    assert payload_reads == {"source_cache", "corrected"}
    assert "exact original ring union" in (project / REFERENCE).read_text()
    assert not any(
        isinstance(n, ast.Call)
        and ast.unparse(n.func).endswith(("pinv", "Delaunay", "run_sim_core"))
        for n in ast.walk(core)
    )
    tests = ast.parse((project / TEST).read_bytes())
    begin = function(tests, "begin")
    assert any(
        isinstance(n, ast.Call) and ast.unparse(n.func) == "archives.persist"
        for n in ast.walk(begin)
    )
    original_review = Path(
        "/mnt/workspaces/Cells/stable-initial-mesh-preparation-20261030-01/root-review-01/REVIEW.json"
    )
    review = json.loads(original_review.read_text())
    return dict(
        kind="cells.stable_mesh_metric_reconstruction_static_correspondence@1",
        topology02=dict(
            path=str(PARENT),
            manifest_sha256=PARENT_SHA256,
            receipt=str(PARENT_RECEIPT),
            receipt_sha256=PARENT_RECEIPT_SHA256,
            candidate_core_unchanged=True,
            qualification_inherited=False,
        ),
        dependency_source_sha256=dict(pins),
        native_source_sha256=native_pins,
        native_methods=native_methods,
        native_dual_vertex_reference_area_scatter=site(mesh_path, reference_area[0]),
        native_graph_mesh_reads=reads,
        native_graph_metric_coefficients=coefficient_sites,
        existing_exact_helpers=helpers,
        new_roles=dict(
            coordinates="original topology coordinates retained bitwise",
            metric_centroids="exact rational targets; original layout anchors remain fixed",
            edge_lengths="correctly rounded dyadic-root target on actual endpoint coordinates",
            directions="source axes; clockwise dual orientation; no orthogonality claim",
            dual_vertex_reference_area="explicit owners; coalesce equal areas without summing",
            source_anchor_admission="existing floor1e-27 +6e-12 relative; centroid also32ulp",
            native_length_ratios="ratio of independently reconstructed binary64 length stores",
            geometric_length_ratios="sqrt of exact squared-length ratio; separate diagnostic",
            inverse_area="reciprocal of the reconstructed binary64 dual area store",
            unsupported="circumcenter layout, unresolved owners, geometry or rounding",
            unqualified="inverse operators, graph, physical cells/environment and initialized loop",
        ),
        independent=dict(
            actual_outgoing_metric_values_supplied_to_reference=False,
            original_ring_edge_union_checked=True,
            Decimal_precision_forms=[4096, 4608],
            existing_exact_polygon_reference=True,
            existing_metric_floors_unchanged=True,
            store_coefficients="exact independently projected binary64; no new numeric floor",
            arithmetic_certificate_checks=True,
        ),
        original_evidence=dict(
            path=str(original_review),
            sha256=sha(original_review),
            original_complete_mesh_passes=review["counts"]["complete_mesh_geometry_passes"],
            original_failures_reclassified=False,
        ),
        scope=dict(
            metric_candidate_evaluated=False,
            topology_candidate_evaluated=False,
            reference_evaluated=False,
            scientific_imports=False,
            fixtures_constructed=False,
            collection=False,
            jobs=False,
            polling=False,
            PROGRESS_edited=False,
            shared_deformation_or_mechanics_checker_edited=False,
            physical_admission=False,
        ),
    )
