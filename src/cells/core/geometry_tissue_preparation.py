"""Explicit initial static native geometry to ordinary passive tissue.

Geometry is rebound from complete declarations. Physical volumes, inventory,
charge, membrane constitutive parameters and all controls have separate, explicit
owners. DEC measures and occupied-grid weights never become exterior volumes.
"""

import json
from copy import deepcopy
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np

from cells.core.specs import ConfigError, digest, parse_spec
from cells.models import surface_tissue
from cells.processes import betse_geometry as geometry

BRIDGE_ID = "native_geometry_passive_tissue@1"
REQUEST_KIND = "cells.initial_static_geometry_tissue_request@1"
KIND = "cells.initial_static_geometry_tissue_preparation@1"
NATIVE_REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
NATIVE_SOURCE_SHA256 = {
    "betse/metadata.py": ("6a09cc83d58ec6c1ea4b5a4c11fa0eb46d3b84518309a0495ddc7d61610ce8a1"),
    "betse/science/cells.py": ("be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"),
    "betse/science/math/mesh.py": (
        "fd0dc21e1f82aa71e19a487f3b91c4b5258f02aec4c69f22c2bf3c419e425c38"
    ),
    "betse/science/math/finitediff.py": (
        "8186bc5c013db8aec224f6ed9b0892e944b2ddd4247f135ff19caf7419478350"
    ),
    "betse/science/math/toolbox.py": (
        "a2a63fe1f44303fe05d2b1fbcfe9250e4575992f688cbe4cbd7fd99ef99e60a3"
    ),
    "betse/util/math/mathoper.py": (
        "375d44263e2b8fbda7f99ee0b63c4f62e2090dc5e8089ece8447df6f8bac4854"
    ),
    "betse/util/math/geometry/polygon/geopoly.py": (
        "8a031ba303e024f13964f8bd2f225b72128f27574c10ff84a21e100a67727f83"
    ),
    "betse/util/math/geometry/polygon/geopolyconvex.py": (
        "7c02760027be9913dc9e1e4c76352be942a6b2628f8c3b19098b21ca6b594199"
    ),
}


@dataclass(frozen=True)
class Preparation:
    definition: dict
    provenance: dict


def _json(value):
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError, OverflowError) as error:
        raise ConfigError("Require complete finite JSON declarations") from error


def _keys(row, required, where):
    if type(row) is not dict or set(row) != set(required):
        raise ConfigError("Require exactly the declared fields for " + where)
    return row


def _number(value, where, *, positive=False):
    if (
        type(value) not in (int, float)
        or not np.isfinite(value)
        or (value <= 0 if positive else value < 0)
    ):
        raise ConfigError("Require finite " + ("positive " if positive else "nonnegative ") + where)
    return float(value)


def _rows(value, names, required, where):
    if type(value) is not list:
        raise ConfigError("Require explicit stable-ID rows for " + where)
    result = {}
    for row in value:
        _keys(row, required, where)
        name = row["id"]
        if type(name) is not str or not name or name in result:
            raise ConfigError("Require unique stable owner IDs for " + where)
        result[name] = row
    if names is not None and set(result) != set(names):
        raise ConfigError("Owner IDs must match the complete bound " + where + " axis")
    return result


def _vector(value, species, where):
    _keys(value, species, where)
    return {name: _number(value[name], where) for name in species}


