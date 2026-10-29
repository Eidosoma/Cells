"""Native geometry, independent owner/measures, conservation and CPU JAX."""

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_geometry as geometry
from validation.geometry import betse_geometry_reference as reference
from validation.geometry.betse_geometry_fixtures import cases, grid_cases, limitations

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/geometry/betse_geometry_protocol.json").read_text())


def captured(name):
    folder = os.environ.get("CELLS_BETSE_GEOMETRY_NATIVE_CAPTURE")
    if not folder:
        pytest.skip("Bounded wrapper supplies actual authenticated native geometries")
    return json.loads((Path(folder) / (name + ".json")).read_text())


def evidence(name, record):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("betse-geometry-" + name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False) + "\n"
        )


def grid_spec(record):
    raw = record["environment"]
    config = record["input"]
    bounds = config["bounds_m"]
    return geometry.GridSpec(
        tuple(f"{record['name']}:environment:{i}" for i in range(len(raw["xy_cents"]))),
        tuple(raw["cents_shape"]),
        tuple(bounds),
        raw["delta"],
        np.asarray(raw["xy_cents"]),
        raw["boundaries"],
        dict(
            native_case=record["name"],
            bounds=bounds,
            grid_shape=raw["cents_shape"],
            source_revision=PROTOCOL["native_source"]["revision"],
        ),
    )


def mesh_spec(record):
    raw = record["mesh"]
    seed = record["seed_binding"]
    assert all(len(row) == 1 for row in seed["retained_matches"])
    ids = tuple(row[0] for row in seed["retained_matches"])
    prefix = record["name"]
    dual = tuple(f"{prefix}:dual-vertex:{i}" for i in range(len(raw["vor_verts"])))
    edges = tuple(f"{prefix}:paired-edge:{i}" for i in range(len(raw["tri_edges"])))
    faces = tuple(f"{prefix}:face:{i}" for i in range(len(raw["tri_cells"])))
    return geometry.MeshSpec(
        ids,
        edges,
        faces,
        dual,
        np.asarray(raw["tri_verts"]),
        tuple(tuple(ids[i] for i in row) for row in raw["tri_edges"]),
        tuple(tuple(ids[i] for i in row) for row in raw["tri_cells"]),
        np.asarray(raw["vor_verts"]),
        tuple(tuple(dual[i] for i in row) for row in raw["vor_edges"]),
        tuple(tuple(dual[i] for i in row) for row in raw["vor_cells"]),
        tuple(ids[i] for i in raw["bflags_tverts"]),
        tuple(dual[i] for i in raw["inner_vvert_i"]),
        np.asarray(raw["tri_sa_o"]),
        tuple(faces[row[0]] for row in record["dual_control_face_candidates"]),
        record["input"]["mesh"]["make_all_operators"],
        tuple(seed["original_ids"]),
        tuple(seed["removed_ids"]),
        dict(
            native_case=prefix,
            seed=record["input"]["seed"],
            seed_binding=seed,
            mesh_parameters=record["input"]["mesh"],
            seed_policy=record["input"]["seed_policy"],
            original_seed_points_m=record["constructed_seed_points_m"],
            source_revision=PROTOCOL["native_source"]["revision"],
        ),
    )


def geometry_spec(record):
    mesh = geometry.bind_mesh(mesh_spec(record))
    grid = geometry.bind_grid(grid_spec(record))
    raw = record["cells"]
    config = record["input"]["cell"]
    ids = tuple(f"{record['name']}:membrane:{i}" for i in range(len(raw["mem_sa"])))
    return geometry.GeometrySpec(
        mesh,
        grid,
        ids,
        tuple(tuple(ids[i] for i in row) for row in raw["cell_to_mems"]),
        tuple(ids[i] for i in raw["nn_i"]),
        tuple(ids[i] for i in raw["bflags_mems"]),
        tuple(grid.environment_ids[i] for i in raw["map_mem2ecm"]),
        tuple(grid.environment_ids[i] for i in raw["map_cell2ecm"]),
        config["scale_cell"],
        config["cell_height"],
        config["cell_space"],
        dict(
            native_case=record["name"], cell_parameters=config, seed_manifest=record["seed_binding"]
        ),
    )


def prepared(name="irregular-centroid-aux"):
    record = captured(name)
    return record, geometry.bind_geometry(geometry_spec(record))


def close(actual, expected, *, rtol=6e-12, atol=0):
    np.testing.assert_allclose(actual, np.asarray(expected, float), rtol=rtol, atol=atol)


