"""Stdlib source correspondence and downstream invalidation inventory only."""

import ast
import hashlib
from pathlib import Path

NATIVE = {
    "betse/science/math/mesh.py": (
        "fd0dc21e1f82aa71e19a487f3b91c4b5258f02aec4c69f22c2bf3c419e425c38"
    ),
    "betse/science/cells.py": ("be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"),
    "betse/science/parameters.py": (
        "f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e"
    ),
    "betse/science/sim.py": ("02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43"),
}
CORE = "src/cells/processes/stable_mesh_physical_reconstruction.py"
KERNEL = "src/cells/processes/betse_initial_mesh_preparation_kernel.py"
OLD_ROOT = Path("/mnt/workspaces/Cells/stable-initial-mesh-preparation-20261030-01")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def method(tree, cls, name):
    return next(
        n
        for c in tree.body
        if isinstance(c, ast.ClassDef) and c.name == cls
        for n in c.body
        if isinstance(n, ast.FunctionDef) and n.name == name
    )


def site(path, node):
    return dict(
        source=path,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def calls(node, expression):
    return sorted(
        (
            n
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and ast.unparse(n.func) == expression
        ),
        key=lambda n: n.lineno,
    )


def stores(node):
    result = set()
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == "self"
            and isinstance(n.ctx, ast.Store)
        ):
            result.add(n.attr)
    return sorted(result)


def attributes(node, receiver):
    return sorted(
        {
            n.attr
            for n in ast.walk(node)
            if isinstance(n, ast.Attribute) and ast.unparse(n.value) == receiver
        }
    )


