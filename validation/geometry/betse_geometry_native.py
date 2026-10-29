"""Authenticated actual native small-mesh construction and operator captures."""

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import shutil
import subprocess
import sys
import traceback
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.geometry.betse_geometry_fixtures import UNIT, cases, grid_cases, limitations

PROTOCOL = Path(__file__).with_name("betse_geometry_protocol.json")


def serial(value):
    if isinstance(value, np.ndarray):
        return serial(value.tolist())
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    return value


def write(path, value):
    path.write_text(json.dumps(serial(value), indent=2, allow_nan=False) + "\n")


def fields(obj, names):
    return {key: serial(getattr(obj, key)) for key in names.split() if hasattr(obj, key)}


def grid_capture(grid, bound):
    matrix, inverse = grid.makeLaplacian(bound)
    x, y = grid.xy_cents.T
    lx, ly = grid.xmax - grid.xmin, grid.ymax - grid.ymin
    mode = np.cos(np.pi * (x - grid.xmin) / lx) * np.cos(np.pi * (y - grid.ymin) / ly)
    eigen = -((np.pi / lx) ** 2 + (np.pi / ly) ** 2)
    applied = matrix @ mode
    scalar = np.sin(np.arange(len(mode)) + 0.2)
    rhs = matrix @ scalar
    solution = inverse @ rhs
    return dict(
        **fields(
            grid, "delta grid_nx grid_ny cents_shape xy_cents map_ij2k_cents xy_verts u_pts v_pts"
        ),
        boundaries=bound,
        laplacian=matrix,
        pseudoinverse=inverse,
        mode=mode,
        mode_laplacian=applied,
        continuum_eigenvalue=eigen,
        relative_mode_error=float(
            np.linalg.norm(applied - eigen * mode) / np.linalg.norm(eigen * mode)
        ),
        native_inverse_probe=dict(
            scalar=scalar,
            rhs=rhs,
            solution=solution,
            relative_residual=float(np.linalg.norm(matrix @ solution - rhs) / np.linalg.norm(rhs)),
            arithmetic_mean=float(np.mean(solution)),
        ),
    )


def mesh_capture(mesh):
    return fields(
        mesh,
        "tri_verts tri_cells tri_edges tri_mids tri_edge_len tri_tang "
        "tri_sa tri_sa_o tri_cents tri_ccents vor_verts vor_cells vor_edges "
        "vor_mids vor_edge_len vor_tang vor_sa vor_cents vcell_verts "
        "bflags_tverts bflags_tedges inner_tvert_i inner_tedge_i "
        "bflags_vverts bflags_vedges inner_vvert_i "
        "delta_tri_0 delta_tri_0_inv delta_tri_1 delta_tri_1_inv "
        "delta_vor_0 delta_vor_0_inv delta_vor_1 delta_vor_1_inv",
    )


def mesh_probes(mesh):
    x, y = mesh.tri_verts.T
    probe = x / UNIT + 2 * y / UNIT + 0.1 * (x / UNIT) ** 2
    flux = np.sin(np.arange(mesh.n_tedges) + 0.3)
    result = dict(
        probe=probe,
        flux=flux,
        grad=mesh.grad(probe),
        grad_uv=mesh.grad_uv(probe),
        div2=mesh.div(flux, btype=2),
        lap2=mesh.lap(probe, btype=2),
        lap_inv2=mesh.lap_inv(probe, btype=2),
        verts_to_mids=mesh.verts_to_mids(probe),
        mids_to_verts=mesh.mids_to_verts(flux),
    )
    wave = np.sin(0.7 * x / UNIT + 0.4 * y / UNIT)
    mid = mesh.tri_mids
    true = (
        np.cos(0.7 * mid[:, 0] / UNIT + 0.4 * mid[:, 1] / UNIT)
        * (0.7 * mesh.tri_tang[:, 0] + 0.4 * mesh.tri_tang[:, 1])
        / UNIT
    )
    error = mesh.grad(wave) - true
    result["directional_wave"] = dict(
        max_edge_m=float(max(mesh.tri_edge_len)),
        relative_rms_error=float(np.linalg.norm(error) / np.linalg.norm(true)),
    )
    if mesh.make_all_operators:
        dual = mesh.vor_verts[:, 0] / UNIT - 0.4 * mesh.vor_verts[:, 1] / UNIT
        result.update(
            lap1=mesh.lap(probe, btype=1),
            div1=mesh.div(flux, btype=1),
            grad_xy=mesh.grad_xy(probe),
            dual_probe=dual,
            dual_grad=mesh.grad(dual, gtype="vor"),
            dual_div1=mesh.div(flux, gtype="vor", btype=1),
            dual_div2=mesh.div(flux, gtype="vor", btype=2),
            dual_lap1=mesh.lap(dual, gtype="vor", btype=1),
            dual_lap2=mesh.lap(dual, gtype="vor", btype=2),
            lap_inv1=mesh.lap_inv(probe, btype=1),
            dual_lap_inv1=mesh.lap_inv(dual, gtype="vor", btype=1),
            dual_lap_inv2=mesh.lap_inv(dual, gtype="vor", btype=2),
        )
    return result