@pytest.mark.parametrize("raw", cases(), ids=lambda x: x["name"])
def test_native_generation_independent_measures_ownership_and_operators(raw):
    record, binding = prepared(raw["name"])
    k = binding.kernel
    mesh = binding.mesh
    mk = mesh.kernel
    native = record["cells"]
    expected = reference.cell_geometry(record)
    for actual, key in (
        (mesh.centres_m, "cell_centres"),
        (k.membrane_edges_m, "mem_edges_flat"),
        (k.membrane_midpoints_m, "mem_mids_flat"),
        (k.membrane_area_m2, "mem_sa"),
        (k.native_patch_volume_m3, "mem_vol"),
        (k.native_cell_volume_m3, "cell_vol"),
        (k.cell_surface_m2, "cell_sa"),
        (k.owner, "mem_to_cells"),
    ):
        close(actual, native[key], atol=1e-27)
        close(actual, expected[key], atol=1e-27)
    close(k.polygon_cell_volume_m3, expected["polygon_volume_m3"], atol=1e-30)
    close(k.membrane_normal, np.asarray(native["mem_vects_flat"])[:, 2:4], atol=2e-14)
    close(k.membrane_tangent, np.asarray(native["mem_vects_flat"])[:, 4:6], atol=2e-14)
    contact = reference.contacts(expected, raw)
    np.testing.assert_array_equal(k.partner, contact["nn_i"])
    np.testing.assert_array_equal(native["mem_nn"], contact["mem_nn"])
    np.testing.assert_array_equal(np.flatnonzero(k.boundary), contact["bflags_mems"])
    np.testing.assert_array_equal(k.environment_owner, native["map_mem2ecm"])
    close(k.environment_native_weighted_volume_m3, native["true_ecm_vol"], atol=1e-30)
    close(mk.primal_d0, record["mesh"]["delta_tri_0"])
    close(mk.cell_area_m2, record["mesh"]["vor_sa"], atol=1e-26)
    close(mk.lap_closed, native["lapGJ"], atol=3e-3)
    close(mk.source_inverse_closed, native["lapGJinv"], atol=3e-24)
    independent_lap = reference.graph_laplacian(
        record["mesh"]["tri_edges"],
        record["mesh"]["vor_edge_len"],
        record["mesh"]["tri_edge_len"],
        record["mesh"]["vor_sa"],
    )
    close(mk.lap_closed, independent_lap, atol=3e-3)
    probes = record["mesh_probes"]
    close(
        geometry.edge_gradient(probes["probe"], mesh, domain="primal", xp=np),
        probes["grad"],
        atol=3e-8,
    )
    close(
        geometry.mesh_divergence(probes["flux"], mesh, domain="primal", boundary="closed", xp=np),
        probes["div2"],
        atol=3e-8,
    )
    close(
        geometry.mesh_laplacian(probes["probe"], mesh, domain="primal", boundary="closed", xp=np),
        probes["lap2"],
        atol=3e-3,
    )
    close(
        geometry.source_factorized_inverse(
            probes["probe"], mesh, domain="primal", boundary="closed", xp=np
        ),
        probes["lap_inv2"],
        atol=3e-24,
    )
    if mesh.auxiliary:
        close(mk.primal_d1, record["mesh"]["delta_tri_1"])
        close(mk.dual_d0, record["mesh"]["delta_vor_0"])
        close(mk.dual_d1[mk.inner_cell], record["mesh"]["delta_vor_1"])
        dual = probes["dual_probe"]
        for domain, values, flux in (
            ("primal", probes["probe"], probes["flux"]),
            ("dual", dual, probes["flux"]),
        ):
            for bound, num in (("interior_rows", 1), ("closed", 2)):
                prefix = "dual_" if domain == "dual" else ""
                close(
                    geometry.mesh_laplacian(values, mesh, domain=domain, boundary=bound, xp=np),
                    probes[prefix + "lap" + str(num)],
                    atol=3e-3,
                )
                close(
                    geometry.mesh_divergence(flux, mesh, domain=domain, boundary=bound, xp=np),
                    probes[prefix + "div" + str(num)],
                    atol=3e-8,
                )
                close(
                    geometry.source_factorized_inverse(
                        values, mesh, domain=domain, boundary=bound, xp=np
                    ),
                    probes[prefix + "lap_inv" + str(num)],
                    atol=3e-24,
                )
        close(
            geometry.source_xy_gradient(probes["probe"], mesh, xp=np), probes["grad_xy"], atol=3e-8
        )
    cell_expected = reference.cell_probes(expected, record)
    cp = record["cell_probes"]
    edge, vector = geometry.cell_gradient(cp["probe"], binding, domain="cell", xp=np)
    close(edge, cp["gradient"][0], atol=2e-8)
    close(edge, cell_expected["gradient"][0], atol=2e-8)
    close(vector.T, cp["gradient"][1:], atol=2e-8)
    close(geometry.cell_mean(cp["probe"], binding, domain="cell", xp=np), cell_expected["mean"])
    vectors = np.column_stack((cp["fx"], cp["fy"]))
    for closed, key in ((False, "divergence"), (True, "divergence_closed")):
        actual = geometry.cell_divergence(
            vectors, binding, closed=closed, volume_policy="native_radial", xp=np
        )
        close(actual, cp[key], atol=3e-8)
        close(actual, cell_expected[key], atol=3e-8)
    close(
        geometry.circumference_gradient(cp["fx"], binding, domain="membrane", xp=np),
        cp["theta"],
        atol=3e-8,
    )
    grid = binding.grid
    grid_expected = reference.grid_laplacian(grid.shape, grid.delta_m, dict(grid.boundaries))
    close(grid.kernel.laplacian, grid_expected)
    close(grid.kernel.laplacian, record["environment"]["laplacian"])
    close(grid.kernel.pseudoinverse, record["environment"]["pseudoinverse"], atol=3e-23)
    phi = np.cos(np.arange(len(mesh.cell_ids)) + 0.3)
    rhs = geometry.mesh_laplacian(phi, mesh, domain="primal", boundary="closed", xp=np)
    source_solution = geometry.source_factorized_inverse(
        rhs, mesh, domain="primal", boundary="closed", xp=np
    )
    source_residual = (
        geometry.mesh_laplacian(source_solution, mesh, domain="primal", boundary="closed", xp=np)
        - rhs
    )
    evidence(
        raw["name"],
        dict(
            status="passed",
            geometry_identity=binding.identity,
            cells=len(mesh.cell_ids),
            membranes=len(binding.membrane_ids),
            environment=len(grid.environment_ids),
            source_seed_removals=list(mesh.removed_seed_ids),
            maximum_native_vs_polygon_volume_relative_difference=float(
                np.max(np.abs(k.native_cell_volume_m3 / k.polygon_cell_volume_m3 - 1))
            ),
            source_factorized_inverse_relative_residual=float(
                np.linalg.norm(source_residual) / np.linalg.norm(rhs)
            ),
            missing_native_dual_face_steps=list(mesh.missing_dual_face_steps),
            auxiliary=mesh.auxiliary,
            actual_geometry_generation=True,
            physical_state_remapped=False,
        ),
    )


