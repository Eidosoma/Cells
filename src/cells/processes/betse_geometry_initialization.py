"""Capture-authenticated initial native geometry into the environment binding.

Manufactured seed clouds and the native DECMesh ring-plus-centre generator are
different declarations. B09 generation is reused, not re-qualified. No metric
override, full make_world/image path, biological calibration or solver runs here.
"""

import hashlib
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from cells.core import geometry_tissue_preparation as existing
from cells.core.specs import digest, read_json
from cells.processes import betse_environment_field as environment
from cells.processes import betse_normal_current as current
from cells.processes import betse_perturbations as random_source

LAW_ID = "betse_geometry_initialization_environment_bridge@1"
KIND = "cells.betse_geometry_initialization_recipe@1"
B09_RECEIPT = Path("/mnt/workspaces/Cells/betse-geometry-development-20261029-03/result.json")
B09_SHA256 = "cbc165a2a899d30136ce3c78224ebec3e9acab9ce11ed08de680a7cd81b6a46f"
MODES = ("manufactured_seed_cloud", "native_generated_ring_and_centre")
MESH_FIELDS = {
    "cell_radius",
    "mesh_type",
    "use_centroids",
    "use_alpha_shape",
    "alpha_shape",
    "single_cell_sides",
    "single_cell_noise",
    "make_all_operators",
    "allow_merging",
    "merge_thresh",
    "close_thresh",
}
GEOMETRY_PARAMETERS = {"cell_height_m", "cell_space_m", "cell_radius_m"}


