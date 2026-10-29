"""Complete declarations over frozen authenticated native geometry captures."""

import hashlib
import json
import os
from copy import deepcopy
from math import fsum
from pathlib import Path

from validation.geometry import geometry_tissue_preparation_reference as reference

NATIVE = Path("/mnt/workspaces/Cells/betse-geometry-development-20261029-03/native-source")
CASES = (
    "centroid-core",
    "irregular-centroid-aux",
    "irregular-circumcenter-aux",
    "translated-scaled-circumcenter",
    "circumcenter-aux",
)


def identity(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def source(name, permuted=False):
    folder = Path(os.environ.get("CELLS_GEOMETRY_PREPARATION_NATIVE", str(NATIVE)))
    path = folder / (name + ".json")
    raw = json.loads(path.read_text())
    manifest = json.loads((folder / "source-manifest.json").read_text())
    gen = dict(
        mode="initial_native_generation@1",
        source=dict(
            version=manifest["version"],
            revision=manifest["revision"],
            files_sha256={k: v["sha256"] for k, v in manifest["files"].items()},
            runtime_versions=manifest["versions"],
        ),
        input=raw["input"],
        constructed_seed_points_m=raw["constructed_seed_points_m"],
        seed_binding=raw["seed_binding"],
        rng_before=raw["rng_before"],
        rng_after_constructor=raw["rng_after_constructor"],
        rng_after=raw["rng_after"],
        native_capture_file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        native_capture_record=raw,
        native_capture_identity=identity(raw),
        native_membrane_ids=[f"{name}-membrane-{i}" for i in range(len(raw["cells"]["mem_sa"]))],
        provenance=dict(
            capture=(
                "Actual authenticated native classes from qualified B09 receipt; "
                "initial geometry before any physical inventories"
            )
        ),
    )
    seal = identity(gen)
    m = raw["mesh"]
    seed = raw["seed_binding"]
    cells = [row[0] for row in seed["retained_matches"]]
    dual = [f"{name}-dual-vertex-{i}" for i in range(len(m["vor_verts"]))]
    edge = [f"{name}-paired-edge-{i}" for i in range(len(m["tri_edges"]))]
    face = [f"{name}-face-{i}" for i in range(len(m["tri_cells"]))]
    mesh = dict(
        cell_ids=cells,
        edge_ids=edge,
        face_ids=face,
        dual_vertex_ids=dual,
        primal_points_m=m["tri_verts"],
        primal_edges=[[cells[i] for i in row] for row in m["tri_edges"]],
        primal_faces=[[cells[i] for i in row] for row in m["tri_cells"]],
        dual_points_m=m["vor_verts"],
        dual_edges=[[dual[i] for i in row] for row in m["vor_edges"]],
        dual_cells=[[dual[i] for i in row] for row in m["vor_cells"]],
        boundary_cell_ids=[cells[i] for i in m["bflags_tverts"]],
        inner_dual_vertex_ids=[dual[i] for i in m["inner_vvert_i"]],
        dual_control_area_m2=m["tri_sa_o"],
        dual_control_face_ids=[face[row[0]] for row in raw["dual_control_face_candidates"]],
        auxiliary=raw["input"]["mesh"]["make_all_operators"],
        source_seed_ids=seed["original_ids"],
        removed_seed_ids=seed["removed_ids"],
        provenance=dict(
            generation_identity=seal,
            native_case=name,
            seed_binding=seed,
            mesh_parameters=raw["input"]["mesh"],
        ),
    )
    env = raw["environment"]
    oids = [f"{name}-environment-{i}" for i in range(len(env["xy_cents"]))]
    grid = dict(
        environment_ids=oids,
        shape=env["cents_shape"],
        bounds_m=raw["input"]["bounds_m"],
        delta_m=env["delta"],
        coordinates_m=env["xy_cents"],
        boundaries=env["boundaries"],
        provenance=dict(generation_identity=seal, native_case=name),
    )
    c = raw["cells"]
    params = raw["input"]["cell"]
    mids = [f"{name}-membrane-{i}" for i in range(len(c["mem_sa"]))]
    geom = dict(
        membrane_ids=mids,
        cell_membrane_ids=[[mids[i] for i in row] for row in c["cell_to_mems"]],
        partner_membrane_ids=[mids[i] for i in c["nn_i"]],
        boundary_membrane_ids=[mids[i] for i in c["bflags_mems"]],
        membrane_environment_ids=[oids[i] for i in c["map_mem2ecm"]],
        cell_environment_ids=[oids[i] for i in c["map_cell2ecm"]],
        shrink_factor=params["scale_cell"],
        height_m=params["cell_height"],
        gap_m=params["cell_space"],
        provenance=dict(generation_identity=seal, native_case=name, cell_parameters=params),
    )
    if permuted:
        for key in ("membrane_ids", "partner_membrane_ids", "membrane_environment_ids"):
            geom[key] = list(reversed(geom[key]))
    return dict(generation=gen, mesh=mesh, grid=grid, geometry=geom)


def request(name="irregular-centroid-aux", policy="native_radial", permuted=False):
    src = source(name, permuted)
    g = src["geometry"]
    metric = reference.measures(src)
    species = [dict(id="Na", valence=1), dict(id="K", valence=1), dict(id="Cl", valence=-1)]
    ids = [v["id"] for v in species]
    z = [v["valence"] for v in species]
    owner = {
        mid: cid
        for cid, group in zip(src["mesh"]["cell_ids"], g["cell_membrane_ids"], strict=True)
        for mid in group
    }
    patches = []
    for i, mid in enumerate(g["membrane_ids"]):
        patches.append(
            dict(
                id=mid,
                inside=owner[mid],
                outside=g["membrane_environment_ids"][i],
                thickness_m=(5 + 0.01 * i) * 1e-9,
                specific_capacitance_F_per_m2=0.01,
                diffusivity_m2_per_s=dict(zip(ids, [1.5e-18, 3e-18, 2.4e-18], strict=True)),
            )
        )
    cell_rows = []
    charge_per_fmol = 96485.33212331001 * 1e-15
    for i, cid in enumerate(src["mesh"]["cell_ids"]):
        volume = metric["cells"][cid][policy] * 1e15
        amounts = dict(zip(ids, [(12 + i) * volume, (140 - i) * volume, 11 * volume], strict=True))
        capacitance = fsum(
            metric["membranes"][mid]["area_m2"] * 0.01 for mid in g["cell_membrane_ids"][i]
        )
        charge = capacitance * (-0.025 + 0.001 * i)
        fixed = charge / charge_per_fmol - fsum(v * amounts[s] for s, v in zip(ids, z, strict=True))
        cell_rows.append(
            dict(
                id=cid,
                initial_amount_fmol=amounts,
                initial_charge_C=charge,
                fixed_charge_equivalent_fmol=fixed,
            )
        )
    exterior = []
    for i, oid in enumerate(src["grid"]["environment_ids"]):
        volume = (2 + i / 100) * src["grid"]["delta_m"] ** 2 * g["height_m"]
        amounts = dict(
            zip(ids, [145 * volume * 1e15, 4 * volume * 1e15, 120 * volume * 1e15], strict=True)
        )
        exterior.append(
            dict(
                id=oid,
                volume_m3=volume,
                initial_amount_fmol=amounts,
                initial_charge_C=0.0,
                fixed_charge_equivalent_fmol=-fsum(
                    v * amounts[s] for s, v in zip(ids, z, strict=True)
                ),
                reservoir=True,
                boundary_potential_V=0.0,
            )
        )
    junctions = []
    position = {name: i for i, name in enumerate(g["membrane_ids"])}
    for a, b in zip(g["membrane_ids"], g["partner_membrane_ids"], strict=True):
        if position[a] < position[b]:
            junctions.append(
                dict(
                    id=f"{name}-junction-{len(junctions)}",
                    sender=owner[a],
                    receiver=owner[b],
                    membrane_ids=[a, b],
                    permeability_m_per_s=dict(zip(ids, [2e-8, 3e-8, 1e-8], strict=True)),
                )
            )
    faces = []
    oids = src["grid"]["environment_ids"]
    for i in range(len(oids) - 1):
        faces.append(
            dict(
                id=f"{name}-physical-face-{i}",
                sender=oids[i],
                receiver=oids[i + 1],
                area_m2=1.7e-10,
                length_m=2.2e-6,
                diffusivity_m2_per_s={s: 1.1e-12 for s in ids},
                law="logmean_electrodiffusion@1",
            )
        )
    physical = dict(
        volume_policy=policy,
        exterior_volume_policy="explicit_physical_m3@1",
        membrane_area_policy="bound_edge_length_times_height@1",
        junction_area_policy="one_bound_contact_surface@1",
        species=species,
        temperature_K=298.15,
        cells=cell_rows,
        extracellular=exterior,
        membranes=patches,
        junctions=junctions,
        faces=faces,
        closure=dict(
            law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
        ),
        provenance=dict(
            exterior_volume=(
                "Explicit manufactured physical well-mixed volumes, "
                "distinct from every native weighting"
            ),
            constitutive_parameters=(
                "Explicit SI thickness, areal capacitance, diffusion and junction P"
            ),
            initial_state=(
                "Explicit inventories/fixed background and charge anchors before any evolution"
            ),
        ),
    )
    experiment = dict(end_time=1e-5, observation_times=[0.0, 5e-6, 1e-5])
    for kind, rows in (("membrane", patches), ("junction", junctions)):
        experiment[kind + "_controls"] = [
            {
                kind + "_id": row["id"],
                "schedule": [dict(time=0.0, availability=1.0), dict(time=5e-6, availability=0.7)],
            }
            for row in rows
        ]
    execution = dict(
        dt=1e-6,
        jit=False,
        backend="cpu",
        precision="float64",
        solver="rk4",
        max_steps=20,
        max_trace_bytes=2000000,
        material_balance_atol_fmol={s: 1e-11 for s in ids},
        capacity=len(cell_rows) + 1,
        extracellular_capacity=len(exterior) + 1,
        membrane_capacity=len(patches) + 1,
        edge_capacity=len(junctions) + 1,
        face_capacity=len(faces) + 1,
        field_solver="capacitive_reduction_gauged_damped_newton@1",
    )
    if permuted:
        for key in ("cells", "extracellular", "membranes"):
            physical[key].reverse()
    return deepcopy(
        dict(
            kind="cells.initial_static_geometry_tissue_request@1",
            geometry_source=src,
            physics=physical,
            experiment=experiment,
            execution=execution,
        )
    )