@pytest.mark.parametrize(
    "name",
    [
        "centroid-core",
        "irregular-centroid-aux",
        "irregular-circumcenter-aux",
        "merged-square-aux",
        "directional-refinement-9",
    ],
)
def test_discrete_conservation_nullspace_adjoint_and_contact_measures(name):
    _, binding = prepared(name)
    mesh = binding.mesh
    k = mesh.kernel
    g = binding.kernel
    n = len(mesh.cell_ids)
    scalar = np.sin(np.arange(n) + 0.4)
    flux = np.cos(np.arange(len(mesh.edge_ids)) + 0.6)
    grad = geometry.edge_gradient(scalar, mesh, domain="primal", xp=np)
    div = geometry.mesh_divergence(flux, mesh, domain="primal", boundary="closed", xp=np)
    scale = np.sum(np.abs(div * k.cell_area_m2))
    assert abs(np.dot(div, k.cell_area_m2)) <= 3e-13 * scale
    left = np.dot(scalar * k.cell_area_m2, div)
    right = -np.sum(grad * flux * k.primal_length_m * k.dual_length_m)
    close(left, right, rtol=3e-12, atol=1e-20)
    np.testing.assert_array_equal(
        geometry.edge_gradient(np.ones(n), mesh, domain="primal", xp=np), 0
    )
    np.testing.assert_array_equal(k.primal_d1 @ k.primal_d0, 0)
    assert np.allclose(
        k.cell_area_m2[:, None] * k.lap_closed,
        (k.cell_area_m2[:, None] * k.lap_closed).T,
        rtol=2e-14,
        atol=1e-14,
    )
    lap = geometry.mesh_laplacian(scalar, mesh, domain="primal", boundary="closed", xp=np)
    close(
        -np.dot(scalar * k.cell_area_m2, lap),
        np.sum(grad**2 * k.primal_length_m * k.dual_length_m),
        rtol=3e-12,
    )
    normal_flux = np.sin(np.arange(len(binding.membrane_ids)) + 0.2)
    cell = -geometry.surface_integrals(normal_flux, binding, domain="cell", xp=np)
    env = geometry.surface_integrals(normal_flux, binding, domain="environment", xp=np)
    assert abs(np.sum(cell) + np.sum(env)) <= 3e-14 * (np.sum(np.abs(cell)) + np.sum(np.abs(env)))
    internal = np.zeros(len(binding.membrane_ids))
    for i, j in g.contact_pairs:
        internal[i] = np.sin(i + 0.7)
        internal[j] = -internal[i]
    vectors = internal[:, None] * g.membrane_normal
    for policy, volume in (
        ("native_radial", g.native_cell_volume_m3),
        ("polygon", g.polygon_cell_volume_m3),
    ):
        divergence = geometry.cell_divergence(
            vectors, binding, closed=True, volume_policy=policy, xp=np
        )
        assert abs(np.sum(divergence * volume)) <= 3e-14 * np.sum(np.abs(divergence * volume))


def test_density_poisson_is_compatible_gauged_and_distinct_from_source_factorization():
    record, binding = prepared()
    mesh = binding.mesh
    k = mesh.kernel
    n = len(mesh.cell_ids)
    scalar = np.cos(np.arange(n) + 0.1)
    rhs = geometry.mesh_laplacian(scalar, mesh, domain="primal", boundary="closed", xp=np)
    assert geometry.density_rhs_valid(rhs, mesh, xp=np)
    assert not geometry.density_rhs_valid(np.ones(n), mesh, xp=np)
    assert geometry.density_rhs_valid(np.zeros(n), mesh, xp=np)
    actual = geometry.density_poisson(rhs, mesh, xp=np)
    close(actual, scalar - scalar.mean(), atol=3e-12)
    scale = np.max(np.abs(k.lap_closed))
    matrix = k.lap_closed / scale - np.ones((n, n)) / n
    expected = reference.solve_dense(matrix.tolist(), (rhs / scale).tolist())
    close(actual, expected, atol=4e-12)
    source = geometry.source_factorized_inverse(
        rhs, mesh, domain="primal", boundary="closed", xp=np
    )
    defect = np.linalg.norm(
        geometry.mesh_laplacian(source, mesh, domain="primal", boundary="closed", xp=np) - rhs
    ) / np.linalg.norm(rhs)
    assert defect > 1e-3
    evidence(
        "gauge",
        dict(
            status="passed",
            source_factorized_relative_residual=float(defect),
            density_relative_residual=float(
                np.linalg.norm(k.lap_closed @ actual - rhs) / np.linalg.norm(rhs)
            ),
            potential_arithmetic_mean=float(np.mean(actual)),
            native_case=record["name"],
            policy=(
                "Compatible density RHS, separate Cells pseudoinverse; no silent source projection"
            ),
        ),
    )