def capture_case(raw, output, mesh_class, cells_class, limited=False):
    record = dict(name=raw["name"], input=raw, status="capturing", last_step="initializing")
    write(output / (raw["name"] + ".json"), record)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            np.random.seed(raw["seed"])
            record["rng_before"] = serial(np.random.get_state())
            points = raw["seed_points_m"]
            mesh = mesh_class(
                seed_points=None if points is None else np.asarray(points, float), **raw["mesh"]
            )
            record["constructed_seed_points_m"] = serial(mesh.tri_verts.copy())
            record["rng_after_constructor"] = serial(np.random.get_state())
            record["last_step"] = "mesh.init_mesh"
            mesh.init_mesh()
            record["mesh"] = mesh_capture(mesh)
            # tri_sa_o repeats a reference face area at dual vertices. Bind an
            # explicit compatible source face; ties with identical area are
            # retained as candidates rather than asserting a physical dual cell.
            reference_points = mesh.tri_cents if raw["mesh"]["use_centroids"] else mesh.tri_ccents
            owners = []
            for point, area in zip(mesh.vor_verts, mesh.tri_sa_o, strict=True):
                candidates = []
                for face, centre in enumerate(reference_points):
                    positions = [centre]
                    for edge in mesh.bflags_tedges:
                        if face in mesh.tedges_to_tcell[edge]:
                            mid = mesh.tri_mids[edge]
                            positions.append(mid + (mid - centre))
                    if mesh.tri_sa[face] == area and any(
                        np.array_equal(point, pos) for pos in positions
                    ):
                        candidates.append(face)
                assert candidates, "Unbound native repeated reference control area"
                owners.append(candidates)
            record["dual_control_face_candidates"] = owners
            seed_ids = raw["seed_ids"]
            before = record["constructed_seed_points_m"]
            if seed_ids is None:
                seed_ids = [f"native-seed{raw['seed']}:{i}" for i in range(len(before))]
            matches = [
                [seed_ids[i] for i, point in enumerate(before) if point == list(vertex)]
                for vertex in mesh.tri_verts
            ]
            record["seed_binding"] = dict(
                original_ids=seed_ids,
                retained_matches=matches,
                removed_ids=[v for v in seed_ids if not any(v in row for row in matches)],
                policy="Exact source coordinate equality within this captured generation only",
            )
            record["last_step"] = "mesh probes"
            record["mesh_probes"] = serial(mesh_probes(mesh))
            p = SimpleNamespace(**raw["cell"])
            # The pinned initializer has only `pass`; normalized parameters do
            # not satisfy its package-level beartype Parameters annotation.
            cells = object.__new__(cells_class)
            record["empty_cells_initializer_bypassed"] = True
            cells.mesh = mesh
            cells.ecm_verts = mesh.vcell_verts
            cells.ecm_verts_unique = mesh.vor_verts
            cells.xmin, cells.xmax, cells.ymin, cells.ymax = raw["bounds_m"]
            cells.centre = [(cells.xmin + cells.xmax) / 2, (cells.ymin + cells.ymax) / 2]
            cells.cell_index(p)
            record["voronoi_volume_before_patch_m3"] = serial(cells.cell_vol.copy())
            for name in (
                "cellVerts",
                "cellMatrices",
                "cell_vols",
                "mem_processing",
                "near_neigh",
                "calc_gj_vects",
                "makeECM",
                "environment",
                "graphLaplacian",
                "cellDivM",
            ):
                record["last_step"] = name
                getattr(cells, name)(p)
            record["cells"] = fields(
                cells,
                "cell_centres cell_verts cell_vol cell_sa mem_sa mem_vol "
                "mem_mids_flat mem_edges_flat mem_vects_flat mem_to_cells cell_to_mems "
                "R_rads rads mem_nn nn_i cell_nn_i cell_nn num_nn bflags_mems bflags_cells "
                "nn_len nn_tx nn_ty cell_nn_tx cell_nn_ty ecm_points mem_to_ecm cell_to_ecm "
                "map_mem2ecm map_cell2ecm map_ecm2mem true_ecm_vol ecm_vol ecm_sa "
                "memSa_per_envSquare mems_per_envSquare cell2env_corrF "
                "M_sum_mems M_sum_mems_inv gradTheta radial_len M_divmap_mem2ecm "
                "lapGJ lapGJinv geom_weight divCell_inv delta X Y xypts map_ij2k "
                "bBot_k bTop_k bL_k bR_k ecm_bound_k ecm_allbound_k",
            )
            record["environment"] = serial(
                grid_capture(cells.grid_obj, raw["environment_boundaries"])
            )
            probe = np.arange(len(cells.cell_i), dtype=float) ** 2 + 0.3
            fx = np.cos(np.arange(len(cells.mem_i)) + 0.2)
            fy = np.sin(np.arange(len(cells.mem_i)) + 0.7)
            record["cell_probes"] = serial(
                dict(
                    probe=probe,
                    fx=fx,
                    fy=fy,
                    gradient=cells.gradient(probe),
                    mean=cells.meanval(probe),
                    divergence=cells.div(fx, fy),
                    divergence_closed=cells.div(fx, fy, cbound=True),
                    average_vector=cells.average_vector(fx, fy),
                    theta=cells.gradTheta @ fx,
                )
            )
            if raw.get("probe_failure") == "aux":
                mesh.lap(probe, btype=1)
            elif raw.get("probe_failure") == "gtype":
                mesh.grad(probe, gtype="cell")
            elif raw.get("probe_failure") == "normal-y":
                record["normal_bug"] = serial(
                    dict(
                        actual=cells.mem_normal_component(fx, fy),
                        explicitly_projected=fx * cells.mem_vects_flat[:, 2]
                        + fy * cells.mem_vects_flat[:, 3],
                    )
                )
            record["rng_after"] = serial(np.random.get_state())
            record["status"] = "captured_limitation" if limited else "passed"
        except Exception as error:
            record.update(
                status="captured_failure" if limited else "unexpected_failure",
                failure_type=type(error).__name__,
                failure=str(error),
                traceback=traceback.format_exc(),
            )
    record["warnings"] = [
        dict(category=w.category.__name__, message=str(w.message)) for w in caught
    ]
    write(output / (raw["name"] + ".json"), record)
    if not limited:
        assert record["status"] == "passed", (raw["name"], record.get("failure"))
    return dict(
        name=raw["name"], status=record["status"], path=str(output / (raw["name"] + ".json"))
    )


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    contract = json.loads(PROTOCOL.read_text())
    source = contract["native_source"]
    checkout = Path(source["checkout"])
    installed = Path(source["installed_package"]).parent
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == source["revision"]
    manifest = dict(
        status="capturing",
        revision=revision,
        version=source["version"],
        files={},
        executed_bodies={},
        records=[],
        full_simulator=False,
        versions={name: importlib.metadata.version(name) for name in ("numpy", "scipy", "betse")},
    )
    write(output / "source-manifest.json", manifest)
    for relative, expected in source["source_sha256"].items():
        content = (installed / relative).read_bytes()
        dest = output / "upstream" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, dest)
        assert content == (checkout / relative).read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        assert actual == expected
        manifest["files"][relative] = dict(sha256=actual, checkout_match=True)
    from betse.science.cells import Cells
    from betse.science.math.finitediff import FiniteDiffSolver
    from betse.science.math.mesh import DECMesh

    for cls in (Cells, DECMesh, FiniteDiffSolver):
        location = Path(inspect.getfile(cls)).resolve()
        assert location.is_relative_to(installed)
        relative = str(location.relative_to(installed))
        assert relative in manifest["files"]
        manifest["executed_bodies"][cls.__name__] = dict(
            source=relative, first_line=inspect.getsourcelines(cls)[1], actual_import=True
        )
    for raw in cases():
        manifest["records"].append(capture_case(raw, output, DECMesh, Cells))
        write(output / "source-manifest.json", manifest)
    for raw in limitations():
        manifest["records"].append(capture_case(raw, output, DECMesh, Cells, limited=True))
        write(output / "source-manifest.json", manifest)
    for raw in grid_cases():
        grid = FiniteDiffSolver()
        xmin, xmax, ymin, ymax = raw["bounds_m"]
        grid.cell_grid((xmax - xmin) / raw["n"], xmin, xmax, ymin, ymax)
        record = dict(
            name=raw["name"],
            status="passed",
            input=raw,
            environment=grid_capture(grid, raw["boundaries"]),
        )
        write(output / (raw["name"] + ".json"), record)
        manifest["records"].append(
            dict(name=raw["name"], status="passed", path=str(output / (raw["name"] + ".json")))
        )
    manifest.update(
        status="passed",
        geometry_cases=len(cases()),
        grid_cases=len(grid_cases()),
        limitations=len(limitations()),
        production_cells_imported=any(k == "cells" or k.startswith("cells.") for k in sys.modules),
        jax_imported=any(k == "jax" or k.startswith("jax.") for k in sys.modules),
        solver_or_cut_executed=False,
        geometry_generation_executed=True,
        yaml_or_full_make_world=False,
        production_random_stream_claim=False,
    )
    assert not manifest["production_cells_imported"] and not manifest["jax_imported"]
    write(output / "source-manifest.json", manifest)
    print(
        json.dumps(
            dict(
                status="passed",
                geometry_cases=len(cases()),
                grid_cases=len(grid_cases()),
                limitations=len(limitations()),
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    capture(parser.parse_args().output)
