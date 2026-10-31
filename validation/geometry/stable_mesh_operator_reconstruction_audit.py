"""Static native operator/store-seam correspondence; never import scientific code."""

import ast
import hashlib
import json
from pathlib import Path

CORE = "src/cells/processes/stable_mesh_operator_reconstruction.py"
ALGEBRA = "src/cells/processes/stable_mesh_operator_reconstruction_algebra.py"
REFERENCE = "validation/geometry/stable_mesh_operator_reconstruction_reference.py"
TEST = "tests/unit/test_stable_mesh_operator_reconstruction.py"
TOPOLOGY02 = Path("/mnt/workspaces/Cells/stable-mesh-physical-reconstruction-prepared-20261031-02")
TOPOLOGY02_SHA256 = "86867136cb973d47bb2765039090254eb403e7ac2037789177aea5879fcb0b39"
METRIC02 = Path("/mnt/workspaces/Cells/stable-mesh-metric-reconstruction-prepared-20261031-02")
METRIC02_SHA256 = "8cf17f19595b67d10cc37a58fc9f4b2cdce99b4d50853d9f4c9a1e554e8e1811"
METRIC03 = Path("/mnt/workspaces/Cells/stable-mesh-metric-reconstruction-prepared-20261031-03")
METRIC03_SHA256 = "39c7dae39a44409cd83cf352d60f98ae5a96133537b51549296d611ff66522f9"
PROBE_REVIEW = Path(
    "/mnt/workspaces/Cells/stable-mesh-metric-square-zero-probe-review-20261031-01/REVIEW.json"
)
PROBE_REVIEW_SHA256 = "4bff37c48e8701b07f7fb7bac773e1afb2d4c8fbd134a3d96dea0a942d47e185"
COMPANION = Path("/mnt/workspaces/Cells/stable-mesh-metric-reconstruction-companion-20261031-03")
COMPANION_SHA256 = "9b6bc90a7ff788e8ee8615a755128c2f71014c0fc916233037caebb1a7e944df"
NATIVE_PINS = {
    "betse/science/math/mesh.py": (
        "fd0dc21e1f82aa71e19a487f3b91c4b5258f02aec4c69f22c2bf3c419e425c38"
    ),
    "betse/science/cells.py": "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2",
}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def literal(tree, name):
    return ast.literal_eval(
        next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
        )
    )


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
        expression=ast.unparse(node),
    )


def calls(node, expression):
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and ast.unparse(child.func) == expression
    ]


def assigned(node, target):
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Assign)
        and any(ast.unparse(value) == target for value in child.targets)
    ]