def _capture_consistency(source):
    """Bind declared stable axes to the complete, retained native record."""
    g = source["generation"]
    record = g["native_capture_record"]
    if digest(record) != g["native_capture_identity"] or record["status"] != "passed":
        raise ConfigError("Require an unchanged completed initial native geometry capture")
    for key in (
        "input",
        "constructed_seed_points_m",
        "seed_binding",
        "rng_before",
        "rng_after_constructor",
        "rng_after",
    ):
        if g[key] != record[key]:
            raise ConfigError("Native generation metadata disagrees with the complete capture")
    m, mesh = record["mesh"], source["mesh"]
    cids, dual = mesh["cell_ids"], mesh["dual_vertex_ids"]
    for declared, captured in (
        ("primal_points_m", "tri_verts"),
        ("dual_points_m", "vor_verts"),
        ("dual_control_area_m2", "tri_sa_o"),
    ):
        if mesh[declared] != m[captured]:
            raise ConfigError("Declared mesh metric differs from its initial native capture")
    for declared, captured, axis in (
        ("primal_edges", "tri_edges", cids),
        ("primal_faces", "tri_cells", cids),
        ("dual_edges", "vor_edges", dual),
        ("dual_cells", "vor_cells", dual),
    ):
        if mesh[declared] != [[axis[i] for i in row] for row in m[captured]]:
            raise ConfigError("Declared mesh topology differs from its initial native capture")
    if (
        mesh["boundary_cell_ids"] != [cids[i] for i in m["bflags_tverts"]]
        or mesh["inner_dual_vertex_ids"] != [dual[i] for i in m["inner_vvert_i"]]
        or mesh["auxiliary"] != g["input"]["mesh"]["make_all_operators"]
    ):
        raise ConfigError("Native boundary/auxiliary mesh declaration changed")
    for vertex, candidate in zip(
        mesh["dual_control_face_ids"], record["dual_control_face_candidates"], strict=True
    ):
        if vertex != mesh["face_ids"][candidate[0]]:
            raise ConfigError("Native reference-face ownership changed")
    grid, env = source["grid"], record["environment"]
    for declared, captured in (
        ("shape", "cents_shape"),
        ("coordinates_m", "xy_cents"),
        ("delta_m", "delta"),
        ("boundaries", "boundaries"),
    ):
        if grid[declared] != env[captured]:
            raise ConfigError("Declared grid metric differs from initial native capture")
    ids = g["native_membrane_ids"]
    geom, cells = source["geometry"], record["cells"]
    if (
        len(ids) != len(cells["nn_i"])
        or len(set(ids)) != len(ids)
        or set(ids) != set(geom["membrane_ids"])
    ):
        raise ConfigError("Explicit native membrane occurrence axis lost its stable IDs")
    env_ids = grid["environment_ids"]
    partner = dict(zip(ids, (ids[i] for i in cells["nn_i"]), strict=True))
    environment = dict(zip(ids, (env_ids[i] for i in cells["map_mem2ecm"]), strict=True))
    if (
        geom["cell_membrane_ids"] != [[ids[i] for i in row] for row in cells["cell_to_mems"]]
        or geom["partner_membrane_ids"] != [partner[name] for name in geom["membrane_ids"]]
        or geom["membrane_environment_ids"] != [environment[name] for name in geom["membrane_ids"]]
        or geom["cell_environment_ids"] != [env_ids[i] for i in cells["map_cell2ecm"]]
        or geom["boundary_membrane_ids"] != [ids[i] for i in cells["bflags_mems"]]
    ):
        raise ConfigError("Static physical surface owners differ from the native capture")