def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _canonical(value):
    return json.dumps(
        environment.plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


@dataclass(frozen=True, slots=True)
class Recipe:
    declaration_json: str
    identity: str

    @property
    def declaration(self):
        return json.loads(self.declaration_json)


@dataclass(frozen=True, slots=True)
class SeedState:
    recipe_identity: str
    points_m: object
    seed_ids: tuple
    x_uniforms: object
    y_uniforms: object
    stream_before: random_source.NativeStream
    stream_after: random_source.NativeStream
    draw_order: tuple
    identity: str


@dataclass(frozen=True, slots=True)
class Initialization:
    recipe_json: str
    seed_state: SeedState
    source_json: str
    authentication_json: str
    identity: str

    @property
    def source(self):
        return json.loads(self.source_json)

    @property
    def authentication(self):
        return json.loads(self.authentication_json)


@dataclass(frozen=True, slots=True)
class EnvironmentPreparation:
    initialization_identity: str
    material_json: str
    binding: environment.Binding
    provenance_json: str
    identity: str


def bind(raw):
    if (
        type(raw) is not dict
        or set(raw) != {"kind", "classification", "provenance", "native_input"}
        or raw["kind"] != KIND
    ):
        raise ValueError("Require the complete separate initial generation recipe")
    if (
        raw["classification"] not in MODES
        or type(raw["provenance"]) is not str
        or not raw["provenance"].strip()
    ):
        raise ValueError(
            "Declare manufactured seed coordinates or the supported native generated preset"
        )
    data = raw["native_input"]
    if set(data) != {
        "name",
        "seed",
        "seed_points_m",
        "seed_ids",
        "seed_policy",
        "mesh",
        "cell",
        "bounds_m",
        "environment_boundaries",
    }:
        raise ValueError("Require the exact B09 initial native generation inputs")
    if (
        type(data["name"]) is not str
        or not data["name"]
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for c in data["name"]
        )
    ):
        raise ValueError("Require a bounded capture case name without path components")
    if type(data["seed"]) is not int or not 0 <= data["seed"] < 2**32:
        raise ValueError("Require the original uint32 native seed")
    mesh, cell = data["mesh"], data["cell"]
    if set(mesh) != MESH_FIELDS or set(cell) != {
        "cell_radius",
        "scale_cell",
        "cell_space",
        "cell_height",
        "tm",
        "grid_size",
    }:
        raise ValueError("Require complete original B09 mesh and cell parameters")
    if mesh["mesh_type"] not in ("tri", "quad") or any(
        type(mesh[key]) is not bool
        for key in ("use_centroids", "use_alpha_shape", "make_all_operators", "allow_merging")
    ):
        raise ValueError("Declare native mesh algorithm and exact boolean branch controls")
    if mesh["use_alpha_shape"] or mesh["allow_merging"] or mesh["mesh_type"] != "tri":
        raise ValueError("This bridge does not broaden into alpha filtering or quad merging")
    for key in ("cell_radius", "alpha_shape", "merge_thresh", "close_thresh"):
        environment._scalar(mesh[key], key)
    if type(mesh["single_cell_sides"]) is not int or not 3 <= mesh["single_cell_sides"] <= 12:
        raise ValueError("Bound the native generated ring to 3..12 sides")
    noise = environment._scalar(mesh["single_cell_noise"], "single_cell_noise", positive=False)
    if not 0 <= noise <= 1:
        raise ValueError("Declare bounded native preset noise without clipping")
    for key in ("cell_radius", "scale_cell", "cell_space", "cell_height", "tm"):
        environment._scalar(cell[key], key)
    if (
        not cell["scale_cell"] < 1
        or type(cell["grid_size"]) is not int
        or not 2 <= cell["grid_size"] <= 7
    ):
        raise ValueError("Require source cell shrink and bounded environment grid")
    bounds = current._array(data["bounds_m"], (4,), "native world bounds")
    if bounds[1] <= bounds[0] or bounds[3] <= bounds[2]:
        raise ValueError("Require increasing original native world bounds")
    delta = (bounds[1] - bounds[0]) / cell["grid_size"]
    shape = (int((bounds[3] - bounds[2]) / delta), int((bounds[1] - bounds[0]) / delta))
    if min(shape) < 2 or math.prod(shape) > environment.MAX_GRID_POINTS:
        raise ValueError("Native grid exceeds the separate environment component bounds")
    if set(data["environment_boundaries"]) != {"N", "S", "E", "W"} or any(
        v not in ("value", "flux") for v in data["environment_boundaries"].values()
    ):
        raise ValueError(
            "Record original B09 boundary types even though field HH uses its value inverse"
        )
    if raw["classification"] == MODES[0]:
        points = np.asarray(data["seed_points_m"])
        if points.ndim != 2 or points.shape[1] != 2 or not 4 <= len(points) <= 32:
            raise ValueError("Declare a bounded manufactured seed cloud")
        current._array(points, points.shape, "manufactured seed cloud")
        if len(current._ids(data["seed_ids"], 32)) != len(points):
            raise ValueError("Every original manufactured seed requires its stable ID")
    elif data["seed_points_m"] is not None or data["seed_ids"] is not None:
        raise ValueError(
            "Native generated mode accepts no manufactured coordinates or owner override"
        )
    declaration = _canonical(raw)
    return Recipe(declaration, digest(json.loads(declaration)))


def seed_record(state):
    return dict(
        law=LAW_ID,
        recipe_identity=state.recipe_identity,
        points_m=state.points_m,
        seed_ids=state.seed_ids,
        x_uniforms=state.x_uniforms,
        y_uniforms=state.y_uniforms,
        stream_before=random_source.native_stream_manifest(state.stream_before),
        stream_after=random_source.native_stream_manifest(state.stream_after),
        draw_order=state.draw_order,
    )