@pytest.mark.parametrize("raw", grid_cases(), ids=lambda x: x["name"])
def test_actual_environment_boundary_rows_pseudoinverse_and_reference(raw):
    record = captured(raw["name"])
    grid = geometry.bind_grid(grid_spec(record))
    native = record["environment"]
    close(
        grid.kernel.laplacian,
        reference.grid_laplacian(grid.shape, grid.delta_m, dict(grid.boundaries)),
    )
    close(grid.kernel.pseudoinverse, native["pseudoinverse"], atol=2e-24)
    close(
        geometry.environment_laplacian(native["mode"], grid, xp=np),
        native["mode_laplacian"],
        atol=1e-2,
    )
    scalar = np.sin(np.arange(len(grid.environment_ids)) + 0.2)
    rhs = geometry.environment_laplacian(scalar, grid, xp=np)
    assert geometry.environment_rhs_valid(rhs, grid, xp=np)
    solution = geometry.environment_poisson(rhs, grid, convention="compatible_gauge", xp=np)
    source = geometry.environment_poisson(rhs, grid, convention="native", xp=np)
    close(source, native["native_inverse_probe"]["solution"], atol=1e-2)
    if all(v == "flux" for v in grid.boundaries.values()):
        close(solution, scalar - scalar.mean(), atol=2e-11)
        close(grid.kernel.laplacian @ np.ones(len(scalar)), 0, atol=0)
    else:
        close(solution, scalar, atol=2e-11)
        assert grid.kernel.laplacian[0, 0] == 1 / grid.delta_m**2
    evidence(
        raw["name"],
        dict(
            status="passed",
            shape=list(grid.shape),
            relative_mode_error=native["relative_mode_error"],
            gauge="Arithmetic mean zero for all flux; none for fixed rows",
            source_value_rows="Identity divided by delta^2; caller scales boundary RHS",
            native_inverse_relative_residual=native["native_inverse_probe"]["relative_residual"],
            native_inverse_arithmetic_mean=native["native_inverse_probe"]["arithmetic_mean"],
            compatible_inverse_relative_residual=float(
                np.linalg.norm(grid.kernel.laplacian @ solution - rhs) / np.linalg.norm(rhs)
            ),
        ),
    )


def test_source_boundary_labels_are_interior_output_rows_and_corner_precedence():
    record, binding = prepared("mixed-environment-corners")
    mesh = binding.mesh
    # Core-only mesh rejects a helper that native attempts without aux data.
    with pytest.raises(ValueError, match="auxiliary"):
        geometry.mesh_laplacian(
            np.ones(len(mesh.cell_ids)), mesh, domain="primal", boundary="interior_rows", xp=np
        )
    grid = binding.grid
    matrix = grid.kernel.laplacian
    ny, nx = grid.shape
    assert matrix[0, 0] < 0  # SW takes South flux.
    assert matrix[nx - 1, nx - 1] > 0  # SE takes East value.
    assert matrix[(ny - 1) * nx, (ny - 1) * nx] > 0  # NW takes North value.
    assert record["environment"]["boundaries"]["W"] == "flux"
    _, other = prepared("centroid-aux")
    k = other.mesh.kernel
    np.testing.assert_array_equal(
        k.lap_interior[np.setdiff1d(np.arange(len(other.mesh.cell_ids)), k.inner_cell)], 0
    )
    # A constant still has zero derivative: native btype=1 does not impose
    # a nonzero/zero potential boundary condition on the input field.
    np.testing.assert_array_equal(
        geometry.mesh_laplacian(
            np.ones(len(other.mesh.cell_ids)),
            other.mesh,
            domain="primal",
            boundary="interior_rows",
            xp=np,
        ),
        0,
    )


def test_geometry_measures_are_distinct_and_no_silent_seed_or_owner_remap():
    record, binding = prepared()
    k = binding.kernel
    relative = np.abs(k.native_cell_volume_m3 / k.polygon_cell_volume_m3 - 1)
    assert max(relative) > 1e-4
    assert not np.allclose(record["mesh"]["tri_verts"], binding.mesh.centres_m, rtol=0, atol=1e-12)
    duplicate = captured("duplicate-seed-removal")
    spec = mesh_spec(duplicate)
    assert len(spec.removed_seed_ids) == 2
    with pytest.raises(ValueError, match="partition"):
        geometry.bind_mesh(replace(spec, removed_seed_ids=()))
    retained = geometry.bind_mesh(spec)
    assert set(retained.source_seed_ids) == set(retained.cell_ids) | set(retained.removed_seed_ids)
    assert not set(retained.cell_ids) & set(retained.removed_seed_ids)
    single = captured("native-single-preset-seed17")
    assert len(single["mesh"]["tri_verts"]) == 7
    assert single["rng_before"] != single["rng_after_constructor"]
    assert single["rng_after_constructor"] == single["rng_after"]
    assert record["rng_before"] == record["rng_after"]