def audit(checkout, project):
    checkout, project = Path(checkout), Path(project)
    for path, pin in NATIVE.items():
        if sha(checkout / path) != pin:
            raise ValueError("Changed pinned native geometry source: " + path)
    mesh_path, cells_path = "betse/science/math/mesh.py", "betse/science/cells.py"
    mesh = ast.parse((checkout / mesh_path).read_bytes())
    cells = ast.parse((checkout / cells_path).read_bytes())
    mapping = method(mesh, "DECMesh", "create_mappings")
    assert len(calls(mapping, "edge_tree.query")) == 1
    query = calls(mapping, "edge_tree.query")[0]
    assert ast.unparse(query.args[0]) == "[vi, vj]"
    exact_guard = next(
        n
        for n in ast.walk(mapping)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "dist_e == 0.0"
    )
    assert query.lineno < exact_guard.lineno
    vor = method(mesh, "DECMesh", "process_voredges")
    boundary_store = next(
        n
        for n in ast.walk(vor)
        if isinstance(n, ast.Assign)
        and any(ast.unparse(t) == "self.bflags_vedges" for t in n.targets)
    )
    selection = next(
        n
        for n in ast.walk(vor)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "self.vor_edges" for t in n.targets)
    )
    assert ast.unparse(selection.value) == "vor_edges[map_vedge_to_tedge]"
    nearest = next(
        n for n in calls(vor, "vor_tree.query") if ast.unparse(n.args[0]) == "self.tri_mids"
    )
    assert boundary_store.lineno < nearest.lineno < selection.lineno
    assert (
        len(
            [
                n
                for n in ast.walk(vor)
                if isinstance(n, ast.Attribute)
                and isinstance(n.ctx, ast.Store)
                and ast.unparse(n) == "self.bflags_vedges"
            ]
        )
        == 1
    )
    boundary_reads = [
        n
        for t in (mesh, cells)
        for n in ast.walk(t)
        if isinstance(n, ast.Attribute)
        and n.attr == "bflags_vedges"
        and isinstance(n.ctx, ast.Load)
    ]
    assert not boundary_reads
    aux = method(mesh, "DECMesh", "create_aux_operators")
    assert len(calls(aux, "tedge_tree.query")) == 2
    assert {ast.unparse(n.args[0]) for n in calls(aux, "tedge_tree.query")} == {
        "[vi, vj]",
        "[vj, vi]",
    }
    physical_order = (
        "cell_index",
        "cellVerts",
        "cellMatrices",
        "cell_vols",
        "mem_processing",
        "near_neigh",
        "makeECM",
        "environment",
    )
    world = method(cells, "Cells", "make_world")
    reached = [calls(world, "self." + name)[0].lineno for name in physical_order]
    assert reached == sorted(reached)
    fields, bodies = {}, {}
    for path, tree, cls, names in (
        (
            mesh_path,
            mesh,
            "DECMesh",
            (
                "pre_mesh",
                "process_primary_edges",
                "create_mappings",
                "define_vorverts",
                "process_voredges",
                "create_core_operators",
                "create_aux_operators",
            ),
        ),
        (
            cells_path,
            cells,
            "Cells",
            ("make_world", "make_voronoi", *physical_order, "redo_gj", "graphLaplacian"),
        ),
    ):
        for name in names:
            node = method(tree, cls, name)
            key = cls + "." + name
            fields[key] = site(path, node) | dict(
                attribute_bindings=stores(node),
                self_attribute_occurrences=attributes(node, "self"),
                parameter_reads=attributes(node, "p"),
            )
            bodies[key] = ast.unparse(node)
    index = method(cells, "Cells", "cell_index")
    vols = method(cells, "Cells", "cell_vols")
    index_vol = next(
        n
        for n in ast.walk(index)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "self.cell_vol" for t in n.targets)
    )
    final_vol = next(
        n
        for n in ast.walk(vols)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "self.cell_vol" for t in n.targets)
    )
    assert ast.unparse(index_vol.value) == "self.mesh.vor_sa * p.cell_height"
    assert ast.unparse(final_vol.value) == "np.dot(self.M_sum_mems, self.mem_vol)"
    vertices = method(cells, "Cells", "cellVerts")
    vectors = next(
        n
        for n in ast.walk(vertices)
        if isinstance(n, ast.Assign)
        and any(ast.unparse(t) == "self.mem_vects_flat" for t in n.targets)
    )
    assert ast.unparse(vectors.value) == "np.array([cv_x, cv_y, cv_nx, cv_ny, cv_tx, cv_ty]).T"
    previous = next(
        n
        for n in ast.walk(vertices)
        if isinstance(n, ast.Assign)
        and any(ast.unparse(t) == "pt1" for t in n.targets)
        and ast.unparse(n.value) == "polyc[i - 1]"
    )
    current = next(
        n
        for n in ast.walk(vertices)
        if isinstance(n, ast.Assign)
        and any(ast.unparse(t) == "pt2" for t in n.targets)
        and ast.unparse(n.value) == "polyc[i]"
    )
    params = ast.parse((checkout / "betse/science/parameters.py").read_bytes())
    scale = next(
        n
        for n in ast.walk(params)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "self.scale_cell" for t in n.targets)
    )
    core = ast.parse((project / CORE).read_bytes())
    assert not any(
        isinstance(n, (ast.Import, ast.ImportFrom))
        and ((n.module if isinstance(n, ast.ImportFrom) else n.names[0].name) or "").split(".")[0]
        in {"numpy", "scipy", "jax", "betse", "cells"}
        for n in ast.walk(core)
    )
    assert not any(
        isinstance(n, ast.Call)
        and ast.unparse(n.func).endswith(("pinv", "sqrt", "Delaunay", "reconstruct_native"))
        for n in ast.walk(core)
    )
    kernel = ast.parse((project / KERNEL).read_bytes())
    kernel_cls = next(n.name for n in kernel.body if isinstance(n, ast.ClassDef))
    owned_mapping = method(kernel, kernel_cls, "create_mappings")
    return dict(
        kind="cells.stable_mesh_physical_reconstruction_source_correspondence@1",
        native_source_sha256=NATIVE,
        original_mapping_kernel_sha256=sha(project / KERNEL),
        original_directed_mapping=dict(
            query=site(mesh_path, query),
            exact_directed_guard=site(mesh_path, exact_guard),
            native_method=site(mesh_path, mapping),
            preserved_owned_method=site(KERNEL, owned_mapping),
        ),
        original_dual_axis_defect=dict(
            full_boundary_flag_store=site(mesh_path, boundary_store),
            nearest_midpoint_selection=site(mesh_path, nearest),
            overwritten_selected_axis=site(mesh_path, selection),
            boundary_flags_reindexed_after_selection=False,
            flag_read_by_audited_mesh_or_cells_code=False,
        ),
        original_aux_operator=dict(
            method=site(mesh_path, aux),
            already_checks_both_directions=True,
            distinction=(
                "mapping cache defect is separate from already signed native auxiliary incidence"
            ),
        ),
        downstream_native_owners=fields,
        downstream_source_bodies=bodies,
        physical_order=list(physical_order),
        source_metric_roles=dict(
            initial_mesh_area_volume=site(cells_path, index_vol),
            final_physical_pie_volume=site(cells_path, final_vol),
            scale_cell_producer=site("betse/science/parameters.py", scale),
            scale_cell_statement=ast.unparse(scale),
            separate_unshrunk_DEC_area_and_scaled_physical_volume=True,
            drawing_only_comment_is_not_used_to_override_reached_physical_operations=True,
            native_membrane_vector_store=site(cells_path, vectors),
            native_membrane_vector_columns=(
                "mid_x",
                "mid_y",
                "normal_x",
                "normal_y",
                "tangent_x",
                "tangent_y",
            ),
            membrane_previous_endpoint=site(cells_path, previous),
            membrane_current_endpoint=site(cells_path, current),
        ),
        corrected_law=dict(
            original_seed_primal_dual_coordinates_preserved=True,
            primal_mapping="exact undirected pair with retained source edge orientation",
            vertex_mapping="unique edge endpoint membership",
            dual_pairing="unique actual polygon owner pair; missing/ambiguous pairs refused",
            axes="full dual polygon edge IDs and primal-aligned selected dual IDs are separate",
            operators="integer incidence only; inverses/metrics/physical cache rebuild required",
            boundary_membrane_partner_policy="explicitly unresolved, never defaulted to self",
            native_equivalence=False,
            physical_admission=False,
            core_imports_scientific_packages=False,
        ),
        reused_evidence=dict(
            original_failed_review=dict(
                path=str(OLD_ROOT / "root-review-01/REVIEW.json"),
                sha256=sha(OLD_ROOT / "root-review-01/REVIEW.json"),
            ),
            stable_primitive_bundle=dict(
                path="/mnt/workspaces/Cells/stable-geometry-primitives-prepared-20261030-02/manifest.json",
                sha256="71add3636c486e9a2ec2f6690ed1b48a51c4011f6ded3d3da4e49e8f1dbb55b8",
                use=(
                    "separate prior law; prospective metrics may reuse it "
                    "without inheriting whole mesh qualification"
                ),
            ),
            mesh_lifecycle_review=dict(
                path=(
                    "/mnt/workspaces/Cells/betse-mesh-lifecycle-preparation-20261030-01/"
                    "root-review-01/REVIEW.json"
                ),
                use=(
                    "separate conditional lifecycle/operator evidence, "
                    "not a completed physical seed"
                ),
            ),
        ),
        scope=dict(
            source_bodies_evaluated=False,
            reference_evaluated=False,
            corrected_adapter_evaluated=False,
            fixtures_constructed=False,
            geometry_recomputed=False,
            original_failures_reclassified=False,
        ),
    )