def bind_source(source):
    """Recompute all qualified binding data; a raw binding is not accepted."""
    _keys(source, {"generation", "mesh", "grid", "geometry"}, "geometry source")
    generation = source["generation"]
    _keys(
        generation,
        {
            "mode",
            "source",
            "input",
            "constructed_seed_points_m",
            "seed_binding",
            "rng_before",
            "rng_after_constructor",
            "rng_after",
            "native_capture_file_sha256",
            "native_capture_record",
            "native_capture_identity",
            "native_membrane_ids",
            "provenance",
        },
        "initial generation provenance",
    )
    if generation["mode"] != "initial_native_generation@1":
        raise ConfigError("Cut, remapped, moving or continuing geometry needs a new contract")
    pin = generation["source"]
    _keys(pin, {"version", "revision", "files_sha256", "runtime_versions"}, "native source pins")
    if pin["version"] != "1.5.0" or pin["revision"] != NATIVE_REVISION:
        raise ConfigError("Require the qualified native geometry version and revision")
    if pin["files_sha256"] != NATIVE_SOURCE_SHA256:
        raise ConfigError("Native geometry source hashes differ from the qualified pinned bodies")
    hashes = [generation["native_capture_file_sha256"], *pin["files_sha256"].values()]
    if not pin["files_sha256"] or any(
        type(v) is not str or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
        for v in hashes
    ):
        raise ConfigError("Require complete native capture/source identities")
    if not pin["runtime_versions"] or not generation["provenance"]:
        raise ConfigError("Native runtime and generation provenance must be explicit")
    for key in ("rng_before", "rng_after_constructor", "rng_after"):
        if type(generation[key]) is not list or len(generation[key]) != 5:
            raise ConfigError("Persist each complete native RandomState record")
    for cls, key, omit in (
        (geometry.MeshSpec, "mesh", set()),
        (geometry.GridSpec, "grid", set()),
        (geometry.GeometrySpec, "geometry", {"mesh", "grid"}),
    ):
        _keys(source[key], {f.name for f in fields(cls)} - omit, key + " spec")
        if type(source[key]["provenance"]) is not dict or source[key]["provenance"].get(
            "generation_identity"
        ) != digest(generation):
            raise ConfigError("Every geometry spec must bind the full initial generation recipe")
    seed = generation["seed_binding"]
    _keys(seed, {"original_ids", "retained_matches", "removed_ids", "policy"}, "seed ledger")
    mesh_raw = source["mesh"]
    if (
        seed["original_ids"] != mesh_raw["source_seed_ids"]
        or seed["removed_ids"] != mesh_raw["removed_seed_ids"]
        or seed["retained_matches"] != [[name] for name in mesh_raw["cell_ids"]]
    ):
        raise ConfigError("Initial seed ledger and declared retained physical owners disagree")
    points = generation["constructed_seed_points_m"]
    if len(points) != len(seed["original_ids"]):
        raise ConfigError("Initial generated seed coordinates need every original owner")
    by_seed = dict(zip(seed["original_ids"], points, strict=True))
    if not np.array_equal(
        [by_seed[name] for name in mesh_raw["cell_ids"]], mesh_raw["primal_points_m"]
    ):
        raise ConfigError("Retained primal coordinates lost their initial seed provenance")
    native_input = generation["input"]
    _keys(
        native_input,
        {
            "name",
            "seed",
            "seed_points_m",
            "seed_ids",
            "seed_policy",
            "mesh",
            "cell",
            "bounds_m",
            "environment_boundaries",
        },
        "native generation inputs",
    )
    params = native_input["cell"]
    for a, b in (
        ("height_m", "cell_height"),
        ("gap_m", "cell_space"),
        ("shrink_factor", "scale_cell"),
    ):
        if source["geometry"][a] != params[b]:
            raise ConfigError("Geometry height/gap/shrink differs from its generation inputs")
    if (
        source["grid"]["bounds_m"] != native_input["bounds_m"]
        or source["grid"]["boundaries"] != native_input["environment_boundaries"]
    ):
        raise ConfigError("Grid bounds/boundary labels differ from initial generation")
    try:
        _capture_consistency(source)
        mesh = geometry.bind_mesh(geometry.MeshSpec(**mesh_raw))
        grid = geometry.bind_grid(geometry.GridSpec(**source["grid"]))
        return geometry.bind_geometry(
            geometry.GeometrySpec(mesh=mesh, grid=grid, **source["geometry"])
        )
    except (TypeError, ValueError, ArithmeticError, KeyError) as error:
        raise ConfigError("Invalid complete static geometry: " + str(error)) from error