def test_declared_disconnected_components_have_separate_compatibility_and_gauges():
    record = captured("centroid-core")
    first = mesh_spec(record)

    def second_ids(values):
        return tuple("second:" + v for v in values)

    def second_rows(rows):
        return tuple(second_ids(row) for row in rows)

    spec = replace(
        first,
        cell_ids=first.cell_ids + second_ids(first.cell_ids),
        edge_ids=first.edge_ids + second_ids(first.edge_ids),
        face_ids=first.face_ids + second_ids(first.face_ids),
        dual_vertex_ids=first.dual_vertex_ids + second_ids(first.dual_vertex_ids),
        primal_points_m=np.concatenate((first.primal_points_m, first.primal_points_m + 1e-4)),
        dual_points_m=np.concatenate((first.dual_points_m, first.dual_points_m + 1e-4)),
        primal_edges=first.primal_edges + second_rows(first.primal_edges),
        dual_edges=first.dual_edges + second_rows(first.dual_edges),
        primal_faces=first.primal_faces + second_rows(first.primal_faces),
        dual_cells=first.dual_cells + second_rows(first.dual_cells),
        boundary_cell_ids=first.boundary_cell_ids + second_ids(first.boundary_cell_ids),
        inner_dual_vertex_ids=first.inner_dual_vertex_ids + second_ids(first.inner_dual_vertex_ids),
        dual_control_area_m2=np.tile(first.dual_control_area_m2, 2),
        dual_control_face_ids=first.dual_control_face_ids + second_ids(first.dual_control_face_ids),
        source_seed_ids=first.source_seed_ids + second_ids(first.source_seed_ids),
        provenance=dict(
            operation="Explicit disconnected topology composition, not native Delaunay generation"
        ),
    )
    mesh = geometry.bind_mesh(spec)
    n = len(first.cell_ids)
    assert mesh.kernel.components.shape == (2, 2 * n)
    # Global balance alone cannot certify the independent component nullspaces.
    invalid = np.r_[np.ones(n), -np.ones(n)]
    assert not geometry.density_rhs_valid(invalid, mesh, xp=np)
    phi = np.sin(np.arange(2 * n) + 0.3)
    rhs = geometry.mesh_laplacian(phi, mesh, domain="primal", boundary="closed", xp=np)
    assert geometry.density_rhs_valid(rhs, mesh, xp=np)
    result = geometry.density_poisson(rhs, mesh, xp=np)
    close(result[:n], phi[:n] - phi[:n].mean(), atol=4e-11)
    close(result[n:], phi[n:] - phi[n:].mean(), atol=4e-11)
    evidence(
        "disconnected-gauges",
        dict(
            status="passed",
            components=2,
            global_balance_insufficient=True,
            policy="Declared topology composition only; per-component gauge",
        ),
    )


def test_geometry_manifest_immutable_axes_stale_rejection_and_membrane_axis_permutation():
    record, binding = prepared()
    manifest = geometry.geometry_manifest(binding)
    geometry.validate_geometry_manifest(json.loads(json.dumps(manifest)), binding)
    stale = deepcopy(manifest)
    stale["identity"] = "wrong"
    with pytest.raises(ValueError, match="Stale"):
        geometry.validate_geometry_manifest(stale, binding)
    for array in (*binding.kernel, binding.mesh.centres_m, binding.grid.coordinates_m):
        assert not array.flags.writeable
    with pytest.raises(ValueError):
        binding.kernel.owner[0] = 1
    spec = geometry_spec(record)
    permuted = geometry.bind_geometry(
        replace(
            spec,
            membrane_ids=tuple(reversed(spec.membrane_ids)),
            partner_membrane_ids=tuple(reversed(spec.partner_membrane_ids)),
            membrane_environment_ids=tuple(reversed(spec.membrane_environment_ids)),
        )
    )
    np.testing.assert_array_equal(permuted.kernel.owner, binding.kernel.owner[::-1])
    close(permuted.kernel.membrane_area_m2, binding.kernel.membrane_area_m2[::-1])
    close(permuted.kernel.native_cell_volume_m3, binding.kernel.native_cell_volume_m3)
    assert permuted.identity != binding.identity
    with pytest.raises(ValueError):
        geometry.validate_geometry_manifest(manifest, permuted)