def initialise(recipe):
    if type(recipe) is not Recipe or bind(recipe.declaration) != recipe:
        raise ValueError("Changed original geometry initialization recipe")
    declaration = recipe.declaration
    data, mode = declaration["native_input"], declaration["classification"]
    before = random_source.native_stream(data["seed"])
    rng = np.random.RandomState(0)
    state = random_source.native_stream_manifest(before)["state"]
    rng.set_state((state[0], np.asarray(state[1], np.uint32), state[2], state[3], state[4]))
    if mode == MODES[1]:
        mesh = data["mesh"]
        sides, radius, noise = (
            mesh["single_cell_sides"],
            mesh["cell_radius"],
            mesh["single_cell_noise"],
        )
        angles = [(2 * n * np.pi) / sides for n in range(sides)]
        x, y = 2 * radius * np.cos(angles), 2 * radius * np.sin(angles)
        ux, uy = rng.random(sides + 1), rng.random(sides + 1)
        x = np.hstack((x, 0.0)) + ux * radius * noise + 0.0
        y = np.hstack((y, 0.0)) + uy * radius * noise + 0.0
        points = np.column_stack((x, y))
        ids = tuple(f"native-seed{data['seed']}:{i}" for i in range(sides + 1))
        order = (("noisex", sides + 1), ("noisey", sides + 1))
    else:
        points = np.asarray(data["seed_points_m"], dtype=np.float64)
        ux = uy = np.empty(0)
        ids, order = tuple(data["seed_ids"]), ()
    saved = rng.get_state()
    after = random_source._native_stream(
        [saved[0], saved[1].tolist(), int(saved[2]), int(saved[3]), float(saved[4])], np.__version__
    )
    value = SeedState(
        recipe.identity,
        environment.frozen(points),
        ids,
        environment.frozen(ux),
        environment.frozen(uy),
        before,
        after,
        order,
        "",
    )
    return replace(value, identity=current._digest(seed_record(value)))


def _validate_seed(recipe, value):
    expected = initialise(recipe)
    if (
        type(value) is not SeedState
        or current.record(seed_record(value)) != current.record(seed_record(expected))
        or value.identity != expected.identity
    ):
        raise ValueError("Changed exact seed coordinates, draw ordering or complete MT19937 state")
    if any(v.flags.writeable for v in (value.points_m, value.x_uniforms, value.y_uniforms)):
        raise ValueError("Require immutable generated seeds and draw buffers")
    return value