def _definition(request, bound):
    physical = request["physics"]
    _keys(
        physical,
        {
            "volume_policy",
            "exterior_volume_policy",
            "membrane_area_policy",
            "junction_area_policy",
            "species",
            "temperature_K",
            "cells",
            "extracellular",
            "membranes",
            "junctions",
            "faces",
            "closure",
            "provenance",
        },
        "passive physical declarations",
    )
    if physical["volume_policy"] not in ("native_radial", "polygon"):
        raise ConfigError("Choose native_radial or polygon cell volume explicitly")
    if physical["exterior_volume_policy"] != "explicit_physical_m3@1":
        raise ConfigError(
            "Exterior volumes require explicit physical m3, never source DEC/grid weights"
        )
    if physical["membrane_area_policy"] != "bound_edge_length_times_height@1":
        raise ConfigError("Declare the bound physical membrane area policy")
    if physical["junction_area_policy"] != "one_bound_contact_surface@1":
        raise ConfigError("Declare one physical junction surface per reciprocal contact")
    if type(physical["provenance"]) is not dict or not physical["provenance"]:
        raise ConfigError("Explicit physical volume/coefficient/inventory provenance required")
    if type(physical["species"]) is not list or not physical["species"]:
        raise ConfigError("Require explicit ordered species and valences")
    species = []
    for row in physical["species"]:
        _keys(row, {"id", "valence"}, "species")
        if type(row["id"]) is not str or row["id"] in species:
            raise ConfigError("Species IDs must be unique explicit strings")
        species.append(row["id"])
    initial = {"id", "initial_amount_fmol", "initial_charge_C", "fixed_charge_equivalent_fmol"}
    cells = _rows(physical["cells"], bound.mesh.cell_ids, initial, "cell")
    outside = _rows(
        physical["extracellular"],
        bound.grid.environment_ids,
        initial | {"volume_m3", "reservoir", "boundary_potential_V"},
        "exterior",
    )
    patches = _rows(
        physical["membranes"],
        bound.membrane_ids,
        {
            "id",
            "inside",
            "outside",
            "thickness_m",
            "specific_capacitance_F_per_m2",
            "diffusivity_m2_per_s",
        },
        "membrane",
    )
    k = bound.kernel
    volume = (
        k.native_cell_volume_m3
        if physical["volume_policy"] == "native_radial"
        else k.polygon_cell_volume_m3
    )
    model = dict(
        id="resolved_tissue@1", species=physical["species"], temperature_K=physical["temperature_K"]
    )
    model["cells"] = [
        dict(cells[name], volume_pL=float(volume[i]) * 1e15)
        for i, name in enumerate(bound.mesh.cell_ids)
    ]
    model["extracellular"] = []
    for name in bound.grid.environment_ids:
        row = deepcopy(outside[name])
        row["volume_pL"] = (
            _number(row.pop("volume_m3"), "physical exterior volume", positive=True) * 1e15
        )
        model["extracellular"].append(row)
    model["membranes"] = []
    for i, name in enumerate(bound.membrane_ids):
        row = patches[name]
        if (
            row["inside"] != bound.mesh.cell_ids[k.owner[i]]
            or row["outside"] != bound.grid.environment_ids[k.environment_owner[i]]
        ):
            raise ConfigError("Membrane physical owners disagree with bound native owners")
        thickness = _number(row["thickness_m"], "membrane thickness", positive=True)
        specific = _number(row["specific_capacitance_F_per_m2"], "areal capacitance", positive=True)
        diffusion = _vector(row["diffusivity_m2_per_s"], species, "membrane diffusivity")
        model["membranes"].append(
            dict(
                id=name,
                inside=row["inside"],
                outside=row["outside"],
                area_m2=float(k.membrane_area_m2[i]),
                capacitance_F=float(k.membrane_area_m2[i]) * specific,
                permeability_m_per_s={s: diffusion[s] / thickness for s in species},
                law="constant_field@1",
            )
        )
    junctions = _rows(
        physical["junctions"],
        None,
        {"id", "sender", "receiver", "membrane_ids", "permeability_m_per_s"},
        "junction",
    )
    expected = {
        frozenset((bound.membrane_ids[a], bound.membrane_ids[b])) for a, b in k.contact_pairs
    }
    seen = set()
    model["junctions"] = []
    for row in junctions.values():
        pair = row["membrane_ids"]
        if type(pair) is not list or len(pair) != 2 or any(type(v) is not str for v in pair):
            raise ConfigError("Junctions require two ordered stable contact membranes")
        key = frozenset(pair)
        if key not in expected or key in seen:
            raise ConfigError("Junction contacts must cover actual reciprocal pairs exactly once")
        seen.add(key)
        a, b = (bound.membrane_ids.index(v) for v in pair)
        if (
            row["sender"] != bound.mesh.cell_ids[k.owner[a]]
            or row["receiver"] != bound.mesh.cell_ids[k.owner[b]]
        ):
            raise ConfigError("Junction orientation must follow declared contact owners")
        model["junctions"].append(
            dict(
                id=row["id"],
                sender=row["sender"],
                receiver=row["receiver"],
                area_m2=float(k.membrane_area_m2[a]),
                permeability_m_per_s=_vector(
                    row["permeability_m_per_s"], species, "junction permeability"
                ),
                law="constant_field@1",
            )
        )
    if seen != expected:
        raise ConfigError("Every reciprocal contact needs an explicit junction; no inferred route")
    model["faces"] = deepcopy(physical["faces"])
    model["closure"] = deepcopy(physical["closure"])
    return dict(
        schema_version=1,
        model=model,
        experiment=request["experiment"],
        execution=request["execution"],
    )