@pytest.mark.parametrize(
    "variant",
    (
        "duplicate-cell-id",
        "coincident-primal",
        "bad-face-edge",
        "reversed-cell",
        "negative-dual-area",
        "missing-seed-ledger",
        "boolean-points",
        "wrong-grid-order",
        "nonuniform-grid",
        "bad-boundary-label",
        "wrong-membrane-count",
        "wrong-cell-partition",
        "nonreciprocal-contact",
        "contact-as-boundary",
        "wrong-environment-map",
        "zero-height",
        "zero-gap",
        "zero-shrink",
        "full-shrink",
        "nan-height",
    ),
)
def test_invalid_geometries_fail_before_numerical_binding(variant):
    record = captured("irregular-centroid-aux")
    ms, gs = mesh_spec(record), grid_spec(record)
    if variant == "duplicate-cell-id":
        ms = replace(ms, cell_ids=(ms.cell_ids[0],) * len(ms.cell_ids))
    elif variant == "coincident-primal":
        points = ms.primal_points_m.copy()
        points[0] = points[1]
        ms = replace(ms, primal_points_m=points)
    elif variant == "bad-face-edge":
        ms = replace(ms, primal_edges=ms.primal_edges[:-1])
    elif variant == "reversed-cell":
        ms = replace(ms, dual_cells=(tuple(reversed(ms.dual_cells[0])), *ms.dual_cells[1:]))
    elif variant == "negative-dual-area":
        ms = replace(ms, dual_control_area_m2=-ms.dual_control_area_m2)
    elif variant == "missing-seed-ledger":
        ms = replace(ms, source_seed_ids=(*ms.source_seed_ids, "silent-owner"))
    elif variant == "boolean-points":
        ms = replace(ms, primal_points_m=ms.primal_points_m.astype(bool))
    elif variant == "wrong-grid-order":
        gs = replace(gs, coordinates_m=gs.coordinates_m[::-1])
    elif variant == "nonuniform-grid":
        gs = replace(gs, delta_m=gs.delta_m * 1.1)
    elif variant == "bad-boundary-label":
        gs = replace(gs, boundaries=dict(N="periodic", S="flux", E="flux", W="flux"))
    if variant in (
        "duplicate-cell-id",
        "coincident-primal",
        "bad-face-edge",
        "reversed-cell",
        "negative-dual-area",
        "missing-seed-ledger",
        "boolean-points",
    ):
        with pytest.raises(ValueError):
            geometry.bind_mesh(ms)
        return
    if variant in ("wrong-grid-order", "nonuniform-grid", "bad-boundary-label"):
        with pytest.raises(ValueError):
            geometry.bind_grid(gs)
        return
    spec = geometry_spec(record)
    if variant == "wrong-membrane-count":
        spec = replace(spec, membrane_ids=spec.membrane_ids[:-1])
    elif variant == "wrong-cell-partition":
        spec = replace(
            spec, cell_membrane_ids=(spec.cell_membrane_ids[0],) * len(spec.cell_membrane_ids)
        )
    elif variant == "nonreciprocal-contact":
        pair = list(spec.partner_membrane_ids)
        pair[0] = spec.membrane_ids[1]
        spec = replace(spec, partner_membrane_ids=tuple(pair))
    elif variant == "contact-as-boundary":
        index = next(
            i for i, v in enumerate(spec.partner_membrane_ids) if v != spec.membrane_ids[i]
        )
        spec = replace(spec, boundary_membrane_ids=(spec.membrane_ids[index],))
    elif variant == "wrong-environment-map":
        spec = replace(
            spec, membrane_environment_ids=(spec.grid.environment_ids[-1],) * len(spec.membrane_ids)
        )
    elif variant == "zero-height":
        spec = replace(spec, height_m=0)
    elif variant == "zero-gap":
        spec = replace(spec, gap_m=0)
    elif variant == "zero-shrink":
        spec = replace(spec, shrink_factor=0)
    elif variant == "full-shrink":
        spec = replace(spec, shrink_factor=1)
    else:
        spec = replace(spec, height_m=np.nan)
    with pytest.raises(ValueError):
        geometry.bind_geometry(spec)


@pytest.mark.parametrize("raw", limitations(), ids=lambda x: x["name"])
def test_native_degeneracy_and_operator_failures_remain_recorded(raw):
    record = captured(raw["name"])
    expected = {
        "too-few-seeds": "QhullError",
        "collinear-seeds": "QhullError",
        "unmerged-cocircular-dual": "AssertionError",
        "alpha-removes-all": "ValueError",
        "zero-cell-scale": "IndexError",
        "zero-height": "LinAlgError",
        "core-missing-aux": "AttributeError",
        "unsupported-gradient-domain": "BetseMathMeshException",
    }
    if raw["name"] in expected:
        assert record["status"] == "captured_failure"
        assert record["failure_type"] == expected[raw["name"]]
        assert record["traceback"]
    else:
        assert record["status"] == "captured_limitation"
    if raw["name"] == "nonintegral-grid-aspect":
        with pytest.raises(ValueError, match="uniform metric"):
            geometry.bind_grid(grid_spec(record))
    elif raw["name"] == "membrane-normal-y-source-bug":
        bug = record["normal_bug"]
        assert not np.allclose(bug["actual"], bug["explicitly_projected"])
    elif raw["name"] in ("duplicate-seed-removal", "close-seed-removal"):
        assert record["seed_binding"]["removed_ids"]


def test_native_and_environment_spatial_refinement_limits():
    names = ["centroid-core", "directional-refinement-5", "directional-refinement-9"]
    rows = [captured(name)["mesh_probes"]["directional_wave"] for name in names]
    grid = [
        captured(f"environment-refinement-{n}")["environment"]["relative_mode_error"]
        for n in (4, 8, 16)
    ]
    order = [
        float(np.log(rows[i]["relative_rms_error"] / rows[i + 1]["relative_rms_error"]) / np.log(2))
        for i in range(2)
    ]
    grid_order = [float(np.log(grid[i] / grid[i + 1]) / np.log(2)) for i in range(2)]
    assert all(v > 1.7 for v in order) and all(v > 1.9 for v in grid_order)
    evidence(
        "refinement",
        dict(
            status="passed",
            native_directional=rows,
            directional_orders=order,
            environment_relative_mode_errors=grid,
            environment_orders=grid_order,
            scope=(
                "Edge-directional sine difference and uniform all-flux grid eigenmode; "
                "no centroid-dual continuum Laplacian convergence claim"
            ),
        ),
    )