def _source(record, manifest, record_sha):
    """Build existing B09 declarations solely from authenticated native outputs."""
    name, mesh, cells = record["name"], record["mesh"], record["cells"]
    seed = record["seed_binding"]
    if any(len(row) != 1 for row in seed["retained_matches"]):
        raise ValueError("Ambiguous native seed ownership remains a retained refusal")
    cell_ids = [row[0] for row in seed["retained_matches"]]
    dual = [f"{name}-dual-vertex-{i}" for i in range(len(mesh["vor_verts"]))]
    edge = [f"{name}-paired-edge-{i}" for i in range(len(mesh["tri_edges"]))]
    face = [f"{name}-face-{i}" for i in range(len(mesh["tri_cells"]))]
    membrane = [f"{name}-membrane-{i}" for i in range(len(cells["mem_sa"]))]
    env = record["environment"]
    environment_ids = [f"{name}-environment-{i}" for i in range(len(env["xy_cents"]))]
    generation = dict(
        mode="initial_native_generation@1",
        source=dict(
            version=manifest["version"],
            revision=manifest["revision"],
            files_sha256={key: value["sha256"] for key, value in manifest["files"].items()},
            runtime_versions=manifest["versions"],
        ),
        input=record["input"],
        constructed_seed_points_m=record["constructed_seed_points_m"],
        seed_binding=seed,
        rng_before=record["rng_before"],
        rng_after_constructor=record["rng_after_constructor"],
        rng_after=record["rng_after"],
        native_capture_file_sha256=record_sha,
        native_capture_record=record,
        native_capture_identity=digest(record),
        native_membrane_ids=membrane,
        provenance=dict(source="Pinned B09 generated initialization, no caller metric overrides"),
    )
    provenance = dict(generation_identity=digest(generation), native_case=name)
    return dict(
        generation=generation,
        mesh=dict(
            cell_ids=cell_ids,
            edge_ids=edge,
            face_ids=face,
            dual_vertex_ids=dual,
            primal_points_m=mesh["tri_verts"],
            primal_edges=[[cell_ids[i] for i in row] for row in mesh["tri_edges"]],
            primal_faces=[[cell_ids[i] for i in row] for row in mesh["tri_cells"]],
            dual_points_m=mesh["vor_verts"],
            dual_edges=[[dual[i] for i in row] for row in mesh["vor_edges"]],
            dual_cells=[[dual[i] for i in row] for row in mesh["vor_cells"]],
            boundary_cell_ids=[cell_ids[i] for i in mesh["bflags_tverts"]],
            inner_dual_vertex_ids=[dual[i] for i in mesh["inner_vvert_i"]],
            dual_control_area_m2=mesh["tri_sa_o"],
            dual_control_face_ids=[face[row[0]] for row in record["dual_control_face_candidates"]],
            auxiliary=record["input"]["mesh"]["make_all_operators"],
            source_seed_ids=seed["original_ids"],
            removed_seed_ids=seed["removed_ids"],
            provenance=provenance,
        ),
        grid=dict(
            environment_ids=environment_ids,
            shape=env["cents_shape"],
            bounds_m=record["input"]["bounds_m"],
            delta_m=env["delta"],
            coordinates_m=env["xy_cents"],
            boundaries=env["boundaries"],
            provenance=provenance,
        ),
        geometry=dict(
            membrane_ids=membrane,
            cell_membrane_ids=[[membrane[i] for i in row] for row in cells["cell_to_mems"]],
            partner_membrane_ids=[membrane[i] for i in cells["nn_i"]],
            boundary_membrane_ids=[membrane[i] for i in cells["bflags_mems"]],
            membrane_environment_ids=[environment_ids[i] for i in cells["map_mem2ecm"]],
            cell_environment_ids=[environment_ids[i] for i in cells["map_cell2ecm"]],
            shrink_factor=record["input"]["cell"]["scale_cell"],
            height_m=record["input"]["cell"]["cell_height"],
            gap_m=record["input"]["cell"]["cell_space"],
            provenance=provenance,
        ),
    )


def load_initialization(recipe, seed_state, *, receipt_path=B09_RECEIPT):
    """Accept only a capture sealed by the already-qualified fixed B09 receipt."""
    _validate_seed(recipe, seed_state)
    receipt_path = Path(receipt_path).resolve()
    if _sha(receipt_path) != B09_SHA256:
        raise ValueError(
            "Require the fixed reviewed B09 receipt; a caller checksum is not authority"
        )
    receipt = read_json(receipt_path)
    if receipt["status"] != "passed":
        raise ValueError("Require the unchanged passed B09 receipt")
    name = recipe.declaration["native_input"]["name"]
    relative = "native-source/" + name + ".json"
    manifest_relative = "native-source/source-manifest.json"
    root = receipt_path.parent
    record_path, manifest_path = root / relative, root / manifest_relative
    for rel, path in ((relative, record_path), (manifest_relative, manifest_path)):
        if not path.resolve().is_relative_to(root) or _sha(path) != receipt["output_sha256"][rel]:
            raise ValueError("Capture or source manifest differs from qualified B09 evidence")
    record, manifest = read_json(record_path), read_json(manifest_path)
    if (
        record["status"] != "passed"
        or manifest["status"] != "passed"
        or digest(record["input"]) != digest(recipe.declaration["native_input"])
    ):
        raise ValueError("Native generation input/capture differs from the original seed recipe")
    pins = {key: value["sha256"] for key, value in manifest["files"].items()}
    if pins != existing.NATIVE_SOURCE_SHA256 or manifest["revision"] != existing.NATIVE_REVISION:
        raise ValueError("Native geometry algorithm/source dependencies changed")
    if manifest["versions"]["numpy"] != np.__version__:
        raise ValueError("Exact native RNG replay requires the original NumPy version")
    before = random_source.native_stream_manifest(seed_state.stream_before)["state"]
    after = random_source.native_stream_manifest(seed_state.stream_after)["state"]
    if (
        digest(record["rng_before"]) != digest(before)
        or digest(record["rng_after_constructor"]) != digest(after)
        or digest(record["rng_after"]) != digest(after)
    ):
        raise ValueError("Native constructor or downstream mesh changed the declared draw state")
    if not np.array_equal(
        np.asarray(record["constructed_seed_points_m"], dtype=float), seed_state.points_m
    ) or record["seed_binding"]["original_ids"] != list(seed_state.seed_ids):
        raise ValueError(
            "Generated coordinates or original seed ordering differ from native capture"
        )
    source = _source(record, manifest, _sha(record_path))
    existing.bind_source(source)
    authentication = dict(
        receipt_path=str(receipt_path),
        receipt_sha256=B09_SHA256,
        record_sha256=_sha(record_path),
        source_manifest_sha256=_sha(manifest_path),
        reused_B09_coverage=True,
        classification=recipe.declaration["classification"],
        full_make_world=False,
        biological_geometry=False,
    )
    value = Initialization(
        recipe.declaration_json, seed_state, _canonical(source), _canonical(authentication), ""
    )
    return replace(
        value,
        identity=digest(
            dict(
                recipe=recipe.identity,
                seed_state=seed_state.identity,
                source=source,
                authentication=authentication,
            )
        ),
    )


