"""Source/AST-only origin and independence audit; no geometric evaluation."""

import ast
import hashlib
import json
from pathlib import Path

CORE = "src/cells/processes/stable_seed_control_volumes.py"
REFERENCE = "validation/geometry/stable_seed_control_volumes_reference.py"
PARENT = Path("/mnt/workspaces/Cells/stable-mesh-metric-reconstruction-prepared-20261031-03")
PARENT_SHA256 = "39c7dae39a44409cd83cf352d60f98ae5a96133537b51549296d611ff66522f9"
NATIVE_PINS = {
    "betse/science/math/mesh.py": (
        "fd0dc21e1f82aa71e19a487f3b91c4b5258f02aec4c69f22c2bf3c419e425c38"
    ),
    "betse/science/cells.py": "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def function(tree, name, cls=None):
    body = tree.body
    if cls:
        body = next(
            node.body for node in body if isinstance(node, ast.ClassDef) and node.name == cls
        )
    return next(node for node in body if isinstance(node, ast.FunctionDef) and node.name == name)


def literal(tree, name):
    return ast.literal_eval(
        next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
        )
    )


def site(source, node):
    return dict(
        source=source,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
        expression=ast.unparse(node),
    )


def calls(node):
    return [ast.unparse(child.func) for child in ast.walk(node) if isinstance(child, ast.Call)]


def audit(native, project):
    native, project = Path(native), Path(project)
    assert sha(PARENT / "manifest.json") == PARENT_SHA256
    parent = json.loads((PARENT / "manifest.json").read_text())["file_sha256"]
    for path, pin in NATIVE_PINS.items():
        assert sha(native / path) == pin, path
    code = ast.parse((project / CORE).read_bytes())
    reference = ast.parse((project / REFERENCE).read_bytes())
    dependencies = dict(literal(code, "SOURCE_PINS"))
    for name, pin in dependencies.items():
        path = "src/cells/processes/" + name + ".py"
        assert sha(project / path) == pin == parent["source/" + path], path
    mesh_path, cells_path = "betse/science/math/mesh.py", "betse/science/cells.py"
    mesh = ast.parse((native / mesh_path).read_bytes())
    cells = ast.parse((native / cells_path).read_bytes())
    mappings = function(mesh, "create_mappings", "DECMesh")
    lookups = [
        ast.unparse(node)
        for node in ast.walk(mappings)
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "edge_tree.query"
    ]
    assert lookups == ["edge_tree.query([vi, vj])"]
    layout = function(mesh, "define_vorverts", "DECMesh")
    assignments = {
        ast.unparse(node.targets[0]): ast.unparse(node.value)
        for node in ast.walk(layout)
        if isinstance(node, ast.Assign) and len(node.targets) == 1
    }
    assert assignments["bedge_mid"] == "np.mean(bedge_verts, axis=0)"
    assert assignments["dist_diff"] == "bedge_mid - pt_o"
    assert assignments["intpt"] == "bedge_mid + dist_diff"
    assert "self.cc_sort_inds" in calls(layout)
    assert "cKDTree" in calls(layout)
    original_topology_path = "src/cells/processes/stable_mesh_physical_reconstruction.py"
    original_topology = ast.parse((project / original_topology_path).read_bytes())
    reconstruct = function(original_topology, "reconstruct")
    assert (
        "freeze(dict(tri_verts=points, tri_cells=faces, vor_verts=vpoints, vor_cells=vcells))"
        in ast.unparse(reconstruct)
    )
    primary = function(code, "exact_partition")
    assert "_clip" in calls(primary)
    independent = function(reference, "independent_partition")
    assert "intersection" in calls(independent) and "hull" in calls(independent)
    assert not any(name.endswith("_clip") for name in calls(independent))
    assert not any(name.startswith(("np.", "numpy.", "scipy.")) for name in calls(code))
    assert not any(
        name in calls(code)
        for name in (
            "polygons.prepare",
            "polygons.from_polygons",
            "topology.require_physical_admission",
        )
    )
    assert {
        "polygons._complex",
        "polygons._moments",
        "polygons._inside",
        "arithmetic._round",
    } <= set(calls(code))
    imported = []
    for node in ast.walk(reference):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module)
    assert not {name.split(".")[0] for name in imported} & {
        "cells",
        "betse",
        "numpy",
        "scipy",
        "jax",
        "PIL",
        "torch",
    }
    assert isinstance(function(code, "require_physical_admission").body[0], ast.Raise)
    return dict(
        kind="cells.fixed_seed_control_volumes_static_correspondence@1",
        metric03_dependency_manifest_sha256=PARENT_SHA256,
        runtime_dependency_sha256=dependencies,
        native_source_sha256=NATIVE_PINS,
        native_origin={
            name: site(mesh_path, function(mesh, name, "DECMesh"))
            for name in (
                "trimesh_core_calcs",
                "create_tri_map",
                "create_mappings",
                "define_vorverts",
                "process_voredges",
            )
        },
        lattice_domain_origin=site(cells_path, function(cells, "_make_cell_lattice", "Cells")),
        corrected_topology_preserves_source_geometry=site(original_topology_path, reconstruct),
        production_exact_construction=site(CORE, primary),
        independent_exact_construction=site(REFERENCE, independent),
        reused_conservative_admission=site(CORE, function(code, "admit_complex")),
        conservation=site(CORE, function(code, "conservation")),
        domain_contract=site(CORE, function(code, "_domain")),
        independent_stored_geometry_admission=site(REFERENCE, function(reference, "admit")),
        boundary=dict(
            seeds_and_ids_fixed=True,
            original_layout_evidence_retained=True,
            old_dual_coordinates_rings_and_connectivity_replaced=True,
            envelope="explicit caller convex polygon; never an implicit plotting extent/margin",
            physical_admission=False,
            native_equivalence=False,
            old_failures_reclassified=False,
        ),
        preparation=dict(
            source_AST_only=True,
            scientific_imports=False,
            geometric_evaluations=0,
            fixture_executions=0,
            collection=0,
            qualification_jobs=0,
            GPU_jobs=0,
            metric_files_edited=False,
            operator01_or02_edited=False,
            root_diagnostic_edited=False,
            PROGRESS_or_shared_ledger_edited=False,
        ),
    )