def test_existing_profile_cut_and_deformation_interfaces_use_declared_geometry_only():
    from cells.processes import betse_deformation, betse_tissue_cut, betse_tissue_profiles

    _, binding = prepared()
    mesh = binding.mesh
    k = binding.kernel
    mk = mesh.kernel
    profile = betse_tissue_profiles.validate_layout(
        betse_tissue_profiles.Layout(
            mesh.cell_ids,
            binding.membrane_ids,
            binding.grid.environment_ids,
            tuple(mesh.cell_ids[i] for i in k.owner),
            tuple(binding.grid.environment_ids[i] for i in k.environment_owner),
            binding.cell_membrane_ids,
            mesh.centres_m,
            binding.grid.bounds_m,
            None,
        )
    )
    assert profile.cell_ids == mesh.cell_ids
    pairs = k.contact_pairs
    # Field edges and physical contact edges remain separate declared domains.
    top = betse_tissue_cut.validate_topology(
        betse_tissue_cut.Topology(
            mesh.cell_ids,
            binding.membrane_ids,
            tuple(f"contact:{i}" for i in range(len(pairs))),
            binding.grid.environment_ids,
            k.owner,
            k.environment_owner,
            k.owner[pairs],
            pairs,
            np.ones(len(pairs), bool),
        )
    )
    assert all(top.edge_is_contact)
    # Source uses -1 m for self-paired boundary lengths. Difference rows there
    # are identically zero; explicitly replace only that sentinel with 1 m to
    # satisfy the frozen binder, retaining identical numerical operators.
    neighbor = np.column_stack((k.owner, k.owner[k.partner]))
    delta = mesh.centres_m[neighbor[:, 1]] - mesh.centres_m[neighbor[:, 0]]
    length = np.linalg.norm(delta, axis=-1)
    safe = np.where(length > 0, length, 1.0)
    curl = np.divide(delta, safe[:, None])
    op = betse_deformation.bind_operators(
        neighbor,
        safe,
        k.membrane_normal,
        curl,
        k.cell_sum,
        mk.primal_d0,
        np.linalg.pinv(mk.primal_d0),
        mk.dual_length_m,
        mk.primal_length_m,
        mk.cell_area_m2,
    )
    close(op.laplacian, mk.lap_closed, atol=3e-3)
    close(op.laplacian_inverse, mk.source_inverse_closed, atol=3e-24)
    evidence(
        "existing-interface-binding",
        dict(
            status="passed",
            profile_layout_identity=betse_tissue_profiles.layout_identity(profile),
            cut_topology_identity=betse_tissue_cut.layout_identity(top),
            geometry_identity=binding.identity,
            self_boundary_denominator_policy=(
                "Explicit 1 m neutral sentinel for zero difference rows"
            ),
            cut_executed=False,
            physical_state_remapped=False,
            deformation_evolved=False,
        ),
    )


def test_source_authentication_and_reference_independence():
    folder = os.environ.get("CELLS_BETSE_GEOMETRY_NATIVE_CAPTURE")
    if not folder:
        pytest.skip("Bounded wrapper supplies native geometry capture")
    path = Path(folder)
    manifest = json.loads((path / "source-manifest.json").read_text())
    assert manifest["geometry_cases"] == len(cases()) == 12
    assert manifest["grid_cases"] == len(grid_cases()) == 4
    assert manifest["limitations"] == len(limitations()) == 12
    assert not manifest["production_cells_imported"] and not manifest["jax_imported"]
    assert manifest["geometry_generation_executed"] and not manifest["solver_or_cut_executed"]
    for rel, digest in PROTOCOL["native_source"]["source_sha256"].items():
        assert hashlib.sha256((path / "upstream" / rel).read_bytes()).hexdigest() == digest
    source = (ROOT / "validation/geometry/betse_geometry_reference.py").read_text()
    assert (
        "import numpy" not in source and "import jax" not in source and "from cells" not in source
    )


def test_explicit_domain_shape_and_nonfinite_rejection():
    _, binding = prepared()
    mesh = binding.mesh
    with pytest.raises(ValueError):
        geometry.edge_gradient(np.ones(len(mesh.cell_ids)), mesh, domain="cell", xp=np)
    with pytest.raises(ValueError):
        geometry.cell_gradient(np.ones(len(mesh.cell_ids)), binding, domain="membrane", xp=np)
    with pytest.raises(ValueError):
        geometry.cell_mean(np.ones(len(mesh.cell_ids)), binding, domain="membrane", xp=np)
    with pytest.raises(ValueError):
        geometry.cell_divergence(
            np.ones((len(binding.membrane_ids), 2)),
            binding,
            closed=False,
            volume_policy="automatic",
            xp=np,
        )
    assert not geometry.density_rhs_valid(np.full(len(mesh.cell_ids), np.nan), mesh, xp=np)
    assert not geometry.density_rhs_valid(np.ones((len(mesh.cell_ids), 1)), mesh, xp=np)
    with pytest.raises(ValueError):
        geometry.polygon_measure(np.array([[0, 0], [1, 1], [0, 1], [1, 0]]))
    assert not geometry.field_valid(
        np.full(len(mesh.cell_ids), np.nan), binding, domain="cell", xp=np
    )
    assert not geometry.field_valid(
        np.ones(len(mesh.cell_ids), bool), binding, domain="cell", xp=np
    )
    assert geometry.field_valid(
        np.ones((len(binding.membrane_ids), 2)), binding, domain="membrane", vector=True, xp=np
    )
    with pytest.raises(ValueError):
        geometry.surface_integrals(1.0, binding, domain="cell", xp=np)
    with pytest.raises(ValueError):
        geometry.mesh_divergence(True, mesh, domain="primal", boundary="closed", xp=np)