def validate_initialization(value):
    if type(value) is not Initialization:
        raise ValueError("Require the complete authenticated initialization")
    recipe = bind(json.loads(value.recipe_json))
    expected = load_initialization(
        recipe, value.seed_state, receipt_path=value.authentication["receipt_path"]
    )
    if (value.recipe_json, value.source_json, value.authentication_json, value.identity) != (
        expected.recipe_json,
        expected.source_json,
        expected.authentication_json,
        expected.identity,
    ):
        raise ValueError("Resealed initialization differs from authenticated B09 generation")
    return value


def prepare_environment(initialization, material):
    """Derive geometry fields from authenticated capture; no geometry override API."""
    validate_initialization(initialization)
    recipe = bind(json.loads(initialization.recipe_json))
    _validate_seed(recipe, initialization.seed_state)
    source, auth = initialization.source, initialization.authentication
    identity = digest(
        dict(
            recipe=recipe.identity,
            seed_state=initialization.seed_state.identity,
            source=source,
            authentication=auth,
        )
    )
    if identity != initialization.identity or auth["receipt_sha256"] != B09_SHA256:
        raise ValueError("Changed authenticated geometry initialization")
    # Recompute the verified B09 topology/measures; generated metric columns
    # below retain original native arithmetic and source order.
    geometry = existing.bind_source(source)
    if type(material) is not dict or set(material) != {
        "ions",
        "F_C_mol",
        "sharpness_cell",
        "constants",
    }:
        raise ValueError("Declare material and constants only; metric overrides are unsupported")
    constants = material["constants"]
    if set(constants) != set(environment.PARAMETERS) - GEOMETRY_PARAMETERS:
        raise ValueError("Only non-geometry source constants may be supplied")
    ions = material["ions"]
    if (
        not isinstance(ions, list)
        or not 1 <= len(ions) <= 32
        or any(
            set(row)
            != {
                "id",
                "valence",
                "initial_cell_mol_m3",
                "initial_environment_mol_m3",
                "free_diffusion_m2_s",
            }
            for row in ions
        )
    ):
        raise ValueError("Declare bounded species and uniform manufactured initializer material")
    record = source["generation"]["native_capture_record"]
    c, params = record["cells"], record["input"]["cell"]
    n, m, e = (
        len(geometry.mesh.cell_ids),
        len(geometry.membrane_ids),
        len(geometry.grid.environment_ids),
    )
    bounds = record["input"]["bounds_m"]
    definition = dict(
        kind=environment.INPUT_KIND,
        provenance="Authenticated initial geometry "
        + initialization.identity
        + "; material remains declared, not biological calibration",
        is_ecm=True,
        current_definition=dict(
            kind=current.INPUT_KIND,
            provenance="Native generated geometry occurrence order " + initialization.identity,
            geometry=dict(
                cell_ids=geometry.mesh.cell_ids,
                membrane_ids=geometry.membrane_ids,
                owner=c["mem_to_cells"],
                membrane_area_m2=c["mem_sa"],
                cell_area_m2=c["cell_sa"],
                normal_xy=np.asarray(c["mem_vects_flat"])[:, 2:4],
            ),
            ions=dict(ids=[row["id"] for row in ions], valence=[row["valence"] for row in ions]),
            parameters=dict(F_C_mol=material["F_C_mol"], sharpness_cell=material["sharpness_cell"]),
        ),
        world=dict(
            xmin_m=bounds[0],
            xmax_m=bounds[1],
            ymin_m=bounds[2],
            ymax_m=bounds[3],
            grid_size=params["grid_size"],
        ),
        geometry=dict(
            cell_centres_m=c["cell_centres"],
            membrane_midpoints_m=c["mem_mids_flat"],
            cell_volume_m3=c["cell_vol"],
        ),
        parameters=constants
        | dict(
            cell_height_m=params["cell_height"],
            cell_space_m=params["cell_space"],
            cell_radius_m=params["cell_radius"],
        ),
        cache_initial_state=dict(
            cell_mol_m3=[[row["initial_cell_mol_m3"]] * n for row in ions],
            environment_mol_m3=[[row["initial_environment_mol_m3"]] * e for row in ions],
            free_diffusion_m2_s=[row["free_diffusion_m2_s"] for row in ions],
        ),
    )
    try:
        binding = environment.bind(environment.plain(definition))
    except environment.EnvironmentFieldRejected as error:
        error.generated_definition = environment.plain(definition)
        error.initialization_identity = initialization.identity
        raise
    if not np.array_equal(
        binding.geometry.membrane_to_grid, c["map_mem2ecm"]
    ) or not np.array_equal(binding.geometry.cell_to_grid, c["map_cell2ecm"]):
        raise ValueError("Re-derived unique environment maps differ from captured native maps")
    provenance = dict(
        law=LAW_ID,
        initialization_identity=initialization.identity,
        reused_B09_coverage=True,
        geometry_classification=recipe.declaration["classification"],
        material_classification="declared_uniform_manufactured_material",
        caller_metric_overrides=False,
        strict_environment_nearest_admission=True,
        original_native_metric_columns=True,
        geometry_cell_count=n,
        geometry_membrane_count=m,
        biological_geometry=False,
        full_make_world=False,
        field_readout_or_tissue_step=False,
    )
    value = EnvironmentPreparation(
        initialization.identity, _canonical(material), binding, _canonical(provenance), ""
    )
    return replace(
        value,
        identity=current._digest(
            dict(
                initialization=initialization.identity,
                material=material,
                field_binding=environment.binding_record(binding),
                provenance=provenance,
            )
        ),
    )


def validate_preparation(initialization, value):
    if type(value) is not EnvironmentPreparation:
        raise ValueError("Require the complete geometry/environment preparation")
    expected = prepare_environment(initialization, json.loads(value.material_json))
    if (
        value.identity != expected.identity
        or value.initialization_identity != expected.initialization_identity
        or value.provenance_json != expected.provenance_json
        or current.record(environment.binding_record(value.binding))
        != current.record(environment.binding_record(expected.binding))
    ):
        raise ValueError(
            "Resealed prepared environment differs from original generated geometry/material"
        )
    return value