def audit(native, project):
    native, project = Path(native), Path(project)
    assert sha(TOPOLOGY02 / "manifest.json") == TOPOLOGY02_SHA256
    assert sha(METRIC02 / "manifest.json") == METRIC02_SHA256
    assert sha(METRIC03 / "manifest.json") == METRIC03_SHA256
    assert sha(PROBE_REVIEW) == PROBE_REVIEW_SHA256
    assert sha(COMPANION / "manifest.json") == COMPANION_SHA256
    parent = json.loads((METRIC03 / "manifest.json").read_text())["file_sha256"]
    code, algebra, reference = (
        ast.parse((project / path).read_bytes()) for path in (CORE, ALGEBRA, REFERENCE)
    )
    pins = dict(literal(code, "SOURCE_PINS"))
    assert literal(code, "BASELINE_BINDING") == literal(reference, "BASELINE_BINDING")
    binding = literal(code, "BASELINE_BINDING")
    assert binding["metric03_manifest_sha256"] == METRIC03_SHA256
    assert binding["probe_review_sha256"] == PROBE_REVIEW_SHA256
    assert binding["metric03_companion_manifest_sha256"] == COMPANION_SHA256
    assert len(calls(function(code, "bind"), "_verify_parent_baseline")) == 1
    assert len(calls(function(reference, "derive"), "verify_parent_baseline")) == 1
    for name, expected in pins.items():
        path = "src/cells/processes/" + name + ".py"
        assert sha(project / path) == expected, path
        if path != ALGEBRA:
            assert parent["source/" + path] == expected, path
    for path, expected in NATIVE_PINS.items():
        assert sha(native / path) == expected, path
    mesh = ast.parse((native / "betse/science/math/mesh.py").read_bytes())
    cells = ast.parse((native / "betse/science/cells.py").read_bytes())
    core = function(mesh, "create_core_operators", "DECMesh")
    assert len(calls(core, "np.linalg.pinv")) == 1
    assert ast.unparse(calls(core, "np.linalg.pinv")[0]) == "np.linalg.pinv(self.delta_tri_0)"
    graph = function(cells, "graphLaplacian", "Cells")
    expected = {
        "star_eij": "np.diag(self.mesh.vor_edge_len / self.mesh.tri_edge_len)",
        "star_eij_inv": "np.diag(self.mesh.tri_edge_len / self.mesh.vor_edge_len)",
        "star_a": "np.diag(1 / self.mesh.vor_sa)",
        "star_a_inv": "np.diag(self.mesh.vor_sa)",
        "L1": "np.dot(star_eij, self.mesh.delta_tri_0)",
        "L2": "np.dot(star_a, -self.mesh.delta_tri_0.T)",
        "L1_inv": "np.dot(self.mesh.delta_tri_0_inv, star_eij_inv)",
        "L2_inv": "np.dot(-self.mesh.delta_tri_0_inv.T, star_a_inv)",
        "self.lapGJ": "np.dot(L2, L1)",
        "self.lapGJinv": "np.dot(L1_inv, L2_inv)",
    }
    graph_sites = {}
    for name, expression in expected.items():
        matches = assigned(graph, name)
        assert len(matches) == 1 and ast.unparse(matches[0].value) == expression, name
        graph_sites[name] = site("betse/science/cells.py", matches[0])
    physical = assigned(graph, "self.geom_weight")
    assert len(physical) == 1
    source_functions = {
        name: site("betse/science/math/mesh.py", function(mesh, name, "DECMesh"))
        for name in (
            "create_core_operators",
            "create_aux_operators",
            "grad",
            "grad_xy",
            "div",
            "lap",
            "lap_inv",
        )
    }
    new_functions = {
        name: site(CORE, function(code, name))
        for name in ("bind", "prepare", "source_factors", "components", "require_native_cache")
    }
    assert not any(
        isinstance(node, ast.Call)
        and ast.unparse(node.func).endswith((".pinv", ".svd", ".lstsq", ".run_sim_core", ".cold"))
        for node in ast.walk(code)
    )
    assert not any(
        isinstance(node, ast.Call) and ast.unparse(node.func).endswith((".pinv", ".svd", ".lstsq"))
        for node in ast.walk(algebra)
    )
    assert len(calls(function(reference, "derive"), "bareiss_solve")) == 1
    assert "baseline_failed" in (project / REFERENCE).read_text()
    assert "input_exact" in (project / REFERENCE).read_text()
    assert isinstance(function(code, "require_native_cache").body[0], ast.Raise)
    tests = ast.parse((project / TEST).read_bytes())
    corrupt = function(tests, "test_resealed_corruption_requires_a_passing_independent_baseline")
    assert any(
        isinstance(node, ast.keyword) and node.arg == "baseline" for node in ast.walk(corrupt)
    )
    return dict(
        kind="cells.stable_mesh_operator_static_correspondence@1",
        topology02_manifest_sha256=TOPOLOGY02_SHA256,
        metric02_manifest_sha256=METRIC02_SHA256,
        metric03_manifest_sha256=METRIC03_SHA256,
        probe_review_sha256=PROBE_REVIEW_SHA256,
        prospective_metric03_companion_sha256=COMPANION_SHA256,
        explicit_reviewed_parent_binding=binding,
        runtime_source_sha256=pins,
        native_source_sha256=NATIVE_PINS,
        native_mesh_methods=source_functions,
        native_graph_assignments=graph_sites,
        withheld_physical_geom_weight=site("betse/science/cells.py", physical[0]),
        new_operator_sites=new_functions,
        exact_rank_factorization=site(ALGEBRA, function(algebra, "pseudoinverse")),
        independent_bordered_integer_solve=site(REFERENCE, function(reference, "bareiss_solve")),
        independent_target_derivation=site(REFERENCE, function(reference, "derive")),
        independent_certificate_and_algebra_checks=site(
            REFERENCE, function(reference, "verify_candidate")
        ),
        boundary=dict(
            included="primal D0, unweighted exact MP and source graph factorized caches",
            source_inverse="native factorized map; not a general weighted MP/inverse claim",
            finite_arithmetic="binary64 store targets; no native BLAS/SVD byte equality",
            forward_mass="exact reciprocal of stored inverse area; source-area defect retained",
            factorized_mass="source unscaled area; right kernel uses its reciprocal",
            rank="exact rational full-rank factorization; no cutoff, damping or regularization",
            excluded="dual/curl/Cartesian/Dirichlet/geom_weight/physical/ECM/full-loop caches",
        ),
        evidence=dict(
            complete_source_owner_scalar_cardinality=True,
            independent_target_links=True,
            complete_exact_pivot_inputs_and_returns=True,
            positive_baseline_required_in_control_worker=True,
            no_control_credit_if_positive_reference_is_broken=True,
        ),
        scope=dict(
            science_imports=False,
            numerical_evaluations=False,
            fixture_construction=False,
            collection=False,
            jobs=False,
            PROGRESS_edited=False,
            frozen_packets_edited=False,
            shared_catalog_calcium_mechanics_files_edited=False,
            physical_admission=False,
        ),
    )