def prepare(request):
    request = _json(request)
    _keys(
        request,
        {"kind", "geometry_source", "physics", "experiment", "execution"},
        "initial static preparation request",
    )
    if request["kind"] != REQUEST_KIND:
        raise ConfigError("Only initial static passive preparation is supported")
    bound = bind_source(request["geometry_source"])
    spec = parse_spec(_definition(request, bound))
    definition = spec.to_dict()
    state, _ = surface_tissue.initial_values(spec)
    if any(np.any(np.asarray(v) != 0) for v in state):
        raise ConfigError("Ordinary initial passive state must start with empty transfer ledgers")
    record = dict(
        kind=KIND,
        bridge_id=BRIDGE_ID,
        request=request,
        request_sha256=digest(request),
        prepared_definition_sha256=digest(definition),
        geometry_manifest=_json(geometry.geometry_manifest(bound)),
        geometry_law_id=geometry.LAW_ID,
        volume_policy=request["physics"]["volume_policy"],
        cell_measures_m3={
            name: dict(
                native_radial=float(bound.kernel.native_cell_volume_m3[i]),
                polygon=float(bound.kernel.polygon_cell_volume_m3[i]),
            )
            for i, name in enumerate(bound.mesh.cell_ids)
        },
        excluded_exterior_measures=(
            "DEC control areas and native occupied-grid weights are never physical exterior volumes"
        ),
        membrane_constitutive_policy=(
            "C=bound_area*specific_capacitance; P=explicit_diffusivity/explicit_thickness"
        ),
        junction_constitutive_policy=(
            "Explicit permeability on one declared reciprocal physical contact surface"
        ),
        initial_state_fields=list(state._fields),
        initial_state_sha256=digest(
            {
                name: dict(
                    dtype=str(np.asarray(v).dtype),
                    shape=list(np.asarray(v).shape),
                    values=np.asarray(v).tolist(),
                )
                for name, v in state._asdict().items()
            }
        ),
        physical_inventory_sha256=digest(
            {key: definition["model"][key] for key in ("species", "cells", "extracellular")}
        ),
        control_history_sha256=digest(definition["experiment"]),
        scope=(
            "Initial static resolved_tissue@1 only; no geometry generation, physical remap, "
            "moving geometry, cut or solver continuation"
        ),
    )
    record = _json(record)
    record["identity"] = digest(record)
    return Preparation(definition, record)


def replay(provenance):
    try:
        row = deepcopy(provenance)
        identity = row.pop("identity")
        if row["kind"] != KIND or identity != digest(row):
            raise ConfigError("Stale initial geometry preparation identity")
        result = prepare(row["request"])
        if result.provenance != provenance:
            raise ConfigError("Geometry/physics/owner/state/control provenance changed")
        return result
    except (ValueError, TypeError, KeyError, ArithmeticError) as error:
        raise ConfigError("Invalid complete geometry preparation: " + str(error)) from error


def write_preparation(directory, prepared):
    expected = replay(prepared.provenance)
    if expected.definition != prepared.definition:
        raise ConfigError("Prepared tissue differs from its geometry/physics recipe")
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    for name, value in (
        ("definition.json", expected.definition),
        ("provenance.json", expected.provenance),
    ):
        (path / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return path


def read_preparation(directory):
    path = Path(directory)
    expected = replay(json.loads((path / "provenance.json").read_text()))
    if json.loads((path / "definition.json").read_text()) != expected.definition:
        raise ConfigError("Serialized passive tissue differs from its full geometry recipe")
    return expected