def test_cpu_jax_geometry_operators_batching_and_conservation():
    import jax
    import jax.numpy as jnp

    _, binding = prepared()
    mesh = binding.mesh
    assert jax.config.x64_enabled and all(d.platform == "cpu" for d in jax.devices())
    fields = np.stack(
        (np.sin(np.arange(len(mesh.cell_ids))), np.cos(np.arange(len(mesh.cell_ids))))
    )
    run = jax.jit(
        lambda value: geometry.mesh_laplacian(value, mesh, domain="primal", boundary="closed")
    )
    close(
        run(jnp.asarray(fields)),
        geometry.mesh_laplacian(fields, mesh, domain="primal", boundary="closed", xp=np),
        atol=3e-3,
    )
    flux = jnp.sin(jnp.arange(len(binding.membrane_ids)) + 0.3)

    def transfers(value):
        return (
            -geometry.surface_integrals(value, binding, domain="cell"),
            geometry.surface_integrals(value, binding, domain="environment"),
        )

    cell, env = jax.jit(transfers)(flux)
    assert abs(float(jnp.sum(cell) + jnp.sum(env))) <= 3e-14 * float(
        jnp.sum(jnp.abs(cell)) + jnp.sum(jnp.abs(env))
    )
    vector = np.stack(
        (
            np.column_stack(
                (
                    np.cos(np.arange(len(binding.membrane_ids))),
                    np.sin(np.arange(len(binding.membrane_ids))),
                )
            ),
        )
        * 2
    )
    div = jax.jit(
        lambda v: geometry.cell_divergence(v, binding, closed=True, volume_policy="native_radial")
    )(jnp.asarray(vector))
    close(
        div,
        geometry.cell_divergence(
            vector, binding, closed=True, volume_policy="native_radial", xp=np
        ),
        atol=3e-8,
    )


def test_cpu_jax_auxiliary_and_environment_operators():
    import jax
    import jax.numpy as jnp

    record, binding = prepared()
    mesh = binding.mesh
    dual = jnp.asarray(record["mesh_probes"]["dual_probe"])
    actual = jax.jit(
        lambda x: geometry.mesh_laplacian(x, mesh, domain="dual", boundary="interior_rows")
    )(dual)
    close(actual, record["mesh_probes"]["dual_lap1"], atol=3e-3)
    value = jnp.asarray(record["mesh_probes"]["probe"])
    close(
        jax.jit(lambda x: geometry.source_xy_gradient(x, mesh))(value),
        record["mesh_probes"]["grad_xy"],
        atol=3e-8,
    )
    grid = binding.grid
    mode = jnp.asarray(record["environment"]["mode"])
    lap = jax.jit(lambda x: geometry.environment_laplacian(x, grid))(mode)
    close(lap, record["environment"]["mode_laplacian"], atol=3e-3)
    reconstructed = jax.jit(
        lambda x: geometry.environment_poisson(x, grid, convention="compatible_gauge")
    )(lap)
    close(reconstructed, np.asarray(mode) - float(jnp.mean(mode)), atol=3e-12)


def test_cpu_jax_gauge_invalid_world_isolation_and_exact_repeat():
    import jax
    import jax.numpy as jnp

    _, binding = prepared()
    mesh = binding.mesh
    scalar = np.cos(np.arange(len(mesh.cell_ids)) + 0.1)
    rhs = geometry.mesh_laplacian(scalar, mesh, domain="primal", boundary="closed", xp=np)
    worlds = np.stack((rhs, np.ones_like(rhs), rhs))
    worlds[1, 0] = np.nan
    valid = jax.jit(jax.vmap(lambda x: geometry.density_rhs_valid(x, mesh)))(jnp.asarray(worlds))
    np.testing.assert_array_equal(valid, [True, False, True])
    solve = jax.jit(lambda x: geometry.density_poisson(x, mesh))
    first = solve(jnp.asarray(rhs))
    second = solve(jnp.asarray(rhs))
    np.testing.assert_array_equal(first, second)
    close(first, scalar - scalar.mean(), atol=3e-12)
    evidence(
        "jax-gauge",
        dict(
            status="passed",
            valid_worlds=[True, False, True],
            exact_repeated_solve=True,
            scope="Static geometry/operator buffers; no trajectory/restart or checkpoint claim",
        ),
    )


def test_cpu_jax_differentiable_incidence_and_surface_transfer():
    import jax
    import jax.numpy as jnp

    _, binding = prepared()
    mesh = binding.mesh
    field = jnp.sin(jnp.arange(len(mesh.cell_ids)) + 0.1)
    jac = jax.jit(jax.jacfwd(lambda x: geometry.edge_gradient(x, mesh, domain="primal")))(field)
    close(jac, mesh.kernel.primal_d0 / mesh.kernel.primal_length_m[:, None])
    flux = jnp.cos(jnp.arange(len(binding.membrane_ids)))

    def total(x):
        return jnp.sum(geometry.surface_integrals(x, binding, domain="cell"))

    derivative = jax.jit(jax.grad(total))(flux)
    close(derivative, binding.kernel.membrane_area_m2)
    evidence(
        "jax-derivatives",
        dict(
            status="passed",
            incidence_jacobian_shape=list(jac.shape),
            surface_transfer_gradient=(
                "Declared membrane areas, no physical geometry differentiation"
            ),
        ),
    )
