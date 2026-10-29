"""Independent Decimal oracle for static extracellular barrier preparation.

Only coefficients and their physical owners are prepared.  BETSE's native
barrier assignments are retained; its collocated transport stencil is not used.
The resulting ordinary tissue still uses logmean_electrodiffusion@1.  This file
imports only the Python standard library and never calls Cells/JAX code.
"""

import math
import sys
from copy import deepcopy
from decimal import Decimal, localcontext

REQUEST_KIND = "cells.environment_barrier_preparation_request@1"
GRID_FIELDS = {
    "site_ids",
    "species_ids",
    "valence",
    "shape",
    "coordinates_m",
    "delta_m",
    "height_m",
    "internal_face_ids",
    "internal_face_sites",
    "boundary_face_ids",
    "boundary_face_sites",
    "boundary_face_sides",
    "provenance",
}
REGION_FIELDS = (
    "cluster_sites",
    "boundary_membrane_sites",
    "neighbor_membrane_sites",
    "boundary_cell_sites",
)
REQUEST_FIELDS = {
    "schema_version",
    "kind",
    "definition",
    "grid",
    "regions",
    "free_diffusion_m2_s",
    "relative_TJ",
    "adherens_factor",
    "tight_factor",
    "ion_modulators",
    "perimeter_policy",
}


def _number(value, name, *, nonnegative=False, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: require a finite JSON number")
    result = Decimal(str(value))
    if (nonnegative and result < 0) or (positive and result <= 0):
        raise ValueError(f"{name}: invalid sign")
    return result


def _ids(values, name):
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(v, str) or not v for v in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError(f"{name}: require unique nonempty JSON owner IDs")
    return values


def _mapping(value, keys, name):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{name}: require complete explicit owner map")
    return value


def _close(actual, expected, name):
    value = _number(actual, name, positive=True)
    tolerance = Decimal(64) * Decimal(str(sys.float_info.epsilon)) * abs(expected)
    if abs(value - expected) > tolerance:
        raise ValueError(f"{name}: incompatible physical geometry")


def _rows(rows, name):
    if not isinstance(rows, list):
        raise ValueError(f"{name}: require owner rows")
    ids = _ids([row.get("id") if isinstance(row, dict) else None for row in rows], name)
    return dict(zip(ids, rows, strict=True))


def _validate(request):
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        raise ValueError("Require the complete static barrier request")
    if type(request["schema_version"]) is not int or request["schema_version"] != 1:
        raise ValueError("Unsupported request schema")
    if request["kind"] != REQUEST_KIND or request["perimeter_policy"] != "sealed":
        raise ValueError("Only sealed static barrier preparation is supported")
    raw = request["definition"]
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Require an ordinary definition")
    model = raw.get("model", {})
    if model.get("id") != "resolved_tissue@1":
        raise ValueError("Only ordinary resolved_tissue@1 is supported")
    species = _rows(model.get("species"), "species")
    outside = _rows(model.get("extracellular"), "extracellular")
    faces = _rows(model.get("faces"), "faces")
    _rows(model.get("cells"), "cells")
    if any(row.get("reservoir") is not False for row in outside.values()):
        raise ValueError("Every exterior owner must be finite")
    if model.get("closure", {}).get("gauge_reference") not in outside:
        raise ValueError("A finite exterior gauge owner is required")
    grid = request["grid"]
    if not isinstance(grid, dict) or set(grid) != GRID_FIELDS:
        raise ValueError("Require all explicit JSON GridSpec fields")
    sites = _ids(grid["site_ids"], "site_ids")
    species_ids = _ids(grid["species_ids"], "species_ids")
    if set(sites) != set(outside) or set(species_ids) != set(species):
        raise ValueError("Grid and definition owners differ")
    if len(grid["valence"]) != len(species_ids):
        raise ValueError("Valence requires the complete species axis")
    for sid, z in zip(species_ids, grid["valence"], strict=True):
        if _number(z, "valence") != _number(species[sid]["valence"], "species valence"):
            raise ValueError("Grid valence does not match its species owner")
    shape = grid["shape"]
    if (
        not isinstance(shape, list)
        or len(shape) != 2
        or any(type(v) is not int or v < 2 for v in shape)
        or shape[0] * shape[1] != len(sites)
    ):
        raise ValueError("Require a complete C-order rectangular grid with ny,nx>=2")
    ny, nx = shape
    delta = _number(grid["delta_m"], "delta_m", positive=True)
    height = _number(grid["height_m"], "height_m", positive=True)
    coordinates = grid["coordinates_m"]
    if not isinstance(coordinates, list) or len(coordinates) != len(sites):
        raise ValueError("Require explicit site coordinates")
    if any(not isinstance(row, list) or len(row) != 2 for row in coordinates):
        raise ValueError("Coordinates require a site-by-two axis")
    coordinates = [[_number(v, "coordinate") for v in row] for row in coordinates]
    tolerance = (
        Decimal(64)
        * Decimal(str(sys.float_info.epsilon))
        * max(delta, *(abs(v) for row in coordinates for v in row))
    )
    for at, (x, y) in enumerate(coordinates):
        row, column = divmod(at, nx)
        if (
            abs(x - coordinates[0][0] - column * delta) > tolerance
            or abs(y - coordinates[0][1] - row * delta) > tolerance
        ):
            raise ValueError("Coordinates do not match the C-order uniform grid")
    face_ids = _ids(grid["internal_face_ids"], "internal_face_ids")
    pairs = grid["internal_face_sites"]
    if not isinstance(pairs, list) or len(pairs) != len(face_ids):
        raise ValueError("Require explicit internal face endpoints")
    if any(
        not isinstance(pair, list)
        or len(pair) != 2
        or pair[0] == pair[1]
        or any(site not in outside for site in pair)
        for pair in pairs
    ):
        raise ValueError("Invalid internal face endpoints")
    expected_edges = set()
    expected_perimeter = set()
    for at, site in enumerate(sites):
        row, column = divmod(at, nx)
        if column + 1 < nx:
            expected_edges.add(frozenset((site, sites[at + 1])))
        if row + 1 < ny:
            expected_edges.add(frozenset((site, sites[at + nx])))
        for on_boundary, side in (
            (row == 0, "S"),
            (row == ny - 1, "N"),
            (column == 0, "W"),
            (column == nx - 1, "E"),
        ):
            if on_boundary:
                expected_perimeter.add((site, side))
    edges = [frozenset(pair) for pair in pairs]
    if len(set(edges)) != len(edges) or set(edges) != expected_edges:
        raise ValueError("Every nearest-neighbor grid edge must occur exactly once")
    if set(face_ids) != set(faces):
        raise ValueError("Grid and definition internal face IDs differ")
    for face_id, pair in zip(face_ids, pairs, strict=True):
        face = faces[face_id]
        if frozenset((face.get("sender"), face.get("receiver"))) != frozenset(pair):
            raise ValueError("Face owners differ from grid endpoints")
        if face.get("law") != "logmean_electrodiffusion@1":
            raise ValueError("The ordinary logmean face law must remain explicit")
        _close(face["area_m2"], delta * height, "face area")
        _close(face["length_m"], delta, "face length")
        _mapping(face["diffusivity_m2_per_s"], species_ids, "existing face diffusivity")
        for value in face["diffusivity_m2_per_s"].values():
            _number(value, "existing face diffusivity", nonnegative=True)
    for row in outside.values():
        _close(row["volume_pL"], delta * delta * height * Decimal("1e15"), "outside volume")
    boundary_ids = _ids(grid["boundary_face_ids"], "boundary_face_ids")
    boundary_sites, boundary_sides = grid["boundary_face_sites"], grid["boundary_face_sides"]
    if (
        not isinstance(boundary_sites, list)
        or not isinstance(boundary_sides, list)
        or len(boundary_sites) != len(boundary_ids)
        or len(boundary_sides) != len(boundary_ids)
    ):
        raise ValueError("Require complete perimeter owner and side axes")
    perimeter = list(zip(boundary_sites, boundary_sides, strict=True))
    if len(set(perimeter)) != len(perimeter) or set(perimeter) != expected_perimeter:
        raise ValueError("Every sealed perimeter face must occur exactly once")
    if not isinstance(grid["provenance"], dict) or not grid["provenance"]:
        raise ValueError("Explicit nonempty grid provenance is required")
    regions = _mapping(request["regions"], REGION_FIELDS, "regions")
    for name in REGION_FIELDS:
        if not isinstance(regions[name], list) or any(
            site not in outside for site in regions[name]
        ):
            raise ValueError("Region occurrences require explicit valid site IDs")
    free = _mapping(request["free_diffusion_m2_s"], species_ids, "free_diffusion_m2_s")
    relative = _mapping(request["relative_TJ"], species_ids, "relative_TJ")
    modulators = _mapping(request["ion_modulators"], species_ids, "ion_modulators")
    for sid in species_ids:
        _number(free[sid], "free diffusion", nonnegative=True)
        _number(relative[sid], "relative TJ", nonnegative=True)
        _mapping(modulators[sid], sites, "modulator sites")
        for value in modulators[sid].values():
            _number(value, "ion modulator", nonnegative=True)
    _number(request["adherens_factor"], "adherens factor", nonnegative=True)
    _number(request["tight_factor"], "tight factor", nonnegative=True)
    return model, sites, species_ids, face_ids, pairs


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Prepared coefficients must remain finite in float64")
    return result


def prepare(request):
    """Return independent expected definition, coefficient maps and provenance arrays.

    Site and face maps are species -> stable owner ID -> float. Arithmetic uses
    80-digit Decimal values made from JSON numbers; arrays retain explicit grid
    axes and duplicate target occurrences. Sodium normalization precedes ionic
    modulation. It is a native initialization diagnostic, not a conductance.
    Full ordinary-tissue solvability remains the production binder's contract.
    """
    with localcontext() as context:
        context.prec = 80
        model, sites, species, face_ids, pairs = _validate(request)
        regions = request["regions"]
        targets = sum((regions[name] for name in REGION_FIELDS[1:]), [])
        adherens = _number(request["adherens_factor"], "adherens")
        tight = _number(request["tight_factor"], "tight")
        base, effective, faces = {}, {}, {}
        for sid in species:
            free = _number(request["free_diffusion_m2_s"][sid], "free")
            relative = _number(request["relative_TJ"][sid], "relative")
            row = dict.fromkeys(sites, free)
            for site in regions["cluster_sites"]:
                row[site] = free * adherens
            for site in targets:
                row[site] = free * tight * relative
            base[sid] = row
            effective[sid] = {
                site: row[site] * _number(request["ion_modulators"][sid][site], "modulator")
                for site in sites
            }
            faces[sid] = {}
            for face_id, (a, b) in zip(face_ids, pairs, strict=True):
                da, db = effective[sid][a], effective[sid][b]
                faces[sid][face_id] = Decimal(0) if da == 0 or db == 0 else 2 * da * db / (da + db)
        if "Na" not in base or max(base["Na"].values()) <= 0:
            raise ValueError(
                "Native sodium normalization requires Na and a positive pre-modulator maximum"
            )
        sodium_max = max(base["Na"].values())
        coefficients = {
            "site_base_m2_s": {
                s: {k: _float(v) for k, v in row.items()} for s, row in base.items()
            },
            "site_effective_m2_s": {
                s: {k: _float(v) for k, v in row.items()} for s, row in effective.items()
            },
            "face_m2_s": {s: {k: _float(v) for k, v in row.items()} for s, row in faces.items()},
        }
        output = deepcopy(request["definition"])
        for face in output["model"]["faces"]:
            face["diffusivity_m2_per_s"] = {
                s["id"]: coefficients["face_m2_s"][s["id"]][face["id"]]
                for s in output["model"]["species"]
            }
        arrays = {
            "species_ids": list(species),
            "site_ids": list(sites),
            "internal_face_ids": list(face_ids),
            "internal_face_sites": deepcopy(pairs),
            "boundary_target_site_ids": list(targets),
            "boundary_target_site_indices": [sites.index(site) for site in targets],
            "cluster_site_indices": [sites.index(site) for site in regions["cluster_sites"]],
            "free_diffusion_m2_s": [request["free_diffusion_m2_s"][s] for s in species],
            "relative_TJ": [request["relative_TJ"][s] for s in species],
            "ion_modulator": [
                [request["ion_modulators"][s][site] for site in sites] for s in species
            ],
            "initial_TJ_modulator": [[1.0] * len(sites) for _ in species],
            "site_base_m2_s": [[_float(base[s][site]) for site in sites] for s in species],
            "site_effective_m2_s": [
                [_float(effective[s][site]) for site in sites] for s in species
            ],
            "face_m2_s": [[_float(faces[s][face]) for face in face_ids] for s in species],
            "sodium_weight": [_float(base["Na"][site] / sodium_max) for site in sites],
            "grid_to_definition_species_index": [
                [row["id"] for row in model["species"]].index(s) for s in species
            ],
            "grid_to_definition_site_index": [
                [row["id"] for row in model["extracellular"]].index(s) for s in sites
            ],
            "grid_to_definition_face_index": [
                [row["id"] for row in model["faces"]].index(s) for s in face_ids
            ],
        }
        return {"definition": output, "coefficients": coefficients, "arrays": arrays}
